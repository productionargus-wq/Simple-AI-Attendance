/**
 * ARGUS Universal Live Closed Captions Engine
 * -------------------------------------------------------------
 * Displays real-time, high-contrast captions whenever the application speaks English voice.
 * Strictly excludes Tamil speech per client accessibility requirements.
 */

(function (window) {
  'use strict';

  const TAMIL_UNICODE_REGEX = /[\u0B80-\u0BFF]/;

  class ArgusCaptionsEngine {
    constructor() {
      this.hudEl = null;
      this.textEl = null;
      this.closeBtn = null;
      this.hideTimer = null;
      this.isDismissedByUser = false;
      this.currentText = '';

      this.init();
    }

    init() {
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => this.injectHUD());
      } else {
        this.injectHUD();
      }

      this.installSpeechSynthesisHooks();
    }

    injectHUD() {
      if (document.getElementById('argusCaptionsHud')) {
        this.hudEl = document.getElementById('argusCaptionsHud');
        this.textEl = this.hudEl.querySelector('.argus-captions-text');
        this.closeBtn = this.hudEl.querySelector('.argus-captions-close');
        return;
      }

      const hud = document.createElement('div');
      hud.id = 'argusCaptionsHud';
      hud.className = 'argus-captions-hud';
      hud.setAttribute('role', 'status');
      hud.setAttribute('aria-live', 'polite');
      hud.innerHTML = `
        <span class="argus-captions-badge">CC</span>
        <div class="argus-captions-equalizer" aria-hidden="true">
          <span></span><span></span><span></span>
        </div>
        <div class="argus-captions-text"></div>
        <button type="button" class="argus-captions-close" title="Dismiss captions" aria-label="Dismiss captions">&times;</button>
      `;

      document.body.appendChild(hud);

      this.hudEl = hud;
      this.textEl = hud.querySelector('.argus-captions-text');
      this.closeBtn = hud.querySelector('.argus-captions-close');

      if (this.closeBtn) {
        this.closeBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          this.dismiss();
        });
      }
    }

    /**
     * Checks if given text is strictly English (not Tamil).
     */
    isEnglish(text, lang = '') {
      if (!text || typeof text !== 'string') return false;
      if (lang && String(lang).toLowerCase().startsWith('ta')) return false;
      // If it contains Tamil Unicode characters, reject
      if (TAMIL_UNICODE_REGEX.test(text)) return false;
      // Check if it contains alphanumeric characters (standard English text)
      return /[a-zA-Z0-9]/.test(text);
    }

    /**
     * Cleans up markdown or system formatting before display.
     */
    cleanText(rawText) {
      if (!rawText) return '';
      return String(rawText)
        .replace(/\*\*(.*?)\*\*/g, '$1')
        .replace(/\*(.*?)\*/g, '$1')
        .replace(/`([^`]+)`/g, '$1')
        .replace(/#{1,6}\s*/g, '')
        .replace(/a\.\s*Explanation:?\s*/gi, '')
        .replace(/b\.\s*Rule\s*\/?\s*criteria:?\s*/gi, '')
        .replace(/\bExplanation:?\s*/gi, '')
        .replace(/\b(?:Rule\s*(?:and|\/|&)?\s*)?Criteria:?\s*/gi, '')
        .replace(/\s+/g, ' ')
        .trim();
    }

    /**
     * Show live caption for English spoken text.
     */
    show(text, options = {}) {
      if (!text) return;
      const lang = options.lang || '';

      // Strictly English only - skip Tamil speech
      if (!this.isEnglish(text, lang)) {
        return;
      }

      if (!this.hudEl) {
        this.injectHUD();
      }
      if (!this.hudEl || !this.textEl) return;

      const formatted = this.cleanText(text);
      if (!formatted) return;

      // Clear any pending dismissal
      if (this.hideTimer) {
        clearTimeout(this.hideTimer);
        this.hideTimer = null;
      }

      this.currentText = formatted;
      this.textEl.textContent = formatted;
      this.isDismissedByUser = false;

      this.hudEl.classList.add('active');
      this.hudEl.classList.add('speaking');
    }

    /**
     * Called when speech finishes - keeps caption readable for 2.5s buffer before smooth fadeout.
     */
    hide(immediate = false) {
      if (!this.hudEl) return;

      this.hudEl.classList.remove('speaking');

      if (this.hideTimer) {
        clearTimeout(this.hideTimer);
        this.hideTimer = null;
      }

      if (immediate) {
        this.hudEl.classList.remove('active');
        this.currentText = '';
        return;
      }

      this.hideTimer = setTimeout(() => {
        if (this.hudEl) {
          this.hudEl.classList.remove('active');
          this.currentText = '';
        }
      }, 2500);
    }

    /**
     * User clicked close button - hide immediately.
     */
    dismiss() {
      this.isDismissedByUser = true;
      this.hide(true);
    }

    /**
     * Universal SpeechSynthesis hook:
     * Intercepts all browser SpeechSynthesis utterances globally.
     */
    installSpeechSynthesisHooks() {
      if (!('speechSynthesis' in window)) return;

      const self = this;
      const originalSpeak = window.speechSynthesis.speak.bind(window.speechSynthesis);
      const originalCancel = window.speechSynthesis.cancel.bind(window.speechSynthesis);

      window.speechSynthesis.speak = function (utterance) {
        if (utterance && utterance.text) {
          const text = utterance.text;
          const lang = utterance.lang || (utterance.voice && utterance.voice.lang) || '';

          if (self.isEnglish(text, lang)) {
            // Show caption immediately on call
            self.show(text, { lang });

            const prevOnStart = utterance.onstart;
            utterance.onstart = function (e) {
              self.show(text, { lang });
              if (typeof prevOnStart === 'function') prevOnStart.call(utterance, e);
            };

            const prevOnEnd = utterance.onend;
            utterance.onend = function (e) {
              self.hide(false);
              if (typeof prevOnEnd === 'function') prevOnEnd.call(utterance, e);
            };

            const prevOnError = utterance.onerror;
            utterance.onerror = function (e) {
              self.hide(false);
              if (typeof prevOnError === 'function') prevOnError.call(utterance, e);
            };
          }
        }
        return originalSpeak(utterance);
      };

      window.speechSynthesis.cancel = function () {
        self.hide(true);
        return originalCancel();
      };
    }
  }

  // Expose singleton globally
  window.ArgusCaptions = new ArgusCaptionsEngine();

})(window);
