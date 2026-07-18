"""Shared validation helpers for untrusted uploaded files."""

from pathlib import Path


TEXT_EXTENSIONS = {
    ".txt", ".md", ".html", ".py", ".js", ".ts", ".json",
    ".yaml", ".yml", ".xml", ".csv",
}
ZIP_EXTENSIONS = {".docx", ".xlsx", ".pptx"}
OLE_EXTENSIONS = {".doc", ".xls", ".ppt"}


def safe_upload_filename(filename: str | None) -> str:
    """Discard directory components supplied by a client."""
    name = Path((filename or "upload").replace("\\", "/")).name.strip()
    return name or "upload"


def file_signature_matches(path: str, extension: str) -> bool:
    """Perform a small allow-list signature check before parsing a file."""
    with open(path, "rb") as handle:
        header = handle.read(16)

    extension = extension.lower()
    if extension == ".pdf":
        return header.startswith(b"%PDF-")
    if extension in ZIP_EXTENSIONS:
        return header.startswith(b"PK\x03\x04")
    if extension in OLE_EXTENSIONS:
        return header.startswith(b"\xd0\xcf\x11\xe0")
    if extension in TEXT_EXTENSIONS:
        return b"\x00" not in header
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension == ".gif":
        return header.startswith((b"GIF87a", b"GIF89a"))
    if extension == ".webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if extension == ".bmp":
        return header.startswith(b"BM")
    return False
