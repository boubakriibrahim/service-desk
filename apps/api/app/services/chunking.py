import re


def chunk_text(text: str, max_chars: int = 1100) -> list[tuple[str | None, str]]:
    text = text.replace("\r\n", "\n")
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    chunks: list[tuple[str | None, str]] = []
    current: list[str] = []
    section: str | None = None
    size = 0

    def flush():
        nonlocal current, size
        if current:
            chunks.append((section, "\n\n".join(current)))
            current = []
            size = 0

    for block in blocks:
        if block.startswith("#"):
            flush()
            section = block.lstrip("# ").strip()[:255]
            continue
        if size + len(block) > max_chars and current:
            flush()
        current.append(block)
        size += len(block)
    flush()
    return chunks or [(section, text[:max_chars])]
