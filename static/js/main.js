// Main application script: Navigation, sidebar toggle, refresh reload
document.addEventListener('DOMContentLoaded', function () {
  const sidebar = document.getElementById('appSidebar');
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');
  const pageRefreshBtn = document.getElementById('pageRefreshBtn');
  const appContainer = document.querySelector('.app-container');

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
    if (appContainer) {
      if (isMobile()) {
        appContainer.style.marginLeft = '0px';
      } else {
        appContainer.style.marginLeft = isCollapsed ? '0px' : '200px';
      }
    }
  }

  // Auto-collapse sidebar on initial mobile load
  if (isMobile() && sidebar) {
    sidebar.classList.add('collapsed');
  }

  // Navbar hamburger toggle (open / close)
  if (sidebarToggle) {
    sidebarToggle.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleSidebar();
    });
  }

  // Sidebar internal hamburger button (top left inside sidebar to expand main content)
  if (sidebarCollapseBtn) {
    sidebarCollapseBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleSidebar(false); // Collapses sidebar -> Expands main content!
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

  // Top-right Refresh / Reload button
  if (pageRefreshBtn) {
    pageRefreshBtn.addEventListener('click', function () {
      window.location.reload();
    });
  }

  // Handle window resize dynamically
  window.addEventListener('resize', function () {
    if (!sidebar || !appContainer) return;
    if (isMobile()) {
      appContainer.style.marginLeft = '0px';
    } else {
      appContainer.style.marginLeft = sidebar.classList.contains('collapsed') ? '0px' : '200px';
    }
  });
});

