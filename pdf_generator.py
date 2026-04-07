"""
pdf_generator.py — Rich PDF report generation with embedded charts & images.

Uses fpdf2 for layout and matplotlib (Agg backend) for chart rendering.
All charts are rendered to in-memory PNG buffers and embedded into the PDF.
"""
from __future__ import annotations

import io
import math
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend — safe for server use
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from fpdf import FPDF
from PIL import Image

# ── Brand palette ──────────────────────────────────────────────────────────────
DARK        = (31, 35, 41)
WHITE       = (255, 255, 255)
ACCENT      = (99, 102, 241)   # Indigo-500
METAL_CLR   = (231, 76, 60)    # Crimson red
NONMETAL_CLR= (52, 152, 219)   # Sky blue
BG_CLR      = (149, 165, 166)  # Slate gray
LIGHT_FILL  = (245, 247, 250)
BORDER      = (220, 220, 220)
TEXT_DARK    = (40, 40, 40)
TEXT_MUTED   = (120, 120, 120)

# ── Chart helpers (matplotlib → PNG bytes) ─────────────────────────────────────

def _fig_to_png_bytes(fig) -> bytes:
    """Render a matplotlib figure to an in-memory PNG buffer."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=180, bbox_inches="tight",
                facecolor="#FAFBFD", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _make_donut_chart(metal: float, non_metal: float, background: float) -> bytes:
    """Generate a donut (ring) pie chart and return PNG bytes."""
    labels = ["Metals", "Non-Metals", "Background"]
    sizes  = [metal, non_metal, background]
    colors = [
        f"#{METAL_CLR[0]:02x}{METAL_CLR[1]:02x}{METAL_CLR[2]:02x}",
        f"#{NONMETAL_CLR[0]:02x}{NONMETAL_CLR[1]:02x}{NONMETAL_CLR[2]:02x}",
        f"#{BG_CLR[0]:02x}{BG_CLR[1]:02x}{BG_CLR[2]:02x}",
    ]
    explode = (0.03, 0.03, 0.03)

    fig, ax = plt.subplots(figsize=(4, 4))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors, explode=explode,
        autopct=lambda p: f"{p:.1f}%" if p > 0.5 else "",
        startangle=140, pctdistance=0.75,
        textprops={"fontsize": 9, "fontweight": "bold"},
        wedgeprops={"width": 0.45, "edgecolor": "white", "linewidth": 2},
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_color("white")
        at.set_fontweight("bold")

    # Centre label
    ax.text(0, 0, f"{metal:.0f}%\nMetal", ha="center", va="center",
            fontsize=14, fontweight="bold", color="#1F2329")
    ax.set_title("Material Composition", fontsize=12, fontweight="bold",
                 pad=12, color="#1F2329")
    return _fig_to_png_bytes(fig)


def _make_horizontal_bar(metal: float, non_metal: float, background: float) -> bytes:
    """Generate a horizontal stacked bar chart and return PNG bytes."""
    categories = ["Metals", "Non-Metals", "Background"]
    values = [metal, non_metal, background]
    colors = [
        f"#{METAL_CLR[0]:02x}{METAL_CLR[1]:02x}{METAL_CLR[2]:02x}",
        f"#{NONMETAL_CLR[0]:02x}{NONMETAL_CLR[1]:02x}{NONMETAL_CLR[2]:02x}",
        f"#{BG_CLR[0]:02x}{BG_CLR[1]:02x}{BG_CLR[2]:02x}",
    ]

    fig, ax = plt.subplots(figsize=(5.5, 2.2))
    bars = ax.barh(categories, values, color=colors, height=0.55,
                   edgecolor="white", linewidth=1.5)
    for bar, val in zip(bars, values):
        ax.text(bar.get_width() + 1.2, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}%", va="center", fontsize=10, fontweight="bold",
                color="#1F2329")
    ax.set_xlim(0, 110)
    ax.set_xlabel("Percentage (%)", fontsize=9, color="#666")
    ax.set_title("Composition Breakdown", fontsize=11, fontweight="bold",
                 color="#1F2329", pad=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=10)
    ax.tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def _make_history_trend(history: list[dict]) -> bytes:
    """Generate a line chart showing metal % trend over recent scans."""
    # history is newest-first; reverse for chronological order
    ordered = list(reversed(history))
    indices = list(range(1, len(ordered) + 1))
    metals = [r.get("metal_pct", 0) for r in ordered]
    non_metals = [r.get("non_metal_pct", 0) for r in ordered]

    fig, ax = plt.subplots(figsize=(6, 2.8))
    ax.plot(indices, metals, color=f"#{METAL_CLR[0]:02x}{METAL_CLR[1]:02x}{METAL_CLR[2]:02x}",
            marker="o", markersize=4, linewidth=2, label="Metal %")
    ax.plot(indices, non_metals, color=f"#{NONMETAL_CLR[0]:02x}{NONMETAL_CLR[1]:02x}{NONMETAL_CLR[2]:02x}",
            marker="s", markersize=4, linewidth=2, label="Non-Metal %")
    ax.fill_between(indices, metals, alpha=0.12, color=f"#{METAL_CLR[0]:02x}{METAL_CLR[1]:02x}{METAL_CLR[2]:02x}")
    ax.set_xlabel("Scan #", fontsize=9, color="#666")
    ax.set_ylabel("Percentage (%)", fontsize=9, color="#666")
    ax.set_title("Purity Trend (Recent Scans)", fontsize=11, fontweight="bold",
                 color="#1F2329", pad=10)
    ax.legend(fontsize=8, loc="upper right")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_ylim(0, 105)
    ax.tick_params(labelsize=8)
    fig.tight_layout()
    return _fig_to_png_bytes(fig)


def _make_material_distribution_pie(history: list[dict]) -> bytes:
    """Pie chart of dominant material distribution across all scans."""
    from collections import Counter
    materials = [r.get("dominant", "Unknown") for r in history]
    counts = Counter(materials)
    labels = list(counts.keys())
    sizes = list(counts.values())

    # Use a nice palette
    cmap = plt.cm.Set2
    colors = [cmap(i / max(len(labels), 1)) for i in range(len(labels))]

    fig, ax = plt.subplots(figsize=(4, 3.5))
    wedges, texts, autotexts = ax.pie(
        sizes, labels=labels, colors=colors,
        autopct=lambda p: f"{p:.0f}%" if p > 3 else "",
        startangle=90, textprops={"fontsize": 9},
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    for at in autotexts:
        at.set_fontsize(9)
        at.set_fontweight("bold")
    ax.set_title("Material Type Distribution", fontsize=11, fontweight="bold",
                 color="#1F2329", pad=10)
    return _fig_to_png_bytes(fig)


# ── PDF base class ─────────────────────────────────────────────────────────────

class ScrapVisionPDF(FPDF):
    """Custom PDF with branded header, footer, and helper drawing methods."""

    def header(self):
        # Dark banner
        self.set_fill_color(*DARK)
        self.rect(0, 0, 210, 28, style="F")
        # Logo text
        self.set_font("helvetica", "B", 16)
        self.set_text_color(*WHITE)
        self.set_y(5)
        self.cell(0, 10, "ScrapVision AI", align="C")
        self.ln(8)
        self.set_font("helvetica", "", 9)
        self.set_text_color(200, 200, 210)
        self.cell(0, 6, "Intelligent Scrap Material Analysis Report", align="C")
        self.ln(18)

    def footer(self):
        self.set_y(-14)
        self.set_font("helvetica", "I", 7)
        self.set_text_color(*TEXT_MUTED)
        self.cell(0, 6, f"Generated by ScrapVision AI  |  Page {self.page_no()}/{{nb}}  |  Confidential",
                  align="C")

    # ── Drawing primitives ──

    def section_title(self, title: str):
        """Draw a bold section heading with accent underline."""
        self.set_font("helvetica", "B", 13)
        self.set_text_color(*DARK)
        self.cell(0, 10, title, ln=True)
        # Accent underline
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.8)
        self.line(self.get_x(), self.get_y(), self.get_x() + 55, self.get_y())
        # Reset
        self.set_draw_color(*BORDER)
        self.set_line_width(0.3)
        self.ln(5)

    def sub_heading(self, text: str):
        self.set_font("helvetica", "B", 11)
        self.set_text_color(*TEXT_DARK)
        self.cell(0, 8, text, ln=True)
        self.ln(2)

    def info_row(self, label: str, value: str):
        """Key-value row with label on the left and value on the right."""
        self.set_x(10)  # Reset to left margin
        self.set_font("helvetica", "B", 10)
        self.set_text_color(*TEXT_MUTED)
        self.cell(55, 7, label)
        self.set_font("helvetica", "", 10)
        self.set_text_color(*TEXT_DARK)
        self.multi_cell(135, 7, str(value))

    def colored_badge(self, text: str, color: tuple):
        """Draw a rounded coloured badge inline."""
        self.set_fill_color(*color)
        self.set_text_color(*WHITE)
        self.set_font("helvetica", "B", 10)
        w = self.get_string_width(text) + 10
        self.cell(w, 8, f"  {text}  ", ln=False, fill=True)
        self.set_text_color(*TEXT_DARK)

    def separator(self):
        self.ln(3)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def embed_chart(self, png_bytes: bytes, w: int = 170):
        """Embed a PNG chart (from matplotlib bytes) centred on the page."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(png_bytes)
            tmp_path = tmp.name
        try:
            self.image(tmp_path, x="C", w=w)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        self.ln(4)


# ═══════════════════════════════════════════════════════════════════════════════
# INDIVIDUAL ANALYSIS REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def generate_individual_report(result: dict, source_img=None) -> bytes:
    """
    Build a multi-page, richly illustrated PDF for a single scan.

    Parameters
    ----------
    result : dict
        Keys: dominant_material, dominant_confidence, composition{metals,
        non_metal, background}, analysis_notes, model_used, confidence
    source_img : PIL.Image.Image | None
        The original uploaded image to embed.
    """
    pdf = ScrapVisionPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    timestamp = datetime.now().strftime("%B %d, %Y  |  %H:%M:%S")
    comp = result.get("composition", {})
    metals     = comp.get("metals", 0)
    non_metals = comp.get("non_metal", 0)
    background = comp.get("background", 0)
    dominant   = result.get("dominant_material", "N/A")
    confidence_val = result.get("dominant_confidence", 0)
    confidence_str = result.get("confidence", "")
    model      = result.get("model_used", "Gemini AI")
    notes      = result.get("analysis_notes", "No additional notes.")

    # ─── Section 1: Report Metadata ───────────────────────────────────────
    pdf.section_title("Report Information")
    pdf.info_row("Report ID:", f"SV-{int(datetime.now().timestamp())}")
    pdf.info_row("Generated:", timestamp)
    pdf.info_row("AI Model:", model)
    pdf.info_row("Analysis Type:", "Scrap Material Classification")
    pdf.ln(2)

    # ─── Section 2: Analysed Image ────────────────────────────────────────
    if source_img is not None:
        pdf.section_title("Analysed Image")
        # Save PIL image to a temp file for fpdf2
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
            # Convert to RGB if needed (handles RGBA)
            if isinstance(source_img, Image.Image):
                img_to_save = source_img.convert("RGB") if source_img.mode != "RGB" else source_img
                img_to_save.save(tmp_path, format="PNG")
            else:
                # Already a file path or bytes
                with open(tmp_path, "wb") as f:
                    f.write(source_img if isinstance(source_img, bytes) else b"")
        try:
            # Add thin border around image
            img_x = (210 - 100) / 2   # centre for w=100
            pdf.set_draw_color(*BORDER)
            pdf.set_line_width(0.5)
            # Get image dimensions to calculate height
            with Image.open(tmp_path) as pimg:
                aspect = pimg.height / pimg.width
            img_h = 100 * aspect
            pdf.rect(img_x - 1, pdf.get_y() - 1, 102, img_h + 2)
            pdf.image(tmp_path, x=img_x, w=100)
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        pdf.ln(6)

    # ─── Section 3: Classification Result ─────────────────────────────────
    pdf.section_title("Classification Result")

    # Dominant material badge
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(*TEXT_MUTED)
    pdf.cell(55, 8, "Dominant Material:")

    # Pick badge colour based on material
    mat_lower = dominant.lower()
    if "metal" in mat_lower and "non" not in mat_lower:
        badge_clr = METAL_CLR
    elif "non" in mat_lower:
        badge_clr = NONMETAL_CLR
    else:
        badge_clr = BG_CLR
    pdf.colored_badge(dominant, badge_clr)
    pdf.ln(10)

    pdf.info_row("Confidence Level:", confidence_str if confidence_str else f"{confidence_val:.1f}%")

    # Grading
    if confidence_val >= 80:
        grade, grade_clr = "A - High Purity", (39, 174, 96)
    elif confidence_val >= 60:
        grade, grade_clr = "B - Moderate Purity", (243, 156, 18)
    elif confidence_val >= 40:
        grade, grade_clr = "C - Mixed Composition", (230, 126, 34)
    else:
        grade, grade_clr = "D - Low Purity / Background-Dominant", METAL_CLR

    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(*TEXT_MUTED)
    pdf.cell(55, 8, "Quality Grade:")
    pdf.colored_badge(grade, grade_clr)
    pdf.ln(8)
    pdf.separator()

    # ─── Section 4: Graphical Composition ─────────────────────────────────
    pdf.section_title("Graphical Composition Analysis")

    # Donut chart
    donut_png = _make_donut_chart(metals, non_metals, background)
    pdf.embed_chart(donut_png, w=110)

    # Check remaining space; add page if needed
    if pdf.get_y() > 200:
        pdf.add_page()

    # Horizontal bar chart
    hbar_png = _make_horizontal_bar(metals, non_metals, background)
    pdf.embed_chart(hbar_png, w=150)

    # ─── Section 5: Composition Data Table ────────────────────────────────
    if pdf.get_y() > 230:
        pdf.add_page()

    pdf.section_title("Detailed Composition Data")

    # Table header
    col_widths = [60, 45, 45, 40]
    headers    = ["Material", "Percentage", "Proportion", "Status"]
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(*WHITE)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 9, h, border=1, fill=True, align="C")
    pdf.ln()

    # Data rows
    rows = [
        ("Metallic Content",  metals,     "Primary Target"   if metals > non_metals else "Secondary"),
        ("Non-Metallic",      non_metals, "Impurity"         if non_metals < metals else "Dominant"),
        ("Background Noise",  background, "Noise / Substrate"),
    ]
    colors_row = [METAL_CLR, NONMETAL_CLR, BG_CLR]

    for idx, (mat_name, pct, status) in enumerate(rows):
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(*TEXT_DARK)
        fill = idx % 2 == 0
        if fill:
            pdf.set_fill_color(*LIGHT_FILL)
        pdf.cell(col_widths[0], 9, mat_name, border=1, fill=fill)
        pdf.cell(col_widths[1], 9, f"{pct:.1f}%", border=1, align="C", fill=fill)
        pdf.cell(col_widths[2], 9, f"{pct / 100:.3f}", border=1, align="C", fill=fill)
        pdf.cell(col_widths[3], 9, status, border=1, align="C", fill=fill)
        pdf.ln()

    # Total row
    pdf.set_font("helvetica", "B", 10)
    pdf.set_fill_color(*LIGHT_FILL)
    pdf.cell(col_widths[0], 9, "TOTAL", border=1, fill=True)
    pdf.cell(col_widths[1], 9, f"{metals + non_metals + background:.1f}%",
             border=1, align="C", fill=True)
    pdf.cell(col_widths[2], 9, "1.000", border=1, align="C", fill=True)
    pdf.cell(col_widths[3], 9, "-", border=1, align="C", fill=True)
    pdf.ln(10)

    # ─── Section 6: Analysis Notes ────────────────────────────────────────
    if pdf.get_y() > 240:
        pdf.add_page()

    pdf.section_title("AI Analysis Notes")
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*TEXT_DARK)
    # Light background block for notes
    note_x = pdf.get_x()
    note_y = pdf.get_y()
    pdf.set_fill_color(248, 249, 252)
    # Multi-cell draws the content; we wrap in a rect afterwards
    start_y = pdf.get_y()
    pdf.set_x(15)
    pdf.multi_cell(180, 7, notes)
    end_y = pdf.get_y()
    # Draw background rect behind the text (using overlay trick)
    # Since fpdf draws sequentially, we accept the text on white for now
    pdf.ln(6)

    # ─── Section 7: Recommendations ───────────────────────────────────────
    pdf.section_title("Processing Recommendations")
    recommendations = _generate_recommendations(metals, non_metals, background, dominant)
    for i, rec in enumerate(recommendations, 1):
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(*ACCENT)
        pdf.cell(8, 7, f"{i}.")
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(*TEXT_DARK)
        pdf.multi_cell(0, 7, rec)
        pdf.ln(1)

    # ─── Disclaimer ───────────────────────────────────────────────────────
    pdf.ln(8)
    pdf.separator()
    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(*TEXT_MUTED)
    pdf.multi_cell(0, 5,
        "Disclaimer: This report is generated by an AI-powered analysis system. "
        "Results are probabilistic estimates and should be verified by qualified "
        "personnel before making processing or recycling decisions. "
        "ScrapVision AI does not guarantee absolute accuracy of material classification."
    )

    return bytes(pdf.output())


# ═══════════════════════════════════════════════════════════════════════════════
# HISTORY REPORT
# ═══════════════════════════════════════════════════════════════════════════════

def generate_history_report(history_data: list[dict]) -> bytes:
    """
    Build a comprehensive multi-page history report with summary stats,
    trend chart, material distribution pie, and a full scan log table.
    """
    pdf = ScrapVisionPDF()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    timestamp = datetime.now().strftime("%B %d, %Y  |  %H:%M:%S")
    total = len(history_data)

    # ─── Summary ──────────────────────────────────────────────────────────
    pdf.section_title("Report Summary")
    pdf.info_row("Report Generated:", timestamp)
    pdf.info_row("Total Scans Analysed:", str(total))

    if total > 0:
        metals_list = [r.get("metal_pct", 0) for r in history_data]
        avg_metal = sum(metals_list) / total
        max_metal = max(metals_list)
        min_metal = min(metals_list)

        pdf.info_row("Average Metal Purity:", f"{avg_metal:.1f}%")
        pdf.info_row("Peak Metal Purity:", f"{max_metal:.1f}%")
        pdf.info_row("Lowest Metal Purity:", f"{min_metal:.1f}%")
    pdf.ln(4)

    # ─── Key metrics boxes ────────────────────────────────────────────────
    if total > 0:
        pdf.section_title("Key Performance Indicators")
        box_w = 60
        box_h = 22
        start_x = 10
        gap = 5

        kpis = [
            ("Total Scans", str(total), ACCENT),
            ("Avg. Metal %", f"{avg_metal:.1f}%", METAL_CLR),
            ("Peak Metal %", f"{max_metal:.1f}%", (39, 174, 96)),
        ]
        for i, (label, value, color) in enumerate(kpis):
            x = start_x + i * (box_w + gap)
            y = pdf.get_y()
            pdf.set_fill_color(*color)
            pdf.set_draw_color(*color)
            pdf.rect(x, y, box_w, box_h, style="FD")
            pdf.set_xy(x, y + 3)
            pdf.set_font("helvetica", "", 8)
            pdf.set_text_color(*WHITE)
            pdf.cell(box_w, 5, label, align="C")
            pdf.set_xy(x, y + 10)
            pdf.set_font("helvetica", "B", 14)
            pdf.cell(box_w, 8, value, align="C")

        pdf.set_y(pdf.get_y() + box_h + 8)
        pdf.set_text_color(*TEXT_DARK)

    # ─── Trend Chart ──────────────────────────────────────────────────────
    if total > 1:
        pdf.section_title("Purity Trend Over Time")
        trend_png = _make_history_trend(history_data[:50])  # last 50
        pdf.embed_chart(trend_png, w=170)

    # ─── Material Distribution ────────────────────────────────────────────
    if total > 0:
        if pdf.get_y() > 180:
            pdf.add_page()
        pdf.section_title("Material Type Distribution")
        dist_png = _make_material_distribution_pie(history_data)
        pdf.embed_chart(dist_png, w=120)

    # ─── Full Scan Log Table ──────────────────────────────────────────────
    pdf.add_page()
    pdf.section_title("Complete Scan Log")

    col_w = [10, 38, 28, 28, 28, 30, 28]
    hdrs  = ["#", "Timestamp", "Source", "Metal %", "Non-Met %", "Dominant", "Confidence"]
    pdf.set_font("helvetica", "B", 8)
    pdf.set_fill_color(*DARK)
    pdf.set_text_color(*WHITE)
    for i, h in enumerate(hdrs):
        pdf.cell(col_w[i], 8, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font("helvetica", "", 8)
    for idx, record in enumerate(history_data):
        if pdf.get_y() > 270:
            pdf.add_page()
            # Reprint header
            pdf.set_font("helvetica", "B", 8)
            pdf.set_fill_color(*DARK)
            pdf.set_text_color(*WHITE)
            for i, h in enumerate(hdrs):
                pdf.cell(col_w[i], 8, h, border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_font("helvetica", "", 8)

        fill = idx % 2 == 0
        if fill:
            pdf.set_fill_color(*LIGHT_FILL)
        pdf.set_text_color(*TEXT_DARK)

        ts_raw  = str(record.get("timestamp", ""))[:16]
        source  = record.get("source", "")
        m_pct   = f"{record.get('metal_pct', 0):.1f}"
        nm_pct  = f"{record.get('non_metal_pct', 0):.1f}"
        dom     = record.get("dominant", "")[:14]
        conf    = record.get("confidence", "")

        pdf.cell(col_w[0], 7, str(idx + 1), border=1, fill=fill, align="C")
        pdf.cell(col_w[1], 7, ts_raw,       border=1, fill=fill, align="C")
        pdf.cell(col_w[2], 7, source,        border=1, fill=fill, align="C")
        pdf.cell(col_w[3], 7, m_pct,         border=1, fill=fill, align="R")
        pdf.cell(col_w[4], 7, nm_pct,        border=1, fill=fill, align="R")
        pdf.cell(col_w[5], 7, dom,           border=1, fill=fill, align="C")
        pdf.cell(col_w[6], 7, conf,          border=1, fill=fill, align="C")
        pdf.ln()

    # ─── Disclaimer ───────────────────────────────────────────────────────
    pdf.ln(10)
    pdf.separator()
    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(*TEXT_MUTED)
    pdf.multi_cell(0, 5,
        "This historical report is auto-generated by ScrapVision AI. "
        "Data reflects past scan results and is subject to the accuracy of the "
        "underlying AI classification model at the time of each scan."
    )

    return bytes(pdf.output())


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _generate_recommendations(metal: float, non_metal: float, background: float,
                               dominant: str) -> list[str]:
    """Generate context-aware processing recommendations based on composition."""
    recs = []
    if metal >= 80:
        recs.append("High metal purity detected. This batch is suitable for direct smelting or refining with minimal pre-processing.")
        recs.append("Consider segregating by metal type (ferrous vs non-ferrous) for optimal recovery yield.")
    elif metal >= 50:
        recs.append("Moderate metal content detected. Mechanical separation (magnetic / eddy-current) is recommended before processing.")
        recs.append("Secondary sorting may improve purity by 15-25% and increase market value.")
    else:
        recs.append("Low metal concentration in this sample. Manual or optical sorting is recommended to extract recoverable materials.")

    if non_metal >= 30:
        recs.append(f"Non-metallic impurities are significant at {non_metal:.1f}%. Consider shredding and density separation to isolate plastics, rubber, or glass components.")

    if background >= 25:
        recs.append(f"Background noise is {background:.1f}% — if this sample contains soil or debris, pre-washing may improve classification accuracy on re-scan.")

    recs.append("For export-grade scrap, ensure compliance with ISRI (Institute of Scrap Recycling Industries) grading standards.")
    return recs
