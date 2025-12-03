"""
Database Manager
Handles all database operations including initialization, migrations, and schema management
"""

import sys
import os
from typing import Optional, Dict, Any
from sqlalchemy.exc import OperationalError, ProgrammingError


class DatabaseManager:
    """Manages database operations"""
    
    def __init__(self, database_uri: str):
        self.database_uri = database_uri
        self._app = None
        self._db = None
    
    def initialize_app(self):
        """Initialize Flask app and database context"""
        # Ensure we can import Flask and models
        sys.path.insert(0, os.getcwd())
        
        from flask import Flask
        from flaskweb.models import db
        
        self._app = Flask(__name__)
        self._app.config['SQLALCHEMY_DATABASE_URI'] = self.database_uri
        self._app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        db.init_app(self._app)
        self._db = db
        
        return self._app
    
    def test_connection(self) -> tuple[bool, Optional[str]]:
        """Test database connection"""
        if not self._app:
            self.initialize_app()
        
        try:
            with self._app.app_context():
                # Try a simple query
                self._db.session.execute(self._db.text('SELECT 1'))
            return True, None
        except OperationalError as e:
            error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            return False, error_msg
        except Exception as e:
            return False, str(e)
    
    def create_all_tables(self) -> tuple[bool, Optional[str]]:
        """Create all database tables"""
        if not self._app:
            self.initialize_app()
        
        try:
            with self._app.app_context():
                self._db.create_all()
            return True, None
        except Exception as e:
            return False, str(e)
    
    def drop_all_tables(self) -> tuple[bool, Optional[str]]:
        """Drop all database tables (use with caution!)"""
        if not self._app:
            self.initialize_app()
        
        try:
            with self._app.app_context():
                self._db.drop_all()
            return True, None
        except Exception as e:
            return False, str(e)
    
    def create_default_lot(self, lot_id: str = 'LOT-001', lot_name: str = 'Default Parking Lot') -> tuple[bool, Optional[str]]:
        """Create default parking lot"""
        if not self._app:
            self.initialize_app()
        
        try:
            with self._app.app_context():
                from flaskweb.models import ParkingLot
                
                # Check if lot already exists
                existing_lot = ParkingLot.query.filter_by(public_id=lot_id).first()
                
                if existing_lot:
                    return True, f"Lot {lot_id} already exists"
                
                # Create new lot
                new_lot = ParkingLot(
                    public_id=lot_id,
                    name=lot_name,
                    total_spots=0
                )
                self._db.session.add(new_lot)
                self._db.session.commit()
                
                return True, f"Created lot {lot_id}"
        except Exception as e:
            return False, str(e)
    
    def get_schema_version(self) -> Optional[str]:
        """Get current database schema version"""
        if not self._app:
            self.initialize_app()
        
        try:
            with self._app.app_context():
                # Check if schema_version table exists
                result = self._db.session.execute(
                    self._db.text(
                        "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
                    )
                )
                row = result.fetchone()
                return row[0] if row else None
        except (OperationalError, ProgrammingError):
            # Table doesn't exist, this is a fresh install
            return None
        except Exception:
            return None
    
    def set_schema_version(self, version: str) -> bool:
        """Set schema version"""
        if not self._app:
            self.initialize_app()
        
        try:
            with self._app.app_context():
                # Create schema_version table if it doesn't exist
                self._db.session.execute(self._db.text("""
                    CREATE TABLE IF NOT EXISTS schema_version (
                        id SERIAL PRIMARY KEY,
                        version VARCHAR(50) NOT NULL,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                
                # Insert new version
                self._db.session.execute(
                    self._db.text("INSERT INTO schema_version (version) VALUES (:version)"),
                    {"version": version}
                )
                self._db.session.commit()
                return True
        except Exception as e:
            print(f"Error setting schema version: {e}")
            return False
    
    def get_table_list(self) -> list[str]:
        """Get list of all tables in the database"""
        if not self._app:
            self.initialize_app()
        
        try:
            with self._app.app_context():
                result = self._db.session.execute(self._db.text("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public'
                """))
                return [row[0] for row in result.fetchall()]
        except Exception:
            return []
    
    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get information about a specific table"""
        if not self._app:
            self.initialize_app()
        
        try:
            with self._app.app_context():
                # Get column information
                result = self._db.session.execute(self._db.text("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = :table_name
                    ORDER BY ordinal_position
                """), {"table_name": table_name})
                
                columns = []
                for row in result.fetchall():
                    columns.append({
                        'name': row[0],
                        'type': row[1],
                        'nullable': row[2] == 'YES',
                        'default': row[3]
                    })
                
                # Get row count
                count_result = self._db.session.execute(
                    self._db.text(f"SELECT COUNT(*) FROM {table_name}")
                )
                row_count = count_result.fetchone()[0]
                
                return {
                    'table_name': table_name,
                    'columns': columns,
                    'row_count': row_count
                }
        except Exception as e:
            return {
                'table_name': table_name,
                'error': str(e)
            }
    
    def backup_data(self, output_file: str) -> tuple[bool, Optional[str]]:
        """Backup database data to JSON file"""
        if not self._app:
            self.initialize_app()
        
        try:
            with self._app.app_context():
                from flaskweb.models import ParkingLot, Spot, StatusUpdate
                
                backup_data = {
                    'lots': [],
                    'spots': [],
                    'status_updates': []
                }
                
                # Backup parking lots
                for lot in ParkingLot.query.all():
                    backup_data['lots'].append({
                        'public_id': lot.public_id,
                        'name': lot.name,
                        'total_spots': lot.total_spots,
                        'camera_url': lot.camera_url,
                        'camera_type': lot.camera_type
                    })
                
                # Backup spots
                for spot in Spot.query.all():
                    backup_data['spots'].append({
                        'spot_id': spot.spot_id,
                        'lot_public_id': spot.lot.public_id
                    })
                
                # Backup recent status updates (last 1000)
                for update in StatusUpdate.query.order_by(StatusUpdate.timestamp.desc()).limit(1000):
                    backup_data['status_updates'].append({
                        'spot_id': update.spot.spot_id,
                        'status': update.status,
                        'confidence': update.confidence,
                        'timestamp': update.timestamp.isoformat(),
                        'vehicle_data': update.vehicle_data
                    })
                
                import json
                with open(output_file, 'w') as f:
                    json.dump(backup_data, f, indent=2)
                
                return True, f"Backup saved to {output_file}"
        except Exception as e:
            return False, str(e)
