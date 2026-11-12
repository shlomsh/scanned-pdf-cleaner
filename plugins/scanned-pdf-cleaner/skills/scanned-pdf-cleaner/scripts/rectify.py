# Flatten a photographed page by its own text: lines come out straight, the justified column edges vertical.
# Library module; clean.py drives it.
import cv2
import numpy as np

SCALE = 2          # output pixels per working pixel
PAGE_W = 860       # every page is brought to this width (working pixels) before reading its text
rng = np.random.default_rng(0)


def ink_of(gray, poly):
    """Dark marks inside the page outline, as glyph-sized components."""
    bg = cv2.medianBlur(cv2.dilate(gray, np.ones((7, 7), np.uint8)), 31)
    ink = ((gray.astype(np.float32) / np.maximum(bg, 1)) < 0.72).astype(np.uint8)
    m = np.zeros_like(ink)
    cv2.fillPoly(m, [poly.astype(np.int32)], 1)
    m = cv2.erode(m, np.ones((21, 21), np.uint8))
    ink *= m
    n, lab, st, _ = cv2.connectedComponentsWithStats(ink, 8)
    keep = np.zeros(n, bool)
    keep[1:] = (st[1:, cv2.CC_STAT_HEIGHT] < 34) & (st[1:, cv2.CC_STAT_AREA] >= 3)
    return keep[lab].astype(np.uint8), m


def text_lines(ink, page_w):
    """Each text line as a cubic (or lower) polynomial y(x) over its x range."""
    closed = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((1, 19), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(closed, 8)
    lines = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if w < 0.10 * page_w or h < 6 or h > 0.25 * page_w:
            continue
        sub = (lab[y:y + h, x:x + w] == i) & (ink[y:y + h, x:x + w] > 0)
        xs, ys, th = [], [], []
        for c in range(0, w, 3):
            col = np.nonzero(sub[:, c])[0]
            if len(col):
                xs.append(x + c)
                ys.append(y + np.median(col))
                th.append(col.max() - col.min())
        if len(xs) < 8 or np.median(th) > 26 or np.median(th) < 5:  # two lines run together, or a drawing
            continue
        xs, ys = np.array(xs, float), np.array(ys, float)
        deg = 3 if w > 0.5 * page_w else (2 if w > 0.3 * page_w else 1)
        p = np.polyfit(xs, ys, deg)
        ok = np.abs(np.polyval(p, xs) - ys) < 6
        if ok.sum() >= 6:
            p = np.polyfit(xs[ok], ys[ok], deg)
        if ok.mean() < 0.6:  # not one line of text (a drawing, a shadow)
            continue
        p = np.concatenate([np.zeros(4 - len(p)), p])
        lines.append({'p': p, 'x0': float(x), 'x1': float(x + w), 'xs': xs, 'ys': ys})
    if not lines:
        return []
    lines.sort(key=lambda L: np.polyval(L['p'], (L['x0'] + L['x1']) / 2))
    # A stroke of a drawing can pass for a line; text lines run alongside their neighbours.
    mid = np.array([np.polyval(L['p'], (L['x0'] + L['x1']) / 2) for L in lines])
    keep = []
    for i, L in enumerate(lines):
        xc = (L['x0'] + L['x1']) / 2
        own = np.polyval(np.polyder(L['p']), xc)
        near = [np.polyval(np.polyder(lines[j]['p']), xc) for j in range(len(lines))
                if j != i and abs(mid[j] - mid[i]) < 160 and lines[j]['x0'] <= xc <= lines[j]['x1']]
        keep.append(len(near) < 2 or abs(own - np.median(near)) < 0.06)
    lines = [L for L, k in zip(lines, keep) if k]
    return tidy(lines, page_w) if lines else []


def fit(xs, ys):
    deg = 3 if np.ptp(xs) > 300 else (2 if np.ptp(xs) > 180 else 1)
    p = np.polyfit(xs, ys, deg)
    return np.concatenate([np.zeros(4 - len(p)), p])


def tidy(lines, page_w):
    """Join the pieces of one curved line, drop duplicates, drop short labels inside drawings."""
    at = lambda L, x: float(np.polyval(L['p'], x))
    full = [L for L in lines if L['x1'] - L['x0'] > 0.5 * page_w]
    mids = sorted(at(L, (L['x0'] + L['x1']) / 2) for L in full)
    pitch = float(np.median(np.diff(mids))) if len(mids) > 3 else 30.0
    merged = True
    while merged:
        merged = False
        for a in range(len(lines)):
            for b in range(len(lines)):
                A, B = lines[a], lines[b]
                if a == b or A['x1'] > B['x0'] + 15 or B['x0'] - A['x1'] > 80:
                    continue
                gap = (A['x1'] + B['x0']) / 2
                if abs(at(A, gap) - at(B, gap)) < 0.3 * pitch:
                    xs, ys = np.concatenate([A['xs'], B['xs']]), np.concatenate([A['ys'], B['ys']])
                    lines[a] = {'p': fit(xs, ys), 'x0': A['x0'], 'x1': max(A['x1'], B['x1']), 'xs': xs, 'ys': ys}
                    del lines[b]
                    merged = True
                    break
            if merged:
                break
    drop = set()
    for a in range(len(lines)):
        for b in range(len(lines)):
            A, B = lines[a], lines[b]
            lo, hi = max(A['x0'], B['x0']), min(A['x1'], B['x1'])
            if a < b and hi - lo > 20 and abs(at(A, (lo + hi) / 2) - at(B, (lo + hi) / 2)) < 0.6 * pitch:
                drop.add(a if A['x1'] - A['x0'] < B['x1'] - B['x0'] else b)
    lines = [L for i, L in enumerate(lines) if i not in drop]
    top = min(at(L, (L['x0'] + L['x1']) / 2) for L in lines)
    out = []
    for L in lines:
        m = at(L, (L['x0'] + L['x1']) / 2)
        short = L['x1'] - L['x0'] < 0.2 * page_w
        near = any(K is not L and abs(at(K, (K['x0'] + K['x1']) / 2) - m) < 2.0 * pitch and K['x1'] - K['x0'] > 0.3 * page_w for K in lines)
        if short and not near and m - top > 1.5 * pitch:
            continue
        out.append(L)
    out.sort(key=lambda L: at(L, (L['x0'] + L['x1']) / 2))
    return out


def ransac_edges(pts, n_lines, outer):
    """The outermost well-supported straight edge x = a + b*y through line ends (a justified column edge)."""
    pts = np.array(pts, float)
    left = pts.copy()
    cands = []
    for _ in range(4):
        if len(left) < 4:
            break
        best = None
        for _ in range(400):
            i, j = rng.choice(len(left), 2, replace=False)
            (x1, y1), (x2, y2) = left[i], left[j]
            if abs(y2 - y1) < 40:
                continue
            b = (x2 - x1) / (y2 - y1)
            if abs(b) > 0.35:
                continue
            a = x1 - b * y1
            inl = np.abs(left[:, 0] - (a + b * left[:, 1])) < 5
            if best is None or inl.sum() > best.sum():
                best = inl
        if best is None or best.sum() < 4:
            break
        b, a = np.polyfit(left[best, 1], left[best, 0], 1)
        cands.append((a, b, int(best.sum()), float(left[best, 0].mean())))
        left = left[~best]
    need = max(4, int(0.2 * n_lines))
    good = [c for c in cands if c[2] >= need]
    if not good:
        return None
    return max(good, key=lambda c: outer * c[3])[:2]


def edge_from_quad(q, side):
    a, b = (q[0], q[3]) if side == 'L' else (q[1], q[2])
    bb = (b[0] - a[0]) / (b[1] - a[1])
    return a[0] - bb * a[1], bb


def cross(p, edge):
    a, b = edge
    x = a
    for _ in range(6):
        x = a + b * np.polyval(p, x)
    return np.array([x, np.polyval(p, x)])


def _flat(gray, q, why):
    """No text to read (a title page, a full-page figure): a plain four-corner warp of the page outline."""
    Wt = (np.linalg.norm(q[1] - q[0]) + np.linalg.norm(q[2] - q[3])) / 2
    Ht = (np.linalg.norm(q[3] - q[0]) + np.linalg.norm(q[2] - q[1])) / 2
    ow, oh = int(Wt * SCALE), int(Ht * SCALE)
    H = cv2.getPerspectiveTransform(q.astype(np.float32), np.float32([[0, 0], [ow, 0], [ow, oh], [0, oh]]))
    out = cv2.warpPerspective(gray, H, (ow, oh), flags=cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    inside = np.full((oh, ow), 255, np.uint8)
    m = 0.06
    block = {'x0': m * ow, 'x1': (1 - m) * ow, 'y0': m * oh, 'y1': (1 - m) * oh, 'pitch': 0.02 * oh}
    return out, inside, {'lines': 0, 'flat': why, 'block': block}


def rectify(img, quad):
    """Returns (flattened gray page, mask of what came from inside the page outline, info with the text block)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    q = np.array(quad, float)
    s = PAGE_W / np.linalg.norm(q[1] - q[0])
    gray = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC if s > 1 else cv2.INTER_AREA)
    q = q * s
    page_w = np.linalg.norm(q[1] - q[0])
    ink, pagemask = ink_of(gray, q)
    lines = text_lines(ink, page_w)
    if len(lines) < 5:
        return _flat(gray, q, f'{len(lines)} text lines')
    ends_L = [(L['x0'], np.polyval(L['p'], L['x0'])) for L in lines]
    ends_R = [(L['x1'], np.polyval(L['p'], L['x1'])) for L in lines]
    eL = ransac_edges(ends_L, len(lines), -1) or edge_from_quad(q, 'L')
    eR = ransac_edges(ends_R, len(lines), +1) or edge_from_quad(q, 'R')

    def chord(L):  # the straight line through a text line's ends
        xa, xb = L['x0'], L['x1']
        ya, yb = np.polyval(L['p'], xa), np.polyval(L['p'], xb)
        return np.array([0.0, (yb - ya) / (xb - xa), ya - (yb - ya) / (xb - xa) * xa])
    span = lambda L: (L['x1'] - L['x0']) / max(1, cross(chord(L), eR)[0] - cross(chord(L), eL)[0])
    full = [L for L in lines if span(L) > 0.4]
    if len(full) < 2:
        full = lines
    top, bot = chord(full[0]), chord(full[-1])
    src = np.float32([cross(top, eL), cross(top, eR), cross(bot, eR), cross(bot, eL)])
    Wt = (np.linalg.norm(src[1] - src[0]) + np.linalg.norm(src[2] - src[3])) / 2
    Ht = (np.linalg.norm(src[3] - src[0]) + np.linalg.norm(src[2] - src[1])) / 2
    if Wt < 0.3 * page_w or Ht < 0.2 * page_w:
        return _flat(gray, q, 'text block too small')
    H = cv2.getPerspectiveTransform(src, np.float32([[0, 0], [Wt, 0], [Wt, Ht], [0, Ht]]))

    # In the homography's frame the text block is square; what is left is the page's bend. Each line sits at
    # its own height Y_i, and the bend d(u, v) is one smooth low-order surface fitted to every line at once.
    Hi = np.linalg.inv(H)
    us, vs, ids = [], [], []
    for i, L in enumerate(lines):
        xs = np.arange(L['x0'], L['x1'], 6.0)
        uv = cv2.perspectiveTransform(np.stack([xs, np.polyval(L['p'], xs)], 1)[None].astype(np.float32), H)[0]
        us.append(uv[:, 0] / Wt); vs.append(uv[:, 1] / Ht); ids.append(np.full(len(xs), i))
    u, v, ids = np.concatenate(us), np.concatenate(vs), np.concatenate(ids)
    A_DEG, B_DEG = 4, 3

    def surface(u, v):
        return np.stack([u ** a * v ** b for a in range(1, A_DEG + 1) for b in range(B_DEG + 1)], 1)
    n = len(lines)
    onehot = np.zeros((len(u), n)); onehot[np.arange(len(u)), ids] = 1
    M = np.hstack([onehot, surface(u, v)])
    w = np.ones(len(u))
    k = 2.0 / Ht
    for _ in range(8):  # IRLS: a line that does not follow the page (a merge of two, a drawing) loses its say
        sol, *_ = np.linalg.lstsq(M * w[:, None], v * w, rcond=None)
        r = v - M @ sol
        w = 1 / np.maximum(1, np.abs(r) / k)
        rms = np.array([np.sqrt(np.mean(r[ids == i] ** 2)) for i in range(n)])
        w[rms[ids] > 4.0 / Ht] = 0.0
    coef = sol[n:]
    # Past the text the surface is held at its edge value: a polynomial run out into the margins swings wildly.
    ulo, uhi = u.min() - 0.03, u.max() + 0.03
    vlo, vhi = v.min() - 0.03, v.max() + 0.03
    bend = lambda uu, vv: surface(np.clip(uu, ulo, uhi), np.clip(vv, vlo, vhi)) @ coef

    def to_source(P):
        uu, vv = P[:, 0] / Wt, P[:, 1] / Ht
        val = vv.copy()
        for _ in range(8):
            val = vv + bend(uu, val)
        pts = np.stack([uu * Wt, val * Ht], 1)[None].astype(np.float32)
        return cv2.perspectiveTransform(pts, Hi)[0].astype(np.float64)
    good = rms <= 4.0 / Ht

    # The output is the part of a wide target area whose source lands on the page outline.
    poly = np.zeros(gray.shape, np.uint8)
    cv2.fillPoly(poly, [q.astype(np.int32)], 1)
    hgt, wid = gray.shape
    pq = cv2.perspectiveTransform(q[None].astype(np.float32), H)[0]
    gx0, gy0 = np.maximum(pq.min(0) - 0.15 * Wt, [-2 * Wt, -2 * Wt])
    gx1, gy1 = np.minimum(pq.max(0) + 0.15 * Wt, [3 * Wt, 4 * Wt])
    cx, cy = np.meshgrid(np.arange(gx0, gx1, 12), np.arange(gy0, gy1, 12))
    cs = to_source(np.stack([cx.ravel(), cy.ravel()], 1))
    on = (cs[:, 0] >= 0) & (cs[:, 0] < wid) & (cs[:, 1] >= 0) & (cs[:, 1] < hgt)
    on[on] = poly[cs[on, 1].astype(int), cs[on, 0].astype(int)] > 0
    on = on.reshape(cx.shape)
    rows, cols = np.nonzero(on)
    x0, x1 = cx[0, cols.min()], cx[0, cols.max()]
    y0, y1 = cy[rows.min(), 0], cy[rows.max(), 0]
    step = 8
    gx, gy = np.meshgrid(np.arange(x0, x1 + step, step), np.arange(y0, y1 + step, step))
    m = to_source(np.stack([gx.ravel(), gy.ravel()], 1)).reshape(gx.shape + (2,)).astype(np.float32)
    ow, oh = int((x1 - x0) * SCALE), int((y1 - y0) * SCALE)
    mx = cv2.resize(m[..., 0], (ow, oh), interpolation=cv2.INTER_CUBIC)
    my = cv2.resize(m[..., 1], (ow, oh), interpolation=cv2.INTER_CUBIC)
    out = cv2.remap(gray, mx, my, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=255)
    inside = cv2.remap(cv2.dilate(pagemask, np.ones((9, 9), np.uint8)) * 255, mx, my, cv2.INTER_NEAREST,
                       borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    ys = sol[:n][good] * Ht
    pitch_t = float(np.median(np.diff(np.sort(ys)))) if good.sum() > 3 else 30.0
    block = {  # the text block in output pixels, and the line pitch there
        'x0': (0 - x0) * SCALE, 'x1': (Wt - x0) * SCALE,
        'y0': (ys.min() - y0) * SCALE, 'y1': (ys.max() - y0) * SCALE, 'pitch': pitch_t * SCALE,
    }
    return out, inside, {'lines': int(good.sum()), 'flat': None, 'block': block}


def tone(g, inside):
    """Paper to white, ink to black, without losing thin strokes or washing out large dark drawings."""
    g = g.astype(np.float32)
    bg = cv2.dilate(g, np.ones((31, 31), np.uint8))
    bg = cv2.GaussianBlur(cv2.medianBlur(bg.astype(np.uint8), 61).astype(np.float32), (0, 0), 15)
    small = cv2.resize(g, None, fx=1 / 8, fy=1 / 8, interpolation=cv2.INTER_AREA)
    big = cv2.morphologyEx(small, cv2.MORPH_CLOSE, np.ones((81, 81), np.uint8))
    big = cv2.resize(cv2.GaussianBlur(big, (0, 0), 6), (g.shape[1], g.shape[0]), interpolation=cv2.INTER_LINEAR)
    bg = np.where(bg < 0.55 * big, 0.75 * big, bg)  # only inside a big dark drawing, never in a page shadow
    r = np.clip(g / np.maximum(bg, 1), 0, 1.2)
    sharp = cv2.addWeighted(r, 1.6, cv2.GaussianBlur(r, (0, 0), 1.6), -0.6, 0)
    t = np.clip((sharp - 0.42) / (0.88 - 0.42), 0, 1)
    t = t * t * (3 - 2 * t)
    t[inside == 0] = 1.0
    return (t * 255).astype(np.uint8)
