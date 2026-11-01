# -*- coding: utf-8 -*-
"""极简软件渲染器 (numpy z-buffer) —— 只用于生成预览 PNG。

依赖: numpy, Pillow
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def _u(v):
    v = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def camera(eye, target, up=(0, 1, 0), fov=30.0):
    eye = np.asarray(eye, float)
    target = np.asarray(target, float)
    up = _u(up)
    f = _u(target - eye)
    r = _u(np.cross(f, up))
    u = np.cross(r, f)
    return dict(eye=eye, f=f, r=r, u=u, tan=float(np.tan(np.radians(fov) * 0.5)))


# 相机坐标系内的三点光: (方向, 颜色, 强度)  方向 +z 指向观察方向
# 主光故意偏离视线 (约 55°): 太平的主光 (=跟着镜头走) 会让 1 mm 级的浮雕完全看不出明暗
LIGHTS = [((-0.60, 0.72, -0.62), (1.00, 0.98, 0.93), 0.78),
          ((0.85, 0.10, -0.55), (0.82, 0.89, 1.00), 0.32),
          ((0.05, -0.80, 0.45), (1.00, 0.94, 0.88), 0.24)]


def vertex_normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)


def corner_normals(V, F, cos_thresh=0.96):
    """按相邻面夹角分组算角点法线: 平面保持平面, 圆柱保持光滑。"""
    e1 = V[F[:, 1]] - V[F[:, 0]]
    e2 = V[F[:, 2]] - V[F[:, 0]]
    fn = np.cross(e1, e2)
    L = np.linalg.norm(fn, axis=1, keepdims=True)
    L[L < 1e-15] = 1.0
    un = fn / L
    inc = {}
    for fi in range(len(F)):
        for k in range(3):
            inc.setdefault(int(F[fi, k]), []).append(fi)
    cn = np.empty((len(F), 3, 3), dtype=np.float64)
    for v, fs in inc.items():
        nfs = un[fs]
        sim = nfs @ nfs.T
        for i, fi in enumerate(fs):
            s = nfs[sim[i] >= cos_thresh].sum(axis=0)
            nl = float(np.linalg.norm(s))
            k = int(np.where(F[fi] == v)[0][0])
            cn[fi, k] = (s / nl) if nl > 1e-12 else un[fi]
    return cn


def render(meshes, cam, W=1500, H=1050, ss=2, ambient=0.30, spec=0.20, rim=0.16,
           bg=((0.985, 0.986, 0.992), (0.855, 0.868, 0.902)), clip=None):
    """meshes: [{'V':Nx3,'F':Mx3,'color':(r,g,b)}] ; 返回 (uint8 图, hit 掩码)"""
    Wp, Hp = int(W * ss), int(H * ss)
    zb = np.full((Hp, Wp), np.inf)
    hit = np.zeros((Hp, Wp), bool)
    t = np.linspace(0.0, 1.0, Hp)[:, None, None]
    bgimg = np.array(bg[0])[None, None, :] * (1 - t) + np.array(bg[1])[None, None, :] * t
    img = np.broadcast_to(bgimg, (Hp, Wp, 3)).astype(np.float32).copy()
    aspect = Wp / Hp
    L = [(_u(cam['r'] * d[0] + cam['u'] * d[1] + cam['f'] * d[2]), np.array(c, float), float(i))
         for d, c, i in LIGHTS]
    view = -cam['f']

    order = sorted(range(len(meshes)),
                   key=lambda k: 0 if float(meshes[k].get('alpha', 1.0)) >= 0.999 else 1)
    for k in order:
        me = meshes[k]
        V = np.asarray(me['V'], float)
        F = np.asarray(me['F'], int)
        base = np.array(me.get('color', (0.7, 0.7, 0.7)), float)
        if clip is not None:
            axis, val, keep = clip
            cen = V[F].mean(axis=1)[:, axis] * keep
            F = F[cen >= val * keep - 1e-9]
            if len(F) == 0:
                continue
        cn = corner_normals(V, F)
        d = V - cam['eye']
        cx = d @ cam['r']
        cy = d @ cam['u']
        cz = d @ cam['f']
        sx = (cx / cz) / (cam['tan'] * aspect)
        sy = (cy / cz) / cam['tan']
        px = (sx + 1.0) * 0.5 * (Wp - 1)
        py = (1.0 - sy) * 0.5 * (Hp - 1)
        invz = 1.0 / np.maximum(cz, 1e-6)

        for fi, (a, b, c2) in enumerate(F):
            if cz[a] <= 0.05 or cz[b] <= 0.05 or cz[c2] <= 0.05:
                continue
            na, nb, nc = cn[fi, 0], cn[fi, 1], cn[fi, 2]
            x0, x1, x2 = px[a], px[b], px[c2]
            y0, y1, y2 = py[a], py[b], py[c2]
            xmin = int(max(0, np.floor(min(x0, x1, x2))))
            xmax = int(min(Wp - 1, np.ceil(max(x0, x1, x2))))
            ymin = int(max(0, np.floor(min(y0, y1, y2))))
            ymax = int(min(Hp - 1, np.ceil(max(y0, y1, y2))))
            if xmax < xmin or ymax < ymin:
                continue
            X, Y = np.meshgrid(np.arange(xmin, xmax + 1), np.arange(ymin, ymax + 1))
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-12:
                continue
            w0 = ((y1 - y2) * (X - x2) + (x2 - x1) * (Y - y2)) / den
            w1 = ((y2 - y0) * (X - x2) + (x0 - x2) * (Y - y2)) / den
            w2 = 1.0 - w0 - w1
            m = (w0 >= -1e-9) & (w1 >= -1e-9) & (w2 >= -1e-9)
            if not m.any():
                continue
            iz = w0 * invz[a] + w1 * invz[b] + w2 * invz[c2]
            zz = 1.0 / np.maximum(iz, 1e-12)
            sub = m & (zz < zb[ymin:ymax + 1, xmin:xmax + 1])
            if not sub.any():
                continue
            nrm = (w0[..., None] * na * invz[a] + w1[..., None] * nb * invz[b]
                   + w2[..., None] * nc * invz[c2]) * zz[..., None]
            nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-12)
            col = np.zeros(nrm.shape, dtype=np.float64)
            for ld, lc, li in L:
                col += np.maximum(0.0, nrm @ ld)[..., None] * (lc * li)
                hv = _u(ld + view)
                col += (np.maximum(0.0, nrm @ hv) ** 40)[..., None] * (lc * spec)
            col += ambient * 0.85
            rimp = np.clip(1.0 - np.abs(nrm @ view), 0, 1) ** 3
            out = np.clip(base[None, None, :] * col + rimp[..., None] * rim, 0, 1)
            alpha = float(me.get('alpha', 1.0))
            if alpha >= 0.999:
                zb[ymin:ymax + 1, xmin:xmax + 1][sub] = zz[sub]
                img[ymin:ymax + 1, xmin:xmax + 1][sub] = out[sub]
            else:
                cur = img[ymin:ymax + 1, xmin:xmax + 1]
                cur[sub] = cur[sub] * (1.0 - alpha) + out[sub] * alpha
            hit[ymin:ymax + 1, xmin:xmax + 1][sub] = True

    if ss > 1:
        img = img.reshape(H, ss, W, ss, 3).mean(axis=(1, 3))
        hit2 = hit.reshape(H, ss, W, ss).any(axis=(1, 3))
    else:
        hit2 = hit
    return (np.clip(img, 0, 1) * 255).astype(np.uint8), hit2


def save(arr, path):
    Image.fromarray(arr).save(path)


def project(cam, p, W, H):
    """把 3D 点投到像素坐标, 供标注用"""
    d = np.asarray(p, float) - cam['eye']
    cx, cy, cz = d @ cam['r'], d @ cam['u'], d @ cam['f']
    if cz <= 1e-6:
        return None
    aspect = W / H
    sx = (cx / cz) / (cam['tan'] * aspect)
    sy = (cy / cz) / cam['tan']
    return ((sx + 1.0) * 0.5 * (W - 1), (1.0 - sy) * 0.5 * (H - 1))


def annotate(arr, items, size=25, color=(30, 34, 42), line=(120, 128, 140)):
    """items: [(px, py, dx, dy, 文字)] —— 从 (px,py) 拉一条引线到 (px+dx,py+dy) 再写字"""
    im = Image.fromarray(arr)
    d = ImageDraw.Draw(im)
    for px, py, dx, dy, text in items:
        if px is None:
            continue
        x2, y2 = px + dx, py + dy
        d.line([px, py, x2, y2], fill=line, width=2)
        d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=line)
        anchor = "lm" if dx >= 0 else "rm"
        d.text((x2 + (8 if dx >= 0 else -8), y2), text, font=_font(size), fill=color, anchor=anchor)
    return np.array(im)


def _font(size):
    for p in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\msyhbd.ttc",
              r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\simsun.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


def label(im, xy, text, size=26, fill=(40, 44, 52), anchor="la"):
    d = ImageDraw.Draw(im)
    d.text(xy, text, font=_font(size), fill=fill, anchor=anchor)


def parts_sheet(items, path, cols=4, cell=(560, 430), title="零件一览 (单位 mm)"):
    """items: [(名称, V, F, color, 说明)] —— 每格单独渲染 + 中文标签"""
    cw, ch = cell
    rows = int(np.ceil(len(items) / cols))
    W, H = cols * cw, rows * ch
    canvas = np.full((H, W, 3), 255, np.uint8)
    for k, (name, V, F, color, note) in enumerate(items):
        r, c = divmod(k, cols)
        V = np.asarray(V, float)
        lo = V.min(axis=0)
        hi = V.max(axis=0)
        cen = (lo + hi) * 0.5
        rad = 0.5 * float(np.linalg.norm(hi - lo)) + 1e-6
        dist = rad * 1.12 / np.tan(np.radians(16.0))
        eye = cen + _u((0.95, 0.72, -1.0)) * dist
        cam = camera(eye, cen, fov=32.0)
        sub, hit = render([dict(V=V, F=F, color=color)], cam, W=cw, H=ch - 62, ss=1)
        sub = np.where(hit[..., None], sub, 255).astype(np.uint8)
        y0 = r * ch
        canvas[y0:y0 + ch - 62, c * cw:c * cw + cw] = sub
        im = Image.fromarray(canvas)
        label(im, (c * cw + cw // 2, y0 + ch - 30), name, size=27, anchor="ms")
        label(im, (c * cw + cw // 2, y0 + ch - 8), note, size=19,
              fill=(110, 116, 128), anchor="ms")
        d = ImageDraw.Draw(im)
        d.rectangle([c * cw, y0, c * cw + cw - 1, y0 + ch - 1], outline=(216, 220, 228), width=1)
        canvas = np.array(im)
    Image.fromarray(canvas).save(path)
    return path
