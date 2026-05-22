"""
server.py - FastAPI backend for the DDR Report Generation system.

Endpoints:
  POST /generate          → upload 2 PDFs, returns job_id
  GET  /status/{job_id}   → poll job progress
  GET  /download/{job_id} → download DDR.docx
  GET  /preview/{job_id}  → get JSON extraction summary
  GET  /health            → health check
"""

import uuid
import asyncio
import tempfile
import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import io

from src.utils.helpers import setup_logger

logger = setup_logger("server")

# ─── App Init ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="DDR Report Generator API",
    description="AI-powered Detailed Diagnostic Report generator from inspection + thermal PDFs",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-Memory Job Store ──────────────────────────────────────────────────────
# Structure: { job_id: { status, progress, message, result, created_at } }
JOBS: Dict[str, Dict[str, Any]] = {}

JOB_STATUS = {
    "queued":     "queued",
    "running":    "running",
    "done":       "done",
    "failed":     "failed",
}

# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "DDR Report Generator"}


# ─── POST /generate ───────────────────────────────────────────────────────────

@app.post("/generate")
async def generate(
    background_tasks: BackgroundTasks,
    inspection_pdf: UploadFile = File(..., description="Inspection Report PDF"),
    thermal_pdf:    UploadFile = File(..., description="Thermal Images PDF"),
    skip_vision:    bool = False,
):
    """
    Upload inspection + thermal PDFs.
    Returns a job_id to poll for progress.
    """
    # Validate file types
    for upload in [inspection_pdf, thermal_pdf]:
        if not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"File '{upload.filename}' is not a PDF."
            )

    job_id = str(uuid.uuid4())

    # Save uploaded files to temp directory
    tmp_dir = tempfile.mkdtemp(prefix=f"ddr_{job_id}_")
    inspection_path = os.path.join(tmp_dir, "inspection.pdf")
    thermal_path    = os.path.join(tmp_dir, "thermal.pdf")

    insp_bytes = await inspection_pdf.read()
    therm_bytes = await thermal_pdf.read()

    with open(inspection_path, "wb") as f:
        f.write(insp_bytes)
    with open(thermal_path, "wb") as f:
        f.write(therm_bytes)

    # Initialize job record
    JOBS[job_id] = {
        "status": JOB_STATUS["queued"],
        "progress": 0,
        "message": "Job queued. Starting shortly...",
        "stage_index": 0,
        "result": None,
        "errors": [],
        "warnings": [],
        "created_at": datetime.utcnow().isoformat(),
        "inspection_filename": inspection_pdf.filename,
        "thermal_filename": thermal_pdf.filename,
    }

    # Run pipeline in background
    background_tasks.add_task(
        _run_pipeline_job,
        job_id=job_id,
        inspection_path=inspection_path,
        thermal_path=thermal_path,
        tmp_dir=tmp_dir,
        skip_vision=skip_vision,
    )

    logger.info(f"Job {job_id} created. Files: {inspection_pdf.filename}, {thermal_pdf.filename}")

    return {
        "job_id": job_id,
        "status": "queued",
        "message": "Job queued. Poll /status/{job_id} for progress.",
    }


# ─── GET /status/{job_id} ─────────────────────────────────────────────────────

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """Poll job progress."""
    job = _get_job_or_404(job_id)
    return {
        "job_id":      job_id,
        "status":      job["status"],
        "progress":    job["progress"],      # 0-100
        "message":     job["message"],
        "stage_index": job["stage_index"],
        "errors":      job["errors"],
        "warnings":    job["warnings"],
        "created_at":  job["created_at"],
    }


# ─── GET /download/{job_id} ──────────────────────────────────────────────────

@app.get("/download/{job_id}")
async def download_report(job_id: str):
    """Download the generated DDR .docx file."""
    job = _get_job_or_404(job_id)

    if job["status"] != JOB_STATUS["done"]:
        raise HTTPException(
            status_code=202,
            detail=f"Job not ready. Current status: {job['status']} ({job['progress']}%)"
        )

    result = job.get("result")
    if not result or not result.get("docx_bytes"):
        raise HTTPException(status_code=500, detail="DDR document not found in job result.")

    docx_bytes = result["docx_bytes"]
    filename   = f"DDR_Report_{job_id[:8]}.docx"

    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ─── GET /preview/{job_id} ───────────────────────────────────────────────────

@app.get("/preview/{job_id}")
async def preview_data(job_id: str):
    """
    Return a JSON preview of extracted data (areas, readings, links).
    Available as soon as the job is done.
    """
    job = _get_job_or_404(job_id)

    if job["status"] not in (JOB_STATUS["done"],):
        raise HTTPException(
            status_code=202,
            detail=f"Job not ready. Current status: {job['status']} ({job['progress']}%)"
        )

    result = job.get("result", {})

    # Return a lightweight preview (no raw image bytes)
    inspection = result.get("inspection_data", {})
    thermal    = result.get("thermal_data", {})
    links      = result.get("links_data", {})

    preview = {
        "job_id": job_id,
        "status": job["status"],
        "property": inspection.get("property", {}),
        "areas": [
            {"area_id": a["area_id"], "name": a["name"]}
            for a in inspection.get("areas", [])
        ],
        "observations_count": len(inspection.get("observations", [])),
        "thermal_readings": [
            {
                "reading_id": r["reading_id"],
                "location": r.get("location"),
                "hotspot_temp": r.get("hotspot_temp"),
                "coldspot_temp": r.get("coldspot_temp"),
                "anomaly_type": r.get("anomaly_type"),
            }
            for r in thermal.get("readings", [])
        ],
        "links": [
            {
                "thermal_id": l["thermal_id"],
                "area_name": l["area_name"],
                "confidence": l["confidence"],
                "method": l["method"],
            }
            for l in links.get("links", [])
        ],
        "unmatched_thermals": links.get("unmatched_thermals", []),
        "conflicts": links.get("conflicts", []),
        "statistics": links.get("statistics", {}),
        "summary_table": inspection.get("summary_table", []),
        "warnings": job["warnings"],
        "errors": job["errors"],
        "audit": result.get("audit", {}),
    }
    return JSONResponse(content=preview)


# ─── GET /jobs ────────────────────────────────────────────────────────────────

@app.get("/jobs")
async def list_jobs():
    """List all jobs (lightweight)."""
    return [
        {
            "job_id":   jid,
            "status":   j["status"],
            "progress": j["progress"],
            "message":  j["message"],
            "created_at": j["created_at"],
        }
        for jid, j in JOBS.items()
    ]


# ─── Background Pipeline Runner ───────────────────────────────────────────────

async def _run_pipeline_job(
    job_id: str,
    inspection_path: str,
    thermal_path: str,
    tmp_dir: str,
    skip_vision: bool,
):
    """Background task that runs the DDR pipeline and updates the job record."""
    import shutil
    from pipeline import DDRPipeline

    job = JOBS[job_id]
    job["status"] = JOB_STATUS["running"]

    def progress_callback(message: str, pct: int, stage: int):
        job["progress"]    = pct
        job["message"]     = message
        job["stage_index"] = stage
        logger.info(f"[Job {job_id[:8]}] [{pct}%] {message}")

    try:
        # Run in a thread executor to avoid blocking the event loop
        loop = asyncio.get_event_loop()
        pipeline = DDRPipeline(
            inspection_pdf_path = inspection_path,
            thermal_pdf_path    = thermal_path,
            progress_callback   = progress_callback,
            skip_vision         = skip_vision,
        )

        result = await loop.run_in_executor(None, pipeline.run)

        job["result"]   = result
        job["errors"]   = result.get("errors", [])
        job["warnings"] = result.get("warnings", [])

        if result["status"] in ("success", "partial"):
            job["status"]   = JOB_STATUS["done"]
            job["progress"] = 100
            job["message"]  = "✅ DDR report generated successfully!"
        else:
            job["status"]  = JOB_STATUS["failed"]
            job["message"] = "Pipeline failed. Check errors for details."

    except Exception as e:
        logger.error(f"[Job {job_id[:8]}] Unexpected error: {e}", exc_info=True)
        job["status"]  = JOB_STATUS["failed"]
        job["message"] = f"Unexpected error: {str(e)}"
        job["errors"].append(str(e))

    finally:
        # Cleanup temp files (keep result in memory)
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# ─── Helper ───────────────────────────────────────────────────────────────────

def _get_job_or_404(job_id: str) -> Dict:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
