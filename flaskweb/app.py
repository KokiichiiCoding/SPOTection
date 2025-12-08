from flask import Flask, render_template, jsonify, request, send_from_directory, session, redirect, url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import sys
import os
from functools import wraps
import secrets

# Suppress PyTorch NNPACK warnings on unsupported hardware
os.environ['PYTORCH_DISABLE_NNPACK'] = '1'
# Also suppress other common PyTorch warnings
import warnings
warnings.filterwarnings('ignore', message='.*NNPACK.*')
warnings.filterwarnings('ignore', message='.*Unsupported hardware.*')

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flaskweb.models import db, ParkingLot, Spot, StatusUpdate
import json
from datetime import datetime, timezone
from pathlib import Path
import threading
import time
import logging
import random
import traceback
import numpy as np
from shapely.geometry import Polygon, box as shapely_box

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import camera manager
from flaskweb.camera_manager import create_camera_feed

# Import media storage manager
from flaskweb.media_storage import MediaStorageManager

# Import YOLO for detection
try:
    from ultralytics import YOLO
    import cv2
    DETECTION_AVAILABLE = True
    logger.info("✓ Detection libraries available")
except ImportError:
    DETECTION_AVAILABLE = False
    logger.warning("⚠ YOLO/CV2 not available - detection disabled")

def load_main_config():
    """Load main configuration from config.json"""
    config_file = 'config.json'
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    # Fallback to a template if it doesn't exist
    if os.path.exists('config.json.template'):
        with open('config.json.template', 'r') as f:
            return json.load(f)
    return {}

main_config = load_main_config()

app = Flask(__name__)
CORS(app)

# Secret key for sessions (generate a random one if not in config)
app.config['SECRET_KEY'] = main_config.get('secret_key', secrets.token_hex(32))

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["1000 per hour"],  # Default limit for all routes
    storage_uri="memory://",  # Use in-memory storage (for production, consider Redis)
    storage_options={},
    strategy="fixed-window"
)

# Admin credentials (load from config or use defaults - should be changed in production!)
ADMIN_USERNAME = main_config.get('admin_username', 'admin')
ADMIN_PASSWORD = main_config.get('admin_password', 'admin123')  # Change this!

# Format: postgresql://USER:PASSWORD@HOST:PORT/DATABASE_NAME
app.config['SQLALCHEMY_DATABASE_URI'] = main_config.get('database_uri', 'postgresql://spotection_client:password123@localhost:5432/parking_db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
# Note: Tables need to be created first via db.create_all() but only once, will put in setup.py

# Configuration
CONFIG = {
    'upload_folder': 'uploads',
    'camera_feed_folder': 'camera_feeds',
    'screenshot_folder': 'screenshots',
    'max_upload_size': 16 * 1024 * 1024  # 16MB
}

# Create necessary folders
for folder in CONFIG.values():
    if isinstance(folder, str) and folder not in ['max_upload_size']:
        os.makedirs(folder, exist_ok=True)

# ============================================
# CAMERA CONFIGURATION
# ============================================
camera = None

# Store latest vehicle detections per lot for overlay display
latest_detections = {}  # {lot_id: [detections]}

# Store spot status history for hysteresis (prevent flickering)
# {lot_id: {spot_id: {'empty_count': N, 'last_seen': timestamp}}} - track empty frames
spot_status_history = {}  # Track consecutive empty detections
EMPTY_FRAMES_REQUIRED = 3  # Require 3 consecutive empty frames before marking as free

def load_camera_config():
    """Load camera configuration - tries to load from default lot in database first, then config.json"""
    global camera
    config_file = 'config.json'
    camera_source = 'placeholder'
    camera_url = None
    extraction_pattern_type = 'auto'
    extraction_pattern_value = None

    # First try to get camera from default lot (LOT-001)
    try:
        with app.app_context():
            default_lot = ParkingLot.query.filter_by(public_id='LOT-001').first()
            if default_lot and default_lot.camera_url:
                camera_url = default_lot.camera_url
                camera_source = default_lot.camera_type or 'auto'
                extraction_pattern_type = default_lot.extraction_pattern_type or 'auto'
                extraction_pattern_value = default_lot.extraction_pattern_value
    except Exception as e:
        logger.debug(f"Could not load camera from database: {e}")

    # Fallback to config.json if no database camera found
    if not camera_url and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            try:
                config = json.load(f)
                if 'camera_source' in config and 'camera_url' in config:
                    camera_source = config.get('camera_source')
                    camera_url = config.get('camera_url')
                    extraction_pattern_type = config.get('extraction_pattern_type', 'auto')
                    extraction_pattern_value = config.get('extraction_pattern_value')
            except Exception as e:
                logger.debug(f"Error loading camera config: {e}")

    # Stop old camera
    if camera:
        camera.stop()
        time.sleep(0.5)

    # Create new camera
    camera = create_camera_feed(camera_source, camera_url, extraction_pattern_type, extraction_pattern_value)

# Load initial camera config (skip during testing)
if not os.environ.get('TESTING'):
    load_camera_config()
# ============================================

# ============================================
# MEDIA STORAGE SYSTEM
# ============================================
media_storage = None
last_media_capture = {}  # Track last capture time per lot

def load_media_storage():
    """Initialize media storage manager"""
    global media_storage
    try:
        storage_config = main_config.get('media_storage', {})
        if storage_config.get('enabled', True):
            base_path = storage_config.get('base_path', 'media_archive')
            max_size_gb = storage_config.get('max_size_gb', 20.0)
            media_storage = MediaStorageManager(base_path, max_size_gb)
        else:
            logger.info("Media storage disabled in config")
    except Exception as e:
        logger.error(f"Failed to initialize media storage: {e}")

# Initialize media storage (skip during testing)
if not os.environ.get('TESTING'):
    load_media_storage()
# ============================================

# ============================================
# DETECTION SYSTEM
# ============================================
detection_model = None
detection_running = False
detection_thread = None

def load_detection_model():
    """Load YOLO detection model"""
    global detection_model
    if not DETECTION_AVAILABLE:
        logger.warning("Detection not available - YOLO/CV2 not installed")
        return False
    
    try:
        model_path = main_config.get('model_path', 'yolov8n.pt')
        detection_model = YOLO(model_path)
        
        # Set model to evaluation mode for consistency
        detection_model.model.eval()
        
        logger.info(f"Detection model loaded: {model_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to load detection model: {e}")
        return False

def detect_vehicles_in_frame(frame):
    """Detect vehicles in a single frame"""
    if not detection_model:
        return []
    
    try:
        # Apply advanced image enhancement if configured
        detection_frame = frame
        if main_config.get("image_enhancement", True):
            # Step 1: Bilateral filter to reduce noise while preserving edges (helps with blur)
            denoised = cv2.bilateralFilter(frame, 9, 75, 75)
            
            # Step 2: CLAHE enhancement for better contrast
            lab = cv2.cvtColor(denoised, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Use stronger CLAHE for distant/blurry vehicles
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l)
            lab_enhanced = cv2.merge([l_enhanced, a, b])
            detection_frame = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
            
            # Step 3: Sharpen the image to counteract blur
            kernel = np.array([[-1,-1,-1],
                              [-1, 9,-1],
                              [-1,-1,-1]])
            detection_frame = cv2.filter2D(detection_frame, -1, kernel)
        
        # Run detection with optimized parameters
        # Use a lower base confidence threshold to ensure we catch vehicles in small/distant spots
        # We'll filter by higher confidence during spot analysis for normal-sized spots
        conf_threshold = main_config.get('confidence_threshold', 0.2)
        small_spot_conf_threshold = conf_threshold * 0.65  # 65% of normal threshold for small spots
        
        # Use the lower threshold globally to catch all potential vehicles
        iou_threshold = main_config.get('iou_threshold', 0.45)  # NMS threshold
        img_size = main_config.get('detection_image_size', 1280)  # Larger size for better distant detection
        
        results = detection_model(
            detection_frame,
            conf=small_spot_conf_threshold,  # Use lower threshold to catch vehicles in small spots
            iou=iou_threshold,
            imgsz=img_size,
            verbose=False,
            device='cpu',  # Explicitly use CPU for consistency
            half=False,    # Disable half-precision for accuracy
            augment=True   # Enable test-time augmentation for better detection
        )[0]
        
        detections = []
        vehicle_classes = set(main_config.get('vehicle_classes', ['car', 'truck', 'bus', 'motorcycle', 'bicycle']))
        
        for box_data in results.boxes:
            cls_id = int(box_data.cls[0])
            class_name = detection_model.names[cls_id]
            confidence = float(box_data.conf[0])
            x1, y1, x2, y2 = map(int, box_data.xyxy[0])
            
            if class_name in vehicle_classes:
                detections.append({
                    "class": class_name,
                    "confidence": confidence,
                    "bbox": (x1, y1, x2, y2),
                    "box": shapely_box(x1, y1, x2, y2)
                })
        
        return detections
    except Exception as e:
        logger.error(f"Detection error: {e}")
        return []

def analyze_spots_with_detections(detections, calibration_data, frame_shape, lot_id=None):
    """Analyze which spots are occupied based on detections"""
    if not calibration_data:
        return {}
    
    results = {}
    overlap_threshold = main_config.get('overlap_threshold', 0.25)
    
    # Get current spot statuses for hysteresis - use memory tracking, not database
    # Database may have been updated too recently
    current_statuses = {}
    if lot_id and lot_id in spot_status_history:
        for spot_id in spot_status_history[lot_id]:
            # If empty_count is 0, spot is considered occupied
            if spot_status_history[lot_id][spot_id]['empty_count'] == 0:
                current_statuses[spot_id] = 'occupied'
            else:
                current_statuses[spot_id] = 'free'
    
    for spot_data in calibration_data:
        spot_id = spot_data['id']
        polygon_coords = spot_data['polygon']
        
        try:
            # Convert normalized coordinates to pixel coordinates
            pixel_coords = [(p['x'] * frame_shape[1], p['y'] * frame_shape[0]) for p in polygon_coords]
            spot_polygon = Polygon(pixel_coords)
            spot_area = spot_polygon.area
            
            # Determine if this is a small/distant spot (less than 5000 pixels²)
            is_small_spot = spot_area < 5000
            
            # Check if spot is currently occupied (for hysteresis)
            currently_occupied = current_statuses.get(spot_id) == 'occupied'
            
            # Adjust thresholds for small spots
            if is_small_spot:
                # Use intersection/spot_area ratio instead of IoU for small spots
                # Lower threshold significantly for small/distant spots (50% of normal)
                effective_threshold = overlap_threshold * 0.5
                # Also lower confidence threshold for small spots (65% of normal)
                min_confidence = main_config.get('confidence_threshold', 0.2) * 0.65
            else:
                effective_threshold = overlap_threshold
                # Use normal confidence threshold for regular spots
                min_confidence = main_config.get('confidence_threshold', 0.2)
            
            # Apply hysteresis: if currently occupied, use 80% of threshold to become free
            # This prevents flickering when vehicle slightly moves
            if currently_occupied:
                free_threshold = effective_threshold * 0.8
            else:
                free_threshold = effective_threshold
            
            best_match = None
            max_overlap = 0.0
            
            for detection in detections:
                # Skip detections that don't meet the minimum confidence for this spot size
                if detection['confidence'] < min_confidence:
                    continue
                    
                intersection = spot_polygon.intersection(detection["box"])
                if intersection.area > 0:
                    if is_small_spot:
                        # For small spots, use intersection/spot ratio (more sensitive)
                        overlap_ratio = intersection.area / spot_area
                    else:
                        # For normal spots, use IoU
                        union_area = spot_polygon.area + detection["box"].area - intersection.area
                        overlap_ratio = intersection.area / union_area if union_area > 0 else 0
                    
                    if overlap_ratio > max_overlap:
                        max_overlap = overlap_ratio
                        best_match = detection
            
            if max_overlap > effective_threshold and best_match:
                results[spot_id] = {
                    'status': 'occupied',
                    'confidence': best_match['confidence'],
                    'vehicle_data': {
                        'class': best_match['class'],
                        'confidence': best_match['confidence'],
                        'bbox': best_match['bbox']  # Store bounding box
                    }
                }
                # Reset empty counter when vehicle detected
                if lot_id and lot_id in spot_status_history:
                    if spot_id in spot_status_history[lot_id]:
                        spot_status_history[lot_id][spot_id]['empty_count'] = 0
            elif max_overlap > 0.15 and best_match and best_match['confidence'] < 0.6:
                # Low confidence detection - mark as occupied to be safe
                # Require minimum 15% overlap to avoid shadows
                results[spot_id] = {
                    'status': 'occupied',
                    'confidence': best_match['confidence'],
                    'vehicle_data': {
                        'class': best_match['class'],
                        'confidence': best_match['confidence'],
                        'uncertain': True,
                        'bbox': best_match['bbox']  # Store bounding box
                    }
                }
                # Reset empty counter
                if lot_id and lot_id in spot_status_history:
                    if spot_id in spot_status_history[lot_id]:
                        spot_status_history[lot_id][spot_id]['empty_count'] = 0
            elif currently_occupied and max_overlap > free_threshold and best_match:
                # Hysteresis: keep as occupied if still above lower threshold
                results[spot_id] = {
                    'status': 'occupied',
                    'confidence': best_match['confidence'],
                    'vehicle_data': {
                        'class': best_match['class'],
                        'confidence': best_match['confidence'],
                        'bbox': best_match['bbox']
                    }
                }
                # Reset empty counter
                if lot_id and lot_id in spot_status_history:
                    if spot_id in spot_status_history[lot_id]:
                        spot_status_history[lot_id][spot_id]['empty_count'] = 0
            else:
                # Spot appears empty - check if we should mark it free
                should_mark_free = True
                
                if currently_occupied and lot_id:
                    # Initialize tracking for this lot if needed
                    if lot_id not in spot_status_history:
                        spot_status_history[lot_id] = {}
                    if spot_id not in spot_status_history[lot_id]:
                        spot_status_history[lot_id][spot_id] = {'empty_count': 0}
                    
                    # Increment empty frame counter
                    spot_status_history[lot_id][spot_id]['empty_count'] += 1
                    empty_count = spot_status_history[lot_id][spot_id]['empty_count']
                    
                    if empty_count < EMPTY_FRAMES_REQUIRED:
                        # Keep as occupied until we have enough consecutive empty frames
                        should_mark_free = False
                        # Get the last known vehicle data from database (already in app context)
                        try:
                            lot_obj = ParkingLot.query.filter_by(public_id=lot_id).first()
                            if lot_obj:
                                spot_obj = Spot.query.filter_by(lot_id=lot_obj.id, spot_id=spot_id).first()
                                if spot_obj:
                                    latest = StatusUpdate.query.filter_by(spot_id=spot_obj.id).order_by(StatusUpdate.timestamp.desc()).first()
                                    if latest and latest.vehicle_data:
                                        results[spot_id] = {
                                            'status': 'occupied',
                                            'confidence': latest.confidence,
                                            'vehicle_data': latest.vehicle_data
                                        }
                                    else:
                                        # No previous vehicle data, mark as free
                                        should_mark_free = True
                        except Exception as e:
                            pass
                            should_mark_free = True
                
                if should_mark_free:
                    results[spot_id] = {
                        'status': 'free',
                        'confidence': 0.0,
                        'vehicle_data': None
                    }
                    # Reset counter when marked free
                    if lot_id and lot_id in spot_status_history and spot_id in spot_status_history[lot_id]:
                        spot_status_history[lot_id][spot_id]['empty_count'] = 0
        except Exception as e:
            logger.error(f"Error analyzing spot {spot_id}: {e}", exc_info=True)
            continue
    
    return results

def update_database_with_detections(spot_results, lot_id):
    """Update database with detection results"""
    try:
        with app.app_context():
            lot = ParkingLot.query.filter_by(public_id=lot_id).first()
            if not lot:
                logger.error(f"Lot {lot_id} not found in database")
                return
            
            updated_count = 0
            for spot_id, result in spot_results.items():
                spot = Spot.query.filter_by(lot_id=lot.id, spot_id=spot_id).first()
                if not spot:
                    logger.warning(f"Spot {spot_id} not found in database (lot_id={lot.id})")
                    continue
                
                # Get latest status
                latest = StatusUpdate.query.filter_by(spot_id=spot.id).order_by(StatusUpdate.timestamp.desc()).first()
                
                # Only update if status changed
                if not latest or latest.status != result['status']:
                    new_status = StatusUpdate(
                        spot_id=spot.id,
                        status=result['status'],
                        confidence=result['confidence'],
                        vehicle_data=result['vehicle_data']
                    )
                    db.session.add(new_status)
                    updated_count += 1
            
            db.session.commit()
    except Exception as e:
        logger.error(f"Database update error: {e}", exc_info=True)
        db.session.rollback()

def detection_loop():
    """Background detection loop"""
    global detection_running
    
    # Use update_interval from config (configurable in admin panel)
    interval = main_config.get('update_interval', 5)  # Default to 5 seconds
    logger.info(f"Detection loop started (interval: {interval}s)")
    
    while detection_running:
        try:
            # Get all lots from database
            with app.app_context():
                lots = ParkingLot.query.all()
                
                for lot in lots:
                    lot_id = lot.public_id
                    
                    # Check if this lot has calibration data
                    config_key = f'calibration_data_{lot_id}'
                    calibration_data = main_config.get(config_key)
                    if not calibration_data:
                        # Fallback to default calibration for LOT-001 or general calibration_data
                        if lot_id == main_config.get('default_lot_id', 'LOT-001'):
                            calibration_data = main_config.get('calibration_data', [])
                        if not calibration_data:
                            continue
                    
                    # Check if this lot has a camera configured
                    if not lot.camera_url:
                        continue
                    
                    # Create temporary camera for this lot
                    lot_camera = None
                    try:
                        lot_camera = create_camera_feed(
                            lot.camera_type or 'auto',
                            lot.camera_url,
                            lot.extraction_pattern_type or 'auto',
                            lot.extraction_pattern_value
                        )
                    except Exception as e:
                        logger.error(f"Failed to create camera for {lot_id}: {e}")
                        continue
                    
                    try:
                        # Get frame from camera
                        frame_b64 = lot_camera.get_frame('base64')
                        if not frame_b64 or not frame_b64.startswith('data:image'):
                            logger.warning(f"No valid frame from camera for {lot_id}")
                            continue
                        
                        # Decode base64 frame
                        import base64
                        img_data = base64.b64decode(frame_b64.split(',')[1])
                        nparr = np.frombuffer(img_data, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        if frame is None:
                            logger.warning(f"Failed to decode frame for {lot_id}")
                            continue
                        
                        # Detect vehicles
                        detections = detect_vehicles_in_frame(frame)
                        
                        # Cache detections for overlay display
                        global latest_detections
                        latest_detections[lot_id] = detections
                        
                        # Analyze spots
                        spot_results = analyze_spots_with_detections(detections, calibration_data, frame.shape, lot_id=lot_id)
                        
                        # Update database
                        update_database_with_detections(spot_results, lot_id)
                        
                        # Save media to archive if enabled
                        if media_storage:
                            try:
                                storage_config = main_config.get('media_storage', {})
                                capture_interval = storage_config.get('capture_interval', 300)  # 5 minutes default
                                capture_on_change = storage_config.get('capture_on_change', True)
                                
                                # Determine if we should capture
                                should_capture = False
                                now = time.time()
                                
                                # Check time-based capture
                                last_capture_time = last_media_capture.get(lot_id, 0)
                                if now - last_capture_time >= capture_interval:
                                    should_capture = True
                                
                                # Check change-based capture
                                if capture_on_change and not should_capture:
                                    # Compare current occupancy with previous
                                    occupied_spots = sum(1 for s in spot_results.values() if s.get('occupied'))
                                    prev_occupied = last_media_capture.get(f"{lot_id}_occupied", occupied_spots)
                                    
                                    if occupied_spots != prev_occupied:
                                        should_capture = True
                                        last_media_capture[f"{lot_id}_occupied"] = occupied_spots
                                
                                if should_capture:
                                    # Prepare metadata
                                    occupied_count = sum(1 for s in spot_results.values() if s.get('occupied'))
                                    metadata = {
                                        'detections_count': occupied_count,  # Count vehicles in spots, not all detections
                                        'occupied_spots': occupied_count,
                                        'total_spots': len(spot_results),
                                        'vehicle_types': {},
                                        'capture_reason': 'interval' if now - last_capture_time >= capture_interval else 'change'
                                    }
                                    
                                    # Count vehicle types from occupied spots only
                                    for spot_data in spot_results.values():
                                        if spot_data.get('occupied') and spot_data.get('vehicle_class'):
                                            veh_class = spot_data.get('vehicle_class', 'unknown')
                                            metadata['vehicle_types'][veh_class] = metadata['vehicle_types'].get(veh_class, 0) + 1
                                    
                                    # Save image with app context
                                    with app.app_context():
                                        success, result = media_storage.save_image(
                                            db,
                                            frame,
                                            lot.id,
                                            datetime.now(),
                                            metadata
                                        )
                                        
                                        if success:
                                            last_media_capture[lot_id] = now
                                        else:
                                            logger.error(f"{lot_id}: Media save failed: {result}")
                                
                            except Exception as e:
                                logger.error(f"{lot_id}: Media capture error: {e}", exc_info=True)
                        
                        # Print clean summary
                        occupied = sum(1 for r in spot_results.values() if r['status'] == 'occupied')
                        free = sum(1 for r in spot_results.values() if r['status'] == 'free')
                        logger.info(f"[{lot_id}] 🚗 {len(detections)} vehicles | 🅿️ {occupied}/{len(spot_results)} occupied | ✓ Detection complete")
                        
                    finally:
                        # Clean up lot camera
                        if lot_camera:
                            lot_camera.stop()
            
        except Exception as e:
            logger.error(f"Detection loop error: {e}", exc_info=True)
        
        # Re-read interval from config on each iteration (allows dynamic updates)
        interval = main_config.get('update_interval', 5)
        time.sleep(interval)
    
    logger.info("Detection loop stopped")

def start_detection():
    """Start background detection"""
    global detection_running, detection_thread
    
    # Load model if not already loaded
    if not detection_model:
        if not load_detection_model():
            logger.error("Cannot start detection - model not loaded")
            return False
    
    if detection_running:
        logger.warning("Detection already running")
        return True
    
    detection_running = True
    detection_thread = threading.Thread(target=detection_loop, daemon=True)
    detection_thread.start()
    return True

def stop_detection():
    """Stop background detection"""
    global detection_running
    detection_running = False
    if detection_thread:
        detection_thread.join(timeout=2)

# Auto-start detection when module loads (skip during testing)
# Only run in the main worker process, not the reloader parent process
if DETECTION_AVAILABLE and not os.environ.get('TESTING'):
    # In debug mode with reloader, only run in the actual worker process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or not app.debug:
        # Load model first
        if load_detection_model():
            # Start detection automatically
            start_detection()
        else:
            logger.warning("Detection model not loaded at startup - use /api/detection/load_model")

# ============================================

# Mock data for alpha testing (replace with actual ML model integration)
parking_data = {
    'lot_id': 'LOT-001',
    'total_spaces': 50,
    'available_spaces': 23,
    'occupied_spaces': 27,
    'last_updated': datetime.now().isoformat(),
    'spaces': []
}

# Load calibration data if exists
def load_calibration():
    """Load calibration data from file"""
    config_file = 'config.json'
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                if 'calibration_data' in config:
                    return config['calibration_data']
        except Exception as e:
            logger.debug(f"Error loading calibration: {e}")
    return []

# Initialize parking spaces from calibration or create empty list (skip during testing)
if not os.environ.get('TESTING'):
    calibration_data = load_calibration()
    if calibration_data:
        parking_data['spaces'] = calibration_data
        parking_data['total_spaces'] = len(calibration_data)
        logger.info(f"Loaded {len(calibration_data)} calibrated parking spaces")
    else:
        # Initialize mock parking spaces without polygons
        for i in range(50):
            parking_data['spaces'].append({
                'id': f'SPACE-{i+1:03d}',
                'status': 'available' if i < 23 else 'occupied',
                'polygon': []  # Empty - will be filled by calibration
            })
        logger.warning("No calibration data found. Please calibrate the system at /admin.")
else:
    calibration_data = []

# Note: Real-time updates are now handled by the detection_loop() function
# The obsolete update_parking_data() background thread has been removed

# ============================================
# AUTHENTICATION
# ============================================
def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # Prevent brute force attacks
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            next_page = request.args.get('next')
            return redirect(next_page or url_for('admin'))
        else:
            return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout"""
    session.clear()
    return redirect(url_for('index'))

# Routes
@app.route('/')
def index():
    """Main dashboard with live detection - UC-001: View Real-Time Parking Availability"""
    return render_template('index.html')

@app.route('/live')
def live():
    """Redirect to main dashboard"""
    return redirect(url_for('index'))

@app.route('/media-archive')
def media_archive():
    """Media archive viewer"""
    return render_template('media_archive.html')

@app.route('/analytics')
def analytics():
    """Redirect to main dashboard"""
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    """Admin panel - UC-002: Calibrate, UC-005: Configure"""
    return render_template('admin.html')

@app.route('/api/system/settings', methods=['GET', 'POST'])
@login_required
@limiter.limit("30 per minute")
def system_settings():
    """Get or update system settings"""
    if request.method == 'GET':
        # Return current configuration (excluding sensitive data)
        safe_config = {
            'detection': {
                'confidence_threshold': main_config.get('confidence_threshold', 0.25),
                'overlap_threshold': main_config.get('overlap_threshold', 0.3),
                'iou_threshold': main_config.get('iou_threshold', 0.45),
                'detection_image_size': main_config.get('detection_image_size', 640),
                'image_enhancement': main_config.get('image_enhancement', True),
                'vehicle_classes': main_config.get('vehicle_classes', [])
            },
            'camera': {
                'camera_source': main_config.get('camera_source', 'placeholder'),
                'camera_url': main_config.get('camera_url'),
                'update_interval': main_config.get('update_interval', 5)
            },
            'media_storage': main_config.get('media_storage', {}),
            'system': {
                'screenshot_interval': main_config.get('screenshot_interval', 120),
                'save_raw_screenshots': main_config.get('save_raw_screenshots', True),
                'log_dir': main_config.get('log_dir', 'logs/'),
                'output_dir': main_config.get('output_dir', 'output/')
            }
        }
        return jsonify(safe_config)
    
    elif request.method == 'POST':
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            # Update configuration sections
            if 'detection' in data:
                for key, value in data['detection'].items():
                    main_config[key] = value
            
            if 'camera' in data:
                for key, value in data['camera'].items():
                    main_config[key] = value
            
            if 'media_storage' in data:
                main_config['media_storage'] = {**main_config.get('media_storage', {}), **data['media_storage']}
                
                # Reinitialize media storage if settings changed
                global media_storage
                if media_storage and main_config['media_storage'].get('enabled', True):
                    from flaskweb.media_storage import MediaStorageManager
                    media_storage = MediaStorageManager(
                        base_path=main_config['media_storage'].get('base_path', 'media_archive'),
                        max_size_gb=main_config['media_storage'].get('max_size_gb', 20.0)
                    )
            
            if 'system' in data:
                for key, value in data['system'].items():
                    main_config[key] = value
            
            # Save to config.json
            with open('config.json', 'w') as f:
                json.dump(main_config, f, indent=2)
            
            logger.info("System settings updated")
            return jsonify({'success': True, 'message': 'Settings updated successfully'})
        
        except Exception as e:
            logger.error(f"Error updating settings: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/test-multilot')
def test_multilot():
    """Test page for multi-lot functionality"""
    return render_template('test_multilot.html')

# API Endpoints
@app.route('/api/parking/status', methods=['GET'])
@limiter.limit("60 per minute")  # Public API - moderate limit
def get_parking_status():
    """Get current parking lot status - redirects to default lot with fresh config data"""
    # Reload calibration data from config to ensure sync
    global parking_data
    calibration_data = load_calibration()
    if calibration_data:
        parking_data['spaces'] = calibration_data
        parking_data['total_spaces'] = len(calibration_data)
    
    # Use the default lot from config
    lot_id = main_config.get('default_lot_id', 'LOT-001')
    return get_lot_status(lot_id)

@app.route('/api/parking/spaces', methods=['GET'])
def get_spaces():
    """Get detailed space information"""
    return jsonify({
        'spaces': parking_data['spaces'],
        'total': parking_data['total_spaces']
    })

@app.route('/api/parking/space/<space_id>', methods=['GET', 'PUT'])
def manage_space(space_id):
    """Get or update individual space"""
    # PUT requires authentication
    if request.method == 'PUT' and not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'}), 401
    
    if request.method == 'GET':
        space = next((s for s in parking_data['spaces'] if s['id'] == space_id), None)
        if space:
            return jsonify(space)
        return jsonify({'error': 'Space not found'}), 404
    
    elif request.method == 'PUT':
        # Update space calibration data
        data = request.json
        space = next((s for s in parking_data['spaces'] if s['id'] == space_id), None)
        if space:
            space['polygon'] = data.get('polygon', space['polygon'])
            return jsonify({'success': True, 'space': space})
        return jsonify({'error': 'Space not found'}), 404

@app.route('/api/lot/<string:lot_id>/calibration', methods=['GET', 'POST'])

@limiter.limit("30 per minute")  # Calibration endpoint - restricted
def lot_calibration(lot_id):
    """Get or set calibration for a specific lot"""
    # POST requires authentication
    if request.method == 'POST' and not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'}), 401
    
    if request.method == 'GET':
        try:
            # Get calibration for this lot
            config_file = 'config.json'
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    # Check if we have lot-specific calibration
                    lot_key = f'calibration_data_{lot_id}'
                    if lot_key in config:
                        return jsonify({'calibration_data': config[lot_key], 'lot_id': lot_id})
                    # Fall back to default calibration if it's the default lot
                    elif lot_id == config.get('default_lot_id', 'LOT-001') and 'calibration_data' in config:
                        return jsonify({'calibration_data': config['calibration_data'], 'lot_id': lot_id})
            return jsonify({'calibration_data': [], 'lot_id': lot_id})
        except Exception as e:
            logger.error(f"Error loading calibration for {lot_id}: {e}")
            return jsonify({'error': str(e), 'calibration_data': [], 'lot_id': lot_id}), 500
    
    elif request.method == 'POST':
        try:
            data = request.json
            if not data:
                return jsonify({'success': False, 'error': 'No JSON data provided'}), 400
            
            calibration_spaces = data.get('calibration_data', [])
            
            if not calibration_spaces:
                return jsonify({'success': False, 'error': 'No calibration_data in request'}), 400
            
            logger.info(f"✅ Saving {len(calibration_spaces)} calibrated spaces to lot {lot_id}")
            
            # SYNC TO DATABASE: Create/update Spot records for this lot
            try:
                lot = ParkingLot.query.filter_by(public_id=lot_id).first()
                
                if not lot:
                    logger.warning(f"Lot '{lot_id}' not found in database. Creating it...")
                    lot = ParkingLot(
                        public_id=lot_id,
                        name=f"Parking Lot {lot_id}",
                        total_spots=len(calibration_spaces)
                    )
                    db.session.add(lot)
                    db.session.flush()
                    logger.info(f"Created new lot: {lot_id}")
                else:
                    # Update total spots
                    lot.total_spots = len(calibration_spaces)
                
                # Get existing spots for this lot
                existing_spots = {spot.spot_id: spot for spot in Spot.query.filter_by(lot_id=lot.id).all()}
                calibrated_spot_ids = {space['id'] for space in calibration_spaces}
                
                # Remove spots that are no longer in calibration
                for spot_id, spot in list(existing_spots.items()):
                    if spot_id not in calibrated_spot_ids:
                        logger.info(f"Removing deleted spot: {spot_id}")
                        StatusUpdate.query.filter_by(spot_id=spot.id).delete()
                        db.session.delete(spot)
                        del existing_spots[spot_id]
                
                # Add new spots from calibration
                spots_created = 0
                for space in calibration_spaces:
                    spot_id = space['id']
                    if spot_id not in existing_spots:
                        new_spot = Spot(spot_id=spot_id, lot_id=lot.id)
                        db.session.add(new_spot)
                        db.session.flush()
                        
                        # Create initial 'free' status
                        initial_status = StatusUpdate(
                            spot_id=new_spot.id,
                            status='free',
                            confidence=0.0,
                            vehicle_data=None
                        )
                        db.session.add(initial_status)
                        spots_created += 1
                        logger.info(f"Created new spot: {spot_id} with initial 'free' status")
                
                db.session.commit()
                logger.info(f"✓ Database synced: {spots_created} new spots created, {len(calibration_spaces)} total spots in lot '{lot_id}'")
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error syncing calibration to database: {e}", exc_info=True)
                return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500
            
            # Save to config file
            config_file = 'config.json'
            existing_config = {}
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    try:
                        existing_config = json.load(f)
                    except json.JSONDecodeError as je:
                        logger.error(f"Config file corrupted: {je}")
                        return jsonify({'success': False, 'error': 'Config file is corrupted'}), 500
            
            # Save lot-specific calibration
            lot_key = f'calibration_data_{lot_id}'
            existing_config[lot_key] = calibration_spaces
            
            # If this is the default lot, also update the main calibration_data
            if lot_id == existing_config.get('default_lot_id', 'LOT-001'):
                existing_config['calibration_data'] = calibration_spaces
            
            try:
                with open(config_file, 'w') as f:
                    json.dump(existing_config, f, indent=2)
            except Exception as e:
                logger.error(f"Error writing config file: {e}")
                return jsonify({'success': False, 'error': f'Failed to save config: {str(e)}'}), 500
            
            return jsonify({'success': True, 'lot_id': lot_id, 'spaces_saved': len(calibration_spaces)})
        
        except Exception as e:
            logger.error(f"Error saving calibration for {lot_id}: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/lot/<string:lot_id>/calibration/status', methods=['GET'])
def lot_calibration_status(lot_id):
    """Check if calibration is synced to database for a specific lot"""
    try:
        # Get config calibration
        config_file = 'config.json'
        config_spots = 0
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                lot_key = f'calibration_data_{lot_id}'
                if lot_key in config:
                    config_spots = len(config[lot_key])
                elif lot_id == config.get('default_lot_id', 'LOT-001') and 'calibration_data' in config:
                    config_spots = len(config['calibration_data'])
        
        # Get database spots
        lot = ParkingLot.query.filter_by(public_id=lot_id).first()
        db_spots = 0
        if lot:
            db_spots = Spot.query.filter_by(lot_id=lot.id).count()
        
        synced = (config_spots == db_spots) and config_spots > 0
        
        return jsonify({
            'synced': synced,
            'lot_id': lot_id,
            'config_spots': config_spots,
            'db_spots': db_spots
        })
    except Exception as e:
        logger.error(f"Error checking calibration status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/config', methods=['GET', 'POST'])
@limiter.limit("20 per minute")  # Config endpoint - very restricted
def config():
    """Get or update configuration - UC-005"""
    # POST requires authentication
    if request.method == 'POST' and not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'}), 401
    
    config_file = 'config.json'
    
    if request.method == 'GET':
        # Default config values
        default_config = {
            'confidence_threshold': 0.2,
            'overlap_threshold': 0.25,
            'iou_threshold': 0.45,
            'detection_image_size': 640,
            'detection_threshold': 0.5,
            'update_interval': 5,
            'camera_resolution': '1920x1080',
            'model_version': 'v1.0',
            'calibration_data': []
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                existing_config = json.load(f)
                # Merge with defaults to ensure all fields exist
                default_config.update(existing_config)
        
        return jsonify(default_config)
    
    elif request.method == 'POST':
        global parking_data, main_config
        data = request.json
        
        # If calibration data is being saved, update parking_data
        if 'calibration_data' in data:
            calibration_spaces = data['calibration_data']
            
            # Update parking data with calibrated spaces
            parking_data['spaces'] = calibration_spaces
            parking_data['total_spaces'] = len(calibration_spaces)
            
            # Initialize all spots as 'free' (detection system will update with actual status)
            for space in parking_data['spaces']:
                if 'status' not in space:
                    space['status'] = 'free'  # Default to free, detection will update
            
            parking_data['available_spaces'] = len(calibration_spaces)  # All free initially
            parking_data['occupied_spaces'] = 0
            
            logger.info(f"✅ Saved {len(calibration_spaces)} calibrated parking spaces")
            
            # SYNC TO DATABASE: Create/update Spot records for the configured lot
            try:
                lot_id = main_config.get('default_lot_id', 'LOT-001')
                lot = ParkingLot.query.filter_by(public_id=lot_id).first()
                
                if not lot:
                    logger.warning(f"Lot '{lot_id}' not found in database. Creating it...")
                    lot = ParkingLot(
                        public_id=lot_id,
                        name=f"Parking Lot {lot_id}",
                        total_spots=len(calibration_spaces)
                    )
                    db.session.add(lot)
                    db.session.flush()
                    logger.info(f"Created new lot: {lot_id}")
                else:
                    # Update total spots
                    lot.total_spots = len(calibration_spaces)
                
                # Get existing spots for this lot
                existing_spots = {spot.spot_id: spot for spot in Spot.query.filter_by(lot_id=lot.id).all()}
                calibrated_spot_ids = {space['id'] for space in calibration_spaces}
                
                # Remove spots that are no longer in calibration
                for spot_id, spot in list(existing_spots.items()):
                    if spot_id not in calibrated_spot_ids:
                        logger.info(f"Removing deleted spot: {spot_id}")
                        # Delete associated status updates first
                        StatusUpdate.query.filter_by(spot_id=spot.id).delete()
                        db.session.delete(spot)
                        del existing_spots[spot_id]
                
                # Add new spots from calibration
                spots_created = 0
                for space in calibration_spaces:
                    spot_id = space['id']
                    if spot_id not in existing_spots:
                        new_spot = Spot(spot_id=spot_id, lot_id=lot.id)
                        db.session.add(new_spot)
                        db.session.flush()  # Get the new spot ID
                        
                        # Create initial 'free' status update for new spots
                        initial_status = StatusUpdate(
                            spot_id=new_spot.id,
                            status='free',
                            confidence=0.0,
                            vehicle_data=None
                        )
                        db.session.add(initial_status)
                        spots_created += 1
                        logger.info(f"Created new spot: {spot_id} with initial 'free' status")
                
                db.session.commit()
                logger.info(f"✓ Database synced: {spots_created} new spots created, {len(calibration_spaces)} total spots in lot '{lot_id}'")
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error syncing calibration to database: {e}")
                logger.error(traceback.format_exc())
                # Don't fail the entire save if DB sync fails
        
        # Save to file
        existing_config = {}
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                try:
                    existing_config = json.load(f)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse config.json: {e}")
                    pass
        
        # Merge with existing config
        existing_config.update(data)
        
        with open(config_file, 'w') as f:
            json.dump(existing_config, f, indent=2)
        
        # Reload main_config to apply changes immediately
        main_config = load_main_config()
        logger.info(f"✓ Configuration updated and reloaded: confidence_threshold={main_config.get('confidence_threshold')}, overlap_threshold={main_config.get('overlap_threshold')}")
        
        return jsonify({'success': True, 'config': existing_config})

@app.route('/api/camera/feed', methods=['GET'])
@limiter.limit("600 per minute")  # Higher limit for live camera feed
def camera_feed():
    """Get latest camera frame for a specific lot or default camera"""
    global camera
    
    # Check if a specific lot is requested
    lot_id = request.args.get('lot_id')
    
    # If lot_id provided, create temporary camera for that lot
    if lot_id:
        try:
            lot = ParkingLot.query.filter_by(public_id=lot_id).first()
        except Exception as e:
            logger.error(f"Database error querying lot {lot_id}: {e}")
            return jsonify({'error': 'Database error', 'image_url': None}), 500
            
        if not lot:
            logger.error(f"Lot {lot_id} not found")
            return jsonify({'error': f'Lot {lot_id} not found', 'image_url': None}), 404
            
        if not lot.camera_url:
            logger.error(f"No camera URL configured for lot {lot_id}")
            return jsonify({'error': f'No camera configured for {lot_id}', 'image_url': None}), 404
        
        # Create temporary camera for this lot
        temp_camera = None
        try:
            camera_type = lot.camera_type if lot.camera_type else 'auto'
            camera_url = lot.camera_url
            extraction_type = lot.extraction_pattern_type if lot.extraction_pattern_type else 'auto'
            extraction_value = lot.extraction_pattern_value
            
            logger.debug(f"Creating camera for lot {lot_id}: type={camera_type}, url={camera_url[:50]}...")
            
            temp_camera = create_camera_feed(
                camera_type,
                camera_url,
                extraction_type,
                extraction_value
            )
            image_data = temp_camera.get_frame('base64')
            
            if temp_camera:
                try:
                    temp_camera.stop()  # Clean up
                except:
                    pass
            
            if not image_data:
                return jsonify({'error': 'No frame data available', 'image_url': None}), 500
            
            response = jsonify({
                'image_url': image_data,
                'timestamp': datetime.now().isoformat(),
                'lot_id': lot_id
            })
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        except Exception as e:
            logger.error(f"Error getting camera feed for {lot_id}: {e}", exc_info=True)
            return jsonify({'error': str(e), 'image_url': None}), 500
    
    # Otherwise use global camera (backwards compatibility)
    if not camera:
        logger.error("Camera not initialized")
        return jsonify({'error': 'Camera not initialized', 'image_url': None}), 500
    
    try:
        # Get frame as base64 encoded image
        image_data = camera.get_frame('base64')
        
        if not image_data:
            logger.error("Camera returned no frame data")
            return jsonify({'error': 'No frame data available', 'image_url': None}), 500
        
        # Log success for debugging
        logger.debug(f"Camera feed retrieved successfully, type: {camera.source_type}")
        
        response = jsonify({
            'image_url': image_data,
            'timestamp': datetime.now().isoformat(),
            'source_info': camera.get_info()
        })
        
        # Add cache control headers to prevent stale data
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response
    except Exception as e:
        logger.error(f"Error getting camera feed: {e}", exc_info=True)
        return jsonify({'error': str(e), 'image_url': None}), 500

@app.route('/api/detection/status', methods=['GET'])
def detection_status():
    """Get detection system status"""
    return jsonify({
        'running': detection_running,
        'available': DETECTION_AVAILABLE,
        'model_loaded': detection_model is not None,
        'camera_available': camera is not None,
        'werkzeug_main': os.environ.get('WERKZEUG_RUN_MAIN')
    })

@app.route('/api/detection/load_model', methods=['POST'])
@login_required
def load_model_endpoint():
    """Manually load detection model"""
    try:
        if load_detection_model():
            return jsonify({'success': True, 'message': 'Model loaded successfully'})
        else:
            return jsonify({'success': False, 'error': 'Model loading returned False'}), 500
    except Exception as e:
        logger.error(f"Error loading model: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/detection/control', methods=['POST'])
@login_required
def control_detection():
    """Start or stop detection"""
    action = request.json.get('action')
    
    if action == 'start':
        if start_detection():
            return jsonify({'success': True, 'message': 'Detection started', 'running': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to start detection'}), 500
    elif action == 'stop':
        stop_detection()
        return jsonify({'success': True, 'message': 'Detection stopped', 'running': False})
    else:
        return jsonify({'error': 'Invalid action. Use "start" or "stop"'}), 400

@app.route('/api/detection/overlay', methods=['GET'])
@limiter.limit("60 per minute")  # Overlay data - moderate limit
def get_detection_overlay():
    """Get detection overlay data with spot status and vehicle information (default lot)"""
    lot_id = main_config.get('default_lot_id', 'LOT-001')
    return get_lot_detection_overlay(lot_id)

@app.route('/api/lot/<lot_id>/detection/overlay', methods=['GET'])
@limiter.limit("60 per minute")  # Higher limit for live overlay updates
def get_lot_detection_overlay(lot_id):
    """Get detection overlay data for a specific lot with spot status and vehicle information"""
    try:
        # Reload config to get latest calibration data
        global main_config
        main_config = load_main_config()
        
        # Load lot-specific calibration
        config_key = f'calibration_data_{lot_id}'
        calibration_data = main_config.get(config_key)
        if not calibration_data:
            # Fallback to default calibration
            calibration_data = main_config.get('calibration_data', [])
        
        # Get lot status from database
        lot = ParkingLot.query.filter_by(public_id=lot_id).first()
        
        overlay_data = {
            'spots': [],
            'vehicles': [],  # Add vehicle detections
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'has_calibration': len(calibration_data) > 0
        }
        
        if lot and calibration_data:
            # Merge calibration polygon data with database status
            calibration_map = {spot['id']: spot for spot in calibration_data}
            
            # Get frame dimensions (assuming a standard resolution if not available)
            # This is used to calculate spot area in pixels
            frame_width = 1920  # Default, should match actual camera resolution
            frame_height = 1080
            
            for spot in lot.spots:
                latest_status = StatusUpdate.query.filter_by(spot_id=spot.id).order_by(StatusUpdate.timestamp.desc()).first()
                calibration = calibration_map.get(spot.spot_id, {})
                
                # Calculate if this is a small spot
                is_small_spot = False
                polygon_coords = calibration.get('polygon', [])
                if polygon_coords and len(polygon_coords) >= 3:
                    try:
                        from shapely.geometry import Polygon
                        pixel_coords = [(p['x'] * frame_width, p['y'] * frame_height) for p in polygon_coords]
                        spot_polygon = Polygon(pixel_coords)
                        spot_area = spot_polygon.area
                        is_small_spot = spot_area < 5000
                    except Exception as e:
                        logger.debug(f"Failed to calculate spot area: {e}")
                        pass
                
                spot_data = {
                    'id': spot.spot_id,
                    'polygon': polygon_coords,
                    'status': latest_status.status if latest_status else 'free',
                    'confidence': latest_status.confidence if latest_status else 0.0,
                    'vehicle': latest_status.vehicle_data if latest_status else None,
                    'color': calibration.get('color', '#10b981'),
                    'is_small': is_small_spot  # Add flag for small spots
                }
                overlay_data['spots'].append(spot_data)
        
        # Add ALL cached vehicle detections (not just matched ones)
        if lot_id in latest_detections:
            for detection in latest_detections[lot_id]:
                overlay_data['vehicles'].append({
                    'bbox': detection['bbox'],
                    'class': detection['class'],
                    'confidence': detection['confidence']
                })
            logger.debug(f"Added {len(latest_detections[lot_id])} vehicle detections to overlay")
        
        response = jsonify(overlay_data)
        # Add cache control headers to prevent browser caching
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
    except Exception as e:
        logger.error(f"Error getting detection overlay for lot {lot_id}: {e}")
        return jsonify({'error': str(e), 'spots': [], 'vehicles': [], 'has_calibration': False}), 500

@app.route('/api/camera/refresh', methods=['POST'])
@login_required
def refresh_camera():
    """Force reload camera from config"""
    try:
        load_camera_config()
        return jsonify({
            'success': True,
            'message': 'Camera reloaded',
            'camera_info': camera.get_info() if camera else None
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera/screenshot', methods=['POST'])
def save_screenshot():
    """Save current camera frame - UC-003"""
    try:
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        filepath = os.path.join(CONFIG['screenshot_folder'], filename)
        
        # Save the current frame
        if camera.save_frame(filepath):
            return jsonify({
                'success': True,
                'filename': filename,
                'path': filepath
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to capture frame'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/analytics/summary', methods=['GET'])
def analytics_summary():
    """Get analytics summary - UC-004"""
    # Use real parking data for analytics
    total = parking_data['total_spaces']
    occupied = parking_data['occupied_spaces']
    available = parking_data['available_spaces']
    
    # Calculate real metrics
    occupancy_rate = (occupied / total) if total > 0 else 0
    daily_average = occupied  # In production, calculate from historical data
    
    # Generate trend data (in production, pull from database)
    # For now, generate realistic-looking data based on current occupancy
    base = occupied
    trends = []
    for i in range(7):
        variance = random.randint(-5, 5)
        value = max(0, min(total, base + variance))
        trends.append(value)
    
    return jsonify({
        'daily_average': daily_average,
        'peak_hours': ['08:00-09:00', '17:00-18:00'],
        'occupancy_rate': occupancy_rate,
        'current_occupied': occupied,
        'current_available': available,
        'total_spaces': total,
        'trends': {
            'last_7_days': trends,
            'labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        }
    })

@app.route('/api/analytics/export', methods=['GET'])
def export_analytics():
    """Export analytics data - UC-004"""
    format_type = request.args.get('format', 'json')
    
    if format_type == 'csv':
        # TODO: Generate CSV
        return jsonify({'error': 'CSV export not yet implemented'}), 501
    
    return jsonify({
        'lot_id': parking_data['lot_id'],
        'export_date': datetime.now().isoformat(),
        'data': parking_data
    })

@app.route('/api/debug/calibration', methods=['GET'])
def debug_calibration():
    """Debug endpoint to check calibration data"""
    config_file = 'config.json'
    calibration_info = {
        'config_file_exists': os.path.exists(config_file),
        'total_spaces': parking_data['total_spaces'],
        'spaces_with_polygons': sum(1 for s in parking_data['spaces'] if s.get('polygon') and len(s['polygon']) > 0),
        'sample_space': parking_data['spaces'][0] if parking_data['spaces'] else None
    }
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            calibration_info['config_file_content'] = json.load(f)
    
    return jsonify(calibration_info)

@app.route('/api/camera/config', methods=['POST'])
@login_required
@limiter.limit("10 per minute")  # Lower limit for configuration changes
def set_camera_config():
    """Set new camera configuration"""
    global camera
    
    data = request.json
    camera_url = data.get('cameraUrl')
    camera_source = data.get('cameraSource')  # Can be empty
    extraction_pattern_type = data.get('extractionPatternType', 'auto')
    extraction_pattern_value = data.get('extractionPatternValue')

    if not camera_url:
        return jsonify({'error': 'Camera URL is required'}), 400

    # Stop and cleanup old camera feed completely
    if camera:
        logger.info("Stopping old camera feed")
        try:
            camera.stop()
        except Exception as e:
            logger.warning(f"Warning during camera stop: {e}")
        camera = None
        time.sleep(1)  # Give more time for complete cleanup

    # Save to config file
    config_file = 'config.json'
    existing_config = {}
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            try:
                existing_config = json.load(f)
            except json.JSONDecodeError:
                pass # Ignore if file is empty or invalid

    # Update camera config
    existing_config['camera_url'] = camera_url
    if camera_source:
        existing_config['camera_source'] = camera_source
    else:
        # If auto-detecting, remove the old source type
        if 'camera_source' in existing_config:
            del existing_config['camera_source']
    
    # Save extraction pattern settings
    existing_config['extraction_pattern_type'] = extraction_pattern_type
    if extraction_pattern_value:
        existing_config['extraction_pattern_value'] = extraction_pattern_value
    elif 'extraction_pattern_value' in existing_config:
        del existing_config['extraction_pattern_value']

    with open(config_file, 'w') as f:
        json.dump(existing_config, f, indent=2)

    # Create completely new camera with updated config
    logger.info(f"Creating new camera: {camera_source or 'auto'}")
    camera = create_camera_feed(camera_source or '', camera_url, extraction_pattern_type, extraction_pattern_value)
    logger.info(f"New camera initialized: {camera.get_info()}")

    return jsonify({
        'success': True,
        'message': 'Camera configuration updated. New feed loaded.',
        'camera_info': camera.get_info()
    })

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded errors"""
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': str(e.description)
    }), 429

# ============================================
# MULTI-LOT MANAGEMENT API
# ============================================

@app.route('/api/calibration/status', methods=['GET'])
def get_calibration_status():
    """Get calibration sync status - shows config vs database state"""
    try:
        # Get calibration from config
        config_spaces = []
        if os.path.exists('config.json'):
            with open('config.json', 'r') as f:
                config = json.load(f)
                config_spaces = config.get('calibration_data', [])
        
        # Get spots from database
        lot_id = main_config.get('default_lot_id', 'LOT-001')
        lot = ParkingLot.query.filter_by(public_id=lot_id).first()
        
        db_spots = []
        if lot:
            db_spots = [spot.spot_id for spot in Spot.query.filter_by(lot_id=lot.id).all()]
        
        config_spot_ids = [space['id'] for space in config_spaces]
        
        # Compare
        in_config_not_db = [sid for sid in config_spot_ids if sid not in db_spots]
        in_db_not_config = [sid for sid in db_spots if sid not in config_spot_ids]
        
        synced = len(in_config_not_db) == 0 and len(in_db_not_config) == 0
        
        return jsonify({
            'synced': synced,
            'lot_id': lot_id,
            'lot_exists': lot is not None,
            'config_spots': len(config_spaces),
            'db_spots': len(db_spots),
            'in_config_not_db': in_config_not_db,
            'in_db_not_config': in_db_not_config,
            'message': 'Calibration synced' if synced else 'Calibration out of sync'
        })
    except Exception as e:
        logger.error(f"Error checking calibration status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/lots', methods=['GET'])
def get_all_lots():
    """Get list of all parking lots"""
    lots = ParkingLot.query.all()
    return jsonify({
        'lots': [{
            'id': lot.id,  # Database ID for API calls
            'public_id': lot.public_id,  # Public display ID
            'name': lot.name,
            'total_spots': lot.total_spots,
            'camera_url': lot.camera_url,
            'camera_type': lot.camera_type
        } for lot in lots]
    })

@app.route('/api/lots', methods=['POST'])
@login_required
def create_lot():
    """Create a new parking lot"""
    data = request.json
    lot_id = data.get('lot_id')
    lot_name = data.get('name', f'Parking Lot {lot_id}')
    
    if not lot_id:
        return jsonify({'error': 'lot_id is required'}), 400
    
    # Check if lot already exists
    existing = ParkingLot.query.filter_by(public_id=lot_id).first()
    if existing:
        return jsonify({'error': 'Lot with this ID already exists'}), 409
    
    new_lot = ParkingLot(
        public_id=lot_id,
        name=lot_name,
        total_spots=0
    )
    db.session.add(new_lot)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'lot': {
            'id': new_lot.public_id,
            'name': new_lot.name,
            'total_spots': new_lot.total_spots
        }
    }), 201

@app.route('/api/lot/<string:lot_id>/camera', methods=['GET', 'PUT'])
def lot_camera_config(lot_id):
    """Get or update camera configuration for a specific lot"""
    # PUT requires authentication
    if request.method == 'PUT' and not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'}), 401
    
    lot = ParkingLot.query.filter_by(public_id=lot_id).first()
    
    if not lot:
        return jsonify({'error': 'Lot not found'}), 404
    
    if request.method == 'GET':
        return jsonify({
            'lot_id': lot.public_id,
            'camera_url': lot.camera_url,
            'camera_type': lot.camera_type,
            'extraction_pattern_type': lot.extraction_pattern_type,
            'extraction_pattern_value': lot.extraction_pattern_value
        })
    
    elif request.method == 'PUT':
        data = request.json
        lot.camera_url = data.get('camera_url')
        lot.camera_type = data.get('camera_type', 'website_embed')
        lot.extraction_pattern_type = data.get('extraction_pattern_type', 'auto')
        lot.extraction_pattern_value = data.get('extraction_pattern_value')
        
        try:
            db.session.commit()
            
            # If this is LOT-001 (default), reload the camera feed
            if lot.public_id == 'LOT-001':
                logger.info(f"Reloading camera for default lot")
                load_camera_config()
            
            return jsonify({
                'success': True,
                'lot_id': lot.public_id,
                'camera_url': lot.camera_url,
                'camera_type': lot.camera_type,
                'extraction_pattern_type': lot.extraction_pattern_type,
                'extraction_pattern_value': lot.extraction_pattern_value
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

@app.route('/api/lots/<string:lot_id>', methods=['DELETE'])
@login_required
def delete_lot(lot_id):
    """Delete a parking lot and all its data"""
    # Prevent deletion of default lot
    if lot_id == 'LOT-001':
        return jsonify({'success': False, 'error': 'Cannot delete the default lot (LOT-001)'}), 400
    
    lot = ParkingLot.query.filter_by(public_id=lot_id).first()
    
    if not lot:
        return jsonify({'success': False, 'error': f'Lot {lot_id} not found'}), 404
    
    try:
        # Delete all related data in correct order
        for spot in lot.spots:
            StatusUpdate.query.filter_by(spot_id=spot.id).delete()
            db.session.delete(spot)
        
        db.session.delete(lot)
        db.session.commit()
        
        logger.info(f"✓ Deleted lot {lot_id} and all associated data")
        
        return jsonify({'success': True, 'message': f'Lot {lot_id} deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting lot {lot_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/lots/<string:lot_id>', methods=['PUT'])
@login_required
def update_lot(lot_id):
    """Update parking lot information"""
    lot = ParkingLot.query.filter_by(public_id=lot_id).first_or_404()
    data = request.json
    
    if 'name' in data:
        lot.name = data['name']
    if 'total_spots' in data:
        lot.total_spots = data['total_spots']
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'lot': {
            'id': lot.public_id,
            'name': lot.name,
            'total_spots': lot.total_spots
        }
    })

@app.route('/api/lot/<string:lot_id>/status/cleanup', methods=['POST'])
@login_required
def cleanup_old_status_updates(lot_id):
    """Clean up old status updates, keeping only the latest N per spot"""
    try:
        lot = ParkingLot.query.filter_by(public_id=lot_id).first_or_404()
        data = request.json or {}
        keep_count = data.get('keep_count', 10)  # Keep last 10 updates per spot by default
        
        deleted_total = 0
        for spot in lot.spots:
            # Get all status updates for this spot, ordered by timestamp descending
            all_updates = StatusUpdate.query.filter_by(spot_id=spot.id).order_by(StatusUpdate.timestamp.desc()).all()
            
            if len(all_updates) > keep_count:
                # Delete all except the most recent N
                to_delete = all_updates[keep_count:]
                for update in to_delete:
                    db.session.delete(update)
                deleted_total += len(to_delete)
        
        db.session.commit()
        logger.info(f"Cleaned up {deleted_total} old status updates for lot '{lot_id}'")
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_total,
            'message': f'Cleaned up {deleted_total} old status updates'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error cleaning up status updates: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/lot/<string:lot_id>/status/history', methods=['GET'])
def get_spot_status_history(lot_id):
    """Get status history for a specific spot or all spots in a lot"""
    try:
        lot = ParkingLot.query.filter_by(public_id=lot_id).first_or_404()
        spot_id = request.args.get('spot_id')
        limit = int(request.args.get('limit', 50))
        
        if spot_id:
            # Get history for specific spot
            spot = Spot.query.filter_by(lot_id=lot.id, spot_id=spot_id).first_or_404()
            updates = StatusUpdate.query.filter_by(spot_id=spot.id).order_by(StatusUpdate.timestamp.desc()).limit(limit).all()
            
            history = [{
                'id': update.id,
                'status': update.status,
                'confidence': update.confidence,
                'timestamp': update.timestamp.isoformat(),
                'vehicle': update.vehicle_data
            } for update in updates]
            
            return jsonify({
                'spot_id': spot_id,
                'history': history,
                'count': len(history)
            })
        else:
            # Get summary of all spots
            summary = []
            for spot in lot.spots:
                latest = StatusUpdate.query.filter_by(spot_id=spot.id).order_by(StatusUpdate.timestamp.desc()).first()
                update_count = StatusUpdate.query.filter_by(spot_id=spot.id).count()
                
                summary.append({
                    'spot_id': spot.spot_id,
                    'latest_status': latest.status if latest else None,
                    'latest_timestamp': latest.timestamp.isoformat() if latest else None,
                    'update_count': update_count
                })
            
            return jsonify({
                'lot_id': lot_id,
                'spots': summary
            })
    except Exception as e:
        logger.error(f"Error getting status history: {e}")
        return jsonify({'error': str(e)}), 500

# Database Routes
@app.route('/api/lot/<string:lot_public_id>/status')
@limiter.limit("60 per minute")  # Higher limit for live status updates
def get_lot_status(lot_public_id):
    """Endpoint that generates a LotStatus object based on the latest data from the DB."""
    try:
        lot = ParkingLot.query.filter_by(public_id=lot_public_id).first_or_404()
    except Exception as e:
        logger.error(f"Error finding lot {lot_public_id}: {e}")
        return jsonify({"error": f"Lot not found: {lot_public_id}"}), 404

    all_spots = lot.spots
    spot_statuses = []

    free_spots = 0
    occupied_spots = 0

    for spot in all_spots:
        try:
            # Grabs the latest data for a spot
            latest_status = db.session.query(StatusUpdate).filter(StatusUpdate.spot_id == spot.id).order_by(StatusUpdate.timestamp.desc()).first()

            if latest_status:
                current_status = latest_status.status
                if current_status == 'free':
                    free_spots += 1
                elif current_status == 'occupied':
                    occupied_spots += 1
                else:
                    # Handle legacy or unknown status
                    logger.warning(f"Unknown status '{current_status}' for spot {spot.spot_id}, treating as occupied")
                    occupied_spots += 1
                
                spot_statuses.append({
                    "id": spot.spot_id,
                    "status": current_status,
                    "confidence": latest_status.confidence,
                    "timestamp": latest_status.timestamp.isoformat() if latest_status.timestamp else None,
                    "vehicle": latest_status.vehicle_data
                })
            else:
                # In the case of no status updates, default to free (not yet detected)
                logger.debug(f"No status updates found for spot {spot.spot_id}, defaulting to free")
                free_spots += 1
                spot_statuses.append({
                    "id": spot.spot_id,
                    "status": "free",
                    "confidence": 0.0,
                    "timestamp": None,
                    "vehicle": None
                })
        except Exception as e:
            logger.error(f"Error processing spot {spot.spot_id}: {e}")
            continue
        
    # Build the lot status response
    response = {
        "lot_id": lot.public_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_spaces": lot.total_spots,
        "available_spaces": free_spots,  # Frontend expects 'available_spaces'
        "occupied_spaces": occupied_spots,  # Frontend expects 'occupied_spaces'
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "spaces": spot_statuses
    }
    
    logger.debug(f"Status query for {lot_public_id}: {free_spots} free, {occupied_spots} occupied out of {lot.total_spots} total")

    return jsonify(response)


# ============================================
# MEDIA STORAGE API ENDPOINTS
# ============================================

@app.route('/api/media/storage/stats', methods=['GET'])
def get_media_storage_stats():
    """Get media storage statistics"""
    try:
        if not media_storage:
            return jsonify({"error": "Media storage not enabled"}), 503
        
        stats = media_storage.get_storage_stats(db)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting storage stats: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/media/<int:lot_id>/timeline', methods=['GET'])
def get_media_timeline(lot_id):
    """Get media timeline for a specific date"""
    try:
        if not media_storage:
            return jsonify({"error": "Media storage not enabled"}), 503
        
        # Get date parameter (default to today)
        date_str = request.args.get('date')
        if date_str:
            target_date = datetime.fromisoformat(date_str)
        else:
            target_date = datetime.now()
        
        timeline = media_storage.get_media_timeline(db, lot_id, target_date)
        
        return jsonify({
            'lot_id': lot_id,
            'date': target_date.date().isoformat(),
            'timeline': timeline
        })
    except Exception as e:
        logger.error(f"Error getting media timeline: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/media/<int:lot_id>/timerange', methods=['GET'])
def get_media_by_timerange(lot_id):
    """Get media files within a time range"""
    try:
        if not media_storage:
            return jsonify({"error": "Media storage not enabled"}), 503
        
        # Get time range parameters
        start_time_str = request.args.get('start_time')
        end_time_str = request.args.get('end_time')
        media_type = request.args.get('media_type')  # 'image', 'video', or None for all
        limit = int(request.args.get('limit', 100))
        
        if not start_time_str or not end_time_str:
            return jsonify({"error": "start_time and end_time required"}), 400
        
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)
        
        media_files = media_storage.get_media_by_timerange(
            db, lot_id, start_time, end_time, media_type, limit
        )
        
        return jsonify({
            'lot_id': lot_id,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'media_type': media_type,
            'count': len(media_files),
            'media': media_files
        })
    except Exception as e:
        logger.error(f"Error getting media by timerange: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/media/<int:media_id>/file', methods=['GET'])
def serve_media_file(media_id):
    """Serve a media file (image or video)"""
    try:
        if not media_storage:
            logger.error("Media storage not enabled")
            return jsonify({"error": "Media storage not enabled"}), 503
        
        # Get media record from database
        result = db.session.execute(
            db.text("SELECT file_path, media_type FROM media_storage WHERE id = :id"),
            {'id': media_id}
        ).fetchone()
        
        if not result:
            logger.error(f"Media {media_id} not found in database")
            return jsonify({"error": "Media not found"}), 404
        
        file_path = result.file_path
        media_type = result.media_type
        
        logger.info(f"Attempting to serve media {media_id}: {file_path}")
        
        # Check if file exists
        from pathlib import Path
        import os
        file_path_obj = Path(file_path)
        
        # Determine the correct path
        if file_path_obj.is_absolute():
            # Already absolute path
            pass
        elif str(file_path).startswith('media_archive'):
            # Old format: full path from project root (e.g., media_archive\images\lot10_...)
            file_path_obj = Path.cwd() / file_path
        else:
            # New format: relative to media_archive (e.g., images/2025-12-03/lot10_...)
            if media_storage and hasattr(media_storage, 'base_path'):
                file_path_obj = media_storage.base_path / file_path
            else:
                file_path_obj = Path.cwd() / 'media_archive' / file_path
        
        logger.info(f"Resolved path: {file_path_obj}, exists: {file_path_obj.exists()}")
        
        if not file_path_obj.exists():
            logger.error(f"File not found on disk: {file_path_obj}")
            return jsonify({"error": f"File not found on disk: {file_path_obj}"}), 404
        
        # Serve file using absolute path
        mimetype = 'image/jpeg' if media_type == 'image' else 'video/mp4'
        
        logger.info(f"Serving file with mimetype {mimetype}")
        
        # Read and send file directly
        with open(str(file_path_obj), 'rb') as f:
            from flask import Response
            return Response(f.read(), mimetype=mimetype)
    except Exception as e:
        logger.error(f"Error serving media file {media_id}: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/api/media/<int:media_id>/thumbnail', methods=['GET'])
def serve_media_thumbnail(media_id):
    """Serve a media thumbnail"""
    try:
        if not media_storage:
            return jsonify({"error": "Media storage not enabled"}), 503
        
        # Get media record from database
        result = db.session.execute(
            db.text("SELECT thumbnail_path FROM media_storage WHERE id = :id"),
            {'id': media_id}
        ).fetchone()
        
        if not result or not result.thumbnail_path:
            return jsonify({"error": "Thumbnail not found"}), 404
        
        thumb_path = result.thumbnail_path
        
        # Check if file exists
        from pathlib import Path
        thumb_path_obj = Path(thumb_path)
        
        # Determine the correct path (same logic as main file)
        if thumb_path_obj.is_absolute():
            # Already absolute path
            pass
        elif str(thumb_path).startswith('media_archive'):
            # Old format: full path from project root
            thumb_path_obj = Path.cwd() / thumb_path
        else:
            # New format: relative to media_archive
            if media_storage and hasattr(media_storage, 'base_path'):
                thumb_path_obj = media_storage.base_path / thumb_path
            else:
                thumb_path_obj = Path.cwd() / 'media_archive' / thumb_path
        
        if not thumb_path_obj.exists():
            return jsonify({"error": "Thumbnail not found on disk"}), 404
        
        # Serve file directly
        with open(str(thumb_path_obj), 'rb') as f:
            from flask import Response
            return Response(f.read(), mimetype='image/jpeg')
    except Exception as e:
        logger.error(f"Error serving thumbnail: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/media/<int:lot_id>/parking-state', methods=['GET'])
def get_parking_state_at_time(lot_id):
    """Get parking lot occupancy state at a specific time"""
    try:
        # Get timestamp
        timestamp_str = request.args.get('timestamp')
        if not timestamp_str:
            return jsonify({"error": "timestamp parameter required"}), 400
        
        timestamp = datetime.fromisoformat(timestamp_str)
        
        # Get lot from database
        lot = ParkingLot.query.get(lot_id)
        if not lot:
            return jsonify({"error": "Lot not found"}), 404
        
        # Get spots that existed at or before that time
        # Include spots even if they don't have history yet (show as unknown)
        spots_query = db.text("""
            SELECT 
                s.id, 
                s.spot_id as spot_number, 
                NULL as polygon, 
                NULL as created_at,
                (
                    SELECT status 
                    FROM status_update 
                    WHERE spot_id = s.id AND timestamp <= :timestamp
                    ORDER BY timestamp DESC 
                    LIMIT 1
                ) as status,
                (
                    SELECT confidence 
                    FROM status_update 
                    WHERE spot_id = s.id AND timestamp <= :timestamp
                    ORDER BY timestamp DESC 
                    LIMIT 1
                ) as confidence,
                NULL as vehicle_class
            FROM spot s
            WHERE s.lot_id = :lot_id
            ORDER BY s.spot_id
        """)
        
        results = db.session.execute(spots_query, {
            'lot_id': lot_id,
            'timestamp': timestamp
        }).fetchall()
        
        # Get calibration data for polygons
        lot = ParkingLot.query.get(lot_id)
        if not lot:
            return jsonify({"error": "Lot not found"}), 404
        
        # Load calibration from config
        config_file = 'config.json'
        calibration_polygons = {}
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                config = json.load(f)
                lot_key = f'calibration_data_{lot.public_id}'
                calibration_data = config.get(lot_key) or config.get('calibration_data', [])
                
                for cal_spot in calibration_data:
                    calibration_polygons[cal_spot.get('spot_number') or cal_spot.get('id')] = cal_spot.get('polygon', [])
        
        spots_data = []
        for r in results:
            # Get polygon from calibration
            polygon = calibration_polygons.get(r.spot_number, [])
            
            # Only include spot if it existed at this time
            # If no history, mark as unknown (gray)
            has_history = r.status is not None
            
            spots_data.append({
                'spot_number': r.spot_number,
                'polygon': polygon,
                'occupied': r.status == 'occupied' if has_history else None,  # None = unknown/no data yet
                'confidence': float(r.confidence) if r.confidence else 0,
                'vehicle_class': None,
                'has_history': has_history
            })
        
        return jsonify({
            'lot_id': lot_id,
            'timestamp': timestamp.isoformat(),
            'spots': spots_data
        })
    except Exception as e:
        logger.error(f"Error getting parking state: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("SPOTection - Parking Detection System")
    logger.info("Server: http://localhost:5000")
    if camera:
        logger.info(f"Camera: {camera.get_info()}")
    
    # Start detection if available
    if DETECTION_AVAILABLE:
        if start_detection():
            logger.info("Detection: ENABLED")
        else:
            logger.warning("Detection: FAILED TO START")
    else:
        logger.warning("Detection: DISABLED (install ultralytics and opencv-python)")
    
    logger.info("=" * 60)
    
    # Get host and port from config, with fallbacks
    host = main_config.get('host', '0.0.0.0')
    port = main_config.get('port', 5000)
    debug = main_config.get('debug', False)
    
    try:
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    finally:
        # Cleanup
        stop_detection()
        if camera:
            camera.stop()
