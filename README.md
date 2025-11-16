# SPOTection - AI-Powered Parking Spot Detection

A Flask application that streams MJPEG/HTTP/S snapshots, overlays AI-powered parking detections, and serves an admin-friendly calibration tool for shaping parking lots. This branch focuses on a reliable live feed experience (including the https://taco-about-python.com/video_feed source), better white-vehicle detection, and keeping operational data hidden until administrators complete calibration.

## Highlights
- **Live feed hosting** – `/live` renders the MJPEG/HLS feed with automatic orientation fixes. Taco About Python's demo feed now rotates automatically so the video renders upright.
- **Detection tuned for bright vehicles** – every inference frame is enhanced (white balance + CLAHE + gamma correction + denoising) before YOLO runs, drastically improving the hit rate on white cars.
- **Calibrated-only dashboard** – `/` withholds availability metrics until the lot has been calibrated and approved, preventing stale numbers.
- **Protected admin tools** – set `ADMIN_ACCESS_CODE` to require a passcode before anyone can open `/admin` or submit calibration/configuration changes.
- **Requirements at the top of the repo** – install everything from the root `requirements.txt` alongside this README and other docs.

## Quick start
1. **Install dependencies**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure the camera feed (environment variables)**
   ```bash
   export CAMERA_SOURCE=http_mjpeg
   export CAMERA_URL=https://taco-about-python.com/video_feed
   export CAMERA_ORIENTATION=auto        # rotate180 automatically for Taco feed
   export CAMERA_TIMEOUT=10
   export CAMERA_MAX_RETRIES=3
   export ADMIN_ACCESS_CODE=supersecret  # optional but recommended
   ```
   Supported `CAMERA_SOURCE` values: `placeholder`, `webcam`, `http_mjpeg`, `http_snapshot`, `rtsp`, `hls`, or `webpage`.
3. **Run the Flask server**
   ```bash
   python -m flask --app flaskweb.app --debug run
   ```
4. **Calibrate the lot**
   - Visit `/admin`, enter the admin access code if configured, and draw each parking polygon over the live feed.
   - Click **Save All** to persist calibration data (`config.json`). The dashboard and analytics will unlock once at least one space exists.

## Meeting the deployment requirements
- ✅ **Hosted web application with live video** – Flask serves the dashboard, analytics, and admin UI plus a live MJPEG/HLS feed viewer.
- ✅ **Access to live streaming feed** – `/live` consumes MJPEG/HLS, auto-rotates Taco's feed, and exposes camera health.
- ✅ **Displays available vs. total spaces** – the dashboard shows numeric stats only after calibration to avoid misleading values.
- ✅ **Determines availability from live feed** – calibrated polygons plus the YOLO + enhancement pipeline drive the parking status endpoints.
- ✅ **Create/edit/delete parking spaces (lots)** – the admin calibration UI lets authorized users define, update, export, and clear spaces entirely through the browser.
- ✅ **Admin-only configuration** – `ADMIN_ACCESS_CODE` gates `/admin` and any configuration write operations without introducing a full login system.

## Useful environment variables
| Variable | Purpose |
| --- | --- |
| `CAMERA_SOURCE` / `CAMERA_URL` | Select and point to your camera source (webcam, MJPEG, RTSP, etc.). |
| `CAMERA_ORIENTATION` | `auto`, `rotate180`, `flip_horizontal`, or `flip_vertical`. `auto` rotates Taco's demo feed automatically. |
| `CAMERA_TIMEOUT`, `CAMERA_MAX_RETRIES` | Harden HTTP/RTSP connectivity. |
| `ADMIN_ACCESS_CODE` | Passcode required to unlock `/admin` and submit calibration/configuration changes. Leave unset for local demos. |

## Project structure
- `flaskweb/` – Flask blueprints, templates, camera manager, and static assets.
- `src/core/` – YOLO-based detection, live camera utilities, and calibration logic.
- `src/utils/image_enhancer.py` – shared frame enhancement helpers for better vehicle recognition.
- `requirements.txt` – all Python dependencies at the repository root for easy deployment.

Calibrate, unlock the dashboard, and enjoy upright, white-car-friendly detections!
