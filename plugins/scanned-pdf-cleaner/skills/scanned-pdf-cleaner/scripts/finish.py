# Step 7. Apply the keep/remove decision, even out the margins, and write the PDF.
#  - Outside the text block only the kept printed items survive; everything else becomes paper.
#  - decisions.json: {"keep": [flag numbers that are print],
#                     "strokes_only": [flag numbers where only long pen strokes go, e.g. a bracket beside letters],
#                     "erase": [{"page": "014", "box": [x, y, w, h], "mode": "all" | "strokes"}]}   (page pixels)
#  - Tall thin pen strokes hugging the text block's sides (margin brackets) go too.
# usage: finish.py WORK OUT.pdf [--no-frame] [--dpi 300]
import sys, os, glob
import cv2
import numpy as np
import img2pdf
from common import load, block_box, write_jpg, contact_sheets
from frame import frame


def strokes(roi, min_h):
    """White out components taller than min_h (pen strokes), leaving letters."""
    dark = (roi < 150).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(dark, np.ones((3, 3), np.uint8)), 8)
    for j in range(1, n):
        if st[j, cv2.CC_STAT_HEIGHT] > min_h:
            roi[cv2.dilate((lab == j).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0] = 255


if __name__ == '__main__':
    work, pdf = sys.argv[1], sys.argv[2]
    do_frame = '--no-frame' not in sys.argv
    dpi = int(sys.argv[sys.argv.index('--dpi') + 1]) if '--dpi' in sys.argv else 300
    blocks = load(work, 'blocks.json')
    flags = load(work, os.path.join('flags', 'flags.json'), [])
    dec = load(work, 'decisions.json', {})
    keep, strokes_only = set(dec.get('keep', [])), set(dec.get('strokes_only', []))
    clean_dir = os.path.join(work, 'cleaned')
    for key in sorted(blocks):
        g = cv2.imread(os.path.join(work, 'pages', f'page-{key}.jpg'), cv2.IMREAD_GRAYSCALE)
        b = blocks[key]; p = b['pitch']
        bx0, by0, bx1, by1 = block_box(b, g.shape)
        allowed = np.zeros_like(g); allowed[by0:by1, bx0:bx1] = 1
        for i, (k, x, y, w, h) in enumerate(flags):
            if k == key and (i in keep or i in strokes_only):
                allowed[y:y + h, x:x + w] = 1
        g[allowed == 0] = 255
        for i, (k, x, y, w, h) in enumerate(flags):
            if k == key and i in strokes_only:
                strokes(g[y:y + h, x:x + w], 1.5 * p)
        for e in dec.get('erase', []):
            if e['page'] == key:
                x, y, w, h = e['box']
                if e.get('mode', 'all') == 'strokes':
                    strokes(g[y:y + h, x:x + w], 1.5 * p)
                else:
                    g[y:y + h, x:x + w] = 255
        # Margin brackets: tall, thin, within a line pitch of the block's left or right edge.
        n, lab, st, _ = cv2.connectedComponentsWithStats((g < 150).astype(np.uint8), 8)
        for j in range(1, n):
            x, y, w, h, _ = st[j]
            side = min(abs(x - b['x0']), abs(x + w - b['x1']), abs(x - b['x1']), abs(x + w - b['x0'])) < p
            if side and h > 2.5 * p and w < 0.5 * p:
                g[cv2.dilate((lab == j).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0] = 255
        write_jpg(os.path.join(clean_dir, f'page-{key}.jpg'), g)
    final = os.path.join(work, 'final')
    for old in glob.glob(os.path.join(final, 'page-*.jpg')):
        os.remove(old)
    if do_frame:
        W, H = frame(clean_dir, blocks, final)
        print('page size', W, 'x', H, 'px')
    else:
        os.makedirs(final, exist_ok=True)
        for f in glob.glob(os.path.join(clean_dir, 'page-*.jpg')):
            os.replace(f, os.path.join(final, os.path.basename(f)))
    pages = sorted(glob.glob(os.path.join(final, 'page-*.jpg')))
    with open(pdf, 'wb') as f:
        f.write(img2pdf.convert(pages, layout_fun=img2pdf.get_fixed_dpi_layout_fun((dpi, dpi))))
    print(pdf, len(pages), 'pages')
    for s in contact_sheets(pages, os.path.join(work, 'sheets'), per=6, height=420, prefix='final'):
        print(s)
