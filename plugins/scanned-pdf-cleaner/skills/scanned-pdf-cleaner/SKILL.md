---
name: scanned-pdf-cleaner
description: Turn phone photos or rough scans of book pages and academic papers into a clean, flat, print-like PDF for reading. Straightens curved lines and tilted pages by the text itself, removes fingers, spine shadows, page curl, neighbouring-page slivers, smudges and margin pen notes, keeps printed text, figures, captions and page numbers, and evens out the margins. Use when someone has a photographed or badly scanned book chapter, article or paper (PDF or images) that is hard to read, skewed, curved, stained or off-centre.
license: MIT
---

# Scanned PDF cleaner

Phone photos of an open book come out curved near the spine, tilted, grey, with a thumb on the edge and a
sliver of the next page. This skill turns them into pages that read like a clean print.

The scripts do the pixel work. You do the judging: you trace each page's corners, look at what got
removed, and decide which marks outside the text are printed (keep) and which are not (remove). Each
step writes contact sheets you can read as images, so look at them. Don't assume a step worked.

## Setup (once per machine)

```bash
SKILL=<this skill's folder>      # the folder holding this SKILL.md
python3 -m venv ~/.cache/scanned-pdf-cleaner-venv
~/.cache/scanned-pdf-cleaner-venv/bin/pip install -q -r "$SKILL/requirements.txt"
PY=~/.cache/scanned-pdf-cleaner-venv/bin/python
```

Every command below runs as `cd "$SKILL/scripts" && $PY <script> ...`. Use a new, empty work folder per
document, outside the user's project (a scratch or temp folder). The user's files are only read.

## Workflow

### 1. Prepare

```bash
$PY prepare.py INPUT.pdf WORK          # or: a folder of images, or image files (HEIC: convert first)
```

Writes `WORK/src/p-NNN.jpg` (upright photos), `WORK/grid/g-NNN.jpg` (each photo with a red grid every 100
px, labelled in hundreds on all four edges), and `WORK/rough.json` with a placeholder outline per photo.

If a photo is sideways or upside down, turn it: `$PY prepare.py --turn WORK p-003.jpg 90|180|270` (clockwise).

### 2. Trace the page corners (you)

Read every grid image. For each photo, find the page that belongs to the document. Write its four
corners into `WORK/rough.json` in source pixels, ordered **top-left, top-right, bottom-right,
bottom-left of the page as it reads**. For grid label 7 across and 12 down, write `[700, 1200]`.

```json
{"001": {"src": "p-000.jpg", "quad": [[96,72],[930,92],[945,1468],[70,1480]]}}
```

- Keys are the output page order (`001`, `002`, ...). Keep that order matched to the reading order.
- Take the page's paper edge, not the text. Near the spine, take the line where the page bends away
  into the gutter. A page that runs off the photo gets corners on the photo's edge.
- A photo of a two-page spread gives two entries with the same `src`, one per page, for example `"005"`
  and `"006"`.
- Within about 30 px is enough. The next step snaps to the real edge.

### 3. Snap to the paper edge

```bash
$PY refine.py WORK
```

Writes `WORK/quads.json` and `WORK/sheets/quads-NN.jpg`: orange = your trace, red = snapped, green dot =
top-left. Read the sheets. If a red outline jumped onto a shadow, the table or the neighbouring page,
fix that trace and run the step again.

### 4. Flatten, tone and clean the edges

```bash
$PY clean.py WORK            # or: clean.py WORK 004 007  to redo some pages
```

For each page this:
- finds its text lines and the justified column edges;
- squares the text block and fits one smooth bend surface to every line, so curved lines come out straight;
- tones paper to white and ink to black;
- removes dark marks that touch the page's edge: fingers, spine curl, creases and next-page slivers.

Pages with fewer than 5 text lines, such as title pages and full-page figures, get a plain four-corner
warp instead. Output: `WORK/pages/`, `WORK/blocks.json`, and `WORK/sheets/review-NN.jpg`, where red =
removed, blue = left for your decision and green = text block.

Read the review sheets. Things to look for:
- Lines still curved, or the page skewed: the trace is off. Fix `rough.json`, then rerun refine and clean for that page.
- Text inside the green box shown in red: tell the user. The edge clean never removes text inside the
  block unless it lies on the page's edge band.

### 5. List the marks outside the text

```bash
$PY flags.py WORK
```

Writes `WORK/flags/flags-N.jpg`: numbered tiles of every dark mark outside the text block.

### 6. Decide keep or remove (you)

Read the flag sheets and write `WORK/decisions.json`:

```json
{"keep": [0, 3, 4, 7], "strokes_only": [23], "erase": [{"page": "014", "box": [1500, 300, 80, 900], "mode": "strokes"}]}
```

- **keep**: anything printed. That covers page numbers, running heads, chapter numbers, captions, side
  labels, table rules, figures and drawings. Printed type is crisp and regular. Drawings in the book
  are print too, even when they are scribbly children's drawings.
- **remove**: leave the number out. This covers handwriting, pen and pencil notes, smudges, specks,
  fingerprints, grey bars and torn-edge shadows. Pen lines are thin, uneven and often slanted, and
  don't match the font.
- **strokes_only**: printed letters with a pen stroke through or beside them. Only strokes taller than
  1.5 lines are removed.
- **erase**: a box in page pixels on `pages/page-KEY.jpg`, for marks inside the text block that you
  were asked to remove. `"mode": "all"` whitens the box; `"strokes"` removes only tall strokes.

Ask the user before removing what they may want. This covers pen underlines and notes between the lines
inside the text, and highlighter. Default: remove margin notes, keep underlines inside the text. Ask
too when you can't tell print from pen. Show the tile, don't describe it.

### 7. Finish

```bash
$PY finish.py WORK OUT.pdf           # --no-frame keeps each page's own framing; --dpi 300 by default
```

What it does:
- Whitens everything outside the text block except kept items.
- Removes tall thin pen brackets that hug the block's sides.
- Frames every page on one page size:
  - Text comes out at one size: photos taken closer or further away match. Scaling uses the text
    block's width, or the line pitch where a figure narrows the column.
  - Side margins are equal, so content that sat against one edge or was pushed off-centre by the
    book's thickness is centred.
  - Every page starts at the same top margin.

Read `WORK/sheets/final-NN.jpg` before handing over. Check every page for leftover smudges, cut text and
anything you kept by mistake. Then give the user the PDF path. Save the PDF next to the input (for
example `<name>_clean.pdf`) unless they say otherwise.

## What good looks like

- Text lines straight and level edge to edge, including the line nearest the spine.
- Paper pure white and type solid black, with thin strokes intact. Large dark drawings keep their fill.
- No fingers, shadows, neighbouring-page slivers or specks. Side margins equal, and the same text size on every page.

## Notes from real use

- The rectifier reads text, so it is at its best on pages full of justified lines. It works for any
  script, including right-to-left (Hebrew, Arabic), because it only looks at line shapes.
- Short lines inside drawings (labels) are ignored when fitting the bend, so figures don't fold the page.
- A dark drawing that fills much of a page would wash out to grey with naive toning. `tone()` holds the
  paper estimate down from the surrounding paper.
- When a page's curl swallows a few letters at the spine, the photo has nothing to recover. Say so and
  don't invent text.
- Two-column papers: the block spans both columns. Check the review sheet for lines fitted across the gutter.
