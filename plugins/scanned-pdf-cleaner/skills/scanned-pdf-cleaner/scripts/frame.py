# Put every page on one page size with book-like margins.
#  - Text is brought to one size: photos taken closer or further away come out the same scale
#    (by the text block's width on full-width pages, by line pitch where a figure narrows the column).
#  - Side margins are equal: content cramped against one edge, or pushed off-centre by the next page's
#    sliver or the book's thickness, is re-centred.
#  - Content starts at one top margin; a page whose content is too tall eats into the bottom margin first,
#    then shrinks to fit.
# usage: frame.py PAGES_DIR BLOCKS_JSON OUT_DIR [side top bottom]   (margins as shares of the page, default .12 .075 .09)
import sys, os, glob, json
import cv2
import numpy as np


def content_box(g):
    """The printed content's bounding box, ignoring specks."""
    d = (g < 160).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(d, np.ones((5, 5), np.uint8)), 8)
    ok = [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 60]
    if not ok:
        return 0, 0, g.shape[1], g.shape[0]
    x0 = min(st[i, 0] for i in ok); y0 = min(st[i, 1] for i in ok)
    x1 = max(st[i, 0] + st[i, 2] for i in ok); y1 = max(st[i, 1] + st[i, 3] for i in ok)
    return x0, y0, x1, y1


def scales(blocks):
    """Per page, the factor that brings its text to the document's common size."""
    width = {k: b['x1'] - b['x0'] for k, b in blocks.items() if b.get('lines', 0) >= 5}
    if not width:
        return {k: 1.0 for k in blocks}, None
    med_w = float(np.median(list(width.values())))
    full = {k: w for k, w in width.items() if w > 0.85 * med_w}
    target_w = float(np.median(list(full.values())))
    target_p = float(np.median([blocks[k]['pitch'] for k in full]))
    out = {}
    for k, b in blocks.items():
        if k in full:
            out[k] = target_w / full[k]
        elif k in width:  # a narrow column beside a figure
            out[k] = target_p / b['pitch']
        else:  # no text to measure
            out[k] = 1.0
    return out, target_w


def frame(pages_dir, blocks, out_dir, side=0.12, top=0.075, bottom=0.09):
    os.makedirs(out_dir, exist_ok=True)
    s, text_w = scales(blocks)
    pages = {}
    for f in sorted(glob.glob(os.path.join(pages_dir, 'page-*.jpg'))):
        k = os.path.splitext(os.path.basename(f))[0][5:]
        g = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
        f_ = s.get(k, 1.0)
        g = cv2.resize(g, None, fx=f_, fy=f_, interpolation=cv2.INTER_AREA if f_ < 1 else cv2.INTER_CUBIC)
        x0, y0, x1, y1 = content_box(g)
        pages[k] = g[y0:y1, x0:x1]
    if text_w is None:  # no page had text to measure: size the page by its content
        text_w = float(np.median([c.shape[1] for c in pages.values()]))
    W = int(round(text_w / (1 - 2 * side)))
    heights = sorted(c.shape[0] for c in pages.values())
    H = int(round(heights[int(0.85 * (len(heights) - 1))] / (1 - top - bottom)))
    for k, c in pages.items():
        min_side, min_bottom = int(0.05 * W), int(0.04 * H)
        room_w, room_h = W - 2 * min_side, H - int(top * H) - min_bottom
        f_ = min(1.0, room_w / c.shape[1], room_h / c.shape[0])
        if f_ < 1:
            c = cv2.resize(c, None, fx=f_, fy=f_, interpolation=cv2.INTER_AREA)
        canvas = np.full((H, W), 255, np.uint8)
        x = (W - c.shape[1]) // 2
        y = int(top * H)
        canvas[y:y + c.shape[0], x:x + c.shape[1]] = c
        cv2.imwrite(os.path.join(out_dir, f'page-{k}.jpg'), canvas, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(k, 'scale %.3f' % s.get(k, 1.0), 'fit %.3f' % f_)
    return W, H


if __name__ == '__main__':
    pages_dir, blocks, out_dir = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]
    m = [float(a) for a in sys.argv[4:7]] or [0.12, 0.075, 0.09]
    W, H = frame(pages_dir, blocks, out_dir, *m)
    print('page', W, 'x', H)
