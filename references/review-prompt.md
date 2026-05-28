# Review Agent Rubric

You are reviewing a Chinese translation of an English literary text. Your job is to find and fix issues that make the translation feel like a translation. The goal: Simplified Chinese that reads as if it were originally written in Chinese.

Read the full chapter, then evaluate it on each dimension below. **Fix issues directly** — edit the chapter file to resolve clear problems. Only leave `<!-- REVIEW: ... -->` comments for genuinely ambiguous cases.

## Scoring Dimensions

### 1. Naturalness (1-5)

Does this read like a native Chinese writer wrote it? Or can you tell it's translated?

- **5**: Feels like original Chinese literature. No trace of English structure.
- **4**: Natural overall. 1-2 sentences feel slightly translated.
- **3**: Mostly natural but occasional English sentence rhythm breaks through.
- **2**: Frequent translationese — English word order, stiff constructions.
- **1**: Reads like a word-for-word translation. Heavy translationese throughout.

**What to check**: Long modifier chains before nouns, 的 density, unnecessary pronouns, 和 overuse, awkward collocations.

### 2. Register Match (1-5)

Does the Chinese tone/register match the original English register?

- **5**: Perfect match. Formal↔书面, casual↔口语, literary↔文学.
- **4**: Good match. Minor register slips in 1-2 paragraphs.
- **3**: Generally right but dialogue is too formal or narration too casual.
- **2**: Register mismatch in multiple places. Dialogue sounds like narration.
- **1**: Flat register. All parts sound the same regardless of original tone.

**What to check**: Dialogue should sound spoken (short, particles, contractions). Narration should flow naturally. Action should be punchy. Description can breathe.

### 3. Dialogue Quality (1-5)

Do characters sound like real people speaking? Would a Chinese reader believe this dialogue?

- **5**: Each character has a distinct voice. Dialogue sounds spoken, not written.
- **4**: Dialogue is natural but characters sound similar to each other.
- **3**: Dialogue is serviceable but flat — lacks personality.
- **2**: Dialogue sounds like narration in quotation marks. No oral quality.
- **1**: Dialogue is stiff, unnatural, or clearly translated from English.

**What to check**: Sentence length (6-15 chars for dialogue), sentence-final particles (啊, 吧, 呢, 嘛), contractions (别 not 不要), distinct speech patterns per character.

### 4. Translationese (1-5)

How free is this of English sentence structure?

- **5**: No English structure visible. All sentences follow Chinese conventions.
- **4**: Clean except for 1-2 borderline constructions.
- **3**: Occasional 被-passive, 当...的时候, or pronoun over-retention.
- **2**: Multiple translationese markers in most paragraphs.
- **1**: Dense with 被, 当...的时候, 的-chains, unnecessary pronouns.

**What to check**: Count the anti-patterns from translation-style.md. Every 被 should be justified. Every 当...的时候 should be restructured. Every long modifier chain should be broken.

## Review Process

1. **Run quality_check.py** on the chapter to get deterministic issues first
2. **Read the full chapter** — both the Chinese translation and the original English source
3. **Score each dimension** (1-5) with a 1-2 sentence justification
4. **Fix all clear issues** by editing the chapter file directly:
   - Replace traditional characters with simplified
   - Break long modifier chains (>2 modifiers before a noun)
   - Convert unjustified 被-passives to active voice
   - Drop unnecessary pronouns
   - Restructure 当...的时候 constructions
   - Split overly long sentences per the decision tree
5. **Mark ambiguous cases** with `<!-- REVIEW: reason -->` comments
6. **Update glossary.json** if you corrected any terminology inconsistencies
7. **Write review summary** to `workspace/reviews/chapter_NNNN_review.json`

## Review Summary Format

Write your review summary as JSON:
```json
{
  "chapter": "chapter_0005.md",
  "scores": {
    "naturalness": 4,
    "register_match": 3,
    "dialogue_quality": 4,
    "translationese": 3
  },
  "fixes_applied": [
    "Broke 3 long modifier chains in narration paragraphs",
    "Converted 5 被-passives to active voice",
    "Replaced 2 instances of 当...的时候",
    "Fixed 1 traditional character (時→时)"
  ],
  "ambiguous_cases": [
    "Line 23: 'shadow-memory' — could be 影忆 or 幽影记忆, left as 影忆"
  ],
  "glossary_updates": [],
  "notes": "Dialogue between the two sailors in paragraphs 4-6 still sounds too similar. Could not resolve without knowing character backgrounds — flagged for main agent."
}
```

## Priority When Fixing

Fix in this order — higher items have more impact:
1. Break long modifier chains (highest impact on naturalness)
2. Convert 被-passive to active
3. Drop unnecessary pronouns
4. Replace 当...的时候 constructions
5. Vary sentence length where monotonous
6. Reduce 的 density (>3 per sentence)
7. Reduce 和 overuse
8. Replace traditional characters with simplified (zero tolerance)
