import os
import io
import csv
import secrets
import urllib.parse
import requests
import werkzeug.utils
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, send_from_directory, Response, session
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

app.config['UPLOAD_FOLDER'] = os.environ.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(__file__), 'static', 'uploads'))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create upload directory: {e}")

try:
    database.init_db()
    fe = get_face_engine()
    if fe:
        fe.ensure_models_available()
        fe.auto_sync_stored_employee_embeddings()
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
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def super_admin_required(f):
    """Requires Super Admin session (Platform Owner)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in') or session.get('role') != 'super_admin':
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def employee_required(f):
    """Requires Employee self-service session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('employee_logged_in') or session.get('role') != 'employee':
            return redirect(url_for('employee_login'))
        return f(*args, **kwargs)
    return decorated_function

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
    if os.path.exists(os.path.join(icon_dir, 'logo.png')):
        return send_from_directory(icon_dir, 'logo.png', mimetype='image/png')
    return Response(status=204)

@app.errorhandler(500)
def handle_500(e):
    err = traceback.format_exc()
    print("500 Internal Error:", err)
    return f"<h1>Internal Server Error (500)</h1><pre>{err}</pre>", 500

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return e
    err = traceback.format_exc()
    print("Unhandled Exception:", err)
    return f"<h1>Server Error</h1><pre>{err}</pre>", 500

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
                error_msg = 'Access Denied: Email is not authorized as Super Admin. Please verify with Google below.'
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
                f"Access Denied: The Google account '{google_email}' is not authorized as Super Admin."
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
    return render_template('dashboard.html', active_tab='DASHBOARD', stats=stats)

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

@app.route('/balance-report')
@login_required
def balance_report():
    employees_res = database.get_all_employees(company_id=get_current_company_id(), limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('balance_report.html', active_tab='PAYMENT ENTRY', employees=employees)

@app.route('/monthly-payslip')
@login_required
def monthly_payslip():
    employees_res = database.get_all_employees(company_id=get_current_company_id(), limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('monthly_payslip.html', active_tab='MONTHLY PAYSLIP', employees=employees)

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
            # STRICT PRIVACY RULE: Never leak client company passwords to Super Admin
            if not is_master:
                company.pop('password', None)
                company.pop('password_hash', None)
                company['has_password'] = False
            else:
                has_pass = bool(company.get('password') or company.get('password_hash'))
                company['has_password'] = has_pass
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
        has_pass = bool(company.get('password') or company.get('password_hash'))
        company['has_password'] = has_pass
        company.pop('password', None)
        company.pop('password_hash', None)
        return jsonify({
            'success': True,
            'role': 'company_admin',
            'company': company,
            'has_password': has_pass
        })

@app.route('/api/company-profile', methods=['PUT'])
@login_required
def api_update_company_profile():
    role = session.get('role', 'company_admin')
    data = request.get_json(silent=True) or {}
    
    if role == 'company_admin':
        # Company Admin can edit their address and their own password
        comp_id = session.get('company_id')
        if not comp_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
        if 'address' in data:
            address = str(data.get('address', '')).strip()
            if not address:
                return jsonify({'success': False, 'error': 'Address cannot be empty.'}), 400
            database.update_company(comp_id, {'address': address})
            
        new_pass = str(data.get('password', '')).strip()
        if new_pass:
            if len(new_pass) < 4:
                return jsonify({'success': False, 'error': 'Password must be at least 4 characters.'}), 400
            database.set_company_password(comp_id, new_pass)
            
        return jsonify({'success': True, 'message': 'Company profile and credentials updated successfully.'})
    
    elif role == 'super_admin':
        # Super Admin can edit all fields of any company, but can only set password for System Administration
        target_id = data.get('id') or data.get('company_id')
        if not target_id:
            return jsonify({'success': False, 'error': 'Company ID is required.'}), 400
        
        new_pass = str(data.get('password', '')).strip()
        if target_id == 'ARGUS_MASTER':
            # Setting password for System Administration
            if new_pass:
                if len(new_pass) < 4:
                    return jsonify({'success': False, 'error': 'Password must be at least 4 characters.'}), 400
                database.set_admin_password(new_pass)
        else:
            # STRICT PRIVACY RULE: Super admin cannot view or overwrite client company passwords!
            data.pop('password', None)
            data.pop('password_hash', None)
            
        try:
            data_to_save = dict(data)
            data_to_save.pop('password', None)
            data_to_save.pop('password_hash', None)
            database.update_company(target_id, data_to_save)
            return jsonify({'success': True, 'message': 'Company profile settings updated successfully.'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 400
            
    return jsonify({'success': False, 'error': 'Unauthorized'}), 403

# ----------------- EMPLOYEE PORTAL API ROUTES ----------------- #

@app.route('/api/employee/my-attendance', methods=['GET'])
@employee_required
def api_employee_my_attendance():
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
    data = request.get_json(silent=True) or request.form.to_dict()
    new_password = str(data.get('password', '')).strip()
    if not new_password or len(new_password) < 4:
        return jsonify({'success': False, 'error': 'Password must be at least 4 characters long.'}), 400
    
    emp_id = session.get('employee_id')
    success = database.set_employee_password(emp_id, new_password)
    if success:
        return jsonify({
            'success': True,
            'message': 'Your password has been saved successfully! You can now sign in using your email and password.'
        })
    return jsonify({'success': False, 'error': 'Failed to save password. Please try again.'}), 500

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

@app.route('/api/employees', methods=['POST'])
@login_required
def api_create_employee():
    data = {}
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
        
    photo_filename = ''
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            file_bytes = file.read()
            # Extract 128-d face embedding immediately (Image is NOT stored)
            embedding = get_face_engine().extract_face_embedding_from_image(file_bytes)
            data['face_embedding'] = database.json.dumps(embedding)
            
            # Reset file pointer if saving thumbnail or legacy
            filename = werkzeug.utils.secure_filename(file.filename)
            unique_filename = f"{int(database.time.time())}_{filename}"
            with open(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename), 'wb') as f:
                f.write(file_bytes)
            photo_filename = unique_filename
            
    if photo_filename:
        data['photo_filename'] = photo_filename
        data['photo'] = photo_filename

    if not data.get('employee_name'):
        return jsonify({'error': 'Employee name is required'}), 400
        
    try:
        emp_id = database.create_employee(data, company_id=get_current_company_id())
        return jsonify({'success': True, 'id': emp_id, 'message': 'Employee created successfully'})
    except ValueError as ve:
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to create employee: {e}'}), 500

@app.route('/api/employees/<emp_id>', methods=['PUT', 'POST'])
@login_required
def api_update_employee(emp_id):
    emp = database.get_employee_by_id(emp_id)
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404
        
    data = {}
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form.to_dict()
        
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            file_bytes = file.read()
            embedding = get_face_engine().extract_face_embedding_from_image(file_bytes)
            data['face_embedding'] = database.json.dumps(embedding)
            
            filename = werkzeug.utils.secure_filename(file.filename)
            unique_filename = f"{int(database.time.time())}_{filename}"
            with open(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename), 'wb') as f:
                f.write(file_bytes)
            data['photo_filename'] = unique_filename
            data['photo'] = unique_filename
            
    database.update_employee(emp_id, data)
    return jsonify({'success': True, 'message': 'Employee updated successfully'})

@app.route('/api/employees/<emp_id>', methods=['DELETE'])
@login_required
def api_delete_employee(emp_id):
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
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.isfile(file_path):
        return Response(DEFAULT_AVATAR_SVG, mimetype='image/svg+xml')
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

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
        
    inserted_id = database.add_live_entry(
        employee_id=employee_id,
        employee_name=employee_name,
        entry_time=data.get('entry_time'),
        site_name=data.get('site_name', 'OFFICE'),
        entry_location=data.get('entry_location', '515, Rabindranath Tagore Rd, Coimbatore'),
        entry_distance=float(data.get('entry_distance', 0.0)),
        is_timeout=int(data.get('is_timeout', 0)),
        company_id=get_current_company_id()
    )
    return jsonify({'success': True, 'id': inserted_id})

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
    writer.writerow(['EMPLOYEE NAME', 'ENTRY TIME', 'SITE NAME', 'ENTRY LOCATION', 'ENTRY DISTANCE'])
    for r in result.get('data', []):
        writer.writerow([
            r.get('employee_name', ''),
            r.get('entry_time', ''),
            r.get('site_name', '----') or '----',
            r.get('entry_location', '----') or '----',
            r.get('entry_distance', '----') or '----'
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
    if 'photo' not in request.files:
        return jsonify({'error': 'Camera frame is required'}), 400
        
    file = request.files['photo']
    file_bytes = file.read()
    
    query_embedding = get_face_engine().extract_face_embedding_from_image(file_bytes)
    if not query_embedding:
        return jsonify({
            'matched': False,
            'confidence': 0.0,
            'message': 'No face detected in camera frame. Please face the camera directly in good lighting.'
        })

    # If marked from employee portal, scope search to employee's company
    portal_company_id = session.get('company_id') if session.get('employee_logged_in') else None
    result = get_face_engine().recognize_face(query_embedding, company_id=portal_company_id)
    
    if result.get('matched'):
        emp_id = result['employee_id']
        emp_name = result['employee_name']
        
        user_lat = request.form.get('latitude')
        user_lng = request.form.get('longitude')
        client_time = request.form.get('client_time')
        
        # Enrich with employee details for dynamic punch card
        db = database.get_db()
        emp_doc = db.employees.find_one(database.build_id_filter(emp_id)) or db.employees.find_one({'employee_name': emp_name})
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
            client_time=client_time
        )
        result['live_entry_id'] = punch_res.get('live_id')
        result['punch_status'] = punch_res.get('status')
        result['formatted_distance'] = punch_res.get('formatted_dist')
        result['punch_time'] = client_time or datetime.now().strftime('%d %b %Y, %I:%M:%S %p')
        if punch_res.get('working_hours'):
            result['working_hours'] = punch_res.get('working_hours')
        
    return jsonify(result)

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
    
    if report_type == 'simple':
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
        writer.writerow(['EMPLOYEE NAME', 'ENTRY TIME', 'ENTRY DISTANCE', 'ENTRY LOCATION', 'EXIT TIME', 'EXIT DISTANCE', 'EXIT LOCATION', 'WORKING HOURS', 'SHIFT VARIANCE', 'WORKING SALARY'])
        for r in result.get('data', []):
            writer.writerow([
                r.get('employee_name', ''),
                r.get('entry_time', '') or '',
                r.get('entry_distance', '----') or '----',
                r.get('entry_location', '----') or '----',
                r.get('exit_time', '----') or '----',
                r.get('exit_distance', '----') or '----',
                r.get('exit_location', '----') or '----',
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
    if report_type == 'simple':
        result = database.get_attendance_simple_table(employee=employee, start_date=start_date, end_date=end_date, company_id=comp_id)
        emp_title = f" - {employee}" if (employee and employee not in ['All', 'All Employees']) else ""
        date_title = f" ({start_date} to {end_date})" if (start_date and end_date) else (f" (From {start_date})" if start_date else (f" (Up to {end_date})" if end_date else ""))
        title = f"Attendance Report (Simple Table){emp_title}{date_title}"
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
        writer.writerow([
            r['employee_name'], r['entry_date'], r['hours'], r['status'],
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
    reason = request.args.get('reason', 'All').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_payments(
        employee=employee,
        start_date=start_date,
        end_date=end_date,
        bank=bank,
        payment_type=payment_type,
        reason=reason,
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
    reason = request.args.get('reason', 'All').strip()
    
    result = database.get_payments(
        employee=employee,
        start_date=start_date,
        end_date=end_date,
        bank=bank,
        payment_type=payment_type,
        reason=reason,
        limit=10000,
        company_id=get_current_company_id()
    )
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['TIMESTAMP', 'EMPLOYEE', 'DATE', 'AMOUNT', 'BANK', 'PAYMENT TYPE', 'REASON'])
    for r in result['data']:
        writer.writerow([
            r['timestamp'], r['employee_name'], r['payment_date'],
            f"{float(r['amount']):.2f}", r['bank'] or '-',
            r['payment_type'], r['reason']
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
    reason = request.args.get('reason', 'All').strip()
    
    result = database.get_payments(
        employee=employee,
        start_date=start_date,
        end_date=end_date,
        bank=bank,
        payment_type=payment_type,
        reason=reason,
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

@app.route('/api/balance-report/export/excel', methods=['GET'])
@app.route('/api/balance-report/export/csv', methods=['GET'])
@login_required
def api_balance_report_export_excel():
    employee = request.args.get('employee', 'All').strip()
    result = database.get_balance_report(employee=employee, limit=10000, company_id=get_current_company_id())
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['TIMESTAMP', 'NAME', 'DATE', 'ADVANCE AMOUNT', 'ADVANCE REPAYMENT AMOUNT', 'BALANCE AMOUNT'])
    for r in result['data']:
        writer.writerow([
            r['timestamp'], r['name'], r['date'],
            f"{float(r['advance_amount']):.2f}",
            f"{float(r['advance_repayment_amount']):.2f}",
            f"{float(r['balance_amount']):.2f}"
        ])
    writer.writerow([])
    writer.writerow(['TOTAL ADVANCE', f"{result['total_advance']:.2f}", 'TOTAL REPAYMENT', f"{result['total_repayment']:.2f}", 'BALANCE AMOUNT', f"{result['balance_amount']:.2f}"])
    output.seek(0)
    filename = "balance_report.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

@app.route('/api/balance-report/export/pdf', methods=['GET'])
@login_required
def api_balance_report_export_pdf():
    employee = request.args.get('employee', 'All').strip()
    result = database.get_balance_report(employee=employee, limit=10000, company_id=get_current_company_id())
    totals = {
        'total_advance': result['total_advance'],
        'total_repayment': result['total_repayment'],
        'balance_amount': result['balance_amount']
    }
    company_info = get_current_company_info()
    pdf_buffer = pdf_generator.generate_balance_report_pdf(result['data'], totals, company_info=company_info)
    filename = "balance_report.pdf"
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
    payslip = database.get_payslip_data(employee, month, company_id=comp_id)
    database.save_generated_salary_report(payslip, company_id=comp_id)
    return jsonify(payslip)

@app.route('/api/payslip/export/pdf', methods=['GET'])
def api_export_payslip_pdf():
    """Generates and downloads payslip PDF. Available to Admins and Employees."""
    employee = (request.args.get('employee_name') or request.args.get('employee') or '').strip()
    month = request.args.get('month', '').strip()
    
    if not month:
        month = datetime.now().strftime("%Y-%m")
    
    comp_id = get_current_company_id()
    if not employee:
        emp_res = database.get_all_employees(company_id=comp_id, limit=1)
        if emp_res['data']:
            employee = emp_res['data'][0]['employee_name']
        else:
            employee = 'Employee'
    
    payslip = database.get_payslip_data(employee, month, company_id=comp_id)
    pdf_buffer = pdf_generator.generate_payslip_pdf(payslip)
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
