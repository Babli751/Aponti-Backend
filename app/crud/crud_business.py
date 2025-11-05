from sqlalchemy.orm import Session
from app.models.models import Business
from app.models.schemas import BusinessCreateSchema

def get_business_by_email(db: Session, email: str):
    return db.query(Business).filter(Business.email == email).first()

def create_business(db: Session, business: BusinessCreateSchema):
    db_business = Business(
        name=business.name,
        owner_name=business.owner_name,
        email=business.email,
        password=business.password,  # Şifreyi hash'lemen önerilir!
        phone=business.phone,
        address=business.address,
        city=business.city,
        description=business.description
    )
    db.add(db_business)
    db.commit()
    db.refresh(db_business)
    return db_business