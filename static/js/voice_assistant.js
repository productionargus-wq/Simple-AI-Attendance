/**
 * ARGUS AI Voice Assistant Engine
 * -------------------------------------------------------------
 * Provides seamless, device-aware voice guidance and announcements:
 * - Mobile Phones / Tablets (Android & iOS): Authentic Tamil Voice (ta-IN)
 * - Desktop PCs (Windows, Mac, Linux): Clear Native English Voice (en-US)
 *
 * Persists user preference via localStorage ('argus_voice_assist').
 */

(function (window) {
  'use strict';

  function isMobileDevice() {
    const ua = navigator.userAgent || '';
    const mobileRegex = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile/i;
    const hasTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    return mobileRegex.test(ua) || (hasTouch && window.innerWidth <= 1024);
  }

  class ArgusVoiceAssistant {
    constructor() {
      this.synth = window.speechSynthesis || null;
      this.isMobile = isMobileDevice();
      this.tamilVoice = null;
      this.englishVoice = null;
      this.activeServerAudio = null;
      this.tamilRate = 1.45;
      this.isVoiceEnabled = localStorage.getItem('argus_voice_assist') !== 'false';
      this.lastGuidanceTime = 0;
      this.lastGuidanceText = '';
      this.boundButtons = [];

      this.init();
    }

    init() {
      if (this.synth) {
        this.refreshVoices();
        if (typeof this.synth.onvoiceschanged !== 'undefined') {
          this.synth.onvoiceschanged = () => this.refreshVoices();
        }
      }

      // Proactively unlock AudioContext / SpeechSynthesis on first user tap/click
      const unlockHandler = () => {
        this.unlockAudio();
        window.removeEventListener('click', unlockHandler);
        window.removeEventListener('touchstart', unlockHandler);
      };
      window.addEventListener('click', unlockHandler, { passive: true, once: true });
      window.addEventListener('touchstart', unlockHandler, { passive: true, once: true });
    }

    refreshVoices() {
      if (!this.synth) return;
      const voices = this.synth.getVoices();
      if (!voices || voices.length === 0) return;

      // 1. Mobile Tamil Voice Resolution
      let foundTa = voices.find(v => v.lang === 'ta-IN' || v.lang === 'ta_IN');
      if (!foundTa) {
        foundTa = voices.find(v => v.lang && v.lang.toLowerCase().startsWith('ta'));
      }
      if (!foundTa) {
        foundTa = voices.find(v => {
          const n = (v.name || '').toLowerCase();
          return n.includes('tamil') || n.includes('தமிழ்') || n.includes('valluvar') || n.includes('pallavi');
        });
      }
      this.tamilVoice = foundTa || null;

      // 2. Desktop English Voice Resolution
      let foundEn = voices.find(v => {
        const n = (v.name || '').toLowerCase();
        return (v.lang === 'en-US' || v.lang === 'en-GB' || v.lang === 'en-IN') &&
          (n.includes('natural') || n.includes('david') || n.includes('zira') || n.includes('google') || n.includes('samantha'));
      });
      if (!foundEn) {
        foundEn = voices.find(v => v.lang === 'en-US' || v.lang === 'en-GB' || v.lang === 'en-IN');
      }
      if (!foundEn) {
        foundEn = voices.find(v => v.lang && v.lang.toLowerCase().startsWith('en'));
      }
      this.englishVoice = foundEn || voices[0] || null;
    }

    unlockAudio() {
      if (!this.synth) return;
      try {
        if (this.synth.paused) {
          this.synth.resume();
        }
      } catch (e) { }
    }

    setEnabled(enabled) {
      this.isVoiceEnabled = Boolean(enabled);
      localStorage.setItem('argus_voice_assist', this.isVoiceEnabled ? 'true' : 'false');
      if (!this.isVoiceEnabled) {
        this.cancel();
      }
      this.updateBoundToggles();
    }

    cancel() {
      if (this.synth) {
        try {
          this.synth.cancel();
        } catch (e) { }
      }
      if (this.activeServerAudio) {
        try {
          this.activeServerAudio.pause();
          this.activeServerAudio.currentTime = 0;
        } catch (e) { }
        this.activeServerAudio = null;
      }
    }

    playServerAudio(text) {
      if (!text) return;
      this.cancel();
      try {
        const audio = new Audio('/api/voice/tamil-tts?text=' + encodeURIComponent(text) + '&lang=ta');
        audio.playbackRate = this.tamilRate || 1.45;
        this.activeServerAudio = audio;
        audio.play().catch(e => {
          console.warn('Server TTS playback notice:', e);
        });
      } catch (e) { }
    }

    toggle() {
      const now = Date.now();
      if (this._lastToggleTime && (now - this._lastToggleTime < 350)) {
        return this.isVoiceEnabled;
      }
      this._lastToggleTime = now;

      const newState = !this.isVoiceEnabled;
      this.setEnabled(newState);
      if (newState) {
        this.unlockAudio();
        this.speak({
          tamil: 'குரல் உதவி இயக்கப்பட்டது.',
          english: 'Audio voice assistant enabled.'
        }, { interrupt: true, force: true });
      }
      return this.isVoiceEnabled;
    }

    speakDual(content, options = {}) {
      if (!content) return;
      const payload = {
        english: content.english || content.en || '',
        tamil: content.tamil || content.ta || ''
      };
      this.speak(payload, options);
    }

    speak(content, options = {}) {
      if ((!this.isVoiceEnabled && !options.force) || !content) return;

      let targetText = '';
      if (typeof content === 'object') {
        targetText = this.isMobile
          ? (content.tamil || content.ta || content.english || content.en || '')
          : (content.english || content.en || content.tamil || content.ta || '');
      } else {
        targetText = String(content);
      }
      if (!targetText) return;

      const interrupt = options.interrupt || false;
      const isGuidance = options.isGuidance || false;

      if (interrupt) {
        this.cancel();
      } else if (this.synth && this.synth.speaking && !isGuidance) {
        return;
      }

      if (isGuidance) {
        const now = Date.now();
        if (now - this.lastGuidanceTime < 3500) return;
        if (targetText === this.lastGuidanceText && now - this.lastGuidanceTime < 6000) return;
        this.lastGuidanceTime = now;
        this.lastGuidanceText = targetText;
      }

      // DESKTOP: Native English speech synthesis
      if (!this.isMobile) {
        if (this.synth) {
          try {
            this.cancel();
            this.unlockAudio();
            if (!this.englishVoice) {
              this.refreshVoices();
            }
            const utter = new SpeechSynthesisUtterance(targetText);
            if (this.englishVoice) utter.voice = this.englishVoice;
            utter.lang = (this.englishVoice && this.englishVoice.lang) || 'en-US';
            utter.rate = options.rate || 1.0;
            utter.pitch = options.pitch || 1.0;
            utter.volume = 1.0;
            // Prevent Chrome utterance garbage collection
            window._activeSpeechUtterance = utter;
            utter.onend = () => { window._activeSpeechUtterance = null; };
            utter.onerror = () => { window._activeSpeechUtterance = null; };
            this.synth.speak(utter);
            return;
          } catch (err) {
            console.warn('Desktop SpeechSynthesis error:', err);
          }
        }
        return;
      }

      // MOBILE: Authentic Tamil speech synthesis
      if (this.tamilVoice && this.synth) {
        try {
          this.cancel();
          this.unlockAudio();
          const utter = new SpeechSynthesisUtterance(targetText);
          utter.voice = this.tamilVoice;
          utter.lang = this.tamilVoice.lang || 'ta-IN';
          utter.rate = options.rate || this.tamilRate || 1.45;
          utter.pitch = options.pitch || 1.0;
          utter.volume = 1.0;
          window._activeSpeechUtterance = utter;
          utter.onend = () => { window._activeSpeechUtterance = null; };
          utter.onerror = () => { window._activeSpeechUtterance = null; };
          this.synth.speak(utter);
          return;
        } catch (err) {
          console.warn('Mobile Tamil SpeechSynthesis error, using server fallback:', err);
        }
      }

      // Mobile Fallback: Server-side streaming Tamil TTS
      this.playServerAudio(targetText);
    }

    speakGuidance(content) {
      this.speak(content, { isGuidance: true, rate: this.isMobile ? (this.tamilRate || 1.45) : 1.0 });
    }

    // Format standard time into natural spoken Tamil
    toTamilTime(timeStr) {
      if (!timeStr) return '';
      const match = String(timeStr).match(/(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?/i);
      if (!match) return timeStr;
      let h = parseInt(match[1], 10);
      const m = parseInt(match[2], 10);
      const ampm = (match[3] || '').toUpperCase();

      let period = 'காலை';
      if (ampm === 'PM') {
        period = (h === 12 || h < 4) ? 'மதியம்' : 'மாலை';
      } else if (ampm === 'AM' && (h === 12 || h < 4)) {
        period = 'அதிகாலை';
      }
      const minText = m > 0 ? ` ${m} நிமிடம்` : '';
      return `${period} ${h} மணி${minText}`;
    }

    // Format standard time for natural spoken English
    toEnglishTime(timeStr) {
      if (!timeStr) return '';
      const match = String(timeStr).match(/(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?/i);
      if (!match) return timeStr;
      let h = parseInt(match[1], 10);
      const m = parseInt(match[2], 10);
      const ampm = (match[3] || '').toUpperCase();
      const minStr = m < 10 ? `0${m}` : `${m}`;
      return `${h}:${minStr} ${ampm}`;
    }

    announcePunchIn(empName, punchTime) {
      const timeTa = this.toTamilTime(punchTime);
      const timeEn = this.toEnglishTime(punchTime);
      this.speak({
        tamil: `நன்றி ${empName}! உங்கள் வருகை பதிவாகியது. நேரம் ${timeTa}.`,
        english: `Thank you, ${empName}! Your punch in is recorded at ${timeEn}.`
      }, { interrupt: true, rate: this.isMobile ? (this.tamilRate || 1.45) : 1.0 });
    }

    announcePunchOut(empName, punchTime) {
      const timeTa = this.toTamilTime(punchTime);
      const timeEn = this.toEnglishTime(punchTime);
      this.speak({
        tamil: `நன்றி ${empName}! பணி நிறைவு நேரம் பதிவானது. நேரம் ${timeTa}.`,
        english: `Thank you, ${empName}! Your punch out is recorded at ${timeEn}.`
      }, { interrupt: true, rate: this.isMobile ? (this.tamilRate || 1.45) : 1.0 });
    }

    announceAlreadyPunched(empName) {
      this.speak({
        tamil: `${empName}, உங்கள் வருகை ஏற்கனவே பதிவாகியுள்ளது.`,
        english: `${empName}, your attendance is already marked.`
      }, { interrupt: true, rate: this.isMobile ? (this.tamilRate || 1.45) : 1.0 });
    }

    announceGeofenceWarning(locationName) {
      const locTa = locationName ? ` (${locationName})` : '';
      const locEn = locationName ? ` at ${locationName}` : '';
      this.speak({
        tamil: `எச்சரிக்கை! நீங்கள் அனுமதிக்கப்பட்ட எல்லைக்கு வெளியே உள்ளீர்கள்${locTa}.`,
        english: `Warning: You are outside your assigned work location${locEn}.`
      }, { interrupt: true, rate: this.isMobile ? (this.tamilRate || 1.45) : 1.0 });
    }

    announceSuccess(tamilText, englishText) {
      this.speak({
        tamil: tamilText || 'வெற்றிகரமாக பதிவு செய்யப்பட்டது.',
        english: englishText || 'Saved and recorded successfully.'
      }, { interrupt: true });
    }

    announceError(tamilText, englishText) {
      this.speak({
        tamil: tamilText || 'செயல்பாட்டில் பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்.',
        english: englishText || 'An error occurred. Please try again.'
      }, { interrupt: true });
    }

    announceWarning(tamilText, englishText) {
      this.speak({
        tamil: tamilText,
        english: englishText
      }, { interrupt: true });
    }

    // Bind a standardized Audio On/Off toggle button
    bindToggle(btn, icon, label) {
      const btnEl = typeof btn === 'string' ? document.getElementById(btn) : btn;
      if (!btnEl) {
        return;
      }

      let iconEl = typeof icon === 'string' ? document.getElementById(icon) : icon;
      let labelEl = typeof label === 'string' ? document.getElementById(label) : label;

      if (!iconEl) {
        iconEl = btnEl.querySelector('.voice-icon') || btnEl.querySelector('[id*="Icon"]') || btnEl.querySelector('[id*="icon"]');
      }
      if (!labelEl) {
        labelEl = btnEl.querySelector('.voice-text') || btnEl.querySelector('.voice-label') || btnEl.querySelector('[id*="Label"]') || btnEl.querySelector('[id*="label"]');
      }

      const toggleObj = { btn: btnEl, icon: iconEl, label: labelEl };

      // Remove any existing binding for this element to prevent duplicates
      this.boundButtons = this.boundButtons.filter(t => t.btn !== btnEl);
      this.boundButtons.push(toggleObj);
      this.renderToggle(toggleObj);

      if (!btnEl._hasVoiceClickListener) {
        btnEl._hasVoiceClickListener = true;
        btnEl.addEventListener('click', (e) => {
          if (e && e.preventDefault) e.preventDefault();
          this.toggle();
        });
      }
    }

    renderToggle(t) {
      if (!t || !t.btn || !t.btn.classList) return;
      const iconEl = t.icon || t.btn.querySelector('.voice-icon') || t.btn.querySelector('[id*="Icon"]') || t.btn.querySelector('[id*="icon"]');
      const labelEl = t.label || t.btn.querySelector('.voice-text') || t.btn.querySelector('.voice-label') || t.btn.querySelector('[id*="Label"]') || t.btn.querySelector('[id*="label"]');

      if (this.isVoiceEnabled) {
        t.btn.classList.add('active');
        t.btn.setAttribute('aria-pressed', 'true');
        t.btn.setAttribute('title', 'Voice audio is ON (click to mute)');
        t.btn.style.borderColor = '#93c5fd';
        t.btn.style.color = '#1d4ed8';
        t.btn.style.background = '#eff6ff';
        if (iconEl) iconEl.textContent = '🔊';
        if (labelEl) labelEl.textContent = 'Audio: On';
        if (!labelEl && !iconEl) t.btn.textContent = '🔊 Audio: On';
      } else {
        t.btn.classList.remove('active');
        t.btn.setAttribute('aria-pressed', 'false');
        t.btn.setAttribute('title', 'Voice audio is OFF (click to turn on)');
        t.btn.style.borderColor = '#cbd5e1';
        t.btn.style.color = '#64748b';
        t.btn.style.background = '#f8fafc';
        if (iconEl) iconEl.textContent = '🔇';
        if (labelEl) labelEl.textContent = 'Audio: Off';
        if (!labelEl && !iconEl) t.btn.textContent = '🔇 Audio: Off';
      }
    }

    updateBoundToggles() {
      // Clean up disconnected buttons from memory
      this.boundButtons = this.boundButtons.filter(t => t.btn && document.contains(t.btn));
      this.boundButtons.forEach(t => this.renderToggle(t));
    }

    /**
     * Attach field-by-field voice guidance to form inputs/selects inside a modal or container.
     * Guidance triggers on 'focus' (placing cursor in field).
     * Strictly anti-looping:
     * - Does NOT trigger on typing (input/keyup/keydown).
     * - Speaks at most once per field per modal open session.
     * - Debounced (minimum 2.2s between consecutive field prompts).
     *
     * @param {string|HTMLElement} container - Modal container or form element/selector
     * @param {Object} guidanceRules - Map of CSS selector or element ID to { english: '...', tamil: '...' }
     */
    attachFormGuidance(container, guidanceRules = {}) {
      const containerEl = typeof container === 'string' ? document.querySelector(container) : container;
      if (!containerEl) return;

      if (!containerEl._guidedFieldsSet) {
        containerEl._guidedFieldsSet = new Set();
      }

      // Reset session cache when modal close buttons or cancel buttons are clicked
      const closeButtons = containerEl.querySelectorAll('.modal-close-btn, .btn-reset, [data-modal-close], [id*="close"], [id*="Cancel"]');
      closeButtons.forEach(btn => {
        if (!btn._hasVoiceResetListener) {
          btn._hasVoiceResetListener = true;
          btn.addEventListener('click', () => {
            containerEl._guidedFieldsSet.clear();
          });
        }
      });

      // Use focusin delegation for seamless dynamic element support and robust capture
      containerEl._guidanceRules = containerEl._guidanceRules || {};
      Object.assign(containerEl._guidanceRules, guidanceRules);

      if (!containerEl._hasFormGuidanceFocusin) {
        containerEl._hasFormGuidanceFocusin = true;

        containerEl.addEventListener('focusin', (e) => {
          if (!this.isVoiceEnabled) return;
          const target = e.target;
          if (!target || !target.matches) return;

          const rules = containerEl._guidanceRules || {};
          let matchedRule = null;
          let fieldKey = null;

          for (const selector of Object.keys(rules)) {
            const cleanSelector = (selector.startsWith('#') || selector.startsWith('.'))
              ? selector
              : `#${selector}, [name="${selector}"]`;

            if (target.matches(cleanSelector)) {
              matchedRule = rules[selector];
              fieldKey = target.id ? `#${target.id}` : (target.name ? `[name="${target.name}"]` : selector);
              break;
            }
          }

          if (!matchedRule || !fieldKey) return;

          // Check if already guided in this modal session (Anti-looping)
          if (containerEl._guidedFieldsSet.has(fieldKey)) {
            return;
          }

          // Cooldown check (prevent rapid tab jumps from overlapping speech)
          const now = Date.now();
          if (this._lastFieldGuidanceTime && (now - this._lastFieldGuidanceTime < 2200)) {
            return;
          }

          containerEl._guidedFieldsSet.add(fieldKey);
          this._lastFieldGuidanceTime = now;

          this.speakDual({
            english: matchedRule.english || matchedRule.en || '',
            tamil: matchedRule.tamil || matchedRule.ta || ''
          }, { interrupt: true });
        });
      }
    }

    /**
     * Manually clear guided fields session cache for a modal container.
     */
    resetFormGuidance(container) {
      const containerEl = typeof container === 'string' ? document.querySelector(container) : container;
      if (containerEl && containerEl._guidedFieldsSet) {
        containerEl._guidedFieldsSet.clear();
      }
    }
  }

  // Expose singleton instance globally
  window.ArgusVoice = new ArgusVoiceAssistant();
  window.tamilVoice = window.ArgusVoice;

})(window);
