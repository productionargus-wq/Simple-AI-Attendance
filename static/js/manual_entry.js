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

  // Load employee names for modal dropdown
  async function loadEmployees() {
    try {
      const res = await fetch('/api/employees');
      const data = await res.json();
      if (empNameSelect && data.data) {
        empNameSelect.innerHTML = '<option value="" disabled selected>Select</option>';
        data.data.forEach(e => {
          const opt = document.createElement('option');
          opt.value = e.employee_name;
          opt.textContent = e.employee_name;
          empNameSelect.appendChild(opt);
        });
      }
    } catch (err) {
      console.warn('Could not load employees:', err);
    }
  }

  // Load entries from server
  async function loadEntries() {
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

    if (!rows || rows.length === 0) {
      tableBody.innerHTML = `
        <tr>
          <td colspan="10" style="text-align: center; color: #555; padding: 25px;">
            No data available in table
          </td>
        </tr>
      `;
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
      const rawReason = (r.reason || '').trim();
      let statusDisplay = rawStatus;
      if (rawReason) {
        if (rawReason.startsWith('(') && rawReason.endsWith(')')) {
          statusDisplay = `${rawStatus} ${rawReason}`;
        } else {
          statusDisplay = `${rawStatus} (${rawReason})`;
        }
      }

      tr.innerHTML = `
        <td class="col-wrap" style="white-space: normal !important; word-break: break-word !important; min-width: 140px;">${escapeHtml(r.employee_name)}</td>
        <td>${escapeHtml(r.entry_date || '')}</td>
        <td>${hoursDisplay}</td>
        <td class="col-wrap" style="white-space: normal !important; word-break: break-word !important; min-width: 120px;">${escapeHtml(statusDisplay)}</td>
        <td>${escapeHtml(r.submitted_at || '')}</td>
        <td>${Number(r.hourly_rate || 0).toFixed(0)}</td>
        <td>${Number(r.day_rate || 0).toFixed(0)}</td>
        <td>${Number(r.half_rate || 0).toFixed(0)}</td>
        <td><span class="${salClass}">${salDisplay}</span></td>
        <td>
          <button class="btn-action-manual-edit" onclick="editManualEntry(${r.id})">Edit</button>
          <button class="btn-action-manual-del" onclick="deleteManualEntry(${r.id}, '${escapeHtml(r.employee_name)}')">Del</button>
        </td>
      `;
      tableBody.appendChild(tr);
    });
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

      const url = id ? `/api/manual-entries/${id}` : '/api/manual-entries';
      const method = id ? 'PUT' : 'POST';

      try {
        const res = await fetch(url, {
          method: method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(formData)
        });

        const d = await res.json();
        if (res.ok && d.success) {
          modal.classList.remove('active');
          loadEntries();
        } else {
          alert(d.error || 'Failed to save entry');
        }
      } catch (err) {
        alert('Error saving manual entry: ' + err.message);
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
      printWindow.document.write('<h2>ARGUS TECHNOLOGIES - MANUAL ENTRIES</h2>');
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

  // Initial load
  loadEmployees();
  loadEntries();
});
