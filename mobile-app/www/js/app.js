/**
 * Argus Attendance Intelligence Mobile App Bootstrap & Navigation
 * Enforces:
 * 1. Animated Splashscreen (using 2nd brand lockup image)
 * 2. Kiosk Terminal connected to backend attendance punching
 * 3. Single Login Button ("Employee Login") -> Employee-only UI
 */
(function (window) {
  'use strict';

  var currentView = 'kiosk';
  var kioskTerminal = null;
  var currentEmployee = null;
  var currentCompany = null;

  function showView(viewName) {
    currentView = viewName;
    ['kioskView', 'loginView', 'portalView'].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.classList.remove('active');
    });
    if (viewName === 'login') {
      if (kioskTerminal && kioskTerminal.isCameraRunning) kioskTerminal.stopCamera();
      if (window.ArgusEmployeePortal) window.ArgusEmployeePortal.stopCamera();
      document.getElementById('loginView').classList.add('active');
    } else if (viewName === 'portal') {
      if (!currentEmployee) {
        showView('login');
        return;
      }
      if (kioskTerminal && kioskTerminal.isCameraRunning) kioskTerminal.stopCamera();
      document.getElementById('portalView').classList.add('active');
    } else {
      if (window.ArgusEmployeePortal) window.ArgusEmployeePortal.stopCamera();
      document.getElementById('kioskView').classList.add('active');
    }
    updateHeaderNav();
  }

  function updateHeaderNav() {
    var btnLogin = document.getElementById('btnHeaderEmployeeLogin');
    var btnPortal = document.getElementById('btnHeaderMyPortal');
    if (currentEmployee) {
      if (btnLogin) btnLogin.style.display = 'none';
      if (btnPortal) btnPortal.style.display = 'inline-flex';
    } else {
      if (btnLogin) btnLogin.style.display = 'inline-flex';
      if (btnPortal) btnPortal.style.display = 'none';
    }
  }

  function startClocks() {
    var months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    function tick() {
      var now = new Date();
      var rawH = now.getHours();
      var ap = rawH >= 12 ? 'PM' : 'AM';
      var h12 = String(rawH % 12 || 12).padStart(2, '0');
      var min = String(now.getMinutes()).padStart(2, '0');
      var sec = String(now.getSeconds()).padStart(2, '0');

      var dEl = document.getElementById('liveDate');
      var tEl = document.getElementById('liveTime');
      if (dEl) dEl.textContent = now.getDate() + ' ' + months[now.getMonth()] + ' ' + now.getFullYear();
      if (tEl) tEl.textContent = h12 + ':' + min + ':' + sec + ' ' + ap;

      var pClock = document.getElementById('portalLiveClock');
      if (pClock) {
        pClock.textContent = String(now.getDate()).padStart(2, '0') + '/' +
          String(now.getMonth() + 1).padStart(2, '0') + '/' + now.getFullYear() + ' ' +
          h12 + ':' + min + ':' + sec + ' ' + ap;
      }
    }
    tick();
    setInterval(tick, 1000);
  }

  function dismissSplash() {
    var splash = document.getElementById('appSplashScreen');
    if (splash && !splash.classList.contains('splash-hidden')) {
      splash.classList.add('splash-hidden');
      setTimeout(function () { splash.style.display = 'none'; }, 480);
    }
  }

  function setLoginError(msg) {
    var box = document.getElementById('loginErrorBox');
    if (!box) return;
    if (msg) {
      box.textContent = msg;
      box.style.display = 'block';
    } else {
      box.textContent = '';
      box.style.display = 'none';
    }
  }

  function applyAuthenticatedEmployee(employee, company) {
    currentEmployee = employee;
    currentCompany = company || {};
    if (window.ArgusEmployeePortal) {
      window.ArgusEmployeePortal.render(employee, company);
    }
    showView('portal');
  }

  async function restoreEmployeeSession() {
    var token = window.ArgusConfig.getToken();
    if (!token) return false;
    try {
      var res = await window.ArgusConfig.apiFetch('/api/mobile/auth/restore-session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: token })
      });
      var data = await res.json();
      if (res.ok && data && data.success && data.role === 'employee' && data.employee) {
        applyAuthenticatedEmployee(data.employee, data.company);
        return true;
      }
      window.ArgusConfig.clearToken();
    } catch (e) {}
    return false;
  }

  async function loadKioskConfig() {
    var cid = window.ArgusConfig.getSavedCompanyId();
    var q = cid ? '?company_id=' + encodeURIComponent(cid) : '';
    try {
      var res = await window.ArgusConfig.apiFetch('/api/kiosk/config' + q, { cache: 'no-store' });
      var cfg = await res.json();
      if (cfg && kioskTerminal) {
        kioskTerminal.setCompanyConfig(cfg.company_id || cid, cfg.modules || {});
        var badge = document.getElementById('kioskCompanyBadge');
        if (badge && cfg.company_name && cfg.company_name.toUpperCase() !== 'ARGUS CNC™') {
          badge.textContent = '🏢 ' + cfg.company_name;
          badge.style.display = 'inline-block';
        }
      }
    } catch (e) {}
  }

  async function handleGoogleLogin() {
    setLoginError('');
    var oauthUrl = window.ArgusConfig.apiUrl('/auth/google/login?type=employee&mobile=1');
    try {
      var browserPlugin = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Browser;
      if (browserPlugin && typeof browserPlugin.open === 'function') {
        await browserPlugin.open({ url: oauthUrl });
        return;
      }
    } catch (e) {}
    window.location.href = oauthUrl;
  }

  async function handleAuthCallbackUrl(url) {
    if (!url || url.indexOf('auth/callback') === -1) return;
    try {
      var browserPlugin = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Browser;
      if (browserPlugin && typeof browserPlugin.close === 'function') {
        browserPlugin.close().catch(function () {});
      }
    } catch (e) {}

    try {
      var qIdx = url.indexOf('?');
      if (qIdx === -1) return;
      var params = new URLSearchParams(url.slice(qIdx + 1));
      var err = params.get('error');
      var code = params.get('code');
      var tok = params.get('token');
      if (err) {
        showView('login');
        setLoginError(err);
        return;
      }
      if (code) {
        var exRes = await window.ArgusConfig.apiFetch('/api/mobile/auth/exchange-code', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code: code })
        });
        var exData = await exRes.json().catch(function () { return {}; });
        if (exRes.ok && exData && exData.success && exData.token) {
          window.ArgusConfig.setToken(exData.token);
          if (exData.employee) {
            enterPortal(exData.employee, exData.company);
            return;
          }
          var okEx = await restoreEmployeeSession();
          if (okEx) return;
        }
        showView('login');
        setLoginError((exData && exData.message) || 'Authorization code expired. Please sign in again.');
        return;
      }
      if (tok) {
        window.ArgusConfig.setToken(tok);
        var ok = await restoreEmployeeSession();
        if (!ok) {
          showView('login');
          setLoginError('Unable to verify employee session. Only registered employees can sign in.');
        }
      }
    } catch (e) {}
  }

  async function handleLogout() {
    try {
      await window.ArgusConfig.apiFetch('/api/mobile/logout', { method: 'POST' });
    } catch (e) {}
    window.ArgusConfig.clearToken();
    currentEmployee = null;
    currentCompany = null;
    showView('kiosk');
  }

  document.addEventListener('DOMContentLoaded', async function () {
    startClocks();

    kioskTerminal = new window.ArgusBiometricTerminal({
      mode: 'kiosk',
      elements: {
        video: document.getElementById('cameraFeed'),
        canvas: document.getElementById('captureCanvas'),
        cameraOverlay: document.getElementById('cameraOverlay'),
        faceReticle: document.getElementById('faceReticle'),
        btnToggleCamera: document.getElementById('btnToggleCamera'),
        btnToggleCameraText: document.getElementById('btnToggleCameraText'),
        btnMark: document.getElementById('btnMarkAttendance'),
        btnMarkText: document.getElementById('btnMarkAttendanceText'),
        punchContainer: document.getElementById('punchDetailContainer'),
        btnHandsFree: document.getElementById('btnToggleHandsFree'),
        handsFreeLabel: document.getElementById('handsfreeToggleLabel'),
        btnSensitivity: document.getElementById('btnToggleSensitivity'),
        sensitivityLabel: document.getElementById('sensitivityLabel'),
        blinkHudOverlay: document.getElementById('blinkHudOverlay'),
        blinkHudPill: document.getElementById('blinkHudPill'),
        blinkHudIcon: document.getElementById('blinkHudIcon'),
        blinkHudText: document.getElementById('blinkHudText'),
        blinkHudDots: document.getElementById('blinkHudDots'),
        blinkDot1: document.getElementById('blinkDot1'),
        blinkDot2: document.getElementById('blinkDot2'),
        blinkEyeState: document.getElementById('blinkEyeState')
      }
    });

    // Voice & Language Toggles
    if (window.ArgusVoice) {
      var btnTermLang = document.getElementById('btnTerminalLangToggle');
      var btnPortalLang = document.getElementById('mobileGlobalLangBtn');
      if (btnTermLang) window.ArgusVoice.bindLangButton(btnTermLang);
      if (btnPortalLang) window.ArgusVoice.bindLangButton(btnPortalLang);

      var syncVoiceBtns = function () {
        var en = window.ArgusVoice.isVoiceEnabled;
        [['btnToggleVoice', 'voiceToggleIcon', 'voiceToggleLabel'], ['btnPortalToggleVoice', 'portalVoiceToggleIcon', 'portalVoiceToggleLabel']].forEach(function (ids) {
          var b = document.getElementById(ids[0]);
          var ic = document.getElementById(ids[1]);
          var lb = document.getElementById(ids[2]);
          if (!b) return;
          b.classList.toggle('active', en);
          if (ic) ic.textContent = en ? '🔊' : '🔇';
          if (lb) lb.textContent = en ? 'Audio: On' : 'Audio: Off';
        });
      };
      syncVoiceBtns();
      ['btnToggleVoice', 'btnPortalToggleVoice'].forEach(function (id) {
        var b = document.getElementById(id);
        if (b) {
          b.addEventListener('click', function () {
            window.ArgusVoice.setEnabled(!window.ArgusVoice.isVoiceEnabled);
            syncVoiceBtns();
            if (window.ArgusVoice.isVoiceEnabled) {
              window.ArgusVoice.unlockAudio();
              window.ArgusVoice.speak({ tamil: 'குரல் உதவி இயக்கப்பட்டது.', english: 'Voice assistant enabled.' }, { interrupt: true });
            }
          });
        }
      });
    }

    // Navigation: Single Employee Login Button + Portal Switchers
    var btnHeaderLogin = document.getElementById('btnHeaderEmployeeLogin');
    var btnHeaderMyPortal = document.getElementById('btnHeaderMyPortal');
    var btnBackKiosk = document.getElementById('btnBackToKiosk');
    var btnLogout = document.getElementById('btnPortalLogout');
    var btnGoogle = document.getElementById('btnEmployeeGoogleLogin');

    if (btnHeaderLogin) btnHeaderLogin.addEventListener('click', function () { setLoginError(''); showView('login'); });
    if (btnHeaderMyPortal) btnHeaderMyPortal.addEventListener('click', function () { showView('portal'); });
    if (btnBackKiosk) btnBackKiosk.addEventListener('click', function () { showView('kiosk'); });
    if (btnLogout) btnLogout.addEventListener('click', handleLogout);
    if (btnGoogle) btnGoogle.addEventListener('click', handleGoogleLogin);

    // Password Visibility Toggle on Employee Login
    var togglePass = document.getElementById('toggleLoginPassBtn');
    var passInp = document.getElementById('loginPassword');
    if (togglePass && passInp) {
      togglePass.addEventListener('click', function () {
        passInp.type = passInp.type === 'password' ? 'text' : 'password';
      });
    }

    // Employee Email/Password Login Submit
    var loginForm = document.getElementById('employeeLoginForm');
    if (loginForm) {
      loginForm.addEventListener('submit', async function (e) {
        e.preventDefault();
        setLoginError('');
        var email = (document.getElementById('loginEmail').value || '').trim();
        var password = (document.getElementById('loginPassword').value || '').trim();
        var submitBtn = document.getElementById('btnEmployeeSignIn');
        if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'SIGNING IN...'; }
        try {
          var res = await window.ArgusConfig.apiFetch('/api/mobile/employee/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: email, password: password })
          });
          var data = await res.json().catch(function () { return {}; });
          if (res.ok && data && data.success && data.token && data.role === 'employee') {
            window.ArgusConfig.setToken(data.token);
            applyAuthenticatedEmployee(data.employee, data.company);
          } else if (res.status === 404) {
            setLoginError('Mobile API endpoint (/api/mobile/employee/login) is not deployed on the server yet. Please deploy the updated app.py.');
          } else {
            setLoginError((data && data.message) || 'Invalid credentials or unauthorized account.');
          }
        } catch (err) {
          setLoginError('Unable to reach server. Please check your internet connection.');
        } finally {
          if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'SIGN IN'; }
        }
      });
    }

    // Capacitor Deep-Link & Hardware Back Button
    try {
      var AppPlugin = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.App;
      if (AppPlugin && typeof AppPlugin.addListener === 'function') {
        AppPlugin.addListener('appUrlOpen', function (ev) {
          if (ev && ev.url) handleAuthCallbackUrl(ev.url);
        });
        AppPlugin.addListener('appStateChange', function (state) {
          if (state && state.isActive && !currentEmployee && window.ArgusConfig.getToken()) {
            restoreEmployeeSession();
          }
        });
        if (typeof AppPlugin.getLaunchUrl === 'function') {
          AppPlugin.getLaunchUrl().then(function (launch) {
            if (launch && launch.url) handleAuthCallbackUrl(launch.url);
          }).catch(function () {});
        }
        AppPlugin.addListener('backButton', function () {
          if (currentView === 'login') showView('kiosk');
          else if (currentView === 'portal') showView('kiosk');
        });
      }
      var SplashPlugin = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.SplashScreen;
      if (SplashPlugin && typeof SplashPlugin.hide === 'function') {
        SplashPlugin.hide().catch(function () {});
      }
    } catch (e) {}

    var splashStatus = document.getElementById('splashStatusText');
    if (splashStatus) splashStatus.textContent = 'Syncing Kiosk & Employee Session...';

    var minSplashWait = new Promise(function (r) { setTimeout(r, 1550); });
    var restored = false;
    try {
      var results = await Promise.all([loadKioskConfig(), restoreEmployeeSession(), minSplashWait]);
      restored = Boolean(results[1]);
    } catch (e) {
      await minSplashWait;
    }

    if (splashStatus) splashStatus.textContent = 'Ready';
    dismissSplash();

    if (!restored) {
      showView('kiosk');
      setTimeout(function () {
        if (currentView === 'kiosk' && kioskTerminal && !kioskTerminal.isCameraRunning) {
          kioskTerminal.startCamera();
        }
      }, 350);
    }
  });
})(window);
