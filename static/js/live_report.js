// Live Report & Timeout Entries Script
document.addEventListener('DOMContentLoaded', function () {
  let currentType = 'live'; // 'live' or 'timeout'
  let currentPage = 1;
  let currentLimit = 10;
  let currentSearch = '';
  let startDate = '';
  let endDate = '';

  // Check query parameter if initial tab specified
  const urlParams = new URLSearchParams(window.location.search);
  if (urlParams.get('type') === 'timeout' || urlParams.get('tab') === 'timeout') {
    currentType = 'timeout';
  }

  // DOM Elements
  const pageTitle = document.getElementById('pageTitle');
  const reportSubtitle = document.getElementById('reportSubtitle');
  const btnLiveEntries = document.getElementById('btnLiveEntries');
  const btnTimeoutEntries = document.getElementById('btnTimeoutEntries');
  const colTimeHeader = document.getElementById('colTimeHeader');
  const colLocationHeader = document.getElementById('colLocationHeader');
  const colDistanceHeader = document.getElementById('colDistanceHeader');
  const colStatusHeader = document.getElementById('colStatusHeader');
  
  const startDateInput = document.getElementById('startDate');
  const endDateInput = document.getElementById('endDate');
  const btnFilter = document.getElementById('btnFilter');
  const btnClear = document.getElementById('btnClear');

  const entriesLimitSelect = document.getElementById('entriesLimit');
  const searchInput = document.getElementById('tableSearch');
  const tableBody = document.getElementById('liveReportTableBody');
  const tableInfoText = document.getElementById('tableInfoText');
  const prevArrowBtn = document.getElementById('prevArrowBtn');
  const nextArrowBtn = document.getElementById('nextArrowBtn');

  const btnCopy = document.getElementById('btnCopyTable');
  const btnExcel = document.getElementById('btnExportExcel');
  const btnPdf = document.getElementById('btnExportPdf');
  const btnPrint = document.getElementById('btnPrintReport');

  // Bulk actions elements
  const bulkBar = document.getElementById('bulkActionsBar');
  const selectedCountBadge = document.getElementById('selectedCountBadge');
  const btnSelectedCount = document.getElementById('btnSelectedCount');
  const btnClearSelection = document.getElementById('btnClearSelection');
  const btnDeleteSelected = document.getElementById('btnDeleteSelected');
  const selectAllLive = document.getElementById('selectAllLive');
  const selectedLiveIds = new Set();

  function updateBulkBar() {
    const count = selectedLiveIds.size;
    if (bulkBar) {
      bulkBar.style.display = count > 0 ? 'flex' : 'none';
    }
    if (selectedCountBadge) selectedCountBadge.textContent = count;
    if (btnSelectedCount) btnSelectedCount.textContent = count;
    if (selectAllLive) {
      const pageCheckboxes = document.querySelectorAll('.live-row-select');
      if (pageCheckboxes.length > 0) {
        selectAllLive.checked = Array.from(pageCheckboxes).every(cb => cb.checked);
      } else {
        selectAllLive.checked = false;
      }
    }
  }

  function clearSelection() {
    selectedLiveIds.clear();
    document.querySelectorAll('.live-row-select').forEach(cb => cb.checked = false);
    if (selectAllLive) selectAllLive.checked = false;
    updateBulkBar();
  }

  // Switch View
  function setView(type) {
    currentType = type;
    currentPage = 1;
    clearSelection();

    if (currentType === 'live') {
      pageTitle.textContent = 'LIVE ENTRIES';
      reportSubtitle.textContent = 'Displays employees who are punched-in and currently working.';
      btnLiveEntries.className = 'btn-toggle-tab active';
      btnTimeoutEntries.className = 'btn-toggle-tab inactive';
      if (colTimeHeader) {
        colTimeHeader.innerHTML = 'ENTRY TIME <span class="sort-icon">⇅</span>';
      }
      if (colLocationHeader) {
        colLocationHeader.innerHTML = 'ENTRY LOCATION <span class="sort-icon">⇅</span>';
      }
      if (colDistanceHeader) {
        colDistanceHeader.innerHTML = 'ENTRY DISTANCE <span class="sort-icon">⇅</span>';
      }
      if (colStatusHeader) {
        colStatusHeader.innerHTML = 'ENTRY STATUS <span class="sort-icon">⇅</span>';
      }
    } else {
      pageTitle.textContent = 'TIMEOUT ENTRIES';
      reportSubtitle.textContent = 'Displays employees who have punched out (manual punch-out and automatic checkout).';
      btnTimeoutEntries.className = 'btn-toggle-tab active';
      btnLiveEntries.className = 'btn-toggle-tab inactive';
      if (colTimeHeader) {
        colTimeHeader.innerHTML = 'EXIT TIME <span class="sort-icon">⇅</span>';
      }
      if (colLocationHeader) {
        colLocationHeader.innerHTML = 'EXIT LOCATION <span class="sort-icon">⇅</span>';
      }
      if (colDistanceHeader) {
        colDistanceHeader.innerHTML = 'EXIT DISTANCE <span class="sort-icon">⇅</span>';
      }
      if (colStatusHeader) {
        colStatusHeader.innerHTML = 'EXIT STATUS <span class="sort-icon">⇅</span>';
      }
    }

    loadEntries();
  }

  if (btnLiveEntries) btnLiveEntries.addEventListener('click', () => setView('live'));
  if (btnTimeoutEntries) btnTimeoutEntries.addEventListener('click', () => setView('timeout'));

  // Load Data
  async function loadEntries() {
    if (!tableBody) return;
    try {
      const params = new URLSearchParams({
        type: currentType,
        search: currentSearch,
        start_date: startDate,
        end_date: endDate,
        page: currentPage,
        limit: currentLimit
      });

      const res = await fetch(`/api/live-entries?${params.toString()}`);
      const data = await res.json();

      renderRows(data.data);
      updatePagination(data.total, data.page, data.limit);
    } catch (err) {
      console.error('Failed to load live entries:', err);
    }
  }

  function renderStatusBadge(statusText) {
    if (!statusText || statusText === '-' || statusText === '----') {
      return '<span style="color: #64748b; font-weight: 600;">-</span>';
    }
    const txt = String(statusText).trim();
    const lower = txt.toLowerCase();
    if (lower.includes('leave')) {
      return `<span class="table-badge badge-leave">${escapeHtml(txt)}</span>`;
    }
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

  function renderRows(entries) {
    if (!tableBody) return;
    tableBody.innerHTML = '';

    const canDelete = Boolean(window.CAN_DELETE_ENTRIES || window.IS_SYSTEM_ADMIN);
    const colCount = canDelete ? 7 : 5;

    if (!entries || entries.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="${colCount}" style="text-align: center; color: #555; padding: 25px; font-size: 13px;">
            No data available in table
          </td>
        </tr>
      `;
      updateBulkBar();
      return;
    }

    entries.forEach(entry => {
      const tr = document.createElement('tr');
      let distStr = (entry.formatted_distance !== undefined && entry.formatted_distance !== null) ? String(entry.formatted_distance).trim() : '';
      if (!distStr) {
        if (entry.entry_distance !== undefined && entry.entry_distance !== null && String(entry.entry_distance).trim() !== '' && String(entry.entry_distance).trim() !== '----' && String(entry.entry_distance).trim() !== '-') {
          const dNum = parseFloat(entry.entry_distance);
          if (!Number.isNaN(dNum)) {
            distStr = dNum >= 1000 ? `OFFICE DISTANCE ${(dNum / 1000).toFixed(2)}KM` : `OFFICE DISTANCE ${dNum.toFixed(1)}M`;
          } else {
            distStr = String(entry.entry_distance);
          }
        } else {
          distStr = '----';
        }
      }

      const timeDisplay = (currentType === 'timeout' && entry.exit_time) ? entry.exit_time : (entry.entry_time || '----');
      const locDisplay = (currentType === 'timeout' && entry.exit_location) ? entry.exit_location : (entry.entry_location || '----');
      const distDisplay = (currentType === 'timeout' && entry.exit_distance && entry.exit_distance !== '----') ? entry.exit_distance : distStr;
      const statusDisplay = (currentType === 'timeout' && entry.exit_status) ? entry.exit_status : (entry.entry_status || '-');

      const entryId = String(entry.id || entry._id);
      const isChecked = selectedLiveIds.has(entryId);
      const chkCol = canDelete
        ? `<td style="text-align: center;"><input type="checkbox" class="live-row-select" data-id="${escapeHtml(entryId)}" ${isChecked ? 'checked' : ''} style="cursor: pointer; width: 16px; height: 16px; accent-color: #dc2626;"></td>`
        : '';

      const actionHtml = canDelete ? `
        <td style="text-align: center; white-space: nowrap;">
          <button class="btn-action-del" data-id="${escapeHtml(entryId)}" data-name="${escapeHtml(entry.employee_name)}" title="Delete entry" style="padding: 3px 8px; font-size: 11px; background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; border-radius: 4px; cursor: pointer; font-weight: 600;">Del</button>
        </td>
      ` : '';

      tr.innerHTML = `
        ${chkCol}
        <td class="sticky-col-emp" style="white-space: nowrap;"><strong>${escapeHtml(entry.employee_name)}</strong></td>
        <td style="white-space: nowrap;">${escapeHtml(timeDisplay)}</td>
        <td class="col-location" data-col="entry_location" title="${escapeHtml(locDisplay)}" style="min-width: 220px; max-width: 320px; white-space: normal !important; word-break: break-word !important; overflow-wrap: break-word !important; font-size: 11.5px; line-height: 1.4;">
          ${locDisplay && locDisplay !== '----' ? '<span style="color: #0284c7; margin-right: 3px;">📍</span>' : ''}${escapeHtml(locDisplay)}
        </td>
        <td class="col-nowrap" data-col="entry_distance" title="${escapeHtml(locDisplay)}" style="white-space: nowrap !important; min-width: 140px;">${escapeHtml(distDisplay)}</td>
        <td class="col-nowrap" data-col="entry_status" style="text-align: center; white-space: nowrap !important; min-width: 120px;">${renderStatusBadge(statusDisplay)}</td>
        ${actionHtml}
      `;
      tableBody.appendChild(tr);
    });

    tableBody.querySelectorAll('.live-row-select').forEach(cb => {
      cb.addEventListener('change', function () {
        const id = this.getAttribute('data-id');
        if (this.checked) {
          selectedLiveIds.add(id);
        } else {
          selectedLiveIds.delete(id);
        }
        updateBulkBar();
      });
    });
    updateBulkBar();
  }

  function updatePagination(total, page, limit) {
    if (total === 0) {
      tableInfoText.textContent = 'Showing 0 to 0 of 0 entries';
      prevArrowBtn.classList.add('disabled');
      nextArrowBtn.classList.add('disabled');
      return;
    }

    const start = (page - 1) * limit + 1;
    const end = Math.min(page * limit, total);
    tableInfoText.textContent = `Showing ${start} to ${end} of ${total} entries`;

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

  // Filter & Clear
  if (btnFilter) {
    btnFilter.addEventListener('click', function () {
      startDate = startDateInput.value.trim();
      endDate = endDateInput.value.trim();
      currentPage = 1;
      loadEntries();
    });
  }

  if (btnClear) {
    btnClear.addEventListener('click', function () {
      startDateInput.value = '';
      endDateInput.value = '';
      startDate = '';
      endDate = '';
      currentPage = 1;
      loadEntries();
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
        loadEntries();
      }, 250);
    });
  }

  // Limit select
  if (entriesLimitSelect) {
    entriesLimitSelect.addEventListener('change', function () {
      currentLimit = parseInt(this.value, 10);
      currentPage = 1;
      loadEntries();
    });
  }

  // Pagination arrows
  if (prevArrowBtn) {
    prevArrowBtn.addEventListener('click', function () {
      if (currentPage > 1) {
        currentPage--;
        loadEntries();
      }
    });
  }

  if (nextArrowBtn) {
    nextArrowBtn.addEventListener('click', function () {
      currentPage++;
      loadEntries();
    });
  }

  // ================= EXPORT ACTIONS =================

  // 1. Copy table
  if (btnCopy) {
    btnCopy.addEventListener('click', function () {
      const table = document.getElementById('liveReportTable');
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
      }).catch(err => {
        console.error('Copy failed:', err);
      });
    });
  }

  // 2. Export Excel (CSV)
  if (btnExcel) {
    btnExcel.addEventListener('click', function () {
      window.location.href = `/api/live-entries/export/excel?type=${currentType}&start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
    });
  }

  // 3. Export PDF
  if (btnPdf) {
    btnPdf.addEventListener('click', function () {
      window.location.href = `/api/live-entries/export/pdf?type=${currentType}&start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
    });
  }

  // 4. Print table
  if (btnPrint) {
    btnPrint.addEventListener('click', function () {
      const printContents = document.getElementById('printableTableSection').innerHTML;
      const printWindow = window.open('', '', 'height=600,width=800');
      printWindow.document.write('<html><head><title>Print Report</title>');
      printWindow.document.write('<style>');
      printWindow.document.write(`
        body { font-family: sans-serif; padding: 20px; }
        h2 { text-align: center; margin-bottom: 20px; text-transform: uppercase; font-size: 18px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ccc; padding: 8px 12px; font-size: 12px; text-align: left; }
        th { background: #f0f4f8; }
      `);
      printWindow.document.write('</style></head><body>');
      const compName = document.querySelector('.nav-title')?.innerText?.trim() || 'ARGUS CNC™';
      printWindow.document.write(`<h2>${compName} - ${currentType === 'live' ? 'LIVE ENTRIES' : 'TIMEOUT ENTRIES'}</h2>`);
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

  // Handle Delete (System Admin only)
  if (tableBody) {
    tableBody.addEventListener('click', async function (e) {
      const delBtn = e.target.closest('.btn-action-del');
      if (!delBtn) return;
      const entryId = delBtn.dataset.id;
      const empName = delBtn.dataset.name || 'this employee';
      if (!entryId) return;

      if (!confirm(`Are you sure you want to delete the ${currentType} entry for "${empName}"? This action cannot be undone.`)) {
        return;
      }

      try {
        const res = await fetch(`/api/live-entries/${entryId}?type=${currentType}`, {
          method: 'DELETE'
        });
        const result = await res.json();
        if (res.ok && result.success) {
          loadEntries();
        } else {
          alert(result.error || 'Failed to delete entry');
        }
      } catch (err) {
        console.error('Delete error:', err);
        alert('An error occurred while deleting the entry.');
      }
    });
  }

  if (selectAllLive) {
    selectAllLive.addEventListener('change', function () {
      const isChecked = this.checked;
      tableBody.querySelectorAll('.live-row-select').forEach(cb => {
        cb.checked = isChecked;
        const id = cb.getAttribute('data-id');
        if (isChecked) {
          selectedLiveIds.add(id);
        } else {
          selectedLiveIds.delete(id);
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
      const count = selectedLiveIds.size;
      if (count === 0) return;
      if (!confirm(`Are you sure you want to permanently delete the ${count} selected ${currentType} entries?`)) {
        return;
      }
      btnDeleteSelected.disabled = true;
      btnDeleteSelected.style.opacity = '0.7';
      try {
        const res = await fetch('/api/live-entries/bulk-delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items: Array.from(selectedLiveIds) })
        });
        const d = await res.json();
        if (res.ok && d.success) {
          alert(d.message || `Deleted ${d.deleted_count} live entries successfully.`);
          clearSelection();
          loadEntries();
        } else {
          alert(d.error || 'Failed to delete selected live entries.');
        }
      } catch (err) {
        alert('An error occurred during bulk deletion: ' + err.message);
      } finally {
        btnDeleteSelected.disabled = false;
        btnDeleteSelected.style.opacity = '1';
      }
    });
  }

  // Initial trigger
  setView(currentType);
});
