"""Extract text from EPUB files and detect chapter boundaries.

Usage:
    python extract_epub.py <epub_path> <output_dir>

Outputs:
    <output_dir>/chapters/    — one .txt file per detected chapter
    <output_dir>/metadata.json — chapter titles, order, total word count
"""

import json
import os
import re
import sys
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup


def extract_text_from_epub(epub_path: str, output_dir: str) -> dict:
    os.makedirs(os.path.join(output_dir, "chapters"), exist_ok=True)

    # First try ebooklib for proper TOC extraction
    try:
        from ebooklib import epub

        book = epub.read_epub(epub_path)
        chapters = _extract_via_ebooklib(book, output_dir)
        if chapters:
            return _build_metadata(epub_path, chapters, output_dir)
    except Exception:
        pass

    # Fallback: raw ZIP + HTML parsing
    chapters = _extract_via_zip(epub_path, output_dir)
    return _build_metadata(epub_path, chapters, output_dir)


def _extract_via_ebooklib(book, output_dir: str) -> list[dict]:
    from ebooklib import epub

    chapters = []
    spine = book.spine if hasattr(book, "spine") else []
    toc = book.toc if hasattr(book, "toc") else []

    # Build TOC href → title map
    toc_map = {}
    for item in toc:
        if hasattr(item, "title") and hasattr(item, "href"):
            toc_map[item.href.split("#")[0]] = item.title

    # Collect all spine items with their content
    items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
    item_map = {item.get_name(): item for item in items}

    for idx, (item_id, _linear) in enumerate(spine):
        item = item_map.get(item_id)
        if item is None:
            continue
        text = _html_to_text(item.get_body_content().decode("utf-8", errors="replace"))
        if not text.strip():
            continue
        title = toc_map.get(item.get_name(), f"Chapter {len(chapters) + 1}")
        if not _looks_like_chapter(title) and len(chapters) == 0:
            title = "Front Matter" if text.strip() else title
        chapters.append({"index": len(chapters), "title": title, "text": text})

    return chapters


def _extract_via_zip(epub_path: str, output_dir: str) -> list[dict]:
    chapters = []
    seen_fingerprints = set()

    with zipfile.ZipFile(epub_path) as zf:
        html_files = sorted(
            [f for f in zf.namelist() if f.endswith((".html", ".xhtml", ".htm"))],
            key=_sort_key,
        )

        for fname in html_files:
            html = zf.read(fname).decode("utf-8", errors="replace")
            soup = BeautifulSoup(html, "lxml")

            # Remove non-content elements
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()

            text = soup.get_text("\n", strip=True)
            text = _clean_text(text)

            if not text or len(text) < 50:
                continue

            fp = _fingerprint(text)
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)

            title = _guess_title(soup, fname, len(chapters))
            chapters.append({"index": len(chapters), "title": title, "text": text})

    return chapters


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()
    return _clean_text(soup.get_text("\n", strip=True))


def _clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _fingerprint(text: str, length: int = 200) -> str:
    return text.strip()[:length]


def _guess_title(soup, filename: str, index: int) -> str:
    # Try h1, h2, h3 in order
    for level in ["h1", "h2", "h3"]:
        h = soup.find(level)
        if h and h.get_text(strip=True):
            t = h.get_text(strip=True)[:120]
            if _looks_like_chapter(t):
                return t

    # Try title tag
    title_tag = soup.find("title")
    if title_tag:
        t = title_tag.get_text(strip=True)[:120]
        if t and not t.startswith("Untitled"):
            return t

    # Derive from filename
    stem = Path(filename).stem
    stem = re.sub(r"[-_]", " ", stem)
    stem = re.sub(r"(ch?|chapter|part|section)\s*(\d+)", r"Chapter \2", stem, flags=re.I)
    if _looks_like_chapter(stem):
        return stem

    return f"Chapter {index + 1}"


def _looks_like_chapter(title: str) -> bool:
    patterns = [
        r"chapter\s+\d+",
        r"ch\.?\s*\d+",
        r"part\s+\w+",
        r"section\s+\d+",
        r"book\s+\w+",
        r"第.*章",
        r"^\d+\.\s+\w",
        r"act\s+\w+",
        r"prologue|epilogue|preface|foreword|introduction|appendix|afterword|acknowledgments?|contents?",
    ]
    return any(re.search(p, title, re.I) for p in patterns)


def _sort_key(name: str) -> tuple:
    nums = re.findall(r"\d+", name)
    return tuple(int(n) for n in nums)


def _build_metadata(epub_path: str, chapters: list[dict], output_dir: str) -> dict:
    total_words = 0
    for i, ch in enumerate(chapters):
        fname = f"chapter_{i + 1:04d}.txt"
        fpath = os.path.join(output_dir, "chapters", fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(ch["text"])
        ch["file"] = fname
        ch["word_count"] = len(ch["text"].split())
        total_words += ch["word_count"]
        del ch["text"]  # Free memory, keep only metadata

    metadata = {
        "source": os.path.basename(epub_path),
        "format": "epub",
        "total_chapters": len(chapters),
        "total_words": total_words,
        "chapters": chapters,
    }
    with open(os.path.join(output_dir, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return metadata


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python extract_epub.py <epub_path> <output_dir>")
        sys.exit(1)
    metadata = extract_text_from_epub(sys.argv[1], sys.argv[2])
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
