import streamlit as st
from faster_whisper import WhisperModel
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib import colors
import tempfile, os, re
from collections import Counter

try:
    from moviepy import VideoFileClip
except ImportError:
    from moviepy.editor import VideoFileClip

# ── PAGE CONFIG ──────────────────────────────────────────────────
st.set_page_config(page_title="VoxDoc", page_icon="🎙", layout="wide",
                   initial_sidebar_state="expanded")

# ── SESSION STATE ────────────────────────────────────────────────
for k, v in {"dark_mode": True, "transcript_done": False, "paragraphs": [],
              "segments_raw": [], "duration": 0, "video_name": "",
              "edited_transcript": ""}.items():
    if k not in st.session_state:
        st.session_state[k] = v

dm = st.session_state.dark_mode
if dm:
    BG,BG2,BG3 = "#0C0C0F","#141418","#1C1C22"
    BORDER      = "#2A2A35"
    TEXT,TEXT2  = "#F0EEF8","#8B8A9A"
    ACC,ACC2    = "#7C6EF5","#4ECDC4"
    SUCC,DANGER = "#6BCB77","#FF6B6B"
else:
    BG,BG2,BG3 = "#F8F7FF","#FFFFFF","#F0EEF8"
    BORDER      = "#E0DEF0"
    TEXT,TEXT2  = "#0C0C1A","#6B6A7A"
    ACC,ACC2    = "#5B4EE0","#2DB8B0"
    SUCC,DANGER = "#3A9A45","#E04444"

# ── CSS ─────────────────────────────────────────────────────────
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500;600&family=Bricolage+Grotesque:wght@400;600;700;800&display=swap');

html,body,[class*="css"],.stApp {{
    font-family:'Bricolage Grotesque',sans-serif !important;
    background:{BG} !important; color:{TEXT} !important;
}}
#MainMenu,footer {{visibility:hidden;}}
.block-container {{padding:1.5rem 2rem 2rem 2rem !important; max-width:100% !important;}}

[data-testid="stSidebar"] {{
    background:{BG2} !important;
    border-right:1px solid {BORDER} !important;
}}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {{
    color:{TEXT} !important;
}}
[data-testid="stSidebar"] .stMarkdown p {{
    color:{TEXT2} !important; font-size:0.78rem !important;
}}

/* cards */
.vd-card {{background:{BG2};border:1px solid {BORDER};border-radius:14px;padding:1.25rem 1.5rem;margin-bottom:1rem;}}
.vd-label {{font-family:'Geist Mono',monospace;font-size:9px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:{TEXT2};margin-bottom:6px;display:block;}}
.vd-badge {{font-family:'Geist Mono',monospace;font-size:9px;font-weight:600;letter-spacing:1px;padding:3px 9px;border-radius:6px;text-transform:uppercase;display:inline-block;}}
.bp {{background:{ACC}22;color:{ACC};}}
.bt {{background:{ACC2}22;color:{ACC2};}}
.bg {{background:{SUCC}22;color:{SUCC};}}

/* metrics */
.vd-metrics {{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;margin-bottom:1rem;}}
.vd-metric {{background:{BG3};border:1px solid {BORDER};border-radius:12px;padding:1rem 1.25rem;}}
.vd-metric-label {{font-family:'Geist Mono',monospace;font-size:9px;letter-spacing:2px;text-transform:uppercase;color:{TEXT2};margin-bottom:6px;}}
.vd-metric-value {{font-size:1.7rem;font-weight:800;color:{TEXT};line-height:1;letter-spacing:-0.03em;}}
.vd-metric-sub {{font-family:'Geist Mono',monospace;font-size:9px;color:{TEXT2};margin-top:4px;}}
.vd-bar {{height:3px;border-radius:2px;background:{BORDER};margin-top:10px;overflow:hidden;}}
.vd-bar-f {{height:100%;border-radius:2px;background:linear-gradient(90deg,{ACC},{ACC2});}}

/* transcript */
.vd-para {{padding:1rem 1.25rem;margin-bottom:.75rem;border-radius:10px;background:{BG3};border-left:3px solid {ACC};font-size:.875rem;line-height:1.85;color:{TEXT};}}
.vd-ts {{font-family:'Geist Mono',monospace;font-size:9px;color:{ACC};margin-bottom:6px;letter-spacing:1px;}}
.vd-para mark {{background:{ACC}44;color:{TEXT};border-radius:3px;padding:0 2px;}}

/* freq chart */
.freq-row {{display:flex;align-items:center;gap:10px;margin-bottom:7px;}}
.freq-w {{font-family:'Geist Mono',monospace;font-size:.72rem;min-width:90px;color:{TEXT};}}
.freq-bw {{flex:1;height:5px;background:{BORDER};border-radius:3px;overflow:hidden;}}
.freq-bi {{height:100%;border-radius:3px;background:linear-gradient(90deg,{ACC},{ACC2});}}
.freq-n {{font-family:'Geist Mono',monospace;font-size:.68rem;color:{TEXT2};min-width:24px;text-align:right;}}

/* radio override */
.stRadio>label{{display:none!important;}}
.stRadio>div{{display:flex!important;flex-direction:row!important;gap:6px!important;flex-wrap:wrap;}}
.stRadio>div>label{{background:{BG3}!important;border:1px solid {BORDER}!important;border-radius:8px!important;padding:6px 14px!important;font-size:.75rem!important;font-weight:600!important;color:{TEXT2}!important;cursor:pointer!important;transition:all .15s!important;}}
.stRadio>div>label:hover{{border-color:{ACC}!important;color:{TEXT}!important;}}

/* select */
.stSelectbox>div>div,[data-baseweb="select"]>div {{background:{BG3}!important;border:1px solid {BORDER}!important;border-radius:10px!important;color:{TEXT}!important;font-size:.82rem!important;}}
[data-baseweb="select"] *{{color:{TEXT}!important;background:{BG3}!important;}}

/* text inputs */
.stTextInput>div>div>input,.stTextArea>div>div>textarea {{background:{BG3}!important;border:1px solid {BORDER}!important;border-radius:10px!important;color:{TEXT}!important;font-size:.82rem!important;font-family:'Geist Mono',monospace!important;}}
.stTextInput>div>div>input:focus,.stTextArea>div>div>textarea:focus {{border-color:{ACC}!important;box-shadow:0 0 0 3px {ACC}22!important;}}

/* file uploader */
[data-testid="stFileUploader"]>div {{background:{BG3}!important;border:1.5px dashed {BORDER}!important;border-radius:14px!important;padding:1.5rem!important;}}
[data-testid="stFileUploader"]>div:hover{{border-color:{ACC}!important;}}
[data-testid="stFileUploader"] *{{color:{TEXT2}!important;font-size:.8rem!important;}}

/* buttons */
.stButton>button {{background:{ACC}!important;color:#fff!important;border:none!important;border-radius:10px!important;padding:.65rem 1.5rem!important;font-family:'Bricolage Grotesque',sans-serif!important;font-weight:700!important;font-size:.82rem!important;width:100%!important;transition:all .15s!important;}}
.stButton>button:hover {{background:{ACC}DD!important;transform:translateY(-1px)!important;box-shadow:0 6px 20px {ACC}44!important;}}
.stDownloadButton>button {{background:transparent!important;color:{ACC2}!important;border:1.5px solid {ACC2}!important;border-radius:10px!important;padding:.65rem 1.5rem!important;font-weight:700!important;font-size:.82rem!important;width:100%!important;transition:all .15s!important;margin-bottom:6px!important;}}
.stDownloadButton>button:hover{{background:{ACC2}18!important;}}

/* misc */
div[data-testid="stSlider"]>div>div>div{{background:{ACC}!important;}}
.stCheckbox>label>span{{color:{TEXT}!important;font-size:.82rem!important;}}
[data-testid="stExpander"]{{background:{BG3}!important;border:1px solid {BORDER}!important;border-radius:12px!important;}}
[data-testid="stExpander"] summary{{color:{TEXT}!important;font-size:.82rem!important;font-weight:600!important;}}
.stSuccess{{background:{SUCC}18!important;border:1px solid {SUCC}55!important;border-radius:10px!important;color:{SUCC}!important;font-size:.8rem!important;}}
.stError{{background:{DANGER}18!important;border:1px solid {DANGER}55!important;border-radius:10px!important;font-size:.8rem!important;}}
.stInfo{{background:{ACC}14!important;border:1px solid {ACC}44!important;border-radius:10px!important;color:{ACC}!important;font-size:.8rem!important;}}
.stSpinner>div{{border-top-color:{ACC}!important;}}
.stVideo{{border-radius:12px!important;overflow:hidden!important;}}
.stMarkdown h1,.stMarkdown h2,.stMarkdown h3{{color:{TEXT}!important;}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
</style>
""", unsafe_allow_html=True)


# ── HELPERS ──────────────────────────────────────────────────────
@st.cache_resource
def load_model(ms):
    return WhisperModel(ms, device="cpu", compute_type="int8")

def format_transcript(segs, secs=90):
    FW = ["so","now","next","then","finally","first","second","third","also",
          "additionally","however","therefore","moreover","furthermore",
          "meanwhile","consequently"]
    def clean(t):
        t = t.strip()
        if not t: return t
        t = t[0].upper() + t[1:]
        for fw in FW:
            t = re.compile(rf'^({re.escape(fw)})\s', re.IGNORECASE).sub(
                lambda m: m.group(1).capitalize() + ', ', t)
        return t
    out, cur, s0 = [], [], None
    for seg in segs:
        if s0 is None: s0 = seg.start
        cur.append(clean(seg.text))
        if seg.end - s0 >= secs:
            out.append((' '.join(cur), s0, seg.end))
            cur, s0 = [], None
    if cur:
        out.append((' '.join(cur), s0 or 0, segs[-1].end if segs else 0))
    return out

def ft(s):
    m, sec = divmod(int(s), 60)
    h, m   = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"

def wfreq(text, n=12):
    STOP = {"the","a","an","is","it","in","of","to","and","that","this","was","for",
            "are","with","he","she","they","we","you","i","be","have","has","had",
            "not","but","so","at","on","or","as","do","did","by","from","up","about",
            "into","then","also","just","like","what","when","there","been","would","could","should"}
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    return Counter(w for w in words if w not in STOP).most_common(n)

def build_txt(paras, ts=False):
    lines = []
    for p, s, e in paras:
        if ts: lines.append(f"[{ft(s)} -> {ft(e)}]")
        lines.append(p)
        lines.append("")
    return "\n".join(lines)

def build_pdf(paras, vname, dur, wc, ts=False):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
        path = f.name
    doc  = SimpleDocTemplate(path, rightMargin=inch, leftMargin=inch,
                              topMargin=inch, bottomMargin=inch)
    sty  = getSampleStyleSheet()
    body = ParagraphStyle('b', parent=sty['Normal'], fontSize=11,
                           leading=18, alignment=TA_JUSTIFY, spaceAfter=12)
    ts_s = ParagraphStyle('t', parent=sty['Normal'], fontSize=8,
                           textColor=colors.HexColor('#7C6EF5'), spaceAfter=4)
    ti_s = ParagraphStyle('ti', parent=sty['Title'], fontSize=20, spaceAfter=6)
    me_s = ParagraphStyle('m', parent=sty['Normal'], fontSize=9,
                           textColor=colors.HexColor('#8B8A9A'), spaceAfter=3)
    el   = [Paragraph("VoxDoc - Transcript Report", ti_s), Spacer(1, .1*inch),
            Paragraph(f"File: {vname}", me_s),
            Paragraph(f"Duration: {ft(dur)}  |  Words: {wc:,}  |  Paragraphs: {len(paras)}", me_s),
            Spacer(1, .2*inch),
            HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2A2A35')),
            Spacer(1, .2*inch)]
    for p, s, e in paras:
        if ts: el.append(Paragraph(f"{ft(s)} -> {ft(e)}", ts_s))
        el.append(Paragraph(p, body))
        el.append(Spacer(1, .1*inch))
    doc.build(el)
    return path


# ════════════════════════════════════════════════════════════════
#  SIDEBAR  — 100% native Streamlit widgets only
# ════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🎙 VoxDoc")
    st.caption("v3.0  ·  AI Transcription Engine")
    st.divider()

    st.markdown("**🎨 Appearance**")
    dark = st.toggle("Dark mode", value=st.session_state.dark_mode)
    if dark != st.session_state.dark_mode:
        st.session_state.dark_mode = dark
        st.rerun()

    st.divider()
    st.markdown("**🧠 Whisper Model**")
    model_size = st.selectbox("Model", ["tiny", "base", "small", "medium"],
                               index=1, label_visibility="collapsed")
    st.caption("tiny=fastest · base=balanced · small=accurate · medium=best")

    st.divider()
    st.markdown("**🌍 Language**")
    lang_map = {
        "Auto detect": None, "English": "en", "Hindi": "hi",
        "Spanish": "es", "French": "fr", "German": "de",
        "Italian": "it", "Portuguese": "pt", "Russian": "ru",
        "Japanese": "ja", "Korean": "ko", "Chinese": "zh",
        "Arabic": "ar", "Dutch": "nl", "Turkish": "tr",
        "Polish": "pl", "Swedish": "sv", "Norwegian": "no",
        "Finnish": "fi", "Greek": "el"
    }
    lang_label = st.selectbox("Language", list(lang_map.keys()),
                               label_visibility="collapsed")
    lang_code  = lang_map[lang_label]

    st.divider()
    st.markdown("**⏱ Paragraph Length**")
    para_secs = st.select_slider(
        "Para", options=[30, 45, 60, 90, 120, 180], value=90,
        format_func=lambda x: f"{x}s", label_visibility="collapsed")

    st.divider()
    st.markdown("**📤 Export Options**")
    include_timestamps = st.checkbox("Include timestamps", value=True)
    include_meta       = st.checkbox("Include metadata",   value=True)

    st.divider()
    if st.button("🗑  Clear session", use_container_width=True):
        st.session_state.transcript_done   = False
        st.session_state.paragraphs        = []
        st.session_state.segments_raw      = []
        st.session_state.duration          = 0
        st.session_state.video_name        = ""
        st.session_state.edited_transcript = ""
        st.rerun()

    st.divider()
    if st.session_state.transcript_done:
        st.success("✅ Transcript ready")
        st.caption(f"📁 {st.session_state.video_name[:30]}")
        st.caption(f"⏱ {ft(st.session_state.duration)}")
        st.caption(f"📋 {len(st.session_state.paragraphs)} paragraphs")
    else:
        st.info("⬆ Upload a file or paste a link to begin")


# ════════════════════════════════════════════════════════════════
#  TOPBAR  — native st.columns (no sticky div)
# ════════════════════════════════════════════════════════════════
tb1, tb2, tb3 = st.columns([2, 5, 3])

with tb1:
    st.markdown(f"### 🎙 VoxDoc")

with tb2:
    label = (st.session_state.video_name[:65] + "..."
             if len(st.session_state.video_name) > 65
             else st.session_state.video_name) if st.session_state.transcript_done \
             else "No file loaded — upload or paste a link below"
    st.markdown(f"<p style='color:{TEXT2};font-family:Geist Mono,monospace;"
                f"font-size:.78rem;padding-top:14px;'>{label}</p>",
                unsafe_allow_html=True)

with tb3:
    dot = f"<span style='display:inline-block;width:7px;height:7px;border-radius:50%;" \
          f"background:{SUCC};margin-right:6px;'></span>" \
          if st.session_state.transcript_done else ""
    st.markdown(f"<p style='text-align:right;color:{TEXT2};"
                f"font-family:Geist Mono,monospace;font-size:.75rem;"
                f"padding-top:14px;'>{dot}{model_size.upper()} · {lang_label}</p>",
                unsafe_allow_html=True)

st.markdown(f"<hr style='border:none;border-top:1px solid {BORDER};"
            f"margin:.25rem 0 1.5rem;'>", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
#  INPUT SECTION
# ════════════════════════════════════════════════════════════════
col_l, col_r = st.columns([3, 2], gap="large")

with col_l:
    st.markdown('<div class="vd-card">', unsafe_allow_html=True)
    st.markdown(
        f"<div style='display:flex;align-items:center;"
        f"justify-content:space-between;margin-bottom:.75rem;'>"
        f"<b style='font-size:.88rem;'>📂 Input Source</b>"
        f"<span class='vd-badge bp'>Required</span></div>",
        unsafe_allow_html=True)

    input_method = st.radio("input_method", ["Upload File", "YouTube / URL"],
                             label_visibility="collapsed")
    video_path = audio_path = video_name = None

    if input_method == "Upload File":
        uploaded = st.file_uploader(
            "", type=["mp4", "mov", "avi", "mkv", "webm", "m4v"],
            label_visibility="collapsed")
        if uploaded:
            ext = os.path.splitext(uploaded.name)[-1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                tmp.write(uploaded.read())
                video_path = tmp.name
            video_name = uploaded.name
            st.video(uploaded)
            c1, c2, c3 = st.columns(3)
            c1.markdown(f"<span class='vd-badge bg'>{ext.upper().strip('.')}</span>",
                        unsafe_allow_html=True)
            c2.markdown(f"<span class='vd-badge bt'>{round(uploaded.size/1024/1024,1)} MB</span>",
                        unsafe_allow_html=True)
            c3.markdown("<span class='vd-badge bp'>Ready</span>", unsafe_allow_html=True)
    else:
        url = st.text_input("", placeholder="https://youtube.com/watch?v=...",
                             label_visibility="collapsed")
        if url:
            with st.spinner("Downloading..."):
                try:
                    import yt_dlp
                    with tempfile.TemporaryDirectory() as td:
                        opts = {'format': 'best[ext=mp4]/best',
                                'outtmpl': os.path.join(td, 'video.%(ext)s'),
                                'quiet': True}
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info = ydl.extract_info(url, download=True)
                            video_name = info.get('title', 'video')
                            ext = f".{info['ext']}"
                            src = os.path.join(td, f"video.{info['ext']}")
                            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                                tmp.write(open(src, 'rb').read())
                                video_path = tmp.name
                    st.success(f"Downloaded: {video_name[:55]}")
                except Exception as e:
                    st.error(f"Failed: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

with col_r:
    st.markdown('<div class="vd-card">', unsafe_allow_html=True)
    st.markdown("<b style='font-size:.88rem;'>⚙️ Transcription Settings</b>",
                unsafe_allow_html=True)
    st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)

    st.markdown("<span class='vd-label'>VAD Silence Filter (ms)</span>",
                unsafe_allow_html=True)
    vad_ms = st.slider("vad", 200, 1000, 500, 50, label_visibility="collapsed")

    st.markdown("<span class='vd-label'>Beam Size</span>", unsafe_allow_html=True)
    beam = st.slider("beam", 1, 10, 5, label_visibility="collapsed")

    task = "transcribe"

    st.markdown(f"""
    <div style='background:{BG3};border:1px solid {BORDER};border-radius:9px;
    padding:9px 13px;margin-top:.75rem;font-family:Geist Mono,monospace;
    font-size:9px;color:{TEXT2};line-height:2;'>
    Model&nbsp;<span style='color:{ACC}'>{model_size}</span>&nbsp;&nbsp;
    Lang&nbsp;<span style='color:{ACC}'>{lang_label}</span><br>
    Para&nbsp;<span style='color:{ACC}'>{para_secs}s</span>&nbsp;&nbsp;
    Timestamps&nbsp;<span style='color:{ACC2}'>{'on' if include_timestamps else 'off'}</span>
    </div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    if video_path:
        st.markdown("<div style='height:.4rem'></div>", unsafe_allow_html=True)
        if st.button("▶  Run Transcription"):
            audio_path = video_path + ".wav"
            vobj = None
            with st.spinner("Extracting audio & transcribing..."):
                try:
                    vobj = VideoFileClip(video_path)
                    dur  = round(vobj.duration, 2)
                    vobj.audio.write_audiofile(audio_path, logger=None)
                    vobj.close()

                    mdl  = load_model(model_size)
                    segs, _ = mdl.transcribe(
                        audio_path, beam_size=beam,
                        language=lang_code, task=task,
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=vad_ms))
                    sl    = list(segs)
                    paras = format_transcript(sl, para_secs)

                    st.session_state.transcript_done   = True
                    st.session_state.paragraphs        = paras
                    st.session_state.segments_raw      = sl
                    st.session_state.duration          = dur
                    st.session_state.video_name        = video_name or "unknown"
                    st.session_state.edited_transcript = "\n\n".join(
                        [p for p, _, _ in paras])

                    for p in [video_path, audio_path]:
                        try: os.remove(p)
                        except: pass
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
                finally:
                    if vobj:
                        try: vobj.close()
                        except: pass


# ════════════════════════════════════════════════════════════════
#  RESULTS
# ════════════════════════════════════════════════════════════════
if st.session_state.transcript_done and st.session_state.paragraphs:
    paras    = st.session_state.paragraphs
    full_txt = " ".join([p for p, _, _ in paras])
    wc       = len(full_txt.split())
    dur      = st.session_state.duration
    vname    = st.session_state.video_name
    freq     = wfreq(full_txt)
    wpm      = int(wc / max(dur / 60, 0.01))

    st.markdown(
        f"<hr style='border:none;border-top:1px solid {BORDER};"
        f"margin:.5rem 0 1rem;'>", unsafe_allow_html=True)

    # ── METRICS ──
    st.markdown(f"""
    <div class="vd-metrics">
      <div class="vd-metric">
        <div class="vd-metric-label">Words</div>
        <div class="vd-metric-value">{wc:,}</div>
        <div class="vd-metric-sub">transcribed</div>
        <div class="vd-bar"><div class="vd-bar-f" style="width:100%"></div></div>
      </div>
      <div class="vd-metric">
        <div class="vd-metric-label">Duration</div>
        <div class="vd-metric-value">{ft(dur)}</div>
        <div class="vd-metric-sub">audio length</div>
        <div class="vd-bar"><div class="vd-bar-f" style="width:70%"></div></div>
      </div>
      <div class="vd-metric">
        <div class="vd-metric-label">Paragraphs</div>
        <div class="vd-metric-value">{len(paras)}</div>
        <div class="vd-metric-sub">{para_secs}s each</div>
        <div class="vd-bar"><div class="vd-bar-f" style="width:50%"></div></div>
      </div>
      <div class="vd-metric">
        <div class="vd-metric-label">Speech Rate</div>
        <div class="vd-metric-value">{wpm}</div>
        <div class="vd-metric-sub">words / min</div>
        <div class="vd-bar"><div class="vd-bar-f" style="width:60%"></div></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col_t, col_s = st.columns([3, 2], gap="large")

    with col_t:
        st.markdown('<div class="vd-card">', unsafe_allow_html=True)
        st.markdown(
            f"<div style='display:flex;align-items:center;"
            f"justify-content:space-between;margin-bottom:.75rem;'>"
            f"<b style='font-size:.88rem;'>📝 Transcript</b>"
            f"<span class='vd-badge bg'>{len(paras)} sections</span></div>",
            unsafe_allow_html=True)

        view = st.radio("view", ["Formatted", "Timestamps", "Edit", "Search"],
                         horizontal=True, label_visibility="collapsed")

        if view == "Formatted":
            st.markdown("".join(
                f'<div class="vd-para">{p}</div>'
                for p, _, _ in paras), unsafe_allow_html=True)

        elif view == "Timestamps":
            st.markdown("".join(
                f'<div class="vd-para">'
                f'<div class="vd-ts">{ft(s)} &rarr; {ft(e)}</div>{p}</div>'
                for p, s, e in paras), unsafe_allow_html=True)

        elif view == "Edit":
            st.caption("Edit below — changes are reflected in all exports")
            ed = st.text_area("", value=st.session_state.edited_transcript,
                               height=420, label_visibility="collapsed")
            st.session_state.edited_transcript = ed

        elif view == "Search":
            q = st.text_input("", placeholder="Search transcript...",
                               label_visibility="collapsed")
            if q:
                hits, n = [], 0
                for p, s, e in paras:
                    if q.lower() in p.lower():
                        hl = re.sub(f'({re.escape(q)})', r'<mark>\1</mark>',
                                    p, flags=re.IGNORECASE)
                        n += p.lower().count(q.lower())
                        hits.append(
                            f'<div class="vd-para">'
                            f'<div class="vd-ts">{ft(s)}</div>{hl}</div>')
                if hits:
                    st.markdown(
                        f"<p style='font-family:Geist Mono,monospace;font-size:10px;"
                        f"color:{ACC};margin-bottom:8px;'>{n} match(es) found</p>",
                        unsafe_allow_html=True)
                    st.markdown("".join(hits), unsafe_allow_html=True)
                else:
                    st.caption(f'No results for "{q}"')
            else:
                st.caption("Type above to search the transcript")

        st.markdown('</div>', unsafe_allow_html=True)

    with col_s:
        # word frequency
        st.markdown('<div class="vd-card">', unsafe_allow_html=True)
        st.markdown(
            f"<div style='display:flex;align-items:center;"
            f"justify-content:space-between;margin-bottom:.75rem;'>"
            f"<b style='font-size:.88rem;'>📊 Top Words</b>"
            f"<span class='vd-badge bt'>Frequency</span></div>",
            unsafe_allow_html=True)
        if freq:
            mx = freq[0][1]
            st.markdown("".join(
                f'<div class="freq-row">'
                f'<div class="freq-w">{w}</div>'
                f'<div class="freq-bw"><div class="freq-bi" style="width:{int(c/mx*100)}%">'
                f'</div></div><div class="freq-n">{c}</div></div>'
                for w, c in freq), unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # export
        st.markdown('<div class="vd-card">', unsafe_allow_html=True)
        st.markdown(
            f"<div style='display:flex;align-items:center;"
            f"justify-content:space-between;margin-bottom:.75rem;'>"
            f"<b style='font-size:.88rem;'>⬇️ Export</b>"
            f"<span class='vd-badge bp'>2 formats</span></div>",
            unsafe_allow_html=True)

        # use edited transcript if available
        ep = paras
        if st.session_state.edited_transcript.strip():
            et = [x.strip() for x in
                  st.session_state.edited_transcript.split("\n\n") if x.strip()]
            if len(et) == len(paras):
                ep = [(t, s, e) for t, (_, s, e) in zip(et, paras)]

        pdf_p = build_pdf(ep, vname, dur, wc, include_timestamps)
        with open(pdf_p, "rb") as f:
            st.download_button(
                "📄  Download PDF", f,
                file_name=f"voxdoc_{vname[:20].replace(' ', '_')}.pdf",
                mime="application/pdf")

        st.download_button(
            "📃  Download TXT",
            build_txt(ep, include_timestamps).encode(),
            file_name=f"voxdoc_{vname[:20].replace(' ', '_')}.txt",
            mime="text/plain")

        st.markdown(
            f"<p style='font-family:Geist Mono,monospace;font-size:9px;"
            f"color:{TEXT2};margin-top:.5rem;'>"
            f"Timestamps: {'on' if include_timestamps else 'off'} "
            f"&nbsp;·&nbsp; {len(paras)} segments</p>",
            unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # segment browser
        with st.expander("🔎  Segment Browser"):
            sl = st.session_state.segments_raw
            for seg in sl[:30]:
                st.markdown(
                    f"<div style='display:flex;gap:10px;padding:5px 0;"
                    f"border-bottom:1px solid {BORDER};'>"
                    f"<span style='font-family:Geist Mono,monospace;font-size:9px;"
                    f"color:{ACC};min-width:55px;flex-shrink:0;'>{ft(seg.start)}</span>"
                    f"<span style='font-size:.78rem;color:{TEXT};line-height:1.5;'>"
                    f"{seg.text.strip()}</span></div>",
                    unsafe_allow_html=True)
            if len(sl) > 30:
                st.caption(f"+ {len(sl) - 30} more segments")