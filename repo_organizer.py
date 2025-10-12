#!/usr/bin/env python3
"""
Spotection Repository Organizer
Clean up and restructure the project for alpha release
"""

import os
import shutil
import json
from pathlib import Path


class RepoOrganizer:
    """Organize and clean up Spotection repository"""
    
    def __init__(self, project_root="."):
        self.root = Path(project_root)
        self.backup_dir = self.root / "backup_before_cleanup"
        
    def backup_repo(self):
        """Create backup of important files before cleanup"""
        print("Creating backup...")
        
        important_files = [
            "config.json",
            "data/spot_layout.json",
            "data/test_image.jpg",
        ]
        
        self.backup_dir.mkdir(exist_ok=True)
        
        for file_path in important_files:
            src = self.root / file_path
            if src.exists():
                dst = self.backup_dir / file_path
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                print(f"  ✓ Backed up: {file_path}")
    
    def remove_unnecessary_folders(self):
        """Remove folders that aren't needed"""
        print("\nRemoving unnecessary folders...")
        
        to_remove = [
            "templates",  # Not needed
            "notebooks",  # Development files
            "yolox_inference",  # Old model files
        ]
        
        for folder in to_remove:
            folder_path = self.root / folder
            if folder_path.exists():
                shutil.rmtree(folder_path)
                print(f"  ✓ Removed: {folder}")
    
    def create_proper_structure(self):
        """Create organized directory structure"""
        print("\nCreating proper structure...")
        
        structure = {
            "src": "Main source code",
            "src/core": "Core detection logic",
            "src/api": "Web API code",
            "src/utils": "Utility functions",
            "src/models": "Model wrappers",
            "config": "Configuration files",
            "data": "Data directory",
            "data/images": "Input images",
            "data/layouts": "Spot layout JSONs",
            "data/ground_truth": "Ground truth annotations",
            "static": "Static web files",
            "static/css": "Stylesheets",
            "static/js": "JavaScript files",
            "static/images": "Web images/icons",
            "output": "Detection output",
            "logs": "Log files",
            "tests": "Test files",
            "scripts": "Utility scripts",
            "docs": "Documentation",
        }
        
        for directory, description in structure.items():
            dir_path = self.root / directory
            dir_path.mkdir(parents=True, exist_ok=True)
            
            # Create README in each main directory
            if "/" not in directory:
                readme = dir_path / "README.md"
                if not readme.exists():
                    with open(readme, 'w') as f:
                        f.write(f"# {directory.title()}\n\n{description}\n")
        
        print("  ✓ Directory structure created")
    
    def organize_python_files(self):
        """Move Python files to appropriate locations"""
        print("\nOrganizing Python files...")
        
        # Core detection files
        core_files = {
            "enhanced_spotection.py": "src/core/detection_system.py",
            "spotection_system.py": "src/core/legacy_detection.py",
            "auto_polygon_gen.py": "src/core/polygon_generator.py",
            "complete_calibration_tool.py": "src/core/calibration_tool.py",
        }
        
        # API files
        api_files = {
            "webapp/spotection_web_api.py": "src/api/main.py",
        }
        
        # Utility files
        util_files = {
            "performance_monitor.py": "src/utils/performance.py",
            "cnrpark_loader.py": "src/utils/dataset_loader.py",
        }
        
        # Scripts
        script_files = {
            "alpha_deploy.py": "scripts/deploy.py",
            "setup_spotection.py": "scripts/setup.py",
            "test_suite.py": "tests/test_all.py",
        }
        
        all_moves = {**core_files, **api_files, **util_files, **script_files}
        
        for src_name, dst_name in all_moves.items():
            src = self.root / src_name
            dst = self.root / dst_name
            
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
                print(f"  ✓ Moved: {src_name} → {dst_name}")
    
    def organize_data_files(self):
        """Organize data directory"""
        print("\nOrganizing data files...")
        
        # Move test images
        test_image = self.root / "data" / "test_image.jpg"
        if test_image.exists():
            new_path = self.root / "data" / "images" / "test_image.jpg"
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(test_image), str(new_path))
            print(f"  ✓ Moved test image to data/images/")
        
        # Move spot layouts
        spot_layout = self.root / "data" / "spot_layout.json"
        if spot_layout.exists():
            new_path = self.root / "data" / "layouts" / "default_layout.json"
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(spot_layout), str(new_path))
            print(f"  ✓ Moved spot layout to data/layouts/")
    
    def consolidate_requirements(self):
        """Consolidate and clean up requirements files"""
        print("\nConsolidating requirements...")
        
        # Remove duplicate requirements files
        duplicates = [
            "updated_requirements.txt",
            "updated_requirements (1).txt",
        ]
        
        for dup in duplicates:
            dup_path = self.root / dup
            if dup_path.exists():
                dup_path.unlink()
                print(f"  ✓ Removed duplicate: {dup}")
        
        # Ensure we have clean requirements.txt
        print("  ✓ Kept clean requirements.txt")
    
    def update_config_paths(self):
        """Update config.json with new paths"""
        print("\nUpdating configuration...")
        
        config_path = self.root / "config.json"
        
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Update paths
            config.update({
                "image_path": "data/images/test_image.jpg",
                "spot_layout_path": "data/layouts/default_layout.json",
                "output_dir": "output/",
                "log_dir": "logs/",
            })
            
            # Move to config directory
            new_config_path = self.root / "config" / "config.json"
            new_config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(new_config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Keep a copy in root for convenience
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            print("  ✓ Updated config with new paths")
    
    def create_package_structure(self):
        """Create proper Python package structure"""
        print("\nCreating package structure...")
        
        # Create __init__.py files
        package_dirs = [
            "src",
            "src/core",
            "src/api",
            "src/utils",
            "src/models",
        ]
        
        for pkg_dir in package_dirs:
            init_file = self.root / pkg_dir / "__init__.py"
            if not init_file.exists():
                with open(init_file, 'w') as f:
                    f.write(f'"""Spotection - {pkg_dir.split("/")[-1].title()} Package"""\n\n')
                    f.write(f'__version__ = "1.0.0-alpha"\n')
                print(f"  ✓ Created {init_file}")
    
    def create_gitignore(self):
        """Create comprehensive .gitignore"""
        print("\nCreating .gitignore...")
        
        gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/
*.egg-info/
dist/
build/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# Project specific
output/
logs/*.log
*.pt
*.pth
cnrpark_data/
data/images/*.jpg
data/images/*.png
!data/images/sample.jpg
backup_before_cleanup/

# OS
.DS_Store
Thumbs.db

# Temp files
*.tmp
*.temp
"""
        
        gitignore_path = self.root / ".gitignore"
        with open(gitignore_path, 'w') as f:
            f.write(gitignore_content)
        
        print("  ✓ Created .gitignore")
    
    def create_main_entry_point(self):
        """Create main.py entry point"""
        print("\nCreating main entry point...")
        
        main_content = """#!/usr/bin/env python3
\"\"\"
Spotection - Main Entry Point
Alpha v1.0
\"\"\"

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.detection_system import EnhancedSpotectionSystem
from api.main import start_server
from utils.performance import PerformanceMonitor


def main():
    parser = argparse.ArgumentParser(
        description="Spotection - AI Parking Detection System"
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Detect command
    detect_parser = subparsers.add_parser('detect', help='Run detection')
    detect_parser.add_argument('--image', help='Image path')
    detect_parser.add_argument('--config', default='config/config.json')
    
    # Serve command
    serve_parser = subparsers.add_parser('serve', help='Start web server')
    serve_parser.add_argument('--host', default='0.0.0.0')
    serve_parser.add_argument('--port', type=int, default=8000)
    
    # Calibrate command
    calibrate_parser = subparsers.add_parser('calibrate', help='Run calibration')
    calibrate_parser.add_argument('--image', required=True)
    
    args = parser.parse_args()
    
    if args.command == 'detect':
        system = EnhancedSpotectionSystem(args.config)
        results = system.run_detection(image_path=args.image)
        
        if results:
            print(f"\\n✓ Detection Complete")
            print(f"Free: {results['free_spots']}/{results['total_spots']}")
    
    elif args.command == 'serve':
        print(f"Starting server on {args.host}:{args.port}")
        start_server(host=args.host, port=args.port)
    
    elif args.command == 'calibrate':
        from core.calibration_tool import complete_lot_calibration
        complete_lot_calibration()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
"""
        
        main_path = self.root / "main.py"
        with open(main_path, 'w') as f:
            f.write(main_content)
        
        # Make executable
        try:
            os.chmod(main_path, 0o755)
        except:
            pass
        
        print("  ✓ Created main.py")
    
    def cleanup_old_files(self):
        """Remove old/redundant files"""
        print("\nCleaning up old files...")
        
        to_remove = [
            "Conditional_Generation.ipynb",
            "debug_aggressive_detection.jpg",
            "yolov8n.pt",  # Will be downloaded by setup
        ]
        
        for file in to_remove:
            file_path = self.root / file
            if file_path.exists():
                if file_path.is_file():
                    file_path.unlink()
                    print(f"  ✓ Removed: {file}")
    
    def create_readme_sections(self):
        """Create additional README files"""
        print("\nCreating documentation...")
        
        # API README
        api_readme = self.root / "src" / "api" / "README.md"
        with open(api_readme, 'w') as f:
            f.write("""# Spotection API

FastAPI-based REST API for parking detection.

## Running

```bash
python main.py serve
```

## Endpoints

- `GET /api/lots/{lot_id}/status` - Get parking status
- `GET /api/lots/{lot_id}/image` - Get annotated image
- `WS /ws` - WebSocket for live updates

See `/docs` for interactive API documentation.
""")
        
        print("  ✓ Created API documentation")
    
    def reorganize(self):
        """Run complete reorganization"""
        print("="*60)
        print("SPOTECTION REPOSITORY REORGANIZATION")
        print("="*60)
        
        steps = [
            ("Backing up important files", self.backup_repo),
            ("Removing unnecessary folders", self.remove_unnecessary_folders),
            ("Creating proper structure", self.create_proper_structure),
            ("Organizing Python files", self.organize_python_files),
            ("Organizing data files", self.organize_data_files),
            ("Consolidating requirements", self.consolidate_requirements),
            ("Updating configuration", self.update_config_paths),
            ("Creating package structure", self.create_package_structure),
            ("Creating .gitignore", self.create_gitignore),
            ("Creating main entry point", self.create_main_entry_point),
            ("Cleaning up old files", self.cleanup_old_files),
            ("Creating documentation", self.create_readme_sections),
        ]
        
        for step_name, step_func in steps:
            try:
                step_func()
            except Exception as e:
                print(f"  ✗ Error in {step_name}: {e}")
        
        print("\n" + "="*60)
        print("REORGANIZATION COMPLETE!")
        print("="*60)
        print("\nNew structure:")
        print("""
spotection/
├── main.py              # Main entry point
├── config/
│   └── config.json      # Configuration
├── src/
│   ├── core/           # Detection logic
│   ├── api/            # Web API
│   ├── utils/          # Utilities
│   └── models/         # Model wrappers
├── data/
│   ├── images/         # Input images
│   ├── layouts/        # Spot layouts
│   └── ground_truth/   # Annotations
├── static/             # Web files
├── scripts/            # Utility scripts
├── tests/              # Tests
└── docs/               # Documentation
        """)
        
        print("\nQuick commands:")
        print("  python main.py detect         # Run detection")
        print("  python main.py serve          # Start web server")
        print("  python main.py calibrate      # Run calibration")
        print("\nBackup created in: backup_before_cleanup/")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Reorganize Spotection repository")
    parser.add_argument("--dry-run", action="store_true", 
                       help="Show what would be done without making changes")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("DRY RUN - No changes will be made")
        print("\nThis would:")
        print("- Remove templates/, notebooks/, yolox_inference/")
        print("- Organize files into src/core/, src/api/, src/utils/")
        print("- Create proper package structure")
        print("- Update all import paths")
        print("- Create main.py entry point")
        return
    
    organizer = RepoOrganizer()
    organizer.reorganize()


if __name__ == "__main__":
    main()
