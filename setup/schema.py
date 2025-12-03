"""
Database Schema Management
Defines database schema versions and migrations
"""

from typing import List, Dict, Callable, Optional


# Current schema version
CURRENT_SCHEMA_VERSION = "1.4.0"


class Migration:
    """Represents a database migration"""
    
    def __init__(self, version: str, description: str, 
                 upgrade_func: Callable, downgrade_func: Optional[Callable] = None):
        self.version = version
        self.description = description
        self.upgrade = upgrade_func
        self.downgrade = downgrade_func


def migration_1_0_0_initial(db, app_context):
    """Initial schema creation"""
    with app_context:
        db.create_all()
        print("Created initial schema (parking_lot, spot, status_update)")


def migration_1_1_0_add_camera_fields(db, app_context):
    """Add camera configuration fields to parking_lot table"""
    with app_context:
        db.session.execute(db.text("""
            ALTER TABLE parking_lot
            ADD COLUMN IF NOT EXISTS camera_url VARCHAR(500),
            ADD COLUMN IF NOT EXISTS camera_type VARCHAR(50),
            ADD COLUMN IF NOT EXISTS extraction_pattern_type VARCHAR(50),
            ADD COLUMN IF NOT EXISTS extraction_pattern_value VARCHAR(200)
        """))
        db.session.commit()
        print("Added camera configuration fields")


def migration_1_2_0_add_indexes(db, app_context):
    """Add performance indexes"""
    with app_context:
        db.session.execute(db.text("""
            CREATE INDEX IF NOT EXISTS ix_parking_lot_public_id 
            ON parking_lot(public_id);
            
            CREATE INDEX IF NOT EXISTS ix_spot_lot_id 
            ON spot(lot_id);
            
            CREATE INDEX IF NOT EXISTS ix_status_update_spot_id 
            ON status_update(spot_id);
            
            CREATE INDEX IF NOT EXISTS ix_status_update_timestamp 
            ON status_update(timestamp DESC);
        """))
        db.session.commit()
        print("Added performance indexes")


def migration_1_3_0_add_analytics_table(db, app_context):
    """Add analytics summary table for faster reporting"""
    with app_context:
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS analytics_summary (
                id SERIAL PRIMARY KEY,
                lot_id INTEGER REFERENCES parking_lot(id),
                date DATE NOT NULL,
                hour INTEGER NOT NULL,
                avg_occupancy FLOAT,
                peak_occupancy INTEGER,
                total_vehicles INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lot_id, date, hour)
            );
            
            CREATE INDEX IF NOT EXISTS ix_analytics_summary_lot_date 
            ON analytics_summary(lot_id, date);
        """))
        db.session.commit()
        print("Added analytics_summary table")


def migration_1_4_0_add_media_storage(db, app_context):
    """Add media storage table for screenshots/video footage archive"""
    with app_context:
        db.session.execute(db.text("""
            CREATE TABLE IF NOT EXISTS media_storage (
                id SERIAL PRIMARY KEY,
                lot_id INTEGER REFERENCES parking_lot(id),
                media_type VARCHAR(20) NOT NULL,
                file_path VARCHAR(500) NOT NULL,
                file_size BIGINT NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                duration INTEGER,
                frame_count INTEGER,
                resolution VARCHAR(20),
                metadata JSONB,
                thumbnail_path VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (media_type IN ('image', 'video'))
            );
            
            CREATE INDEX IF NOT EXISTS ix_media_storage_lot_timestamp 
            ON media_storage(lot_id, timestamp DESC);
            
            CREATE INDEX IF NOT EXISTS ix_media_storage_timestamp 
            ON media_storage(timestamp DESC);
            
            CREATE TABLE IF NOT EXISTS media_storage_stats (
                id SERIAL PRIMARY KEY,
                total_size BIGINT DEFAULT 0,
                image_count INTEGER DEFAULT 0,
                video_count INTEGER DEFAULT 0,
                oldest_media_timestamp TIMESTAMP,
                newest_media_timestamp TIMESTAMP,
                last_cleanup TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            INSERT INTO media_storage_stats (total_size, image_count, video_count)
            VALUES (0, 0, 0)
            ON CONFLICT DO NOTHING;
        """))
        db.session.commit()
        print("Added media_storage and media_storage_stats tables")



# Define all migrations in order
MIGRATIONS: List[Migration] = [
    Migration(
        version="1.0.0",
        description="Initial schema",
        upgrade_func=migration_1_0_0_initial
    ),
    Migration(
        version="1.1.0",
        description="Add camera configuration fields",
        upgrade_func=migration_1_1_0_add_camera_fields
    ),
    Migration(
        version="1.2.0",
        description="Add performance indexes",
        upgrade_func=migration_1_2_0_add_indexes
    ),
    Migration(
        version="1.3.0",
        description="Add analytics summary table",
        upgrade_func=migration_1_3_0_add_analytics_table
    ),
    Migration(
        version="1.4.0",
        description="Add media storage tables for screenshots/video archive",
        upgrade_func=migration_1_4_0_add_media_storage
    )
]


def get_schema_version() -> str:
    """Get the current schema version"""
    return CURRENT_SCHEMA_VERSION


def get_migrations_to_apply(current_version: Optional[str]) -> List[Migration]:
    """Get list of migrations that need to be applied"""
    if current_version is None:
        # Fresh install, apply all migrations
        return MIGRATIONS
    
    # Find migrations newer than current version
    migrations_to_apply = []
    found_current = False
    
    for migration in MIGRATIONS:
        if found_current:
            migrations_to_apply.append(migration)
        elif migration.version == current_version:
            found_current = True
    
    return migrations_to_apply


def apply_migrations(db_manager) -> tuple[bool, List[str]]:
    """Apply all pending migrations"""
    from setup.db_manager import DatabaseManager
    
    messages = []
    
    try:
        # Get current schema version
        current_version = db_manager.get_schema_version()
        
        if current_version:
            messages.append(f"Current schema version: {current_version}")
        else:
            messages.append("No schema version found (fresh install)")
        
        # Get migrations to apply
        migrations_to_apply = get_migrations_to_apply(current_version)
        
        if not migrations_to_apply:
            messages.append("Schema is up to date")
            return True, messages
        
        messages.append(f"Applying {len(migrations_to_apply)} migration(s)...")
        
        # Apply each migration
        app = db_manager._app
        if not app:
            app = db_manager.initialize_app()
        
        db = db_manager._db
        
        for migration in migrations_to_apply:
            messages.append(f"Applying {migration.version}: {migration.description}")
            
            try:
                migration.upgrade(db, app.app_context())
                
                # Update schema version
                db_manager.set_schema_version(migration.version)
                
                messages.append(f"✓ Applied {migration.version}")
            except Exception as e:
                messages.append(f"✗ Failed to apply {migration.version}: {e}")
                return False, messages
        
        messages.append("All migrations applied successfully")
        return True, messages
        
    except Exception as e:
        messages.append(f"Error applying migrations: {e}")
        return False, messages


def get_migration_info() -> List[Dict[str, str]]:
    """Get information about all available migrations"""
    return [
        {
            'version': m.version,
            'description': m.description,
            'has_downgrade': m.downgrade is not None
        }
        for m in MIGRATIONS
    ]
