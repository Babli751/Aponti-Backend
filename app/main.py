print("MAIN.PY STARTING...")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.core.database import engine, SessionLocal
from app.models import models
from app.models.models import Service, Business, User, Booking
from app.routers import auth, user, barber, booking, business, dashboard, upload, workers, slots, reviews, notifications, payments
try:
    from app.routers.services import router as services_router
    print("Services router imported successfully")
except ImportError as e:
    print(f"Failed to import services router: {e}")
    services_router = None
from app.core.security import get_password_hash

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="BarberPro API",
    description="API for the BarberPro booking platform.",
    version="1.0.0"
)

# Mount static files for avatars
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://206.189.57.55",      # Apache frontend (port 80)
        "http://206.189.57.55:8000", # Direct backend access (for testing)
        "http://206.189.57.55:8001"  # Backend port (for Apache proxy)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
print("Including routers...")
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(user.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(barber.router, prefix="/api/v1/barbers", tags=["Barbers"])
app.include_router(booking.router, prefix="/api/v1/bookings", tags=["Bookings"])
app.include_router(business.router, prefix="/api/v1/businesses", tags=["Business"])
if services_router:
    print(f"Including services router: {services_router}")
    app.include_router(services_router, prefix="/api/v1", tags=["Services"])
else:
    print("Services router is None, skipping inclusion")
app.include_router(dashboard.router)
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
app.include_router(workers.router, prefix="/api/v1/business/workers", tags=["Workers"])
app.include_router(slots.router, prefix="/api/v1/slots", tags=["Slots"])
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["Reviews"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])
print("All routers included")

@app.get("/")
def read_root():
    return {"message": "Welcome to the BarberPro API"}

# -----------------------------
# Startup event: create mock services
# -----------------------------
def create_mock_services():
    db: Session = SessionLocal()
    try:
        # Create a default business if none exists
        business = db.query(Business).first()
        if not business:
            business = Business(
                name="Default Shop",
                owner_name="Admin",
                email="shop@test.com",
                hashed_password=get_password_hash("123456"),
                phone="1234567890",
                address="Street 1",
                city="City",
                description="Demo business"
            )
            db.add(business)
            db.commit()
            db.refresh(business)

        # Create a default barber if none exists
        barber = db.query(User).filter(User.is_barber == True).first()
        if not barber:
            barber = User(
                email="barber@test.com",
                hashed_password=get_password_hash("password123"),
                first_name="John",
                last_name="Doe",
                is_barber=True,
                is_active=True
            )
            db.add(barber)
            db.commit()
            db.refresh(barber)

        # Remove mock services and related bookings
        mock_names = ["Haircut", "Shave", "Haircut + Shave"]
        for name in mock_names:
            service = db.query(Service).filter(Service.name == name).first()
            if service:
                # Delete related bookings first
                bookings = db.query(Booking).filter(Booking.service_id == service.id).all()
                for booking in bookings:
                    db.delete(booking)
                db.delete(service)

        # Remove mock business
        mock_business = db.query(Business).filter(Business.email == "shop@test.com").first()
        if mock_business:
            db.delete(mock_business)

        db.commit()
    finally:
        db.close()

# @app.on_event("startup")
# def startup_event():
#     create_mock_services()
