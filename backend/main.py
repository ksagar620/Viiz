from __future__ import annotations

from pathlib import Path
from typing import List

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.agent import analyze_uploaded_files

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"

app = FastAPI(title="Viiz Data Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.post("/api/analyze")
async def analyze(
    files: List[UploadFile] = File(...),
    prompt: str = Form(default=""),
    generate_all: bool = Form(default=False),
):
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    file_payloads = []
    for file in files:
        if file.filename is None:
            continue
        content = await file.read()
        file_payloads.append((file.filename, content))

    if not file_payloads:
        raise HTTPException(status_code=400, detail="No valid files were uploaded.")

    return analyze_uploaded_files(file_payloads, prompt=prompt, generate_all=generate_all)
