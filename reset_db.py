#!/usr/bin/env python3
"""
Database reset script - clears all data from tables
Run with: python reset_db.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    # Use local database connection for reset script
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker
    from app.models.models import User, Business, Service, Booking, FavoriteBarber

    # Local database connection for reset
    DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/barber_booking"
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    print("🔄 Connecting to database...")

    db = SessionLocal()
    try:
        # Delete all data in correct order (respecting foreign keys)
        print("🗑️  Deleting bookings...")
        db.execute(text('DELETE FROM bookings'))

        print("🗑️  Deleting favorite barbers...")
        db.execute(text('DELETE FROM favorite_barbers'))

        print("🗑️  Deleting services...")
        db.execute(text('DELETE FROM services'))

        print("🗑️  Deleting users...")
        db.execute(text('DELETE FROM users'))

        print("🗑️  Deleting businesses...")
        db.execute(text('DELETE FROM businesses'))

        db.commit()
        print("✅ Database reset completed successfully!")
        print("✅ All tables are now empty - ready for fresh signup!")

    except Exception as e:
        print(f"❌ Error during database reset: {e}")
        db.rollback()
    finally:
        db.close()

except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure you're running this from the booksy-backend directory")
    print("and that the virtual environment is activated")
except Exception as e:
    print(f"❌ Unexpected error: {e}")