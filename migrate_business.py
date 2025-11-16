#!/usr/bin/env python3
"""Migration script to add missing columns to businesses table"""
import sqlite3
import os

# Database path
DB_PATH = "barber_booking.db"

def migrate():
    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check existing columns
    cursor.execute("PRAGMA table_info(businesses)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    print(f"Existing columns: {existing_columns}")

    # Columns to add
    columns_to_add = [
        ("country", "VARCHAR"),
        ("category", "VARCHAR"),
        ("latitude", "REAL"),
        ("longitude", "REAL"),
        ("avatar_url", "VARCHAR"),
        ("cover_photo_url", "VARCHAR")
    ]

    # Add missing columns
    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            try:
                print(f"Adding column: {col_name} ({col_type})")
                cursor.execute(f"ALTER TABLE businesses ADD COLUMN {col_name} {col_type}")
                print(f"✅ Added {col_name}")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Error adding {col_name}: {e}")
        else:
            print(f"✓ Column {col_name} already exists")

    conn.commit()

    # Verify
    cursor.execute("PRAGMA table_info(businesses)")
    final_columns = [row[1] for row in cursor.fetchall()]
    print(f"\nFinal columns: {final_columns}")

    conn.close()
    print("\n✅ Migration complete!")

if __name__ == "__main__":
    migrate()
