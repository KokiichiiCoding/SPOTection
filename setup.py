"""
System Setup and Initialization
-------------------------------
This script prepares the Spotection system for its first run.
It performs the following actions:
1.  Creates the `config.json` file from the template if it doesn't exist.
2.  Initializes the PostgreSQL database by creating all necessary tables.
3.  Creates a default parking lot (`LOT-001`) if it doesn't already exist.
"""

import os
import json
from flask import Flask
from flaskweb.models import db, ParkingLot
from sqlalchemy.exc import OperationalError

def create_default_config():
    """
    Creates or updates config.json from the template.
    It preserves existing values in config.json and only adds missing keys from the template.
    """
    template_path = 'config.json.template'
    config_path = 'config.json'

    if not os.path.exists(template_path):
        print("⚠️ Warning: config.json.template not found. Cannot create or update config.")
        return None

    with open(template_path, 'r') as f:
        template_config = json.load(f)

    if not os.path.exists(config_path):
        print("📄 Creating default config.json from template...")
        with open(config_path, 'w') as f_config:
            json.dump(template_config, f_config, indent=4)
        print("✅ config.json created. Please review it and edit if necessary.")
        return template_config
    else:
        print("👍 config.json already exists. Checking for missing keys...")
        with open(config_path, 'r') as f_config:
            try:
                user_config = json.load(f_config)
            except json.JSONDecodeError:
                print("⚠️ Warning: config.json is corrupted. Overwriting with template.")
                user_config = {}

        # Add missing keys from template to user_config
        updated = False
        for key, value in template_config.items():
            if key not in user_config:
                user_config[key] = value
                updated = True
                print(f"    + Added missing key: '{key}'")

        if updated:
            with open(config_path, 'w') as f_config:
                json.dump(user_config, f_config, indent=4)
            print("✅ config.json has been updated with new keys.")
        else:
            print("    No missing keys found.")
            
        return user_config

def initialize_database(app):
    """Creates database tables and a default parking lot."""
    with app.app_context():
        print("🔄 Initializing database...")
        db.create_all()
        print("✅ Tables created successfully.")

        # Create a default parking lot if it doesn't exist
        config = app.config.get('MAIN_CONFIG', {})
        default_lot_id = config.get('default_lot_id', 'LOT-001')
        
        existing_lot = ParkingLot.query.filter_by(public_id=default_lot_id).first()
        if not existing_lot:
            print(f"🅿️  Creating default parking lot: {default_lot_id}")
            new_lot = ParkingLot(
                public_id=default_lot_id,
                name="Default Parking Lot",
                total_spots=0  # This will be updated as spots are calibrated/detected
            )
            db.session.add(new_lot)
            db.session.commit()
            print(f"✅ Default lot '{default_lot_id}' created.")
        else:
            print(f"👍 Default lot '{default_lot_id}' already exists.")

def prompt_for_db_config(config):
    """Prompts the user for database details and updates the config."""
    print("\n--- Database Configuration ---")
    print("Please provide your PostgreSQL database details.")

    db_user = input("Enter database user [default: postgres]: ") or "postgres"
    db_pass = input(f"Enter password for {db_user}: ")
    db_host = input("Enter database host [default: localhost]: ") or "localhost"
    db_port = input("Enter database port [default: 5432]: ") or "5432"
    db_name = input("Enter database name [default: parking_db]: ") or "parking_db"

    database_uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    config['database_uri'] = database_uri

    # Save the updated config
    with open('config.json', 'w') as f:
        json.dump(config, f, indent=4)
    
    print("\n✅ Database URI has been configured and saved to config.json.")
    return config

def main():
    """Main setup function."""
    print("="*50)
    print("🚀 Starting Spotection System Setup")
    print("="*50)

    # 1. Create/update config file
    config = create_default_config()
    if not config:
        print("❌ Setup failed: Could not load configuration.")
        return

    # 2. Check for database URI and prompt if not set
    if not config.get('database_uri'):
        config = prompt_for_db_config(config)

    # 3. Database initialization loop with retry
    while True:
        # Set up Flask app for database context
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = config.get('database_uri')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['MAIN_CONFIG'] = config # Make config accessible
        db.init_app(app)

        # Try to initialize database
        try:
            initialize_database(app)
            print("\n✅ Database connection successful and initialized.")
            break  # Exit the loop on success
        except OperationalError as e:
            print("\n" + "="*50)
            print("❌ Database Connection Failed.")
            print(f"   Error: {str(e.orig) if hasattr(e, 'orig') else str(e)}")
            print("   Most likely causes:")
            print("   - Incorrect username or password")
            print("   - Database server is not running")
            print("   - Database does not exist")
            print("   - Host or port is incorrect")
            print("="*50 + "\n")
            
            if input("Would you like to re-enter database credentials? (y/n): ").lower() == 'y':
                config = prompt_for_db_config(config)
            else:
                print("\n❌ Setup aborted. Please fix the database configuration and try again.")
                return

    print("\n🎉 Setup complete!")
    print("="*50)
    
    # Prompt to start the system
    print("\nWould you like to start the Spotection web application now?")
    start_choice = input("Start system? (y/n): ").lower()
    
    if start_choice == 'y':
        print("\n🚀 Starting Spotection web application...")
        print("Press Ctrl+C to stop the server\n")
        print("="*50)
        
        # Import and run Flask app
        try:
            import subprocess
            import sys
            
            # Detect if we're in a virtual environment
            venv_python = None
            if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
                # We're in a venv
                venv_python = sys.executable
            
            # Run Flask app
            if venv_python:
                subprocess.run([venv_python, "-m", "flask", "--app", "flaskweb.app", "run", "--debug"])
            else:
                subprocess.run([sys.executable, "-m", "flask", "--app", "flaskweb.app", "run", "--debug"])
                
        except KeyboardInterrupt:
            print("\n\n👋 Server stopped by user.")
        except Exception as e:
            print(f"\n❌ Error starting server: {e}")
            print("You can manually start it with: python -m flask --app flaskweb.app run --debug")
    else:
        print("\nYou can start the system later with:")
        print("  python -m flask --app flaskweb.app run --debug")
        print("\nOr run the setup again: python setup.py")

if __name__ == '__main__':
    main()
