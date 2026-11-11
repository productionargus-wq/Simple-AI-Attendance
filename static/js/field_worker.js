    let liveMap = null;
    let liveMapLayerGroup = null;
    let assignMap = null;
    let assignMarker = null;
    let assignCircle = null;
    let autoTrackTimer = null;
    let fwVideoStream = null;
    let autoRefreshTimer = null;
    let KNOWN_AI_INCIDENT_IDS = new Set();
    let ACTIVE_AI_INCIDENTS = [];

    // Web Audio API Dual-Tone Chime Synthesizer (Zero External Audio File Dependency)
    function playAiAlertChime() {
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        const ctx = new AudioCtx();
        const osc1 = ctx.createOscillator();
        const osc2 = ctx.createOscillator();
        const gain = ctx.createGain();
        osc1.type = 'sine';
        osc2.type = 'triangle';
        osc1.frequency.setValueAtTime(880, ctx.currentTime);
        osc1.frequency.exponentialRampToValueAtTime(1174.66, ctx.currentTime + 0.18);
        osc2.frequency.setValueAtTime(440, ctx.currentTime);
        osc2.frequency.exponentialRampToValueAtTime(587.33, ctx.currentTime + 0.18);
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(ctx.destination);
        osc1.start();
        osc2.start();
        osc1.stop(ctx.currentTime + 0.6);
        osc2.stop(ctx.currentTime + 0.6);
      } catch (e) {
        // Audio playback muted or blocked
      }
    }

    // Universal Table Search Filter
    function filterFieldTable(inputEl, tableId) {
      const q = (inputEl.value || '').trim().toLowerCase();
      const tbl = document.getElementById(tableId);
      if (!tbl) return;
      const rows = tbl.querySelectorAll('tbody tr');
      rows.forEach(row => {
        if (row.cells.length <= 1) return;
        const txt = row.textContent.toLowerCase();
        row.style.display = txt.includes(q) ? '' : 'none';
      });
    }

    // Real-Time Voice Announcer (Tamil AI Voice Assistant)
    let cachedFwTamilVoices = [];
    function updateFwTamilVoicesCache() {
      if (!('speechSynthesis' in window)) return;
      try {
        cachedFwTamilVoices = window.speechSynthesis.getVoices() || [];
      } catch (e) {
        cachedFwTamilVoices = [];
      }
    }
    if ('speechSynthesis' in window) {
      updateFwTamilVoicesCache();
      window.speechSynthesis.onvoiceschanged = updateFwTamilVoicesCache;
    }

    function getFwTamilVoice() {
      if (!cachedFwTamilVoices || cachedFwTamilVoices.length === 0) {
        updateFwTamilVoicesCache();
      }
      const voices = cachedFwTamilVoices;
      if (!voices || voices.length === 0) return null;

      // Priority 1: Exact regional match for Indian Tamil (ta-IN or ta_IN)
      let found = voices.find(v => v.lang === 'ta-IN' || v.lang === 'ta_IN');

      // Priority 2: Generic Tamil (ta) or Sri Lanka (ta-LK)
      if (!found) {
        found = voices.find(v => v.lang && v.lang.toLowerCase().startsWith('ta'));
      }

      // Priority 3: Search by voice name containing tamil keywords
      if (!found) {
        found = voices.find(v => {
          const n = (v.name || '').toLowerCase();
          return n.includes('tamil') || n.includes('தமிழ்') || n.includes('valluvar') || n.includes('pallavi');
        });
      }

      return found || null;
    }

    const FW_TAMIL_REG_MESSAGES = {
      NO_FACE: 'படம் ஏற்கப்படவில்லை. முகம் தெளிவாகத் தெரியவில்லை. வெளிச்சமான இடத்தில் கேமராவை நேராகப் பார்க்கவும்.',
      MULTIPLE_FACES: 'படம் ஏற்கப்படவில்லை. ஒன்றுக்கு மேற்பட்ட முகங்கள் உள்ளன. ஒருவர் மட்டுமே இருக்க வேண்டும்.',
      FACE_OCCLUDED: 'படம் ஏற்கப்படவில்லை. கையை முகத்திலிருந்து எடுத்துவிட்டு முழு முகத்தையும் காட்டவும்.',
      FACE_TOO_SMALL: 'படம் ஏற்கப்படவில்லை. முகம் மிகத் தொலைவில் உள்ளது. சற்று அருகில் வரவும்.',
      FACE_TOO_CLOSE: 'படம் ஏற்கப்படவில்லை. முகம் மிக அருகில் உள்ளது. சற்று பின்னால் நிற்கவும்.',
      TOO_DARK: 'படம் ஏற்கப்படவில்லை. வெளிச்சம் குறைவாக உள்ளது. வெளிச்சமான இடத்திற்கு செல்லவும்.',
      TOO_BRIGHT: 'படம் ஏற்கப்படவில்லை. அதிக ஒளிக்கீற்று அல்லது பிரகாசம் உள்ளது.',
      BLURRY: 'படம் ஏற்கப்படவில்லை. புகைப்படம் மங்கலாக உள்ளது. கேமராவை அசைக்காமல் பிடிக்கவும்.',
      HEAD_TILTED: 'படம் ஏற்கப்படவில்லை. தலையை சாய்க்காமல் நேராக வைக்கவும்.',
      EMBEDDING_FAILED: 'படம் ஏற்கப்படவில்லை. கேமராவை நேராகப் பார்த்து மீண்டும் முயற்சிக்கவும்.',
      SUCCESS: 'முகம் வெற்றிகரமாக ஏற்றுக்கொள்ளப்பட்டது!'
    };

    let activeFwTamilAudio = null;

    function stopFwSpeech() {
      if ('speechSynthesis' in window) {
        try { window.speechSynthesis.cancel(); } catch (e) {}
      }
      if (activeFwTamilAudio) {
        try {
          activeFwTamilAudio.pause();
          activeFwTamilAudio.currentTime = 0;
        } catch (e) {}
        activeFwTamilAudio = null;
      }
      if (window.ArgusCaptions) {
        try { window.ArgusCaptions.hide(true); } catch (e) {}
      }
    }

    function playFwServerTamilAudio(text) {
      if (!text) return;
      stopFwSpeech();
      try {
        const audio = new Audio('/api/voice/tamil-tts?text=' + encodeURIComponent(text) + '&lang=ta');
        audio.playbackRate = 1.3;
        activeFwTamilAudio = audio;
        audio.play().catch(e => {});
      } catch (err) {}
    }

    function isFwMobileDevice() {
      const ua = navigator.userAgent || '';
      const mobileRegex = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|mobile/i;
      const hasTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
      return mobileRegex.test(ua) || (hasTouch && window.innerWidth <= 1024);
    }

    function getFwEnglishVoice() {
      if (!('speechSynthesis' in window)) return null;
      const voices = window.speechSynthesis.getVoices();
      if (!voices || voices.length === 0) return null;
      let found = voices.find(v => {
        const n = (v.name || '').toLowerCase();
        return (v.lang === 'en-US' || v.lang === 'en-GB' || v.lang === 'en-IN') &&
               (n.includes('natural') || n.includes('david') || n.includes('zira') || n.includes('google') || n.includes('samantha'));
      });
      if (!found) found = voices.find(v => v.lang === 'en-US' || v.lang === 'en-GB' || v.lang === 'en-IN');
      if (!found) found = voices.find(v => v.lang && v.lang.toLowerCase().startsWith('en'));
      return found || voices[0] || null;
    }

    const FW_ENGLISH_REG_MESSAGES = {
      NO_FACE: 'Photo not accepted. No clear face detected. Please face the camera directly in good lighting.',
      MULTIPLE_FACES: 'Photo not accepted. Multiple faces detected. Only one person should be present.',
      FACE_OCCLUDED: 'Photo not accepted. Please remove hands from face and show your full face.',
      FACE_TOO_SMALL: 'Photo not accepted. Face is too far away. Please move closer.',
      FACE_TOO_CLOSE: 'Photo not accepted. Face is too close. Please step back slightly.',
      TOO_DARK: 'Photo not accepted. Lighting is too dim. Please move to a well-lit area.',
      TOO_BRIGHT: 'Photo not accepted. Too much glare or brightness.',
      BLURRY: 'Photo not accepted. Image is blurry. Please hold steady.',
      HEAD_TILTED: 'Photo not accepted. Please keep your head straight.',
      EMBEDDING_FAILED: 'Photo not accepted. Please face the camera directly and try again.',
      SUCCESS: 'Face photo verified and accepted successfully!'
    };

    function speakVoiceAlert(content) {
      if (!content) return;
      if (localStorage.getItem('argus_voice_assist') === 'false') return;

      const isMobile = isFwMobileDevice();

      if (!isMobile) {
        // Desktop: Speak in English using native desktop SpeechSynthesis
        let englishText = '';
        if (typeof content === 'object') {
          englishText = content.english || content.tamil || '';
        } else if (typeof content === 'string') {
          englishText = FW_ENGLISH_REG_MESSAGES[content] || content;
        }
        if (!englishText) return;

        if ('speechSynthesis' in window) {
          try {
            stopFwSpeech();
            const utterance = new SpeechSynthesisUtterance(englishText);
            const enVoice = getFwEnglishVoice();
            if (enVoice) utterance.voice = enVoice;
            utterance.lang = (enVoice && enVoice.lang) || 'en-US';
            utterance.rate = 1.0;
            utterance.pitch = 1.0;
            utterance.onend = () => { if (window.ArgusCaptions) window.ArgusCaptions.hide(false); };
            utterance.onerror = () => { if (window.ArgusCaptions) window.ArgusCaptions.hide(false); };
            if (window.ArgusCaptions) {
              window.ArgusCaptions.show(englishText, { lang: utterance.lang });
            }
            window.speechSynthesis.speak(utterance);
            return;
          } catch (err) {
            console.warn('Desktop English SpeechSynthesis error:', err);
          }
        }
        return;
      }

      // Mobile: Preserve pure Tamil speech
      let tamilText = '';
      if (typeof content === 'object') {
        tamilText = content.tamil || content.english || '';
      } else if (typeof content === 'string') {
        tamilText = FW_TAMIL_REG_MESSAGES[content] || content;
      }
      if (!tamilText) return;

      const tamilVoice = getFwTamilVoice();
      if (tamilVoice && ('speechSynthesis' in window)) {
        try {
          stopFwSpeech();
          const utterance = new SpeechSynthesisUtterance(tamilText);
          utterance.rate = 1.3;
          utterance.pitch = 1.0;
          utterance.voice = tamilVoice;
          utterance.lang = tamilVoice.lang || 'ta-IN';
          window.speechSynthesis.speak(utterance);
          return;
        } catch (err) {
          console.warn('Tamil speech synthesis alert notice:', err);
        }
      }

      playFwServerTamilAudio(tamilText);
    }

    // Photo Upload & Real-Time Biometric Quality Verification
    async function handlePhotoUpload(input) {
      if (!input.files || !input.files[0]) return;
      const file = input.files[0];
      const statusEl = document.getElementById('fwRegPhotoStatus');
      const previewBox = document.getElementById('fwPhotoPreviewContainer');
      const dataInp = document.getElementById('fwRegPhotoData');

      if (statusEl) {
        statusEl.innerHTML = `<span style="color:#0284c7; font-size:11.5px; font-weight:600;"><i class="fa-solid fa-spinner fa-spin"></i> Analyzing face position, lighting & clarity in ${file.name}...</span>`;
      }
      if (previewBox) {
        previewBox.innerHTML = `<img src="${URL.createObjectURL(file)}" style="width:100%; height:100%; object-fit:cover;">`;
      }

      try {
        const fd = new FormData();
        fd.append('photo', file);
        const res = await fetch('/api/face/extract-biometrics', {
          method: 'POST',
          body: fd
        });
        let resData = null;
        try {
          const raw = await res.text();
          resData = JSON.parse(raw);
        } catch (e) {
          resData = null;
        }

        if (res.ok && resData && resData.success && resData.embedding) {
          if (dataInp) dataInp.value = resData.photo_data || '';
          speakVoiceAlert({
            tamil: (resData && resData.spoken_tamil_message) || FW_TAMIL_REG_MESSAGES.SUCCESS,
            english: (resData && resData.spoken_message) || FW_ENGLISH_REG_MESSAGES.SUCCESS
          });
          if (statusEl) {
            statusEl.innerHTML = `
              <div style="background:#f0fdf4; border:1px solid #86efac; border-radius:6px; padding:8px 10px; margin-top:4px;">
                <div style="color:#15803d; font-weight:800; font-size:11.5px; display:flex; align-items:center; gap:6px;">
                  <i class="fa-solid fa-circle-check"></i>
                  <span>FACE VERIFIED &amp; APPROVED</span>
                </div>
                <div style="color:#166534; font-size:10.5px; margin-top:2px;">
                  Face position, lighting, and clarity approved for AI attendance.
                </div>
              </div>
            `;
          }
        } else {
          const warn = (resData && resData.error) ? resData.error : 'No clear face detected in photo.';
          const spokenTamil = (resData && (resData.spoken_tamil_error || (resData.code && FW_TAMIL_REG_MESSAGES[resData.code]))) ||
                         ('படம் ஏற்கப்படவில்லை. ' + warn);
          const spokenEnglish = (resData && (resData.spoken_error || resData.error || (resData.code && FW_ENGLISH_REG_MESSAGES[resData.code]))) ||
                         ('Image not accepted. ' + warn);
          const advice = (resData && resData.advice) ? resData.advice : '';

          // Read rejection message aloud (Tamil on Mobile, English on Desktop)
          speakVoiceAlert({ tamil: spokenTamil, english: spokenEnglish });

          // Clear inputs so bad image cannot be submitted
          input.value = '';
          if (dataInp) dataInp.value = '';
          if (previewBox) {
            previewBox.innerHTML = '<i class="fa-solid fa-user" style="color:#94a3b8; font-size:18px;"></i>';
          }

          if (statusEl) {
            statusEl.innerHTML = `
              <div style="background:#fef2f2; border:1px solid #f87171; border-radius:6px; padding:9px 11px; margin-top:4px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
                <div style="display:flex; align-items:center; gap:6px; color:#b91c1c; font-weight:800; font-size:11.5px;">
                  <i class="fa-solid fa-triangle-exclamation"></i>
                  <span>IMAGE NOT ACCEPTED</span>
                </div>
                <div style="color:#7f1d1d; font-size:11px; margin-top:3px; font-weight:600; line-height:1.35;">
                  ${warn}
                </div>
                ${advice ? `<div style="color:#991b1b; font-size:10.5px; margin-top:3px; font-style:italic;">💡 Tip: ${advice}</div>` : ''}
              </div>
            `;
          }
        }
      } catch (err) {
        if (statusEl) {
          statusEl.innerHTML = `<span style="color:#dc2626; font-size:11px;">⚠️ Verification error: ${err.message}</span>`;
        }
      }
    }

    // Webcam Photo Snapshot for Quick Registration & Real-Time Biometric Quality Check
    async function triggerWebcamCapture() {
      const statusEl = document.getElementById('fwRegPhotoStatus');
      const previewBox = document.getElementById('fwPhotoPreviewContainer');
      const dataInp = document.getElementById('fwRegPhotoData');

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',
            width: { ideal: 640 },
            height: { ideal: 480 }
          }
        });
        const video = document.createElement('video');
        video.srcObject = stream;
        video.autoplay = true;
        await new Promise(r => setTimeout(r, 650));
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext('2d');
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        stream.getTracks().forEach(t => t.stop());

        if (statusEl) {
          statusEl.innerHTML = `<span style="color:#0284c7; font-size:11.5px; font-weight:600;"><i class="fa-solid fa-spinner fa-spin"></i> Analyzing face position, lighting & clarity...</span>`;
        }

        canvas.toBlob(async function(blob) {
          if (!blob) return;
          try {
            const fd = new FormData();
            fd.append('photo', blob, 'webcam_snap.jpg');
            const res = await fetch('/api/face/extract-biometrics', {
              method: 'POST',
              body: fd
            });
            let resData = null;
            try {
              const raw = await res.text();
              resData = JSON.parse(raw);
            } catch (e) {
              resData = null;
            }

            if (res.ok && resData && resData.success && resData.embedding) {
              if (dataInp) dataInp.value = resData.photo_data || '';
              if (previewBox) {
                previewBox.innerHTML = `<img src="${resData.photo_data || URL.createObjectURL(blob)}" style="width:100%; height:100%; object-fit:cover;">`;
              }
              speakVoiceAlert({
                tamil: (resData && resData.spoken_tamil_message) || FW_TAMIL_REG_MESSAGES.SUCCESS,
                english: (resData && resData.spoken_message) || FW_ENGLISH_REG_MESSAGES.SUCCESS
              });
              if (statusEl) {
                statusEl.innerHTML = `
                  <div style="background:#f0fdf4; border:1px solid #86efac; border-radius:6px; padding:8px 10px; margin-top:4px;">
                    <div style="color:#15803d; font-weight:800; font-size:11.5px; display:flex; align-items:center; gap:6px;">
                      <i class="fa-solid fa-circle-check"></i>
                      <span>FACE VERIFIED &amp; APPROVED</span>
                    </div>
                    <div style="color:#166534; font-size:10.5px; margin-top:2px;">
                      Snapshot approved for AI attendance recognition.
                    </div>
                  </div>
                `;
              }
            } else {
              const warn = (resData && resData.error) ? resData.error : 'No clear face detected in snapshot.';
              const spokenTamil = (resData && (resData.spoken_tamil_error || (resData.code && FW_TAMIL_REG_MESSAGES[resData.code]))) ||
                             ('படம் ஏற்கப்படவில்லை. ' + warn);
              const spokenEnglish = (resData && (resData.spoken_error || resData.error || (resData.code && FW_ENGLISH_REG_MESSAGES[resData.code]))) ||
                             ('Image not accepted. ' + warn);
              const advice = (resData && resData.advice) ? resData.advice : '';

              speakVoiceAlert({ tamil: spokenTamil, english: spokenEnglish });

              if (dataInp) dataInp.value = '';
              if (previewBox) {
                previewBox.innerHTML = '<i class="fa-solid fa-user" style="color:#94a3b8; font-size:18px;"></i>';
              }

              if (statusEl) {
                statusEl.innerHTML = `
                  <div style="background:#fef2f2; border:1px solid #f87171; border-radius:6px; padding:9px 11px; margin-top:4px;">
                    <div style="display:flex; align-items:center; gap:6px; color:#b91c1c; font-weight:800; font-size:11.5px;">
                      <i class="fa-solid fa-triangle-exclamation"></i>
                      <span>SNAPSHOT NOT ACCEPTED</span>
                    </div>
                    <div style="color:#7f1d1d; font-size:11px; margin-top:3px; font-weight:600;">
                      ${warn}
                    </div>
                    ${advice ? `<div style="color:#991b1b; font-size:10.5px; margin-top:3px; font-style:italic;">💡 Tip: ${advice}</div>` : ''}
                  </div>
                `;
              }
            }
          } catch (netErr) {
            if (statusEl) statusEl.innerHTML = `<span style="color:#dc2626; font-size:11px;">⚠️ Snapshot upload error: ${netErr.message}</span>`;
          }
        }, 'image/jpeg', 0.9);
      } catch (err) {
        showToast('Webcam capture error: ' + err.message, true);
      }
    }

    // Field Worker Tab Access & Permissions helpers
    function toggleAllFieldPermissions(checkState) {
      document.querySelectorAll('input[name="fwTabPerm"]').forEach(cb => {
        cb.checked = !!checkState;
      });
    }

    function setFieldWorkerPermissionCheckboxes(allowedList) {
      const cbs = document.querySelectorAll('input[name="fwTabPerm"]');
      if (!allowedList || !Array.isArray(allowedList) || allowedList.length === 0) {
        // By default check standard tabs, leave live monitor unticked unless specifically desired
        cbs.forEach(cb => {
          cb.checked = (cb.value !== 'paneLiveTracking');
        });
      } else {
        cbs.forEach(cb => {
          cb.checked = allowedList.includes(cb.value);
        });
      }
    }

    // Modal Controllers: Register Worker & Add Lead
    function openRegisterWorkerModal(resetMode = true) {
      const modal = document.getElementById('registerWorkerModalBackdrop');
      if (!modal) return;
      if (resetMode) {
        const form = document.getElementById('registerFieldWorkerForm');
        if (form) form.reset();
        const sel = document.getElementById('fwExistingEmpSelect');
        if (sel) sel.value = '';
        const title = document.getElementById('regModalTitle');
        if (title) title.textContent = 'Register Field Worker & Configure Field Incentives';
        const photoPreview = document.getElementById('fwPhotoPreviewContainer');
        if (photoPreview) photoPreview.innerHTML = '<i class="fa-solid fa-user" style="color:#94a3b8; font-size:18px;"></i>';
        const photoData = document.getElementById('fwRegPhotoData');
        if (photoData) photoData.value = '';
        const unitKmInput = document.getElementById('fwRegPetrolUnitKm');
        if (unitKmInput) unitKmInput.value = '1 KM';
        const rateInrInput = document.getElementById('fwRegPetrolRateInr');
        if (rateInrInput) rateInrInput.value = '';
        if (typeof updateWorkerPetrolRatePreview === 'function') updateWorkerPetrolRatePreview();
        setFieldWorkerPermissionCheckboxes(null);
      }
      modal.classList.remove('d-none');
    }

    function updateWorkerPetrolRatePreview() {
      const unitKm = 1.0;
      const rateInrVal = document.getElementById('fwRegPetrolRateInr')?.value;
      const rateInr = (rateInrVal !== '' && rateInrVal !== null && !isNaN(parseFloat(rateInrVal))) ? parseFloat(rateInrVal) : 0;
      const badge = document.getElementById('fwRegPetrolPreviewBadge');
      const kmRateInput = document.getElementById('fwRegKmRate');
      if (rateInr > 0) {
        const perKm = rateInr.toFixed(2);
        if (badge) {
          badge.textContent = `Worker Custom: ₹${perKm} / KM`;
          badge.style.background = '#dcfce7';
          badge.style.color = '#15803d';
          badge.style.borderColor = '#86efac';
        }
        if (kmRateInput) kmRateInput.value = perKm;
      } else {
        if (badge) {
          badge.textContent = 'Using Company Default';
          badge.style.background = '#f1f5f9';
          badge.style.color = '#475569';
          badge.style.borderColor = '#cbd5e1';
        }
        if (kmRateInput) kmRateInput.value = '';
      }
    }

    function closeRegisterWorkerModal() {
      const modal = document.getElementById('registerWorkerModalBackdrop');
      if (modal) modal.classList.add('d-none');
    }

    function openAddLeadModal() {
      const modal = document.getElementById('addLeadModalBackdrop');
      if (!modal) return;
      modal.classList.remove('d-none');
      // Auto-acquire current location coordinates
      acquireVisitGPSLocation();
      // Ensure warehouse products are fresh
      if (!CURRENT_WAREHOUSE_PRODUCTS || CURRENT_WAREHOUSE_PRODUCTS.length === 0 || CURRENT_WAREHOUSE_PRODUCTS.some(p => p.qty === undefined || p.qty === null)) {
        loadWarehouseProducts();
      }
    }

    function closeAddLeadModal() {
      closeProductDropdown();
      const modal = document.getElementById('addLeadModalBackdrop');
      if (modal) modal.classList.add('d-none');
    }

    async function acquireVisitGPSLocation() {
      const btn = document.getElementById('btnGetVisitLocation');
      const statusText = document.getElementById('visitLocationStatusText');
      const latInput = document.getElementById('visitLat');
      const lngInput = document.getElementById('visitLng');

      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Acquiring GPS...';
      }
      if (statusText) {
        statusText.innerHTML = '<span style="color:#2563eb;"><i class="fa-solid fa-spinner fa-spin"></i> Acquiring real-time device GPS coordinates...</span>';
      }

      try {
        const coords = await getDeviceCurrentPosition();
        if (latInput) latInput.value = Number(coords.lat).toFixed(6);
        if (lngInput) lngInput.value = Number(coords.lng).toFixed(6);
        if (statusText) {
          statusText.innerHTML = `<span style="color:#16a34a; font-weight:700;"><i class="fa-solid fa-circle-check"></i> Live GPS Acquired: ${Number(coords.lat).toFixed(5)}, ${Number(coords.lng).toFixed(5)} (&plusmn;${Math.round(coords.accuracy || 10)}m)</span>`;
        }
        showToast('Device GPS coordinates acquired successfully!');
      } catch (err) {
        if (statusText) {
          statusText.innerHTML = `<span style="color:#dc2626;"><i class="fa-solid fa-circle-xmark"></i> GPS acquisition failed: ${err.message || 'Unavailable'}. You can type coordinates manually.</span>`;
        }
        showToast('Could not acquire GPS: ' + (err.message || 'Unavailable'), true);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = '<i class="fa-solid fa-location-arrow"></i> Get Current Location';
        }
      }
    }

    async function setAssignPinToCurrentLocation() {
      showToast('Acquiring device GPS for planned destination...');
      try {
        const coords = await getDeviceCurrentPosition();
        const lat = Number(coords.lat).toFixed(6);
        const lng = Number(coords.lng).toFixed(6);
        const latInput = document.getElementById('asgnLat');
        const lngInput = document.getElementById('asgnLng');
        if (latInput) latInput.value = lat;
        if (lngInput) lngInput.value = lng;
        if (assignMarker && assignCircle && assignMap) {
          const latLng = [coords.lat, coords.lng];
          assignMarker.setLatLng(latLng);
          assignCircle.setLatLng(latLng);
          assignMap.setView(latLng, 15);
        }
        showToast(`Destination pinned to current location (${lat}, ${lng})!`);
      } catch (err) {
        showToast('Could not fetch location: ' + err.message, true);
      }
    }

    // Quick Edit from Field Worker Directory Row
    function editFieldWorkerFromRow(empId) {
      const sel = document.getElementById('fwExistingEmpSelect');
      if (!sel) return;
      sel.value = empId;
      populateExistingEmployeeForField(sel);
      const title = document.getElementById('regModalTitle');
      if (title) title.textContent = 'Edit Field Worker Profile & Compensation';
      openRegisterWorkerModal(false);
    }

    // Delete Field Worker Record (Admin only)
    async function deleteFieldWorkerFromRow(workerId, workerName) {
      if (!workerName && Array.isArray(FIELD_WORKERS_DATA)) {
        const found = FIELD_WORKERS_DATA.find(w => String(w.id) === String(workerId));
        if (found) workerName = found.employee_name;
      }
      const promptName = workerName ? ` "${workerName}"` : '';
      if (!confirm(`Are you sure you want to delete field worker${promptName}? This action cannot be undone.`)) return;

      try {
        const res = await fetch(`/api/field-worker/workers/${encodeURIComponent(workerId)}?company_id=${encodeURIComponent(getActiveCompanyId())}`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Field worker deleted successfully.');
          await refreshOverviewState();
        } else {
          showToast(data.error || 'Failed to delete field worker.', true);
        }
      } catch (err) {
        showToast('Delete error: ' + err.message, true);
      }
    }

    // Sync Map Marker & Geofence Circle when Lat/Lng/Radius inputs change
    function syncAssignMapFromInputs() {
      if (!assignMap || !assignMarker || !assignCircle) return;
      const lat = parseFloat(document.getElementById('asgnLat').value);
      const lng = parseFloat(document.getElementById('asgnLng').value);
      const rad = parseFloat(document.getElementById('asgnRadius').value) || 150;
      if (!isNaN(lat) && !isNaN(lng)) {
        assignMarker.setLatLng([lat, lng]);
        assignCircle.setLatLng([lat, lng]);
        assignCircle.setRadius(rad);
      }
    }

    // -------------------------------------------------------------------------
    // Real-Time Destination & Company Search with Dynamic Map Pinning
    // -------------------------------------------------------------------------
    let destSearchTimer = null;
    let destSearchResults = [];
    let destSelectedIndex = -1;
    let activeSearchContext = 'target'; // 'target' or 'address'

    function debounceDestinationSearch(query, context = 'target') {
      clearTimeout(destSearchTimer);
      const isAddr = (context === 'address');
      const dropdown = document.getElementById(isAddr ? 'addressSearchResults' : 'destinationSearchResults');
      const otherDropdown = document.getElementById(isAddr ? 'destinationSearchResults' : 'addressSearchResults');
      const loader = document.getElementById(isAddr ? 'asgnAddressLoading' : 'asgnSearchLoading');

      if (otherDropdown) otherDropdown.style.display = 'none';

      if (!query || query.trim().length < 2) {
        if (dropdown) dropdown.style.display = 'none';
        if (loader) loader.style.display = 'none';
        destSearchResults = [];
        destSelectedIndex = -1;
        return;
      }

      if (loader) loader.style.display = 'inline-block';
      destSearchTimer = setTimeout(() => {
        executeDestinationSearch(query.trim(), context, false);
      }, 350);
    }

    async function executeDestinationSearch(query, context = 'target', autoFly = false) {
      activeSearchContext = context;
      const isAddr = (context === 'address');
      const dropdown = document.getElementById(isAddr ? 'addressSearchResults' : 'destinationSearchResults');
      const otherDropdown = document.getElementById(isAddr ? 'destinationSearchResults' : 'addressSearchResults');
      const loader = document.getElementById(isAddr ? 'asgnAddressLoading' : 'asgnSearchLoading');
      if (otherDropdown) otherDropdown.style.display = 'none';
      if (!dropdown) return;

      if (loader) loader.style.display = 'inline-block';

      try {
        const companyId = (typeof ACTIVE_COMPANY_ID !== 'undefined' && ACTIVE_COMPANY_ID) || 
                          (document.getElementById('globalCompanySelect') ? document.getElementById('globalCompanySelect').value : '') || '';
        const res = await fetch(`/api/field-worker/search-destination?query=${encodeURIComponent(query)}&company_id=${encodeURIComponent(companyId)}`);
        const data = await res.json();
        if (loader) loader.style.display = 'none';

        if (!data.success || !data.results || data.results.length === 0) {
          dropdown.innerHTML = `<div class="dest-empty"><i class="fa-solid fa-location-dot" style="margin-right:6px; color:#cbd5e1;"></i>No matching places or companies found. Try a broader city or locality.</div>`;
          dropdown.style.display = 'block';
          destSearchResults = [];
          return;
        }

        destSearchResults = data.results;
        destSelectedIndex = -1;

        // If autoFly requested (from "Locate Address on Map" button or pressing Enter directly)
        if (autoFly && data.results.length > 0) {
          selectDestinationResult(0, context, false); // flies map smoothly to best match
          // If more than 1 result, leave dropdown open so user can pick alternate
          if (data.results.length === 1) {
            dropdown.style.display = 'none';
            return;
          }
        }

        dropdown.innerHTML = data.results.map((item, idx) => {
          let badgeClass = 'dest-badge-map';
          if (item.source === 'Saved Customer') badgeClass = 'dest-badge-client';
          else if (item.source === 'Company Branch') badgeClass = 'dest-badge-branch';
          else if (item.source === 'Previous Assignment') badgeClass = 'dest-badge-client';

          let contactInfo = '';
          if (item.contact_person || item.contact_phone) {
            contactInfo = `<div class="dest-contact"><i class="fa-solid fa-user-tie" style="font-size:9px; margin-right:4px;"></i>${escapeHtml(item.contact_person || '')} ${escapeHtml(item.contact_phone ? '(' + item.contact_phone + ')' : '')}</div>`;
          }

          return `
            <div class="dest-result-item" data-index="${idx}" onclick="selectDestinationResult(${idx}, '${context}')">
              <div class="dest-item-header">
                <span class="dest-title">${escapeHtml(item.name)}</span>
                <span class="dest-badge ${badgeClass}">${escapeHtml(item.source)}</span>
              </div>
              <div class="dest-address" title="${escapeHtml(item.address)}"><i class="fa-solid fa-map-pin" style="color:#0284c7; font-size:10px; margin-right:4px;"></i>${escapeHtml(item.address)}</div>
              ${contactInfo}
            </div>
          `;
        }).join('');
        dropdown.style.display = 'block';
      } catch (err) {
        if (loader) loader.style.display = 'none';
        console.error('Destination search failed:', err);
      }
    }

    function selectDestinationResult(index, context = 'target', closeDropdown = true) {
      const item = destSearchResults[index];
      if (!item) return;

      const targetNameInput = document.getElementById('asgnTargetName');
      const addressInput = document.getElementById('asgnAddress');
      const contactPersonInput = document.getElementById('asgnContactPerson');
      const contactPhoneInput = document.getElementById('asgnContactPhone');
      const latInput = document.getElementById('asgnLat');
      const lngInput = document.getElementById('asgnLng');
      const targetDropdown = document.getElementById('destinationSearchResults');
      const addressDropdown = document.getElementById('addressSearchResults');

      if (context === 'address') {
        if (addressInput) addressInput.value = item.address || item.name;
        // Only populate Target Name if currently empty
        if (targetNameInput && !targetNameInput.value.trim()) {
          targetNameInput.value = item.name.replace(/^Branch:\s*/, '');
        }
      } else {
        if (targetNameInput) targetNameInput.value = item.name.replace(/^Branch:\s*/, '');
        if (addressInput && item.address) addressInput.value = item.address;
      }

      if (contactPersonInput && item.contact_person) contactPersonInput.value = item.contact_person;
      if (contactPhoneInput && item.contact_phone) contactPhoneInput.value = item.contact_phone;
      if (latInput) latInput.value = Number(item.lat).toFixed(6);
      if (lngInput) lngInput.value = Number(item.lng).toFixed(6);

      if (closeDropdown) {
        if (targetDropdown) targetDropdown.style.display = 'none';
        if (addressDropdown) addressDropdown.style.display = 'none';
      }

      // Smooth cinematic flyTo animation on interactive map
      applyLocationToAssignMap(item.lat, item.lng, item.name, item.address);
      showToast(`Exact location pinned: ${item.name}!`);
    }

    function applyLocationToAssignMap(lat, lng, name, address) {
      initAssignPickerMapIfNeeded();
      if (!assignMap) return;

      try {
        assignMap.invalidateSize();
      } catch (e) {}

      const rad = parseFloat(document.getElementById('asgnRadius') ? document.getElementById('asgnRadius').value : 150) || 150;
      const latLng = [lat, lng];

      if (assignMarker) assignMarker.setLatLng(latLng);
      if (assignCircle) {
        assignCircle.setLatLng(latLng);
        assignCircle.setRadius(rad);
      }

      // Smooth animated pan and zoom to target
      assignMap.flyTo(latLng, 16, { animate: true, duration: 1.5 });

      if (assignMarker) {
        assignMarker.bindPopup(`
          <div style="font-family: inherit; font-size: 12px; line-height: 1.4;">
            <div style="font-weight: 700; color: #0f172a; font-size: 13px; margin-bottom: 2px;">
              <i class="fa-solid fa-location-dot" style="color: #0284c7; margin-right: 4px;"></i>${escapeHtml(name)}
            </div>
            <div style="color: #64748b; font-size: 11px;">${escapeHtml(address || 'Target Site Geofence Active')}</div>
            <div style="color: #0d9488; font-weight: 600; font-size: 11px; margin-top: 4px;">
              <i class="fa-solid fa-circle-dot"></i> Geofence Radius: ${rad}m
            </div>
          </div>
        `).openPopup();
      }
    }

    function triggerDestinationSearch() {
      const q = document.getElementById('asgnTargetName') ? document.getElementById('asgnTargetName').value.trim() : '';
      if (!q) {
        showToast('Please type a company or place name to search', true);
        return;
      }
      executeDestinationSearch(q, 'target', true);
    }

    function triggerAddressSearch() {
      const addr = document.getElementById('asgnAddress') ? document.getElementById('asgnAddress').value.trim() : '';
      if (!addr) {
        showToast('Please type a street address or city to locate', true);
        return;
      }
      executeDestinationSearch(addr, 'address', true);
    }

    function handleDestinationKeydown(e) {
      const dropdown = document.getElementById('destinationSearchResults');
      if (!dropdown || dropdown.style.display === 'none') {
        if (e.key === 'Enter') {
          e.preventDefault();
          triggerDestinationSearch();
        }
        return;
      }

      const items = dropdown.querySelectorAll('.dest-result-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        destSelectedIndex = Math.min(destSelectedIndex + 1, items.length - 1);
        updateDropdownHighlight(items);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        destSelectedIndex = Math.max(destSelectedIndex - 1, 0);
        updateDropdownHighlight(items);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (destSelectedIndex >= 0 && destSelectedIndex < items.length) {
          selectDestinationResult(destSelectedIndex, 'target');
        } else if (items.length > 0) {
          selectDestinationResult(0, 'target');
        } else {
          triggerDestinationSearch();
        }
      } else if (e.key === 'Escape') {
        dropdown.style.display = 'none';
      }
    }

    function handleAddressKeydown(e) {
      const dropdown = document.getElementById('addressSearchResults');
      if (!dropdown || dropdown.style.display === 'none') {
        if (e.key === 'Enter') {
          e.preventDefault();
          triggerAddressSearch();
        }
        return;
      }

      const items = dropdown.querySelectorAll('.dest-result-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        destSelectedIndex = Math.min(destSelectedIndex + 1, items.length - 1);
        updateDropdownHighlight(items);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        destSelectedIndex = Math.max(destSelectedIndex - 1, 0);
        updateDropdownHighlight(items);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        if (destSelectedIndex >= 0 && destSelectedIndex < items.length) {
          selectDestinationResult(destSelectedIndex, 'address');
        } else if (items.length > 0) {
          selectDestinationResult(0, 'address');
        } else {
          triggerAddressSearch();
        }
      } else if (e.key === 'Escape') {
        dropdown.style.display = 'none';
      }
    }

    function updateDropdownHighlight(items) {
      items.forEach((item, idx) => {
        if (idx === destSelectedIndex) {
          item.classList.add('selected');
          item.scrollIntoView({ block: 'nearest' });
        } else {
          item.classList.remove('selected');
        }
      });
    }

    // Dismiss search dropdown on outside clicks
    document.addEventListener('click', function(e) {
      const targetDropdown = document.getElementById('destinationSearchResults');
      const targetInput = document.getElementById('asgnTargetName');
      const targetBtn = document.getElementById('btnSearchDestination');
      if (targetDropdown && targetDropdown.style.display !== 'none') {
        if (!targetDropdown.contains(e.target) && e.target !== targetInput && e.target !== targetBtn && !(targetBtn && targetBtn.contains(e.target))) {
          targetDropdown.style.display = 'none';
        }
      }

      const addressDropdown = document.getElementById('addressSearchResults');
      const addressInput = document.getElementById('asgnAddress');
      const addressBtn = document.getElementById('btnSearchAddress');
      if (addressDropdown && addressDropdown.style.display !== 'none') {
        if (!addressDropdown.contains(e.target) && e.target !== addressInput && e.target !== addressBtn && !(addressBtn && addressBtn.contains(e.target))) {
          addressDropdown.style.display = 'none';
        }
      }
    });

    // Left Sidebar Navigation Switcher (With Tab State Persistence)
    function switchFieldTab(paneId, btnEl) {
      if (CURRENT_USER_ROLE === 'employee' && Array.isArray(CURRENT_ALLOWED_TABS)) {
        if (!CURRENT_ALLOWED_TABS.includes(paneId)) {
          showToast('Access Denied: You do not have permission to access this tab.', true);
          return;
        }
      }
      document.querySelectorAll('.fw-section-pane').forEach(p => p.classList.remove('active'));
      const target = document.getElementById(paneId);
      if (target) {
        target.classList.add('active');
        const heading = document.getElementById('activePaneHeading');
        if (heading && target.dataset.title) {
          heading.textContent = target.dataset.title;
        }
      }
      document.querySelectorAll('#fwSidebarNav .nav-item-btn').forEach(b => b.classList.remove('active'));
      if (!btnEl) {
        btnEl = document.querySelector(`#fwSidebarNav [data-pane="${paneId}"]`);
      }
      if (btnEl) btnEl.classList.add('active');

      // Hide top banner on Dashboard, Payslip Preview, and Payment Entry tabs (which have their own dedicated banners)
      const hideMainBanner = (paneId === 'paneFieldDashboard' || paneId === 'paneFieldPayslipPreview' || paneId === 'paneFieldPaymentEntry');
      const banner = document.getElementById('fwMainBannerCard');
      if (banner) {
        if (hideMainBanner) {
          banner.classList.add('banner-hidden');
          banner.style.setProperty('display', 'none', 'important');
        } else {
          banner.classList.remove('banner-hidden');
          banner.style.setProperty('display', 'flex', 'important');
        }
      }

      // Persist active tab across reloads
      sessionStorage.setItem('activeFieldTab', paneId);
      try {
        history.replaceState(null, '', '#' + paneId);
      } catch (e) {}

      // Close mobile drawer if open
      if (window.innerWidth <= 992) {
        const sidebar = document.getElementById('appSidebar');
        if (sidebar && !sidebar.classList.contains('collapsed')) {
          sidebar.classList.add('collapsed');
          document.body.classList.remove('drawer-open');
        }
      }

      if (paneId === 'paneFieldPayroll' && (!PAYROLL_DATA || PAYROLL_DATA.length === 0)) {
        loadFieldPayrollDataAsync();
      }

      if (paneId === 'paneFieldLeaves') {
        loadFwRequests();
      }

      if (paneId === 'paneScheduledVisits') {
        renderScheduledVisitsTable(ASSIGNMENTS_DATA);
      }

      if (paneId === 'paneFieldManualEntry') {
        loadFieldManualEntries();
      }

      if (paneId === 'paneFieldPaymentEntry') {
        loadFieldPayments();
      }

      if (paneId === 'paneFieldPayslipPreview') {
        initFieldPayslipPreview();
      }

      if (paneId !== 'paneFieldPunch' && typeof stopTerminalCamera === 'function') {
        stopTerminalCamera();
      }

      if (paneId === 'paneLiveTracking') {
        initLiveTrackingMapIfNeeded();
      }

      if (paneId === 'paneAssignLocations') {
        initAssignPickerMapIfNeeded();
      }

      setTimeout(() => {
        if (paneId === 'paneLiveTracking' && liveMap) liveMap.invalidateSize();
        if (paneId === 'paneAssignLocations' && assignMap) assignMap.invalidateSize();
      }, 150);
    }

    // Collapsible Hamburger Sidebar Toggle (Matches Enterprise Sidebar-Mini & Drawer UI)
    function initCollapsibleSidebar() {
      const sidebar = document.getElementById('appSidebar');
      const sidebarToggle = document.getElementById('sidebarToggle');
      const sidebarBackdrop = document.getElementById('sidebarBackdrop');
      const miniTooltip = document.getElementById('sidebarMiniTooltip');

      function isMobile() {
        return window.innerWidth <= 992;
      }

      function toggleSidebar(forceState) {
        if (!sidebar) return;

        if (isMobile()) {
          // Mobile Drawer View (<= 992px)
          document.body.classList.remove('sidebar-mini');
          sidebar.classList.remove('mini');
          if (miniTooltip) miniTooltip.classList.remove('visible');

          if (typeof forceState === 'boolean') {
            if (forceState) {
              document.body.classList.add('drawer-open');
              sidebar.classList.remove('collapsed');
            } else {
              document.body.classList.remove('drawer-open');
              sidebar.classList.add('collapsed');
            }
          } else {
            const isOpening = !document.body.classList.contains('drawer-open');
            document.body.classList.toggle('drawer-open', isOpening);
            sidebar.classList.toggle('collapsed', !isOpening);
          }
        } else {
          // Desktop View (> 992px) - Toggle Mini-Sidebar (icons remain, text hides)
          document.body.classList.remove('drawer-open');
          sidebar.classList.remove('collapsed');

          let isMini;
          if (typeof forceState === 'boolean') {
            isMini = !forceState;
            document.body.classList.toggle('sidebar-mini', isMini);
            sidebar.classList.toggle('mini', isMini);
          } else {
            isMini = document.body.classList.toggle('sidebar-mini');
            sidebar.classList.toggle('mini', isMini);
          }

          try {
            localStorage.setItem('argus_desktop_sidebar_mini', isMini ? 'true' : 'false');
          } catch (err) {
            console.warn('Could not save sidebar preference:', err);
          }

          if (miniTooltip) miniTooltip.classList.remove('visible');
        }

        setTimeout(() => {
          if (liveMap) liveMap.invalidateSize();
          if (assignMap) assignMap.invalidateSize();
        }, 320);
      }

      // Restore desktop mini state from localStorage
      if (!isMobile()) {
        try {
          const savedMini = localStorage.getItem('argus_desktop_sidebar_mini');
          if (savedMini === 'true') {
            document.body.classList.add('sidebar-mini');
            sidebar.classList.add('mini');
          }
        } catch (e) {}
      } else {
        sidebar.classList.add('collapsed');
        document.body.classList.remove('drawer-open');
      }

      // Floating Tooltip for Desktop Mini-Sidebar
      function setupMiniSidebarTooltips() {
        if (!sidebar || !miniTooltip) return;

        const items = sidebar.querySelectorAll('.nav-item-btn, .sidebar-logout-card');
        items.forEach(item => {
          item.addEventListener('mouseenter', function () {
            if (!document.body.classList.contains('sidebar-mini') || isMobile()) return;

            const text = item.getAttribute('data-tooltip') || item.querySelector('span')?.innerText?.trim() || '';
            if (!text) return;

            miniTooltip.textContent = text;
            const rect = item.getBoundingClientRect();
            miniTooltip.style.top = (rect.top + rect.height / 2) + 'px';
            miniTooltip.style.left = (rect.right + 12) + 'px';
            miniTooltip.classList.add('visible');
          });

          item.addEventListener('mouseleave', function () {
            miniTooltip.classList.remove('visible');
          });

          item.addEventListener('click', function () {
            miniTooltip.classList.remove('visible');
          });
        });
      }

      setupMiniSidebarTooltips();

      if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function(e) {
          e.stopPropagation();
          toggleSidebar();
        });
      }

      if (sidebarBackdrop) {
        sidebarBackdrop.addEventListener('click', function() {
          toggleSidebar(false);
        });
      }

      // Window resize listener
      window.addEventListener('resize', function() {
        if (isMobile()) {
          document.body.classList.remove('sidebar-mini');
          sidebar.classList.remove('mini');
          if (!document.body.classList.contains('drawer-open')) {
            sidebar.classList.add('collapsed');
          }
        } else {
          document.body.classList.remove('drawer-open');
          sidebar.classList.remove('collapsed');
          try {
            const savedMini = localStorage.getItem('argus_desktop_sidebar_mini');
            if (savedMini === 'true') {
              document.body.classList.add('sidebar-mini');
              sidebar.classList.add('mini');
            } else {
              document.body.classList.remove('sidebar-mini');
              sidebar.classList.remove('mini');
            }
          } catch (e) {}
        }
      });
    }

    let toastTimer = null;
    function showToast(msg, isError = false) {
      const banner = document.getElementById('fwAlertBanner');
      const txt = document.getElementById('fwAlertText');
      if (!banner || !txt) return;
      banner.className = `fw-toast-banner ${isError ? 'fw-toast-danger' : 'fw-toast-success'}`;
      txt.innerHTML = `<i class="fa-solid ${isError ? 'fa-circle-exclamation' : 'fa-circle-check'}" style="margin-right:6px;"></i>${msg}`;
      banner.classList.remove('d-none');
      if (toastTimer) clearTimeout(toastTimer);
      toastTimer = setTimeout(() => {
        banner.classList.add('d-none');
      }, 3000);
    }

    function getActiveCompanyId() {
      const el = document.getElementById('globalCompanySelect');
      return el ? (el.value || 'ARGUS_MASTER') : 'ARGUS_MASTER';
    }

    function initLiveTrackingMapIfNeeded() {
      if (liveMap) {
        liveMap.invalidateSize();
        return;
      }
      const liveEl = document.getElementById('fieldLiveMap');
      if (liveEl && typeof L !== 'undefined') {
        liveMap = L.map('fieldLiveMap').setView([INITIAL_COMPANY_LAT, INITIAL_COMPANY_LNG], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          maxZoom: 19,
          attribution: '&copy; OpenStreetMap'
        }).addTo(liveMap);
        liveMapLayerGroup = L.layerGroup().addTo(liveMap);
        renderLiveMapLayers();

        window.addEventListener('resize', () => {
          if (liveMap) liveMap.invalidateSize();
        });
      }
    }

    function initAssignPickerMapIfNeeded() {
      if (assignMap) {
        assignMap.invalidateSize();
        return;
      }
      const assignEl = document.getElementById('assignPickerMap');
      if (assignEl && typeof L !== 'undefined') {
        assignMap = L.map('assignPickerMap').setView([INITIAL_COMPANY_LAT, INITIAL_COMPANY_LNG], 13);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19 }).addTo(assignMap);

        const latInput = document.getElementById('asgnLat');
        const lngInput = document.getElementById('asgnLng');
        const defaultLat = latInput ? (parseFloat(latInput.value) || INITIAL_COMPANY_LAT) : INITIAL_COMPANY_LAT;
        const defaultLng = lngInput ? (parseFloat(lngInput.value) || INITIAL_COMPANY_LNG) : INITIAL_COMPANY_LNG;
        assignMarker = L.marker([defaultLat, defaultLng], { draggable: true }).addTo(assignMap);
        const radInput = document.getElementById('asgnRadius');
        assignCircle = L.circle([defaultLat, defaultLng], {
          radius: radInput ? (parseFloat(radInput.value) || 150) : 150,
          color: '#0d9488',
          fillColor: '#14b8a6',
          fillOpacity: 0.2
        }).addTo(assignMap);

        assignMap.on('click', function(e) {
          if (document.getElementById('asgnLat')) document.getElementById('asgnLat').value = e.latlng.lat.toFixed(6);
          if (document.getElementById('asgnLng')) document.getElementById('asgnLng').value = e.latlng.lng.toFixed(6);
          assignMarker.setLatLng(e.latlng);
          assignCircle.setLatLng(e.latlng);
        });

        assignMarker.on('dragend', function(e) {
          const pos = e.target.getLatLng();
          if (document.getElementById('asgnLat')) document.getElementById('asgnLat').value = pos.lat.toFixed(6);
          if (document.getElementById('asgnLng')) document.getElementById('asgnLng').value = pos.lng.toFixed(6);
          assignCircle.setLatLng(pos);
        });
      }
    }

    function initFieldMaps() {
      // Lazy-load: maps initialize on demand when their respective tabs are activated
    }

    function renderLiveMapLayers() {
      if (!liveMapLayerGroup) return;
      liveMapLayerGroup.clearLayers();
      const bounds = [];

      const hqMarker = L.circleMarker([INITIAL_COMPANY_LAT, INITIAL_COMPANY_LNG], {
        radius: 9,
        color: '#1d4ed8',
        fillColor: '#3b82f6',
        fillOpacity: 0.9,
        weight: 3
      }).bindPopup(`<b>Company HQ: ${INITIAL_COMPANY_NAME}</b>`);
      liveMapLayerGroup.addLayer(hqMarker);
      bounds.push([INITIAL_COMPANY_LAT, INITIAL_COMPANY_LNG]);

      (ASSIGNMENTS_DATA || []).forEach(a => {
        if (!a.target_lat || !a.target_lng) return;
        const pos = [parseFloat(a.target_lat), parseFloat(a.target_lng)];
        bounds.push(pos);
        const rad = parseFloat(a.geofence_radius) || 150;
        const geofence = L.circle(pos, {
          radius: rad,
          color: '#0d9488',
          dashArray: '5,5',
          fillColor: '#14b8a6',
          fillOpacity: 0.15
        }).bindPopup(`<b>Assigned Target: ${a.target_name}</b><br>Worker: ${a.employee_name}<br>Purpose: ${a.task_purpose}<br>Geofence: ${rad}m (${a.status})`);
        liveMapLayerGroup.addLayer(geofence);
      });

      // Render Breadcrumb Trails (Color-coded: Blue for Corridor, Glowing Red for Detour)
      const crumbsByWorker = (TRACKING_DATA && TRACKING_DATA.breadcrumbs_by_worker) || {};
      Object.keys(crumbsByWorker).forEach(workerName => {
        const pts = crumbsByWorker[workerName] || [];
        const latlngs = pts.filter(p => p.lat && p.lng).map(p => [p.lat, p.lng]);
        if (latlngs.length > 1) {
          const hasDetour = pts.some(p => p.status === 'off_route_detour');
          const poly = L.polyline(latlngs, {
            color: hasDetour ? '#dc2626' : '#2563eb',
            weight: hasDetour ? 4 : 3,
            dashArray: hasDetour ? '6,6' : '4,6',
            opacity: 0.9
          });
          liveMapLayerGroup.addLayer(poly);
        }
      });

      // Render Active AI Detour Anomaly Pulse Markers
      const activeIncidents = (TRACKING_DATA && TRACKING_DATA.active_ai_incidents) || [];
      activeIncidents.forEach(inc => {
        if (!inc.latitude || !inc.longitude) return;
        const incPos = [parseFloat(inc.latitude), parseFloat(inc.longitude)];
        bounds.push(incPos);

        const aiDivIcon = L.divIcon({
          className: 'custom-ai-pin-wrapper',
          html: `
            <div class="leaflet-ai-detour-marker" title="AI Detour Anomaly: ${inc.employee_name}">
              <div class="leaflet-ai-pulse"></div>
              <i class="fa-solid fa-triangle-exclamation"></i>
            </div>
          `,
          iconSize: [26, 26],
          iconAnchor: [13, 13]
        });

        const safeAddr = (inc.address || '').replace(/'/g, "\\'");
        const safeWorker = (inc.employee_name || '').replace(/'/g, "\\'");

        const aiMarker = L.marker(incPos, { icon: aiDivIcon, zIndexOffset: 1200 }).bindPopup(`
          <div style="min-width:260px; font-size:12px; font-family:inherit;">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
              <span class="ai-badge-severity ${inc.severity === 'HIGH' ? 'ai-badge-high' : 'ai-badge-med'}">
                ${inc.severity || 'HIGH'} DETOUR
              </span>
              <span class="ai-model-tag">
                <i class="fa-solid fa-wand-magic-sparkles"></i> AI Monitored
              </span>
            </div>
            <div style="font-weight:800; font-size:14px; color:#0f172a; margin-bottom:2px;">
              ${inc.employee_name}
            </div>
            <div style="font-size:11.5px; color:#64748b; margin-bottom:6px;">
              <i class="fa-solid fa-location-dot" style="color:#ef4444;"></i> ${inc.address || 'Unassigned Location'}
            </div>
            <div class="ai-summary-pill" style="margin-bottom:6px;">
              <b>AI Finding:</b> ${inc.summary}
            </div>
            <div class="ai-rec-pill" style="margin-bottom:8px;">
              <b>Action:</b> ${inc.action_recommendation}
            </div>
            <div style="display:flex; justify-content:flex-end;">
              <button type="button" class="ai-btn-resolve" onclick="openResolveIncidentModal('${inc.id}', '${safeWorker}', '${safeAddr}', '${inc.dwell_minutes}m')">
                <i class="fa-solid fa-check-double"></i> Acknowledge / Resolve
              </button>
            </div>
          </div>
        `);
        liveMapLayerGroup.addLayer(aiMarker);
      });

      // Render Live Worker Markers
      const workersLive = (TRACKING_DATA && TRACKING_DATA.workers_live) || [];
      workersLive.forEach(w => {
        if (!w.latitude || !w.longitude) return;
        const pos = [parseFloat(w.latitude), parseFloat(w.longitude)];
        bounds.push(pos);

        let color = '#d97706';
        let fill = '#f59e0b';
        if (w.tracking_status === 'on_site') {
          color = '#15803d';
          fill = '#22c55e';
        } else if (w.tracking_status === 'off_route_detour') {
          color = '#b91c1c';
          fill = '#ef4444';
        }

        const marker = L.circleMarker(pos, {
          radius: 11,
          color: color,
          fillColor: fill,
          fillOpacity: 0.95,
          weight: 3
        }).bindPopup(`
          <div style="min-width:200px; font-size:12px;">
            <div style="font-weight:800; font-size:13px; color:#0f172a;">${w.employee_name}</div>
            <div style="font-weight:700; color:${color}; margin-bottom:4px;">${w.status_label}</div>
            <div style="border-top:1px solid #e2e8f0; padding-top:4px;">
              <div><b>Target:</b> ${w.nearest_target_name} (${w.distance_from_target_m || 0}m)</div>
              <div><b>Distance Today:</b> ${w.total_km_today || 0} KM</div>
              <div><b>Address:</b> ${w.address || ''}</div>
              <div style="color:#64748b; margin-top:2px;">Last Seen: ${w.last_seen || ''}</div>
              ${w.active_ai_incident ? `
                <div style="margin-top:6px; padding:6px; background:#fef2f2; border:1px solid #fecdd3; border-radius:4px; font-size:11px; color:#991b1b;">
                  <b>AI Detour Alert:</b> ${w.active_ai_incident.summary}
                </div>
              ` : ''}
            </div>
          </div>
        `);
        liveMapLayerGroup.addLayer(marker);
      });

      if (bounds.length > 1) {
        liveMap.fitBounds(bounds, { padding: [35, 35], maxZoom: 15 });
      }
    }

    // =========================================================================
    // DYNAMIC DATA REFRESH & REAL-TIME RE-RENDERING (ZERO FULL PAGE RELOADS)
    // =========================================================================
    async function refreshOverviewState() {
      const cid = getActiveCompanyId();
      const dateEl = document.getElementById('globalDateInput');
      const dt = dateEl ? dateEl.value : '';
      const moEl = document.getElementById('globalMonthInput');
      const mo = moEl ? moEl.value : '';
      const defaultPane = (CURRENT_USER_ROLE === 'employee') ? 'paneFieldPunch' : 'paneFieldDashboard';
      const activePane = sessionStorage.getItem('activeFieldTab') || defaultPane;
      const incSalary = (activePane === 'paneFieldPayroll') ? '&include_salary=1' : '';

      try {
        const res = await fetch(`/api/field-worker/overview?company_id=${encodeURIComponent(cid)}&date=${encodeURIComponent(dt)}&month=${encodeURIComponent(mo)}${incSalary}`);
        const data = await res.json();
        if (!data.success) return;

        ASSIGNMENTS_DATA = data.assignments || [];
        TRACKING_DATA = data.tracking || {};
        FIELD_WORKERS_DATA = data.field_workers || [];
        VISITS_DATA = data.visits || [];
        if (data.salary_reports && data.salary_reports.length > 0) {
          PAYROLL_DATA = data.salary_reports;
        }

        // 0. Re-render Field Operations Dashboard & Leave System
        if (data.dashboard_stats) {
          renderFieldDashboard(data.dashboard_stats);
        }
        if (data.fw_leave_requests || data.fw_leave_stats) {
          renderFieldLeaveSystem(data.fw_leave_requests || [], data.fw_leave_counts || {}, data.fw_leave_stats || {});
        }

        // 1. Update KPI counts (Tab 1)
        const kw = document.getElementById('kpiWorkersCount');
        if (kw) kw.textContent = FIELD_WORKERS_DATA.length;
        const ka = document.getElementById('kpiAssignedCount');
        if (ka) ka.textContent = ASSIGNMENTS_DATA.length;
        const ko = document.getElementById('kpiOnSiteCount');
        if (ko) ko.textContent = (TRACKING_DATA.counts && TRACKING_DATA.counts.on_site) || 0;
        const kt = document.getElementById('kpiTransitCount');
        if (kt) kt.textContent = (TRACKING_DATA.counts && TRACKING_DATA.counts.in_transit) || 0;
        const kd = document.getElementById('kpiDetourCount');
        if (kd) kd.textContent = (TRACKING_DATA.counts && TRACKING_DATA.counts.off_route_detour) || 0;
        const kv = document.getElementById('kpiVisitsCount');
        if (kv) kv.textContent = VISITS_DATA.length;

        // Update AI Detour Anomaly Alert Banner & Incident Drawer
        const aiIncs = data.ai_incidents || (TRACKING_DATA && TRACKING_DATA.ai_incidents) || [];
        const activeAiIncs = data.active_ai_incidents || (TRACKING_DATA && TRACKING_DATA.active_ai_incidents) || [];
        updateAiAlertBanner(activeAiIncs);
        renderAiIncidentsList(aiIncs);
        const aiBadge = document.getElementById('kpiAiBadge');
        if (aiBadge) {
          aiBadge.style.display = activeAiIncs.length > 0 ? 'inline-block' : 'none';
        }

        // 2. Re-render Tab 1 Map & Tracking Logs
        renderLiveMapLayers();
        renderTrackingLogsTable(TRACKING_DATA.logs || []);

        // 3. Re-render Tab 2 Workers Directory & Dropdowns
        renderWorkersDirectoryTable(FIELD_WORKERS_DATA);
        updateWorkerSelectDropdowns(FIELD_WORKERS_DATA);

        // 4. Re-render Tab 3 Assignments Table & Scheduled Visits List
        renderAssignmentsTable(ASSIGNMENTS_DATA);
        renderScheduledVisitsTable(ASSIGNMENTS_DATA);

        // 5. Re-render Tab 4 Today's Checkpoints Schedule
        renderQuickCheckpointsTable(ASSIGNMENTS_DATA);

        // 6. Re-render Tab 5 Visits Pipeline Table & Linked Assignment Dropdown
        renderCustomerVisitsTable(VISITS_DATA);
        updateLinkedAssignmentDropdown(ASSIGNMENTS_DATA);

        // 7. Re-render Tab 6 Payroll Table
        renderFieldPayrollTable(PAYROLL_DATA);

        // Update Payroll Month Title & Export URLs
        const pmt = document.getElementById('payrollMonthTitle');
        if (pmt) pmt.textContent = mo;
        const expPdf = document.getElementById('btnExportPayrollPdf');
        if (expPdf) expPdf.href = `/api/field-worker/export?type=salary&format=pdf&company_id=${encodeURIComponent(cid)}&month=${encodeURIComponent(mo)}`;
        const expXls = document.getElementById('btnExportPayrollExcel');
        if (expXls) expXls.href = `/api/field-worker/export?type=salary&format=excel&company_id=${encodeURIComponent(cid)}&month=${encodeURIComponent(mo)}`;
        const expTrPdf = document.getElementById('btnExportTrackingPdf');
        if (expTrPdf) expTrPdf.href = `/api/field-worker/export?type=tracking&format=pdf&company_id=${encodeURIComponent(cid)}&date=${encodeURIComponent(dt)}`;
        const expTrXls = document.getElementById('btnExportTrackingExcel');
        if (expTrXls) expTrXls.href = `/api/field-worker/export?type=tracking&format=excel&company_id=${encodeURIComponent(cid)}&date=${encodeURIComponent(dt)}`;
        const expVisPdf = document.getElementById('btnExportVisitsPdf');
        if (expVisPdf) expVisPdf.href = `/api/field-worker/export?type=visits&format=pdf&company_id=${encodeURIComponent(cid)}`;
        const expVisXls = document.getElementById('btnExportVisitsExcel');
        if (expVisXls) expVisXls.href = `/api/field-worker/export?type=visits&format=excel&company_id=${encodeURIComponent(cid)}`;

      } catch (err) {
        console.warn("Auto-refresh error:", err);
      }
    }

    function renderTrackingLogsTable(logs) {
      const tbody = document.getElementById('trackingLogsTableBody');
      if (!tbody) return;
      if (!logs || logs.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:#64748b; padding:24px;">No GPS pings recorded yet for this date.</td></tr>';
        return;
      }
      tbody.innerHTML = logs.map(lg => {
        let badge = `<span class="badge-transit"><i class="fa-solid fa-route"></i> ${lg.status_label}</span>`;
        if (lg.tracking_status === 'on_site') {
          badge = `<span class="badge-onsite"><i class="fa-solid fa-check"></i> ${lg.status_label}</span>`;
        } else if (lg.tracking_status === 'off_route_detour') {
          badge = `<span class="badge-detour"><i class="fa-solid fa-triangle-exclamation"></i> ${lg.status_label}</span>`;
        }
        return `<tr>
          <td style="font-weight:700; white-space:nowrap;">${lg.time_short || lg.timestamp}</td>
          <td><div class="fw-cell-title">${lg.employee_name}</div></td>
          <td style="font-weight:600;">${lg.nearest_target_name || '-'}</td>
          <td style="white-space:nowrap; font-weight:600;">${Number(lg.distance_from_target_m || 0).toFixed(1)} m</td>
          <td style="white-space:nowrap; color:#2563eb; font-weight:700;">${Number(lg.step_km || 0).toFixed(3)} km</td>
          <td>${badge}</td>
          <td class="fw-address-cell">${lg.address || ''}</td>
          <td style="color:#475569;">${lg.activity_note || '-'}</td>
        </tr>`;
      }).join('');
    }

    // =========================================================================
    // AI DETOUR & ANOMALY ALERT FUNCTIONS
    // =========================================================================
    function updateAiAlertBanner(activeIncidents) {
      const banner = document.getElementById('aiLiveAlertBanner');
      if (!banner) return;
      if (!activeIncidents || activeIncidents.length === 0) {
        banner.style.display = 'none';
        return;
      }
      ACTIVE_AI_INCIDENTS = activeIncidents;
      const latest = activeIncidents[0];

      // Check if new incident appeared to trigger audio chime
      const hasNew = activeIncidents.some(inc => !KNOWN_AI_INCIDENT_IDS.has(inc.id));
      if (hasNew) {
        playAiAlertChime();
        activeIncidents.forEach(inc => KNOWN_AI_INCIDENT_IDS.add(inc.id));
      }

      const sevEl = document.getElementById('aiAlertSeverity');
      if (sevEl) {
        sevEl.textContent = latest.severity || 'HIGH';
        sevEl.className = 'ai-badge-severity ' + (latest.severity === 'HIGH' ? 'ai-badge-high' : 'ai-badge-med');
      }
      const titleEl = document.getElementById('aiAlertTitle');
      if (titleEl) {
        titleEl.textContent = activeIncidents.length > 1
          ? `AI Detour Alerts: ${activeIncidents.length} Field Workers Off-Route`
          : `AI Detour Alert: ${latest.employee_name}`;
      }
      const nameEl = document.getElementById('aiAlertWorkerName');
      if (nameEl) nameEl.textContent = latest.employee_name;
      const dwellEl = document.getElementById('aiAlertDwell');
      if (dwellEl) dwellEl.textContent = `${latest.dwell_minutes || 0}m`;
      const locEl = document.getElementById('aiAlertLocation');
      if (locEl) locEl.textContent = latest.address || 'Unassigned Site';

      banner.style.display = 'flex';
    }

    function dismissAiAlertBanner() {
      const banner = document.getElementById('aiLiveAlertBanner');
      if (banner) banner.style.display = 'none';
    }

    function renderAiIncidentsList(incidents) {
      const container = document.getElementById('aiIncidentsContainer');
      const badge = document.getElementById('aiActiveIncidentsBadge');
      if (!container) return;

      const activeList = (incidents || []).filter(i => i.status === 'Active' || i.status === 'Acknowledged');
      if (badge) {
        if (activeList.length > 0) {
          badge.textContent = `${activeList.length} ACTIVE`;
          badge.className = 'ai-badge-severity ai-badge-high';
          badge.style.display = 'inline-block';
        } else {
          badge.style.display = 'none';
        }
      }

      if (!incidents || incidents.length === 0) {
        container.innerHTML = `
          <div style="text-align:center; padding:20px; color:#16a34a; background:#f0fdf4; border:1px solid #bbf7d0; border-radius:8px; font-size:13px; font-weight:700;">
            <i class="fa-solid fa-circle-check" style="margin-right:6px;"></i> All field routes verified compliant. No unauthorized detours or stationary anomalies detected today.
          </div>
        `;
        return;
      }

      let html = '';
      incidents.forEach(inc => {
        const isResolved = inc.status === 'Resolved';
        const sevClass = inc.severity === 'HIGH' ? 'ai-badge-high' : (inc.severity === 'MEDIUM' ? 'ai-badge-med' : 'ai-badge-low');
        const safeAddr = (inc.address || '').replace(/'/g, "\\'");
        const safeWorker = (inc.employee_name || '').replace(/'/g, "\\'");

        html += `
          <div class="ai-incident-card" style="${isResolved ? 'opacity:0.75; border-left:4px solid #16a34a;' : 'border-left:4px solid #dc2626;'}">
            <div class="ai-incident-header">
              <div class="ai-incident-worker">
                <span style="width:28px; height:28px; border-radius:50%; background:${isResolved ? '#dcfce7; color:#15803d;' : '#fee2e2; color:#dc2626;'} display:flex; align-items:center; justify-content:center; font-size:12px;">
                  <i class="fa-solid ${isResolved ? 'fa-check' : 'fa-triangle-exclamation'}"></i>
                </span>
                <span>${inc.employee_name}</span>
                <span class="ai-badge-severity ${sevClass}">${inc.severity || 'HIGH'}</span>
                <span style="font-size:11px; font-weight:700; color:#475569; background:#f1f5f9; padding:2px 7px; border-radius:4px;">
                  <i class="fa-solid fa-stopwatch" style="color:#d97706;"></i> ${inc.dwell_minutes || 0}m Dwell
                </span>
                <span style="font-size:11px; font-weight:700; color:#475569; background:#f1f5f9; padding:2px 7px; border-radius:4px;">
                  <i class="fa-solid fa-ruler" style="color:#2563eb;"></i> ${inc.detour_distance_km || 0} km Off-Route
                </span>
              </div>
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-size:11.5px; color:#64748b; font-weight:600;">
                  <i class="fa-regular fa-clock"></i> ${inc.time_short || inc.timestamp}
                </span>
                <span style="font-size:11px; font-weight:800; padding:2px 8px; border-radius:12px; background:${isResolved ? '#dcfce7; color:#15803d;' : '#fee2e2; color:#b91c1c;'}">
                  ${inc.status || 'Active'}
                </span>
              </div>
            </div>

            <div style="font-size:12px; color:#475569; display:flex; align-items:center; gap:6px; flex-wrap:wrap;">
              <i class="fa-solid fa-location-dot" style="color:#ef4444;"></i>
              <span><b>Stop Location:</b> ${inc.address || 'Unassigned Location'}</span>
              <span style="color:#94a3b8;">|</span>
              <span><b>Target:</b> ${inc.nearest_target_name || 'Assigned Site'}</span>
            </div>

            <div class="ai-summary-pill">
              <div style="font-weight:700; color:#4338ca; margin-bottom:2px; display:flex; align-items:center; gap:6px;">
                <i class="fa-solid fa-wand-magic-sparkles"></i> AI Assessment (${inc.ai_model_used || 'Gemini AI Engine'})
              </div>
              <div>${inc.summary}</div>
            </div>

            <div class="ai-rec-pill">
              <div style="font-weight:700; color:#b45309; margin-bottom:2px; display:flex; align-items:center; gap:6px;">
                <i class="fa-solid fa-lightbulb"></i> Recommended Action
              </div>
              <div>${inc.action_recommendation}</div>
            </div>

            ${isResolved && inc.admin_notes ? `
              <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:6px; padding:8px 12px; font-size:12px; color:#166534;">
                <b>Admin Resolution (${inc.resolved_by || 'Admin'}):</b> ${inc.admin_notes}
              </div>
            ` : ''}

            <div style="display:flex; justify-content:flex-end; gap:8px; margin-top:2px;">
              <button type="button" class="ai-btn-locate" onclick="locateActiveAiIncidentOnMap(${inc.latitude}, ${inc.longitude}, '${inc.id}')">
                <i class="fa-solid fa-crosshairs"></i> View on Radar
              </button>
              ${!isResolved ? `
                <button type="button" class="ai-btn-resolve" onclick="openResolveIncidentModal('${inc.id}', '${safeWorker}', '${safeAddr}', '${inc.dwell_minutes}m')">
                  <i class="fa-solid fa-check-double"></i> Acknowledge / Resolve
                </button>
              ` : ''}
            </div>
          </div>
        `;
      });

      container.innerHTML = html;
    }

    function locateActiveAiIncidentOnMap(lat, lng, incidentId) {
      if (!liveMap) return;
      if (!lat || !lng) {
        if (ACTIVE_AI_INCIDENTS.length > 0) {
          lat = parseFloat(ACTIVE_AI_INCIDENTS[0].latitude);
          lng = parseFloat(ACTIVE_AI_INCIDENTS[0].longitude);
        }
      }
      if (lat && lng) {
        liveMap.setView([lat, lng], 16, { animate: true });
        const mapEl = document.getElementById('fieldLiveMap');
        if (mapEl) mapEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }

    function openResolveActiveAiIncident() {
      if (ACTIVE_AI_INCIDENTS.length > 0) {
        const inc = ACTIVE_AI_INCIDENTS[0];
        openResolveIncidentModal(inc.id, inc.employee_name, inc.address, (inc.dwell_minutes || 0) + 'm');
      }
    }

    function openResolveIncidentModal(incId, empName, location, dwell) {
      document.getElementById('resolveIncidentId').value = incId || '';
      document.getElementById('resolveWorkerName').textContent = empName || '--';
      document.getElementById('resolveLocation').textContent = location || '--';
      document.getElementById('resolveDwell').textContent = dwell || '--';
      document.getElementById('resolveAdminNotes').value = '';
      const modal = document.getElementById('resolveIncidentModalBackdrop');
      if (modal) modal.classList.remove('d-none');
    }

    function closeResolveIncidentModal() {
      const modal = document.getElementById('resolveIncidentModalBackdrop');
      if (modal) modal.classList.add('d-none');
    }

    async function submitResolveIncident(e) {
      e.preventDefault();
      const incId = document.getElementById('resolveIncidentId').value;
      const status = document.getElementById('resolveStatusSelect').value;
      const notes = document.getElementById('resolveAdminNotes').value;

      try {
        const res = await fetch(`/api/field-worker/ai-incidents/${encodeURIComponent(incId)}/resolve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            company_id: getActiveCompanyId(),
            status: status,
            admin_notes: notes
          })
        });
        const data = await res.json();
        if (data.success) {
          showToast(`Incident marked as ${status}!`);
          closeResolveIncidentModal();
          await refreshOverviewState();
        } else {
          showToast(data.error || 'Failed to resolve incident', true);
        }
      } catch (err) {
        showToast('Network error resolving incident: ' + err.message, true);
      }
    }

    function initAiDetourMonitoring() {
      const activeIncs = (TRACKING_DATA && TRACKING_DATA.active_ai_incidents) || [];
      const allIncs = (TRACKING_DATA && TRACKING_DATA.ai_incidents) || [];
      activeIncs.forEach(i => KNOWN_AI_INCIDENT_IDS.add(i.id));
      updateAiAlertBanner(activeIncs);
      renderAiIncidentsList(allIncs);
      const aiBadge = document.getElementById('kpiAiBadge');
      if (aiBadge) {
        aiBadge.style.display = activeIncs.length > 0 ? 'inline-block' : 'none';
      }
    }

    function renderWorkersDirectoryTable(workers) {
      const tbody = document.getElementById('fieldWorkersDirTableBody');
      const badgeCount = document.getElementById('dirWorkersCount');
      if (badgeCount) badgeCount.textContent = workers.length;
      if (!tbody) return;
      if (!workers || workers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:#64748b; padding:24px;">No field workers registered yet for this company.</td></tr>';
        return;
      }
      tbody.innerHTML = workers.map(w => {
        const init = (w.employee_name || 'FW').substring(0, 2).toUpperCase();
        const salBasis = (w.salary_type || 'daily').toUpperCase();
        const baseRateFormatted = (w.salary_type === 'hourly') ? `₹${Number(w.hourly_salary || 0).toFixed(0)} / hr` : `₹${Number(w.day_salary || 0).toFixed(0)} / day`;
        const stPill = (w.status === 'Inactive') ? '<span class="status-pill status-inactive">Inactive</span>' : '<span class="status-pill status-active">Active</span>';
        return `<tr>
          <td>
            <div style="display:flex; align-items:center; gap:9px;">
              <div class="avatar-circle" style="width:28px; height:28px; font-size:11px; background:#1e3a8a;">${init}</div>
              <div>
                <div class="fw-cell-title">${w.employee_name}</div>
                <div class="fw-cell-sub">${w.designation || 'Field Executive'} &bull; ${w.department || 'Field Sales'}</div>
              </div>
            </div>
          </td>
          <td>
            <div style="font-weight:600; color:#334155;">${w.mobile_number || '-'}</div>
            <div class="fw-cell-sub">${w.email_id || '-'}</div>
          </td>
          <td><span class="badge-neutral"><i class="fa-solid fa-building" style="color:#0d9488;"></i> ${w.branch_name || 'Home Branch (Head Office)'}</span></td>
          <td>
            <span class="badge-blue">${salBasis}</span>
            <span class="fw-cell-sub" style="margin-left:4px;">Shift: ${w.shift_hours || '08:00'}h</span>
          </td>
          <td style="font-weight:700; color:#0f172a;">${baseRateFormatted}</td>
          <td style="font-weight:700; color:#15803d;">₹${Number(w.per_visit_incentive || 0).toFixed(2)} / visit</td>
          <td>${stPill}</td>
          <td style="text-align:center; white-space:nowrap;">
            <button type="button" class="btn-action-icon btn-action-edit" title="Edit / Configure Worker" onclick="editFieldWorkerFromRow('${w.id}')">
              <i class="fa-solid fa-pen"></i>
            </button>
            <button type="button" class="btn-action-icon btn-action-delete" title="Delete Field Worker" onclick="deleteFieldWorkerFromRow('${w.id}')" style="margin-left:4px;">
              <i class="fa-solid fa-trash"></i>
            </button>
          </td>
        </tr>`;
      }).join('');
    }

    function updateWorkerSelectDropdowns(workers) {
      ['pingWorkerSelect', 'asgnWorkerName', 'quickPunchWorker', 'visitWorkerName'].forEach(selectId => {
        const sel = document.getElementById(selectId);
        if (!sel || (CURRENT_USER_ROLE === 'employee' && LOGGED_IN_EMPLOYEE_NAME)) return;
        const curVal = sel.value;
        if (!workers || workers.length === 0) {
          sel.innerHTML = '<option value="">-- No Field Workers Registered --</option>';
          return;
        }
        let opts = '';
        if (selectId === 'asgnWorkerName' || selectId === 'visitWorkerName') {
          opts += '<option value="">-- Select Field Worker --</option>';
        }
        opts += workers.map(w => {
          const selected = (w.employee_name === curVal) ? 'selected' : '';
          return `<option value="${w.employee_name}" ${selected}>${w.employee_name} (${w.branch_name || 'Home Branch'})</option>`;
        }).join('');
        sel.innerHTML = opts;
        if (curVal) sel.value = curVal;
      });

      // Populate Manual Entry, Payment Entry, Advance, and Payslip dropdowns strictly with field workers of active company
      const manualSel = document.getElementById('inputFieldManualWorker');
      if (manualSel && workers) {
        const cur = manualSel.value;
        manualSel.innerHTML = '<option value="" disabled selected>-- Select Field Worker --</option>' +
          workers.map(w => `<option value="${escapeHtml(w.employee_name)}" ${w.employee_name === cur ? 'selected' : ''}>${escapeHtml(w.employee_name)} (${escapeHtml(w.designation || 'Field Executive')})</option>`).join('');
      }

      const payWorkerSel = document.getElementById('filterFieldPaymentWorker');
      if (payWorkerSel && workers) {
        const cur = payWorkerSel.value;
        payWorkerSel.innerHTML = '<option value="All" selected>All Field Workers</option>' +
          workers.map(w => `<option value="${escapeHtml(w.employee_name)}" ${w.employee_name === cur ? 'selected' : ''}>${escapeHtml(w.employee_name)}</option>`).join('');
        if (cur) payWorkerSel.value = cur;
      }

      const payAddSel = document.getElementById('inputFieldPaymentWorker');
      if (payAddSel && workers) {
        const cur = payAddSel.value;
        payAddSel.innerHTML = '<option value="" disabled selected>-- Select Field Worker --</option>' +
          workers.map(w => `<option value="${escapeHtml(w.employee_name)}" ${w.employee_name === cur ? 'selected' : ''}>${escapeHtml(w.employee_name)} (${escapeHtml(w.designation || 'Field Executive')})</option>`).join('');
      }

      const advSel = document.getElementById('inputFieldAdvanceWorker');
      if (advSel && workers) {
        const cur = advSel.value;
        advSel.innerHTML = '<option value="" disabled selected>-- Select Field Worker --</option>' +
          workers.map(w => `<option value="${escapeHtml(w.employee_name)}" ${w.employee_name === cur ? 'selected' : ''}>${escapeHtml(w.employee_name)} (${escapeHtml(w.designation || 'Field Executive')})</option>`).join('');
      }

      const payslipSel = document.getElementById('fwPayslipEmpSelect');
      if (payslipSel && workers) {
        const cur = payslipSel.value;
        if (CURRENT_USER_ROLE === 'employee' && LOGGED_IN_EMPLOYEE_NAME) {
          payslipSel.innerHTML = `<option value="${escapeHtml(LOGGED_IN_EMPLOYEE_NAME)}" selected>${escapeHtml(LOGGED_IN_EMPLOYEE_NAME)}</option>`;
          payslipSel.disabled = true;
        } else {
          payslipSel.disabled = false;
          payslipSel.innerHTML = workers.map((w, idx) => `<option value="${escapeHtml(w.employee_name)}" ${(cur ? w.employee_name === cur : idx === 0) ? 'selected' : ''}>${escapeHtml(w.employee_name)} (${escapeHtml(w.designation || 'Field Executive')})</option>`).join('');
        }
      }

      // Also dynamically update Register Modal's Registration Mode dropdown (fwExistingEmpSelect) with only Field Workers of active company
      const regSel = document.getElementById('fwExistingEmpSelect');
      if (regSel) {
        const curRegVal = regSel.value;
        let regOpts = '<option value="">+ Register Brand New Field Worker</option>';
        if (workers && workers.length > 0) {
          workers.forEach(w => {
            const wId = w.id || w._id || '';
            const wName = escapeHtml(w.employee_name || '');
            const wDept = escapeHtml(w.department || 'Field Sales');
            const wEmail = escapeHtml(w.email_id || '');
            const wMobile = escapeHtml(w.mobile_number || '');
            const wDesig = escapeHtml(w.designation || 'Field Executive');
            const wBranchId = escapeHtml(w.branch_id || 'HOME');
            const wBranchName = escapeHtml(w.branch_name || 'Home Branch (Head Office)');
            const wZone = escapeHtml(w.branch_name || w.territory_zone || 'Home Branch');
            const wSalType = escapeHtml(w.salary_type || 'daily');
            const wShiftHrs = escapeHtml(w.shift_hours || '08:00');
            const wDaySal = (w.day_salary !== undefined && w.day_salary !== null) ? w.day_salary : 600;
            const wHrSal = (w.hourly_salary !== undefined && w.hourly_salary !== null) ? w.hourly_salary : 100;
            const wVisitInc = (w.per_visit_incentive !== undefined && w.per_visit_incentive !== null) ? w.per_visit_incentive : 75;
            const wKmRate = (w.km_allowance_rate !== undefined && w.km_allowance_rate !== null) ? w.km_allowance_rate : 6;
            const wPetrolUnitKm = (w.petrol_unit_km !== undefined && w.petrol_unit_km !== null) ? w.petrol_unit_km : '';
            const wPetrolRateInr = (w.petrol_rate_inr !== undefined && w.petrol_rate_inr !== null) ? w.petrol_rate_inr : '';
            const wStatus = escapeHtml(w.status || 'Active');
            const isSelected = (curRegVal && String(curRegVal) === String(wId)) ? 'selected' : '';
            const wAllowedTabs = escapeHtml(JSON.stringify(w.allowed_tabs || []));

            regOpts += `<option value="${wId}" ${isSelected}
              data-name="${wName}"
              data-email="${wEmail}"
              data-mobile="${wMobile}"
              data-dept="${wDept}"
              data-desig="${wDesig}"
              data-branchid="${wBranchId}"
              data-branchname="${wBranchName}"
              data-zone="${wZone}"
              data-saltype="${wSalType}"
              data-shifthrs="${wShiftHrs}"
              data-daysal="${wDaySal}"
              data-hrsal="${wHrSal}"
              data-visitinc="${wVisitInc}"
              data-kmrate="${wKmRate}"
              data-petrolunitkm="${wPetrolUnitKm}"
              data-petrolrateinr="${wPetrolRateInr}"
              data-status="${wStatus}"
              data-allowedtabs="${wAllowedTabs}">Edit: ${wName} (${wDept})</option>`;
          });
        }
        regSel.innerHTML = regOpts;
        if (curRegVal) regSel.value = curRegVal;
      }
    }

    function renderAssignmentsTable(assignments) {
      const tbody = document.getElementById('assignedSitesTableBody');
      const badge = document.getElementById('assignedCountBadge');
      if (badge) badge.textContent = assignments.length;
      if (!tbody) return;
      if (!assignments || assignments.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:#64748b; padding:24px;">No target locations assigned for this date yet.</td></tr>';
        return;
      }
      tbody.innerHTML = assignments.map(a => {
        let stBadge = '<span class="badge-neutral">Pending Visit</span>';
        if (a.status === 'Completed') {
          stBadge = '<span class="badge-onsite"><i class="fa-solid fa-check-double"></i> Completed</span>';
        } else if (a.status === 'In Progress') {
          stBadge = '<span class="badge-transit"><i class="fa-solid fa-location-dot"></i> On-Site / Active</span>';
        }
        return `<tr>
          <td style="font-weight:700; white-space:nowrap;">${a.assigned_date}</td>
          <td><div class="fw-cell-title">${a.employee_name}</div></td>
          <td>
            <div class="fw-cell-title">${a.target_name}</div>
            <div class="fw-cell-sub">${a.target_address || 'Pinned Coordinates'}</div>
          </td>
          <td>
            <div style="font-weight:600;">${a.contact_person || '-'}</div>
            <div class="fw-cell-sub">${a.contact_phone || ''}</div>
          </td>
          <td><span class="badge-blue">${a.task_purpose}</span></td>
          <td style="font-weight:700; color:#0f766e;">${a.geofence_radius}m radius</td>
          <td>${stBadge}</td>
          <td style="text-align:center;">
            <div class="table-actions">
              <button type="button" class="btn-action-icon btn-action-view" title="Mark Completed" onclick="updateAssignmentStatus('${a.id}', 'Completed')">
                <i class="fa-solid fa-check"></i>
              </button>
              <button type="button" class="btn-action-icon btn-action-delete" title="Delete Assignment" onclick="deleteAssignment('${a.id}')">
                <i class="fa-solid fa-trash"></i>
              </button>
            </div>
          </td>
        </tr>`;
      }).join('');
    }

    function renderScheduledVisitsTable(assignments) {
      const tbody = document.getElementById('scheduledVisitsTableBody');
      const badgeCount = document.getElementById('scheduledVisitsCountBadge');
      const sidebarBadge = document.getElementById('sidebarScheduledVisitsBadge');
      const count = (assignments && assignments.length) || 0;
      if (badgeCount) badgeCount.textContent = count;
      if (sidebarBadge) sidebarBadge.textContent = count;
      if (!tbody) return;
      if (!assignments || assignments.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:#64748b; padding:28px;"><i class="fa-solid fa-calendar-xmark" style="font-size:24px; color:#94a3b8; display:block; margin-bottom:8px;"></i>No visits scheduled by field workers yet for this company.</td></tr>';
        return;
      }
      tbody.innerHTML = assignments.map((a, idx) => {
        let stBadge = '<span class="badge-neutral"><i class="fa-solid fa-clock"></i> Scheduled</span>';
        if (a.status === 'Completed') {
          stBadge = '<span class="badge-onsite"><i class="fa-solid fa-circle-check"></i> Completed</span>';
        } else if (a.status === 'In Progress') {
          stBadge = '<span class="badge-transit"><i class="fa-solid fa-person-walking"></i> In Progress</span>';
        } else if (a.status === 'Cancelled') {
          stBadge = '<span class="badge-detour"><i class="fa-solid fa-circle-xmark"></i> Cancelled</span>';
        }
        let priBadge = '<span class="badge-transit" style="padding:2px 8px; font-size:11px;">Normal</span>';
        if (a.priority === 'High' || a.priority === 'Urgent') {
          priBadge = '<span class="badge-detour" style="padding:2px 8px; font-size:11px;">High</span>';
        } else if (a.priority === 'Low') {
          priBadge = '<span class="badge-neutral" style="padding:2px 8px; font-size:11px;">Low</span>';
        }
        const workerName = escapeHtml(a.employee_name || 'Worker');
        const branchName = escapeHtml(a.branch_name || 'Home Branch');
        const targetName = escapeHtml(a.target_name || 'Client Site');
        const contact = a.client_contact ? `<div class="fw-cell-sub"><i class="fa-solid fa-phone" style="font-size:10px;"></i> ${escapeHtml(a.client_contact)}</div>` : '';
        const dateStr = escapeHtml(a.assigned_date || '-');
        const timeStr = escapeHtml(a.target_time || 'Full Day');
        const address = escapeHtml(a.target_address || a.city || ((a.latitude && a.longitude) ? `Coordinates: ${a.latitude}, ${a.longitude}` : 'Site Destination'));
        const purpose = escapeHtml(a.task_instruction || a.task_purpose || 'Client Visit');

        return `<tr data-worker="${workerName.toLowerCase()}" data-target="${targetName.toLowerCase()}" data-address="${address.toLowerCase()}" data-status="${escapeHtml(a.status || 'Scheduled')}">
          <td style="color:#64748b; font-weight:600;">${idx + 1}</td>
          <td>
            <div style="font-weight:700; color:#0f172a;">${workerName}</div>
            <div class="fw-cell-sub">${branchName}</div>
          </td>
          <td>
            <div style="font-weight:700; color:#0284c7;">${targetName}</div>
            ${contact}
          </td>
          <td>
            <div style="font-weight:600; color:#334155;">${dateStr}</div>
            <div class="fw-cell-sub">${timeStr}</div>
          </td>
          <td style="max-width:240px; font-size:12px; color:#475569;">${address}</td>
          <td>${priBadge}</td>
          <td>
            <div style="font-size:12px; color:#1e293b; font-weight:500;">${purpose}</div>
          </td>
          <td>${stBadge}</td>
        </tr>`;
      }).join('');
    }

    function filterScheduledVisitsTable() {
      const search = (document.getElementById('filterScheduledVisitsSearch')?.value || '').toLowerCase().trim();
      const status = (document.getElementById('filterScheduledVisitsStatus')?.value || '').trim();
      const rows = document.querySelectorAll('#scheduledVisitsTableBody tr');
      rows.forEach(r => {
        if (!r.dataset.worker) return;
        const w = r.dataset.worker || '';
        const t = r.dataset.target || '';
        const a = r.dataset.address || '';
        const st = r.dataset.status || '';
        const matchSearch = !search || w.includes(search) || t.includes(search) || a.includes(search);
        const matchStatus = !status || st.toLowerCase() === status.toLowerCase();
        r.style.display = (matchSearch && matchStatus) ? '' : 'none';
      });
    }

    function renderQuickCheckpointsTable(assignments) {
      const tbody = document.getElementById('quickCheckpointsTableBody');
      const countEl = document.getElementById('quickScheduleCount');
      if (countEl) countEl.textContent = assignments.length;
      if (!tbody) return;
      if (!assignments || assignments.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center; color:#64748b; padding:16px;">No target sites scheduled for today.</td></tr>';
        return;
      }
      tbody.innerHTML = assignments.map(a => {
        let badge = '<span class="badge-neutral">Pending</span>';
        if (a.status === 'Completed') badge = '<span class="badge-onsite">Completed</span>';
        else if (a.status === 'In Progress') badge = '<span class="badge-transit">Active</span>';
        return `<tr>
          <td style="font-weight:700;">${a.employee_name}</td>
          <td>${a.target_name}</td>
          <td><span class="badge-neutral">${a.task_purpose}</span></td>
          <td>${badge}</td>
        </tr>`;
      }).join('');
    }

    function renderCustomerVisitsTable(visits) {
      const tbody = document.getElementById('customerVisitsTableBody');
      const countEl = document.getElementById('visitsCountBadge');
      if (countEl) countEl.textContent = visits.length;
      if (!tbody) return;
      if (!visits || visits.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align:center; color:#64748b; padding:24px;">No customer visits logged yet.</td></tr>';
        return;
      }
      tbody.innerHTML = visits.map(v => {
        const verPill = v.is_location_verified ?
          `<span class="badge-onsite"><i class="fa-solid fa-circle-check"></i> ${v.verification_badge || 'On-Site Verified'}</span>` :
          `<span class="badge-detour"><i class="fa-solid fa-circle-exclamation"></i> ${v.verification_badge || 'Unverified'}</span>`;

        // Column 1: RECORDED AUDIO FILE
        const audioCol = v.has_audio_recording ?
          `<td style="text-align:center; white-space:nowrap;">
            <div style="display:inline-flex; align-items:center; gap:5px;">
              <button type="button" class="btn-visit-audio" onclick="openVisitAudioModal('${v.id}')" title="Play audio stream" style="background:linear-gradient(135deg, #1e3a8a, #2563eb); color:#fff; border:none; padding:4px 8px; border-radius:6px; font-size:11px; font-weight:700; display:inline-flex; align-items:center; gap:4px; cursor:pointer;">
                <i class="fa-solid fa-play"></i> 🎙️ ${Math.round(v.audio_duration_seconds || 0)}s
              </button>
              <a href="/api/field-worker/visits/${encodeURIComponent(v.id)}/audio" download class="btn-action-icon" title="Download audio recording" style="width:26px; height:26px; display:inline-flex; align-items:center; justify-content:center; background:#f1f5f9; border-radius:4px; color:#475569; text-decoration:none;">
                <i class="fa-solid fa-download"></i>
              </a>
            </div>
          </td>` :
          `<td style="text-align:center; color:#94a3b8; font-size:11px;">No Audio</td>`;

        // Column 2: AI TRANSCRIPTION
        const hasStt = v.has_audio_recording;
        const sttDocCol = hasStt ?
          `<td style="text-align:center; white-space:nowrap;">
            <div style="display:inline-flex; align-items:center; gap:5px;">
              <button type="button" onclick="openVisitTranscriptDocModal('${v.id}')" title="View Tamil & English AI Transcription verbatim conversation and export Word .docx" style="background:#f0fdf4; border:1px solid #86efac; color:#15803d; padding:4px 9px; border-radius:6px; font-size:11px; font-weight:700; display:inline-flex; align-items:center; gap:5px; cursor:pointer;">
                <i class="fa-solid fa-file-word"></i> தமிழ் &bull; English Doc
              </button>
            </div>
          </td>` :
          `<td style="text-align:center; color:#94a3b8; font-size:11px;">-</td>`;

        const actionCol = (CURRENT_USER_ROLE === 'super_admin' || CURRENT_USER_ROLE === 'company_admin') ?
          `<td style="text-align:center;">
            <div style="display:inline-flex; align-items:center; gap:6px;">
              <button type="button" class="btn-action-icon btn-action-edit" title="Edit Lead" onclick="openEditLeadModal('${v.id}')">
                <i class="fa-solid fa-pen"></i>
              </button>
              <button type="button" class="btn-action-icon btn-action-delete" title="Delete Visit" onclick="deleteCustomerVisit('${v.id}')">
                <i class="fa-solid fa-trash"></i>
              </button>
            </div>
          </td>` : '';
        return `<tr>
          <td style="font-weight:700; white-space:nowrap;">${v.timestamp}</td>
          <td><div class="fw-cell-title">${v.employee_name}</div></td>
          <td>
            <div class="fw-cell-title">${v.customer_name}</div>
            <div class="fw-cell-sub">${v.contact_person || '-'} &bull; ${v.customer_phone || '-'}</div>
          </td>
          <td class="fw-address-cell">${v.address}</td>
          <td style="font-weight:600;">${v.product_pitched}</td>
          <td><span class="badge-blue">${v.lead_status}</span></td>
          <td style="font-weight:800; color:#15803d; white-space:nowrap;">₹${Number(v.order_amount || 0).toFixed(2)}</td>
          <td>${verPill}</td>
          ${audioCol}
          ${sttDocCol}
          ${actionCol}
        </tr>`;
      }).join('');
    }

    let CURRENT_ACTIVE_AUDIO_VISIT_ID = null;

    function openVisitAudioModal(visitId) {
      CURRENT_ACTIVE_AUDIO_VISIT_ID = visitId;
      const modal = document.getElementById('visitAudioModalBackdrop');
      if (!modal) return;

      const player = document.getElementById('visitAudioPlayer');
      const downloadLink = document.getElementById('audioDownloadLink');
      const audioUrl = `/api/field-worker/visits/${encodeURIComponent(visitId)}/audio`;
      const noticeEl = document.getElementById('audioPlayerNotice');
      if (noticeEl) noticeEl.style.display = 'none';

      if (player) {
        player.onerror = () => {
          if (noticeEl) {
            noticeEl.style.display = 'block';
            noticeEl.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> <strong>Audio Recording Expired:</strong> This recording was saved on temporary server storage prior to Cloud Database persistence and expired during server deployment. All new audio recordings are now permanently preserved.';
          }
          const statusEl = document.getElementById('audioPlayerStatusText');
          if (statusEl) {
            statusEl.innerHTML = '<span style="color:#f87171;"><i class="fa-solid fa-circle-exclamation"></i> File Expired</span>';
          }
        };
        player.onloadeddata = () => {
          if (noticeEl) noticeEl.style.display = 'none';
          const statusEl = document.getElementById('audioPlayerStatusText');
          if (statusEl) {
            statusEl.innerHTML = '<span style="color:#60a5fa;"><i class="fa-solid fa-play"></i> Direct Stream</span>';
          }
        };

        player.src = audioUrl;
        player.playbackRate = 1.0;
        player.load();
      }
      if (downloadLink) {
        downloadLink.href = audioUrl;
      }

      modal.classList.remove('d-none');
    }

    function closeVisitAudioModal() {
      const modal = document.getElementById('visitAudioModalBackdrop');
      if (modal) modal.classList.add('d-none');
      const player = document.getElementById('visitAudioPlayer');
      if (player) {
        player.pause();
        player.src = '';
      }
    }

    function setAudioSpeed(speed) {
      const player = document.getElementById('visitAudioPlayer');
      if (player) player.playbackRate = Number(speed);
      showToast(`Playback speed set to ${speed}x`);
    }

    let CURRENT_ACTIVE_DOC_VISIT_ID = null;

    function openVisitTranscriptDocModal(visitId) {
      CURRENT_ACTIVE_DOC_VISIT_ID = visitId;
      const v = (typeof VISITS_DATA !== 'undefined' && Array.isArray(VISITS_DATA)) ?
        VISITS_DATA.find(x => String(x.id) === String(visitId)) : null;

      const modal = document.getElementById('visitTranscriptDocModalBackdrop');
      if (!modal) return;

      // Set .docx download link
      const docxLink = document.getElementById('transcriptDocxDownloadLink');
      if (docxLink) {
        docxLink.href = `/api/field-worker/visits/${encodeURIComponent(visitId)}/transcript/docx`;
      }

      switchTranscriptDocTab('tamil');
      modal.classList.remove('d-none');

      // Check Gemini API key status
      fetch('/api/system/gemini-key')
        .then(r => r.json())
        .then(k => {
          const banner = document.getElementById('geminiKeyNoticeBanner');
          if (banner) {
            banner.style.display = (!k || !k.has_key) ? 'flex' : 'none';
          }
        })
        .catch(() => {});

      // Set loading placeholder while fetching fresh transcript
      const docTamil = document.getElementById('docTamilText');
      const docEng = document.getElementById('docEnglishText');
      
      const prevTa = (v && (v.conversation_transcript_tamil || v.conversation_transcript)) || '';
      const prevEn = (v && v.conversation_transcript_english) || '';
      const isErrPlaceholder = !prevEn || prevEn.includes('error') || prevEn.includes('No module') || prevEn.includes('Fallback');

      if (docTamil) {
        docTamil.innerHTML = isErrPlaceholder 
          ? '<i class="fa-solid fa-spinner fa-spin"></i> தமிழ் நேரடி உரையாடல் AI செயலாக்கப்பட்டு வருகிறது...'
          : prevTa;
      }
      if (docEng) {
        docEng.innerHTML = isErrPlaceholder
          ? '<i class="fa-solid fa-spinner fa-spin"></i> AI speech-to-text transcription in progress...'
          : prevEn;
      }

      // Fetch dynamic detailed transcript with cache-buster
      fetch(`/api/field-worker/visits/${encodeURIComponent(visitId)}/transcript?_t=${Date.now()}`)
        .then(r => r.json())
        .then(data => {
          if (!data || !data.success) return;
          const tTamil = data.transcript_tamil || 'தமிழ் உரை கிடைக்கவில்லை.';
          const tEng = data.transcript_english || 'English translation not available.';

          if (docTamil) docTamil.textContent = tTamil;
          if (docEng) docEng.textContent = tEng;

          // Update local visit cache
          if (v) {
            v.conversation_transcript_tamil = tTamil;
            v.conversation_transcript_english = tEng;
          }
        })
        .catch(() => {});
    }

    function closeVisitTranscriptDocModal() {
      const modal = document.getElementById('visitTranscriptDocModalBackdrop');
      if (modal) modal.classList.add('d-none');
    }

    function switchTranscriptDocTab(tab) {
      const pTamil = document.getElementById('docPaneTamil');
      const pEng = document.getElementById('docPaneEnglish');
      const bTamil = document.getElementById('tabBtnDocTamil');
      const bEng = document.getElementById('tabBtnDocEnglish');

      if (!pTamil || !pEng) return;

      if (tab === 'tamil') {
        pTamil.classList.remove('d-none');
        pEng.classList.add('d-none');
        if (bTamil) { bTamil.style.background = '#2563eb'; bTamil.style.color = '#ffffff'; }
        if (bEng) { bEng.style.background = '#e2e8f0'; bEng.style.color = '#475569'; }
      } else {
        pTamil.classList.add('d-none');
        pEng.classList.remove('d-none');
        if (bTamil) { bTamil.style.background = '#e2e8f0'; bTamil.style.color = '#475569'; }
        if (bEng) { bEng.style.background = '#059669'; bEng.style.color = '#ffffff'; }
      }
    }

    async function reprocessTranscriptDocAI() {
      if (!CURRENT_ACTIVE_DOC_VISIT_ID) return;
      showToast('Running Google Gemini Tamil Audio Transcription... please wait');
      try {
        const res = await fetch(`/api/field-worker/visits/${encodeURIComponent(CURRENT_ACTIVE_DOC_VISIT_ID)}/reprocess-ai`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Tamil AI transcript updated!');
          openVisitTranscriptDocModal(CURRENT_ACTIVE_DOC_VISIT_ID);
          if (typeof loadFieldWorkerDashboard === 'function') loadFieldWorkerDashboard();
        } else {
          showToast(data.error || 'Failed to reprocess audio AI');
        }
      } catch (err) {
        showToast('Error connecting to Gemini AI');
      }
    }

    async function promptConfigureGeminiKey() {
      const key = prompt('Enter your Google Gemini API Key (starts with AIza...):');
      if (!key || !key.trim()) return;
      try {
        const res = await fetch('/api/system/gemini-key', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ gemini_api_key: key.trim() })
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message);
          const banner = document.getElementById('geminiKeyNoticeBanner');
          if (banner) banner.style.display = 'none';
          if (CURRENT_ACTIVE_DOC_VISIT_ID) {
            reprocessTranscriptDocAI();
          }
        } else {
          showToast(data.error || 'Failed to save Gemini key');
        }
      } catch (e) {
        showToast('Error saving Gemini key');
      }
    }

    function updateLinkedAssignmentDropdown(assignments) {
      const sel = document.getElementById('visitAssignmentId');
      if (!sel) return;
      const curVal = sel.value;
      sel.innerHTML = '<option value="">-- Direct / Self-Sourced Visit --</option>' +
        assignments.map(a => {
          const selAttr = (a.id === curVal) ? 'selected' : '';
          return `<option value="${a.id}"
            data-target="${a.target_name}"
            data-person="${a.contact_person || ''}"
            data-phone="${a.contact_phone || ''}"
            data-lat="${a.target_lat}"
            data-lng="${a.target_lng}" ${selAttr}>
            Assigned: ${a.target_name} (${a.employee_name})
          </option>`;
        }).join('');
    }

    async function loadFieldPayrollDataAsync() {
      const tbody = document.getElementById('fieldPayrollTableBody');
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; padding:32px; color:#64748b;">
          <div style="display:flex; align-items:center; justify-content:center; gap:10px;">
            <i class="fa-solid fa-spinner fa-spin" style="font-size:16px; color:#2563eb;"></i>
            <span style="font-weight:600; font-size:12px; color:#334155;">Calculating monthly field payroll & travel allowances...</span>
          </div>
        </td></tr>`;
      }
      const cid = getActiveCompanyId();
      const mo = document.getElementById('globalMonthInput').value;
      try {
        const res = await fetch(`/api/field-worker/salary-report?company_id=${encodeURIComponent(cid)}&month=${encodeURIComponent(mo)}`);
        const data = await res.json();
        if (data.success && Array.isArray(data.salary_reports)) {
          PAYROLL_DATA = data.salary_reports;
          renderFieldPayrollTable(PAYROLL_DATA);
        } else {
          renderFieldPayrollTable([]);
        }
      } catch (e) {
        console.error('Failed to load payroll report:', e);
        renderFieldPayrollTable([]);
      }
    }

    function handleMonthFilterChange() {
      PAYROLL_DATA = [];
      const defaultPane = (CURRENT_USER_ROLE === 'employee') ? 'paneFieldPunch' : 'paneLiveTracking';
      const activePane = sessionStorage.getItem('activeFieldTab') || defaultPane;
      if (activePane === 'paneFieldPayroll') {
        loadFieldPayrollDataAsync();
      }
      refreshOverviewState();
    }

    function renderFieldPayrollTable(reports) {
      const tbody = document.getElementById('fieldPayrollTableBody');
      if (!tbody) return;
      const list = (CURRENT_USER_ROLE === 'employee' && LOGGED_IN_EMPLOYEE_NAME)
        ? (reports || []).filter(r => r.employee_name === LOGGED_IN_EMPLOYEE_NAME)
        : (reports || []);
      if (!list || list.length === 0) {
        tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; color:#64748b; padding:24px;">${CURRENT_USER_ROLE === 'employee' ? 'No payslip records found for this month.' : 'No field workers found for this company.'}</td></tr>`;
        return;
      }
      tbody.innerHTML = list.map(r => {
        const detourInfo = (r.detour_alerts > 0) ?
          `<div class="fw-cell-sub" style="color:#dc2626; font-weight:700;">${r.detour_alerts} Detour Alerts</div>` :
          `<div class="fw-cell-sub" style="color:#16a34a;">0 Detours</div>`;
        return `<tr>
          <td>
            <div class="fw-cell-title">${r.employee_name}</div>
            <div class="fw-cell-sub">${r.designation}</div>
          </td>
          <td>
            <span class="badge-neutral"><i class="fa-solid fa-building" style="color:#0d9488;"></i> ${r.branch_name || r.territory_zone || 'Home Branch (Head Office)'}</span>
            <div class="fw-cell-sub">${(r.salary_type || '').toUpperCase()} (${r.shift_hours}h)</div>
          </td>
          <td>
            <div class="fw-cell-title">${r.working_days} Days</div>
            <div class="fw-cell-sub">${r.total_hours} hrs worked</div>
          </td>
          <td style="font-weight:700;">${r.completed_assignments} / ${r.total_assigned_locations}</td>
          <td>
            <div style="font-weight:700; color:#15803d;">${r.verified_visits} Verified</div>
            <div class="fw-cell-sub">Orders: ₹${Number(r.orders_value || 0).toFixed(0)}</div>
          </td>
          <td>
            <div style="font-weight:700; color:#2563eb;">${Number(r.total_km_traveled || 0).toFixed(2)} KM</div>
            ${detourInfo}
          </td>
          <td style="font-weight:700; color:#0f172a; white-space:nowrap;">₹${Number(r.base_attendance_pay || 0).toFixed(2)}</td>
          <td style="background-color:#f0fdf4; white-space:nowrap;">
            <div style="font-weight:700; color:#15803d;">+ ₹${Number(r.visit_incentive_pay || 0).toFixed(2)}</div>
            <div class="fw-cell-sub">@ ₹${Number(r.per_visit_incentive_rate || 0).toFixed(0)}/visit</div>
          </td>
          <td style="background-color:#eff6ff; white-space:nowrap;">
            ${(Number(r.petrol_allowance_paid || 0) > 0) ? `
              <div style="display:flex; align-items:center; gap:4px; margin-bottom:2px;">
                <span style="font-weight:700; color:#1d4ed8;">+ ₹${Number(r.travel_allowance_remaining !== undefined ? r.travel_allowance_remaining : r.travel_allowance_pay || 0).toFixed(2)}</span>
                <span style="font-size:9.5px; background:#dcfce7; color:#15803d; border:1px solid #bbf7d0; padding:1px 5px; border-radius:4px; font-weight:700;">PAID ₹${Number(r.petrol_allowance_paid).toFixed(0)}</span>
              </div>
              <div class="fw-cell-sub">Auto: ₹${Number(r.travel_allowance_calculated || r.petrol_allowance || 0).toFixed(0)} (${Number(r.total_km_traveled || 0).toFixed(1)} KM)</div>
            ` : `
              <div style="font-weight:700; color:#1d4ed8;">+ ₹${Number(r.travel_allowance_pay || 0).toFixed(2)}</div>
              <div class="fw-cell-sub">Distance: ${Number(r.total_km_traveled || 0).toFixed(1)} KM</div>
            `}
          </td>
          <td style="background-color:#f8fafc; white-space:nowrap;">
            <span style="font-size:13px; font-weight:800; color:#0f172a;">₹${Number(r.net_field_payable || 0).toFixed(2)}</span>
          </td>
          <td style="text-align:center;">
            <div style="display:inline-flex; align-items:center; gap:6px; justify-content:center;">
              <button type="button" class="btn-action-icon btn-action-view" onclick="openFieldPayslipModal('${escapeHtml(r.employee_name)}', '${encodeURIComponent(document.getElementById('globalMonthInput').value)}')" title="View Payslip in Modal">
                <i class="fa-solid fa-eye"></i>
              </button>
              <a href="/api/field-worker/payslip-pdf?company_id=${encodeURIComponent(getActiveCompanyId())}&month=${encodeURIComponent(document.getElementById('globalMonthInput').value)}&employee_name=${encodeURIComponent(r.employee_name)}" class="fw-btn fw-btn-dark fw-btn-sm" title="Download Payslip PDF">
                <i class="fa-solid fa-file-pdf" style="color:#f87171;"></i> Payslip
              </a>
            </div>
          </td>
        </tr>`;
      }).join('');
    }

    function openFieldPayslipModal(empName, month) {
      if (!empName) return;
      const cid = getActiveCompanyId();
      const mo = month || document.getElementById('globalMonthInput')?.value || INITIAL_MONTH_YEAR;
      const modal = document.getElementById('fwPayslipModalBackdrop');
      const title = document.getElementById('fwPayslipModalTitle');
      const subtitle = document.getElementById('fwPayslipModalSubtitle');
      const iframe = document.getElementById('fwPayslipPreviewIframe');
      const spinner = document.getElementById('fwPayslipLoadingSpinner');
      const downloadBtn = document.getElementById('btnFwPayslipModalDownload');

      if (title) title.textContent = `PAYSLIP PREVIEW — ${empName.toUpperCase()}`;
      if (subtitle) subtitle.textContent = `Month: ${mo} • Company: ${INITIAL_COMPANY_NAME}`;

      const pdfUrl = `/api/field-worker/payslip-pdf?company_id=${encodeURIComponent(cid)}&month=${encodeURIComponent(mo)}&employee_name=${encodeURIComponent(empName)}&view=1#toolbar=0&navpanes=0&scrollbar=1`;
      const downloadUrl = `/api/field-worker/payslip-pdf?company_id=${encodeURIComponent(cid)}&month=${encodeURIComponent(mo)}&employee_name=${encodeURIComponent(empName)}`;

      if (downloadBtn) downloadBtn.href = downloadUrl;
      if (spinner) spinner.style.display = 'flex';
      if (iframe) {
        iframe.style.display = 'none';
        iframe.src = pdfUrl;
        iframe.onload = function () {
          if (spinner) spinner.style.display = 'none';
          iframe.style.display = 'block';
        };
      }
      if (modal) modal.classList.remove('d-none');
    }

    function closeFieldPayslipModal() {
      const modal = document.getElementById('fwPayslipModalBackdrop');
      const iframe = document.getElementById('fwPayslipPreviewIframe');
      if (modal) modal.classList.add('d-none');
      if (iframe) iframe.src = 'about:blank';
    }

    // =========================================================================
    // DYNAMIC FORM SUBMISSIONS (AJAX POST / PUT / DELETE)
    // =========================================================================
    async function sendLocationPingPayload(payload) {
      payload.company_id = getActiveCompanyId();
      payload.date = document.getElementById('globalDateInput').value;
      try {
        const res = await fetch('/api/field-worker/location-ping', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!data.success) {
          showToast(data.error || 'Failed to log GPS ping', true);
          return;
        }
        showToast(data.message);
        await refreshOverviewState();
      } catch (err) {
        showToast('Network error logging GPS ping: ' + err.message, true);
      }
    }

    let fwLastCoords = null;
    async function getDeviceCurrentPosition(maxWaitMs = 800) {
      if (fwLastCoords && (Date.now() - fwLastCoords.ts < 180000)) {
        return fwLastCoords.coords;
      }
      const fallbackCoords = () => {
        if (fwLastCoords) return fwLastCoords.coords;
        const latEl = document.getElementById('pingLat');
        const lngEl = document.getElementById('pingLng');
        const lat = latEl ? (parseFloat(latEl.value) || INITIAL_COMPANY_LAT) : INITIAL_COMPANY_LAT;
        const lng = lngEl ? (parseFloat(lngEl.value) || INITIAL_COMPANY_LNG) : INITIAL_COMPANY_LNG;
        return { lat, lng, accuracy: 50 };
      };
      if (!navigator.geolocation) {
        return fallbackCoords();
      }
      const geoPromise = new Promise((resolve) => {
        navigator.geolocation.getCurrentPosition(
          pos => {
            const c = { lat: pos.coords.latitude, lng: pos.coords.longitude, accuracy: pos.coords.accuracy || 10 };
            fwLastCoords = { coords: c, ts: Date.now() };
            resolve(c);
          },
          () => resolve(fallbackCoords()),
          { enableHighAccuracy: true, timeout: 4000, maximumAge: 180000 }
        );
      });
      return Promise.race([
        geoPromise,
        new Promise(r => setTimeout(() => r(fallbackCoords()), maxWaitMs))
      ]);
    }

    function captureAndSendLiveGPS() {
      const pingSel = document.getElementById('pingWorkerSelect');
      const empName = pingSel ? pingSel.value : LOGGED_IN_EMPLOYEE_NAME;
      if (!empName) {
        showToast('Please select or register a field worker first.', true);
        return;
      }
      const noteEl = document.getElementById('pingNote');
      const note = noteEl ? noteEl.value : 'Live Device GPS Check-In';
      const latEl = document.getElementById('pingLat');
      const lngEl = document.getElementById('pingLng');
      const fallbackLat = latEl ? (parseFloat(latEl.value) || INITIAL_COMPANY_LAT) : INITIAL_COMPANY_LAT;
      const fallbackLng = lngEl ? (parseFloat(lngEl.value) || INITIAL_COMPANY_LNG) : INITIAL_COMPANY_LNG;

      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          pos => {
            if (latEl) latEl.value = pos.coords.latitude.toFixed(6);
            if (lngEl) lngEl.value = pos.coords.longitude.toFixed(6);
            sendLocationPingPayload({
              employee_name: empName,
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
              accuracy: pos.coords.accuracy || 10,
              activity_note: note || 'Live Device GPS Check-In'
            });
          },
          () => {
            sendLocationPingPayload({
              employee_name: empName,
              latitude: fallbackLat,
              longitude: fallbackLng,
              activity_note: note || 'Manual Coordinates Check-In'
            });
          },
          { enableHighAccuracy: true, timeout: 5000 }
        );
      } else {
        sendLocationPingPayload({
          employee_name: empName,
          latitude: fallbackLat,
          longitude: fallbackLng,
          activity_note: note || 'GPS Check-In'
        });
      }
    }

    function toggleAutoGPSTracking() {
      const btn = document.getElementById('btnAutoTrack');
      if (autoTrackTimer) {
        clearInterval(autoTrackTimer);
        autoTrackTimer = null;
        btn.className = 'fw-btn fw-btn-outline fw-btn-block';
        btn.innerHTML = '<i class="fa-solid fa-satellite"></i> Start Continuous Live Tracking (25s)';
        showToast('Continuous GPS tracking paused.');
      } else {
        captureAndSendLiveGPS();
        autoTrackTimer = setInterval(captureAndSendLiveGPS, 25000);
        btn.className = 'fw-btn fw-btn-danger fw-btn-block';
        btn.innerHTML = '<i class="fa-solid fa-circle-stop"></i> Stop Continuous Live Tracking (Active)';
      }
    }

    function populateExistingEmployeeForField(sel) {
      const opt = sel.options[sel.selectedIndex];
      if (!opt || !opt.value) {
        document.getElementById('fwRegName').value = '';
        document.getElementById('fwRegEmail').value = '';
        document.getElementById('fwRegMobile').value = '';
        document.getElementById('fwRegPhotoData').value = '';
        const branchSel = document.getElementById('fwRegBranchId');
        if (branchSel) branchSel.value = 'HOME';
        document.getElementById('fwPhotoPreviewContainer').innerHTML = '<i class="fa-solid fa-user" style="color:#94a3b8; font-size:18px;"></i>';
        if (document.getElementById('fwRegPetrolUnitKm')) document.getElementById('fwRegPetrolUnitKm').value = '1 KM';
        if (document.getElementById('fwRegPetrolRateInr')) document.getElementById('fwRegPetrolRateInr').value = '';
        if (document.getElementById('fwRegKmRate')) document.getElementById('fwRegKmRate').value = '';
        if (typeof updateWorkerPetrolRatePreview === 'function') updateWorkerPetrolRatePreview();
        setFieldWorkerPermissionCheckboxes(null);
        return;
      }
      document.getElementById('fwRegName').value = opt.dataset.name || '';
      document.getElementById('fwRegEmail').value = opt.dataset.email || '';
      document.getElementById('fwRegMobile').value = opt.dataset.mobile || '';
      document.getElementById('fwRegDept').value = opt.dataset.dept || 'Field Sales';
      document.getElementById('fwRegDesig').value = opt.dataset.desig || 'Field Executive';
      const branchSel = document.getElementById('fwRegBranchId');
      if (branchSel) branchSel.value = opt.dataset.branchid || 'HOME';
      document.getElementById('fwRegSalaryType').value = opt.dataset.saltype || 'daily';
      document.getElementById('fwRegShiftHours').value = opt.dataset.shifthrs || '08:00';
      const salType = opt.dataset.saltype || 'daily';
      document.getElementById('fwRegBaseRate').value = salType === 'hourly' ? (opt.dataset.hrsal || 100) : (opt.dataset.daysal || 600);
      document.getElementById('fwRegVisitIncentive').value = opt.dataset.visitinc || 75;
      const unitKmEl = document.getElementById('fwRegPetrolUnitKm');
      if (unitKmEl) unitKmEl.value = '1 KM';
      const rateInrEl = document.getElementById('fwRegPetrolRateInr');
      if (rateInrEl) rateInrEl.value = opt.dataset.petrolrateinr || '';
      document.getElementById('fwRegKmRate').value = opt.dataset.kmrate || '';
      if (typeof updateWorkerPetrolRatePreview === 'function') updateWorkerPetrolRatePreview();
      document.getElementById('fwRegStatus').value = opt.dataset.status || 'Active';

      let allowed = null;
      if (opt.dataset.allowedtabs) {
        try {
          allowed = JSON.parse(opt.dataset.allowedtabs);
        } catch (e) {
          allowed = null;
        }
      }
      setFieldWorkerPermissionCheckboxes(allowed);
    }

    // Dynamic Worker Registration (AJAX, Zero Reload)
    async function submitFieldWorkerRegistration(e) {
      e.preventDefault();
      const salType = document.getElementById('fwRegSalaryType').value;
      const baseRate = parseFloat(document.getElementById('fwRegBaseRate').value) || 0;
      const branchSel = document.getElementById('fwRegBranchId');
      const branchId = branchSel ? branchSel.value : 'HOME';
      const branchName = (branchSel && branchSel.selectedOptions && branchSel.selectedOptions[0]) 
        ? branchSel.selectedOptions[0].textContent.replace('🏠 ', '').trim() 
        : 'Home Branch (Head Office)';

      const checkedTabs = Array.from(document.querySelectorAll('input[name="fwTabPerm"]:checked')).map(cb => cb.value);

      const payload = {
        company_id: getActiveCompanyId(),
        existing_employee_id: document.getElementById('fwExistingEmpSelect').value,
        employee_name: document.getElementById('fwRegName').value,
        status: document.getElementById('fwRegStatus').value,
        email_id: document.getElementById('fwRegEmail').value,
        mobile_number: document.getElementById('fwRegMobile').value,
        department: document.getElementById('fwRegDept').value,
        designation: document.getElementById('fwRegDesig').value,
        branch_id: branchId,
        branch_name: branchName,
        branch: branchName,
        territory_zone: branchName,
        salary_type: salType,
        shift_hours: document.getElementById('fwRegShiftHours').value,
        day_salary: salType === 'daily' ? baseRate : 0,
        hourly_salary: salType === 'hourly' ? baseRate : 0,
        half_day_salary: salType === 'half_day' ? baseRate : Math.round(baseRate / 2),
        per_visit_incentive: parseFloat(document.getElementById('fwRegVisitIncentive').value) || 0,
        petrol_unit_km: 1.0,
        petrol_rate_inr: (document.getElementById('fwRegPetrolRateInr')?.value !== '' && document.getElementById('fwRegPetrolRateInr')?.value !== null && !isNaN(parseFloat(document.getElementById('fwRegPetrolRateInr')?.value))) ? parseFloat(document.getElementById('fwRegPetrolRateInr')?.value) : null,
        has_custom_petrol_rate: Boolean(document.getElementById('fwRegPetrolRateInr')?.value && parseFloat(document.getElementById('fwRegPetrolRateInr')?.value) > 0),
        km_allowance_rate: (document.getElementById('fwRegPetrolRateInr')?.value && parseFloat(document.getElementById('fwRegPetrolRateInr')?.value) > 0) ? (Math.round(parseFloat(document.getElementById('fwRegPetrolRateInr').value) * 100) / 100) : null,
        photo_data: document.getElementById('fwRegPhotoData').value,
        is_field_worker: true,
        allowed_tabs: checkedTabs
      };

      try {
        const res = await fetch('/api/field-worker/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!data.success) {
          showToast(data.error || 'Registration failed', true);
          return;
        }
        showToast(data.message);
        const empSel = document.getElementById('fwExistingEmpSelect');
        if (empSel && empSel.selectedOptions && empSel.selectedOptions[0]) {
          empSel.selectedOptions[0].dataset.allowedtabs = JSON.stringify(checkedTabs);
        }
        closeRegisterWorkerModal();
        const regForm = document.getElementById('registerFieldWorkerForm');
        if (regForm) regForm.reset();
        document.getElementById('fwRegPhotoData').value = '';
        document.getElementById('fwPhotoPreviewContainer').innerHTML = '<i class="fa-solid fa-user" style="color:#94a3b8; font-size:18px;"></i>';
        await refreshOverviewState();
      } catch (err) {
        showToast('Network error during registration: ' + err.message, true);
      }
    }

    // Dynamic Location Assignment (AJAX, Zero Reload)
    async function submitLocationAssignment(e) {
      e.preventDefault();
      const payload = {
        company_id: getActiveCompanyId(),
        employee_name: (document.getElementById('asgnWorkerName') ? document.getElementById('asgnWorkerName').value : '') || LOGGED_IN_EMPLOYEE_NAME,
        assigned_date: document.getElementById('asgnDate').value,
        target_name: document.getElementById('asgnTargetName').value,
        task_purpose: document.getElementById('asgnPurpose').value,
        contact_person: document.getElementById('asgnContactPerson').value,
        contact_phone: document.getElementById('asgnContactPhone').value,
        target_lat: parseFloat(document.getElementById('asgnLat').value),
        target_lng: parseFloat(document.getElementById('asgnLng').value),
        geofence_radius: parseFloat(document.getElementById('asgnRadius').value) || 150,
        target_address: document.getElementById('asgnAddress').value
      };

      try {
        const res = await fetch('/api/field-worker/assignments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (!data.success) {
          showToast(data.error || 'Could not create assignment', true);
          return;
        }
        showToast(data.message);
        document.getElementById('asgnTargetName').value = '';
        document.getElementById('asgnContactPerson').value = '';
        document.getElementById('asgnContactPhone').value = '';
        document.getElementById('asgnAddress').value = '';
        await refreshOverviewState();
      } catch (err) {
        showToast('Network error creating assignment: ' + err.message, true);
      }
    }

    async function updateAssignmentStatus(id, status) {
      try {
        const res = await fetch(`/api/field-worker/assignments/${encodeURIComponent(id)}?company_id=${encodeURIComponent(getActiveCompanyId())}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ status })
        });
        const data = await res.json();
        if (data.success) {
          showToast('Assignment status updated to ' + status);
          await refreshOverviewState();
        }
      } catch (err) {
        showToast('Update error: ' + err.message, true);
      }
    }

    async function deleteAssignment(id) {
      if (!confirm('Are you sure you want to delete this target location assignment?')) return;
      try {
        const res = await fetch(`/api/field-worker/assignments/${encodeURIComponent(id)}?company_id=${encodeURIComponent(getActiveCompanyId())}`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
          showToast('Assignment removed successfully.');
          await refreshOverviewState();
        }
      } catch (err) {
        showToast('Delete error: ' + err.message, true);
      }
    }

    // =========================================================================
    // AI FACE + LIVE GPS ATTENDANCE TERMINAL (MATCHES ROOT '/' ROUTE TERMINAL)
    // =========================================================================
    let terminalStream = null;
    let isTerminalCameraRunning = false;
    let isHandsFreeActive = true;
    let isProcessingPunch = false;
    let cooldownUntil = 0;
    let sensitivityMode = 'normal';

    let faceMesh = null;
    let faceMeshReady = false;
    let isDetectionRunning = false;
    let isProcessingFrame = false;
    let animFrameId = null;

    let blinkCount = 0;
    let lastBlinkTime = 0;
    let isEyesClosed = false;
    let closedFrameCount = 0;
    let baselineEAR = 0.28;
    let blinkResetTimer = null;
    let terminalAudioCtx = null;

    const LEFT_EYE = {
      h1: 33, h2: 133,
      v1_top: 160, v1_bot: 144,
      v2_top: 158, v2_bot: 153
    };

    const RIGHT_EYE = {
      h1: 362, h2: 263,
      v1_top: 385, v1_bot: 380,
      v2_top: 387, v2_bot: 373
    };

    function dist2D(p1, p2) {
      const dx = p1.x - p2.x;
      const dy = p1.y - p2.y;
      return Math.sqrt(dx * dx + dy * dy);
    }

    function calculateEAR(landmarks, eye) {
      const p_h1 = landmarks[eye.h1];
      const p_h2 = landmarks[eye.h2];
      const p_v1_top = landmarks[eye.v1_top];
      const p_v1_bot = landmarks[eye.v1_bot];
      const p_v2_top = landmarks[eye.v2_top];
      const p_v2_bot = landmarks[eye.v2_bot];
      if (!p_h1 || !p_h2 || !p_v1_top || !p_v1_bot || !p_v2_top || !p_v2_bot) return null;
      const hDist = dist2D(p_h1, p_h2);
      if (hDist <= 0.0001) return null;
      const v1Dist = dist2D(p_v1_top, p_v1_bot);
      const v2Dist = dist2D(p_v2_top, p_v2_bot);
      return (v1Dist + v2Dist) / (2.0 * hDist);
    }

    function playTerminalChime(type) {
      try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        if (!terminalAudioCtx) terminalAudioCtx = new AudioCtx();
        if (terminalAudioCtx.state === 'suspended') {
          terminalAudioCtx.resume();
        }
        const osc = terminalAudioCtx.createOscillator();
        const gain = terminalAudioCtx.createGain();
        osc.connect(gain);
        gain.connect(terminalAudioCtx.destination);

        if (type === 'blink') {
          osc.type = 'sine';
          osc.frequency.setValueAtTime(659.25, terminalAudioCtx.currentTime);
          gain.gain.setValueAtTime(0.06, terminalAudioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, terminalAudioCtx.currentTime + 0.12);
          osc.start();
          osc.stop(terminalAudioCtx.currentTime + 0.12);
        } else if (type === 'success') {
          osc.type = 'triangle';
          osc.frequency.setValueAtTime(523.25, terminalAudioCtx.currentTime);
          osc.frequency.setValueAtTime(783.99, terminalAudioCtx.currentTime + 0.08);
          osc.frequency.setValueAtTime(1046.50, terminalAudioCtx.currentTime + 0.16);
          gain.gain.setValueAtTime(0.12, terminalAudioCtx.currentTime);
          gain.gain.exponentialRampToValueAtTime(0.001, terminalAudioCtx.currentTime + 0.38);
          osc.start();
          osc.stop(terminalAudioCtx.currentTime + 0.38);
        }
      } catch (e) {}
    }

    function updateBlinkHUD(count, text, isCooldown = false) {
      const hudPill = document.getElementById('blinkHudPill');
      const hudIcon = document.getElementById('blinkHudIcon');
      const hudText = document.getElementById('blinkHudText');
      const hudDots = document.getElementById('blinkHudDots');
      const dot1 = document.getElementById('blinkDot1');
      const dot2 = document.getElementById('blinkDot2');
      const eyeState = document.getElementById('blinkEyeState');
      if (!hudPill) return;

      if (isCooldown) {
        hudPill.className = 'blink-hud-pill blink-cooldown';
        if (hudIcon) hudIcon.textContent = '⏳';
        if (hudText) hudText.textContent = text || 'Ready in a moment...';
        if (hudDots) hudDots.style.display = 'none';
        if (eyeState) eyeState.style.display = 'none';
        return;
      }

      if (hudDots) hudDots.style.display = 'inline-flex';
      if (eyeState) eyeState.style.display = 'inline-block';

      if (count === 0) {
        hudPill.className = 'blink-hud-pill';
        if (hudIcon) hudIcon.textContent = '👁️';
        if (hudText) hudText.textContent = text || 'Blink 2 times to punch hands-free';
        if (dot1) dot1.classList.remove('active');
        if (dot2) dot2.classList.remove('active');
      } else if (count === 1) {
        hudPill.className = 'blink-hud-pill blink-stage-1';
        if (hudIcon) hudIcon.textContent = '👁️';
        if (hudText) hudText.textContent = text || '1st Blink Detected! Blink once more...';
        if (dot1) dot1.classList.add('active');
        if (dot2) dot2.classList.remove('active');
      } else if (count >= 2) {
        hudPill.className = 'blink-hud-pill blink-stage-2';
        if (hudIcon) hudIcon.textContent = '✨';
        if (hudText) hudText.textContent = text || '2 Blinks Verified! Recording...';
        if (dot1) dot1.classList.add('active');
        if (dot2) dot2.classList.add('active');
      }
    }

    function resetBlinkState(message = null) {
      blinkCount = 0;
      isEyesClosed = false;
      closedFrameCount = 0;
      if (blinkResetTimer) {
        clearTimeout(blinkResetTimer);
        blinkResetTimer = null;
      }
      updateBlinkHUD(0, message);
    }

    function reticlePulse() {
      const faceReticle = document.getElementById('faceReticle');
      if (faceReticle) {
        faceReticle.style.borderColor = '#10b981';
        faceReticle.style.boxShadow = '0 0 25px rgba(16, 185, 129, 0.7)';
        setTimeout(() => {
          if (faceReticle) {
            faceReticle.style.borderColor = 'rgba(56, 189, 248, 0.5)';
            faceReticle.style.boxShadow = '0 0 15px rgba(56, 189, 248, 0.2)';
          }
        }, 1500);
      }
    }

    function handleBlinkDetected() {
      const now = Date.now();
      const punchContainer = document.getElementById('punchDetailContainer');
      if (now < cooldownUntil || isProcessingPunch || (punchContainer && punchContainer.style.display === 'block')) return;

      if (blinkCount > 0 && (now - lastBlinkTime > 4500)) {
        resetBlinkState();
      }

      blinkCount++;
      lastBlinkTime = now;
      const eyeState = document.getElementById('blinkEyeState');

      if (blinkCount === 1) {
        playTerminalChime('blink');
        updateBlinkHUD(1, '1st Blink Detected! Blink once more...');
        if (eyeState) {
          eyeState.textContent = 'Blink!';
          eyeState.className = 'blink-eye-state eye-blink';
          setTimeout(() => {
            if (!isEyesClosed && eyeState) {
              eyeState.textContent = 'Eye Open';
              eyeState.className = 'blink-eye-state eye-open';
            }
          }, 300);
        }
        if (blinkResetTimer) clearTimeout(blinkResetTimer);
        blinkResetTimer = setTimeout(() => {
          if (blinkCount === 1 && !isProcessingPunch) {
            resetBlinkState('Window expired. Blink 2 times to punch');
          }
        }, 4500);
      } else if (blinkCount >= 2) {
        if (blinkResetTimer) clearTimeout(blinkResetTimer);
        playTerminalChime('success');
        updateBlinkHUD(2, '✨ 2 Blinks Verified! Recording...');
        if (eyeState) {
          eyeState.textContent = 'Verified!';
          eyeState.className = 'blink-eye-state eye-blink';
        }
        reticlePulse();
        executeAttendancePunch('blink');
      }
    }

    function onFaceMeshResults(results) {
      if (!isTerminalCameraRunning || isProcessingPunch) return;
      const now = Date.now();
      if (now < cooldownUntil) {
        const remainSec = Math.ceil((cooldownUntil - now) / 1000);
        updateBlinkHUD(0, `✔ Punch Recorded! Cooldown: ${remainSec}s`, true);
        return;
      }

      const punchContainer = document.getElementById('punchDetailContainer');
      if (punchContainer && punchContainer.style.display === 'block') {
        return;
      }

      const eyeState = document.getElementById('blinkEyeState');
      if (!results.multiFaceLandmarks || results.multiFaceLandmarks.length === 0) {
        if (eyeState) {
          eyeState.textContent = 'Detecting...';
          eyeState.className = 'blink-eye-state';
        }
        if (blinkCount > 0 && (now - lastBlinkTime > 4500)) {
          resetBlinkState();
        }
        return;
      }

      const landmarks = results.multiFaceLandmarks[0];
      const leftEAR = calculateEAR(landmarks, LEFT_EYE);
      const rightEAR = calculateEAR(landmarks, RIGHT_EYE);
      if (leftEAR === null || rightEAR === null) return;

      const avgEAR = (leftEAR + rightEAR) / 2.0;
      if (avgEAR > 0.22 && !isEyesClosed) {
        baselineEAR = Math.max(0.24, Math.min(0.38, baselineEAR * 0.95 + avgEAR * 0.05));
      }

      const isHigh = (sensitivityMode === 'high');
      const dropRatio = isHigh ? 0.84 : 0.78;
      const closeFloor = isHigh ? 0.26 : 0.24;
      const closeThreshold = Math.min(closeFloor, Math.max(0.16, baselineEAR * dropRatio));
      const openThreshold = Math.max(0.22, baselineEAR * (isHigh ? 0.86 : 0.82));

      if (blinkCount > 0 && (now - lastBlinkTime > 4500)) {
        resetBlinkState('Window timed out. Blink 2 times to punch');
        return;
      }

      const eyeIsLow = (avgEAR < closeThreshold) ||
                       (leftEAR < closeThreshold && rightEAR < closeThreshold + 0.05) ||
                       (rightEAR < closeThreshold && leftEAR < closeThreshold + 0.05);

      if (eyeIsLow) {
        closedFrameCount++;
        if (closedFrameCount >= 1 && closedFrameCount <= 24) {
          isEyesClosed = true;
          if (eyeState) {
            eyeState.textContent = 'Blink!';
            eyeState.className = 'blink-eye-state eye-blink';
          }
        }
      } else if (avgEAR >= openThreshold) {
        if (eyeState) {
          eyeState.textContent = 'Eye Open';
          eyeState.className = 'blink-eye-state eye-open';
        }
        if (isEyesClosed && closedFrameCount >= 1 && closedFrameCount <= 24) {
          isEyesClosed = false;
          closedFrameCount = 0;
          if (isHandsFreeActive) {
            handleBlinkDetected();
          }
        } else {
          isEyesClosed = false;
          closedFrameCount = 0;
        }
      }
    }

    function initFaceMesh() {
      if (typeof FaceMesh === 'undefined') {
        return;
      }
      if (faceMesh) return;
      try {
        faceMesh = new FaceMesh({
          locateFile: (file) => '/static/vendor/mediapipe/' + file + '?v=20261111_v1'
        });
        faceMesh.setOptions({
          maxNumFaces: 1,
          refineLandmarks: false,
          minDetectionConfidence: 0.5,
          minTrackingConfidence: 0.5
        });
        faceMesh.onResults(onFaceMeshResults);
        faceMeshReady = true;
      } catch (err) {
        console.warn('FaceMesh initialization notice:', err);
        faceMeshReady = false;
      }
    }

    let lastFwDetectionTs = 0;
    async function runDetectionLoop() {
      if (!isTerminalCameraRunning) {
        isDetectionRunning = false;
        return;
      }
      const now = Date.now();
      const video = document.getElementById('cameraFeed');
      if (now - lastFwDetectionTs >= 100 && faceMeshReady && video && video.readyState >= 2 && !isProcessingPunch && !isProcessingFrame) {
        lastFwDetectionTs = now;
        isProcessingFrame = true;
        try {
          await faceMesh.send({ image: video });
        } catch (e) {
        } finally {
          isProcessingFrame = false;
        }
      }
      if (isTerminalCameraRunning) {
        animFrameId = requestAnimationFrame(runDetectionLoop);
      } else {
        isDetectionRunning = false;
      }
    }

    async function startTerminalCamera() {
      const btnToggle = document.getElementById('btnToggleCamera');
      const btnToggleText = document.getElementById('btnToggleCameraText');
      const video = document.getElementById('cameraFeed');
      const cameraOverlay = document.getElementById('cameraOverlay');
      const faceReticle = document.getElementById('faceReticle');
      const blinkHud = document.getElementById('blinkHudOverlay');

      if (btnToggleText) btnToggleText.textContent = 'Starting...';

      try {
        terminalStream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } }
        });
        if (video) {
          video.srcObject = terminalStream;
          video.style.display = 'block';
        }
        if (cameraOverlay) cameraOverlay.style.display = 'none';
        if (faceReticle) faceReticle.style.display = 'block';

        isTerminalCameraRunning = true;
        if (btnToggleText) btnToggleText.textContent = 'Turn Off Camera';
        if (btnToggle) btnToggle.classList.add('active');

        if (blinkHud) blinkHud.style.display = 'flex';
        updateBlinkHUD(0, isHandsFreeActive ? '👁️ Blink 2 times to punch hands-free' : '🟢 Camera Active — Ready to Mark');
        resetBlinkState();
        initFaceMesh();
        if (!isDetectionRunning) {
          isDetectionRunning = true;
          requestAnimationFrame(runDetectionLoop);
        }
      } catch (err) {
        console.warn('Camera permission denied or camera unavailable:', err);
        if (cameraOverlay) {
          cameraOverlay.innerHTML = `
            <svg class="camera-off-icon" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
              <line x1="1" y1="1" x2="23" y2="23"></line>
              <path d="M21 21H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h3m3-3h6l2 3h4a2 2 0 0 1 2 2v9.34m-7.72-2.06a4 4 0 1 1-5.56-5.56"></path>
            </svg>
            <div class="camera-off-title" style="color: #fca5a5;">Camera Access Denied</div>
            <div class="camera-off-subtitle">Please allow camera permissions in browser settings.</div>
          `;
          cameraOverlay.style.display = 'flex';
        }
        if (video) video.style.display = 'none';
        if (faceReticle) faceReticle.style.display = 'none';
        if (blinkHud) blinkHud.style.display = 'none';
        if (btnToggleText) btnToggleText.textContent = 'Turn On Camera';
        if (btnToggle) btnToggle.classList.remove('active');
        isTerminalCameraRunning = false;
      }
    }

    function stopTerminalCamera() {
      if (terminalStream) {
        terminalStream.getTracks().forEach(t => t.stop());
        terminalStream = null;
      }
      const video = document.getElementById('cameraFeed');
      const cameraOverlay = document.getElementById('cameraOverlay');
      const faceReticle = document.getElementById('faceReticle');
      const blinkHud = document.getElementById('blinkHudOverlay');
      const btnToggle = document.getElementById('btnToggleCamera');
      const btnToggleText = document.getElementById('btnToggleCameraText');

      if (video) {
        video.srcObject = null;
        video.style.display = 'none';
      }
      if (faceReticle) faceReticle.style.display = 'none';
      if (blinkHud) blinkHud.style.display = 'none';
      isDetectionRunning = false;
      if (animFrameId) {
        cancelAnimationFrame(animFrameId);
        animFrameId = null;
      }
      resetBlinkState();

      if (cameraOverlay) {
        cameraOverlay.innerHTML = `
          <svg class="camera-off-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path>
            <circle cx="12" cy="13" r="4"></circle>
          </svg>
          <div class="camera-off-title">Camera is turned off</div>
          <div class="camera-off-subtitle">Click &ldquo;Turn On Camera&rdquo; to enable.</div>
        `;
        cameraOverlay.style.display = 'flex';
      }

      isTerminalCameraRunning = false;
      if (btnToggleText) btnToggleText.textContent = 'Turn On Camera';
      if (btnToggle) btnToggle.classList.remove('active');
    }

    async function executeAttendancePunch(source = 'button') {
      if (isProcessingPunch) return;

      const video = document.getElementById('cameraFeed');
      const canvas = document.getElementById('captureCanvas');
      const btnMark = document.getElementById('btnMarkAttendance');
      const btnMarkText = document.getElementById('btnMarkAttendanceText');
      const punchContainer = document.getElementById('punchDetailContainer');

      if (!isTerminalCameraRunning || !terminalStream) {
        await startTerminalCamera();
        if (!isTerminalCameraRunning) return;
        await new Promise(r => setTimeout(r, 600));
      }

      isProcessingPunch = true;
      if (btnMark) btnMark.disabled = true;
      if (btnMarkText) btnMarkText.textContent = 'Verifying Face...';
      if (punchContainer) punchContainer.style.display = 'none';

      if (source === 'blink') {
        updateBlinkHUD(2, '✨ Verifying Face...');
      }

      try {
        const coords = await getDeviceCurrentPosition();
        const lat = coords.lat;
        const lng = coords.lng;

        canvas.width = (video && video.videoWidth) || 640;
        canvas.height = (video && video.videoHeight) || 480;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const blob1 = await new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.90));

        await new Promise(r => setTimeout(r, 200));
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        const blob2 = await new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.90));

        if (!blob1) throw new Error('Unable to capture camera frame');

        const now = new Date();
        const day = String(now.getDate()).padStart(2, '0');
        const month = String(now.getMonth() + 1).padStart(2, '0');
        const year = now.getFullYear();
        let rawHours = now.getHours();
        const ampm = rawHours >= 12 ? 'PM' : 'AM';
        let hours = rawHours % 12;
        hours = hours ? hours : 12;
        const hoursStr = String(hours).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        const clientTimestamp = `${day}/${month}/${year} ${hoursStr}:${minutes}:${seconds} ${ampm}`;

        const formData = new FormData();
        formData.append('photo', blob1, 'punch_frame.jpg');
        if (blob2) formData.append('burst_photo', blob2, 'burst_frame.jpg');
        if (lat != null && lng != null) {
          formData.append('latitude', lat);
          formData.append('longitude', lng);
        }
        formData.append('client_time', clientTimestamp);
        const cid = getActiveCompanyId();
        if (cid) formData.append('company_id', cid);

        const res = await fetch('/api/face/recognize', { method: 'POST', body: formData });
        const data = await res.json();

        if (data.matched) {
          playTerminalChime('success');
          cooldownUntil = Date.now() + 8000;
          updateBlinkHUD(0, '✔ Punch Recorded! Cooldown: 8s', true);

          const isPunchOut = data.punch_status === 'punch_out';
          const isAlreadyPunched = Boolean(data.punch_status === 'already_punched_in' || data.already_punched_in);
          const statusLabel = isAlreadyPunched ? 'Punch In Active (On Duty)' : (isPunchOut ? 'Punch Out Recorded' : 'Punch In Recorded');
          const statusIcon = isAlreadyPunched ? 'ℹ' : (isPunchOut ? '⏏' : '✔');
          const badgeStyle = isAlreadyPunched ? 'background: #2563eb; color: #ffffff;' : '';
          const empName = data.employee_name || LOGGED_IN_EMPLOYEE_NAME || 'Field Worker';
          const empCode = data.employee_code || data.employee_id || 'FW-VERIFIED';
          const dept = data.department || 'Field Sales';
          const desig = data.designation || 'Field Executive';
          const punchTime = data.punch_time || `${hoursStr}:${minutes}:${seconds} ${ampm}`;
          const conf = data.confidence ? `${data.confidence}% Match` : '98.5% Match';
          const distInfo = data.formatted_distance ? `${data.formatted_distance}` : `GPS (${lat.toFixed(4)}, ${lng.toFixed(4)})`;

          if (punchContainer) {
            punchContainer.innerHTML = `
              <div class="punch-card-verified" style="${isAlreadyPunched ? 'border-left: 5px solid #2563eb; background: #f8fafc;' : ''}">
                <div class="punch-header">
                  <span class="punch-badge-success" style="${badgeStyle}">${statusIcon} ${statusLabel}</span>
                  <span class="punch-time-tag">${punchTime}</span>
                </div>
                <div class="punch-body">
                  <div class="punch-emp-name">
                    ${escapeHtml(empName)}
                    <span style="background: #ccfbf1; color: #0f766e; border: 1px solid #99f6e4; font-size: 10px; font-weight: 800; padding: 2px 7px; border-radius: 999px; margin-left: 6px; display: inline-flex; align-items: center; gap: 4px; vertical-align: middle;">FIELD WORKER</span>
                  </div>
                  <div class="punch-grid">
                    <div class="punch-grid-item">
                      <span class="punch-grid-label">ID:</span>
                      <span class="punch-grid-value">${escapeHtml(empCode)}</span>
                    </div>
                    <div class="punch-grid-item">
                      <span class="punch-grid-label">Role:</span>
                      <span class="punch-grid-value">${escapeHtml(desig)}</span>
                    </div>
                    <div class="punch-grid-item">
                      <span class="punch-grid-label">Dept:</span>
                      <span class="punch-grid-value">${escapeHtml(dept)}</span>
                    </div>
                    <div class="punch-grid-item">
                      <span class="punch-grid-label">Biometric:</span>
                      <span class="punch-conf-pill">${conf}</span>
                    </div>
                    ${data.working_hours ? `
                      <div class="punch-grid-item">
                        <span class="punch-grid-label">Working Hours:</span>
                        <span class="punch-grid-value" style="color: #16a34a;">${escapeHtml(data.working_hours)}</span>
                      </div>
                    ` : ''}
                  </div>
                  <div class="punch-geo-badge">
                    <i class="fa-solid fa-location-dot"></i>
                    <span>${escapeHtml(distInfo)}</span>
                  </div>
                </div>
              </div>
            `;
            punchContainer.style.display = 'block';
            punchContainer.style.opacity = '1';
          }

          // Send telemetry ping to update fleet monitor
          await sendLocationPingPayload({
            employee_name: empName,
            latitude: lat,
            longitude: lng,
            accuracy: coords.accuracy || 10,
            activity_note: `AI Face Attendance Punch (${data.punch_status || 'Verified'})`
          });
          await refreshOverviewState();

        } else {
          const errMsg = data.message || data.error || 'Face not recognized in database.';
          const isSpoof = Boolean(data.spoof_detected);
          const badgeText = isSpoof ? '🛑 Anti-Spoofing Alert' : 'Biometric Verification';
          const subText = isSpoof
            ? 'Attendance requires a live human presence. Smartphone screen or printed photo is blocked.'
            : 'Please face the camera directly in good lighting and try again.';

          if (punchContainer) {
            punchContainer.innerHTML = `
              <div class="punch-card-failed" style="${isSpoof ? 'border-left: 5px solid #ef4444; background: #fff1f2;' : ''}">
                <div class="punch-header">
                  <span class="punch-badge-failed" style="${isSpoof ? 'background: #ef4444; color: #fff;' : ''}">⚠ ${escapeHtml(badgeText)}</span>
                  <span class="punch-time-tag">${hoursStr}:${minutes}:${seconds} ${ampm}</span>
                </div>
                <div class="punch-body">
                  <div style="font-size: 13.5px; font-weight: 700; color: #991b1b;">${escapeHtml(errMsg)}</div>
                  <div style="font-size: 12px; color: ${isSpoof ? '#7f1d1d' : '#64748b'}; margin-top: 3px;">${escapeHtml(subText)}</div>
                </div>
              </div>
            `;
            punchContainer.style.display = 'block';
            punchContainer.style.opacity = '1';
          }
        }

      } catch (err) {
        console.error('Mark Attendance error:', err);
        if (punchContainer) {
          punchContainer.innerHTML = `
            <div class="punch-card-failed">
              <div class="punch-header">
                <span class="punch-badge-failed">⚠ Attendance Notice</span>
              </div>
              <div style="font-size: 13px; color: #991b1b; padding-top: 4px;">
                ${escapeHtml(err.message || 'Unable to contact attendance server.')}
              </div>
            </div>
          `;
          punchContainer.style.display = 'block';
          punchContainer.style.opacity = '1';
        }
      } finally {
        isProcessingPunch = false;
        if (btnMark) btnMark.disabled = false;
        if (btnMarkText) btnMarkText.textContent = 'Mark Attendance';

        // Auto-dismiss dynamic punch card after 10 seconds
        setTimeout(() => {
          if (punchContainer && punchContainer.style.display === 'block') {
            punchContainer.style.opacity = '0';
            punchContainer.style.transition = 'opacity 0.5s ease';
            setTimeout(() => {
              punchContainer.style.display = 'none';
            }, 500);
          }
        }, 10000);
      }
    }

    // Backwards compatibility wrappers
    function startFieldPunchCamera() { return startTerminalCamera(); }
    function stopFieldPunchCamera() { return stopTerminalCamera(); }
    function performFieldFacePunch() { return executeAttendancePunch('button'); }

    // Bind terminal listeners when DOM is ready
    function initTerminalListeners() {
      const btnToggle = document.getElementById('btnToggleCamera');
      if (btnToggle) {
        btnToggle.addEventListener('click', function () {
          if (isTerminalCameraRunning) {
            stopTerminalCamera();
          } else {
            startTerminalCamera();
          }
        });
      }

      const btnMark = document.getElementById('btnMarkAttendance');
      if (btnMark) {
        btnMark.addEventListener('click', function () {
          executeAttendancePunch('button');
        });
      }

      const btnHandsFree = document.getElementById('btnToggleHandsFree');
      const handsfreeLabel = document.getElementById('handsfreeToggleLabel');
      const blinkHud = document.getElementById('blinkHudOverlay');
      if (btnHandsFree) {
        btnHandsFree.addEventListener('click', function () {
          isHandsFreeActive = !isHandsFreeActive;
          if (isHandsFreeActive) {
            btnHandsFree.classList.add('active');
            if (handsfreeLabel) handsfreeLabel.textContent = 'Hands-Free: Active (Blink 2x)';
            if (blinkHud && isTerminalCameraRunning) blinkHud.style.display = 'flex';
            updateBlinkHUD(0, '👁️ Blink 2 times to punch hands-free');
          } else {
            btnHandsFree.classList.remove('active');
            if (handsfreeLabel) handsfreeLabel.textContent = 'Hands-Free: Inactive (Manual Mode)';
            if (blinkHud) blinkHud.style.display = 'none';
          }
        });
      }

      const btnSens = document.getElementById('btnToggleSensitivity');
      const sensLabel = document.getElementById('sensitivityLabel');
      if (btnSens) {
        btnSens.addEventListener('click', function () {
          if (sensitivityMode === 'normal') {
            sensitivityMode = 'high';
            if (sensLabel) {
              sensLabel.textContent = 'High (Spectacles)';
              sensLabel.style.color = '#10b981';
            }
          } else {
            sensitivityMode = 'normal';
            if (sensLabel) {
              sensLabel.textContent = 'Normal';
              sensLabel.style.color = '#0284c7';
            }
          }
        });
      }
    }

    async function submitQuickFieldCheckIn() {
      const workerEl = document.getElementById('quickPunchWorker');
      const emp = workerEl ? (workerEl.value || LOGGED_IN_EMPLOYEE_NAME) : LOGGED_IN_EMPLOYEE_NAME;
      const noteEl = document.getElementById('quickPunchNote');
      const note = noteEl ? noteEl.value : 'Field Duty Check-In - Verified at Client Site';

      if (!emp) {
        showToast('Field worker name not identified.', true);
        return;
      }

      showToast('Acquiring device GPS coordinates...');
      const coords = await getDeviceCurrentPosition();
      await sendLocationPingPayload({
        employee_name: emp,
        latitude: coords.lat,
        longitude: coords.lng,
        accuracy: coords.accuracy || 10,
        activity_note: note || 'Quick Field Duty Check-In'
      });
      showToast('GPS Field Check-In recorded successfully!');
    }

    function prefillVisitFromAssignment(sel) {
      const opt = sel.options[sel.selectedIndex];
      if (!opt.value) return;
      document.getElementById('visitCustomerName').value = opt.dataset.target || '';
      document.getElementById('visitContactPerson').value = opt.dataset.person || '';
      document.getElementById('visitCustomerPhone').value = opt.dataset.phone || '';
      if (opt.dataset.lat) document.getElementById('visitLat').value = opt.dataset.lat;
      if (opt.dataset.lng) document.getElementById('visitLng').value = opt.dataset.lng;
    }

    // Dynamic Customer Visit Submission (AJAX, Zero Reload)
    async function submitCustomerVisit(e) {
      e.preventDefault();
      if (WEB_IS_RECORDING) {
        stopWebAudioRecording();
      }

      const formData = new FormData();
      formData.append('company_id', getActiveCompanyId());
      formData.append('visit_date', document.getElementById('globalDateInput').value);
      formData.append('employee_name', (CURRENT_USER_ROLE === 'employee' && LOGGED_IN_EMPLOYEE_NAME) ? LOGGED_IN_EMPLOYEE_NAME : ((document.getElementById('visitWorkerName') ? document.getElementById('visitWorkerName').value : '') || LOGGED_IN_EMPLOYEE_NAME));
      formData.append('assignment_id', document.getElementById('visitAssignmentId').value || '');
      formData.append('customer_name', document.getElementById('visitCustomerName').value || '');
      formData.append('contact_person', document.getElementById('visitContactPerson').value || '');
      formData.append('customer_phone', document.getElementById('visitCustomerPhone').value || '');
      formData.append('product_pitched', document.getElementById('visitProduct').value || '');
      formData.append('lead_status', document.getElementById('visitLeadStatus').value || 'Interested');
      formData.append('order_amount', parseFloat(document.getElementById('visitOrderAmount').value) || 0);
      formData.append('follow_up_date', document.getElementById('visitFollowUpDate').value || '');
      formData.append('latitude', (document.getElementById('visitLat') ? parseFloat(document.getElementById('visitLat').value) : null) || INITIAL_COMPANY_LAT);
      formData.append('longitude', (document.getElementById('visitLng') ? parseFloat(document.getElementById('visitLng').value) : null) || INITIAL_COMPANY_LNG);
      formData.append('remarks', document.getElementById('visitRemarks').value || '');

      if (WEB_RECORDED_AUDIO_BLOB) {
        const mime = WEB_RECORDED_AUDIO_BLOB.type || 'audio/webm';
        const ext = mime.includes('mp4') ? 'm4a' : 'webm';
        formData.append('audio_file', WEB_RECORDED_AUDIO_BLOB, `visit_web_audio_${Date.now()}.${ext}`);
        formData.append('audio_duration_seconds', WEB_RECORDED_AUDIO_SECONDS || 0);
        formData.append('audio_mime_type', mime);
        showToast('Uploading visit & running Tamil Gemini AI speech-to-text...');
      }

      try {
        const res = await fetch('/api/field-worker/visits', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (!data.success) {
          showToast(data.error || 'Could not log customer visit', true);
          return;
        }
        showToast(data.message);
        discardWebAudioRecording();
        closeAddLeadModal();
        const visitForm = document.getElementById('customerVisitForm');
        if (visitForm) visitForm.reset();
        document.getElementById('visitOrderAmount').value = '0';
        await refreshOverviewState();
      } catch (err) {
        showToast('Visit submission network error: ' + err.message, true);
      }
    }

    // =========================================================================
    // PRODUCT WAREHOUSE (GOOGLE SHEETS) & WEB IN-BROWSER AUDIO RECORDER ENGINE
    // =========================================================================

    let CURRENT_WAREHOUSE_PRODUCTS = [];
    let CURRENT_WAREHOUSE_SHEET_URL = '';

    async function loadWarehouseProducts(forceSync = false) {
      try {
        const cid = getActiveCompanyId();
        const res = await fetch(`/api/field-worker/products?company_id=${encodeURIComponent(cid)}&_t=${Date.now()}${forceSync ? '&sync=1' : ''}`);
        const data = await res.json();
        if (data.success && Array.isArray(data.products)) {
          CURRENT_WAREHOUSE_PRODUCTS = data.products;
          CURRENT_WAREHOUSE_SHEET_URL = data.sheet_url || '';
          
          const datalist = document.getElementById('warehouseProductList');
          if (datalist) {
            datalist.innerHTML = '';
          }

          const sheetInp = document.getElementById('warehouseSheetUrlInput');
          if (sheetInp && data.sheet_url) sheetInp.value = data.sheet_url;
          
          const statusEl = document.getElementById('warehouseSyncStatusText');
          if (statusEl) statusEl.textContent = `${data.products.length} Products Active (${data.sync_status || 'Ready'})`;
          
          const lastEl = document.getElementById('warehouseLastSyncedText');
          if (lastEl) lastEl.textContent = `Last synced: ${data.last_synced_at || 'Recently'}`;

          const openTabBtn = document.getElementById('btnOpenSheetInTab');
          if (openTabBtn) {
            openTabBtn.href = data.sheet_url || '#';
            if (!data.sheet_url) openTabBtn.onclick = (e) => { e.preventDefault(); showToast('Please enter a Google Sheet URL first.'); };
            else openTabBtn.onclick = null;
          }

          // Automatically refresh hint badge in active modals if product is selected
          const editInp = document.getElementById('editProductPitched');
          if (editInp && editInp.value) handleEditProductSelected(editInp.value);
          const addInp = document.getElementById('visitProductPitched');
          if (addInp && addInp.value) handleProductSelected(addInp.value);
        }
      } catch (err) {
        console.warn('Could not load warehouse products:', err);
      }
    }

    function openProductWarehouse() {
      if (CURRENT_WAREHOUSE_SHEET_URL && CURRENT_WAREHOUSE_SHEET_URL.trim().startsWith('http')) {
        window.open(CURRENT_WAREHOUSE_SHEET_URL.trim(), '_blank');
      } else {
        openWarehouseSettingsModal();
      }
    }

    function openWarehouseSettingsModal() {
      const modal = document.getElementById('warehouseSettingsModalBackdrop');
      if (modal) {
        modal.classList.remove('d-none');
        loadWarehouseProducts();
      }
    }

    function closeWarehouseSettingsModal() {
      const modal = document.getElementById('warehouseSettingsModalBackdrop');
      if (modal) modal.classList.add('d-none');
    }

    async function saveWarehouseSheetUrl() {
      const urlInput = document.getElementById('warehouseSheetUrlInput');
      const sheetUrl = (urlInput ? urlInput.value : '').trim();
      if (!sheetUrl) {
        showToast('Please enter a valid Google Sheets URL.', true);
        return;
      }
      try {
        showToast('Saving Google Sheet URL & fetching products...');
        const res = await fetch('/api/field-worker/products/sheet-url', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sheet_url: sheetUrl, company_id: getActiveCompanyId() })
        });
        const data = await res.json();
        if (data.success) {
          showToast('Product Warehouse linked & synced successfully!');
          closeWarehouseSettingsModal();
          await loadWarehouseProducts();
        } else {
          showToast(data.error || 'Failed to sync Google Sheet.', true);
        }
      } catch (err) {
        showToast('Error connecting to Google Sheets: ' + err.message, true);
      }
    }

    async function syncWarehouseProducts() {
      const btn = document.getElementById('btnSyncWarehouse');
      if (btn) btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
      try {
        const res = await fetch('/api/field-worker/products/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ company_id: getActiveCompanyId() })
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || `Synced ${data.product_count} products from Google Sheets!`);
          await loadWarehouseProducts();
        } else {
          showToast(data.error || 'Sync warning: Using current catalog.', true);
        }
      } catch (err) {
        showToast('Sync error: ' + err.message, true);
      } finally {
        if (btn) btn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i>';
      }
    }

    function handleProductSelected(val) {
      const hint = document.getElementById('productPriceHint');
      if (!val) {
        if (hint) hint.style.display = 'none';
        return;
      }
      const cleanVal = val.trim().toLowerCase();
      const matched = CURRENT_WAREHOUSE_PRODUCTS.find(p => (p.name || '').trim().toLowerCase() === cleanVal);
      const orderInp = document.getElementById('visitOrderAmount');
      if (matched) {
        if (matched.price > 0 && orderInp && (!orderInp.value || parseFloat(orderInp.value) === 0)) {
          orderInp.value = matched.price.toFixed(2);
        }
        if (hint) {
          const rawQty = (matched.qty !== undefined && matched.qty !== null && String(matched.qty).trim() !== '') 
            ? matched.qty 
            : ((matched.quantity !== undefined && matched.quantity !== null && String(matched.quantity).trim() !== '') ? matched.quantity : null);
          const qtyText = rawQty !== null 
            ? `<span style="margin-left:8px; background:#dbeafe; color:#1e40af; font-size:11px; font-weight:700; padding:2px 8px; border-radius:12px; border:1px solid #bfdbfe; white-space:nowrap;"><i class="fa-solid fa-boxes-stacked"></i> Available Qty: ${rawQty}</span>`
            : '';
          const priceText = matched.price > 0 
            ? `<span style="color:#059669; font-weight:600;"><i class="fa-solid fa-circle-check"></i> Price: ₹${Number(matched.price).toLocaleString('en-IN')}</span>`
            : '';
          hint.innerHTML = priceText + qtyText;
          hint.style.display = (priceText || qtyText) ? 'block' : 'none';
        }
      } else {
        if (hint) hint.style.display = 'none';
      }
    }

    function handleEditProductSelected(val) {
      const hint = document.getElementById('editProductPriceHint');
      if (!val) {
        if (hint) hint.style.display = 'none';
        return;
      }
      const cleanVal = val.trim().toLowerCase();
      const matched = CURRENT_WAREHOUSE_PRODUCTS.find(p => (p.name || '').trim().toLowerCase() === cleanVal);
      const orderInp = document.getElementById('editOrderAmount');
      if (matched) {
        if (matched.price > 0 && orderInp && (!orderInp.value || parseFloat(orderInp.value) === 0)) {
          orderInp.value = matched.price.toFixed(2);
        }
        if (hint) {
          const rawQty = (matched.qty !== undefined && matched.qty !== null && String(matched.qty).trim() !== '') 
            ? matched.qty 
            : ((matched.quantity !== undefined && matched.quantity !== null && String(matched.quantity).trim() !== '') ? matched.quantity : null);
          const qtyText = rawQty !== null 
            ? `<span style="margin-left:8px; background:#dbeafe; color:#1e40af; font-size:11px; font-weight:700; padding:2px 8px; border-radius:12px; border:1px solid #bfdbfe; white-space:nowrap;"><i class="fa-solid fa-boxes-stacked"></i> Available Qty: ${rawQty}</span>`
            : '';
          const priceText = matched.price > 0 
            ? `<span style="color:#059669; font-weight:600;"><i class="fa-solid fa-circle-check"></i> Price: ₹${Number(matched.price).toLocaleString('en-IN')}</span>`
            : '';
          hint.innerHTML = priceText + qtyText;
          hint.style.display = (priceText || qtyText) ? 'block' : 'none';
        }
      } else {
        if (hint) hint.style.display = 'none';
      }
    }

    function closeProductDropdown() {
      const existing = document.getElementById('floatingProductDropdownList');
      if (existing) existing.remove();
    }

    function toggleProductDropdown(targetInputId) {
      const existing = document.getElementById('floatingProductDropdownList');
      if (existing && existing.dataset.targetInput === targetInputId) {
        existing.remove();
        return;
      }
      const input = document.getElementById(targetInputId);
      renderProductDropdown(targetInputId, input ? input.value : '');
    }

    function filterProductDropdown(targetInputId, query) {
      renderProductDropdown(targetInputId, query);
    }

    function renderProductDropdown(targetInputId, query = '') {
      const input = document.getElementById(targetInputId);
      if (!input) return;

      if (!CURRENT_WAREHOUSE_PRODUCTS || CURRENT_WAREHOUSE_PRODUCTS.length === 0) {
        loadWarehouseProducts().then(() => {
          if (CURRENT_WAREHOUSE_PRODUCTS && CURRENT_WAREHOUSE_PRODUCTS.length > 0) {
            renderProductDropdown(targetInputId, query);
          } else {
            showToast('No warehouse products found. Sync your Google Sheet first.');
          }
        });
        return;
      }

      const q = (query || '').trim().toLowerCase();
      const items = q 
        ? CURRENT_WAREHOUSE_PRODUCTS.filter(p => 
            (p.name || '').toLowerCase().includes(q) || 
            (p.category || '').toLowerCase().includes(q)
          )
        : CURRENT_WAREHOUSE_PRODUCTS;

      let dropdown = document.getElementById('floatingProductDropdownList');
      if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.id = 'floatingProductDropdownList';
        document.body.appendChild(dropdown);
      }
      dropdown.dataset.targetInput = targetInputId;

      const rect = input.getBoundingClientRect();
      dropdown.style.cssText = `
        position: fixed;
        left: ${rect.left}px;
        top: ${rect.bottom + 4}px;
        width: ${Math.max(rect.width, 340)}px;
        max-height: 240px;
        overflow-y: auto;
        background: #ffffff;
        border: 1px solid #cbd5e1;
        border-radius: 8px;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.15), 0 8px 10px -6px rgba(0,0,0,0.08);
        z-index: 9999;
        font-family: inherit;
      `;

      dropdown.innerHTML = `
        <div style="padding: 6px 10px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; font-size: 11px; font-weight: 700; color: #64748b; display: flex; justify-content: space-between; align-items: center;">
          <span>WAREHOUSE CATALOG (${items.length}${items.length !== CURRENT_WAREHOUSE_PRODUCTS.length ? ' of ' + CURRENT_WAREHOUSE_PRODUCTS.length : ''})</span>
          <span style="cursor: pointer; font-size: 14px; color: #94a3b8;" onclick="closeProductDropdown()">&times;</span>
        </div>
        ${items.length === 0 ? `
          <div style="padding: 12px; font-size: 12px; color: #94a3b8; text-align: center;">No matching products found</div>
        ` : items.map(p => {
          const rawQty = (p.qty !== undefined && p.qty !== null && String(p.qty).trim() !== '') 
            ? p.qty 
            : ((p.quantity !== undefined && p.quantity !== null && String(p.quantity).trim() !== '') ? p.quantity : null);
          return `
          <div class="product-dropdown-item" 
               onclick="selectDropdownProduct('${targetInputId}', '${(p.name || '').replace(/'/g, "\\'")}', ${p.price || 0})" 
               onmouseenter="this.style.background='#f1f5f9'" 
               onmouseleave="this.style.background='transparent'" 
               style="padding: 8px 12px; cursor: pointer; border-bottom: 1px solid #f1f5f9; display: flex; justify-content: space-between; align-items: center; transition: background 0.15s;">
            <div style="padding-right: 8px;">
              <div style="font-size: 12.5px; font-weight: 700; color: #0f172a;">${p.name}</div>
              <div style="font-size: 10.5px; color: #64748b;">${p.category || 'General'}</div>
            </div>
            <div style="display:flex; align-items:center; gap:8px; flex-shrink: 0;">
              ${rawQty !== null ? `
                <span style="font-size: 11px; font-weight: 700; color: #1e40af; background: #dbeafe; padding: 2px 8px; border-radius: 12px; border: 1px solid #bfdbfe; white-space: nowrap;">
                  <i class="fa-solid fa-boxes-stacked" style="font-size:10px; margin-right:3px;"></i> Qty: ${rawQty}
                </span>
              ` : ''}
              <div style="font-size: 12px; font-weight: 800; color: #15803d; background: #ecfdf5; padding: 2px 8px; border-radius: 4px; white-space: nowrap;">
                ₹${Number(p.price || 0).toLocaleString('en-IN')}
              </div>
            </div>
          </div>
        `; }).join('')}
      `;

      // Auto close when clicking outside
      const outsideClickHandler = (e) => {
        const dd = document.getElementById('floatingProductDropdownList');
        if (dd && !dd.contains(e.target) && e.target !== input && !e.target.closest('button')) {
          dd.remove();
          document.removeEventListener('click', outsideClickHandler);
        }
      };
      setTimeout(() => document.addEventListener('click', outsideClickHandler), 10);
    }

    function selectDropdownProduct(targetInputId, name, price) {
      const input = document.getElementById(targetInputId);
      if (input) {
        input.value = name;
        if (targetInputId === 'editProductPitched') {
          handleEditProductSelected(name);
        } else {
          handleProductSelected(name);
        }
      }
      closeProductDropdown();
    }

    // -------------------------------------------------------------------------
    // WEB IN-BROWSER AUDIO RECORDER (MediaRecorder API for Tamil Gemini STT)
    // -------------------------------------------------------------------------

    let WEB_MEDIA_RECORDER = null;
    let WEB_AUDIO_STREAM = null;
    let WEB_RECORDED_AUDIO_CHUNKS = [];
    let WEB_RECORDED_AUDIO_BLOB = null;
    let WEB_RECORDED_AUDIO_SECONDS = 0;
    let WEB_RECORD_TIMER_INTERVAL = null;
    let WEB_IS_RECORDING = false;
    let WEB_IS_PAUSED = false;

    async function toggleWebAudioRecording() {
      if (WEB_IS_RECORDING) {
        stopWebAudioRecording();
      } else {
        await startWebAudioRecording();
      }
    }

    async function startWebAudioRecording() {
      try {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
          showToast('Audio recording is not supported in this browser.', true);
          return;
        }

        WEB_AUDIO_STREAM = await navigator.mediaDevices.getUserMedia({ audio: true });
        
        let options = { mimeType: 'audio/webm;codecs=opus' };
        if (!MediaRecorder.isTypeSupported(options.mimeType)) {
          if (MediaRecorder.isTypeSupported('audio/mp4')) options = { mimeType: 'audio/mp4' };
          else if (MediaRecorder.isTypeSupported('audio/webm')) options = { mimeType: 'audio/webm' };
          else options = {};
        }

        WEB_MEDIA_RECORDER = new MediaRecorder(WEB_AUDIO_STREAM, options);
        WEB_RECORDED_AUDIO_CHUNKS = [];

        WEB_MEDIA_RECORDER.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            WEB_RECORDED_AUDIO_CHUNKS.push(e.data);
          }
        };

        WEB_MEDIA_RECORDER.onstop = () => {
          const mime = (WEB_MEDIA_RECORDER && WEB_MEDIA_RECORDER.mimeType) ? WEB_MEDIA_RECORDER.mimeType : 'audio/webm';
          WEB_RECORDED_AUDIO_BLOB = new Blob(WEB_RECORDED_AUDIO_CHUNKS, { type: mime });
          
          const preview = document.getElementById('webAudioPreview');
          const previewCont = document.getElementById('webAudioPreviewContainer');
          const durEl = document.getElementById('webAudioRecordedDuration');
          
          if (preview && WEB_RECORDED_AUDIO_BLOB) {
            preview.src = URL.createObjectURL(WEB_RECORDED_AUDIO_BLOB);
            if (previewCont) previewCont.classList.remove('d-none');
            if (durEl) durEl.textContent = `Duration: ${WEB_RECORDED_AUDIO_SECONDS}s`;
          }

          if (WEB_AUDIO_STREAM) {
            WEB_AUDIO_STREAM.getTracks().forEach(track => track.stop());
            WEB_AUDIO_STREAM = null;
          }
        };

        WEB_MEDIA_RECORDER.start(250);
        WEB_IS_RECORDING = true;
        WEB_IS_PAUSED = false;
        WEB_RECORDED_AUDIO_SECONDS = 0;

        const badge = document.getElementById('webRecordStatusBadge');
        if (badge) {
          badge.textContent = '● Recording Audio (Tamil AI)';
          badge.style.background = '#fee2e2';
          badge.style.color = '#dc2626';
        }

        const startBtn = document.getElementById('btnWebRecordStart');
        const startText = document.getElementById('btnWebRecordStartText');
        if (startBtn) {
          startBtn.style.background = '#dc2626';
          if (startText) startText.textContent = 'Stop Recording';
        }

        const pauseBtn = document.getElementById('btnWebRecordPause');
        if (pauseBtn) pauseBtn.classList.remove('d-none');

        const discardBtn = document.getElementById('btnWebRecordDiscard');
        if (discardBtn) discardBtn.classList.remove('d-none');

        const timerEl = document.getElementById('webRecordTimer');
        if (timerEl) {
          timerEl.textContent = '00:00';
          timerEl.style.display = 'inline-block';
        }

        clearInterval(WEB_RECORD_TIMER_INTERVAL);
        WEB_RECORD_TIMER_INTERVAL = setInterval(() => {
          if (!WEB_IS_PAUSED) {
            WEB_RECORDED_AUDIO_SECONDS++;
            const mins = String(Math.floor(WEB_RECORDED_AUDIO_SECONDS / 60)).padStart(2, '0');
            const secs = String(WEB_RECORDED_AUDIO_SECONDS % 60).padStart(2, '0');
            if (timerEl) timerEl.textContent = `${mins}:${secs}`;
          }
        }, 1000);

      } catch (err) {
        showToast('Microphone access denied or error: ' + err.message, true);
      }
    }

    function pauseResumeWebAudioRecording() {
      if (!WEB_MEDIA_RECORDER || !WEB_IS_RECORDING) return;
      const pauseText = document.getElementById('btnWebRecordPauseText');
      const badge = document.getElementById('webRecordStatusBadge');
      if (WEB_IS_PAUSED) {
        WEB_MEDIA_RECORDER.resume();
        WEB_IS_PAUSED = false;
        if (pauseText) pauseText.textContent = 'Pause';
        if (badge) {
          badge.textContent = '● Recording Audio (Tamil AI)';
          badge.style.background = '#fee2e2';
          badge.style.color = '#dc2626';
        }
      } else {
        WEB_MEDIA_RECORDER.pause();
        WEB_IS_PAUSED = true;
        if (pauseText) pauseText.textContent = 'Resume';
        if (badge) {
          badge.textContent = '❚❚ Recording Paused';
          badge.style.background = '#fef3c7';
          badge.style.color = '#b45309';
        }
      }
    }

    function stopWebAudioRecording() {
      if (WEB_MEDIA_RECORDER && WEB_IS_RECORDING) {
        WEB_MEDIA_RECORDER.stop();
      }
      WEB_IS_RECORDING = false;
      WEB_IS_PAUSED = false;
      clearInterval(WEB_RECORD_TIMER_INTERVAL);

      const badge = document.getElementById('webRecordStatusBadge');
      if (badge) {
        badge.textContent = `✓ ${WEB_RECORDED_AUDIO_SECONDS}s Recorded`;
        badge.style.background = '#ecfdf5';
        badge.style.color = '#059669';
      }

      const startBtn = document.getElementById('btnWebRecordStart');
      const startText = document.getElementById('btnWebRecordStartText');
      if (startBtn) {
        startBtn.style.background = '#2563eb';
        if (startText) startText.textContent = 'Re-record Audio';
      }

      const pauseBtn = document.getElementById('btnWebRecordPause');
      if (pauseBtn) pauseBtn.classList.add('d-none');
    }

    function discardWebAudioRecording() {
      if (WEB_MEDIA_RECORDER && WEB_IS_RECORDING) {
        WEB_MEDIA_RECORDER.stop();
      }
      if (WEB_AUDIO_STREAM) {
        WEB_AUDIO_STREAM.getTracks().forEach(track => track.stop());
        WEB_AUDIO_STREAM = null;
      }
      clearInterval(WEB_RECORD_TIMER_INTERVAL);
      WEB_IS_RECORDING = false;
      WEB_IS_PAUSED = false;
      WEB_RECORDED_AUDIO_CHUNKS = [];
      WEB_RECORDED_AUDIO_BLOB = null;
      WEB_RECORDED_AUDIO_SECONDS = 0;

      const badge = document.getElementById('webRecordStatusBadge');
      if (badge) {
        badge.textContent = 'Mic Ready';
        badge.style.background = '#e2e8f0';
        badge.style.color = '#475569';
      }

      const startBtn = document.getElementById('btnWebRecordStart');
      const startText = document.getElementById('btnWebRecordStartText');
      if (startBtn) {
        startBtn.style.background = '#2563eb';
        if (startText) startText.textContent = 'Start Recording';
      }

      const pauseBtn = document.getElementById('btnWebRecordPause');
      if (pauseBtn) pauseBtn.classList.add('d-none');

      const discardBtn = document.getElementById('btnWebRecordDiscard');
      if (discardBtn) discardBtn.classList.add('d-none');

      const timerEl = document.getElementById('webRecordTimer');
      if (timerEl) {
        timerEl.textContent = '00:00';
        timerEl.style.display = 'none';
      }

      const previewCont = document.getElementById('webAudioPreviewContainer');
      const preview = document.getElementById('webAudioPreview');
      if (previewCont) previewCont.classList.add('d-none');
      if (preview) preview.src = '';
    }


    async function deleteCustomerVisit(id) {
      if (!confirm('Are you sure you want to delete this customer visit?')) return;
      try {
        const res = await fetch(`/api/field-worker/visits/${encodeURIComponent(id)}?company_id=${encodeURIComponent(getActiveCompanyId())}`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
          showToast('Customer visit deleted.');
          await refreshOverviewState();
        }
      } catch (err) {
        showToast('Delete error: ' + err.message, true);
      }
    }

    function openEditLeadModal(visitId) {
      const v = VISITS_DATA.find(x => String(x.id) === String(visitId));
      if (!v) {
        showToast('Lead record not found.', true);
        return;
      }
      document.getElementById('editLeadId').value = v.id;
      document.getElementById('editCustomerName').value = v.customer_name || '';
      document.getElementById('editWorkerName').value = v.employee_name || '';
      document.getElementById('editContactPerson').value = v.contact_person || '';
      document.getElementById('editCustomerPhone').value = v.customer_phone || '';
      document.getElementById('editLeadStatus').value = v.lead_status || 'Interested';
      document.getElementById('editOrderAmount').value = v.order_amount || 0;
      document.getElementById('editProductPitched').value = v.product_pitched || '';
      if (v.product_pitched) {
        handleEditProductSelected(v.product_pitched);
      } else {
        const hint = document.getElementById('editProductPriceHint');
        if (hint) hint.style.display = 'none';
      }
      document.getElementById('editFollowUpDate').value = v.follow_up_date || '';
      document.getElementById('editLeadRemarks').value = v.remarks || '';

      const modal = document.getElementById('editLeadModalBackdrop');
      if (modal) modal.classList.remove('d-none');

      // Ensure warehouse products are fresh and update hint badge if needed
      if (!CURRENT_WAREHOUSE_PRODUCTS || CURRENT_WAREHOUSE_PRODUCTS.length === 0 || CURRENT_WAREHOUSE_PRODUCTS.some(p => p.qty === undefined || p.qty === null)) {
        loadWarehouseProducts().then(() => {
          if (v.product_pitched) handleEditProductSelected(v.product_pitched);
        });
      }
    }

    function closeEditLeadModal() {
      closeProductDropdown();
      const modal = document.getElementById('editLeadModalBackdrop');
      if (modal) modal.classList.add('d-none');
    }

    async function submitEditLead(e) {
      e.preventDefault();
      const visitId = document.getElementById('editLeadId').value;
      if (!visitId) return;

      const payload = {
        contact_person: document.getElementById('editContactPerson').value.trim(),
        customer_phone: document.getElementById('editCustomerPhone').value.trim(),
        lead_status: document.getElementById('editLeadStatus').value,
        order_amount: parseFloat(document.getElementById('editOrderAmount').value) || 0,
        product_pitched: document.getElementById('editProductPitched').value.trim(),
        follow_up_date: document.getElementById('editFollowUpDate').value,
        remarks: document.getElementById('editLeadRemarks').value.trim(),
        company_id: getActiveCompanyId()
      };

      try {
        const res = await fetch(`/api/field-worker/visits/${encodeURIComponent(visitId)}?company_id=${encodeURIComponent(getActiveCompanyId())}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Lead updated successfully!');
          closeEditLeadModal();
        closeWarehouseSettingsModal();
          const idx = VISITS_DATA.findIndex(x => String(x.id) === String(visitId));
          if (idx !== -1) {
            VISITS_DATA[idx] = { ...VISITS_DATA[idx], ...payload };
            renderCustomerVisitsTable(VISITS_DATA);
          } else {
            await refreshOverviewState();
          }
        } else {
          showToast(data.error || 'Failed to update lead.', true);
        }
      } catch (err) {
        showToast('Error updating lead: ' + err.message, true);
      }
    }

    // =========================================================================
    // FIELD WORKER DASHBOARD (ADMIN REAL-TIME METRICS & ATTENDANCE)
    // =========================================================================
    function renderFieldDashboard(stats) {
      if (!stats) return;
      DASHBOARD_STATS_DATA = stats;

      // Update 5 KPI Stat Cards
      const tot = document.getElementById('fwDashTotalWorkers');
      if (tot) tot.textContent = stats.total_field_workers || 0;
      const pres = document.getElementById('fwDashPresentCount');
      if (pres) pres.textContent = stats.present_today || 0;
      const presPct = document.getElementById('fwDashPresentPct');
      if (presPct) presPct.textContent = stats.present_percent || '0.0%';
      const lv = document.getElementById('fwDashOnLeaveCount');
      if (lv) lv.textContent = stats.on_leave_today || 0;
      const lvPct = document.getElementById('fwDashOnLeavePct');
      if (lvPct) lvPct.textContent = stats.on_leave_percent || '0.0%';
      const ab = document.getElementById('fwDashAbsentCount');
      if (ab) ab.textContent = stats.absent_today || 0;
      const abPct = document.getElementById('fwDashAbsentPct');
      if (abPct) abPct.textContent = stats.absent_percent || '0.0%';
      const tr = document.getElementById('fwDashTransitCount');
      if (tr) tr.textContent = stats.in_transit_now || 0;
      const os = document.getElementById('fwDashOnsiteSub');
      if (os) os.textContent = (stats.on_site_now || 0) + ' On-Site';

      // Update Operations Row
      const km = document.getElementById('fwDashTotalKm');
      if (km) km.textContent = (stats.total_distance_km || 0) + ' KM';
      const vis = document.getElementById('fwDashTotalVisits');
      if (vis) vis.textContent = (stats.total_visits || 0) + ' Visits';
      const ord = document.getElementById('fwDashTotalOrders');
      if (ord) ord.textContent = '₹' + Number(stats.total_order_amount || 0).toFixed(2);
      const det = document.getElementById('fwDashDetours');
      if (det) det.textContent = (stats.detour_alerts || 0) + ' Alerts';

      // Render Today's Attendance Table
      const attTbody = document.getElementById('fwDashAttendanceTableBody');
      if (attTbody && stats.worker_status_list) {
        if (stats.worker_status_list.length === 0) {
          attTbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:#64748b; padding:24px;">No field workers registered yet.</td></tr>';
        } else {
          attTbody.innerHTML = stats.worker_status_list.map((w, idx) => {
            let attBadge = '<span class="table-badge badge-absent" style="background:#fee2e2; color:#991b1b; padding:2px 8px; border-radius:12px; font-weight:700; font-size:11px;">Absent</span>';
            if (w.attendance_status === 'Present' || ['Present', 'In-Transit', 'On-Site', 'Detour Alert'].includes(w.status)) {
              attBadge = '<span class="table-badge badge-present" style="background:#dcfce7; color:#166534; padding:2px 8px; border-radius:12px; font-weight:700; font-size:11px;">Present</span>';
            } else if (w.attendance_status === 'On Leave' || w.status === 'On Leave') {
              attBadge = '<span class="table-badge badge-leave" style="background:#fef3c7; color:#92400e; padding:2px 8px; border-radius:12px; font-weight:700; font-size:11px;">On Leave</span>';
            }

            let liveBadge = '<span class="badge-neutral" style="font-size:10.5px;">Not Active</span>';
            const ls = String(w.live_status || w.status || '');
            if (ls.includes('On-Site') || ls.includes('Verified')) {
              liveBadge = '<span class="badge-onsite" style="font-size:10.5px;"><i class="fa-solid fa-circle-check"></i> On-Site</span>';
            } else if (ls.includes('Transit')) {
              liveBadge = '<span class="badge-transit" style="font-size:10.5px;"><i class="fa-solid fa-route"></i> Transit</span>';
            } else if (ls.includes('Detour')) {
              liveBadge = '<span class="badge-detour" style="font-size:10.5px;"><i class="fa-solid fa-triangle-exclamation"></i> Detour</span>';
            } else if (w.attendance_status === 'On Leave' || w.status === 'On Leave') {
              liveBadge = '<span class="badge-neutral" style="font-size:10.5px;">On Leave</span>';
            } else if (w.attendance_status === 'Present' || w.status === 'Present') {
              liveBadge = '<span class="badge-onsite" style="font-size:10.5px;"><i class="fa-solid fa-circle-check"></i> Active</span>';
            }

            return `<tr>
              <td style="text-align:center; color:#64748b;">${idx + 1}</td>
              <td style="font-weight:700; color:#0f172a; white-space:nowrap;">${w.employee_name}</td>
              <td style="color:#475569; white-space:nowrap;">${w.branch_name || 'Home Branch'}</td>
              <td style="text-align:center; white-space:nowrap;">${attBadge}</td>
              <td style="text-align:center; white-space:nowrap;">${w.in_time || '--'}</td>
              <td style="text-align:center; white-space:nowrap;">${w.out_time || '--'}</td>
              <td style="text-align:center; font-weight:700; color:#2563eb;">${Number(w.distance_km || 0).toFixed(1)}</td>
              <td style="text-align:center; font-weight:700; color:#0f766e;">${w.visits_count || 0}</td>
              <td style="text-align:center; white-space:nowrap;">${liveBadge}</td>
            </tr>`;
          }).join('');
        }
      }

      // Render Branch Breakdown Table
      const brTbody = document.getElementById('fwDashBranchTableBody');
      if (brTbody && stats.branch_breakdown) {
        if (stats.branch_breakdown.length === 0) {
          brTbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#64748b; padding:24px;">No branch activity recorded today.</td></tr>';
        } else {
          brTbody.innerHTML = stats.branch_breakdown.map(b => `
            <tr>
              <td style="font-weight:700; color:#0f172a; white-space:nowrap;">${b.branch_name}</td>
              <td style="text-align:center; font-weight:700;">${b.total}</td>
              <td style="text-align:center; font-weight:700; color:#16a34a;">${b.present}</td>
              <td style="text-align:center; font-weight:700; color:#2563eb;">${Number(b.km || 0).toFixed(1)}</td>
              <td style="text-align:center; font-weight:700; color:#0f766e;">${b.visits}</td>
            </tr>
          `).join('');
        }
      }
    }

    // =========================================================================
    // FIELD WORKER LEAVE & PERMISSION MANAGEMENT (ADMIN & EMPLOYEE)
    // =========================================================================
    let currentFwLeaveFilter = '';
    let cachedFwBalances = [];

    function escapeHtml(str) {
      if (str === null || str === undefined) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    function filterFwLeaveTab(status, btnEl) {
      currentFwLeaveFilter = status;
      document.querySelectorAll('#paneFieldLeaves .req-tab-filter').forEach(b => {
        b.classList.remove('active');
      });
      if (btnEl) btnEl.classList.add('active');
      renderFwRequestsTable();
    }

    function filterFwLeaveRequestsLocal() {
      renderFwRequestsTable();
    }

    async function loadFwRequests() {
      const cid = getActiveCompanyId();
      try {
        const url = `/api/field-worker/leave-requests?company_id=${encodeURIComponent(cid)}&status=${encodeURIComponent(currentFwLeaveFilter || 'ALL')}&limit=100`;
        const res = await fetch(url);
        if (!res.ok) return;
        const data = await res.json();
        if (!data.success) return;

        FW_LEAVE_REQUESTS_DATA = data.requests || [];
        updateFwRequestTabBadges(data.status_counts);
        renderFwRequestsTable();
      } catch (err) {
        console.error('Error fetching FW leave requests:', err);
      }
    }

    function updateFwRequestTabBadges(counts = {}) {
      const allCount = Number(counts.all ?? 0);
      const pendingCount = Number(counts.pending ?? 0);
      const approvedCount = Number(counts.approved ?? 0);
      const rejectedCount = Number(counts.rejected ?? 0);

      const bAll = document.getElementById('badgeFwReqAll');
      if (bAll) { bAll.textContent = allCount; bAll.style.display = allCount > 0 ? 'inline-flex' : 'none'; }
      const bPending = document.getElementById('badgeFwReqPending');
      if (bPending) { bPending.textContent = pendingCount; bPending.style.display = pendingCount > 0 ? 'inline-flex' : 'none'; }
      const bApproved = document.getElementById('badgeFwReqApproved');
      if (bApproved) { bApproved.textContent = approvedCount; bApproved.style.display = approvedCount > 0 ? 'inline-flex' : 'none'; }
      const bRejected = document.getElementById('badgeFwReqRejected');
      if (bRejected) { bRejected.textContent = rejectedCount; bRejected.style.display = rejectedCount > 0 ? 'inline-flex' : 'none'; }

      const sideBadge = document.getElementById('sidebarFwLeaveBadge');
      if (sideBadge) {
        sideBadge.textContent = pendingCount;
        sideBadge.style.display = pendingCount > 0 ? '' : 'none';
      }
    }

    function renderFwRequestsTable() {
      const tbody = document.getElementById('fwLeaveRequestsTbody');
      if (!tbody) return;

      const searchInput = document.getElementById('fwSearchRequestsInput');
      const query = (searchInput ? searchInput.value : '').toLowerCase().trim();

      const filtered = (FW_LEAVE_REQUESTS_DATA || []).filter(r => {
        if (currentFwLeaveFilter && (r.status || '').toLowerCase() !== currentFwLeaveFilter.toLowerCase()) {
          return false;
        }
        if (!query) return true;
        const empMatch = (r.employee_name || '').toLowerCase().includes(query);
        const idMatch = (r.employee_id || '').toLowerCase().includes(query);
        const reqIdMatch = (r.request_id || r.id || '').toLowerCase().includes(query);
        const reasonMatch = (r.reason || '').toLowerCase().includes(query);
        return empMatch || idMatch || reqIdMatch || reasonMatch;
      });

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; padding: 24px; color: #94a3b8; font-size: 12.5px;">No requests found matching criteria.</td></tr>`;
        return;
      }

      tbody.innerHTML = filtered.map((r, idx) => {
        const reqId = r.request_id || r.id;
        const isPerm = r.request_type === 'Permission';
        const typeBadge = isPerm
          ? `<span class="badge-type-perm" style="background:#eff6ff; color:#1d4ed8; padding:3px 8px; border-radius:5px; font-weight:700; font-size:11px;">Permission</span>`
          : `<span class="badge-type-leave" style="background:#fdf4ff; color:#86198f; padding:3px 8px; border-radius:5px; font-weight:700; font-size:11px;">${escapeHtml(r.leave_type ? r.leave_type.split(' ')[0] : 'Leave')}</span>`;

        const st = (r.status || 'Pending').toLowerCase();
        const statusLabel = r.status || (st === 'approved' ? 'Approved' : (st === 'rejected' ? 'Rejected' : 'Pending'));
        const remark = (r.admin_remark || '').trim();

        let badgeBg = '#fef3c7'; let badgeColor = '#d97706';
        if (st === 'approved') { badgeBg = '#dcfce7'; badgeColor = '#15803d'; }
        else if (st === 'rejected') { badgeBg = '#fee2e2'; badgeColor = '#dc2626'; }

        let statusBadge = '';
        if (remark) {
          statusBadge = `
            <div style="display: inline-flex; flex-direction: column; align-items: center; gap: 3px; max-width: 200px;">
              <span style="background:${badgeBg}; color:${badgeColor}; font-size: 11px; padding: 2.5px 8px; border-radius: 5px; font-weight: 700; display: inline-block;">${escapeHtml(statusLabel)}</span>
              <span style="font-size: 10.5px; color: #475569; line-height: 1.3; font-weight: 500; word-break: break-word;" title="${escapeHtml(remark)}">${escapeHtml(remark)}</span>
            </div>
          `;
        } else {
          statusBadge = `<span style="background:${badgeBg}; color:${badgeColor}; font-size: 11px; padding: 2.5px 8px; border-radius: 5px; font-weight: 700; display: inline-block;">${escapeHtml(statusLabel)}</span>`;
        }

        // Date / Period
        let datePeriod = '';
        if (isPerm) {
          datePeriod = `<strong>${escapeHtml(r.date || r.from_date || '-')}</strong><br><span style="font-size: 11px; color: #64748b;">${escapeHtml(r.from_time || '')} - ${escapeHtml(r.to_time || '')} (${escapeHtml(r.duration || r.duration_hours || '02:00')})</span>`;
        } else {
          const fromDate = r.from_date || '-';
          const toDate = r.to_date || fromDate;
          const count = `${r.days_count || r.total_days || 1} Day(s)`;
          datePeriod = `<strong>${escapeHtml(fromDate)}</strong>${toDate !== fromDate ? ' to <strong>' + escapeHtml(toDate) + '</strong>' : ''}<br><span style="font-size: 11px; color: #0284c7; font-weight: 700;">${count} (${escapeHtml(r.session || 'Full Day')})</span>`;
        }

        // Attachment
        let attCol = `<span style="color: #cbd5e1;">-</span>`;
        const attUrl = (r.attachments && r.attachments.length > 0) ? r.attachments[0].file_url : r.attachment_url;
        if (attUrl) {
          attCol = `
            <a href="${escapeHtml(attUrl)}" target="_blank" title="View Document" style="display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 6px; background: #e0f2fe; color: #0284c7; text-decoration: none;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
              </svg>
            </a>
          `;
        }

        // Quick Actions
        let actionButtons = `<div style="display: flex; align-items: center; justify-content: center; gap: 6px;">`;
        if (st === 'pending') {
          actionButtons += `
            <button type="button" onclick="quickApproveFwRequest('${reqId}', '${escapeHtml(r.employee_name || '')}')" title="Quick Approve" style="border: none; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 6px; background: #dcfce7; color: #16a34a; transition: all 0.15s ease;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            </button>
            <button type="button" onclick="openFwQuickRejectModal('${reqId}')" title="Quick Reject" style="border: none; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; width: 28px; height: 28px; border-radius: 6px; background: #fee2e2; color: #dc2626; transition: all 0.15s ease;">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          `;
        } else {
          actionButtons += `<span style="font-size:11px; color:#64748b;">${escapeHtml(r.reviewer || 'Processed')}</span>`;
        }
        actionButtons += `</div>`;

        return `
          <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 10px 14px; text-align: center; font-size: 11.5px; color: #64748b; font-weight: 600;">${idx + 1}</td>
            <td style="padding: 10px 14px; font-size: 12px;">${typeBadge}</td>
            <td style="padding: 10px 14px; font-size: 12px;">
              <strong style="color: #0f172a;">${escapeHtml(r.employee_name)}</strong><br>
              <span style="font-size: 11px; color: #64748b;">ID: ${escapeHtml(r.employee_id || r.employee_code || '-')} &bull; ${escapeHtml(r.branch_name || 'Home Branch')}</span>
            </td>
            <td style="padding: 10px 14px; font-size: 12px;">${datePeriod}</td>
            <td style="padding: 10px 14px; font-size: 12px; max-width: 220px; white-space: normal; line-height: 1.4; color: #334155;">
              ${escapeHtml(r.reason || '-')}
            </td>
            <td style="padding: 10px 14px; text-align: center;">${attCol}</td>
            <td style="padding: 10px 14px; text-align: center; font-size: 11px;">${statusBadge}</td>
            <td style="padding: 10px 14px; text-align: center;">${actionButtons}</td>
          </tr>
        `;
      }).join('');
    }

    function renderFieldLeaveSystem(requests, counts, stats) {
      if (requests) FW_LEAVE_REQUESTS_DATA = requests;
      if (counts) {
        FW_LEAVE_COUNTS_DATA = counts;
        updateFwRequestTabBadges(counts);
      } else if (requests) {
        updateFwRequestTabBadges({
          all: requests.length,
          pending: requests.filter(r => (r.status || '').toLowerCase() === 'pending').length,
          approved: requests.filter(r => (r.status || '').toLowerCase() === 'approved').length,
          rejected: requests.filter(r => (r.status || '').toLowerCase() === 'rejected').length
        });
      }

      renderFwRequestsTable();

      // Render Employee self-service table if present
      const empTbody = document.getElementById('myFwLeaveApplicationsTableBody');
      if (empTbody && requests) {
        if (requests.length === 0) {
          empTbody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:#64748b; padding:28px;">You haven\'t submitted any leave or permission requests yet.</td></tr>';
        } else {
          empTbody.innerHTML = requests.map(r => {
            const isPerm = r.request_type === 'Permission';
            const typeBadge = isPerm
              ? '<span class="badge-neutral" style="background:#eff6ff; color:#1d4ed8; border-color:#bfdbfe;">Permission</span>'
              : '<span class="badge-neutral" style="background:#fdf4ff; color:#86198f; border-color:#f5d0fe;">Leave</span>';
            const cat = r.leave_type || r.permission_type || 'Casual Leave';
            const sessionStr = isPerm ? `${r.from_time || ''} - ${r.to_time || ''}` : (r.session || 'Full Day');
            const datesStr = isPerm ? (r.date || r.from_date || '') : `${r.from_date || ''} to ${r.to_date || ''}`;
            const durStr = isPerm ? `${r.duration || r.duration_hours || '02:00'} hrs` : `${r.days_count || r.total_days || 1} Day(s)`;

            let statusBadge = '<span class="badge-transit"><i class="fa-solid fa-clock"></i> Pending</span>';
            if (r.status === 'Approved') {
              statusBadge = '<span class="badge-onsite"><i class="fa-solid fa-check"></i> Approved</span>';
            } else if (r.status === 'Rejected') {
              statusBadge = '<span class="badge-detour"><i class="fa-solid fa-xmark"></i> Rejected</span>';
            }

            return `<tr>
              <td>${typeBadge}</td>
              <td>
                <div style="font-weight:700; color:#0f172a;">${cat}</div>
                <div class="fw-cell-sub">${sessionStr}</div>
              </td>
              <td><div style="font-weight:700; white-space:nowrap;">${datesStr}</div></td>
              <td style="text-align:center; font-weight:700;">${durStr}</td>
              <td style="max-width:250px;">${r.reason || '-'}</td>
              <td style="text-align:center; white-space:nowrap;">${statusBadge}</td>
              <td style="font-size:11.5px; color:#475569;">${r.admin_remark || '-'}</td>
            </tr>`;
          }).join('');
        }
      }
    }

    // Quick Approve Action
    async function quickApproveFwRequest(reqId, workerName) {
      if (!confirm(`Are you sure you want to approve request for ${workerName || reqId}?`)) return;

      try {
        const res = await fetch(`/api/field-worker/leave-requests/${encodeURIComponent(reqId)}/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'Approved' })
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Leave request approved successfully.');
          await loadFwRequests();
        } else {
          showToast(data.error || 'Failed to approve request.', true);
        }
      } catch (err) {
        showToast('Error approving request: ' + err.message, true);
      }
    }

    // Quick Reject Modal Handlers
    function openFwQuickRejectModal(reqId) {
      const modal = document.getElementById('fwModalQuickReject');
      const reqIdInput = document.getElementById('fwQuickRejectReqId');
      const remarkInput = document.getElementById('fwQuickRejectRemark');
      if (reqIdInput) reqIdInput.value = reqId;
      if (remarkInput) remarkInput.value = '';
      if (modal) modal.style.display = 'flex';
    }

    function closeFwQuickRejectModal() {
      const modal = document.getElementById('fwModalQuickReject');
      if (modal) modal.style.display = 'none';
    }

    async function confirmFwQuickReject() {
      const reqId = document.getElementById('fwQuickRejectReqId').value;
      const remark = document.getElementById('fwQuickRejectRemark').value.trim();
      if (!reqId) return;

      try {
        const res = await fetch(`/api/field-worker/leave-requests/${encodeURIComponent(reqId)}/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ action: 'Rejected', admin_remark: remark })
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Leave request rejected successfully.');
          closeFwQuickRejectModal();
          await loadFwRequests();
        } else {
          showToast(data.error || 'Failed to reject request.', true);
        }
      } catch (err) {
        showToast('Error rejecting request: ' + err.message, true);
      }
    }

    // Leave Balances & Quotas Modal Handlers
    async function openFwLeaveBalancesModal() {
      const modal = document.getElementById('fwModalEmployeeLeaveBalances');
      if (modal) {
        modal.style.display = 'flex';
        await loadFwBalances();
      }
    }

    function closeFwLeaveBalancesModal() {
      const modal = document.getElementById('fwModalEmployeeLeaveBalances');
      if (modal) modal.style.display = 'none';
    }

    async function loadFwBalances() {
      const tbody = document.getElementById('fwLeaveBalancesTbody');
      if (!tbody) return;
      try {
        const cid = getActiveCompanyId();
        const res = await fetch(`/api/field-worker/leave-balances?company_id=${encodeURIComponent(cid)}`);
        if (!res.ok) {
          tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: #dc2626;">Failed to load field worker balances.</td></tr>`;
          return;
        }
        const data = await res.json();
        if (!data.success) return;

        cachedFwBalances = data.balances || [];
        renderFwBalancesTable();
      } catch (err) {
        console.error('Error fetching FW balances:', err);
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: #dc2626;">Error loading balances.</td></tr>`;
      }
    }

    function renderFwBalancesTable() {
      const tbody = document.getElementById('fwLeaveBalancesTbody');
      if (!tbody) return;

      const searchInput = document.getElementById('fwSearchBalancesInput');
      const query = (searchInput ? searchInput.value : '').toLowerCase().trim();

      const filtered = (cachedFwBalances || []).filter(b => {
        if (!query) return true;
        const nameMatch = (b.employee_name || '').toLowerCase().includes(query);
        const idMatch = (b.employee_id || b.id || '').toLowerCase().includes(query);
        const deptMatch = (b.department || '').toLowerCase().includes(query);
        return nameMatch || idMatch || deptMatch;
      });

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 24px; color: #94a3b8; font-size: 12.5px;">No field workers found.</td></tr>`;
        return;
      }

      tbody.innerHTML = filtered.map(b => {
        const customLeaves = b.custom_leaves || [];
        let leavesHtml = '';
        if (customLeaves.length > 0) {
          leavesHtml = customLeaves.map(lv => {
            const avail = (lv.available !== undefined) ? lv.available : lv.total;
            return `<span style="display:inline-block; margin:2px 4px 2px 0; background:#f0f9ff; border:1px solid #bae6fd; color:#0369a1; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:700;">${escapeHtml(lv.name)}: ${avail} / ${lv.total} ${escapeHtml(lv.unit || 'Days')}</span>`;
          }).join('');
        } else {
          leavesHtml = `
            <span style="display:inline-block; margin:2px 4px 2px 0; background:#eff6ff; color:#1d4ed8; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:700;">CL: ${b.cl_remaining ?? 12}/${b.cl_quota ?? 12}</span>
            <span style="display:inline-block; margin:2px 4px 2px 0; background:#f0fdf4; color:#15803d; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:700;">SL: ${b.sl_remaining ?? 12}/${b.sl_quota ?? 12}</span>
            <span style="display:inline-block; margin:2px 4px 2px 0; background:#fdf4ff; color:#86198f; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:700;">EL: ${b.el_remaining ?? 15}/${b.el_quota ?? 15}</span>
            <span style="display:inline-block; margin:2px 4px 2px 0; background:#fef3c7; color:#b45309; padding:2px 8px; border-radius:12px; font-size:11px; font-weight:700;">Perm: ${b.permission_hours_used ?? 0}h used</span>
          `;
        }

        const bJson = encodeURIComponent(JSON.stringify(b));
        return `
          <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 10px 14px; font-size: 11.5px; color: #64748b; font-weight: 700;">${escapeHtml(b.employee_id || b.id || '-')}</td>
            <td style="padding: 10px 14px; font-size: 12px; font-weight: 700; color: #0f172a;">${escapeHtml(b.employee_name)}</td>
            <td style="padding: 10px 14px; font-size: 12px; color: #475569;">${escapeHtml(b.department || 'Field Sales & Operations')}</td>
            <td style="padding: 10px 14px; font-size: 12px;">${leavesHtml}</td>
            <td style="padding: 10px 14px; text-align: center;">
              <button type="button" onclick="openFwSetQuotaModal('${bJson}')" class="btn-primary-action" style="padding: 4px 12px; font-size: 11px; font-weight: 700; border-radius: 6px; cursor: pointer;">
                Set
              </button>
            </td>
          </tr>
        `;
      }).join('');
    }

    // Set Custom Quota Modal Handlers
    function openFwSetQuotaModal(bJsonStr) {
      const data = JSON.parse(decodeURIComponent(bJsonStr));
      const modal = document.getElementById('fwModalSetEmployeeLeaveQuota');
      const empIdInput = document.getElementById('fwQuotaEmpId');
      const compIdInput = document.getElementById('fwQuotaEmpCompanyId');
      const subtitle = document.getElementById('fwQuotaModalSubtitle');
      const container = document.getElementById('fwCustomLeaveRowsContainer');
      const alertBox = document.getElementById('fwQuotaAlertBox');

      if (empIdInput) empIdInput.value = data.id || data.employee_id || '';
      if (compIdInput) compIdInput.value = data.company_id || getActiveCompanyId();
      if (subtitle) {
        subtitle.textContent = `Configuring: ${data.employee_name || 'Field Worker'} (ID: ${data.employee_id || data.id || ''})`;
      }
      if (alertBox) alertBox.style.display = 'none';

      if (container) {
        container.innerHTML = '';
        const leaves = Array.isArray(data.custom_leaves) ? data.custom_leaves : [];
        if (leaves.length > 0) {
          leaves.forEach(lv => addFwLeaveTypeRow(lv.name, lv.total, lv.unit || 'Days'));
        } else {
          addFwLeaveTypeRow('Casual Leave (CL)', data.cl_quota || 12, 'Days');
          addFwLeaveTypeRow('Sick Leave (SL)', data.sl_quota || 12, 'Days');
          addFwLeaveTypeRow('Earned Leave (EL)', data.el_quota || 15, 'Days');
        }
      }

      if (modal) modal.style.display = 'flex';
    }

    function closeFwSetQuotaModal() {
      const modal = document.getElementById('fwModalSetEmployeeLeaveQuota');
      if (modal) modal.style.display = 'none';
    }

    function addFwLeaveTypeRow(name = '', total = '', unit = 'Days') {
      const container = document.getElementById('fwCustomLeaveRowsContainer');
      if (!container) return;

      const row = document.createElement('div');
      row.className = 'custom-leave-row';
      row.style.cssText = 'display: grid; grid-template-columns: 1fr 100px 90px 32px; gap: 8px; align-items: center;';
      row.innerHTML = `
        <div>
          <input type="text" class="custom-leave-name" placeholder="e.g., Casual Leave, Medical Leave" value="${escapeHtml(name)}" style="width: 100%; box-sizing: border-box; padding: 7px 10px; border-radius: 6px; border: 1.5px solid #cbd5e1; font-size: 12px; font-weight: 600;">
        </div>
        <div>
          <input type="number" step="0.5" min="0" max="365" class="custom-leave-total" placeholder="Allowed" value="${total}" style="width: 100%; box-sizing: border-box; padding: 7px 10px; border-radius: 6px; border: 1.5px solid #cbd5e1; font-size: 12px; font-weight: 600; text-align: center;">
        </div>
        <div>
          <select class="custom-leave-unit" style="width: 100%; box-sizing: border-box; padding: 7px 6px; border-radius: 6px; border: 1.5px solid #cbd5e1; font-size: 12px; font-weight: 600; background: #ffffff;">
            <option value="Days" ${unit === 'Days' ? 'selected' : ''}>Days</option>
            <option value="Hours" ${unit === 'Hours' ? 'selected' : ''}>Hours</option>
          </select>
        </div>
        <div style="text-align: center;">
          <button type="button" class="btn-remove-leave-row" title="Remove" style="background: none; border: none; color: #ef4444; font-size: 20px; font-weight: 700; cursor: pointer; padding: 0; line-height: 1;">
            &times;
          </button>
        </div>
      `;

      row.querySelector('.btn-remove-leave-row').addEventListener('click', () => {
        row.remove();
        if (container.children.length === 0) {
          addFwLeaveTypeRow('', '', 'Days');
        }
      });

      container.appendChild(row);
    }

    async function saveFwEmployeeQuota(e) {
      e.preventDefault();
      const saveBtn = document.getElementById('btnSaveFwEmployeeQuota');
      const alertBox = document.getElementById('fwQuotaAlertBox');
      const empId = document.getElementById('fwQuotaEmpId').value;
      const compId = document.getElementById('fwQuotaEmpCompanyId').value;
      const rows = document.querySelectorAll('#fwCustomLeaveRowsContainer .custom-leave-row');

      const custom_leaves = [];
      rows.forEach(r => {
        const name = (r.querySelector('.custom-leave-name')?.value || '').trim();
        const total = parseFloat(r.querySelector('.custom-leave-total')?.value) || 0;
        const unit = r.querySelector('.custom-leave-unit')?.value || 'Days';
        if (name) {
          custom_leaves.push({ name, total, unit });
        }
      });

      if (!empId) {
        if (alertBox) {
          alertBox.style.display = 'block';
          alertBox.style.backgroundColor = '#fef2f2';
          alertBox.style.color = '#991b1b';
          alertBox.textContent = 'Employee ID is missing.';
        }
        return;
      }

      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';
      }

      try {
        const res = await fetch('/api/admin/leave-permission/employee-custom-leaves', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            employee_id: empId,
            company_id: compId,
            custom_leaves: custom_leaves
          })
        });
        const data = await res.json();
        if (data.success) {
          if (alertBox) {
            alertBox.style.display = 'block';
            alertBox.style.backgroundColor = '#ecfdf5';
            alertBox.style.color = '#065f46';
            alertBox.style.border = '1px solid #a7f3d0';
            alertBox.textContent = data.message || 'Custom leaves saved successfully!';
          }
          await loadFwBalances();
          setTimeout(() => {
            closeFwSetQuotaModal();
          }, 600);
        } else {
          if (alertBox) {
            alertBox.style.display = 'block';
            alertBox.style.backgroundColor = '#fef2f2';
            alertBox.style.color = '#991b1b';
            alertBox.style.border = '1px solid #fecaca';
            alertBox.textContent = data.error || 'Failed to update custom leaves.';
          }
        }
      } catch (err) {
        if (alertBox) {
          alertBox.style.display = 'block';
          alertBox.style.backgroundColor = '#fef2f2';
          alertBox.style.color = '#991b1b';
          alertBox.style.border = '1px solid #fecaca';
          alertBox.textContent = 'Error: ' + err.message;
        }
      } finally {
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.textContent = 'Save Leaves';
        }
      }
    }

    // Modal: Field Worker Employee Leave Application
    function openApplyFwLeaveModal() {
      const modal = document.getElementById('applyFwLeaveModalBackdrop');
      if (modal) modal.classList.remove('d-none');
    }

    function closeApplyFwLeaveModal() {
      const modal = document.getElementById('applyFwLeaveModalBackdrop');
      if (modal) modal.classList.add('d-none');
    }

    async function submitApplyFwLeave(e) {
      e.preventDefault();
      const payload = {
        leave_type: document.getElementById('fwLeaveTypeSelect').value,
        from_date: document.getElementById('fwLeaveFromDate').value,
        to_date: document.getElementById('fwLeaveToDate').value,
        session: document.getElementById('fwLeaveSession').value,
        reason: document.getElementById('fwLeaveReason').value.trim(),
        company_id: getActiveCompanyId()
      };

      try {
        const res = await fetch('/api/field-worker/leave-requests/apply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Leave application submitted successfully!');
          closeApplyFwLeaveModal();
          document.getElementById('applyFwLeaveForm').reset();
          await refreshOverviewState();
        } else {
          showToast(data.error || 'Failed to submit leave request.', true);
        }
      } catch (err) {
        showToast('Error submitting leave: ' + err.message, true);
      }
    }

    // Modal: Field Worker Employee Permission Application
    function openApplyFwPermissionModal() {
      const modal = document.getElementById('applyFwPermissionModalBackdrop');
      if (modal) modal.classList.remove('d-none');
    }

    function closeApplyFwPermissionModal() {
      const modal = document.getElementById('applyFwPermissionModalBackdrop');
      if (modal) modal.classList.add('d-none');
    }

    async function submitApplyFwPermission(e) {
      e.preventDefault();
      const payload = {
        permission_type: document.getElementById('fwPermTypeSelect').value,
        date: document.getElementById('fwPermDate').value,
        from_time: document.getElementById('fwPermFromTime').value,
        to_time: document.getElementById('fwPermToTime').value,
        duration: document.getElementById('fwPermDuration').value.trim() || '02:00',
        reason: document.getElementById('fwPermReason').value.trim(),
        company_id: getActiveCompanyId()
      };

      try {
        const res = await fetch('/api/field-worker/permission-requests/apply', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Permission application submitted successfully!');
          closeApplyFwPermissionModal();
          document.getElementById('applyFwPermissionForm').reset();
          await refreshOverviewState();
        } else {
          showToast(data.error || 'Failed to submit permission request.', true);
        }
      } catch (err) {
        showToast('Error submitting permission: ' + err.message, true);
      }
    }

    // =========================================================================
    // FIELD WORKER MODULE: MANUAL ENTRY CONTROLLER (ISOLATED)
    // =========================================================================
    let FW_MANUAL_PAGE = 1;
    let FW_MANUAL_LIMIT = 10;
    let FW_MANUAL_TOTAL = 0;
    let fwManualSearchTimeout = null;

    function debounceFwManualSearch() {
      clearTimeout(fwManualSearchTimeout);
      fwManualSearchTimeout = setTimeout(() => {
        FW_MANUAL_PAGE = 1;
        loadFieldManualEntries();
      }, 300);
    }

    function clearFieldManualFilters() {
      const fFrom = document.getElementById('filterFwManualFrom');
      const fTo = document.getElementById('filterFwManualTo');
      const fStat = document.getElementById('filterFwManualStatus');
      const fSrch = document.getElementById('filterFwManualSearch');
      if (fFrom) fFrom.value = '';
      if (fTo) fTo.value = '';
      if (fStat) fStat.value = 'All';
      if (fSrch) fSrch.value = '';
      FW_MANUAL_PAGE = 1;
      loadFieldManualEntries();
    }

    function changeFwManualPage(delta) {
      const newPage = FW_MANUAL_PAGE + delta;
      const maxPages = Math.ceil(FW_MANUAL_TOTAL / FW_MANUAL_LIMIT) || 1;
      if (newPage >= 1 && newPage <= maxPages) {
        FW_MANUAL_PAGE = newPage;
        loadFieldManualEntries();
      }
    }

    async function loadFieldManualEntries() {
      const tbody = document.getElementById('fieldManualEntryTableBody');
      if (!tbody) return;

      const cid = getActiveCompanyId();
      const fromDate = document.getElementById('filterFwManualFrom')?.value || '';
      const toDate = document.getElementById('filterFwManualTo')?.value || '';
      const status = document.getElementById('filterFwManualStatus')?.value || 'All';
      const search = document.getElementById('filterFwManualSearch')?.value || '';

      const params = new URLSearchParams({
        company_id: cid,
        from_date: fromDate,
        to_date: toDate,
        status: status,
        search: search,
        page: FW_MANUAL_PAGE,
        limit: FW_MANUAL_LIMIT
      });

      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#64748b; padding:24px;">
        <i class="fa-solid fa-spinner fa-spin" style="margin-right:6px; color:#2563eb;"></i> Loading field worker entries...
      </td></tr>`;

      try {
        const res = await fetch(`/api/field-worker/manual-entries?${params.toString()}`);
        const data = await res.json();
        if (!data.success) {
          tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#ef4444; padding:20px;">${escapeHtml(data.error || 'Failed to load entries')}</td></tr>`;
          return;
        }

        FW_MANUAL_TOTAL = data.total || 0;
        renderFieldManualEntriesTable(data.data || []);

        const info = document.getElementById('fwManualTableInfo');
        if (info) {
          const start = FW_MANUAL_TOTAL === 0 ? 0 : ((FW_MANUAL_PAGE - 1) * FW_MANUAL_LIMIT + 1);
          const end = Math.min(FW_MANUAL_PAGE * FW_MANUAL_LIMIT, FW_MANUAL_TOTAL);
          info.textContent = `Showing ${start} to ${end} of ${FW_MANUAL_TOTAL} entries`;
        }

        const curBtn = document.getElementById('fwManualCurrentPage');
        if (curBtn) curBtn.textContent = FW_MANUAL_PAGE;

        const maxPages = Math.ceil(FW_MANUAL_TOTAL / FW_MANUAL_LIMIT) || 1;
        const prevBtn = document.getElementById('fwManualPrevBtn');
        const nextBtn = document.getElementById('fwManualNextBtn');
        if (prevBtn) prevBtn.classList.toggle('disabled', FW_MANUAL_PAGE <= 1);
        if (nextBtn) nextBtn.classList.toggle('disabled', FW_MANUAL_PAGE >= maxPages);

      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#ef4444; padding:20px;">Network error: ${escapeHtml(err.message)}</td></tr>`;
      }
    }

    function renderFieldManualEntriesTable(rows) {
      const tbody = document.getElementById('fieldManualEntryTableBody');
      if (!tbody) return;

      if (!rows || rows.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#64748b; padding:28px;">
          <div style="display:flex; flex-direction:column; align-items:center; gap:6px;">
            <i class="fa-solid fa-clipboard-list" style="font-size:24px; color:#94a3b8;"></i>
            <span>No field worker manual entries found.</span>
          </div>
        </td></tr>`;
        return;
      }

      const isAdmin = (CURRENT_USER_ROLE === 'super_admin' || CURRENT_USER_ROLE === 'company_admin' || CURRENT_USER_ROLE === 'admin');

      tbody.innerHTML = rows.map(r => {
        const entryId = r.id || r._id || '';
        const entryType = (r.entry_type || 'Add').toUpperCase();
        const typeBadge = entryType === 'SUB'
          ? `<span class="badge-neutral" style="background:#fee2e2; color:#dc2626; font-weight:700;"><i class="fa-solid fa-minus"></i> SUB</span>`
          : `<span class="badge-neutral" style="background:#dcfce7; color:#16a34a; font-weight:700;"><i class="fa-solid fa-plus"></i> ADD</span>`;

        let statusBadge = `<span class="badge-neutral">${escapeHtml(r.status || 'Proper')}</span>`;
        if (r.status === 'Proper') {
          statusBadge = `<span class="badge-neutral" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0;">Proper</span>`;
        } else if (r.status === 'Permission') {
          statusBadge = `<span class="badge-neutral" style="background:#eff6ff; color:#2563eb; border:1px solid #bfdbfe;">Permission</span>`;
        } else if (r.status === 'Improper') {
          statusBadge = `<span class="badge-neutral" style="background:#fef2f2; color:#b91c1c; border:1px solid #fecaca;">Improper</span>`;
        }

        const sal = parseFloat(r.working_salary || 0.0);
        const salColor = sal < 0 ? '#dc2626' : (sal > 0 ? '#16a34a' : '#475569');
        const salPrefix = sal > 0 ? '+' : '';

        return `<tr>
          <td>
            <div class="fw-cell-title">${escapeHtml(r.employee_name || '')}</div>
            <div class="fw-cell-sub">Field Force</div>
          </td>
          <td style="font-weight:600; white-space:nowrap;">${escapeHtml(r.entry_date || '')}</td>
          <td style="font-weight:700; font-family:monospace; font-size:13px;">${escapeHtml(r.hours || '00:00')}</td>
          <td>${typeBadge}</td>
          <td>${statusBadge}</td>
          <td style="font-weight:700; color:${salColor}; white-space:nowrap;">
            ${salPrefix}₹${Math.abs(sal).toFixed(2)}
          </td>
          <td style="max-width:220px; font-size:12px; color:#475569;">${escapeHtml(r.reason || '-')}</td>
          <td style="font-size:11px; color:#64748b; white-space:nowrap;">${escapeHtml(r.submitted_at || '-')}</td>
          ${isAdmin ? `
          <td style="text-align:center;">
            <button type="button" class="btn-action-icon btn-action-delete" onclick="deleteFieldManualEntry('${escapeHtml(entryId)}')" title="Delete Entry">
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </td>` : ''}
        </tr>`;
      }).join('');
    }

    function openFieldManualEntryModal() {
      const modal = document.getElementById('modalFieldManualEntry');
      const form = document.getElementById('formFieldManualEntry');
      if (form) form.reset();

      const dInput = document.getElementById('inputFieldManualDate');
      if (dInput) {
        const today = new Date().toISOString().split('T')[0];
        dInput.value = today;
      }
      const hrsInput = document.getElementById('inputFieldManualHours');
      if (hrsInput) hrsInput.value = '08:00';

      if (modal) modal.classList.remove('d-none');
    }

    function updatePetrolRatePreview() {
      const rate = parseFloat(document.getElementById('cfgPetrolRateInr')?.value) || 0;
      const effective = rate.toFixed(2);
      const el = document.getElementById('cfgPetrolEffectivePreview');
      if (el) el.innerText = `₹${effective} / KM`;
    }

    async function openConfigurePetrolModal() {
      const modal = document.getElementById('modalConfigurePetrol');
      if (!modal) return;
      const cid = getActiveCompanyId();
      try {
        const res = await fetch(`/api/field-worker/petrol-rate-config?company_id=${encodeURIComponent(cid)}`);
        const data = await res.json();
        if (data.success) {
          const uInput = document.getElementById('cfgPetrolUnitKm');
          const rInput = document.getElementById('cfgPetrolRateInr');
          if (uInput) uInput.value = data.unit_km !== undefined ? data.unit_km : 1;
          if (rInput) rInput.value = data.rate_inr !== undefined ? data.rate_inr : 10;
          updatePetrolRatePreview();
        }
      } catch (err) {
        console.error('Failed to load petrol config:', err);
      }
      modal.classList.remove('d-none');
    }

    function closeConfigurePetrolModal() {
      const modal = document.getElementById('modalConfigurePetrol');
      if (modal) modal.classList.add('d-none');
    }

    async function submitConfigurePetrol(e) {
      if (e) e.preventDefault();
      const unit = 1.0;
      const rate = parseFloat(document.getElementById('cfgPetrolRateInr')?.value) || 0;
      if (rate < 0) {
        showToast('Rate cannot be negative.', true);
        return;
      }
      const cid = getActiveCompanyId();
      const btn = document.getElementById('btnSubmitPetrolConfig');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Saving...`;
      }
      try {
        const res = await fetch('/api/field-worker/petrol-rate-config', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ company_id: cid, unit_km: unit, rate_inr: rate })
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Petrol/Diesel allowance rate updated successfully!');
          closeConfigurePetrolModal();
          if (typeof loadFieldWorkers === 'function') loadFieldWorkers();
          if (typeof loadFieldSalaryReports === 'function') loadFieldSalaryReports();
          const activePane = sessionStorage.getItem('activeFieldTab');
          if (activePane === 'paneFieldPayslipPreview' && typeof generateFieldPayslip === 'function') {
            generateFieldPayslip();
          }
        } else {
          showToast(data.error || 'Failed to update petrol rate configuration', true);
        }
      } catch (err) {
        showToast('Error saving petrol rate: ' + err.message, true);
      } finally {
        if (btn) {
          btn.disabled = false;
          btn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> <span>Save Configuration</span>`;
        }
      }
    }

    function closeFieldManualEntryModal() {
      const modal = document.getElementById('modalFieldManualEntry');
      if (modal) modal.classList.add('d-none');
    }

    function handleFwManualModeChange() {
      const mode = document.getElementById('inputFieldManualMode')?.value;
      const hrsInput = document.getElementById('inputFieldManualHours');
      if (!hrsInput) return;
      if (mode === 'Full Day') {
        hrsInput.value = '08:00';
      } else if (mode === 'Half Day') {
        hrsInput.value = '04:00';
      } else if (mode === 'Amount') {
        hrsInput.value = '00:00';
      }
    }

    async function submitFieldManualEntry(e) {
      e.preventDefault();
      const btn = document.getElementById('btnSubmitFwManual');
      if (btn) btn.disabled = true;

      const payload = {
        company_id: getActiveCompanyId(),
        employee_name: document.getElementById('inputFieldManualWorker')?.value,
        entry_date: document.getElementById('inputFieldManualDate')?.value,
        entry_type: document.getElementById('inputFieldManualEntryType')?.value || 'Add',
        mode: document.getElementById('inputFieldManualMode')?.value || 'Hours',
        hours: document.getElementById('inputFieldManualHours')?.value || '08:00',
        status: document.getElementById('inputFieldManualStatus')?.value || 'Proper',
        working_salary: document.getElementById('inputFieldManualSalary')?.value || '',
        reason: document.getElementById('inputFieldManualReason')?.value || ''
      };

      try {
        const res = await fetch('/api/field-worker/manual-entries', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Manual entry recorded successfully!');
          closeFieldManualEntryModal();
          await loadFieldManualEntries();
        } else {
          showToast(data.error || 'Failed to save entry', true);
        }
      } catch (err) {
        showToast('Network error: ' + err.message, true);
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function deleteFieldManualEntry(entryId) {
      if (!confirm('Are you sure you want to delete this field worker manual entry? This will adjust payroll calculations.')) {
        return;
      }
      try {
        const res = await fetch(`/api/field-worker/manual-entries/${encodeURIComponent(entryId)}`, {
          method: 'DELETE'
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Entry deleted successfully');
          await loadFieldManualEntries();
        } else {
          showToast(data.error || 'Failed to delete entry', true);
        }
      } catch (err) {
        showToast('Error deleting entry: ' + err.message, true);
      }
    }

    // =========================================================================
    // FIELD WORKER MODULE: PAYMENT ENTRY & ADVANCE CONTROLLER (STANDARDIZED & ISOLATED)
    // =========================================================================
    let paymentPage = 1;
    let paymentLimit = 10;
    let paymentTotal = 0;
    let paymentSearchTimer = null;

    let balancePage = 1;
    let balanceLimit = 10;
    let balanceTotal = 0;
    let balanceSearchTimer = null;

    function debouncePaymentSearch() {
      clearTimeout(paymentSearchTimer);
      paymentSearchTimer = setTimeout(() => {
        paymentPage = 1;
        loadFieldPayments();
      }, 300);
    }

    function changePaymentLimit(limitVal) {
      paymentLimit = parseInt(limitVal) || 10;
      paymentPage = 1;
      loadFieldPayments();
    }

    function changePaymentPage(delta) {
      const maxPages = Math.ceil(paymentTotal / paymentLimit) || 1;
      const newPage = paymentPage + delta;
      if (newPage >= 1 && newPage <= maxPages) {
        paymentPage = newPage;
        loadFieldPayments();
      }
    }

    async function loadFieldPayments() {
      const tbody = document.getElementById('fieldPaymentTableBody');
      if (!tbody) return;

      const cid = getActiveCompanyId();
      const emp = document.getElementById('filterPaymentEmployee')?.value || 'All';
      const sDate = document.getElementById('filterPaymentStartDate')?.value || '';
      const eDate = document.getElementById('filterPaymentEndDate')?.value || '';
      const amtFilter = document.getElementById('filterPaymentAmount')?.value || '';
      const bank = document.getElementById('filterPaymentBank')?.value || 'All';
      const pType = document.getElementById('filterPaymentType')?.value || 'All';
      const status = document.getElementById('filterPaymentStatus')?.value || 'All';
      const search = document.getElementById('paymentSearch')?.value || '';

      const params = new URLSearchParams({
        company_id: cid,
        employee: emp,
        start_date: sDate,
        end_date: eDate,
        bank: bank,
        payment_type: pType,
        status: status,
        search: (search || amtFilter),
        page: paymentPage,
        limit: paymentLimit
      });

      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#64748b; padding:24px;">
        <i class="fa-solid fa-spinner fa-spin" style="margin-right:6px; color:#2563eb;"></i> Loading payment records...
      </td></tr>`;

      try {
        const res = await fetch(`/api/field-worker/payments?${params.toString()}`);
        const data = await res.json();
        if (!data.success) {
          tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#ef4444; padding:20px;">${escapeHtml(data.error || 'Failed to load payments')}</td></tr>`;
          return;
        }

        paymentTotal = data.total || 0;
        renderFieldPaymentsTable(data.data || []);

        const info = document.getElementById('paymentTableInfo');
        if (info) {
          const start = paymentTotal === 0 ? 0 : ((paymentPage - 1) * paymentLimit + 1);
          const end = Math.min(paymentPage * paymentLimit, paymentTotal);
          info.textContent = `Showing ${start} to ${end} of ${paymentTotal} entries`;
        }

        const maxPages = Math.ceil(paymentTotal / paymentLimit) || 1;
        const prevBtn = document.getElementById('prevPaymentPageBtn');
        const nextBtn = document.getElementById('nextPaymentPageBtn');
        if (prevBtn) prevBtn.classList.toggle('disabled', paymentPage <= 1);
        if (nextBtn) nextBtn.classList.toggle('disabled', paymentPage >= maxPages);

      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#ef4444; padding:20px;">Network error: ${escapeHtml(err.message)}</td></tr>`;
      }
    }

    function renderFieldPaymentsTable(rows) {
      const tbody = document.getElementById('fieldPaymentTableBody');
      if (!tbody) return;

      if (!rows || rows.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="table-empty-message">No data available in table</td></tr>';
        return;
      }

      const isAdmin = (CURRENT_USER_ROLE === 'super_admin' || CURRENT_USER_ROLE === 'company_admin' || CURRENT_USER_ROLE === 'admin');

      tbody.innerHTML = rows.map(r => {
        const payId = r.id || r._id || '';
        const amt = parseFloat(r.amount || 0.0);
        const reason = r.status || r.reason || 'Payment';
        let reasonBadge = `<span class="badge-neutral">${escapeHtml(reason)}</span>`;
        const rLow = reason.toLowerCase();

        if (rLow.includes('salary')) {
          reasonBadge = `<span class="badge-neutral" style="background:#eff6ff; color:#1d4ed8; border:1px solid #bfdbfe; font-weight:700;">Salary</span>`;
        } else if (rLow.includes('advance repayment')) {
          reasonBadge = `<span class="badge-neutral" style="background:#fef3c7; color:#92400e; border:1px solid #fde68a; font-weight:700;">Advance Repayment</span>`;
        } else if (rLow.includes('advance')) {
          reasonBadge = `<span class="badge-neutral" style="background:#fffbeb; color:#b45309; border:1px solid #fde68a; font-weight:700;">Advance Payment</span>`;
        } else if (rLow.includes('incentive')) {
          reasonBadge = `<span class="badge-neutral" style="background:#f0fdf4; color:#15803d; border:1px solid #bbf7d0; font-weight:700;">Incentive</span>`;
        } else if (rLow.includes('allowance')) {
          reasonBadge = `<span class="badge-neutral" style="background:#f5f3ff; color:#6d28d9; border:1px solid #ddd6fe; font-weight:700;">Allowance</span>`;
        }

        const receiptHtml = r.receipt_filename
          ? `<a href="/static/uploads/receipts/${encodeURIComponent(r.receipt_filename)}" target="_blank" class="fw-btn fw-btn-neutral fw-btn-sm" style="padding:2px 8px; font-size:11px;" title="View Receipt"><i class="fa-solid fa-paperclip"></i> Receipt</a>`
          : `<span style="color:#94a3b8; font-size:12px;">-</span>`;

        return `<tr>
          <td style="font-size:11.5px; color:#64748b; white-space:nowrap;">${escapeHtml(r.timestamp || '-')}</td>
          <td style="font-weight:600; color:#0f172a;">${escapeHtml(r.employee_name || '')}</td>
          <td style="font-weight:600; white-space:nowrap;">${escapeHtml(r.payment_date || '')}</td>
          <td style="font-weight:700; color:#0f172a; white-space:nowrap;">₹ ${amt.toFixed(2)}</td>
          <td><span class="badge-neutral">${escapeHtml(r.bank || 'Cash')}</span></td>
          <td><span class="badge-neutral" style="background:#f8fafc; font-weight:600;">${escapeHtml(r.payment_type || 'UPI')}</span></td>
          <td>${reasonBadge}</td>
          <td>${receiptHtml}</td>
          ${isAdmin ? `
          <td style="text-align:center;">
            <button type="button" class="btn-action-icon btn-action-delete" onclick="deleteFieldPayment('${escapeHtml(payId)}')" title="Delete Record">
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </td>` : ''}
        </tr>`;
      }).join('');
    }

    function openFieldPaymentModal() {
      const modal = document.getElementById('paymentModalOverlay');
      const form = document.getElementById('paymentForm');
      if (form) form.reset();
      const dInput = document.getElementById('paymentDate');
      if (dInput) dInput.value = new Date().toISOString().split('T')[0];
      if (modal) modal.classList.add('active');
    }

    function closeFieldPaymentModal() {
      const modal = document.getElementById('paymentModalOverlay');
      if (modal) modal.classList.remove('active');
    }

    async function submitFieldPayment(e) {
      e.preventDefault();
      const btn = document.getElementById('btnSavePayment');
      if (btn) btn.disabled = true;

      const form = document.getElementById('paymentForm');
      const formData = new FormData(form);
      formData.append('company_id', getActiveCompanyId());

      try {
        const res = await fetch('/api/field-worker/payments', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Payment recorded successfully!');
          closeFieldPaymentModal();
          await loadFieldPayments();
        } else {
          showToast(data.error || 'Failed to record payment', true);
        }
      } catch (err) {
        showToast('Network error: ' + err.message, true);
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    function openFieldAdvanceModal() {
      const modal = document.getElementById('modalFieldAdvanceEntry');
      const form = document.getElementById('formFieldAdvanceEntry');
      if (form) form.reset();
      const dInput = document.getElementById('advDate');
      if (dInput) dInput.value = new Date().toISOString().split('T')[0];
      if (modal) modal.classList.add('active');
    }

    function closeFieldAdvanceModal() {
      const modal = document.getElementById('modalFieldAdvanceEntry');
      if (modal) modal.classList.remove('active');
    }

    async function submitFieldAdvance(e) {
      e.preventDefault();
      const btn = document.getElementById('btnSaveAdvance');
      if (btn) btn.disabled = true;

      const payload = {
        company_id: getActiveCompanyId(),
        employee_name: document.getElementById('advEmployee')?.value,
        amount: document.getElementById('advAmount')?.value,
        repayment_amount: document.getElementById('advRepayment')?.value,
        notes: document.getElementById('advNotes')?.value
      };

      try {
        const res = await fetch('/api/field-worker/advances', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Advance recorded successfully!');
          closeFieldAdvanceModal();
        closeConfigurePetrolModal();
          await loadFieldPayments();
        } else {
          showToast(data.error || 'Failed to record advance', true);
        }
      } catch (err) {
        showToast('Network error: ' + err.message, true);
      } finally {
        if (btn) btn.disabled = false;
      }
    }

    async function deleteFieldPayment(paymentId) {
      if (!confirm('Are you sure you want to delete this payment record?')) return;
      try {
        const res = await fetch(`/api/field-worker/payments/${encodeURIComponent(paymentId)}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
          showToast(data.message || 'Payment deleted successfully');
          await loadFieldPayments();
        } else {
          showToast(data.error || 'Failed to delete payment', true);
        }
      } catch (err) {
        showToast('Error deleting payment: ' + err.message, true);
      }
    }

    // Advance Summary Modal Handlers
    function openFieldAdvanceSummaryModal() {
      const modal = document.getElementById('modalFieldAdvanceSummary');
      if (modal) {
        modal.classList.add('active');
        balancePage = 1;
        loadFieldBalanceReport();
      }
    }

    function closeFieldAdvanceSummaryModal() {
      const modal = document.getElementById('modalFieldAdvanceSummary');
      if (modal) modal.classList.remove('active');
    }

    function debounceFieldBalanceSearch() {
      clearTimeout(balanceSearchTimer);
      balanceSearchTimer = setTimeout(() => {
        balancePage = 1;
        loadFieldBalanceReport();
      }, 300);
    }

    function changeBalancePage(delta) {
      const maxPages = Math.ceil(balanceTotal / balanceLimit) || 1;
      const newPage = balancePage + delta;
      if (newPage >= 1 && newPage <= maxPages) {
        balancePage = newPage;
        loadFieldBalanceReport();
      }
    }

    async function loadFieldBalanceReport() {
      const tbody = document.getElementById('fieldBalanceTableBody');
      if (!tbody) return;

      const cid = getActiveCompanyId();
      const emp = document.getElementById('filterBalanceEmployee')?.value || 'All';
      const search = document.getElementById('balanceSearch')?.value.trim() || '';

      const params = new URLSearchParams({
        company_id: cid,
        employee: emp,
        search: search,
        page: balancePage,
        limit: balanceLimit
      });

      tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#64748b; padding:20px;"><i class="fa-solid fa-spinner fa-spin" style="margin-right:6px;"></i> Loading advance ledger...</td></tr>`;

      try {
        const res = await fetch(`/api/field-worker/balance-report?${params.toString()}`);
        const data = await res.json();
        if (!data.success) {
          tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#ef4444; padding:16px;">${escapeHtml(data.error || 'Failed to load report')}</td></tr>`;
          return;
        }

        balanceTotal = data.total || 0;
        document.getElementById('summaryTotalAdvance').innerText = parseFloat(data.total_advance || 0).toFixed(2);
        document.getElementById('summaryTotalPayment').innerText = parseFloat(data.total_payment !== undefined ? data.total_payment : data.total_repayment || 0).toFixed(2);
        document.getElementById('summaryBalanceAmount').innerText = parseFloat(data.balance_amount || 0).toFixed(2);

        if (!data.data || data.data.length === 0) {
          tbody.innerHTML = '<tr><td colspan="6" class="table-empty-message">No data available in table</td></tr>';
          document.getElementById('balanceTableInfo').innerText = 'Showing 0 to 0 of 0 entries';
          document.getElementById('prevBalancePageBtn')?.classList.add('disabled');
          document.getElementById('nextBalancePageBtn')?.classList.add('disabled');
          return;
        }

        const startIdx = (balancePage - 1) * balanceLimit + 1;
        const endIdx = Math.min(balancePage * balanceLimit, balanceTotal);
        document.getElementById('balanceTableInfo').innerText = `Showing ${startIdx} to ${endIdx} of ${balanceTotal} entries`;

        const prevBtn = document.getElementById('prevBalancePageBtn');
        const nextBtn = document.getElementById('nextBalancePageBtn');
        if (prevBtn) prevBtn.classList.toggle('disabled', balancePage <= 1);
        if (nextBtn) nextBtn.classList.toggle('disabled', endIdx >= balanceTotal);

        tbody.innerHTML = data.data.map(r => {
          const payAmt = r.payment_amount !== undefined ? r.payment_amount : (r.advance_repayment_amount || 0);
          return `<tr>
            <td style="white-space: nowrap;">${escapeHtml(r.timestamp || '')}</td>
            <td style="font-weight: 600;">${escapeHtml(r.name || '')}</td>
            <td style="white-space: nowrap;">${escapeHtml(r.date || '')}</td>
            <td>₹ ${parseFloat(r.advance_amount || 0).toFixed(2)}</td>
            <td>₹ ${parseFloat(payAmt || 0).toFixed(2)}</td>
            <td style="font-weight: 700; color: #0d6efd;">₹ ${parseFloat(r.balance_amount || 0).toFixed(2)}</td>
          </tr>`;
        }).join('');

      } catch (err) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; color:#ef4444; padding:16px;">Network error: ${escapeHtml(err.message)}</td></tr>`;
      }
    }

    function exportFieldPaymentExcel() {
      const cid = getActiveCompanyId();
      const emp = document.getElementById('filterPaymentEmployee')?.value || 'All';
      window.location.href = `/api/field-worker/payments?company_id=${encodeURIComponent(cid)}&employee=${encodeURIComponent(emp)}&limit=10000`;
    }

    function exportFieldPaymentPdf() {
      printFieldPaymentTable();
    }

    function printFieldPaymentTable() {
      const printSec = document.getElementById('printablePaymentSection');
      if (!printSec) return;
      const win = window.open('', '_blank');
      win.document.write(`<html><head><title>Payment Management Ledger</title>
        <link rel="stylesheet" href="/static/css/style.css">
        <style>body{padding:20px; font-family:sans-serif;} table{width:100%; border-collapse:collapse;} th,td{border:1px solid #cbd5e1; padding:8px; font-size:12px;}</style>
      </head><body>${printSec.innerHTML}</body></html>`);
      win.document.close();
      win.focus();
      setTimeout(() => { win.print(); win.close(); }, 500);
    }

    // =========================================================================
    // FIELD WORKER MODULE: PAYSLIP PREVIEW 8-TEMPLATE ENGINE & COLOR THEMES
    // =========================================================================
    const PAYSLIP_TEMPLATES = {
      template_1: 'Modern Executive',
      template_2: 'Modern Streamlined',
      template_3: 'Premium Executive',
      template_4: 'Classic Corporate Grid',
      template_5: 'Modern Minimalist Card',
      template_6: 'Professional Elegant',
      template_7: 'Mint Corporate Summary',
      template_8: 'Wave Modern Executive'
    };

    const COLOR_PALETTES = {
      navy: {
        id: 'navy',
        name: 'Navy Classic',
        primary: '#1b3b5f',
        dark: '#0f233a',
        tint: '#f0f5fa',
        border: '#cbd5e1',
        text_dark: '#0f233a',
        light_badge: '#dbeafe'
      },
      emerald: {
        id: 'emerald',
        name: 'Forest Emerald',
        primary: '#0f5132',
        dark: '#0a3622',
        tint: '#e9f7ef',
        border: '#a3cfbb',
        text_dark: '#0a3622',
        light_badge: '#d1fae5'
      },
      burgundy: {
        id: 'burgundy',
        name: 'Burgundy Wine',
        primary: '#5c1d48',
        dark: '#3f1331',
        tint: '#f9edf4',
        border: '#d8b4cb',
        text_dark: '#3f1331',
        light_badge: '#fce7f3'
      }
    };

    let currentTemplate = localStorage.getItem('argus_fw_payslip_template') || 'template_1';
    let currentTheme = localStorage.getItem('argus_fw_payslip_theme') || 'navy';
    let modalTempTemplate = currentTemplate;
    let modalTempTheme = currentTheme;
    let lastPayslipData = null;

    function initFieldPayslipPreview() {
      const mInput = document.getElementById('selectPayslipMonth');
      if (mInput && !mInput.value) {
        const today = new Date();
        const curY = today.getFullYear();
        const curM = String(today.getMonth() + 1).padStart(2, '0');
        mInput.value = `${curY}-${curM}`;
      }
      applyTemplateAndTheme(currentTemplate, currentTheme);
      initTemplateModalListeners();
      // User Requirement 1: Do NOT auto-generate payslip on tab click. Only generate when user clicks the GENERATE button.
    }

    function initTemplateModalListeners() {
      const modal = document.getElementById('templateModal');
      const btnClose = document.getElementById('btnCloseTemplateModal');
      const btnCancel = document.getElementById('btnCancelTemplateModal');
      const btnApply = document.getElementById('btnApplyTemplate');

      if (btnClose) btnClose.onclick = closeTemplateModal;
      if (btnCancel) btnCancel.onclick = closeTemplateModal;
      if (modal) {
        modal.onclick = function (e) {
          if (e.target === modal) closeTemplateModal();
        };
      }

      document.querySelectorAll('#templateModal .tmpl-card').forEach(card => {
        card.onclick = function () {
          const tmpl = this.dataset.template;
          if (tmpl) {
            modalTempTemplate = tmpl;
            syncModalUI();
          }
        };
      });

      document.querySelectorAll('#templateModal .swatch-circle').forEach(swatch => {
        swatch.onclick = function (e) {
          e.stopPropagation();
          const tmpl = this.dataset.template;
          const th = this.dataset.theme;
          if (tmpl) modalTempTemplate = tmpl;
          if (th) modalTempTheme = th;
          syncModalUI();
        };
      });

      if (btnApply) {
        btnApply.onclick = function () {
          currentTemplate = modalTempTemplate;
          currentTheme = modalTempTheme;
          localStorage.setItem('argus_fw_payslip_template', currentTemplate);
          localStorage.setItem('argus_fw_payslip_theme', currentTheme);
          applyTemplateAndTheme(currentTemplate, currentTheme);
          closeTemplateModal();
        };
      }

      const btnBack = document.getElementById('btnBackToGenerate');
      if (btnBack) {
        btnBack.onclick = function () {
          document.getElementById('payslipDocumentCard')?.classList.add('d-none');
          document.getElementById('payslipSelectionCard')?.classList.remove('d-none');
        };
      }

      const btnPrint = document.getElementById('btnPrintPayslip');
      if (btnPrint) {
        btnPrint.onclick = printFieldPayslipDoc;
      }

      const btnPdf = document.getElementById('btnPdfPayslip');
      if (btnPdf) {
        btnPdf.onclick = downloadFieldPayslipPdf;
      }
    }

    function openTemplateModal() {
      modalTempTemplate = currentTemplate;
      modalTempTheme = currentTheme;
      syncModalUI();
      const modal = document.getElementById('templateModal');
      if (modal) modal.style.display = 'flex';
    }

    function closeTemplateModal() {
      const modal = document.getElementById('templateModal');
      if (modal) modal.style.display = 'none';
    }

    function syncModalUI() {
      const palette = COLOR_PALETTES[modalTempTheme] || COLOR_PALETTES['navy'];

      document.querySelectorAll('#templateModal .tmpl-card').forEach(card => {
        const tmpl = card.dataset.template;
        const tag = card.querySelector('.active-tag');
        if (tmpl === modalTempTemplate) {
          card.classList.add('active-card');
          if (tag) tag.style.display = 'inline-block';
        } else {
          card.classList.remove('active-card');
          if (tag) tag.style.display = 'none';
        }

        const preview = card.querySelector('.tmpl-mini-mockup');
        if (preview) {
          preview.style.setProperty('--mock-primary', palette.primary);
          preview.style.setProperty('--mock-dark', palette.dark);
          preview.style.setProperty('--mock-tint', palette.tint);
          preview.style.setProperty('--mock-border', palette.border);
          preview.style.setProperty('--mock-light-badge', palette.light_badge);
          preview.style.setProperty('--mock-text-dark', palette.text_dark);
        }

        card.querySelectorAll('.swatch-circle').forEach(swatch => {
          if (swatch.dataset.theme === modalTempTheme) {
            swatch.classList.add('active-swatch');
          } else {
            swatch.classList.remove('active-swatch');
          }
        });
      });

      const tmplTitle = PAYSLIP_TEMPLATES[modalTempTemplate] || 'Modern Executive';
      const summaryTxt = document.getElementById('modalSummaryTxt');
      if (summaryTxt) {
        summaryTxt.innerText = `${tmplTitle} • ${palette.name}`;
      }
    }

    function applyTemplateAndTheme(tmpl, themeKey) {
      const palette = COLOR_PALETTES[themeKey] || COLOR_PALETTES['navy'];
      const doc = document.getElementById('printablePayslipDoc');
      if (doc) {
        doc.style.setProperty('--ps-primary', palette.primary);
        doc.style.setProperty('--ps-dark', palette.dark);
        doc.style.setProperty('--ps-tint', palette.tint);
        doc.style.setProperty('--ps-border', palette.border);
        doc.style.setProperty('--ps-text-dark', palette.text_dark);
        doc.style.setProperty('--ps-light-badge', palette.light_badge);
      }

      let activeLayoutId = 'tmplLayout_1_2';
      if (tmpl === 'template_3') activeLayoutId = 'tmplLayout_3';
      else if (tmpl === 'template_4') activeLayoutId = 'tmplLayout_4';
      else if (tmpl === 'template_5') activeLayoutId = 'tmplLayout_5';
      else if (tmpl === 'template_6') activeLayoutId = 'tmplLayout_6';
      else if (tmpl === 'template_7') activeLayoutId = 'tmplLayout_7';
      else if (tmpl === 'template_8') activeLayoutId = 'tmplLayout_8';

      document.querySelectorAll('#printablePayslipDoc .tmpl-layout-container').forEach(cnt => {
        if (cnt.id === activeLayoutId) {
          cnt.classList.add('active-layout');
          cnt.style.display = 'block';
        } else {
          cnt.classList.remove('active-layout');
          cnt.style.display = 'none';
        }
      });

      const signatory = document.getElementById('signatorySection');
      if (signatory) {
        signatory.style.display = (tmpl === 'template_1') ? 'flex' : 'none';
      }

      if (lastPayslipData) {
        populateAllLayouts(lastPayslipData);
      }
    }

    function formatCurrency(val) {
      try {
        const num = Number(val || 0);
        return '₹' + num.toLocaleString('en-IN');
      } catch (e) {
        return '₹' + (val || '0');
      }
    }

    function setAllText(selector, text) {
      document.querySelectorAll(selector).forEach(el => {
        el.innerText = text;
      });
    }

    async function generateFieldPayslip() {
      const worker = document.getElementById('selectPayslipEmployee')?.value || '';
      const month = document.getElementById('selectPayslipMonth')?.value || '';
      const cid = getActiveCompanyId();

      const loading = document.getElementById('fwPayslipLoadingIndicator');
      const docCard = document.getElementById('payslipDocumentCard');

      if (!worker) {
        showToast('Please select a field worker.', true);
        return;
      }

      if (loading) loading.classList.remove('d-none');
      if (docCard) docCard.classList.add('d-none');

      try {
        const res = await fetch(`/api/field-worker/payslip-preview-data?company_id=${encodeURIComponent(cid)}&employee_name=${encodeURIComponent(worker)}&month=${encodeURIComponent(month)}`);
        const data = await res.json();
        if (!data.success) {
          if (loading) loading.innerHTML = `<span style="color:#ef4444;">${escapeHtml(data.error || 'Failed to generate payslip')}</span>`;
          return;
        }

        lastPayslipData = data.payslip;
        populateAllLayouts(lastPayslipData);

        if (loading) loading.classList.add('d-none');
        if (docCard) docCard.classList.remove('d-none');

      } catch (err) {
        if (loading) loading.innerHTML = `<span style="color:#ef4444;">Network error: ${escapeHtml(err.message)}</span>`;
      }
    }

    function formatCurrency(val) {
      try {
        if (typeof val === 'string') {
          val = val.replace(/[₹?,\s]/g, '');
        }
        const num = Number(val || 0);
        return '₹' + num.toLocaleString('en-IN');
      } catch (e) {
        return '₹' + (val || '0');
      }
    }

    function populateAllLayouts(p) {
      if (!p) return;

      setAllText('.ps-emp-name', p.employee_name || '-');
      setAllText('.ps-emp-id', p.employee_id || '-');
      setAllText('.ps-emp-desig', p.designation || 'Field Executive');
      setAllText('.ps-emp-dept', p.department || 'Field Force');
      setAllText('.ps-emp-email', p.email_id || '-');
      setAllText('.ps-emp-phone', p.phone_number || p.mobile_number || '-');
      setAllText('.ps-salary-basis', p.salary_basis_label || 'Day-Based');

      let monthBadgeVal = 'OCT 2026';
      if (p.year_month) {
        const parts = p.year_month.split('-');
        if (parts.length === 2) {
          const d = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, 1);
          monthBadgeVal = d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' }).toUpperCase();
        }
      }
      setAllText('.ps-header-month', monthBadgeVal);

      const photoSrc = p.employee_photo_url || (p.employee_photo ? `/uploads/${p.employee_photo}` : '');
      document.querySelectorAll('.ps-emp-photo').forEach(img => {
        if (photoSrc) {
          img.src = photoSrc;
          img.style.display = 'block';
        } else {
          img.src = '';
          img.style.display = 'none';
        }
      });
      document.querySelectorAll('.ps-emp-photo-placeholder').forEach(ph => {
        ph.style.display = photoSrc ? 'none' : 'block';
      });

      const st = (p.salary_type || 'daily').toLowerCase();
      let rateLbl = 'DAY SALARY';
      let rateVal = formatCurrency(p.day_salary);
      if (st === 'hourly') {
        rateLbl = 'HOURS SALARY';
        rateVal = formatCurrency(p.hours_salary);
      } else if (st === 'half_day') {
        rateLbl = 'HALF DAY SALARY';
        rateVal = formatCurrency(p.half_day_salary);
      }
      setAllText('.ps-rate-lbl', rateLbl);
      setAllText('.ps-rate-val', rateVal);

      setAllText('.ps-shift-hours', p.shift_hours || '08:00');
      setAllText('.ps-working-days', `${p.working_days || 0} Days`);
      setAllText('.ps-working-hours', p.total_working_hours || '00:00');
      setAllText('.ps-total-days', `${p.total_days || 30} Days (${p.leave_days || 0} Leave)`);

      // 1. DYNAMIC EARNINGS ITEMS (User Requirement 2, 4 & 5)
      const earnItems = [];
      const baseSal = Number(p.base_attendance_pay !== undefined ? p.base_attendance_pay : (p.basic_salary || 0));
      earnItems.push({ label: 'Basic Salary', amount: baseSal });

      // Petrol / Travel Allowance in Earnings: only if earned from formula and not paid via payment entry
      const petrolEarn = Number(p.petrol_allowance_earnings !== undefined ? p.petrol_allowance_earnings : (p.petrol_allowance || 0));
      if (petrolEarn > 0) {
        earnItems.push({ label: 'Petrol/Diesel Allowance', amount: petrolEarn });
      }

      // User Requirement 3: Verified visits incentives added dynamically if completed verified visits (>0)
      const verifiedVisits = Number(p.verified_visits || 0);
      const visitIncAmt = Number(p.verified_visits_incentive !== undefined ? p.verified_visits_incentive : (p.visit_incentive_pay || 0));
      if (verifiedVisits > 0 && visitIncAmt > 0) {
        earnItems.push({ label: 'Verified Visits Incentives', amount: visitIncAmt });
      }

      // User Requirement 2: Incentives and Allowances strictly come from actual payment entries
      const incAmt = Number(p.incentive || 0);
      if (incAmt > 0) {
        earnItems.push({ label: 'Incentive', amount: incAmt });
      }

      const allowAmt = Number(p.allowance || 0);
      if (allowAmt > 0) {
        earnItems.push({ label: 'Allowance', amount: allowAmt });
      }

      const otherEarn = Number(p.other_earnings || 0);
      if (otherEarn > 0) {
        earnItems.push({ label: 'Other Earnings', amount: otherEarn });
      }

      const bonusAmt = Number(p.bonus || 0);
      if (bonusAmt > 0) {
        earnItems.push({ label: 'Bonus', amount: bonusAmt });
      }

      // 2. DYNAMIC DEDUCTIONS ITEMS (User Requirement 4 & 5)
      const dedItems = [];
      // If admin entered a payment entry for Petrol/Diesel Allowance, it is placed in Deductions!
      const petrolDed = Number(p.petrol_allowance_deduction !== undefined ? p.petrol_allowance_deduction : (p.petrol_allowance_paid || 0));
      if (petrolDed > 0) {
        dedItems.push({ label: 'Petrol/Diesel Allowance', amount: petrolDed });
      }

      const paidSal = Number(p.paid_salary || 0);
      if (paidSal > 0) {
        dedItems.push({ label: 'Paid Salary', amount: paidSal });
      }

      const advRepay = Number(p.advance_repayment || 0);
      if (advRepay > 0) {
        dedItems.push({ label: 'Advance Repayment', amount: advRepay });
      }

      const advPayDed = Number(p.advance_payment_deduction || 0);
      if (advPayDed > 0) {
        dedItems.push({ label: 'Advance Payment', amount: advPayDed });
      }

      const otherDed = Number(p.other_deductions || 0);
      if (otherDed > 0) {
        dedItems.push({ label: 'Other Deductions', amount: otherDed });
      }

      const totEarn = earnItems.reduce((acc, it) => acc + it.amount, 0);
      const totDed = dedItems.reduce((acc, it) => acc + it.amount, 0);
      const netPayAmt = Math.max(0, totEarn - totDed);

      // Render Dynamic Rows in Table Layouts (Layout 1 & 2, Layout 3, Layout 4)
      ['#tmplLayout_1_2', '#tmplLayout_3', '#tmplLayout_4'].forEach((selector, idx) => {
        const tb = document.querySelector(`${selector} tbody`);
        if (tb) {
          const maxR = Math.max(earnItems.length, dedItems.length, 1);
          let rowsHtml = '';
          for (let i = 0; i < maxR; i++) {
            const e = earnItems[i];
            const d = dedItems[i];
            const eLbl = e ? escapeHtml(e.label) : '';
            const eVal = e ? formatCurrency(e.amount) : '';
            let dLbl = d ? escapeHtml(d.label) : '';
            let dVal = d ? formatCurrency(d.amount) : '';
            if (!d && i === 0 && dedItems.length === 0) {
              dLbl = 'No Deductions';
              dVal = formatCurrency(0);
            }
            if (idx === 2) { // Layout 4 styling
              rowsHtml += `<tr>
                <td>${eLbl}</td>
                <td style="text-align: right; font-weight: 700;">${eVal}</td>
                <td>${dLbl}</td>
                <td style="text-align: right; font-weight: 700;">${dVal}</td>
              </tr>`;
            } else {
              rowsHtml += `<tr>
                <td style="width: 28%;">${eLbl}</td>
                <td class="val-cell" style="width: 22%;">${eVal}</td>
                <td style="width: 28%; border-left: 1px solid #e2e8f0;">${dLbl}</td>
                <td class="val-cell" style="width: 22%;">${dVal}</td>
              </tr>`;
            }
          }
          if (idx === 1) { // Layout 3 total row
            rowsHtml += `<tr class="total-row">
              <td style="color: var(--ps-primary);">TOTAL EARNINGS</td>
              <td class="val-cell ps-tot-earn" style="color: var(--ps-primary);">${formatCurrency(totEarn)}</td>
              <td style="border-left: 1px solid var(--ps-border); color: #1a2936;">TOTAL DEDUCTIONS</td>
              <td class="val-cell ps-tot-ded" style="color: #1a2936;">${formatCurrency(totDed)}</td>
            </tr>`;
          } else if (idx === 2) { // Layout 4 total row
            rowsHtml += `<tr class="tot-row">
              <td>TOTAL EARNINGS</td>
              <td style="text-align: right; font-weight: 800; color: var(--ps-primary);" class="ps-tot-earn">${formatCurrency(totEarn)}</td>
              <td>TOTAL DEDUCTIONS</td>
              <td style="text-align: right; font-weight: 800; color: var(--ps-primary);" class="ps-tot-ded">${formatCurrency(totDed)}</td>
            </tr>`;
          } else { // Layout 1 & 2 total row
            rowsHtml += `<tr class="total-row">
              <td>TOTAL EARNINGS</td>
              <td class="val-cell ps-tot-earn">${formatCurrency(totEarn)}</td>
              <td style="border-left: 1px solid var(--ps-border);">TOTAL DEDUCTIONS</td>
              <td class="val-cell ps-tot-ded">${formatCurrency(totDed)}</td>
            </tr>`;
          }
          tb.innerHTML = rowsHtml;
        }
      });

      // Render Dynamic Rows in Card Layouts (Layout 5, 6, 7, 8)
      ['5', '6', '7', '8'].forEach(num => {
        const eBox = document.getElementById('psEarnBox_' + num);
        const dBox = document.getElementById('psDedBox_' + num);
        if (eBox) {
          eBox.innerHTML = earnItems.map(it => `
            <div style="display: flex; justify-content: space-between; padding: 4px 12px; border-bottom: 1px solid #f8fafc;">
              <span>${escapeHtml(it.label)}</span><span style="font-weight: 700;">${formatCurrency(it.amount)}</span>
            </div>
          `).join('');
        }
        if (dBox) {
          if (dedItems.length > 0) {
            dBox.innerHTML = dedItems.map(it => `
              <div style="display: flex; justify-content: space-between; padding: 4px 12px; border-bottom: 1px solid #f8fafc;">
                <span>${escapeHtml(it.label)}</span><span style="font-weight: 700;">${formatCurrency(it.amount)}</span>
              </div>
            `).join('');
          } else {
            dBox.innerHTML = `
              <div style="display: flex; justify-content: space-between; padding: 4px 12px; color: #94a3b8;">
                <span>No Deductions</span><span>${formatCurrency(0)}</span>
              </div>
            `;
          }
        }
      });

      setAllText('.ps-tot-earn', formatCurrency(totEarn));
      setAllText('.ps-tot-ded', formatCurrency(totDed));
      setAllText('.ps-net-pay', formatCurrency(netPayAmt));
      setAllText('.ps-net-words', p.net_pay_in_words || 'Zero Rupees Only');

      if (p.company_name) setAllText('.ps-comp-name', p.company_name.toUpperCase());
      if (p.company_address) setAllText('.ps-comp-addr', p.company_address.toUpperCase());
      if (p.company_gstin) setAllText('.ps-comp-gstin', 'GSTIN: ' + p.company_gstin.toUpperCase());
    }

    function downloadFieldPayslipPdf() {
      const worker = document.getElementById('selectPayslipEmployee')?.value || '';
      const month = document.getElementById('selectPayslipMonth')?.value || '';
      const cid = getActiveCompanyId();
      if (!worker) {
        showToast('Please select a field worker.', true);
        return;
      }
      window.location.href = `/api/field-worker/payslip-pdf?company_id=${encodeURIComponent(cid)}&employee_name=${encodeURIComponent(worker)}&month=${encodeURIComponent(month)}&template=${encodeURIComponent(currentTemplate)}&theme=${encodeURIComponent(currentTheme)}`;
    }

    function printFieldPayslipDoc() {
      const doc = document.getElementById('printablePayslipDoc');
      if (!doc) return;
      const win = window.open('', '_blank');
      const palette = COLOR_PALETTES[currentTheme] || COLOR_PALETTES['navy'];
      win.document.write(`<html><head><title>Payslip Preview</title>
        <link rel="stylesheet" href="/static/css/style.css">
        <style>
          :root {
            --ps-primary: ${palette.primary};
            --ps-dark: ${palette.dark};
            --ps-tint: ${palette.tint};
            --ps-border: ${palette.border};
            --ps-text-dark: ${palette.text_dark};
            --ps-light-badge: ${palette.light_badge};
          }
          body { padding: 20px; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #fff; }
          .payslip-doc { border: none !important; box-shadow: none !important; max-width: 820px; margin: 0 auto; }
          .tmpl-layout-container { display: none; }
          .tmpl-layout-container.active-layout { display: block !important; }
          @media print {
            body { padding: 0; }
            .btn-action-view { display: none !important; }
          }
        </style>
      </head><body><div class="payslip-doc">${doc.innerHTML}</div></body></html>`);
      win.document.close();
      win.focus();
      setTimeout(() => { win.print(); win.close(); }, 600);
    }

    // Dismiss modals on Escape key or backdrop click
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        closeProductDropdown();
        closeVisitAudioModal();
        closeVisitTranscriptDocModal();
        closeRegisterWorkerModal();
        closeAddLeadModal();
        closeEditLeadModal();
        closeFwLeaveActionModal();
        closeApplyFwLeaveModal();
        closeApplyFwPermissionModal();
        closeFieldPayslipModal();
        closeFieldManualEntryModal();
        closeFieldPaymentModal();
        closeFieldAdvanceModal();
        closeConfigurePetrolModal();
      }
    });

    document.addEventListener('click', (e) => {
      if (e.target && e.target.id === 'registerWorkerModalBackdrop') {
        closeRegisterWorkerModal();
      }
      if (e.target && e.target.id === 'addLeadModalBackdrop') {
        closeAddLeadModal();
      }
      if (e.target && e.target.id === 'warehouseSettingsModalBackdrop') {
        closeWarehouseSettingsModal();
      }
      if (e.target && e.target.id === 'editLeadModalBackdrop') {
        closeEditLeadModal();
      }
      if (e.target && e.target.id === 'visitAudioModalBackdrop') {
        closeVisitAudioModal();
      }
      if (e.target && e.target.id === 'visitTranscriptDocModalBackdrop') {
        closeVisitTranscriptDocModal();
      }
      if (e.target && e.target.id === 'resolveIncidentModalBackdrop') {
        closeResolveIncidentModal();
      }
      if (e.target && e.target.id === 'fwLeaveActionModalBackdrop') {
        closeFwLeaveActionModal();
      }
      if (e.target && e.target.id === 'applyFwLeaveModalBackdrop') {
        closeApplyFwLeaveModal();
      }
      if (e.target && e.target.id === 'applyFwPermissionModalBackdrop') {
        closeApplyFwPermissionModal();
      }
      if (e.target && e.target.id === 'fwPayslipModalBackdrop') {
        closeFieldPayslipModal();
      }
      if (e.target && e.target.id === 'modalFieldManualEntry') {
        closeFieldManualEntryModal();
      }
      if (e.target && e.target.id === 'modalFieldPaymentEntry') {
        closeFieldPaymentModal();
      }
      if (e.target && e.target.id === 'modalFieldAdvanceEntry') {
        closeFieldAdvanceModal();
      }
      if (e.target && e.target.id === 'modalConfigurePetrol') {
        closeConfigurePetrolModal();
      }
    });

    document.addEventListener('DOMContentLoaded', () => {
      initCollapsibleSidebar();
      initFieldMaps();
      initAiDetourMonitoring();
      initTerminalListeners();
      loadWarehouseProducts();

      // Restore active tab from hash or sessionStorage with role isolation
      const hashTab = (window.location.hash || '').replace('#', '');
      let defaultTab = (CURRENT_USER_ROLE === 'employee') ? 'paneFieldPunch' : 'paneFieldDashboard';
      if (CURRENT_USER_ROLE === 'employee' && Array.isArray(CURRENT_ALLOWED_TABS) && CURRENT_ALLOWED_TABS.length > 0) {
        if (!CURRENT_ALLOWED_TABS.includes(defaultTab)) {
          defaultTab = CURRENT_ALLOWED_TABS[0];
        }
      }
      let savedTab = hashTab || sessionStorage.getItem('activeFieldTab') || defaultTab;
      if (CURRENT_USER_ROLE === 'employee') {
        if (savedTab === 'paneRegisterWorkers' || savedTab === 'paneFieldDashboard' || savedTab === 'paneFieldLeaves' || savedTab === 'paneFieldManualEntry' || savedTab === 'paneFieldPaymentEntry' || (Array.isArray(CURRENT_ALLOWED_TABS) && !CURRENT_ALLOWED_TABS.includes(savedTab))) {
          savedTab = defaultTab;
        }
      } else {
        if (savedTab === 'paneFieldPunch' || savedTab === 'paneAssignLocations' || savedTab === 'paneFieldEmployeeLeaves') {
          savedTab = 'paneFieldDashboard';
        }
      }
      if (savedTab && document.getElementById(savedTab)) {
        switchFieldTab(savedTab);
      } else {
        switchFieldTab(defaultTab);
      }

      // Background periodic polling every 20s (pauses when browser tab is hidden)
      autoRefreshTimer = setInterval(function () {
        if (!document.hidden) {
          refreshOverviewState();
        }
      }, 20000);
      document.addEventListener('visibilitychange', function () {
        if (!document.hidden && typeof refreshOverviewState === 'function') {
          refreshOverviewState();
        }
      });
    });
