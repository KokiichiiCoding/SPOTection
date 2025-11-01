"""
Stream Extractor - Extract video stream URLs from various sources
Supports: YouTube embeds, HLS streams, direct video URLs, iframe embeds
"""

import re
import logging
from urllib.parse import urlparse, parse_qs, urljoin

logger = logging.getLogger(__name__)

try:
    import requests
    from bs4 import BeautifulSoup
    EXTRACTION_AVAILABLE = True
except ImportError:
    EXTRACTION_AVAILABLE = False
    logger.warning("BeautifulSoup not available. Install with: pip install beautifulsoup4")


class StreamExtractor:
    """Extract video stream URLs from webpages"""

    def __init__(self):
        self.user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

    def extract_stream_url(self, url):
        """
        Main extraction method - tries multiple strategies
        Returns: dict with {'type': str, 'url': str, 'info': dict}
        """
        logger.info(f"Attempting to extract stream from: {url}")

        # Try different extraction methods
        strategies = [
            self._extract_youtube_embed,
            self._extract_hls_stream,
            self._extract_iframe_src,
            self._extract_video_tags,
            self._extract_m3u8_links,
        ]

        for strategy in strategies:
            try:
                result = strategy(url)
                if result:
                    logger.info(f"Successfully extracted stream using {strategy.__name__}: {result}")
                    return result
            except Exception as e:
                logger.debug(f"{strategy.__name__} failed: {e}")
                continue

        logger.warning(f"Could not extract stream from {url}")
        return None

    def _fetch_page(self, url):
        """Fetch webpage content with proper headers"""
        if not EXTRACTION_AVAILABLE:
            return None

        headers = {
            'User-Agent': self.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"HTTP {response.status_code} when fetching {url}")
                return None
        except Exception as e:
            logger.error(f"Error fetching page: {e}")
            return None

    def _extract_youtube_embed(self, url):
        """Extract YouTube video ID from embeds or direct links"""
        html = self._fetch_page(url)
        if not html:
            return None

        # Try to find YouTube embeds
        youtube_patterns = [
            r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})',
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            r'youtube\.com/live/([a-zA-Z0-9_-]{11})',
        ]

        for pattern in youtube_patterns:
            match = re.search(pattern, html)
            if match:
                video_id = match.group(1)
                # Return YouTube thumbnail URL (can be updated in real-time)
                thumbnail_url = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                return {
                    'type': 'youtube',
                    'url': thumbnail_url,
                    'video_id': video_id,
                    'live_url': f"https://www.youtube.com/watch?v={video_id}",
                    'info': 'YouTube video detected - using thumbnail (live stream requires youtube-dl)'
                }

        return None

    def _extract_hls_stream(self, url):
        """Extract HLS (.m3u8) stream URLs"""
        html = self._fetch_page(url)
        if not html:
            return None

        # Look for .m3u8 URLs
        m3u8_pattern = r'(https?://[^\s\'"]+\.m3u8[^\s\'"]*)'
        matches = re.findall(m3u8_pattern, html)

        if matches:
            hls_url = matches[0]
            return {
                'type': 'hls',
                'url': hls_url,
                'info': 'HLS stream detected (.m3u8)'
            }

        return None

    def _extract_iframe_src(self, url):
        """Extract iframe src attributes"""
        html = self._fetch_page(url)
        if not html or not EXTRACTION_AVAILABLE:
            return None

        soup = BeautifulSoup(html, 'html.parser')
        iframes = soup.find_all('iframe')

        for iframe in iframes:
            src = iframe.get('src', '')
            if src and ('youtube' in src or 'video' in src or 'stream' in src):
                # Recursively extract from iframe source
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    parsed = urlparse(url)
                    src = f"{parsed.scheme}://{parsed.netloc}{src}"

                logger.info(f"Found iframe source: {src}")
                # Try to extract from the iframe source
                return self.extract_stream_url(src)

        return None

    def _extract_video_tags(self, url):
        """Extract direct video source from HTML5 video tags"""
        html = self._fetch_page(url)
        if not html or not EXTRACTION_AVAILABLE:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        # Look for <video> tags
        videos = soup.find_all('video')
        for video in videos:
            # Check for source tags
            sources = video.find_all('source')
            for source in sources:
                src = source.get('src', '')
                if src:
                    if src.startswith('/'):
                        parsed = urlparse(url)
                        src = f"{parsed.scheme}://{parsed.netloc}{src}"

                    return {
                        'type': 'video',
                        'url': src,
                        'info': 'HTML5 video tag detected'
                    }

            # Check for src attribute on video tag itself
            src = video.get('src', '')
            if src:
                if src.startswith('/'):
                    parsed = urlparse(url)
                    src = f"{parsed.scheme}://{parsed.netloc}{src}"

                return {
                    'type': 'video',
                    'url': src,
                    'info': 'HTML5 video tag detected'
                }

        return None

    def _extract_m3u8_links(self, url):
        """Find any .m3u8 links in the page"""
        html = self._fetch_page(url)
        if not html:
            return None

        # More aggressive m3u8 search
        patterns = [
            r'(https?://[^\s\'"]+\.m3u8[^\s\'"]*)',
            r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']',
            r'src\s*=\s*["\']([^"\']+\.m3u8[^"\']*)["\']',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            if matches:
                m3u8_url = matches[0]
                if isinstance(m3u8_url, tuple):
                    m3u8_url = m3u8_url[0]

                return {
                    'type': 'hls',
                    'url': m3u8_url,
                    'info': 'M3U8 stream found in page'
                }

        return None


def extract_stream_from_webpage(url):
    """
    Convenience function to extract stream URL from a webpage
    Returns the stream URL or None
    """
    extractor = StreamExtractor()
    result = extractor.extract_stream_url(url)

    if result:
        logger.info(f"Stream extraction successful: {result['type']} - {result.get('info', '')}")
        return result['url']
    else:
        logger.warning(f"Could not extract stream from {url}")
        return None


# Test function
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    test_urls = [
        'https://taco-about-python.com',
        'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
    ]

    extractor = StreamExtractor()
    for test_url in test_urls:
        print(f"\nTesting: {test_url}")
        result = extractor.extract_stream_url(test_url)
        if result:
            print(f"  Type: {result['type']}")
            print(f"  URL: {result['url']}")
            print(f"  Info: {result.get('info', 'N/A')}")
        else:
            print("  No stream found")
