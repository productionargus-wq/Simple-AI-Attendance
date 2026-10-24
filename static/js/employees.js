// Employee Details Script: Table management, search, sort, pagination, modals (Add/Edit/View/Delete)
document.addEventListener('DOMContentLoaded', function () {
  let currentPage = 1;
  let currentLimit = 10;
  let currentSearch = '';
  let currentStatus = 'All';
  let currentSortCol = 'id';
  let currentSortDir = 'desc';
  let currentViewingEmpId = null;
  let currentCapturedBlob = null;
  let capturedFaceEmbedding = null;
  let capturedPhotoData = null;
  let capturedPhotoFilename = null;

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
  let currentView = 'grid';
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
      const bParam = new URLSearchParams(window.location.search).get('branch_id');
      const url = `/api/employees?search=${encodeURIComponent(currentSearch)}&status=${encodeURIComponent(currentStatus)}&sort_col=${currentSortCol}&sort_dir=${currentSortDir}&page=${currentPage}&limit=${currentLimit}${bParam ? '&branch_id=' + encodeURIComponent(bParam) : ''}`;
      const res = await fetch(url);
      const data = await res.json();

      currentEmployees = data.data || [];
      if (currentView === 'grid') {
        renderGridCards(currentEmployees);
      } else {
        renderTableRows(currentEmployees);
      }
      updatePagination(data.total, data.page, data.limit);

      // Update Quota badge and status filter pill counts
      const countAllEl = document.getElementById('countAllPill');
      if (countAllEl) countAllEl.textContent = `(${data.total_preserved ?? data.total ?? 0})`;
      const countActiveEl = document.getElementById('countActivePill');
      if (countActiveEl) countActiveEl.textContent = `(${data.active_count ?? 0})`;
      const countInactiveEl = document.getElementById('countInactivePill');
      if (countInactiveEl) countInactiveEl.textContent = `(${data.inactive_count ?? 0})`;

      const quotaUsageEl = document.getElementById('quotaUsageText');
      if (quotaUsageEl) {
        quotaUsageEl.textContent = `${data.active_count ?? 0} / ${data.employee_limit ?? 50} Active`;
      }
    } catch (err) {
      console.error('Failed to load employees:', err);
    }
  }

  function renderTableRows(employees) {
    if (!tableBody) return;
    tableBody.innerHTML = '';

    if (!employees || employees.length === 0) {
      tableBody.innerHTML = `<tr><td colspan="13" style="text-align: center; padding: 24px; color: #64748b;">No matching records found</td></tr>`;
      return;
    }

    employees.forEach(emp => {
      const tr = document.createElement('tr');

      const isInactive = (emp.status === 'Inactive');
      const statusBadgeHtml = isInactive 
        ? '<span class="status-pill status-inactive">Inactive</span>' 
        : '<span class="status-pill status-active">Active</span>';

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

        const fwBadge = emp.is_field_worker 
          ? '<span class="status-pill" style="background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; font-size: 10px; font-weight: 700; padding: 1px 6px; border-radius: 4px; display: inline-flex; align-items: center; gap: 3px; margin-left: 6px; white-space: nowrap;">🏃 Field Worker</span>' 
          : '';

        tr.innerHTML = `
        <td style="font-weight: 700; color: #0f172a; white-space: nowrap;">${escapeHtml(emp.id)}</td>
        <td style="text-align: center; vertical-align: middle;">${photoHtml}</td>
        <td class="col-wrap" style="max-width: 180px; white-space: normal !important; word-break: break-word !important;"><strong style="color: #0f172a;">${escapeHtml(emp.employee_name)}</strong>${fwBadge}</td>
        <td class="col-wrap" style="color: #475569; max-width: 160px; white-space: normal !important; word-break: break-word !important;">${escapeHtml(emp.designation || '')}</td>
        <td style="white-space: nowrap;">${statusBadgeHtml}</td>
        <td style="white-space: nowrap;">${badgeHtml}</td>
        <td style="font-weight: 600; white-space: nowrap;">₹${Number(emp.hourly_salary || 0).toFixed(2)}</td>
        <td style="font-weight: 600; white-space: nowrap;">₹${Number(emp.day_salary || 0).toFixed(0)}</td>
        <td style="font-weight: 600; white-space: nowrap;">₹${Number(emp.half_day_salary || 0).toFixed(0)}</td>
        <td style="white-space: nowrap;">${escapeHtml(emp.mobile_number || '')}</td>
        <td style="white-space: nowrap;">${escapeHtml(emp.email_id || '')}</td>
        <td style="white-space: nowrap;">${escapeHtml(emp.shift_hours || '-')}</td>
        <td style="text-align: center; white-space: nowrap;">
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
      let salaryRateDisplay = `₹${Number(emp.hourly_salary || 0).toFixed(2)}/hr`;
      if (st === 'daily') salaryRateDisplay = `₹${Number(emp.day_salary || 0).toFixed(0)}/day`;
      else if (st === 'half_day') salaryRateDisplay = `₹${Number(emp.half_day_salary || 0).toFixed(0)}/half-day`;

      const isInactive = (emp.status === 'Inactive');
      const statusBadgeHtml = isInactive 
        ? '<span class="status-pill status-inactive" style="font-size: 10.5px; padding: 2px 7px;">Inactive</span>' 
        : '<span class="status-pill status-active" style="font-size: 10.5px; padding: 2px 7px;">Active</span>';

      card.innerHTML = `
        <div class="emp-grid-header">
          ${photoImgHtml}
          <div style="flex: 1; min-width: 0;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 6px;">
              <div class="emp-grid-info-title">${escapeHtml(emp.employee_name)}</div>
              ${statusBadgeHtml}
            </div>
            <div class="emp-grid-info-sub">${escapeHtml(emp.designation || 'Staff')} &bull; ID: ${escapeHtml(emp.id)}</div>
            ${emp.is_field_worker ? '<div style="margin-top: 3px;"><span style="background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; display: inline-flex; align-items: center; gap: 3px;">🏃 Field Worker</span></div>' : ''}
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

  // Status Filter Tabs (All / Active / Inactive)
  const statusFilterBtns = document.querySelectorAll('.btn-status-filter');
  statusFilterBtns.forEach(btn => {
    btn.addEventListener('click', function () {
      statusFilterBtns.forEach(b => {
        b.classList.remove('active');
        b.style.background = 'transparent';
        b.style.boxShadow = 'none';
      });
      this.classList.add('active');
      this.style.background = '#ffffff';
      this.style.boxShadow = '0 1px 2px rgba(0,0,0,0.06)';
      currentStatus = this.getAttribute('data-status') || 'All';
      currentPage = 1;
      loadEmployees();
    });
  });

  // ================= EMPLOYEE DOCUMENTS MANAGEMENT =================
  const employeeDocsContainer = document.getElementById('employeeDocsContainer');
  const btnAddDocRowTop = document.getElementById('btnAddDocRowTop');
  let currentExistingDocs = [];

  function renderEmployeeDocuments(existingDocs = []) {
    if (!employeeDocsContainer) return;
    employeeDocsContainer.innerHTML = '';
    currentExistingDocs = Array.isArray(existingDocs) ? [...existingDocs] : [];

    // Render existing saved documents
    currentExistingDocs.forEach((doc, idx) => {
      const row = createExistingDocRow(doc, idx);
      employeeDocsContainer.appendChild(row);
    });

    // Always append at least 1 new upload row
    addNewDocumentRow();
  }

  function createExistingDocRow(doc, idx) {
    const row = document.createElement('div');
    row.className = 'doc-entry-row existing-doc-row';
    row.dataset.docId = doc.id || idx;

    const docName = doc.document_name || doc.filename || 'Document';
    const docUrl = doc.file_url || (doc.filename ? `/static/uploads/employee_documents/${doc.filename}` : '#');
    const docExt = doc.file_type ? doc.file_type.toUpperCase() : 'FILE';

    row.innerHTML = `
      <div style="display: flex; align-items: center; gap: 8px; flex: 1; min-width: 170px;">
        <span style="font-size: 13px;">📄</span>
        <input type="text" class="form-input doc-title-input existing-doc-title" value="${escapeHtml(docName)}" placeholder="Document Name" style="font-weight: 600;">
        <span style="font-size: 10px; background: #e2e8f0; color: #475569; padding: 2px 6px; border-radius: 4px; font-weight: 700;">${escapeHtml(docExt)}</span>
      </div>
      <div class="doc-upload-box">
        <a href="${escapeHtml(docUrl)}" target="_blank" class="btn-doc-view" title="View attached document">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
            <circle cx="12" cy="12" r="3"></circle>
          </svg>
          <span>View</span>
        </a>
        <button type="button" class="btn-doc-remove btn-remove-existing" title="Delete document">
          &times;
        </button>
      </div>
    `;

    const removeBtn = row.querySelector('.btn-remove-existing');
    if (removeBtn) {
      removeBtn.addEventListener('click', function () {
        currentExistingDocs = currentExistingDocs.filter(d => (d.id || '') !== (doc.id || ''));
        row.remove();
        if (employeeDocsContainer.querySelectorAll('.doc-entry-row').length === 0) {
          addNewDocumentRow();
        }
      });
    }

    return row;
  }

  function addNewDocumentRow() {
    if (!employeeDocsContainer) return;

    const row = document.createElement('div');
    row.className = 'doc-entry-row new-doc-row';

    row.innerHTML = `
      <input type="text" class="form-input doc-title-input new-doc-title" placeholder="Document Name (e.g. Aadhar Card)">
      <div class="doc-upload-box">
        <input type="file" class="doc-file-input" accept="image/*,.pdf,.doc,.docx,.xls,.xlsx,.txt" style="display: none;">
        <button type="button" class="btn-doc-choose">
          📁 Choose File
        </button>
        <span class="doc-file-status">No file chosen</span>
        <button type="button" class="btn-doc-view btn-preview-new-doc" style="display: none;" title="Preview uploaded document">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
            <circle cx="12" cy="12" r="3"></circle>
          </svg>
          <span>View</span>
        </button>
        <button type="button" class="btn-doc-add" title="Add another document row">
          +
        </button>
        <button type="button" class="btn-doc-remove btn-remove-new-row" title="Remove this row">
          &times;
        </button>
      </div>
    `;

    const fileInput = row.querySelector('.doc-file-input');
    const chooseBtn = row.querySelector('.btn-doc-choose');
    const statusSpan = row.querySelector('.doc-file-status');
    const previewBtn = row.querySelector('.btn-preview-new-doc');
    const titleInput = row.querySelector('.new-doc-title');
    const addBtn = row.querySelector('.btn-doc-add');
    const removeBtn = row.querySelector('.btn-remove-new-row');

    let currentFileObj = null;

    if (chooseBtn && fileInput) {
      chooseBtn.addEventListener('click', function () {
        fileInput.click();
      });
    }

    if (fileInput) {
      fileInput.addEventListener('change', function () {
        if (fileInput.files && fileInput.files[0]) {
          const file = fileInput.files[0];
          currentFileObj = file;
          const sizeKb = Math.round(file.size / 1024);
          statusSpan.textContent = `${file.name} (${sizeKb} KB)`;
          statusSpan.title = file.name;
          statusSpan.style.color = '#0284c7';
          statusSpan.style.fontWeight = '700';

          // Auto-fill document title if empty
          if (!titleInput.value.trim()) {
            const rawName = file.name.substring(0, file.name.lastIndexOf('.')) || file.name;
            titleInput.value = rawName.replace(/[_-]/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
          }

          // Display the View icon immediately
          if (previewBtn) {
            previewBtn.style.display = 'inline-flex';
          }
        } else {
          currentFileObj = null;
          statusSpan.textContent = 'No file chosen';
          statusSpan.style.color = '#64748b';
          statusSpan.style.fontWeight = '500';
          if (previewBtn) {
            previewBtn.style.display = 'none';
          }
        }
      });
    }

    // View icon click: instant preview
    if (previewBtn) {
      previewBtn.addEventListener('click', function (e) {
        e.preventDefault();
        if (currentFileObj) {
          const blobUrl = URL.createObjectURL(currentFileObj);
          window.open(blobUrl, '_blank');
        }
      });
    }

    // Inline + button: add new row below
    if (addBtn) {
      addBtn.addEventListener('click', function () {
        addNewDocumentRow();
      });
    }

    // Remove button: delete this row
    if (removeBtn) {
      removeBtn.addEventListener('click', function () {
        const totalRows = employeeDocsContainer.querySelectorAll('.doc-entry-row').length;
        if (totalRows > 1) {
          row.remove();
        } else {
          fileInput.value = '';
          currentFileObj = null;
          statusSpan.textContent = 'No file chosen';
          statusSpan.style.color = '#64748b';
          statusSpan.style.fontWeight = '500';
          titleInput.value = '';
          if (previewBtn) previewBtn.style.display = 'none';
        }
      });
    }

    employeeDocsContainer.appendChild(row);
  }

  if (btnAddDocRowTop) {
    btnAddDocRowTop.addEventListener('click', function () {
      addNewDocumentRow();
    });
  }

  // ================= ADD / EDIT MODAL LOGIC =================
  function toggleFieldWorkerFormFields(empType) {
    const isFw = (empType === 'field_worker');
    const groupFw = document.getElementById('groupFieldWorkerSettings');
    if (groupFw) {
      groupFw.style.display = isFw ? 'block' : 'none';
    }
  }

  const inputEmployeeType = document.getElementById('inputEmployeeType');
  if (inputEmployeeType) {
    inputEmployeeType.addEventListener('change', function () {
      toggleFieldWorkerFormFields(this.value);
    });
  }

  if (btnOpenNewEntry) {
    btnOpenNewEntry.addEventListener('click', function () {
      openAddEntryModal();
    });
  }

  function openAddEntryModal() {
    employeeForm.reset();
    currentCapturedBlob = null;
    capturedFaceEmbedding = null;
    capturedPhotoData = null;
    capturedPhotoFilename = null;
    document.getElementById('formEmployeeId').value = '';
    document.getElementById('entryModalTitle').textContent = 'Employee Detail Entry';
    document.getElementById('inputSalaryType').value = 'daily';
    const inStatus = document.getElementById('inputStatus');
    if (inStatus) inStatus.value = 'Active';
    const inEmpType = document.getElementById('inputEmployeeType');
    if (inEmpType) inEmpType.value = 'standard';
    const inTerritory = document.getElementById('inputTerritoryZone');
    if (inTerritory) inTerritory.value = '';
    const inVisitInc = document.getElementById('inputVisitIncentive');
    if (inVisitInc) inVisitInc.value = '';
    const inKmRate = document.getElementById('inputKmAllowance');
    if (inKmRate) inKmRate.value = '';
    toggleFieldWorkerFormFields('standard');
    const inBranch = document.getElementById('inputBranchId');
    if (inBranch) inBranch.value = window.ACTIVE_BRANCH_ID || inBranch.getAttribute('data-default-branch') || (inBranch.querySelector('option[value="HOME"]') ? 'HOME' : '');
    const inDob = document.getElementById('inputDob');
    if (inDob) inDob.value = '';
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
    const pLeave = document.getElementById('permLeavePermission');
    if (pLeave) pLeave.checked = true;

    // Reset Employee Documents to 1 empty row
    renderEmployeeDocuments([]);

    if (window.ArgusVoice) {
      window.ArgusVoice.resetFormGuidance('#entryModal');
    }

    entryModal.classList.add('active');
  }

  window.editEmployee = async function (empId) {
    try {
      const res = await fetch(`/api/employees/${empId}`);
      if (!res.ok) throw new Error('Employee not found');
      const emp = await res.json();

      currentCapturedBlob = null;
      capturedFaceEmbedding = emp.face_embedding || null;
      capturedPhotoData = emp.photo_data || null;
      capturedPhotoFilename = emp.photo_filename || emp.photo || null;

      document.getElementById('formEmployeeId').value = emp.id;
      document.getElementById('entryModalTitle').textContent = 'Employee Detail Entry';
      document.getElementById('inputName').value = emp.employee_name || '';
      const inDept = document.getElementById('inputDepartment');
      if (inDept) inDept.value = emp.department || '';
      document.getElementById('inputDesignation').value = emp.designation || '';
      document.getElementById('inputSalaryType').value = emp.salary_type || 'hourly';
      const inEditStatus = document.getElementById('inputStatus');
      if (inEditStatus) inEditStatus.value = (emp.status === 'Inactive') ? 'Inactive' : 'Active';
      const isFw = Boolean(emp.is_field_worker);
      const inEditEmpType = document.getElementById('inputEmployeeType');
      if (inEditEmpType) inEditEmpType.value = isFw ? 'field_worker' : 'standard';
      const inEditTerritory = document.getElementById('inputTerritoryZone');
      if (inEditTerritory) inEditTerritory.value = emp.territory_zone || '';
      const inEditVisitInc = document.getElementById('inputVisitIncentive');
      if (inEditVisitInc) inEditVisitInc.value = (emp.per_visit_incentive !== undefined && emp.per_visit_incentive !== null) ? emp.per_visit_incentive : '';
      const inEditKmRate = document.getElementById('inputKmAllowance');
      if (inEditKmRate) inEditKmRate.value = (emp.km_allowance_rate !== undefined && emp.km_allowance_rate !== null) ? emp.km_allowance_rate : '';
      toggleFieldWorkerFormFields(isFw ? 'field_worker' : 'standard');
      const inBranch = document.getElementById('inputBranchId');
      if (inBranch) inBranch.value = (emp.branch_id && emp.branch_id !== 'HOME') ? emp.branch_id : (inBranch.querySelector('option[value="HOME"]') ? 'HOME' : '');
      document.getElementById('inputMobile').value = emp.mobile_number || '';
      document.getElementById('inputHourlySalary').value = (emp.hourly_salary !== undefined && emp.hourly_salary !== null) ? emp.hourly_salary : '';
      document.getElementById('inputDaySalary').value = (emp.day_salary !== undefined && emp.day_salary !== null) ? emp.day_salary : '';
      document.getElementById('inputHalfDaySalary').value = (emp.half_day_salary !== undefined && emp.half_day_salary !== null) ? emp.half_day_salary : '';
      document.getElementById('inputEmail').value = emp.email_id || '';
      document.getElementById('inputAadhar').value = emp.aadhar_number || '';
      document.getElementById('inputEmergency').value = emp.emergency_contact || '';
      const inDob = document.getElementById('inputDob');
      if (inDob) inDob.value = emp.date_of_birth || emp.dob || '';
      document.getElementById('inputJoiningDate').value = emp.joining_date || '';
      document.getElementById('inputAccountHolder').value = emp.account_holder_name || '';
      document.getElementById('inputUpi').value = emp.upi_number || '';
      if (document.getElementById('inputBankName')) document.getElementById('inputBankName').value = emp.bank_name || '';
      document.getElementById('inputAccountNumber').value = emp.account_number || '';
      document.getElementById('inputIfsc').value = emp.ifsc_code || '';
      document.getElementById('inputShiftHours').value = (emp.shift_hours !== undefined && emp.shift_hours !== null && String(emp.shift_hours).trim() !== '') ? emp.shift_hours : '09:00';
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
      const editLeave = document.getElementById('permLeavePermission');
      if (editLeave) editLeave.checked = perms.leave_permission !== false;

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

      // Render Employee Documents
      renderEmployeeDocuments(emp.documents || []);

      if (window.ArgusVoice) {
        window.ArgusVoice.resetFormGuidance('#entryModal');
      }

      entryModal.classList.add('active');
    } catch (err) {
      alert('Error fetching employee details: ' + err.message);
    }
  };

  if (closeEntryModalBtn) {
    closeEntryModalBtn.addEventListener('click', function () {
      entryModal.classList.remove('active');
      stopFaceCamera();
    });
  }

  const btnCancelEntryModal = document.getElementById('btnCancelEntryModal');
  if (btnCancelEntryModal) {
    btnCancelEntryModal.addEventListener('click', function () {
      entryModal.classList.remove('active');
      stopFaceCamera();
    });
  }

  if (btnResetForm) {
    btnResetForm.addEventListener('click', function () {
      employeeForm.reset();
      const inStatus = document.getElementById('inputStatus');
      if (inStatus) inStatus.value = 'Active';
      const inEmpType = document.getElementById('inputEmployeeType');
      if (inEmpType) inEmpType.value = 'standard';
      toggleFieldWorkerFormFields('standard');
      const inDob = document.getElementById('inputDob');
      if (inDob) inDob.value = '';
      const pPunch = document.getElementById('permPunchAttendance');
      if (pPunch) pPunch.checked = true;
      const pHist = document.getElementById('permAttendanceHistory');
      if (pHist) pHist.checked = true;
      const pPay = document.getElementById('permMonthlyPayslip');
      if (pPay) pPay.checked = true;
      const pCred = document.getElementById('permEmployeeCredentials');
      if (pCred) pCred.checked = true;
      const pLeave = document.getElementById('permLeavePermission');
      if (pLeave) pLeave.checked = true;
      renderEmployeeDocuments([]);
    });
  }

  // Auto-calculate and synchronize Day Salary, Half Day Salary, and Hourly Salary
  const inputSalaryType = document.getElementById('inputSalaryType');
  const inputHourly = document.getElementById('inputHourlySalary');
  const inputDay = document.getElementById('inputDaySalary');
  const inputHalfDay = document.getElementById('inputHalfDaySalary');
  const inputShift = document.getElementById('inputShiftHours');

  // Smart hour:minute format normalizer (e.g. 8.30 -> 08:30, 8 -> 08:00, 0 -> 00:00)
  function normalizeTimeInput(val) {
    if (val === undefined || val === null || String(val).trim() === '') return '08:00';
    let s = String(val).trim();
    if (s === '0' || s === '00' || s === '0:0' || s === '0:00' || s === '00:00') {
      return '00:00';
    }
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
    if (inputShift && inputShift.value.trim() !== '') {
      const val = inputShift.value.trim();
      if (val === '0' || val === '00' || val === '0:0' || val === '0:00' || val === '00:00') {
        return 0;
      }
      const parts = val.split(':');
      if (parts.length >= 2) {
        const h = parseFloat(parts[0]);
        const m = parseFloat(parts[1]);
        if (!isNaN(h) && !isNaN(m)) {
          const dur = h + (m / 60.0);
          return dur >= 0 ? dur : 8.0;
        }
      } else if (!isNaN(parseFloat(val))) {
        const dur = parseFloat(val);
        return dur >= 0 ? dur : 8.0;
      }
    }
    return 8.0;
  }

  // When Hourly changes
  function onHourlyInput() {
    const hourly = parseFloat(inputHourly.value) || 0;
    if (hourly <= 0) return;
    const dur = getShiftDuration();
    if (dur === 0) {
      if (inputDay) inputDay.value = '0';
      if (inputHalfDay) inputHalfDay.value = '0';
      return;
    }
    const day = hourly * dur;
    inputDay.value = day.toFixed(2);
    inputHalfDay.value = (day / 2).toFixed(2);
  }

  // When Day changes
  function onDayInput() {
    const day = parseFloat(inputDay.value) || 0;
    if (day <= 0) return;
    const dur = getShiftDuration();
    if (dur === 0) return;
    const st = inputSalaryType ? inputSalaryType.value : 'daily';
    if (st === 'hourly') {
      inputHourly.value = (day / dur).toFixed(2);
      inputHalfDay.value = (day / 2).toFixed(2);
    } else {
      inputDay.value = Math.round(day);
      inputHalfDay.value = Math.round(day / 2);
    }
  }

  // When Half-Day changes
  function onHalfDayInput() {
    const half = parseFloat(inputHalfDay.value) || 0;
    if (half <= 0) return;
    const dur = getShiftDuration();
    if (dur === 0) return;
    const st = inputSalaryType ? inputSalaryType.value : 'daily';
    if (st === 'hourly') {
      const day = half * 2;
      inputDay.value = day.toFixed(2);
      inputHourly.value = (day / dur).toFixed(2);
    } else {
      inputHalfDay.value = Math.round(half);
      inputDay.value = Math.round(half * 2);
    }
  }

  if (inputSalaryType) {
    inputSalaryType.addEventListener('change', function () {
      const st = this.value;
      if (st === 'hourly') {
        if (inputHourly) {
          inputHourly.step = '0.01';
          inputHourly.placeholder = 'Rate in Decimals (e.g. 150.50)';
          inputHourly.focus();
        }
        if (inputDay) inputDay.step = '0.01';
        if (inputHalfDay) inputHalfDay.step = '0.01';
      } else {
        if (inputHourly) {
          inputHourly.step = '1';
          inputHourly.placeholder = 'Amount (e.g. 100)';
        }
        if (inputDay) {
          inputDay.step = '1';
          if (inputDay.value) inputDay.value = Math.round(parseFloat(inputDay.value) || 0);
        }
        if (inputHalfDay) {
          inputHalfDay.step = '1';
          if (inputHalfDay.value) inputHalfDay.value = Math.round(parseFloat(inputHalfDay.value) || 0);
        }
        if (st === 'daily' && inputDay) inputDay.focus();
        else if (st === 'half_day' && inputHalfDay) inputHalfDay.focus();
      }
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
    inputShift.addEventListener('input', function () {
      if (getShiftDuration() === 0) {
        if (inputDay) inputDay.value = '0';
        if (inputHalfDay) inputHalfDay.value = '0';
      }
    });
    inputShift.addEventListener('change', function () {
      if (this.value !== '') this.value = normalizeTimeInput(this.value);
      if (getShiftDuration() === 0) {
        if (inputDay) inputDay.value = '0';
        if (inputHalfDay) inputHalfDay.value = '0';
        return;
      }
      const st = inputSalaryType ? inputSalaryType.value : 'daily';
      if (st === 'hourly') onHourlyInput();
      else if (st === 'daily') onDayInput();
      else onHalfDayInput();
    });
    inputShift.addEventListener('blur', function () {
      if (this.value !== '') this.value = normalizeTimeInput(this.value);
      if (getShiftDuration() === 0) {
        if (inputDay) inputDay.value = '0';
        if (inputHalfDay) inputHalfDay.value = '0';
      }
    });
  }

  if (employeeForm) {
    employeeForm.addEventListener('submit', async function (e) {
      e.preventDefault();

      if (employeeForm._isSubmitting) {
        return false;
      }

      // Ensure salary rates are calculated even if user only entered one
      const hourlyVal = inputHourly ? (parseFloat(inputHourly.value) || 0) : 0;
      const dayVal = inputDay ? (parseFloat(inputDay.value) || 0) : 0;
      const halfVal = inputHalfDay ? (parseFloat(inputHalfDay.value) || 0) : 0;
      const dur = getShiftDuration();

      if (dur === 0) {
        if (inputDay) inputDay.value = '0';
        if (inputHalfDay) inputHalfDay.value = '0';
        if (inputHourly && !inputHourly.value) inputHourly.value = '0.00';
      } else if (dayVal > 0) {
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

      // Lock form and engage feedback immediately
      employeeForm._isSubmitting = true;
      const btnSubmitForm = document.getElementById('btnSubmitForm');
      const origText = btnSubmitForm ? btnSubmitForm.innerHTML : 'Submit';
      if (btnSubmitForm) {
        btnSubmitForm.disabled = true;
        btnSubmitForm.classList.add('btn-is-submitting');
        btnSubmitForm.innerHTML = '<span class="spinner-ring" style="width:14px;height:14px;border-width:2px;display:inline-block;vertical-align:middle;margin-right:6px;"></span> Saving...';
      }
      if (window.showSavingPopup) {
        window.showSavingPopup(
          empId ? 'Saving Employee Changes...' : 'Saving Employee Details...',
          'Please wait while the system securely saves the employee profile and updates records.'
        );
      }

      const formData = new FormData(employeeForm);

      // Explicitly serialize employee type and field worker settings
      const inSubmitEmpType = document.getElementById('inputEmployeeType');
      const empTypeVal = inSubmitEmpType ? inSubmitEmpType.value : 'standard';
      const isFwSubmit = (empTypeVal === 'field_worker');
      formData.set('employee_type', empTypeVal);
      formData.set('is_field_worker', isFwSubmit ? 'true' : 'false');
      if (isFwSubmit) {
        const inTerritory = document.getElementById('inputTerritoryZone');
        const inVisitInc = document.getElementById('inputVisitIncentive');
        const inKmRate = document.getElementById('inputKmAllowance');
        if (inTerritory) formData.set('territory_zone', inTerritory.value.trim());
        if (inVisitInc) formData.set('per_visit_incentive', inVisitInc.value.trim());
        if (inKmRate) formData.set('km_allowance_rate', inKmRate.value.trim());
      } else {
        formData.set('territory_zone', '');
        formData.set('per_visit_incentive', '0');
        formData.set('km_allowance_rate', '0');
      }

      // Explicitly serialize employee portal permissions
      const permPunch = document.getElementById('permPunchAttendance');
      const permHist = document.getElementById('permAttendanceHistory');
      const permPay = document.getElementById('permMonthlyPayslip');
      const permCred = document.getElementById('permEmployeeCredentials');
      const permLeave = document.getElementById('permLeavePermission');
      formData.set('perm_punch_attendance', permPunch ? (permPunch.checked ? 'true' : 'false') : 'true');
      formData.set('perm_attendance_history', permHist ? (permHist.checked ? 'true' : 'false') : 'true');
      formData.set('perm_monthly_payslip', permPay ? (permPay.checked ? 'true' : 'false') : 'true');
      formData.set('perm_employee_credentials', permCred ? (permCred.checked ? 'true' : 'false') : 'true');
      formData.set('perm_leave_permission', permLeave ? (permLeave.checked ? 'true' : 'false') : 'true');

      // Explicitly serialize employee documents
      if (employeeDocsContainer) {
        // 1. Retained existing documents
        const existingRows = employeeDocsContainer.querySelectorAll('.existing-doc-row');
        const retainedDocs = [];
        existingRows.forEach(er => {
          const docId = er.dataset.docId;
          const titleEl = er.querySelector('.existing-doc-title');
          const matchedDoc = currentExistingDocs.find(d => String(d.id || '') === String(docId));
          if (matchedDoc) {
            const updatedDoc = { ...matchedDoc };
            if (titleEl && titleEl.value.trim()) {
              updatedDoc.document_name = titleEl.value.trim();
            }
            retainedDocs.push(updatedDoc);
          }
        });
        formData.set('existing_documents', JSON.stringify(retainedDocs));

        // 2. Newly uploaded documents
        const newRows = employeeDocsContainer.querySelectorAll('.new-doc-row');
        let newDocCount = 0;
        newRows.forEach(nr => {
          const fInput = nr.querySelector('.doc-file-input');
          const tInput = nr.querySelector('.new-doc-title');
          if (fInput && fInput.files && fInput.files[0]) {
            const file = fInput.files[0];
            const title = tInput ? tInput.value.trim() : '';
            formData.append(`doc_file_${newDocCount}`, file);
            formData.append(`doc_title_${newDocCount}`, title);
            newDocCount++;
          }
        });
        formData.set('doc_count', String(newDocCount));
      }

      // Attach webcam captured photo if user took snapshot
      if (currentCapturedBlob) {
        formData.set('photo', currentCapturedBlob, 'face_capture.jpg');
      }

      // Attach pre-generated biometrics & photo data if available (instant submit)
      if (capturedFaceEmbedding) {
        formData.set('face_embedding', typeof capturedFaceEmbedding === 'string' ? capturedFaceEmbedding : JSON.stringify(capturedFaceEmbedding));
      }
      if (capturedPhotoData) {
        formData.set('photo_data', capturedPhotoData);
      }
      if (capturedPhotoFilename) {
        formData.set('photo_filename', capturedPhotoFilename);
      }

      const url = empId ? `/api/employees/${empId}` : '/api/employees';
      const method = 'POST';

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
          capturedFaceEmbedding = null;
          capturedPhotoData = null;
          capturedPhotoFilename = null;
          const msg = data.message || (empId ? 'Employee updated successfully!' : 'Employee created successfully!');
          const empName = formData.get('employee_name') || 'Employee';
          if (window.ArgusVoice) {
            ArgusVoice.announceSuccess(
              `ஊழியர் ${empName} விவரங்கள் வெற்றிகரமாக சேமிக்கப்பட்டன.`,
              `Employee profile for ${empName} saved successfully.`
            );
          }
          if (window.hideSavingPopup) window.hideSavingPopup();
          alert(msg);
          loadEmployees();
        } else {
          if (window.hideSavingPopup) window.hideSavingPopup();
          if (window.ArgusVoice) {
            ArgusVoice.announceError('ஊழியர் விவரங்களை சேமிப்பதில் பிழை ஏற்பட்டது.', data.error || 'Failed to save employee.');
          }
          alert(data.error || 'Failed to save employee');
        }
      } catch (err) {
        if (window.hideSavingPopup) window.hideSavingPopup();
        alert('Error saving employee: ' + err.message);
      } finally {
        employeeForm._isSubmitting = false;
        if (window.hideSavingPopup) window.hideSavingPopup();
        if (btnSubmitForm) {
          btnSubmitForm.disabled = false;
          btnSubmitForm.classList.remove('btn-is-submitting');
          btnSubmitForm.innerHTML = origText;
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
        ['STATUS', (emp.status === 'Inactive') ? '<span class="status-pill status-inactive">Inactive</span>' : '<span class="status-pill status-active">Active</span>'],
        ['EMPLOYEE TYPE', emp.is_field_worker ? '<span class="status-pill" style="background:#ecfdf5;color:#047857;border:1px solid #a7f3d0;font-weight:700;">🏃 Field Worker (GPS Tracked)</span>' : '<span class="status-pill status-blue">🏢 Standard Employee (Office / In-House)</span>'],
        ...(emp.is_field_worker ? [
          ['TERRITORY / ZONE', emp.territory_zone ? `📍 ${escapeHtml(emp.territory_zone)}` : 'General Zone'],
          ['PER-VISIT INCENTIVE', emp.per_visit_incentive ? `₹${Number(emp.per_visit_incentive).toFixed(2)}` : '₹0.00'],
          ['KM ALLOWANCE RATE', emp.km_allowance_rate ? `₹${Number(emp.km_allowance_rate).toFixed(2)} / KM` : '₹0.00 / KM']
        ] : []),
        ['ASSIGNED BRANCH', emp.branch_name ? `📍 ${escapeHtml(emp.branch_name)}` : '🏢 Main / Head Office (Unassigned)'],
        ['SALARY BASIS', stLabels[emp.salary_type] || 'Hourly-Based'],
        ['HOURLY SALARY', emp.hourly_salary],
        ['DAY SALARY', emp.day_salary],
        ['HALF DAY SALARY', emp.half_day_salary],
        ['MOBILE NUMBER', emp.mobile_number],
        ['EMAIL ID', emp.email_id],
        ['AADHAR NUMBER', emp.aadhar_number],
        ['EMERGENCY CONTACT', emp.emergency_contact],
        ['DATE OF BIRTH', emp.date_of_birth || emp.dob || '-'],
        ['JOINING DATE', emp.joining_date],
        ['ACCOUNT HOLDER NAME', emp.account_holder_name],
        ['UPI NUMBER', emp.upi_number],
        ['ACCOUNT NUMBER', emp.account_number],
        ['IFSC CODE', emp.ifsc_code],
        ['SHIFT HOURS', emp.shift_hours || '09:00'],
        ['SHIFT START', emp.shift_start || '09:00 AM'],
        ['SHIFT END', emp.shift_end || '06:00 PM'],
        ['RECORD CREATED AT', formattedCreated]
      ];

      // Attached documents
      const docs = emp.documents || [];
      let docsHtml = '<span style="color: #94a3b8; font-style: italic;">No documents attached</span>';
      if (Array.isArray(docs) && docs.length > 0) {
        docsHtml = `<div style="display: flex; flex-direction: column; gap: 6px;">` + docs.map(d => {
          const dName = escapeHtml(d.document_name || d.filename || 'Document');
          const dUrl = escapeHtml(d.file_url || (d.filename ? `/static/uploads/employee_documents/${d.filename}` : '#'));
          const dExt = escapeHtml(d.file_type ? d.file_type.toUpperCase() : 'FILE');
          return `<div style="display: inline-flex; align-items: center; gap: 8px;">
            <span style="font-weight: 600; color: #1e293b;">${dName}</span>
            <span style="font-size: 10px; background: #e2e8f0; color: #475569; padding: 2px 6px; border-radius: 4px; font-weight: 700;">${dExt}</span>
            <a href="${dUrl}" target="_blank" class="btn-doc-view" style="padding: 3px 8px; font-size: 11px;">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8z"></path>
                <circle cx="12" cy="12" r="3"></circle>
              </svg> View
            </a>
          </div>`;
        }).join('') + `</div>`;
      }
      fields.push(['EMPLOYEE DOCUMENTS', docsHtml]);

      const htmlLabels = new Set(['PHOTO', 'STATUS', 'EMPLOYEE TYPE', 'EMPLOYEE DOCUMENTS']);

      fields.forEach(([label, val]) => {
        const tr = document.createElement('tr');
        const isHtml = htmlLabels.has(label) || (typeof val === 'string' && val.trim().startsWith('<') && val.trim().endsWith('>'));
        const displayVal = val ? (isHtml ? val : escapeHtml(String(val))) : '-';
        tr.innerHTML = `
          <td class="info-label">${label}</td>
          <td>${displayVal}</td>
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
          if (window.ArgusVoice) {
            ArgusVoice.announceSuccess('ஊழியர் விவரம் நீக்கப்பட்டது.', 'Employee record deleted successfully.');
          }
          loadEmployees();
        } else {
          alert(data.error || 'Failed to delete employee');
        }
      } catch (err) {
        alert('Error deleting employee: ' + err.message);
      }
    }
  };

  // Close viewModal and photoModal on clicking backdrop (entryModal can only close via X, Cancel, or Submit)
  [viewModal, photoModal].forEach(modal => {
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
      const bParam = new URLSearchParams(window.location.search).get('branch_id');
      window.location.href = `/api/employees/export/csv?search=${encodeURIComponent(currentSearch)}&status=${encodeURIComponent(currentStatus)}${bParam ? '&branch_id=' + encodeURIComponent(bParam) : ''}`;
    });
  }

  if (btnExcelEmployees) {
    btnExcelEmployees.addEventListener('click', function () {
      const bParam = new URLSearchParams(window.location.search).get('branch_id');
      window.location.href = `/api/employees/export/excel?search=${encodeURIComponent(currentSearch)}&status=${encodeURIComponent(currentStatus)}${bParam ? '&branch_id=' + encodeURIComponent(bParam) : ''}`;
    });
  }

  if (btnPdfEmployees) {
    btnPdfEmployees.addEventListener('click', function () {
      const bParam = new URLSearchParams(window.location.search).get('branch_id');
      window.location.href = `/api/employees/export/pdf?search=${encodeURIComponent(currentSearch)}&status=${encodeURIComponent(currentStatus)}${bParam ? '&branch_id=' + encodeURIComponent(bParam) : ''}`;
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
    stopAllSpeech();
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
        faceStream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',
            width: { ideal: 640 },
            height: { ideal: 480 }
          }
        });
        faceRegVideo.srcObject = faceStream;
        if (cameraStatusMsg) {
          cameraStatusMsg.textContent = 'Position face within frame and click Capture Snapshot';
          cameraStatusMsg.style.color = '#198754';
        }
        speakVoiceAlert({
          tamil: 'கேமராவை நேராகப் பார்த்து முகத்தை வட்டத்திற்குள் வைக்கவும்.',
          english: 'Please look straight at the camera and align your face inside the circle.'
        });
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


  // ===== REAL-TIME VOICE ANNOUNCER (UNIVERSAL DUAL-ENGINE TAMIL VOICE) =====
  let cachedTamilVoices = [];
  let activeTamilAudio = null;

  function stopAllSpeech() {
    if ('speechSynthesis' in window) {
      try { window.speechSynthesis.cancel(); } catch (e) {}
    }
    if (activeTamilAudio) {
      try {
        activeTamilAudio.pause();
        activeTamilAudio.currentTime = 0;
      } catch (e) {}
      activeTamilAudio = null;
    }
  }

  function updateTamilVoicesCache() {
    if (!('speechSynthesis' in window)) return;
    try {
      cachedTamilVoices = window.speechSynthesis.getVoices() || [];
    } catch (e) {
      cachedTamilVoices = [];
    }
  }
  if ('speechSynthesis' in window) {
    updateTamilVoicesCache();
    window.speechSynthesis.onvoiceschanged = updateTamilVoicesCache;
  }

  function getTamilVoice() {
    if (!cachedTamilVoices || cachedTamilVoices.length === 0) {
      updateTamilVoicesCache();
    }
    const voices = cachedTamilVoices;
    if (!voices || voices.length === 0) return null;

    // Priority 1: Exact regional match for Indian Tamil (ta-IN or ta_IN)
    let found = voices.find(v => v.lang === 'ta-IN' || v.lang === 'ta_IN');

    // Priority 2: Generic Tamil (ta) or Sri Lanka (ta-LK)
    if (!found) {
      found = voices.find(v => v.lang && v.lang.toLowerCase().startsWith('ta'));
    }

    // Priority 3: Search by voice name containing tamil keywords
    if (!found) {
      found = voices.find(v => {
        const n = (v.name || '').toLowerCase();
        return n.includes('tamil') || n.includes('தமிழ்') || n.includes('valluvar') || n.includes('pallavi');
      });
    }

    return found || null;
  }

  function isMobileDevice() {
    const ua = navigator.userAgent || '';
    const mobileRegex = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile/i;
    const hasTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    return mobileRegex.test(ua) || (hasTouch && window.innerWidth <= 1024);
  }

  function getEnglishVoice() {
    if (!('speechSynthesis' in window)) return null;
    const voices = window.speechSynthesis.getVoices();
    if (!voices || voices.length === 0) return null;
    let found = voices.find(v => {
      const n = (v.name || '').toLowerCase();
      return (v.lang === 'en-US' || v.lang === 'en-GB' || v.lang === 'en-IN') &&
             (n.includes('natural') || n.includes('david') || n.includes('zira') || n.includes('google') || n.includes('samantha'));
    });
    if (!found) {
      found = voices.find(v => v.lang === 'en-US' || v.lang === 'en-GB' || v.lang === 'en-IN');
    }
    if (!found) {
      found = voices.find(v => v.lang && v.lang.toLowerCase().startsWith('en'));
    }
    return found || voices[0] || null;
  }

  function playServerTamilAudio(text) {
    if (!text) return;
    stopAllSpeech();
    try {
      const url = '/api/voice/tamil-tts?text=' + encodeURIComponent(text) + '&lang=ta';
      const audio = new Audio(url);
      audio.playbackRate = 1.45;
      activeTamilAudio = audio;
      audio.play().catch(e => {
        console.warn('Server Tamil Audio playback notice:', e);
      });
    } catch (err) {
      console.warn('Server Tamil Audio error:', err);
    }
  }

  const TAMIL_REG_MESSAGES = {
    NO_FACE: 'படம் ஏற்கப்படவில்லை. முகம் தெளிவாகத் தெரியவில்லை. வெளிச்சமான இடத்தில் கேமராவை நேராகப் பார்க்கவும்.',
    MULTIPLE_FACES: 'படம் ஏற்கப்படவில்லை. ஒன்றுக்கு மேற்பட்ட முகங்கள் உள்ளன. ஒருவர் மட்டுமே இருக்க வேண்டும்.',
    FACE_OCCLUDED: 'படம் ஏற்கப்படவில்லை. கையை முகத்திலிருந்து எடுத்துவிட்டு முழு முகத்தையும் காட்டவும்.',
    FACE_TOO_SMALL: 'படம் ஏற்கப்படவில்லை. முகம் மிகத் தொலைவில் உள்ளது. சற்று அருகில் வரவும்.',
    FACE_TOO_CLOSE: 'படம் ஏற்கப்படவில்லை. முகம் மிக அருகில் உள்ளது. சற்று பின்னால் நிற்கவும்.',
    TOO_DARK: 'படம் ஏற்கப்படவில்லை. வெளிச்சம் குறைவாக உள்ளது. வெளிச்சமான இடத்திற்கு செல்லவும்.',
    TOO_BRIGHT: 'படம் ஏற்கப்படவில்லை. அதிக ஒளிக்கீற்று அல்லது பிரகாசம் உள்ளது.',
    BLURRY: 'படம் ஏற்கப்படவில்லை. புகைப்படம் மங்கலாக உள்ளது. கேமராவை அசைக்காமல் பிடிக்கவும்.',
    HEAD_TILTED: 'படம் ஏற்கப்படவில்லை. தலையை சாய்க்காமல் நேராக வைக்கவும்.',
    EMBEDDING_FAILED: 'படம் ஏற்கப்படவில்லை. கேமராவை நேராகப் பார்த்து மீண்டும் முயற்சிக்கவும்.',
    SUCCESS: 'முகம் வெற்றிகரமாக ஏற்றுக்கொள்ளப்பட்டது!'
  };

  const ENGLISH_REG_MESSAGES = {
    NO_FACE: 'Photo not accepted. No clear face detected. Please face the camera directly in good lighting.',
    MULTIPLE_FACES: 'Photo not accepted. Multiple faces detected. Only one person should be present.',
    FACE_OCCLUDED: 'Photo not accepted. Please remove hands from face and show your full face.',
    FACE_TOO_SMALL: 'Photo not accepted. Face is too far away. Please move closer.',
    FACE_TOO_CLOSE: 'Photo not accepted. Face is too close. Please step back slightly.',
    TOO_DARK: 'Photo not accepted. Lighting is too dim. Please move to a well-lit area.',
    TOO_BRIGHT: 'Photo not accepted. Too much glare or brightness.',
    BLURRY: 'Photo not accepted. Image is blurry. Please hold steady.',
    HEAD_TILTED: 'Photo not accepted. Please keep your head straight.',
    EMBEDDING_FAILED: 'Photo not accepted. Please face the camera directly and try again.',
    SUCCESS: 'Face photo verified and accepted successfully!'
  };

  function speakTamilVoiceAlert(text) {
    if (!text) return;
    if (localStorage.getItem('argus_voice_assist') === 'false') return;

    // Mobile phones & Tamil-enabled devices: native SpeechSynthesis
    const tamilVoice = getTamilVoice();
    if (tamilVoice && ('speechSynthesis' in window)) {
      try {
        stopAllSpeech();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.45;
        utterance.pitch = 1.0;
        utterance.voice = tamilVoice;
        utterance.lang = tamilVoice.lang || 'ta-IN';
        window.speechSynthesis.speak(utterance);
        return;
      } catch (err) {
        console.warn('Native speech synthesis error, using server fallback:', err);
      }
    }

    // High-fidelity Server-side Tamil TTS stream fallback for mobile
    playServerTamilAudio(text);
  }

  function speakVoiceAlert(content) {
    if (!content) return;
    if (localStorage.getItem('argus_voice_assist') === 'false') return;

    const isMobile = isMobileDevice();

    if (!isMobile) {
      // Desktop: speak English via native desktop speech synthesis
      let englishText = '';
      if (typeof content === 'object') {
        englishText = content.english || content.tamil || '';
      } else if (typeof content === 'string') {
        englishText = ENGLISH_REG_MESSAGES[content] || content;
      }
      if (!englishText) return;

      if ('speechSynthesis' in window) {
        try {
          stopAllSpeech();
          const utterance = new SpeechSynthesisUtterance(englishText);
          const enVoice = getEnglishVoice();
          if (enVoice) utterance.voice = enVoice;
          utterance.lang = (enVoice && enVoice.lang) || 'en-US';
          utterance.rate = 1.0;
          utterance.pitch = 1.0;
          window.speechSynthesis.speak(utterance);
          return;
        } catch (err) {
          console.warn('Desktop English SpeechSynthesis error:', err);
        }
      }
      return;
    }

    // Mobile phones: preserve existing pure Tamil voice
    let tamilText = '';
    if (typeof content === 'object') {
      tamilText = content.tamil || content.english || '';
    } else if (typeof content === 'string') {
      tamilText = TAMIL_REG_MESSAGES[content] || content;
    }
    if (!tamilText) return;

    speakTamilVoiceAlert(tamilText);
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

      const origBtnText = btnTakeSnapshot.textContent;
      btnTakeSnapshot.disabled = true;
      btnTakeSnapshot.textContent = 'Analyzing Biometrics...';
      if (cameraStatusMsg) {
        cameraStatusMsg.innerHTML = '<span style="color:#0284c7;"><i class="fa-solid fa-spinner fa-spin"></i> Analyzing face position, lighting & clarity...</span>';
      }

      faceRegCanvas.toBlob(async function (blob) {
        if (!blob) {
          btnTakeSnapshot.disabled = false;
          btnTakeSnapshot.textContent = origBtnText;
          if (cameraStatusMsg) {
            cameraStatusMsg.textContent = 'Failed to capture frame from camera. Please try again.';
            cameraStatusMsg.style.color = '#dc2626';
          }
          return;
        }

        try {
          const fd = new FormData();
          fd.append('photo', blob, 'face_capture.jpg');

          const res = await fetch('/api/face/extract-biometrics', {
            method: 'POST',
            body: fd
          });

          let resData = null;
          try {
            const rawText = await res.text();
            resData = JSON.parse(rawText);
          } catch (jsonErr) {
            resData = null;
          }

          if (!res.ok || !resData || !resData.success) {
            btnTakeSnapshot.disabled = false;
            btnTakeSnapshot.textContent = origBtnText;
            const errMsg = (resData && resData.error) ? resData.error : 'No clear face detected in snapshot. Please face the camera directly in good lighting.';
            const spokenTamil = (resData && (resData.spoken_tamil_error || (resData.code && TAMIL_REG_MESSAGES[resData.code]))) ||
                           TAMIL_REG_MESSAGES.NO_FACE;
            const spokenEnglish = (resData && (resData.spoken_error || resData.error || (resData.code && ENGLISH_REG_MESSAGES[resData.code]))) ||
                           errMsg || ENGLISH_REG_MESSAGES.NO_FACE;
            const advice = (resData && resData.advice) ? resData.advice : '';

            // Read the rejection message aloud (Tamil on Mobile, English on Desktop)
            speakVoiceAlert({ tamil: spokenTamil, english: spokenEnglish });

            if (cameraStatusMsg) {
              cameraStatusMsg.innerHTML = `
                <div style="background:#fef2f2; border:1px solid #f87171; border-radius:6px; padding:8px 12px; margin-top:8px; text-align:left;">
                  <div style="color:#b91c1c; font-weight:800; font-size:12px; display:flex; align-items:center; gap:6px;">
                    <i class="fa-solid fa-triangle-exclamation"></i>
                    <span>SNAPSHOT NOT ACCEPTED</span>
                  </div>
                  <div style="color:#7f1d1d; font-size:11.5px; margin-top:4px; font-weight:600; line-height:1.4;">
                    ${errMsg}
                  </div>
                  ${advice ? `<div style="color:#991b1b; font-size:11px; margin-top:3px; font-style:italic;">💡 Tip: ${advice}</div>` : ''}
                </div>
              `;
            }
            if (captureStatus) {
              captureStatus.innerHTML = `
                <div style="background:#fef2f2; border:1px solid #f87171; border-radius:6px; padding:8px 12px; margin-top:8px;">
                  <div style="color:#b91c1c; font-weight:800; font-size:11.5px;">⚠️ Snapshot Rejected</div>
                  <div style="color:#7f1d1d; font-size:11px; margin-top:2px;">${errMsg}</div>
                </div>
              `;
            }
            return;
          }

          // SUCCESS: Quality validated and biometrics extracted!
          currentCapturedBlob = blob;
          capturedFaceEmbedding = resData.embedding;
          capturedPhotoData = resData.photo_data || null;
          capturedPhotoFilename = resData.photo_filename || 'face_capture.jpg';

          // Announce success (Tamil on Mobile, English on Desktop)
          speakVoiceAlert({
            tamil: (resData && resData.spoken_tamil_message) || TAMIL_REG_MESSAGES.SUCCESS,
            english: (resData && resData.spoken_message) || ENGLISH_REG_MESSAGES.SUCCESS
          });

          try {
            const file = new File([blob], 'face_capture.jpg', { type: 'image/jpeg' });
            const dt = new DataTransfer();
            dt.items.add(file);
            inputPhoto.files = dt.files;
          } catch (err) {
            console.warn('DataTransfer fallback used for photo upload:', err);
          }

          if (cameraStatusMsg) {
            cameraStatusMsg.innerHTML = `
              <div style="background:#f0fdf4; border:1px solid #86efac; border-radius:6px; padding:8px 12px; margin-top:8px;">
                <div style="color:#15803d; font-weight:800; font-size:12px; display:flex; align-items:center; gap:6px;">
                  <i class="fa-solid fa-circle-check"></i>
                  <span>FACE VERIFIED &amp; ACCEPTED!</span>
                </div>
                <div style="color:#166534; font-size:11px; margin-top:2px;">
                  Quality approved. Saving biometrics...
                </div>
              </div>
            `;
          }

          if (captureStatus) {
            captureStatus.innerHTML = `
              <div style="background:#f0fdf4; border:1px solid #86efac; border-radius:6px; padding:8px 12px; margin-top:8px;">
                <div style="color:#15803d; font-weight:800; font-size:12px; display:flex; align-items:center; gap:6px;">
                  <i class="fa-solid fa-circle-check"></i>
                  <span>FACE VERIFIED &amp; APPROVED</span>
                </div>
                <div style="color:#166534; font-size:11px; margin-top:2px;">
                  Face position, lighting, and clarity approved for AI attendance.
                </div>
              </div>
            `;
          }

          const photoPreviewBox = document.getElementById('currentPhotoPreview');
          const editThumb = document.getElementById('editPhotoThumb');
          const editNote = document.getElementById('editPhotoNote');
          if (photoPreviewBox && editThumb) {
            editThumb.src = capturedPhotoData || URL.createObjectURL(blob);
            if (editNote) editNote.textContent = '✓ AI Face Biometrics generated & verified. Ready to save.';
            photoPreviewBox.style.display = 'flex';
          }

          btnTakeSnapshot.disabled = false;
          btnTakeSnapshot.textContent = origBtnText;

          // Smoothly close camera modal after short delay so user sees green verification
          setTimeout(() => {
            stopFaceCamera();
          }, 900);
        } catch (netErr) {
          console.error('Error during biometric extraction:', netErr);
          btnTakeSnapshot.disabled = false;
          btnTakeSnapshot.textContent = origBtnText;
          if (cameraStatusMsg) {
            cameraStatusMsg.textContent = '⚠️ Network error during biometric generation: ' + netErr.message;
            cameraStatusMsg.style.color = '#dc2626';
          }
        }
      }, 'image/jpeg', 0.9);
    });
  }

  // Live preview & biometrics extraction when selecting image via file input
  if (inputPhoto) {
    inputPhoto.addEventListener('change', async function () {
      if (this.files && this.files[0]) {
        const file = this.files[0];
        currentCapturedBlob = null;
        capturedFaceEmbedding = null;
        capturedPhotoData = null;
        capturedPhotoFilename = null;

        const photoPreviewBox = document.getElementById('currentPhotoPreview');
        const editThumb = document.getElementById('editPhotoThumb');
        const editNote = document.getElementById('editPhotoNote');
        if (photoPreviewBox && editThumb) {
          editThumb.src = URL.createObjectURL(file);
          if (editNote) editNote.textContent = `⏳ Verifying face position, lighting & clarity in ${file.name}...`;
          photoPreviewBox.style.display = 'flex';
        }
        if (captureStatus) {
          captureStatus.innerHTML = `<span style="color:#0284c7;"><i class="fa-solid fa-spinner fa-spin"></i> Analyzing face position, lighting &amp; clarity in ${file.name}...</span>`;
        }

        try {
          const fd = new FormData();
          fd.append('photo', file);
          const res = await fetch('/api/face/extract-biometrics', {
            method: 'POST',
            body: fd
          });
          let resData = null;
          try {
            const rawText = await res.text();
            resData = JSON.parse(rawText);
          } catch (jsonErr) {
            resData = null;
          }

          if (res.ok && resData && resData.success && resData.embedding) {
            capturedFaceEmbedding = resData.embedding;
            capturedPhotoData = resData.photo_data || null;
            capturedPhotoFilename = resData.photo_filename || file.name;

            // Announce success aloud (Tamil on Mobile, English on Desktop)
            speakVoiceAlert({
              tamil: (resData && resData.spoken_tamil_message) || TAMIL_REG_MESSAGES.SUCCESS,
              english: (resData && resData.spoken_message) || ENGLISH_REG_MESSAGES.SUCCESS
            });

            if (captureStatus) {
              captureStatus.innerHTML = `
                <div style="background:#f0fdf4; border:1px solid #86efac; border-radius:6px; padding:8px 12px; margin-top:8px;">
                  <div style="color:#15803d; font-weight:800; font-size:12px; display:flex; align-items:center; gap:6px;">
                    <i class="fa-solid fa-circle-check"></i>
                    <span>FACE VERIFIED &amp; APPROVED</span>
                  </div>
                  <div style="color:#166534; font-size:11px; margin-top:2px;">
                    Face position, lighting, and clarity approved for AI attendance.
                  </div>
                </div>
              `;
            }
            if (editNote) editNote.textContent = `✓ AI Face Biometrics verified in ${file.name}.`;
          } else {
            const warn = (resData && resData.error) ? resData.error : 'No clear face detected in photo.';
            const spokenTamil = (resData && (resData.spoken_tamil_error || (resData.code && TAMIL_REG_MESSAGES[resData.code]))) ||
                           TAMIL_REG_MESSAGES.NO_FACE;
            const spokenEnglish = (resData && (resData.spoken_error || resData.error || (resData.code && ENGLISH_REG_MESSAGES[resData.code]))) ||
                           warn || ENGLISH_REG_MESSAGES.NO_FACE;
            const advice = (resData && resData.advice) ? resData.advice : '';

            // Read the rejection message aloud (Tamil on Mobile, English on Desktop)
            speakVoiceAlert({ tamil: spokenTamil, english: spokenEnglish });

            // Clear input & state so unacceptable image cannot be saved
            inputPhoto.value = '';
            currentCapturedBlob = null;
            capturedFaceEmbedding = null;
            capturedPhotoData = null;
            capturedPhotoFilename = null;

            if (captureStatus) {
              captureStatus.innerHTML = `
                <div style="background:#fef2f2; border:1px solid #f87171; border-radius:6px; padding:10px 12px; margin-top:8px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                  <div style="display:flex; align-items:center; gap:8px; color:#b91c1c; font-weight:800; font-size:12px;">
                    <i class="fa-solid fa-triangle-exclamation" style="font-size:14px;"></i>
                    <span>IMAGE NOT ACCEPTED</span>
                  </div>
                  <div style="color:#7f1d1d; font-size:11.5px; margin-top:4px; font-weight:600; line-height:1.4;">
                    ${warn}
                  </div>
                  ${advice ? `<div style="color:#991b1b; font-size:11px; margin-top:4px; font-style:italic;">💡 Tip: ${advice}</div>` : ''}
                </div>
              `;
            }
            if (editNote) editNote.textContent = `⚠️ Image not accepted: ${warn}`;
          }
        } catch (e) {
          if (captureStatus) {
            captureStatus.textContent = `⚠️ Error analyzing photo: ${e.message}`;
            captureStatus.style.color = '#dc2626';
          }
        }
      }
    });
  }


  // Also stop face camera when employee entry modal closes
  const closeEntryModalBtn2 = document.getElementById('closeEntryModal');
  if (closeEntryModalBtn2) {
    closeEntryModalBtn2.addEventListener('click', stopFaceCamera);
  }

  // Voice AI Field Guidance for Employee Registration & Edit Modal
  if (window.ArgusVoice) {
    window.ArgusVoice.bindToggle('btnEntryModalToggleVoice');

    window.ArgusVoice.attachFormGuidance('#entryModal', {
      '#inputName': {
        english: 'Please enter the full name of the employee.',
        tamil: 'தயவுசெய்து ஊழியரின் முழுப் பெயரை உள்ளிடவும்.'
      },
      '#inputDepartment': {
        english: 'Enter the department, such as Production, IT, or HR.',
        tamil: 'தயவுசெய்து ஊழியரின் துறையை உள்ளிடவும்.'
      },
      '#inputDesignation': {
        english: 'Specify the employee job designation or role.',
        tamil: 'ஊழியரின் பதவி அல்லது பொறுப்பை உள்ளிடவும்.'
      },
      '#inputMobile': {
        english: 'Please enter a valid 10-digit mobile number.',
        tamil: 'பத்து இலக்க செல்லுபடியாகும் செல்போன் எண்ணை உள்ளிடவும்.'
      },
      '#inputEmail': {
        english: 'Please enter a valid email address with an at symbol.',
        tamil: 'அட் குறியீட்டுடன் செல்லுபடியாகும் மின்னஞ்சல் முகவரியை உள்ளிடவும்.'
      },
      '#inputDaySalary': {
        english: 'Enter the daily salary amount in rupees.',
        tamil: 'ஒரு நாளுக்கான சம்பளத் தொகையை ரூபாயில் உள்ளிடவும்.'
      },
      '#inputHalfDaySalary': {
        english: 'Enter the half day salary amount in rupees.',
        tamil: 'அரை நாளுக்கான சம்பளத் தொகையை உள்ளிடவும்.'
      },
      '#inputHourlySalary': {
        english: 'Enter the hourly pay rate in rupees.',
        tamil: 'ஒரு மணி நேரத்திற்கான ஊதியத்தை உள்ளிடவும்.'
      },
      '#inputBankName': {
        english: 'Enter the bank name for salary disbursements.',
        tamil: 'சம்பளப் பரிமாற்றத்திற்கான வங்கிப் பெயரை உள்ளிடவும்.'
      },
      '#inputAccountNo': {
        english: 'Enter the bank account number carefully.',
        tamil: 'வங்கி கணக்கு எண்ணை கவனமாக உள்ளிடவும்.'
      },
      '#inputIfscCode': {
        english: 'Enter the eleven-character bank IFSC code.',
        tamil: 'பதினொரு எழுத்துக்கள் கொண்ட ஐ.எஃப்.எஸ்.சி குறியீட்டை உள்ளிடவும்.'
      },
      '#inputShiftHours': {
        english: 'Set daily shift working hours, for example 8 hours.',
        tamil: 'ஒரு நாளுக்கான வேலை நேரத்தை உள்ளிடவும்.'
      },
      '#inputGracePeriod': {
        english: 'Enter grace period minutes allowed for late punch in.',
        tamil: 'தாமத வருகைக்கு அனுமதிக்கப்பட்ட சலுகை நிமிடங்களை உள்ளிடவும்.'
      }
    });
  }
});
