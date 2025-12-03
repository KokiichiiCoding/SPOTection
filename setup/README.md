# Setup Package - Modular Setup Architecture

This package contains modular components for Spotection system setup, enabling scalable and maintainable configuration management.

## Architecture

The setup system is split into focused modules, each with a single responsibility:

- **config_manager.py** - Configuration file operations
- **db_manager.py** - Database operations and schema versioning  
- **env_manager.py** - Virtual environment and dependency management
- **schema.py** - Database schema migrations

## Modules

### ConfigManager (`config_manager.py`)

Handles all `config.json` operations:

```python
from setup import ConfigManager

config = ConfigManager()

# Load configuration
config.load()

# Get values
db_uri = config.get('database_uri')

# Set values
config.set('debug', True)

# Update database credentials
config.update_database_uri('user', 'pass', 'localhost', 5432, 'db_name')

# Validate configuration
is_valid, errors = config.validate()
```

**Methods:**
- `load()` - Load config.json
- `save()` - Save current configuration
- `create_from_template()` - Create from config.json.template with secure key generation
- `update_missing_keys()` - Merge new template keys into existing config
- `validate()` - Check required fields, returns `(bool, List[str])`
- `get(key, default)` - Get configuration value
- `set(key, value)` - Set configuration value  
- `update_database_uri(...)` - Update database connection
- `update_admin_credentials(...)` - Update admin credentials

### DatabaseManager (`db_manager.py`)

Handles database operations and schema versioning:

```python
from setup import DatabaseManager

db = DatabaseManager(database_uri)

# Test connection
success, error = db.test_connection()

# Apply migrations
from setup.schema import apply_migrations
success, messages = apply_migrations(db)

# Check schema version
version = db.get_schema_version()

# Create default lot
success, msg = db.create_default_lot('LOT-001')
```

**Methods:**
- `initialize_app()` - Create Flask app context
- `test_connection()` - Validate database credentials
- `create_all_tables()` - Create database schema
- `drop_all_tables()` - Drop all tables (careful!)
- `get_schema_version()` / `set_schema_version()` - Track migrations
- `create_default_lot(lot_id, name)` - Initialize default parking lot
- `get_table_list()` - List all tables
- `get_table_info(table_name)` - Get table schema
- `backup_data()` - Export database to JSON

### EnvironmentManager (`env_manager.py`)

Handles virtual environment and dependencies:

```python
from setup import EnvironmentManager

env = EnvironmentManager()

# Check Python version
is_compatible, version = env.check_python_version()

# Create venv
success, msg = env.create_venv()

# Install dependencies
success, msg = env.install_requirements()

# Check package
is_installed = env.check_package_installed('flask')
```

**Methods:**
- `get_python_command()` - Returns 'python' or 'python3'
- `check_python_version()` - Validate Python 3.8+ requirement
- `venv_exists()` - Check if venv directory exists
- `create_venv(recreate=False)` - Create virtual environment
- `upgrade_pip()` - Upgrade pip to latest
- `install_requirements()` - Install from requirements.txt
- `install_package(package)` - Install single package
- `get_installed_packages()` - List installed packages
- `check_package_installed(package)` - Test package availability
- `create_directories(dirs)` - Create app directories
- `get_activation_command()` - Platform-specific activation

### Schema Migrations (`schema.py`)

Define and apply database schema migrations:

```python
from setup import get_schema_version, apply_migrations, DatabaseManager

# Check current version
version = get_schema_version()

# Apply migrations
db = DatabaseManager(uri)
success, messages = apply_migrations(db)
```

**Components:**
- `CURRENT_SCHEMA_VERSION` - Latest schema version
- `Migration` - Migration class (version, description, upgrade_func, downgrade_func)
- `MIGRATIONS` - Ordered list of all migrations
- `get_schema_version()` - Get current schema version
- `get_migrations_to_apply(current)` - Determine pending migrations
- `apply_migrations(db_manager)` - Execute all pending migrations

## Adding New Migrations

To add a new database schema change:

### 1. Define Migration Function

```python
# In schema.py

def migration_1_4_0_add_users_table(db_manager: DatabaseManager) -> tuple[bool, str]:
    """Add users table for multi-user support"""
    try:
        db_manager.initialize_app()
        from flaskweb.models import db
        
        # Your migration logic
        db.engine.execute("""
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        return True, "Users table created successfully"
    except Exception as e:
        return False, f"Failed to create users table: {e}"


def migration_1_4_0_downgrade(db_manager: DatabaseManager) -> tuple[bool, str]:
    """Remove users table"""
    try:
        db_manager.initialize_app()
        from flaskweb.models import db
        
        db.engine.execute("DROP TABLE IF EXISTS users")
        return True, "Users table removed"
    except Exception as e:
        return False, f"Failed to remove users table: {e}"
```

### 2. Add to MIGRATIONS List

```python
# In schema.py

MIGRATIONS = [
    # ... existing migrations ...
    Migration(
        version="1.4.0",
        description="Add users table for multi-user support",
        upgrade_func=migration_1_4_0_add_users_table,
        downgrade_func=migration_1_4_0_downgrade
    )
]

# Update version
CURRENT_SCHEMA_VERSION = "1.4.0"
```

### 3. Run Setup

```bash
python setup.py
```

The migration will automatically be detected and applied!

## Migration Best Practices

1. **Incremental Changes**: Keep migrations small and focused
2. **Version Numbers**: Use semantic versioning (major.minor.patch)
3. **Descriptive Names**: Use clear function names like `migration_X_Y_Z_what_it_does`
4. **Error Handling**: Always return `(bool, str)` for success/failure
5. **Downgrade Functions**: Implement reversible migrations when possible
6. **Test First**: Test migrations on a copy of production database
7. **Document**: Add clear docstrings explaining what the migration does

## Example Migration Patterns

### Adding a Column

```python
def migration_1_5_0_add_description_to_lots(db_manager):
    """Add description field to parking_lot table"""
    try:
        db_manager.initialize_app()
        from flaskweb.models import db
        
        db.engine.execute("""
            ALTER TABLE parking_lot 
            ADD COLUMN description TEXT
        """)
        
        return True, "Added description column"
    except Exception as e:
        return False, f"Failed: {e}"
```

### Adding an Index

```python
def migration_1_6_0_add_email_index(db_manager):
    """Add index on user email for faster lookups"""
    try:
        db_manager.initialize_app()
        from flaskweb.models import db
        
        db.engine.execute("""
            CREATE INDEX idx_user_email ON users(email)
        """)
        
        return True, "Email index created"
    except Exception as e:
        return False, f"Failed: {e}"
```

### Adding a Table with Foreign Keys

```python
def migration_1_7_0_add_audit_log(db_manager):
    """Add audit log table"""
    try:
        db_manager.initialize_app()
        from flaskweb.models import db
        
        db.engine.execute("""
            CREATE TABLE audit_log (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                action VARCHAR(50) NOT NULL,
                target_table VARCHAR(50),
                target_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details JSONB
            )
        """)
        
        return True, "Audit log table created"
    except Exception as e:
        return False, f"Failed: {e}"
```

## Troubleshooting

### Migration Fails

Check `schema_version` table:
```python
db = DatabaseManager(uri)
version = db.get_schema_version()
print(f"Current version: {version}")
```

### Reset Schema Version

```python
db = DatabaseManager(uri)
db.set_schema_version("1.0.0")  # Reset to specific version
```

### Backup Before Migration

```python
db = DatabaseManager(uri)
backup = db.backup_data()
```

### Manual Migration

```python
from setup import DatabaseManager, MIGRATIONS

db = DatabaseManager(uri)

# Apply specific migration
migration = MIGRATIONS[3]  # Version 1.3.0
success, msg = migration.upgrade_func(db)
print(msg)
```

## Testing

Each module can be unit tested independently:

```python
# test_config_manager.py
from setup import ConfigManager

def test_load_config():
    config = ConfigManager('test_config.json')
    data = config.load()
    assert 'secret_key' in data

def test_validate():
    config = ConfigManager()
    config.set('database_uri', '')
    is_valid, errors = config.validate()
    assert not is_valid
    assert 'database_uri' in str(errors)
```

## Future Enhancements

Potential improvements:

1. **CLI Tool**: `python -m setup.db_manager backup`
2. **Migration Rollback**: `python -m setup.schema downgrade 1.2.0`
3. **Dry Run**: Test migrations without applying
4. **Migration History**: Track when/who applied migrations
5. **Auto Backup**: Backup before each migration
6. **Parallel Migrations**: Apply independent migrations in parallel

## Dependencies

- Python 3.8+
- Flask
- SQLAlchemy
- psycopg2-binary (PostgreSQL)

## License

Same as parent project (SPOTection)
