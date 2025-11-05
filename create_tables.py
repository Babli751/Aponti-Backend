#!/usr/bin/env python3
"""
Create database tables script
Run with: python create_tables.py
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import engine
from app.models import models

print("🔄 Creating database tables...")
try:
    models.Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")
except Exception as e:
    print(f"❌ Error creating tables: {e}")
    sys.exit(1)