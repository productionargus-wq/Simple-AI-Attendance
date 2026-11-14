/**
 * ARGUS CNC™ — TEACHER AI ENGINE (AGENT 1)
 * =============================================================
 * Interactive on-screen AI tutor and mentor that explains any element,
 * badge, stat card, report column, or calculation rule in our application.
 *
 * Standard Format for all Concepts:
 *   a. Explanation
 *   b. Rule / criteria
 *
 * Triggered by shortcut key: CTRL + SHIFT (or CTRL + SHIFT + T)
 * Or by clicking the floating bottom-right '🎓 Teacher' trigger pill.
 */

(function (window, document) {
  'use strict';

  // --- UNIVERSAL INDEPENDENTLY DRAGGABLE AGENT BUTTON CONTROLLER ---
  if (!window.makeAgentButtonDraggable) {
    window.makeAgentButtonDraggable = function (btn, storageKey, defaultOffsetPx) {
      if (!btn || btn.__agentDraggableReady) return;
      btn.__agentDraggableReady = true;

      function clampAndApply(left, top) {
        const margin = 12;
        const btnW = btn.offsetWidth || 48;
        const btnH = btn.offsetHeight || 48;
        const maxL = Math.max(margin, window.innerWidth - btnW - margin);
        const maxT = Math.max(margin, window.innerHeight - btnH - margin);
        const safeL = Math.max(margin, Math.min(left, maxL));
        const safeT = Math.max(margin, Math.min(top, maxT));

        btn.style.left = safeL + 'px';
        btn.style.top = safeT + 'px';
        btn.style.bottom = 'auto';
        btn.style.right = 'auto';
        btn.style.transform = 'none';
      }

      function getActiveStorageKey() {
        return window.innerWidth <= 768 ? `${storageKey}_mobile` : storageKey;
      }

      function restorePosition() {
        const activeKey = getActiveStorageKey();
        try {
          const saved = localStorage.getItem(activeKey);
          if (saved) {
            const pos = JSON.parse(saved);
            if (typeof pos.left === 'number' && typeof pos.top === 'number') {
              clampAndApply(pos.left, pos.top);
              return;
            }
          }
        } catch (e) {}

        if (window.innerWidth <= 768) {
          const rightPx = Math.round(12 + ((60 - (Number(defaultOffsetPx) || 0)) / 60) * 50);
          btn.style.left = 'auto';
          btn.style.top = 'auto';
          btn.style.right = rightPx + 'px';
          btn.style.bottom = 'calc(50px + env(safe-area-inset-bottom, 0px))';
          btn.style.transform = 'none';
          return;
        }

        btn.style.left = `calc(50% + ${defaultOffsetPx}px)`;
        btn.style.bottom = '24px';
        btn.style.top = 'auto';
        btn.style.right = 'auto';
        btn.style.transform = 'translateX(-50%)';
      }

      let isDragging = false;
      let hasMoved = false;
      let startX = 0, startY = 0;
      let initialLeft = 0, initialTop = 0;

      function onPointerDown(e) {
        if (e.type === 'mousedown' && e.button !== 0) return;
        const pt = e.touches ? e.touches[0] : e;
        startX = pt.clientX;
        startY = pt.clientY;

        const rect = btn.getBoundingClientRect();
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
          btn.classList.add('is-dragging');
        }

        if (hasMoved) {
          if (e.cancelable) e.preventDefault();
          clampAndApply(initialLeft + dx, initialTop + dy);
        }
      }

      function onPointerUp(e) {
        if (!isDragging) return;
        isDragging = false;
        btn.classList.remove('is-dragging');

        document.removeEventListener('mousemove', onPointerMove);
        document.removeEventListener('mouseup', onPointerUp);
        document.removeEventListener('touchmove', onPointerMove);
        document.removeEventListener('touchend', onPointerUp);

        if (hasMoved) {
          btn.__justDragged = true;
          setTimeout(() => { btn.__justDragged = false; }, 160);

          const rect = btn.getBoundingClientRect();
          try {
            localStorage.setItem(getActiveStorageKey(), JSON.stringify({
              left: Math.round(rect.left),
              top: Math.round(rect.top)
            }));
          } catch (err) {}
        }
      }

      btn.addEventListener('mousedown', onPointerDown);
      btn.addEventListener('touchstart', onPointerDown, { passive: true });

      btn.addEventListener('click', function (e) {
        if (btn.__justDragged) {
          e.stopImmediatePropagation();
          e.preventDefault();
        }
      }, true);

      setTimeout(restorePosition, 40);
      window.addEventListener('resize', restorePosition);
    };
  }

  // =========================================================================
  // 1. ARGUS KNOWLEDGE BASE (STRUCTURED: a. Explanation, b. Rule/criteria)
  // =========================================================================
  const ARGUS_KNOWLEDGE_BASE = {
    // --- DASHBOARD STAT CARDS & BADGES ---
    'stat-timeout-emp': {
      title: 'On Timeout / Timeout Badge',
      category: 'Attendance Metric',
      text: 'Identifies check-in attendance sessions that remained open and unclosed long past the normal shift conclusion without a departure punch.\nIn our application: In our application, an entry is marked "On Timeout" when the elapsed time from punch-in exceeds 15 consecutive hours without a checkout punch. It is automatically flagged for administrative review and stops accumulating working hours to prevent unintended overtime salary calculation.',
      tip: 'Admins can reconcile timeouts from Live Report or Attendance Report tabs.'
    },
    'stat-total-emp': {
      title: 'Total Active Employees',
      category: 'Workforce KPI',
      text: 'The complete count of registered personnel currently employed in this company who are scheduled to work.\nIn our application: Evaluates all records in the employees registry where status is "Active". Employees tagged as "Terminated" or "Inactive" are excluded from this count and do not count toward your subscription quota.',
      tip: 'Click to open Employee Directory.'
    },
    'stat-present-emp': {
      title: 'Present Employees Today',
      category: 'Workforce KPI',
      text: 'The verified count of employees who have clocked into work today through biometric facial recognition, mobile GPS check-in, or manual entry.\nIn our application: Condition: Any registered employee who has at least one attendance punch matching today\'s calendar date (entry_date = today).',
      tip: 'Real-time count auto-updates with each facial scan.'
    },
    'stat-absent-emp': {
      title: 'Absent Employees Today',
      category: 'Workforce KPI',
      text: 'Active employees scheduled to work today who have neither checked in nor submitted an authorized leave request.\nIn our application: Formula: Total Active Employees - (Present Employees Today + Approved Leaves Today). Unexcused absences are flagged for operations shift coverage.',
      tip: 'Employees on approved leave are excluded from the absent count.'
    },
    'stat-present-pct': {
      title: 'Attendance Percentage Rate',
      category: 'Workforce KPI',
      text: 'The proportional attendance capacity of your total workforce operating on duty today.\nIn our application: Formula: (Present Today ÷ Total Active Employees) × 100. A rate >= 90% reflects optimal production efficiency; below 75% triggers an operational staffing warning.',
      tip: 'Target 90%+ for steady factory and office throughput.'
    },
    'stat-on-leave': {
      title: 'On Leave Badge',
      category: 'Attendance Metric',
      text: 'Personnel who are officially excused from work today under an authorized company leave of absence.\nIn our application: Verified against the leave database where request_type is "Leave", status is "Approved", and today\'s date falls within [from_date, to_date]. Does not penalize punctuality.',
      tip: 'Manage leave requests from the Leaves tab.'
    },

    // --- SALARY CONCEPTS & TYPES ---
    'concept-day-salary': {
      title: 'Day Salary (Daily Wage Basis)',
      category: 'Compensation Policy',
      text: 'Fixed daily wage rate credited to an employee upon successfully completing their full daily operational work shift.\nIn our application: In our application, when worked minutes >= full shift target duration (e.g. 8 or 9 hours), the employee earns 100% of the Day Salary. If worked duration is >= half-shift target (e.g. 4 hours), half-day rate is credited. Total Daily Basic Salary = (Full Days × Day Salary) + (Half Days × Half Salary).',
      tip: 'Configured in the employee profile modal under Salary Type: Daily.'
    },
    'concept-half-day-salary': {
      title: 'Half Day Salary (Half-Day Basis)',
      category: 'Compensation Policy',
      text: 'Compensation credited when an employee works at least half of their standard shift or operates on half-day units.\nIn our application: In our application, an attendance record is classified as Half-Day when worked duration is >= 4 hours and < 8 hours. Basic Salary is computed in half-day blocks: (Total Half Units × Half Day Salary) + Prorated Partial Minutes.',
      tip: 'Employees leaving early with permission are evaluated under this rate.'
    },
    'concept-hourly-salary': {
      title: 'Hourly Salary (Hour-Based Basis)',
      category: 'Compensation Policy',
      text: 'Precision wage calculation directly proportional to the exact number of elapsed working hours and minutes recorded.\nIn our application: In our application: Basic Salary = (Total Worked Minutes ÷ 60.0) × Hourly Salary Rate. Every minute between punch-in and punch-out is compensated precisely at the hourly rate quotient.',
      tip: 'Ideal for part-time, temporary, or machine-operator shift rosters.'
    },

    // --- ATTENDANCE ENTRY TYPES & CRITERIA ---
    'concept-manual-entry': {
      title: 'Manual Attendance Entry',
      category: 'Attendance Policy',
      text: 'Administrative override tool allowing managers to insert past, missed, or adjusted attendance punches without camera facial recognition.\nIn our application: Criteria & When to Use: Used when the biometric terminal is offline, power outage, off-site client deployment without mobile app, or backdated reconciliation. When logged, sets working salary or hours directly and is distinctly flagged as "Manual Entry" so biometric audit trails remain intact.',
      tip: 'Manual entries are permanently audited under Manual Entries tab.'
    },
    'concept-live-entries': {
      title: 'Live Entries',
      category: 'Attendance Policy',
      text: 'Real-time active shift check-ins currently in progress on the company premises for today.\nIn our application: Criteria in our application: Punch-in timestamp is recorded today, punch-out is null (empty), and elapsed duration is <= 15 hours. Indicates the staff member is currently on duty.',
      tip: 'Monitors real-time employee presence across all office branches.'
    },
    'concept-timeout-entries': {
      title: 'Timeout Entries',
      category: 'Attendance Policy',
      text: 'Attendance sessions where an employee clocked in but did not register a departure punch at shift conclusion.\nIn our application: Criteria in our application: Elapsed time from clock-in > 15 consecutive hours without checkout. Automatically held for administrator review to prevent unintended overtime wage accrual.',
      tip: 'Reconcile timeout entries daily before generating monthly payroll.'
    },
    'concept-proper-entries': {
      title: 'Proper Entries (Geofence Verified)',
      category: 'Geofencing Policy',
      text: 'High-trust biometric attendance punches recorded strictly within the authorized physical perimeter of your office or factory.\nIn our application: Criteria in our application: Punch GPS Coordinates Distance <= Company Geofence Radius (default: 200 meters from office coordinates). Marked in green with verified badge.',
      tip: 'Ensures employees are physically on premises when clocking in.'
    },
    'concept-improper-entries': {
      title: 'Improper Entries (Outside Geofence)',
      category: 'Geofencing Policy',
      text: 'Attendance punches recorded outside the designated company premises perimeter (e.g. from home, transit, or outside allowed radius).\nIn our application: Criteria in our application: Punch GPS Coordinates Distance > Company Geofence Radius. Flagged in orange/red with exact distance in meters for administrative inspection.',
      tip: 'Remote workers can be exempted via the "Apply Geofence Validation" / "Geofence Validation" setting.'
    },
    'concept-all-entries': {
      title: 'All Entries Feed',
      category: 'Attendance Report',
      text: 'The master, unfiltered unified log displaying every punch recorded across the company.\nIn our application: Combines all Proper Entries, Improper Entries, and Manual Entries in chronological sequence without filtering.',
      tip: 'Use date and branch filters to audit comprehensive punch trails.'
    },
    'concept-compact-view': {
      title: 'Compact Consolidated View',
      category: 'Attendance Report',
      text: 'High-density daily summary view consolidating multiple punches per employee into a single clean row per date.\nIn our application: Aggregates first punch-in, last punch-out, net daily minutes worked, daily basic wage, and status. Differentiates from raw logs by providing executive-level daily totals.',
      tip: 'Recommended view for rapid end-of-month attendance audits.'
    },

    // --- FINANCIAL METRICS: EARNINGS & DEDUCTIONS ---
    'concept-earnings': {
      title: 'Earnings / Total Earnings Calculation',
      category: 'Payroll Formula',
      text: 'The gross monetary compensation earned by an employee during the pay period before deductions.\nIn our application: In our application: Total Earnings = Basic Salary + Regular Allowance + Incentive + Petrol/Travel Allowance + Verified Customer Visits Incentive + Other Earnings.\n• Basic Salary is computed from attendance records based on the employee\'s salary type (Daily, Half-Day, or Hourly).\n• Allowances and Incentives come from payments logged with status "Allowance" or "Incentive".\n• Petrol Allowance is computed as Total GPS KM × Per-KM Rate.\n• Verified Client Visits add Verified Visits × Per-Visit Incentive.',
      tip: 'All earnings breakdown items are certified on official monthly payslips.'
    },
    'concept-deductions': {
      title: 'Deductions / Total Deductions Calculation',
      category: 'Payroll Formula',
      text: 'The sum of all financial withholdings, repayments, and prior disbursements deducted from gross earnings.\nIn our application: In our application: Total Deductions = Paid Salary + Advance Repayment + Advance Cash Deductions + Other Deductions.\n• Final Net Pay = max(0, Total Earnings - Total Deductions).\n• Advance Repayment recovers borrowed employee loans logged in the payment ledger.\n• Paid Salary accounts for interim salary advances already disbursed.',
      tip: 'Deductions can never exceed gross earnings (Net pay floored at ₹0.00).'
    },
    'concept-basic-salary': {
      title: 'Basic Salary Calculation',
      category: 'Payroll Formula',
      text: 'The base guaranteed compensation earned from verified shifts worked during the calendar month.\nIn our application: Computed based on employee\'s Salary Type:\n• Daily Basis: (Worked Full Days × Day Salary) + (Half Days × Half Salary)\n• Hourly Basis: (Total Worked Minutes ÷ 60.0) × Hourly Salary\n• Half-Day Basis: (Total Half Units × Half Salary) + Prorated Partial Minutes.',
      tip: 'Overtime hours beyond full shift target can accrue overtime credits.'
    },
    'concept-net-salary': {
      title: 'Net Salary Payable',
      category: 'Payroll Formula',
      text: 'The final certified take-home wage disbursed to the employee.\nIn our application: Formula: max(0, Total Gross Earnings - Total Deductions). This exact figure is printed on the authorized monthly salary slip and voucher.',
      tip: 'Export payslips with authorized seal and signature from Monthly Payslip tab.'
    },
    'concept-advance-repayment': {
      title: 'Advance Repayment',
      category: 'Financial Ledger',
      text: 'Payment entry crediting funds back to the company against an outstanding advance loan.\nIn our application: In our application, logged in Payment Entry with status "Advance Repayment". Directly reduces the employee\'s outstanding loan balance in the Advance & Balance statement.',
      tip: 'Supports Cash, UPI, and Bank Transfer disbursement modes.'
    },

    // --- NAVIGATION TABS ---
    'nav-dashboard': {
      title: 'Dashboard Overview',
      category: 'Navigation Tab',
      text: 'Central command screen providing real-time headcount, attendance KPIs, and trend telemetry.\nIn our application: Aggregates active employee counts, present headcounts, absent rates, and timeout entries for today.',
      tip: 'Click any KPI stat card to drill down into detailed attendance lists.'
    },
    'nav-employee-details': {
      title: 'Employee Registry & Directory',
      category: 'Navigation Tab',
      text: 'Directory for managing full employee profiles, 128-d biometric facial embeddings, and salary terms.\nIn our application: Only active employees in this registry can punch biometric attendance and count toward company quotas.',
      tip: 'Use "+ Add Employee" to enroll new staff with zero-image biometric storage.'
    },
    'nav-live-report': {
      title: 'Live Check-In & Timeout Monitor',
      category: 'Navigation Tab',
      text: 'Monitors real-time on-duty facial check-in sessions and flags open shifts exceeding 15 hours.\nIn our application: Entries with elapsed time > 15 hours without checkout punch are auto-transferred to Timeout review.',
      tip: 'Entries are automatically synchronized with GPS proximity distance.'
    },
    'nav-attendance-report': {
      title: 'Attendance Report Central',
      category: 'Navigation Tab',
      text: 'Historical attendance registry categorized into Proper, Improper, Manual, and Compact views.\nIn our application: Allows managers to recalculate hours, filter by date ranges, and export formatted spreadsheets.',
      tip: 'Use the 🔄 Update button to recalculate attendance and working hours on-the-fly.'
    },
    'nav-manual-entry': {
      title: 'Manual Attendance Entry',
      category: 'Navigation Tab',
      text: 'Administrative tool allowing managers to log or adjust attendance punches without camera biometrics.\nIn our application: Used when biometric terminal is offline or for backdated reconciliation. Flagged under Manual Entries.',
      tip: 'Manual entries calculate salary based on entered hours and status.'
    },
    'nav-payment-entry': {
      title: 'Payment & Wage Management',
      category: 'Navigation Tab',
      text: 'Disburse employee salaries, record advance repayments, and track payment transactions.\nIn our application: Supports Advance Repayment, Salary, Incentive, Allowance, and Bonus disbursement statuses.',
      tip: 'Linked directly with the Advance Management and Balance Report tabs.'
    },
    'nav-advance-management': {
      title: 'Advance & Loan Management',
      category: 'Navigation Tab',
      text: 'Record employee salary advances, track repayment balances, and deduct installments during payroll.\nIn our application: Unsettled advance balances are tracked continuously until cleared by repayments or salary deductions.',
      tip: 'Remaining balances sync with monthly salary slips.'
    },
    'nav-balance-report': {
      title: 'Employee Balance Statement',
      category: 'Navigation Tab',
      text: 'Consolidated financial report showing gross earnings, total advances, repayments, and net balance.\nIn our application: Formula: Outstanding Balance = Total Advances Issued - Total Advance Repayments.',
      tip: 'Audit all employee loan balances from this statement.'
    },
    'nav-monthly-payslip': {
      title: 'Monthly Certified Payslip',
      category: 'Navigation Tab',
      text: 'Generates official Argus corporate salary slips with earnings and deductions breakdown.\nIn our application: Computes Net Pay = max(0, Total Earnings - Total Deductions) with company seal and authorized signature.',
      tip: 'Select employee, year, and month to preview and print payslips.'
    },
    'nav-salary-report': {
      title: 'Monthly Consolidated Salary Report',
      category: 'Navigation Tab',
      text: 'Detailed multi-column payroll sheet calculating working days, overtime, allowances, deductions, and net pay.\nIn our application: Aggregates full attendance and payment data across the entire workforce for the selected month.',
      tip: 'Export to Excel for accounting and bookkeeping.'
    },
    'nav-company-profile': {
      title: 'Company Profile & Geofence Settings',
      category: 'Navigation Tab',
      text: 'Configure company legal branding, office address, GPS geofence coordinates, and shift hours.\nIn our application: Geofence radius defines the physical perimeter for validating Proper vs Improper punches.',
      tip: 'Use Detect Location to automatically set your office coordinates.'
    },
    'nav-manage-companies': {
      title: 'Multi-Tenant Company Management',
      category: 'Super Admin Portal',
      text: 'System Admin command center to register client companies, allocate employee quotas, and manage credentials.\nIn our application: Available exclusively to System Administrators with super_admin privileges.',
      tip: 'Control tenant quotas, branch modules, and billing status.'
    }
  };

  // =========================================================================
  // 2. TEACHER AI CORE ENGINE CLASS
  // =========================================================================
  class ArgusTeacherAI {
    constructor() {
      this.isActive = false;
      this.isMobile = (window.ArgusVoice && window.ArgusVoice.isMobile !== undefined)
        ? window.ArgusVoice.isMobile
        : (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile/i.test(navigator.userAgent || '') || (('ontouchstart' in window) && window.innerWidth <= 1024));
      // Desktop devices EXCLUSIVELY use English audio; Mobile defaults to Tamil or saved preference
      this.language = this.isMobile
        ? ((window.ArgusVoice && typeof window.ArgusVoice.getLanguage === 'function') ? window.ArgusVoice.getLanguage() : (localStorage.getItem('argus_app_voice_lang') || 'ta'))
        : 'en';
      this.voiceEnabled = localStorage.getItem('argus_teacher_ai_voice') !== 'false';
      this.synth = window.speechSynthesis || null;
      this.activeServerAudio = null;
      this.lastInspectedEl = null;
      this.debounceTimer = null;

      // UI Elements
      this.hudEl = null;
      this.triggerPillEl = null;

      // Bound Event Listeners
      this._onKeyDown = this.handleKeyDown.bind(this);
      this._onMouseMove = this.handleMouseMove.bind(this);
      this._onMouseLeave = this.handleMouseLeave.bind(this);
      this._onDocumentClick = this.handleDocumentClick.bind(this);

      this.init();
    }

    init() {
      this.injectUI();
      this.bindShortcuts();
      console.log('%c[Argus Teacher] Agent 1 initialized. Shortcut: CTRL+SHIFT', 'color: #38bdf8; font-weight: bold;');

      // Auto-restore active state across sidebar tab navigation & SPA page loads
      window.addEventListener('page:loaded', () => {
        if (localStorage.getItem('argus_teacher_ai_active') === 'true' && !this.isActive) {
          this.activate(true);
        }
      });

      if (localStorage.getItem('argus_teacher_ai_active') === 'true') {
        setTimeout(() => {
          if (!this.isActive) this.activate(true);
        }, 200);
      }
    }

    injectUI() {
      // 1. Top HUD
      this.hudEl = document.createElement('div');
      this.hudEl.className = 'teacher-ai-hud';
      this.hudEl.innerHTML = `
        <div class="teacher-ai-hud-pulse-ring" title="Teacher Active">
          <div class="teacher-ai-hud-pulse-dot"></div>
        </div>
        <div class="teacher-ai-hud-brand">
          <span class="teacher-ai-hud-icon-wrap">🎓</span>
          <span class="teacher-ai-hud-title">Teacher Active</span>
        </div>
        <div class="teacher-ai-hud-divider"></div>
        <div class="teacher-ai-hud-hint">Hover or click any card, badge, or text to learn rules</div>
        <div class="teacher-ai-hud-actions">
          <button type="button" class="teacher-ai-hud-btn teacher-ai-hud-btn-lang" id="teacherAiToggleLangBtn" title="Switch Voice Language" style="display: ${this.isMobile ? 'inline-flex' : 'none'};">
            <span id="teacherAiLangText">${this.language === 'ta' ? '🌐 தமிழ்' : '🌐 EN'}</span>
          </button>
          <button type="button" class="teacher-ai-hud-btn teacher-ai-hud-btn-voice ${this.voiceEnabled ? 'is-active' : ''}" id="teacherAiToggleVoiceBtn" title="Toggle Spoken Voice Explanation">
            <span class="voice-icon">${this.voiceEnabled ? '🔊' : '🔇'}</span>
            <span class="voice-label">${this.voiceEnabled ? 'Voice: ON' : 'Voice: OFF'}</span>
          </button>
          <button type="button" class="teacher-ai-hud-btn-close" id="teacherAiCloseBtn" title="Exit Teacher (Ctrl+Shift)" aria-label="Exit Teacher">&times;</button>
        </div>
      `;
      document.body.appendChild(this.hudEl);

      // 2. Floating Trigger Button
      let dock = document.getElementById('argusAiDock');
      if (!dock) {
        dock = document.createElement('div');
        dock.id = 'argusAiDock';
        dock.className = 'argus-ai-dock';
        document.body.appendChild(dock);
      }

      dock.querySelectorAll('#teacherAiCircleBtn').forEach(b => b.remove());

      this.circleBtn = document.createElement('button');
      this.circleBtn.className = 'argus-ai-circle-btn teacher-ai-btn';
      this.circleBtn.id = 'teacherAiCircleBtn';
      this.circleBtn.setAttribute('data-tooltip', 'Teacher (Ctrl + Shift)');
      this.circleBtn.setAttribute('aria-label', 'Toggle Teacher');
      this.circleBtn.innerHTML = `<span class="argus-ai-icon">🎓</span>`;
      dock.appendChild(this.circleBtn);
      this.triggerPillEl = this.circleBtn;
      if (window.makeAgentButtonDraggable) {
        window.makeAgentButtonDraggable(this.circleBtn, 'argus_ai_pos_teacher', -60);
      }

      // HUD Button Listeners
      const langBtn = this.hudEl.querySelector('#teacherAiToggleLangBtn');
      if (langBtn) {
        langBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          if (!this.isMobile) return;
          if (window.ArgusVoice && typeof window.ArgusVoice.toggleLanguage === 'function') {
            this.language = window.ArgusVoice.toggleLanguage();
          } else {
            this.language = (this.language === 'ta') ? 'en' : 'ta';
            localStorage.setItem('argus_app_voice_lang', this.language);
            localStorage.setItem('argus_ai_voice_lang', this.language);
          }
          const lbl = langBtn.querySelector('#teacherAiLangText');
          if (lbl) lbl.innerText = (this.language === 'ta') ? '🌐 தமிழ்' : '🌐 EN';
          if (this.voiceEnabled) {
            this.speak(this.language === 'ta' ? 'குரல் மொழி தமிழில் மாற்றப்பட்டது.' : 'Voice language set to English.');
          }
        });
      }

      window.addEventListener('argus-voice-language-changed', (e) => {
        if (!this.isMobile) return;
        this.language = (e.detail && e.detail.language) || 'ta';
        const lbl = this.hudEl ? this.hudEl.querySelector('#teacherAiLangText') : null;
        if (lbl) lbl.innerText = (this.language === 'ta') ? '🌐 தமிழ்' : '🌐 EN';
      });

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

      this.triggerPillEl.addEventListener('click', () => {
        this.toggle();
      });
    }

    bindShortcuts() {
      window.addEventListener('keydown', this._onKeyDown, true);
    }

    handleKeyDown(e) {
      const isCtrlShift = (e.ctrlKey || e.metaKey) && e.shiftKey;
      if (isCtrlShift && (e.key === 'Control' || e.key === 'Shift' || e.code === 'KeyT' || e.key === 'T')) {
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

    activate(silent = false) {
      if (this.isActive) return;
      this.isActive = true;
      localStorage.setItem('argus_teacher_ai_active', 'true');
      this.hudEl.classList.add('active');
      this.triggerPillEl.classList.add('active');
      this.triggerPillEl.setAttribute('data-tooltip', 'Teacher Active (Esc / Ctrl+Shift)');

      // Attach mouse tracking and click inspection
      document.addEventListener('mouseover', this._onMouseMove, true);
      document.addEventListener('mouseleave', this._onMouseLeave, true);
      document.addEventListener('click', this._onDocumentClick, true);

      if (!silent) {
        this.speak("Teacher activated. Hover over any card, badge, or text to learn its rules.");
      }
    }

    deactivate() {
      if (!this.isActive) return;
      this.isActive = false;
      localStorage.setItem('argus_teacher_ai_active', 'false');
      this.hudEl.classList.remove('active');
      this.triggerPillEl.classList.remove('active');
      this.triggerPillEl.setAttribute('data-tooltip', 'Teacher (Ctrl + Shift)');

      document.removeEventListener('mouseover', this._onMouseMove, true);
      document.removeEventListener('mouseleave', this._onMouseLeave, true);
      document.removeEventListener('click', this._onDocumentClick, true);

      this.clearHighlight();
      this.stopSpeaking();
      if (window.ArgusCaptions) {
        window.ArgusCaptions.hide(true);
      }
    }

    toggleVoice() {
      this.voiceEnabled = !this.voiceEnabled;
      localStorage.setItem('argus_teacher_ai_voice', this.voiceEnabled ? 'true' : 'false');
      const voiceBtn = this.hudEl.querySelector('#teacherAiToggleVoiceBtn');
      if (voiceBtn) {
        if (this.voiceEnabled) {
          voiceBtn.classList.add('is-active');
          voiceBtn.innerHTML = '<span class="voice-icon">🔊</span><span class="voice-label">Voice: ON</span>';
        } else {
          voiceBtn.classList.remove('is-active');
          voiceBtn.innerHTML = '<span class="voice-icon">🔇</span><span class="voice-label">Voice: OFF</span>';
        }
      }
      if (this.voiceEnabled) {
        this.speak("Voice enabled.");
      } else {
        this.stopSpeaking();
      }
    }

    // Handles user clicking on any card, text, or header (e.g. "Earnings", "Deductions")
    // NEVER prevents navigation, button triggers, or tab switching!
    handleDocumentClick(e) {
      if (!this.isActive) return;

      const target = e.target;
      if (!target ||
          target === this.hudEl || this.hudEl.contains(target) ||
          target === this.triggerPillEl || this.triggerPillEl.contains(target)) {
        return;
      }

      // Check if clicked element is an actionable button, link, sidebar item, tab, or input
      const actionable = target.closest(
        'a, button, [role="button"], input, select, textarea, ' +
        '.nav-item, .nav-link, .sidebar-link, .btn, .btn-toggle-tab, [onclick], ' +
        '.tab-toggle-container, .sysadmin-company-select, .pagination a, [data-dismiss]'
      );
      if (actionable) {
        // ALWAYS permit normal clicks, navigation, tab toggling, and button triggers!
        return;
      }

      // If clicked on an informative element (stat card, financial title, column header)
      const candidate = this.resolveClickableTextTarget(target);
      if (candidate) {
        this.inspectElement(candidate, true);
      }
    }

    resolveClickableTextTarget(el) {
      if (!el || el === document.body || el === document.documentElement) return null;
      const card = el.closest('[data-teacher-key], .dash-stat-card, .stat-card, .stat-card-clean');
      if (card) return card;

      const text = (el.innerText || el.textContent || '').trim().toLowerCase();
      if (text.length > 2 && text.length < 50) {
        if (text.includes('earning') || text.includes('deduction') || text.includes('salary') ||
            text.includes('timeout') || text.includes('advance') || text.includes('proper') ||
            text.includes('improper') || text.includes('manual') || text.includes('present') ||
            text.includes('absent') || text.includes('leave') || text.includes('total')) {
          return el;
        }
      }
      return null;
    }

    handleMouseMove(e) {
      if (!this.isActive) return;

      const target = e.target;
      if (!target ||
          target === this.hudEl || this.hudEl.contains(target) ||
          target === this.triggerPillEl || this.triggerPillEl.contains(target)) {
        return;
      }

      const candidate = this.resolveInteractiveTarget(target);
      if (!candidate || candidate === this.lastInspectedEl) {
        return;
      }

      clearTimeout(this.debounceTimer);
      this.debounceTimer = setTimeout(() => {
        this.inspectElement(candidate, false);
      }, 160);
    }

    handleMouseLeave() {
      clearTimeout(this.debounceTimer);
      this.clearHighlight();
      this.stopSpeaking();
      if (window.ArgusCaptions) {
        window.ArgusCaptions.hide(true);
      }
    }

    resolveInteractiveTarget(el) {
      if (!el || el === document.body || el === document.documentElement) return null;

      // 1. Direct attribute or wrapper with data-teacher-key
      const explicitCard = el.closest('[data-teacher-key], .dash-stat-card, .stat-card, .stat-card-clean, .kpi-card');
      if (explicitCard) return explicitCard;

      // 2. Direct matchers: Badges, table headers, buttons, inputs, links, labels, tabs
      const direct = el.closest(
        '.badge, [class*="badge"], th, .nav-item, a, button, input, select, textarea, ' +
        '.info-table tr, [data-explain], [title], .table-header, label, .btn-toggle-tab'
      );
      if (direct) return direct;

      // 3. If clicked or hovered on standalone text element
      const text = (el.innerText || el.textContent || '').trim().toLowerCase();
      if (text.length > 2 && text.length < 50) {
        if (text.includes('earning') || text.includes('deduction') || text.includes('salary') ||
            text.includes('timeout') || text.includes('advance') || text.includes('proper') ||
            text.includes('improper') || text.includes('manual') || text.includes('present') ||
            text.includes('absent') || text.includes('leave') || text.includes('total')) {
          return el;
        }
      }

      return el;
    }

    sanitizeExplanationText(rawText) {
      if (!rawText) return '';
      return String(rawText)
        .replace(/a\.\s*Explanation:?\s*/gi, '')
        .replace(/b\.\s*Rule\s*\/?\s*criteria:?\s*/gi, '')
        .replace(/Criteria\s*&\s*When\s*to\s*Use:?\s*/gi, 'When to use: ')
        .replace(/Criteria\s*in\s*our\s*application:?\s*/gi, 'In our application: ')
        .replace(/\bExplanation:?\s*/gi, '')
        .replace(/\b(?:Rule\s*(?:and|\/|&)?\s*)?Criteria:?\s*/gi, '')
        .replace(/\n+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    }

    inspectElement(el, isExplicitClick = false) {
      if (!this.isActive || !el) return;

      this.lastInspectedEl = el;
      this.applyHighlight(el);

      const info = this.resolveElementExplanation(el);
      if (info) {
        const cleanBody = this.sanitizeExplanationText(info.text);
        const speechClean = cleanBody ? `${info.title}. ${cleanBody}` : info.title;
        if (this.voiceEnabled) {
          this.speak(speechClean);
        } else {
          // If voice is muted, show in live captions HUD without obstruction
          if (window.ArgusCaptions && this.language === 'en') {
            window.ArgusCaptions.show(speechClean);
          }
        }
      }
    }

    resolveElementExplanation(el) {
      const id = el.id || '';
      const name = el.getAttribute('name') || '';
      const href = el.getAttribute('href') || '';
      const customExplain = el.getAttribute('data-explain');
      const textContent = (el.textContent || el.innerText || '').toLowerCase();

      // 0. Direct data-teacher-key attribute on element or closest parent
      const teacherKey = el.getAttribute('data-teacher-key') || el.closest('[data-teacher-key]')?.getAttribute('data-teacher-key');
      if (teacherKey && ARGUS_KNOWLEDGE_BASE[teacherKey]) {
        return ARGUS_KNOWLEDGE_BASE[teacherKey];
      }

      // 1. Explicit data-explain attribute
      if (customExplain) {
        return {
          title: el.getAttribute('data-title') || 'Feature Information',
          category: 'Guide',
          text: customExplain,
          tip: el.getAttribute('data-tip') || null
        };
      }

      // 2. Direct ID lookup
      if (id && ARGUS_KNOWLEDGE_BASE[id]) {
        return ARGUS_KNOWLEDGE_BASE[id];
      }

      // 3. Name lookup
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

      // 5. Stat Cards & Badges by class, ID, or content
      const cardEl = el.closest('.dash-stat-card, .stat-card, .stat-card-clean') || el;
      if (cardEl.classList.contains('card-timeout') || el.classList.contains('badge-timeout') || el.closest('.badge-timeout') || id.includes('timeout') || textContent.includes('timeout')) {
        return ARGUS_KNOWLEDGE_BASE['stat-timeout-emp'];
      }
      if (cardEl.classList.contains('card-total') || id === 'statTotal' || id === 'totalEmployees' || textContent.includes('total employee') || textContent.includes('total staff')) {
        return ARGUS_KNOWLEDGE_BASE['stat-total-emp'];
      }
      if (cardEl.classList.contains('card-present') || id === 'statPresent' || id === 'presentToday' || textContent.includes('present today')) {
        if (el.id === 'statPresentPct' || (textContent.includes('%') && textContent.includes('present'))) {
          return ARGUS_KNOWLEDGE_BASE['stat-present-pct'];
        }
        return ARGUS_KNOWLEDGE_BASE['stat-present-emp'];
      }
      if (cardEl.classList.contains('card-leave') || id === 'statOnLeave' || el.classList.contains('badge-leave') || el.closest('.badge-leave') || textContent.includes('on leave')) {
        return ARGUS_KNOWLEDGE_BASE['stat-on-leave'];
      }
      if (cardEl.classList.contains('card-absent') || id === 'statAbsent' || id === 'absentToday' || textContent.includes('absent today')) {
        return ARGUS_KNOWLEDGE_BASE['stat-absent-emp'];
      }
      if (textContent.includes('present %') || textContent.includes('percentage') || textContent.includes('attendance rate') || id === 'statPresentPct') {
        return ARGUS_KNOWLEDGE_BASE['stat-present-pct'];
      }

      // 6. Financial Concepts (Earnings, Deductions, Net Pay, Advances)
      if (textContent.includes('earning') || textContent.includes('gross pay')) {
        return ARGUS_KNOWLEDGE_BASE['concept-earnings'];
      }
      if (textContent.includes('deduction') || textContent.includes('total deduction')) {
        return ARGUS_KNOWLEDGE_BASE['concept-deductions'];
      }
      if (textContent.includes('net salary') || textContent.includes('net pay') || textContent.includes('take home')) {
        return ARGUS_KNOWLEDGE_BASE['concept-net-salary'];
      }
      if (textContent.includes('basic salary') || textContent.includes('basic wage') || textContent.includes('basic pay')) {
        return ARGUS_KNOWLEDGE_BASE['concept-basic-salary'];
      }
      if (textContent.includes('advance repayment') || textContent.includes('repayment')) {
        return ARGUS_KNOWLEDGE_BASE['concept-advance-repayment'];
      }
      if (textContent.includes('advance')) {
        return ARGUS_KNOWLEDGE_BASE['nav-advance-management'];
      }

      // 7. Salary Types
      if (textContent.includes('day salary') || textContent.includes('daily wage') || textContent.includes('day-based')) {
        return ARGUS_KNOWLEDGE_BASE['concept-day-salary'];
      }
      if (textContent.includes('half day') || textContent.includes('half-day')) {
        return ARGUS_KNOWLEDGE_BASE['concept-half-day-salary'];
      }
      if (textContent.includes('hourly') || textContent.includes('hour rate') || textContent.includes('hour salary')) {
        return ARGUS_KNOWLEDGE_BASE['concept-hourly-salary'];
      }

      // 8. Attendance Types (Proper, Improper, Manual, Compact View, Live)
      if (textContent.includes('proper entry') || textContent.includes('proper entries')) {
        return ARGUS_KNOWLEDGE_BASE['concept-proper-entries'];
      }
      if (textContent.includes('improper entry') || textContent.includes('improper entries')) {
        return ARGUS_KNOWLEDGE_BASE['concept-improper-entries'];
      }
      if (textContent.includes('compact view') || textContent.includes('compact report')) {
        return ARGUS_KNOWLEDGE_BASE['concept-compact-view'];
      }
      if (textContent.includes('all entries')) {
        return ARGUS_KNOWLEDGE_BASE['concept-all-entries'];
      }
      if (textContent.includes('manual entry') || textContent.includes('manual attendance')) {
        return ARGUS_KNOWLEDGE_BASE['concept-manual-entry'];
      }
      if (textContent.includes('live report') || textContent.includes('live entries')) {
        return ARGUS_KNOWLEDGE_BASE['concept-live-entries'];
      }

      // 9. Heuristic Fallback with strict a. Explanation and b. Rule/criteria structure
      return this.generateHeuristicExplanation(el);
    }

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
        labelText = el.getAttribute('placeholder') || el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent.trim().split('\n')[0].substring(0, 32) || 'Application Control';
      }

      const tagName = el.tagName.toUpperCase();
      let category = 'Operational Control';
      let text = `Configured interface control for managing ${labelText} in this module. Verified according to active tenant business rules and role authorization permissions.`;

      if (tagName === 'BUTTON') {
        category = 'Action Trigger';
        text = `Interactive command button to execute the ${labelText} operation. Triggers the designated server action or workflow modal when clicked by an authorized manager.`;
      } else if (tagName === 'TH') {
        category = 'Report Column';
        text = `Displays verified tabular data metrics for ${labelText}. In our application, this column reflects data queried directly from the tenant database filtered by selected date and branch parameters.`;
      } else if (tagName === 'INPUT' || tagName === 'SELECT' || tagName === 'TEXTAREA') {
        category = 'Form Configuration';
        text = `Configurable parameters field for ${labelText}. In our application, input is validated for required formats, numeric boundaries, and tenant isolation before saving.`;
      }

      return {
        title: labelText,
        category: category,
        text: text,
        tip: null
      };
    }

    hideBubble() {
      // Deprecated: UI modal bubble removed in favor of non-intrusive Live Closed Captions
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
        this.lastInspectedEl = null;
      }
      document.querySelectorAll('.teacher-ai-inspected').forEach(el => el.classList.remove('teacher-ai-inspected'));
    }

    stopSpeaking() {
      if (this.activeServerAudio) {
        try {
          this.activeServerAudio.pause();
          this.activeServerAudio.currentTime = 0;
          this.activeServerAudio.src = '';
        } catch (e) {}
        this.activeServerAudio = null;
      }
      if (this.synth) {
        try { this.synth.cancel(); } catch (e) {}
      }
      if (window.speechSynthesis) {
        try { window.speechSynthesis.cancel(); } catch (e) {}
      }
      if (window.ArgusCaptions) {
        try { window.ArgusCaptions.hide(true); } catch (e) {}
      }
    }

    speak(text) {
      if (!this.isActive || !text || this.voiceEnabled === false) return;
      this.stopSpeaking();

      const clean = text.replace(/[*_#`•⚠️📈🏢🚨|]/g, '').replace(/₹/g, ' rupees ').trim();

      // Desktop devices NEVER speak Tamil audio
      if (!this.isMobile) {
        this.language = 'en';
        this.speakEnglishFallback(clean);
        return;
      }

      if (this.language === 'ta') {
        if (this.synth) {
          const voices = this.synth.getVoices() || [];
          const taVoice = voices.find(v => {
            const lang = (v.lang || '').toLowerCase();
            const name = (v.name || '').toLowerCase();
            return lang.startsWith('ta') || name.includes('tamil') || name.includes('தமிழ்');
          });

          if (taVoice) {
            try {
              const utter = new SpeechSynthesisUtterance(clean);
              utter.voice = taVoice;
              utter.lang = taVoice.lang || 'ta-IN';
              utter.rate = 1.05;
              this.synth.speak(utter);
              return;
            } catch (err) {}
          }
        }

        try {
          const audio = new Audio('/api/voice/tamil-tts?text=' + encodeURIComponent(clean.slice(0, 950)) + '&lang=ta');
          audio.playbackRate = 1.1;
          this.activeServerAudio = audio;
          audio.play().catch(e => {
            this.speakEnglishFallback(clean);
          });
          return;
        } catch (e) {
          this.speakEnglishFallback(clean);
        }
      } else {
        this.speakEnglishFallback(clean);
      }
    }

    speakEnglishFallback(text) {
      if (!this.isActive || !this.synth) return;
      try {
        const clean = (text || '').replace(/[*_#`•⚠️📈🏢🚨|]/g, '').replace(/₹/g, ' rupees ').trim();
        const utter = new SpeechSynthesisUtterance(clean);
        utter.rate = 1.05;
        const voices = this.synth.getVoices() || [];
        const enVoice = voices.find(v => (v.lang === 'en-US' || v.lang === 'en-IN' || v.lang === 'en-GB')) ||
                        voices.find(v => (v.lang || '').toLowerCase().startsWith('en'));
        if (enVoice) utter.voice = enVoice;
        utter.onend = () => { if (window.ArgusCaptions) window.ArgusCaptions.hide(false); };
        utter.onerror = () => { if (window.ArgusCaptions) window.ArgusCaptions.hide(false); };
        if (window.ArgusCaptions) {
          window.ArgusCaptions.show(clean, { lang: utter.lang || 'en-US' });
        }
        this.synth.speak(utter);
      } catch (e) {}
    }
  }

  // Initialize on DOM load
  if (!window.argusTeacherAI) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        if (!window.argusTeacherAI) window.argusTeacherAI = new ArgusTeacherAI();
      });
    } else {
      window.argusTeacherAI = new ArgusTeacherAI();
    }
  }

})(window, document);
