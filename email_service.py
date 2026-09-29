import os
import json
import base64
import requests
from datetime import datetime
from dotenv import load_dotenv
import database

load_dotenv()

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FALLBACK_FROM = "Argus Simple Attendance <onboarding@resend.dev>"

def get_resend_config():
    """Retrieve Resend API key and sender configuration from environment."""
    api_key = (os.environ.get('RESEND_API_KEY') or '').strip()
    from_email = (os.environ.get('RESEND_FROM') or '').strip() or DEFAULT_FALLBACK_FROM
    return api_key, from_email

def send_email(to_email, subject, html_content, attachments=None, company_id=None, report_type='general'):
    """
    Sends an email via Resend REST API and logs the result in MongoDB db.email_logs.
    Includes automatic fallback to onboarding@resend.dev if a custom domain is not yet verified.
    
    attachments: list of dicts [{'filename': 'report.pdf', 'content': bytes}]
    """
    db = database.get_db()
    api_key, from_email = get_resend_config()

    if not api_key:
        error_msg = "Resend API key (RESEND_API_KEY) is not configured in environment."
        print(f"[EmailService Error] {error_msg}")
        _log_email(db, to_email, subject, 'FAILED', error_msg, company_id, report_type)
        return False, error_msg

    # Format attachments for Resend API (base64 encoded)
    resend_attachments = []
    if attachments:
        for att in attachments:
            fname = att.get('filename', 'attachment.pdf')
            content = att.get('content')
            if isinstance(content, (bytes, bytearray)):
                b64_content = base64.b64encode(content).decode('utf-8')
            elif isinstance(content, str):
                b64_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
            else:
                continue
            resend_attachments.append({
                'filename': fname,
                'content': b64_content
            })

    payload = {
        'from': from_email,
        'to': [to_email.strip()],
        'subject': subject,
        'html': html_content
    }
    if resend_attachments:
        payload['attachments'] = resend_attachments

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    try:
        resp = requests.post(RESEND_API_URL, headers=headers, json=payload, timeout=15)
        
        # If 403 domain unverified error occurs, try fallback to onboarding@resend.dev
        if resp.status_code == 403 and from_email != DEFAULT_FALLBACK_FROM and ("not verified" in resp.text.lower() or "verify" in resp.text.lower()):
            print(f"[EmailService] Domain unverified for '{from_email}'. Retrying with fallback '{DEFAULT_FALLBACK_FROM}'...")
            payload['from'] = DEFAULT_FALLBACK_FROM
            resp = requests.post(RESEND_API_URL, headers=headers, json=payload, timeout=15)

        # If Resend sandbox restricts to own email address, redirect to technologiesargus@gmail.com for preview
        if resp.status_code == 403 and ("own email address" in resp.text.lower() or "only send testing" in resp.text.lower()):
            sandbox_dest = "technologiesargus@gmail.com"
            print(f"[EmailService Sandbox] External recipient '{to_email}' requires verified domain on Resend. Delivering preview to '{sandbox_dest}'...")
            payload['to'] = [sandbox_dest]
            payload['subject'] = f"[Preview for {to_email}] " + subject
            resp = requests.post(RESEND_API_URL, headers=headers, json=payload, timeout=15)

        if resp.status_code in [200, 201]:
            data = resp.json()
            email_id = data.get('id', '')
            status_label = 'SENT' if payload['to'] == [to_email.strip()] else 'SENT_SANDBOX_PREVIEW'
            print(f"[EmailService] Email successfully sent to {payload['to']} (ID: {email_id})")
            _log_email(db, to_email, subject, status_label, f"Success (ID: {email_id}, Delivered to: {payload['to']})", company_id, report_type, email_id)
            return True, email_id
        else:
            err = resp.text
            print(f"[EmailService Error] Failed to send email to {to_email}. Code: {resp.status_code}, Response: {err}")
            _log_email(db, to_email, subject, 'FAILED', f"HTTP {resp.status_code}: {err}", company_id, report_type)
            return False, err
    except Exception as e:
        err_msg = str(e)
        print(f"[EmailService Exception] {err_msg}")
        _log_email(db, to_email, subject, 'FAILED', err_msg, company_id, report_type)
        return False, err_msg

def _log_email(db, to_email, subject, status, details, company_id, report_type, message_id=None):
    """Audits email dispatch attempt in MongoDB db.email_logs."""
    try:
        doc = {
            'to_email': to_email,
            'company_id': str(company_id or 'ARGUS_MASTER'),
            'report_type': report_type,
            'subject': subject,
            'status': status,
            'details': details,
            'message_id': message_id,
            'timestamp': database.get_ist_now().strftime("%d-%m-%Y %I:%M:%S %p"),
            'created_at': database.get_ist_now().isoformat()
        }
        db.email_logs.insert_one(doc)
    except Exception as e:
        print(f"Warning: Could not write to db.email_logs: {e}")

# ----------------- HTML TEMPLATE GENERATORS ----------------- #

def render_daily_activity_html(report_data):
    """
    Renders a responsive, executive HTML email digest for yesterday's activities.
    report_data keys:
      - company_name
      - date_str (Yesterday's date)
      - total_employees
      - total_punches
      - total_hours_worked
      - total_working_salary
      - punches: list of punch dicts
      - manual_entries: list of manual entry dicts
      - payments: list of payment dicts
    """
    comp_name = report_data.get('company_name', 'Company')
    date_str = report_data.get('date_str', '')
    total_emp = report_data.get('total_employees', 0)
    total_punches = report_data.get('total_punches', 0)
    total_hours = report_data.get('total_hours_worked', '00:00')
    total_sal = report_data.get('total_working_salary', 0.0)
    punches = report_data.get('punches', [])
    manual_entries = report_data.get('manual_entries', [])
    payments = report_data.get('payments', [])

    # Punches Table Rows
    punches_rows = ""
    if punches:
        for p in punches:
            badge_color = "#198754" if p.get('day_credit_type') == 'Full Day' else ("#ffc107" if 'Half' in p.get('day_credit_type', '') else "#6c757d")
            punches_rows += f"""
            <tr style="border-bottom: 1px solid #e2e8f0; font-size: 13px;">
              <td style="padding: 10px 8px; font-weight: 600; color: #2c3e50;">{p.get('employee_name', '')}</td>
              <td style="padding: 10px 8px; color: #475569;">{p.get('entry_time', '-')}</td>
              <td style="padding: 10px 8px; color: #475569;">{p.get('exit_time', '-')}</td>
              <td style="padding: 10px 8px; font-weight: 700; color: #1e293b;">{p.get('working_hours', '00:00')}</td>
              <td style="padding: 10px 8px; color: #64748b;">{p.get('shift_variance', '00:00')}</td>
              <td style="padding: 10px 8px;">
                <span style="background-color: {badge_color}; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700;">
                  {p.get('day_credit_type', 'Present')}
                </span>
              </td>
              <td style="padding: 10px 8px; font-weight: 700; color: #0f172a;">Rs. {p.get('working_salary', 0)}</td>
            </tr>
            """
    else:
        punches_rows = """
        <tr>
          <td colspan="7" style="padding: 16px; text-align: center; color: #94a3b8; font-size: 13px;">
            No face attendance punches recorded for this day.
          </td>
        </tr>
        """

    # Manual Entries Table Rows
    manual_rows = ""
    if manual_entries:
        for m in manual_entries:
            manual_rows += f"""
            <tr style="border-bottom: 1px solid #e2e8f0; font-size: 13px;">
              <td style="padding: 10px 8px; font-weight: 600; color: #2c3e50;">{m.get('employee_name', '')}</td>
              <td style="padding: 10px 8px; color: #475569;">{m.get('hours', '00:00')}</td>
              <td style="padding: 10px 8px; color: #475569;">{m.get('status', '-')}</td>
              <td style="padding: 10px 8px; color: #64748b;">{m.get('mode', 'Hours')}</td>
              <td style="padding: 10px 8px; font-weight: 700; color: #0f172a;">Rs. {m.get('working_salary', 0)}</td>
            </tr>
            """
    else:
        manual_rows = """
        <tr>
          <td colspan="5" style="padding: 16px; text-align: center; color: #94a3b8; font-size: 13px;">
            No manual adjustments recorded for this day.
          </td>
        </tr>
        """

    # Payments Table Rows
    payments_rows = ""
    if payments:
        for pay in payments:
            payments_rows += f"""
            <tr style="border-bottom: 1px solid #e2e8f0; font-size: 13px;">
              <td style="padding: 10px 8px; font-weight: 600; color: #2c3e50;">{pay.get('employee_name', '')}</td>
              <td style="padding: 10px 8px; color: #475569;">{pay.get('reason', 'Payment')}</td>
              <td style="padding: 10px 8px; font-weight: 700; color: #0f172a;">Rs. {pay.get('amount', 0)}</td>
              <td style="padding: 10px 8px; color: #64748b;">{pay.get('timestamp', pay.get('payment_date', ''))}</td>
            </tr>
            """
    else:
        payments_rows = """
        <tr>
          <td colspan="4" style="padding: 16px; text-align: center; color: #94a3b8; font-size: 13px;">
            No payments or advance repayments logged for this day.
          </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Daily Activity Digest - {comp_name}</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px; color: #1e293b;">
      
      <div style="max-width: 680px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
        
        <!-- Header -->
        <div style="background-color: #3d6078; padding: 24px; color: #ffffff; text-align: left;">
          <div style="font-size: 13px; font-weight: 700; color: #ffd166; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px;">
            ARGUS TECHNOLOGIES &bull; SUPER ADMIN
          </div>
          <div style="font-size: 20px; font-weight: 800; margin-bottom: 4px;">
            Daily Employee Activity Report
          </div>
          <div style="font-size: 13px; color: #e2e8f0;">
            Organisation: <strong>{comp_name}</strong> &bull; Activity Date: <strong>{date_str}</strong>
          </div>
        </div>

        <div style="padding: 24px;">
          
          <!-- Executive Stats Badges -->
          <div style="display: flex; gap: 12px; margin-bottom: 24px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 120px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; text-align: center;">
              <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Staff Active</div>
              <div style="font-size: 20px; font-weight: 800; color: #3d6078; margin-top: 4px;">{total_emp}</div>
            </div>
            <div style="flex: 1; min-width: 120px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; text-align: center;">
              <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Total Punches</div>
              <div style="font-size: 20px; font-weight: 800; color: #198754; margin-top: 4px;">{total_punches}</div>
            </div>
            <div style="flex: 1; min-width: 120px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; text-align: center;">
              <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Hours Worked</div>
              <div style="font-size: 20px; font-weight: 800; color: #0284c7; margin-top: 4px;">{total_hours}</div>
            </div>
            <div style="flex: 1; min-width: 120px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; text-align: center;">
              <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Daily Payroll</div>
              <div style="font-size: 20px; font-weight: 800; color: #d97706; margin-top: 4px;">Rs. {total_sal:.0f}</div>
            </div>
          </div>

          <!-- Section 1: Biometric Attendance Punches -->
          <div style="margin-bottom: 28px;">
            <div style="font-size: 14px; font-weight: 800; color: #1e293b; border-bottom: 2px solid #3d6078; padding-bottom: 6px; margin-bottom: 12px;">
              1. Biometric Face Attendance Punches ({len(punches)})
            </div>
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
              <thead>
                <tr style="background-color: #f8fafc; font-size: 11px; font-weight: 800; color: #64748b; text-transform: uppercase; border-bottom: 2px solid #e2e8f0;">
                  <th style="padding: 8px;">Employee</th>
                  <th style="padding: 8px;">Entry</th>
                  <th style="padding: 8px;">Exit</th>
                  <th style="padding: 8px;">Hours</th>
                  <th style="padding: 8px;">Variance</th>
                  <th style="padding: 8px;">Status</th>
                  <th style="padding: 8px;">Salary</th>
                </tr>
              </thead>
              <tbody>
                {punches_rows}
              </tbody>
            </table>
          </div>

          <!-- Section 2: Manual Entries -->
          <div style="margin-bottom: 28px;">
            <div style="font-size: 14px; font-weight: 800; color: #1e293b; border-bottom: 2px solid #3d6078; padding-bottom: 6px; margin-bottom: 12px;">
              2. Manual Attendance Adjustments ({len(manual_entries)})
            </div>
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
              <thead>
                <tr style="background-color: #f8fafc; font-size: 11px; font-weight: 800; color: #64748b; text-transform: uppercase; border-bottom: 2px solid #e2e8f0;">
                  <th style="padding: 8px;">Employee</th>
                  <th style="padding: 8px;">Hours</th>
                  <th style="padding: 8px;">Status / Reason</th>
                  <th style="padding: 8px;">Mode</th>
                  <th style="padding: 8px;">Salary</th>
                </tr>
              </thead>
              <tbody>
                {manual_rows}
              </tbody>
            </table>
          </div>

          <!-- Section 3: Payments & Deductions -->
          <div style="margin-bottom: 24px;">
            <div style="font-size: 14px; font-weight: 800; color: #1e293b; border-bottom: 2px solid #3d6078; padding-bottom: 6px; margin-bottom: 12px;">
              3. Payments, Allowances & Advances ({len(payments)})
            </div>
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
              <thead>
                <tr style="background-color: #f8fafc; font-size: 11px; font-weight: 800; color: #64748b; text-transform: uppercase; border-bottom: 2px solid #e2e8f0;">
                  <th style="padding: 8px;">Employee</th>
                  <th style="padding: 8px;">Type / Reason</th>
                  <th style="padding: 8px;">Amount</th>
                  <th style="padding: 8px;">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {payments_rows}
              </tbody>
            </table>
          </div>

        </div>

        <!-- Footer -->
        <div style="background-color: #f8fafc; padding: 18px 24px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b;">
          This is an automated operational report dispatched daily by <strong>ARGUS TECHNOLOGIES</strong> AI Attendance Engine.<br>
          For queries or administrative support, please contact your Argus Platform Administrator.
        </div>

      </div>

    </body>
    </html>
    """

def render_monthly_salary_html(report_data):
    """
    Renders an executive Monthly Salary and Payroll Summary HTML email.
    report_data keys:
      - company_name
      - pay_period (e.g. September 2026 / 2026-09)
      - total_employees
      - total_working_days
      - total_gross_salary
      - total_allowance
      - total_deductions
      - total_net_payout
      - employee_payslips: list of employee payslip summary dicts
    """
    comp_name = report_data.get('company_name', 'Company')
    pay_period = report_data.get('pay_period', '')
    total_emp = report_data.get('total_employees', 0)
    total_gross = report_data.get('total_gross_salary', 0.0)
    total_allow = report_data.get('total_allowance', 0.0)
    total_ded = report_data.get('total_deductions', 0.0)
    total_net = report_data.get('total_net_payout', 0.0)
    payslips = report_data.get('employee_payslips', [])

    emp_rows = ""
    if payslips:
        for p in payslips:
            emp_rows += f"""
            <tr style="border-bottom: 1px solid #e2e8f0; font-size: 13px;">
              <td style="padding: 10px 8px; font-weight: 600; color: #2c3e50;">{p.get('employee_name', '')}</td>
              <td style="padding: 10px 8px; color: #475569;">{p.get('designation', '-')}</td>
              <td style="padding: 10px 8px; color: #64748b;">{p.get('salary_basis_label', p.get('salary_type', 'Day-Based'))}</td>
              <td style="padding: 10px 8px; text-align: center; color: #1e293b;">{p.get('working_days', 0)}</td>
              <td style="padding: 10px 8px; text-align: center; color: #1e293b;">{p.get('total_working_hours', '00:00')}</td>
              <td style="padding: 10px 8px; font-weight: 700; color: #0f172a;">Rs. {p.get('basic_salary', 0)}</td>
              <td style="padding: 10px 8px; color: #16a34a;">Rs. {p.get('allowance', 0) + p.get('incentive', 0)}</td>
              <td style="padding: 10px 8px; color: #dc2626;">Rs. {p.get('total_deduction', 0)}</td>
              <td style="padding: 10px 8px; font-weight: 800; color: #15803d;">Rs. {p.get('net_pay', 0)}</td>
            </tr>
            """
    else:
        emp_rows = """
        <tr>
          <td colspan="9" style="padding: 16px; text-align: center; color: #94a3b8; font-size: 13px;">
            No employee salary records found for this period.
          </td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>Monthly Salary Report - {comp_name}</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px; color: #1e293b;">
      
      <div style="max-width: 760px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;">
        
        <!-- Header -->
        <div style="background-color: #3d6078; padding: 26px; color: #ffffff; text-align: left;">
          <div style="font-size: 13px; font-weight: 700; color: #ffd166; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 4px;">
            ARGUS TECHNOLOGIES &bull; SUPER ADMIN
          </div>
          <div style="font-size: 22px; font-weight: 800; margin-bottom: 4px;">
            Monthly Company Payroll & Salary Statement
          </div>
          <div style="font-size: 14px; color: #e2e8f0;">
            Organisation: <strong>{comp_name}</strong> &bull; Pay Period: <strong>{pay_period}</strong>
          </div>
        </div>

        <div style="padding: 24px;">
          
          <!-- Financial Overview Cards -->
          <div style="display: flex; gap: 12px; margin-bottom: 26px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 140px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; text-align: center;">
              <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Employees</div>
              <div style="font-size: 22px; font-weight: 800; color: #3d6078; margin-top: 4px;">{total_emp}</div>
            </div>
            <div style="flex: 1; min-width: 140px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; text-align: center;">
              <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Gross Basic Salary</div>
              <div style="font-size: 22px; font-weight: 800; color: #1e293b; margin-top: 4px;">Rs. {total_gross:.0f}</div>
            </div>
            <div style="flex: 1; min-width: 140px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; text-align: center;">
              <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Allowances / Bonus</div>
              <div style="font-size: 22px; font-weight: 800; color: #16a34a; margin-top: 4px;">Rs. {total_allow:.0f}</div>
            </div>
            <div style="flex: 1; min-width: 140px; background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 14px; text-align: center;">
              <div style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase;">Advance Deductions</div>
              <div style="font-size: 22px; font-weight: 800; color: #dc2626; margin-top: 4px;">Rs. {total_ded:.0f}</div>
            </div>
            <div style="flex: 1; min-width: 140px; background-color: #ecfdf5; border: 2px solid #10b981; border-radius: 6px; padding: 14px; text-align: center;">
              <div style="font-size: 11px; font-weight: 800; color: #065f46; text-transform: uppercase;">Total Net Payout</div>
              <div style="font-size: 22px; font-weight: 900; color: #047857; margin-top: 4px;">Rs. {total_net:.0f}</div>
            </div>
          </div>

          <!-- Detailed Breakdown Table -->
          <div>
            <div style="font-size: 15px; font-weight: 800; color: #1e293b; border-bottom: 2px solid #3d6078; padding-bottom: 8px; margin-bottom: 12px;">
              Staff Monthly Payroll Breakdown ({len(payslips)} Employees)
            </div>
            <div style="overflow-x: auto;">
              <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                  <tr style="background-color: #f8fafc; font-size: 11px; font-weight: 800; color: #64748b; text-transform: uppercase; border-bottom: 2px solid #e2e8f0;">
                    <th style="padding: 8px;">Employee</th>
                    <th style="padding: 8px;">Designation</th>
                    <th style="padding: 8px;">Basis</th>
                    <th style="padding: 8px; text-align: center;">Days</th>
                    <th style="padding: 8px; text-align: center;">Hours</th>
                    <th style="padding: 8px;">Basic</th>
                    <th style="padding: 8px;">Allowances</th>
                    <th style="padding: 8px;">Deductions</th>
                    <th style="padding: 8px;">Net Pay</th>
                  </tr>
                </thead>
                <tbody>
                  {emp_rows}
                </tbody>
              </table>
            </div>
          </div>

        </div>

        <!-- Footer -->
        <div style="background-color: #f8fafc; padding: 18px 24px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b;">
          This statement was generated automatically by <strong>ARGUS TECHNOLOGIES</strong> AI Multi-Tenant B2B Payroll Engine.<br>
          For payroll questions or discrepancy verification, please consult your Super Admin portal.
        </div>

      </div>

    </body>
    </html>
    """
