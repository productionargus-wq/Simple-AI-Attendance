/**
 * Argus Attendance Intelligence - Support Tickets Admin Module
 * Handles ticket listings, multi-tenant company filtering, status tab filtering,
 * search, pagination, tabular exports (Copy, CSV, Excel, PDF, Print), quick modal updates,
 * quick resolutions, and full ticket conversation details view.
 */

(function () {
  'use strict';

  // Global Admin State
  let admStatusTab = 'all';
  let admSelectedCompany = '';
  let admSelectedStatus = '';
  let admSearchQuery = '';
  let admPage = 1;
  let admLimit = 10;
  let admSearchTimeout = null;
  let currentAdminActiveTicket = null;
  let admReplyFiles = [];

  // Expose state getters/setters for debugging if needed
  window.getAdmState = function () {
    return { admStatusTab, admSelectedCompany, admSelectedStatus, admSearchQuery, admPage, admLimit };
  };

  // Helper escape
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function escapeAttr(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getStatusBadgeClass(status) {
    const s = (status || '').toLowerCase().trim();
    if (s === 'open') return 'status-open';
    if (s === 'in progress') return 'status-inprogress';
    if (s === 'resolved') return 'status-resolved';
    if (s === 'closed') return 'status-closed';
    return 'status-open';
  }

  // --------------------------------------------------------------------------
  // STATUS TABS & COMPANY FILTERS
  // --------------------------------------------------------------------------
  function filterAdminByStatusTab(status, btnElement) {
    admStatusTab = status || 'all';
    admSelectedStatus = (status === 'all') ? '' : status;

    // Synchronize the dropdown filter if present
    const statusSelect = document.getElementById('admFilterStatus');
    if (statusSelect) {
      statusSelect.value = (status === 'all') ? '' : status;
    }

    // Update active tab buttons UI
    document.querySelectorAll('.status-tab-btn').forEach(b => {
      const bStatus = b.getAttribute('data-status');
      if (bStatus === admStatusTab) {
        b.classList.add('active');
      } else {
        b.classList.remove('active');
      }
    });

    admPage = 1;
    fetchAdminTickets();
  }

  function handleAdminFilterChange() {
    const compEl = document.getElementById('sysadminCompanyFilterSupport') || document.getElementById('admFilterCompany');
    admSelectedCompany = compEl ? compEl.value : '';

    const statusEl = document.getElementById('admFilterStatus');
    admSelectedStatus = statusEl ? statusEl.value : '';
    admStatusTab = admSelectedStatus || 'all';

    // Synchronize status tabs UI
    document.querySelectorAll('.status-tab-btn').forEach(b => {
      const bStatus = b.getAttribute('data-status');
      if (bStatus === admStatusTab) {
        b.classList.add('active');
      } else {
        b.classList.remove('active');
      }
    });

    admPage = 1;
    fetchAdminTickets();
  }

  function handleAdminCompanyFilter(val) {
    const compEl = document.getElementById('sysadminCompanyFilterSupport');
    if (compEl && val !== undefined) {
      compEl.value = val;
    }
    handleAdminFilterChange();
  }

  function changeAdminEntriesLimit(newLimit) {
    admLimit = parseInt(newLimit, 10) || 10;
    admPage = 1;
    fetchAdminTickets();
  }

  function handleAdminSearchDebounce() {
    clearTimeout(admSearchTimeout);
    admSearchTimeout = setTimeout(() => {
      const input = document.getElementById('admSearchInput');
      admSearchQuery = input ? input.value.trim() : '';
      admPage = 1;
      fetchAdminTickets();
    }, 300);
  }

  // --------------------------------------------------------------------------
  // FETCH & RENDER TICKETS
  // --------------------------------------------------------------------------
  async function fetchAdminTickets() {
    const tbody = document.getElementById('adminTicketsTableBody');
    if (!tbody) return;

    tbody.innerHTML = `<tr><td colspan="10" class="loading-empty-state"><div class="spinner-inline"></div>Loading tickets...</td></tr>`;

    try {
      const effStatus = admSelectedStatus || (admStatusTab !== 'all' ? admStatusTab : '');
      const params = new URLSearchParams({
        company_id: admSelectedCompany,
        status: effStatus || 'all',
        search: admSearchQuery,
        page: admPage,
        limit: admLimit
      });

      const res = await fetch(`/api/admin/support/tickets?${params.toString()}`);
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = await res.json();

      if (!data.success) {
        tbody.innerHTML = `<tr><td colspan="10" class="loading-empty-state" style="color: #ef4444;">Failed to load tickets: ${escapeHtml(data.error || 'Server error')}</td></tr>`;
        return;
      }

      // Update Counts Badges on Status Tabs
      const counts = data.counts || {};
      const elAll = document.getElementById('admCntAll');
      const elOpen = document.getElementById('admCntOpen');
      const elProg = document.getElementById('admCntProgress');
      const elRes = document.getElementById('admCntResolved');
      const elClosed = document.getElementById('admCntClosed');

      if (elAll) elAll.innerText = counts.all || 0;
      if (elOpen) elOpen.innerText = counts.open || 0;
      if (elProg) elProg.innerText = counts.in_progress || 0;
      if (elRes) elRes.innerText = counts.resolved || 0;
      if (elClosed) elClosed.innerText = counts.closed || 0;

      const tickets = data.tickets || [];
      if (tickets.length === 0) {
        tbody.innerHTML = `<tr><td colspan="10" class="loading-empty-state">No support tickets found matching criteria.</td></tr>`;
        const info = document.getElementById('admPaginationInfo');
        if (info) info.innerText = 'Showing 0 to 0 of 0 entries';
        const controls = document.getElementById('admPaginationControls');
        if (controls) controls.innerHTML = '';
        return;
      }

      tbody.innerHTML = '';
      tickets.forEach((t, idx) => {
        const rowIdx = (admPage - 1) * admLimit + (idx + 1);
        const statusClass = getStatusBadgeClass(t.status);
        const attCount = (t.attachments && t.attachments.length) || 0;

        const safeTicketId = escapeAttr(t.ticket_id);
        const safeStatus = escapeAttr(t.status || 'Open');

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-weight: 600; color: #64748b;">${rowIdx}</td>
          <td style="font-weight: 700; color: #0284c7; cursor: pointer;" onclick="viewAdminTicketDetails('${safeTicketId}')">
            ${escapeHtml(t.ticket_id)}
          </td>
          <td style="font-weight: 500;">${escapeHtml(t.date_time_str || '')}</td>
          <td style="font-weight: 700; color: #1e293b;">${escapeHtml(t.company_name || 'ARGUS CNC™')}</td>
          <td style="font-weight: 600;">${escapeHtml(t.subject || '')}</td>
          <td>
            <div class="table-desc-preview" title="${escapeHtml(t.description || '')}">
              ${escapeHtml(t.description || '')}
            </div>
          </td>
          <td>
            <span class="status-pill ${statusClass}">${escapeHtml(t.status || 'Open')}</span>
          </td>
          <td>
            <span class="attachment-count-cell">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>
              ${attCount}
            </span>
          </td>
          <td style="font-size: 12px; color: #475569;">${escapeHtml(t.raised_by || 'Admin')}</td>
          <td style="text-align: center;">
            <div class="adm-actions-group">
              <button type="button" class="btn-adm-action btn-adm-view" onclick="viewAdminTicketDetails('${safeTicketId}')" title="View Ticket">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                View
              </button>
              <button type="button" class="btn-adm-action btn-adm-update" onclick="openQuickStatusModal('${safeTicketId}', '${safeStatus}')" title="Update Status">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                Update
              </button>
              <button type="button" class="btn-adm-action btn-adm-resolve" onclick="quickResolveTicket('${safeTicketId}')" title="Quick Resolve">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
                Resolve
              </button>
            </div>
          </td>
        `;
        tbody.appendChild(tr);
      });

      renderAdminPagination(data.total, data.page, data.limit);

    } catch (err) {
      console.error('Error fetching admin tickets:', err);
      tbody.innerHTML = `<tr><td colspan="10" class="loading-empty-state" style="color: #ef4444;">Error fetching support tickets.</td></tr>`;
    }
  }

  function renderAdminPagination(total, page, limit) {
    const totalEntries = total || 0;
    const start = totalEntries === 0 ? 0 : (page - 1) * limit + 1;
    const end = Math.min(page * limit, totalEntries);
    const info = document.getElementById('admPaginationInfo');
    if (info) {
      info.innerText = `Showing ${start} to ${end} of ${totalEntries} entries`;
    }

    const totalPages = Math.ceil(totalEntries / limit);
    const controls = document.getElementById('admPaginationControls');
    if (!controls) return;
    controls.innerHTML = '';

    if (totalPages <= 1) return;

    for (let i = 1; i <= totalPages; i++) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = `page-btn ${i === page ? 'active' : ''}`;
      btn.innerText = i;
      btn.onclick = () => {
        admPage = i;
        fetchAdminTickets();
      };
      controls.appendChild(btn);
    }
  }

  // --------------------------------------------------------------------------
  // ADMIN TICKET DETAILS VIEW
  // --------------------------------------------------------------------------
  async function viewAdminTicketDetails(ticketId) {
    try {
      const res = await fetch(`/api/support/ticket/${encodeURIComponent(ticketId)}`);
      const data = await res.json();
      if (!data.success || !data.ticket) {
        alert(data.error || 'Could not retrieve ticket details.');
        return;
      }

      currentAdminActiveTicket = data.ticket;
      populateAdminDetailsView(data.ticket);

      // Switch panels
      const listView = document.getElementById('adminTicketsListView');
      const detailsView = document.getElementById('adminTicketDetailsView');
      if (listView) listView.style.display = 'none';
      if (detailsView) detailsView.style.display = 'block';

      window.scrollTo({ top: 0, behavior: 'smooth' });

    } catch (err) {
      console.error('Error opening admin ticket details:', err);
      alert('Failed to load ticket details.');
    }
  }

  function backToAdminTicketsList() {
    const listView = document.getElementById('adminTicketsListView');
    const detailsView = document.getElementById('adminTicketDetailsView');
    if (detailsView) detailsView.style.display = 'none';
    if (listView) listView.style.display = 'block';

    currentAdminActiveTicket = null;
    fetchAdminTickets();
    updateSidebarAdminSupportBadge();
  }

  function populateAdminDetailsView(t) {
    const elId = document.getElementById('admDTicketId');
    const elComp = document.getElementById('admDCompanyName');
    const elRaised = document.getElementById('admDRaisedBy');
    const elDt = document.getElementById('admDDateTime');
    const elSub = document.getElementById('admDSubject');
    const elDesc = document.getElementById('admDDescription');

    if (elId) elId.innerText = t.ticket_id || '';
    if (elComp) elComp.innerText = t.company_name || 'ARGUS CNC™';
    if (elRaised) elRaised.innerText = t.raised_by || 'Admin';
    if (elDt) elDt.innerText = t.date_time_str || '';
    if (elSub) elSub.innerText = t.subject || '';
    if (elDesc) elDesc.innerText = t.description || '';

    // Status Badge and Select Dropdown
    const stBadge = document.getElementById('admDStatusBadge');
    if (stBadge) {
      stBadge.innerText = t.status || 'Open';
      stBadge.className = `status-pill ${getStatusBadgeClass(t.status)}`;
    }
    const stSelect = document.getElementById('admDetailStatusSelect');
    if (stSelect) {
      stSelect.value = t.status || 'Open';
    }

    // Attachments List
    const attList = document.getElementById('admDAttachmentsList');
    const btnDownloadAll = document.getElementById('admBtnDownloadAll');
    if (attList) {
      attList.innerHTML = '';
      const attachments = t.attachments || [];

      if (attachments.length === 0) {
        attList.innerHTML = '<div style="font-size: 12px; color: #94a3b8; padding: 4px 0;">No attachments provided.</div>';
        if (btnDownloadAll) btnDownloadAll.style.display = 'none';
      } else {
        if (btnDownloadAll) btnDownloadAll.style.display = 'inline-flex';
        attachments.forEach(att => {
          const card = document.createElement('div');
          card.className = 'attachment-row-card';
          const origName = att.original_name || att.filename || 'File';
          const fileUrl = `/api/support/attachment/${encodeURIComponent(t.ticket_id)}/${encodeURIComponent(att.filename || origName)}`;
          card.innerHTML = `
            <div class="att-row-left">
              <div class="att-file-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
              </div>
              <div>
                <div class="att-name" title="${escapeHtml(origName)}">${escapeHtml(origName)}</div>
                <div class="att-size">${escapeHtml(att.file_size_display || '')}</div>
              </div>
            </div>
            <div class="att-row-actions">
              <a href="${fileUrl}" target="_blank" class="btn-att-action">View</a>
              <a href="${fileUrl}?download=1" class="btn-att-action">Download</a>
            </div>
          `;
          attList.appendChild(card);
        });
      }
    }

    // Conversation Thread
    const thread = document.getElementById('admDConversationThread');
    if (thread) {
      thread.innerHTML = '';
      const messages = t.messages || [];

      messages.forEach(msg => {
        const isSuper = msg.sender_role === 'super_admin';
        const avatarBg = msg.avatar_bg || (isSuper ? '#8b5cf6' : '#ef4444');
        const avatarLetter = msg.sender_avatar || (isSuper ? 'S' : 'A');

        const msgItem = document.createElement('div');
        msgItem.className = 'thread-msg-item';

        let eventPill = '';
        if (msg.badge) {
          eventPill = `<span class="thread-badge-event ${getStatusBadgeClass(msg.badge)}">${escapeHtml(msg.badge)}</span>`;
        }

        let attChipsHtml = '';
        if (msg.attachments && msg.attachments.length > 0) {
          attChipsHtml = '<div class="thread-msg-att-chips">';
          msg.attachments.forEach(att => {
            const aName = att.original_name || att.filename || 'Attachment';
            const aUrl = `/api/support/attachment/${encodeURIComponent(t.ticket_id)}/${encodeURIComponent(att.filename || aName)}`;
            attChipsHtml += `<a href="${aUrl}" target="_blank" class="thread-att-chip">📎 ${escapeHtml(aName)}</a>`;
          });
          attChipsHtml += '</div>';
        }

        msgItem.innerHTML = `
          <div class="thread-avatar" style="background: ${avatarBg};">${escapeHtml(avatarLetter)}</div>
          <div class="thread-content">
            <div class="thread-content-header">
              <div>
                <span class="thread-sender-name">${escapeHtml(msg.sender_name || 'Admin')}</span>
                ${eventPill}
              </div>
              <span class="thread-time">${escapeHtml(msg.created_at_display || '')}</span>
            </div>
            <p class="thread-msg-text">${escapeHtml(msg.message || '')}</p>
            ${attChipsHtml}
          </div>
        `;
        thread.appendChild(msgItem);
      });

      setTimeout(() => {
        thread.scrollTop = thread.scrollHeight;
      }, 50);
    }

    // Update Box State depending on Resolved or Open
    const isResolved = (t.status || '').toLowerCase() === 'resolved';
    const isClosed = (t.status || '').toLowerCase() === 'closed';
    const textarea = document.getElementById('admUpdateMessageText');
    const btnSend = document.getElementById('admBtnSendUpdate');
    const btnAttach = document.getElementById('admBtnAttach');
    const btnReopen = document.getElementById('admBtnReopenTicket');
    const btnResolve = document.getElementById('admBtnResolveTicket');
    const badgeResolved = document.getElementById('admBadgeResolved');

    if (isResolved || isClosed) {
      if (textarea) {
        textarea.value = '';
        textarea.placeholder = `Ticket is ${isResolved ? 'resolved' : 'closed'}. You can reopen if needed.`;
        textarea.disabled = true;
      }
      if (btnSend) btnSend.disabled = true;
      if (btnAttach) btnAttach.disabled = true;
      if (btnReopen) btnReopen.style.display = 'inline-flex';
      if (btnResolve) btnResolve.style.display = 'none';
      if (badgeResolved) badgeResolved.style.display = 'inline-flex';
    } else {
      if (textarea) {
        textarea.disabled = false;
        textarea.placeholder = 'Type your message here...';
      }
      if (btnSend) btnSend.disabled = false;
      if (btnAttach) btnAttach.disabled = false;
      if (btnReopen) btnReopen.style.display = 'none';
      if (btnResolve) btnResolve.style.display = 'inline-flex';
      if (badgeResolved) badgeResolved.style.display = 'none';
    }
  }

  function handleAdminReplyFilesSelect(input) {
    if (!input || !input.files) return;
    const files = Array.from(input.files);
    for (const f of files) {
      if (f.size > 10 * 1024 * 1024) {
        alert(`File "${f.name}" exceeds 10 MB limit.`);
        continue;
      }
      admReplyFiles.push(f);
    }
    const chips = document.getElementById('admUpdateFilesChips');
    if (chips) {
      chips.innerText = admReplyFiles.length > 0 ? `${admReplyFiles.length} file(s) attached` : '';
    }
    input.value = '';
  }

  async function submitAdminTicketUpdate(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (!currentAdminActiveTicket) return;

    const btn = document.getElementById('admBtnSendUpdate');
    if (btn && btn._isSubmitting) return;

    const textarea = document.getElementById('admUpdateMessageText');
    const msg = textarea ? textarea.value.trim() : '';
    if (!msg) {
      alert('Please enter your update message.');
      return;
    }

    if (btn) {
      btn._isSubmitting = true;
      btn.disabled = true;
      btn.classList.add('btn-is-submitting');
    }

    if (window.showSavingPopup) {
      window.showSavingPopup('Sending Admin Update...', 'Posting resolution message to ticket discussion...');
    }

    const formData = new FormData();
    formData.append('message', msg);
    admReplyFiles.forEach(f => formData.append('attachments', f));

    try {
      const res = await fetch(`/api/support/ticket/${encodeURIComponent(currentAdminActiveTicket.ticket_id)}/reply`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (window.hideSavingPopup) window.hideSavingPopup();
      if (data.success) {
        if (textarea) textarea.value = '';
        admReplyFiles = [];
        const chips = document.getElementById('admUpdateFilesChips');
        if (chips) chips.innerText = '';
        currentAdminActiveTicket = data.ticket;
        populateAdminDetailsView(data.ticket);
      } else {
        alert(data.error || 'Failed to post update.');
      }
    } catch (err) {
      if (window.hideSavingPopup) window.hideSavingPopup();
      console.error('Error posting admin update:', err);
      alert('Network error while posting update.');
    } finally {
      if (btn) {
        btn._isSubmitting = false;
        btn.disabled = false;
        btn.classList.remove('btn-is-submitting');
      }
      if (window.hideSavingPopup) window.hideSavingPopup();
    }
  }

  async function updateTicketStatusFromSelect(newStatus) {
    if (!currentAdminActiveTicket) return;
    try {
      const res = await fetch(`/api/admin/support/ticket/${encodeURIComponent(currentAdminActiveTicket.ticket_id)}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus, remark: `Status updated to ${newStatus} by Super Admin.` })
      });
      const data = await res.json();
      if (data.success) {
        currentAdminActiveTicket = data.ticket;
        populateAdminDetailsView(data.ticket);
        updateSidebarAdminSupportBadge();
      } else {
        alert(data.error || 'Failed to update status.');
      }
    } catch (err) {
      console.error('Error updating status:', err);
    }
  }

  async function resolveAdminTicket() {
    if (!currentAdminActiveTicket) return;
    if (!confirm(`Are you sure you want to mark Ticket ${currentAdminActiveTicket.ticket_id} as Resolved?`)) return;

    try {
      const res = await fetch(`/api/admin/support/ticket/${encodeURIComponent(currentAdminActiveTicket.ticket_id)}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'Resolved', remark: 'Ticket marked as resolved by Super Admin.' })
      });
      const data = await res.json();
      if (data.success) {
        currentAdminActiveTicket = data.ticket;
        populateAdminDetailsView(data.ticket);
        updateSidebarAdminSupportBadge();
      } else {
        alert(data.error || 'Failed to resolve ticket.');
      }
    } catch (err) {
      console.error('Error resolving admin ticket:', err);
    }
  }

  async function reopenAdminTicket() {
    if (!currentAdminActiveTicket) return;
    if (!confirm(`Do you want to reopen Ticket ${currentAdminActiveTicket.ticket_id}?`)) return;

    try {
      const res = await fetch(`/api/admin/support/ticket/${encodeURIComponent(currentAdminActiveTicket.ticket_id)}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'Open', remark: 'Ticket reopened by Super Admin.' })
      });
      const data = await res.json();
      if (data.success) {
        currentAdminActiveTicket = data.ticket;
        populateAdminDetailsView(data.ticket);
        updateSidebarAdminSupportBadge();
      } else {
        alert(data.error || 'Failed to reopen ticket.');
      }
    } catch (err) {
      console.error('Error reopening admin ticket:', err);
    }
  }

  function downloadAllAdminTicketAttachments() {
    if (!currentAdminActiveTicket) return;
    window.open(`/api/support/attachment/${encodeURIComponent(currentAdminActiveTicket.ticket_id)}/download-all`, '_blank');
  }

  // --------------------------------------------------------------------------
  // QUICK STATUS UPDATE MODAL (TABLE ACTIONS)
  // --------------------------------------------------------------------------
  function openQuickStatusModal(ticketId, currentStatus) {
    const inputId = document.getElementById('quickModalTicketId');
    const selectStatus = document.getElementById('quickModalStatus');
    const remark = document.getElementById('quickModalRemark');
    const modal = document.getElementById('quickStatusModal');

    if (inputId) inputId.value = ticketId;
    if (selectStatus) selectStatus.value = currentStatus || 'Open';
    if (remark) remark.value = '';
    if (modal) modal.style.display = 'flex';
  }

  function closeQuickStatusModal() {
    const modal = document.getElementById('quickStatusModal');
    if (modal) modal.style.display = 'none';
  }

  async function submitQuickStatusUpdate() {
    const modal = document.getElementById('quickStatusModal');
    if (modal && modal._isSubmitting) return;

    const inputId = document.getElementById('quickModalTicketId');
    const selectStatus = document.getElementById('quickModalStatus');
    const remarkEl = document.getElementById('quickModalRemark');

    const ticketId = inputId ? inputId.value.trim() : '';
    const status = selectStatus ? selectStatus.value : 'Open';
    const remark = remarkEl ? remarkEl.value.trim() : '';

    if (!ticketId) {
      alert('Missing ticket identifier.');
      return;
    }

    if (modal) modal._isSubmitting = true;
    if (window.showSavingPopup) {
      window.showSavingPopup('Updating Ticket Status...', 'Saving ticket status changes...');
    }

    try {
      const res = await fetch(`/api/admin/support/ticket/${encodeURIComponent(ticketId)}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: status, remark: remark })
      });
      const data = await res.json();
      if (window.hideSavingPopup) window.hideSavingPopup();
      if (data.success) {
        closeQuickStatusModal();
        fetchAdminTickets();
        updateSidebarAdminSupportBadge();
      } else {
        alert(data.error || 'Failed to update status.');
      }
    } catch (err) {
      if (window.hideSavingPopup) window.hideSavingPopup();
      console.error('Error updating status:', err);
      alert('Failed to update ticket status due to a network error.');
    } finally {
      if (modal) modal._isSubmitting = false;
      if (window.hideSavingPopup) window.hideSavingPopup();
    }
  }

  async function quickResolveTicket(ticketId) {
    if (!confirm(`Are you sure you want to mark Ticket ${ticketId} as Resolved?`)) return;
    try {
      const res = await fetch(`/api/admin/support/ticket/${encodeURIComponent(ticketId)}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'Resolved', remark: 'Ticket resolved directly from dashboard.' })
      });
      const data = await res.json();
      if (data.success) {
        fetchAdminTickets();
        updateSidebarAdminSupportBadge();
      } else {
        alert(data.error || 'Failed to resolve ticket.');
      }
    } catch (err) {
      console.error('Quick resolve error:', err);
      alert('Failed to resolve ticket.');
    }
  }

  // --------------------------------------------------------------------------
  // EXPORT, COPY & PRINT ACTIONS
  // --------------------------------------------------------------------------
  function exportAdminTickets(format) {
    const effStatus = admSelectedStatus || (admStatusTab !== 'all' ? admStatusTab : '');
    const url = `/api/admin/support/export?format=${encodeURIComponent(format)}&company_id=${encodeURIComponent(admSelectedCompany)}&status=${encodeURIComponent(effStatus)}&search=${encodeURIComponent(admSearchQuery)}`;
    window.open(url, '_blank');
  }

  function fallbackCopyText(text) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand('copy');
      alert('Support tickets table copied to clipboard!');
    } catch (e) {
      alert('Failed to copy table to clipboard.');
    }
    document.body.removeChild(ta);
  }

  function copyAdminTicketsTable() {
    const table = document.getElementById('adminTicketsTable');
    if (!table) {
      alert('Table not available.');
      return;
    }
    let text = '';
    for (let row of table.rows) {
      let rowData = [];
      const cellCount = row.cells.length;
      // Skip the last cell if it contains action buttons
      const maxCol = cellCount > 1 ? cellCount - 1 : cellCount;
      for (let i = 0; i < maxCol; i++) {
        rowData.push(row.cells[i].innerText.trim().replace(/\r?\n+/g, ' '));
      }
      text += rowData.join('\t') + '\n';
    }

    if (!text.trim()) {
      alert('No support ticket data to copy.');
      return;
    }

    if (window.safeCopyToClipboard) {
      window.safeCopyToClipboard(text).then(() => {
        alert('Support tickets table copied to clipboard!');
      }).catch(() => fallbackCopyText(text));
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        alert('Support tickets table copied to clipboard!');
      }).catch(() => fallbackCopyText(text));
    } else {
      fallbackCopyText(text);
    }
  }

  function printAdminTicketsTable() {
    const table = document.getElementById('adminTicketsTable');
    if (!table) {
      alert('Table not available.');
      return;
    }

    const printWindow = window.open('', '', 'height=700,width=950');
    if (!printWindow) {
      alert('Please allow popups to print ticket table.');
      return;
    }

    // Clone table to strip out actions column for a clean printout
    const clone = table.cloneNode(true);
    for (let r of clone.rows) {
      if (r.cells.length > 0) {
        r.deleteCell(r.cells.length - 1);
      }
    }

    printWindow.document.write('<!DOCTYPE html><html><head><title>Support Tickets Report</title>');
    printWindow.document.write('<style>');
    printWindow.document.write(`
      body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; padding: 25px; color: #1e293b; }
      h2 { margin: 0 0 6px 0; font-size: 20px; font-weight: 700; color: #0f172a; }
      .meta-info { font-size: 12px; color: #64748b; margin-bottom: 18px; }
      table { width: 100%; border-collapse: collapse; font-size: 11px; margin-top: 10px; }
      th, td { border: 1px solid #cbd5e1; padding: 6px 8px; text-align: left; vertical-align: top; }
      th { background: #f1f5f9; font-weight: 700; color: #0f172a; }
      tr:nth-child(even) { background: #f8fafc; }
      .status-pill { display: inline-block; padding: 2px 6px; border-radius: 4px; font-weight: 600; font-size: 10px; }
      .status-open { background: #fee2e2; color: #ef4444; }
      .status-inprogress { background: #fef3c7; color: #d97706; }
      .status-resolved { background: #dcfce7; color: #16a34a; }
      .status-closed { background: #e2e8f0; color: #64748b; }
      @media print {
        @page { size: landscape; margin: 10mm; }
      }
    `);
    printWindow.document.write('</style></head><body>');
    printWindow.document.write('<h2>ARGUS CNC™ - System Support Tickets</h2>');
    printWindow.document.write('<div class="meta-info">Generated on ' + new Date().toLocaleString() + '</div>');
    printWindow.document.write(clone.outerHTML);
    printWindow.document.write('</body></html>');
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
    }, 300);
  }

  // --------------------------------------------------------------------------
  // SIDEBAR BADGE UPDATE
  // --------------------------------------------------------------------------
  async function updateSidebarAdminSupportBadge() {
    try {
      const res = await fetch('/api/support/badge-count');
      const data = await res.json();
      if (data && data.success) {
        const badge = document.getElementById('sidebarAdminSupportBadge');
        if (badge) {
          if (data.count > 0) {
            badge.innerText = data.count;
            badge.style.display = 'inline-block';
          } else {
            badge.style.display = 'none';
          }
        }
      }
    } catch (e) {
      console.error('Badge update error:', e);
    }
  }

  // --------------------------------------------------------------------------
  // BIND ALL DOM EVENT LISTENERS (DEFENSE-IN-DEPTH)
  // --------------------------------------------------------------------------
  function bindAdminSupportEventListeners() {
    // Status Tabs
    document.querySelectorAll('.status-tab-btn').forEach(btn => {
      btn.onclick = function (e) {
        e.preventDefault();
        const st = this.getAttribute('data-status') || 'all';
        filterAdminByStatusTab(st, this);
      };
    });

    // Company filter
    const compFilter = document.getElementById('sysadminCompanyFilterSupport');
    if (compFilter) {
      compFilter.onchange = handleAdminFilterChange;
    }

    // Status dropdown filter
    const statusFilter = document.getElementById('admFilterStatus');
    if (statusFilter) {
      statusFilter.onchange = handleAdminFilterChange;
    }

    // Entries limit
    const entriesSelect = document.getElementById('admEntriesSelect');
    if (entriesSelect) {
      entriesSelect.onchange = function () {
        changeAdminEntriesLimit(this.value);
      };
    }

    // Search input
    const searchInput = document.getElementById('admSearchInput');
    if (searchInput) {
      searchInput.onkeyup = handleAdminSearchDebounce;
      searchInput.oninput = handleAdminSearchDebounce;
    }

    // Export buttons
    const btnCopy = document.getElementById('btnAdminCopy');
    if (btnCopy) btnCopy.onclick = copyAdminTicketsTable;

    const btnCsv = document.getElementById('btnAdminCsv');
    if (btnCsv) btnCsv.onclick = () => exportAdminTickets('csv');

    const btnExcel = document.getElementById('btnAdminExcel');
    if (btnExcel) btnExcel.onclick = () => exportAdminTickets('excel');

    const btnPdf = document.getElementById('btnAdminPdf');
    if (btnPdf) btnPdf.onclick = () => exportAdminTickets('pdf');

    const btnPrint = document.getElementById('btnAdminPrint');
    if (btnPrint) btnPrint.onclick = printAdminTicketsTable;

    const btnExportTop = document.getElementById('btnAdminExportTop');
    if (btnExportTop) btnExportTop.onclick = () => exportAdminTickets('csv');
  }

  // --------------------------------------------------------------------------
  // ATTACH TO WINDOW GLOBAL SCOPE (ENSURES INLINE ONCLICK ATTRIBUTES NEVER FAIL)
  // --------------------------------------------------------------------------
  window.fetchAdminTickets = fetchAdminTickets;
  window.filterAdminByStatusTab = filterAdminByStatusTab;
  window.handleAdminFilterChange = handleAdminFilterChange;
  window.handleAdminCompanyFilter = handleAdminCompanyFilter;
  window.changeAdminEntriesLimit = changeAdminEntriesLimit;
  window.handleAdminSearchDebounce = handleAdminSearchDebounce;
  window.viewAdminTicketDetails = viewAdminTicketDetails;
  window.backToAdminTicketsList = backToAdminTicketsList;
  window.openQuickStatusModal = openQuickStatusModal;
  window.closeQuickStatusModal = closeQuickStatusModal;
  window.submitQuickStatusUpdate = submitQuickStatusUpdate;
  window.quickResolveTicket = quickResolveTicket;
  window.exportAdminTickets = exportAdminTickets;
  window.copyAdminTicketsTable = copyAdminTicketsTable;
  window.printAdminTicketsTable = printAdminTicketsTable;
  window.submitAdminTicketUpdate = submitAdminTicketUpdate;
  window.updateTicketStatusFromSelect = updateTicketStatusFromSelect;
  window.resolveAdminTicket = resolveAdminTicket;
  window.reopenAdminTicket = reopenAdminTicket;
  window.downloadAllAdminTicketAttachments = downloadAllAdminTicketAttachments;
  window.handleAdminReplyFilesSelect = handleAdminReplyFilesSelect;
  window.getStatusBadgeClass = getStatusBadgeClass;
  window.renderAdminPagination = renderAdminPagination;
  window.populateAdminDetailsView = populateAdminDetailsView;
  window.updateSidebarAdminSupportBadge = updateSidebarAdminSupportBadge;
  window.bindAdminSupportEventListeners = bindAdminSupportEventListeners;
  window.escapeHtml = escapeHtml;

  // Initialize immediately or on ready
  function initAdminSupport() {
    bindAdminSupportEventListeners();
    fetchAdminTickets();
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    initAdminSupport();
  } else {
    document.addEventListener('DOMContentLoaded', initAdminSupport);
  }
  window.addEventListener('page:loaded', initAdminSupport);

})();
