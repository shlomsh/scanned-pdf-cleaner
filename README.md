# scanned-pdf-cleaner

A Claude skill that turns phone photos or rough scans of book pages and academic papers into a clean,
flat PDF that reads like a print.

- **Straight lines.** Pages are flattened by their own text: the lines and the justified column edges.
  Curl near the spine and tilted shots both come out square.
- **Clean paper.** Fingers, spine shadows, creases and slivers of the next page are removed. So are
  smudges, specks and pen notes in the margins.
- **Print kept.** Text, figures, captions, page numbers and running heads stay.
- **Even pages.** The same text size on every page, equal side margins, and one page size.

It works with any script, right-to-left included, and runs entirely on your machine with OpenCV and NumPy.

## How it works

The scripts do the image processing. Claude does the looking. It traces each page's corners on a grid,
checks the result on contact sheets, and decides which marks outside the text are print and which are
not. It asks you when that's unclear: underlines in the text, notes between lines, highlighter.

Steps: prepare, trace corners, snap to the paper edge, flatten and clean, list stray marks, decide
keep or remove, frame and write the PDF. [SKILL.md](plugins/scanned-pdf-cleaner/skills/scanned-pdf-cleaner/SKILL.md) has the details.

## Install

In Claude Code:

```
/plugin marketplace add shlomsh/scanned-pdf-cleaner
/plugin install scanned-pdf-cleaner@scanned-pdf-cleaner
```

Or copy `plugins/scanned-pdf-cleaner/skills/scanned-pdf-cleaner` into `~/.claude/skills/`.

It needs Python 3.10+. The skill sets up its own virtual environment from `requirements.txt` (opencv-python-headless,
numpy, img2pdf, pypdfium2) the first time it runs.

## Use

Ask Claude something like:

> Clean up this scanned chapter so it's easy to read: ~/Downloads/chapter3.pdf

You get `chapter3_clean.pdf` next to the original.

## License

MIT
