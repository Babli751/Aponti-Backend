from datetime import datetime, time, date
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict


# -------------------- TOKEN --------------------
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


# -------------------- USER --------------------
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    is_barber: bool = False

class User(UserBase):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: bool
    is_barber: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------- BARBER --------------------
class BarberInfo(BaseModel):
    barber_bio: Optional[str] = None
    barber_shop_name: Optional[str] = None
    barber_shop_address: Optional[str] = None

class Barber(User):
    barber_bio: Optional[str] = None
    barber_shop_name: Optional[str] = None
    barber_shop_address: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


# -------------------- SERVICE --------------------
class ServiceBase(BaseModel):
    name: str
    description: Optional[str] = None
    duration: int
    price: float

class ServiceCreate(ServiceBase):
    pass

class Service(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    duration: int
    business_id: Optional[int] = None
    barber_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------- WORKING HOURS --------------------
class WorkingHoursBase(BaseModel):
    day_of_week: int
    start_time: time
    end_time: time
    is_working: bool = True

class WorkingHoursCreate(WorkingHoursBase):
    pass

class WorkingHours(WorkingHoursBase):
    id: int
    barber_id: int
    
    model_config = ConfigDict(from_attributes=True)


# -------------------- BOOKING --------------------
class BookingBase(BaseModel):
    customer_name: str
    customer_email: EmailStr
    customer_phone: str
    start_time: datetime
    service_id: int
    notes: Optional[str] = None

class BookingCreate(BaseModel):
    barber_id: int
    service_id: int
    start_time: datetime
    notes: Optional[str] = None
    customer_phone: Optional[str] = None

class Booking(BookingBase):
    id: int
    barber_id: int
    end_time: datetime
    status: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class BookingSchema(BaseModel):
    id: int
    user_id: int
    barber_id: int
    service_id: int
    start_time: datetime
    end_time: datetime
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------- BARBER EXTENDED --------------------
class BarberWithServicesAndHours(Barber):
    services: List[Service] = []
    working_hours: List[WorkingHours] = []
    
    model_config = ConfigDict(from_attributes=True)


# -------------------- AVAILABLE SLOTS --------------------
class AvailableSlots(BaseModel):
    date: date
    available_times: List[datetime]


# -------------------- AUTH --------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# -------------------- USER UPDATE --------------------
class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_barber: Optional[bool] = None
    barber_bio: Optional[str] = None
    barber_shop_name: Optional[str] = None
    barber_shop_address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# -------------------- USER STATS & SETTINGS --------------------
class NotificationSettings(BaseModel):
    email_notifications: Optional[bool] = True
    sms_notifications: Optional[bool] = True
    push_notifications: Optional[bool] = True

    model_config = ConfigDict(from_attributes=True)

class UserStats(BaseModel):
    total_appointments: int
    favorite_barbers: int
    upcoming_appointments: int

    model_config = ConfigDict(from_attributes=True)


# -------------------- USER SCHEMA --------------------
class UserSchema(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    phone_number: Optional[str] = None
    birth_date: Optional[date] = None
    address: Optional[str] = None
    loyalty_points: Optional[int] = 0
    membership_tier: Optional[str] = None
    rating: Optional[float] = None
    notification_settings: Optional[dict] = None
    avatar_url: Optional[str] = None
    is_active: bool
    is_barber: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# -------------------- BUSINESS --------------------
class BusinessBase(BaseModel):
    name: str
    owner_name: str
    email: EmailStr
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    avatar_url: Optional[str] = None
    cover_photo_url: Optional[str] = None

class Business(BusinessBase):
    id: int

    model_config = ConfigDict(from_attributes=True)

class ServiceCreateForBusiness(BaseModel):
    name: str
    price: float
    duration: int

class BusinessCreateSchema(BaseModel):
    name: str
    owner_name: str
    email: EmailStr
    password: str
    phone: str
    address: str
    city: str
    country: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    services: List[ServiceCreateForBusiness] = []


# -------------------- WORKER MANAGEMENT --------------------
class WorkerInvite(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = "worker"  # owner, manager, worker

class WorkerResponse(BaseModel):
    id: int
    email: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None
    rating: Optional[float] = None
    barber_bio: Optional[str] = None
    status: str  # active, invited, suspended
    role: str
    joined_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class WorkerUpdate(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None
