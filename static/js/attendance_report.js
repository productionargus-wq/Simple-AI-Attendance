// Attendance Report Script: Manages All, Proper, Improper, Manual, and Simple Table views
document.addEventListener('DOMContentLoaded', function () {
  let currentView = 'all'; // 'all', 'proper', 'improper', 'manual', 'simple'
  let currentPage = 1;
  let currentLimit = 10;
  let currentSearch = '';
  let startDate = '';
  let endDate = '';
  let employeeName = 'All';

  // Check URL query parameters
  const urlParams = new URLSearchParams(window.location.search);
  const paramView = urlParams.get('tab') || urlParams.get('view');
  if (['all', 'proper', 'improper', 'manual', 'compact', 'simple'].includes(paramView)) {
    currentView = (paramView === 'simple') ? 'compact' : paramView;
  }

  // DOM Elements
  const pageTitle = document.getElementById('pageTitle');
  const reportSubtitle = document.getElementById('reportSubtitle');
  const standardTableContainer = document.getElementById('standardTableContainer');
  const simpleTableContainer = document.getElementById('simpleTableContainer');

  const btnAllEntries = document.getElementById('btnAllEntries');
  const btnProperEntries = document.getElementById('btnProperEntries');
  const btnImproperEntries = document.getElementById('btnImproperEntries');
  const btnManualEntries = document.getElementById('btnManualEntries');
  const btnCompactView = document.getElementById('btnCompactView') || document.getElementById('btnSimpleTable');
  const btnSimpleTable = btnCompactView;
  const btnUpdateData = document.getElementById('btnUpdateData');

  const startDateInput = document.getElementById('startDate');
  const endDateInput = document.getElementById('endDate');
  const employeeFilterInput = document.getElementById('employeeFilter');
  const btnFilter = document.getElementById('btnFilter');
  const btnClear = document.getElementById('btnClear');

  // Standard Table elements
  const entriesLimitSelect = document.getElementById('entriesLimit');
  const searchInput = document.getElementById('tableSearch');
  const standardTableBody = document.getElementById('attendanceStandardTableBody');
  const tableInfoText = document.getElementById('tableInfoText');
  const prevArrowBtn = document.getElementById('prevArrowBtn');
  const nextArrowBtn = document.getElementById('nextArrowBtn');
  const currentPageBtn = document.getElementById('currentPageBtn');

  // Export buttons
  const btnCopy = document.getElementById('btnCopyTable');
  const btnExcel = document.getElementById('btnExportExcel');
  const btnPdf = document.getElementById('btnExportPdf');
  const btnPrint = document.getElementById('btnPrintReport');

  // Simple Table elements
  const simpleEmployeeSelect = document.getElementById('simpleEmployeeSelect');
  const simpleTableBody = document.getElementById('attendanceSimpleTableBody');
  const totalHoursVal = document.getElementById('totalHoursVal');
  const totalSalaryVal = document.getElementById('totalSalaryVal');
  const btnSimpleExcel = document.getElementById('btnSimpleExcel');
  const btnSimplePdf = document.getElementById('btnSimplePdf');
  const btnSimplePrint = document.getElementById('btnSimplePrint');

  // Subtitle dictionary
  const subtitles = {
    'all': 'Displays all attendance records, including Proper, Improper, and Manual entries.',
    'proper': 'Displays valid attendance records where location distance is within 200 meters of the configured office geolocation.',
    'improper': 'Displays attendance records where location distance exceeds 200 meters from the configured office geolocation.',
    'manual': 'Displays attendance records that were entered manually by the administrator.',
    'compact': 'View essential attendance details in a compact format.',
    'simple': 'View essential attendance details in a compact format.'
  };

  const titles = {
    'all': 'ALL ENTRIES',
    'proper': 'PROPER ENTRIES',
    'improper': 'IMPROPER ENTRIES',
    'manual': 'MANUAL ENTRIES',
    'compact': 'COMPACT OVERVIEW',
    'simple': 'COMPACT OVERVIEW'
  };

  const toggleButtons = {
    'all': btnAllEntries,
    'proper': btnProperEntries,
    'improper': btnImproperEntries,
    'manual': btnManualEntries,
    'compact': btnCompactView
  };

  // Populate employee dropdowns
  async function loadEmployeeNames() {
    try {
      const res = await fetch('/api/employees?limit=1000');
      const data = await res.json();
      if (simpleEmployeeSelect && data.data) {
        simpleEmployeeSelect.innerHTML = '<option value="All Employees">All Employees</option>';
        data.data.forEach(emp => {
          const opt = document.createElement('option');
          opt.value = emp.employee_name;
          opt.textContent = emp.employee_name;
          simpleEmployeeSelect.appendChild(opt);
        });
      }
      if (employeeFilterInput && data.data && employeeFilterInput.tagName === 'SELECT' && employeeFilterInput.options.length <= 1) {
        employeeFilterInput.innerHTML = '<option value="All">All</option>';
        data.data.forEach(emp => {
          const opt = document.createElement('option');
          opt.value = emp.employee_name;
          opt.textContent = emp.employee_name;
          employeeFilterInput.appendChild(opt);
        });
      }
    } catch (err) {
      console.warn('Could not load employees:', err);
    }
  }

  // Set View
  function switchView(view) {
    const canonicalView = (view === 'simple') ? 'compact' : view;
    currentView = canonicalView;
    currentPage = 1;

    if (pageTitle) pageTitle.textContent = titles[canonicalView] || titles['compact'] || 'ALL ENTRIES';
    if (reportSubtitle) reportSubtitle.textContent = subtitles[canonicalView] || subtitles['compact'] || '';

    // Update active button classes
    Object.keys(toggleButtons).forEach(key => {
      const btn = toggleButtons[key];
      if (btn) {
        if (key === canonicalView) {
          btn.className = 'btn-toggle-tab active';
        } else {
          btn.className = 'btn-toggle-tab inactive';
        }
      }
    });

    if (canonicalView === 'compact') {
      if (standardTableContainer) standardTableContainer.style.display = 'none';
      if (simpleTableContainer) simpleTableContainer.style.display = 'block';
      if (simpleEmployeeSelect && employeeFilterInput && employeeFilterInput.value && employeeFilterInput.value !== 'All') {
        simpleEmployeeSelect.value = employeeFilterInput.value;
      }
      loadSimpleTable();
    } else {
      if (simpleTableContainer) simpleTableContainer.style.display = 'none';
      if (standardTableContainer) standardTableContainer.style.display = 'block';
      loadStandardTable();
    }
  }

  // Event listeners for toggle buttons
  if (btnAllEntries) btnAllEntries.addEventListener('click', () => switchView('all'));
  if (btnProperEntries) btnProperEntries.addEventListener('click', () => switchView('proper'));
  if (btnImproperEntries) btnImproperEntries.addEventListener('click', () => switchView('improper'));
  if (btnManualEntries) btnManualEntries.addEventListener('click', () => switchView('manual'));
  if (btnCompactView) {
    btnCompactView.addEventListener('click', () => switchView('compact'));
  }

  // Load Standard Table Data (All / Proper / Improper / Manual)
  async function loadStandardTable() {
    try {
      const params = new URLSearchParams({
        type: currentView,
        start_date: startDate,
        end_date: endDate,
        employee: employeeName,
        search: currentSearch,
        page: currentPage,
        limit: currentLimit
      });

      const res = await fetch(`/api/attendance-reports?${params.toString()}`);
      const data = await res.json();

      renderStandardRows(data.data);
      updatePagination(data.total, data.page, data.limit);
    } catch (err) {
      console.error('Failed to load attendance report:', err);
    }
  }

  function renderStatusBadge(statusText) {
    if (!statusText || statusText === '-' || statusText === '----') {
      return '<span style="color: #64748b; font-weight: 600;">-</span>';
    }
    const txt = String(statusText).trim();
    const lower = txt.toLowerCase();
    let badgeClass = 'status-pill status-active';
    if (lower.includes('late')) {
      badgeClass = 'status-pill status-inactive';
    } else if (lower.includes('early')) {
      badgeClass = 'status-pill status-blue';
    } else if (lower.includes('overtime')) {
      badgeClass = 'status-pill status-blue';
    } else if (lower.includes('on time')) {
      badgeClass = 'status-pill status-active';
    }
    return `<span class="${badgeClass}">${escapeHtml(txt)}</span>`;
  }

  function renderStandardRows(rows) {
    if (!standardTableBody) return;
    standardTableBody.innerHTML = '';

    if (!rows || rows.length === 0) {
      standardTableBody.innerHTML = `
        <tr>
          <td colspan="${window.IS_SYSTEM_ADMIN ? 13 : 12}" style="text-align: center; color: #555; padding: 25px;">
            No data available in table
          </td>
        </tr>
      `;
      return;
    }

    rows.forEach(r => {
      const tr = document.createElement('tr');
      const entryStatusVal = (r.is_manual || r.source === 'manual') ? '-' : (r.entry_status || '-');
      const exitStatusVal = (r.is_manual || r.source === 'manual') ? '-' : (r.exit_status || '-');
      const isManual = (r.is_manual || r.entry_type === 'manual' || r.source === 'manual') ? true : false;
      const actionHtml = window.IS_SYSTEM_ADMIN ? `
        <td style="text-align: center; white-space: nowrap;">
          <button class="btn-action-del" data-id="${escapeHtml(r.id || r._id)}" data-manual="${isManual}" data-name="${escapeHtml(r.employee_name)}" title="Delete record" style="padding: 3px 8px; font-size: 11px; background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; border-radius: 4px; cursor: pointer; font-weight: 600;">Del</button>
        </td>
      ` : '';

      tr.innerHTML = `
        <td style="white-space: nowrap;"><strong>${escapeHtml(r.employee_name)}</strong></td>
        <td style="white-space: nowrap;">${escapeHtml(r.entry_time || '')}</td>
        <td class="col-nowrap" data-col="entry_distance" title="${escapeHtml(r.entry_location || '')}" style="white-space: nowrap !important; min-width: 130px;">${escapeHtml(r.entry_distance || '')}</td>
        <td class="col-location" data-col="entry_location" title="${escapeHtml(r.entry_location || '')}" style="min-width: 220px; max-width: 320px; white-space: normal !important; word-break: break-word !important; overflow-wrap: break-word !important; font-size: 11.5px; line-height: 1.4;">
          ${r.entry_location && r.entry_location !== '----' ? '<span style="color: #0284c7; margin-right: 3px;">📍</span>' : ''}${escapeHtml(r.entry_location || '')}
        </td>
        <td class="col-nowrap" data-col="entry_status" style="text-align: center; white-space: nowrap !important; min-width: 120px;">${renderStatusBadge(entryStatusVal)}</td>
        <td style="white-space: nowrap;">${escapeHtml(r.exit_time || '')}</td>
        <td class="col-nowrap" data-col="exit_distance" title="${escapeHtml(r.exit_location || '')}" style="white-space: nowrap !important; min-width: 130px;">${escapeHtml(r.exit_distance || '')}</td>
        <td class="col-location" data-col="exit_location" title="${escapeHtml(r.exit_location || '')}" style="min-width: 220px; max-width: 320px; white-space: normal !important; word-break: break-word !important; overflow-wrap: break-word !important; font-size: 11.5px; line-height: 1.4;">
          ${r.exit_location && r.exit_location !== '----' ? '<span style="color: #0284c7; margin-right: 3px;">📍</span>' : ''}${escapeHtml(r.exit_location || '')}
        </td>
        <td class="col-nowrap" data-col="exit_status" style="text-align: center; white-space: nowrap !important; min-width: 120px;">${renderStatusBadge(exitStatusVal)}</td>
        <td style="white-space: nowrap;">${escapeHtml(r.working_hours || '')}</td>
        <td style="white-space: nowrap;">${escapeHtml(r.shift_variance || '')}</td>
        <td style="white-space: nowrap;">${Number(r.working_salary || 0).toFixed(0)}</td>
        ${actionHtml}
      `;
      standardTableBody.appendChild(tr);
    });
  }

  // Load Simple Table Data
  async function loadSimpleTable() {
    try {
      const empSelectVal = simpleEmployeeSelect ? simpleEmployeeSelect.value : employeeName;
      const curStart = startDateInput ? startDateInput.value.trim() : startDate;
      const curEnd = endDateInput ? endDateInput.value.trim() : endDate;
      const params = new URLSearchParams({
        employee: empSelectVal,
        start_date: curStart,
        end_date: curEnd
      });

      const res = await fetch(`/api/attendance-reports/simple?${params.toString()}`);
      const data = await res.json();

      renderSimpleRows(data.data);
      if (totalHoursVal) totalHoursVal.textContent = data.total_working_hours || '00:00';
      if (totalSalaryVal) totalSalaryVal.textContent = data.total_working_salary || '0.00';
    } catch (err) {
      console.error('Failed to load simple table:', err);
    }
  }

  function renderSimpleRows(rows) {
    if (!simpleTableBody) return;
    simpleTableBody.innerHTML = '';

    if (!rows || rows.length === 0) {
      simpleTableBody.innerHTML = `
        <tr>
          <td colspan="${window.IS_SYSTEM_ADMIN ? 8 : 7}" style="text-align: center; color: #555; padding: 25px;">
            No data available in table
          </td>
        </tr>
      `;
      return;
    }

    rows.forEach(r => {
      const tr = document.createElement('tr');
      // Format Entry Time: e.g. "14/07/2026 05:30:00" -> blue time
      let entryTimeHtml = escapeHtml(r.entry_time || '');
      if (entryTimeHtml.includes(' ')) {
        const parts = entryTimeHtml.split(' ');
        entryTimeHtml = `${parts[0]} <span class="text-time-blue">${parts.slice(1).join(' ')}</span>`;
      }

      const rawStatus = (r.status || 'Manual').trim();
      let statusHtml = '';
      if (rawStatus.toLowerCase() === 'manual') {
        statusHtml = `<span class="text-status-manual">Manual</span>`;
      } else if (rawStatus.toLowerCase() === 'proper') {
        statusHtml = `<span style="color: #16a34a; font-weight: 700;">Proper</span>`;
      } else if (rawStatus.toLowerCase() === 'improper') {
        statusHtml = `<span style="color: #dc2626; font-weight: 700;">Improper</span>`;
      } else {
        statusHtml = `<span class="text-status-manual">${escapeHtml(rawStatus)}</span>`;
      }

      const isManual = (r.is_manual || r.source === 'manual') ? true : false;
      const actionHtml = window.IS_SYSTEM_ADMIN ? `
        <td style="text-align: center; white-space: nowrap;">
          <button class="btn-action-del" data-id="${escapeHtml(r.id || r._id)}" data-manual="${isManual}" data-name="${escapeHtml(r.employee_name)}" title="Delete record" style="padding: 3px 8px; font-size: 11px; background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; border-radius: 4px; cursor: pointer; font-weight: 600;">Del</button>
        </td>
      ` : '';

      tr.innerHTML = `
        <td>${escapeHtml(r.employee_name)}</td>
        <td>${entryTimeHtml}</td>
        <td>${escapeHtml(r.exit_time || '')}</td>
        <td>${escapeHtml(r.working_hours || '')}</td>
        <td>${escapeHtml(r.shift_variance || '')}</td>
        <td>${Number(r.working_salary || 0).toFixed(2)}</td>
        <td>${statusHtml}</td>
        ${actionHtml}
      `;
      simpleTableBody.appendChild(tr);
    });
  }

  function updatePagination(total, page, limit) {
    if (total === 0) {
      tableInfoText.textContent = 'Showing 0 to 0 of 0 entries';
      currentPageBtn.textContent = '1';
      prevArrowBtn.classList.add('disabled');
      nextArrowBtn.classList.add('disabled');
      return;
    }

    const start = (page - 1) * limit + 1;
    const end = Math.min(page * limit, total);
    tableInfoText.textContent = `Showing ${start} to ${end} of ${total} entries`;
    currentPageBtn.textContent = String(page);

    if (page <= 1) {
      prevArrowBtn.classList.add('disabled');
    } else {
      prevArrowBtn.classList.remove('disabled');
    }

    const maxPages = Math.ceil(total / limit);
    if (page >= maxPages) {
      nextArrowBtn.classList.add('disabled');
    } else {
      nextArrowBtn.classList.remove('disabled');
    }
  }

  // Filter Bar Events
  if (btnFilter) {
    btnFilter.addEventListener('click', function () {
      startDate = startDateInput.value.trim();
      endDate = endDateInput.value.trim();
      employeeName = employeeFilterInput.value.trim();
      currentPage = 1;
      if (currentView === 'simple' || currentView === 'compact') {
        loadSimpleTable();
      } else {
        loadStandardTable();
      }
    });
  }

  if (btnClear) {
    btnClear.addEventListener('click', function () {
      startDateInput.value = '';
      endDateInput.value = '';
      employeeFilterInput.value = 'All';
      startDate = '';
      endDate = '';
      employeeName = 'All';
      currentPage = 1;
      if (currentView === 'simple' || currentView === 'compact') {
        if (simpleEmployeeSelect) simpleEmployeeSelect.value = 'All Employees';
        loadSimpleTable();
      } else {
        loadStandardTable();
      }
    });
  }

  if (simpleEmployeeSelect) {
    simpleEmployeeSelect.addEventListener('change', function () {
      loadSimpleTable();
    });
  }

  // Update button event
  if (btnUpdateData) {
    btnUpdateData.addEventListener('click', async function () {
      btnUpdateData.style.opacity = '0.6';
      btnUpdateData.disabled = true;
      try {
        const res = await fetch('/api/attendance-reports/update', { method: 'POST' });
        const d = await res.json();
        if (d.success) {
          alert('Attendance records refreshed successfully!');
          if (currentView === 'simple' || currentView === 'compact') {
            loadSimpleTable();
          } else {
            loadStandardTable();
          }
        }
      } catch (err) {
        console.error('Update failed:', err);
      } finally {
        btnUpdateData.style.opacity = '1';
        btnUpdateData.disabled = false;
      }
    });
  }

  // Search input
  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        currentSearch = searchInput.value.trim();
        currentPage = 1;
        loadStandardTable();
      }, 250);
    });
  }

  // Limit select
  if (entriesLimitSelect) {
    entriesLimitSelect.addEventListener('change', function () {
      currentLimit = parseInt(this.value, 10);
      currentPage = 1;
      loadStandardTable();
    });
  }

  // Pagination navigation
  if (prevArrowBtn) {
    prevArrowBtn.addEventListener('click', function () {
      if (currentPage > 1) {
        currentPage--;
        loadStandardTable();
      }
    });
  }

  if (nextArrowBtn) {
    nextArrowBtn.addEventListener('click', function () {
      currentPage++;
      loadStandardTable();
    });
  }

  // ================= EXPORTS =================

  // Copy
  if (btnCopy) {
    btnCopy.addEventListener('click', function () {
      const table = document.getElementById('attendanceStandardTable');
      let text = '';
      for (let row of table.rows) {
        let rowData = [];
        for (let cell of row.cells) {
          rowData.push(cell.innerText.trim());
        }
        text += rowData.join('\t') + '\n';
      }
      (window.safeCopyToClipboard ? window.safeCopyToClipboard(text) : navigator.clipboard.writeText(text)).then(() => {
        alert('Table data copied to clipboard!');
      }).catch(err => console.error(err));
    });
  }

  // Excel
  if (btnExcel) {
    btnExcel.addEventListener('click', function () {
      window.location.href = `/api/attendance-reports/export/excel?type=${currentView}&start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}&employee=${encodeURIComponent(employeeName)}`;
    });
  }

  if (btnSimpleExcel) {
    btnSimpleExcel.addEventListener('click', function () {
      const emp = simpleEmployeeSelect ? simpleEmployeeSelect.value : 'All Employees';
      const curStart = startDateInput ? startDateInput.value.trim() : startDate;
      const curEnd = endDateInput ? endDateInput.value.trim() : endDate;
      window.location.href = `/api/attendance-reports/export/excel?type=compact&start_date=${encodeURIComponent(curStart)}&end_date=${encodeURIComponent(curEnd)}&employee=${encodeURIComponent(emp)}`;
    });
  }

  // PDF
  if (btnPdf) {
    btnPdf.addEventListener('click', function () {
      window.location.href = `/api/attendance-reports/export/pdf?type=${currentView}&start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}&employee=${encodeURIComponent(employeeName)}`;
    });
  }

  if (btnSimplePdf) {
    btnSimplePdf.addEventListener('click', function () {
      const emp = simpleEmployeeSelect ? simpleEmployeeSelect.value : 'All Employees';
      const curStart = startDateInput ? startDateInput.value.trim() : startDate;
      const curEnd = endDateInput ? endDateInput.value.trim() : endDate;
      window.location.href = `/api/attendance-reports/export/pdf?type=compact&start_date=${encodeURIComponent(curStart)}&end_date=${encodeURIComponent(curEnd)}&employee=${encodeURIComponent(emp)}`;
    });
  }

  // Print
  if (btnPrint) {
    btnPrint.addEventListener('click', function () {
      printTable('printableStandardSection', titles[currentView]);
    });
  }

  if (btnSimplePrint) {
    btnSimplePrint.addEventListener('click', function () {
      printTable('printableSimpleSection', 'COMPACT OVERVIEW');
    });
  }

  function printTable(elementId, title) {
    const printContents = document.getElementById(elementId).innerHTML;
    const printWindow = window.open('', '', 'height=600,width=800');
    printWindow.document.write('<html><head><title>Print Attendance Report</title>');
    printWindow.document.write('<style>');
    printWindow.document.write(`
      body { font-family: sans-serif; padding: 20px; }
      h2 { text-align: center; margin-bottom: 20px; font-size: 18px; }
      table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }
      th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }
      th { background: #2c3e50; color: #fff; }
      .row-total td { background: #e9ecef; font-weight: bold; }
    `);
    printWindow.document.write('</style></head><body>');
    const compName = document.querySelector('.nav-title')?.innerText?.trim() || 'ARGUS TECHNOLOGIES';
    printWindow.document.write(`<h2>${compName} - ${title}</h2>`);
    printWindow.document.write(printContents);
    printWindow.document.write('</body></html>');
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
    }, 250);
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

  // Handle Attendance Deletion (System Admin only)
  async function handleAttendanceDelete(e) {
    const delBtn = e.target.closest('.btn-action-del');
    if (!delBtn) return;
    const recId = delBtn.dataset.id;
    const isManual = delBtn.dataset.manual === 'true';
    const empName = delBtn.dataset.name || 'this employee';
    if (!recId) return;

    if (!confirm(`Are you sure you want to delete this attendance record for "${empName}"? This action cannot be undone.`)) {
      return;
    }

    try {
      const res = await fetch(`/api/attendance-reports/${recId}?is_manual=${isManual}`, {
        method: 'DELETE'
      });
      const result = await res.json();
      if (res.ok && result.success) {
        if (currentView === 'compact') {
          loadSimpleTable();
        } else {
          loadStandardTable();
        }
      } else {
        alert(result.error || 'Failed to delete record');
      }
    } catch (err) {
      console.error('Delete error:', err);
      alert('An error occurred while deleting the record.');
    }
  }

  if (standardTableBody) standardTableBody.addEventListener('click', handleAttendanceDelete);
  if (simpleTableBody) simpleTableBody.addEventListener('click', handleAttendanceDelete);

  // Init
  loadEmployeeNames();
  switchView(currentView);
});
