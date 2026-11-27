/**
 * Argus Attendance Intelligence Mobile Configuration
 * Connects standalone Capacitor mobile UI to the Flask backend API.
 */
(function (window) {
  'use strict';

  var DEFAULT_API_BASE = 'https://argusattendanceintelligence.argussoftwares.com';
  var TOKEN_KEY = 'argus_mobile_employee_token';
  var API_BASE_KEY = 'argus_mobile_api_base';
  var COMPANY_ID_KEY = 'argus_kiosk_company_id';

  function sanitizeBase(url) {
    return String(url || '').trim().replace(/\/+$/, '');
  }

  function isAllowedApiBase(url) {
    try {
      var parsed = new URL(sanitizeBase(url));
      var host = (parsed.hostname || '').toLowerCase();
      if (parsed.protocol === 'https:' && (host === 'argussoftwares.com' || host.endsWith('.argussoftwares.com'))) {
        return true;
      }
      if (parsed.protocol === 'http:' && (host === 'localhost' || host === '127.0.0.1')) {
        return true;
      }
    } catch (e) {}
    return false;
  }

  function getApiBase() {
    try {
      var params = new URLSearchParams(window.location.search || '');
      var qBase = params.get('api_base');
      if (qBase && isAllowedApiBase(qBase)) {
        var cleanQ = sanitizeBase(qBase);
        localStorage.setItem(API_BASE_KEY, cleanQ);
        return cleanQ;
      }
      var stored = localStorage.getItem(API_BASE_KEY);
      if (stored && isAllowedApiBase(stored)) {
        return sanitizeBase(stored);
      }
      if (stored) {
        localStorage.removeItem(API_BASE_KEY);
      }
    } catch (e) {}
    return DEFAULT_API_BASE;
  }

  function apiUrl(path) {
    if (!path) return getApiBase();
    if (/^https?:\/\//i.test(path)) return path;
    var p = path.charAt(0) === '/' ? path : '/' + path;
    return getApiBase() + p;
  }

  function getToken() {
    try {
      return (localStorage.getItem(TOKEN_KEY) || '').trim();
    } catch (e) {
      return '';
    }
  }

  function setToken(token) {
    try {
      if (token) {
        localStorage.setItem(TOKEN_KEY, String(token).trim());
      } else {
        localStorage.removeItem(TOKEN_KEY);
      }
    } catch (e) {}
  }

  function clearToken() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch (e) {}
  }

  function getSavedCompanyId() {
    try {
      var params = new URLSearchParams(window.location.search || '');
      var qCid = (params.get('company_id') || '').trim();
      if (qCid && qCid !== 'ALL' && qCid !== 'None') {
        localStorage.setItem(COMPANY_ID_KEY, qCid);
        return qCid;
      }
      return (localStorage.getItem(COMPANY_ID_KEY) || '').trim();
    } catch (e) {
      return '';
    }
  }

  async function apiFetch(path, options) {
    var opts = Object.assign({}, options || {});
    var headers = new Headers(opts.headers || {});
    var token = getToken();
    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', 'Bearer ' + token);
    }
    opts.headers = headers;
    return window.fetch(apiUrl(path), opts);
  }

  function isCapacitorNative() {
    return Boolean(
      window.Capacitor &&
      typeof window.Capacitor.isNativePlatform === 'function' &&
      window.Capacitor.isNativePlatform()
    );
  }

  window.ArgusConfig = {
    DEFAULT_API_BASE: DEFAULT_API_BASE,
    getApiBase: getApiBase,
    apiUrl: apiUrl,
    getToken: getToken,
    setToken: setToken,
    clearToken: clearToken,
    getSavedCompanyId: getSavedCompanyId,
    apiFetch: apiFetch,
    isCapacitorNative: isCapacitorNative
  };
})(window);
