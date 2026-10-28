/**
 * ARGUS TECHNOLOGIES — TEACHER AI ENGINE (AGENT 1)
 * =============================================================
 * Interactive on-screen AI tutor and mentor that explains any element,
 * tab, form input, modal control, or button wherever the cursor hovers.
 *
 * Triggered by shortcut key: CTRL + SHIFT (or CTRL + SHIFT + T)
 * Or by clicking the floating bottom-right '🎓 Teacher AI' trigger pill.
 */

(function (window, document) {
  'use strict';

// --- UNIVERSAL DRAGGABLE & BOTTOM-CENTERED AI DOCK CONTROLLER ---
if (!window.initArgusAiDockDraggable) {
// Shared utility: Initialize Draggable & Bottom-Centered AI Dock
window.initArgusAiDockDraggable = function (dock) {
  if (!dock || dock.__argusDraggableReady) return;
  dock.__argusDraggableReady = true;

  const STORAGE_KEY = 'argus_ai_dock_pos';

  function clampAndApply(left, top) {
    const dockW = dock.offsetWidth || 170;
    const dockH = dock.offsetHeight || 50;
    const margin = 12;
    const maxL = Math.max(margin, window.innerWidth - dockW - margin);
    const maxT = Math.max(margin, window.innerHeight - dockH - margin);
    const safeL = Math.max(margin, Math.min(left, maxL));
    const safeT = Math.max(margin, Math.min(top, maxT));

    dock.style.left = safeL + 'px';
    dock.style.top = safeT + 'px';
    dock.style.bottom = 'auto';
    dock.style.right = 'auto';
    dock.style.transform = 'none';
  }

  function restorePosition() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const pos = JSON.parse(saved);
        if (typeof pos.left === 'number' && typeof pos.top === 'number') {
          clampAndApply(pos.left, pos.top);
          return;
        }
      }
    } catch (e) {
      console.warn('Dock restore error:', e);
    }
    // Default position: bottom center
    dock.style.left = '50%';
    dock.style.bottom = '24px';
    dock.style.top = 'auto';
    dock.style.right = 'auto';
    dock.style.transform = 'translateX(-50%)';
  }

  let isDragging = false;
  let hasMoved = false;
  let startX = 0, startY = 0;
  let initialLeft = 0, initialTop = 0;

  function onPointerDown(e) {
    // Only primary mouse button or single touch
    if (e.type === 'mousedown' && e.button !== 0) return;

    const pt = e.touches ? e.touches[0] : e;
    startX = pt.clientX;
    startY = pt.clientY;

    const rect = dock.getBoundingClientRect();
    initialLeft = rect.left;
    initialTop = rect.top;
    hasMoved = false;
    isDragging = true;

    document.addEventListener('mousemove', onPointerMove, { passive: false });
    document.addEventListener('mouseup', onPointerUp, { passive: false });
    document.addEventListener('touchmove', onPointerMove, { passive: false });
    document.addEventListener('touchend', onPointerUp, { passive: false });
  }

  function onPointerMove(e) {
    if (!isDragging) return;
    const pt = e.touches ? e.touches[0] : e;
    const dx = pt.clientX - startX;
    const dy = pt.clientY - startY;

    if (!hasMoved && Math.hypot(dx, dy) > 5) {
      hasMoved = true;
      dock.classList.add('is-dragging');
    }

    if (hasMoved) {
      if (e.cancelable) e.preventDefault();
      clampAndApply(initialLeft + dx, initialTop + dy);
    }
  }

  function onPointerUp(e) {
    if (!isDragging) return;
    isDragging = false;
    dock.classList.remove('is-dragging');

    document.removeEventListener('mousemove', onPointerMove);
    document.removeEventListener('mouseup', onPointerUp);
    document.removeEventListener('touchmove', onPointerMove);
    document.removeEventListener('touchend', onPointerUp);

    if (hasMoved) {
      // Mark as just dragged so clicks on circle buttons are suppressed
      window.__argusDockJustDragged = true;
      setTimeout(() => {
        window.__argusDockJustDragged = false;
      }, 160);

      const rect = dock.getBoundingClientRect();
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify({
          left: Math.round(rect.left),
          top: Math.round(rect.top)
        }));
      } catch (err) {}
    }
  }

  dock.addEventListener('mousedown', onPointerDown);
  dock.addEventListener('touchstart', onPointerDown, { passive: true });

  // Capture click events during or immediately after drag to prevent opening agent modals
  dock.addEventListener('click', function (e) {
    if (window.__argusDockJustDragged) {
      e.stopImmediatePropagation();
      e.preventDefault();
    }
  }, true);

  // Restore position immediately and on window resize
  setTimeout(restorePosition, 40);
  window.addEventListener('resize', () => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const pos = JSON.parse(saved);
        if (typeof pos.left === 'number' && typeof pos.top === 'number') {
          clampAndApply(pos.left, pos.top);
        }
      }
    } catch (e) {}
  });
};

}


  // =========================================================================
  // 1. ARGUS KNOWLEDGE BASE (TIER 1 - INSTANT 0ms RESPONSES)
  // =========================================================================
  const ARGUS_KNOWLEDGE_BASE = {
    // --- NAVIGATION TABS ---
    'nav-dashboard': {
      title: 'Dashboard Overview',
      category: 'Navigation Tab',
      text: 'Provides real-time attendance KPIs, active employee headcounts, dynamic attendance trend graphs, and operational alerts for your organization.',
      tip: 'Click any KPI stat card to drill down into detailed attendance lists.'
    },
    'nav-employee-details': {
      title: 'Employee Registry & Directory',
      category: 'Navigation Tab',
      text: 'Manage full employee profiles, register 128-d AI facial biometrics, configure salary types, assign branches, and upload ID documents.',
      tip: 'Use "+ Add Employee" to enroll new staff with zero-image biometric storage.'
    },
    'nav-live-report': {
      title: 'Live Check-In & Timeout Monitor',
      category: 'Navigation Tab',
      text: 'Monitors real-time facial check-in sessions, active on-duty personnel, and flags overtime shifts (>15 hrs) for automatic timeout reconciliation.',
      tip: 'Entries are automatically synchronized with GPS proximity distance.'
    },
    'nav-attendance-report': {
      title: 'Attendance Report Central',
      category: 'Navigation Tab',
      text: 'Review daily and monthly attendance categorized into Proper Entries, Improper Entries (outside geofence), Manual Entries, and Simple Tables.',
      tip: 'Use the 🔄 Update button to recalculate attendance and working hours on-the-fly.'
    },
    'nav-manual-entry': {
      title: 'Manual Attendance Entry',
      category: 'Navigation Tab',
      text: 'Allows administrators to insert past attendance punches, backdate entries, and override in/out hours with automated working salary calculation.',
      tip: 'Manual entries are audited and flagged under Manual Entries reports.'
    },
    'nav-payment-entry': {
      title: 'Payment & Wage Management',
      category: 'Navigation Tab',
      text: 'Disburse employee salaries, log payment disbursements (Cash, UPI, Bank Transfer), settle employee advances, and print verified payment vouchers.',
      tip: 'Linked directly with the Advance Management and Balance Report tabs.'
    },
    'nav-advance-management': {
      title: 'Advance & Loan Management',
      category: 'Navigation Tab',
      text: 'Record employee salary advances, track repayment balances, and automatically deduct agreed installments during monthly payroll processing.',
      tip: 'Remaining balances sync with monthly salary slips.'
    },
    'nav-balance-report': {
      title: 'Employee Balance Statement',
      category: 'Navigation Tab',
      text: 'Consolidated financial report showing gross earnings, total advances disbursed, advance repayments, and net balance outstanding across all employees.'
    },
    'nav-monthly-payslip': {
      title: 'Monthly Certified Payslip',
      category: 'Navigation Tab',
      text: 'Generates official Argus corporate salary slips with 4-column earnings and deductions breakdown, company seal, authorized signature, and PDF export.',
      tip: 'Select employee, year, and month to preview and print payslips.'
    },
    'nav-salary-report': {
      title: 'Monthly Consolidated Salary Report',
      category: 'Navigation Tab',
      text: 'Detailed 14-column payroll sheet calculating total working days, overtime, basic wages, travel allowances, deductions, and net salary payable.'
    },
    'nav-company-profile': {
      title: 'Company Profile & Geofence Settings',
      category: 'Navigation Tab',
      text: 'Configure company branding, official office address, GPS geofence coordinates, shift hours, and automated email reporting schedules.'
    },
    'nav-manage-companies': {
      title: 'Multi-Tenant Company Management',
      category: 'Super Admin Portal',
      text: 'System Admin command center to register client companies, allocate employee quotas, assign platform modules, and manage corporate credentials.'
    },
    'nav-branches': {
      title: 'Branch & Regional Hub Management',
      category: 'Enterprise Module',
      text: 'Create and oversee regional branch offices, independent branch GPS perimeters, and assign local staff to dedicated branch hubs.'
    },
    'nav-field-worker': {
      title: 'Field Worker Tracking & CRM',
      category: 'Field Force Module',
      text: 'Live GPS route tracking, client visit logging, Tamil voice audio AI summaries, KM travel reimbursements, and detour anomaly detection for mobile staff.'
    },
    'nav-support': {
      title: 'Support & Help Desk',
      category: 'Support Portal',
      text: 'Submit technical inquiries, report hardware or biometric issues, and communicate directly with Argus Technologies technical support engineers.'
    },

    // --- EMPLOYEE MODAL FIELDS ---
    'inputName': {
      title: 'Employee Full Name',
      category: 'Employee Registry',
      text: 'The legal full name of the employee as it will appear on official company attendance records, daily rosters, and monthly payslips.'
    },
    'inputDepartment': {
      title: 'Department / Division',
      category: 'Employee Registry',
      text: 'Assigns the staff member to an operational department (e.g. Production, IT, HR, Marketing) for filtered reporting and team management.'
    },
    'inputDesignation': {
      title: 'Designation / Job Role',
      category: 'Employee Registry',
      text: 'The employee’s job position or title within the company hierarchy (e.g. Senior CNC Operator, Software Engineer, Supervisor).'
    },
    'inputStatus': {
      title: 'Employee Status',
      category: 'Employee Registry',
      text: 'Active employees count toward your company headcount quota and are eligible for biometric check-in. Inactive employees are archived and quota-exempt.',
      tip: 'Deactivating an employee preserves all their past attendance and payroll records.'
    },
    'inputEmployeeType': {
      title: 'Employee Classification',
      category: 'Employee Registry',
      text: 'Choose Standard Employee for office/in-house biometric terminal check-in, or Field Worker for mobile staff with real-time GPS telemetry and client visits.'
    },
    'inputBranchId': {
      title: 'Assigned Branch Location',
      category: 'Employee Registry',
      text: 'Tags the employee to a specific regional office or the Main Home Office, filtering their attendance to that branch’s geofence perimeter.'
    },
    'inputCalculateProperEntries': {
      title: 'Calculate Proper Entries (Geofence Check)',
      category: 'Attendance Policy',
      text: 'When checked (default), attendance punches outside the company geofence radius are flagged as Improper. Uncheck to exempt this employee (all punches will be marked Proper).',
      tip: 'Ideal for executives, remote staff, or roving workers who need flexible check-in locations.'
    },
    'inputSalaryType': {
      title: 'Salary Basis / Structure',
      category: 'Compensation',
      text: 'Defines how wages are calculated: Hourly-Based (hours worked x hourly rate), Day-Based (daily wage on completing full shift), or Half-Day-Based.'
    },
    'inputDaySalary': {
      title: 'Full Day Salary Rate (₹)',
      category: 'Compensation',
      text: 'The base compensation credited to this employee upon completing their full daily shift hours.'
    },
    'inputHalfDaySalary': {
      title: 'Half Day Salary Rate (₹)',
      category: 'Compensation',
      text: 'The compensation credited when the employee works half shift duration or punches out early.'
    },
    'inputHourlySalary': {
      title: 'Hourly Pay Rate (₹)',
      category: 'Compensation',
      text: 'The rate per hour used to compute precise prorated wages based on exact punch-in and punch-out working hours.'
    },
    'inputShiftStart': {
      title: 'Shift Start Time',
      category: 'Work Schedule',
      text: 'The official expected shift commencement time (e.g. 09:00 AM) used to compute arrival punctuality and shift grace limits.'
    },
    'inputShiftEnd': {
      title: 'Shift End Time',
      category: 'Work Schedule',
      text: 'The official shift conclusion time (e.g. 06:00 PM) used to measure full shift completion and overtime hours.'
    },
    'inputShiftHours': {
      title: 'Shift Duration Target',
      category: 'Work Schedule',
      text: 'Total required working hours per day (e.g. 09:00 or 08:00) needed for a full day wage credit.'
    },
    'inputPhoto': {
      title: 'Face Biometrics Registration',
      category: 'AI Biometrics',
      text: 'Upload or capture a clear frontal portrait. The AI neural engine extracts a 128-dimensional embedding vector and immediately discards the raw photo for 100% privacy.',
      tip: 'Ensure good lighting, direct frontal gaze, and no face coverings.'
    },
    'btnCaptureface': {
      title: 'Capture Face with Webcam',
      category: 'AI Biometrics',
      text: 'Opens the live webcam camera modal with real-time AI face quality analysis to register biometric embeddings directly from your browser.'
    },
    'btnAddDocRowTop': {
      title: 'Add Employee Document',
      category: 'Document Management',
      text: 'Attach identity proofs, certificates, and contracts (PDF, DOCX, JPG, PNG) stored securely in the company document repository.'
    },
    'permPunchAttendance': {
      title: 'Portal Permission: Punch Attendance',
      category: 'Portal Security',
      text: 'Controls whether this employee is permitted to record attendance punches through their personal employee portal login.'
    },
    'permAttendanceHistory': {
      title: 'Portal Permission: Attendance History',
      category: 'Portal Security',
      text: 'Allows the employee to view their historical monthly check-in logs, total working hours, and punch timestamps.'
    },
    'permMonthlyPayslip': {
      title: 'Portal Permission: Monthly Payslip',
      category: 'Portal Security',
      text: 'Enables the employee to preview and download their official monthly salary slips directly from their self-service portal.'
    },

    // --- COMPANY MODAL FIELDS ---
    'inputCompanyName': {
      title: 'Company Legal Name',
      category: 'Company Profile',
      text: 'The registered legal entity name displayed on the top navigation bar, client login portal, reports, and certified payslips.'
    },
    'inputGstin': {
      title: 'GSTIN Registration Number',
      category: 'Company Profile',
      text: 'The 15-digit Goods and Services Tax Identification Number displayed on official corporate documentation and monthly payslips.'
    },
    'inputGeofenceRadius': {
      title: 'Geofence Radius (Meters)',
      category: 'Geofencing Policy',
      text: 'The allowed physical perimeter distance in meters from your office coordinates. Punches within this boundary are recorded as Proper Entries (default: 200m).',
      tip: 'Editable anytime by System Admin to adapt to large campus or factory layouts.'
    },
    'inputCalculateProperEntriesCompany': {
      title: 'Company Proper Entry Policy',
      category: 'Geofencing Policy',
      text: 'When enabled, all employee punches are validated against the geofence perimeter. When disabled, geofence checks are bypassed for the entire company (all punches marked Proper).',
      tip: 'Useful for fully remote companies or distributed workforces without physical offices.'
    },
    'inputEmployeeLimit': {
      title: 'Employee Headcount Quota',
      category: 'Subscription Quota',
      text: 'The maximum number of active employees allowed to be registered by this company under their active subscription tier.'
    },
    'inputBranchLimit': {
      title: 'Branch Creation Limit',
      category: 'Subscription Quota',
      text: 'The maximum number of regional hub branches this company can create under the Multi-Branch Enterprise Module.'
    },
    'inputAutoEmailReports': {
      title: 'Automated Email Digest Service',
      category: 'Automated Reporting',
      text: 'Automatically delivers yesterday’s daily attendance digest and monthly salary spreadsheets directly to the company admin email.'
    },
    'inputDailyReportTime': {
      title: 'Daily Digest Dispatch Time',
      category: 'Automated Reporting',
      text: 'The scheduled time each morning (default: 07:00 AM) when the system automatically compiles and emails yesterday’s attendance report.'
    },
    'inputMonthlyReportDay': {
      title: 'Monthly Salary Report Dispatch Day',
      category: 'Automated Reporting',
      text: 'The day of the month (e.g. 1st) when the system automatically computes and emails the consolidated monthly salary spreadsheet.'
    },
    'inputModSingleCompany': {
      title: 'Single Company Module',
      category: 'Platform Module',
      text: 'Core single-office attendance system including live camera check-in, employee roster, manual entries, and monthly payslips.'
    },
    'inputModBranchCompany': {
      title: 'Multi-Branch Enterprise Module',
      category: 'Platform Module',
      text: 'Enables regional branch offices, independent branch geofences, branch managers, and district-filtered payroll reports.'
    },
    'inputModFieldWorker': {
      title: 'Field Worker & CRM Module',
      category: 'Platform Module',
      text: 'Enables live mobile GPS tracking, client visit CRM, travel allowance calculations, and detour anomaly AI detection.'
    },

    // --- DASHBOARD STAT CARDS ---
    'stat-total-emp': {
      title: 'Total Active Employees',
      category: 'Dashboard KPI',
      text: 'Total number of active staff enrolled in this company who are scheduled to work today.'
    },
    'stat-present-emp': {
      title: 'Present Employees Today',
      category: 'Dashboard KPI',
      text: 'The count of employees who have successfully registered at least one attendance punch today.'
    },
    'stat-absent-emp': {
      title: 'Absent Employees Today',
      category: 'Dashboard KPI',
      text: 'The number of active employees who have not punched attendance today and do not have an approved leave.'
    },
    'stat-present-pct': {
      title: 'Attendance Percentage Rate',
      category: 'Dashboard KPI',
      text: 'The proportion of present employees relative to total active staff: (Present ÷ Total Active) × 100.'
    },
    'stat-timeout-emp': {
      title: 'Active Timeout Entries',
      category: 'Dashboard KPI',
      text: 'Punches that have exceeded 15 consecutive hours without a checkout, flagged for administrator review.'
    },

    // --- BUTTONS & CONTROLS ---
    'btnDetectLocation': {
      title: 'GPS Office Location Detector',
      category: 'Action Button',
      text: 'Uses your device GPS hardware to automatically obtain current high-precision latitude and longitude coordinates.'
    },
    'btnExportPdf': {
      title: 'Export Formatted PDF Report',
      category: 'Action Button',
      text: 'Compiles the current filtered table into a branded, printable corporate PDF report with headers, totals, and timestamps.'
    },
    'btnExportExcel': {
      title: 'Export Excel Spreadsheet',
      category: 'Action Button',
      text: 'Downloads raw report data as an editable Microsoft Excel (.xlsx) spreadsheet for internal bookkeeping and audits.'
    },
    'navBranchDropdownBtn': {
      title: 'Active Branch Location Selector',
      category: 'Header Control',
      text: 'Switch active view between Main Office and regional branches. Filters all dashboards, employee rosters, and reports to that branch.'
    },
    'navCompanyDropdownBtn': {
      title: 'Multi-Tenant Company Switcher',
      category: 'System Admin Control',
      text: 'Allows System Administrators to switch between registered client companies to inspect and manage their individual tenants.'
    }
  };

  // =========================================================================
  // 2. TEACHER AI CORE ENGINE CLASS
  // =========================================================================
  class ArgusTeacherAI {
    constructor() {
      this.isActive = false;
      this.voiceEnabled = localStorage.getItem('argus_teacher_ai_voice') !== 'false';
      this.synth = window.speechSynthesis || null;
      this.currentUtterance = null;
      this.lastInspectedEl = null;
      this.debounceTimer = null;
      this.cachedExplanations = new Map();

      // UI Elements
      this.hudEl = null;
      this.bubbleEl = null;
      this.triggerPillEl = null;

      // Bound Event Listeners
      this._onKeyDown = this.handleKeyDown.bind(this);
      this._onMouseMove = this.handleMouseMove.bind(this);
      this._onMouseLeave = this.handleMouseLeave.bind(this);

      this.init();
    }

    init() {
      this.injectUI();
      this.bindShortcuts();
      console.log('%c[Argus Teacher AI] Agent 1 initialized. Shortcut: CTRL+SHIFT', 'color: #38bdf8; font-weight: bold;');
    }

    // Injects the floating HUD, Explanation Bubble, and Shortcut Trigger Pill
    injectUI() {
      // 1. Top HUD
      this.hudEl = document.createElement('div');
      this.hudEl.className = 'teacher-ai-hud';
      this.hudEl.innerHTML = `
        <div class="teacher-ai-hud-pulse"></div>
        <div class="teacher-ai-hud-title">
          <span>🎓</span>
          <span>Teacher AI Active</span>
        </div>
        <div class="teacher-ai-hud-info">Hover over any tab, field, or button to learn</div>
        <div class="teacher-ai-hud-actions">
          <button type="button" class="teacher-ai-btn-voice" id="teacherAiToggleVoiceBtn" title="Toggle Spoken Voice Explanation">
            <span>${this.voiceEnabled ? '🔊 Voice: ON' : '🔇 Voice: OFF'}</span>
          </button>
          <button type="button" class="teacher-ai-btn-close" id="teacherAiCloseBtn" title="Exit Teacher AI (Ctrl+Shift)">&times;</button>
        </div>
      `;
      document.body.appendChild(this.hudEl);

      // 2. Floating Contextual Bubble
      this.bubbleEl = document.createElement('div');
      this.bubbleEl.className = 'teacher-ai-bubble';
      this.bubbleEl.innerHTML = `
        <div class="teacher-ai-bubble-header">
          <span class="teacher-ai-badge" id="teacherAiBadge">FEATURE</span>
          <span style="font-size: 11px; color: #64748b; font-family: monospace;">ARGUS AI</span>
        </div>
        <div class="teacher-ai-bubble-title" id="teacherAiTitle">Title</div>
        <div class="teacher-ai-bubble-body" id="teacherAiBody">Explanation</div>
        <div class="teacher-ai-bubble-tip" id="teacherAiTip" style="display: none;">
          <span class="icon">💡</span>
          <span id="teacherAiTipText"></span>
        </div>
      `;
      document.body.appendChild(this.bubbleEl);

      // 3. Shared Floating Action Dock & Circular Trigger Button
      let dock = document.getElementById('argusAiDock');
      if (!dock) {
        dock = document.createElement('div');
        dock.id = 'argusAiDock';
        dock.className = 'argus-ai-dock';
        document.body.appendChild(dock);
      }
      if (window.initArgusAiDockDraggable) {
        window.initArgusAiDockDraggable(dock);
      }

      // Remove existing teacher AI buttons if any to prevent duplicate dock icons
      dock.querySelectorAll('#teacherAiCircleBtn').forEach(b => b.remove());

      this.circleBtn = document.createElement('button');
      this.circleBtn.className = 'argus-ai-circle-btn teacher-ai-btn';
      this.circleBtn.id = 'teacherAiCircleBtn';
      this.circleBtn.setAttribute('data-tooltip', 'Teacher AI (Ctrl + Shift)');
      this.circleBtn.setAttribute('aria-label', 'Toggle Teacher AI');
      this.circleBtn.innerHTML = `
        <span class="argus-ai-icon">🎓</span>
      `;
      dock.appendChild(this.circleBtn);
      this.triggerPillEl = this.circleBtn;

      // Bind HUD Buttons
      const voiceBtn = this.hudEl.querySelector('#teacherAiToggleVoiceBtn');
      if (voiceBtn) {
        voiceBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.toggleVoice();
        });
      }

      const closeBtn = this.hudEl.querySelector('#teacherAiCloseBtn');
      if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.deactivate();
        });
      }

      // Bind Trigger Pill Click
      this.triggerPillEl.addEventListener('click', () => {
        this.toggle();
      });
    }

    // Listens for CTRL+SHIFT or CTRL+SHIFT+T
    bindShortcuts() {
      window.addEventListener('keydown', this._onKeyDown, true);
    }

    handleKeyDown(e) {
      // Check for CTRL + SHIFT (with or without T)
      const isCtrlShift = (e.ctrlKey || e.metaKey) && e.shiftKey;
      if (isCtrlShift && (e.key === 'Control' || e.key === 'Shift' || e.code === 'KeyT' || e.key === 'T')) {
        // Prevent default browser conflicts where applicable
        if (e.code === 'KeyT' || e.key === 'T') {
          e.preventDefault();
        }
        this.toggle();
      }
    }

    toggle() {
      if (this.isActive) {
        this.deactivate();
      } else {
        this.activate();
      }
    }

    activate() {
      if (this.isActive) return;
      this.isActive = true;
      this.hudEl.classList.add('active');
      this.triggerPillEl.classList.add('active');
      this.triggerPillEl.setAttribute('data-tooltip', 'Teacher AI Active (Esc / Ctrl+Shift)');
      this.triggerPillEl.innerHTML = '<span class="argus-ai-icon">🎓</span>';

      // Attach mouse tracking
      document.addEventListener('mouseover', this._onMouseMove, true);
      document.addEventListener('mouseleave', this._onMouseLeave, true);

      // Announce activation if voice enabled
      this.speak("Teacher AI activated. Move your cursor over any button, tab, or field to learn how it works.");
    }

    deactivate() {
      if (!this.isActive) return;
      this.isActive = false;
      this.hudEl.classList.remove('active');
      this.triggerPillEl.classList.remove('active');
      this.triggerPillEl.setAttribute('data-tooltip', 'Teacher AI (Ctrl + Shift)');
      this.triggerPillEl.innerHTML = '<span class="argus-ai-icon">🎓</span>';

      // Detach mouse tracking
      document.removeEventListener('mouseover', this._onMouseMove, true);
      document.removeEventListener('mouseleave', this._onMouseLeave, true);

      // Clear highlights & speech
      this.clearHighlight();
      this.hideBubble();
      this.stopSpeaking();
    }

    toggleVoice() {
      this.voiceEnabled = !this.voiceEnabled;
      localStorage.setItem('argus_teacher_ai_voice', this.voiceEnabled ? 'true' : 'false');
      const voiceBtn = this.hudEl.querySelector('#teacherAiToggleVoiceBtn');
      if (voiceBtn) {
        voiceBtn.innerHTML = `<span>${this.voiceEnabled ? '🔊 Voice: ON' : '🔇 Voice: OFF'}</span>`;
      }
      if (this.voiceEnabled) {
        this.speak("Voice enabled.");
      } else {
        this.stopSpeaking();
      }
    }

    // Handles mouse cursor movement across UI elements with smart 160ms debounce
    handleMouseMove(e) {
      if (!this.isActive) return;

      const target = e.target;
      if (!target || target === this.bubbleEl || this.bubbleEl.contains(target) ||
          target === this.hudEl || this.hudEl.contains(target) ||
          target === this.triggerPillEl || this.triggerPillEl.contains(target)) {
        return;
      }

      // Resolve the closest interactive candidate
      const candidate = this.resolveInteractiveTarget(target);
      if (!candidate || candidate === this.lastInspectedEl) {
        return;
      }

      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => {
        this.inspectElement(candidate);
      }, 160);
    }

    handleMouseLeave() {
      clearTimeout(this.debounceTimer);
      this.clearHighlight();
      this.hideBubble();
      this.stopSpeaking();
    }

    // Traverses up from the raw target to find an element with semantic meaning
    resolveInteractiveTarget(el) {
      if (!el || el === document.body || el === document.documentElement) return null;

      // Direct matchers: Links, buttons, form inputs, stat cards, table headers
      const direct = el.closest(
        'a, button, input, select, textarea, .stat-card, .stat-card-clean, th, .nav-item, ' +
        '.nav-branch-toggle-btn, .nav-company-toggle-btn, .modal-box .form-group, .info-table tr, [data-explain], [title]'
      );
      if (direct) return direct;

      // If clicked on a label, return its linked input or the label itself
      if (el.tagName === 'LABEL') return el;

      return el;
    }

    // Analyzes the element and displays explanation
    inspectElement(el) {
      if (!this.isActive || !el) return;

      this.lastInspectedEl = el;
      this.applyHighlight(el);

      // 1. Query Knowledge Base (Tier 1)
      const info = this.resolveElementExplanation(el);
      if (info) {
        this.renderBubble(el, info);
        if (this.voiceEnabled) {
          const speechText = `${info.title}. ${info.text}`;
          this.speak(speechText);
        }
      }
    }

    // Resolves element explanation using Tier 1 dictionary or Tier 2 heuristic
    resolveElementExplanation(el) {
      const id = el.id || '';
      const name = el.getAttribute('name') || '';
      const href = el.getAttribute('href') || '';
      const customExplain = el.getAttribute('data-explain');

      // 1. Explicit data-explain attribute
      if (customExplain) {
        return {
          title: el.getAttribute('data-title') || 'Feature Information',
          category: 'Guide',
          text: customExplain,
          tip: el.getAttribute('data-tip') || null
        };
      }

      // 2. Direct ID lookup in Knowledge Base
      if (id && ARGUS_KNOWLEDGE_BASE[id]) {
        return ARGUS_KNOWLEDGE_BASE[id];
      }

      // 3. Name lookup in Knowledge Base
      if (name && ARGUS_KNOWLEDGE_BASE[name]) {
        return ARGUS_KNOWLEDGE_BASE[name];
      }

      // 4. Navigation Links by href
      if (href) {
        for (const key in ARGUS_KNOWLEDGE_BASE) {
          if (key.startsWith('nav-')) {
            const cleanKey = key.replace('nav-', '');
            if (href.includes(cleanKey) || (cleanKey === 'dashboard' && href === '/')) {
              return ARGUS_KNOWLEDGE_BASE[key];
            }
          }
        }
      }

      // 5. Stat Cards by class
      if (el.classList.contains('stat-card') || el.closest('.stat-card')) {
        const card = el.classList.contains('stat-card') ? el : el.closest('.stat-card');
        const textContent = (card.textContent || '').toLowerCase();
        if (textContent.includes('present %') || textContent.includes('percentage')) return ARGUS_KNOWLEDGE_BASE['stat-present-pct'];
        if (textContent.includes('present')) return ARGUS_KNOWLEDGE_BASE['stat-present-emp'];
        if (textContent.includes('absent')) return ARGUS_KNOWLEDGE_BASE['stat-absent-emp'];
        if (textContent.includes('timeout')) return ARGUS_KNOWLEDGE_BASE['stat-timeout-emp'];
        if (textContent.includes('total')) return ARGUS_KNOWLEDGE_BASE['stat-total-emp'];
      }

      // 6. Action Buttons by class
      if (el.classList.contains('btn-action-view') || el.querySelector('.btn-action-view')) {
        return {
          title: 'View Details Modal',
          category: 'Action Button',
          text: 'Opens the comprehensive full-profile view modal displaying all registered parameters, photos, and documents.'
        };
      }
      if (el.classList.contains('btn-action-edit') || el.querySelector('.btn-action-edit')) {
        return {
          title: 'Edit Record',
          category: 'Action Button',
          text: 'Opens the edit modal to modify details, permissions, salary structure, or update profile parameters.'
        };
      }
      if (el.classList.contains('btn-action-delete') || el.querySelector('.btn-action-delete')) {
        return {
          title: 'Delete Record',
          category: 'Action Button',
          text: 'Permanently removes this record from the database. Available only to authorized System Administrators.'
        };
      }

      // 7. Form Input child inside a .form-group
      if (el.classList.contains('form-group')) {
        const inputInside = el.querySelector('input, select, textarea');
        if (inputInside) {
          return this.resolveElementExplanation(inputInside);
        }
      }

      // 8. TIER 2: Heuristic Fallback for unmapped elements
      return this.generateHeuristicExplanation(el);
    }

    // Heuristically builds a concise explanation from DOM metadata
    generateHeuristicExplanation(el) {
      let labelText = '';
      if (el.id) {
        const linkedLabel = document.querySelector(`label[for="${el.id}"]`);
        if (linkedLabel) labelText = linkedLabel.textContent.replace('*', '').trim();
      }
      if (!labelText) {
        const parentGroup = el.closest('.form-group');
        if (parentGroup) {
          const lbl = parentGroup.querySelector('label');
          if (lbl) labelText = lbl.textContent.replace('*', '').trim();
        }
      }
      if (!labelText) {
        labelText = el.getAttribute('placeholder') || el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent.trim().split('\n')[0].substring(0, 30) || 'Action Control';
      }

      const tagName = el.tagName.toUpperCase();
      let category = 'UI Element';
      let text = `Interactive ${labelText} control in the application.`;

      if (tagName === 'BUTTON') {
        category = 'Action Button';
        text = `Triggers the ${labelText} operation when clicked.`;
      } else if (tagName === 'SELECT') {
        category = 'Selection Dropdown';
        text = `Select the configured option for ${labelText}.`;
      } else if (tagName === 'INPUT') {
        const type = el.getAttribute('type') || 'text';
        if (type === 'checkbox') {
          category = 'Toggle Option';
          text = `Enable or disable ${labelText}.`;
        } else if (type === 'date') {
          category = 'Date Picker';
          text = `Select the effective calendar date for ${labelText}.`;
        } else {
          category = 'Input Field';
          text = `Enter the designated value for ${labelText}.`;
        }
      } else if (tagName === 'TH') {
        category = 'Table Column';
        text = `Displays data sorted by ${labelText}.`;
      }

      return {
        title: labelText,
        category: category,
        text: text,
        tip: null
      };
    }

    // Positions and renders the glassmorphic bubble adjacent to the element
    renderBubble(el, info) {
      const rect = el.getBoundingClientRect();
      const badgeEl = this.bubbleEl.querySelector('#teacherAiBadge');
      const titleEl = this.bubbleEl.querySelector('#teacherAiTitle');
      const bodyEl = this.bubbleEl.querySelector('#teacherAiBody');
      const tipWrapEl = this.bubbleEl.querySelector('#teacherAiTip');
      const tipTextEl = this.bubbleEl.querySelector('#teacherAiTipText');

      // Set category badge style
      badgeEl.textContent = info.category || 'FEATURE';
      badgeEl.className = 'teacher-ai-badge';
      const cat = (info.category || '').toLowerCase();
      if (cat.includes('nav')) badgeEl.classList.add('category-nav');
      else if (cat.includes('form') || cat.includes('field')) badgeEl.classList.add('category-form');
      else if (cat.includes('rule') || cat.includes('policy')) badgeEl.classList.add('category-rule');
      else if (cat.includes('action') || cat.includes('button')) badgeEl.classList.add('category-action');

      titleEl.textContent = info.title;
      bodyEl.textContent = info.text;

      if (info.tip) {
        tipWrapEl.style.display = 'flex';
        tipTextEl.textContent = info.tip;
      } else {
        tipWrapEl.style.display = 'none';
      }

      // Compute optimal position
      const bubbleWidth = 320;
      const bubbleHeight = 160;
      const margin = 12;

      let top = rect.bottom + margin;
      let left = rect.left + (rect.width / 2) - (bubbleWidth / 2);

      // Prevent overflow horizontally
      if (left < 16) left = 16;
      if (left + bubbleWidth > window.innerWidth - 16) {
        left = window.innerWidth - bubbleWidth - 16;
      }

      // Prevent overflow vertically (flip above if near bottom)
      if (top + bubbleHeight > window.innerHeight - 16) {
        top = rect.top - bubbleHeight - margin;
        if (top < 16) top = 16;
      }

      this.bubbleEl.style.top = `${Math.round(top)}px`;
      this.bubbleEl.style.left = `${Math.round(left)}px`;
      this.bubbleEl.classList.add('visible');
    }

    hideBubble() {
      if (this.bubbleEl) {
        this.bubbleEl.classList.remove('visible');
      }
    }

    applyHighlight(el) {
      this.clearHighlight();
      if (el) {
        el.classList.add('teacher-ai-inspected');
      }
    }

    clearHighlight() {
      if (this.lastInspectedEl) {
        this.lastInspectedEl.classList.remove('teacher-ai-inspected');
      }
    }

    // Text to Speech
    speak(text) {
      if (!this.synth || !this.voiceEnabled || !text) return;

      this.stopSpeaking();
      try {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.05;
        utterance.pitch = 1.0;

        // Choose English or Tamil voice based on device / availability
        const voices = this.synth.getVoices();
        if (voices && voices.length > 0) {
          const enVoice = voices.find(v => v.lang.startsWith('en-US') || v.lang.startsWith('en-IN') || v.lang.startsWith('en-GB'));
          if (enVoice) utterance.voice = enVoice;
        }

        this.currentUtterance = utterance;
        this.synth.speak(utterance);
      } catch (err) {
        console.warn('[Teacher AI] Speech synthesis notice:', err);
      }
    }

    stopSpeaking() {
      if (this.synth) {
        try {
          this.synth.cancel();
        } catch (e) {}
      }
      this.currentUtterance = null;
    }
  }

  // Auto-instantiate when DOM is ready (guarded against duplicate executions)
  if (window.__argusTeacherAIInitialized && window.ArgusTeacherAI) {
    // Already active
  } else {
    window.__argusTeacherAIInitialized = true;
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        if (!window.ArgusTeacherAI) {
          window.ArgusTeacherAI = new ArgusTeacherAI();
        }
      });
    } else {
      if (!window.ArgusTeacherAI) {
        window.ArgusTeacherAI = new ArgusTeacherAI();
      }
    }
  }

})(window, document);

