from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import User as UserModel, Booking, FavoriteBarber, Service
from app.models.schemas import UserSchema, UserUpdate, UserStats, NotificationSettings, BookingSchema, UserCreate
from app.core import security
from typing import List
from datetime import datetime

# Import get_full_image_url helper
import os

def get_full_image_url(relative_url):
    """Convert relative image URL to full URL"""
    if not relative_url:
        return None

    # Get base URL from environment or use production URL
    base_url = os.getenv('BASE_URL', 'https://aponti.org')

    # If it's already a full URL with localhost, replace with production URL
    if relative_url.startswith('http://localhost'):
        relative_url = relative_url.replace('http://localhost:8000/', '')
        relative_url = relative_url.replace('http://localhost/', '')
    # If it's already a production URL, return as is
    elif relative_url.startswith('http'):
        return relative_url

    # Remove leading slash if present to avoid double slashes
    relative_url = relative_url.lstrip('/')
    return f"{base_url}/{relative_url}"

router = APIRouter(
    tags=["users"]
)

@router.post("/avatar", response_model=dict)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: UserModel = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    # Avatar yükleme işlemi burada yapılacak
    filename = f"{current_user.id}_{file.filename}"
    file_location = f"uploads/{filename}"
    with open(file_location, "wb") as buffer:
        buffer.write(await file.read())
    current_user.avatar_url = file_location
    db.commit()

    # Return full URL to frontend
    full_url = get_full_image_url(file_location)
    return {"avatar_url": full_url}

@router.get("/appointments/my", response_model=List[BookingSchema])
def get_my_appointments(
    current_user: UserModel = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    appointments = db.query(Booking).filter(Booking.user_id == current_user.id).all()
    return appointments

@router.get("/me", response_model=UserSchema)
def get_current_user_route(
    current_user: UserModel = Depends(security.get_current_user)
):
    full_name = None
    if current_user.first_name or current_user.last_name:
        full_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()

    avatar_url = get_full_image_url(current_user.avatar_url)
    print(f"👤 GET /users/me - User: {current_user.email}")
    print(f"   Avatar DB: {current_user.avatar_url}")
    print(f"   Avatar Full URL: {avatar_url}")

    return UserSchema(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        full_name=full_name,
        phone_number=current_user.phone_number,
        birth_date=current_user.birth_date,
        address=current_user.address,
        latitude=current_user.latitude,
        longitude=current_user.longitude,
        loyalty_points=current_user.loyalty_points or 0,
        membership_tier=current_user.membership_tier,
        rating=current_user.rating,
        notification_settings=current_user.notification_settings,
        avatar_url=avatar_url,
        is_barber=current_user.is_barber,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )

@router.get("/stats", response_model=UserStats)
def get_user_stats(
    current_user: UserModel = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    total_appointments = db.query(Booking).filter(Booking.user_id == current_user.id).count()
    upcoming_appointments = db.query(Booking).filter(
        Booking.user_id == current_user.id,
        Booking.start_time > func.now()
    ).count()
    completed_appointments = db.query(Booking).filter(
        Booking.user_id == current_user.id,
        Booking.status == "completed"
    ).count()
    favorite_barbers = db.query(FavoriteBarber).filter(FavoriteBarber.user_id == current_user.id).count()
    return UserStats(
        total_appointments=total_appointments,
        upcoming_appointments=upcoming_appointments,
        completed_appointments=completed_appointments,
        favorite_barbers=favorite_barbers
    )

@router.get("/favorites")
def get_favorite_services(
    current_user: UserModel = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """Get favorite services for the current user"""
    favorites = db.query(FavoriteBarber).filter(FavoriteBarber.user_id == current_user.id).all()

    result = []
    for fav in favorites:
        if fav.service_id:
            # Service-based favorite
            service = db.query(Service).filter(Service.id == fav.service_id).first()
            if service:
                barber = db.query(UserModel).filter(UserModel.id == service.barber_id).first()
                result.append({
                    "id": service.id,
                    "service_id": service.id,
                    "name": service.name,
                    "category": service.name,  # Show service name
                    "price": service.price,
                    "duration": service.duration,
                    "barber_id": service.barber_id,
                    "barber_name": f"{barber.first_name or ''} {barber.last_name or ''}".strip() if barber else "Unknown",
                    "image": barber.avatar_url if barber else None
                })
        elif fav.barber_id:
            # Legacy barber-based favorite
            barber = db.query(UserModel).filter(UserModel.id == fav.barber_id).first()
            if barber:
                result.append({
                    "id": barber.id,
                    "name": f"{barber.first_name or ''} {barber.last_name or ''}".strip() or "Barber",
                    "category": f"{barber.first_name or ''} {barber.last_name or ''}".strip() or "Barber",
                    "barber_id": barber.id,
                    "image": barber.avatar_url
                })

    return result

@router.get("/favorites/services")
def get_favorite_services_alias(
    current_user: UserModel = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    """Get favorite services for the current user (alias endpoint)"""
    return get_favorite_services(current_user=current_user, db=db)

@router.post("/favorites/services/{service_id}")
def add_favorite_service(
    service_id: int,
    current_user: UserModel = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    # Check if service exists
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Check if already favorited
    existing = db.query(FavoriteBarber).filter(
        FavoriteBarber.user_id == current_user.id,
        FavoriteBarber.service_id == service_id
    ).first()

    if existing:
        return {"message": "Already in favorites", "favorite_id": existing.id}

    # Add to favorites with service_id
    favorite = FavoriteBarber(user_id=current_user.id, service_id=service_id, barber_id=service.barber_id)
    db.add(favorite)
    db.commit()
    db.refresh(favorite)

    return {"message": "Added to favorites", "favorite_id": favorite.id}

@router.delete("/favorites/services/{service_id}")
def remove_favorite_service(
    service_id: int,
    current_user: UserModel = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    favorite = db.query(FavoriteBarber).filter(
        FavoriteBarber.user_id == current_user.id,
        FavoriteBarber.service_id == service_id
    ).first()

    if not favorite:
        raise HTTPException(status_code=404, detail="Favorite not found")

    db.delete(favorite)
    db.commit()

    return {"message": "Removed from favorites"}

@router.put("/me", response_model=UserSchema)
def update_current_user_route(
    user_update: UserUpdate,
    current_user: UserModel = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    for field, value in user_update.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)

    full_name = None
    if current_user.first_name or current_user.last_name:
        full_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()

    return UserSchema(
        id=current_user.id,
        email=current_user.email,
        full_name=full_name,
        phone_number=current_user.phone_number,
        birth_date=current_user.birth_date,
        address=current_user.address,
        loyalty_points=current_user.loyalty_points or 0,
        membership_tier=current_user.membership_tier,
        rating=current_user.rating,
        notification_settings=current_user.notification_settings,
        avatar_url=current_user.avatar_url,
        is_barber=current_user.is_barber,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )