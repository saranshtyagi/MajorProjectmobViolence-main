# 🔴 Mob Violence Detection System

> A real-time AI-powered CCTV surveillance dashboard that detects mob violence in video footage using computer vision and a multimodal large language model.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python) ![Flask](https://img.shields.io/badge/Flask-2.x-black?logo=flask) ![Groq](https://img.shields.io/badge/Groq-LLaMA_4_Scout-orange) ![OpenCV](https://img.shields.io/badge/OpenCV-4.x-green?logo=opencv) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Data Flow](#data-flow)
- [Project Directory Structure](#project-directory-structure)
- [Component Breakdown](#component-breakdown)
- [API Reference](#api-reference)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Configuration](#configuration)
- [How the AI Analysis Works](#how-the-ai-analysis-works)
- [Frontend Dashboard](#frontend-dashboard)
- [Threading Model](#threading-model)
- [Versioning Notes](#versioning-notes)

---

## Overview

This project is a web-based security surveillance tool that uses Groq's API (running **Meta LLaMA 4 Scout 17B**, a multimodal vision model) to analyze video footage and classify it as **violent** or **non-violent** in near-real-time.

It supports two operational modes:
1. **Live Feed Mode** — continuously analyzes frames from a webcam or simulated CCTV video every 10 seconds, streaming the video back to the browser as MJPEG.
2. **Clip Analysis Mode** — one-off upload and analysis of a single video file.

---

## Features

- 📷 **Webcam live feed** with real-time violence detection
- 🎬 **CCTV simulation** by uploading a pre-recorded video file
- 📁 **Single clip analysis** with detailed probability output
- 🧠 **Multimodal LLM reasoning** — the model explains *why* it flagged footage
- 📊 **Live dashboard** with prediction log, confidence score, and status badge
- 🔄 **Polling-based result delivery** (frontend polls every 3 seconds)
- 🔒 **Thread-safe state management** for concurrent video capture and analysis

---

## System Architecture

```mermaid
graph TB
    subgraph Frontend["Frontend (Browser)"]
        UI["Dashboard UI\n(index.html / app.js / style.css)"]
        MJPEG["MJPEG Stream Display"]
        POLL["Result Polling\n(every 3 seconds)"]
        UPLOAD["Video Upload\n(clip or simulation)"]
    end

    subgraph Backend["Backend (Flask — server.py)"]
        FLASK["Flask HTTP Server :5000"]

        subgraph Routes["API Routes"]
            R1["/video_feed GET"]
            R2["/start_webcam POST"]
            R3["/start_simulation POST"]
            R4["/stop_feed POST"]
            R5["/live_result GET"]
            R6["/predict_clip POST"]
        end

        subgraph SharedState["Shared State (Thread-Safe)"]
            SS1["active_source\n{type, cap}"]
            SS2["live_result\n{label, prob, reason, timestamp}"]
        end

        subgraph BackgroundThread["Background Analysis Thread"]
            BT["live_analysis_loop()\ndaemon thread"]
        end

        subgraph VideoProcessing["Video Processing"]
            CV["OpenCV cv2.VideoCapture"]
            FE["Frame Extractor\n5 frames per analysis"]
            MJ["MJPEG Generator\n~30 FPS stream"]
        end
    end

    subgraph ExternalAPI["External API"]
        GROQ["Groq Cloud API\nmeta-llama/llama-4-scout-17b-16e-instruct"]
    end

    UI --> MJPEG
    UI --> POLL
    UI --> UPLOAD

    MJPEG -->|"GET /video_feed"| R1
    POLL -->|"GET /live_result"| R5
    UPLOAD -->|"POST /predict_clip"| R6
    UPLOAD -->|"POST /start_simulation"| R3
    UI -->|"POST /start_webcam"| R2
    UI -->|"POST /stop_feed"| R4

    R1 --> MJ
    R2 --> SS1
    R3 --> SS1
    R4 --> SS1
    R5 --> SS2
    R6 --> FE

    MJ --> CV
    BT --> CV
    CV --> SS1

    FE --> GROQ
    BT --> FE
    BT --> SS2

    GROQ -->|"JSON: label, probability, reason"| FE
```

---

## Data Flow

### Live Feed Mode

```mermaid
sequenceDiagram
    actor User
    participant Browser as Browser (Frontend)
    participant Flask as Flask Server
    participant OpenCV as OpenCV
    participant Groq as Groq API (LLaMA 4 Scout)

    User->>Browser: Click "Start Webcam" or upload simulation video
    Browser->>Flask: POST /start_webcam OR POST /start_simulation
    Flask->>OpenCV: cv2.VideoCapture(0) or VideoCapture(file)
    Flask-->>Browser: { status: "started" }

    Browser->>Flask: GET /video_feed (MJPEG stream)
    activate Flask
    loop Every frame (~30 FPS)
        Flask->>OpenCV: cap.read()
        OpenCV-->>Flask: Raw frame
        Flask-->>Browser: MJPEG frame bytes
    end
    deactivate Flask

    loop Every 10 seconds (background thread)
        Flask->>OpenCV: grab_live_frames() — 5 frames over ~2s
        OpenCV-->>Flask: 5 JPEG frames (base64)
        Flask->>Groq: POST — 5 frames + surveillance prompt
        Groq-->>Flask: { label, probability, reason }
        Flask->>Flask: Update live_result (thread-safe lock)
    end

    loop Every 3 seconds (frontend polling)
        Browser->>Flask: GET /live_result
        Flask-->>Browser: { label, probability, reason, timestamp }
        Browser->>Browser: Update dashboard badge + log
    end

    User->>Browser: Click "Stop Feed"
    Browser->>Flask: POST /stop_feed
    Flask->>OpenCV: cap.release()
```

### Clip Analysis Mode

```mermaid
sequenceDiagram
    actor User
    participant Browser as Browser (Frontend)
    participant Flask as Flask Server
    participant OpenCV as OpenCV
    participant Groq as Groq API (LLaMA 4 Scout)

    User->>Browser: Select video file + Click "Analyze"
    Browser->>Flask: POST /predict_clip (multipart/form-data)
    Flask->>Flask: Save to temp file (mkstemp)
    Flask->>OpenCV: cv2.VideoCapture(tmp_path)
    OpenCV-->>Flask: Video opened
    Flask->>Flask: extract_frames_from_video()\nSample 5 evenly-spaced frames
    Flask->>Flask: Encode frames as base64 JPEG
    Flask->>Groq: POST — 5 frames + surveillance prompt
    Groq-->>Flask: Raw JSON string
    Flask->>Flask: parse_groq_response()\nHandle single/multiple JSON objects
    Flask->>Flask: Delete temp file
    Flask-->>Browser: { probability, label, reason, raw_probs }
    Browser->>Browser: Display result card + update log
```

---

## Project Directory Structure

```
MajorProjectmobViolence-main-main/
│
├── backend/
│   └── server.py          # Core Flask application
│                          #   - All API route handlers
│                          #   - OpenCV frame extraction
│                          #   - Groq API integration
│                          #   - Background analysis thread
│                          #   - MJPEG stream generator
│                          #   - Thread-safe shared state
│
├── index.html             # Single-page dashboard UI
│                          #   - Live camera feed panel
│                          #   - Clip upload/analyze panel
│                          #   - Prediction log panel
│
├── app.js                 # Frontend JavaScript
│                          #   - DOM bindings
│                          #   - API fetch calls
│                          #   - Live polling loop (3s interval)
│                          #   - Result rendering & log management
│
├── style.css              # Dashboard CSS
│                          #   - Dark surveillance aesthetic
│                          #   - Status badges & video overlays
│                          #   - Responsive two-column layout
│
└── .gitignore
```

```mermaid
graph LR
    ROOT["📁 project root"]

    ROOT --> BE["📁 backend/"]
    ROOT --> FE_HTML["📄 index.html"]
    ROOT --> FE_JS["📄 app.js"]
    ROOT --> FE_CSS["📄 style.css"]
    ROOT --> GI["📄 .gitignore"]

    BE --> SRV["📄 server.py\nFlask app · Routes · OpenCV\nGroq integration · Threads"]

    FE_HTML -.->|"Defines structure of"| DASH["🖥️ Dashboard UI"]
    FE_JS -.->|"Drives logic of"| DASH
    FE_CSS -.->|"Styles"| DASH
```

---

## Component Breakdown

```mermaid
graph TD
    subgraph server.py
        CONFIG["⚙️ Config Constants\nNUM_FRAMES=5\nFRAME_HEIGHT/WIDTH=512\nTHRESHOLD=0.5\nANALYSIS_INTERVAL=10s"]

        subgraph State["🔒 Shared Mutable State"]
            LS["live_result dict\n+ live_result_lock"]
            AS["active_source dict\n+ active_source_lock"]
        end

        subgraph FrameUtils["🎞️ Frame Utilities"]
            EFV["extract_frames_from_video()\nEvenly-spaced frames\nfor clip analysis"]
            GLF["grab_live_frames()\n5 frames over ~2 seconds\nfor live analysis"]
        end

        subgraph GroqUtils["🧠 Groq Utilities"]
            AWG["analyze_with_groq()\nBuilds multimodal prompt\nCalls Groq API"]
            PGR["parse_groq_response()\nHandles single + multi-JSON\nAverages multi-frame results"]
        end

        subgraph LiveThread["🔁 Background Thread"]
            LAL["live_analysis_loop()\nDaemon thread — runs forever"]
        end

        subgraph MJPEGGen["📡 Streaming"]
            GMJ["generate_mjpeg()\nYield generator · ~30 FPS"]
        end

        subgraph APIRoutes["🌐 Flask Routes"]
            RT_HEALTH["GET /"]
            RT_FEED["GET /video_feed"]
            RT_WEBCAM["POST /start_webcam"]
            RT_SIM["POST /start_simulation"]
            RT_STOP["POST /stop_feed"]
            RT_RESULT["GET /live_result"]
            RT_CLIP["POST /predict_clip"]
        end
    end

    CONFIG --> FrameUtils
    CONFIG --> LiveThread
    FrameUtils --> GroqUtils
    State --> LiveThread
    State --> MJPEGGen
    State --> APIRoutes
    LiveThread --> FrameUtils
    LiveThread --> GroqUtils
    MJPEGGen --> RT_FEED
    RT_WEBCAM --> AS
    RT_SIM --> AS
    RT_STOP --> AS
    RT_RESULT --> LS
    RT_CLIP --> EFV
    LAL --> LS
```

---

## API Reference

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `GET` | `/` | Health check | — | `{ status, backend }` |
| `GET` | `/video_feed` | MJPEG video stream | — | `multipart/x-mixed-replace` stream |
| `POST` | `/start_webcam` | Start laptop webcam as live feed | — | `{ status }` |
| `POST` | `/start_simulation` | Upload video to simulate CCTV feed | `multipart: video` | `{ status, file }` |
| `POST` | `/stop_feed` | Stop the active live feed | — | `{ status }` |
| `GET` | `/live_result` | Get latest live analysis result | — | `{ label, probability, reason, timestamp }` |
| `POST` | `/predict_clip` | Analyze a single uploaded video clip | `multipart: video` | `{ label, probability, reason, raw_probs }` |

### Response Schemas

**`/live_result`**
```json
{
  "label": "violent",
  "probability": 0.87,
  "reason": "Multiple individuals appear to be striking each other near a crowd",
  "timestamp": "14:32:01"
}
```

**`/predict_clip`**
```json
{
  "label": "violent",
  "probability": 0.87,
  "reason": "Multiple individuals appear to be striking each other near a crowd",
  "raw_probs": {
    "violent": 0.87,
    "non_violent": 0.13
  }
}
```

---

## Setup & Installation

### Prerequisites

- Python 3.9+
- A [Groq API key](https://console.groq.com/)
- A webcam (optional, for live feed mode)

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/your-username/mob-violence-detection.git
cd mob-violence-detection

# 2. Install Python dependencies
pip install flask flask-cors opencv-python numpy groq python-dotenv

# 3. Create your .env file
echo "GROQ_API_KEY=your_groq_api_key_here" > .env

# 4. Start the backend
python backend/server.py

# 5. Open the frontend
# Open index.html directly in your browser, or serve it with:
npx serve .
# Then visit http://localhost:3000
```

> **Note:** The frontend connects to `http://localhost:5000` by default. If you change the Flask port, update `API_BASE_URL` at the top of `app.js`.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | Your Groq Cloud API key. Obtain one at [console.groq.com](https://console.groq.com) |

---

## Configuration

All tunable constants are defined at the top of `backend/server.py`:

| Constant | Default | Description |
|----------|---------|-------------|
| `NUM_FRAMES` | `5` | Number of frames extracted per analysis cycle |
| `FRAME_HEIGHT` | `512` | Frame resize height (pixels) before sending to Groq |
| `FRAME_WIDTH` | `512` | Frame resize width (pixels) before sending to Groq |
| `THRESHOLD` | `0.5` | Probability cutoff for classifying as `violent` |
| `ANALYSIS_INTERVAL` | `10` | Seconds between each background analysis in live mode |

---

## How the AI Analysis Works

```mermaid
flowchart TD
    A["📹 Video Source\n(file or live capture)"] --> B["Extract 5 Frames\n(evenly spaced or ~2s apart for live)"]
    B --> C["Resize each frame to 512×512\nEncode as base64 JPEG"]
    C --> D["Build Multimodal Prompt\n'You are a security surveillance AI...\nAnalyze ALL frames as ONE video'"]
    D --> E["POST to Groq API\nModel: llama-4-scout-17b-16e-instruct\ntemp=0.1, max_tokens=256"]
    E --> F{Response format?}
    F -->|Single JSON object| G["Parse directly with json.loads()"]
    F -->|Multiple JSON objects| H["Split on curly-brace boundaries\nAverage probabilities\nMajority-vote on label"]
    G --> I["Extract: label · probability · reason"]
    H --> I
    I --> J{probability >= 0.5?}
    J -->|Yes| K["🔴 Label: VIOLENT"]
    J -->|No| L["🟢 Label: NON-VIOLENT"]
```

The model is prompted to look for:
- Punching, kicking, or striking between individuals
- Throwing objects at people
- Stampede or crush dynamics in a crowd
- Aggressive mob formations with apparent intent

The model explicitly treats the following as **non-violent**:
- Normal crowd gatherings and queues
- People walking or standing in groups
- General movement without aggression

---

## Frontend Dashboard

```mermaid
graph LR
    subgraph Dashboard["🖥️ Dashboard Layout"]
        subgraph Left["Left Panel — Live Feed"]
            VF["📺 Video Display\nMJPEG stream or placeholder"]
            OB["🔴/🟢 Overlay Badge\nCurrent label + confidence"]
            META["⏱️ Threshold · Last prediction time"]
            FC["Feed Controls\n📷 Webcam | 🎬 Simulate | ⏹ Stop"]
        end
        subgraph Right["Right Column"]
            CA["📁 Clip Analysis\nFile picker + Analyze button"]
            RC["📊 Result Card\nLabel + probability + reason"]
            PL["📋 Prediction Log\nTimestamped, color-coded history"]
        end
    end
```

The frontend is a **single-page vanilla JS application** with no framework or build step required. Key behaviors:

- Embeds the MJPEG stream as a plain `<img src="/video_feed">` tag — no WebRTC or WebSocket needed
- Polls `/live_result` every **3 seconds** and compares timestamps to avoid duplicate log entries
- Dynamically updates the colored status badge overlaid on the video panel
- Maintains a scrollable, prepended prediction history log with green/red color coding

---

## Threading Model

```mermaid
graph TD
    MAIN["🧵 Main Thread\nFlask HTTP Server\nHandles all incoming requests\nincluding MJPEG stream generation"]
    BG["🔁 Background Daemon Thread\nlive_analysis_loop\nRuns every ANALYSIS_INTERVAL seconds"]

    LOCK1["🔒 active_source_lock\nthreading.Lock"]
    LOCK2["🔒 live_result_lock\nthreading.Lock"]

    MAIN <-->|"Read/write\nactive_source"| LOCK1
    BG <-->|"Read\nactive_source"| LOCK1
    BG <-->|"Write\nlive_result"| LOCK2
    MAIN <-->|"Read\nlive_result"| LOCK2
```

Both threads share two mutable objects, each protected by a `threading.Lock`:

- **`active_source`** — holds the current `cv2.VideoCapture` object and a string indicating source type (`"webcam"` or `"simulation"`)
- **`live_result`** — holds the latest classification result dict served to the polling frontend

The background thread is started as a **daemon thread**, so it automatically exits when the Flask process terminates — no manual cleanup required.

---

## Versioning Notes

`server.py` contains two versions of the backend logic:

| Version | Status | Features |
|---------|--------|----------|
| **v1** (fully commented out at top of file) | Legacy | Single clip analysis via `/predict_clip` only |
| **v2** (active, below the comments) | Current | v1 + live webcam feed, MJPEG streaming, background analysis thread, CCTV simulation mode |

The v1 code is intentionally preserved in comments as a reference baseline, making the evolution of the system easy to trace.

---

## License

MIT © 2024
