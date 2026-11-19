// Manual Entry Tab Script: Table management, filters, modal actions (Add/Edit/Delete), and exports
document.addEventListener('DOMContentLoaded', function () {
  let currentPage = 1;
  let currentLimit = 10;
  let currentSearch = '';
  let fromDate = '';
  let toDate = '';
  let statusVal = 'All';

  // DOM Elements
  const tableBody = document.getElementById('manualEntryTableBody');
  const tableInfoText = document.getElementById('tableInfoText');
  const searchInput = document.getElementById('tableSearch');
  const limitSelect = document.getElementById('entriesLimit');
  const prevBtn = document.getElementById('prevPageBtn');
  const nextBtn = document.getElementById('nextPageBtn');
  const currentPageBtn = document.getElementById('currentPageBtn');

  const fromDateFilter = document.getElementById('fromDateFilter');
  const toDateFilter = document.getElementById('toDateFilter');
  const statusFilter = document.getElementById('statusFilter');
  const btnFilter = document.getElementById('btnFilterManual');
  const btnClear = document.getElementById('btnClearManual');

  // Modal elements
  const modal = document.getElementById('manualEntryModal');
  const btnOpenModal = document.getElementById('btnOpenManualEntryModal');
  const btnCloseModal = document.getElementById('closeManualModal');
  const form = document.getElementById('manualEntryForm');
  const modalTitle = document.getElementById('manualModalTitle');
  const entryIdInput = document.getElementById('manualEntryId');
  const entryTypeInput = document.getElementById('inputEntryType');
  const empNameSelect = document.getElementById('inputEmployeeName');
  const entryDateInput = document.getElementById('inputEntryDate');
  const hoursInput = document.getElementById('inputHours');
  const statusSelect = document.getElementById('inputStatus');
  const reasonInput = document.getElementById('inputReason');

  // Export buttons
  const btnCopy = document.getElementById('btnCopyTable');
  const btnCsv = document.getElementById('btnCsvTable');
  const btnExcel = document.getElementById('btnExcelTable');
  const btnPdf = document.getElementById('btnPdfTable');
  const btnPrint = document.getElementById('btnPrintTable');

  // Bulk actions elements
  const bulkBar = document.getElementById('bulkActionsBar');
  const selectedCountBadge = document.getElementById('selectedCountBadge');
  const btnSelectedCount = document.getElementById('btnSelectedCount');
  const btnClearSelection = document.getElementById('btnClearSelection');
  const btnDeleteSelected = document.getElementById('btnDeleteSelected');
  const btnOpenDeleteRangeManual = document.getElementById('btnOpenDeleteRangeManual');
  const selectAllManual = document.getElementById('selectAllManual');
  const selectedManualIds = new Set();

  function updateBulkBar() {
    const count = selectedManualIds.size;
    if (bulkBar) {
      bulkBar.style.display = count > 0 ? 'flex' : 'none';
    }
    if (selectedCountBadge) selectedCountBadge.textContent = count;
    if (btnSelectedCount) btnSelectedCount.textContent = count;
    if (selectAllManual) {
      const pageCheckboxes = document.querySelectorAll('.manual-row-select');
      if (pageCheckboxes.length > 0) {
        selectAllManual.checked = Array.from(pageCheckboxes).every(cb => cb.checked);
      } else {
        selectAllManual.checked = false;
      }
    }
  }

  function clearSelection() {
    selectedManualIds.clear();
    document.querySelectorAll('.manual-row-select').forEach(cb => cb.checked = false);
    if (selectAllManual) selectAllManual.checked = false;
    updateBulkBar();
  }

  // Load employee names for modal dropdown (reuse server-rendered options; fallback to lightweight names endpoint)
  async function loadEmployees() {
    if (empNameSelect && empNameSelect.options.length > 1) return;
    try {
      const res = await fetch('/api/employees/names');
      const data = await res.json();
      const names = data.names || (data.data || []).map(e => e.employee_name);
      if (empNameSelect && names.length > 0) {
        empNameSelect.innerHTML = '<option value="" disabled selected>Select</option>';
        names.forEach(name => {
          const opt = document.createElement('option');
          opt.value = name;
          opt.textContent = name;
          empNameSelect.appendChild(opt);
        });
      }
    } catch (err) {
      console.warn('Could not load employees:', err);
    }
  }

  // Load entries from server
  async function loadEntries() {
    if (document.hidden) return;
    if (window.renderTableLoading && tableBody) {
      window.renderTableLoading(tableBody, "Loading manual entry logs...", 10);
    }
    try {
      const params = new URLSearchParams({
        from_date: fromDate,
        to_date: toDate,
        status: statusVal,
        search: currentSearch,
        page: currentPage,
        limit: currentLimit
      });

      const res = await fetch(`/api/manual-entries?${params.toString()}`);
      const data = await res.json();

      renderRows(data.data);
      updatePagination(data.total, data.page, data.limit);
    } catch (err) {
      console.error('Failed to load manual entries:', err);
    }
  }

  function renderRows(rows) {
    if (!tableBody) return;
    tableBody.innerHTML = '';

    const canDelete = Boolean(window.CAN_DELETE_ENTRIES);
    const colCount = canDelete ? 11 : 10;

    if (!rows || rows.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="${colCount}" style="text-align: center; color: #555; padding: 25px;">
            No data available in table
          </td>
        </tr>
      `;
      updateBulkBar();
      return;
    }

    rows.forEach(r => {
      const tr = document.createElement('tr');
      const isSub = String(r.entry_type || '').toLowerCase() === 'sub' || Number(r.working_salary || 0) < 0;
      const salVal = Math.abs(Number(r.working_salary || 0)).toFixed(0);
      let salDisplay = '₹ 0';
      let salClass = 'salary-positive';
      if (isSub && Number(salVal) > 0) {
        salDisplay = `₹ -${salVal}`;
        salClass = 'salary-negative';
      } else if (Number(salVal) > 0) {
        salDisplay = `₹ +${salVal}`;
        salClass = 'salary-positive';
      }
      const hoursDisplay = isSub ? `-${escapeHtml(r.hours || '')}` : escapeHtml(r.hours || '');
      const rawStatus = r.status || '';
      const isCoworkerEntry = String(r.recorded_by || '').trim().toLowerCase() === 'coworker'
        || /^recorded by co-?worker$/i.test(String(r.reason || '').trim());
      let rawReason = (r.reason || '').trim();
      if (!rawReason && isCoworkerEntry) {
        rawReason = 'Recorded by Coworker';
      }
      let statusDisplay = rawStatus;
      if (rawReason) {
        if (rawReason.startsWith('(') && rawReason.endsWith(')')) {
          statusDisplay = `${rawStatus} ${rawReason}`;
        } else {
          statusDisplay = `${rawStatus} (${rawReason})`;
        }
      }
      const coworkerBadgeHtml = isCoworkerEntry
        ? ` <span style="display: inline-flex; align-items: center; gap: 3px; margin-left: 6px; padding: 2px 7px; font-size: 10.5px; font-weight: 700; border-radius: 999px; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; white-space: nowrap;" title="Entered via Co-Worker AI">🤖 Recorded by Coworker</span>`
        : '';

      const rIdStr = String(r.id);
      const isChecked = selectedManualIds.has(rIdStr);
      const chkCol = canDelete
        ? `<td style="text-align: center;"><input type="checkbox" class="manual-row-select" data-id="${escapeHtml(rIdStr)}" ${isChecked ? 'checked' : ''} style="cursor: pointer; width: 16px; height: 16px; accent-color: #dc2626;"></td>`
        : '';
      const delBtnHtml = canDelete
        ? `<button class="btn-action-manual-del" onclick="deleteManualEntry(${r.id}, '${escapeHtml(r.employee_name)}')">Del</button>`
        : '';

      tr.innerHTML = `
        ${chkCol}
        <td class="col-wrap sticky-col-emp" style="white-space: normal !important; word-break: break-word !important; min-width: 140px;">${escapeHtml(r.employee_name)}</td>
        <td>${escapeHtml(r.entry_date || '')}</td>
        <td>${hoursDisplay}</td>
        <td class="col-wrap" style="white-space: normal !important; word-break: break-word !important; min-width: 150px;"><span>${escapeHtml(statusDisplay)}</span>${coworkerBadgeHtml}</td>
        <td>${escapeHtml(r.submitted_at || '')}</td>
        <td>${Number(r.hourly_rate || 0).toFixed(0)}</td>
        <td>${Number(r.day_rate || 0).toFixed(0)}</td>
        <td>${Number(r.half_rate || 0).toFixed(0)}</td>
        <td><span class="${salClass}">${salDisplay}</span></td>
        <td>
          <button class="btn-action-manual-edit" onclick="editManualEntry(${r.id})">Edit</button>
          ${delBtnHtml}
        </td>
      `;
      tableBody.appendChild(tr);
    });

    tableBody.querySelectorAll('.manual-row-select').forEach(cb => {
      cb.addEventListener('change', function () {
        const id = this.getAttribute('data-id');
        if (this.checked) {
          selectedManualIds.add(id);
        } else {
          selectedManualIds.delete(id);
        }
        updateBulkBar();
      });
    });
    updateBulkBar();
  }

  function updatePagination(total, page, limit) {
    if (total === 0) {
      tableInfoText.textContent = 'Showing 0 to 0 of 0 entries';
      currentPageBtn.textContent = '1';
      prevBtn.classList.add('disabled');
      nextBtn.classList.add('disabled');
      return;
    }

    const start = (page - 1) * limit + 1;
    const end = Math.min(page * limit, total);
    tableInfoText.textContent = `Showing ${start} to ${end} of ${total} entries`;
    currentPageBtn.textContent = String(page);

    if (page <= 1) {
      prevBtn.classList.add('disabled');
    } else {
      prevBtn.classList.remove('disabled');
    }

    const maxPages = Math.ceil(total / limit);
    if (page >= maxPages) {
      nextBtn.classList.add('disabled');
    } else {
      nextBtn.classList.remove('disabled');
    }
  }

  // Filter & Clear events
  if (btnFilter) {
    btnFilter.addEventListener('click', function () {
      fromDate = fromDateFilter.value.trim();
      toDate = toDateFilter.value.trim();
      statusVal = statusFilter.value;
      currentPage = 1;
      loadEntries();
    });
  }

  if (btnClear) {
    btnClear.addEventListener('click', function () {
      fromDateFilter.value = '';
      toDateFilter.value = '';
      statusFilter.value = 'All';
      fromDate = '';
      toDate = '';
      statusVal = 'All';
      currentPage = 1;
      loadEntries();
    });
  }

  // Instant Search
  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        currentSearch = searchInput.value.trim();
        currentPage = 1;
        loadEntries();
      }, 250);
    });
  }

  // Entries limit
  if (limitSelect) {
    limitSelect.addEventListener('change', function () {
      currentLimit = parseInt(this.value, 10);
      currentPage = 1;
      loadEntries();
    });
  }

  // Pagination clicks
  if (prevBtn) {
    prevBtn.addEventListener('click', function () {
      if (currentPage > 1) {
        currentPage--;
        loadEntries();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      currentPage++;
      loadEntries();
    });
  }

  // ================= MODAL LOGIC =================
  if (btnOpenModal) {
    btnOpenModal.addEventListener('click', function () {
      form.reset();
      entryIdInput.value = '';
      if (entryTypeInput) entryTypeInput.value = 'Add';
      modalTitle.textContent = 'Manual Entry';
      // Default to today
      const today = new Date().toISOString().split('T')[0];
      entryDateInput.value = today;
      hoursInput.value = '04:00';
      statusSelect.value = 'Proper';
      if (reasonInput) reasonInput.value = '';
      if (window.ArgusVoice) window.ArgusVoice.resetFormGuidance('#manualEntryModal');
      modal.classList.add('active');
    });
  }

  // Smart hour:minute format normalizer (e.g. 8.30 -> 08:30, 8 -> 08:00, 8:30 -> 08:30)
  function normalizeTimeInput(val) {
    if (!val) return '00:00';
    let s = String(val).trim();
    if (s.includes('.')) {
      const parts = s.split('.');
      const h = parseInt(parts[0], 10) || 0;
      let m = parts[1] || '0';
      if (m.length === 1) m = m + '0';
      const mInt = parseInt(m.substring(0, 2), 10) || 0;
      return `${String(h).padStart(2, '0')}:${String(mInt).padStart(2, '0')}`;
    } else if (s.includes(':')) {
      const parts = s.split(':');
      const h = parseInt(parts[0], 10) || 0;
      const m = parseInt(parts[1], 10) || 0;
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
    } else if (!isNaN(parseFloat(s))) {
      const h = parseInt(s, 10) || 0;
      return `${String(h).padStart(2, '0')}:00`;
    }
    return val;
  }

  if (hoursInput) {
    hoursInput.addEventListener('blur', function () {
      if (this.value) {
        this.value = normalizeTimeInput(this.value);
      }
    });
    hoursInput.addEventListener('change', function () {
      if (this.value) {
        this.value = normalizeTimeInput(this.value);
      }
    });
  }

  if (btnCloseModal) {
    btnCloseModal.addEventListener('click', function () {
      modal.classList.remove('active');
    });
  }

  modal.addEventListener('click', function (e) {
    if (e.target === modal) {
      modal.classList.remove('active');
    }
  });

  // Edit record
  window.editManualEntry = async function (id) {
    try {
      const res = await fetch(`/api/manual-entries/${id}`);
      if (!res.ok) throw new Error('Entry not found');
      const entry = await res.json();

      entryIdInput.value = entry.id;
      if (entryTypeInput) {
        entryTypeInput.value = entry.entry_type || (Number(entry.working_salary || 0) < 0 ? 'Sub' : 'Add');
      }
      modalTitle.textContent = 'Manual Entry';
      empNameSelect.value = entry.employee_name;
      
      // Format date if needed
      let d = entry.entry_date;
      if (d && d.includes('-') && d.split('-')[0].length === 2) {
        const parts = d.split('-');
        d = `${parts[2]}-${parts[1]}-${parts[0]}`;
      }
      entryDateInput.value = d;
      hoursInput.value = entry.hours || '04:00';
      statusSelect.value = entry.status || 'Proper';
      if (reasonInput) reasonInput.value = entry.reason || '';

      if (window.ArgusVoice) window.ArgusVoice.resetFormGuidance('#manualEntryModal');
      modal.classList.add('active');
    } catch (err) {
      alert('Error fetching manual entry: ' + err.message);
    }
  };

  // Delete record
  window.deleteManualEntry = async function (id, name) {
    if (confirm(`Are you sure you want to delete manual entry for "${name}"?`)) {
      try {
        const res = await fetch(`/api/manual-entries/${id}`, { method: 'DELETE' });
        const d = await res.json();
        if (d.success) {
          if (window.ArgusVoice) {
            ArgusVoice.announceSuccess('வருகை பதிவு நீக்கப்பட்டது.', 'Manual attendance entry deleted successfully.');
          }
          loadEntries();
        } else {
          alert(d.error || 'Failed to delete record');
        }
      } catch (err) {
        alert('Error deleting entry: ' + err.message);
      }
    }
  };

  // Form submit
  if (form) {
    form.addEventListener('submit', async function (e) {
      e.preventDefault();

      if (form._isSubmitting) {
        return false;
      }

      const id = entryIdInput.value;
      const rInput = document.getElementById('inputReason');
      const reasonVal = rInput ? rInput.value.trim() : (form.elements['reason'] ? form.elements['reason'].value.trim() : (reasonInput ? reasonInput.value.trim() : ''));
      const formData = {
        employee_name: empNameSelect.value,
        entry_date: entryDateInput.value,
        hours: hoursInput.value,
        status: statusSelect.value,
        reason: reasonVal,
        entry_type: (entryTypeInput ? entryTypeInput.value : 'Add')
      };

      if (!formData.employee_name) {
        alert('Please select an employee.');
        return;
      }

      form._isSubmitting = true;
      const btnSubmitManual = document.getElementById('btnSubmitManual') || form.querySelector('button[type="submit"]');
      const origText = btnSubmitManual ? btnSubmitManual.innerHTML : 'Submit';
      if (btnSubmitManual) {
        btnSubmitManual.disabled = true;
        btnSubmitManual.classList.add('btn-is-submitting');
        btnSubmitManual.innerHTML = '<span class="spinner-ring" style="width:14px;height:14px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Saving...';
      }
      if (window.showSavingPopup) {
        window.showSavingPopup(
          id ? 'Updating Manual Entry...' : 'Saving Manual Entry...',
          'Recording employee attendance details into attendance registry...'
        );
      }

      const url = id ? `/api/manual-entries/${id}` : '/api/manual-entries';
      const method = id ? 'PUT' : 'POST';

      try {
        const res = await fetch(url, {
          method: method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData)
        });

        const d = await res.json();
        if (window.hideSavingPopup) window.hideSavingPopup();
        if (res.ok && d.success) {
          const empName = formData.employee_name || 'Employee';
          if (window.ArgusVoice) {
            ArgusVoice.announceSuccess(
              `${empName}-க்கான வருகை திருத்தம் பதிவு செய்யப்பட்டது.`,
              `Manual attendance entry for ${empName} saved successfully.`
            );
          }
          modal.classList.remove('active');
          loadEntries();
        } else {
          if (window.ArgusVoice) {
            ArgusVoice.announceError(
              'வருகை திருத்தத்தை சேமிப்பதில் பிழை ஏற்பட்டது.',
              d.error || 'Failed to save manual attendance entry.'
            );
          }
          alert(d.error || 'Failed to save entry');
        }
      } catch (err) {
        if (window.hideSavingPopup) window.hideSavingPopup();
        alert('Error saving manual entry: ' + err.message);
      } finally {
        form._isSubmitting = false;
        if (window.hideSavingPopup) window.hideSavingPopup();
        if (btnSubmitManual) {
          btnSubmitManual.disabled = false;
          btnSubmitManual.classList.remove('btn-is-submitting');
          btnSubmitManual.innerHTML = origText;
        }
      }
    });
  }

  // ================= EXPORTS =================
  if (btnCopy) {
    btnCopy.addEventListener('click', function () {
      const table = document.getElementById('manualEntryTable');
      let text = '';
      for (let row of table.rows) {
        let rowData = [];
        for (let cell of row.cells) {
          rowData.push(cell.innerText.trim());
        }
        text += rowData.join('\t') + '\n';
      }
      (window.safeCopyToClipboard ? window.safeCopyToClipboard(text) : navigator.clipboard.writeText(text)).then(() => {
        alert('Manual entries copied to clipboard!');
      }).catch(err => console.error(err));
    });
  }

  if (btnCsv || btnExcel) {
    const handler = function () {
      window.location.href = `/api/manual-entries/export/excel?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}&status=${encodeURIComponent(statusVal)}`;
    };
    if (btnCsv) btnCsv.addEventListener('click', handler);
    if (btnExcel) btnExcel.addEventListener('click', handler);
  }

  if (btnPdf) {
    btnPdf.addEventListener('click', function () {
      window.location.href = `/api/manual-entries/export/pdf?from_date=${encodeURIComponent(fromDate)}&to_date=${encodeURIComponent(toDate)}&status=${encodeURIComponent(statusVal)}`;
    });
  }

  if (btnPrint) {
    btnPrint.addEventListener('click', function () {
      const printContents = document.getElementById('printableManualSection').innerHTML;
      const printWindow = window.open('', '', 'height=600,width=800');
      printWindow.document.write('<html><head><title>Print Manual Entries</title>');
      printWindow.document.write('<style>');
      printWindow.document.write(`
        body { font-family: sans-serif; padding: 20px; }
        h2 { text-align: center; margin-bottom: 20px; font-size: 18px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }
        th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; }
        th { background: #f0f4f8; }
        .salary-positive { color: #198754; font-weight: bold; }
        .btn-action-manual-edit, .btn-action-manual-del { display: none; }
      `);
      printWindow.document.write('</style></head><body>');
      printWindow.document.write('<h2>ARGUS CNC™ - MANUAL ENTRIES</h2>');
      printWindow.document.write(printContents);
      printWindow.document.write('</body></html>');
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => {
        printWindow.print();
        printWindow.close();
      }, 250);
    });
  }

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  if (selectAllManual) {
    selectAllManual.addEventListener('change', function () {
      const isChecked = this.checked;
      tableBody.querySelectorAll('.manual-row-select').forEach(cb => {
        cb.checked = isChecked;
        const id = cb.getAttribute('data-id');
        if (isChecked) {
          selectedManualIds.add(id);
        } else {
          selectedManualIds.delete(id);
        }
      });
      updateBulkBar();
    });
  }

  if (btnClearSelection) {
    btnClearSelection.addEventListener('click', clearSelection);
  }

  if (btnDeleteSelected) {
    btnDeleteSelected.addEventListener('click', async function () {
      const count = selectedManualIds.size;
      if (count === 0) return;
      if (!confirm(`Are you sure you want to permanently delete the ${count} selected manual entries?`)) {
        return;
      }
      btnDeleteSelected.disabled = true;
      btnDeleteSelected.style.opacity = '0.7';
      try {
        const res = await fetch('/api/manual-entries/bulk-delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items: Array.from(selectedManualIds) })
        });
        const d = await res.json();
        if (res.ok && d.success) {
          alert(d.message || `Deleted ${d.deleted_count} manual entries successfully.`);
          clearSelection();
          loadEntries();
        } else {
          alert(d.error || 'Failed to delete selected manual entries.');
        }
      } catch (err) {
        alert('An error occurred during bulk deletion: ' + err.message);
      } finally {
        btnDeleteSelected.disabled = false;
        btnDeleteSelected.style.opacity = '1';
      }
    });
  }

  if (btnOpenDeleteRangeManual) {
    btnOpenDeleteRangeManual.addEventListener('click', async function () {
      if (!fromDate || !toDate) {
        alert('Please select both a From Date and a To Date before deleting by date range.');
        return;
      }
      const promptMsg = `⚠️ DANGER ZONE: BULK DELETE MANUAL ENTRIES BY DATE RANGE\n\n` +
        `You are about to permanently delete ALL manual entries from "${fromDate}" to "${toDate}" (Status: ${statusVal}).\n\n` +
        `Type "DELETE" (all uppercase) to confirm:`;
      const conf = prompt(promptMsg);
      if (conf !== 'DELETE') {
        if (conf !== null) alert('Deletion cancelled: confirmation text did not match "DELETE".');
        return;
      }
      btnOpenDeleteRangeManual.disabled = true;
      btnOpenDeleteRangeManual.style.opacity = '0.7';
      try {
        const res = await fetch('/api/manual-entries/delete-range', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            start_date: fromDate,
            end_date: toDate,
            status: statusVal
          })
        });
        const d = await res.json();
        if (res.ok && d.success) {
          alert(d.message || `Deleted ${d.deleted_count} manual entries in date range.`);
          clearSelection();
          loadEntries();
        } else {
          alert(d.error || 'Failed to delete manual entries by date range.');
        }
      } catch (err) {
        alert('An error occurred while deleting date range manual entries.');
      } finally {
        btnOpenDeleteRangeManual.disabled = false;
        btnOpenDeleteRangeManual.style.opacity = '1';
      }
    });
  }

  // Initial load
  loadEmployees();
  loadEntries();

  // Auto-resume data loading when user switches back to this tab
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      loadEntries();
    }
  });

  // Real-time synchronization with Co-Worker AI
  window.addEventListener('argus:manual-entry-updated', function () {
    loadEntries();
  });

  // Voice AI Field Guidance for Manual Entry Modal
  if (window.ArgusVoice) {
    window.ArgusVoice.bindToggle('btnManualModalToggleVoice');

    window.ArgusVoice.attachFormGuidance('#manualEntryModal', {
      '#inputEmployeeName': {
        english: 'Select the employee for this attendance record.',
        tamil: 'வருகைப் பதிவிற்கான ஊழியரைத் தேர்ந்தெடுக்கவும்.'
      },
      '#inputEntryDate': {
        english: 'Select the date of attendance.',
        tamil: 'வருகைப் பதிவு தேதியைத் தேர்ந்தெடுக்கவும்.'
      },
      '#inputHours': {
        english: 'Enter the working hours in hours and minutes format.',
        tamil: 'வேலை செய்த நேரத்தை மணி மற்றும் நிமிடங்களில் உள்ளிடவும்.'
      },
      '#inputStatus': {
        english: 'Select attendance status: Proper, Permission, or Improper.',
        tamil: 'வருகை நிலையை தேர்ந்தெடுக்கவும்.'
      },
      '#inputReason': {
        english: 'Provide a reason or remarks for manual entry.',
        tamil: 'கைமுறை வருகைப் பதிவிற்கான காரணத்தை உள்ளிடவும்.'
      }
    });
  }
});
