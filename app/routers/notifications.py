from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from app.core.security import get_current_user, get_current_business
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, func

router = APIRouter(tags=["notifications"])


# Notification Model
class Notification(models.Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String, nullable=False)  # booking_confirmation, reminder, status_change, promotion
    related_booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


# Schemas
class NotificationCreate(BaseModel):
    user_id: Optional[int] = None
    business_id: Optional[int] = None
    title: str
    message: str
    type: str
    related_booking_id: Optional[int] = None


class NotificationResponse(BaseModel):
    id: int
    title: str
    message: str
    type: str
    is_read: bool
    created_at: datetime
    related_booking_id: Optional[int] = None


# ------------------------------
# Create Notification (Internal)
# ------------------------------
def create_notification(db: Session, notification_data: NotificationCreate):
    """Internal function to create notification"""
    notification = Notification(**notification_data.dict())
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification


# ------------------------------
# Get User Notifications
# ------------------------------
@router.get("/user", response_model=List[NotificationResponse])
def get_user_notifications(
    unread_only: bool = False,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all notifications for current user"""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)

    if unread_only:
        query = query.filter(Notification.is_read == False)

    notifications = query.order_by(Notification.created_at.desc()).limit(50).all()

    return [
        NotificationResponse(
            id=n.id,
            title=n.title,
            message=n.message,
            type=n.type,
            is_read=n.is_read,
            created_at=n.created_at,
            related_booking_id=n.related_booking_id
        )
        for n in notifications
    ]


# ------------------------------
# Get Business Notifications
# ------------------------------
@router.get("/business", response_model=List[NotificationResponse])
def get_business_notifications(
    unread_only: bool = False,
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Get all notifications for current business"""
    query = db.query(Notification).filter(Notification.business_id == current_business.id)

    if unread_only:
        query = query.filter(Notification.is_read == False)

    notifications = query.order_by(Notification.created_at.desc()).limit(50).all()

    return [
        NotificationResponse(
            id=n.id,
            title=n.title,
            message=n.message,
            type=n.type,
            is_read=n.is_read,
            created_at=n.created_at,
            related_booking_id=n.related_booking_id
        )
        for n in notifications
    ]


# ------------------------------
# Mark Notification as Read
# ------------------------------
@router.put("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.is_read = True
    db.commit()

    return {"success": True, "message": "Notification marked as read"}


# ------------------------------
# Mark All as Read
# ------------------------------
@router.put("/mark-all-read")
def mark_all_notifications_read(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all notifications as read"""
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})

    db.commit()

    return {"success": True, "message": "All notifications marked as read"}


# ------------------------------
# Delete Notification
# ------------------------------
@router.delete("/{notification_id}")
def delete_notification(
    notification_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a notification"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")

    db.delete(notification)
    db.commit()

    return {"success": True, "message": "Notification deleted"}


# ------------------------------
# Get Unread Count
# ------------------------------
@router.get("/count/unread")
def get_unread_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get count of unread notifications"""
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).count()

    return {"count": count}


# ------------------------------
# Notification Triggers (Call these from other endpoints)
# ------------------------------
def send_booking_confirmation(db: Session, booking_id: int):
    """Send booking confirmation notification"""
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        return

    # To customer
    create_notification(db, NotificationCreate(
        user_id=booking.user_id,
        title="Booking Confirmed!",
        message=f"Your appointment for {booking.service.name} has been confirmed for {booking.start_time.strftime('%B %d, %Y at %I:%M %p')}",
        type="booking_confirmation",
        related_booking_id=booking_id
    ))

    # To business
    service = booking.service
    if service and service.business_id:
        create_notification(db, NotificationCreate(
            business_id=service.business_id,
            title="New Booking",
            message=f"New booking from {booking.customer_name} for {service.name}",
            type="booking_confirmation",
            related_booking_id=booking_id
        ))


def send_booking_reminder(db: Session, booking_id: int):
    """Send appointment reminder (call this from a scheduled task)"""
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        return

    hours_until = (booking.start_time - datetime.now()).total_seconds() / 3600

    create_notification(db, NotificationCreate(
        user_id=booking.user_id,
        title="Appointment Reminder",
        message=f"You have an appointment in {int(hours_until)} hours for {booking.service.name}",
        type="reminder",
        related_booking_id=booking_id
    ))


def send_status_change_notification(db: Session, booking_id: int, new_status: str):
    """Send notification when booking status changes"""
    booking = db.query(models.Booking).filter(models.Booking.id == booking_id).first()
    if not booking:
        return

    status_messages = {
        "confirmed": "Your appointment has been confirmed",
        "cancelled": "Your appointment has been cancelled",
        "completed": "Your appointment is complete. Please leave a review!",
        "rejected": "Your appointment request was not approved"
    }

    create_notification(db, NotificationCreate(
        user_id=booking.user_id,
        title="Booking Status Update",
        message=status_messages.get(new_status, f"Your booking status changed to {new_status}"),
        type="status_change",
        related_booking_id=booking_id
    ))
