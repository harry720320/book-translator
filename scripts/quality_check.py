#!/usr/bin/env python3
"""Deterministic quality checks for Chinese translation chapters.

Zero model calls. Input: translated chapter file + glossary.json.
Output: JSON report with flagged issues.

Usage:
    python quality_check.py <chapter_file> [--glossary glossary.json] [--json report.json]
"""

import json
import re
import sys
import argparse
from pathlib import Path
from collections import Counter
from math import sqrt


# Traditional Chinese characters — only characters with a distinct simplified form.
# Characters that are identical in both scripts (e.g. 道, 都, 身) are NOT included.
# Map: traditional -> simplified (for reporting)
TRADITIONAL_CHARS: dict[str, str] = {
    # From translation-style.md common offenders table
    "説": "说", "時": "时", "個": "个", "們": "们", "來": "来", "後": "后",
    "會": "会", "過": "过", "對": "对", "開": "开", "關": "关", "學": "学",
    "見": "见", "裡": "里", "裏": "里", "麼": "么", "寫": "写", "為": "为",
    "國": "国", "書": "书", "長": "长", "門": "门", "間": "间", "頭": "头",
    "體": "体", "實": "实", "從": "从", "當": "当", "還": "还", "電": "电",
    "點": "点", "東": "东", "氣": "气", "車": "车", "動": "动", "現": "现",
    "發": "发", "業": "业", "經": "经", "義": "义", "廣": "广", "樂": "乐",
    "專": "专", "機": "机", "錢": "钱",
    # Additional common traditional characters
    "難": "难", "處": "处", "讓": "让", "報": "报", "場": "场", "萬": "万",
    "與": "与", "買": "买", "賣": "卖", "號": "号", "節": "节", "馬": "马",
    "魚": "鱼", "鳥": "鸟", "龍": "龙", "愛": "爱", "飛": "飞", "風": "风",
    "區": "区", "華": "华", "孫": "孙", "劉": "刘", "張": "张", "楊": "杨",
    "趙": "赵", "黃": "黄", "吳": "吴", "陳": "陈", "鄭": "郑", "鄧": "邓",
    "馮": "冯", "蔣": "蒋", "韓": "韩", "盧": "卢", "羅": "罗", "蕭": "萧",
    "獄": "狱", "稱": "称", "確": "确", "雖": "虽", "醫": "医", "鐵": "铁",
    "銀": "银", "護": "护", "際": "际", "領": "领", "預": "预", "顯": "显",
    "驗": "验", "鮮": "鲜", "齊": "齐", "術": "术", "衛": "卫", "補": "补",
    "裝": "装", "觀": "观", "許": "许", "該": "该", "說": "说", "謝": "谢",
    "識": "识", "議": "议", "變": "变", "軍": "军", "較": "较", "輕": "轻",
    "連": "连", "進": "进", "運": "运", "達": "达", "農": "农", "遠": "远",
    "選": "选", "遺": "遗", "縣": "县", "據": "据", "舉": "举", "亞": "亚",
    "畫": "画", "講": "讲", "證": "证", "讀": "读", "談": "谈", "調": "调",
    "論": "论", "試": "试", "詩": "诗", "計": "计", "設": "设", "評": "评",
    "詞": "词", "認": "认", "語": "语", "誤": "误", "請": "请", "誰": "谁",
    "課": "课", "資": "资", "質": "质", "賴": "赖", "費": "费", "賓": "宾",
    "賞": "赏", "賢": "贤", "賠": "赔", "賦": "赋", "賽": "赛", "贊": "赞",
    "贏": "赢", "趕": "赶", "蹤": "踪", "載": "载", "輩": "辈", "輪": "轮",
    "辦": "办", "辭": "辞", "辮": "辫", "辯": "辩", "週": "周", "遊": "游",
    "違": "违", "適": "适", "遞": "递", "遲": "迟", "邊": "边", "郵": "邮",
    "鄉": "乡", "鄰": "邻", "釋": "释", "製": "制", "複": "复", "褲": "裤",
    "襯": "衬", "規": "规", "視": "视", "覽": "览", "覺": "觉", "觸": "触",
    "訂": "订", "訪": "访", "訴": "诉", "診": "诊", "話": "话", "詳": "详",
    "諸": "诸", "謀": "谋", "諷": "讽", "負": "负", "財": "财", "責": "责",
    "貨": "货", "貿": "贸", "貝": "贝", "龜": "龟",
}

# Build a set of traditional chars for fast lookup
TRADITIONAL_SET: set[str] = set(TRADITIONAL_CHARS.keys())


def load_file(filepath: str | Path) -> str:
    """Load file content, return stripped text."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    return path.read_text(encoding="utf-8")


def load_glossary(filepath: str | Path) -> dict | None:
    """Load glossary.json if it exists, return None otherwise."""
    path = Path(filepath)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def split_sentences(text: str) -> list[tuple[str, int]]:
    """Split text into sentences with line numbers. Returns [(sentence, line_number), ...]."""
    lines = text.split("\n")
    results = []
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith(">"):
            continue
        # Split on Chinese/English sentence boundaries
        sentences = re.split(r"[。！？.!?\n]", stripped)
        for s in sentences:
            s = s.strip()
            if s:
                results.append((s, line_num))
    return results


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs (non-empty lines)."""
    return [line.strip() for line in text.split("\n")
            if line.strip() and not line.strip().startswith("#") and not line.strip().startswith(">")]


def check_traditional_chars(text: str) -> dict:
    """Find traditional Chinese characters in text."""
    found: dict[str, list[dict]] = {}
    for line_num, line in enumerate(text.split("\n"), 1):
        for i, char in enumerate(line):
            if char in TRADITIONAL_SET:
                simplified = TRADITIONAL_CHARS.get(char, "?")
                if char not in found:
                    found[char] = []
                found[char].append({
                    "line": line_num,
                    "column": i,
                    "context": line[max(0, i - 10):i + 10].strip(),
                    "simplified": simplified,
                })

    all_issues = []
    for trad_char, occurrences in found.items():
        for occ in occurrences:
            all_issues.append(occ)

    return {
        "count": len(all_issues),
        "unique_traditional": len(found),
        "issues": all_issues,
    }


def check_de_density(sentences: list[tuple[str, int]]) -> dict:
    """Check 的 density per sentence. Flag sentences with >3 的."""
    flagged = []
    for sentence, line_num in sentences:
        de_count = sentence.count("的")
        if de_count > 3:
            flagged.append({
                "line": line_num,
                "de_count": de_count,
                "sentence": sentence[:60] + ("..." if len(sentence) > 60 else ""),
            })
    return {
        "flagged_count": len(flagged),
        "score": "good" if len(flagged) <= len(sentences) * 0.05 else "warn",
        "issues": flagged,
    }


def check_bei_passive(sentences: list[tuple[str, int]]) -> dict:
    """Count 被-constructions. Flag all instances."""
    flagged = []
    for sentence, line_num in sentences:
        if "被" in sentence:
            # Skip common non-passive uses like 被子, 被窝
            if re.search(r"被(?!子|窝|褥|套|单)", sentence):
                flagged.append({
                    "line": line_num,
                    "sentence": sentence[:80] + ("..." if len(sentence) > 80 else ""),
                })

    return {
        "count": len(flagged),
        "issues": flagged,
    }


def check_dang_shihou(sentences: list[tuple[str, int]]) -> dict:
    """Find 当...的时候 constructions."""
    flagged = []
    for sentence, line_num in sentences:
        if "当" in sentence and "的时候" in sentence:
            flagged.append({
                "line": line_num,
                "sentence": sentence[:80] + ("..." if len(sentence) > 80 else ""),
            })

    return {
        "count": len(flagged),
        "issues": flagged,
    }


def check_glossary_drift(text: str, glossary: dict | None) -> dict:
    """Check if translated text uses terms that conflict with the glossary."""
    if glossary is None:
        return {"consistent": True, "note": "No glossary provided"}

    issues = []
    all_terms: dict[str, str] = {}

    # Collect all known terms from glossary
    for category in ["characters", "places", "terms"]:
        if category in glossary:
            for en, zh in glossary[category].items():
                all_terms[en] = zh

    # For each glossary term, check if the Chinese translation appears in text
    for en, expected_zh in all_terms.items():
        if expected_zh not in text:
            issues.append({
                "term": en,
                "expected": expected_zh,
                "issue": "term_not_found",
                "note": f"Expected '{expected_zh}' but not found in chapter",
            })

    # Check for inconsistent usage: same English name with different Chinese
    # Look for partial matches that suggest drift
    for en, expected_zh in all_terms.items():
        # Extract the first 1-2 characters of expected and look for near matches
        if len(expected_zh) >= 2:
            prefix = expected_zh[:2]
            # Find all instances where something similar but not exact appears
            pattern = re.compile(re.escape(prefix[:1]) + r"." + re.escape(expected_zh[1:]) if len(expected_zh) > 2
                                 else re.escape(prefix))
            # This is fuzzy — flag for human review
            pass  # Fuzzy matching is best left to the review agent

    return {
        "consistent": len(issues) == 0,
        "issues": issues,
    }


def check_sentence_variance(sentences: list[tuple[str, int]]) -> dict:
    """Compute character-count variance across sentences. Low variance = monotonous rhythm."""
    lengths = [len(s) for s, _ in sentences]
    if len(lengths) < 3:
        return {"score": "insufficient_data", "stddev": 0, "mean": 0}

    mean = sum(lengths) / len(lengths)
    variance = sum((l - mean) ** 2 for l in lengths) / len(lengths)
    stddev = sqrt(variance)

    if stddev < 8:
        score = "low"  # Too uniform
    elif stddev < 15:
        score = "moderate"
    else:
        score = "good"  # Healthy variation

    return {
        "score": score,
        "stddev": round(stddev, 1),
        "mean": round(mean, 1),
        "min": min(lengths),
        "max": max(lengths),
        "sentence_count": len(lengths),
    }


def check_he_overuse(paragraphs: list[str]) -> dict:
    """Count 和 per paragraph. Flag paragraphs with excessive 和."""
    flagged = []
    for i, para in enumerate(paragraphs):
        he_count = para.count("和")
        char_count = len(para.replace(" ", ""))
        if char_count > 0 and he_count > max(3, char_count * 0.03):
            flagged.append({
                "paragraph": i + 1,
                "he_count": he_count,
                "char_count": char_count,
                "text": para[:80] + ("..." if len(para) > 80 else ""),
            })

    return {
        "flagged_count": len(flagged),
        "issues": flagged,
    }


def run_all_checks(text: str, glossary: dict | None = None) -> dict:
    """Run all quality checks and return a combined report."""
    sentences = split_sentences(text)
    paragraphs = split_paragraphs(text)

    traditional = check_traditional_chars(text)
    de_density = check_de_density(sentences)
    bei = check_bei_passive(sentences)
    dang = check_dang_shihou(sentences)
    glossary_drift = check_glossary_drift(text, glossary)
    variance = check_sentence_variance(sentences)
    he_overuse = check_he_overuse(paragraphs)

    # Determine overall status
    has_major_issues = (
        traditional["count"] > 0 or
        de_density["score"] == "warn" or
        bei["count"] > 5 or
        len(dang["issues"]) > 3 or
        (isinstance(glossary_drift.get("consistent"), bool) and not glossary_drift.get("consistent", True)) or
        variance.get("score") == "low"
    )

    report = {
        "traditional_chars": traditional,
        "de_density": de_density,
        "bei_passive": bei,
        "dang_shihou": dang,
        "glossary_drift": glossary_drift,
        "sentence_variance": variance,
        "he_overuse": he_overuse,
        "overall": "needs_review" if has_major_issues else "clean",
    }

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Deterministic quality checks for Chinese translation chapters"
    )
    parser.add_argument("chapter", help="Path to translated chapter file (.md or .txt)")
    parser.add_argument("--glossary", help="Path to glossary.json", default=None)
    parser.add_argument("--json", help="Output JSON report to file", default=None)
    parser.add_argument("--quiet", action="store_true", help="Print only overall status")
    args = parser.parse_args()

    text = load_file(args.chapter)
    glossary = load_glossary(args.glossary) if args.glossary else None

    report = run_all_checks(text, glossary)

    if args.json:
        Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    if args.quiet:
        print(report["overall"])
    else:
        # Use ascii-safe output on Windows consoles that can't handle UTF-8
        try:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        except UnicodeEncodeError:
            print(json.dumps(report, ensure_ascii=True, indent=2))

    return 0 if report["overall"] == "clean" else 1


if __name__ == "__main__":
    sys.exit(main())
