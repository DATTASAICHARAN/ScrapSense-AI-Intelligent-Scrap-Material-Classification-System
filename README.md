# ⚡ ScrapSense-AI

**Intelligent Scrap Material Classification & Analysis System**

ScrapVision AI is a production-grade, AI-powered web application that classifies scrap materials from images using Google Gemini's multimodal AI models. It provides real-time composition analysis (metals, non-metals, background), interactive visualizations, PDF reporting, and a full scan history dashboard — built for industrial scrap recycling facilities.

---

## 📸 Features

| Feature | Description |
|---|---|
| **AI Image Classification** | Analyzes uploaded or camera-streamed images using Google Gemini to identify metal, non-metal, and background proportions |
| **Dual Input Modes** | Upload JPG/PNG images or connect a live IP camera stream (via apps like IP Webcam) |
| **Interactive Charts** | Real-time donut and bar charts powered by Plotly for composition visualization |
| **Rich PDF Reports** | Multi-page PDF reports with embedded charts (matplotlib), composition tables, quality grading, and processing recommendations |
| **Scan History Dashboard** | SQLite-backed history with pagination, trend analysis, and aggregate statistics |
| **Excel Export** | One-click XLSX download of all scan history with auto-formatted columns |
| **History PDF Report** | Batch PDF report with trend charts, material distribution pie, KPI boxes, and full scan log |
| **Image Preprocessing** | CLAHE de-glare on metallic surfaces and auto-resize to 1024x1024 before analysis |
| **Model Fallback** | Automatic rotation across multiple Gemini models on rate-limit (429) errors |
| **Dark Theme UI** | Premium glassmorphism dark-mode interface with animated indicators |

---

## 🏗️ Architecture

```
ScrapVision AI
├── app.py                 # Main Streamlit UI (tabs, sidebar, analysis flow)
├── config.py              # Central configuration (API keys, prompts, paths)
├── gemini_client.py       # Gemini API wrapper with model rotation & validation
├── preprocessor.py        # Image preprocessing (CLAHE de-glare, resize)
├── camera.py              # IP camera stream manager (OpenCV background thread)
├── database.py            # SQLite persistence & Excel export
├── pdf_generator.py       # Rich PDF report generation (fpdf2 + matplotlib)
├── requirements.txt       # Python dependencies
├── .env                   # API keys (git-ignored)
├── .env.example           # Template for .env
├── assets/
│   └── style.css          # Custom dark-theme CSS
├── tests/
│   ├── conftest.py        # Test path configuration
│   ├── test_db.py         # Database unit tests
│   └── test_gemini.py     # Gemini client tests
├── saved_images/          # Auto-saved analyzed images
├── test_images/           # Sample test images
└── scrap_history.db       # SQLite database (auto-created)
```

### Module Responsibilities

| Module | Purpose |
|---|---|
| `app.py` | Streamlit frontend — sidebar configuration, analyze tab (upload + camera), history dashboard tab with pagination & export |
| `config.py` | Loads `.env`, defines Gemini model rotation list, system prompt, file size limits, camera timeouts, and UI constants |
| `gemini_client.py` | Wraps `google-generativeai` SDK — sends images to Gemini, extracts JSON from AI response, normalizes percentages to 100%, retries on rate-limit |
| `preprocessor.py` | Validates file type & size, loads images via PIL, applies CLAHE (Contrast Limited Adaptive Histogram Equalization) for metallic glare reduction |
| `camera.py` | `CameraStream` class with background OpenCV capture thread; `grab_single_frame()` for one-shot capture from IP camera URL |
| `database.py` | SQLite schema management, scan CRUD operations, aggregate statistics, and `openpyxl`-powered Excel export |
| `pdf_generator.py` | Generates branded multi-page PDFs with embedded matplotlib charts (donut, horizontal bar, trend line, distribution pie), data tables, and AI recommendations |

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+** (tested on 3.11)
- **Google Gemini API Key** — get one free from [Google AI Studio](https://aistudio.google.com/apikey)
- **pip** (Python package manager)

### 1. Clone the Repository

```bash
git clone https://github.com/Venkatasai6789/Sparkless.git
cd Sparkless
```

### 2. Create a Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
# Copy the template
cp .env.example .env

# Then edit .env and add your Gemini API key:
# GEMINI_API_KEY=your_actual_api_key_here
```

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
notepad .env
```

### 5. Run the Application

```bash
streamlit run app.py
```

The application will open automatically in your browser at **http://localhost:8501**.

---

## 🖥️ Usage Guide

### Analyzing Images

1. **Enter your Gemini API Key** in the sidebar (or set it in `.env`)
2. Choose an input mode on the **Analyze** tab:
   - **🖼️ Local Upload** — Drag & drop or browse for a JPG/PNG image (max 10 MB)
   - **📷 Live Stream** — Enter your IP camera URL (e.g., `http://192.168.1.100:8080/video`)
3. Click **🚀 Analyze** to run AI classification
4. View results:
   - Composition donut chart
   - Percentage breakdown bars
   - Dominant material badge & confidence level
   - Detailed AI notes
5. **Download PDF Report** — click the button for a comprehensive multi-page PDF

### Viewing History

1. Switch to the **📊 History Dashboard** tab
2. Browse paginated scan results
3. View aggregate KPIs (total scans, average metal %, peak purity)
4. **Export options:**
   - 📥 Download as Excel (`.xlsx`)
   - 📄 Download History PDF Report (with charts & trend analysis)
5. **Clear History** — permanently delete all records (after confirmation)

### Using IP Camera

1. Install [IP Webcam](https://play.google.com/store/apps/details?id=com.pas.webcam) on your Android phone
2. Start the server in the app — it will show a URL like `http://192.168.1.100:8080`
3. Enter `http://192.168.1.100:8080/video` in the ScrapVision sidebar
4. Make sure your phone and computer are on the **same Wi-Fi network**
5. Click **Test Connection** to verify, then **Capture & Analyze**

---

## ⚙️ Configuration Reference

All settings are in `config.py` and loaded from `.env`:

| Setting | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(from .env)* | Google Gemini API key |
| `GEMINI_MODELS` | `["gemini-3-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]` | Model rotation list (first = primary) |
| `TARGET_SIZE` | `(1024, 1024)` | Image resize dimensions before analysis |
| `MAX_FILE_SIZE_MB` | `10` | Maximum upload file size |
| `CAMERA_TIMEOUT_SEC` | `5` | IP camera connection timeout |
| `CAMERA_RECONNECT_ATTEMPTS` | `3` | Auto-reconnect attempts on camera failure |
| `DB_PATH` | `./scrap_history.db` | SQLite database location |
| `IMAGES_DIR` | `./saved_images/` | Directory for saving analyzed images |
| `HISTORY_PAGE_SIZE` | `20` | Rows per page in history dashboard |

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with HTML report
pytest tests/ -v --html=report.html

# Run a specific test file
pytest tests/test_db.py -v
```

### Test Coverage

| Test File | What It Tests |
|---|---|
| `tests/test_db.py` | Database init, save/retrieve scans, stats aggregation |
| `tests/test_gemini.py` | Gemini client mock, JSON extraction, percentage normalization |

---

## 📄 PDF Reports

ScrapVision generates two types of rich, branded PDF reports:

### Individual Analysis Report
Generated per-scan with:
- 📋 Report metadata (ID, timestamp, AI model)
- 🖼️ Embedded source image
- 🏷️ Material classification badge with quality grade (A/B/C/D)
- 🍩 Donut composition chart (matplotlib)
- 📊 Horizontal bar chart breakdown
- 📋 Detailed composition data table
- 📝 AI analysis notes
- 💡 Context-aware processing recommendations
- ⚖️ Disclaimer

### History Report
Generated from all scan data with:
- 📊 Summary statistics (total, average, peak, lowest metal %)
- 🎯 Colored KPI boxes
- 📈 Purity trend line chart
- 🥧 Material type distribution pie chart
- 📋 Complete scan log table (paginated across pages)

---

## 🛠️ Tech Stack

| Technology | Role |
|---|---|
| [Streamlit](https://streamlit.io) | Web UI framework |
| [Google Gemini API](https://ai.google.dev) | Multimodal AI image classification |
| [OpenCV](https://opencv.org) | Image preprocessing (CLAHE) & camera capture |
| [Pillow (PIL)](https://pillow.readthedocs.io) | Image loading & manipulation |
| [Matplotlib](https://matplotlib.org) | Chart rendering for PDF reports |
| [Plotly](https://plotly.com) | Interactive web charts |
| [fpdf2](https://py-pdf.github.io/fpdf2/) | PDF document generation |
| [SQLite](https://sqlite.org) | Lightweight embedded database |
| [Pandas](https://pandas.pydata.org) | Data manipulation & Excel export |
| [openpyxl](https://openpyxl.readthedocs.io) | Excel file generation engine |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Environment variable management |
| [pytest](https://pytest.org) | Unit testing framework |

---

## 📁 Environment Variables

Create a `.env` file in the project root (use `.env.example` as a template):

```env
# Required — get from https://aistudio.google.com/apikey
GEMINI_API_KEY=your_api_key_here
```

> **Security:** Never commit your `.env` file. Add it to `.gitignore`.

---

## 🔧 Troubleshooting

| Issue | Solution |
|---|---|
| `GEMINI_API_KEY is not set` | Create a `.env` file with your key, or enter it in the sidebar at runtime |
| `OpenCV not available` | Run `pip install opencv-python-headless` — camera & CLAHE features need it |
| `Rate limit / 429 errors` | The app auto-rotates models. If all fail, wait 60 seconds and retry |
| `Camera connection failed` | Ensure phone & PC are on the same network. Test the URL in a browser first |
| `PDF generation error` | Ensure `matplotlib` and `fpdf2` are installed: `pip install matplotlib fpdf2` |
| `Excel export fails` | Ensure `openpyxl` is installed: `pip install openpyxl` |
| `Streamlit not found` | Run `pip install streamlit` and ensure your virtual environment is activated |
| `Port 8501 in use` | Run with a different port: `streamlit run app.py --server.port 8502` |

---

## 🗂️ Database Schema

The SQLite database (`scrap_history.db`) uses a single `scans` table:

```sql
CREATE TABLE scans (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT    NOT NULL,
    source         TEXT    NOT NULL,      -- 'IP Camera' | 'Upload'
    filename       TEXT,
    image_path     TEXT,
    metal_pct      REAL    NOT NULL,
    non_metal_pct  REAL    NOT NULL,
    background_pct REAL    NOT NULL,
    dominant       TEXT,
    model_used     TEXT,
    confidence     TEXT,
    notes          TEXT
);
```

---

## 📜 System Prompt (AI Instructions)

The Gemini model receives a structured system prompt that instructs it to:
1. Classify visible materials into **Metal**, **Non-Metal**, and **Background**
2. Ensure percentages sum to exactly **100**
3. Return **pure JSON** (no markdown or explanation)
4. Include dominant material, confidence level, and optional notes

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-new-feature`
3. Commit your changes: `git commit -m "Add new feature"`
4. Push to the branch: `git push origin feature/my-new-feature`
5. Open a Pull Request

---

## 📄 License

This project is open-source. See the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Developed & Enhanced by

**Datta Sai Charan**  
[GitHub](https://github.com/DATTASAICHARAN)

> Originally based on an open-source project, further developed and enhanced with additional features and improvements.
---

<p align="center">
  Built with ❤️ using Streamlit & Google Gemini AI
</p>
