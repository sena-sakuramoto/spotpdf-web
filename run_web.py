#!/usr/bin/env python3
"""
SpotPDF Web Application Launcher
"""
import os
import sys
import logging
from pathlib import Path

def setup_environment():
    """Setup the application environment."""
    # Ensure required directories exist
    directories = [
        'uploads',
        'static/outputs',
        'templates',
        'static'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('web_app.log'),
            logging.StreamHandler()
        ]
    )

def check_dependencies():
    """Check if required dependencies are installed."""
    required_packages = [
        'flask',
        'werkzeug', 
        'fitz',  # PyMuPDF
        'PIL',   # Pillow
        'cv2',   # opencv-python
        'numpy',
        'gspread',
        'google.auth',
        'google_auth_oauthlib'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("Missing required packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nInstall them with: pip install -r requirements_web.txt")
        sys.exit(1)

def main():
    """Main function to run the web application."""
    print("=" * 50)
    print("  SpotPDF Web Application")
    print("=" * 50)
    
    setup_environment()
    check_dependencies()
    
    # Check configuration
    config_file = Path("GoogleLoginLauncher/SpotPDFLauncher.config.json")
    if not config_file.exists():
        print(f"Error: Configuration file not found: {config_file}")
        print("Please ensure the configuration file exists with Google OAuth settings.")
        sys.exit(1)
    
    # Import and run the web app
    try:
        from web_app import app
        
        print("Starting SpotPDF Web Application...")
        print("Access the application at: http://localhost:5000")
        print("Press Ctrl+C to stop the server")
        print("-" * 50)
        
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            threaded=True
        )
        
    except KeyboardInterrupt:
        print("\nShutting down SpotPDF Web Application...")
    except Exception as e:
        logging.error(f"Failed to start web application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()