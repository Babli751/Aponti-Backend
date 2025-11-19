from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from app.core.security import get_current_user
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

router = APIRouter(tags=["reviews"])


# Schemas
class ReviewCreate(BaseModel):
    business_id: int
    rating: int  # 1-5 stars
    comment: Optional[str] = None


class ReviewResponse(BaseModel):
    id: int
    user_id: int
    user_name: str
    user_avatar: Optional[str]
    business_id: int
    rating: int
    comment: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Create review
@router.post("/", response_model=dict)
def create_review(
    review_data: ReviewCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a review for a business"""

    if review_data.rating < 1 or review_data.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    # Check if business exists
    business = db.query(models.Business).filter(models.Business.id == review_data.business_id).first()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    # Create review
    review = models.Review(
        user_id=current_user.id,
        business_id=review_data.business_id,
        rating=review_data.rating,
        comment=review_data.comment
    )

    db.add(review)
    db.commit()
    db.refresh(review)

    return {"success": True, "review_id": review.id, "message": "Review submitted successfully"}


# Get reviews for business
@router.get("/business/{business_id}", response_model=List[ReviewResponse])
def get_business_reviews(business_id: int, db: Session = Depends(get_db)):
    """Get all reviews for a business"""

    reviews = db.query(models.Review).filter(models.Review.business_id == business_id).order_by(models.Review.created_at.desc()).all()

    result = []
    for review in reviews:
        user = db.query(models.User).filter(models.User.id == review.user_id).first()
        user_name = "Anonymous"
        if user:
            if user.first_name and user.last_name:
                user_name = f"{user.first_name} {user.last_name}"
            elif user.first_name:
                user_name = user.first_name

        result.append(ReviewResponse(
            id=review.id,
            user_id=review.user_id,
            user_name=user_name,
            user_avatar=user.avatar_url if user else None,
            business_id=review.business_id,
            rating=review.rating,
            comment=review.comment,
            created_at=review.created_at
        ))

    return result
