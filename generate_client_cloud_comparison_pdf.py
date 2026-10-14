import os
import sys
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Adds running header on page 2 and clean 'Page X of Y' footer on all pages."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#64748b"))

        # Running Top Header on Page 2
        if self._pageNumber > 1:
            self.drawString(45, letter[1] - 30, "ARGUS TECHNOLOGIES  |  CLOUD HOSTING EVALUATION FOR CLIENT DECISION")
            self.setFont("Helvetica", 8)
            self.drawRightString(letter[0] - 45, letter[1] - 30, "RENDER vs. AWS COMPARISON")
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.5)
            self.line(45, letter[1] - 36, letter[0] - 45, letter[1] - 36)

        # Running Bottom Footer
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.75)
        self.line(45, 36, letter[0] - 45, 36)

        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(45, 24, "Confidential  |  Prepared for Client Review & Commercial Decision")
        
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 45, 24, page_str)
        self.restoreState()


def create_cloud_comparison_pdf(output_path):
    # Page setup: Margins 45pt (0.625 inch) for maximum clean printable area
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=45,
        rightMargin=45,
        topMargin=36,
        bottomMargin=42
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=21,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=2
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#475569'),
        spaceAfter=8
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#0f172a'),
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor('#334155'),
        spaceAfter=4
    )

    callout_text = ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12.5,
        textColor=colors.HexColor('#1e293b')
    )

    tbl_head = ParagraphStyle(
        'TblHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#ffffff')
    )

    tbl_cell = ParagraphStyle(
        'TblCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#1e293b')
    )

    tbl_cell_bold = ParagraphStyle(
        'TblCellBold',
        parent=tbl_cell,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#0f172a')
    )

    tbl_cell_green = ParagraphStyle(
        'TblCellGreen',
        parent=tbl_cell,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#15803d')
    )

    story = []

    # =========================================================================
    # PAGE 1: Executive Overview, Problem Analogy, Provider Basics, Cost Table
    # =========================================================================

    # Header with Letterhead
    header_data = [
        [
            Paragraph("<b>ARGUS TECHNOLOGIES</b><br/><font size=7.5 color='#64748b'>Workforce Automation, AI Attendance &amp; Cloud Systems</font>", body_style),
            Paragraph("<font color='#2563eb'><b>COMMERCIAL PROPOSAL</b></font><br/><font size=7.5 color='#64748b'>Date: October 2026 &nbsp;|&nbsp; Version 2.0</font>", ParagraphStyle('HdrR', parent=body_style, alignment=2))
        ]
    ]
    hdr_table = Table(header_data, colWidths=[330, 192])
    hdr_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(hdr_table)
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563eb'), spaceBefore=4, spaceAfter=8))

    # Title
    story.append(Paragraph("Cloud Server Hosting &amp; Annual Cost Evaluation", title_style))
    story.append(Paragraph("A Plain-English Business Guide for Decision Makers: <b>Render vs. Amazon Web Services (AWS)</b>", subtitle_style))

    # Executive Summary Box
    summary_html = """
    <b>Executive Summary:</b><br/>
    Our Attendance and Field Workforce application is currently running on a <b>Free Hosting Server</b>.
    Free servers automatically enter <b>'Sleep Mode'</b> whenever no one uses the system for 15 minutes, causing a 60-second delay on the next visit.
    Upgrading to an <b>Always-On Server</b> guarantees the application opens <b>instantly in under 1 second</b> for all workers 24/7.
    This document outlines the simplest, most cost-effective path forward.
    """
    summary_box = Table([[Paragraph(summary_html, callout_text)]], colWidths=[522])
    summary_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eff6ff')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#bfdbfe')),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(summary_box)
    story.append(Spacer(1, 6))

    # 1. The Problem Explained
    story.append(Paragraph("1. Why Does the Application Pause or Feel Slow Right Now?", h1_style))
    story.append(Paragraph(
        "Think of our current free server like a <b>television that goes into 'Power-Saving Sleep Mode'</b> when no one presses a button for 15 minutes. "
        "When an employee arrives in the morning and tries to punch attendance, the server has to wake up, turn on its engines, and reconnect to the database. "
        "This creates a <b>50 to 90 second delay</b> before the screen responds. "
        "To employees and managers, it feels like the application is frozen or broken.",
        body_style
    ))
    story.append(Paragraph(
        "<b>The Solution:</b> A paid server is <b>Always-On (running 24 hours a day, 365 days a year)</b>. "
        "Whether it is 8:55 AM or midnight, the application responds <b>instantly in less than 1 second.</b>",
        body_style
    ))
    story.append(Spacer(1, 4))

    # 2. Render vs AWS in Simple Terms
    story.append(Paragraph("2. Understanding the Options in Plain Business Terms", h1_style))
    story.append(Paragraph(
        "- <b>Option A (Render):</b> Think of Render like renting a <i>fully furnished executive apartment</i>. Everything (electricity, security, maintenance, updates) is managed for you. We flip a single switch, pay a fixed small fee, and it runs reliably with <b>zero developer maintenance</b>.<br/>"
        "- <b>Option B (AWS - Amazon Web Services):</b> Think of AWS like <i>owning a large commercial building</i>. It offers infinite scalability and global infrastructure. However, it requires technical upkeep, server management, and careful monitoring to avoid complex billing surprises.<br/>"
        "- <b>What About Our Database (MongoDB)?</b> Good news: <b>Our database does NOT need to change.</b> It is already hosted on the cloud (MongoDB Atlas) and safely holds all employee records, face biometrics, and payslips without extra costs.",
        body_style
    ))
    story.append(Spacer(1, 4))

    # 3. Cost Table
    story.append(Paragraph("3. Annual Cost Breakdown (USD &amp; Indian Rupees)", h1_style))
    story.append(Paragraph(
        "All calculations assume a standard currency exchange rate of <b>1 USD = Rs. 84</b>:",
        body_style
    ))

    table_data = [
        [
            Paragraph("<b>Hosting Plan &amp; Provider</b>", tbl_head),
            Paragraph("<b>Target Capacity</b>", tbl_head),
            Paragraph("<b>Monthly Cost</b>", tbl_head),
            Paragraph("<b>Annual (USD)</b>", tbl_head),
            Paragraph("<b>Annual (INR)</b>", tbl_head),
            Paragraph("<b>Performance</b>", tbl_head)
        ],
        [
            Paragraph("<b>Render Free Tier</b><br/><font size=6.5 color='#64748b'>Current Setup</font>", tbl_cell_bold),
            Paragraph("Testing Only<br/>(1 - 2 users)", tbl_cell),
            Paragraph("$0 / mo", tbl_cell),
            Paragraph("$0", tbl_cell_bold),
            Paragraph("Rs. 0", tbl_cell_bold),
            Paragraph("<font color='#dc2626'><b>Sleeps after 15m</b><br/>(60-90s delay)</font>", tbl_cell)
        ],
        [
            Paragraph("<b>Render Starter Plan</b><br/><font size=6.5 color='#2563eb'>RECOMMENDED (Phase 1)</font>", tbl_cell_bold),
            Paragraph("Up to 25 Companies<br/>(500 - 1,500 workers)", tbl_cell),
            Paragraph("<b>$7.00 / mo</b>", tbl_cell_bold),
            Paragraph("<b>$84.00 / yr</b>", tbl_cell_bold),
            Paragraph("<b>Rs. 7,050 / yr</b>", tbl_cell_green),
            Paragraph("<font color='#15803d'><b>100% Always-On</b><br/>(Instant &lt; 1 sec)</font>", tbl_cell)
        ],
        [
            Paragraph("<b>AWS Lightsail</b><br/><font size=6.5 color='#0284c7'>Amazon Small Business Cloud</font>", tbl_cell_bold),
            Paragraph("Up to 25 Companies<br/>(500 - 2,000 workers)", tbl_cell),
            Paragraph("$5.00 / mo<br/><font size=6.5 color='#15803d'>(3 Mo Free)</font>", tbl_cell),
            Paragraph("$45 - $60 / yr", tbl_cell_bold),
            Paragraph("Rs. 3,800 - 5,000", tbl_cell_green),
            Paragraph("<font color='#15803d'><b>100% Always-On</b><br/>(AWS Mumbai ~20ms)</font>", tbl_cell)
        ],
        [
            Paragraph("<b>Render Standard Plan</b><br/><font size=6.5 color='#64748b'>Growth Tier</font>", tbl_cell_bold),
            Paragraph("Up to 50 Companies<br/>(2,000 - 5,000 workers)", tbl_cell),
            Paragraph("$25.00 / mo", tbl_cell),
            Paragraph("$300.00 / yr", tbl_cell_bold),
            Paragraph("Rs. 25,200 / yr", tbl_cell_bold),
            Paragraph("<font color='#15803d'><b>High Performance</b><br/>(2GB RAM, fast CPU)</font>", tbl_cell)
        ],
        [
            Paragraph("<b>AWS Full Enterprise</b><br/><font size=6.5 color='#64748b'>App Runner / ECS Fargate</font>", tbl_cell_bold),
            Paragraph("100+ Companies<br/>(10,000+ workers)", tbl_cell),
            Paragraph("$35 - $75 / mo", tbl_cell),
            Paragraph("$420 - $900 / yr", tbl_cell_bold),
            Paragraph("Rs. 35,000 - 75,000", tbl_cell_bold),
            Paragraph("<font color='#15803d'><b>Auto-scaling</b><br/>(Enterprise Grade)</font>", tbl_cell)
        ]
    ]

    col_widths = [130, 95, 75, 74, 76, 72]
    cost_table = Table(table_data, colWidths=col_widths)
    cost_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#102a45')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#fef2f2')),  # Light red for free tier
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#f0fdf4')),  # Light green for recommended
        ('ROWBACKGROUNDS', (0, 3), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
    ]))
    story.append(cost_table)

    # Force PageBreak to guarantee a perfectly balanced 2-page document
    story.append(PageBreak())

    # =========================================================================
    # PAGE 2: Side-by-Side Comparison, Strategic Recommendation, Action Plan & Sign-off
    # =========================================================================

    story.append(Paragraph("4. Side-by-Side Feature Comparison (Plain English)", h1_style))

    comp_data = [
        [
            Paragraph("<b>Evaluation Factor</b>", tbl_head),
            Paragraph("<b>Render (Starter Plan)</b>", tbl_head),
            Paragraph("<b>AWS (Lightsail Cloud)</b>", tbl_head)
        ],
        [
            Paragraph("<b>Server Sleep / Inactivity</b>", tbl_cell_bold),
            Paragraph("<b>Never sleeps.</b> Always on 24 hours a day, 7 days a week.", tbl_cell),
            Paragraph("<b>Never sleeps.</b> Always on 24 hours a day, 7 days a week.", tbl_cell)
        ],
        [
            Paragraph("<b>Speed &amp; Employee Response</b>", tbl_cell_bold),
            Paragraph("Instant response (&lt; 1 sec for camera, login, reports).", tbl_cell),
            Paragraph("Instant response (&lt; 1 sec from AWS Mumbai data center).", tbl_cell)
        ],
        [
            Paragraph("<b>Setup &amp; Downtime</b>", tbl_cell_bold),
            Paragraph("<b>1-Click Upgrade (Zero downtime).</b> Ready in 60 seconds.", tbl_cell),
            Paragraph("Requires approx. 1 to 2 hours of server configuration.", tbl_cell)
        ],
        [
            Paragraph("<b>Server Maintenance</b>", tbl_cell_bold),
            Paragraph("<b>100% Fully Managed.</b> Render handles all OS security updates.", tbl_cell),
            Paragraph("Requires manual Linux administration and security monitoring.", tbl_cell)
        ],
        [
            Paragraph("<b>Predictable Billing</b>", tbl_cell_bold),
            Paragraph("<b>Fixed, predictable $7/mo (Rs. 580/mo).</b> Zero hidden fees.", tbl_cell),
            Paragraph("Fixed on Lightsail ($5/mo), but variable on storage and bandwidth.", tbl_cell)
        ],
        [
            Paragraph("<b>Customer Capacity</b>", tbl_cell_bold),
            Paragraph("Easily supports up to 25 companies and 1,500 active employees.", tbl_cell),
            Paragraph("Can scale up to tens of thousands of users across India.", tbl_cell)
        ],
        [
            Paragraph("<b>Annual Investment</b>", tbl_cell_bold),
            Paragraph("<b>$84 / year &nbsp;(approx. Rs. 7,050 / year)</b>", tbl_cell_green),
            Paragraph("<b>$45 - $60 / year &nbsp;(approx. Rs. 3,800 - 5,000 / year)</b>", tbl_cell_bold)
        ]
    ]

    comp_table = Table(comp_data, colWidths=[130, 196, 196])
    comp_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafc')]),
    ]))
    story.append(comp_table)
    story.append(Spacer(1, 8))

    # 5. Strategic Recommendation Box
    story.append(Paragraph("5. Which Plan is Best for You Right Now?", h1_style))
    rec_html = """
    <b>Our Professional Recommendation: Start with the Render Starter Plan ($7/mo | approx. Rs. 580/mo | Rs. 7,050/yr)</b><br/><br/>
    <b>Why this is the smartest decision for your business today:</b><br/>
    1. <b>Immediately Eliminates the Problem:</b> Solves the 15-minute sleep issue 100%. Employees and managers will experience instant punch-ins and fast page loading.<br/>
    2. <b>Zero Transition Risk:</b> There is zero code rewrite, no downtime, and no risk of database corruption or payroll discrepancies.<br/>
    3. <b>Lowest Total Cost of Ownership:</b> AWS seems cheaper on paper ($5/mo vs $7/mo), but AWS requires developer hours to manage Linux patches and firewalls. Render has zero management cost.<br/>
    4. <b>Clear Growth Upgrade:</b> When your customer base grows past 25-30 companies (over 2,000 employees), we can transition the system to AWS seamlessly in an afternoon.
    """
    rec_box = Table([[Paragraph(rec_html, callout_text)]], colWidths=[522])
    rec_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0fdf4')),
        ('BOX', (0, 0), (-1, -1), 1.5, colors.HexColor('#86efac')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(rec_box)
    story.append(Spacer(1, 6))

    # 6. Action Plan
    story.append(Paragraph("6. Simple Action Plan (Next Steps)", h1_style))
    story.append(Paragraph(
        "- <b>Step 1 (Immediate &amp; Free):</b> We have activated an automatic keep-alive ping on our server to keep the current free plan awake during office hours.<br/>"
        "- <b>Step 2 (Recommended Client Approval):</b> Approve the <b>Render Starter Plan ($7/month | approx. Rs. 580/mo)</b> to permanently eliminate cold starts, double the server memory, and deliver a smooth experience for all users.<br/>"
        "- <b>Step 3 (Future Scale):</b> Re-evaluate AWS when your customer workforce crosses 2,000 active employees.",
        body_style
    ))
    story.append(Spacer(1, 10))

    # Sign-off box
    sign_data = [
        [
            Paragraph("<b>Prepared By:</b><br/>Technical Engineering Team<br/>ARGUS Technologies", body_style),
            Paragraph("<b>Commercial Approval (Client):</b><br/><br/>________________________________________<br/>Authorized Signature &amp; Date", body_style)
        ]
    ]
    sign_table = Table(sign_data, colWidths=[261, 261])
    sign_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(sign_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    return output_path

if __name__ == '__main__':
    out_pdf = "Cloud_Hosting_Comparison_Render_vs_AWS.pdf"
    create_cloud_comparison_pdf(out_pdf)
    print(f"Generated PDF successfully: {out_pdf}")
