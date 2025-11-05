# Minimal, robust settings loader compatible with both Pydantic v1/v2 or no pydantic at all.
# Avoids runtime import errors on servers where pydantic versions differ.
import os

class Settings:
    # API and security
    API_V1_STR = "/api/v1"
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7)))  # 1 week

    # Admin reset key (optional; if not set, admin endpoint will also accept SECRET_KEY)
    ADMIN_RESET_KEY = os.getenv("ADMIN_RESET_KEY", "disabled")

    # Database URL - Use SQLite for simplicity
    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "sqlite:///./barber_booking.db"
    )

# Export settings singleton
settings = Settings()
