from sqlalchemy.orm import Session
from app.models.models import User as UserModel, Booking, Service, WorkingHours  # Modeli import edin
from app.models.schemas import UserCreate, UserUpdate, NotificationSettings  # Sadece şemaları import edin
from app.core import security

def get_user(db: Session, user_id: int):
    return db.query(UserModel).filter(UserModel.id == user_id).first()

def get_user_by_email(db: Session, email: str):
    return db.query(UserModel).filter(UserModel.email == email).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(UserModel).offset(skip).limit(limit).all()

def create_user(db: Session, user: UserCreate):
    hashed_password = security.get_password_hash(user.password)
    db_user = UserModel(
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        phone_number=user.phone_number,
        hashed_password=hashed_password,
        is_active=True,
        is_barber=user.is_barber   # 👈 burayı ekle!
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_barbers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(UserModel).filter(UserModel.is_barber == True).offset(skip).limit(limit).all()

# app/crud/crud_user.py - get_user_stats fonksiyonunu düzeltin
def get_user_stats(db: Session, user_id: int, user_email: str):
    # Müşteri istatistikleri (customer_email kullanarak)
    total_appointments = db.query(Booking).filter(
        Booking.customer_email == user_email  # customer_id yerine customer_email
    ).count()
    
    # Berber istatistikleri
    upcoming_appointments = db.query(Booking).filter(
        Booking.customer_email == user_email,  # customer_id yerine customer_email
        Booking.status == "confirmed"
    ).count()
    
    # Favori berber sayısı (geçici olarak 0)
    favorite_barbers = 0

    return {
        "total_appointments": total_appointments,
        "favorite_barbers": favorite_barbers,
        "upcoming_appointments": upcoming_appointments
    }

def update_user(db: Session, user_id: int, user_update: UserUpdate):
    db_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not db_user:
        return None
    
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_user, field, value)
    
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_notifications(db: Session, user_id: int, settings: NotificationSettings):
    db_user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not db_user:
        return None
    
    # Convert settings to JSON or store as separate fields
    db_user.notification_settings = settings.dict()
    db.commit()
    db.refresh(db_user)
    return settings

def get_dashboard_stats(db: Session):
    total_users = db.query(UserModel).count()
    total_bookings = db.query(Booking).count()
    total_barbers = db.query(UserModel).filter(UserModel.is_barber == True).count()
    
    upcoming_bookings = db.query(Booking).filter(Booking.status == "confirmed").count()
    
    return {
        "total_users": total_users,
        "total_barbers": total_barbers,
        "total_bookings": total_bookings,
        "upcoming_bookings": upcoming_bookings
    }    