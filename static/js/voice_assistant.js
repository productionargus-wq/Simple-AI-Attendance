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
      } catch (e) {}
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
        } catch (e) {}
      }
      if (this.activeServerAudio) {
        try {
          this.activeServerAudio.pause();
          this.activeServerAudio.currentTime = 0;
        } catch (e) {}
        this.activeServerAudio = null;
      }
    }

    playServerAudio(text) {
      if (!text) return;
      this.cancel();
      try {
        const audio = new Audio('/api/voice/tamil-tts?text=' + encodeURIComponent(text) + '&lang=ta');
        this.activeServerAudio = audio;
        audio.play().catch(e => {
          console.warn('Server TTS playback notice:', e);
        });
      } catch (e) {}
    }

    speak(content, options = {}) {
      if (!this.isVoiceEnabled || !content) return;

      let targetText = '';
      if (typeof content === 'object') {
        targetText = this.isMobile
          ? (content.tamil || content.english || '')
          : (content.english || content.tamil || '');
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
            const utter = new SpeechSynthesisUtterance(targetText);
            if (this.englishVoice) utter.voice = this.englishVoice;
            utter.lang = (this.englishVoice && this.englishVoice.lang) || 'en-US';
            utter.rate = options.rate || 1.0;
            utter.pitch = options.pitch || 1.0;
            utter.volume = 1.0;
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
          const utter = new SpeechSynthesisUtterance(targetText);
          utter.voice = this.tamilVoice;
          utter.lang = this.tamilVoice.lang || 'ta-IN';
          utter.rate = options.rate || 0.95;
          utter.pitch = options.pitch || 1.0;
          utter.volume = 1.0;
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
      this.speak(content, { isGuidance: true, rate: this.isMobile ? 0.98 : 1.0 });
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
      }, { interrupt: true, rate: this.isMobile ? 0.95 : 1.0 });
    }

    announcePunchOut(empName, punchTime) {
      const timeTa = this.toTamilTime(punchTime);
      const timeEn = this.toEnglishTime(punchTime);
      this.speak({
        tamil: `நன்றி ${empName}! பணி நிறைவு நேரம் பதிவானது. நேரம் ${timeTa}.`,
        english: `Thank you, ${empName}! Your punch out is recorded at ${timeEn}.`
      }, { interrupt: true, rate: this.isMobile ? 0.95 : 1.0 });
    }

    announceAlreadyPunched(empName) {
      this.speak({
        tamil: `${empName}, உங்கள் வருகை ஏற்கனவே பதிவாகியுள்ளது.`,
        english: `${empName}, your attendance is already marked.`
      }, { interrupt: true, rate: this.isMobile ? 0.95 : 1.0 });
    }

    announceGeofenceWarning(locationName) {
      const locTa = locationName ? ` (${locationName})` : '';
      const locEn = locationName ? ` at ${locationName}` : '';
      this.speak({
        tamil: `எச்சரிக்கை! நீங்கள் அனுமதிக்கப்பட்ட எல்லைக்கு வெளியே உள்ளீர்கள்${locTa}.`,
        english: `Warning: You are outside your assigned work location${locEn}.`
      }, { interrupt: true, rate: this.isMobile ? 0.95 : 1.0 });
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
    bindToggle(btnEl, iconEl, labelEl) {
      if (!btnEl) return;
      const toggleObj = { btn: btnEl, icon: iconEl, label: labelEl };
      this.boundButtons.push(toggleObj);
      this.renderToggle(toggleObj);

      btnEl.addEventListener('click', () => {
        const newState = !this.isVoiceEnabled;
        this.setEnabled(newState);
        if (newState) {
          this.unlockAudio();
          this.speak({
            tamil: 'குரல் உதவி இயக்கப்பட்டது.',
            english: 'Audio voice assistant enabled.'
          }, { interrupt: true });
        }
      });
    }

    renderToggle(t) {
      if (!t.btn) return;
      if (this.isVoiceEnabled) {
        t.btn.classList.add('active');
        if (t.icon) t.icon.textContent = '🔊';
        if (t.label) t.label.textContent = 'Audio: On';
      } else {
        t.btn.classList.remove('active');
        if (t.icon) t.icon.textContent = '🔇';
        if (t.label) t.label.textContent = 'Audio: Off';
      }
    }

    updateBoundToggles() {
      this.boundButtons.forEach(t => this.renderToggle(t));
    }
  }

  // Expose singleton instance globally
  window.ArgusVoice = new ArgusVoiceAssistant();

})(window);
