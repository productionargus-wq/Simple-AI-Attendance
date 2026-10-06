/**
 * Leave & Permission Management Admin Hub (Image 4)
 * Handles KPIs, Company Policy, Employee Balances, and Request Actions.
 */

document.addEventListener('DOMContentLoaded', function () {
  // Elements
  const companySelect = document.getElementById('leaveCompanySelect');
  const btnRefresh = document.getElementById('btnRefreshLeaveData');

  // KPI Elements
  const kpiPending = document.getElementById('kpiPendingCount');
  const kpiApproved = document.getElementById('kpiApprovedCount');
  const kpiRejected = document.getElementById('kpiRejectedCount');
  const kpiLowBal = document.getElementById('kpiLowBalCount');

  // Policy Elements
  const formPolicy = document.getElementById('formLeavePolicy');
  const btnSavePolicy = document.getElementById('btnSavePolicy');
  const policyCL = document.getElementById('policyCL');
  const policySL = document.getElementById('policySL');
  const policyEL = document.getElementById('policyEL');
  const policyPermHours = document.getElementById('policyPermHours');
  const policyAlert = document.getElementById('policyAlert');

  // Balances Elements
  const searchBalancesInput = document.getElementById('searchBalancesInput');
  const balancesTbody = document.getElementById('leaveBalancesTbody');

  // Requests Elements
  const reqFilterTabs = document.querySelectorAll('.req-tab-filter');
  const searchRequestsInput = document.getElementById('searchRequestsInput');
  const requestsTbody = document.getElementById('leaveRequestsTbody');

  // Quick Reject Modal
  const modalQuickReject = document.getElementById('modalQuickReject');
  const quickRejectReqId = document.getElementById('quickRejectReqId');
  const quickRejectRemark = document.getElementById('quickRejectRemark');
  const confirmQuickRejectBtn = document.getElementById('confirmQuickRejectBtn');
  const cancelQuickRejectBtn = document.getElementById('cancelQuickRejectBtn');
  const closeQuickRejectBtn = document.getElementById('closeQuickRejectBtn');

  let currentStatusFilter = '';
  let cachedBalances = [];
  let cachedRequests = [];

  function getSelectedCompanyId() {
    return companySelect ? (companySelect.value || '') : '';
  }

  // 1. Fetch & Update KPI Stats
  async function loadStats() {
    try {
      const compId = getSelectedCompanyId();
      const url = `/api/admin/leave-permission/stats${compId ? '?company_id=' + encodeURIComponent(compId) : ''}`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      if (!data.success) return;

      const s = data.stats || {};
      if (kpiPending) kpiPending.textContent = s.pending_count ?? 0;
      if (kpiApproved) kpiApproved.textContent = s.approved_today ?? 0;
      if (kpiRejected) kpiRejected.textContent = s.rejected_count ?? 0;
      if (kpiLowBal) kpiLowBal.textContent = s.low_balance_count ?? 0;

      const sbBadge = document.getElementById('sidebarLeaveBadge');
      if (sbBadge) {
        const pc = s.pending_count ?? 0;
        sbBadge.textContent = pc;
        sbBadge.style.display = pc > 0 ? 'inline-flex' : 'none';
      }
    } catch (err) {
      console.error('Error loading leave stats:', err);
    }
  }

  // 2. Fetch & Populate Policy
  async function loadPolicy() {
    try {
      const compId = getSelectedCompanyId();
      const url = `/api/admin/leave-permission/policy${compId ? '?company_id=' + encodeURIComponent(compId) : ''}`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      if (!data.success || !data.policy) return;

      const p = data.policy;
      if (policyCL) policyCL.value = p.casual_leave_annual ?? 12;
      if (policySL) policySL.value = p.sick_leave_annual ?? 12;
      if (policyEL) policyEL.value = p.earned_leave_annual ?? 12;
      if (policyPermHours) policyPermHours.value = p.permission_hours_monthly ?? 16;
      renderBalancesTable();
    } catch (err) {
      console.error('Error loading leave policy:', err);
    }
  }

  // Save Policy
  if (btnSavePolicy) {
    btnSavePolicy.addEventListener('click', async function (e) {
      e.preventDefault();
      btnSavePolicy.disabled = true;

      const compId = getSelectedCompanyId();
      const payload = {
        company_id: compId,
        casual_leave_annual: parseInt(policyCL.value) || 0,
        sick_leave_annual: parseInt(policySL.value) || 0,
        earned_leave_annual: parseInt(policyEL.value) || 0,
        permission_hours_monthly: parseInt(policyPermHours.value) || 0
      };

      try {
        const url = `/api/admin/leave-permission/policy${compId ? '?company_id=' + encodeURIComponent(compId) : ''}`;
        const res = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showPolicyAlert(data.message || 'Leave policy saved and persisted successfully!', 'success');
          if (data.policy) {
            if (policyCL) policyCL.value = data.policy.casual_leave_annual ?? policyCL.value;
            if (policySL) policySL.value = data.policy.sick_leave_annual ?? policySL.value;
            if (policyEL) policyEL.value = data.policy.earned_leave_annual ?? policyEL.value;
            if (policyPermHours) policyPermHours.value = data.policy.permission_hours_monthly ?? policyPermHours.value;
          }
          await loadBalances();
        } else {
          showPolicyAlert(data.error || 'Failed to save leave policy.', 'error');
        }
      } catch (err) {
        showPolicyAlert('Error saving policy: ' + err.message, 'error');
      } finally {
        btnSavePolicy.disabled = false;
      }
    });
  }

  // Live dynamic update of Employee Leave Balances as policy inputs change
  [policyCL, policySL, policyEL, policyPermHours].forEach(input => {
    if (input) {
      input.addEventListener('input', () => {
        renderBalancesTable();
      });
      input.addEventListener('change', () => {
        renderBalancesTable();
      });
    }
  });

  function showPolicyAlert(msg, type) {
    if (!policyAlert) return;
    policyAlert.style.display = 'block';
    if (type === 'success') {
      policyAlert.style.backgroundColor = '#ecfdf5';
      policyAlert.style.color = '#065f46';
      policyAlert.style.border = '1px solid #a7f3d0';
    } else {
      policyAlert.style.backgroundColor = '#fef2f2';
      policyAlert.style.color = '#991b1b';
      policyAlert.style.border = '1px solid #fecaca';
    }
    policyAlert.textContent = msg;
    setTimeout(() => {
      policyAlert.style.display = 'none';
    }, 4000);
  }

  // 3. Fetch & Render Employee Balances
  async function loadBalances() {
    if (!balancesTbody) return;
    try {
      const compId = getSelectedCompanyId();
      const url = `/api/admin/leave-permission/balances${compId ? '?company_id=' + encodeURIComponent(compId) : ''}`;
      const res = await fetch(url);
      if (!res.ok) {
        balancesTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 20px; color: #dc2626;">Failed to load employee balances.</td></tr>`;
        return;
      }
      const data = await res.json();
      if (!data.success) return;

      cachedBalances = data.balances || [];
      renderBalancesTable();
    } catch (err) {
      console.error('Error fetching balances:', err);
      balancesTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 20px; color: #dc2626;">Error loading balances.</td></tr>`;
    }
  }

  function renderBalancesTable() {
    if (!balancesTbody) return;
    const query = (searchBalancesInput ? searchBalancesInput.value : '').toLowerCase().trim();

    const filtered = cachedBalances.filter(b => {
      if (!query) return true;
      const idMatch = (b.employee_id || '').toLowerCase().includes(query);
      const nameMatch = (b.employee_name || '').toLowerCase().includes(query);
      return idMatch || nameMatch;
    });

    if (filtered.length === 0) {
      balancesTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 22px; color: #94a3b8; font-size: 12.5px;">No employee balance records found.</td></tr>`;
      return;
    }

    // Read live policy inputs if present
    const liveCL = policyCL && policyCL.value !== '' ? parseInt(policyCL.value) : null;
    const liveSL = policySL && policySL.value !== '' ? parseInt(policySL.value) : null;
    const liveEL = policyEL && policyEL.value !== '' ? parseInt(policyEL.value) : null;
    const livePerm = policyPermHours && policyPermHours.value !== '' ? parseInt(policyPermHours.value) : null;

    balancesTbody.innerHTML = filtered.map(b => {
      const clUsed = Number(b.casual_leave_used || 0);
      const slUsed = Number(b.sick_leave_used || 0);
      const elUsed = Number(b.earned_leave_used || 0);
      const permUsed = Number(b.permission_hours_used || 0);

      const clTot = liveCL !== null && !isNaN(liveCL) ? liveCL : (b.casual_leave_total || 12);
      const slTot = liveSL !== null && !isNaN(liveSL) ? liveSL : (b.sick_leave_total || 12);
      const elTot = liveEL !== null && !isNaN(liveEL) ? liveEL : (b.earned_leave_total || 18);
      const permTot = livePerm !== null && !isNaN(livePerm) ? livePerm : (b.permission_hours_total || 16);

      const clAvail = Math.max(0, clTot - clUsed);
      const slAvail = Math.max(0, slTot - slUsed);
      const elAvail = Math.max(0, elTot - elUsed);
      const permAvail = Math.max(0, permTot - permUsed);

      return `
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 10px 14px; font-size: 12px; font-weight: 700; color: #0f172a;">${escapeHtml(b.employee_id)}</td>
          <td style="padding: 10px 14px; font-size: 12px; font-weight: 600; color: #334155;">${escapeHtml(b.employee_name)}</td>
          <td style="padding: 10px 14px; text-align: center;">
            <span class="badge-bal-blue">${clAvail} / ${clTot} Days</span>
          </td>
          <td style="padding: 10px 14px; text-align: center;">
            <span class="badge-bal-green">${slAvail} / ${slTot} Days</span>
          </td>
          <td style="padding: 10px 14px; text-align: center;">
            <span class="badge-bal-yellow">${elAvail} / ${elTot} Days</span>
          </td>
          <td style="padding: 10px 14px; text-align: center;">
            <span style="display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 700; background: #f3e8ff; color: #7e22ce;">
              ${permAvail} / ${permTot} Hrs
            </span>
          </td>
        </tr>
      `;
    }).join('');
  }

  if (searchBalancesInput) {
    searchBalancesInput.addEventListener('input', renderBalancesTable);
  }

  // 4. Fetch & Render Leave Requests
  async function loadRequests() {
    if (!requestsTbody) return;
    try {
      const compId = getSelectedCompanyId();
      let url = `/api/admin/leave-permission/requests?limit=100`;
      if (compId) url += `&company_id=${encodeURIComponent(compId)}`;
      if (currentStatusFilter) url += `&status=${encodeURIComponent(currentStatusFilter)}`;

      const res = await fetch(url);
      if (!res.ok) {
        requestsTbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 20px; color: #dc2626;">Failed to load leave requests.</td></tr>`;
        return;
      }
      const data = await res.json();
      if (!data.success) return;

      cachedRequests = data.requests || [];
      renderRequestsTable();
    } catch (err) {
      console.error('Error fetching requests:', err);
      requestsTbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 20px; color: #dc2626;">Error loading requests.</td></tr>`;
    }
  }

  function renderRequestsTable() {
    if (!requestsTbody) return;
    const query = (searchRequestsInput ? searchRequestsInput.value : '').toLowerCase().trim();

    const filtered = cachedRequests.filter(r => {
      if (currentStatusFilter && (r.status || '').toLowerCase() !== currentStatusFilter.toLowerCase()) {
        return false;
      }
      if (!query) return true;
      const empMatch = (r.employee_name || '').toLowerCase().includes(query);
      const idMatch = (r.employee_id || '').toLowerCase().includes(query);
      const reqIdMatch = (r.request_id || '').toLowerCase().includes(query);
      const reasonMatch = (r.reason || '').toLowerCase().includes(query);
      return empMatch || idMatch || reqIdMatch || reasonMatch;
    });

    if (filtered.length === 0) {
      requestsTbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 24px; color: #94a3b8; font-size: 12.5px;">No requests found matching criteria.</td></tr>`;
      return;
    }

    requestsTbody.innerHTML = filtered.map((r, idx) => {
      let typeBadge = '';
      if (r.request_type === 'Permission') {
        typeBadge = `<span class="badge-type-perm">Permission</span>`;
      } else {
        const shortType = r.leave_type ? r.leave_type.split(' ')[0] : 'Leave';
        typeBadge = `<span class="badge-type-leave">${escapeHtml(shortType)}</span>`;
      }

      let statusBadge = '';
      const st = (r.status || 'Pending').toLowerCase();
      const statusLabel = r.status || (st === 'approved' ? 'Approved' : (st === 'rejected' ? 'Rejected' : 'Pending'));
      const remark = (r.admin_remark || '').trim();
      const displayStatus = remark ? `${statusLabel} - ${remark}` : statusLabel;

      if (st === 'approved') {
        statusBadge = `<span class="badge-status-approved" style="white-space: normal; line-height: 1.35; display: inline-block; text-align: center; max-width: 220px;" title="${escapeHtml(displayStatus)}">${escapeHtml(displayStatus)}</span>`;
      } else if (st === 'rejected') {
        statusBadge = `<span class="badge-status-rejected" style="white-space: normal; line-height: 1.35; display: inline-block; text-align: center; max-width: 220px;" title="${escapeHtml(displayStatus)}">${escapeHtml(displayStatus)}</span>`;
      } else {
        statusBadge = `<span class="badge-status-pending" style="white-space: normal; line-height: 1.35; display: inline-block; text-align: center; max-width: 220px;" title="${escapeHtml(displayStatus)}">${escapeHtml(displayStatus)}</span>`;
      }

      // Date / Period string
      let datePeriod = '';
      if (r.request_type === 'Permission') {
        datePeriod = `<strong>${escapeHtml(r.date || '-')}</strong><br><span style="font-size: 11px; color: #64748b;">${escapeHtml(r.from_time || '')} - ${escapeHtml(r.to_time || '')} (${escapeHtml(r.duration || '')})</span>`;
      } else {
        const fromDate = r.from_date || '-';
        const toDate = r.to_date || fromDate;
        if (r.session === 'Hourly') {
          const durLabel = r.leave_duration || (r.duration_hours ? r.duration_hours + ' Hrs' : '-');
          datePeriod = `<strong>${escapeHtml(fromDate)}</strong>${toDate !== fromDate ? ' to <strong>' + escapeHtml(toDate) + '</strong>' : ''}<br><span style="font-size: 11px; color: #0284c7; font-weight: 700;">${escapeHtml(durLabel)} (Hourly)</span>`;
        } else {
          const count = `${r.days_count || 1} Day${(r.days_count && r.days_count > 1) ? 's' : ''}`;
          datePeriod = `<strong>${escapeHtml(fromDate)}</strong>${toDate !== fromDate ? ' to <strong>' + escapeHtml(toDate) + '</strong>' : ''}<br><span style="font-size: 11px; color: #0284c7; font-weight: 700;">${count} (${escapeHtml(r.session || 'Full Day')})</span>`;
        }
      }

      // Attachment button
      let attCol = `<span style="color: #cbd5e1;">-</span>`;
      const attUrl = (r.attachments && r.attachments.length > 0) ? r.attachments[0].file_url : r.attachment_url;
      if (attUrl) {
        attCol = `
          <a href="${escapeHtml(attUrl)}" target="_blank" title="View Document" style="display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 6px; background: #e0f2fe; color: #0284c7; text-decoration: none;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
              <polyline points="14 2 14 8 20 8"></polyline>
            </svg>
          </a>
        `;
      }

      // Quick Actions
      let actionButtons = `
        <div style="display: flex; align-items: center; justify-content: center; gap: 6px;">
          <a href="/leave-permission/review/${r.request_id}" class="btn-action-view" title="Review Details" style="text-decoration: none; display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 6px; background: #f1f5f9; color: #475569;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
          </a>
      `;

      if (st === 'pending') {
        actionButtons += `
          <button type="button" class="btn-quick-approve" data-id="${r.request_id}" title="Quick Approve" style="border: none; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 6px; background: #dcfce7; color: #16a34a;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
          </button>
          <button type="button" class="btn-quick-reject" data-id="${r.request_id}" title="Quick Reject" style="border: none; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 6px; background: #fee2e2; color: #dc2626;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        `;
      }

      actionButtons += `</div>`;

      return `
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 10px 14px; text-align: center; font-size: 11.5px; color: #64748b; font-weight: 600;">${idx + 1}</td>
          <td style="padding: 10px 14px; font-size: 12px;">${typeBadge}</td>
          <td style="padding: 10px 14px; font-size: 12px;">
            <strong style="color: #0f172a;">${escapeHtml(r.employee_name)}</strong><br>
            <span style="font-size: 11px; color: #64748b;">ID: ${escapeHtml(r.employee_id)}</span>
          </td>
          <td style="padding: 10px 14px; font-size: 12px;">${datePeriod}</td>
          <td style="padding: 10px 14px; font-size: 12px; max-width: 220px; white-space: normal; line-height: 1.4; color: #334155;">
            ${escapeHtml(r.reason || '-')}
          </td>
          <td style="padding: 10px 14px; text-align: center;">${attCol}</td>
          <td style="padding: 10px 14px; text-align: center;">${statusBadge}</td>
          <td style="padding: 10px 14px; text-align: center;">${actionButtons}</td>
        </tr>
      `;
    }).join('');

    attachQuickActionHandlers();
  }

  function attachQuickActionHandlers() {
    // Quick Approve
    document.querySelectorAll('.btn-quick-approve').forEach(btn => {
      btn.addEventListener('click', async function () {
        const reqId = this.getAttribute('data-id');
        if (!confirm(`Are you sure you want to approve request ${reqId}?`)) return;

        this.disabled = true;
        try {
          const res = await fetch(`/api/admin/leave-permission/requests/${reqId}/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'Approve', admin_remark: 'Approved via quick action' })
          });
          const data = await res.json();
          if (data.success) {
            refreshAllData();
          } else {
            alert(data.error || 'Failed to approve request.');
          }
        } catch (err) {
          console.error(err);
          alert('Error approving request.');
        } finally {
          this.disabled = false;
        }
      });
    });

    // Quick Reject (Opens modal)
    document.querySelectorAll('.btn-quick-reject').forEach(btn => {
      btn.addEventListener('click', function () {
        const reqId = this.getAttribute('data-id');
        if (quickRejectReqId) quickRejectReqId.value = reqId;
        if (quickRejectRemark) quickRejectRemark.value = '';
        if (modalQuickReject) modalQuickReject.style.display = 'flex';
      });
    });
  }

  // Quick Reject Modal Handlers
  if (closeQuickRejectBtn && modalQuickReject) {
    closeQuickRejectBtn.addEventListener('click', () => { modalQuickReject.style.display = 'none'; });
  }
  if (cancelQuickRejectBtn && modalQuickReject) {
    cancelQuickRejectBtn.addEventListener('click', () => { modalQuickReject.style.display = 'none'; });
  }

  if (confirmQuickRejectBtn) {
    confirmQuickRejectBtn.addEventListener('click', async function () {
      const reqId = quickRejectReqId ? quickRejectReqId.value : '';
      const remark = quickRejectRemark ? quickRejectRemark.value.trim() : '';

      if (!reqId) return;
      confirmQuickRejectBtn.disabled = true;

      try {
        const res = await fetch(`/api/admin/leave-permission/requests/${reqId}/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'Reject', admin_remark: remark })
        });
        const data = await res.json();
        if (data.success) {
          if (modalQuickReject) modalQuickReject.style.display = 'none';
          refreshAllData();
        } else {
          alert(data.error || 'Failed to reject request.');
        }
      } catch (err) {
        console.error(err);
        alert('Error rejecting request.');
      } finally {
        confirmQuickRejectBtn.disabled = false;
      }
    });
  }

  // Filter Tabs Handler
  reqFilterTabs.forEach(tab => {
    tab.addEventListener('click', function () {
      reqFilterTabs.forEach(t => t.classList.remove('active'));
      this.classList.add('active');
      currentStatusFilter = this.getAttribute('data-status') || '';
      loadRequests();
    });
  });

  if (searchRequestsInput) {
    searchRequestsInput.addEventListener('input', renderRequestsTable);
  }

  // Refresh All Data
  async function refreshAllData() {
    if (btnRefresh) {
      btnRefresh.disabled = true;
      btnRefresh.innerHTML = `
        <svg class="spin-anim" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="23 4 23 10 17 10"></polyline>
          <polyline points="1 20 1 14 7 14"></polyline>
          <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
        </svg>
        Refreshing...
      `;
    }

    try {
      await Promise.all([
        loadStats(),
        loadPolicy(),
        loadBalances(),
        loadRequests()
      ]);
    } catch (err) {
      console.error('Error refreshing leave data:', err);
    } finally {
      if (btnRefresh) {
        btnRefresh.disabled = false;
        btnRefresh.innerHTML = `
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="23 4 23 10 17 10"></polyline>
            <polyline points="1 20 1 14 7 14"></polyline>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
          Refresh
        `;
      }
    }
  }

  if (btnRefresh) {
    btnRefresh.addEventListener('click', refreshAllData);
  }

  if (companySelect) {
    companySelect.addEventListener('change', refreshAllData);
  }

  function escapeHtml(text) {
    if (!text) return '';
    return String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // Initial load
  refreshAllData();
});
