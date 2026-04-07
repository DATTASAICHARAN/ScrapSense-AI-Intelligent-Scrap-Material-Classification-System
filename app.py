import os
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

import camera
import config
import database
import preprocessor
import pdf_generator
from gemini_client import create_client

# ── UI Config ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load Custom CSS
css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── State Initialization ───────────────────────────────────────────────────────
if "gemini_key" not in st.session_state:
    st.session_state.gemini_key = config.GEMINI_API_KEY

if "camera_url" not in st.session_state:
    st.session_state.camera_url = "http://192.168.1.100:8080/video"

if "last_analysis" not in st.session_state:
    st.session_state.last_analysis = None

if "last_image" not in st.session_state:
    st.session_state.last_image = None

# Init DB
database.init_db()

# ── Helpers ────────────────────────────────────────────────────────────────────
def create_donut_chart(metal: float, non_metal: float, background: float):
    labels = ["Metal", "Non-Metal", "Background"]
    values = [metal, non_metal, background]
    colors = ["#2f81f7", "#da3633", "#484f58"]  # Using CSS variables roughly

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.65,
        marker_colors=colors,
        textinfo="percent",
        hoverinfo="label+percent",
        textfont_size=14,
        marker=dict(line=dict(color='#0a0c10', width=2))
    )])
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
        margin=dict(t=20, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#8b949e"),
        height=350,
    )
    return fig

def create_trend_chart(df: pd.DataFrame):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['metal_pct'],
        mode='lines+markers',
        name='Metal %',
        line=dict(color='#2f81f7', width=3),
        marker=dict(size=6)
    ))
    fig.add_trace(go.Scatter(
        x=df['timestamp'], y=df['non_metal_pct'],
        mode='lines',
        name='Non-Metal %',
        line=dict(color='#da3633', width=2, dash='dot')
    ))
    fig.update_layout(
        margin=dict(t=20, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#8b949e"),
        height=300,
        xaxis=dict(showgrid=False, color="#8b949e"),
        yaxis=dict(showgrid=True, gridcolor="rgba(48, 54, 61, 0.5)", color="#8b949e"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

@st.dialog("Clear History Confirmation")
def clear_history_dialog():
    st.warning("Are you sure you want to delete all scan history? This action cannot be undone.")
    c1, c2 = st.columns(2)
    if c1.button("Cancel", use_container_width=True):
        st.rerun()
    if c2.button("Yes, clear history", type="primary", use_container_width=True):
        database.clear_all()
        st.success("History cleared!")
        time.sleep(1)
        st.rerun()

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"<h1>{config.APP_ICON} {config.APP_TITLE}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='font-size: 0.85rem; color: var(--text-muted); margin-top: -10px;'>v{config.APP_VERSION}</p>", unsafe_allow_html=True)
    
    st.markdown(f"<div class='glass-card' style='margin-bottom: 20px;'><p style='margin:0;font-size:0.9rem;'>{config.APP_DESCRIPTION}</p></div>", unsafe_allow_html=True)
    
    api_key_status = "active" if st.session_state.gemini_key else "offline"
    api_key_label = "API Connected" if st.session_state.gemini_key else "Missing API Key"
    st.markdown(f"<div style='margin-bottom:20px;'><span class='pulse-indicator {api_key_status}'></span><span style='font-size:0.9rem;color:var(--text-muted);'>{api_key_label}</span></div>", unsafe_allow_html=True)
    
    st.divider()

    st.subheader("⚙️ Configuration")
    
    # API Key specific block
    api_key_input = st.text_input(
        "Gemini API Key",
        value=st.session_state.gemini_key,
        type="password",
        help="Get yours from Google AI Studio"
    )
    if api_key_input != st.session_state.gemini_key:
        st.session_state.gemini_key = api_key_input
        st.toast("✅ API Key updated!")

    camera_url_input = st.text_input(
        "IP Camera URL",
        value=st.session_state.camera_url,
        help="Use an app like 'IP Webcam' on Android"
    )
    if camera_url_input != st.session_state.camera_url:
        st.session_state.camera_url = camera_url_input

    st.divider()
    stats = database.get_stats()
    total_scans = stats.get("total_scans", 0)
    
    # Using columns for compact metrics in sidebar
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.metric("Total Scans", total_scans)
    with col_s2:
        avg_metal = stats.get("avg_metal", 0) or 0
        st.metric("Avg Metal", f"{avg_metal:.1f}%")

# ── Main Content Tabs ──────────────────────────────────────────────────────────
tab_analyze, tab_history = st.tabs(["🔍 Analyze", "📊 History Dashboard"])

# ===============================================================================
# TAB 1: ANALYZE
# ===============================================================================
with tab_analyze:
    if not st.session_state.gemini_key:
        st.warning("⚠️ Please configure your Google Gemini API Key in the sidebar to run analysis.")
        st.stop()

    # Input Mode Selection
    st.markdown("### Image Source")
    input_mode = st.radio(
        "Select Source",
        ["🖼️ Local Upload", "📷 Live Stream"],
        horizontal=True,
        label_visibility="collapsed"
    )

    ready_to_analyze = False
    source_img = None
    source_label = ""
    filename = ""

    col_input, col_preview = st.columns([1, 1], gap="large")

    with col_input:
        if input_mode == "🖼️ Local Upload":
            uploaded_file = st.file_uploader("Drag and drop scrap image here", type=["jpg", "png", "jpeg"])
            if uploaded_file is not None:
                try:
                    raw_bytes = uploaded_file.read()
                    preprocessor.validate_file(raw_bytes, uploaded_file.name)
                    source_img = Image.open(uploaded_file)
                    ready_to_analyze = True
                    source_label = "Upload"
                    filename = uploaded_file.name
                except Exception as e:
                    st.error(f"Error loading image: {e}")
            
        else: # IP Camera
            st.markdown(f"<div class='glass-card' style='margin-bottom:1rem;'><div class='detail-row'><span class='detail-label'>Target Camera:</span><span class='detail-value'>{st.session_state.camera_url}</span></div></div>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🔌 Test Connection", use_container_width=True):
                    with st.spinner("Connecting..."):
                        try:
                            if camera.CameraStream(st.session_state.camera_url).test_connection():
                                st.toast("✅ Camera connected successfully!")
                            else:
                                st.error("Connection failed.")
                        except Exception as e:
                            st.error(f"Error: {e}")
            with c2:
                if st.button("📸 Grab Frame", type="primary", use_container_width=True):
                    with st.spinner("Capturing..."):
                        try:
                            source_img = camera.grab_single_frame(st.session_state.camera_url)
                            ready_to_analyze = True
                            source_label = "IP Camera"
                            st.session_state.last_image = source_img
                        except Exception as e:
                            st.error(f"Capture failed: {e}")
            
            # Restore camera frame on re-render
            if not ready_to_analyze and st.session_state.get("last_image"):
                source_img = st.session_state.last_image
                ready_to_analyze = True
                source_label = "IP Camera"

        # Action Block
        st.markdown("<br>", unsafe_allow_html=True)
        analyze_clicked = st.button(
            "⚡ Run Analysis",
            type="primary",
            use_container_width=True,
            disabled=not ready_to_analyze
        )

    with col_preview:
        if source_img:
            st.markdown("<div style='border: 1px solid var(--border-color); border-radius: var(--radius-md); overflow: hidden; padding: 4px; background: var(--bg-card);'>", unsafe_allow_html=True)
            st.image(source_img, use_column_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown("""
                <div style='height: 300px; display: flex; align-items: center; justify-content: center; border: 2px dashed var(--border-color); border-radius: var(--radius-md); background: var(--bg-input); color: var(--text-muted);'>
                    <span>Preview Area (Awaiting Image)</span>
                </div>
            """, unsafe_allow_html=True)


    if analyze_clicked and source_img:
        st.divider()
        progress_text = "Analysis in progress..."
        prog_bar = st.progress(0, text=progress_text)
        
        try:
            # Step 1
            prog_bar.progress(20, text="Optimizing image sizing & reducing glare...")
            processed_img = preprocessor.preprocess(source_img)
            time.sleep(0.4)
            
            # Step 2
            prog_bar.progress(50, text="Transmitting to Gemini AI Core...")
            client = create_client(api_key=st.session_state.gemini_key)
            time.sleep(0.4)
            
            # Step 3
            prog_bar.progress(70, text="Segmenting materials & calculating densities...")
            result = client.analyze_image(processed_img)
            prog_bar.progress(90, text="Finalizing report...")

            if result.is_valid:
                # Save history
                db_id = database.save_scan(
                    source=source_label,
                    filename=filename,
                    metal_pct=result.metal,
                    non_metal_pct=result.non_metal,
                    background_pct=result.background,
                    dominant=result.dominant_material,
                    model_used=result.model_used,
                    confidence=result.confidence,
                    notes=result.notes
                )
                st.session_state.last_analysis = result
                prog_bar.progress(100, text="Analysis Complete!")
                time.sleep(0.5)
                prog_bar.empty()
            else:
                prog_bar.empty()
                st.error(f"Analysis failed: {result.error}")
                st.code(result.raw_response, language="json" if "{" in result.raw_response else "text")

        except Exception as e:
            prog_bar.empty()
            st.error(f"Application error during analysis: {e}")

    # Display Results
    if st.session_state.last_analysis and st.session_state.last_analysis.is_valid:
        st.divider()
        res = st.session_state.last_analysis
        
        st.markdown("### 📊 Diagnostic Results")
        
        # HTML custom badges
        conf_class = "badge-high" if res.confidence.lower() == "high" else ("badge-medium" if res.confidence.lower() == "medium" else "badge-low")
        st.markdown(f"<span class='badge {conf_class}'>Confidence: {res.confidence}</span>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Metrics
        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric("Metal Content", f"{res.metal}%", delta="Primary Target")
        with m_col2:
            st.metric("Non-Metal Content", f"{res.non_metal}%", delta="Impurities", delta_color="inverse")
        with m_col3:
            st.metric("Background", f"{res.background}%", delta="Discarded")

        c1, c2 = st.columns([1.5, 1])
        with c1:
            st.markdown("<div class='glass-card' style='height:100%;'>", unsafe_allow_html=True)
            st.plotly_chart(create_donut_chart(res.metal, res.non_metal, res.background), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
        with c2:
            st.markdown(f"""
            <div class='glass-card' style='height:100%;'>
                <h4 style='margin-top:0;'>Composition Details</h4>
                <div class='detail-row'>
                    <span class='detail-label'>Dominant Material</span>
                    <span class='detail-value'>{res.dominant_material}</span>
                </div>
                <div class='detail-row'>
                    <span class='detail-label'>AI Model</span>
                    <span class='detail-value'>{res.model_used}</span>
                </div>
                <div class='quote-block'>
                    {res.notes}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        # Build comprehensive report payload
        pdf_bytes = pdf_generator.generate_individual_report({
            "dominant_material": res.dominant_material,
            "dominant_confidence": max([res.metal, res.non_metal, res.background]),
            "confidence": res.confidence,
            "model_used": res.model_used,
            "composition": {
                "metals": res.metal,
                "non_metal": res.non_metal,
                "background": res.background
            },
            "analysis_notes": res.notes
        }, source_img=source_img)
        st.download_button(
            label="📄 Download Detailed PDF Report",
            data=pdf_bytes,
            file_name=f"scrap_analysis_{int(time.time())}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )


# ===============================================================================
# TAB 2: HISTORY
# ===============================================================================
with tab_history:
    
    total_records = database.get_total_count()
    if total_records == 0:
        st.info("No scans recorded yet. Run an analysis in the Analyze tab to see data here.")
    else:
        # Action Bar
        hc1, hc2, hc3, hc4 = st.columns([2, 1, 1, 1])
        with hc1:
            st.markdown("### 📈 Analytics Dashboard")
        with hc2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🗑️ Clear History", use_container_width=True):
                clear_history_dialog()
        with hc3:
            st.markdown("<br>", unsafe_allow_html=True)
            try:
                excel_data = database.export_to_excel()
                st.download_button(
                    label="📥 Export .xlsx",
                    data=excel_data,
                    file_name=f"scrap_history_{int(time.time())}.xlsx",
                    use_container_width=True
                )
            except Exception as e:
                st.warning(f"Could not export Excel: {e}")
        with hc4:
            st.markdown("<br>", unsafe_allow_html=True)
            try:
                history_data = database.get_history(limit=500)
                if history_data:
                    pdf_bytes_hist = pdf_generator.generate_history_report(history_data)
                    st.download_button(
                        label="📄 Export .pdf",
                        data=pdf_bytes_hist,
                        file_name=f"scrap_history_{int(time.time())}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
            except Exception as e:
                st.warning(f"Could not generate PDF: {e}")

        # Mini-dashboard
        stats = database.get_stats()
        h_col1, h_col2, h_col3 = st.columns(3)
        with h_col1:
            st.markdown(f"""
            <div class='glass-card'>
                <div class='detail-label'>Total Processed</div>
                <div style='font-size:2rem;font-weight:700;'>{stats.get('total_scans', 0)}</div>
            </div>
            """, unsafe_allow_html=True)
        with h_col2:
            st.markdown(f"""
            <div class='glass-card'>
                <div class='detail-label'>Peak Metal Purity</div>
                <div style='font-size:2rem;font-weight:700;color:var(--accent-primary);'>{stats.get('max_metal', 0)}%</div>
            </div>
            """, unsafe_allow_html=True)
        with h_col3:
            st.markdown(f"""
            <div class='glass-card'>
                <div class='detail-label'>Average Purity</div>
                <div style='font-size:2rem;font-weight:700;'>{stats.get('avg_metal', 0):.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Trend Chart
        history_data = database.get_history(limit=50)
        df = pd.DataFrame(history_data)
        
        if not df.empty and len(df) > 1:
            st.markdown("#### Purity Trend (Last 50 Scans)")
            st.plotly_chart(create_trend_chart(df), use_container_width=True)

        st.markdown("#### Scan Logs")
        
        # Formatting dataframe for display
        display_df = df[["id", "timestamp", "source", "metal_pct", "non_metal_pct", "confidence"]].copy()
        display_df.rename(columns={
            "id": "ID", "timestamp": "Date/Time", "source": "Source", 
            "metal_pct": "Metal %", "non_metal_pct": "Non-Metal %", "confidence": "Confidence"
        }, inplace=True)
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
