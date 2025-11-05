from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from datetime import datetime, time, timedelta, date as dt_date
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(tags=["slots"])


class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    available: bool
    worker_id: int
    worker_name: str


class AvailableSlotsResponse(BaseModel):
    date: str
    worker_id: int
    worker_name: str
    service_id: int
    service_name: str
    service_duration: int
    slots: List[TimeSlot]


def time_to_minutes(t: time) -> int:
    """Convert time to minutes since midnight"""
    return t.hour * 60 + t.minute


def minutes_to_time(minutes: int) -> time:
    """Convert minutes since midnight to time"""
    hours = minutes // 60
    mins = minutes % 60
    return time(hour=hours, minute=mins)


def generate_time_slots(
    start_time: time,
    end_time: time,
    service_duration: int,
    slot_interval: int = 15  # Minimum gap between slots
) -> List[time]:
    """Generate possible time slots for a given time range"""
    slots = []

    current_minutes = time_to_minutes(start_time)
    end_minutes = time_to_minutes(end_time)

    while current_minutes + service_duration <= end_minutes:
        slots.append(minutes_to_time(current_minutes))
        current_minutes += slot_interval

    return slots


def is_slot_available(
    worker_id: int,
    slot_start: datetime,
    slot_end: datetime,
    db: Session
) -> bool:
    """Check if a time slot is available (no overlapping bookings)"""

    # Check for overlapping bookings
    overlapping_bookings = db.query(models.Booking).filter(
        models.Booking.barber_id == worker_id,
        models.Booking.status != "cancelled",
        models.Booking.status != "rejected",
        # Check for overlap: (new_start < existing_end) AND (new_end > existing_start)
        models.Booking.start_time < slot_end,
        models.Booking.end_time > slot_start
    ).first()

    return overlapping_bookings is None


# ------------------------------
# Get Available Slots for Worker & Service
# ------------------------------
@router.get("/available", response_model=AvailableSlotsResponse)
def get_available_slots(
    worker_id: int = Query(..., description="Worker/Barber ID"),
    service_id: int = Query(..., description="Service ID"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    db: Session = Depends(get_db)
):
    """Get all available time slots for a worker providing a specific service on a given date"""

    # Parse date
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Verify worker exists
    worker = db.query(models.User).filter(
        models.User.id == worker_id,
        models.User.is_barber == True
    ).first()

    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Verify service exists
    service = db.query(models.Service).filter(models.Service.id == service_id).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Get worker's working hours for this day of week (0=Monday, 6=Sunday)
    day_of_week = target_date.weekday()

    working_hours = db.query(models.WorkingHours).filter(
        models.WorkingHours.barber_id == worker_id,
        models.WorkingHours.day_of_week == day_of_week,
        models.WorkingHours.is_working == True
    ).first()

    if not working_hours:
        # Worker doesn't work on this day
        return AvailableSlotsResponse(
            date=date,
            worker_id=worker_id,
            worker_name=f"{worker.first_name} {worker.last_name}",
            service_id=service_id,
            service_name=service.name,
            service_duration=service.duration,
            slots=[]
        )

    # Generate possible time slots
    possible_times = generate_time_slots(
        working_hours.start_time,
        working_hours.end_time,
        service.duration
    )

    # Check availability for each slot
    slots = []
    for slot_time in possible_times:
        slot_start = datetime.combine(target_date, slot_time)
        slot_end = slot_start + timedelta(minutes=service.duration)

        available = is_slot_available(worker_id, slot_start, slot_end, db)

        slots.append(TimeSlot(
            start_time=slot_start,
            end_time=slot_end,
            available=available,
            worker_id=worker_id,
            worker_name=f"{worker.first_name} {worker.last_name}"
        ))

    return AvailableSlotsResponse(
        date=date,
        worker_id=worker_id,
        worker_name=f"{worker.first_name} {worker.last_name}",
        service_id=service_id,
        service_name=service.name,
        service_duration=service.duration,
        slots=slots
    )


# ------------------------------
# Get Available Workers for a Service & Time
# ------------------------------
class WorkerAvailability(BaseModel):
    worker_id: int
    worker_name: str
    avatar_url: Optional[str]
    rating: float
    available: bool
    next_available_slot: Optional[datetime] = None


@router.get("/workers-available", response_model=List[WorkerAvailability])
def get_available_workers(
    business_id: int = Query(..., description="Business ID"),
    service_id: int = Query(..., description="Service ID"),
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    time_str: str = Query(..., description="Time in HH:MM format"),
    db: Session = Depends(get_db)
):
    """Get all workers who can provide a service at a specific date/time"""

    # Parse date and time
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
        target_time = datetime.strptime(time_str, "%H:%M").time()
        target_datetime = datetime.combine(target_date, target_time)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time format")

    # Get service
    service = db.query(models.Service).filter(models.Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Get all workers for this business who can perform this service
    business_workers = db.query(models.BusinessWorker).filter(
        models.BusinessWorker.business_id == business_id,
        models.BusinessWorker.status == "active"
    ).all()

    worker_ids = [bw.worker_id for bw in business_workers]

    # Get workers who can perform this service
    barber_services = db.query(models.BarberService).filter(
        models.BarberService.service_id == service_id,
        models.BarberService.barber_id.in_(worker_ids)
    ).all()

    service_worker_ids = [bs.barber_id for bs in barber_services]

    if not service_worker_ids:
        return []

    # Check availability for each worker
    workers = db.query(models.User).filter(models.User.id.in_(service_worker_ids)).all()

    worker_availability = []
    for worker in workers:
        slot_end = target_datetime + timedelta(minutes=service.duration)
        available = is_slot_available(worker.id, target_datetime, slot_end, db)

        # If not available, find next available slot (optional enhancement)
        next_slot = None
        if not available:
            # TODO: Implement next available slot finder
            pass

        worker_availability.append(WorkerAvailability(
            worker_id=worker.id,
            worker_name=f"{worker.first_name} {worker.last_name}",
            avatar_url=worker.avatar_url,
            rating=worker.rating or 0.0,
            available=available,
            next_available_slot=next_slot
        ))

    return worker_availability


# ------------------------------
# Validate Booking (Check for conflicts)
# ------------------------------
class BookingValidation(BaseModel):
    worker_id: int
    service_id: int
    start_time: datetime


@router.post("/validate-booking")
def validate_booking(
    validation: BookingValidation,
    db: Session = Depends(get_db)
):
    """Validate if a booking can be made (check for conflicts)"""

    # Get service
    service = db.query(models.Service).filter(models.Service.id == validation.service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Calculate end time
    end_time = validation.start_time + timedelta(minutes=service.duration)

    # Check availability
    available = is_slot_available(validation.worker_id, validation.start_time, end_time, db)

    if not available:
        return {
            "valid": False,
            "message": "This time slot is not available",
            "suggestion": "Please choose another time"
        }

    # Check working hours
    day_of_week = validation.start_time.weekday()
    working_hours = db.query(models.WorkingHours).filter(
        models.WorkingHours.barber_id == validation.worker_id,
        models.WorkingHours.day_of_week == day_of_week,
        models.WorkingHours.is_working == True
    ).first()

    if not working_hours:
        return {
            "valid": False,
            "message": "Worker doesn't work on this day",
            "suggestion": "Please choose another day"
        }

    # Check if time is within working hours
    booking_time = validation.start_time.time()
    if booking_time < working_hours.start_time or booking_time >= working_hours.end_time:
        return {
            "valid": False,
            "message": "Time is outside working hours",
            "suggestion": f"Working hours: {working_hours.start_time} - {working_hours.end_time}"
        }

    return {
        "valid": True,
        "message": "Booking slot is available",
        "start_time": validation.start_time.isoformat(),
        "end_time": end_time.isoformat()
    }
