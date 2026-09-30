// Main application script: Navigation, sidebar toggle
document.addEventListener('DOMContentLoaded', function () {
  const sidebar = document.getElementById('appSidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const appContainer = document.querySelector('.app-container');
  const topNavbar = document.querySelector('.top-navbar');

  function isMobile() {
    return window.innerWidth <= 768;
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

    const marginValue = isCollapsed || isMobile() ? '0px' : '220px';
    if (topNavbar) {
      topNavbar.style.marginLeft = marginValue;
    }
    if (appContainer) {
      appContainer.style.marginLeft = marginValue;
    }
  }

  // Auto-collapse sidebar on initial mobile load
  if (isMobile() && sidebar) {
    sidebar.classList.add('collapsed');
    document.body.classList.add('sidebar-collapsed');
    if (topNavbar) topNavbar.style.marginLeft = '0px';
    if (appContainer) appContainer.style.marginLeft = '0px';
  } else {
    if (topNavbar) topNavbar.style.marginLeft = '220px';
    if (appContainer) appContainer.style.marginLeft = '220px';
  }

  // Navbar hamburger toggle (open / close)
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleSidebar();
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

  // Handle window resize dynamically
  window.addEventListener('resize', function () {
    if (!sidebar) return;
    const isCollapsed = sidebar.classList.contains('collapsed');
    const marginValue = isCollapsed || isMobile() ? '0px' : '220px';
    if (topNavbar) {
      topNavbar.style.marginLeft = marginValue;
    }
    if (appContainer) {
      appContainer.style.marginLeft = marginValue;
    }
  });
});
