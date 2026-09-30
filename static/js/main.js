// Main application script: Navigation, mobile drawer, responsive sidebar
document.addEventListener('DOMContentLoaded', function () {
  const sidebar = document.getElementById('appSidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarBackdrop = document.getElementById('sidebarBackdrop');
  const appContainer = document.querySelector('.app-container');
  const topNavbar = document.querySelector('.top-navbar');

  function isMobile() {
    return window.innerWidth <= 992;
  }

  function toggleSidebar(forceState) {
    if (!sidebar) return;
    if (typeof forceState === 'boolean') {
      sidebar.classList.toggle('collapsed', !forceState);
    } else {
      sidebar.classList.toggle('collapsed');
    }

    const isCollapsed = sidebar.classList.contains('collapsed');
    document.body.classList.toggle('sidebar-collapsed', isCollapsed);

    if (isMobile()) {
      // On mobile, lock/unlock body scroll when drawer is open
      if (!isCollapsed) {
        document.body.classList.add('drawer-open');
      } else {
        document.body.classList.remove('drawer-open');
      }
      if (topNavbar) topNavbar.style.marginLeft = '0px';
      if (appContainer) appContainer.style.marginLeft = '0px';
    } else {
      document.body.classList.remove('drawer-open');
      const marginValue = isCollapsed ? '0px' : '220px';
      if (topNavbar) topNavbar.style.marginLeft = marginValue;
      if (appContainer) appContainer.style.marginLeft = marginValue;
    }
  }

  // Initial state setup on page load
  if (isMobile() && sidebar) {
    sidebar.classList.add('collapsed');
    document.body.classList.add('sidebar-collapsed');
    document.body.classList.remove('drawer-open');
    if (topNavbar) topNavbar.style.marginLeft = '0px';
    if (appContainer) appContainer.style.marginLeft = '0px';
  } else if (sidebar) {
    const isCollapsed = sidebar.classList.contains('collapsed');
    const marginValue = isCollapsed ? '0px' : '220px';
    if (topNavbar) topNavbar.style.marginLeft = marginValue;
    if (appContainer) appContainer.style.marginLeft = marginValue;
  }

  // Navbar hamburger toggle (open / close)
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
  document.addEventListener('touchstart', function (e) {
    if (e.target.classList && e.target.classList.contains('modal-overlay') && e.target.classList.contains('active')) {
      e.target.classList.remove('active');
    }
  }, { passive: true });

  // Handle window resize dynamically
  window.addEventListener('resize', function () {
    if (!sidebar) return;
    const isCollapsed = sidebar.classList.contains('collapsed');
    if (isMobile()) {
      if (topNavbar) topNavbar.style.marginLeft = '0px';
      if (appContainer) appContainer.style.marginLeft = '0px';
      if (isCollapsed) {
        document.body.classList.remove('drawer-open');
      }
    } else {
      document.body.classList.remove('drawer-open');
      const marginValue = isCollapsed ? '0px' : '220px';
      if (topNavbar) topNavbar.style.marginLeft = marginValue;
      if (appContainer) appContainer.style.marginLeft = marginValue;
    }
  });
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
