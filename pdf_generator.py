import io
import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

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
    
    # Header logo or company text
    elements.append(Paragraph("ARGUS TECHNOLOGIES", title_style))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("EMPLOYEE DETAILS", subtitle_style))
    elements.append(Spacer(1, 15))
    
    # Fields table matching Image 4
    fields = [
        ("ID", str(emp.get('id', ''))),
        ("EMPLOYEE NAME", str(emp.get('employee_name', ''))),
        ("DESIGNATION", str(emp.get('designation', ''))),
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
        ("SHIFT HOURS", str(emp.get('shift_hours', '')))
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
    elements.append(Paragraph("© Argus Technologies | version 4.5", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_live_report_pdf(title, entries):
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
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#3d6078')
    )
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
    elements.append(Paragraph("ARGUS TECHNOLOGIES", title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(title.upper(), subtitle_style))
    elements.append(Spacer(1, 14))
    
    table_data = [
        [
            Paragraph("EMPLOYEE NAME", header_style),
            Paragraph("ENTRY TIME", header_style),
            Paragraph("SITE NAME", header_style),
            Paragraph("ENTRY LOCATION", header_style),
            Paragraph("ENTRY DISTANCE", header_style)
        ]
    ]
    
    for row in entries:
        table_data.append([
            Paragraph(str(row.get('employee_name', '')), cell_style),
            Paragraph(str(row.get('entry_time', '')), cell_style),
            Paragraph(str(row.get('site_name', '')), cell_style),
            Paragraph(str(row.get('entry_location', '')), cell_style),
            Paragraph(str(row.get('entry_distance', '0')), cell_style)
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
    elements.append(Paragraph("© Argus Technologies | version 4.5", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_attendance_report_pdf(title, entries, is_simple=False, totals=None):
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
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#3d6078')
    )
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
    elements.append(Paragraph("ARGUS TECHNOLOGIES", title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(title.upper(), subtitle_style))
    elements.append(Spacer(1, 12))
    
    if not is_simple:
        # Full view table (omitting image columns)
        table_data = [
            [
                Paragraph("EMPLOYEE NAME", header_style),
                Paragraph("ENTRY TIME", header_style),
                Paragraph("ENTRY DISTANCE", header_style),
                Paragraph("ENTRY LOCATION", header_style),
                Paragraph("EXIT TIME", header_style),
                Paragraph("EXIT DISTANCE", header_style),
                Paragraph("EXIT LOCATION", header_style),
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
                Paragraph(str(r.get('exit_time', '')), cell_style),
                Paragraph(str(r.get('exit_distance', '')), cell_style),
                Paragraph(str(r.get('exit_location', '')), cell_style),
                Paragraph(str(r.get('working_hours', '')), cell_style),
                Paragraph(str(r.get('shift_variance', '')), cell_style),
                Paragraph(str(r.get('working_salary', '0')), cell_style)
            ])
            
        col_widths = [65, 65, 65, 140, 65, 65, 140, 50, 45, 50]
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
    elements.append(Paragraph("© Argus Technologies | version 4.5", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_manual_entries_pdf(entries):
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
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#3d6078')
    )
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
    elements.append(Paragraph("ARGUS TECHNOLOGIES", title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("MANUAL ENTRIES REPORT", subtitle_style))
    elements.append(Spacer(1, 14))
    
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
    elements.append(Paragraph("© Argus Technologies | version 4.5", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_payments_pdf(payments):
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
    elements.append(Paragraph("ARGUS TECHNOLOGIES", title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("PAYMENT MANAGEMENT REPORT", subtitle_style))
    elements.append(Spacer(1, 14))
    
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
    elements.append(Paragraph("© Argus Technologies | version 4.5", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_advances_pdf(advances):
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
    elements.append(Paragraph("ARGUS TECHNOLOGIES", title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("ADVANCE MANAGEMENT REPORT", subtitle_style))
    elements.append(Spacer(1, 14))
    
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
    elements.append(Paragraph("© Argus Technologies | version 4.5", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_balance_report_pdf(data, totals=None):
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
    elements.append(Paragraph("ARGUS TECHNOLOGIES", title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("BALANCE REPORT", subtitle_style))
    elements.append(Spacer(1, 14))
    
    table_data = [
        [
            Paragraph("TIMESTAMP", header_style),
            Paragraph("NAME", header_style),
            Paragraph("DATE", header_style),
            Paragraph("ADVANCE AMOUNT", header_style),
            Paragraph("ADVANCE REPAYMENT AMOUNT", header_style),
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
            table_data.append([
                Paragraph(str(r.get('timestamp', '')), cell_style),
                Paragraph(str(r.get('name', '')), cell_style),
                Paragraph(str(r.get('date', '')), cell_style),
                Paragraph(f"{float(r.get('advance_amount', 0)):.2f}", cell_style),
                Paragraph(f"{float(r.get('advance_repayment_amount', 0)):.2f}", cell_style),
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
        tot_text = f"<b>Total Advance:</b> {totals.get('total_advance', 0.0):.2f} &nbsp;&nbsp;&nbsp;&nbsp; <b>Total Advance Repayment:</b> {totals.get('total_repayment', 0.0):.2f} &nbsp;&nbsp;&nbsp;&nbsp; <b>Balance Amount:</b> {totals.get('balance_amount', 0.0):.2f}"
        elements.append(Paragraph(tot_text, ParagraphStyle('Totals', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#0d6efd'))))
        elements.append(Spacer(1, 14))
        
    elements.append(Paragraph("© Argus Technologies | version 4.5", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    doc.build(elements)
    buffer.seek(0)
    return buffer

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
    
    # Header
    title_style = ParagraphStyle('CompTitle', fontName='Helvetica-Bold', fontSize=16, leading=20, alignment=TA_CENTER, textColor=colors.HexColor('#003366'))
    addr_style = ParagraphStyle('CompAddr', fontName='Helvetica', fontSize=8, leading=11, alignment=TA_CENTER, textColor=colors.HexColor('#0056b3'))
    sub_style = ParagraphStyle('CompSub', fontName='Helvetica-Bold', fontSize=11, leading=15, alignment=TA_CENTER, textColor=colors.HexColor('#212529'))
    
    elements.append(Paragraph(p.get('company_name', 'ARGUS TECHNOLOGIES'), title_style))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(p.get('company_address', ''), addr_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("Monthly Payslip", sub_style))
    elements.append(Spacer(1, 10))
    
    cell_lbl_style = ParagraphStyle('CellLbl', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.HexColor('#212529'))
    cell_val_style = ParagraphStyle('CellVal', fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#333333'))
    
    # 4-column Employee Info Table
    info_data = [
        [Paragraph("PAYSLIP", ParagraphStyle('SectionHdr', fontName='Helvetica-Bold', fontSize=10, leading=12, alignment=TA_CENTER, textColor=colors.white)), "", "", ""],
        [Paragraph("Employee Name", cell_lbl_style), Paragraph(str(p.get('employee_name', '')), cell_val_style), Paragraph("Hours Salary", cell_lbl_style), Paragraph(f"Rs. {p.get('hours_salary', 0)}", cell_val_style)],
        [Paragraph("Employee ID", cell_lbl_style), Paragraph(str(p.get('employee_id', '')), cell_val_style), Paragraph("Day Salary", cell_lbl_style), Paragraph(f"Rs. {p.get('day_salary', 0)}", cell_val_style)],
        [Paragraph("Designation", cell_lbl_style), Paragraph(str(p.get('designation', '')), cell_val_style), Paragraph("Half Day Salary", cell_lbl_style), Paragraph(f"Rs. {p.get('half_day_salary', 0)}", cell_val_style)],
        [Paragraph("Phone Number", cell_lbl_style), Paragraph(str(p.get('phone_number', '')), cell_val_style), Paragraph("Working Days", cell_lbl_style), Paragraph(str(p.get('working_days', 0)), cell_val_style)],
        [Paragraph("Year & Month", cell_lbl_style), Paragraph(str(p.get('year_month', '')), cell_val_style), Paragraph("Leave Days", cell_lbl_style), Paragraph(str(p.get('leave_days', 0)), cell_val_style)],
        [Paragraph("Total Working Hours", cell_lbl_style), Paragraph(str(p.get('total_working_hours', '00:00')), cell_val_style), Paragraph("Total Days of this Month", cell_lbl_style), Paragraph(str(p.get('total_days_of_month', 30)), cell_val_style)],
    ]
    
    t_info = Table(info_data, colWidths=[120, 150, 130, 140])
    t_info.setStyle(TableStyle([
        ('SPAN', (0, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (3, 0), colors.HexColor('#1565c0')),
        ('ALIGN', (0, 0), (3, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#767676')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_info)
    elements.append(Spacer(1, 10))
    
    # Earnings & Deductions Table
    earn_ded_data = [
        [Paragraph("EARNINGS", ParagraphStyle('EarnHdr', fontName='Helvetica-Bold', fontSize=9, leading=11, alignment=TA_CENTER, textColor=colors.white)), "",
         Paragraph("DEDUCTION", ParagraphStyle('DedHdr', fontName='Helvetica-Bold', fontSize=9, leading=11, alignment=TA_CENTER, textColor=colors.white)), ""],
        [Paragraph("Basic Salary", cell_lbl_style), Paragraph(f"Rs. {p.get('basic_salary', 0)}", cell_val_style), Paragraph("Paid Salary", cell_lbl_style), Paragraph(f"Rs. {p.get('paid_salary', 0)}", cell_val_style)],
        [Paragraph("Allowance", cell_lbl_style), Paragraph(f"Rs. {p.get('allowance', 0)}", cell_val_style), Paragraph("Advance Repayment", cell_lbl_style), Paragraph(f"Rs. {p.get('advance_repayment', 0)}", cell_val_style)],
        [Paragraph("Incentive", cell_lbl_style), Paragraph(f"Rs. {p.get('incentive', 0)}", cell_val_style), Paragraph("Other Deductions", cell_lbl_style), Paragraph(f"Rs. {p.get('other_deductions', 0)}", cell_val_style)],
        [Paragraph("Others Earnings", cell_lbl_style), Paragraph(f"Rs. {p.get('other_earnings', 0)}", cell_val_style), Paragraph("", cell_lbl_style), Paragraph("", cell_val_style)],
        [Paragraph("TOTAL EARNINGS", cell_lbl_style), Paragraph(f"Rs. {p.get('total_earnings', 0)}", cell_lbl_style), Paragraph("", cell_lbl_style), Paragraph("", cell_val_style)],
        [Paragraph("TOTAL DEDUCTION", cell_lbl_style), Paragraph(f"Rs. {p.get('total_deduction', 0)}", cell_lbl_style), Paragraph("", cell_lbl_style), Paragraph("", cell_val_style)],
    ]
    
    t_earn = Table(earn_ded_data, colWidths=[150, 120, 150, 120])
    t_earn.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (2, 0), (3, 0)),
        ('BACKGROUND', (0, 0), (1, 0), colors.HexColor('#0d47a1')),
        ('BACKGROUND', (2, 0), (3, 0), colors.HexColor('#0d47a1')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#767676')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t_earn)
    elements.append(Spacer(1, 10))
    
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
    
    doc.build(elements)
    buffer.seek(0)
    return buffer

def generate_salary_report_pdf(data):
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
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#2c3e50')
    )
    
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
    elements.append(Paragraph("ARGUS TECHNOLOGIES", title_style))
    elements.append(Spacer(1, 3))
    elements.append(Paragraph("SALARY REPORT", ParagraphStyle('Sub', fontName='Helvetica-Bold', fontSize=11, leading=14, alignment=TA_CENTER, textColor=colors.HexColor('#3d6078'))))
    elements.append(Spacer(1, 10))
    
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
    elements.append(Paragraph("© Argus Technologies | version 4.5", ParagraphStyle('Footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER, textColor=colors.gray)))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer





