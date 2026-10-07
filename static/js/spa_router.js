/**
 * SPA Router & Instant Navigation Engine
 * Eliminates full-page reloads and browser tab title bar spinners.
 * Provides instant Gmail/Slack-style tab transitions across the sidebar.
 */

(function () {
  'use strict';

  // 1. DOMContentLoaded Polyfill for dynamically loaded scripts
  // If document is already loaded/interactive, any new 'DOMContentLoaded' listener runs immediately via setTimeout
  const _origAddEventListener = document.addEventListener.bind(document);
  document.addEventListener = function (type, listener, options) {
    if (type === 'DOMContentLoaded' && (document.readyState === 'complete' || document.readyState === 'interactive')) {
      setTimeout(listener, 0);
      return;
    }
    return _origAddEventListener(type, listener, options);
  };

  // State
  let isNavigating = false;
  let activeAbortController = null;
  let progressBar = null;
  let progressTimer = null;

  // 2. Initialize Top Progress Bar
  function initProgressBar() {
    if (progressBar) return;
    progressBar = document.getElementById('appTopProgressBar');
    if (!progressBar) {
      progressBar = document.createElement('div');
      progressBar.id = 'appTopProgressBar';
      progressBar.className = 'spa-progress-bar';
      document.body.appendChild(progressBar);
    }
  }

  function startProgress() {
    initProgressBar();
    if (!progressBar) return;
    clearTimeout(progressTimer);
    progressBar.style.opacity = '1';
    progressBar.style.width = '0%';
    setTimeout(() => {
      if (progressBar) progressBar.style.width = '35%';
    }, 10);
    setTimeout(() => {
      if (progressBar && isNavigating) progressBar.style.width = '70%';
    }, 120);
  }

  function finishProgress() {
    if (!progressBar) return;
    progressBar.style.width = '100%';
    progressTimer = setTimeout(() => {
      if (progressBar) {
        progressBar.style.opacity = '0';
        setTimeout(() => {
          if (progressBar) progressBar.style.width = '0%';
        }, 200);
      }
    }, 120);
  }

  // 3. Check if link should be intercepted
  function shouldIntercept(anchor) {
    if (!anchor || !anchor.href) return false;

    // Check key modifiers (allow Ctrl+Click to open in new tab)
    if (window.event && (window.event.ctrlKey || window.event.metaKey || window.event.shiftKey || window.event.altKey)) {
      return false;
    }

    const href = anchor.getAttribute('href');
    if (!href || href === '#' || href.startsWith('javascript:') || href.startsWith('mailto:') || href.startsWith('tel:')) {
      return false;
    }

    if (anchor.target && anchor.target !== '_self') return false;
    if (anchor.hasAttribute('download')) return false;
    if (anchor.dataset.noSpa === 'true' || anchor.dataset.turbo === 'false') return false;

    // Check same origin
    const url = new URL(anchor.href, window.location.origin);
    if (url.origin !== window.location.origin) return false;

    // Disallow logout and raw files/downloads
    if (url.pathname === '/logout' || url.pathname.includes('/logout')) return false;
    if (url.pathname.startsWith('/api/') && (url.pathname.includes('/pdf') || url.pathname.includes('/excel') || url.pathname.includes('/download'))) {
      return false;
    }

    return true;
  }

  // 4. Update Sidebar Active State
  function updateSidebarActive(targetPath) {
    const sidebar = document.getElementById('appSidebar');
    if (!sidebar) return;

    const navLinks = sidebar.querySelectorAll('.sidebar-nav a.nav-item-btn');
    const normalizedTarget = targetPath.split('?')[0].replace(/\/+$/, '') || '/';

    navLinks.forEach(link => {
      const linkUrl = new URL(link.href, window.location.origin);
      const linkPath = linkUrl.pathname.replace(/\/+$/, '') || '/';
      if (linkPath === normalizedTarget) {
        link.classList.add('active');
      } else {
        link.classList.remove('active');
      }
    });
  }

  // 5. Update Sidebar Count Badges from incoming document
  function updateSidebarBadges(newDoc) {
    const badgeIds = ['sidebarLeaveBadge', 'sidebarSupportBadge', 'sidebarAdminSupportBadge'];
    badgeIds.forEach(id => {
      const newBadge = newDoc.getElementById(id);
      const currentBadge = document.getElementById(id);
      if (newBadge && currentBadge) {
        currentBadge.textContent = newBadge.textContent;
        currentBadge.style.display = newBadge.style.display;
      }
    });
  }

  // 6. Execute scripts from the incoming page
  async function executePageScripts(newDoc) {
    // Notify previous page to clean up timers/intervals
    window.dispatchEvent(new CustomEvent('page:beforeunload', { detail: { url: window.location.href } }));

    let scriptContainer = document.getElementById('spaScriptContainer');
    if (!scriptContainer) {
      scriptContainer = document.createElement('div');
      scriptContainer.id = 'spaScriptContainer';
      document.body.appendChild(scriptContainer);
    }
    // Clear old dynamically injected scripts
    scriptContainer.innerHTML = '';

    // Find scripts in the new document that are page-specific (not main.js and not spa_router.js)
    const incomingScripts = Array.from(newDoc.querySelectorAll('script'));
    const scriptsToRun = incomingScripts.filter(s => {
      const src = s.getAttribute('src') || '';
      return !src.includes('main.js') && !src.includes('spa_router.js') && !src.includes('chart.umd.min.js');
    });

    for (const oldScript of scriptsToRun) {
      await new Promise((resolve) => {
        const s = document.createElement('script');
        if (oldScript.id) s.id = oldScript.id;
        if (oldScript.type) s.type = oldScript.type;

        if (oldScript.src) {
          s.src = oldScript.src;
          s.onload = () => resolve();
          s.onerror = () => resolve();
          scriptContainer.appendChild(s);
        } else {
          s.textContent = oldScript.textContent;
          scriptContainer.appendChild(s);
          resolve();
        }
      });
    }

    // Dispatch custom page:loaded event
    window.dispatchEvent(new CustomEvent('page:loaded', { detail: { url: window.location.href } }));
  }

  // 7. Core Navigate Function
  async function navigateTo(url, pushState = true) {
    if (isNavigating && activeAbortController) {
      activeAbortController.abort();
    }

    const targetUrl = new URL(url, window.location.origin);
    const currentUrl = new URL(window.location.href);

    // If same URL including hash, do nothing
    if (targetUrl.href === currentUrl.href) {
      return;
    }

    isNavigating = true;
    startProgress();

    activeAbortController = new AbortController();

    try {
      const response = await fetch(targetUrl.href, {
        signal: activeAbortController.signal,
        headers: {
          'X-Requested-With': 'SPA-Router'
        }
      });

      // If server redirected to login or another external page
      if (response.redirected && response.url) {
        window.location.href = response.url;
        return;
      }

      if (!response.ok) {
        // Fallback to native navigation on server error
        window.location.href = targetUrl.href;
        return;
      }

      const htmlText = await response.text();
      const parser = new DOMParser();
      const newDoc = parser.parseFromString(htmlText, 'text/html');

      const currentMain = document.querySelector('.main-content');
      const newMain = newDoc.querySelector('.main-content');

      if (!newMain || !currentMain) {
        // Fallback to full reload if template structure differs
        window.location.href = targetUrl.href;
        return;
      }

      // Perform DOM swap (using View Transitions API if supported)
      const applySwap = () => {
        // Update document title
        if (newDoc.title) {
          document.title = newDoc.title;
        }

        // Update body class
        if (newDoc.body && newDoc.body.className) {
          document.body.className = newDoc.body.className;
        }

        // Swap main content
        currentMain.innerHTML = newMain.innerHTML;

        // Update sidebar active link
        updateSidebarActive(targetUrl.pathname);

        // Update sidebar badges
        updateSidebarBadges(newDoc);

        // Scroll to top
        window.scrollTo(0, 0);
        const mainWrapper = document.querySelector('.main-wrapper');
        if (mainWrapper) mainWrapper.scrollTop = 0;
      };

      if (document.startViewTransition) {
        document.startViewTransition(() => {
          applySwap();
        });
      } else {
        applySwap();
      }

      // Update History
      if (pushState) {
        window.history.pushState({ spa: true, url: targetUrl.href }, '', targetUrl.href);
      }

      // Execute new page scripts
      await executePageScripts(newDoc);

    } catch (err) {
      if (err.name !== 'AbortError') {
        console.error('SPA Navigation error, falling back to full reload:', err);
        window.location.href = targetUrl.href;
      }
    } finally {
      isNavigating = false;
      finishProgress();
    }
  }

  // 8. Event Listeners
  document.addEventListener('click', function (e) {
    const anchor = e.target.closest('a');
    if (!anchor) return;

    if (shouldIntercept(anchor)) {
      e.preventDefault();
      navigateTo(anchor.href, true);
    }
  });

  // Handle Browser Back / Forward buttons
  window.addEventListener('popstate', function () {
    navigateTo(window.location.href, false);
  });

  // Initialize progress bar on boot
  document.addEventListener('DOMContentLoaded', initProgressBar);

  // Expose helper to window for programmatic navigation
  window.spaNavigate = navigateTo;

})();
