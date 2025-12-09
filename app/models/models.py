from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, JSON, ForeignKey, Time, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from pydantic import BaseModel
from typing import Optional
from datetime import date, time

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)  # unique eklendi
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, index=True)
    last_name = Column(String, index=True)
    phone_number = Column(String, unique=True, nullable=True)
    birth_date = Column(Date, nullable=True)  # DateTime yerine Date
    address = Column(Text, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    loyalty_points = Column(Integer, default=0)
    membership_tier = Column(String, default="Bronze")
    rating = Column(Float, default=0.0)
    notification_settings = Column(JSON, default={})
    avatar_url = Column(String, nullable=True)
    is_barber = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    
    # Barber-specific fields - EKLENDİ
    barber_bio = Column(Text, nullable=True)
    barber_shop_name = Column(String, nullable=True)
    barber_shop_address = Column(Text, nullable=True)
    
    # Full name property - EKLENDİ
    # @property
    # def full_name(self):
    #     if self.first_name and self.last_name:
    #         return f"{self.first_name} {self.last_name}"
    #     elif self.first_name:
    #         return self.first_name
    #     elif self.last_name:
    #         return self.last_name
    #     else:
    #         return ""

    # İlişkiler
    working_hours = relationship("WorkingHours", back_populates="barber")
    services = relationship("Service", back_populates="barber")
    barber_services = relationship("BarberService", back_populates="barber")
    bookings_as_customer = relationship("Booking", foreign_keys="[Booking.user_id]", back_populates="user")
    bookings_as_barber = relationship("Booking", foreign_keys="[Booking.barber_id]", back_populates="barber")
    favorite_barbers = relationship("FavoriteBarber", foreign_keys="[FavoriteBarber.user_id]", back_populates="user")
    favorited_by = relationship("FavoriteBarber", foreign_keys="[FavoriteBarber.barber_id]", back_populates="barber")
    worker_businesses = relationship("BusinessWorker", back_populates="worker")

class WorkingHours(Base):
    __tablename__ = "working_hours"
    id = Column(Integer, primary_key=True, index=True)
    barber_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_working = Column(Boolean, default=True)  # EKLENDİ - schema ile uyumlu olması için

    barber = relationship("User", back_populates="working_hours")

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    barber_id = Column(Integer, ForeignKey("users.id"))
    service_id = Column(Integer, ForeignKey("services.id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String, default="pending")

    customer_email = Column(String, nullable=False)
    customer_name = Column(String, nullable=False)
    customer_phone = Column(String, nullable=True)

    # Yeni eklenen alan
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    barber = relationship("User", foreign_keys=[barber_id])
    service = relationship("Service")


class FavoriteBarber(Base):
    __tablename__ = "favorite_barbers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    barber_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Made nullable for service-only favorites
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)  # Added for service favorites
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="favorite_barbers")
    barber = relationship("User", foreign_keys=[barber_id], back_populates="favorited_by")
    service = relationship("Service")  # Added service relationship

class BusinessWorker(Base):
    """Many-to-Many relationship between Business and Workers (Users)"""
    __tablename__ = "business_workers"
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    worker_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, default="worker")  # owner, manager, worker
    status = Column(String, default="active")  # active, invited, suspended
    invited_at = Column(DateTime, server_default=func.now())
    joined_at = Column(DateTime, nullable=True)

    # Working hours for this worker at this business
    work_start_time = Column(Time, default=time(9, 0))  # Default 09:00
    work_end_time = Column(Time, default=time(21, 0))   # Default 21:00 (9 PM)

    business = relationship("Business", back_populates="business_workers")
    worker = relationship("User", back_populates="worker_businesses")

class Business(Base):
    __tablename__ = "businesses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    owner_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    phone = Column(String)
    address = Column(String)
    city = Column(String)
    country = Column(String, nullable=True)
    category = Column(String, nullable=True)
    description = Column(String)
    latitude = Column(Float, nullable=True, index=True)  # GPS coordinates
    longitude = Column(Float, nullable=True, index=True)  # GPS coordinates
    avatar_url = Column(String, nullable=True)  # Business profile photo
    cover_photo_url = Column(String, nullable=True)  # Business cover photo
    gallery_photos = Column(Text, nullable=True)  # JSON array of gallery photo URLs
    working_hours_json = Column(Text, nullable=True)  # JSON string for salon working hours

    services = relationship("Service", back_populates="business")
    business_workers = relationship("BusinessWorker", back_populates="business")

class Service(Base):
    __tablename__ = "services"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    duration = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True)
    barber_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    business = relationship("Business", back_populates="services")
    barber = relationship("User", back_populates="services")
    barber_services = relationship("BarberService", back_populates="service")

class BarberService(Base):
    __tablename__ = "barber_services"
    id = Column(Integer, primary_key=True, index=True)
    barber_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)

    barber = relationship("User", back_populates="barber_services")
    service = relationship("Service", back_populates="barber_services")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    status = Column(String, default="pending")  # pending, completed, failed, refunded
    payment_method = Column(String, default="2checkout")  # 2checkout, stripe, etc
    transaction_id = Column(String, nullable=True)  # 2Checkout order/sale ID
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    booking = relationship("Booking")
    user = relationship("User")

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True)
    worker_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    rating = Column(Float, nullable=False)  # Changed to Float to match DB
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    business = relationship("Business")
    user = relationship("User", foreign_keys=[user_id])
    worker = relationship("User", foreign_keys=[worker_id])
    booking = relationship("Booking")


# ==================== ANALYTICS MODELS ====================

class VisitorSession(Base):
    """Track unique visitors and their sessions"""
    __tablename__ = "visitor_sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)  # UUID for session
    visitor_id = Column(String, index=True, nullable=False)  # Fingerprint/cookie ID for returning visitor detection
    ip_address = Column(String, nullable=True)
    country = Column(String, nullable=True)
    city = Column(String, nullable=True)
    user_agent = Column(Text, nullable=True)
    device_type = Column(String, nullable=True)  # mobile, tablet, desktop
    browser = Column(String, nullable=True)
    os = Column(String, nullable=True)
    referrer = Column(String, nullable=True)  # Where they came from
    landing_page = Column(String, nullable=True)  # First page they visited
    is_returning = Column(Boolean, default=False)  # Returning visitor?
    created_at = Column(DateTime, server_default=func.now())
    last_activity = Column(DateTime, server_default=func.now())


class PageView(Base):
    """Track individual page views"""
    __tablename__ = "page_views"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("visitor_sessions.session_id"), nullable=False, index=True)
    page_path = Column(String, nullable=False, index=True)  # /home, /business/123, etc
    page_title = Column(String, nullable=True)
    time_on_page = Column(Integer, nullable=True)  # Seconds spent on page
    created_at = Column(DateTime, server_default=func.now())


class ClickEvent(Base):
    """Track clicks on important elements"""
    __tablename__ = "click_events"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, ForeignKey("visitor_sessions.session_id"), nullable=False, index=True)
    element_id = Column(String, nullable=True)  # Button ID or element identifier
    element_text = Column(String, nullable=True)  # "Book Now", "Try Business", etc
    element_type = Column(String, nullable=True)  # button, link, card
    page_path = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class AdminUser(Base):
    """Admin users for the admin panel"""
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superadmin = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    last_login = Column(DateTime, nullable=True)