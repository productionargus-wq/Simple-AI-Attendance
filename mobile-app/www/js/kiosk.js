/**
 * Shared Biometric Face Attendance Terminal Engine
 * Used by both Kiosk Terminal view and Employee Portal self-punch card.
 */
(function (window) {
  'use strict';

  var LEFT_EYE = { h1: 33, h2: 133, v1_top: 160, v1_bot: 144, v2_top: 158, v2_bot: 153 };
  var RIGHT_EYE = { h1: 362, h2: 263, v1_top: 385, v1_bot: 380, v2_top: 387, v2_bot: 373 };

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function dist2D(p1, p2) {
    var dx = p1.x - p2.x;
    var dy = p1.y - p2.y;
    return Math.sqrt(dx * dx + dy * dy);
  }

  function calculateEAR(landmarks, eye) {
    var p_h1 = landmarks[eye.h1], p_h2 = landmarks[eye.h2];
    var p_v1t = landmarks[eye.v1_top], p_v1b = landmarks[eye.v1_bot];
    var p_v2t = landmarks[eye.v2_top], p_v2b = landmarks[eye.v2_bot];
    if (!p_h1 || !p_h2 || !p_v1t || !p_v1b || !p_v2t || !p_v2b) return null;
    var hDist = dist2D(p_h1, p_h2);
    if (hDist <= 0.0001) return null;
    return (dist2D(p_v1t, p_v1b) + dist2D(p_v2t, p_v2b)) / (2.0 * hDist);
  }

  function evaluateFaceGuidance(landmarks, numFaces) {
    if (numFaces > 1) return 'multiple_faces';
    if (!landmarks || landmarks.length === 0) return 'no_face';
    var pTop = landmarks[10], pBot = landmarks[152];
    if (pTop && pBot) {
      var faceH = Math.abs(pBot.y - pTop.y);
      if (faceH < 0.27) return 'too_far';
      if (faceH > 0.78) return 'too_close';
    }
    var nose = landmarks[1];
    if (nose) {
      if (nose.x < 0.32 || nose.x > 0.68 || nose.y < 0.24 || nose.y > 0.76) return 'off_center';
    }
    var cheekL = landmarks[234], cheekR = landmarks[454];
    if (nose && cheekL && cheekR) {
      var distL = Math.abs(nose.x - cheekL.x);
      var distR = Math.abs(cheekR.x - nose.x);
      if (distL > 0.005 && distR > 0.005) {
        var ratio = distL / distR;
        if (ratio > 2.0 || ratio < 0.50) return 'looking_away';
      }
    }
    return 'aligned';
  }

  class ArgusBiometricTerminal {
    constructor(cfg) {
      this.el = cfg.elements;
      this.mode = cfg.mode || 'kiosk'; // 'kiosk' | 'portal'
      this.companyId = cfg.companyId || '';
      this.allowBlink = true;
      this.allowButton = false;
      this.onPunchSuccess = cfg.onPunchSuccess || null;

      this.stream = null;
      this.isCameraRunning = false;
      this.isHandsFreeActive = true;
      this.isProcessingPunch = false;
      this.cooldownUntil = 0;
      this.sensitivityMode = 'normal';

      this.faceMesh = null;
      this.faceMeshReady = false;
      this.isDetectionRunning = false;
      this.isProcessingFrame = false;
      this.animFrameId = null;
      this.lastDetectionTs = 0;
      this.lastMeshSeenTime = 0;

      this.isAIModelReady = false;
      this.aiWarmupTimer = null;
      this.hasAnnouncedWarmup = false;
      this.calibratedFrames = 0;
      this.currentGuidanceCandidate = null;
      this.guidanceCandidateStartTime = 0;
      this.hasSpokenAlignedGuidance = false;
      this.hasSpokenSteadyHold = false;

      this.blinkCount = 0;
      this.lastBlinkTime = 0;
      this.lastVerifiedBlinkTime = 0;
      this.pendingLivenessPunch = false;
      this.pendingLivenessTimer = null;
      this.isEyesClosed = false;
      this.closedFrameCount = 0;
      this.baselineEAR = 0.28;
      this.blinkResetTimer = null;
      this.autoDismissTimer = null;
      this.audioCtx = null;

      this.prewarmedCoords = null;
      this.bindEvents();
      this.applyModulesConfig();
    }

    setCompanyConfig(companyId, modules) {
      this.companyId = companyId || '';
      var mods = modules || {};
      this.allowBlink = mods.face_blink !== false;
      this.allowButton = Boolean(mods.face_button);
      this.applyModulesConfig();
    }

    applyModulesConfig() {
      var el = this.el;
      if (!this.allowBlink && this.allowButton) {
        this.isHandsFreeActive = false;
        if (el.btnHandsFree) el.btnHandsFree.classList.remove('active');
        if (el.handsFreeLabel) el.handsFreeLabel.textContent = 'Mode: One-Click Capture';
        if (el.btnSensitivity) el.btnSensitivity.style.display = 'none';
        if (el.blinkHudOverlay) el.blinkHudOverlay.style.display = 'none';
        if (el.btnMarkText) el.btnMarkText.textContent = this.mode === 'portal' ? 'Mark My Attendance' : 'Mark Attendance';
      } else if (this.allowBlink && !this.allowButton) {
        this.isHandsFreeActive = true;
        if (el.btnHandsFree) el.btnHandsFree.classList.add('active');
        if (el.handsFreeLabel) el.handsFreeLabel.textContent = 'Hands-Free: Active (Blink 2x)';
        if (el.btnSensitivity) el.btnSensitivity.style.display = '';
        if (el.btnMarkText) el.btnMarkText.textContent = this.mode === 'portal' ? 'Mark My Attendance' : 'Proceed to Next Person';
      } else {
        this.isHandsFreeActive = true;
        if (el.btnHandsFree) el.btnHandsFree.classList.add('active');
        if (el.handsFreeLabel) el.handsFreeLabel.textContent = 'Dual Mode: Blink 2x or Click';
        if (el.btnSensitivity) el.btnSensitivity.style.display = '';
        if (el.btnMarkText) el.btnMarkText.textContent = this.mode === 'portal' ? 'Mark My Attendance' : 'Mark Attendance';
      }
    }

    bindEvents() {
      var el = this.el;
      if (el.btnToggleCamera) {
        el.btnToggleCamera.addEventListener('click', () => {
          if (this.isCameraRunning) this.stopCamera();
          else this.startCamera();
        });
      }
      if (el.btnHandsFree) {
        el.btnHandsFree.addEventListener('click', () => {
          if (!this.allowBlink) return;
          this.isHandsFreeActive = !this.isHandsFreeActive;
          if (this.isHandsFreeActive) {
            el.btnHandsFree.classList.add('active');
            if (el.handsFreeLabel) el.handsFreeLabel.textContent = 'Hands-Free: Active (Blink 2x)';
            if (el.blinkHudOverlay && this.isCameraRunning) {
              el.blinkHudOverlay.style.display = 'flex';
              this.resetBlinkState();
              this.initFaceMesh();
              if (!this.isDetectionRunning) {
                this.isDetectionRunning = true;
                requestAnimationFrame(() => this.runDetectionLoop());
              }
            }
          } else {
            el.btnHandsFree.classList.remove('active');
            if (el.handsFreeLabel) el.handsFreeLabel.textContent = 'Hands-Free: Paused (Manual)';
            if (el.blinkHudOverlay) el.blinkHudOverlay.style.display = 'none';
            this.resetBlinkState();
          }
        });
      }
      if (el.btnSensitivity) {
        el.btnSensitivity.addEventListener('click', () => {
          this.sensitivityMode = this.sensitivityMode === 'normal' ? 'high' : 'normal';
          if (el.sensitivityLabel) {
            el.sensitivityLabel.textContent = this.sensitivityMode === 'high' ? 'High (Glasses)' : 'Normal';
          }
        });
      }
      if (el.btnMark) {
        el.btnMark.addEventListener('click', () => this.onMarkButtonClick());
      }
    }

    playChime(type) {
      try {
        var Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) return;
        if (!this.audioCtx) this.audioCtx = new Ctx();
        if (this.audioCtx.state === 'suspended') this.audioCtx.resume().catch(() => {});
        var osc = this.audioCtx.createOscillator();
        var gain = this.audioCtx.createGain();
        osc.connect(gain);
        gain.connect(this.audioCtx.destination);
        if (type === 'blink') {
          osc.type = 'sine';
          osc.frequency.setValueAtTime(659.25, this.audioCtx.currentTime);
          gain.gain.setValueAtTime(0.06, this.audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.12);
          osc.start();
          osc.stop(this.audioCtx.currentTime + 0.12);
        } else {
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(523.25, this.audioCtx.currentTime);
          osc.frequency.setValueAtTime(783.99, this.audioCtx.currentTime + 0.08);
          osc.frequency.setValueAtTime(1046.50, this.audioCtx.currentTime + 0.16);
          gain.gain.setValueAtTime(0.12, this.audioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + 0.35);
          osc.start();
          osc.stop(this.audioCtx.currentTime + 0.35);
        }
      } catch (e) {}
    }

    updateBlinkHUD(count, text, isCooldown, isWarmup, isSteady) {
      var el = this.el;
      if (!el.blinkHudOverlay || !el.blinkHudPill) return;
      if (isCooldown) {
        el.blinkHudPill.className = 'blink-hud-pill blink-cooldown';
        if (el.blinkHudIcon) el.blinkHudIcon.textContent = '⏳';
        if (el.blinkHudText) el.blinkHudText.textContent = text || 'Ready in a moment...';
        if (el.blinkHudDots) el.blinkHudDots.style.display = 'none';
        if (el.blinkEyeState) el.blinkEyeState.style.display = 'none';
        return;
      }
      if (isWarmup) {
        el.blinkHudPill.className = 'blink-hud-pill blink-warmup';
        if (el.blinkHudIcon) el.blinkHudIcon.textContent = '⚡';
        if (el.blinkHudText) el.blinkHudText.textContent = text || 'Starting Face AI...';
        if (el.blinkHudDots) el.blinkHudDots.style.display = 'none';
        if (el.blinkEyeState) el.blinkEyeState.style.display = 'none';
        return;
      }
      if (isSteady) {
        el.blinkHudPill.className = 'blink-hud-pill blink-steady';
        if (el.blinkHudIcon) el.blinkHudIcon.textContent = '✨';
        if (el.blinkHudText) el.blinkHudText.textContent = text || 'Hold steady...';
        if (el.blinkHudDots) el.blinkHudDots.style.display = 'none';
        if (el.blinkEyeState) el.blinkEyeState.style.display = 'inline-block';
        return;
      }
      if (el.blinkHudDots) el.blinkHudDots.style.display = 'inline-flex';
      if (el.blinkEyeState) el.blinkEyeState.style.display = 'inline-block';
      if (count === 0) {
        el.blinkHudPill.className = 'blink-hud-pill';
        if (el.blinkHudIcon) el.blinkHudIcon.textContent = '👁️';
        if (el.blinkHudText) el.blinkHudText.textContent = text || (this.isHandsFreeActive ? 'Blink 2 times or hold steady' : 'Ready to Mark');
        if (el.blinkDot1) el.blinkDot1.classList.remove('active');
        if (el.blinkDot2) el.blinkDot2.classList.remove('active');
      } else if (count === 1) {
        el.blinkHudPill.className = 'blink-hud-pill blink-stage-1';
        if (el.blinkHudIcon) el.blinkHudIcon.textContent = '👁️';
        if (el.blinkHudText) el.blinkHudText.textContent = text || '1st Blink! Blink once more...';
        if (el.blinkDot1) el.blinkDot1.classList.add('active');
        if (el.blinkDot2) el.blinkDot2.classList.remove('active');
      } else {
        el.blinkHudPill.className = 'blink-hud-pill blink-stage-2';
        if (el.blinkHudIcon) el.blinkHudIcon.textContent = '✨';
        if (el.blinkHudText) el.blinkHudText.textContent = text || '2 Blinks Verified! Recording...';
        if (el.blinkDot1) el.blinkDot1.classList.add('active');
        if (el.blinkDot2) el.blinkDot2.classList.add('active');
      }
    }

    resetBlinkState(message) {
      this.blinkCount = 0;
      this.isEyesClosed = false;
      this.closedFrameCount = 0;
      this.pendingLivenessPunch = false;
      this.hasSpokenSteadyHold = false;
      if (this.pendingLivenessTimer) {
        clearTimeout(this.pendingLivenessTimer);
        this.pendingLivenessTimer = null;
      }
      if (this.blinkResetTimer) {
        clearTimeout(this.blinkResetTimer);
        this.blinkResetTimer = null;
      }
      this.updateBlinkHUD(0, message || null);
    }

    reticlePulse() {
      var r = this.el.faceReticle;
      if (!r) return;
      r.style.borderColor = '#10b981';
      r.style.boxShadow = '0 0 25px rgba(16, 185, 129, 0.7)';
      setTimeout(() => {
        if (r) {
          r.style.borderColor = 'rgba(56, 189, 248, 0.55)';
          r.style.boxShadow = '0 0 15px rgba(56, 189, 248, 0.2)';
        }
      }, 1500);
    }

    handleBlinkDetected() {
      var now = Date.now();
      var pc = this.el.punchContainer;
      if (now < this.cooldownUntil || this.isProcessingPunch || (pc && pc.style.display === 'block')) return;
      if (this.blinkCount > 0 && now - this.lastBlinkTime > 4500) this.resetBlinkState();

      this.blinkCount++;
      this.lastBlinkTime = now;

      if (this.blinkCount === 1) {
        this.playChime('blink');
        this.updateBlinkHUD(1, '1st Blink Detected! Blink once more...');
        if (window.ArgusVoice) {
          window.ArgusVoice.speak({ tamil: 'இன்னொரு முறை சிமிட்டவும்.', english: 'Please blink once more.' });
        }
        if (this.blinkResetTimer) clearTimeout(this.blinkResetTimer);
        this.blinkResetTimer = setTimeout(() => {
          if (this.blinkCount === 1 && !this.isProcessingPunch) {
            this.resetBlinkState('Window expired. Blink 2 times to punch');
          }
        }, 4500);
      } else if (this.blinkCount >= 2) {
        if (this.blinkResetTimer) clearTimeout(this.blinkResetTimer);
        this.playChime('success');
        this.updateBlinkHUD(2, '✨ 2 Blinks Verified! Recording...');
        this.reticlePulse();
        this.executeAttendancePunch('blink');
      }
    }

    initFaceMesh() {
      if (typeof window.FaceMesh === 'undefined' || this.faceMesh) return;
      try {
        this.faceMesh = new window.FaceMesh({
          locateFile: (file) => 'vendor/mediapipe/' + file
        });
        this.faceMesh.setOptions({
          maxNumFaces: 1,
          refineLandmarks: false,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5
        });
        this.faceMesh.onResults((res) => this.onFaceMeshResults(res));
        this.faceMeshReady = true;
      } catch (err) {
        this.faceMeshReady = false;
      }
    }

    onFaceMeshResults(results) {
      if (!this.isCameraRunning || this.isProcessingPunch) return;
      var now = Date.now();
      if (now < this.cooldownUntil) {
        this.updateBlinkHUD(0, '✔ Punch Recorded! Cooldown: ' + Math.ceil((this.cooldownUntil - now) / 1000) + 's', true);
        return;
      }
      var pc = this.el.punchContainer;
      if (pc && pc.style.display === 'block') return;

      var landmarksList = results && results.multiFaceLandmarks;
      if (!landmarksList || landmarksList.length === 0) {
        if (this.el.blinkEyeState) {
          this.el.blinkEyeState.textContent = 'Detecting...';
          this.el.blinkEyeState.className = 'blink-eye-state';
        }
        if (this.el.faceReticle) {
          this.el.faceReticle.style.borderColor = 'rgba(56, 189, 248, 0.55)';
        }
        this.currentGuidanceCandidate = null;
        this.hasSpokenAlignedGuidance = false;
        this.hasSpokenSteadyHold = false;
        if (this.blinkCount > 0 && now - this.lastBlinkTime > 4500) this.resetBlinkState();
        if (this.isAIModelReady && now - this.lastMeshSeenTime > 6500 && window.ArgusVoice) {
          window.ArgusVoice.speakGuidance({
            tamil: 'வணக்கம்! கேமராவின் முன் நிற்கவும்.',
            english: 'Hello! Please stand in front of the camera.'
          });
        }
        return;
      }

      this.lastMeshSeenTime = now;
      var landmarks = landmarksList[0];
      if (!this.isAIModelReady) {
        this.calibratedFrames++;
        var initL = calculateEAR(landmarks, LEFT_EYE);
        var initR = calculateEAR(landmarks, RIGHT_EYE);
        if (initL !== null && initR !== null) {
          var initAvg = (initL + initR) / 2.0;
          if (initAvg > 0.16 && initAvg < 0.45) {
            this.baselineEAR = this.baselineEAR === 0.28 ? initAvg : (this.baselineEAR * 0.7 + initAvg * 0.3);
          }
        }
        if (this.calibratedFrames >= 3) {
          this.isAIModelReady = true;
          if (this.aiWarmupTimer) { clearTimeout(this.aiWarmupTimer); this.aiWarmupTimer = null; }
          this.updateBlinkHUD(0, this.isHandsFreeActive ? '👁️ Blink 2 times or hold steady' : '🟢 Ready to Mark');
        } else {
          return;
        }
      }

      var candidate = evaluateFaceGuidance(landmarks, landmarksList.length);
      if (candidate !== this.currentGuidanceCandidate) {
        this.currentGuidanceCandidate = candidate;
        this.guidanceCandidateStartTime = now;
        this.hasSpokenAlignedGuidance = false;
        this.hasSpokenSteadyHold = false;
      } else if (now - this.guidanceCandidateStartTime > 750) {
        if (candidate === 'multiple_faces') {
          if (this.el.faceReticle) this.el.faceReticle.style.borderColor = '#ef4444';
          this.updateBlinkHUD(0, '⚠️ One person at a time');
          return;
        } else if (candidate === 'too_far') {
          if (this.el.faceReticle) this.el.faceReticle.style.borderColor = '#f59e0b';
          this.updateBlinkHUD(0, '🔍 Move a little closer');
        } else if (candidate === 'too_close') {
          if (this.el.faceReticle) this.el.faceReticle.style.borderColor = '#f59e0b';
          this.updateBlinkHUD(0, '↔️ Step back slightly');
        } else if (candidate === 'off_center') {
          if (this.el.faceReticle) this.el.faceReticle.style.borderColor = '#f59e0b';
          this.updateBlinkHUD(0, '🎯 Center your face');
        } else if (candidate === 'looking_away') {
          if (this.el.faceReticle) this.el.faceReticle.style.borderColor = '#f59e0b';
          this.updateBlinkHUD(0, '👀 Look straight at camera');
        } else if (candidate === 'aligned') {
          if (this.el.faceReticle) this.el.faceReticle.style.borderColor = '#10b981';
          var alignedDuration = now - this.guidanceCandidateStartTime;
          if (this.blinkCount === 0 && !this.hasSpokenAlignedGuidance && alignedDuration > 900 && window.ArgusVoice) {
            this.hasSpokenAlignedGuidance = true;
            window.ArgusVoice.speakGuidance(this.allowBlink
              ? { tamil: 'முகத்தை நேராகப் பார்த்து இருமுறை கண் சிமிட்டவும்.', english: 'Look straight at the camera and blink twice.' }
              : { tamil: 'கேமராவை நேராகப் பார்த்து வருகைப் பதிவு செய்யவும்.', english: 'Look straight at the camera and tap Mark Attendance.' });
          }
          if (this.blinkCount === 0 && this.isHandsFreeActive && !this.isProcessingPunch && alignedDuration >= 2600) {
            if (!this.hasSpokenSteadyHold && window.ArgusVoice) {
              this.hasSpokenSteadyHold = true;
              window.ArgusVoice.speak({ tamil: 'அசையாமல் நிற்கவும்.', english: 'Please hold steady.' });
            }
            this.updateBlinkHUD(1, '✨ Hold steady — verifying...', false, false, true);
            if (alignedDuration >= 3800) {
              this.playChime('success');
              this.updateBlinkHUD(2, '✨ Face Verified! Recording...');
              this.reticlePulse();
              this.executeAttendancePunch('steady_face');
              return;
            }
          }
        }
      }

      var leftEAR = calculateEAR(landmarks, LEFT_EYE);
      var rightEAR = calculateEAR(landmarks, RIGHT_EYE);
      if (leftEAR === null || rightEAR === null) return;
      var avgEAR = (leftEAR + rightEAR) / 2.0;

      if (!this.isEyesClosed && avgEAR > 0.16) {
        this.baselineEAR = Math.max(0.18, Math.min(0.40, this.baselineEAR * 0.94 + avgEAR * 0.06));
      }
      var isHigh = this.sensitivityMode === 'high';
      var closeThresh = this.baselineEAR * (isHigh ? 0.88 : 0.85);
      var openThresh = this.baselineEAR * (isHigh ? 0.93 : 0.90);

      if (this.blinkCount > 0 && now - this.lastBlinkTime > 4500) {
        this.resetBlinkState('Window timed out. Blink 2 times to punch');
        return;
      }

      var eyeIsLow = (avgEAR < closeThresh) || (leftEAR < this.baselineEAR * 0.82) || (rightEAR < this.baselineEAR * 0.82);
      if (eyeIsLow) {
        this.closedFrameCount++;
        if (this.closedFrameCount >= 1 && this.closedFrameCount <= 25) {
          this.isEyesClosed = true;
          if (this.el.blinkEyeState) {
            this.el.blinkEyeState.textContent = 'Blink!';
            this.el.blinkEyeState.className = 'blink-eye-state eye-blink';
          }
        }
      } else if (avgEAR >= openThresh || (leftEAR >= openThresh && rightEAR >= openThresh)) {
        if (this.el.blinkEyeState) {
          this.el.blinkEyeState.textContent = 'Eye Open';
          this.el.blinkEyeState.className = 'blink-eye-state';
        }
        if (this.isEyesClosed && this.closedFrameCount >= 1 && this.closedFrameCount <= 25) {
          this.isEyesClosed = false;
          this.closedFrameCount = 0;
          this.lastVerifiedBlinkTime = Date.now();
          if (this.pendingLivenessPunch) {
            this.pendingLivenessPunch = false;
            if (this.pendingLivenessTimer) { clearTimeout(this.pendingLivenessTimer); this.pendingLivenessTimer = null; }
            this.updateBlinkHUD(2, '✨ Live Human Verified! Recording...');
            this.playChime('success');
            this.reticlePulse();
            this.executeAttendancePunch('button-liveness');
            return;
          }
          if (this.isHandsFreeActive) this.handleBlinkDetected();
        } else {
          this.isEyesClosed = false;
          this.closedFrameCount = 0;
        }
      }
    }

    async runDetectionLoop() {
      if (!this.isCameraRunning) {
        this.isDetectionRunning = false;
        return;
      }
      var now = Date.now();
      if (now < this.cooldownUntil) {
        this.updateBlinkHUD(0, 'Punch recorded ✔ Ready in ' + Math.ceil((this.cooldownUntil - now) / 1000) + 's', true);
      }
      if (!document.hidden && now - this.lastDetectionTs >= 100 && this.faceMeshReady && this.el.video && this.el.video.readyState >= 2 && !this.isProcessingPunch && !this.isProcessingFrame) {
        this.lastDetectionTs = now;
        this.isProcessingFrame = true;
        try {
          await this.faceMesh.send({ image: this.el.video });
        } catch (e) {
        } finally {
          this.isProcessingFrame = false;
        }
      }
      if (this.isCameraRunning) {
        this.animFrameId = requestAnimationFrame(() => this.runDetectionLoop());
      } else {
        this.isDetectionRunning = false;
      }
    }

    async startCamera() {
      var el = this.el;
      if (el.btnToggleCameraText) el.btnToggleCameraText.textContent = 'Starting...';
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }
        });
        el.video.srcObject = this.stream;
        el.video.style.display = 'block';
        if (el.cameraOverlay) el.cameraOverlay.style.display = 'none';
        if (el.faceReticle) el.faceReticle.style.display = 'block';
        this.isCameraRunning = true;
        if (el.btnToggleCameraText) el.btnToggleCameraText.textContent = 'Turn Off Camera';
        if (el.btnToggleCamera) el.btnToggleCamera.classList.add('active');
        if (window.ArgusVoice) {
          window.ArgusVoice.unlockAudio();
          window.ArgusVoice.speakGuidance({
            tamil: 'கேமரா தயார். நேராகப் பார்க்கவும்.',
            english: 'Camera is ready. Please look straight at the camera.'
          });
        }

        if (!this.allowBlink && this.allowButton) {
          if (el.blinkHudOverlay) el.blinkHudOverlay.style.display = 'none';
          this.isAIModelReady = true;
        } else {
          if (el.blinkHudOverlay) el.blinkHudOverlay.style.display = 'flex';
          this.isAIModelReady = false;
          this.calibratedFrames = 0;
          this.updateBlinkHUD(0, '⚡ AI Camera Starting...', false, true);
          this.resetBlinkState();
          this.initFaceMesh();
          if (!this.isDetectionRunning) {
            this.isDetectionRunning = true;
            requestAnimationFrame(() => this.runDetectionLoop());
          }
        }
      } catch (err) {
        if (el.cameraOverlay) {
          el.cameraOverlay.innerHTML = '<div class="camera-off-title" style="color:#fca5a5;">Camera Access Denied</div><div class="camera-off-subtitle">Allow camera permissions to punch attendance.</div>';
          el.cameraOverlay.style.display = 'flex';
        }
        if (el.btnToggleCameraText) el.btnToggleCameraText.textContent = 'Turn On Camera';
        if (el.btnToggleCamera) el.btnToggleCamera.classList.remove('active');
        this.isCameraRunning = false;
      }
    }

    stopCamera() {
      var el = this.el;
      if (this.aiWarmupTimer) { clearTimeout(this.aiWarmupTimer); this.aiWarmupTimer = null; }
      this.isAIModelReady = false;
      this.calibratedFrames = 0;
      if (this.stream) {
        this.stream.getTracks().forEach(t => t.stop());
        this.stream = null;
      }
      if (el.video) {
        el.video.srcObject = null;
        el.video.style.display = 'none';
      }
      if (el.faceReticle) el.faceReticle.style.display = 'none';
      if (el.blinkHudOverlay) el.blinkHudOverlay.style.display = 'none';
      this.isDetectionRunning = false;
      if (this.animFrameId) { cancelAnimationFrame(this.animFrameId); this.animFrameId = null; }
      this.resetBlinkState();
      if (el.cameraOverlay) {
        el.cameraOverlay.innerHTML = '<svg class="camera-off-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg><div class="camera-off-title">Camera is turned off</div><div class="camera-off-subtitle">Tap "Turn On Camera" to enable.</div>';
        el.cameraOverlay.style.display = 'flex';
      }
      this.isCameraRunning = false;
      if (el.btnToggleCameraText) el.btnToggleCameraText.textContent = 'Turn On Camera';
      if (el.btnToggleCamera) el.btnToggleCamera.classList.remove('active');
    }

    async getUserLocation() {
      try {
        var geoPlugin = window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Geolocation;
        if (geoPlugin) {
          var pos = await geoPlugin.getCurrentPosition({ enableHighAccuracy: true, timeout: 5000, maximumAge: 15000 });
          if (pos && pos.coords) {
            this.prewarmedCoords = { latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy };
            return this.prewarmedCoords;
          }
        }
      } catch (e) {}

      if (this.prewarmedCoords) return this.prewarmedCoords;
      return new Promise(resolve => {
        if (!navigator.geolocation) { resolve(null); return; }
        var settled = false;
        var timer = setTimeout(() => { if (!settled) { settled = true; resolve(null); } }, 3000);
        navigator.geolocation.getCurrentPosition(
          p => { clearTimeout(timer); if (!settled) { settled = true; this.prewarmedCoords = p.coords; resolve(p.coords); } },
          () => { clearTimeout(timer); if (!settled) { settled = true; resolve(null); } },
          { enableHighAccuracy: true, timeout: 3000, maximumAge: 15000 }
        );
      });
    }

    resetForNextPerson() {
      if (this.autoDismissTimer) { clearTimeout(this.autoDismissTimer); this.autoDismissTimer = null; }
      this.cooldownUntil = 0;
      if (this.el.punchContainer) {
        this.el.punchContainer.style.display = 'none';
        this.el.punchContainer.innerHTML = '';
      }
      this.currentGuidanceCandidate = null;
      this.hasSpokenAlignedGuidance = false;
      this.hasSpokenSteadyHold = false;
      this.resetBlinkState();
      if (this.el.btnMark) {
        this.el.btnMark.disabled = false;
        this.el.btnMark.classList.remove('btn-next-highlight');
      }
      if (this.el.btnMarkText) {
        this.el.btnMarkText.textContent = this.mode === 'portal'
          ? 'Mark My Attendance'
          : (this.allowButton ? 'Mark Attendance' : 'Proceed to Next Person');
      }
    }

    onMarkButtonClick() {
      if (this.isProcessingPunch) return;
      if (!this.isCameraRunning || !this.stream) {
        this.startCamera();
        return;
      }
      var pc = this.el.punchContainer;
      if ((pc && pc.style.display === 'block') || Date.now() < this.cooldownUntil) {
        this.resetForNextPerson();
        return;
      }
      if (this.allowButton) {
        this.executeAttendancePunch('button');
        return;
      }
      if (this.lastVerifiedBlinkTime && Date.now() - this.lastVerifiedBlinkTime <= 4500) {
        this.executeAttendancePunch('button');
      } else {
        this.pendingLivenessPunch = true;
        if (this.el.blinkHudOverlay && this.isCameraRunning) this.el.blinkHudOverlay.style.display = 'flex';
        this.updateBlinkHUD(1, '👁️ Liveness Check: Blink once to verify!');
        if (this.el.btnMark) this.el.btnMark.disabled = true;
        if (this.el.btnMarkText) this.el.btnMarkText.textContent = '👁️ Blink to Verify...';
        if (this.pendingLivenessTimer) clearTimeout(this.pendingLivenessTimer);
        this.pendingLivenessTimer = setTimeout(() => {
          if (this.pendingLivenessPunch && !this.isProcessingPunch) {
            this.pendingLivenessPunch = false;
            if (this.el.btnMark) this.el.btnMark.disabled = false;
            if (this.el.btnMarkText) this.el.btnMarkText.textContent = this.mode === 'portal' ? 'Mark My Attendance' : 'Proceed to Next Person';
            this.updateBlinkHUD(0, '⚠️ Liveness timed out. Blink to verify.');
          }
        }, 7000);
      }
    }

    async executeAttendancePunch(source) {
      if (this.isProcessingPunch) return;
      if (!this.isCameraRunning || !this.stream) {
        await this.startCamera();
        if (!this.isCameraRunning) return;
      }
      var el = this.el;
      this.isProcessingPunch = true;
      if (el.btnMark) el.btnMark.disabled = true;
      if (el.btnMarkText) el.btnMarkText.textContent = 'Verifying Face...';
      if (el.punchContainer) el.punchContainer.style.display = 'none';

      try {
        var coords = await this.getUserLocation();
        el.canvas.width = el.video.videoWidth || 640;
        el.canvas.height = el.video.videoHeight || 480;
        var ctx = el.canvas.getContext('2d');
        ctx.drawImage(el.video, 0, 0, el.canvas.width, el.canvas.height);
        var blob1 = await new Promise(r => el.canvas.toBlob(r, 'image/jpeg', 0.90));
        await new Promise(r => setTimeout(r, 200));
        ctx.drawImage(el.video, 0, 0, el.canvas.width, el.canvas.height);
        var blob2 = await new Promise(r => el.canvas.toBlob(r, 'image/jpeg', 0.90));
        if (!blob1) throw new Error('Unable to capture camera frame.');

        var now = new Date();
        var rawH = now.getHours();
        var ampm = rawH >= 12 ? 'PM' : 'AM';
        var h12 = rawH % 12 || 12;
        var clientTime = String(now.getDate()).padStart(2, '0') + '/' +
          String(now.getMonth() + 1).padStart(2, '0') + '/' + now.getFullYear() + ' ' +
          String(h12).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0') + ':' +
          String(now.getSeconds()).padStart(2, '0') + ' ' + ampm;

        var fd = new FormData();
        fd.append('photo', blob1, 'punch_frame.jpg');
        if (blob2) fd.append('burst_photo', blob2, 'burst_frame.jpg');
        if (coords && coords.latitude != null && coords.longitude != null) {
          fd.append('latitude', coords.latitude);
          fd.append('longitude', coords.longitude);
        }
        fd.append('client_time', clientTime);
        fd.append('punch_source', source || 'button');
        if (this.companyId) fd.append('company_id', this.companyId);

        var res = await window.ArgusConfig.apiFetch('/api/face/recognize', { method: 'POST', body: fd });
        var data = await res.json().catch(() => ({ matched: false, message: 'Server error. Please try again.' }));

        if (data && data.matched) {
          var isOut = data.punch_status === 'punch_out';
          var isAlready = Boolean(data.punch_status === 'already_punched_in' || data.already_punched_in);
          var badgeLabel = isAlready ? 'Punch In Active (On Duty)' : (isOut ? 'Punch Out Recorded' : 'Punch In Recorded');
          var badgeIcon = isAlready ? 'ℹ' : (isOut ? '⏏' : '✔');
          var empName = data.employee_name || 'Verified Employee';
          var punchTime = data.punch_time || clientTime;

          if (window.ArgusVoice) {
            if (isAlready) window.ArgusVoice.announceAlreadyPunched(empName);
            else if (isOut) window.ArgusVoice.announcePunchOut(empName, punchTime);
            else window.ArgusVoice.announcePunchIn(empName, punchTime);
          }

          var distInfo = (data.formatted_distance || '').trim();
          if (distInfo === '----' || distInfo === '-') distInfo = '';
          var isImproper = Boolean(data.geofence_enabled && (data.entry_type === 'improper' || data.is_improper));
          var geoPill = data.geofence_enabled
            ? (isImproper
              ? '<span style="background:#fee2e2;color:#b91c1c;padding:2px 8px;border-radius:999px;font-size:10.5px;font-weight:800;">⚠ ' + (data.gps_verified === false ? 'GPS Unverified (Improper)' : 'Outside Geofence (Improper)') + '</span>'
              : '<span style="background:#dcfce7;color:#15803d;padding:2px 8px;border-radius:999px;font-size:10.5px;font-weight:800;">✓ Within Geofence (Proper)</span>')
            : '';

          el.punchContainer.innerHTML =
            '<div class="punch-card-verified">' +
              '<div class="punch-header">' +
                '<span class="punch-badge-success"' + (isAlready ? ' style="background:#2563eb;"' : '') + '>' + badgeIcon + ' ' + badgeLabel + '</span>' +
                '<span class="punch-time-tag">' + escapeHtml(punchTime) + '</span>' +
              '</div>' +
              '<div class="punch-emp-name">' + escapeHtml(empName) + '</div>' +
              '<div class="punch-grid">' +
                '<div><span class="punch-grid-label">ID:</span> <span class="punch-grid-value">' + escapeHtml(data.employee_code || data.employee_id || '-') + '</span></div>' +
                '<div><span class="punch-grid-label">Role:</span> <span class="punch-grid-value">' + escapeHtml(data.designation || 'Staff') + '</span></div>' +
                '<div><span class="punch-grid-label">Dept:</span> <span class="punch-grid-value">' + escapeHtml(data.department || 'General') + '</span></div>' +
                '<div><span class="punch-grid-label">Biometric:</span> <span class="punch-conf-pill">' + (data.confidence ? escapeHtml(data.confidence) + '% Match' : 'Verified') + '</span></div>' +
                (data.working_hours && !isAlready ? '<div><span class="punch-grid-label">Hours:</span> <span class="punch-grid-value" style="color:#16a34a;">' + escapeHtml(data.working_hours) + '</span></div>' : '') +
              '</div>' +
              ((distInfo || data.live_location || geoPill)
                ? '<div class="punch-geo-badge">' +
                    (distInfo ? '<div>📍 ' + escapeHtml(distInfo) + '</div>' : '') +
                    (data.live_location ? '<div style="color:#475569;">' + escapeHtml(data.live_location) + '</div>' : '') +
                    (geoPill ? '<div>' + geoPill + '</div>' : '') +
                  '</div>'
                : '') +
            '</div>';
          el.punchContainer.style.display = 'block';
          if (typeof this.onPunchSuccess === 'function') this.onPunchSuccess(data);
        } else {
          var errMsg = (data && (data.message || data.error)) || 'Face not recognized.';
          var isSpoof = Boolean(data && data.spoof_detected);
          if (window.ArgusVoice) {
            if (isSpoof) window.ArgusVoice.announceSpoofDetected();
            else window.ArgusVoice.announceUnrecognized();
          }
          el.punchContainer.innerHTML =
            '<div class="punch-card-failed">' +
              '<div class="punch-header">' +
                '<span class="punch-badge-failed">⚠ ' + (isSpoof ? 'Anti-Spoofing Alert' : 'Verification Notice') + '</span>' +
                '<span class="punch-time-tag">' + escapeHtml(clientTime) + '</span>' +
              '</div>' +
              '<div style="font-size:13px;font-weight:700;color:#991b1b;">' + escapeHtml(errMsg) + '</div>' +
            '</div>';
          el.punchContainer.style.display = 'block';
        }
      } catch (err) {
        if (el.punchContainer) {
          el.punchContainer.innerHTML = '<div class="punch-card-failed"><div class="punch-header"><span class="punch-badge-failed">⚠ Connection Notice</span></div><div style="font-size:12.5px;color:#991b1b;">' + escapeHtml(err.message || 'Unable to reach attendance backend.') + '</div></div>';
          el.punchContainer.style.display = 'block';
        }
      } finally {
        this.isProcessingPunch = false;
        this.cooldownUntil = Date.now() + 15000;
        this.resetBlinkState();
        if (el.btnMark) {
          el.btnMark.disabled = false;
          el.btnMark.classList.add('btn-next-highlight');
        }
        if (el.btnMarkText) {
          el.btnMarkText.textContent = this.mode === 'portal' ? 'Ready for Next Punch →' : 'Proceed to Next Person →';
        }
        if (this.autoDismissTimer) clearTimeout(this.autoDismissTimer);
        this.autoDismissTimer = setTimeout(() => this.resetForNextPerson(), 10000);
      }
    }
  }

  window.ArgusBiometricTerminal = ArgusBiometricTerminal;
})(window);
