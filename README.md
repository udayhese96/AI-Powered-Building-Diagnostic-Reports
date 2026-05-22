# 🏗️ DDR Report Generator — AI-Powered Building Diagnostic Reports

An end-to-end industrial-grade Python pipeline that reads raw **Inspection** and **Thermal** PDF reports and automatically generates a highly professional, 30+ page **Detailed Diagnostic Report (DDR)** in Microsoft Word (`.docx`) format. 

Built with a **FastAPI** backend + **Streamlit** frontend + **GPT-4o mini** text-pathology generator + **PyMuPDF** local coordinate image classifier.

---

## ✨ What's Enhanced (Premium Industrial Standard)

Compared to generic AI-generated documents, this platform outputs documents matching professional forensic engineering inspections:

| Feature Area | Before | After (Premium Elite Standard) |
| :--- | :--- | :--- |
| **Document Length** | ~5 pages | **30+ pages** (Dynamic, non-page-wise section growth) |
| **Visual-Thermal Alignment** | Randomly floating images | **Sleek Side-by-Side Tables** (Visual photo left, FLIR Thermal Map right) |
| **Thermal Image Filtering** | Unwanted crosshairs & icons | **Filter Reticle Noise** (Ignores small overlays, extracts real $w, h \ge 300$ radiometric maps) |
| **Checklist Formatting** | Text summaries | **Wingdings Checkbox Grids** (Color-coded Good/Moderate/Poor ticks ``) |
| **Data Verification** | Raw generation | **3-Tier Checkpoint Validation** (Extractor, Linker, and Builder gates) |
| **Figure Numbering** | Hallucinated static tags | **Dynamic Sequential Captions** (Automatically maps absolute indexes e.g., `Figure 1`) |
| **Pathology Terminology** | Simple layperson words | **Expert Engineering Vocabulary** (Capillary draw, evaporative cooling patterns, etc.) |
| **Rehabilitation Steps** | Generic advice | **Chemical Formulations** (Dr. Fixit polymer-modified mortars, mixing ratios, etc.) |
| **Programmatic Charts** | None | **Matplotlib Severity Donut Charts** embedded in section centers |

---

## 📸 System Overview

Our system decouples raw visual/thermal image sorting from the LLM, running it locally via Python coordinate boundaries. The LLM is then used as a highly specialized semantic engine for technical pathology writing.

```
Sample Report.pdf  ──┐
                      ├──► [PyMuPDF Coordinate Parser] ──► [GPT-4o-mini Text] ──► [Docx Assembly Engine] ──► DDR_Report.docx
Thermal Images.pdf ──┘         ▲
                               │
                         Streamlit UI
                      (Upload → Track → Download)
```

### ⚙️ 5-Stage Orchestration Pipeline

| Stage | Module Name | Core Mechanics |
| :--- | :--- | :--- |
| **Stage 1a** | `InspectionExtractor` | Parses property details & checklists using a **perfected horizontal two-column coordinate boundary parser** (splitting checklists via $y$-axis checks). |
| **Stage 1b** | `ThermalExtractor` | Local image extraction. Filters out reticles ($width, height < 300$) and classifies remaining high-res images: **Thermal IR Map** ($y0 < 200$) vs. **Visual Photo** ($y0 \ge 200$), locking them page-by-page. |
| **Stage 1c** | `ThermalAreaLinker` | Binds thermodynamic labels (`T1`, `T2`) to physical structural rooms using a **4-tier matching matrix** (Exact $\rightarrow$ Keyword $\rightarrow$ Row Alignment $\rightarrow$ Page Proximity). |
| **Stage 4** | `DDRGenerator` | Context optimizer that feeds compressed JSON definitions into **GPT-4o-mini** (OpenAI JSON Mode), injecting technical pathology definitions and rehabilitation guidelines. |
| **Stage 5** | `DocxBuilder` | Dynamic document assembly. Styles headers, embeds side-by-side tables, inserts dynamic Matplotlib donut charts, formats Wingdings checkbox grids, and sequentializes image captions. |

---

## 📁 Project Structure

```
DDR Report Genrator/
├── src/
│   ├── utils/
│   │   ├── config.py                  # API models, colors, and layout constants
│   │   └── helpers.py                 # Common utility functions
│   ├── stage1_extract/
│   │   ├── inspection_extractor.py    # Extracts text & checklists from Inspection PDF
│   │   ├── thermal_extractor.py       # Decoupled image coordinate classifier
│   │   └── linker.py                  # Links thermal anomalies to structural areas
│   ├── stage3_validate/
│   │   └── validator.py               # Robust 3-tier validation checkpoints
│   ├── stage4_generate/
│   │   ├── chart_generator.py         # Matplotlib dynamic donut chart generator
│   │   └── ddr_generator.py           # Technical pathology text builder (GPT-4o-mini)
│   └── stage5_assemble/
│       └── docx_builder.py            # Styled Microsoft Word document assembler
├── pipeline.py                        # Programmatic Command Line interface (CLI)
├── server.py                          # High-performance FastAPI backend
├── app.py                             # Interactive Streamlit frontend UI
├── start.ps1                          # Automated Windows PowerShell startup script
├── requirements.txt                   # List of Python library dependencies
├── .env                               # Secrets (contains your OpenAI API key)
└── .env.example                       # Example format template for local secrets
```

---

## ⚙️ Prerequisites

- **Python 3.10 or higher** — [Download Python](https://www.python.org/downloads/)
- **OpenAI API Key** — [OpenAI Developer Portal](https://platform.openai.com/)
- **PowerShell** (Default on Windows)

---

## 🚀 Installation & Setup

### Step 1: Open the Project Directory
Open PowerShell or your command prompt in your local workspace folder:
```powershell
cd "d:\Coding Area\DDR Report Genrator"
```

### Step 2: Create a Dedicated Virtual Environment
Isolate your packages by initializing a local environment:
```powershell
python -m venv venv
```

### Step 3: Activate the Virtual Environment
Activate your environment prior to installing packages:
* **Windows (PowerShell)**:
  ```powershell
  .\venv\Scripts\Activate.ps1
  ```
* **Windows (Command Prompt)**:
  ```cmd
  venv\Scripts\activate.bat
  ```

*(You will see `(venv)` prepended to your command line prompt when successful).*

### Step 4: Install Dependencies
Install the required packages using `requirements.txt`:
```powershell
pip install -r requirements.txt
```

This installs:
* `fastapi` & `uvicorn` — Backend server execution.
* `streamlit` — Beautiful web application frontend interface.
* `pymupdf` — Local PDF object parsing.
* `python-docx` — High-fidelity Microsoft Word generation.
* `openai` — GPT-4o-mini semantic text interactions.
* `pillow` — Visual aspect ratio calculations.
* `matplotlib` — Dynamic donut charts.
* `pandas` & `requests` — Internal dataframes and communication.

### Step 5: Configure Local Environment Credentials
Duplicate the sample configuration file and insert your API key:
```powershell
Copy-Item .env.example .env
```

Open the newly created `.env` file in your editor and add your OpenAI API key:
```env
OPENAI_API_KEY=sk-proj-yourActualOpenAiApiKeyHere...
```

---

## ▶️ Running the Platform

### Method A: One-Click Automated Startup (Recommended)
Our system includes a robust PowerShell orchestration script that automatically tests dependencies, sets environment encodings, and boots the backend and frontend servers in isolated shell processes.

To launch the app instantly, run:
```powershell
.\start.ps1
```
* **FastAPI Backend Portal**: Launches at `http://localhost:8000`
* **Streamlit Web Client UI**: Automatically opens your default browser at `http://localhost:8501`

---

### Method B: Manual Startup (Two Separate Terminals)

If you prefer starting processes manually:

**Terminal 1 — Activate environment & start FastAPI server:**
```powershell
.\venv\Scripts\Activate.ps1
uvicorn server:app --reload --port 8000
```

**Terminal 2 — Activate environment & start Streamlit UI:**
```powershell
.\venv\Scripts\Activate.ps1
streamlit run app.py --server.port 8501
```

---

### Method C: Command-Line Core (No UI Interface)
You can run the entire compilation pipeline programmatically without booting the server or opening a web browser:

```powershell
python pipeline.py --inspection "Sample Report.pdf" --thermal "Thermal Images.pdf" --output DDR_Report.docx
```

**Development Flags:**
```powershell
# Skip OpenAI API Calls (Perfect for offline extraction testing)
python pipeline.py --inspection "Sample Report.pdf" --thermal "Thermal Images.pdf" --skip-vision

# Define a custom output path
python pipeline.py --inspection "Sample Report.pdf" --thermal "Thermal Images.pdf" --output "d:\MyReports\Completed_DDR.docx"
```

---

## 🖥️ Using the Web Interface

1. Navigate your web browser to `http://localhost:8501`.
2. **Upload Sources**:
   * Drag-and-drop your inspection document (`Sample Report.pdf`) into the **Inspection PDF Panel**.
   * Drag-and-drop your FLIR thermodynamic document (`Thermal Images.pdf`) into the **Thermal PDF Panel**.
3. **Trigger Generator**: Click the **🚀 Generate DDR Report** button.
4. **Monitor Progress**: Watch the real-time execution logger detailing each pipeline step and checkpoint validation status.
5. **Interactive Preview Panels**:
   * Check structural observations grouped per room.
   * View linked thermal maps and calculated anomalies.
   * Inspect color-coded severity tables.
6. **Trigger Export**: Click the **📥 Download DDR Report (.docx)** button to save the professional document locally.

---

## 🩺 Troubleshooting Common Windows Issues

* **Execution Policy Blocked on `start.ps1`**:
  If PowerShell returns an execution policy error, grant standard local permission by running:
  ```powershell
  Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```
* **Unicode Encoding Errors in Command Output**:
  If the Windows PowerShell terminal crashes due to character encoding, set UTF-8 defaults:
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  ```
* **FastAPI Port Conflicts**:
  If port `8000` is occupied, change the uvicorn launch command:
  ```powershell
  uvicorn server:app --reload --port 8080
  ```
