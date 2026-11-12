# Step 4. Flatten each page by its text, tone it to paper-white and ink-black, and remove what belongs to the
# page's edge: fingers, the curl into the spine, crease shadows, a sliver of the next page.
# Writes pages/page-KEY.jpg, review/rev-KEY.jpg (red = removed, blue = left for review, green = text block)
# and blocks.json (each page's text block and line pitch, in output pixels).
# usage: clean.py WORK [KEY ...]
import sys, os
import cv2
import numpy as np
from common import load, save, block_box, write_jpg, contact_sheets
import rectify as R


def clean(page, inside, block):
    h, w = page.shape
    dark = (page < 150).astype(np.uint8)
    edge = (inside == 0).astype(np.uint8)  # where the page outline or the photo ends
    edge[:3, :] = edge[-3:, :] = 1; edge[:, :3] = edge[:, -3:] = 1
    band = cv2.dilate(edge, np.ones((int(0.02 * w) | 1,) * 2, np.uint8))
    p = block['pitch']
    bx0, by0, bx1, by1 = block_box(block, page.shape)
    blk = np.zeros_like(dark); blk[by0:by1, bx0:bx1] = 1
    joined = cv2.dilate(dark, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(joined, 8)
    removed = np.zeros_like(dark); flagged = np.zeros_like(dark)
    glyph = 1.2 * p
    for i in range(1, n):
        x, y, cw, ch, area = st[i]
        comp = lab[y:y + ch, x:x + cw] == i
        inblk = blk[y:y + ch, x:x + cw][comp].mean()
        touches = band[y:y + ch, x:x + cw][comp].any()
        if inblk > 0.98 and not (touches and (cw > 4 * p or ch > 4 * p)):
            continue  # text, underlines, figures inside the block
        if touches:
            if cw < glyph and ch < glyph and inblk > 0.5:
                continue  # a cut-off letter on a text row at the photo's edge
            # Inside the text block only the edge band itself goes: a curl that runs into a line keeps the line.
            keep_txt = (blk[y:y + ch, x:x + cw] > 0) & (band[y:y + ch, x:x + cw] == 0)
            removed[y:y + ch, x:x + cw] |= (comp & ~keep_txt).astype(np.uint8)
        else:
            flagged[y:y + ch, x:x + cw] |= comp.astype(np.uint8)
    out = page.copy()
    rim = (cv2.dilate(removed, np.ones((9, 9), np.uint8)) > 0) & ~((blk > 0) & (band == 0))
    out[rim] = 255
    near_kept = cv2.dilate(flagged, np.ones((51, 51), np.uint8)) > 0
    out[(blk == 0) & (out > 150) & ~near_kept] = 255  # curl shadows and grey rims
    vis = cv2.cvtColor(page, cv2.COLOR_GRAY2BGR)
    vis[removed > 0] = (0, 0, 255); vis[flagged > 0] = (255, 120, 0)
    cv2.rectangle(vis, (bx0, by0), (bx1, by1), (0, 170, 0), 4)
    return out, vis


if __name__ == '__main__':
    work = sys.argv[1]
    quads = load(work, 'quads.json')
    blocks = load(work, 'blocks.json', {})
    keys = sys.argv[2:] or sorted(quads)
    for key in keys:
        e = quads[key]
        img = cv2.imread(os.path.join(work, 'src', e['src']))
        g, inside, info = R.rectify(img, e['quad'])
        out, vis = clean(R.tone(g, inside), inside, info['block'])
        write_jpg(os.path.join(work, 'pages', f'page-{key}.jpg'), out)
        write_jpg(os.path.join(work, 'review', f'rev-{key}.jpg'), cv2.resize(vis, None, fx=0.35, fy=0.35, interpolation=cv2.INTER_AREA), 85)
        blocks[key] = {**{k: float(v) for k, v in info['block'].items()}, 'lines': info['lines']}
        print(key, f"{info['lines']} lines" if not info['flat'] else f"flat warp ({info['flat']})")
    save(work, 'blocks.json', blocks)
    revs = [os.path.join(work, 'review', f'rev-{k}.jpg') for k in sorted(blocks)]
    for s in contact_sheets(revs, os.path.join(work, 'sheets'), per=6, height=520, prefix='review'):
        print(s)
