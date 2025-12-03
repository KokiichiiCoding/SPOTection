"""
Setup package for Spotection
Contains modular setup components for easy maintenance and scaling
"""

from .config_manager import ConfigManager
from .db_manager import DatabaseManager
from .env_manager import EnvironmentManager
from .schema import get_schema_version, apply_migrations

__all__ = [
    'ConfigManager',
    'DatabaseManager',
    'EnvironmentManager',
    'get_schema_version',
    'apply_migrations'
]
