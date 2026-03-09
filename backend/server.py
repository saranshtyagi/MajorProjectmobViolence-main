# import os
# import re
# import json
# import tempfile
# import base64

# import cv2
# import numpy as np
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# from groq import Groq
# from dotenv import load_dotenv

# # -------- Load .env -------- #
# load_dotenv()

# # -------- Config -------- #
# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# NUM_FRAMES = 5
# FRAME_HEIGHT = 512
# FRAME_WIDTH = 512
# THRESHOLD = 0.5

# if not GROQ_API_KEY:
#     raise ValueError("GROQ_API_KEY not found in .env file")

# client = Groq(api_key=GROQ_API_KEY)

# # -------- Flask App -------- #
# app = Flask(__name__)
# CORS(app)


# def extract_frames(video_path, num_frames=NUM_FRAMES):
#     """Extract evenly-spaced frames from a video and return as base64 JPEG strings."""
#     cap = cv2.VideoCapture(video_path)
#     if not cap.isOpened():
#         cap.release()
#         return None

#     total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
#     if total_frames <= 0:
#         cap.release()
#         return None

#     indices = set(np.linspace(0, total_frames - 1, num_frames, dtype=int))
#     frames_b64 = []
#     idx = 0

#     while True:
#         ret, frame = cap.read()
#         if not ret:
#             break
#         if idx in indices:
#             frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
#             _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
#             frames_b64.append(base64.b64encode(buffer).decode("utf-8"))
#         idx += 1

#     cap.release()
#     return frames_b64 if frames_b64 else None


# def analyze_with_groq(frames_b64):
#     """Send frames to Groq vision model and get violence analysis."""

#     content = [
#         {
#             "type": "text",
#             "text": (
#                 "You are a security surveillance AI assistant. I am giving you multiple frames "
#                 "extracted from a SINGLE CCTV video clip. Analyze ALL frames TOGETHER as one video "
#                 "and give me ONE single consolidated assessment of the entire video.\n\n"
#                 "DO NOT analyze each frame separately. Look at all frames as a sequence from one video.\n\n"
#                 "You MUST respond with EXACTLY ONE JSON object in this format, nothing else:\n"
#                 '{"label": "violent" or "non-violent", "probability": <float between 0.0 and 1.0>, '
#                 '"reason": "<brief one-line explanation>"}\n\n'
#                 "Rules:\n"
#                 "- probability should reflect your confidence (0.0 = definitely safe, 1.0 = definitely violent)\n"
#                 "- Look for punching, kicking, throwing objects, stampede, aggressive mobs.\n"
#                 "- Normal crowd gatherings, walking, standing are NOT violent.\n"
#                 "- Respond with ONLY ONE raw JSON object. No multiple objects. No markdown. No extra text."
#             ),
#         }
#     ]

#     for i, b64 in enumerate(frames_b64):
#         content.append({
#             "type": "image_url",
#             "image_url": {
#                 "url": f"data:image/jpeg;base64,{b64}",
#             },
#         })

#     response = client.chat.completions.create(
#         model="meta-llama/llama-4-scout-17b-16e-instruct",
#         messages=[
#             {
#                 "role": "user",
#                 "content": content,
#             }
#         ],
#         temperature=0.1,
#         max_completion_tokens=256,
#     )

#     return response.choices[0].message.content


# def parse_groq_response(raw_response):
#     """
#     Parse the Groq response. Handles two cases:
#     1. Single JSON object (expected) — parse directly
#     2. Multiple JSON objects (one per frame) — parse each, average results
#     """
#     cleaned = raw_response.strip()

#     # Strip markdown code fences if present
#     if cleaned.startswith("```"):
#         cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

#     # Try parsing as a single JSON object first
#     try:
#         result = json.loads(cleaned)
#         return result
#     except json.JSONDecodeError:
#         pass

#     # Fallback: Multiple JSON objects (one per line or concatenated)
#     parts = re.split(r'\}\s*\n\s*\{', cleaned)

#     results = []
#     for i, part in enumerate(parts):
#         if not part.strip().startswith("{"):
#             part = "{" + part
#         if not part.strip().endswith("}"):
#             part = part + "}"
#         try:
#             results.append(json.loads(part))
#         except json.JSONDecodeError:
#             continue

#     if not results:
#         raise ValueError(f"Could not parse Groq response: {raw_response}")

#     # Average all results into one
#     avg_prob = sum(r.get("probability", 0.0) for r in results) / len(results)

#     # Count violent vs non-violent labels (majority vote)
#     violent_count = sum(1 for r in results if r.get("label", "").lower() == "violent")
#     label = "violent" if violent_count > len(results) / 2 else "non-violent"

#     # Combine reasons
#     reasons = [r.get("reason", "") for r in results if r.get("reason")]
#     combined_reason = reasons[0] if len(reasons) == 1 else f"Based on {len(results)} frames: {reasons[0]}"

#     return {
#         "label": label,
#         "probability": round(avg_prob, 4),
#         "reason": combined_reason,
#     }


# # -------- Routes -------- #

# @app.route("/", methods=["GET"])
# def health():
#     return jsonify({"status": "ok", "backend": "groq-vision"})


# @app.route("/predict_clip", methods=["POST"])
# def predict_clip():
#     if "video" not in request.files:
#         return jsonify({"error": "No 'video' file in request"}), 400

#     file = request.files["video"]
#     if file.filename == "":
#         return jsonify({"error": "Empty filename"}), 400

#     fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
#     os.close(fd)
#     file.save(tmp_path)

#     try:
#         frames = extract_frames(tmp_path)
#         if frames is None:
#             return jsonify({"error": "Could not read video frames"}), 400

#         print(f"Extracted {len(frames)} frames, sending to Groq...")

#         raw_response = analyze_with_groq(frames)
#         print("Groq response:", raw_response)

#         # Parse with fallback handling
#         result = parse_groq_response(raw_response)

#         prob = float(result.get("probability", 0.0))
#         label = result.get("label", "non-violent").lower()
#         reason = result.get("reason", "")

#         if label not in ("violent", "non-violent"):
#             label = "violent" if prob >= THRESHOLD else "non-violent"

#         return jsonify({
#             "probability": prob,
#             "label": label,
#             "reason": reason,
#             "raw_probs": {
#                 "non_violent": round(1 - prob, 4),
#                 "violent": round(prob, 4),
#             },
#         })

#     except Exception as e:
#         print("Error:", e)
#         return jsonify({"error": str(e)}), 500
#     finally:
#         if os.path.exists(tmp_path):
#             os.remove(tmp_path)


# if __name__ == "__main__":
#     app.run(host="0.0.0.0", port=5000, debug=True)

import os
import re
import json
import tempfile
import base64
import time
import threading

import cv2
import numpy as np
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv

# -------- Load .env -------- #
load_dotenv()

# -------- Config -------- #
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
NUM_FRAMES = 5
FRAME_HEIGHT = 512
FRAME_WIDTH = 512
THRESHOLD = 0.5
ANALYSIS_INTERVAL = 10  # Seconds between each live analysis

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not found in .env file")

client = Groq(api_key=GROQ_API_KEY)

# -------- Flask App -------- #
app = Flask(__name__)
CORS(app)

# -------- Shared State -------- #
# Stores the latest live analysis result so the frontend can poll it
live_result = {
    "label": "non-violent",
    "probability": 0.0,
    "reason": "Waiting for first analysis...",
    "timestamp": None,
}
live_result_lock = threading.Lock()

# Active video source: "webcam" or path to a video file
active_source = {"type": None, "cap": None}
active_source_lock = threading.Lock()


# -------- Frame Extraction -------- #

def extract_frames_from_video(video_path, num_frames=NUM_FRAMES):
    """Extract evenly-spaced frames from a video file and return as base64 JPEG strings."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return None

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        return None

    indices = set(np.linspace(0, total_frames - 1, num_frames, dtype=int))
    frames_b64 = []
    idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx in indices:
            frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frames_b64.append(base64.b64encode(buffer).decode("utf-8"))
        idx += 1

    cap.release()
    return frames_b64 if frames_b64 else None


def grab_live_frames(cap, num_frames=NUM_FRAMES):
    """Grab num_frames from a live video capture (webcam or simulation) spread over ~2 seconds."""
    frames_b64 = []
    for i in range(num_frames):
        ret, frame = cap.read()
        if not ret:
            return None
        frame = cv2.resize(frame, (FRAME_WIDTH, FRAME_HEIGHT))
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        frames_b64.append(base64.b64encode(buffer).decode("utf-8"))
        if i < num_frames - 1:
            time.sleep(0.4)  # Spread frames over ~2 seconds
    return frames_b64 if frames_b64 else None


# -------- Groq Analysis -------- #

def analyze_with_groq(frames_b64):
    """Send frames to Groq vision model and get violence analysis."""
    content = [
        {
            "type": "text",
            "text": (
                "You are a security surveillance AI assistant. I am giving you multiple frames "
                "extracted from a SINGLE CCTV video clip. Analyze ALL frames TOGETHER as one video "
                "and give me ONE single consolidated assessment of the entire video.\n\n"
                "DO NOT analyze each frame separately. Look at all frames as a sequence from one video.\n\n"
                "You MUST respond with EXACTLY ONE JSON object in this format, nothing else:\n"
                '{"label": "violent" or "non-violent", "probability": <float between 0.0 and 1.0>, '
                '"reason": "<brief one-line explanation>"}\n\n'
                "Rules:\n"
                "- probability should reflect your confidence (0.0 = definitely safe, 1.0 = definitely violent)\n"
                "- Look for punching, kicking, throwing objects, stampede, aggressive mobs.\n"
                "- Normal crowd gatherings, walking, standing are NOT violent.\n"
                "- Respond with ONLY ONE raw JSON object. No multiple objects. No markdown. No extra text."
            ),
        }
    ]

    for b64 in frames_b64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
            },
        })

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "user", "content": content}],
        temperature=0.1,
        max_completion_tokens=256,
    )

    return response.choices[0].message.content


def parse_groq_response(raw_response):
    """Parse Groq response — handles single or multiple JSON objects."""
    cleaned = raw_response.strip()

    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    # Try single JSON first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: multiple JSON objects
    parts = re.split(r'\}\s*\n\s*\{', cleaned)
    results = []
    for part in parts:
        if not part.strip().startswith("{"):
            part = "{" + part
        if not part.strip().endswith("}"):
            part = part + "}"
        try:
            results.append(json.loads(part))
        except json.JSONDecodeError:
            continue

    if not results:
        raise ValueError(f"Could not parse Groq response: {raw_response}")

    avg_prob = sum(r.get("probability", 0.0) for r in results) / len(results)
    violent_count = sum(1 for r in results if r.get("label", "").lower() == "violent")
    label = "violent" if violent_count > len(results) / 2 else "non-violent"
    reasons = [r.get("reason", "") for r in results if r.get("reason")]
    combined_reason = reasons[0] if len(reasons) == 1 else f"Based on {len(results)} frames: {reasons[0]}"

    return {"label": label, "probability": round(avg_prob, 4), "reason": combined_reason}


# -------- Live Analysis Background Thread -------- #

def live_analysis_loop():
    """Background thread that periodically grabs frames and analyzes them."""
    global live_result

    while True:
        cap = None
        with active_source_lock:
            if active_source["cap"] is not None and active_source["cap"].isOpened():
                cap = active_source["cap"]

        if cap is None:
            time.sleep(1)
            continue

        try:
            frames = grab_live_frames(cap, NUM_FRAMES)
            if frames is None:
                # Video ended (simulation), stop the source
                with active_source_lock:
                    if active_source["cap"] is not None:
                        active_source["cap"].release()
                        active_source["cap"] = None
                        active_source["type"] = None
                with live_result_lock:
                    live_result = {
                        "label": "non-violent",
                        "probability": 0.0,
                        "reason": "Feed ended.",
                        "timestamp": time.strftime("%H:%M:%S"),
                    }
                continue

            print(f"[Live] Grabbed {len(frames)} frames, analyzing...")
            raw = analyze_with_groq(frames)
            print(f"[Live] Groq response: {raw}")

            result = parse_groq_response(raw)
            with live_result_lock:
                live_result = {
                    "label": result.get("label", "non-violent"),
                    "probability": float(result.get("probability", 0.0)),
                    "reason": result.get("reason", ""),
                    "timestamp": time.strftime("%H:%M:%S"),
                }

        except Exception as e:
            print(f"[Live] Analysis error: {e}")

        time.sleep(ANALYSIS_INTERVAL)


# Start background thread
analysis_thread = threading.Thread(target=live_analysis_loop, daemon=True)
analysis_thread.start()


# -------- MJPEG Stream Generator -------- #

def generate_mjpeg():
    """Yields MJPEG frames from the active source for the browser to display."""
    while True:
        cap = None
        with active_source_lock:
            if active_source["cap"] is not None and active_source["cap"].isOpened():
                cap = active_source["cap"]

        if cap is None:
            # Send a blank frame
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, "No feed active", (150, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            _, buffer = cv2.imencode(".jpg", blank)
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
            time.sleep(0.5)
            continue

        ret, frame = cap.read()
        if not ret:
            # Video simulation ended
            with active_source_lock:
                active_source["cap"].release()
                active_source["cap"] = None
                active_source["type"] = None
            continue

        # Add a small overlay showing source type
        with active_source_lock:
            src_type = active_source["type"] or ""
        overlay_text = "LIVE - WEBCAM" if src_type == "webcam" else "LIVE - SIMULATION"
        cv2.putText(frame, overlay_text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")
        time.sleep(0.033)  # ~30 FPS


# -------- Routes -------- #

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok", "backend": "groq-vision"})


@app.route("/video_feed")
def video_feed():
    """MJPEG stream endpoint — plug this into an <img> tag."""
    return Response(generate_mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/start_webcam", methods=["POST"])
def start_webcam():
    """Start the laptop webcam as the live feed source."""
    with active_source_lock:
        if active_source["cap"] is not None:
            active_source["cap"].release()
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            return jsonify({"error": "Could not open webcam"}), 500
        active_source["cap"] = cap
        active_source["type"] = "webcam"
    return jsonify({"status": "webcam started"})


@app.route("/start_simulation", methods=["POST"])
def start_simulation():
    """Upload a pre-recorded video to simulate as a live CCTV feed."""
    if "video" not in request.files:
        return jsonify({"error": "No 'video' file in request"}), 400

    file = request.files["video"]
    fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    file.save(tmp_path)

    with active_source_lock:
        if active_source["cap"] is not None:
            active_source["cap"].release()
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            return jsonify({"error": "Could not open video file"}), 500
        active_source["cap"] = cap
        active_source["type"] = "simulation"

    return jsonify({"status": "simulation started", "file": file.filename})


@app.route("/stop_feed", methods=["POST"])
def stop_feed():
    """Stop the current live feed."""
    with active_source_lock:
        if active_source["cap"] is not None:
            active_source["cap"].release()
        active_source["cap"] = None
        active_source["type"] = None
    return jsonify({"status": "feed stopped"})


@app.route("/live_result", methods=["GET"])
def get_live_result():
    """Poll this to get the latest live analysis result."""
    with live_result_lock:
        return jsonify(live_result)


@app.route("/predict_clip", methods=["POST"])
def predict_clip():
    """Upload and analyze a single video clip (original feature)."""
    if "video" not in request.files:
        return jsonify({"error": "No 'video' file in request"}), 400

    file = request.files["video"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400

    fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
    os.close(fd)
    file.save(tmp_path)

    try:
        frames = extract_frames_from_video(tmp_path)
        if frames is None:
            return jsonify({"error": "Could not read video frames"}), 400

        print(f"Extracted {len(frames)} frames, sending to Groq...")
        raw_response = analyze_with_groq(frames)
        print("Groq response:", raw_response)

        result = parse_groq_response(raw_response)

        prob = float(result.get("probability", 0.0))
        label = result.get("label", "non-violent").lower()
        reason = result.get("reason", "")

        if label not in ("violent", "non-violent"):
            label = "violent" if prob >= THRESHOLD else "non-violent"

        return jsonify({
            "probability": prob,
            "label": label,
            "reason": reason,
            "raw_probs": {
                "non_violent": round(1 - prob, 4),
                "violent": round(prob, 4),
            },
        })

    except Exception as e:
        print("Error:", e)
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)