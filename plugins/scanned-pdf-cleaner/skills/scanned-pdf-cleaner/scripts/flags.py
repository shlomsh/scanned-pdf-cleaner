# Step 5. Every dark mark left outside the text block, cropped and numbered on contact sheets, for a
# keep/remove decision: printed things (page numbers, running heads, captions, side labels, figures) stay;
# pen notes, smudges, specks and fingerprints go.
# Writes flags/flags-N.jpg and flags/flags.json ([[page, x, y, w, h], ...], indexed by the number on the tile).
# usage: flags.py WORK
import sys, os, glob
import cv2
import numpy as np
from common import load, block_box

if __name__ == '__main__':
    work = sys.argv[1]
    blocks = load(work, 'blocks.json')
    out = os.path.join(work, 'flags'); os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, 'flags-*.jpg')):
        os.remove(old)
    tiles, listing = [], []
    for key in sorted(blocks):
        page = cv2.imread(os.path.join(work, 'pages', f'page-{key}.jpg'), cv2.IMREAD_GRAYSCALE)
        bx0, by0, bx1, by1 = block_box(blocks[key], page.shape)
        blk = np.zeros_like(page); blk[by0:by1, bx0:bx1] = 1
        dark = ((page < 150) & (blk == 0)).astype(np.uint8)
        grp = cv2.dilate(dark, np.ones((61, 61), np.uint8))
        m, lab, st, _ = cv2.connectedComponentsWithStats(grp, 8)
        for i in range(1, m):
            x, y, w, h, _ = st[i]
            if dark[y:y + h, x:x + w].sum() < 15:
                continue
            crop = cv2.cvtColor(page[y:y + h, x:x + w], cv2.COLOR_GRAY2BGR)
            s = 160 / max(h, w, 1) if max(h, w) > 160 else 1.0
            crop = cv2.resize(crop, (max(1, int(w * s)), max(1, int(h * s))))
            tile = np.full((200, 200, 3), 255, np.uint8); tile[30:30 + crop.shape[0], 20:20 + crop.shape[1]] = crop
            cv2.putText(tile, f'#{len(listing)} p{key}', (4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)
            cv2.rectangle(tile, (0, 0), (199, 199), (180, 180, 180), 1)
            tiles.append(tile); listing.append([key, int(x), int(y), int(w), int(h)])
    blank = np.full((200, 200, 3), 255, np.uint8)
    rows = [np.hstack(tiles[i:i + 8] + [blank] * (8 - len(tiles[i:i + 8]))) for i in range(0, len(tiles), 8)]
    for j in range(0, len(rows), 5):
        p = os.path.join(out, f'flags-{j // 5}.jpg'); cv2.imwrite(p, np.vstack(rows[j:j + 5])); print(p)
    import json
    json.dump(listing, open(os.path.join(out, 'flags.json'), 'w'))
    print(len(listing), 'marks outside the text block')
