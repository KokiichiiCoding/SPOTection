"""
Environment Manager
Handles virtual environment creation and dependency management
"""

import os
import sys
import subprocess
import platform
import shutil
from typing import Optional, Tuple


class EnvironmentManager:
    """Manages Python virtual environments and dependencies"""
    
    def __init__(self, venv_path: str = None):
        # Auto-detect venv path or use provided one
        if venv_path is None:
            # Check common venv names
            for name in ['.venv', 'venv', '.virtualenv', 'env']:
                if os.path.exists(name):
                    venv_path = name
                    break
            # If in an active venv, detect from sys.prefix
            if venv_path is None and hasattr(sys, 'prefix') and sys.prefix != sys.base_prefix:
                venv_path = sys.prefix
            # Default fallback
            if venv_path is None:
                venv_path = 'venv'
        
        self.venv_path = venv_path
        self.is_windows = platform.system() == "Windows"
    
    def get_python_command(self) -> str:
        """Get the appropriate Python command for this system"""
        return "python" if self.is_windows else "python3"
    
    def get_venv_python(self) -> str:
        """Get the Python executable path in the virtual environment"""
        # If already in a venv, return current Python
        if hasattr(sys, 'prefix') and sys.prefix != sys.base_prefix:
            return sys.executable
        
        # Otherwise, construct path to venv Python
        if self.is_windows:
            return os.path.join(self.venv_path, "Scripts", "python.exe")
        return os.path.join(self.venv_path, "bin", "python")
    
    def get_venv_pip(self) -> str:
        """Get the pip executable path in the virtual environment"""
        # If already in a venv, use pip from current environment
        if hasattr(sys, 'prefix') and sys.prefix != sys.base_prefix:
            if self.is_windows:
                return os.path.join(sys.prefix, "Scripts", "pip.exe")
            return os.path.join(sys.prefix, "bin", "pip")
        
        # Otherwise, construct path to venv pip
        if self.is_windows:
            return os.path.join(self.venv_path, "Scripts", "pip.exe")
        return os.path.join(self.venv_path, "bin", "pip")
    
    def check_python_version(self) -> Tuple[bool, str]:
        """Check if Python version is compatible"""
        version = sys.version_info
        version_str = f"{version.major}.{version.minor}.{version.micro}"
        
        if version.major < 3 or (version.major == 3 and version.minor < 8):
            return False, version_str
        
        return True, version_str
    
    def venv_exists(self) -> bool:
        """Check if virtual environment exists"""
        return os.path.exists(self.venv_path) and os.path.exists(self.get_venv_python())
    
    def create_venv(self, recreate: bool = False) -> Tuple[bool, Optional[str]]:
        """Create a virtual environment"""
        if self.venv_exists():
            if not recreate:
                return True, "Virtual environment already exists"
            
            # Remove existing venv
            try:
                shutil.rmtree(self.venv_path)
            except Exception as e:
                return False, f"Failed to remove existing venv: {e}"
        
        try:
            python_cmd = self.get_python_command()
            result = subprocess.run(
                [python_cmd, "-m", "venv", self.venv_path],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                return False, f"venv creation failed: {result.stderr}"
            
            return True, "Virtual environment created successfully"
        except subprocess.TimeoutExpired:
            return False, "venv creation timed out"
        except Exception as e:
            return False, str(e)
    
    def upgrade_pip(self) -> Tuple[bool, Optional[str]]:
        """Upgrade pip to the latest version"""
        try:
            pip_exe = self.get_venv_pip()
            result = subprocess.run(
                [pip_exe, "install", "--upgrade", "pip"],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                return False, f"pip upgrade failed: {result.stderr}"
            
            return True, "pip upgraded successfully"
        except Exception as e:
            return False, str(e)
    
    def install_requirements(self, requirements_file: str = "requirements.txt") -> Tuple[bool, Optional[str]]:
        """Install dependencies from requirements file"""
        if not os.path.exists(requirements_file):
            return False, f"{requirements_file} not found"
        
        try:
            pip_exe = self.get_venv_pip()
            result = subprocess.run(
                [pip_exe, "install", "-r", requirements_file],
                capture_output=True,
                text=True,
                timeout=600  # 10 minutes timeout for large installs
            )
            
            if result.returncode != 0:
                return False, f"Installation failed: {result.stderr}"
            
            return True, "All dependencies installed successfully"
        except subprocess.TimeoutExpired:
            return False, "Installation timed out (may be partially complete)"
        except Exception as e:
            return False, str(e)
    
    def install_package(self, package: str) -> Tuple[bool, Optional[str]]:
        """Install a single package"""
        try:
            pip_exe = self.get_venv_pip()
            result = subprocess.run(
                [pip_exe, "install", package],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                return False, f"Failed to install {package}: {result.stderr}"
            
            return True, f"{package} installed successfully"
        except Exception as e:
            return False, str(e)
    
    def get_installed_packages(self) -> list[str]:
        """Get list of installed packages"""
        try:
            pip_exe = self.get_venv_pip()
            result = subprocess.run(
                [pip_exe, "list", "--format=freeze"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return result.stdout.strip().split('\n')
            return []
        except Exception:
            return []
    
    def check_package_installed(self, package: str) -> bool:
        """Check if a specific package is installed"""
        try:
            python_exe = self.get_venv_python()
            result = subprocess.run(
                [python_exe, "-c", f"import {package}"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def create_directories(self, directories: list[str]) -> Tuple[bool, Optional[str]]:
        """Create required application directories"""
        try:
            for directory in directories:
                os.makedirs(directory, exist_ok=True)
            return True, f"Created {len(directories)} directories"
        except Exception as e:
            return False, str(e)
    
    def get_activation_command(self) -> str:
        """Get the command to activate the virtual environment"""
        if self.is_windows:
            return f"{self.venv_path}\\Scripts\\activate"
        return f"source {self.venv_path}/bin/activate"
