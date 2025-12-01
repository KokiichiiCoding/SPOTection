# Authentication Guide

## Overview

SPOTection now includes authentication to protect the admin panel from unauthorized access.

## Default Credentials

**⚠️ IMPORTANT: Change these immediately in production!**

- **Username:** `admin`
- **Password:** `admin123`

## Configuration

Authentication settings are stored in `config.json`:

```json
{
  "admin_username": "admin",
  "admin_password": "admin123",
  "secret_key": "CHANGE_THIS_TO_A_RANDOM_STRING"
}
```

### Changing Admin Credentials

1. Open `config.json`
2. Update the `admin_username` and `admin_password` fields
3. **Change the `secret_key`** to a random string for session security
4. Restart the Flask application

### Generating a Secure Secret Key

Use Python to generate a secure random key:

```python
import secrets
print(secrets.token_hex(32))
```

Copy the output and use it as your `secret_key` in `config.json`.

## Protected Routes

The following routes require authentication:

- `/admin` - Admin panel with calibration and configuration tools

## Protected API Endpoints

All API endpoints that can modify data or configuration require authentication:

- **Configuration:** `/api/config` (POST), `/api/camera/config` (POST), `/api/camera/refresh` (POST)
- **Detection:** `/api/detection/load_model` (POST), `/api/detection/control` (POST)  
- **Lot Management:** `/api/lots` (POST), `/api/lots/<lot_id>` (PUT/DELETE), `/api/lot/<lot_id>/camera` (PUT), `/api/lot/<lot_id>/status/cleanup` (POST)
- **Calibration:** `/api/lot/<lot_id>/calibration` (POST), `/api/parking/space/<space_id>` (PUT)

**📖 See [API_SECURITY.md](API_SECURITY.md) for complete API security documentation.**

## Public Routes

These routes are accessible without login:

- `/` - Main dashboard with live detection feed
- All `/api/*` endpoints (for programmatic access)

## Login Flow

1. Attempting to access `/admin` without authentication redirects to `/login`
2. After successful login, users are redirected back to the requested page
3. Sessions persist until logout or browser closure
4. Use `/logout` to manually end the session

## Security Best Practices

1. **Change default credentials immediately**
2. **Use a strong, random secret key**
3. **Don't commit credentials to version control**
4. **Use HTTPS in production** (sessions use cookies that should be secure)
5. **Consider adding rate limiting** for login attempts
6. **Implement password hashing** for production use (currently plaintext)

## Future Enhancements

For production deployment, consider:

- Password hashing (bcrypt, argon2)
- Multi-user support with roles
- Database-backed user accounts
- Two-factor authentication
- Password reset functionality
- Login attempt rate limiting
- Session timeout configuration
- API key authentication for endpoints

## Troubleshooting

### "Invalid credentials" error

- Check username and password in `config.json`
- Ensure the application has been restarted after config changes

### Redirected to login repeatedly

- Check that `secret_key` is set in `config.json`
- Clear browser cookies and try again
- Check Flask logs for session errors

### Can't access admin panel

- Verify you're logged in (check for "Logout" link in navbar)
- Try logging out and logging back in
- Check browser console for errors
