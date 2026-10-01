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

  // Switch View
  function setView(type) {
    currentType = type;
    currentPage = 1;

    if (currentType === 'live') {
      pageTitle.textContent = 'LIVE ENTRIES';
      reportSubtitle.textContent = 'Displays employees who are punched-in and currently working.';
      btnLiveEntries.className = 'btn-toggle-tab active';
      btnTimeoutEntries.className = 'btn-toggle-tab inactive';
      if (colTimeHeader) {
        colTimeHeader.innerHTML = 'ENTRY TIME <span class="sort-icon">⇅</span>';
      }
    } else {
      pageTitle.textContent = 'TIMEOUT ENTRIES';
      reportSubtitle.textContent = 'Displays employees who have punched out (manual punch-out and automatic checkout).';
      btnTimeoutEntries.className = 'btn-toggle-tab active';
      btnLiveEntries.className = 'btn-toggle-tab inactive';
      if (colTimeHeader) {
        colTimeHeader.innerHTML = 'EXIT TIME <span class="sort-icon">⇅</span>';
      }
    }

    loadEntries();
  }

  btnLiveEntries.addEventListener('click', () => setView('live'));
  btnTimeoutEntries.addEventListener('click', () => setView('timeout'));

  // Load Data
  async function loadEntries() {
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

  function renderRows(entries) {
    if (!tableBody) return;
    tableBody.innerHTML = '';

    if (!entries || entries.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="5" style="text-align: center; color: #555; padding: 25px; font-size: 13px;">
            No data available in table
          </td>
        </tr>
      `;
      return;
    }

    entries.forEach(entry => {
      const tr = document.createElement('tr');
      let distStr = entry.formatted_distance;
      if (!distStr) {
        const dNum = parseFloat(entry.entry_distance || 0);
        distStr = dNum >= 1000 ? `OFFICE DISTANCE ${(dNum / 1000).toFixed(2)}KM` : `OFFICE DISTANCE ${dNum.toFixed(1)}M`;
      }

      const timeDisplay = (currentType === 'timeout' && entry.exit_time) ? entry.exit_time : (entry.entry_time || '----');

      let siteBadge = escapeHtml(entry.site_name || '----');
      if (entry.site_name && entry.site_name.includes('PUNCH OUT')) {
        siteBadge = `<span style="background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">${escapeHtml(entry.site_name)}</span>`;
      } else if (entry.site_name && entry.site_name.includes('AUTO TIMEOUT')) {
        siteBadge = `<span style="background: #fef3c7; color: #b45309; padding: 2px 8px; border-radius: 4px; font-weight: 600; font-size: 11px;">${escapeHtml(entry.site_name)}</span>`;
      }

      tr.innerHTML = `
        <td><strong>${escapeHtml(entry.employee_name)}</strong></td>
        <td>${escapeHtml(timeDisplay)}</td>
        <td>${siteBadge}</td>
        <td>${escapeHtml(entry.entry_location || '----')}</td>
        <td>${escapeHtml(distStr)}</td>
      `;
      tableBody.appendChild(tr);
    });
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
      const compName = document.querySelector('.nav-title')?.innerText?.trim() || 'ARGUS TECHNOLOGIES';
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

  // Initial trigger
  setView(currentType);
});
