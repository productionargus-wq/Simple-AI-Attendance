import os
import time
import json
import re
from datetime import datetime, date, timedelta, timezone
from dotenv import load_dotenv
from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

def hash_user_password(plain_password):
    """Generates a secure PBKDF2/SHA256 password hash."""
    return generate_password_hash(str(plain_password).strip())

def verify_user_password(stored_password, provided_password):
    """Verifies a plain password against a hashed or legacy plaintext password."""
    if not stored_password or not provided_password:
        return False
    stored = str(stored_password).strip()
    provided = str(provided_password).strip()
    if stored.startswith('pbkdf2:') or stored.startswith('scrypt:'):
        return check_password_hash(stored, provided)
    return stored == provided

# Indian Standard Time (IST, UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Returns the current timezone-aware datetime in Indian Standard Time (IST)."""
    return datetime.now(IST)

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
    """Clean MongoDB document for JSON serialization recursively."""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [clean_doc(item) for item in doc]
    d = dict(doc)
    for k, v in list(d.items()):
        if isinstance(v, ObjectId):
            d[k] = str(v)
        elif isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
        elif isinstance(v, dict):
            d[k] = clean_doc(v)
        elif isinstance(v, list):
            d[k] = [
                clean_doc(item) if isinstance(item, dict)
                else (item.isoformat() if isinstance(item, (datetime, date))
                      else (str(item) if isinstance(item, ObjectId) else item))
                for item in v
            ]
    if '_id' in d:
        if 'id' not in d or not d['id']:
            d['id'] = str(d['_id'])
        d['_id'] = str(d['_id'])
    if 'photo_filename' in d and not d.get('photo'):
        d['photo'] = d['photo_filename']
    elif 'photo' in d and not d.get('photo_filename'):
        d['photo_filename'] = d['photo']
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

def migrate_existing_data_to_master():
    """Backfills legacy documents without company_id to ARGUS_MASTER."""
    try:
        db = get_db()
        collections = ['employees', 'live_entries', 'attendance_reports', 'attendance', 'manual_entries', 'payments', 'advances', 'salary_reports']
        for coll_name in collections:
            coll = db[coll_name]
            coll.update_many(
                {'$or': [{'company_id': {'$exists': False}}, {'company_id': None}, {'company_id': ''}]},
                {'$set': {'company_id': 'ARGUS_MASTER'}}
            )
        db.admin_users.update_many(
            {'username': 'Admin'},
            {'$set': {'role': 'super_admin', 'company_id': 'ARGUS_MASTER', 'company_name': 'ARGUS TECHNOLOGIES'}}
        )
        # Backfill salary_type if missing
        for emp in db.employees.find({'$or': [{'salary_type': {'$exists': False}}, {'salary_type': None}, {'salary_type': ''}]}):
            st = 'hourly'
            d_sal = float(emp.get('day_salary', 0.0) or 0.0)
            h_sal = float(emp.get('hourly_salary', 0.0) or 0.0)
            hd_sal = float(emp.get('half_day_salary', 0.0) or 0.0)
            if d_sal > 0 and h_sal == 0:
                st = 'daily'
            elif hd_sal > 0 and d_sal == 0 and h_sal == 0:
                st = 'half_day'
            else:
                st = 'hourly'
            db.employees.update_one({'_id': emp['_id']}, {'$set': {'salary_type': st}})
    except Exception as e:
        print(f"Warning during tenant data migration: {e}")

def init_db():
    db = get_db()
    
    # Create indexes for high-speed queries
    try:
        # Multi-Tenant Company Admin Index
        db.company_admin.create_index([("id", ASCENDING)], unique=True)
        db.company_admin.create_index([("email", ASCENDING)], unique=True)
        db.company_admin.create_index([("company_name", ASCENDING)])
        
        # Operational Indexes with company_id
        db.employees.create_index([("id", ASCENDING)], unique=True)
        db.employees.create_index([("company_id", ASCENDING), ("employee_name", ASCENDING)])
        db.employees.create_index([("email_id", ASCENDING)])
        db.live_entries.create_index([("company_id", ASCENDING), ("is_timeout", ASCENDING), ("entry_time", DESCENDING)])
        db.attendance_reports.create_index([("company_id", ASCENDING), ("entry_type", ASCENDING), ("employee_name", ASCENDING)])
        db.attendance.create_index([("company_id", ASCENDING), ("date", DESCENDING)])
        db.manual_entries.create_index([("company_id", ASCENDING), ("entry_date", DESCENDING)])
        db.payments.create_index([("company_id", ASCENDING), ("payment_date", DESCENDING), ("reason", ASCENDING)])
        db.advances.create_index([("company_id", ASCENDING), ("advance_date", DESCENDING)])
        db.salary_reports.create_index([("company_id", ASCENDING), ("pay_period", DESCENDING), ("employee_name", ASCENDING)])
    except Exception as e:
        print(f"Warning creating MongoDB indexes: {e}")

    if db.admin_users.count_documents({}) == 0:
        db.admin_users.insert_one({
            'username': 'Admin',
            'email': 'technologiesargus@gmail.com',
            'password': '76543',
            'role': 'super_admin',
            'company_id': 'ARGUS_MASTER',
            'company_name': 'ARGUS TECHNOLOGIES'
        })
    else:
        db.admin_users.update_many(
            {},
            {'$set': {
                'email': 'technologiesargus@gmail.com',
                'role': 'super_admin',
                'company_id': 'ARGUS_MASTER',
                'company_name': 'ARGUS TECHNOLOGIES'
            }}
        )

    # Backfill default password_raw if not present
    db.admin_users.update_many(
        {'password_raw': {'$exists': False}},
        {'$set': {'password_raw': '76543'}}
    )

    # Automatically backfill legacy records with company_id: ARGUS_MASTER
    migrate_existing_data_to_master()

    # Ensure master company profile exists in company_admin
    existing_argus = db.company_admin.find_one({'email': 'technologiesargus@gmail.com'})
    if existing_argus:
        db.company_admin.update_one(
            {'_id': existing_argus['_id']},
            {'$set': {
                'id': 'ARGUS_MASTER',
                'company_name': 'ARGUS TECHNOLOGIES',
                'address': existing_argus.get('address') or 'SF NO. 515, Bharathiyar Road, Maniyakaranpalayam, Ganapathy (PO), Coimbatore - 641 006'
            }}
        )
    elif not db.company_admin.find_one({'id': 'ARGUS_MASTER'}):
        try:
            db.company_admin.insert_one({
                'id': 'ARGUS_MASTER',
                'company_name': 'ARGUS TECHNOLOGIES',
                'gstin': '33AABCA0000A1Z5',
                'email': 'technologiesargus@gmail.com',
                'phone': '+91 98765 43210',
                'address': 'SF NO. 515, Bharathiyar Road, Maniyakaranpalayam, Ganapathy (PO), Coimbatore - 641 006',
                'latitude': 11.02980,
                'longitude': 76.97400,
                'status': 'Active',
                'employee_limit': 1000,
                'shift_hours': '08:00',
                'auto_email_reports': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
        except Exception as e:
            print(f"Master company seeding notice: {e}")

# ----------------- MULTI-TENANT COMPANY MANAGEMENT ----------------- #

def apply_tenant_filter(query, company_id):
    """Applies strict tenant isolation filter to a MongoDB query dictionary."""
    if query is None:
        query = {}
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
    return query

def create_company(data):
    """Registers a new client company in company_admin collection."""
    db = get_db()
    comp_id = str(data.get('id') or f"comp_{int(time.time() * 1000)}")
    email = data.get('email', '').strip().lower()
    if not email:
        raise ValueError("Company registered email is required.")
        
    existing = db.company_admin.find_one({'email': {'$regex': f"^{re.escape(email)}$", '$options': 'i'}})
    if existing:
        raise ValueError(f"A company with email '{email}' is already registered.")
        
    now_ist = get_ist_now()
    reg_date_str = now_ist.strftime('%d/%m/%Y %I:%M %p')
    lat_val = data.get('latitude')
    lng_val = data.get('longitude')
    lat = None
    lng = None
    if lat_val is not None and str(lat_val).strip() != '':
        try:
            lat = float(lat_val)
        except Exception:
            lat = None
    if lng_val is not None and str(lng_val).strip() != '':
        try:
            lng = float(lng_val)
        except Exception:
            lng = None

    coords_locked = bool(lat is not None and lng is not None)

    doc = {
        'id': comp_id,
        'company_name': data.get('company_name', '').strip(),
        'gstin': data.get('gstin', '').strip().upper(),
        'email': email,
        'phone': data.get('phone', '').strip(),
        'address': data.get('address', '').strip(),
        'latitude': lat,
        'longitude': lng,
        'coordinates_locked': coords_locked,
        'coordinates_locked_at': now_ist if coords_locked else None,
        'status': data.get('status', 'Active').strip(),
        'employee_limit': int(data.get('employee_limit') or data.get('employee_count') or 50),
        'shift_hours': str(data.get('shift_hours') or '08:00').strip(),
        'auto_email_reports': bool(data.get('auto_email_reports', True)),
        'registered_date': reg_date_str,
        'created_at': now_ist,
        'updated_at': now_ist
    }
    db.company_admin.insert_one(doc)
    return comp_id

def format_company_reg_date(val):
    if not val:
        return '-'
    if isinstance(val, datetime):
        return val.strftime('%d/%m/%Y %I:%M %p')
    val_str = str(val).strip()
    if not val_str or val_str == '-':
        return '-'
    if 'T' in val_str or '-' in val_str:
        clean_str = val_str.replace('Z', '')
        if '.' in clean_str:
            clean_str = clean_str.split('.')[0]
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y %I:%M %p', '%d/%m/%Y'):
            try:
                parsed = datetime.strptime(clean_str, fmt)
                return parsed.strftime('%d/%m/%Y %I:%M %p')
            except Exception:
                pass
    return val_str

def get_all_companies(search='', page=1, limit=10):
    """Retrieves paginated companies with employee count, limit, and registered date."""
    db = get_db()
    query = {}
    search_str = str(search or '').strip()
    if search_str:
        reg = {'$regex': re.escape(search_str), '$options': 'i'}
        query['$or'] = [
            {'company_name': reg},
            {'email': reg},
            {'gstin': reg},
            {'phone': reg},
            {'id': reg},
            {'address': reg}
        ]
        
    total = db.company_admin.count_documents(query)
    cursor = db.company_admin.find(query).sort([("created_at", DESCENDING), ("_id", DESCENDING)])
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    companies = []
    for doc in cursor:
        c = clean_doc(doc)
        c['address'] = c.get('address') or c.get('location') or ''
        c['employee_count'] = db.employees.count_documents({'company_id': c['id']})
        c['employee_limit'] = int(c.get('employee_limit') or c.get('employee_count') or 50)
        c['shift_hours'] = str(c.get('shift_hours') or '08:00').strip()
        if 'auto_email_reports' not in c:
            c['auto_email_reports'] = True
            
        c['registered_date'] = format_company_reg_date(c.get('registered_date') or c.get('created_at'))
        companies.append(c)
        
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': companies
    }

def get_company_by_id(comp_id):
    """Fetches company details by ID with current employee count, limit, and registered date."""
    db = get_db()
    if not comp_id:
        return None
    doc = db.company_admin.find_one({'id': str(comp_id)})
    if not doc:
        doc = db.company_admin.find_one(build_id_filter(comp_id))
    if doc:
        c = clean_doc(doc)
        c['address'] = c.get('address') or c.get('location') or ''
        c['employee_count'] = db.employees.count_documents({'company_id': c['id']})
        c['employee_limit'] = int(c.get('employee_limit') or c.get('employee_count') or 50)
        c['shift_hours'] = str(c.get('shift_hours') or '08:00').strip()
        if 'auto_email_reports' not in c:
            c['auto_email_reports'] = True
        c['registered_date'] = format_company_reg_date(c.get('registered_date') or c.get('created_at'))
        return c
    return None

def get_company_by_email(email):
    """Fetches company details by registered email."""
    db = get_db()
    if not email:
        return None
    doc = db.company_admin.find_one({'email': {'$regex': f"^{re.escape(email.strip())}$", '$options': 'i'}})
    if doc:
        c = clean_doc(doc)
        c['address'] = c.get('address') or c.get('location') or ''
        return c
    return None

def update_company(comp_id, data):
    """Updates company details in company_admin."""
    db = get_db()
    upd = {
        'updated_at': get_ist_now()
    }
    if 'company_name' in data and data['company_name']:
        upd['company_name'] = str(data['company_name']).strip()
    if 'gstin' in data and data['gstin']:
        upd['gstin'] = str(data['gstin']).strip().upper()
    if 'email' in data and data['email']:
        upd['email'] = str(data['email']).strip().lower()
    if 'phone' in data and data['phone']:
        upd['phone'] = str(data['phone']).strip()
    if 'address' in data:
        upd['address'] = str(data['address']).strip()
        upd['location'] = str(data['address']).strip()
    if 'latitude' in data:
        lat_val = data['latitude']
        if lat_val is None or str(lat_val).strip() == '':
            upd['latitude'] = None
        else:
            try:
                upd['latitude'] = float(lat_val)
            except Exception:
                pass
    if 'longitude' in data:
        lng_val = data['longitude']
        if lng_val is None or str(lng_val).strip() == '':
            upd['longitude'] = None
        else:
            try:
                upd['longitude'] = float(lng_val)
            except Exception:
                pass
    if 'coordinates_locked' in data:
        upd['coordinates_locked'] = bool(data['coordinates_locked'])
    elif ('latitude' in upd or 'longitude' in upd):
        cur_lat = upd.get('latitude')
        cur_lng = upd.get('longitude')
        if cur_lat is not None and cur_lng is not None:
            upd['coordinates_locked'] = True
            upd['coordinates_locked_at'] = get_ist_now()
        elif cur_lat is None and cur_lng is None and ('latitude' in upd and 'longitude' in upd):
            upd['coordinates_locked'] = False
    if 'coordinates_locked_at' in data:
        upd['coordinates_locked_at'] = data['coordinates_locked_at']
    if 'status' in data and data['status']:
        upd['status'] = str(data['status']).strip()
    if 'employee_limit' in data or 'employee_count' in data:
        lim = data.get('employee_limit') or data.get('employee_count')
        if lim:
            try:
                upd['employee_limit'] = int(lim)
            except Exception:
                pass
    if 'shift_hours' in data and data['shift_hours']:
        upd['shift_hours'] = str(data['shift_hours']).strip()
    if 'auto_email_reports' in data:
        upd['auto_email_reports'] = bool(data['auto_email_reports'])
    db.company_admin.update_one({'id': str(comp_id)}, {'$set': upd})
    return True

def toggle_company_auto_reports(comp_id, enabled=None):
    """Toggles or sets the automatic email report preference for a company."""
    db = get_db()
    comp = db.company_admin.find_one({'id': str(comp_id)})
    if not comp:
        return None
    current_val = comp.get('auto_email_reports', True)
    new_val = not current_val if enabled is None else bool(enabled)
    db.company_admin.update_one({'id': str(comp_id)}, {'$set': {'auto_email_reports': new_val, 'updated_at': datetime.now()}})
    return new_val

def delete_company(comp_id):
    """Removes company from company_admin."""
    db = get_db()
    db.company_admin.delete_one({'id': str(comp_id)})
    return True

def get_company_reports_summary():
    """Generates platform-wide company summary metrics for Super Admin."""
    db = get_db()
    total_companies = db.company_admin.count_documents({})
    active_companies = db.company_admin.count_documents({'status': 'Active'})
    total_tenant_employees = db.employees.count_documents({'company_id': {'$ne': 'ARGUS_MASTER'}})
    total_argus_employees = db.employees.count_documents({'company_id': 'ARGUS_MASTER'})
    
    companies = list(db.company_admin.find({}, sort=[('created_at', DESCENDING)]))
    breakdown = []
    today_slash = get_ist_now().strftime('%d/%m/%Y')
    for c in companies:
        cid = str(c.get('id') or c.get('_id'))
        emp_cnt = db.employees.count_documents({'company_id': cid})
        active_today = len(db.live_entries.distinct('employee_name', {'company_id': cid, 'entry_time': {'$regex': today_slash}}))
        created_str = c.get('created_at').strftime('%d/%m/%Y') if hasattr(c.get('created_at'), 'strftime') else str(c.get('created_at', ''))
        breakdown.append({
            'id': cid,
            'company_name': c.get('company_name', ''),
            'gstin': c.get('gstin', ''),
            'email': c.get('email', ''),
            'phone': c.get('phone', ''),
            'latitude': c.get('latitude', 11.02980),
            'longitude': c.get('longitude', 76.97400),
            'status': c.get('status', 'Active'),
            'employee_count': emp_cnt,
            'active_today': active_today,
            'created_at': created_str
        })
        
    return {
        'total_companies': total_companies,
        'active_companies': active_companies,
        'total_tenant_employees': total_tenant_employees,
        'total_argus_employees': total_argus_employees,
        'total_employees_all': total_tenant_employees + total_argus_employees,
        'companies': breakdown
    }

def validate_company_login(email, password=None):
    """Validates company admin login by registered email, and optionally verifies password for manual login."""
    db = get_db()
    if not email:
        return None if password is None else {'success': False, 'error': 'NOT_REGISTERED'}
    email_clean = email.strip().lower()
    doc = db.company_admin.find_one({
        'email': {'$regex': f"^{re.escape(email_clean)}$", '$options': 'i'}
    })
    if not doc:
        return None if password is None else {'success': False, 'error': 'NOT_REGISTERED'}
    company = clean_doc(doc)
    
    if password is None:
        # Google OAuth flow - password not required
        return company

    # Manual login with password required
    stored = doc.get('password') or doc.get('password_hash')
    if not stored:
        return {'success': False, 'error': 'PASSWORD_NOT_SET', 'company': company}
    if verify_user_password(stored, password):
        return {'success': True, 'company': company}
    return {'success': False, 'error': 'INVALID_PASSWORD', 'company': company}

def set_company_password(company_id_or_email, plain_password):
    """Sets a new hashed password for a company administrator and persists password_raw."""
    db = get_db()
    if not company_id_or_email or not plain_password:
        return False
    raw = str(plain_password).strip()
    hashed = hash_user_password(raw)
    res = db.company_admin.update_one(
        {'$or': [{'id': str(company_id_or_email)}, {'email': str(company_id_or_email)}]},
        {'$set': {'password': hashed, 'password_hash': hashed, 'password_raw': raw, 'password_updated_at': datetime.now()}}
    )
    return res.modified_count > 0 or res.matched_count > 0

def validate_employee_login(email, password=None):
    """Validates employee login by registered email and attaches company details, optionally verifying password."""
    db = get_db()
    if not email:
        return None if password is None else {'success': False, 'error': 'NOT_REGISTERED'}
    email_clean = email.strip().lower()
    doc = db.employees.find_one({
        'email_id': {'$regex': f"^{re.escape(email_clean)}$", '$options': 'i'}
    })
    if not doc:
        return None if password is None else {'success': False, 'error': 'NOT_REGISTERED'}
    emp = clean_doc(doc)
    comp_id = emp.get('company_id')
    if comp_id and comp_id != 'ARGUS_MASTER':
        comp = db.company_admin.find_one({'id': str(comp_id)})
        emp['company_name'] = comp.get('company_name') if comp else 'Client Company'
        emp['company_lat'] = comp.get('latitude') if comp else 11.02980
        emp['company_lng'] = comp.get('longitude') if comp else 76.97400
    else:
        emp['company_name'] = 'ARGUS TECHNOLOGIES'
        emp['company_lat'] = 11.02980
        emp['company_lng'] = 76.97400

    if password is None:
        # Google OAuth flow - password not required
        return emp

    # Manual login with password required
    stored = doc.get('password') or doc.get('password_hash')
    if not stored:
        return {'success': False, 'error': 'PASSWORD_NOT_SET', 'employee': emp}
    if verify_user_password(stored, password):
        return {'success': True, 'employee': emp}
    return {'success': False, 'error': 'INVALID_PASSWORD', 'employee': emp}

def set_employee_password(emp_id_or_email, plain_password):
    """Sets a new hashed password for an employee."""
    db = get_db()
    if not emp_id_or_email or not plain_password:
        return False
    hashed = hash_user_password(plain_password)
    res = db.employees.update_one(
        {'$or': [build_id_filter(emp_id_or_email), {'email_id': str(emp_id_or_email)}]},
        {'$set': {'password': hashed, 'password_hash': hashed, 'password_updated_at': datetime.now()}}
    )
    return res.modified_count > 0 or res.matched_count > 0

# ----------------- EMPLOYEE OPERATIONS ----------------- #

def generate_employee_id():
    return str(int(time.time() * 1000))

def get_all_employees(company_id=None, search='', sort_col='id', sort_dir='desc', page=1, limit=10):
    db = get_db()
    query = {}
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        search_filter = {
            '$or': [
                {'employee_name': reg},
                {'designation': reg},
                {'mobile_number': reg},
                {'email_id': reg},
                {'id': reg}
            ]
        }
        if query:
            query = {'$and': [query, search_filter]}
        else:
            query = search_filter
    
    total = db.employees.count_documents(query)
    sort_direction = ASCENDING if sort_dir.lower() == 'asc' else DESCENDING
    
    # Ensure newest records appear at the top
    if sort_col in ['id', 'created_at', '']:
        cursor = db.employees.find(query).sort([('created_at', sort_direction), ('id', sort_direction), ('_id', sort_direction)])
    else:
        cursor = db.employees.find(query).sort([(sort_col, sort_direction), ('created_at', DESCENDING), ('id', DESCENDING)])
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    employees = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': employees
    }

def get_employee_by_id(emp_id, company_id=None):
    db = get_db()
    f = build_id_filter(emp_id)
    if company_id and company_id != 'ALL':
        f = {'$and': [f, {'company_id': str(company_id)}]}
    doc = db.employees.find_one(f)
    return clean_doc(doc)

def create_employee(data, company_id=None):
    db = get_db()
    emp_id = data.get('id') or generate_employee_id()
    assigned_company_id = str(company_id or data.get('company_id') or 'ARGUS_MASTER')

    # Enforce Employee Count registration limit for tenant companies
    if assigned_company_id != 'ARGUS_MASTER':
        comp = db.company_admin.find_one({'id': assigned_company_id})
        if comp:
            limit = int(comp.get('employee_limit') or comp.get('employee_count') or 50)
            current_count = db.employees.count_documents({'company_id': assigned_company_id})
            if current_count >= limit:
                comp_name = comp.get('company_name', assigned_company_id)
                raise ValueError(
                    f"Employee registration limit reached: Company '{comp_name}' allows a maximum of {limit} employees ({current_count}/{limit} currently registered). Please contact Super Admin to increase the employee limit."
                )

    raw_st = str(data.get('salary_type') or 'hourly').strip().lower()
    salary_type = raw_st if raw_st in ['hourly', 'daily', 'half_day'] else 'hourly'
    
    doc = {
        'id': emp_id,
        'company_id': assigned_company_id,
        'employee_name': data.get('employee_name', '').strip(),
        'designation': data.get('designation', '').strip(),
        'salary_type': salary_type,
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
        'shift_start': str(data.get('shift_start') or '09:00 AM').strip(),
        'shift_end': str(data.get('shift_end') or '06:00 PM').strip(),
        'photo': str(data.get('photo') or data.get('photo_filename') or '').strip(),
        'photo_filename': str(data.get('photo_filename') or data.get('photo') or '').strip(),
        'face_embedding': data.get('face_embedding', ''),
        'created_at': get_ist_now(),
        'updated_at': get_ist_now()
    }
    
    db.employees.insert_one(doc)
    return emp_id

def update_employee(emp_id, data, company_id=None):
    db = get_db()
    f = build_id_filter(emp_id)
    if company_id and company_id != 'ALL':
        f = {'$and': [f, {'company_id': str(company_id)}]}
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
        'updated_at': get_ist_now()
    }
    if 'shift_start' in data and data['shift_start']:
        upd['shift_start'] = str(data['shift_start']).strip()
    if 'shift_end' in data and data['shift_end']:
        upd['shift_end'] = str(data['shift_end']).strip()
    if 'salary_type' in data and data['salary_type']:
        st = str(data['salary_type']).strip().lower()
        if st in ['hourly', 'daily', 'half_day']:
            upd['salary_type'] = st
    photo_val = data.get('photo') or data.get('photo_filename')
    if photo_val:
        upd['photo_filename'] = str(photo_val).strip()
        upd['photo'] = str(photo_val).strip()
    if 'face_embedding' in data and data['face_embedding']:
        upd['face_embedding'] = data['face_embedding']
    if 'company_id' in data and data['company_id']:
        upd['company_id'] = str(data['company_id'])
        
    db.employees.update_one(f, {'$set': upd})
    return True

def delete_employee(emp_id, company_id=None):
    db = get_db()
    f = build_id_filter(emp_id)
    if company_id and company_id != 'ALL':
        f = {'$and': [f, {'company_id': str(company_id)}]}
    db.employees.delete_one(f)
    return True

def get_all_face_embeddings(company_id=None):
    db = get_db()
    q = {'face_embedding': {'$ne': '', '$exists': True}}
    if company_id and company_id != 'ALL':
        q['company_id'] = str(company_id)
    employees = db.employees.find(q)
    results = []
    for emp in employees:
        embedding_data = emp.get('face_embedding', '')
        if embedding_data:
            try:
                embedding = json.loads(embedding_data) if isinstance(embedding_data, str) else embedding_data
                results.append({
                    'id': str(emp.get('id', emp.get('_id', ''))),
                    'employee_name': emp.get('employee_name', ''),
                    'company_id': emp.get('company_id', 'ARGUS_MASTER'),
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

def get_dashboard_stats(company_id=None):
    db = get_db()
    t_filter = {}
    if company_id and company_id != 'ALL':
        t_filter['company_id'] = str(company_id)
        
    total_employees = db.employees.count_documents(t_filter)
    
    # Calculate today's active punches across live punches, attendance, reports, and manual entries
    today_str = get_ist_now().strftime('%Y-%m-%d')
    today_slash = get_ist_now().strftime('%d/%m/%Y')
    
    p_filter = dict(t_filter)
    p_filter['date'] = today_str
    present_names = db.attendance.distinct('employee_name', p_filter)
    
    ar_today_filter = dict(t_filter)
    ar_today_filter['date'] = today_str
    ar_today = db.attendance_reports.distinct('employee_name', ar_today_filter)
    
    l_filter = dict(t_filter)
    l_filter['entry_time'] = {'$regex': today_slash}
    live_today = db.live_entries.distinct('employee_name', l_filter)
    
    m_filter = dict(t_filter)
    m_filter['$or'] = [
        {'entry_date': today_str},
        {'submitted_at': {'$regex': today_str}},
        {'submitted_at': {'$regex': today_slash}}
    ]
    manual_today = db.manual_entries.distinct('employee_name', m_filter)
    
    combined_present = set(present_names).union(set(live_today)).union(set(ar_today)).union(set(manual_today))
    present_count = len(combined_present)
    absent_count = max(0, total_employees - present_count)
    present_percentage = round((present_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    absent_percentage = round((absent_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    
    tout_filter = dict(t_filter)
    tout_filter['is_timeout'] = 1
    timeout_count = db.live_entries.count_documents(tout_filter)
    timeout_percentage = round((timeout_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    
    # Last 7 days dynamic calculation including manual entries
    last_7_days = []
    today = get_ist_now().date()
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        day_slash = day.strftime('%d/%m/%Y')
        label = day.strftime('%d %b')
        
        d_att = dict(t_filter)
        d_att['date'] = day_str
        d_att_names = db.attendance.distinct('employee_name', d_att)
        
        d_ar = dict(t_filter)
        d_ar['date'] = day_str
        d_ar_names = db.attendance_reports.distinct('employee_name', d_ar)
        
        d_me = dict(t_filter)
        d_me['$or'] = [
            {'entry_date': day_str},
            {'submitted_at': {'$regex': day_str}},
            {'submitted_at': {'$regex': day_slash}}
        ]
        d_me_names = db.manual_entries.distinct('employee_name', d_me)
        
        d_live = dict(t_filter)
        d_live['entry_time'] = {'$regex': day_slash}
        d_live_names = db.live_entries.distinct('employee_name', d_live)
        
        d_tout = dict(d_live)
        d_tout['is_timeout'] = 1
        d_tout_cnt = db.live_entries.count_documents(d_tout)
        
        unique_day_present = set(d_att_names).union(set(d_ar_names)).union(set(d_me_names)).union(set(d_live_names))
        day_present_cnt = len(unique_day_present)
        day_absent_cnt = max(0, total_employees - day_present_cnt)
        
        last_7_days.append({
            'date': label,
            'present': day_present_cnt,
            'absent': day_absent_cnt,
            'timeout': d_tout_cnt,
            'count': day_present_cnt
        })
        
    # Monthly stats dynamic calculation across attendance punches and manual entries
    monthly_stats = []
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    curr_year = get_ist_now().year
    curr_month = get_ist_now().month
    for m_idx, m_name in enumerate(months, start=1):
        m_prefix = f"{curr_year}-{m_idx:02d}"
        m_hyphen = f"-{m_idx:02d}-{curr_year}"
        
        mo_att = dict(t_filter)
        mo_att['date'] = {'$regex': f"^{m_prefix}"}
        att_cnt = db.attendance.count_documents(mo_att)
        
        mo_ar = dict(t_filter)
        mo_ar['date'] = {'$regex': f"^{m_prefix}"}
        ar_cnt = db.attendance_reports.count_documents(mo_ar)
        
        mo_me = dict(t_filter)
        mo_me['$or'] = [
            {'entry_date': {'$regex': f"^{m_prefix}"}},
            {'submitted_at': {'$regex': f"^{m_prefix}"}},
            {'submitted_at': {'$regex': m_hyphen}}
        ]
        me_cnt = db.manual_entries.count_documents(mo_me)
        
        mo_tout = dict(t_filter)
        mo_tout['is_timeout'] = 1
        mo_tout['entry_time'] = {'$regex': f"/{m_idx:02d}/{curr_year}"}
        tout_cnt = db.live_entries.count_documents(mo_tout)
        
        total_monthly_punches = att_cnt + ar_cnt + me_cnt
        
        if m_idx <= curr_month and total_employees > 0:
            m_absent = max(0, total_employees * 26 - total_monthly_punches) if total_monthly_punches > 0 else 0
        else:
            m_absent = 0
            
        monthly_stats.append({
            'month': m_name,
            'present': total_monthly_punches,
            'absent': m_absent,
            'timeout': tout_cnt,
            'count': total_monthly_punches
        })
        
    # Today's attendance list & Department summary
    employees = list(db.employees.find(t_filter, {'_id': 0, 'id': 1, 'employee_name': 1, 'department': 1, 'designation': 1}))
    
    p_filter = dict(t_filter)
    p_filter['date'] = today_str
    att_docs = {a['employee_name']: a for a in db.attendance.find(p_filter)}
    
    ar_today_filter = dict(t_filter)
    ar_today_filter['date'] = today_str
    ar_docs = {a['employee_name']: a for a in db.attendance_reports.find(ar_today_filter)}
    
    l_filter = dict(t_filter)
    l_filter['entry_time'] = {'$regex': today_slash}
    live_docs = {l['employee_name']: l for l in db.live_entries.find(l_filter)}
    
    m_filter = dict(t_filter)
    m_filter['$or'] = [
        {'entry_date': today_str},
        {'submitted_at': {'$regex': today_str}},
        {'submitted_at': {'$regex': today_slash}}
    ]
    manual_docs = {m['employee_name']: m for m in db.manual_entries.find(m_filter)}
    
    today_attendance = []
    present_names_set = set()
    timeout_names_set = set()
    
    def format_time_str(t_str):
        if not t_str or t_str == '-':
            return '-'
        parts = str(t_str).strip().split()
        if len(parts) >= 3 and ('AM' in parts or 'PM' in parts):
            time_part = parts[-2]
            ampm = parts[-1]
            time_sub = time_part.split(':')
            if len(time_sub) >= 2:
                return f"{time_sub[0]}:{time_sub[1]} {ampm}"
        elif len(parts) == 2 and ('AM' in parts[1] or 'PM' in parts[1]):
            time_sub = parts[0].split(':')
            if len(time_sub) >= 2:
                return f"{time_sub[0]}:{time_sub[1]} {parts[1]}"
        elif len(parts) == 1 and ':' in parts[0]:
            time_sub = parts[0].split(':')
            if len(time_sub) >= 2:
                return f"{time_sub[0]}:{time_sub[1]}"
        return str(t_str)

    for emp in employees:
        ename = emp.get('employee_name', '')
        in_time = '-'
        out_time = '-'
        hours = '-'
        status = 'Absent'
        
        if ename in live_docs:
            l = live_docs[ename]
            in_time = format_time_str(l.get('entry_time'))
            out_time = format_time_str(l.get('exit_time'))
            hours = str(l.get('total_hours') or '-')
            if l.get('is_timeout') == 1:
                status = 'Timeout'
                timeout_names_set.add(ename)
            else:
                status = 'Present'
                present_names_set.add(ename)
        elif ename in att_docs:
            a = att_docs[ename]
            in_time = format_time_str(a.get('in_time') or a.get('entry_time'))
            out_time = format_time_str(a.get('out_time') or a.get('exit_time'))
            hours = str(a.get('working_hours') or a.get('total_hours') or '-')
            status = 'Present'
            present_names_set.add(ename)
        elif ename in ar_docs:
            ar = ar_docs[ename]
            in_time = format_time_str(ar.get('entry_time'))
            out_time = format_time_str(ar.get('exit_time'))
            hours = str(ar.get('working_hours') or '-')
            status = 'Present'
            present_names_set.add(ename)
        elif ename in manual_docs:
            m = manual_docs[ename]
            in_time = format_time_str(m.get('in_time') or m.get('entry_time'))
            out_time = format_time_str(m.get('out_time') or m.get('exit_time'))
            hours = str(m.get('working_hours') or m.get('hours') or '-')
            status = 'Present'
            present_names_set.add(ename)
            
        today_attendance.append({
            'employee_name': ename,
            'department': emp.get('department') or emp.get('designation') or 'General',
            'in_time': in_time,
            'out_time': out_time,
            'hours': hours,
            'status': status
        })
        
    status_order = {'Present': 0, 'Timeout': 1, 'Absent': 2}
    today_attendance.sort(key=lambda x: (status_order.get(x['status'], 3), x['employee_name']))
    for idx, item in enumerate(today_attendance, 1):
        item['index'] = idx
        
    # Department Wise Summary
    dept_map = {}
    for emp in employees:
        dept = emp.get('department') or emp.get('designation') or 'General'
        if not dept:
            dept = 'General'
        if dept not in dept_map:
            dept_map[dept] = {'department': dept, 'total': 0, 'present': 0, 'absent': 0, 'timeout': 0}
        dept_map[dept]['total'] += 1
        ename = emp.get('employee_name', '')
        if ename in timeout_names_set:
            dept_map[dept]['timeout'] += 1
        elif ename in present_names_set:
            dept_map[dept]['present'] += 1
        else:
            dept_map[dept]['absent'] += 1
            
    department_summary = list(dept_map.values())
    department_summary.sort(key=lambda x: x['total'], reverse=True)
    
    return {
        'total': total_employees,
        'present': present_count,
        'absent': absent_count,
        'present_percentage': present_percentage,
        'present_percent': f"{present_percentage}%",
        'absent_percentage': absent_percentage,
        'absent_percent': f"{absent_percentage}%",
        'timeout': timeout_count,
        'timeout_percentage': timeout_percentage,
        'timeout_percent': f"{timeout_percentage}%",
        'last_7_days': last_7_days,
        'monthly_stats': monthly_stats,
        'today_attendance': today_attendance,
        'department_summary': department_summary
    }

# ----------------- LIVE & TIMEOUT ENTRIES ----------------- #

def process_company_timeout_entries(company_id=None):
    """
    Checks for employees who punched in and forgot to punch out.
    If current IST time exceeds (entry_time + company.shift_hours),
    automatically completes their punch-out according to the company shift time.
    """
    db = get_db()
    now = get_ist_now()
    
    rep_query = {'exit_time': '----'}
    if company_id and company_id != 'ALL':
        rep_query['company_id'] = str(company_id)
        
    pending_reps = list(db.attendance_reports.find(rep_query))
    if not pending_reps:
        return 0
        
    company_shifts = {}
    auto_count = 0
    
    for rep in pending_reps:
        cid = rep.get('company_id', 'ARGUS_MASTER')
        if cid not in company_shifts:
            comp = db.company_admin.find_one({'id': str(cid)})
            company_shifts[cid] = comp.get('shift_hours', '08:00') if comp else '08:00'
            
        shift_str = company_shifts[cid]
        shift_h = 8
        shift_m = 0
        try:
            if ':' in shift_str:
                sp = shift_str.split(':')
                shift_h = int(sp[0])
                shift_m = int(sp[1])
            else:
                shift_h = int(float(shift_str))
        except Exception:
            shift_h = 8
            shift_m = 0
            
        shift_mins = shift_h * 60 + shift_m
        if shift_mins <= 0:
            shift_mins = 480
            shift_h = 8
            shift_m = 0
            
        entry_time_str = rep.get('entry_time', '')
        entry_dt = None
        for fmt in ['%d/%m/%Y %I:%M:%S %p', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%d-%m-%Y %I:%M:%S %p']:
            try:
                entry_dt = datetime.strptime(entry_time_str.strip(), fmt)
                break
            except Exception:
                pass
                
        if not entry_dt:
            try:
                entry_dt = datetime.fromisoformat(rep.get('created_at', ''))
            except Exception:
                continue
                
        if entry_dt.tzinfo is None:
            entry_dt = entry_dt.replace(tzinfo=IST)
            
        auto_exit_dt = entry_dt + timedelta(minutes=shift_mins)
        
        # If current time is past scheduled shift exit, auto timeout punch-out
        if now >= auto_exit_dt:
            auto_exit_str = auto_exit_dt.strftime('%d/%m/%Y %I:%M:%S %p')
            working_hours_str = f"{shift_h:02d}:{shift_m:02d}"
            
            emp_name = rep.get('employee_name', '')
            emp = db.employees.find_one({'employee_name': emp_name})
            salary_type = str(emp.get('salary_type') or 'hourly').strip().lower() if emp else 'hourly'
            hourly_rate = float(emp.get('hourly_salary', 0.0)) if emp else 100.0
            day_rate = float(emp.get('day_salary', 0.0)) if emp else (hourly_rate * 8.0)
            half_rate = float(emp.get('half_day_salary', 0.0)) if emp else (day_rate / 2.0)
            
            day_credit_type = 'Full Day'
            working_salary = 0.0
            if salary_type == 'hourly':
                working_salary = round((shift_mins / 60.0) * hourly_rate, 2)
            elif salary_type == 'daily':
                working_salary = day_rate
            elif salary_type == 'half_day':
                working_salary = half_rate * 2.0
            else:
                working_salary = round((shift_mins / 60.0) * hourly_rate, 2)
                
            db.attendance_reports.update_one(
                {'_id': rep['_id']},
                {'$set': {
                    'exit_time': auto_exit_str,
                    'exit_distance': '0.0M (AUTO TIMEOUT)',
                    'exit_location': f"Auto Punch-Out based on Company Shift Time ({shift_str})",
                    'working_hours': working_hours_str,
                    'shift_variance': '00:00',
                    'day_credit_type': day_credit_type,
                    'working_salary': working_salary,
                    'is_timeout': 1,
                    'entry_type': rep.get('entry_type', 'proper'),
                    'updated_at': now.isoformat()
                }}
            )
            
            timeout_filter = {
                'company_id': str(cid),
                'employee_name': emp_name,
                'is_timeout': 1,
                'entry_time': auto_exit_str
            }
            if not db.live_entries.find_one(timeout_filter):
                db.live_entries.insert_one({
                    'company_id': str(cid),
                    'employee_id': rep.get('employee_id', ''),
                    'employee_name': emp_name,
                    'entry_time': auto_exit_str,
                    'site_name': 'OFFICE (AUTO TIMEOUT)',
                    'entry_location': f"Auto Punch-Out based on Company Shift ({shift_str})",
                    'entry_distance': 0.0,
                    'is_timeout': 1,
                    'created_at': now.isoformat()
                })
            auto_count += 1
            
    return auto_count

def get_live_report_entries(tab='live', start_date=None, end_date=None, search=None, page=1, limit=10, company_id=None):
    process_company_timeout_entries(company_id=company_id)
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
        
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

def calculate_realistic_proximity(user_lat, user_lng, office_lat=OFFICE_LAT, office_lng=OFFICE_LNG):
    """Calculate distance in meters, with realistic office vicinity variation (12m - 45m) if desktop coordinates match exactly."""
    if user_lat is None or user_lng is None:
        import random
        return random.uniform(12.0, 35.0)
    try:
        ulat = float(user_lat)
        ulng = float(user_lng)
        olat = float(office_lat if office_lat is not None else OFFICE_LAT)
        olng = float(office_lng if office_lng is not None else OFFICE_LNG)
        d = calculate_distance_meters(ulat, ulng, olat, olng)
        if d < 5.0:
            import random
            return round(random.uniform(8.5, 24.5), 1)
        return round(d, 1)
    except Exception:
        return 14.5

def add_live_entry(employee_id, employee_name, entry_time=None, site_name='OFFICE', entry_location=OFFICE_LOCATION_STR, entry_distance=0.0, is_timeout=0, user_lat=None, user_lng=None, company_id='ARGUS_MASTER', target_lat=None, target_lng=None):
    db = get_db()
    if not entry_time:
        entry_time = get_ist_now().strftime('%d/%m/%Y %I:%M:%S %p')
        
    calculated_meters = float(entry_distance or 0.0)
    if calculated_meters > 0.0:
        pass
    elif user_lat is not None and user_lng is not None:
        try:
            calculated_meters = calculate_realistic_proximity(user_lat, user_lng, office_lat=target_lat, office_lng=target_lng)
        except Exception:
            calculated_meters = 14.5
    elif calculated_meters == 0.0:
        calculated_meters = calculate_realistic_proximity(None, None, office_lat=target_lat, office_lng=target_lng)
            
    doc = {
        'company_id': str(company_id or 'ARGUS_MASTER'),
        'employee_id': str(employee_id),
        'employee_name': employee_name,
        'entry_time': entry_time,
        'site_name': site_name,
        'entry_location': entry_location,
        'entry_distance': round(calculated_meters, 2),
        'formatted_distance': format_office_distance(calculated_meters),
        'is_timeout': int(is_timeout),
        'created_at': get_ist_now().isoformat()
    }
    result = db.live_entries.insert_one(doc)
    return str(result.inserted_id)

def record_face_attendance(employee_id, employee_name, user_lat=None, user_lng=None, company_id=None, client_time=None):
    """
    Punch In / Punch Out Attendance Lifecycle Engine with Multi-Tenant Geolocation Support:
    1. Records Live Entry in db.live_entries with company_id in 12-hour format (IST).
    2. Resolves company office coordinates from company_admin if tenant-owned.
    3. Handles Punch In & Punch Out lifecycle under exact company_id.
    """
    db = get_db()
    now = get_ist_now()
    now_time_12 = client_time.strip() if client_time and client_time.strip() else now.strftime('%d/%m/%Y %I:%M:%S %p')
    today_date = now.strftime('%Y-%m-%d')
    today_slash = now.strftime('%d/%m/%Y')
    
    # Get employee details for hourly/day rate, shift, and company_id
    emp = db.employees.find_one(build_id_filter(employee_id))
    if not emp:
        emp = db.employees.find_one({'employee_name': employee_name})
        
    comp_id = str(company_id or (emp.get('company_id') if emp else None) or 'ARGUS_MASTER')
    
    # Determine office coordinates and location string for this company
    target_lat = OFFICE_LAT
    target_lng = OFFICE_LNG
    loc_str = OFFICE_LOCATION_STR
    if comp_id != 'ARGUS_MASTER':
        comp = db.company_admin.find_one({'id': comp_id})
        if comp:
            target_lat = float(comp.get('latitude') or OFFICE_LAT)
            target_lng = float(comp.get('longitude') or OFFICE_LNG)
            loc_str = f"{comp.get('company_name', 'Company')} Premises"
            
    # Calculate proximity distance
    dist_meters = calculate_realistic_proximity(user_lat, user_lng, target_lat, target_lng)
    formatted_dist = format_office_distance(dist_meters)
    
    # 1. Create Live Entry
    live_id = add_live_entry(
        employee_id=employee_id,
        employee_name=employee_name,
        entry_time=now_time_12,
        site_name='OFFICE',
        entry_location=loc_str,
        entry_distance=dist_meters,
        is_timeout=0,
        user_lat=user_lat,
        user_lng=user_lng,
        company_id=comp_id
    )
    
    salary_type = str(emp.get('salary_type') or 'hourly').strip().lower() if emp else 'hourly'
    hourly_rate = float(emp.get('hourly_salary', 0.0)) if emp else 100.0
    day_rate = float(emp.get('day_salary', 0.0)) if emp else (hourly_rate * 8.0)
    half_rate = float(emp.get('half_day_salary', 0.0)) if emp else (day_rate / 2.0)
    shift_hours_str = emp.get('shift_hours', '08:00') if emp else '08:00'
    
    # Check if there is already an attendance report entry today
    report_filter = {
        'company_id': comp_id,
        'employee_name': employee_name,
        '$or': [
            {'date': today_date},
            {'entry_time': {'$regex': f'^{today_slash}'}}
        ]
    }
    
    existing_rep = db.attendance_reports.find_one(report_filter, sort=[('created_at', DESCENDING)])
    
    if not existing_rep or (existing_rep.get('exit_time') and existing_rep.get('exit_time') != '----'):
        # Geofencing threshold: 2000 meters (<= 2000m is proper, > 2000m is improper)
        punch_in_entry_type = 'proper' if dist_meters <= 2000.0 else 'improper'
        rep_doc = {
            'company_id': comp_id,
            'employee_id': str(employee_id),
            'employee_name': employee_name,
            'date': today_date,
            'entry_time': now_time_12,
            'entry_distance': formatted_dist,
            'entry_location': loc_str,
            'exit_time': '----',
            'exit_distance': '----',
            'exit_location': '----',
            'working_hours': '00:00',
            'shift_variance': '----',
            'salary_type': salary_type,
            'day_credit_type': 'Pending',
            'working_salary': 0,
            'entry_type': punch_in_entry_type,
            'created_at': now.isoformat()
        }
        db.attendance_reports.insert_one(rep_doc)
        
        # Upsert in db.attendance for dashboard present stat
        db.attendance.update_one(
            {'company_id': comp_id, 'employee_name': employee_name, 'date': today_date},
            {'$set': {'company_id': comp_id, 'employee_name': employee_name, 'date': today_date, 'status': 'Present', 'updated_at': now}},
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
                if entry_dt.tzinfo is None:
                    entry_dt = entry_dt.replace(tzinfo=IST)
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
        if shift_target_minutes <= 0:
            shift_target_minutes = 480
            
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
            
        # Calculate Working Salary accurately based on employee salary_type
        half_shift_target = max(1, shift_target_minutes // 2)
        computed_salary = 0
        day_credit_type = 'Full Day'

        if salary_type == 'hourly':
            computed_salary = int(round((working_minutes / 60.0) * hourly_rate))
            if working_minutes >= shift_target_minutes:
                day_credit_type = 'Full Day'
            elif working_minutes >= half_shift_target:
                day_credit_type = 'Half Day'
            else:
                day_credit_type = 'Partial'

        elif salary_type == 'daily':
            # Day-Based Employee:
            # Full Day if worked >= shift_target_minutes (strict, no grace)
            if working_minutes >= shift_target_minutes:
                computed_salary = int(round(day_rate))
                day_credit_type = 'Full Day'
            # Half Day if worked >= half_shift_target (strict, no grace)
            elif working_minutes >= half_shift_target:
                effective_half = half_rate if half_rate > 0 else (day_rate / 2.0)
                computed_salary = int(round(effective_half))
                day_credit_type = 'Half Day'
            else:
                effective_hourly = hourly_rate if hourly_rate > 0 else (day_rate / (shift_target_minutes / 60.0))
                computed_salary = int(round((working_minutes / 60.0) * effective_hourly))
                day_credit_type = 'Partial'

        elif salary_type == 'half_day':
            effective_half = half_rate if half_rate > 0 else (day_rate / 2.0 if day_rate > 0 else (hourly_rate * 4.0))
            if working_minutes >= shift_target_minutes:
                computed_salary = int(round(effective_half * 2.0))
                day_credit_type = 'Full Day (2x Half)'
            elif working_minutes >= half_shift_target:
                computed_salary = int(round(effective_half))
                day_credit_type = 'Half Day'
            else:
                computed_salary = int(round((working_minutes / float(half_shift_target)) * effective_half))
                day_credit_type = 'Partial'
        else:
            computed_salary = int(round((working_minutes / 60.0) * hourly_rate))
            
        # Determine final entry_type: Proper only if BOTH punch-in and punch-out are <= 2000m
        in_entry_type = existing_rep.get('entry_type', 'proper')
        out_is_proper = (dist_meters <= 2000.0)
        final_entry_type = 'proper' if (in_entry_type == 'proper' and out_is_proper) else 'improper'

        upd_data = {
            'exit_time': now_time_12,
            'exit_distance': formatted_dist,
            'exit_location': loc_str,
            'working_hours': working_hours_str,
            'shift_variance': shift_variance_str,
            'salary_type': salary_type,
            'day_credit_type': day_credit_type,
            'working_salary': computed_salary,
            'entry_type': final_entry_type,
            'updated_at': now.isoformat()
        }
        db.attendance_reports.update_one({'_id': existing_rep['_id']}, {'$set': upd_data})
        
        # Update db.attendance
        db.attendance.update_one(
            {'company_id': comp_id, 'employee_name': employee_name, 'date': today_date},
            {'$set': {'company_id': comp_id, 'working_hours': working_hours_str, 'status': 'Present', 'updated_at': now}},
            upsert=True
        )
        return {'status': 'punch_out', 'live_id': live_id, 'formatted_dist': formatted_dist, 'working_hours': working_hours_str}

# ----------------- ATTENDANCE REPORTS ----------------- #

def get_attendance_reports(report_type='all', start_date=None, end_date=None, employee='All', search=None, page=1, limit=10, company_id=None):
    db = get_db()

    if report_type == 'manual':
        m_query = {}
        if company_id and company_id != 'ALL':
            m_query['company_id'] = str(company_id)
        if employee and employee != 'All':
            m_query['employee_name'] = employee
        if start_date:
            m_query.setdefault('entry_date', {})['$gte'] = start_date.strip()
        if end_date:
            m_query.setdefault('entry_date', {})['$lte'] = end_date.strip()
        if search:
            reg = {'$regex': re.escape(search), '$options': 'i'}
            m_query['$or'] = [{'employee_name': reg}, {'entry_date': reg}, {'status': reg}]
            
        total = db.manual_entries.count_documents(m_query)
        cursor = db.manual_entries.find(m_query).sort([("entry_date", DESCENDING), ("created_at", DESCENDING)])
        if limit and limit > 0:
            cursor = cursor.skip((page - 1) * limit).limit(limit)
        data = []
        for doc in cursor:
            c = clean_doc(doc)
            data.append({
                'employee_name': c.get('employee_name', ''),
                'entry_time': c.get('submitted_at') or c.get('entry_date', ''),
                'entry_distance': 'MANUAL ENTRY',
                'entry_location': f"Manual Adjustment ({c.get('status', 'Proper')})",
                'exit_time': '----',
                'exit_distance': '----',
                'exit_location': '----',
                'working_hours': c.get('hours', '00:00'),
                'shift_variance': '----',
                'working_salary': c.get('working_salary', 0),
                'entry_type': 'manual'
            })
        return {
            'total': total,
            'page': page,
            'limit': limit,
            'data': data
        }

    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
        
    if report_type == 'proper':
        query['entry_type'] = {'$ne': 'improper'}
    elif report_type == 'improper':
        query['entry_type'] = 'improper'
        
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
    cursor = db.attendance_reports.find(query).sort([("date", DESCENDING), ("created_at", DESCENDING), ("_id", DESCENDING)])
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': data
    }

def get_attendance_simple_table(employee='All', start_date=None, end_date=None, company_id=None):
    db = get_db()
    
    clean_emp = str(employee or '').strip()
    is_all_emp = (clean_emp in ['All', 'All Employees', '', 'None'])
    
    def extract_iso_date(val):
        if not val:
            return ''
        s = str(val).strip()
        m = re.search(r'(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])', s)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        m2 = re.search(r'(0[1-9]|[12]\d|3[01])[-/](0[1-9]|1[0-2])[-/](20\d{2})', s)
        if m2:
            return f"{m2.group(3)}-{m2.group(2)}-{m2.group(1)}"
        return ''

    s_iso = extract_iso_date(start_date) if start_date else ''
    e_iso = extract_iso_date(end_date) if end_date else ''

    # Pre-fetch employees in company for rate configurations
    emp_filter = {}
    if company_id and company_id != 'ALL':
        emp_filter['company_id'] = str(company_id)
    emp_docs = list(db.employees.find(emp_filter))
    emp_map = {e.get('employee_name'): clean_doc(e) for e in emp_docs if e.get('employee_name')}

    def calc_salary(emp_name, hours_str):
        emp_info = emp_map.get(emp_name)
        if not emp_info:
            return 0.0
        stype = str(emp_info.get('salary_type') or 'hourly').lower()
        hr_rate = float(emp_info.get('hourly_salary') or 0.0)
        d_rate = float(emp_info.get('day_salary') or 0.0)
        h_rate = float(emp_info.get('half_day_salary') or 0.0)
        if hr_rate <= 0 and d_rate > 0:
            hr_rate = d_rate / 8.0

        shift_str = emp_info.get('shift_hours', '08:00') or '08:00'
        shift_mins = 480
        try:
            sp = str(shift_str).split(':')
            shift_mins = int(sp[0]) * 60 + int(sp[1])
        except Exception:
            shift_mins = 480
        if shift_mins <= 0:
            shift_mins = 480
        half_shift = max(1, shift_mins // 2)

        tot_mins = 0
        try:
            parts = str(hours_str or '').split(':')
            if len(parts) >= 2:
                tot_mins = int(parts[0]) * 60 + int(parts[1])
        except Exception:
            tot_mins = 0

        if tot_mins <= 0:
            return 0.0

        if stype == 'hourly':
            return round((tot_mins / 60.0) * hr_rate, 2)
        elif stype == 'daily':
            if tot_mins >= shift_mins:
                return round(d_rate, 2)
            elif tot_mins >= half_shift:
                eff_h = h_rate if h_rate > 0 else (d_rate / 2.0)
                return round(eff_h, 2)
            else:
                eff_hr = hr_rate if hr_rate > 0 else (d_rate / (shift_mins / 60.0))
                return round((tot_mins / 60.0) * eff_hr, 2)
        elif stype == 'half_day':
            eff_h = h_rate if h_rate > 0 else (d_rate / 2.0 if d_rate > 0 else hr_rate * 4.0)
            if tot_mins >= shift_mins:
                return round(eff_h * 2.0, 2)
            elif tot_mins >= half_shift:
                return round(eff_h, 2)
            else:
                return round((tot_mins / float(half_shift)) * eff_h, 2)
        else:
            return round((tot_mins / 60.0) * hr_rate, 2)

    data = []

    # 1. Fetch Facial Attendance Punches (attendance_reports)
    rep_query = {}
    if company_id and company_id != 'ALL':
        rep_query['company_id'] = str(company_id)
    if not is_all_emp:
        rep_query['employee_name'] = clean_emp

    for doc in db.attendance_reports.find(rep_query):
        r = clean_doc(doc)
        rec_date = extract_iso_date(r.get('date') or r.get('entry_time') or r.get('created_at'))
        if s_iso and rec_date and rec_date < s_iso:
            continue
        if e_iso and rec_date and rec_date > e_iso:
            continue

        emp_name = r.get('employee_name', '')
        entry_t = r.get('entry_time') or r.get('date') or ''
        exit_t = r.get('exit_time') or '----'
        wh = r.get('working_hours', '00:00')
        sv = r.get('shift_variance', '----')
        is_improper = (str(r.get('entry_type', '')).lower() == 'improper')

        if is_improper:
            w_sal = 0.0
            status_label = 'Improper'
        else:
            raw_sal = r.get('working_salary')
            if raw_sal is not None and float(raw_sal) > 0:
                w_sal = float(raw_sal)
            else:
                w_sal = calc_salary(emp_name, wh)
            status_label = r.get('status') or 'Proper'

        data.append({
            'employee_name': emp_name,
            'entry_time': entry_t,
            'exit_time': exit_t,
            'working_hours': wh,
            'shift_variance': sv,
            'working_salary': round(w_sal, 2),
            'status': status_label,
            'sort_key': rec_date or entry_t,
            'is_improper': is_improper,
            'source': 'punch'
        })

    # 2. Fetch Manual Entries (manual_entries)
    m_query = {}
    if company_id and company_id != 'ALL':
        m_query['company_id'] = str(company_id)
    if not is_all_emp:
        m_query['employee_name'] = clean_emp

    for doc in db.manual_entries.find(m_query):
        m = clean_doc(doc)
        rec_date = extract_iso_date(m.get('entry_date') or m.get('submitted_at') or m.get('created_at'))
        if s_iso and rec_date and rec_date < s_iso:
            continue
        if e_iso and rec_date and rec_date > e_iso:
            continue

        emp_name = m.get('employee_name', '')
        raw_date = m.get('entry_date', '')
        if rec_date and '-' in rec_date:
            parts = rec_date.split('-')
            fmt_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
        else:
            fmt_date = raw_date
        
        sub_at = m.get('submitted_at', '')
        time_part = "05:30:00"
        if sub_at and (' ' in sub_at or ':' in sub_at):
            t_match = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)', sub_at, re.I)
            if t_match:
                time_part = t_match.group(1)
        entry_t = f"{fmt_date} {time_part}".strip()

        wh = m.get('hours', '00:00')
        raw_status = (m.get('status') or 'Manual').strip()
        is_improper = (raw_status.lower() == 'improper')

        if is_improper:
            w_sal = 0.0
            status_label = 'Improper'
        else:
            raw_sal = m.get('working_salary')
            if raw_sal is not None and float(raw_sal) > 0:
                w_sal = float(raw_sal)
            else:
                w_sal = calc_salary(emp_name, wh)
            status_label = 'Manual' if raw_status in ['Proper', 'Full Day', 'Half Day', 'Manual', 'Others', 'Permission'] else raw_status

        data.append({
            'employee_name': emp_name,
            'entry_time': entry_t,
            'exit_time': '',
            'working_hours': wh,
            'shift_variance': '',
            'working_salary': round(w_sal, 2),
            'status': status_label,
            'sort_key': rec_date or entry_t,
            'is_improper': is_improper,
            'source': 'manual'
        })

    # Sort descending by sort_key then entry_time
    data.sort(key=lambda x: (x.get('sort_key', ''), x.get('entry_time', '')), reverse=True)

    # Compute Totals
    total_minutes = 0
    total_salary = 0.0

    for r in data:
        wh = r.get('working_hours', '00:00')
        parts = wh.split(':')
        if len(parts) >= 2:
            try:
                total_minutes += int(parts[0]) * 60 + int(parts[1])
            except ValueError:
                pass
        if not r.get('is_improper'):
            total_salary += float(r.get('working_salary', 0.0))

    tot_h = total_minutes // 60
    tot_m = total_minutes % 60
    formatted_total_hours = f"{tot_h:02d}:{tot_m:02d}"
    formatted_total_salary = f"{total_salary:.2f}"

    return {
        'data': data,
        'total_working_hours': formatted_total_hours,
        'total_working_salary': formatted_total_salary
    }

# ----------------- MANUAL ENTRIES ----------------- #

def get_manual_entries(from_date=None, to_date=None, status='All', search=None, page=1, limit=10, company_id=None):
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
        
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
    cursor = db.manual_entries.find(query).sort([("entry_date", DESCENDING), ("created_at", DESCENDING), ("id", DESCENDING), ("_id", DESCENDING)])
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': data
    }

def get_manual_entry_by_id(entry_id, company_id=None):
    db = get_db()
    f = build_id_filter(entry_id)
    if company_id and company_id != 'ALL':
        f = {'$and': [f, {'company_id': str(company_id)}]}
    doc = db.manual_entries.find_one(f)
    return clean_doc(doc)

def create_manual_entry(data, company_id=None):
    db = get_db()
    emp_name = data.get('employee_name', '')
    emp = db.employees.find_one({'employee_name': emp_name})
    hourly_rate = float(emp['hourly_salary'] if emp and 'hourly_salary' in emp else 1.0)
    day_rate = float(emp['day_salary'] if emp and 'day_salary' in emp else 0.0)
    half_rate = float(emp['half_day_salary'] if emp and 'half_day_salary' in emp else 0.0)
    emp_id = emp['id'] if emp and 'id' in emp else 'EMP_' + str(int(time.time()))
    assigned_company_id = str(company_id or data.get('company_id') or (emp.get('company_id') if emp else None) or 'ARGUS_MASTER')
    
    hours_str = data.get('hours', '00:00')
    mode = data.get('mode', 'Hours')
    status = data.get('status', 'Proper')
    salary_type = str(emp.get('salary_type') or 'hourly').strip().lower() if emp else 'hourly'
    shift_hours_str = emp.get('shift_hours', '08:00') if emp else '08:00'
    shift_target_minutes = 480
    try:
        sp = shift_hours_str.split(':')
        shift_target_minutes = int(sp[0]) * 60 + int(sp[1])
    except Exception:
        shift_target_minutes = 480
    if shift_target_minutes <= 0:
        shift_target_minutes = 480
    half_shift_target = max(1, shift_target_minutes // 2)

    working_salary = 0.0
    if mode == 'Salary':
        working_salary = float(data.get('working_salary') or 0.0)
    elif mode == 'Full Day' or status == 'Full Day':
        working_salary = day_rate if day_rate > 0 else (hourly_rate * (shift_target_minutes / 60.0))
    elif mode == 'Half Day' or status == 'Half Day':
        working_salary = half_rate if half_rate > 0 else (day_rate / 2.0 if day_rate > 0 else (hourly_rate * 4.0))
    else:
        parts = hours_str.split(':')
        total_mins = 0
        if len(parts) >= 2:
            try:
                hrs = int(parts[0])
                mins = int(parts[1])
                total_mins = hrs * 60 + mins
            except ValueError:
                total_mins = 0
        if salary_type == 'hourly':
            working_salary = round((total_mins / 60.0) * hourly_rate, 2)
        elif salary_type == 'daily':
            if total_mins >= shift_target_minutes:
                working_salary = day_rate
            elif total_mins >= half_shift_target:
                working_salary = half_rate if half_rate > 0 else (day_rate / 2.0)
            else:
                effective_hour = hourly_rate if hourly_rate > 0 else (day_rate / (shift_target_minutes / 60.0))
                working_salary = round((total_mins / 60.0) * effective_hour, 2)
        elif salary_type == 'half_day':
            effective_half = half_rate if half_rate > 0 else (day_rate / 2.0)
            if total_mins >= shift_target_minutes:
                working_salary = effective_half * 2.0
            elif total_mins >= half_shift_target:
                working_salary = effective_half
            else:
                working_salary = round((total_mins / float(half_shift_target)) * effective_half, 2)
        else:
            working_salary = round((total_mins / 60.0) * hourly_rate, 2)
        
    entry_type = str(data.get('entry_type', 'Add')).strip()
    if entry_type.lower() == 'sub':
        working_salary = -abs(working_salary)

    now_ts = get_ist_now().strftime("%d-%m-%Y %I:%M:%S %p")
    entry_id = int(time.time() * 1000)
    
    doc = {
        'id': entry_id,
        'company_id': assigned_company_id,
        'employee_id': emp_id,
        'employee_name': emp_name,
        'entry_date': data.get('entry_date', ''),
        'hours': hours_str,
        'status': status,
        'submitted_at': now_ts,
        'hourly_rate': hourly_rate,
        'day_rate': day_rate,
        'half_rate': half_rate,
        'salary_type': salary_type,
        'working_salary': working_salary,
        'entry_type': entry_type,
        'mode': mode,
        'created_at': get_ist_now().isoformat()
    }
    db.manual_entries.insert_one(doc)
    return entry_id

def update_manual_entry(entry_id, data):
    db = get_db()
    emp_name = data.get('employee_name', '')
    emp = db.employees.find_one({'employee_name': emp_name})
    hourly_rate = float(emp['hourly_salary'] if emp and 'hourly_salary' in emp else 1.0)
    day_rate = float(emp['day_salary'] if emp and 'day_salary' in emp else 0.0)
    half_rate = float(emp['half_day_salary'] if emp and 'half_day_salary' in emp else 0.0)
    salary_type = str(emp.get('salary_type') or 'hourly').strip().lower() if emp else 'hourly'
    shift_hours_str = emp.get('shift_hours', '08:00') if emp else '08:00'
    shift_target_minutes = 480
    try:
        sp = shift_hours_str.split(':')
        shift_target_minutes = int(sp[0]) * 60 + int(sp[1])
    except Exception:
        shift_target_minutes = 480
    if shift_target_minutes <= 0:
        shift_target_minutes = 480
    half_shift_target = max(1, shift_target_minutes // 2)

    hours_str = data.get('hours', '00:00')
    mode = data.get('mode', 'Hours')
    status = data.get('status', 'Proper')
    
    working_salary = 0.0
    if mode == 'Salary':
        working_salary = float(data.get('working_salary') or 0.0)
    elif mode == 'Full Day' or status == 'Full Day':
        working_salary = day_rate if day_rate > 0 else (hourly_rate * (shift_target_minutes / 60.0))
    elif mode == 'Half Day' or status == 'Half Day':
        working_salary = half_rate if half_rate > 0 else (day_rate / 2.0 if day_rate > 0 else (hourly_rate * 4.0))
    else:
        parts = hours_str.split(':')
        total_mins = 0
        if len(parts) >= 2:
            try:
                hrs = int(parts[0])
                mins = int(parts[1])
                total_mins = hrs * 60 + mins
            except ValueError:
                total_mins = 0
        if salary_type == 'hourly':
            working_salary = round((total_mins / 60.0) * hourly_rate, 2)
        elif salary_type == 'daily':
            if total_mins >= shift_target_minutes:
                working_salary = day_rate
            elif total_mins >= half_shift_target:
                working_salary = half_rate if half_rate > 0 else (day_rate / 2.0)
            else:
                effective_hour = hourly_rate if hourly_rate > 0 else (day_rate / (shift_target_minutes / 60.0))
                working_salary = round((total_mins / 60.0) * effective_hour, 2)
        elif salary_type == 'half_day':
            effective_half = half_rate if half_rate > 0 else (day_rate / 2.0)
            if total_mins >= shift_target_minutes:
                working_salary = effective_half * 2.0
            elif total_mins >= half_shift_target:
                working_salary = effective_half
            else:
                working_salary = round((total_mins / float(half_shift_target)) * effective_half, 2)
        else:
            working_salary = round((total_mins / 60.0) * hourly_rate, 2)
        
    entry_type = str(data.get('entry_type', 'Add')).strip()
    if entry_type.lower() == 'sub':
        working_salary = -abs(working_salary)

    upd = {
        'employee_name': emp_name,
        'entry_date': data.get('entry_date', ''),
        'hours': hours_str,
        'status': status,
        'entry_type': entry_type,
        'mode': mode,
        'hourly_rate': hourly_rate,
        'day_rate': day_rate,
        'half_rate': half_rate,
        'salary_type': salary_type,
        'working_salary': working_salary
    }
    db.manual_entries.update_one(build_id_filter(entry_id), {'$set': upd})
    return True

def delete_manual_entry(entry_id):
    db = get_db()
    db.manual_entries.delete_one(build_id_filter(entry_id))
    return True

# ----------------- PAYMENT MANAGEMENT ----------------- #

def get_payments(employee=None, start_date=None, end_date=None, bank=None, payment_type=None, reason=None, search=None, page=1, limit=10, company_id=None):
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
        
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
    cursor = db.payments.find(query).sort([("payment_date", DESCENDING), ("created_at", DESCENDING), ("id", DESCENDING), ("_id", DESCENDING)])
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': data
    }

def get_payment_by_id(payment_id, company_id=None):
    db = get_db()
    f = build_id_filter(payment_id)
    if company_id and company_id != 'ALL':
        f = {'$and': [f, {'company_id': str(company_id)}]}
    doc = db.payments.find_one(f)
    return clean_doc(doc)

def create_payment(data, company_id=None):
    db = get_db()
    emp_name = data.get('employee_name', '')
    emp = db.employees.find_one({'employee_name': emp_name})
    emp_id = emp['id'] if emp and 'id' in emp else 'EMP_' + str(int(time.time()))
    assigned_company_id = str(company_id or data.get('company_id') or (emp.get('company_id') if emp else None) or 'ARGUS_MASTER')
    
    now_ts = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
    payment_date = data.get('payment_date') or datetime.now().strftime("%Y-%m-%d")
    amount = float(data.get('amount') or 0.0)
    bank = data.get('bank', '').strip()
    payment_type = data.get('payment_type', 'UPI')
    reason = data.get('reason', 'Advance Repayment')
    receipt_filename = data.get('receipt_filename', '')
    
    doc = {
        'id': int(time.time() * 1000),
        'company_id': assigned_company_id,
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

def get_advances(employee=None, start_date=None, end_date=None, search=None, page=1, limit=10, company_id=None):
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
        
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
    cursor = db.advances.find(query).sort([("advance_date", DESCENDING), ("created_at", DESCENDING), ("id", DESCENDING), ("_id", DESCENDING)])
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = [clean_doc(doc) for doc in cursor]
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': data
    }

def get_advance_by_id(advance_id, company_id=None):
    db = get_db()
    f = build_id_filter(advance_id)
    if company_id and company_id != 'ALL':
        f = {'$and': [f, {'company_id': str(company_id)}]}
    doc = db.advances.find_one(f)
    return clean_doc(doc)

def create_advance(data, company_id=None):
    db = get_db()
    emp_name = data.get('employee_name', '')
    emp = db.employees.find_one({'employee_name': emp_name})
    emp_id = emp['id'] if emp and 'id' in emp else 'EMP_' + str(int(time.time()))
    assigned_company_id = str(company_id or data.get('company_id') or (emp.get('company_id') if emp else None) or 'ARGUS_MASTER')
    
    now_ts = datetime.now().strftime("%d-%m-%Y %I:%M:%S %p")
    advance_date = data.get('advance_date') or datetime.now().strftime("%Y-%m-%d")
    amount = float(data.get('amount') or 0.0)
    
    doc = {
        'id': int(time.time() * 1000),
        'company_id': assigned_company_id,
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

def get_balance_report(employee=None, search=None, page=1, limit=10, company_id=None):
    db = get_db()
    
    # Query all advances
    adv_query = {}
    if company_id and company_id != 'ALL':
        adv_query['company_id'] = str(company_id)
    if employee and employee != 'All':
        adv_query['employee_name'] = employee
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        adv_query['$or'] = [{'employee_name': reg}, {'timestamp': reg}, {'advance_date': reg}]
        
    adv_cursor = db.advances.find(adv_query)
    
    # Query all advance repayments
    rep_query = {'reason': 'Advance Repayment'}
    if company_id and company_id != 'ALL':
        rep_query['company_id'] = str(company_id)
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
        
    combined.sort(key=lambda x: (x.get('date', '') or x.get('timestamp', ''), str(x.get('id', ''))), reverse=True)
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

def get_salary_reports(start_month=None, end_month=None, search=None, page=1, limit=10, company_id=None):
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
        
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
    cursor = db.salary_reports.find(query).sort([("pay_period", DESCENDING), ("created_at", DESCENDING), ("id", DESCENDING), ("_id", DESCENDING)])
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

def validate_admin_login(email_or_username, password=None):
    """Validates Super Admin login by registered email (technologiesargus@gmail.com) or username, optionally verifying password."""
    db = get_db()
    if not email_or_username:
        return None if password is None else {'success': False, 'error': 'NOT_REGISTERED'}
    clean = str(email_or_username).strip().lower()
    doc = db.admin_users.find_one({
        '$or': [
            {'email': {'$regex': f"^{re.escape(clean)}$", '$options': 'i'}},
            {'username': {'$regex': f"^{re.escape(clean)}$", '$options': 'i'}}
        ]
    })
    if not doc and clean in ['technologiesargus@gmail.com', 'admin']:
        # Ensure Super Admin doc exists in MongoDB
        db.admin_users.update_one(
            {'role': 'super_admin'},
            {'$set': {
                'email': 'technologiesargus@gmail.com',
                'username': 'Admin',
                'password': '76543',
                'role': 'super_admin',
                'company_id': 'ARGUS_MASTER',
                'company_name': 'ARGUS TECHNOLOGIES'
            }},
            upsert=True
        )
        doc = db.admin_users.find_one({'email': 'technologiesargus@gmail.com'})

    if not doc:
        return None if password is None else {'success': False, 'error': 'NOT_REGISTERED'}
    admin_user = clean_doc(doc)

    if password is None:
        # Google OAuth flow - password not required
        return admin_user

    # Manual login with password
    stored = doc.get('password') or doc.get('password_hash')
    if not stored:
        return {'success': False, 'error': 'PASSWORD_NOT_SET', 'admin': admin_user}
    if verify_user_password(stored, password):
        return {'success': True, 'admin': admin_user}
    return {'success': False, 'error': 'INVALID_PASSWORD', 'admin': admin_user}

def set_admin_password(plain_password):
    """Sets a new hashed password for the Super Admin system administrator and persists password_raw."""
    db = get_db()
    if not plain_password:
        return False
    raw = str(plain_password).strip()
    hashed = hash_user_password(raw)
    db.admin_users.update_many(
        {'role': 'super_admin'},
        {'$set': {'password': hashed, 'password_hash': hashed, 'password_raw': raw, 'password_updated_at': datetime.now()}}
    )
    db.company_admin.update_one(
        {'id': 'ARGUS_MASTER'},
        {'$set': {'password': hashed, 'password_hash': hashed, 'password_raw': raw, 'password_updated_at': datetime.now()}}
    )
    return True

def save_generated_salary_report(p, company_id=None):
    """Save or upsert generated payslip record into db.salary_reports."""
    db = get_db()
    assigned_company_id = str(company_id or p.get('company_id') or 'ARGUS_MASTER')
    doc = {
        'company_id': assigned_company_id,
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
        {'company_id': assigned_company_id, 'employee_name': doc['employee_name'], 'pay_period': doc['pay_period']},
        {'$set': doc, '$setOnInsert': {'id': int(time.time() * 1000), 'created_at': datetime.now()}},
        upsert=True
    )
    return True

def get_payslip_data(employee_name, month_year, company_id=None):
    db = get_db()
    emp_q = {'employee_name': employee_name}
    if company_id and company_id != 'ALL':
        emp_q['company_id'] = str(company_id)
    emp = db.employees.find_one(emp_q)
    
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
    salary_type = str(emp.get('salary_type') or 'hourly').strip().lower() if emp else 'hourly'
    hours_salary = float(emp.get('hourly_salary', 0.0)) if emp else 0.0
    day_salary = float(emp.get('day_salary', 0.0)) if emp else 0.0
    half_salary = float(emp.get('half_day_salary', 0.0)) if emp else 0.0
    assigned_company_id = str(company_id or (emp.get('company_id') if emp else None) or 'ARGUS_MASTER')
    company_name = 'ARGUS TECHNOLOGIES'
    company_address = 'SF NO. 515, Bharathiyar Road, Maniyakaranpalayam, Ganapathy (PO), Coimbatore - 641 006'
    comp_email = 'technologiesargus@gmail.com'
    comp_phone = '+91 98765 43210'
    comp_gstin = ''
    comp_doc = db.company_admin.find_one({'id': assigned_company_id})
    if comp_doc:
        company_name = comp_doc.get('company_name') or company_name
        comp_email = comp_doc.get('email') or comp_email
        comp_phone = comp_doc.get('phone') or comp_phone
        comp_gstin = comp_doc.get('gstin') or comp_gstin
        loc = comp_doc.get('address') or comp_doc.get('location') or ''
        if loc:
            company_address = loc
        else:
            lat = comp_doc.get('latitude')
            lng = comp_doc.get('longitude')
            if lat and lng:
                company_address = f"Location: Lat {lat}, Lng {lng}"

    shift_hours_str = emp.get('shift_hours', '08:00') if emp else '08:00'

    shift_target_minutes = 480
    try:
        sp = shift_hours_str.split(':')
        shift_target_minutes = int(sp[0]) * 60 + int(sp[1])
    except Exception:
        shift_target_minutes = 480
    if shift_target_minutes <= 0:
        shift_target_minutes = 480
    half_shift_target = max(1, shift_target_minutes // 2)
    
    # 1. Query attendance & attendance_reports for this employee & month (Only Proper entries)
    att_query = {
        'employee_name': employee_name,
        'entry_type': {'$ne': 'improper'},
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

    daily_minutes = {}
    daily_manual_salary = {}

    for rec in records:
        if rec.get('entry_type') == 'improper':
            continue
        d_val = rec.get('date') or (rec.get('entry_time', '').split(' ')[0] if rec.get('entry_time') else '')
        if not d_val:
            continue

        wh = rec.get('working_hours', '00:00')
        mins = 0
        if wh and ':' in wh:
            try:
                h, m = wh.split(':')[:2]
                mins = int(h) * 60 + int(m)
            except Exception:
                pass
        elif rec.get('working_hours'):
            try:
                mins = int(float(rec.get('working_hours')) * 60)
            except Exception:
                pass
        daily_minutes[d_val] = daily_minutes.get(d_val, 0) + mins

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

    for m_entry in manual_entries:
        st = str(m_entry.get('status', '')).strip().lower()
        if 'improper' in st:
            continue
        ed = m_entry.get('entry_date') or (m_entry.get('submitted_at', '').split(' ')[0] if m_entry.get('submitted_at') else '')
        if not ed:
            continue
            
        hrs_str = m_entry.get('hours', '00:00')
        mins = 0
        if hrs_str:
            clean_hrs = str(hrs_str).replace('-', '').strip()
            if ':' in clean_hrs:
                try:
                    parts = clean_hrs.split(':')
                    h = abs(int(parts[0]))
                    m = abs(int(parts[1]))
                    mins = h * 60 + m
                except Exception:
                    mins = 0
        st = str(m_entry.get('status', '')).lower()
        if 'full' in st:
            mins = max(mins, shift_target_minutes)
        elif 'half' in st:
            mins = max(mins, half_shift_target)
        entry_type = str(m_entry.get('entry_type', 'Add')).strip()
        is_sub = entry_type.lower() == 'sub' or float(m_entry.get('working_salary', 0.0)) < 0
        msal = abs(float(m_entry.get('working_salary', 0.0)))

        delta_mins = -mins if is_sub else mins
        delta_sal = -msal if is_sub else msal

        daily_minutes[ed] = daily_minutes.get(ed, 0) + delta_mins
        daily_manual_salary[ed] = daily_manual_salary.get(ed, 0.0) + delta_sal

    net_daily_minutes = {d: max(0, m) for d, m in daily_minutes.items()}
    positive_days = {d: m for d, m in net_daily_minutes.items() if m > 0}
    total_minutes = max(0, sum(daily_minutes.values()))
    working_days = len(positive_days)
    tot_hrs = total_minutes // 60
    tot_mins = total_minutes % 60
    working_hours = f"{tot_hrs:02d}:{tot_mins:02d}"

    full_days = 0
    half_days = 0
    partial_days = 0
    partial_minutes = 0

    if salary_type == 'half_day':
        # Standard half-day target is 4 hours (240 mins) or half of shift
        ref_half_mins = 240 if shift_target_minutes >= 480 else (shift_target_minutes if shift_target_minutes <= 300 else 240)
        ref_full_mins = ref_half_mins * 2
        for d, mins in net_daily_minutes.items():
            if mins >= ref_full_mins:
                full_days += 1
            elif mins >= ref_half_mins:
                half_days += 1
            elif mins > 0:
                partial_days += 1
                partial_minutes += mins
    else:
        for d, mins in net_daily_minutes.items():
            if mins >= shift_target_minutes:
                full_days += 1
            elif mins >= half_shift_target:
                half_days += 1
            elif mins > 0:
                partial_days += 1
                partial_minutes += mins

    effective_half = half_salary if half_salary > 0 else (day_salary / 2.0 if day_salary > 0 else (hours_salary * 4.0))
    effective_hour = hours_salary if hours_salary > 0 else (day_salary / (shift_target_minutes / 60.0) if day_salary > 0 else 0.0)
    manual_salary_sum = sum(daily_manual_salary.values())

    # Calculate basic salary accurately based on salary_type and presence of records vs manual_entries
    if not records and manual_entries:
        # Solely driven by manual entries: basic salary is exact net sum of manual entries' working salary
        manual_net = sum(float(m.get('working_salary', 0.0)) for m in manual_entries)
        basic_salary = max(0.0, round(manual_net, 2))
    elif salary_type == 'hourly':
        basic_salary = round((total_minutes / 60.0) * hours_salary, 2)
    elif salary_type == 'daily':
        part_sal = (partial_minutes / 60.0) * effective_hour
        basic_salary = round((full_days * day_salary) + (half_days * effective_half) + part_sal, 2)
        # Deduct unapplied manual deductions (e.g. deductions logged on days without biometric punches)
        unapplied_deductions = sum(m for d, m in daily_manual_salary.items() if m < 0 and daily_minutes.get(d, 0) < 0)
        basic_salary = max(0.0, round(basic_salary + unapplied_deductions, 2))
    elif salary_type == 'half_day':
        total_half_units = (full_days * 2) + half_days
        target_half_div = ref_half_mins if 'ref_half_mins' in locals() and ref_half_mins > 0 else 240
        part_sal = (partial_minutes / float(target_half_div)) * effective_half
        basic_salary = round((total_half_units * effective_half) + part_sal, 2)
        unapplied_deductions = sum(m for d, m in daily_manual_salary.items() if m < 0 and daily_minutes.get(d, 0) < 0)
        basic_salary = max(0.0, round(basic_salary + unapplied_deductions, 2))
    else:
        if hours_salary > 0:
            basic_salary = round((total_minutes / 60.0) * hours_salary, 2)
        elif day_salary > 0:
            basic_salary = round((full_days * day_salary) + (half_days * effective_half), 2)
        else:
            basic_salary = max(0.0, manual_salary_sum)

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
    
    basis_labels = {
        'hourly': 'Hourly-Based',
        'daily': 'Day-Based',
        'half_day': 'Half-Day-Based'
    }
    salary_basis_label = basis_labels.get(salary_type, 'Day-Based')
    if salary_type == 'half_day':
        if full_days == 0:
            working_days_breakdown = f"{half_days} Half Days"
        else:
            working_days_breakdown = f"{total_half_units} Half Days ({full_days} Full, {half_days} Half)"
    else:
        working_days_breakdown = f"{working_days} ({full_days} Full, {half_days} Half)" if (full_days > 0 or half_days > 0) else str(working_days)

    # Format rate reporting on payslips: only report rates applicable to the employee's basis
    rep_hours_salary = int(round(hours_salary)) if salary_type == 'hourly' else 0
    rep_day_salary = int(round(day_salary)) if salary_type == 'daily' else 0
    rep_half_salary = int(round(half_salary)) if salary_type in ['daily', 'half_day'] else 0

    return {
        'company_id': assigned_company_id,
        'company_name': company_name,
        'company_address': company_address,
        'company_email': comp_email,
        'company_phone': comp_phone,
        'company_gstin': comp_gstin,
        'employee_name': employee_name,
        'employee_id': emp_id,
        'designation': designation,
        'phone_number': phone,
        'shift_hours': str(shift_hours_str or '08:00'),
        'bank_name': str(emp.get('bank_name', '') if emp else ''),
        'account_number': str(emp.get('account_number', '') if emp else ''),
        'salary_type': salary_type,
        'salary_basis': salary_basis_label,
        'salary_basis_label': salary_basis_label,
        'full_days': full_days,
        'half_days': half_days,
        'partial_days': partial_days,
        'working_days_breakdown': working_days_breakdown,
        'pay_period': month_year,
        'year_month': month_year,
        'hours_salary': rep_hours_salary,
        'day_salary': rep_day_salary,
        'half_day_salary': rep_half_salary,
        'working_days': working_days,
        'leave_days': leave_days,
        'total_days': total_days,
        'total_days_of_month': total_days,
        'total_working_hours': working_hours,
        'working_hours': working_hours,
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
