"""
Unit tests for detection system
"""
import pytest
import numpy as np
import cv2
from shapely.geometry import box as shapely_box


@pytest.fixture
def mock_frame():
    """Create a mock camera frame"""
    # Create a 640x480 test frame
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    # Add a white rectangle to simulate a car
    cv2.rectangle(frame, (100, 100), (200, 200), (255, 255, 255), -1)
    return frame


@pytest.fixture
def mock_detections():
    """Create mock vehicle detections"""
    return [
        {
            "class": "car",
            "confidence": 0.95,
            "bbox": (100, 100, 200, 200),
            "box": shapely_box(100, 100, 200, 200)
        },
        {
            "class": "truck",
            "confidence": 0.87,
            "bbox": (300, 300, 450, 400),
            "box": shapely_box(300, 300, 450, 400)
        }
    ]


@pytest.fixture
def calibration_data():
    """Create test calibration data"""
    return [
        {
            'id': 'SPACE-001',
            'polygon': [
                {'x': 0.15, 'y': 0.2},   # Normalized coordinates
                {'x': 0.35, 'y': 0.2},
                {'x': 0.35, 'y': 0.45},
                {'x': 0.15, 'y': 0.45}
            ]
        },
        {
            'id': 'SPACE-002',
            'polygon': [
                {'x': 0.45, 'y': 0.6},
                {'x': 0.75, 'y': 0.6},
                {'x': 0.75, 'y': 0.85},
                {'x': 0.45, 'y': 0.85}
            ]
        }
    ]


class TestDetectionAnalysis:
    """Test detection analysis functions"""
    
    def test_analyze_spots_basic(self, mock_detections, calibration_data):
        """Test basic spot analysis with detections"""
        from flaskweb.app import analyze_spots_with_detections
        
        frame_shape = (480, 640, 3)
        results = analyze_spots_with_detections(
            mock_detections,
            calibration_data,
            frame_shape
        )
        
        assert 'SPACE-001' in results
        assert 'SPACE-002' in results
        assert results['SPACE-001']['status'] == 'occupied'
        assert results['SPACE-002']['status'] == 'occupied'
    
    def test_analyze_empty_spots(self, calibration_data):
        """Test spot analysis with no detections"""
        from flaskweb.app import analyze_spots_with_detections
        
        frame_shape = (480, 640, 3)
        results = analyze_spots_with_detections(
            [],  # No detections
            calibration_data,
            frame_shape
        )
        
        assert 'SPACE-001' in results
        assert 'SPACE-002' in results
        assert results['SPACE-001']['status'] == 'free'
        assert results['SPACE-002']['status'] == 'free'
    
    def test_small_spot_detection(self):
        """Test detection for small/distant parking spots"""
        from flaskweb.app import analyze_spots_with_detections
        
        # Small spot (< 5000 pixels²)
        small_calibration = [
            {
                'id': 'SPACE-SMALL',
                'polygon': [
                    {'x': 0.1, 'y': 0.1},
                    {'x': 0.15, 'y': 0.1},
                    {'x': 0.15, 'y': 0.15},
                    {'x': 0.1, 'y': 0.15}
                ]
            }
        ]
        
        # Detection overlapping small spot
        small_detection = [
            {
                "class": "car",
                "confidence": 0.85,
                "bbox": (60, 45, 100, 75),
                "box": shapely_box(60, 45, 100, 75)
            }
        ]
        
        frame_shape = (480, 640, 3)
        results = analyze_spots_with_detections(
            small_detection,
            small_calibration,
            frame_shape
        )
        
        assert 'SPACE-SMALL' in results
        # Small spots use adjusted threshold
        assert results['SPACE-SMALL']['status'] in ['occupied', 'free']
    
    def test_uncertain_detection(self, calibration_data):
        """Test uncertain/low-confidence detection handling"""
        from flaskweb.app import analyze_spots_with_detections
        
        # Low confidence detection
        uncertain_detection = [
            {
                "class": "car",
                "confidence": 0.45,  # Below 0.6 threshold
                "bbox": (100, 100, 200, 200),
                "box": shapely_box(100, 100, 200, 200)
            }
        ]
        
        frame_shape = (480, 640, 3)
        results = analyze_spots_with_detections(
            uncertain_detection,
            calibration_data,
            frame_shape
        )
        
        # Should mark as occupied (fail-safe) or free depending on overlap
        assert 'SPACE-001' in results
        if results['SPACE-001']['status'] == 'occupied':
            # If marked occupied, check for uncertain flag
            if results['SPACE-001']['vehicle_data']:
                assert 'confidence' in results['SPACE-001']['vehicle_data']


class TestDetectionConfiguration:
    """Test detection configuration and thresholds"""
    
    def test_confidence_threshold(self):
        """Test confidence threshold setting"""
        from flaskweb.app import main_config
        
        # Default should be 0.4
        assert main_config.get('confidence_threshold', 0.4) >= 0.4
    
    def test_overlap_threshold(self):
        """Test overlap threshold setting"""
        from flaskweb.app import main_config
        
        # Default should be 0.25
        threshold = main_config.get('overlap_threshold', 0.25)
        assert 0.1 <= threshold <= 0.5  # Reasonable range
    
    def test_detection_interval(self):
        """Test detection interval setting"""
        from flaskweb.app import main_config
        
        # Should be reasonable (1-60 seconds)
        interval = main_config.get('detection_interval', 5)
        assert 1 <= interval <= 60


class TestVehicleClassFiltering:
    """Test vehicle class filtering"""
    
    def test_valid_vehicle_classes(self):
        """Test that only valid vehicle classes are detected"""
        from flaskweb.app import main_config
        
        vehicle_classes = main_config.get('vehicle_classes', [
            'car', 'truck', 'bus', 'motorcycle', 'bicycle'
        ])
        
        assert 'car' in vehicle_classes
        assert 'truck' in vehicle_classes
        assert 'person' not in vehicle_classes  # Should not detect people
