from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import timedelta
from pydantic import BaseModel
from app.core.database import get_db
from app.models import models
from app.models.models import Business, Service, Booking as BookingModel, User, BusinessWorker, WorkingHours
from datetime import time
from app.models.schemas import BusinessCreateSchema
from typing import List, Optional
from app.core.security import verify_password, create_access_token, get_current_business
from app.core.config import settings
import math
import requests

router = APIRouter(tags=["business"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# ------------------------------
# Helper Functions for GPS
# ------------------------------
def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two GPS coordinates in kilometers using Haversine formula"""
    R = 6371  # Earth's radius in kilometers

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)

    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c

def geocode_address(address: str, city: str, country: str) -> tuple:
    """Convert address to GPS coordinates using OpenStreetMap Nominatim API (free, no API key needed)"""
    try:
        full_address = f"{address}, {city}, {country}"
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": full_address,
            "format": "json",
            "limit": 1
        }
        headers = {
            "User-Agent": "Booksy-App/1.0"  # Nominatim requires a User-Agent
        }

        response = requests.get(url, params=params, headers=headers, timeout=5)

        if response.status_code == 200 and response.json():
            data = response.json()[0]
            return float(data["lat"]), float(data["lon"])
        return None, None
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None, None


# ------------------------------
# Business Signup
# ------------------------------
@router.post("/signup")
def create_business(business_in: BusinessCreateSchema, db: Session = Depends(get_db)):
    print("Signup raw password:", business_in.password)
    hashed_pw = get_password_hash(business_in.password)
    print("Signup hashed password:", hashed_pw)

    # Check if email already exists
    existing_business = db.query(models.Business).filter(models.Business.email == business_in.email).first()
    if existing_business:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Use frontend-provided coordinates if available, otherwise geocode address
    latitude = business_in.latitude
    longitude = business_in.longitude

    print(f"🔍 Received from frontend - latitude: {latitude}, longitude: {longitude}")

    if latitude and longitude:
        print(f"✅ Using frontend coordinates: ({latitude}, {longitude})")
    elif business_in.address and business_in.city and business_in.country:
        # Fallback to backend geocoding if frontend didn't provide coordinates
        print(f"⚠️ Frontend coordinates not provided, trying backend geocoding...")
        latitude, longitude = geocode_address(business_in.address, business_in.city, business_in.country)
        if latitude and longitude:
            print(f"✅ Backend geocoded: {business_in.address} → ({latitude}, {longitude})")
        else:
            print(f"⚠️ Could not geocode address: {business_in.address}")

    # Yeni biznes yarat
    db_business = models.Business(
        name=business_in.name,
        owner_name=business_in.owner_name,
        email=business_in.email,
        hashed_password=hashed_pw,
        phone=business_in.phone,
        address=business_in.address,
        city=business_in.city,
        country=business_in.country,
        category=business_in.category,
        description=business_in.description,
        latitude=latitude,
        longitude=longitude
    )
    db.add(db_business)
    db.commit()
    db.refresh(db_business)

    # Servisleri əlavə et
    for service in business_in.services:
        db_service = Service(
            name=service.name,
            price=service.price,
            duration=service.duration,
            business_id=db_business.id
        )
        db.add(db_service)
    db.commit()

    # Generate access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_business.email, "role": "business"},
        expires_delta=access_token_expires
    )

    return {
        "message": "Business created successfully",
        "business_id": db_business.id,
        "access_token": access_token,
        "token_type": "bearer"
    }


# ------------------------------
# Business Login
# ------------------------------
class BusinessLoginSchema(BaseModel):
    email: str
    password: str


@router.post("/login")
def login_business(login_data: BusinessLoginSchema, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.email == login_data.email).first()
    
    if not business:
        raise HTTPException(status_code=400, detail="Business not found")

    # Debug
    print("Login attempt:", login_data.email, login_data.password)
    print("DB hashed:", business.hashed_password)

    # Check if password is hashed or plain text
    verify_result = False
    if business.hashed_password.startswith('$2b$') or business.hashed_password.startswith('$2a$'):
        # Password is hashed, verify using bcrypt
        verify_result = verify_password(login_data.password, business.hashed_password)
    else:
        # Password is plain text (for test accounts), compare directly
        verify_result = (login_data.password == business.hashed_password)

    print("Verify result:", verify_result)

    if not verify_result:
        raise HTTPException(status_code=400, detail="Incorrect password")
    
    access_token_expires = timedelta(minutes=60 * 24)
    access_token = create_access_token(
        data={"sub": business.email, "role": "business"},
        expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "business_id": business.id,
        "business_name": business.name
    }


# ------------------------------
# Get Business Profile
# ------------------------------
@router.get("/test")
def test_business_endpoint():
    return {"message": "Business test endpoint working"}

@router.get("/profile", response_model=None)
async def get_business_profile(current_business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    # Get business services
    services = db.query(Service).filter(Service.business_id == current_business.id).all()

    # Get bookings for business services
    service_ids = [s.id for s in services]
    bookings = []
    if service_ids:
        bookings = db.query(BookingModel).filter(BookingModel.service_id.in_(service_ids)).all()

    # Calculate stats
    total_bookings = len(bookings)
    monthly_revenue = sum(b.service.price for b in bookings if b.service and b.status == "completed")
    completed_bookings = [b for b in bookings if b.status == "completed"]
    rating = 4.5  # Default rating for now
    review_count = len(completed_bookings)

    # Get workers for this business
    workers = [
        {
            "id": bw.worker.id,
            "email": bw.worker.email,
            "first_name": bw.worker.first_name,
            "last_name": bw.worker.last_name,
            "full_name": f"{bw.worker.first_name or ''} {bw.worker.last_name or ''}".strip() or bw.worker.email,
            "phone_number": bw.worker.phone_number,
            "is_barber": bw.worker.is_barber
        }
        for bw in current_business.business_workers
        if bw.worker
    ]

    import json

    # Parse working hours from JSON
    working_hours = None
    if current_business.working_hours_json:
        try:
            working_hours = json.loads(current_business.working_hours_json)
        except:
            working_hours = None

    # Parse gallery photos
    gallery_photos = []
    if current_business.gallery_photos:
        try:
            gallery_photos = json.loads(current_business.gallery_photos)
        except:
            gallery_photos = []

    return {
        "id": current_business.id,
        "name": current_business.name,
        "owner_name": current_business.owner_name,
        "email": current_business.email,
        "phone": current_business.phone,
        "address": current_business.address,
        "city": current_business.city,
        "category": current_business.category,
        "description": current_business.description,
        "avatar": current_business.avatar_url or "",
        "coverPhoto": current_business.cover_photo_url or "",
        "galleryPhotos": gallery_photos,
        "rating": rating,
        "reviewCount": review_count,
        "totalBookings": total_bookings,
        "monthlyRevenue": monthly_revenue,
        "workers": workers,
        "workingHours": working_hours,
        "services": [
            {
                "id": s.id,
                "name": s.name,
                "price": s.price,
                "duration": s.duration,
                "description": s.description
            }
            for s in services
        ]
    }


# ------------------------------
# Update Business Profile
# ------------------------------
class BusinessUpdateSchema(BaseModel):
    name: str = None
    owner_name: str = None
    phone: str = None
    address: str = None
    city: str = None
    description: str = None
    working_hours: dict = None

@router.put("/profile", response_model=None)
async def update_business_profile(
    update_data: BusinessUpdateSchema,
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    import json

    # Update only provided fields
    if update_data.name is not None:
        current_business.name = update_data.name
    if update_data.owner_name is not None:
        current_business.owner_name = update_data.owner_name
    if update_data.phone is not None:
        current_business.phone = update_data.phone
    if update_data.address is not None:
        current_business.address = update_data.address
    if update_data.city is not None:
        current_business.city = update_data.city
    if update_data.description is not None:
        current_business.description = update_data.description
    if update_data.working_hours is not None:
        current_business.working_hours_json = json.dumps(update_data.working_hours)

    db.commit()
    db.refresh(current_business)

    return {
        "success": True,
        "message": "Profile updated successfully",
        "business": {
            "id": current_business.id,
            "name": current_business.name,
            "owner_name": current_business.owner_name,
            "email": current_business.email,
            "phone": current_business.phone,
            "address": current_business.address,
            "city": current_business.city,
            "description": current_business.description
        }
    }


# ------------------------------
# Business Services Management
# ------------------------------
class ServiceCreateSchema(BaseModel):
    name: str
    price: float
    duration: int
    description: str = ""

@router.post("/my-services")
def create_service(service_data: ServiceCreateSchema, current_business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    # Check if service name already exists for this business
    existing_service = db.query(Service).filter(
        Service.name == service_data.name,
        Service.business_id == current_business.id
    ).first()

    if existing_service:
        raise HTTPException(status_code=400, detail="Service with this name already exists")

    # Create new service
    db_service = Service(
        name=service_data.name,
        price=service_data.price,
        duration=service_data.duration,
        description=service_data.description,
        business_id=current_business.id
    )

    db.add(db_service)
    db.commit()
    db.refresh(db_service)

    return {
        "id": db_service.id,
        "name": db_service.name,
        "price": db_service.price,
        "duration": db_service.duration,
        "description": db_service.description
    }

@router.get("/my-services")
def get_business_services(current_business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    services = db.query(Service).filter(Service.business_id == current_business.id).all()
    return [{
        "id": s.id,
        "name": s.name,
        "price": s.price,
        "duration": s.duration,
        "description": s.description
    } for s in services]

@router.delete("/my-services/{service_id}")
def delete_service(service_id: int, current_business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    service = db.query(Service).filter(
        Service.id == service_id,
        Service.business_id == current_business.id
    ).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    db.delete(service)
    db.commit()

    return {"message": "Service deleted successfully"}


# ------------------------------
# Get Business Appointments
# ------------------------------
@router.get("/appointments")
def get_business_appointments(current_business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    # Get all services for this business
    business_services = db.query(Service).filter(Service.business_id == current_business.id).all()
    service_ids = [s.id for s in business_services]

    if not service_ids:
        return []

    # Get all bookings for business services
    bookings = db.query(BookingModel).filter(BookingModel.service_id.in_(service_ids)).all()

    return [
        {
            "id": b.id,
            "customer_name": b.customer_name,
            "customer_phone": b.customer_phone,
            "service_name": b.service.name if b.service else "Unknown Service",
            "start_time": b.start_time.isoformat() if b.start_time else None,
            "status": b.status
        }
        for b in bookings
    ]


# ------------------------------
# Get Business Activity
# ------------------------------
@router.get("/activity")
def get_business_activity(current_business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
    # Get recent bookings for this business
    business_services = db.query(Service).filter(Service.business_id == current_business.id).all()
    service_ids = [s.id for s in business_services]

    if not service_ids:
        return []

    # Get recent bookings (last 10)
    recent_bookings = (
        db.query(BookingModel)
        .filter(BookingModel.service_id.in_(service_ids))
        .order_by(BookingModel.start_time.desc())
        .limit(10)
        .all()
    )

    return [
        {
            "id": b.id,
            "message": f"New booking: {b.customer_name} for {b.service.name if b.service else 'Unknown Service'}",
            "timestamp": b.start_time.isoformat() if b.start_time else None,
            "type": "booking"
        }
        for b in recent_bookings
    ]


# ------------------------------
# Get All Businesses
# ------------------------------
@router.get("/")
def read_businesses(db: Session = Depends(get_db)):
    try:
        businesses = db.query(models.Business).all()

        result = []
        for b in businesses:
            try:
                # Count real workers for this business
                workers_count = db.query(BusinessWorker).filter(
                    BusinessWorker.business_id == b.id
                ).count()

                # Count real services for this business (directly by business_id)
                services_count = db.query(Service).filter(
                    Service.business_id == b.id
                ).count()

                result.append({
                    "id": b.id,
                    "business_name": b.name,
                    "name": b.name,
                    "owner_name": b.owner_name,
                    "email": b.email,
                    "phone": b.phone or "",
                    "address": b.address or "",
                    "city": b.city or "",
                    "country": getattr(b, 'country', ""),
                    "business_type": b.category or "barber",
                    "category": b.category or "barber",
                    "description": b.description or "Professional services",
                    "latitude": b.latitude or (41.0082 + (b.id * 0.01)),
                    "longitude": b.longitude or (28.9784 + (b.id * 0.01)),
                    "avatar_url": getattr(b, 'avatar_url', None),
                    "cover_photo_url": getattr(b, 'cover_photo_url', None),
                    "workers_count": workers_count,
                    "services_count": services_count
                })
            except Exception as e:
                print(f"Error processing business {b.id}: {e}")
                continue

        return result
    except Exception as e:
        print(f"Error in read_businesses: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching businesses: {str(e)}")

@router.get("/list")
def get_businesses_list(db: Session = Depends(get_db)):
    businesses = db.query(models.Business).all()
    print(f"🔍 Database query returned {len(businesses)} businesses")
    for b in businesses:
        print(f"   - Business: {b.name} (ID: {b.id})")
    return [{
        "id": b.id,
        "business_name": b.name,
        "owner_name": b.owner_name,
        "email": b.email,
        "phone": b.phone,
        "address": b.address,
        "city": b.city,
        "country": b.country,
        "description": b.description,
        "avatar": None,
        "cover_photo": None,
        "facebook": None,
        "instagram": None,
        "category": b.category or "barber"
    } for b in businesses]


# ------------------------------
# Get Nearby Businesses (GPS-based) - MOVED BEFORE /{business_id}
# ------------------------------
@router.get("/nearby")
def get_nearby_businesses(
    lat: float = Query(..., description="User's latitude"),
    lon: float = Query(..., description="User's longitude"),
    radius: float = Query(10, description="Search radius in kilometers"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db)
):
    """Get businesses near user's location"""
    # Get all businesses with GPS coordinates
    businesses = db.query(models.Business).filter(
        models.Business.latitude.isnot(None),
        models.Business.longitude.isnot(None)
    ).all()

    # Filter by category if provided
    if category:
        businesses = [b for b in businesses if b.category == category]

    # Calculate distances and filter by radius
    nearby_businesses = []
    for business in businesses:
        distance = calculate_distance(lat, lon, business.latitude, business.longitude)

        if distance <= radius:
            # Get services count
            services_count = db.query(Service).filter(Service.business_id == business.id).count()

            nearby_businesses.append({
                "id": business.id,
                "name": business.name,
                "owner_name": business.owner_name,
                "address": business.address,
                "city": business.city,
                "category": business.category,
                "description": business.description,
                "phone": business.phone,
                "avatar_url": business.avatar_url,
                "cover_photo_url": business.cover_photo_url,
                "latitude": business.latitude,
                "longitude": business.longitude,
                "distance": round(distance, 2),  # Distance in km
                "services_count": services_count
            })

    # Sort by distance (closest first)
    nearby_businesses.sort(key=lambda x: x["distance"])

    return {
        "total": len(nearby_businesses),
        "user_location": {"lat": lat, "lon": lon},
        "radius_km": radius,
        "businesses": nearby_businesses
    }


# ------------------------------
# Geocode Address Endpoint - MOVED BEFORE /{business_id}
# ------------------------------
class GeocodeRequest(BaseModel):
    address: str
    city: str
    country: str

@router.post("/geocode")
def geocode_address_endpoint(request: GeocodeRequest):
    """Convert address to GPS coordinates"""
    latitude, longitude = geocode_address(request.address, request.city, request.country)

    if latitude and longitude:
        return {
            "success": True,
            "latitude": latitude,
            "longitude": longitude,
            "address": f"{request.address}, {request.city}, {request.country}"
        }
    else:
        return {
            "success": False,
            "message": "Could not geocode address"
        }


# ------------------------------
# Get Business Details by ID
# ------------------------------
@router.get("/{business_id}")
def get_business_by_id(business_id: int, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Parse gallery photos
    import json
    gallery_photos = []
    if business.gallery_photos:
        try:
            gallery_photos = json.loads(business.gallery_photos)
        except:
            gallery_photos = []

    return {
        "id": business.id,
        "business_name": business.name,
        "owner_name": business.owner_name,
        "email": business.email,
        "phone": business.phone,
        "address": business.address,
        "city": business.city,
        "description": business.description,
        "avatar_url": business.avatar_url,
        "cover_photo_url": business.cover_photo_url,
        "gallery_photos": gallery_photos,
        "facebook": None,
        "instagram": None,
        "category": business.category or "barber"
    }


# ------------------------------
# Get Business Workers (Users who are barbers)
# ------------------------------
@router.get("/{business_id}/workers")
def get_business_workers(business_id: int, db: Session = Depends(get_db)):
    # Verify business exists
    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Get workers for this specific business from business_workers table
    worker_ids = db.query(BusinessWorker.worker_id).filter(
        BusinessWorker.business_id == business_id
    ).all()
    worker_ids = [w[0] for w in worker_ids]

    if not worker_ids:
        return []

    # Get worker details
    workers = db.query(models.User).filter(
        models.User.id.in_(worker_ids),
        models.User.is_barber == True
    ).all()

    return [{
        "id": w.id,
        "full_name": f"{w.first_name or ''} {w.last_name or ''}".strip() or w.email.split('@')[0],
        "first_name": w.first_name,
        "last_name": w.last_name,
        "email": w.email,
        "phone": w.phone_number,
        "avatar_url": w.avatar_url,
        "rating": w.rating or 0.0,
        "bio": w.barber_bio,
        "business_id": business_id
    } for w in workers]


# ------------------------------
# Add Worker to Business
# ------------------------------
class AddWorkerSchema(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone_number: str = ""
    password: str
    is_barber: bool = True

@router.post("/workers/add")
def add_worker_to_business(
    worker_data: AddWorkerSchema,
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """
    Add a new worker (barber) to the current business.
    This creates a new user and links them to the business.
    """
    # Check if user with this email already exists
    existing_user = db.query(User).filter(User.email == worker_data.email).first()

    if existing_user:
        # If user exists, just link them to this business
        # Check if they're already linked
        existing_link = db.query(BusinessWorker).filter(
            BusinessWorker.business_id == current_business.id,
            BusinessWorker.worker_id == existing_user.id
        ).first()

        if existing_link:
            raise HTTPException(status_code=400, detail="Worker already added to this business")

        # Create link
        business_worker = BusinessWorker(
            business_id=current_business.id,
            worker_id=existing_user.id
        )
        db.add(business_worker)
        db.commit()
        db.refresh(business_worker)

        return {
            "message": "Existing worker added to business successfully",
            "worker": {
                "id": existing_user.id,
                "email": existing_user.email,
                "first_name": existing_user.first_name,
                "last_name": existing_user.last_name,
                "full_name": f"{existing_user.first_name or ''} {existing_user.last_name or ''}".strip() or existing_user.email
            }
        }

    # Create new user
    hashed_password = get_password_hash(worker_data.password)
    new_user = User(
        email=worker_data.email,
        hashed_password=hashed_password,
        first_name=worker_data.first_name,
        last_name=worker_data.last_name,
        phone_number=worker_data.phone_number,
        is_barber=worker_data.is_barber,
        is_active=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Link new user to business
    business_worker = BusinessWorker(
        business_id=current_business.id,
        worker_id=new_user.id
    )
    db.add(business_worker)
    db.commit()
    db.refresh(business_worker)

    return {
        "message": "Worker added successfully",
        "worker": {
            "id": new_user.id,
            "email": new_user.email,
            "first_name": new_user.first_name,
            "last_name": new_user.last_name,
            "full_name": f"{new_user.first_name or ''} {new_user.last_name or ''}".strip() or new_user.email,
            "phone_number": new_user.phone_number,
            "is_barber": new_user.is_barber
        }
    }


# ------------------------------
# Get Business Services (Public)
# ------------------------------
@router.get("/{business_id}/services")
def get_business_services_public(business_id: int, db: Session = Depends(get_db)):
    # Verify business exists
    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Get all services for this business
    services = db.query(Service).filter(Service.business_id == business_id).all()

    return [{
        "id": s.id,
        "name": s.name,
        "price": s.price,
        "duration": s.duration,
        "description": s.description,
        "business_id": business_id
    } for s in services]


# ------------------------------
# Get Worker Services
# ------------------------------
@router.get("/worker/{worker_id}/services")
def get_worker_services(worker_id: int, db: Session = Depends(get_db)):
    # Verify worker exists
    worker = db.query(models.User).filter(models.User.id == worker_id, models.User.is_barber == True).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Get services for this worker/barber
    # Method 1: Services directly assigned to barber
    direct_services = db.query(Service).filter(Service.barber_id == worker_id).all()

    # Method 2: Services through BarberService relationship
    barber_service_ids = db.query(models.BarberService.service_id).filter(
        models.BarberService.barber_id == worker_id
    ).all()
    service_ids = [bs[0] for bs in barber_service_ids]
    related_services = db.query(Service).filter(Service.id.in_(service_ids)).all() if service_ids else []

    # Combine both methods and remove duplicates
    all_services = {s.id: s for s in (direct_services + related_services)}

    return [{
        "id": s.id,
        "name": s.name,
        "price": s.price,
        "duration": s.duration,
        "description": s.description,
        "worker_id": worker_id
    } for s in all_services.values()]


# ------------------------------
# Business Photo Upload Endpoints
# ------------------------------
from fastapi import UploadFile, File
import os
import shutil
from datetime import datetime

@router.post("/avatar")
async def upload_business_avatar(
    file: UploadFile = File(...),
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Upload business avatar/profile photo"""
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = "uploads/business_avatars"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = file.filename.split(".")[-1]
        filename = f"business_{current_business.id}_{timestamp}.{file_extension}"
        file_path = os.path.join(upload_dir, filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Update business avatar_url in database
        avatar_url = f"/uploads/business_avatars/{filename}"
        current_business.avatar_url = avatar_url
        db.commit()
        
        return {
            "message": "Avatar uploaded successfully",
            "avatar_url": avatar_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload avatar: {str(e)}")


@router.post("/cover-photo")
async def upload_business_cover_photo(
    file: UploadFile = File(...),
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Upload business cover photo"""
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = "uploads/business_covers"
        os.makedirs(upload_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = file.filename.split(".")[-1]
        filename = f"business_{current_business.id}_{timestamp}.{file_extension}"
        file_path = os.path.join(upload_dir, filename)
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Update business cover_photo_url in database
        cover_url = f"/uploads/business_covers/{filename}"
        current_business.cover_photo_url = cover_url
        db.commit()
        
        return {
            "message": "Cover photo uploaded successfully",
            "cover_photo_url": cover_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload cover photo: {str(e)}")

@router.post("/upload-gallery-photo")
async def upload_gallery_photo(
    file: UploadFile = File(...),
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Upload a photo to business gallery"""
    try:
        upload_dir = "uploads/business_gallery"
        os.makedirs(upload_dir, exist_ok=True)

        file_extension = file.filename.split('.')[-1]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"business_{current_business.id}_gallery_{timestamp}.{file_extension}"
        file_path = os.path.join(upload_dir, filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        photo_url = f"/uploads/business_gallery/{filename}"

        # Get current gallery photos
        import json
        current_photos = []
        if current_business.gallery_photos:
            current_photos = json.loads(current_business.gallery_photos)

        # Add new photo
        current_photos.append(photo_url)

        # Update database
        current_business.gallery_photos = json.dumps(current_photos)
        db.commit()

        return {
            "success": True,
            "photo_url": photo_url,
            "gallery_photos": current_photos
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload gallery photo: {str(e)}")

@router.delete("/gallery-photo")
async def delete_gallery_photo(
    photo_url: str,
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Delete a photo from business gallery"""
    try:
        import json
        if not current_business.gallery_photos:
            return {"success": True, "gallery_photos": []}

        current_photos = json.loads(current_business.gallery_photos)

        # Remove the photo from list
        if photo_url in current_photos:
            current_photos.remove(photo_url)

            # Delete file
            file_path = photo_url.lstrip('/')
            if os.path.exists(file_path):
                os.remove(file_path)

        # Update database
        current_business.gallery_photos = json.dumps(current_photos)
        db.commit()

        return {
            "success": True,
            "gallery_photos": current_photos
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete gallery photo: {str(e)}")


# ------------------------------
# Worker Working Hours Management
# ------------------------------
class WorkerHourSchema(BaseModel):
    day_of_week: int  # 0=Monday, 6=Sunday
    start_time: str   # "09:00"
    end_time: str     # "17:00"
    is_working: bool = True

class WorkerHoursUpdateSchema(BaseModel):
    worker_id: int
    hours: List[WorkerHourSchema]

@router.get("/workers/{worker_id}/hours")
async def get_worker_hours(
    worker_id: int,
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    # Verify worker belongs to this business
    business_worker = db.query(BusinessWorker).filter(
        BusinessWorker.business_id == current_business.id,
        BusinessWorker.worker_id == worker_id
    ).first()

    if not business_worker:
        raise HTTPException(status_code=404, detail="Worker not found in this business")

    # Get worker's working hours
    hours = db.query(WorkingHours).filter(
        WorkingHours.barber_id == worker_id
    ).order_by(WorkingHours.day_of_week).all()

    return [
        {
            "id": h.id,
            "day_of_week": h.day_of_week,
            "start_time": h.start_time.strftime("%H:%M") if h.start_time else "09:00",
            "end_time": h.end_time.strftime("%H:%M") if h.end_time else "17:00",
            "is_working": h.is_working
        }
        for h in hours
    ]

@router.put("/workers/{worker_id}/hours")
async def update_worker_hours(
    worker_id: int,
    hours_data: List[WorkerHourSchema],
    current_business: Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    # Verify worker belongs to this business
    business_worker = db.query(BusinessWorker).filter(
        BusinessWorker.business_id == current_business.id,
        BusinessWorker.worker_id == worker_id
    ).first()

    if not business_worker:
        raise HTTPException(status_code=404, detail="Worker not found in this business")

    # Delete existing hours for this worker
    db.query(WorkingHours).filter(WorkingHours.barber_id == worker_id).delete()

    # Add new hours
    for hour in hours_data:
        # Parse time strings
        start_parts = hour.start_time.split(":")
        end_parts = hour.end_time.split(":")

        new_hour = WorkingHours(
            barber_id=worker_id,
            day_of_week=hour.day_of_week,
            start_time=time(int(start_parts[0]), int(start_parts[1])),
            end_time=time(int(end_parts[0]), int(end_parts[1])),
            is_working=hour.is_working
        )
        db.add(new_hour)

    db.commit()

    return {"success": True, "message": "Worker hours updated successfully"}


# Public endpoint to get worker hours (for booking)
@router.get("/public/workers/{worker_id}/hours")
def get_worker_hours_public(
    worker_id: int,
    db: Session = Depends(get_db)
):
    # Get worker's working hours
    hours = db.query(WorkingHours).filter(
        WorkingHours.barber_id == worker_id
    ).order_by(WorkingHours.day_of_week).all()

    return [
        {
            "day_of_week": h.day_of_week,
            "start_time": h.start_time.strftime("%H:%M") if h.start_time else "09:00",
            "end_time": h.end_time.strftime("%H:%M") if h.end_time else "17:00",
            "is_working": h.is_working
        }
        for h in hours
    ]
