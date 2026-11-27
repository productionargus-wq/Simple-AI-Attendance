/**
 * ARGUS Mobile Bilingual AI Voice Assistant (Tamil / English)
 * Priority 1: Native Android TextToSpeech bridge (window.ArgusNativeTTS)
 * Priority 2: Pre-unlocked persistent HTMLAudioElement streaming /api/voice/tamil-tts
 * Priority 3: Web SpeechSynthesis when matching voices exist
 */
(function (window) {
  'use strict';

  var LANG_KEY = 'argus_app_voice_lang';
  var ENABLED_KEY = 'argus_voice_assist';
  var SILENT_WAV = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';

  class MobileVoiceAssistant {
    constructor() {
      this.synth = window.speechSynthesis || null;
      this.tamilVoice = null;
      this.englishVoice = null;
      this.sharedAudio = null;
      this.audioUnlocked = false;
      this.audioCtx = null;
      this.tamilRate = 1.05;
      this.isVoiceEnabled = true;
      try {
        this.isVoiceEnabled = localStorage.getItem(ENABLED_KEY) !== 'false';
      } catch (e) {}
      this.lastGuidanceTime = 0;
      this.lastGuidanceText = '';
      this.boundLangButtons = [];

      if (this.synth) {
        this.refreshVoices();
        if (typeof this.synth.onvoiceschanged !== 'undefined') {
          this.synth.onvoiceschanged = () => this.refreshVoices();
        }
      }

      var unlockOnce = () => {
        this.unlockAudio();
      };
      window.addEventListener('click', unlockOnce, { passive: true, once: true });
      window.addEventListener('touchstart', unlockOnce, { passive: true, once: true });
    }

    refreshVoices() {
      if (!this.synth) return;
      var voices = this.synth.getVoices() || [];
      this.tamilVoice =
        voices.find(v => v.lang === 'ta-IN' || v.lang === 'ta_IN') ||
        voices.find(v => v.lang && v.lang.toLowerCase().startsWith('ta')) ||
        null;
      this.englishVoice =
        voices.find(v => v.lang === 'en-IN' || v.lang === 'en-US' || v.lang === 'en-GB') ||
        voices.find(v => v.lang && v.lang.toLowerCase().startsWith('en')) ||
        null;
    }

    getLanguage() {
      try {
        var saved = localStorage.getItem(LANG_KEY);
        return (saved === 'en' || saved === 'ta') ? saved : 'ta';
      } catch (e) {
        return 'ta';
      }
    }

    setLanguage(lang, silent) {
      var clean = (lang === 'en') ? 'en' : 'ta';
      try { localStorage.setItem(LANG_KEY, clean); } catch (e) {}
      this.updateBoundLangButtons();
      if (!silent) {
        this.unlockAudio();
        this.speak({
          tamil: clean === 'ta' ? 'குரல் உதவி தமிழில் அமைக்கப்பட்டது.' : 'குரல் உதவி ஆங்கிலத்தில் அமைக்கப்பட்டது.',
          english: clean === 'ta' ? 'Voice language set to Tamil.' : 'Voice language set to English.'
        }, { interrupt: true });
      }
      return clean;
    }

    toggleLanguage() {
      return this.setLanguage(this.getLanguage() === 'ta' ? 'en' : 'ta');
    }

    bindLangButton(btn) {
      if (!btn || this.boundLangButtons.indexOf(btn) !== -1) return;
      this.boundLangButtons.push(btn);
      btn.addEventListener('click', () => this.toggleLanguage());
      this.updateBoundLangButtons();
    }

    updateBoundLangButtons() {
      var lang = this.getLanguage();
      this.boundLangButtons.forEach(btn => {
        var lbl = btn.querySelector('.lang-label, #terminalLangLabel');
        if (lbl) {
          lbl.textContent = lang === 'ta' ? 'தமிழ்' : 'English';
        }
        btn.setAttribute('title', lang === 'ta' ? 'Voice Language: Tamil' : 'Voice Language: English');
      });
    }

    setEnabled(enabled) {
      this.isVoiceEnabled = Boolean(enabled);
      try { localStorage.setItem(ENABLED_KEY, String(this.isVoiceEnabled)); } catch (e) {}
      if (!this.isVoiceEnabled) this.cancel();
    }

    unlockAudio() {
      try {
        var Ctx = window.AudioContext || window.webkitAudioContext;
        if (Ctx) {
          if (!this.audioCtx) this.audioCtx = new Ctx();
          if (this.audioCtx.state === 'suspended') {
            this.audioCtx.resume().catch(() => {});
          }
        }
      } catch (e) {}

      try {
        if (!this.sharedAudio) {
          this.sharedAudio = new Audio();
          this.sharedAudio.preload = 'auto';
        }
        if (!this.audioUnlocked) {
          this.sharedAudio.src = SILENT_WAV;
          var p = this.sharedAudio.play();
          if (p && typeof p.then === 'function') {
            p.then(() => {
              this.audioUnlocked = true;
              this.sharedAudio.pause();
            }).catch(() => {});
          }
        }
      } catch (e) {}
    }

    cancel() {
      try {
        if (window.ArgusNativeTTS && typeof window.ArgusNativeTTS.stop === 'function') {
          window.ArgusNativeTTS.stop();
        }
      } catch (e) {}
      try {
        if (this.synth) this.synth.cancel();
      } catch (e) {}
      try {
        if (this.sharedAudio) {
          this.sharedAudio.pause();
          this.sharedAudio.currentTime = 0;
        }
      } catch (e) {}
    }

    speakNative(text, lang, rate) {
      try {
        var nat = window.ArgusNativeTTS;
        if (!nat || typeof nat.isAvailable !== 'function' || !nat.isAvailable()) {
          return false;
        }
        if (typeof nat.isLanguageAvailable === 'function' && !nat.isLanguageAvailable(lang)) {
          return false;
        }
        return Boolean(nat.speak(text, lang, rate));
      } catch (e) {
        return false;
      }
    }

    playServerAudio(text, lang) {
      if (!text || !window.ArgusConfig) return;
      try {
        var url = window.ArgusConfig.apiUrl('/api/voice/tamil-tts?text=' + encodeURIComponent(text) + '&lang=' + encodeURIComponent(lang || 'ta'));
        if (!this.sharedAudio) {
          this.sharedAudio = new Audio();
        }
        this.sharedAudio.pause();
        this.sharedAudio.src = url;
        this.sharedAudio.load();
        var playPromise = this.sharedAudio.play();
        if (playPromise && typeof playPromise.catch === 'function') {
          playPromise.catch(() => {});
        }
      } catch (e) {}
    }

    speak(content, options) {
      if (!this.isVoiceEnabled || !content) return;
      var opts = options || {};
      var lang = this.getLanguage();
      var text = '';
      if (typeof content === 'object') {
        text = lang === 'ta'
          ? (content.tamil || content.ta || content.english || content.en || '')
          : (content.english || content.en || content.tamil || content.ta || '');
      } else {
        text = String(content);
      }
      if (!text) return;

      if (opts.interrupt) {
        this.cancel();
      } else if (this.synth && this.synth.speaking && !opts.isGuidance) {
        return;
      }

      if (opts.isGuidance) {
        var now = Date.now();
        if (now - this.lastGuidanceTime < 3500) return;
        if (text === this.lastGuidanceText && now - this.lastGuidanceTime < 6000) return;
        this.lastGuidanceTime = now;
        this.lastGuidanceText = text;
      }

      var rate = opts.rate || (lang === 'ta' ? this.tamilRate : 1.0);

      // 1. Native Android Hardware TTS (works offline & bypasses WebView silence/autoplay bugs)
      if (this.speakNative(text, lang, rate)) {
        return;
      }

      // 2. Web SpeechSynthesis ONLY when matching voice is genuinely available
      if (this.synth) {
        this.refreshVoices();
        var targetVoice = (lang === 'ta') ? this.tamilVoice : this.englishVoice;
        if (targetVoice) {
          try {
            var utter = new SpeechSynthesisUtterance(text);
            utter.voice = targetVoice;
            utter.lang = targetVoice.lang || (lang === 'ta' ? 'ta-IN' : 'en-US');
            utter.rate = rate;
            this.synth.speak(utter);
            return;
          } catch (e) {}
        }
      }

      // 3. Persistent Unlocked Server Audio Fallback (/api/voice/tamil-tts)
      this.playServerAudio(text, lang);
    }

    speakGuidance(content) {
      this.speak(content, { isGuidance: true });
    }

    toTamilTime(timeStr) {
      var m = String(timeStr || '').match(/(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?/i);
      if (!m) return timeStr || '';
      var h = parseInt(m[1], 10);
      var min = parseInt(m[2], 10);
      var ap = (m[3] || '').toUpperCase();
      var period = 'காலை';
      if (ap === 'PM') period = (h === 12 || h < 4) ? 'மதியம்' : 'மாலை';
      else if (ap === 'AM' && (h === 12 || h < 4)) period = 'அதிகாலை';
      return period + ' ' + h + ' மணி' + (min > 0 ? ' ' + min + ' நிமிடம்' : '');
    }

    toEnglishTime(timeStr) {
      var m = String(timeStr || '').match(/(\d{1,2}):(\d{2})(?::\d{2})?\s*(AM|PM)?/i);
      if (!m) return timeStr || '';
      return parseInt(m[1], 10) + ':' + m[2] + ' ' + (m[3] || '').toUpperCase();
    }

    announcePunchIn(empName, punchTime) {
      this.speak({
        tamil: 'நன்றி ' + empName + '! உங்கள் வருகை பதிவாகியது. நேரம் ' + this.toTamilTime(punchTime) + '.',
        english: 'Thank you, ' + empName + '! Your punch in is recorded at ' + this.toEnglishTime(punchTime) + '.'
      }, { interrupt: true });
    }

    announcePunchOut(empName, punchTime) {
      this.speak({
        tamil: 'நன்றி ' + empName + '! பணி நிறைவு நேரம் பதிவானது. நேரம் ' + this.toTamilTime(punchTime) + '.',
        english: 'Thank you, ' + empName + '! Your punch out is recorded at ' + this.toEnglishTime(punchTime) + '.'
      }, { interrupt: true });
    }

    announceAlreadyPunched(empName) {
      this.speak({
        tamil: empName + ', உங்கள் வருகை ஏற்கனவே பதிவாகியுள்ளது.',
        english: empName + ', your attendance is already marked.'
      }, { interrupt: true });
    }

    announceUnrecognized() {
      this.speak({
        tamil: 'முகம் அடையாளம் காணப்படவில்லை. மீண்டும் முயற்சிக்கவும்.',
        english: 'Face not recognized. Please face the camera directly and try again.'
      }, { interrupt: true });
    }

    announceSpoofDetected() {
      this.speak({
        tamil: 'நேரடி மனித முகம் மட்டுமே அனுமதிக்கப்படும்.',
        english: 'Live human presence required. Digital screens and photos are not permitted.'
      }, { interrupt: true });
    }

    announceSuccess(ta, en) {
      this.speak({ tamil: ta, english: en }, { interrupt: true });
    }

    announceError(ta, en) {
      this.speak({ tamil: ta, english: en }, { interrupt: true });
    }

    announceWarning(ta, en) {
      this.speak({ tamil: ta, english: en }, { interrupt: true });
    }
  }

  var instance = new MobileVoiceAssistant();
  window.ArgusVoice = instance;
  window.tamilVoice = instance;
})(window);
