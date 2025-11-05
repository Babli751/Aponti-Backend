from app.models.schemas import BookingSchema
from app.models.models import Booking as BookingModel, User
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.crud.crud_barber import (
    get_barber_services,
    create_barber_service,
    delete_barber_service,
    get_barber_working_hours,
    update_barber_working_hours,
    update_barber_profile
)
from app.models.schemas import (
    Service,  # BU EKLENDİ
    ServiceCreate,  # BU EKLENDİ
    WorkingHours,
    WorkingHoursCreate,
    Barber
)
from app.models.models import User
router = APIRouter()

# --------------------------
# Tüm berberleri getir - DÜZELTİLMİŞ VERSİYON
# --------------------------
@router.get("/", response_model=List[Barber])
def read_all_barbers(db: Session = Depends(get_db)):
    try:
        barbers = db.query(User).filter(User.is_barber == True).all()
        
        barber_list = []
        for barber in barbers:
            # full_name'i first_name ve last_name'den oluştur
            full_name = f"{barber.first_name or ''} {barber.last_name or ''}".strip()
            if not full_name:
                full_name = barber.email  # Fallback olarak email kullan
                
            barber_data = {
                "id": barber.id,
                "email": barber.email,
                "full_name": full_name,
                "phone_number": barber.phone_number,
                "is_active": barber.is_active,
                "is_barber": barber.is_barber,
                "created_at": barber.created_at,
                "barber_bio": getattr(barber, 'barber_bio', None),
                "barber_shop_name": getattr(barber, 'barber_shop_name', None),
                "barber_shop_address": getattr(barber, 'barber_shop_address', None)
            }
            barber_list.append(Barber(**barber_data))
        
        return barber_list
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving barbers: {str(e)}")

# --------------------------
# Berberin servislerini getir
# --------------------------
@router.get("/{barber_id}/services", response_model=List[Service])
def read_barber_services(barber_id: int, db: Session = Depends(get_db)):
    services = get_barber_services(db, barber_id=barber_id)
    return [
        Service(
            id=service.id,
            name=service.name,
            description=service.description,
            duration=service.duration,
            price=service.price,
            barber_id=service.barber_id,
            business_id=service.business_id
        )
        for service in services
    ]

# --------------------------
# Berber servisi ekle
# --------------------------
@router.post("/{barber_id}/services", response_model=Service)
def add_barber_service(
    barber_id: int,
    service: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.id != barber_id or not current_user.is_barber:
        raise HTTPException(status_code=403, detail="Only the barber can add services")

    new_service = create_barber_service(db=db, service=service, barber_id=barber_id)
    return Service(
        id=new_service.id,
        name=new_service.name,
        description=new_service.description,
        duration=new_service.duration,
        price=new_service.price,
        barber_id=new_service.barber_id,
        business_id=new_service.business_id
    )

# --------------------------
# Berber servisi sil
# --------------------------
@router.delete("/{barber_id}/services/{service_id}")
def remove_barber_service(
    barber_id: int,
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.id != barber_id or not current_user.is_barber:
        raise HTTPException(status_code=403, detail="Only the barber can delete services")

    try:
        deleted_service = delete_barber_service(db=db, barber_id=barber_id, service_id=service_id)
        if not deleted_service:
            raise HTTPException(status_code=404, detail="Service not found")

        return {"message": "Service deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# --------------------------
# Berber çalışma saatlerini getir
# --------------------------
@router.get("/{barber_id}/working-hours", response_model=List[WorkingHours])
def read_barber_working_hours(barber_id: int, db: Session = Depends(get_db)):
    working_hours = get_barber_working_hours(db, barber_id=barber_id)
    return [
        WorkingHours(
            id=wh.id,
            day_of_week=wh.day_of_week,
            start_time=wh.start_time,
            end_time=wh.end_time,
            is_working=wh.is_working,
            barber_id=wh.barber_id
        )
        for wh in working_hours
    ]

# --------------------------
# Berber çalışma saatlerini güncelle
# --------------------------
@router.put("/{barber_id}/working-hours", response_model=List[WorkingHours])
def set_barber_working_hours(
    barber_id: int,
    working_hours: List[WorkingHoursCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.id != barber_id or not current_user.is_barber:
        raise HTTPException(status_code=403, detail="Only the barber can set working hours")
    
    updated_working_hours = update_barber_working_hours(db=db, barber_id=barber_id, working_hours=working_hours)
    return [
        WorkingHours(
            id=wh.id,
            day_of_week=wh.day_of_week,
            start_time=wh.start_time,
            end_time=wh.end_time,
            is_working=wh.is_working,
            barber_id=wh.barber_id
        )
        for wh in updated_working_hours
    ]

# --------------------------
# Berber profilini güncelle
# --------------------------
@router.put("/{barber_id}/profile")
def update_profile(
    barber_id: int,
    bio: str,
    shop_name: str,
    shop_address: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if current_user.id != barber_id or not current_user.is_barber:
        raise HTTPException(status_code=403, detail="Only the barber can update profile")
    
    updated_barber = update_barber_profile(
        db=db,
        barber_id=barber_id,
        bio=bio,
        shop_name=shop_name,
        shop_address=shop_address
    )
    return Barber(
        id=updated_barber.id,
        email=updated_barber.email,
        full_name=updated_barber.full_name,
        phone_number=updated_barber.phone_number,
        is_active=updated_barber.is_active,
        is_barber=updated_barber.is_barber,
        created_at=updated_barber.created_at,
        barber_bio=updated_barber.barber_bio,
        barber_shop_name=updated_barber.barber_shop_name,
        barber_shop_address=updated_barber.barber_shop_address
    )

@router.get("/{barber_id}", response_model=Barber)
def read_one_barber(barber_id: int, db: Session = Depends(get_db)):
    barber = db.query(User).filter(User.id == barber_id, User.is_barber == True).first()
    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    full_name = f"{barber.first_name or ''} {barber.last_name or ''}".strip()
    if not full_name:
        full_name = barber.email

    return Barber(
        id=barber.id,
        email=barber.email,
        full_name=full_name,
        phone_number=barber.phone_number,
        is_active=barber.is_active,
        is_barber=barber.is_barber,
        created_at=barber.created_at,
        barber_bio=getattr(barber, 'barber_bio', None),
        barber_shop_name=getattr(barber, 'barber_shop_name', None),
        barber_shop_address=getattr(barber, 'barber_shop_address', None)
    )

