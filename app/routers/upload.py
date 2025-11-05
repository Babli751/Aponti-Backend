from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from app.core.security import get_current_user, get_current_business
from typing import Optional
import os
import shutil
from pathlib import Path
import uuid
from datetime import datetime

router = APIRouter(tags=["upload"])

# Upload directory
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Allowed file extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

def validate_image(file: UploadFile) -> bool:
    """Validate uploaded image"""
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return True

def save_upload_file(upload_file: UploadFile, destination: Path) -> None:
    """Save uploaded file to disk"""
    try:
        with destination.open("wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    finally:
        upload_file.file.close()

def generate_filename(original_filename: str) -> str:
    """Generate unique filename"""
    file_ext = Path(original_filename).suffix.lower()
    unique_id = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{unique_id}{file_ext}"


# ------------------------------
# Upload Business Avatar
# ------------------------------
@router.post("/business/avatar")
async def upload_business_avatar(
    file: UploadFile = File(...),
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Upload business profile avatar"""
    validate_image(file)

    # Create business-specific directory
    business_dir = UPLOAD_DIR / "businesses" / str(current_business.id)
    business_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename and save
    filename = generate_filename(file.filename)
    file_path = business_dir / filename
    save_upload_file(file, file_path)

    # Update database
    file_url = f"/uploads/businesses/{current_business.id}/{filename}"
    current_business.avatar_url = file_url
    db.commit()

    return {
        "success": True,
        "avatar_url": file_url,
        "message": "Avatar uploaded successfully"
    }


# ------------------------------
# Upload Business Cover Photo
# ------------------------------
@router.post("/business/cover")
async def upload_business_cover(
    file: UploadFile = File(...),
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Upload business cover photo"""
    validate_image(file)

    # Create business-specific directory
    business_dir = UPLOAD_DIR / "businesses" / str(current_business.id)
    business_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename and save
    filename = generate_filename(file.filename)
    file_path = business_dir / filename
    save_upload_file(file, file_path)

    # Update database
    file_url = f"/uploads/businesses/{current_business.id}/{filename}"
    current_business.cover_photo_url = file_url
    db.commit()

    return {
        "success": True,
        "cover_photo_url": file_url,
        "message": "Cover photo uploaded successfully"
    }


# ------------------------------
# Upload User/Worker Avatar
# ------------------------------
@router.post("/user/avatar")
async def upload_user_avatar(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload user/worker profile avatar"""
    validate_image(file)

    # Create user-specific directory
    user_dir = UPLOAD_DIR / "users" / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename and save
    filename = generate_filename(file.filename)
    file_path = user_dir / filename
    save_upload_file(file, file_path)

    # Update database
    file_url = f"/uploads/users/{current_user.id}/{filename}"
    current_user.avatar_url = file_url
    db.commit()

    return {
        "success": True,
        "avatar_url": file_url,
        "message": "Avatar uploaded successfully"
    }


# ------------------------------
# Upload Service Photo (for portfolio/gallery)
# ------------------------------
@router.post("/service/{service_id}/photo")
async def upload_service_photo(
    service_id: int,
    file: UploadFile = File(...),
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Upload service photo (e.g., before/after, portfolio)"""
    validate_image(file)

    # Verify service belongs to business
    service = db.query(models.Service).filter(
        models.Service.id == service_id,
        models.Service.business_id == current_business.id
    ).first()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    # Create service-specific directory
    service_dir = UPLOAD_DIR / "services" / str(service_id)
    service_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename and save
    filename = generate_filename(file.filename)
    file_path = service_dir / filename
    save_upload_file(file, file_path)

    file_url = f"/uploads/services/{service_id}/{filename}"

    # TODO: Add ServicePhoto model to store multiple photos per service
    # For now, we'll just return the URL

    return {
        "success": True,
        "photo_url": file_url,
        "message": "Service photo uploaded successfully"
    }


# ------------------------------
# Delete Uploaded File
# ------------------------------
@router.delete("/files")
async def delete_file(
    file_path: str,
    current_user: Optional[models.User] = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete uploaded file (for cleaning up old avatars/photos)"""
    # Security: Only allow deletion of files in uploads directory
    if not file_path.startswith("/uploads/"):
        raise HTTPException(status_code=400, detail="Invalid file path")

    # Remove leading slash
    file_path = file_path.lstrip("/")

    # Full path
    full_path = Path(file_path)

    # Check if file exists
    if not full_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Delete file
    try:
        full_path.unlink()
        return {"success": True, "message": "File deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")
