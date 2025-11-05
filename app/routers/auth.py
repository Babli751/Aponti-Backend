from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Annotated, Optional, Literal
from pydantic import BaseModel
import requests

from app.core import security
from app.core.config import settings
from app.crud.crud_user import create_user, get_user_by_email
from app.models.schemas import UserCreate, Token, User
from app.models.models import User as DBUser
from app.core.database import get_db
from app.models import models  # for Business

router = APIRouter(tags=["auth"])


# ------------------------------
# Register
# ------------------------------
@router.post("/register", response_model=dict)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    print(f"🔄 Registration attempt for: {user_data.email}")
    print(f"📝 User data dict: {user_data.dict()}")
    print(f"📝 User data: email={user_data.email}, is_barber={user_data.is_barber}, first_name={user_data.first_name}, last_name={user_data.last_name}")

    # Force is_barber to True for all registrations
    user_data.is_barber = True

    db_user = get_user_by_email(db, email=user_data.email)
    if db_user:
        print(f"❌ Email already registered: {user_data.email}")
        raise HTTPException(status_code=400, detail="Email already registered")

    print("👤 Creating user...")
    user = create_user(db, user_data)
    print(f"✅ User created with ID: {user.id}, is_barber: {user.is_barber}")

    # Force commit and check if user exists
    db.commit()
    print(f"💾 Transaction committed")

    # Verify user was saved
    saved_user = get_user_by_email(db, email=user_data.email)
    if saved_user:
        print(f"✅ User verified in database: ID={saved_user.id}, email={saved_user.email}, is_barber={saved_user.is_barber}")
    else:
        print(f"❌ User NOT found in database after commit!")

    return {"status": "success", "id": user.id, "message": "User created successfully"}


# ------------------------------
# Login with form-data (OAuth2)
# ------------------------------
@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    print(f"🔄 Login attempt for: {form_data.username}")
    user = get_user_by_email(db, email=form_data.username)
    if not user:
        print(f"❌ User not found: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    print(f"✅ User found: {user.email}, is_barber: {user.is_barber}")
    if not security.verify_password(form_data.password, user.hashed_password):
        print(f"❌ Password incorrect for: {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    print(f"✅ Password correct, creating token")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    print(f"✅ Login successful for: {form_data.username}")
    return {"access_token": access_token, "token_type": "bearer"}


# ------------------------------
# Login with JSON body (custom)
# ------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/login_json", response_model=Token)
async def login_with_json(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, email=login_data.email)
    if not user or not security.verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ------------------------------
# Get current user
# ------------------------------
@router.get("/me", response_model=User)
async def read_current_user(
    current_user: Annotated[DBUser, Depends(security.get_current_user)]
):
    return User(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone_number=current_user.phone_number,
        is_active=current_user.is_active,
        is_barber=current_user.is_barber,
        created_at=current_user.created_at
    )


# ------------------------------
# Admin-only password reset (temporary, protected via X-Admin-Key)
# ------------------------------
class AdminResetRequest(BaseModel):
    target: Literal["user", "business"]
    email: str
    new_password: str

@router.post("/admin/reset_password", response_model=dict)
async def admin_reset_password(
    payload: AdminResetRequest,
    db: Session = Depends(get_db),
    x_admin_key: Optional[str] = Header(default=None, alias="X-Admin-Key"),
):
    # Validate admin key (prefer ADMIN_RESET_KEY if set, else allow SECRET_KEY)
    expected_keys = set()
    if settings.ADMIN_RESET_KEY and settings.ADMIN_RESET_KEY != "disabled":
        expected_keys.add(settings.ADMIN_RESET_KEY)
    expected_keys.add(settings.SECRET_KEY)

    if not x_admin_key or x_admin_key not in expected_keys:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")

    if payload.target == "user":
        user = get_user_by_email(db, email=payload.email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.hashed_password = security.get_password_hash(payload.new_password)
        db.add(user)
        db.commit()
        return {"status": "ok", "message": "User password reset", "email": payload.email}

    if payload.target == "business":
        business = db.query(models.Business).filter(models.Business.email == payload.email).first()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")
        business.hashed_password = security.get_password_hash(payload.new_password)
        db.add(business)
        db.commit()
        return {"status": "ok", "message": "Business password reset", "email": payload.email}

    raise HTTPException(status_code=400, detail="Invalid target")


# ------------------------------
# Social Login
# ------------------------------
class SocialLoginRequest(BaseModel):
    provider: str
    token: str

@router.post("/social-login", response_model=Token)
async def social_login(request: SocialLoginRequest, db: Session = Depends(get_db)):
    if request.provider == 'google':
        # Verify Google token
        try:
            response = requests.get(f'https://oauth2.googleapis.com/tokeninfo?id_token={request.token}')
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Invalid Google token")
            data = response.json()
            email = data.get('email')
            if not email:
                raise HTTPException(status_code=400, detail="Email not found in token")
            first_name = data.get('given_name', '')
            last_name = data.get('family_name', '')
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Token verification failed: {str(e)}")

    else:
        raise HTTPException(status_code=400, detail="Unsupported provider")

    # Check if user exists
    user = get_user_by_email(db, email=email)
    if not user:
        # Create new user
        user_data = UserCreate(
            email=email,
            password="social_login",  # Dummy password
            first_name=first_name,
            last_name=last_name,
            is_barber=False
        )
        user = create_user(db, user_data)

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        data={"sub": user.email},
        expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}
