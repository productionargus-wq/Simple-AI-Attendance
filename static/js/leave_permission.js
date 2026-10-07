/**
 * Leave & Permission Management Admin Hub (Image 4)
 * Handles KPIs, Company Policy, Employee Balances, and Request Actions.
 */

document.addEventListener('DOMContentLoaded', function () {
  // Elements
  const companySelect = document.getElementById('leaveCompanySelect');
  const btnRefresh = document.getElementById('btnRefreshLeaveData');

  // Balances Elements
  const btnOpenLeaveBalancesModal = document.getElementById('btnOpenLeaveBalancesModal');
  const modalEmployeeLeaveBalances = document.getElementById('modalEmployeeLeaveBalances');
  const closeLeaveBalancesModalBtn = document.getElementById('closeLeaveBalancesModalBtn');
  const doneLeaveBalancesModalBtn = document.getElementById('doneLeaveBalancesModalBtn');
  const searchBalancesInput = document.getElementById('searchBalancesInput');
  const balancesTbody = document.getElementById('leaveBalancesTbody');

  // Set Employee Quota Modal Elements (Modal 2)
  const modalSetQuota = document.getElementById('modalSetEmployeeLeaveQuota');
  const formSetQuota = document.getElementById('formSetEmployeeLeaveQuota');
  const quotaEmpId = document.getElementById('quotaEmpId');
  const quotaEmpCompanyId = document.getElementById('quotaEmpCompanyId');
  const quotaModalSubtitle = document.getElementById('quotaModalEmpSubtitle');
  const customLeaveRowsContainer = document.getElementById('customLeaveRowsContainer');
  const btnAddLeaveTypeRow = document.getElementById('btnAddLeaveTypeRow');
  const quotaAlertBox = document.getElementById('quotaAlertBox');
  const closeSetQuotaModalBtn = document.getElementById('closeSetQuotaModalBtn');
  const cancelSetQuotaModalBtn = document.getElementById('cancelSetQuotaModalBtn');
  const btnSaveEmployeeQuota = document.getElementById('btnSaveEmployeeQuota');

  // Requests Elements
  const reqFilterTabs = document.querySelectorAll('.req-tab-filter');
  const searchRequestsInput = document.getElementById('searchRequestsInput');
  const requestsTbody = document.getElementById('leaveRequestsTbody');

  // Request Tab Badge Elements
  const badgeReqAll = document.getElementById('badgeReqAll');
  const badgeReqPending = document.getElementById('badgeReqPending');
  const badgeReqApproved = document.getElementById('badgeReqApproved');
  const badgeReqRejected = document.getElementById('badgeReqRejected');

  function updateRequestTabBadges(counts = {}) {
    const allCount = Number(counts.all ?? 0);
    const pendingCount = Number(counts.pending ?? 0);
    const approvedCount = Number(counts.approved ?? 0);
    const rejectedCount = Number(counts.rejected ?? 0);

    if (badgeReqAll) {
      badgeReqAll.textContent = allCount;
      badgeReqAll.style.display = allCount > 0 ? 'inline-flex' : 'none';
    }
    if (badgeReqPending) {
      badgeReqPending.textContent = pendingCount;
      badgeReqPending.style.display = pendingCount > 0 ? 'inline-flex' : 'none';
    }
    if (badgeReqApproved) {
      badgeReqApproved.textContent = approvedCount;
      badgeReqApproved.style.display = approvedCount > 0 ? 'inline-flex' : 'none';
    }
    if (badgeReqRejected) {
      badgeReqRejected.textContent = rejectedCount;
      badgeReqRejected.style.display = rejectedCount > 0 ? 'inline-flex' : 'none';
    }
  }

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

  // Hook up Modal 1 (Employee Leave Balances & Quotas)
  function openLeaveBalancesModal() {
    if (modalEmployeeLeaveBalances) {
      modalEmployeeLeaveBalances.style.display = 'flex';
      loadBalances();
    }
  }

  function closeLeaveBalancesModal() {
    if (modalEmployeeLeaveBalances) {
      modalEmployeeLeaveBalances.style.display = 'none';
    }
  }

  if (btnOpenLeaveBalancesModal) btnOpenLeaveBalancesModal.addEventListener('click', openLeaveBalancesModal);
  if (closeLeaveBalancesModalBtn) closeLeaveBalancesModalBtn.addEventListener('click', closeLeaveBalancesModal);
  if (doneLeaveBalancesModalBtn) doneLeaveBalancesModalBtn.addEventListener('click', closeLeaveBalancesModal);

  // 1. Fetch & Update Sidebar Badge Stats (if present)
  async function loadStats() {
    try {
      const compId = getSelectedCompanyId();
      const url = `/api/admin/leave-permission/stats${compId ? '?company_id=' + encodeURIComponent(compId) : ''}`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      if (!data.success) return;

      const s = data.stats || {};
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

  // 2. Fetch & Render Employee Balances
  async function loadBalances() {
    if (!balancesTbody) return;
    try {
      const compId = getSelectedCompanyId();
      const url = `/api/admin/leave-permission/balances${compId ? '?company_id=' + encodeURIComponent(compId) : ''}`;
      const res = await fetch(url);
      if (!res.ok) {
        balancesTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: #dc2626;">Failed to load employee balances.</td></tr>`;
        return;
      }
      const data = await res.json();
      if (!data.success) return;

      cachedBalances = data.balances || [];
      renderBalancesTable();
    } catch (err) {
      console.error('Error fetching balances:', err);
      balancesTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: #dc2626;">Error loading balances.</td></tr>`;
    }
  }

  function renderBalancesTable() {
    if (!balancesTbody) return;
    const query = (searchBalancesInput ? searchBalancesInput.value : '').toLowerCase().trim();

    const filtered = cachedBalances.filter(b => {
      if (!query) return true;
      const idMatch = (b.employee_id || '').toLowerCase().includes(query);
      const nameMatch = (b.employee_name || '').toLowerCase().includes(query);
      const deptMatch = (b.department || '').toLowerCase().includes(query);
      return idMatch || nameMatch || deptMatch;
    });

    if (filtered.length === 0) {
      balancesTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 22px; color: #94a3b8; font-size: 12.5px;">No employee balance records found.</td></tr>`;
      return;
    }

    balancesTbody.innerHTML = filtered.map(b => {
      const empId = b.id || b.employee_id || '';
      const empCode = b.employee_id || b.id || '';
      const empName = b.employee_name || '';
      const dept = b.department || 'General';
      const compId = b.company_id || '';

      const customLeaves = Array.isArray(b.custom_leaves) ? b.custom_leaves : [];
      let leavesHtml = '';

      if (customLeaves.length === 0) {
        leavesHtml = `<span style="color: #94a3b8; font-size: 11.5px; font-style: italic;">No leaves configured</span>`;
      } else {
        const badgeColors = [
          { bg: '#eff6ff', color: '#1d4ed8', border: '#bfdbfe' },
          { bg: '#f0fdf4', color: '#15803d', border: '#bbf7d0' },
          { bg: '#fefce8', color: '#a16207', border: '#fef08a' },
          { bg: '#faf5ff', color: '#7e22ce', border: '#e9d5ff' },
          { bg: '#fff1f2', color: '#be123c', border: '#fecdd3' },
          { bg: '#ecfeff', color: '#0e7490', border: '#a5f3fc' },
        ];
        leavesHtml = customLeaves.map((lv, idx) => {
          const st = badgeColors[idx % badgeColors.length];
          const avail = lv.available !== undefined ? lv.available : lv.total;
          const tot = lv.total ?? 0;
          const unitShort = (lv.unit || 'Days').toLowerCase() === 'hours' ? 'Hrs' : 'Days';
          return `<span style="display: inline-block; padding: 2.5px 8px; margin: 2px 5px 2px 0; border-radius: 12px; font-size: 11px; font-weight: 700; background: ${st.bg}; color: ${st.color}; border: 1px solid ${st.border}; white-space: nowrap;">
            ${escapeHtml(lv.name)}: ${avail} / ${tot} ${unitShort}
          </span>`;
        }).join('');
      }

      return `
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 10px 14px; font-size: 12px; font-weight: 700; color: #0f172a;">${escapeHtml(empCode)}</td>
          <td style="padding: 10px 14px; font-size: 12px; font-weight: 600; color: #334155;">${escapeHtml(empName)}</td>
          <td style="padding: 10px 14px; font-size: 12px; font-weight: 500; color: #64748b;">${escapeHtml(dept)}</td>
          <td style="padding: 10px 14px; font-size: 12px;">
            ${leavesHtml}
          </td>
          <td style="padding: 10px 14px; text-align: center;">
            <button type="button" class="btn-set-quota" 
              data-id="${escapeHtml(empId)}" 
              data-name="${escapeHtml(empName)}" 
              data-comp="${escapeHtml(compId)}"
              style="display: inline-flex; align-items: center; justify-content: center; padding: 5px 16px; border-radius: 6px; font-size: 11.5px; font-weight: 700; background: #0284c7; color: #ffffff; border: none; cursor: pointer; transition: all 0.15s ease;">
              Set
            </button>
          </td>
        </tr>
      `;
    }).join('');
  }

  // Handle click on "Set" button via delegation
  if (balancesTbody) {
    balancesTbody.addEventListener('click', function (e) {
      const btn = e.target.closest('.btn-set-quota');
      if (!btn) return;
      const empId = btn.getAttribute('data-id');
      const empName = btn.getAttribute('data-name');
      const comp = btn.getAttribute('data-comp') || '';

      const empData = cachedBalances.find(b => String(b.id || b.employee_id) === String(empId)) || {
        id: empId,
        employee_id: empId,
        employee_name: empName,
        company_id: comp,
        custom_leaves: []
      };

      openSetQuotaModal(empData);
    });
  }

  // Row builder for Custom Leave Form (Modal 2)
  function createCustomLeaveRow(name = '', total = '', unit = 'Days') {
    const row = document.createElement('div');
    row.className = 'custom-leave-row';
    row.style.cssText = 'display: grid; grid-template-columns: 1fr 105px 95px 36px; gap: 8px; align-items: center; background: #f8fafc; padding: 8px 10px; border-radius: 6px; border: 1px solid #e2e8f0;';

    row.innerHTML = `
      <div>
        <input type="text" class="custom-leave-name" placeholder="Leave Name (e.g. Medical Leave)" value="${escapeHtml(name)}" style="width: 100%; box-sizing: border-box; padding: 7px 10px; border-radius: 6px; border: 1.5px solid #cbd5e1; font-size: 12.5px; font-weight: 600;" required>
      </div>
      <div>
        <input type="number" step="0.5" min="0" max="365" class="custom-leave-total" placeholder="Quota" value="${total !== '' ? total : ''}" style="width: 100%; box-sizing: border-box; padding: 7px 10px; border-radius: 6px; border: 1.5px solid #cbd5e1; font-size: 12.5px; font-weight: 700;" required>
      </div>
      <div>
        <select class="custom-leave-unit" style="width: 100%; box-sizing: border-box; padding: 7px 6px; border-radius: 6px; border: 1.5px solid #cbd5e1; font-size: 12px; font-weight: 600; background: #ffffff;">
          <option value="Days" ${unit === 'Days' ? 'selected' : ''}>Days</option>
          <option value="Hours" ${unit === 'Hours' ? 'selected' : ''}>Hours</option>
        </select>
      </div>
      <div style="text-align: center;">
        <button type="button" class="btn-remove-leave-row" title="Remove" style="background: none; border: none; color: #ef4444; font-size: 20px; font-weight: 700; cursor: pointer; padding: 0; line-height: 1;">
          &times;
        </button>
      </div>
    `;

    const removeBtn = row.querySelector('.btn-remove-leave-row');
    removeBtn.addEventListener('click', () => {
      row.remove();
      if (customLeaveRowsContainer && customLeaveRowsContainer.children.length === 0) {
        customLeaveRowsContainer.appendChild(createCustomLeaveRow('', '', 'Days'));
      }
    });

    return row;
  }

  if (btnAddLeaveTypeRow) {
    btnAddLeaveTypeRow.addEventListener('click', () => {
      if (customLeaveRowsContainer) {
        const newRow = createCustomLeaveRow('', '', 'Days');
        customLeaveRowsContainer.appendChild(newRow);
        const nameInput = newRow.querySelector('.custom-leave-name');
        if (nameInput) nameInput.focus();
      }
    });
  }

  function openSetQuotaModal(data) {
    if (!modalSetQuota) return;
    if (quotaEmpId) quotaEmpId.value = data.id || data.employee_id || '';
    if (quotaEmpCompanyId) quotaEmpCompanyId.value = data.company_id || getSelectedCompanyId() || '';
    if (quotaModalSubtitle) {
      quotaModalSubtitle.textContent = `Configuring: ${data.employee_name || 'Employee'} (ID: ${data.employee_id || data.id || ''})`;
    }

    if (customLeaveRowsContainer) {
      customLeaveRowsContainer.innerHTML = '';
      const leaves = Array.isArray(data.custom_leaves) ? data.custom_leaves : [];
      if (leaves.length > 0) {
        leaves.forEach(lv => {
          customLeaveRowsContainer.appendChild(createCustomLeaveRow(lv.name, lv.total, lv.unit || 'Days'));
        });
      } else {
        // Starter blank row
        customLeaveRowsContainer.appendChild(createCustomLeaveRow('', '', 'Days'));
      }
    }

    if (quotaAlertBox) {
      quotaAlertBox.style.display = 'none';
      quotaAlertBox.textContent = '';
    }
    modalSetQuota.style.display = 'flex';
  }

  function closeSetQuotaModal() {
    if (modalSetQuota) modalSetQuota.style.display = 'none';
  }

  if (closeSetQuotaModalBtn) closeSetQuotaModalBtn.addEventListener('click', closeSetQuotaModal);
  if (cancelSetQuotaModalBtn) cancelSetQuotaModalBtn.addEventListener('click', closeSetQuotaModal);

  // Submit Handler for Set Quota Form
  if (formSetQuota) {
    formSetQuota.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (!btnSaveEmployeeQuota) return;

      const rows = customLeaveRowsContainer ? customLeaveRowsContainer.querySelectorAll('.custom-leave-row') : [];
      const custom_leaves = [];
      rows.forEach(r => {
        const nameInput = r.querySelector('.custom-leave-name');
        const totalInput = r.querySelector('.custom-leave-total');
        const unitInput = r.querySelector('.custom-leave-unit');
        const name = nameInput ? nameInput.value.trim() : '';
        const total = totalInput ? (parseFloat(totalInput.value) || 0) : 0;
        const unit = unitInput ? (unitInput.value || 'Days') : 'Days';
        if (name) {
          custom_leaves.push({ name, total, unit });
        }
      });

      btnSaveEmployeeQuota.disabled = true;
      const origText = btnSaveEmployeeQuota.innerHTML;
      btnSaveEmployeeQuota.innerHTML = `Saving...`;

      try {
        const payload = {
          employee_id: quotaEmpId ? quotaEmpId.value : '',
          company_id: quotaEmpCompanyId ? quotaEmpCompanyId.value : getSelectedCompanyId(),
          custom_leaves: custom_leaves
        };

        const res = await fetch('/api/admin/leave-permission/employee-custom-leaves', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          if (quotaAlertBox) {
            quotaAlertBox.style.display = 'block';
            quotaAlertBox.style.backgroundColor = '#ecfdf5';
            quotaAlertBox.style.color = '#065f46';
            quotaAlertBox.style.border = '1px solid #a7f3d0';
            quotaAlertBox.textContent = data.message || 'Custom leaves saved successfully!';
          }
          await loadBalances();
          setTimeout(() => {
            closeSetQuotaModal();
          }, 600);
        } else {
          if (quotaAlertBox) {
            quotaAlertBox.style.display = 'block';
            quotaAlertBox.style.backgroundColor = '#fef2f2';
            quotaAlertBox.style.color = '#991b1b';
            quotaAlertBox.style.border = '1px solid #fecaca';
            quotaAlertBox.textContent = data.error || 'Failed to update custom leaves.';
          }
        }
      } catch (err) {
        if (quotaAlertBox) {
          quotaAlertBox.style.display = 'block';
          quotaAlertBox.style.backgroundColor = '#fef2f2';
          quotaAlertBox.style.color = '#991b1b';
          quotaAlertBox.style.border = '1px solid #fecaca';
          quotaAlertBox.textContent = 'Error: ' + err.message;
        }
      } finally {
        btnSaveEmployeeQuota.disabled = false;
        btnSaveEmployeeQuota.innerHTML = origText;
      }
    });
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
      if (data.status_counts) {
        updateRequestTabBadges(data.status_counts);
      } else if (!currentStatusFilter && Array.isArray(cachedRequests)) {
        updateRequestTabBadges({
          all: cachedRequests.length,
          pending: cachedRequests.filter(r => (r.status || '').toLowerCase() === 'pending').length,
          approved: cachedRequests.filter(r => (r.status || '').toLowerCase() === 'approved').length,
          rejected: cachedRequests.filter(r => (r.status || '').toLowerCase() === 'rejected').length
        });
      }
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

      const badgeCls = st === 'approved' ? 'badge-status-approved' : (st === 'rejected' ? 'badge-status-rejected' : 'badge-status-pending');
      if (remark) {
        statusBadge = `
          <div style="display: inline-flex; flex-direction: column; align-items: center; gap: 3px; max-width: 200px;">
            <span class="${badgeCls}" style="font-size: 11px; padding: 2.5px 8px; border-radius: 5px; font-weight: 700; display: inline-block;">${escapeHtml(statusLabel)}</span>
            <span style="font-size: 10.5px; color: #475569; line-height: 1.3; font-weight: 500; word-break: break-word;" title="${escapeHtml(remark)}">${escapeHtml(remark)}</span>
          </div>
        `;
      } else {
        statusBadge = `<span class="${badgeCls}" style="font-size: 11px; padding: 2.5px 8px; border-radius: 5px; font-weight: 700; display: inline-block;">${escapeHtml(statusLabel)}</span>`;
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
          <td style="padding: 10px 14px; text-align: center; font-size: 11px;">${statusBadge}</td>
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
