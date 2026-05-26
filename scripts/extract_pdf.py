"""Extract text from PDF files and detect chapter boundaries.

Usage:
    python extract_pdf.py <pdf_path> <output_dir>

Outputs:
    <output_dir>/chapters/    — one .txt file per detected chapter/page-group
    <output_dir>/metadata.json — chapter info, total word count
"""

import json
import os
import re
import sys
from collections import defaultdict


def extract_text_from_pdf(pdf_path: str, output_dir: str) -> dict:
    os.makedirs(os.path.join(output_dir, "chapters"), exist_ok=True)

    import fitz  # pymupdf

    doc = fitz.open(pdf_path)
    all_pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        all_pages.append({"page": page_num + 1, "text": text})

    doc.close()

    chapters = _split_into_chapters(all_pages)
    return _build_metadata(pdf_path, chapters, output_dir)


def _split_into_chapters(pages: list[dict]) -> list[dict]:
    # Strategy 1: Look for explicit chapter headings
    chapter_pattern = re.compile(
        r"^\s*(?:CHAPTER|CHAP\.?|Ch\.?)\s+(?:\d+|[A-Z]+)\b",
        re.MULTILINE | re.IGNORECASE,
    )
    alt_pattern = re.compile(
        r"^\s*(?:\d+)\s*\n\s*\n\s*[A-Z][A-Za-z\s,'-]{3,50}\s*\n",
        re.MULTILINE,
    )

    chapter_starts = []
    for pg in pages:
        if chapter_pattern.search(pg["text"]):
            chapter_starts.append(pg["page"])

    if len(chapter_starts) < 2:
        # Try looser pattern
        chapter_starts = []
        for pg in pages:
            text = pg["text"]
            lines = text.strip().split("\n")
            for line in lines[:5]:
                line = line.strip()
                if re.match(r"^(?:Chapter|Part|Section|Book)\s+\w+", line, re.I):
                    chapter_starts.append(pg["page"])
                    break
                if re.match(r"^\d{1,3}\s*$", line) and len(line.strip()) <= 3:
                    chapter_starts.append(pg["page"])
                    break

    if len(chapter_starts) < 2:
        # Split evenly by page count (rough: ~20 pages per chunk)
        chunk_size = max(15, len(pages) // max(1, len(pages) // 20))
        chapter_starts = [1]
        for i in range(chunk_size, len(pages), chunk_size):
            chapter_starts.append(pages[i]["page"])

    # Build chapter map
    start_pages = sorted(set(chapter_starts))
    chapters = []
    for i, start in enumerate(start_pages):
        end = start_pages[i + 1] if i + 1 < len(start_pages) else pages[-1]["page"] + 1
        ch_pages = [p for p in pages if start <= p["page"] < end]
        text = "\n\n".join(p["text"] for p in ch_pages)
        text = _clean_text(text)
        if not text.strip():
            continue
        title = _guess_chapter_title(text, i)
        chapters.append({"index": len(chapters), "title": title, "text": text})

    return chapters


def _guess_chapter_title(text: str, index: int) -> str:
    first_line = text.strip().split("\n")[0].strip()
    if re.match(r"^(?:Chapter|Part|Section|Book)\s+\w+", first_line, re.I):
        return first_line[:120]
    if len(first_line) < 80 and first_line.isupper():
        return first_line[:120]
    return f"Chapter {index + 1}"


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Remove page numbers
    text = re.sub(r"\n\d{1,4}\n", "\n", text)
    return text.strip()


def _build_metadata(pdf_path: str, chapters: list[dict], output_dir: str) -> dict:
    total_words = 0
    for i, ch in enumerate(chapters):
        fname = f"chapter_{i + 1:04d}.txt"
        fpath = os.path.join(output_dir, "chapters", fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(ch["text"])
        ch["file"] = fname
        ch["word_count"] = len(ch["text"].split())
        total_words += ch["word_count"]
        del ch["text"]

    metadata = {
        "source": os.path.basename(pdf_path),
        "format": "pdf",
        "total_chapters": len(chapters),
        "total_words": total_words,
        "chapters": chapters,
    }
    with open(os.path.join(output_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return metadata


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_pdf.py <pdf_path> <output_dir>")
        sys.exit(1)
    metadata = extract_text_from_pdf(sys.argv[1], sys.argv[2])
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
