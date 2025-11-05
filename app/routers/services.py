# app/routers/services.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.models import Service, Booking
from app.models.schemas import Service as ServiceSchema

router = APIRouter(tags=["Services"])

@router.get("/test", response_model=dict)
def test_endpoint():
    print("TEST ENDPOINT CALLED")
    return {"message": "test successful"}

@router.get("/services/")
def get_services(business_id: int = None, db: Session = Depends(get_db)):
    try:
        # Debug: write to file
        with open('/tmp/debug_services.log', 'w') as f:
            f.write(f"Starting get_services, business_id={business_id}\n")
            f.write(f"Database session: {db}\n")
            f.write(f"Database URL: {db.bind.url}\n")

        query = db.query(Service)
        if business_id is not None:
            query = query.filter(Service.business_id == business_id)

        services = query.all()

        with open('/tmp/debug_services.log', 'a') as f:
            f.write(f"Found {len(services)} services\n")
            for i, service in enumerate(services):
                f.write(f"Service {i}: id={service.id}, name={service.name}\n")

        # Convert to dictionaries manually
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

        with open('/tmp/debug_services.log', 'a') as f:
            f.write(f"Returning {len(result)} services\n")

        return result
    except Exception as e:
        with open('/tmp/debug_services.log', 'a') as f:
            f.write(f"ERROR: {e}\n")
            import traceback
            f.write(traceback.format_exc())
        return []

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
