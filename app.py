"""
app.py - Premium Streamlit UI for the DDR Report Generation System.
Connects to the FastAPI backend at localhost:8000.
"""

import streamlit as st
import requests
import time
import json
import pandas as pd
from datetime import datetime

# ─── Page Config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="DDR Report Generator | AI-Powered Diagnostics",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

API_BASE = "http://localhost:8000"

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
  /* ── Global ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #0d1117;
    color: #e6edf3;
  }

  .stApp { background: #0d1117; }

  /* ── Hide Streamlit chrome ── */
  #MainMenu, footer, header { visibility: hidden; }
  .block-container { padding: 2rem 3rem !important; max-width: 1200px; margin: auto; }

  /* ── Hero Banner ── */
  .hero {
    background: linear-gradient(135deg, #1f3864 0%, #2e5299 50%, #1a2980 100%);
    border-radius: 16px;
    padding: 3rem 3.5rem;
    margin-bottom: 2rem;
    border: 1px solid rgba(255,255,255,0.08);
    position: relative;
    overflow: hidden;
  }
  .hero::before {
    content: '';
    position: absolute;
    top: -50%; right: -10%;
    width: 400px; height: 400px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(224,123,57,0.15) 0%, transparent 70%);
  }
  .hero h1 {
    font-size: 2.4rem;
    font-weight: 800;
    color: #ffffff;
    margin: 0 0 0.5rem 0;
    line-height: 1.2;
  }
  .hero p {
    font-size: 1.1rem;
    color: rgba(255,255,255,0.75);
    margin: 0;
    font-weight: 300;
  }
  .hero .badge {
    display: inline-block;
    background: rgba(224,123,57,0.2);
    color: #e07b39;
    border: 1px solid rgba(224,123,57,0.4);
    border-radius: 100px;
    padding: 4px 14px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-bottom: 1rem;
    letter-spacing: 0.05em;
  }

  /* ── Cards ── */
  .card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 1rem;
    transition: border-color 0.2s ease;
  }
  .card:hover { border-color: #58a6ff; }
  .card-title {
    font-size: 1rem;
    font-weight: 600;
    color: #58a6ff;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  /* ── Upload zone ── */
  .upload-card {
    background: #161b22;
    border: 2px dashed #30363d;
    border-radius: 12px;
    padding: 2rem 1.5rem;
    text-align: center;
    transition: all 0.2s;
    cursor: pointer;
  }
  .upload-card:hover { border-color: #e07b39; background: #1c2228; }
  .upload-icon { font-size: 2rem; margin-bottom: 0.5rem; }
  .upload-label {
    font-weight: 600;
    font-size: 0.95rem;
    color: #e6edf3;
    margin-bottom: 0.25rem;
  }
  .upload-sub { font-size: 0.8rem; color: #8b949e; }

  /* ── Progress bar ── */
  .progress-container { margin: 1.5rem 0; }
  .progress-stage {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.7rem 1rem;
    border-radius: 8px;
    margin-bottom: 0.5rem;
    font-size: 0.875rem;
    transition: all 0.3s;
  }
  .stage-done { background: rgba(56,139,108,0.15); color: #3fb950; }
  .stage-active { background: rgba(88,166,255,0.15); color: #58a6ff; }
  .stage-pending { background: rgba(48,54,61,0.5); color: #8b949e; }
  .stage-icon { font-size: 1rem; width: 24px; text-align: center; }

  /* ── Metric cards ── */
  .metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin: 1rem 0;
  }
  .metric-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 1rem 1.25rem;
    text-align: center;
  }
  .metric-value {
    font-size: 2rem;
    font-weight: 700;
    color: #58a6ff;
    line-height: 1;
  }
  .metric-label {
    font-size: 0.75rem;
    color: #8b949e;
    margin-top: 0.3rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  /* ── Severity badges ── */
  .badge-high { background: rgba(200,0,0,0.15); color: #f85149; border: 1px solid rgba(200,0,0,0.3); border-radius: 6px; padding: 2px 10px; font-size: 0.8rem; font-weight: 600; }
  .badge-medium { background: rgba(224,123,57,0.15); color: #e07b39; border: 1px solid rgba(224,123,57,0.3); border-radius: 6px; padding: 2px 10px; font-size: 0.8rem; font-weight: 600; }
  .badge-low { background: rgba(55,86,35,0.2); color: #3fb950; border: 1px solid rgba(55,86,35,0.4); border-radius: 6px; padding: 2px 10px; font-size: 0.8rem; font-weight: 600; }

  /* ── Download button ── */
  .stDownloadButton > button {
    background: linear-gradient(135deg, #e07b39, #c95e1a) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    padding: 0.75rem 2.5rem !important;
    width: 100% !important;
    transition: all 0.2s !important;
    letter-spacing: 0.02em !important;
  }
  .stDownloadButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(224,123,57,0.35) !important;
  }

  /* ── File uploader ── */
  [data-testid="stFileUploader"] {
    background: #161b22;
    border: 2px dashed #30363d;
    border-radius: 12px;
    padding: 1rem;
  }
  [data-testid="stFileUploader"]:hover { border-color: #e07b39; }

  /* ── Button ── */
  div.stButton > button {
    background: linear-gradient(135deg, #2e5299, #1a3a6e) !important;
    color: white !important;
    border: 1px solid rgba(88,166,255,0.3) !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.6rem 2rem !important;
    width: 100% !important;
    transition: all 0.2s !important;
  }
  div.stButton > button:hover {
    background: linear-gradient(135deg, #3a68bd, #2249a0) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(46,82,153,0.4) !important;
  }

  /* ── Tabs ── */
  .stTabs [data-baseweb="tab-list"] { background: #161b22; border-radius: 10px; padding: 4px; }
  .stTabs [data-baseweb="tab"] { border-radius: 8px; color: #8b949e; font-weight: 500; }
  .stTabs [aria-selected="true"] { background: #2e5299 !important; color: white !important; }

  /* ── Tables ── */
  .stDataFrame { border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }

  /* ── Alert boxes ── */
  .alert-warning {
    background: rgba(224,123,57,0.1);
    border: 1px solid rgba(224,123,57,0.3);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    color: #e07b39;
    font-size: 0.875rem;
  }
  .alert-error {
    background: rgba(200,0,0,0.1);
    border: 1px solid rgba(200,0,0,0.3);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    color: #f85149;
    font-size: 0.875rem;
  }
  .alert-success {
    background: rgba(63,185,80,0.1);
    border: 1px solid rgba(63,185,80,0.3);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    color: #3fb950;
    font-size: 0.875rem;
  }

  /* ── Divider ── */
  hr { border-color: #30363d !important; margin: 1.5rem 0 !important; }

  /* ── Scrollbar ── */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: #0d1117; }
  ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #484f58; }
</style>
""", unsafe_allow_html=True)

# ─── Session State Init ───────────────────────────────────────────────────────
if "job_id"   not in st.session_state: st.session_state.job_id   = None
if "job_done" not in st.session_state: st.session_state.job_done = False
if "preview"  not in st.session_state: st.session_state.preview  = None
if "docx_bytes" not in st.session_state: st.session_state.docx_bytes = None

# ─── Helpers ──────────────────────────────────────────────────────────────────

def api_post_generate(inspection_bytes, inspection_name, thermal_bytes, thermal_name, skip_vision):
    """Submit generate job to FastAPI."""
    files = {
        "inspection_pdf": (inspection_name, inspection_bytes, "application/pdf"),
        "thermal_pdf":    (thermal_name,    thermal_bytes,    "application/pdf"),
    }
    resp = requests.post(
        f"{API_BASE}/generate",
        files=files,
        params={"skip_vision": str(skip_vision).lower()},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def api_get_status(job_id):
    resp = requests.get(f"{API_BASE}/status/{job_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def api_get_preview(job_id):
    resp = requests.get(f"{API_BASE}/preview/{job_id}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def api_download(job_id):
    resp = requests.get(f"{API_BASE}/download/{job_id}", timeout=30)
    resp.raise_for_status()
    return resp.content


def check_api_health():
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=3)
        return resp.status_code == 200
    except:
        return False


STAGE_LABELS = [
    ("⚙️", "Initializing pipeline"),
    ("📄", "Extracting inspection report"),
    ("🌡️", "Extracting thermal data"),
    ("🔗", "Linking thermal → areas"),
    ("👁️",  "Analyzing images with AI"),
    ("✍️", "Generating DDR sections"),
    ("📝", "Assembling Word document"),
    ("✅", "Complete"),
]


def render_stages(current_stage: int, pct: int):
    """Render animated stage progress tracker."""
    st.markdown('<div class="progress-container">', unsafe_allow_html=True)
    for i, (icon, label) in enumerate(STAGE_LABELS):
        if i < current_stage:
            cls = "stage-done"
            status_icon = "✅"
        elif i == current_stage:
            cls = "stage-active"
            status_icon = "⏳"
        else:
            cls = "stage-pending"
            status_icon = "○"
        st.markdown(
            f'<div class="progress-stage {cls}">'
            f'  <span class="stage-icon">{status_icon}</span>'
            f'  <span>{icon} {label}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown('</div>', unsafe_allow_html=True)
    st.progress(pct / 100, text=f"{pct}% complete")


def render_metrics(preview: dict):
    """Show key extraction metrics."""
    stats = preview.get("statistics", {})
    st.markdown(f"""
    <div class="metric-grid">
      <div class="metric-card">
        <div class="metric-value">{len(preview.get('areas', []))}</div>
        <div class="metric-label">Areas Found</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{preview.get('observations_count', 0)}</div>
        <div class="metric-label">Observations</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{len(preview.get('thermal_readings', []))}</div>
        <div class="metric-label">Thermal Readings</div>
      </div>
      <div class="metric-card">
        <div class="metric-value">{stats.get('matched', 0)}</div>
        <div class="metric-label">Links Matched</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ─── Main App ─────────────────────────────────────────────────────────────────

# Hero
st.markdown("""
<div class="hero">
  <div class="badge">AI-POWERED DIAGNOSTICS</div>
  <h1>🏗️ DDR Report Generator</h1>
  <p>Upload your inspection and thermal PDF reports — our AI pipeline extracts,
  links, validates, and generates a professional Detailed Diagnostic Report in seconds.</p>
</div>
""", unsafe_allow_html=True)

# API health check
api_ok = check_api_health()
if not api_ok:
    st.markdown("""
    <div class="alert-error">
      ⚠️ <strong>FastAPI server is not running.</strong>
      Please start it with: <code>uvicorn server:app --reload --port 8000</code>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ─── Upload Section ───────────────────────────────────────────────────────────
if not st.session_state.job_id:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="card">
          <div class="card-title">📄 Inspection Report PDF</div>
        </div>
        """, unsafe_allow_html=True)
        inspection_file = st.file_uploader(
            "Upload Inspection PDF",
            type=["pdf"],
            key="inspection_upload",
            label_visibility="collapsed",
        )
        if inspection_file:
            st.success(f"✅ {inspection_file.name} ({inspection_file.size // 1024} KB)")

    with col2:
        st.markdown("""
        <div class="card">
          <div class="card-title">🌡️ Thermal Images PDF</div>
        </div>
        """, unsafe_allow_html=True)
        thermal_file = st.file_uploader(
            "Upload Thermal PDF",
            type=["pdf"],
            key="thermal_upload",
            label_visibility="collapsed",
        )
        if thermal_file:
            st.success(f"✅ {thermal_file.name} ({thermal_file.size // 1024} KB)")

    st.markdown("<br>", unsafe_allow_html=True)

    col_opt, col_btn = st.columns([1, 2])
    with col_opt:
        skip_vision = st.checkbox(
            "⚡ Skip Vision API (faster, no image AI)",
            help="Skip GPT-4o mini Vision calls. Useful for testing or if you don't have an OpenAI key.",
        )
    with col_btn:
        generate_clicked = st.button(
            "🚀 Generate DDR Report",
            disabled=not (inspection_file and thermal_file),
            type="primary",
        )

    if generate_clicked and inspection_file and thermal_file:
        with st.spinner("Submitting to API..."):
            try:
                resp = api_post_generate(
                    inspection_bytes = inspection_file.read(),
                    inspection_name  = inspection_file.name,
                    thermal_bytes    = thermal_file.read(),
                    thermal_name     = thermal_file.name,
                    skip_vision      = skip_vision,
                )
                st.session_state.job_id = resp["job_id"]
                st.rerun()
            except Exception as e:
                st.error(f"Failed to submit: {e}")


# ─── Progress & Results Section ───────────────────────────────────────────────
if st.session_state.job_id:
    job_id = st.session_state.job_id

    st.markdown(f"""
    <div class="card">
      <div class="card-title">📊 Job Status</div>
      <div style="color: #8b949e; font-size: 0.85rem; font-family: monospace;">
        Job ID: {job_id}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Poll until done
    if not st.session_state.job_done:
        status_placeholder = st.empty()
        progress_placeholder = st.empty()

        while True:
            try:
                status = api_get_status(job_id)
            except Exception as e:
                st.error(f"Failed to poll status: {e}")
                break

            pct   = status.get("progress", 0)
            msg   = status.get("message", "")
            stage = status.get("stage_index", 0)
            state = status.get("status", "running")

            with progress_placeholder.container():
                render_stages(stage, pct)
                st.caption(f"💬 {msg}")

            if state == "done":
                st.session_state.job_done = True
                # Fetch preview + docx
                try:
                    st.session_state.preview = api_get_preview(job_id)
                    st.session_state.docx_bytes = api_download(job_id)
                except Exception as e:
                    st.warning(f"Could not fetch results: {e}")
                break

            if state == "failed":
                st.error("❌ Pipeline failed. Check errors below.")
                errs = status.get("errors", [])
                for err in errs:
                    st.error(f"• {err}")
                break

            time.sleep(2)
            st.rerun()

    # ─── Results Panel ────────────────────────────────────────────────────────
    if st.session_state.job_done and st.session_state.preview:
        preview = st.session_state.preview

        st.markdown("""
        <div class="alert-success">
          ✅ <strong>DDR Report generated successfully!</strong> Review the findings below and download your report.
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # Metrics
        render_metrics(preview)

        # Download button
        if st.session_state.docx_bytes:
            st.download_button(
                label="📥 Download DDR Report (.docx)",
                data=st.session_state.docx_bytes,
                file_name=f"DDR_Report_{job_id[:8]}.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # Tabs for detailed preview
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "🏠 Areas & Observations",
            "🌡️ Thermal Readings",
            "🔗 Links & Matching",
            "📋 Summary Table",
            "⚠️ Conflicts & Warnings",
        ])

        # ── Tab 1: Areas ──────────────────────────────────────────────────────
        with tab1:
            areas = preview.get("areas", [])
            observations_by_area = {}  # group later from full preview

            if areas:
                for area in areas:
                    st.markdown(f"""
                    <div class="card" style="padding: 1rem 1.25rem;">
                      <div style="font-weight: 600; color: #e6edf3;">
                        🏠 Area {area.get('area_id')}: {area.get('name', 'Unknown')}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No areas extracted. Check the inspection PDF format.")

        # ── Tab 2: Thermal Readings ───────────────────────────────────────────
        with tab2:
            readings = preview.get("thermal_readings", [])
            if readings:
                df = pd.DataFrame(readings)
                # Rename columns for display
                df = df.rename(columns={
                    "reading_id": "ID",
                    "location": "Location",
                    "hotspot_temp": "Hotspot (°C)",
                    "coldspot_temp": "Coldspot (°C)",
                    "anomaly_type": "Anomaly Type",
                })
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No thermal readings extracted.")

        # ── Tab 3: Links ─────────────────────────────────────────────────────
        with tab3:
            links = preview.get("links", [])
            if links:
                df = pd.DataFrame(links)
                # Color confidence column
                df["confidence"] = df["confidence"].apply(lambda x: f"{x:.0%}")
                df = df.rename(columns={
                    "thermal_id": "Thermal ID",
                    "area_name":  "Linked Area",
                    "confidence": "Confidence",
                    "method":     "Match Method",
                })
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No links found.")

            unmatched = preview.get("unmatched_thermals", [])
            if unmatched:
                st.markdown("<br>**Unmatched Thermal Readings:**", unsafe_allow_html=True)
                for u in unmatched:
                    st.markdown(f"""
                    <div class="alert-warning">
                      ⚠️ <strong>{u.get('reading_id')}</strong> — {u.get('location', 'Unknown')}:
                      {u.get('reason', '')}
                    </div>
                    """, unsafe_allow_html=True)

        # ── Tab 4: Summary Table ──────────────────────────────────────────────
        with tab4:
            summary = preview.get("summary_table", [])
            if summary:
                df = pd.DataFrame(summary)
                df = df.rename(columns={
                    "point_no":      "Point No.",
                    "negative_area": "Negative Side (-ve)",
                    "positive_area": "Positive Side (+ve)",
                })
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("No summary table found in the inspection PDF.")

        # ── Tab 5: Conflicts & Warnings ───────────────────────────────────────
        with tab5:
            conflicts = preview.get("conflicts", [])
            warnings  = preview.get("warnings", [])
            errors    = preview.get("errors", [])

            if conflicts:
                st.subheader("🔴 Conflicts Detected")
                for c in conflicts:
                    st.markdown(f"""
                    <div class="alert-error">
                      <strong>Area: {c.get('area_name', '')}</strong><br>
                      📋 Inspection: {c.get('inspection_finding', '')}<br>
                      🌡️ Thermal: {c.get('thermal_finding', '')}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("✅ No conflicts detected between inspection and thermal data.")

            if warnings:
                st.subheader("⚠️ Warnings")
                for w in warnings:
                    st.markdown(f'<div class="alert-warning">⚠️ {w}</div>', unsafe_allow_html=True)

            if errors:
                st.subheader("❌ Errors")
                for err in errors:
                    st.markdown(f'<div class="alert-error">❌ {err}</div>', unsafe_allow_html=True)

            if not conflicts and not warnings and not errors:
                st.success("✅ All validations passed with no warnings.")

        # Restart button
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Generate Another Report"):
            st.session_state.job_id     = None
            st.session_state.job_done   = False
            st.session_state.preview    = None
            st.session_state.docx_bytes = None
            st.rerun()

# ─── Sidebar Info ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📖 How It Works")
    for i, (icon, label) in enumerate(STAGE_LABELS[:-1], 1):
        st.markdown(f"**{i}.** {icon} {label}")

    st.markdown("---")
    st.markdown("## ⚙️ API Server")
    if api_ok:
        st.success("🟢 FastAPI running at :8000")
    else:
        st.error("🔴 FastAPI not running")
    if st.button("Check API Health"):
        st.rerun()

    st.markdown("---")
    st.markdown("## 📋 Endpoints")
    st.code("""POST /generate
GET  /status/{id}
GET  /download/{id}
GET  /preview/{id}
GET  /jobs""", language="text")
