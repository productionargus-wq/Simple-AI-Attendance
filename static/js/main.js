// Main application script: Navigation, mobile drawer, responsive sidebar & desktop mini-sidebar
document.addEventListener('DOMContentLoaded', function () {
  const sidebar = document.getElementById('appSidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarBackdrop = document.getElementById('sidebarBackdrop');
  const miniTooltip = document.getElementById('sidebarMiniTooltip');

  function isMobile() {
    return window.innerWidth <= 992;
  }

  function toggleSidebar(forceState) {
    if (!sidebar) return;

    if (isMobile()) {
      // ---------------- Mobile View (<= 992px) ----------------
      // Always treat as full off-canvas drawer with backdrop overlay
      document.body.classList.remove('sidebar-mini');
      if (miniTooltip) miniTooltip.classList.remove('visible');

      if (typeof forceState === 'boolean') {
        if (forceState) {
          document.body.classList.add('drawer-open');
          sidebar.classList.remove('collapsed');
        } else {
          document.body.classList.remove('drawer-open');
          sidebar.classList.add('collapsed');
        }
      } else {
        const isOpening = !document.body.classList.contains('drawer-open');
        document.body.classList.toggle('drawer-open', isOpening);
        sidebar.classList.toggle('collapsed', !isOpening);
      }
    } else {
      // ---------------- Desktop View (> 992px) ----------------
      // Toggle Mini-Sidebar (icon-only mode with tooltips & full-width content expansion)
      document.body.classList.remove('drawer-open');
      sidebar.classList.remove('collapsed');

      let isMini;
      if (typeof forceState === 'boolean') {
        isMini = !forceState;
        document.body.classList.toggle('sidebar-mini', isMini);
        sidebar.classList.toggle('mini', isMini);
      } else {
        isMini = document.body.classList.toggle('sidebar-mini');
        sidebar.classList.toggle('mini', isMini);
      }

      // Persist desktop mini preference in localStorage
      try {
        localStorage.setItem('argus_desktop_sidebar_mini', isMini ? 'true' : 'false');
      } catch (err) {
        console.warn('Could not save sidebar preference:', err);
      }

      if (miniTooltip) miniTooltip.classList.remove('visible');
    }
  }

  // Floating Tooltip for Desktop Mini-Sidebar
  function setupMiniSidebarTooltips() {
    if (!sidebar || !miniTooltip) return;

    const items = sidebar.querySelectorAll('.nav-item-btn, .sidebar-logout-card, .sidebar-fw-card');
    items.forEach(item => {
      item.addEventListener('mouseenter', function () {
        if (!document.body.classList.contains('sidebar-mini') || isMobile()) return;

        const text = item.getAttribute('data-tooltip') || item.querySelector('span')?.innerText?.trim() || '';
        if (!text) return;

        miniTooltip.textContent = text;
        const rect = item.getBoundingClientRect();
        miniTooltip.style.top = (rect.top + rect.height / 2) + 'px';
        miniTooltip.style.left = (rect.right + 12) + 'px';
        miniTooltip.classList.add('visible');
      });

      item.addEventListener('mouseleave', function () {
        miniTooltip.classList.remove('visible');
      });

      item.addEventListener('click', function () {
        miniTooltip.classList.remove('visible');
      });
    });

    const sidebarNav = sidebar.querySelector('.sidebar-nav');
    if (sidebarNav) {
      sidebarNav.addEventListener('scroll', function () {
        miniTooltip.classList.remove('visible');
      });
    }
  }

  // Initial State Setup on Page Load
  if (isMobile()) {
    document.body.classList.remove('drawer-open');
    document.body.classList.remove('sidebar-mini');
    if (sidebar) {
      sidebar.classList.add('collapsed');
      sidebar.classList.remove('mini');
    }
  } else {
    document.body.classList.remove('drawer-open');
    if (sidebar) sidebar.classList.remove('collapsed');

    // Restore desktop mini state from localStorage
    try {
      const savedMini = localStorage.getItem('argus_desktop_sidebar_mini');
      if (savedMini === 'true') {
        document.body.classList.add('sidebar-mini');
        if (sidebar) sidebar.classList.add('mini');
      } else {
        document.body.classList.remove('sidebar-mini');
        if (sidebar) sidebar.classList.remove('mini');
      }
    } catch (e) {
      // Default to expanded on desktop
    }
  }

  setupMiniSidebarTooltips();

  // Window resize handler: seamlessly switch between mobile drawer and desktop mini states
  window.addEventListener('resize', function () {
    if (isMobile()) {
      document.body.classList.remove('sidebar-mini');
      if (miniTooltip) miniTooltip.classList.remove('visible');
      if (!document.body.classList.contains('drawer-open') && sidebar) {
        sidebar.classList.add('collapsed');
      }
    } else {
      document.body.classList.remove('drawer-open');
      if (sidebar) sidebar.classList.remove('collapsed');
      try {
        const savedMini = localStorage.getItem('argus_desktop_sidebar_mini');
        if (savedMini === 'true') {
          document.body.classList.add('sidebar-mini');
          if (sidebar) sidebar.classList.add('mini');
        } else {
          document.body.classList.remove('sidebar-mini');
          if (sidebar) sidebar.classList.remove('mini');
        }
      } catch (e) {}
    }
  });

  // Navbar hamburger toggle (open / close / mini)
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleSidebar();
    });
  }

  // Backdrop overlay click/touch closes drawer on mobile
  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', function () {
      toggleSidebar(false);
    });
    sidebarBackdrop.addEventListener('touchstart', function (e) {
      e.preventDefault();
      toggleSidebar(false);
    }, { passive: false });
  }

  // Close sidebar when clicking outside on mobile screens
  document.addEventListener('click', function (e) {
    if (isMobile() && sidebar && !sidebar.classList.contains('collapsed')) {
      if (!sidebar.contains(e.target) && (!sidebarToggle || !sidebarToggle.contains(e.target))) {
        toggleSidebar(false);
      }
    }
  });

  // Auto-close drawer on mobile when clicking navigation links
  if (sidebar) {
    const navLinks = sidebar.querySelectorAll('a');
    navLinks.forEach(link => {
      link.addEventListener('click', function () {
        if (isMobile()) {
          toggleSidebar(false);
        }
      });
    });
  }

  // Touch swipe support to close drawer on mobile with vertical scroll guard
  let touchStartX = 0;
  let touchStartY = 0;
  if (sidebar) {
    sidebar.addEventListener('touchstart', function (e) {
      touchStartX = e.changedTouches[0].clientX;
      touchStartY = e.changedTouches[0].clientY;
    }, { passive: true });

    sidebar.addEventListener('touchend', function (e) {
      const deltaX = touchStartX - e.changedTouches[0].clientX;
      const deltaY = touchStartY - e.changedTouches[0].clientY;
      if (deltaX > 50 && Math.abs(deltaX) > Math.abs(deltaY)) {
        // Swiped left horizontally by more than 50px
        toggleSidebar(false);
      }
    }, { passive: true });
  }

  // Universal modal body-scroll lock observer with state guard to eliminate DOM thrashing
  let lastModalState = false;
  const modalObserver = new MutationObserver(function () {
    const hasActiveModal = !!document.querySelector('.modal-overlay.active');
    if (hasActiveModal !== lastModalState) {
      lastModalState = hasActiveModal;
      if (hasActiveModal) {
        document.body.classList.add('modal-open');
      } else {
        document.body.classList.remove('modal-open');
      }
    }
  });
  modalObserver.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['class'] });

  // Global Escape key to dismiss any active modal
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' || e.keyCode === 27) {
      const activeModal = document.querySelector('.modal-overlay.active');
      if (activeModal) {
        activeModal.classList.remove('active');
      }
    }
  });

  // Modal backdrop touch dismiss
  // Passive touchstart for mobile modal dismissal
  document.addEventListener('touchstart', function (e) {
    if (e.target.classList && e.target.classList.contains('modal-overlay') && e.target.classList.contains('active')) {
      e.target.classList.remove('active');
    }
  }, { passive: true });
});

// Universal safe clipboard copy helper with fallback for non-secure HTTP / LAN mobile
window.safeCopyToClipboard = function (text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  return new Promise((resolve, reject) => {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.left = '-9999px';
      ta.style.top = '-9999px';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const success = document.execCommand('copy');
      document.body.removeChild(ta);
      if (success) resolve();
      else reject(new Error('execCommand copy failed'));
    } catch (err) {
      reject(err);
    }
  });
};

// ==========================================================================
// Global Saving Feedback Popup & Anti-Duplicate Overlay Controller
// ==========================================================================
window.showSavingPopup = function (title = 'Saving Record...', subtitle = 'Please wait while the system securely processes your request.') {
  let overlay = document.getElementById('globalSavingOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'globalSavingOverlay';
    overlay.className = 'global-saving-overlay';
    overlay.innerHTML = `
      <div class="global-saving-card">
        <div class="global-saving-spinner">
          <div class="spinner-ring"></div>
        </div>
        <div class="global-saving-content">
          <h4 id="globalSavingTitle" class="global-saving-title">Saving Record...</h4>
          <p id="globalSavingSubtitle" class="global-saving-subtitle">Please wait while the system securely processes your request.</p>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
  }
  const titleEl = document.getElementById('globalSavingTitle');
  const subEl = document.getElementById('globalSavingSubtitle');
  if (titleEl) titleEl.textContent = title;
  if (subEl) subEl.textContent = subtitle;
  overlay.classList.add('active');
};

window.hideSavingPopup = function () {
  const overlay = document.getElementById('globalSavingOverlay');
  if (overlay) {
    overlay.classList.remove('active');
  }
};
