from flask import Flask, render_template, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import json
from datetime import datetime
import threading
import time

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

# Mock data for alpha testing (replace with actual ML model integration)
parking_data = {
    'lot_id': 'LOT-001',
    'total_spaces': 50,
    'available_spaces': 23,
    'occupied_spaces': 27,
    'last_updated': datetime.now().isoformat(),
    'spaces': []
}

# Initialize mock parking spaces
for i in range(50):
    parking_data['spaces'].append({
        'id': f'SPACE-{i+1:03d}',
        'status': 'available' if i < 23 else 'occupied',
        'polygon': []  # Calibration data
    })

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

@app.route('/admin')
def admin():
    """Admin panel - UC-002: Calibrate, UC-005: Configure"""
    return render_template('admin.html')

@app.route('/monitor')
def monitor():
    """Live monitoring - UC-003: Monitor Live Camera Feed"""
    return render_template('monitor.html')

@app.route('/analytics')
def analytics():
    """Analytics dashboard - UC-004: Generate Analytics Report"""
    return render_template('analytics.html')

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
            'model_version': 'v1.0'
        })
    
    elif request.method == 'POST':
        data = request.json
        with open(config_file, 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({'success': True, 'config': data})

@app.route('/api/camera/feed', methods=['GET'])
def camera_feed():
    """Get latest camera frame"""
    # TODO: Integrate with actual camera feed
    return jsonify({
        'image_url': '/static/images/placeholder_feed.jpg',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/camera/screenshot', methods=['POST'])
def save_screenshot():
    """Save current camera frame - UC-003"""
    # TODO: Capture actual frame from camera
    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    filepath = os.path.join(CONFIG['screenshot_folder'], filename)
    
    return jsonify({
        'success': True,
        'filename': filename,
        'path': filepath
    })

@app.route('/api/analytics/summary', methods=['GET'])
def analytics_summary():
    """Get analytics summary - UC-004"""
    # TODO: Generate from historical data
    return jsonify({
        'daily_average': 28.5,
        'peak_hours': ['08:00-09:00', '17:00-18:00'],
        'occupancy_rate': 0.65,
        'trends': {
            'last_7_days': [45, 52, 48, 55, 50, 49, 54],
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
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=True)
