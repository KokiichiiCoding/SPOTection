"""
Configuration Verification Script
Tests all configuration settings and database connectivity
"""

import json
import sys
import os

def test_config():
    """Test configuration file"""
    print("=" * 60)
    print("CONFIGURATION VERIFICATION")
    print("=" * 60)
    print()
    
    # 1. Check if config.json exists
    print("1. Checking config.json...")
    if not os.path.exists('config.json'):
        print("   ❌ config.json not found!")
        return False
    print("   ✅ config.json found")
    
    # 2. Validate JSON syntax
    print("\n2. Validating JSON syntax...")
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        print("   ✅ Valid JSON")
    except json.JSONDecodeError as e:
        print(f"   ❌ Invalid JSON: {e}")
        return False
    
    # 3. Check required keys
    print("\n3. Checking required keys...")
    required_keys = [
        'database_uri',
        'admin_username',
        'admin_password',
        'secret_key',
        'model_path',
        'default_lot_id'
    ]
    
    missing_keys = []
    for key in required_keys:
        if key not in config:
            missing_keys.append(key)
            print(f"   ❌ Missing: {key}")
        else:
            # Don't print sensitive values
            if key in ['admin_password', 'secret_key']:
                value = "***SET***" if config[key] else "***NOT SET***"
            else:
                value = config[key]
            print(f"   ✅ {key}: {value}")
    
    if missing_keys:
        print(f"\n   ❌ Missing {len(missing_keys)} required keys")
        return False
    
    # 4. Check media storage configuration
    print("\n4. Checking media storage configuration...")
    if 'media_storage' in config:
        ms_config = config['media_storage']
        print(f"   ✅ Media storage enabled: {ms_config.get('enabled', False)}")
        print(f"   ✅ Base path: {ms_config.get('base_path', 'NOT SET')}")
        print(f"   ✅ Max size: {ms_config.get('max_size_gb', 'NOT SET')} GB")
        print(f"   ✅ Capture interval: {ms_config.get('capture_interval', 'NOT SET')}s")
    else:
        print("   ⚠️  Media storage configuration not found (optional)")
    
    # 5. Check security settings
    print("\n5. Checking security settings...")
    
    # Check secret key
    secret_key = config.get('secret_key', '')
    if not secret_key or secret_key == 'your-secret-key-here-change-me':
        print("   ❌ Secret key not set or using default")
        return False
    elif len(secret_key) < 32:
        print("   ⚠️  Secret key too short (should be 32+ characters)")
    else:
        print(f"   ✅ Secret key properly configured ({len(secret_key)} chars)")
    
    # Check admin password
    admin_pass = config.get('admin_password', '')
    if admin_pass in ['admin', 'admin123', 'CHANGE_THIS_PASSWORD', 'password']:
        print("   ⚠️  Admin password is using a common/default value")
        print("      Consider changing it for production!")
    else:
        print("   ✅ Admin password configured")
    
    # 6. Check database URI
    print("\n6. Checking database configuration...")
    db_uri = config.get('database_uri', '')
    if not db_uri:
        print("   ❌ Database URI not set")
        return False
    
    if 'password123' in db_uri or 'your_password' in db_uri:
        print("   ⚠️  Database URI contains default password")
    
    print(f"   ✅ Database URI configured")
    
    # Try to parse database URI
    if db_uri.startswith('postgresql://'):
        try:
            # Extract components
            uri_parts = db_uri.replace('postgresql://', '').split('@')
            if len(uri_parts) == 2:
                user_pass = uri_parts[0].split(':')
                host_db = uri_parts[1].split('/')
                
                print(f"      User: {user_pass[0]}")
                print(f"      Host: {host_db[0].split(':')[0]}")
                print(f"      Port: {host_db[0].split(':')[1] if ':' in host_db[0] else '5432'}")
                print(f"      Database: {host_db[1] if len(host_db) > 1 else 'NOT SET'}")
        except:
            print("      ⚠️  Could not parse database URI")
    
    # 7. Test database connection
    print("\n7. Testing database connection...")
    try:
        import psycopg2
        # Parse connection params from URI
        from urllib.parse import urlparse
        parsed = urlparse(db_uri)
        
        try:
            conn = psycopg2.connect(
                dbname=parsed.path[1:],
                user=parsed.username,
                password=parsed.password,
                host=parsed.hostname,
                port=parsed.port or 5432,
                connect_timeout=5
            )
            conn.close()
            print("   ✅ Database connection successful!")
        except psycopg2.OperationalError as e:
            print(f"   ❌ Database connection failed: {e}")
            print("      Make sure PostgreSQL is running and credentials are correct")
            return False
    except ImportError:
        print("   ⚠️  psycopg2 not installed - skipping connection test")
        print("      Install with: pip install psycopg2-binary")
    
    # 8. Check YOLO model
    print("\n8. Checking YOLO model...")
    model_path = config.get('model_path', 'yolov8n.pt')
    if os.path.exists(model_path):
        size_mb = os.path.getsize(model_path) / (1024 * 1024)
        print(f"   ✅ Model found: {model_path} ({size_mb:.1f} MB)")
    else:
        print(f"   ⚠️  Model not found: {model_path}")
        print("      It will be downloaded on first run")
    
    # 9. Check directories
    print("\n9. Checking required directories...")
    directories = [
        config.get('output_dir', 'output/'),
        config.get('log_dir', 'logs/'),
        'uploads',
        'screenshots',
        'camera_feeds',
        'data/layouts'
    ]
    
    if 'media_storage' in config:
        directories.append(config['media_storage'].get('base_path', 'media_archive'))
    
    for directory in directories:
        if os.path.exists(directory):
            print(f"   ✅ {directory}")
        else:
            print(f"   ⚠️  {directory} (will be created)")
    
    print("\n" + "=" * 60)
    print("✅ CONFIGURATION VERIFICATION COMPLETE")
    print("=" * 60)
    print()
    print("Summary:")
    print("  • Configuration file is valid")
    print("  • All required keys are present")
    print("  • Security settings configured")
    if 'media_storage' in config:
        print("  • Media storage system ready")
    print()
    print("⚠️  Warnings (if any):")
    print("  • Change default admin password before production")
    print("  • Make sure PostgreSQL database is accessible")
    print()
    
    return True


if __name__ == '__main__':
    try:
        success = test_config()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
