from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.models import User, Business
from app.core.database import get_db

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme configuration
# User login üçün token URL
oauth2_scheme_user = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
# Business login üçün token URL
oauth2_scheme_business = OAuth2PasswordBearer(tokenUrl="/api/v1/business/login")

# ----------------- Password Hashing -----------------
def get_password_hash(password: str) -> str:
    """Hash parol"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Parolu doğrula"""
    return pwd_context.verify(plain_password, hashed_password)

# ----------------- JWT Token -----------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT token yarat"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def verify_token(token: str) -> str:
    """Token doğrula və email qaytar"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise JWTError("Invalid token payload")
        return email
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ----------------- Current User / Business -----------------
async def get_current_user(
    token: str = Depends(oauth2_scheme_user),
    db: Session = Depends(get_db)
) -> User:
    """Aktiv useri al"""
    try:
        email = verify_token(token)
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        print(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Aktiv useri al"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_current_business(
    token: str = Depends(oauth2_scheme_business),
    db: Session = Depends(get_db)
) -> Business:
    """Aktiv businessi al"""
    try:
        email = verify_token(token)
        business = db.query(Business).filter(Business.email == email).first()
        if not business:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Business not found"
            )
        return business
    except HTTPException:
        raise
    except Exception as e:
        print(f"Business token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
