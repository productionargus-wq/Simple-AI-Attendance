import os
import json
import base64
import requests
from datetime import datetime
from dotenv import load_dotenv
import database

load_dotenv()

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FALLBACK_FROM = "ARGUS ATTENDANCE <onboarding@resend.dev>"

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

def format_month_year(period_str):
    """Converts '2026-09' or '09-2026' into 'September 2026'."""
    if not period_str:
        return ""
    try:
        parts = str(period_str).strip().split('-')
        if len(parts) == 2:
            if len(parts[0]) == 4:  # YYYY-MM
                y, m = int(parts[0]), int(parts[1])
                return datetime(y, m, 1).strftime("%B %Y")
            elif len(parts[1]) == 4:  # MM-YYYY
                m, y = int(parts[0]), int(parts[1])
                return datetime(y, m, 1).strftime("%B %Y")
    except Exception:
        pass
    return str(period_str)

def render_daily_activity_html(report_data):
    """
    Renders an executive letter HTML email for Yesterday's Activity Report.
    Matches exact corporate letter template:
    - Dear {{Client Name}},
    - Please find attached the Yesterday’s Activity Report for {{DATE}}, generated automatically from Argus Attendance.
    - The report includes the recorded attendance and activity details for your organization for the specified date.
    - Attachment: Yesterday’s Activity Report – {{DATE}}.pdf
    - This is an automated email generated by Argus Attendance. If you have any questions or require assistance regarding the report, please contact our support team.
    - Regards, Argus Attendance / Powered by ARGUSCNC / Version 5.1
    """
    comp_name = report_data.get('company_name') or 'Client'
    date_str = report_data.get('date_str') or report_data.get('target_date') or ''

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="x-apple-disable-message-reformatting">
  <title>Yesterday’s Activity Report – {date_str}</title>
  <style>
    @media only screen and (max-width: 600px) {{
      .email-body {{ padding: 12px 8px !important; }}
      .email-container {{ width: 100% !important; border-radius: 6px !important; }}
      .email-header {{ padding: 18px 18px !important; }}
      .email-content {{ padding: 22px 18px !important; }}
      .attachment-box {{ padding: 12px 14px !important; }}
    }}
  </style>
</head>
<body class="email-body" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px 12px; color: #1e293b; -webkit-font-smoothing: antialiased; line-height: 1.6;">
  
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="width: 100%; border-collapse: collapse;">
    <tr>
      <td align="center">
        
        <table class="email-container" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; text-align: left;">
          
          <!-- Header Bar -->
          <tr>
            <td class="email-header" style="background-color: #1e293b; padding: 22px 28px; text-align: left; border-bottom: 3px solid #0284c7;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <div style="font-size: 19px; font-weight: 800; color: #ffffff; letter-spacing: 0.8px; text-transform: uppercase;">
                      ARGUS ATTENDANCE
                    </div>
                    <div style="font-size: 12px; color: #94a3b8; font-weight: 500; margin-top: 3px;">
                      Automated Operational Reporting System
                    </div>
                  </td>
                  <td align="right" valign="middle">
                    <span style="background-color: #0369a1; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;">
                      Daily Report
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Letter Content -->
          <tr>
            <td class="email-content" style="padding: 28px 28px 24px 28px; font-size: 15px; color: #334155;">
              
              <p style="margin: 0 0 18px 0; font-size: 15.5px; color: #1e293b; font-weight: 600;">
                Dear {comp_name},
              </p>

              <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.65; color: #334155;">
                Please find attached the <strong>Yesterday’s Activity Report</strong> for <strong>{date_str}</strong>, generated automatically from <strong>Argus Attendance</strong>.
              </p>

              <p style="margin: 0 0 22px 0; font-size: 15px; line-height: 1.65; color: #334155;">
                The report includes the recorded attendance and activity details for your organization for the specified date.
              </p>

              <!-- Attachment Box -->
              <div class="attachment-box" style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #0284c7; border-radius: 6px; padding: 14px 18px; margin: 0 0 22px 0;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="width: 100%;">
                  <tr>
                    <td width="36" valign="middle" style="padding-right: 12px; width: 36px;">
                      <div style="background-color: #e0f2fe; color: #0284c7; width: 34px; height: 34px; border-radius: 6px; text-align: center; line-height: 34px; font-size: 17px; font-weight: bold;">
                        &#128196;
                      </div>
                    </td>
                    <td valign="middle">
                      <div style="font-size: 14px; font-weight: 700; color: #0f172a;">
                        <strong>Attachment:</strong> Yesterday’s Activity Report – {date_str}.pdf
                      </div>
                      <div style="font-size: 12px; color: #64748b; margin-top: 2px;">
                        Attached PDF file &bull; Official Daily Attendance Register
                      </div>
                    </td>
                    <td align="right" valign="middle" style="padding-left: 8px;">
                      <span style="background-color: #0284c7; color: #ffffff; padding: 4px 9px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase;">
                        PDF
                      </span>
                    </td>
                  </tr>
                </table>
              </div>

              <p style="margin: 0 0 24px 0; font-size: 14.5px; line-height: 1.65; color: #475569;">
                This is an automated email generated by <strong>Argus Attendance</strong>. If you have any questions or require assistance regarding the report, please contact our support team.
              </p>

              <!-- Sign-off Block -->
              <div style="border-top: 1px solid #e2e8f0; padding-top: 18px; margin-top: 20px; font-size: 14.5px; line-height: 1.55; color: #334155;">
                Regards,<br>
                <strong style="color: #0f172a; font-size: 15px;">Argus Attendance</strong><br>
                <span style="color: #475569;">Powered by <strong style="color: #0f172a;">ARGUSCNC</strong></span><br>
                <span style="color: #64748b; font-size: 13px; font-weight: 600;">Version 5.1</span>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; padding: 16px 24px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #94a3b8; line-height: 1.5;">
              This is an automated notification dispatched by <strong>Argus Attendance</strong>.<br>
              &copy; 2026 ARGUS ATTENDANCE &bull; Powered by ARGUSCNC
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>

</body>
</html>"""

def render_monthly_salary_html(report_data):
    """
    Renders an executive letter HTML email for Monthly Salary Report.
    Matches exact corporate letter template:
    - Dear {{Client Name}},
    - Please find attached the Monthly Salary Report for {{MONTH}} {{YEAR}}, automatically generated from Argus Attendance.
    - The report provides the consolidated salary details for all employees based on the attendance and payroll records available for the selected month.
    - Attachment: Monthly Salary Report – {{MONTH}} {{YEAR}}.pdf
    - Please review the report for your records. If you have any questions or require assistance regarding the report, please contact our support team.
    - This is an automated email generated by Argus Attendance.
    - Regards, Argus Attendance / Powered by ARGUSCNC / Version 5.1
    """
    comp_name = report_data.get('company_name') or 'Client'
    month_year = report_data.get('month_year_str') or format_month_year(report_data.get('pay_period', ''))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="x-apple-disable-message-reformatting">
  <title>Monthly Salary Report – {month_year}</title>
  <style>
    @media only screen and (max-width: 600px) {{
      .email-body {{ padding: 12px 8px !important; }}
      .email-container {{ width: 100% !important; border-radius: 6px !important; }}
      .email-header {{ padding: 18px 18px !important; }}
      .email-content {{ padding: 22px 18px !important; }}
      .attachment-box {{ padding: 12px 14px !important; }}
    }}
  </style>
</head>
<body class="email-body" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f9; margin: 0; padding: 24px 12px; color: #1e293b; -webkit-font-smoothing: antialiased; line-height: 1.6;">
  
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="width: 100%; border-collapse: collapse;">
    <tr>
      <td align="center">
        
        <table class="email-container" cellpadding="0" cellspacing="0" border="0" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 14px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; text-align: left;">
          
          <!-- Header Bar -->
          <tr>
            <td class="email-header" style="background-color: #1e293b; padding: 22px 28px; text-align: left; border-bottom: 3px solid #16a34a;">
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                <tr>
                  <td>
                    <div style="font-size: 19px; font-weight: 800; color: #ffffff; letter-spacing: 0.8px; text-transform: uppercase;">
                      ARGUS ATTENDANCE
                    </div>
                    <div style="font-size: 12px; color: #94a3b8; font-weight: 500; margin-top: 3px;">
                      Automated Operational Reporting System
                    </div>
                  </td>
                  <td align="right" valign="middle">
                    <span style="background-color: #15803d; color: #ffffff; padding: 4px 10px; border-radius: 4px; font-size: 11px; font-weight: 700; letter-spacing: 0.5px; text-transform: uppercase;">
                      Monthly Payroll
                    </span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Letter Content -->
          <tr>
            <td class="email-content" style="padding: 28px 28px 24px 28px; font-size: 15px; color: #334155;">
              
              <p style="margin: 0 0 18px 0; font-size: 15.5px; color: #1e293b; font-weight: 600;">
                Dear {comp_name},
              </p>

              <p style="margin: 0 0 16px 0; font-size: 15px; line-height: 1.65; color: #334155;">
                Please find attached the <strong>Monthly Salary Report</strong> for <strong>{month_year}</strong>, automatically generated from <strong>Argus Attendance</strong>.
              </p>

              <p style="margin: 0 0 22px 0; font-size: 15px; line-height: 1.65; color: #334155;">
                The report provides the consolidated salary details for all employees based on the attendance and payroll records available for the selected month.
              </p>

              <!-- Attachment Box -->
              <div class="attachment-box" style="background-color: #f8fafc; border: 1px solid #cbd5e1; border-left: 4px solid #16a34a; border-radius: 6px; padding: 14px 18px; margin: 0 0 22px 0;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="width: 100%;">
                  <tr>
                    <td width="36" valign="middle" style="padding-right: 12px; width: 36px;">
                      <div style="background-color: #dcfce7; color: #16a34a; width: 34px; height: 34px; border-radius: 6px; text-align: center; line-height: 34px; font-size: 17px; font-weight: bold;">
                        &#128196;
                      </div>
                    </td>
                    <td valign="middle">
                      <div style="font-size: 14px; font-weight: 700; color: #0f172a;">
                        <strong>Attachment:</strong> Monthly Salary Report – {month_year}.pdf
                      </div>
                      <div style="font-size: 12px; color: #64748b; margin-top: 2px;">
                        Attached PDF file &bull; Official Monthly Salary Statement
                      </div>
                    </td>
                    <td align="right" valign="middle" style="padding-left: 8px;">
                      <span style="background-color: #16a34a; color: #ffffff; padding: 4px 9px; border-radius: 4px; font-size: 11px; font-weight: 700; text-transform: uppercase;">
                        PDF
                      </span>
                    </td>
                  </tr>
                </table>
              </div>

              <p style="margin: 0 0 16px 0; font-size: 14.5px; line-height: 1.65; color: #475569;">
                Please review the report for your records. If you have any questions or require assistance regarding the report, please contact our support team.
              </p>

              <p style="margin: 0 0 24px 0; font-size: 14.5px; line-height: 1.65; color: #475569;">
                This is an automated email generated by <strong>Argus Attendance</strong>.
              </p>

              <!-- Sign-off Block -->
              <div style="border-top: 1px solid #e2e8f0; padding-top: 18px; margin-top: 20px; font-size: 14.5px; line-height: 1.55; color: #334155;">
                Regards,<br>
                <strong style="color: #0f172a; font-size: 15px;">Argus Attendance</strong><br>
                <span style="color: #475569;">Powered by <strong style="color: #0f172a;">ARGUSCNC</strong></span><br>
                <span style="color: #64748b; font-size: 13px; font-weight: 600;">Version 5.1</span>
              </div>

            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="background-color: #f8fafc; padding: 16px 24px; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #94a3b8; line-height: 1.5;">
              This is an automated notification dispatched by <strong>Argus Attendance</strong>.<br>
              &copy; 2026 ARGUS ATTENDANCE &bull; Powered by ARGUSCNC
            </td>
          </tr>

        </table>

      </td>
    </tr>
  </table>

</body>
</html>"""
