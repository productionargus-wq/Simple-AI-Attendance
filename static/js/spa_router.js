/**
 * High-Performance SPA Router & Instant Navigation Engine
 * 
 * Features:
 * 1. 0ms Perceived Latency via Hover & Touch Pre-fetching
 * 2. In-Memory Cache with Stale-While-Revalidate (SWR)
 * 3. Idle Pre-loading of popular tabs (requestIdleCallback)
 * 4. DOMContentLoaded polyfill for dynamic page scripts
 * 5. Native View Transitions cross-fade animations
 * 6. Browser History (pushState & popstate) with zero tab reloading
 */

(function () {
  'use strict';

  // 1. DOMContentLoaded Polyfill for dynamically loaded scripts
  const _origAddEventListener = document.addEventListener.bind(document);
  document.addEventListener = function (type, listener, options) {
    if (type === 'DOMContentLoaded' && (document.readyState === 'complete' || document.readyState === 'interactive')) {
      setTimeout(listener, 0);
      return;
    }
    return _origAddEventListener(type, listener, options);
  };

  // State & Caches
  const pageCache = new Map(); // key -> { htmlText, timestamp }
  const inflightFetches = new Map(); // key -> Promise<string>
  const hoverTimers = new Map(); // anchor -> timerId

  const CACHE_MAX_AGE_MS = 60 * 1000;       // 60 seconds max cache lifetime
  const SWR_STALE_AFTER_MS = 25 * 1000;     // After 25 seconds, revalidate in background
  const HOVER_DELAY_MS = 65;                // 65ms hover debounce to avoid accidental swipes

  let isNavigating = false;
  let activeAbortController = null;
  let progressBar = null;
  let progressTimer = null;

  // 2. Slim Top Progress Bar
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
      if (progressBar) progressBar.style.width = '40%';
    }, 10);
    setTimeout(() => {
      if (progressBar && isNavigating) progressBar.style.width = '75%';
    }, 100);
  }

  function finishProgress() {
    if (!progressBar) return;
    progressBar.style.width = '100%';
    progressTimer = setTimeout(() => {
      if (progressBar) {
        progressBar.style.opacity = '0';
        setTimeout(() => {
          if (progressBar) progressBar.style.width = '0%';
        }, 150);
      }
    }, 100);
  }

  // 3. Link Validity Checker
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

    // Exclude logout and file download endpoints
    if (url.pathname === '/logout' || url.pathname.includes('/logout')) return false;
    if (url.pathname.startsWith('/api/') && (url.pathname.includes('/pdf') || url.pathname.includes('/excel') || url.pathname.includes('/download'))) {
      return false;
    }

    return true;
  }

  function getCacheKey(url) {
    const u = new URL(url, window.location.origin);
    return u.pathname + u.search;
  }

  // 4. Pre-fetch Engine (SWR + Background Fetch)
  function prefetch(url) {
    const targetUrl = new URL(url, window.location.origin);
    const key = getCacheKey(targetUrl);
    const currentKey = getCacheKey(window.location.href);

    // Don't prefetch current active page
    if (key === currentKey) return Promise.resolve(null);

    // Check existing fresh cache entry
    const cached = pageCache.get(key);
    const now = Date.now();
    if (cached && (now - cached.timestamp < SWR_STALE_AFTER_MS)) {
      return Promise.resolve(cached.htmlText);
    }

    // Deduplicate in-flight fetch
    if (inflightFetches.has(key)) {
      return inflightFetches.get(key);
    }

    const fetchPromise = fetch(targetUrl.href, {
      headers: {
        'X-Requested-With': 'SPA-Router',
        'Purpose': 'prefetch'
      }
    })
      .then(async (res) => {
        if (res.ok && !res.redirected) {
          const htmlText = await res.text();
          pageCache.set(key, {
            htmlText: htmlText,
            timestamp: Date.now()
          });
          return htmlText;
        }
        return null;
      })
      .catch(() => null)
      .finally(() => {
        inflightFetches.delete(key);
      });

    inflightFetches.set(key, fetchPromise);
    return fetchPromise;
  }

  // 5. Update Sidebar Active State
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

  // 6. Update Sidebar Count Badges from incoming document
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

  // 7. Execute scripts from incoming page
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

    // Find scripts in new document that are page-specific
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

  // 8. Core Navigate Function (with Instant Cache Retrieval)
  async function navigateTo(url, pushState = true) {
    if (isNavigating && activeAbortController) {
      activeAbortController.abort();
    }

    const targetUrl = new URL(url, window.location.origin);
    const currentUrl = new URL(window.location.href);
    const key = getCacheKey(targetUrl);

    // If same URL including hash, do nothing
    if (targetUrl.href === currentUrl.href) {
      return;
    }

    isNavigating = true;
    startProgress();

    activeAbortController = new AbortController();

    try {
      let htmlText = null;
      const cached = pageCache.get(key);
      const now = Date.now();

      // Check if available in RAM cache
      if (cached && (now - cached.timestamp < CACHE_MAX_AGE_MS)) {
        htmlText = cached.htmlText;
        // Stale-While-Revalidate: If older than 25s, fetch fresh copy in background silently
        if (now - cached.timestamp > SWR_STALE_AFTER_MS) {
          prefetch(targetUrl.href);
        }
      } else if (inflightFetches.has(key)) {
        // Reuse ongoing hover prefetch
        htmlText = await inflightFetches.get(key);
      }

      // If not cached, fetch over network
      if (!htmlText) {
        const response = await fetch(targetUrl.href, {
          signal: activeAbortController.signal,
          headers: {
            'X-Requested-With': 'SPA-Router'
          }
        });

        if (response.redirected && response.url) {
          window.location.href = response.url;
          return;
        }

        if (!response.ok) {
          window.location.href = targetUrl.href;
          return;
        }

        htmlText = await response.text();
        // Save to cache
        pageCache.set(key, {
          htmlText: htmlText,
          timestamp: Date.now()
        });
      }

      const parser = new DOMParser();
      const newDoc = parser.parseFromString(htmlText, 'text/html');

      const currentMain = document.querySelector('.main-content');
      const newMain = newDoc.querySelector('.main-content');

      if (!newMain || !currentMain) {
        window.location.href = targetUrl.href;
        return;
      }

      // Perform DOM swap (using View Transitions API if supported)
      const applySwap = () => {
        if (newDoc.title) {
          document.title = newDoc.title;
        }

        if (newDoc.body && newDoc.body.className) {
          document.body.className = newDoc.body.className;
        }

        // Instant content swap
        currentMain.innerHTML = newMain.innerHTML;

        // Update active sidebar tab
        updateSidebarActive(targetUrl.pathname);

        // Update sidebar counter badges
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

      // Update browser history
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

  // 9. Hover & Touch Pre-fetching Listeners
  // Triggered on mouseover / touchstart so page is ready in RAM before user clicks
  document.addEventListener('mouseover', function (e) {
    const anchor = e.target.closest('a');
    if (!anchor || !shouldIntercept(anchor)) return;

    if (hoverTimers.has(anchor)) return;
    const timer = setTimeout(() => {
      prefetch(anchor.href);
      hoverTimers.delete(anchor);
    }, HOVER_DELAY_MS);
    hoverTimers.set(anchor, timer);
  }, { passive: true });

  document.addEventListener('mouseout', function (e) {
    const anchor = e.target.closest('a');
    if (!anchor) return;
    if (hoverTimers.has(anchor)) {
      clearTimeout(hoverTimers.get(anchor));
      hoverTimers.delete(anchor);
    }
  }, { passive: true });

  document.addEventListener('touchstart', function (e) {
    const anchor = e.target.closest('a');
    if (anchor && shouldIntercept(anchor)) {
      prefetch(anchor.href);
    }
  }, { passive: true });

  // 10. Click Interceptor
  document.addEventListener('click', function (e) {
    const anchor = e.target.closest('a');
    if (!anchor) return;

    if (shouldIntercept(anchor)) {
      e.preventDefault();
      navigateTo(anchor.href, true);
    }
  });

  // 11. Handle Browser Back & Forward buttons
  window.addEventListener('popstate', function () {
    navigateTo(window.location.href, false);
  });

  // 12. Idle Pre-loading: Pre-load common routes when CPU & Network are idle
  function preloadCommonTabs() {
    const commonTabs = ['/dashboard', '/live-report', '/attendance-report', '/employee-details'];
    const idleRunner = window.requestIdleCallback || ((cb) => setTimeout(cb, 1200));

    idleRunner(() => {
      commonTabs.forEach((tab, index) => {
        setTimeout(() => {
          prefetch(tab);
        }, index * 300);
      });
    });
  }

  // 13. Initialize on boot
  document.addEventListener('DOMContentLoaded', () => {
    initProgressBar();
    setTimeout(preloadCommonTabs, 1200);
  });

  // Expose global methods
  window.spaNavigate = navigateTo;
  window.spaPrefetch = prefetch;
  window.spaClearCache = () => pageCache.clear();

})();
