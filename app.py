import asyncio
import io
import os
import re

import edge_tts
from flask import Flask, Response, jsonify, render_template_string, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ALLOWED_VOICES = {
    "my-MM-ThihaNeural",
    "my-MM-NilarNeural",
}

RATE_RE = re.compile(r"^[+-]\d+%$")
PITCH_RE = re.compile(r"^[+-]\d+Hz$")

HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Myanmar TTS</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #0f0f13;
      color: #e8e8f0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }

    .card {
      background: #1a1a24;
      border: 1px solid #2a2a3a;
      border-radius: 16px;
      padding: 40px;
      width: 100%;
      max-width: 560px;
      box-shadow: 0 24px 64px rgba(0,0,0,0.5);
    }

    h1 {
      font-size: 1.4rem;
      font-weight: 600;
      color: #c9b8ff;
      letter-spacing: -0.02em;
      margin-bottom: 6px;
    }

    .subtitle {
      font-size: 0.85rem;
      color: #666688;
      margin-bottom: 32px;
    }

    label {
      display: block;
      font-size: 0.78rem;
      font-weight: 500;
      color: #888899;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 8px;
    }

    .field { margin-bottom: 20px; }

    textarea {
      width: 100%;
      background: #111118;
      border: 1px solid #2a2a3a;
      border-radius: 10px;
      color: #e8e8f0;
      font-size: 1rem;
      line-height: 1.6;
      padding: 14px 16px;
      resize: vertical;
      min-height: 120px;
      outline: none;
      transition: border-color 0.15s;
    }

    textarea:focus { border-color: #7c5cfc; }
    textarea::placeholder { color: #444460; }

    .row { display: flex; gap: 16px; }
    .row .field { flex: 1; }

    select, input[type="text"] {
      width: 100%;
      background: #111118;
      border: 1px solid #2a2a3a;
      border-radius: 10px;
      color: #e8e8f0;
      font-size: 0.92rem;
      padding: 12px 14px;
      outline: none;
      transition: border-color 0.15s;
      appearance: none;
    }

    select:focus, input[type="text"]:focus { border-color: #7c5cfc; }

    select {
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%23666688' stroke-width='1.5' fill='none' stroke-linecap='round'/%3E%3C/svg%3E");
      background-repeat: no-repeat;
      background-position: right 14px center;
      padding-right: 36px;
    }

    .hint {
      font-size: 0.72rem;
      color: #555570;
      margin-top: 5px;
    }

    button {
      width: 100%;
      background: #7c5cfc;
      border: none;
      border-radius: 10px;
      color: #fff;
      font-size: 1rem;
      font-weight: 600;
      padding: 15px;
      cursor: pointer;
      margin-top: 8px;
      transition: background 0.15s, transform 0.1s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }

    button:hover { background: #6a4de8; }
    button:active { transform: scale(0.98); }
    button:disabled { background: #3a3a52; color: #666688; cursor: not-allowed; transform: none; }

    .audio-wrap {
      margin-top: 20px;
      display: none;
    }

    audio {
      width: 100%;
      border-radius: 8px;
      outline: none;
    }

    .error {
      margin-top: 16px;
      background: #2a1020;
      border: 1px solid #5a1530;
      border-radius: 8px;
      color: #ff6688;
      font-size: 0.85rem;
      padding: 12px 14px;
      display: none;
    }

    .spinner {
      width: 18px;
      height: 18px;
      border: 2px solid rgba(255,255,255,0.3);
      border-top-color: #fff;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      display: none;
    }

    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>
  <div class="card">
    <h1>Myanmar Text to Speech</h1>
    <p class="subtitle">Powered by Microsoft Edge TTS</p>

    <div class="field">
      <label for="text">Text</label>
      <textarea id="text" placeholder="မင်္ဂလာပါ..."></textarea>
    </div>

    <div class="field">
      <label for="voice">Voice</label>
      <select id="voice">
        <option value="my-MM-ThihaNeural">ThihaNeural — Male</option>
        <option value="my-MM-NilarNeural">NilarNeural — Female</option>
      </select>
    </div>

    <div class="row">
      <div class="field">
        <label for="rate">Speed</label>
        <input type="text" id="rate" value="+0%" placeholder="+0%" />
        <div class="hint">e.g. +20%, -10%, +0%</div>
      </div>
      <div class="field">
        <label for="pitch">Pitch</label>
        <input type="text" id="pitch" value="+0Hz" placeholder="+0Hz" />
        <div class="hint">e.g. +50Hz, -30Hz, +0Hz</div>
      </div>
    </div>

    <button id="playBtn" onclick="synthesize()">
      <span id="btnText">Play</span>
      <div class="spinner" id="spinner"></div>
    </button>

    <div class="audio-wrap" id="audioWrap">
      <audio id="player" controls></audio>
    </div>

    <div class="error" id="error"></div>
  </div>

  <script>
    async function synthesize() {
      const text = document.getElementById('text').value.trim();
      const voice = document.getElementById('voice').value;
      const rate = document.getElementById('rate').value.trim();
      const pitch = document.getElementById('pitch').value.trim();
      const btn = document.getElementById('playBtn');
      const spinner = document.getElementById('spinner');
      const btnText = document.getElementById('btnText');
      const audioWrap = document.getElementById('audioWrap');
      const player = document.getElementById('player');
      const errorEl = document.getElementById('error');

      errorEl.style.display = 'none';
      audioWrap.style.display = 'none';

      if (!text) {
        showError('Please enter some text.');
        return;
      }

      btn.disabled = true;
      btnText.textContent = 'Generating...';
      spinner.style.display = 'block';

      try {
        const res = await fetch('/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, voice, rate, pitch })
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          showError(data.error || `Error ${res.status}`);
          return;
        }

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        player.src = url;
        audioWrap.style.display = 'block';
        player.play();
      } catch (err) {
        showError('Request failed. Is the server running?');
      } finally {
        btn.disabled = false;
        btnText.textContent = 'Play';
        spinner.style.display = 'none';
      }
    }

    function showError(msg) {
      const el = document.getElementById('error');
      el.textContent = msg;
      el.style.display = 'block';
    }

    document.getElementById('text').addEventListener('keydown', e => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) synthesize();
    });
  </script>
</body>
</html>"""


@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_PAGE)


@app.route("/tts", methods=["POST"])
def tts():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    text = data.get("text", "").strip()
    voice = data.get("voice", "").strip()
    rate = data.get("rate", "+0%")
    pitch = data.get("pitch", "+0Hz")

    if not text:
        return jsonify({"error": "Missing or empty 'text' field"}), 400

    if not voice:
        return jsonify({"error": "Missing or empty 'voice' field"}), 400

    if voice not in ALLOWED_VOICES:
        return jsonify({
            "error": f"Invalid voice '{voice}'. Allowed voices: {sorted(ALLOWED_VOICES)}"
        }), 400

    if not isinstance(rate, str) or not RATE_RE.match(rate):
        return jsonify({
            "error": "Invalid 'rate'. Must be a string like '+10%', '-5%', or '+0%'"
        }), 400

    if not isinstance(pitch, str) or not PITCH_RE.match(pitch):
        return jsonify({
            "error": "Invalid 'pitch'. Must be a string like '+0Hz', '+50Hz', or '-30Hz'"
        }), 400

    try:
        audio_data = asyncio.run(_synthesize(text, voice, rate, pitch))
    except Exception as exc:
        return jsonify({"error": f"TTS synthesis failed: {exc}"}), 500

    return Response(audio_data, mimetype="audio/mpeg")


async def _synthesize(text: str, voice: str, rate: str, pitch: str) -> bytes:
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return buf.read()


@app.route("/healthz", methods=["GET"])
@app.route("/tts/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
