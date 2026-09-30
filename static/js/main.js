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

  // Backdrop overlay click closes drawer on mobile
  if (sidebarBackdrop) {
    sidebarBackdrop.addEventListener('click', function () {
      toggleSidebar(false);
    });
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

  // Touch swipe support to close drawer on mobile
  let touchStartX = 0;
  if (sidebar) {
    sidebar.addEventListener('touchstart', function (e) {
      touchStartX = e.changedTouches[0].screenX;
    }, { passive: true });

    sidebar.addEventListener('touchend', function (e) {
      const touchEndX = e.changedTouches[0].screenX;
      if (touchStartX - touchEndX > 50) {
        // Swiped left by more than 50px
        toggleSidebar(false);
      }
    }, { passive: true });
  }

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
