"""
Media Storage Manager
Handles storage, retrieval, and cleanup of parking lot screenshots/video footage
Maintains a 20GB rolling archive with automatic cleanup
"""

import os
import time
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Tuple
import cv2
import numpy as np
from sqlalchemy import desc, asc


class MediaStorageManager:
    """Manages media storage with automatic cleanup and size management"""
    
    def __init__(self, base_path: str = "media_archive", max_size_gb: float = 20.0):
        """
        Initialize media storage manager
        
        Args:
            base_path: Base directory for media storage
            max_size_gb: Maximum storage size in GB (default 20GB)
        """
        self.base_path = Path(base_path)
        self.max_size_bytes = int(max_size_gb * 1024 * 1024 * 1024)
        
        # Create directory structure
        self.images_path = self.base_path / "images"
        self.videos_path = self.base_path / "videos"
        self.thumbnails_path = self.base_path / "thumbnails"
        
        for path in [self.images_path, self.videos_path, self.thumbnails_path]:
            path.mkdir(parents=True, exist_ok=True)
    
    def get_storage_stats(self, db) -> Dict:
        """Get current storage statistics from database"""
        stats = db.session.execute(
            db.text("SELECT * FROM media_storage_stats LIMIT 1")
        ).fetchone()
        
        if stats:
            return {
                'total_size': stats.total_size,
                'total_size_gb': stats.total_size / (1024**3),
                'image_count': stats.image_count,
                'video_count': stats.video_count,
                'oldest_media': stats.oldest_media_timestamp,
                'newest_media': stats.newest_media_timestamp,
                'last_cleanup': stats.last_cleanup,
                'max_size_gb': self.max_size_bytes / (1024**3),
                'percent_full': (stats.total_size / self.max_size_bytes) * 100
            }
        
        return {
            'total_size': 0,
            'total_size_gb': 0,
            'image_count': 0,
            'video_count': 0,
            'oldest_media': None,
            'newest_media': None,
            'last_cleanup': None,
            'max_size_gb': self.max_size_bytes / (1024**3),
            'percent_full': 0
        }
    
    def update_storage_stats(self, db):
        """Recalculate and update storage statistics"""
        # Get actual counts and sizes from database
        result = db.session.execute(db.text("""
            SELECT 
                COALESCE(SUM(file_size), 0) as total_size,
                COALESCE(SUM(CASE WHEN media_type = 'image' THEN 1 ELSE 0 END), 0) as image_count,
                COALESCE(SUM(CASE WHEN media_type = 'video' THEN 1 ELSE 0 END), 0) as video_count,
                MIN(timestamp) as oldest_timestamp,
                MAX(timestamp) as newest_timestamp
            FROM media_storage
        """)).fetchone()
        
        db.session.execute(db.text("""
            UPDATE media_storage_stats 
            SET total_size = :total_size,
                image_count = :image_count,
                video_count = :video_count,
                oldest_media_timestamp = :oldest_timestamp,
                newest_media_timestamp = :newest_timestamp,
                updated_at = NOW()
        """), {
            'total_size': result.total_size,
            'image_count': result.image_count,
            'video_count': result.video_count,
            'oldest_timestamp': result.oldest_timestamp,
            'newest_timestamp': result.newest_timestamp
        })
        db.session.commit()
    
    def save_image(self, db, image: np.ndarray, lot_id: int, 
                   timestamp: datetime = None, metadata: Dict = None) -> Tuple[bool, Optional[str]]:
        """
        Save parking lot image to storage
        
        Args:
            db: Database session
            image: Image as numpy array
            lot_id: Parking lot ID
            timestamp: Timestamp for the image
            metadata: Additional metadata (parking status, detections, etc.)
        
        Returns:
            (success, file_path or error_message)
        """
        try:
            if timestamp is None:
                timestamp = datetime.now()
            
            # Create date-based folder structure
            date_folder = self.images_path / timestamp.strftime('%Y-%m-%d')
            date_folder.mkdir(exist_ok=True)
            
            # Create filename with time only (date is in folder name)
            filename = f"lot{lot_id}_{timestamp.strftime('%H%M%S_%f')}.jpg"
            file_path = date_folder / filename
            
            # Save image
            cv2.imwrite(str(file_path), image, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            # Get file size
            file_size = file_path.stat().st_size
            
            # Create thumbnail with date folder
            thumbnail_path = self._create_thumbnail(image, filename, timestamp)
            
            # Get image resolution
            height, width = image.shape[:2]
            resolution = f"{width}x{height}"
            
            # Save relative path to database (relative to media_archive root)
            relative_path = str(file_path.relative_to(self.base_path))
            relative_thumbnail = str(thumbnail_path.relative_to(self.base_path)) if thumbnail_path else None
            
            # Save to database
            db.session.execute(db.text("""
                INSERT INTO media_storage 
                (lot_id, media_type, file_path, file_size, timestamp, resolution, metadata, thumbnail_path)
                VALUES (:lot_id, 'image', :file_path, :file_size, :timestamp, :resolution, :metadata, :thumbnail_path)
            """), {
                'lot_id': lot_id,
                'file_path': relative_path,
                'file_size': file_size,
                'timestamp': timestamp,
                'resolution': resolution,
                'metadata': json.dumps(metadata) if metadata else None,
                'thumbnail_path': relative_thumbnail
            })
            db.session.commit()
            
            # Update stats
            self.update_storage_stats(db)
            
            # Check if cleanup needed
            self._auto_cleanup(db)
            
            return True, str(file_path)
            
        except Exception as e:
            return False, f"Error saving image: {e}"
    
    def save_video(self, db, video_path: str, lot_id: int,
                   timestamp: datetime = None, metadata: Dict = None) -> Tuple[bool, Optional[str]]:
        """
        Save video file to storage
        
        Args:
            db: Database session
            video_path: Path to temporary video file
            lot_id: Parking lot ID
            timestamp: Timestamp for the video
            metadata: Additional metadata
        
        Returns:
            (success, file_path or error_message)
        """
        try:
            if timestamp is None:
                timestamp = datetime.now()
            
            # Create date-based folder structure
            date_folder = self.videos_path / timestamp.strftime('%Y-%m-%d')
            date_folder.mkdir(exist_ok=True)
            
            # Create filename with time only (date is in folder name)
            filename = f"lot{lot_id}_{timestamp.strftime('%H%M%S')}.mp4"
            dest_path = date_folder / filename
            
            # Move video to storage
            Path(video_path).rename(dest_path)
            
            # Get video info
            cap = cv2.VideoCapture(str(dest_path))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = frame_count / fps if fps > 0 else 0
            
            # Create thumbnail from first frame
            ret, frame = cap.read()
            cap.release()
            
            thumbnail_path = None
            if ret:
                thumbnail_path = self._create_thumbnail(frame, filename.replace('.mp4', '.jpg'), timestamp)
            
            # Get file size
            file_size = dest_path.stat().st_size
            resolution = f"{width}x{height}"
            
            # Save relative path to database (relative to media_archive root)
            relative_path = str(dest_path.relative_to(self.base_path))
            relative_thumbnail = str(thumbnail_path.relative_to(self.base_path)) if thumbnail_path else None
            
            # Save to database
            db.session.execute(db.text("""
                INSERT INTO media_storage 
                (lot_id, media_type, file_path, file_size, timestamp, duration, frame_count, 
                 resolution, metadata, thumbnail_path)
                VALUES (:lot_id, 'video', :file_path, :file_size, :timestamp, :duration, 
                        :frame_count, :resolution, :metadata, :thumbnail_path)
            """), {
                'lot_id': lot_id,
                'file_path': relative_path,
                'file_size': file_size,
                'timestamp': timestamp,
                'duration': duration,
                'frame_count': frame_count,
                'resolution': resolution,
                'metadata': json.dumps(metadata) if metadata else None,
                'thumbnail_path': relative_thumbnail
            })
            db.session.commit()
            
            # Update stats
            self.update_storage_stats(db)
            
            # Check if cleanup needed
            self._auto_cleanup(db)
            
            return True, str(dest_path)
            
        except Exception as e:
            return False, f"Error saving video: {e}"
    
    def _create_thumbnail(self, image: np.ndarray, filename: str, 
                         timestamp: datetime = None,
                         max_size: Tuple[int, int] = (320, 240)) -> Optional[Path]:
        """Create thumbnail from image"""
        try:
            # Resize image
            h, w = image.shape[:2]
            scale = min(max_size[0] / w, max_size[1] / h)
            new_w, new_h = int(w * scale), int(h * scale)
            
            thumbnail = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
            
            # Create date-based folder for thumbnails if timestamp provided
            if timestamp:
                date_folder = self.thumbnails_path / timestamp.strftime('%Y-%m-%d')
                date_folder.mkdir(exist_ok=True)
                thumb_path = date_folder / f"thumb_{filename}"
            else:
                thumb_path = self.thumbnails_path / f"thumb_{filename}"
            
            cv2.imwrite(str(thumb_path), thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 70])
            
            return thumb_path
            
        except Exception as e:
            print(f"Error creating thumbnail: {e}")
            return None
    
    def get_media_by_timerange(self, db, lot_id: int, start_time: datetime, 
                               end_time: datetime, media_type: str = None,
                               limit: int = 100) -> List[Dict]:
        """
        Get media files within a time range
        
        Args:
            db: Database session
            lot_id: Parking lot ID
            start_time: Start of time range
            end_time: End of time range
            media_type: Filter by 'image' or 'video' (None for all)
            limit: Maximum number of results
        
        Returns:
            List of media records
        """
        query = """
            SELECT id, lot_id, media_type, file_path, file_size, timestamp, 
                   duration, resolution, metadata, thumbnail_path
            FROM media_storage
            WHERE lot_id = :lot_id 
              AND timestamp >= :start_time 
              AND timestamp <= :end_time
        """
        
        params = {
            'lot_id': lot_id,
            'start_time': start_time,
            'end_time': end_time,
            'limit': limit
        }
        
        if media_type:
            query += " AND media_type = :media_type"
            params['media_type'] = media_type
        
        query += " ORDER BY timestamp DESC LIMIT :limit"
        
        results = db.session.execute(db.text(query), params).fetchall()
        
        return [
            {
                'id': r.id,
                'lot_id': r.lot_id,
                'media_type': r.media_type,
                'file_path': r.file_path,
                'file_size': r.file_size,
                'timestamp': r.timestamp.isoformat() if r.timestamp else None,
                'duration': r.duration,
                'resolution': r.resolution,
                'metadata': json.loads(r.metadata) if (r.metadata and isinstance(r.metadata, str)) else r.metadata,
                'thumbnail_path': r.thumbnail_path
            }
            for r in results
        ]
    
    def get_media_timeline(self, db, lot_id: int, date: datetime = None) -> List[Dict]:
        """
        Get media timeline for a specific date (hourly breakdown)
        
        Args:
            db: Database session
            lot_id: Parking lot ID
            date: Date to get timeline for (default: today)
        
        Returns:
            List of hourly summaries with media counts
        """
        if date is None:
            date = datetime.now()
        
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        results = db.session.execute(db.text("""
            SELECT 
                EXTRACT(HOUR FROM timestamp) as hour,
                COUNT(*) as total_count,
                SUM(CASE WHEN media_type = 'image' THEN 1 ELSE 0 END) as image_count,
                SUM(CASE WHEN media_type = 'video' THEN 1 ELSE 0 END) as video_count,
                MIN(timestamp) as first_capture,
                MAX(timestamp) as last_capture
            FROM media_storage
            WHERE lot_id = :lot_id
              AND timestamp >= :start_time
              AND timestamp < :end_time
            GROUP BY EXTRACT(HOUR FROM timestamp)
            ORDER BY hour
        """), {
            'lot_id': lot_id,
            'start_time': start_of_day,
            'end_time': end_of_day
        }).fetchall()
        
        return [
            {
                'hour': int(r.hour),
                'total_count': r.total_count,
                'image_count': r.image_count,
                'video_count': r.video_count,
                'first_capture': r.first_capture.isoformat() if r.first_capture else None,
                'last_capture': r.last_capture.isoformat() if r.last_capture else None
            }
            for r in results
        ]
    
    def _auto_cleanup(self, db):
        """Automatically cleanup old media if storage limit exceeded"""
        stats = self.get_storage_stats(db)
        
        if stats['total_size'] > self.max_size_bytes:
            # Need to free up space - delete oldest 10% of media
            target_size = self.max_size_bytes * 0.9  # Free up to 90% capacity
            bytes_to_free = stats['total_size'] - target_size
            
            print(f"Storage limit exceeded ({stats['total_size_gb']:.2f}GB / {self.max_size_bytes/(1024**3):.0f}GB)")
            print(f"Cleaning up {bytes_to_free/(1024**3):.2f}GB of old media...")
            
            self.cleanup_old_media(db, bytes_to_free)
    
    def cleanup_old_media(self, db, bytes_to_free: int = None) -> Tuple[int, int]:
        """
        Remove oldest media files to free up space
        
        Args:
            db: Database session
            bytes_to_free: Target bytes to free (None = delete all old media)
        
        Returns:
            (files_deleted, bytes_freed)
        """
        files_deleted = 0
        bytes_freed = 0
        
        # Get oldest media files
        query = """
            SELECT id, file_path, file_size, thumbnail_path
            FROM media_storage
            ORDER BY timestamp ASC
        """
        
        if bytes_to_free:
            # Get enough files to free target space (plus 10% buffer)
            query += f" LIMIT (SELECT COUNT(*) FROM media_storage WHERE file_size > 0)"
        
        results = db.session.execute(db.text(query)).fetchall()
        
        for record in results:
            if bytes_to_free and bytes_freed >= bytes_to_free:
                break
            
            try:
                # Delete file (handle both absolute and relative paths)
                file_path = Path(record.file_path)
                if not file_path.is_absolute():
                    file_path = self.base_path / file_path
                    
                if file_path.exists():
                    file_path.unlink()
                    
                    # Check if parent directory is empty and remove if it's a date folder
                    parent_dir = file_path.parent
                    if parent_dir != self.images_path and parent_dir != self.videos_path:
                        try:
                            if not any(parent_dir.iterdir()):  # Check if empty
                                parent_dir.rmdir()
                        except:
                            pass  # Ignore errors removing directories
                
                # Delete thumbnail
                if record.thumbnail_path:
                    thumb_path = Path(record.thumbnail_path)
                    if not thumb_path.is_absolute():
                        thumb_path = self.base_path / thumb_path
                        
                    if thumb_path.exists():
                        thumb_path.unlink()
                        
                        # Check if parent thumbnail directory is empty
                        parent_dir = thumb_path.parent
                        if parent_dir != self.thumbnails_path:
                            try:
                                if not any(parent_dir.iterdir()):
                                    parent_dir.rmdir()
                            except:
                                pass
                
                # Delete from database
                db.session.execute(
                    db.text("DELETE FROM media_storage WHERE id = :id"),
                    {'id': record.id}
                )
                
                files_deleted += 1
                bytes_freed += record.file_size
                
            except Exception as e:
                print(f"Error deleting media {record.id}: {e}")
        
        db.session.commit()
        
        # Update stats and set last_cleanup time
        db.session.execute(db.text("""
            UPDATE media_storage_stats 
            SET last_cleanup = NOW()
        """))
        db.session.commit()
        
        self.update_storage_stats(db)
        
        print(f"Cleanup complete: {files_deleted} files deleted, {bytes_freed/(1024**2):.2f}MB freed")
        
        return files_deleted, bytes_freed
    
    def get_parking_state_at_time(self, db, lot_id: int, timestamp: datetime) -> Optional[Dict]:
        """
        Get parking lot state (spot occupancy) at a specific time
        
        Args:
            db: Database session
            lot_id: Parking lot ID
            timestamp: Time to query
        
        Returns:
            Dictionary with spot statuses
        """
        # Get all spots for this lot
        spots = db.session.execute(db.text("""
            SELECT id, spot_number
            FROM spot
            WHERE lot_id = :lot_id
            ORDER BY spot_number
        """), {'lot_id': lot_id}).fetchall()
        
        # Get status for each spot at the given timestamp
        # (most recent status before or at the timestamp)
        spot_statuses = []
        
        for spot in spots:
            status = db.session.execute(db.text("""
                SELECT occupied, confidence, timestamp
                FROM status_update
                WHERE spot_id = :spot_id
                  AND timestamp <= :timestamp
                ORDER BY timestamp DESC
                LIMIT 1
            """), {
                'spot_id': spot.id,
                'timestamp': timestamp
            }).fetchone()
            
            spot_statuses.append({
                'spot_number': spot.spot_number,
                'occupied': status.occupied if status else None,
                'confidence': status.confidence if status else None,
                'last_update': status.timestamp.isoformat() if status and status.timestamp else None
            })
        
        return {
            'lot_id': lot_id,
            'timestamp': timestamp.isoformat(),
            'spots': spot_statuses,
            'total_occupied': sum(1 for s in spot_statuses if s['occupied']),
            'total_spots': len(spot_statuses)
        }
