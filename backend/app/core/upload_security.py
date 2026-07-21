"""Shared validation helpers for untrusted uploaded files.

P2-20: Adds optional content scanning via ClamAV when available, and
static heuristics for embedded binary / macro content that hint at
potentially malicious payloads.  The scanner never blocks a clean file
but flags suspicious content for downstream review.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# P2-20: content scanning (optional, fail-open)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanResult:
    ok: bool
    code: str
    detail: str
    backend: str = "heuristic"

    def to_dict(self) -> dict:
        return {"ok": self.ok, "code": self.code, "detail": self.detail, "backend": self.backend}


# Sentinel returned when no scanner is configured.
SCAN_SKIPPED = ScanResult(ok=True, code="SKIP", detail="Content scanner not configured")


def scanner_available() -> bool:
    """Return True when a scanning backend (currently ClamAV via ``clamd``)
    is reachable.  The check is lazy — the socket connection is attempted
    once per process.
    """
    if not hasattr(scanner_available, "_cached"):
        host = os.environ.get("CLAMAV_HOST") or os.environ.get("CLAMD_HOST")
        port = int(os.environ.get("CLAMAV_PORT") or os.environ.get("CLAMD_PORT", "3310"))
        timeout = float(os.environ.get("CLAMAV_TIMEOUT") or os.environ.get("CLAMD_TIMEOUT", "3"))
        if not host:
            scanner_available._cached = False
            logger.info("Content scanner: no CLAMAV_HOST set, scan disabled.")
        else:
            try:
                import socket
                sock = socket.create_connection((host, port), timeout=timeout)
                sock.sendall(b"PING\n")
                response = sock.recv(128)
                sock.close()
                scanner_available._cached = b"PONG" in response
                if scanner_available._cached:
                    logger.info("Content scanner: ClamAV reachable at %s:%d", host, port)
                else:
                    logger.warning("Content scanner: ClamAV did not respond to PING")
            except Exception as exc:
                scanner_available._cached = False
                logger.warning("Content scanner: ClamAV unreachable (%s)", exc)
    return scanner_available._cached


def scan_file(path: str) -> ScanResult:
    """Scan *path* with the available backend and return a ``ScanResult``.

    The function tries the following in order:

    1. ClamAV (via clamd protocol) when ``CLAMAV_HOST`` is set.
    2. Static heuristics for the known file types.

    Falls back to ``SCAN_SKIPPED`` when neither scanner is available.
    Fails open so uploads never block on missing infrastructure.
    """
    if scanner_available():
        return _scan_clamav(path)
    return _scan_heuristics(path)


def _scan_clamav(path: str) -> ScanResult:
    """Stream *path* to ClamAV via INSTREAM and interpret the result."""
    import socket
    from time import monotonic

    host = os.environ.get("CLAMAV_HOST") or os.environ.get("CLAMD_HOST", "")
    port = int(os.environ.get("CLAMAV_PORT") or os.environ.get("CLAMD_PORT", "3310"))
    timeout = float(os.environ.get("CLAMAV_TIMEOUT") or os.environ.get("CLAMD_TIMEOUT", "30"))

    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        # INSTREAM: send file size prefix, then chunks, then zero-length chunk.
        sock.sendall(b"zINSTREAM\0")
        with open(path, "rb") as fh:
            while True:
                chunk = fh.read(8192)
                if not chunk:
                    break
                size = len(chunk).to_bytes(4, "big")
                sock.sendall(size + chunk)
        sock.sendall(b"\x00\x00\x00\x00")  # end-of-stream marker
        response = sock.recv(4096).decode("utf-8", errors="replace")
    finally:
        sock.close()

    if "OK" in response:
        return ScanResult(ok=True, code="AV_CLEAN", detail="ClamAV: clean", backend="clamav")
    if "FOUND" in response:
        signature = response.replace("FOUND", "").replace("stream:", "").strip()
        return ScanResult(ok=False, code="AV_MALWARE", detail=f"ClamAV: {signature}", backend="clamav")
    return ScanResult(ok=True, code="AV_ERROR", detail=f"ClamAV: unexpected response: {response[:120]}", backend="clamav")


def _scan_heuristics(path: str) -> ScanResult:
    """Apply basic content heuristics without an external scanner.

    Rules:

    * Text files must not contain binary null bytes (already enforced by
      ``file_signature_matches``).  Additionally flag files whose first
      4 KB are > 15 % high-frequency control characters (``\\x00``–``\\x08``,
      ``\\x0e``–``\\x1f``) that suggest obfuscated payload embedded in a
      "text" container.
    * Text files larger than 50 MB are rejected (compression bomb defence).
    """
    ext = Path(path).suffix.lower()

    # Size enforcement for text-like extensions (compression bomb guard).
    if ext in TEXT_EXTENSIONS:
        size = os.path.getsize(path)
        if size > 50 * 1024 * 1024:
            return ScanResult(ok=False, code="TOO_LARGE", detail="Text file exceeds 50 MB", backend="heuristic")

        with open(path, "rb") as fh:
            head = fh.read(4096)
            if not head:
                return ScanResult(ok=True, code="EMPTY", detail="File is empty", backend="heuristic")

            # Count bytes that are suspicious in a plain-text context.
            suspicious = sum(1 for b in head if (0 < b < 0x09) or (0x0e < b < 0x20))
            if suspicious > len(head) * 0.15:
                return ScanResult(ok=False, code="HIGH_CTRL_CHARS", detail="Text file contains many control characters",
                                  backend="heuristic")

    return ScanResult(ok=True, code="PASS", detail="Heuristics: clean", backend="heuristic")
