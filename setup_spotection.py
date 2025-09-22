#!/usr/bin/env python3
"""
Spotection Setup and Usage Script
CS 490 Senior Capstone Project

This script helps set up and run the Spotection parking detection system.
"""

import os
import sys
import subprocess
import json
import argparse
from pathlib import Path

def create_directory_structure():
    """Create necessary directories for the project"""
    directories = [
        "data",
        "output", 
        "static",
        "models",
        "logs"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created directory: {directory}/")

def install_requirements():
    """Install required Python packages"""
    requirements = [
        "ultralytics",
        "opencv-python", 
        "shapely",
        "numpy",
        "fastapi",
        "uvicorn[standard]",
        "python-multipart",
        "websockets"
    ]
    
    print("Installing required packages...")
    for package in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            print(f"✓ Installed: {package}")
        except subprocess.CalledProcessError as e:
            print(f"✗ Failed to install {package}: {e}")
            return False
    
    return True

def download_yolo_model():
    """Download YOLOv8 model if not present"""
    model_path = "yolov8n.pt"
    if not os.path.exists(model_path):
        print("Downloading YOLOv8 model...")
        try:
            from ultralytics import YOLO
            model = YOLO("yolov8n.pt")  # This will download the model
            print("✓ YOLOv8 model downloaded successfully")
        except Exception as e:
            print(f"✗ Failed to download YOLOv8 model: {e}")
            return False
    else:
        print("✓ YOLOv8 model already present")
    
    return True

def create_sample_config():
    """Create a sample configuration file"""
    config = {
        "model_path": "yolov8n.pt",
        "confidence_threshold": 0.3,
        "overlap_threshold": 0.15,
        "image_path": "data/test_image.jpg",
        "spot_layout_path": "data/spot_layout.json",
        "output_dir": "output/"
    }
    
    with open("config.json", "w", encoding='utf-8') as f:
        json.dump(config, f, indent=2)
    
    print("✓ Created config.json")

def create_sample_html():
    """Create a simple web interface"""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spotection - Parking Detection System</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        .stats {
            display: flex;
            justify-content: space-around;
            padding: 20px;
            background: #f8f9fa;
        }
        .stat-card {
            text-align: center;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            min-width: 120px;
        }
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }
        .stat-label {
            color: #666;
            margin-top: 5px;
        }
        .spots-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
            padding: 20px;
        }
        .spot-card {
            padding: 15px;
            border-radius: 8px;
            border: 2px solid #ddd;
            background: white;
        }
        .spot-free {
            border-color: #28a745;
            background-color: #d4edda;
        }
        .spot-occupied {
            border-color: #dc3545;
            background-color: #f8d7da;
        }
        .spot-unknown {
            border-color: #ffc107;
            background-color: #fff3cd;
        }
        .controls {
            padding: 20px;
            text-align: center;
            border-top: 1px solid #ddd;
        }
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            margin: 0 10px;
            font-size: 16px;
        }
        button:hover {
            background: #5a6fd8;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Spotection</h1>
            <p>AI-Powered Parking Detection System</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number" id="total-spots">-</div>
                <div class="stat-label">Total Spots</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="free-spots">-</div>
                <div class="stat-label">Free Spots</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="occupied-spots">-</div>
                <div class="stat-label">Occupied</div>
            </div>
        </div>
        
        <div id="spots-container" class="spots-grid">
            <div class="loading">Loading parking data...</div>
        </div>
        
        <div class="controls">
            <button onclick="refreshData()">Refresh</button>
            <button onclick="window.open('/api/lots/main_lot/image', '_blank')">View Image</button>
            <button onclick="window.open('/admin', '_blank')">Admin Panel</button>
        </div>
    </div>

    <script>
        let socket = null;
        
        async function refreshData() {
            try {
                const response = await fetch('/api/lots/main_lot/status');
                const data = await response.json();
                updateDisplay(data);
            } catch (error) {
                console.error('Error fetching data:', error);
                document.getElementById('spots-container').innerHTML = 
                    '<div class="loading">Error loading data. Please try again.</div>';
            }
        }
        
        function updateDisplay(data) {
            // Update stats
            document.getElementById('total-spots').textContent = data.total_spots;
            document.getElementById('free-spots').textContent = data.free_spots;
            document.getElementById('occupied-spots').textContent = data.occupied_spots;
            
            // Update spots
            const container = document.getElementById('spots-container');
            container.innerHTML = data.spots.map(spot => `
                <div class="spot-card spot-${spot.status.toLowerCase()}">
                    <h3>${spot.id}</h3>
                    <p><strong>${spot.status}</strong></p>
                    ${spot.vehicle ? `<p>Vehicle: ${spot.vehicle.class}</p>` : ''}
                    <p>Confidence: ${(spot.confidence * 100).toFixed(1)}%</p>
                    <small>Updated: ${new Date(spot.timestamp).toLocaleTimeString()}</small>
                </div>
            `).join('');
        }
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            socket = new WebSocket(wsUrl);
            
            socket.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'status_update') {
                    updateDisplay({
                        total_spots: data.spots.length,
                        free_spots: data.spots.filter(s => s.status === 'FREE').length,
                        occupied_spots: data.spots.filter(s => s.status === 'OCCUPIED').length,
                        spots: data.spots
                    });
                }
            };
            
            socket.onclose = function() {
                console.log('WebSocket disconnected, retrying in 5 seconds...');
                setTimeout(connectWebSocket, 5000);
            };
        }
        
        // Initialize
        refreshData();
        connectWebSocket();
        
        // Refresh every 30 seconds as fallback
        setInterval(refreshData, 30000);
    </script>
</body>
</html>"""
    
    with open("static/index.html", "w", encoding='utf-8') as f:
        f.write(html_content)
    
    print("✓ Created web interface at static/index.html")

def setup_project():
    """Complete project setup"""
    print("Setting up Spotection parking detection system...")
    print("=" * 50)
    
    # Create directories
    create_directory_structure()
    
    # Install requirements
    if not install_requirements():
        print("❌ Failed to install requirements")
        return False
    
    # Download YOLO model
    if not download_yolo_model():
        print("❌ Failed to download YOLO model")
        return False
    
    # Create config
    create_sample_config()
    
    # Create web interface
    create_sample_html()
    
    print("\n" + "=" * 50)
    print("Setup complete!")
    print("\nNext steps:")
    print("1. Add your parking lot image to: data/test_image.jpg")
    print("2. Run calibration: python spotection_system.py --calibrate")
    print("3. Test detection: python spotection_system.py")
    print("4. Start web server: python webapp/spotection_web_api.py")
    print("\nWeb interface will be available at: http://localhost:8000")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Spotection setup and management")
    parser.add_argument("--setup", action="store_true", help="Run complete project setup")
    parser.add_argument("--calibrate", action="store_true", help="Run spot calibration tool")
    parser.add_argument("--detect", action="store_true", help="Run detection")
    parser.add_argument("--serve", action="store_true", help="Start web server")
    parser.add_argument("--image", help="Path to parking lot image")
    
    args = parser.parse_args()
    
    if args.setup:
        setup_project()
    elif args.calibrate:
        from spotection_system import SpotectionSystem
        system = SpotectionSystem()
        if args.image:
            system.config["image_path"] = args.image
        system.interactive_polygon_drawer(
            system.config["image_path"],
            system.config["spot_layout_path"]
        )
    elif args.detect:
        from spotection_system import SpotectionSystem
        system = SpotectionSystem()
        if args.image:
            system.config["image_path"] = args.image
        system.run_detection()
    elif args.serve:
        print("Starting Spotection web server...")
        import uvicorn
        from spotection_web_api import app
        uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
    else:
        print("Spotection - AI Parking Detection System")
        print("Use --help to see available commands")
        print("\nQuick start:")
        print("1. python setup_spotection.py --setup")
        print("2. python setup_spotection.py --calibrate --image your_image.jpg")
        print("3. python setup_spotection.py --detect")
        print("4. python setup_spotection.py --serve")

if __name__ == "__main__":
    main()