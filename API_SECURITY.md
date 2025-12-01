# API Security Documentation

## Overview

SPOTection's REST API includes authentication protection on all endpoints that could be used maliciously to modify system configuration or data.

## Authentication Methods

### Session-Based (Web Interface)
- Used by the web admin panel
- Login via `/login` with username/password
- Session cookie maintained automatically by browser
- Logout via `/logout`

---

## Protected Endpoints (Require Authentication)

### ⚠️ Configuration Management

| Endpoint | Method | Description | Risk Level |
|----------|--------|-------------|------------|
| `/admin` | GET | Admin panel page | High |
| `/api/config` | POST | Update system configuration | **Critical** |
| `/api/camera/config` | POST | Change camera configuration | **Critical** |
| `/api/camera/refresh` | POST | Force camera reload | High |

### ⚠️ Detection Control

| Endpoint | Method | Description | Risk Level |
|----------|--------|-------------|------------|
| `/api/detection/load_model` | POST | Load ML detection model | High |
| `/api/detection/control` | POST | Start/stop detection | High |

### ⚠️ Lot Management

| Endpoint | Method | Description | Risk Level |
|----------|--------|-------------|------------|
| `/api/lots` | POST | Create new parking lot | High |
| `/api/lots/<lot_id>` | PUT | Update lot details | High |
| `/api/lots/<lot_id>` | DELETE | Delete parking lot | **Critical** |
| `/api/lot/<lot_id>/camera` | PUT | Update lot camera config | High |
| `/api/lot/<lot_id>/status/cleanup` | POST | Delete old status data | Medium |

### ⚠️ Calibration

| Endpoint | Method | Description | Risk Level |
|----------|--------|-------------|------------|
| `/api/lot/<lot_id>/calibration` | POST | Save parking space layout | **Critical** |
| `/api/parking/space/<space_id>` | PUT | Update individual space | Medium |

---

## Public Endpoints (No Authentication Required)

### ✅ Read-Only Status & Data

| Endpoint | Method | Description | Public Access Reason |
|----------|--------|-------------|---------------------|
| `/` | GET | Dashboard with live detection | User-facing feature |
| `/api/parking/status` | GET | Current parking status | Public information |
| `/api/parking/spaces` | GET | List all spaces | Public information |
| `/api/parking/space/<id>` | GET | Get space details | Public information |
| `/api/lot/<lot_id>/status` | GET | Lot status | Public information |
| `/api/lot/<lot_id>/status/history` | GET | Status history | Public information |
| `/api/lots` | GET | List all lots | Public information |
| `/api/lot/<lot_id>/camera` | GET | Get camera config | Public information |
| `/api/lot/<lot_id>/calibration` | GET | Get calibration data | Public information |
| `/api/lot/<lot_id>/calibration/status` | GET | Calibration status | Public information |
| `/api/detection/status` | GET | Detection system status | Public information |
| `/api/detection/overlay` | GET | Detection visualization data | Public information |
| `/api/lot/<lot_id>/detection/overlay` | GET | Lot-specific detection overlay | Public information |
| `/api/camera/feed` | GET | Camera feed stream | Public information |
| `/api/analytics/summary` | GET | Analytics summary | Public information |
| `/api/analytics/export` | GET | Export analytics | Public information |
| `/api/calibration/status` | GET | System calibration status | Public information |
| `/api/debug/calibration` | GET | Debug calibration data | Development aid |

---

## Security Considerations by Endpoint Type

### Critical Risk Endpoints
**Why protected:** Can permanently alter system configuration or delete data

- `/api/config` POST - Modifies system-wide settings
- `/api/camera/config` POST - Changes camera source (potential for external resource abuse)
- `/api/lot/<lot_id>/calibration` POST - Overwrites parking space definitions
- `/api/lots/<lot_id>` DELETE - Irreversibly deletes data

**Attack Scenarios Prevented:**
- Malicious reconfiguration rendering system inoperable
- Pointing camera at malicious streams (bandwidth/resource abuse)
- Deleting calibration data causing service disruption
- Destroying parking lot records

### High Risk Endpoints
**Why protected:** Can disrupt service or cause resource consumption

- `/api/detection/load_model` POST - Loads ML models (CPU/memory intensive)
- `/api/detection/control` POST - Starts/stops detection (resource control)
- `/api/lots` POST - Creates lots (potential for spam/abuse)
- `/api/camera/refresh` POST - Forces camera reload (resource intensive)

**Attack Scenarios Prevented:**
- DoS via repeated model loading
- Service disruption by stopping detection
- Database spam with fake lots
- Resource exhaustion via camera cycling

### Medium Risk Endpoints
**Why protected:** Can modify data but limited blast radius

- `/api/parking/space/<id>` PUT - Modifies single space
- `/api/lot/<lot_id>/status/cleanup` POST - Deletes old records (but keeps recent)
- `/api/lots/<lot_id>` PUT - Updates lot metadata

**Attack Scenarios Prevented:**
- Data corruption of parking spaces
- Unwanted data deletion
- Metadata tampering

---

## API Security Best Practices

### For Development

1. **Never commit credentials**
   ```bash
   # Add to .gitignore
   config.json
   *.env
   ```

2. **Use environment variables for production**
   ```python
   ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
   ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')
   ```

3. **Test with authentication disabled temporarily**
   ```python
   # For testing only - NEVER in production
   SKIP_AUTH = os.environ.get('SKIP_AUTH') == 'true'
   
   if not SKIP_AUTH and not session.get('logged_in'):
       return jsonify({'error': 'Authentication required'}), 401
   ```

### For Production Deployment

1. **Enable HTTPS**
   - Session cookies should be secure
   - Credentials transmitted encrypted

2. **Implement rate limiting**
   ```python
   from flask_limiter import Limiter
   
   limiter = Limiter(app, key_func=lambda: request.remote_addr)
   
   @app.route('/login', methods=['POST'])
   @limiter.limit("5 per minute")
   def login():
       ...
   ```

3. **Add API key authentication for programmatic access**
   ```python
   def api_key_required(f):
       @wraps(f)
       def decorated(*args, **kwargs):
           api_key = request.headers.get('X-API-Key')
           if api_key != VALID_API_KEY:
               return jsonify({'error': 'Invalid API key'}), 401
           return f(*args, **kwargs)
       return decorated
   ```

4. **Implement password hashing**
   ```python
   from werkzeug.security import check_password_hash, generate_password_hash
   
   # Store hashed password
   hashed_password = generate_password_hash(password)
   
   # Verify login
   if check_password_hash(stored_hash, provided_password):
       # Login successful
   ```

5. **Add CORS restrictions**
   ```python
   CORS(app, resources={
       r"/api/*": {"origins": ["https://yourdomain.com"]}
   })
   ```

6. **Log security events**
   ```python
   @app.route('/api/config', methods=['POST'])
   @login_required
   def config():
       logger.warning(f"Config modified by {session.get('username')} from {request.remote_addr}")
       ...
   ```

---

## Testing Authentication

### Test Protected Endpoints

```bash
# Should return 401 Unauthorized
curl -X POST http://localhost:5000/api/config \
  -H "Content-Type: application/json" \
  -d '{"confidence_threshold": 0.5}'

# Should return 401 Unauthorized  
curl -X POST http://localhost:5000/api/lots \
  -H "Content-Type: application/json" \
  -d '{"lot_id": "LOT-999", "name": "Test Lot"}'
```

### Test with Session

```bash
# 1. Login to get session cookie
curl -X POST http://localhost:5000/login \
  -c cookies.txt \
  -d "username=admin&password=admin123"

# 2. Use session cookie for protected endpoint
curl -X POST http://localhost:5000/api/config \
  -b cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"confidence_threshold": 0.5}'
```

### Test Public Endpoints

```bash
# Should work without authentication
curl http://localhost:5000/api/parking/status
curl http://localhost:5000/api/lots
curl http://localhost:5000/api/detection/status
```

---

## Audit Log

All protected endpoint access should be logged:

```python
# Add to protected endpoints
logger.info(f"API {request.method} {request.path} - User: {session.get('username', 'anonymous')} - IP: {request.remote_addr}")
```

View logs:
```bash
tail -f logs/flask.log | grep "API POST"
```

---

## Future Security Enhancements

### Planned
- [ ] Password hashing (bcrypt)
- [ ] API key authentication
- [ ] Rate limiting on all POST endpoints
- [ ] CSRF tokens for forms
- [ ] JWT tokens for API access

### Recommended
- [ ] Multi-factor authentication (2FA)
- [ ] OAuth/SSO integration
- [ ] Granular role-based access control (RBAC)
- [ ] Audit log viewing in admin panel
- [ ] IP whitelist/blacklist
- [ ] Automated security scanning

---

## Incident Response

If unauthorized access is suspected:

1. **Immediately change credentials** in `config.json`
2. **Restart the application** to invalidate all sessions
3. **Review logs** for suspicious activity:
   ```bash
   grep "Authentication required" logs/flask.log
   grep "POST /api" logs/flask.log
   ```
4. **Check for unauthorized changes** in database:
   ```sql
   SELECT * FROM parking_lot ORDER BY id DESC LIMIT 10;
   SELECT * FROM status_update ORDER BY timestamp DESC LIMIT 50;
   ```
5. **Enable additional logging** temporarily
6. **Consider IP restrictions** if specific IPs are attacking

---

## Contact & Support

For security concerns:
- Review logs in `logs/` directory
- Check Flask application logs for authentication failures
- Verify `config.json` hasn't been tampered with
- Ensure no unauthorized changes in database

**Remember:** Default credentials (`admin`/`admin123`) must be changed before any production deployment!
