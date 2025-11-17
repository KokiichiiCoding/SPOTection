"""
Simple Camera Manager - Quick setup for alpha testing
"""

import base64
from datetime import datetime
from io import BytesIO
import time
import threading
import os

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


def autodetect_source_type(url: str) -> str:
    """Automatically detect camera source type from URL"""
    if "youtube.com" in url or "youtu.be" in url:
        return 'youtube'
        
    # Check for RTSP
    if url.lower().startswith('rtsp://'):
        return 'rtsp'
        
    # Check for local video file
    if os.path.exists(url):
        return 'video_file'
        
    # Check for webcam index
    if url.isdigit():
        return 'webcam'
        
    # Check for common stream paths (MJPEG)
    if any(ext in url.lower() for ext in ['.mjpg', 'mjpeg.cgi', 'video.cgi', 'axis-cgi']):
        return 'http_mjpeg'
    
    # Check for common snapshot/image paths
    if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', 'snapshot.cgi', 'image.jpg', 'current.jpg']):
        return 'http_snapshot'
        
    # Check for insecam.org or similar camera websites
    if 'insecam' in url.lower() or 'webcamtaxi' in url.lower() or 'earthcam' in url.lower():
        return 'website_embed'
        
    # Default to website embed for HTTP/HTTPS links (try to extract stream)
    if url.lower().startswith('http'):
        return 'website_embed'
        
    return 'unknown'


class SimpleCameraFeed:
    """Simple camera feed for quick alpha testing"""
    
    def __init__(self, source_type='placeholder', source_url=None):
        if source_type in [None, '', 'auto', 'autodetect']:
            self.source_type = autodetect_source_type(source_url)
            print(f"ℹ️ Auto-detected source type: {self.source_type}")
        else:
            self.source_type = source_type
            
        self.source_url = source_url
        self.current_frame = None
        self.last_update = None
        self.is_running = False
        self.thread = None
        
        if self.source_type == 'placeholder':
            self._create_placeholder()
        elif self.source_type == 'http_mjpeg':
            self._start_http_stream()
        elif self.source_type == 'http_snapshot':
            # HTTP snapshots are fetched on-demand
            pass
        elif self.source_type == 'website_embed':
            # Website embeds need stream URL extraction
            self._extract_stream_url()
        elif self.source_type == 'webcam':
            self._start_webcam()
        elif self.source_type == 'rtsp':
            self._start_rtsp()
        elif self.source_type == 'video_file':
            self._start_video_file()
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
    
    def _start_video_file(self):
        """Start video file playback"""
        if not CV2_AVAILABLE:
            print("❌ OpenCV required for video files")
            self._create_placeholder()
            return
        
        self.cap = cv2.VideoCapture(self.source_url)
        
        if not self.cap.isOpened():
            print(f"❌ Failed to open video file: {self.source_url}")
            self._create_placeholder()
            return
            
        print(f"✅ Video file opened: {self.source_url}")
        self.is_running = True
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
    
    def _extract_stream_url(self):
        """Extract actual stream URL from website pages like insecam.org"""
        if not REQUESTS_AVAILABLE:
            print("❌ Requests library required for website extraction")
            self._create_placeholder()
            return
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.source_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                content = response.text
                
                # Try to find MJPEG or image URLs in the page
                import re
                
                # For insecam.org specifically, look for the main camera image
                if 'insecam' in self.source_url.lower():
                    # PRIORITY 1: Look for img tag with id="image0" - this is the standard main feed for insecam
                    # This is especially common for password-protected feeds that serve JPGs at 1 FPS
                    image0_pattern = r'<img[^>]+id=["\']image0["\'][^>]+src=["\'](http[^"\']+)["\']'
                    image0_match = re.search(image0_pattern, content, re.IGNORECASE)
                    
                    if image0_match:
                        extracted_url = image0_match.group(1)
                        print(f"✅ Found insecam main feed (image0): {extracted_url}")
                        
                        # Test accessibility
                        try:
                            test_response = requests.head(extracted_url, headers=headers, timeout=5, allow_redirects=True)
                            if test_response.status_code in [401, 403]:
                                print(f"⚠️ Main feed requires authentication (status {test_response.status_code})")
                                print("📸 Using webpage screenshot mode (1 FPS) - this is normal for secured feeds")
                                self.source_type = 'webpage_screenshot'
                                self.extracted_img_url = extracted_url
                                return
                            elif test_response.status_code >= 400:
                                print(f"⚠️ Main feed returned error {test_response.status_code}")
                            else:
                                # Direct access works
                                self.source_url = extracted_url
                                self.source_type = 'http_snapshot'  # JPG snapshot
                                return
                        except requests.exceptions.RequestException as e:
                            print(f"⚠️ Could not test URL: {e}")
                            print("📸 Using webpage screenshot mode (1 FPS)")
                            self.source_type = 'webpage_screenshot'
                            self.extracted_img_url = extracted_url
                            return
                    
                    # PRIORITY 2: Look for other main camera patterns if image0 not found
                    main_img_patterns = [
                        r'<img[^>]+id=["\'](?:camera|main|live|player|current)["\'][^>]+src=["\'](http[^"\']+)["\']',
                        r'<img[^>]+class=["\'](?:camera|main|live|player|current)[^"\']*["\'][^>]+src=["\'](http[^"\']+)["\']',
                        r'<img[^>]+src=["\'](http[^"\']+\.jpg)["\'][^>]+(?:id|class)=["\'](?:camera|main|live|player|current)',
                    ]
                    
                    for pattern in main_img_patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        for match in matches:
                            # Strict filtering for insecam - must NOT contain preview/thumbnail indicators
                            if any(bad in match.lower() for bad in ['thumb', 'preview', 'small', 'mini', 'icon', 'logo', 'related', 'recommend', 'similar', 'other']):
                                print(f"⏭️ Skipping preview/thumbnail URL: {match}")
                                continue
                            
                            # Must be a substantial image (check URL structure)
                            if 'image' in match.lower() or 'current' in match.lower() or 'live' in match.lower():
                                extracted_url = match
                                print(f"✅ Extracted main camera URL from insecam: {extracted_url}")
                                
                                # Test accessibility before committing
                                try:
                                    test_response = requests.head(extracted_url, headers=headers, timeout=5, allow_redirects=True)
                                    if test_response.status_code in [401, 403]:
                                        print(f"⚠️ Main camera URL requires authentication (status {test_response.status_code})")
                                        print("📸 Falling back to webpage screenshot mode (1 FPS)")
                                        self.source_type = 'webpage_screenshot'
                                        self.extracted_img_url = extracted_url
                                        return
                                    elif test_response.status_code >= 400:
                                        print(f"⚠️ Main camera URL returned error {test_response.status_code}, trying next match...")
                                        continue
                                except requests.exceptions.RequestException as e:
                                    print(f"⚠️ Could not test URL accessibility: {e}")
                                    print("📸 Using webpage screenshot mode as fallback (1 FPS)")
                                    self.source_type = 'webpage_screenshot'
                                    self.extracted_img_url = extracted_url
                                    return
                                
                                self.source_url = extracted_url
                                self.source_type = autodetect_source_type(extracted_url)
                                
                                if self.source_type == 'http_mjpeg':
                                    self._start_http_stream()
                                elif self.source_type == 'http_snapshot':
                                    pass  # On-demand fetching
                                return
                            extracted_url = matches[0]
                            print(f"✅ Extracted main camera URL from insecam: {extracted_url}")
                            self.source_url = extracted_url
                            self.source_type = autodetect_source_type(extracted_url)
                            
                            if self.source_type == 'http_mjpeg':
                                self._start_http_stream()
                            elif self.source_type == 'http_snapshot':
                                pass  # On-demand fetching
                            return
                
                # Generic patterns - prioritize non-thumbnail, non-preview images
                patterns = [
                    # High priority: streaming endpoints
                    (r'http[s]?://[^\s\'"<>]+/axis-cgi/mjpg/[^\s\'"<>]+', 10),
                    (r'http[s]?://[^\s\'"<>]+/video\.cgi[^\s\'"<>]*', 10),
                    (r'http[s]?://[^\s\'"<>]+\.mjp[e]?g[^\s\'"<>]*', 9),
                    
                    # Medium priority: snapshot endpoints
                    (r'http[s]?://[^\s\'"<>]+/snapshot\.cgi[^\s\'"<>]*', 8),
                    (r'http[s]?://[^\s\'"<>]+/current\.jpg[^\s\'"<>]*', 7),
                    (r'http[s]?://[^\s\'"<>]+/image\.jpg[^\s\'"<>]*', 7),
                    
                    # Low priority: generic jpg (but exclude thumbnails)
                    (r'http[s]?://[^\s\'"<>]+/(?!thumb|preview|small|mini)[^/]*\.jpg[^\s\'"<>]*', 5),
                ]
                
                # Expanded list of preview/secondary feed indicators
                secondary_indicators = [
                    'thumb', 'thumbnail', 'preview', 'small', 'mini', 'icon', 'logo',
                    'related', 'recommend', 'similar', 'other', 'next', 'more',
                    'sidebar', 'widget', 'teaser', 'promo', 'ad', 'banner'
                ]
                
                # Collect all matches with priorities
                all_matches = []
                for pattern, priority in patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Strict filtering - skip if URL contains any secondary feed indicators
                        match_lower = match.lower()
                        if any(indicator in match_lower for indicator in secondary_indicators):
                            print(f"⏭️ Skipping secondary feed URL: {match}")
                            continue
                        
                        # Additional check: if it's a generic jpg, it should be in a main content area
                        # Look for size indicators in URL - main feeds usually have larger dimensions
                        if match_lower.endswith('.jpg') and not any(x in match_lower for x in ['current', 'live', 'main', 'camera', 'image', 'snapshot']):
                            # Check if URL has dimension indicators suggesting it's too small
                            import re as regex
                            size_match = regex.search(r'(\d+)x(\d+)', match_lower)
                            if size_match:
                                width, height = int(size_match.group(1)), int(size_match.group(2))
                                if width < 300 or height < 200:  # Too small to be main feed
                                    print(f"⏭️ Skipping small image ({width}x{height}): {match}")
                                    continue
                        
                        all_matches.append((match, priority))
                
                # Sort by priority (highest first) and test each until we find one that works
                if all_matches:
                    all_matches.sort(key=lambda x: x[1], reverse=True)
                    
                    # Try each URL in priority order until we find one that works
                    for extracted_url, priority in all_matches:
                        extracted_url = extracted_url.split('"')[0].split("'")[0]
                        print(f"🔍 Testing extracted URL: {extracted_url} (priority: {priority})")
                        
                        # Test if the URL is accessible (not blocked by auth)
                        try:
                            test_response = requests.head(extracted_url, headers=headers, timeout=5, allow_redirects=True)
                            
                            if test_response.status_code in [401, 403]:
                                print(f"⚠️ URL requires authentication (status {test_response.status_code})")
                                # Don't give up yet - save this as fallback and try next URL
                                if not hasattr(self, 'fallback_url'):
                                    self.fallback_url = extracted_url
                                continue
                            
                            elif test_response.status_code >= 400:
                                print(f"⚠️ URL returned error {test_response.status_code}, trying next...")
                                continue
                            
                            # Success! This URL is accessible
                            print(f"✅ Found accessible stream URL: {extracted_url}")
                            self.source_url = extracted_url
                            
                            # Re-detect the type for the extracted URL
                            self.source_type = autodetect_source_type(extracted_url)
                            
                            # Start the appropriate handler
                            if self.source_type == 'http_mjpeg':
                                self._start_http_stream()
                            elif self.source_type == 'http_snapshot':
                                pass  # On-demand fetching
                            return
                            
                        except requests.exceptions.RequestException as e:
                            print(f"⚠️ Could not test URL: {e}")
                            # Save as fallback and continue to next URL
                            if not hasattr(self, 'fallback_url'):
                                self.fallback_url = extracted_url
                            continue
                    
                    # If we get here, no URLs were directly accessible
                    # Use the fallback URL (first authenticated one) if we found one
                    if hasattr(self, 'fallback_url'):
                        print("📸 No direct access URLs found, using webpage screenshot mode (1 FPS)")
                        self.source_type = 'webpage_screenshot'
                        self.extracted_img_url = self.fallback_url
                        return
                
                print("⚠️ Could not extract stream URL from page, using page as snapshot source")
                self.source_type = 'http_snapshot'
            else:
                print(f"❌ Failed to fetch page: {response.status_code}")
                self._create_placeholder()
                
        except Exception as e:
            print(f"❌ Stream extraction error: {e}")
            self._create_placeholder()
    
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
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
            }
            response = requests.get(self.source_url, headers=headers, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                img_array = np.frombuffer(response.content, dtype=np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                if frame is not None:
                    return frame
                else:
                    print("⚠️ Failed to decode image from response")
            elif response.status_code in [401, 403]:
                print(f"⚠️ Authentication required (status {response.status_code}), trying fallback...")
                # Try webpage screenshot fallback
                return self._fetch_webpage_screenshot()
        except Exception as e:
            print(f"❌ HTTP snapshot error: {e}")
        return None
    
    def _fetch_webpage_screenshot(self):
        """Fallback: Try to extract the displayed image from the webpage itself"""
        if not REQUESTS_AVAILABLE or not CV2_AVAILABLE:
            return None
        
        try:
            # Try to fetch the image as it appears on the page (embedded with page cookies)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': self.source_url,  # Important: send referrer
            }
            
            # If we have an extracted image URL, try to fetch it with the page as referrer
            if hasattr(self, 'extracted_img_url'):
                print(f"📸 Fetching image with referrer: {self.extracted_img_url}")
                response = requests.get(self.extracted_img_url, headers=headers, timeout=10, allow_redirects=True)
                if response.status_code == 200:
                    img_array = np.frombuffer(response.content, dtype=np.uint8)
                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    if frame is not None:
                        return frame
            
            # If that fails, try to get image from the page context
            # Some sites serve images through the page itself
            session = requests.Session()
            session.headers.update(headers)
            
            # First load the page to get cookies
            page_response = session.get(self.source_url, timeout=10)
            if page_response.status_code == 200:
                # Now try the image URL with the session cookies
                if hasattr(self, 'extracted_img_url'):
                    img_response = session.get(self.extracted_img_url, timeout=10)
                    if img_response.status_code == 200:
                        img_array = np.frombuffer(img_response.content, dtype=np.uint8)
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        if frame is not None:
                            print("✅ Successfully fetched image via session")
                            return frame
            
        except Exception as e:
            print(f"❌ Webpage screenshot error: {e}")
        
        return None
    
    def get_frame(self, format='base64'):
        """Get the current frame"""
        try:
            # For HTTP snapshots, fetch on-demand
            if self.source_type == 'http_snapshot':
                frame = self._fetch_http_snapshot()
                if frame is not None:
                    self.current_frame = frame
                    self.last_update = datetime.now()
            
            # For webpage screenshots (fallback mode for authenticated feeds)
            elif self.source_type == 'webpage_screenshot':
                frame = self._fetch_webpage_screenshot()
                if frame is not None:
                    self.current_frame = frame
                    self.last_update = datetime.now()
            
            # Use current frame or placeholder
            frame = self.current_frame
            
            if frame is None:
                print("⚠️ No frame available, creating placeholder")
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
        except Exception as e:
            print(f"❌ Error in get_frame: {e}")
            import traceback
            traceback.print_exc()
            # Create placeholder on error
            self._create_placeholder()
            if format == 'base64' and self.current_frame:
                try:
                    if CV2_AVAILABLE and isinstance(self.current_frame, np.ndarray):
                        _, buffer = cv2.imencode('.jpg', self.current_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        img_str = base64.b64encode(buffer).decode()
                        return f'data:image/jpeg;base64,{img_str}'
                except:
                    pass
            return None
    
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
        info = {
            'source_type': self.source_type,
            'source_url': self.source_url,
            'status': 'running' if self.is_running else 'stopped',
            'last_update': self.last_update.isoformat() if self.last_update else None
        }
        
        # Add fallback info if using webpage screenshot mode
        if self.source_type == 'webpage_screenshot':
            info['fallback_mode'] = True
            info['note'] = 'Using webpage screenshot (1 FPS) due to authentication'
            if hasattr(self, 'extracted_img_url'):
                info['extracted_url'] = self.extracted_img_url
        
        return info
    
    def stop(self):
        """Cleanup"""
        print(f"🛑 Stopping camera feed: {self.source_type}")
        self.is_running = False
        
        # Clear current frame
        self.current_frame = None
        self.last_update = None
        
        # Stop background thread
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
            self.thread = None
        
        # Release video capture
        if hasattr(self, 'cap'):
            try:
                self.cap.release()
            except:
                pass
            delattr(self, 'cap')
        
        print("✅ Camera stopped and cleaned up")


def create_camera_feed(source_type='placeholder', source_url=None):
    """
    Create a camera feed
    
    source_type options:
        - 'placeholder': Test placeholder
        - 'webcam': Computer webcam
        - 'http_mjpeg': MJPEG stream URL
        - 'http_snapshot': HTTP snapshot URL
        - 'website_embed': Website page with embedded camera (e.g., insecam.org)
        - 'rtsp': RTSP stream
        - 'video_file': Local video file
        - '' or 'auto': Auto-detect from URL
    
    source_url: Provide your own URL/path or website page
    """
    print(f"📹 Creating camera feed. Type: '{source_type}', URL: '{source_url}'")
    
    return SimpleCameraFeed(source_type, source_url)


# Test
if __name__ == '__main__':
    print("🎥 Testing Camera Manager\n")
    
    camera = create_camera_feed('placeholder')
    print(f"Camera info: {camera.get_info()}")
    
    frame = camera.get_frame('base64')
    print(f"Frame type: {type(frame)}")
    print(f"Frame starts with: {frame[:50] if isinstance(frame, str) else 'N/A'}")
    
    print("\n✅ Camera manager working!")
