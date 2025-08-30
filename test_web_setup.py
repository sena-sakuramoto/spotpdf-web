#!/usr/bin/env python3
"""
Test script to verify the web application setup
"""
import sys
import os
from pathlib import Path

def test_file_structure():
    """Test if all required files are present."""
    print("Testing file structure...")
    
    required_files = [
        'web_app.py',
        'run_web.py', 
        'pixel_diff_detector.py',
        'templates/base.html',
        'templates/login.html',
        'templates/index.html',
        'static/config.json',
        'requirements_web.txt',
        'Dockerfile',
        'docker-compose.yml',
        'README_WEB.md'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("[ERROR] Missing files:")
        for file in missing_files:
            print(f"  - {file}")
        return False
    else:
        print("[OK] All required files present")
        return True

def test_directories():
    """Test if required directories exist or can be created."""
    print("\nTesting directories...")
    
    required_dirs = [
        'templates',
        'static',
        'uploads',
        'static/outputs'
    ]
    
    for dir_path in required_dirs:
        path = Path(dir_path)
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"[OK] Created directory: {dir_path}")
            except Exception as e:
                print(f"[ERROR] Failed to create directory {dir_path}: {e}")
                return False
        else:
            print(f"[OK] Directory exists: {dir_path}")
    
    return True

def test_core_imports():
    """Test if core Python modules can be imported."""
    print("\nTesting core imports...")
    
    core_modules = [
        ('pixel_diff_detector', 'PixelDiffDetector'),
        ('pathlib', 'Path'),
        ('json', 'json'),
        ('tempfile', 'tempfile'),
        ('datetime', 'datetime'),
        ('logging', 'logging')
    ]
    
    for module_name, display_name in core_modules:
        try:
            __import__(module_name)
            print(f"[OK] {display_name} import OK")
        except ImportError as e:
            print(f"[ERROR] {display_name} import failed: {e}")
            return False
    
    return True

def test_config_file():
    """Test configuration file existence and format."""
    print("\nTesting configuration...")
    
    config_file = Path("GoogleLoginLauncher/SpotPDFLauncher.config.json")
    if not config_file.exists():
        print(f"[WARNING] Configuration file not found: {config_file}")
        print("   This is required for Google authentication.")
        return False
    
    try:
        import json
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        required_keys = ["GoogleClientId", "GoogleClientSecret", "ServiceAccountKeyPath", "SpreadsheetUrl"]
        missing_keys = [key for key in required_keys if not config.get(key)]
        
        if missing_keys:
            print(f"[ERROR] Configuration missing keys: {missing_keys}")
            return False
        else:
            print("[OK] Configuration file valid")
            return True
    except Exception as e:
        print(f"[ERROR] Configuration file error: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("  SpotPDF Web Application Setup Test")
    print("=" * 50)
    
    tests = [
        test_file_structure,
        test_directories,  
        test_core_imports,
        test_config_file
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "=" * 50)
    if all(results):
        print("[SUCCESS] All tests passed! Web application setup is ready.")
        print("\nNext steps:")
        print("1. Install web dependencies: pip install -r requirements_web.txt")
        print("2. Run the application: python run_web.py")
        print("3. Access http://localhost:5000 in your browser")
    else:
        print("[FAIL] Some tests failed. Please fix the issues above.")
        print("\nCommon solutions:")
        print("- Install missing packages: pip install -r requirements_web.txt")
        print("- Check configuration file path and content")
        print("- Ensure all template and static files are present")
    
    print("=" * 50)

if __name__ == '__main__':
    main()