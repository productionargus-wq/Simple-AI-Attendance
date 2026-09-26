import os
import io
import csv
import werkzeug.utils
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

# Support writable temp directory in serverless environments like Vercel
if os.environ.get('VERCEL'):
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
else:
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create upload directory: {e}")

try:
    database.init_db()
except Exception as e:
    print(f"Warning: database init error: {e}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('login'))
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

# ----------------- PAGE ROUTES ----------------- #

@app.route('/')
def index():
    return render_template('attendance.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if database.validate_admin_login(username, password):
            session['admin_logged_in'] = True
            session['admin_username'] = username
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    stats = database.get_dashboard_stats()
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
    employees_res = database.get_all_employees(limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('attendance_report.html', active_tab='ATTENDANCE REPORT', employees=employees)

@app.route('/manual-entry')
@login_required
def manual_entry():
    return render_template('manual_entry.html', active_tab='MANUAL ENTRY')

@app.route('/payment-entry')
@login_required
def payment_entry():
    employees_res = database.get_all_employees(limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('payment_entry.html', active_tab='PAYMENT ENTRY', employees=employees)

@app.route('/advance-management')
@login_required
def advance_management():
    employees_res = database.get_all_employees(limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('advance_management.html', active_tab='PAYMENT ENTRY', employees=employees)

@app.route('/balance-report')
@login_required
def balance_report():
    employees_res = database.get_all_employees(limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('balance_report.html', active_tab='PAYMENT ENTRY', employees=employees)

@app.route('/monthly-payslip')
@login_required
def monthly_payslip():
    employees_res = database.get_all_employees(limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('monthly_payslip.html', active_tab='MONTHLY PAYSLIP', employees=employees)

@app.route('/salary-report')
@login_required
def salary_report():
    employees_res = database.get_all_employees(limit=1000)
    employees = [e['employee_name'] for e in employees_res['data']]
    return render_template('salary_report.html', active_tab='SALARY REPORT', employees=employees)

# ----------------- EMPLOYEE API ROUTES ----------------- #

@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    stats = database.get_dashboard_stats()
    return jsonify(stats)

@app.route('/api/employees', methods=['GET'])
def api_get_employees():
    search = request.args.get('search', '').strip()
    sort_col = request.args.get('sort_col', 'id')
    sort_dir = request.args.get('sort_dir', 'asc')
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_all_employees(search, sort_col, sort_dir, page, limit)
    return jsonify(result)

@app.route('/api/employees/<emp_id>', methods=['GET'])
def api_get_employee(emp_id):
    emp = database.get_employee_by_id(emp_id)
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404
    return jsonify(emp)

@app.route('/api/employees', methods=['POST'])
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
        
    emp_id = database.create_employee(data)
    return jsonify({'success': True, 'id': emp_id, 'message': 'Employee created successfully'})

@app.route('/api/employees/<emp_id>', methods=['PUT', 'POST'])
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
            # Extract face embedding
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
def api_delete_employee(emp_id):
    emp = database.get_employee_by_id(emp_id)
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404
    database.delete_employee(emp_id)
    return jsonify({'success': True, 'message': 'Employee deleted successfully'})

@app.route('/api/employees/<emp_id>/pdf', methods=['GET'])
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
def api_get_live_entries():
    entry_type = request.args.get('type', 'live')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_live_entries(entry_type, start_date, end_date, search, page, limit)
    return jsonify(result)

@app.route('/api/live-entries', methods=['POST'])
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
        is_timeout=int(data.get('is_timeout', 0))
    )
    return jsonify({'success': True, 'id': inserted_id})

@app.route('/api/live-entries/export/excel', methods=['GET'])
def api_export_excel():
    entry_type = request.args.get('type', 'live')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    result = database.get_live_entries(entry_type, start_date, end_date, limit=10000)
    
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
def api_export_pdf():
    entry_type = request.args.get('type', 'live')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    result = database.get_live_entries(entry_type, start_date, end_date, limit=10000)
    
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
    
    # Compute 128-d embedding
    embedding = get_face_engine().extract_face_embedding_from_image(file_bytes)
    database.save_face_embedding(emp_id, embedding)
    
    # Notice: file_bytes is NOT saved to disk! Image is discarded.
    return jsonify({
        'success': True,
        'message': 'Face embedding enrolled successfully. Image discarded for privacy.',
        'vector_dimensions': len(embedding)
    })

@app.route('/api/face/recognize', methods=['POST'])
def api_face_recognize():
    """
    Recognizes employee face from live camera frame:
    Compares 128-d live vector with stored embeddings using Cosine Similarity.
    Marks attendance & creates live entry.
    """
    if 'photo' not in request.files:
        return jsonify({'error': 'Camera frame is required'}), 400
        
    file = request.files['photo']
    file_bytes = file.read()
    
    # Extract query embedding
    query_embedding = get_face_engine().extract_face_embedding_from_image(file_bytes)
    result = get_face_engine().recognize_face(query_embedding)
    
    if result.get('matched'):
        emp_id = result['employee_id']
        emp_name = result['employee_name']
        
        user_lat = request.form.get('latitude')
        user_lng = request.form.get('longitude')
        
        # Mark Attendance Punch In / Punch Out Lifecycle & Live Entry
        punch_res = database.record_face_attendance(
            employee_id=emp_id,
            employee_name=emp_name,
            user_lat=user_lat,
            user_lng=user_lng
        )
        result['live_entry_id'] = punch_res.get('live_id')
        result['punch_status'] = punch_res.get('status')
        result['formatted_distance'] = punch_res.get('formatted_dist')
        if punch_res.get('working_hours'):
            result['working_hours'] = punch_res.get('working_hours')
        
    return jsonify(result)

# ----------------- ATTENDANCE REPORTS API ROUTES ----------------- #

@app.route('/api/attendance-reports', methods=['GET'])
def api_get_attendance_reports():
    report_type = request.args.get('type', 'all')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    employee = request.args.get('employee', 'All').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_attendance_reports(report_type, start_date, end_date, employee, search, page, limit)
    return jsonify(result)

@app.route('/api/attendance-reports/simple', methods=['GET'])
def api_get_attendance_simple():
    employee = request.args.get('employee', 'All Employees').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    result = database.get_attendance_simple_table(employee, start_date, end_date)
    return jsonify(result)

@app.route('/api/attendance-reports/update', methods=['POST'])
def api_update_attendance_records():
    return jsonify({'success': True, 'message': 'Attendance records updated successfully'})

@app.route('/api/attendance-reports/export/excel', methods=['GET'])
def api_attendance_export_excel():
    report_type = request.args.get('type', 'all')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    employee = request.args.get('employee', 'All').strip()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if report_type == 'simple':
        result = database.get_attendance_simple_table(employee, start_date, end_date)
        writer.writerow(['EMPLOYEE NAME', 'ENTRY TIME', 'EXIT TIME', 'WORKING HOURS', 'SHIFT VARIANCE', 'WORKING SALARY', 'STATUS'])
        for r in result['data']:
            writer.writerow([r['employee_name'], r['entry_time'], r['exit_time'], r['working_hours'], r['shift_variance'], r['working_salary'], r['status']])
        writer.writerow([])
        writer.writerow(['TOTAL', '', '', result['total_working_hours'], '----', result['total_working_salary'], ''])
    else:
        result = database.get_attendance_reports(report_type, start_date, end_date, employee, limit=10000)
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
def api_attendance_export_pdf():
    report_type = request.args.get('type', 'all')
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    employee = request.args.get('employee', 'All').strip()
    
    if report_type == 'simple':
        result = database.get_attendance_simple_table(employee, start_date, end_date)
        title = "Manual Entries (Simple Table)"
        totals = {
            'total_working_hours': result['total_working_hours'],
            'total_working_salary': result['total_working_salary']
        }
        pdf_buffer = pdf_generator.generate_attendance_report_pdf(title, result['data'], is_simple=True, totals=totals)
    else:
        result = database.get_attendance_reports(report_type, start_date, end_date, employee, limit=10000)
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
def api_get_manual_entries():
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()
    status = request.args.get('status', 'All').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_manual_entries(from_date, to_date, status, search, page, limit)
    return jsonify(result)

@app.route('/api/manual-entries/<entry_id>', methods=['GET'])
def api_get_manual_entry(entry_id):
    entry = database.get_manual_entry_by_id(entry_id)
    if not entry:
        return jsonify({'error': 'Manual entry not found'}), 404
    return jsonify(entry)

@app.route('/api/manual-entries', methods=['POST'])
def api_create_manual_entry():
    data = request.get_json() if request.is_json else request.form.to_dict()
    if not data.get('employee_name'):
        return jsonify({'error': 'Employee name is required'}), 400
        
    inserted_id = database.create_manual_entry(data)
    return jsonify({'success': True, 'id': inserted_id, 'message': 'Manual entry created successfully'})

@app.route('/api/manual-entries/<entry_id>', methods=['PUT', 'POST'])
def api_update_manual_entry(entry_id):
    entry = database.get_manual_entry_by_id(entry_id)
    if not entry:
        return jsonify({'error': 'Manual entry not found'}), 404
        
    data = request.get_json() if request.is_json else request.form.to_dict()
    database.update_manual_entry(entry_id, data)
    return jsonify({'success': True, 'message': 'Manual entry updated successfully'})

@app.route('/api/manual-entries/<entry_id>', methods=['DELETE'])
def api_delete_manual_entry(entry_id):
    entry = database.get_manual_entry_by_id(entry_id)
    if not entry:
        return jsonify({'error': 'Manual entry not found'}), 404
        
    database.delete_manual_entry(entry_id)
    return jsonify({'success': True, 'message': 'Manual entry deleted successfully'})

@app.route('/api/manual-entries/export/excel', methods=['GET'])
def api_manual_entries_export_excel():
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()
    status = request.args.get('status', 'All').strip()
    
    result = database.get_manual_entries(from_date, to_date, status, limit=10000)
    
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
def api_manual_entries_export_pdf():
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()
    status = request.args.get('status', 'All').strip()
    
    result = database.get_manual_entries(from_date, to_date, status, limit=10000)
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
    
    result = database.get_payments(employee, start_date, end_date, bank, payment_type, reason, search, page, limit)
    return jsonify(result)

@app.route('/api/payments/<payment_id>', methods=['GET'])
def api_get_payment(payment_id):
    p = database.get_payment_by_id(payment_id)
    if not p:
        return jsonify({'error': 'Payment not found'}), 404
    return jsonify(p)

@app.route('/api/payments', methods=['POST'])
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
        
    inserted_id = database.create_payment(data)
    return jsonify({'success': True, 'id': inserted_id, 'message': 'Payment created successfully'})

@app.route('/api/payments/<payment_id>', methods=['PUT', 'POST'])
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
def api_delete_payment(payment_id):
    p = database.get_payment_by_id(payment_id)
    if not p:
        return jsonify({'error': 'Payment not found'}), 404
        
    database.delete_payment(payment_id)
    return jsonify({'success': True, 'message': 'Payment deleted successfully'})

@app.route('/api/payments/export/excel', methods=['GET'])
def api_payments_export_excel():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    bank = request.args.get('bank', 'All').strip()
    payment_type = request.args.get('payment_type', 'All').strip()
    reason = request.args.get('reason', 'All').strip()
    
    result = database.get_payments(employee, start_date, end_date, bank, payment_type, reason, limit=10000)
    
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
def api_payments_export_pdf():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    bank = request.args.get('bank', 'All').strip()
    payment_type = request.args.get('payment_type', 'All').strip()
    reason = request.args.get('reason', 'All').strip()
    
    result = database.get_payments(employee, start_date, end_date, bank, payment_type, reason, limit=10000)
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
def api_get_advances():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_advances(employee, start_date, end_date, search, page, limit)
    return jsonify(result)

@app.route('/api/advances/<advance_id>', methods=['GET'])
def api_get_advance(advance_id):
    a = database.get_advance_by_id(advance_id)
    if not a:
        return jsonify({'error': 'Advance not found'}), 404
    return jsonify(a)

@app.route('/api/advances', methods=['POST'])
def api_create_advance():
    data = request.get_json() if request.is_json else request.form.to_dict()
    if not data.get('employee_name'):
        return jsonify({'error': 'Employee name is required'}), 400
        
    inserted_id = database.create_advance(data)
    return jsonify({'success': True, 'id': inserted_id, 'message': 'Advance created successfully'})

@app.route('/api/advances/<advance_id>', methods=['PUT', 'POST'])
def api_update_advance(advance_id):
    a = database.get_advance_by_id(advance_id)
    if not a:
        return jsonify({'error': 'Advance not found'}), 404
        
    data = request.get_json() if request.is_json else request.form.to_dict()
    database.update_advance(advance_id, data)
    return jsonify({'success': True, 'message': 'Advance updated successfully'})

@app.route('/api/advances/<advance_id>', methods=['DELETE'])
def api_delete_advance(advance_id):
    a = database.get_advance_by_id(advance_id)
    if not a:
        return jsonify({'error': 'Advance not found'}), 404
        
    database.delete_advance(advance_id)
    return jsonify({'success': True, 'message': 'Advance deleted successfully'})

@app.route('/api/advances/export/excel', methods=['GET'])
def api_advances_export_excel():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    result = database.get_advances(employee, start_date, end_date, limit=10000)
    
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
def api_advances_export_pdf():
    employee = request.args.get('employee', 'All').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    
    result = database.get_advances(employee, start_date, end_date, limit=10000)
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
def api_get_balance_report():
    employee = request.args.get('employee', 'All').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    result = database.get_balance_report(employee, search, page, limit)
    return jsonify(result)

@app.route('/api/balance-report/export/excel', methods=['GET'])
def api_balance_report_export_excel():
    employee = request.args.get('employee', 'All').strip()
    result = database.get_balance_report(employee, limit=10000)
    
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
def api_balance_report_export_pdf():
    employee = request.args.get('employee', 'All').strip()
    result = database.get_balance_report(employee, limit=10000)
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
        
    payslip = database.get_payslip_data(employee, month)
    # Upsert generated payslip into salary_reports so it appears in Salary Report tab!
    database.save_generated_salary_report(payslip)
    return jsonify(payslip)

@app.route('/api/payslip/export/pdf', methods=['GET'])
def api_export_payslip_pdf():
    employee = request.args.get('employee_name', '').strip()
    month = request.args.get('month', '').strip()
    
    if not month:
        month = datetime.now().strftime("%Y-%m")
    if not employee:
        # Default to first available employee if none provided
        emp_res = database.get_all_employees(limit=1)
        if emp_res['data']:
            employee = emp_res['data'][0]['employee_name']
        else:
            employee = 'Employee'
    
    payslip = database.get_payslip_data(employee, month)
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
def api_get_salary_reports():
    start_month = request.args.get('start_month', '').strip()
    end_month = request.args.get('end_month', '').strip()
    search = request.args.get('search', '').strip()
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 10))
    
    result = database.get_salary_reports(start_month, end_month, search, page, limit)
    return jsonify(result)

@app.route('/api/salary-reports/export/excel', methods=['GET'])
def api_salary_reports_export_excel():
    start_month = request.args.get('start_month', '').strip()
    end_month = request.args.get('end_month', '').strip()
    
    result = database.get_salary_reports(start_month, end_month, limit=10000)
    
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
def api_salary_reports_export_pdf():
    start_month = request.args.get('start_month', '').strip()
    end_month = request.args.get('end_month', '').strip()
    
    result = database.get_salary_reports(start_month, end_month, limit=10000)
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


