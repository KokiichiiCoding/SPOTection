"""
Unit tests for API endpoints

WARNING: These tests currently hang due to Flask-SQLAlchemy fixture issues.
The app fixture in conftest.py attempts to rebind the database from PostgreSQL to
a test database, but SQLAlchemy's engine is already bound when flaskweb.app is imported.

Tests hang on database operations.

TODO: Refactor flaskweb/app.py to use application factory pattern for proper test isolation.
"""
import pytest
import json
from flaskweb.models import db, ParkingLot, Spot


class TestLotEndpoints:
    """Test parking lot API endpoints"""
    
    def test_get_lots(self, client, test_lot):
        """Test GET /api/lots"""
        response = client.get('/api/lots')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'lots' in data
        assert len(data['lots']) == 1
        assert data['lots'][0]['public_id'] == 'LOT-001'
        assert data['lots'][0]['name'] == 'Test Lot'
    
    def test_create_lot(self, client, test_lot):
        """Test POST /api/lots"""
        new_lot = {
            'lot_id': 'LOT-002',
            'name': 'New Test Lot',
            'total_spots': 5
        }
        
        response = client.post(
            '/api/lots',
            data=json.dumps(new_lot),
            content_type='application/json'
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['lot_id'] == 'LOT-002'
    
    def test_create_duplicate_lot(self, client, test_lot):
        """Test creating lot with duplicate ID"""
        duplicate_lot = {
            'lot_id': 'LOT-001',
            'name': 'Duplicate',
            'total_spots': 5
        }
        
        response = client.post(
            '/api/lots',
            data=json.dumps(duplicate_lot),
            content_type='application/json'
        )
        assert response.status_code == 400


class TestCameraEndpoints:
    """Test camera API endpoints"""
    
    def test_get_lot_camera(self, client, test_lot):
        """Test GET /api/lot/<lot_id>/camera"""
        response = client.get('/api/lot/LOT-001/camera')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['lot_id'] == 'LOT-001'
        assert 'camera_url' in data
        assert 'camera_type' in data
    
    def test_update_lot_camera(self, client, test_lot):
        """Test PUT /api/lot/<lot_id>/camera"""
        camera_config = {
            'camera_url': 'http://newcamera.com/feed',
            'camera_type': 'rtsp'
        }
        
        response = client.put(
            '/api/lot/LOT-001/camera',
            data=json.dumps(camera_config),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['camera_url'] == camera_config['camera_url']
        assert data['camera_type'] == camera_config['camera_type']
    
    def test_get_nonexistent_lot_camera(self, client, test_lot):
        """Test getting camera for non-existent lot"""
        response = client.get('/api/lot/NONEXISTENT/camera')
        assert response.status_code == 404


class TestCalibrationEndpoints:
    """Test calibration API endpoints"""
    
    def test_get_calibration(self, client, app, test_lot):
        """Test GET /api/lot/<lot_id>/calibration"""
        with app.app_context():
            # Save test calibration data
            from flaskweb.app import main_config
            test_calibration = [
                {
                    'id': 'SPACE-001',
                    'polygon': [
                        {'x': 0.1, 'y': 0.1},
                        {'x': 0.2, 'y': 0.1},
                        {'x': 0.2, 'y': 0.2},
                        {'x': 0.1, 'y': 0.2}
                    ]
                }
            ]
            main_config['calibration_data_LOT-001'] = test_calibration
        
        response = client.get('/api/lot/LOT-001/calibration')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'spaces' in data
        assert len(data['spaces']) == 1
        assert data['spaces'][0]['id'] == 'SPACE-001'
    
    def test_save_calibration(self, client, test_lot):
        """Test POST /api/lot/<lot_id>/calibration"""
        calibration_data = {
            'spaces': [
                {
                    'id': 'SPACE-001',
                    'polygon': [
                        {'x': 0.1, 'y': 0.1},
                        {'x': 0.2, 'y': 0.1},
                        {'x': 0.2, 'y': 0.2},
                        {'x': 0.1, 'y': 0.2}
                    ]
                }
            ]
        }
        
        response = client.post(
            '/api/lot/LOT-001/calibration',
            data=json.dumps(calibration_data),
            content_type='application/json'
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True


class TestStatusEndpoints:
    """Test parking status API endpoints"""
    
    def test_get_lot_status(self, client, test_lot):
        """Test GET /api/lot/<lot_id>/status"""
        response = client.get('/api/lot/LOT-001/status')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'lot_id' in data
        assert 'total_spaces' in data
        assert 'free_spaces' in data
        assert 'occupied_spaces' in data
        assert 'spots' in data
    
    def test_get_detection_overlay(self, client, test_lot):
        """Test GET /api/lot/<lot_id>/detection/overlay"""
        response = client.get('/api/lot/LOT-001/detection/overlay')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'spots' in data
        assert 'timestamp' in data
        assert 'has_calibration' in data


class TestDetectionEndpoints:
    """Test detection control API endpoints"""
    
    def test_detection_status(self, client):
        """Test GET /api/detection/status"""
        response = client.get('/api/detection/status')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'running' in data
        assert 'available' in data
        assert 'model_loaded' in data
        assert 'camera_available' in data
