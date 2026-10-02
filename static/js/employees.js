// Employee Details Script: Table management, search, sort, pagination, modals (Add/Edit/View/Delete)
document.addEventListener('DOMContentLoaded', function () {
  let currentPage = 1;
  let currentLimit = 10;
  let currentSearch = '';
  let currentSortCol = 'id';
  let currentSortDir = 'desc';
  let currentViewingEmpId = null;
  let currentCapturedBlob = null;

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
      btnListView.classList.add('active');
      btnGridView.classList.remove('active');
      if (employeeListSection) employeeListSection.style.display = 'block';
      if (employeeGridSection) employeeGridSection.style.display = 'none';
      renderTableRows(currentEmployees);
    });

    btnGridView.addEventListener('click', function () {
      currentView = 'grid';
      btnGridView.classList.add('active');
      btnListView.classList.remove('active');
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
      tableBody.innerHTML = `<tr><td colspan="12" style="text-align: center; padding: 24px; color: #64748b;">No matching records found</td></tr>`;
      return;
    }

    employees.forEach(emp => {
      const tr = document.createElement('tr');

      const st = emp.salary_type || 'hourly';
      let badgeHtml = '';
      if (st === 'hourly') {
        badgeHtml = '<span class="status-pill status-blue">Hourly</span>';
      } else if (st === 'daily') {
        badgeHtml = '<span class="status-pill status-active">Day-Based</span>';
      } else if (st === 'half_day') {
        badgeHtml = '<span class="status-pill status-pending">Half-Day</span>';
      } else {
        badgeHtml = '<span class="status-pill status-blue">Hourly</span>';
      }

      const photoFile = emp.photo || emp.photo_filename;
      const photoSrc = emp.photo_data || (photoFile ? (photoFile.startsWith('data:') ? photoFile : `/uploads/${encodeURIComponent(photoFile)}`) : '');
      let photoHtml = '';
      if (photoSrc) {
        photoHtml = `<img src="${photoSrc}" class="emp-table-photo" onclick="openPhotoModal(this.src, '${escapeHtml(emp.employee_name)}')" title="Click to view photo">`;
      } else {
        const initials = (emp.employee_name || 'E').substring(0, 2).toUpperCase();
        photoHtml = `<div class="avatar-circle">${initials}</div>`;
      }

      tr.innerHTML = `
        <td style="font-weight: 700; color: #0f172a;">${escapeHtml(emp.id)}</td>
        <td style="text-align: center; vertical-align: middle;">${photoHtml}</td>
        <td><strong style="color: #0f172a;">${escapeHtml(emp.employee_name)}</strong></td>
        <td style="color: #475569;">${escapeHtml(emp.designation || '')}</td>
        <td>${badgeHtml}</td>
        <td style="font-weight: 600;">₹${Number(emp.hourly_salary || 0).toFixed(2)}</td>
        <td style="font-weight: 600;">₹${Number(emp.day_salary || 0).toFixed(0)}</td>
        <td style="font-weight: 600;">₹${Number(emp.half_day_salary || 0).toFixed(0)}</td>
        <td>${escapeHtml(emp.mobile_number || '')}</td>
        <td>${escapeHtml(emp.email_id || '')}</td>
        <td>${escapeHtml(emp.shift_hours || '-')}</td>
        <td style="text-align: center;">
          <div class="table-actions">
            <button class="btn-action-icon btn-action-view" onclick="viewEmployee('${emp.id}')" title="View Details">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg>
            </button>
            <button class="btn-action-icon btn-action-edit" onclick="editEmployee('${emp.id}')" title="Edit Employee">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
              </svg>
            </button>
            <button class="btn-action-icon btn-action-delete" onclick="deleteEmployee('${emp.id}', '${escapeHtml(emp.employee_name)}')" title="Delete Employee">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
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
      const photoSrc = emp.photo_data || (photoFile ? (photoFile.startsWith('data:') ? photoFile : `/uploads/${encodeURIComponent(photoFile)}`) : '');
      let photoImgHtml = '';
      if (photoSrc) {
        photoImgHtml = `<img src="${photoSrc}" class="emp-grid-photo" onclick="openPhotoModal(this.src, '${escapeHtml(emp.employee_name)}')" title="Click to view photo">`;
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
    currentCapturedBlob = null;
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
    const photoPreviewBox = document.getElementById('currentPhotoPreview');
    if (photoPreviewBox) photoPreviewBox.style.display = 'none';

    // Reset Employee Permissions to all checked
    const pPunch = document.getElementById('permPunchAttendance');
    if (pPunch) pPunch.checked = true;
    const pHist = document.getElementById('permAttendanceHistory');
    if (pHist) pHist.checked = true;
    const pPay = document.getElementById('permMonthlyPayslip');
    if (pPay) pPay.checked = true;
    const pCred = document.getElementById('permEmployeeCredentials');
    if (pCred) pCred.checked = true;

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
      const inDept = document.getElementById('inputDepartment');
      if (inDept) inDept.value = emp.department || '';
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

      // Populate Employee Permissions (defaulting to true for backward compatibility)
      const perms = emp.permissions || {};
      const editPunch = document.getElementById('permPunchAttendance');
      if (editPunch) editPunch.checked = perms.punch_attendance !== false;
      const editHist = document.getElementById('permAttendanceHistory');
      if (editHist) editHist.checked = perms.attendance_history !== false;
      const editPay = document.getElementById('permMonthlyPayslip');
      if (editPay) editPay.checked = perms.monthly_payslip !== false;
      const editCred = document.getElementById('permEmployeeCredentials');
      if (editCred) editCred.checked = perms.employee_credentials !== false;

      // Show existing photo preview if present
      const photoPreviewBox = document.getElementById('currentPhotoPreview');
      const editThumb = document.getElementById('editPhotoThumb');
      const editNote = document.getElementById('editPhotoNote');
      const photoFile = emp.photo || emp.photo_filename;
      const currentPhotoSrc = emp.photo_data || (photoFile ? (photoFile.startsWith('data:') ? photoFile : `/uploads/${encodeURIComponent(photoFile)}`) : '');
      if (currentPhotoSrc && photoPreviewBox && editThumb) {
        editThumb.src = currentPhotoSrc;
        if (editNote) editNote.textContent = 'Current registered photo. Leave file input empty to keep this photo, or capture/upload a new one to replace.';
        photoPreviewBox.style.display = 'flex';
      } else if (photoPreviewBox) {
        photoPreviewBox.style.display = 'none';
      }

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
      const pPunch = document.getElementById('permPunchAttendance');
      if (pPunch) pPunch.checked = true;
      const pHist = document.getElementById('permAttendanceHistory');
      if (pHist) pHist.checked = true;
      const pPay = document.getElementById('permMonthlyPayslip');
      if (pPay) pPay.checked = true;
      const pCred = document.getElementById('permEmployeeCredentials');
      if (pCred) pCred.checked = true;
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

      // Ensure salary rates are calculated even if user only entered one
      const hourlyVal = inputHourly ? (parseFloat(inputHourly.value) || 0) : 0;
      const dayVal = inputDay ? (parseFloat(inputDay.value) || 0) : 0;
      const halfVal = inputHalfDay ? (parseFloat(inputHalfDay.value) || 0) : 0;
      const dur = getShiftDuration();

      if (dayVal > 0) {
        if (hourlyVal <= 0 && inputHourly) inputHourly.value = (dayVal / dur).toFixed(2);
        if (halfVal <= 0 && inputHalfDay) inputHalfDay.value = (dayVal / 2).toFixed(2);
      } else if (hourlyVal > 0) {
        if (inputDay) inputDay.value = (hourlyVal * dur).toFixed(2);
        if (inputHalfDay) inputHalfDay.value = ((hourlyVal * dur) / 2).toFixed(2);
      } else if (halfVal > 0) {
        if (inputDay) inputDay.value = (halfVal * 2).toFixed(2);
        if (inputHourly) inputHourly.value = ((halfVal * 2) / dur).toFixed(2);
      } else {
        if (inputDay && !inputDay.value) inputDay.value = '0.00';
        if (inputHalfDay && !inputHalfDay.value) inputHalfDay.value = '0.00';
        if (inputHourly && !inputHourly.value) inputHourly.value = '0.00';
      }

      const emailInput = document.getElementById('inputEmail');
      const emailVal = emailInput ? emailInput.value.trim() : '';
      if (!emailVal) {
        alert('Email ID is required.');
        if (emailInput) emailInput.focus();
        return;
      }
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(emailVal)) {
        alert('Please enter a valid email address (e.g. employee@company.com).');
        if (emailInput) emailInput.focus();
        return;
      }

      const empId = document.getElementById('formEmployeeId').value.trim();
      const formData = new FormData(employeeForm);

      // Explicitly serialize employee portal permissions
      const permPunch = document.getElementById('permPunchAttendance');
      const permHist = document.getElementById('permAttendanceHistory');
      const permPay = document.getElementById('permMonthlyPayslip');
      const permCred = document.getElementById('permEmployeeCredentials');
      formData.set('perm_punch_attendance', permPunch ? (permPunch.checked ? 'true' : 'false') : 'true');
      formData.set('perm_attendance_history', permHist ? (permHist.checked ? 'true' : 'false') : 'true');
      formData.set('perm_monthly_payslip', permPay ? (permPay.checked ? 'true' : 'false') : 'true');
      formData.set('perm_employee_credentials', permCred ? (permCred.checked ? 'true' : 'false') : 'true');

      // Attach webcam captured photo if user took snapshot
      if (currentCapturedBlob) {
        formData.set('photo', currentCapturedBlob, 'face_capture.jpg');
        try {
          const canvas = document.getElementById('faceRegCanvas');
          if (canvas) {
            const cData = canvas.toDataURL('image/jpeg', 0.9);
            if (cData && cData.startsWith('data:image')) {
              formData.set('photo_data', cData);
            }
          }
        } catch (cErr) {
          console.warn('Canvas toDataURL fallback failed:', cErr);
        }
      }

      const url = empId ? `/api/employees/${empId}` : '/api/employees';
      const method = 'POST';

      const btnSubmitForm = document.getElementById('btnSubmitForm');
      const origText = btnSubmitForm ? btnSubmitForm.textContent : 'Submit';
      if (btnSubmitForm) {
        btnSubmitForm.disabled = true;
        btnSubmitForm.textContent = 'Saving...';
      }

      try {
        const res = await fetch(url, {
          method: method,
          body: formData
        });

        const contentType = res.headers.get('content-type') || '';
        let data = {};
        if (contentType.includes('application/json')) {
          data = await res.json();
        } else {
          const text = await res.text();
          if (res.status === 401) {
            alert('Your session has expired. Please log in again.');
            window.location.href = '/login';
            return;
          }
          throw new Error(`Server returned status ${res.status}: ${text.slice(0, 150)}`);
        }

        if (res.ok && data.success) {
          entryModal.classList.remove('active');
          currentCapturedBlob = null;
          const msg = data.message || (empId ? 'Employee updated successfully!' : 'Employee created successfully!');
          alert(msg);
          loadEmployees();
        } else {
          alert(data.error || 'Failed to save employee');
        }
      } catch (err) {
        alert('Error saving employee: ' + err.message);
      } finally {
        if (btnSubmitForm) {
          btnSubmitForm.disabled = false;
          btnSubmitForm.textContent = origText;
        }
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
      const photoSrc = emp.photo_data || (photoFile ? (photoFile.startsWith('data:') ? photoFile : `/uploads/${encodeURIComponent(photoFile)}`) : '');
      if (photoHeader) {
        if (photoSrc) {
          photoHeader.innerHTML = `<img src="${photoSrc}" class="view-modal-photo" onclick="openPhotoModal(this.src, '${escapeHtml(emp.employee_name)}')" title="Click to view full photo">`;
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
        ['DEPARTMENT', emp.department || emp.designation || '-'],
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
  window.openPhotoModal = function (srcOrFilename, name) {
    const imgEl = document.getElementById('photoModalImg');
    const titleEl = document.getElementById('photoModalTitle');
    let validSrc = srcOrFilename || '';
    if (validSrc && typeof validSrc === 'string' && !validSrc.startsWith('data:') && !validSrc.startsWith('http://') && !validSrc.startsWith('https://') && !validSrc.startsWith('/')) {
      validSrc = `/uploads/${encodeURIComponent(validSrc)}`;
    }
    imgEl.src = validSrc;
    titleEl.textContent = `${name || 'Employee'} - Photo`;
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

  // ================= EXPORTS (COPY, CSV, EXCEL, PDF, PRINT) =================
  const btnCopyEmployees = document.getElementById('btnCopyEmployees');
  const btnCsvEmployees = document.getElementById('btnCsvEmployees');
  const btnExcelEmployees = document.getElementById('btnExcelEmployees');
  const btnPdfEmployees = document.getElementById('btnPdfEmployees');
  const btnPrintEmployees = document.getElementById('btnPrintEmployees');

  if (btnCopyEmployees) {
    btnCopyEmployees.addEventListener('click', function () {
      const table = document.getElementById('employeeDataTable');
      if (!table) return;
      let text = '';
      for (let row of table.rows) {
        let rowData = [];
        const cellCount = row.cells.length;
        for (let i = 0; i < cellCount - 1; i++) {
          rowData.push(row.cells[i].innerText.trim());
        }
        text += rowData.join('\t') + '\n';
      }
      (window.safeCopyToClipboard ? window.safeCopyToClipboard(text) : navigator.clipboard.writeText(text)).then(() => {
        alert('Employee table copied to clipboard!');
      }).catch(err => console.error(err));
    });
  }

  if (btnCsvEmployees) {
    btnCsvEmployees.addEventListener('click', function () {
      window.location.href = `/api/employees/export/csv?search=${encodeURIComponent(currentSearch)}`;
    });
  }

  if (btnExcelEmployees) {
    btnExcelEmployees.addEventListener('click', function () {
      window.location.href = `/api/employees/export/excel?search=${encodeURIComponent(currentSearch)}`;
    });
  }

  if (btnPdfEmployees) {
    btnPdfEmployees.addEventListener('click', function () {
      window.location.href = `/api/employees/export/pdf?search=${encodeURIComponent(currentSearch)}`;
    });
  }

  if (btnPrintEmployees) {
    btnPrintEmployees.addEventListener('click', function () {
      const printContents = document.getElementById('employeeDataTable').outerHTML;
      const printWindow = window.open('', '', 'height=600,width=850');
      printWindow.document.write('<html><head><title>Print Employee Directory</title>');
      printWindow.document.write('<style>');
      printWindow.document.write(`
        body { font-family: sans-serif; padding: 20px; }
        h2 { text-align: center; margin-bottom: 20px; font-size: 18px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }
        th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }
        th { background: #2c3e50; color: #fff; }
        th:last-child, td:last-child { display: none; }
      `);
      printWindow.document.write('</style></head><body>');
      const compName = document.querySelector('.nav-title')?.innerText?.trim() || 'ARGUS TECHNOLOGIES';
      printWindow.document.write(`<h2>${compName} - EMPLOYEE DIRECTORY REPORT</h2>`);
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

  // Initial load
  loadEmployees();

  // ===== FACE BIOMETRICS CAMERA CAPTURE (SEPARATE OVERLAY MODAL) =====
  const btnCaptureFace = document.getElementById('btnCaptureface');
  const faceCameraModal = document.getElementById('faceCameraModal');
  const closeCameraModal = document.getElementById('closeCameraModal');
  const faceRegVideo = document.getElementById('faceRegVideo');
  const faceRegCanvas = document.getElementById('faceRegCanvas');
  const btnTakeSnapshot = document.getElementById('btnTakeSnapshot');
  const btnCancelCapture = document.getElementById('btnCancelCapture');
  const cameraStatusMsg = document.getElementById('cameraStatusMsg');
  const captureStatus = document.getElementById('captureStatus');
  const inputPhoto = document.getElementById('inputPhoto');
  let faceStream = null;

  function stopFaceCamera() {
    if (faceStream) {
      faceStream.getTracks().forEach(t => t.stop());
      faceStream = null;
    }
    if (faceCameraModal) {
      faceCameraModal.classList.remove('active');
    }
    if (cameraStatusMsg) {
      cameraStatusMsg.textContent = '';
    }
  }

  if (btnCaptureFace) {
    btnCaptureFace.addEventListener('click', async function () {
      if (faceCameraModal) faceCameraModal.classList.add('active');
      if (cameraStatusMsg) {
        cameraStatusMsg.textContent = 'Connecting to webcam...';
        cameraStatusMsg.style.color = '#3d6078';
      }
      try {
        faceStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 320, height: 240 } });
        faceRegVideo.srcObject = faceStream;
        if (cameraStatusMsg) {
          cameraStatusMsg.textContent = 'Position face within frame and click Capture Snapshot';
          cameraStatusMsg.style.color = '#198754';
        }
      } catch (err) {
        if (cameraStatusMsg) {
          cameraStatusMsg.textContent = 'Camera access denied: ' + err.message;
          cameraStatusMsg.style.color = '#dc3545';
        }
      }
    });
  }

  if (closeCameraModal) {
    closeCameraModal.addEventListener('click', stopFaceCamera);
  }

  if (btnCancelCapture) {
    btnCancelCapture.addEventListener('click', stopFaceCamera);
  }

  if (faceCameraModal) {
    faceCameraModal.addEventListener('click', function (e) {
      if (e.target === faceCameraModal) {
        stopFaceCamera();
      }
    });
  }

  if (btnTakeSnapshot) {
    btnTakeSnapshot.addEventListener('click', function () {
      if (!faceStream) return;
      faceRegCanvas.width = faceRegVideo.videoWidth || 640;
      faceRegCanvas.height = faceRegVideo.videoHeight || 480;
      const ctx = faceRegCanvas.getContext('2d');
      ctx.translate(faceRegCanvas.width, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(faceRegVideo, 0, 0, faceRegCanvas.width, faceRegCanvas.height);

      faceRegCanvas.toBlob(function (blob) {
        currentCapturedBlob = blob;
        try {
          const file = new File([blob], 'face_capture.jpg', { type: 'image/jpeg' });
          const dt = new DataTransfer();
          dt.items.add(file);
          inputPhoto.files = dt.files;
        } catch (err) {
          console.warn('DataTransfer fallback used for photo upload:', err);
        }

        if (captureStatus) {
          captureStatus.textContent = '✓ Face snapshot captured (AI Face Biometrics will be generated upon saving)';
          captureStatus.style.color = '#198754';
        }

        // Update photo preview thumbnail in entry modal
        const photoPreviewBox = document.getElementById('currentPhotoPreview');
        const editThumb = document.getElementById('editPhotoThumb');
        const editNote = document.getElementById('editPhotoNote');
        if (photoPreviewBox && editThumb) {
          editThumb.src = URL.createObjectURL(blob);
          if (editNote) editNote.textContent = '✓ New snapshot captured and ready to save.';
          photoPreviewBox.style.display = 'flex';
        }

        stopFaceCamera();
      }, 'image/jpeg', 0.9);
    });
  }

  // Live preview when selecting image via file input
  if (inputPhoto) {
    inputPhoto.addEventListener('change', function () {
      if (this.files && this.files[0]) {
        currentCapturedBlob = null;
        const photoPreviewBox = document.getElementById('currentPhotoPreview');
        const editThumb = document.getElementById('editPhotoThumb');
        const editNote = document.getElementById('editPhotoNote');
        if (photoPreviewBox && editThumb) {
          editThumb.src = URL.createObjectURL(this.files[0]);
          if (editNote) editNote.textContent = `✓ Selected photo: ${this.files[0].name}`;
          photoPreviewBox.style.display = 'flex';
        }
        if (captureStatus) {
          captureStatus.textContent = `✓ Selected photo: ${this.files[0].name}`;
          captureStatus.style.color = '#198754';
        }
      }
    });
  }

  // Also stop face camera when employee entry modal closes
  const closeEntryModalBtn2 = document.getElementById('closeEntryModal');
  if (closeEntryModalBtn2) {
    closeEntryModalBtn2.addEventListener('click', stopFaceCamera);
  }
});
