from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models import models
from app.core.security import get_current_user, get_current_business
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, func, Boolean, Text
import os
import secrets

router = APIRouter(tags=["payments"])

# Stripe API Key (set in environment)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_your_key_here")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_your_key_here")

# Note: Payment and Invoice models are now in app/models/models.py to avoid duplication

# Schemas
class PaymentCreate(BaseModel):
    booking_id: int
    amount: float
    payment_method: str  # card, cash, online, deposit
    stripe_token: Optional[str] = None
    save_card: Optional[bool] = False
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    id: int
    booking_id: int
    amount: float
    currency: str
    payment_method: str
    status: str
    invoice_number: Optional[str] = None
    created_at: datetime


class RefundRequest(BaseModel):
    payment_id: int
    amount: Optional[float] = None  # If None, full refund
    reason: str


class InvoiceCreate(BaseModel):
    payment_id: int
    tax_rate: Optional[float] = 0.0
    due_days: Optional[int] = 30
    notes: Optional[str] = None


class InvoiceResponse(BaseModel):
    id: int
    invoice_number: str
    payment_id: int
    amount: float
    tax_amount: float
    total_amount: float
    currency: str
    status: str
    due_date: Optional[datetime]
    created_at: datetime


# Helper Functions
def generate_invoice_number() -> str:
    """Generate unique invoice number"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_part = secrets.token_hex(4).upper()
    return f"INV-{timestamp}-{random_part}"


def simulate_stripe_charge(amount: float, token: str) -> dict:
    """
    Simulate Stripe charge (replace with actual Stripe API in production)

    In production:
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    charge = stripe.Charge.create(
        amount=int(amount * 100),  # Convert to cents
        currency="usd",
        source=token,
        description="Booking payment"
    )
    return charge
    """
    return {
        "id": f"ch_{secrets.token_hex(12)}",
        "status": "succeeded",
        "amount": amount,
        "currency": "usd"
    }


def simulate_stripe_refund(payment_id: str, amount: float) -> dict:
    """
    Simulate Stripe refund (replace with actual Stripe API in production)

    In production:
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    refund = stripe.Refund.create(
        charge=payment_id,
        amount=int(amount * 100)
    )
    return refund
    """
    return {
        "id": f"re_{secrets.token_hex(12)}",
        "status": "succeeded",
        "amount": amount
    }


# ------------------------------
# Create Payment
# ------------------------------
@router.post("/", response_model=PaymentResponse)
def create_payment(
    payment_data: PaymentCreate,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a payment for a booking"""

    # Verify booking exists and belongs to user
    booking = db.query(models.Booking).filter(
        models.Booking.id == payment_data.booking_id,
        models.Booking.user_id == current_user.id
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check if payment already exists
    existing_payment = db.query(models.Payment).filter(
        models.Payment.booking_id == payment_data.booking_id
    ).first()

    if existing_payment:
        raise HTTPException(status_code=400, detail="Payment already exists for this booking")

    # Get business from service
    service = booking.service
    if not service or not service.business_id:
        raise HTTPException(status_code=400, detail="Invalid booking service")

    # Process payment based on method
    stripe_payment_id = None
    payment_status = "pending"

    if payment_data.payment_method == "online" and payment_data.stripe_token:
        # Process with Stripe
        try:
            stripe_charge = simulate_stripe_charge(payment_data.amount, payment_data.stripe_token)
            stripe_payment_id = stripe_charge["id"]
            payment_status = "completed" if stripe_charge["status"] == "succeeded" else "failed"
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Payment processing failed: {str(e)}")

    elif payment_data.payment_method == "cash":
        payment_status = "pending"  # Will be marked completed by business

    elif payment_data.payment_method == "deposit":
        # Deposit payment (partial)
        if payment_data.amount < service.price * 0.1:
            raise HTTPException(status_code=400, detail="Deposit must be at least 10% of service price")
        payment_status = "completed"

    # Generate invoice number
    invoice_number = generate_invoice_number()

    # Create payment record
    payment = models.Payment(
        booking_id=payment_data.booking_id,
        user_id=current_user.id,
        business_id=service.business_id,
        amount=payment_data.amount,
        payment_method=payment_data.payment_method,
        status=payment_status,
        stripe_payment_id=stripe_payment_id,
        invoice_number=invoice_number,
        notes=payment_data.notes
    )

    db.add(payment)
    db.commit()
    db.refresh(payment)

    # Update booking status
    if payment_status == "completed":
        booking.status = "confirmed"
        db.commit()

    # Send notification (background task)
    # background_tasks.add_task(send_payment_confirmation, db, payment.id)

    return PaymentResponse(
        id=payment.id,
        booking_id=payment.booking_id,
        amount=payment.amount,
        currency=payment.currency,
        payment_method=payment.payment_method,
        status=payment.status,
        invoice_number=payment.invoice_number,
        created_at=payment.created_at
    )


# Get Payment History
@router.get("/history")
def get_payment_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's payment history"""
    payments = db.query(models.Payment).filter(models.Payment.user_id == current_user.id).all()

    return [
        {
            "id": p.id,
            "booking_id": p.booking_id,
            "amount": p.amount,
            "currency": p.currency,
            "payment_method": p.payment_method,
            "status": p.status,
            "created_at": p.created_at
        }
        for p in payments
    ]


# ------------------------------
# Process Refund
# ------------------------------
@router.post("/refund")
def process_refund(
    refund_data: RefundRequest,
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Process a refund for a payment"""

    # Get payment
    payment = db.query(models.Payment).filter(
        models.Payment.id == refund_data.payment_id,
        models.Payment.business_id == current_business.id
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.status == "refunded":
        raise HTTPException(status_code=400, detail="Payment already refunded")

    if payment.status != "completed":
        raise HTTPException(status_code=400, detail="Can only refund completed payments")

    # Determine refund amount
    refund_amount = refund_data.amount if refund_data.amount else payment.amount

    if refund_amount > payment.amount:
        raise HTTPException(status_code=400, detail="Refund amount cannot exceed payment amount")

    # Process refund with Stripe if online payment
    stripe_refund_id = None
    if payment.payment_method == "online" and payment.stripe_payment_id:
        try:
            stripe_refund = simulate_stripe_refund(payment.stripe_payment_id, refund_amount)
            stripe_refund_id = stripe_refund["id"]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Refund processing failed: {str(e)}")

    # Update payment
    payment.refund_amount = refund_amount
    payment.refund_reason = refund_data.reason
    payment.stripe_refund_id = stripe_refund_id
    payment.status = "refunded" if refund_amount == payment.amount else "partially_refunded"

    db.commit()

    # Update booking status
    booking = db.query(models.Booking).filter(models.Booking.id == payment.booking_id).first()
    if booking:
        booking.status = "cancelled"
        db.commit()

    return {
        "success": True,
        "payment_id": payment.id,
        "refund_amount": refund_amount,
        "status": payment.status,
        "message": "Refund processed successfully"
    }


# ------------------------------
# Create Invoice
# ------------------------------
@router.post("/invoice", response_model=InvoiceResponse)
def create_invoice(
    invoice_data: InvoiceCreate,
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Create an invoice for a payment"""

    # Get payment
    payment = db.query(models.Payment).filter(
        models.Payment.id == invoice_data.payment_id,
        models.Payment.business_id == current_business.id
    ).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Check if invoice already exists
    existing_invoice = db.query(models.Invoice).filter(models.Invoice.payment_id == payment.id).first()
    if existing_invoice:
        raise HTTPException(status_code=400, detail="Invoice already exists for this payment")

    # Calculate amounts
    tax_amount = payment.amount * invoice_data.tax_rate if invoice_data.tax_rate else 0
    total_amount = payment.amount + tax_amount

    # Generate invoice number (use payment's invoice number if exists)
    invoice_number = payment.invoice_number if payment.invoice_number else generate_invoice_number()

    # Calculate due date
    due_date = datetime.now() + timedelta(days=invoice_data.due_days)

    # Create invoice
    invoice = models.Invoice(
        invoice_number=invoice_number,
        payment_id=payment.id,
        user_id=payment.user_id,
        business_id=payment.business_id,
        amount=payment.amount,
        tax_amount=tax_amount,
        total_amount=total_amount,
        due_date=due_date,
        status="paid" if payment.status == "completed" else "issued",
        paid_at=payment.created_at if payment.status == "completed" else None,
        notes=invoice_data.notes
    )

    db.add(invoice)
    db.commit()
    db.refresh(invoice)

    return InvoiceResponse(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        payment_id=invoice.payment_id,
        amount=invoice.amount,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        status=invoice.status,
        due_date=invoice.due_date,
        created_at=invoice.created_at
    )


# ------------------------------
# Get Invoices
# ------------------------------
@router.get("/invoices", response_model=List[InvoiceResponse])
def get_invoices(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's invoices"""
    invoices = db.query(models.Invoice).filter(models.Invoice.user_id == current_user.id).all()

    return [
        InvoiceResponse(
            id=inv.id,
            invoice_number=inv.invoice_number,
            payment_id=inv.payment_id,
            amount=inv.amount,
            tax_amount=inv.tax_amount,
            total_amount=inv.total_amount,
            currency=inv.currency,
            status=inv.status,
            due_date=inv.due_date,
            created_at=inv.created_at
        )
        for inv in invoices
    ]


# ------------------------------
# Get Business Revenue Stats
# ------------------------------
@router.get("/business/revenue")
def get_business_revenue(
    current_business: models.Business = Depends(get_current_business),
    db: Session = Depends(get_db)
):
    """Get business revenue stats"""
    payments = db.query(models.Payment).filter(
        models.Payment.business_id == current_business.id,
        models.Payment.status.in_(["completed", "partially_refunded"])
    ).all()

    total_revenue = sum(p.amount for p in payments)
    total_refunded = sum(p.refund_amount for p in payments if p.refund_amount)
    net_revenue = total_revenue - total_refunded
    total_transactions = len(payments)

    # Get payment method breakdown
    payment_methods = {}
    for p in payments:
        payment_methods[p.payment_method] = payment_methods.get(p.payment_method, 0) + p.amount

    return {
        "total_revenue": total_revenue,
        "total_refunded": total_refunded,
        "net_revenue": net_revenue,
        "total_transactions": total_transactions,
        "payment_methods": payment_methods,
        "currency": "USD"
    }


# ------------------------------
# Get Stripe Publishable Key (for frontend)
# ------------------------------

# Add this endpoint before the @router.get("/config/stripe") endpoint

# ------------------------------
# Get Payment Configuration (for 2Checkout)
# ------------------------------
@router.get("/config")
def get_payment_config():
    """Get payment configuration for frontend"""
    # 2Checkout configuration
    merchant_code = os.getenv("TWOCHECKOUT_MERCHANT_CODE", "253177870927")
    publishable_key = os.getenv("TWOCHECKOUT_PUBLISHABLE_KEY", "67134D0A-9FA7-454E-989E-D2D1F0EFF8DB")
    sandbox = os.getenv("TWOCHECKOUT_SANDBOX", "true").lower() == "true"
    
    return {
        "merchant_code": merchant_code,
        "publishable_key": publishable_key,
        "sandbox": sandbox,
        "provider": "2checkout"
    }

@router.get("/config/stripe")
def get_stripe_config():
    """Get Stripe publishable key for frontend"""
    return {
        "publishable_key": STRIPE_PUBLISHABLE_KEY
    }
