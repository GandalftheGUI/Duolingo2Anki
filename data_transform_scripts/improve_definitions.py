#!/usr/bin/env python3
"""
Generate Spanish→English flashcards with provenance columns:

Output CSV columns:
- word
- duolingo_definition
- model_definition
- cleaned_definition

Input:
- A CSV that contains at least a "word" column.
- Optionally contains "duolingo_definition" (or "definition", or "duolingo") column.

Batching:
- Sends ONLY the words (one per line) to Ollama
- Expects NDJSON back: {"word":"...","definition":"..."} per line

Usage:
    python3 improve_definitions.py \
    --in words_from_duo.csv \
    --system prompts/system_prompt5.txt \
    --out enhanced_words_from_duo.csv \
    --model qwen2.5:32b \
    --batch 100 \
    --temperature 0


Notes:
- "model_definition" is the raw model definition string.
- "cleaned_definition" applies small deterministic fixes (optional).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

# Allowed leading subject prefixes (exact form)
SUBJECT_PREFIX_PATTERN = re.compile(
    r"^\((I|you|he / she / it|we|they / you-plural)\)\s+"
)

@dataclass
class RowIn:
    word: str
    duolingo_definition: str

@dataclass
class RowOut:
    word: str
    duolingo_definition: str
    model_definition: str
    cleaned_definition: str

def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def read_input_csv(path: str) -> List[RowIn]:
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("Input CSV has no header row.")

        fields = {h.strip(): h for h in reader.fieldnames}
        # required
        if "word" not in fields:
            raise ValueError('Input CSV must contain a "word" column.')

        # optional duo definition column detection
        duo_col = None
        for candidate in ["duolingo_definition", "duolingo", "definition", "duo_definition"]:
            if candidate in fields:
                duo_col = fields[candidate]
                break

        rows: List[RowIn] = []
        for r in reader:
            w = (r.get(fields["word"]) or "").strip()
            if not w:
                continue
            d = (r.get(duo_col) if duo_col else "") or ""
            rows.append(RowIn(word=w, duolingo_definition=d.strip()))
        return rows

def chunk_list(xs: List[str], n: int) -> List[List[str]]:
    return [xs[i:i+n] for i in range(0, len(xs), n)]

def ollama_chat_stream_collect_content(
    *,
    url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: Optional[float],
    top_p: Optional[float],
    timeout_s: int = 600,
) -> str:
    payload: Dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
    }
    options: Dict = {}
    if temperature is not None:
        options["temperature"] = temperature
    if top_p is not None:
        options["top_p"] = top_p
    if options:
        payload["options"] = options

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    parts: List[str] = []
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            piece = (obj.get("message") or {}).get("content")
            if isinstance(piece, str) and piece:
                parts.append(piece)
            if obj.get("done") is True:
                break
    return "".join(parts)

def parse_ndjson_word_defs(content: str) -> Tuple[Dict[str, str], List[str]]:
    """
    Returns (map word->definition, parse_errors)
    """
    out: Dict[str, str] = {}
    errors: List[str] = []

    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    for idx, ln in enumerate(lines, start=1):
        try:
            obj = json.loads(ln)
        except Exception as e:
            errors.append(f"Line {idx}: invalid JSON ({e}): {ln[:160]}")
            continue
        if not isinstance(obj, dict):
            errors.append(f"Line {idx}: JSON not an object")
            continue
        w = obj.get("word")
        d = obj.get("definition")
        if not isinstance(w, str) or not isinstance(d, str):
            errors.append(f"Line {idx}: word/definition not strings")
            continue
        out[w] = d
    return out, errors

def post_fix_definition(defn: str) -> str:
    """
    Cleanups for your workflow:
    - remove 'oneself'
    - remove any parentheses not part of an allowed leading subject prefix
      (keeps '(it)' in gustar phrases? NOTE: this will REMOVE it unless it's in text without parentheses.
       If you want to KEEP '(it)', see KEEP_IT_PARENS option below.)
    - normalize whitespace
    """
    KEEP_IT_PARENS = True  # set False if you want to strip parentheses everywhere except subject

    # Remove banned/undesired learner phrasing
    defn = re.sub(r"\boneself\b", "", defn, flags=re.IGNORECASE)

    # Preserve allowed subject prefix if present
    prefix = ""
    rest = defn
    m = SUBJECT_PREFIX_PATTERN.match(defn)
    if m:
        prefix = defn[:m.end()]
        rest = defn[m.end():]

    # Strip parentheses from rest (optionally keep "(it)")
    if KEEP_IT_PARENS:
        # temporarily protect "(it)" tokens
        rest = rest.replace("(it)", "__KEEP_IT__")
        rest = re.sub(r"\([^)]*\)", "", rest)
        rest = rest.replace("__KEEP_IT__", "(it)")
    else:
        rest = re.sub(r"\([^)]*\)", "", rest)

    # Recombine + whitespace normalize
    cleaned = (prefix + rest).strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"\s+([,;:.!?])", r"\1", cleaned)
    cleaned = cleaned.strip(" -")
    return cleaned

def generate(
    *,
    url: str,
    model: str,
    system_prompt: str,
    words: List[str],
    batch_size: int,
    temperature: Optional[float],
    top_p: Optional[float],
    max_retries: int,
    retry_batch_size: int,
    apply_postfixes: bool,
    sleep_between_s: float,
) -> Dict[str, Tuple[str, str]]:
    """
    Returns word -> (model_definition, cleaned_definition)
    """
    results: Dict[str, Tuple[str, str]] = {}
    batches = chunk_list(words, batch_size)

    for bi, batch in enumerate(batches, start=1):
        user_prompt = "\n".join(batch)
        content = ollama_chat_stream_collect_content(
            url=url,
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            top_p=top_p,
        )
        parsed_map, _ = parse_ndjson_word_defs(content)

        missing = []
        for w in batch:
            d = parsed_map.get(w, "")
            if not isinstance(d, str) or not d.strip():
                missing.append(w)
                continue
            cleaned = post_fix_definition(d) if apply_postfixes else d
            results[w] = (d, cleaned)

        attempt = 0
        while missing and attempt < max_retries:
            attempt += 1
            next_missing: List[str] = []
            for rb in chunk_list(missing, retry_batch_size):
                if sleep_between_s:
                    time.sleep(sleep_between_s)
                retry_content = ollama_chat_stream_collect_content(
                    url=url,
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt="\n".join(rb),
                    temperature=temperature,
                    top_p=top_p,
                )
                retry_map, _ = parse_ndjson_word_defs(retry_content)
                for w in rb:
                    d = retry_map.get(w, "")
                    if not isinstance(d, str) or not d.strip():
                        next_missing.append(w)
                        continue
                    cleaned = post_fix_definition(d) if apply_postfixes else d
                    results[w] = (d, cleaned)
            missing = next_missing

        # Fill any still-missing with empty strings
        for w in missing:
            if w not in results:
                results[w] = ("", "")

        got = sum(1 for w in batch if results.get(w, ("", ""))[0].strip())
        print(f"[batch {bi}/{len(batches)}] got {got}/{len(batch)}", file=sys.stderr)

    return results

def write_output_csv(path: str, rows: List[RowOut]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["word", "duolingo_definition", "model_definition", "cleaned_definition"],
        )
        writer.writeheader()
        for r in rows:
            writer.writerow(
                {
                    "word": r.word,
                    "duolingo_definition": r.duolingo_definition,
                    "model_definition": r.model_definition,
                    "cleaned_definition": r.cleaned_definition,
                }
            )

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input CSV with at least 'word' column")
    ap.add_argument("--system", required=True, help="System prompt file")
    ap.add_argument("--out", required=True, help="Output CSV path")
    ap.add_argument("--model", default="qwen2.5:32b", help="Ollama model name")
    ap.add_argument("--url", default=DEFAULT_OLLAMA_URL, help="Ollama /api/chat URL")
    ap.add_argument("--batch", type=int, default=100, help="Words per request")
    ap.add_argument("--retry-batch", type=int, default=25, help="Words per retry request")
    ap.add_argument("--retries", type=int, default=2, help="Max retry rounds for missing outputs")
    ap.add_argument("--temperature", type=float, default=0.0, help="Temperature (0 recommended)")
    ap.add_argument("--top-p", type=float, default=1.0, help="Top-p (1 recommended)")
    ap.add_argument("--no-clean", action="store_true", help="Disable cleaned_definition post-fixes")
    ap.add_argument("--sleep", type=float, default=0.0, help="Sleep between requests (seconds)")
    args = ap.parse_args()

    system_prompt = read_text(args.system)
    inputs = read_input_csv(args.inp)
    if not inputs:
        print("No input rows found.", file=sys.stderr)
        return 2

    words = [r.word for r in inputs]

    word_to_defs = generate(
        url=args.url,
        model=args.model,
        system_prompt=system_prompt,
        words=words,
        batch_size=args.batch,
        temperature=args.temperature,
        top_p=args.top_p,
        max_retries=args.retries,
        retry_batch_size=args.retry_batch,
        apply_postfixes=(not args.no_clean),
        sleep_between_s=args.sleep,
    )

    out_rows: List[RowOut] = []
    missing_count = 0
    for r in inputs:
        model_def, cleaned_def = word_to_defs.get(r.word, ("", ""))
        if not model_def.strip():
            missing_count += 1
        out_rows.append(
            RowOut(
                word=r.word,
                duolingo_definition=r.duolingo_definition,
                model_definition=model_def,
                cleaned_definition=cleaned_def,
            )
        )

    write_output_csv(args.out, out_rows)

    print(f"Wrote {len(out_rows)} rows to {args.out}", file=sys.stderr)
    if missing_count:
        print(f"Missing model definitions: {missing_count}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
