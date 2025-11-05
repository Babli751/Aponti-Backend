from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from app.core.security import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime, func

router = APIRouter(tags=["reviews"])


# Create Review model (add to models.py later)
class Review(models.Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=True)
    worker_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=True)
    rating = Column(Float, nullable=False)  # 1-5 stars
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


# Schemas
class ReviewCreate(BaseModel):
    business_id: Optional[int] = None
    worker_id: Optional[int] = None
    booking_id: Optional[int] = None
    rating: float
    comment: Optional[str] = None


class ReviewResponse(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_avatar: Optional[str]
    business_id: Optional[int]
    worker_id: Optional[int]
    rating: float
    comment: Optional[str]
    created_at: datetime


# Create review
@router.post("/", response_model=dict)
def create_review(
    review_data: ReviewCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a review for business or worker"""

    if review_data.rating < 1 or review_data.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    review = Review(
        user_id=current_user.id,
        business_id=review_data.business_id,
        worker_id=review_data.worker_id,
        booking_id=review_data.booking_id,
        rating=review_data.rating,
        comment=review_data.comment
    )

    db.add(review)
    db.commit()
    db.refresh(review)

    # Update worker/business average rating
    if review_data.worker_id:
        avg_rating = db.query(func.avg(Review.rating)).filter(Review.worker_id == review_data.worker_id).scalar()
        worker = db.query(models.User).filter(models.User.id == review_data.worker_id).first()
        if worker:
            worker.rating = float(avg_rating) if avg_rating else 0.0
            db.commit()

    return {"success": True, "review_id": review.id, "message": "Review submitted successfully"}


# Get reviews for business
@router.get("/business/{business_id}", response_model=List[ReviewResponse])
def get_business_reviews(business_id: int, db: Session = Depends(get_db)):
    """Get all reviews for a business"""

    reviews = db.query(Review).filter(Review.business_id == business_id).all()

    result = []
    for review in reviews:
        user = db.query(models.User).filter(models.User.id == review.user_id).first()
        result.append(ReviewResponse(
            id=review.id,
            user_id=review.user_id,
            user_name=f"{user.first_name} {user.last_name}" if user else "Anonymous",
            user_avatar=user.avatar_url if user else None,
            business_id=review.business_id,
            worker_id=review.worker_id,
            rating=review.rating,
            comment=review.comment,
            created_at=review.created_at
        ))

    return result


# Get reviews for worker
@router.get("/worker/{worker_id}", response_model=List[ReviewResponse])
def get_worker_reviews(worker_id: int, db: Session = Depends(get_db)):
    """Get all reviews for a worker"""

    reviews = db.query(Review).filter(Review.worker_id == worker_id).all()

    result = []
    for review in reviews:
        user = db.query(models.User).filter(models.User.id == review.user_id).first()
        result.append(ReviewResponse(
            id=review.id,
            user_id=review.user_id,
            user_name=f"{user.first_name} {user.last_name}" if user else "Anonymous",
            user_avatar=user.avatar_url if user else None,
            business_id=review.business_id,
            worker_id=review.worker_id,
            rating=review.rating,
            comment=review.comment,
            created_at=review.created_at
        ))

    return result
