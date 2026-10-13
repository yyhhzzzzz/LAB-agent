import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Document,
    DocumentChunk,
    DocumentProcessingStatus,
    Equipment,
)

CHUNK_SIZE = 1800
SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


def safe_filename(filename: Optional[str]) -> str:
    raw_name = (filename or "document").replace("\\", "/").split("/")[-1]
    suffix = Path(raw_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="仅支持 Markdown、TXT 和 PDF 文件。")

    stem = raw_name[: -len(Path(raw_name).suffix)] if Path(raw_name).suffix else raw_name
    normalized = unicodedata.normalize("NFKC", stem)
    safe_stem = "".join(
        char if char.isalnum() or char in {" ", "-", "_", "."} else "_"
        for char in normalized
    ).strip(" ._")
    if not safe_stem:
        safe_stem = "document"
    return "{}{}".format(safe_stem[:120], suffix)


async def read_upload(upload: UploadFile, max_bytes: int) -> bytes:
    content = bytearray()
    while True:
        block = await upload.read(min(64 * 1024, max_bytes + 1 - len(content)))
        if not block:
            break
        content.extend(block)
        if len(content) > max_bytes:
            raise HTTPException(status_code=413, detail="上传文件超过大小限制。")
    if not content:
        raise HTTPException(status_code=422, detail="上传文件不能为空。")
    return bytes(content)


def parse_document(filename: str, content: bytes) -> List[Dict[str, object]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="文件内容不是有效的 PDF。")
        try:
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise HTTPException(status_code=422, detail="不支持加密 PDF。")
            pages = [page.extract_text() or "" for page in reader.pages]
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=422, detail="无法解析 PDF 文件。") from exc
        sections = [
            (None, page_number, page_number, _normalize_text(page_text))
            for page_number, page_text in enumerate(pages, start=1)
            if page_text.strip()
        ]
    else:
        try:
            text = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="文本文档必须使用 UTF-8 编码。") from exc
        sections = _text_sections(filename, _normalize_text(text))

    chunks: List[Dict[str, object]] = []
    for chapter, page_start, page_end, text in sections:
        for piece in _split_text(text, CHUNK_SIZE):
            chunks.append(
                {
                    "chunk_index": len(chunks),
                    "content": piece,
                    "chapter": chapter,
                    "page_start": page_start,
                    "page_end": page_end,
                }
            )
    if not chunks:
        raise HTTPException(status_code=422, detail="文件中没有可读取的文本内容。")
    return chunks


def _normalize_text(value: str) -> str:
    return value.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n").strip()


def _text_sections(
    filename: str, text: str
) -> List[Tuple[Optional[str], Optional[int], Optional[int], str]]:
    if Path(filename).suffix.lower() != ".md":
        return [(None, None, None, text)] if text else []

    sections: List[Tuple[Optional[str], Optional[int], Optional[int], str]] = []
    chapter: Optional[str] = None
    paragraph: List[str] = []

    def flush_paragraph() -> None:
        content = "\n".join(paragraph).strip()
        if content:
            sections.append((chapter, None, None, content))
        paragraph.clear()

    for line in text.splitlines():
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading:
            flush_paragraph()
            chapter = heading.group(1).strip()
        elif line.strip():
            paragraph.append(line.rstrip())
        else:
            flush_paragraph()
    flush_paragraph()
    return sections


def _split_text(text: str, max_chars: int) -> Sequence[str]:
    remaining = text.strip()
    pieces: List[str] = []
    while len(remaining) > max_chars:
        split_at = remaining.rfind("\n", 0, max_chars + 1)
        if split_at < max_chars // 2:
            split_at = remaining.rfind(" ", 0, max_chars + 1)
        if split_at < max_chars // 2:
            split_at = max_chars
        piece = remaining[:split_at].strip()
        if piece:
            pieces.append(piece)
        remaining = remaining[split_at:].strip()
    if remaining:
        pieces.append(remaining)
    return pieces


async def save_uploaded_document(
    session: AsyncSession,
    *,
    equipment: Optional[Equipment],
    filename: str,
    title: Optional[str],
    content: bytes,
    storage_path: Path,
    uploaded_by_id: Optional[str] = None,
) -> Tuple[Document, int, bool]:
    equipment_code = equipment.equipment_code if equipment else None
    checksum = hashlib.sha256(content).hexdigest()
    duplicate_query = select(Document).where(Document.checksum == checksum)
    if equipment_code is None:
        duplicate_query = duplicate_query.where(Document.equipment_code.is_(None))
    else:
        duplicate_query = duplicate_query.where(Document.equipment_code == equipment_code)
    duplicate = await session.scalar(duplicate_query)
    if duplicate is not None:
        count = await session.scalar(
            select(func.count()).select_from(DocumentChunk).where(
                DocumentChunk.document_id == duplicate.id
            )
        )
        return duplicate, count or 0, True

    chunks = parse_document(filename, content)
    document_id = str(uuid4())
    document_dir = storage_path / document_id
    target = document_dir / filename
    source_path = "{}/{}".format(document_id, filename)
    try:
        document_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
        with target.open("xb") as output:
            output.write(content)
        document = Document(
            id=document_id,
            equipment_id=equipment.id if equipment else None,
            equipment_code=equipment_code,
            uploaded_by_id=uploaded_by_id,
            filename=filename,
            title=(title or Path(filename).stem).strip()[:255] or Path(filename).stem,
            checksum=checksum,
            source_path=source_path,
            processing_status=DocumentProcessingStatus.READY,
            processed_at=datetime.now(timezone.utc),
        )
        session.add(document)
        await session.flush()
        for chunk in chunks:
            session.add(
                DocumentChunk(
                    id=str(uuid4()),
                    document_id=document.id,
                    checksum=checksum,
                    source_path=source_path,
                    **chunk,
                )
            )
        await session.commit()
        return document, len(chunks), False
    except Exception:
        await session.rollback()
        try:
            target.unlink(missing_ok=True)
            if document_dir.exists():
                document_dir.rmdir()
        except OSError:
            pass
        raise
