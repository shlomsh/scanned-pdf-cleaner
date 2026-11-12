# Step 1. Photos in, upright JPEGs out, plus grid images for tracing each page's corners.
# usage: prepare.py INPUT WORK      INPUT = a PDF, a folder of images, or image files
#        prepare.py --turn WORK p-003.jpg 90|180|270     (clockwise) when a photo is sideways or upside down
import sys, os, glob, shutil
import cv2
import numpy as np
from common import save, load

LONG_EDGE = 2400   # photos are kept at most this big; more adds nothing a page needs
IMAGE_EXT = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp', '.bmp')


def fit(img):
    s = LONG_EDGE / max(img.shape[:2])
    return cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img


def from_pdf(path):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(path)
    for page in pdf:
        w, h = page.get_size()
        # A photo PDF: render at the photo's own resolution, not past it.
        px = [o.get_px_size()[0] / max(o.get_bounds()[2] - o.get_bounds()[0], 1) for o in page.get_objects()
              if o.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE]
        scale = min(LONG_EDGE / max(w, h), max(px)) if px else 300 / 72
        bmp = page.render(scale=min(scale, LONG_EDGE / max(w, h))).to_numpy()
        yield cv2.cvtColor(bmp, cv2.COLOR_RGB2BGR if bmp.shape[2] == 3 else cv2.COLOR_RGBA2BGR)


def from_images(paths):
    for p in paths:
        img = cv2.imread(p)  # applies EXIF orientation
        if img is None:
            raise SystemExit(f'cannot read {p} (HEIC? convert it first, e.g. sips -s format jpeg)')
        yield img


def grid(img, path):
    """The photo at most 1600 px tall/wide, with lines every 100 source px, labelled in hundreds."""
    s = min(1.0, 1600 / max(img.shape[:2]))
    im = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    ov = im.copy()
    H, W = img.shape[:2]
    for x in range(100, W, 100):
        cv2.line(ov, (int(x * s), 0), (int(x * s), im.shape[0]), (0, 0, 255), 1 if x % 500 else 2)
    for y in range(100, H, 100):
        cv2.line(ov, (0, int(y * s)), (im.shape[1], int(y * s)), (0, 0, 255), 1 if y % 500 else 2)
    im = cv2.addWeighted(ov, 0.45, im, 0.55, 0)
    for x in range(100, W, 100):
        for yy in (22, im.shape[0] - 8):
            cv2.putText(im, str(x // 100), (int(x * s) - 8, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    for y in range(100, H, 100):
        for xx in (4, im.shape[1] - 30):
            cv2.putText(im, str(y // 100), (xx, int(y * s) + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    cv2.imwrite(path, im, [cv2.IMWRITE_JPEG_QUALITY, 85])


def template(img, name):
    h, w = img.shape[:2]
    m = 0.03
    return {'src': name, 'quad': [[m * w, m * h], [(1 - m) * w, m * h], [(1 - m) * w, (1 - m) * h], [m * w, (1 - m) * h]]}


if __name__ == '__main__':
    if sys.argv[1] == '--turn':
        work, name, deg = sys.argv[2], sys.argv[3], int(sys.argv[4])
        p = os.path.join(work, 'src', name)
        code = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}[deg]
        img = cv2.rotate(cv2.imread(p), code)
        cv2.imwrite(p, img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        grid(img, os.path.join(work, 'grid', 'g-' + name[2:]))
        rough = load(work, 'rough.json', {})
        for k, v in rough.items():
            if v['src'] == name:
                rough[k] = template(img, name)
        save(work, 'rough.json', rough)
        print('turned', name, deg, '- trace its corners again')
        sys.exit()
    inputs, work = sys.argv[1:-1], sys.argv[-1]
    if os.path.exists(os.path.join(work, 'src')):
        raise SystemExit(f'{work}/src exists; use a new work folder')
    os.makedirs(os.path.join(work, 'src')); os.makedirs(os.path.join(work, 'grid'))
    if len(inputs) == 1 and inputs[0].lower().endswith('.pdf'):
        imgs = from_pdf(inputs[0])
    else:
        files = []
        for p in inputs:
            files += sorted(f for f in glob.glob(os.path.join(p, '*')) if f.lower().endswith(IMAGE_EXT)) if os.path.isdir(p) else [p]
        imgs = from_images(files)
    rough = {}
    for i, img in enumerate(imgs):
        img = fit(img)
        name = f'p-{i:03d}.jpg'
        cv2.imwrite(os.path.join(work, 'src', name), img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        grid(img, os.path.join(work, 'grid', f'g-{i:03d}.jpg'))
        rough[f'{i + 1:03d}'] = template(img, name)
        print(name, img.shape[1], 'x', img.shape[0])
    save(work, 'rough.json', rough)
    print(len(rough), 'photos; trace corners into', os.path.join(work, 'rough.json'))
