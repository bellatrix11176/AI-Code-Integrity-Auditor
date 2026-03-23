import logging
import os
from tempfile import NamedTemporaryFile
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from src.scanner.engine import ScanEngine

app = FastAPI(title="AI Code Integrity Auditor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/scan")
async def scan_files(files: List[UploadFile] = File(...)):
    # Pre-read content because ScanEngine is synchronous and doesn't await read()
    wrapped_files = []
    for f in files:
        content = await f.read()
        wrapped_files.append({"filename": f.filename, "content": content})
        
    engine = ScanEngine()
    results = engine.scan_uploaded_files(wrapped_files)
    return results

@app.get("/api/health")
def health_check():
    return {"status": "ok"}
