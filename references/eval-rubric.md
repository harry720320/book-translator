# Model-as-Judge Evaluation Rubric

You are evaluating the quality of a Chinese literary translation. Score the translation on each dimension below. Be strict — a score of 3 means "acceptable for a first draft," not "good."

## Scoring Dimensions

### 1. Naturalness (1-5)

Does this read like native Chinese, or can you tell it was translated from English?

| Score | Criteria |
|---|---|
| 5 | Feels like original Chinese literature. No trace of English sentence structure. |
| 4 | Natural overall; 1-2 sentences feel slightly translated but it would take a careful reader to notice. |
| 3 | Mostly natural but occasional English rhythm or word order breaks through. |
| 2 | Frequent translationese — the English original is visible behind the Chinese. |
| 1 | Reads like word-for-word translation. Heavy translationese throughout. |

Key indicators: modifier chain length, 的 density, unnecessary pronouns, 和 overuse, 被-passive frequency.

### 2. Register Match (1-5)

Does the Chinese tone/register match the original English register?

| Score | Criteria |
|---|---|
| 5 | Perfect register match. Formal↔书面, casual↔口语, literary↔文学. Each registers feels authentic in Chinese. |
| 4 | Good match; minor slips in 1-2 paragraphs where dialogue is slightly stiff or narration slightly flat. |
| 3 | Generally right register but inconsistent. Dialogue reads like narration, or narration lacks literary quality. |
| 2 | Register consistently off. Dialogue sounds written, narration lacks rhythm, action lacks pace. |
| 1 | Flat, undifferentiated register. All parts sound the same. |

### 3. Dialogue Quality (1-5)

Do characters sound like distinct, believable people when speaking?

| Score | Criteria |
|---|---|
| 5 | Each character has a distinct voice. Dialogue sounds spoken aloud, with natural rhythm and oral markers. |
| 4 | Dialogue is natural but characters have similar speech patterns. |
| 3 | Serviceable dialogue but flat — conveys information but lacks personality. |
| 2 | Dialogue sounds like prose with quotation marks. No oral quality, no character differentiation. |
| 1 | Stiff, unnatural dialogue. Characters speak in ways no real person would. |

Key indicators: sentence length (6-15 chars for dialogue), sentence-final particles, contractions, distinct speech patterns per character.

### 4. Literary Quality (1-5)

Are metaphors, imagery, rhythm, and stylistic features of the original preserved or well-adapted?

| Score | Criteria |
|---|---|
| 5 | Literary features preserved or creatively adapted. Metaphors feel natural in Chinese. Imagery vivid. Rhythm intentional. |
| 4 | Good handling of literary elements; 1-2 metaphors or images could be sharper. |
| 3 | Adequate but safe. Metaphors are translated literally rather than adapted. Imagery is accurate but flat. |
| 2 | Literary qualities diminished. Metaphors explained rather than translated. Rhythm ignored. |
| 1 | Literary qualities lost. Flat, functional text with no stylistic ambition. |

### 5. Terminology Consistency (1-5)

Are names, places, and special terms consistent and well-chosen?

| Score | Criteria |
|---|---|
| 5 | All terms consistent across chapters. Transliterations use standard or well-chosen characters. |
| 4 | Consistent; 1-2 minor transliteration choices could be improved. |
| 3 | Mostly consistent but 1-2 terms drift between chapters or have awkward transliterations. |
| 2 | Multiple inconsistencies. Same character/place translated differently in different places. |
| 1 | Frequent drift. No apparent terminology management. |

## Evaluation Format

For each chapter, output:

```json
{
  "chapter": "chapter_0005.md",
  "scores": {
    "naturalness": {"score": 4, "justification": "Generally natural but paragraph 3 has a 的-chain that betrays English structure."},
    "register_match": {"score": 3, "justification": "Dialogue in paragraphs 5-6 is too formal for the casual bar scene described."},
    "dialogue_quality": {"score": 4, "justification": "The bartender has a distinct voice but the protagonist's speech is generic."},
    "literary_quality": {"score": 3, "justification": "The storm metaphor is translated literally — a Chinese storm metaphor would use different imagery."},
    "terminology": {"score": 5, "justification": "All names and terms consistent with glossary and previous chapters."}
  },
  "overall": 3.8,
  "worst_passage": {
    "text": "...",
    "issue": "Heavy translationese — long modifier chain + 被-passive + 当...的时候 all in two sentences."
  },
  "best_passage": {
    "text": "...",
    "strength": "Dialogue flows naturally, character voice is distinct, reads like original Chinese."
  }
}
```

## Scoring Guidelines

- Score each dimension independently — a chapter can have great dialogue (5) but poor register match (2)
- Justify every score with a specific example from the text
- Be strict. A score of 3 isn't "average" — it's "needs improvement"
- The overall score is the mean of the 5 dimensions
