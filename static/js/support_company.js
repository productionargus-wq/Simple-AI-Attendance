/**
 * Argus Attendance Intelligence - Company Support Center Module
 * Handles ticket raising, attachment management, ticket listings & filtering,
 * interactive ticket discussion threads & replies, and high-fidelity video tutorials.
 */

(function () {
  'use strict';

  // Global State
  let currentTab = 'raise';
  let currentStatusFilter = 'all';
  let currentSearchQuery = '';
  let currentPage = 1;
  let currentLimit = 10;
  let selectedTicketFiles = [];
  let replyTicketFiles = [];
  let currentActiveTicket = null;
  let allDemoVideos = [];
  let activeVideoIndex = 0;
  let searchDebounceTimeout = null;

  // Video playback simulation state
  let isSimulatedPlaying = false;
  let simulatedPlaySeconds = 0;
  let simulatedDurationSeconds = 504;
  let simulatedPlayInterval = null;
  let isSimulatedMuted = false;

  // Utility: HTML Escaping
  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function parseDurationToSeconds(durStr) {
    if (!durStr) return 300;
    const parts = durStr.split(':').map(Number);
    if (parts.length === 2) return (parts[0] * 60) + parts[1];
    if (parts.length === 3) return (parts[0] * 3600) + (parts[1] * 60) + parts[2];
    return 300;
  }

  function formatSeconds(secs) {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
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
  // TAB SWITCHER FOR TOP HERO CARDS
  // --------------------------------------------------------------------------
  function switchSupportTab(tabKey) {
    currentTab = tabKey;

    // Highlight hero card
    document.querySelectorAll('.support-hero-card').forEach(c => {
      c.classList.remove('active-hero');
      c.classList.remove('active-videos');
    });
    const heroRaise = document.getElementById('heroCardRaise');
    const heroTickets = document.getElementById('heroCardTickets');
    const heroVideos = document.getElementById('heroCardVideos');

    if (tabKey === 'raise' && heroRaise) heroRaise.classList.add('active-hero');
    if (tabKey === 'tickets' && heroTickets) heroTickets.classList.add('active-hero');
    if (tabKey === 'videos' && heroVideos) heroVideos.classList.add('active-videos');

    // Toggle view panels
    const viewRaise = document.getElementById('viewRaiseTicket');
    const viewTickets = document.getElementById('viewMyTickets');
    const viewVideos = document.getElementById('viewDemoVideos');

    if (viewRaise) viewRaise.style.display = tabKey === 'raise' ? 'block' : 'none';
    if (viewTickets) viewTickets.style.display = tabKey === 'tickets' ? 'block' : 'none';
    if (viewVideos) viewVideos.style.display = tabKey === 'videos' ? 'block' : 'none';

    if (tabKey === 'tickets') {
      fetchTicketsList();
    }
  }

  // --------------------------------------------------------------------------
  // RAISE TICKET FILE HANDLERS
  // --------------------------------------------------------------------------
  function handleTicketFilesSelect(input) {
    if (!input || !input.files) return;
    const files = Array.from(input.files);
    for (const f of files) {
      if (f.size > 10 * 1024 * 1024) {
        alert(`File "${f.name}" exceeds the 10 MB limit.`);
        continue;
      }
      selectedTicketFiles.push(f);
    }
    renderTicketFileChips();
    input.value = '';
  }

  function renderTicketFileChips() {
    const container = document.getElementById('selectedFilesContainer');
    if (!container) return;
    container.innerHTML = '';
    selectedTicketFiles.forEach((f, idx) => {
      const chip = document.createElement('div');
      chip.className = 'file-chip';
      chip.innerHTML = `
        <span>📎 ${escapeHtml(f.name)} (${formatFileSize(f.size)})</span>
        <button type="button" class="file-chip-remove" onclick="removeTicketFile(${idx})">✕</button>
      `;
      container.appendChild(chip);
    });
  }

  function removeTicketFile(idx) {
    selectedTicketFiles.splice(idx, 1);
    renderTicketFileChips();
  }

  // --------------------------------------------------------------------------
  // SUBMIT TICKET
  // --------------------------------------------------------------------------
  async function submitSupportTicket(e) {
    if (e && e.preventDefault) e.preventDefault();
    const subjectEl = document.getElementById('ticketSubject');
    const descEl = document.getElementById('ticketDesc');
    const subject = subjectEl ? subjectEl.value.trim() : '';
    const description = descEl ? descEl.value.trim() : '';

    if (!subject || !description) {
      alert('Please enter both Subject and Description.');
      return;
    }

    const btn = document.getElementById('btnSubmitTicket');
    if (btn && btn._isSubmitting) return;
    if (btn) btn._isSubmitting = true;

    const btnText = document.getElementById('btnSubmitTicketText');
    if (btn) {
      btn.disabled = true;
      btn.classList.add('btn-is-submitting');
    }
    if (btnText) btnText.innerHTML = '<span class="spinner-inline"></span> Submitting...';

    if (window.showSavingPopup) {
      window.showSavingPopup('Submitting Support Ticket...', 'Registering ticket and notifying support team...');
    }

    const formData = new FormData();
    formData.append('subject', subject);
    formData.append('description', description);
    selectedTicketFiles.forEach(f => {
      formData.append('attachments', f);
    });

    try {
      const res = await fetch('/api/support/ticket', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (window.hideSavingPopup) window.hideSavingPopup();
      if (data.success) {
        alert(`Ticket ${data.ticket.ticket_id} submitted successfully! Our support team will review it.`);
        const form = document.getElementById('raiseTicketForm');
        if (form) form.reset();
        selectedTicketFiles = [];
        renderTicketFileChips();
        updateSidebarSupportBadge();
        switchSupportTab('tickets');
      } else {
        alert(data.error || 'Failed to submit ticket. Please try again.');
      }
    } catch (err) {
      if (window.hideSavingPopup) window.hideSavingPopup();
      console.error('Error creating ticket:', err);
      alert('An unexpected network error occurred.');
    } finally {
      if (btn) {
        btn._isSubmitting = false;
        btn.disabled = false;
        btn.classList.remove('btn-is-submitting');
      }
      if (window.hideSavingPopup) window.hideSavingPopup();
      if (btnText) btnText.innerHTML = 'Submit Ticket';
    }
  }

  // --------------------------------------------------------------------------
  // MY TICKETS TABLE & FILTERS
  // --------------------------------------------------------------------------
  function filterTicketsByStatus(status, btnElement) {
    currentStatusFilter = status;
    currentPage = 1;
    document.querySelectorAll('.status-tab-btn').forEach(b => b.classList.remove('active'));
    if (btnElement) btnElement.classList.add('active');
    fetchTicketsList();
  }

  function handleTicketSearchDebounce() {
    clearTimeout(searchDebounceTimeout);
    searchDebounceTimeout = setTimeout(() => {
      const searchInput = document.getElementById('ticketsSearchInput');
      currentSearchQuery = searchInput ? searchInput.value.trim() : '';
      currentPage = 1;
      fetchTicketsList();
    }, 350);
  }

  function refreshSupportTickets() {
    fetchTicketsList();
    updateSidebarSupportBadge();
  }

  async function fetchTicketsList() {
    const tbody = document.getElementById('ticketsTableBody');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="7" class="loading-empty-state"><div class="spinner-inline"></div>Loading tickets...</td></tr>`;

    try {
      const params = new URLSearchParams({
        status: currentStatusFilter,
        search: currentSearchQuery,
        page: currentPage,
        limit: currentLimit
      });

      const res = await fetch(`/api/support/tickets?${params.toString()}`);
      const data = await res.json();

      if (!data.success) {
        tbody.innerHTML = `<tr><td colspan="7" class="loading-empty-state" style="color: #ef4444;">Failed to load tickets.</td></tr>`;
        return;
      }

      // Update Counts Badges
      const counts = data.counts || {};
      const elAll = document.getElementById('cntAll');
      const elOpen = document.getElementById('cntOpen');
      const elProgress = document.getElementById('cntProgress');
      const elResolved = document.getElementById('cntResolved');
      const elClosed = document.getElementById('cntClosed');

      if (elAll) elAll.innerText = counts.all || 0;
      if (elOpen) elOpen.innerText = counts.open || 0;
      if (elProgress) elProgress.innerText = counts.in_progress || 0;
      if (elResolved) elResolved.innerText = counts.resolved || 0;
      if (elClosed) elClosed.innerText = counts.closed || 0;

      // Render Table Rows
      const tickets = data.tickets || [];
      const infoEl = document.getElementById('paginationInfo');
      const ctrlEl = document.getElementById('paginationControls');

      if (tickets.length === 0) {
        tbody.innerHTML = `<tr><td colspan="7" class="loading-empty-state">No support tickets found.</td></tr>`;
        if (infoEl) infoEl.innerText = 'Showing 0 to 0 of 0 entries';
        if (ctrlEl) ctrlEl.innerHTML = '';
        return;
      }

      tbody.innerHTML = '';
      tickets.forEach((t, idx) => {
        const rowIdx = (currentPage - 1) * currentLimit + (idx + 1);
        const statusClass = getStatusBadgeClass(t.status);
        const attCount = (t.attachments && t.attachments.length) || 0;

        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td style="font-weight: 600; color: #64748b;">${rowIdx}</td>
          <td style="font-weight: 500;">${escapeHtml(t.date_time_str || '')}</td>
          <td>
            <div style="font-weight: 700; color: #0284c7; cursor: pointer;" onclick="openTicketModal('${t.ticket_id}')">${escapeHtml(t.subject || '')}</div>
            <div style="font-size: 11px; color: #94a3b8;">${t.ticket_id}</div>
          </td>
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
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path></svg>
              ${attCount}
            </span>
          </td>
          <td style="text-align: center;">
            <button type="button" class="btn-action-view" onclick="openTicketModal('${t.ticket_id}')">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
              View
            </button>
          </td>
        `;
        tbody.appendChild(tr);
      });

      renderPagination(data.total, data.page, data.limit);

    } catch (err) {
      console.error('Error fetching tickets list:', err);
      tbody.innerHTML = `<tr><td colspan="7" class="loading-empty-state" style="color: #ef4444;">Error fetching data.</td></tr>`;
    }
  }

  function renderPagination(total, page, limit) {
    const infoEl = document.getElementById('paginationInfo');
    const controls = document.getElementById('paginationControls');
    if (!infoEl || !controls) return;

    const start = total === 0 ? 0 : (page - 1) * limit + 1;
    const end = Math.min(page * limit, total);
    infoEl.innerText = `Showing ${start} to ${end} of ${total} entries`;

    const totalPages = Math.ceil(total / limit);
    controls.innerHTML = '';

    if (totalPages <= 1) return;

    for (let i = 1; i <= totalPages; i++) {
      const btn = document.createElement('button');
      btn.className = `page-btn ${i === page ? 'active' : ''}`;
      btn.innerText = i;
      btn.onclick = () => {
        currentPage = i;
        fetchTicketsList();
      };
      controls.appendChild(btn);
    }
  }

  // --------------------------------------------------------------------------
  // TICKET DETAILS MODAL LOGIC
  // --------------------------------------------------------------------------
  async function openTicketModal(ticketId) {
    const backdrop = document.getElementById('ticketModalBackdrop');
    if (backdrop) backdrop.style.display = 'flex';
    replyTicketFiles = [];
    renderReplyFileChips();
    const replyInput = document.getElementById('replyMessageText');
    if (replyInput) replyInput.value = '';

    try {
      const res = await fetch(`/api/support/ticket/${ticketId}`);
      const data = await res.json();
      if (!data.success || !data.ticket) {
        alert('Could not retrieve ticket details.');
        closeTicketModal();
        return;
      }

      currentActiveTicket = data.ticket;
      populateTicketModal(data.ticket);

    } catch (err) {
      console.error('Error opening ticket modal:', err);
      alert('Error retrieving ticket details.');
      closeTicketModal();
    }
  }

  function closeTicketModal() {
    const backdrop = document.getElementById('ticketModalBackdrop');
    if (backdrop) backdrop.style.display = 'none';
    currentActiveTicket = null;
  }

  function populateTicketModal(t) {
    const mId = document.getElementById('mTicketId');
    const mComp = document.getElementById('mCompanyName');
    const mRaised = document.getElementById('mRaisedBy');
    const mDate = document.getElementById('mDateTime');
    const mSub = document.getElementById('mSubject');
    const mDesc = document.getElementById('mDescription');

    if (mId) mId.innerText = t.ticket_id;
    if (mComp) mComp.innerText = t.company_name || 'ARGUS CNC™';
    if (mRaised) mRaised.innerText = t.raised_by || 'Admin';
    if (mDate) mDate.innerText = t.date_time_str || '';
    if (mSub) mSub.innerText = t.subject || '';
    if (mDesc) mDesc.innerText = t.description || '';

    // Status Badge
    const stBadge = document.getElementById('mStatusBadge');
    if (stBadge) {
      stBadge.innerText = t.status || 'Open';
      stBadge.className = `status-pill ${getStatusBadgeClass(t.status)}`;
    }

    // Attachments List
    const attList = document.getElementById('mAttachmentsList');
    const btnDlAll = document.getElementById('btnDownloadAll');
    if (attList) {
      attList.innerHTML = '';
      const attachments = t.attachments || [];

      if (attachments.length === 0) {
        attList.innerHTML = '<div style="font-size: 12px; color: #94a3b8; padding: 4px 0;">No attachments provided.</div>';
        if (btnDlAll) btnDlAll.style.display = 'none';
      } else {
        if (btnDlAll) btnDlAll.style.display = 'inline-flex';
        attachments.forEach(att => {
          const card = document.createElement('div');
          card.className = 'attachment-row-card';
          const fileUrl = `/api/support/attachment/${t.ticket_id}/${encodeURIComponent(att.filename)}`;
          card.innerHTML = `
            <div class="att-row-left">
              <div class="att-file-icon">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
              </div>
              <div>
                <div class="att-name" title="${escapeHtml(att.original_name)}">${escapeHtml(att.original_name)}</div>
                <div class="att-size">${att.file_size_display || ''}</div>
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
    const thread = document.getElementById('mConversationThread');
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
            const aUrl = `/api/support/attachment/${t.ticket_id}/${encodeURIComponent(att.filename || att)}`;
            const aName = att.original_name || att.filename || 'Attachment';
            attChipsHtml += `<a href="${aUrl}" target="_blank" class="thread-att-chip">📎 ${escapeHtml(aName)}</a>`;
          });
          attChipsHtml += '</div>';
        }

        msgItem.innerHTML = `
          <div class="thread-avatar" style="background: ${avatarBg};">${avatarLetter}</div>
          <div class="thread-content">
            <div class="thread-content-header">
              <div>
                <span class="thread-sender-name">${escapeHtml(msg.sender_name)}</span>
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

    // Toggle Footer Buttons (Reopen vs Resolve)
    const isResolvedOrClosed = ['resolved', 'closed'].includes((t.status || '').toLowerCase());
    const btnReopen = document.getElementById('btnReopenTicket');
    const btnResolve = document.getElementById('btnResolveTicket');
    if (btnReopen) btnReopen.style.display = isResolvedOrClosed ? 'inline-flex' : 'none';
    if (btnResolve) btnResolve.style.display = isResolvedOrClosed ? 'none' : 'inline-flex';
  }

  function handleReplyFilesSelect(input) {
    if (!input || !input.files) return;
    const files = Array.from(input.files);
    for (const f of files) {
      if (f.size > 10 * 1024 * 1024) {
        alert(`File "${f.name}" exceeds 10 MB limit.`);
        continue;
      }
      replyTicketFiles.push(f);
    }
    renderReplyFileChips();
    input.value = '';
  }

  function renderReplyFileChips() {
    const container = document.getElementById('replyFilesChips');
    if (!container) return;
    container.innerHTML = '';
    if (replyTicketFiles.length > 0) {
      container.innerText = `${replyTicketFiles.length} file(s) selected`;
    }
  }

  async function submitTicketReply(e) {
    if (e && e.preventDefault) e.preventDefault();
    if (!currentActiveTicket) return;

    const btn = document.getElementById('btnSendReply');
    if (btn && btn._isSubmitting) return;

    const msgInput = document.getElementById('replyMessageText');
    const msg = msgInput ? msgInput.value.trim() : '';
    if (!msg) {
      alert('Please enter your reply message.');
      return;
    }

    if (btn) {
      btn._isSubmitting = true;
      btn.disabled = true;
      btn.classList.add('btn-is-submitting');
    }

    if (window.showSavingPopup) {
      window.showSavingPopup('Sending Reply...', 'Posting message update to ticket conversation...');
    }

    const formData = new FormData();
    formData.append('message', msg);
    replyTicketFiles.forEach(f => {
      formData.append('attachments', f);
    });

    try {
      const res = await fetch(`/api/support/ticket/${currentActiveTicket.ticket_id}/reply`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (window.hideSavingPopup) window.hideSavingPopup();
      if (data.success) {
        if (msgInput) msgInput.value = '';
        replyTicketFiles = [];
        renderReplyFileChips();
        currentActiveTicket = data.ticket;
        populateTicketModal(data.ticket);
        fetchTicketsList();
      } else {
        alert(data.error || 'Failed to send reply.');
      }
    } catch (err) {
      if (window.hideSavingPopup) window.hideSavingPopup();
      console.error('Error replying to ticket:', err);
      alert('Network error while posting reply.');
    } finally {
      if (btn) {
        btn._isSubmitting = false;
        btn.disabled = false;
        btn.classList.remove('btn-is-submitting');
      }
      if (window.hideSavingPopup) window.hideSavingPopup();
    }
  }

  async function resolveCurrentTicket() {
    if (!currentActiveTicket) return;
    if (!confirm(`Are you sure you want to mark Ticket ${currentActiveTicket.ticket_id} as Resolved?`)) return;

    try {
      const res = await fetch(`/api/support/ticket/${currentActiveTicket.ticket_id}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ remark: 'Ticket marked as resolved by company user.' })
      });
      const data = await res.json();
      if (data.success) {
        currentActiveTicket = data.ticket;
        populateTicketModal(data.ticket);
        fetchTicketsList();
        updateSidebarSupportBadge();
      } else {
        alert(data.error || 'Failed to resolve ticket.');
      }
    } catch (err) {
      console.error('Error resolving ticket:', err);
    }
  }

  async function reopenCurrentTicket() {
    if (!currentActiveTicket) return;
    if (!confirm(`Do you want to reopen Ticket ${currentActiveTicket.ticket_id}?`)) return;

    try {
      const res = await fetch(`/api/support/ticket/${currentActiveTicket.ticket_id}/reopen`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ remark: 'Ticket reopened by company user.' })
      });
      const data = await res.json();
      if (data.success) {
        currentActiveTicket = data.ticket;
        populateTicketModal(data.ticket);
        fetchTicketsList();
        updateSidebarSupportBadge();
      } else {
        alert(data.error || 'Failed to reopen ticket.');
      }
    } catch (err) {
      console.error('Error reopening ticket:', err);
    }
  }

  function downloadAllTicketAttachments() {
    if (!currentActiveTicket) return;
    window.open(`/api/support/attachment/${currentActiveTicket.ticket_id}/download-all`, '_blank');
  }

  // --------------------------------------------------------------------------
  // DEMO VIDEOS HUB LOGIC
  // --------------------------------------------------------------------------
  async function loadDemoVideos() {
    try {
      const res = await fetch('/api/support/demo-videos');
      const data = await res.json();
      if (data.success && data.videos && data.videos.length > 0) {
        allDemoVideos = data.videos;
        renderChaptersList();
        selectDemoVideoChapter(0);
        renderMoreVideosCarousel();
      }
    } catch (err) {
      console.error('Error loading demo videos:', err);
    }
  }

  function renderChaptersList() {
    const container = document.getElementById('chaptersListContainer');
    if (!container) return;
    container.innerHTML = '';
    const badge = document.getElementById('chaptersCountBadge');
    if (badge) badge.innerText = `${allDemoVideos.length} Chapters`;

    allDemoVideos.forEach((v, idx) => {
      const item = document.createElement('div');
      item.className = `chapter-item-card ${idx === activeVideoIndex ? 'active-chapter' : ''}`;
      item.id = `chapterItem_${idx}`;
      item.onclick = () => selectDemoVideoChapter(idx);

      item.innerHTML = `
        <div class="chapter-card-left">
          <div class="chapter-card-icon">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="6 4 19 12 6 20 6 4"></polygon></svg>
          </div>
          <div>
            <div class="chapter-card-title">${escapeHtml(v.title)}</div>
            <div class="chapter-card-sub">${escapeHtml(v.subtitle || '')}</div>
          </div>
        </div>
        <div class="chapter-duration-badge">${escapeHtml(v.duration || '05:00')}</div>
      `;
      container.appendChild(item);
    });
  }

  function selectDemoVideoChapter(idx) {
    activeVideoIndex = idx;
    const v = allDemoVideos[idx];
    if (!v) return;

    pauseDemoPlayback();
    simulatedPlaySeconds = 0;
    simulatedDurationSeconds = parseDurationToSeconds(v.duration);

    document.querySelectorAll('.chapter-item-card').forEach((el, i) => {
      el.classList.toggle('active-chapter', i === idx);
    });

    const vTitle = document.getElementById('activeVideoTitle');
    const vSub = document.getElementById('activeVideoSubtitle');
    const vDur = document.getElementById('activeVideoDuration');
    const vTimeDisp = document.getElementById('vCtlTimeDisplay');
    const vFill = document.getElementById('vSeekBarFill');
    const vThumb = document.getElementById('vSeekBarThumb');

    if (vTitle) vTitle.innerText = v.title;
    if (vSub) vSub.innerText = v.subtitle || `Learn how to use ${v.title.replace(/^[0-9]+\.\s*/, '')} in Argus Attendance Intelligence.`;
    if (vDur) vDur.innerText = v.duration || '08:24';
    if (vTimeDisp) vTimeDisp.innerText = `0:00 / ${v.duration || '08:24'}`;
    if (vFill) vFill.style.width = '0%';
    if (vThumb) vThumb.style.left = '0%';

    renderChapterMockup(idx);

    const vDesc = document.getElementById('activeVideoDesc');
    if (vDesc) {
      vDesc.innerText = v.description ||
        `In this video, you will learn how to manage ${v.title.replace(/^[0-9]+\.\s*/, '')} in Argus Attendance Intelligence. This includes configuration, workflow operations, export options, and best practices.`;
    }

    const checkList = document.getElementById('activeVideoLearningList');
    if (checkList) {
      checkList.innerHTML = '';
      const items = v.what_you_will_learn || [
        `Navigate the ${v.title.replace(/^[0-9]+\.\s*/, '')} module seamlessly`,
        'Step-by-step practical operations and management workflows',
        'Configuring system rules, filters and custom preferences',
        'Troubleshooting common errors and ensuring data accuracy',
        'Exporting reports to CSV, Excel, and PDF formats'
      ];
      items.forEach(pt => {
        const li = document.createElement('li');
        li.innerHTML = `
          <svg class="check-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"></polyline></svg>
          <span>${escapeHtml(pt)}</span>
        `;
        checkList.appendChild(li);
      });
    }

    const html5Vid = document.getElementById('demoHtml5Video');
    const source = document.getElementById('demoVideoSource');
    const screen = document.getElementById('simulatedVideoScreen');
    if (html5Vid) {
      html5Vid.pause();
      html5Vid.style.display = 'none';
    }
    if (screen) screen.style.display = 'block';
    if (source && v.video_url) {
      source.src = v.video_url;
      if (html5Vid) html5Vid.load();
    }

    const centerPlay = document.getElementById('screenCenterPlayWrapper');
    if (centerPlay) {
      centerPlay.style.opacity = '1';
      centerPlay.style.pointerEvents = 'auto';
    }
    updatePlayButtonIcon(false);
  }

  // --------------------------------------------------------------------------
  // HIGH-FIDELITY SOFTWARE UI MOCKUP RENDERER
  // --------------------------------------------------------------------------
  function renderChapterMockup(idx) {
    const viewport = document.getElementById('mockupViewport');
    if (!viewport) return;

    const pageRoot = document.getElementById('supportCenterContainer');
    const compName = (pageRoot && pageRoot.getAttribute('data-company-name')) || window.ARGUS_SUPPORT_COMPANY_NAME || 'ARGUS CNC™';
    const initial = compName ? compName.charAt(0).toUpperCase() : 'A';

    const sideModules = [
      { name: 'Dashboard', icon: '📊' },
      { name: 'Employee Details', icon: '👥', activeFor: 0 },
      { name: 'Live Report', icon: '📡', activeFor: 1 },
      { name: 'Attendance Report', icon: '📋', activeFor: 2 },
      { name: 'Manual Entry', icon: '✏️', activeFor: 3 },
      { name: 'Payment Entry', icon: '💳', activeFor: 4 },
      { name: 'Payslip Preview', icon: '📄', activeFor: 5 },
      { name: 'Salary Report', icon: '📈', activeFor: 6 },
      { name: 'Company Profile', icon: '🏢', activeFor: 7 }
    ];

    let sidebarItemsHtml = '';
    sideModules.forEach(m => {
      const isActive = m.activeFor === idx;
      sidebarItemsHtml += `
        <div class="mockup-side-item ${isActive ? 'active' : ''}">
          <span>${m.icon}</span>
          <span>${m.name}</span>
        </div>
      `;
    });

    let moduleBodyHtml = '';

    if (idx === 0) {
      moduleBodyHtml = `
        <div class="mockup-header-row">
          <div class="mockup-header-text">
            <h4>Employee Details</h4>
            <p>Manage your employees, add new employees, and update their information.</p>
          </div>
          <button type="button" class="mockup-btn-primary">+ Add Employee</button>
        </div>
        <div class="mockup-filter-row">
          <input type="text" class="mockup-search-input" placeholder="🔍 Search employees by name, ID..." readonly>
          <select class="mockup-select"><option>All Departments</option></select>
          <select class="mockup-select"><option>All Status</option></select>
          <span style="font-size: 8px; color: #64748b; cursor: pointer;">🔄</span>
        </div>
        <div class="mockup-table-box">
          <table class="mockup-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Employee ID</th>
                <th>Employee Name</th>
                <th>Designation</th>
                <th>Department</th>
                <th>Phone Number</th>
                <th>Join Date</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>1</td>
                <td style="font-weight: 700; color: #0284c7;">EMP001</td>
                <td style="font-weight: 600;">John Smith</td>
                <td>Manager</td>
                <td>Administration</td>
                <td>9876543210</td>
                <td>12/01/2023</td>
                <td><span class="mockup-pill-green">Active</span></td>
                <td>✏️ 👁️</td>
              </tr>
              <tr>
                <td>2</td>
                <td style="font-weight: 700; color: #0284c7;">EMP002</td>
                <td style="font-weight: 600;">Sarah Johnson</td>
                <td>HR Executive</td>
                <td>Human Resources</td>
                <td>9876543211</td>
                <td>15/02/2023</td>
                <td><span class="mockup-pill-green">Active</span></td>
                <td>✏️ 👁️</td>
              </tr>
              <tr>
                <td>3</td>
                <td style="font-weight: 700; color: #0284c7;">EMP003</td>
                <td style="font-weight: 600;">Michael Brown</td>
                <td>Software Engineer</td>
                <td>IT</td>
                <td>9876543212</td>
                <td>10/03/2023</td>
                <td><span class="mockup-pill-green">Active</span></td>
                <td>✏️ 👁️</td>
              </tr>
            </tbody>
          </table>
        </div>
      `;
    } else if (idx === 1) {
      moduleBodyHtml = `
        <div class="mockup-header-row">
          <div class="mockup-header-text">
            <h4>Live Report &amp; Face Recognition Monitor</h4>
            <p>Real-time employee attendance feed with biometric validation.</p>
          </div>
          <span style="font-size: 7.5px; background: #dcfce7; color: #16a34a; font-weight: 700; padding: 2px 6px; border-radius: 4px;">● Live Feed Active</span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;">
          <div style="background: #ffffff; padding: 4px 6px; border-radius: 3px; border: 1px solid #e2e8f0;">
            <div style="font-size: 7px; color: #64748b;">Total Staff</div>
            <div style="font-size: 11px; font-weight: 800; color: #0f172a;">42</div>
          </div>
          <div style="background: #ffffff; padding: 4px 6px; border-radius: 3px; border: 1px solid #e2e8f0;">
            <div style="font-size: 7px; color: #64748b;">Present Today</div>
            <div style="font-size: 11px; font-weight: 800; color: #16a34a;">38</div>
          </div>
          <div style="background: #ffffff; padding: 4px 6px; border-radius: 3px; border: 1px solid #e2e8f0;">
            <div style="font-size: 7px; color: #64748b;">Late Entries</div>
            <div style="font-size: 11px; font-weight: 800; color: #d97706;">3</div>
          </div>
          <div style="background: #ffffff; padding: 4px 6px; border-radius: 3px; border: 1px solid #e2e8f0;">
            <div style="font-size: 7px; color: #64748b;">On Leave</div>
            <div style="font-size: 11px; font-weight: 800; color: #0284c7;">1</div>
          </div>
        </div>
        <div class="mockup-table-box">
          <table class="mockup-table">
            <thead>
              <tr>
                <th>Punch Time</th>
                <th>Employee Name</th>
                <th>Department</th>
                <th>Status</th>
                <th>Device</th>
                <th>Match</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="font-weight: 700;">09:02:14 AM</td>
                <td style="font-weight: 600;">John Smith</td>
                <td>Admin</td>
                <td><span class="mockup-pill-green">PUNCH IN</span></td>
                <td>Gate Cam 01</td>
                <td style="color: #16a34a; font-weight: 700;">99.4%</td>
              </tr>
            </tbody>
          </table>
        </div>
      `;
    } else {
      moduleBodyHtml = `
        <div class="mockup-header-row">
          <div class="mockup-header-text">
            <h4>Attendance Operations &amp; Intelligence</h4>
            <p>Comprehensive attendance reports, shifts, payroll calculations and company policies.</p>
          </div>
          <button type="button" class="mockup-btn-primary">📊 View Reports</button>
        </div>
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 4px; padding: 10px; font-size: 8px;">
          <div style="font-weight: 700; color: #0284c7; margin-bottom: 4px;">Argus Attendance Intelligence Platform</div>
          <p style="color: #475569; margin: 0;">Automated AI gate camera attendance, monthly payroll salary generation, leave policies, and system administration.</p>
        </div>
      `;
    }

    viewport.innerHTML = `
      <div class="mockup-top-nav">
        <div class="mockup-nav-left" style="display: flex; align-items: center; gap: 8px;">
          <img src="/static/images/argus_square_badge.png?v=20261118_v5" class="brand-square-badge" alt="Argus" style="width: 20px; height: 20px; border-radius: 4px;">
          <div class="brand-vertical-divider" style="height: 14px;"></div>
          <span class="brand-text-inline" style="font-size: 10px;">ATTENDANCE INTELLIGENCE</span>
        </div>
        <div class="mockup-nav-title">${escapeHtml(compName)}</div>
        <div class="mockup-nav-right">
          <span style="font-size: 10px;">🔔</span>
          <div class="mockup-avatar-pill">
            <div class="mockup-avatar-circle">${initial}</div>
            <span>${escapeHtml(compName)}</span>
          </div>
        </div>
      </div>
      <div class="mockup-body">
        <div class="mockup-sidebar">${sidebarItemsHtml}</div>
        <div class="mockup-content">${moduleBodyHtml}</div>
      </div>
    `;
  }

  // --------------------------------------------------------------------------
  // VIDEO PLAYBACK SIMULATION & CONTROLS
  // --------------------------------------------------------------------------
  function toggleDemoVideoPlayback() {
    const v = allDemoVideos[activeVideoIndex];
    if (!v) return;

    const html5Vid = document.getElementById('demoHtml5Video');
    const source = document.getElementById('demoVideoSource');
    if (v.video_url && html5Vid && source) {
      if (html5Vid.paused) {
        if (!source.getAttribute('src') || source.getAttribute('src') !== v.video_url) {
          source.src = v.video_url;
          html5Vid.load();
        }
        const screen = document.getElementById('simulatedVideoScreen');
        if (screen) screen.style.display = 'none';
        html5Vid.style.display = 'block';
        html5Vid.play().catch(e => console.log(e));
        updatePlayButtonIcon(true);
      } else {
        html5Vid.pause();
        updatePlayButtonIcon(false);
      }
      html5Vid.onended = () => {
        html5Vid.style.display = 'none';
        const screen = document.getElementById('simulatedVideoScreen');
        if (screen) screen.style.display = 'block';
        const centerPlay = document.getElementById('screenCenterPlayWrapper');
        if (centerPlay) {
          centerPlay.style.opacity = '1';
          centerPlay.style.pointerEvents = 'auto';
        }
        updatePlayButtonIcon(false);
      };
      html5Vid.onpause = () => updatePlayButtonIcon(false);
      html5Vid.onplay = () => updatePlayButtonIcon(true);
      return;
    }

    if (isSimulatedPlaying) {
      pauseDemoPlayback();
    } else {
      playDemoPlayback();
    }
  }

  function playDemoPlayback() {
    isSimulatedPlaying = true;
    updatePlayButtonIcon(true);

    const centerBtn = document.getElementById('screenCenterPlayWrapper');
    if (centerBtn) {
      centerBtn.style.opacity = '0';
      centerBtn.style.pointerEvents = 'none';
    }

    clearInterval(simulatedPlayInterval);
    simulatedPlayInterval = setInterval(() => {
      simulatedPlaySeconds++;
      if (simulatedPlaySeconds > simulatedDurationSeconds) {
        simulatedPlaySeconds = 0;
        pauseDemoPlayback();
        return;
      }
      updatePlaybackProgressUI();
    }, 1000);
  }

  function pauseDemoPlayback() {
    isSimulatedPlaying = false;
    clearInterval(simulatedPlayInterval);
    updatePlayButtonIcon(false);

    const centerBtn = document.getElementById('screenCenterPlayWrapper');
    if (centerBtn) {
      centerBtn.style.opacity = '1';
      centerBtn.style.pointerEvents = 'auto';
    }
  }

  function updatePlaybackProgressUI() {
    const pct = Math.min(100, (simulatedPlaySeconds / simulatedDurationSeconds) * 100);
    const fill = document.getElementById('vSeekBarFill');
    const thumb = document.getElementById('vSeekBarThumb');
    if (fill) fill.style.width = `${pct}%`;
    if (thumb) thumb.style.left = `${pct}%`;

    const v = allDemoVideos[activeVideoIndex];
    const durStr = v ? v.duration : '08:24';
    const timeDisp = document.getElementById('vCtlTimeDisplay');
    if (timeDisp) timeDisp.innerText = `${formatSeconds(simulatedPlaySeconds)} / ${durStr}`;
  }

  function updatePlayButtonIcon(playing) {
    const icon = document.getElementById('iconPlayPause');
    if (!icon) return;
    if (playing) {
      icon.innerHTML = `<rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect>`;
    } else {
      icon.innerHTML = `<polygon points="6 4 19 12 6 20 6 4"></polygon>`;
    }
  }

  function handleSeekbarClick(e) {
    const track = document.getElementById('vSeekBarTrack');
    if (!track) return;
    const rect = track.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, clickX / rect.width));

    simulatedPlaySeconds = Math.floor(pct * simulatedDurationSeconds);
    updatePlaybackProgressUI();
  }

  function toggleDemoVolume() {
    isSimulatedMuted = !isSimulatedMuted;
    const icon = document.getElementById('iconVolume');
    if (!icon) return;
    if (isSimulatedMuted) {
      icon.innerHTML = `<line x1="1" y1="1" x2="23" y2="23"></line><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"></path>`;
    } else {
      icon.innerHTML = `<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"></polygon><path d="M19.07 4.93a10 10 0 0 1 0 14.14M15.54 8.46a5 5 0 0 1 0 7.07"></path>`;
    }
  }

  function togglePlayerFullscreen() {
    const frame = document.getElementById('demoVideoPlayerFrame');
    if (!frame) return;
    if (!document.fullscreenElement) {
      frame.requestFullscreen().catch(err => console.log('Fullscreen error:', err));
    } else {
      document.exitFullscreen().catch(err => console.log(err));
    }
  }

  function renderMoreVideosCarousel() {
    const container = document.getElementById('moreVideosContainer');
    if (!container) return;
    container.innerHTML = '';

    allDemoVideos.forEach((v, idx) => {
      const card = document.createElement('div');
      card.className = 'more-video-card';
      card.onclick = () => {
        selectDemoVideoChapter(idx);
        const playerFrame = document.getElementById('demoVideoPlayerFrame');
        if (playerFrame) playerFrame.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      };

      const colors = ['#0284c7', '#16a34a', '#8b5cf6', '#d97706', '#059669', '#2563eb', '#dc2626', '#475569'];
      const barColor = colors[idx % colors.length];

      card.innerHTML = `
        <div class="more-video-thumb">
          <div style="position: absolute; top: 0; left: 0; right: 0; height: 18px; background: #ffffff; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; padding: 0 6px; gap: 4px;">
            <div style="width: 5px; height: 5px; border-radius: 50%; background: ${barColor};"></div>
            <span style="font-size: 7px; font-weight: 800; color: #0f172a;">ARGUS</span>
          </div>
          <div style="position: absolute; top: 22px; left: 6px; right: 6px; bottom: 6px; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 3px; display: flex; flex-direction: column; gap: 3px; padding: 3px;">
            <div style="height: 4px; width: 45%; background: ${barColor}; border-radius: 1px;"></div>
            <div style="height: 3px; width: 85%; background: #e2e8f0; border-radius: 1px;"></div>
            <div style="height: 3px; width: 70%; background: #e2e8f0; border-radius: 1px;"></div>
            <div style="height: 3px; width: 90%; background: #e2e8f0; border-radius: 1px;"></div>
          </div>
          <div class="more-thumb-play">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="#ffffff"><polygon points="7 4 20 12 7 20 7 4"></polygon></svg>
          </div>
          <span class="more-thumb-duration">${v.duration || '05:00'}</span>
        </div>
        <div class="more-video-card-title">${escapeHtml(v.title)}</div>
      `;
      container.appendChild(card);
    });
  }

  function scrollMoreVideos(direction) {
    const container = document.getElementById('moreVideosContainer');
    if (!container) return;
    const scrollAmount = direction === 'left' ? -220 : 220;
    container.scrollBy({ left: scrollAmount, behavior: 'smooth' });
  }

  async function updateSidebarSupportBadge() {
    try {
      const res = await fetch('/api/support/badge-count');
      const data = await res.json();
      if (data.success) {
        const badge = document.getElementById('sidebarSupportBadge');
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
  // PROGRAMMATIC EVENT BINDING
  // --------------------------------------------------------------------------
  function bindCompanySupportEventListeners() {
    const heroRaise = document.getElementById('heroCardRaise');
    const heroTickets = document.getElementById('heroCardTickets');
    const heroVideos = document.getElementById('heroCardVideos');
    if (heroRaise) heroRaise.onclick = () => switchSupportTab('raise');
    if (heroTickets) heroTickets.onclick = () => switchSupportTab('tickets');
    if (heroVideos) heroVideos.onclick = () => switchSupportTab('videos');

    const formRaise = document.getElementById('raiseTicketForm');
    if (formRaise) {
      formRaise.onsubmit = (e) => submitSupportTicket(e);
    }

    const fileInp = document.getElementById('ticketFilesInput');
    if (fileInp) {
      fileInp.onchange = function () { handleTicketFilesSelect(this); };
    }

    const searchInp = document.getElementById('ticketsSearchInput');
    if (searchInp) {
      searchInp.onkeyup = () => handleTicketSearchDebounce();
    }

    const btnRefresh = document.getElementById('btnRefreshSupport');
    if (btnRefresh) {
      btnRefresh.onclick = () => refreshSupportTickets();
    }

    const modalBackdrop = document.getElementById('ticketModalBackdrop');
    if (modalBackdrop) {
      modalBackdrop.onclick = function (e) {
        if (e.target === modalBackdrop) closeTicketModal();
      };
    }

    const btnCloseModal = document.getElementById('btnCloseTicketModal');
    if (btnCloseModal) {
      btnCloseModal.onclick = () => closeTicketModal();
    }

    const formReply = document.getElementById('ticketReplyForm');
    if (formReply) {
      formReply.onsubmit = (e) => submitTicketReply(e);
    }

    const replyInp = document.getElementById('replyFileInput');
    if (replyInp) {
      replyInp.onchange = function () { handleReplyFilesSelect(this); };
    }

    const btnReopen = document.getElementById('btnReopenTicket');
    if (btnReopen) {
      btnReopen.onclick = () => reopenCurrentTicket();
    }

    const btnResolve = document.getElementById('btnResolveTicket');
    if (btnResolve) {
      btnResolve.onclick = () => resolveCurrentTicket();
    }

    const btnDlAll = document.getElementById('btnDownloadAll');
    if (btnDlAll) {
      btnDlAll.onclick = () => downloadAllTicketAttachments();
    }
  }

  // --------------------------------------------------------------------------
  // ATTACH TO WINDOW GLOBAL SCOPE (ENSURES ALL INLINE ONCLICK HANDLERS WORK)
  // --------------------------------------------------------------------------
  window.switchSupportTab = switchSupportTab;
  window._switchSupportTabHandler = switchSupportTab;
  window.handleTicketFilesSelect = handleTicketFilesSelect;
  window.renderTicketFileChips = renderTicketFileChips;
  window.removeTicketFile = removeTicketFile;
  window.formatFileSize = formatFileSize;
  window.submitSupportTicket = submitSupportTicket;
  window.filterTicketsByStatus = filterTicketsByStatus;
  window.handleTicketSearchDebounce = handleTicketSearchDebounce;
  window.refreshSupportTickets = refreshSupportTickets;
  window.fetchTicketsList = fetchTicketsList;
  window.getStatusBadgeClass = getStatusBadgeClass;
  window.renderPagination = renderPagination;
  window.openTicketModal = openTicketModal;
  window.closeTicketModal = closeTicketModal;
  window.populateTicketModal = populateTicketModal;
  window.handleReplyFilesSelect = handleReplyFilesSelect;
  window.renderReplyFileChips = renderReplyFileChips;
  window.submitTicketReply = submitTicketReply;
  window.resolveCurrentTicket = resolveCurrentTicket;
  window.reopenCurrentTicket = reopenCurrentTicket;
  window.downloadAllTicketAttachments = downloadAllTicketAttachments;
  window.loadDemoVideos = loadDemoVideos;
  window.renderChaptersList = renderChaptersList;
  window.selectDemoVideoChapter = selectDemoVideoChapter;
  window.renderChapterMockup = renderChapterMockup;
  window.toggleDemoVideoPlayback = toggleDemoVideoPlayback;
  window.playDemoPlayback = playDemoPlayback;
  window.pauseDemoPlayback = pauseDemoPlayback;
  window.updatePlaybackProgressUI = updatePlaybackProgressUI;
  window.updatePlayButtonIcon = updatePlayButtonIcon;
  window.handleSeekbarClick = handleSeekbarClick;
  window.toggleDemoVolume = toggleDemoVolume;
  window.togglePlayerFullscreen = togglePlayerFullscreen;
  window.renderMoreVideosCarousel = renderMoreVideosCarousel;
  window.scrollMoreVideos = scrollMoreVideos;
  window.updateSidebarSupportBadge = updateSidebarSupportBadge;
  window.bindCompanySupportEventListeners = bindCompanySupportEventListeners;
  window.escapeHtml = escapeHtml;

  // --------------------------------------------------------------------------
  // INITIALIZATION FOR BOTH DIRECT PAGE LOAD AND SPA NAVIGATION
  // --------------------------------------------------------------------------
  function initCompanySupport() {
    const isSupportPage = document.getElementById('supportCenterContainer') || document.getElementById('heroCardRaise') || document.getElementById('viewRaiseTicket');
    if (!isSupportPage) return;

    bindCompanySupportEventListeners();
    loadDemoVideos();
    fetchTicketsList();
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    initCompanySupport();
  } else {
    document.addEventListener('DOMContentLoaded', initCompanySupport);
  }
  window.addEventListener('page:loaded', initCompanySupport);

})();
