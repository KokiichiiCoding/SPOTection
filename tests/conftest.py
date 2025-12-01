"""
Pytest configuration and shared fixtures
"""
import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set testing environment variable BEFORE importing app
os.environ['TESTING'] = 'true'

import pytest


@pytest.fixture(scope='function')
def app():
    """Create test Flask app with test PostgreSQL database"""
    # Import app from flaskweb - db is already initialized
    from flaskweb.app import app as flask_app
    from flaskweb import models
    
    # Store original database URI
    original_uri = flask_app.config.get('SQLALCHEMY_DATABASE_URI')
    
    # Use a separate test database to avoid affecting production
    test_db_uri = 'postgresql://spotection_client:password123@localhost:5432/parking_db_test'
    
    # Configure for testing
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = test_db_uri
    flask_app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Push app context manually
    ctx = flask_app.app_context()
    ctx.push()
    
    try:
        # CRITICAL: Dispose the old engine so it reconnects with new URI
        models.db.engine.dispose()
        
        # Create test database tables (won't affect production parking_db)
        models.db.create_all()
        
        yield flask_app
        
        # Cleanup: Drop all test tables after test completes
        models.db.session.remove()
        models.db.drop_all()
        
        # Dispose test engine
        models.db.engine.dispose()
    finally:
        # Pop app context
        ctx.pop()
        
        # Restore original URI
        flask_app.config['SQLALCHEMY_DATABASE_URI'] = original_uri


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def test_lot(app):
    """Create a test parking lot"""
    from flaskweb.models import db, ParkingLot, Spot
    
    with app.app_context():
        lot = ParkingLot(
            public_id='LOT-001',
            name='Test Lot',
            total_spots=3,
            camera_url='http://test.com/camera',
            camera_type='http_mjpeg'
        )
        db.session.add(lot)
        db.session.commit()
        
        # Create test spots
        for i in range(1, 4):
            spot = Spot(lot_id=lot.id, spot_id=f'SPACE-{i:03d}')
            db.session.add(spot)
        db.session.commit()
        
        yield lot
        
        # Cleanup
        db.session.query(Spot).filter_by(lot_id=lot.id).delete()
        db.session.delete(lot)
        db.session.commit()
