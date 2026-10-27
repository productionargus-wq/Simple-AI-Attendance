/**
 * ARGUS ADVISOR AI ENGINE (AGENT 3)
 * Strategic Management Intelligence & C-Suite Consultant
 * Shortcut: CTRL + SHIFT + ALT
 */

(function () {
  'use strict';

  class AdvisorAIEngine {
    constructor() {
      this.isOpen = false;
      this.voiceEnabled = localStorage.getItem('argus_advisor_voice') === 'true';
      this.history = [];
      this.isRecognizing = false;
      this.recognition = null;
      this.kpis = null;

      this.init();
    }

    init() {
      this.loadHistory();
      this.createUI();
      this.setupShortcuts();
      this.setupSpeechRecognition();
      this.renderAllMessages();
    }

    loadHistory() {
      try {
        const saved = sessionStorage.getItem('argus_advisor_history');
        if (saved) {
          this.history = JSON.parse(saved);
        } else {
          this.history = [
            {
              sender: 'advisor',
              text: 'Welcome to **Advisor AI Executive Boardroom**. I analyze your real-time workforce health, credit risks, advance liabilities, and punctuality patterns. How can I advise company leadership today?',
              time: this.formatTime(new Date()),
              highlights: null
            }
          ];
        }
      } catch (e) {
        this.history = [];
      }
    }

    saveHistory() {
      try {
        const trimmed = this.history.slice(-30);
        sessionStorage.setItem('argus_advisor_history', JSON.stringify(trimmed));
      } catch (e) {}
    }

    formatTime(date) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    createUI() {
      // 1. Shared Floating Dock & Circular Advisor Button
      let dock = document.getElementById('argusAiDock');
      if (!dock) {
        dock = document.createElement('div');
        dock.id = 'argusAiDock';
        dock.className = 'argus-ai-dock';
        document.body.appendChild(dock);
      }

      // Remove existing advisor circle buttons to prevent duplicate dock icons
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

      // 2. Modal Backdrop
      const oldBackdrop = document.getElementById('advisorModalBackdrop');
      if (oldBackdrop) oldBackdrop.remove();
      const backdrop = document.createElement('div');
      backdrop.className = 'advisor-modal-backdrop';
      backdrop.id = 'advisorModalBackdrop';
      document.body.appendChild(backdrop);
      this.backdrop = backdrop;

      // 3. Boardroom Console Window
      const oldWin = document.getElementById('advisorConsoleWindow');
      if (oldWin) oldWin.remove();
      const win = document.createElement('div');
      win.className = 'advisor-chat-window';
      win.id = 'advisorChatWindow';

      win.innerHTML = `
        <!-- HEADER -->
        <div class="advisor-header">
          <div class="advisor-header-left">
            <div class="advisor-avatar">
              💼
              <span class="advisor-online-dot"></span>
            </div>
            <div class="advisor-header-info">
              <div class="advisor-header-title">
                Advisor AI
                <span class="advisor-badge-pill">C-Suite Intelligence</span>
              </div>
              <div class="advisor-header-subtitle">Management Strategic Partner • Live</div>
            </div>
          </div>
          <div class="advisor-header-actions">
            <button class="advisor-icon-btn ${this.voiceEnabled ? 'active' : ''}" id="advisorVoiceBtn" title="Toggle Executive Audio Briefings">
              ${this.voiceEnabled ? '🔊' : '🔇'}
            </button>
            <button class="advisor-icon-btn" id="advisorClearBtn" title="Clear Executive History">
              🧹
            </button>
            <button class="advisor-icon-btn" id="advisorCloseBtn" title="Close (Esc)">
              ✕
            </button>
          </div>
        </div>

        <!-- LIVE EXECUTIVE KPI RIBBON -->
        <div class="advisor-kpi-ribbon" id="advisorKpiRibbon">
          <div class="advisor-kpi-card">
            <span class="advisor-kpi-label">Health Score</span>
            <span class="advisor-kpi-value green" id="advKpiHealth">--</span>
          </div>
          <div class="advisor-kpi-card">
            <span class="advisor-kpi-label">Advance Liability</span>
            <span class="advisor-kpi-value amber" id="advKpiLiability">--</span>
          </div>
          <div class="advisor-kpi-card">
            <span class="advisor-kpi-label">Punctuality</span>
            <span class="advisor-kpi-value indigo" id="advKpiPunc">--</span>
          </div>
          <div class="advisor-kpi-card">
            <span class="advisor-kpi-label">Present Today</span>
            <span class="advisor-kpi-value" id="advKpiStaff">--</span>
          </div>
        </div>

        <!-- STRATEGIC AUDIT PRESET BAR -->
        <div class="advisor-presets-bar">
          <div class="advisor-preset-chip" data-audit="health_audit">
            📊 Workforce Health Audit
          </div>
          <div class="advisor-preset-chip" data-audit="advance_risk">
            ⚠️ Advance Risk Radar
          </div>
          <div class="advisor-preset-chip" data-audit="latecomers">
            ⏰ Latecomers & Coverage
          </div>
          <div class="advisor-preset-chip" data-audit="executive_summary">
            📋 Executive Briefing
          </div>
        </div>

        <!-- CONVERSATION BODY -->
        <div class="advisor-chat-body" id="advisorChatBody">
          <!-- Messages will be rendered here -->
        </div>

        <!-- TYPING / REASONING INDICATOR -->
        <div class="advisor-typing-indicator" id="advisorTypingIndicator">
          <span>Synthesizing management insights</span>
          <div class="advisor-typing-dots">
            <span></span><span></span><span></span>
          </div>
        </div>

        <!-- FOOTER & INPUT BAR -->
        <div class="advisor-footer">
          <div class="advisor-input-wrapper">
            <textarea class="advisor-textarea" id="advisorInput" rows="1" placeholder="Consult Advisor AI (e.g. 'How can we reduce overtime costs this month?')..."></textarea>
            <button class="advisor-action-btn advisor-mic-btn" id="advisorMicBtn" title="Speak to Advisor AI">
              🎤
            </button>
            <button class="advisor-action-btn advisor-send-btn" id="advisorSendBtn" title="Send Strategic Inquiry">
              ➤
            </button>
          </div>
        </div>
      `;

      document.body.appendChild(win);
      this.chatWindow = win;

      // Selectors
      this.messagesContainer = win.querySelector('#advisorChatBody');
      this.textarea = win.querySelector('#advisorInput');
      this.sendBtn = win.querySelector('#advisorSendBtn');
      this.micBtn = win.querySelector('#advisorMicBtn');
      this.voiceBtn = win.querySelector('#advisorVoiceBtn');
      this.clearBtn = win.querySelector('#advisorClearBtn');
      this.closeBtn = win.querySelector('#advisorCloseBtn');
      this.typingIndicator = win.querySelector('#advisorTypingIndicator');

      this.bindEvents();
    }

    bindEvents() {
      // Toggle button click
      this.triggerPill.addEventListener('click', () => this.toggle());

      // Backdrop click
      this.backdrop.addEventListener('click', () => this.close());

      // Close button
      this.closeBtn.addEventListener('click', () => this.close());

      // Clear button
      this.clearBtn.addEventListener('click', () => this.clearChat());

      // Voice toggle
      this.voiceBtn.addEventListener('click', () => {
        this.voiceEnabled = !this.voiceEnabled;
        localStorage.setItem('argus_advisor_voice', this.voiceEnabled ? 'true' : 'false');
        this.voiceBtn.innerHTML = this.voiceEnabled ? '🔊' : '🔇';
        this.voiceBtn.classList.toggle('active', this.voiceEnabled);
      });

      // Quick preset audits
      const chips = this.chatWindow.querySelectorAll('.advisor-preset-chip');
      chips.forEach((chip) => {
        chip.addEventListener('click', () => {
          const auditType = chip.getAttribute('data-audit');
          const title = chip.innerText.trim();
          this.runAudit(auditType, title);
        });
      });

      // Textarea auto-resize & Enter key
      this.textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });

      this.textarea.addEventListener('input', () => {
        this.textarea.style.height = 'auto';
        this.textarea.style.height = Math.min(this.textarea.scrollHeight, 80) + 'px';
      });

      // Send button
      this.sendBtn.addEventListener('click', () => this.sendMessage());

      // Mic button
      this.micBtn.addEventListener('click', () => {
        if (this.isRecognizing) {
          this.stopSpeech();
        } else {
          this.startSpeech();
        }
      });
    }

    setupShortcuts() {
      window.addEventListener('keydown', (e) => {
        // Toggle on Ctrl + Shift + Alt
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
        this.recognition.lang = 'en-US';

        this.recognition.onstart = () => {
          this.isRecognizing = true;
          this.micBtn.classList.add('recording');
        };

        this.recognition.onresult = (event) => {
          const text = event.results[0][0].transcript;
          if (text) {
            this.textarea.value = text;
            this.sendMessage();
          }
        };

        this.recognition.onerror = () => {
          this.stopSpeech();
        };

        this.recognition.onend = () => {
          this.stopSpeech();
        };
      } catch (e) {}
    }

    startSpeech() {
      if (this.recognition && !this.isRecognizing) {
        try {
          this.recognition.start();
        } catch (e) {}
      }
    }

    stopSpeech() {
      this.isRecognizing = false;
      if (this.micBtn) this.micBtn.classList.remove('recording');
      if (this.recognition) {
        try {
          this.recognition.stop();
        } catch (e) {}
      }
    }

    async loadBriefing() {
      try {
        const resp = await fetch('/api/ai/advisor/briefing');
        const data = await resp.json();
        if (data && data.success && data.kpis) {
          this.kpis = data.kpis;
          const k = data.kpis;

          const healthEl = this.chatWindow.querySelector('#advKpiHealth');
          const liabEl = this.chatWindow.querySelector('#advKpiLiability');
          const puncEl = this.chatWindow.querySelector('#advKpiPunc');
          const staffEl = this.chatWindow.querySelector('#advKpiStaff');

          if (healthEl) healthEl.innerText = `${k.health_index || 0}%`;
          if (liabEl) liabEl.innerText = `₹${(k.net_advance_liability || 0).toLocaleString()}`;
          if (puncEl) puncEl.innerText = `${k.punctuality_score || 100}%`;
          if (staffEl) staffEl.innerText = `${k.present_today || 0} / ${k.total_staff || 0}`;
        }
      } catch (e) {}
    }

    async runAudit(auditType, title) {
      this.appendMessage('user', title);
      this.showTyping(true);

      try {
        const resp = await fetch('/api/ai/advisor/consult', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ audit_type: auditType })
        });
        const data = await resp.json();
        this.showTyping(false);

        if (data && data.success) {
          this.appendMessage('advisor', data.reply, this.formatTime(new Date()), data.highlights);
          if (this.voiceEnabled) {
            this.speakReply(data.reply);
          }
        } else {
          this.appendMessage('advisor', 'Unable to compile strategic audit at this time. Please retry.');
        }
      } catch (err) {
        this.showTyping(false);
        this.appendMessage('advisor', 'Connection error while communicating with Advisor AI.');
      }
    }

    async sendMessage() {
      const text = this.textarea.value.trim();
      if (!text) return;

      this.textarea.value = '';
      this.textarea.style.height = 'auto';

      this.appendMessage('user', text);
      this.showTyping(true);

      try {
        const resp = await fetch('/api/ai/advisor/consult', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: text })
        });
        const data = await resp.json();
        this.showTyping(false);

        if (data && data.success) {
          this.appendMessage('advisor', data.reply, this.formatTime(new Date()), data.highlights);
          if (this.voiceEnabled) {
            this.speakReply(data.reply);
          }
        } else {
          this.appendMessage('advisor', 'I encountered an error analyzing that inquiry. Please try again.');
        }
      } catch (err) {
        this.showTyping(false);
        this.appendMessage('advisor', 'Connection error while communicating with Advisor AI.');
      }
    }

    speakReply(text) {
      if (!window.speechSynthesis) return;
      try {
        window.speechSynthesis.cancel();
        // Clean markdown symbols for cleaner TTS
        const clean = text.replace(/[*_#`•]/g, '').replace(/₹/g, ' rupees ');
        const utterance = new SpeechSynthesisUtterance(clean);
        utterance.rate = 1.02;
        window.speechSynthesis.speak(utterance);
      } catch (e) {}
    }

    showTyping(show) {
      if (this.typingIndicator) {
        this.typingIndicator.style.display = show ? 'flex' : 'none';
        this.scrollToBottom();
      }
    }

    appendMessage(sender, text, timeStr, highlights = null) {
      const msgObj = {
        sender,
        text,
        time: timeStr || this.formatTime(new Date()),
        highlights: highlights || null
      };
      this.history.push(msgObj);
      this.saveHistory();
      this.renderMessageElement(msgObj);
      this.scrollToBottom();
    }

    renderAllMessages() {
      this.messagesContainer.innerHTML = '';
      this.history.forEach((m) => this.renderMessageElement(m));
      this.scrollToBottom();
    }

    renderMessageElement(msg) {
      const row = document.createElement('div');
      row.className = `advisor-msg-row ${msg.sender}`;

      let highlightsHtml = '';
      if (msg.highlights && typeof msg.highlights === 'object') {
        let items = '';
        for (const [k, v] of Object.entries(msg.highlights)) {
          items += `
            <div class="advisor-hl-item">
              <span class="advisor-hl-label">${k}</span>
              <span class="advisor-hl-value">${v}</span>
            </div>
          `;
        }
        highlightsHtml = `<div class="advisor-highlights-grid">${items}</div>`;
      }

      // Convert simple markdown headings & bold/italic
      let formattedText = (msg.text || '')
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');

      row.innerHTML = `
        <div class="advisor-msg-bubble">
          ${formattedText}
          ${highlightsHtml}
          <div class="advisor-msg-time">${msg.time || ''}</div>
        </div>
      `;

      this.messagesContainer.appendChild(row);
    }

    clearChat() {
      if (confirm('Clear Advisor AI executive conversation?')) {
        this.history = [];
        sessionStorage.removeItem('argus_advisor_history');
        this.renderAllMessages();
      }
    }

    scrollToBottom() {
      if (this.messagesContainer) {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
      }
    }

    open() {
      this.isOpen = true;
      this.chatWindow.classList.add('open');
      this.backdrop.classList.add('active');
      this.triggerPill.classList.add('active');

      // Hide dock to ensure clear view
      const dock = document.getElementById('argusAiDock');
      if (dock) dock.classList.add('dock-hidden');

      // Close Co-Worker AI if open to prevent screen clutter
      if (window.argusCoworkerAI && window.argusCoworkerAI.isOpen) {
        window.argusCoworkerAI.close();
      }

      this.loadBriefing();
      this.scrollToBottom();
      setTimeout(() => this.textarea.focus(), 150);
    }

    close() {
      this.isOpen = false;
      this.chatWindow.classList.remove('open');
      this.backdrop.classList.remove('active');
      this.triggerPill.classList.remove('active');

      const dock = document.getElementById('argusAiDock');
      if (dock) dock.classList.remove('dock-hidden');

      this.stopSpeech();
    }

    toggle() {
      if (this.isOpen) {
        this.close();
      } else {
        this.open();
      }
    }
  }

  // Initialize on DOM load (guarded against duplicate executions)
  if (window.__argusAdvisorAIInitialized && window.argusAdvisorAI) {
    // Already active
  } else {
    window.__argusAdvisorAIInitialized = true;
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        if (!window.argusAdvisorAI) {
          window.argusAdvisorAI = new AdvisorAIEngine();
        }
      });
    } else {
      if (!window.argusAdvisorAI) {
        window.argusAdvisorAI = new AdvisorAIEngine();
      }
    }
  }

})();
