from datetime import datetime, date
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.crud.crud_booking import (
    get_bookings,
    get_customer_bookings,
    create_booking,
    cancel_booking,
    get_available_slots
)
from app.models.models import User, Booking as BookingModel, Service
from app.models.schemas import BookingSchema, BookingCreate, AvailableSlots

router = APIRouter(tags=["Bookings"])


@router.post("/", response_model=BookingSchema, status_code=status.HTTP_201_CREATED)
async def create_new_booking(
    booking: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # ✅ Barber kontrolü
    print(f"🔍 Step 1: Checking barber {booking.barber_id}")
    barber = db.query(User).filter(User.id == booking.barber_id, User.is_barber == True).first()
    if not barber:
        print(f"❌ Barber {booking.barber_id} not found")
        raise HTTPException(status_code=404, detail="Barber not found")
    print(f"✅ Barber found: {barber.id}")

    # ✅ Service kontrolü (barber'a ait mi?)
    print(f"🔍 Step 2: Checking service {booking.service_id} for barber {booking.barber_id}")
    service = db.query(Service).filter(
        Service.id == booking.service_id,
        Service.barber_id == booking.barber_id
    ).first()
    if not service:
        print(f"❌ Service {booking.service_id} not found for barber {booking.barber_id}")
        raise HTTPException(status_code=404, detail="Service not found for this barber")
    print(f"✅ Service found: {service.id}")

    # ✅ Tarih kontrolü (aware datetime)
    start_time = booking.start_time
    print(f"📅 Booking request - Barber: {booking.barber_id}, Service: {booking.service_id}, Start: {start_time}")

    # If start_time has no timezone, treat it as a naive datetime (local time)
    # and don't add timezone for comparison
    if start_time.tzinfo is None:
        print(f"🔍 Step 3: start_time is naive (no timezone), treating as local time")
        now = datetime.now()  # Get naive datetime for comparison
    else:
        print(f"🔍 Step 3: start_time has timezone: {start_time.tzinfo}")
        now = datetime.now(tz=start_time.tzinfo)

    print(f"🔍 Step 4: Comparing start_time {start_time} with now {now}")
    if start_time < now:
        print(f"❌ Booking time is in the past!")
        raise HTTPException(status_code=400, detail="Booking time must be in the future")
    print(f"✅ Booking time is valid")

    # Booking verilerini oluştur
    print(f"🔍 Step 5: Building booking data")
    booking_data = booking.dict()
    # Build customer name from first_name and last_name
    customer_name = "Anonymous"
    if current_user.first_name or current_user.last_name:
        customer_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()

    booking_data.update({
        "user_id": current_user.id,
        "barber_id": booking.barber_id,
        "service_id": booking.service_id,
        "customer_email": current_user.email,
        "customer_name": customer_name,
        "customer_phone": current_user.phone_number or booking.customer_phone,
    })
    print(f"✅ Booking data prepared")

    # ✅ Booking oluşturma
    try:
        print(f"📝 Creating booking with data: {booking_data}")
        new_booking: BookingModel = create_booking(db=db, booking_data=booking_data)
        return BookingSchema.from_orm(new_booking)  # SQLAlchemy objesini Pydantic'e çevir
    except ValueError as e:
        print(f"❌ Booking validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Booking creation error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/customer", response_model=List[BookingSchema])
async def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    bookings = get_customer_bookings(db=db, customer_email=current_user.email)
    return [BookingSchema.from_orm(b) for b in bookings]


@router.get("/available-dates")
async def get_available_dates(
    barber_id: int,
    service_id: int,
    db: Session = Depends(get_db)
):
    """Get available dates for the next 30 days"""
    from datetime import timedelta

    available_dates = []
    today = date.today()

    # Generate next 30 days
    for i in range(30):
        current_date = today + timedelta(days=i)
        available_dates.append(current_date.isoformat())

    return available_dates


@router.get("/available-times")
async def get_available_times(
    barber_id: int,
    service_id: int,
    date: str,
    db: Session = Depends(get_db)
):
    """Get available time slots for a specific date based on worker's working hours"""
    from datetime import datetime, timedelta
    from app.models.models import WorkingHours

    # Parse date
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Get service duration
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Get day of week (0=Monday, 6=Sunday)
    day_of_week = target_date.weekday()
    print(f"📅 Target date: {target_date}, Day of week: {day_of_week}")

    # Get worker's working hours from working_hours table for this specific day
    worker_hours = db.query(WorkingHours).filter(
        WorkingHours.barber_id == barber_id,
        WorkingHours.day_of_week == day_of_week
    ).first()

    # Check if worker is working on this day
    if not worker_hours or not worker_hours.is_working:
        print(f"❌ Worker {barber_id} is not working on day {day_of_week}")
        return []  # Worker doesn't work on this day

    # Parse worker's start and end times (they are time objects, not strings)
    working_start = worker_hours.start_time.hour
    working_end = worker_hours.end_time.hour

    print(f"🕐 Worker {barber_id} working hours on day {day_of_week}: {worker_hours.start_time} - {worker_hours.end_time}")

    # Get existing bookings for this barber on this date
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())

    existing_bookings = db.query(BookingModel).filter(
        BookingModel.barber_id == barber_id,
        BookingModel.start_time >= start_of_day,
        BookingModel.start_time <= end_of_day,
        BookingModel.status != "cancelled"
    ).all()

    print(f"📋 Found {len(existing_bookings)} existing bookings")

    # Generate time slots based on worker's working hours (every 30 minutes)
    available_times = []

    # Get current time for comparison
    now = datetime.now()

    for hour in range(working_start, working_end + 1):
        for minute in [0, 30]:
            # Don't add slots after end hour
            if hour == working_end and minute > 0:
                break

            time_slot = f"{hour:02d}:{minute:02d}"
            slot_datetime = datetime.combine(target_date, datetime.strptime(time_slot, "%H:%M").time())

            # Skip if this time slot is in the past
            if slot_datetime < now:
                continue

            # Check if this slot conflicts with existing bookings
            is_available = True
            for booking in existing_bookings:
                booking_end = booking.start_time + timedelta(minutes=service.duration)
                slot_end = slot_datetime + timedelta(minutes=service.duration)

                # Check for overlap
                if (slot_datetime < booking_end and slot_end > booking.start_time):
                    is_available = False
                    break

            if is_available:
                available_times.append(time_slot)

    print(f"✅ Returning {len(available_times)} available time slots")
    return available_times


@router.get("/available-slots")
async def get_available_time_slots(
    barber_id: int,
    service_id: int,
    date: date,
    db: Session = Depends(get_db)
):
    slots = get_available_slots(db=db, barber_id=barber_id, service_id=service_id, selected_date=date)
    if not slots:
        raise HTTPException(status_code=404, detail="No available slots found")
    return slots


@router.post("/{booking_id}/cancel", response_model=BookingSchema)
async def cancel_my_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    booking = db.query(BookingModel).filter(
        BookingModel.id == booking_id,
        BookingModel.customer_email == current_user.email
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    cancelled_booking = cancel_booking(db=db, booking_id=booking_id)
    if not cancelled_booking:
        raise HTTPException(status_code=400, detail="Could not cancel booking")

    return BookingSchema.from_orm(cancelled_booking)

@router.get("/barber/{barber_id}", response_model=List[BookingSchema])
async def get_bookings_by_barber(
    barber_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Sadece berber kendi randevularını görebilir
    if not current_user.is_barber or current_user.id != barber_id:
        raise HTTPException(status_code=403, detail="Not authorized to view these bookings")

    bookings = db.query(BookingModel).filter(BookingModel.barber_id == barber_id).all()
    return [BookingSchema.from_orm(b) for b in bookings]


@router.get("/barber-appointments/{barber_id}")
async def get_barber_appointments(
    barber_id: int,
    db: Session = Depends(get_db)
):
    """Get appointments for a specific barber (public endpoint)"""
    bookings = db.query(BookingModel).filter(BookingModel.barber_id == barber_id).all()

    return [
        {
            "id": b.id,
            "customer_name": b.customer_name,
            "customer_phone": b.customer_phone,
            "service": {
                "name": b.service.name if b.service else "Unknown Service",
                "price": b.service.price if b.service else 0,
                "duration": b.service.duration if b.service else 0
            },
            "start_time": b.start_time.isoformat() if b.start_time else None,
            "status": b.status
        }
        for b in bookings
    ]

@router.get("/worker/{worker_id}/date/{date}")
async def get_worker_bookings_by_date(
    worker_id: int,
    date: str,
    db: Session = Depends(get_db)
):
    """Get bookings for a specific worker on a specific date"""
    from datetime import datetime, timedelta

    # Parse the date string (YYYY-MM-DD)
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Get start and end of day
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())

    # Query bookings for this worker on this date
    bookings = db.query(BookingModel).filter(
        BookingModel.barber_id == worker_id,
        BookingModel.start_time >= start_of_day,
        BookingModel.start_time <= end_of_day,
        BookingModel.status != "cancelled"
    ).all()

    return [
        {
            "id": b.id,
            "start_time": b.start_time.isoformat() if b.start_time else None,
            "end_time": b.end_time.isoformat() if b.end_time else None,
            "status": b.status
        }
        for b in bookings
    ]