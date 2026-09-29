// Employee Details Script: Table management, search, sort, pagination, modals (Add/Edit/View/Delete)
document.addEventListener('DOMContentLoaded', function () {
  let currentPage = 1;
  let currentLimit = 10;
  let currentSearch = '';
  let currentSortCol = 'id';
  let currentSortDir = 'desc';
  let currentViewingEmpId = null;

  // DOM Elements
  const tableBody = document.getElementById('employeeTableBody');
  const tableInfoText = document.getElementById('tableInfoText');
  const searchInput = document.getElementById('tableSearch');
  const limitSelect = document.getElementById('entriesLimit');
  const prevBtn = document.getElementById('prevPageBtn');
  const nextBtn = document.getElementById('nextPageBtn');
  const currentPageBtn = document.getElementById('currentPageBtn');

  // Modals
  const entryModal = document.getElementById('entryModal');
  const viewModal = document.getElementById('viewModal');
  const photoModal = document.getElementById('photoModal');

  // Modal triggers & buttons
  const btnOpenNewEntry = document.getElementById('btnOpenNewEntryModal');
  const closeEntryModalBtn = document.getElementById('closeEntryModal');
  const closeViewModalBtn = document.getElementById('closeViewModal');
  const closePhotoModalBtn = document.getElementById('closePhotoModal');
  const employeeForm = document.getElementById('employeeForm');
  const btnResetForm = document.getElementById('btnResetForm');
  const btnPrintDetail = document.getElementById('btnPrintDetail');
  const btnDownloadPdf = document.getElementById('btnDownloadPdf');

  // List vs Grid View Toggle Elements
  let currentView = 'list';
  let currentEmployees = [];
  const btnListView = document.getElementById('btnListView');
  const btnGridView = document.getElementById('btnGridView');
  const employeeListSection = document.getElementById('employeeListSection');
  const employeeGridSection = document.getElementById('employeeGridSection');

  if (btnListView && btnGridView) {
    btnListView.addEventListener('click', function () {
      currentView = 'list';
      btnListView.className = 'btn-toggle-tab active';
      btnGridView.className = 'btn-toggle-tab inactive';
      if (employeeListSection) employeeListSection.style.display = 'block';
      if (employeeGridSection) employeeGridSection.style.display = 'none';
      renderTableRows(currentEmployees);
    });

    btnGridView.addEventListener('click', function () {
      currentView = 'grid';
      btnGridView.className = 'btn-toggle-tab active';
      btnListView.className = 'btn-toggle-tab inactive';
      if (employeeListSection) employeeListSection.style.display = 'none';
      if (employeeGridSection) employeeGridSection.style.display = 'grid';
      renderGridCards(currentEmployees);
    });
  }

  // Fetch and render data
  async function loadEmployees() {
    try {
      const url = `/api/employees?search=${encodeURIComponent(currentSearch)}&sort_col=${currentSortCol}&sort_dir=${currentSortDir}&page=${currentPage}&limit=${currentLimit}`;
      const res = await fetch(url);
      const data = await res.json();

      currentEmployees = data.data || [];
      if (currentView === 'grid') {
        renderGridCards(currentEmployees);
      } else {
        renderTableRows(currentEmployees);
      }
      updatePagination(data.total, data.page, data.limit);
    } catch (err) {
      console.error('Failed to load employees:', err);
    }
  }

  function renderTableRows(employees) {
    if (!tableBody) return;
    tableBody.innerHTML = '';

    if (!employees || employees.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="13" style="text-align: center; padding: 20px; color: #888;">No matching records found</td></tr>`;
      return;
    }

    employees.forEach(emp => {
      const tr = document.createElement('tr');

      const st = emp.salary_type || 'hourly';
      let badgeHtml = '';
      if (st === 'hourly') {
        badgeHtml = '<span style="background:#e0f2fe; color:#0369a1; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:700;">Hourly</span>';
      } else if (st === 'daily') {
        badgeHtml = '<span style="background:#dcfce7; color:#15803d; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:700;">Day-Based</span>';
      } else if (st === 'half_day') {
        badgeHtml = '<span style="background:#fef3c7; color:#b45309; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:700;">Half-Day</span>';
      } else {
        badgeHtml = '<span style="background:#f1f5f9; color:#475569; padding:3px 8px; border-radius:12px; font-size:11px; font-weight:700;">Hourly</span>';
      }

      const photoFile = emp.photo || emp.photo_filename;
      let photoHtml = '';
      if (photoFile) {
        photoHtml = `<img src="/uploads/${escapeHtml(photoFile)}" class="emp-table-photo" onclick="openPhotoModal('${escapeHtml(photoFile)}', '${escapeHtml(emp.employee_name)}')" title="Click to view photo">`;
      } else {
        const initials = (emp.employee_name || 'E').substring(0, 2).toUpperCase();
        photoHtml = `<div class="emp-avatar-placeholder">${initials}</div>`;
      }

      tr.innerHTML = `
        <td>${escapeHtml(emp.id)}</td>
        <td style="text-align: center; vertical-align: middle;">${photoHtml}</td>
        <td>${escapeHtml(emp.employee_name)}</td>
        <td>${escapeHtml(emp.designation || '')}</td>
        <td>${badgeHtml}</td>
        <td>${Number(emp.hourly_salary || 0).toFixed(2)}</td>
        <td>${Number(emp.day_salary || 0).toFixed(0)}</td>
        <td>${Number(emp.half_day_salary || 0).toFixed(0)}</td>
        <td>${escapeHtml(emp.mobile_number || '')}</td>
        <td>${escapeHtml(emp.email_id || '')}</td>
        <td>${escapeHtml(emp.shift_hours || '')}</td>
        <td>
          <button class="btn-action btn-action-view" onclick="viewEmployee('${emp.id}')" title="View">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
          </button>
        </td>
        <td>
          <button class="btn-action btn-action-edit" onclick="editEmployee('${emp.id}')" title="Edit">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
          </button>
        </td>
        <td>
          <button class="btn-action btn-action-delete" onclick="deleteEmployee('${emp.id}', '${escapeHtml(emp.employee_name)}')" title="Delete">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </td>
      `;
      tableBody.appendChild(tr);
    });
  }

  function renderGridCards(employees) {
    if (!employeeGridSection) return;
    employeeGridSection.innerHTML = '';
    if (!employees || employees.length === 0) {
      employeeGridSection.innerHTML = `<div style="grid-column: 1/-1; text-align: center; padding: 30px; color: #888;">No matching records found</div>`;
      return;
    }

    employees.forEach(emp => {
      const card = document.createElement('div');
      card.className = 'emp-grid-card';

      const photoFile = emp.photo || emp.photo_filename;
      let photoImgHtml = '';
      if (photoFile) {
        photoImgHtml = `<img src="/uploads/${escapeHtml(photoFile)}" class="emp-grid-photo" onclick="openPhotoModal('${escapeHtml(photoFile)}', '${escapeHtml(emp.employee_name)}')" title="Click to view photo">`;
      } else {
        const initials = (emp.employee_name || 'E').substring(0, 2).toUpperCase();
        photoImgHtml = `<div class="emp-grid-avatar-placeholder">${initials}</div>`;
      }

      const st = emp.salary_type || 'hourly';
      let salaryRateDisplay = `₹${Number(emp.hourly_salary || 0).toFixed(0)}/hr`;
      if (st === 'daily') salaryRateDisplay = `₹${Number(emp.day_salary || 0).toFixed(0)}/day`;
      else if (st === 'half_day') salaryRateDisplay = `₹${Number(emp.half_day_salary || 0).toFixed(0)}/half-day`;

      card.innerHTML = `
        <div class="emp-grid-header">
          ${photoImgHtml}
          <div style="flex: 1; min-width: 0;">
            <div class="emp-grid-info-title">${escapeHtml(emp.employee_name)}</div>
            <div class="emp-grid-info-sub">${escapeHtml(emp.designation || 'Staff')} &bull; ID: ${escapeHtml(emp.id)}</div>
          </div>
        </div>
        <div class="emp-grid-body">
          <div class="emp-grid-row">
            <span class="emp-grid-label">Salary Basis:</span>
            <span class="emp-grid-val">${salaryRateDisplay}</span>
          </div>
          <div class="emp-grid-row">
            <span class="emp-grid-label">Mobile:</span>
            <span class="emp-grid-val">${escapeHtml(emp.mobile_number || '-')}</span>
          </div>
          <div class="emp-grid-row">
            <span class="emp-grid-label">Email:</span>
            <span class="emp-grid-val" style="font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 160px;" title="${escapeHtml(emp.email_id || '-')}">${escapeHtml(emp.email_id || '-')}</span>
          </div>
          <div class="emp-grid-row">
            <span class="emp-grid-label">Shift Hours:</span>
            <span class="emp-grid-val">${escapeHtml(emp.shift_hours || '09:00')}</span>
          </div>
          ${emp.shift_start || emp.shift_end ? `
          <div class="emp-grid-row">
            <span class="emp-grid-label">Shift Timing:</span>
            <span class="emp-grid-val">${escapeHtml(emp.shift_start || '09:00 AM')} - ${escapeHtml(emp.shift_end || '06:00 PM')}</span>
          </div>` : ''}
        </div>
        <div class="emp-grid-actions">
          <button class="btn-action btn-action-view" onclick="viewEmployee('${emp.id}')" title="View Details">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
              <circle cx="12" cy="12" r="3"></circle>
            </svg>
          </button>
          <button class="btn-action btn-action-edit" onclick="editEmployee('${emp.id}')" title="Edit Employee">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
          </button>
          <button class="btn-action btn-action-delete" onclick="deleteEmployee('${emp.id}', '${escapeHtml(emp.employee_name)}')" title="Delete Employee">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      `;
      employeeGridSection.appendChild(card);
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

  // Sorting
  document.querySelectorAll('.employee-table th[data-col]').forEach(th => {
    th.addEventListener('click', function () {
      const col = this.getAttribute('data-col');
      if (currentSortCol === col) {
        currentSortDir = currentSortDir === 'asc' ? 'desc' : 'asc';
      } else {
        currentSortCol = col;
        currentSortDir = 'asc';
      }
      loadEmployees();
    });
  });

  // Search filter
  let searchTimeout = null;
  if (searchInput) {
    searchInput.addEventListener('input', function () {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        currentSearch = searchInput.value.trim();
        currentPage = 1;
        loadEmployees();
      }, 250);
    });
  }

  // Limit select
  if (limitSelect) {
    limitSelect.addEventListener('change', function () {
      currentLimit = parseInt(this.value, 10);
      currentPage = 1;
      loadEmployees();
    });
  }

  // Pagination navigation
  if (prevBtn) {
    prevBtn.addEventListener('click', function () {
      if (currentPage > 1) {
        currentPage--;
        loadEmployees();
      }
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      currentPage++;
      loadEmployees();
    });
  }

  // ================= ADD / EDIT MODAL LOGIC =================
  if (btnOpenNewEntry) {
    btnOpenNewEntry.addEventListener('click', function () {
      openAddEntryModal();
    });
  }

  function openAddEntryModal() {
    employeeForm.reset();
    document.getElementById('formEmployeeId').value = '';
    document.getElementById('entryModalTitle').textContent = 'Employee Detail Entry';
    document.getElementById('inputSalaryType').value = 'daily';
    const inStart = document.getElementById('inputShiftStart');
    const inEnd = document.getElementById('inputShiftEnd');
    if (inStart) inStart.value = '09:00 AM';
    if (inEnd) inEnd.value = '06:00 PM';
    document.getElementById('inputShiftHours').value = '09:00';
    const captureStatusEl = document.getElementById('captureStatus');
    if (captureStatusEl) captureStatusEl.textContent = '';
    entryModal.classList.add('active');
  }

  window.editEmployee = async function (empId) {
    try {
      const res = await fetch(`/api/employees/${empId}`);
      if (!res.ok) throw new Error('Employee not found');
      const emp = await res.json();

      document.getElementById('formEmployeeId').value = emp.id;
      document.getElementById('entryModalTitle').textContent = 'Employee Detail Entry';
      document.getElementById('inputName').value = emp.employee_name || '';
      document.getElementById('inputDesignation').value = emp.designation || '';
      document.getElementById('inputSalaryType').value = emp.salary_type || 'hourly';
      document.getElementById('inputMobile').value = emp.mobile_number || '';
      document.getElementById('inputHourlySalary').value = emp.hourly_salary || '';
      document.getElementById('inputDaySalary').value = emp.day_salary || '';
      document.getElementById('inputHalfDaySalary').value = emp.half_day_salary || '';
      document.getElementById('inputEmail').value = emp.email_id || '';
      document.getElementById('inputAadhar').value = emp.aadhar_number || '';
      document.getElementById('inputEmergency').value = emp.emergency_contact || '';
      document.getElementById('inputJoiningDate').value = emp.joining_date || '';
      document.getElementById('inputAccountHolder').value = emp.account_holder_name || '';
      document.getElementById('inputUpi').value = emp.upi_number || '';
      document.getElementById('inputBankName').value = emp.bank_name || '';
      document.getElementById('inputAccountNumber').value = emp.account_number || '';
      document.getElementById('inputIfsc').value = emp.ifsc_code || '';
      document.getElementById('inputShiftHours').value = emp.shift_hours || '09:00';
      const inStart = document.getElementById('inputShiftStart');
      const inEnd = document.getElementById('inputShiftEnd');
      if (inStart) inStart.value = emp.shift_start || '09:00 AM';
      if (inEnd) inEnd.value = emp.shift_end || '06:00 PM';
      const captureStatusEl = document.getElementById('captureStatus');
      if (captureStatusEl) captureStatusEl.textContent = '';

      entryModal.classList.add('active');
    } catch (err) {
      alert('Error fetching employee details: ' + err.message);
    }
  };

  if (closeEntryModalBtn) {
    closeEntryModalBtn.addEventListener('click', function () {
      entryModal.classList.remove('active');
    });
  }

  if (btnResetForm) {
    btnResetForm.addEventListener('click', function () {
      employeeForm.reset();
    });
  }

  // Auto-calculate and synchronize Day Salary, Half Day Salary, and Hourly Salary
  const inputSalaryType = document.getElementById('inputSalaryType');
  const inputHourly = document.getElementById('inputHourlySalary');
  const inputDay = document.getElementById('inputDaySalary');
  const inputHalfDay = document.getElementById('inputHalfDaySalary');
  const inputShift = document.getElementById('inputShiftHours');

  // Smart hour:minute format normalizer (e.g. 8.30 -> 08:30, 8 -> 08:00, 8:30 -> 08:30)
  function normalizeTimeInput(val) {
    if (!val) return '08:00';
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

  function getShiftDuration() {
    let shiftDuration = 8.0;
    if (inputShift && inputShift.value.trim()) {
      const val = inputShift.value.trim();
      const parts = val.split(':');
      if (parts.length >= 2) {
        shiftDuration = (parseFloat(parts[0]) || 0) + (parseFloat(parts[1]) || 0) / 60;
      } else if (!isNaN(parseFloat(val))) {
        shiftDuration = parseFloat(val);
      }
    }
    return shiftDuration > 0 ? shiftDuration : 8.0;
  }

  // When Hourly changes
  function onHourlyInput() {
    const hourly = parseFloat(inputHourly.value) || 0;
    if (hourly <= 0) return;
    const dur = getShiftDuration();
    const day = hourly * dur;
    inputDay.value = day.toFixed(2);
    inputHalfDay.value = (day / 2).toFixed(2);
  }

  // When Day changes
  function onDayInput() {
    const day = parseFloat(inputDay.value) || 0;
    if (day <= 0) return;
    const dur = getShiftDuration();
    inputHourly.value = (day / dur).toFixed(2);
    inputHalfDay.value = (day / 2).toFixed(2);
  }

  // When Half-Day changes
  function onHalfDayInput() {
    const half = parseFloat(inputHalfDay.value) || 0;
    if (half <= 0) return;
    const dur = getShiftDuration();
    const day = half * 2;
    inputDay.value = day.toFixed(2);
    inputHourly.value = (day / dur).toFixed(2);
  }

  if (inputSalaryType) {
    inputSalaryType.addEventListener('change', function () {
      const st = this.value;
      if (st === 'hourly' && inputHourly) inputHourly.focus();
      else if (st === 'daily' && inputDay) inputDay.focus();
      else if (st === 'half_day' && inputHalfDay) inputHalfDay.focus();
    });
  }

  if (inputHourly) {
    inputHourly.addEventListener('input', onHourlyInput);
  }
  if (inputDay) {
    inputDay.addEventListener('input', onDayInput);
  }
  if (inputHalfDay) {
    inputHalfDay.addEventListener('input', onHalfDayInput);
  }

  if (inputShift) {
    inputShift.addEventListener('change', function () {
      if (this.value) this.value = normalizeTimeInput(this.value);
      const st = inputSalaryType ? inputSalaryType.value : 'daily';
      if (st === 'hourly') onHourlyInput();
      else if (st === 'daily') onDayInput();
      else onHalfDayInput();
    });
    inputShift.addEventListener('blur', function () {
      if (this.value) this.value = normalizeTimeInput(this.value);
    });
  }

  if (employeeForm) {
    employeeForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      const empId = document.getElementById('formEmployeeId').value;
      const formData = new FormData(employeeForm);

      const url = empId ? `/api/employees/${empId}` : '/api/employees';
      const method = 'POST';

      try {
        const res = await fetch(url, {
          method: method,
          body: formData
        });

        const data = await res.json();
        if (res.ok && data.success) {
          entryModal.classList.remove('active');
          loadEmployees();
        } else {
          alert(data.error || 'Failed to save employee');
        }
      } catch (err) {
        alert('Error saving employee: ' + err.message);
      }
    });
  }

  // ================= VIEW EMPLOYEE MODAL LOGIC =================
  window.viewEmployee = async function (empId) {
    try {
      const res = await fetch(`/api/employees/${empId}`);
      if (!res.ok) throw new Error('Employee not found');
      const emp = await res.json();

      currentViewingEmpId = emp.id;
      const tbody = document.getElementById('viewInfoTableBody');
      tbody.innerHTML = '';

      // Render photo in modal header
      const photoHeader = document.getElementById('viewEmpPhotoHeader');
      const photoFile = emp.photo || emp.photo_filename;
      if (photoHeader) {
        if (photoFile) {
          photoHeader.innerHTML = `<img src="/uploads/${escapeHtml(photoFile)}" class="view-modal-photo" onclick="openPhotoModal('${escapeHtml(photoFile)}', '${escapeHtml(emp.employee_name)}')" title="Click to view full photo">`;
        } else {
          const initials = (emp.employee_name || 'E').substring(0, 2).toUpperCase();
          photoHeader.innerHTML = `<div class="emp-grid-avatar-placeholder" style="width: 58px; height: 58px; font-size: 20px;">${initials}</div>`;
        }
      }

      let formattedCreated = '-';
      if (emp.created_at) {
        try {
          const cd = new Date(emp.created_at);
          if (!isNaN(cd.getTime())) {
            formattedCreated = cd.toLocaleString('en-IN', {
              day: '2-digit', month: '2-digit', year: 'numeric',
              hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
            });
          } else {
            formattedCreated = String(emp.created_at);
          }
        } catch (e) {
          formattedCreated = String(emp.created_at);
        }
      }

      const stLabels = { hourly: 'Hourly-Based', daily: 'Day-Based', half_day: 'Half-Day-Based' };
      const fields = [
        ['ID', emp.id],
        ['PHOTO', photoFile ? `<a href="/uploads/${escapeHtml(photoFile)}" target="_blank" style="color: #0d6efd; font-weight: 700; text-decoration: underline;">View Uploaded Photo</a>` : 'No photo registered'],
        ['EMPLOYEE NAME', emp.employee_name],
        ['DESIGNATION', emp.designation],
        ['SALARY BASIS', stLabels[emp.salary_type] || 'Hourly-Based'],
        ['HOURLY SALARY', emp.hourly_salary],
        ['DAY SALARY', emp.day_salary],
        ['HALF DAY SALARY', emp.half_day_salary],
        ['MOBILE NUMBER', emp.mobile_number],
        ['EMAIL ID', emp.email_id],
        ['AADHAR NUMBER', emp.aadhar_number],
        ['EMERGENCY CONTACT', emp.emergency_contact],
        ['JOINING DATE', emp.joining_date],
        ['ACCOUNT HOLDER NAME', emp.account_holder_name],
        ['UPI NUMBER', emp.upi_number],
        ['BANK NAME', emp.bank_name],
        ['ACCOUNT NUMBER', emp.account_number],
        ['IFSC CODE', emp.ifsc_code],
        ['SHIFT HOURS', emp.shift_hours || '09:00'],
        ['SHIFT START', emp.shift_start || '09:00 AM'],
        ['SHIFT END', emp.shift_end || '06:00 PM'],
        ['RECORD CREATED AT', formattedCreated]
      ];

      fields.forEach(([label, val]) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="info-label">${label}</td>
          <td>${val ? (label === 'PHOTO' ? val : escapeHtml(String(val))) : '-'}</td>
        `;
        tbody.appendChild(tr);
      });

      viewModal.classList.add('active');
    } catch (err) {
      alert('Error fetching employee details: ' + err.message);
    }
  };

  if (closeViewModalBtn) {
    closeViewModalBtn.addEventListener('click', function () {
      viewModal.classList.remove('active');
    });
  }

  if (btnPrintDetail) {
    btnPrintDetail.addEventListener('click', function () {
      const printContents = document.getElementById('printSection').innerHTML;
      const originalContents = document.body.innerHTML;
      
      const printWindow = window.open('', '', 'height=600,width=800');
      printWindow.document.write('<html><head><title>Print Employee Detail</title>');
      printWindow.document.write('<style>');
      printWindow.document.write(`
        body { font-family: sans-serif; padding: 20px; }
        .view-emp-heading { text-align: center; font-size: 20px; font-weight: bold; margin-bottom: 20px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { border: 1px solid #ccc; padding: 8px 12px; text-align: left; font-size: 13px; }
        th { background: #f0f4f8; }
        .info-label { font-weight: bold; background: #fafafa; width: 35%; }
      `);
      printWindow.document.write('</style></head><body>');
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

  if (btnDownloadPdf) {
    btnDownloadPdf.addEventListener('click', function () {
      if (currentViewingEmpId) {
        window.location.href = `/api/employees/${currentViewingEmpId}/pdf`;
      }
    });
  }

  // ================= PHOTO PREVIEW MODAL LOGIC =================
  window.openPhotoModal = function (filename, name) {
    const imgEl = document.getElementById('photoModalImg');
    const titleEl = document.getElementById('photoModalTitle');
    imgEl.src = `/uploads/${filename}`;
    titleEl.textContent = `${name} - Photo`;
    photoModal.classList.add('active');
  };

  if (closePhotoModalBtn) {
    closePhotoModalBtn.addEventListener('click', function () {
      photoModal.classList.remove('active');
    });
  }

  // ================= DELETE EMPLOYEE =================
  window.deleteEmployee = async function (empId, name) {
    if (confirm(`Are you sure you want to delete employee "${name}"?`)) {
      try {
        const res = await fetch(`/api/employees/${empId}`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (res.ok && data.success) {
          loadEmployees();
        } else {
          alert(data.error || 'Failed to delete employee');
        }
      } catch (err) {
        alert('Error deleting employee: ' + err.message);
      }
    }
  };

  // Close modals on clicking backdrop
  [entryModal, viewModal, photoModal].forEach(modal => {
    if (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target === modal) {
          modal.classList.remove('active');
        }
      });
    }
  });

  // Helper function for HTML escaping
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

  // ===== FACE BIOMETRICS CAMERA CAPTURE =====
  const btnCaptureFace = document.getElementById('btnCaptureface');
  const faceCaptureArea = document.getElementById('faceCaptureArea');
  const faceRegVideo = document.getElementById('faceRegVideo');
  const faceRegCanvas = document.getElementById('faceRegCanvas');
  const btnTakeSnapshot = document.getElementById('btnTakeSnapshot');
  const btnCancelCapture = document.getElementById('btnCancelCapture');
  const captureStatus = document.getElementById('captureStatus');
  const inputPhoto = document.getElementById('inputPhoto');
  let faceStream = null;

  if (btnCaptureFace) {
    btnCaptureFace.addEventListener('click', async function () {
      faceCaptureArea.style.display = 'block';
      captureStatus.textContent = '';
      try {
        faceStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 320, height: 240 } });
        faceRegVideo.srcObject = faceStream;
      } catch (err) {
        captureStatus.textContent = 'Camera access denied';
        captureStatus.style.color = '#dc3545';
      }
    });
  }

  if (btnCancelCapture) {
    btnCancelCapture.addEventListener('click', function () {
      if (faceStream) {
        faceStream.getTracks().forEach(t => t.stop());
        faceStream = null;
      }
      faceCaptureArea.style.display = 'none';
    });
  }

  if (btnTakeSnapshot) {
    btnTakeSnapshot.addEventListener('click', function () {
      if (!faceStream) return;
      faceRegCanvas.width = faceRegVideo.videoWidth;
      faceRegCanvas.height = faceRegVideo.videoHeight;
      const ctx = faceRegCanvas.getContext('2d');
      ctx.translate(faceRegCanvas.width, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(faceRegVideo, 0, 0);

      faceRegCanvas.toBlob(function (blob) {
        // Create a File object and set it on the file input via DataTransfer
        const file = new File([blob], 'face_capture.jpg', { type: 'image/jpeg' });
        const dt = new DataTransfer();
        dt.items.add(file);
        inputPhoto.files = dt.files;

        captureStatus.textContent = '✓ Face captured successfully';
        captureStatus.style.color = '#198754';

        // Stop camera
        if (faceStream) {
          faceStream.getTracks().forEach(t => t.stop());
          faceStream = null;
        }
        // Hide video after short delay
        setTimeout(() => {
          faceCaptureArea.style.display = 'none';
        }, 1500);
      }, 'image/jpeg', 0.9);
    });
  }

  // Stop face camera when modal closes
  const closeEntryModalBtn2 = document.getElementById('closeEntryModal');
  if (closeEntryModalBtn2) {
    closeEntryModalBtn2.addEventListener('click', function () {
      if (faceStream) {
        faceStream.getTracks().forEach(t => t.stop());
        faceStream = null;
      }
      if (faceCaptureArea) faceCaptureArea.style.display = 'none';
    });
  }
});
