/**
 * ARGUS Co-Worker AI Engine (Agent 2)
 * -----------------------------------------------------------------
 * Autonomous WhatsApp-style Executive Assistant for Argus Web App.
 *
 * Capabilities:
 * - Shortcut trigger: Ctrl + Alt (or Ctrl + Alt + C / floating trigger pill)
 * - Dual-engine natural speech-to-text (Web Speech API + Gemini Audio STT)
 * - Autonomous task execution (Payments, Attendance, Leaves, Lookups, Navigation)
 * - WhatsApp chat interface with audio waveform and task cards
 */

(function (window) {
  'use strict';

  class ArgusCoworkerAI {
    constructor() {
      this.isOpen = false;
      this.voiceEnabled = localStorage.getItem('argus_coworker_voice') === 'true';
      this.history = [];
      this.recognition = null;
      this.isRecognizing = false;
      this.mediaRecorder = null;
      this.audioChunks = [];
      this.recordingTimer = null;
      this.recordingSeconds = 0;
      this.isAudioRecording = false;

      this.init();
    }

    init() {
      this.loadHistory();
      this.injectUI();
      this.bindEvents();
      this.initSpeechRecognition();
    }

    /* -------------------------------------------------------------------------
       1. CHAT HISTORY PERSISTENCE
       ------------------------------------------------------------------------- */
    loadHistory() {
      try {
        const stored = sessionStorage.getItem('argus_coworker_history');
        if (stored) {
          this.history = JSON.parse(stored);
        } else {
          this.history = [
            {
              sender: 'ai',
              text: 'Hello! I am your **Co-Worker AI**.\n\nYou can chat or speak to assign tasks like creating payments, adding attendance, or applying leaves.\n\n*Try:* *"Create a payment entry for Ramesh for ₹5,000 as Advance Repayment"*',
              time: this.formatTime(new Date()),
              task: null
            }
          ];
        }
      } catch (e) {
        this.history = [];
      }
    }

    saveHistory() {
      try {
        // Keep last 40 messages to avoid sessionStorage overflow
        const trimmed = this.history.slice(-40);
        sessionStorage.setItem('argus_coworker_history', JSON.stringify(trimmed));
      } catch (e) {}
    }

    formatTime(date) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /* -------------------------------------------------------------------------
       2. UI INJECTION & DOM CREATION
       ------------------------------------------------------------------------- */
    injectUI() {
      // 1. Shared Floating Action Dock & Co-Worker Circular Button
      let dock = document.getElementById('argusAiDock');
      if (!dock) {
        dock = document.createElement('div');
        dock.id = 'argusAiDock';
        dock.className = 'argus-ai-dock';
        document.body.appendChild(dock);
      }

      const circleBtn = document.createElement('button');
      circleBtn.className = 'argus-ai-circle-btn coworker-ai-btn';
      circleBtn.id = 'coworkerAiCircleBtn';
      circleBtn.setAttribute('data-tooltip', 'Co-Worker AI (Ctrl + Alt)');
      circleBtn.setAttribute('aria-label', 'Open Co-Worker AI');
      circleBtn.innerHTML = `
        <span class="argus-ai-icon">🤖</span>
        <span class="argus-ai-status-dot"></span>
      `;
      dock.appendChild(circleBtn);
      this.triggerPill = circleBtn;

      // 2. Backdrop
      const backdrop = document.createElement('div');
      backdrop.className = 'coworker-modal-backdrop';
      backdrop.id = 'coworkerBackdrop';
      document.body.appendChild(backdrop);
      this.backdrop = backdrop;

      // 3. WhatsApp Chat Window
      const win = document.createElement('div');
      win.className = 'coworker-chat-window';
      win.id = 'coworkerChatWindow';
      win.innerHTML = `
        <!-- HEADER -->
        <div class="coworker-chat-header">
          <div class="coworker-header-left">
            <div class="coworker-avatar-wrapper">
              <div class="coworker-avatar-img">🤖</div>
              <div class="coworker-online-dot"></div>
            </div>
            <div class="coworker-header-info">
              <span class="coworker-header-title">Co-Worker AI</span>
              <span class="coworker-header-status">Argus Executive Assistant • Online</span>
            </div>
          </div>
          <div class="coworker-header-actions">
            <button class="coworker-icon-btn coworker-voice-toggle-btn ${this.voiceEnabled ? 'active' : ''}" id="coworkerVoiceToggleBtn" title="Toggle Voice Responses (TTS)">
              ${this.voiceEnabled ? '🔊' : '🔇'}
            </button>
            <button class="coworker-icon-btn" id="coworkerClearChatBtn" title="Clear Conversation">
              🧹
            </button>
            <button class="coworker-icon-btn" id="coworkerCloseBtn" title="Close (Esc)">
              ✕
            </button>
          </div>
        </div>

        <!-- CHAT BODY -->
        <div class="coworker-chat-body" id="coworkerChatBody">
          <div class="coworker-date-pill">TODAY</div>
          <div id="coworkerMessagesContainer"></div>
          <div class="coworker-typing" id="coworkerTypingIndicator" style="display: none;">
            <div class="coworker-typing-dot"></div>
            <div class="coworker-typing-dot"></div>
            <div class="coworker-typing-dot"></div>
          </div>
        </div>

        <!-- QUICK CHIPS -->
        <div class="coworker-chips-container" id="coworkerChips">
          <div class="coworker-chip" data-prompt="Create a payment entry for ">💰 Create Payment</div>
          <div class="coworker-chip" data-prompt="How many employees are present today?">📋 Today's Attendance</div>
          <div class="coworker-chip" data-prompt="Apply leave for ">🏖️ Apply Leave</div>
          <div class="coworker-chip" data-prompt="Search employee details for ">🔍 Search Employee</div>
        </div>

        <!-- FOOTER / INPUT -->
        <div class="coworker-chat-footer">
          <!-- Voice Recording Bar Overlay -->
          <div class="coworker-recording-overlay" id="coworkerRecOverlay">
            <div class="coworker-recording-left">
              <div class="coworker-rec-dot"></div>
              <span class="coworker-rec-timer" id="coworkerRecTimer">00:00</span>
              <span class="coworker-rec-text">Listening to your voice...</span>
            </div>
            <button class="coworker-rec-stop-btn" id="coworkerRecStopBtn">Done</button>
          </div>

          <div class="coworker-input-wrapper">
            <textarea class="coworker-textarea" id="coworkerTextarea" placeholder="Type a task or hold mic to speak..." rows="1"></textarea>
          </div>
          <button class="coworker-mic-btn" id="coworkerMicBtn" title="Click or Hold to Speak">
            🎙️
          </button>
          <button class="coworker-send-btn" id="coworkerSendBtn" title="Send Task">
            ➤
          </button>
        </div>
      `;
      document.body.appendChild(win);
      this.chatWindow = win;

      this.messagesContainer = win.querySelector('#coworkerMessagesContainer');
      this.textarea = win.querySelector('#coworkerTextarea');
      this.micBtn = win.querySelector('#coworkerMicBtn');
      this.sendBtn = win.querySelector('#coworkerSendBtn');
      this.voiceToggleBtn = win.querySelector('#coworkerVoiceToggleBtn');
      this.clearBtn = win.querySelector('#coworkerClearChatBtn');
      this.closeBtn = win.querySelector('#coworkerCloseBtn');
      this.typingIndicator = win.querySelector('#coworkerTypingIndicator');
      this.recOverlay = win.querySelector('#coworkerRecOverlay');
      this.recTimer = win.querySelector('#coworkerRecTimer');
      this.recStopBtn = win.querySelector('#coworkerRecStopBtn');

      this.renderAllMessages();
    }

    /* -------------------------------------------------------------------------
       3. EVENT BINDINGS
       ------------------------------------------------------------------------- */
    bindEvents() {
      // Shortcut Listener: Ctrl + Alt or Ctrl + Alt + C
      window.addEventListener('keydown', (e) => {
        // Toggle on Ctrl + Alt (without other modifiers) or Ctrl + Alt + C
        if (e.ctrlKey && e.altKey && !e.shiftKey) {
          if (e.key === 'c' || e.key === 'C' || e.key === 'Control' || e.key === 'Alt') {
            e.preventDefault();
            this.toggle();
          }
        } else if (e.key === 'Escape' && this.isOpen) {
          e.preventDefault();
          this.close();
        }
      });

      // Trigger Pill click
      this.triggerPill.addEventListener('click', () => this.toggle());

      // Backdrop click
      this.backdrop.addEventListener('click', () => this.close());

      // Close button
      this.closeBtn.addEventListener('click', () => this.close());

      // Clear button
      this.clearBtn.addEventListener('click', () => this.clearChat());

      // Voice Toggle button
      this.voiceToggleBtn.addEventListener('click', () => {
        this.voiceEnabled = !this.voiceEnabled;
        localStorage.setItem('argus_coworker_voice', this.voiceEnabled ? 'true' : 'false');
        this.voiceToggleBtn.innerHTML = this.voiceEnabled ? '🔊' : '🔇';
        this.voiceToggleBtn.classList.toggle('active', this.voiceEnabled);
      });

      // Quick Chips click
      const chips = this.chatWindow.querySelectorAll('.coworker-chip');
      chips.forEach((chip) => {
        chip.addEventListener('click', () => {
          const prompt = chip.getAttribute('data-prompt') || '';
          this.textarea.value = prompt;
          this.textarea.focus();
          this.updateInputButtons();
        });
      });

      // Textarea input changes & Enter to send
      this.textarea.addEventListener('input', () => {
        this.autoGrowTextarea();
        this.updateInputButtons();
      });

      this.textarea.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          this.sendMessage();
        }
      });

      // Send Button click
      this.sendBtn.addEventListener('click', () => this.sendMessage());

      // Mic Button: Click to toggle dictation/recording
      this.micBtn.addEventListener('click', () => {
        if (this.isAudioRecording || this.isRecognizing) {
          this.stopSpeech();
        } else {
          this.startSpeech();
        }
      });

      // Stop recording overlay button
      this.recStopBtn.addEventListener('click', () => {
        this.stopSpeech();
      });
    }

    autoGrowTextarea() {
      this.textarea.style.height = 'auto';
      this.textarea.style.height = Math.min(this.textarea.scrollHeight, 100) + 'px';
    }

    updateInputButtons() {
      const hasText = this.textarea.value.trim().length > 0;
      if (hasText) {
        this.sendBtn.style.display = 'flex';
        this.micBtn.style.display = 'none';
      } else {
        this.sendBtn.style.display = 'none';
        this.micBtn.style.display = 'flex';
      }
    }

    /* -------------------------------------------------------------------------
       4. SPEECH RECOGNITION & NATURAL VOICE ENGINE
       ------------------------------------------------------------------------- */
    initSpeechRecognition() {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
      if (SpeechRecognition) {
        this.recognition = new SpeechRecognition();
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-IN'; // Indian English handles accents & Tanglish smoothly

        this.recognition.onstart = () => {
          this.isRecognizing = true;
          this.baseText = this.textarea.value.trim();
          this.showRecordingState(true);
        };

        this.recognition.onresult = (event) => {
          let accumulatedFinal = '';
          let currentInterim = '';

          for (let i = 0; i < event.results.length; ++i) {
            const transcript = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
              accumulatedFinal += transcript + ' ';
            } else {
              currentInterim += transcript;
            }
          }

          const prefix = this.baseText ? this.baseText + ' ' : '';
          this.textarea.value = (prefix + accumulatedFinal + currentInterim).trimStart();
          this.autoGrowTextarea();
          this.updateInputButtons();
        };

        this.recognition.onerror = (e) => {
          console.warn('Speech recognition warning:', e.error);
          this.stopSpeech();
        };

        this.recognition.onend = () => {
          this.isRecognizing = false;
          this.textarea.value = this.textarea.value.trim();
          this.showRecordingState(false);
        };
      }
    }

    async startSpeech() {
      // 1. If Web Speech API is supported, start it
      if (this.recognition) {
        try {
          this.recognition.start();
          return;
        } catch (e) {
          console.warn('Recognition start caught, trying MediaRecorder fallback:', e);
        }
      }

      // 2. High-Fidelity Gemini Audio Recording Fallback via MediaRecorder
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
          this.audioChunks = [];
          this.mediaRecorder = new MediaRecorder(stream);
          this.mediaRecorder.ondataavailable = (e) => {
            if (e.data && e.data.size > 0) this.audioChunks.push(e.data);
          };
          this.mediaRecorder.onstop = () => {
            stream.getTracks().forEach((track) => track.stop());
            this.uploadAndTranscribeAudio();
          };
          this.mediaRecorder.start();
          this.isAudioRecording = true;
          this.showRecordingState(true);
        } catch (err) {
          alert('Microphone permission required for voice command input.');
        }
      } else {
        alert('Speech recognition is not supported in this browser. Please type your message.');
      }
    }

    stopSpeech() {
      if (this.recognition && this.isRecognizing) {
        try {
          this.recognition.stop();
        } catch (e) {}
        this.isRecognizing = false;
      }

      if (this.mediaRecorder && this.isAudioRecording) {
        try {
          this.mediaRecorder.stop();
        } catch (e) {}
        this.isAudioRecording = false;
      }

      this.showRecordingState(false);
    }

    showRecordingState(active) {
      if (active) {
        this.recOverlay.classList.add('active');
        this.micBtn.classList.add('recording');
        this.recordingSeconds = 0;
        this.recTimer.innerText = '00:00';
        clearInterval(this.recordingTimer);
        this.recordingTimer = setInterval(() => {
          this.recordingSeconds++;
          const mins = String(Math.floor(this.recordingSeconds / 60)).padStart(2, '0');
          const secs = String(this.recordingSeconds % 60).padStart(2, '0');
          this.recTimer.innerText = `${mins}:${secs}`;
        }, 1000);
      } else {
        this.recOverlay.classList.remove('active');
        this.micBtn.classList.remove('recording');
        clearInterval(this.recordingTimer);
        this.updateInputButtons();
      }
    }

    async uploadAndTranscribeAudio() {
      if (!this.audioChunks || this.audioChunks.length === 0) return;
      const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
      const formData = new FormData();
      formData.append('audio_file', audioBlob, 'coworker_voice.webm');

      this.showTyping(true);
      try {
        const resp = await fetch('/api/ai/coworker/transcribe', {
          method: 'POST',
          body: formData
        });
        const res = await resp.json();
        if (res && res.success && res.transcript) {
          this.textarea.value = res.transcript;
          this.autoGrowTextarea();
          this.updateInputButtons();
          // Automatically send transcribed voice command
          this.sendMessage();
        } else {
          this.appendMessage('ai', "I couldn't hear that clearly. Could you please repeat or type it?");
        }
      } catch (err) {
        this.appendMessage('ai', 'Error processing audio note. Please try again or type directly.');
      } finally {
        this.showTyping(false);
      }
    }

    /* -------------------------------------------------------------------------
       5. CHAT MESSAGING & TASK EXECUTION
       ------------------------------------------------------------------------- */
    async sendMessage() {
      const text = this.textarea.value.trim();
      if (!text) return;

      // 1. Append user message to UI
      const timeStr = this.formatTime(new Date());
      this.appendMessage('user', text, timeStr);
      this.textarea.value = '';
      this.textarea.style.height = 'auto';
      this.updateInputButtons();

      // 2. Show typing indicator
      this.showTyping(true);

      // 3. Post to Backend Co-Worker Chat API
      try {
        const payload = {
          message: text,
          history: this.history.slice(-8), // Send recent context
          context: {
            url: window.location.pathname,
            title: document.title
          }
        };

        const resp = await fetch('/api/ai/coworker/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        const data = await resp.json();
        this.showTyping(false);

        if (data && data.success) {
          const aiReply = data.reply || 'Task completed.';
          const taskData = data.task_data || null;

          this.appendMessage('ai', aiReply, this.formatTime(new Date()), taskData);

          // Update dynamic chips for interactive next steps
          this.renderDynamicChips(taskData);

          // Voice feedback if enabled (interactively speaks back)
          if (this.voiceEnabled) {
            this.speakReply(aiReply);
          }

          // Handle client-side actions if dispatched
          if (data.action) {
            this.handleClientAction(data.action, taskData);
          }
        } else {
          const errReply = data.error || 'Sorry, I encountered an error while processing this request.';
          this.appendMessage('ai', errReply, this.formatTime(new Date()));
        }
      } catch (err) {
        this.showTyping(false);
        this.appendMessage('ai', 'Connection error. Please check your network or try again.', this.formatTime(new Date()));
      }
    }

    renderDynamicChips(taskData) {
      if (!this.chatWindow) return;
      const chipsContainer = this.chatWindow.querySelector('#coworkerChips');
      if (!chipsContainer) return;

      let chipPrompts = [];
      if (taskData && taskData.type === 'payment') {
        const emp = (taskData.details && taskData.details.Employee) ? taskData.details.Employee : '';
        chipPrompts = [
          { label: '💰 Check Balance', prompt: `Check payment balance for ${emp}` },
          { label: '➕ New Payment', prompt: `Create a payment entry for ` },
          { label: '📋 View Ledger', prompt: `Take me to payment entry` }
        ];
      } else if (taskData && taskData.type === 'attendance') {
        chipPrompts = [
          { label: '👥 Who is absent today?', prompt: `Who is absent today?` },
          { label: '📋 View Manual Entries', prompt: `Take me to manual entries` },
          { label: '💰 Check Payments', prompt: `Check total payments this month` }
        ];
      } else {
        chipPrompts = [
          { label: '💰 Create Payment', prompt: 'Create a payment entry for ' },
          { label: '📋 Today\'s Attendance', prompt: 'How many employees are present today?' },
          { label: '🏖️ Apply Leave', prompt: 'Apply leave for ' },
          { label: '🔍 Search Staff', prompt: 'Search employee details for ' }
        ];
      }

      chipsContainer.innerHTML = '';
      chipPrompts.forEach(item => {
        const chip = document.createElement('div');
        chip.className = 'coworker-chip';
        chip.setAttribute('data-prompt', item.prompt);
        chip.innerText = item.label;
        chip.addEventListener('click', () => {
          this.textarea.value = item.prompt;
          this.textarea.focus();
          this.updateInputButtons();
        });
        chipsContainer.appendChild(chip);
      });
    }

    speakReply(text) {
      if (!window.speechSynthesis) return;
      try {
        window.speechSynthesis.cancel();
        // Clean markdown symbols for cleaner TTS
        const clean = text.replace(/[*_#`]/g, '').replace(/₹/g, ' rupees ');
        const utterance = new SpeechSynthesisUtterance(clean);
        utterance.rate = 1.05;
        window.speechSynthesis.speak(utterance);
      } catch (e) {}
    }

    handleClientAction(action, data) {
      if (!action) return;
      if (action === 'navigate' && data && data.url) {
        setTimeout(() => {
          window.location.href = data.url;
        }, 1200);
      } else if (action === 'refresh_page') {
        setTimeout(() => {
          window.location.reload();
        }, 1500);
      } else if (action === 'switch_tab' && data && data.tab_id) {
        const tabEl = document.getElementById(data.tab_id);
        if (tabEl) tabEl.click();
      }
    }

    showTyping(show) {
      if (this.typingIndicator) {
        this.typingIndicator.style.display = show ? 'flex' : 'none';
        this.scrollToBottom();
      }
    }

    appendMessage(sender, text, timeStr, taskData = null) {
      const msgObj = {
        sender,
        text,
        time: timeStr || this.formatTime(new Date()),
        task: taskData
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
      row.className = `coworker-msg-row ${msg.sender}`;

      let taskHtml = '';
      if (msg.task) {
        taskHtml = this.generateTaskCardHtml(msg.task);
      }

      // Convert simple markdown bold/italic
      let formattedText = (msg.text || '')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');

      row.innerHTML = `
        <div class="coworker-msg-bubble">
          <div class="coworker-msg-content">${formattedText}</div>
          ${taskHtml}
          <div class="coworker-msg-footer">
            <span>${msg.time || ''}</span>
            ${msg.sender === 'user' ? '<span class="coworker-double-tick">✓✓</span>' : ''}
          </div>
        </div>
      `;

      this.messagesContainer.appendChild(row);
    }

    generateTaskCardHtml(task) {
      const type = task.type || 'payment';
      let title = 'Task Recorded';
      let badgeClass = 'payment';
      let icon = '💳';

      if (type === 'payment') {
        title = 'Payment Entry Created';
        badgeClass = 'payment';
        icon = '💳';
      } else if (type === 'attendance') {
        title = 'Attendance Logged';
        badgeClass = 'attendance';
        icon = '📅';
      } else if (type === 'leave') {
        title = 'Leave Application Submitted';
        badgeClass = 'leave';
        icon = '🏖️';
      }

      let gridItems = '';
      if (task.details) {
        for (const [key, val] of Object.entries(task.details)) {
          gridItems += `
            <div class="coworker-task-item">
              <span class="coworker-task-label">${key}</span>
              <span class="coworker-task-value">${val}</span>
            </div>
          `;
        }
      }

      let actionBtn = '';
      if (task.action_label && task.action_url) {
        actionBtn = `
          <button class="coworker-task-action-btn" onclick="window.location.href='${task.action_url}'">
            🔗 ${task.action_label}
          </button>
        `;
      }

      return `
        <div class="coworker-task-card ${badgeClass}">
          <div class="coworker-task-card-header">
            <span class="coworker-task-type-badge">${icon} ${title}</span>
          </div>
          <div class="coworker-task-grid">
            ${gridItems}
          </div>
          ${actionBtn}
        </div>
      `;
    }

    scrollToBottom() {
      setTimeout(() => {
        const body = document.getElementById('coworkerChatBody');
        if (body) body.scrollTop = body.scrollHeight;
      }, 50);
    }

    clearChat() {
      if (confirm('Clear Co-Worker AI chat conversation?')) {
        this.history = [];
        sessionStorage.removeItem('argus_coworker_history');
        this.renderAllMessages();
      }
    }

    /* -------------------------------------------------------------------------
       6. LIFECYCLE CONTROLS
       ------------------------------------------------------------------------- */
    open() {
      this.isOpen = true;
      this.backdrop.classList.add('active');
      this.chatWindow.classList.add('active');
      this.scrollToBottom();
      setTimeout(() => this.textarea.focus(), 150);
    }

    close() {
      this.isOpen = false;
      this.backdrop.classList.remove('active');
      this.chatWindow.classList.remove('active');
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

  // Initialize on DOMContentLoaded or immediately if ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      window.argusCoworker = new ArgusCoworkerAI();
    });
  } else {
    window.argusCoworker = new ArgusCoworkerAI();
  }

})(window);

