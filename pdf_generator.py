import io
import os
import base64
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def build_pdf_header(elements, company_info=None, title=None, subtitle=None):
    """Renders standardized dynamic company header across all generated PDF reports."""
    comp_info = company_info or {}
    comp_name = comp_info.get('company_name') or "ARGUS TECHNOLOGIES"
    comp_addr = comp_info.get('company_address') or comp_info.get('address') or ""
    email = comp_info.get('email') or comp_info.get('company_email') or ""
    phone = comp_info.get('phone') or comp_info.get('company_phone') or ""
    gstin = comp_info.get('gstin') or comp_info.get('company_gstin') or ""

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocHeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=19,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1e3a8a')
    )
    addr_style = ParagraphStyle(
        'DocHeaderAddr',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#475569')
    )
    report_title_style = ParagraphStyle(
        'DocHeaderReportTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#0f172a')
    )

    elements.append(Paragraph(comp_name.upper(), title_style))
    
    if comp_addr:
        elements.append(Spacer(1, 2))
        elements.append(Paragraph(comp_addr, addr_style))

    contact_parts = []
    if email:
        contact_parts.append(f"Email: {email}")
    if phone:
        contact_parts.append(f"Phone: {phone}")
    if gstin:
        contact_parts.append(f"GSTIN: {gstin}")
    if contact_parts:
        elements.append(Spacer(1, 2))
        elements.append(Paragraph(" | ".join(contact_parts), addr_style))

    if title:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(title.upper(), report_title_style))
    if subtitle:
        elements.append(Spacer(1, 2))
        elements.append(Paragraph(subtitle, addr_style))

    elements.append(Spacer(1, 10))

def generate_employee_pdf(emp):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#3d6078')
    )
    
    header_cell_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.HexColor('#2c3e50')
    )
    
    body_label_style = ParagraphStyle(
        'BodyLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#2c3e50')
    )
    
    body_val_style = ParagraphStyle(
        'BodyVal',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#333333')
    )

    elements = []
    
    # Check for employee photo (from MongoDB base64 or disk)
    photo_name = emp.get('photo') or emp.get('photo_filename')
    photo_data = emp.get('photo_data')
    photo_widget = None

    if photo_data and isinstance(photo_data, str) and ',' in photo_data:
        try:
            b64_part = photo_data.split(',', 1)[1]
            p_bytes = base64.b64decode(b64_part)
            photo_widget = RLImage(io.BytesIO(p_bytes), width=70, height=70)
        except Exception:
            photo_widget = None

    if not photo_widget and photo_name:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        possible_paths = [
            os.path.join(base_dir, 'static', 'uploads', str(photo_name)),
            os.path.join(base_dir, 'uploads', str(photo_name)),
            os.path.join('static', 'uploads', str(photo_name)),
            os.path.join('uploads', str(photo_name))
        ]
        for p_path in possible_paths:
            if os.path.exists(p_path):
                try:
                    photo_widget = RLImage(p_path, width=70, height=70)
                    break
                except Exception:
                    photo_widget = None

    # Header logo or company text
    comp_name = emp.get('company_name') or "ARGUS TECHNOLOGIES"
    if photo_widget:
        hdr_text = [
            Paragraph(comp_name, title_style),
            Spacer(1, 4),
            Paragraph("EMPLOYEE DETAILS", subtitle_style)
        ]
        hdr_table = Table([[hdr_text, photo_widget]], colWidths=[440, 100])
        hdr_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
        ]))
        elements.append(hdr_table)
    else:
        elements.append(Paragraph(comp_name, title_style))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("EMPLOYEE DETAILS", subtitle_style))
    elements.append(Spacer(1, 15))
    
    # Format created_at in readable IST format
    raw_created = emp.get('created_at', '')
    created_str = '-'
    if raw_created:
        try:
            if isinstance(raw_created, str):
                dt = datetime.fromisoformat(raw_created.replace('Z', '+00:00'))
            else:
                dt = raw_created
            created_str = dt.strftime('%d/%m/%Y %I:%M:%S %p')
        except Exception:
            created_str = str(raw_created)

    # Fields table
    fields = [
        ("ID", str(emp.get('id', ''))),
        ("EMPLOYEE NAME", str(emp.get('employee_name', ''))),
        ("DESIGNATION", str(emp.get('designation', ''))),
        ("SALARY BASIS", str(emp.get('salary_type', 'hourly')).replace('_', '-').title() + "-Based"),
        ("HOURLY SALARY", str(emp.get('hourly_salary', '0'))),
        ("DAY SALARY", str(emp.get('day_salary', '0'))),
        ("HALF DAY SALARY", str(emp.get('half_day_salary', '0'))),
        ("MOBILE NUMBER", str(emp.get('mobile_number', ''))),
        ("EMAIL ID", str(emp.get('email_id', ''))),
        ("AADHAR NUMBER", str(emp.get('aadhar_number', ''))),
        ("EMERGENCY CONTACT", str(emp.get('emergency_contact', ''))),
        ("JOINING DATE", str(emp.get('joining_date', ''))),
        ("ACCOUNT HOLDER NAME", str(emp.get('account_holder_name', ''))),
        ("UPI NUMBER", str(emp.get('upi_number', ''))),
        ("BANK NAME", str(emp.get('bank_name', ''))),
        ("ACCOUNT NUMBER", str(emp.get('account_number', ''))),
        ("IFSC CODE", str(emp.get('ifsc_code', ''))),
        ("SHIFT HOURS", str(emp.get('shift_hours', ''))),
        ("SHIFT START", str(emp.get('shift_start') or '09:00 AM')),
        ("SHIFT END", str(emp.get('shift_end') or '06:00 PM')),
        ("RECORD CREATED AT", created_str)
    ]
    
    table_data = [
        [Paragraph("INFORMATION", header_cell_style), Paragraph("INFORMATION VALUE", header_cell_style)]
    ]
    
    for label, val in fields:
        table_data.append([
            Paragraph(label, body_label_style),
            Paragraph(val or "-", body_val_style)
        ])
        
    col_widths = [200, 340]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF1F5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FBFBFD')])
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 20))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_employees_pdf(employees, company_info=None):
    """Generates a clean PDF directory report of all registered employees."""
    from reportlab.lib.pagesizes import landscape
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle('EmpHdr', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#2c3e50'))
    cell_style = ParagraphStyle('EmpCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#333333'))
    
    elements = []
    build_pdf_header(elements, company_info=company_info, title="EMPLOYEE DIRECTORY REPORT")
    
    table_data = [
        [
            Paragraph("SL NO", header_style),
            Paragraph("EMP ID", header_style),
            Paragraph("EMPLOYEE NAME", header_style),
            Paragraph("SALARY BASIS", header_style),
            Paragraph("MOBILE", header_style),
            Paragraph("SHIFT HOURS", header_style),
            Paragraph("BANK NAME", header_style),
            Paragraph("ACCOUNT NO", header_style),
            Paragraph("JOIN DATE", header_style)
        ]
    ]
    
    if not employees:
        table_data.append([
            Paragraph("No employee records found", cell_style),
            Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style),
            Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style),
            Paragraph("", cell_style), Paragraph("", cell_style)
        ])
    else:
        for idx, emp in enumerate(employees, 1):
            st = str(emp.get('salary_type', 'hourly')).lower()
            st_label = 'Hourly' if st == 'hourly' else ('Day-Based' if st == 'daily' else 'Half-Day')
            table_data.append([
                Paragraph(str(idx), cell_style),
                Paragraph(str(emp.get('id', '')), cell_style),
                Paragraph(str(emp.get('employee_name', '')), cell_style),
                Paragraph(st_label, cell_style),
                Paragraph(str(emp.get('mobile_number', '') or '-'), cell_style),
                Paragraph(str(emp.get('shift_hours', '08:00')), cell_style),
                Paragraph(str(emp.get('bank_name', '') or '-'), cell_style),
                Paragraph(str(emp.get('account_number', '') or '-'), cell_style),
                Paragraph(str(emp.get('joining_date', '') or emp.get('date_of_joining', '') or '-'), cell_style)
            ])
            
    col_widths = [45, 60, 110, 80, 85, 75, 95, 100, 80]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF1F5')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FBFBFD')])
    ]))
    elements.append(t)
    elements.append(Spacer(1, 14))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_companies_pdf(companies, company_info=None):
    """Generates a clean PDF directory report of all registered companies."""
    from reportlab.lib.pagesizes import landscape
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle('CompHdr', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#2c3e50'))
    cell_style = ParagraphStyle('CompCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#333333'))
    
    elements = []
    build_pdf_header(elements, company_info=company_info, title="REGISTERED CLIENT COMPANIES REPORT")
    
    table_data = [
        [
            Paragraph("SL NO", header_style),
            Paragraph("COMPANY NAME", header_style),
            Paragraph("GSTIN", header_style),
            Paragraph("EMAIL", header_style),
            Paragraph("PHONE", header_style),
            Paragraph("SHIFT HOURS", header_style),
            Paragraph("EMPLOYEES", header_style),
            Paragraph("STATUS", header_style)
        ]
    ]
    
    if not companies:
        table_data.append([
            Paragraph("No registered companies found", cell_style),
            Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style),
            Paragraph("", cell_style), Paragraph("", cell_style), Paragraph("", cell_style),
            Paragraph("", cell_style)
        ])
    else:
        for idx, c in enumerate(companies, 1):
            table_data.append([
                Paragraph(str(idx), cell_style),
                Paragraph(str(c.get('company_name', '')), cell_style),
                Paragraph(str(c.get('gstin', '')), cell_style),
                Paragraph(str(c.get('email', '')), cell_style),
                Paragraph(str(c.get('phone', '')), cell_style),
                Paragraph(str(c.get('shift_hours', '08:00')), cell_style),
                Paragraph(f"{c.get('employee_count', 0)} / {c.get('employee_limit', 50)}", cell_style),
                Paragraph(str(c.get('status', 'Active')), cell_style)
            ])
            
    col_widths = [45, 140, 100, 150, 95, 75, 75, 60]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF1F5')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FBFBFD')])
    ]))
    elements.append(t)
    elements.append(Spacer(1, 14))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_live_report_pdf(title, entries, company_info=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#2c3e50')
    )
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#333333')
    )
    
    elements = []
    build_pdf_header(elements, company_info=company_info, title=title)

    
    is_timeout_pdf = "timeout" in (title or '').lower()
    time_col_title = "EXIT TIME" if is_timeout_pdf else "ENTRY TIME"
    loc_col_title = "EXIT LOCATION" if is_timeout_pdf else "ENTRY LOCATION"
    dist_col_title = "EXIT DISTANCE" if is_timeout_pdf else "ENTRY DISTANCE"
    table_data = [
        [
            Paragraph("EMPLOYEE NAME", header_style),
            Paragraph(time_col_title, header_style),
            Paragraph("SITE NAME", header_style),
            Paragraph(loc_col_title, header_style),
            Paragraph(dist_col_title, header_style)
        ]
    ]
    
    for row in entries:
        t_val = row.get('exit_time') if is_timeout_pdf and row.get('exit_time') else row.get('entry_time', '')
        l_val = row.get('exit_location') if is_timeout_pdf and row.get('exit_location') else row.get('entry_location', '')
        d_val = row.get('exit_distance') if is_timeout_pdf and row.get('exit_distance') and row.get('exit_distance') != '----' else (row.get('formatted_distance') or str(row.get('entry_distance', '0')))
        table_data.append([
            Paragraph(str(row.get('employee_name', '')), cell_style),
            Paragraph(str(t_val), cell_style),
            Paragraph(str(row.get('site_name', '')), cell_style),
            Paragraph(str(l_val), cell_style),
            Paragraph(str(d_val), cell_style)
        ])
        
    if len(table_data) == 1:
        table_data.append([
            Paragraph("No data available in table", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style)
        ])
        
    col_widths = [90, 80, 60, 240, 80]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF1F5')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FBFBFD')])
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_attendance_report_pdf(title, entries, is_simple=False, totals=None, company_info=None):
    from reportlab.lib.pagesizes import landscape
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter if is_simple else landscape(letter),
        rightMargin=20,
        leftMargin=20,
        topMargin=25,
        bottomMargin=25
    )
    
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7 if not is_simple else 8,
        leading=9 if not is_simple else 10,
        textColor=colors.HexColor('#ffffff' if is_simple else '#2c3e50')
    )
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7 if not is_simple else 8,
        leading=9 if not is_simple else 10,
        textColor=colors.HexColor('#333333')
    )
    bold_cell_style = ParagraphStyle(
        'BoldCellStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#111111')
    )
    
    elements = []
    build_pdf_header(elements, company_info=company_info, title=title)

    
    if not is_simple:
        # Full view table (omitting image columns)
        table_data = [
            [
                Paragraph("EMPLOYEE NAME", header_style),
                Paragraph("ENTRY TIME", header_style),
                Paragraph("ENTRY DISTANCE", header_style),
                Paragraph("ENTRY LOCATION", header_style),
                Paragraph("ENTRY STATUS", header_style),
                Paragraph("EXIT TIME", header_style),
                Paragraph("EXIT DISTANCE", header_style),
                Paragraph("EXIT LOCATION", header_style),
                Paragraph("EXIT STATUS", header_style),
                Paragraph("WORKING HOURS", header_style),
                Paragraph("SHIFT VARIANCE", header_style),
                Paragraph("WORKING SALARY", header_style)
            ]
        ]
        
        for r in entries:
            table_data.append([
                Paragraph(str(r.get('employee_name', '')), cell_style),
                Paragraph(str(r.get('entry_time', '')), cell_style),
                Paragraph(str(r.get('entry_distance', '')), cell_style),
                Paragraph(str(r.get('entry_location', '')), cell_style),
                Paragraph(str(r.get('entry_status', '-')), cell_style),
                Paragraph(str(r.get('exit_time', '')), cell_style),
                Paragraph(str(r.get('exit_distance', '')), cell_style),
                Paragraph(str(r.get('exit_location', '')), cell_style),
                Paragraph(str(r.get('exit_status', '-')), cell_style),
                Paragraph(str(r.get('working_hours', '')), cell_style),
                Paragraph(str(r.get('shift_variance', '')), cell_style),
                Paragraph(str(r.get('working_salary', '0')), cell_style)
            ])
            
        col_widths = [65, 60, 50, 110, 55, 60, 50, 110, 55, 45, 45, 47]
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF1F5')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FBFBFD')])
        ]))
    else:
        # Simple table view
        table_data = [
            [
                Paragraph("EMPLOYEE NAME", header_style),
                Paragraph("ENTRY TIME", header_style),
                Paragraph("EXIT TIME", header_style),
                Paragraph("WORKING HOURS", header_style),
                Paragraph("SHIFT VARIANCE", header_style),
                Paragraph("WORKING SALARY", header_style),
                Paragraph("STATUS", header_style)
            ]
        ]
        
        for r in entries:
            table_data.append([
                Paragraph(str(r.get('employee_name', '')), cell_style),
                Paragraph(str(r.get('entry_time', '')), cell_style),
                Paragraph(str(r.get('exit_time', '')), cell_style),
                Paragraph(str(r.get('working_hours', '')), cell_style),
                Paragraph(str(r.get('shift_variance', '')), cell_style),
                Paragraph(str(r.get('working_salary', '0')), cell_style),
                Paragraph(str(r.get('status', 'Manual')), cell_style)
            ])
            
        if totals:
            table_data.append([
                Paragraph("", cell_style),
                Paragraph("", cell_style),
                Paragraph("TOTAL", bold_cell_style),
                Paragraph(str(totals.get('total_working_hours', '')), bold_cell_style),
                Paragraph("----", bold_cell_style),
                Paragraph(str(totals.get('total_working_salary', '')), bold_cell_style),
                Paragraph("", cell_style)
            ])
            
        col_widths = [90, 100, 70, 75, 75, 75, 65]
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#212529')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2 if totals else -1), [colors.white, colors.HexColor('#FBFBFD')]),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E9ECEF')) if totals else ('BACKGROUND', (0, 0), (0, 0), colors.transparent)
        ]))

    elements.append(t)
    elements.append(Spacer(1, 14))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_manual_entries_pdf(entries, company_info=None):
    from reportlab.lib.pagesizes import landscape
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )
    
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'HeaderStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#2c3e50')
    )
    cell_style = ParagraphStyle(
        'CellStyle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#333333')
    )
    salary_style = ParagraphStyle(
        'SalaryStyle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#198754')
    )
    
    elements = []
    build_pdf_header(elements, company_info=company_info, title="MANUAL ENTRIES REPORT")
    
    table_data = [
        [
            Paragraph("NAME", header_style),
            Paragraph("DATE", header_style),
            Paragraph("HOURS", header_style),
            Paragraph("STATUS", header_style),
            Paragraph("SUBMITTED", header_style),
            Paragraph("HOURLY", header_style),
            Paragraph("DAY", header_style),
            Paragraph("HALF", header_style),
            Paragraph("WORKING SALARY", header_style)
        ]
    ]
    
    for r in entries:
        sal = f"+{int(float(r.get('working_salary', 0)))}" if float(r.get('working_salary', 0)) > 0 else "0"
        table_data.append([
            Paragraph(str(r.get('employee_name', '')), cell_style),
            Paragraph(str(r.get('entry_date', '')), cell_style),
            Paragraph(str(r.get('hours', '')), cell_style),
            Paragraph(str(r.get('status', '')), cell_style),
            Paragraph(str(r.get('submitted_at', '')), cell_style),
            Paragraph(str(int(float(r.get('hourly_rate', 0)))), cell_style),
            Paragraph(str(int(float(r.get('day_rate', 0)))), cell_style),
            Paragraph(str(int(float(r.get('half_rate', 0)))), cell_style),
            Paragraph(sal, salary_style)
        ])
        
    col_widths = [90, 80, 50, 75, 120, 50, 45, 45, 90]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF1F5')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FBFBFD')])
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_payments_pdf(payments, company_info=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#2c3e50')
    )
    
    cell_style = ParagraphStyle(
        'BodyCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#333333')
    )
    
    amount_style = ParagraphStyle(
        'AmountCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0d6efd')
    )
    
    elements = []
    build_pdf_header(elements, company_info=company_info, title="PAYMENT MANAGEMENT REPORT")

    
    table_data = [
        [
            Paragraph("TIMESTAMP", header_style),
            Paragraph("EMPLOYEE", header_style),
            Paragraph("DATE", header_style),
            Paragraph("AMOUNT", header_style),
            Paragraph("BANK", header_style),
            Paragraph("PAYMENT TYPE", header_style),
            Paragraph("REASON", header_style)
        ]
    ]
    
    if not payments:
        table_data.append([
            Paragraph("No data available in table", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style)
        ])
    else:
        for r in payments:
            table_data.append([
                Paragraph(str(r.get('timestamp', '')), cell_style),
                Paragraph(str(r.get('employee_name', '')), cell_style),
                Paragraph(str(r.get('payment_date', '')), cell_style),
                Paragraph(f"{float(r.get('amount', 0)):.2f}", amount_style),
                Paragraph(str(r.get('bank', '') or '-'), cell_style),
                Paragraph(str(r.get('payment_type', '')), cell_style),
                Paragraph(str(r.get('reason', '')), cell_style)
            ])
            
    col_widths = [100, 85, 65, 60, 70, 75, 85]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF1F5')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FBFBFD')])
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_advances_pdf(advances, company_info=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#2c3e50')
    )
    
    cell_style = ParagraphStyle(
        'BodyCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#333333')
    )
    
    amount_style = ParagraphStyle(
        'AmountCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#0d6efd')
    )
    
    elements = []
    build_pdf_header(elements, company_info=company_info, title="ADVANCE MANAGEMENT REPORT")
    
    table_data = [
        [
            Paragraph("TIMESTAMP", header_style),
            Paragraph("EMPLOYEE", header_style),
            Paragraph("DATE", header_style),
            Paragraph("AMOUNT", header_style)
        ]
    ]
    
    if not advances:
        table_data.append([
            Paragraph("No data available in table", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style)
        ])
    else:
        for r in advances:
            table_data.append([
                Paragraph(str(r.get('timestamp', '')), cell_style),
                Paragraph(str(r.get('employee_name', '')), cell_style),
                Paragraph(str(r.get('advance_date', '')), cell_style),
                Paragraph(f"{float(r.get('amount', 0)):.2f}", amount_style)
            ])
            
    col_widths = [150, 150, 120, 120]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF1F5')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FBFBFD')])
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_balance_report_pdf(data, totals=None, company_info=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#2c3e50')
    )
    
    cell_style = ParagraphStyle(
        'BodyCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#333333')
    )
    
    elements = []
    build_pdf_header(elements, company_info=company_info, title="ADVANCE SUMMARY")

    table_data = [
        [
            Paragraph("DATE&TIME", header_style),
            Paragraph("NAME", header_style),
            Paragraph("DATE", header_style),
            Paragraph("ADVANCE AMOUNT", header_style),
            Paragraph("PAYMENT AMOUNT", header_style),
            Paragraph("BALANCE AMOUNT", header_style)
        ]
    ]
    
    if not data:
        table_data.append([
            Paragraph("No data available in table", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style),
            Paragraph("", cell_style)
        ])
    else:
        for r in data:
            pay_amt = r.get('payment_amount', r.get('advance_repayment_amount', 0))
            table_data.append([
                Paragraph(str(r.get('timestamp', '')), cell_style),
                Paragraph(str(r.get('name', '')), cell_style),
                Paragraph(str(r.get('date', '')), cell_style),
                Paragraph(f"{float(r.get('advance_amount', 0)):.2f}", cell_style),
                Paragraph(f"{float(pay_amt):.2f}", cell_style),
                Paragraph(f"{float(r.get('balance_amount', 0)):.2f}", cell_style)
            ])
            
    col_widths = [100, 100, 70, 90, 100, 80]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF1F5')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FBFBFD')])
    ]))
    elements.append(t)
    elements.append(Spacer(1, 14))
    
    if totals:
        tot_pay = totals.get('total_payment', totals.get('total_repayment', 0.0))
        tot_text = f"<b>Total Advance:</b> {totals.get('total_advance', 0.0):.2f} &nbsp;&nbsp;&nbsp;&nbsp; <b>Total Payment:</b> {tot_pay:.2f} &nbsp;&nbsp;&nbsp;&nbsp; <b>Balance Amount:</b> {totals.get('balance_amount', 0.0):.2f}"
        elements.append(Paragraph(tot_text, ParagraphStyle('Totals', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#0d6efd'))))
        elements.append(Spacer(1, 14))
        
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    doc.build(elements)
    buffer.seek(0)
    return buffer

def get_rl_image(img_ref, max_width=120, max_height=50):
    """Safely creates a ReportLab Image from filepath, filename, or data URI."""
    if not img_ref:
        return None
    try:
        raw_str = str(img_ref).strip()
        if not raw_str:
            return None
        # Check if base64 data URI
        if raw_str.startswith('data:image'):
            header, b64 = raw_str.split(',', 1)
            raw = base64.b64decode(b64)
            img_io = io.BytesIO(raw)
            img = RLImage(img_io)
        elif os.path.isabs(raw_str) and os.path.isfile(raw_str):
            img = RLImage(raw_str)
        else:
            base_dir = os.path.abspath(os.path.dirname(__file__))
            candidates = [
                os.path.join(base_dir, 'static', 'uploads', raw_str),
                os.path.join(base_dir, 'static', raw_str.lstrip('/\\')),
                os.path.join(base_dir, 'static', 'images', raw_str),
                os.path.join(base_dir, raw_str.lstrip('/\\'))
            ]
            clean_name = os.path.basename(raw_str)
            candidates.append(os.path.join(base_dir, 'static', 'uploads', clean_name))

            found = None
            for path in candidates:
                if os.path.isfile(path):
                    found = path
                    break
            if not found:
                return None
            img = RLImage(found)

        # Scale preserving aspect ratio
        if getattr(img, 'imageWidth', None) and getattr(img, 'imageHeight', None) and img.imageWidth > 0 and img.imageHeight > 0:
            aspect = float(img.imageWidth) / float(img.imageHeight)
            w = max_width
            h = w / aspect
            if h > max_height:
                h = max_height
                w = h * aspect
            img.drawWidth = w
            img.drawHeight = h
            return img
    except Exception as e:
        print(f"Notice: Image load for PDF failed for {img_ref}: {e}")
    return None

def generate_payslip_pdf(p):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    elements = []
    
    # 1. Company Logo at top (if available)
    logo_img = get_rl_image(p.get('company_logo') or p.get('company_logo_url'), max_width=140, max_height=45)
    if logo_img:
        logo_img.hAlign = 'CENTER'
        elements.append(logo_img)
        elements.append(Spacer(1, 4))

    # Header
    title_style = ParagraphStyle('CompTitle', fontName='Helvetica-Bold', fontSize=15, leading=19, alignment=TA_CENTER, textColor=colors.HexColor('#003366'))
    addr_style = ParagraphStyle('CompAddr', fontName='Helvetica', fontSize=8, leading=11, alignment=TA_CENTER, textColor=colors.HexColor('#0056b3'))
    sub_style = ParagraphStyle('CompSub', fontName='Helvetica-Bold', fontSize=11, leading=15, alignment=TA_CENTER, textColor=colors.HexColor('#212529'))
    
    comp_name = p.get('company_name', 'ARGUS TECHNOLOGIES')
    comp_addr = p.get('company_address', '')
    comp_email = p.get('company_email', '')
    comp_phone = p.get('company_phone', '')
    comp_gstin = p.get('company_gstin', '')

    elements.append(Paragraph(comp_name.upper(), title_style))
    if comp_addr:
        elements.append(Spacer(1, 2))
        elements.append(Paragraph(comp_addr, addr_style))
    contact_parts = []
    if comp_email:
        contact_parts.append(f"Email: {comp_email}")
    if comp_phone:
        contact_parts.append(f"Phone: {comp_phone}")
    if comp_gstin:
        contact_parts.append(f"GSTIN: {comp_gstin}")
    if contact_parts:
        elements.append(Spacer(1, 2))
        elements.append(Paragraph(" | ".join(contact_parts), addr_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Monthly Payslip", sub_style))
    elements.append(Spacer(1, 8))
    
    cell_lbl_style = ParagraphStyle('CellLbl', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#212529'))
    cell_val_style = ParagraphStyle('CellVal', fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#333333'))
    
    # 5-column Employee Info Table with Employee Photo on right
    st = str(p.get('salary_type', 'daily')).lower()
    shift_h = str(p.get('shift_hours') or '08:00')
    bank = str(p.get('bank_name') or '—')

    if st == 'hourly':
        lbl_r2, val_r2 = "Hours Salary", f"Rs. {p.get('hours_salary', 0)}"
    elif st == 'half_day':
        lbl_r2, val_r2 = "Half Day Salary", f"Rs. {p.get('half_day_salary', 0)}"
    else:  # 'daily'
        lbl_r2, val_r2 = "Day Salary", f"Rs. {p.get('day_salary', 0)}"

    emp_photo_img = get_rl_image(p.get('employee_photo') or p.get('employee_photo_url'), max_width=65, max_height=80)
    if emp_photo_img:
        emp_photo_img.hAlign = 'CENTER'
        photo_cell = emp_photo_img
    else:
        photo_cell = Paragraph("<font size='8' color='#94a3b8'>PHOTO</font>", ParagraphStyle('PhotoHolder', alignment=TA_CENTER))

    info_data = [
        [Paragraph("PAYSLIP", ParagraphStyle('SectionHdr', fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=TA_CENTER, textColor=colors.white)), "", "", "", ""],
        [Paragraph("Employee Name", cell_lbl_style), Paragraph(str(p.get('employee_name', '')), cell_val_style), Paragraph("Salary Basis", cell_lbl_style), Paragraph(str(p.get('salary_basis_label', 'Day-Based')), cell_val_style), photo_cell],
        [Paragraph("Employee ID", cell_lbl_style), Paragraph(str(p.get('employee_id', '')), cell_val_style), Paragraph(lbl_r2, cell_lbl_style), Paragraph(val_r2, cell_val_style), ""],
        [Paragraph("Department", cell_lbl_style), Paragraph(str(p.get('department', 'General')), cell_val_style), Paragraph("Designation", cell_lbl_style), Paragraph(str(p.get('designation', '')), cell_val_style), ""],
        [Paragraph("Email ID", cell_lbl_style), Paragraph(str(p.get('email_id', '')), cell_val_style), Paragraph("Phone Number", cell_lbl_style), Paragraph(str(p.get('phone_number', '')), cell_val_style), ""],
        [Paragraph("Shift Hours", cell_lbl_style), Paragraph(shift_h, cell_val_style), Paragraph("Bank Name", cell_lbl_style), Paragraph(bank, cell_val_style), ""],
        [Paragraph("Year & Month", cell_lbl_style), Paragraph(str(p.get('year_month', '')), cell_val_style), Paragraph("Working Days", cell_lbl_style), Paragraph(str(p.get('working_days_breakdown', p.get('working_days', 0))), cell_val_style), ""],
        [Paragraph("Total Working Hours", cell_lbl_style), Paragraph(str(p.get('total_working_hours', '00:00')), cell_val_style), Paragraph("Total Days / Leave", cell_lbl_style), Paragraph(f"{p.get('total_days_of_month', 30)} Days ({p.get('leave_days', 0)} Leave)", cell_val_style), ""],
    ]
    
    t_info = Table(info_data, colWidths=[110, 135, 110, 115, 70])
    t_info.setStyle(TableStyle([
        ('SPAN', (0, 0), (4, 0)),
        ('BACKGROUND', (0, 0), (4, 0), colors.HexColor('#1565c0')),
        ('ALIGN', (0, 0), (4, 0), 'CENTER'),
        ('SPAN', (4, 1), (4, 7)),
        ('ALIGN', (4, 1), (4, 7), 'CENTER'),
        ('VALIGN', (4, 1), (4, 7), 'MIDDLE'),
        ('BACKGROUND', (4, 1), (4, 7), colors.HexColor('#fafafa')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#767676')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 8))
    
    # Earnings & Deductions Table (Total Earnings and Total Deductions in SAME ROW)
    bold_earn_style = ParagraphStyle('BoldEarn', fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.HexColor('#0f172a'))
    
    earn_ded_data = [
        [Paragraph("EARNINGS", ParagraphStyle('EarnHdr', fontName='Helvetica-Bold', fontSize=9, leading=11, alignment=TA_CENTER, textColor=colors.white)), "",
         Paragraph("DEDUCTION", ParagraphStyle('DedHdr', fontName='Helvetica-Bold', fontSize=9, leading=11, alignment=TA_CENTER, textColor=colors.white)), ""],
        [Paragraph("Basic Salary", cell_lbl_style), Paragraph(f"Rs. {p.get('basic_salary', 0)}", cell_val_style), Paragraph("Paid Salary", cell_lbl_style), Paragraph(f"Rs. {p.get('paid_salary', 0)}", cell_val_style)],
        [Paragraph("Allowance", cell_lbl_style), Paragraph(f"Rs. {p.get('allowance', 0)}", cell_val_style), Paragraph("Advance Repayment", cell_lbl_style), Paragraph(f"Rs. {p.get('advance_repayment', 0)}", cell_val_style)],
        [Paragraph("Incentive", cell_lbl_style), Paragraph(f"Rs. {p.get('incentive', 0)}", cell_val_style), Paragraph("Other Deductions", cell_lbl_style), Paragraph(f"Rs. {p.get('other_deductions', 0)}", cell_val_style)],
        [Paragraph("Others Earnings", cell_lbl_style), Paragraph(f"Rs. {p.get('other_earnings', 0)}", cell_val_style), Paragraph("", cell_lbl_style), Paragraph("", cell_val_style)],
        [Paragraph("TOTAL EARNINGS", bold_earn_style), Paragraph(f"Rs. {p.get('total_earnings', 0)}", bold_earn_style),
         Paragraph("TOTAL DEDUCTIONS", bold_earn_style), Paragraph(f"Rs. {p.get('total_deductions', p.get('total_deduction', 0))}", bold_earn_style)],
    ]
    
    t_earn = Table(earn_ded_data, colWidths=[150, 120, 150, 120])
    t_earn.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (2, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#0d47a1')),
        ('BACKGROUND', (2, 0), (3, 0), colors.HexColor('#0d47a1')),
        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#767676')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_earn)
    elements.append(Spacer(1, 8))
    
    # Net Pay Bar
    net_data = [
        [Paragraph(f"<b>NET PAY : Rs. {p.get('net_pay', 0)}</b>", ParagraphStyle('NetPay', fontName='Helvetica-Bold', fontSize=12, leading=15, alignment=TA_CENTER, textColor=colors.black))],
        [Paragraph(f"<b>NET PAY IN WORDS: {p.get('net_pay_in_words', '')}</b>", ParagraphStyle('NetWords', fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=TA_CENTER, textColor=colors.HexColor('#003366')))],
        [Paragraph("<font size='7'><i>** Net Pay = Total Earnings - Total Deduction<br/>* Payslip is auto-generated and valid without the need for a signature. *</i></font>", ParagraphStyle('Notes', fontName='Helvetica', fontSize=7, leading=9, alignment=TA_CENTER, textColor=colors.HexColor('#333333')))],
        [Paragraph("<font color='white'><b>** This document has been automatically generated by ARGUS **</b></font>", ParagraphStyle('ArgusGen', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.white))]
    ]
    t_net = Table(net_data, colWidths=[540])
    t_net.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f1f3f5')),
        ('BACKGROUND', (0, 1), (0, 1), colors.HexColor('#fef9e7')),
        ('BACKGROUND', (0, 3), (0, 3), colors.HexColor('#37474f')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#767676')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_net)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_salary_report_pdf(data, company_info=None):
    from reportlab.lib.pagesizes import landscape
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )
    
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#2c3e50')
    )
    
    cell_style = ParagraphStyle(
        'BodyCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#333333')
    )
    
    earn_cell_style = ParagraphStyle(
        'EarnCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#198754')
    )
    
    net_cell_style = ParagraphStyle(
        'NetCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=6.5,
        leading=8,
        textColor=colors.HexColor('#0d6efd')
    )
    
    elements = []
    build_pdf_header(elements, company_info=company_info, title="MONTHLY SALARY REPORT")

    
    table_data = [
        [
            Paragraph("EMPLOYEE NAME", header_style),
            Paragraph("PAY PERIOD", header_style),
            Paragraph("WORKING DAYS", header_style),
            Paragraph("WORKING HOURS", header_style),
            Paragraph("ALLOWANCE", header_style),
            Paragraph("INCENTIVE", header_style),
            Paragraph("OTHER EARNINGS", header_style),
            Paragraph("BASIC EARNINGS", header_style),
            Paragraph("TOTAL EARNINGS", header_style),
            Paragraph("PAID SALARY", header_style),
            Paragraph("ADVANCE REPAYMENT", header_style),
            Paragraph("OTHER DEDUCTIONS", header_style),
            Paragraph("TOTAL DEDUCTIONS", header_style),
            Paragraph("NET SALARY", header_style),
        ]
    ]
    
    for r in data:
        table_data.append([
            Paragraph(str(r.get('employee_name', '')), cell_style),
            Paragraph(str(r.get('pay_period', '')), cell_style),
            Paragraph(str(r.get('working_days', '')), cell_style),
            Paragraph(str(r.get('working_hours', '')), cell_style),
            Paragraph(f"Rs. {int(float(r.get('allowance', 0)))}", cell_style),
            Paragraph(f"Rs. {int(float(r.get('incentive', 0)))}", cell_style),
            Paragraph(f"Rs. {int(float(r.get('other_earnings', 0)))}", cell_style),
            Paragraph(f"Rs. {int(float(r.get('basic_earnings', 0)))}", cell_style),
            Paragraph(f"Rs. {int(float(r.get('total_earnings', 0)))}", earn_cell_style),
            Paragraph(f"Rs. {int(float(r.get('paid_salary', 0)))}", cell_style),
            Paragraph(f"Rs. {int(float(r.get('advance_repayment', 0)))}", cell_style),
            Paragraph(f"Rs. {int(float(r.get('other_deductions', 0)))}", cell_style),
            Paragraph(f"Rs. {int(float(r.get('total_deductions', 0)))}", cell_style),
            Paragraph(f"Rs. {int(float(r.get('net_salary', 0)))}", net_cell_style),
        ])
        
    col_widths = [75, 45, 42, 45, 45, 45, 50, 48, 52, 45, 52, 52, 52, 50]
    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EDF1F5')),
        ('BACKGROUND', (8, 1), (8, -1), colors.HexColor('#e8f5e9')),
        ('BACKGROUND', (13, 1), (13, -1), colors.HexColor('#e3f2fd')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DCE1E7')),
    ]))
    
    elements.append(t)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer





