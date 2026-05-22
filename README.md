# DDR Report Generator — AI-Powered Building Diagnostic Reports

An end-to-end industrial-grade Python pipeline that reads raw **Inspection** and **Thermal** PDF reports and automatically generates a highly professional, 30+ page **Detailed Diagnostic Report (DDR)** in Microsoft Word (`.docx`) format. 

Built with a **FastAPI** backend + **Streamlit** frontend + **GPT-4o mini** text-pathology generator + **PyMuPDF** local coordinate image classifier.

---

## System Overview

Our system decouples raw visual/thermal image sorting from the LLM, running it locally via Python coordinate boundaries. The LLM is then used as a highly specialized semantic engine for technical pathology writing.

```
Sample Report.pdf  ──┐
                      ├──► [PyMuPDF Coordinate Parser] ──► [GPT-4o-mini Text] ──► [Docx Assembly Engine] ──► DDR_Report.docx
Thermal Images.pdf ──┘         ▲
                               │
                         Streamlit UI
                      (Upload → Track → Download)
```



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

To launch the application, you run the backend service and the frontend web client concurrently.

**Terminal 1 — Start the FastAPI backend:**
```powershell
.\venv\Scripts\Activate.ps1
uvicorn server:app --reload --port 8000
```

**Terminal 2 — Start the Streamlit frontend client:**
```powershell
.\venv\Scripts\Activate.ps1
streamlit run app.py --server.port 8501
```

---

## Using the Web Interface

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
