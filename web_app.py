from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
import os
import tempfile
import shutil
from pathlib import Path
import json
from datetime import datetime
import logging
from pixel_diff_detector import PixelDiffDetector
import secrets
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import gspread
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'static/outputs'
ALLOWED_EXTENSIONS = {'pdf'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs('static', exist_ok=True)

# Load configuration
CONFIG_FILE = Path("GoogleLoginLauncher/SpotPDFLauncher.config.json")

def load_config():
    """Load configuration from JSON file."""
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # Also load client config for frontend
            with open('static/config.json', 'w', encoding='utf-8') as cf:
                json.dump({"GoogleClientId": config["GoogleClientId"]}, cf, indent=2)
            return config
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {CONFIG_FILE}")
        return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_authorized_users():
    """Get authorized users from Google Sheets."""
    config = load_config()
    if not config:
        return {}
    
    try:
        sa_creds = ServiceAccountCredentials.from_service_account_file(
            config["ServiceAccountKeyPath"],
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
        client = gspread.authorize(sa_creds)
        spreadsheet = client.open_by_url(config["SpreadsheetUrl"])
        worksheet = spreadsheet.sheet1
        records = worksheet.get_all_records()
        
        authorized_users = {}
        for record in records:
            email = record.get('email')
            exp_date_str = record.get('expiration_date')
            if email and exp_date_str:
                try:
                    exp_date = datetime.strptime(str(exp_date_str), "%Y-%m-%d").date()
                    authorized_users[email.lower()] = exp_date
                except ValueError:
                    logging.warning(f"Invalid date format for user {email}: {exp_date_str}")
        return authorized_users
    except Exception as e:
        logging.error(f"Error accessing spreadsheet: {e}")
        return {}

@app.route('/')
def index():
    if 'user_email' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', user_email=session['user_email'])

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/auth/google', methods=['POST'])
def google_auth():
    """Handle Google OAuth authentication."""
    config = load_config()
    if not config:
        return jsonify({'error': 'Configuration not found'}), 500
    
    token = request.json.get('credential')
    if not token:
        return jsonify({'error': 'No token provided'}), 400
    
    try:
        # Verify the token
        idinfo = id_token.verify_oauth2_token(
            token, google_requests.Request(), config["GoogleClientId"]
        )
        
        user_email = idinfo['email'].lower()
        
        # Check if user is authorized
        authorized_users = get_authorized_users()
        if user_email not in authorized_users:
            return jsonify({'error': 'Unauthorized user'}), 403
        
        # Check if authorization is still valid
        exp_date = authorized_users[user_email]
        if datetime.now().date() > exp_date:
            return jsonify({'error': 'Authorization expired'}), 403
        
        # Store user info in session
        session['user_email'] = user_email
        session['user_name'] = idinfo.get('name', user_email)
        
        return jsonify({'success': True, 'redirect': url_for('index')})
        
    except ValueError as e:
        return jsonify({'error': f'Invalid token: {e}'}), 400
    except Exception as e:
        logging.error(f"Authentication error: {e}")
        return jsonify({'error': 'Authentication failed'}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle PDF file uploads."""
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if 'old_pdf' not in request.files or 'new_pdf' not in request.files:
        return jsonify({'error': 'Both old and new PDF files are required'}), 400
    
    old_file = request.files['old_pdf']
    new_file = request.files['new_pdf']
    
    if old_file.filename == '' or new_file.filename == '':
        return jsonify({'error': 'No files selected'}), 400
    
    if not (allowed_file(old_file.filename) and allowed_file(new_file.filename)):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    # Create temporary directory for this comparison
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Save uploaded files
        old_filename = secure_filename(old_file.filename)
        new_filename = secure_filename(new_file.filename)
        
        old_path = os.path.join(temp_dir, old_filename)
        new_path = os.path.join(temp_dir, new_filename)
        
        old_file.save(old_path)
        new_file.save(new_path)
        
        # Get settings from request
        settings = {
            'sensitivity': int(request.form.get('sensitivity', 10)),
            'display_filter': {
                'added': request.form.get('show_added', 'true') == 'true',
                'removed': request.form.get('show_removed', 'true') == 'true'
            },
            'export_all_patterns': request.form.get('export_all', 'false') == 'true'
        }
        
        # Process PDF comparison
        detector = PixelDiffDetector()
        
        # Create output directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{Path(old_filename).stem}_vs_{Path(new_filename).stem}_{timestamp}"
        output_path = os.path.join(OUTPUT_FOLDER, output_name)
        
        results = detector.create_pixel_diff_output(
            old_path, new_path, output_path, settings=settings
        )
        
        # Copy results to static folder for web access
        if os.path.exists(results['output_path']):
            web_output_path = f"outputs/{output_name}"
            return jsonify({
                'success': True,
                'output_path': web_output_path,
                'results': results
            })
        else:
            return jsonify({'error': 'Failed to generate comparison'}), 500
    
    except Exception as e:
        logging.error(f"Upload processing error: {e}")
        return jsonify({'error': f'Processing failed: {str(e)}'}), 500
    
    finally:
        # Cleanup temporary files
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

@app.route('/download/<path:filename>')
def download_file(filename):
    """Download generated files."""
    if 'user_email' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/status')
def status():
    """Check authentication status."""
    return jsonify({
        'authenticated': 'user_email' in session,
        'user': session.get('user_name', '')
    })

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, host='0.0.0.0', port=5000)