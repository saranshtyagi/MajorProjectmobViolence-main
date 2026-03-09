const API_BASE_URL = "http://localhost:5000";

// -------- DOM Elements -------- //
const videoInput = document.getElementById("videoInput");
const uploadBtn = document.getElementById("uploadBtn");
const analyzeBtn = document.getElementById("analyzeBtn");
const fileNameLabel = document.getElementById("fileName");
const loader = document.getElementById("loader");
const errorText = document.getElementById("errorText");
const resultCard = document.getElementById("resultCard");
const resultLabel = document.getElementById("resultLabel");
const resultProb = document.getElementById("resultProb");
const resultReason = document.getElementById("resultReason");
const logList = document.getElementById("logList");
const liveStatusBadge = document.getElementById("liveStatusBadge");
const liveStatusText = document.getElementById("liveStatusText");
const lastPredictionTime = document.getElementById("lastPredictionTime");
const systemStatus = document.getElementById("systemStatus");

// Live feed elements
const liveStream = document.getElementById("liveStream");
const videoPlaceholder = document.getElementById("videoPlaceholder");
const startWebcamBtn = document.getElementById("startWebcamBtn");
const startSimBtn = document.getElementById("startSimBtn");
const simVideoInput = document.getElementById("simVideoInput");
const stopFeedBtn = document.getElementById("stopFeedBtn");

let selectedFile = null;
let livePollingInterval = null;
let lastLoggedTimestamp = null;

// -------- Helpers -------- //

function setLoading(isLoading) {
    loader.hidden = !isLoading;
    analyzeBtn.disabled = isLoading || !selectedFile;
    uploadBtn.disabled = isLoading;
}

function showError(msg) {
    errorText.hidden = false;
    errorText.textContent = msg;
}

function clearError() {
    errorText.hidden = true;
    errorText.textContent = "";
}

function addLogEntry(label, prob, reason) {
    const time = new Date().toLocaleTimeString();
    const isViolent = label === "violent";

    const emptyMsg = logList.querySelector(".log-empty");
    if (emptyMsg) emptyMsg.remove();

    const item = document.createElement("div");
    item.className = "log-item";

    const left = document.createElement("div");
    left.className = "log-label";

    const dot = document.createElement("span");
    dot.className = "dot " + (isViolent ? "dot-violent" : "dot-safe");

    const text = document.createElement("span");
    text.className = isViolent ? "log-label-violent" : "log-label-safe";
    text.textContent = isViolent
        ? `Violence detected (${prob.toFixed(2)})`
        : `Safe (${prob.toFixed(2)})`;

    left.appendChild(dot);
    left.appendChild(text);

    const reasonElem = document.createElement("small");
    reasonElem.className = "log-reason";
    reasonElem.textContent = reason || "";
    reasonElem.style.display = "block";
    reasonElem.style.color = "#888";
    reasonElem.style.fontSize = "0.75rem";
    reasonElem.style.marginTop = "2px";

    const timeElem = document.createElement("span");
    timeElem.className = "log-time";
    timeElem.textContent = time;

    const wrapper = document.createElement("div");
    wrapper.style.flex = "1";
    wrapper.appendChild(left);
    wrapper.appendChild(reasonElem);

    item.appendChild(wrapper);
    item.appendChild(timeElem);

    logList.prepend(item);
}

function updateLiveStatus(label, prob) {
    const isViolent = label === "violent";
    const dot = liveStatusBadge.querySelector(".dot");

    dot.classList.remove("dot-safe", "dot-violent");
    dot.classList.add(isViolent ? "dot-violent" : "dot-safe");

    liveStatusText.textContent = isViolent
        ? `Violence (${prob.toFixed(2)})`
        : `Safe (${prob.toFixed(2)})`;

    lastPredictionTime.textContent = new Date().toLocaleTimeString();
}

// -------- Live Feed Controls -------- //

function showStream() {
    liveStream.src = `${API_BASE_URL}/video_feed`;
    liveStream.style.display = "block";
    videoPlaceholder.style.display = "none";
    stopFeedBtn.disabled = false;
    systemStatus.textContent = "Live";
    systemStatus.style.background = "#22c55e";
    startLivePolling();
}

function hideStream() {
    liveStream.src = "";
    liveStream.style.display = "none";
    videoPlaceholder.style.display = "flex";
    stopFeedBtn.disabled = true;
    systemStatus.textContent = "Idle";
    systemStatus.style.background = "";
    stopLivePolling();
}

function startLivePolling() {
    if (livePollingInterval) clearInterval(livePollingInterval);
    livePollingInterval = setInterval(pollLiveResult, 3000);
}

function stopLivePolling() {
    if (livePollingInterval) {
        clearInterval(livePollingInterval);
        livePollingInterval = null;
    }
}

async function pollLiveResult() {
    try {
        const res = await fetch(`${API_BASE_URL}/live_result`);
        if (!res.ok) return;
        const data = await res.json();

        if (data.timestamp && data.timestamp !== lastLoggedTimestamp) {
            lastLoggedTimestamp = data.timestamp;
            const prob = data.probability || 0;
            const label = data.label || "non-violent";
            const reason = data.reason || "";

            updateLiveStatus(label, prob);
            addLogEntry(label, prob, reason);
        }
    } catch (err) {
        console.error("Polling error:", err);
    }
}

// Start Webcam
startWebcamBtn.addEventListener("click", async () => {
    try {
        startWebcamBtn.disabled = true;
        startWebcamBtn.textContent = "Starting...";
        const res = await fetch(`${API_BASE_URL}/start_webcam`, { method: "POST" });
        const data = await res.json();
        if (res.ok) {
            showStream();
        } else {
            alert(data.error || "Failed to start webcam");
        }
    } catch (err) {
        alert("Could not connect to backend. Is it running?");
    } finally {
        startWebcamBtn.disabled = false;
        startWebcamBtn.textContent = "📷 Start Webcam";
    }
});

// Start Simulation
startSimBtn.addEventListener("click", () => {
    simVideoInput.click();
});

simVideoInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    startSimBtn.disabled = true;
    startSimBtn.textContent = "Loading...";

    const formData = new FormData();
    formData.append("video", file);

    try {
        const res = await fetch(`${API_BASE_URL}/start_simulation`, {
            method: "POST",
            body: formData,
        });
        const data = await res.json();
        if (res.ok) {
            showStream();
        } else {
            alert(data.error || "Failed to start simulation");
        }
    } catch (err) {
        alert("Could not connect to backend.");
    } finally {
        startSimBtn.disabled = false;
        startSimBtn.textContent = "🎬 Simulate CCTV";
        simVideoInput.value = "";
    }
});

// Stop Feed
stopFeedBtn.addEventListener("click", async () => {
    try {
        await fetch(`${API_BASE_URL}/stop_feed`, { method: "POST" });
    } catch (err) {
        console.error(err);
    }
    hideStream();
});

// -------- Clip Upload & Analyze (Original Feature) -------- //

uploadBtn.addEventListener("click", () => {
    videoInput.click();
});

videoInput.addEventListener("change", (e) => {
    const files = e.target.files;
    if (!files || files.length === 0) {
        selectedFile = null;
        fileNameLabel.textContent = "No file selected";
        analyzeBtn.disabled = true;
        return;
    }
    selectedFile = files[0];
    fileNameLabel.textContent = selectedFile.name;
    analyzeBtn.disabled = false;
    clearError();
});

analyzeBtn.addEventListener("click", async () => {
    if (!selectedFile) {
        showError("Please select a video file first.");
        return;
    }

    clearError();
    setLoading(true);

    const formData = new FormData();
    formData.append("video", selectedFile);

    try {
        const res = await fetch(`${API_BASE_URL}/predict_clip`, {
            method: "POST",
            body: formData,
        });

        if (!res.ok) {
            const errText = await res.text();
            throw new Error(errText || "Server error");
        }

        const data = await res.json();
        const prob = data.probability;
        const label = data.label;
        const reason = data.reason || "";

        resultCard.hidden = false;
        resultLabel.textContent = label === "violent" ? "Violent" : "Non-violent";
        resultProb.textContent = prob.toFixed(3);
        if (resultReason) resultReason.textContent = reason;

        updateLiveStatus(label, prob);
        addLogEntry(label, prob, reason);
    } catch (err) {
        console.error(err);
        showError("Failed to analyze video. Check backend and try again.");
    } finally {
        setLoading(false);
    }
});