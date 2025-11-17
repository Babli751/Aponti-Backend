# app/routers/services.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.models import Service, Booking
from app.models.schemas import Service as ServiceSchema

router = APIRouter(tags=["Services"])

@router.get("/")
def get_services(business_id: int = None, db: Session = Depends(get_db)):
    """Get all services, optionally filtered by business_id"""
    query = db.query(Service)
    if business_id is not None:
        query = query.filter(Service.business_id == business_id)

    services = query.all()

    # Convert to dictionaries
    result = []
    for service in services:
        result.append({
            "id": service.id,
            "name": service.name,
            "description": service.description,
            "price": service.price,
            "duration": service.duration,
            "business_id": service.business_id,
            "barber_id": service.barber_id
        })

    return result

@router.delete("/{service_id}")
def delete_service(service_id: int, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Delete related bookings first to avoid foreign key constraint
    bookings = db.query(Booking).filter(Booking.service_id == service_id).all()
    for booking in bookings:
        db.delete(booking)

    db.delete(service)
    db.commit()
    return {"message": "Service deleted successfully"}
