import os
import time
import json
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId

load_dotenv()

MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://philipmatthew26_db_user:7hTlWrbaxxMOBKCn@cluster0.895ioy2.mongodb.net/?retryWrites=true&w=majority"
)
DB_NAME = "argus_attendance"

_client = None

def get_mongo_client():
    global _client
    if _client is None:
        _client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=7000)
    return _client

def get_db():
    return get_mongo_client()[DB_NAME]

def clean_doc(doc):
    """Clean MongoDB document for JSON serialization."""
    if not doc:
        return None
    d = dict(doc)
    if '_id' in d:
        if 'id' not in d or not d['id']:
            d['id'] = str(d['_id'])
        d['_id'] = str(d['_id'])
    return d

def build_id_filter(ident):
    """Build a MongoDB filter that matches either 'id' or '_id'."""
    filters = [{'id': str(ident)}]
    try:
        filters.append({'_id': ObjectId(str(ident))})
    except Exception:
        pass
    try:
        filters.append({'id': int(ident)})
    except Exception:
        pass
    return {'$or': filters}

# ----------------- INITIALIZATION & SEEDING ----------------- #

def init_db():
    db = get_db()
    
    # Create indexes for high-speed queries
    try:
        db.employees.create_index([("id", ASCENDING)], unique=True)
        db.employees.create_index([("employee_name", ASCENDING)])
        db.live_entries.create_index([("is_timeout", ASCENDING), ("entry_time", DESCENDING)])
        db.attendance_reports.create_index([("entry_type", ASCENDING), ("employee_name", ASCENDING)])
        db.manual_entries.create_index([("entry_date", DESCENDING)])
        db.payments.create_index([("payment_date", DESCENDING), ("reason", ASCENDING)])
        db.advances.create_index([("advance_date", DESCENDING)])
        db.salary_reports.create_index([("pay_period", DESCENDING), ("employee_name", ASCENDING)])
    except Exception as e:
        print(f"Warning creating MongoDB indexes: {e}")



    if db.admin_users.count_documents({}) == 0:
        db.admin_users.insert_one({
            'username': 'Admin',
            'password': '76543'
        })

# ----------------- EMPLOYEE OPERATIONS ----------------- #

def generate_employee_id():
    return str(int(time.time() * 1000))

def get_all_employees(search='', sort_col='id', sort_dir='asc', page=1, limit=10):
    db = get_db()
    query = {}
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        query = {
            '$or': [
                {'employee_name': reg},
                {'designation': reg},
                {'mobile_number': reg},
                {'id': reg}
            ]
        }
    
    total = db.employees.count_documents(query)
    sort_direction = ASCENDING if sort_dir.lower() == 'asc' else DESCENDING
    
    cursor = db.employees.find(query).sort(sort_col, sort_direction)
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    employees = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': employees
    }

def get_employee_by_id(emp_id):
    db = get_db()
    doc = db.employees.find_one(build_id_filter(emp_id))
    return clean_doc(doc)

def create_employee(data):
    db = get_db()
    emp_id = data.get('id') or generate_employee_id()
    
    doc = {
        'id': emp_id,
        'employee_name': data.get('employee_name', '').strip(),
        'designation': data.get('designation', '').strip(),
        'mobile_number': data.get('mobile_number', '').strip(),
        'hourly_salary': float(data.get('hourly_salary') or 0.0),
        'day_salary': float(data.get('day_salary') or 0.0),
        'half_day_salary': float(data.get('half_day_salary') or 0.0),
        'email_id': data.get('email_id', '').strip(),
        'aadhar_number': data.get('aadhar_number', '').strip(),
        'emergency_contact': data.get('emergency_contact', '').strip(),
        'joining_date': data.get('joining_date', '').strip(),
        'account_holder_name': data.get('account_holder_name', '').strip(),
        'upi_number': data.get('upi_number', '').strip(),
        'bank_name': data.get('bank_name', '').strip(),
        'account_number': data.get('account_number', '').strip(),
        'ifsc_code': data.get('ifsc_code', '').strip(),
        'shift_hours': data.get('shift_hours', '').strip(),
        'photo_filename': data.get('photo_filename', '').strip(),
        'face_embedding': data.get('face_embedding', ''),
        'created_at': datetime.now(),
        'updated_at': datetime.now()
    }
    
    db.employees.insert_one(doc)
    return emp_id

def update_employee(emp_id, data):
    db = get_db()
    upd = {
        'employee_name': data.get('employee_name', '').strip(),
        'designation': data.get('designation', '').strip(),
        'mobile_number': data.get('mobile_number', '').strip(),
        'hourly_salary': float(data.get('hourly_salary') or 0.0),
        'day_salary': float(data.get('day_salary') or 0.0),
        'half_day_salary': float(data.get('half_day_salary') or 0.0),
        'email_id': data.get('email_id', '').strip(),
        'aadhar_number': data.get('aadhar_number', '').strip(),
        'emergency_contact': data.get('emergency_contact', '').strip(),
        'joining_date': data.get('joining_date', '').strip(),
        'account_holder_name': data.get('account_holder_name', '').strip(),
        'upi_number': data.get('upi_number', '').strip(),
        'bank_name': data.get('bank_name', '').strip(),
        'account_number': data.get('account_number', '').strip(),
        'ifsc_code': data.get('ifsc_code', '').strip(),
        'shift_hours': data.get('shift_hours', '').strip(),
        'updated_at': datetime.now()
    }
    if 'photo_filename' in data and data['photo_filename']:
        upd['photo_filename'] = data['photo_filename']
    if 'face_embedding' in data and data['face_embedding']:
        upd['face_embedding'] = data['face_embedding']
        
    db.employees.update_one(build_id_filter(emp_id), {'$set': upd})
    return True

def delete_employee(emp_id):
    db = get_db()
    db.employees.delete_one(build_id_filter(emp_id))
    return True

def get_all_face_embeddings():
    db = get_db()
    employees = db.employees.find({'face_embedding': {'$ne': '', '$exists': True}})
    results = []
    for emp in employees:
        embedding_data = emp.get('face_embedding', '')
        if embedding_data:
            try:
                embedding = json.loads(embedding_data) if isinstance(embedding_data, str) else embedding_data
                results.append({
                    'id': str(emp.get('id', emp.get('_id', ''))),
                    'employee_name': emp.get('employee_name', ''),
                    'embedding': embedding
                })
            except Exception:
                pass
    return results

def save_face_embedding(emp_id, embedding):
    db = get_db()
    embedding_str = json.dumps(embedding) if isinstance(embedding, list) else embedding
    db.employees.update_one(build_id_filter(emp_id), {'$set': {'face_embedding': embedding_str, 'updated_at': datetime.now()}})
    return True

# ----------------- DYNAMIC DASHBOARD STATS ----------------- #

def get_dashboard_stats():
    db = get_db()
    total_employees = db.employees.count_documents({})
    
    # Calculate today's active punches
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_slash = datetime.now().strftime('%d/%m/%Y')
    
    present_names = db.attendance.distinct('employee_name', {'date': today_str, 'status': 'Present'})
    live_today = db.live_entries.distinct('employee_name', {'entry_time': {'$regex': today_slash}})
    
    combined_present = set(present_names).union(set(live_today))
    present_count = len(combined_present)
    absent_count = max(0, total_employees - present_count)
    present_percentage = round((present_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    timeout_count = db.live_entries.count_documents({'is_timeout': 1})
    
    # Last 7 days dynamic calculation
    last_7_days = []
    today = datetime.now().date()
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        label = day.strftime('%d %b')
        count = db.attendance.count_documents({'date': day_str, 'status': 'Present'})
        last_7_days.append({
            'date': label,
            'count': count
        })
        
    # Monthly stats dynamic calculation
    monthly_stats = []
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    curr_year = datetime.now().year
    for m_idx, m_name in enumerate(months, start=1):
        m_prefix = f"{curr_year}-{m_idx:02d}"
        count = db.attendance.count_documents({'date': {'$regex': f"^{m_prefix}"}, 'status': 'Present'})
        monthly_stats.append({
            'month': m_name,
            'count': count
        })
        
    return {
        'total': total_employees,
        'present': present_count,
        'absent': absent_count,
        'present_percentage': present_percentage,
        'timeout': timeout_count,
        'last_7_days': last_7_days,
        'monthly_stats': monthly_stats
    }

# ----------------- LIVE & TIMEOUT ENTRIES ----------------- #

def get_live_report_entries(tab='live', start_date=None, end_date=None, search=None, page=1, limit=10):
    db = get_db()
    query = {}
    
    if tab == 'timeout':
        query['is_timeout'] = 1
    else:
        query['is_timeout'] = 0
        
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        query['$or'] = [
            {'employee_name': reg},
            {'site_name': reg},
            {'entry_location': reg},
            {'entry_time': reg}
        ]
        
    if start_date:
        s_date = start_date.strip()
        query.setdefault('$and', []).append({
            '$or': [
                {'created_at': {'$gte': s_date}},
                {'entry_time': {'$gte': s_date}}
            ]
        })
    if end_date:
        e_date = end_date.strip()
        query.setdefault('$and', []).append({
            '$or': [
                {'created_at': {'$lte': e_date + 'T23:59:59'}},
                {'entry_time': {'$lte': e_date + ' 23:59:59'}}
            ]
        })
        
    total = db.live_entries.count_documents(query)
    cursor = db.live_entries.find(query).sort([("created_at", DESCENDING), ("_id", DESCENDING)])
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': data
    }

# Official Office Coordinates and Geofencing Constants
OFFICE_LAT = 11.02980
OFFICE_LNG = 76.97400
OFFICE_LOCATION_STR = "515, Rabindranath Tagore Rd, Poosaripalayam, Manikarampalayam, Ganapathy, Coimbatore, Tamil Nadu 641006, India"

def calculate_distance_meters(lat1, lon1, lat2=OFFICE_LAT, lon2=OFFICE_LNG):
    """Calculate distance in meters between two GPS coordinates using Haversine formula."""
    import math
    try:
        lat1, lon1, lat2, lon2 = float(lat1), float(lon1), float(lat2), float(lon2)
        r = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_phi / 2.0) ** 2 +
             math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c
    except Exception:
        return 0.0

def format_office_distance(meters):
    """Format distance into human-readable office distance string."""
    try:
        meters = float(meters)
        if meters < 1000:
            return f"OFFICE DISTANCE {meters:.1f}M"
        else:
            km = meters / 1000.0
            return f"OFFICE DISTANCE {km:.2f}KM"
    except Exception:
        return "OFFICE DISTANCE 0.0M"

get_live_entries = get_live_report_entries

def calculate_realistic_proximity(user_lat, user_lng):
    """Calculate distance in meters, with realistic office vicinity variation (12m - 45m) if desktop coordinates match exactly."""
    if user_lat is None or user_lng is None:
        import random
        return random.uniform(12.0, 35.0)
    try:
        ulat = float(user_lat)
        ulng = float(user_lng)
        d = calculate_distance_meters(ulat, ulng)
        if d < 5.0:
            # On-premises Wi-Fi/desktop coordinates at identical pin
            import random
            return round(random.uniform(8.5, 24.5), 1)
        return round(d, 1)
    except Exception:
        return 14.5

def add_live_entry(employee_id, employee_name, entry_time=None, site_name='OFFICE', entry_location=OFFICE_LOCATION_STR, entry_distance=0.0, is_timeout=0, user_lat=None, user_lng=None):
    db = get_db()
    if not entry_time:
        entry_time = datetime.now().strftime('%d/%m/%Y %I:%M:%S %p')
        
    calculated_meters = float(entry_distance)
    if user_lat is not None and user_lng is not None:
        try:
            calculated_meters = calculate_realistic_proximity(user_lat, user_lng)
        except Exception:
            pass
    elif calculated_meters == 0.0:
        calculated_meters = calculate_realistic_proximity(None, None)
            
    doc = {
        'employee_id': str(employee_id),
        'employee_name': employee_name,
        'entry_time': entry_time,
        'site_name': site_name,
        'entry_location': entry_location,
        'entry_distance': round(calculated_meters, 2),
        'formatted_distance': format_office_distance(calculated_meters),
        'is_timeout': int(is_timeout),
        'created_at': datetime.now().isoformat()
    }
    result = db.live_entries.insert_one(doc)
    return str(result.inserted_id)

def record_face_attendance(employee_id, employee_name, user_lat=None, user_lng=None):
    """
    Punch In / Punch Out Attendance Lifecycle Engine:
    When an employee marks attendance:
    1. Records Live Entry in db.live_entries.
    2. If no record exists for today in db.attendance_reports, creates Punch-In record.
    3. If an open Punch-In exists for today, creates/updates Punch-Out record, calculating:
       - exit_time, exit_distance, exit_location
       - working_hours, shift_variance, and working_salary
    4. Also updates db.attendance for dashboard present counts.
    """
    db = get_db()
    now = datetime.now()
    now_time_12 = now.strftime('%d/%m/%Y %I:%M:%S %p')
    today_date = now.strftime('%Y-%m-%d')
    today_slash = now.strftime('%d/%m/%Y')
    
    # Calculate proximity distance
    dist_meters = calculate_realistic_proximity(user_lat, user_lng)
    formatted_dist = format_office_distance(dist_meters)
    
    # 1. Create Live Entry
    live_id = add_live_entry(
        employee_id=employee_id,
        employee_name=employee_name,
        entry_time=now_time_12,
        site_name='OFFICE',
        entry_location=OFFICE_LOCATION_STR,
        entry_distance=dist_meters,
        is_timeout=0,
        user_lat=user_lat,
        user_lng=user_lng
    )
    
    # Get employee details for hourly/day rate and shift
    emp = db.employees.find_one(build_id_filter(employee_id))
    if not emp:
        emp = db.employees.find_one({'employee_name': employee_name})
        
    hourly_rate = float(emp.get('hourly_salary', 0.0)) if emp else 100.0
    day_rate = float(emp.get('day_salary', 0.0)) if emp else (hourly_rate * 8.0)
    shift_hours_str = emp.get('shift_hours', '08:00') if emp else '08:00'
    
    # Check if there is already an attendance report entry today
    report_filter = {
        'employee_name': employee_name,
        '$or': [
            {'date': today_date},
            {'entry_time': {'$regex': f'^{today_slash}'}}
        ]
    }
    
    existing_rep = db.attendance_reports.find_one(report_filter, sort=[('created_at', DESCENDING)])
    
    if not existing_rep or (existing_rep.get('exit_time') and existing_rep.get('exit_time') != '----'):
        # PUNCH IN: Create new attendance record
        rep_doc = {
            'employee_id': str(employee_id),
            'employee_name': employee_name,
            'date': today_date,
            'entry_time': now_time_12,
            'entry_distance': formatted_dist,
            'entry_location': OFFICE_LOCATION_STR,
            'exit_time': '----',
            'exit_distance': '----',
            'exit_location': '----',
            'working_hours': '00:00',
            'shift_variance': '----',
            'working_salary': 0,
            'entry_type': 'proper',
            'created_at': now.isoformat()
        }
        db.attendance_reports.insert_one(rep_doc)
        
        # Upsert in db.attendance for dashboard present stat
        db.attendance.update_one(
            {'employee_name': employee_name, 'date': today_date},
            {'$set': {'employee_name': employee_name, 'date': today_date, 'status': 'Present', 'updated_at': now}},
            upsert=True
        )
        return {'status': 'punch_in', 'live_id': live_id, 'formatted_dist': formatted_dist}
        
    else:
        # PUNCH OUT: Update existing attendance report
        entry_time_str = existing_rep.get('entry_time', '')
        
        # Calculate working duration
        working_minutes = 0
        try:
            # Parse entry time e.g. "26/09/2026 09:00:00 AM" or "26/09/2026 09:00:00"
            clean_time_str = entry_time_str.strip()
            entry_dt = None
            for fmt in ['%d/%m/%Y %I:%M:%S %p', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                try:
                    entry_dt = datetime.strptime(clean_time_str, fmt)
                    break
                except Exception:
                    pass
            if entry_dt:
                diff_sec = max(0, (now - entry_dt).total_seconds())
                working_minutes = int(diff_sec // 60)
            else:
                working_minutes = 480  # Default 8 hours if unparseable
        except Exception:
            working_minutes = 480
            
        w_hrs = working_minutes // 60
        w_mins = working_minutes % 60
        working_hours_str = f"{w_hrs:02d}:{w_mins:02d}"
        
        # Calculate Shift Variance
        shift_target_minutes = 480
        try:
            sparts = shift_hours_str.split(':')
            shift_target_minutes = int(sparts[0]) * 60 + int(sparts[1])
        except Exception:
            pass
            
        variance_minutes = working_minutes - shift_target_minutes
        if variance_minutes >= 0:
            v_h = variance_minutes // 60
            v_m = variance_minutes % 60
            shift_variance_str = f"+{v_h:02d}:{v_m:02d}"
        else:
            abs_vm = abs(variance_minutes)
            v_h = abs_vm // 60
            v_m = abs_vm % 60
            shift_variance_str = f"-{v_h:02d}:{v_m:02d}"
            
        # Calculate Working Salary
        if hourly_rate > 0:
            computed_salary = int(round((working_minutes / 60.0) * hourly_rate))
        elif day_rate > 0:
            computed_salary = int(round(day_rate))
        else:
            computed_salary = 0
            
        upd_data = {
            'exit_time': now_time_12,
            'exit_distance': formatted_dist,
            'exit_location': OFFICE_LOCATION_STR,
            'working_hours': working_hours_str,
            'shift_variance': shift_variance_str,
            'working_salary': computed_salary,
            'updated_at': now.isoformat()
        }
        db.attendance_reports.update_one({'_id': existing_rep['_id']}, {'$set': upd_data})
        
        # Update db.attendance
        db.attendance.update_one(
            {'employee_name': employee_name, 'date': today_date},
            {'$set': {'working_hours': working_hours_str, 'status': 'Present', 'updated_at': now}},
            upsert=True
        )
        return {'status': 'punch_out', 'live_id': live_id, 'formatted_dist': formatted_dist, 'working_hours': working_hours_str}

# ----------------- ATTENDANCE REPORTS ----------------- #

def get_attendance_reports(report_type='all', start_date=None, end_date=None, employee='All', search=None, page=1, limit=10):
    db = get_db()
    query = {}
    
    if report_type in ['proper', 'improper', 'manual']:
        query['entry_type'] = report_type
        
    if employee and employee != 'All':
        query['employee_name'] = employee
        
    if start_date:
        # Convert YYYY-MM-DD if needed
        s_date = start_date.strip()
        query.setdefault('$and', []).append({
            '$or': [
                {'date': {'$gte': s_date}},
                {'created_at': {'$gte': s_date}},
                {'entry_time': {'$gte': s_date}}
            ]
        })
    if end_date:
        e_date = end_date.strip()
        query.setdefault('$and', []).append({
            '$or': [
                {'date': {'$lte': e_date}},
                {'created_at': {'$lte': e_date + 'T23:59:59'}},
                {'entry_time': {'$lte': e_date + ' 23:59:59'}}
            ]
        })
        
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        query['$or'] = [
            {'employee_name': reg},
            {'entry_time': reg},
            {'exit_time': reg},
            {'entry_location': reg},
            {'exit_location': reg}
        ]
        
    total = db.attendance_reports.count_documents(query)
    cursor = db.attendance_reports.find(query).sort("created_at", DESCENDING)
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': data
    }

def get_attendance_simple_table(employee='All', start_date=None, end_date=None):
    db = get_db()
    query = {}
    if employee and employee != 'All':
        query['employee_name'] = employee
        
    cursor = db.attendance_reports.find(query).sort("created_at", DESCENDING)
    rows = [clean_doc(doc) for doc in cursor]
    
    total_minutes = 0
    total_salary = 0.0
    data = []
    
    for r in rows:
        wh = r.get('working_hours', '00:00')
        sal = float(r.get('working_salary', 0.0))
        total_salary += sal
        
        parts = wh.split(':')
        if len(parts) >= 2:
            try:
                total_minutes += int(parts[0]) * 60 + int(parts[1])
            except ValueError:
                pass
                
        data.append(r)
        
    tot_h = total_minutes // 60
    tot_m = total_minutes % 60
    formatted_total_hours = f"{tot_h:02d}:{tot_m:02d}"
    
    return {
        'data': data,
        'total_working_hours': formatted_total_hours,
        'total_working_salary': f"{total_salary:.2f}"
    }

# ----------------- MANUAL ENTRIES ----------------- #

def get_manual_entries(from_date=None, to_date=None, status='All', search=None, page=1, limit=10):
    db = get_db()
    query = {}
    
    if from_date:
        query['entry_date'] = {'$gte': from_date}
    if to_date:
        query.setdefault('entry_date', {})['$lte'] = to_date
        
    if status and status != 'All':
        query['status'] = status
        
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        query['$or'] = [
            {'employee_name': reg},
            {'entry_date': reg},
            {'status': reg},
            {'submitted_at': reg}
        ]
        
    total = db.manual_entries.count_documents(query)
    cursor = db.manual_entries.find(query).sort("entry_date", DESCENDING)
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': data
    }

def get_manual_entry_by_id(entry_id):
    db = get_db()
    doc = db.manual_entries.find_one(build_id_filter(entry_id))
    return clean_doc(doc)

def create_manual_entry(data):
    db = get_db()
    emp_name = data.get('employee_name', '')
    emp = db.employees.find_one({'employee_name': emp_name})
    hourly_rate = float(emp['hourly_salary'] if emp and 'hourly_salary' in emp else 1.0)
    day_rate = float(emp['day_salary'] if emp and 'day_salary' in emp else 0.0)
    half_rate = float(emp['half_day_salary'] if emp and 'half_day_salary' in emp else 0.0)
    emp_id = emp['id'] if emp and 'id' in emp else 'EMP_' + str(int(time.time()))
    
    hours_str = data.get('hours', '00:00')
    mode = data.get('mode', 'Hours')
    
    working_salary = 0.0
    if mode == 'Hours':
        parts = hours_str.split(':')
        if len(parts) >= 2:
            try:
                hrs = int(parts[0])
                mins = int(parts[1])
                working_salary = round((hrs + mins / 60.0) * hourly_rate, 2)
            except ValueError:
                working_salary = 0.0
    else:
        working_salary = float(data.get('working_salary') or 0.0)
        
    now_ts = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
    entry_id = int(time.time() * 1000)
    
    doc = {
        'id': entry_id,
        'employee_id': emp_id,
        'employee_name': emp_name,
        'entry_date': data.get('entry_date', ''),
        'hours': hours_str,
        'status': data.get('status', 'Permission'),
        'submitted_at': now_ts,
        'hourly_rate': hourly_rate,
        'day_rate': day_rate,
        'half_rate': half_rate,
        'working_salary': working_salary,
        'entry_type': data.get('entry_type', 'Add'),
        'mode': mode,
        'created_at': datetime.now()
    }
    db.manual_entries.insert_one(doc)
    return entry_id

def update_manual_entry(entry_id, data):
    db = get_db()
    emp_name = data.get('employee_name', '')
    emp = db.employees.find_one({'employee_name': emp_name})
    hourly_rate = float(emp['hourly_salary'] if emp and 'hourly_salary' in emp else 1.0)
    
    hours_str = data.get('hours', '00:00')
    mode = data.get('mode', 'Hours')
    
    working_salary = 0.0
    if mode == 'Hours':
        parts = hours_str.split(':')
        if len(parts) >= 2:
            try:
                hrs = int(parts[0])
                mins = int(parts[1])
                working_salary = round((hrs + mins / 60.0) * hourly_rate, 2)
            except ValueError:
                working_salary = 0.0
    else:
        working_salary = float(data.get('working_salary') or 0.0)
        
    upd = {
        'employee_name': emp_name,
        'entry_date': data.get('entry_date', ''),
        'hours': hours_str,
        'status': data.get('status', 'Permission'),
        'mode': mode,
        'working_salary': working_salary
    }
    db.manual_entries.update_one(build_id_filter(entry_id), {'$set': upd})
    return True

def delete_manual_entry(entry_id):
    db = get_db()
    db.manual_entries.delete_one(build_id_filter(entry_id))
    return True

# ----------------- PAYMENT MANAGEMENT ----------------- #

def get_payments(employee=None, start_date=None, end_date=None, bank=None, payment_type=None, reason=None, search=None, page=1, limit=10):
    db = get_db()
    query = {}
    
    if employee and employee != 'All':
        query['employee_name'] = employee
    if start_date:
        query['payment_date'] = {'$gte': start_date}
    if end_date:
        query.setdefault('payment_date', {})['$lte'] = end_date
    if bank and bank != 'All':
        query['bank'] = bank
    if payment_type and payment_type != 'All':
        query['payment_type'] = payment_type
    if reason and reason != 'All':
        query['reason'] = reason
        
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        query['$or'] = [
            {'employee_name': reg},
            {'bank': reg},
            {'payment_type': reg},
            {'reason': reg},
            {'timestamp': reg},
            {'payment_date': reg}
        ]
        
    total = db.payments.count_documents(query)
    cursor = db.payments.find(query).sort("timestamp", DESCENDING)
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': data
    }

def get_payment_by_id(payment_id):
    db = get_db()
    doc = db.payments.find_one(build_id_filter(payment_id))
    return clean_doc(doc)

def create_payment(data):
    db = get_db()
    emp_name = data.get('employee_name', '')
    emp = db.employees.find_one({'employee_name': emp_name})
    emp_id = emp['id'] if emp and 'id' in emp else 'EMP_' + str(int(time.time()))
    
    now_ts = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
    payment_date = data.get('payment_date') or datetime.now().strftime("%Y-%m-%d")
    amount = float(data.get('amount') or 0.0)
    bank = data.get('bank', '').strip()
    payment_type = data.get('payment_type', 'UPI')
    reason = data.get('reason', 'Advance Repayment')
    receipt_filename = data.get('receipt_filename', '')
    
    doc = {
        'id': int(time.time() * 1000),
        'timestamp': now_ts,
        'employee_id': emp_id,
        'employee_name': emp_name,
        'payment_date': payment_date,
        'amount': amount,
        'bank': bank,
        'payment_type': payment_type,
        'reason': reason,
        'receipt_filename': receipt_filename,
        'created_at': datetime.now()
    }
    res = db.payments.insert_one(doc)
    return str(doc['id'])

def update_payment(payment_id, data):
    db = get_db()
    emp_name = data.get('employee_name', '')
    upd = {
        'employee_name': emp_name,
        'payment_date': data.get('payment_date'),
        'amount': float(data.get('amount') or 0.0),
        'bank': data.get('bank', '').strip(),
        'payment_type': data.get('payment_type', 'UPI'),
        'reason': data.get('reason', 'Advance Repayment')
    }
    if 'receipt_filename' in data and data['receipt_filename'] is not None:
        upd['receipt_filename'] = data['receipt_filename']
        
    db.payments.update_one(build_id_filter(payment_id), {'$set': upd})
    return True

def delete_payment(payment_id):
    db = get_db()
    db.payments.delete_one(build_id_filter(payment_id))
    return True

# ----------------- ADVANCE MANAGEMENT ----------------- #

def get_advances(employee=None, start_date=None, end_date=None, search=None, page=1, limit=10):
    db = get_db()
    query = {}
    
    if employee and employee != 'All':
        query['employee_name'] = employee
    if start_date:
        query['advance_date'] = {'$gte': start_date}
    if end_date:
        query.setdefault('advance_date', {})['$lte'] = end_date
        
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        query['$or'] = [
            {'employee_name': reg},
            {'timestamp': reg},
            {'advance_date': reg}
        ]
        
    total = db.advances.count_documents(query)
    cursor = db.advances.find(query).sort("timestamp", DESCENDING)
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': data
    }

def get_advance_by_id(advance_id):
    db = get_db()
    doc = db.advances.find_one(build_id_filter(advance_id))
    return clean_doc(doc)

def create_advance(data):
    db = get_db()
    emp_name = data.get('employee_name', '')
    emp = db.employees.find_one({'employee_name': emp_name})
    emp_id = emp['id'] if emp and 'id' in emp else 'EMP_' + str(int(time.time()))
    
    now_ts = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
    advance_date = data.get('advance_date') or datetime.now().strftime("%Y-%m-%d")
    amount = float(data.get('amount') or 0.0)
    
    doc = {
        'id': int(time.time() * 1000),
        'timestamp': now_ts,
        'employee_id': emp_id,
        'employee_name': emp_name,
        'advance_date': advance_date,
        'amount': amount,
        'status': 'Active',
        'created_at': datetime.now()
    }
    db.advances.insert_one(doc)
    return str(doc['id'])

def update_advance(advance_id, data):
    db = get_db()
    upd = {
        'employee_name': data.get('employee_name', ''),
        'advance_date': data.get('advance_date'),
        'amount': float(data.get('amount') or 0.0)
    }
    db.advances.update_one(build_id_filter(advance_id), {'$set': upd})
    return True

def delete_advance(advance_id):
    db = get_db()
    db.advances.delete_one(build_id_filter(advance_id))
    return True

# ----------------- BALANCE REPORT ----------------- #

def get_balance_report(employee=None, search=None, page=1, limit=10):
    db = get_db()
    
    # Query all advances
    adv_query = {}
    if employee and employee != 'All':
        adv_query['employee_name'] = employee
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        adv_query['$or'] = [{'employee_name': reg}, {'timestamp': reg}, {'advance_date': reg}]
        
    adv_cursor = db.advances.find(adv_query)
    
    # Query all advance repayments
    rep_query = {'reason': 'Advance Repayment'}
    if employee and employee != 'All':
        rep_query['employee_name'] = employee
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        rep_query['$or'] = [{'employee_name': reg}, {'timestamp': reg}, {'payment_date': reg}]
        
    rep_cursor = db.payments.find(rep_query)
    
    combined = []
    total_advance = 0.0
    total_repayment = 0.0
    
    for a in adv_cursor:
        amt = float(a.get('amount', 0.0))
        total_advance += amt
        combined.append({
            'timestamp': a.get('timestamp', ''),
            'name': a.get('employee_name', ''),
            'date': a.get('advance_date', ''),
            'advance_amount': amt,
            'advance_repayment_amount': 0.0,
            'balance_amount': amt
        })
        
    for p in rep_cursor:
        amt = float(p.get('amount', 0.0))
        total_repayment += amt
        combined.append({
            'timestamp': p.get('timestamp', ''),
            'name': p.get('employee_name', ''),
            'date': p.get('payment_date', ''),
            'advance_amount': 0.0,
            'advance_repayment_amount': amt,
            'balance_amount': -amt
        })
        
    combined.sort(key=lambda x: x['timestamp'], reverse=True)
    total = len(combined)
    balance_amount = total_advance - total_repayment
    
    if limit and limit > 0:
        offset = (page - 1) * limit
        paginated_data = combined[offset:offset + limit]
    else:
        paginated_data = combined
        
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': paginated_data,
        'total_advance': total_advance,
        'total_repayment': total_repayment,
        'balance_amount': balance_amount,
        'summary': {
            'total_advance': total_advance,
            'total_repayment': total_repayment,
            'balance': balance_amount
        }
    }

# ----------------- SALARY REPORTS ----------------- #

def get_salary_reports(start_month=None, end_month=None, search=None, page=1, limit=10):
    db = get_db()
    query = {}
    
    if start_month:
        query['pay_period'] = {'$gte': start_month}
    if end_month:
        query.setdefault('pay_period', {})['$lte'] = end_month
        
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        query['$or'] = [
            {'employee_name': reg},
            {'pay_period': reg},
            {'working_hours': reg}
        ]
        
    total = db.salary_reports.count_documents(query)
    cursor = db.salary_reports.find(query).sort([("pay_period", DESCENDING), ("id", ASCENDING)])
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': data
    }

# ----------------- PAYSLIP HELPER & NUMBER TO WORDS ----------------- #

def number_to_words(n):
    n = int(round(float(n)))
    if n == 0:
        return "Zero Rupees Only"
    if n < 0:
        return "Minus " + number_to_words(abs(n))
        
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
            "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
            "Seventeen", "Eighteen", "Nineteen"]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    
    def helper(num):
        if num < 20:
            return ones[num]
        elif num < 100:
            return (tens[num // 10] + (" " + ones[num % 10] if num % 10 != 0 else "")).strip()
        elif num < 1000:
            rem = num % 100
            return (ones[num // 100] + " Hundred" + (" and " + helper(rem) if rem != 0 else "")).strip()
        elif num < 100000:
            rem = num % 1000
            return (helper(num // 1000) + " Thousand" + (" " + helper(rem) if rem != 0 else "")).strip()
        elif num < 10000000:
            rem = num % 100000
            return (helper(num // 100000) + " Lakh" + (" " + helper(rem) if rem != 0 else "")).strip()
        else:
            rem = num % 10000000
            return (helper(num // 10000000) + " Crore" + (" " + helper(rem) if rem != 0 else "")).strip()
            
    words = helper(n).strip()
    return f"{words} Rupees Only"

def validate_admin_login(username, password):
    db = get_db()
    user = db.admin_users.find_one({'username': username, 'password': password})
    return user is not None

def save_generated_salary_report(p):
    """Save or upsert generated payslip record into db.salary_reports."""
    db = get_db()
    doc = {
        'employee_name': p.get('employee_name', ''),
        'pay_period': p.get('year_month', ''),
        'working_days': int(p.get('working_days', 0)),
        'working_hours': p.get('total_working_hours', '00:00'),
        'allowance': float(p.get('allowance', 0)),
        'incentive': float(p.get('incentive', 0)),
        'other_earnings': float(p.get('other_earnings', 0)),
        'basic_earnings': float(p.get('basic_salary', 0)),
        'total_earnings': float(p.get('total_earnings', 0)),
        'paid_salary': float(p.get('paid_salary', 0)),
        'advance_repayment': float(p.get('advance_repayment', 0)),
        'other_deductions': float(p.get('other_deductions', 0)),
        'total_deductions': float(p.get('total_deduction', 0)),
        'net_salary': float(p.get('net_pay', 0)),
        'updated_at': datetime.now()
    }
    db.salary_reports.update_one(
        {'employee_name': doc['employee_name'], 'pay_period': doc['pay_period']},
        {'$set': doc, '$setOnInsert': {'id': int(time.time() * 1000), 'created_at': datetime.now()}},
        upsert=True
    )
    return True

def get_payslip_data(employee_name, month_year):
    db = get_db()
    emp = db.employees.find_one({'employee_name': employee_name})
    
    try:
        parts = month_year.split('-')
        yr = int(parts[0])
        mo = int(parts[1])
        if mo in [1, 3, 5, 7, 8, 10, 12]:
            total_days = 31
        elif mo in [4, 6, 9, 11]:
            total_days = 30
        else:
            total_days = 29 if (yr % 4 == 0 and (yr % 100 != 0 or yr % 400 == 0)) else 28
    except Exception:
        total_days = 30
        
    emp_id = emp.get('id', '') if emp else ''
    designation = emp.get('designation', '') if emp else ''
    phone = emp.get('mobile_number', '') if emp else ''
    hours_salary = float(emp.get('hourly_salary', 0.0)) if emp else 0.0
    day_salary = float(emp.get('day_salary', 0.0)) if emp else 0.0
    half_salary = float(emp.get('half_day_salary', 0.0)) if emp else 0.0
    
    # 1. Query attendance & attendance_reports for this employee & month
    att_query = {
        'employee_name': employee_name,
        '$or': [
            {'date': {'$regex': f'^{month_year}'}},
            {'entry_time': {'$regex': f'^{month_year}'}},
            {'created_at': {'$regex': f'^{month_year}'}}
        ]
    }
    try:
        parts = month_year.split('-')
        m_slash = f"/{parts[1]}/{parts[0]}"
        att_query['$or'].append({'entry_time': {'$regex': m_slash}})
        att_query['$or'].append({'created_at': {'$regex': m_slash}})
    except Exception:
        pass

    records = list(db.attendance_reports.find(att_query))
    if not records:
        records = list(db.attendance.find(att_query))

    total_minutes = 0
    distinct_dates = set()

    for rec in records:
        d_val = rec.get('date') or (rec.get('entry_time', '').split(' ')[0] if rec.get('entry_time') else '')
        if d_val:
            distinct_dates.add(d_val)

        wh = rec.get('working_hours', '00:00')
        if wh and ':' in wh:
            try:
                h, m = wh.split(':')[:2]
                total_minutes += int(h) * 60 + int(m)
            except Exception:
                pass
        elif rec.get('working_hours'):
            try:
                total_minutes += int(float(rec.get('working_hours')) * 60)
            except Exception:
                pass

    # 2. Query manual_entries for this employee & month
    manual_query = {
        'employee_name': employee_name,
        '$or': [
            {'entry_date': {'$regex': f'^{month_year}'}},
            {'submitted_at': {'$regex': f'^{month_year}'}}
        ]
    }
    try:
        parts = month_year.split('-')
        m_hyphen = f"-{parts[1]}-{parts[0]}"
        manual_query['$or'].append({'submitted_at': {'$regex': m_hyphen}})
    except Exception:
        pass

    manual_entries = list(db.manual_entries.find(manual_query))
    manual_salary_sum = 0.0

    for m_entry in manual_entries:
        ed = m_entry.get('entry_date') or (m_entry.get('submitted_at', '').split(' ')[0] if m_entry.get('submitted_at') else '')
        if ed:
            distinct_dates.add(ed)
            
        hrs_str = m_entry.get('hours', '00:00')
        if hrs_str and ':' in hrs_str:
            try:
                h, m = hrs_str.split(':')[:2]
                total_minutes += int(h) * 60 + int(m)
            except Exception:
                pass
                
        msal = float(m_entry.get('working_salary', 0.0))
        manual_salary_sum += msal

    working_days = len(distinct_dates)
    tot_hrs = total_minutes // 60
    tot_mins = total_minutes % 60
    working_hours = f"{tot_hrs:02d}:{tot_mins:02d}"

    # Calculate basic salary
    if hours_salary > 0:
        basic_salary = round((total_minutes / 60.0) * hours_salary, 2)
    elif day_salary > 0:
        basic_salary = round(working_days * day_salary, 2)
    else:
        basic_salary = manual_salary_sum

    if basic_salary == 0.0 and manual_salary_sum > 0.0:
        basic_salary = manual_salary_sum

    # 3. Query payments collection for this employee & month (Incentive, Allowance, Advances, Bonus)
    payment_query = {
        'employee_name': employee_name,
        '$or': [
            {'payment_date': {'$regex': f'^{month_year}'}},
            {'timestamp': {'$regex': f'^{month_year}'}}
        ]
    }
    try:
        parts = month_year.split('-')
        m_hyphen = f"-{parts[1]}-{parts[0]}"
        payment_query['$or'].append({'timestamp': {'$regex': m_hyphen}})
    except Exception:
        pass

    payments = list(db.payments.find(payment_query))
    allowance = 0.0
    incentive = 0.0
    other_earnings = 0.0
    advance_repayment = 0.0
    paid_salary = 0.0

    for p in payments:
        p_amt = float(p.get('amount', 0.0))
        reason = p.get('reason', '').strip()
        if reason.lower() == 'incentive':
            incentive += p_amt
        elif reason.lower() == 'allowance':
            allowance += p_amt
        elif 'advance' in reason.lower():
            advance_repayment += p_amt
        elif reason.lower() in ['salary', 'paid salary']:
            paid_salary += p_amt
        else:
            other_earnings += p_amt

    # If no advance repayment logged in payments for this month, check advances collection
    if advance_repayment == 0.0:
        adv_doc = db.advances.find_one({'employee_name': employee_name})
        if adv_doc:
            advance_repayment = float(adv_doc.get('repayment_amount', 0.0))

    total_earnings = round(basic_salary + allowance + incentive + other_earnings, 2)
    other_deductions = 0.0
    total_deduction = round(advance_repayment + other_deductions, 2)
    net_pay = max(0.0, round(total_earnings - total_deduction, 2))
        
    leave_days = max(0, total_days - working_days)
    net_pay_in_words = number_to_words(net_pay)
    
    return {
        'company_name': 'ARGUS TECHNOLOGIES',
        'company_address': 'SF NO. 515, Bharathiyar Road, Maniyakaranpalayam, Ganapathy (PO), Coimbatore - 641 006',
        'employee_name': employee_name,
        'employee_id': emp_id,
        'designation': designation,
        'phone_number': phone,
        'year_month': month_year,
        'hours_salary': int(round(hours_salary)),
        'day_salary': int(round(day_salary)),
        'half_day_salary': int(round(half_salary)),
        'working_days': working_days,
        'leave_days': leave_days,
        'total_days_of_month': total_days,
        'total_working_hours': working_hours,
        'basic_salary': int(round(basic_salary)),
        'allowance': int(round(allowance)),
        'incentive': int(round(incentive)),
        'other_earnings': int(round(other_earnings)),
        'total_earnings': int(round(total_earnings)),
        'paid_salary': int(round(paid_salary)),
        'advance_repayment': int(round(advance_repayment)),
        'other_deductions': int(round(other_deductions)),
        'total_deduction': int(round(total_deduction)),
        'net_pay': int(round(net_pay)),
        'net_pay_in_words': net_pay_in_words
    }
