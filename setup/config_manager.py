"""
Configuration Manager
Handles all config.json operations including creation, validation, and updates
"""

import json
import os
import secrets
from typing import Dict, Optional, Any


class ConfigManager:
    """Manages application configuration"""
    
    DEFAULT_CONFIG = {
        "model_path": "yolov8n.pt",
        "confidence_threshold": 0.25,
        "overlap_threshold": 0.3,
        "iou_threshold": 0.45,
        "detection_image_size": 640,
        "detection_threshold": 0.25,
        "image_enhancement": True,
        "vehicle_classes": ["car", "truck", "bus", "motorcycle", "bicycle"],
        "update_interval": 5,
        "database_uri": "postgresql://spotection_client:password123@localhost:5432/parking_db",
        "default_lot_id": "LOT-001",
        "camera_url": None,
        "camera_source": "placeholder",
        "extraction_pattern_type": "auto",
        "extraction_pattern_value": None,
        "output_dir": "output/",
        "log_dir": "logs/",
        "screenshot_interval": 120,
        "save_raw_screenshots": True,
        "admin_username": "admin",
        "admin_password": "CHANGE_THIS_PASSWORD",
        "secret_key": None,
        "host": "0.0.0.0",
        "port": 5000,
        "debug": False,
        "calibration_data": [],
        "media_storage": {
            "enabled": True,
            "base_path": "media_archive",
            "max_size_gb": 20.0,
            "capture_interval": 300,
            "capture_on_change": True,
            "video_recording": False,
            "video_segment_duration": 300,
            "cleanup_enabled": True,
            "keep_thumbnails": True
        }
    }
    
    REQUIRED_KEYS = [
        "database_uri",
        "admin_username",
        "admin_password",
        "secret_key"
    ]
    
    def __init__(self, config_path: str = 'config.json', template_path: str = 'config.json.template'):
        self.config_path = config_path
        self.template_path = template_path
        self._config: Optional[Dict[str, Any]] = None
    
    def load(self) -> Dict[str, Any]:
        """Load configuration from file or template"""
        # Try loading from config.json
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
                return self._config
            except json.JSONDecodeError:
                print(f"Warning: {self.config_path} is corrupted")
        
        # Try loading from template
        if os.path.exists(self.template_path):
            with open(self.template_path, 'r') as f:
                self._config = json.load(f)
            return self._config
        
        # Use default config
        self._config = self.DEFAULT_CONFIG.copy()
        return self._config
    
    def save(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """Save configuration to file"""
        if config is not None:
            self._config = config
        
        if self._config is None:
            return False
        
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def create_from_template(self) -> Dict[str, Any]:
        """Create config.json from template"""
        if os.path.exists(self.template_path):
            with open(self.template_path, 'r') as f:
                config = json.load(f)
        else:
            config = self.DEFAULT_CONFIG.copy()
        
        # Generate secure secret key if not present
        if not config.get('secret_key') or config['secret_key'] == 'CHANGE_THIS_TO_A_RANDOM_STRING_USE_secrets.token_hex(32)':
            config['secret_key'] = secrets.token_hex(32)
        
        self._config = config
        self.save()
        return config
    
    def update_missing_keys(self) -> bool:
        """Update config with missing keys from template"""
        if self._config is None:
            self.load()
        
        template_config = self.DEFAULT_CONFIG.copy()
        if os.path.exists(self.template_path):
            with open(self.template_path, 'r') as f:
                template_config.update(json.load(f))
        
        updated = False
        for key, value in template_config.items():
            if key not in self._config:
                self._config[key] = value
                updated = True
            # Special handling for nested media_storage config
            elif key == 'media_storage' and isinstance(value, dict):
                if not isinstance(self._config[key], dict):
                    self._config[key] = value
                    updated = True
                else:
                    for sub_key, sub_value in value.items():
                        if sub_key not in self._config[key]:
                            self._config[key][sub_key] = sub_value
                            updated = True
        
        if updated:
            self.save()
        
        return updated
    
    def validate(self) -> tuple[bool, list[str]]:
        """Validate configuration"""
        if self._config is None:
            self.load()
        
        errors = []
        
        # Check required keys
        for key in self.REQUIRED_KEYS:
            if key not in self._config:
                errors.append(f"Missing required key: {key}")
            elif not self._config[key]:
                errors.append(f"Required key '{key}' is empty")
        
        # Validate specific fields
        if self._config.get('admin_password') == 'CHANGE_THIS_PASSWORD':
            errors.append("Admin password must be changed from default")
        
        if self._config.get('secret_key') and 'CHANGE_THIS' in self._config['secret_key']:
            errors.append("Secret key must be changed from default")
        
        if self._config.get('port') and not (1024 <= self._config['port'] <= 65535):
            errors.append(f"Port must be between 1024 and 65535")
        
        return len(errors) == 0, errors
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value"""
        if self._config is None:
            self.load()
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set a configuration value"""
        if self._config is None:
            self.load()
        self._config[key] = value
    
    def update_database_uri(self, user: str, password: str, host: str = 'localhost', 
                           port: int = 5432, database: str = 'parking_db') -> str:
        """Update database URI"""
        uri = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self.set('database_uri', uri)
        self.save()
        return uri
    
    def update_admin_credentials(self, username: str, password: str) -> None:
        """Update admin credentials and regenerate secret key"""
        self.set('admin_username', username)
        self.set('admin_password', password)
        self.set('secret_key', secrets.token_hex(32))
        self.save()
    
    def get_config(self) -> Dict[str, Any]:
        """Get the full configuration dictionary"""
        if self._config is None:
            self.load()
        return self._config.copy()
