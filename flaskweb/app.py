from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import json
from datetime import datetime
import threading
import time
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import camera manager
from camera_manager import create_camera_feed

app = Flask(__name__)
CORS(app)

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
# CAMERA CONFIGURATION - Environment Variable Support
# ============================================
# Options: 'placeholder', 'webcam', 'http_mjpeg', 'http_snapshot', 'rtsp'
# Can be configured via environment variables or defaults below

# Get camera configuration from environment variables or use defaults
CAMERA_SOURCE = os.getenv(
    'CAMERA_SOURCE',
    'http_snapshot'  # Default
)

CAMERA_URL = os.getenv(
    'CAMERA_URL',
    'https://resource6.earthcam.net/v0/object/GtVJZlL4VnwZ3X0VJw8BsaKt465wCMA_ACspS6wYgxexPT5u4kEum-0uKZRnSm3SnJlL_j-pyYnDEWnIWTyt9Q!!.jpg'
)

CAMERA_TIMEOUT = int(os.getenv('CAMERA_TIMEOUT', '10'))  # seconds
CAMERA_MAX_RETRIES = int(os.getenv('CAMERA_MAX_RETRIES', '3'))

# Validate camera source
VALID_SOURCES = ['placeholder', 'webcam', 'http_mjpeg', 'http_snapshot', 'rtsp']
if CAMERA_SOURCE not in VALID_SOURCES:
    logger.warning(f"Invalid CAMERA_SOURCE '{CAMERA_SOURCE}'. Valid options: {VALID_SOURCES}")
    logger.warning("Falling back to 'placeholder' mode")
    CAMERA_SOURCE = 'placeholder'

# Validate URL is provided for sources that require it
if CAMERA_SOURCE in ['http_mjpeg', 'http_snapshot', 'rtsp'] and not CAMERA_URL:
    logger.error(f"CAMERA_URL required for source type '{CAMERA_SOURCE}'")
    logger.warning("Falling back to 'placeholder' mode")
    CAMERA_SOURCE = 'placeholder'

# Initialize camera feed with enhanced configuration
logger.info(f"Initializing camera: source={CAMERA_SOURCE}, timeout={CAMERA_TIMEOUT}s, retries={CAMERA_MAX_RETRIES}")
if CAMERA_URL:
    # Mask sensitive parts of URL in logs
    display_url = CAMERA_URL[:50] + '...' if len(CAMERA_URL) > 50 else CAMERA_URL
    logger.info(f"Camera URL: {display_url}")
    camera = create_camera_feed(CAMERA_SOURCE, CAMERA_URL)
else:
    camera = create_camera_feed(CAMERA_SOURCE)

# Log camera initialization status
camera_info = camera.get_info()
logger.info(f"Camera initialized: {camera_info}")

# Validate camera is working
if camera_info.get('health') == 'unhealthy':
    logger.error(f"Camera health check failed: {camera_info.get('last_error')}")
    logger.warning("Camera may not be working properly. Check configuration.")
elif camera_info.get('health') == 'healthy':
    logger.info("✅ Camera is healthy and ready")
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
            print(f"Error loading calibration: {e}")
    return []

# Initialize parking spaces from calibration or create empty list
calibration_data = load_calibration()
if calibration_data:
    parking_data['spaces'] = calibration_data
    parking_data['total_spaces'] = len(calibration_data)
    print(f"✅ Loaded {len(calibration_data)} calibrated parking spaces")
else:
    # Initialize mock parking spaces without polygons
    for i in range(50):
        parking_data['spaces'].append({
            'id': f'SPACE-{i+1:03d}',
            'status': 'available' if i < 23 else 'occupied',
            'polygon': []  # Empty - will be filled by calibration
        })
    print("⚠️ No calibration data found. Please calibrate spaces in /admin")

# Background thread to simulate real-time updates
def update_parking_data():
    """Simulate periodic updates from ML model"""
    while True:
        time.sleep(5)  # Update every 5 seconds
        # TODO: Replace with actual ML model detection
        import random
        available = random.randint(15, 35)
        parking_data['available_spaces'] = available
        parking_data['occupied_spaces'] = 50 - available
        parking_data['last_updated'] = datetime.now().isoformat()

# Start background thread
update_thread = threading.Thread(target=update_parking_data, daemon=True)
update_thread.start()

# Routes
@app.route('/')
def index():
    """Main dashboard - UC-001: View Real-Time Parking Availability"""
    return render_template('index.html')

@app.route('/live')
def live():
    """Live view - Real-time detection feed for users"""
    return render_template('live.html')

@app.route('/monitor')
def monitor():
    """Live monitoring - UC-003: Monitor Live Camera Feed"""
    return render_template('monitor.html')

@app.route('/analytics')
def analytics():
    """Analytics dashboard - UC-004: Generate Analytics Report"""
    return render_template('analytics.html')

@app.route('/admin')
def admin():
    """Admin panel - UC-002: Calibrate, UC-005: Configure"""
    return render_template('admin.html')

# API Endpoints
@app.route('/api/parking/status', methods=['GET'])
def get_parking_status():
    """Get current parking lot status"""
    return jsonify(parking_data)

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

@app.route('/api/config', methods=['GET', 'POST'])
def config():
    """Get or update configuration - UC-005"""
    config_file = 'config.json'
    
    if request.method == 'GET':
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return jsonify(json.load(f))
        return jsonify({
            'detection_threshold': 0.5,
            'update_interval': 5,
            'camera_resolution': '1920x1080',
            'model_version': 'v1.0',
            'calibration_data': []
        })
    
    elif request.method == 'POST':
        data = request.json
        
        # If calibration data is being saved, update parking_data
        if 'calibration_data' in data:
            global parking_data
            calibration_spaces = data['calibration_data']
            
            # Update parking data with calibrated spaces
            parking_data['spaces'] = calibration_spaces
            parking_data['total_spaces'] = len(calibration_spaces)
            
            # Randomly assign status for demo (in production, this comes from ML detection)
            import random
            available_count = 0
            for space in parking_data['spaces']:
                if 'status' not in space:
                    space['status'] = 'available' if random.random() > 0.5 else 'occupied'
                if space['status'] == 'available':
                    available_count += 1
            
            parking_data['available_spaces'] = available_count
            parking_data['occupied_spaces'] = len(calibration_spaces) - available_count
            
            print(f"✅ Saved {len(calibration_spaces)} calibrated parking spaces")
        
        # Save to file
        existing_config = {}
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                try:
                    existing_config = json.load(f)
                except:
                    pass
        
        # Merge with existing config
        existing_config.update(data)
        
        with open(config_file, 'w') as f:
            json.dump(existing_config, f, indent=2)
        
        return jsonify({'success': True, 'config': existing_config})

@app.route('/api/camera/feed', methods=['GET'])
def camera_feed():
    """Get latest camera frame"""
    try:
        # Get frame as base64 encoded image
        image_data = camera.get_frame('base64')

        return jsonify({
            'image_url': image_data,
            'timestamp': datetime.now().isoformat(),
            'source': CAMERA_SOURCE,
            'source_url': CAMERA_URL if CAMERA_URL else 'N/A'
        })
    except Exception as e:
        logger.error(f"Error getting camera feed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/camera/health', methods=['GET'])
def camera_health():
    """Get camera health status and diagnostic information"""
    try:
        camera_info = camera.get_info()
        return jsonify({
            'success': True,
            'camera_info': camera_info,
            'configuration': {
                'source_type': CAMERA_SOURCE,
                'timeout': CAMERA_TIMEOUT,
                'max_retries': CAMERA_MAX_RETRIES
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting camera health: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
    import random
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

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    print("🚗 Parking Detection System - Alpha")
    print("📍 Server starting on http://localhost:5000")
    print(f"📹 Camera Source: {CAMERA_SOURCE}")
    print("=" * 50)
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        # Cleanup camera on shutdown
        camera.stop()
        print("\n👋 Server stopped. Camera cleanup complete.")
