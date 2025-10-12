#!/usr/bin/env python3
"""
Spotection Comprehensive Test Suite
Tests all major components before alpha release
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpotectionTestSuite:
    """Complete test suite for Spotection system"""
    
    def __init__(self):
        self.project_dir = Path(".")
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "passed": 0,
            "failed": 0,
            "total": 0
        }
    
    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
        if message:
            logger.info(f"  {message}")
        
        self.test_results["tests"].append({
            "name": test_name,
            "passed": passed,
            "message": message
        })
        
        if passed:
            self.test_results["passed"] += 1
        else:
            self.test_results["failed"] += 1
        self.test_results["total"] += 1
    
    def test_python_version(self) -> bool:
        """Test Python version"""
        version = sys.version_info
        passed = version.major >= 3 and version.minor >= 8
        self.log_test(
            "Python Version",
            passed,
            f"Python {version.major}.{version.minor}.{version.micro}"
        )
        return passed
    
    def test_dependencies(self) -> bool:
        """Test required dependencies"""
        required = [
            "cv2",
            "numpy",
            "shapely",
            "ultralytics",
            "fastapi",
            "uvicorn",
            "matplotlib",
            "psutil"
        ]
        
        missing = []
        for module in required:
            try:
                __import__(module)
            except ImportError:
                missing.append(module)
        
        passed = len(missing) == 0
        message = f"All dependencies installed" if passed else f"Missing: {', '.join(missing)}"
        self.log_test("Dependencies", passed, message)
        return passed
    
    def test_directory_structure(self) -> bool:
        """Test directory structure"""
        required_dirs = [
            "data",
            "output",
            "static",
            "webapp",
            "logs"
        ]
        
        missing = []
        for directory in required_dirs:
            if not (self.project_dir / directory).exists():
                missing.append(directory)
        
        passed = len(missing) == 0
        message = "All directories exist" if passed else f"Missing: {', '.join(missing)}"
        self.log_test("Directory Structure", passed, message)
        return passed
    
    def test_configuration(self) -> bool:
        """Test configuration file"""
        config_file = self.project_dir / "config.json"
        
        if not config_file.exists():
            self.log_test("Configuration", False, "config.json not found")
            return False
        
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            
            required_keys = [
                "model_path",
                "confidence_threshold",
                "overlap_threshold",
                "image_path",
                "spot_layout_path"
            ]
            
            missing_keys = [k for k in required_keys if k not in config]
            
            if missing_keys:
                self.log_test(
                    "Configuration",
                    False,
                    f"Missing keys: {', '.join(missing_keys)}"
                )
                return False
            
            self.log_test("Configuration", True, "Valid configuration")
            return True
            
        except Exception as e:
            self.log_test("Configuration", False, f"Error: {e}")
            return False
    
    def test_yolo_model(self) -> bool:
        """Test YOLO model"""
        try:
            from ultralytics import YOLO
            
            model_path = self.project_dir / "yolov8n.pt"
            if not model_path.exists():
                self.log_test("YOLO Model", False, "Model file not found")
                return False
            
            model = YOLO(str(model_path))
            self.log_test("YOLO Model", True, "Model loaded successfully")
            return True
            
        except Exception as e:
            self.log_test("YOLO Model", False, f"Error: {e}")
            return False
    
    def test_image_loading(self) -> bool:
        """Test image loading"""
        try:
            import cv2
            
            # Check for test image
            image_path = self.project_dir / "data" / "test_image.jpg"
            
            if not image_path.exists():
                self.log_test(
                    "Image Loading",
                    False,
                    "test_image.jpg not found in data/"
                )
                return False
            
            image = cv2.imread(str(image_path))
            
            if image is None:
                self.log_test("Image Loading", False, "Failed to load image")
                return False
            
            height, width = image.shape[:2]
            self.log_test(
                "Image Loading",
                True,
                f"Image loaded: {width}x{height}"
            )
            return True
            
        except Exception as e:
            self.log_test("Image Loading", False, f"Error: {e}")
            return False
    
    def test_spot_layout(self) -> bool:
        """Test spot layout"""
        try:
            layout_path = self.project_dir / "data" / "spot_layout.json"
            
            if not layout_path.exists():
                self.log_test(
                    "Spot Layout",
                    False,
                    "spot_layout.json not found - run calibration"
                )
                return False
            
            with open(layout_path, 'r') as f:
                spots = json.load(f)
            
            if not isinstance(spots, list):
                self.log_test("Spot Layout", False, "Invalid format")
                return False
            
            if len(spots) == 0:
                self.log_test("Spot Layout", False, "No spots defined")
                return False
            
            # Validate spot structure
            for spot in spots:
                if "id" not in spot or "polygon" not in spot:
                    self.log_test("Spot Layout", False, "Invalid spot structure")
                    return False
                
                if len(spot["polygon"]) != 4:
                    self.log_test("Spot Layout", False, "Polygon must have 4 points")
                    return False
            
            self.log_test(
                "Spot Layout",
                True,
                f"{len(spots)} spots defined"
            )
            return True
            
        except Exception as e:
            self.log_test("Spot Layout", False, f"Error: {e}")
            return False
    
    def test_detection_system(self) -> bool:
        """Test detection system"""
        try:
            from enhanced_spotection import EnhancedSpotectionSystem
            
            system = EnhancedSpotectionSystem()
            
            # Check if we have everything needed for detection
            image_path = self.project_dir / "data" / "test_image.jpg"
            layout_path = self.project_dir / "data" / "spot_layout.json"
            
            if not image_path.exists() or not layout_path.exists():
                self.log_test(
                    "Detection System",
                    False,
                    "Missing test image or spot layout"
                )
                return False
            
            # Try detection
            results = system.run_detection()
            
            if not results or "total_spots" not in results:
                self.log_test("Detection System", False, "Detection failed")
                return False
            
            self.log_test(
                "Detection System",
                True,
                f"Detected {results['free_spots']} free, {results['occupied_spots']} occupied"
            )
            return True
            
        except Exception as e:
            self.log_test("Detection System", False, f"Error: {e}")
            return False
    
    def test_auto_polygon_generator(self) -> bool:
        """Test auto polygon generator"""
        try:
            from auto_polygon_generator import AutoPolygonGenerator
            
            image_path = self.project_dir / "data" / "test_image.jpg"
            if not image_path.exists():
                self.log_test(
                    "Auto Polygon Generator",
                    False,
                    "Test image required"
                )
                return False
            
            generator = AutoPolygonGenerator(str(image_path))
            self.log_test("Auto Polygon Generator", True, "Initialized successfully")
            return True
            
        except Exception as e:
            self.log_test("Auto Polygon Generator", False, f"Error: {e}")
            return False
    
    def test_web_api(self) -> bool:
        """Test web API"""
        try:
            from webapp.spotection_web_api import app
            
            if app is None:
                self.log_test("Web API", False, "Failed to load API")
                return False
            
            self.log_test("Web API", True, "API loaded successfully")
            return True
            
        except Exception as e:
            self.log_test("Web API", False, f"Error: {e}")
            return False
    
    def test_web_interface(self) -> bool:
        """Test web interface"""
        index_path = self.project_dir / "static" / "index.html"
        
        if not index_path.exists():
            self.log_test("Web Interface", False, "index.html not found")
            return False
        
        # Check file size (should be substantial)
        size = index_path.stat().st_size
        if size < 1000:
            self.log_test("Web Interface", False, "index.html seems incomplete")
            return False
        
        self.log_test("Web Interface", True, f"HTML file exists ({size} bytes)")
        return True
    
    def test_performance_monitor(self) -> bool:
        """Test performance monitor"""
        try:
            from performance_monitor import PerformanceMonitor
            
            monitor = PerformanceMonitor()
            
            # Test basic functionality
            start = monitor.start_timer()
            import time
            time.sleep(0.1)
            elapsed = monitor.end_timer(start)
            
            if elapsed < 0.1:
                self.log_test("Performance Monitor", False, "Timer not working")
                return False
            
            self.log_test("Performance Monitor", True, "Monitor working correctly")
            return True
            
        except Exception as e:
            self.log_test("Performance Monitor", False, f"Error: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all tests"""
        logger.info("="*60)
        logger.info("SPOTECTION TEST SUITE")
        logger.info("="*60 + "\n")
        
        # Core tests
        logger.info("Core System Tests:")
        self.test_python_version()
        self.test_dependencies()
        self.test_directory_structure()
        self.test_configuration()
        
        # Model and data tests
        logger.info("\nModel and Data Tests:")
        self.test_yolo_model()
        self.test_image_loading()
        self.test_spot_layout()
        
        # Component tests
        logger.info("\nComponent Tests:")
        self.test_detection_system()
        self.test_auto_polygon_generator()
        self.test_performance_monitor()
        
        # Web tests
        logger.info("\nWeb Interface Tests:")
        self.test_web_api()
        self.test_web_interface()
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)
        logger.info(f"Total Tests: {self.test_results['total']}")
        logger.info(f"Passed: {self.test_results['passed']}")
        logger.info(f"Failed: {self.test_results['failed']}")
        
        pass_rate = (self.test_results['passed'] / self.test_results['total'] * 100) if self.test_results['total'] > 0 else 0
        logger.info(f"Pass Rate: {pass_rate:.1f}%")
        
        # Save results
        results_path = self.project_dir / "logs" / f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        results_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(results_path, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        
        logger.info(f"\nResults saved: {results_path}")
        
        # Alpha readiness check
        logger.info("\n" + "="*60)
        if pass_rate >= 80:
            logger.info("✓ SYSTEM READY FOR ALPHA RELEASE")
        else:
            logger.info("✗ SYSTEM NOT READY - Address failing tests")
        logger.info("="*60 + "\n")
        
        return pass_rate >= 80


def main():
    suite = SpotectionTestSuite()
    success = suite.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
