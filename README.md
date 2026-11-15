# SPOTection: AI Parking Spot Detection

Fall 2025 computer science capstone (Marshall University). SPOTection watches a parking lot camera feed, detects vehicles with YOLOv8, and reports which spaces are open or occupied through a web dashboard.

## Features
- **Detection:** YOLOv8 vehicle detection matched against calibrated parking-space polygons; uncertain detections fail safe to "occupied".
- **Web app (Flask):** live view, admin panel, lot management, and web-based calibration.
- **Security:** session-based login for the admin panel; every state-changing API endpoint requires authentication and is risk-rated in [API_SECURITY.md](API_SECURITY.md).
- **Media archive:** periodic and change-triggered screenshots with a size-capped rolling archive and historical playback ([MEDIA_STORAGE.md](MEDIA_STORAGE.md)).
- **Setup:** modular setup package for configuration, PostgreSQL schema migrations and the virtual environment ([setup/README.md](setup/README.md)).
- **Tests:** pytest suite for detection, models and the API ([TESTING.md](TESTING.md)).

## Quick start
1. Copy `config.json.template` to `config.json` and set your database URI, camera URL, admin credentials and a random `secret_key`. `config.json` is git-ignored, so keep secrets there and never commit it.
2. `python setup.py`
3. `start.bat` (Windows) or `start.ps1`

## Team
Built by Matthew Walker ([@KokiichiiCoding](https://github.com/KokiichiiCoding)) and Jacob Gibson ([@Jacob-Gibson](https://github.com/Jacob-Gibson)).
- **Matthew:** the original polygon-based detection and the alpha web app (live view, admin, analytics, camera manager).
- **Jacob:** automatic space detection, PostgreSQL storage, authentication and the beta integration.
