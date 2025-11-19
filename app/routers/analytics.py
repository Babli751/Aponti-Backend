from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, distinct, and_, cast, Date
from datetime import datetime, timedelta
from typing import List, Optional
from pydantic import BaseModel
import httpx
import uuid
from app.core.database import get_db
from app.models.models import (
    VisitorSession, PageView, ClickEvent, AdminUser,
    User, Business, Booking, Payment, Review
)
from passlib.context import CryptContext
from jose import jwt
import os

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings for admin
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "admin-super-secret-key-change-in-production")
ADMIN_ALGORITHM = "HS256"


# ==================== SCHEMAS ====================

class SessionStartRequest(BaseModel):
    visitor_id: str
    user_agent: Optional[str] = None
    referrer: Optional[str] = None
    landing_page: Optional[str] = None

class PageViewRequest(BaseModel):
    session_id: str
    page_path: str
    page_title: Optional[str] = None
    time_on_page: Optional[int] = None

class ClickEventRequest(BaseModel):
    session_id: str
    element_id: Optional[str] = None
    element_text: Optional[str] = None
    element_type: Optional[str] = None
    page_path: Optional[str] = None

class AdminLoginRequest(BaseModel):
    username: str
    password: str

class AdminCreateRequest(BaseModel):
    username: str
    email: str
    password: str
    is_superadmin: bool = False


# ==================== HELPER FUNCTIONS ====================

def get_client_ip(request: Request) -> str:
    """Get real client IP from request headers"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

def parse_user_agent(user_agent: str) -> dict:
    """Parse user agent to extract device, browser, OS info"""
    ua_lower = user_agent.lower() if user_agent else ""

    # Device type
    if "mobile" in ua_lower or "android" in ua_lower and "mobile" in ua_lower:
        device_type = "mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device_type = "tablet"
    else:
        device_type = "desktop"

    # Browser
    if "chrome" in ua_lower and "edg" not in ua_lower:
        browser = "Chrome"
    elif "firefox" in ua_lower:
        browser = "Firefox"
    elif "safari" in ua_lower and "chrome" not in ua_lower:
        browser = "Safari"
    elif "edg" in ua_lower:
        browser = "Edge"
    else:
        browser = "Other"

    # OS
    if "windows" in ua_lower:
        os_name = "Windows"
    elif "mac" in ua_lower:
        os_name = "macOS"
    elif "linux" in ua_lower:
        os_name = "Linux"
    elif "android" in ua_lower:
        os_name = "Android"
    elif "iphone" in ua_lower or "ipad" in ua_lower:
        os_name = "iOS"
    else:
        os_name = "Other"

    return {"device_type": device_type, "browser": browser, "os": os_name}

async def get_geolocation(ip_address: str) -> dict:
    """Get country and city from IP address using free API"""
    if ip_address in ["127.0.0.1", "localhost", "unknown"]:
        return {"country": "Local", "city": "Local"}

    try:
        async with httpx.AsyncClient() as client:
            # Using ip-api.com (free, no API key needed, 45 requests/minute)
            response = await client.get(f"http://ip-api.com/json/{ip_address}?fields=country,city")
            if response.status_code == 200:
                data = response.json()
                return {
                    "country": data.get("country", "Unknown"),
                    "city": data.get("city", "Unknown")
                }
    except Exception as e:
        print(f"Geolocation error: {e}")

    return {"country": "Unknown", "city": "Unknown"}

def create_admin_token(admin_id: int, username: str) -> str:
    """Create JWT token for admin"""
    expire = datetime.utcnow() + timedelta(hours=24)
    payload = {
        "sub": str(admin_id),
        "username": username,
        "exp": expire,
        "type": "admin"
    }
    return jwt.encode(payload, ADMIN_SECRET_KEY, algorithm=ADMIN_ALGORITHM)

def verify_admin_token(token: str) -> dict:
    """Verify admin JWT token"""
    try:
        payload = jwt.decode(token, ADMIN_SECRET_KEY, algorithms=[ADMIN_ALGORITHM])
        return payload
    except:
        return None


# ==================== TRACKING ENDPOINTS ====================

@router.post("/track/session")
async def start_session(
    request: Request,
    data: SessionStartRequest,
    db: Session = Depends(get_db)
):
    """Start a new visitor session"""
    ip_address = get_client_ip(request)
    ua_info = parse_user_agent(data.user_agent)
    geo_info = await get_geolocation(ip_address)

    # Check if returning visitor
    existing_visitor = db.query(VisitorSession).filter(
        VisitorSession.visitor_id == data.visitor_id
    ).first()
    is_returning = existing_visitor is not None

    # Create new session
    session_id = str(uuid.uuid4())
    session = VisitorSession(
        session_id=session_id,
        visitor_id=data.visitor_id,
        ip_address=ip_address,
        country=geo_info["country"],
        city=geo_info["city"],
        user_agent=data.user_agent,
        device_type=ua_info["device_type"],
        browser=ua_info["browser"],
        os=ua_info["os"],
        referrer=data.referrer,
        landing_page=data.landing_page,
        is_returning=is_returning
    )
    db.add(session)
    db.commit()

    return {"session_id": session_id, "is_returning": is_returning}


@router.post("/track/pageview")
async def track_pageview(
    data: PageViewRequest,
    db: Session = Depends(get_db)
):
    """Track a page view"""
    # Update session last activity
    session = db.query(VisitorSession).filter(
        VisitorSession.session_id == data.session_id
    ).first()

    if session:
        session.last_activity = datetime.utcnow()

    # Create page view record
    page_view = PageView(
        session_id=data.session_id,
        page_path=data.page_path,
        page_title=data.page_title,
        time_on_page=data.time_on_page
    )
    db.add(page_view)
    db.commit()

    return {"status": "ok"}


@router.post("/track/click")
async def track_click(
    data: ClickEventRequest,
    db: Session = Depends(get_db)
):
    """Track a click event"""
    click_event = ClickEvent(
        session_id=data.session_id,
        element_id=data.element_id,
        element_text=data.element_text,
        element_type=data.element_type,
        page_path=data.page_path
    )
    db.add(click_event)
    db.commit()

    return {"status": "ok"}


# ==================== ADMIN AUTH ENDPOINTS ====================

@router.post("/admin/login")
async def admin_login(
    data: AdminLoginRequest,
    db: Session = Depends(get_db)
):
    """Admin login"""
    admin = db.query(AdminUser).filter(
        AdminUser.username == data.username
    ).first()

    if not admin or not pwd_context.verify(data.password, admin.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not admin.is_active:
        raise HTTPException(status_code=401, detail="Account disabled")

    # Update last login
    admin.last_login = datetime.utcnow()
    db.commit()

    token = create_admin_token(admin.id, admin.username)
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": admin.username,
        "is_superadmin": admin.is_superadmin
    }


@router.post("/admin/create")
async def create_admin(
    data: AdminCreateRequest,
    db: Session = Depends(get_db)
):
    """Create new admin user (should be protected in production)"""
    # Check if admin already exists
    existing = db.query(AdminUser).filter(
        (AdminUser.username == data.username) | (AdminUser.email == data.email)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Username or email already exists")

    admin = AdminUser(
        username=data.username,
        email=data.email,
        hashed_password=pwd_context.hash(data.password),
        is_superadmin=data.is_superadmin
    )
    db.add(admin)
    db.commit()

    return {"status": "Admin created", "username": data.username}


# ==================== ADMIN DASHBOARD ENDPOINTS ====================

@router.get("/admin/dashboard/overview")
async def get_dashboard_overview(
    db: Session = Depends(get_db)
):
    """Get main dashboard overview stats"""
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Total visitors (all time)
    total_visitors = db.query(func.count(distinct(VisitorSession.visitor_id))).scalar() or 0

    # Today's visitors
    today_visitors = db.query(func.count(distinct(VisitorSession.visitor_id))).filter(
        cast(VisitorSession.created_at, Date) == today
    ).scalar() or 0

    # This week's visitors
    week_visitors = db.query(func.count(distinct(VisitorSession.visitor_id))).filter(
        cast(VisitorSession.created_at, Date) >= week_ago
    ).scalar() or 0

    # Total page views
    total_pageviews = db.query(func.count(PageView.id)).scalar() or 0

    # Total users (registered)
    total_users = db.query(func.count(User.id)).scalar() or 0

    # Total businesses
    total_businesses = db.query(func.count(Business.id)).scalar() or 0

    # Total bookings
    total_bookings = db.query(func.count(Booking.id)).scalar() or 0

    # Total revenue
    total_revenue = db.query(func.sum(Payment.amount)).filter(
        Payment.status == "completed"
    ).scalar() or 0

    # Returning vs new visitors
    returning_visitors = db.query(func.count(VisitorSession.id)).filter(
        VisitorSession.is_returning == True
    ).scalar() or 0

    new_visitors = db.query(func.count(VisitorSession.id)).filter(
        VisitorSession.is_returning == False
    ).scalar() or 0

    return {
        "visitors": {
            "total": total_visitors,
            "today": today_visitors,
            "this_week": week_visitors,
            "returning": returning_visitors,
            "new": new_visitors
        },
        "pageviews": {
            "total": total_pageviews
        },
        "users": {
            "total": total_users
        },
        "businesses": {
            "total": total_businesses
        },
        "bookings": {
            "total": total_bookings
        },
        "revenue": {
            "total": round(total_revenue, 2)
        }
    }


@router.get("/admin/dashboard/visitors-by-country")
async def get_visitors_by_country(
    db: Session = Depends(get_db)
):
    """Get visitor count by country"""
    results = db.query(
        VisitorSession.country,
        func.count(distinct(VisitorSession.visitor_id)).label("count")
    ).group_by(VisitorSession.country).order_by(desc("count")).limit(20).all()

    return [{"country": r.country or "Unknown", "count": r.count} for r in results]


@router.get("/admin/dashboard/top-pages")
async def get_top_pages(
    db: Session = Depends(get_db)
):
    """Get most visited pages"""
    results = db.query(
        PageView.page_path,
        func.count(PageView.id).label("views")
    ).group_by(PageView.page_path).order_by(desc("views")).limit(20).all()

    return [{"page": r.page_path, "views": r.views} for r in results]


@router.get("/admin/dashboard/click-stats")
async def get_click_stats(
    db: Session = Depends(get_db)
):
    """Get click statistics by element"""
    results = db.query(
        ClickEvent.element_text,
        ClickEvent.element_id,
        func.count(ClickEvent.id).label("clicks")
    ).group_by(ClickEvent.element_text, ClickEvent.element_id).order_by(desc("clicks")).limit(30).all()

    return [
        {
            "element": r.element_text or r.element_id or "Unknown",
            "clicks": r.clicks
        } for r in results
    ]


@router.get("/admin/dashboard/visitors-timeline")
async def get_visitors_timeline(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Get daily visitor counts for the last N days"""
    start_date = datetime.utcnow().date() - timedelta(days=days)

    results = db.query(
        cast(VisitorSession.created_at, Date).label("date"),
        func.count(distinct(VisitorSession.visitor_id)).label("visitors")
    ).filter(
        cast(VisitorSession.created_at, Date) >= start_date
    ).group_by(
        cast(VisitorSession.created_at, Date)
    ).order_by("date").all()

    return [
        {
            "date": str(r.date),
            "visitors": r.visitors
        } for r in results
    ]


@router.get("/admin/dashboard/device-stats")
async def get_device_stats(
    db: Session = Depends(get_db)
):
    """Get visitor device breakdown"""
    results = db.query(
        VisitorSession.device_type,
        func.count(VisitorSession.id).label("count")
    ).group_by(VisitorSession.device_type).all()

    return [{"device": r.device_type or "Unknown", "count": r.count} for r in results]


@router.get("/admin/dashboard/browser-stats")
async def get_browser_stats(
    db: Session = Depends(get_db)
):
    """Get visitor browser breakdown"""
    results = db.query(
        VisitorSession.browser,
        func.count(VisitorSession.id).label("count")
    ).group_by(VisitorSession.browser).all()

    return [{"browser": r.browser or "Unknown", "count": r.count} for r in results]


@router.get("/admin/dashboard/recent-sessions")
async def get_recent_sessions(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get recent visitor sessions"""
    sessions = db.query(VisitorSession).order_by(
        desc(VisitorSession.created_at)
    ).limit(limit).all()

    return [
        {
            "session_id": s.session_id,
            "visitor_id": s.visitor_id[:8] + "...",  # Truncate for privacy
            "ip_address": s.ip_address,
            "country": s.country,
            "city": s.city,
            "device": s.device_type,
            "browser": s.browser,
            "os": s.os,
            "landing_page": s.landing_page,
            "is_returning": s.is_returning,
            "created_at": s.created_at.isoformat() if s.created_at else None
        } for s in sessions
    ]


@router.get("/admin/dashboard/revenue-breakdown")
async def get_revenue_breakdown(
    db: Session = Depends(get_db)
):
    """Get revenue breakdown by business"""
    # Get payments with business info through bookings
    results = db.query(
        Business.name,
        Business.id,
        func.sum(Payment.amount).label("revenue"),
        func.count(Payment.id).label("transactions")
    ).join(
        Booking, Payment.booking_id == Booking.id
    ).join(
        # Join with service to get business
        Business, Booking.service_id.in_(
            db.query(Service.id).filter(Service.business_id == Business.id)
        )
    ).filter(
        Payment.status == "completed"
    ).group_by(Business.id, Business.name).order_by(desc("revenue")).all()

    # Fallback simpler query if above doesn't work well
    if not results:
        # Simple approach: just show total revenue
        total = db.query(func.sum(Payment.amount)).filter(Payment.status == "completed").scalar() or 0
        return [{"business": "All Businesses", "revenue": round(total, 2), "transactions": 0}]

    return [
        {
            "business": r.name,
            "business_id": r.id,
            "revenue": round(r.revenue, 2),
            "transactions": r.transactions
        } for r in results
    ]


@router.get("/admin/dashboard/users-list")
async def get_users_list(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get list of registered users"""
    users = db.query(User).order_by(desc(User.created_at)).offset(offset).limit(limit).all()
    total = db.query(func.count(User.id)).scalar() or 0

    return {
        "total": total,
        "users": [
            {
                "id": u.id,
                "email": u.email,
                "name": f"{u.first_name or ''} {u.last_name or ''}".strip(),
                "phone": u.phone_number,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "is_active": u.is_active
            } for u in users
        ]
    }


@router.get("/admin/dashboard/businesses-list")
async def get_businesses_list(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get list of businesses"""
    businesses = db.query(Business).order_by(desc(Business.id)).offset(offset).limit(limit).all()
    total = db.query(func.count(Business.id)).scalar() or 0

    return {
        "total": total,
        "businesses": [
            {
                "id": b.id,
                "name": b.name,
                "owner": b.owner_name,
                "email": b.email,
                "phone": b.phone,
                "city": b.city,
                "country": b.country,
                "category": b.category
            } for b in businesses
        ]
    }


# Need to import Service for revenue breakdown
from app.models.models import Service
