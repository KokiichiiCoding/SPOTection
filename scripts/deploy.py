#!/usr/bin/env python3
"""
Spotection Alpha Deployment Script
Complete setup and deployment for alpha release
"""

import os
import sys
import subprocess
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SpotectionAlphaDeployment:
    """Complete alpha deployment manager"""
    
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)
        self.config_file = self.project_dir / "config.json"
        
    def check_python_version(self):
        """Verify Python version"""
        logger.info("Checking Python version...")
        version = sys.version_info
        
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            logger.error("Python 3.8+ required")
            return False
        
        logger.info(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    
    def create_directory_structure(self):
        """Create all necessary directories"""
        logger.info("Creating directory structure...")
        
        directories = [
            "data",
            "output",
            "static",
            "static/css",
            "static/js",
            "models",
            "logs",
            "cnrpark_data",
            "training_data",
            "webapp",
            "tests"
        ]
        
        for directory in directories:
            dir_path = self.project_dir / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"✓ Created: {directory}/")
        
        return True
    
    def install_dependencies(self, use_trusted_hosts: bool = False):
        """Install Python dependencies"""
        logger.info("Installing dependencies...")
        
        requirements_file = self.project_dir / "requirements.txt"
        
        if not requirements_file.exists():
            logger.error("requirements.txt not found!")
            return False
        
        cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)]
        
        if use_trusted_hosts:
            cmd.extend([
                "--trusted-host", "pypi.org",
                "--trusted-host", "pypi.python.org",
                "--trusted-host", "files.pythonhosted.org"
            ])
        
        try:
            subprocess.run(cmd, check=True)
            logger.info("✓ Dependencies installed")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Dependency installation failed: {e}")
            return False
    
    def download_models(self):
        """Download required models"""
        logger.info("Downloading models...")
        
        try:
            from ultralytics import YOLO
            
            # Download YOLOv8 model
            model_path = self.project_dir / "yolov8n.pt"
            if not model_path.exists():
                logger.info("Downloading YOLOv8n model...")
                model = YOLO("yolov8n.pt")
                logger.info("✓ YOLOv8n model downloaded")
            else:
                logger.info("✓ YOLOv8n model already present")
            
            return True
            
        except Exception as e:
            logger.error(f"Model download failed: {e}")
            return False
    
    def create_default_config(self):
        """Create default configuration file"""
        logger.info("Creating configuration...")
        
        config = {
            "model_path": "yolov8n.pt",
            "cnrpark_model_path": "runs/detect/cnrpark_finetuned/weights/best.pt",
            "use_cnrpark_model": False,
            "confidence_threshold": 0.25,
            "overlap_threshold": 0.15,
            "image_path": "data/test_image.jpg",
            "spot_layout_path": "data/spot_layout.json",
            "output_dir": "output/",
            "vehicle_classes": ["car", "truck", "bus", "van", "motorcycle", "bicycle"],
            "auto_generate_spots": True,
            "enable_tracking": True,
            "save_debug_images": True,
            "api": {
                "host": "0.0.0.0",
                "port": 8000,
                "reload": True
            },
            "logging": {
                "level": "INFO",
                "file": "logs/spotection.log"
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"✓ Configuration created: {self.config_file}")
        return True
    
    def setup_web_interface(self):
        """Setup enhanced web interface"""
        logger.info("Setting up web interface...")
        
        # Create enhanced index.html
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spotection Alpha - Parking Detection System</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        
        .header h1 {
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .version-badge {
            background: rgba(255,255,255,0.2);
            padding: 5px 15px;
            border-radius: 20px;
            display: inline-block;
            font-size: 0.9em;
        }
        
        .dashboard {
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        
        .stats-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
            border-bottom: 2px solid #e9ecef;
        }
        
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
            transition: transform 0.2s;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        
        .stat-number {
            font-size: 2.5em;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .stat-label {
            color: #6c757d;
            margin-top: 10px;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .main-content {
            padding: 30px;
        }
        
        .section {
            margin-bottom: 30px;
        }
        
        .section-title {
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #333;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #28a745;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .spots-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px;
        }
        
        .spot-card {
            background: white;
            border: 2px solid #dee2e6;
            border-radius: 10px;
            padding: 20px;
            transition: all 0.3s;
        }
        
        .spot-card.free {
            border-color: #28a745;
            background: linear-gradient(135deg, #d4edda 0%, #c3e6cb 100%);
        }
        
        .spot-card.occupied {
            border-color: #dc3545;
            background: linear-gradient(135deg, #f8d7da 0%, #f5c6cb 100%);
        }
        
        .spot-card.unknown {
            border-color: #ffc107;
            background: linear-gradient(135deg, #fff3cd 0%, #ffe8a1 100%);
        }
        
        .spot-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .spot-id {
            font-size: 1.3em;
            font-weight: bold;
            color: #333;
        }
        
        .spot-status {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .status-free {
            background: #28a745;
            color: white;
        }
        
        .status-occupied {
            background: #dc3545;
            color: white;
        }
        
        .status-unknown {
            background: #ffc107;
            color: #333;
        }
        
        .spot-details {
            color: #6c757d;
            font-size: 0.9em;
        }
        
        .spot-details div {
            margin: 5px 0;
        }
        
        .controls {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            padding: 20px 30px;
            background: #f8f9fa;
            border-top: 2px solid #e9ecef;
        }
        
        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 1em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        }
        
        .btn-secondary {
            background: #6c757d;
            color: white;
        }
        
        .btn-secondary:hover {
            background: #5a6268;
        }
        
        .loading {
            text-align: center;
            padding: 60px;
            color: #6c757d;
        }
        
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 50px;
            height: 50px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .last-update {
            text-align: center;
            padding: 15px;
            color: #6c757d;
            font-size: 0.9em;
            border-top: 1px solid #e9ecef;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚗 Spotection</h1>
            <p style="font-size: 1.2em; margin: 10px 0;">AI-Powered Parking Detection System</p>
            <span class="version-badge">Alpha v1.0</span>
        </div>
        
        <div class="dashboard">
            <div class="stats-bar">
                <div class="stat-card">
                    <div class="stat-number" id="total-spots">-</div>
                    <div class="stat-label">Total Spots</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="free-spots">-</div>
                    <div class="stat-label">Available</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="occupied-spots">-</div>
                    <div class="stat-label">Occupied</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="occupancy-rate">-</div>
                    <div class="stat-label">Occupancy Rate</div>
                </div>
            </div>
            
            <div class="main-content">
                <div class="section">
                    <div class="section-title">
                        <div class="status-indicator"></div>
                        Live Parking Status
                    </div>
                    
                    <div id="spots-container" class="spots-grid">
                        <div class="loading">
                            <div class="spinner"></div>
                            <p>Loading parking data...</p>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="controls">
                <button class="btn btn-primary" onclick="refreshData()">
                    🔄 Refresh
                </button>
                <button class="btn btn-secondary" onclick="window.open('/api/lots/main_lot/image', '_blank')">
                    📷 View Image
                </button>
                <button class="btn btn-secondary" onclick="window.open('/admin', '_blank')">
                    ⚙️ Admin Panel
                </button>
                <button class="btn btn-secondary" onclick="window.open('/api/docs', '_blank')">
                    📚 API Docs
                </button>
            </div>
            
            <div class="last-update">
                Last updated: <span id="last-update-time">-</span>
            </div>
        </div>
    </div>

    <script>
        let socket = null;
        let isConnected = false;
        
        async function refreshData() {
            try {
                const response = await fetch('/api/lots/main_lot/status');
                const data = await response.json();
                updateDisplay(data);
            } catch (error) {
                console.error('Error fetching data:', error);
                document.getElementById('spots-container').innerHTML = 
                    '<div class="loading"><p style="color: #dc3545;">Error loading data. Please try again.</p></div>';
            }
        }
        
        function updateDisplay(data) {
            // Update stats
            document.getElementById('total-spots').textContent = data.total_spots;
            document.getElementById('free-spots').textContent = data.free_spots;
            document.getElementById('occupied-spots').textContent = data.occupied_spots;
            
            const occupancyRate = ((data.occupied_spots / data.total_spots) * 100).toFixed(1);
            document.getElementById('occupancy-rate').textContent = occupancyRate + '%';
            
            // Update last update time
            document.getElementById('last-update-time').textContent = 
                new Date(data.timestamp).toLocaleString();
            
            // Update spots
            const container = document.getElementById('spots-container');
            container.innerHTML = data.spots.map(spot => {
                const statusClass = spot.status.toLowerCase();
                return `
                    <div class="spot-card ${statusClass}">
                        <div class="spot-header">
                            <div class="spot-id">${spot.id}</div>
                            <div class="spot-status status-${statusClass}">${spot.status}</div>
                        </div>
                        <div class="spot-details">
                            ${spot.vehicle ? `
                                <div><strong>Vehicle:</strong> ${spot.vehicle.class}</div>
                                <div><strong>Confidence:</strong> ${(spot.vehicle.confidence * 100).toFixed(1)}%</div>
                            ` : '<div>No vehicle detected</div>'}
                            <div><strong>Detection:</strong> ${(spot.confidence * 100).toFixed(1)}%</div>
                            <div style="font-size: 0.8em; margin-top: 8px; color: #999;">
                                ${new Date(spot.timestamp).toLocaleTimeString()}
                            </div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            socket = new WebSocket(wsUrl);
            
            socket.onopen = () => {
                console.log('WebSocket connected');
                isConnected = true;
                document.querySelector('.status-indicator').style.background = '#28a745';
            };
            
            socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.type === 'status_update') {
                    updateDisplay({
                        total_spots: data.spots.length,
                        free_spots: data.spots.filter(s => s.status === 'FREE').length,
                        occupied_spots: data.spots.filter(s => s.status === 'OCCUPIED').length,
                        timestamp: data.timestamp,
                        spots: data.spots
                    });
                }
            };
            
            socket.onclose = () => {
                console.log('WebSocket disconnected');
                isConnected = false;
                document.querySelector('.status-indicator').style.background = '#dc3545';
                setTimeout(connectWebSocket, 5000);
            };
            
            socket.onerror = (error) => {
                console.error('WebSocket error:', error);
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
        
        index_path = self.project_dir / "static" / "index.html"
        with open(index_path, 'w') as f:
            f.write(html_content)
        
        logger.info(f"✓ Web interface created: {index_path}")
        return True
    
    def run_initial_setup(self):
        """Run initial setup wizard"""
        logger.info("\n" + "="*60)
        logger.info("SPOTECTION ALPHA SETUP")
        logger.info("="*60 + "\n")
        
        # Check if test image exists
        test_image = self.project_dir / "data" / "test_image.jpg"
        if not test_image.exists():
            logger.warning("No test image found at data/test_image.jpg")
            logger.info("Please add your parking lot image to data/test_image.jpg")
            logger.info("You can use the auto-generation tool later:")
            logger.info("  python auto_polygon_generator.py --image data/test_image.jpg")
        else:
            logger.info("✓ Test image found")
            
            # Offer to auto-generate spots
            logger.info("\nWould you like to auto-generate parking spot polygons?")
            logger.info("This will analyze the image and create spot definitions.")
            
            try:
                response = input("Auto-generate spots? (y/n): ").lower()
                if response == 'y':
                    logger.info("Running auto-generation...")
                    try:
                        from auto_polygon_generator import AutoPolygonGenerator
                        generator = AutoPolygonGenerator(str(test_image))
                        generator.auto_generate()
                    except Exception as e:
                        logger.error(f"Auto-generation failed: {e}")
                        logger.info("You can run manual calibration:")
                        logger.info("  python complete_calibration_tool.py")
            except KeyboardInterrupt:
                logger.info("\nSkipping auto-generation")
        
        return True
    
    def create_test_script(self):
        """Create a simple test script"""
        test_script = """#!/usr/bin/env python3
# Quick test script for Spotection

import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

def test_detection():
    from enhanced_spotection import EnhancedSpotectionSystem
    
    print("Testing Spotection System...")
    
    try:
        system = EnhancedSpotectionSystem()
        print("✓ System initialized")
        
        # Run detection
        results = system.run_detection()
        
        if results:
            print("\\n✓ Detection successful!")
            print(f"  Free spots: {results['free_spots']}")
            print(f"  Occupied: {results['occupied_spots']}")
            print(f"  Total: {results['total_spots']}")
            return True
        else:
            print("✗ Detection failed")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_detection()
    sys.exit(0 if success else 1)
"""
        
        test_path = self.project_dir / "test_spotection.py"
        with open(test_path, 'w') as f:
            f.write(test_script)
        
        # Make executable on Unix systems
        try:
            os.chmod(test_path, 0o755)
        except:
            pass
        
        logger.info(f"✓ Test script created: {test_path}")
        return True
    
    def deploy(self, skip_deps: bool = False, use_trusted_hosts: bool = False):
        """Run complete deployment"""
        logger.info("Starting Spotection Alpha Deployment...")
        
        steps = [
            ("Checking Python version", self.check_python_version),
            ("Creating directories", self.create_directory_structure),
            ("Creating configuration", self.create_default_config),
            ("Setting up web interface", self.setup_web_interface),
            ("Creating test script", self.create_test_script),
        ]
        
        if not skip_deps:
            steps.insert(2, ("Installing dependencies", 
                           lambda: self.install_dependencies(use_trusted_hosts)))
            steps.insert(3, ("Downloading models", self.download_models))
        
        for step_name, step_func in steps:
            logger.info(f"\n{step_name}...")
            if not step_func():
                logger.error(f"Failed: {step_name}")
                return False
        
        # Run initial setup
        self.run_initial_setup()
        
        logger.info("\n" + "="*60)
        logger.info("DEPLOYMENT COMPLETE!")
        logger.info("="*60)
        logger.info("\nNext steps:")
        logger.info("1. Add parking lot image: data/test_image.jpg")
        logger.info("2. Generate spots: python auto_polygon_generator.py --image data/test_image.jpg")
        logger.info("3. Test detection: python test_spotection.py")
        logger.info("4. Start web server: python webapp/spotection_web_api.py")
        logger.info("\nWeb interface: http://localhost:8000")
        logger.info("API docs: http://localhost:8000/docs")
        logger.info("\nFor CNRPark dataset integration:")
        logger.info("  python cnrpark_loader.py --download --prepare --yolo --train")
        
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Spotection Alpha Deployment")
    parser.add_argument("--skip-deps", action="store_true",
                       help="Skip dependency installation")
    parser.add_argument("--trusted-hosts", action="store_true",
                       help="Use trusted hosts for pip (for SSL issues)")
    parser.add_argument("--project-dir", default=".",
                       help="Project directory")
    
    args = parser.parse_args()
    
    deployer = SpotectionAlphaDeployment(args.project_dir)
    success = deployer.deploy(
        skip_deps=args.skip_deps,
        use_trusted_hosts=args.trusted_hosts
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
