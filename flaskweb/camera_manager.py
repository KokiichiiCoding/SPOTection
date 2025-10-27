"""
Simple Camera Manager - Quick setup for alpha testing
"""

import base64
from datetime import datetime
from io import BytesIO
import time
import threading

try:
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("⚠️ PIL/Pillow not installed. Install with: pip install pillow")

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    print("⚠️ OpenCV not installed. Install with: pip install opencv-python")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️ Requests not installed. Install with: pip install requests")


class SimpleCameraFeed:
    """Simple camera feed for quick alpha testing"""
    
    def __init__(self, source_type='placeholder', source_url=None):
        self.source_type = source_type
        self.source_url = source_url
        self.current_frame = None
        self.last_update = None
        self.is_running = False
        self.thread = None
        
        if source_type == 'placeholder':
            self._create_placeholder()
        elif source_type == 'http_mjpeg':
            self._start_http_stream()
        elif source_type == 'http_snapshot':
            # HTTP snapshots are fetched on-demand
            pass
        elif source_type == 'webcam':
            self._start_webcam()
        elif source_type == 'rtsp':
            self._start_rtsp()
        else:
            self._create_placeholder()
    
    def _create_placeholder(self):
        """Create a placeholder image"""
        if not PILLOW_AVAILABLE:
            # Fallback without PIL
            self.placeholder_svg = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"><rect width="1280" height="720" fill="%231e293b"/><text x="640" y="340" font-size="32" fill="%2364748b" text-anchor="middle">Camera Feed Placeholder</text><text x="640" y="380" font-size="18" fill="%2364748b" text-anchor="middle">Connect your camera in camera_manager.py</text></svg>'
            return
        
        # Create with PIL
        img = Image.new('RGB', (1280, 720), color='#1e293b')
        draw = ImageDraw.Draw(img)
        
        # Try to load font
        try:
            font_large = ImageFont.truetype("arial.ttf", 36)
            font_small = ImageFont.truetype("arial.ttf", 20)
        except:
            try:
                font_large = ImageFont.truetype("Arial.ttf", 36)
                font_small = ImageFont.truetype("Arial.ttf", 20)
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
        
        # Draw camera icon
        draw.rectangle([590, 310, 690, 360], outline='#64748b', width=3)
        draw.ellipse([610, 325, 670, 385], outline='#64748b', width=3)
        
        # Draw text
        draw.text((640, 420), "Camera Feed Placeholder", fill='#64748b', anchor="mm", font=font_large)
        draw.text((640, 460), f"Mode: {self.source_type}", fill='#64748b', anchor="mm", font=font_small)
        
        if self.source_url:
            draw.text((640, 490), f"URL: {self.source_url[:50]}...", fill='#94a3b8', anchor="mm", font=font_small)
        else:
            draw.text((640, 490), "Configure camera in app.py", fill='#94a3b8', anchor="mm", font=font_small)
        
        if CV2_AVAILABLE:
            self.current_frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        else:
            self.current_frame = img
        
        self.last_update = datetime.now()
    
    def _start_http_stream(self):
        """Start HTTP MJPEG stream in background thread"""
        if not CV2_AVAILABLE or not REQUESTS_AVAILABLE:
            print("❌ OpenCV and Requests required for HTTP streams")
            self._create_placeholder()
            return
        
        print(f"📹 Starting HTTP stream: {self.source_url}")
        self.is_running = True
        self.thread = threading.Thread(target=self._http_stream_loop, daemon=True)
        self.thread.start()
    
    def _http_stream_loop(self):
        """Background loop for HTTP MJPEG stream"""
        while self.is_running:
            try:
                # For MJPEG streams
                response = requests.get(self.source_url, stream=True, timeout=10)
                bytes_data = bytes()
                
                for chunk in response.iter_content(chunk_size=1024):
                    bytes_data += chunk
                    # Look for JPEG markers
                    a = bytes_data.find(b'\xff\xd8')  # JPEG start
                    b = bytes_data.find(b'\xff\xd9')  # JPEG end
                    
                    if a != -1 and b != -1:
                        jpg = bytes_data[a:b+2]
                        bytes_data = bytes_data[b+2:]
                        
                        # Decode image
                        img_array = np.frombuffer(jpg, dtype=np.uint8)
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            self.current_frame = frame
                            self.last_update = datetime.now()
                
            except Exception as e:
                print(f"❌ HTTP stream error: {e}")
                self._create_placeholder()
                time.sleep(5)  # Wait before retry
    
    def _start_webcam(self):
        """Start webcam capture"""
        if not CV2_AVAILABLE:
            print("❌ OpenCV required for webcam")
            self._create_placeholder()
            return
        
        camera_index = int(self.source_url) if self.source_url else 0
        self.cap = cv2.VideoCapture(camera_index)
        
        if not self.cap.isOpened():
            print(f"❌ Failed to open webcam {camera_index}")
            self._create_placeholder()
            return
        
        print(f"✅ Webcam {camera_index} opened")
        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
    
    def _start_rtsp(self):
        """Start RTSP stream"""
        if not CV2_AVAILABLE:
            print("❌ OpenCV required for RTSP")
            self._create_placeholder()
            return
        
        self.cap = cv2.VideoCapture(self.source_url)
        
        if not self.cap.isOpened():
            print(f"❌ Failed to open RTSP stream: {self.source_url}")
            self._create_placeholder()
            return
        
        print(f"✅ RTSP stream opened")
        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
    
    def _capture_loop(self):
        """Background capture loop for OpenCV sources"""
        while self.is_running:
            try:
                if hasattr(self, 'cap') and self.cap.isOpened():
                    ret, frame = self.cap.read()
                    if ret:
                        self.current_frame = frame
                        self.last_update = datetime.now()
                    else:
                        print("⚠️ Failed to read frame")
                        time.sleep(1)
                else:
                    break
                
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                print(f"❌ Capture error: {e}")
                time.sleep(1)
    
    def _fetch_http_snapshot(self):
        """Fetch a single snapshot from HTTP URL"""
        if not REQUESTS_AVAILABLE or not CV2_AVAILABLE:
            return None
        
        try:
            response = requests.get(self.source_url, timeout=5)
            if response.status_code == 200:
                img_array = np.frombuffer(response.content, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                return frame
        except Exception as e:
            print(f"❌ HTTP snapshot error: {e}")
        return None
    
    def get_frame(self, format='base64'):
        """Get the current frame"""
        # For HTTP snapshots, fetch on-demand
        if self.source_type == 'http_snapshot':
            frame = self._fetch_http_snapshot()
            if frame is not None:
                self.current_frame = frame
                self.last_update = datetime.now()
        
        # Use current frame or placeholder
        frame = self.current_frame
        
        if frame is None:
            self._create_placeholder()
            frame = self.current_frame
        
        if not PILLOW_AVAILABLE and hasattr(self, 'placeholder_svg'):
            return self.placeholder_svg
        
        if format == 'base64':
            # Convert to base64
            if CV2_AVAILABLE and isinstance(frame, np.ndarray):
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                img_str = base64.b64encode(buffer).decode()
            else:
                buffered = BytesIO()
                frame.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
            
            return f'data:image/jpeg;base64,{img_str}'
        
        return frame
    
    def save_frame(self, filepath):
        """Save current frame to file"""
        try:
            frame = self.current_frame
            if frame is None:
                return False
            
            if CV2_AVAILABLE and isinstance(frame, np.ndarray):
                cv2.imwrite(filepath, frame)
            elif PILLOW_AVAILABLE:
                frame.save(filepath)
            else:
                return False
            return True
        except Exception as e:
            print(f"Error saving frame: {e}")
            return False
    
    def get_info(self):
        """Get camera info"""
        return {
            'source_type': self.source_type,
            'source_url': self.source_url,
            'status': 'running' if self.is_running else 'stopped',
            'last_update': self.last_update.isoformat() if self.last_update else None
        }
    
    def stop(self):
        """Cleanup"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
        if hasattr(self, 'cap'):
            self.cap.release()


def create_camera_feed(config_name='placeholder', custom_url=None):
    """
    Create a camera feed
    
    config_name options:
        - 'placeholder': Test placeholder
        - 'webcam': Computer webcam
        - 'http_mjpeg': MJPEG stream URL
        - 'http_snapshot': HTTP snapshot URL
        - 'rtsp': RTSP stream
    
    custom_url: Provide your own URL/path
    """
    print(f"📹 Creating camera feed: {config_name}")
    
    if config_name == 'placeholder':
        return SimpleCameraFeed('placeholder')
    
    elif config_name == 'webcam':
        return SimpleCameraFeed('webcam', '0')
    
    elif config_name == 'http_mjpeg' and custom_url:
        return SimpleCameraFeed('http_mjpeg', custom_url)
    
    elif config_name == 'http_snapshot' and custom_url:
        return SimpleCameraFeed('http_snapshot', custom_url)
    
    elif config_name == 'rtsp' and custom_url:
        return SimpleCameraFeed('rtsp', custom_url)
    
    else:
        print(f"⚠️ Unknown config or missing URL, using placeholder")
        return SimpleCameraFeed('placeholder')


# Test
if __name__ == '__main__':
    print("🎥 Testing Camera Manager\n")
    
    camera = create_camera_feed('placeholder')
    print(f"Camera info: {camera.get_info()}")
    
    frame = camera.get_frame('base64')
    print(f"Frame type: {type(frame)}")
    print(f"Frame starts with: {frame[:50] if isinstance(frame, str) else 'N/A'}")
    
    print("\n✅ Camera manager working!")
