"""
Spotection System Automated Setup
---------------------------------
This script performs complete system setup for end users using modular components.

Usage: python setup.py
"""

import sys
import os
import subprocess
import platform

def is_venv():
    """Check if running in a virtual environment"""
    return (hasattr(sys, 'real_prefix') or
            (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))

def find_existing_venv():
    """Find existing virtual environment in common locations"""
    venv_names = ['.venv', 'venv', '.virtualenv', 'env']
    for name in venv_names:
        if os.path.exists(name):
            # Check if it's actually a venv
            is_windows = platform.system() == "Windows"
            python_path = os.path.join(name, "Scripts" if is_windows else "bin", 
                                      "python.exe" if is_windows else "python")
            if os.path.exists(python_path):
                return name, python_path
    return None, None

def create_venv(venv_path=".venv"):
    """Create a new virtual environment"""
    print(f"📦 Creating virtual environment: {venv_path}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "venv", venv_path],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode != 0:
            print(f"❌ Failed to create virtual environment:\n{result.stderr}")
            return None
        
        is_windows = platform.system() == "Windows"
        python_path = os.path.join(venv_path, "Scripts" if is_windows else "bin",
                                   "python.exe" if is_windows else "python")
        print(f"✅ Virtual environment created: {venv_path}")
        return python_path
    except Exception as e:
        print(f"❌ Error creating virtual environment: {e}")
        return None

def activate_and_rerun(python_path):
    """Rerun the script in the virtual environment"""
    print(f"\n🔄 Restarting setup in virtual environment...\n")
    try:
        # Run setup.py with the venv Python
        result = subprocess.run(
            [python_path, "setup.py"],
            cwd=os.getcwd()
        )
        sys.exit(result.returncode)
    except Exception as e:
        print(f"❌ Error running setup in virtual environment: {e}")
        sys.exit(1)

def install_dependencies(show_progress=True):
    """Install dependencies from requirements.txt with progress"""
    print("\n📦 Installing dependencies from requirements.txt...")
    print("   This may take a few minutes...\n")
    
    if not os.path.exists('requirements.txt'):
        print("❌ requirements.txt not found!")
        return False
    
    # Verify we're using the right Python
    print(f"🐍 Using Python: {sys.executable}")
    print(f"🐍 Python version: {sys.version.split()[0]}")
    
    try:
        # Install with real-time output using explicit pip module
        if show_progress:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"],
                text=True,
                timeout=600  # 10 minute timeout
            )
        else:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade"],
                capture_output=True,
                text=True,
                timeout=600
            )
        
        if result.returncode != 0:
            print(f"❌ Installation failed")
            if not show_progress and result.stderr:
                print(result.stderr)
            return False
        
        # Verify installation
        print("\n🔍 Verifying installation...")
        verify_result = subprocess.run(
            [sys.executable, "-c", "import flask_limiter; import sqlalchemy; print('✓ Key packages imported successfully')"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if verify_result.returncode != 0:
            print(f"⚠️  Warning: Package verification failed")
            print(f"   Error: {verify_result.stderr}")
            print(f"   Trying to import key modules...")
            return False
        else:
            print(verify_result.stdout.strip())
        
        print("\n✅ Dependencies installed successfully\n")
        return True
        
    except subprocess.TimeoutExpired:
        print("❌ Installation timed out")
        return False
    except Exception as e:
        print(f"❌ Installation error: {e}")
        return False

# Main setup logic
print("=" * 60)
print("🚀 Spotection Setup")
print("=" * 60)

# Check if in virtual environment
if not is_venv():
    print("\n⚠️  Not running in a virtual environment!")
    
    # Check for existing venv
    venv_name, venv_python = find_existing_venv()
    
    if venv_name:
        print(f"✅ Found existing virtual environment: {venv_name}")
        activate_and_rerun(venv_python)
    else:
        print("No virtual environment found.")
        create_new = input("Create new virtual environment? (y/n): ").lower()
        
        if create_new == 'y':
            venv_python = create_venv(".venv")
            if venv_python:
                activate_and_rerun(venv_python)
            else:
                print("\n❌ Setup cannot continue without a virtual environment")
                sys.exit(1)
        else:
            print("\n❌ Setup requires a virtual environment to avoid conflicts")
            print("Please create and activate a virtual environment:")
            print("  python -m venv .venv")
            if platform.system() == "Windows":
                print("  .venv\\Scripts\\activate")
            else:
                print("  source .venv/bin/activate")
            print("Then run setup.py again")
            sys.exit(1)
else:
    print("\n✅ Running in virtual environment")

# Always install/upgrade dependencies in venv
if not install_dependencies(show_progress=True):
    print("\n❌ Failed to install dependencies. Please run manually:")
    print(f"   {sys.executable} -m pip install -r requirements.txt")
    sys.exit(1)

# Now import setup modules
from setup import ConfigManager, DatabaseManager, EnvironmentManager, apply_migrations

class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(message):
    """Print a styled header message"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{message}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

def print_success(message):
    """Print a success message"""
    print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")

def print_error(message):
    """Print an error message"""
    print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")

def print_warning(message):
    """Print a warning message"""
    print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}")

def print_info(message):
    """Print an info message"""
    print(f"{Colors.OKCYAN}ℹ️  {message}{Colors.ENDC}")


def setup_environment():
    """Set up Python environment"""
    print_header("Step 1: Environment Setup")
    
    env_manager = EnvironmentManager()
    
    # Check Python version
    print_info("Checking Python version...")
    is_compatible, version = env_manager.check_python_version()
    if not is_compatible:
        print_error(f"Python 3.8+ required. Found: {version}")
        return None
    print_success(f"Python {version} detected")
    
    # Create virtual environment
    if env_manager.venv_exists():
        print_warning("Virtual environment already exists")
        recreate = input(f"{Colors.OKCYAN}Recreate? (y/n): {Colors.ENDC}").lower() == 'y'
        success, msg = env_manager.create_venv(recreate=recreate)
    else:
        print_info("Creating virtual environment...")
        success, msg = env_manager.create_venv()
    
    if not success:
        print_error(msg)
        return None
    print_success(msg)
    
    # Upgrade pip
    print_info("Upgrading pip...")
    success, msg = env_manager.upgrade_pip()
    if not success:
        print_warning(f"Pip upgrade failed: {msg}")
    else:
        print_success(msg)
    
    # Install dependencies
    print_info("Installing dependencies (this may take a few minutes)...")
    success, msg = env_manager.install_requirements()
    if not success:
        print_error(msg)
        cont = input(f"{Colors.WARNING}Continue anyway? (y/n): {Colors.ENDC}").lower()
        if cont != 'y':
            return None
    else:
        print_success(msg)
    
    # Create directories
    directories = [
        'uploads', 
        'screenshots', 
        'camera_feeds', 
        'logs', 
        'output', 
        'data/layouts',
        'media_archive',
        'media_archive/images',
        'media_archive/videos',
        'media_archive/thumbnails'
    ]
    success, msg = env_manager.create_directories(directories)
    if success:
        print_success(msg)
    
    return env_manager


def setup_configuration():
    """Set up application configuration"""
    print_header("Step 2: Configuration Setup")
    
    config_manager = ConfigManager()
    
    # Load or create config
    print_info("Loading configuration...")
    config = config_manager.load()
    
    # If config doesn't exist, create from template
    if not config or not config_manager.get('secret_key'):
        print_info("Creating new configuration from template...")
        config = config_manager.create_from_template()
        print_success("Configuration created")
    else:
        print_success("Configuration loaded")
        
        # Update missing keys
        if config_manager.update_missing_keys():
            print_info("Added missing configuration keys")
    
    # Admin credentials setup
    print("\n" + Colors.HEADER + "Admin Account" + Colors.ENDC)
    current_user = config_manager.get('admin_username', 'admin')
    current_pass = config_manager.get('admin_password', 'admin123')
    
    print_warning(f"Current username: {current_user}")
    
    if current_pass == 'CHANGE_THIS_PASSWORD' or current_pass == 'admin123':
        print_warning("Using default password - must be changed!")
        change = 'y'
    else:
        change = input(f"{Colors.OKCYAN}Change admin credentials? (y/n): {Colors.ENDC}").lower()
    
    if change == 'y':
        username = input(f"{Colors.OKCYAN}Admin username [{current_user}]: {Colors.ENDC}") or current_user
        password = input(f"{Colors.OKCYAN}Admin password: {Colors.ENDC}")
        
        if password:
            config_manager.update_admin_credentials(username, password)
            print_success("Admin credentials updated")
    
    # Validate configuration
    is_valid, errors = config_manager.validate()
    if not is_valid:
        print_warning("Configuration validation warnings:")
        for error in errors:
            print(f"  - {error}")
    
    # Ensure media storage is configured
    if not config_manager.get('media_storage'):
        print_info("Setting up media storage configuration...")
        config_manager.set('media_storage', {
            'enabled': True,
            'base_path': 'media_archive',
            'max_size_gb': 20.0,
            'capture_interval': 300,
            'capture_on_change': True,
            'video_recording': False,
            'video_segment_duration': 300,
            'cleanup_enabled': True,
            'keep_thumbnails': True
        })
        config_manager.save()
        print_success("Media storage configured")
    else:
        # Show current media storage settings
        ms_config = config_manager.get('media_storage')
        print_info(f"Media Storage: {'Enabled' if ms_config.get('enabled') else 'Disabled'}")
        if ms_config.get('enabled'):
            print_info(f"  - Max size: {ms_config.get('max_size_gb', 20)}GB")
            print_info(f"  - Video recording: {'Yes' if ms_config.get('video_recording') else 'No'}")
    
    return config_manager


def setup_database(config_manager):
    """Set up database"""
    print_header("Step 3: Database Setup")
    
    db_uri = config_manager.get('database_uri')
    
    # Prompt for database credentials if needed
    if not db_uri or 'password123' in db_uri:
        print_warning("Database credentials need configuration")
        
        db_user = input(f"{Colors.OKCYAN}Database user [spotection_client]: {Colors.ENDC}") or "spotection_client"
        db_pass = input(f"{Colors.OKCYAN}Password: {Colors.ENDC}")
        db_host = input(f"{Colors.OKCYAN}Host [localhost]: {Colors.ENDC}") or "localhost"
        db_port = int(input(f"{Colors.OKCYAN}Port [5432]: {Colors.ENDC}") or "5432")
        db_name = input(f"{Colors.OKCYAN}Database [parking_db]: {Colors.ENDC}") or "parking_db"
        
        db_uri = config_manager.update_database_uri(db_user, db_pass, db_host, db_port, db_name)
        print_success("Database URI configured")
    
    # Test connection
    db_manager = DatabaseManager(db_uri)
    
    max_retries = 3
    for attempt in range(max_retries):
        print_info(f"Testing database connection (attempt {attempt + 1}/{max_retries})...")
        
        success, error = db_manager.test_connection()
        
        if success:
            print_success("Database connection successful")
            break
        else:
            print_error(f"Connection failed: {error}")
            
            if attempt < max_retries - 1:
                retry = input(f"{Colors.WARNING}Try different credentials? (y/n): {Colors.ENDC}").lower()
                if retry == 'y':
                    db_user = input(f"{Colors.OKCYAN}Database user: {Colors.ENDC}")
                    db_pass = input(f"{Colors.OKCYAN}Password: {Colors.ENDC}")
                    db_host = input(f"{Colors.OKCYAN}Host [localhost]: {Colors.ENDC}") or "localhost"
                    db_port = int(input(f"{Colors.OKCYAN}Port [5432]: {Colors.ENDC}") or "5432")
                    db_name = input(f"{Colors.OKCYAN}Database [parking_db]: {Colors.ENDC}") or "parking_db"
                    
                    db_uri = config_manager.update_database_uri(db_user, db_pass, db_host, db_port, db_name)
                    db_manager = DatabaseManager(db_uri)
                else:
                    print_error("Database setup failed")
                    return None
            else:
                print_error("Maximum connection attempts reached")
                return None
    
    # Apply migrations
    print_info("Applying database migrations...")
    success, messages = apply_migrations(db_manager)
    
    for msg in messages:
        if '✓' in msg:
            print_success(msg)
        elif '✗' in msg:
            print_error(msg)
        else:
            print_info(msg)
    
    if not success:
        print_error("Migration failed")
        return None
    
    # Create default lot
    print_info("Creating default parking lot...")
    default_lot_id = config_manager.get('default_lot_id', 'LOT-001')
    success, msg = db_manager.create_default_lot(default_lot_id)
    
    if success:
        print_success(msg)
    else:
        print_error(msg)
    
    return db_manager


def start_application(env_manager):
    """Start the application"""
    print_header("Starting Spotection")
    
    print_info("Starting web server...")
    print_info("Press Ctrl+C to stop")
    print_info("Access at: http://localhost:5000")
    print(f"\n{Colors.OKGREEN}{'='*60}{Colors.ENDC}\n")
    
    import subprocess
    
    try:
        python_exe = env_manager.get_venv_python()
        subprocess.run([python_exe, "flaskweb/app.py"])
    except KeyboardInterrupt:
        print(f"\n\n{Colors.OKGREEN}👋 Server stopped{Colors.ENDC}")
    except Exception as e:
        print_error(f"Error starting server: {e}")
        print_info(f"\nManually start with: {env_manager.get_activation_command()}")
        print_info(f"Then: python flaskweb/app.py")


def main():
    """Main setup function"""
    print_header("🚀 Spotection Automated Setup")
    
    try:
        # Step 1: Environment
        env_manager = setup_environment()
        if not env_manager:
            return
        
        # Step 2: Configuration
        config_manager = setup_configuration()
        if not config_manager:
            return
        
        # Step 3: Database
        db_manager = setup_database(config_manager)
        if not db_manager:
            print_warning("Database setup incomplete")
            print_info("You can configure it later and run: python setup.py")
        
        # Complete
        print_header("🎉 Setup Complete!")
        
        print(f"\n{Colors.OKGREEN}Next steps:{Colors.ENDC}")
        print("  1. Review config.json")
        print("  2. Start the application")
        print("  3. Visit http://localhost:5000")
        print("  4. Log in with admin credentials")
        print("  5. Calibrate parking spaces\n")
        
        # Start application
        start = input(f"{Colors.OKCYAN}Start application now? (y/n): {Colors.ENDC}").lower()
        
        if start == 'y':
            start_application(env_manager)
        else:
            print(f"\n{Colors.OKGREEN}Start later with:{Colors.ENDC}")
            print(f"  {env_manager.get_activation_command()}")
            print(f"  python flaskweb/app.py")
    
    except KeyboardInterrupt:
        print(f"\n\n{Colors.WARNING}Setup interrupted{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
