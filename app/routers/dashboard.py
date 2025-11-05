from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import User, Booking, FavoriteBarber  # 🔑 Modelleri import et

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard"]
)


@router.get("/{user_email}")
def get_dashboard_data(user_email: str, db: Session = Depends(get_db)):
    # Kullanıcıyı email ile bul
    user = db.query(User).filter(User.email == user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Kullanıcının randevularını çek
    appointments = db.query(Booking).filter(Booking.user_id == user.id).all()

    # Favori berberlerini çek
    favorite_barbers = (
        db.query(FavoriteBarber)
        .filter(FavoriteBarber.user_id == user.id)
        .all()
    )

    # Response
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name
        },
        "upcoming_appointments": [
            {
                "id": a.id,
                "barber_id": a.barber_id,
                "service_id": a.service_id,
                "start_time": a.start_time,
                "end_time": a.end_time,
                "status": a.status,
                "notes": a.notes
            }
            for a in appointments if a.status in ["pending", "confirmed"]
        ],
        "past_appointments": [
            {
                "id": a.id,
                "barber_id": a.barber_id,
                "service_id": a.service_id,
                "start_time": a.start_time,
                "end_time": a.end_time,
                "status": a.status,
                "notes": a.notes
            }
            for a in appointments if a.status in ["completed", "cancelled"]
        ],
        "favorite_barbers": [
            {
                "id": fb.barber.id,
                "name": f"{fb.barber.first_name} {fb.barber.last_name}",
                "email": fb.barber.email
            }
            for fb in favorite_barbers
        ]
    }
