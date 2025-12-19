# Duolingo2Anki
LLM-powered pipeline for extracting, cleaning, and normalizing Duolingo vocabulary into Anki-ready flashcards.

<img width="978" height="415" alt="image" src="https://github.com/user-attachments/assets/51752d02-0d1f-48eb-85b2-fd0281b41bff" />

### TL;DR

- Extracts Duolingo vocabulary into CSV
- Uses a fixed system prompt + Qwen 2.5 32B to normalize definitions
- Preserves provenance and original order
- Outputs Anki-ready flashcards

## How to run

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/) installed and running
- A local LLM pulled (recommended: `qwen2.5:32b`)

```bash
ollama pull qwen2.5:32b
```
### Input format
The script expects a CSV with at least these columns:

```csv
word,definition
solamente,"only, just"
plaza,"plaza, bullring, seat"
```

Note: The full Duolingo word list is not included due to data ownership limitations; please use your own export to reproduce results.
See [examples/words_from_duo.csv](examples/words_from_duo.csv.example) for a representative sample.

### Run the pipeline
```bash
python3 improve_definitions.py \
  --in words_from_duo.csv \
  --out enhanced_words.csv \
  --system prompts/system_prompt5.txt \
  --model qwen2.5:32b \
  --batch 100 \
  --temperature 0
```
The output CSV preserves the original word order and includes full provenance:

```csv
word,definition,model_definition,cleaned_definition
```

### Ouput format
```csv
word,duolingo_definition,model_definition,cleaned_definition
solamente,"only, just","only, just","only, just"
plaza,"plaza, bullring, seat","square, plaza","square, plaza"
lindo,"beautiful, lovely, nice","cute, pretty, handsome","cute, pretty, handsome"
```
See [examples/enhanced_words_from_duo.csv](examples/enhanced_words_from_duo.csv.example) for example output.

# Overview

This project started as a personal attempt to improve Spanish vocabulary retention, but after manually correcting 100+ vocab flashcards, I saw it for what it really was: <ins>a small, tightly-scoped **data cleaning and LLM evaluation pipeline** project.</ins> 😎

The core problem was not language learning itself. Duolingo exposes a large amount of semi-structured data through a UI, provides no export functionality, and ships definitions that are poorly suited for reuse. Rather than manually fixing thousands of entries, I treated this as an engineering problem: extract messy data, normalize it into a clean schema, and apply LLMs in a controlled, repeatable way (I am actually learning Spainish after all and will have more vocab words in the future).

The end result is a pipeline that:

- extracts ~2,500 vocabulary entries from Duolingo
- cleans and normalizes inconsistent definitions
- applies LLM-assisted transformations under strict constraints
- produces output optimized for spaced repetition in Anki

While the downstream use case is language learning, the work itself centers on **data extraction, transformation, evaluation, and iteration with LLMs**.

### Objective

Build a repeatable pipeline that takes noisy, semi-structured third-party data and transforms it into high-quality, task-specific output.

Concretely, this involved:

- extracting data from an unfriendly source
- defining and enforcing a strict output schema
- using LLMs as transformation tools rather than black boxes
- evaluating prompts and models empirically
- preserving provenance and debuggability throughout the pipeline

### Context

While learning Spanish with Duolingo, I've accumulated 2,500+ vocabulary entries. Duolingo’s built-in review vocabulary tools are limited (to put it mildly), and the English definitions provided are often ambiguous, overly broad, or actively misleading for recall-based study (i.e. flashcards).

Now that I've put my engineering hat on, I need to answer some questions:

- How do you reliably extract data from a UI that doesn’t want to give it to you?
- How do you normalize inconsistent definitions into something usable?
- How do you constrain an LLM so it produces consistent, recall-friendly output?
- How do you evaluate and iterate without guessing?

## Part 1: Data Extraction and Normalization

### Extracting vocabulary from Duolingo

Duolingo exposes learned vocabulary through a practice page that loads approximately 50 entries at a time and provides no export functionality.

<img width="1720" height="1139" alt="image" src="https://github.com/user-attachments/assets/489c48cb-7d2f-4eb3-a774-d09e97a6963c" />

Rather than automate the UI, the simplest solution was manual:

1. Click **Load more** until all entries are visible (about a minute).
2. Save the page locally.

This produced a single, albeit very large HTML file containing all vocabulary entries and definitions.

### Converting HTML into a CSV

The saved HTML file was ~13MB and effectively one long line of markup, making it impractical to inspect directly.

Instead, I used ChatGPT to generate a small Python script that:

- locates vocabulary entries in the DOM
- extracts the Spanish word and English definition
- writes them to a CSV

This produced an initial dataset of the form:

```csv
word,definition
solamente,"only, just"
plaza,"plaza, bullring, seat"
lindo,"beautiful, lovely, nice"
principal,"main, central, front"
habitante,inhabitant
las afueras,outskirts
```

At this point, the data was usable — but not good.

#### The Problem with Duolingo's Definitions

Many of Duolingo's definitions are poorly suited for recall-based study. They often:

- mix unrelated meanings
- collapse multiple parts of speech into one entry
- include conjugated verb forms without context
- resemble dictionary entries rather than flashcard material

A representative example:

```python
"enfrente": "in front, (I/he/she/it/you) bring … face to face, (I/he/she/it/you) bring … into conflict","in front of, opposite"
```
This is a mess, and it won't work as a flashcard. It is a terrible combination of both being too wordy and ambiguous.

What I want during review is clarity:

```python
"enfrente": "in front of / opposite"
```

Manually fixing thousands of entries was not realistic (I am a lazy engineer who strives to automate as much as possible after all), which led to the second phase.

## Part 2: LLM-Assisted Definition Improvement

### Objective

Automatically improve Duolingo's English definitions so they are:

- short
- specific
- consistent
- optimized for recall rather than explanation

### Generating Initial System Prompts
Before automating anything, I had already spent significant time manually correcting flashcards with ChatGPT. Over time, this became an implicit feedback loop: rejecting grammar explanations, correcting vague output, and reinforcing what “good” looked like.

The first step was to capture that context. I asked ChatGPT to summarize the entire conversation into a single system prompt. This became [system_prompt1](prompts/system_prompt1.txt).

It wasn’t perfect, but it established a baseline.

In parallel, I took a more concrete approach. After manually correcting ~100 definitions to exactly the format I wanted, I exported those examples to a CSV and asked ChatGPT to infer the underlying rules and generate a system prompt from them.

This approach produced better results because it encoded patterns from real examples rather than abstract instructions.

### Iteration and Evaluation

From there, the process became systematic:

1. Run my new system prompts against a fixed test set.
1. Compare outputs side-by-side.
1. Look for regressions, verbosity, and rule violations.
1. Generate a new system prompt that attempts to fix issues with previous iterations.

Some prompts were too permissive and ignored formatting constraints. Others were overly strict and produced unnatural English. I generated prompts until I felt performance had plateaued and clear tradeoffs had immerged. In the end, ended up with 7 different prompts  (check them out in the [prompts folder](prompts/)) and selecting a final prompt was straightforward.


### Model Selection

I tested multiple models using the same prompts and evaluation set:

- Mixtral 7B
- Qwen 14B
- Qwen 32B
- LLaMA 70B

Key observations:

- Smaller models were fast but less consistent.
- Moving from Qwen 14B to Qwen 32B produced a significant quality improvement.
- Moving from Qwen 32B to LLaMA 70B did not materially improve output quality, but did significantly increase runtime.
- Qwen 2.5 32B provided the best balance between quality, instruction adherence, and performance.

(Take at the [test_runs folder](test_runs/) for a more granular look at the how the performance differed)

### Pipeline Automation

The final pipeline looks like this:

1. Read the original Duolingo CSV (word, definition).
2. Send words to the LLM in batches using the fixed system prompt.
3. Require one NDJSON object per word:

   ```json
   {"word":"…","definition":"…"}
   ```

4. Validate output structure.
5. Apply minimal deterministic cleanup.
6. Write results to a new CSV.

Preserving provenance was a key design decision. The output schema is:

```csv
word,definition,model_definition,cleaned_definition
```
The script batches requests, retries failures, and guarantees output order matches input order.

### Example Results

| Spanish | Duolingo Definition | Improved Definition |  |
|---------|---------------------|---------------------|--|
| empuje | drive, go, drove | (you formal) push | _corrected the original which was just plain wrong_ |
| se ríe | laugh | (he / she / it) laughs | _original was correct, but the new version has enough context to know which verb form is being secified_ |
| al salir | (I) left, left | when leaving | _another example of correcting an incorrect definition_ |

(More results can be seen here: [enhanced_words.csv](examples/enhanced_words_from_duo.csv.example))

Spanish encodes subject and meaning directly in verb forms far more than English does. Many original definitions omit that information, which makes comprehension harder later when reading or listening.

By reflecting subject only when the Spanish form encodes it, the resulting flashcards reinforce complete ideas rather than isolated stems.

## Outcome

The result is a repeatable, auditable pipeline that turns noisy third-party data into clean, task-specific output.

Studying is faster, recall is clearer, and the system can be rerun any time new vocabulary is added.

The Spanish use case was the motivation, but the core takeaway is about applying LLMs as constrained transformation tools, not oracles. As such, they should be evaluated with the same rigor as any other component in a data pipeline.
