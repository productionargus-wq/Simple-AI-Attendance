import io
import os
import base64
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

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

PAYSLIP_THEMES = {
    'navy': {
        'primary': colors.HexColor('#1b3b5f'),
        'dark': colors.HexColor('#0f233a'),
        'tint': colors.HexColor('#f0f5fa'),
        'border': colors.HexColor('#cbd5e1'),
        'text_dark': colors.HexColor('#0f172a'),
        'text_sub': colors.HexColor('#475569'),
        'light_badge': colors.HexColor('#dbeafe'),
    },
    'emerald': {
        'primary': colors.HexColor('#0f5132'),
        'dark': colors.HexColor('#0a3622'),
        'tint': colors.HexColor('#e9f7ef'),
        'border': colors.HexColor('#a3cfbb'),
        'text_dark': colors.HexColor('#064e3b'),
        'text_sub': colors.HexColor('#198754'),
        'light_badge': colors.HexColor('#d1fae5'),
    },
    'burgundy': {
        'primary': colors.HexColor('#5c1d48'),
        'dark': colors.HexColor('#3f1331'),
        'tint': colors.HexColor('#f9edf4'),
        'border': colors.HexColor('#d8b4cb'),
        'text_dark': colors.HexColor('#4a153b'),
        'text_sub': colors.HexColor('#701a75'),
        'light_badge': colors.HexColor('#fce7f3'),
    }
}

def _extract_payslip_fields(p):
    """Centralized extractor for all payslip data fields ensuring consistent dynamic reporting."""
    comp_name = str(p.get('company_name') or 'ARGUS TECHNOLOGIES').upper()
    comp_addr = str(p.get('company_address') or '').upper()
    
    contact_bits = []
    if p.get('company_email'): contact_bits.append(f"Email: {p['company_email']}")
    elif p.get('email'): contact_bits.append(f"Email: {p['email']}")
    if p.get('company_phone'): contact_bits.append(f"Phone: {p['company_phone']}")
    elif p.get('phone'): contact_bits.append(f"Phone: {p['phone']}")
    if p.get('company_gstin'): contact_bits.append(f"GSTIN: {p['company_gstin']}")
    elif p.get('gstin'): contact_bits.append(f"GSTIN: {p['gstin']}")
    contact_str = " | ".join(contact_bits) if contact_bits else ""

    raw_ym = str(p.get('year_month', '')).strip()
    month_badge_val = "OCT 2026"
    if raw_ym:
        try:
            dt = datetime.strptime(raw_ym, "%Y-%m")
            month_badge_val = dt.strftime("%b %Y").upper()
        except Exception:
            month_badge_val = raw_ym.upper()

    logo_ref = p.get('company_logo_data') or p.get('logo_data') or p.get('company_logo_url') or p.get('company_logo') or p.get('logo')
    photo_ref = p.get('employee_photo_data') or p.get('photo_data') or p.get('employee_photo_url') or p.get('employee_photo') or p.get('photo')

    emp_name = str(p.get('employee_name') or 'EMPLOYEE').upper()
    emp_id = str(p.get('employee_id') or '-')
    desig = str(p.get('designation') or '-').upper()
    dept = str(p.get('department') or 'GENERAL').upper()
    email = str(p.get('email_id') or '-')
    phone = str(p.get('phone_number') or p.get('mobile_number') or '-')

    st = str(p.get('salary_type', 'daily')).lower()
    if st == 'hourly':
        basis_lbl = "Hourly-Based"
        rate_lbl = "HOURS SALARY"
        rate_val = f"Rs. {Number_format(p.get('hours_salary', p.get('hourly_salary', 0)))}"
    elif st == 'half_day':
        basis_lbl = "Half-Day Based"
        rate_lbl = "HALF DAY SALARY"
        rate_val = f"Rs. {Number_format(p.get('half_day_salary', 0))}"
    else:
        basis_lbl = "Daily-Based"
        rate_lbl = "DAY SALARY"
        rate_val = f"Rs. {Number_format(p.get('day_salary', 0))}"

    shift_h = str(p.get('shift_hours') or '08:00')
    working_days = str(p.get('working_days_breakdown') or f"{p.get('working_days', 0)} Days")
    tot_work_h = str(p.get('total_working_hours') or p.get('working_hours') or '00:00')
    tot_days = p.get('total_days_of_month', p.get('total_days', 30))
    leave_days = p.get('leave_days', 0)
    bank_name = str(p.get('bank_name') or '').strip()
    acct_num = str(p.get('account_number') or '').strip()
    if bank_name and acct_num:
        bank_display = f"{bank_name} (A/C: {acct_num})"
    elif bank_name:
        bank_display = bank_name
    else:
        bank_display = "—"

    basic_sal = Number_format(p.get('basic_salary', 0))
    allowance = Number_format(p.get('allowance', 0))
    incentive = Number_format(p.get('incentive', 0))
    other_earn = Number_format(p.get('other_earnings', 0))
    tot_earn = Number_format(p.get('total_earnings', 0))

    paid_sal = Number_format(p.get('paid_salary', 0))
    adv_repay = Number_format(p.get('advance_repayment', 0))
    other_ded = Number_format(p.get('other_deductions', 0))
    tot_ded = Number_format(p.get('total_deductions', p.get('total_deduction', 0)))

    net_pay_val = Number_format(p.get('net_pay', 0))
    net_words_val = str(p.get('net_pay_in_words', '')).strip() or "Zero Rupees Only"

    return {
        'comp_name': comp_name,
        'comp_addr': comp_addr,
        'contact_str': contact_str,
        'month_badge_val': month_badge_val,
        'logo_ref': logo_ref,
        'photo_ref': photo_ref,
        'emp_name': emp_name,
        'emp_id': emp_id,
        'desig': desig,
        'dept': dept,
        'email': email,
        'phone': phone,
        'basis_lbl': basis_lbl,
        'rate_lbl': rate_lbl,
        'rate_val': rate_val,
        'shift_h': shift_h,
        'working_days': working_days,
        'tot_work_h': tot_work_h,
        'tot_days': tot_days,
        'leave_days': leave_days,
        'bank_display': bank_display,
        'bank_name': bank_name,
        'basic_sal': basic_sal,
        'allowance': allowance,
        'incentive': incentive,
        'other_earn': other_earn,
        'tot_earn': tot_earn,
        'paid_sal': paid_sal,
        'adv_repay': adv_repay,
        'other_ded': other_ded,
        'tot_ded': tot_ded,
        'net_pay_val': net_pay_val,
        'net_words_val': net_words_val
    }

def _build_payslip_modern_executive(p, template_id, palette):
    """Builder for Template 1 (With Signatory) and Template 2 (Streamlined/Paperless)."""
    f = _extract_payslip_fields(p)
    has_signatory = (template_id != 'template_2')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=32, bottomMargin=32)
    elements = []

    # 1. Header Pill
    logo_img = get_rl_image(f['logo_ref'], max_width=44, max_height=44)
    if logo_img:
        logo_cell_content = [logo_img]
    else:
        comp_initial = f['comp_name'][:1] or 'A'
        logo_cell_content = [Paragraph(f"<font size='16' color='#1b3b5f'><b>{comp_initial}</b></font>", ParagraphStyle('LogoInit', alignment=TA_CENTER))]

    hdr_center = [Paragraph(f"<b>{f['comp_name']}</b>", ParagraphStyle('HdrName', fontName='Helvetica-Bold', fontSize=12.5, leading=15, textColor=colors.white))]
    if f['comp_addr']:
        hdr_center.append(Paragraph(f['comp_addr'], ParagraphStyle('HdrAddr', fontName='Helvetica', fontSize=7.5, leading=10, textColor=colors.HexColor('#e2e8f0'))))
    if f['contact_str']:
        hdr_center.append(Paragraph(f['contact_str'], ParagraphStyle('HdrContact', fontName='Helvetica', fontSize=6.5, leading=9, textColor=colors.HexColor('#cbd5e1'))))

    hdr_data = [[
        logo_cell_content,
        hdr_center,
        [
            Paragraph("<font size='6.5' color='#cbd5e1'><b>MONTHLY PAYSLIP</b></font>", ParagraphStyle('HdrBadgeSub', fontName='Helvetica-Bold', alignment=TA_CENTER, leading=8)),
            Paragraph(f"<b>{f['month_badge_val']}</b>", ParagraphStyle('HdrBadgeMain', fontName='Helvetica-Bold', fontSize=12, leading=15, alignment=TA_CENTER, textColor=colors.white))
        ]
    ]]
    t_hdr = Table(hdr_data, colWidths=[52, 368, 120])
    t_hdr.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['primary']),
        ('BACKGROUND', (0, 0), (0, 0), colors.white),
        ('BACKGROUND', (2, 0), (2, 0), palette['dark']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (1, 0), (1, 0), 10),
        ('RIGHTPADDING', (1, 0), (1, 0), 6),
    ]))
    elements.append(t_hdr)
    elements.append(Spacer(1, 10))

    # 2. Employee Details Card (Dynamic with Photo)
    emp_photo_img = get_rl_image(f['photo_ref'], max_width=44, max_height=44)
    if emp_photo_img:
        emp_data = [[
            Paragraph("<b>EMPLOYEE</b>", ParagraphStyle('EmpBadge', fontName='Helvetica-Bold', fontSize=8.5, leading=10, alignment=TA_CENTER, textColor=colors.white)),
            [
                Paragraph(f"<b>{f['emp_name']}</b>", ParagraphStyle('EmpName', fontName='Helvetica-Bold', fontSize=11.5, leading=14, textColor=palette['text_dark'])),
                Paragraph(f"Employee ID: <b>{f['emp_id']}</b> &nbsp;|&nbsp; Designation: <b>{f['desig']}</b> &nbsp;|&nbsp; Department: <b>{f['dept']}</b>", ParagraphStyle('EmpLine1', fontName='Helvetica', fontSize=7.2, leading=9.5, textColor=palette['text_sub'])),
                Paragraph(f"Email: <b>{f['email']}</b> &nbsp;|&nbsp; Phone: <b>{f['phone']}</b>", ParagraphStyle('EmpLine2', fontName='Helvetica', fontSize=7.2, leading=9.5, textColor=palette['text_sub']))
            ],
            emp_photo_img
        ]]
        t_emp = Table(emp_data, colWidths=[75, 415, 50])
        t_emp.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), palette['tint']),
            ('BACKGROUND', (0, 0), (0, 0), palette['primary']),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (1, 0), (1, 0), 10),
            ('RIGHTPADDING', (2, 0), (2, 0), 6),
        ]))
    else:
        emp_data = [[
            Paragraph("<b>EMPLOYEE</b>", ParagraphStyle('EmpBadge', fontName='Helvetica-Bold', fontSize=8.5, leading=10, alignment=TA_CENTER, textColor=colors.white)),
            [
                Paragraph(f"<b>{f['emp_name']}</b>", ParagraphStyle('EmpName', fontName='Helvetica-Bold', fontSize=11.5, leading=14, textColor=palette['text_dark'])),
                Paragraph(f"Employee ID: <b>{f['emp_id']}</b> &nbsp;|&nbsp; Designation: <b>{f['desig']}</b> &nbsp;|&nbsp; Department: <b>{f['dept']}</b>", ParagraphStyle('EmpLine1', fontName='Helvetica', fontSize=7.2, leading=9.5, textColor=palette['text_sub'])),
                Paragraph(f"Email: <b>{f['email']}</b> &nbsp;|&nbsp; Phone: <b>{f['phone']}</b>", ParagraphStyle('EmpLine2', fontName='Helvetica', fontSize=7.2, leading=9.5, textColor=palette['text_sub']))
            ]
        ]]
        t_emp = Table(emp_data, colWidths=[75, 465])
        t_emp.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), palette['tint']),
            ('BACKGROUND', (0, 0), (0, 0), palette['primary']),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (1, 0), (1, 0), 10),
        ]))
    elements.append(t_emp)
    elements.append(Spacer(1, 10))

    # 3. 4 Key Metric Cards
    metric_lbl_style = ParagraphStyle('MetLbl', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.HexColor('#64748b'))
    metric_val_style = ParagraphStyle('MetVal', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=colors.HexColor('#0f172a'))
    cards_data = [[
        [Paragraph("SALARY BASIS", metric_lbl_style), Paragraph(f"<b>{f['basis_lbl']}</b>", metric_val_style)],
        [Paragraph(f['rate_lbl'], metric_lbl_style), Paragraph(f"<b>{f['rate_val']}</b>", metric_val_style)],
        [Paragraph("SHIFT HOURS", metric_lbl_style), Paragraph(f"<b>{f['shift_h']}</b>", metric_val_style)],
        [Paragraph("WORKING DAYS", metric_lbl_style), Paragraph(f"<b>{f['working_days']}</b>", metric_val_style)],
    ]]
    t_cards = Table(cards_data, colWidths=[135, 135, 135, 135])
    t_cards.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (0, 0), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX', (1, 0), (1, 0), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX', (2, 0), (2, 0), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX', (3, 0), (3, 0), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 8))

    # 4. Summary Bar
    summary_style = ParagraphStyle('SumTxt', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.HexColor('#334155'))
    summary_data = [[
        Paragraph(f"Total Working Hours: <b>{f['tot_work_h']}</b>", summary_style),
        Paragraph(f"Total Days / Leave: <b>{f['tot_days']} Days ({f['leave_days']} Leave)</b>", summary_style),
        Paragraph(f"Bank: <b>{f['bank_display']}</b>", ParagraphStyle('BankTxt', parent=summary_style, alignment=TA_CENTER))
    ]]
    t_summary = Table(summary_data, colWidths=[180, 240, 120])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['tint']),
        ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 10))

    # 5. Dual Side-by-Side Tables
    cell_lbl_style = ParagraphStyle('DualLbl', fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#334155'))
    cell_val_style = ParagraphStyle('DualVal', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.HexColor('#0f172a'))
    hdr_style = ParagraphStyle('DualHdr', fontName='Helvetica-Bold', fontSize=8.5, leading=10, textColor=colors.white)
    total_lbl_style = ParagraphStyle('TotLbl', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=palette['text_dark'])
    total_val_style = ParagraphStyle('TotVal', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=palette['text_dark'])

    earn_ded_data = [
        [Paragraph("EARNINGS", hdr_style), "", Paragraph("DEDUCTIONS", hdr_style), ""],
        [Paragraph("Basic Salary", cell_lbl_style), Paragraph(f"Rs. {f['basic_sal']}", cell_val_style), Paragraph("Paid Salary", cell_lbl_style), Paragraph(f"Rs. {f['paid_sal']}", cell_val_style)],
        [Paragraph("Allowance", cell_lbl_style), Paragraph(f"Rs. {f['allowance']}", cell_val_style), Paragraph("Advance Repayment", cell_lbl_style), Paragraph(f"Rs. {f['adv_repay']}", cell_val_style)],
        [Paragraph("Incentive", cell_lbl_style), Paragraph(f"Rs. {f['incentive']}", cell_val_style), Paragraph("Other Deductions", cell_lbl_style), Paragraph(f"Rs. {f['other_ded']}", cell_val_style)],
        [Paragraph("Other Earnings", cell_lbl_style), Paragraph(f"Rs. {f['other_earn']}", cell_val_style), Paragraph("", cell_lbl_style), Paragraph("", cell_val_style)],
        [Paragraph("TOTAL EARNINGS", total_lbl_style), Paragraph(f"Rs. {f['tot_earn']}", total_val_style), Paragraph("TOTAL DEDUCTIONS", total_lbl_style), Paragraph(f"Rs. {f['tot_ded']}", total_val_style)]
    ]
    t_tables = Table(earn_ded_data, colWidths=[160, 105, 165, 110])
    t_tables.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (2, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (1, 0), palette['primary']),
        ('BACKGROUND', (2, 0), (3, 0), palette['primary']),
        ('BACKGROUND', (0, 5), (1, 5), palette['tint']),
        ('BACKGROUND', (2, 5), (3, 5), palette['tint']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 1), (1, 4), 0.5, colors.HexColor('#f1f5f9')),
        ('LINEBELOW', (2, 1), (3, 4), 0.5, colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t_tables)
    elements.append(Spacer(1, 10))

    # 6. Net Pay Banner
    net_banner_data = [[
        [
            Paragraph("<font size='7' color='#cbd5e1'><b>NET PAY</b></font>", ParagraphStyle('NetLbl', fontName='Helvetica-Bold', leading=8)),
            Paragraph(f"<b>Rs. {f['net_pay_val']}</b>", ParagraphStyle('NetVal', fontName='Helvetica-Bold', fontSize=17, leading=20, textColor=colors.white))
        ],
        [
            Paragraph("<font size='6.5' color='#cbd5e1'><b>IN WORDS</b></font>", ParagraphStyle('WordsLbl', fontName='Helvetica-Bold', leading=8, alignment=TA_CENTER)),
            Paragraph(f"<b>{f['net_words_val']}</b>", ParagraphStyle('WordsVal', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=colors.white))
        ]
    ]]
    t_net = Table(net_banner_data, colWidths=[200, 340])
    t_net.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['primary']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (0, 0), 14),
        ('RIGHTPADDING', (1, 0), (1, 0), 14),
    ]))
    elements.append(t_net)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("<i>Net Pay = Total Earnings - Total Deductions</i>", ParagraphStyle('FootnoteFormula', fontName='Helvetica-Oblique', fontSize=7, leading=9, textColor=colors.HexColor('#64748b'))))

    # 7. Authorized Signatory (Template 1 Only)
    if has_signatory:
        elements.append(Spacer(1, 18))
        sig_data = [["", [
            Paragraph("<b>AUTHORIZED SIGNATORY</b>", ParagraphStyle('SigHdr', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.HexColor('#1e293b'))),
            Spacer(1, 24),
            Paragraph("________________________________", ParagraphStyle('SigLine', fontName='Helvetica', fontSize=8, leading=9, alignment=TA_CENTER, textColor=colors.HexColor('#94a3b8'))),
            Paragraph("Signature & Company Seal", ParagraphStyle('SigSub', fontName='Helvetica', fontSize=7, leading=9, alignment=TA_CENTER, textColor=colors.HexColor('#64748b')))
        ]]]
        t_sig = Table(sig_data, colWidths=[350, 190])
        t_sig.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('ALIGN', (1, 0), (1, 0), 'CENTER')]))
        elements.append(t_sig)
    else:
        elements.append(Spacer(1, 12))

    # 8. Standardized Footer
    elements.append(Spacer(1, 10))
    footer_data = [[
        Paragraph("Generated by ARGUS Attendance", ParagraphStyle('FtrL', fontName='Helvetica', fontSize=7.2, leading=9, textColor=colors.HexColor('#64748b'))),
        Paragraph("Argus Attendance | version 5.1 | powered by ArgusCNC(TM)", ParagraphStyle('FtrR', fontName='Helvetica', fontSize=7.2, leading=9, alignment=TA_CENTER, textColor=colors.HexColor('#64748b')))
    ]]
    t_ftr = Table(footer_data, colWidths=[270, 270])
    t_ftr.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_ftr)

    doc.build(elements)
    buffer.seek(0)
    return buffer

def _build_payslip_premium_executive(p, palette):
    """Builder for Template 3 (1st Uploaded Image): Dark pill header, circular icons, dual-color headers."""
    f = _extract_payslip_fields(p)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=32, bottomMargin=32)
    elements = []

    # 1. Dark Pill Header
    logo_img = get_rl_image(f['logo_ref'], max_width=44, max_height=44)
    if logo_img:
        logo_cell_content = [logo_img]
    else:
        comp_initial = f['comp_name'][:1] or 'A'
        logo_cell_content = [Paragraph(f"<font size='16' color='#1b3b5f'><b>{comp_initial}</b></font>", ParagraphStyle('LogoInit', alignment=TA_CENTER))]

    hdr_center = [Paragraph(f"<b>{f['comp_name']}</b>", ParagraphStyle('HdrName', fontName='Helvetica-Bold', fontSize=12.5, leading=15, textColor=colors.white))]
    if f['comp_addr']:
        hdr_center.append(Paragraph(f['comp_addr'], ParagraphStyle('HdrAddr', fontName='Helvetica', fontSize=7.5, leading=10, textColor=colors.HexColor('#e2e8f0'))))
    if f['contact_str']:
        hdr_center.append(Paragraph(f['contact_str'], ParagraphStyle('HdrContact', fontName='Helvetica', fontSize=6.5, leading=9, textColor=colors.HexColor('#cbd5e1'))))

    hdr_data = [[
        logo_cell_content,
        hdr_center,
        [
            Paragraph("<font size='6.5' color='#cbd5e1'><b>MONTHLY PAYSLIP</b></font>", ParagraphStyle('HdrBadgeSub', fontName='Helvetica-Bold', alignment=TA_CENTER, leading=8)),
            Paragraph(f"<b>{f['month_badge_val']}</b>", ParagraphStyle('HdrBadgeMain', fontName='Helvetica-Bold', fontSize=12, leading=15, alignment=TA_CENTER, textColor=colors.white))
        ]
    ]]
    t_hdr = Table(hdr_data, colWidths=[52, 368, 120])
    t_hdr.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1a2936')),
        ('BACKGROUND', (0, 0), (0, 0), colors.white),
        ('BACKGROUND', (2, 0), (2, 0), palette['primary']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (1, 0), (1, 0), 10),
        ('RIGHTPADDING', (1, 0), (1, 0), 6),
    ]))
    elements.append(t_hdr)
    elements.append(Spacer(1, 10))

    # 2. Employee Details Card (Teal Badge + Soft background)
    emp_photo_img = get_rl_image(f['photo_ref'], max_width=44, max_height=44)
    if emp_photo_img:
        emp_data = [[
            Paragraph("<b>EMPLOYEE</b>", ParagraphStyle('EmpBadge', fontName='Helvetica-Bold', fontSize=8.5, leading=10, alignment=TA_CENTER, textColor=colors.white)),
            [
                Paragraph(f"<b>{f['emp_name']}</b>", ParagraphStyle('EmpName', fontName='Helvetica-Bold', fontSize=11.5, leading=14, textColor=colors.HexColor('#0f233a'))),
                Paragraph(f"Employee ID: <b>{f['emp_id']}</b> &nbsp;|&nbsp; Designation: <b>{f['desig']}</b> &nbsp;|&nbsp; Department: <b>{f['dept']}</b>", ParagraphStyle('EmpLine1', fontName='Helvetica', fontSize=7.2, leading=9.5, textColor=colors.HexColor('#475569'))),
                Paragraph(f"Email: <b>{f['email']}</b> &nbsp;|&nbsp; Phone: <b>{f['phone']}</b>", ParagraphStyle('EmpLine2', fontName='Helvetica', fontSize=7.2, leading=9.5, textColor=colors.HexColor('#475569')))
            ],
            emp_photo_img
        ]]
        t_emp = Table(emp_data, colWidths=[75, 415, 50])
        t_emp.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f7f9')),
            ('BACKGROUND', (0, 0), (0, 0), palette['primary']),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (1, 0), (1, 0), 10),
            ('RIGHTPADDING', (2, 0), (2, 0), 6),
        ]))
    else:
        emp_data = [[
            Paragraph("<b>EMPLOYEE</b>", ParagraphStyle('EmpBadge', fontName='Helvetica-Bold', fontSize=8.5, leading=10, alignment=TA_CENTER, textColor=colors.white)),
            [
                Paragraph(f"<b>{f['emp_name']}</b>", ParagraphStyle('EmpName', fontName='Helvetica-Bold', fontSize=11.5, leading=14, textColor=colors.HexColor('#0f233a'))),
                Paragraph(f"Employee ID: <b>{f['emp_id']}</b> &nbsp;|&nbsp; Designation: <b>{f['desig']}</b> &nbsp;|&nbsp; Department: <b>{f['dept']}</b>", ParagraphStyle('EmpLine1', fontName='Helvetica', fontSize=7.2, leading=9.5, textColor=colors.HexColor('#475569'))),
                Paragraph(f"Email: <b>{f['email']}</b> &nbsp;|&nbsp; Phone: <b>{f['phone']}</b>", ParagraphStyle('EmpLine2', fontName='Helvetica', fontSize=7.2, leading=9.5, textColor=colors.HexColor('#475569')))
            ]
        ]]
        t_emp = Table(emp_data, colWidths=[75, 465])
        t_emp.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f7f9')),
            ('BACKGROUND', (0, 0), (0, 0), palette['primary']),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (1, 0), (1, 0), 10),
        ]))
    elements.append(t_emp)
    elements.append(Spacer(1, 10))

    # 3. 4 Key Metric Cards
    metric_lbl_style = ParagraphStyle('MetLbl3', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.HexColor('#64748b'))
    metric_val_style = ParagraphStyle('MetVal3', fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=colors.HexColor('#0f172a'))
    cards_data = [[
        [Paragraph("SALARY BASIS", metric_lbl_style), Paragraph(f"<b>{f['basis_lbl']}</b>", metric_val_style)],
        [Paragraph(f['rate_lbl'], metric_lbl_style), Paragraph(f"<b>{f['rate_val']}</b>", metric_val_style)],
        [Paragraph("SHIFT HOURS", metric_lbl_style), Paragraph(f"<b>{f['shift_h']}</b>", metric_val_style)],
        [Paragraph("WORKING DAYS", metric_lbl_style), Paragraph(f"<b>{f['working_days']}</b>", metric_val_style)],
    ]]
    t_cards = Table(cards_data, colWidths=[135, 135, 135, 135])
    t_cards.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (0, 0), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX', (1, 0), (1, 0), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX', (2, 0), (2, 0), 0.5, colors.HexColor('#e2e8f0')),
        ('BOX', (3, 0), (3, 0), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 8))

    # 4. Summary Bar
    summary_style = ParagraphStyle('SumTxt3', fontName='Helvetica-Bold', fontSize=7.5, leading=9, textColor=colors.HexColor('#334155'))
    summary_data = [[
        Paragraph(f"Total Working Hours: <b>{f['tot_work_h']}</b>", summary_style),
        Paragraph(f"Total Days / Leave: <b>{f['tot_days']} Days ({f['leave_days']} Leave)</b>", summary_style),
        Paragraph(f"Bank: <b>{f['bank_display']}</b>", ParagraphStyle('BankTxt3', parent=summary_style, alignment=TA_CENTER))
    ]]
    t_summary = Table(summary_data, colWidths=[180, 240, 120])
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0f7f9')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(t_summary)
    elements.append(Spacer(1, 10))

    # 5. Dual Side-by-Side Tables (Dual Color Headers: Earnings=Primary, Deductions=Dark Slate)
    cell_lbl_style = ParagraphStyle('DualLbl3', fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#334155'))
    cell_val_style = ParagraphStyle('DualVal3', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.HexColor('#0f172a'))
    hdr_style = ParagraphStyle('DualHdr3', fontName='Helvetica-Bold', fontSize=8.5, leading=10, textColor=colors.white)

    earn_ded_data = [
        [Paragraph("EARNINGS", hdr_style), "", Paragraph("DEDUCTIONS", hdr_style), ""],
        [Paragraph("Basic Salary", cell_lbl_style), Paragraph(f"Rs. {f['basic_sal']}", cell_val_style), Paragraph("Paid Salary", cell_lbl_style), Paragraph(f"Rs. {f['paid_sal']}", cell_val_style)],
        [Paragraph("Allowance", cell_lbl_style), Paragraph(f"Rs. {f['allowance']}", cell_val_style), Paragraph("Advance Repayment", cell_lbl_style), Paragraph(f"Rs. {f['adv_repay']}", cell_val_style)],
        [Paragraph("Incentive", cell_lbl_style), Paragraph(f"Rs. {f['incentive']}", cell_val_style), Paragraph("Other Deductions", cell_lbl_style), Paragraph(f"Rs. {f['other_ded']}", cell_val_style)],
        [Paragraph("Other Earnings", cell_lbl_style), Paragraph(f"Rs. {f['other_earn']}", cell_val_style), Paragraph("", cell_lbl_style), Paragraph("", cell_val_style)],
        [Paragraph("TOTAL EARNINGS", ParagraphStyle('TotEarnLbl', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=palette['primary'])),
         Paragraph(f"Rs. {f['tot_earn']}", ParagraphStyle('TotEarnVal', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=palette['primary'])),
         Paragraph("TOTAL DEDUCTIONS", ParagraphStyle('TotDedLbl', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=colors.HexColor('#1a2936'))),
         Paragraph(f"Rs. {f['tot_ded']}", ParagraphStyle('TotDedVal', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=colors.HexColor('#1a2936')))]
    ]
    t_tables = Table(earn_ded_data, colWidths=[160, 105, 165, 110])
    t_tables.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (2, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (1, 0), palette['primary']),
        ('BACKGROUND', (2, 0), (3, 0), colors.HexColor('#1a2936')),
        ('BACKGROUND', (0, 5), (1, 5), colors.HexColor('#e0f2f1')),
        ('BACKGROUND', (2, 5), (3, 5), colors.HexColor('#f1f5f9')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 1), (1, 4), 0.5, colors.HexColor('#f1f5f9')),
        ('LINEBELOW', (2, 1), (3, 4), 0.5, colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t_tables)
    elements.append(Spacer(1, 10))

    # 6. Net Pay Banner (Teal Background with Divider)
    net_banner_data = [[
        [
            Paragraph("<font size='7' color='#e0f2f1'><b>NET PAY</b></font>", ParagraphStyle('NetLbl3', fontName='Helvetica-Bold', leading=8)),
            Paragraph(f"<b>Rs. {f['net_pay_val']}</b>", ParagraphStyle('NetVal3', fontName='Helvetica-Bold', fontSize=17, leading=20, textColor=colors.white))
        ],
        [
            Paragraph("<font size='6.5' color='#e0f2f1'><b>IN WORDS</b></font>", ParagraphStyle('WordsLbl3', fontName='Helvetica-Bold', leading=8, alignment=TA_CENTER)),
            Paragraph(f"<b>{f['net_words_val']}</b>", ParagraphStyle('WordsVal3', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=colors.white))
        ]
    ]]
    t_net = Table(net_banner_data, colWidths=[200, 340])
    t_net.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['primary']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (0, 0), 14),
        ('RIGHTPADDING', (1, 0), (1, 0), 14),
    ]))
    elements.append(t_net)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("<i>Net Pay = Total Earnings - Total Deductions</i>", ParagraphStyle('FootnoteFormula3', fontName='Helvetica-Oblique', fontSize=7, leading=9, textColor=colors.HexColor('#64748b'))))

    # 7. Standardized Footer
    elements.append(Spacer(1, 14))
    footer_data = [[
        Paragraph("Generated by ARGUS Attendance", ParagraphStyle('FtrL3', fontName='Helvetica', fontSize=7.2, leading=9, textColor=colors.HexColor('#64748b'))),
        Paragraph("Argus Attendance | version 5.1 | powered by ArgusCNC(TM)", ParagraphStyle('FtrR3', fontName='Helvetica', fontSize=7.2, leading=9, alignment=TA_CENTER, textColor=colors.HexColor('#64748b')))
    ]]
    t_ftr = Table(footer_data, colWidths=[270, 270])
    t_ftr.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_ftr)

    doc.build(elements)
    buffer.seek(0)
    return buffer

def _build_payslip_classic_grid(p, palette):
    """Builder for Template 4 (Uploaded PDF): Centered header, classic 5-column bordered grid with photo on right."""
    f = _extract_payslip_fields(p)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=26, bottomMargin=26)
    elements = []

    # 1. Centered Header
    logo_img = get_rl_image(f['logo_ref'], max_width=55, max_height=42)
    if logo_img:
        elements.append(logo_img)
        elements.append(Spacer(1, 3))

    elements.append(Paragraph(f"<b>{f['comp_name']}</b>", ParagraphStyle('C4Name', fontName='Helvetica-Bold', fontSize=14, leading=17, alignment=TA_CENTER, textColor=palette['primary'])))
    if f['comp_addr']:
        elements.append(Paragraph(f['comp_addr'], ParagraphStyle('C4Addr', fontName='Helvetica', fontSize=8, leading=11, alignment=TA_CENTER, textColor=colors.HexColor('#0056b3'))))
    if f['contact_str']:
        elements.append(Paragraph(f['contact_str'], ParagraphStyle('C4Contact', fontName='Helvetica', fontSize=7.2, leading=10, alignment=TA_CENTER, textColor=colors.HexColor('#475569'))))
    elements.append(Spacer(1, 3))
    elements.append(Paragraph("<b>Monthly Payslip</b>", ParagraphStyle('C4Sub', fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=TA_CENTER, textColor=colors.black)))
    elements.append(Spacer(1, 5))

    # 2. Section Bar: PAYSLIP
    t_bar = Table([[Paragraph("<b>PAYSLIP</b>", ParagraphStyle('BarTxt', fontName='Helvetica-Bold', fontSize=9, leading=11, alignment=TA_CENTER, textColor=colors.white))]], colWidths=[540])
    t_bar.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['primary']),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#767676')),
    ]))
    elements.append(t_bar)

    # 3. 5-Column Info Table with Employee Photo spanning on right
    emp_photo_img = get_rl_image(f['photo_ref'], max_width=65, max_height=80)
    photo_cell = emp_photo_img if emp_photo_img else Paragraph("<font size='8' color='#94a3b8'>PHOTO</font>", ParagraphStyle('PhPlace', alignment=TA_CENTER))

    cell_l = ParagraphStyle('GridLbl', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.black)
    cell_v = ParagraphStyle('GridVal', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.black)
    cell_v_bold = ParagraphStyle('GridValB', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=palette['primary'])

    grid_data = [
        [Paragraph("Employee Name", cell_l), Paragraph(f['emp_name'], cell_v), Paragraph("Salary Basis", cell_l), Paragraph(f['basis_lbl'], cell_v_bold), photo_cell],
        [Paragraph("Employee ID", cell_l), Paragraph(f['emp_id'], cell_v), Paragraph(f['rate_lbl'].title(), cell_l), Paragraph(f['rate_val'], cell_v), ""],
        [Paragraph("Department", cell_l), Paragraph(f['dept'], cell_v), Paragraph("Designation", cell_l), Paragraph(f['desig'], cell_v), ""],
        [Paragraph("Email ID", cell_l), Paragraph(f['email'], cell_v), Paragraph("Phone Number", cell_l), Paragraph(f['phone'], cell_v), ""],
        [Paragraph("Shift Hours", cell_l), Paragraph(f['shift_h'], cell_v), Paragraph("Bank Name", cell_l), Paragraph(f['bank_name'] or '—', cell_v), ""],
        [Paragraph("Year & Month", cell_l), Paragraph(f['month_badge_val'], cell_v), Paragraph("Working Days", cell_l), Paragraph(f['working_days'], cell_v), ""],
        [Paragraph("Total Working Hours", cell_l), Paragraph(f['tot_work_h'], cell_v), Paragraph("Total Days / Leave", cell_l), Paragraph(f"{f['tot_days']} Days ({f['leave_days']} Leave)", cell_v), ""]
    ]
    t_grid = Table(grid_data, colWidths=[115, 115, 115, 115, 80])
    t_grid.setStyle(TableStyle([
        ('SPAN', (4, 0), (4, 6)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (4, 0), (4, 6), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#767676')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_grid)
    elements.append(Spacer(1, 6))

    # 4. Earnings & Deductions Tables
    hdr_txt_style = ParagraphStyle('G4Hdr', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.white)
    t4_cell_l = ParagraphStyle('G4Lbl', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.black)
    t4_cell_v = ParagraphStyle('G4Val', fontName='Helvetica', fontSize=7.5, leading=9.5, alignment=TA_CENTER, textColor=colors.black)
    t4_tot_l = ParagraphStyle('G4TotL', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.black)
    t4_tot_v = ParagraphStyle('G4TotV', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.black)

    earn_ded_data = [
        [Paragraph("EARNINGS", hdr_txt_style), "", Paragraph("DEDUCTION", hdr_txt_style), ""],
        [Paragraph("Basic Salary", t4_cell_l), Paragraph(f"Rs. {f['basic_sal']}", t4_cell_v), Paragraph("Paid Salary", t4_cell_l), Paragraph(f"Rs. {f['paid_sal']}", t4_cell_v)],
        [Paragraph("Allowance", t4_cell_l), Paragraph(f"Rs. {f['allowance']}", t4_cell_v), Paragraph("Advance Repayment", t4_cell_l), Paragraph(f"Rs. {f['adv_repay']}", t4_cell_v)],
        [Paragraph("Incentive", t4_cell_l), Paragraph(f"Rs. {f['incentive']}", t4_cell_v), Paragraph("Other Deductions", t4_cell_l), Paragraph(f"Rs. {f['other_ded']}", t4_cell_v)],
        [Paragraph("Others Earnings", t4_cell_l), Paragraph(f"Rs. {f['other_earn']}", t4_cell_v), Paragraph("", t4_cell_l), Paragraph("", t4_cell_v)],
        [Paragraph("TOTAL EARNINGS", t4_tot_l), Paragraph(f"Rs. {f['tot_earn']}", t4_tot_v), Paragraph("TOTAL DEDUCTIONS", t4_tot_l), Paragraph(f"Rs. {f['tot_ded']}", t4_tot_v)]
    ]
    t_earn = Table(earn_ded_data, colWidths=[150, 120, 150, 120])
    t_earn.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (2, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (1, 0), palette['primary']),
        ('BACKGROUND', (2, 0), (3, 0), palette['primary']),
        ('BACKGROUND', (0, 5), (-1, 5), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#767676')),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_earn)

    # 5. Dual Stacked Net Pay Bars
    t_net1 = Table([[Paragraph(f"<b>NET PAY : Rs. {f['net_pay_val']}</b>", ParagraphStyle('N1', fontName='Helvetica-Bold', fontSize=11, leading=14, alignment=TA_CENTER, textColor=colors.black))]], colWidths=[540])
    t_net1.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f1f3f5')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#767676')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(t_net1)

    t_net2 = Table([[Paragraph(f"<b>NET PAY IN WORDS: {f['net_words_val']}</b>", ParagraphStyle('N2', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=colors.HexColor('#003366')))]], colWidths=[540])
    t_net2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fef9e7')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#767676')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_net2)

    # 6. Footnotes & Bottom Dark Banner
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("<font size='6.5'><i>** Net Pay = Total Earnings - Total Deduction<br/>* Payslip is auto-generated and valid without the need for a signature. *</i></font>", ParagraphStyle('Fn4', fontName='Helvetica', alignment=TA_CENTER, leading=8.5, textColor=colors.HexColor('#475569'))))
    elements.append(Spacer(1, 4))

    t_dark = Table([[Paragraph("<font color='white'><b>** This document has been automatically generated by ARGUS **</b></font>", ParagraphStyle('Drk4', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, alignment=TA_CENTER, textColor=colors.white))]], colWidths=[540])
    t_dark.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#37474f')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t_dark)
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("© Argus Attendance | version 5.1 | powered by ArgusCNC™", ParagraphStyle('Ftr4', fontName='Helvetica', fontSize=7, leading=9, alignment=TA_CENTER, textColor=colors.gray)))

    doc.build(elements)
    buffer.seek(0)
    return buffer

def _build_payslip_minimalist_card(p, palette):
    """Builder for Template 5 (2nd Uploaded Image): Framed card, colon-aligned metadata, 4 metric cards with icons."""
    f = _extract_payslip_fields(p)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=28, bottomMargin=28)
    elements = []

    # 1. Clean Header (Logo + Company Left, Light Badge Month Right)
    logo_img = get_rl_image(f['logo_ref'], max_width=50, max_height=42)
    logo_cell = [logo_img] if logo_img else [Paragraph(f"<font size='16' color='#1b3b5f'><b>{f['comp_name'][:1]}</b></font>", ParagraphStyle('LogoInit5', alignment=TA_CENTER))]

    hdr_center = [Paragraph(f"<b>{f['comp_name']}</b>", ParagraphStyle('H5Name', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.HexColor('#0f172a')))]
    if f['comp_addr']:
        hdr_center.append(Paragraph(f['comp_addr'], ParagraphStyle('H5Addr', fontName='Helvetica', fontSize=7.5, leading=10, textColor=colors.HexColor('#475569'))))
    if f['contact_str']:
        hdr_center.append(Paragraph(f['contact_str'], ParagraphStyle('H5Contact', fontName='Helvetica', fontSize=6.8, leading=9, textColor=colors.HexColor('#64748b'))))

    hdr_data = [[
        logo_cell,
        hdr_center,
        [
            Paragraph("<font size='6.5' color='#1e40af'><b>MONTHLY PAYSLIP</b></font>", ParagraphStyle('H5B1', fontName='Helvetica-Bold', alignment=TA_CENTER, leading=8)),
            Paragraph(f"<b>{f['month_badge_val']}</b>", ParagraphStyle('H5B2', fontName='Helvetica-Bold', fontSize=12, leading=15, alignment=TA_CENTER, textColor=colors.HexColor('#1e3a8a')))
        ]
    ]]
    t_hdr = Table(hdr_data, colWidths=[52, 348, 140])
    t_hdr.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (2, 0), (2, 0), palette['light_badge']),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('TOPPADDING', (2, 0), (2, 0), 8),
        ('BOTTOMPADDING', (2, 0), (2, 0), 8),
    ]))
    elements.append(t_hdr)
    elements.append(Spacer(1, 8))

    # 2. Employee Details Box (Solid Pill Badge + 2-Column Colon Aligned)
    lbl_s = ParagraphStyle('E5Lbl', fontName='Helvetica', fontSize=7.8, leading=10, textColor=colors.HexColor('#334155'))
    col_s = ParagraphStyle('E5Col', fontName='Helvetica-Bold', fontSize=7.8, leading=10, alignment=TA_CENTER, textColor=colors.HexColor('#64748b'))
    val_s = ParagraphStyle('E5Val', fontName='Helvetica', fontSize=7.8, leading=10, textColor=colors.HexColor('#0f172a'))
    val_sb = ParagraphStyle('E5ValB', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#0f172a'))

    emp_meta = [
        [Paragraph("<b>EMPLOYEE DETAILS</b>", ParagraphStyle('E5Bdg', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white)), "", "", "", "", ""],
        [Paragraph("Employee Name", lbl_s), ":", Paragraph(f['emp_name'], val_sb), Paragraph("Designation", lbl_s), ":", Paragraph(f['desig'], val_sb)],
        [Paragraph("Employee ID", lbl_s), ":", Paragraph(f['emp_id'], val_s), Paragraph("Phone Number", lbl_s), ":", Paragraph(f['phone'], val_s)],
        [Paragraph("Department", lbl_s), ":", Paragraph(f['dept'], val_s), Paragraph("Bank Name", lbl_s), ":", Paragraph(f['bank_display'], val_s)],
        [Paragraph("Email ID", lbl_s), ":", Paragraph(f['email'], val_s), Paragraph("Salary Basis", lbl_s), ":", Paragraph(f['basis_lbl'], val_s)],
        [Paragraph("", lbl_s), ":", Paragraph("", val_s), Paragraph("Hours/Day Salary", lbl_s), ":", Paragraph(f['rate_val'], val_s)]
    ]
    t_meta = Table(emp_meta, colWidths=[100, 14, 146, 95, 14, 171])
    t_meta.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), palette['primary']),
        ('BACKGROUND', (0, 1), (-1, -1), palette['tint']),
        ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (1, 0), (1, -1), 0),
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
        ('LEFTPADDING', (4, 0), (4, -1), 0),
        ('RIGHTPADDING', (4, 0), (4, -1), 0),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (4, 0), (4, -1), 'CENTER'),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 8))

    # 3. 4 Key Metrics Bar (Horizontal Cards)
    m_lbl_s = ParagraphStyle('M5L', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.HexColor('#64748b'))
    m_val_s = ParagraphStyle('M5V', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=colors.HexColor('#0f172a'))
    cards_data = [[
        [Paragraph("SHIFT HOURS", m_lbl_s), Paragraph(f"<b>{f['shift_h']}</b>", m_val_s)],
        [Paragraph("WORKING DAYS", m_lbl_s), Paragraph(f"<b>{f['working_days']}</b>", m_val_s)],
        [Paragraph("TOTAL WORKING HOURS", m_lbl_s), Paragraph(f"<b>{f['tot_work_h']}</b>", m_val_s)],
        [Paragraph("TOTAL DAYS / LEAVE", m_lbl_s), Paragraph(f"<b>{f['tot_days']} Days ({f['leave_days']} Leave)</b>", m_val_s)]
    ]]
    t_cards = Table(cards_data, colWidths=[135, 135, 135, 135])
    t_cards.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['tint']),
        ('BOX', (0, 0), (0, 0), 0.5, palette['border']),
        ('BOX', (1, 0), (1, 0), 0.5, palette['border']),
        ('BOX', (2, 0), (2, 0), 0.5, palette['border']),
        ('BOX', (3, 0), (3, 0), 0.5, palette['border']),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 8))

    # 4. Dual Separate Card Tables
    chdr_s = ParagraphStyle('CHdr5', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.white)
    csub_s = ParagraphStyle('CSub5', fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=colors.HexColor('#475569'))
    csub_r = ParagraphStyle('CSub5R', fontName='Helvetica-Bold', fontSize=7, leading=9, alignment=TA_RIGHT, textColor=colors.HexColor('#475569'))
    cr_l = ParagraphStyle('CRowL', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#334155'))
    cr_r = ParagraphStyle('CRowR', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, alignment=TA_RIGHT, textColor=colors.HexColor('#0f172a'))

    t_earn_data = [
        [Paragraph("EARNINGS", chdr_s), ""],
        [Paragraph("Particulars", csub_s), Paragraph("Amount", csub_r)],
        [Paragraph("Basic Salary", cr_l), Paragraph(f"Rs. {f['basic_sal']}", cr_r)],
        [Paragraph("Allowance", cr_l), Paragraph(f"Rs. {f['allowance']}", cr_r)],
        [Paragraph("Incentive", cr_l), Paragraph(f"Rs. {f['incentive']}", cr_r)],
        [Paragraph("Others Earnings", cr_l), Paragraph(f"Rs. {f['other_earn']}", cr_r)],
        [Paragraph("TOTAL EARNINGS", ParagraphStyle('Tot5L', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=palette['primary'])),
         Paragraph(f"Rs. {f['tot_earn']}", ParagraphStyle('Tot5R', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_RIGHT, textColor=palette['primary']))]
    ]
    t_left = Table(t_earn_data, colWidths=[175, 90])
    t_left.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), palette['primary']),
        ('BACKGROUND', (0, 1), (1, 1), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0, 6), (1, 6), palette['light_badge']),
        ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
        ('LINEBELOW', (0, 2), (1, 5), 0.5, colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))

    t_ded_data = [
        [Paragraph("DEDUCTIONS", chdr_s), ""],
        [Paragraph("Particulars", csub_s), Paragraph("Amount", csub_r)],
        [Paragraph("Paid Salary", cr_l), Paragraph(f"Rs. {f['paid_sal']}", cr_r)],
        [Paragraph("Advance Repayment", cr_l), Paragraph(f"Rs. {f['adv_repay']}", cr_r)],
        [Paragraph("Other Deductions", cr_l), Paragraph(f"Rs. {f['other_ded']}", cr_r)],
        [Paragraph("", cr_l), Paragraph("", cr_r)],
        [Paragraph("TOTAL DEDUCTIONS", ParagraphStyle('Tot5DL', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=palette['primary'])),
         Paragraph(f"Rs. {f['tot_ded']}", ParagraphStyle('Tot5DR', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_RIGHT, textColor=palette['primary']))]
    ]
    t_right = Table(t_ded_data, colWidths=[175, 90])
    t_right.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), palette['primary']),
        ('BACKGROUND', (0, 1), (1, 1), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0, 6), (1, 6), palette['light_badge']),
        ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
        ('LINEBELOW', (0, 2), (1, 5), 0.5, colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))

    t_dual_wrapper = Table([[t_left, "", t_right]], colWidths=[265, 10, 265])
    t_dual_wrapper.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(t_dual_wrapper)
    elements.append(Spacer(1, 8))

    # 5. Soft Net Pay Banner with Rupee Badge
    net_data5 = [[
        [
            Paragraph("<font size='6.5' color='#475569'><b>NET PAY</b></font>", ParagraphStyle('NL5', fontName='Helvetica-Bold', leading=8)),
            Paragraph(f"<b>Rs. {f['net_pay_val']}</b>", ParagraphStyle('NV5', fontName='Helvetica-Bold', fontSize=16, leading=19, textColor=palette['primary']))
        ],
        [
            Paragraph("<font size='6.5' color='#475569'><b>NET PAY IN WORDS</b></font>", ParagraphStyle('NWL5', fontName='Helvetica-Bold', leading=8, alignment=TA_CENTER)),
            Paragraph(f"<b>{f['net_words_val']}</b>", ParagraphStyle('NWV5', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=colors.HexColor('#0f172a')))
        ]
    ]]
    t_net5 = Table(net_data5, colWidths=[200, 340])
    t_net5.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['light_badge']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (0, 0), 12),
        ('RIGHTPADDING', (1, 0), (1, 0), 12),
        ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
    ]))
    elements.append(t_net5)
    elements.append(Spacer(1, 6))

    # Footnote Pill
    t_fn = Table([[Paragraph("Net Pay = Total Earnings - Total Deduction", ParagraphStyle('Fn5', fontName='Helvetica', fontSize=7.2, leading=9, alignment=TA_CENTER, textColor=colors.HexColor('#475569')))]], colWidths=[540])
    t_fn.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['tint']),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_fn)
    elements.append(Spacer(1, 10))

    # Footer
    footer_data = [[
        Paragraph("Generated by ARGUS Attendance", ParagraphStyle('FtrL5', fontName='Helvetica', fontSize=7.2, leading=9, textColor=colors.HexColor('#64748b'))),
        Paragraph("Professional Payroll Document | © Argus Attendance | Version 5.1", ParagraphStyle('FtrR5', fontName='Helvetica', fontSize=7.2, leading=9, alignment=TA_CENTER, textColor=colors.HexColor('#64748b')))
    ]]
    t_ftr = Table(footer_data, colWidths=[270, 270])
    t_ftr.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_ftr)

    doc.build(elements)
    buffer.seek(0)
    return buffer

def _build_payslip_professional_elegant(p, palette):
    """Builder for Template 6 (3rd Uploaded Image): Mint/Forest framed card with person icon & 5x2 aligned metadata."""
    f = _extract_payslip_fields(p)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=28, bottomMargin=28)
    elements = []

    # 1. Elegant Header
    logo_img = get_rl_image(f['logo_ref'], max_width=50, max_height=42)
    logo_cell = [logo_img] if logo_img else [Paragraph(f"<font size='16' color='#0f5132'><b>{f['comp_name'][:1]}</b></font>", ParagraphStyle('LogoInit6', alignment=TA_CENTER))]

    hdr_center = [Paragraph(f"<b>{f['comp_name']}</b>", ParagraphStyle('H6Name', fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=colors.HexColor('#0f172a')))]
    if f['comp_addr']:
        hdr_center.append(Paragraph(f['comp_addr'], ParagraphStyle('H6Addr', fontName='Helvetica', fontSize=7.5, leading=10, textColor=colors.HexColor('#475569'))))
    if f['contact_str']:
        hdr_center.append(Paragraph(f['contact_str'], ParagraphStyle('H6Contact', fontName='Helvetica', fontSize=6.8, leading=9, textColor=colors.HexColor('#64748b'))))

    hdr_data = [[
        logo_cell,
        hdr_center,
        [
            Paragraph("<font size='6.5' color='#065f46'><b>MONTHLY PAYSLIP</b></font>", ParagraphStyle('H6B1', fontName='Helvetica-Bold', alignment=TA_CENTER, leading=8)),
            Paragraph(f"<b>{f['month_badge_val']}</b>", ParagraphStyle('H6B2', fontName='Helvetica-Bold', fontSize=12, leading=15, alignment=TA_CENTER, textColor=colors.HexColor('#064e3b')))
        ]
    ]]
    t_hdr = Table(hdr_data, colWidths=[52, 348, 140])
    t_hdr.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (2, 0), (2, 0), palette['light_badge']),
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),
        ('TOPPADDING', (2, 0), (2, 0), 8),
        ('BOTTOMPADDING', (2, 0), (2, 0), 8),
    ]))
    elements.append(t_hdr)
    elements.append(Spacer(1, 8))

    # 2. Employee Details Box (Badge with Person Icon + 5x2 list including Year & Month)
    lbl_s = ParagraphStyle('E6Lbl', fontName='Helvetica', fontSize=7.8, leading=10, textColor=colors.HexColor('#334155'))
    col_s = ParagraphStyle('E6Col', fontName='Helvetica-Bold', fontSize=7.8, leading=10, alignment=TA_CENTER, textColor=colors.HexColor('#64748b'))
    val_s = ParagraphStyle('E6Val', fontName='Helvetica', fontSize=7.8, leading=10, textColor=colors.HexColor('#0f172a'))
    val_sb = ParagraphStyle('E6ValB', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#0f172a'))

    emp_meta = [
        [Paragraph("<b>EMPLOYEE DETAILS</b>", ParagraphStyle('E6Bdg', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white)), "", "", "", "", ""],
        [Paragraph("Employee Name", lbl_s), ":", Paragraph(f['emp_name'], val_sb), Paragraph("Phone Number", lbl_s), ":", Paragraph(f['phone'], val_s)],
        [Paragraph("Employee ID", lbl_s), ":", Paragraph(f['emp_id'], val_s), Paragraph("Bank Name", lbl_s), ":", Paragraph(f['bank_display'], val_s)],
        [Paragraph("Department", lbl_s), ":", Paragraph(f['dept'], val_s), Paragraph("Salary Basis", lbl_s), ":", Paragraph(f['basis_lbl'], val_s)],
        [Paragraph("Email ID", lbl_s), ":", Paragraph(f['email'], val_s), Paragraph("Hours/Day Salary", lbl_s), ":", Paragraph(f['rate_val'], val_s)],
        [Paragraph("Designation", lbl_s), ":", Paragraph(f['desig'], val_s), Paragraph("Year & Month", lbl_s), ":", Paragraph(f"<b>{f['month_badge_val']}</b>", val_sb)]
    ]
    t_meta = Table(emp_meta, colWidths=[100, 14, 146, 95, 14, 171])
    t_meta.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), palette['primary']),
        ('BACKGROUND', (0, 1), (-1, -1), palette['tint']),
        ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (1, 0), (1, -1), 0),
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
        ('LEFTPADDING', (4, 0), (4, -1), 0),
        ('RIGHTPADDING', (4, 0), (4, -1), 0),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (4, 0), (4, -1), 'CENTER'),
    ]))
    elements.append(t_meta)
    elements.append(Spacer(1, 8))

    # 3. 4 Key Metrics Bar
    m_lbl_s = ParagraphStyle('M6L', fontName='Helvetica-Bold', fontSize=6.5, leading=8, textColor=colors.HexColor('#64748b'))
    m_val_s = ParagraphStyle('M6V', fontName='Helvetica-Bold', fontSize=9.5, leading=12, textColor=colors.HexColor('#0f172a'))
    cards_data = [[
        [Paragraph("SHIFT HOURS", m_lbl_s), Paragraph(f"<b>{f['shift_h']}</b>", m_val_s)],
        [Paragraph("WORKING DAYS", m_lbl_s), Paragraph(f"<b>{f['working_days']}</b>", m_val_s)],
        [Paragraph("TOTAL WORKING HOURS", m_lbl_s), Paragraph(f"<b>{f['tot_work_h']}</b>", m_val_s)],
        [Paragraph("TOTAL DAYS / LEAVE", m_lbl_s), Paragraph(f"<b>{f['tot_days']} Days ({f['leave_days']} Leave)</b>", m_val_s)]
    ]]
    t_cards = Table(cards_data, colWidths=[135, 135, 135, 135])
    t_cards.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['tint']),
        ('BOX', (0, 0), (0, 0), 0.5, palette['border']),
        ('BOX', (1, 0), (1, 0), 0.5, palette['border']),
        ('BOX', (2, 0), (2, 0), 0.5, palette['border']),
        ('BOX', (3, 0), (3, 0), 0.5, palette['border']),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(t_cards)
    elements.append(Spacer(1, 8))

    # 4. Dual Separate Card Tables
    chdr_s = ParagraphStyle('CHdr6', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.white)
    csub_s = ParagraphStyle('CSub6', fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=colors.HexColor('#475569'))
    csub_r = ParagraphStyle('CSub6R', fontName='Helvetica-Bold', fontSize=7, leading=9, alignment=TA_RIGHT, textColor=colors.HexColor('#475569'))
    cr_l = ParagraphStyle('CRow6L', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=colors.HexColor('#334155'))
    cr_r = ParagraphStyle('CRow6R', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, alignment=TA_RIGHT, textColor=colors.HexColor('#0f172a'))

    t_earn_data = [
        [Paragraph("EARNINGS", chdr_s), ""],
        [Paragraph("Particulars", csub_s), Paragraph("Amount", csub_r)],
        [Paragraph("Basic Salary", cr_l), Paragraph(f"Rs. {f['basic_sal']}", cr_r)],
        [Paragraph("Allowance", cr_l), Paragraph(f"Rs. {f['allowance']}", cr_r)],
        [Paragraph("Incentive", cr_l), Paragraph(f"Rs. {f['incentive']}", cr_r)],
        [Paragraph("Others Earnings", cr_l), Paragraph(f"Rs. {f['other_earn']}", cr_r)],
        [Paragraph("TOTAL EARNINGS", ParagraphStyle('Tot6L', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=palette['primary'])),
         Paragraph(f"Rs. {f['tot_earn']}", ParagraphStyle('Tot6R', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_RIGHT, textColor=palette['primary']))]
    ]
    t_left = Table(t_earn_data, colWidths=[175, 90])
    t_left.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), palette['primary']),
        ('BACKGROUND', (0, 1), (1, 1), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0, 6), (1, 6), palette['light_badge']),
        ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
        ('LINEBELOW', (0, 2), (1, 5), 0.5, colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))

    t_ded_data = [
        [Paragraph("DEDUCTIONS", chdr_s), ""],
        [Paragraph("Particulars", csub_s), Paragraph("Amount", csub_r)],
        [Paragraph("Paid Salary", cr_l), Paragraph(f"Rs. {f['paid_sal']}", cr_r)],
        [Paragraph("Advance Repayment", cr_l), Paragraph(f"Rs. {f['adv_repay']}", cr_r)],
        [Paragraph("Other Deductions", cr_l), Paragraph(f"Rs. {f['other_ded']}", cr_r)],
        [Paragraph("", cr_l), Paragraph("", cr_r)],
        [Paragraph("TOTAL DEDUCTIONS", ParagraphStyle('Tot6DL', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=palette['primary'])),
         Paragraph(f"Rs. {f['tot_ded']}", ParagraphStyle('Tot6DR', fontName='Helvetica-Bold', fontSize=8, leading=10, alignment=TA_RIGHT, textColor=palette['primary']))]
    ]
    t_right = Table(t_ded_data, colWidths=[175, 90])
    t_right.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), palette['primary']),
        ('BACKGROUND', (0, 1), (1, 1), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (0, 6), (1, 6), palette['light_badge']),
        ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
        ('LINEBELOW', (0, 2), (1, 5), 0.5, colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))

    t_dual_wrapper = Table([[t_left, "", t_right]], colWidths=[265, 10, 265])
    t_dual_wrapper.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(t_dual_wrapper)
    elements.append(Spacer(1, 8))

    # 5. Soft Net Pay Banner with Cash Stack Icon
    net_data6 = [[
        [
            Paragraph("<font size='6.5' color='#475569'><b>NET PAY</b></font>", ParagraphStyle('NL6', fontName='Helvetica-Bold', leading=8)),
            Paragraph(f"<b>Rs. {f['net_pay_val']}</b>", ParagraphStyle('NV6', fontName='Helvetica-Bold', fontSize=16, leading=19, textColor=palette['primary']))
        ],
        [
            Paragraph("<font size='6.5' color='#475569'><b>NET PAY IN WORDS</b></font>", ParagraphStyle('NWL6', fontName='Helvetica-Bold', leading=8, alignment=TA_CENTER)),
            Paragraph(f"<b>{f['net_words_val']}</b>", ParagraphStyle('NWV6', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_CENTER, textColor=colors.HexColor('#0f172a')))
        ]
    ]]
    t_net6 = Table(net_data6, colWidths=[200, 340])
    t_net6.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['light_badge']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (0, 0), 12),
        ('RIGHTPADDING', (1, 0), (1, 0), 12),
        ('BOX', (0, 0), (-1, -1), 0.5, palette['border']),
    ]))
    elements.append(t_net6)
    elements.append(Spacer(1, 6))

    # Footnote Pill
    t_fn = Table([[Paragraph("Net Pay = Total Earnings - Total Deduction", ParagraphStyle('Fn6', fontName='Helvetica', fontSize=7.2, leading=9, alignment=TA_CENTER, textColor=colors.HexColor('#475569')))]], colWidths=[540])
    t_fn.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['tint']),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_fn)
    elements.append(Spacer(1, 10))

    # Footer
    footer_data = [[
        Paragraph("Generated by ARGUS Attendance", ParagraphStyle('FtrL6', fontName='Helvetica', fontSize=7.2, leading=9, textColor=colors.HexColor('#64748b'))),
        Paragraph("Professional Payroll Document | © Argus Attendance | Version 5.1", ParagraphStyle('FtrR6', fontName='Helvetica', fontSize=7.2, leading=9, alignment=TA_CENTER, textColor=colors.HexColor('#64748b')))
    ]]
    t_ftr = Table(footer_data, colWidths=[270, 270])
    t_ftr.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(t_ftr)

    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_payslip_pdf(p, template_id='template_1', theme='navy'):
    """Main entry point: dispatches payslip PDF generation to the requested template (1..6) and theme."""
    tmpl = str(template_id or 'template_1').lower().strip()
    theme_key = str(theme or 'navy').lower().strip()
    palette = PAYSLIP_THEMES.get(theme_key, PAYSLIP_THEMES['navy'])

    if tmpl == 'template_4':
        return _build_payslip_classic_grid(p, palette)
    elif tmpl == 'template_5':
        return _build_payslip_minimalist_card(p, palette)
    elif tmpl == 'template_6':
        return _build_payslip_professional_elegant(p, palette)
    elif tmpl == 'template_3':
        return _build_payslip_premium_executive(p, palette)
    else:
        # Default: template_1 (with signatory) or template_2 (streamlined/paperless)
        return _build_payslip_modern_executive(p, tmpl, palette)

def Number_format(val):
    """Formats numeric value with commas (e.g. 1000 -> '1,000')."""
    try:
        return f"{int(float(val)):,}"
    except Exception:
        return str(val)

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





