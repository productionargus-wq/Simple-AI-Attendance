/**
 * Employee Self-Service Portal Controller for Mobile App
 * Renders strictly Employee-only data & actions using Bearer token APIs.
 */
(function (window) {
  'use strict';

  function esc(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  class EmployeePortalController {
    constructor() {
      this.employee = null;
      this.company = null;
      this.cachedRequests = [];
      this.lastPayslip = null;
      this.portalTerminal = null;
      this.bound = false;
    }

    initTerminalIfNeeded() {
      if (!this.portalTerminal && window.ArgusBiometricTerminal) {
        this.portalTerminal = new window.ArgusBiometricTerminal({
          mode: 'portal',
          elements: {
            video: document.getElementById('portalCameraFeed'),
            canvas: document.getElementById('portalCanvas'),
            cameraOverlay: document.getElementById('portalCameraOverlay'),
            faceReticle: document.getElementById('portalFaceReticle'),
            btnToggleCamera: document.getElementById('btnPortalToggleCam'),
            btnToggleCameraText: document.getElementById('btnPortalToggleCamText'),
            btnMark: document.getElementById('btnPortalPunch'),
            btnMarkText: document.getElementById('btnPortalPunchText'),
            punchContainer: document.getElementById('portalPunchResult'),
            btnHandsFree: document.getElementById('btnPortalToggleHandsFree'),
            handsFreeLabel: document.getElementById('portalHandsfreeToggleLabel'),
            btnSensitivity: document.getElementById('btnPortalToggleSensitivity'),
            sensitivityLabel: document.getElementById('portalSensitivityLabel'),
            blinkHudOverlay: document.getElementById('portalBlinkHudOverlay'),
            blinkHudPill: document.getElementById('portalBlinkHudPill'),
            blinkHudIcon: document.getElementById('portalBlinkHudIcon'),
            blinkHudText: document.getElementById('portalBlinkHudText'),
            blinkHudDots: document.getElementById('portalBlinkHudDots'),
            blinkDot1: document.getElementById('portalBlinkDot1'),
            blinkDot2: document.getElementById('portalBlinkDot2'),
            blinkEyeState: document.getElementById('portalBlinkEyeState')
          },
          onPunchSuccess: () => {
            this.loadAttendanceHistory();
          }
        });
      }
      if (this.portalTerminal && this.company) {
        this.portalTerminal.setCompanyConfig(this.company.company_id || '', this.company.modules || {});
      }
    }

    stopCamera() {
      if (this.portalTerminal && this.portalTerminal.isCameraRunning) {
        this.portalTerminal.stopCamera();
      }
    }

    bindStaticListeners() {
      if (this.bound) return;
      this.bound = true;

      var btnMore = document.getElementById('btnToggleMoreEmpDetails');
      var extra = document.getElementById('empExtraDetails');
      if (btnMore && extra) {
        btnMore.addEventListener('click', function () {
          var isOpen = extra.classList.toggle('open');
          btnMore.textContent = isOpen ? 'Show Less Details ▴' : 'Show More Details ▾';
        });
      }

      var btnFilter = document.getElementById('btnFilterHistory');
      var btnClear = document.getElementById('btnClearHistoryFilter');
      var fromInp = document.getElementById('historyFromDate');
      var toInp = document.getElementById('historyToDate');
      if (btnFilter) btnFilter.addEventListener('click', () => this.loadAttendanceHistory());
      if (btnClear && fromInp && toInp) {
        btnClear.addEventListener('click', () => {
          fromInp.value = '';
          toInp.value = '';
          this.loadAttendanceHistory();
        });
      }

      var psMonth = document.getElementById('payslipMonth');
      var btnLoadPs = document.getElementById('btnLoadPayslip');
      var btnDlPs = document.getElementById('btnDownloadPayslip');
      var btnModalDl = document.getElementById('btnModalDownloadPayslipPdf');
      var closePs = document.getElementById('closePortalPayslipModalBtn');
      var donePs = document.getElementById('donePortalPayslipModalBtn');

      if (psMonth) psMonth.addEventListener('change', () => this.loadPayslip(false));
      if (btnLoadPs) btnLoadPs.addEventListener('click', () => this.loadPayslip(true));
      if (btnDlPs) btnDlPs.addEventListener('click', () => this.downloadPayslipPdf());
      if (btnModalDl) btnModalDl.addEventListener('click', () => this.downloadPayslipPdf());
      if (closePs) closePs.addEventListener('click', () => this.closeModal('modalPortalPayslipPreview'));
      if (donePs) donePs.addEventListener('click', () => this.closeModal('modalPortalPayslipPreview'));

      // Leave & Permission Modals
      var btnOpenLeave = document.getElementById('btnHeaderApplyLeave');
      var btnOpenPerm = document.getElementById('btnHeaderApplyPerm');
      if (btnOpenLeave) btnOpenLeave.addEventListener('click', () => this.openLeaveModal());
      if (btnOpenPerm) btnOpenPerm.addEventListener('click', () => this.openPermModal());

      ['closeLeaveModal', 'btnCancelLeave'].forEach(id => {
        var b = document.getElementById(id);
        if (b) b.addEventListener('click', () => this.closeModal('modalApplyLeave'));
      });
      ['closePermModal', 'btnCancelPerm'].forEach(id => {
        var b = document.getElementById(id);
        if (b) b.addEventListener('click', () => this.closeModal('modalApplyPermission'));
      });
      ['closeViewReqModal', 'btnCloseViewReqModalBtn'].forEach(id => {
        var b = document.getElementById(id);
        if (b) b.addEventListener('click', () => this.closeModal('modalViewEmpRequest'));
      });

      var formLeave = document.getElementById('formApplyLeave');
      if (formLeave) formLeave.addEventListener('submit', (e) => this.submitLeaveForm(e));

      var formPerm = document.getElementById('formApplyPermission');
      if (formPerm) formPerm.addEventListener('submit', (e) => this.submitPermForm(e));

      var pFrom = document.getElementById('permFromTime');
      var pTo = document.getElementById('permToTime');
      if (pFrom) pFrom.addEventListener('change', () => this.calcPermDuration());
      if (pTo) pTo.addEventListener('change', () => this.calcPermDuration());

      var credForm = document.getElementById('employeeCredentialsForm');
      if (credForm) credForm.addEventListener('submit', (e) => this.submitCredentials(e));

      var toggleCredEye = document.getElementById('toggleEmpPassBtn');
      var credInput = document.getElementById('employeeNewPassword');
      if (toggleCredEye && credInput) {
        toggleCredEye.addEventListener('click', () => {
          credInput.type = credInput.type === 'password' ? 'text' : 'password';
        });
      }
    }

    openModal(id) {
      var m = document.getElementById(id);
      if (m) m.classList.add('open');
    }

    closeModal(id) {
      var m = document.getElementById(id);
      if (m) m.classList.remove('open');
    }

    render(employee, company) {
      this.employee = employee || {};
      this.company = company || {};
      this.bindStaticListeners();
      this.initTerminalIfNeeded();

      var emp = this.employee;
      var comp = this.company;
      var perms = emp.permissions || {};

      var compTitle = document.getElementById('portalCompanyTitle');
      if (compTitle) compTitle.textContent = (comp.company_name || emp.company_name || 'ARGUS CNC™').toUpperCase();

      var empNameEl = document.getElementById('portalEmpName');
      var empEmailEl = document.getElementById('portalEmpEmail');
      if (empNameEl) empNameEl.textContent = emp.employee_name || '-';
      if (empEmailEl) empEmailEl.textContent = emp.email_id || '-';

      var logoImg = document.getElementById('portalCompanyLogoImg');
      if (logoImg) {
        if (comp.logo_url) {
          logoImg.src = /^https?:|^data:/i.test(comp.logo_url) ? comp.logo_url : window.ArgusConfig.apiUrl(comp.logo_url);
        } else {
          logoImg.src = 'images/default_profile.svg';
        }
      }

      var salLabel = 'Hourly-Based (₹' + (emp.hourly_salary || 0) + '/hr)';
      if (emp.salary_type === 'daily') salLabel = 'Day-Based (₹' + (emp.day_salary || 0) + '/day)';
      else if (emp.salary_type === 'half_day') salLabel = 'Half-Day-Based (₹' + (emp.half_day_salary || 0) + '/half-day)';

      var extraHtml =
        '<div><strong>Employee ID:</strong> ' + esc(emp.employee_id || emp.id || '-') + '</div>' +
        '<div><strong>Designation:</strong> ' + esc(emp.designation || '-') + '</div>' +
        '<div><strong>Department:</strong> ' + esc(emp.department || '-') + '</div>' +
        '<div><strong>Salary Basis:</strong> ' + esc(salLabel) + '</div>' +
        '<div><strong>Mobile:</strong> ' + esc(emp.mobile_number || '-') + '</div>' +
        '<div><strong>Shift Hours:</strong> ' + esc(emp.no_shift ? '-' : (emp.shift_hours || '09:00')) + '</div>' +
        '<div><strong>Company:</strong> ' + esc(comp.company_name || emp.company_name || '-') + '</div>';

      if (emp.reports_to_details && emp.reports_to_details.length) {
        extraHtml += '<div class="portal-role-block"><strong>Reports To:</strong><div style="display:flex;flex-wrap:wrap;gap:5px;">' +
          emp.reports_to_details.map(m => '<span class="portal-chip">' + esc(m.employee_name) + (m.designation ? ' (' + esc(m.designation) + ')' : '') + '</span>').join('') +
          '</div></div>';
      }
      if (emp.skills && emp.skills.length) {
        extraHtml += '<div class="portal-role-block"><strong>Skillset:</strong><div style="display:flex;flex-wrap:wrap;gap:5px;">' +
          emp.skills.map(s => '<span class="portal-chip">' + esc(s) + '</span>').join('') +
          '</div></div>';
      }
      if (emp.responsibilities_points && emp.responsibilities_points.length) {
        extraHtml += '<div class="portal-role-block"><strong>Responsibilities:</strong><ul style="margin:0;padding-left:18px;">' +
          emp.responsibilities_points.map(pt => '<li>' + esc(pt) + '</li>').join('') +
          '</ul></div>';
      }
      var extraEl = document.getElementById('empExtraDetails');
      if (extraEl) extraEl.innerHTML = extraHtml;

      var pPunch = perms.punch_attendance !== false;
      var pHist = perms.attendance_history !== false;
      var pLeave = perms.leave_permission !== false;
      var pPay = perms.monthly_payslip !== false;
      var pCred = perms.employee_credentials !== false;

      var setVis = (id, show) => {
        var el = document.getElementById(id);
        if (el) el.style.display = show ? '' : 'none';
      };
      setVis('portalRestrictedCard', !(pPunch || pHist || pLeave || pPay || pCred));
      setVis('portalAttendanceCard', pPunch);
      setVis('portalHistoryCard', pHist);
      setVis('leavePermissionSection', pLeave);
      setVis('portalPayslipCard', pPay);
      setVis('portalCredentialsCard', pCred);

      var now = new Date();
      var ym = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
      var fromInp = document.getElementById('historyFromDate');
      var toInp = document.getElementById('historyToDate');
      if (fromInp && !fromInp.value) fromInp.value = ym + '-01';
      if (toInp && !toInp.value) toInp.value = now.toISOString().split('T')[0];

      var psMonth = document.getElementById('payslipMonth');
      if (psMonth && !psMonth.value) psMonth.value = ym;

      var credBadge = document.getElementById('empPassStatusBadge');
      if (credBadge) {
        credBadge.textContent = emp.has_password ? '✓ Password Configured' : 'Not Set';
        credBadge.style.color = emp.has_password ? '#16a34a' : '#b45309';
      }
      var curPwdGrp = document.getElementById('employeeCurrentPasswordGroup');
      if (curPwdGrp) {
        curPwdGrp.style.display = emp.has_password ? '' : 'none';
      }

      if (pHist) this.loadAttendanceHistory();
      if (pLeave) {
        this.loadLeaveBalances();
        this.loadLeaveRequests();
      }
      if (pPay) this.loadPayslip(false);
    }

    async loadAttendanceHistory() {
      var tbody = document.getElementById('portalHistoryBody');
      if (!tbody) return;
      var fromVal = (document.getElementById('historyFromDate') || {}).value || '';
      var toVal = (document.getElementById('historyToDate') || {}).value || '';
      tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:18px;color:#64748b;">Loading attendance history...</td></tr>';

      try {
        var q = new URLSearchParams({ from_date: fromVal, to_date: toVal });
        var res = await window.ArgusConfig.apiFetch('/api/mobile/employee/my-attendance?' + q.toString(), { cache: 'no-store' });
        var data = await res.json();
        var rows = (data && data.data) || [];
        if (!rows.length) {
          tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:20px;color:#64748b;">No attendance records found for this period.</td></tr>';
          return;
        }
        tbody.innerHTML = rows.map(r => {
          var isDone = r.exit_time && r.exit_time !== '----';
          var stPill = isDone
            ? '<span class="badge-status-approved">Completed</span>'
            : '<span class="badge-status-pending">Punched In</span>';
          return '<tr>' +
            '<td style="font-weight:700;white-space:nowrap;">' + esc(r.entry_time || '-') + '</td>' +
            '<td style="min-width:150px;font-size:11.5px;">' + esc(r.entry_location || '-') + '</td>' +
            '<td style="white-space:nowrap;">' + esc(r.entry_status || '-') + '</td>' +
            '<td style="white-space:nowrap;">' + esc(r.exit_time || '----') + '</td>' +
            '<td style="white-space:nowrap;">' + esc(r.exit_status || '-') + '</td>' +
            '<td style="font-weight:700;white-space:nowrap;">' + esc(r.working_hours || '00:00') + '</td>' +
            '<td style="text-align:center;">' + stPill + '</td>' +
          '</tr>';
        }).join('');
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:18px;color:#dc2626;">Failed to load attendance history.</td></tr>';
      }
    }

    async loadLeaveBalances() {
      try {
        var res = await window.ArgusConfig.apiFetch('/api/mobile/employee/leave-balance', { cache: 'no-store' });
        var data = await res.json();
        var b = (data && (data.balance || data.balances)) || {};

        var dayLeaves = [];
        if (b.custom_leaves && Array.isArray(b.custom_leaves) && b.custom_leaves.length) {
          dayLeaves = b.custom_leaves.filter(lv => {
            var u = String(lv.unit || 'Days').toLowerCase();
            var n = String(lv.name || '').toLowerCase();
            return !u.includes('hour') && !u.includes('hr') && n !== 'permission';
          });
        } else {
          dayLeaves = [
            { name: 'Casual Leave (CL)', available: b.casual_leave_available ?? 0, total: b.casual_leave_total || 12, unit: 'Days' },
            { name: 'Sick Leave (SL)', available: b.sick_leave_available ?? 0, total: b.sick_leave_total || 12, unit: 'Days' },
            { name: 'Earned Leave (EL)', available: b.earned_leave_available ?? 0, total: b.earned_leave_total || 18, unit: 'Days' }
          ];
        }

        var permTot = b.permission_hours_total ?? 16;
        var permAvail = b.permission_hours_available ?? 16;
        if (b.custom_leaves && Array.isArray(b.custom_leaves)) {
          var permC = b.custom_leaves.find(lv => String(lv.name || '').toLowerCase() === 'permission' || String(lv.unit || '').toLowerCase().includes('hour'));
          if (permC) {
            permTot = permC.total ?? 0;
            permAvail = permC.available ?? 0;
          }
        }

        var fillClasses = ['fill-blue', 'fill-teal', 'fill-indigo'];
        var barsEl = document.getElementById('empLeaveBarsContainer');
        if (barsEl) {
          var html = dayLeaves.map((lv, idx) => {
            var tot = Number(lv.total || 0);
            var avail = Number(lv.available || 0);
            var pct = tot > 0 ? Math.max(0, Math.min(100, (avail / tot) * 100)) : 0;
            return '<div class="balance-bar-item">' +
              '<div class="balance-bar-header"><span>' + esc(lv.name) + '</span><strong>' + avail + ' / ' + tot + '</strong></div>' +
              '<div class="balance-track"><div class="balance-fill ' + fillClasses[idx % fillClasses.length] + '" style="width:' + pct + '%;"></div></div>' +
            '</div>';
          }).join('');
          var pPct = permTot > 0 ? Math.max(0, Math.min(100, (permAvail / permTot) * 100)) : 0;
          html += '<div class="balance-bar-item">' +
            '<div class="balance-bar-header"><span>Permission Hours</span><strong>' + permAvail + ' / ' + permTot + ' Hrs</strong></div>' +
            '<div class="balance-track"><div class="balance-fill fill-purple" style="width:' + pPct + '%;"></div></div>' +
          '</div>';
          barsEl.innerHTML = html;
        }

        var sel = document.getElementById('leaveInputType');
        if (sel) {
          sel.innerHTML = '<option value="" disabled selected>-- Select Leave Type --</option>';
          dayLeaves.forEach(lv => {
            var o = document.createElement('option');
            o.value = lv.name;
            o.textContent = lv.name + ' (' + (lv.available ?? 0) + ' ' + (lv.unit || 'Days') + ' avail)';
            sel.appendChild(o);
          });
        }
      } catch (e) {}
    }

    async loadLeaveRequests() {
      var tbody = document.getElementById('empRequestsTableBody');
      if (!tbody) return;
      try {
        var res = await window.ArgusConfig.apiFetch('/api/mobile/employee/leave-requests', { cache: 'no-store' });
        var data = await res.json();
        this.cachedRequests = (data && data.requests) || [];
        if (!this.cachedRequests.length) {
          tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:18px;color:#64748b;">No leave or permission requests found.</td></tr>';
          return;
        }
        tbody.innerHTML = this.cachedRequests.map(r => {
          var reqId = String(r.request_id || r.id || r._id || '');
          var st = String(r.status || 'Pending');
          var stLow = st.toLowerCase();
          var stCls = stLow === 'approved' ? 'badge-status-approved' : (stLow === 'rejected' ? 'badge-status-rejected' : 'badge-status-pending');
          var typeHtml = r.request_type === 'Permission'
            ? '<span class="badge-type-perm">Permission</span>'
            : '<span class="badge-type-leave">' + esc((r.leave_type || 'Leave').split(' ')[0]) + '</span>';
          var units = r.request_type === 'Permission'
            ? (r.duration || '01:00') + ' Hrs'
            : (r.days_count || 1) + ' Day(s)';
          var actions = '<button type="button" class="portal-btn-clear" style="padding:3px 7px;font-size:10.5px;" data-view-req="' + esc(reqId) + '">View</button>';
          if (stLow === 'pending') {
            actions += ' <button type="button" class="portal-btn-clear" style="padding:3px 7px;font-size:10.5px;color:#dc2626;" data-del-req="' + esc(reqId) + '">Delete</button>';
          }
          return '<tr>' +
            '<td>' + typeHtml + '</td>' +
            '<td>' + esc(r.from_date || r.date || '-') + '</td>' +
            '<td>' + esc(r.to_date || r.date || '-') + '</td>' +
            '<td><strong>' + esc(units) + '</strong></td>' +
            '<td><span class="' + stCls + '">' + esc(st) + '</span></td>' +
            '<td style="white-space:nowrap;">' + actions + '</td>' +
          '</tr>';
        }).join('');

        tbody.querySelectorAll('[data-view-req]').forEach(btn => {
          btn.addEventListener('click', () => this.viewRequest(btn.getAttribute('data-view-req')));
        });
        tbody.querySelectorAll('[data-del-req]').forEach(btn => {
          btn.addEventListener('click', () => this.deleteRequest(btn.getAttribute('data-del-req')));
        });
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;padding:18px;color:#dc2626;">Failed to load requests.</td></tr>';
      }
    }

    viewRequest(id) {
      var r = this.cachedRequests.find(x => String(x.request_id || x.id || x._id) === String(id));
      if (!r) return;
      var body = document.getElementById('viewReqModalBody');
      if (body) {
        body.innerHTML =
          '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:12.5px;margin-bottom:12px;">' +
            '<div><div style="color:#64748b;font-size:11px;">Type</div><strong>' + esc(r.request_type === 'Permission' ? 'Permission' : (r.leave_type || 'Leave')) + '</strong></div>' +
            '<div><div style="color:#64748b;font-size:11px;">Status</div><strong>' + esc(r.status || 'Pending') + '</strong></div>' +
            '<div><div style="color:#64748b;font-size:11px;">Dates</div><strong>' + esc((r.from_date || r.date || '-') + ' → ' + (r.to_date || r.date || '-')) + '</strong></div>' +
            '<div><div style="color:#64748b;font-size:11px;">Applied On</div><strong>' + esc(r.applied_on || '-') + '</strong></div>' +
          '</div>' +
          '<div style="font-size:12.5px;margin-bottom:10px;"><div style="color:#64748b;font-size:11px;">Reason</div><div style="padding:8px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;">' + esc(r.reason || '-') + '</div></div>' +
          '<div style="font-size:12.5px;"><div style="color:#64748b;font-size:11px;">Admin Remark</div><div style="padding:8px;background:#f1f5f9;border-radius:6px;">' + esc(r.admin_remark || 'No feedback provided yet.') + '</div></div>';
      }
      this.openModal('modalViewEmpRequest');
    }

    async deleteRequest(id) {
      if (!window.confirm('Delete this pending request?')) return;
      try {
        var res = await window.ArgusConfig.apiFetch('/api/mobile/employee/leave-requests/' + encodeURIComponent(id), { method: 'DELETE' });
        var data = await res.json();
        if (data.success) {
          this.loadLeaveBalances();
          this.loadLeaveRequests();
        } else {
          window.alert(data.error || 'Could not delete request.');
        }
      } catch (e) {
        window.alert('Network error deleting request.');
      }
    }

    openLeaveModal() {
      var alertEl = document.getElementById('leaveAlert');
      if (alertEl) { alertEl.className = 'alert-banner'; alertEl.textContent = ''; }
      var todayStr = new Date().toISOString().split('T')[0];
      var f = document.getElementById('leaveFromDate'), t = document.getElementById('leaveToDate');
      if (f && !f.value) f.value = todayStr;
      if (t && !t.value) t.value = todayStr;
      this.openModal('modalApplyLeave');
    }

    openPermModal() {
      var alertEl = document.getElementById('permAlert');
      if (alertEl) { alertEl.className = 'alert-banner'; alertEl.textContent = ''; }
      var pd = document.getElementById('permDate');
      if (pd && !pd.value) pd.value = new Date().toISOString().split('T')[0];
      this.calcPermDuration();
      this.openModal('modalApplyPermission');
    }

    calcPermDuration() {
      var f = (document.getElementById('permFromTime') || {}).value || '10:00';
      var t = (document.getElementById('permToTime') || {}).value || '12:00';
      var out = document.getElementById('permDuration');
      if (!out) return;
      var fp = f.split(':'), tp = t.split(':');
      var mins = (parseInt(tp[0], 10) * 60 + parseInt(tp[1], 10)) - (parseInt(fp[0], 10) * 60 + parseInt(fp[1], 10));
      if (mins < 0) mins += 1440;
      var hh = String(Math.floor(mins / 60)).padStart(2, '0');
      var mm = String(mins % 60).padStart(2, '0');
      out.value = hh + ':' + mm;
    }

    async submitLeaveForm(e) {
      e.preventDefault();
      var alertEl = document.getElementById('leaveAlert');
      var btn = document.getElementById('btnSubmitLeave');
      if (btn) btn.disabled = true;
      try {
        var fd = new FormData(e.target);
        var res = await window.ArgusConfig.apiFetch('/api/mobile/employee/leave-requests/apply', { method: 'POST', body: fd });
        var data = await res.json();
        if (data.success) {
          if (alertEl) { alertEl.className = 'alert-banner success'; alertEl.textContent = data.message || 'Leave submitted!'; }
          if (window.ArgusVoice) window.ArgusVoice.announceSuccess('விடுப்பு விண்ணப்பம் சமர்ப்பிக்கப்பட்டது.', 'Leave request submitted.');
          e.target.reset();
          this.loadLeaveBalances();
          this.loadLeaveRequests();
          setTimeout(() => this.closeModal('modalApplyLeave'), 900);
        } else {
          if (alertEl) { alertEl.className = 'alert-banner error'; alertEl.textContent = data.error || 'Failed to submit leave.'; }
        }
      } catch (err) {
        if (alertEl) { alertEl.className = 'alert-banner error'; alertEl.textContent = 'Network error submitting leave.'; }
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async submitPermForm(e) {
      e.preventDefault();
      var alertEl = document.getElementById('permAlert');
      var btn = document.getElementById('btnSubmitPerm');
      if (btn) btn.disabled = true;
      try {
        var fd = new FormData(e.target);
        var res = await window.ArgusConfig.apiFetch('/api/mobile/employee/permission-requests/apply', { method: 'POST', body: fd });
        var data = await res.json();
        if (data.success) {
          if (alertEl) { alertEl.className = 'alert-banner success'; alertEl.textContent = data.message || 'Permission submitted!'; }
          if (window.ArgusVoice) window.ArgusVoice.announceSuccess('அனுமதி விண்ணப்பம் சமர்ப்பிக்கப்பட்டது.', 'Permission request submitted.');
          e.target.reset();
          this.loadLeaveBalances();
          this.loadLeaveRequests();
          setTimeout(() => this.closeModal('modalApplyPermission'), 900);
        } else {
          if (alertEl) { alertEl.className = 'alert-banner error'; alertEl.textContent = data.error || 'Failed to submit permission.'; }
        }
      } catch (err) {
        if (alertEl) { alertEl.className = 'alert-banner error'; alertEl.textContent = 'Network error submitting permission.'; }
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async loadPayslip(openModal) {
      var monthInp = document.getElementById('payslipMonth');
      var errEl = document.getElementById('payslipErrorBanner');
      if (errEl) { errEl.className = 'alert-banner'; errEl.textContent = ''; }
      var month = (monthInp && monthInp.value) || new Date().toISOString().slice(0, 7);
      try {
        var res = await window.ArgusConfig.apiFetch('/api/mobile/employee/my-payslip?month=' + encodeURIComponent(month), { cache: 'no-store' });
        var data = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || 'Failed to load payslip.');
        var p = data.payslip || data || {};
        this.lastPayslip = p;

        var basic = p.basic_salary !== undefined ? p.basic_salary : (p.basic_earnings || 0);
        var deduct = p.total_deduction !== undefined ? p.total_deduction : (p.total_deductions || 0);
        var net = p.net_pay !== undefined ? p.net_pay : (p.net_salary || 0);
        var fmt = (v) => '₹' + Number(v || 0).toLocaleString();

        var setText = (id, val) => { var el = document.getElementById(id); if (el) el.textContent = val; };
        setText('psBasic', fmt(basic));
        setText('psOvertime', p.no_shift ? '-' : fmt(p.overtime_pay || 0));
        setText('psAllowance', fmt(p.allowance || 0));
        setText('psIncentive', fmt(p.incentive || 0));
        setText('psTotalEarnings', fmt(p.total_earnings || 0));
        setText('psAdvanceRepay', fmt(p.advance_repayment || 0));
        setText('psOtherDeduct', fmt(p.other_deductions || 0));
        setText('psTotalDeduct', fmt(deduct));
        setText('psNetSalary', fmt(net));
        setText('psWorkingDays', 'Working Days: ' + (p.working_days_breakdown || ((p.working_days || 0) + ' Days')) + ' | Hours: ' + (p.total_working_hours || p.working_hours || '00:00'));

        if (openModal) {
          setText('psModalPeriod', 'Pay Period: ' + (p.pay_period || month));
          var body = document.getElementById('psModalBody');
          if (body) {
            body.innerHTML =
              '<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;font-size:12px;">' +
                '<strong>' + esc(p.company_name || 'Company') + '</strong><br>' +
                'Employee: ' + esc(p.employee_name || '-') + ' | Days: ' + esc(p.working_days_breakdown || p.working_days || 0) +
              '</div>' +
              '<div class="payslip-box"><strong>Total Earnings:</strong> ' + fmt(p.total_earnings) + '</div>' +
              '<div class="payslip-box"><strong>Total Deductions:</strong> ' + fmt(deduct) + '</div>' +
              '<div class="payslip-net-box"><div style="font-size:11px;">NET PAYABLE</div><div style="font-size:24px;font-weight:900;">' + fmt(net) + '</div></div>';
          }
          this.openModal('modalPortalPayslipPreview');
        }
      } catch (err) {
        if (errEl) { errEl.className = 'alert-banner error'; errEl.textContent = err.message || 'Unable to load payslip.'; }
      }
    }

    async downloadPayslipPdf() {
      var month = (document.getElementById('payslipMonth') || {}).value || new Date().toISOString().slice(0, 7);
      var tok = window.ArgusConfig.getToken();
      var url = window.ArgusConfig.apiUrl('/api/mobile/employee/payslip-pdf?month=' + encodeURIComponent(month) + '&auth_token=' + encodeURIComponent(tok));
      try {
        var browserPlugin = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Browser;
        if (browserPlugin && typeof browserPlugin.open === 'function') {
          await browserPlugin.open({ url: url });
          return;
        }
      } catch (e) {}
      window.open(url, '_blank');
    }

    async submitCredentials(e) {
      e.preventDefault();
      var curInp = document.getElementById('employeeCurrentPassword');
      var curGrp = document.getElementById('employeeCurrentPasswordGroup');
      var pwdInp = document.getElementById('employeeNewPassword');
      var alertEl = document.getElementById('credentialsAlert');
      var btn = document.getElementById('btnSaveCredentials');
      var curPwd = (curInp && curInp.value || '').trim();
      var pwd = (pwdInp && pwdInp.value || '').trim();
      var needsCurrent = curGrp && curGrp.style.display !== 'none';
      if (needsCurrent && !curPwd) {
        if (alertEl) { alertEl.className = 'alert-banner error'; alertEl.textContent = 'Please enter your current password.'; }
        return;
      }
      if (!pwd || pwd.length < 8) {
        if (alertEl) { alertEl.className = 'alert-banner error'; alertEl.textContent = 'Password must be at least 8 characters long.'; }
        return;
      }
      if (btn) btn.disabled = true;
      try {
        var res = await window.ArgusConfig.apiFetch('/api/mobile/employee/credentials', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ current_password: curPwd, new_password: pwd })
        });
        var data = await res.json();
        if (data.success) {
          if (alertEl) { alertEl.className = 'alert-banner success'; alertEl.textContent = data.message || 'Password updated!'; }
          if (curInp) curInp.value = '';
          if (pwdInp) pwdInp.value = '';
          if (curGrp) curGrp.style.display = '';
          var badge = document.getElementById('empPassStatusBadge');
          if (badge) { badge.textContent = '✓ Password Configured'; badge.style.color = '#16a34a'; }
        } else {
          if (alertEl) { alertEl.className = 'alert-banner error'; alertEl.textContent = data.error || 'Failed to save password.'; }
        }
      } catch (err) {
        if (alertEl) { alertEl.className = 'alert-banner error'; alertEl.textContent = 'Network error updating password.'; }
      } finally {
        if (btn) btn.disabled = false;
      }
    }
  }

  window.ArgusEmployeePortal = new EmployeePortalController();
})(window);
