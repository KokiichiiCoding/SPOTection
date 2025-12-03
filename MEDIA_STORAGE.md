# Media Storage System - Documentation

## Overview

The SPOTection media storage system provides a comprehensive solution for archiving parking lot screenshots and video footage with automatic storage management, historical playback, and integration with parking detection data.

## Features

### Core Capabilities

- **Automatic Screenshot Capture**: Captures parking lot images at configurable intervals
- **Change Detection**: Optionally captures images when parking occupancy changes
- **Rolling Archive**: Maintains up to 20GB (configurable) of historical footage
- **Automatic Cleanup**: Deletes oldest media when storage limit is reached
- **Thumbnail Generation**: Creates thumbnails for fast preview
- **Historical Playback**: View parking lot state at any point in time
- **Parking State Correlation**: Links media with parking spot occupancy data

### Storage Management

- **Size Limit**: Configurable maximum storage (default 20GB)
- **Automatic Cleanup**: Removes oldest media when approaching limit
- **Manual Cleanup**: Admin can trigger cleanup via API
- **Storage Statistics**: Real-time monitoring of storage usage
- **File Organization**: Structured storage by type (images/videos/thumbnails)

## Architecture

### Database Schema

Two new tables added in migration 1.4.0:

#### `media_storage` Table
```sql
CREATE TABLE media_storage (
    id SERIAL PRIMARY KEY,
    lot_id INTEGER REFERENCES parking_lot(id),
    media_type VARCHAR(20) NOT NULL,          -- 'image' or 'video'
    file_path VARCHAR(500) NOT NULL,
    file_size BIGINT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    duration INTEGER,                          -- Video duration (seconds)
    frame_count INTEGER,                       -- Video frame count
    resolution VARCHAR(20),                    -- e.g., "1920x1080"
    metadata JSONB,                           -- Detections, occupancy, etc.
    thumbnail_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX ix_media_storage_lot_timestamp ON media_storage(lot_id, timestamp DESC);
CREATE INDEX ix_media_storage_timestamp ON media_storage(timestamp DESC);
```

#### `media_storage_stats` Table
```sql
CREATE TABLE media_storage_stats (
    id SERIAL PRIMARY KEY,
    total_size BIGINT DEFAULT 0,
    image_count INTEGER DEFAULT 0,
    video_count INTEGER DEFAULT 0,
    oldest_media_timestamp TIMESTAMP,
    newest_media_timestamp TIMESTAMP,
    last_cleanup TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### File Structure

```
media_archive/
├── images/
│   ├── lot1_20250203_143022_123456.jpg
│   ├── lot1_20250203_143522_234567.jpg
│   └── ...
├── videos/
│   ├── lot1_20250203_140000.mp4
│   └── ...
└── thumbnails/
    ├── thumb_lot1_20250203_143022_123456.jpg
    └── ...
```

## Configuration

### config.json

```json
{
  "media_storage": {
    "enabled": true,
    "base_path": "media_archive",
    "max_size_gb": 20.0,
    "capture_interval": 300,
    "capture_on_change": true,
    "video_recording": false,
    "video_segment_duration": 300,
    "cleanup_enabled": true,
    "keep_thumbnails": true
  }
}
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable media storage |
| `base_path` | string | `"media_archive"` | Directory for media files |
| `max_size_gb` | float | `20.0` | Maximum storage in gigabytes |
| `capture_interval` | integer | `300` | Seconds between captures (5 minutes) |
| `capture_on_change` | boolean | `true` | Capture when occupancy changes |
| `video_recording` | boolean | `false` | Enable video recording (future) |
| `video_segment_duration` | integer | `300` | Video segment length in seconds |
| `cleanup_enabled` | boolean | `true` | Enable automatic cleanup |
| `keep_thumbnails` | boolean | `true` | Keep thumbnails after cleanup |

## API Endpoints

### Get Storage Statistics

```http
GET /api/media/storage/stats
Authentication: Required (session)
```

**Response:**
```json
{
  "total_size": 5368709120,
  "total_size_gb": 5.0,
  "image_count": 1234,
  "video_count": 0,
  "oldest_media": "2025-01-15T08:30:00",
  "newest_media": "2025-02-03T14:45:00",
  "last_cleanup": "2025-02-01T03:00:00",
  "max_size_gb": 20.0,
  "percent_full": 25.0
}
```

### Get Media Timeline

```http
GET /api/media/<lot_id>/timeline?date=2025-02-03
Authentication: Required
```

**Response:**
```json
{
  "lot_id": 1,
  "date": "2025-02-03",
  "timeline": [
    {
      "hour": 8,
      "total_count": 12,
      "image_count": 12,
      "video_count": 0,
      "first_capture": "2025-02-03T08:05:00",
      "last_capture": "2025-02-03T08:55:00"
    }
  ]
}
```

### Get Media by Time Range

```http
GET /api/media/<lot_id>/timerange?start_time=2025-02-03T08:00:00&end_time=2025-02-03T09:00:00&limit=50
Authentication: Required
```

**Response:**
```json
{
  "lot_id": 1,
  "start_time": "2025-02-03T08:00:00",
  "end_time": "2025-02-03T09:00:00",
  "media_type": null,
  "count": 12,
  "media": [
    {
      "id": 123,
      "lot_id": 1,
      "media_type": "image",
      "file_path": "media_archive/images/lot1_20250203_080500.jpg",
      "file_size": 245632,
      "timestamp": "2025-02-03T08:05:00",
      "resolution": "1920x1080",
      "metadata": {
        "detections_count": 15,
        "occupied_spots": 18,
        "total_spots": 50,
        "vehicle_types": {"car": 12, "truck": 3},
        "capture_reason": "interval"
      },
      "thumbnail_path": "media_archive/thumbnails/thumb_lot1_20250203_080500.jpg"
    }
  ]
}
```

### Serve Media File

```http
GET /api/media/<media_id>/file
Authentication: Required
```

Returns: JPEG image or MP4 video file

### Serve Thumbnail

```http
GET /api/media/<media_id>/thumbnail
Authentication: Required
```

Returns: JPEG thumbnail (max 320x240)

### Get Parking State at Time

```http
GET /api/media/<lot_id>/parking-state?timestamp=2025-02-03T08:05:00
Authentication: Required
```

**Response:**
```json
{
  "lot_id": 1,
  "timestamp": "2025-02-03T08:05:00",
  "spots": [
    {
      "spot_number": 1,
      "occupied": true,
      "confidence": 0.95,
      "last_update": "2025-02-03T08:04:30"
    }
  ],
  "total_occupied": 18,
  "total_spots": 50
}
```

### Manual Cleanup

```http
POST /api/media/storage/cleanup
Authentication: Required
Content-Type: application/json

{
  "bytes_to_free": 1073741824
}
```

**Response:**
```json
{
  "success": true,
  "files_deleted": 234,
  "bytes_freed": 1073741824,
  "bytes_freed_mb": 1024.0,
  "bytes_freed_gb": 1.0
}
```

## Usage

### Accessing the Media Archive

1. Log in to SPOTection admin panel
2. Navigate to `/media-archive`
3. Select a date to view timeline
4. Click on hour blocks to view media
5. Click on images for full-size view with parking state

### Automatic Capture

Media is automatically captured during the detection loop based on:

- **Time-based**: Every `capture_interval` seconds (default 5 minutes)
- **Change-based**: When parking occupancy changes (if `capture_on_change` is true)

### Manual Capture

Currently automatic only. Future versions may support manual capture via API.

### Storage Cleanup

**Automatic**: When storage exceeds `max_size_gb`, oldest 10% of media is deleted to reach 90% capacity.

**Manual**: Admin can trigger cleanup via:
- Web interface: Click "Cleanup Storage" button
- API: POST to `/api/media/storage/cleanup`

## Media Storage Manager API

### Python Usage

```python
from flaskweb.media_storage import MediaStorageManager

# Initialize
media_storage = MediaStorageManager(
    base_path="media_archive",
    max_size_gb=20.0
)

# Save image
success, result = media_storage.save_image(
    db=db,
    image=frame,  # numpy array
    lot_id=1,
    timestamp=datetime.now(),
    metadata={
        'detections_count': 15,
        'occupied_spots': 18,
        'total_spots': 50
    }
)

# Get storage stats
stats = media_storage.get_storage_stats(db)

# Get media by time range
media_files = media_storage.get_media_by_timerange(
    db=db,
    lot_id=1,
    start_time=datetime(2025, 2, 3, 8, 0),
    end_time=datetime(2025, 2, 3, 9, 0),
    media_type='image',
    limit=50
)

# Get parking state at specific time
parking_state = media_storage.get_parking_state_at_time(
    db=db,
    lot_id=1,
    timestamp=datetime(2025, 2, 3, 8, 5)
)

# Manual cleanup
files_deleted, bytes_freed = media_storage.cleanup_old_media(
    db=db,
    bytes_to_free=1024**3  # 1GB
)
```

## Frontend Interface

### Media Archive Page (`/media-archive`)

Features:
- **Storage Statistics Dashboard**: Real-time storage usage
- **Date Picker**: Select any date to view
- **Timeline View**: 24-hour timeline with hourly blocks
- **Media Grid**: Thumbnails of captured images
- **Full-Size Viewer**: Modal with full image and parking state
- **Cleanup Button**: Trigger manual storage cleanup

### Timeline Navigation

1. Select date with date picker or click "Today"
2. Timeline shows 24 hour blocks
3. Blocks with media are highlighted in green
4. Click hour block to load media for that hour
5. Media appears in grid below timeline

### Viewing Historical Data

1. Click on any image thumbnail
2. Full-size image opens in modal
3. Parking state data loads automatically
4. Shows which spots were occupied/free at that moment
5. Close with X button or Escape key

## Performance Considerations

### Storage Optimization

- **JPEG Compression**: Images saved at 85% quality
- **Thumbnail Size**: Max 320x240 pixels at 70% quality
- **Efficient Indexing**: Database indexes on timestamp and lot_id
- **Batch Cleanup**: Deletes multiple files in single transaction

### Query Performance

- **Time Range Queries**: Optimized with indexes
- **Limit Parameter**: Prevents returning too many results
- **Thumbnail Loading**: Fast preview without loading full images
- **Lazy Loading**: Full images only loaded on click

### Database Performance

- **JSONB Metadata**: Efficient storage and querying
- **Separate Stats Table**: Avoids expensive aggregations
- **Periodic Stat Updates**: Only recalculated on changes

## Troubleshooting

### Storage Not Capturing

1. Check `media_storage.enabled` is `true` in config
2. Verify detection system is running
3. Check logs for errors in media storage initialization
4. Ensure `media_archive` directory exists and is writable

### Storage Full

1. Check storage stats: `/api/media/storage/stats`
2. Trigger manual cleanup: `/api/media/storage/cleanup`
3. Increase `max_size_gb` in config
4. Decrease `capture_interval` to capture less frequently

### Missing Thumbnails

1. Check `keep_thumbnails` is `true` in config
2. Verify thumbnail directory exists
3. Check file permissions
4. Re-run migration to create missing thumbnails

### Slow Timeline Loading

1. Reduce `limit` parameter in API calls
2. Check database indexes exist
3. Consider archiving very old data
4. Optimize PostgreSQL performance

## Future Enhancements

### Planned Features

- **Video Recording**: Continuous or motion-triggered video
- **Time-Lapse Generation**: Create time-lapse videos from images
- **Smart Cleanup**: Keep interesting events longer
- **Export Functionality**: Download media archives
- **Search by Events**: Find specific parking events
- **Mobile App**: Access media archive from mobile
- **Cloud Backup**: Optional cloud storage integration
- **Analytics Integration**: Link media with analytics reports

### Video Recording (Planned)

When `video_recording` is enabled:
- Records video in segments of `video_segment_duration` seconds
- Saves to `media_archive/videos/`
- Creates thumbnails from first frame
- Includes frame count and duration in metadata
- Automatic segmentation prevents huge files

## Security Considerations

- **Authentication Required**: All media endpoints require login
- **Path Validation**: File paths validated to prevent directory traversal
- **File Type Checking**: Only serves JPEG/MP4 files
- **Size Limits**: Prevents storage exhaustion attacks
- **Rate Limiting**: API endpoints have rate limits

## Migration

To add media storage to existing installation:

1. Update code to latest version
2. Run `python setup.py` to apply migration 1.4.0
3. Update `config.json` with `media_storage` section
4. Restart application
5. Media will start capturing automatically

## Backup and Recovery

### Backup Media Archive

```bash
# Backup media files
tar -czf media_backup_$(date +%Y%m%d).tar.gz media_archive/

# Backup database (includes media_storage tables)
pg_dump parking_db > parking_db_backup_$(date +%Y%m%d).sql
```

### Restore Media Archive

```bash
# Restore media files
tar -xzf media_backup_20250203.tar.gz

# Restore database
psql parking_db < parking_db_backup_20250203.sql

# Update storage stats
# Run from Python:
# media_storage.update_storage_stats(db)
```

## Monitoring

### Key Metrics

- **Storage Usage**: Monitor `percent_full` from stats API
- **Capture Rate**: Images per hour
- **Cleanup Frequency**: Track `last_cleanup` timestamp
- **File Counts**: Monitor `image_count` growth
- **Failed Captures**: Check logs for save errors

### Alerts

Consider setting up alerts for:
- Storage > 90% full
- No captures for extended period
- Cleanup failures
- Disk space issues

## Credits

Developed as part of SPOTection v1.4.0 update
- Schema migration: 1.4.0
- Media storage manager: `flaskweb/media_storage.py`
- API endpoints: `flaskweb/app.py`
- Frontend: `templates/media_archive.html`
