# Step 3. Snap each traced page edge to the paper's real edge (the strongest bright-inside/dark-outside step
# within RADIUS px), fit a straight line per side, intersect. Writes quads.json and check images.
# usage: refine.py WORK [RADIUS]
import sys, os
import cv2
import numpy as np
from common import load, save, contact_sheets


def line_fit(pts):
    pts = np.array(pts, np.float32)
    best = None
    for _ in range(3):
        vx, vy, x0, y0 = cv2.fitLine(pts, cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
        n = np.array([-vy, vx]); d = (pts - [x0, y0]) @ n
        keep = np.abs(d) < max(4, 2.5 * np.median(np.abs(d)))
        if keep.sum() < 5:
            break
        pts = pts[keep]; best = (vx, vy, x0, y0)
    return best


def intersect(l1, l2):
    (vx1, vy1, x1, y1), (vx2, vy2, x2, y2) = l1, l2
    t = np.linalg.solve(np.array([[vx1, -vx2], [vy1, -vy2]]), np.array([x2 - x1, y2 - y1]))[0]
    return [float(x1 + vx1 * t), float(y1 + vy1 * t)]


def snap(img, q, R):
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 2.0)
    h, w = g.shape
    q = np.array(q, float); c = q.mean(0)
    lines = []
    for i in range(4):
        a, b = q[i], q[(i + 1) % 4]; t = (b - a) / np.linalg.norm(b - a); nrm = np.array([t[1], -t[0]])
        if (c - a) @ nrm > 0:
            nrm = -nrm  # outward
        pts = []
        for s in np.linspace(0.12, 0.88, 50):
            p = a + (b - a) * s
            offs = np.arange(-R, R + 1)
            xy = p[None] + offs[:, None] * nrm[None]
            ok = (xy[:, 0] >= 1) & (xy[:, 0] < w - 2) & (xy[:, 1] >= 1) & (xy[:, 1] < h - 2)
            if ok.sum() < R:
                continue
            v = cv2.remap(g, xy[:, 0:1].astype(np.float32), xy[:, 1:2].astype(np.float32), cv2.INTER_LINEAR).ravel()
            v[~ok] = np.nan
            step = np.full_like(v, -1e9)
            for k in range(4, len(v) - 4):  # inside (lower offset) minus outside (higher offset)
                if np.isnan(v[k - 4:k + 5]).any():
                    continue
                step[k] = v[k - 4:k].mean() - v[k + 1:k + 5].mean()
            k = int(np.argmax(step))
            if step[k] > 6:
                pts.append(p + offs[k] * nrm)
        lines.append(line_fit(pts) if len(pts) >= 8 else None)
        if lines[-1] is None:  # the page runs out of the photo here: keep the traced edge
            lines[-1] = (t[0], t[1], a[0], a[1])
    out = [intersect(lines[(i - 1) % 4], lines[i]) for i in range(4)]
    # A snapped corner far from the traced one means the edge locked onto something else: keep the trace.
    out = [o if np.hypot(o[0] - p[0], o[1] - p[1]) < 2 * R else list(map(float, p)) for o, p in zip(out, q)]
    return [[min(max(x, 0), w - 1), min(max(y, 0), h - 1)] for x, y in out]


if __name__ == '__main__':
    work = sys.argv[1]
    rough = load(work, 'rough.json')
    quads = {}
    os.makedirs(os.path.join(work, 'check'), exist_ok=True)
    shots = []
    for key in sorted(rough):
        e = rough[key]
        img = cv2.imread(os.path.join(work, 'src', e['src']))
        R = int(sys.argv[2]) if len(sys.argv) > 2 else max(30, int(0.04 * max(img.shape[:2])))
        quads[key] = {'src': e['src'], 'quad': snap(img, e['quad'], R)}
        vis = img.copy()
        cv2.polylines(vis, [np.int32(e['quad'])], True, (0, 200, 255), 3)
        cv2.polylines(vis, [np.int32(quads[key]['quad'])], True, (0, 0, 255), 3)
        cv2.circle(vis, tuple(np.int32(quads[key]['quad'][0])), 18, (0, 160, 0), -1)  # top-left as read
        p = os.path.join(work, 'check', f'q-{key}.jpg')
        cv2.imwrite(p, vis, [cv2.IMWRITE_JPEG_QUALITY, 80]); shots.append(p)
    save(work, 'quads.json', quads)
    for s in contact_sheets(shots, os.path.join(work, 'sheets'), per=6, height=520, prefix='quads'):
        print(s)
