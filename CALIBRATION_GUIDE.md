# Calibration System - Complete Guide

## Overview
The SPOTection calibration system allows you to define parking spot boundaries on camera images. This guide explains how calibration works and how to troubleshoot issues.

## How Calibration Works

### 1. **Web-Based Calibration** (Recommended)
Access the admin panel at `http://{Your Domain}/admin`

**Steps:**
1. View the camera feed in the calibration canvas
2. Click 4 corners of each parking spot (clockwise from top-left)
3. Each spot is automatically saved with ID `SPACE-001`, `SPACE-002`, etc.
4. Click "💾 Save All" when all spots are defined

**What Happens When You Save:**
- ✅ Saves to `config.json` under `calibration_data`
- ✅ Automatically creates `Spot` records in the database
- ✅ Creates or updates the parking lot (default: `LOT-001`)
- ✅ Removes old spots that were deleted
- ✅ Shows sync status with checkmark indicator

### 2. **Manual Configuration**
You can also manually edit `config.json` to define calibration data:

```json
{
  "calibration_data": [
    {
      "id": "SPACE-001",
      "polygon": [
        {"x": 0.1, "y": 0.2},
        {"x": 0.3, "y": 0.2},
        {"x": 0.3, "y": 0.4},
        {"x": 0.1, "y": 0.4}
      ]
    }
  ]
}
```

**Note:** After manual edits, re-save calibration through the admin page to sync with the database.

## Database Structure

The calibration system uses three database tables:

```
ParkingLot (public_id: LOT-001)
  └─ Spot (spot_id: SPACE-001)
      └─ StatusUpdate (status: free/occupied, confidence, timestamp)
```

## Calibration Status Indicator

The admin page now shows a status box:

- **✅ Green:** Calibration synced - database matches config
- **⚠️ Yellow:** Out of sync - re-save calibration to fix
- **❌ Red:** Lot doesn't exist - create it in Lot Management section

Click "🔄 Check Sync Status" to refresh the indicator.

## Troubleshooting

### Problem: "No spots found in database"

**Symptoms:**
- Detection system logs: `⚠ Lot 'LOT-001' not found in database`
- Frontend shows 0 spots
- No status updates appearing

**Solutions:**

#### Option 1: Re-save Calibration (Easiest)
1. Go to `/admin`
2. Your spots should still be visible on the canvas
3. Click "💾 Save All" again
4. Check the status indicator turns green

#### Option 2: Use the Admin Interface
If calibration exists in `config.json` but not in database:

1. Go to `http://localhost:5000/admin`
2. Click "💾 Save All" to sync the existing calibration data
3. Check the status indicator turns green

This will:
- Read calibration from `config.json`
- Create/update the lot in database
- Add all spots to database
- Show sync status

#### Option 3: Verify via API
Check the calibration status API:

```
GET http://localhost:5000/api/calibration/status
```

This will show:
- Database connectivity
- Existing lots and spots
- Sync status

### Problem: Calibration data exists but spots are wrong

**Solution:**
1. Go to `/admin`
2. Click "Clear All Spaces" to reset
3. Re-draw the correct spot boundaries
4. Click "💾 Save All"

The system will automatically:
- Remove old spots from database
- Add new spots
- Update lot's total_spots count

### Problem: Multiple lots, calibration goes to wrong lot

**Solution:**
1. Check `config.json` for `default_lot_id`
2. Change it to your desired lot:
   ```json
   {
     "default_lot_id": "LOT-002",
     ...
   }
   ```
3. Re-save calibration from admin page to sync with database

## Verification Steps

After calibration, verify everything works:

### 1. Check Config File
```bash
# View calibration data
python -c "import json; print(json.load(open('config.json'))['calibration_data'])"
```

Should show array of spots with polygon coordinates.

### 2. Check Database via API
```bash
curl http://localhost:5000/api/lot/LOT-001/status
```

Should show:
- Your lot exists
- Correct number of spots
- Current status of all spots

### 3. Check API Endpoint
Visit: `http://localhost:5000/api/calibration/status`

Should return:
```json
{
  "synced": true,
  "lot_id": "LOT-001",
  "config_spots": 10,
  "db_spots": 10,
  "message": "Calibration synced"
}
```

### 4. Check Lot Status
Visit: `http://localhost:5000/api/lot/LOT-001/status`

Should show all your spots with status data.

## API Endpoints

### Get Calibration Status
```
GET /api/calibration/status
```
Returns sync status between config.json and database.

### Save Calibration
```
POST /api/config
Body: {
  "calibration_data": [...],
  "total_spaces": 10
}
```
Saves to config.json AND syncs to database automatically.

### Get Lot Status
```
GET /api/lot/{lot_id}/status
```
Returns current status of all spots in the lot.

## Key Files

- `flaskweb/app.py` - Main Flask application with calibration sync logic
- `flaskweb/templates/admin.html` - Web-based calibration interface
- `config.json` - Stores calibration data and configuration
- `flaskweb/models.py` - Database models for lots, spots, and status updates

## Common Issues

### Issue: "Lot not found" error
**Fix:** Create the lot via admin page "Parking Lot Management" section, or it will be auto-created on first calibration save.

### Issue: Calibration saves but detection doesn't work
**Check:**
1. Is the Flask application running? `python -m flask --app flaskweb.app run`
2. Does config.json have `default_lot_id` set correctly?
3. Check API endpoint: `http://localhost:5000/api/calibration/status` to verify spots exist

### Issue: Old spots still appearing after re-calibration
**Fix:** The system automatically removes old spots when you save new calibration. If they persist:
1. Check you're viewing the correct lot in the frontend
2. Clear browser cache
3. Verify with: `http://localhost:5000/api/calibration/status`

## Best Practices

1. **Always use the web-based calibration** - it handles database sync automatically
2. **Check the status indicator** after saving - ensure it's green
3. **Use consistent lot IDs** - set `default_lot_id` in config.json
4. **Test with the API** (`/api/calibration/status`) after major changes
5. **Keep backups** of config.json with your calibration data

## Support Commands

```bash
# View calibration data
python -c "import json; print(len(json.load(open('config.json')).get('calibration_data', []))), 'spots in config'"

# Check sync status via API
curl http://localhost:5000/api/calibration/status

# View lot status
curl http://localhost:5000/api/lot/LOT-001/status

# Start the application
python -m flask --app flaskweb.app run --debug
```

## Summary

The calibration system now:
- ✅ Automatically syncs to database on save
- ✅ Shows real-time sync status
- ✅ Handles lot creation automatically
- ✅ Removes deleted spots
- ✅ Provides verification tools
- ✅ Gives detailed feedback on save

No more "no spots found" errors after calibration!
