# Custom Extraction Pattern Feature

## Overview
This feature allows users to specify custom HTML tag patterns to extract camera feeds from websites. This is particularly useful for custom websites that don't follow standard camera streaming patterns.

## New Fields

### Database (ParkingLot model)
- `extraction_pattern_type` (VARCHAR 50): The type of extraction pattern to use
- `extraction_pattern_value` (VARCHAR 200): The ID or class name when applicable

### Supported Pattern Types

1. **Auto-detect** (`auto`) - Default behavior
   - Smart detection of image sources
   - Ranks images by size and relevance
   - Works for most standard websites

2. **First img tag** (`first_img`)
   - Uses the first `<img>` tag found on the page
   - No additional value needed

3. **img by id** (`img_by_id`)
   - Targets `<img>` tag with specific id attribute
   - Requires: `extraction_pattern_value` = the id (e.g., "camera-feed")
   - Example: `<img id="camera-feed" src="...">`

4. **img by class** (`img_by_class`)
   - Targets `<img>` tag with specific class attribute
   - Requires: `extraction_pattern_value` = the class name (e.g., "main-image")
   - Example: `<img class="main-image" src="...">`

5. **video by id** (`video_by_id`)
   - Targets `<video>` tag with specific id attribute
   - Extracts source URL from `<source>` tag inside
   - Requires: `extraction_pattern_value` = the id (e.g., "live-feed")
   - Example: `<video id="live-feed"><source src="..."></video>`

## Usage

### Admin Panel
1. Navigate to the Admin panel
2. Select your parking lot
3. In "Camera Configuration" section:
   - Enter the website URL
   - Select "Website Embed" as camera type (or leave as auto-detect)
   - In "Custom Extraction Pattern" section:
     - Choose pattern type from dropdown
     - If using id/class pattern, enter the id or class name
4. Click "Set Camera" to save

### API
Update camera configuration via PUT request to `/api/lot/{lot_id}/camera`:

```json
{
  "camera_url": "https://taco-about-python.com/",
  "camera_type": "website_embed",
  "extraction_pattern_type": "img_by_id",
  "extraction_pattern_value": "camera-feed"
}
```

## Examples

### Example 1: Using first image
```json
{
  "extraction_pattern_type": "first_img"
}
```

### Example 2: Targeting specific ID
```json
{
  "extraction_pattern_type": "img_by_id",
  "extraction_pattern_value": "main-camera"
}
```
Matches: `<img id="main-camera" src="https://...">`

### Example 3: Targeting by class
```json
{
  "extraction_pattern_type": "img_by_class",
  "extraction_pattern_value": "live-feed"
}
```
Matches: `<img class="live-feed camera-view" src="https://...">`

### Example 4: Video element
```json
{
  "extraction_pattern_type": "video_by_id",
  "extraction_pattern_value": "video-player"
}
```
Matches: `<video id="video-player"><source src="https://..."></video>`

## Migration

Run the migration script to add the new columns to existing databases:

```bash
python migrate_add_extraction_patterns.py
```

This will add:
- `extraction_pattern_type` column to `parking_lot` table
- `extraction_pattern_value` column to `parking_lot` table

## Technical Details

### Files Modified
1. `flaskweb/models.py` - Added extraction pattern fields to ParkingLot model
2. `flaskweb/camera_manager.py`:
   - Updated `SimpleCameraFeed.__init__()` to accept pattern parameters
   - Added `_extract_with_custom_pattern()` method
   - Added `_process_extracted_url()` helper method
   - Updated `create_camera_feed()` function signature
3. `flaskweb/app.py`:
   - Updated `load_camera_config()` to load pattern settings
   - Updated `detection_loop()` to pass patterns to cameras
   - Updated `camera_feed()` endpoint
   - Updated `set_camera_config()` endpoint
   - Updated `lot_camera_config()` endpoint
4. `flaskweb/templates/admin.html`:
   - Added extraction pattern UI fields
   - Added `toggleExtractionValue()` JavaScript function
   - Updated form submission to include pattern fields

### How It Works
1. User configures pattern type and value in admin panel
2. Settings saved to database and config.json
3. When creating camera feed, pattern parameters are passed to `SimpleCameraFeed`
4. If pattern type is not 'auto', `_extract_with_custom_pattern()` is called first
5. Method uses regex to find matching HTML tags based on pattern
6. Extracted URL is validated and tested for accessibility
7. Falls back to auto-detection if custom pattern fails

### Fallback Behavior
- If custom pattern fails to find a match, system automatically falls back to auto-detection
- If extracted URL requires authentication, switches to webpage_screenshot mode (1 FPS)
- Relative URLs are automatically converted to absolute URLs
- Data URLs and pixel trackers are automatically filtered out

## Benefits
- ✅ Works with any website structure
- ✅ No need to modify code for new websites
- ✅ Configurable per parking lot
- ✅ Graceful fallback to auto-detection
- ✅ Supports both images and videos
- ✅ User-friendly admin interface
