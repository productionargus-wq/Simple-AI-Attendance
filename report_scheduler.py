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

        if is_improper:
            loc = p.get('entry_location') or 'Remote Location'
            if len(loc) > 40:
                loc = 'Remote Location'
            reason = 'Outside geofence'
            if 'entry after limit' in str(p.get('notes', '')).lower() or 'late' in str(p.get('notes', '')).lower():
                reason = 'Entry after limit'
            elif p.get('shift_variance') and '-' in str(p.get('shift_variance')) and not p.get('shift_variance', '').startswith('-00'):
                reason = 'Outside geofence'

            improper_entries.append({
                'employee_name': emp_name,
                'entry_time': entry_t,
                'distance': dist_str if dist_str else '350 m',
                'location': loc if loc else 'Remote Location',
                'reason': reason
            })
        else:
            loc = 'Office'
            proper_entries.append({
                'employee_name': emp_name,
                'entry_time': entry_t,
                'exit_time': exit_t if exit_t != '-' else '-',
                'working_hours': wh,
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
        sub_at = m.get('submitted_at') or f"{d_slash} 09:00 AM"
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

        manual_entries.append({
            'employee_name': emp_name,
            'date_time': sub_at,
            'type': etype,
            'added_by': added_by,
            'remarks': remarks
        })

    # 4. Payment Entries
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

    # 5. Employee Details
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
    subject = f"Argus Attendance & Activity Digest - {report['company_name']} ({target_date})"
    html_body = email_service.render_daily_activity_html(report)

    success, msg = email_service.send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_body,
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
    subject = f"Monthly Payroll & Salary Report - {report['company_name']} ({target_month})"
    html_body = email_service.render_monthly_salary_html(report)

    success, msg = email_service.send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_body,
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

def _scheduler_worker():
    """Worker loop that runs scheduled jobs in background."""
    print("[Scheduler Daemon] Started background report scheduler worker.")
    
    # Schedule Daily Report every morning at 07:00 IST
    schedule.every().day.at("07:00").do(dispatch_all_daily_reports)
    
    # Schedule Monthly Salary Report on the 1st of every month at 08:00 IST
    def monthly_job_trigger():
        now = database.get_ist_now()
        if now.day == 1:
            print(f"[Scheduler Daemon] 1st of month detected ({now.strftime('%Y-%m-%d')}). Triggering monthly payroll dispatch...")
            dispatch_all_monthly_reports()

    schedule.every().day.at("08:00").do(monthly_job_trigger)

    while True:
        try:
            schedule.run_pending()
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
