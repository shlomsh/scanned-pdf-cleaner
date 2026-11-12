# Shared paths and small helpers. A work folder holds everything one document needs:
#   src/p-NNN.jpg     the photos, upright        grid/       photos with a coordinate grid, for tracing corners
#   rough.json        traced page corners         quads.json  corners snapped to the paper's edge
#   pages/            flattened, toned, edge-cleaned pages   review/  what the edge clean removed (red) and left (blue)
#   flags/            marks outside the text block, for a keep/remove decision   decisions.json  that decision
#   final/            the finished pages          sheets/     contact sheets for looking at many pages at once
import json, os, glob
import cv2
import numpy as np


def load(work, name, default=None):
    p = os.path.join(work, name)
    if not os.path.exists(p):
        if default is not None:
            return default
        raise SystemExit(f'missing {p}')
    with open(p) as f:
        return json.load(f)


def save(work, name, data):
    with open(os.path.join(work, name), 'w') as f:
        json.dump(data, f, indent=1)


def gray(path):
    return cv2.imread(path, cv2.IMREAD_GRAYSCALE)


def write_jpg(path, img, q=92):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cv2.imwrite(path, img, [cv2.IMWRITE_JPEG_QUALITY, q])


def block_box(b, shape):
    """The text block with room for a running head above and a page number below."""
    p = b['pitch']
    h, w = shape[:2]
    return (max(int(b['x0'] - 0.5 * p), 0), max(int(b['y0'] - 1.2 * p), 0),
            min(int(b['x1'] + 0.5 * p), w), min(int(b['y1'] + 1.0 * p), h))


def contact_sheets(paths, out_dir, per=6, height=420, prefix='sheet'):
    """Pages side by side at their own aspect, labelled by file name. Returns the sheet paths."""
    os.makedirs(out_dir, exist_ok=True)
    for old in glob.glob(os.path.join(out_dir, f'{prefix}-*.jpg')):
        os.remove(old)
    tiles = []
    for f in paths:
        im = cv2.imread(f)
        im = cv2.resize(im, (int(im.shape[1] * height / im.shape[0]), height), interpolation=cv2.INTER_AREA)
        label = os.path.splitext(os.path.basename(f))[0].split('-')[-1]
        cv2.putText(im, label, (6, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        tiles.append(cv2.copyMakeBorder(im, 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=(80, 80, 80)))
    out = []
    for i in range(0, len(tiles), per):
        p = os.path.join(out_dir, f'{prefix}-{i // per:02d}.jpg')
        cv2.imwrite(p, np.hstack(tiles[i:i + per]), [cv2.IMWRITE_JPEG_QUALITY, 85])
        out.append(p)
    return out
