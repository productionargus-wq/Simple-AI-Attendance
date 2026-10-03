import os
import time
import re
import io
import csv
import gzip
import secrets
import base64
import threading
import urllib.parse
import requests
import werkzeug.utils
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageOps

load_dotenv()

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, send_from_directory, Response, session, make_response, flash
from functools import wraps
from flask_cors import CORS
import database

GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '').strip()
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip()

try:
    import pdf_generator
except Exception as e:
    pdf_generator = None
    print(f"Warning: pdf_generator import failed: {e}")

# Lazy import face_engine to avoid numpy/opencv crash on serverless
face_engine = None
def get_face_engine():
    global face_engine
    if face_engine is None:
        try:
            import face_engine as _fe
            face_engine = _fe
        except Exception as e:
            print(f"Warning: face_engine import failed: {e}")
    return face_engine

app = Flask(__name__)
CORS(app)
app.secret_key = 'argus-tech-secret-key-2026'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', os.path.join(BASE_DIR, 'static', 'uploads'))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 43200  # 12 hours static caching
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create upload directory: {e}")

def process_uploaded_photo(file_bytes, original_filename='photo.jpg'):
    """
    Optimizes and prepares photo for dual-storage (disk + permanent MongoDB Atlas base64):
    1. Auto-orients portrait/landscape via EXIF metadata.
    2. Resizes to max 600x600 px using high-quality LANCZOS resampling.
    3. Converts to standard RGB JPEG (~30-50 KB).
    4. Generates base64 data URI for 100% persistent MongoDB storage (never lost on refresh/redeploy).
    5. Saves optimized copy to UPLOAD_FOLDER on disk.
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img = ImageOps.exif_transpose(img)
        if img.mode in ('RGBA', 'P', 'LA'):
            img = img.convert('RGB')
        img.thumbnail((600, 600), Image.Resampling.LANCZOS)
        out_buf = io.BytesIO()
        img.save(out_buf, format='JPEG', quality=85, optimize=True)
        optimized_bytes = out_buf.getvalue()
    except Exception as e:
        print(f"Warning: PIL photo optimization failed, using raw bytes: {e}")
        optimized_bytes = file_bytes

    b64_str = base64.b64encode(optimized_bytes).decode('utf-8')
    photo_data_url = f"data:image/jpeg;base64,{b64_str}"

    clean_name = werkzeug.utils.secure_filename(original_filename) or 'face_capture.jpg'
    if not clean_name.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
        clean_name += '.jpg'
    unique_filename = f"{int(database.time.time())}_{clean_name}"

    try:
        upload_dir = app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, unique_filename)
        with open(file_path, 'wb') as f:
            f.write(optimized_bytes)
    except Exception as io_err:
        print(f"Warning: could not write photo to disk: {io_err}")

    return unique_filename, photo_data_url, optimized_bytes

def _background_startup():
    try:
        fe = get_face_engine()
        if fe:
            fe.ensure_models_available()
            fe.auto_sync_stored_employee_embeddings()
    except Exception as e:
        print(f"Warning: background face sync error: {e}")

try:
    database.init_db()
    threading.Thread(target=_background_startup, daemon=True, name="FaceSyncStartup").start()
    import report_scheduler
    report_scheduler.start_scheduler()
except Exception as e:
    print(f"Warning: database/face/scheduler init error: {e}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------- MULTI-TENANT RBAC HELPERS & DECORATORS ----------------- #

def get_current_company_id():
    """Returns the company_id associated with the currently logged-in user."""
    role = session.get('role')
    comp_id = session.get('company_id')
    if role == 'super_admin':
        return comp_id or 'ARGUS_MASTER'
    return comp_id or 'ARGUS_MASTER'

def get_current_company_info():
    """Returns dynamic company dictionary for PDF generation and headers."""
    comp_id = get_current_company_id()
    if comp_id and comp_id != 'ARGUS_MASTER':
        comp = database.get_company_by_id(comp_id)
        if comp:
            addr = comp.get('address') or comp.get('location') or ''
            if not addr and comp.get('latitude') and comp.get('longitude'):
                addr = f"Location: Lat {comp.get('latitude')}, Lng {comp.get('longitude')}"
            return {
                'id': comp.get('id', comp_id),
                'company_name': comp.get('company_name') or session.get('company_name', 'ARGUS TECHNOLOGIES'),
                'company_address': addr,
                'email': comp.get('email', ''),
                'phone': comp.get('phone', ''),
                'gstin': comp.get('gstin', '')
            }
    # Master / Default ARGUS info
    master_comp = database.get_company_by_id('ARGUS_MASTER')
    if master_comp:
        return {
            'id': 'ARGUS_MASTER',
            'company_name': master_comp.get('company_name', 'ARGUS TECHNOLOGIES'),
            'company_address': master_comp.get('address', 'SF NO. 515, Bharathiyar Road, Maniyakaranpalayam, Ganapathy (PO), Coimbatore - 641 006'),
            'email': master_comp.get('email', 'technologiesargus@gmail.com'),
            'phone': master_comp.get('phone', '+91 98765 43210'),
            'gstin': master_comp.get('gstin', '33AABCA0000A1Z5')
        }
    return {
        'id': 'ARGUS_MASTER',
        'company_name': 'ARGUS TECHNOLOGIES',
        'company_address': 'SF NO. 515, Bharathiyar Road, Maniyakaranpalayam, Ganapathy (PO), Coimbatore - 641 006',
        'email': 'technologiesargus@gmail.com',
        'phone': '+91 98765 43210',
        'gstin': '33AABCA0000A1Z5'
    }

def login_required(f):
    """Requires Super Admin or Company Admin session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in') or session.get('role') not in ['super_admin', 'company_admin']:
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Authentication required. Your session may have expired. Please refresh and log in again.'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    """Requires Super Admin session (Platform Owner)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Super Admin privileges required.'}), 403
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def employee_required(f):
    """Requires Employee self-service session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('employee_logged_in') or session.get('role') != 'employee':
            if request.path.startswith('/api/'):
                return jsonify({'error': 'Employee authentication required.'}), 401
            return redirect(url_for('employee_login'))
        return f(*args, **kwargs)
    return decorated_function

def check_user_can_delete_entries():
    """Checks whether the currently logged-in user can delete attendance/report entries."""
    if not session.get('admin_logged_in'):
        return False
    if session.get('role') == 'super_admin':
        return True
    if session.get('role') == 'company_admin':
        comp_id = session.get('company_id')
        if comp_id and database.can_company_delete_entries(comp_id):
            return True
    return False

@app.context_processor
def inject_delete_permissions():
    """Injects delete permissions and system admin status into all templates dynamically."""
    is_super = session.get('role') == 'super_admin'
    comp_can_del = False
    if is_super:
        comp_can_del = True
    elif session.get('role') == 'company_admin':
        comp_id = session.get('company_id')
        if comp_id:
            comp_can_del = database.can_company_delete_entries(comp_id)
    return {
        'is_system_admin': is_super,
        'can_delete_entries': comp_can_del
    }

import traceback
from werkzeug.exceptions import HTTPException

DEFAULT_AVATAR_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120" width="120" height="120">
  <rect width="120" height="120" fill="#e2e8f0" rx="8"/>
  <circle cx="60" cy="46" r="22" fill="#94a3b8"/>
  <path d="M26 104c0-18.8 15.2-34 34-34s34 15.2 34 34" fill="#94a3b8"/>
</svg>'''

@app.route('/favicon.ico')
def favicon():
    icon_dir = os.path.join(app.root_path, 'static', 'images')
    if os.path.exists(os.path.join(icon_dir, 'argus_triangle_logo.png')):
        return send_from_directory(icon_dir, 'argus_triangle_logo.png', mimetype='image/png')
    elif os.path.exists(os.path.join(icon_dir, 'logo.png')):
        return send_from_directory(icon_dir, 'logo.png', mimetype='image/png')
    return Response(status=204)

@app.errorhandler(500)
def handle_500(e):
    err = traceback.format_exc()
    print("500 Internal Error:", err)
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500
    return f"<h1>Internal Server Error (500)</h1><pre>{err}</pre>", 500

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        if request.path.startswith('/api/'):
            return jsonify({'error': e.description}), e.code
        return e
    err = traceback.format_exc()
    print("Unhandled Exception:", err)
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Server error', 'details': str(e)}), 500
    return f"<h1>Server Error</h1><pre>{err}</pre>", 500

@app.after_request
def add_performance_headers(response):
    if request.path.startswith('/static/'):
        if request.args.get('v'):
            response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        else:
            response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    elif response.status_code == 200 and request.method == 'GET' and not request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'

    accept_encoding = request.headers.get('Accept-Encoding', '')
    if (
        'gzip' in accept_encoding.lower()
        and response.status_code == 200
        and not response.direct_passthrough
        and response.mimetype in ['text/html', 'text/css', 'application/javascript', 'application/json', 'image/svg+xml']
    ):
        try:
            data = response.get_data()
            if len(data) > 1024:
                gzip_buffer = io.BytesIO()
                with gzip.GzipFile(mode='wb', fileobj=gzip_buffer, compresslevel=6) as gz:
                    gz.write(data)
                response.set_data(gzip_buffer.getvalue())
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Content-Length'] = len(response.get_data())
                response.headers['Vary'] = 'Accept-Encoding'
        except Exception:
            pass
    return response

# ----------------- AUTHENTICATION & PAGE ROUTES ----------------- #

@app.route('/')
def index():
    return render_template('attendance.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Super Admin Login (Registered Email: technologiesargus@gmail.com)."""
    if request.method == 'POST':
        email = (request.form.get('email') or request.form.get('username') or '').strip()
        password = request.form.get('password', '').strip()
        if not email:
            return render_template('login.html', error='Please enter your authorized email address.')
        if not password:
            return render_template(
                'login.html',
                error='Password is required for manual sign-in. First time signing in? Please use Continue with Google below.'
            )
        
        result = database.validate_admin_login(email, password=password)
        if isinstance(result, dict) and result.get('success'):
            admin_user = result['admin']
            session.clear()
            session['admin_logged_in'] = True
            session['admin_username'] = admin_user.get('username', 'Admin')
            session['admin_email'] = admin_user.get('email', 'technologiesargus@gmail.com')
            session['role'] = 'super_admin'
            session['company_id'] = 'ARGUS_MASTER'
            session['company_name'] = 'ARGUS TECHNOLOGIES'
            return redirect(url_for('dashboard'))
        else:
            err_code = result.get('error') if isinstance(result, dict) else None
            if err_code == 'PASSWORD_NOT_SET':
                error_msg = "Password has not been set yet. First-time access? Please click 'Continue with Google' below to verify your account and set your password."
            elif err_code == 'NOT_REGISTERED':
                error_msg = 'Access Denied: Email is not authorized as System Admin. Please verify with Google below.'
            else:
                error_msg = 'Invalid password. Please verify your password or sign in with Google.'
            return render_template('login.html', error=error_msg)
    return render_template('login.html')

@app.route('/auth/google/login')
def google_login():
    """Initiates Google OAuth 2.0 Authorization Flow."""
    login_type = request.args.get('type', 'admin').strip().lower()
    if login_type not in ['admin', 'company', 'employee']:
        login_type = 'admin'

    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_login_type'] = login_type

    redirect_uri = url_for('google_callback', _external=True)
    if request.headers.get('X-Forwarded-Proto') == 'https' and redirect_uri.startswith('http://'):
        redirect_uri = redirect_uri.replace('http://', 'https://', 1)

    session['oauth_redirect_uri'] = redirect_uri

    params = {
        'client_id': GOOGLE_CLIENT_ID,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account'
    }
    auth_url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)
    return redirect(auth_url)

@app.route('/auth/google/callback')
def google_callback():
    """Handles Google OAuth 2.0 Callback and role-based authorization."""
    error = request.args.get('error')
    login_type = session.get('oauth_login_type', 'admin')

    def render_oauth_error(msg):
        if login_type == 'company':
            return render_template('company_login.html', error=msg)
        elif login_type == 'employee':
            return render_template('employee_login.html', error=msg)
        else:
            return render_template('login.html', error=msg)

    if error:
        return render_oauth_error(f"Google sign-in was cancelled or failed ({error}).")

    code = request.args.get('code')
    state = request.args.get('state')
    expected_state = session.get('oauth_state')

    if not code or not state or state != expected_state:
        return render_oauth_error("Invalid or expired OAuth state. Please try logging in again.")

    redirect_uri = session.get('oauth_redirect_uri') or url_for('google_callback', _external=True)
    if request.headers.get('X-Forwarded-Proto') == 'https' and redirect_uri.startswith('http://'):
        redirect_uri = redirect_uri.replace('http://', 'https://', 1)

    token_url = 'https://oauth2.googleapis.com/token'
    token_payload = {
        'code': code,
        'client_id': GOOGLE_CLIENT_ID,
        'client_secret': GOOGLE_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }

    try:
        token_resp = requests.post(token_url, data=token_payload, timeout=12)
        token_data = token_resp.json()
        if 'error' in token_data:
            err_desc = token_data.get('error_description') or token_data.get('error')
            return render_oauth_error(f"Google authorization error: {err_desc}")

        access_token = token_data.get('access_token')
        userinfo_resp = requests.get(
            'https://www.googleapis.com/oauth2/v3/userinfo',
            headers={'Authorization': f"Bearer {access_token}"},
            timeout=12
        )
        user_info = userinfo_resp.json()
        google_email = (user_info.get('email') or '').strip().lower()
        if not google_email:
            return render_oauth_error("Unable to obtain verified email address from Google.")
    except Exception as exc:
        return render_oauth_error(f"Communication error with Google services: {str(exc)}")

    # Clear OAuth temporary session tokens
    session.pop('oauth_state', None)
    session.pop('oauth_redirect_uri', None)
    session.pop('oauth_login_type', None)

    # Authorized Role Verification
    if login_type == 'admin':
        admin_user = database.validate_admin_login(google_email)
        if admin_user:
            session.clear()
            session['admin_logged_in'] = True
            session['admin_username'] = admin_user.get('username', 'Admin')
            session['admin_email'] = admin_user.get('email', 'technologiesargus@gmail.com')
            session['role'] = 'super_admin'
            session['company_id'] = 'ARGUS_MASTER'
            session['company_name'] = 'ARGUS TECHNOLOGIES'
            return redirect(url_for('dashboard'))
        else:
            return render_oauth_error(
                f"Access Denied: The Google account '{google_email}' is not authorized as System Admin."
            )

    elif login_type == 'company':
        company = database.validate_company_login(google_email)
        if company:
            session.clear()
            session['admin_logged_in'] = True
            session['admin_username'] = company.get('company_name', 'Company Admin')
            session['role'] = 'company_admin'
            session['company_id'] = company['id']
            session['company_name'] = company.get('company_name', '')
            session['company_email'] = company.get('email', '')
            return redirect(url_for('dashboard'))
        else:
            return render_oauth_error(
                f"Access Denied: The Google account '{google_email}' is not registered as a company administrator. Please contact Argus Support."
            )

    elif login_type == 'employee':
        employee = database.validate_employee_login(google_email)
        if employee:
            session.clear()
            session['employee_logged_in'] = True
            session['role'] = 'employee'
            session['employee_id'] = str(employee.get('id', employee.get('_id', '')))
            session['employee_name'] = employee.get('employee_name', '')
            session['employee_email'] = employee.get('email_id', '')
            comp_id = employee.get('company_id', 'ARGUS_MASTER')
            session['company_id'] = comp_id
            comp_record = database.get_company_by_id(comp_id) if comp_id != 'ARGUS_MASTER' else None
            session['company_name'] = comp_record.get('company_name', 'ARGUS TECHNOLOGIES') if comp_record else 'ARGUS TECHNOLOGIES'
            return redirect(url_for('employee_portal'))
        else:
            return render_oauth_error(
                f"Access Denied: The Google account '{google_email}' is not registered with any organisation. Please contact your company HR."
            )

    return redirect(url_for('login'))

@app.route('/company-login', methods=['GET', 'POST'])
def company_login():
    """Dedicated Company Admin Portal Login via Registered Corporate Email."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        if not email:
            return render_template('company_login.html', error='Please enter your registered corporate email.')
        if not password:
            return render_template(
                'company_login.html',
                error='Password is required for manual sign-in. First time signing in? Please use Continue with Google below.'
            )

        result = database.validate_company_login(email, password=password)
        if isinstance(result, dict) and result.get('success'):
            company = result['company']
            session.clear()
            session['admin_logged_in'] = True
            session['admin_username'] = company.get('company_name', 'Company Admin')
            session['role'] = 'company_admin'
            session['company_id'] = company['id']
            session['company_name'] = company.get('company_name', '')
            session['company_email'] = company.get('email', '')
            return redirect(url_for('dashboard'))
        else:
            err_code = result.get('error') if isinstance(result, dict) else None
            if err_code == 'PASSWORD_NOT_SET':
                error_msg = "Password has not been set yet. First-time access? Please click 'Continue with Google' below to verify your account and set your password in Company Profile."
            elif err_code == 'NOT_REGISTERED':
                error_msg = 'Access Denied: This email is not registered as a company administrator. Please contact Argus Support.'
            else:
                error_msg = 'Invalid password. Please check your credentials or continue with Google.'
            return render_template('company_login.html', error=error_msg)
    return render_template('company_login.html')

@app.route('/employee-login', methods=['GET', 'POST'])
def employee_login():
    """Dedicated Employee Portal Login via Registered Employee Email."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        if not email:
            return render_template('employee_login.html', error='Please enter your registered employee email.')
        if not password:
            return render_template(
                'employee_login.html',
                error='Password is required for manual sign-in. First time signing in? Please use Continue with Google below.'
            )

        result = database.validate_employee_login(email, password=password)
        if isinstance(result, dict) and result.get('success'):
            employee = result['employee']
            session.clear()
            session['employee_logged_in'] = True
            session['role'] = 'employee'
            session['employee_id'] = str(employee.get('id', employee.get('_id', '')))
            session['employee_name'] = employee.get('employee_name', '')
            session['employee_email'] = employee.get('email_id', '')
            comp_id = employee.get('company_id', 'ARGUS_MASTER')
            session['company_id'] = comp_id
            comp_record = database.get_company_by_id(comp_id) if comp_id != 'ARGUS_MASTER' else None
            session['company_name'] = comp_record.get('company_name', 'ARGUS TECHNOLOGIES') if comp_record else 'ARGUS TECHNOLOGIES'
            return redirect(url_for('employee_portal'))
        else:
            err_code = result.get('error') if isinstance(result, dict) else None
            if err_code == 'PASSWORD_NOT_SET':
                error_msg = "Password has not been set yet. First-time access? Please click 'Continue with Google' below to verify your account and set your password in My Credentials."
            elif err_code == 'NOT_REGISTERED':
                error_msg = 'Access Denied: Email not registered with any organisation. Please contact your company HR.'
            else:
                error_msg = 'Invalid password. Please check your credentials or continue with Google.'
            return render_template('employee_login.html', error=error_msg)
    return render_template('employee_login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/manage-companies')
@super_admin_required
def manage_companies():
    return render_template('manage_companies.html', active_tab='MANAGE COMPANIES')

@app.route('/company-profile')
@login_required
def company_profile():
    role = session.get('role', 'company_admin')
    return render_template('company_profile.html', active_tab='COMPANY PROFILE', role=role)

@app.route('/leave-permission')
@login_required
def leave_permission():
    comp_id = get_current_company_id()
    policy = database.get_company_leave_policy(comp_id)
    stats = database.get_admin_leave_stats(company_id=comp_id)
    companies = []
    if session.get('role') == 'super_admin':
        companies = database.get_all_companies()
    return render_template('leave_permission.html', active_tab='LEAVE & PERMISSION', policy=policy, stats=stats, companies=companies)

@app.route('/leave-permission/review/<request_id>')
@login_required
def leave_permission_review(request_id):
    req = database.get_leave_request_by_id(request_id)
    if not req:
        flash('Leave request not found', 'danger')
        return redirect(url_for('leave_permission'))
    emp_id = req.get('employee_id')
    comp_id = req.get('company_id')
    emp = database.get_employee_by_id(emp_id)
    bal = database.get_employee_leave_balance(emp_id, company_id=comp_id)
    return render_template('leave_review.html', active_tab='LEAVE & PERMISSION', req=req, employee=emp or {}, balance=bal or {})

@app.route('/employee/portal')
@employee_required
def employee_portal():
    emp_id = session.get('employee_id')
    comp_id = session.get('company_id')
    employee = database.get_employee_by_id(emp_id)
    company = database.get_company_by_id(comp_id) if comp_id != 'ARGUS_MASTER' else {'company_name': 'Argus Technologies'}
    if company and company.get('company_name'):
        session['company_name'] = company['company_name']
    return render_template('employee_portal.html', employee=employee, company=company)

@app.route('/dashboard')
@login_required
def dashboard():
    comp_id = get_current_company_id()
    if comp_id and comp_id != 'ARGUS_MASTER':
        comp = database.get_company_by_id(comp_id)
        if comp and comp.get('company_name'):
            session['company_name'] = comp['company_name']
    stats = database.get_dashboard_stats(company_id=comp_id)

    try:
        from report_scheduler import get_yesterday_ist, get_previous_month_ist
        yesterday_str = get_yesterday_ist()
        prev_month_str = get_previous_month_ist()

        try:
            y_dt = datetime.strptime(yesterday_str, '%Y-%m-%d')
            yesterday_display = y_dt.strftime('%d %b %Y')
        except Exception:
            yesterday_display = yesterday_str

        try:
            m_dt = datetime.strptime(prev_month_str, '%Y-%m')
            prev_month_display = m_dt.strftime('%B %Y')
        except Exception:
            prev_month_display = prev_month_str

        stats['yesterday_date'] = yesterday_str
        stats['yesterday_display'] = yesterday_display
        stats['previous_month'] = prev_month_str
        stats['previous_month_display'] = prev_month_display
    except Exception as e:
        print(f"Error computing dashboard date badges: {e}")
        stats['yesterday_date'] = ''
        stats['yesterday_display'] = 'Yesterday'
        stats['previous_month'] = ''
        stats['previous_month_display'] = 'Previous Month'

    return render_template('dashboard.html', active_tab='DASHBOARD', stats=stats)

@app.route('/api/dashboard/yesterday-activity/pdf', methods=['GET'])
@login_required
def api_dashboard_yesterday_activity_pdf():
    try:
        from report_scheduler import get_yesterday_ist, build_yesterdays_activity_full_data
        comp_id = get_current_company_id()
        yesterday = get_yesterday_ist()
        company_info = get_current_company_info()

        activity_data = build_yesterdays_activity_full_data(comp_id, target_date=yesterday)
        pdf_buffer = pdf_generator.generate_yesterdays_activity_report_pdf(
            activity_data,
            company_info=company_info
        )

        disposition_type = 'attachment' if request.args.get('download') == '1' else 'inline'
        filename = f"yesterday_activity_{yesterday}.pdf"

        resp = make_response(pdf_buffer.getvalue())
        resp.headers['Content-Type'] = 'application/pdf'
        resp.headers['Content-Disposition'] = f'{disposition_type}; filename="{filename}"'
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return resp
    except Exception as e:
        print(f"Error generating yesterday activity PDF: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/dashboard/previous-month-salary/pdf', methods=['GET'])
@login_required
def api_dashboard_previous_month_salary_pdf():
    try:
        from report_scheduler import get_previous_month_ist, build_monthly_salary_report
        comp_id = get_current_company_id()
        prev_month = get_previous_month_ist()
        company_info = get_current_company_info()

        result = database.get_salary_reports(
            start_month=prev_month,
            end_month=prev_month,
            limit=1000,
            company_id=comp_id
        )
        data = result.get('data', []) if isinstance(result, dict) else []
        if not data:
            build_monthly_salary_report(comp_id, target_month=prev_month)
            result = database.get_salary_reports(
                start_month=prev_month,
                end_month=prev_month,
                limit=1000,
                company_id=comp_id
            )
            data = result.get('data', []) if isinstance(result, dict) else []

        pdf_buffer = pdf_generator.generate_salary_report_pdf(data, company_info=company_info)

        disposition_type = 'attachment' if request.args.get('download') == '1' else 'inline'
        filename = f"salary_report_{prev_month}.pdf"

        resp = make_response(pdf_buffer.getvalue())
        resp.headers['Content-Type'] = 'application/pdf'
        resp.headers['Content-Disposition'] = f'{disposition_type}; filename="{filename}"'
        resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return resp
    except Exception as e:
        print(f"Error generating previous month salary PDF: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/employee-details')
@login_required
def employee_details():
    return render_template('employees.html', active_tab='EMPLOYEE DETAILS')

@app.route('/live-report')
@login_required
def live_report():
    return render_template('live_report.html', active_tab='LIVE REPORT')

@app.route('/attendance-report')
@login_required
def attendance_report():
    employees_res = database.get_all_employees(company_id=get_current_company_id(), limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('attendance_report.html', active_tab='ATTENDANCE REPORT', employees=employees)

@app.route('/manual-entry')
@login_required
def manual_entry():
    return render_template('manual_entry.html', active_tab='MANUAL ENTRY')

@app.route('/payment-entry')
@login_required
def payment_entry():
    employees_res = database.get_all_employees(company_id=get_current_company_id(), limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('payment_entry.html', active_tab='PAYMENT ENTRY', employees=employees)

@app.route('/advance-management')
@login_required
def advance_management():
    employees_res = database.get_all_employees(company_id=get_current_company_id(), limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('advance_management.html', active_tab='PAYMENT ENTRY', employees=employees)

@app.route('/advance-summary')
@app.route('/balance-report')
@login_required
def balance_report():
    employees_res = database.get_all_employees(company_id=get_current_company_id(), limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('balance_report.html', active_tab='PAYMENT ENTRY', employees=employees)

@app.route('/monthly-payslip')
@app.route('/payslip-preview')
@login_required
def monthly_payslip():
    comp_id = get_current_company_id()
    if session.get('role') == 'super_admin':
        comp_id = 'ALL'
    employees_res = database.get_all_employees(company_id=comp_id, limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('monthly_payslip.html', active_tab='PAYSLIP PREVIEW', employees=employees)

@app.route('/salary-report')
@login_required
def salary_report():
    employees_res = database.get_all_employees(company_id=get_current_company_id(), limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('salary_report.html', active_tab='SALARY REPORT', employees=employees)

# ----------------- COMPANY MANAGEMENT API (SUPER ADMIN ONLY) ----------------- #

@app.route('/api/companies', methods=['GET'])
@super_admin_required
def api_get_companies():
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    result = database.get_all_companies(search=search, page=page, limit=limit)
    result['companies'] = result.get('data', [])
    import math
    result['pages'] = math.ceil(result['total'] / limit) if limit else 1
    return jsonify(result)

@app.route('/api/companies', methods=['POST'])
@super_admin_required
def api_create_company():
    data = request.get_json() if request.is_json else request.form.to_dict()
    try:
        comp_id = database.create_company(data)
        return jsonify({'success': True, 'id': comp_id, 'message': 'Company registered successfully'})
    except ValueError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': f'Failed to create company: {e}'}), 500

@app.route('/api/companies/<comp_id>', methods=['GET'])
@super_admin_required
def api_get_company(comp_id):
    comp = database.get_company_by_id(comp_id)
    if not comp:
        return jsonify({'error': 'Company not found'}), 404
    return jsonify(comp)

@app.route('/api/companies/<comp_id>', methods=['PUT', 'POST'])
@super_admin_required
def api_update_company(comp_id):
    data = request.get_json() if request.is_json else request.form.to_dict()
    try:
        database.update_company(comp_id, data)
        return jsonify({'success': True, 'message': 'Company updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/companies/<comp_id>', methods=['DELETE'])
@super_admin_required
def api_delete_company(comp_id):
    try:
        database.delete_company(comp_id)
        return jsonify({'success': True, 'message': 'Company deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/companies/<comp_id>/toggle-auto-reports', methods=['POST'])
@super_admin_required
def api_toggle_company_auto_reports(comp_id):
    data = request.get_json(silent=True) or {}
    enabled = data.get('enabled')
    new_state = database.toggle_company_auto_reports(comp_id, enabled)
    if new_state is None:
        return jsonify({'success': False, 'error': 'Company not found'}), 404
    return jsonify({
        'success': True,
        'company_id': comp_id,
        'auto_email_reports': new_state,
        'message': f"Automatic email reports {'enabled' if new_state else 'disabled'} successfully."
    })

@app.route('/api/companies/<comp_id>/toggle-delete-entries', methods=['POST'])
@super_admin_required
def api_toggle_company_delete_entries(comp_id):
    data = request.get_json(silent=True) or {}
    enabled = data.get('enabled')
    new_state = database.toggle_company_delete_entries(comp_id, enabled)
    if new_state is None:
        return jsonify({'success': False, 'error': 'Company not found'}), 404
    return jsonify({
        'success': True,
        'company_id': comp_id,
        'can_delete_entries': new_state,
        'message': f"Delete entries feature {'enabled' if new_state else 'disabled'} successfully."
    })

@app.route('/api/companies/reports', methods=['GET'])
@super_admin_required
def api_company_reports():
    summary = database.get_company_reports_summary()
    return jsonify({'success': True, 'summary': summary})

@app.route('/api/companies/export/excel', methods=['GET'])
@app.route('/api/companies/export/csv', methods=['GET'])
@super_admin_required
def api_companies_export_excel():
    search = request.args.get('search', '').strip()
    result = database.get_all_companies(search=search, limit=10000)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SL NO', 'COMPANY NAME', 'GSTIN', 'EMAIL', 'PHONE', 'ADDRESS', 'LATITUDE', 'LONGITUDE', 'SHIFT HOURS', 'EMPLOYEES', 'EMPLOYEE LIMIT', 'STATUS'])
    for idx, c in enumerate(result['data'], 1):
        writer.writerow([
            idx,
            c.get('company_name', ''),
            c.get('gstin', ''),
            c.get('email', ''),
            c.get('phone', ''),
            c.get('address', ''),
            c.get('latitude', ''),
            c.get('longitude', ''),
            c.get('shift_hours', '08:00'),
            c.get('employee_count', 0),
            c.get('employee_limit', 50),
            c.get('status', 'Active')
        ])
    output.seek(0)
    filename = "registered_companies.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/companies/export/pdf', methods=['GET'])
@super_admin_required
def api_companies_export_pdf():
    search = request.args.get('search', '').strip()
    result = database.get_all_companies(search=search, limit=10000)
    company_info = get_current_company_info()
    pdf_buffer = pdf_generator.generate_companies_pdf(result['data'], company_info=company_info)
    filename = "registered_companies.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ----------------- COMPANY PROFILE API ROUTES ----------------- #

@app.route('/api/company-profile', methods=['GET'])
@login_required
def api_get_company_profile():
    role = session.get('role', 'company_admin')
    if role == 'super_admin':
        req_id = request.args.get('company_id', '').strip()
        all_comps = database.get_all_companies(limit=1000)['data']
        
        # Build dropdown list with System Administration prominently at top
        comps_dropdown = [{'id': 'ARGUS_MASTER', 'company_name': 'System Administration (ARGUS TECHNOLOGIES)'}]
        for c in all_comps:
            if c.get('id') != 'ARGUS_MASTER':
                comps_dropdown.append({'id': c['id'], 'company_name': c.get('company_name', c['id'])})

        target_id = req_id or 'ARGUS_MASTER'
        company = database.get_company_by_id(target_id)
        if not company and target_id == 'ARGUS_MASTER':
            company = database.get_company_by_id('ARGUS_MASTER') or {
                'id': 'ARGUS_MASTER',
                'company_name': 'ARGUS TECHNOLOGIES',
                'email': 'technologiesargus@gmail.com'
            }

        is_master = (target_id == 'ARGUS_MASTER')
        if company:
            is_locked = company.get('coordinates_locked')
            if is_locked is None:
                lat = company.get('latitude')
                lng = company.get('longitude')
                is_locked = bool(lat is not None and lng is not None and str(lat).strip() != '' and str(lng).strip() != '')
            company['coordinates_locked'] = bool(is_locked)

            raw_pass = company.get('password_raw') or ''
            if not raw_pass and is_master:
                db = database.get_db()
                adm = db.admin_users.find_one({'role': 'super_admin'}) or db.admin_users.find_one({'username': 'Admin'})
                if adm:
                    raw_pass = adm.get('password_raw') or adm.get('password', '')
                    if raw_pass and (raw_pass.startswith('pbkdf2:') or raw_pass.startswith('scrypt:')):
                        raw_pass = ''
            elif not raw_pass:
                p = company.get('password', '')
                if p and not p.startswith('pbkdf2:') and not p.startswith('scrypt:'):
                    raw_pass = p
            company['saved_password'] = raw_pass
            company['has_password'] = bool(raw_pass or company.get('password') or company.get('password_hash'))
            company['logo'] = company.get('logo') or ''
            company['logo_url'] = company.get('logo_data') or (f"/uploads/{company['logo']}" if company.get('logo') else '')
            company.pop('password', None)
            company.pop('password_hash', None)

        return jsonify({
            'success': True,
            'role': 'super_admin',
            'company': company,
            'is_master': is_master,
            'companies_list': comps_dropdown
        })
    else:
        comp_id = session.get('company_id')
        company = database.get_company_by_id(comp_id)
        if not company:
            return jsonify({'success': False, 'error': 'Company profile not found'}), 404

        is_locked = company.get('coordinates_locked')
        if is_locked is None:
            lat = company.get('latitude')
            lng = company.get('longitude')
            is_locked = bool(lat is not None and lng is not None and str(lat).strip() != '' and str(lng).strip() != '')
        company['coordinates_locked'] = bool(is_locked)

        raw_pass = company.get('password_raw') or ''
        if not raw_pass:
            p = company.get('password', '')
            if p and not p.startswith('pbkdf2:') and not p.startswith('scrypt:'):
                raw_pass = p
        company['saved_password'] = raw_pass
        company['has_password'] = bool(raw_pass or company.get('password') or company.get('password_hash'))
        company['logo'] = company.get('logo') or ''
        company['logo_url'] = company.get('logo_data') or (f"/uploads/{company['logo']}" if company.get('logo') else '')
        company.pop('password', None)
        company.pop('password_hash', None)
        return jsonify({
            'success': True,
            'role': 'company_admin',
            'company': company,
            'has_password': company['has_password']
        })

@app.route('/api/company-profile', methods=['PUT'])
@login_required
def api_update_company_profile():
    role = session.get('role')
    if not role and session.get('admin_logged_in'):
        role = 'super_admin' if session.get('company_id') == 'ARGUS_MASTER' or not session.get('company_id') else 'company_admin'
    role = role or 'company_admin'
    data = request.get_json(silent=True) or {}
    
    if role == 'company_admin':
        comp_id = session.get('company_id')
        if not comp_id:
            return jsonify({'success': False, 'error': 'Unauthorized: No company ID associated with session.'}), 403

        comp = database.get_company_by_id(comp_id)
        if not comp:
            return jsonify({'success': False, 'error': 'Company profile not found'}), 404

        is_locked = comp.get('coordinates_locked')
        if is_locked is None:
            lat = comp.get('latitude')
            lng = comp.get('longitude')
            is_locked = bool(lat is not None and lng is not None and str(lat).strip() != '' and str(lng).strip() != '')

        # Coordinates handling: only once allowed for company_admin
        if 'latitude' in data or 'longitude' in data:
            lat_val = data.get('latitude')
            lng_val = data.get('longitude')

            # Check if user typed or pasted combined coordinates (e.g. "11.0298, 76.9740")
            if lat_val and (',' in str(lat_val) or ';' in str(lat_val)) and (not lng_val or str(lng_val).strip() == ''):
                import re
                parts = re.split(r'[,;]+', str(lat_val))
                if len(parts) >= 2:
                    lat_val = parts[0].strip()
                    lng_val = parts[1].strip()

            # If not locked yet, company admin can lock them for the first time
            if not is_locked and lat_val is not None and lng_val is not None and str(lat_val).strip() != '' and str(lng_val).strip() != '':
                new_lat = database.parse_coordinate_value(lat_val)
                new_lng = database.parse_coordinate_value(lng_val)
                database.update_company(comp_id, {
                    'latitude': new_lat,
                    'longitude': new_lng,
                    'coordinates_locked': True,
                    'coordinates_locked_at': database.get_ist_now()
                })

        if 'address' in data:
            address = str(data.get('address', '')).strip()
            if address:
                database.update_company(comp_id, {'address': address})
            
        new_pass = str(data.get('password', '')).strip()
        if new_pass:
            if len(new_pass) < 4:
                return jsonify({'success': False, 'error': 'Password must be at least 4 characters.'}), 400
            database.set_company_password(comp_id, new_pass)
            
        return jsonify({'success': True, 'message': 'Company profile updated successfully.'})
    
    elif role == 'super_admin':
        target_id = data.get('id') or data.get('company_id') or session.get('company_id') or 'ARGUS_MASTER'
        
        new_pass = str(data.get('password', '')).strip()
        if new_pass:
            if len(new_pass) < 4:
                return jsonify({'success': False, 'error': 'Password must be at least 4 characters.'}), 400
            if target_id == 'ARGUS_MASTER':
                database.set_admin_password(new_pass)
            else:
                database.set_company_password(target_id, new_pass)
            
        try:
            data_to_save = dict(data)
            data_to_save.pop('password', None)
            data_to_save.pop('password_hash', None)

            lat_val = data_to_save.get('latitude')
            lng_val = data_to_save.get('longitude')
            # Check if user typed or pasted combined coordinates
            if lat_val and (',' in str(lat_val) or ';' in str(lat_val)) and (not lng_val or str(lng_val).strip() == ''):
                import re
                parts = re.split(r'[,;]+', str(lat_val))
                if len(parts) >= 2:
                    lat_val = parts[0].strip()
                    lng_val = parts[1].strip()
                    data_to_save['longitude'] = lng_val

            if 'latitude' in data_to_save:
                val = lat_val
                if val is not None and str(val).strip() != '':
                    data_to_save['latitude'] = database.parse_coordinate_value(val)
                else:
                    data_to_save['latitude'] = None

            if 'longitude' in data_to_save:
                val = data_to_save.get('longitude')
                if val is not None and str(val).strip() != '':
                    data_to_save['longitude'] = database.parse_coordinate_value(val)
                else:
                    data_to_save['longitude'] = None

            if data_to_save.get('latitude') is not None and data_to_save.get('longitude') is not None and str(data_to_save.get('latitude')).strip() != '' and str(data_to_save.get('longitude')).strip() != '':
                data_to_save['coordinates_locked'] = True
                data_to_save['coordinates_locked_at'] = database.get_ist_now()

            database.update_company(target_id, data_to_save)
            return jsonify({'success': True, 'message': 'Company profile updated successfully.'})
        except Exception as e:
            print("Error in super_admin update_company_profile:", traceback.format_exc())
            return jsonify({'success': False, 'error': str(e)}), 400
            
    return jsonify({'success': False, 'error': 'Unauthorized: Admin role not recognized.'}), 403

@app.route('/api/company-profile/logo', methods=['POST'])
@login_required
def api_upload_company_logo():
    role = session.get('role', 'company_admin')
    if role not in ['super_admin', 'company_admin']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    if 'logo' not in request.files:
        return jsonify({'success': False, 'error': 'No logo file provided'}), 400

    file = request.files['logo']
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'No file selected'}), 400

    allowed_exts = {'png', 'jpg', 'jpeg', 'webp', 'svg'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed_exts:
        return jsonify({'success': False, 'error': f'Unsupported format .{ext}. Please upload PNG, JPG, JPEG, or WEBP.'}), 400

    if role == 'super_admin':
        comp_id = request.form.get('company_id') or session.get('company_id') or 'ARGUS_MASTER'
    else:
        comp_id = session.get('company_id')
        if not comp_id:
            return jsonify({'success': False, 'error': 'No company ID associated with session'}), 403

    comp_id_clean = re.sub(r'[^a-zA-Z0-9_-]', '_', str(comp_id))
    timestamp = int(datetime.now().timestamp())
    filename = f"company_logo_{comp_id_clean}_{timestamp}.{ext}"
    upload_folder = app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file_path = os.path.join(upload_folder, filename)

    file_bytes = file.read()
    with open(file_path, 'wb') as f:
        f.write(file_bytes)

    # Generate base64 data URI for database storage and recovery
    mime = f"image/{'svg+xml' if ext == 'svg' else ext}"
    if ext == 'jpg': mime = 'image/jpeg'
    b64_str = base64.b64encode(file_bytes).decode('utf-8')
    logo_data = f"data:{mime};base64,{b64_str}"

    db = database.get_db()
    if comp_id == 'ARGUS_MASTER':
        db.company_admin.update_one(
            {'id': 'ARGUS_MASTER'},
            {'$set': {'id': 'ARGUS_MASTER', 'company_name': 'ARGUS TECHNOLOGIES', 'logo': filename, 'logo_data': logo_data, 'updated_at': database.get_ist_now()}},
            upsert=True
        )
    else:
        database.update_company(comp_id, {'logo': filename, 'logo_data': logo_data})

    return jsonify({
        'success': True,
        'logo': filename,
        'logo_url': f"/uploads/{filename}",
        'message': 'Company logo uploaded and saved successfully.'
    })

@app.route('/api/company-profile/logo', methods=['DELETE'])
@login_required
def api_delete_company_logo():
    role = session.get('role', 'company_admin')
    if role not in ['super_admin', 'company_admin']:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403

    if role == 'super_admin':
        comp_id = request.args.get('company_id') or session.get('company_id') or 'ARGUS_MASTER'
    else:
        comp_id = session.get('company_id')

    db = database.get_db()
    db.company_admin.update_one(
        {'id': str(comp_id)},
        {'$set': {'logo': '', 'logo_data': '', 'updated_at': database.get_ist_now()}}
    )
    return jsonify({'success': True, 'message': 'Company logo removed successfully.'})

# ----------------- EMPLOYEE PORTAL API ROUTES ----------------- #

@app.route('/api/employee/my-attendance', methods=['GET'])
@employee_required
def api_employee_my_attendance():
    emp_id = session.get('employee_id')
    curr_emp = database.get_employee_by_id(emp_id)
    if curr_emp and curr_emp.get('permissions') and curr_emp['permissions'].get('attendance_history') is False:
        return jsonify({'error': 'Attendance history view is disabled for your account.'}), 403

    emp_name = session.get('employee_name')
    comp_id = session.get('company_id')
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()
    result = database.get_attendance_reports(
        report_type='all',
        start_date=from_date,
        end_date=to_date,
        employee=emp_name,
        limit=500,
        company_id=comp_id
    )
    return jsonify(result)

@app.route('/api/employee/my-payslip', methods=['GET'])
@employee_required
def api_employee_my_payslip():
    emp_id = session.get('employee_id')
    curr_emp = database.get_employee_by_id(emp_id)
    if curr_emp and curr_emp.get('permissions') and curr_emp['permissions'].get('monthly_payslip') is False:
        return jsonify({'error': 'Monthly payslip view is disabled for your account.'}), 403

    emp_name = session.get('employee_name')
    comp_id = session.get('company_id')
    month = request.args.get('month', '').strip()
    if not month:
        month = datetime.now().strftime("%Y-%m")
    payslip = database.get_payslip_data(emp_name, month, company_id=comp_id)
    return jsonify(payslip)

@app.route('/api/employee/credentials', methods=['POST'])
@employee_required
def api_employee_set_credentials():
    """Allows authenticated employee to create or update their portal password."""
    emp_id = session.get('employee_id')
    curr_emp = database.get_employee_by_id(emp_id)
    if curr_emp and curr_emp.get('permissions') and curr_emp['permissions'].get('employee_credentials') is False:
        return jsonify({'success': False, 'error': 'Credential updates are disabled for your account.'}), 403

    data = request.get_json(silent=True) or request.form.to_dict()
    new_password = str(data.get('password', '')).strip()
    if not new_password or len(new_password) < 4:
        return jsonify({'success': False, 'error': 'Password must be at least 4 characters long.'}), 400
    
    success = database.set_employee_password(emp_id, new_password)
    if success:
        return jsonify({
            'success': True,
            'message': 'Your password has been saved successfully! You can now sign in using your email and password.'
        })
    return jsonify({'success': False, 'error': 'Failed to save password. Please try again.'}), 500

# ----------------- LEAVE & PERMISSION API ROUTES ----------------- #

LEAVES_FOLDER = os.path.join(app.config['UPLOAD_FOLDER'], 'leaves')
try:
    os.makedirs(LEAVES_FOLDER, exist_ok=True)
except Exception:
    pass

@app.route('/uploads/leaves/<path:filename>')
def serve_leave_attachment(filename):
    return send_from_directory(LEAVES_FOLDER, filename)

@app.route('/api/employee/leave-balance', methods=['GET'])
@employee_required
def api_employee_leave_balance():
    emp_id = session.get('employee_id')
    comp_id = session.get('company_id')
    bal = database.get_employee_leave_balance(emp_id, company_id=comp_id)
    return jsonify({'success': True, 'balance': bal, 'balances': bal})

@app.route('/api/employee/leave-requests', methods=['GET'])
@employee_required
def api_employee_leave_requests():
    emp_id = session.get('employee_id')
    limit = int(request.args.get('limit', 20))
    page = int(request.args.get('page', 1))
    status = request.args.get('status', 'ALL')
    res = database.get_leave_requests(employee_id=emp_id, status=status, limit=limit, page=page)
    return jsonify({'success': True, 'requests': res['requests'], 'total': res['total']})

@app.route('/api/employee/leave-requests/apply', methods=['POST'])
@employee_required
def api_employee_apply_leave():
    emp_id = session.get('employee_id')
    emp = database.get_employee_by_id(emp_id)
    if not emp:
        return jsonify({'success': False, 'error': 'Employee profile not found'}), 404

    data = request.form.to_dict()
    leave_type = data.get('leave_type', '').strip()
    from_date = data.get('from_date', '').strip()
    to_date = data.get('to_date', '').strip() or from_date
    session_type = data.get('session', 'Full Day').strip()
    reason = data.get('reason', '').strip()

    if not leave_type or not from_date or not reason:
        return jsonify({'success': False, 'error': 'Please fill in all required fields (Leave Type, Dates, Reason).'}), 400

    attachments = []
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename:
            fname = werkzeug.utils.secure_filename(file.filename) or 'leave_doc'
            base_name, ext = os.path.splitext(fname)
            unique_fname = f"{base_name}_{int(time.time())}{ext}"
            os.makedirs(LEAVES_FOLDER, exist_ok=True)
            dest_path = os.path.join(LEAVES_FOLDER, unique_fname)
            file.save(dest_path)
            size_kb = round(os.path.getsize(dest_path) / 1024, 1)
            attachments.append({
                'filename': unique_fname,
                'original_name': fname,
                'file_url': f"/uploads/leaves/{unique_fname}",
                'size_str': f"{size_kb} KB",
                'mime_type': file.mimetype or 'application/octet-stream',
                'uploaded_at': database.get_ist_now().strftime('%d %b %Y %I:%M %p')
            })

    req_doc = {
        'company_id': emp.get('company_id') or session.get('company_id'),
        'employee_id': emp_id,
        'employee_code': emp.get('employee_id') or emp.get('emp_id') or str(emp_id),
        'employee_name': emp.get('employee_name', ''),
        'department': emp.get('department', 'General'),
        'designation': emp.get('designation', ''),
        'mobile_number': emp.get('mobile_number', ''),
        'leave_type': leave_type,
        'from_date': from_date,
        'to_date': to_date,
        'session': session_type,
        'reason': reason,
        'attachments': attachments
    }
    # For hourly employees, store time-based leave details
    if session_type == 'Hourly':
        req_doc['leave_from_time'] = data.get('leave_from_time', '').strip()
        req_doc['leave_to_time'] = data.get('leave_to_time', '').strip()
        req_doc['leave_duration'] = data.get('leave_duration', '').strip()
        try:
            req_doc['duration_hours'] = float(data.get('duration_hours', 0))
        except (ValueError, TypeError):
            req_doc['duration_hours'] = 0.0
    new_req = database.submit_leave_request(req_doc)
    return jsonify({
        'success': True,
        'message': 'Your leave request has been submitted successfully!',
        'request': new_req
    })

@app.route('/api/employee/permission-requests/apply', methods=['POST'])
@employee_required
def api_employee_apply_permission():
    emp_id = session.get('employee_id')
    emp = database.get_employee_by_id(emp_id)
    if not emp:
        return jsonify({'success': False, 'error': 'Employee profile not found'}), 404

    data = request.form.to_dict()
    perm_type = data.get('permission_type', 'Short Leave').strip()
    perm_date = data.get('date', '').strip()
    from_time = data.get('from_time', '').strip()
    to_time = data.get('to_time', '').strip()
    duration = data.get('duration', '02:00').strip()
    reason = data.get('reason', '').strip()

    if not perm_type or not perm_date or not from_time or not to_time:
        return jsonify({'success': False, 'error': 'Please fill in all required fields (Permission Type, Date, Times).'}), 400

    attachments = []
    if 'attachment' in request.files:
        file = request.files['attachment']
        if file and file.filename:
            fname = werkzeug.utils.secure_filename(file.filename) or 'perm_doc'
            base_name, ext = os.path.splitext(fname)
            unique_fname = f"{base_name}_{int(time.time())}{ext}"
            os.makedirs(LEAVES_FOLDER, exist_ok=True)
            dest_path = os.path.join(LEAVES_FOLDER, unique_fname)
            file.save(dest_path)
            size_kb = round(os.path.getsize(dest_path) / 1024, 1)
            attachments.append({
                'filename': unique_fname,
                'original_name': fname,
                'file_url': f"/uploads/leaves/{unique_fname}",
                'size_str': f"{size_kb} KB",
                'mime_type': file.mimetype or 'application/octet-stream',
                'uploaded_at': database.get_ist_now().strftime('%d %b %Y %I:%M %p')
            })

    req_doc = {
        'company_id': emp.get('company_id') or session.get('company_id'),
        'employee_id': emp_id,
        'employee_code': emp.get('employee_id') or emp.get('emp_id') or str(emp_id),
        'employee_name': emp.get('employee_name', ''),
        'department': emp.get('department', 'General'),
        'designation': emp.get('designation', ''),
        'mobile_number': emp.get('mobile_number', ''),
        'permission_type': perm_type,
        'date': perm_date,
        'from_time': from_time,
        'to_time': to_time,
        'duration': duration,
        'reason': reason,
        'attachments': attachments
    }
    new_req = database.submit_permission_request(req_doc)
    return jsonify({
        'success': True,
        'message': 'Your permission request has been submitted successfully!',
        'request': new_req
    })

@app.route('/api/admin/leave-permission/stats', methods=['GET'])
@login_required
def api_admin_leave_stats():
    comp_id = get_current_company_id()
    stats = database.get_admin_leave_stats(company_id=comp_id)
    return jsonify({'success': True, 'stats': stats})

@app.route('/api/admin/leave-permission/policy', methods=['GET', 'POST'])
@login_required
def api_admin_leave_policy():
    comp_id = get_current_company_id()
    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form.to_dict()
        saved = database.save_company_leave_policy(comp_id, data)
        return jsonify({
            'success': saved,
            'message': 'Leave policy saved successfully!',
            'policy': database.get_company_leave_policy(comp_id)
        })
    pol = database.get_company_leave_policy(comp_id)
    return jsonify({'success': True, 'policy': pol})

@app.route('/api/admin/leave-permission/balances', methods=['GET'])
@login_required
def api_admin_leave_balances():
    comp_id = get_current_company_id()
    search = request.args.get('search', '').strip()
    bals = database.get_all_employees_leave_balances(company_id=comp_id, search=search)
    return jsonify({'success': True, 'balances': bals})

@app.route('/api/admin/leave-permission/requests', methods=['GET'])
@login_required
def api_admin_leave_requests():
    comp_id = get_current_company_id()
    status = request.args.get('status', 'ALL')
    limit = int(request.args.get('limit', 50))
    page = int(request.args.get('page', 1))
    emp_id = request.args.get('employee_id', None)
    res = database.get_leave_requests(company_id=comp_id, employee_id=emp_id, status=status, limit=limit, page=page)
    return jsonify({
        'success': True,
        'requests': res['requests'],
        'total': res['total'],
        'page': res['page'],
        'limit': res['limit']
    })

@app.route('/api/admin/leave-permission/requests/<request_id>', methods=['GET'])
@login_required
def api_admin_leave_request_detail(request_id):
    req = database.get_leave_request_by_id(request_id)
    if not req:
        return jsonify({'success': False, 'error': 'Leave request not found'}), 404
    emp_id = req.get('employee_id')
    comp_id = req.get('company_id')
    emp = database.get_employee_by_id(emp_id)
    bal = database.get_employee_leave_balance(emp_id, company_id=comp_id)
    return jsonify({
        'success': True,
        'request': req,
        'employee': emp or {},
        'balance': bal or {}
    })

@app.route('/api/admin/leave-permission/requests/<request_id>/action', methods=['POST'])
@login_required
def api_admin_leave_request_action(request_id):
    data = request.get_json(silent=True) or request.form.to_dict()
    action = str(data.get('action') or data.get('status') or '').strip()
    if action.lower() in ['approve', 'approved']:
        action = 'Approved'
    elif action.lower() in ['reject', 'rejected']:
        action = 'Rejected'
    else:
        return jsonify({'success': False, 'error': "Action must be 'Approved' or 'Rejected'"}), 400
    remark = data.get('admin_remark', '').strip()
    reviewer = session.get('user') or 'Administrator'
    res = database.update_leave_request_status(request_id, action, admin_remark=remark, reviewer=reviewer)
    return jsonify(res)

# ----------------- EMPLOYEE MANAGEMENT API ROUTES ----------------- #

@app.route('/api/dashboard/stats')
@login_required
def api_dashboard_stats():
    stats = database.get_dashboard_stats(company_id=get_current_company_id())
    return jsonify(stats)

@app.route('/api/employees', methods=['GET'])
@login_required
def api_get_employees():
    search = request.args.get('search', '').strip()
    sort_col = request.args.get('sort_col', 'id')
    sort_dir = request.args.get('sort_dir', 'desc')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_all_employees(
        company_id=get_current_company_id(),
        search=search,
        sort_col=sort_col,
        sort_dir=sort_dir,
        page=page,
        limit=limit
    )
    return jsonify(result)

@app.route('/api/employees/<emp_id>', methods=['GET'])
@login_required
def api_get_employee(emp_id):
    emp = database.get_employee_by_id(emp_id)
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404
    return jsonify(emp)

def extract_employee_permissions(data, default_val=True):
    raw_perms = data.get('permissions')
    if isinstance(raw_perms, str):
        try:
            raw_perms = database.json.loads(raw_perms)
        except Exception:
            raw_perms = {}
    if not isinstance(raw_perms, dict):
        raw_perms = {}

    def to_bool(val, fallback):
        if val is None:
            return fallback
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        if s in ('true', '1', 'yes', 'on'):
            return True
        if s in ('false', '0', 'no', 'off'):
            return False
        return fallback

    return {
        'punch_attendance': to_bool(data.get('perm_punch_attendance', raw_perms.get('punch_attendance')), default_val),
        'attendance_history': to_bool(data.get('perm_attendance_history', raw_perms.get('attendance_history')), default_val),
        'monthly_payslip': to_bool(data.get('perm_monthly_payslip', raw_perms.get('monthly_payslip')), default_val),
        'employee_credentials': to_bool(data.get('perm_employee_credentials', raw_perms.get('employee_credentials')), default_val)
    }

@app.route('/api/employees', methods=['POST'])
@login_required
def api_create_employee():
    try:
        data = {}
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
            
        photo_filename = ''
        photo_data_url = ''
        face_registered = False
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                try:
                    file_bytes = file.read()
                    if file_bytes:
                        # Extract 128-d face embedding immediately for AI attendance
                        fe = get_face_engine()
                        if fe and hasattr(fe, 'extract_face_embedding_from_image'):
                            try:
                                embedding = fe.extract_face_embedding_from_image(file_bytes)
                                if embedding:
                                    data['face_embedding'] = database.json.dumps(embedding)
                                    face_registered = True
                            except Exception as fe_err:
                                print(f"Warning: face embedding extraction error: {fe_err}")
                        
                        unique_filename, photo_data_url, _ = process_uploaded_photo(file_bytes, file.filename)
                        photo_filename = unique_filename
                except Exception as pe:
                    print(f"Warning: photo processing error: {pe}")
                
        # Fallback: if photo was sent as base64 data URI in form body
        if not photo_data_url and data.get('photo_data') and str(data['photo_data']).startswith('data:image'):
            try:
                raw_b64 = str(data['photo_data'])
                header, b64_part = raw_b64.split(',', 1)
                img_bytes = base64.b64decode(b64_part)
                fe = get_face_engine()
                if fe and hasattr(fe, 'extract_face_embedding_from_image'):
                    try:
                        embedding = fe.extract_face_embedding_from_image(img_bytes)
                        if embedding:
                            data['face_embedding'] = database.json.dumps(embedding)
                            face_registered = True
                    except Exception as fe_err:
                        print(f"Warning: face embedding extraction error: {fe_err}")
                unique_filename, photo_data_url, _ = process_uploaded_photo(img_bytes, 'face_capture.jpg')
                photo_filename = unique_filename
            except Exception as b64_err:
                print(f"Warning: processing base64 photo_data failed: {b64_err}")

        if photo_filename:
            data['photo_filename'] = photo_filename
            data['photo'] = photo_filename
        if photo_data_url:
            data['photo_data'] = photo_data_url

        if not data.get('employee_name'):
            return jsonify({'error': 'Employee name is required'}), 400
        if not (data.get('email_id') or '').strip():
            return jsonify({'error': 'Email ID is required'}), 400
            
        data['permissions'] = extract_employee_permissions(data, default_val=True)
        emp_id = database.create_employee(data, company_id=get_current_company_id())
        success_msg = 'Employee created successfully'
        if face_registered:
            success_msg += ' (AI Face Biometrics Registered)'
        return jsonify({
            'success': True,
            'id': emp_id,
            'face_registered': face_registered,
            'message': success_msg
        })
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        print("Error in api_create_employee:", traceback.format_exc())
        return jsonify({'error': f'Failed to create employee: {str(e)}'}), 500

@app.route('/api/employees/<emp_id>', methods=['PUT', 'POST'])
@login_required
def api_update_employee(emp_id):
    try:
        emp = database.get_employee_by_id(emp_id)
        if not emp:
            return jsonify({'error': 'Employee not found'}), 404
            
        data = {}
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}
            
        if 'email_id' in data and not (data.get('email_id') or '').strip():
            return jsonify({'error': 'Email ID is required'}), 400
            
        face_registered = False
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                try:
                    file_bytes = file.read()
                    if file_bytes:
                        fe = get_face_engine()
                        if fe and hasattr(fe, 'extract_face_embedding_from_image'):
                            try:
                                embedding = fe.extract_face_embedding_from_image(file_bytes)
                                if embedding:
                                    data['face_embedding'] = database.json.dumps(embedding)
                                    face_registered = True
                            except Exception as fe_err:
                                print(f"Warning: face embedding extraction error: {fe_err}")
                        
                        unique_filename, photo_data_url, _ = process_uploaded_photo(file_bytes, file.filename)
                        data['photo_filename'] = unique_filename
                        data['photo'] = unique_filename
                        data['photo_data'] = photo_data_url
                except Exception as pe:
                    print(f"Warning: photo processing error: {pe}")
                
        # Fallback: if photo was sent as base64 data URI in update form body
        if not face_registered and 'photo_data' in data and data['photo_data'] and str(data['photo_data']).startswith('data:image'):
            try:
                raw_b64 = str(data['photo_data'])
                header, b64_part = raw_b64.split(',', 1)
                img_bytes = base64.b64decode(b64_part)
                fe = get_face_engine()
                if fe and hasattr(fe, 'extract_face_embedding_from_image'):
                    try:
                        embedding = fe.extract_face_embedding_from_image(img_bytes)
                        if embedding:
                            data['face_embedding'] = database.json.dumps(embedding)
                            face_registered = True
                    except Exception as fe_err:
                        print(f"Warning: face embedding extraction from photo_data error: {fe_err}")
                unique_filename, photo_data_url, _ = process_uploaded_photo(img_bytes, 'face_capture.jpg')
                data['photo_filename'] = unique_filename
                data['photo'] = unique_filename
                data['photo_data'] = photo_data_url
            except Exception as b64_err:
                print(f"Warning: processing base64 photo_data in update failed: {b64_err}")
                
        # Update permissions if permission fields or permissions dict was passed
        if any(k in data for k in ['perm_punch_attendance', 'perm_attendance_history', 'perm_monthly_payslip', 'perm_employee_credentials', 'permissions']):
            data['permissions'] = extract_employee_permissions(data, default_val=True)

        database.update_employee(emp_id, data)
        success_msg = 'Employee updated successfully'
        if face_registered:
            success_msg += ' (AI Face Biometrics Registered)'
        return jsonify({
            'success': True,
            'face_registered': face_registered,
            'message': success_msg
        })
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        print("Error in api_update_employee:", traceback.format_exc())
        return jsonify({'error': f'Failed to update employee: {str(e)}'}), 500

@app.route('/api/employees/<emp_id>', methods=['DELETE'])
@login_required
def api_delete_employee(emp_id):
    if not check_user_can_delete_entries():
        return jsonify({'error': 'Delete permission is disabled for your company. Please contact System Administrator.'}), 403
    emp = database.get_employee_by_id(emp_id)
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404
    database.delete_employee(emp_id)
    return jsonify({'success': True, 'message': 'Employee deleted successfully'})

@app.route('/api/employees/<emp_id>/pdf', methods=['GET'])
@login_required
def api_employee_pdf(emp_id):
    emp = database.get_employee_by_id(emp_id)
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404
        
    if emp.get('company_id') and emp.get('company_id') != 'ARGUS_MASTER':
        comp = database.get_company_by_id(emp['company_id'])
        if comp:
            emp['company_name'] = comp.get('company_name', 'ARGUS TECHNOLOGIES')
            
    pdf_buffer = pdf_generator.generate_employee_pdf(emp)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"employee_{emp_id}_{emp.get('employee_name', 'details')}.pdf",
        mimetype='application/pdf'
    )

@app.route('/api/employees/export/excel', methods=['GET'])
@app.route('/api/employees/export/csv', methods=['GET'])
@login_required
def api_employees_export_excel():
    search = request.args.get('search', '').strip()
    comp_id = get_current_company_id()
    result = database.get_all_employees(search=search, limit=10000, company_id=comp_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['SL NO', 'EMPLOYEE ID', 'EMPLOYEE NAME', 'SALARY BASIS', 'HOURLY SALARY', 'DAY SALARY', 'HALF DAY SALARY', 'MOBILE NUMBER', 'SHIFT HOURS', 'BANK NAME', 'ACCOUNT NUMBER', 'DATE OF JOINING'])
    for idx, emp in enumerate(result['data'], 1):
        st = str(emp.get('salary_type', 'hourly')).lower()
        st_label = 'Hourly' if st == 'hourly' else ('Day-Based' if st == 'daily' else 'Half-Day')
        writer.writerow([
            idx,
            emp.get('id', ''),
            emp.get('employee_name', ''),
            st_label,
            emp.get('hourly_salary', 0),
            emp.get('day_salary', 0),
            emp.get('half_day_salary', 0),
            emp.get('mobile_number', ''),
            emp.get('shift_hours', '08:00'),
            emp.get('bank_name', ''),
            emp.get('account_number', ''),
            emp.get('joining_date', '') or emp.get('date_of_joining', '')
        ])
    output.seek(0)
    filename = "employee_directory.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/employees/export/pdf', methods=['GET'])
@login_required
def api_employees_export_pdf():
    search = request.args.get('search', '').strip()
    comp_id = get_current_company_id()
    result = database.get_all_employees(search=search, limit=10000, company_id=comp_id)
    company_info = get_current_company_info()
    pdf_buffer = pdf_generator.generate_employees_pdf(result['data'], company_info=company_info)
    filename = "employee_directory.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    upload_folder = app.config['UPLOAD_FOLDER']
    file_path = os.path.join(upload_folder, filename)

    # 1. If file exists on disk, serve it directly
    if os.path.isfile(file_path):
        return send_from_directory(upload_folder, filename)

    # 2. If file missing from disk (e.g. server restart, ephemeral container, hard refresh),
    # recover it permanently from MongoDB Atlas!
    try:
        db = database.get_db()
        emp = db.employees.find_one({
            '$or': [
                {'photo': filename},
                {'photo_filename': filename}
            ]
        })
        if not emp:
            clean_name = os.path.basename(filename)
            import re
            emp = db.employees.find_one({
                '$or': [
                    {'photo': {'$regex': re.escape(clean_name)}},
                    {'photo_filename': {'$regex': re.escape(clean_name)}}
                ]
            })

        if emp and emp.get('photo_data'):
            raw_data = str(emp['photo_data'])
            if ',' in raw_data:
                header, b64_data = raw_data.split(',', 1)
                mime = header.split(';')[0].replace('data:', '') if 'data:' in header else 'image/jpeg'
            else:
                b64_data = raw_data
                mime = 'image/jpeg'
            img_bytes = base64.b64decode(b64_data)

            # Re-cache to disk for fast subsequent requests
            try:
                os.makedirs(upload_folder, exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(img_bytes)
            except Exception:
                pass

            return Response(img_bytes, mimetype=mime)

        # Check company_admin for company logos
        comp = db.company_admin.find_one({'logo': filename})
        if not comp:
            clean_name = os.path.basename(filename)
            import re
            comp = db.company_admin.find_one({'logo': {'$regex': re.escape(clean_name)}})
        if comp and comp.get('logo_data'):
            raw_data = str(comp['logo_data'])
            if ',' in raw_data:
                header, b64_data = raw_data.split(',', 1)
                mime = header.split(';')[0].replace('data:', '') if 'data:' in header else 'image/png'
            else:
                b64_data = raw_data
                mime = 'image/png'
            img_bytes = base64.b64decode(b64_data)
            try:
                os.makedirs(upload_folder, exist_ok=True)
                with open(file_path, 'wb') as f:
                    f.write(img_bytes)
            except Exception:
                pass
            return Response(img_bytes, mimetype=mime)
    except Exception as ex:
        print(f"Notice: Image recovery from DB error for {filename}: {ex}")

    return Response(DEFAULT_AVATAR_SVG, mimetype='image/svg+xml')

# ----------------- LIVE & TIMEOUT REPORT API ROUTES ----------------- #

@app.route('/api/live-entries', methods=['GET'])
@login_required
def api_get_live_entries():
    entry_type = request.args.get('type', 'live')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_live_entries(
        tab=entry_type,
        start_date=start_date,
        end_date=end_date,
        search=search,
        page=page,
        limit=limit,
        company_id=get_current_company_id()
    )
    return jsonify(result)

@app.route('/api/live-entries', methods=['POST'])
@login_required
def api_add_live_entry():
    data = request.get_json() if request.is_json else request.form.to_dict()
    employee_id = data.get('employee_id')
    employee_name = data.get('employee_name')
    if not employee_id or not employee_name:
        return jsonify({'error': 'Employee ID and name are required'}), 400
        
    user_lat = data.get('latitude') or data.get('user_lat')
    user_lng = data.get('longitude') or data.get('user_lng')
    entry_loc = data.get('entry_location') or data.get('live_address')

    inserted_id = database.add_live_entry(
        employee_id=employee_id,
        employee_name=employee_name,
        entry_time=data.get('entry_time'),
        site_name=data.get('site_name', 'OFFICE'),
        entry_location=entry_loc,
        entry_distance=float(data.get('entry_distance', 0.0)),
        is_timeout=int(data.get('is_timeout', 0)),
        user_lat=user_lat,
        user_lng=user_lng,
        company_id=get_current_company_id(),
        live_address=data.get('live_address')
    )
    return jsonify({'success': True, 'id': inserted_id})

@app.route('/api/live-entries/<entry_id>', methods=['DELETE'])
@login_required
def api_delete_live_entry(entry_id):
    if not check_user_can_delete_entries():
        return jsonify({'error': 'Delete permission is disabled for your company. Please contact System Administrator.'}), 403
    entry_type = request.args.get('type', 'live')
    success = database.delete_live_report_entry(entry_id, entry_type=entry_type, company_id=get_current_company_id())
    if not success:
        return jsonify({'error': 'Entry not found or could not be deleted'}), 404
    return jsonify({'success': True, 'message': 'Live report entry deleted successfully'})

@app.route('/api/live-entries/export/excel', methods=['GET'])
@app.route('/api/live-entries/export/csv', methods=['GET'])
@login_required
def api_export_excel():
    entry_type = request.args.get('type', 'live')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    result = database.get_live_entries(
        tab=entry_type,
        start_date=start_date,
        end_date=end_date,
        limit=10000,
        company_id=get_current_company_id()
    )
    
    output = io.StringIO()
    writer = csv.writer(output)
    time_header = 'EXIT TIME' if entry_type == 'timeout' else 'ENTRY TIME'
    writer.writerow(['EMPLOYEE NAME', time_header, 'SITE NAME', 'ENTRY LOCATION', 'ENTRY DISTANCE'])
    for r in result.get('data', []):
        time_val = (r.get('exit_time') if entry_type == 'timeout' and r.get('exit_time') else r.get('entry_time', '')) or '----'
        dist_val = r.get('formatted_distance') or (f"OFFICE DISTANCE {r.get('entry_distance', 0)}M" if r.get('entry_distance') is not None else '----')
        writer.writerow([
            r.get('employee_name', ''),
            time_val,
            r.get('site_name', '----') or '----',
            r.get('entry_location', '----') or '----',
            dist_val
        ])
        
    output.seek(0)
    filename = f"{entry_type}_entries_report.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/live-entries/export/pdf', methods=['GET'])
@login_required
def api_export_pdf():
    entry_type = request.args.get('type', 'live')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    result = database.get_live_entries(
        tab=entry_type,
        start_date=start_date,
        end_date=end_date,
        limit=10000,
        company_id=get_current_company_id()
    )
    
    title = "Live Entries Report" if entry_type == 'live' else "Timeout Entries Report"
    company_info = get_current_company_info()
    pdf_buffer = pdf_generator.generate_live_report_pdf(title, result['data'], company_info=company_info)
    filename = f"{entry_type}_entries_report.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ----------------- ZERO-IMAGE FACE RECOGNITION API ----------------- #

@app.route('/api/face/enroll', methods=['POST'])
@login_required
def api_face_enroll():
    """
    Enrolls employee face:
    Computes 128-d embedding and discards the image immediately.
    """
    emp_id = request.form.get('employee_id')
    if not emp_id:
        return jsonify({'error': 'Employee ID is required'}), 400
        
    if 'photo' not in request.files:
        return jsonify({'error': 'Face photo frame is required'}), 400
        
    file = request.files['photo']
    file_bytes = file.read()
    
    embedding = get_face_engine().extract_face_embedding_from_image(file_bytes)
    if not embedding:
        return jsonify({'error': 'No face detected in photo. Please ensure your face is clearly visible in good lighting.'}), 400

    database.save_face_embedding(emp_id, embedding)
    
    return jsonify({
        'success': True,
        'message': 'Face biometrics enrolled successfully. Image discarded for privacy.',
        'vector_dimensions': len(embedding)
    })

@app.route('/api/face/recognize', methods=['POST'])
def api_face_recognize():
    """
    Recognizes employee face from live camera frame:
    Compares 128-d deep vector with stored embeddings using Cosine Similarity.
    Marks attendance & creates live entry with company-specific geofencing.
    """
    try:
        if 'photo' not in request.files:
            return jsonify({'matched': False, 'message': 'Camera frame is required'}), 400
            
        file = request.files['photo']
        file_bytes = file.read()
        if not file_bytes:
            return jsonify({'matched': False, 'message': 'Empty camera frame received. Please try again.'}), 400

        engine = get_face_engine()
        if engine is None:
            return jsonify({
                'matched': False,
                'message': 'Face recognition engine is initializing or unavailable. Please try again in a few moments.'
            }), 503
        
        query_embedding = engine.extract_face_embedding_from_image(file_bytes)
        if not query_embedding:
            return jsonify({
                'matched': False,
                'confidence': 0.0,
                'message': 'No face detected in camera frame. Please face the camera directly in good lighting.'
            })

        # If marked from employee portal, scope search to employee's company
        portal_company_id = session.get('company_id') if session.get('employee_logged_in') else None
        result = engine.recognize_face(query_embedding, company_id=portal_company_id)
        
        if result.get('matched'):
            emp_id = result['employee_id']
            emp_name = result['employee_name']
            
            user_lat = request.form.get('latitude')
            user_lng = request.form.get('longitude')
            client_time = request.form.get('client_time')
            live_address = request.form.get('live_address') or request.form.get('location')
            
            # Enrich with employee details for dynamic punch card
            db = database.get_db()
            emp_doc = db.employees.find_one(database.build_id_filter(emp_id)) or db.employees.find_one({'employee_name': emp_name})
            
            # Check if Punch Attendance is permitted for employee when punching from portal
            if session.get('employee_logged_in') and emp_doc and emp_doc.get('permissions') and emp_doc['permissions'].get('punch_attendance') is False:
                return jsonify({
                    'matched': False,
                    'message': 'Punch attendance is disabled for your account by your administrator.'
                }), 403

            if emp_doc:
                result['employee_code'] = emp_doc.get('employee_id', emp_id)
                result['designation'] = emp_doc.get('designation', '') or 'Staff'
                result['department'] = emp_doc.get('department', '') or 'General'
                result['company_name'] = emp_doc.get('company_name', 'Argus Technologies')
                result['shift_hours'] = emp_doc.get('shift_hours', '08:00')
            else:
                result['employee_code'] = emp_id
                result['designation'] = 'Staff'
                result['department'] = 'General'
                result['company_name'] = 'Argus Technologies'

            # Mark Attendance Punch In / Punch Out Lifecycle & Live Entry (Company-aware, 12-hour format)
            punch_res = database.record_face_attendance(
                employee_id=emp_id,
                employee_name=emp_name,
                user_lat=user_lat,
                user_lng=user_lng,
                company_id=portal_company_id,
                client_time=client_time,
                live_address=live_address
            )
            result['live_entry_id'] = str(punch_res.get('live_id', ''))
            result['punch_status'] = str(punch_res.get('status', ''))
            result['formatted_distance'] = str(punch_res.get('formatted_dist', ''))
            result['live_location'] = str(punch_res.get('live_location', ''))
            result['entry_location'] = str(punch_res.get('live_location', ''))
            result['punch_time'] = client_time or datetime.now().strftime('%d %b %Y, %I:%M:%S %p')
            if punch_res.get('working_hours'):
                result['working_hours'] = str(punch_res.get('working_hours'))
            
        clean_result = database.clean_doc(result)
        return jsonify(clean_result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'matched': False,
            'message': f'Face recognition processing error: {str(e)}'
        }), 500

# ----------------- ATTENDANCE REPORTS API ROUTES ----------------- #

@app.route('/api/attendance-reports', methods=['GET'])
@login_required
def api_get_attendance_reports():
    report_type = request.args.get('type', 'all')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    employee = request.args.get('employee', 'All').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_attendance_reports(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        employee=employee,
        search=search,
        page=page,
        limit=limit,
        company_id=get_current_company_id()
    )
    return jsonify(result)

@app.route('/api/attendance-reports/compact', methods=['GET'])
@app.route('/api/attendance-reports/simple', methods=['GET'])
@login_required
def api_get_attendance_simple():
    employee = request.args.get('employee', 'All Employees').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    result = database.get_attendance_simple_table(
        employee=employee,
        start_date=start_date,
        end_date=end_date,
        company_id=get_current_company_id()
    )
    return jsonify(result)

@app.route('/api/attendance-reports/update', methods=['POST'])
@login_required
def api_update_attendance_records():
    return jsonify({'success': True, 'message': 'Attendance records updated successfully'})

@app.route('/api/attendance-reports/<report_id>', methods=['DELETE'])
@login_required
def api_delete_attendance_report(report_id):
    if not check_user_can_delete_entries():
        return jsonify({'error': 'Delete permission is disabled for your company. Please contact System Administrator.'}), 403
    is_manual = request.args.get('is_manual', 'false').lower() in ['true', '1', 'yes']
    success = database.delete_attendance_report(report_id, is_manual=is_manual, company_id=get_current_company_id())
    if not success:
        return jsonify({'error': 'Attendance record not found or could not be deleted'}), 404
    return jsonify({'success': True, 'message': 'Attendance record deleted successfully'})

@app.route('/api/attendance-reports/export/excel', methods=['GET'])
@app.route('/api/attendance-reports/export/csv', methods=['GET'])
@login_required
def api_attendance_export_excel():
    report_type = request.args.get('type', 'all')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    employee = request.args.get('employee', 'All').strip()
    comp_id = get_current_company_id()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if report_type in ['simple', 'compact']:
        result = database.get_attendance_simple_table(employee=employee, start_date=start_date, end_date=end_date, company_id=comp_id)
        writer.writerow(['EMPLOYEE NAME', 'ENTRY TIME', 'EXIT TIME', 'WORKING HOURS', 'SHIFT VARIANCE', 'WORKING SALARY', 'STATUS'])
        for r in result.get('data', []):
            writer.writerow([
                r.get('employee_name', ''),
                r.get('entry_time', ''),
                r.get('exit_time', '') or '',
                r.get('working_hours', '00:00') or '00:00',
                r.get('shift_variance', '') or '',
                r.get('working_salary', 0),
                r.get('status', 'Manual')
            ])
        writer.writerow([])
        writer.writerow(['TOTAL', '', '', result.get('total_working_hours', '00:00'), '----', result.get('total_working_salary', '0.00'), ''])
    else:
        result = database.get_attendance_reports(report_type=report_type, start_date=start_date, end_date=end_date, employee=employee, limit=10000, company_id=comp_id)
        writer.writerow(['EMPLOYEE NAME', 'ENTRY TIME', 'ENTRY DISTANCE', 'ENTRY LOCATION', 'ENTRY STATUS', 'EXIT TIME', 'EXIT DISTANCE', 'EXIT LOCATION', 'EXIT STATUS', 'WORKING HOURS', 'SHIFT VARIANCE', 'WORKING SALARY'])
        for r in result.get('data', []):
            writer.writerow([
                r.get('employee_name', ''),
                r.get('entry_time', '') or '',
                r.get('entry_distance', '----') or '----',
                r.get('entry_location', '----') or '----',
                r.get('entry_status', '-') or '-',
                r.get('exit_time', '----') or '----',
                r.get('exit_distance', '----') or '----',
                r.get('exit_location', '----') or '----',
                r.get('exit_status', '-') or '-',
                r.get('working_hours', '00:00') or '00:00',
                r.get('shift_variance', '----') or '----',
                r.get('working_salary', 0) if r.get('working_salary') is not None else 0
            ])
            
    output.seek(0)
    filename = f"attendance_{report_type}_report.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/attendance-reports/export/pdf', methods=['GET'])
@login_required
def api_attendance_export_pdf():
    report_type = request.args.get('type', 'all')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    employee = request.args.get('employee', 'All').strip()
    comp_id = get_current_company_id()
    
    company_info = get_current_company_info()
    if report_type in ['simple', 'compact']:
        result = database.get_attendance_simple_table(employee=employee, start_date=start_date, end_date=end_date, company_id=comp_id)
        emp_title = f" - {employee}" if (employee and employee not in ['All', 'All Employees']) else ""
        date_title = f" ({start_date} to {end_date})" if (start_date and end_date) else (f" (From {start_date})" if start_date else (f" (Up to {end_date})" if end_date else ""))
        title = f"Attendance Report (Compact View){emp_title}{date_title}"
        totals = {
            'total_working_hours': result['total_working_hours'],
            'total_working_salary': result['total_working_salary']
        }
        pdf_buffer = pdf_generator.generate_attendance_report_pdf(title, result['data'], is_simple=True, totals=totals, company_info=company_info)
    else:
        result = database.get_attendance_reports(report_type=report_type, start_date=start_date, end_date=end_date, employee=employee, limit=10000, company_id=comp_id)
        titles = {
            'all': 'All Attendance Entries',
            'proper': 'Proper Attendance Entries',
            'improper': 'Improper Attendance Entries',
            'manual': 'Manual Attendance Entries'
        }
        title = titles.get(report_type, 'Attendance Report')
        pdf_buffer = pdf_generator.generate_attendance_report_pdf(title, result['data'], is_simple=False, company_info=company_info)
        
    filename = f"attendance_{report_type}_report.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ----------------- MANUAL ENTRIES API ROUTES ----------------- #

@app.route('/api/manual-entries', methods=['GET'])
@login_required
def api_get_manual_entries():
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()
    status = request.args.get('status', 'All').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_manual_entries(
        from_date=from_date,
        to_date=to_date,
        status=status,
        search=search,
        page=page,
        limit=limit,
        company_id=get_current_company_id()
    )
    return jsonify(result)

@app.route('/api/manual-entries/<entry_id>', methods=['GET'])
@login_required
def api_get_manual_entry(entry_id):
    entry = database.get_manual_entry_by_id(entry_id)
    if not entry:
        return jsonify({'error': 'Manual entry not found'}), 404
    return jsonify(entry)

@app.route('/api/manual-entries', methods=['POST'])
@login_required
def api_create_manual_entry():
    data = request.get_json() if request.is_json else request.form.to_dict()
    if not data.get('employee_name'):
        return jsonify({'error': 'Employee name is required'}), 400
        
    inserted_id = database.create_manual_entry(data, company_id=get_current_company_id())
    return jsonify({'success': True, 'id': inserted_id, 'message': 'Manual entry created successfully'})

@app.route('/api/manual-entries/<entry_id>', methods=['PUT', 'POST'])
@login_required
def api_update_manual_entry(entry_id):
    entry = database.get_manual_entry_by_id(entry_id)
    if not entry:
        return jsonify({'error': 'Manual entry not found'}), 404
        
    data = request.get_json() if request.is_json else request.form.to_dict()
    database.update_manual_entry(entry_id, data)
    return jsonify({'success': True, 'message': 'Manual entry updated successfully'})

@app.route('/api/manual-entries/<entry_id>', methods=['DELETE'])
@login_required
def api_delete_manual_entry(entry_id):
    if not check_user_can_delete_entries():
        return jsonify({'error': 'Delete permission is disabled for your company. Please contact System Administrator.'}), 403
    entry = database.get_manual_entry_by_id(entry_id)
    if not entry:
        return jsonify({'error': 'Manual entry not found'}), 404
        
    database.delete_manual_entry(entry_id)
    return jsonify({'success': True, 'message': 'Manual entry deleted successfully'})

@app.route('/api/manual-entries/export/excel', methods=['GET'])
@app.route('/api/manual-entries/export/csv', methods=['GET'])
@login_required
def api_manual_entries_export_excel():
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()
    status = request.args.get('status', 'All').strip()
    
    result = database.get_manual_entries(
        from_date=from_date,
        to_date=to_date,
        status=status,
        limit=10000,
        company_id=get_current_company_id()
    )
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['NAME', 'DATE', 'HOURS', 'STATUS', 'SUBMITTED', 'HOURLY', 'DAY', 'HALF', 'WORKING SALARY'])
    for r in result['data']:
        sal = f"+{int(float(r.get('working_salary', 0)))}" if float(r.get('working_salary', 0)) > 0 else "0"
        st_val = r.get('status', '')
        rs_val = (r.get('reason') or '').strip()
        status_display = f"{st_val} ({rs_val})" if rs_val else st_val
        writer.writerow([
            r['employee_name'], r['entry_date'], r['hours'], status_display,
            r['submitted_at'], int(float(r['hourly_rate'])), int(float(r['day_rate'])),
            int(float(r['half_rate'])), sal
        ])
        
    output.seek(0)
    filename = "manual_entries_report.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/manual-entries/export/pdf', methods=['GET'])
@login_required
def api_manual_entries_export_pdf():
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()
    status = request.args.get('status', 'All').strip()
    
    result = database.get_manual_entries(
        from_date=from_date,
        to_date=to_date,
        status=status,
        limit=10000,
        company_id=get_current_company_id()
    )
    company_info = get_current_company_info()
    pdf_buffer = pdf_generator.generate_manual_entries_pdf(result['data'], company_info=company_info)
    filename = "manual_entries_report.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ----------------- PAYMENT MANAGEMENT API ROUTES ----------------- #

RECEIPTS_FOLDER = os.path.join(app.config['UPLOAD_FOLDER'], 'receipts')
try:
    os.makedirs(RECEIPTS_FOLDER, exist_ok=True)
except Exception:
    pass

@app.route('/api/payments', methods=['GET'])
@login_required
def api_get_payments():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    bank = request.args.get('bank', 'All').strip()
    payment_type = request.args.get('payment_type', 'All').strip()
    status = (request.args.get('status') or request.args.get('reason') or 'All').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_payments(
        employee=employee,
        start_date=start_date,
        end_date=end_date,
        bank=bank,
        payment_type=payment_type,
        status=status,
        search=search,
        page=page,
        limit=limit,
        company_id=get_current_company_id()
    )
    return jsonify(result)

@app.route('/api/payments/<payment_id>', methods=['GET'])
@login_required
def api_get_payment(payment_id):
    p = database.get_payment_by_id(payment_id)
    if not p:
        return jsonify({'error': 'Payment not found'}), 404
    return jsonify(p)

@app.route('/api/payments', methods=['POST'])
@login_required
def api_create_payment():
    data = {}
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
        
    if 'receipt' in request.files:
        file = request.files['receipt']
        if file and file.filename:
            fname = werkzeug.utils.secure_filename(file.filename)
            uniq = f"{int(database.time.time())}_{fname}"
            file.save(os.path.join(RECEIPTS_FOLDER, uniq))
            data['receipt_filename'] = uniq
            
    if not data.get('employee_name'):
        return jsonify({'error': 'Employee name is required'}), 400
        
    inserted_id = database.create_payment(data, company_id=get_current_company_id())
    return jsonify({'success': True, 'id': inserted_id, 'message': 'Payment created successfully'})

@app.route('/api/payments/<payment_id>', methods=['PUT', 'POST'])
@login_required
def api_update_payment(payment_id):
    p = database.get_payment_by_id(payment_id)
    if not p:
        return jsonify({'error': 'Payment not found'}), 404
        
    data = {}
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
        
    if 'receipt' in request.files:
        file = request.files['receipt']
        if file and file.filename:
            fname = werkzeug.utils.secure_filename(file.filename)
            uniq = f"{int(database.time.time())}_{fname}"
            file.save(os.path.join(RECEIPTS_FOLDER, uniq))
            data['receipt_filename'] = uniq
            
    database.update_payment(payment_id, data)
    return jsonify({'success': True, 'message': 'Payment updated successfully'})

@app.route('/api/payments/<payment_id>', methods=['DELETE'])
@login_required
def api_delete_payment(payment_id):
    if not check_user_can_delete_entries():
        return jsonify({'error': 'Delete permission is disabled for your company. Please contact System Administrator.'}), 403
    p = database.get_payment_by_id(payment_id)
    if not p:
        return jsonify({'error': 'Payment not found'}), 404
        
    database.delete_payment(payment_id)
    return jsonify({'success': True, 'message': 'Payment deleted successfully'})

@app.route('/api/payments/export/excel', methods=['GET'])
@app.route('/api/payments/export/csv', methods=['GET'])
@login_required
def api_payments_export_excel():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    bank = request.args.get('bank', 'All').strip()
    payment_type = request.args.get('payment_type', 'All').strip()
    status = (request.args.get('status') or request.args.get('reason') or 'All').strip()
    
    result = database.get_payments(
        employee=employee,
        start_date=start_date,
        end_date=end_date,
        bank=bank,
        payment_type=payment_type,
        status=status,
        limit=10000,
        company_id=get_current_company_id()
    )
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['TIMESTAMP', 'EMPLOYEE', 'DATE', 'AMOUNT', 'BANK', 'PAYMENT TYPE', 'STATUS'])
    for r in result['data']:
        st = r.get('status') or r.get('reason') or 'Payment'
        rs = r.get('reason') if r.get('status') else ''
        disp_st = f"{st} - {rs}" if rs else st
        writer.writerow([
            r['timestamp'], r['employee_name'], r['payment_date'],
            f"{float(r['amount']):.2f}", r['bank'] or '-',
            r['payment_type'], disp_st
        ])
        
    output.seek(0)
    filename = "payment_management_report.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/payments/export/pdf', methods=['GET'])
@login_required
def api_payments_export_pdf():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    bank = request.args.get('bank', 'All').strip()
    payment_type = request.args.get('payment_type', 'All').strip()
    status = (request.args.get('status') or request.args.get('reason') or 'All').strip()
    
    result = database.get_payments(
        employee=employee,
        start_date=start_date,
        end_date=end_date,
        bank=bank,
        payment_type=payment_type,
        status=status,
        limit=10000,
        company_id=get_current_company_id()
    )
    company_info = get_current_company_info()
    pdf_buffer = pdf_generator.generate_payments_pdf(result['data'], company_info=company_info)
    filename = "payment_management_report.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ----------------- ADVANCE MANAGEMENT API ROUTES ----------------- #

@app.route('/api/advances', methods=['GET'])
@login_required
def api_get_advances():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_advances(
        employee=employee,
        start_date=start_date,
        end_date=end_date,
        search=search,
        page=page,
        limit=limit,
        company_id=get_current_company_id()
    )
    return jsonify(result)

@app.route('/api/advances/<advance_id>', methods=['GET'])
@login_required
def api_get_advance(advance_id):
    a = database.get_advance_by_id(advance_id)
    if not a:
        return jsonify({'error': 'Advance not found'}), 404
    return jsonify(a)

@app.route('/api/advances', methods=['POST'])
@login_required
def api_create_advance():
    data = request.get_json() if request.is_json else request.form.to_dict()
    if not data.get('employee_name'):
        return jsonify({'error': 'Employee name is required'}), 400
        
    inserted_id = database.create_advance(data, company_id=get_current_company_id())
    return jsonify({'success': True, 'id': inserted_id, 'message': 'Advance created successfully'})

@app.route('/api/advances/<advance_id>', methods=['PUT', 'POST'])
@login_required
def api_update_advance(advance_id):
    a = database.get_advance_by_id(advance_id)
    if not a:
        return jsonify({'error': 'Advance not found'}), 404
        
    data = request.get_json() if request.is_json else request.form.to_dict()
    database.update_advance(advance_id, data)
    return jsonify({'success': True, 'message': 'Advance updated successfully'})

@app.route('/api/advances/<advance_id>', methods=['DELETE'])
@login_required
def api_delete_advance(advance_id):
    if not check_user_can_delete_entries():
        return jsonify({'error': 'Delete permission is disabled for your company. Please contact System Administrator.'}), 403
    a = database.get_advance_by_id(advance_id)
    if not a:
        return jsonify({'error': 'Advance not found'}), 404
        
    database.delete_advance(advance_id)
    return jsonify({'success': True, 'message': 'Advance deleted successfully'})

@app.route('/api/advances/export/excel', methods=['GET'])
@app.route('/api/advances/export/csv', methods=['GET'])
@login_required
def api_advances_export_excel():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    result = database.get_advances(
        employee=employee,
        start_date=start_date,
        end_date=end_date,
        limit=10000,
        company_id=get_current_company_id()
    )
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['TIMESTAMP', 'EMPLOYEE', 'DATE', 'AMOUNT'])
    for r in result['data']:
        writer.writerow([
            r['timestamp'], r['employee_name'], r['advance_date'],
            f"{float(r['amount']):.2f}"
        ])
        
    output.seek(0)
    filename = "advance_management_report.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/advances/export/pdf', methods=['GET'])
@login_required
def api_advances_export_pdf():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    result = database.get_advances(
        employee=employee,
        start_date=start_date,
        end_date=end_date,
        limit=10000,
        company_id=get_current_company_id()
    )
    company_info = get_current_company_info()
    pdf_buffer = pdf_generator.generate_advances_pdf(result['data'], company_info=company_info)
    filename = "advance_management_report.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ----------------- BALANCE REPORT API ROUTES ----------------- #

@app.route('/api/advance-summary', methods=['GET'])
@app.route('/api/balance-report', methods=['GET'])
@login_required
def api_get_balance_report():
    employee = request.args.get('employee', 'All').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    result = database.get_balance_report(
        employee=employee,
        search=search,
        page=page,
        limit=limit,
        company_id=get_current_company_id()
    )
    return jsonify(result)

@app.route('/api/advance-summary/export/excel', methods=['GET'])
@app.route('/api/advance-summary/export/csv', methods=['GET'])
@app.route('/api/balance-report/export/excel', methods=['GET'])
@app.route('/api/balance-report/export/csv', methods=['GET'])
@login_required
def api_balance_report_export_excel():
    employee = request.args.get('employee', 'All').strip()
    result = database.get_balance_report(employee=employee, limit=10000, company_id=get_current_company_id())
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['DATE&TIME', 'NAME', 'DATE', 'ADVANCE AMOUNT', 'REPAYMENT AMOUNT', 'BALANCE AMOUNT'])
    for r in result['data']:
        pay_amt = r.get('payment_amount', r.get('advance_repayment_amount', 0.0))
        writer.writerow([
            r['timestamp'], r['name'], r['date'],
            f"{float(r['advance_amount']):.2f}",
            f"{float(pay_amt):.2f}",
            f"{float(r['balance_amount']):.2f}"
        ])
    writer.writerow([])
    writer.writerow(['TOTAL ADVANCE', f"{result['total_advance']:.2f}", 'TOTAL REPAYMENT', f"{result.get('total_payment', result.get('total_repayment', 0.0)):.2f}", 'BALANCE AMOUNT', f"{result['balance_amount']:.2f}"])
    output.seek(0)
    filename = "advance_summary.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/advance-summary/export/pdf', methods=['GET'])
@app.route('/api/balance-report/export/pdf', methods=['GET'])
@login_required
def api_balance_report_export_pdf():
    employee = request.args.get('employee', 'All').strip()
    result = database.get_balance_report(employee=employee, limit=10000, company_id=get_current_company_id())
    totals = {
        'total_advance': result['total_advance'],
        'total_repayment': result.get('total_payment', result.get('total_repayment', 0.0)),
        'total_payment': result.get('total_payment', result.get('total_repayment', 0.0)),
        'balance_amount': result['balance_amount']
    }
    company_info = get_current_company_info()
    pdf_buffer = pdf_generator.generate_balance_report_pdf(result['data'], totals, company_info=company_info)
    filename = "advance_summary.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ----------------- MONTHLY PAYSLIP API ROUTES ----------------- #

@app.route('/api/payslip/generate', methods=['GET', 'POST'])
@login_required
def api_generate_payslip():
    if request.method == 'POST':
        data = request.get_json() if request.is_json else request.form.to_dict()
        employee = (data.get('employee_name') or data.get('employee') or '').strip()
        month = data.get('month', '').strip()
    else:
        employee = (request.args.get('employee_name') or request.args.get('employee') or '').strip()
        month = request.args.get('month', '').strip()
        
    if not employee:
        return jsonify({'error': 'Employee name is required'}), 400
    if not month:
        month = datetime.now().strftime("%Y-%m")
        
    comp_id = get_current_company_id()
    if session.get('role') == 'super_admin':
        comp_id = None
    payslip = database.get_payslip_data(employee, month, company_id=comp_id)
    database.save_generated_salary_report(payslip, company_id=payslip.get('company_id') or comp_id)
    return jsonify(payslip)

@app.route('/api/payslip/export/pdf', methods=['GET'])
def api_export_payslip_pdf():
    """Generates and downloads payslip PDF. Available to Admins and Employees."""
    employee = (request.args.get('employee_name') or request.args.get('employee') or '').strip()
    month = request.args.get('month', '').strip()
    
    if not month:
        month = datetime.now().strftime("%Y-%m")
    
    comp_id = get_current_company_id()
    if session.get('role') == 'super_admin':
        comp_id = None
    if not employee:
        emp_res = database.get_all_employees(company_id=comp_id or 'ALL', limit=1)
        if emp_res['data']:
            employee = emp_res['data'][0]['employee_name']
        else:
            employee = 'Employee'
    
    template = request.args.get('template', 'template_1').strip()
    theme = request.args.get('theme', 'navy').strip()
    payslip = database.get_payslip_data(employee, month, company_id=comp_id)
    pdf_buffer = pdf_generator.generate_payslip_pdf(payslip, template_id=template, theme=theme)
    filename = f"payslip_{employee}_{month}.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ----------------- SALARY REPORTS API ROUTES ----------------- #

@app.route('/api/salary-reports', methods=['GET'])
@login_required
def api_get_salary_reports():
    start_month = request.args.get('start_month', '').strip()
    end_month = request.args.get('end_month', '').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_salary_reports(
        start_month=start_month,
        end_month=end_month,
        search=search,
        page=page,
        limit=limit,
        company_id=get_current_company_id()
    )
    return jsonify(result)

@app.route('/api/salary-reports/export/excel', methods=['GET'])
@app.route('/api/salary-reports/export/csv', methods=['GET'])
@login_required
def api_salary_reports_export_excel():
    start_month = request.args.get('start_month', '').strip()
    end_month = request.args.get('end_month', '').strip()
    
    result = database.get_salary_reports(
        start_month=start_month,
        end_month=end_month,
        limit=10000,
        company_id=get_current_company_id()
    )
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'EMPLOYEE NAME', 'PAY PERIOD', 'WORKING DAYS', 'WORKING HOURS',
        'ALLOWANCE', 'INCENTIVE', 'OTHER EARNINGS', 'BASIC EARNINGS',
        'TOTAL EARNINGS', 'PAID SALARY', 'ADVANCE REPAYMENT', 'OTHER DEDUCTIONS',
        'TOTAL DEDUCTIONS', 'NET SALARY'
    ])
    for r in result['data']:
        writer.writerow([
            r['employee_name'], r['pay_period'], r['working_days'], r['working_hours'],
            int(float(r['allowance'])), int(float(r['incentive'])), int(float(r['other_earnings'])),
            int(float(r['basic_earnings'])), int(float(r['total_earnings'])), int(float(r['paid_salary'])),
            int(float(r['advance_repayment'])), int(float(r['other_deductions'])), int(float(r['total_deductions'])),
            int(float(r['net_salary']))
        ])
        
    output.seek(0)
    filename = "salary_report.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/salary-reports/export/pdf', methods=['GET'])
@login_required
def api_salary_reports_export_pdf():
    start_month = request.args.get('start_month', '').strip()
    end_month = request.args.get('end_month', '').strip()
    
    result = database.get_salary_reports(
        start_month=start_month,
        end_month=end_month,
        limit=10000,
        company_id=get_current_company_id()
    )
    company_info = get_current_company_info()
    pdf_buffer = pdf_generator.generate_salary_report_pdf(result['data'], company_info=company_info)
    filename = "salary_report.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

# ----------------- AUTOMATED COMPANY EMAIL REPORTING ROUTES ----------------- #

@app.route('/api/admin/reports/send-daily', methods=['POST'])
@super_admin_required
def api_admin_send_daily_reports():
    """Manually triggers or tests yesterday's daily activity reports to companies."""
    data = request.get_json() if request.is_json else request.form.to_dict()
    company_id = (data.get('company_id') or '').strip()
    target_date = (data.get('date') or '').strip() or None
    force = bool(data.get('force', False))

    import report_scheduler
    if company_id and company_id != 'ALL':
        ok, msg, report = report_scheduler.send_daily_activity_email(company_id, target_date=target_date, force=force)
        return jsonify({
            'success': ok,
            'message': msg,
            'company_id': company_id,
            'report': report
        })
    else:
        results = report_scheduler.dispatch_all_daily_reports(target_date=target_date, force=force)
        return jsonify({
            'success': True,
            'total_companies': len(results),
            'results': results
        })

@app.route('/api/admin/reports/send-monthly', methods=['POST'])
@super_admin_required
def api_admin_send_monthly_reports():
    """Manually triggers or tests monthly payroll reports to companies."""
    data = request.get_json() if request.is_json else request.form.to_dict()
    company_id = (data.get('company_id') or '').strip()
    target_month = (data.get('month') or '').strip() or None
    force = bool(data.get('force', False))

    import report_scheduler
    if company_id and company_id != 'ALL':
        ok, msg, report = report_scheduler.send_monthly_salary_email(company_id, target_month=target_month, force=force)
        return jsonify({
            'success': ok,
            'message': msg,
            'company_id': company_id,
            'report': report
        })
    else:
        results = report_scheduler.dispatch_all_monthly_reports(target_month=target_month, force=force)
        return jsonify({
            'success': True,
            'total_companies': len(results),
            'results': results
        })

@app.route('/api/admin/reports/email-logs', methods=['GET'])
@super_admin_required
def api_admin_email_logs():
    """Retrieves recent email dispatch audit logs from db.email_logs."""
    db = database.get_db()
    limit = int(request.args.get('limit', 50))
    company_id = request.args.get('company_id', '').strip()
    q = {}
    if company_id and company_id != 'ALL':
        q['company_id'] = company_id
    logs = list(db.email_logs.find(q).sort('_id', -1).limit(limit))
    return jsonify({'logs': database.clean_doc(logs)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
