/**
 * ARGUS ADVISOR AI ENGINE (AGENT 3)
 * Strategic Management Intelligence & C-Suite Executive Consultant
 * Shortcut: CTRL + SHIFT + ALT
 *
 * Chat-Free Boardroom Intelligence HUD with Autonomous Multi-Company Flaw Auditing
 * and Real-Time Interruption Handling for System Admin & Company Management.
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

        btn.style.left = `calc(50% + ${defaultOffsetPx}px)`;
        btn.style.bottom = '24px';
        btn.style.top = 'auto';
        btn.style.right = 'auto';
        btn.style.transform = 'translateX(-50%)';
      }

      let isDragging = false;
      let hasMoved = false;
      let startX = 0, startY = 0;
      let initialLeft = 0, initialTop = 0;

      function onPointerDown(e) {
        if (e.type === 'mousedown' && e.button !== 0) return;
        const pt = e.touches ? e.touches[0] : e;
        startX = pt.clientX;
        startY = pt.clientY;

        const rect = btn.getBoundingClientRect();
        initialLeft = rect.left;
        initialTop = rect.top;
        hasMoved = false;
        isDragging = true;

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

        if (!hasMoved && Math.hypot(dx, dy) > 5) {
          hasMoved = true;
          btn.classList.add('is-dragging');
        }

        if (hasMoved) {
          if (e.cancelable) e.preventDefault();
          clampAndApply(initialLeft + dx, initialTop + dy);
        }
      }

      function onPointerUp(e) {
        if (!isDragging) return;
        isDragging = false;
        btn.classList.remove('is-dragging');

        document.removeEventListener('mousemove', onPointerMove);
        document.removeEventListener('mouseup', onPointerUp);
        document.removeEventListener('touchmove', onPointerMove);
        document.removeEventListener('touchend', onPointerUp);

        if (hasMoved) {
          btn.__justDragged = true;
          setTimeout(() => { btn.__justDragged = false; }, 160);

          const rect = btn.getBoundingClientRect();
          try {
            localStorage.setItem(storageKey, JSON.stringify({
              left: Math.round(rect.left),
              top: Math.round(rect.top)
            }));
          } catch (err) {}
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
            if (typeof pos.left === 'number' && typeof pos.top === 'number') {
              clampAndApply(pos.left, pos.top);
            }
          }
        } catch (e) {}
      });
    };
  }

  class AdvisorAIEngine {
    constructor() {
      this.isOpen = false;
      this.isSystemAdmin = Boolean(window.IS_SYSTEM_ADMIN);
      this.language = localStorage.getItem('argus_ai_voice_lang') || 'en';
      this.voiceEnabled = localStorage.getItem('argus_advisor_voice') !== 'false';
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
      // 1. Shared Floating Dock Icon
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
      circleBtn.setAttribute('data-tooltip', 'Advisor AI (Ctrl+Shift+Alt)');
      circleBtn.setAttribute('title', 'Advisor AI (Ctrl+Shift+Alt)');
      circleBtn.setAttribute('aria-label', 'Advisor AI');
      circleBtn.innerHTML = '💼';

      dock.appendChild(circleBtn);
      this.triggerPill = circleBtn;
      if (window.makeAgentButtonDraggable) {
        window.makeAgentButtonDraggable(circleBtn, 'argus_ai_pos_advisor', 60);
      }

      // 2. Backdrop
      const oldBackdrop = document.getElementById('advisorModalBackdrop');
      if (oldBackdrop) oldBackdrop.remove();
      const backdrop = document.createElement('div');
      backdrop.className = 'advisor-modal-backdrop';
      backdrop.id = 'advisorModalBackdrop';
      document.body.appendChild(backdrop);
      this.backdrop = backdrop;

      // 3. Boardroom Executive Console Window (Chat-Free Strategic HUD)
      const oldWin = document.getElementById('advisorChatWindow') || document.getElementById('advisorConsoleWindow');
      if (oldWin) oldWin.remove();

      const win = document.createElement('div');
      win.className = 'advisor-chat-window advisor-executive-hud';
      win.id = 'advisorChatWindow';

      const roleBadge = this.isSystemAdmin ? 'System Admin Strategic Fleet' : 'C-Suite Intelligence';
      const roleSubtitle = this.isSystemAdmin ? 'Multi-Company Fleet Performance & Flaw Auditor' : 'Management Strategic Partner • Live Flaw Radar';

      win.innerHTML = `
        <!-- EXECUTIVE HEADER -->
        <div class="advisor-header">
          <div class="advisor-header-left">
            <div class="advisor-avatar">
              💼
              <span class="advisor-online-dot"></span>
            </div>
            <div class="advisor-header-info">
              <div class="advisor-header-title">
                Advisor AI
                <span class="advisor-badge-pill">${roleBadge}</span>
              </div>
              <div class="advisor-header-subtitle">${roleSubtitle}</div>
            </div>
          </div>
          <div class="advisor-header-actions">
            <button class="advisor-icon-btn advisor-lang-btn" id="advisorLangToggleBtn" title="Language: English / தமிழ்">
              🌐 <span id="advisorLangLabel">${this.language === 'ta' ? 'தமிழ்' : 'EN'}</span>
            </button>
            <button class="advisor-icon-btn ${this.voiceEnabled ? 'active' : ''}" id="advisorVoiceBtn" title="Toggle Executive Audio Briefings">
              ${this.voiceEnabled ? '🔊' : '🔇'}
            </button>
            <button class="advisor-icon-btn" id="advisorRefreshBtn" title="Rerun Strategic Audit">
              🔄
            </button>
            <button class="advisor-icon-btn" id="advisorCloseBtn" title="Close (Esc)">
              ✕
            </button>
          </div>
        </div>

        <!-- LIVE EXECUTIVE KPI STRIP -->
        <div class="advisor-kpi-ribbon" id="advisorKpiRibbon">
          <div class="advisor-kpi-card">
            <span class="advisor-kpi-label">${this.isSystemAdmin ? 'Fleet Health' : 'Health Score'}</span>
            <span class="advisor-kpi-value green" id="advKpiHealth">--</span>
          </div>
          <div class="advisor-kpi-card">
            <span class="advisor-kpi-label">${this.isSystemAdmin ? 'Fleet Advances' : 'Advance Liability'}</span>
            <span class="advisor-kpi-value amber" id="advKpiLiability">--</span>
          </div>
          <div class="advisor-kpi-card">
            <span class="advisor-kpi-label">${this.isSystemAdmin ? 'Timeout Punches' : 'Punctuality'}</span>
            <span class="advisor-kpi-value indigo" id="advKpiPunc">--</span>
          </div>
          <div class="advisor-kpi-card">
            <span class="advisor-kpi-label">${this.isSystemAdmin ? 'Platform Workforce' : 'Present Today'}</span>
            <span class="advisor-kpi-value" id="advKpiStaff">--</span>
          </div>
        </div>

        <!-- STRATEGIC AUDIT PRESET TABS -->
        <div class="advisor-presets-bar">
          <div class="advisor-preset-chip active-chip" data-audit="flaw_audit">
            ${this.isSystemAdmin ? '🏢 Fleet Companies & Flaws' : '🚨 Flaw Radar & Solutions'}
          </div>
          <div class="advisor-preset-chip" data-audit="health_audit">
            📊 Workforce Health Audit
          </div>
          <div class="advisor-preset-chip" data-audit="advance_risk">
            ⚠️ Advance Risk Radar
          </div>
          <div class="advisor-preset-chip" data-audit="latecomers">
            ⏰ Latecomers & Timeouts
          </div>
          <div class="advisor-preset-chip" data-audit="executive_summary">
            📋 Executive Briefing
          </div>
        </div>

        <!-- AUDIO WAVEFORM & BRIEFING BROADCAST STATUS -->
        <div class="advisor-voice-status-bar" id="advisorVoiceStatusBar">
          <div class="advisor-voice-wave" id="advisorVoiceWave">
            <span></span><span></span><span></span><span></span><span></span>
          </div>
          <div class="advisor-voice-status-text" id="advisorVoiceStatusText">
            Executive Briefing Ready
          </div>
          <button class="advisor-voice-control-btn" id="advisorVoicePlayPauseBtn" title="Pause / Resume Audio">
            ⏸️ Pause
          </button>
        </div>

        <!-- BOARDROOM PRESENTATION STAGE (Chat-Free Core) -->
        <div class="advisor-presentation-stage" id="advisorPresentationStage">
          <div class="advisor-loading-card" id="advisorLoadingCard">
            <div class="advisor-typing-dots">
              <span></span><span></span><span></span>
            </div>
            <span>Analyzing organizational telemetry and operational flaws...</span>
          </div>
          <div class="advisor-stage-content" id="advisorStageContent">
            <!-- Strategic Report Markdown & Company Matrix rendered here -->
          </div>
        </div>

        <!-- LIVE INTERRUPTION BAR (Ask or Interrupt Advisor AI) -->
        <div class="advisor-interruption-bar">
          <div class="advisor-interrupt-chips-scroll" id="advisorInterruptChips">
            <span class="advisor-interrupt-hint">💡 Tap or speak to ask Advisor AI:</span>
            <!-- Dynamically populated interrupt chips -->
          </div>
          <div class="advisor-interrupt-input-wrap">
            <button class="advisor-interrupt-mic-btn" id="advisorInterruptMicBtn" title="Speak to Interrupt Advisor AI">
              🎙️ Tap to Speak / Interrupt
            </button>
            <input type="text" class="advisor-interrupt-input" id="advisorInterruptInput" placeholder="Ask specific question about any company, flaw, or metric (e.g. 'What about HEXA TECHNOLOGIES?')..." />
            <button class="advisor-interrupt-submit-btn" id="advisorInterruptSubmitBtn" title="Submit Question">
              ➤
            </button>
          </div>
        </div>
      `;

      document.body.appendChild(win);
      this.consoleWindow = win;

      // Selectors
      this.stageContent = win.querySelector('#advisorStageContent');
      this.loadingCard = win.querySelector('#advisorLoadingCard');
      this.voiceStatusBar = win.querySelector('#advisorVoiceStatusBar');
      this.voiceWave = win.querySelector('#advisorVoiceWave');
      this.voiceStatusText = win.querySelector('#advisorVoiceStatusText');
      this.voicePlayPauseBtn = win.querySelector('#advisorVoicePlayPauseBtn');
      this.voiceBtn = win.querySelector('#advisorVoiceBtn');
      this.langBtn = win.querySelector('#advisorLangToggleBtn');
      this.refreshBtn = win.querySelector('#advisorRefreshBtn');
      this.closeBtn = win.querySelector('#advisorCloseBtn');
      this.interruptMicBtn = win.querySelector('#advisorInterruptMicBtn');
      this.interruptInput = win.querySelector('#advisorInterruptInput');
      this.interruptSubmitBtn = win.querySelector('#advisorInterruptSubmitBtn');
      this.interruptChipsWrap = win.querySelector('#advisorInterruptChips');

      this.bindEvents();
    }

    bindEvents() {
      // Toggle button
      this.triggerPill.addEventListener('click', () => this.toggle());

      // Backdrop click
      this.backdrop.addEventListener('click', () => this.close());

      // Close button
      this.closeBtn.addEventListener('click', () => this.close());

      // Refresh button
      this.refreshBtn.addEventListener('click', () => this.autoRunFlawAudit());

      // Language toggle (Cleanly references this.langBtn with no scoped variable error)
      if (this.langBtn) {
        this.langBtn.addEventListener('click', () => {
          this.language = (this.language === 'ta') ? 'en' : 'ta';
          localStorage.setItem('argus_ai_voice_lang', this.language);
          const lbl = this.langBtn.querySelector('#advisorLangLabel');
          if (lbl) lbl.innerText = (this.language === 'ta') ? 'தமிழ்' : 'EN';
          this.autoRunFlawAudit();
        });
      }

      // Voice toggle
      this.voiceBtn.addEventListener('click', () => {
        this.voiceEnabled = !this.voiceEnabled;
        localStorage.setItem('argus_advisor_voice', this.voiceEnabled ? 'true' : 'false');
        this.voiceBtn.innerHTML = this.voiceEnabled ? '🔊' : '🔇';
        this.voiceBtn.classList.toggle('active', this.voiceEnabled);
        if (!this.voiceEnabled) {
          this.stopSpeaking();
          this.updateVoiceStatus('Voice Briefing Muted', false);
        } else {
          this.updateVoiceStatus('Voice Briefing Enabled', false);
        }
      });

      // Play / Pause voice briefing
      this.voicePlayPauseBtn.addEventListener('click', () => {
        if (this.isSpeaking) {
          this.stopSpeaking();
          this.updateVoiceStatus('Briefing Paused', false);
          this.voicePlayPauseBtn.innerHTML = '▶️ Resume';
        } else if (this.currentBriefingData) {
          const speechScript = (this.language === 'ta') ? (this.currentBriefingData.speech_ta || this.currentBriefingData.speech_en) : this.currentBriefingData.speech_en;
          this.speakReply(speechScript, this.currentBriefingData.speech_en);
          this.voicePlayPauseBtn.innerHTML = '⏸️ Pause';
        }
      });

      // Preset tabs
      const chips = this.consoleWindow.querySelectorAll('.advisor-preset-chip');
      chips.forEach((chip) => {
        chip.addEventListener('click', () => {
          chips.forEach(c => c.classList.remove('active-chip'));
          chip.classList.add('active-chip');
          const auditType = chip.getAttribute('data-audit');
          const title = chip.innerText.trim();
          this.runAudit(auditType, title);
        });
      });

      // Interruption Mic
      this.interruptMicBtn.addEventListener('click', () => {
        if (this.isListeningInterruption) {
          this.stopSpeechRecognition();
        } else {
          this.startSpeechRecognition();
        }
      });

      // Interruption Submit
      this.interruptSubmitBtn.addEventListener('click', () => this.handleInterruptionQuery());
      this.interruptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          this.handleInterruptionQuery();
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
          this.interruptMicBtn.classList.add('recording');
          this.interruptMicBtn.innerHTML = '🔴 Listening...';
          this.stopSpeaking();
          this.updateVoiceStatus('Listening for your strategic question...', true);
        };

        this.recognition.onresult = (event) => {
          const text = event.results[0][0].transcript;
          if (text) {
            this.interruptInput.value = text;
            this.handleInterruptionQuery();
          }
        };

        this.recognition.onerror = () => {
          this.stopSpeechRecognition();
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
      if (this.interruptMicBtn) {
        this.interruptMicBtn.classList.remove('recording');
        this.interruptMicBtn.innerHTML = '🎙️ Tap to Speak / Interrupt';
      }
      if (this.recognition) {
        try { this.recognition.stop(); } catch (e) {}
      }
    }

    updateVoiceStatus(text, isWaving) {
      if (this.voiceStatusText) this.voiceStatusText.innerText = text;
      if (this.voiceWave) {
        this.voiceWave.style.opacity = isWaving ? '1' : '0.2';
      }
    }

    populateInterruptChips(fleetCompanies) {
      if (!this.interruptChipsWrap) return;
      this.interruptChipsWrap.innerHTML = '<span class="advisor-interrupt-hint">💡 Tap or speak to ask Advisor AI:</span>';

      let sampleChips = [];
      if (this.isSystemAdmin && fleetCompanies && fleetCompanies.length) {
        fleetCompanies.slice(0, 4).forEach(c => {
          sampleChips.push(`What about ${c.name}?`);
        });
        sampleChips.push("Which company has highest advance debt?");
        sampleChips.push("Show timeout violations across tenants");
      } else {
        sampleChips = [
          "Why are timeouts flagged?",
          "How to recover employee advances?",
          "Workforce health recommendations",
          "Shift punctuality solutions"
        ];
      }

      sampleChips.forEach(chipText => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'advisor-inter-chip';
        btn.innerText = chipText;
        btn.addEventListener('click', () => {
          this.interruptInput.value = chipText;
          this.handleInterruptionQuery();
        });
        this.interruptChipsWrap.appendChild(btn);
      });
    }

    async loadBriefing() {
      try {
        const resp = await fetch('/api/ai/advisor/briefing');
        const data = await resp.json();
        if (data && data.success && data.kpis) {
          const k = data.kpis;
          const healthEl = this.consoleWindow.querySelector('#advKpiHealth');
          const liabEl = this.consoleWindow.querySelector('#advKpiLiability');
          const puncEl = this.consoleWindow.querySelector('#advKpiPunc');
          const staffEl = this.consoleWindow.querySelector('#advKpiStaff');

          if (this.isSystemAdmin) {
            if (healthEl) healthEl.innerText = `${k.health_index || 0}%`;
            if (liabEl) liabEl.innerText = `₹${(k.net_advance_liability || 0).toLocaleString()}`;
            if (puncEl) puncEl.innerText = `${k.total_timeouts || 0} Open`;
            if (staffEl) staffEl.innerText = `${k.present_count || 0} / ${k.total_staff || 0}`;
          } else {
            if (healthEl) healthEl.innerText = `${k.health_index || 0}%`;
            if (liabEl) liabEl.innerText = `₹${(k.net_advance_liability || 0).toLocaleString()}`;
            if (puncEl) puncEl.innerText = `${k.punctuality_score || 100}%`;
            if (staffEl) staffEl.innerText = `${k.present_today || 0} / ${k.total_staff || 0}`;
          }
        }
      } catch (e) {}
    }

    async autoRunFlawAudit() {
      this.showLoading(true);
      this.stopSpeaking();
      this.updateVoiceStatus('Analyzing organizational telemetry...', true);

      try {
        const resp = await fetch(`/api/ai/advisor/live-flaws?lang=${this.language}`);
        const data = await resp.json();
        this.showLoading(false);

        if (data && data.success) {
          this.currentBriefingData = data;
          this.renderStageContent(data.report_markdown);
          this.populateInterruptChips(data.fleet_companies || []);

          if (data.kpis) {
            const k = data.kpis;
            const healthEl = this.consoleWindow.querySelector('#advKpiHealth');
            const liabEl = this.consoleWindow.querySelector('#advKpiLiability');
            const puncEl = this.consoleWindow.querySelector('#advKpiPunc');
            const staffEl = this.consoleWindow.querySelector('#advKpiStaff');

            if (this.isSystemAdmin) {
              if (healthEl) healthEl.innerText = `${k.health_index || 0}%`;
              if (liabEl) liabEl.innerText = `₹${(k.net_advance_liability || 0).toLocaleString()}`;
              if (puncEl) puncEl.innerText = `${k.total_timeouts || 0} Open`;
              if (staffEl) staffEl.innerText = `${k.present_count || 0} / ${k.total_staff || 0}`;
            } else {
              if (healthEl) healthEl.innerText = `${k.health_index || 0}%`;
              if (liabEl) liabEl.innerText = `₹${(k.net_advance_liability || 0).toLocaleString()}`;
              if (puncEl) puncEl.innerText = `${k.total_timeouts || 0} Timeouts`;
              if (staffEl) staffEl.innerText = `${k.present_count || 0} / ${k.total_staff || 0}`;
            }
          }

          const speechScript = (this.language === 'ta') ? (data.speech_ta || data.speech_en) : data.speech_en;
          if (this.voiceEnabled) {
            this.speakReply(speechScript, data.speech_en);
          } else {
            this.updateVoiceStatus('Executive Briefing Ready', false);
          }
        } else {
          this.renderStageContent('### ⚠️ Unable to Compile Strategic Audit\nPlease retry in a moment.');
          this.updateVoiceStatus('Briefing Compilation Failed', false);
        }
      } catch (err) {
        this.showLoading(false);
        this.renderStageContent('### ⚠️ Connection Notice\nUnable to establish link with Advisor AI analytics service.');
        this.updateVoiceStatus('Connection Error', false);
      }
    }

    async runAudit(auditType, title) {
      this.showLoading(true);
      this.stopSpeaking();
      this.updateVoiceStatus(`Synthesizing ${title}...`, true);

      try {
        const resp = await fetch('/api/ai/advisor/consult', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audit_type: auditType, language: this.language })
        });
        const data = await resp.json();
        this.showLoading(false);

        if (data && data.success) {
          this.renderStageContent(data.reply);
          const speechScript = (this.language === 'ta') ? (data.speech_ta || data.speech || data.reply) : (data.speech_en || data.speech || data.reply);
          if (this.voiceEnabled) {
            this.speakReply(speechScript, data.speech_en || data.reply);
          } else {
            this.updateVoiceStatus(`${title} Ready`, false);
          }
        }
      } catch (e) {
        this.showLoading(false);
      }
    }

    // Handles live interruption query by the administrator
    async handleInterruptionQuery() {
      const query = this.interruptInput.value.trim();
      if (!query) return;

      // 1. Immediately halt current speech!
      this.stopSpeaking();
      this.stopSpeechRecognition();
      this.interruptInput.value = '';
      this.updateVoiceStatus(`Analyzing question: "${query}"...`, true);
      this.showLoading(true);

      try {
        const resp = await fetch('/api/ai/advisor/consult', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: query, language: this.language })
        });
        const data = await resp.json();
        this.showLoading(false);

        if (data && data.success) {
          this.renderStageContent(data.reply);
          const speechScript = (this.language === 'ta') ? (data.speech_ta || data.speech || data.reply) : (data.speech_en || data.speech || data.reply);
          if (this.voiceEnabled) {
            this.speakReply(speechScript, data.speech_en || data.reply);
          } else {
            this.updateVoiceStatus('Targeted Strategic Analysis Ready', false);
          }
        } else {
          this.renderStageContent(`### 💼 Advisor AI Assessment\n\nUnable to analyze specific query *'${query}'*. Please verify company name or query terms.`);
          this.updateVoiceStatus('Inquiry Unresolved', false);
        }
      } catch (err) {
        this.showLoading(false);
        this.renderStageContent('### ⚠️ Connection Notice\nError consulting Advisor AI.');
        this.updateVoiceStatus('Connection Error', false);
      }
    }

    renderStageContent(markdownText) {
      if (!this.stageContent) return;

      let html = (markdownText || '')
        .replace(/^### (.*$)/gim, '<h3 class="adv-stage-h3">$1</h3>')
        .replace(/^#### (.*$)/gim, '<h4 class="adv-stage-h4">$1</h4>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>');

      // Markdown Table Parser
      if (html.includes('|')) {
        const lines = html.split('\n');
        let inTable = false;
        let tableHtml = '<div class="adv-table-scroll"><table class="adv-stage-table">';
        let newLines = [];

        for (let i = 0; i < lines.length; i++) {
          const line = lines[i].trim();
          if (line.startsWith('|') && line.endsWith('|')) {
            if (!inTable) {
              inTable = true;
              newLines.push(tableHtml);
            }
            if (line.includes('---')) {
              continue; // separator
            }
            const cells = line.split('|').slice(1, -1).map(c => c.trim());
            const isHeader = (newLines.length > 0 && newLines[newLines.length - 1].includes('<table'));
            const tag = isHeader ? 'th' : 'td';
            let rowHtml = '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>';
            newLines.push(rowHtml);
          } else {
            if (inTable) {
              inTable = false;
              newLines.push('</table></div>');
            }
            newLines.push(line);
          }
        }
        if (inTable) newLines.push('</table></div>');
        html = newLines.join('\n');
      }

      html = html.replace(/\n/g, '<br>');
      this.stageContent.innerHTML = html;
      this.stageContent.scrollTop = 0;
    }

    showLoading(show) {
      if (this.loadingCard) this.loadingCard.style.display = show ? 'flex' : 'none';
      if (this.stageContent && show) this.stageContent.style.opacity = '0.35';
      if (this.stageContent && !show) this.stageContent.style.opacity = '1';
    }

    stopSpeaking() {
      this.isSpeaking = false;
      if (this.activeServerAudio) {
        try {
          this.activeServerAudio.pause();
          this.activeServerAudio.currentTime = 0;
        } catch (e) {}
        this.activeServerAudio = null;
      }
      if (window.speechSynthesis) {
        try { window.speechSynthesis.cancel(); } catch (e) {}
      }
      if (this.voiceWave) this.voiceWave.style.opacity = '0.2';
      if (this.voicePlayPauseBtn) this.voicePlayPauseBtn.innerHTML = '▶️ Resume';
    }

    speakReply(text, altEnglishText) {
      if (!text || this.voiceEnabled === false) return;
      this.stopSpeaking();
      this.isSpeaking = true;
      if (this.voicePlayPauseBtn) this.voicePlayPauseBtn.innerHTML = '⏸️ Pause';
      this.updateVoiceStatus('🔊 Speaking Executive Advisory...', true);

      const clean = text.replace(/[*_#`•⚠️📈🏢🚨|]/g, '').replace(/₹/g, ' rupees ').trim();

      if (this.language === 'ta') {
        if (window.speechSynthesis) {
          const voices = window.speechSynthesis.getVoices() || [];
          const taVoice = voices.find(v => {
            const lang = (v.lang || '').toLowerCase();
            const name = (v.name || '').toLowerCase();
            return lang.startsWith('ta') || name.includes('tamil') || name.includes('தமிழ்');
          });

          if (taVoice) {
            try {
              const utter = new SpeechSynthesisUtterance(clean);
              utter.voice = taVoice;
              utter.lang = taVoice.lang || 'ta-IN';
              utter.rate = 1.05;
              utter.onend = () => {
                this.isSpeaking = false;
                this.updateVoiceStatus('Briefing Completed', false);
              };
              window.speechSynthesis.speak(utter);
              return;
            } catch (err) {}
          }
        }

        try {
          const audio = new Audio('/api/voice/tamil-tts?text=' + encodeURIComponent(clean.slice(0, 950)) + '&lang=ta');
          audio.playbackRate = 1.1;
          this.activeServerAudio = audio;
          audio.onended = () => {
            this.isSpeaking = false;
            this.updateVoiceStatus('Briefing Completed', false);
          };
          audio.play().catch(e => {
            this.speakEnglishFallback(altEnglishText || clean);
          });
          return;
        } catch (e) {
          this.speakEnglishFallback(altEnglishText || clean);
        }
      } else {
        this.speakEnglishFallback(clean);
      }
    }

    speakEnglishFallback(text) {
      if (!window.speechSynthesis) return;
      try {
        const clean = (text || '').replace(/[*_#`•⚠️📈🏢🚨|]/g, '').replace(/₹/g, ' rupees ').trim();
        const utter = new SpeechSynthesisUtterance(clean);
        utter.rate = 1.05;
        const voices = window.speechSynthesis.getVoices() || [];
        const enVoice = voices.find(v => (v.lang === 'en-US' || v.lang === 'en-IN' || v.lang === 'en-GB')) ||
                        voices.find(v => (v.lang || '').toLowerCase().startsWith('en'));
        if (enVoice) utter.voice = enVoice;
        utter.onend = () => {
          this.isSpeaking = false;
          this.updateVoiceStatus('Briefing Completed', false);
        };
        window.speechSynthesis.speak(utter);
      } catch (e) {}
    }

    open() {
      this.isOpen = true;
      this.consoleWindow.classList.add('open');
      this.backdrop.classList.add('active');
      this.triggerPill.classList.add('active');

      const dock = document.getElementById('argusAiDock');
      if (dock) dock.classList.add('dock-hidden');

      if (window.argusCoworkerAI && window.argusCoworkerAI.isOpen) {
        window.argusCoworkerAI.close();
      }

      this.loadBriefing();
      this.autoRunFlawAudit();
    }

    close() {
      this.isOpen = false;
      this.consoleWindow.classList.remove('open');
      this.backdrop.classList.remove('active');
      this.triggerPill.classList.remove('active');

      const dock = document.getElementById('argusAiDock');
      if (dock) dock.classList.remove('dock-hidden');

      this.stopSpeaking();
      this.stopSpeechRecognition();
    }

    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    }
  }

  // Initialize on DOM load
  if (!window.argusAdvisorAI) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        if (!window.argusAdvisorAI) window.argusAdvisorAI = new AdvisorAIEngine();
      });
    } else {
      window.argusAdvisorAI = new AdvisorAIEngine();
    }
  }

})();
