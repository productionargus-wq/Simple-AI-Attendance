// Manage Companies JavaScript
document.addEventListener('DOMContentLoaded', function () {
  let currentPage = 1;
  let currentLimit = 10;
  let currentSearch = '';

  const companyTableBody = document.getElementById('companyTableBody');
  const companyEntriesLimit = document.getElementById('companyEntriesLimit');
  const companyTableSearch = document.getElementById('companyTableSearch');
  const companyTableInfo = document.getElementById('companyTableInfo');
  const companyPrevBtn = document.getElementById('companyPrevBtn');
  const companyCurrentBtn = document.getElementById('companyCurrentBtn');
  const companyNextBtn = document.getElementById('companyNextBtn');

  // Modal elements
  const companyModal = document.getElementById('companyModal');
  const companyModalTitle = document.getElementById('companyModalTitle');
  const btnSaveCompany = document.getElementById('btnSaveCompany');
  const btnOpenAddCompanyModal = document.getElementById('btnOpenAddCompanyModal');
  const closeCompanyModal = document.getElementById('closeCompanyModal');
  const btnCancelCompany = document.getElementById('btnCancelCompany');
  const companyForm = document.getElementById('companyForm');
  const companyFormAlert = document.getElementById('companyFormAlert');
  const btnDetectLocation = document.getElementById('btnDetectLocation');

  const inputCompanyName = document.getElementById('inputCompanyName');
  const inputGstin = document.getElementById('inputGstin');
  const inputPhone = document.getElementById('inputPhone');
  const inputEmail = document.getElementById('inputEmail');
  const inputLatitude = document.getElementById('inputLatitude');
  const inputLongitude = document.getElementById('inputLongitude');
  const inputStatus = document.getElementById('inputStatus');
  const inputEmployeeLimit = document.getElementById('inputEmployeeLimit');
  const inputCompanyShiftHours = document.getElementById('inputShiftHours');
  const inputRegisteredDate = document.getElementById('inputRegisteredDate');
  const inputAutoEmailReports = document.getElementById('inputAutoEmailReports');
  const inputCanDeleteEntries = document.getElementById('inputCanDeleteEntries');
  const inputSupportEnabled = document.getElementById('inputSupportEnabled');
  const inputGeofenceRadius = document.getElementById('inputGeofenceRadius');

  // Cascade Delete Confirmation Modal elements
  const deleteCompanyModal = document.getElementById('deleteCompanyModal');
  const closeDeleteCompanyModal = document.getElementById('closeDeleteCompanyModal');
  const btnCancelDeleteCompany = document.getElementById('btnCancelDeleteCompany');
  const btnConfirmDeleteCompany = document.getElementById('btnConfirmDeleteCompany');
  const deleteCompanyTargetName = document.getElementById('deleteCompanyTargetName');
  const deleteCompanyTargetId = document.getElementById('deleteCompanyTargetId');
  const btnConfirmDeleteText = document.getElementById('btnConfirmDeleteText');
  let companyToDeleteId = null;
  let companyToDeleteName = '';

  function formatDateForDateInput(val) {
    if (!val || val === '-') return new Date().toISOString().split('T')[0];
    const s = String(val).trim();
    if (s.includes('/')) {
      const parts = s.split(' ')[0].split('/');
      if (parts.length === 3) {
        return `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
      }
    } else if (s.includes('-')) {
      const parts = s.split(' ')[0].split('-');
      if (parts.length === 3) {
        if (parts[0].length === 4) return parts.join('-');
        return `${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}`;
      }
    }
    return new Date().toISOString().split('T')[0];
  }

  let loadedCompanies = [];
  let editingCompanyId = null;

  // Reports modal elements
  const reportsModal = document.getElementById('reportsModal');
  const btnOpenReportsModal = document.getElementById('btnOpenReportsModal');
  const closeReportsModal = document.getElementById('closeReportsModal');
  const btnCloseReportsFooter = document.getElementById('btnCloseReportsFooter');

  // View modal elements
  const viewCompanyModal = document.getElementById('viewCompanyModal');
  const closeViewCompanyModal = document.getElementById('closeViewCompanyModal');
  const btnCloseViewCompanyFooter = document.getElementById('btnCloseViewCompanyFooter');
  const viewCompanyName = document.getElementById('viewCompanyName');
  const viewCompanyId = document.getElementById('viewCompanyId');
  const viewCompanyRegisteredDate = document.getElementById('viewCompanyRegisteredDate');
  const viewCompanyGstin = document.getElementById('viewCompanyGstin');
  const viewCompanyPhone = document.getElementById('viewCompanyPhone');
  const viewCompanyEmail = document.getElementById('viewCompanyEmail');
  const viewCompanyLocation = document.getElementById('viewCompanyLocation');
  const viewCompanyShiftHours = document.getElementById('viewCompanyShiftHours');
  const viewCompanyEmployees = document.getElementById('viewCompanyEmployees');
  const viewCompanyStatusBadge = document.getElementById('viewCompanyStatusBadge');
  const viewCompanyReportsBadge = document.getElementById('viewCompanyReportsBadge');
  const viewCompanyDeleteEntriesBadge = document.getElementById('viewCompanyDeleteEntriesBadge');

  function formatDisplayDate(dateStr) {
    if (!dateStr || dateStr === '-') return '-';
    if (typeof dateStr === 'string' && (dateStr.includes('T') || (dateStr.includes('-') && dateStr.includes(':')))) {
      try {
        const d = new Date(dateStr.replace(' ', 'T'));
        if (!isNaN(d.getTime())) {
          const day = String(d.getDate()).padStart(2, '0');
          const month = String(d.getMonth() + 1).padStart(2, '0');
          const year = d.getFullYear();
          let hours = d.getHours();
          const minutes = String(d.getMinutes()).padStart(2, '0');
          const ampm = hours >= 12 ? 'PM' : 'AM';
          hours = hours % 12;
          hours = hours ? hours : 12;
          const strHours = String(hours).padStart(2, '0');
          return `${day}/${month}/${year} ${strHours}:${minutes} ${ampm}`;
        }
      } catch (e) {}
    }
    return dateStr;
  }

  // Fetch and display companies
  async function loadCompanies(page = 1) {
    currentPage = page;
    companyTableBody.innerHTML = `
      <tr>
        <td colspan="12" style="text-align: center; padding: 24px; color: #6c757d;">Loading companies...</td>
      </tr>
    `;

    try {
      const params = new URLSearchParams({
        page: currentPage,
        limit: currentLimit,
        search: currentSearch
      });

      const res = await fetch(`/api/companies?${params.toString()}`);
      const data = await res.json();
      loadedCompanies = data.companies || [];

      if (!data.companies || data.companies.length === 0) {
        companyTableBody.innerHTML = `
          <tr>
            <td colspan="13" style="text-align: center; padding: 28px; color: #6c757d;">
              No registered companies found. Click <strong>+ Add Company</strong> above to register a new tenant.
            </td>
          </tr>
        `;
        companyTableInfo.textContent = 'Showing 0 to 0 of 0 entries';
        updatePagination(0, 0);
        return;
      }

      companyTableBody.innerHTML = '';
      const startIndex = (data.page - 1) * data.limit;

      data.companies.forEach((comp, idx) => {
        const slNo = startIndex + idx + 1;
        const hasCoords = (comp.latitude !== undefined && comp.latitude !== null && String(comp.latitude).trim() !== '') &&
                          (comp.longitude !== undefined && comp.longitude !== null && String(comp.longitude).trim() !== '');
        const lat = hasCoords ? (isNaN(Number(comp.latitude)) ? comp.latitude : Number(comp.latitude).toFixed(5)) : '-';
        const lng = hasCoords ? (isNaN(Number(comp.longitude)) ? comp.longitude : Number(comp.longitude).toFixed(5)) : '-';
        const isDeactive = String(comp.status || '').trim().toLowerCase() === 'deactive' || String(comp.status || '').trim().toLowerCase() === 'inactive';
        const statusBadge = !isDeactive
          ? `<span class="status-pill status-active">Active</span>`
          : `<span class="status-pill status-inactive" style="background-color: #fee2e2; color: #b91c1c; border: 1px solid #f87171;">Deactive</span>`;

        const isAutoReports = comp.auto_email_reports !== false;
        const autoReportsBadge = isAutoReports
          ? `<button type="button" class="btn-toggle-auto-reports btn-reports-enabled" data-id="${comp.id}" data-name="${escapeHtml(comp.company_name)}" data-state="true" title="Auto Email Reports: ENABLED (Click to turn off)" style="background-color: #e8f5e9; color: #2e7d32; border: 1.5px solid #a5d6a7; border-radius: 16px; padding: 4px 10px; font-size: 11px; font-weight: 800; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 0.2s ease; white-space: nowrap;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                <polyline points="22,6 12,13 2,6"></polyline>
              </svg>
              <span>ON</span>
            </button>`
          : `<button type="button" class="btn-toggle-auto-reports btn-reports-disabled" data-id="${comp.id}" data-name="${escapeHtml(comp.company_name)}" data-state="false" title="Auto Email Reports: DISABLED (Click to turn on)" style="background-color: #f1f5f9; color: #64748b; border: 1.5px solid #cbd5e1; border-radius: 16px; padding: 4px 10px; font-size: 11px; font-weight: 800; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 0.2s ease; opacity: 0.85; white-space: nowrap;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                <line x1="2" y1="2" x2="22" y2="22"></line>
              </svg>
              <span>OFF</span>
            </button>`;

        const isDeleteEnabled = comp.can_delete_entries === true;
        const deleteEntriesBadge = isDeleteEnabled
          ? `<button type="button" class="btn-toggle-delete-entries btn-delete-perm-enabled" data-id="${comp.id}" data-name="${escapeHtml(comp.company_name)}" data-state="true" title="Delete Entries: ENABLED (Click to turn off)" style="background-color: #e8f5e9; color: #166534; border: 1.5px solid #86efac; border-radius: 16px; padding: 4px 10px; font-size: 11px; font-weight: 800; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 0.2s ease; white-space: nowrap;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              <span>Delete Enabled</span>
            </button>`
          : `<button type="button" class="btn-toggle-delete-entries btn-delete-perm-disabled" data-id="${comp.id}" data-name="${escapeHtml(comp.company_name)}" data-state="false" title="Delete Entries: DISABLED (Click to turn on)" style="background-color: #fee2e2; color: #b91c1c; border: 1.5px solid #fca5a5; border-radius: 16px; padding: 4px 10px; font-size: 11px; font-weight: 800; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 0.2s ease; white-space: nowrap;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line>
              </svg>
              <span>Enable Delete Entries</span>
            </button>`;

        const isSupportEnabled = comp.support_enabled === true;
        const supportBadge = isSupportEnabled
          ? `<button type="button" class="btn-toggle-support btn-support-enabled" data-id="${comp.id}" data-name="${escapeHtml(comp.company_name)}" data-state="true" title="Support: Enabled (Click to Disable)" style="background-color: #fee2e2; color: #b91c1c; border: 1.5px solid #fca5a5; border-radius: 16px; padding: 4px 12px; font-size: 11px; font-weight: 800; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 0.2s ease; white-space: nowrap;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"></line>
              </svg>
              <span>Disable</span>
            </button>`
          : `<button type="button" class="btn-toggle-support btn-support-disabled" data-id="${comp.id}" data-name="${escapeHtml(comp.company_name)}" data-state="false" title="Support: Disabled (Click to Enable)" style="background-color: #e8f5e9; color: #166534; border: 1.5px solid #86efac; border-radius: 16px; padding: 4px 12px; font-size: 11px; font-weight: 800; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 0.2s ease; white-space: nowrap;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
              <span>Enable</span>
            </button>`;

        const formattedDate = formatDisplayDate(comp.registered_date);
        const regDateDisplay = formattedDate && formattedDate !== '-'
          ? `<span style="display: inline-block; background-color: #f1f5f9; color: #334155; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; white-space: nowrap;">${escapeHtml(formattedDate)}</span>`
          : `<span style="color: #94a3b8; font-size: 11px;">-</span>`;

        const row = document.createElement('tr');
        row.innerHTML = `
          <td style="font-weight: 700; color: #64748b; text-align: center; white-space: nowrap;">${slNo}</td>
          <td class="col-wrap" style="min-width: 170px; max-width: 280px; white-space: normal !important; word-break: break-word !important; overflow-wrap: break-word !important;">
            <div style="font-weight: 800; color: #0f172a; font-size: 12.5px; line-height: 1.35; word-break: break-word;">${escapeHtml(comp.company_name)}</div>
            <div style="font-size: 10.5px; color: #64748b; font-family: monospace; margin-top: 2px; white-space: nowrap;">ID: ${comp.id}</div>
          </td>
          <td style="white-space: nowrap; text-align: center;">${regDateDisplay}</td>
          <td style="white-space: nowrap;"><code style="background-color: #f1f5f9; padding: 3px 6px; border-radius: 4px; font-size: 11px; color: #334155; font-weight: 600;">${escapeHtml(comp.gstin || '-')}</code></td>
          <td style="white-space: nowrap;">
            <a href="mailto:${escapeHtml(comp.email)}" style="color: #2563eb; text-decoration: none; font-weight: 700;">
              ${escapeHtml(comp.email)}
            </a>
          </td>
          <td style="white-space: nowrap; font-weight: 600; color: #334155;">${escapeHtml(comp.phone || '-')}</td>
          <td style="white-space: nowrap;">
            <div style="font-size: 11px; color: #334155; font-weight: 600;">
              ${hasCoords ? `📍 ${lat}, ${lng} <span style="display: block; font-size: 10px; color: #0284c7; font-weight: 700; margin-top: 2px;">⭕ ${comp.geofence_radius || 200}m radius</span>` : `<span style="color: #94a3b8; font-size: 11px;">-</span>`}
            </div>
          </td>
          <td style="text-align: center; white-space: nowrap;">
            <span style="font-weight: 700; color: #0f172a; font-size: 11.5px; background-color: #f8fafc; border: 1px solid #e2e8f0; padding: 3px 8px; border-radius: 6px; display: inline-block;">
              ${escapeHtml(comp.shift_hours || '08:00')}
            </span>
          </td>
          <td style="text-align: center; white-space: nowrap;">
            <span style="display: inline-block; background-color: #e2e8f0; color: #1e293b; padding: 3px 8px; border-radius: 12px; font-weight: 800; font-size: 11px;">
              ${comp.employee_count || 0}/${comp.employee_limit || 50}
            </span>
          </td>
          <td style="text-align: center; white-space: nowrap;">${statusBadge}</td>
          <td style="text-align: center; white-space: nowrap;">${autoReportsBadge}</td>
          <td style="text-align: center; white-space: nowrap;">${deleteEntriesBadge}</td>
          <td style="text-align: center; white-space: nowrap;">${supportBadge}</td>
          <td style="text-align: center; white-space: nowrap;">
            <div class="table-actions">
              <button class="btn-action-icon btn-action-view" data-id="${comp.id}" title="View Company Details">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                  <circle cx="12" cy="12" r="3"></circle>
                </svg>
              </button>
              <button class="btn-action-icon btn-action-edit" data-id="${comp.id}" title="Edit Company">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
              </button>
              <button class="btn-action-icon btn-action-delete" data-id="${comp.id}" data-name="${escapeHtml(comp.company_name)}" title="Delete Company">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </div>
          </td>
        `;
        companyTableBody.appendChild(row);
      });

      // Update footer info
      const startEntry = startIndex + 1;
      const endEntry = Math.min(startIndex + data.companies.length, data.total);
      companyTableInfo.textContent = `Showing ${startEntry} to ${endEntry} of ${data.total} entries`;
      updatePagination(data.page, data.pages);

      // Attach auto reports toggle handlers
      document.querySelectorAll('.btn-toggle-auto-reports').forEach(btn => {
        btn.addEventListener('click', async function () {
          const compId = this.getAttribute('data-id');
          const compName = this.getAttribute('data-name');
          const currentState = this.getAttribute('data-state') === 'true';
          const nextState = !currentState;

          this.disabled = true;
          this.style.opacity = '0.6';

          try {
            const res = await fetch(`/api/companies/${compId}/toggle-auto-reports`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ enabled: nextState })
            });
            const resp = await res.json();
            if (resp.success) {
              loadCompanies(currentPage);
            } else {
              alert(`Error: ${resp.error || 'Failed to update auto reports setting'}`);
              this.disabled = false;
              this.style.opacity = '1';
            }
          } catch (err) {
            alert('Network error while updating auto reports setting.');
            this.disabled = false;
            this.style.opacity = '1';
          }
        });
      });

      // Attach delete entries toggle handlers
      document.querySelectorAll('.btn-toggle-delete-entries').forEach(btn => {
        btn.addEventListener('click', async function () {
          const compId = this.getAttribute('data-id');
          const compName = this.getAttribute('data-name');
          const currentState = this.getAttribute('data-state') === 'true';
          const nextState = !currentState;

          this.disabled = true;
          this.style.opacity = '0.6';

          try {
            const res = await fetch(`/api/companies/${compId}/toggle-delete-entries`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ enabled: nextState })
            });
            const resp = await res.json();
            if (resp.success) {
              loadCompanies(currentPage);
            } else {
              alert(`Error: ${resp.error || 'Failed to update delete entries permission'}`);
              this.disabled = false;
              this.style.opacity = '1';
            }
          } catch (err) {
            alert('Network error while updating delete entries permission.');
            this.disabled = false;
            this.style.opacity = '1';
          }
        });
      });

      // Attach view handlers
      document.querySelectorAll('.btn-action-view').forEach(btn => {
        btn.addEventListener('click', async function () {
          const compId = this.getAttribute('data-id');
          let comp = loadedCompanies.find(c => String(c.id) === String(compId));
          if (!comp) {
            try {
              const res = await fetch(`/api/companies/${compId}`);
              comp = await res.json();
            } catch (err) {
              console.error('Error fetching company details:', err);
            }
          }
          if (!comp) return;

          if (viewCompanyName) viewCompanyName.textContent = comp.company_name || '-';
          if (viewCompanyId) viewCompanyId.textContent = comp.id || '-';
          if (viewCompanyRegisteredDate) viewCompanyRegisteredDate.textContent = comp.registered_date && comp.registered_date !== '-' ? comp.registered_date : 'Not recorded';
          if (viewCompanyGstin) viewCompanyGstin.textContent = comp.gstin || '-';
          if (viewCompanyPhone) viewCompanyPhone.textContent = comp.phone || '-';
          if (viewCompanyEmail) viewCompanyEmail.textContent = comp.email || '-';

          const lat = (comp.latitude !== undefined && comp.latitude !== null && String(comp.latitude).trim() !== '') ? (isNaN(Number(comp.latitude)) ? comp.latitude : Number(comp.latitude).toFixed(5)) : '-';
          const lng = (comp.longitude !== undefined && comp.longitude !== null && String(comp.longitude).trim() !== '') ? (isNaN(Number(comp.longitude)) ? comp.longitude : Number(comp.longitude).toFixed(5)) : '-';
          if (viewCompanyLocation) viewCompanyLocation.textContent = (lat !== '-' && lng !== '-') ? `Lat: ${lat}, Long: ${lng}` : '-';

          if (viewCompanyShiftHours) viewCompanyShiftHours.textContent = comp.shift_hours || '08:00';
          if (viewCompanyEmployees) viewCompanyEmployees.textContent = `${comp.employee_count || 0} enrolled (Limit: ${comp.employee_limit || 50})`;

          if (viewCompanyStatusBadge) {
            const isDeactive = String(comp.status || '').trim().toLowerCase() === 'deactive' || String(comp.status || '').trim().toLowerCase() === 'inactive';
            viewCompanyStatusBadge.innerHTML = !isDeactive
              ? `<span class="status-pill status-active">Active</span>`
              : `<span class="status-pill status-inactive" style="background-color: #fee2e2; color: #b91c1c; border: 1px solid #f87171;">Deactive</span>`;
          }

          if (viewCompanyReportsBadge) {
            viewCompanyReportsBadge.innerHTML = (comp.auto_email_reports !== false)
              ? `<span class="status-pill status-active">Enabled</span>`
              : `<span class="status-pill status-inactive">Disabled</span>`;
          }

          if (viewCompanyDeleteEntriesBadge) {
            viewCompanyDeleteEntriesBadge.innerHTML = (comp.can_delete_entries === true)
              ? `<span class="status-pill status-active">Enabled</span>`
              : `<span class="status-pill status-inactive">Disabled</span>`;
          }

          const viewCompanySupportBadge = document.getElementById('viewCompanySupportBadge');
          if (viewCompanySupportBadge) {
            viewCompanySupportBadge.innerHTML = (comp.support_enabled === true)
              ? `<span class="status-pill status-active" style="background-color: #e8f5e9; color: #166534; border: 1px solid #86efac;">Enabled</span>`
              : `<span class="status-pill status-inactive" style="background-color: #fee2e2; color: #b91c1c; border: 1px solid #f87171;">Disabled</span>`;
          }

          if (viewCompanyModal) {
            viewCompanyModal.classList.add('active');
          }
        });
      });

      // Attach edit handlers
      document.querySelectorAll('.btn-action-edit').forEach(btn => {
        btn.addEventListener('click', function () {
          const compId = this.getAttribute('data-id');
          const comp = loadedCompanies.find(c => String(c.id) === String(compId));
          if (!comp) return;

          editingCompanyId = comp.id;
          companyForm.reset();
          companyFormAlert.style.display = 'none';

          if (companyModalTitle) companyModalTitle.textContent = `Edit Company - ${comp.company_name}`;
          if (btnSaveCompany) btnSaveCompany.textContent = 'Update Company';

          inputCompanyName.value = comp.company_name || '';
          inputGstin.value = comp.gstin || '';
          inputPhone.value = comp.phone || '';
          inputEmail.value = comp.email || '';
          inputLatitude.value = (comp.latitude !== undefined && comp.latitude !== null) ? comp.latitude : '';
          inputLongitude.value = (comp.longitude !== undefined && comp.longitude !== null) ? comp.longitude : '';
          const isDeactive = String(comp.status || '').trim().toLowerCase() === 'deactive' || String(comp.status || '').trim().toLowerCase() === 'inactive';
          inputStatus.value = isDeactive ? 'Deactive' : 'Active';
          if (inputEmployeeLimit) inputEmployeeLimit.value = comp.employee_limit || 50;
          if (inputCompanyShiftHours) inputCompanyShiftHours.value = comp.shift_hours || '08:00';
          if (inputRegisteredDate) inputRegisteredDate.value = formatDateForDateInput(comp.registered_date);
          if (inputAutoEmailReports) inputAutoEmailReports.value = (comp.auto_email_reports !== false) ? 'true' : 'false';
          if (inputCanDeleteEntries) inputCanDeleteEntries.value = (comp.can_delete_entries === true) ? 'true' : 'false';
          if (inputSupportEnabled) inputSupportEnabled.value = (comp.support_enabled === true) ? 'true' : 'false';
          if (inputGeofenceRadius) inputGeofenceRadius.value = comp.geofence_radius || comp.radius_meters || 200;

          companyModal.classList.add('active');
        });
      });

      // Attach delete handlers to open Confirmation Modal
      document.querySelectorAll('.btn-action-delete').forEach(btn => {
        btn.addEventListener('click', function () {
          companyToDeleteId = this.getAttribute('data-id');
          companyToDeleteName = this.getAttribute('data-name');
          if (deleteCompanyTargetName) deleteCompanyTargetName.textContent = companyToDeleteName;
          if (deleteCompanyTargetId) deleteCompanyTargetId.textContent = companyToDeleteId;
          if (btnConfirmDeleteText) btnConfirmDeleteText.textContent = 'Yes, Delete Company & All Records';
          if (btnConfirmDeleteCompany) btnConfirmDeleteCompany.disabled = false;
          if (deleteCompanyModal) deleteCompanyModal.classList.add('active');
        });
      });

      // Attach support toggle handlers
      document.querySelectorAll('.btn-toggle-support').forEach(btn => {
        btn.addEventListener('click', async function (e) {
          e.preventDefault();
          const compId = this.getAttribute('data-id');
          const currentState = this.getAttribute('data-state') === 'true';
          const newState = !currentState;

          this.disabled = true;
          this.style.opacity = '0.6';

          try {
            const res = await fetch(`/api/companies/${compId}/toggle-support`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ enabled: newState })
            });
            const data = await res.json();
            if (data.success) {
              loadCompanies(currentPage);
            } else {
              alert(`Error: ${data.error || 'Failed to update support status.'}`);
              this.disabled = false;
              this.style.opacity = '1';
            }
          } catch (err) {
            alert('Network error while updating support status.');
            this.disabled = false;
            this.style.opacity = '1';
          }
        });
      });

    } catch (err) {
      companyTableBody.innerHTML = `
        <tr>
          <td colspan="10" style="text-align: center; padding: 24px; color: #dc3545;">
            Failed to load companies. Please check database connection.
          </td>
        </tr>
      `;
    }
  }

  function updatePagination(page, totalPages) {
    companyCurrentBtn.textContent = page || 1;
    if (page <= 1) {
      companyPrevBtn.classList.add('disabled');
    } else {
      companyPrevBtn.classList.remove('disabled');
    }
    if (page >= totalPages || totalPages === 0) {
      companyNextBtn.classList.add('disabled');
    } else {
      companyNextBtn.classList.remove('disabled');
    }
  }

  companyPrevBtn.addEventListener('click', function () {
    if (!this.classList.contains('disabled') && currentPage > 1) {
      loadCompanies(currentPage - 1);
    }
  });

  companyNextBtn.addEventListener('click', function () {
    if (!this.classList.contains('disabled')) {
      loadCompanies(currentPage + 1);
    }
  });

  // Limit change
  companyEntriesLimit.addEventListener('change', function () {
    currentLimit = parseInt(this.value, 10);
    loadCompanies(1);
  });

  // Search input debounce
  let searchTimer;
  companyTableSearch.addEventListener('input', function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      currentSearch = companyTableSearch.value.trim();
      loadCompanies(1);
    }, 300);
  });

  // Modal 1: Add Company Modal
  if (btnOpenAddCompanyModal) {
    btnOpenAddCompanyModal.addEventListener('click', function () {
      editingCompanyId = null;
      companyForm.reset();
      companyFormAlert.style.display = 'none';
      if (companyModalTitle) companyModalTitle.textContent = 'Register New Company';
      if (btnSaveCompany) btnSaveCompany.textContent = 'Save Company';
      if (inputEmployeeLimit) inputEmployeeLimit.value = 25;
      if (inputCompanyShiftHours) inputCompanyShiftHours.value = '08:00';
      if (inputRegisteredDate) inputRegisteredDate.value = new Date().toISOString().split('T')[0];
      if (inputStatus) inputStatus.value = 'Active';
      if (inputAutoEmailReports) inputAutoEmailReports.value = 'false';
      if (inputCanDeleteEntries) inputCanDeleteEntries.value = 'false';
      if (inputSupportEnabled) inputSupportEnabled.value = 'false';
      if (inputGeofenceRadius) inputGeofenceRadius.value = 200;
      companyModal.classList.add('active');
    });
  }

  function closeCompanyModalFunc() {
    companyModal.classList.remove('active');
  }

  if (closeCompanyModal) closeCompanyModal.addEventListener('click', closeCompanyModalFunc);
  if (btnCancelCompany) btnCancelCompany.addEventListener('click', closeCompanyModalFunc);

  // Auto Geolocation detection
  if (btnDetectLocation) {
    btnDetectLocation.addEventListener('click', function () {
      if (navigator.geolocation) {
        btnDetectLocation.textContent = '⏳ Detecting...';
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            document.getElementById('inputLatitude').value = pos.coords.latitude.toFixed(6);
            document.getElementById('inputLongitude').value = pos.coords.longitude.toFixed(6);
            btnDetectLocation.textContent = '✓ Location Detected';
            setTimeout(() => { btnDetectLocation.textContent = '📍 Get Current Location'; }, 3000);
          },
          function (err) {
            alert('Could not retrieve current location: ' + err.message);
            btnDetectLocation.textContent = '📍 Get Current Location';
          },
          { enableHighAccuracy: true, timeout: 8000 }
        );
      } else {
        alert('Geolocation is not supported by your browser.');
      }
    });
  }

  // Auto-split combined coordinates if user pastes/types "lat, lng" into latitude field
  if (inputLatitude && inputLongitude) {
    inputLatitude.addEventListener('input', function () {
      const val = this.value;
      if (val && (val.includes(',') || val.includes(';'))) {
        const parts = val.split(/[,;]+/);
        if (parts.length >= 2) {
          this.value = parts[0].trim();
          inputLongitude.value = parts[1].trim();
        }
      }
    });
  }

  // Submit Company Form
  if (companyForm) {
    companyForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      companyFormAlert.style.display = 'none';

      const formData = new FormData(companyForm);
      const payload = {
        company_name: formData.get('company_name'),
        gstin: formData.get('gstin'),
        phone: formData.get('phone'),
        email: formData.get('email'),
        latitude: (formData.get('latitude') !== null && String(formData.get('latitude')).trim() !== '') ? String(formData.get('latitude')).trim() : null,
        longitude: (formData.get('longitude') !== null && String(formData.get('longitude')).trim() !== '') ? String(formData.get('longitude')).trim() : null,
        status: (formData.get('status') === 'Deactive' || formData.get('status') === 'Inactive') ? 'Deactive' : 'Active',
        employee_limit: parseInt(formData.get('employee_limit'), 10) || 50,
        shift_hours: (formData.get('shift_hours') || '08:00').trim(),
        registered_date: formData.get('registered_date') || '',
        auto_email_reports: formData.get('auto_email_reports') === 'true',
        can_delete_entries: formData.get('can_delete_entries') === 'true',
        support_enabled: formData.get('support_enabled') === 'true',
        geofence_radius: parseFloat(formData.get('geofence_radius')) || 200
      };

      const btnSave = btnSaveCompany || document.getElementById('btnSaveCompany');
      try {
        if (btnSave) {
          btnSave.disabled = true;
          btnSave.textContent = editingCompanyId ? 'Updating...' : 'Saving...';
        }

        const url = editingCompanyId ? `/api/companies/${editingCompanyId}` : '/api/companies';
        const method = editingCompanyId ? 'PUT' : 'POST';

        const res = await fetch(url, {
          method: method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const resp = await res.json();
        if (btnSave) {
          btnSave.disabled = false;
          btnSave.textContent = editingCompanyId ? 'Update Company' : 'Save Company';
        }

        if (resp.success) {
          closeCompanyModalFunc();
          loadCompanies(currentPage);
        } else {
          companyFormAlert.textContent = resp.error || 'Failed to save company.';
          companyFormAlert.style.backgroundColor = '#f8d7da';
          companyFormAlert.style.color = '#842029';
          companyFormAlert.style.display = 'block';
        }
      } catch (err) {
        if (btnSave) {
          btnSave.disabled = false;
          btnSave.textContent = editingCompanyId ? 'Update Company' : 'Save Company';
        }
        companyFormAlert.textContent = 'Connection error. Please try again.';
        companyFormAlert.style.backgroundColor = '#f8d7da';
        companyFormAlert.style.color = '#842029';
        companyFormAlert.style.display = 'block';
      }
    });
  }

  // Modal 2: Reports Summary Modal
  if (btnOpenReportsModal) {
    btnOpenReportsModal.addEventListener('click', async function () {
      reportsModal.classList.add('active');
      const breakdownBody = document.getElementById('reportsBreakdownBody');
      breakdownBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 18px;">Loading report summary...</td></tr>';

      try {
        const res = await fetch('/api/companies/reports');
        const data = await res.json();

        if (data.success && data.summary) {
          const s = data.summary;
          document.getElementById('statTotalCompanies').textContent = s.total_companies || 0;
          document.getElementById('statActiveCompanies').textContent = s.active_companies || 0;
          document.getElementById('statTenantEmployees').textContent = s.total_tenant_employees || 0;
          document.getElementById('statArgusEmployees').textContent = s.total_argus_employees || 0;

          if (!s.companies || s.companies.length === 0) {
            breakdownBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 18px; color: #888;">No client companies registered yet.</td></tr>';
          } else {
            breakdownBody.innerHTML = '';
            s.companies.forEach(c => {
              const row = document.createElement('tr');
              const badge = c.status === 'Active'
                ? '<span style="background-color: #d1e7dd; color: #0f5132; padding: 2px 6px; border-radius: 10px; font-size: 10px; font-weight: 700;">Active</span>'
                : '<span style="background-color: #f8d7da; color: #842029; padding: 2px 6px; border-radius: 10px; font-size: 10px; font-weight: 700;">Inactive</span>';

              row.innerHTML = `
                <td style="font-weight: 700;">${escapeHtml(c.company_name)}</td>
                <td>${escapeHtml(c.email)}</td>
                <td style="text-align: center; font-weight: 800;">${c.employee_count}</td>
                <td style="text-align: center;">${badge}</td>
              `;
              breakdownBody.appendChild(row);
            });
          }
        }
      } catch (err) {
        breakdownBody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 18px; color: #dc3545;">Error loading reports summary.</td></tr>';
      }
    });
  }

  function closeReportsModalFunc() {
    if (reportsModal) reportsModal.classList.remove('active');
  }

  if (closeReportsModal) closeReportsModal.addEventListener('click', closeReportsModalFunc);
  if (btnCloseReportsFooter) btnCloseReportsFooter.addEventListener('click', closeReportsModalFunc);

  function closeViewCompanyModalFunc() {
    if (viewCompanyModal) viewCompanyModal.classList.remove('active');
  }

  if (closeViewCompanyModal) closeViewCompanyModal.addEventListener('click', closeViewCompanyModalFunc);
  if (btnCloseViewCompanyFooter) btnCloseViewCompanyFooter.addEventListener('click', closeViewCompanyModalFunc);

  // Modal: Cascade Delete Confirmation Handlers
  function closeDeleteCompanyModalFunc() {
    if (deleteCompanyModal) deleteCompanyModal.classList.remove('active');
    companyToDeleteId = null;
    companyToDeleteName = '';
  }

  if (closeDeleteCompanyModal) closeDeleteCompanyModal.addEventListener('click', closeDeleteCompanyModalFunc);
  if (btnCancelDeleteCompany) btnCancelDeleteCompany.addEventListener('click', closeDeleteCompanyModalFunc);

  if (btnConfirmDeleteCompany) {
    btnConfirmDeleteCompany.addEventListener('click', async function () {
      if (!companyToDeleteId) return;

      btnConfirmDeleteCompany.disabled = true;
      if (btnConfirmDeleteText) btnConfirmDeleteText.textContent = 'Deleting all records...';

      try {
        const res = await fetch(`/api/companies/${companyToDeleteId}`, { method: 'DELETE' });
        const resp = await res.json();
        if (resp.success) {
          closeDeleteCompanyModalFunc();
          loadCompanies(currentPage);
        } else {
          alert(`Error: ${resp.error || 'Failed to delete company'}`);
        }
      } catch (err) {
        alert('Network error while deleting company.');
      } finally {
        if (btnConfirmDeleteCompany) btnConfirmDeleteCompany.disabled = false;
        if (btnConfirmDeleteText) btnConfirmDeleteText.textContent = 'Yes, Delete Company & All Records';
      }
    });
  }

  window.addEventListener('click', function (e) {
    if (e.target === viewCompanyModal) closeViewCompanyModalFunc();
    // companyModal is intentionally NOT closed on backdrop click to prevent losing form data
    if (e.target === reportsModal) closeReportsModalFunc();
    if (e.target === deleteCompanyModal) closeDeleteCompanyModalFunc();
  });

  // Helper escape function
  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  // ================= EXPORTS (COPY, CSV, EXCEL, PDF, PRINT) =================
  const btnCopyCompanies = document.getElementById('btnCopyCompanies');
  const btnCsvCompanies = document.getElementById('btnCsvCompanies');
  const btnExcelCompanies = document.getElementById('btnExcelCompanies');
  const btnPdfCompanies = document.getElementById('btnPdfCompanies');
  const btnPrintCompanies = document.getElementById('btnPrintCompanies');

  if (btnCopyCompanies) {
    btnCopyCompanies.addEventListener('click', function () {
      const table = document.getElementById('companyDataTable');
      if (!table) return;
      let text = '';
      for (let row of table.rows) {
        let rowData = [];
        const cellCount = row.cells.length;
        for (let i = 0; i < Math.max(1, cellCount - 2); i++) {
          rowData.push(row.cells[i].innerText.trim());
        }
        text += rowData.join('\t') + '\n';
      }
      (window.safeCopyToClipboard ? window.safeCopyToClipboard(text) : navigator.clipboard.writeText(text)).then(() => {
        alert('Companies table copied to clipboard!');
      }).catch(err => console.error(err));
    });
  }

  if (btnCsvCompanies) {
    btnCsvCompanies.addEventListener('click', function () {
      window.location.href = `/api/companies/export/csv?search=${encodeURIComponent(currentSearch)}`;
    });
  }

  if (btnExcelCompanies) {
    btnExcelCompanies.addEventListener('click', function () {
      window.location.href = `/api/companies/export/excel?search=${encodeURIComponent(currentSearch)}`;
    });
  }

  if (btnPdfCompanies) {
    btnPdfCompanies.addEventListener('click', function () {
      window.location.href = `/api/companies/export/pdf?search=${encodeURIComponent(currentSearch)}`;
    });
  }

  if (btnPrintCompanies) {
    btnPrintCompanies.addEventListener('click', function () {
      const printContents = document.getElementById('companyDataTable').outerHTML;
      const printWindow = window.open('', '', 'height=600,width=850');
      printWindow.document.write('<html><head><title>Print Companies Directory</title>');
      printWindow.document.write('<style>');
      printWindow.document.write(`
        body { font-family: sans-serif; padding: 20px; }
        h2 { text-align: center; margin-bottom: 20px; font-size: 18px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 11px; }
        th, td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }
        th { background: #2c3e50; color: #fff; }
        th:nth-last-child(1), td:nth-last-child(1), th:nth-last-child(2), td:nth-last-child(2) { display: none; }
      `);
      printWindow.document.write('</style></head><body>');
      printWindow.document.write('<h2>REGISTERED CLIENT COMPANIES</h2>');
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
  loadCompanies(1);
});
