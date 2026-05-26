"""Fetch or generate a cover image for a book.

Usage:
    python fetch_cover.py "<Book Title>" <output_path>

Strategy:
    1. Search the web for the book cover by title
    2. Download the best match if found
    3. If no image found online, generate a thematic cover based on plot text
"""

import json
import os
import re
import sys
import urllib.request
import urllib.parse
import io
from pathlib import Path


def fetch_cover(book_title: str, output_path: str, workspace_dir: str = None) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    # Strategy 1: Try DuckDuckGo image search for the book cover
    cover_url = _search_for_cover(book_title)
    if cover_url:
        try:
            _download_image(cover_url, str(out))
            if out.exists() and out.stat().st_size > 1000:
                print(f"Cover downloaded from: {cover_url}")
                return str(out)
        except Exception:
            pass

    # Strategy 2: Try Google Books / Open Library cover API
    isbn = _extract_isbn(workspace_dir)
    if isbn:
        ol_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
        try:
            _download_image(ol_url, str(out))
            if out.exists() and out.stat().st_size > 1000:
                print(f"Cover found via Open Library (ISBN: {isbn})")
                return str(out)
        except Exception:
            pass

    # Strategy 3: Generate a cover from plot text
    print("No cover found online. Generating from plot text...")
    _generate_cover_from_text(book_title, str(out), workspace_dir)
    return str(out)


def _search_for_cover(title: str) -> str | None:
    """Search for book cover image URL using DuckDuckGo image search."""
    try:
        query = urllib.parse.quote(f"{title} book cover")
        search_url = f"https://duckduckgo.com/?q={query}&iax=images&ia=images"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Extract image URLs from search results
        urls = re.findall(r'"thumbnail":"(https?://[^"]+)"', html)
        urls += re.findall(r'"image":"(https?://[^"]+)"', html)

        # Filter for likely book covers (larger images, not icons)
        for url in urls:
            url = url.replace("\\u0026", "&")
            if any(ext in url.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                if "icon" not in url.lower() and "favicon" not in url.lower():
                    return url
        return None
    except Exception as e:
        print(f"  Cover search failed: {e}")
        return None


def _extract_isbn(workspace_dir: str | None) -> str | None:
    """Try to find an ISBN in the extracted text."""
    if not workspace_dir:
        return None
    # Search extracted text for ISBN patterns
    ws = Path(workspace_dir)
    chunks_dir = ws / "extracted" / "chapters"
    if not chunks_dir.exists():
        chunks_dir = ws / "extracted" / "chunks"
    if not chunks_dir.exists():
        return None

    isbn_pattern = re.compile(r"\b(?:ISBN(?:-1[03])?:?\s*)?(\d{9}[\dX]|\d{13})\b")
    files = sorted(chunks_dir.glob("*.txt"))[:5]
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
            match = isbn_pattern.search(text)
            if match:
                isbn = match.group(1)
                return isbn
        except Exception:
            pass
    return None


def _download_image(url: str, output_path: str):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    with open(output_path, "wb") as f:
        f.write(data)


def _generate_cover_from_text(title: str, output_path: str, workspace_dir: str | None):
    """Generate a simple but attractive cover image using PIL."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  PIL not available; creating placeholder text cover")
        _create_placeholder_cover(title, output_path)
        return

    # Read some plot text to determine mood/theme
    theme_words = _analyze_plot_text(workspace_dir)

    # Create canvas
    width, height = 800, 1200
    img = Image.new("RGB", (width, height), _background_color(theme_words))
    draw = ImageDraw.Draw(img)

    # Try to load a font
    font_title = _load_font(42)
    font_subtitle = _load_font(28)
    font_small = _load_font(18)

    # Draw decorative elements
    _draw_decorative(draw, width, height, theme_words)

    # Draw title (centered, upper portion)
    title_lines = _wrap_text(title, 30)
    y = 350
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) / 2, y), line, fill="#FFFFFF", font=font_title)
        y += 55

    # Draw subtitle / genre hint
    genre_hint = _genre_hint(theme_words)
    y += 60
    bbox = draw.textbbox((0, 0), genre_hint, font=font_subtitle)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) / 2, y), genre_hint, fill="#CCCCCC", font=font_subtitle)

    # Draw translator credit at bottom
    credit = "中文译本 · Claude AI Literary Translator"
    y = height - 80
    bbox = draw.textbbox((0, 0), credit, font=font_small)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) / 2, y), credit, fill="#888888", font=font_small)

    img.save(output_path, "JPEG", quality=90)
    print(f"  Generated cover: {output_path}")


def _background_color(theme_words: list[str]) -> tuple:
    """Pick a background color based on detected themes."""
    themes = " ".join(theme_words).lower()
    if any(w in themes for w in ["dark", "night", "horror", "murder", "crime"]):
        return (20, 20, 40)  # Dark navy
    if any(w in themes for w in ["love", "romance", "wedding", "heart"]):
        return (80, 20, 40)  # Deep burgundy
    if any(w in themes for w in ["nature", "ocean", "forest", "mountain", "garden"]):
        return (20, 60, 40)  # Forest green
    if any(w in themes for w in ["city", "urban", "street", "night"]):
        return (40, 40, 60)  # Urban blue-gray
    if any(w in themes for w in ["dream", "sleep", "memory", "mind"]):
        return (30, 20, 60)  # Deep purple
    return (40, 30, 50)  # Default: muted dark


def _analyze_plot_text(workspace_dir: str | None) -> list[str]:
    """Extract theme keywords from the extracted book text."""
    if not workspace_dir:
        return ["book", "novel"]
    ws = Path(workspace_dir)
    chunks_dir = ws / "extracted" / "chapters"
    if not chunks_dir.exists():
        chunks_dir = ws / "extracted" / "chunks"
    if not chunks_dir.exists():
        return ["book", "novel"]

    text = ""
    files = sorted(chunks_dir.glob("*.txt"))[:10]
    for f in files:
        try:
            text += f.read_text(encoding="utf-8", errors="replace")[:3000] + " "
        except Exception:
            pass

    themes = {
        "love": ["love", "kiss", "heart", "romance", "wedding", "marriage"],
        "death": ["death", "died", "killed", "murder", "funeral", "grave"],
        "family": ["mother", "father", "child", "children", "family", "parent", "daughter", "son", "baby"],
        "crime": ["crime", "police", "prison", "jail", " arrested", "criminal", "detective"],
        "war": ["war", "battle", "soldier", "fight", "enemy", "army"],
        "dream": ["dream", "sleep", "nightmare", "wake", "asleep"],
        "nature": ["ocean", "sea", "forest", "mountain", "river", "lake", "garden", "tree"],
        "city": ["city", "street", "building", "urban", "downtown", "apartment"],
        "dark": ["dark", "night", "shadow", "black", "darkness"],
    }

    text_lower = text.lower()
    score = {}
    for theme, keywords in themes.items():
        score[theme] = sum(text_lower.count(kw) for kw in keywords)

    top = sorted(score.items(), key=lambda x: -x[1])[:5]
    return [t for t, s in top if s > 0] or ["book", "novel"]


def _genre_hint(theme_words: list[str]) -> str:
    """Return a genre hint based on themes."""
    tw = " ".join(theme_words).lower()
    if "dream" in tw or "sleep" in tw:
        return "一部关于梦与监控的小说"
    if "crime" in tw or "murder" in tw:
        return "一部悬疑惊悚小说"
    if "love" in tw:
        return "一个关于爱与命运的故事"
    if "war" in tw:
        return "一部战争史诗"
    return "一本小说"


def _wrap_text(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines = []
    current = ""
    for w in words:
        test = f"{current} {w}".strip()
        if len(test) > max_chars:
            lines.append(current)
            current = w
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def _load_font(size: int):
    try:
        # Try common system fonts
        for font_name in ["simhei.ttf", "msyh.ttf", "arial.ttf", "DejaVuSans.ttf"]:
            try:
                from PIL import ImageFont
                return ImageFont.truetype(font_name, size)
            except Exception:
                pass
        return ImageFont.load_default()
    except Exception:
        from PIL import ImageFont
        return ImageFont.load_default()


def _draw_decorative(draw, width: int, height: int, theme_words: list[str]):
    """Add subtle decorative elements to the cover."""
    tw = " ".join(theme_words).lower()

    # Horizontal lines
    draw.rectangle([60, 300, width - 60, 302], fill="#FFFFFF44")
    draw.rectangle([60, height - 150, width - 60, height - 148], fill="#FFFFFF44")

    # Subtle dot pattern if dream-themed
    if "dream" in tw or "sleep" in tw:
        import random
        for _ in range(50):
            x = random.randint(0, width)
            y = random.randint(0, height)
            r = random.randint(1, 3)
            draw.ellipse([x - r, y - r, x + r, y + r], fill="#FFFFFF15")


def _create_placeholder_cover(title: str, output_path: str):
    """Fallback: create a minimal text-based cover without PIL."""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Cover: {title}\n[Generated placeholder — install Pillow for proper cover images]\n")
    print(f"  Placeholder cover created: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python fetch_cover.py '<Book Title>' <output_path> [workspace_dir]")
        sys.exit(1)
    title = sys.argv[1]
    out = sys.argv[2]
    ws = sys.argv[3] if len(sys.argv) > 3 else None
    result = fetch_cover(title, out, ws)
    print(f"Cover saved: {result}")
