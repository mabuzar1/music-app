/* ==========================================================================
   Resona frontend logic
   - Records audio via MediaRecorder + visualizes it live via AnalyserNode
   - Supports drag-and-drop / click-to-browse file upload as an alternative
   - Sends the clip to /api/identify and renders the result card
   ========================================================================== */

const RECORD_SECONDS = 12; // matches config.RECORD_SECONDS on the backend

const micButton = document.getElementById("micButton");
const stage = document.getElementById("stage");
const statusText = document.getElementById("statusText");
const waveformCanvas = document.getElementById("waveformCanvas");
const canvasCtx = waveformCanvas.getContext("2d");

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const filePreview = document.getElementById("filePreview");
const filePreviewAudio = document.getElementById("filePreviewAudio");
const filePreviewName = document.getElementById("filePreviewName");
const analyzeUploadBtn = document.getElementById("analyzeUploadBtn");

const progressTrack = document.getElementById("progressTrack");
const resultCard = document.getElementById("resultCard");
const toast = document.getElementById("toast");

let audioContext, analyser, animationFrameId;
let pendingUploadFile = null;

/* ---------------------------------------------------------------------- */
/* Toast helper                                                            */
/* ---------------------------------------------------------------------- */
function showToast(message, type = "info", duration = 3200) {
  toast.textContent = message;
  toast.className = `toast visible ${type}`;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    toast.classList.remove("visible");
  }, duration);
}

/* ---------------------------------------------------------------------- */
/* Waveform visualization                                                  */
/* ---------------------------------------------------------------------- */
function resizeCanvas() {
  const rect = waveformCanvas.getBoundingClientRect();
  waveformCanvas.width = rect.width * window.devicePixelRatio;
  waveformCanvas.height = rect.height * window.devicePixelRatio;
}

function drawWaveform() {
  if (!analyser) return;
  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);

  function render() {
    animationFrameId = requestAnimationFrame(render);
    analyser.getByteTimeDomainData(dataArray);

    const w = waveformCanvas.width;
    const h = waveformCanvas.height;
    canvasCtx.clearRect(0, 0, w, h);

    const centerX = w / 2;
    const centerY = h / 2;
    const baseRadius = h * 0.22;

    canvasCtx.beginPath();
    const points = 64;
    for (let i = 0; i < points; i++) {
      const dataIndex = Math.floor((i / points) * bufferLength);
      const amp = (dataArray[dataIndex] - 128) / 128; // -1..1
      const radius = baseRadius + amp * (h * 0.14);
      const angle = (i / points) * Math.PI * 2;
      const x = centerX + Math.cos(angle) * radius;
      const y = centerY + Math.sin(angle) * radius;
      if (i === 0) canvasCtx.moveTo(x, y);
      else canvasCtx.lineTo(x, y);
    }
    canvasCtx.closePath();

    const gradient = canvasCtx.createLinearGradient(0, 0, w, h);
    gradient.addColorStop(0, "#8B5CF6");
    gradient.addColorStop(1, "#22D3EE");
    canvasCtx.strokeStyle = gradient;
    canvasCtx.lineWidth = 2 * window.devicePixelRatio;
    canvasCtx.stroke();
  }
  render();
}

function stopWaveform() {
  if (animationFrameId) cancelAnimationFrame(animationFrameId);
  canvasCtx.clearRect(0, 0, waveformCanvas.width, waveformCanvas.height);
}

/* ---------------------------------------------------------------------- */
/* Recording flow                                                          */
/* ---------------------------------------------------------------------- */
micButton.addEventListener("click", startRecording);

async function startRecording() {
  hideResult();
  micButton.disabled = true;

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

    resizeCanvas();
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(stream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);

    stage.classList.add("listening");
    drawWaveform();

    const mediaRecorder = new MediaRecorder(stream);
    const chunks = [];
    mediaRecorder.ondataavailable = (e) => chunks.push(e.data);

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      stage.classList.remove("listening");
      stopWaveform();
      if (audioContext) audioContext.close();

      const audioBlob = new Blob(chunks, { type: "audio/webm" });
      await submitClip(audioBlob, "clip.webm");
    };

    mediaRecorder.start();

    let secondsLeft = RECORD_SECONDS;
    statusText.textContent = `Listening... ${secondsLeft}s`;
    const countdown = setInterval(() => {
      secondsLeft -= 1;
      if (secondsLeft > 0) {
        statusText.textContent = `Listening... ${secondsLeft}s`;
      } else {
        clearInterval(countdown);
      }
    }, 1000);

    setTimeout(() => mediaRecorder.stop(), RECORD_SECONDS * 1000);
  } catch (err) {
    showToast("Microphone access denied or unavailable.", "error");
    statusText.textContent = "Tap the button and play music nearby";
    micButton.disabled = false;
  }
}

/* ---------------------------------------------------------------------- */
/* Drag-and-drop / file upload flow                                        */
/* ---------------------------------------------------------------------- */
dropzone.addEventListener("click", () => fileInput.click());

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
  })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelected(file);
});
fileInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (file) handleFileSelected(file);
});

function handleFileSelected(file) {
  pendingUploadFile = file;
  filePreviewName.textContent = file.name;
  filePreviewAudio.src = URL.createObjectURL(file);
  filePreview.classList.add("visible");
  hideResult();
}

analyzeUploadBtn.addEventListener("click", () => {
  if (pendingUploadFile) submitClip(pendingUploadFile, pendingUploadFile.name);
});

/* ---------------------------------------------------------------------- */
/* Submit to backend + render results                                      */
/* ---------------------------------------------------------------------- */
async function submitClip(blobOrFile, filename) {
  progressTrack.classList.add("visible");
  statusText.textContent = "Analyzing audio...";
  micButton.disabled = true;

  const formData = new FormData();
  formData.append("audio", blobOrFile, filename);

  try {
    const response = await fetch("/api/identify", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();

    if (!response.ok) {
      showToast(data.error || "Something went wrong.", "error");
      statusText.textContent = "Tap the button and play music nearby";
      return;
    }

    renderResult(data);

    if (data.match) {
      showToast("Match found!", "success");
    } else {
      showToast("No match found in the library.", "error");
    }
    statusText.textContent = "Tap the button and play music nearby";
  } catch (err) {
    showToast("Could not reach the server.", "error");
    statusText.textContent = "Tap the button and play music nearby";
  } finally {
    progressTrack.classList.remove("visible");
    micButton.disabled = false;
  }
}

function hideResult() {
  resultCard.classList.remove("visible");
}

function formatDuration(seconds) {
  if (seconds == null) return "--";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function renderResult(data) {
  const badgeClass = data.match ? "found" : "not-found";
  const badgeLabel = data.match_status;

  const coverSrc = data.cover_url || null;

  resultCard.innerHTML = `
    <div class="result-header">
      ${
        coverSrc
          ? `<img class="cover-art" src="${coverSrc}" alt="Album cover" />`
          : `<div class="cover-art"></div>`
      }
      <div class="result-title-block">
        <p class="result-title">${data.match ? escapeHtml(data.title) : "No Match Found"}</p>
        <p class="result-artist">${data.match ? escapeHtml(data.artist) : "This clip did not match any song in the library"}</p>
        <span class="match-badge ${badgeClass}"><span class="dot"></span>${badgeLabel}</span>
      </div>
    </div>

    <div class="confidence-block">
      <div class="confidence-label">
        <span>Confidence Score</span>
        <span class="confidence-value" id="confValue">0%</span>
      </div>
      <div class="confidence-track">
        <div class="confidence-fill" id="confFill"></div>
      </div>
    </div>

    ${
      data.match
        ? `
    <div class="meta-grid">
      <div class="meta-item">
        <div class="meta-label">Album</div>
        <div class="meta-value">${escapeHtml(data.album)}</div>
      </div>
      <div class="meta-item">
        <div class="meta-label">Genre</div>
        <div class="meta-value">${escapeHtml(data.genre)}</div>
      </div>
      <div class="meta-item">
        <div class="meta-label">Duration</div>
        <div class="meta-value mono">${formatDuration(data.duration_seconds)}</div>
      </div>
      <div class="meta-item">
        <div class="meta-label">Recognition Time</div>
        <div class="meta-value mono">${data.recognition_time_ms} ms</div>
      </div>
    </div>`
        : `
    <div class="meta-grid">
      <div class="meta-item">
        <div class="meta-label">Recognition Time</div>
        <div class="meta-value mono">${data.recognition_time_ms} ms</div>
      </div>
    </div>`
    }
  `;

  resultCard.classList.add("visible");

  // Animate the confidence bar and number after the card is in the DOM
  requestAnimationFrame(() => {
    const pct = data.confidence_score || 0;
    document.getElementById("confFill").style.width = `${pct}%`;
    animateNumber(document.getElementById("confValue"), pct);
  });
}

function animateNumber(el, target) {
  const duration = 800;
  const start = performance.now();
  function step(now) {
    const progress = Math.min(1, (now - start) / duration);
    const value = (progress * target).toFixed(1);
    el.textContent = `${value}%`;
    if (progress < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

window.addEventListener("resize", resizeCanvas);
