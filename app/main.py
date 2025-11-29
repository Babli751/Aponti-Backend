print("MAIN.PY STARTING...")
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.core.database import engine, SessionLocal
from app.models import models
from app.models.models import Service, Business, User, Booking
from app.routers import auth, user, barber, booking, business, dashboard, upload, workers, slots, reviews, notifications, payments, analytics
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
        "http://206.189.57.55:8001", # Backend port (for Apache proxy)
        "https://aponti.org",         # HTTPS domain
        "https://www.aponti.org"      # HTTPS www subdomain
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
    app.include_router(services_router, prefix="/api/v1/services", tags=["Services"])
else:
    print("Services router is None, skipping inclusion")
app.include_router(dashboard.router)
app.include_router(upload.router, prefix="/api/v1/upload", tags=["Upload"])
app.include_router(workers.router, prefix="/api/v1/business/workers", tags=["Workers"])
app.include_router(slots.router, prefix="/api/v1/slots", tags=["Slots"])
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["Reviews"])
app.include_router(notifications.router, prefix="/api/v1/notifications", tags=["Notifications"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["Payments"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
print("All routers included")

@app.get("/")
def read_root():
    return {"message": "Welcome to the BarberPro API"}
