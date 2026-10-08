import os
import time
import threading
from datetime import datetime, timedelta
import schedule
import database
import email_service

_scheduler_thread = None
_scheduler_lock = threading.Lock()

def get_yesterday_ist():
    """Returns yesterday's date string in YYYY-MM-DD format (IST)."""
    now_ist = database.get_ist_now()
    yesterday = now_ist - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")

def get_previous_month_ist():
    """Returns previous month string in YYYY-MM format (IST)."""
    now_ist = database.get_ist_now()
    first_of_curr_month = now_ist.replace(day=1)
    last_of_prev_month = first_of_curr_month - timedelta(days=1)
    return last_of_prev_month.strftime("%Y-%m")

# ----------------- DATA AGGREGATORS ----------------- #

def build_daily_activity_report(company_id, target_date=None):
    """
    Compiles all face punches, manual entries, and payments for a company on target_date.
    target_date format: YYYY-MM-DD (defaults to yesterday).
    """
    db = database.get_db()
    if not target_date:
        target_date = get_yesterday_ist()

    comp_id_str = str(company_id)
    comp = db.company_admin.find_one({'id': comp_id_str})
    comp_name = comp.get('company_name', 'Company') if comp else 'Company'
    comp_email = comp.get('email', '') if comp else ''

    # Handle alternate date formats (e.g. DD-MM-YYYY vs YYYY-MM-DD)
    date_parts = target_date.split('-')
    d_alt = f"{date_parts[2]}-{date_parts[1]}-{date_parts[0]}" if len(date_parts) == 3 else target_date

    # 1. Face Attendance Punches for yesterday
    punch_query = {
        'company_id': comp_id_str,
        '$or': [
            {'date': target_date},
            {'date': d_alt},
            {'entry_time': {'$regex': f"^{target_date}"}},
            {'entry_time': {'$regex': f"^{d_alt}"}},
            {'created_at': {'$regex': f"^{target_date}"}}
        ]
    }
    punches_cursor = db.attendance_reports.find(punch_query)
    punches = list(punches_cursor)
    if not punches:
        punches = list(db.attendance.find(punch_query))

    clean_punches = []
    total_punch_minutes = 0
    total_punch_salary = 0.0
    active_employees = set()

    for p in punches:
        emp_name = p.get('employee_name', '')
        if emp_name:
            active_employees.add(emp_name)

        wh_str = p.get('working_hours', '00:00')
        mins = 0
        if wh_str and ':' in wh_str:
            try:
                sp = wh_str.split(':')
                mins = int(sp[0]) * 60 + int(sp[1])
            except Exception:
                mins = 0
        total_punch_minutes += mins
        
        sal = float(p.get('working_salary') or 0.0)
        total_punch_salary += sal

        clean_punches.append({
            'employee_name': emp_name,
            'entry_time': p.get('entry_time', '-'),
            'exit_time': p.get('exit_time', '-'),
            'working_hours': wh_str,
            'shift_variance': p.get('shift_variance', '00:00'),
            'day_credit_type': p.get('day_credit_type', 'Present'),
            'working_salary': int(round(sal))
        })

    # 2. Manual Entries for yesterday
    manual_query = {
        'company_id': comp_id_str,
        '$or': [
            {'entry_date': target_date},
            {'entry_date': d_alt},
            {'submitted_at': {'$regex': f"^{target_date}"}},
            {'submitted_at': {'$regex': f"^{d_alt}"}}
        ]
    }
    manual_entries = list(db.manual_entries.find(manual_query))
    clean_manual = []
    total_manual_salary = 0.0

    for m in manual_entries:
        emp_name = m.get('employee_name', '')
        if emp_name:
            active_employees.add(emp_name)

        sal = float(m.get('working_salary') or 0.0)
        total_manual_salary += sal
        
        clean_manual.append({
            'employee_name': emp_name,
            'hours': m.get('hours', '00:00'),
            'status': m.get('status', '-'),
            'mode': m.get('mode', 'Hours'),
            'working_salary': int(round(sal))
        })

    # 3. Payments / Adjustments for yesterday
    payment_query = {
        'company_id': comp_id_str,
        '$or': [
            {'payment_date': target_date},
            {'payment_date': d_alt},
            {'timestamp': {'$regex': f"^{target_date}"}},
            {'timestamp': {'$regex': f"^{d_alt}"}}
        ]
    }
    payments = list(db.payments.find(payment_query))
    clean_payments = []
    for pay in payments:
        p_stat = pay.get('status') or pay.get('reason') or 'Payment'
        p_reas = pay.get('reason') if pay.get('status') else ''
        p_disp = f"{p_stat} - {p_reas}" if p_reas else p_stat
        clean_payments.append({
            'employee_name': pay.get('employee_name', ''),
            'reason': p_disp,
            'amount': int(round(float(pay.get('amount', 0.0)))),
            'timestamp': pay.get('timestamp') or pay.get('payment_date', '')
        })

    total_hours_int = total_punch_minutes // 60
    total_mins_int = total_punch_minutes % 60
    total_hours_str = f"{total_hours_int:02d}:{total_mins_int:02d}"

    return {
        'company_id': comp_id_str,
        'company_name': comp_name,
        'company_email': comp_email,
        'date_str': target_date,
        'total_employees': len(active_employees),
        'total_punches': len(clean_punches),
        'total_hours_worked': total_hours_str,
        'total_working_salary': total_punch_salary + total_manual_salary,
        'punches': clean_punches,
        'manual_entries': clean_manual,
        'payments': clean_payments
    }

def format_time_12h(time_val):
    """Formats arbitrary timestamp or time string into 12-hour hh:mm AM/PM format."""
    if not time_val or time_val in ['-', 'None', '']:
        return '-'
    time_str = str(time_val).strip()
    for fmt in [
        "%d/%m/%Y %I:%M:%S %p",
        "%d/%m/%Y %I:%M %p",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %I:%M:%S %p",
        "%d-%m-%Y %I:%M %p",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%I:%M:%S %p",
        "%I:%M %p",
        "%H:%M:%S",
        "%H:%M"
    ]:
        try:
            dt = datetime.strptime(time_str.split('+')[0].split('.')[0], fmt)
            return dt.strftime("%I:%M %p")
        except Exception:
            pass
    parts = time_str.split()
    if len(parts) >= 2 and parts[-1].upper() in ['AM', 'PM']:
        t_part = parts[-2]
        t_sub = t_part.split(':')
        if len(t_sub) >= 2:
            try:
                return f"{int(t_sub[0]):02d}:{t_sub[1]} {parts[-1].upper()}"
            except Exception:
                pass
    return time_str

def format_distance_str(dist_val):
    """Normalizes raw distance values into human-readable e.g. '420 m' or '2.68 km'."""
    if not dist_val or dist_val in ['-', 'None', '']:
        return '0 m'
    s = str(dist_val).strip()
    if s.upper().startswith('OFFICE DISTANCE '):
        s = s[16:].strip()
    if s.endswith('M') and not s.endswith('KM'):
        try:
            val = float(s[:-1])
            return f"{int(round(val))} m"
        except Exception:
            return s.lower()
    elif s.endswith('KM'):
        try:
            val = float(s[:-2])
            if val >= 1:
                return f"{val:.2f} km"
            else:
                return f"{int(round(val * 1000))} m"
        except Exception:
            return s.lower()
    return s

def build_yesterdays_activity_full_data(company_id, target_date=None):
    """
    Compiles complete 6-category dynamic activity data for yesterday's activity report:
    1. Proper Entries
    2. Improper Entries
    3. Timeout Entries
    4. Manual Entries
    5. Payment Entries
    6. Employee Details
    """
    db = database.get_db()
    if not target_date:
        target_date = get_yesterday_ist()

    # Parse target_date object
    try:
        d_obj = datetime.strptime(target_date, "%Y-%m-%d")
    except Exception:
        try:
            d_obj = datetime.strptime(target_date, "%d-%m-%Y")
            target_date = d_obj.strftime("%Y-%m-%d")
        except Exception:
            d_obj = database.get_ist_now() - timedelta(days=1)
            target_date = d_obj.strftime("%Y-%m-%d")

    d_alt = d_obj.strftime("%d-%m-%Y")
    d_slash = d_obj.strftime("%d/%m/%Y")
    date_variants = [target_date, d_alt, d_slash]

    activity_date_str = d_obj.strftime("%d %B %Y")
    now_ist = database.get_ist_now()
    generated_date_str = now_ist.strftime("%d %B %Y")

    comp_id_str = str(company_id)
    comp = db.company_admin.find_one({'id': comp_id_str}) or {}
    comp_name = comp.get('company_name', 'ARGUS TECHNOLOGIES')
    comp_address = comp.get('address') or comp.get('location') or ''
    comp_location = comp.get('location') or comp.get('address') or ''

    # Cache active company employees for salary calculation and absent analysis
    emp_docs = list(db.employees.find({'company_id': comp_id_str}))
    emp_map = {e.get('employee_name'): e for e in emp_docs if e.get('employee_name')}

    def calculate_employee_working_salary(emp_info, working_hours_str, punch_doc=None):
        if punch_doc:
            for k in ['working_salary', 'salary_earned', 'salary']:
                if punch_doc.get(k) is not None:
                    try:
                        return float(punch_doc[k])
                    except (ValueError, TypeError):
                        pass
        if not emp_info:
            return 0.0
        stype = str(emp_info.get('salary_type') or 'hourly').strip().lower()
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
            parts = str(working_hours_str or '').split(':')
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

    # 1. Attendance punches (Proper & Improper)
    punch_query = {
        'company_id': comp_id_str,
        '$or': [
            {'date': {'$in': date_variants}},
            {'entry_time': {'$regex': f"^{d_slash}"}},
            {'entry_time': {'$regex': f"^{d_alt}"}},
            {'entry_time': {'$regex': f"^{target_date}"}},
            {'created_at': {'$regex': f"^{target_date}"}},
            {'created_at': {'$regex': f"^{d_alt}"}}
        ]
    }
    punches_cursor = db.attendance_reports.find(punch_query).sort('entry_time', 1)
    all_punches = list(punches_cursor)
    if not all_punches:
        all_punches = list(db.attendance.find(punch_query).sort('entry_time', 1))

    proper_entries = []
    improper_entries = []

    for p in all_punches:
        emp_name = p.get('employee_name', '-')
        entry_t = format_time_12h(p.get('entry_time'))
        exit_t = format_time_12h(p.get('exit_time'))
        wh = p.get('working_hours') or '00:00'

        entry_type = str(p.get('entry_type', '')).lower()
        is_improper = (entry_type == 'improper') or (p.get('is_improper') in [True, 1, '1'])

        raw_dist = p.get('entry_distance') or p.get('formatted_distance') or ''
        dist_str = format_distance_str(raw_dist)

        # Determine if improper by distance if not tagged
        if not is_improper and ('km' in dist_str.lower() or (dist_str.endswith('m') and dist_str[:-2].strip().isdigit() and int(dist_str[:-2].strip()) > 200)):
            is_improper = True

        emp_info = emp_map.get(emp_name)

        if is_improper:
            loc = p.get('entry_location') or 'Remote Location'
            if len(loc) > 40:
                loc = 'Remote Location'
            reason = 'Outside geofence'
            if 'entry after limit' in str(p.get('notes', '')).lower() or 'late' in str(p.get('notes', '')).lower():
                reason = 'Entry after limit'
            elif p.get('shift_variance') and '-' in str(p.get('shift_variance')) and not p.get('shift_variance', '').startswith('-00'):
                reason = 'Outside geofence'

            entry_status = p.get('entry_status')
            exit_status = p.get('exit_status')
            if not entry_status or entry_status == '-' or not exit_status or exit_status == '-':
                calc_e_stat, calc_x_stat = database.compute_entry_exit_status(
                    p.get('entry_time'),
                    p.get('exit_time')
                )
                if not entry_status or entry_status == '-':
                    entry_status = calc_e_stat
                if not exit_status or exit_status == '-':
                    exit_status = calc_x_stat

            improper_entries.append({
                'employee_name': emp_name,
                'entry_time': entry_t,
                'entry_status': entry_status or 'On Time',
                'exit_time': exit_t if exit_t != '-' else '-',
                'exit_status': exit_status or '-',
                'distance': dist_str if dist_str else '350 m',
                'location': loc if loc else 'Remote Location',
                'reason': reason
            })
        else:
            loc = 'Office'
            ws_val = calculate_employee_working_salary(emp_info, wh, p)
            proper_entries.append({
                'employee_name': emp_name,
                'entry_time': entry_t,
                'exit_time': exit_t if exit_t != '-' else '-',
                'working_hours': wh,
                'working_salary': f"Rs. {ws_val:,.0f}" if ws_val > 0 else "Rs. 0",
                'working_salary_val': ws_val,
                'location': loc,
                'status': 'Proper'
            })

    # 2. Timeout Entries
    timeout_query = {
        'company_id': comp_id_str,
        '$or': [
            {'date': {'$in': date_variants}},
            {'entry_time': {'$regex': f"^{d_slash}"}},
            {'entry_time': {'$regex': f"^{d_alt}"}},
            {'entry_time': {'$regex': f"^{target_date}"}},
            {'created_at': {'$regex': f"^{target_date}"}},
            {'created_at': {'$regex': f"^{d_alt}"}}
        ]
    }
    timeouts_raw = list(db.timeout_entries.find(timeout_query).sort('entry_time', 1))
    if not timeouts_raw:
        timeouts_raw = list(db.attendance_reports.find({
            'company_id': comp_id_str,
            'is_timeout': {'$in': [1, '1', True]},
            '$or': [
                {'date': {'$in': date_variants}},
                {'entry_time': {'$regex': f"^{d_slash}"}},
                {'created_at': {'$regex': f"^{target_date}"}}
            ]
        }))

    timeout_entries = []
    for t in timeouts_raw:
        emp_name = t.get('employee_name', '-')
        cin = format_time_12h(t.get('entry_time'))
        cout = format_time_12h(t.get('exit_time'))
        wh = t.get('working_hours') or '08:00'

        reason = t.get('reason')
        if not reason:
            if cout == '-' or not t.get('exit_time'):
                reason = 'Checkout not recorded'
            elif wh.startswith('12') or wh.startswith('10') or wh.startswith('08'):
                reason = 'Automatic checkout limit'
            else:
                reason = 'Automatic timeout'

        timeout_entries.append({
            'employee_name': emp_name,
            'checkin_time': cin,
            'auto_checkout': cout,
            'working_hours': wh,
            'reason': reason
        })

    # 3. Manual Entries
    manual_query = {
        'company_id': comp_id_str,
        '$or': [
            {'entry_date': {'$in': date_variants}},
            {'submitted_at': {'$regex': f"^{d_slash}"}},
            {'submitted_at': {'$regex': f"^{d_alt}"}},
            {'submitted_at': {'$regex': f"^{target_date}"}},
            {'created_at': {'$regex': f"^{target_date}"}}
        ]
    }
    manuals_raw = list(db.manual_entries.find(manual_query).sort('submitted_at', 1))
    manual_entries = []
    for m in manuals_raw:
        emp_name = m.get('employee_name', '-')
        raw_date = m.get('entry_date') or m.get('date') or ''
        date_display = '-'
        if raw_date:
            try:
                raw_str = str(raw_date).strip()
                if '-' in raw_str:
                    parts = raw_str.split('-')
                    if len(parts[0]) == 4:  # YYYY-MM-DD
                        date_display = f"{parts[2]}/{parts[1]}/{parts[0]}"
                    else:  # DD-MM-YYYY
                        date_display = f"{parts[0]}/{parts[1]}/{parts[2]}"
                elif '/' in raw_str:
                    date_display = raw_str
            except Exception:
                date_display = str(raw_date)
        if date_display == '-':
            date_display = d_slash

        hours_val = m.get('hours') or m.get('working_hours') or '08:00'
        etype = m.get('entry_type') or 'Check In'
        if etype == 'Add':
            etype = 'Check In'
        elif etype == 'Sub':
            etype = 'Check Out'
        added_by = m.get('added_by') or 'Admin'
        m_stat = m.get('status') or 'Manual entry'
        m_reas = (m.get('reason') or '').strip()
        remarks = f"{m_stat} - {m_reas}" if m_reas else (m.get('remarks') or m_stat)
        if remarks in ['Others', '-']:
            remarks = 'System down - manual entry'

        # Working salary computation
        if m.get('working_salary') is not None:
            try:
                ws_num = float(m['working_salary'])
            except Exception:
                ws_num = 0.0
        elif m.get('amount') is not None:
            try:
                ws_num = float(m['amount'])
            except Exception:
                ws_num = 0.0
        else:
            ws_num = calculate_employee_working_salary(emp_map.get(emp_name), hours_val)

        ws_disp = f"Rs. {abs(ws_num):,.0f}"
        if ws_num < 0 or str(m.get('entry_type', '')).lower() == 'sub':
            ws_disp = f"-Rs. {abs(ws_num):,.0f}"

        manual_entries.append({
            'employee_name': emp_name,
            'date': date_display,
            'hours': hours_val,
            'working_salary': ws_disp,
            'type': etype,
            'added_by': added_by,
            'remarks': remarks
        })

    # 4. Leave & Permissions Entries
    leave_query = {
        'company_id': comp_id_str,
        '$or': [
            {'request_type': 'Leave', 'from_date': {'$lte': target_date}, 'to_date': {'$gte': target_date}},
            {'request_type': 'Leave', 'from_date': {'$in': date_variants}},
            {'request_type': 'Permission', 'from_date': {'$in': date_variants}},
            {'request_type': 'Permission', 'date': {'$in': date_variants}}
        ]
    }
    leaves_raw = list(db.leave_requests.find(leave_query).sort('created_at', 1))
    leave_entries = []
    for lr in leaves_raw:
        ename = lr.get('employee_name', '-')
        req_type = lr.get('request_type', 'Leave')
        l_type = lr.get('leave_type') or lr.get('permission_type') or req_type

        if req_type == 'Permission':
            dur = lr.get('duration_str') or lr.get('duration')
            if not dur and lr.get('duration_hours'):
                dur = f"{lr.get('duration_hours')} hrs"
            if not dur:
                dur = "1 hr"
        else:
            session = lr.get('session')
            days_c = lr.get('total_days') or lr.get('days_count') or 1.0
            if session == 'Half Day':
                dur = "0.5 Day (Half Day)"
            elif days_c == 1.0 or days_c == 1:
                dur = "1 Day (Full Day)"
            else:
                dur = f"{days_c} Days"

        reason = lr.get('reason') or '-'
        status = lr.get('status') or 'Approved'

        leave_entries.append({
            'name': ename,
            'type': l_type,
            'duration': dur,
            'reason': reason,
            'status': status
        })

    # 5. Absent Report Entries
    present_names = set()
    for p in proper_entries:
        if p.get('employee_name') and p['employee_name'] != '-':
            present_names.add(p['employee_name'])
    for ip in improper_entries:
        if ip.get('employee_name') and ip['employee_name'] != '-':
            present_names.add(ip['employee_name'])
    for to in timeout_entries:
        if to.get('employee_name') and to['employee_name'] != '-':
            present_names.add(to['employee_name'])
    for me in manual_entries:
        if me.get('employee_name') and me['employee_name'] != '-':
            present_names.add(me['employee_name'])

    approved_leave_names = set()
    for lr in leave_entries:
        if str(lr.get('status')).lower() == 'approved' and 'leave' in str(lr.get('type', '')).lower():
            approved_leave_names.add(lr.get('name'))

    active_emps = list(db.employees.find({
        'company_id': comp_id_str,
        'status': {'$nin': ['inactive', 'Inactive', 'Disabled', 'Terminated']}
    }).sort('employee_name', 1))

    absent_entries = []
    for e in active_emps:
        ename = e.get('employee_name', '-')
        if ename not in present_names and ename not in approved_leave_names:
            dept = e.get('department') or '-'
            desig = e.get('designation') or '-'
            shift_time = e.get('shift_time') or e.get('shift_hours') or '09:00 AM - 06:00 PM'
            absent_entries.append({
                'employee_name': ename,
                'department': dept,
                'designation': desig,
                'shift': shift_time,
                'status': 'Absent'
            })

    # 6. Payment Entries
    pay_query = {
        'company_id': comp_id_str,
        '$or': [
            {'payment_date': {'$in': date_variants}},
            {'timestamp': {'$regex': f"^{d_slash}"}},
            {'timestamp': {'$regex': f"^{d_alt}"}},
            {'timestamp': {'$regex': f"^{target_date}"}},
            {'created_at': {'$regex': f"^{target_date}"}}
        ]
    }
    adv_query = {
        'company_id': comp_id_str,
        '$or': [
            {'advance_date': {'$in': date_variants}},
            {'timestamp': {'$regex': f"^{d_slash}"}},
            {'timestamp': {'$regex': f"^{d_alt}"}},
            {'timestamp': {'$regex': f"^{target_date}"}},
            {'created_at': {'$regex': f"^{target_date}"}}
        ]
    }
    payments_raw = list(db.payments.find(pay_query).sort('timestamp', 1))
    advances_raw = list(db.advances.find(adv_query).sort('timestamp', 1))

    payment_entries = []
    for p in payments_raw:
        emp_name = p.get('employee_name', '-')
        amt_num = int(round(float(p.get('amount') or 0.0)))
        p_stat = p.get('status') or p.get('reason') or 'Payment'
        p_reas = p.get('reason') if p.get('status') else ''
        p_disp = f"{p_stat} - {p_reas}" if p_reas else p_stat
        payment_entries.append({
            'employee_name': emp_name,
            'date': d_slash,
            'type': p.get('payment_type') or 'Payment',
            'amount': f"{amt_num:,}",
            'remarks': p_disp
        })
    for a in advances_raw:
        emp_name = a.get('employee_name', '-')
        amt_num = int(round(float(a.get('amount') or 0.0)))
        payment_entries.append({
            'employee_name': emp_name,
            'date': d_slash,
            'type': 'Advance',
            'amount': f"{amt_num:,}",
            'remarks': a.get('reason') or 'Advance payment'
        })

    # 7. Employee Details
    emp_query = {
        'company_id': comp_id_str,
        '$or': [
            {'updated_at': {'$regex': f"^{target_date}"}},
            {'updated_at': {'$regex': f"^{d_alt}"}},
            {'created_at': {'$regex': f"^{target_date}"}},
            {'created_at': {'$regex': f"^{d_alt}"}}
        ]
    }
    updated_emps = list(db.employees.find(emp_query))
    employee_details = []
    for e in updated_emps:
        emp_name = e.get('employee_name', '-')
        up_type = 'Profile Update'
        up_field = 'Mobile Number' if e.get('mobile_number') else 'Address'
        new_val = e.get('mobile_number') or e.get('address') or e.get('department') or 'Updated'
        employee_details.append({
            'employee_name': emp_name,
            'update_type': up_type,
            'updated_field': up_field,
            'old_value': '-',
            'new_value': new_val
        })

    counts = {
        'proper': len(proper_entries),
        'improper': len(improper_entries),
        'timeout': len(timeout_entries),
        'manual': len(manual_entries),
        'leave_permissions': len(leave_entries),
        'absent': len(absent_entries),
        'payment': len(payment_entries),
        'employee_details': len(employee_details)
    }

    return {
        'company_id': comp_id_str,
        'company_name': comp_name,
        'company_location': comp_location,
        'company_address': comp_address,
        'target_date': target_date,
        'activity_date_str': activity_date_str,
        'generated_date_str': generated_date_str,
        'counts': counts,
        'proper_entries': proper_entries,
        'improper_entries': improper_entries,
        'timeout_entries': timeout_entries,
        'manual_entries': manual_entries,
        'leave_entries': leave_entries,
        'absent_entries': absent_entries,
        'payment_entries': payment_entries,
        'employee_details': employee_details
    }

def build_monthly_salary_report(company_id, target_month=None):
    """
    Compiles complete monthly payroll and payslips for all company employees.
    target_month format: YYYY-MM (defaults to previous month).
    """
    db = database.get_db()
    if not target_month:
        target_month = get_previous_month_ist()

    comp_id_str = str(company_id)
    comp = db.company_admin.find_one({'id': comp_id_str})
    comp_name = comp.get('company_name', 'Company') if comp else 'Company'
    comp_email = comp.get('email', '') if comp else ''

    # Fetch all employees belonging to this company
    employees = list(db.employees.find({'company_id': comp_id_str}))

    payslips = []
    total_gross = 0.0
    total_allow = 0.0
    total_ded = 0.0
    total_net = 0.0

    for emp in employees:
        emp_name = emp.get('employee_name')
        if not emp_name:
            continue
        p = database.get_payslip_data(emp_name, target_month, company_id=comp_id_str)
        # Persist report record in salary_reports
        database.save_generated_salary_report(p, company_id=comp_id_str)

        total_gross += float(p.get('basic_salary', 0.0))
        total_allow += float(p.get('allowance', 0.0)) + float(p.get('incentive', 0.0))
        total_ded += float(p.get('total_deduction', 0.0))
        total_net += float(p.get('net_pay', 0.0))

        payslips.append(p)

    return {
        'company_id': comp_id_str,
        'company_name': comp_name,
        'company_email': comp_email,
        'pay_period': target_month,
        'total_employees': len(payslips),
        'total_gross_salary': total_gross,
        'total_allowance': total_allow,
        'total_deductions': total_ded,
        'total_net_payout': total_net,
        'employee_payslips': payslips
    }

# ----------------- EMAIL DISPATCH HANDLERS ----------------- #

def send_daily_activity_email(company_id, target_date=None, force=False):
    """
    Generates and sends yesterday's daily activity digest to the company's registered email.
    Idempotent: skips if already sent today unless force=True.
    """
    db = database.get_db()
    if not target_date:
        target_date = get_yesterday_ist()

    comp_id_str = str(company_id)
    comp = db.company_admin.find_one({'id': comp_id_str})
    if not comp or not comp.get('email'):
        return False, f"Company {comp_id_str} not found or has no registered email.", None

    # Check if automatic email reports are turned off for this company
    if not force and comp.get('auto_email_reports') is False:
        return False, f"Automatic email reports are turned off for {comp.get('company_name', comp_id_str)}. Skipping.", None

    to_email = comp['email'].strip()

    # Idempotency check: Don't send twice for the same date unless forced
    if not force:
        already_sent = db.email_logs.find_one({
            'company_id': comp_id_str,
            'report_type': 'daily_activity',
            'subject': {'$regex': target_date},
            'status': {'$in': ['SENT', 'SENT_SANDBOX_PREVIEW']}
        })
        if already_sent:
            return True, f"Daily report for {target_date} already sent to {to_email}. Skipping.", None

    report = build_daily_activity_report(comp_id_str, target_date)
    subject = f"Yesterday’s Activity Report for {target_date} - {report['company_name']}"
    html_body = email_service.render_daily_activity_html(report)

    # Generate and attach official 2-page landscape Daily Activity PDF
    attachments = []
    try:
        import pdf_generator
        comp_info = database.get_company_by_id(comp_id_str)
        activity_data = build_yesterdays_activity_full_data(comp_id_str, target_date=target_date)
        pdf_buffer = pdf_generator.generate_yesterdays_activity_report_pdf(activity_data, company_info=comp_info)
        pdf_filename = f"Yesterday’s Activity Report – {target_date}.pdf"
        attachments.append({
            'filename': pdf_filename,
            'content': pdf_buffer.getvalue()
        })
    except Exception as pdf_err:
        print(f"[Scheduler Warning] Failed to generate Daily Activity PDF attachment for {comp_id_str}: {pdf_err}")

    success, msg = email_service.send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_body,
        attachments=attachments,
        company_id=comp_id_str,
        report_type='daily_activity'
    )
    return success, msg, report

def send_monthly_salary_email(company_id, target_month=None, force=False):
    """
    Generates and sends monthly payroll statement to the company's registered email.
    Idempotent: skips if already sent for this month unless force=True.
    """
    db = database.get_db()
    if not target_month:
        target_month = get_previous_month_ist()

    comp_id_str = str(company_id)
    comp = db.company_admin.find_one({'id': comp_id_str})
    if not comp or not comp.get('email'):
        return False, f"Company {comp_id_str} not found or has no registered email.", None

    # Check if automatic email reports are turned off for this company
    if not force and comp.get('auto_email_reports') is False:
        return False, f"Automatic email reports are turned off for {comp.get('company_name', comp_id_str)}. Skipping.", None

    to_email = comp['email'].strip()

    if not force:
        already_sent = db.email_logs.find_one({
            'company_id': comp_id_str,
            'report_type': 'monthly_salary',
            'subject': {'$regex': target_month},
            'status': {'$in': ['SENT', 'SENT_SANDBOX_PREVIEW']}
        })
        if already_sent:
            return True, f"Monthly salary report for {target_month} already sent to {to_email}. Skipping.", None

    report = build_monthly_salary_report(comp_id_str, target_month)
    month_year_display = email_service.format_month_year(target_month)
    report['month_year_str'] = month_year_display
    subject = f"Monthly Salary Report for {month_year_display} - {report['company_name']}"
    html_body = email_service.render_monthly_salary_html(report)

    # Generate and attach official Monthly Payroll PDF
    attachments = []
    try:
        import pdf_generator
        comp_info = database.get_company_by_id(comp_id_str)
        result = database.get_salary_reports(
            start_month=target_month,
            end_month=target_month,
            limit=1000,
            company_id=comp_id_str
        )
        sal_data = result.get('data', []) if isinstance(result, dict) else []
        pdf_buffer = pdf_generator.generate_salary_report_pdf(sal_data, company_info=comp_info)
        pdf_filename = f"Monthly Salary Report – {month_year_display}.pdf"
        attachments.append({
            'filename': pdf_filename,
            'content': pdf_buffer.getvalue()
        })
    except Exception as pdf_err:
        print(f"[Scheduler Warning] Failed to generate Monthly Salary PDF attachment for {comp_id_str}: {pdf_err}")

    success, msg = email_service.send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_body,
        attachments=attachments,
        company_id=comp_id_str,
        report_type='monthly_salary'
    )
    return success, msg, report

def dispatch_all_daily_reports(target_date=None, force=False):
    """Dispatches daily activity reports to ALL registered companies in MongoDB."""
    db = database.get_db()
    companies = list(db.company_admin.find({}))
    results = []
    print(f"[Scheduler] Dispatching daily activity reports to {len(companies)} registered companies...")

    for comp in companies:
        c_id = comp.get('id')
        c_name = comp.get('company_name', '')
        c_email = comp.get('email', '')
        if not c_id or not c_email:
            continue
        if comp.get('auto_email_reports') is False and not force:
            print(f"[Scheduler] Skipping company '{c_name}' (ID: {c_id}) - Automatic email reports turned off.")
            results.append({'company_id': c_id, 'company_name': c_name, 'email': c_email, 'status': 'SKIPPED', 'message': 'Automatic email reports disabled by Super Admin.'})
            continue
        try:
            ok, msg, _ = send_daily_activity_email(c_id, target_date=target_date, force=force)
            results.append({'company_id': c_id, 'company_name': c_name, 'email': c_email, 'status': 'SENT' if ok else 'FAILED', 'message': msg})
        except Exception as e:
            results.append({'company_id': c_id, 'company_name': c_name, 'email': c_email, 'status': 'ERROR', 'message': str(e)})

    return results

def dispatch_all_monthly_reports(target_month=None, force=False):
    """Dispatches monthly payroll reports to ALL registered companies in MongoDB."""
    db = database.get_db()
    companies = list(db.company_admin.find({}))
    results = []
    print(f"[Scheduler] Dispatching monthly payroll reports to {len(companies)} registered companies...")

    for comp in companies:
        c_id = comp.get('id')
        c_name = comp.get('company_name', '')
        c_email = comp.get('email', '')
        if not c_id or not c_email:
            continue
        if comp.get('auto_email_reports') is False and not force:
            print(f"[Scheduler] Skipping company '{c_name}' (ID: {c_id}) - Automatic email reports turned off.")
            results.append({'company_id': c_id, 'company_name': c_name, 'email': c_email, 'status': 'SKIPPED', 'message': 'Automatic email reports disabled by Super Admin.'})
            continue
        try:
            ok, msg, _ = send_monthly_salary_email(c_id, target_month=target_month, force=force)
            results.append({'company_id': c_id, 'company_name': c_name, 'email': c_email, 'status': 'SENT' if ok else 'FAILED', 'message': msg})
        except Exception as e:
            results.append({'company_id': c_id, 'company_name': c_name, 'email': c_email, 'status': 'ERROR', 'message': str(e)})

    return results

# ----------------- BACKGROUND SCHEDULER DAEMON ----------------- #

def check_and_dispatch_scheduled_reports():
    """
    Evaluates each company's individual email schedule and dispatches reports
    when their configured time / day has arrived.
    - Daily Activity Report: Sent at company.daily_report_time (default '07:00') for yesterday's activity.
    - Monthly Salary Report: Sent on company.monthly_report_day (default 1) at company.daily_report_time for previous month.
    Built-in idempotency ensures no duplicate dispatches even across server reboots.
    """
    try:
        db = database.get_db()
        now = database.get_ist_now()
        cur_time_str = now.strftime('%H:%M')
        cur_day = now.day
        yesterday = get_yesterday_ist()
        prev_month = get_previous_month_ist()

        # Query active companies that have automatic reports enabled
        companies = list(db.company_admin.find({
            'auto_email_reports': {'$ne': False},
            'status': {'$nin': ['Deactive', 'Inactive']}
        }))

        for comp in companies:
            c_id = comp.get('id')
            c_name = comp.get('company_name', '')
            c_email = comp.get('email', '')
            if not c_id or not c_email:
                continue

            c_daily_time = str(comp.get('daily_report_time') or '07:00').strip()
            c_monthly_day = int(comp.get('monthly_report_day') or 1)

            # 1. Daily Report Check:
            if cur_time_str >= c_daily_time:
                try:
                    ok, msg, _ = send_daily_activity_email(c_id, target_date=yesterday, force=False)
                    if ok and "already sent" not in str(msg).lower():
                        print(f"[Scheduler Daemon] Sent scheduled daily report to '{c_name}' ({c_email}) at {cur_time_str} IST.")
                except Exception as e:
                    print(f"[Scheduler Daemon Error] Failed daily report for '{c_name}': {e}")

            # 2. Monthly Report Check:
            if cur_day >= c_monthly_day and cur_time_str >= c_daily_time:
                try:
                    ok, msg, _ = send_monthly_salary_email(c_id, target_month=prev_month, force=False)
                    if ok and "already sent" not in str(msg).lower():
                        print(f"[Scheduler Daemon] Sent scheduled monthly payroll report to '{c_name}' ({c_email}) on day {cur_day} at {cur_time_str} IST.")
                except Exception as e:
                    print(f"[Scheduler Daemon Error] Failed monthly report for '{c_name}': {e}")
    except Exception as e:
        print(f"[Scheduler Daemon Check Error] {e}")

def _scheduler_worker():
    """Worker loop that runs scheduled jobs in background."""
    print("[Scheduler Daemon] Started background dynamic report scheduler worker.")
    
    while True:
        try:
            check_and_dispatch_scheduled_reports()
        except Exception as e:
            print(f"[Scheduler Daemon Exception] {e}")
        time.sleep(30)

def start_scheduler():
    """Starts the background scheduler daemon thread if not already running."""
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread is None or not _scheduler_thread.is_alive():
            _scheduler_thread = threading.Thread(target=_scheduler_worker, daemon=True, name="ReportSchedulerDaemon")
            _scheduler_thread.start()
            print("[Scheduler] Report scheduler daemon successfully started.")
