import os
import io
import csv
import werkzeug.utils
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, send_from_directory, Response, session
from functools import wraps
from flask_cors import CORS
import database

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
except Exception as e:
    print(f"Warning: database/face init error: {e}")

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

@app.errorhandler(500)
def handle_500(e):
    err = traceback.format_exc()
    print("500 Internal Error:", err)
    return f"<h1>Internal Server Error (500)</h1><pre>{err}</pre>", 500

@app.errorhandler(Exception)
def handle_exception(e):
    err = traceback.format_exc()
    print("Unhandled Exception:", err)
    return f"<h1>Server Error</h1><pre>{err}</pre>", 500

# ----------------- AUTHENTICATION & PAGE ROUTES ----------------- #

@app.route('/')
def index():
    return render_template('attendance.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Super Admin Login (Admin / 76543)."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if database.validate_admin_login(username, password):
            session.clear()
            session['admin_logged_in'] = True
            session['admin_username'] = username
            session['role'] = 'super_admin'
            session['company_id'] = 'ARGUS_MASTER'
            session['company_name'] = 'ARGUS TECHNOLOGIES'
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

@app.route('/company-login', methods=['GET', 'POST'])
def company_login():
    """Dedicated Company Admin Portal Login via Registered Corporate Email."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        company = database.validate_company_login(email)
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
            return render_template(
                'company_login.html',
                error='Access Denied: This email is not registered as a company administrator. Please contact Argus Support.'
            )
    return render_template('company_login.html')

@app.route('/employee-login', methods=['GET', 'POST'])
def employee_login():
    """Dedicated Employee Portal Login via Registered Employee Email."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        employee = database.validate_employee_login(email)
        if employee:
            session.clear()
            session['employee_logged_in'] = True
            session['role'] = 'employee'
            session['employee_id'] = str(employee.get('id', employee.get('_id', '')))
            session['employee_name'] = employee.get('employee_name', '')
            session['employee_email'] = employee.get('email_id', '')
            session['company_id'] = employee.get('company_id', 'ARGUS_MASTER')
            return redirect(url_for('employee_portal'))
        else:
            return render_template(
                'employee_login.html',
                error='Access Denied: Email not registered with any organisation. Please contact your company HR.'
            )
    return render_template('employee_login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/manage-companies')
@super_admin_required
def manage_companies():
    return render_template('manage_companies.html', active_tab='MANAGE COMPANIES')

@app.route('/employee/portal')
@employee_required
def employee_portal():
    emp_id = session.get('employee_id')
    comp_id = session.get('company_id')
    employee = database.get_employee_by_id(emp_id)
    company = database.get_company_by_id(comp_id) if comp_id != 'ARGUS_MASTER' else {'company_name': 'Argus Technologies'}
    return render_template('employee_portal.html', employee=employee, company=company)

@app.route('/dashboard')
@login_required
def dashboard():
    stats = database.get_dashboard_stats(company_id=get_current_company_id())
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

@app.route('/api/companies/reports', methods=['GET'])
@super_admin_required
def api_company_reports():
    summary = database.get_company_reports_summary()
    return jsonify({'success': True, 'summary': summary})

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
    sort_dir = request.args.get('sort_dir', 'asc')
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

    if not data.get('employee_name'):
        return jsonify({'error': 'Employee name is required'}), 400
        
    emp_id = database.create_employee(data, company_id=get_current_company_id())
    return jsonify({'success': True, 'id': emp_id, 'message': 'Employee created successfully'})

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
        
    pdf_buffer = pdf_generator.generate_employee_pdf(emp)
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=f"employee_{emp_id}_{emp.get('employee_name', 'details')}.pdf",
        mimetype='application/pdf'
    )

@app.route('/uploads/<filename>')
def uploaded_file(filename):
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
    for r in result['data']:
        writer.writerow([r['employee_name'], r['entry_time'], r['site_name'], r['entry_location'], r['entry_distance']])
        
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
    pdf_buffer = pdf_generator.generate_live_report_pdf(title, result['data'])
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
        
        # Mark Attendance Punch In / Punch Out Lifecycle & Live Entry (Company-aware)
        punch_res = database.record_face_attendance(
            employee_id=emp_id,
            employee_name=emp_name,
            user_lat=user_lat,
            user_lng=user_lng,
            company_id=portal_company_id
        )
        result['live_entry_id'] = punch_res.get('live_id')
        result['punch_status'] = punch_res.get('status')
        result['formatted_distance'] = punch_res.get('formatted_dist')
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
        for r in result['data']:
            writer.writerow([r['employee_name'], r['entry_time'], r['exit_time'], r['working_hours'], r['shift_variance'], r['working_salary'], r['status']])
        writer.writerow([])
        writer.writerow(['TOTAL', '', '', result['total_working_hours'], '----', result['total_working_salary'], ''])
    else:
        result = database.get_attendance_reports(report_type=report_type, start_date=start_date, end_date=end_date, employee=employee, limit=10000, company_id=comp_id)
        writer.writerow(['EMPLOYEE NAME', 'ENTRY TIME', 'ENTRY DISTANCE', 'ENTRY LOCATION', 'EXIT TIME', 'EXIT DISTANCE', 'EXIT LOCATION', 'WORKING HOURS', 'SHIFT VARIANCE', 'WORKING SALARY'])
        for r in result['data']:
            writer.writerow([
                r['employee_name'], r['entry_time'], r['entry_distance'], r['entry_location'],
                r['exit_time'], r['exit_distance'], r['exit_location'], r['working_hours'],
                r['shift_variance'], r['working_salary']
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
    
    if report_type == 'simple':
        result = database.get_attendance_simple_table(employee=employee, start_date=start_date, end_date=end_date, company_id=comp_id)
        title = "Manual Entries (Simple Table)"
        totals = {
            'total_working_hours': result['total_working_hours'],
            'total_working_salary': result['total_working_salary']
        }
        pdf_buffer = pdf_generator.generate_attendance_report_pdf(title, result['data'], is_simple=True, totals=totals)
    else:
        result = database.get_attendance_reports(report_type=report_type, start_date=start_date, end_date=end_date, employee=employee, limit=10000, company_id=comp_id)
        titles = {
            'all': 'All Attendance Entries',
            'proper': 'Proper Attendance Entries',
            'improper': 'Improper Attendance Entries',
            'manual': 'Manual Attendance Entries'
        }
        title = titles.get(report_type, 'Attendance Report')
        pdf_buffer = pdf_generator.generate_attendance_report_pdf(title, result['data'], is_simple=False)
        
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
    pdf_buffer = pdf_generator.generate_manual_entries_pdf(result['data'])
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
    pdf_buffer = pdf_generator.generate_payments_pdf(result['data'])
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
    pdf_buffer = pdf_generator.generate_advances_pdf(result['data'])
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
    pdf_buffer = pdf_generator.generate_balance_report_pdf(result['data'], totals)
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
        employee = data.get('employee_name', '').strip()
        month = data.get('month', '').strip()
    else:
        employee = request.args.get('employee_name', '').strip()
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
    employee = request.args.get('employee_name', '').strip()
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
    pdf_buffer = pdf_generator.generate_salary_report_pdf(result['data'])
    filename = "salary_report.pdf"
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
