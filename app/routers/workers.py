from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from app.models.schemas import WorkerInvite, WorkerResponse, WorkerUpdate
from app.core.security import get_current_business, get_password_hash
from typing import List
from datetime import datetime

router = APIRouter(tags=["workers"])


# ------------------------------
# Get All Workers for Business
# ------------------------------
@router.get("/", response_model=List[WorkerResponse])
def get_business_workers(
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Get all workers (employees) for the current business"""
    # Get all business-worker relationships
    business_workers = db.query(models.BusinessWorker).filter(
        models.BusinessWorker.business_id == current_business.id
    ).all()

    workers = []
    for bw in business_workers:
        worker = bw.worker
        workers.append(WorkerResponse(
            id=worker.id,
            email=worker.email,
            first_name=worker.first_name,
            last_name=worker.last_name,
            phone_number=worker.phone_number,
            avatar_url=worker.avatar_url,
            rating=worker.rating,
            barber_bio=worker.barber_bio,
            status=bw.status,
            role=bw.role,
            joined_at=bw.joined_at
        ))

    return workers


# ------------------------------
# Invite Worker to Business
# ------------------------------
@router.post("/invite", response_model=dict)
def invite_worker(
    invite_data: WorkerInvite,
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Invite a worker to join the business"""

    # Check if user already exists
    existing_user = db.query(models.User).filter(
        models.User.email == invite_data.email
    ).first()

    if existing_user:
        # Check if already a worker for this business
        existing_relationship = db.query(models.BusinessWorker).filter(
            models.BusinessWorker.business_id == current_business.id,
            models.BusinessWorker.worker_id == existing_user.id
        ).first()

        if existing_relationship:
            raise HTTPException(
                status_code=400,
                detail="This user is already a worker at your business"
            )

        # Add existing user as worker
        business_worker = models.BusinessWorker(
            business_id=current_business.id,
            worker_id=existing_user.id,
            role=invite_data.role,
            status="active",
            joined_at=datetime.now()
        )
        db.add(business_worker)
        db.commit()

        return {
            "success": True,
            "message": "Worker added successfully",
            "worker_id": existing_user.id,
            "status": "active"
        }
    else:
        # Create new user account (invited state)
        # Generate temporary password (they'll reset it on first login)
        temp_password = f"temp_{invite_data.email.split('@')[0]}123"

        new_user = models.User(
            email=invite_data.email,
            hashed_password=get_password_hash(temp_password),
            first_name=invite_data.first_name,
            last_name=invite_data.last_name,
            is_barber=True,  # Workers are barbers
            is_active=True
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Create business-worker relationship
        business_worker = models.BusinessWorker(
            business_id=current_business.id,
            worker_id=new_user.id,
            role=invite_data.role,
            status="invited"  # Invited status until they login
        )
        db.add(business_worker)
        db.commit()

        # TODO: Send email invitation with temp password
        # For now, just return the temp password in response (NOT SECURE for production!)

        return {
            "success": True,
            "message": "Worker invited successfully",
            "worker_id": new_user.id,
            "status": "invited",
            "temp_password": temp_password,  # Remove this in production!
            "note": "Send this temp password to the worker via email"
        }


# ------------------------------
# Update Worker (Role/Status)
# ------------------------------
@router.put("/{worker_id}", response_model=dict)
def update_worker(
    worker_id: int,
    update_data: WorkerUpdate,
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Update worker's role or status"""

    # Get business-worker relationship
    business_worker = db.query(models.BusinessWorker).filter(
        models.BusinessWorker.business_id == current_business.id,
        models.BusinessWorker.worker_id == worker_id
    ).first()

    if not business_worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Update fields
    if update_data.role:
        business_worker.role = update_data.role

    if update_data.status:
        business_worker.status = update_data.status

        # If activating invited worker, set joined_at
        if update_data.status == "active" and business_worker.status == "invited":
            business_worker.joined_at = datetime.now()

    db.commit()

    return {
        "success": True,
        "message": "Worker updated successfully",
        "worker_id": worker_id
    }


# ------------------------------
# Remove Worker from Business
# ------------------------------
@router.delete("/{worker_id}", response_model=dict)
def remove_worker(
    worker_id: int,
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Remove a worker from the business"""

    # Get business-worker relationship
    business_worker = db.query(models.BusinessWorker).filter(
        models.BusinessWorker.business_id == current_business.id,
        models.BusinessWorker.worker_id == worker_id
    ).first()

    if not business_worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Delete the relationship
    db.delete(business_worker)
    db.commit()

    return {
        "success": True,
        "message": "Worker removed successfully",
        "worker_id": worker_id
    }


# ------------------------------
# Get Worker Details
# ------------------------------
@router.get("/{worker_id}", response_model=WorkerResponse)
def get_worker_details(
    worker_id: int,
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific worker"""

    # Get business-worker relationship
    business_worker = db.query(models.BusinessWorker).filter(
        models.BusinessWorker.business_id == current_business.id,
        models.BusinessWorker.worker_id == worker_id
    ).first()

    if not business_worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    worker = business_worker.worker

    return WorkerResponse(
        id=worker.id,
        email=worker.email,
        first_name=worker.first_name,
        last_name=worker.last_name,
        phone_number=worker.phone_number,
        avatar_url=worker.avatar_url,
        rating=worker.rating,
        barber_bio=worker.barber_bio,
        status=business_worker.status,
        role=business_worker.role,
        joined_at=business_worker.joined_at
    )


# ------------------------------
# Assign Services to Worker
# ------------------------------
@router.post("/{worker_id}/services", response_model=dict)
def assign_services_to_worker(
    worker_id: int,
    service_ids: List[int],
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Assign multiple services to a worker"""

    # Verify worker belongs to business
    business_worker = db.query(models.BusinessWorker).filter(
        models.BusinessWorker.business_id == current_business.id,
        models.BusinessWorker.worker_id == worker_id
    ).first()

    if not business_worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Clear existing service assignments for this worker and business
    db.query(models.BarberService).filter(
        models.BarberService.barber_id == worker_id
    ).delete()

    # Assign new services
    assigned_count = 0
    for service_id in service_ids:
        # Verify service belongs to business
        service = db.query(models.Service).filter(
            models.Service.id == service_id,
            models.Service.business_id == current_business.id
        ).first()

        if service:
            barber_service = models.BarberService(
                barber_id=worker_id,
                service_id=service_id
            )
            db.add(barber_service)
            assigned_count += 1

    db.commit()

    return {
        "success": True,
        "message": f"Assigned {assigned_count} services to worker",
        "worker_id": worker_id,
        "service_count": assigned_count
    }


# ------------------------------
# Get Worker's Services
# ------------------------------
@router.get("/{worker_id}/services", response_model=List[dict])
def get_worker_services(
    worker_id: int,
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Get all services assigned to a worker"""

    # Verify worker belongs to business
    business_worker = db.query(models.BusinessWorker).filter(
        models.BusinessWorker.business_id == current_business.id,
        models.BusinessWorker.worker_id == worker_id
    ).first()

    if not business_worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    # Get worker's services
    barber_services = db.query(models.BarberService).filter(
        models.BarberService.barber_id == worker_id
    ).all()

    services = []
    for bs in barber_services:
        service = bs.service
        if service and service.business_id == current_business.id:
            services.append({
                "id": service.id,
                "name": service.name,
                "price": service.price,
                "duration": service.duration,
                "description": service.description
            })

    return services
