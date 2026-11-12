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
    if (window.renderTableLoading) {
      window.renderTableLoading(balancesTbody, "Loading leave balances...", 5);
    }
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
          <td class="sticky-col-emp" style="padding: 10px 14px; font-size: 12px; font-weight: 600; color: #334155;">${escapeHtml(empName)}</td>
          <td style="padding: 10px 14px; font-size: 12px; font-weight: 500; color: #64748b;">${escapeHtml(dept)}</td>
          <td style="padding: 10px 14px; font-size: 12px;">
            ${leavesHtml}
          </td>
          <td style="padding: 10px 14px; text-align: center;">
            <div style="display: inline-flex; align-items: center; justify-content: center; gap: 6px;">
              <button type="button" class="btn-set-quota" 
                data-id="${escapeHtml(empId)}" 
                data-name="${escapeHtml(empName)}" 
                data-comp="${escapeHtml(compId)}"
                style="display: inline-flex; align-items: center; justify-content: center; padding: 5px 11px; border-radius: 6px; font-size: 11.5px; font-weight: 700; background: #0284c7; color: #ffffff; border: none; cursor: pointer; transition: all 0.15s ease;">
                Edit
              </button>
              <button type="button" class="btn-del-emp-leaves" 
                data-id="${escapeHtml(empId)}" 
                data-name="${escapeHtml(empName)}" 
                data-comp="${escapeHtml(compId)}"
                style="display: inline-flex; align-items: center; justify-content: center; padding: 5px 10px; border-radius: 6px; font-size: 11.5px; font-weight: 700; background: #fee2e2; color: #dc2626; border: 1px solid #fecaca; cursor: pointer; transition: all 0.15s ease;">
                Delete
              </button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  // Handle click on "Edit" or "Delete" button via delegation
  if (balancesTbody) {
    balancesTbody.addEventListener('click', async function (e) {
      const editBtn = e.target.closest('.btn-set-quota');
      if (editBtn) {
        const empId = editBtn.getAttribute('data-id');
        const empName = editBtn.getAttribute('data-name');
        const comp = editBtn.getAttribute('data-comp') || '';

        const empData = cachedBalances.find(b => String(b.id || b.employee_id) === String(empId)) || {
          id: empId,
          employee_id: empId,
          employee_name: empName,
          company_id: comp,
          custom_leaves: []
        };

        openSetQuotaModal(empData);
        return;
      }

      const delBtn = e.target.closest('.btn-del-emp-leaves');
      if (delBtn) {
        const empId = delBtn.getAttribute('data-id');
        const empName = delBtn.getAttribute('data-name') || 'this employee';
        const comp = delBtn.getAttribute('data-comp') || getSelectedCompanyId() || '';
        if (!confirm(`Delete all custom leave & permission quotas configured for ${empName}?`)) return;
        try {
          delBtn.disabled = true;
          const url = `/api/admin/leave-permission/employee-custom-leaves/${encodeURIComponent(empId)}${comp ? '?company_id=' + encodeURIComponent(comp) : ''}`;
          const res = await fetch(url, { method: 'DELETE' });
          const data = await res.json();
          if (data.success) {
            await loadBalances();
          } else {
            alert(data.error || 'Failed to delete employee leaves.');
          }
        } catch (err) {
          alert('Error deleting employee leaves: ' + err.message);
        } finally {
          delBtn.disabled = false;
        }
      }
    });
  }

  function buildLeaveUnitOptionsHtml(selectedUnit) {
    const isHours = String(selectedUnit || 'Days').toLowerCase().includes('hour');
    return `
      <option value="Days" ${!isHours ? 'selected' : ''}>Days - Leave</option>
      <option value="Hours" ${isHours ? 'selected' : ''}>Hours - Permission</option>
    `;
  }

  // Row builder for Custom Leave Form (Modal 2)
  function createCustomLeaveRow(name = '', total = '', unit = 'Days', source = 'employee') {
    const row = document.createElement('div');
    row.className = 'custom-leave-row';
    row.setAttribute('data-source', source || 'employee');

    row.innerHTML = `
      <div>
        <input type="text" class="custom-leave-name" placeholder="Leave Name (e.g. Medical Leave)" value="${escapeHtml(name)}" style="width: 100%; box-sizing: border-box; padding: 7px 10px; border-radius: 6px; border: 1.5px solid #cbd5e1; font-size: 12.5px; font-weight: 600;" required>
      </div>
      <div>
        <input type="number" step="0.5" min="0" max="365" class="custom-leave-total" placeholder="Quota" value="${total !== '' ? total : ''}" style="width: 100%; box-sizing: border-box; padding: 7px 10px; border-radius: 6px; border: 1.5px solid #cbd5e1; font-size: 12.5px; font-weight: 700;" required>
      </div>
      <div>
        <select class="custom-leave-unit" style="width: 100%; box-sizing: border-box; padding: 7px 6px; border-radius: 6px; border: 1.5px solid #cbd5e1; font-size: 12px; font-weight: 600; background: #ffffff;">
          ${buildLeaveUnitOptionsHtml(unit)}
        </select>
      </div>
      <div style="display: flex; align-items: center; justify-content: flex-end; gap: 4px;">
        <button type="button" class="btn-edit-leave-row" title="Edit Leave Type" style="padding: 5px 8px; border-radius: 5px; font-size: 11px; font-weight: 700; background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; cursor: pointer;">
          Edit
        </button>
        <button type="button" class="btn-remove-leave-row" title="Delete Leave Type" style="padding: 5px 8px; border-radius: 5px; font-size: 11px; font-weight: 700; background: #fee2e2; color: #dc2626; border: 1px solid #fecaca; cursor: pointer;">
          Del
        </button>
      </div>
    `;

    const editBtn = row.querySelector('.btn-edit-leave-row');
    const nameInput = row.querySelector('.custom-leave-name');
    if (editBtn && nameInput) {
      editBtn.addEventListener('click', () => {
        nameInput.focus();
        nameInput.select();
        row.style.borderColor = '#0284c7';
        row.style.background = '#f0f9ff';
      });
    }

    const removeBtn = row.querySelector('.btn-remove-leave-row');
    removeBtn.addEventListener('click', () => {
      row.remove();
      if (customLeaveRowsContainer && customLeaveRowsContainer.querySelectorAll('.custom-leave-row').length === 0) {
        const emptyHint = document.createElement('div');
        emptyHint.className = 'custom-leave-empty-hint';
        emptyHint.style.cssText = 'padding: 12px; text-align: center; color: #64748b; font-size: 12px; background: #f8fafc; border-radius: 6px; border: 1px dashed #cbd5e1;';
        emptyHint.textContent = 'All leave items removed. Click "Save Leaves" to clear custom leaves, or "+ Add Leave Type" to add one.';
        customLeaveRowsContainer.appendChild(emptyHint);
      }
    });

    return row;
  }

  if (btnAddLeaveTypeRow) {
    btnAddLeaveTypeRow.addEventListener('click', () => {
      if (customLeaveRowsContainer) {
        const hint = customLeaveRowsContainer.querySelector('.custom-leave-empty-hint');
        if (hint) hint.remove();
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
          customLeaveRowsContainer.appendChild(createCustomLeaveRow(lv.name, lv.total, lv.unit || 'Days', lv.source || 'employee'));
        });
      } else {
        // Starter blank row
        customLeaveRowsContainer.appendChild(createCustomLeaveRow('', '', 'Days', 'employee'));
      }
    }

    if (quotaAlertBox) {
      quotaAlertBox.style.display = 'none';
      quotaAlertBox.textContent = '';
    }

    if (window.ArgusVoice) {
      window.ArgusVoice.resetFormGuidance('#modalSetEmployeeLeaveQuota');
    }

    modalSetQuota.style.display = 'flex';
  }

  function closeSetQuotaModal() {
    if (window.ArgusVoice) {
      if (typeof window.ArgusVoice.stop === 'function') {
        window.ArgusVoice.stop();
      } else if (typeof window.ArgusVoice.cancel === 'function') {
        window.ArgusVoice.cancel();
      }
      if (typeof window.ArgusVoice.resetFormGuidance === 'function') {
        window.ArgusVoice.resetFormGuidance('#modalSetEmployeeLeaveQuota');
      }
    }
    if (modalSetQuota) modalSetQuota.style.display = 'none';
  }

  if (closeSetQuotaModalBtn) closeSetQuotaModalBtn.addEventListener('click', closeSetQuotaModal);
  if (cancelSetQuotaModalBtn) cancelSetQuotaModalBtn.addEventListener('click', closeSetQuotaModal);

  // Submit Handler for Set Quota Form
  if (formSetQuota) {
    formSetQuota.addEventListener('submit', async function (e) {
      e.preventDefault();
      if (!btnSaveEmployeeQuota || formSetQuota._isSubmitting) return false;

      const rows = customLeaveRowsContainer ? customLeaveRowsContainer.querySelectorAll('.custom-leave-row') : [];
      const custom_leaves = [];
      rows.forEach(r => {
        const nameInput = r.querySelector('.custom-leave-name');
        const totalInput = r.querySelector('.custom-leave-total');
        const unitInput = r.querySelector('.custom-leave-unit');
        const name = nameInput ? nameInput.value.trim() : '';
        const total = totalInput ? (parseFloat(totalInput.value) || 0) : 0;
        const unit = unitInput ? (unitInput.value || 'Days') : 'Days';
        const source = r.getAttribute('data-source') || 'employee';
        if (name) {
          custom_leaves.push({ name, total, unit, source });
        }
      });

      formSetQuota._isSubmitting = true;
      btnSaveEmployeeQuota.disabled = true;
      btnSaveEmployeeQuota.classList.add('btn-is-submitting');
      const origText = btnSaveEmployeeQuota.innerHTML;
      btnSaveEmployeeQuota.innerHTML = `<span class="spinner-ring" style="width:14px;height:14px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Saving...`;

      if (window.showSavingPopup) {
        window.showSavingPopup('Updating Leave Quota...', 'Saving custom leave entitlement for employee...');
      }

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
        if (window.hideSavingPopup) window.hideSavingPopup();
        if (data.success) {
          if (quotaAlertBox) {
            quotaAlertBox.style.display = 'block';
            quotaAlertBox.style.backgroundColor = '#ecfdf5';
            quotaAlertBox.style.color = '#065f46';
            quotaAlertBox.style.border = '1px solid #a7f3d0';
            quotaAlertBox.textContent = data.message || 'Custom leaves saved successfully!';
          }
          if (window.ArgusVoice) {
            window.ArgusVoice.speakDual({
              en: 'Employee leave quota saved successfully.',
              ta: 'ஊழியர் விடுப்பு ஒதுக்கீடு வெற்றிகரமாக சேமிக்கப்பட்டது.'
            });
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
        if (window.hideSavingPopup) window.hideSavingPopup();
        if (quotaAlertBox) {
          quotaAlertBox.style.display = 'block';
          quotaAlertBox.style.backgroundColor = '#fef2f2';
          quotaAlertBox.style.color = '#991b1b';
          quotaAlertBox.style.border = '1px solid #fecaca';
          quotaAlertBox.textContent = 'Error: ' + err.message;
        }
      } finally {
        formSetQuota._isSubmitting = false;
        if (window.hideSavingPopup) window.hideSavingPopup();
        btnSaveEmployeeQuota.disabled = false;
        btnSaveEmployeeQuota.classList.remove('btn-is-submitting');
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
    if (window.renderTableLoading) {
      window.renderTableLoading(requestsTbody, "Loading leave requests...", 8);
    }
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
          <td class="sticky-col-emp" style="padding: 10px 14px; font-size: 12px;">
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
            if (window.ArgusVoice) {
              window.ArgusVoice.speakDual({
                en: `Request ${reqId} has been approved.`,
                ta: `விண்ணப்பம் ${reqId} ஏற்கப்பட்டது.`
              });
            }
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
        if (window.ArgusVoice) {
          window.ArgusVoice.resetFormGuidance('#modalQuickReject');
        }
        if (modalQuickReject) modalQuickReject.style.display = 'flex';
      });
    });
  }

  // Quick Reject Modal Handlers
  function closeQuickRejectModalFunc() {
    if (window.ArgusVoice) {
      window.ArgusVoice.stop();
      window.ArgusVoice.resetFormGuidance('#modalQuickReject');
    }
    if (modalQuickReject) modalQuickReject.style.display = 'none';
  }

  if (closeQuickRejectBtn && modalQuickReject) {
    closeQuickRejectBtn.addEventListener('click', closeQuickRejectModalFunc);
  }
  if (cancelQuickRejectBtn && modalQuickReject) {
    cancelQuickRejectBtn.addEventListener('click', closeQuickRejectModalFunc);
  }

  if (confirmQuickRejectBtn) {
    confirmQuickRejectBtn.addEventListener('click', async function () {
      if (confirmQuickRejectBtn._isSubmitting) return false;

      const reqId = quickRejectReqId ? quickRejectReqId.value : '';
      const remark = quickRejectRemark ? quickRejectRemark.value.trim() : '';

      if (!reqId) return;

      confirmQuickRejectBtn._isSubmitting = true;
      confirmQuickRejectBtn.disabled = true;
      confirmQuickRejectBtn.classList.add('btn-is-submitting');
      const origRejectText = confirmQuickRejectBtn.innerHTML;
      confirmQuickRejectBtn.innerHTML = `<span class="spinner-ring" style="width:14px;height:14px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Rejecting...`;

      if (window.showSavingPopup) {
        window.showSavingPopup('Processing Rejection...', 'Updating request status and restoring leave balances...');
      }

      try {
        const res = await fetch(`/api/admin/leave-permission/requests/${reqId}/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'Reject', admin_remark: remark })
        });
        const data = await res.json();
        if (window.hideSavingPopup) window.hideSavingPopup();
        if (data.success) {
          if (modalQuickReject) modalQuickReject.style.display = 'none';
          refreshAllData();
          if (window.ArgusVoice) {
            window.ArgusVoice.speakDual({
              en: `Request ${reqId} has been rejected.`,
              ta: `விண்ணப்பம் ${reqId} நிராகரிக்கப்பட்டது.`
            });
          }
        } else {
          alert(data.error || 'Failed to reject request.');
        }
      } catch (err) {
        if (window.hideSavingPopup) window.hideSavingPopup();
        console.error(err);
        alert('Error rejecting request.');
      } finally {
        confirmQuickRejectBtn._isSubmitting = false;
        if (window.hideSavingPopup) window.hideSavingPopup();
        confirmQuickRejectBtn.disabled = false;
        confirmQuickRejectBtn.classList.remove('btn-is-submitting');
        confirmQuickRejectBtn.innerHTML = origRejectText;
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

  // ================= 5. COMPANY OVERALL LEAVES CONTROLLER =================
  const btnOpenCompanyLeavesModal = document.getElementById('btnOpenCompanyLeavesModal');
  const modalCompanyOverallLeaves = document.getElementById('modalCompanyOverallLeaves');
  const closeCompanyLeavesModalBtn = document.getElementById('closeCompanyLeavesModalBtn');
  const doneCompanyLeavesModalBtn = document.getElementById('doneCompanyLeavesModalBtn');
  const companyLeavesAlertBox = document.getElementById('companyLeavesAlertBox');
  const overallLeaveFormHeading = document.getElementById('overallLeaveFormHeading');
  const overallLeaveEditIndex = document.getElementById('overallLeaveEditIndex');
  const overallLeaveNameInput = document.getElementById('overallLeaveNameInput');
  const overallLeaveTotalInput = document.getElementById('overallLeaveTotalInput');
  const overallLeaveUnitSelect = document.getElementById('overallLeaveUnitSelect');
  const btnAddOrUpdateOverallLeave = document.getElementById('btnAddOrUpdateOverallLeave');
  const btnCancelOverallLeaveEdit = document.getElementById('btnCancelOverallLeaveEdit');
  const companyOverallLeavesTbody = document.getElementById('companyOverallLeavesTbody');
  const btnSaveAllCompanyOverallLeaves = document.getElementById('btnSaveAllCompanyOverallLeaves');

  let overallLeavesState = [];

  function showCompanyLeavesAlert(msg, isError = false) {
    if (!companyLeavesAlertBox) return;
    companyLeavesAlertBox.style.display = msg ? 'block' : 'none';
    companyLeavesAlertBox.textContent = msg || '';
    companyLeavesAlertBox.style.backgroundColor = isError ? '#fef2f2' : '#ecfdf5';
    companyLeavesAlertBox.style.color = isError ? '#991b1b' : '#065f46';
    companyLeavesAlertBox.style.border = isError ? '1px solid #fecaca' : '1px solid #a7f3d0';
  }

  function resetOverallLeaveInlineForm() {
    if (overallLeaveEditIndex) overallLeaveEditIndex.value = '-1';
    if (overallLeaveNameInput) overallLeaveNameInput.value = '';
    if (overallLeaveTotalInput) overallLeaveTotalInput.value = '';
    if (overallLeaveUnitSelect) overallLeaveUnitSelect.value = 'Days';
    if (overallLeaveFormHeading) overallLeaveFormHeading.textContent = 'Add Overall Leave / Permission Type';
    if (btnAddOrUpdateOverallLeave) btnAddOrUpdateOverallLeave.textContent = '+ Add';
    if (btnCancelOverallLeaveEdit) btnCancelOverallLeaveEdit.style.display = 'none';
  }

  function renderOverallLeavesTable() {
    if (!companyOverallLeavesTbody) return;
    if (!overallLeavesState || overallLeavesState.length === 0) {
      companyOverallLeavesTbody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; padding: 20px; color: #64748b; font-size: 12.5px;">
            No overall company leaves configured yet. Add a Leave or Permission above, then click "Save & Apply to All Employees".
          </td>
        </tr>
      `;
      return;
    }

    companyOverallLeavesTbody.innerHTML = overallLeavesState.map((item, idx) => {
      const unitStr = String(item.unit || 'Days').toLowerCase().includes('hour') ? 'Hours - Permission' : 'Days - Leave';
      const badgeBg = unitStr.startsWith('Hours') ? '#fef3c7' : '#eff6ff';
      const badgeCol = unitStr.startsWith('Hours') ? '#92400e' : '#1d4ed8';
      return `
        <tr style="border-bottom: 1px solid #f1f5f9;">
          <td style="padding: 9px 12px; font-size: 12px; font-weight: 700; color: #475569;">${idx + 1}</td>
          <td style="padding: 9px 12px; font-size: 12.5px; font-weight: 700; color: #0f172a;">${escapeHtml(item.name)}</td>
          <td style="padding: 9px 12px; text-align: center; font-size: 12.5px; font-weight: 700; color: #0f172a;">${item.total ?? 0}</td>
          <td style="padding: 9px 12px;">
            <span style="display: inline-block; padding: 3px 9px; border-radius: 12px; font-size: 11px; font-weight: 700; background: ${badgeBg}; color: ${badgeCol};">${unitStr}</span>
          </td>
          <td style="padding: 9px 12px; text-align: center;">
            <div style="display: inline-flex; gap: 6px;">
              <button type="button" class="btn-edit-overall-row" data-idx="${idx}" style="padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: 700; background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; cursor: pointer;">Edit</button>
              <button type="button" class="btn-del-overall-row" data-idx="${idx}" style="padding: 4px 10px; border-radius: 5px; font-size: 11px; font-weight: 700; background: #fee2e2; color: #dc2626; border: 1px solid #fecaca; cursor: pointer;">Delete</button>
            </div>
          </td>
        </tr>
      `;
    }).join('');
  }

  async function loadCompanyOverallLeaves() {
    if (companyOverallLeavesTbody) {
      companyOverallLeavesTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: #64748b; font-size: 12.5px;">Loading overall leaves...</td></tr>`;
    }
    try {
      const compId = getSelectedCompanyId();
      const url = `/api/admin/leave-permission/company-overall-leaves${compId ? '?company_id=' + encodeURIComponent(compId) : ''}`;
      const res = await fetch(url);
      const data = await res.json();
      overallLeavesState = Array.isArray(data.overall_leaves) ? data.overall_leaves : [];
      renderOverallLeavesTable();
    } catch (err) {
      showCompanyLeavesAlert('Failed to load overall company leaves: ' + err.message, true);
    }
  }

  function openCompanyLeavesModal() {
    if (!modalCompanyOverallLeaves) return;
    showCompanyLeavesAlert('');
    resetOverallLeaveInlineForm();
    modalCompanyOverallLeaves.style.display = 'flex';
    loadCompanyOverallLeaves();
  }

  function closeCompanyLeavesModal() {
    if (modalCompanyOverallLeaves) modalCompanyOverallLeaves.style.display = 'none';
  }

  if (btnOpenCompanyLeavesModal) btnOpenCompanyLeavesModal.addEventListener('click', openCompanyLeavesModal);
  if (closeCompanyLeavesModalBtn) closeCompanyLeavesModalBtn.addEventListener('click', closeCompanyLeavesModal);
  if (doneCompanyLeavesModalBtn) doneCompanyLeavesModalBtn.addEventListener('click', closeCompanyLeavesModal);
  if (btnCancelOverallLeaveEdit) btnCancelOverallLeaveEdit.addEventListener('click', resetOverallLeaveInlineForm);

  if (btnAddOrUpdateOverallLeave) {
    btnAddOrUpdateOverallLeave.addEventListener('click', () => {
      const name = overallLeaveNameInput ? overallLeaveNameInput.value.trim() : '';
      const totalRaw = overallLeaveTotalInput ? overallLeaveTotalInput.value.trim() : '';
      const total = totalRaw === '' ? 0 : parseFloat(totalRaw);
      const unit = overallLeaveUnitSelect ? (overallLeaveUnitSelect.value || 'Days') : 'Days';
      const editIdx = overallLeaveEditIndex ? parseInt(overallLeaveEditIndex.value, 10) : -1;

      if (!name) {
        showCompanyLeavesAlert('Please enter a Leave / Permission Name.', true);
        if (overallLeaveNameInput) overallLeaveNameInput.focus();
        return;
      }
      if (isNaN(total) || total < 0) {
        showCompanyLeavesAlert('Please enter a valid non-negative count.', true);
        if (overallLeaveTotalInput) overallLeaveTotalInput.focus();
        return;
      }
      showCompanyLeavesAlert('');

      const duplicateIdx = overallLeavesState.findIndex((it, i) => i !== editIdx && String(it.name || '').trim().toLowerCase() === name.toLowerCase());
      if (duplicateIdx >= 0) {
        overallLeavesState[duplicateIdx] = { name, total, unit, source: 'overall' };
      } else if (editIdx >= 0 && editIdx < overallLeavesState.length) {
        overallLeavesState[editIdx] = { name, total, unit, source: 'overall' };
      } else {
        overallLeavesState.push({ name, total, unit, source: 'overall' });
      }
      resetOverallLeaveInlineForm();
      renderOverallLeavesTable();
    });
  }

  if (companyOverallLeavesTbody) {
    companyOverallLeavesTbody.addEventListener('click', async (e) => {
      const editBtn = e.target.closest('.btn-edit-overall-row');
      if (editBtn) {
        const idx = parseInt(editBtn.getAttribute('data-idx'), 10);
        const item = overallLeavesState[idx];
        if (!item) return;
        if (overallLeaveEditIndex) overallLeaveEditIndex.value = String(idx);
        if (overallLeaveNameInput) overallLeaveNameInput.value = item.name || '';
        if (overallLeaveTotalInput) overallLeaveTotalInput.value = item.total ?? '';
        if (overallLeaveUnitSelect) overallLeaveUnitSelect.value = String(item.unit || 'Days').toLowerCase().includes('hour') ? 'Hours' : 'Days';
        if (overallLeaveFormHeading) overallLeaveFormHeading.textContent = `Editing: ${item.name}`;
        if (btnAddOrUpdateOverallLeave) btnAddOrUpdateOverallLeave.textContent = 'Update Row';
        if (btnCancelOverallLeaveEdit) btnCancelOverallLeaveEdit.style.display = 'inline-block';
        if (overallLeaveNameInput) overallLeaveNameInput.focus();
        return;
      }

      const delBtn = e.target.closest('.btn-del-overall-row');
      if (delBtn) {
        const idx = parseInt(delBtn.getAttribute('data-idx'), 10);
        const item = overallLeavesState[idx];
        if (!item) return;
        if (!confirm(`Delete "${item.name}" from Company Overall Leaves and remove it from employees?`)) return;
        overallLeavesState.splice(idx, 1);
        resetOverallLeaveInlineForm();
        renderOverallLeavesTable();
        try {
          const compId = getSelectedCompanyId();
          const res = await fetch('/api/admin/leave-permission/company-overall-leaves', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ company_id: compId, leave_name: item.name })
          });
          const data = await res.json();
          if (data.success) {
            overallLeavesState = Array.isArray(data.overall_leaves) ? data.overall_leaves : overallLeavesState;
            renderOverallLeavesTable();
            showCompanyLeavesAlert(data.message || `Deleted "${item.name}".`);
            await loadBalances();
          }
        } catch (err) {
          showCompanyLeavesAlert('Error deleting leave: ' + err.message, true);
        }
      }
    });
  }

  if (btnSaveAllCompanyOverallLeaves) {
    btnSaveAllCompanyOverallLeaves.addEventListener('click', async () => {
      // Auto-include any pending text typed into inline form if user forgot to click "+ Add"
      const pendingName = overallLeaveNameInput ? overallLeaveNameInput.value.trim() : '';
      if (pendingName && btnAddOrUpdateOverallLeave) {
        btnAddOrUpdateOverallLeave.click();
      }
      const origHtml = btnSaveAllCompanyOverallLeaves.innerHTML;
      btnSaveAllCompanyOverallLeaves.disabled = true;
      btnSaveAllCompanyOverallLeaves.textContent = 'Applying to Employees...';
      try {
        const compId = getSelectedCompanyId();
        const res = await fetch('/api/admin/leave-permission/company-overall-leaves', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ company_id: compId, overall_leaves: overallLeavesState })
        });
        const data = await res.json();
        if (data.success) {
          overallLeavesState = Array.isArray(data.overall_leaves) ? data.overall_leaves : overallLeavesState;
          renderOverallLeavesTable();
          showCompanyLeavesAlert(data.message || 'Overall company leaves applied to all employees!');
          await loadBalances();
        } else {
          showCompanyLeavesAlert(data.error || 'Failed to save overall company leaves.', true);
        }
      } catch (err) {
        showCompanyLeavesAlert('Error saving overall leaves: ' + err.message, true);
      } finally {
        btnSaveAllCompanyOverallLeaves.disabled = false;
        btnSaveAllCompanyOverallLeaves.innerHTML = origHtml;
      }
    });
  }

  // ================= 6. PAID HOLIDAYS CALENDAR CONTROLLER =================
  const btnOpenPaidHolidaysModal = document.getElementById('btnOpenPaidHolidaysModal');
  const modalPaidHolidaysCalendar = document.getElementById('modalPaidHolidaysCalendar');
  const closePaidHolidaysModalBtn = document.getElementById('closePaidHolidaysModalBtn');
  const donePaidHolidaysModalBtn = document.getElementById('donePaidHolidaysModalBtn');
  const paidHolidaysAlertBox = document.getElementById('paidHolidaysAlertBox');
  const btnHolPrevMonth = document.getElementById('btnHolPrevMonth');
  const btnHolNextMonth = document.getElementById('btnHolNextMonth');
  const btnHolTodayMonth = document.getElementById('btnHolTodayMonth');
  const holCalendarMonthTitle = document.getElementById('holCalendarMonthTitle');
  const holCalendarYearSelect = document.getElementById('holCalendarYearSelect');
  const holCalendarGrid = document.getElementById('holCalendarGrid');
  const formPaidHoliday = document.getElementById('formPaidHoliday');
  const paidHolidayEditId = document.getElementById('paidHolidayEditId');
  const paidHolidayFormTitle = document.getElementById('paidHolidayFormTitle');
  const paidHolidayDateInput = document.getElementById('paidHolidayDateInput');
  const paidHolidayNameInput = document.getElementById('paidHolidayNameInput');
  const btnSavePaidHoliday = document.getElementById('btnSavePaidHoliday');
  const btnCancelPaidHolidayEdit = document.getElementById('btnCancelPaidHolidayEdit');
  const paidHolidaysListHeading = document.getElementById('paidHolidaysListHeading');
  const paidHolidaysTbody = document.getElementById('paidHolidaysTbody');

  const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  let holViewYear = new Date().getFullYear();
  let holViewMonth = new Date().getMonth(); // 0-indexed
  let cachedYearHolidays = [];

  function showPaidHolidaysAlert(msg, isError = false) {
    if (!paidHolidaysAlertBox) return;
    paidHolidaysAlertBox.style.display = msg ? 'block' : 'none';
    paidHolidaysAlertBox.textContent = msg || '';
    paidHolidaysAlertBox.style.backgroundColor = isError ? '#fef2f2' : '#ecfdf5';
    paidHolidaysAlertBox.style.color = isError ? '#991b1b' : '#065f46';
    paidHolidaysAlertBox.style.border = isError ? '1px solid #fecaca' : '1px solid #a7f3d0';
  }

  function populateHolYearOptions(selectedYr) {
    if (!holCalendarYearSelect) return;
    const baseYr = new Date().getFullYear();
    const minY = Math.min(baseYr - 2, selectedYr - 1);
    const maxY = Math.max(baseYr + 4, selectedYr + 1);
    let opts = '';
    for (let y = minY; y <= maxY; y++) {
      opts += `<option value="${y}" ${y === selectedYr ? 'selected' : ''}>${y}</option>`;
    }
    holCalendarYearSelect.innerHTML = opts;
  }

  function resetPaidHolidayForm(defaultDateStr = '') {
    if (paidHolidayEditId) paidHolidayEditId.value = '';
    if (paidHolidayDateInput) paidHolidayDateInput.value = defaultDateStr || '';
    if (paidHolidayNameInput) paidHolidayNameInput.value = '';
    if (paidHolidayFormTitle) paidHolidayFormTitle.textContent = 'Mark Paid Holiday';
    if (btnSavePaidHoliday) btnSavePaidHoliday.textContent = 'Save Paid Holiday';
    if (btnCancelPaidHolidayEdit) btnCancelPaidHolidayEdit.style.display = 'none';
  }

  function selectHolidayForEdit(hol) {
    if (!hol) return;
    if (paidHolidayEditId) paidHolidayEditId.value = hol.id || '';
    if (paidHolidayDateInput) paidHolidayDateInput.value = hol.date || '';
    if (paidHolidayNameInput) paidHolidayNameInput.value = hol.holiday_name || '';
    if (paidHolidayFormTitle) paidHolidayFormTitle.textContent = `Edit Paid Holiday (${hol.date})`;
    if (btnSavePaidHoliday) btnSavePaidHoliday.textContent = 'Update Paid Holiday';
    if (btnCancelPaidHolidayEdit) btnCancelPaidHolidayEdit.style.display = 'inline-block';
    if (paidHolidayNameInput) paidHolidayNameInput.focus();
  }

  function renderHolidaysCalendarAndTable() {
    const mmStr = String(holViewMonth + 1).padStart(2, '0');
    const ymPrefix = `${holViewYear}-${mmStr}`;
    if (holCalendarMonthTitle) {
      holCalendarMonthTitle.textContent = `${MONTH_NAMES[holViewMonth]} ${holViewYear}`;
    }
    if (holCalendarYearSelect) {
      holCalendarYearSelect.value = String(holViewYear);
    }
    if (paidHolidaysListHeading) {
      paidHolidaysListHeading.textContent = `Paid Holidays — ${MONTH_NAMES[holViewMonth]} ${holViewYear}`;
    }

    const holByDate = {};
    cachedYearHolidays.forEach(h => {
      if (h && h.date) holByDate[h.date] = h;
    });

    if (holCalendarGrid) {
      const firstDow = new Date(holViewYear, holViewMonth, 1).getDay();
      const daysInMonth = new Date(holViewYear, holViewMonth + 1, 0).getDate();
      const now = new Date();
      const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
      const activeSelectedIso = paidHolidayDateInput ? paidHolidayDateInput.value : '';

      let cellsHtml = '';
      for (let i = 0; i < firstDow; i++) {
        cellsHtml += `<div style="min-height: 68px; border-radius: 8px; background: #f8fafc; opacity: 0.45;"></div>`;
      }

      for (let d = 1; d <= daysInMonth; d++) {
        const dStr = `${ymPrefix}-${String(d).padStart(2, '0')}`;
        const dow = (firstDow + d - 1) % 7;
        const hol = holByDate[dStr];
        const isToday = (dStr === todayIso);
        const isSelected = (dStr === activeSelectedIso);

        const bg = hol ? '#ecfdf5' : (dow === 0 ? '#fff5f5' : '#ffffff');
        const border = isSelected ? '2px solid #0284c7' : (hol ? '1.5px solid #34d399' : (isToday ? '1.5px solid #2563eb' : '1px solid #e2e8f0'));
        const numColor = hol ? '#065f46' : (dow === 0 ? '#dc2626' : '#0f172a');

        cellsHtml += `
          <button type="button" class="hol-cal-day" data-date="${dStr}"
            style="min-height: 68px; padding: 6px; border-radius: 8px; background: ${bg}; border: ${border}; text-align: left; display: flex; flex-direction: column; justify-content: space-between; cursor: pointer; transition: all 0.12s ease;">
            <div style="display: flex; align-items: center; justify-content: space-between; width: 100%;">
              <span style="font-size: 12.5px; font-weight: 800; color: ${numColor};">${d}</span>
              ${hol ? `<span style="width: 7px; height: 7px; border-radius: 50%; background: #059669;"></span>` : ''}
            </div>
            ${hol
              ? `<div style="font-size: 10px; font-weight: 700; color: #047857; background: #d1fae5; padding: 2px 5px; border-radius: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%;" title="${escapeHtml(hol.holiday_name)}">${escapeHtml(hol.holiday_name)}</div>`
              : `<div style="font-size: 9.5px; color: #94a3b8;">Click to set</div>`
            }
          </button>
        `;
      }
      holCalendarGrid.innerHTML = cellsHtml;
    }

    if (paidHolidaysTbody) {
      const monthHolidays = cachedYearHolidays.filter(h => String(h.date || '').startsWith(ymPrefix));
      if (monthHolidays.length === 0) {
        paidHolidaysTbody.innerHTML = `
          <tr>
            <td colspan="3" style="text-align: center; padding: 18px; color: #64748b; font-size: 12px;">
              No Paid Holidays marked in ${MONTH_NAMES[holViewMonth]} ${holViewYear}. Click any date on the calendar to add one.
            </td>
          </tr>
        `;
      } else {
        paidHolidaysTbody.innerHTML = monthHolidays.map(h => `
          <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 8px 10px; font-size: 11.5px; font-weight: 700; color: #0f172a; white-space: nowrap;">${escapeHtml(h.date)}</td>
            <td style="padding: 8px 10px; font-size: 12px; font-weight: 600; color: #065f46;">${escapeHtml(h.holiday_name)}</td>
            <td style="padding: 8px 10px; text-align: center; white-space: nowrap;">
              <button type="button" class="btn-edit-holiday" data-id="${escapeHtml(h.id)}" style="padding: 3px 8px; border-radius: 5px; font-size: 11px; font-weight: 700; background: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd; cursor: pointer; margin-right: 4px;">Edit</button>
              <button type="button" class="btn-del-holiday" data-id="${escapeHtml(h.id)}" data-name="${escapeHtml(h.holiday_name)}" style="padding: 3px 8px; border-radius: 5px; font-size: 11px; font-weight: 700; background: #fee2e2; color: #dc2626; border: 1px solid #fecaca; cursor: pointer;">Del</button>
            </td>
          </tr>
        `).join('');
      }
    }
  }

  async function loadHolidaysForYear(year) {
    try {
      const compId = getSelectedCompanyId();
      const qs = new URLSearchParams({ year: String(year) });
      if (compId) qs.set('company_id', compId);
      const res = await fetch(`/api/admin/leave-permission/holidays?${qs.toString()}`);
      const data = await res.json();
      cachedYearHolidays = Array.isArray(data.holidays) ? data.holidays : [];
      renderHolidaysCalendarAndTable();
    } catch (err) {
      showPaidHolidaysAlert('Failed to load paid holidays: ' + err.message, true);
    }
  }

  function openPaidHolidaysModal() {
    if (!modalPaidHolidaysCalendar) return;
    const now = new Date();
    holViewYear = now.getFullYear();
    holViewMonth = now.getMonth();
    populateHolYearOptions(holViewYear);
    showPaidHolidaysAlert('');
    resetPaidHolidayForm(`${holViewYear}-${String(holViewMonth + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`);
    modalPaidHolidaysCalendar.style.display = 'flex';
    loadHolidaysForYear(holViewYear);
  }

  function closePaidHolidaysModal() {
    if (modalPaidHolidaysCalendar) modalPaidHolidaysCalendar.style.display = 'none';
  }

  if (btnOpenPaidHolidaysModal) btnOpenPaidHolidaysModal.addEventListener('click', openPaidHolidaysModal);
  if (closePaidHolidaysModalBtn) closePaidHolidaysModalBtn.addEventListener('click', closePaidHolidaysModal);
  if (donePaidHolidaysModalBtn) donePaidHolidaysModalBtn.addEventListener('click', closePaidHolidaysModal);
  if (btnCancelPaidHolidayEdit) {
    btnCancelPaidHolidayEdit.addEventListener('click', () => {
      resetPaidHolidayForm(paidHolidayDateInput ? paidHolidayDateInput.value : '');
      renderHolidaysCalendarAndTable();
    });
  }

  if (btnHolPrevMonth) {
    btnHolPrevMonth.addEventListener('click', () => {
      const prevYear = holViewYear;
      holViewMonth -= 1;
      if (holViewMonth < 0) {
        holViewMonth = 11;
        holViewYear -= 1;
      }
      populateHolYearOptions(holViewYear);
      if (holViewYear !== prevYear) loadHolidaysForYear(holViewYear);
      else renderHolidaysCalendarAndTable();
    });
  }

  if (btnHolNextMonth) {
    btnHolNextMonth.addEventListener('click', () => {
      const prevYear = holViewYear;
      holViewMonth += 1;
      if (holViewMonth > 11) {
        holViewMonth = 0;
        holViewYear += 1;
      }
      populateHolYearOptions(holViewYear);
      if (holViewYear !== prevYear) loadHolidaysForYear(holViewYear);
      else renderHolidaysCalendarAndTable();
    });
  }

  if (btnHolTodayMonth) {
    btnHolTodayMonth.addEventListener('click', () => {
      const now = new Date();
      const prevYear = holViewYear;
      holViewYear = now.getFullYear();
      holViewMonth = now.getMonth();
      populateHolYearOptions(holViewYear);
      if (holViewYear !== prevYear) loadHolidaysForYear(holViewYear);
      else renderHolidaysCalendarAndTable();
    });
  }

  if (holCalendarYearSelect) {
    holCalendarYearSelect.addEventListener('change', () => {
      holViewYear = parseInt(holCalendarYearSelect.value, 10) || new Date().getFullYear();
      loadHolidaysForYear(holViewYear);
    });
  }

  if (holCalendarGrid) {
    holCalendarGrid.addEventListener('click', (e) => {
      const cell = e.target.closest('.hol-cal-day');
      if (!cell) return;
      const dStr = cell.getAttribute('data-date');
      const existingHol = cachedYearHolidays.find(h => h.date === dStr);
      if (existingHol) {
        selectHolidayForEdit(existingHol);
      } else {
        resetPaidHolidayForm(dStr);
        if (paidHolidayNameInput) paidHolidayNameInput.focus();
      }
      renderHolidaysCalendarAndTable();
    });
  }

  if (paidHolidaysTbody) {
    paidHolidaysTbody.addEventListener('click', async (e) => {
      const editBtn = e.target.closest('.btn-edit-holiday');
      if (editBtn) {
        const holId = editBtn.getAttribute('data-id');
        const hol = cachedYearHolidays.find(h => String(h.id) === String(holId));
        if (hol) {
          selectHolidayForEdit(hol);
          renderHolidaysCalendarAndTable();
        }
        return;
      }

      const delBtn = e.target.closest('.btn-del-holiday');
      if (delBtn) {
        const holId = delBtn.getAttribute('data-id');
        const holName = delBtn.getAttribute('data-name') || 'this holiday';
        if (!confirm(`Delete Paid Holiday "${holName}"?`)) return;
        try {
          const compId = getSelectedCompanyId();
          const url = `/api/admin/leave-permission/holidays/${encodeURIComponent(holId)}${compId ? '?company_id=' + encodeURIComponent(compId) : ''}`;
          const res = await fetch(url, { method: 'DELETE' });
          const data = await res.json();
          if (data.success) {
            showPaidHolidaysAlert(data.message || 'Paid holiday deleted.');
            if (paidHolidayEditId && paidHolidayEditId.value === holId) resetPaidHolidayForm('');
            await loadHolidaysForYear(holViewYear);
          } else {
            showPaidHolidaysAlert(data.error || 'Failed to delete holiday.', true);
          }
        } catch (err) {
          showPaidHolidaysAlert('Error deleting holiday: ' + err.message, true);
        }
      }
    });
  }

  if (formPaidHoliday) {
    formPaidHoliday.addEventListener('submit', async (e) => {
      e.preventDefault();
      const editId = paidHolidayEditId ? paidHolidayEditId.value.trim() : '';
      const dateVal = paidHolidayDateInput ? paidHolidayDateInput.value.trim() : '';
      const nameVal = paidHolidayNameInput ? paidHolidayNameInput.value.trim() : '';
      if (!dateVal || !nameVal) {
        showPaidHolidaysAlert('Date and Holiday Name are required.', true);
        return;
      }

      const origText = btnSavePaidHoliday ? btnSavePaidHoliday.textContent : 'Save Paid Holiday';
      if (btnSavePaidHoliday) {
        btnSavePaidHoliday.disabled = true;
        btnSavePaidHoliday.textContent = 'Saving...';
      }
      try {
        const compId = getSelectedCompanyId();
        const url = editId
          ? `/api/admin/leave-permission/holidays/${encodeURIComponent(editId)}`
          : '/api/admin/leave-permission/holidays';
        const method = editId ? 'PUT' : 'POST';
        const res = await fetch(url, {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company_id: compId,
            date: dateVal,
            holiday_name: nameVal,
            is_paid: true
          })
        });
        const data = await res.json();
        if (data.success) {
          showPaidHolidaysAlert(data.message || 'Paid holiday saved!');
          const savedYr = parseInt(dateVal.split('-')[0], 10);
          const savedMo = parseInt(dateVal.split('-')[1], 10) - 1;
          if (!isNaN(savedYr) && !isNaN(savedMo)) {
            holViewYear = savedYr;
            holViewMonth = savedMo;
            populateHolYearOptions(holViewYear);
          }
          resetPaidHolidayForm(dateVal);
          await loadHolidaysForYear(holViewYear);
        } else {
          showPaidHolidaysAlert(data.error || 'Failed to save paid holiday.', true);
        }
      } catch (err) {
        showPaidHolidaysAlert('Error saving paid holiday: ' + err.message, true);
      } finally {
        if (btnSavePaidHoliday) {
          btnSavePaidHoliday.disabled = false;
          btnSavePaidHoliday.textContent = origText;
        }
      }
    });
  }

  // Bind Voice Toggles and Form Guidance
  if (window.ArgusVoice) {
    window.ArgusVoice.bindToggle('btnLeaveToggleVoice');
    window.ArgusVoice.bindToggle('btnQuotaModalToggleVoice');
    window.ArgusVoice.bindToggle('btnQuickRejectModalToggleVoice');

    window.ArgusVoice.attachFormGuidance('#modalSetEmployeeLeaveQuota', {
      '.custom-leave-name': {
        english: 'Enter the custom leave category name, such as Casual, Sick, or Annual leave.',
        tamil: 'கேசுவல், சிக் அல்லது ஆண்டு விடுப்பு போன்ற தனிப்பயன் விடுப்பு வகையின் பெயரை உள்ளிடவும்.'
      },
      '.custom-leave-total': {
        english: 'Enter the total allocated quota days for this leave category.',
        tamil: 'இந்த விடுப்பு வகைக்கான மொத்த ஒதுக்கீட்டு நாட்களை உள்ளிடவும்.'
      }
    });

    window.ArgusVoice.attachFormGuidance('#modalQuickReject', {
      '#quickRejectRemark': {
        english: 'Please provide a clear admin reason for rejecting this leave request.',
        tamil: 'விடுப்பு கோரிக்கையை நிராகரிப்பதற்கான தெளிவான காரணத்தை உள்ளிடவும்.'
      }
    });
  }

  // Initial load
  refreshAllData();
});
