import os
import shutil
import time
import json
import re
import calendar
import secrets
from datetime import datetime, date, time as dt_time, timedelta, timezone
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

def get_default_two_month_range():
    """
    Returns (start_date_str, end_date_str, start_month_str, end_month_str)
    covering the previous month (from day 1) through the present month.
    e.g., if today is October 2026:
    start_date_str = '2026-09-01'
    end_date_str = '2026-10-31'
    start_month_str = '2026-09'
    end_month_str = '2026-10'
    """
    now = get_ist_now()
    cur_year = now.year
    cur_month = now.month
    
    if cur_month == 1:
        prev_year = cur_year - 1
        prev_month = 12
    else:
        prev_year = cur_year
        prev_month = cur_month - 1
        
    start_date_str = f"{prev_year:04d}-{prev_month:02d}-01"
    _, last_day_cur = calendar.monthrange(cur_year, cur_month)
    end_date_str = f"{cur_year:04d}-{cur_month:02d}-{last_day_cur:02d}"
    
    start_month_str = f"{prev_year:04d}-{prev_month:02d}"
    end_month_str = f"{cur_year:04d}-{cur_month:02d}"
    
    return start_date_str, end_date_str, start_month_str, end_month_str


MONGODB_URI = os.environ.get(
    "MONGODB_URI",
    "mongodb+srv://philipmatthew26_db_user:7hTlWrbaxxMOBKCn@cluster0.895ioy2.mongodb.net/?retryWrites=true&w=majority"
)
DB_NAME = "argus_attendance"

_client = None

def get_mongo_client():
    global _client
    if _client is None:
        _client = MongoClient(
            MONGODB_URI,
            maxPoolSize=50,
            minPoolSize=5,
            maxIdleTimeMS=45000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
            serverSelectionTimeoutMS=5000
        )
    return _client

def get_db():
    return get_mongo_client()[DB_NAME]

def clean_doc(doc):
    """Clean MongoDB document and nested types for JSON serialization recursively."""
    if doc is None:
        return None
    if hasattr(doc, 'item'):
        return doc.item()
    if isinstance(doc, list):
        return [clean_doc(item) for item in doc]
    if not isinstance(doc, dict):
        return doc
    d = dict(doc)
    for k, v in list(d.items()):
        if isinstance(v, ObjectId):
            d[k] = str(v)
        elif isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
        elif hasattr(v, 'item'):
            d[k] = v.item()
        elif isinstance(v, dict):
            d[k] = clean_doc(v)
        elif isinstance(v, list):
            d[k] = [
                clean_doc(item) if isinstance(item, dict)
                else (item.item() if hasattr(item, 'item')
                      else (item.isoformat() if isinstance(item, (datetime, date))
                            else (str(item) if isinstance(item, ObjectId) else item)))
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
        val = int(ident)
        if -9223372036854775808 <= val <= 9223372036854775807:
            filters.append({'id': val})
    except Exception:
        pass
    return {'$or': filters}

# ----------------- INITIALIZATION & SEEDING ----------------- #

def migrate_existing_data_to_master():
    """Backfills legacy documents without company_id to ARGUS_MASTER once."""
    try:
        db = get_db()
        if db.system_flags.find_one({'name': 'master_migration_done'}):
            return
        collections = ['employees', 'live_entries', 'timeout_entries', 'attendance_reports', 'attendance', 'manual_entries', 'payments', 'advances', 'salary_reports']
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
        db.system_flags.insert_one({'name': 'master_migration_done', 'at': get_ist_now()})
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
        db.attendance_reports.create_index([("company_id", ASCENDING), ("date", DESCENDING)])
        db.attendance_reports.create_index([("company_id", ASCENDING), ("entry_type", ASCENDING), ("employee_name", ASCENDING)])
        db.live_entries.create_index([("company_id", ASCENDING), ("entry_time", DESCENDING)])
        db.timeout_entries.create_index([("company_id", ASCENDING), ("exit_time", DESCENDING), ("created_at", DESCENDING)])
        db.timeout_entries.create_index([("company_id", ASCENDING), ("employee_name", ASCENDING)])
        db.attendance.create_index([("company_id", ASCENDING), ("date", DESCENDING)])
        db.manual_entries.create_index([("company_id", ASCENDING), ("entry_date", DESCENDING)])
        db.payments.create_index([("company_id", ASCENDING), ("payment_date", DESCENDING), ("reason", ASCENDING)])
        db.advances.create_index([("company_id", ASCENDING), ("advance_date", DESCENDING)])
        db.salary_reports.create_index([("company_id", ASCENDING), ("pay_period", DESCENDING), ("employee_name", ASCENDING)])
        db.leave_requests.create_index([("company_id", ASCENDING), ("status", ASCENDING), ("created_at", DESCENDING)])
        # Multi-Branch & Support Tickets Performance Indexes
        db.company_branches.create_index([("company_id", ASCENDING), ("status", ASCENDING)])
        db.company_branches.create_index([("id", ASCENDING)], unique=True)
        db.company_branches.create_index([("branch_name", ASCENDING)])
        db.support_tickets.create_index([("company_id", ASCENDING), ("status", ASCENDING)])
        db.support_tickets.create_index([("status", ASCENDING)])
        db.employees.create_index([("company_id", ASCENDING), ("branch_id", ASCENDING)])
        db.employees.create_index([("branch_id", ASCENDING)])
        db.employees.create_index([("status", ASCENDING)])
        db.attendance_reports.create_index([("company_id", ASCENDING), ("branch_id", ASCENDING), ("date", DESCENDING)])
        # Field Worker Module Indexes
        db.field_assignments.create_index([("company_id", ASCENDING), ("assigned_date", DESCENDING), ("employee_name", ASCENDING)])
        db.field_location_logs.create_index([("company_id", ASCENDING), ("date", DESCENDING), ("employee_name", ASCENDING), ("created_at", DESCENDING)])
        db.field_customer_visits.create_index([("company_id", ASCENDING), ("visit_date", DESCENDING), ("employee_name", ASCENDING)])
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
                'branch_limit': 100,
                'shift_hours': '08:00',
                'auto_email_reports': True,
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
        except Exception as e:
            print(f"Master company seeding notice: {e}")

    # Ensure master company has at least one default branch for System Admin view
    try:
        if db.company_branches.count_documents({'company_id': 'ARGUS_MASTER'}) == 0:
            db.company_branches.insert_one({
                'id': f"branch_{int(time.time() * 1000)}",
                'company_id': 'ARGUS_MASTER',
                'branch_name': 'Coimbatore',
                'branch_code': 'ARG-CBE',
                'district': 'Coimbatore',
                'address': 'SF NO. 515, Bharathiyar Road, Maniyakaranpalayam, Ganapathy, Coimbatore - 641 006',
                'latitude': 11.02980,
                'longitude': 76.97400,
                'geofence_radius': 150.0,
                'status': 'Active',
                'created_at': datetime.now(),
                'updated_at': datetime.now()
            })
    except Exception as e:
        print(f"Master branch seeding notice: {e}")

    try:
        sync_geofence_entry_types()
    except Exception as e:
        print(f"Geofence sync notice: {e}")

    try:
        sync_live_and_timeout_entries()
    except Exception as e:
        print(f"Live and timeout entries sync notice: {e}")

# ----------------- UNIVERSAL COORDINATE PARSERS ----------------- #

def parse_coordinate_value(val):
    """
    Parses any coordinate representation (decimal, DMS, directional, or custom manual entry).
    Never throws an exception. Allows users to type manually ANY coordinate.
    If numeric or standard GPS, returns a clean float.
    If custom string/format, returns the sanitized string so nothing is ever rejected.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    if not val_str:
        return None

    # 1. Direct float conversion attempt
    try:
        return float(val_str)
    except Exception:
        pass

    # 2. Regex parsing for degrees/minutes/seconds (DMS) or directional letters (N/S/E/W)
    try:
        # Check DMS format: e.g. 11° 1' 47.3" N or 11d 1m 47.3s N
        dms_m = re.search(r'(\d+(?:\.\d+)?)\s*[°d\s]\s*(\d+(?:\.\d+)?|\b)?\s*[\'m\s]?\s*([\d\.]+)?\s*[\"s]?\s*([NSEWnsew])?', val_str)
        if dms_m and (dms_m.group(4) or '°' in val_str or "'" in val_str or '"' in val_str):
            deg = float(dms_m.group(1) or 0)
            minute = float(dms_m.group(2) or 0)
            sec = float(dms_m.group(3) or 0)
            dec = deg + (minute / 60.0) + (sec / 3600.0)
            dir_card = (dms_m.group(4) or '').upper()
            if dir_card in ('S', 'W'):
                dec = -dec
            return round(dec, 7)

        # Check decimal with direction: e.g. 11.0298 N or 76.9740 W or S 33.8688
        dir_dec_m = re.search(r'([NSEWnsew])?\s*([-+]?\d+(?:\.\d+)?)\s*([NSEWnsew])?', val_str)
        if dir_dec_m:
            num = float(dir_dec_m.group(2))
            dir_card = ((dir_dec_m.group(1) or '') + (dir_dec_m.group(3) or '')).upper()
            if ('S' in dir_card or 'W' in dir_card) and num > 0:
                num = -num
            return num
    except Exception:
        pass

    # 3. If arbitrary custom manual coordinate or text, preserve and return as string (never reject)
    return val_str

def parse_coordinate_to_float(val, default_val=None):
    """Safely extracts a float value from any coordinate for distance calculation."""
    if val is None:
        return default_val
    parsed = parse_coordinate_value(val)
    if isinstance(parsed, (int, float)):
        return float(parsed)
    try:
        return float(str(parsed).strip())
    except Exception:
        return default_val

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
    manual_date = data.get('registered_date')
    if manual_date and str(manual_date).strip():
        m_str = str(manual_date).strip()
        try:
            if '-' in m_str:
                parts = m_str.split('-')
                if len(parts) == 3:
                    if len(parts[0]) == 4: # YYYY-MM-DD
                        reg_date_str = f"{parts[2]}/{parts[1]}/{parts[0]}"
                    else: # DD-MM-YYYY
                        reg_date_str = f"{parts[0]}/{parts[1]}/{parts[2]}"
                else:
                    reg_date_str = m_str
            else:
                reg_date_str = m_str
        except Exception:
            reg_date_str = m_str
    else:
        reg_date_str = now_ist.strftime('%d/%m/%Y')

    lat_val = data.get('latitude')
    lng_val = data.get('longitude')
    
    # Check if user typed or pasted combined coordinates (e.g. "11.0298, 76.9740")
    if lat_val and (',' in str(lat_val) or ';' in str(lat_val)) and (not lng_val or str(lng_val).strip() == ''):
        parts = re.split(r'[,;]+', str(lat_val))
        if len(parts) >= 2:
            lat_val = parts[0].strip()
            lng_val = parts[1].strip()

    lat = parse_coordinate_value(lat_val)
    lng = parse_coordinate_value(lng_val)

    coords_locked = bool(lat is not None and lng is not None and str(lat).strip() != '' and str(lng).strip() != '')

    address_val = data.get('address', '').strip()
    if not address_val and lat is not None and lng is not None:
        try:
            address_val = reverse_geocode_coordinates(lat, lng) or ''
        except Exception:
            address_val = ''

    doc = {
        'id': comp_id,
        'company_name': data.get('company_name', '').strip(),
        'gstin': data.get('gstin', '').strip().upper(),
        'email': email,
        'phone': data.get('phone', '').strip(),
        'address': address_val,
        'location': address_val,
        'latitude': lat,
        'longitude': lng,
        'coordinates_locked': coords_locked,
        'coordinates_locked_at': now_ist if coords_locked else None,
        'status': 'Deactive' if str(data.get('status', 'Active')).strip().lower() in ['inactive', 'deactive'] else 'Active',
        'employee_limit': int(data.get('employee_limit') or data.get('employee_count') or 50),
        'branch_limit': int(data.get('branch_limit') or 5),
        'shift_hours': str(data.get('shift_hours') or '08:00').strip(),
        'auto_email_reports': str(data.get('auto_email_reports', 'false')).lower() in ['true', '1', 'yes'],
        'daily_report_time': str(data.get('daily_report_time') or '07:00').strip(),
        'monthly_report_day': int(data.get('monthly_report_day') or 1),
        'geofence_radius': float(data.get('geofence_radius') or data.get('radius_meters') or 200.0),
        'radius_meters': float(data.get('geofence_radius') or data.get('radius_meters') or 200.0),
        'can_delete_entries': str(data.get('can_delete_entries', False)).lower() in ['true', '1', 'yes'],
        'support_enabled': str(data.get('support_enabled', False)).lower() in ['true', '1', 'yes'],
        'modules': {
            'single_company': bool(data.get('modules', {}).get('single_company', True) if isinstance(data.get('modules'), dict) else str(data.get('module_single_company', True)).lower() in ['true', '1', 'yes', 'on']),
            'branch_company': bool(data.get('modules', {}).get('branch_company', False) if isinstance(data.get('modules'), dict) else str(data.get('module_branch_company', False)).lower() in ['true', '1', 'yes', 'on']),
            'field_worker': bool(data.get('modules', {}).get('field_worker', False) if isinstance(data.get('modules'), dict) else str(data.get('module_field_worker', False)).lower() in ['true', '1', 'yes', 'on'])
        },
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
        return val.strftime('%d/%m/%Y')
    val_str = str(val).strip()
    if not val_str or val_str == '-':
        return '-'
    if re.match(r'^\d{2}/\d{2}/\d{4}$', val_str):
        return val_str
    if 'T' in val_str or '-' in val_str:
        clean_str = val_str.replace('Z', '')
        if '.' in clean_str:
            clean_str = clean_str.split('.')[0]
        for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y %I:%M %p', '%d/%m/%Y'):
            try:
                parsed = datetime.strptime(clean_str, fmt)
                return parsed.strftime('%d/%m/%Y')
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
    company_docs = list(cursor)
    
    # Batch calculate employee & branch counts in single queries instead of N sequential calls
    comp_ids = [doc.get('id') for doc in company_docs if doc.get('id')]
    counts_map = {}
    branch_counts_map = {}
    if comp_ids:
        try:
            agg_res = db.employees.aggregate([
                {'$match': {'company_id': {'$in': comp_ids}}},
                {'$group': {
                    '_id': '$company_id',
                    'total_count': {'$sum': 1},
                    'active_count': {
                        '$sum': {'$cond': [{'$ne': ['$status', 'Inactive']}, 1, 0]}
                    }
                }}
            ])
            counts_map = {item['_id']: item for item in agg_res}
        except Exception:
            pass
        try:
            br_agg = db.company_branches.aggregate([
                {'$match': {'company_id': {'$in': [str(cid) for cid in comp_ids]}, 'status': {'$ne': 'Deleted'}}},
                {'$group': {'_id': '$company_id', 'count': {'$sum': 1}}}
            ])
            branch_counts_map = {str(item['_id']): item['count'] for item in br_agg}
        except Exception:
            pass

    for doc in company_docs:
        c = clean_doc(doc)
        c['address'] = c.get('address') or c.get('location') or ''
        comp_counts = counts_map.get(c['id'], {})
        c['active_count'] = comp_counts.get('active_count', 0)
        c['total_count'] = comp_counts.get('total_count', 0)
        c['employee_count'] = c['active_count']
        c['employee_limit'] = int(c.get('employee_limit') or c['employee_count'] or 50)
        c['branch_count'] = branch_counts_map.get(str(c['id']), 0)
        c['branch_limit'] = int(c.get('branch_limit') or 5)
        c['shift_hours'] = str(c.get('shift_hours') or '08:00').strip()
        if 'auto_email_reports' not in c:
            c['auto_email_reports'] = True
        c['daily_report_time'] = str(c.get('daily_report_time') or '07:00').strip()
        c['monthly_report_day'] = int(c.get('monthly_report_day') or 1)
        if 'can_delete_entries' not in c:
            c['can_delete_entries'] = False
        c['support_enabled'] = bool(c.get('support_enabled', False))
        c['geofence_radius'] = float(c.get('geofence_radius') or c.get('radius_meters') or 200.0)
        c['radius_meters'] = c['geofence_radius']
        c['status'] = 'Deactive' if str(c.get('status', 'Active')).strip().lower() in ['inactive', 'deactive'] else 'Active'
            
        c['registered_date'] = format_company_reg_date(c.get('registered_date') or c.get('created_at'))
        companies.append(c)
        
    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': companies
    }

_company_cache = {}
_company_cache_ttl = 60  # seconds

def invalidate_company_cache(comp_id=None):
    global _company_cache
    if comp_id:
        _company_cache.pop(str(comp_id), None)
        _company_cache.pop('ALL', None)
        _company_cache.pop('ARGUS_MASTER', None)
    else:
        _company_cache.clear()
    invalidate_company_modules_cache(comp_id)

def get_company_by_id(comp_id, include_counts=False):
    """Fetches company details by ID with in-memory caching. When include_counts=False (default), skips expensive employee count queries."""
    if not comp_id:
        return None
    key = str(comp_id)
    now_ts = time.time()
    if not include_counts and key in _company_cache:
        t, val = _company_cache[key]
        if now_ts - t < _company_cache_ttl:
            return dict(val)

    db = get_db()
    doc = db.company_admin.find_one({'id': key})
    if not doc:
        doc = db.company_admin.find_one(build_id_filter(comp_id))
    if doc:
        c = clean_doc(doc)
        c['address'] = c.get('address') or c.get('location') or ''
        c['shift_hours'] = str(c.get('shift_hours') or '08:00').strip()
        if 'auto_email_reports' not in c:
            c['auto_email_reports'] = True
        c['daily_report_time'] = str(c.get('daily_report_time') or '07:00').strip()
        c['monthly_report_day'] = int(c.get('monthly_report_day') or 1)
        if 'can_delete_entries' not in c:
            c['can_delete_entries'] = False
        c['support_enabled'] = bool(c.get('support_enabled', False))
        c['geofence_radius'] = float(c.get('geofence_radius') or c.get('radius_meters') or 200.0)
        c['radius_meters'] = c['geofence_radius']
        c['status'] = 'Deactive' if str(c.get('status', 'Active')).strip().lower() in ['inactive', 'deactive'] else 'Active'
        c['registered_date'] = format_company_reg_date(c.get('registered_date') or c.get('created_at'))
        c['employee_limit'] = int(c.get('employee_limit') or 50)
        c['branch_limit'] = int(c.get('branch_limit') or 5)

        # Store in in-memory cache
        _company_cache[key] = (now_ts, dict(c))

        if include_counts:
            c['active_count'] = db.employees.count_documents({'company_id': c['id'], 'status': {'$ne': 'Inactive'}})
            c['total_count'] = db.employees.count_documents({'company_id': c['id']})
            c['employee_count'] = c['active_count']
            c['employee_limit'] = int(c.get('employee_limit') or c['employee_count'] or 50)
            c['branch_count'] = db.company_branches.count_documents({'company_id': str(c['id']), 'status': {'$ne': 'Deleted'}})
        else:
            c['active_count'] = 0
            c['total_count'] = 0
            c['employee_count'] = 0
            c['branch_count'] = 0
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
            upd['latitude'] = parse_coordinate_value(lat_val)
    if 'longitude' in data:
        lng_val = data['longitude']
        if lng_val is None or str(lng_val).strip() == '':
            upd['longitude'] = None
        else:
            upd['longitude'] = parse_coordinate_value(lng_val)
    if 'coordinates_locked' in data:
        upd['coordinates_locked'] = bool(data['coordinates_locked'])
    elif ('latitude' in upd or 'longitude' in upd):
        cur_lat = upd.get('latitude')
        cur_lng = upd.get('longitude')
        if cur_lat is not None and cur_lng is not None and str(cur_lat).strip() != '' and str(cur_lng).strip() != '':
            upd['coordinates_locked'] = True
            upd['coordinates_locked_at'] = get_ist_now()
        elif cur_lat is None and cur_lng is None and ('latitude' in upd and 'longitude' in upd):
            upd['coordinates_locked'] = False

    if not upd.get('address'):
        comp_cur = db.company_admin.find_one(build_id_filter(comp_id))
        c_lat = upd.get('latitude', comp_cur.get('latitude') if comp_cur else None)
        c_lng = upd.get('longitude', comp_cur.get('longitude') if comp_cur else None)
        if c_lat is not None and c_lng is not None and not (comp_cur and comp_cur.get('address')):
            resolved = reverse_geocode_coordinates(c_lat, c_lng)
            if resolved:
                upd['address'] = resolved
                upd['location'] = resolved
    if 'coordinates_locked_at' in data:
        upd['coordinates_locked_at'] = data['coordinates_locked_at']
    if 'status' in data and data['status']:
        st = str(data['status']).strip()
        upd['status'] = 'Deactive' if st.lower() in ['inactive', 'deactive'] else 'Active'
    if 'support_enabled' in data:
        upd['support_enabled'] = str(data['support_enabled']).lower() in ['true', '1', 'yes']
    if 'employee_limit' in data or 'employee_count' in data:
        lim = data.get('employee_limit') or data.get('employee_count')
        if lim:
            try:
                upd['employee_limit'] = int(lim)
            except Exception:
                pass
    if 'branch_limit' in data:
        b_lim = data.get('branch_limit')
        if b_lim:
            try:
                upd['branch_limit'] = int(b_lim)
            except Exception:
                pass
    if 'shift_hours' in data and data['shift_hours']:
        upd['shift_hours'] = str(data['shift_hours']).strip()
    if 'registered_date' in data and data['registered_date']:
        m_str = str(data['registered_date']).strip()
        try:
            if '-' in m_str:
                parts = m_str.split('-')
                if len(parts) == 3 and len(parts[0]) == 4:
                    upd['registered_date'] = f"{parts[2]}/{parts[1]}/{parts[0]}"
                else:
                    upd['registered_date'] = m_str
            else:
                upd['registered_date'] = m_str
        except Exception:
            upd['registered_date'] = m_str
    if 'auto_email_reports' in data:
        upd['auto_email_reports'] = bool(data['auto_email_reports'])
    if 'can_delete_entries' in data:
        upd['can_delete_entries'] = str(data['can_delete_entries']).lower() in ['true', '1', 'yes']
    if 'logo' in data:
        upd['logo'] = str(data['logo']).strip()
    if 'daily_report_time' in data and data['daily_report_time']:
        upd['daily_report_time'] = str(data['daily_report_time']).strip()
    if 'monthly_report_day' in data and data['monthly_report_day'] is not None and str(data['monthly_report_day']).strip() != '':
        try:
            m_day = int(data['monthly_report_day'])
            if 1 <= m_day <= 31:
                upd['monthly_report_day'] = m_day
        except Exception:
            pass
    if 'geofence_radius' in data or 'radius_meters' in data:
        rad_val = data.get('geofence_radius') if 'geofence_radius' in data else data.get('radius_meters')
        try:
            r_num = float(rad_val)
            if r_num > 0:
                upd['geofence_radius'] = r_num
                upd['radius_meters'] = r_num
        except Exception:
            pass
    if 'modules' in data and isinstance(data['modules'], dict):
        raw_m = data['modules']
        upd['modules'] = {
            'single_company': bool(raw_m.get('single_company', True)),
            'branch_company': bool(raw_m.get('branch_company', False)),
            'field_worker': bool(raw_m.get('field_worker', False))
        }
    elif any(k.startswith('module_') for k in data.keys()):
        upd['modules'] = {
            'single_company': str(data.get('module_single_company', True)).lower() in ['true', '1', 'yes', 'on'],
            'branch_company': str(data.get('module_branch_company', False)).lower() in ['true', '1', 'yes', 'on'],
            'field_worker': str(data.get('module_field_worker', False)).lower() in ['true', '1', 'yes', 'on']
        }
    db.company_admin.update_one(build_id_filter(comp_id), {'$set': upd})
    invalidate_company_modules_cache(comp_id)
    invalidate_company_cache(comp_id)
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

def can_company_delete_entries(comp_id):
    """Checks whether a company has permission to delete attendance / report entries."""
    if not comp_id:
        return False
    c = get_company_by_id(comp_id, include_counts=False)
    return bool(c.get('can_delete_entries', False)) if c else False

def toggle_company_delete_entries(comp_id, enabled=None):
    """Toggles or sets the entry deletion permission for a company."""
    db = get_db()
    comp = db.company_admin.find_one({'id': str(comp_id)})
    if not comp:
        comp = db.company_admin.find_one(build_id_filter(comp_id))
    if not comp:
        return None
    current_val = bool(comp.get('can_delete_entries', False))
    new_val = not current_val if enabled is None else bool(str(enabled).lower() in ['true', '1', 'yes'])
    db.company_admin.update_one({'_id': comp['_id']}, {'$set': {'can_delete_entries': new_val, 'updated_at': get_ist_now()}})
    invalidate_company_cache(comp_id)
    return new_val

def is_company_active(comp_id):
    """Checks whether a company is active. Returns False ONLY if explicitly marked Deactive or Inactive."""
    if not comp_id or str(comp_id).strip() in ['ALL', 'ARGUS_MASTER']:
        return True
    try:
        db = get_db()
        cid_str = str(comp_id).strip()
        comp = db.company_admin.find_one({'id': cid_str})
        if not comp:
            comp = db.company_admin.find_one(build_id_filter(cid_str))
        if not comp:
            # If company record not found, don't falsely evict an active session
            return True
        status = str(comp.get('status', 'Active')).strip().lower()
        return status not in ['deactive', 'inactive', 'disabled']
    except Exception as e:
        print(f"Warning: is_company_active check error: {e}")
        return True

def create_user_session(user_data):
    """
    Creates a persistent database-backed login session token (valid for 365 days).
    Persists across browser tab closures, browser restarts, and server reloads.
    """
    if not user_data or not isinstance(user_data, dict):
        return None
    try:
        db = get_db()
        token = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=365)
        
        session_doc = {
            'token': token,
            'role': str(user_data.get('role', 'company_admin')).strip(),
            'company_id': str(user_data.get('company_id', '')).strip(),
            'company_name': str(user_data.get('company_name', '')).strip(),
            'username': str(user_data.get('username') or user_data.get('admin_username') or user_data.get('company_name') or 'User').strip(),
            'email': str(user_data.get('email') or user_data.get('admin_email') or user_data.get('company_email') or '').strip().lower(),
            'employee_id': str(user_data.get('employee_id', '')).strip(),
            'employee_name': str(user_data.get('employee_name', '')).strip(),
            'created_at': now,
            'expires_at': expires_at,
            'last_active': now
        }
        db.user_sessions.insert_one(session_doc)
        return token
    except Exception as e:
        print(f"Warning: create_user_session error: {e}")
        return None

def get_user_session_by_token(token):
    """
    Validates and retrieves persistent database session data by token.
    Automatically verifies that token has not expired and company remains active.
    """
    if not token or not str(token).strip():
        return None
    try:
        db = get_db()
        token_clean = str(token).strip()
        doc = db.user_sessions.find_one({'token': token_clean})
        if not doc:
            return None
        
        now = datetime.now(timezone.utc)
        exp = doc.get('expires_at')
        if exp:
            if hasattr(exp, 'tzinfo') and exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                db.user_sessions.delete_one({'_id': doc['_id']})
                return None
        
        # Verify company is not deactivated
        comp_id = doc.get('company_id')
        if comp_id and not is_company_active(comp_id):
            db.user_sessions.delete_one({'_id': doc['_id']})
            return None
        
        # Touch last_active
        db.user_sessions.update_one({'_id': doc['_id']}, {'$set': {'last_active': now}})
        return clean_doc(doc)
    except Exception as e:
        print(f"Warning: get_user_session_by_token error: {e}")
        return None

def delete_user_session(token):
    """Explicitly deletes a session token on logout."""
    if not token:
        return False
    try:
        db = get_db()
        db.user_sessions.delete_one({'token': str(token).strip()})
        return True
    except Exception:
        return False

def is_company_support_enabled(comp_id):
    """Checks whether Support & Help is enabled for a company. Defaults to False."""
    if not comp_id or str(comp_id).strip() in ['ALL', 'ARGUS_MASTER']:
        return True  # System Administrator always has access
    c = get_company_by_id(comp_id, include_counts=False)
    return bool(c.get('support_enabled', False)) if c else False

def toggle_company_support(comp_id, enabled=None):
    """Toggles or sets the support feature permission for a company."""
    if not comp_id:
        return None
    db = get_db()
    cid_str = str(comp_id).strip()
    comp = db.company_admin.find_one({'id': cid_str})
    if not comp:
        comp = db.company_admin.find_one(build_id_filter(cid_str))
    if not comp:
        return None
    current_val = bool(comp.get('support_enabled', False))
    new_val = not current_val if enabled is None else (str(enabled).lower() in ['true', '1', 'yes'])
    db.company_admin.update_one({'_id': comp['_id']}, {'$set': {'support_enabled': new_val, 'updated_at': get_ist_now()}})
    invalidate_company_cache(comp_id)
    return new_val

def delete_company(comp_id):
    """
    Cascading delete: Completely removes the company and all associated records:
    - company_admin
    - employees
    - attendance
    - attendance_reports
    - live_entries
    - timeout_entries
    - manual_entries
    - leave_requests
    - leave_balances
    - leave_policies
    - payments
    - advances
    - salary_reports
    - support_tickets
    Also removes support ticket upload folders and invalidates dashboard caches.
    """
    if not comp_id:
        raise ValueError("Company ID is required for deletion.")
    
    db = get_db()
    cid_str = str(comp_id).strip()
    
    comp_doc = db.company_admin.find_one({'id': cid_str})
    if not comp_doc:
        comp_doc = db.company_admin.find_one(build_id_filter(cid_str))
    
    if not comp_doc:
        raise ValueError(f"Company '{cid_str}' not found.")
        
    actual_id = str(comp_doc.get('id') or cid_str)
    comp_obj_id = comp_doc['_id']
    comp_name = comp_doc.get('company_name', 'Company')
    
    tenant_filter = {'company_id': actual_id}
    
    counts = {}
    counts['employees'] = db.employees.delete_many(tenant_filter).deleted_count
    counts['attendance'] = db.attendance.delete_many(tenant_filter).deleted_count
    counts['attendance_reports'] = db.attendance_reports.delete_many(tenant_filter).deleted_count
    counts['live_entries'] = db.live_entries.delete_many(tenant_filter).deleted_count
    counts['timeout_entries'] = db.timeout_entries.delete_many(tenant_filter).deleted_count
    counts['manual_entries'] = db.manual_entries.delete_many(tenant_filter).deleted_count
    counts['leave_requests'] = db.leave_requests.delete_many(tenant_filter).deleted_count
    counts['leave_balances'] = db.leave_balances.delete_many(tenant_filter).deleted_count
    counts['leave_policies'] = db.leave_policies.delete_many(tenant_filter).deleted_count
    counts['payments'] = db.payments.delete_many(tenant_filter).deleted_count
    counts['advances'] = db.advances.delete_many(tenant_filter).deleted_count
    counts['salary_reports'] = db.salary_reports.delete_many(tenant_filter).deleted_count
    counts['support_tickets'] = db.support_tickets.delete_many(tenant_filter).deleted_count
    counts['field_assignments'] = db.field_assignments.delete_many(tenant_filter).deleted_count
    counts['field_location_logs'] = db.field_location_logs.delete_many(tenant_filter).deleted_count
    counts['field_customer_visits'] = db.field_customer_visits.delete_many(tenant_filter).deleted_count
    
    # Remove company document
    counts['company'] = db.company_admin.delete_one({'_id': comp_obj_id}).deleted_count
    
    # Also remove uploaded support ticket attachments on disk
    try:
        support_uploads_dir = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'support_tickets', actual_id)
        if os.path.exists(support_uploads_dir):
            shutil.rmtree(support_uploads_dir, ignore_errors=True)
    except Exception as fs_err:
        print(f"Warning: could not delete support uploads directory: {fs_err}")
        
    # Invalidate dashboard metrics caches
    try:
        invalidate_dashboard_cache(actual_id)
        invalidate_company_cache(actual_id)
        invalidate_company_branches_cache(actual_id)
    except Exception:
        pass
        
    total_purged = sum(counts.values())
    return {
        'success': True,
        'company_id': actual_id,
        'company_name': comp_name,
        'deleted_counts': counts,
        'total_records_deleted': total_purged,
        'message': f"Company '{comp_name}' and all associated {total_purged} records deleted successfully."
    }

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
    
    st = str(company.get('status', 'Active')).strip().lower()
    if st in ['deactive', 'inactive', 'disabled']:
        return {
            'success': False,
            'error': 'COMPANY_DEACTIVATED',
            'status': 'Deactive',
            'company': company,
            'message': 'This company account has been deactivated. Please contact System Administrator.'
        }

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
        if not comp:
            comp = db.company_admin.find_one(build_id_filter(comp_id))
        if comp:
            st = str(comp.get('status', 'Active')).strip().lower()
            if st in ['deactive', 'inactive', 'disabled']:
                return {
                    'success': False,
                    'error': 'COMPANY_DEACTIVATED',
                    'status': 'Deactive',
                    'employee': emp,
                    'message': 'Your company account has been deactivated. Please contact System Administrator.'
                }
            emp['company_name'] = comp.get('company_name') if comp else 'Client Company'
            emp['company_lat'] = comp.get('latitude') if comp else 11.02980
            emp['company_lng'] = comp.get('longitude') if comp else 76.97400
    else:
        emp['company_name'] = 'ARGUS TECHNOLOGIES'
        emp['company_lat'] = 11.02980
        emp['company_lng'] = 76.97400

    emp_st = str(emp.get('status', 'Active')).strip().capitalize()
    if emp_st == 'Inactive':
        return {
            'success': False,
            'error': 'EMPLOYEE_INACTIVE',
            'status': 'Inactive',
            'employee': emp,
            'message': 'Your employee account is currently set to Inactive. Please contact your company administrator.'
        }

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

def is_home_branch_id(b_id):
    """Returns True if branch ID represents Home Branch / Main Company HQ."""
    return bool(b_id and str(b_id).strip().upper() in ['HOME', 'HQ', 'MAIN', 'UNASSIGNED'])

def get_branch_employee_query(b_id, company_id=None):
    """
    Returns a MongoDB query dictionary for matching employees by branch_id.
    - If branch_id is None or ALL: returns base company query without branch restriction.
    - If branch_id is HOME: matches employees belonging to initial company account (branch_id in [None, '', 'HOME', 'HQ', 'MAIN', 'unassigned'] or missing).
    - If branch_id is a specific ID: matches employees with that exact branch_id.
    """
    q = {}
    if company_id and str(company_id) not in ['ALL', 'ARGUS_MASTER']:
        q['company_id'] = str(company_id)
    clean_bid = str(b_id).strip() if b_id and str(b_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if clean_bid:
        if is_home_branch_id(clean_bid):
            q['$or'] = [
                {'branch_id': {'$in': [None, '', 'HOME', 'HQ', 'MAIN', 'unassigned']}},
                {'branch_id': {'$exists': False}}
            ]
        else:
            q['branch_id'] = clean_bid
    return q

_branch_emp_names_cache = {}
_BRANCH_CACHE_TTL = 30.0

def get_cached_branch_names_and_ids(b_id, company_id=None):
    clean_bid = str(b_id).strip() if b_id and str(b_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if not clean_bid:
        return set(), set()
    key = (str(company_id or ''), clean_bid)
    now_ts = time.time()
    if key in _branch_emp_names_cache:
        ts, names, ids = _branch_emp_names_cache[key]
        if now_ts - ts < _BRANCH_CACHE_TTL:
            return set(names), set(ids)
    
    b_emp_q = get_branch_employee_query(clean_bid, company_id)
    b_emps = list(get_db().employees.find(b_emp_q, {'id': 1, '_id': 1, 'employee_name': 1}))
    names = set(e.get('employee_name') for e in b_emps if e.get('employee_name'))
    ids = set()
    for e in b_emps:
        if e.get('id'):
            ids.add(str(e.get('id')))
        if e.get('_id'):
            ids.add(str(e.get('_id')))
    _branch_emp_names_cache[key] = (now_ts, names, ids)
    return set(names), set(ids)

def invalidate_branch_emp_cache(company_id=None):
    global _branch_emp_names_cache
    if company_id:
        c_str = str(company_id)
        _branch_emp_names_cache = {k: v for k, v in _branch_emp_names_cache.items() if k[0] != c_str}
    else:
        _branch_emp_names_cache.clear()

def get_branch_record_condition(b_id, b_names=None):
    """
    Returns query condition for attendance, punches, payments, and other records.
    - For HOME: matches records where employee_name in b_names OR branch_id in ['HOME', 'HQ', 'MAIN'].
    - For specific branch: matches records where branch_id == clean_bid OR employee_name in b_names.
    """
    clean_bid = str(b_id).strip() if b_id and str(b_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if not clean_bid:
        return None
    if is_home_branch_id(clean_bid):
        if b_names:
            return {'$or': [
                {'employee_name': {'$in': list(b_names)}},
                {'branch_id': {'$in': ['HOME', 'HQ', 'MAIN']}}
            ]}
        return {'branch_id': {'$in': ['HOME', 'HQ', 'MAIN']}}
    else:
        if b_names:
            return {'$or': [{'branch_id': clean_bid}, {'employee_name': {'$in': list(b_names)}}]}
        return {'branch_id': clean_bid}

def get_branch_leave_condition(b_id, b_emp_ids=None, b_emp_names=None):
    """Returns query condition for leave_requests matching branch."""
    clean_bid = str(b_id).strip() if b_id and str(b_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if not clean_bid:
        return None
    conds = []
    if is_home_branch_id(clean_bid):
        conds.append({'branch_id': {'$in': ['HOME', 'HQ', 'MAIN']}})
    else:
        conds.append({'branch_id': clean_bid})
    if b_emp_ids:
        conds.append({'employee_id': {'$in': list(b_emp_ids)}})
    if b_emp_names:
        conds.append({'employee_name': {'$in': list(b_emp_names)}})
    if len(conds) == 1:
        return conds[0]
    return {'$or': conds}

def generate_employee_id():
    import secrets
    return f"{int(time.time() * 1000)}{secrets.randbelow(100):02d}"

def get_all_employees(company_id=None, search='', sort_col='id', sort_dir='desc', page=1, limit=10, status=None, branch_id=None):
    db = get_db()
    query = {}
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)

    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if b_id:
        if is_home_branch_id(b_id):
            query['$or'] = [
                {'branch_id': {'$in': [None, '', 'HOME', 'HQ', 'MAIN', 'unassigned']}},
                {'branch_id': {'$exists': False}}
            ]
        else:
            query['branch_id'] = b_id

    # Filter by employee status if specified
    if status and str(status).strip().lower() not in ['all', '', 'none']:
        st_clean = str(status).strip().capitalize()
        if st_clean == 'Inactive':
            query['status'] = 'Inactive'
        elif st_clean == 'Active':
            query['status'] = {'$ne': 'Inactive'}

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
        
    employees = []
    for doc in cursor:
        c = clean_doc(doc)
        c['status'] = 'Inactive' if str(c.get('status', 'Active')).strip().capitalize() == 'Inactive' else 'Active'
        employees.append(c)

    # Compute company active quota summary stats
    base_comp_query = {'company_id': str(company_id)} if (company_id and company_id != 'ALL') else {}
    if b_id:
        base_comp_query['branch_id'] = b_id
    active_count = db.employees.count_documents({**base_comp_query, 'status': {'$ne': 'Inactive'}})
    inactive_count = db.employees.count_documents({**base_comp_query, 'status': 'Inactive'})
    total_preserved = db.employees.count_documents(base_comp_query)

    employee_limit = 50
    if company_id and company_id not in ['ALL', 'ARGUS_MASTER']:
        comp = db.company_admin.find_one(build_id_filter(company_id))
        if comp:
            try:
                employee_limit = int(comp.get('employee_limit') or comp.get('employee_count') or 50)
            except Exception:
                employee_limit = 50

    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': employees,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'total_preserved': total_preserved,
        'employee_limit': employee_limit
    }

def get_employee_by_id(emp_id, company_id=None):
    db = get_db()
    f = build_id_filter(emp_id)
    if company_id and company_id != 'ALL':
        f = {'$and': [f, {'company_id': str(company_id)}]}
    doc = db.employees.find_one(f)
    cleaned = clean_doc(doc)
    if cleaned:
        cleaned['status'] = 'Inactive' if str(cleaned.get('status', 'Active')).strip().capitalize() == 'Inactive' else 'Active'
        if not cleaned.get('permissions'):
            cleaned['permissions'] = {
                'punch_attendance': True,
                'attendance_history': True,
                'monthly_payslip': True,
                'employee_credentials': True
            }
    return cleaned

def safe_float(val, default=0.0):
    """Safely converts string/number/empty to float without raising ValueError."""
    try:
        if val is None:
            return default
        s = str(val).replace(',', '').strip()
        if not s:
            return default
        return float(s)
    except (ValueError, TypeError):
        return default

def parse_shift_hours_to_minutes(shift_str, default_minutes=480):
    """
    Parses shift_hours string (e.g. '08:00', '8', '00:00', '0') into minutes.
    - If shift_str is explicitly zero ('0', '00:00', '0:00', '00', '0.0', '0.00', 0),
      returns 0 (flexible / zero-shift employee).
    - If shift_str is None or empty string, returns default_minutes (e.g., 480).
    """
    if shift_str is None:
        return default_minutes
    s = str(shift_str).strip()
    if not s:
        return default_minutes
    if s in ['0', '00', '0:0', '0:00', '00:0', '00:00', '0.0', '0.00', '00.00']:
        return 0
    try:
        if ':' in s:
            parts = s.split(':')
            h = int(float(parts[0])) if parts[0].strip() else 0
            m = int(float(parts[1])) if len(parts) > 1 and parts[1].strip() else 0
            mins = h * 60 + m
            return max(0, mins)
        else:
            val = float(s)
            if val <= 0:
                return 0
            return int(round(val * 60))
    except Exception:
        return default_minutes

def create_employee(data, company_id=None):
    db = get_db()
    emp_name = str(data.get('employee_name') or '').strip()
    if not emp_name:
        raise ValueError('Employee name is required.')
    email_id = str(data.get('email_id') or '').strip()
    if not email_id:
        raise ValueError('Email ID is required.')

    emp_id = str(data.get('id') or '').strip()
    if not emp_id or db.employees.find_one({'id': emp_id}):
        emp_id = generate_employee_id()
    assigned_company_id = str(company_id or data.get('company_id') or 'ARGUS_MASTER')

    # Deduplication check: prevent duplicate employee creation from rapid multi-clicks
    existing_emp = db.employees.find_one({
        'company_id': assigned_company_id,
        'email_id': email_id
    })
    if existing_emp:
        created_at = existing_emp.get('created_at')
        try:
            if created_at and (get_ist_now() - created_at).total_seconds() < 10:
                return existing_emp.get('id')
        except Exception:
            pass
        raise ValueError(f"An employee with email '{email_id}' is already registered in this organization.")

    # Normalize status: default to 'Active'
    raw_status = str(data.get('status') or 'Active').strip().capitalize()
    emp_status = 'Inactive' if raw_status == 'Inactive' else 'Active'

    # Enforce Active Employee registration limit for tenant companies
    # Inactive employees do not count toward this limit
    if assigned_company_id != 'ARGUS_MASTER' and emp_status == 'Active':
        comp = db.company_admin.find_one(build_id_filter(assigned_company_id))
        if comp:
            try:
                limit = int(comp.get('employee_limit') or comp.get('employee_count') or 50)
            except (ValueError, TypeError):
                limit = 50
            current_count = db.employees.count_documents({
                'company_id': assigned_company_id,
                'status': {'$ne': 'Inactive'}
            })
            if current_count >= limit:
                comp_name = comp.get('company_name', assigned_company_id)
                raise ValueError(
                    f"Active employee registration limit reached: Company '{comp_name}' allows a maximum of {limit} active employees ({current_count}/{limit} currently active). Please mark existing employees as Inactive or contact System Admin to increase the employee limit."
                )

    raw_st = str(data.get('salary_type') or 'daily').strip().lower()
    salary_type = raw_st if raw_st in ['hourly', 'daily', 'half_day'] else 'daily'
    shift_val_str = str(data.get('shift_hours') or '').strip()
    shift_mins_emp = parse_shift_hours_to_minutes(shift_val_str, default_minutes=480)
    if shift_mins_emp == 0:
        shift_val_str = '00:00'

    if salary_type == 'hourly':
        h_sal = round(safe_float(data.get('hourly_salary')), 2)
        if shift_mins_emp == 0:
            d_sal = 0.0
            hd_sal = 0.0
        else:
            d_sal = round(safe_float(data.get('day_salary')), 2)
            hd_sal = round(safe_float(data.get('half_day_salary')), 2)
    else:
        h_sal = 0.0
        if shift_mins_emp == 0:
            d_sal = 0
            hd_sal = 0
        else:
            d_sal = int(round(safe_float(data.get('day_salary'))))
            hd_sal = int(round(safe_float(data.get('half_day_salary'))))
    
    doc = {
        'id': emp_id,
        'company_id': assigned_company_id,
        'employee_name': emp_name,
        'status': emp_status,
        'department': (data.get('department') or data.get('designation') or 'General').strip(),
        'designation': data.get('designation', '').strip(),
        'salary_type': salary_type,
        'mobile_number': data.get('mobile_number', '').strip(),
        'hourly_salary': h_sal,
        'day_salary': d_sal,
        'half_day_salary': hd_sal,
        'email_id': data.get('email_id', '').strip(),
        'aadhar_number': data.get('aadhar_number', '').strip(),
        'emergency_contact': data.get('emergency_contact', '').strip(),
        'date_of_birth': str(data.get('date_of_birth') or data.get('dob') or '').strip(),
        'joining_date': data.get('joining_date', '').strip(),
        'account_holder_name': data.get('account_holder_name', '').strip(),
        'upi_number': data.get('upi_number', '').strip(),
        'bank_name': data.get('bank_name', '').strip(),
        'account_number': data.get('account_number', '').strip(),
        'ifsc_code': data.get('ifsc_code', '').strip(),
        'shift_hours': shift_val_str,
        'shift_start': str(data.get('shift_start') or '09:00 AM').strip(),
        'shift_end': str(data.get('shift_end') or '06:00 PM').strip(),
        'photo': str(data.get('photo') or data.get('photo_filename') or '').strip(),
        'photo_filename': str(data.get('photo_filename') or data.get('photo') or '').strip(),
        'photo_data': str(data.get('photo_data') or '').strip(),
        'face_embedding': data.get('face_embedding', ''),
        'permissions': data.get('permissions', {
            'punch_attendance': True,
            'attendance_history': True,
            'monthly_payslip': True,
            'employee_credentials': True,
            'leave_permission': True
        }),
        'documents': data.get('documents', []),
        'is_field_worker': (
            (str(data.get('employee_type', '')).strip().lower() in ['field_worker', 'field', 'fw'])
            or (str(data.get('is_field_worker', '')).strip().lower() in ['true', '1', 'yes'])
            if (data.get('employee_type') is not None or data.get('is_field_worker') is not None)
            else False
        ),
        'territory_zone': str(data.get('territory_zone') or '').strip(),
        'per_visit_incentive': round(safe_float(data.get('per_visit_incentive')), 2),
        'km_allowance_rate': round(safe_float(data.get('km_allowance_rate')), 2),
        'branch_id': None,
        'branch_name': None,
        'created_at': get_ist_now(),
        'updated_at': get_ist_now()
    }

    # Resolve branch assignment if provided
    raw_bid = str(data.get('branch_id') or '').strip()
    if raw_bid and raw_bid not in ['ALL', 'all', '', 'none', 'None']:
        try:
            b_doc = get_branch_by_id(raw_bid, assigned_company_id)
            if b_doc:
                doc['branch_id'] = raw_bid
                doc['branch_name'] = b_doc.get('branch_name')
        except Exception:
            pass
    
    db.employees.insert_one(doc)
    invalidate_dashboard_cache(assigned_company_id)
    invalidate_branch_emp_cache(assigned_company_id)
    return emp_id

def update_employee(emp_id, data, company_id=None):
    db = get_db()
    f = build_id_filter(emp_id)
    if company_id and company_id != 'ALL':
        f = {'$and': [f, {'company_id': str(company_id)}]}
    if 'email_id' in data and not str(data.get('email_id') or '').strip():
        raise ValueError('Email ID is required.')

    upd = {'updated_at': get_ist_now()}

    text_fields = [
        'employee_name', 'department', 'designation', 'mobile_number', 'email_id',
        'aadhar_number', 'emergency_contact', 'date_of_birth', 'dob', 'joining_date', 'account_holder_name',
        'upi_number', 'bank_name', 'account_number', 'ifsc_code', 'shift_hours',
        'shift_start', 'shift_end', 'territory_zone'
    ]
    for key in text_fields:
        if key in data:
            upd[key] = str(data[key]).strip() if data[key] is not None else ''

    if 'employee_type' in data and data['employee_type'] is not None:
        upd['is_field_worker'] = str(data['employee_type']).strip().lower() in ['field_worker', 'field', 'fw']
    elif 'is_field_worker' in data and data['is_field_worker'] is not None:
        if isinstance(data['is_field_worker'], bool):
            upd['is_field_worker'] = data['is_field_worker']
        else:
            upd['is_field_worker'] = str(data['is_field_worker']).strip().lower() in ['true', '1', 'yes']

    if 'territory_zone' in data:
        upd['territory_zone'] = str(data['territory_zone']).strip() if data['territory_zone'] is not None else ''
    if 'per_visit_incentive' in data:
        upd['per_visit_incentive'] = round(safe_float(data['per_visit_incentive']), 2)
    if 'km_allowance_rate' in data:
        upd['km_allowance_rate'] = round(safe_float(data['km_allowance_rate']), 2)

    if 'salary_type' in data and data['salary_type']:
        st = str(data['salary_type']).strip().lower()
        if st in ['hourly', 'daily', 'half_day']:
            upd['salary_type'] = st

    existing_emp = db.employees.find_one(f) if f else None
    effective_st = upd.get('salary_type') or (existing_emp.get('salary_type') if existing_emp else 'daily')
    effective_shift_str = upd.get('shift_hours') if 'shift_hours' in upd else (existing_emp.get('shift_hours') if existing_emp else '08:00')
    effective_shift_mins = parse_shift_hours_to_minutes(effective_shift_str, default_minutes=480)
    if effective_shift_mins == 0 and 'shift_hours' in upd:
        upd['shift_hours'] = '00:00'

    if effective_st == 'hourly':
        if 'hourly_salary' in data:
            upd['hourly_salary'] = round(safe_float(data['hourly_salary']), 2)
        if effective_shift_mins == 0:
            upd['day_salary'] = 0.0
            upd['half_day_salary'] = 0.0
        else:
            if 'day_salary' in data:
                upd['day_salary'] = round(safe_float(data['day_salary']), 2)
            if 'half_day_salary' in data:
                upd['half_day_salary'] = round(safe_float(data['half_day_salary']), 2)
    else:
        if 'hourly_salary' in data:
            upd['hourly_salary'] = 0.0
        if effective_shift_mins == 0:
            upd['day_salary'] = 0
            upd['half_day_salary'] = 0
        else:
            if 'day_salary' in data:
                upd['day_salary'] = int(round(safe_float(data['day_salary'])))
            if 'half_day_salary' in data:
                upd['half_day_salary'] = int(round(safe_float(data['half_day_salary'])))

    photo_val = data.get('photo') or data.get('photo_filename')
    if photo_val:
        upd['photo_filename'] = str(photo_val).strip()
        upd['photo'] = str(photo_val).strip()

    if 'photo_data' in data and data['photo_data']:
        upd['photo_data'] = str(data['photo_data']).strip()

    if 'face_embedding' in data and data['face_embedding']:
        upd['face_embedding'] = data['face_embedding']
    if 'permissions' in data and isinstance(data['permissions'], dict):
        upd['permissions'] = data['permissions']
    if 'documents' in data and isinstance(data['documents'], list):
        upd['documents'] = data['documents']
    if 'company_id' in data and data['company_id']:
        upd['company_id'] = str(data['company_id'])

    if 'branch_id' in data:
        raw_bid = str(data.get('branch_id') or '').strip()
        if raw_bid and raw_bid not in ['ALL', 'all', '', 'none', 'None']:
            assigned_c_id = (existing_emp.get('company_id') if existing_emp else None) or company_id
            try:
                b_doc = get_branch_by_id(raw_bid, assigned_c_id)
                if b_doc:
                    upd['branch_id'] = raw_bid
                    upd['branch_name'] = b_doc.get('branch_name')
                else:
                    upd['branch_id'] = None
                    upd['branch_name'] = None
            except Exception:
                upd['branch_id'] = None
                upd['branch_name'] = None
        else:
            upd['branch_id'] = None
            upd['branch_name'] = None

    if 'status' in data and data['status'] is not None:
        raw_st_val = str(data['status']).strip().capitalize()
        new_status = 'Inactive' if raw_st_val == 'Inactive' else 'Active'
        if new_status == 'Active':
            existing_emp_doc = existing_emp or (db.employees.find_one(f) if f else None)
            existing_status = 'Active'
            if existing_emp_doc:
                existing_status = 'Inactive' if str(existing_emp_doc.get('status', 'Active')).strip().capitalize() == 'Inactive' else 'Active'
            if existing_status == 'Inactive':
                assigned_comp_id = (existing_emp_doc.get('company_id') if existing_emp_doc else None) or company_id
                if assigned_comp_id and assigned_comp_id != 'ARGUS_MASTER':
                    comp = db.company_admin.find_one(build_id_filter(assigned_comp_id))
                    if comp:
                        try:
                            limit = int(comp.get('employee_limit') or comp.get('employee_count') or 50)
                        except (ValueError, TypeError):
                            limit = 50
                        active_count = db.employees.count_documents({
                            'company_id': assigned_comp_id,
                            'status': {'$ne': 'Inactive'},
                            'id': {'$ne': emp_id}
                        })
                        if active_count >= limit:
                            comp_name = comp.get('company_name', assigned_comp_id)
                            raise ValueError(
                                f"Cannot activate employee: Company '{comp_name}' allows a maximum of {limit} active employees ({active_count}/{limit} currently active). Please mark another employee as Inactive first or contact System Admin to increase the employee limit."
                            )
        upd['status'] = new_status
        
    db.employees.update_one(f, {'$set': upd})
    invalidate_dashboard_cache(company_id)
    invalidate_branch_emp_cache(company_id)
    return True

def delete_employee(emp_id, company_id=None):
    db = get_db()
    f = build_id_filter(emp_id)
    if company_id and company_id != 'ALL':
        f = {'$and': [f, {'company_id': str(company_id)}]}
    db.employees.delete_one(f)
    invalidate_dashboard_cache(company_id)
    invalidate_branch_emp_cache(company_id)
    return True

def get_all_face_embeddings(company_id=None):
    db = get_db()
    q = {'face_embedding': {'$nin': ['', 'null', None], '$exists': True}}
    if company_id and company_id != 'ALL':
        q['company_id'] = str(company_id)
    employees = db.employees.find(q)
    results = []
    for emp in employees:
        embedding_data = emp.get('face_embedding', '')
        if embedding_data and embedding_data != 'null':
            try:
                embedding = json.loads(embedding_data) if isinstance(embedding_data, str) else embedding_data
                if embedding and isinstance(embedding, (list, tuple)) and len(embedding) > 0:
                    results.append({
                        'id': str(emp.get('id', emp.get('_id', ''))),
                        'employee_name': emp.get('employee_name', ''),
                        'company_id': emp.get('company_id', 'ARGUS_MASTER'),
                        'embedding': [float(x) for x in embedding]
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

_dashboard_cache = {}
_dashboard_cache_ttl = 30  # seconds

def invalidate_dashboard_cache(company_id=None):
    global _dashboard_cache
    invalidate_employee_names_cache(company_id)
    if company_id:
        _dashboard_cache.pop(str(company_id), None)
        _dashboard_cache.pop('ALL', None)
        _dashboard_cache.pop(None, None)
    else:
        _dashboard_cache.clear()

_employee_names_cache = {}
_employee_names_cache_ttl = 60  # seconds

def invalidate_employee_names_cache(company_id=None):
    global _employee_names_cache
    if company_id:
        _employee_names_cache.pop(str(company_id), None)
        _employee_names_cache.pop('ALL', None)
        _employee_names_cache.pop(None, None)
    else:
        _employee_names_cache.clear()

def get_employee_names_cached(company_id=None, branch_id=None):
    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    cache_key = f"{company_id or 'ALL'}:{b_id or 'ALL'}"
    now_ts = time.time()
    if cache_key in _employee_names_cache:
        entry_time, cached_val = _employee_names_cache[cache_key]
        if now_ts - entry_time < _employee_names_cache_ttl:
            return cached_val

    db = get_db()
    filt = get_branch_employee_query(b_id, company_id)

    cursor = db.employees.find(filt, {'employee_name': 1}).sort('employee_name', 1)
    names = [doc.get('employee_name') for doc in cursor if doc.get('employee_name')]
    _employee_names_cache[cache_key] = (now_ts, names)
    return names

def get_dashboard_stats(company_id=None, branch_id=None):
    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', ''] else None
    cache_key = f"{company_id or 'ALL'}:{b_id or 'ALL'}"
    now_ts = time.time()
    if cache_key in _dashboard_cache:
        entry_time, cached_val = _dashboard_cache[cache_key]
        if now_ts - entry_time < _dashboard_cache_ttl:
            return cached_val

    db = get_db()
    t_filter = get_branch_employee_query(b_id, company_id)
        
    branch_emp_names = set()
    if b_id:
        b_emps = list(db.employees.find(t_filter, {'employee_name': 1}))
        branch_emp_names = set(e.get('employee_name') for e in b_emps if e.get('employee_name'))

    total_preserved_employees = db.employees.count_documents(t_filter)
    total_employees = db.employees.count_documents({**t_filter, 'status': {'$ne': 'Inactive'}})
    
    # Calculate today's active punches across live punches, attendance, reports, and manual entries
    now_ist = get_ist_now()
    today = now_ist.date()
    today_str = now_ist.strftime('%Y-%m-%d')
    today_slash = now_ist.strftime('%d/%m/%Y')
    curr_year = now_ist.year
    curr_month = now_ist.month

    # Fetch today's records upfront in batch (avoids duplicate queries)
    comp_base = {'company_id': str(company_id)} if (company_id and company_id != 'ALL') else {}
    if b_id:
        branch_punch_matcher = get_branch_record_condition(b_id, branch_emp_names)
        def _combine_filter(*parts):
            clean = [p for p in parts if p]
            if not clean:
                return {}
            if len(clean) == 1:
                return dict(clean[0])
            return {'$and': [dict(p) for p in clean]}

        record_base = _combine_filter(comp_base, branch_punch_matcher)
        p_filter = _combine_filter(comp_base, branch_punch_matcher, {'date': today_str})
        ar_today_filter = _combine_filter(comp_base, branch_punch_matcher, {'date': today_str})
        l_filter = _combine_filter(comp_base, branch_punch_matcher, {'entry_time': {'$regex': today_slash}})
        m_filter = _combine_filter(comp_base, branch_punch_matcher, {
            '$or': [
                {'entry_date': today_str},
                {'submitted_at': {'$regex': today_str}},
                {'submitted_at': {'$regex': today_slash}}
            ]
        })
        timeout_filter = _combine_filter(comp_base, branch_punch_matcher, {
            '$or': [{'entry_time': {'$regex': today_slash}}, {'exit_time': {'$regex': today_slash}}]
        })
    else:
        record_base = dict(t_filter)
        p_filter = dict(t_filter)
        p_filter['date'] = today_str
        ar_today_filter = dict(t_filter)
        ar_today_filter['date'] = today_str
        l_filter = dict(t_filter)
        l_filter['entry_time'] = {'$regex': today_slash}
        m_filter = dict(t_filter)
        m_filter['$or'] = [
            {'entry_date': today_str},
            {'submitted_at': {'$regex': today_str}},
            {'submitted_at': {'$regex': today_slash}}
        ]
        timeout_filter = {**t_filter, '$or': [{'entry_time': {'$regex': today_slash}}, {'exit_time': {'$regex': today_slash}}]}

    att_docs = {a['employee_name']: a for a in db.attendance.find(p_filter)}
    ar_docs = {a['employee_name']: a for a in db.attendance_reports.find(ar_today_filter)}
    live_docs = {l['employee_name']: l for l in db.live_entries.find(l_filter)}
    manual_docs = {m['employee_name']: m for m in db.manual_entries.find(m_filter)}
    timeout_today = {t['employee_name']: t for t in db.timeout_entries.find(timeout_filter)}
    combined_present = set(att_docs.keys()).union(set(ar_docs.keys())).union(set(live_docs.keys())).union(set(manual_docs.keys())).union(set(timeout_today.keys()))
    present_count = len(combined_present)

    # Approved leaves today integration
    approved_leaves_today = get_approved_leaves_for_date(today_str, company_id=company_id)
    if b_id:
        approved_leaves_today = {k: v for k, v in approved_leaves_today.items() if k in branch_emp_names}
    on_leave_set = set(approved_leaves_today.keys()).difference(combined_present)
    on_leave_count = len(on_leave_set)

    absent_count = max(0, total_employees - present_count - on_leave_count)
    present_percentage = round((present_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    on_leave_percentage = round((on_leave_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    absent_percentage = round((absent_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    
    tout_filter = dict(record_base)
    tout_filter['is_timeout'] = 1
    timeout_count = db.timeout_entries.count_documents(dict(record_base)) + db.live_entries.count_documents(tout_filter)
    timeout_percentage = round((timeout_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    
    # Last 7 days dynamic calculation in BATCH queries (replaces 35 individual network calls)
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    day_map = {d.strftime('%Y-%m-%d'): {'label': d.strftime('%d %b'), 'slash': d.strftime('%d/%m/%Y'), 'present': set(), 'timeouts': 0} for d in days}
    day_strs = list(day_map.keys())
    day_slashes = [v['slash'] for v in day_map.values()]

    att_7d = list(db.attendance.find({**record_base, 'date': {'$in': day_strs}}, {'employee_name': 1, 'date': 1}))
    for a in att_7d:
        dt = a.get('date')
        if dt in day_map and a.get('employee_name'):
            day_map[dt]['present'].add(a['employee_name'])

    ar_7d = list(db.attendance_reports.find({**record_base, 'date': {'$in': day_strs}}, {'employee_name': 1, 'date': 1}))
    for a in ar_7d:
        dt = a.get('date')
        if dt in day_map and a.get('employee_name'):
            day_map[dt]['present'].add(a['employee_name'])

    slash_pattern = "|".join([d.replace('/', '\\/') for d in day_slashes])
    hyphen_pattern = "|".join(day_strs)
    me_7d = list(db.manual_entries.find({
        **record_base,
        '$or': [
            {'entry_date': {'$in': day_strs}},
            {'submitted_at': {'$regex': hyphen_pattern}},
            {'submitted_at': {'$regex': slash_pattern}}
        ]
    }, {'employee_name': 1, 'entry_date': 1, 'submitted_at': 1}))
    for m in me_7d:
        ename = m.get('employee_name')
        edate = m.get('entry_date') or m.get('submitted_at', '')
        for dt, info in day_map.items():
            if dt in edate or info['slash'] in edate:
                if ename:
                    info['present'].add(ename)
                break

    live_7d = list(db.live_entries.find({**record_base, 'entry_time': {'$regex': slash_pattern}}, {'employee_name': 1, 'entry_time': 1, 'is_timeout': 1}))
    for l in live_7d:
        et = l.get('entry_time', '')
        ename = l.get('employee_name')
        for dt, info in day_map.items():
            if info['slash'] in et:
                if ename:
                    info['present'].add(ename)
                if l.get('is_timeout') == 1:
                    info['timeouts'] += 1
                break

    timeout_7d = list(db.timeout_entries.find({**record_base, '$or': [{'entry_time': {'$regex': slash_pattern}}, {'exit_time': {'$regex': slash_pattern}}]}, {'employee_name': 1, 'entry_time': 1, 'exit_time': 1}))
    for t_doc in timeout_7d:
        et = t_doc.get('exit_time') or t_doc.get('entry_time', '')
        ename = t_doc.get('employee_name')
        for dt, info in day_map.items():
            if info['slash'] in et:
                if ename:
                    info['present'].add(ename)
                info['timeouts'] += 1
                break

    last_7_days = []
    for dt in day_strs:
        info = day_map[dt]
        p_cnt = len(info['present'])
        last_7_days.append({
            'date': info['label'],
            'present': p_cnt,
            'absent': max(0, total_employees - p_cnt),
            'timeout': info['timeouts'],
            'count': p_cnt
        })
        
    # Monthly stats dynamic calculation in BATCH queries (replaces 48 individual network calls)
    months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_map = {m_idx: {'present_cnt': 0, 'timeout_cnt': 0} for m_idx in range(1, 13)}

    year_att = list(db.attendance.find({**record_base, 'date': {'$regex': f"^{curr_year}-"}}, {'date': 1}))
    for a in year_att:
        dt = a.get('date', '')
        if len(dt) >= 7:
            try:
                m_idx = int(dt[5:7])
                if m_idx in monthly_map:
                    monthly_map[m_idx]['present_cnt'] += 1
            except Exception:
                pass

    year_ar = list(db.attendance_reports.find({**record_base, 'date': {'$regex': f"^{curr_year}-"}}, {'date': 1}))
    for a in year_ar:
        dt = a.get('date', '')
        if len(dt) >= 7:
            try:
                m_idx = int(dt[5:7])
                if m_idx in monthly_map:
                    monthly_map[m_idx]['present_cnt'] += 1
            except Exception:
                pass

    year_me = list(db.manual_entries.find({
        **record_base,
        '$or': [
            {'entry_date': {'$regex': f"^{curr_year}-"}},
            {'submitted_at': {'$regex': f"^{curr_year}-"}},
            {'submitted_at': {'$regex': f"-{curr_year}$"}}
        ]
    }, {'entry_date': 1, 'submitted_at': 1}))
    for m in year_me:
        dt = m.get('entry_date') or m.get('submitted_at', '')
        if len(dt) >= 7:
            try:
                if dt[4] == '-':
                    m_idx = int(dt[5:7])
                elif '/' in dt:
                    m_idx = int(dt.split('/')[1])
                else:
                    m_idx = 0
                if m_idx in monthly_map:
                    monthly_map[m_idx]['present_cnt'] += 1
            except Exception:
                pass

    year_live = list(db.live_entries.find({**record_base, 'entry_time': {'$regex': f"/{curr_year}"}}, {'entry_time': 1, 'is_timeout': 1}))
    for l in year_live:
        et = l.get('entry_time', '')
        sp = et.split('/')
        if len(sp) >= 2:
            try:
                m_idx = int(sp[1])
                if m_idx in monthly_map and l.get('is_timeout') == 1:
                    monthly_map[m_idx]['timeout_cnt'] += 1
            except Exception:
                pass

    monthly_stats = []
    for m_idx, m_name in enumerate(months, start=1):
        info = monthly_map[m_idx]
        total_monthly_punches = info['present_cnt']
        m_absent = max(0, total_employees * 26 - total_monthly_punches) if (m_idx <= curr_month and total_employees > 0 and total_monthly_punches > 0) else 0
        monthly_stats.append({
            'month': m_name,
            'present': total_monthly_punches,
            'absent': m_absent,
            'timeout': info['timeout_cnt'],
            'count': total_monthly_punches
        })
        
    # Today's attendance list & Department summary (Active employees only)
    employees = list(db.employees.find({**t_filter, 'status': {'$ne': 'Inactive'}}, {'_id': 0, 'id': 1, 'employee_name': 1, 'department': 1, 'designation': 1, 'branch_id': 1, 'branch_name': 1}))
    
    today_attendance = []
    present_names_set = set()
    timeout_names_set = set()
    on_leave_names_set = set()
    
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
        elif ename in approved_leaves_today or str(emp.get('id', '')) in approved_leaves_today:
            l_info = approved_leaves_today.get(ename) or approved_leaves_today.get(str(emp.get('id', '')))
            l_type = l_info.get('leave_type') or 'Leave'
            hours = l_type
            status = 'On Leave'
            on_leave_names_set.add(ename)
            
        today_attendance.append({
            'employee_name': ename,
            'department': emp.get('department') or emp.get('designation') or 'General',
            'branch_id': emp.get('branch_id') or '',
            'branch_name': emp.get('branch_name') or '',
            'in_time': in_time,
            'out_time': out_time,
            'hours': hours,
            'status': status
        })
        
    status_order = {'Present': 0, 'On Leave': 1, 'Timeout': 2, 'Absent': 3}
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
            dept_map[dept] = {'department': dept, 'total': 0, 'present': 0, 'leave': 0, 'absent': 0, 'timeout': 0}
        dept_map[dept]['total'] += 1
        ename = emp.get('employee_name', '')
        if ename in timeout_names_set:
            dept_map[dept]['timeout'] += 1
        elif ename in present_names_set:
            dept_map[dept]['present'] += 1
        elif ename in on_leave_names_set:
            dept_map[dept]['leave'] += 1
        else:
            dept_map[dept]['absent'] += 1
            
    department_summary = list(dept_map.values())
    department_summary.sort(key=lambda x: x['total'], reverse=True)
    
    res = {
        'total': total_employees,
        'total_active': total_employees,
        'total_preserved': total_preserved_employees,
        'present': present_count,
        'on_leave': on_leave_count,
        'on_leave_percentage': on_leave_percentage,
        'on_leave_percent': f"{on_leave_percentage}%",
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
    _dashboard_cache[cache_key] = (now_ts, res)
    return res

# ----------------- LIVE & TIMEOUT ENTRIES ----------------- #

def process_company_timeout_entries(company_id=None):
    """
    Checks for employees who punched in and forgot to punch out.
    If current IST time exceeds (entry_time + shift_hours),
    automatically completes their punch-out according to the shift time.
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
        cid = str(rep.get('company_id', 'ARGUS_MASTER'))
        emp_name = rep.get('employee_name', '')
        
        # Determine shift duration: prioritize employee shift, fallback to company shift
        if cid not in company_shifts:
            comp = db.company_admin.find_one({'id': cid})
            company_shifts[cid] = comp.get('shift_hours', '08:00') if comp else '08:00'
            
        emp = db.employees.find_one({'employee_name': emp_name}) if emp_name else None
        emp_shift = emp.get('shift_hours') if emp else None
        shift_str = emp_shift if emp_shift is not None and str(emp_shift).strip() != '' else company_shifts.get(cid, '08:00')
        
        shift_mins = parse_shift_hours_to_minutes(shift_str, default_minutes=480)
        if shift_mins == 0:
            # Zero-shift-hour employee (e.g. flexible hourly employee):
            # Never auto-calculate daily/shift working hours or salary!
            # Salary must only be calculated when they actually Punch-In AND Punch-Out.
            continue
        shift_h = shift_mins // 60
        shift_m = shift_mins % 60
            
        entry_time_str = rep.get('entry_time', '')
        entry_dt = None
        for fmt in [
            '%d/%m/%Y %I:%M:%S %p',
            '%d/%m/%Y %I:%M %p',
            '%d/%m/%Y %H:%M:%S',
            '%d/%m/%Y %H:%M',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d %I:%M:%S %p',
            '%d-%m-%Y %I:%M:%S %p',
            '%d-%m-%Y %H:%M:%S'
        ]:
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
            
        # Determine employee's scheduled shift end time and calculate auto exit timestamp
        shift_end_str = str(emp.get('shift_end') or '06:00 PM').strip() if emp else '06:00 PM'
        end_time_obj = None
        for t_fmt in ['%I:%M %p', '%I:%M:%S %p', '%H:%M', '%H:%M:%S']:
            try:
                end_time_obj = datetime.strptime(shift_end_str, t_fmt).time()
                break
            except Exception:
                pass
        if not end_time_obj:
            end_time_obj = dt_time(18, 0)  # Default 06:00 PM

        # Scheduled shift end on the exact entry date
        scheduled_end_dt = datetime.combine(entry_dt.date(), end_time_obj).replace(tzinfo=IST)

        shift_start_str = str(emp.get('shift_start') or '09:00 AM').strip() if emp else '09:00 AM'
        start_time_obj = None
        for t_fmt in ['%I:%M %p', '%I:%M:%S %p', '%H:%M', '%H:%M:%S']:
            try:
                start_time_obj = datetime.strptime(shift_start_str, t_fmt).time()
                break
            except Exception:
                pass
        
        is_night_shift = False
        if start_time_obj and end_time_obj:
            is_night_shift = (end_time_obj <= start_time_obj)

        if is_night_shift:
            if scheduled_end_dt <= entry_dt:
                scheduled_end_dt += timedelta(days=1)
            auto_exit_dt = scheduled_end_dt
        else:
            # Daytime shift: auto timeout MUST remain on the SAME date as entry_dt (never roll into next day)
            shift_plus_mins = entry_dt + timedelta(minutes=shift_mins)
            if shift_plus_mins.date() == entry_dt.date():
                auto_exit_dt = max(scheduled_end_dt, shift_plus_mins) if entry_dt < scheduled_end_dt else shift_plus_mins
            else:
                if entry_dt < scheduled_end_dt:
                    auto_exit_dt = scheduled_end_dt
                else:
                    same_day_end = datetime.combine(entry_dt.date(), dt_time(23, 59, 59)).replace(tzinfo=IST)
                    auto_exit_dt = min(entry_dt + timedelta(minutes=30), same_day_end)
        
        # If current time is strictly past scheduled shift exit, auto timeout punch-out
        if now >= auto_exit_dt:
            auto_exit_str = auto_exit_dt.strftime('%d/%m/%Y %I:%M:%S %p')
            working_hours_str = f"{shift_h:02d}:{shift_m:02d}"
            
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
                    'exit_location': f"Auto Punch-Out based on Shift Time ({shift_str})",
                    'working_hours': working_hours_str,
                    'shift_variance': '00:00',
                    'day_credit_type': day_credit_type,
                    'working_salary': working_salary,
                    'is_timeout': 1,
                    'exit_status': 'Auto Timeout',
                    'entry_type': rep.get('entry_type', 'proper'),
                    'updated_at': now.isoformat()
                }}
            )
            
            # Store in timeout_entries
            timeout_filter = {
                'company_id': str(cid),
                'employee_name': emp_name,
                'exit_time': auto_exit_str
            }
            if not db.timeout_entries.find_one(timeout_filter):
                active_live = db.live_entries.find_one({
                    'company_id': str(cid),
                    'employee_name': emp_name,
                    'entry_time': entry_time_str
                })

                entry_t = active_live.get('entry_time', entry_time_str) if active_live else entry_time_str
                entry_l = active_live.get('entry_location', rep.get('entry_location', 'OFFICE')) if active_live else rep.get('entry_location', 'OFFICE')
                entry_d = active_live.get('entry_distance', 0.0) if active_live else 0.0

                db.timeout_entries.insert_one({
                    'company_id': str(cid),
                    'employee_id': rep.get('employee_id', ''),
                    'employee_name': emp_name,
                    'entry_time': entry_t,
                    'exit_time': auto_exit_str,
                    'working_hours': working_hours_str,
                    'site_name': 'OFFICE (AUTO TIMEOUT)',
                    'entry_location': entry_l,
                    'exit_location': f"Auto Punch-Out based on Shift Time ({shift_str})",
                    'entry_distance': entry_d,
                    'exit_distance': '0.0M (AUTO TIMEOUT)',
                    'formatted_distance': '0.0M (AUTO TIMEOUT)',
                    'is_timeout': 1,
                    'exit_status': 'Auto Timeout',
                    'created_at': now.isoformat()
                })

            # Remove from live_entries ONLY for this specific session
            db.live_entries.delete_many({
                'company_id': str(cid),
                'employee_name': emp_name,
                'entry_time': entry_time_str
            })
            auto_count += 1
            
    return auto_count

def sync_live_and_timeout_entries(company_id=None):
    """
    Ensures db.live_entries contains ALL active punched-in employees currently on duty (exit_time == '----').
    1. First runs process_company_timeout_entries to auto punch-out sessions that passed shift duration.
    2. Synchronizes active uncompleted reports (exit_time == '----') into db.live_entries.
    3. Purges stale entries from db.live_entries whose session has been punched out or timed out.
    4. Removes any erroneously created timeout_entries that match an actively open session.
    """
    try:
        db = get_db()
        now = get_ist_now()
        
        # 1. Process any overdue timeouts first
        process_company_timeout_entries(company_id=company_id)
        
        # 2. Find all active attendance reports with exit_time == '----'
        rep_query = {'exit_time': '----'}
        if company_id and company_id != 'ALL':
            rep_query['company_id'] = str(company_id)
            
        open_reps = list(db.attendance_reports.find(rep_query))
        open_session_keys = set()
        
        for rep in open_reps:
            cid = str(rep.get('company_id', 'ARGUS_MASTER'))
            emp_name = rep.get('employee_name')
            entry_t = rep.get('entry_time')
            if not emp_name or not entry_t:
                continue
                
            session_key = (cid, emp_name, entry_t)
            open_session_keys.add(session_key)
            
            # Parse distance
            dist_num = 0.0
            try:
                d_val = rep.get('entry_distance', 0.0)
                if isinstance(d_val, (int, float)):
                    dist_num = float(d_val)
                else:
                    d_str = str(d_val).upper().replace('OFFICE DISTANCE', '').replace('KM', '').replace('M', '').strip()
                    dist_num = float(d_str)
                    if 'KM' in str(d_val).upper():
                        dist_num *= 1000.0
            except Exception:
                dist_num = 0.0
                
            entry_loc = rep.get('entry_location') or get_company_full_address(cid)
            formatted_dist = rep.get('entry_distance') if (rep.get('entry_distance') and 'OFFICE' in str(rep.get('entry_distance'))) else format_office_distance(dist_num)
            
            # Ensure in db.live_entries
            db.live_entries.update_one(
                {
                    'company_id': cid,
                    'employee_name': emp_name,
                    'entry_time': entry_t
                },
                {
                    '$setOnInsert': {
                        'company_id': cid,
                        'employee_id': str(rep.get('employee_id', '')),
                        'employee_name': emp_name,
                        'entry_time': entry_t,
                        'site_name': 'OFFICE',
                        'entry_location': entry_loc,
                        'entry_distance': dist_num,
                        'formatted_distance': formatted_dist,
                        'user_lat': rep.get('entry_lat'),
                        'user_lng': rep.get('entry_lng'),
                        'is_timeout': 0,
                        'created_at': rep.get('created_at', now.isoformat())
                    }
                },
                upsert=True
            )
            
            # If an errant record in timeout_entries matches this active session, remove it
            db.timeout_entries.delete_many({
                'company_id': cid,
                'employee_name': emp_name,
                'entry_time': entry_t
            })
            
        # 3. Clean up any entries in live_entries that are no longer open in attendance_reports
        live_query = {}
        if company_id and company_id != 'ALL':
            live_query['company_id'] = str(company_id)
            
        for live_doc in list(db.live_entries.find(live_query)):
            cid = str(live_doc.get('company_id', 'ARGUS_MASTER'))
            emp_name = live_doc.get('employee_name')
            entry_t = live_doc.get('entry_time')
            
            # If not in open_session_keys, this session is no longer active!
            if (cid, emp_name, entry_t) not in open_session_keys:
                db.live_entries.delete_one({'_id': live_doc['_id']})
                
    except Exception as e:
        print(f"Warning in sync_live_and_timeout_entries: {e}")

def get_live_report_entries(tab='live', start_date=None, end_date=None, search=None, page=1, limit=10, company_id=None, branch_id=None):
    sync_live_and_timeout_entries(company_id=company_id)
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)

    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if b_id:
        b_emp_q = get_branch_employee_query(b_id, company_id)
        b_emps = list(db.employees.find(b_emp_q, {'employee_name': 1}))
        b_names = set(e.get('employee_name') for e in b_emps if e.get('employee_name'))
        branch_cond = get_branch_record_condition(b_id, b_names)
        if branch_cond:
            query.setdefault('$and', []).append(branch_cond)
        
    target_coll = db.timeout_entries if tab == 'timeout' else db.live_entries

    if not start_date and not end_date:
        def_start, _, _, _ = get_default_two_month_range()
        start_date = def_start

    # Pre-load employee shift hours for dynamic status computation
    emp_shifts = {}
    emp_q = get_branch_employee_query(b_id, company_id)
    for emp_d in db.employees.find(emp_q, {'employee_name': 1, 'shift_start': 1, 'shift_end': 1, 'shift_hours': 1}):
        if emp_d.get('employee_name'):
            emp_shifts[emp_d['employee_name']] = {
                'start': emp_d.get('shift_start', '09:00 AM') or '09:00 AM',
                'end': emp_d.get('shift_end', '06:00 PM') or '06:00 PM',
                'shift_mins': parse_shift_hours_to_minutes(emp_d.get('shift_hours', '08:00'), default_minutes=480)
            }

    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        query['$or'] = [
            {'employee_name': reg},
            {'site_name': reg},
            {'entry_location': reg},
            {'exit_location': reg},
            {'entry_time': reg},
            {'exit_time': reg}
        ]
        
    if start_date:
        s_date = start_date.strip()
        parts = s_date.split('-')
        d_slash = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else s_date
        query.setdefault('$and', []).append({
            '$or': [
                {'created_at': {'$gte': s_date}},
                {'entry_time': {'$regex': f"^{re.escape(d_slash)}"}},
                {'exit_time': {'$regex': f"^{re.escape(d_slash)}"}}
            ]
        })
    if end_date:
        e_date = end_date.strip()
        parts = e_date.split('-')
        d_slash_e = f"{parts[2]}/{parts[1]}/{parts[0]}" if len(parts) == 3 else e_date
        query.setdefault('$and', []).append({
            '$or': [
                {'created_at': {'$lte': e_date + 'T23:59:59'}},
                {'entry_time': {'$regex': f"^{re.escape(d_slash_e)}"}},
                {'exit_time': {'$regex': f"^{re.escape(d_slash_e)}"}}
            ]
        })
        
    total = target_coll.count_documents(query)
    cursor = target_coll.find(query).sort([("created_at", DESCENDING), ("_id", DESCENDING)])
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = []
    for doc in cursor:
        c = clean_doc(doc)
        cid = c.get('company_id') or company_id
        full_addr = get_company_full_address(cid)
        if not c.get('entry_location') or str(c.get('entry_location')).strip() in ['OFFICE', '----', '']:
            if c.get('user_lat') and c.get('user_lng'):
                c['entry_location'] = reverse_geocode_coordinates(c['user_lat'], c['user_lng']) or full_addr
            else:
                c['entry_location'] = full_addr
            
        if c.get('exit_location') and str(c.get('exit_location')).strip() not in ['----', '-', '']:
            if str(c.get('exit_location')).strip() == 'OFFICE':
                if c.get('exit_lat') and c.get('exit_lng'):
                    c['exit_location'] = reverse_geocode_coordinates(c['exit_lat'], c['exit_lng']) or full_addr
                else:
                    c['exit_location'] = full_addr

        s_cfg = emp_shifts.get(c.get('employee_name', ''), {'start': '09:00 AM', 'end': '06:00 PM', 'shift_mins': 480})
        e_status, x_status = compute_entry_exit_status(c.get('entry_time'), c.get('exit_time'), s_cfg['start'], s_cfg['end'], is_manual=False, shift_mins=s_cfg.get('shift_mins', 480))
        c['entry_status'] = e_status
        if tab == 'timeout' or c.get('is_timeout') or 'AUTO TIMEOUT' in str(c.get('exit_distance', '')).upper() or 'AUTO PUNCH-OUT' in str(c.get('exit_location', '')).upper():
            c['exit_status'] = 'Auto Timeout'
        else:
            c['exit_status'] = x_status

        data.append(c)
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
GEOFENCE_RADIUS_METERS = 200.0  # Proper entries <= 200 meters, Improper entries > 200 meters

def parse_distance_meters_val(dist_str):
    """Parse distance strings like 'OFFICE DISTANCE 23.5M' or '3.19KM' to float meters."""
    if not dist_str:
        return None
    s = str(dist_str).strip()
    if s in ['----', 'MANUAL ENTRY', '0.0M (AUTO TIMEOUT)', '']:
        return None
    m = re.search(r'([\d.]+)\s*(KM|M)', s, re.IGNORECASE)
    if m:
        try:
            val = float(m.group(1))
            unit = m.group(2).upper()
            return (val * 1000.0) if unit == 'KM' else val
        except Exception:
            return None
    return None

def sync_geofence_entry_types():
    """Synchronize attendance_reports entry_type to strictly match each company's geofencing rule."""
    try:
        db = get_db()
        comp_radii = {}
        for c in db.company_admin.find({}, {'id': 1, 'geofence_radius': 1, 'radius_meters': 1}):
            cid = c.get('id')
            if cid:
                comp_radii[cid] = float(c.get('geofence_radius') or c.get('radius_meters') or GEOFENCE_RADIUS_METERS)

        for doc in db.attendance_reports.find({}):
            e_dist = parse_distance_meters_val(doc.get('entry_distance'))
            x_dist = parse_distance_meters_val(doc.get('exit_distance'))
            
            # If neither distance is recorded (e.g. legacy/mock records without distances), leave as-is
            if e_dist is None and x_dist is None:
                continue

            c_id = doc.get('company_id', 'ARGUS_MASTER')
            threshold = comp_radii.get(c_id, GEOFENCE_RADIUS_METERS)

            is_outside = False
            if e_dist is not None and e_dist > threshold:
                is_outside = True
            if x_dist is not None and x_dist > threshold:
                is_outside = True

            target_type = 'improper' if is_outside else 'proper'
            if doc.get('entry_type') != target_type:
                db.attendance_reports.update_one({'_id': doc['_id']}, {'$set': {'entry_type': target_type}})
    except Exception as e:
        print(f"Warning in sync_geofence_entry_types: {e}")

# Note: sync_live_and_timeout_entries is defined above with full session-aware auto-timeout & live-sync logic.

def calculate_distance_meters(lat1, lon1, lat2=OFFICE_LAT, lon2=OFFICE_LNG):
    """Calculate distance in meters between two GPS coordinates using Haversine formula."""
    import math
    try:
        lat1 = parse_coordinate_to_float(lat1, OFFICE_LAT)
        lon1 = parse_coordinate_to_float(lon1, OFFICE_LNG)
        lat2 = parse_coordinate_to_float(lat2, OFFICE_LAT)
        lon2 = parse_coordinate_to_float(lon2, OFFICE_LNG)
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

def get_company_full_address(company_id):
    """Returns the registered full address string for a company, auto-resolving coordinates if needed."""
    db = get_db()
    if not company_id or str(company_id).strip() in ['ARGUS_MASTER', 'ALL', '']:
        comp = db.company_admin.find_one({'id': 'ARGUS_MASTER'})
        if comp and (comp.get('address') or comp.get('location')):
            return (comp.get('address') or comp.get('location')).strip()
        return OFFICE_LOCATION_STR

    comp = db.company_admin.find_one({'id': str(company_id)})
    if not comp:
        comp = db.company_admin.find_one(build_id_filter(company_id))

    if comp:
        addr = (comp.get('address') or comp.get('location') or '').strip()
        # If company has an actual custom address (and not the generic master fallback)
        if addr and addr not in [OFFICE_LOCATION_STR, '----', '']:
            return addr

        # Auto-resolve from company registered coordinates if available
        lat = comp.get('latitude')
        lng = comp.get('longitude')
        if lat is not None and lng is not None:
            resolved = reverse_geocode_coordinates(lat, lng)
            if resolved:
                try:
                    db.company_admin.update_one({'_id': comp['_id']}, {'$set': {'address': resolved, 'location': resolved}})
                except Exception:
                    pass
                return resolved

        c_name = (comp.get('company_name') or '').strip()
        if c_name:
            return f"{c_name} Office"

    return "Company Office"

get_live_entries = get_live_report_entries

def delete_live_report_entry(entry_id, entry_type='live', company_id=None):
    """
    Deletes an entry from live_entries or timeout_entries.
    Also purges corresponding attendance_reports and attendance records
    so sync_live_and_timeout_entries does not regenerate the entry.
    """
    db = get_db()
    id_filter = build_id_filter(entry_id)
    
    target_coll = db.timeout_entries if entry_type == 'timeout' else db.live_entries
    alt_coll = db.live_entries if entry_type == 'timeout' else db.timeout_entries
    
    doc = target_coll.find_one(id_filter)
    target_used = target_coll
    if not doc:
        doc = alt_coll.find_one(id_filter)
        target_used = alt_coll

    deleted = False
    if doc:
        emp_name = doc.get('employee_name')
        entry_t = doc.get('entry_time')
        cid = doc.get('company_id') or company_id
        
        target_used.delete_one({'_id': doc['_id']})
        if emp_name and entry_t:
            alt_coll.delete_many({'employee_name': emp_name, 'entry_time': entry_t})
            
            # Remove from attendance_reports
            att_rep_filter = {'employee_name': emp_name, 'entry_time': entry_t}
            if cid and cid != 'ALL':
                att_rep_filter['company_id'] = str(cid)
            db.attendance_reports.delete_many(att_rep_filter)
            
            # Clean up db.attendance
            entry_t_str = str(entry_t)
            time_prefix = entry_t_str[:10]
            db.attendance.delete_many({
                '$and': [
                    {'$or': [{'employee_name': emp_name}, {'name': emp_name}]},
                    {'$or': [
                        {'punch_time': entry_t},
                        {'timestamp': {'$regex': f"^{re.escape(time_prefix)}"}}
                    ]}
                ]
            })
        deleted = True
    else:
        res1 = target_coll.delete_one(id_filter)
        res2 = alt_coll.delete_one(id_filter)
        deleted = (res1.deleted_count > 0 or res2.deleted_count > 0)
        
    return deleted

_GEOCODE_CACHE = {}

def reverse_geocode_coordinates(lat, lng, timeout=3.5):
    """
    Reverse-geocodes GPS (lat, lng) to the exact real-time physical address where employee punched.
    Uses in-memory cache, OpenStreetMap Nominatim, and BigDataCloud fallback.
    Returns the real-time physical address string or None if unresolvable.
    """
    if lat is None or lng is None:
        return None
    try:
        flat = float(str(lat).strip())
        flng = float(str(lng).strip())
        if abs(flat) < 0.0001 and abs(flng) < 0.0001:
            return None
        if not (-90.0 <= flat <= 90.0 and -180.0 <= flng <= 180.0):
            return None
            
        cache_key = f"{flat:.4f},{flng:.4f}"
        if cache_key in _GEOCODE_CACHE:
            return _GEOCODE_CACHE[cache_key]
            
        headers = {'User-Agent': 'ArgusAttendanceApp/2.1 (contact@argusattendance.com)'}
        
        # 1. OpenStreetMap Nominatim (Detailed address)
        import urllib.request
        import json
        try:
            nom_url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={flat}&lon={flng}&zoom=18&addressdetails=1"
            req = urllib.request.Request(nom_url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                display_name = data.get('display_name')
                if display_name and len(display_name.strip()) > 3:
                    resolved = display_name.strip()
                    _GEOCODE_CACHE[cache_key] = resolved
                    return resolved
        except Exception:
            pass

        # 2. BigDataCloud Fallback
        try:
            bdc_url = f"https://api.bigdatacloud.net/data/reverse-geocode-client?latitude={flat}&longitude={flng}&localityLanguage=en"
            req = urllib.request.Request(bdc_url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                parts = []
                for field in ['locality', 'city', 'principalSubdivision', 'postcode', 'countryName']:
                    v = (data.get(field) or '').strip()
                    if v and v not in parts:
                        parts.append(v)
                if parts:
                    resolved = ", ".join(parts)
                    _GEOCODE_CACHE[cache_key] = resolved
                    return resolved
        except Exception:
            pass

        # 3. Formatted GPS coordinates fallback
        coord_loc = f"GPS: {flat:.5f}, {flng:.5f}"
        _GEOCODE_CACHE[cache_key] = coord_loc
        return coord_loc
    except Exception:
        return None

def calculate_realistic_proximity(user_lat, user_lng, office_lat=OFFICE_LAT, office_lng=OFFICE_LNG):
    """Calculate distance in meters between user GPS coordinates and target office coordinates using precise Haversine formula."""
    if user_lat is None or user_lng is None:
        return 0.0
    try:
        ulat = parse_coordinate_to_float(user_lat, None)
        ulng = parse_coordinate_to_float(user_lng, None)
        olat = parse_coordinate_to_float(office_lat, OFFICE_LAT)
        olng = parse_coordinate_to_float(office_lng, OFFICE_LNG)
        if ulat is None or ulng is None or olat is None or olng is None:
            return 0.0
        d = calculate_distance_meters(ulat, ulng, olat, olng)
        return round(max(0.0, d), 1)
    except Exception:
        return 0.0

def add_live_entry(employee_id, employee_name, entry_time=None, site_name='OFFICE', entry_location=None, entry_distance=0.0, is_timeout=0, user_lat=None, user_lng=None, company_id='ARGUS_MASTER', target_lat=None, target_lng=None, live_address=None, branch_id=None, branch_name=None):
    db = get_db()
    if not entry_time:
        entry_time = get_ist_now().strftime('%d/%m/%Y %I:%M:%S %p')
        
    resolved_location = entry_location or live_address
    if not resolved_location and user_lat is not None and user_lng is not None:
        resolved_location = reverse_geocode_coordinates(user_lat, user_lng)
    if not resolved_location:
        resolved_location = get_company_full_address(company_id)
        
    calculated_meters = float(entry_distance or 0.0)
    if calculated_meters > 0.0:
        pass
    elif user_lat is not None and user_lng is not None:
        try:
            calculated_meters = calculate_realistic_proximity(user_lat, user_lng, office_lat=target_lat, office_lng=target_lng)
        except Exception:
            calculated_meters = 0.0
    elif calculated_meters == 0.0:
        calculated_meters = calculate_realistic_proximity(None, None, office_lat=target_lat, office_lng=target_lng)
            
    doc = {
        'company_id': str(company_id or 'ARGUS_MASTER'),
        'branch_id': str(branch_id) if branch_id else None,
        'branch_name': str(branch_name) if branch_name else None,
        'employee_id': str(employee_id),
        'employee_name': employee_name,
        'entry_time': entry_time,
        'site_name': site_name,
        'entry_location': resolved_location,
        'entry_distance': round(calculated_meters, 2),
        'formatted_distance': format_office_distance(calculated_meters),
        'user_lat': user_lat,
        'user_lng': user_lng,
        'is_timeout': int(is_timeout),
        'created_at': get_ist_now().isoformat()
    }
    result = db.live_entries.insert_one(doc)
    invalidate_dashboard_cache(doc.get('company_id'))
    return str(result.inserted_id)

def record_face_attendance(employee_id, employee_name, user_lat=None, user_lng=None, company_id=None, client_time=None, live_address=None, branch_id=None):
    """
    Punch In / Punch Out Attendance Lifecycle Engine with Multi-Tenant Geolocation Support:
    1. Records Live Entry in db.live_entries with real-time location address and company_id in 12-hour format (IST).
    2. Resolves company office coordinates and calculates proximity distance.
    3. Handles Punch In & Punch Out lifecycle storing the exact live location address where punched.
    """
    if user_lat is not None and str(user_lat).strip().lower() in ['undefined', 'null', '', 'none']:
        user_lat = None
    if user_lng is not None and str(user_lng).strip().lower() in ['undefined', 'null', '', 'none']:
        user_lng = None

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
    
    # Determine office coordinates and full address for this company
    target_lat = OFFICE_LAT
    target_lng = OFFICE_LNG
    loc_str = get_company_full_address(comp_id)
    company_geofence_radius = GEOFENCE_RADIUS_METERS
    if comp_id != 'ARGUS_MASTER':
        comp = db.company_admin.find_one({'id': comp_id})
        if comp:
            target_lat = parse_coordinate_to_float(comp.get('latitude'), OFFICE_LAT)
            target_lng = parse_coordinate_to_float(comp.get('longitude'), OFFICE_LNG)
            if comp.get('address'):
                loc_str = comp.get('address')
            company_geofence_radius = float(comp.get('geofence_radius') or comp.get('radius_meters') or GEOFENCE_RADIUS_METERS)
    else:
        comp = db.company_admin.find_one({'id': 'ARGUS_MASTER'})
        if comp:
            target_lat = parse_coordinate_to_float(comp.get('latitude'), OFFICE_LAT)
            target_lng = parse_coordinate_to_float(comp.get('longitude'), OFFICE_LNG)
            if comp.get('address'):
                loc_str = comp.get('address')
            company_geofence_radius = float(comp.get('geofence_radius') or comp.get('radius_meters') or GEOFENCE_RADIUS_METERS)

    # Branch-specific geofencing and tagging override
    active_branch_id = str(branch_id).strip() if branch_id and str(branch_id).strip() not in ['None', 'null', '', 'ALL'] else (emp.get('branch_id') if emp else None)
    active_branch_name = None
    if active_branch_id:
        branch = db.company_branches.find_one({'id': str(active_branch_id)})
        if branch:
            active_branch_name = branch.get('branch_name')
            if branch.get('latitude') is not None and branch.get('longitude') is not None:
                target_lat = parse_coordinate_to_float(branch.get('latitude'), target_lat)
                target_lng = parse_coordinate_to_float(branch.get('longitude'), target_lng)
            if branch.get('address'):
                loc_str = branch.get('address')
            if branch.get('geofence_radius'):
                company_geofence_radius = float(branch.get('geofence_radius'))
            
    # Calculate proximity distance
    dist_meters = calculate_realistic_proximity(user_lat, user_lng, target_lat, target_lng)
    formatted_dist = format_office_distance(dist_meters)

    # Resolve exact real-time live location address where employee punched
    live_loc_str = (live_address.strip() if live_address and str(live_address).strip() else None)
    if not live_loc_str and user_lat is not None and user_lng is not None:
        try:
            live_loc_str = reverse_geocode_coordinates(user_lat, user_lng)
        except Exception:
            live_loc_str = None
    if not live_loc_str:
        live_loc_str = loc_str
    
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
        # PUNCH IN:
        # Create active Live Entry (Currently working) with exact real-time live location
        live_id = add_live_entry(
            employee_id=employee_id,
            employee_name=employee_name,
            entry_time=now_time_12,
            site_name='OFFICE',
            entry_location=live_loc_str,
            entry_distance=dist_meters,
            is_timeout=0,
            user_lat=user_lat,
            user_lng=user_lng,
            company_id=comp_id,
            live_address=live_loc_str,
            branch_id=active_branch_id,
            branch_name=active_branch_name
        )

        # Geofencing threshold: Dynamic per company (defaults to 200m)
        punch_in_entry_type = 'proper' if dist_meters <= company_geofence_radius else 'improper'
        rep_doc = {
            'company_id': comp_id,
            'branch_id': active_branch_id,
            'branch_name': active_branch_name,
            'employee_id': str(employee_id),
            'employee_name': employee_name,
            'date': today_date,
            'entry_time': now_time_12,
            'entry_distance': formatted_dist,
            'entry_location': live_loc_str,
            'entry_lat': user_lat,
            'entry_lng': user_lng,
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
        return {'status': 'punch_in', 'live_id': live_id, 'formatted_dist': formatted_dist, 'live_location': live_loc_str}
        
    else:
        # PUNCH OUT: Update existing attendance report
        entry_time_str = existing_rep.get('entry_time', '')
        
        # Calculate working duration
        working_minutes = 0
        diff_sec = 28800
        try:
            # Parse entry time e.g. "26/09/2026 09:00:00 AM" or "26/09/2026 09:00:00"
            clean_time_str = entry_time_str.strip()
            entry_dt = None
            for fmt in [
                '%d/%m/%Y %I:%M:%S %p',
                '%d/%m/%Y %I:%M %p',
                '%d/%m/%Y %H:%M:%S',
                '%d/%m/%Y %H:%M',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%d %I:%M:%S %p',
                '%d-%m-%Y %I:%M:%S %p',
                '%d-%m-%Y %H:%M:%S'
            ]:
                try:
                    entry_dt = datetime.strptime(clean_time_str, fmt)
                    break
                except Exception:
                    pass
            if not entry_dt and existing_rep.get('created_at'):
                try:
                    entry_dt = datetime.fromisoformat(existing_rep.get('created_at'))
                except Exception:
                    pass

            if entry_dt:
                if entry_dt.tzinfo is None:
                    entry_dt = entry_dt.replace(tzinfo=IST)
                diff_sec = max(0, (now - entry_dt).total_seconds())
                working_minutes = int(diff_sec // 60)
            else:
                working_minutes = 0
                diff_sec = 0
        except Exception:
            working_minutes = 0
            diff_sec = 0

        # Minimum interval guard: Reject accidental rapid Punch Out within 120 seconds (2 minutes) of Punch In
        MIN_PUNCH_OUT_INTERVAL_SECONDS = 120
        if entry_dt and diff_sec < MIN_PUNCH_OUT_INTERVAL_SECONDS:
            remaining_cooldown = max(1, int(MIN_PUNCH_OUT_INTERVAL_SECONDS - diff_sec))
            return {
                'status': 'already_punched_in',
                'already_punched_in': True,
                'message': f"Punch In already recorded ({entry_time_str}). Please wait {remaining_cooldown}s before punching out.",
                'cooldown_remaining': remaining_cooldown,
                'entry_time': entry_time_str,
                'formatted_dist': formatted_dist,
                'live_location': live_loc_str,
                'working_hours': '00:00'
            }

        w_hrs = working_minutes // 60
        w_mins = working_minutes % 60
        working_hours_str = f"{w_hrs:02d}:{w_mins:02d}"
        
        # Calculate Shift Variance
        shift_target_minutes = parse_shift_hours_to_minutes(shift_hours_str, default_minutes=480)
        if shift_target_minutes == 0:
            shift_variance_str = "00:00"
        else:
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

        if shift_target_minutes == 0 or salary_type == 'hourly':
            computed_salary = round((working_minutes / 60.0) * hourly_rate, 2)
            if shift_target_minutes == 0:
                day_credit_type = 'Hourly' if working_minutes > 0 else 'Pending'
            elif working_minutes >= shift_target_minutes:
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
            computed_salary = round((working_minutes / 60.0) * hourly_rate, 2)
            
        # Determine final entry_type: Proper only if BOTH punch-in and punch-out are within company_geofence_radius
        in_entry_type = existing_rep.get('entry_type', 'proper')
        out_is_proper = (dist_meters <= company_geofence_radius)
        final_entry_type = 'proper' if (in_entry_type == 'proper' and out_is_proper) else 'improper'

        upd_data = {
            'exit_time': now_time_12,
            'exit_distance': formatted_dist,
            'exit_location': live_loc_str,
            'exit_lat': user_lat,
            'exit_lng': user_lng,
            'working_hours': working_hours_str,
            'shift_variance': shift_variance_str,
            'salary_type': salary_type,
            'day_credit_type': day_credit_type,
            'working_salary': computed_salary,
            'entry_type': final_entry_type,
            'updated_at': now.isoformat()
        }
        if active_branch_id:
            upd_data['branch_id'] = str(active_branch_id)
            upd_data['branch_name'] = str(active_branch_name or '')
        db.attendance_reports.update_one({'_id': existing_rep['_id']}, {'$set': upd_data})
        
        # PUNCH OUT:
        # 1. Fetch employee's active live entry if present
        active_live = db.live_entries.find_one({
            'employee_name': employee_name,
            'company_id': comp_id
        }, sort=[('created_at', DESCENDING)])
        
        entry_time_val = active_live.get('entry_time', entry_time_str) if active_live else entry_time_str
        entry_loc_val = active_live.get('entry_location', existing_rep.get('entry_location', live_loc_str)) if active_live else existing_rep.get('entry_location', live_loc_str)
        entry_dist_val = active_live.get('entry_distance', existing_rep.get('entry_distance', dist_meters)) if active_live else existing_rep.get('entry_distance', dist_meters)

        # 2. Store in timeout_entries
        timeout_doc = {
            'company_id': comp_id,
            'employee_id': str(employee_id),
            'employee_name': employee_name,
            'entry_time': entry_time_val,
            'exit_time': now_time_12,
            'working_hours': working_hours_str,
            'site_name': 'OFFICE (PUNCH OUT)',
            'entry_location': entry_loc_val,
            'exit_location': live_loc_str,
            'entry_distance': entry_dist_val,
            'exit_distance': formatted_dist,
            'formatted_distance': formatted_dist,
            'entry_lat': existing_rep.get('entry_lat'),
            'entry_lng': existing_rep.get('entry_lng'),
            'exit_lat': user_lat,
            'exit_lng': user_lng,
            'is_timeout': 1,
            'created_at': now.isoformat()
        }
        timeout_res = db.timeout_entries.insert_one(timeout_doc)
        timeout_id = str(timeout_res.inserted_id)

        # 3. REMOVE from live_entries (punched-out employee is no longer currently working)
        db.live_entries.delete_many({
            'employee_name': employee_name,
            'company_id': comp_id
        })

        # Update db.attendance
        db.attendance.update_one(
            {'company_id': comp_id, 'employee_name': employee_name, 'date': today_date},
            {'$set': {'company_id': comp_id, 'working_hours': working_hours_str, 'status': 'Present', 'updated_at': now}},
            upsert=True
        )
        invalidate_dashboard_cache(comp_id)
        return {'status': 'punch_out', 'live_id': timeout_id, 'formatted_dist': formatted_dist, 'working_hours': working_hours_str, 'live_location': live_loc_str}

# ----------------- ATTENDANCE REPORTS ----------------- #

def compute_entry_exit_status(entry_time_str, exit_time_str, shift_start='09:00 AM', shift_end='06:00 PM', is_manual=False, shift_mins=480):
    """
    Computes precise ENTRY STATUS and EXIT STATUS strings:
    - If manual entry: returns ('-', '-')
    - If shift_mins == 0 (flex-time / 0 shift hours): returns ('On Time', 'On Time') when punched in/out
    - Entry Status: 'Late by X minutes', 'Late by X hr Y mins', 'Early by X minutes', or 'On Time'
    - Exit Status: 'Early by X minutes', 'Early by X hr Y mins', 'Overtime by X minutes', 'On Time', or '-' (if working/pending)
    """
    if is_manual:
        return '-', '-'

    def parse_time_to_minutes(t_str):
        if not t_str or str(t_str).strip() in ['----', '-', '']:
            return None
        match = re.search(r'(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?', str(t_str), re.I)
        if not match:
            return None
        h = int(match.group(1))
        m = int(match.group(2))
        ampm = match.group(3).upper() if match.group(3) else None
        if ampm == 'PM' and h < 12:
            h += 12
        elif ampm == 'AM' and h == 12:
            h = 0
        return h * 60 + m

    entry_mins = parse_time_to_minutes(entry_time_str)
    exit_mins = parse_time_to_minutes(exit_time_str)

    if shift_mins == 0:
        entry_status = "On Time" if entry_mins is not None else "-"
        exit_status = "On Time" if exit_mins is not None else "-"
        return entry_status, exit_status

    start_mins = parse_time_to_minutes(shift_start)
    if start_mins is None:
        start_mins = 540  # Default 09:00 AM

    if entry_mins is None:
        entry_status = '-'
    else:
        diff_in = entry_mins - start_mins
        if diff_in > 5:  # Grace of 5 mins
            if diff_in >= 60:
                dh = diff_in // 60
                dm = diff_in % 60
                entry_status = f"Late by {dh} hr {dm} mins" if dm > 0 else f"Late by {dh} hr"
            else:
                entry_status = f"Late by {diff_in} minutes"
        elif diff_in < -5:
            early_m = abs(diff_in)
            if early_m >= 60:
                dh = early_m // 60
                dm = early_m % 60
                entry_status = f"Early by {dh} hr {dm} mins" if dm > 0 else f"Early by {dh} hr"
            else:
                entry_status = f"Early by {early_m} minutes"
        else:
            entry_status = "On Time"

    end_mins = parse_time_to_minutes(shift_end)
    if end_mins is None:
        end_mins = 1080  # Default 06:00 PM

    if exit_mins is None:
        exit_status = '-'
    else:
        diff_out = exit_mins - end_mins
        if diff_out < -5:
            early_m = abs(diff_out)
            if early_m >= 60:
                dh = early_m // 60
                dm = early_m % 60
                exit_status = f"Early by {dh} hr {dm} mins" if dm > 0 else f"Early by {dh} hr"
            else:
                exit_status = f"Early by {early_m} minutes"
        elif diff_out > 5:
            ot_m = diff_out
            if ot_m >= 60:
                dh = ot_m // 60
                dm = ot_m % 60
                exit_status = f"Overtime by {dh} hr {dm} mins" if dm > 0 else f"Overtime by {dh} hr"
            else:
                exit_status = f"Overtime by {ot_m} minutes"
        else:
            exit_status = "On Time"

    return entry_status, exit_status

def extract_sort_timestamp(row):
    if not row:
        return '1970-01-01 00:00:00'
    for val in [row.get('entry_time'), row.get('submitted_at'), row.get('created_at'), row.get('date'), row.get('entry_date')]:
        if not val:
            continue
        if isinstance(val, datetime):
            return val.strftime('%Y-%m-%d %H:%M:%S')
        s = str(val).strip()
        # DD/MM/YYYY or DD-MM-YYYY with time (e.g. 02/10/2026 02:33:07 PM or 02-10-2026 04:47:33 PM)
        m_dmy = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)?)?', s, re.I)
        if m_dmy:
            day, month, year = int(m_dmy.group(1)), int(m_dmy.group(2)), int(m_dmy.group(3))
            hour = int(m_dmy.group(4)) if m_dmy.group(4) else 0
            minute = int(m_dmy.group(5)) if m_dmy.group(5) else 0
            second = int(m_dmy.group(6)) if m_dmy.group(6) else 0
            ampm = (m_dmy.group(7) or '').upper()
            if ampm == 'PM' and hour < 12:
                hour += 12
            elif ampm == 'AM' and hour == 12:
                hour = 0
            return f'{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}'
            
        # ISO format: 2026-10-02T14:33:09... or 2026-10-02 14:33:09
        m_iso = re.match(r'^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})', s)
        if m_iso:
            return f'{m_iso.group(1)}-{m_iso.group(2)}-{m_iso.group(3)} {m_iso.group(4)}:{m_iso.group(5)}:{m_iso.group(6)}'
            
        # YYYY-MM-DD
        m_date = re.match(r'^(\d{4})-(\d{2})-(\d{2})', s)
        if m_date:
            return f'{m_date.group(1)}-{m_date.group(2)}-{m_date.group(3)} 00:00:00'
            
    return '1970-01-01 00:00:00'

def get_attendance_reports(report_type='all', start_date=None, end_date=None, employee='All', search=None, page=1, limit=10, company_id=None, branch_id=None):
    db = get_db()

    if not start_date and not end_date:
        def_start, _, _, _ = get_default_two_month_range()
        start_date = def_start

    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    b_names = set()
    branch_cond = None
    if b_id:
        b_names, _ = get_cached_branch_names_and_ids(b_id, company_id)
        branch_cond = get_branch_record_condition(b_id, b_names)

    # Pre-load employee shift hours for dynamic status computation
    emp_shifts = {}
    emp_q = get_branch_employee_query(b_id, company_id)
    for emp_d in db.employees.find(emp_q, {'employee_name': 1, 'shift_start': 1, 'shift_end': 1, 'shift_hours': 1}):
        if emp_d.get('employee_name'):
            emp_shifts[emp_d['employee_name']] = {
                'start': emp_d.get('shift_start', '09:00 AM') or '09:00 AM',
                'end': emp_d.get('shift_end', '06:00 PM') or '06:00 PM',
                'shift_mins': parse_shift_hours_to_minutes(emp_d.get('shift_hours', '08:00'), default_minutes=480)
            }

    if report_type == 'manual':
        m_query = {}
        if company_id and company_id != 'ALL':
            m_query['company_id'] = str(company_id)
        if branch_cond:
            m_query.setdefault('$and', []).append(branch_cond)
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
            m_status = c.get('status', 'Proper')
            m_reason = (c.get('reason') or '').strip()
            status_reason_str = f"{m_status} - {m_reason}" if m_reason else m_status
            data.append({
                'id': c.get('id'),
                'company_id': c.get('company_id'),
                'employee_name': c.get('employee_name', ''),
                'entry_time': c.get('submitted_at') or c.get('entry_date', ''),
                'entry_distance': 'MANUAL ENTRY',
                'entry_location': f"Manual Adjustment ({status_reason_str})",
                'entry_status': '-',
                'exit_time': '----',
                'exit_distance': '----',
                'exit_location': '----',
                'exit_status': '-',
                'working_hours': c.get('hours', '00:00'),
                'shift_variance': '----',
                'working_salary': float(c.get('working_salary', 0)),
                'entry_type': 'manual',
                'is_manual': True
            })
        return {
            'total': total,
            'page': page,
            'limit': limit,
            'data': data
        }

    # Biometric Attendance Reports Query
    query = {}
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
    if branch_cond:
        query.setdefault('$and', []).append(branch_cond)
        
    if report_type == 'proper':
        query['entry_type'] = {'$ne': 'improper'}
    elif report_type == 'improper':
        query['entry_type'] = 'improper'
        
    if employee and employee != 'All':
        query['employee_name'] = employee
        
    if start_date:
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

    # For Proper and Improper reports: query attendance_reports collection
    if report_type in ['proper', 'improper']:
        total = db.attendance_reports.count_documents(query)
        cursor = db.attendance_reports.find(query).sort([("date", DESCENDING), ("created_at", DESCENDING), ("_id", DESCENDING)])
        if limit and limit > 0:
            cursor = cursor.skip((page - 1) * limit).limit(limit)
            
        data = []
        for doc in cursor:
            c = clean_doc(doc)
            cid = c.get('company_id') or company_id
            full_addr = get_company_full_address(cid)
            if not c.get('entry_location') or str(c.get('entry_location')).strip() in ['OFFICE', '----', '']:
                if c.get('entry_lat') and c.get('entry_lng'):
                    c['entry_location'] = reverse_geocode_coordinates(c['entry_lat'], c['entry_lng']) or full_addr
                else:
                    c['entry_location'] = full_addr

            if c.get('exit_location') and str(c.get('exit_location')).strip() not in ['----', '-', '']:
                if str(c.get('exit_location')).strip() == 'OFFICE':
                    if c.get('exit_lat') and c.get('exit_lng'):
                        c['exit_location'] = reverse_geocode_coordinates(c['exit_lat'], c['exit_lng']) or full_addr
                    else:
                        c['exit_location'] = full_addr

            s_cfg = emp_shifts.get(c.get('employee_name', ''), {'start': '09:00 AM', 'end': '06:00 PM', 'shift_mins': 480})
            s_mins = s_cfg.get('shift_mins', 480)
            is_auto_timeout = bool(c.get('is_timeout') or 'AUTO TIMEOUT' in str(c.get('exit_distance', '')).upper() or 'AUTO PUNCH-OUT' in str(c.get('exit_location', '')).upper())
            if s_mins == 0 and (is_auto_timeout or str(c.get('exit_time') or '').strip() in ['----', '-', '']):
                c['working_hours'] = '00:00'
                c['working_salary'] = 0.0
                c['shift_variance'] = '----'
            e_status, x_status = compute_entry_exit_status(c.get('entry_time'), c.get('exit_time'), s_cfg['start'], s_cfg['end'], is_manual=False, shift_mins=s_mins)
            c['entry_status'] = e_status
            if is_auto_timeout:
                c['exit_status'] = 'Auto Timeout'
            else:
                c['exit_status'] = x_status
            data.append(c)
        return {
            'total': total,
            'page': page,
            'limit': limit,
            'data': data
        }

    # For 'all' report_type: merge attendance_reports AND manual_entries
    combined = []
    
    for doc in db.attendance_reports.find(query):
        c = clean_doc(doc)
        cid = c.get('company_id') or company_id
        full_addr = get_company_full_address(cid)
        if not c.get('entry_location') or str(c.get('entry_location')).strip() in ['OFFICE', '----', '']:
            if c.get('entry_lat') and c.get('entry_lng'):
                c['entry_location'] = reverse_geocode_coordinates(c['entry_lat'], c['entry_lng']) or full_addr
            else:
                c['entry_location'] = full_addr

        if c.get('exit_location') and str(c.get('exit_location')).strip() not in ['----', '-', '']:
            if str(c.get('exit_location')).strip() == 'OFFICE':
                if c.get('exit_lat') and c.get('exit_lng'):
                    c['exit_location'] = reverse_geocode_coordinates(c['exit_lat'], c['exit_lng']) or full_addr
                else:
                    c['exit_location'] = full_addr

        s_cfg = emp_shifts.get(c.get('employee_name', ''), {'start': '09:00 AM', 'end': '06:00 PM', 'shift_mins': 480})
        s_mins = s_cfg.get('shift_mins', 480)
        is_auto_timeout = bool(c.get('is_timeout') or 'AUTO TIMEOUT' in str(c.get('exit_distance', '')).upper() or 'AUTO PUNCH-OUT' in str(c.get('exit_location', '')).upper())
        if s_mins == 0 and (is_auto_timeout or str(c.get('exit_time') or '').strip() in ['----', '-', '']):
            c['working_hours'] = '00:00'
            c['working_salary'] = 0.0
            c['shift_variance'] = '----'
        e_status, x_status = compute_entry_exit_status(c.get('entry_time'), c.get('exit_time'), s_cfg['start'], s_cfg['end'], is_manual=False, shift_mins=s_mins)
        c['entry_status'] = e_status
        if is_auto_timeout:
            c['exit_status'] = 'Auto Timeout'
        else:
            c['exit_status'] = x_status
        c['is_manual'] = False
        c['sort_key'] = str(c.get('date') or c.get('created_at') or c.get('entry_time') or '')
        combined.append(c)

    # Manual entries query matching same filters
    m_query = {}
    if company_id and company_id != 'ALL':
        m_query['company_id'] = str(company_id)
    if branch_cond:
        m_query.setdefault('$and', []).append(branch_cond)
    if employee and employee != 'All':
        m_query['employee_name'] = employee
    if start_date:
        m_query.setdefault('entry_date', {})['$gte'] = start_date.strip()
    if end_date:
        m_query.setdefault('entry_date', {})['$lte'] = end_date.strip()
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        m_query['$or'] = [{'employee_name': reg}, {'entry_date': reg}, {'status': reg}]

    for doc in db.manual_entries.find(m_query):
        c = clean_doc(doc)
        m_status = c.get('status', 'Proper')
        m_reason = (c.get('reason') or '').strip()
        status_reason_str = f"{m_status} - {m_reason}" if m_reason else m_status
        combined.append({
            'id': c.get('id'),
            'company_id': c.get('company_id'),
            'employee_name': c.get('employee_name', ''),
            'entry_time': c.get('submitted_at') or c.get('entry_date', ''),
            'entry_distance': 'MANUAL ENTRY',
            'entry_location': f"Manual Adjustment ({status_reason_str})",
            'entry_status': '-',
            'exit_time': '----',
            'exit_distance': '----',
            'exit_location': '----',
            'exit_status': '-',
            'working_hours': c.get('hours', '00:00'),
            'shift_variance': '----',
            'working_salary': float(c.get('working_salary', 0.0)),
            'entry_type': 'manual',
            'is_manual': True,
            'sort_key': str(c.get('entry_date') or c.get('created_at') or c.get('submitted_at') or '')
        })

    # Include approved leaves in 'all' reports
    l_query = {'request_type': 'Leave', 'status': 'Approved'}
    if company_id and company_id != 'ALL':
        l_query['company_id'] = str(company_id)
    if b_id:
        l_query['employee_name'] = {'$in': list(b_names)} if b_names else {'$in': []}
    if employee and employee != 'All':
        l_query['employee_name'] = employee
    if start_date:
        l_query['to_date'] = {'$gte': start_date.strip()}
    if end_date:
        l_query.setdefault('from_date', {})['$lte'] = end_date.strip()
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        l_query['$or'] = [{'employee_name': reg}, {'leave_type': reg}, {'reason': reg}]

    for doc in db.leave_requests.find(l_query):
        c = clean_doc(doc)
        l_type = c.get('leave_type', 'Casual Leave (CL)')
        l_reason = (c.get('reason') or '').strip()
        desc = f"Approved Leave ({l_type}) - {l_reason}" if l_reason else f"Approved Leave ({l_type})"
        combined.append({
            'id': c.get('id'),
            'company_id': c.get('company_id'),
            'employee_name': c.get('employee_name', ''),
            'entry_time': c.get('from_date', ''),
            'entry_distance': 'LEAVE',
            'entry_location': desc,
            'entry_status': 'Leave',
            'exit_time': '----',
            'exit_distance': '----',
            'exit_location': '----',
            'exit_status': '-',
            'working_hours': '00:00' if c.get('session') != 'Half Day' else '04:00',
            'shift_variance': '----',
            'working_salary': 0.0,
            'entry_type': 'leave',
            'is_manual': True,
            'sort_key': str(c.get('from_date') or c.get('created_at') or '')
        })

    # Sort descending by date/timestamp
    combined.sort(key=lambda x: (extract_sort_timestamp(x), str(x.get('created_at', '') or x.get('id', ''))), reverse=True)
    total = len(combined)

    if limit and limit > 0:
        p_data = combined[(page - 1) * limit : page * limit]
    else:
        p_data = combined

    return {
        'total': total,
        'page': page,
        'limit': limit,
        'data': p_data
    }

def get_attendance_simple_table(employee='All', start_date=None, end_date=None, company_id=None, branch_id=None):
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

    if not start_date and not end_date:
        def_start, _, _, _ = get_default_two_month_range()
        start_date = def_start

    s_iso = extract_iso_date(start_date) if start_date else ''
    e_iso = extract_iso_date(end_date) if end_date else ''

    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    branch_names = set()
    branch_cond = None
    if b_id:
        b_emp_q = get_branch_employee_query(b_id, company_id)
        b_emps = list(db.employees.find(b_emp_q, {'employee_name': 1}))
        branch_names = set(e.get('employee_name') for e in b_emps if e.get('employee_name'))
        branch_cond = get_branch_record_condition(b_id, branch_names)

    # Pre-fetch employees in company for rate configurations
    emp_filter = get_branch_employee_query(b_id, company_id)
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

        shift_str = emp_info.get('shift_hours', '08:00')
        shift_mins = parse_shift_hours_to_minutes(shift_str, default_minutes=480)
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

        if shift_mins == 0 or stype == 'hourly':
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
    if branch_cond:
        rep_query.setdefault('$and', []).append(branch_cond)
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

        emp_info = emp_map.get(emp_name)
        emp_shift_mins = parse_shift_hours_to_minutes(emp_info.get('shift_hours', '08:00') if emp_info else '08:00', default_minutes=480)
        is_auto_timeout = bool(r.get('is_timeout') or 'AUTO TIMEOUT' in str(r.get('exit_distance', '')).upper() or 'AUTO PUNCH-OUT' in str(r.get('exit_location', '')).upper())
        is_incomplete = (str(exit_t).strip() in ['----', '-', ''])

        if is_improper:
            w_sal = 0.0
            status_label = 'Improper'
        elif is_incomplete or (emp_shift_mins == 0 and is_auto_timeout):
            wh = '00:00'
            sv = '----'
            w_sal = 0.0
            status_label = r.get('status') or 'Proper'
        else:
            raw_sal = r.get('working_salary')
            if raw_sal is not None and float(raw_sal) > 0:
                w_sal = float(raw_sal)
            else:
                w_sal = calc_salary(emp_name, wh)
            status_label = r.get('status') or 'Proper'

        data.append({
            'id': r.get('id'),
            'company_id': r.get('company_id'),
            'employee_name': emp_name,
            'entry_time': entry_t,
            'exit_time': exit_t,
            'working_hours': wh,
            'shift_variance': sv,
            'working_salary': round(w_sal, 2),
            'status': status_label,
            'sort_key': rec_date or entry_t,
            'is_improper': is_improper,
            'source': 'punch',
            'is_manual': False
        })

    # 2. Fetch Manual Entries (manual_entries)
    m_query = {}
    if company_id and company_id != 'ALL':
        m_query['company_id'] = str(company_id)
    if branch_cond:
        m_query.setdefault('$and', []).append(branch_cond)
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
            is_sub = (str(m.get('entry_type', '')).strip().lower() == 'sub')
            if raw_sal is not None:
                try:
                    w_sal = float(raw_sal)
                    if is_sub and w_sal > 0:
                        w_sal = -w_sal
                except (ValueError, TypeError):
                    w_sal = calc_salary(emp_name, wh)
                    if is_sub:
                        w_sal = -abs(w_sal)
            else:
                w_sal = calc_salary(emp_name, wh)
                if is_sub:
                    w_sal = -abs(w_sal)
            status_label = 'Manual' if raw_status in ['Proper', 'Full Day', 'Half Day', 'Manual', 'Others', 'Permission'] else raw_status

        data.append({
            'id': m.get('id'),
            'company_id': m.get('company_id'),
            'employee_name': emp_name,
            'entry_time': entry_t,
            'exit_time': '',
            'working_hours': wh,
            'shift_variance': '',
            'working_salary': round(w_sal, 2),
            'status': status_label,
            'sort_key': rec_date or entry_t,
            'is_improper': is_improper,
            'source': 'manual',
            'is_manual': True
        })

    # Sort descending by normalized datetime
    data.sort(key=lambda x: (extract_sort_timestamp(x), str(x.get('created_at', '') or x.get('id', ''))), reverse=True)

    # Compute Totals
    total_minutes = 0
    total_salary = 0.0

    for r in data:
        wh = r.get('working_hours', '00:00')
        parts = str(wh).replace('-', '').split(':')
        is_sub = (float(r.get('working_salary', 0.0)) < 0) or (r.get('source') == 'manual' and str(r.get('entry_type', '')).lower() == 'sub')
        if len(parts) >= 2:
            try:
                mins = int(parts[0]) * 60 + int(parts[1])
                total_minutes += (-mins if is_sub else mins)
            except ValueError:
                pass
        if not r.get('is_improper'):
            total_salary += float(r.get('working_salary', 0.0))

    neg = total_minutes < 0
    abs_mins = abs(total_minutes)
    tot_h = abs_mins // 60
    tot_m = abs_mins % 60
    formatted_total_hours = f"{'-' if neg else ''}{tot_h:02d}:{tot_m:02d}"
    formatted_total_salary = f"{total_salary:.2f}"

    return {
        'data': data,
        'total_working_hours': formatted_total_hours,
        'total_working_salary': formatted_total_salary
    }

# ----------------- MANUAL ENTRIES ----------------- #

def get_manual_entries(from_date=None, to_date=None, status='All', search=None, page=1, limit=10, company_id=None, branch_id=None):
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)

    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if b_id:
        b_emp_q = get_branch_employee_query(b_id, company_id)
        b_emps = list(db.employees.find(b_emp_q, {'employee_name': 1}))
        b_names = set(e.get('employee_name') for e in b_emps if e.get('employee_name'))
        branch_cond = get_branch_record_condition(b_id, b_names)
        if branch_cond:
            query.setdefault('$and', []).append(branch_cond)
        
    if not from_date and not to_date:
        def_start, _, _, _ = get_default_two_month_range()
        from_date = def_start

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
            {'reason': reg},
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
    shift_target_minutes = parse_shift_hours_to_minutes(shift_hours_str, default_minutes=480)
    half_shift_target = max(1, shift_target_minutes // 2)

    working_salary = 0.0
    if mode == 'Salary':
        working_salary = float(data.get('working_salary') or 0.0)
    elif (mode == 'Full Day' or status == 'Full Day') and shift_target_minutes > 0:
        working_salary = day_rate if day_rate > 0 else (hourly_rate * (shift_target_minutes / 60.0))
    elif (mode == 'Half Day' or status == 'Half Day') and shift_target_minutes > 0:
        working_salary = half_rate if half_rate > 0 else (day_rate / 2.0 if day_rate > 0 else (hourly_rate * (half_shift_target / 60.0)))
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
        if shift_target_minutes == 0 or salary_type == 'hourly':
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
    
    reason = str(data.get('reason') or '').strip()
    assigned_branch_id = data.get('branch_id') or (emp.get('branch_id') if emp else None)
    doc = {
        'id': entry_id,
        'company_id': assigned_company_id,
        'employee_id': emp_id,
        'employee_name': emp_name,
        'entry_date': data.get('entry_date', ''),
        'hours': hours_str,
        'status': status,
        'reason': reason,
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
    if assigned_branch_id:
        doc['branch_id'] = str(assigned_branch_id)
    # Deduplication guard: check if identical manual entry was inserted within the last 5 seconds
    recent_entry = db.manual_entries.find_one({
        'company_id': assigned_company_id,
        'employee_name': emp_name,
        'entry_date': data.get('entry_date', ''),
        'hours': hours_str,
        'status': status,
        'id': {'$gt': entry_id - 5000}
    })
    if recent_entry:
        return recent_entry['id']

    db.manual_entries.insert_one(doc)
    invalidate_dashboard_cache(doc.get('company_id'))
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
    shift_target_minutes = parse_shift_hours_to_minutes(shift_hours_str, default_minutes=480)
    half_shift_target = max(1, shift_target_minutes // 2)

    hours_str = data.get('hours', '00:00')
    mode = data.get('mode', 'Hours')
    status = data.get('status', 'Proper')
    
    working_salary = 0.0
    if mode == 'Salary':
        working_salary = float(data.get('working_salary') or 0.0)
    elif (mode == 'Full Day' or status == 'Full Day') and shift_target_minutes > 0:
        working_salary = day_rate if day_rate > 0 else (hourly_rate * (shift_target_minutes / 60.0))
    elif (mode == 'Half Day' or status == 'Half Day') and shift_target_minutes > 0:
        working_salary = half_rate if half_rate > 0 else (day_rate / 2.0 if day_rate > 0 else (hourly_rate * (half_shift_target / 60.0)))
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
        if shift_target_minutes == 0 or salary_type == 'hourly':
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

    reason = str(data.get('reason') or '').strip()
    upd = {
        'employee_name': emp_name,
        'entry_date': data.get('entry_date', ''),
        'hours': hours_str,
        'status': status,
        'reason': reason,
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

def delete_attendance_report(report_id, is_manual=False, company_id=None):
    """
    Deletes an attendance report (facial punch or manual adjustment).
    Also purges corresponding live_entries, timeout_entries, and attendance documents.
    """
    db = get_db()
    id_filter = build_id_filter(report_id)
    
    deleted = False
    if is_manual:
        # Check manual_entries
        doc = db.manual_entries.find_one(id_filter)
        if doc:
            db.manual_entries.delete_one({'_id': doc['_id']})
            deleted = True
        else:
            # Fallback: check attendance_reports
            doc = db.attendance_reports.find_one(id_filter)
            if doc:
                db.attendance_reports.delete_one({'_id': doc['_id']})
                deleted = True
            else:
                res = db.manual_entries.delete_one(id_filter)
                deleted = (res.deleted_count > 0)
    else:
        # Check attendance_reports
        doc = db.attendance_reports.find_one(id_filter)
        if doc:
            emp_name = doc.get('employee_name')
            entry_t = doc.get('entry_time')
            cid = doc.get('company_id') or company_id
            
            db.attendance_reports.delete_one({'_id': doc['_id']})
            deleted = True
            
            # Clean up from live_entries and timeout_entries
            if emp_name and entry_t:
                db.live_entries.delete_many({'employee_name': emp_name, 'entry_time': entry_t})
                db.timeout_entries.delete_many({'employee_name': emp_name, 'entry_time': entry_t})
                
                # Also delete from attendance collection
                date_str = doc.get('date') or (str(entry_t)[:10] if entry_t else None)
                if date_str:
                    db.attendance.delete_many({
                        '$and': [
                            {'$or': [{'employee_name': emp_name}, {'name': emp_name}]},
                            {'$or': [
                                {'punch_time': entry_t},
                                {'timestamp': {'$regex': f"^{re.escape(str(date_str))}"}}
                            ]}
                        ]
                    })
        else:
            # Fallback: check manual_entries
            doc = db.manual_entries.find_one(id_filter)
            if doc:
                db.manual_entries.delete_one({'_id': doc['_id']})
                deleted = True
            else:
                res = db.attendance_reports.delete_one(id_filter)
                deleted = (res.deleted_count > 0)
                
    return deleted

# ----------------- PAYMENT MANAGEMENT ----------------- #

def get_payments(employee=None, start_date=None, end_date=None, bank=None, payment_type=None, status=None, reason=None, search=None, page=1, limit=10, company_id=None, branch_id=None):
    db = get_db()
    conditions = []
    
    if company_id and company_id != 'ALL':
        conditions.append({'company_id': str(company_id)})

    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if b_id:
        b_names, _ = get_cached_branch_names_and_ids(b_id, company_id)
        branch_cond = get_branch_record_condition(b_id, b_names)
        if branch_cond:
            conditions.append(branch_cond)
        
    if employee and employee != 'All':
        conditions.append({'employee_name': employee})
    if start_date:
        conditions.append({'payment_date': {'$gte': start_date}})
    if end_date:
        conditions.append({'payment_date': {'$lte': end_date}})
    if bank and bank != 'All':
        conditions.append({'bank': bank})
    if payment_type and payment_type != 'All':
        conditions.append({'payment_type': payment_type})
        
    filter_status = status if (status and status != 'All') else (reason if (reason and reason != 'All') else None)
    if filter_status:
        conditions.append({'$or': [{'status': filter_status}, {'reason': filter_status}]})
        
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        conditions.append({'$or': [
            {'employee_name': reg},
            {'bank': reg},
            {'payment_type': reg},
            {'status': reg},
            {'reason': reg},
            {'timestamp': reg},
            {'payment_date': reg}
        ]})
        
    query = {'$and': conditions} if conditions else {}
        
    total = db.payments.count_documents(query)
    cursor = db.payments.find(query).sort([("created_at", DESCENDING), ("id", DESCENDING), ("_id", DESCENDING), ("payment_date", DESCENDING)])
    if limit and limit > 0:
        cursor = cursor.skip((page - 1) * limit).limit(limit)
        
    data = []
    for doc in cursor:
        cdoc = clean_doc(doc)
        raw_status = cdoc.get('status')
        raw_reason = cdoc.get('reason')
        if not raw_status and raw_reason:
            cdoc['status'] = raw_reason
            cdoc['reason'] = ''
        elif not raw_status:
            cdoc['status'] = 'Advance Repayment'
            cdoc['reason'] = raw_reason or ''
        data.append(cdoc)
        
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
    if not doc:
        return None
    cdoc = clean_doc(doc)
    raw_status = cdoc.get('status')
    raw_reason = cdoc.get('reason')
    if not raw_status and raw_reason:
        cdoc['status'] = raw_reason
        cdoc['reason'] = ''
    elif not raw_status:
        cdoc['status'] = 'Advance Repayment'
        cdoc['reason'] = raw_reason or ''
    return cdoc

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
    
    status = data.get('status')
    reason = data.get('reason', '')
    if not status and reason:
        status = reason
        reason = ''
    elif not status:
        status = 'Advance Repayment'
        
    reason = (reason or '').strip()
    receipt_filename = data.get('receipt_filename', '')
    assigned_branch_id = data.get('branch_id') or (emp.get('branch_id') if emp else None)
    
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
        'status': status,
        'reason': reason,
        'receipt_filename': receipt_filename,
        'created_at': datetime.now()
    }
    if assigned_branch_id:
        doc['branch_id'] = str(assigned_branch_id)
    # Deduplication guard: check if identical payment was recorded within the last 5 seconds
    now_ms = int(time.time() * 1000)
    recent_payment = db.payments.find_one({
        'company_id': assigned_company_id,
        'employee_name': emp_name,
        'payment_date': payment_date,
        'amount': amount,
        'id': {'$gt': now_ms - 5000}
    })
    if recent_payment:
        return str(recent_payment['id'])

    res = db.payments.insert_one(doc)
    return str(doc['id'])

def update_payment(payment_id, data):
    db = get_db()
    emp_name = data.get('employee_name', '')
    status = data.get('status')
    reason = data.get('reason', '')
    if not status and reason:
        status = reason
        reason = ''
    elif not status:
        status = 'Advance Repayment'
        
    reason = (reason or '').strip()
    upd = {
        'employee_name': emp_name,
        'payment_date': data.get('payment_date'),
        'amount': float(data.get('amount') or 0.0),
        'bank': data.get('bank', '').strip(),
        'payment_type': data.get('payment_type', 'UPI'),
        'status': status,
        'reason': reason
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

def get_advances(employee=None, start_date=None, end_date=None, search=None, page=1, limit=10, company_id=None, branch_id=None):
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)

    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if b_id:
        b_names, _ = get_cached_branch_names_and_ids(b_id, company_id)
        branch_cond = get_branch_record_condition(b_id, b_names)
        if branch_cond:
            query.setdefault('$and', []).append(branch_cond)
        
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
    assigned_branch_id = data.get('branch_id') or (emp.get('branch_id') if emp else None)
    
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
    if assigned_branch_id:
        doc['branch_id'] = str(assigned_branch_id)
    # Deduplication guard: check if identical advance was recorded within the last 5 seconds
    now_ms = int(time.time() * 1000)
    recent_advance = db.advances.find_one({
        'company_id': assigned_company_id,
        'employee_name': emp_name,
        'advance_date': advance_date,
        'amount': amount,
        'id': {'$gt': now_ms - 5000}
    })
    if recent_advance:
        return str(recent_advance['id'])

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

def get_balance_report(employee=None, search=None, page=1, limit=10, company_id=None, branch_id=None):
    db = get_db()
    
    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    branch_cond = None
    if b_id:
        b_emp_q = get_branch_employee_query(b_id, company_id)
        b_emps = list(db.employees.find(b_emp_q, {'employee_name': 1}))
        b_names = set(e.get('employee_name') for e in b_emps if e.get('employee_name'))
        branch_cond = get_branch_record_condition(b_id, b_names)

    # Query all advances
    adv_query = {}
    if company_id and company_id != 'ALL':
        adv_query['company_id'] = str(company_id)
    if branch_cond:
        adv_query.setdefault('$and', []).append(branch_cond)
    if employee and employee != 'All':
        adv_query['employee_name'] = employee
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        adv_query['$or'] = [{'employee_name': reg}, {'timestamp': reg}, {'advance_date': reg}]
        
    adv_cursor = list(db.advances.find(adv_query))
    
    # Query all advance repayments
    rep_conditions = [{'$or': [{'status': 'Advance Repayment'}, {'reason': 'Advance Repayment'}]}]
    if company_id and company_id != 'ALL':
        rep_conditions.append({'company_id': str(company_id)})
    if branch_cond:
        rep_conditions.append(branch_cond)
    if employee and employee != 'All':
        rep_conditions.append({'employee_name': employee})
    if search:
        reg = {'$regex': re.escape(search), '$options': 'i'}
        rep_conditions.append({'$or': [{'employee_name': reg}, {'timestamp': reg}, {'payment_date': reg}]})
        
    rep_query = {'$and': rep_conditions}
    rep_cursor = list(db.payments.find(rep_query))
    
    raw_items = []
    total_advance = 0.0
    total_repayment = 0.0
    
    for a in adv_cursor:
        amt = float(a.get('amount', 0.0))
        total_advance += amt
        raw_items.append({
            'type': 'advance',
            'timestamp': a.get('timestamp') or a.get('created_at', ''),
            'name': a.get('employee_name', ''),
            'date': a.get('advance_date', ''),
            'advance_amount': amt,
            'payment_amount': 0.0,
            'advance_repayment_amount': 0.0,
            'created_at': str(a.get('created_at') or a.get('advance_date') or a.get('timestamp') or '')
        })
        
    for p in rep_cursor:
        amt = float(p.get('amount', 0.0))
        total_repayment += amt
        raw_items.append({
            'type': 'repayment',
            'timestamp': p.get('timestamp') or p.get('created_at', ''),
            'name': p.get('employee_name', ''),
            'date': p.get('payment_date', ''),
            'advance_amount': 0.0,
            'payment_amount': amt,
            'advance_repayment_amount': amt,
            'created_at': str(p.get('created_at') or p.get('payment_date') or p.get('timestamp') or '')
        })
        
    # Group by employee to calculate accurate chronological running balance per employee
    from collections import defaultdict
    by_emp = defaultdict(list)
    for it in raw_items:
        by_emp[it['name']].append(it)

    combined = []
    for emp_name, entries in by_emp.items():
        # Sort chronologically (oldest to newest) to calculate cumulative running balance
        entries.sort(key=lambda x: (x.get('date', '') or '', x.get('timestamp', '') or '', x.get('created_at', '')))
        running_bal = 0.0
        for e in entries:
            running_bal += e['advance_amount'] - e['payment_amount']
            e['balance_amount'] = round(running_bal, 2)
        combined.extend(entries)

    # Sort combined for display: chronological order matching Image 1
    combined.sort(key=lambda x: (x.get('date', '') or '', x.get('timestamp', '') or '', x.get('created_at', '')))
    total = len(combined)
    balance_amount = round(total_advance - total_repayment, 2)
    
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
        'total_advance': round(total_advance, 2),
        'total_repayment': round(total_repayment, 2),
        'total_payment': round(total_repayment, 2),
        'balance_amount': balance_amount,
        'summary': {
            'total_advance': round(total_advance, 2),
            'total_repayment': round(total_repayment, 2),
            'total_payment': round(total_repayment, 2),
            'balance': balance_amount
        }
    }

# ----------------- SALARY REPORTS ----------------- #

def get_salary_reports(start_month=None, end_month=None, search=None, page=1, limit=10, company_id=None, branch_id=None):
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)

    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if b_id:
        b_names, _ = get_cached_branch_names_and_ids(b_id, company_id)
        branch_cond = get_branch_record_condition(b_id, b_names)
        if branch_cond:
            query.setdefault('$and', []).append(branch_cond)
        
    if not start_month and not end_month:
        _, _, def_start_month, _ = get_default_two_month_range()
        start_month = def_start_month

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
    if not doc and clean in ['technologiesargus@gmail.com', 'productionargus@gmail.com', 'admin']:
        # Ensure Super Admin doc exists in MongoDB
        target_email = clean if '@' in clean else 'technologiesargus@gmail.com'
        db.admin_users.update_one(
            {'email': target_email},
            {'$set': {
                'email': target_email,
                'username': 'Admin' if target_email == 'technologiesargus@gmail.com' else 'Argus Admin',
                'password': 'scrypt:32768:8:1$QxyLtGr6uxVY074M$7d6c233d713711c9a2c1f470668c0951cf5b743bfb8f08276e0110ac6d8d44650ae4ab1fa120eaac27164317ee39494029048ae0251f71cd7255181c4062ba08',
                'password_hash': 'scrypt:32768:8:1$QxyLtGr6uxVY074M$7d6c233d713711c9a2c1f470668c0951cf5b743bfb8f08276e0110ac6d8d44650ae4ab1fa120eaac27164317ee39494029048ae0251f71cd7255181c4062ba08',
                'password_raw': '76543',
                'role': 'super_admin',
                'company_id': 'ARGUS_MASTER',
                'company_name': 'ARGUS TECHNOLOGIES'
            }},
            upsert=True
        )
        doc = db.admin_users.find_one({'email': target_email})

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

def get_payslip_data(employee_name, month_year, company_id=None, branch_id=None):
    db = get_db()
    emp = None
    if company_id and company_id not in ['ALL', 'ARGUS_MASTER']:
        emp = db.employees.find_one({'employee_name': employee_name, 'company_id': str(company_id)})
    if not emp:
        emp = db.employees.find_one({'employee_name': employee_name})
    if not emp and company_id and company_id not in ['ALL', 'ARGUS_MASTER']:
        emp = db.employees.find_one({'employee_name': {'$regex': f"^{re.escape(str(employee_name).strip())}$", '$options': 'i'}, 'company_id': str(company_id)})
    if not emp:
        emp = db.employees.find_one({'employee_name': {'$regex': f"^{re.escape(str(employee_name).strip())}$", '$options': 'i'}})
    
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

    # Dynamically resolve respective company based on employee's company assignment
    emp_comp_id = str((emp.get('company_id') if (emp and emp.get('company_id')) else None) or company_id or 'ARGUS_MASTER')
    assigned_company_id = emp_comp_id
    emp_comp_name = emp.get('company_name') if emp else None

    comp_doc = None
    if emp_comp_id and emp_comp_id != 'ARGUS_MASTER':
        comp_doc = db.company_admin.find_one({'id': emp_comp_id})
        if not comp_doc:
            comp_doc = db.company_admin.find_one(build_id_filter(emp_comp_id))
    if not comp_doc and emp_comp_name:
        comp_doc = db.company_admin.find_one({'company_name': emp_comp_name})
    if not comp_doc and company_id and company_id not in ['ALL', 'ARGUS_MASTER']:
        comp_doc = db.company_admin.find_one({'id': str(company_id)})
        if not comp_doc:
            comp_doc = db.company_admin.find_one(build_id_filter(company_id))
    if not comp_doc:
        comp_doc = db.company_admin.find_one({'id': 'ARGUS_MASTER'})

    company_name = 'ARGUS TECHNOLOGIES'
    company_address = 'SF NO. 515, Bharathiyar Road, Maniyakaranpalayam, Ganapathy (PO), Coimbatore - 641 006'
    comp_email = 'technologiesargus@gmail.com'
    comp_phone = '+91 98765 43210'
    comp_gstin = '33AHZPG5373L2ZN'
    comp_logo = ''
    comp_logo_data = ''

    if comp_doc:
        company_name = comp_doc.get('company_name') or company_name
        comp_email = comp_doc.get('email') or comp_email
        comp_phone = comp_doc.get('phone') or comp_phone
        comp_gstin = comp_doc.get('gstin') or comp_doc.get('company_gstin') or comp_gstin
        loc = comp_doc.get('address') or comp_doc.get('location') or ''
        if loc:
            company_address = loc
        else:
            lat = comp_doc.get('latitude')
            lng = comp_doc.get('longitude')
            if lat and lng:
                company_address = f"Location: Lat {lat}, Lng {lng}"
        comp_logo = str(comp_doc.get('logo') or comp_doc.get('company_logo') or '')
        comp_logo_data = str(comp_doc.get('logo_data') or '')

    active_b = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    
    resolved_branch_name = None
    if active_b:
        if is_home_branch_id(active_b):
            resolved_branch_name = 'HOME'
        else:
            b_obj = db.company_branches.find_one({'id': active_b})
            if not b_obj and company_id and company_id != 'ALL':
                b_obj = db.company_branches.find_one({'id': active_b, 'company_id': str(company_id)})
            if b_obj:
                resolved_branch_name = b_obj.get('branch_name')
                if b_obj.get('location'):
                    company_address = b_obj.get('location')
            else:
                resolved_branch_name = active_b
    else:
        # Fall back to employee's assigned branch
        if emp:
            emp_bid = emp.get('branch_id')
            if emp_bid and not is_home_branch_id(emp_bid):
                b_obj = db.company_branches.find_one({'id': emp_bid})
                if b_obj:
                    resolved_branch_name = b_obj.get('branch_name')
                    if b_obj.get('location'):
                        company_address = b_obj.get('location')
                else:
                    resolved_branch_name = emp.get('branch_name') or emp_bid
            else:
                resolved_branch_name = 'HOME'
        else:
            resolved_branch_name = 'HOME'

    if resolved_branch_name:
        suffix = f" - {resolved_branch_name.upper()}"
        if not company_name.upper().endswith(suffix.upper()):
            company_name = f"{company_name}{suffix}"

    shift_hours_str = emp.get('shift_hours', '08:00') if emp else '08:00'
    shift_target_minutes = parse_shift_hours_to_minutes(shift_hours_str, default_minutes=480)
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
        exit_t_val = str(rec.get('exit_time') or '').strip()
        if exit_t_val in ['', '----', '-']:
            continue
        is_auto_timeout = bool(rec.get('is_timeout') or 'AUTO TIMEOUT' in str(rec.get('exit_distance', '')).upper() or 'AUTO PUNCH-OUT' in str(rec.get('exit_location', '')).upper())
        if shift_target_minutes == 0 and is_auto_timeout:
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
        if shift_target_minutes > 0:
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
    positive_days = {d: m for d, m in net_daily_minutes.items() if m > 0 or daily_manual_salary.get(d, 0.0) > 0}
    total_minutes = max(0, sum(daily_minutes.values()))
    working_days = len(positive_days)
    tot_hrs = total_minutes // 60
    tot_mins = total_minutes % 60
    working_hours = f"{tot_hrs:02d}:{tot_mins:02d}"

    full_days = 0
    half_days = 0
    partial_days = 0
    partial_minutes = 0
    total_half_units = 0

    if shift_target_minutes == 0:
        for d, mins in net_daily_minutes.items():
            if mins > 0:
                partial_days += 1
                partial_minutes += mins
    elif salary_type == 'half_day':
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
        total_half_units = (full_days * 2) + half_days
    else:
        for d, mins in net_daily_minutes.items():
            if mins >= shift_target_minutes:
                full_days += 1
            elif mins >= half_shift_target:
                half_days += 1
            elif mins > 0:
                partial_days += 1
                partial_minutes += mins

    effective_half = half_salary if half_salary > 0 else (day_salary / 2.0 if day_salary > 0 else (hours_salary * 4.0 if shift_target_minutes > 0 else 0.0))
    effective_hour = hours_salary if hours_salary > 0 else (day_salary / (shift_target_minutes / 60.0) if (day_salary > 0 and shift_target_minutes > 0) else 0.0)
    manual_salary_sum = sum(daily_manual_salary.values())

    # Calculate basic salary accurately based on salary_type and presence of records vs manual_entries
    if not records and manual_entries:
        # Solely driven by manual entries: basic salary is exact net sum of manual entries' working salary
        manual_net = sum(float(m.get('working_salary', 0.0)) for m in manual_entries)
        basic_salary = max(0.0, round(manual_net, 2))
    elif shift_target_minutes == 0 or salary_type == 'hourly':
        basic_salary = round((total_minutes / 60.0) * hours_salary, 2)
        unapplied_deductions = sum(m for d, m in daily_manual_salary.items() if m < 0 and daily_minutes.get(d, 0) < 0)
        unapplied_additions = sum(m for d, m in daily_manual_salary.items() if m > 0 and daily_minutes.get(d, 0) == 0)
        basic_salary = max(0.0, round(basic_salary + unapplied_deductions + unapplied_additions, 2))
    elif salary_type == 'daily':
        part_sal = (partial_minutes / 60.0) * effective_hour
        basic_salary = round((full_days * day_salary) + (half_days * effective_half) + part_sal, 2)
        # Deduct unapplied manual deductions (e.g. deductions logged on days without biometric punches)
        unapplied_deductions = sum(m for d, m in daily_manual_salary.items() if m < 0 and daily_minutes.get(d, 0) < 0)
        unapplied_additions = sum(m for d, m in daily_manual_salary.items() if m > 0 and daily_minutes.get(d, 0) == 0)
        basic_salary = max(0.0, round(basic_salary + unapplied_deductions + unapplied_additions, 2))
    elif salary_type == 'half_day':
        total_half_units = (full_days * 2) + half_days
        target_half_div = ref_half_mins if 'ref_half_mins' in locals() and ref_half_mins > 0 else 240
        part_sal = (partial_minutes / float(target_half_div)) * effective_half
        basic_salary = round((total_half_units * effective_half) + part_sal, 2)
        unapplied_deductions = sum(m for d, m in daily_manual_salary.items() if m < 0 and daily_minutes.get(d, 0) < 0)
        unapplied_additions = sum(m for d, m in daily_manual_salary.items() if m > 0 and daily_minutes.get(d, 0) == 0)
        basic_salary = max(0.0, round(basic_salary + unapplied_deductions + unapplied_additions, 2))
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
    other_deductions = 0.0

    for p in payments:
        p_amt = float(p.get('amount', 0.0))
        reason = (p.get('status') or p.get('reason') or '').strip()
        r_low = reason.lower()
        if r_low == 'incentive':
            incentive += p_amt
        elif r_low == 'allowance':
            allowance += p_amt
        elif 'advance' in r_low:
            advance_repayment += p_amt
        elif r_low in ['salary', 'paid salary']:
            paid_salary += p_amt
        elif 'deduction' in r_low:
            other_deductions += p_amt
        elif 'earning' in r_low:
            other_earnings += p_amt
        else:
            other_earnings += p_amt

    # If no advance repayment logged in payments for this month, check advances collection
    if advance_repayment == 0.0:
        adv_doc = db.advances.find_one({'employee_name': employee_name})
        if adv_doc:
            advance_repayment = float(adv_doc.get('repayment_amount', 0.0))

    total_earnings = round(basic_salary + allowance + incentive + other_earnings, 2)
    # Paid salary is added to total deduction per user Requirement 7
    total_deduction = round(paid_salary + advance_repayment + other_deductions, 2)
    net_pay = max(0.0, round(total_earnings - total_deduction, 2))
        
    leave_days = max(0, total_days - working_days)
    
    # 4. Query approved leave requests for this employee & month
    approved_leave_query = {
        'employee_name': employee_name,
        'request_type': 'Leave',
        'status': 'Approved',
        '$or': [
            {'from_date': {'$regex': f'^{month_year}'}},
            {'to_date': {'$regex': f'^{month_year}'}}
        ]
    }
    if assigned_company_id and assigned_company_id not in ['ALL', 'ARGUS_MASTER']:
        approved_leave_query['company_id'] = str(assigned_company_id)

    approved_leaves = list(db.leave_requests.find(approved_leave_query))

    try:
        y, m = int(month_year.split('-')[0]), int(month_year.split('-')[1])
        month_start = date(y, m, 1)
        month_end = date(y, m, calendar.monthrange(y, m)[1])
    except:
        month_start = month_end = None

    paid_leave_days = 0.0
    paid_leave_half_days = 0
    paid_leave_details = []  # list of {'date': ..., 'type': ..., 'days': ...}

    for lv in approved_leaves:
        try:
            fd = datetime.strptime(lv.get('from_date', ''), '%Y-%m-%d').date()
            td = datetime.strptime(lv.get('to_date', lv.get('from_date', '')), '%Y-%m-%d').date()
        except:
            continue
        
        session = lv.get('session', 'Full Day')
        leave_type = lv.get('leave_type', 'Casual Leave (CL)')
        
        if session == 'Half Day':
            # Half day leave = 0.5 day
            if month_start and month_end and month_start <= fd <= month_end:
                d_str = fd.strftime('%Y-%m-%d')
                # Only count if employee didn't already work a full day
                if daily_minutes.get(d_str, 0) < shift_target_minutes:
                    paid_leave_days += 0.5
                    paid_leave_half_days += 1
                    paid_leave_details.append({'date': d_str, 'type': leave_type, 'days': 0.5, 'session': 'Half Day'})
        else:
            # Full day - iterate each date in the range
            current = max(fd, month_start) if month_start else fd
            end = min(td, month_end) if month_end else td
            while current <= end:
                d_str = current.strftime('%Y-%m-%d')
                # Only count as paid leave if employee did NOT punch in that day
                if daily_minutes.get(d_str, 0) == 0:
                    paid_leave_days += 1.0
                    paid_leave_details.append({'date': d_str, 'type': leave_type, 'days': 1.0, 'session': 'Full Day'})
                current += timedelta(days=1)

    approved_perm_query = {
        'employee_name': employee_name,
        'request_type': 'Permission',
        'status': 'Approved',
        '$or': [
            {'from_date': {'$regex': f'^{month_year}'}},
            {'date': {'$regex': f'^{month_year}'}}
        ]
    }
    if assigned_company_id and assigned_company_id not in ['ALL', 'ARGUS_MASTER']:
        approved_perm_query['company_id'] = str(assigned_company_id)

    approved_perms = list(db.leave_requests.find(approved_perm_query))
    permission_hours_used = 0.0
    permission_details = []
    for pm in approved_perms:
        dur = float(pm.get('duration_hours', pm.get('hours_count', 0)))
        permission_hours_used += dur
        permission_details.append({
            'date': pm.get('date') or pm.get('from_date', ''),
            'hours': dur,
            'type': pm.get('permission_type', 'Short Leave')
        })

    paid_leave_salary = 0.0
    if paid_leave_days > 0 and shift_target_minutes > 0:
        if salary_type == 'daily':
            paid_leave_salary = round((paid_leave_days * day_salary), 2)
        elif salary_type == 'half_day':
            paid_leave_salary = round((paid_leave_days * 2 * effective_half), 2)  # each day = 2 half-day units
        elif salary_type == 'hourly':
            paid_leave_salary = round((paid_leave_days * shift_target_minutes / 60.0) * hours_salary, 2)
        else:
            if day_salary > 0:
                paid_leave_salary = round((paid_leave_days * day_salary), 2)
            elif hours_salary > 0:
                paid_leave_salary = round((paid_leave_days * shift_target_minutes / 60.0) * hours_salary, 2)
        basic_salary = round(basic_salary + paid_leave_salary, 2)

    total_earnings = round(basic_salary + allowance + incentive + other_earnings, 2)
    net_pay = max(0.0, round(total_earnings - total_deduction, 2))
    absent_days_lop = max(0, leave_days - paid_leave_days)

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
    rep_hours_salary = round(hours_salary, 2) if salary_type == 'hourly' else 0
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
        'basic_salary': round(basic_salary, 2) if salary_type == 'hourly' else int(round(basic_salary)),
        'allowance': int(round(allowance)),
        'incentive': int(round(incentive)),
        'other_earnings': int(round(other_earnings)),
        'total_earnings': round(total_earnings, 2) if salary_type == 'hourly' else int(round(total_earnings)),
        'paid_salary': int(round(paid_salary)),
        'advance_repayment': int(round(advance_repayment)),
        'other_deductions': int(round(other_deductions)),
        'total_deduction': int(round(total_deduction)),
        'total_deductions': int(round(total_deduction)),
        'net_pay': round(net_pay, 2) if salary_type == 'hourly' else int(round(net_pay)),
        'net_pay_in_words': net_pay_in_words,
        'email_id': str(emp.get('email_id') or emp.get('email', '') if emp else ''),
        'department': str(emp.get('department', '') or 'General' if emp else 'General'),
        'employee_photo': str(emp.get('photo') or emp.get('photo_filename', '') if emp else ''),
        'employee_photo_data': str(emp.get('photo_data', '') if emp else ''),
        'employee_photo_url': (emp.get('photo_data') if (emp and emp.get('photo_data')) else (f"/uploads/{emp.get('photo') or emp.get('photo_filename')}" if emp and (emp.get('photo') or emp.get('photo_filename')) else '')) if emp else '',
        'company_logo': comp_logo,
        'company_logo_data': comp_logo_data,
        'company_logo_url': comp_logo_data if comp_logo_data else (f"/uploads/{comp_logo}" if comp_logo else ''),
        'paid_leave_days': paid_leave_days,
        'paid_leave_half_days': paid_leave_half_days,
        'paid_leave_salary': round(paid_leave_salary, 2) if salary_type == 'hourly' else int(round(paid_leave_salary)),
        'paid_leave_details': paid_leave_details,
        'absent_days_lop': absent_days_lop,
        'permission_hours_used': permission_hours_used,
        'permission_details': permission_details,
        'leave_breakdown': f"{int(paid_leave_days)} Paid, {int(absent_days_lop)} LOP" if (paid_leave_days > 0 or absent_days_lop > 0) else f"{leave_days} Leave",
    }


# ==============================================================================
# LEAVE & PERMISSION MANAGEMENT ENGINE
# ==============================================================================

def get_company_leave_policy(company_id=None):
    """
    Retrieves the company's annual leave policy.
    Checks:
    1. Dedicated db.leave_policies collection (specific tenant or global DEFAULT/ARGUS_MASTER)
    2. Embedded leave_policy in db.company_admin / db.companies
    3. Global system fallback
    """
    default_policy = {
        'casual_leave': 12,
        'casual_leave_annual': 12,
        'sick_leave': 12,
        'sick_leave_annual': 12,
        'earned_leave': 18,
        'earned_leave_annual': 18,
        'permission_hours': 16.0,
        'permission_hours_monthly': 16
    }
    db = get_db()
    # Check if a global default policy is stored in database
    global_rec = db.leave_policies.find_one({'company_id': {'$in': ['DEFAULT', 'ALL', 'ARGUS_MASTER']}})
    if global_rec:
        default_policy = {
            'casual_leave': int(global_rec.get('casual_leave_annual', global_rec.get('casual_leave', 12))),
            'casual_leave_annual': int(global_rec.get('casual_leave_annual', global_rec.get('casual_leave', 12))),
            'sick_leave': int(global_rec.get('sick_leave_annual', global_rec.get('sick_leave', 12))),
            'sick_leave_annual': int(global_rec.get('sick_leave_annual', global_rec.get('sick_leave', 12))),
            'earned_leave': int(global_rec.get('earned_leave_annual', global_rec.get('earned_leave', 18))),
            'earned_leave_annual': int(global_rec.get('earned_leave_annual', global_rec.get('earned_leave', 18))),
            'permission_hours': float(global_rec.get('permission_hours_monthly', global_rec.get('permission_hours', 16.0))),
            'permission_hours_monthly': int(float(global_rec.get('permission_hours_monthly', global_rec.get('permission_hours', 16.0))))
        }

    if not company_id or str(company_id).upper() in ['ALL', 'ARGUS_MASTER', 'DEFAULT', '']:
        return default_policy

    # 1. Check dedicated leave_policies collection for this specific tenant
    pol_rec = db.leave_policies.find_one({
        '$or': [
            {'company_id': str(company_id)},
            {'company_id': int(company_id) if str(company_id).isdigit() else str(company_id)}
        ]
    })
    if pol_rec:
        cl = int(pol_rec.get('casual_leave_annual', pol_rec.get('casual_leave', default_policy['casual_leave'])))
        sl = int(pol_rec.get('sick_leave_annual', pol_rec.get('sick_leave', default_policy['sick_leave'])))
        el = int(pol_rec.get('earned_leave_annual', pol_rec.get('earned_leave', default_policy['earned_leave'])))
        ph = float(pol_rec.get('permission_hours_monthly', pol_rec.get('permission_hours', default_policy['permission_hours'])))
        return {
            'casual_leave': cl,
            'casual_leave_annual': cl,
            'sick_leave': sl,
            'sick_leave_annual': sl,
            'earned_leave': el,
            'earned_leave_annual': el,
            'permission_hours': ph,
            'permission_hours_monthly': int(ph)
        }

    # 2. Check company_admin document
    comp = db.company_admin.find_one(build_id_filter(company_id))
    if not comp:
        comp = db.companies.find_one(build_id_filter(company_id))
    if comp and 'leave_policy' in comp and isinstance(comp['leave_policy'], dict):
        pol = comp['leave_policy']
        cl = int(pol.get('casual_leave_annual', pol.get('casual_leave', default_policy['casual_leave'])))
        sl = int(pol.get('sick_leave_annual', pol.get('sick_leave', default_policy['sick_leave'])))
        el = int(pol.get('earned_leave_annual', pol.get('earned_leave', default_policy['earned_leave'])))
        ph = float(pol.get('permission_hours_monthly', pol.get('permission_hours', default_policy['permission_hours'])))
        return {
            'casual_leave': cl,
            'casual_leave_annual': cl,
            'sick_leave': sl,
            'sick_leave_annual': sl,
            'earned_leave': el,
            'earned_leave_annual': el,
            'permission_hours': ph,
            'permission_hours_monthly': int(ph)
        }

    return default_policy

def save_company_leave_policy(company_id, policy_data):
    """Saves or updates the default annual leave allocation policy for a company."""
    db = get_db()
    is_global = not company_id or str(company_id).upper() in ['ALL', 'ARGUS_MASTER', 'DEFAULT', '']
    storage_comp_id = 'DEFAULT' if is_global else str(company_id)

    cl = int(policy_data.get('casual_leave_annual', policy_data.get('casual_leave', 12)))
    sl = int(policy_data.get('sick_leave_annual', policy_data.get('sick_leave', 12)))
    el = int(policy_data.get('earned_leave_annual', policy_data.get('earned_leave', 18)))
    ph = float(policy_data.get('permission_hours_monthly', policy_data.get('permission_hours', 16.0)))

    pol_doc = {
        'company_id': storage_comp_id,
        'casual_leave': cl,
        'casual_leave_annual': cl,
        'sick_leave': sl,
        'sick_leave_annual': sl,
        'earned_leave': el,
        'earned_leave_annual': el,
        'permission_hours': ph,
        'permission_hours_monthly': int(ph),
        'updated_at': get_ist_now()
    }
    if is_global:
        db.leave_policies.update_one({'company_id': 'DEFAULT'}, {'$set': pol_doc}, upsert=True)
        db.leave_policies.update_one({'company_id': 'ARGUS_MASTER'}, {'$set': pol_doc}, upsert=True)
        db.leave_policies.update_one({'company_id': 'ALL'}, {'$set': pol_doc}, upsert=True)
    else:
        db.leave_policies.update_one({'company_id': storage_comp_id}, {'$set': pol_doc}, upsert=True)
        if storage_comp_id.isdigit():
            db.leave_policies.update_one({'company_id': int(storage_comp_id)}, {'$set': pol_doc}, upsert=True)

        q = {'id': int(storage_comp_id)} if storage_comp_id.isdigit() else build_id_filter(storage_comp_id)
        db.company_admin.update_one(q, {'$set': {'leave_policy': pol_doc}})

    # Synchronize all existing and new leave balances for this company for current year
    try:
        curr_year = get_ist_now().year
        emp_query = {}
        if not is_global:
            emp_query = {
                '$or': [
                    {'company_id': storage_comp_id},
                    {'company_id': int(storage_comp_id) if storage_comp_id.isdigit() else storage_comp_id}
                ]
            }
        employees = list(db.employees.find(emp_query))
        for emp in employees:
            # If employee already has their own custom leave_quota, do not overwrite with global policy
            if emp.get('leave_quota'):
                continue
            e_id = str(emp.get('id') or emp.get('_id'))
            c_id = str(emp.get('company_id') or storage_comp_id)
            bal = db.leave_balances.find_one({
                '$or': [
                    {'employee_id': e_id},
                    {'employee_id': int(e_id) if e_id.isdigit() else e_id}
                ],
                'year': int(curr_year)
            })
            if bal:
                cl_obj = bal.get('casual_leave') or {}
                sl_obj = bal.get('sick_leave') or {}
                el_obj = bal.get('earned_leave') or {}
                ph_obj = bal.get('permission_hours') or {}

                cl_used = float(cl_obj.get('used', 0) if isinstance(cl_obj, dict) else 0)
                sl_used = float(sl_obj.get('used', 0) if isinstance(sl_obj, dict) else 0)
                el_used = float(el_obj.get('used', 0) if isinstance(el_obj, dict) else 0)
                ph_used = float(ph_obj.get('used', 0) if isinstance(ph_obj, dict) else 0)

                db.leave_balances.update_one(
                    {'_id': bal['_id']},
                    {'$set': {
                        'casual_leave.total': cl,
                        'casual_leave.available': max(0.0, round(cl - cl_used, 1)),
                        'sick_leave.total': sl,
                        'sick_leave.available': max(0.0, round(sl - sl_used, 1)),
                        'earned_leave.total': el,
                        'earned_leave.available': max(0.0, round(el - el_used, 1)),
                        'permission_hours.total': ph,
                        'permission_hours.available': max(0.0, round(ph - ph_used, 2)),
                        'updated_at': get_ist_now()
                    }}
                )
            else:
                new_bal = {
                    'company_id': c_id,
                    'employee_id': e_id,
                    'year': int(curr_year),
                    'casual_leave': {'total': cl, 'used': 0, 'available': cl},
                    'sick_leave': {'total': sl, 'used': 0, 'available': sl},
                    'earned_leave': {'total': el, 'used': 0, 'available': el},
                    'permission_hours': {'total': ph, 'used': 0.0, 'available': ph},
                    'compensatory_off': {'total': 6, 'used': 0, 'available': 6},
                    'created_at': get_ist_now(),
                    'updated_at': get_ist_now()
                }
                db.leave_balances.insert_one(new_bal)
    except Exception as e:
        print("Error synchronizing leave balances on policy update:", e)

    return True

def save_employee_leave_quota(emp_id, quota_data, company_id=None, year=None):
    """
    Saves dynamic leave quota (CL, SL, EL, permission_hours) for a specific employee.
    Persists to db.employees and updates db.leave_balances.
    """
    db = get_db()
    if not emp_id:
        return {'success': False, 'error': 'Employee ID is required'}
        
    emp = db.employees.find_one(build_id_filter(emp_id))
    if not emp:
        return {'success': False, 'error': f"Employee with ID '{emp_id}' not found"}

    e_id = str(emp.get('id') or emp.get('_id'))
    comp_id = company_id or emp.get('company_id') or 'ARGUS_MASTER'
    if year is None:
        year = get_ist_now().year

    try:
        cl = max(0, int(quota_data.get('casual_leave', quota_data.get('casual_leave_annual', 12))))
        sl = max(0, int(quota_data.get('sick_leave', quota_data.get('sick_leave_annual', 12))))
        el = max(0, int(quota_data.get('earned_leave', quota_data.get('earned_leave_annual', 12))))
        ph = max(0.0, float(quota_data.get('permission_hours', quota_data.get('permission_hours_monthly', 16))))
    except (ValueError, TypeError) as ex:
        return {'success': False, 'error': f"Invalid quota values: {ex}"}

    leave_quota = {
        'casual_leave_annual': cl,
        'sick_leave_annual': sl,
        'earned_leave_annual': el,
        'permission_hours_monthly': ph,
        'updated_at': get_ist_now()
    }

    # 1. Update in db.employees
    db.employees.update_one(
        build_id_filter(emp_id),
        {'$set': {
            'leave_quota': leave_quota,
            'updated_at': get_ist_now()
        }}
    )

    # 2. Update or insert in db.leave_balances
    bal = db.leave_balances.find_one({
        '$or': [
            {'employee_id': str(e_id)},
            {'employee_id': int(e_id) if str(e_id).isdigit() else str(e_id)},
            {'employee_id': str(emp_id)},
            {'employee_id': int(emp_id) if str(emp_id).isdigit() else str(emp_id)}
        ],
        'year': int(year)
    })

    if bal:
        cl_obj = bal.get('casual_leave') or {}
        sl_obj = bal.get('sick_leave') or {}
        el_obj = bal.get('earned_leave') or {}
        ph_obj = bal.get('permission_hours') or {}

        cl_used = float(cl_obj.get('used', 0) if isinstance(cl_obj, dict) else 0)
        sl_used = float(sl_obj.get('used', 0) if isinstance(sl_obj, dict) else 0)
        el_used = float(el_obj.get('used', 0) if isinstance(el_obj, dict) else 0)
        ph_used = float(ph_obj.get('used', 0) if isinstance(ph_obj, dict) else 0)

        db.leave_balances.update_one(
            {'_id': bal['_id']},
            {'$set': {
                'casual_leave.total': cl,
                'casual_leave.available': max(0.0, round(cl - cl_used, 1)),
                'sick_leave.total': sl,
                'sick_leave.available': max(0.0, round(sl - sl_used, 1)),
                'earned_leave.total': el,
                'earned_leave.available': max(0.0, round(el - el_used, 1)),
                'permission_hours.total': ph,
                'permission_hours.available': max(0.0, round(ph - ph_used, 2)),
                'updated_at': get_ist_now()
            }}
        )
    else:
        new_bal = {
            'company_id': str(comp_id),
            'employee_id': str(e_id),
            'year': int(year),
            'casual_leave': {'total': cl, 'used': 0, 'available': cl},
            'sick_leave': {'total': sl, 'used': 0, 'available': sl},
            'earned_leave': {'total': el, 'used': 0, 'available': el},
            'permission_hours': {'total': ph, 'used': 0.0, 'available': ph},
            'compensatory_off': {'total': 6, 'used': 0, 'available': 6},
            'created_at': get_ist_now(),
            'updated_at': get_ist_now()
        }
        db.leave_balances.insert_one(new_bal)

    updated_bal = get_employee_leave_balance(e_id, company_id=comp_id, year=year)
    return {
        'success': True,
        'message': f"Leave quota updated successfully for {emp.get('employee_name', emp_id)}",
        'balance': updated_bal,
        'quota': leave_quota
    }

def save_employee_custom_leaves(emp_id, custom_leaves_list, company_id=None, year=None):
    """
    Saves dynamic custom leave types for a specific employee.
    Each item has:
      - 'name': str (e.g. 'Casual Leave', 'Sick Leave', 'Special Leave', 'Short Permission', etc.)
      - 'total': float/int (allocated count)
      - 'unit': str ('Days' or 'Hours', default 'Days')
    Persists to db.employees and updates db.leave_balances.
    """
    db = get_db()
    if not emp_id:
        return {'success': False, 'error': 'Employee ID is required'}
        
    emp = db.employees.find_one(build_id_filter(emp_id))
    if not emp:
        return {'success': False, 'error': f"Employee with ID '{emp_id}' not found"}

    e_id = str(emp.get('id') or emp.get('_id'))
    comp_id = company_id or emp.get('company_id') or 'ARGUS_MASTER'
    if year is None:
        year = get_ist_now().year

    # Process and sanitize custom leaves list
    processed_leaves = []
    seen_names = set()
    for item in (custom_leaves_list or []):
        if not isinstance(item, dict):
            continue
        raw_name = str(item.get('name') or '').strip()
        if not raw_name:
            continue
        norm_name = raw_name.lower()
        if norm_name in seen_names:
            continue
        seen_names.add(norm_name)
        
        try:
            total_val = float(item.get('total') or item.get('quota') or 0.0)
            if total_val.is_integer():
                total_val = int(total_val)
        except (ValueError, TypeError):
            total_val = 0
            
        unit_val = str(item.get('unit') or 'Days').strip().capitalize()
        if unit_val not in ['Days', 'Hours']:
            unit_val = 'Days'
            
        processed_leaves.append({
            'name': raw_name,
            'total': max(0, total_val),
            'unit': unit_val
        })

    # 1. Update in db.employees
    db.employees.update_one(
        build_id_filter(emp_id),
        {'$set': {
            'custom_leaves': processed_leaves,
            'updated_at': get_ist_now()
        }}
    )

    # 2. Update or insert in db.leave_balances
    bal = db.leave_balances.find_one({
        '$or': [
            {'employee_id': str(e_id)},
            {'employee_id': int(e_id) if str(e_id).isdigit() else str(e_id)},
            {'employee_id': str(emp_id)},
            {'employee_id': int(emp_id) if str(emp_id).isdigit() else str(emp_id)}
        ],
        'year': int(year)
    })

    # Map previous used counts for matching leave types (case-insensitive)
    existing_used_map = {}
    if bal and 'custom_leaves' in bal:
        for ex in bal['custom_leaves']:
            if isinstance(ex, dict) and 'name' in ex:
                existing_used_map[ex['name'].lower()] = float(ex.get('used', 0.0))

    if bal:
        cl_u = float(bal.get('casual_leave', {}).get('used', 0.0) if isinstance(bal.get('casual_leave'), dict) else 0.0)
        if cl_u: existing_used_map.setdefault('casual leave', cl_u)
        sl_u = float(bal.get('sick_leave', {}).get('used', 0.0) if isinstance(bal.get('sick_leave'), dict) else 0.0)
        if sl_u: existing_used_map.setdefault('sick leave', sl_u)
        el_u = float(bal.get('earned_leave', {}).get('used', 0.0) if isinstance(bal.get('earned_leave'), dict) else 0.0)
        if el_u: existing_used_map.setdefault('earned leave', el_u)
        ph_u = float(bal.get('permission_hours', {}).get('used', 0.0) if isinstance(bal.get('permission_hours'), dict) else 0.0)
        if ph_u: existing_used_map.setdefault('permission', ph_u)

    final_balance_leaves = []
    for pl in processed_leaves:
        n_low = pl['name'].lower()
        used_val = existing_used_map.get(n_low, 0.0)
        avail_val = max(0.0, round(float(pl['total']) - used_val, 2))
        if avail_val.is_integer():
            avail_val = int(avail_val)
        if isinstance(used_val, float) and used_val.is_integer():
            used_val = int(used_val)
            
        final_balance_leaves.append({
            'name': pl['name'],
            'total': pl['total'],
            'used': used_val,
            'available': avail_val,
            'unit': pl['unit']
        })

    if bal:
        db.leave_balances.update_one(
            {'_id': bal['_id']},
            {'$set': {
                'custom_leaves': final_balance_leaves,
                'updated_at': get_ist_now()
            }}
        )
    else:
        new_bal = {
            'company_id': str(comp_id),
            'employee_id': str(e_id),
            'year': int(year),
            'custom_leaves': final_balance_leaves,
            'created_at': get_ist_now(),
            'updated_at': get_ist_now()
        }
        db.leave_balances.insert_one(new_bal)

    return {
        'success': True,
        'message': f"Custom leaves updated successfully for {emp.get('employee_name', emp_id)}",
        'custom_leaves': final_balance_leaves
    }

def get_employee_leave_balance(emp_id, company_id=None, year=None):
    """
    Retrieves or initializes the employee's leave balance document for the given year.
    Returns: dict with casual_leave, sick_leave, earned_leave, permission_hours, compensatory_off, custom_leaves
    """
    if not emp_id:
        return None
    db = get_db()
    if year is None:
        year = get_ist_now().year
    
    bal = db.leave_balances.find_one({
        '$or': [
            {'employee_id': str(emp_id)},
            {'employee_id': int(emp_id) if str(emp_id).isdigit() else str(emp_id)}
        ],
        'year': int(year)
    })
    
    if not bal:
        # Initialize new balance using employee quota or company policy
        emp = db.employees.find_one(build_id_filter(emp_id))
        comp_id = company_id or (emp.get('company_id') if emp else None)
        pol = get_company_leave_policy(comp_id)

        quota = emp.get('leave_quota') if emp else None
        if quota and isinstance(quota, dict):
            cl_tot = quota.get('casual_leave_annual', quota.get('casual_leave', pol['casual_leave_annual']))
            sl_tot = quota.get('sick_leave_annual', quota.get('sick_leave', pol['sick_leave_annual']))
            el_tot = quota.get('earned_leave_annual', quota.get('earned_leave', pol['earned_leave_annual']))
            ph_tot = quota.get('permission_hours_monthly', quota.get('permission_hours', pol['permission_hours_monthly']))
        else:
            cl_tot = pol['casual_leave_annual']
            sl_tot = pol['sick_leave_annual']
            el_tot = pol['earned_leave_annual']
            ph_tot = pol['permission_hours_monthly']

        new_bal = {
            'company_id': str(comp_id or 'DEFAULT'),
            'employee_id': str(emp_id),
            'year': int(year),
            'casual_leave': {'total': cl_tot, 'used': 0, 'available': cl_tot},
            'sick_leave': {'total': sl_tot, 'used': 0, 'available': sl_tot},
            'earned_leave': {'total': el_tot, 'used': 0, 'available': el_tot},
            'permission_hours': {'total': ph_tot, 'used': 0.0, 'available': ph_tot},
            'compensatory_off': {'total': 6, 'used': 0, 'available': 6},
            'created_at': get_ist_now(),
            'updated_at': get_ist_now()
        }
        res = db.leave_balances.insert_one(new_bal)
        new_bal['_id'] = res.inserted_id
        bal = new_bal

    bal = clean_doc(bal)
    cl = bal.get('casual_leave', {})
    sl = bal.get('sick_leave', {})
    el = bal.get('earned_leave', {})
    ph = bal.get('permission_hours', {})

    def _fmt_val(v):
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v

    bal['casual_leave_available'] = _fmt_val(cl.get('available', 0))
    bal['casual_leave_avail'] = bal['casual_leave_available']
    bal['casual_leave_total'] = _fmt_val(cl.get('total', 12))
    bal['casual_leave_used'] = _fmt_val(cl.get('used', 0))
    bal['sick_leave_available'] = _fmt_val(sl.get('available', 0))
    bal['sick_leave_avail'] = bal['sick_leave_available']
    bal['sick_leave_total'] = _fmt_val(sl.get('total', 12))
    bal['sick_leave_used'] = _fmt_val(sl.get('used', 0))
    bal['earned_leave_available'] = _fmt_val(el.get('available', 0))
    bal['earned_leave_avail'] = bal['earned_leave_available']
    bal['earned_leave_total'] = _fmt_val(el.get('total', 18))
    bal['earned_leave_used'] = _fmt_val(el.get('used', 0))
    bal['permission_hours_available'] = _fmt_val(ph.get('available', 16.0))
    bal['permission_hours_avail'] = bal['permission_hours_available']
    bal['permission_hours_total'] = _fmt_val(ph.get('total', 16.0))
    bal['permission_hours_used'] = _fmt_val(ph.get('used', 0.0))

    # Format custom leaves if present
    c_leaves = bal.get('custom_leaves')
    if not c_leaves:
        emp = db.employees.find_one(build_id_filter(emp_id))
        if emp and emp.get('custom_leaves'):
            c_leaves = []
            for pl in emp['custom_leaves']:
                tot = pl.get('total', 0)
                c_leaves.append({
                    'name': pl.get('name'),
                    'total': tot,
                    'used': 0,
                    'available': tot,
                    'unit': pl.get('unit', 'Days')
                })
            bal['custom_leaves'] = c_leaves
            db.leave_balances.update_one({'_id': bal['_id']}, {'$set': {'custom_leaves': c_leaves}})

    if c_leaves and isinstance(c_leaves, list) and len(c_leaves) > 0:
        # Check custom permission hours
        perm_custom = next((item for item in c_leaves if str(item.get('name', '')).strip().lower() == 'permission' or str(item.get('unit', '')).strip().lower() in ['hours', 'hrs']), None)
        if perm_custom:
            p_tot = perm_custom.get('total', 0.0)
            p_used = perm_custom.get('used', 0.0)
            p_avail = perm_custom.get('available', max(0.0, float(p_tot) - float(p_used)))
            bal['permission_hours_total'] = _fmt_val(p_tot)
            bal['permission_hours_used'] = _fmt_val(p_used)
            bal['permission_hours_available'] = _fmt_val(p_avail)
            bal['permission_hours_avail'] = bal['permission_hours_available']
        else:
            bal['permission_hours_total'] = 0
            bal['permission_hours_used'] = 0
            bal['permission_hours_available'] = 0
            bal['permission_hours_avail'] = 0

        # Check standard day-based leave types in custom_leaves
        cl_custom = next((item for item in c_leaves if 'casual' in str(item.get('name', '')).strip().lower()), None)
        if cl_custom:
            bal['casual_leave_total'] = _fmt_val(cl_custom.get('total', 0))
            bal['casual_leave_used'] = _fmt_val(cl_custom.get('used', 0))
            bal['casual_leave_available'] = _fmt_val(cl_custom.get('available', 0))
            bal['casual_leave_avail'] = bal['casual_leave_available']
        else:
            bal['casual_leave_total'] = 0
            bal['casual_leave_used'] = 0
            bal['casual_leave_available'] = 0
            bal['casual_leave_avail'] = 0

        sl_custom = next((item for item in c_leaves if 'sick' in str(item.get('name', '')).strip().lower()), None)
        if sl_custom:
            bal['sick_leave_total'] = _fmt_val(sl_custom.get('total', 0))
            bal['sick_leave_used'] = _fmt_val(sl_custom.get('used', 0))
            bal['sick_leave_available'] = _fmt_val(sl_custom.get('available', 0))
            bal['sick_leave_avail'] = bal['sick_leave_available']
        else:
            bal['sick_leave_total'] = 0
            bal['sick_leave_used'] = 0
            bal['sick_leave_available'] = 0
            bal['sick_leave_avail'] = 0

        el_custom = next((item for item in c_leaves if 'earned' in str(item.get('name', '')).strip().lower()), None)
        if el_custom:
            bal['earned_leave_total'] = _fmt_val(el_custom.get('total', 0))
            bal['earned_leave_used'] = _fmt_val(el_custom.get('used', 0))
            bal['earned_leave_available'] = _fmt_val(el_custom.get('available', 0))
            bal['earned_leave_avail'] = bal['earned_leave_available']
        else:
            bal['earned_leave_total'] = 0
            bal['earned_leave_used'] = 0
            bal['earned_leave_available'] = 0
            bal['earned_leave_avail'] = 0

    bal['custom_leaves'] = c_leaves or []
    return bal

def get_all_employees_leave_balances(company_id=None, year=None, search=None, branch_id=None):
    """
    Returns list of all employees in company along with their leave balances.
    Matches Image 4's Employee Leave Balance table.
    """
    db = get_db()
    if year is None:
        year = get_ist_now().year

    e_query = get_branch_employee_query(branch_id, company_id)
    
    employees = list(db.employees.find(e_query).sort('employee_name', ASCENDING))
    results = []

    for idx, emp in enumerate(employees):
        emp_id = str(emp.get('id') or emp.get('_id'))
        emp_code = str(emp.get('id') or emp.get('employee_id') or emp.get('emp_id') or emp_id)
        emp_name = str(emp.get('employee_name') or '')
        dept = str(emp.get('department') or 'General')

        if search:
            s_low = str(search).lower().strip()
            if not (s_low in emp_name.lower() or s_low in emp_code.lower() or s_low in dept.lower() or s_low in emp_id.lower()):
                continue

        bal = get_employee_leave_balance(emp_id, company_id=emp.get('company_id'), year=year)
        
        cl = bal.get('casual_leave', {})
        sl = bal.get('sick_leave', {})
        el = bal.get('earned_leave', {})
        perm = bal.get('permission_hours', {})

        cl_avail = cl.get('available', 0)
        if isinstance(cl_avail, float) and cl_avail.is_integer():
            cl_avail = int(cl_avail)
        cl_tot = cl.get('total', 12)

        sl_avail = sl.get('available', 0)
        if isinstance(sl_avail, float) and sl_avail.is_integer():
            sl_avail = int(sl_avail)
        sl_tot = sl.get('total', 12)

        el_avail = el.get('available', 0)
        if isinstance(el_avail, float) and el_avail.is_integer():
            el_avail = int(el_avail)
        el_tot = el.get('total', 18)

        ph_avail = perm.get('available', 16.0)
        if isinstance(ph_avail, float) and ph_avail.is_integer():
            ph_avail = int(ph_avail)
        ph_tot = perm.get('total', 16.0)
        if isinstance(ph_tot, float) and ph_tot.is_integer():
            ph_tot = int(ph_tot)

        results.append({
            'sl_no': len(results) + 1,
            'id': emp_id,
            'employee_name': emp_name,
            'employee_id': emp_code,
            'department': dept,
            'designation': emp.get('designation', ''),
            'mobile_number': emp.get('mobile_number', ''),
            'company_id': emp.get('company_id', ''),
            'casual_leave': f"{cl_avail} / {cl_tot} Days",
            'casual_leave_avail': cl_avail,
            'casual_leave_available': cl_avail,
            'casual_leave_total': cl_tot,
            'casual_leave_used': cl.get('used', 0),
            'sick_leave': f"{sl_avail} / {sl_tot} Days",
            'sick_leave_avail': sl_avail,
            'sick_leave_available': sl_avail,
            'sick_leave_total': sl_tot,
            'sick_leave_used': sl.get('used', 0),
            'earned_leave': f"{el_avail} / {el_tot} Days",
            'earned_leave_avail': el_avail,
            'earned_leave_available': el_avail,
            'earned_leave_total': el_tot,
            'earned_leave_used': el.get('used', 0),
            'permission_hours': f"{ph_avail} / {ph_tot} Hrs",
            'permission_hours_avail': ph_avail,
            'permission_hours_available': ph_avail,
            'permission_hours_total': ph_tot,
            'permission_hours_used': perm.get('used', 0.0),
            'is_low_balance': (cl.get('available', 0) < 2 or sl.get('available', 0) < 2 or el.get('available', 0) < 2),
            'leave_quota': emp.get('leave_quota'),
            'custom_leaves': bal.get('custom_leaves') or emp.get('custom_leaves') or []
        })

    return results

def get_next_leave_request_id():
    """Generates an incremental integer ID for leave requests."""
    db = get_db()
    last = db.leave_requests.find_one(sort=[('id', DESCENDING)])
    if last and isinstance(last.get('id'), int):
        return last['id'] + 1
    return 1001

def submit_leave_request(req_data):
    """
    Submits a Full Day or Half Day Leave request from Employee Portal.
    """
    db = get_db()
    now_ist = get_ist_now()
    req_id = req_data.get('id') or get_next_leave_request_id()
    request_id_code = str(req_data.get('request_id') or f"LR-{now_ist.year}-{req_id}")

    session_type = req_data.get('session', 'Full Day')
    from_date = str(req_data.get('from_date', '')).strip()
    to_date = str(req_data.get('to_date', '')).strip() or from_date

    # Calculate total days
    total_days = 1.0
    if session_type == 'Half Day':
        total_days = 0.5
        to_date = from_date
    else:
        try:
            d1 = datetime.strptime(from_date, '%Y-%m-%d').date()
            d2 = datetime.strptime(to_date, '%Y-%m-%d').date()
            total_days = max(1.0, float((d2 - d1).days + 1))
        except Exception:
            total_days = 1.0

    doc = {
        'id': req_id,
        'request_id': request_id_code,
        'company_id': str(req_data.get('company_id', '')),
        'employee_id': str(req_data.get('employee_id', '')),
        'employee_code': str(req_data.get('employee_code', '')),
        'employee_name': str(req_data.get('employee_name', '')),
        'department': str(req_data.get('department', 'General')),
        'designation': str(req_data.get('designation', '')),
        'mobile_number': str(req_data.get('mobile_number', '')),
        'request_type': 'Leave',
        'leave_type': req_data.get('leave_type', 'Casual Leave (CL)'),
        'session': session_type,
        'from_date': from_date,
        'to_date': to_date,
        'total_days': total_days,
        'days_count': total_days,
        'from_time': None,
        'to_time': None,
        'duration_hours': None,
        'reason': str(req_data.get('reason', '')).strip(),
        'attachments': req_data.get('attachments', []),
        'status': 'Pending',
        'applied_on': now_ist.strftime('%Y-%m-%d %H:%M:%S'),
        'applied_on_display': now_ist.strftime('%d %b %Y %I:%M %p'),
        'reviewed_by': None,
        'reviewed_at': None,
        'admin_remark': None,
        'created_at': now_ist,
        'updated_at': now_ist
    }
    db.leave_requests.insert_one(doc)
    return clean_doc(doc)

def submit_permission_request(req_data):
    """
    Submits an Hourly Permission request from Employee Portal.
    """
    db = get_db()
    now_ist = get_ist_now()
    req_id = req_data.get('id') or get_next_leave_request_id()
    request_id_code = str(req_data.get('request_id') or f"PR-{now_ist.year}-{req_id}")

    perm_date = str(req_data.get('date', '')).strip()
    from_time = str(req_data.get('from_time', '')).strip()
    to_time = str(req_data.get('to_time', '')).strip()
    duration_str = str(req_data.get('duration', '02:00')).strip()

    # Parse duration in hours
    duration_hours = 2.0
    try:
        clean_dur = duration_str.split(' ')[0]
        if ':' in clean_dur:
            hh, mm = clean_dur.split(':')
            duration_hours = round(int(hh) + int(mm) / 60.0, 2)
        else:
            duration_hours = float(clean_dur)
    except Exception:
        duration_hours = 2.0

    doc = {
        'id': req_id,
        'request_id': request_id_code,
        'company_id': str(req_data.get('company_id', '')),
        'employee_id': str(req_data.get('employee_id', '')),
        'employee_code': str(req_data.get('employee_code', '')),
        'employee_name': str(req_data.get('employee_name', '')),
        'department': str(req_data.get('department', 'General')),
        'designation': str(req_data.get('designation', '')),
        'mobile_number': str(req_data.get('mobile_number', '')),
        'request_type': 'Permission',
        'leave_type': 'Permission',
        'permission_type': req_data.get('permission_type', 'Short Leave'),
        'session': None,
        'from_date': perm_date,
        'to_date': perm_date,
        'date': perm_date,
        'total_days': 0.0,
        'from_time': from_time,
        'to_time': to_time,
        'duration': duration_str,
        'duration_str': duration_str,
        'duration_hours': duration_hours,
        'hours_count': duration_hours,
        'reason': str(req_data.get('reason', '')).strip(),
        'attachments': req_data.get('attachments', []),
        'status': 'Pending',
        'applied_on': now_ist.strftime('%Y-%m-%d %H:%M:%S'),
        'applied_on_display': now_ist.strftime('%d %b %Y %I:%M %p'),
        'reviewed_by': None,
        'reviewed_at': None,
        'admin_remark': None,
        'created_at': now_ist,
        'updated_at': now_ist
    }
    db.leave_requests.insert_one(doc)
    return clean_doc(doc)

def get_leave_requests(company_id=None, employee_id=None, status=None, limit=50, page=1, branch_id=None):
    """Retrieves paginated list of leave & permission requests."""
    db = get_db()
    base_query = {}
    if company_id and company_id != 'ALL':
        base_query['company_id'] = str(company_id)

    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if b_id:
        b_emp_names, b_emp_ids = get_cached_branch_names_and_ids(b_id, company_id)
        branch_cond = get_branch_leave_condition(b_id, b_emp_ids, b_emp_names)
        if branch_cond:
            base_query.setdefault('$and', []).append(branch_cond)

    if employee_id:
        base_query['$or'] = [{'employee_id': str(employee_id)}, {'employee_id': int(employee_id) if str(employee_id).isdigit() else str(employee_id)}]
    
    query = dict(base_query)
    if status and status != 'ALL':
        query['status'] = status

    total = db.leave_requests.count_documents(query)
    skip = (int(page) - 1) * int(limit)
    cursor = db.leave_requests.find(query).sort('created_at', DESCENDING).skip(skip).limit(int(limit))
    
    items = []
    for doc in cursor:
        items.append(clean_doc(doc))

    # Calculate status counts across all requests for this scope (ignoring status filter)
    status_counts = {'all': 0, 'pending': 0, 'approved': 0, 'rejected': 0}
    try:
        pipeline = []
        if base_query:
            pipeline.append({'$match': base_query})
        pipeline.append({'$group': {'_id': '$status', 'count': {'$sum': 1}}})
        
        for item in db.leave_requests.aggregate(pipeline):
            st = str(item.get('_id') or '').strip().lower()
            c = int(item.get('count', 0))
            status_counts['all'] += c
            if st == 'pending':
                status_counts['pending'] = c
            elif st == 'approved':
                status_counts['approved'] = c
            elif st == 'rejected':
                status_counts['rejected'] = c
    except Exception as e:
        print(f"Error computing leave request status counts: {e}")

    return {
        'total': total,
        'page': int(page),
        'limit': int(limit),
        'requests': items,
        'status_counts': status_counts
    }

def get_leave_request_by_id(request_id):
    """Retrieves single leave request by request_id, id or _id."""
    db = get_db()
    q = {'$or': [
        {'request_id': str(request_id)},
        {'id': int(request_id) if str(request_id).isdigit() else str(request_id)},
        {'id': str(request_id)},
        build_id_filter(request_id)
    ]}
    doc = db.leave_requests.find_one(q)
    return clean_doc(doc) if doc else None

def update_leave_request_status(request_id, new_status, admin_remark=None, reviewer=None):
    """
    Approves or Rejects a leave request and updates employee leave balance.
    """
    db = get_db()
    q = {'$or': [
        {'request_id': str(request_id)},
        {'id': int(request_id) if str(request_id).isdigit() else str(request_id)},
        {'id': str(request_id)},
        build_id_filter(request_id)
    ]}
    req = db.leave_requests.find_one(q)
    if not req:
        return {'success': False, 'error': 'Leave request not found'}

    # Normalize status string
    status_str = str(new_status).strip()
    if status_str.lower() in ['approve', 'approved']:
        normalized_status = 'Approved'
    elif status_str.lower() in ['reject', 'rejected']:
        normalized_status = 'Rejected'
    else:
        normalized_status = status_str

    old_status = req.get('status', 'Pending')
    if old_status == normalized_status:
        return {'success': True, 'message': f'Status is already {normalized_status}'}

    emp_id = req.get('employee_id')
    comp_id = req.get('company_id')
    now_ist = get_ist_now()
    year = now_ist.year

    # Balance deduction or restoration
    if normalized_status == 'Approved' and old_status != 'Approved':
        bal = get_employee_leave_balance(emp_id, company_id=comp_id, year=year)
        if req.get('request_type') == 'Leave':
            lt = (req.get('leave_type') or '').lower()
            days = float(req.get('total_days', req.get('days_count', 1.0)))
            if 'casual' in lt:
                cat = 'casual_leave'
            elif 'sick' in lt:
                cat = 'sick_leave'
            elif 'earned' in lt:
                cat = 'earned_leave'
            else:
                cat = 'casual_leave'
            
            cur = bal.get(cat, {})
            u = cur.get('used', 0) + days
            t = cur.get('total', 12)
            a = max(0, t - u)
            db.leave_balances.update_one(
                {'employee_id': str(emp_id), 'year': year},
                {'$set': {f"{cat}.used": u, f"{cat}.available": a, 'updated_at': now_ist}}
            )
        elif req.get('request_type') == 'Permission':
            dur = float(req.get('duration_hours', req.get('hours_count', 2.0)))
            cur = bal.get('permission_hours', {})
            u = round(cur.get('used', 0.0) + dur, 2)
            t = cur.get('total', 16.0)
            a = max(0.0, t - u)
            db.leave_balances.update_one(
                {'employee_id': str(emp_id), 'year': year},
                {'$set': {'permission_hours.used': u, 'permission_hours.available': a, 'updated_at': now_ist}}
            )

        # Also deduct from custom_leaves if present
        if bal and bal.get('custom_leaves'):
            c_leaves = bal.get('custom_leaves', [])
            req_lt = str(req.get('leave_type') or req.get('request_type') or '').strip().lower()
            amount = float(req.get('duration_hours') or req.get('hours_count') or req.get('total_days') or req.get('days_count') or 1.0)
            custom_updated = False
            for cl in c_leaves:
                cl_name = str(cl.get('name') or '').strip().lower()
                if cl_name and (cl_name in req_lt or req_lt in cl_name):
                    u = round(float(cl.get('used', 0.0)) + amount, 2)
                    t = float(cl.get('total', 0.0))
                    a = max(0.0, round(t - u, 2))
                    cl['used'] = int(u) if u.is_integer() else u
                    cl['available'] = int(a) if a.is_integer() else a
                    custom_updated = True
                    break
            if custom_updated:
                db.leave_balances.update_one(
                    {'_id': bal['_id']},
                    {'$set': {'custom_leaves': c_leaves, 'updated_at': now_ist}}
                )

    elif old_status == 'Approved' and normalized_status in ['Rejected', 'Pending']:
        bal = get_employee_leave_balance(emp_id, company_id=comp_id, year=year)
        if req.get('request_type') == 'Leave':
            lt = (req.get('leave_type') or '').lower()
            days = float(req.get('total_days', req.get('days_count', 1.0)))
            if 'casual' in lt:
                cat = 'casual_leave'
            elif 'sick' in lt:
                cat = 'sick_leave'
            elif 'earned' in lt:
                cat = 'earned_leave'
            else:
                cat = 'casual_leave'
            
            cur = bal.get(cat, {})
            u = max(0, cur.get('used', 0) - days)
            t = cur.get('total', 12)
            a = max(0, t - u)
            db.leave_balances.update_one(
                {'employee_id': str(emp_id), 'year': year},
                {'$set': {f"{cat}.used": u, f"{cat}.available": a, 'updated_at': now_ist}}
            )
        elif req.get('request_type') == 'Permission':
            dur = float(req.get('duration_hours', req.get('hours_count', 2.0)))
            cur = bal.get('permission_hours', {})
            u = max(0.0, round(cur.get('used', 0.0) - dur, 2))
            t = cur.get('total', 16.0)
            a = max(0.0, t - u)
            db.leave_balances.update_one(
                {'employee_id': str(emp_id), 'year': year},
                {'$set': {'permission_hours.used': u, 'permission_hours.available': a, 'updated_at': now_ist}}
            )

        # Also restore to custom_leaves if present
        if bal and bal.get('custom_leaves'):
            c_leaves = bal.get('custom_leaves', [])
            req_lt = str(req.get('leave_type') or req.get('request_type') or '').strip().lower()
            amount = float(req.get('duration_hours') or req.get('hours_count') or req.get('total_days') or req.get('days_count') or 1.0)
            custom_updated = False
            for cl in c_leaves:
                cl_name = str(cl.get('name') or '').strip().lower()
                if cl_name and (cl_name in req_lt or req_lt in cl_name):
                    u = max(0.0, round(float(cl.get('used', 0.0)) - amount, 2))
                    t = float(cl.get('total', 0.0))
                    a = max(0.0, round(t - u, 2))
                    cl['used'] = int(u) if u.is_integer() else u
                    cl['available'] = int(a) if a.is_integer() else a
                    custom_updated = True
                    break
            if custom_updated:
                db.leave_balances.update_one(
                    {'_id': bal['_id']},
                    {'$set': {'custom_leaves': c_leaves, 'updated_at': now_ist}}
                )

    upd = {
        'status': normalized_status,
        'admin_remark': admin_remark if admin_remark is not None else req.get('admin_remark'),
        'reviewed_by': reviewer or 'System Administrator',
        'reviewed_at': now_ist.strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': now_ist
    }
    db.leave_requests.update_one(q, {'$set': upd})
    return {'success': True, 'status': normalized_status, 'message': f'Request {normalized_status} successfully'}

def get_admin_leave_stats(company_id=None, branch_id=None):
    """Returns the 4 KPI card metrics shown in Image 4."""
    db = get_db()
    query = {}
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)

    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    if b_id:
        b_emp_names, b_emp_ids = get_cached_branch_names_and_ids(b_id, company_id)
        branch_cond = get_branch_leave_condition(b_id, b_emp_ids, b_emp_names)
        if branch_cond:
            query.setdefault('$and', []).append(branch_cond)

    today_str = get_ist_now().strftime('%Y-%m-%d')

    pending_count = db.leave_requests.count_documents({**query, 'status': 'Pending'})
    approved_today = db.leave_requests.count_documents({
        **query,
        'status': 'Approved',
        'reviewed_at': {'$regex': f"^{today_str}"}
    })
    rejected_count = db.leave_requests.count_documents({**query, 'status': 'Rejected'})

    all_bals = get_all_employees_leave_balances(company_id=company_id, branch_id=b_id)
    low_balance_count = sum(1 for b in all_bals if b.get('is_low_balance'))

    return {
        'pending_requests': pending_count,
        'pending_count': pending_count,
        'approved_today': approved_today,
        'approved_count': approved_today,
        'rejected': rejected_count,
        'rejected_count': rejected_count,
        'low_balance_employees': low_balance_count,
        'low_balance_count': low_balance_count
    }

def get_approved_leaves_for_date(date_str, company_id=None):
    """
    Returns a dictionary of employees who have approved leave covering date_str (YYYY-MM-DD).
    Key: employee_name (and employee_id), Value: leave doc.
    """
    db = get_db()
    q = {
        'request_type': 'Leave',
        'status': 'Approved',
        'from_date': {'$lte': date_str},
        'to_date': {'$gte': date_str}
    }
    if company_id and company_id != 'ALL':
        q['company_id'] = str(company_id)

    leaves = list(db.leave_requests.find(q))
    result = {}
    for l in leaves:
        cd = clean_doc(l)
        if l.get('employee_name'):
            result[l['employee_name']] = cd
        if l.get('employee_id'):
            result[str(l['employee_id'])] = cd
    return result

def get_approved_permissions_for_date(date_str, company_id=None):
    """
    Returns a dictionary of employees who have approved permission on date_str (YYYY-MM-DD).
    """
    db = get_db()
    q = {
        'request_type': 'Permission',
        'status': 'Approved',
        'from_date': date_str
    }
    if company_id and company_id != 'ALL':
        q['company_id'] = str(company_id)

    perms = list(db.leave_requests.find(q))
    result = {}
    for p in perms:
        cd = clean_doc(p)
        if p.get('employee_name'):
            result[p['employee_name']] = cd
        if p.get('employee_id'):
            result[str(p['employee_id'])] = cd
    return result

_badge_counts_cache = {}
_badge_counts_ttl = 20  # seconds

def invalidate_badge_counts_cache(company_id=None):
    global _badge_counts_cache
    if company_id:
        _badge_counts_cache.pop(f"leave:{company_id}", None)
        _badge_counts_cache.pop(f"support:{company_id}", None)
        _badge_counts_cache.pop("leave:ALL", None)
        _badge_counts_cache.pop("support:ALL", None)
    else:
        _badge_counts_cache.clear()

def get_pending_leave_requests_count(company_id=None, branch_id=None):
    """
    Returns the count of Pending leave & permission requests with 20s TTL caching.
    """
    b_id = str(branch_id).strip() if branch_id and str(branch_id).strip().upper() not in ['ALL', 'NONE', '', 'NULL'] else None
    key = f"leave:{company_id or 'ALL'}:{b_id or 'ALL'}"
    now_ts = time.time()
    if key in _badge_counts_cache:
        t, val = _badge_counts_cache[key]
        if now_ts - t < _badge_counts_ttl:
            return val
    db = get_db()
    query = {'status': 'Pending'}
    if company_id and str(company_id) not in ['ALL', 'ARGUS_MASTER', 'DEFAULT']:
        query['company_id'] = str(company_id)
    if b_id:
        b_emp_names, b_emp_ids = get_cached_branch_names_and_ids(b_id, company_id)
        branch_cond = get_branch_leave_condition(b_id, b_emp_ids, b_emp_names)
        if branch_cond:
            query.setdefault('$and', []).append(branch_cond)
    cnt = db.leave_requests.count_documents(query)
    _badge_counts_cache[key] = (now_ts, cnt)
    return cnt

def delete_employee_leave_request(request_id, emp_id=None):
    """
    Deletes a leave or permission request submitted by an employee.
    Enforces that status must be 'Pending'. If Approved or Rejected, deletion is blocked.
    """
    db = get_db()
    q = {'$or': [
        {'request_id': str(request_id)},
        {'id': int(request_id) if str(request_id).isdigit() else str(request_id)},
        {'id': str(request_id)},
        build_id_filter(request_id)
    ]}
    req = db.leave_requests.find_one(q)
    if not req:
        return {'success': False, 'error': 'Request not found'}

    # Verify ownership if emp_id provided
    if emp_id:
        req_emp = str(req.get('employee_id', ''))
        req_code = str(req.get('employee_code', ''))
        if str(emp_id) not in [req_emp, req_code]:
            return {'success': False, 'error': 'Unauthorized: You can only delete your own requests'}

    st = str(req.get('status', 'Pending')).strip().lower()
    if st != 'pending':
        return {'success': False, 'error': f'Cannot delete request that has already been {req.get("status")}'}

    db.leave_requests.delete_one({'_id': req['_id']})
    return {'success': True, 'message': 'Request deleted successfully'}

def edit_employee_leave_request(request_id, emp_id, updated_fields):
    """
    Updates a leave or permission request submitted by an employee.
    Enforces that status must be 'Pending'. If Approved or Rejected, editing is blocked.
    """
    db = get_db()
    q = {'$or': [
        {'request_id': str(request_id)},
        {'id': int(request_id) if str(request_id).isdigit() else str(request_id)},
        {'id': str(request_id)},
        build_id_filter(request_id)
    ]}
    req = db.leave_requests.find_one(q)
    if not req:
        return {'success': False, 'error': 'Request not found'}

    # Verify ownership if emp_id provided
    if emp_id:
        req_emp = str(req.get('employee_id', ''))
        req_code = str(req.get('employee_code', ''))
        if str(emp_id) not in [req_emp, req_code]:
            return {'success': False, 'error': 'Unauthorized: You can only edit your own requests'}

    st = str(req.get('status', 'Pending')).strip().lower()
    if st != 'pending':
        return {'success': False, 'error': f'Cannot edit request that has already been {req.get("status")}'}

    updated_fields['updated_at'] = get_ist_now()
    db.leave_requests.update_one({'_id': req['_id']}, {'$set': updated_fields})
    updated_doc = db.leave_requests.find_one({'_id': req['_id']})
    return {'success': True, 'message': 'Request updated successfully', 'request': clean_doc(updated_doc)}


# =========================================================================
# SUPPORT TICKETS & DEMO VIDEOS SYSTEM
# =========================================================================

DEFAULT_DEMO_VIDEOS = [
    {
        'chapter': 1,
        'title': '1. Employee Details',
        'duration': '08:24',
        'duration_seconds': 504,
        'subtitle': 'Learn how to add, edit and manage employee records.',
        'description': 'In this video, you will learn how to manage employee details in ARGUS Attendance. This includes adding new employees, editing existing records, setting designations, updating phone numbers, activating or deactivating employees, and more.',
        'what_you_will_learn': [
            'Add a new employee',
            'Edit employee details',
            'Set designation and department',
            'Update phone number and join date',
            'Activate or deactivate employee',
            'Manage employee records efficiently'
        ],
        'video_url': '/static/videos/demo_employee_details.mp4',
        'poster_url': '/static/images/demo_thumb_1.jpg'
    },
    {
        'chapter': 2,
        'title': '2. Live Report',
        'duration': '06:15',
        'duration_seconds': 375,
        'subtitle': 'View and understand live attendance data.',
        'description': 'In this video, you will learn how to monitor real-time facial check-ins, detect improper geofence punches, verify on-duty staffing levels, and review live entry and exit records as they happen throughout the work shift.',
        'what_you_will_learn': [
            'Monitor live attendance feeds in real time',
            'Filter attendance by department and shifts',
            'Detect and audit improper or remote location punches',
            'Verify check-in timestamps and facial match logs',
            'Track on-duty staffing numbers across branches'
        ],
        'video_url': '/static/videos/demo_live_report.mp4',
        'poster_url': '/static/images/demo_thumb_2.jpg'
    },
    {
        'chapter': 3,
        'title': '3. Attendance Report',
        'duration': '07:30',
        'duration_seconds': 450,
        'subtitle': 'Generate and export attendance reports.',
        'description': 'Master the comprehensive attendance reporting suite. Learn how to filter punch histories by custom date ranges, audit daily presence vs absences, review shift variances, and export reports in PDF and Excel formats.',
        'what_you_will_learn': [
            'Generate custom date range attendance reports',
            'Analyze punch variance, late arrivals, and early departures',
            'Audit working hours and shift compliance',
            'Export formatted attendance registers to Excel and PDF',
            'Review organization-wide attendance trends'
        ],
        'video_url': '/static/videos/demo_attendance_report.mp4',
        'poster_url': '/static/images/demo_thumb_3.jpg'
    },
    {
        'chapter': 4,
        'title': '4. Manual Entry',
        'duration': '05:48',
        'duration_seconds': 348,
        'subtitle': 'Add or update attendance manually.',
        'description': 'Discover when and how to record manual attendance entries for forgotten punches, off-site client visits, hardware maintenance, or special time adjustments while maintaining audit integrity and manager accountability.',
        'what_you_will_learn': [
            'Create manual check-in and check-out records',
            'Configure Add or Deduct entry types',
            'Calculate manual working hours and pro-rated salary',
            'Provide mandatory audit reasons and remarks',
            'Track and audit all manual entry submissions'
        ],
        'video_url': '/static/videos/demo_manual_entry.mp4',
        'poster_url': '/static/images/demo_thumb_4.jpg'
    },
    {
        'chapter': 5,
        'title': '5. Payment Entry',
        'duration': '08:10',
        'duration_seconds': 490,
        'subtitle': 'Record and manage payment entries.',
        'description': 'Understand how to record employee salary advances, manage emergency loans, log installment repayments, and maintain real-time employee advance balance tracking integrated with monthly payroll.',
        'what_you_will_learn': [
            'Record salary advance disbursements',
            'Log repayment installments and adjustments',
            'Track live outstanding advance balances per employee',
            'Verify automatic payslip deduction linking',
            'Download transaction receipts and payment histories'
        ],
        'video_url': '/static/videos/demo_payment_entry.mp4',
        'poster_url': '/static/images/demo_thumb_5.jpg'
    },
    {
        'chapter': 6,
        'title': '6. Payslip Preview',
        'duration': '06:52',
        'duration_seconds': 412,
        'subtitle': 'View and preview employee payslips.',
        'description': 'A complete walkthrough of the payslip preview engine. Learn how working days, paid leaves, statutory deductions, incentives, advance repayments, and net pay are calculated and previewed before final payroll closure.',
        'what_you_will_learn': [
            'Preview individual monthly payslips',
            'Inspect earnings breakdown: basic, allowances, incentives',
            'Verify advance deduction and leave deductions',
            'Review net pay calculations and numbers in words',
            'Generate and download pixel-perfect payslip PDFs'
        ],
        'video_url': '/static/videos/demo_payslip_preview.mp4',
        'poster_url': '/static/images/demo_thumb_6.jpg'
    },
    {
        'chapter': 7,
        'title': '7. Salary Report',
        'duration': '07:18',
        'duration_seconds': 438,
        'subtitle': 'Generate salary reports for your organization.',
        'description': 'Learn how to generate organization-wide monthly payroll summaries, audit departmental wage expenditures, review bank payment sheets, and lock finalized payroll batches for executive sign-off.',
        'what_you_will_learn': [
            'Compile organization-wide monthly payroll sheets',
            'Review total payouts, deductions, and advance summaries',
            'Filter payroll reports by department and designation',
            'Export comprehensive payroll sheets to Excel and PDF',
            'Finalize and lock monthly payroll reports'
        ],
        'video_url': '/static/videos/demo_salary_report.mp4',
        'poster_url': '/static/images/demo_thumb_7.jpg'
    },
    {
        'chapter': 8,
        'title': '8. Company Profile',
        'duration': '04:36',
        'duration_seconds': 276,
        'subtitle': 'Manage your company information and settings.',
        'description': 'Configure company profile essentials: upload company branding logo, setup GPS office geofence coordinates and radius, define official work shifts and grace limits, and configure automated report emails.',
        'what_you_will_learn': [
            'Upload and update company logo branding',
            'Configure office GPS geofence latitude, longitude, and radius',
            'Setup standard work shifts and grace periods',
            'Manage contact credentials and company GST details',
            'Enable or customize automated daily and monthly report emails'
        ],
        'video_url': '/static/videos/demo_company_profile.mp4',
        'poster_url': '/static/images/demo_thumb_8.jpg'
    }
]

def seed_demo_videos_if_needed():
    """Seeds the 8 demo video chapters into db.demo_videos if empty."""
    db = get_db()
    if db.demo_videos.count_documents({}) == 0:
        for v in DEFAULT_DEMO_VIDEOS:
            doc = dict(v)
            doc['created_at'] = get_ist_now().isoformat()
            db.demo_videos.insert_one(doc)

def get_demo_videos():
    """Returns all demo video chapters sorted by chapter number."""
    db = get_db()
    seed_demo_videos_if_needed()
    videos = list(db.demo_videos.find({}).sort('chapter', ASCENDING))
    return [clean_doc(v) for v in videos]

def generate_support_ticket_id():
    """Generates sequential support ticket ID e.g. SUP-000101, SUP-000102."""
    db = get_db()
    last = db.support_tickets.find_one({}, sort=[('ticket_id', DESCENDING)])
    if last and last.get('ticket_id'):
        try:
            num = int(str(last['ticket_id']).split('-')[-1])
            return f"SUP-{num + 1:06d}"
        except Exception:
            pass
    cnt = db.support_tickets.count_documents({})
    return f"SUP-{cnt + 101:06d}"

def create_support_ticket(company_id, company_name, raised_by, subject, description, attachments=None, role='company_admin'):
    """
    Creates a new support ticket and logs the initial message in conversation history.
    """
    db = get_db()
    now_ist = get_ist_now()
    ticket_id = generate_support_ticket_id()
    clean_atts = attachments or []

    initial_msg = {
        'id': f"msg_{int(time.time()*1000)}",
        'sender_name': raised_by or 'Company User',
        'sender_role': role,
        'sender_avatar': (raised_by[:1].upper() if raised_by else 'A'),
        'avatar_bg': '#ef4444' if role == 'company_admin' else '#8b5cf6',
        'message': description.strip(),
        'badge': 'Ticket Raised',
        'attachments': clean_atts,
        'created_at': now_ist.isoformat(),
        'created_at_display': now_ist.strftime('%d/%m/%Y %I:%M %p')
    }

    doc = {
        'ticket_id': ticket_id,
        'company_id': str(company_id),
        'company_name': company_name,
        'raised_by': raised_by,
        'raised_by_role': role,
        'date_time_str': now_ist.strftime('%d/%m/%Y %I:%M %p'),
        'subject': subject.strip(),
        'description': description.strip(),
        'status': 'Open',
        'priority': 'Medium',
        'attachments': clean_atts,
        'messages': [initial_msg],
        'created_at': now_ist,
        'updated_at': now_ist,
        'resolved_at': None
    }

    db.support_tickets.insert_one(doc)
    return clean_doc(doc)

def get_company_support_tickets(company_id, status=None, search=None, page=1, limit=10):
    """
    Returns support tickets for a specific company with status filtering, search, and pagination.
    """
    db = get_db()
    comp_id_str = str(company_id)
    base_filter = {'company_id': comp_id_str}

    # Live tab counts for this company
    all_count = db.support_tickets.count_documents(base_filter)
    open_count = db.support_tickets.count_documents({**base_filter, 'status': 'Open'})
    in_progress_count = db.support_tickets.count_documents({**base_filter, 'status': 'In Progress'})
    resolved_count = db.support_tickets.count_documents({**base_filter, 'status': 'Resolved'})
    closed_count = db.support_tickets.count_documents({**base_filter, 'status': 'Closed'})

    counts = {
        'all': all_count,
        'open': open_count,
        'in_progress': in_progress_count,
        'resolved': resolved_count,
        'closed': closed_count
    }

    query = dict(base_filter)
    if status and str(status).lower() != 'all':
        query['status'] = {'$regex': f"^{re.escape(status)}$", '$options': 'i'}

    if search and str(search).strip():
        s_regex = {'$regex': re.escape(str(search).strip()), '$options': 'i'}
        query['$or'] = [
            {'ticket_id': s_regex},
            {'subject': s_regex},
            {'description': s_regex},
            {'raised_by': s_regex}
        ]

    total_filtered = db.support_tickets.count_documents(query)
    skip = max(0, (page - 1) * limit)
    cursor = db.support_tickets.find(query).sort('created_at', DESCENDING).skip(skip).limit(limit)
    tickets = [clean_doc(t) for t in cursor]

    return {
        'tickets': tickets,
        'total': total_filtered,
        'counts': counts,
        'page': page,
        'limit': limit
    }

def get_all_support_tickets(company_filter=None, status_filter=None, search=None, page=1, limit=10):
    """
    Returns support tickets across ALL companies for Super Admin with multi-tenant filtering.
    """
    db = get_db()
    all_count = db.support_tickets.count_documents({})
    open_count = db.support_tickets.count_documents({'status': 'Open'})
    in_progress_count = db.support_tickets.count_documents({'status': 'In Progress'})
    resolved_count = db.support_tickets.count_documents({'status': 'Resolved'})
    closed_count = db.support_tickets.count_documents({'status': 'Closed'})

    counts = {
        'all': all_count,
        'open': open_count,
        'in_progress': in_progress_count,
        'resolved': resolved_count,
        'closed': closed_count
    }

    query = {}
    if company_filter and str(company_filter).lower() not in ['all', 'all companies', '']:
        query['$or'] = [
            {'company_id': str(company_filter)},
            {'company_name': str(company_filter)}
        ]

    if status_filter and str(status_filter).lower() not in ['all', 'all status', '']:
        query['status'] = {'$regex': f"^{re.escape(status_filter)}$", '$options': 'i'}

    if search and str(search).strip():
        s_regex = {'$regex': re.escape(str(search).strip()), '$options': 'i'}
        search_or = [
            {'ticket_id': s_regex},
            {'company_name': s_regex},
            {'subject': s_regex},
            {'description': s_regex},
            {'raised_by': s_regex}
        ]
        if '$or' in query:
            query = {'$and': [query, {'$or': search_or}]}
        else:
            query['$or'] = search_or

    total_filtered = db.support_tickets.count_documents(query)
    skip = max(0, (page - 1) * limit)
    cursor = db.support_tickets.find(query).sort('created_at', DESCENDING).skip(skip).limit(limit)
    tickets = [clean_doc(t) for t in cursor]

    companies_cursor = db.company_admin.find({}, {'id': 1, 'company_name': 1})
    companies_list = [{'id': c.get('id'), 'company_name': c.get('company_name', 'Company')} for c in companies_cursor]

    return {
        'tickets': tickets,
        'total': total_filtered,
        'counts': counts,
        'companies': companies_list,
        'page': page,
        'limit': limit
    }

def get_support_ticket_by_id(ticket_id, company_id=None):
    """
    Returns single ticket with complete attachments and conversation messages.
    """
    db = get_db()
    t_id_str = str(ticket_id).strip()
    q = {'$or': [
        {'ticket_id': t_id_str},
        {'ticket_id': t_id_str.upper()}
    ]}
    if ObjectId.is_valid(t_id_str):
        q['$or'].append({'_id': ObjectId(t_id_str)})

    ticket = db.support_tickets.find_one(q)
    if not ticket:
        return None

    if company_id and company_id not in ['ALL', 'ARGUS_MASTER']:
        if str(ticket.get('company_id')) != str(company_id):
            return None

    return clean_doc(ticket)

def add_support_ticket_message(ticket_id, sender_name, sender_role, message_text, attachments=None, new_status=None, badge=None, company_id=None):
    """
    Adds a new message/reply into ticket's conversation thread and optionally updates status.
    """
    db = get_db()
    ticket = get_support_ticket_by_id(ticket_id, company_id=company_id)
    if not ticket:
        return {'success': False, 'error': 'Ticket not found or unauthorized'}

    now_ist = get_ist_now()
    clean_atts = attachments or []

    avatar_letter = (sender_name[:1].upper() if sender_name else 'U')
    avatar_bg = '#8b5cf6' if sender_role == 'super_admin' else '#ef4444'

    new_msg = {
        'id': f"msg_{int(time.time()*1000)}",
        'sender_name': sender_name,
        'sender_role': sender_role,
        'sender_avatar': avatar_letter,
        'avatar_bg': avatar_bg,
        'message': str(message_text).strip(),
        'badge': badge,
        'attachments': clean_atts,
        'created_at': now_ist.isoformat(),
        'created_at_display': now_ist.strftime('%d/%m/%Y %I:%M %p')
    }

    update_fields = {
        'updated_at': now_ist
    }

    push_data = {'messages': new_msg}
    if clean_atts:
        push_data['attachments'] = {'$each': clean_atts}

    if new_status:
        update_fields['status'] = new_status
        if new_status.lower() == 'resolved':
            update_fields['resolved_at'] = now_ist
        elif new_status.lower() in ['open', 'in progress']:
            update_fields['resolved_at'] = None

    db.support_tickets.update_one(
        {'ticket_id': ticket['ticket_id']},
        {
            '$push': push_data,
            '$set': update_fields
        }
    )

    updated_ticket = db.support_tickets.find_one({'ticket_id': ticket['ticket_id']})
    return {'success': True, 'ticket': clean_doc(updated_ticket), 'message': new_msg}

def update_support_ticket_status(ticket_id, new_status, updated_by_name, updated_by_role, remark=None, company_id=None):
    """
    Updates the status of a ticket (Open, In Progress, Resolved, Closed).
    """
    db = get_db()
    ticket = get_support_ticket_by_id(ticket_id, company_id=company_id)
    if not ticket:
        return {'success': False, 'error': 'Ticket not found or unauthorized'}

    now_ist = get_ist_now()
    old_status = ticket.get('status', 'Open')
    status_clean = str(new_status).strip().title()
    if status_clean.lower() == 'in progress':
        status_clean = 'In Progress'

    update_fields = {
        'status': status_clean,
        'updated_at': now_ist
    }
    if status_clean == 'Resolved':
        update_fields['resolved_at'] = now_ist
    elif status_clean in ['Open', 'In Progress']:
        update_fields['resolved_at'] = None

    badge = status_clean if status_clean in ['In Progress', 'Resolved', 'Closed'] else None
    audit_text = remark or f"Ticket status changed from {old_status} to {status_clean}."
    status_msg = {
        'id': f"msg_{int(time.time()*1000)}",
        'sender_name': updated_by_name,
        'sender_role': updated_by_role,
        'sender_avatar': updated_by_name[:1].upper() if updated_by_name else 'S',
        'avatar_bg': '#8b5cf6' if updated_by_role == 'super_admin' else '#ef4444',
        'message': audit_text,
        'badge': badge,
        'attachments': [],
        'created_at': now_ist.isoformat(),
        'created_at_display': now_ist.strftime('%d/%m/%Y %I:%M %p')
    }

    db.support_tickets.update_one(
        {'ticket_id': ticket['ticket_id']},
        {
            '$set': update_fields,
            '$push': {'messages': status_msg}
        }
    )

    updated_ticket = db.support_tickets.find_one({'ticket_id': ticket['ticket_id']})
    return {'success': True, 'ticket': clean_doc(updated_ticket)}

def get_support_badge_count(company_id=None):
    """
    Returns un-resolved ticket count for sidebar badge with 20s TTL caching.
    """
    key = f"support:{company_id or 'ALL'}"
    now_ts = time.time()
    if key in _badge_counts_cache:
        t, val = _badge_counts_cache[key]
        if now_ts - t < _badge_counts_ttl:
            return val
    db = get_db()
    q = {'status': {'$in': ['Open', 'In Progress']}}
    if company_id and company_id not in ['ALL', 'ARGUS_MASTER']:
        q['company_id'] = str(company_id)
    cnt = db.support_tickets.count_documents(q)
    _badge_counts_cache[key] = (now_ts, cnt)
    return cnt


# ==============================================================================
# FIELD WORKER MODULE - REGISTRATION, ASSIGNMENTS, LIVE TRACKING, LEADS & SALARY
# ==============================================================================

def get_field_workers(company_id=None, include_all_employees=False):
    """
    Returns field workers for a company. If include_all_employees is True, returns
    all company employees with their field worker attributes so admins can also
    assign or promote existing employees.
    """
    db = get_db()
    q = {}
    if company_id and company_id != 'ALL':
        q['company_id'] = str(company_id)

    all_emps = [clean_doc(e) for e in db.employees.find(q, {'photo_data': 0, 'face_embedding': 0, 'documents': 0}).sort('employee_name', ASCENDING)]
    field_workers = []
    any_explicit_fw = any(e.get('is_field_worker') is True for e in all_emps)
    for emp in all_emps:
        if emp.get('is_field_worker') is not None:
            is_fw = bool(emp.get('is_field_worker'))
        else:
            dept = str(emp.get('department') or '').lower()
            desig = str(emp.get('designation') or '').lower()
            is_fw = any(k in dept or k in desig for k in ['field', 'sales', 'marketing', 'delivery', 'visit'])
        emp['is_field_worker'] = is_fw
        emp['territory_zone'] = str(emp.get('territory_zone') or 'General Zone')
        emp['per_visit_incentive'] = round(safe_float(emp.get('per_visit_incentive', 0.0)), 2)
        emp['km_allowance_rate'] = round(safe_float(emp.get('km_allowance_rate', 0.0)), 2)
        if include_all_employees or is_fw:
            field_workers.append(emp)

    # If no employee is tagged yet and include_all_employees is False, return all active employees so UI isn't empty on first launch
    if not field_workers and all_emps and not include_all_employees and not any_explicit_fw:
        return all_emps
    return field_workers


def create_field_assignment(data, company_id=None):
    """Assigns a target customer/company location and task to a field worker."""
    db = get_db()
    assigned_company_id = str(company_id or data.get('company_id') or 'ARGUS_MASTER')
    emp_name = str(data.get('employee_name') or '').strip()
    target_name = str(data.get('target_name') or '').strip()
    if not emp_name:
        raise ValueError("Field worker name is required.")
    if not target_name:
        raise ValueError("Target customer / location name is required.")

    now_ist = get_ist_now()
    assignment_id = str(data.get('id') or f"FA-{int(time.time() * 1000)}")
    target_lat = round(safe_float(data.get('target_lat') if data.get('target_lat') is not None else data.get('target_latitude'), 11.0168), 6)
    target_lng = round(safe_float(data.get('target_lng') if data.get('target_lng') is not None else data.get('target_longitude'), 76.9558), 6)
    geofence_radius = max(30.0, round(safe_float(data.get('geofence_radius'), 150.0), 1))
    target_address = str(data.get('target_address') or '').strip()
    if not target_address and target_lat and target_lng:
        try:
            target_address = reverse_geocode_coordinates(target_lat, target_lng)
        except Exception:
            target_address = f"{target_lat}, {target_lng}"

    doc = {
        'id': assignment_id,
        'company_id': assigned_company_id,
        'employee_id': str(data.get('employee_id') or '').strip(),
        'employee_name': emp_name,
        'target_name': target_name,
        'contact_person': str(data.get('contact_person') or '').strip(),
        'contact_phone': str(data.get('contact_phone') or '').strip(),
        'target_address': target_address,
        'target_lat': target_lat,
        'target_lng': target_lng,
        'geofence_radius': geofence_radius,
        'assigned_date': str(data.get('assigned_date') or now_ist.strftime('%Y-%m-%d')).strip(),
        'time_window': str(data.get('time_window') or '09:00 AM - 06:00 PM').strip(),
        'task_purpose': str(data.get('task_purpose') or 'Product Sales & Pitch').strip(),
        'priority': str(data.get('priority') or 'High').strip(),
        'notes': str(data.get('notes') or '').strip(),
        'status': str(data.get('status') or 'Pending').strip(),
        'verified_at': None,
        'created_at': now_ist,
        'updated_at': now_ist
    }
    db.field_assignments.insert_one(doc)
    return clean_doc(doc)


def get_field_assignments(company_id=None, employee_name=None, date_str=None, status=None):
    """Fetches assigned field locations filtered by company, worker, date, or status."""
    db = get_db()
    q = {}
    if company_id and company_id != 'ALL':
        q['company_id'] = str(company_id)
    if employee_name:
        q['employee_name'] = str(employee_name).strip()
    if date_str:
        q['assigned_date'] = str(date_str).strip()
    if status:
        q['status'] = str(status).strip()

    docs = list(db.field_assignments.find(q).sort([('assigned_date', DESCENDING), ('created_at', DESCENDING)]))
    return [clean_doc(d) for d in docs]


def update_field_assignment(assignment_id, data, company_id=None):
    """Updates an existing field assignment status or details."""
    db = get_db()
    q = build_id_filter(assignment_id)
    if company_id and company_id != 'ALL':
        q = {'$and': [q, {'company_id': str(company_id)}]}

    upd = {'updated_at': get_ist_now()}
    for k in ['target_name', 'contact_person', 'contact_phone', 'target_address', 'assigned_date', 'time_window', 'task_purpose', 'priority', 'notes', 'status']:
        if k in data and data[k] is not None:
            upd[k] = str(data[k]).strip()
    for num_k in ['target_lat', 'target_lng', 'geofence_radius']:
        if num_k in data and data[num_k] is not None:
            upd[num_k] = float(data[num_k])
    if upd.get('status') == 'Completed':
        upd['verified_at'] = get_ist_now().strftime('%d/%m/%Y %I:%M %p')

    res = db.field_assignments.update_one(q, {'$set': upd})
    return res.matched_count > 0


def delete_field_assignment(assignment_id, company_id=None):
    """Deletes a field location assignment."""
    db = get_db()
    q = build_id_filter(assignment_id)
    if company_id and company_id != 'ALL':
        q = {'$and': [q, {'company_id': str(company_id)}]}
    res = db.field_assignments.delete_one(q)
    return res.deleted_count > 0



def evaluate_field_worker_anomaly(emp_name, lat, lng, address, nearest_target_name, detour_distance_m, dwell_minutes, activity_note='', company_id=None):
    """
    Evaluates a field worker GPS anomaly using Google Gemini 1.5 Flash (if API key configured)
    with a deterministic Heuristic AI Expert System fallback.
    Returns structured incident assessment dict.
    """
    now_ist = get_ist_now()
    detour_km = round(max(0.0, float(detour_distance_m or 0.0) / 1000.0), 2)
    dwell_mins = max(1, int(dwell_minutes or 0))
    addr_lower = (address or '').lower()
    note_lower = (activity_note or '').lower()

    # Rule-Based Heuristic AI Evaluation (Guaranteed 100% Free & Zero External Latency)
    anomaly_category = "Off-Route Stationary Dwell"
    severity = "MEDIUM"

    if any(k in addr_lower or k in note_lower for k in ['mall', 'bazaar', 'market', 'shopping', 'retail', 'complex', 'store', 'hypermarket', 'mart', 'supermarket', 'clothing', 'textile']):
        anomaly_category = "Unauthorized Personal Shopping / Mall Detour"
        severity = "HIGH" if (dwell_mins >= 25 or detour_km >= 2.5) else "MEDIUM"
    elif any(k in addr_lower or k in note_lower for k in ['restaurant', 'cafe', 'hotel', 'bistro', 'coffee', 'dhaba', 'bar', 'juice', 'bakery', 'food court', 'tea', 'mess', 'biryani']):
        anomaly_category = "Unscheduled Dining / Refreshment Halt"
        severity = "HIGH" if dwell_mins >= 40 else ("MEDIUM" if dwell_mins >= 20 else "LOW")
    elif any(k in addr_lower or k in note_lower for k in ['cinema', 'theatre', 'theater', 'movie', 'multiplex', 'park', 'garden', 'resort', 'club', 'stadium', 'play']):
        anomaly_category = "Entertainment / Recreational Detour"
        severity = "HIGH"
    elif any(k in addr_lower or k in note_lower for k in ['residence', 'apartment', 'flat', 'nagar', 'colony', 'layout', 'villas', 'housing', 'house', 'gated community']):
        anomaly_category = "Suspected Personal / Residential Deviation"
        severity = "HIGH" if (dwell_mins >= 25 or detour_km >= 3.0) else "MEDIUM"
    elif any(k in addr_lower or k in note_lower for k in ['highway', 'bypass', 'toll', 'ring road', 'service road', 'fuel', 'petrol', 'pump']):
        anomaly_category = "Corridor Traffic / Stationary Transit Halt"
        severity = "MEDIUM" if dwell_mins >= 35 else "LOW"
    else:
        if dwell_mins >= 30 or detour_km >= 3.5:
            severity = "HIGH"
            anomaly_category = "Severe Off-Route Deviation & Extended Dwell"
        elif dwell_mins >= 15 or detour_km >= 1.5:
            severity = "MEDIUM"
            anomaly_category = "Unassigned Off-Route Stop"
        else:
            severity = "LOW"
            anomaly_category = "Minor Course Deviation"

    est_delay = dwell_mins + int(detour_km * 3) + 10
    clean_addr = address if address and 'Lat:' not in address else 'Unassigned Location'
    summary_text = f"Worker {emp_name} deviated {detour_km} km off-route from '{nearest_target_name}' and has been stationary at {clean_addr} for {dwell_mins} minutes during active duty."

    if severity == "HIGH":
        recommendation_text = f"Contact {emp_name} immediately to verify unauthorized halt and inform destination '{nearest_target_name}' of estimated ~{est_delay} mins delay."
    elif severity == "MEDIUM":
        recommendation_text = f"Monitor live radar for next 10 minutes. If worker remains stationary at {clean_addr}, dispatch phone inquiry."
    else:
        recommendation_text = f"Log telemetry alert. Worker expected to resume route toward '{nearest_target_name}' shortly."

    heuristic_result = {
        'is_unauthorized_detour': True,
        'severity': severity,
        'anomaly_type': anomaly_category,
        'summary': summary_text,
        'estimated_delay_mins': est_delay,
        'action_recommendation': recommendation_text,
        'model_used': 'Argus AI Heuristic Rules Engine'
    }

    # Attempt Google Gemini 1.5 Flash if API Key is configured in environment or settings
    api_key = os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        try:
            db = get_db()
            setting = db.system_settings.find_one({'key': 'gemini_api_key'})
            if setting and setting.get('value'):
                api_key = setting['value']
        except Exception:
            pass

    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = (
                f"You are an AI corporate field operations auditor monitoring mobile sales & service agents in real-time.\n"
                f"Analyze this field telemetry anomaly:\n"
                f"- Worker Name: {emp_name}\n"
                f"- Time: {now_ist.strftime('%I:%M %p, %d %b %Y')}\n"
                f"- Reverse-Geocoded Location: {clean_addr} (Lat: {lat}, Lng: {lng})\n"
                f"- Assigned Target Destination: {nearest_target_name}\n"
                f"- Distance Off-Route: {detour_km} km\n"
                f"- Stationary Dwell Time: {dwell_mins} minutes\n"
                f"- Device/Worker Note: {activity_note}\n\n"
                f"Evaluate if this is an unauthorized personal detour (e.g. shopping mall, cafe, cinema, home visit) vs acceptable transit.\n"
                f"Return ONLY valid JSON matching this schema:\n"
                f'{{"is_unauthorized_detour": true, "severity": "HIGH"|"MEDIUM"|"LOW", "anomaly_type": "string", '
                f'"summary": "concise 1-2 sentence executive explanation", "estimated_delay_mins": int, "action_recommendation": "actionable advice for company admin"}}'
            )
            response = model.generate_content(prompt)
            if response and response.text:
                raw = response.text.strip()
                if raw.startswith('```json'):
                    raw = raw[7:]
                if raw.startswith('```'):
                    raw = raw[3:]
                if raw.endswith('```'):
                    raw = raw[:-3]
                parsed = json.loads(raw.strip())
                if isinstance(parsed, dict) and 'severity' in parsed and 'summary' in parsed:
                    parsed['model_used'] = 'Google Gemini 1.5 Flash'
                    return parsed
        except Exception:
            pass

    return heuristic_result


def save_field_ai_incident(incident_data):
    """
    Saves or updates an AI incident in db.field_ai_incidents.
    De-duplicates active incidents for the same worker and location within 60 minutes.
    """
    db = get_db()
    now_ist = get_ist_now()
    emp_name = str(incident_data.get('employee_name') or '').strip()
    company_id = str(incident_data.get('company_id') or 'ARGUS_MASTER').strip()
    today_str = str(incident_data.get('date') or now_ist.strftime('%Y-%m-%d')).strip()
    lat = safe_float(incident_data.get('latitude'), 0.0)
    lng = safe_float(incident_data.get('longitude'), 0.0)

    # Check for existing active or acknowledged incident today for this worker
    existing = list(db.field_ai_incidents.find({
        'company_id': company_id,
        'employee_name': emp_name,
        'date': today_str,
        'status': {'$in': ['Active', 'Acknowledged']}
    }).sort('created_at', DESCENDING).limit(5))

    matched_existing = None
    for ex in existing:
        ex_lat = safe_float(ex.get('latitude'), 0.0)
        ex_lng = safe_float(ex.get('longitude'), 0.0)
        if ex_lat and ex_lng and lat and lng:
            dist = calculate_realistic_proximity(lat, lng, ex_lat, ex_lng)
            d_m = float(dist.get('geodesic_m', 9999.0)) if isinstance(dist, dict) else float(dist or 9999.0)
            if d_m <= 600.0:
                matched_existing = ex
                break

    if matched_existing:
        new_dwell = max(int(matched_existing.get('dwell_minutes', 0)), int(incident_data.get('dwell_minutes', 0)))
        upd = {
            'dwell_minutes': new_dwell,
            'detour_distance_km': round(safe_float(incident_data.get('detour_distance_km'), matched_existing.get('detour_distance_km', 0.0)), 2),
            'severity': incident_data.get('severity') or matched_existing.get('severity', 'HIGH'),
            'summary': incident_data.get('summary') or matched_existing.get('summary', ''),
            'action_recommendation': incident_data.get('action_recommendation') or matched_existing.get('action_recommendation', ''),
            'estimated_delay_mins': incident_data.get('estimated_delay_mins') or matched_existing.get('estimated_delay_mins', 30),
            'last_ping_time': now_ist.strftime('%I:%M %p'),
            'updated_at': now_ist
        }
        db.field_ai_incidents.update_one({'_id': matched_existing['_id']}, {'$set': upd})
        updated_doc = db.field_ai_incidents.find_one({'_id': matched_existing['_id']})
        return clean_doc(updated_doc)

    incident_doc = {
        'id': f"AI-INC-{int(time.time() * 1000)}",
        'company_id': company_id,
        'employee_id': str(incident_data.get('employee_id') or '').strip(),
        'employee_name': emp_name,
        'date': today_str,
        'timestamp': now_ist.strftime('%d/%m/%Y %I:%M:%S %p'),
        'time_short': now_ist.strftime('%I:%M %p'),
        'latitude': lat,
        'longitude': lng,
        'address': str(incident_data.get('address') or '').strip(),
        'nearest_target_name': str(incident_data.get('nearest_target_name') or 'Assigned Site').strip(),
        'detour_distance_km': round(safe_float(incident_data.get('detour_distance_km'), 0.0), 2),
        'dwell_minutes': int(incident_data.get('dwell_minutes') or 0),
        'severity': str(incident_data.get('severity') or 'HIGH').upper(),
        'anomaly_type': str(incident_data.get('anomaly_type') or 'Off-Route Detour').strip(),
        'summary': str(incident_data.get('summary') or '').strip(),
        'estimated_delay_mins': int(incident_data.get('estimated_delay_mins') or 30),
        'action_recommendation': str(incident_data.get('action_recommendation') or '').strip(),
        'is_unauthorized_detour': bool(incident_data.get('is_unauthorized_detour', True)),
        'ai_model_used': str(incident_data.get('model_used') or 'Argus AI Reasoning Engine').strip(),
        'status': 'Active',
        'admin_notes': '',
        'resolved_by': '',
        'resolved_at': None,
        'created_at': now_ist,
        'updated_at': now_ist
    }
    db.field_ai_incidents.insert_one(incident_doc)
    return clean_doc(incident_doc)


def get_field_ai_incidents(company_id=None, date_str=None, employee_name=None, status=None, limit=50):
    """Fetches AI-detected incidents with optional filtering."""
    db = get_db()
    q = {}
    if company_id and company_id != 'ALL':
        q['company_id'] = str(company_id)
    if date_str:
        q['date'] = str(date_str).strip()
    if employee_name:
        q['employee_name'] = str(employee_name).strip()
    if status and status != 'ALL':
        if status == 'Active':
            q['status'] = {'$in': ['Active', 'Acknowledged']}
        else:
            q['status'] = str(status).strip()

    docs = list(db.field_ai_incidents.find(q).sort('created_at', DESCENDING).limit(limit))
    return [clean_doc(d) for d in docs]


def resolve_field_ai_incident(incident_id, status='Resolved', admin_notes='', resolved_by='Admin', company_id=None):
    """Marks an AI incident as Acknowledged or Resolved."""
    db = get_db()
    now_ist = get_ist_now()
    q = build_id_filter(incident_id)
    if company_id and company_id != 'ALL':
        q = {'$and': [q, {'company_id': str(company_id)}]}

    upd = {
        'status': str(status or 'Resolved').strip(),
        'admin_notes': str(admin_notes or '').strip(),
        'resolved_by': str(resolved_by or 'Admin').strip(),
        'resolved_at': now_ist.strftime('%d/%m/%Y %I:%M %p'),
        'updated_at': now_ist
    }
    res = db.field_ai_incidents.update_one(q, {'$set': upd})
    return res.matched_count > 0


def get_field_ai_incidents_summary(company_id=None, date_str=None):
    """Returns count metrics for AI incidents today."""
    db = get_db()
    now_ist = get_ist_now()
    target_date = str(date_str or now_ist.strftime('%Y-%m-%d')).strip()
    q = {'date': target_date}
    if company_id and company_id != 'ALL':
        q['company_id'] = str(company_id)

    all_incs = list(db.field_ai_incidents.find(q))
    active_cnt = sum(1 for i in all_incs if i.get('status') in ['Active', 'Acknowledged'])
    high_cnt = sum(1 for i in all_incs if i.get('status') in ['Active', 'Acknowledged'] and i.get('severity') == 'HIGH')
    resolved_cnt = sum(1 for i in all_incs if i.get('status') == 'Resolved')

    return {
        'total': len(all_incs),
        'active': active_cnt,
        'high_severity': high_cnt,
        'resolved': resolved_cnt
    }


def record_field_location_ping(data, company_id=None):
    """
    Records a live GPS location ping from a field worker, evaluates whether they are
    at their assigned company location (on_site), moving toward it (in_transit),
    or deviating for personal work / detour (off_route_detour), computes distance traveled,
    and triggers Autonomous AI Anomaly Evaluation when detours or stationary dwell are detected.
    """
    db = get_db()
    now_ist = get_ist_now()
    today_str = str(data.get('date') or now_ist.strftime('%Y-%m-%d')).strip()
    emp_name = str(data.get('employee_name') or '').strip()
    if not emp_name:
        raise ValueError("Employee name is required for GPS tracking.")

    assigned_company_id = str(company_id or data.get('company_id') or '').strip()
    if not assigned_company_id or assigned_company_id == 'ALL':
        emp_doc = db.employees.find_one({'employee_name': emp_name})
        assigned_company_id = str(emp_doc.get('company_id') if emp_doc else 'ARGUS_MASTER')

    lat = round(safe_float(data.get('latitude'), 0.0), 6)
    lng = round(safe_float(data.get('longitude'), 0.0), 6)
    if lat == 0.0 and lng == 0.0:
        raise ValueError("Valid GPS coordinates (latitude, longitude) are required.")

    address = str(data.get('address') or '').strip()
    if not address or 'Lat:' in address:
        try:
            resolved_addr = reverse_geocode_coordinates(lat, lng)
            if resolved_addr:
                address = resolved_addr
        except Exception:
            if not address:
                address = f"Lat: {lat}, Lng: {lng}"

    # Check worker's previous location ping today to compute incremental step_km
    prev_ping = db.field_location_logs.find_one(
        {'company_id': assigned_company_id, 'employee_name': emp_name, 'date': today_str},
        sort=[('created_at', DESCENDING)]
    )
    step_km = 0.0
    if prev_ping and prev_ping.get('latitude') and prev_ping.get('longitude'):
        dist_info = calculate_realistic_proximity(
            prev_ping['latitude'], prev_ping['longitude'], lat, lng
        )
        step_m = float(dist_info.get('geodesic_m', 0.0)) if isinstance(dist_info, dict) else float(dist_info or 0.0)
        # Ignore GPS jitter < 10m and unrealistic jumps > 50km
        if 10.0 <= step_m <= 50000.0:
            step_km = round(step_m / 1000.0, 3)

    # Compute dwell time (stationary outside target)
    dwell_minutes = int(safe_float(data.get('dwell_minutes'), 0))
    recent_pings = list(db.field_location_logs.find(
        {'company_id': assigned_company_id, 'employee_name': emp_name, 'date': today_str},
        sort=[('created_at', DESCENDING)]
    ).limit(10))

    if recent_pings:
        stationary_cluster = []
        for rp in recent_pings:
            rp_lat = rp.get('latitude')
            rp_lng = rp.get('longitude')
            if rp_lat and rp_lng:
                p_dist = calculate_realistic_proximity(lat, lng, rp_lat, rp_lng)
                p_m = float(p_dist.get('geodesic_m', 999.0)) if isinstance(p_dist, dict) else float(p_dist or 999.0)
                if p_m <= 100.0:
                    stationary_cluster.append(rp)
                else:
                    break
        if stationary_cluster:
            earliest_dt = stationary_cluster[-1].get('created_at')
            if earliest_dt and isinstance(earliest_dt, datetime):
                calc_dwell = int((now_ist - earliest_dt).total_seconds() / 60.0)
                dwell_minutes = max(dwell_minutes, calc_dwell)

    # Evaluate against today's assigned company locations for this worker
    assignments_today = list(db.field_assignments.find({
        'company_id': assigned_company_id,
        'employee_name': emp_name,
        'assigned_date': today_str
    }))

    nearest_target_name = 'No Assigned Target Today'
    nearest_assignment_id = str(data.get('assignment_id') or '').strip()
    min_distance_m = None
    matched_radius = 150.0
    matched_assignment = None

    for asgn in assignments_today:
        t_lat = safe_float(asgn.get('target_lat'), 0.0)
        t_lng = safe_float(asgn.get('target_lng'), 0.0)
        if t_lat == 0.0 and t_lng == 0.0:
            continue
        prox = calculate_realistic_proximity(lat, lng, t_lat, t_lng)
        d_m = round(float(prox.get('geodesic_m', 999999.0)) if isinstance(prox, dict) else float(prox if prox is not None else 999999.0), 1)
        if nearest_assignment_id and str(asgn.get('id')) == nearest_assignment_id:
            min_distance_m = d_m
            nearest_target_name = asgn.get('target_name', 'Assigned Site')
            matched_radius = max(30.0, safe_float(asgn.get('geofence_radius'), 150.0))
            matched_assignment = asgn
            break
        if min_distance_m is None or d_m < min_distance_m:
            min_distance_m = d_m
            nearest_target_name = asgn.get('target_name', 'Assigned Site')
            nearest_assignment_id = str(asgn.get('id', ''))
            matched_radius = max(30.0, safe_float(asgn.get('geofence_radius'), 150.0))
            matched_assignment = asgn

    # Determine tracking status: Company Location vs In-Transit vs Personal Work Detour
    explicit_mode = str(data.get('tracking_status') or '').strip().lower()
    if explicit_mode in ['on_site', 'in_transit', 'off_route_detour']:
        tracking_status = explicit_mode
    elif min_distance_m is not None:
        if min_distance_m <= matched_radius:
            tracking_status = 'on_site'
        elif min_distance_m <= max(1000.0, matched_radius * 4):
            tracking_status = 'in_transit'
        else:
            tracking_status = 'off_route_detour'
    else:
        tracking_status = 'in_transit'

    # Auto-update matched assignment if worker arrived on-site
    if tracking_status == 'on_site' and matched_assignment and matched_assignment.get('status') == 'Pending':
        db.field_assignments.update_one(
            {'_id': matched_assignment['_id']},
            {'$set': {'status': 'In Progress', 'updated_at': now_ist}}
        )

    # Provide realistic baseline dwell time for explicit detour simulation / test
    if tracking_status == 'off_route_detour' and dwell_minutes == 0:
        dwell_minutes = 28 if explicit_mode == 'off_route_detour' else 15

    # Autonomous AI Anomaly Pipeline
    ai_incident = None
    if tracking_status == 'off_route_detour' or (min_distance_m is not None and min_distance_m >= 1800.0):
        tracking_status = 'off_route_detour'
        ai_eval = evaluate_field_worker_anomaly(
            emp_name=emp_name,
            lat=lat,
            lng=lng,
            address=address,
            nearest_target_name=nearest_target_name,
            detour_distance_m=min_distance_m if min_distance_m is not None else 2500.0,
            dwell_minutes=dwell_minutes,
            activity_note=str(data.get('activity_note') or ''),
            company_id=assigned_company_id
        )
        ai_incident = save_field_ai_incident({
            'company_id': assigned_company_id,
            'employee_id': str(data.get('employee_id') or '').strip(),
            'employee_name': emp_name,
            'date': today_str,
            'latitude': lat,
            'longitude': lng,
            'address': address,
            'nearest_target_name': nearest_target_name,
            'detour_distance_km': round((min_distance_m or 2500.0) / 1000.0, 2),
            'dwell_minutes': dwell_minutes,
            'severity': ai_eval.get('severity', 'HIGH'),
            'anomaly_type': ai_eval.get('anomaly_type', 'Off-Route Detour'),
            'summary': ai_eval.get('summary', ''),
            'estimated_delay_mins': ai_eval.get('estimated_delay_mins', 30),
            'action_recommendation': ai_eval.get('action_recommendation', ''),
            'is_unauthorized_detour': ai_eval.get('is_unauthorized_detour', True),
            'model_used': ai_eval.get('model_used', 'Argus AI Reasoning Engine')
        })

    status_labels = {
        'on_site': 'Verified at Assigned Company Location',
        'in_transit': 'In-Transit on Official Route',
        'off_route_detour': f"AI Detour Alert ({ai_incident.get('severity', 'HIGH')})" if ai_incident else 'Off-Route / Personal Work Detour Alert'
    }
    status_label = status_labels.get(tracking_status, 'In-Transit')

    ping_doc = {
        'id': f"FP-{int(time.time() * 1000)}",
        'company_id': assigned_company_id,
        'employee_id': str(data.get('employee_id') or '').strip(),
        'employee_name': emp_name,
        'assignment_id': nearest_assignment_id,
        'nearest_target_name': nearest_target_name,
        'latitude': lat,
        'longitude': lng,
        'accuracy': round(safe_float(data.get('accuracy'), 12.0), 1),
        'address': address,
        'distance_from_target_m': min_distance_m if min_distance_m is not None else 0.0,
        'geofence_radius_m': matched_radius,
        'step_km': step_km,
        'dwell_minutes': dwell_minutes,
        'tracking_status': tracking_status,
        'status_label': status_label,
        'activity_note': str(data.get('activity_note') or '').strip(),
        'battery_level': str(data.get('battery_level') or '92%').strip(),
        'ai_incident': ai_incident,
        'date': today_str,
        'timestamp': now_ist.strftime('%d/%m/%Y %I:%M:%S %p'),
        'time_short': now_ist.strftime('%I:%M %p'),
        'created_at': now_ist
    }
    db.field_location_logs.insert_one(ping_doc)
    return clean_doc(ping_doc)


def get_field_live_tracking(company_id=None, date_str=None, employee_name=None):
    """
    Returns live worker markers, route breadcrumbs, AI detour incident alerts, and summary counts for the Live Field Map.
    """
    db = get_db()
    now_ist = get_ist_now()
    target_date = str(date_str or now_ist.strftime('%Y-%m-%d')).strip()

    q = {'date': target_date}
    if company_id and company_id != 'ALL':
        q['company_id'] = str(company_id)
    if employee_name:
        q['employee_name'] = str(employee_name).strip()

    logs = [clean_doc(d) for d in db.field_location_logs.find(q).sort('created_at', ASCENDING)]

    # Fetch AI incidents for today
    incidents_today = get_field_ai_incidents(company_id=company_id, date_str=target_date, employee_name=employee_name)
    active_incidents = [i for i in incidents_today if i.get('status') in ['Active', 'Acknowledged']]
    incidents_summary = get_field_ai_incidents_summary(company_id=company_id, date_str=target_date)

    active_by_worker = {}
    for inc in active_incidents:
        wname = inc.get('employee_name')
        if wname and (wname not in active_by_worker or inc.get('severity') == 'HIGH'):
            active_by_worker[wname] = inc

    workers_map = {}
    breadcrumbs_by_worker = {}
    for lg in logs:
        ename = lg.get('employee_name', 'Unknown')
        if ename not in breadcrumbs_by_worker:
            breadcrumbs_by_worker[ename] = []
        breadcrumbs_by_worker[ename].append({
            'lat': lg.get('latitude'),
            'lng': lg.get('longitude'),
            'status': lg.get('tracking_status'),
            'status_label': lg.get('status_label'),
            'time': lg.get('time_short') or lg.get('timestamp'),
            'address': lg.get('address'),
            'distance_m': lg.get('distance_from_target_m'),
            'target_name': lg.get('nearest_target_name')
        })
        prev_State = workers_map.get(ename, {})
        cum_km = round(float(prev_State.get('total_km_today', 0.0)) + float(lg.get('step_km', 0.0)), 2)
        pings_cnt = int(prev_State.get('pings_count', 0)) + 1
        detours_cnt = int(prev_State.get('detour_count', 0)) + (1 if lg.get('tracking_status') == 'off_route_detour' else 0)

        workers_map[ename] = {
            'employee_name': ename,
            'employee_id': lg.get('employee_id', ''),
            'latitude': lg.get('latitude'),
            'longitude': lg.get('longitude'),
            'address': lg.get('address'),
            'tracking_status': lg.get('tracking_status'),
            'status_label': lg.get('status_label'),
            'nearest_target_name': lg.get('nearest_target_name'),
            'distance_from_target_m': lg.get('distance_from_target_m'),
            'total_km_today': cum_km,
            'pings_count': pings_cnt,
            'detour_count': detours_cnt,
            'last_seen': lg.get('time_short') or lg.get('timestamp'),
            'battery_level': lg.get('battery_level', '90%'),
            'activity_note': lg.get('activity_note', ''),
            'active_ai_incident': active_by_worker.get(ename)
        }

    workers_live = list(workers_map.values())
    on_site_count = sum(1 for w in workers_live if w.get('tracking_status') == 'on_site')
    in_transit_count = sum(1 for w in workers_live if w.get('tracking_status') == 'in_transit')
    detour_count = sum(1 for w in workers_live if w.get('tracking_status') == 'off_route_detour')

    return {
        'date': target_date,
        'workers_live': workers_live,
        'breadcrumbs_by_worker': breadcrumbs_by_worker,
        'logs': list(reversed(logs)),
        'ai_incidents': incidents_today,
        'active_ai_incidents': active_incidents,
        'ai_summary': incidents_summary,
        'counts': {
            'active_tracked': len(workers_live),
            'on_site': on_site_count,
            'in_transit': in_transit_count,
            'off_route_detour': detour_count,
            'ai_alerts': len(active_incidents)
        }
    }



def create_field_customer_visit(data, company_id=None):
    """
    Records a Field Worker Customer Visit / Sales Lead and automatically geo-verifies
    whether the visit took place at an assigned company location.
    """
    db = get_db()
    now_ist = get_ist_now()
    today_str = str(data.get('visit_date') or now_ist.strftime('%Y-%m-%d')).strip()
    emp_name = str(data.get('employee_name') or '').strip()
    customer_name = str(data.get('customer_name') or '').strip()

    if not emp_name:
        raise ValueError("Field worker name is required.")
    if not customer_name:
        raise ValueError("Customer / Business name is required.")

    assigned_company_id = str(company_id or data.get('company_id') or '').strip()
    if not assigned_company_id or assigned_company_id == 'ALL':
        emp_doc = db.employees.find_one({'employee_name': emp_name})
        assigned_company_id = str(emp_doc.get('company_id') if emp_doc else 'ARGUS_MASTER')

    lat = round(safe_float(data.get('latitude'), 11.0168), 6)
    lng = round(safe_float(data.get('longitude'), 76.9558), 6)
    address = str(data.get('address') or '').strip()
    if not address and lat and lng:
        try:
            address = reverse_geocode_coordinates(lat, lng)
        except Exception:
            address = f"{lat}, {lng}"

    # Verify against worker's assigned locations
    assignment_id = str(data.get('assignment_id') or '').strip()
    assignments = list(db.field_assignments.find({
        'company_id': assigned_company_id,
        'employee_name': emp_name,
        'assigned_date': today_str
    }))

    is_location_verified = False
    distance_from_target_m = None
    matched_target_name = 'Self-Sourced / Unassigned Lead'
    matched_asgn_doc = None

    for asgn in assignments:
        t_lat = safe_float(asgn.get('target_lat'), 0.0)
        t_lng = safe_float(asgn.get('target_lng'), 0.0)
        if t_lat == 0.0 and t_lng == 0.0:
            continue
        prox = calculate_realistic_proximity(lat, lng, t_lat, t_lng)
        d_m = round(float(prox.get('geodesic_m', 999999.0)) if isinstance(prox, dict) else float(prox if prox is not None else 999999.0), 1)
        radius = max(50.0, safe_float(asgn.get('geofence_radius'), 150.0))

        if assignment_id and str(asgn.get('id')) == assignment_id:
            distance_from_target_m = d_m
            matched_target_name = asgn.get('target_name', customer_name)
            matched_asgn_doc = asgn
            if d_m <= max(radius, 250.0):
                is_location_verified = True
            break

        if distance_from_target_m is None or d_m < distance_from_target_m:
            distance_from_target_m = d_m
            matched_target_name = asgn.get('target_name', customer_name)
            matched_asgn_doc = asgn
            if d_m <= max(radius, 250.0):
                is_location_verified = True

    # If no assignment existed today or if client explicitly verified GPS at customer shop
    if not assignments and lat != 0.0 and lng != 0.0:
        is_location_verified = True
        matched_target_name = f"Direct Field Visit ({customer_name})"
        distance_from_target_m = 0.0

    if matched_asgn_doc and is_location_verified:
        db.field_assignments.update_one(
            {'_id': matched_asgn_doc['_id']},
            {'$set': {
                'status': 'Completed',
                'verified_at': now_ist.strftime('%d/%m/%Y %I:%M %p'),
                'updated_at': now_ist
            }}
        )

    visit_doc = {
        'id': f"FV-{int(time.time() * 1000)}",
        'company_id': assigned_company_id,
        'employee_id': str(data.get('employee_id') or '').strip(),
        'employee_name': emp_name,
        'assignment_id': str(matched_asgn_doc.get('id')) if matched_asgn_doc else assignment_id,
        'customer_name': customer_name,
        'contact_person': str(data.get('contact_person') or '').strip(),
        'customer_phone': str(data.get('customer_phone') or '').strip(),
        'customer_email': str(data.get('customer_email') or '').strip(),
        'product_pitched': str(data.get('product_pitched') or 'Company Products').strip(),
        'lead_status': str(data.get('lead_status') or 'Interested').strip(),
        'order_amount': round(safe_float(data.get('order_amount'), 0.0), 2),
        'follow_up_date': str(data.get('follow_up_date') or '').strip(),
        'remarks': str(data.get('remarks') or '').strip(),
        'photo_proof': str(data.get('photo_proof') or '').strip(),
        'latitude': lat,
        'longitude': lng,
        'address': address,
        'matched_target_name': matched_target_name,
        'distance_from_target_m': distance_from_target_m if distance_from_target_m is not None else 0.0,
        'is_location_verified': is_location_verified,
        'verification_badge': 'Verified at Assigned Site' if is_location_verified else 'Off-Site / Unassigned Location',
        'visit_date': today_str,
        'visit_time': now_ist.strftime('%I:%M %p'),
        'timestamp': now_ist.strftime('%d/%m/%Y %I:%M %p'),
        'created_at': now_ist
    }
    db.field_customer_visits.insert_one(visit_doc)

    # Also log a GPS ping so the live map reflects this customer visit immediately
    try:
        record_field_location_ping({
            'company_id': assigned_company_id,
            'employee_name': emp_name,
            'latitude': lat,
            'longitude': lng,
            'address': address,
            'assignment_id': visit_doc['assignment_id'],
            'tracking_status': 'on_site' if is_location_verified else 'off_route_detour',
            'activity_note': f"Customer Visit: {customer_name} ({visit_doc['lead_status']})"
        }, company_id=assigned_company_id)
    except Exception:
        pass

    return clean_doc(visit_doc)


def get_field_customer_visits(company_id=None, employee_name=None, start_date=None, end_date=None, lead_status=None):
    """Fetches customer visits / sales leads with optional filters."""
    db = get_db()
    q = {}
    if company_id and company_id != 'ALL':
        q['company_id'] = str(company_id)
    if employee_name:
        q['employee_name'] = str(employee_name).strip()
    if lead_status:
        q['lead_status'] = str(lead_status).strip()
    if start_date and end_date:
        q['visit_date'] = {'$gte': str(start_date).strip(), '$lte': str(end_date).strip()}
    elif start_date:
        q['visit_date'] = str(start_date).strip()

    docs = list(db.field_customer_visits.find(q).sort('created_at', DESCENDING))
    return [clean_doc(d) for d in docs]


def update_field_customer_visit(visit_id, data, company_id=None):
    """Updates customer visit / lead fields such as lead_status, order_amount, remarks, follow_up_date, etc."""
    db = get_db()
    q = build_id_filter(visit_id)
    if company_id and company_id != 'ALL':
        q = {'$and': [q, {'company_id': str(company_id)}]}

    upd = {'updated_at': get_ist_now()}
    for k in ['customer_name', 'contact_person', 'customer_phone', 'customer_email', 'product_pitched', 'lead_status', 'follow_up_date', 'remarks', 'address']:
        if k in data and data[k] is not None:
            upd[k] = str(data[k]).strip()
    if 'order_amount' in data and data['order_amount'] is not None:
        upd['order_amount'] = round(safe_float(data['order_amount'], 0.0), 2)

    res = db.field_customer_visits.update_one(q, {'$set': upd})
    return res.matched_count > 0


def delete_field_customer_visit(visit_id, company_id=None):
    """Deletes a customer visit / lead entry."""
    db = get_db()
    q = build_id_filter(visit_id)
    if company_id and company_id != 'ALL':
        q = {'$and': [q, {'company_id': str(company_id)}]}
    res = db.field_customer_visits.delete_one(q)
    return res.deleted_count > 0


def get_field_worker_salary_report(company_id=None, month_year=None, employee_name=None):
    """
    Calculates monthly Field Worker Salary & Payslip data combining:
    1. Base Attendance Salary (from Punch-In / Punch-Out via get_payslip_data, supporting 0-shift hourly, daily, and regular shifts)
    2. Verified Customer Visit Incentives (verified_visits * per_visit_incentive)
    3. GPS Travel Distance Allowance (total_km_traveled * km_allowance_rate)
    4. Sales Order / Lead Conversion Metrics
    """
    db = get_db()
    now_ist = get_ist_now()
    target_month = str(month_year or now_ist.strftime('%Y-%m')).strip()

    workers = get_field_workers(company_id=company_id, include_all_employees=False)
    if employee_name:
        workers = [w for w in workers if w.get('employee_name') == employee_name]
        if not workers:
            emp_doc = db.employees.find_one({'employee_name': employee_name})
            if emp_doc:
                workers = [clean_doc(emp_doc)]

    reports = []
    for w in workers:
        ename = w.get('employee_name', '')
        if not ename:
            continue
        emp_cid = w.get('company_id') or company_id or 'ARGUS_MASTER'
        payslip = get_payslip_data(ename, target_month, company_id=emp_cid) or {}

        # 1. Field Assignments in target_month
        asgn_q = {
            'company_id': str(emp_cid),
            'employee_name': ename,
            'assigned_date': {'$regex': f'^{re.escape(target_month)}'}
        }
        total_assigned = db.field_assignments.count_documents(asgn_q)
        completed_assigned = db.field_assignments.count_documents({**asgn_q, 'status': 'Completed'})

        # 2. Customer Visits / Leads in target_month
        visit_q = {
            'company_id': str(emp_cid),
            'employee_name': ename,
            'visit_date': {'$regex': f'^{re.escape(target_month)}'}
        }
        visits = list(db.field_customer_visits.find(visit_q))
        total_visits = len(visits)
        verified_visits = sum(1 for v in visits if v.get('is_location_verified', True))
        unverified_visits = max(0, total_visits - verified_visits)
        orders_booked = sum(1 for v in visits if str(v.get('lead_status', '')).lower() in ['order booked', 'payment collected', 'converted'])
        orders_value = round(sum(safe_float(v.get('order_amount', 0.0)) for v in visits), 2)

        # 3. GPS Distance & Detour Alerts in target_month
        log_q = {
            'company_id': str(emp_cid),
            'employee_name': ename,
            'date': {'$regex': f'^{re.escape(target_month)}'}
        }
        logs = list(db.field_location_logs.find(log_q))
        total_km = round(sum(safe_float(lg.get('step_km', 0.0)) for lg in logs), 2)
        detour_alerts = sum(1 for lg in logs if lg.get('tracking_status') == 'off_route_detour')

        # 4. Compensation Calculation
        per_visit_rate = round(safe_float(w.get('per_visit_incentive', 0.0)), 2)
        km_rate = round(safe_float(w.get('km_allowance_rate', 5.0)), 2)
        if km_rate <= 0:
            km_rate = 5.0

        visit_incentive_pay = round(verified_visits * per_visit_rate, 2)
        travel_allowance_pay = round(total_km * km_rate, 2)

        base_attendance_pay = round(safe_float(payslip.get('basic_salary', 0.0)), 2)
        regular_allowance = round(safe_float(payslip.get('allowance', 0.0)), 2)
        regular_incentive = round(safe_float(payslip.get('incentive', 0.0)), 2)
        other_earnings = round(safe_float(payslip.get('other_earnings', 0.0)), 2)
        total_deduction = round(safe_float(payslip.get('total_deduction', 0.0)), 2)

        gross_field_salary = round(
            base_attendance_pay + visit_incentive_pay + travel_allowance_pay + regular_allowance + regular_incentive + other_earnings,
            2
        )
        net_field_payable = max(0.0, round(gross_field_salary - total_deduction, 2))

        reports.append({
            'employee_id': w.get('id', ''),
            'employee_name': ename,
            'company_id': emp_cid,
            'company_name': payslip.get('company_name', 'ARGUS TECHNOLOGIES'),
            'company_address': payslip.get('company_address', ''),
            'department': w.get('department', 'Field Sales'),
            'designation': w.get('designation', 'Field Executive'),
            'territory_zone': w.get('territory_zone') or 'General Zone',
            'status': w.get('status', 'Active'),
            'month_year': target_month,
            'pay_period': payslip.get('pay_period', target_month),
            'salary_type': w.get('salary_type', 'daily'),
            'shift_hours': w.get('shift_hours', '08:00'),
            'working_days': payslip.get('working_days', 0),
            'total_hours': payslip.get('total_hours', '00:00'),
            'total_assigned_locations': total_assigned,
            'completed_assignments': completed_assigned,
            'total_visits': total_visits,
            'verified_visits': verified_visits,
            'unverified_visits': unverified_visits,
            'orders_booked': orders_booked,
            'orders_value': orders_value,
            'total_km_traveled': total_km,
            'detour_alerts': detour_alerts,
            'per_visit_incentive_rate': per_visit_rate,
            'km_allowance_rate': km_rate,
            'base_attendance_pay': base_attendance_pay,
            'visit_incentive_pay': visit_incentive_pay,
            'travel_allowance_pay': travel_allowance_pay,
            'petrol_allowance': travel_allowance_pay,
            'fuel_allowance': travel_allowance_pay,
            'regular_allowance': regular_allowance + regular_incentive + other_earnings,
            'total_deduction': total_deduction,
            'gross_field_salary': gross_field_salary,
            'net_field_payable': net_field_payable,
            'net_pay_in_words': number_to_words(net_field_payable),
            'bank_name': w.get('bank_name', ''),
            'account_number': w.get('account_number', ''),
            'ifsc_code': w.get('ifsc_code', '')
        })

    return reports


# =========================================================================
# MODULE ENTITLEMENTS & MULTI-BRANCH ENTERPRISE MANAGEMENT
# =========================================================================

_company_modules_cache = {}
_company_modules_cache_ttl = 30  # seconds

def invalidate_company_modules_cache(company_id=None):
    global _company_modules_cache
    if company_id:
        _company_modules_cache.pop(str(company_id), None)
        _company_modules_cache.pop('ALL', None)
    else:
        _company_modules_cache.clear()


def get_company_modules(comp_id):
    """
    Returns a dict of active modules for a given company.
    Guarantees backwards-compatibility for existing companies.
    """
    if not comp_id or str(comp_id) in ['ALL', 'ARGUS_MASTER', 'SUPER_ADMIN']:
        return {
            'single_company': True,
            'branch_company': True,
            'field_worker': True
        }
    key = str(comp_id)
    now_ts = time.time()
    if key in _company_modules_cache:
        t, val = _company_modules_cache[key]
        if now_ts - t < _company_modules_cache_ttl:
            return val

    comp = get_company_by_id(comp_id)
    if not comp:
        res = {
            'single_company': True,
            'branch_company': True,
            'field_worker': True
        }
    else:
        mods = comp.get('modules')
        if isinstance(mods, dict):
            res = {
                'single_company': bool(mods.get('single_company', True)),
                'branch_company': bool(mods.get('branch_company', True)),
                'field_worker': bool(mods.get('field_worker', True))
            }
        else:
            # Default for all companies before explicit restriction: all modules active
            res = {
                'single_company': True,
                'branch_company': True,
                'field_worker': True
            }

    _company_modules_cache[key] = (now_ts, res)
    return res


_company_branches_cache = {}
_company_branches_cache_ttl = 60  # seconds

def invalidate_company_branches_cache(company_id=None):
    global _company_branches_cache
    if company_id:
        _company_branches_cache.pop(str(company_id), None)
        _company_branches_cache.pop('ALL', None)
        _company_branches_cache.pop('ARGUS_MASTER', None)
    else:
        _company_branches_cache.clear()

def get_company_branches(company_id, status=None, include_headcount=True):
    """
    Returns list of branch locations for a given company.
    When include_headcount=False, skips employee aggregation for ultra-fast performance.
    """
    if not company_id:
        return []
    key = str(company_id)
    now_ts = time.time()
    if not include_headcount and status is None and key in _company_branches_cache:
        t, val = _company_branches_cache[key]
        if now_ts - t < _company_branches_cache_ttl:
            return [dict(b) for b in val]

    db = get_db()
    query = {}
    if company_id and str(company_id) != 'ALL':
        query['company_id'] = str(company_id)
    if status:
        query['status'] = status
    
    branches = list(db.company_branches.find(query).sort('branch_name', ASCENDING))
    
    count_map = {}
    if include_headcount:
        emp_match = {'status': {'$nin': ['Deactive', 'Inactive']}}
        if company_id and str(company_id) != 'ALL':
            emp_match['company_id'] = str(company_id)
            
        counts = db.employees.aggregate([
            {'$match': emp_match},
            {'$group': {'_id': '$branch_id', 'count': {'$sum': 1}}}
        ])
        count_map = {str(c['_id']): c['count'] for c in counts if c['_id']}
    
    cleaned_branches = []
    for b in branches:
        bid = str(b.get('id') or '')
        b['employee_count'] = count_map.get(bid, 0)
        b['headcount'] = b['employee_count']
        cb = clean_doc(b)
        cb.pop('_id', None)
        cleaned_branches.append(cb)
        
    if not include_headcount and status is None:
        _company_branches_cache[key] = (now_ts, [dict(b) for b in cleaned_branches])

    return cleaned_branches


def get_branch_by_id(branch_id, company_id=None):
    """Returns single branch document by ID."""
    if not branch_id:
        return None
    db = get_db()
    query = {'id': str(branch_id)}
    if company_id and str(company_id) != 'ALL':
        query['company_id'] = str(company_id)
    b = db.company_branches.find_one(query)
    return clean_doc(b)


def create_company_branch(data, company_id):
    """Creates a new branch location for a company."""
    if not company_id:
        raise ValueError("Company ID is required to create a branch.")
    b_name = (data.get('branch_name') or '').strip()
    if not b_name:
        raise ValueError("Branch Name is required.")
        
    db = get_db()
    # Check branch creation limit quota
    comp = get_company_by_id(str(company_id), include_counts=False)
    branch_limit = int(comp.get('branch_limit') or 5) if comp else 5
    current_count = db.company_branches.count_documents({
        'company_id': str(company_id),
        'status': {'$ne': 'Deleted'}
    })
    if current_count >= branch_limit:
        raise ValueError(f"Branch creation limit reached. This company is allowed a maximum of {branch_limit} branches. Contact system admin to upgrade your branch quota.")

    now_ist = get_ist_now()
    branch_id = str(data.get('id') or f"branch_{int(time.time() * 1000)}")
    
    lat = parse_coordinate_value(data.get('latitude'))
    lng = parse_coordinate_value(data.get('longitude'))
    try:
        rad = float(data.get('geofence_radius') or 150.0)
    except (ValueError, TypeError):
        rad = 150.0
    
    # Auto-generate branch code if not provided
    b_code = (data.get('branch_code') or '').strip().upper()
    if not b_code:
        try:
            existing_count = db.company_branches.count_documents({'company_id': str(company_id)})
            clean_prefix = ''.join(c for c in b_name if c.isalnum()).upper()[:3] or "BR"
            b_code = f"{clean_prefix}-{(existing_count + 1):03d}"
        except Exception:
            b_code = f"BR-{(int(time.time()) % 1000):03d}"

    doc = {
        'id': branch_id,
        'company_id': str(company_id),
        'branch_name': b_name,
        'branch_code': b_code,
        'district': (data.get('district') or '').strip(),
        'address': (data.get('address') or '').strip(),
        'latitude': lat,
        'longitude': lng,
        'geofence_radius': rad,
        'branch_head_name': (data.get('branch_head_name') or '').strip(),
        'branch_head_email': (data.get('branch_head_email') or '').strip().lower(),
        'branch_head_phone': (data.get('branch_head_phone') or '').strip(),
        'status': data.get('status', 'Active'),
        'created_at': now_ist,
        'updated_at': now_ist
    }
    db.company_branches.insert_one(doc)
    invalidate_company_branches_cache(company_id)
    return branch_id


def update_company_branch(branch_id, data, company_id=None):
    """Updates an existing branch location."""
    if not branch_id:
        raise ValueError("Branch ID is required.")
    db = get_db()
    now_ist = get_ist_now()
    upd = {'updated_at': now_ist}
    
    if 'branch_name' in data:
        upd['branch_name'] = str(data['branch_name']).strip()
    if 'branch_code' in data:
        upd['branch_code'] = str(data['branch_code']).strip().upper()
    if 'district' in data:
        upd['district'] = str(data['district']).strip()
    if 'address' in data:
        upd['address'] = str(data['address']).strip()
    if 'latitude' in data:
        upd['latitude'] = parse_coordinate_value(data['latitude'])
    if 'longitude' in data:
        upd['longitude'] = parse_coordinate_value(data['longitude'])
    if 'geofence_radius' in data:
        try:
            upd['geofence_radius'] = float(data['geofence_radius'])
        except (ValueError, TypeError):
            pass
    if 'branch_head_name' in data:
        upd['branch_head_name'] = str(data['branch_head_name']).strip()
    if 'branch_head_email' in data:
        upd['branch_head_email'] = str(data['branch_head_email']).strip().lower()
    if 'branch_head_phone' in data:
        upd['branch_head_phone'] = str(data['branch_head_phone']).strip()
    if 'status' in data:
        upd['status'] = data['status']
        
    query = {'id': str(branch_id)}
    if company_id and str(company_id) != 'ALL':
        query['company_id'] = str(company_id)
        
    res = db.company_branches.update_one(query, {'$set': upd})
    
    # If branch_name changed, sync with assigned employees
    if 'branch_name' in upd:
        db.employees.update_many(
            {'branch_id': str(branch_id)},
            {'$set': {'branch_name': upd['branch_name']}}
        )
    actual_cid = company_id or (res.matched_count and query.get('company_id'))
    invalidate_company_branches_cache(actual_cid)
    return res.modified_count > 0


def delete_company_branch(branch_id, company_id=None):
    """Deletes a branch and unassigns employees linked to it."""
    if not branch_id:
        return False
    db = get_db()
    query = {'id': str(branch_id)}
    if company_id and str(company_id) != 'ALL':
        query['company_id'] = str(company_id)
        
    db.company_branches.delete_one(query)
    # Unassign employees linked to this branch
    db.employees.update_many(
        {'branch_id': str(branch_id)},
        {'$set': {'branch_id': None, 'branch_name': None}}
    )
    invalidate_company_branches_cache(company_id)
    return True


def assign_employee_to_branch(employee_id, branch_id, company_id=None):
    """Assigns or transfers an employee to a specific branch."""
    if not employee_id:
        raise ValueError("Employee ID is required.")
    db = get_db()
    
    if not branch_id:
        # Clear branch allocation
        db.employees.update_one(
            {'id': str(employee_id)},
            {'$set': {'branch_id': None, 'branch_name': None}}
        )
        return True
        
    branch = get_branch_by_id(branch_id, company_id)
    if not branch:
        raise ValueError("Selected branch not found.")
        
    db.employees.update_one(
        {'id': str(employee_id)},
        {'$set': {
            'branch_id': str(branch_id),
            'branch_name': branch.get('branch_name')
        }}
    )
    return True


def get_branch_attendance_summary(company_id=None):
    """
    Returns branch-wise attendance summary for today:
    Total employees, Present today, Absent today, and On Leave today for each branch.
    """
    db = get_db()
    branches = get_company_branches(company_id)
    if not branches:
        return []
    
    t_filter = {}
    if company_id and str(company_id) not in ['ALL', 'ARGUS_MASTER']:
        t_filter['company_id'] = str(company_id)
        
    now_ist = get_ist_now()
    today_str = now_ist.strftime('%Y-%m-%d')
    today_slash = now_ist.strftime('%d/%m/%Y')
    
    # Batch query today's punches
    p_filter = dict(t_filter)
    p_filter['date'] = today_str
    att_docs = {a.get('employee_name'): a for a in db.attendance.find(p_filter)}
    
    ar_today_filter = dict(t_filter)
    ar_today_filter['date'] = today_str
    ar_docs = {a.get('employee_name'): a for a in db.attendance_reports.find(ar_today_filter)}
    
    l_filter = dict(t_filter)
    l_filter['entry_time'] = {'$regex': today_slash}
    live_docs = {l.get('employee_name'): l for l in db.live_entries.find(l_filter)}
    
    m_filter = dict(t_filter)
    m_filter['$or'] = [
        {'entry_date': today_str},
        {'submitted_at': {'$regex': today_str}},
        {'submitted_at': {'$regex': today_slash}}
    ]
    manual_docs = {m.get('employee_name'): m for m in db.manual_entries.find(m_filter)}
    
    timeout_today = {t.get('employee_name'): t for t in db.timeout_entries.find({**t_filter, '$or': [{'entry_time': {'$regex': today_slash}}, {'exit_time': {'$regex': today_slash}}]})}
    combined_present = set(k for k in att_docs.keys() if k).union(
        set(k for k in ar_docs.keys() if k),
        set(k for k in live_docs.keys() if k),
        set(k for k in manual_docs.keys() if k),
        set(k for k in timeout_today.keys() if k)
    )
    
    approved_leaves_today = get_approved_leaves_for_date(today_str, company_id=company_id)
    
    # Query all active employees with branch_id
    emp_query = {**t_filter, 'status': {'$ne': 'Inactive'}}
    all_emps = list(db.employees.find(emp_query, {'id': 1, 'employee_name': 1, 'branch_id': 1}))
    
    # Group employees by branch
    branch_map = {}
    for b in branches:
        bid = b.get('id')
        branch_map[bid] = {
            'branch_id': bid,
            'branch_name': b.get('branch_name'),
            'branch_code': b.get('branch_code'),
            'district': b.get('district'),
            'address': b.get('address'),
            'latitude': b.get('latitude'),
            'longitude': b.get('longitude'),
            'geofence_radius': b.get('geofence_radius', 150),
            'branch_head_name': b.get('branch_head_name'),
            'status': b.get('status', 'Active'),
            'total_employees': 0,
            'present_count': 0,
            'leave_count': 0,
            'absent_count': 0
        }
    
    unassigned_stat = {
        'branch_id': 'HOME',
        'branch_name': 'Home Branch',
        'district': 'Headquarters',
        'status': 'Active',
        'total_employees': 0,
        'present_count': 0,
        'leave_count': 0,
        'absent_count': 0
    }
    
    for emp in all_emps:
        bid = emp.get('branch_id')
        ename = emp.get('employee_name')
        target_stat = branch_map.get(bid, unassigned_stat) if (bid and not is_home_branch_id(bid)) else unassigned_stat
        target_stat['total_employees'] += 1
        
        is_pres = ename in combined_present
        is_leave = (ename in approved_leaves_today) or (str(emp.get('id')) in approved_leaves_today)
        
        if is_pres:
            target_stat['present_count'] += 1
        elif is_leave:
            target_stat['leave_count'] += 1
        else:
            target_stat['absent_count'] += 1
            
    result = list(branch_map.values())
    if unassigned_stat['total_employees'] > 0:
        result.insert(0, unassigned_stat)
    return result

