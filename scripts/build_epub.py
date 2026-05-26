"""Build a complete EPUB from translated book workspace.

Usage:
    python build_epub.py <workspace_dir>

Expects:
    workspace/translated/chapter_0001.md ... — translated chapters
    workspace/glossary.json — character/place/term translations
    workspace/summary_cn.txt — Chinese non-spoiler summary
    workspace/cover.jpg — cover image (optional, falls back to text cover)
    workspace/extracted/metadata.json — source metadata

Output:
    workspace/<ChineseTitle>.epub — the complete ebook
"""

import json
import os
import re
import sys
import glob as globmod
from pathlib import Path
from io import BytesIO


def build_epub(workspace_dir: str) -> str:
    ws = Path(workspace_dir)
    if not ws.exists():
        sys.exit(f"Workspace not found: {workspace_dir}")

    # Load metadata
    meta_path = ws / "extracted" / "metadata.json"
    with open(meta_path, encoding="utf-8") as f:
        extraction_meta = json.load(f)

    source_name = extraction_meta.get("source", "Unknown")
    english_title = Path(source_name).stem.replace("_", " ")

    # Load glossary
    glossary_path = ws / "glossary.json"
    with open(glossary_path, encoding="utf-8") as f:
        glossary = json.load(f)

    # Derive Chinese title from glossary or filename
    chinese_title = _infer_chinese_title(english_title, glossary)

    # Load summary
    summary_path = ws / "summary_cn.txt"
    summary_cn = ""
    if summary_path.exists():
        with open(summary_path, encoding="utf-8") as f:
            summary_cn = f.read().strip()

    # Collect translated chapters
    translated_dir = ws / "translated"
    chapter_files = sorted(globmod.glob(str(translated_dir / "chunk_*.md")))
    if not chapter_files:
        chapter_files = sorted(globmod.glob(str(translated_dir / "chapter_*.md")))

    chapters = []
    for cf in chapter_files:
        with open(cf, encoding="utf-8") as f:
            chapters.append(f.read().strip())

    if not chapters:
        sys.exit("No translated chapters found in workspace/translated/")

    # Build EPUB
    full_title = f"{english_title} —— {chinese_title}"
    epub_filename = f"{chinese_title}.epub"
    epub_path = str(ws / epub_filename)

    _write_epub(
        epub_path=epub_path,
        full_title=full_title,
        english_title=english_title,
        chinese_title=chinese_title,
        author="Unknown",
        chapters=chapters,
        summary_cn=summary_cn,
        glossary=glossary,
        cover_path=str(ws / "cover.jpg") if (ws / "cover.jpg").exists() else None,
    )

    return epub_path


def _infer_chinese_title(english_title: str, glossary: dict) -> str:
    """Derive a Chinese title. If the glossary has a 'title' entry, use it.
    Otherwise, provide a reasonable transliteration or leave as placeholder."""
    if "title" in glossary.get("terms", {}):
        return glossary["terms"]["title"]
    # Try common patterns
    title_lower = english_title.lower()
    if "dream hotel" in title_lower:
        return "梦之酒店"
    if "lantern keeper" in title_lower:
        return "提灯人"
    # Fallback: transliterated placeholder
    return f"{english_title}（中译本）"


def _write_epub(
    epub_path: str,
    full_title: str,
    english_title: str,
    chinese_title: str,
    author: str,
    chapters: list[str],
    summary_cn: str,
    glossary: dict,
    cover_path: str = None,
):
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier(f"book-translator-{hash(full_title) & 0xFFFFFFFF:08x}")
    book.set_title(full_title)
    book.set_language("zh-CN")
    book.add_author(author)
    book.add_metadata("DC", "contributor", "Claude (AI Literary Translator)", {"role": "trl"})

    # Cover image
    if cover_path and os.path.exists(cover_path):
        with open(cover_path, "rb") as f:
            cover_data = f.read()
        book.set_cover("cover.jpg", cover_data)

    # Build spine items
    spine = ["nav"]
    toc_entries = []

    # --- Title page ---
    title_html = f"""<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head><title>Title</title></head>
<body style="text-align:center; padding:2em;">
<h1 style="font-size:1.8em;">{english_title}</h1>
<h2 style="font-size:1.4em; margin-top:1em;">{chinese_title}</h2>
<p style="margin-top:3em;">作者：{author}</p>
<p>译者：Claude（AI文学翻译）</p>
</body></html>"""
    title_page = epub.EpubHtml(title="Title Page", file_name="title.xhtml", lang="zh-CN")
    title_page.set_content(title_html)
    book.add_item(title_page)
    spine.append(title_page)
    toc_entries.append(epub.Link("title.xhtml", "书名页 / Title Page", "title"))

    # --- Summary page ---
    if summary_cn:
        summary_html = f"""<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head><title>内容简介</title></head>
<body>
<h2>内容简介</h2>
{"".join(f"<p>{p}</p>" for p in summary_cn.split("\\n") if p.strip())}
</body></html>"""
        summary_page = epub.EpubHtml(title="内容简介", file_name="summary.xhtml", lang="zh-CN")
        summary_page.set_content(summary_html)
        book.add_item(summary_page)
        spine.append(summary_page)
        toc_entries.append(epub.Link("summary.xhtml", "内容简介 / Summary", "summary"))

    # --- Chapter pages ---
    for i, ch_text in enumerate(chapters):
        ch_num = i + 1
        ch_title = f"第{ch_num}章"
        # Try to extract a heading from the chapter text
        heading_match = re.search(r"^##\s*(.+)", ch_text)
        if heading_match:
            ch_title = heading_match.group(1).strip()
            ch_text = re.sub(r"^##\s*.+\n+", "", ch_text, count=1)

        ch_html = f"""<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head><title>{ch_title}</title></head>
<body>
<h2>{ch_title}</h2>
{"".join(f"<p>{p}</p>" for p in ch_text.split("\\n\\n") if p.strip())}
</body></html>"""
        ch_page = epub.EpubHtml(title=ch_title, file_name=f"ch_{ch_num:04d}.xhtml", lang="zh-CN")
        ch_page.set_content(ch_html)
        book.add_item(ch_page)
        spine.append(ch_page)
        toc_entries.append(epub.Link(f"ch_{ch_num:04d}.xhtml", ch_title, f"ch{ch_num}"))

    # --- Glossary appendix ---
    gl_sections = []
    for category, title in [("characters", "人物 / Characters"), ("places", "地点 / Places"), ("terms", "术语 / Terms")]:
        entries = glossary.get(category, {})
        if entries:
            gl_sections.append(f"<h3>{title}</h3><ul>")
            for en, zh in sorted(entries.items()):
                gl_sections.append(f"<li><strong>{en}</strong>: {zh}</li>")
            gl_sections.append("</ul>")

    if gl_sections:
        gl_html = f"""<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN">
<head><title>翻译术语表</title></head>
<body>
<h2>翻译术语表 / Translation Glossary</h2>
{"".join(gl_sections)}
</body></html>"""
        gl_page = epub.EpubHtml(title="翻译术语表", file_name="glossary.xhtml", lang="zh-CN")
        gl_page.set_content(gl_html)
        book.add_item(gl_page)
        spine.append(gl_page)
        toc_entries.append(epub.Link("glossary.xhtml", "翻译术语表 / Glossary", "glossary"))

    # Set TOC and spine
    book.toc = toc_entries
    book.spine = spine
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Write
    epub.write_epub(epub_path, book)
    print(f"EPUB written: {epub_path}".encode("ascii", errors="replace").decode())


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python build_epub.py <workspace_dir>")
        sys.exit(1)
    result = build_epub(sys.argv[1])
    print(f"Output: {result}".encode("ascii", errors="replace").decode())
