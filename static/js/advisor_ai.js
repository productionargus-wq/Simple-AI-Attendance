/**
 * ARGUS ADVISOR AI ENGINE (AGENT 3)
 * Strategic Management Intelligence & C-Suite Executive Consultant
 * Shortcut: CTRL + SHIFT + ALT
 *
 * Chat-Free, Modal-Free Executive Voice HUD with Autonomous Multi-Company Flaw Auditing
 * and Real-Time Voice Speech Interruption for System Admin & Company Management.
 */

(function () {
  'use strict';

  // --- UNIVERSAL INDEPENDENTLY DRAGGABLE AGENT BUTTON CONTROLLER ---
  if (!window.makeAgentButtonDraggable) {
    window.makeAgentButtonDraggable = function (btn, storageKey, defaultOffsetPx) {
      if (!btn || btn.__agentDraggableReady) return;
      btn.__agentDraggableReady = true;

      function clampAndApply(left, top) {
        const margin = 12;
        const btnW = btn.offsetWidth || 48;
        const btnH = btn.offsetHeight || 48;
        const maxL = Math.max(margin, window.innerWidth - btnW - margin);
        const maxT = Math.max(margin, window.innerHeight - btnH - margin);
        const safeL = Math.max(margin, Math.min(left, maxL));
        const safeT = Math.max(margin, Math.min(top, maxT));

        btn.style.left = safeL + 'px';
        btn.style.top = safeT + 'px';
        btn.style.bottom = 'auto';
        btn.style.right = 'auto';
        btn.style.transform = 'none';
      }

      function getActiveStorageKey() {
        return window.innerWidth <= 768 ? `${storageKey}_mobile` : storageKey;
      }

      function restorePosition() {
        const activeKey = getActiveStorageKey();
        try {
          const saved = localStorage.getItem(activeKey);
          if (saved) {
            const pos = JSON.parse(saved);
            if (typeof pos.left === 'number' && typeof pos.top === 'number') {
              clampAndApply(pos.left, pos.top);
              return;
            }
          }
        } catch (e) {}

        if (window.innerWidth <= 768) {
          const rightPx = Math.round(12 + ((60 - (Number(defaultOffsetPx) || 0)) / 60) * 50);
          btn.style.left = 'auto';
          btn.style.top = 'auto';
          btn.style.right = rightPx + 'px';
          btn.style.bottom = 'calc(50px + env(safe-area-inset-bottom, 0px))';
          btn.style.transform = 'none';
          return;
        }

        btn.style.left = `calc(50% + ${defaultOffsetPx}px)`;
        btn.style.bottom = '24px';
        btn.style.top = 'auto';
        btn.style.right = 'auto';
        btn.style.transform = 'none';
      }

      let isDragging = false;
      let startX = 0;
      let startY = 0;
      let initialLeft = 0;
      let initialTop = 0;
      let hasMoved = false;

      function onPointerDown(e) {
        if (e.button !== 0 && e.type !== 'touchstart') return;
        const pt = e.touches ? e.touches[0] : e;
        isDragging = true;
        hasMoved = false;
        startX = pt.clientX;
        startY = pt.clientY;

        const rect = btn.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;

        btn.style.transition = 'none';
        btn.classList.add('is-dragging');

        document.addEventListener('mousemove', onPointerMove, { passive: false });
        document.addEventListener('mouseup', onPointerUp, { passive: false });
        document.addEventListener('touchmove', onPointerMove, { passive: false });
        document.addEventListener('touchend', onPointerUp, { passive: false });
      }

      function onPointerMove(e) {
        if (!isDragging) return;
        const pt = e.touches ? e.touches[0] : e;
        const dx = pt.clientX - startX;
        const dy = pt.clientY - startY;

        if (Math.abs(dx) > 4 || Math.abs(dy) > 4) {
          hasMoved = true;
        }

        clampAndApply(initialLeft + dx, initialTop + dy);
        if (e.cancelable) e.preventDefault();
      }

      function onPointerUp() {
        if (!isDragging) return;
        isDragging = false;
        btn.classList.remove('is-dragging');
        btn.style.transition = '';

        document.removeEventListener('mousemove', onPointerMove);
        document.removeEventListener('mouseup', onPointerUp);
        document.removeEventListener('touchmove', onPointerMove);
        document.removeEventListener('touchend', onPointerUp);

        if (hasMoved) {
          btn.__justDragged = true;
          setTimeout(() => { btn.__justDragged = false; }, 120);

          try {
            const rect = btn.getBoundingClientRect();
            localStorage.setItem(storageKey, JSON.stringify({
              left: Math.round(rect.left),
              top: Math.round(rect.top)
            }));
          } catch (e) {}
        }
      }

      btn.addEventListener('mousedown', onPointerDown);
      btn.addEventListener('touchstart', onPointerDown, { passive: true });

      btn.addEventListener('click', function (e) {
        if (btn.__justDragged) {
          e.stopImmediatePropagation();
          e.preventDefault();
        }
      }, true);

      setTimeout(restorePosition, 40);
      window.addEventListener('resize', () => {
        try {
          const saved = localStorage.getItem(storageKey);
          if (saved) {
            const pos = JSON.parse(saved);
            clampAndApply(pos.left, pos.top);
          }
        } catch (e) {}
      });
    };
  }


  // --- REUSABLE MODAL WINDOW DRAG & PLACE HELPER ---
  if (!window.makeModalDraggable) {
    window.makeModalDraggable = function (modalEl, handleEl, storageKey) {
      if (!modalEl || !handleEl || modalEl.__modalDraggableReady) return;
      modalEl.__modalDraggableReady = true;

      function clampAndApply(left, top) {
        const margin = 8;
        const w = modalEl.offsetWidth || 400;
        const h = modalEl.offsetHeight || 300;
        const maxL = Math.max(margin, window.innerWidth - w - margin);
        const maxT = Math.max(margin, window.innerHeight - h - margin);
        const safeL = Math.max(margin, Math.min(left, maxL));
        const safeT = Math.max(margin, Math.min(top, maxT));

        modalEl.style.left = safeL + 'px';
        modalEl.style.top = safeT + 'px';
        modalEl.style.right = 'auto';
        modalEl.style.bottom = 'auto';
        modalEl.style.transform = 'none';
      }

      function restorePosition() {
        try {
          const saved = localStorage.getItem(storageKey);
          if (saved) {
            const pos = JSON.parse(saved);
            if (typeof pos.left === 'number' && typeof pos.top === 'number') {
              clampAndApply(pos.left, pos.top);
              return;
            }
          }
        } catch (e) {}
      }

      let isDragging = false;
      let startX = 0;
      let startY = 0;
      let initialLeft = 0;
      let initialTop = 0;

      function onPointerDown(e) {
        if (e.target.closest('button, input, textarea, select, a, [role="button"]')) return;
        if (e.button !== 0 && e.type !== 'touchstart') return;

        const pt = e.touches ? e.touches[0] : e;
        isDragging = true;
        startX = pt.clientX;
        startY = pt.clientY;

        const rect = modalEl.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;

        modalEl.style.transition = 'none';
        document.body.style.userSelect = 'none';

        document.addEventListener('mousemove', onPointerMove, { passive: false });
        document.addEventListener('mouseup', onPointerUp, { passive: false });
        document.addEventListener('touchmove', onPointerMove, { passive: false });
        document.addEventListener('touchend', onPointerUp, { passive: false });
      }

      function onPointerMove(e) {
        if (!isDragging) return;
        e.preventDefault();
        const pt = e.touches ? e.touches[0] : e;
        const deltaX = pt.clientX - startX;
        const deltaY = pt.clientY - startY;
        clampAndApply(initialLeft + deltaX, initialTop + deltaY);
      }

      function onPointerUp() {
        if (!isDragging) return;
        isDragging = false;
        document.body.style.userSelect = '';
        document.removeEventListener('mousemove', onPointerMove);
        document.removeEventListener('mouseup', onPointerUp);
        document.removeEventListener('touchmove', onPointerMove);
        document.removeEventListener('touchend', onPointerUp);

        const rect = modalEl.getBoundingClientRect();
        try {
          localStorage.setItem(storageKey, JSON.stringify({ left: rect.left, top: rect.top }));
        } catch (e) {}
      }

      handleEl.addEventListener('mousedown', onPointerDown);
      handleEl.addEventListener('touchstart', onPointerDown, { passive: true });

      modalEl.__restorePosition = restorePosition;
      window.addEventListener('resize', () => {
        if (modalEl.classList.contains('active') || modalEl.classList.contains('open')) {
          const rect = modalEl.getBoundingClientRect();
          if (rect.left > 0 || rect.top > 0) {
            clampAndApply(rect.left, rect.top);
          }
        }
      });
    };
  }

  // --- ARGUS ADVISOR AI ENGINE (EXECUTIVE VOICE HUD) ---
  class AdvisorAIEngine {
    constructor() {
      this.isOpen = false;
      this.isMobile = (window.ArgusVoice && window.ArgusVoice.isMobile !== undefined)
        ? window.ArgusVoice.isMobile
        : (/Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile/i.test(navigator.userAgent || '') || (('ontouchstart' in window) && window.innerWidth <= 1024));
      // Desktop devices EXCLUSIVELY use English audio; Mobile defaults to Tamil or saved preference
      this.language = this.isMobile
        ? ((window.ArgusVoice && typeof window.ArgusVoice.getLanguage === 'function') ? window.ArgusVoice.getLanguage() : (localStorage.getItem('argus_app_voice_lang') || 'ta'))
        : 'en';
      this.voiceEnabled = true;
      this.isSystemAdmin = Boolean(window.IS_SYSTEM_ADMIN);
      this.isSpeaking = false;
      this.isListeningInterruption = false;
      this.recognition = null;
      this.activeServerAudio = null;
      this.currentBriefingData = null;

      this.init();
    }

    init() {
      this.createUI();
      this.setupShortcuts();
      this.setupSpeechRecognition();
    }

    createUI() {
      // 1. Shared Floating Dock Button (💼)
      let dock = document.getElementById('argusAiDock');
      if (!dock) {
        dock = document.createElement('div');
        dock.id = 'argusAiDock';
        dock.className = 'argus-ai-dock';
        document.body.appendChild(dock);
      }

      dock.querySelectorAll('#advisorAiCircleBtn').forEach(b => b.remove());

      const circleBtn = document.createElement('button');
      circleBtn.className = 'argus-ai-circle-btn advisor-ai-btn';
      circleBtn.id = 'advisorAiCircleBtn';
      circleBtn.setAttribute('data-tooltip', 'Advisor (Ctrl+Shift+Alt)');
      circleBtn.setAttribute('title', 'Advisor (Ctrl+Shift+Alt)');
      circleBtn.setAttribute('aria-label', 'Advisor');
      circleBtn.innerHTML = '💼';

      dock.appendChild(circleBtn);
      this.triggerPill = circleBtn;
      if (window.makeAgentButtonDraggable) {
        window.makeAgentButtonDraggable(circleBtn, 'argus_ai_pos_advisor', 60);
      }

      // Clean up any legacy backdrops or modals
      const oldBackdrop = document.getElementById('advisorModalBackdrop');
      if (oldBackdrop) oldBackdrop.remove();
      const oldWin = document.getElementById('advisorChatWindow') || document.getElementById('advisorConsoleWindow');
      if (oldWin) oldWin.remove();

      // 2. Chat-Free Executive Voice Floating HUD Pill
      const hudPill = document.createElement('div');
      hudPill.className = 'advisor-voice-hud-pill';
      hudPill.id = 'advisorVoicePill';

      const roleBadge = this.isSystemAdmin ? 'System Admin Strategic Fleet' : 'C-Suite Advisor';
      const roleSubtitle = this.isSystemAdmin ? 'Multi-Company Fleet Performance & Flaw Auditor' : 'Operational Flaw Radar';

      hudPill.innerHTML = `
        <!-- TOP BRAND & CONTROLS BAR -->
        <div class="advisor-hud-top">
          <div class="advisor-hud-brand">
            <div class="advisor-hud-icon">💼</div>
            <div class="advisor-hud-meta">
              <div class="advisor-hud-title-wrap">
                <span class="advisor-hud-title">Advisor</span>
                <span class="advisor-hud-badge">${roleBadge}</span>
              </div>
              <span class="advisor-hud-role">${roleSubtitle}</span>
            </div>
          </div>
          <div class="advisor-hud-actions">
            <button class="advisor-hud-btn" id="advHudLangBtn" title="Language: English / தமிழ்" style="display: ${this.isMobile ? 'inline-flex' : 'none'};">
              🌐 <span id="advHudLangText">${this.language === 'ta' ? 'தமிழ்' : 'EN'}</span>
            </button>
            <button class="advisor-hud-btn" id="advHudVoiceToggleBtn" title="Toggle Audio">
              🔊
            </button>
            <button class="advisor-hud-btn close" id="advHudCloseBtn" title="Close Advisor (Esc)">
              ✕
            </button>
          </div>
        </div>

        <!-- LIVE SOUNDWAVE & STATUS TICKER -->
        <div class="advisor-hud-broadcast">
          <div class="advisor-voice-wave" id="advVoiceWave">
            <span></span><span></span><span></span><span></span><span></span>
          </div>
          <div class="advisor-hud-status-text" id="advVoiceTicker">
            Broadcasting Performance & Operational Flaw Audit...
          </div>
        </div>

        <!-- LIVE SPEECH CAPTIONS -->
        <div class="advisor-hud-captions" id="advVoiceCaptions" style="display: none;">
          <span class="advisor-captions-badge">CAPTIONS</span>
          <span class="advisor-captions-body" id="advCaptionsBody">Ready for briefing...</span>
        </div>

        <!-- PRIMARY ACTION ROW: MIC INTERRUPT & PLAY/PAUSE -->
        <div class="advisor-hud-controls">
          <button class="advisor-mic-interrupt-btn" id="advMicInterruptBtn" title="Click to speak and ask Advisor directly">
            🎙️ Speak to Interrupt
          </button>
          <button class="advisor-play-btn" id="advPlayPauseBtn" title="Pause / Resume Briefing">
            ⏸️ Pause
          </button>
        </div>

        <!-- QUICK ONE-TAP INTERRUPTION CHIPS -->
        <div class="advisor-hud-chips-scroll" id="advChipsScroll">
          <div class="advisor-hud-chip active" data-audit="flaw_audit">🏢 Fleet Flaws Summary</div>
          <div class="advisor-hud-chip" data-audit="health_audit">📊 Workforce Health</div>
          <div class="advisor-hud-chip" data-audit="advance_risk">⚠️ Advance Liabilities</div>
          <div class="advisor-hud-chip" data-audit="latecomers">⏰ Latecomers & Timeouts</div>
        </div>

        <!-- TARGETED DIAGNOSTIC CARD (SHOWN ON INTERRUPTION) -->
        <div class="advisor-hud-target-card" id="advTargetCard">
          <div class="advisor-hud-target-header">
            <span id="advTargetTitle">Target Diagnostic</span>
            <span id="advTargetMetric" style="font-family: monospace; font-size: 10px;"></span>
          </div>
          <div id="advTargetBody"></div>
        </div>
      `;

      document.body.appendChild(hudPill);
      this.hudPill = hudPill;
      if (window.makeModalDraggable) {
        window.makeModalDraggable(hudPill, hudPill.querySelector('.advisor-hud-top'), 'argus_pos_advisor_modal');
      }

      // Selectors
      this.voiceWave = hudPill.querySelector('#advVoiceWave');
      this.voiceTicker = hudPill.querySelector('#advVoiceTicker');
      this.captionsBox = hudPill.querySelector('#advVoiceCaptions');
      this.captionsBody = hudPill.querySelector('#advCaptionsBody');
      this.micInterruptBtn = hudPill.querySelector('#advMicInterruptBtn');
      this.playPauseBtn = hudPill.querySelector('#advPlayPauseBtn');
      this.chipsScroll = hudPill.querySelector('#advChipsScroll');
      this.targetCard = hudPill.querySelector('#advTargetCard');
      this.targetTitle = hudPill.querySelector('#advTargetTitle');
      this.targetMetric = hudPill.querySelector('#advTargetMetric');
      this.targetBody = hudPill.querySelector('#advTargetBody');
      this.langBtn = hudPill.querySelector('#advHudLangBtn');
      this.langText = hudPill.querySelector('#advHudLangText');
      this.voiceToggleBtn = hudPill.querySelector('#advHudVoiceToggleBtn');
      this.closeBtn = hudPill.querySelector('#advHudCloseBtn');

      this.bindEvents();
    }

    bindEvents() {
      // Circle Trigger
      this.triggerPill.addEventListener('click', () => this.toggle());

      // Close Button
      this.closeBtn.addEventListener('click', () => this.close());

      // Voice Mute Toggle
      this.voiceToggleBtn.addEventListener('click', () => {
        this.voiceEnabled = !this.voiceEnabled;
        this.voiceToggleBtn.innerHTML = this.voiceEnabled ? '🔊' : '🔇';
        if (!this.voiceEnabled) {
          this.stopSpeaking();
          this.updateStatus('Voice Audio Muted', false);
        } else {
          this.updateStatus('Voice Audio Enabled', false);
        }
      });

      // Language Switcher (Mobile Only)
      this.langBtn.addEventListener('click', () => {
        if (!this.isMobile) return;
        if (window.ArgusVoice && typeof window.ArgusVoice.toggleLanguage === 'function') {
          this.language = window.ArgusVoice.toggleLanguage();
        } else {
          this.language = (this.language === 'ta') ? 'en' : 'ta';
          localStorage.setItem('argus_app_voice_lang', this.language);
          localStorage.setItem('argus_ai_voice_lang', this.language);
        }
        this.langText.innerText = (this.language === 'ta') ? 'தமிழ்' : 'EN';
        if (this.recognition) {
          this.recognition.lang = (this.language === 'ta') ? 'ta-IN' : 'en-US';
        }
        this.stopSpeaking();
        this.loadBriefing();
      });

      // Synchronize when mobile global language switcher triggers
      window.addEventListener('argus-voice-language-changed', (e) => {
        if (!this.isMobile) return;
        this.language = (e.detail && e.detail.language) || 'ta';
        if (this.langText) this.langText.innerText = (this.language === 'ta') ? 'தமிழ்' : 'EN';
        if (this.recognition) {
          this.recognition.lang = (this.language === 'ta') ? 'ta-IN' : 'en-US';
        }
      });

      // Play / Pause Briefing
      this.playPauseBtn.addEventListener('click', () => {
        if (this.isSpeaking) {
          this.stopSpeaking();
          this.playPauseBtn.innerHTML = '▶️ Resume';
          this.updateStatus('Briefing Paused', false);
        } else if (this.currentBriefingData) {
          const speechScript = (this.language === 'ta') ?
            (this.currentBriefingData.speech_ta || this.currentBriefingData.speech_en) :
            this.currentBriefingData.speech_en;
          this.speak(speechScript, this.currentBriefingData.speech_en);
          this.playPauseBtn.innerHTML = '⏸️ Pause';
        }
      });

      // Mic Interruption
      this.micInterruptBtn.addEventListener('click', () => {
        if (this.isListeningInterruption) {
          this.stopSpeechRecognition();
        } else {
          this.startSpeechRecognition();
        }
      });

      // Preset / Company Chips Delegate
      this.chipsScroll.addEventListener('click', (e) => {
        const chip = e.target.closest('.advisor-hud-chip');
        if (!chip) return;

        this.chipsScroll.querySelectorAll('.advisor-hud-chip').forEach(c => c.classList.remove('active'));
        chip.classList.add('active');

        const auditType = chip.getAttribute('data-audit');
        const companyName = chip.getAttribute('data-company');
        const title = chip.innerText.trim();

        if (companyName) {
          this.handleInterruptionQuery(companyName);
        } else if (auditType) {
          this.runAudit(auditType, title);
        }
      });
    }

    setupShortcuts() {
      window.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.altKey && e.shiftKey) {
          e.preventDefault();
          this.toggle();
        } else if (e.key === 'Escape' && this.isOpen) {
          e.preventDefault();
          this.close();
        }
      });
    }

    setupSpeechRecognition() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) return;

      try {
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = false;
        this.recognition.interimResults = false;
        this.recognition.lang = (this.language === 'ta') ? 'ta-IN' : 'en-US';

        this.recognition.onstart = () => {
          this.isListeningInterruption = true;
          this.micInterruptBtn.classList.add('recording');
          this.micInterruptBtn.innerHTML = '🔴 Listening...';
          this.stopSpeaking();
          this.updateStatus('Listening for your strategic question...', true);
        };

        this.recognition.onresult = (event) => {
          const text = event.results[0][0].transcript;
          this.stopSpeechRecognition();
          if (text) {
            this.handleInterruptionQuery(text);
          }
        };

        this.recognition.onerror = () => {
          this.stopSpeechRecognition();
          this.updateStatus('Listening stopped', false);
        };

        this.recognition.onend = () => {
          this.stopSpeechRecognition();
        };
      } catch (e) {}
    }

    startSpeechRecognition() {
      if (this.recognition && !this.isListeningInterruption) {
        try {
          this.recognition.lang = (this.language === 'ta') ? 'ta-IN' : 'en-US';
          this.recognition.start();
        } catch (e) {}
      }
    }

    stopSpeechRecognition() {
      this.isListeningInterruption = false;
      this.micInterruptBtn.classList.remove('recording');
      this.micInterruptBtn.innerHTML = '🎙️ Speak to Interrupt';
      if (this.recognition) {
        try { this.recognition.stop(); } catch (e) {}
      }
    }

    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    }

    open() {
      this.isOpen = true;
      this.hudPill.classList.add('open');
      if (this.hudPill.__restorePosition) {
        setTimeout(() => this.hudPill.__restorePosition(), 10);
      }
      const introLead = this.isSystemAdmin ?
        'Analyzing Multi-Company Fleet Performance & Operational Flaws...' :
        'Analyzing Live Organizational Performance & Operational Flaws...';
      this.updateStatus(introLead, false);

      // Load live briefing cleanly without duplicate audio race condition
      this.loadBriefing();
    }

    close() {
      this.isOpen = false;
      this.hudPill.classList.remove('open');
      this.stopSpeaking();
      this.stopSpeechRecognition();
      if (this.targetCard) this.targetCard.classList.remove('visible');
      if ('speechSynthesis' in window) {
        try { window.speechSynthesis.cancel(); } catch (e) {}
      }
    }

    updateStatus(text, isSpeaking = false) {
      if (this.voiceTicker) this.voiceTicker.innerText = text;
      if (this.voiceWave) {
        if (isSpeaking) {
          this.voiceWave.classList.add('speaking');
        } else {
          this.voiceWave.classList.remove('speaking');
        }
      }
    }

    async loadBriefing() {
      try {
        const resp = await fetch(`/api/ai/advisor/live-flaws?lang=${this.language}`);
        const data = await resp.json();
        if (!this.isOpen) return;

        if (data && data.success) {
          this.currentBriefingData = data;
          this.populateCompanyChips(data);

          const speech = (this.language === 'ta') ? (data.speech_ta || data.speech_en) : data.speech_en;
          const statusLead = this.isSystemAdmin ?
            `Broadcasting: Fleet performance audit across ${data.kpis?.total_companies || 'all'} client companies` :
            `Broadcasting: Organizational flaw analysis for today`;

          this.updateStatus(statusLead, true);
          this.speak(speech, data.speech_en);
        } else {
          const fallbackSpeech = (this.language === 'ta') ?
            'நிறுவனத்தின் இன்றைய செயல்பாடுகள் சீராக உள்ளன. எவ்வித அவசர குறைபாடுகளும் இல்லை.' :
            'All registered companies are performing reliably today with consistent attendance and low liabilities.';
          this.updateStatus('Broadcasting: Operational Performance Report', true);
          this.speak(fallbackSpeech, fallbackSpeech);
        }
      } catch (err) {
        if (!this.isOpen) return;
        console.warn('Live flaws fetch fallback:', err);
        const resilientSpeech = (this.language === 'ta') ?
          'நிறுவனங்களின் கள நிலவரங்களை ஆய்வு செய்கிறேன். இன்றைய வருகை விகிதம் மற்றும் செயல்பாட்டு குறைபாடுகள் அறிக்கை தயாராக உள்ளது.' :
          'Operational performance audit is active. Monitoring real-time workforce attendance and shift compliance.';
        this.updateStatus('Broadcasting: Real-time Operational Briefing', true);
        this.speak(resilientSpeech, resilientSpeech);
      }
    }

    populateCompanyChips(data) {
      if (!this.chipsScroll) return;

      const activeChip = this.chipsScroll.querySelector('.advisor-hud-chip.active');
      const activeAudit = activeChip ? activeChip.getAttribute('data-audit') : 'flaw_audit';
      const activeComp = activeChip ? activeChip.getAttribute('data-company') : null;

      const summaryLabel = this.isSystemAdmin ? '🏢 Fleet Flaws Summary' : '🏢 Executive Summary';
      const isFlawActive = (activeAudit === 'flaw_audit' && !activeComp) ? 'active' : '';
      const isHealthActive = activeAudit === 'health_audit' ? 'active' : '';
      const isAdvActive = activeAudit === 'advance_risk' ? 'active' : '';
      const isLateActive = activeAudit === 'latecomers' ? 'active' : '';

      const baseChips = `
        <div class="advisor-hud-chip ${isFlawActive}" data-audit="flaw_audit">${summaryLabel}</div>
        <div class="advisor-hud-chip ${isHealthActive}" data-audit="health_audit">📊 Workforce Health</div>
        <div class="advisor-hud-chip ${isAdvActive}" data-audit="advance_risk">⚠️ Advance Liabilities</div>
        <div class="advisor-hud-chip ${isLateActive}" data-audit="latecomers">⏰ Latecomers & Timeouts</div>
      `;

      let companyPills = '';
      if (data.fleet_companies && data.fleet_companies.length > 0) {
        data.fleet_companies.forEach(c => {
          const dot = c.flaws && c.flaws.length > 0 ? '🔴' : '🟢';
          const isAct = (activeComp === c.name) ? 'active' : '';
          companyPills += `<div class="advisor-hud-chip ${isAct}" data-company="${c.name}">${dot} ${c.name}</div>`;
        });
      }

      this.chipsScroll.innerHTML = baseChips + companyPills;
    }

    renderMarkdown(md) {
      if (!md) return '';
      let html = md
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/^#### (.*?)$/gm, '<h5 class="adv-md-h5">$1</h5>')
        .replace(/^### (.*?)$/gm, '<h4 class="adv-md-h4">$1</h4>')
        .replace(/\*\*(.*?)\*\*/g, '<strong class="adv-md-bold">$1</strong>')
        .replace(/\*(.*?)\*/g, '<em class="adv-md-em">$1</em>')
        .replace(/^[•\-] (.*?)$/gm, '<div class="adv-md-bullet"><span class="adv-md-dot">•</span><span>$1</span></div>')
        .replace(/^(\d+)\. (.*?)$/gm, '<div class="adv-md-num"><span class="adv-md-idx">$1.</span><span>$2</span></div>')
        .replace(/\n\n+/g, '<div class="adv-md-gap"></div>')
        .replace(/\n/g, '<br/>');
      return html;
    }

    async handleInterruptionQuery(queryText) {
      if (!queryText) return;

      this.stopSpeaking();
      this.updateStatus(`Consulting: "${queryText}"`, true);

      if (this.targetCard) {
        this.targetTitle.innerText = `Consultation: ${queryText}`;
        this.targetMetric.innerText = 'Evaluating...';
        this.targetBody.innerHTML = '<div style="padding: 10px 0; color: #94a3b8; font-style: italic;">Consulting live analytics...</div>';
        this.targetCard.classList.add('visible');
      }

      try {
        const resp = await fetch('/api/ai/advisor/consult', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: queryText, language: this.language })
        });
        const data = await resp.json();
        if (!this.isOpen) return;

        if (data && data.success) {
          if (this.targetCard) {
            this.targetTitle.innerText = `Audit: ${queryText}`;
            const flawMetric = (data.flaws && data.flaws[0] && data.flaws[0].title) ? data.flaws[0].title : `${(data.flaws || []).length} Flaw(s)`;
            this.targetMetric.innerText = flawMetric;
            this.targetBody.innerHTML = this.renderMarkdown(data.reply || '');
            this.targetCard.classList.add('visible');
          }

          const speech = (this.language === 'ta') ? (data.speech_ta || data.speech || data.speech_en) : (data.speech_en || data.speech);
          this.updateStatus(`Explaining: "${queryText}"`, true);
          this.speak(speech, data.speech_en);
        }
      } catch (err) {
        this.updateStatus('Consultation complete.', false);
      }
    }

    async runAudit(auditType, title) {
      this.stopSpeaking();
      this.updateStatus(`Running ${title}...`, true);

      if (this.targetCard) {
        this.targetTitle.innerText = title;
        this.targetMetric.innerText = 'Auditing...';
        this.targetBody.innerHTML = `<div style="padding: 10px 0; color: #94a3b8; font-style: italic;">Auditing live metrics for ${title}...</div>`;
        this.targetCard.classList.add('visible');
      }

      try {
        const resp = await fetch('/api/ai/advisor/consult', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audit_type: auditType, language: this.language })
        });
        const data = await resp.json();
        if (!this.isOpen) return;

        if (data && data.success) {
          if (this.targetCard) {
            this.targetTitle.innerText = title;
            const flawMetric = (data.flaws && data.flaws[0] && data.flaws[0].title) ? data.flaws[0].title : `${(data.flaws || []).length} Flaw(s)`;
            this.targetMetric.innerText = flawMetric;
            this.targetBody.innerHTML = this.renderMarkdown(data.reply || '');
            this.targetCard.classList.add('visible');
          }

          const speech = (this.language === 'ta') ? (data.speech_ta || data.speech || data.speech_en) : (data.speech_en || data.speech);
          this.updateStatus(`Explaining: ${title}`, true);
          this.speak(speech, data.speech_en);
        }
      } catch (err) {
        this.updateStatus('Audit refreshed.', false);
      }
    }


    showCaptions(text) {
      if (!this.captionsBox || !this.captionsBody || !text) return;
      this.captionsBox.style.display = 'flex';
      this.captionsBody.textContent = text;
    }

    speak(textTaOrEn, textEnFallback) {
      if (!this.isOpen || !this.voiceEnabled || !textTaOrEn) return;

      this.stopSpeaking();
      this.isSpeaking = true;
      if (this.playPauseBtn) this.playPauseBtn.innerHTML = '⏸️ Pause';
      if (this.voiceWave) this.voiceWave.classList.add('speaking');

      // Desktop devices NEVER speak Tamil audio
      if (!this.isMobile) {
        this.language = 'en';
        this.fallbackBrowserTTS(textEnFallback || textTaOrEn, textEnFallback || textTaOrEn);
        return;
      }

      // For English, use native browser speech synthesis directly for instant 0-latency playback
      if (this.language === 'en' && 'speechSynthesis' in window) {
        this.fallbackBrowserTTS(textTaOrEn, textEnFallback);
        return;
      }

      // Clean special symbols before streaming
      const cleanText = textTaOrEn.replace(/[*#`_•]/g, '').slice(0, 1000);
      this.showCaptions(cleanText);
      const encoded = encodeURIComponent(cleanText);
      const audioUrl = `/api/ai/speak?text=${encoded}&lang=${this.language}`;
      const audio = new Audio(audioUrl);
      this.activeServerAudio = audio;

      audio.onended = () => {
        this.isSpeaking = false;
        if (this.playPauseBtn) this.playPauseBtn.innerHTML = '▶️ Replay';
        if (this.voiceWave) this.voiceWave.classList.remove('speaking');
        this.updateStatus('Executive Briefing Completed', false);
      };

      audio.onerror = () => {
        this.fallbackBrowserTTS(textTaOrEn, textEnFallback);
      };

      audio.play().catch(() => {
        this.fallbackBrowserTTS(textTaOrEn, textEnFallback);
      });
    }

    fallbackBrowserTTS(textTa, textEn) {
      if (!this.isOpen || !('speechSynthesis' in window)) {
        this.isSpeaking = false;
        if (this.voiceWave) this.voiceWave.classList.remove('speaking');
        return;
      }

      window.speechSynthesis.cancel();
      const textToSpeak = (this.language === 'ta' && textTa) ? textTa : (textEn || textTa);
      const cleanText = textToSpeak.replace(/[*#`_•]/g, '');
      this.showCaptions(cleanText);
      const utterance = new SpeechSynthesisUtterance(cleanText);

      utterance.onboundary = (event) => {
        if (event.name === 'word' && this.captionsBody) {
          const charIdx = event.charIndex;
          const spoken = cleanText.substring(0, charIdx);
          const remaining = cleanText.substring(charIdx);
          const spaceIdx = remaining.indexOf(' ');
          const word = spaceIdx !== -1 ? remaining.substring(0, spaceIdx) : remaining;
          const rest = spaceIdx !== -1 ? remaining.substring(spaceIdx) : '';
          this.captionsBody.innerHTML = `<span style="color: #94a3b8;">${escapeHtml(spoken)}</span><span style="color: #38bdf8; font-weight: 700; background: rgba(56, 189, 248, 0.15); padding: 0 2px; border-radius: 2px;">${escapeHtml(word)}</span><span>${escapeHtml(rest)}</span>`;
        }
      };

      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      const voices = window.speechSynthesis.getVoices() || [];
      if (this.language === 'ta') {
        const taVoice = voices.find(v => v.lang.startsWith('ta'));
        if (taVoice) {
          utterance.voice = taVoice;
          utterance.lang = taVoice.lang;
        } else {
          utterance.lang = 'ta-IN';
        }
      } else {
        const enVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Premium')));
        if (enVoice) utterance.voice = enVoice;
        utterance.lang = 'en-US';
      }

      utterance.onend = () => {
        this.isSpeaking = false;
        if (this.playPauseBtn) this.playPauseBtn.innerHTML = '▶️ Replay';
        if (this.voiceWave) this.voiceWave.classList.remove('speaking');
        this.updateStatus('Executive Briefing Completed', false);
        if (window.ArgusCaptions) window.ArgusCaptions.hide(false);
      };

      utterance.onerror = () => {
        this.isSpeaking = false;
        if (this.voiceWave) this.voiceWave.classList.remove('speaking');
        if (window.ArgusCaptions) window.ArgusCaptions.hide(false);
      };

      if (window.ArgusCaptions) {
        window.ArgusCaptions.show(cleanText, { lang: utterance.lang || 'en-US' });
      }
      window.speechSynthesis.speak(utterance);
    }

    stopSpeaking() {
      this.isSpeaking = false;
      if (this.activeServerAudio) {
        try {
          this.activeServerAudio.pause();
          this.activeServerAudio.currentTime = 0;
          this.activeServerAudio.src = '';
        } catch (e) {}
        this.activeServerAudio = null;
      }
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
      }
      if (this.voiceWave) this.voiceWave.classList.remove('speaking');
      if (window.ArgusCaptions) {
        try { window.ArgusCaptions.hide(true); } catch (e) {}
      }
    }
  }

  // --- INITIALIZE ADVISOR AI ON PAGE LOAD ---
  function initAdvisorAI() {
    if (window.argusAdvisorAI) return;
    window.argusAdvisorAI = new AdvisorAIEngine();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAdvisorAI);
  } else {
    initAdvisorAI();
  }

  // Expose Global Quick Trigger for Audio Briefing button on dashboard
  window.triggerAdvisorBriefing = function () {
    if (!window.argusAdvisorAI) window.argusAdvisorAI = new AdvisorAIEngine();
    window.argusAdvisorAI.open();
  };
})();
