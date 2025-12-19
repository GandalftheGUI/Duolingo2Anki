## Duolingo2Anki Part 1: Get the data

### Objective

Get vocabulary words from Duolingo into Anki for easier and more effective vocabulary studying.

### Context

I have been spending a lot of time learning Spanish, and Duolingo has been super helpful in that regard. What hasn’t been great is retaining all the vocabulary Duolingo is blasting me with, and their vocabulary review practice is pretty lacking, to put it mildly. I have used Anki for spaced repetition practice (think flashcards), and I think that is a better tool for vocabulary practice.

### Plan of action

1. Download all words learned from Duolingo (~2,500).
2. Format those words into a CSV, formatted like: `[spanish_word, english_definition]`.
3. Learn some Spanish vocabulary.

### Execution

#### Downloading all the words

Duolingo has a practice section that shows all the words you’ve learned along with their definitions. Unfortunately, Duolingo doesn’t have an export option, and they only load ~50 words at a time; then you have to click **Load more** and another 50 load. 

<img width="1720" height="1139" alt="image" src="https://github.com/user-attachments/assets/489c48cb-7d2f-4eb3-a774-d09e97a6963c" />

As a software engineer, I was thinking about writing some kind of automation to keep loading things, but I realized I was overthinking this.

I found the easiest way to download all words was to just keep clicking **Load more** until everything was loaded. It only took about a minute.

Right-click, save the page, and we’ve got it. 😎

#### Turn the HTML into a CSV

My first attempt was to just ask ChatGPT to do this, but it complained about the 13 MB of text it was asked to process. Instead, I simply asked it for a Python script to do it for me.

I just needed to provide a little bit of HTML to ChatGPT to show it how the data was formatted, but this turned out to be a little more difficult than I originally envisioned. VS Code and Cursor both crashed when trying to open the file and since everything was in one super big line navigating with Vim was pretty terrible too... so the simplest thing to do was just drop in a screenshot of the HTML from the inspector (🤪).

<img width="635" height="599" alt="image" src="https://github.com/user-attachments/assets/1bc99b84-feaf-4a3c-ade9-69281ea67856" />

After providing a little of the HTML to ChatGPT to show it how the data was structured, it gave me a nice script to extract the data to a CSV. (Check out `html_to_csv.py` if you are curious what ChatGPT spat out)

...and one run later we have our CSV!

```csv
word,definition
solamente,"only, just"
plaza,"plaza, bullring, seat"
lindo,"beautiful, lovely, nice"
principal,"main, central, front"
habitante,inhabitant
las afueras,outskirts
[...]
```

Looks good 😎 — a quick import into Anki and we are golden.

…or so I thought.

It turns out a lot of the definitions Duolingo provides here are pretty trash for vocabulary study. Many of them are overly broad, mix unrelated grammatical forms, or try to be a mini-dictionary instead of something optimized for recall.

Here’s a concrete example of what I mean by a **bad definition**:

```csv
enfrente,"in front, (I/he/she/it/you) bring … face to face, (I/he/she/it/you) bring … into conflict","in front of, opposite"
```

This is actively unhelpful in an Anki context:

- It mixes multiple parts of speech.
- It includes conjugated verb forms that aren't even relevant to the word being studied.
- It forces you to parse grammar instead of just remembering what the word means.
- It answers questions you are not asking when reviewing a flashcard.

When I’m studying, I don’t want to think:

“Is this a preposition, a verb, or some weird abstract concept?”

I just want:

“Oh right — enfrente means in front of / opposite.”

I started studying with the raw Duolingo export, but the more I worked, the more I realized that manually fixing 2,500+ definitions is not the move.

I was already using ChatGPT to help double-check some of the definitions that looked off, so why not just do this for the whole thing?

## Duolingo2Anki Part 2: AI-enhance those definitions

### Objective

Automatically improve Duolingo's English definitions so they are:

- short
- specific
- consistent
- actually useful for recall in Anki

### Plan of action

1. Condense the rules for formatting into a system prompt.
2. Test and select an LLM to use.
3. Write a script that queries the LLM and builds a new and improved CSV.

#### Generating the first system prompts

Before automating anything, I had already spent a lot of time manually fixing cards with ChatGPT open in another window. Over the course of that work, I’d effectively trained ChatGPT on my preferences through a long back-and-forth conversation: correcting it, telling it when a definition was too vague, when it was trying to teach grammar, or when it was overthinking things.

Rather than throw that context away, I asked ChatGPT to summarize that entire conversation into a single system prompt. That became system_prompt1.

It wasn’t great, but it was a starting point. It captured my intent, even if it still produced a lot of dictionary-style output and explanatory fluff.

In parallel, I took a more concrete approach.

By that point I had manually corrected around 100 words to exactly the format I wanted. I exported those into a CSV and asked ChatGPT to infer the rules and turn that into a system prompt. This became the next iteration.

This prompt was more grounded. Instead of describing what I wanted in abstract terms, it encoded patterns from real examples of "good" output.

#### Iteration and evaluation

From there, the process became very mechanical:

1. Generate a new system prompt.
2. Run it against the same fixed test set of words.
3. Compare outputs side-by-side.
4. Look for regressions, rule violations, and unnecessary verbosity.

Some prompts were too loose and ignored formatting rules. Others were too strict and produced awkward or unnatural English. Bigger models tended to over-explain; smaller ones sometimes dropped important distinctions.

I iterated and evaluated each subsequent prompt until I had a large enough spread of behaviors to clearly see which approach was working best. Once the differences were obvious, picking a winner was easy.

That final prompt became the foundation for the full automation step.

#### Model selection (aka way more testing than expected)

My initial assumption was "just use the biggest model possible and call it a day." That turned out to be wrong.

I tested:

- Mixtral7B
- Qwen 14B
- Qwen 32B
- LLaMA 70B
- several prompt variations against the same small test set

What I learned pretty quickly:

- Smaller models are faster, but sometimes ignore formatting rules, and try to be a little too helpful (by adding explanations I explicitly didn't want)
- I saw a **significant** quality improvement jumping from Qwen 14B to Qwen 32B.
- I did not see a meaningful jump from Qwen 32B to LLaMA 70B, but I did see a large processing time increase.

After a lot of side-by-side testing, Qwen 2.5 32B ended up being the sweet spot:

- much better rule obedience than 14B
- fast enough to run locally without waiting forever

Once I locked in the model, I froze the prompt and moved on.

#### Automating the whole thing

At this point the pipeline looked like this:

1. Read the original Duolingo CSV (word, definition).
2. Send batches of Spanish words to the LLM using the fixed system prompt.
3. Expect one NDJSON line per word back:

   ```json
   {"word":"…","definition":"…"}
   ```

4. Validate the output.
5. Apply a few small deterministic cleanup rules (things like stripping "oneself").
6. Write everything back out to a new CSV.

One important detail: I wanted to preserve provenance.

The final CSV doesn't just overwrite Duolingo's data. Instead it keeps everything side-by-side:

```csv
word,definition,model_definition,cleaned_definition
```

That way:

- I can see what Duolingo originally said.
- I can see exactly what the model produced.
- I can see the final cleaned version that will actually go into Anki.

This also made debugging much easier when the model occasionally did something weird.

The script batches requests (about 100 words at a time), retries failures, and guarantees that the original word order is preserved, even if requests complete out of order.

Once that was in place, generating improved definitions for all ~2,500 words became a single command.

#### The result

Instead of spending hours manually fixing definitions, I now have:

- a repeatable pipeline
- consistent, recall-friendly definitions
- a clean Anki import
- and a system I can rerun any time Duolingo adds more vocabulary

## Example results

Once the pipeline was in place, the improvements were immediately obvious. The goal wasn’t to make definitions more “complete”, but to make them **more useful for recall**.

Here are a few representative examples.

```csv
word,definition,model_definition,cleaned_definition
empuje,"drive, go, drove","(you formal imperative) push","push"
se ríe,laugh,"(he/she/it) laughs, is laughing","(he/she/it) laughs"
al salir,"(I) left, left","when leaving","when leaving"
```

| Spanish | Duolingo definition | Improved definition |
|--------|---------------------|--------------------|
| empuje | drive, go, drove | (you formal imperative) push |
| se ríe | laugh | (he/she/it) laughs, is laughing |
| al salir | (I) left, left | when leaving |


Compared to the original Duolingo definitions, the improved versions:

- Remove unrelated or misleading meanings.
- Collapse noisy, duplicated definitions into a single clear idea.
- Make the subject explicit when the Spanish form encodes it.
- Avoid grammar explanations while still reinforcing how Spanish actually works.

This last point is especially important. Spanish encodes subject and meaning directly into verb forms much more than English does. By reflecting that in the flashcards, you train yourself to recognize complete ideas instead of mentally reconstructing them every time you see or hear a word.

The result is flashcards that are faster to review, easier to remember, and far more useful when reading or listening in real Spanish contexts.

Most importantly, studying feels dramatically better. I’m spending my time remembering words instead of second-guessing what a card is even trying to say.

Part 3 will probably be about actually using this thing and whether it meaningfully improves retention, but for now I’m calling this a win.