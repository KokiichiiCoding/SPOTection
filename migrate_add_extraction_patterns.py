"""
Migration script to add extraction pattern fields to ParkingLot table
Run this once to update your existing database schema

Usage: 
    Activate your virtual environment first, then run:
    python migrate_add_extraction_patterns.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

print("🔄 Starting database migration...")
print("📦 Importing modules...")

try:
    from flaskweb.app import app, db
    from flaskweb.models import ParkingLot
    print("✓ Modules imported successfully")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\n⚠️  Make sure you:")
    print("   1. Activated your virtual environment")
    print("   2. Installed all requirements (pip install -r requirements.txt)")
    sys.exit(1)

def migrate():
    """Add extraction pattern columns to parking_lot table"""
    with app.app_context():
        try:
            # Check if columns already exist
            inspector = db.inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('parking_lot')]
            
            print(f"📋 Current columns: {', '.join(columns)}")
            
            if 'extraction_pattern_type' in columns and 'extraction_pattern_value' in columns:
                print("✓ Extraction pattern columns already exist - no migration needed")
                return
            
            print("📝 Adding extraction pattern columns to parking_lot table...")
            
            # Add columns using raw SQL
            with db.engine.connect() as conn:
                if 'extraction_pattern_type' not in columns:
                    conn.execute(db.text(
                        "ALTER TABLE parking_lot ADD COLUMN extraction_pattern_type VARCHAR(50)"
                    ))
                    conn.commit()
                    print("✓ Added extraction_pattern_type column")
                
                if 'extraction_pattern_value' not in columns:
                    conn.execute(db.text(
                        "ALTER TABLE parking_lot ADD COLUMN extraction_pattern_value VARCHAR(200)"
                    ))
                    conn.commit()
                    print("✓ Added extraction_pattern_value column")
            
            print("✅ Migration completed successfully!")
            print("\n📌 You can now use custom extraction patterns in the Admin panel")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    migrate()
