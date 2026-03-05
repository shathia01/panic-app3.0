import streamlit as st
import requests
import math
import smtplib
import time
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
import streamlit.components.v1 as components
from streamlit_js_eval import streamlit_js_eval

st.set_page_config(
    page_title="Emergency Shield",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ==============================
# STYLING
# ==============================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
    background-color: #0a0a0f !important;
    color: #e8e8f0 !important;
}
.stApp { background-color: #0a0a0f !important; }
h1, h2, h3 {
    font-family: 'Bebas Neue', sans-serif !important;
    letter-spacing: 2px !important;
}
.stButton > button {
    font-family: 'Bebas Neue', sans-serif !important;
    font-size: 22px !important;
    letter-spacing: 3px !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 16px !important;
    transition: all 0.2s !important;
}
.stButton > button[kind="primary"] {
    background: #ff1a1a !important;
    color: white !important;
    box-shadow: 0 0 20px rgba(255,26,26,0.3) !important;
}
.stButton > button[kind="secondary"] {
    background: transparent !important;
    border: 2px solid #ff1a1a !important;
    color: #ff1a1a !important;
}
.extreme-banner {
    background: #b30000;
    border: 1px solid #ff1a1a;
    border-radius: 8px;
    padding: 14px 16px;
    margin-bottom: 16px;
    animation: pulse 1s ease-in-out infinite;
    font-family: 'Bebas Neue', sans-serif;
    font-size: 20px;
    letter-spacing: 2px;
    color: white;
}
@keyframes pulse { 0%,100%{opacity:1;} 50%{opacity:0.7;} }
.log-box {
    background: #12121a;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px;
    padding: 12px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 11px;
    max-height: 160px;
    overflow-y: auto;
    margin-bottom: 16px;
}
.stAlert { border-radius: 8px !important; }
</style>
""", unsafe_allow_html=True)

# ==============================
# CONFIG — UPDATE THESE
# ==============================
SENDER_EMAIL        = "shathia190304@gmail.com"
SENDER_APP_PASSWORD = "kvskirvfdhsscege"  # <-- Replace with Gmail App Password
SENDER_NAME         = "Emergency Alert"

DEFAULT_CONTACTS = [
    {"name": "Admin", "email": "shathia190304@gmail.com"},
]

# ==============================
# SESSION STATE
# ==============================
defaults = {
    "extreme_active":     False,
    "update_count":       0,
    "auto_detect":        False,
    "voice_triggered":    False,
    "motion_triggered":   False,
    "safe_check_pending": False,
    "safe_check_start":   None,
    "last_location":      None,
    "panic_requested":    False,
    "logs":               [],
    "contacts":           list(DEFAULT_CONTACTS),
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================
# HELPERS
# ==============================
def add_log(msg, level="info"):
    ts    = datetime.now().strftime("%H:%M:%S")
    icon  = {"info": "·", "ok": "✓", "warn": "⚠", "err": "✕"}.get(level, "·")
    color = {"info": "#6b6b85", "ok": "#00e676", "warn": "#ff8c00", "err": "#ff1a1a"}.get(level, "#6b6b85")
    st.session_state.logs.append(f'<span style="color:{color}">[{ts}] {icon} {msg}</span>')
    if len(st.session_state.logs) > 60:
        st.session_state.logs = st.session_state.logs[-60:]

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def find_police(lat, lon, radius=5000):
    query = f"""
    [out:json][timeout:10];
    (
      node["amenity"="police"](around:{radius},{lat},{lon});
      way["amenity"="police"](around:{radius},{lat},{lon});
    );
    out center;
    """
    try:
        res = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query}, timeout=20
        ).json()
        elements = res.get("elements", [])
        if not elements:
            return None
        best, best_dist = None, float("inf")
        for el in elements:
            plat = el.get("lat") or el.get("center", {}).get("lat")
            plon = el.get("lon") or el.get("center", {}).get("lon")
            if not plat or not plon:
                continue
            dist = haversine(lat, lon, plat, plon)
            if dist < best_dist:
                best_dist = dist
                name = el.get("tags", {}).get("name", "Police Station")
                best = (plat, plon, name, best_dist)
        return best
    except:
        return None

def send_email(name, email, lat, lon, update_num=None, accuracy=None):
    maps_link = f"https://maps.google.com/?q={lat},{lon}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject   = (
        f"LIVE UPDATE #{update_num} - Emergency Alert"
        if update_num else "🚨 Emergency Alert - Urgent"
    )
    msg = MIMEMultipart("alternative")
    msg["Subject"]    = subject
    msg["From"]       = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"]         = email
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="gmail.com")
    body = f"""
🚨 EMERGENCY ALERT

Dear {name},

Emergency panic button was activated.

📍 LOCATION:
Latitude:  {lat}
Longitude: {lon}
Accuracy:  {accuracy if accuracy else 'N/A'} meters

🗺️ Google Maps: {maps_link}

🕐 Time: {timestamp}
{'📡 LIVE UPDATE #' + str(update_num) + ' — location updates every 30 seconds.' if update_num else ''}

---
Sent by Emergency Shield Auto-Detection System
"""
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.sendmail(SENDER_EMAIL, email, msg.as_string())
        return True
    except Exception as e:
        add_log(f"Email error: {e}", "err")
        return False

def send_to_all(lat, lon, contacts, update_num=None, accuracy=None):
    results = []
    for c in contacts:
        ok = send_email(c["name"], c["email"], lat, lon, update_num, accuracy)
        results.append((c["name"], ok))
        add_log(f"Email {'sent' if ok else 'FAILED'} → {c['name']}", "ok" if ok else "err")
    return results

# ==============================
# HIGH-ACCURACY GPS JS FUNCTION
# ==============================
# This JS snippet collects up to SAMPLES readings, keeps only those
# with accuracy ≤ MAX_ACCURACY_M, then returns the best (lowest accuracy value).
# Falls back to the best available reading if none meet the threshold.
HIGH_ACCURACY_GPS_JS = """
new Promise(resolve => {
    const SAMPLES        = 5;       // number of readings to collect
    const MAX_ACCURACY_M = 50;      // discard readings worse than 50 m
    const SAMPLE_INTERVAL_MS = 800; // ms between samples
    const TIMEOUT_MS     = 20000;   // total timeout

    const readings = [];
    let done = false;

    const opts = {
        enableHighAccuracy: true,
        timeout: TIMEOUT_MS,
        maximumAge: 0          // always fresh — never use cached position
    };

    function finish() {
        if (done) return;
        done = true;
        if (readings.length === 0) {
            resolve("ERROR:No GPS readings obtained");
            return;
        }
        // Sort by accuracy ascending (lower = better), pick the best
        readings.sort((a, b) => a[2] - b[2]);
        resolve(readings[0]);
    }

    function takeSample(remaining) {
        if (done) return;
        navigator.geolocation.getCurrentPosition(
            pos => {
                const acc = pos.coords.accuracy;
                readings.push([
                    pos.coords.latitude,
                    pos.coords.longitude,
                    Math.round(acc)
                ]);
                // If this reading is already very good, stop early
                if (acc <= 10) { finish(); return; }
                if (remaining > 1) {
                    setTimeout(() => takeSample(remaining - 1), SAMPLE_INTERVAL_MS);
                } else {
                    finish();
                }
            },
            err => {
                // On error keep trying remaining samples unless it's a hard deny
                if (err.code === 1) {
                    done = true;
                    resolve("ERROR:" + err.message);
                } else if (remaining > 1) {
                    setTimeout(() => takeSample(remaining - 1), SAMPLE_INTERVAL_MS);
                } else {
                    finish();
                }
            },
            opts
        );
    }

    // Failsafe: resolve with best available after total timeout
    setTimeout(finish, TIMEOUT_MS);
    takeSample(SAMPLES);
})
"""

# ==============================
# HEADER
# ==============================
st.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;
     border-bottom:1px solid rgba(255,255,255,0.08);padding-bottom:16px;">
  <div style="width:40px;height:40px;background:#ff1a1a;
       clip-path:polygon(50% 0%,100% 20%,100% 60%,50% 100%,0% 60%,0% 20%);
       display:flex;align-items:center;justify-content:center;font-size:18px;">🛡</div>
  <div>
    <div style="font-family:'Bebas Neue',sans-serif;font-size:30px;letter-spacing:3px;">
      EMERGENCY SHIELD
    </div>
    <div style="font-family:'IBM Plex Mono',monospace;font-size:10px;color:#6b6b85;letter-spacing:1px;">
      AUTO-DANGER DETECTION SYSTEM
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# Set up background geolocation watcher for auto-detect features
streamlit_js_eval(js_expressions="""
(function() {
    if (window._geoWatcherStarted) return true;
    window._geoWatcherStarted = true;
    window._lat      = null;
    window._lon      = null;
    window._acc      = null;
    window._locError = '';
    
    if (!navigator.geolocation) {
        window._locError = 'Geolocation not supported';
        return false;
    }

    function onSuccess(pos) {
        // Only update if this reading is better (lower accuracy number) than current
        var newAcc = pos.coords.accuracy;
        if (window._acc === null || newAcc < window._acc) {
            window._lat = pos.coords.latitude;
            window._lon = pos.coords.longitude;
            window._acc = newAcc;
        }
        window._locError = '';
    }

    function onError(e) {
        window._locError = e.message;
    }

    var opts = { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 };
    navigator.geolocation.getCurrentPosition(onSuccess, onError, opts);
    navigator.geolocation.watchPosition(onSuccess, onError, opts);
    return true;
})()
""", key="setup_geo_watcher")

# ==============================
# SENSOR COMPONENT
# ==============================
SENSOR_HTML = """
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #0a0a0f; font-family: 'IBM Plex Mono', monospace; }
  #root { padding: 6px; }
  .row  { display: flex; gap: 8px; margin-bottom: 8px; }
  .box  {
    flex: 1; background: #12121a;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px; padding: 10px 8px; text-align: center;
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  .box.warn   { border-color: #ff8c00; box-shadow: 0 0 10px rgba(255,140,0,0.2); }
  .box.danger {
    border-color: #ff1a1a; box-shadow: 0 0 12px rgba(255,26,26,0.3);
    animation: flash 0.5s ease-in-out;
  }
  @keyframes flash { 0%,100%{background:#12121a;} 50%{background:rgba(255,26,26,0.1);} }
  .icon { font-size: 18px; margin-bottom: 4px; }
  .lbl  { font-size: 9px; color: #6b6b85; text-transform: uppercase; margin-bottom: 2px; }
  .val  { font-size: 11px; color: #e8e8f0; }
  .bar-bg   { height: 3px; background: #1a1a26; border-radius: 2px; margin-top: 6px; overflow: hidden; }
  .bar-fill { height: 100%; width: 0%; border-radius: 2px; background: #00e676;
              transition: width 0.3s, background 0.3s; }
  #waveCanvas { width: 100%; height: 44px; border-radius: 4px; background: #060610; display: block; }
  #waveWrap   {
    background: #12121a; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 8px; padding: 8px; margin-bottom: 8px;
  }
  #waveLabel {
    font-size: 9px; color: #6b6b85; text-transform: uppercase; margin-bottom: 4px;
    display: flex; justify-content: space-between;
  }
  #transcriptBox { font-size: 10px; color: #6b6b85; margin-top: 5px; min-height: 14px; }
  #micBtn {
    width: 100%; padding: 9px; font-size: 11px; font-family: 'IBM Plex Mono', monospace;
    background: #1a1a26; border: 1px solid rgba(255,255,255,0.15); color: #e8e8f0;
    border-radius: 6px; cursor: pointer; margin-bottom: 8px; letter-spacing: 1px;
    transition: background 0.2s;
  }
  #micBtn:hover { background: #222230; }
  #micBtn.on    { border-color: #ff1a1a; color: #ff1a1a; background: rgba(255,26,26,0.08); }
</style>

<div id="root">
  <button id="micBtn" onclick="toggleMic()">🎙 ENABLE MICROPHONE & MOTION DETECTION</button>
  <div id="waveWrap">
    <div id="waveLabel">
      <span>AUDIO WAVEFORM</span>
      <span id="micStatus" style="color:#6b6b85">MIC OFF</span>
    </div>
    <canvas id="waveCanvas" width="600" height="44"></canvas>
    <div id="transcriptBox">Press button above to start monitoring...</div>
  </div>
  <div class="row">
    <div class="box" id="voiceBox">
      <div class="icon">🎙️</div>
      <div class="lbl">Voice</div>
      <div class="val" id="voiceVal">Idle</div>
      <div class="bar-bg"><div class="bar-fill" id="voiceBar"></div></div>
    </div>
    <div class="box" id="motionBox">
      <div class="icon">📳</div>
      <div class="lbl">Motion</div>
      <div class="val" id="motionVal">0.0 m/s²</div>
      <div class="bar-bg"><div class="bar-fill" id="motionBar"></div></div>
    </div>
    <div class="box" id="safeBox">
      <div class="icon">💬</div>
      <div class="lbl">Status</div>
      <div class="val" id="safeVal">Normal</div>
      <div class="bar-bg"><div class="bar-fill" id="safeBar" style="background:#00e676;width:100%;"></div></div>
    </div>
  </div>
</div>

<script>
// FIX 1: Expanded distress word list — single-syllable words like "help" are
// easier for speech recognition to catch reliably.
const DISTRESS_WORDS = [
  "help", "tolong", "tulong",
  "stop", "no", "dont", "don't",
  "please", "please help",
  "emergency", "danger",
  "let go", "let me go", "leave me",
  "fire",
  "assault", "attack", "attacking",
  "call police", "call 911", "call 999",
  "somebody help", "someone help",
  "save me", "i need help",
  "get away", "go away"
];
const MOTION_THRESHOLD = 15;

let audioCtx = null, analyser = null, waveData = null;
let micOn = false, recognition = null;

// FIX 2: Use postMessage to pass trigger data to the parent Streamlit window.
// sessionStorage is sandboxed per-iframe and is NOT readable by the parent —
// this was silently failing every time.
function setTrigger(type, value) {
    try {
        // Write to our own sessionStorage (for local display)
        sessionStorage.setItem('emergency_' + type, JSON.stringify({
            value: value,
            ts: Date.now()
        }));
    } catch(e) {}
    // Also broadcast to parent window so Streamlit can read it
    try {
        window.parent.postMessage({
            type: 'emergency_trigger',
            triggerType: type,
            value: value,
            ts: Date.now()
        }, '*');
    } catch(e) {}
    // FIX 3: Also write to parent sessionStorage directly if same origin
    try {
        window.parent.sessionStorage.setItem('emergency_' + type, JSON.stringify({
            value: value,
            ts: Date.now()
        }));
    } catch(e) {
        // Cross-origin — postMessage above is the fallback
    }
}

function setBox(id, barId, pct, level) {
  document.getElementById(id + 'Box').className =
    'box ' + (level === 'danger' ? 'danger' : level === 'warn' ? 'warn' : '');
  var bar = document.getElementById(barId);
  bar.style.width      = pct + '%';
  bar.style.background = level === 'danger' ? '#ff1a1a'
                       : level === 'warn'   ? '#ff8c00' : '#00e676';
}

async function toggleMic() {
  if (micOn) { stopMic(); return; }
  try {
    var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    audioCtx.createMediaStreamSource(stream).connect(analyser);
    waveData = new Uint8Array(analyser.fftSize);
    micOn    = true;
    document.getElementById('micBtn').textContent = '⛔ STOP MONITORING';
    document.getElementById('micBtn').classList.add('on');
    document.getElementById('micStatus').textContent = 'MIC ON';
    document.getElementById('micStatus').style.color = '#00e676';
    drawWave();
    startSpeech();
    startMotion();
  } catch(e) {
    document.getElementById('transcriptBox').innerHTML =
      '<span style="color:#ff8c00">⚠ Microphone denied — check browser permissions.</span>';
  }
}

function stopMic() {
  micOn = false;
  if (audioCtx)    { audioCtx.close(); audioCtx = null; }
  if (recognition) { recognition.stop(); recognition = null; }
  document.getElementById('micBtn').textContent = '🎙 ENABLE MICROPHONE & MOTION DETECTION';
  document.getElementById('micBtn').classList.remove('on');
  document.getElementById('micStatus').textContent = 'MIC OFF';
  document.getElementById('micStatus').style.color = '#6b6b85';
}

function drawWave() {
  if (!micOn || !analyser) return;
  var canvas = document.getElementById('waveCanvas');
  var ctx    = canvas.getContext('2d');
  var W = canvas.width, H = canvas.height;
  requestAnimationFrame(drawWave);
  analyser.getByteTimeDomainData(waveData);
  var sum = 0;
  for (var i = 0; i < waveData.length; i++) sum += Math.abs(waveData[i] - 128);
  var amp = Math.min(100, (sum / waveData.length) * 5);
  setBox('voice', 'voiceBar', amp,
    amp > 65 ? 'danger' : amp > 35 ? 'warn' : '');
  document.getElementById('voiceVal').textContent =
    amp > 65 ? 'LOUD' : amp > 35 ? 'Active' : 'Low';
  ctx.fillStyle = '#060610';
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = amp > 65 ? '#ff1a1a' : amp > 35 ? '#ff8c00' : '#00e676';
  ctx.lineWidth   = 1.5;
  ctx.beginPath();
  var sw = W / waveData.length;
  for (var i = 0; i < waveData.length; i++) {
    var y = ((waveData[i] / 128.0) * H) / 2;
    i === 0 ? ctx.moveTo(i * sw, y) : ctx.lineTo(i * sw, y);
  }
  ctx.stroke();
}

function startSpeech() {
  var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) {
    document.getElementById('transcriptBox').innerHTML =
      '<span style="color:#ff8c00">Speech recognition unavailable — use Chrome or Edge.</span>';
    return;
  }
  recognition = new SR();
  recognition.continuous     = true;
  recognition.interimResults = true;
  // FIX 4: Use device locale so the engine is already warm;
  // 'en-US' can mis-transcribe accented speech. We try device lang first,
  // fall back to en-US.
  recognition.lang = navigator.language || 'en-US';

  recognition.onresult = function(e) {
    var t = '';
    for (var i = e.resultIndex; i < e.results.length; i++)
      t += e.results[i][0].transcript.toLowerCase();
    document.getElementById('transcriptBox').textContent = 'Heard: "' + t + '"';

    // FIX 5: Check every word individually so partial matches work
    // e.g. "help me please" contains "help" — this works.
    var found = null;
    for (var w = 0; w < DISTRESS_WORDS.length; w++) {
      if (t.indexOf(DISTRESS_WORDS[w]) !== -1) {
        found = DISTRESS_WORDS[w];
        break;
      }
    }

    if (found) {
      document.getElementById('transcriptBox').innerHTML =
        '<span style="color:#ff1a1a;font-weight:600">⚠ DISTRESS: "' + found + '"</span>';
      document.getElementById('voiceBox').className = 'box danger';
      setTrigger('voice', found);
    }
  };

  // FIX 6: Log ALL speech errors visibly so you can debug on device
  recognition.onerror = function(e) {
    var msg = e.error;
    if (msg === 'no-speech') return; // normal silence, ignore
    if (msg === 'not-allowed') {
      document.getElementById('transcriptBox').innerHTML =
        '<span style="color:#ff1a1a">⚠ Mic permission denied. Enable in browser settings.</span>';
    } else if (msg === 'network') {
      document.getElementById('transcriptBox').innerHTML =
        '<span style="color:#ff8c00">⚠ Speech API needs internet connection.</span>';
    } else {
      document.getElementById('transcriptBox').innerHTML =
        '<span style="color:#ff8c00">⚠ Speech error: ' + msg + '</span>';
    }
    console.warn('SpeechRecognition error:', msg);
  };

  recognition.onend = function() {
    if (micOn) setTimeout(function() {
      if (recognition) {
        try { recognition.start(); } catch(e) {}
      }
    }, 300);
  };

  try {
    recognition.start();
  } catch(e) {
    document.getElementById('transcriptBox').innerHTML =
      '<span style="color:#ff8c00">⚠ Could not start speech: ' + e.message + '</span>';
  }
}

function startMotion() {
  var lastSpike = 0;
  function listen() {
    window.addEventListener('devicemotion', function(e) {
      var a = e.acceleration;
      if (!a) return;
      var mag = Math.sqrt((a.x||0)*(a.x||0)+(a.y||0)*(a.y||0)+(a.z||0)*(a.z||0));
      document.getElementById('motionVal').textContent = mag.toFixed(1) + ' m/s²';
      var pct = Math.min(100, (mag / 25) * 100);
      setBox('motion', 'motionBar', pct,
        mag > MOTION_THRESHOLD ? 'danger' : mag > MOTION_THRESHOLD*0.6 ? 'warn' : '');
      if (mag > MOTION_THRESHOLD && Date.now() - lastSpike > 5000) {
        lastSpike = Date.now();
        setTrigger('motion', mag);
      }
    });
  }
  if (typeof DeviceMotionEvent !== 'undefined' &&
      typeof DeviceMotionEvent.requestPermission === 'function') {
    DeviceMotionEvent.requestPermission()
      .then(function(r) { if (r === 'granted') listen(); })
      .catch(function() { listen(); });
  } else if (typeof DeviceMotionEvent !== 'undefined') {
    listen();
  } else {
    document.getElementById('motionVal').textContent = 'N/A';
  }
}
</script>
"""

components.html(SENSOR_HTML, height=295, scrolling=False)

# ── Listen for postMessage events from the sensor iframe ──────────────────────
# The iframe's sessionStorage is sandboxed (not readable by parent).
# We inject a listener on the PARENT window that catches postMessage from the
# iframe and writes it into the PARENT sessionStorage, which Streamlit CAN read.
streamlit_js_eval(js_expressions="""
(function() {
    if (window._triggerListenerStarted) return true;
    window._triggerListenerStarted = true;
    window.addEventListener('message', function(e) {
        try {
            var d = e.data;
            if (d && d.type === 'emergency_trigger') {
                sessionStorage.setItem('emergency_' + d.triggerType, JSON.stringify({
                    value: d.value,
                    ts: d.ts || Date.now()
                }));
            }
        } catch(err) {}
    });
    return true;
})()
""", key="setup_trigger_listener")

# Read auto-detect signals — now reliably written by the postMessage listener above
voice_data_raw  = streamlit_js_eval(js_expressions="sessionStorage.getItem('emergency_voice')",  key="get_voice")
motion_data_raw = streamlit_js_eval(js_expressions="sessionStorage.getItem('emergency_motion')", key="get_motion")

# Parse triggers
voice_triggered    = False
last_distress_word = ""
if voice_data_raw and voice_data_raw != "null":
    try:
        vdata = json.loads(voice_data_raw)
        if (time.time() * 1000 - vdata.get("ts", 0)) < 20000:
            voice_triggered    = True
            last_distress_word = vdata.get("value", "")
    except:
        pass

motion_triggered = False
if motion_data_raw and motion_data_raw != "null":
    try:
        mdata = json.loads(motion_data_raw)
        if (time.time() * 1000 - mdata.get("ts", 0)) < 10000:
            motion_triggered = True
    except:
        pass

# ==============================
# AUTO-DETECT TOGGLE
# ==============================
st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
col_tog, col_desc = st.columns([1, 3])
with col_tog:
    auto = st.toggle("AUTO-DETECT", value=st.session_state.auto_detect,
                     key="auto_toggle_widget")
with col_desc:
    if auto:
        st.markdown("""<div style='font-family:IBM Plex Mono,monospace;font-size:11px;
            color:#ff8c00;padding-top:6px;'>
            ⚡ ACTIVE — Monitoring voice + motion + response timeout</div>""",
            unsafe_allow_html=True)
    else:
        st.markdown("""<div style='font-family:IBM Plex Mono,monospace;font-size:11px;
            color:#6b6b85;padding-top:6px;'>
            Off — Enable to auto-trigger extreme panic on danger signals</div>""",
            unsafe_allow_html=True)

if auto != st.session_state.auto_detect:
    st.session_state.auto_detect = auto
    add_log(f"Auto-detect {'enabled' if auto else 'disabled'}",
            "ok" if auto else "warn")

# ==============================
# AUTO-DANGER LOGIC
# ==============================
if st.session_state.auto_detect and not st.session_state.extreme_active:

    if voice_triggered and not st.session_state.voice_triggered:
        st.session_state.voice_triggered = True
        add_log(f'Distress word detected: "{last_distress_word}"', "err")

    if motion_triggered and not st.session_state.motion_triggered:
        st.session_state.motion_triggered = True
        add_log("Sudden motion spike detected!", "err")

    if (st.session_state.voice_triggered or st.session_state.motion_triggered) \
            and not st.session_state.safe_check_pending:
        st.session_state.safe_check_pending = True
        st.session_state.safe_check_start   = time.time()
        add_log("Safe check initiated — awaiting user response", "warn")

    if st.session_state.safe_check_pending:
        TIMEOUT   = 15
        elapsed   = time.time() - st.session_state.safe_check_start
        remaining = max(0, TIMEOUT - int(elapsed))
        pct       = min(100, int((elapsed / TIMEOUT) * 100))
        bar_color = "#ff1a1a" if pct > 66 else "#ff8c00"

        st.markdown(f"""
        <div style="background:#1a1000;border:2px solid #ff8c00;border-radius:10px;
             padding:16px;margin-bottom:16px;">
          <div style="font-family:'Bebas Neue',sans-serif;font-size:28px;
               color:#ff8c00;letter-spacing:3px;">⚠ ARE YOU SAFE?</div>
          <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;
               color:#aaa;margin-bottom:10px;">
            Distress signals detected. Confirm safety or extreme panic activates in
            <b style="color:#ff1a1a">{remaining}s</b>
          </div>
          <div style="background:#0a0a0f;border-radius:4px;height:6px;
               overflow:hidden;margin-bottom:12px;">
            <div style="height:100%;width:{pct}%;background:{bar_color};
                 border-radius:4px;transition:width 1s;"></div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        sc1, sc2 = st.columns(2)
        with sc1:
            if st.button("✓ I'M SAFE", use_container_width=True,
                         type="primary", key="im_safe_btn"):
                st.session_state.safe_check_pending = False
                st.session_state.voice_triggered    = False
                st.session_state.motion_triggered   = False
                streamlit_js_eval(js_expressions="""
                    sessionStorage.removeItem('emergency_voice');
                    sessionStorage.removeItem('emergency_motion');
                    true
                """, key="clear_triggers")
                add_log("User confirmed SAFE — alert cancelled", "ok")
                st.success("Marked as safe. Monitoring resumes.")
                st.rerun()
        with sc2:
            if st.button("🚨 SEND HELP NOW", use_container_width=True,
                         key="send_now_btn"):
                st.session_state.safe_check_pending = False
                st.session_state.voice_triggered    = False
                st.session_state.motion_triggered   = False
                st.session_state.extreme_active     = True
                st.session_state.update_count       = 0
                add_log("User manually triggered extreme panic", "err")
                st.rerun()

        if remaining <= 0:
            st.session_state.safe_check_pending = False
            st.session_state.voice_triggered    = False
            st.session_state.motion_triggered   = False
            st.session_state.extreme_active     = True
            st.session_state.update_count       = 0
            add_log("NO RESPONSE — AUTO-TRIGGERING EXTREME PANIC", "err")
            st.rerun()

# ==============================
# EXTREME PANIC BANNER
# ==============================
if st.session_state.extreme_active:
    st.markdown(f"""
    <div class="extreme-banner">
      ⚠ EXTREME PANIC ACTIVE — LIVE TRACKING
      <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:400;
           color:rgba(255,255,255,0.6);margin-top:3px;">
        Update #{st.session_state.update_count} · Sending location every 30 seconds
      </div>
    </div>
    """, unsafe_allow_html=True)

# ==============================
# PANIC BUTTONS
# ==============================
c1, c2 = st.columns(2)

with c1:
    if st.button("🚨 PANIC", use_container_width=True, type="primary",
                 disabled=st.session_state.extreme_active, key="panic_btn"):
        st.session_state.panic_requested = True

    if st.session_state.panic_requested:
        st.info("📍 Getting best available location (collecting samples)...")
        # ── HIGH-ACCURACY: collect up to 5 samples, return the best ──
        loc = streamlit_js_eval(
            js_expressions=HIGH_ACCURACY_GPS_JS,
            key="panic_location_demand"
        )

        if loc is None:
            st.info("📍 Waiting for location... Please check browser permissions.")
            
        elif isinstance(loc, list):
            st.session_state.panic_requested = False
            lat, lon = loc[0], loc[1]
            acc = loc[2] if len(loc) > 2 else None

            st.session_state.last_location = (lat, lon, acc)
            add_log(f"Location: {lat:.5f}, {lon:.5f} (±{acc}m)", "ok")
            
            results = send_to_all(lat, lon, st.session_state.contacts, accuracy=acc)
            for name, ok in results:
                if ok: st.success(f"✓ Alert sent → {name}")
                else:  st.error(f"✕ Failed → {name}")
            
            police = find_police(lat, lon)
            if police:
                plat, plon, pname, dist = police
                st.info(f"📍 {pname} — {dist:.0f}m away")
                st.link_button(
                    "→ NAVIGATE TO POLICE STATION",
                    f"https://www.google.com/maps/dir/?api=1&destination={plat},{plon}"
                )
                
        elif isinstance(loc, str):
            st.session_state.panic_requested = False
            st.error(f"⚠ {loc}")
            add_log(f"Location error: {loc}", "err")

with c2:
    if not st.session_state.extreme_active:
        if st.button("⚡ EXTREME PANIC", use_container_width=True, key="extreme_btn"):
            st.session_state.extreme_active = True
            st.session_state.update_count   = 0
            add_log("Extreme panic manually started", "err")
            st.rerun()
    else:
        if st.button("⛔ STOP TRACKING", use_container_width=True, key="stop_btn"):
            st.session_state.extreme_active = False
            add_log("Extreme panic stopped by user", "warn")
            st.rerun()

# ==============================
# EXTREME PANIC LOOP
# ==============================
if st.session_state.extreme_active:

    st.info("📍 Collecting high-accuracy location samples...")
    # ── HIGH-ACCURACY: collect up to 5 samples, return the best ──
    loc = streamlit_js_eval(
        js_expressions=HIGH_ACCURACY_GPS_JS,
        key=f"extreme_loc_{st.session_state.update_count}"
    )

    if loc is None:
        st.info("📍 Fetching live location update...")
        
    elif isinstance(loc, list):
        e_lat, e_lon = loc[0], loc[1]
        e_acc = loc[2] if len(loc) > 2 else None
        
        st.session_state.update_count += 1
        st.session_state.last_location = (e_lat, e_lon, e_acc)
        
        send_to_all(e_lat, e_lon, st.session_state.contacts,
                    update_num=st.session_state.update_count, accuracy=e_acc)
        add_log(f"Update #{st.session_state.update_count}: {e_lat:.5f}, {e_lon:.5f} (±{e_acc}m)", "ok")
        
        countdown_ph = st.empty()
        for i in range(30, 0, -1):
            if not st.session_state.extreme_active:
                st.stop()
            countdown_ph.markdown(f"""
            <div style="background:#12121a;border:1px solid rgba(255,255,255,0.08);
                 border-radius:8px;padding:10px 14px;font-family:'IBM Plex Mono',monospace;
                 font-size:12px;color:#6b6b85;text-align:center;">
              Next location update in
              <span style="color:#ff1a1a;font-size:18px;font-family:'Bebas Neue',sans-serif;">
                {i}s
              </span>
            </div>""", unsafe_allow_html=True)
            time.sleep(1)
        st.rerun()
        
    elif isinstance(loc, str):
        add_log(f"Location error during tracking: {loc}", "err")
        time.sleep(5)
        st.rerun()

# ==============================
# ACTIVITY LOG
# ==============================
st.markdown("""
<div style='font-family:IBM Plex Mono,monospace;font-size:10px;color:#6b6b85;
     letter-spacing:1px;text-transform:uppercase;margin:8px 0 6px;'>
  Activity Log
</div>""", unsafe_allow_html=True)
log_entries = "<br>".join(reversed(st.session_state.logs[-20:]))
st.markdown(f"<div class='log-box'>{log_entries}</div>", unsafe_allow_html=True)

# ==============================
# CONTACTS MANAGEMENT
# ==============================
with st.expander("👥 Alert Contacts", expanded=False):
    for i, c in enumerate(st.session_state.contacts):
        cn, ce, cd = st.columns([2, 3, 1])
        with cn:
            st.markdown(f"<span style='font-size:13px;font-weight:600;'>{c['name']}</span>",
                        unsafe_allow_html=True)
        with ce:
            st.markdown(f"<span style='font-family:IBM Plex Mono,monospace;font-size:11px;"
                        f"color:#6b6b85;'>{c['email']}</span>", unsafe_allow_html=True)
        with cd:
            if i > 0 and st.button("✕", key=f"del_{i}"):
                st.session_state.contacts.pop(i)
                add_log(f"Removed contact: {c['name']}", "warn")
                st.rerun()

    st.divider()
    an1, an2, an3 = st.columns([2, 3, 1])
    with an1:
        new_name = st.text_input("Name", placeholder="Name",
                                 label_visibility="collapsed", key="new_name")
    with an2:
        new_email = st.text_input("Email", placeholder="email@example.com",
                                  label_visibility="collapsed", key="new_email")
    with an3:
        if st.button("Add", key="add_contact_btn"):
            if new_name and new_email and "@" in new_email:
                if not any(c["email"].lower() == new_email.lower()
                           for c in st.session_state.contacts):
                    st.session_state.contacts.append(
                        {"name": new_name, "email": new_email})
                    add_log(f"Contact added: {new_name}", "ok")
                    st.rerun()
                else:
                    st.warning("Contact already exists.")
            else:
                st.error("Enter a valid name and email.")

# ==============================
# FOOTER
# ==============================
st.markdown("""
<div style="text-align:center;font-family:'IBM Plex Mono',monospace;font-size:9px;
     color:#6b6b85;margin-top:24px;letter-spacing:1px;">
  EMERGENCY SHIELD v2.4 · HIGH-ACCURACY GPS · SET GMAIL APP PASSWORD BEFORE USE
</div>
""", unsafe_allow_html=True)
