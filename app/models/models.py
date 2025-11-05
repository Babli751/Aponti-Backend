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

    user = relationship("User", foreign_keys=[user_id])
    barber = relationship("User", foreign_keys=[barber_id])
    service = relationship("Service")


class FavoriteBarber(Base):
    __tablename__ = "favorite_barbers"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    barber_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="favorite_barbers")
    barber = relationship("User", foreign_keys=[barber_id], back_populates="favorited_by")

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