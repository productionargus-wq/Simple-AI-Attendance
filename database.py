import os
import time
import json
import re
import calendar
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
        filters.append({'id': int(ident)})
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
        'can_delete_entries': str(data.get('can_delete_entries', False)).lower() in ['true', '1', 'yes'],
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
    
    # Batch calculate employee counts in a single query instead of N sequential calls
    comp_ids = [doc.get('id') for doc in company_docs if doc.get('id')]
    counts_map = {}
    if comp_ids:
        try:
            agg_res = db.employees.aggregate([
                {'$match': {'company_id': {'$in': comp_ids}}},
                {'$group': {'_id': '$company_id', 'count': {'$sum': 1}}}
            ])
            counts_map = {item['_id']: item['count'] for item in agg_res}
        except Exception:
            pass

    for doc in company_docs:
        c = clean_doc(doc)
        c['address'] = c.get('address') or c.get('location') or ''
        c['employee_count'] = counts_map.get(c['id'], 0)
        c['employee_limit'] = int(c.get('employee_limit') or c['employee_count'] or 50)
        c['shift_hours'] = str(c.get('shift_hours') or '08:00').strip()
        if 'auto_email_reports' not in c:
            c['auto_email_reports'] = True
        if 'can_delete_entries' not in c:
            c['can_delete_entries'] = False
            
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
        if 'can_delete_entries' not in c:
            c['can_delete_entries'] = False
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
    if 'logo_data' in data:
        upd['logo_data'] = str(data['logo_data']).strip()
    db.company_admin.update_one(build_id_filter(comp_id), {'$set': upd})
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
    db = get_db()
    comp = db.company_admin.find_one({'id': str(comp_id)})
    if not comp:
        comp = db.company_admin.find_one(build_id_filter(comp_id))
    if not comp:
        return False
    return bool(comp.get('can_delete_entries', False))

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
    return new_val

def delete_company(comp_id):
    """Removes company from company_admin."""
    db = get_db()
    db.company_admin.delete_one(build_id_filter(comp_id))
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
    cleaned = clean_doc(doc)
    if cleaned and not cleaned.get('permissions'):
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

def create_employee(data, company_id=None):
    db = get_db()
    emp_name = str(data.get('employee_name') or '').strip()
    if not emp_name:
        raise ValueError('Employee name is required.')
    email_id = str(data.get('email_id') or '').strip()
    if not email_id:
        raise ValueError('Email ID is required.')

    emp_id = str(data.get('id') or '').strip() or generate_employee_id()
    assigned_company_id = str(company_id or data.get('company_id') or 'ARGUS_MASTER')

    # Enforce Employee Count registration limit for tenant companies
    if assigned_company_id != 'ARGUS_MASTER':
        comp = db.company_admin.find_one(build_id_filter(assigned_company_id))
        if comp:
            limit = int(comp.get('employee_limit') or comp.get('employee_count') or 50)
            current_count = db.employees.count_documents({'company_id': assigned_company_id})
            if current_count >= limit:
                comp_name = comp.get('company_name', assigned_company_id)
                raise ValueError(
                    f"Employee registration limit reached: Company '{comp_name}' allows a maximum of {limit} employees ({current_count}/{limit} currently registered). Please contact System Admin to increase the employee limit."
                )

    raw_st = str(data.get('salary_type') or 'daily').strip().lower()
    salary_type = raw_st if raw_st in ['hourly', 'daily', 'half_day'] else 'daily'
    
    doc = {
        'id': emp_id,
        'company_id': assigned_company_id,
        'employee_name': emp_name,
        'department': (data.get('department') or data.get('designation') or 'General').strip(),
        'designation': data.get('designation', '').strip(),
        'salary_type': salary_type,
        'mobile_number': data.get('mobile_number', '').strip(),
        'hourly_salary': safe_float(data.get('hourly_salary')),
        'day_salary': safe_float(data.get('day_salary')),
        'half_day_salary': safe_float(data.get('half_day_salary')),
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
        'shift_hours': data.get('shift_hours', '').strip(),
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
        'created_at': get_ist_now(),
        'updated_at': get_ist_now()
    }
    
    db.employees.insert_one(doc)
    invalidate_dashboard_cache(assigned_company_id)
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
        'shift_start', 'shift_end'
    ]
    for key in text_fields:
        if key in data:
            upd[key] = str(data[key]).strip() if data[key] is not None else ''

    salary_fields = ['hourly_salary', 'day_salary', 'half_day_salary']
    for s_key in salary_fields:
        if s_key in data:
            upd[s_key] = safe_float(data[s_key])

    if 'salary_type' in data and data['salary_type']:
        st = str(data['salary_type']).strip().lower()
        if st in ['hourly', 'daily', 'half_day']:
            upd['salary_type'] = st

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
        
    db.employees.update_one(f, {'$set': upd})
    invalidate_dashboard_cache(company_id)
    return True

def delete_employee(emp_id, company_id=None):
    db = get_db()
    f = build_id_filter(emp_id)
    if company_id and company_id != 'ALL':
        f = {'$and': [f, {'company_id': str(company_id)}]}
    db.employees.delete_one(f)
    invalidate_dashboard_cache(company_id)
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
    if company_id:
        _dashboard_cache.pop(str(company_id), None)
        _dashboard_cache.pop('ALL', None)
        _dashboard_cache.pop(None, None)
    else:
        _dashboard_cache.clear()

def get_dashboard_stats(company_id=None):
    cache_key = str(company_id or 'ALL')
    now_ts = time.time()
    if cache_key in _dashboard_cache:
        entry_time, cached_val = _dashboard_cache[cache_key]
        if now_ts - entry_time < _dashboard_cache_ttl:
            return cached_val

    db = get_db()
    t_filter = {}
    if company_id and company_id != 'ALL':
        t_filter['company_id'] = str(company_id)
        
    total_employees = db.employees.count_documents(t_filter)
    
    # Calculate today's active punches across live punches, attendance, reports, and manual entries
    now_ist = get_ist_now()
    today = now_ist.date()
    today_str = now_ist.strftime('%Y-%m-%d')
    today_slash = now_ist.strftime('%d/%m/%Y')
    curr_year = now_ist.year
    curr_month = now_ist.month

    # Fetch today's records upfront in batch (avoids duplicate queries)
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
    
    timeout_today = {t['employee_name']: t for t in db.timeout_entries.find({**t_filter, '$or': [{'entry_time': {'$regex': today_slash}}, {'exit_time': {'$regex': today_slash}}]})}
    combined_present = set(att_docs.keys()).union(set(ar_docs.keys())).union(set(live_docs.keys())).union(set(manual_docs.keys())).union(set(timeout_today.keys()))
    present_count = len(combined_present)

    # Approved leaves today integration
    approved_leaves_today = get_approved_leaves_for_date(today_str, company_id=company_id)
    on_leave_set = set(approved_leaves_today.keys()).difference(combined_present)
    on_leave_count = len(on_leave_set)

    absent_count = max(0, total_employees - present_count - on_leave_count)
    present_percentage = round((present_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    on_leave_percentage = round((on_leave_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    absent_percentage = round((absent_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    
    tout_filter = dict(t_filter)
    tout_filter['is_timeout'] = 1
    timeout_count = db.timeout_entries.count_documents(dict(t_filter)) + db.live_entries.count_documents(tout_filter)
    timeout_percentage = round((timeout_count / total_employees * 100), 1) if total_employees > 0 else 0.0
    
    # Last 7 days dynamic calculation in BATCH queries (replaces 35 individual network calls)
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    day_map = {d.strftime('%Y-%m-%d'): {'label': d.strftime('%d %b'), 'slash': d.strftime('%d/%m/%Y'), 'present': set(), 'timeouts': 0} for d in days}
    day_strs = list(day_map.keys())
    day_slashes = [v['slash'] for v in day_map.values()]

    att_7d = list(db.attendance.find({**t_filter, 'date': {'$in': day_strs}}, {'employee_name': 1, 'date': 1}))
    for a in att_7d:
        dt = a.get('date')
        if dt in day_map and a.get('employee_name'):
            day_map[dt]['present'].add(a['employee_name'])

    ar_7d = list(db.attendance_reports.find({**t_filter, 'date': {'$in': day_strs}}, {'employee_name': 1, 'date': 1}))
    for a in ar_7d:
        dt = a.get('date')
        if dt in day_map and a.get('employee_name'):
            day_map[dt]['present'].add(a['employee_name'])

    slash_pattern = "|".join([d.replace('/', '\\/') for d in day_slashes])
    hyphen_pattern = "|".join(day_strs)
    me_7d = list(db.manual_entries.find({
        **t_filter,
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

    live_7d = list(db.live_entries.find({**t_filter, 'entry_time': {'$regex': slash_pattern}}, {'employee_name': 1, 'entry_time': 1, 'is_timeout': 1}))
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

    timeout_7d = list(db.timeout_entries.find({**t_filter, '$or': [{'entry_time': {'$regex': slash_pattern}}, {'exit_time': {'$regex': slash_pattern}}]}, {'employee_name': 1, 'entry_time': 1, 'exit_time': 1}))
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

    year_att = list(db.attendance.find({**t_filter, 'date': {'$regex': f"^{curr_year}-"}}, {'date': 1}))
    for a in year_att:
        dt = a.get('date', '')
        if len(dt) >= 7:
            try:
                m_idx = int(dt[5:7])
                if m_idx in monthly_map:
                    monthly_map[m_idx]['present_cnt'] += 1
            except Exception:
                pass

    year_ar = list(db.attendance_reports.find({**t_filter, 'date': {'$regex': f"^{curr_year}-"}}, {'date': 1}))
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
        **t_filter,
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

    year_live = list(db.live_entries.find({**t_filter, 'entry_time': {'$regex': f"/{curr_year}"}}, {'entry_time': 1, 'is_timeout': 1}))
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
        
    # Today's attendance list & Department summary
    employees = list(db.employees.find(t_filter, {'_id': 0, 'id': 1, 'employee_name': 1, 'department': 1, 'designation': 1}))
    
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
        shift_str = emp_shift if emp_shift and str(emp_shift).strip() else company_shifts.get(cid, '08:00')
        
        shift_h = 8
        shift_m = 0
        try:
            if shift_str:
                s_clean = str(shift_str).strip()
                if ':' in s_clean:
                    sp = s_clean.split(':')
                    shift_h = int(sp[0])
                    shift_m = int(sp[1])
                else:
                    shift_h = int(float(s_clean))
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
            
        auto_exit_dt = entry_dt + timedelta(minutes=shift_mins)
        
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

def get_live_report_entries(tab='live', start_date=None, end_date=None, search=None, page=1, limit=10, company_id=None):
    sync_live_and_timeout_entries(company_id=company_id)
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
        
    target_coll = db.timeout_entries if tab == 'timeout' else db.live_entries

    if not start_date and not end_date:
        def_start, _, _, _ = get_default_two_month_range()
        start_date = def_start

    # Pre-load employee shift hours for dynamic status computation
    emp_shifts = {}
    emp_q = {}
    if company_id and company_id != 'ALL':
        emp_q['company_id'] = str(company_id)
    for emp_d in db.employees.find(emp_q, {'employee_name': 1, 'shift_start': 1, 'shift_end': 1}):
        if emp_d.get('employee_name'):
            emp_shifts[emp_d['employee_name']] = {
                'start': emp_d.get('shift_start', '09:00 AM') or '09:00 AM',
                'end': emp_d.get('shift_end', '06:00 PM') or '06:00 PM'
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

        s_cfg = emp_shifts.get(c.get('employee_name', ''), {'start': '09:00 AM', 'end': '06:00 PM'})
        e_status, x_status = compute_entry_exit_status(c.get('entry_time'), c.get('exit_time'), s_cfg['start'], s_cfg['end'], is_manual=False)
        c['entry_status'] = e_status
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
    """Synchronize attendance_reports entry_type to strictly match the 200-meter geofencing rule."""
    try:
        db = get_db()
        for doc in db.attendance_reports.find({}):
            e_dist = parse_distance_meters_val(doc.get('entry_distance'))
            x_dist = parse_distance_meters_val(doc.get('exit_distance'))
            
            # If neither distance is recorded (e.g. legacy/mock records without distances), leave as-is
            if e_dist is None and x_dist is None:
                continue

            is_outside = False
            if e_dist is not None and e_dist > GEOFENCE_RADIUS_METERS:
                is_outside = True
            if x_dist is not None and x_dist > GEOFENCE_RADIUS_METERS:
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
    """Returns the registered full address string for a company."""
    if not company_id or company_id == 'ARGUS_MASTER':
        db = get_db()
        comp = db.company_admin.find_one({'id': 'ARGUS_MASTER'})
        return (comp.get('address') if comp else None) or OFFICE_LOCATION_STR
    db = get_db()
    comp = db.company_admin.find_one({'id': str(company_id)})
    if comp:
        return comp.get('address') or comp.get('location') or OFFICE_LOCATION_STR
    return OFFICE_LOCATION_STR

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

def add_live_entry(employee_id, employee_name, entry_time=None, site_name='OFFICE', entry_location=None, entry_distance=0.0, is_timeout=0, user_lat=None, user_lng=None, company_id='ARGUS_MASTER', target_lat=None, target_lng=None, live_address=None):
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

def record_face_attendance(employee_id, employee_name, user_lat=None, user_lng=None, company_id=None, client_time=None, live_address=None):
    """
    Punch In / Punch Out Attendance Lifecycle Engine with Multi-Tenant Geolocation Support:
    1. Records Live Entry in db.live_entries with real-time location address and company_id in 12-hour format (IST).
    2. Resolves company office coordinates and calculates proximity distance.
    3. Handles Punch In & Punch Out lifecycle storing the exact live location address where punched.
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
    
    # Determine office coordinates and full address for this company
    target_lat = OFFICE_LAT
    target_lng = OFFICE_LNG
    loc_str = get_company_full_address(comp_id)
    if comp_id != 'ARGUS_MASTER':
        comp = db.company_admin.find_one({'id': comp_id})
        if comp:
            target_lat = parse_coordinate_to_float(comp.get('latitude'), OFFICE_LAT)
            target_lng = parse_coordinate_to_float(comp.get('longitude'), OFFICE_LNG)
            if comp.get('address'):
                loc_str = comp.get('address')
    else:
        comp = db.company_admin.find_one({'id': 'ARGUS_MASTER'})
        if comp:
            target_lat = parse_coordinate_to_float(comp.get('latitude'), OFFICE_LAT)
            target_lng = parse_coordinate_to_float(comp.get('longitude'), OFFICE_LNG)
            if comp.get('address'):
                loc_str = comp.get('address')
            
    # Calculate proximity distance
    dist_meters = calculate_realistic_proximity(user_lat, user_lng, target_lat, target_lng)
    formatted_dist = format_office_distance(dist_meters)

    # Resolve exact real-time live location address where employee punched
    live_loc_str = (live_address.strip() if live_address and str(live_address).strip() else None)
    if not live_loc_str and user_lat is not None and user_lng is not None:
        live_loc_str = reverse_geocode_coordinates(user_lat, user_lng)
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
            live_address=live_loc_str
        )

        # Geofencing threshold: 200 meters (<= 200m is proper, > 200m is improper)
        punch_in_entry_type = 'proper' if dist_meters <= GEOFENCE_RADIUS_METERS else 'improper'
        rep_doc = {
            'company_id': comp_id,
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
            
        # Determine final entry_type: Proper only if BOTH punch-in and punch-out are <= 200m
        in_entry_type = existing_rep.get('entry_type', 'proper')
        out_is_proper = (dist_meters <= GEOFENCE_RADIUS_METERS)
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

def compute_entry_exit_status(entry_time_str, exit_time_str, shift_start='09:00 AM', shift_end='06:00 PM', is_manual=False):
    """
    Computes precise ENTRY STATUS and EXIT STATUS strings:
    - If manual entry: returns ('-', '-')
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

    exit_mins = parse_time_to_minutes(exit_time_str)
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

def get_attendance_reports(report_type='all', start_date=None, end_date=None, employee='All', search=None, page=1, limit=10, company_id=None):
    db = get_db()

    if not start_date and not end_date:
        def_start, _, _, _ = get_default_two_month_range()
        start_date = def_start

    # Pre-load employee shift hours for dynamic status computation
    emp_shifts = {}
    emp_q = {}
    if company_id and company_id != 'ALL':
        emp_q['company_id'] = str(company_id)
    for emp_d in db.employees.find(emp_q, {'employee_name': 1, 'shift_start': 1, 'shift_end': 1}):
        if emp_d.get('employee_name'):
            emp_shifts[emp_d['employee_name']] = {
                'start': emp_d.get('shift_start', '09:00 AM') or '09:00 AM',
                'end': emp_d.get('shift_end', '06:00 PM') or '06:00 PM'
            }

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

            s_cfg = emp_shifts.get(c.get('employee_name', ''), {'start': '09:00 AM', 'end': '06:00 PM'})
            e_status, x_status = compute_entry_exit_status(c.get('entry_time'), c.get('exit_time'), s_cfg['start'], s_cfg['end'], is_manual=False)
            c['entry_status'] = e_status
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

        s_cfg = emp_shifts.get(c.get('employee_name', ''), {'start': '09:00 AM', 'end': '06:00 PM'})
        e_status, x_status = compute_entry_exit_status(c.get('entry_time'), c.get('exit_time'), s_cfg['start'], s_cfg['end'], is_manual=False)
        c['entry_status'] = e_status
        c['exit_status'] = x_status
        c['is_manual'] = False
        c['sort_key'] = str(c.get('date') or c.get('created_at') or c.get('entry_time') or '')
        combined.append(c)

    # Manual entries query matching same filters
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

    if not start_date and not end_date:
        def_start, _, _, _ = get_default_two_month_range()
        start_date = def_start

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

def get_manual_entries(from_date=None, to_date=None, status='All', search=None, page=1, limit=10, company_id=None):
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
        
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
    
    reason = str(data.get('reason') or '').strip()
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

def get_payments(employee=None, start_date=None, end_date=None, bank=None, payment_type=None, status=None, reason=None, search=None, page=1, limit=10, company_id=None):
    db = get_db()
    conditions = []
    
    if company_id and company_id != 'ALL':
        conditions.append({'company_id': str(company_id)})
        
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
        
    adv_cursor = list(db.advances.find(adv_query))
    
    # Query all advance repayments
    rep_conditions = [{'$or': [{'status': 'Advance Repayment'}, {'reason': 'Advance Repayment'}]}]
    if company_id and company_id != 'ALL':
        rep_conditions.append({'company_id': str(company_id)})
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

def get_salary_reports(start_month=None, end_month=None, search=None, page=1, limit=10, company_id=None):
    db = get_db()
    query = {}
    
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
        
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
        unapplied_additions = sum(m for d, m in daily_manual_salary.items() if m > 0 and daily_minutes.get(d, 0) == 0)
        basic_salary = max(0.0, round(basic_salary + unapplied_additions, 2))
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
    if paid_leave_days > 0:
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
        'total_deductions': int(round(total_deduction)),
        'net_pay': int(round(net_pay)),
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
        'paid_leave_salary': int(round(paid_leave_salary)),
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
    """Retrieves the default annual leave allocation policy for a company."""
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
    if not company_id or company_id == 'ALL':
        return default_policy
    db = get_db()
    
    # 1. Check dedicated leave_policies collection
    pol_rec = db.leave_policies.find_one({'company_id': str(company_id)})
    if pol_rec:
        cl = int(pol_rec.get('casual_leave_annual', pol_rec.get('casual_leave', 12)))
        sl = int(pol_rec.get('sick_leave_annual', pol_rec.get('sick_leave', 12)))
        el = int(pol_rec.get('earned_leave_annual', pol_rec.get('earned_leave', 18)))
        ph = float(pol_rec.get('permission_hours_monthly', pol_rec.get('permission_hours', 16.0)))
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
    if not comp or 'leave_policy' not in comp:
        return default_policy
    pol = comp['leave_policy']
    cl = int(pol.get('casual_leave_annual', pol.get('casual_leave', 12)))
    sl = int(pol.get('sick_leave_annual', pol.get('sick_leave', 12)))
    el = int(pol.get('earned_leave_annual', pol.get('earned_leave', 18)))
    ph = float(pol.get('permission_hours_monthly', pol.get('permission_hours', 16.0)))
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

def save_company_leave_policy(company_id, policy_data):
    """Saves or updates the default annual leave allocation policy for a company."""
    if not company_id or company_id == 'ALL':
        company_id = 'DEFAULT'
    db = get_db()
    cl = int(policy_data.get('casual_leave_annual', policy_data.get('casual_leave', 12)))
    sl = int(policy_data.get('sick_leave_annual', policy_data.get('sick_leave', 12)))
    el = int(policy_data.get('earned_leave_annual', policy_data.get('earned_leave', 18)))
    ph = float(policy_data.get('permission_hours_monthly', policy_data.get('permission_hours', 16.0)))

    pol_doc = {
        'company_id': str(company_id),
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
    db.leave_policies.update_one({'company_id': str(company_id)}, {'$set': pol_doc}, upsert=True)

    # Also sync into company_admin if present
    q = {'id': str(company_id)} if str(company_id).isdigit() else {'$or': [{'id': str(company_id)}, build_id_filter(company_id)]}
    db.company_admin.update_one(q, {'$set': {'leave_policy': pol_doc}})

    # Synchronize all existing leave balances for this company for current year
    try:
        curr_year = get_ist_now().year
        bal_filter = {'year': int(curr_year)}
        if str(company_id) not in ['DEFAULT', 'ALL', 'ARGUS_MASTER']:
            bal_filter['company_id'] = str(company_id)
        
        existing_bals = list(db.leave_balances.find(bal_filter))
        for b in existing_bals:
            b_id = b['_id']
            cl_used = float(b.get('casual_leave', {}).get('used', 0))
            sl_used = float(b.get('sick_leave', {}).get('used', 0))
            el_used = float(b.get('earned_leave', {}).get('used', 0))
            ph_used = float(b.get('permission_hours', {}).get('used', 0.0))

            db.leave_balances.update_one(
                {'_id': b_id},
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
    except Exception as e:
        print("Error synchronizing leave balances on policy update:", e)

    return True

def get_employee_leave_balance(emp_id, company_id=None, year=None):
    """
    Retrieves or initializes the employee's leave balance document for the given year.
    Returns: dict with casual_leave, sick_leave, earned_leave, permission_hours, compensatory_off
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
        # Initialize new balance using company policy
        emp = db.employees.find_one(build_id_filter(emp_id))
        comp_id = company_id or (emp.get('company_id') if emp else None)
        pol = get_company_leave_policy(comp_id)

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
    return bal

def get_all_employees_leave_balances(company_id=None, year=None, search=None):
    """
    Returns list of all employees in company along with their leave balances.
    Matches Image 4's Employee Leave Balance table.
    """
    db = get_db()
    if year is None:
        year = get_ist_now().year

    e_query = {}
    if company_id and company_id != 'ALL':
        e_query['company_id'] = str(company_id)
    
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
            'is_low_balance': (cl.get('available', 0) < 2 or sl.get('available', 0) < 2 or el.get('available', 0) < 2)
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

def get_leave_requests(company_id=None, employee_id=None, status=None, limit=50, page=1):
    """Retrieves paginated list of leave & permission requests."""
    db = get_db()
    query = {}
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)
    if employee_id:
        query['$or'] = [{'employee_id': str(employee_id)}, {'employee_id': int(employee_id) if str(employee_id).isdigit() else str(employee_id)}]
    if status and status != 'ALL':
        query['status'] = status

    total = db.leave_requests.count_documents(query)
    skip = (int(page) - 1) * int(limit)
    cursor = db.leave_requests.find(query).sort('created_at', DESCENDING).skip(skip).limit(int(limit))
    
    items = []
    for doc in cursor:
        items.append(clean_doc(doc))
    return {
        'total': total,
        'page': int(page),
        'limit': int(limit),
        'requests': items
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

    upd = {
        'status': normalized_status,
        'admin_remark': admin_remark if admin_remark is not None else req.get('admin_remark'),
        'reviewed_by': reviewer or 'System Administrator',
        'reviewed_at': now_ist.strftime('%Y-%m-%d %H:%M:%S'),
        'updated_at': now_ist
    }
    db.leave_requests.update_one(q, {'$set': upd})
    return {'success': True, 'status': normalized_status, 'message': f'Request {normalized_status} successfully'}

def get_admin_leave_stats(company_id=None):
    """Returns the 4 KPI card metrics shown in Image 4."""
    db = get_db()
    query = {}
    if company_id and company_id != 'ALL':
        query['company_id'] = str(company_id)

    today_str = get_ist_now().strftime('%Y-%m-%d')

    pending_count = db.leave_requests.count_documents({**query, 'status': 'Pending'})
    approved_today = db.leave_requests.count_documents({
        **query,
        'status': 'Approved',
        'reviewed_at': {'$regex': f"^{today_str}"}
    })
    rejected_count = db.leave_requests.count_documents({**query, 'status': 'Rejected'})

    all_bals = get_all_employees_leave_balances(company_id=company_id)
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

def get_pending_leave_requests_count(company_id=None):
    """
    Returns the count of Pending leave & permission requests.
    """
    db = get_db()
    query = {'status': 'Pending'}
    if company_id and str(company_id) not in ['ALL', 'ARGUS_MASTER', 'DEFAULT']:
        query['company_id'] = str(company_id)
    return db.leave_requests.count_documents(query)

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

