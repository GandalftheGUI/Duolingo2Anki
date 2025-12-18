## Duolingo2Anki Part 1: Get the data

### Objective

Get vocabulary words from Duolingo into Anki for easier and more effective vocabulary studying.

### Context

I have been spending a lot of time learning Spanish, and Duolingo has been super helpful in that regard. What hasn’t been great is retaining all the vocabulary Duolingo is blasting me with, and their vocabulary review practice is pretty lacking, to put it mildly. I have used Anki for spaced repetition practice (flashcards), and I think that is a better tool for vocabulary practice.

### Plan of action

1. Download all words learned somehow (~2,500).
2. Format those words into a CSV, formatted like: `[spanish_word, english_definition]`.
3. Learn some Spanish vocabulary.

### Execution

#### Downloading all the words

Duolingo has a practice section that shows all the words you’ve learned along with their definitions. Unfortunately, Duolingo doesn’t have an export option, and they only load ~50 words at a time; then you have to click **Load more** and another 50 load. As a software engineer, I was thinking about writing some kind of automation to keep loading things, but I realized I was overthinking this.

I found the easiest way to download all words was to just keep clicking **Load more** until everything was loaded. It only took about a minute.

Right-click, save the page, and we’ve got it. 😎

#### Turn the HTML into a CSV

My first attempt was to just ask ChatGPT to do this, but it complained about the 13 MB of text it was asked to process. Instead, I simply asked it for a Python script to do it for me.


I just needed to provide a little bit of HTML to ChatGPT to show it how the data was formatted, but this turned out to be a little more difficult than I originally envisioned. VS Code and Cursor both crashed when trying to open the file, so the simplest thing to do was just drop in a screenshot of the HTML from the inspector (🤪).

<img width="635" height="599" alt="image" src="https://github.com/user-attachments/assets/1bc99b84-feaf-4a3c-ade9-69281ea67856" />

After providing a little of the HTML to ChatGPT to show it how the data was structured, here is what it gave me:

```python
from bs4 import BeautifulSoup
import csv

INPUT_HTML = "input.html"
OUTPUT_CSV = "words.csv"


def main():
    # Read and parse the HTML
    with open(INPUT_HTML, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml")  # or "html.parser"

    rows = []

    # Each word/definition pair seems to live in an <li class="_2g-qq"> ... </li>
    for li in soup.select("li._2g-qq"):
        h3 = li.find("h3")
        if not h3:
            continue

        p = h3.find_next("p")
        if not p:
            continue

        word = h3.get_text(strip=True)
        definition = " ".join(p.stripped_strings)

        rows.append((word, definition))

    # Write the CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["word", "definition"])
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
```

Looks good, and one run later:

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

Looks good 😎

...or so I thought. It turns out a lot of the definitions Duolingo provides here are pretty trash for vocabulary. A lot of them are ambiguous or just plain wrong.

I started studying, but the more I worked, the more I realized that manually fixing 2,500+ definitions is not the move. I was already using ChatGPT to help double-check some of the definitions that looked off, so why not just do this for the whole thing?

## Duolingo2Anki Part 2: AI-enhance those definitions

_Coming soon…_

