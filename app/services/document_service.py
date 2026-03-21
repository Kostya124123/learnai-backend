import os
import aiofiles
from pathlib import Path
from app.core.config import settings


def get_docs_dir() -> Path:
    path = Path(settings.DOCS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_upload(file_bytes: bytes, filename: str) -> str:
    docs_dir = get_docs_dir()
    safe_name = filename.replace(" ", "_")
    file_path = docs_dir / safe_name
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(file_bytes)
    return str(file_path)


def extract_text(file_path: str) -> str:
    """Extract text from PDF, DOCX or TXT."""
    path = Path(file_path)
    ext = path.suffix.lower()
    try:
        if ext == ".pdf":
            import pdfplumber
            text = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text.append(t)
            return "\n".join(text)
        elif ext in (".docx", ".doc"):
            from docx import Document
            doc = Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        elif ext == ".txt":
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as e:
        print(f"Could not extract text from {file_path}: {e}")
    return ""


def chunk_text(text: str, size: int = 1000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks."""
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks
