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
