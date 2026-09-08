"""Untrusted PDF extraction, invoked in a disposable process by admission."""

from __future__ import annotations

import io
import sys


def extract_text(content: bytes, *, max_text: int, max_pages: int) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages = len(reader.pages)
    if not pages:
        raise ValueError("PDF contains no pages")
    if pages > max_pages:
        raise ValueError("source exceeds safe extraction limits")
    parts: list[str] = []
    size = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        size += len(text) + bool(parts)
        if size > max_text:
            raise ValueError("source exceeds safe extraction limits")
        parts.append(text)
    return "\n".join(parts)


if __name__ == "__main__":
    # Enforced before loading the parser. The parent also kills this process
    # after 45 wall-clock seconds. No in-process thread can provide these bounds.
    import resource

    # Keep the parser bounded while allowing the 579-page legal fixture to
    # complete on the slower CI runner; the parent still enforces a 45-second
    # wall-clock timeout for untrusted input.
    resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
    memory = 512 * 1024 * 1024
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    # macOS development does not implement RLIMIT_DATA; production Linux
    # enforces address space. CPU, wall time and output bounds apply on both.
    try:
        text = extract_text(sys.stdin.buffer.read(), max_text=int(sys.argv[1]), max_pages=int(sys.argv[2]))
        sys.stdout.buffer.write(text.encode("utf-8"))
    except (MemoryError, ValueError) as exc:
        sys.exit(3 if isinstance(exc, MemoryError) or str(exc) == "source exceeds safe extraction limits" else 2)
    except Exception:
        sys.exit(2)
