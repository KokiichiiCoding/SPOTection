"""  
Unit tests for database models

WARNING: These tests currently hang due to Flask-SQLAlchemy fixture issues.
The app fixture in conftest.py attempts to rebind the database from PostgreSQL to
a test database, but SQLAlchemy's engine is already bound when flaskweb.app is imported.

Tests hang on db.session.commit() operations.

TODO: Refactor flaskweb/app.py to use application factory pattern for proper test isolation.
"""
import pytest
from datetime import datetime
from flaskweb.models import db, ParkingLot, Spot, StatusUpdate


class TestParkingLotModel:
    """Test ParkingLot model"""
    
    def test_create_parking_lot(self, app):
        """Test creating a parking lot"""
        with app.app_context():
            lot = ParkingLot(
                public_id='TEST-001',
                name='Test Lot',
                total_spots=10,
                camera_url='http://test.com/camera',
                camera_type='http_mjpeg'
            )
            db.session.add(lot)
            db.session.commit()
            
            assert lot.id is not None
            assert lot.public_id == 'TEST-001'
            assert lot.name == 'Test Lot'
            assert lot.total_spots == 10
    
    def test_lot_spots_relationship(self, app):
        """Test relationship between lot and spots"""
        with app.app_context():
            lot = ParkingLot(public_id='TEST-001', name='Test Lot', total_spots=2)
            db.session.add(lot)
            db.session.commit()
            
            spot1 = Spot(lot_id=lot.id, spot_id='SPACE-001')
            spot2 = Spot(lot_id=lot.id, spot_id='SPACE-002')
            db.session.add_all([spot1, spot2])
            db.session.commit()
            
            assert len(lot.spots) == 2
            assert spot1 in lot.spots
            assert spot2 in lot.spots


class TestSpotModel:
    """Test Spot model"""
    
    def test_create_spot(self, app):
        """Test creating a parking spot"""
        with app.app_context():
            lot = ParkingLot(public_id='TEST-001', name='Test Lot', total_spots=1)
            db.session.add(lot)
            db.session.commit()
            
            spot = Spot(lot_id=lot.id, spot_id='SPACE-001')
            db.session.add(spot)
            db.session.commit()
            
            assert spot.id is not None
            assert spot.spot_id == 'SPACE-001'
            assert spot.lot_id == lot.id
    
    def test_spot_status_relationship(self, app):
        """Test relationship between spot and status updates"""
        with app.app_context():
            lot = ParkingLot(public_id='TEST-001', name='Test Lot', total_spots=1)
            spot = Spot(lot_id=1, spot_id='SPACE-001')
            db.session.add_all([lot, spot])
            db.session.commit()
            
            status = StatusUpdate(
                spot_id=spot.id,
                status='occupied',
                confidence=0.95,
                vehicle_data={'class': 'car', 'confidence': 0.95}
            )
            db.session.add(status)
            db.session.commit()
            
            # status_updates is lazy='dynamic', so it's a query object
            assert spot.status_updates.count() == 1
            assert spot.status_updates.first().status == 'occupied'


class TestStatusUpdateModel:
    """Test StatusUpdate model"""
    
    def test_create_status_update(self, app):
        """Test creating a status update"""
        with app.app_context():
            lot = ParkingLot(public_id='TEST-001', name='Test Lot', total_spots=1)
            spot = Spot(lot_id=1, spot_id='SPACE-001')
            db.session.add_all([lot, spot])
            db.session.commit()
            
            status = StatusUpdate(
                spot_id=spot.id,
                status='free',
                confidence=1.0,
                vehicle_data=None
            )
            db.session.add(status)
            db.session.commit()
            
            assert status.id is not None
            assert status.status == 'free'
            assert status.confidence == 1.0
            assert status.vehicle_data is None
            assert status.timestamp is not None
    
    def test_vehicle_data_json(self, app):
        """Test vehicle_data JSONB field"""
        with app.app_context():
            lot = ParkingLot(public_id='TEST-001', name='Test Lot', total_spots=1)
            spot = Spot(lot_id=1, spot_id='SPACE-001')
            db.session.add_all([lot, spot])
            db.session.commit()
            
            vehicle_info = {
                'class': 'truck',
                'confidence': 0.87,
                'color': 'blue',
                'uncertain': False
            }
            
            status = StatusUpdate(
                spot_id=spot.id,
                status='occupied',
                confidence=0.87,
                vehicle_data=vehicle_info
            )
            db.session.add(status)
            db.session.commit()
            
            retrieved = StatusUpdate.query.get(status.id)
            assert retrieved.vehicle_data == vehicle_info
            assert retrieved.vehicle_data['class'] == 'truck'
