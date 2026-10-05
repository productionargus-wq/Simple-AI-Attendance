import os
import math
import numpy as np
import imageio
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "C:/Windows/Fonts/"
try:
    font_title = ImageFont.truetype(FONT_PATH + "segoeuib.ttf", 32)
    font_bold_28 = ImageFont.truetype(FONT_PATH + "segoeuib.ttf", 28)
    font_sub = ImageFont.truetype(FONT_PATH + "segoeui.ttf", 18)
    font_bold_20 = ImageFont.truetype(FONT_PATH + "segoeuib.ttf", 20)
    font_bold_16 = ImageFont.truetype(FONT_PATH + "segoeuib.ttf", 16)
    font_bold_14 = ImageFont.truetype(FONT_PATH + "segoeuib.ttf", 14)
    font_bold_12 = ImageFont.truetype(FONT_PATH + "segoeuib.ttf", 12)
    font_bold_10 = ImageFont.truetype(FONT_PATH + "segoeuib.ttf", 10)
    font_reg_16 = ImageFont.truetype(FONT_PATH + "segoeui.ttf", 16)
    font_reg_14 = ImageFont.truetype(FONT_PATH + "segoeui.ttf", 14)
    font_reg_12 = ImageFont.truetype(FONT_PATH + "segoeui.ttf", 12)
    font_reg_10 = ImageFont.truetype(FONT_PATH + "segoeui.ttf", 10)
except Exception:
    font_title = font_bold_28 = font_sub = font_bold_20 = font_bold_16 = font_bold_14 = font_bold_12 = font_bold_10 = ImageFont.load_default()
    font_reg_16 = font_reg_14 = font_reg_12 = font_reg_10 = ImageFont.load_default()

WIDTH = 1280
HEIGHT = 720
FPS = 24
TOTAL_FRAMES = 240  # 10.0 seconds

# Colors
C_DARK_BG = (15, 23, 42)
C_SIDEBAR = (17, 24, 39)
C_MAIN_BG = (248, 250, 252)
C_CARD_BG = (255, 255, 255)
C_BORDER = (226, 232, 240)
C_PRIMARY = (2, 132, 199)
C_PRIMARY_HOVER = (3, 105, 161)
C_GREEN = (22, 163, 74)
C_GREEN_BG = (220, 252, 231)
C_AMBER = (217, 119, 6)
C_AMBER_BG = (254, 243, 199)
C_BLUE_BG = (224, 242, 254)
C_TEXT_DARK = (15, 23, 42)
C_TEXT_MUTED = (100, 116, 139)
C_TEXT_LIGHT = (148, 163, 184)
C_HEADER_ROW = (241, 245, 249)

def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)

def draw_cursor(draw, x, y, clicking=False):
    x, y = int(x), int(y)
    pts = [
        (x, y),
        (x, y + 22),
        (x + 6, y + 17),
        (x + 11, y + 26),
        (x + 15, y + 24),
        (x + 9, y + 15),
        (x + 17, y + 15)
    ]
    shadow_pts = [(px + 2, py + 2) for px, py in pts]
    draw.polygon(shadow_pts, fill=(0, 0, 0))
    draw.polygon(pts, fill=(255, 255, 255), outline=(15, 23, 42))
    if clicking:
        draw.ellipse([x - 14, y - 14, x + 14, y + 14], outline=C_PRIMARY, width=3)

def draw_shell(img, active_idx):
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=C_MAIN_BG)
    
    # Top Navbar
    draw.rectangle([0, 0, WIDTH, 54], fill=C_CARD_BG, outline=C_BORDER)
    draw.polygon([(26, 18), (40, 40), (12, 40)], fill=C_PRIMARY)
    draw.text((48, 18), "ARGUS ATTENDANCE", font=font_bold_16, fill=C_TEXT_DARK)
    draw.text((540, 18), "HEXA TECHNOLOGIES", font=font_bold_16, fill=C_TEXT_DARK)
    
    # User Badge
    draw.rounded_rectangle([1120, 10, 1260, 44], radius=17, fill=C_MAIN_BG, outline=C_BORDER)
    draw.ellipse([1124, 14, 1150, 40], fill=C_PRIMARY)
    draw.text((1133, 18), "H", font=font_bold_14, fill=C_CARD_BG)
    draw.text((1158, 20), "Hexa Tech", font=font_bold_12, fill=C_TEXT_DARK)
    
    # Left Sidebar
    side_w = 210
    draw.rectangle([0, 54, side_w, HEIGHT], fill=C_SIDEBAR)
    
    modules = [
        ("Dashboard", 0),
        ("Employee Details", 1),
        ("Live Report", 2),
        ("Attendance Report", 3),
        ("Manual Entry", 4),
        ("Payment Entry", 5),
        ("Payslip Preview", 6),
        ("Salary Report", 7),
        ("Company Profile", 8),
        ("Support & Help", 9)
    ]
    
    y = 68
    for name, idx in modules:
        if idx == active_idx:
            draw.rounded_rectangle([10, y, side_w - 10, y + 34], radius=6, fill=C_PRIMARY)
            draw.text((32, y + 8), name, font=font_bold_14, fill=C_CARD_BG)
        else:
            draw.text((32, y + 8), name, font=font_reg_14, fill=C_TEXT_LIGHT)
        y += 40
        
    return draw

def draw_bottom_step_banner(draw, step_num, step_text):
    bx1, by1, bx2, by2 = 230, 646, 1260, 702
    draw.rounded_rectangle([bx1, by1, bx2, by2], radius=10, fill=C_DARK_BG)
    draw.rounded_rectangle([bx1 + 14, by1 + 10, bx1 + 120, by2 - 10], radius=18, fill=C_PRIMARY)
    draw.text((bx1 + 24, by1 + 16), f"STEP {step_num} OF 3", font=font_bold_12, fill=C_CARD_BG)
    draw.text((bx1 + 135, by1 + 17), step_text, font=font_bold_16, fill=C_CARD_BG)

def draw_intro_card(img, chapter_num, title, subtitle):
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=C_DARK_BG)
    draw.polygon([(620, 210), (660, 270), (580, 270)], fill=C_PRIMARY)
    draw.text((540, 285), "ARGUS ATTENDANCE TUTORIAL", font=font_bold_14, fill=C_PRIMARY)
    ch_text = f"CHAPTER {chapter_num}: {title.upper()}"
    bbox = font_title.getbbox(ch_text)
    tw = bbox[2] - bbox[0]
    draw.text(((WIDTH - tw) // 2, 320), ch_text, font=font_title, fill=C_CARD_BG)
    sbox = font_sub.getbbox(subtitle)
    sw = sbox[2] - sbox[0]
    draw.text(((WIDTH - sw) // 2, 380), subtitle, font=font_sub, fill=C_TEXT_LIGHT)
    draw.rounded_rectangle([440, 460, 840, 466], radius=3, fill=(30, 41, 59))
    draw.rounded_rectangle([440, 460, 680, 466], radius=3, fill=C_PRIMARY)

def draw_outro_card(img, chapter_num, title, bullets):
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, WIDTH, HEIGHT], fill=C_DARK_BG)
    draw.ellipse([610, 160, 670, 220], fill=C_GREEN)
    draw.text((630, 172), "✓", font=font_title, fill=C_CARD_BG)
    ch_text = f"Chapter {chapter_num} Complete: {title}"
    bbox = font_bold_20.getbbox(ch_text)
    tw = bbox[2] - bbox[0]
    draw.text(((WIDTH - tw) // 2, 240), ch_text, font=font_bold_20, fill=C_CARD_BG)
    draw.text((490, 290), "WHAT YOU LEARNED IN THIS MODULE:", font=font_bold_12, fill=C_PRIMARY)
    y = 320
    for b in bullets[:3]:
        draw.ellipse([490, y + 4, 498, y + 12], fill=C_PRIMARY)
        draw.text((512, y), b, font=font_reg_14, fill=C_CARD_BG)
        y += 32
    draw.text((490, 440), "Ready for the next lesson in ARGUS Attendance Support Center.", font=font_reg_12, fill=C_TEXT_LIGHT)

# ==============================================================================
# CHAPTER 1: EMPLOYEE DETAILS
# ==============================================================================
def render_chapter_1(frame_idx):
    img = Image.new("RGB", (WIDTH, HEIGHT), color=C_MAIN_BG)
    if frame_idx < 24:
        draw_intro_card(img, 1, "Employee Details", "Learn how to add, edit and manage employee records.")
        return img
    elif frame_idx > 218:
        draw_outro_card(img, 1, "Employee Details", [
            "Add and register new company employees",
            "Configure department, designation & salary terms",
            "Instant profile activation for biometric attendance"
        ])
        return img
    draw = draw_shell(img, active_idx=1)
    draw.text((235, 75), "Employee Details", font=font_bold_20, fill=C_TEXT_DARK)
    draw.text((235, 102), "Manage employee records, designations, and biometric enrollment.", font=font_reg_12, fill=C_TEXT_MUTED)
    draw.rounded_rectangle([860, 78, 1020, 110], radius=6, fill=C_CARD_BG, outline=C_BORDER)
    draw.text((875, 87), "🔍 Search employees...", font=font_reg_12, fill=C_TEXT_MUTED)
    btn_box = [1040, 78, 1250, 110]
    draw.rounded_rectangle(btn_box, radius=6, fill=C_PRIMARY)
    draw.text((1070, 87), "+ Add Employee", font=font_bold_14, fill=C_CARD_BG)
    tx1, ty1, tx2, ty2 = 235, 126, 1250, 620
    draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_CARD_BG, outline=C_BORDER)
    draw.rectangle([tx1, ty1, tx2, ty1 + 36], fill=C_HEADER_ROW)
    headers = [("ID", 260), ("NAME", 340), ("DESIGNATION", 540), ("DEPARTMENT", 740), ("PHONE", 910), ("STATUS", 1060), ("ACTION", 1170)]
    for h, hx in headers:
        draw.text((hx, ty1 + 10), h, font=font_bold_12, fill=C_TEXT_MUTED)
    rows = [
        ("EMP001", "John Smith", "Senior Production Manager", "Manufacturing", "+91 98765 43210", "Active"),
        ("EMP002", "Sarah Johnson", "HR Operations Lead", "Administration", "+91 98450 11223", "Active"),
        ("EMP003", "Michael Scott", "Quality Inspector", "Quality Control", "+91 97412 88990", "Active"),
        ("EMP004", "Emily Davis", "CNC Machine Operator", "Production", "+91 96112 33445", "Active")
    ]
    if frame_idx >= 155:
        rows = [("EMP005", "Sarah Jenkins", "Operations Manager", "Logistics", "+91 91234 56789", "Active")] + rows[:3]
    ry = ty1 + 42
    for r_id, r_name, r_des, r_dept, r_ph, r_st in rows:
        draw.rectangle([tx1, ry, tx2, ry + 42], fill=C_CARD_BG, outline=C_BORDER)
        draw.text((260, ry + 12), r_id, font=font_bold_12, fill=C_PRIMARY)
        draw.text((340, ry + 12), r_name, font=font_bold_14, fill=C_TEXT_DARK)
        draw.text((540, ry + 12), r_des, font=font_reg_12, fill=C_TEXT_MUTED)
        draw.text((740, ry + 12), r_dept, font=font_reg_12, fill=C_TEXT_DARK)
        draw.text((910, ry + 12), r_ph, font=font_reg_12, fill=C_TEXT_MUTED)
        draw.rounded_rectangle([1060, ry + 8, 1120, ry + 30], radius=11, fill=C_GREEN_BG)
        draw.text((1074, ry + 11), r_st, font=font_bold_10, fill=C_GREEN)
        draw.text((1170, ry + 12), "✏️ Edit", font=font_bold_12, fill=C_PRIMARY)
        ry += 44
    if frame_idx < 90:
        t = smoothstep((frame_idx - 24) / (90 - 24))
        cur_x = 650 + (1130 - 650) * t
        cur_y = 450 + (95 - 450) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 82))
        draw_bottom_step_banner(draw, 1, "Click '+ Add Employee' to open the registration form")
    elif frame_idx < 155:
        mx1, my1, mx2, my2 = 440, 130, 940, 560
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 100))
        img.paste(Image.alpha_composite(Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0)), overlay), (0, 0), overlay)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([mx1, my1, mx2, my2], radius=12, fill=C_CARD_BG, outline=C_BORDER)
        draw.text((mx1 + 25, my1 + 20), "Add New Employee", font=font_bold_16, fill=C_TEXT_DARK)
        draw.text((mx2 - 35, my1 + 18), "✕", font=font_bold_16, fill=C_TEXT_MUTED)
        draw.line([mx1, my1 + 56, mx2, my1 + 56], fill=C_BORDER)
        fields = [
            ("Employee ID", "EMP005"),
            ("Full Name", "Sarah Jenkins"),
            ("Designation", "Operations Manager"),
            ("Department", "Logistics"),
            ("Base Salary (Monthly)", "₹ 45,000.00")
        ]
        fy = my1 + 72
        for lbl, val in fields:
            draw.text((mx1 + 25, fy), lbl, font=font_bold_12, fill=C_TEXT_MUTED)
            draw.rounded_rectangle([mx1 + 25, fy + 20, mx2 - 25, fy + 52], radius=6, fill=C_MAIN_BG, outline=C_BORDER)
            draw.text((mx1 + 35, fy + 28), val, font=font_bold_14, fill=C_TEXT_DARK)
            fy += 62
        sbtn_box = [mx2 - 160, my2 - 50, mx2 - 25, my2 - 16]
        draw.rounded_rectangle(sbtn_box, radius=6, fill=C_PRIMARY)
        draw.text((mx2 - 135, my2 - 42), "Save Details", font=font_bold_14, fill=C_CARD_BG)
        t = smoothstep((frame_idx - 90) / (155 - 90))
        cur_x = 550 + (mx2 - 90 - 550) * t
        cur_y = 250 + (my2 - 32 - 250) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 148))
        draw_bottom_step_banner(draw, 2, "Enter employee details, designation, department & salary")
    else:
        draw_bottom_step_banner(draw, 3, "Employee registered! Immediately activated for biometric attendance")
        tx1, ty1, tx2, ty2 = 820, 70, 1245, 118
        draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_GREEN_BG, outline=C_GREEN)
        draw.text((tx1 + 18, ty1 + 14), "✓ Success: Employee 'Sarah Jenkins' registered!", font=font_bold_14, fill=C_GREEN)
        draw_cursor(draw, 1090, 185, clicking=False)
    return img

# ==============================================================================
# CHAPTER 2: LIVE REPORT
# ==============================================================================
def render_chapter_2(frame_idx):
    img = Image.new("RGB", (WIDTH, HEIGHT), color=C_MAIN_BG)
    if frame_idx < 24:
        draw_intro_card(img, 2, "Live Report", "Real-time punch monitoring, biometric facial match, and shift metrics.")
        return img
    elif frame_idx > 218:
        draw_outro_card(img, 2, "Live Report", [
            "Monitor live biometric attendance as it happens",
            "Filter punches by department and active shifts",
            "Instant facial match verification & geofence audit"
        ])
        return img
    draw = draw_shell(img, active_idx=2)
    draw.text((235, 75), "Live Attendance Feed", font=font_bold_20, fill=C_TEXT_DARK)
    draw.text((235, 102), "Real-time employee check-in logs streamed from active biometric terminals.", font=font_reg_12, fill=C_TEXT_MUTED)
    
    # 3 Metric Cards
    m_data = [
        ("TOTAL PRESENT", "42", C_GREEN, C_GREEN_BG),
        ("LATE ARRIVALS", "3", C_AMBER, C_AMBER_BG),
        ("ON DUTY NOW", "39", C_PRIMARY, C_BLUE_BG)
    ]
    mx = 235
    for m_lbl, m_val, col, bg_col in m_data:
        draw.rounded_rectangle([mx, 126, mx + 180, 196], radius=8, fill=C_CARD_BG, outline=C_BORDER)
        draw.text((mx + 16, 138), m_lbl, font=font_bold_10, fill=C_TEXT_MUTED)
        draw.text((mx + 16, 156), m_val, font=font_bold_28, fill=col)
        mx += 200

    # Filter selector
    draw.rounded_rectangle([860, 140, 1040, 180], radius=6, fill=C_CARD_BG, outline=C_BORDER)
    filter_val = "Dept: Engineering" if frame_idx >= 90 else "Dept: All"
    draw.text((875, 152), f"▼ {filter_val}", font=font_bold_12, fill=C_TEXT_DARK)
    
    # Live Badge
    draw.rounded_rectangle([1060, 140, 1250, 180], radius=6, fill=C_GREEN_BG, outline=C_GREEN)
    draw.text((1075, 152), "● LIVE SYNC ACTIVE", font=font_bold_12, fill=C_GREEN)
    
    # Live Feed Table
    tx1, ty1, tx2, ty2 = 235, 215, 1250, 620
    draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_CARD_BG, outline=C_BORDER)
    draw.rectangle([tx1, ty1, tx2, ty1 + 36], fill=C_HEADER_ROW)
    headers = [("TIME", 260), ("EMPLOYEE", 370), ("DEPARTMENT", 590), ("TERMINAL / DEVICE", 770), ("VERIFICATION", 980), ("STATUS", 1140)]
    for h, hx in headers:
        draw.text((hx, ty1 + 10), h, font=font_bold_12, fill=C_TEXT_MUTED)
        
    rows = [
        ("09:14 AM", "David Miller", "Engineering", "Face Terminal #01 (Lobby)", "100% Face Match", "On Time"),
        ("09:11 AM", "Sarah Johnson", "Administration", "Mobile GPS Geofence", "Verified Geofence", "On Time"),
        ("09:05 AM", "Michael Scott", "Quality Control", "Face Terminal #02 (Floor)", "99.8% Face Match", "On Time"),
        ("08:58 AM", "John Smith", "Manufacturing", "Face Terminal #01 (Lobby)", "100% Face Match", "On Time")
    ]
    if frame_idx >= 150:
        rows = [("09:18 AM", "Alex Rivera", "Engineering", "Face Terminal #01 (Lobby)", "100% Face Match", "On Time")] + rows[:3]
        
    ry = ty1 + 42
    for r_tm, r_nm, r_dp, r_dev, r_vr, r_st in rows:
        draw.rectangle([tx1, ry, tx2, ry + 42], fill=C_CARD_BG, outline=C_BORDER)
        draw.text((260, ry + 12), r_tm, font=font_bold_12, fill=C_PRIMARY)
        draw.text((370, ry + 12), r_nm, font=font_bold_14, fill=C_TEXT_DARK)
        draw.text((590, ry + 12), r_dp, font=font_reg_12, fill=C_TEXT_MUTED)
        draw.text((770, ry + 12), r_dev, font=font_reg_12, fill=C_TEXT_DARK)
        draw.text((980, ry + 12), r_vr, font=font_bold_10, fill=C_GREEN)
        draw.rounded_rectangle([1140, ry + 8, 1220, ry + 30], radius=11, fill=C_GREEN_BG)
        draw.text((1154, ry + 11), r_st, font=font_bold_10, fill=C_GREEN)
        ry += 44
        
    if frame_idx < 90:
        t = smoothstep((frame_idx - 24) / (90 - 24))
        cur_x = 550 + (950 - 550) * t
        cur_y = 350 + (160 - 350) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 80))
        draw_bottom_step_banner(draw, 1, "Filter real-time attendance stream by department or work shift")
    elif frame_idx < 155:
        t = smoothstep((frame_idx - 90) / (155 - 90))
        cur_x = 950 + (500 - 950) * t
        cur_y = 160 + (260 - 160) * t
        draw_cursor(draw, cur_x, cur_y, clicking=False)
        draw_bottom_step_banner(draw, 2, "Automatic live sync detects new facial punches instantly")
    else:
        draw_bottom_step_banner(draw, 3, "New punch verified! Alex Rivera registered at 09:18 AM")
        draw_cursor(draw, 420, 260, clicking=False)
    return img

# ==============================================================================
# CHAPTER 3: ATTENDANCE REPORT
# ==============================================================================
def render_chapter_3(frame_idx):
    img = Image.new("RGB", (WIDTH, HEIGHT), color=C_MAIN_BG)
    if frame_idx < 24:
        draw_intro_card(img, 3, "Attendance Report", "Generate, audit, and export multi-day attendance registers.")
        return img
    elif frame_idx > 218:
        draw_outro_card(img, 3, "Attendance Report", [
            "Select custom date ranges & shifts",
            "Audit daily presence, late hours & overtime",
            "Export polished reports to Excel and PDF"
        ])
        return img
    draw = draw_shell(img, active_idx=3)
    draw.text((235, 75), "Attendance Reports", font=font_bold_20, fill=C_TEXT_DARK)
    draw.text((235, 102), "Audit work hours, employee presence compliance, and export statements.", font=font_reg_12, fill=C_TEXT_MUTED)
    
    # Filter Bar
    draw.rounded_rectangle([235, 126, 420, 168], radius=6, fill=C_CARD_BG, outline=C_BORDER)
    draw.text((248, 140), "📅 01/10/2026 - 05/10/2026", font=font_bold_12, fill=C_TEXT_DARK)
    
    draw.rounded_rectangle([435, 126, 610, 168], radius=6, fill=C_CARD_BG, outline=C_BORDER)
    draw.text((450, 140), "Shift: General (9h)", font=font_reg_12, fill=C_TEXT_DARK)
    
    draw.rounded_rectangle([625, 126, 750, 168], radius=6, fill=C_PRIMARY)
    draw.text((650, 140), "Apply Filter", font=font_bold_12, fill=C_CARD_BG)
    
    # Export Button
    draw.rounded_rectangle([1060, 126, 1250, 168], radius=6, fill=C_GREEN)
    draw.text((1085, 140), "📥 Export Excel / PDF", font=font_bold_12, fill=C_CARD_BG)
    
    # Table
    tx1, ty1, tx2, ty2 = 235, 190, 1250, 620
    draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_CARD_BG, outline=C_BORDER)
    draw.rectangle([tx1, ty1, tx2, ty1 + 36], fill=C_HEADER_ROW)
    headers = [("DATE", 260), ("EMPLOYEE", 380), ("IN TIME", 580), ("OUT TIME", 720), ("HOURS", 860), ("SALARY", 990), ("STATUS", 1120)]
    for h, hx in headers:
        draw.text((hx, ty1 + 10), h, font=font_bold_12, fill=C_TEXT_MUTED)
        
    rows = [
        ("05/10/2026", "John Smith", "09:00 AM", "06:00 PM", "9.0 hrs", "₹ 1,230.00", "Present"),
        ("05/10/2026", "Sarah Johnson", "09:30 AM", "06:30 PM", "9.0 hrs", "₹ 1,150.00", "Present"),
        ("05/10/2026", "David Miller", "09:14 AM", "06:14 PM", "9.0 hrs", "₹ 1,080.00", "Present"),
        ("05/10/2026", "Michael Scott", "10:15 AM", "06:30 PM", "8.2 hrs", "₹ 980.00", "Half Day")
    ]
    ry = ty1 + 42
    for r_dt, r_nm, r_in, r_ot, r_hr, r_sl, r_st in rows:
        draw.rectangle([tx1, ry, tx2, ry + 42], fill=C_CARD_BG, outline=C_BORDER)
        draw.text((260, ry + 12), r_dt, font=font_bold_12, fill=C_TEXT_DARK)
        draw.text((380, ry + 12), r_nm, font=font_bold_14, fill=C_TEXT_DARK)
        draw.text((580, ry + 12), r_in, font=font_reg_12, fill=C_GREEN)
        draw.text((720, ry + 12), r_ot, font=font_reg_12, fill=C_PRIMARY)
        draw.text((860, ry + 12), r_hr, font=font_bold_12, fill=C_TEXT_DARK)
        draw.text((990, ry + 12), r_sl, font=font_bold_12, fill=C_TEXT_DARK)
        st_col = C_GREEN if r_st == "Present" else C_AMBER
        st_bg = C_GREEN_BG if r_st == "Present" else C_AMBER_BG
        draw.rounded_rectangle([1120, ry + 8, 1200, ry + 30], radius=11, fill=st_bg)
        draw.text((1135, ry + 11), r_st, font=font_bold_10, fill=st_col)
        ry += 44
        
    if frame_idx < 90:
        t = smoothstep((frame_idx - 24) / (90 - 24))
        cur_x = 400 + (685 - 400) * t
        cur_y = 300 + (147 - 300) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 80))
        draw_bottom_step_banner(draw, 1, "Select date range and click 'Apply Filter' to query records")
    elif frame_idx < 155:
        t = smoothstep((frame_idx - 90) / (155 - 90))
        cur_x = 685 + (1150 - 685) * t
        cur_y = 147 + (147 - 147) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 148))
        draw_bottom_step_banner(draw, 2, "Click 'Export Excel / PDF' to generate the official attendance sheet")
    else:
        draw_bottom_step_banner(draw, 3, "Report generated and downloaded successfully in Excel & PDF formats")
        tx1, ty1, tx2, ty2 = 780, 70, 1245, 118
        draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_GREEN_BG, outline=C_GREEN)
        draw.text((tx1 + 18, ty1 + 14), "✓ Downloaded: Attendance_Report_Oct2026.xlsx", font=font_bold_14, fill=C_GREEN)
    return img

# ==============================================================================
# CHAPTER 4: MANUAL ENTRY
# ==============================================================================
def render_chapter_4(frame_idx):
    img = Image.new("RGB", (WIDTH, HEIGHT), color=C_MAIN_BG)
    if frame_idx < 24:
        draw_intro_card(img, 4, "Manual Entry", "Record or adjust attendance punches with justification audit.")
        return img
    elif frame_idx > 218:
        draw_outro_card(img, 4, "Manual Entry", [
            "Adjust missed punches or off-site visits",
            "Automatic working hours & salary calculation",
            "Maintain strict audit logging with manager reasons"
        ])
        return img
    draw = draw_shell(img, active_idx=4)
    draw.text((235, 75), "Manual Attendance Entry", font=font_bold_20, fill=C_TEXT_DARK)
    draw.text((235, 102), "Submit manual in/out adjustments for missing biometric punches with justification.", font=font_reg_12, fill=C_TEXT_MUTED)
    
    # Form Card in center
    cx1, cy1, cx2, cy2 = 235, 126, 1250, 620
    draw.rounded_rectangle([cx1, cy1, cx2, cy2], radius=8, fill=C_CARD_BG, outline=C_BORDER)
    draw.text((260, 145), "New Attendance Correction Record", font=font_bold_16, fill=C_TEXT_DARK)
    draw.line([cx1, 180, cx2, 180], fill=C_BORDER)
    
    # Inputs grid
    grid_fields = [
        ("Employee", "EMP004 - Michael Scott", 260, 200, 700),
        ("Date", "04/10/2026", 740, 200, 1210),
        ("In Time", "09:30 AM", 260, 275, 700),
        ("Out Time", "06:30 PM (9.0 Hours)", 740, 275, 1210),
        ("Calculated Working Salary", "₹ 900.00", 260, 350, 700),
        ("Justification Reason", "Biometric Terminal Sync Delay / On-site Visit", 740, 350, 1210)
    ]
    for lbl, val, gx1, gy1, gx2 in grid_fields:
        draw.text((gx1, gy1), lbl, font=font_bold_12, fill=C_TEXT_MUTED)
        draw.rounded_rectangle([gx1, gy1 + 22, gx2, gy1 + 58], radius=6, fill=C_MAIN_BG, outline=C_BORDER)
        draw.text((gx1 + 14, gy1 + 33), val, font=font_bold_14, fill=C_TEXT_DARK)
        
    # Save Button
    sbtn = [1050, 440, 1210, 485]
    draw.rounded_rectangle(sbtn, radius=6, fill=C_PRIMARY)
    draw.text((1080, 453), "Save Entry", font=font_bold_14, fill=C_CARD_BG)
    
    # Audit log mini table below
    draw.text((260, 440), "Recent Manual Corrections Audit", font=font_bold_14, fill=C_TEXT_MUTED)
    draw.rounded_rectangle([260, 470, 1000, 580], radius=6, fill=C_MAIN_BG, outline=C_BORDER)
    draw.text((280, 490), "• 03/10/2026: EMP002 - Sarah Johnson (9.0 hrs) - Approved by Admin", font=font_reg_12, fill=C_TEXT_DARK)
    draw.text((280, 520), "• 02/10/2026: EMP001 - John Smith (8.5 hrs) - Approved by Admin", font=font_reg_12, fill=C_TEXT_DARK)
    if frame_idx >= 155:
        draw.text((280, 550), "• 04/10/2026: EMP004 - Michael Scott (9.0 hrs) - ✓ Approved & Synced", font=font_bold_12, fill=C_GREEN)
        
    if frame_idx < 90:
        t = smoothstep((frame_idx - 24) / (90 - 24))
        cur_x = 400 + (500 - 400) * t
        cur_y = 500 + (380 - 500) * t
        draw_cursor(draw, cur_x, cur_y, clicking=False)
        draw_bottom_step_banner(draw, 1, "Enter employee, date, corrected punch hours, and mandatory reason")
    elif frame_idx < 155:
        t = smoothstep((frame_idx - 90) / (155 - 90))
        cur_x = 500 + (1130 - 500) * t
        cur_y = 380 + (462 - 380) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 148))
        draw_bottom_step_banner(draw, 2, "Click 'Save Entry' to commit adjustment into payroll calculation")
    else:
        draw_bottom_step_banner(draw, 3, "Manual entry committed and audited successfully in payroll register")
        tx1, ty1, tx2, ty2 = 780, 70, 1245, 118
        draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_GREEN_BG, outline=C_GREEN)
        draw.text((tx1 + 18, ty1 + 14), "✓ Success: Manual attendance entry approved!", font=font_bold_14, fill=C_GREEN)
    return img

# ==============================================================================
# CHAPTER 5: PAYMENT ENTRY
# ==============================================================================
def render_chapter_5(frame_idx):
    img = Image.new("RGB", (WIDTH, HEIGHT), color=C_MAIN_BG)
    if frame_idx < 24:
        draw_intro_card(img, 5, "Payment Entry", "Record and manage employee advances, loans, and recoveries.")
        return img
    elif frame_idx > 218:
        draw_outro_card(img, 5, "Payment Entry", [
            "Issue salary advance disbursements",
            "Configure monthly installment deductions",
            "Automatic payroll deduction integration"
        ])
        return img
    draw = draw_shell(img, active_idx=5)
    draw.text((235, 75), "Payment & Advance Entry", font=font_bold_20, fill=C_TEXT_DARK)
    draw.text((235, 102), "Manage employee loans, advance disbursements, and payroll settlement recovery.", font=font_reg_12, fill=C_TEXT_MUTED)
    
    # 3 Summary Cards
    mx = 235
    for lbl, val, col in [("TOTAL ACTIVE ADVANCE", "₹ 45,000", C_PRIMARY), ("OPEN RECOVERIES", "4 Employees", C_AMBER), ("SETTLED THIS MONTH", "₹ 12,000", C_GREEN)]:
        draw.rounded_rectangle([mx, 126, mx + 200, 196], radius=8, fill=C_CARD_BG, outline=C_BORDER)
        draw.text((mx + 16, 138), lbl, font=font_bold_10, fill=C_TEXT_MUTED)
        draw.text((mx + 16, 158), val, font=font_bold_20, fill=col)
        mx += 220
        
    btn_box = [1040, 140, 1250, 180]
    draw.rounded_rectangle(btn_box, radius=6, fill=C_PRIMARY)
    draw.text((1068, 152), "+ Add Advance", font=font_bold_14, fill=C_CARD_BG)
    
    # Table
    tx1, ty1, tx2, ty2 = 235, 215, 1250, 620
    draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_CARD_BG, outline=C_BORDER)
    draw.rectangle([tx1, ty1, tx2, ty1 + 36], fill=C_HEADER_ROW)
    headers = [("DATE", 260), ("EMPLOYEE", 390), ("ADVANCE AMOUNT", 590), ("INSTALLMENT", 790), ("REMAINING", 970), ("STATUS", 1120)]
    for h, hx in headers:
        draw.text((hx, ty1 + 10), h, font=font_bold_12, fill=C_TEXT_MUTED)
        
    rows = [
        ("01/10/2026", "Michael Scott", "₹ 15,000.00", "₹ 5,000 / mo", "₹ 10,000.00", "Active"),
        ("28/09/2026", "John Smith", "₹ 10,000.00", "₹ 5,000 / mo", "₹ 0.00", "Settled"),
        ("15/09/2026", "David Miller", "₹ 20,000.00", "₹ 10,000 / mo", "₹ 10,000.00", "Active")
    ]
    if frame_idx >= 155:
        rows = [("05/10/2026", "Emily Davis", "₹ 10,000.00", "₹ 5,000 / mo", "₹ 10,000.00", "Active")] + rows[:2]
        
    ry = ty1 + 42
    for r_dt, r_nm, r_am, r_in, r_rm, r_st in rows:
        draw.rectangle([tx1, ry, tx2, ry + 42], fill=C_CARD_BG, outline=C_BORDER)
        draw.text((260, ry + 12), r_dt, font=font_bold_12, fill=C_TEXT_DARK)
        draw.text((390, ry + 12), r_nm, font=font_bold_14, fill=C_TEXT_DARK)
        draw.text((590, ry + 12), r_am, font=font_bold_14, fill=C_PRIMARY)
        draw.text((790, ry + 12), r_in, font=font_reg_12, fill=C_TEXT_MUTED)
        draw.text((970, ry + 12), r_rm, font=font_bold_12, fill=C_TEXT_DARK)
        st_col = C_GREEN if r_st == "Settled" else C_AMBER
        st_bg = C_GREEN_BG if r_st == "Settled" else C_AMBER_BG
        draw.rounded_rectangle([1120, ry + 8, 1200, ry + 30], radius=11, fill=st_bg)
        draw.text((1135, ry + 11), r_st, font=font_bold_10, fill=st_col)
        ry += 44
        
    if frame_idx < 90:
        t = smoothstep((frame_idx - 24) / (90 - 24))
        cur_x = 700 + (1145 - 700) * t
        cur_y = 350 + (160 - 350) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 80))
        draw_bottom_step_banner(draw, 1, "Click '+ Add Advance' to disburse a new salary advance")
    elif frame_idx < 155:
        mx1, my1, mx2, my2 = 440, 130, 940, 560
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 100))
        img.paste(Image.alpha_composite(Image.new("RGBA", (WIDTH, HEIGHT), (0,0,0,0)), overlay), (0, 0), overlay)
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([mx1, my1, mx2, my2], radius=12, fill=C_CARD_BG, outline=C_BORDER)
        draw.text((mx1 + 25, my1 + 20), "New Advance Disbursement", font=font_bold_16, fill=C_TEXT_DARK)
        draw.line([mx1, my1 + 56, mx2, my1 + 56], fill=C_BORDER)
        adv_fields = [
            ("Employee", "EMP004 - Emily Davis"),
            ("Advance Amount", "₹ 10,000.00"),
            ("Monthly Installment", "₹ 5,000.00 / month (2 Months)"),
            ("Disbursement Mode", "Bank Direct Transfer (#TXN88291)")
        ]
        fy = my1 + 75
        for lbl, val in adv_fields:
            draw.text((mx1 + 25, fy), lbl, font=font_bold_12, fill=C_TEXT_MUTED)
            draw.rounded_rectangle([mx1 + 25, fy + 20, mx2 - 25, fy + 54], radius=6, fill=C_MAIN_BG, outline=C_BORDER)
            draw.text((mx1 + 35, fy + 29), val, font=font_bold_14, fill=C_TEXT_DARK)
            fy += 68
        sbtn_box = [mx2 - 190, my2 - 50, mx2 - 25, my2 - 16]
        draw.rounded_rectangle(sbtn_box, radius=6, fill=C_PRIMARY)
        draw.text((mx2 - 170, my2 - 42), "Disburse Advance", font=font_bold_14, fill=C_CARD_BG)
        t = smoothstep((frame_idx - 90) / (155 - 90))
        cur_x = 550 + (mx2 - 110 - 550) * t
        cur_y = 250 + (my2 - 32 - 250) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 148))
        draw_bottom_step_banner(draw, 2, "Enter advance amount and choose monthly installment recovery terms")
    else:
        draw_bottom_step_banner(draw, 3, "Advance disbursed! Deductions will be automatically linked to payslips")
        tx1, ty1, tx2, ty2 = 780, 70, 1245, 118
        draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_GREEN_BG, outline=C_GREEN)
        draw.text((tx1 + 18, ty1 + 14), "✓ Success: Advance ₹10,000 issued to Emily Davis!", font=font_bold_14, fill=C_GREEN)
    return img

# ==============================================================================
# CHAPTER 6: PAYSLIP PREVIEW
# ==============================================================================
def render_chapter_6(frame_idx):
    img = Image.new("RGB", (WIDTH, HEIGHT), color=C_MAIN_BG)
    if frame_idx < 24:
        draw_intro_card(img, 6, "Payslip Preview", "Generate pixel-perfect monthly payslips with earnings & deduction breakdown.")
        return img
    elif frame_idx > 218:
        draw_outro_card(img, 6, "Payslip Preview", [
            "Dynamic working salary calculation",
            "Automatic deduction of advance installments",
            "Official payslip PDF generation and instant download"
        ])
        return img
    draw = draw_shell(img, active_idx=6)
    draw.text((235, 75), "Monthly Payslip Preview", font=font_bold_20, fill=C_TEXT_DARK)
    draw.text((235, 102), "Inspect earnings, statutory deductions, and generate official employee payslip PDFs.", font=font_reg_12, fill=C_TEXT_MUTED)
    
    # Filter Row
    draw.rounded_rectangle([235, 126, 480, 168], radius=6, fill=C_CARD_BG, outline=C_BORDER)
    draw.text((248, 140), "👤 EMP001 - John Smith", font=font_bold_12, fill=C_TEXT_DARK)
    draw.rounded_rectangle([495, 126, 680, 168], radius=6, fill=C_CARD_BG, outline=C_BORDER)
    draw.text((510, 140), "📅 September 2026", font=font_bold_12, fill=C_TEXT_DARK)
    
    # Download PDF Button
    pdf_btn = [1020, 126, 1250, 168]
    draw.rounded_rectangle(pdf_btn, radius=6, fill=C_PRIMARY)
    draw.text((1045, 140), "📄 Download Payslip PDF", font=font_bold_12, fill=C_CARD_BG)
    
    # Payslip Card Preview
    px1, py1, px2, py2 = 235, 190, 1250, 620
    draw.rounded_rectangle([px1, py1, px2, py2], radius=8, fill=C_CARD_BG, outline=C_BORDER)
    
    # Header
    draw.text((260, 210), "HEXA TECHNOLOGIES - SALARY SLIP FOR SEPTEMBER 2026", font=font_bold_16, fill=C_TEXT_DARK)
    draw.text((260, 235), "Employee: John Smith (EMP001) | Designation: Senior Production Manager", font=font_reg_12, fill=C_TEXT_MUTED)
    draw.line([px1, 260, px2, 260], fill=C_BORDER)
    
    # 2 Column Breakdown (Earnings vs Deductions)
    col_w = (px2 - px1 - 60) // 2
    # Left: Earnings
    draw.rounded_rectangle([px1 + 20, 275, px1 + 20 + col_w, 530], radius=6, fill=C_MAIN_BG, outline=C_BORDER)
    draw.text((px1 + 35, 290), "EARNINGS BREAKDOWN", font=font_bold_14, fill=C_GREEN)
    earnings = [("Basic Working Salary (26 Days)", "₹ 32,000.00"), ("House Rent Allowance (HRA)", "₹ 6,400.00"), ("Special Allowance", "₹ 3,500.00"), ("Performance Incentive", "₹ 2,000.00")]
    ey = 325
    for en, ea in earnings:
        draw.text((px1 + 35, ey), en, font=font_reg_12, fill=C_TEXT_DARK)
        draw.text((px1 + col_w - 90, ey), ea, font=font_bold_12, fill=C_TEXT_DARK)
        ey += 35
    draw.line([px1 + 30, 480, px1 + col_w + 10, 480], fill=C_BORDER)
    draw.text((px1 + 35, 495), "TOTAL GROSS EARNINGS", font=font_bold_14, fill=C_TEXT_DARK)
    draw.text((px1 + col_w - 90, 495), "₹ 43,900.00", font=font_bold_14, fill=C_GREEN)
    
    # Right: Deductions
    rx1 = px1 + 40 + col_w
    draw.rounded_rectangle([rx1, 275, rx1 + col_w, 530], radius=6, fill=C_MAIN_BG, outline=C_BORDER)
    draw.text((rx1 + 15, 290), "DEDUCTIONS BREAKDOWN", font=font_bold_14, fill=C_AMBER)
    deductions = [("Provident Fund (PF)", "₹ 1,800.00"), ("Professional Tax (PT)", "₹ 200.00"), ("Advance Salary Recovery (Inst 1/2)", "₹ 3,000.00")]
    dy = 325
    for dn, da in deductions:
        draw.text((rx1 + 15, dy), dn, font=font_reg_12, fill=C_TEXT_DARK)
        draw.text((rx1 + col_w - 90, dy), da, font=font_bold_12, fill=C_TEXT_DARK)
        dy += 35
    draw.line([rx1 + 10, 480, rx1 + col_w - 10, 480], fill=C_BORDER)
    draw.text((rx1 + 15, 495), "TOTAL DEDUCTIONS", font=font_bold_14, fill=C_TEXT_DARK)
    draw.text((rx1 + col_w - 90, 495), "₹ 5,000.00", font=font_bold_14, fill=C_AMBER)
    
    # Net Pay Banner at bottom
    draw.rounded_rectangle([px1 + 20, 545, px2 - 20, 600], radius=6, fill=C_DARK_BG)
    draw.text((px1 + 40, 563), "NET PAYABLE SALARY:", font=font_bold_14, fill=C_TEXT_LIGHT)
    draw.text((px1 + 240, 558), "₹ 38,900.00", font=font_bold_20, fill=C_GREEN)
    draw.text((px1 + 420, 565), "(Thirty-Eight Thousand Nine Hundred Rupees Only)", font=font_reg_12, fill=C_TEXT_LIGHT)
    
    if frame_idx < 90:
        t = smoothstep((frame_idx - 24) / (90 - 24))
        cur_x = 500 + (350 - 500) * t
        cur_y = 500 + (350 - 500) * t
        draw_cursor(draw, cur_x, cur_y, clicking=False)
        draw_bottom_step_banner(draw, 1, "Select employee and salary month to inspect calculated payslip")
    elif frame_idx < 155:
        t = smoothstep((frame_idx - 90) / (155 - 90))
        cur_x = 350 + (1135 - 350) * t
        cur_y = 350 + (147 - 350) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 148))
        draw_bottom_step_banner(draw, 2, "Click 'Download Payslip PDF' to generate the official company document")
    else:
        draw_bottom_step_banner(draw, 3, "Payslip PDF generated with official company seal & signature layout")
        tx1, ty1, tx2, ty2 = 780, 70, 1245, 118
        draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_GREEN_BG, outline=C_GREEN)
        draw.text((tx1 + 18, ty1 + 14), "✓ Downloaded: Payslip_SEP2026_JohnSmith.pdf", font=font_bold_14, fill=C_GREEN)
    return img

# ==============================================================================
# CHAPTER 7: SALARY REPORT
# ==============================================================================
def render_chapter_7(frame_idx):
    img = Image.new("RGB", (WIDTH, HEIGHT), color=C_MAIN_BG)
    if frame_idx < 24:
        draw_intro_card(img, 7, "Salary Report", "Monthly consolidated payroll registers, bank files & bulk payslip dispatch.")
        return img
    elif frame_idx > 218:
        draw_outro_card(img, 7, "Salary Report", [
            "Company-wide payroll cost overview",
            "Direct bank transfer NEFT/RTGS CSV export",
            "Automated bulk employee payslip email dispatch"
        ])
        return img
    draw = draw_shell(img, active_idx=7)
    draw.text((235, 75), "Consolidated Salary Report", font=font_bold_20, fill=C_TEXT_DARK)
    draw.text((235, 102), "Monthly payroll register, bank transfer file, and automated email dispatch.", font=font_reg_12, fill=C_TEXT_MUTED)
    
    # 3 Summary Cards
    mx = 235
    for lbl, val in [("TOTAL PAYROLL (GROSS)", "₹ 5,40,000"), ("NET BANK PAYOUT", "₹ 4,95,000"), ("EMPLOYEES", "12 Staff")]:
        draw.rounded_rectangle([mx, 126, mx + 200, 196], radius=8, fill=C_CARD_BG, outline=C_BORDER)
        draw.text((mx + 16, 138), lbl, font=font_bold_10, fill=C_TEXT_MUTED)
        draw.text((mx + 16, 158), val, font=font_bold_20, fill=C_PRIMARY)
        mx += 220
        
    btn_csv = [920, 140, 1070, 180]
    draw.rounded_rectangle(btn_csv, radius=6, fill=C_GREEN)
    draw.text((945, 152), "📊 Bank CSV", font=font_bold_12, fill=C_CARD_BG)
    
    btn_mail = [1085, 140, 1250, 180]
    draw.rounded_rectangle(btn_mail, radius=6, fill=C_PRIMARY)
    draw.text((1100, 152), "✉️ Dispatch Emails", font=font_bold_12, fill=C_CARD_BG)
    
    # Table
    tx1, ty1, tx2, ty2 = 235, 215, 1250, 620
    draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_CARD_BG, outline=C_BORDER)
    draw.rectangle([tx1, ty1, tx2, ty1 + 36], fill=C_HEADER_ROW)
    headers = [("EMPLOYEE", 260), ("BANK ACCOUNT", 430), ("GROSS", 630), ("DEDUCTIONS", 780), ("NET PAY", 930), ("EMAIL STATUS", 1090)]
    for h, hx in headers:
        draw.text((hx, ty1 + 10), h, font=font_bold_12, fill=C_TEXT_MUTED)
        
    rows = [
        ("John Smith", "HDFC •••• 4819", "₹ 43,900", "₹ 5,000", "₹ 38,900", "Sent" if frame_idx >= 155 else "Pending"),
        ("Sarah Johnson", "ICICI •••• 9102", "₹ 41,200", "₹ 4,200", "₹ 37,000", "Sent" if frame_idx >= 155 else "Pending"),
        ("Michael Scott", "SBI •••• 1184", "₹ 38,500", "₹ 3,800", "₹ 34,700", "Sent" if frame_idx >= 155 else "Pending"),
        ("Emily Davis", "HDFC •••• 6631", "₹ 35,000", "₹ 3,500", "₹ 31,500", "Sent" if frame_idx >= 155 else "Pending")
    ]
    ry = ty1 + 42
    for r_nm, r_bk, r_gr, r_dd, r_nt, r_em in rows:
        draw.rectangle([tx1, ry, tx2, ry + 42], fill=C_CARD_BG, outline=C_BORDER)
        draw.text((260, ry + 12), r_nm, font=font_bold_14, fill=C_TEXT_DARK)
        draw.text((430, ry + 12), r_bk, font=font_reg_12, fill=C_TEXT_MUTED)
        draw.text((630, ry + 12), r_gr, font=font_bold_12, fill=C_TEXT_DARK)
        draw.text((780, ry + 12), r_dd, font=font_reg_12, fill=C_AMBER)
        draw.text((930, ry + 12), r_nt, font=font_bold_14, fill=C_GREEN)
        em_col = C_GREEN if r_em == "Sent" else C_TEXT_MUTED
        em_bg = C_GREEN_BG if r_em == "Sent" else C_MAIN_BG
        draw.rounded_rectangle([1090, ry + 8, 1170, ry + 30], radius=11, fill=em_bg)
        draw.text((1110, ry + 11), r_em, font=font_bold_10, fill=em_col)
        ry += 44
        
    if frame_idx < 90:
        t = smoothstep((frame_idx - 24) / (90 - 24))
        cur_x = 500 + (995 - 500) * t
        cur_y = 350 + (160 - 350) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 80))
        draw_bottom_step_banner(draw, 1, "Click 'Bank CSV' to prepare direct salary transfer upload for banking portal")
    elif frame_idx < 155:
        t = smoothstep((frame_idx - 90) / (155 - 90))
        cur_x = 995 + (1165 - 995) * t
        cur_y = 160 + (160 - 160) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 148))
        draw_bottom_step_banner(draw, 2, "Click 'Dispatch Emails' to automatically send encrypted payslip PDFs to staff")
    else:
        draw_bottom_step_banner(draw, 3, "Payroll dispatch complete! 12 payslip PDF emails sent successfully")
        tx1, ty1, tx2, ty2 = 780, 70, 1245, 118
        draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_GREEN_BG, outline=C_GREEN)
        draw.text((tx1 + 18, ty1 + 14), "✓ Success: 12 Payslip emails dispatched!", font=font_bold_14, fill=C_GREEN)
    return img

# ==============================================================================
# CHAPTER 8: COMPANY PROFILE
# ==============================================================================
def render_chapter_8(frame_idx):
    img = Image.new("RGB", (WIDTH, HEIGHT), color=C_MAIN_BG)
    if frame_idx < 24:
        draw_intro_card(img, 8, "Company Profile", "Configure organization metadata, logo branding, GPS geofence & shift policies.")
        return img
    elif frame_idx > 218:
        draw_outro_card(img, 8, "Company Profile", [
            "Upload company branding logo for reports",
            "Configure office GPS geofence latitude, longitude & radius",
            "Set official work shifts, grace limits & email alerts"
        ])
        return img
    draw = draw_shell(img, active_idx=8)
    draw.text((235, 75), "Company Profile & Attendance Policies", font=font_bold_20, fill=C_TEXT_DARK)
    draw.text((235, 102), "Manage company branding, office GPS geofence boundary, and official shift hours.", font=font_reg_12, fill=C_TEXT_MUTED)
    
    # 2 Column Settings Form
    cx1, cy1, cx2, cy2 = 235, 126, 1250, 620
    draw.rounded_rectangle([cx1, cy1, cx2, cy2], radius=8, fill=C_CARD_BG, outline=C_BORDER)
    draw.text((260, 145), "Organization Settings & Geofence Coordinates", font=font_bold_16, fill=C_TEXT_DARK)
    draw.line([cx1, 180, cx2, 180], fill=C_BORDER)
    
    settings = [
        ("Company Legal Name", "HEXA TECHNOLOGIES PRIVATE LIMITED", 260, 200, 700),
        ("GSTIN / Tax Registration", "33AAAAA0000A1Z5", 740, 200, 1210),
        ("Office GPS Geofence Coordinates", "12.9716° N, 77.5946° E (Allowed Radius: 150m)", 260, 280, 700),
        ("Standard Shift Schedule", "09:00 AM - 06:00 PM (Grace Period: 15 mins)", 740, 280, 1210),
        ("Automated Daily Report Email", "director@hexatech.com, hr@hexatech.com", 260, 360, 700),
        ("Company Logo Branding", "argus_triangle_logo.png (Configured)", 740, 360, 1210)
    ]
    for lbl, val, gx1, gy1, gx2 in settings:
        draw.text((gx1, gy1), lbl, font=font_bold_12, fill=C_TEXT_MUTED)
        draw.rounded_rectangle([gx1, gy1 + 22, gx2, gy1 + 58], radius=6, fill=C_MAIN_BG, outline=C_BORDER)
        draw.text((gx1 + 14, gy1 + 33), val, font=font_bold_14, fill=C_TEXT_DARK)
        
    # Save Button
    sbtn = [1050, 450, 1210, 495]
    draw.rounded_rectangle(sbtn, radius=6, fill=C_PRIMARY)
    draw.text((1075, 463), "Save Settings", font=font_bold_14, fill=C_CARD_BG)
    
    if frame_idx < 90:
        t = smoothstep((frame_idx - 24) / (90 - 24))
        cur_x = 400 + (500 - 400) * t
        cur_y = 500 + (300 - 500) * t
        draw_cursor(draw, cur_x, cur_y, clicking=False)
        draw_bottom_step_banner(draw, 1, "Review organization branding, GSTIN, and GPS office geofence radius")
    elif frame_idx < 155:
        t = smoothstep((frame_idx - 90) / (155 - 90))
        cur_x = 500 + (1130 - 500) * t
        cur_y = 300 + (472 - 300) * t
        draw_cursor(draw, cur_x, cur_y, clicking=(frame_idx >= 148))
        draw_bottom_step_banner(draw, 2, "Click 'Save Settings' to apply shifts, geofence, and automated reports")
    else:
        draw_bottom_step_banner(draw, 3, "Company configuration saved! Attendance rules & geofence active")
        tx1, ty1, tx2, ty2 = 780, 70, 1245, 118
        draw.rounded_rectangle([tx1, ty1, tx2, ty2], radius=8, fill=C_GREEN_BG, outline=C_GREEN)
        draw.text((tx1 + 18, ty1 + 14), "✓ Success: Company profile and policies saved!", font=font_bold_14, fill=C_GREEN)
    return img

ALL_CHAPTERS = [
    (1, "demo_employee_details.mp4", render_chapter_1),
    (2, "demo_live_report.mp4", render_chapter_2),
    (3, "demo_attendance_report.mp4", render_chapter_3),
    (4, "demo_manual_entry.mp4", render_chapter_4),
    (5, "demo_payment_entry.mp4", render_chapter_5),
    (6, "demo_payslip_preview.mp4", render_chapter_6),
    (7, "demo_salary_report.mp4", render_chapter_7),
    (8, "demo_company_profile.mp4", render_chapter_8)
]

def generate_all_videos():
    out_dir = "static/videos"
    os.makedirs(out_dir, exist_ok=True)
    for ch_num, filename, render_func in ALL_CHAPTERS:
        filepath = os.path.join(out_dir, filename)
        print(f"Generating Chapter {ch_num} -> {filepath}...")
        writer = imageio.get_writer(filepath, fps=FPS, codec="libx264", pixelformat="yuv420p", quality=8)
        for f in range(TOTAL_FRAMES):
            frame_img = render_func(f)
            writer.append_data(np.array(frame_img))
        writer.close()
        sz = os.path.getsize(filepath)
        print(f"  [OK] Finished Chapter {ch_num} ({sz} bytes)")
    print("\nAll 8 tutorial videos generated successfully!")

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    generate_all_videos()
