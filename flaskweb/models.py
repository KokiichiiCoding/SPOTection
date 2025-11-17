from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Index, JSON, TypeDecorator
from datetime import datetime, timezone

db = SQLAlchemy()

class JSONType(TypeDecorator):
    """Platform-independent JSON type that uses JSONB for PostgreSQL and JSON for SQLite"""
    impl = JSON
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())

class ParkingLot(db.Model):
    """Represents a physical lot."""
    __tablename__ = 'parking_lot'

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255))
    total_spots = db.Column(db.Integer)
    camera_url = db.Column(db.String(500), nullable=True)  # Camera feed URL for this lot
    camera_type = db.Column(db.String(50), nullable=True)  # Camera type (http_snapshot, rtsp, etc.)

    spots = db.relationship('Spot', back_populates='lot')

class Spot(db.Model):
    """Represents a single physical spot in a lot."""
    __tablename__ = 'spot'

    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.String(50), nullable=False)

    # Foreign key to link a spot to a parking lot
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)

    # Links to ParkingLot object
    lot = db.relationship('ParkingLot', back_populates='spots')

    # Lists historic statuses for this specific spot
    status_updates = db.relationship('StatusUpdate', back_populates='spot', lazy='dynamic') # lazy set to dynamic since it's apparently good for large histories

    __table_args__ = (db.UniqueConstraint('lot_id', 'spot_id', name='_lot_spot_uc'),)

class StatusUpdate(db.Model):
    """A log entry for every update to a spot's status"""
    __tablename__ = 'status_update'
    
    id = db.Column(db.Integer, primary_key=True)

    # Foreign key to link to a specific spot
    spot_id = db.Column(db.Integer, db.ForeignKey('spot.id'), nullable=False)

    # General data for the spot
    status = db.Column(db.String(20), nullable=False) # 'free' or 'occupied'
    confidence = db.Column(db.Float) # The confidence rating (IoU overlap ratio)
    timestamp = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Even stores what vehicle was present because why not
    vehicle_data = db.Column(JSONType)

    # Image path
    image_url = db.Column(db.String(1024))

    # Links back to the spot object
    spot = db.relationship('Spot', back_populates='status_updates')

# Index for the timestamp column as it will definitely be queried heavily
Index('ix_status_update_timestamp', StatusUpdate.timestamp)
