from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from datetime import timedelta
from pydantic import BaseModel
from app.core.database import get_db
from app.models import models
from app.models.models import Business, Service, Booking as BookingModel
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

    # Geocode address to get GPS coordinates
    latitude, longitude = None, None
    if business_in.address and business_in.city and business_in.country:
        latitude, longitude = geocode_address(business_in.address, business_in.city, business_in.country)
        if latitude and longitude:
            print(f"✅ Geocoded: {business_in.address} → ({latitude}, {longitude})")
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

    verify_result = verify_password(login_data.password, business.hashed_password)
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
def get_business_profile(current_business: Business = Depends(get_current_business), db: Session = Depends(get_db)):
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

    return {
        "id": current_business.id,
        "name": current_business.name,
        "owner_name": current_business.owner_name,
        "email": current_business.email,
        "phone": current_business.phone,
        "address": current_business.address,
        "city": current_business.city,
        "country": current_business.country,
        "category": current_business.category,
        "description": current_business.description,
        "avatar": "",  # Default avatar for now
        "rating": rating,
        "reviewCount": review_count,
        "totalBookings": total_bookings,
        "monthlyRevenue": monthly_revenue,
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
    businesses = db.query(models.Business).all()
    return [{
        "id": b.id,
        "business_name": b.name,
        "name": b.name,
        "owner_name": b.owner_name,
        "email": b.email,
        "phone": b.phone,
        "address": b.address,
        "city": b.city,
        "country": b.country,
        "business_type": b.category or "barber",
        "category": b.category or "barber",
        "description": b.description or "Professional services",
        "latitude": 41.0082 + (b.id * 0.01),  # Temp: generate coords based on ID
        "longitude": 28.9784 + (b.id * 0.01),
        "avatar_url": None,
        "cover_photo_url": None,
        "workers_count": 5,
        "services_count": 8
    } for b in businesses]

@router.get("/list")
def get_businesses_list(db: Session = Depends(get_db)):
    businesses = db.query(models.Business).all()
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
# Get Business Details by ID
# ------------------------------
@router.get("/{business_id}")
def get_business_by_id(business_id: int, db: Session = Depends(get_db)):
    business = db.query(models.Business).filter(models.Business.id == business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    return {
        "id": business.id,
        "business_name": business.name,
        "owner_name": business.owner_name,
        "email": business.email,
        "phone": business.phone,
        "address": business.address,
        "city": business.city,
        "country": business.country,
        "description": business.description,
        "avatar": None,
        "cover_photo": None,
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

    # Get all barbers (users where is_barber=True)
    # For now, we'll return all barbers as workers for this business
    # TODO: Add a relationship between Business and Workers in the future
    workers = db.query(models.User).filter(models.User.is_barber == True).all()

    return [{
        "id": w.id,
        "name": f"{w.first_name} {w.last_name}".strip() or w.email.split('@')[0],
        "email": w.email,
        "phone": w.phone_number,
        "avatar": w.avatar_url,
        "rating": w.rating,
        "bio": w.barber_bio,
        "business_id": business_id
    } for w in workers]


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
# Get Nearby Businesses (GPS-based)
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
                "country": business.country,
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
# Geocode Address Endpoint (for manual address lookup)
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
        raise HTTPException(status_code=404, detail="Could not geocode address")
