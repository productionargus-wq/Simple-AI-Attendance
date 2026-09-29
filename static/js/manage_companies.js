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
  const inputAutoEmailReports = document.getElementById('inputAutoEmailReports');

  let loadedCompanies = [];
  let editingCompanyId = null;

  // Reports modal elements
  const reportsModal = document.getElementById('reportsModal');
  const btnOpenReportsModal = document.getElementById('btnOpenReportsModal');
  const closeReportsModal = document.getElementById('closeReportsModal');
  const btnCloseReportsFooter = document.getElementById('btnCloseReportsFooter');

  // Fetch and display companies
  async function loadCompanies(page = 1) {
    currentPage = page;
    companyTableBody.innerHTML = `
      <tr>
        <td colspan="10" style="text-align: center; padding: 24px; color: #6c757d;">Loading companies...</td>
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
            <td colspan="10" style="text-align: center; padding: 28px; color: #6c757d;">
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
        const lat = comp.latitude ? Number(comp.latitude).toFixed(5) : '11.02980';
        const lng = comp.longitude ? Number(comp.longitude).toFixed(5) : '76.97400';
        const statusBadge = comp.status === 'Active'
          ? `<span style="background-color: #d1e7dd; color: #0f5132; padding: 3px 8px; border-radius: 12px; font-weight: 700; font-size: 11px;">Active</span>`
          : `<span style="background-color: #f8d7da; color: #842029; padding: 3px 8px; border-radius: 12px; font-weight: 700; font-size: 11px;">Inactive</span>`;

        const isAutoReports = comp.auto_email_reports !== false;
        const autoReportsBadge = isAutoReports
          ? `<button type="button" class="btn-toggle-auto-reports btn-reports-enabled" data-id="${comp.id}" data-name="${escapeHtml(comp.company_name)}" data-state="true" title="Auto Email Reports: ENABLED (Click to turn off)" style="background-color: #e8f5e9; color: #2e7d32; border: 1.5px solid #a5d6a7; border-radius: 16px; padding: 4px 10px; font-size: 11px; font-weight: 800; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 0.2s ease;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                <polyline points="22,6 12,13 2,6"></polyline>
              </svg>
              <span>ON</span>
            </button>`
          : `<button type="button" class="btn-toggle-auto-reports btn-reports-disabled" data-id="${comp.id}" data-name="${escapeHtml(comp.company_name)}" data-state="false" title="Auto Email Reports: DISABLED (Click to turn on)" style="background-color: #f1f5f9; color: #64748b; border: 1.5px solid #cbd5e1; border-radius: 16px; padding: 4px 10px; font-size: 11px; font-weight: 800; cursor: pointer; display: inline-flex; align-items: center; gap: 5px; transition: all 0.2s ease; opacity: 0.85;">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"></path>
                <line x1="2" y1="2" x2="22" y2="22"></line>
              </svg>
              <span>OFF</span>
            </button>`;

        const row = document.createElement('tr');
        row.innerHTML = `
          <td style="font-weight: 700; color: #555;">${slNo}</td>
          <td>
            <div style="font-weight: 800; color: #2c3e50;">${escapeHtml(comp.company_name)}</div>
            <div style="font-size: 10px; color: #888;">ID: ${comp.id}</div>
          </td>
          <td><code style="background-color: #f1f5f9; padding: 2px 6px; border-radius: 3px; font-size: 11px;">${escapeHtml(comp.gstin || '-')}</code></td>
          <td>
            <a href="mailto:${escapeHtml(comp.email)}" style="color: #007bff; text-decoration: none; font-weight: 700;">
              ${escapeHtml(comp.email)}
            </a>
          </td>
          <td>${escapeHtml(comp.phone || '-')}</td>
          <td>
            <div style="font-size: 11px; color: #3d6078; font-weight: 600;">📍 ${lat}, ${lng}</div>
          </td>
          <td style="text-align: center;">
            <span style="display: inline-block; background-color: #e2e8f0; color: #1e293b; padding: 4px 12px; border-radius: 12px; font-weight: 800; font-size: 11px;">
              ${comp.employee_limit || 50}
            </span>
          </td>
          <td style="text-align: center;">${statusBadge}</td>
          <td style="text-align: center;">${autoReportsBadge}</td>
          <td style="text-align: center;">
            <div style="display: flex; gap: 6px; justify-content: center; align-items: center;">
              <button class="btn-action btn-action-edit" data-id="${comp.id}" title="Edit Company" style="background-color: #e0f2fe; color: #0284c7; border: 1px solid #bae6fd; border-radius: 4px; padding: 5px 8px; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; transition: all 0.15s ease;">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
              </button>
              <button class="btn-action btn-action-delete" data-id="${comp.id}" data-name="${escapeHtml(comp.company_name)}" title="Delete Company">
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
          inputLatitude.value = comp.latitude || 11.02980;
          inputLongitude.value = comp.longitude || 76.97400;
          inputStatus.value = comp.status || 'Active';
          if (inputEmployeeLimit) inputEmployeeLimit.value = comp.employee_limit || 50;
          if (inputAutoEmailReports) inputAutoEmailReports.value = (comp.auto_email_reports !== false) ? 'true' : 'false';

          companyModal.classList.add('active');
        });
      });

      // Attach delete handlers
      document.querySelectorAll('.btn-action-delete').forEach(btn => {
        btn.addEventListener('click', async function () {
          const compId = this.getAttribute('data-id');
          const compName = this.getAttribute('data-name');
          if (confirm(`Are you sure you want to delete company "${compName}"?\nThis will remove company access.`)) {
            try {
              const res = await fetch(`/api/companies/${compId}`, { method: 'DELETE' });
              const resp = await res.json();
              if (resp.success) {
                loadCompanies(currentPage);
              } else {
                alert(`Error: ${resp.error || 'Failed to delete company'}`);
              }
            } catch (err) {
              alert('Network error while deleting company.');
            }
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
      if (inputAutoEmailReports) inputAutoEmailReports.value = 'true';
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
        latitude: parseFloat(formData.get('latitude')) || 11.02980,
        longitude: parseFloat(formData.get('longitude')) || 76.97400,
        status: formData.get('status') || 'Active',
        employee_limit: parseInt(formData.get('employee_limit'), 10) || 50,
        auto_email_reports: formData.get('auto_email_reports') === 'true'
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
    reportsModal.classList.remove('active');
  }

  if (closeReportsModal) closeReportsModal.addEventListener('click', closeReportsModalFunc);
  if (btnCloseReportsFooter) btnCloseReportsFooter.addEventListener('click', closeReportsModalFunc);

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

  // Initial load
  loadCompanies(1);
});
