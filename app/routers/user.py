from sqlalchemy import func
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import User as UserModel, Booking, FavoriteBarber
from app.models.schemas import UserSchema, UserUpdate, UserStats, NotificationSettings, BookingSchema, UserCreate
from app.core import security
from typing import List
from datetime import datetime

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
    return {"avatar_url": file_location}

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
    return UserSchema(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone_number=current_user.phone_number,
        birth_date=current_user.birth_date,
        address=current_user.address,
        loyalty_points=current_user.loyalty_points,
        membership_tier=current_user.membership_tier,
        rating=current_user.rating,
        notification_settings=current_user.notification_settings,
        avatar_url=current_user.avatar_url,
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

@router.get("/favorites", response_model=List[UserSchema])
def get_favorite_barbers(
    current_user: UserModel = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    favorites = db.query(FavoriteBarber).filter(FavoriteBarber.user_id == current_user.id).all()
    barbers = [db.query(UserModel).filter(UserModel.id == fav.barber_id).first() for fav in favorites]
    return [
        UserSchema(
            id=barber.id,
            email=barber.email,
            first_name=barber.first_name,
            last_name=barber.last_name,
            phone_number=barber.phone_number,
            birth_date=barber.birth_date,
            address=barber.address,
            loyalty_points=barber.loyalty_points,
            membership_tier=barber.membership_tier,
            rating=barber.rating,
            notification_settings=barber.notification_settings,
            avatar_url=barber.avatar_url,
            is_barber=barber.is_barber,
            is_active=barber.is_active,
            created_at=barber.created_at
        )
        for barber in barbers if barber
    ]

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
    return UserSchema(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone_number=current_user.phone_number,
        birth_date=current_user.birth_date,
        address=current_user.address,
        loyalty_points=current_user.loyalty_points,
        membership_tier=current_user.membership_tier,
        rating=current_user.rating,
        notification_settings=current_user.notification_settings,
        avatar_url=current_user.avatar_url,
        is_barber=current_user.is_barber,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )