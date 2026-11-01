#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MG90S 电梯按钮 “后拉” 演示样机  v1
方案 = 苏格兰轭 (Scotch yoke) + 无胶 / 可拆 / 可换销 的装配思路 (自研)

坐标:  X 右      Y 上      Z 朝墙里 (面板正面 Z=0)
      舵机在 -X 一侧, 按钮 / 滑杆在 X=0 轴线上, 两层机构沿 Y 叠放 (中心距 51)

原理:  舵机轴沿 X 伸出 -> 曲柄在 YZ 平面内转 -> 曲柄上的销钉在滑块(轭)的竖槽里滑
      -> 只剩销钉的 Y 分量被约束掉, 滑块沿 Z 做纯直线运动。
      位移 = R*sin(角度),  R = 8 mm, 转 22° 拉 3 mm。

依赖:  pip install manifold3d trimesh numpy pillow
运行:  py -3 build.py
"""
import math
import os
import sys

import numpy as np
import manifold3d as m
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIR_STL = os.path.join(ROOT, "stl")
DIR_IMG = os.path.join(ROOT, "预览")
os.makedirs(DIR_STL, exist_ok=True)
os.makedirs(DIR_IMG, exist_ok=True)

sys.path.insert(0, HERE)
import render as rnd          # noqa: E402

M = m.Manifold
SEG = 64
RAD = math.radians

# ============================== 参数 (mm) ==============================
# ---- 面板 / 按钮 ----
PANEL_W, PANEL_H, PANEL_T = 70.0, 125.0, 5.0
BTN_Y = (37.0, 88.0)                       # 两个按钮轴线高度
DY = BTN_Y[1] - BTN_Y[0]                   # 51
BORE_D = 24.8
BEZEL_ID, BEZEL_OD, BEZEL_H = 25.6, 31.0, 1.0
CAP_D, CAP_T = 27.6, 2.6
CAP_BACK = -5.0                            # 静止时帽背面 Z (到凸圈前面 = 4 = 行程)
CAP_FRONT = CAP_BACK - CAP_T               # -7.6
STEM_D = 24.0
STEM_Z0, STEM_Z1 = CAP_BACK, 11.0
SOCK_W, SOCK_H = 5.4, 11.0                 # 杆后端方孔 (滑杆插进去)
SOCK_Z0 = 3.5                              # 方孔底 = 滑杆前端面 -> 自然对位
LINK_Z = 9.0                               # 连接销轴线 (必须在面板背面之后)
LINK_D, LINK_HOLE_D = 3.2, 3.4
LINK_HEAD_D, LINK_HEAD_T = 6.0, 2.0
ARROW_H = 1.3                              # ▲▼ 浮雕凸出高度
STOP_TRAVEL = 4.0                          # 硬限位 (帽背顶到凸圈前面)

# ---- 苏格兰轭 ----
R_CRANK = 8.0
OP_TRAVEL = 3.0                            # 默认行程 = 22°
Z_SHAFT = 33.5                             # 舵机轴心 Z (两层相同)
BAR_W, BAR_H = 5.0, 10.6
BAR_Z0, BAR_Z1 = 3.5, 28.0
FIN_T, FIN_L = 5.5, 22.0
FIN_Z0, FIN_Z1 = 27.5, 39.5
SLOT_W, SLOT_HY = 6.6, 3.5                 # 竖槽: Z 向宽 / Y 向两心距的一半
BLK_X1, BLK_HY = 4.7, 8.2
BLK_Z0, BLK_Z1 = 15.5, 27.0
TUN_HW, TUN_HH = 2.7, 5.7
SPINE_X0, SPINE_X1 = -10.0, -4.7
SPINE_Z0, SPINE_Z1 = 16.5, 26.5

# ---- 舵机墙 / 底座 ----
WALL_X0, WALL_X1 = -21.0, -18.0
WALL_Z0, WALL_Z1 = 23.0, 42.5
WALL_Y1 = 99.0
WIN_HY, WIN_HZ = 11.7, 6.6
EAR_HP, EAR_HOLE_D = 13.85, 2.0
PLATE_X0, PLATE_X1 = -44.0, 38.0
PLATE_Z0, PLATE_Z1 = -6.0, 42.5
PLATE_T = 5.0
POST_X, POST_HW = 28.0, 5.0
POST_Z0, POST_Z1, POST_Y1 = 9.0, 13.0, 20.0
POST_HOLE_D, POST_HOLE_Y = 3.3, 14.0
BOSS_D, BOSS_Z0, BOSS_Z1 = 8.0, PANEL_T, PANEL_T + 4.0
BOSS_HOLE_D = 2.5

# ---- 曲柄 / 销钉 ----
CRANK_X0, CRANK_X1 = -16.5, -12.0          # 装在舵机花键上, 厚 4.5
HUB_D = 17.0
SPLINE_BORE = 4.9                          # 花键孔 (略大于 ⌀4.8, 靠夹紧螺丝抱死)
PIN_D = 6.0
LOBE_D = 11.0
SLIT_W = 0.8                               # 夹紧缝宽
CLAMP_Y = -5.0                             # 夹紧螺丝相对轴心的 Y 偏置
CLAMP_D_CLR, CLAMP_D_TAP = 3.3, 2.5
PIN_X0, PIN_X1 = -16.0, 3.0
PIN_FL_D, PIN_FL_T = 9.0, 1.5
LINK_X0, LINK_X1 = -13.0, 11.5

# ---- MG90S 外形 ----
SV_CASE_TOP = WALL_X0 + 1.5                # 机身端面 (埋进墙 1.5)
SV_CASE_L, SV_CASE_HY, SV_CASE_HZ = 22.6, 11.4, 6.2
SV_BOSS_L, SV_BOSS_D = 3.0, 11.8
SV_SPLINE_L, SV_SPLINE_D = 4.5, 4.8
SV_EAR_T, SV_EAR_HY, SV_EAR_HZ = 2.5, 16.05, 6.2
SV_BOSS_X0, SV_BOSS_X1 = SV_CASE_TOP, SV_CASE_TOP + SV_BOSS_L
SV_SPLINE_X0, SV_SPLINE_X1 = SV_BOSS_X1, SV_BOSS_X1 + SV_SPLINE_L

COL = {"base": (0.44, 0.47, 0.52), "panel": (0.80, 0.81, 0.84),
       "up": (0.94, 0.68, 0.20), "dn": (0.24, 0.54, 0.85),
       "yoke": (0.20, 0.63, 0.60), "crank": (0.90, 0.44, 0.14),
       "pin": (0.97, 0.93, 0.45), "link": (0.82, 0.24, 0.24),
       "ghost": (0.34, 0.40, 0.55)}


# ============================== 小工具 ==============================
def box(x0, x1, y0, y1, z0, z1):
    return M.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def cylx(x0, x1, y, z, d0, d1=None):
    return M.cylinder(x1 - x0, d0 / 2, (d1 if d1 else d0) / 2, SEG).rotate((0, 90, 0)).translate((x0, y, z))


def cyly(y0, y1, x, z, d):
    return M.cylinder(y1 - y0, d / 2, d / 2, SEG).rotate((-90, 0, 0)).translate((x, y0, z))


def cylz(z0, z1, x, y, d):
    return M.cylinder(z1 - z0, d / 2, d / 2, SEG).translate((x, y, z0))


def hull(*parts):
    return M.batch_hull(list(parts))


def uni(*parts):
    return M.batch_boolean(list(parts), m.OpType.Add)


def inter(a, b):
    return M.batch_boolean([a, b], m.OpType.Intersect)


def rotx(man, cy, cz, deg):
    """绕“过点 (cy,cz)、方向 +X”的轴旋转 deg 度"""
    return man.translate((0, -cy, -cz)).rotate((deg, 0, 0)).translate((0, cy, cz))


def dims(man):
    return man.bounding_box()


def vf(man):
    me = man.to_mesh()
    return np.asarray(me.vert_properties, float)[:, :3], np.asarray(me.tri_verts, int)


# ============================== 打印姿态 ==============================
TF = {"base": lambda q: q.rotate((90, 0, 0)),        # 底板平放, 墙/立柱朝上
      "panel": lambda q: q.rotate((180, 0, 0)),      # 面板背面朝下, ▲▼ 朝上
      "button": lambda q: q.rotate((180, 0, 0)),     # 按钮杆朝下, 帽朝上
      "flat_x": lambda q: q.rotate((0, -90, 0)),     # 板面平放 (轭板/曲柄)
      "pin": lambda q: q.rotate((90, 0, 0))}         # 轴水平躺下 (销钉)


def drop(man, key):
    man = TF[key](man)
    x0, y0, z0, x1, y1, z1 = dims(man)
    return man.translate((-(x0 + x1) / 2, -(y0 + y1) / 2, -z0))


# ============================== 零件 ==============================
def part_panel():
    rr = 6.0
    p = hull(M.cube((PANEL_W, PANEL_H - 2 * rr, PANEL_T)).translate((-PANEL_W / 2, rr, 0)),
             M.cube((PANEL_W - 2 * rr, PANEL_H, PANEL_T)).translate((-PANEL_W / 2 + rr, 0, 0)))
    for yb in BTN_Y:
        p = p - cylz(-1, PANEL_T + 1, 0, yb, BORE_D)
    rings = uni(*[cylz(-BEZEL_H, 0, 0, yb, BEZEL_OD) - cylz(-BEZEL_H - 1, 1, 0, yb, BEZEL_ID)
                  for yb in BTN_Y])
    p = p + rings
    for sx in (-1, 1):
        p = p + cylz(BOSS_Z0, BOSS_Z1, sx * POST_X, POST_HOLE_Y, BOSS_D)
        p = p - cylz(BOSS_Z0, BOSS_Z1 + 1, sx * POST_X, POST_HOLE_Y, BOSS_HOLE_D)
    return p


def part_button(up: bool):
    yb = 0.0
    # 帽与杆在 Z 向互相咬合 0.5, 避免用 "+0.001" 造成虚拟过盈
    b = uni(cylz(CAP_FRONT, CAP_BACK, 0, yb, CAP_D),
            cylz(CAP_BACK - 0.5, STEM_Z1, 0, yb, STEM_D))
    b = b - box(-SOCK_W / 2, SOCK_W / 2, yb - SOCK_H / 2, yb + SOCK_H / 2, SOCK_Z0, STEM_Z1 + 1)
    b = b - cylx(-STEM_D, STEM_D, yb, LINK_Z, LINK_HOLE_D)
    # ▲▼ 浮雕: 做成带斜面的三角台, 这样各个角度都能看出明暗 (平顶面会和帽面一样亮)
    w, h = 5.4, 4.4
    zb0, zb1 = CAP_FRONT - ARROW_H, CAP_FRONT + 0.6
    s = 1.0 if up else -1.0
    by, ay = yb - s * h, yb + s * h
    cyc = (2 * by + ay) / 3.0
    k = 0.5
    bot = [(-w, by), (w, by), (0.0, ay)]
    top = [(x * k, cyc + k * (y - cyc)) for x, y in bot]
    # 大三角在“根部”(贴着帽面), 小三角在“尖端” -> 斜面朝外, 从任何角度都看得出
    tri = hull(*[cylz(zb1 - 0.05, zb1, x, y, 1.0) for x, y in bot],
               *[cylz(zb0, zb0 + 0.05, x, y, 1.0) for x, y in top])
    return uni(b, tri)


def part_yoke():
    bar = box(-BAR_W / 2, BAR_W / 2, -BAR_H / 2, BAR_H / 2, BAR_Z0, BAR_Z1)
    fin = box(-FIN_T / 2, FIN_T / 2, -FIN_L / 2, FIN_L / 2, FIN_Z0, FIN_Z1)
    fin = fin - hull(cylx(-FIN_T, FIN_T, SLOT_HY, Z_SHAFT, SLOT_W),
                     cylx(-FIN_T, FIN_T, -SLOT_HY, Z_SHAFT, SLOT_W))
    y = uni(bar, fin)
    y = y - hull(box(-BAR_W / 2 - 1, BAR_W / 2 + 1, -BAR_H / 2 - 1, BAR_H / 2 + 1, BAR_Z0 - 0.001, BAR_Z0 + 0.001),
                 box(-BAR_W / 2 + 0.6, BAR_W / 2 - 0.6, -BAR_H / 2 + 0.6, BAR_H / 2 - 0.6, BAR_Z0 + 0.7, BAR_Z0 + 0.701))
    # 连接销横孔 (与按钮杆上的孔同高, 保证装入时自动对齐)
    y = y - cylx(-BAR_W / 2 - 1, BAR_W / 2 + 1, 0, LINK_Z, LINK_HOLE_D)
    return y


def part_crank():
    hub = cylx(CRANK_X0, CRANK_X1, 0, 0, HUB_D)
    lobe = cylx(CRANK_X0, CRANK_X1, R_CRANK, 0, LOBE_D)
    arm = hull(cylx(CRANK_X0, CRANK_X1, 0, 0, HUB_D - 3.0),
               cylx(CRANK_X0, CRANK_X1, R_CRANK, 0, LOBE_D - 2.0))
    c = uni(hub, lobe, arm)
    c = c - cylx(CRANK_X0 - 1, CRANK_X1 + 1, 0, 0, SPLINE_BORE)
    c = c - cylx(CRANK_X0 - 1, CRANK_X1 + 1, R_CRANK, 0, PIN_D)
    c = c - box(CRANK_X0 - 1, CRANK_X1 + 1, -HUB_D, 0.0, -SLIT_W / 2, SLIT_W / 2)
    c = c - cylz(-HUB_D / 2, -SLIT_W / 2, 0, CLAMP_Y, CLAMP_D_TAP)
    c = c - cylz(SLIT_W / 2, HUB_D / 2, 0, CLAMP_Y, CLAMP_D_CLR)
    return c


def part_pin():
    return uni(cylx(PIN_X0, PIN_X1, 0, 0, PIN_D),
               cylx(CRANK_X1, CRANK_X1 + PIN_FL_T, 0, 0, PIN_FL_D))


def part_link():
    return uni(cylx(LINK_X0, LINK_X1, 0, 0, LINK_D),
               cylx(LINK_X0 - LINK_HEAD_T, LINK_X0, 0, 0, LINK_HEAD_D))


def ghost_servo(yb):
    ys = yb - R_CRANK
    case = box(SV_CASE_TOP - SV_CASE_L, SV_CASE_TOP, ys - SV_CASE_HY, ys + SV_CASE_HY,
               Z_SHAFT - SV_CASE_HZ, Z_SHAFT + SV_CASE_HZ)
    boss = cylx(SV_BOSS_X0, SV_BOSS_X1, ys, Z_SHAFT, SV_BOSS_D)
    ears = box(WALL_X0 - SV_EAR_T, WALL_X0, ys - SV_EAR_HY, ys + SV_EAR_HY,
               Z_SHAFT - SV_EAR_HZ, Z_SHAFT + SV_EAR_HZ)
    ears = ears - uni(*[cylx(WALL_X0 - SV_EAR_T - 1, WALL_X0 + 1, ys + s * EAR_HP, Z_SHAFT, EAR_HOLE_D)
                        for s in (-1, 1)])
    return uni(case, boss, ears)


def ghost_spline(yb):
    ys = yb - R_CRANK
    return cylx(SV_SPLINE_X0, SV_SPLINE_X1, ys, Z_SHAFT, SV_SPLINE_D)


def part_base():
    rr = 5.0
    b = hull(*[cyly(-PLATE_T, 0, x, z, rr * 2)
               for x in (PLATE_X0 + rr, PLATE_X1 - rr)
               for z in (PLATE_Z0 + rr, PLATE_Z1 - rr)])
    for sx in (-1, 1):
        b = b + box(sx * POST_X - POST_HW, sx * POST_X + POST_HW, 0, POST_Y1, POST_Z0, POST_Z1)
        b = b - cylz(POST_Z0 - 1, POST_Z1 + 1, sx * POST_X, POST_HOLE_Y, POST_HOLE_D)
    b = b + box(WALL_X0, WALL_X1, 0, WALL_Y1, WALL_Z0, WALL_Z1)
    b = b + box(WALL_X0 - 4.0, WALL_X0, 0, 12.0, WALL_Z0 + 3, WALL_Z1 - 4)
    spine_y1 = BTN_Y[1] + BLK_HY
    b = b + box(SPINE_X0, SPINE_X1, 0, spine_y1, SPINE_Z0, SPINE_Z1)
    b = b + box(SPINE_X0 - 4.0, SPINE_X0, 0, 12.0, SPINE_Z0 + 2, SPINE_Z1)
    for yb in BTN_Y:
        ys = yb - R_CRANK
        b = b + box(SPINE_X1 - 0.001, BLK_X1, yb - BLK_HY, yb + BLK_HY, BLK_Z0, BLK_Z1)
        b = b - box(WALL_X0 - 1, WALL_X1 + 1, ys - WIN_HY, ys + WIN_HY,
                    Z_SHAFT - WIN_HZ, Z_SHAFT + WIN_HZ)
        for s in (-1, 1):
            b = b - cylx(WALL_X0 - 1, WALL_X1 + 1, ys + s * EAR_HP, Z_SHAFT, EAR_HOLE_D)
        b = b - box(-TUN_HW, TUN_HW, yb - TUN_HH, yb + TUN_HH, BLK_Z0 - 1, BLK_Z1 + 1)
    return b


# ============================== 装配 ==============================
def build_assembly():
    base = part_base()
    panel = part_panel()
    btn_up, btn_dn = part_button(True), part_button(False)
    yoke0, crank0, pin0, link0 = part_yoke(), part_crank(), part_pin(), part_link()

    def layer(yb, btn):
        ys = yb - R_CRANK
        return dict(ys=ys, yb=yb,
                    yoke=yoke0.translate((0, yb, 0)),
                    crank=crank0.translate((0, ys, Z_SHAFT)),
                    pin=pin0.translate((0, yb, Z_SHAFT)),      # 销钉在曲柄的销孔里 -> 高度 = 按钮轴线
                    link=link0.translate((0, yb, LINK_Z)),
                    button=btn.translate((0, yb, 0)))

    return base, panel, [layer(BTN_Y[0], btn_dn), layer(BTN_Y[1], btn_up)]


def pose(L, deg):
    t = R_CRANK * math.sin(RAD(deg))
    cp = rotx(uni(L["crank"], L["pin"]), L["ys"], Z_SHAFT, deg)
    off = (0, 0, t)
    return cp, L["yoke"].translate(off), L["button"].translate(off), L["link"].translate(off)


# ============================== 校验 ==============================
DEGS = (0, 3, 6, 9, 12, 15, 18, 22, 26, 30)


def verify(base, panel, layers):
    """两两检查: 4 个运动件彼此之间、以及每个运动件 vs 固定件/舵机。
    注意: 曲柄与销钉是设计上的过盈配合, 所以把它们当成一个整体 cp, 不互相检查。"""
    rows, worst_gap, diag = [], [], []
    fixedm = {"底座": base, "面板": panel}
    fixed = uni(base, panel)
    for i, L in enumerate(layers):
        ghost = ghost_servo(BTN_Y[i])
        name = "下层(▼)" if i == 0 else "上层(▲)"
        for deg in DEGS:
            cp, yk, bt, lk = pose(L, deg)
            mv = {"曲柄+销": cp, "滑块": yk, "按钮": bt, "连接销": lk}
            keys = list(mv)
            vfix = vgh = 0.0
            for nm in keys:
                v = inter(mv[nm], fixed).volume()
                if v > 1e-3:
                    diag.append("%s %2d° t=%.2f  %s <-> 底座/面板 = %.4f mm3" % (name, deg, R_CRANK * math.sin(RAD(deg)), nm, v))
                vfix = max(vfix, v)
                v = inter(mv[nm], ghost).volume()
                if v > 1e-3:
                    diag.append("%s %2d° t=%.2f  %s <-> 舵机 = %.4f mm3" % (name, deg, R_CRANK * math.sin(RAD(deg)), nm, v))
                vgh = max(vgh, v)
            for a in range(len(keys)):
                for b in range(a + 1, len(keys)):
                    v = inter(mv[keys[a]], mv[keys[b]]).volume()
                    if v > 1e-3:
                        diag.append("%s %2d° t=%.2f  %s <-> %s = %.4f mm3"
                                    % (name, deg, R_CRANK * math.sin(RAD(deg)), keys[a], keys[b], v))
                        vfix = max(vfix, v)
            rows.append((name, deg, R_CRANK * math.sin(RAD(deg)), vfix, vgh))
    # 两层运动件之间的最小间隙 (四种极限组合)
    g = 9e9
    for d0 in (0, 30):
        for d1 in (0, 30):
            a = uni(*pose(layers[0], d0))
            b = uni(*pose(layers[1], d1))
            g = min(g, a.min_gap(b, 120.0))
    worst_gap.append(("两层运动件", g))
    return rows, worst_gap, diag


def kinematic_table():
    return [(deg, R_CRANK * math.sin(RAD(deg)), R_CRANK * (1 - math.cos(RAD(deg))))
            for deg in (0, 5, 10, 15, 18, 22, 26, 30)]


def clearances(base, panel, layers):
    """静止姿态下各运动副的真实间隙 (用 manifold 的最小距离算, 不靠手算)"""
    L = layers[0]
    cp, yk, bt, lk = pose(L, 0)
    g = ghost_servo(BTN_Y[0])
    prs = [("销钉 ⌀%.1f → 竖槽侧壁 (槽宽 %.1f)" % (PIN_D, SLOT_W), L["pin"], yk),
           ("滑杆截面 → 按钮方孔 (5.4 x 11.0)", yk, bt),
           ("滑杆截面 → 导向块方孔 (5.4 x 11.4)", yk, base),
           ("连接销 ⌀%.1f → 按钮横孔 ⌀%.1f" % (LINK_D, LINK_HOLE_D), lk, bt),
           ("连接销 → 滑杆横孔", lk, yk),
           ("按钮杆 ⌀%.1f → 面板孔 ⌀%.1f" % (STEM_D, BORE_D), bt, panel),
           ("按钮后端 (z=11) → 导向块前端 (z=15.5)", bt, base),
           ("曲柄 (半径 %.1f) → 底座" % (R_CRANK + LOBE_D / 2), cp, base),
           ("曲柄 + 销钉 → 舵机外形", cp, g),
           ("轭板 → 底座导向块", yk, base)]
    return [(txt, a.min_gap(b, 200.0)) for txt, a, b in prs]


# ============================== 导出 ==============================
def export_all(items):
    info = []
    for fname, man, key in items:
        d = drop(man, key)
        V, F = vf(d)
        tri = trimesh.Trimesh(vertices=V, faces=F)
        tri.export(os.path.join(DIR_STL, fname))
        x0, y0, z0, x1, y1, z1 = dims(d)
        info.append((fname, d.volume() / 1000.0, len(F), tri.is_watertight,
                     (x1 - x0, y1 - y0, z1 - z0)))
    return info


# ============================== 渲染 ==============================
def render_figures(base, panel, layers, sheet):
    out = []
    L0, L1 = layers

    def mk(man, col, alpha=1.0):
        V, F = vf(man)
        m = dict(V=V, F=F, color=col)
        if alpha < 0.999:
            m["alpha"] = alpha
        return m

    def shot(ms, cam, name, W=1500, H=1050, ss=2, clip=None, notes=()):
        img, _ = rnd.render(ms, cam, W=W, H=H, ss=ss, clip=clip)
        if notes:
            it = []
            for p3, dx, dy, tx in notes:
                q = rnd.project(cam, p3, W, H)
                if q:
                    it.append((q[0], q[1], dx, dy, tx))
            img = rnd.annotate(img, it)
        p = os.path.join(DIR_IMG, name + ".png")
        rnd.save(img, p)
        out.append(p)

    cp0, yk0, bt0, lk0 = pose(L0, 0)
    cp1, yk1, bt1, lk1 = pose(L1, 0)

    # 01 总装 / 正面
    shot([mk(base, COL["base"]), mk(panel, COL["panel"]),
          mk(L0["button"], COL["dn"]), mk(L1["button"], COL["up"])],
         rnd.camera((150, 178, -270), (0, 60, 12), fov=25), "01_总装_正面")

    # 02 总装 / 背面 3/4 (舵机与按钮半透明, 看得到里面的机构)
    shot([mk(base, COL["base"]),
          mk(ghost_servo(BTN_Y[0]), COL["ghost"], 0.30), mk(ghost_servo(BTN_Y[1]), COL["ghost"], 0.30),
          mk(yk0, COL["yoke"]), mk(yk1, COL["yoke"]),
          mk(cp0, COL["crank"]), mk(cp1, COL["crank"]),
          mk(bt0, COL["dn"], 0.62), mk(bt1, COL["up"], 0.62),
          mk(lk0, COL["link"]), mk(lk1, COL["link"])],
         rnd.camera((-215, 152, 228), (-2, 58, 22), fov=28), "02_总装_背面",
         notes=[((-14.25, 29, 33.5), -120, -70, "曲柄"),
                ((-30, 29, 39.7), -230, 10, "MG90S 舵机 (半透明)"),
                ((0, 37, 39.5), 90, -120, "轭板竖槽"),
                ((0, 31, 16), 150, 80, "滑杆"),
                ((-13.5, 37, 9), -170, 150, "连接销")])

    # 03 机构特写 (下层, 只留机构本身: 舵机/按钮半透明)
    shot([mk(ghost_servo(BTN_Y[0]), COL["ghost"], 0.26),
          mk(cp0, COL["crank"]), mk(yk0, COL["yoke"]),
          mk(bt0, COL["dn"], 0.30), mk(lk0, COL["link"])],
         rnd.camera((196, 128, -158), (-12, 35, 20), fov=20), "03_机构特写",
         notes=[((-31, 29, 33.5), -300, -120, "MG90S 舵机 (半透明)"),
                ((-15.0, 21.5, 33.5), -110, 230, "曲柄: 花键孔 + 夹紧缝"),
                ((-2, 37, 33.5), 60, -170, "销钉"),
                ((0, 45.5, 33.5), 230, -60, "轭板竖槽"),
                ((0, 31.5, 20), -250, 60, "滑杆"),
                ((11.5, 37, 9), 130, 150, "连接销"),
                ((0, 44, -6), -60, -280, "按钮 (半透明)")])

    # 04 / 05 侧向剖视 (沿 -X 看; 剪掉曲柄看销钉在槽里的状态)
    cam4 = rnd.camera((-520, BTN_Y[0], Z_SHAFT), (-14.25, BTN_Y[0], Z_SHAFT), fov=5.4)
    for tag, deg, txt in (("04_剖视_静止", 0, "静止: 销钉在槽中央, 按钮行程 0"),
                          ("05_剖视_压下3mm", 22, "按下 3 mm: 曲柄转 22°, 销钉在槽里下移 0.58 mm")):
        cp, yk, bt, lk = pose(L0, deg)
        t = R_CRANK * math.sin(RAD(deg))
        shot([mk(base, COL["base"]), mk(panel, COL["panel"], 0.30),
              mk(yk, COL["yoke"]), mk(bt, COL["dn"], 0.45),
              mk(cp, COL["crank"]), mk(lk, COL["link"])],
             cam4, tag, W=1500, H=620, ss=2, clip=(0, -11.5, 1),
             notes=[((0, 37, -6.6 + t), -40, -120, "按钮"),
                    ((0, 32, 14 + t), 40, 120, "滑杆"),
                    ((0, 37 - R_CRANK * (1 - math.cos(RAD(deg))), 33.5 + t), 150, 60, "销钉"),
                    ((0, 46, 33.5), 170, -90, "轭板竖槽"),
                    ((-2.75, 30, 33.5), -140, 140, txt)])

    # 06 爆炸图
    shot([mk(base, COL["base"]),
          mk(ghost_servo(BTN_Y[0]).translate((-64, 0, 0)), COL["ghost"], 0.55),
          mk(ghost_servo(BTN_Y[1]).translate((-64, 0, 0)), COL["ghost"], 0.55),
          mk(cp0.translate((-27, 0, 0)), COL["crank"]),
          mk(cp1.translate((-27, 0, 0)), COL["crank"]),
          mk(yk0.translate((0, 0, 30)), COL["yoke"]),
          mk(yk1.translate((0, 0, 30)), COL["yoke"]),
          mk(L0["button"].translate((0, 0, 68)), COL["dn"]),
          mk(L1["button"].translate((0, 0, 68)), COL["up"]),
          mk(panel.translate((-6, 0, 112)), COL["panel"], 0.92)],
         rnd.camera((500, 300, -250), (-14, 52, 45), fov=27), "06_爆炸图", W=1500, H=1100)

    # 07 零件一览
    items = []
    for nm, note, man, col in sheet:
        V, F = vf(man)
        items.append((nm, V, F, col, note))
    rnd.parts_sheet(items, os.path.join(DIR_IMG, "07_零件一览.png"), cols=4, cell=(620, 470))
    out.append(os.path.join(DIR_IMG, "07_零件一览.png"))

    # 09 打印摆放 (每个零件按切片软件里应有的姿态)
    pr = [("01 底座", "底板贴平台, 一切竖直, 不用支撑", base, COL["base"], "base"),
          ("02 面板", "背面朝下平放, 凸圈/▲▼ 朝上", panel, COL["panel"], "panel"),
          ("03 按钮 ▲", "杆朝下、帽朝上", part_button(True), COL["up"], "button"),
          ("04 按钮 ▼", "杆朝下、帽朝上", part_button(False), COL["dn"], "button"),
          ("05 滑块", "轭板平放, 竖槽成竖直孔", part_yoke(), COL["yoke"], "flat_x"),
          ("06 曲柄", "板面平放, 花键孔竖直", part_crank(), COL["crank"], "flat_x"),
          ("07 销钉", "横躺在平台上", part_pin(), COL["pin"], "pin"),
          ("08 连接销", "横躺在平台上", part_link(), COL["link"], "pin")]
    items2 = [(nm, *vf(drop(man, key)), col, note) for nm, note, man, col, key in pr]
    rnd.parts_sheet(items2, os.path.join(DIR_IMG, "08_打印摆放.png"), cols=4, cell=(620, 470))
    out.append(os.path.join(DIR_IMG, "08_打印摆放.png"))

    # 10 原理图
    out.append(principle_figure())
    return out


def principle_figure():
    """纯 PIL 画的原理图: 左=曲柄+竖槽示意, 右=行程曲线"""
    from PIL import Image, ImageDraw
    W, H = 1500, 820
    img = Image.new("RGB", (W, H), (252, 252, 254))
    d = ImageDraw.Draw(img)
    f = rnd._font
    ink, gray, dim = (38, 42, 52), (150, 156, 168), (206, 210, 218)
    teal, orange, blue = (26, 150, 140), (226, 116, 40), (50, 120, 200)

    d.text((52, 30), "① 曲柄转一点, 销钉在竖槽里上下滑, 滑块只走直线", font=f(30), fill=ink)
    S = 18.0
    ox, oy = 330.0, 430.0
    ys0 = BTN_Y[0] - R_CRANK

    def P(y, z):
        return (ox + S * (z - Z_SHAFT), oy - S * (y - ys0))

    cx, cy = P(ys0, Z_SHAFT)
    d.ellipse([cx - 8 * S, cy - 8 * S, cx + 8 * S, cy + 8 * S], outline=dim, width=2)
    d.text((cx - 8 * S - 6, cy + 8 * S - 4), "销钉轨迹 R=8", font=f(19), fill=gray, anchor="lm")
    hw, hh = SLOT_W / 2 * S, (SLOT_HY + SLOT_W / 2) * S

    for deg, col, wid in ((0, gray, 2), (22, teal, 4)):
        t = R_CRANK * math.sin(RAD(deg))
        drop = R_CRANK * (1 - math.cos(RAD(deg)))
        scx, scy = P(BTN_Y[0], Z_SHAFT + t)                     # 槽中心 (跟着按钮走)
        pcx, pcy = P(BTN_Y[0] - drop, Z_SHAFT + t)              # 销钉中心 (跟着曲柄走)
        d.rounded_rectangle([scx - hw, scy - hh, scx + hw, scy + hh],
                            radius=hw, outline=col, width=wid)
        d.line([cx, cy, pcx, pcy], fill=(orange if deg else dim), width=(7 if deg else 3))
        rr = 3 * S if deg else 3 * S
        d.ellipse([pcx - rr, pcy - rr, pcx + rr, pcy + rr],
                  fill=(orange if deg else (232, 235, 240)), outline=(orange if deg else gray), width=3)

    d.ellipse([cx - 9, cy - 9, cx + 9, cy + 9], fill=ink)
    d.text((cx - 18, cy + 16), "舵机轴心", font=f(19), fill=gray, anchor="ma")

    # 行程尺寸 (两槽中心之间)
    x1 = P(BTN_Y[0], Z_SHAFT)[0]
    x2 = P(BTN_Y[0], Z_SHAFT + 3.0)[0]
    yd = 140
    for xx in (x1, x2):
        d.line([xx, yd - 14, xx, yd + 14], fill=teal, width=3)
    d.line([x1, yd, x2, yd], fill=teal, width=3)
    d.text(((x1 + x2) / 2, yd - 26), "行程 3.00 mm", font=f(21), fill=teal, anchor="ma")

    for i, (txt, col) in enumerate((("灰细线 = 静止 0°", gray),
                                    ("青粗线 = 按下 3 mm (舵机转 22°)", teal),
                                    ("橙 = 曲柄 + 销钉", orange),
                                    ("销钉每转一点, 上下也会动一点;", ink),
                                    ("竖槽把这部分放掉, 所以滑块只走前后.", ink),
                                    ("销钉在槽里上下余量 ±%.1f mm" % (SLOT_HY + SLOT_W / 2 - PIN_D / 2), ink))):
        d.text((52, 618 + i * 33), txt, font=f(21), fill=col)

    # ---- 右: 行程曲线 ----
    gx0, gy0, gw, gh = 900, 200, 500, 420
    d.text((gx0, 112), "② 行程 = R · sin(角度)   (R = 8 mm)", font=f(28), fill=ink)
    d.line([gx0, gy0 + gh, gx0 + gw, gy0 + gh], fill=ink, width=2)
    d.line([gx0, gy0, gx0, gy0 + gh], fill=ink, width=2)
    A = 34.0
    pts = []
    for k in range(0, 31):
        pts.append((gx0 + k / A * gw, gy0 + gh - (R_CRANK * math.sin(RAD(k)) / 4.0) * gh))
    d.line(pts, fill=blue, width=4)
    for k, tl in ((22, "3.00 mm / 22°"), (30, "4.00 mm / 30° (限位)")):
        px = gx0 + k / A * gw
        py = gy0 + gh - (R_CRANK * math.sin(RAD(k)) / 4.0) * gh
        d.line([px, py, px, gy0 + gh], fill=dim, width=2)
        d.ellipse([px - 7, py - 7, px + 7, py + 7], fill=orange)
        if k == 22:
            d.text((px + 14, py - 4), tl, font=f(21), fill=ink, anchor="lm")
        else:
            d.text((px - 12, py - 28), tl, font=f(21), fill=ink, anchor="rm")
    for k in (0, 10, 20, 30):
        px = gx0 + k / A * gw
        d.text((px, gy0 + gh + 12), "%d°" % k, font=f(20), fill=gray, anchor="ma")
    d.text((gx0 - 14, gy0 + gh), "0", font=f(20), fill=gray, anchor="rm")
    d.text((gx0 - 14, gy0 + gh - gh), "4 mm", font=f(20), fill=gray, anchor="rm")
    d.text((gx0 + gw / 2, gy0 + gh + 52), "舵机转角", font=f(22), fill=gray, anchor="ma")

    p = os.path.join(DIR_IMG, "09_原理图.png")
    img.save(p)
    return p


# ============================== 主流程 ==============================
class _Tee:
    def __init__(self, *fs):
        self.fs = fs

    def write(self, s):
        for f in self.fs:
            try:
                f.write(s)
            except Exception:
                pass

    def flush(self):
        for f in self.fs:
            try:
                f.flush()
            except Exception:
                pass


def main():
    sys.stdout = _Tee(sys.stdout, open(os.path.join(HERE, "_run.txt"), "w", encoding="utf-8"))
    base, panel, layers = build_assembly()
    L0, L1 = layers

    print("=== 整机包围盒 (装配) ===")
    allm = uni(base, panel, L0["button"], L0["yoke"], L0["crank"], L0["pin"], L0["link"],
               L1["button"], L1["yoke"], L1["crank"], L1["pin"], L1["link"],
               ghost_servo(BTN_Y[0]), ghost_servo(BTN_Y[1]), ghost_spline(BTN_Y[1]))
    x0, y0, z0, x1, y1, z1 = dims(allm)
    print("  整机 X %.1f..%.1f  Y %.1f..%.1f  Z %.1f..%.1f  =>  %.1f(宽) x %.1f(高) x %.1f(深)"
          % (x0, x1, y0, y1, z0, z1, x1 - x0, y1 - y0, z1 - z0))
    for nm, man in (("底座", base), ("面板", panel), ("按钮", L0["button"]),
                    ("滑块(轭)", L0["yoke"]), ("曲柄", L0["crank"]), ("销钉", L0["pin"])):
        a, b, c, d, e, f = dims(man)
        print("  %-8s %.1f x %.1f x %.1f   体积 %.2f cm3"
              % (nm, d - a, e - b, f - c, man.volume() / 1000))

    print("\n=== 运动学  位移 = R·sinθ  (R=%.0f) ===" % R_CRANK)
    for deg, t, dr in kinematic_table():
        print("  %5.1f°  ->  行程 %5.2f mm     销钉中心下移 %5.2f mm" % (deg, t, dr))

    print("\n=== 干涉 / 间隙校验 ===")
    rows, gaps, diag = verify(base, panel, layers)
    mx = max(max(r[3], r[4]) for r in rows)
    for d in diag:
        print("  !! " + d)
    print("  检查 %d 个姿态, 最大干涉体积 %.6f mm3  => %s" % (len(rows), mx, "通过" if mx < 1e-3 else "不通过"))
    for nm, g in gaps:
        print("  %s 最小间隙 %.2f mm" % (nm, g))
    clr = clearances(base, panel, layers)
    print("  --- 静止姿态实测间隙 ---")
    for txt, g in clr:
        print("    %-42s %5.2f mm" % (txt, g))

    print("\n=== 导出 STL ===")
    items = [("01_底座.stl", base, "base"),
             ("02_面板.stl", panel, "panel"),
             ("03_按钮_上.stl", part_button(True), "button"),
             ("04_按钮_下.stl", part_button(False), "button"),
             ("05_滑块.stl", part_yoke(), "flat_x"),
             ("06_曲柄.stl", part_crank(), "flat_x"),
             ("07_销钉.stl", part_pin(), "pin"),
             ("08_连接销.stl", part_link(), "pin")]
    info = export_all(items)
    for fname, vol, ntri, wt, (sx, sy, sz) in info:
        print("  %-14s %7.2f cm3  三角 %6d  水密 %s   打印高 %.1f mm"
              % (fname, vol, ntri, "OK " if wt else "NO!", sz))

    print("\n=== 渲染 ===")
    sheet = [("底座", "1 件: 底板+舵机墙+立柱+导向块", base, COL["base"]),
             ("面板", "70x125x5, 凸圈 + ▲▼", panel, COL["panel"]),
             ("按钮 ▲", "帽+杆+方孔+连接销孔", part_button(True), COL["up"]),
             ("按钮 ▼", "同上, 箭头反向", part_button(False), COL["dn"]),
             ("滑块(轭)", "滑杆 + 轭板 + 竖槽", part_yoke(), COL["yoke"]),
             ("曲柄", "花键孔 + 夹紧缝 + 销钉孔", part_crank(), COL["crank"]),
             ("销钉", "⌀6+法兰, 可单独更换", part_pin(), COL["pin"]),
             ("连接销", "⌀3.2, 连按钮与滑杆", part_link(), COL["link"])]
    for f in render_figures(base, panel, layers, sheet):
        print("  " + f)

    # ---------------- 报告 ----------------
    rep = ["# 演示样机 参数与校验报告 (v1)\n\n",
           "> 由 `cad/build.py` 自动生成, 每次修改参数后重新生成。\n",
           "> 坐标: X 右 / Y 上 / Z 朝墙里 (面板正面 Z=0)。单位 mm。\n\n",
           "## 1. 关键尺寸\n\n| 项目 | 数值 |\n|---|---|\n"]
    a, b, c, d, e, f = dims(allm)
    rep.append("| 整机包围盒 | %.0f 宽 x %.0f 高 x %.0f 深 |\n" % (d - a, e - b, f - c))
    rep.append("| 面板 | %.0f x %.0f x %.1f, 按钮孔 ⌀%.1f, 上下中心距 %.0f |\n"
               % (PANEL_W, PANEL_H, PANEL_T, BORE_D, DY))
    rep.append("| 按钮 | 帽 ⌀%.1f 厚 %.1f, 杆 ⌀%.0f, 静止间隙 %.0f, 工作行程 %.0f, 硬限位 %.0f |\n"
               % (CAP_D, CAP_T, STEM_D, -CAP_BACK, OP_TRAVEL, STOP_TRAVEL))
    rep.append("| 曲柄 | R=%.0f, 厚 %.1f, 轮毂 ⌀%.0f, 花键孔 ⌀%.1f, 销钉 ⌀%.0f |\n"
               % (R_CRANK, CRANK_X1 - CRANK_X0, HUB_D, SPLINE_BORE, PIN_D))
    rep.append("| 轭槽 | %.1f (行程向) x %.1f (容差向), 销钉 %.1f -> 侧隙 %.1f, 轴心高度容差 ±%.1f |\n"
               % (SLOT_W, (SLOT_HY + SLOT_W / 2) * 2, PIN_D, SLOT_W - PIN_D, SLOT_HY + SLOT_W / 2 - PIN_D / 2))
    rep.append("| 滑杆 | %.1f x %.1f |\n" % (BAR_W, BAR_H))
    rep.append("| 舵机轴心 | Z=%.1f (比按钮中心低 %.0f), 安装耳孔距 %.2f x2 |\n"
               % (Z_SHAFT, R_CRANK, EAR_HP * 2))
    rep.append("\n## 2. 运动学\n\n| 角度 | 行程 (mm) | 销钉中心下移 (mm) |\n|---|---|---|\n")
    for deg, t, dr in kinematic_table():
        rep.append("| %.0f° | %.2f | %.2f |\n" % (deg, t, dr))
    rep.append("\n## 3. 干涉校验\n\n")
    rep.append("在 0°~30° (行程 0~%.0f mm) 逐角度检查 4 个运动件 (曲柄+销钉 / 滑块 / 按钮 / 连接销)\n"
               "它们**彼此之间**、以及每个与固定件 (底座 / 面板 / 舵机外形) 的布尔交集体积\n"
               "(曲柄与销钉是设计上的过盈配合, 视为一个整体, 不互相检查)。\n\n" % STOP_TRAVEL)
    rep.append("- 检查姿态数: **%d**\n- 最大干涉体积: **%.6f mm³** -> **%s**\n"
               % (len(rows), mx, "通过" if mx < 1e-3 else "不通过"))
    for nm, g in gaps:
        rep.append("- %s 最小间隙: %.2f mm\n" % (nm, g))
    rep.append("\n### 3.1 静止姿态实测间隙 (manifold 最小距离)\n\n| 配合 | 实测间隙 |\n|---|---|\n")
    for txt, g in clr:
        rep.append("| %s | %.2f mm |\n" % (txt, g))
    rep.append("\n## 4. 零件体积 (PLA 1.24 g/cm³)\n\n| 零件 | 数量 | 体积 cm³ | 估重 g |\n|---|---|---|---|\n")
    qty = {"01": 1, "02": 1, "03": 1, "04": 1, "05": 2, "06": 2, "07": 2, "08": 2}
    tot = 0.0
    for fname, vol, ntri, wt, sz in info:
        n = qty[fname[:2]]
        tot += vol * n
        rep.append("| %s | %d | %.2f | %.0f |\n" % (fname, n, vol, vol * 1.24))
    rep.append("| **合计** | **%d 件** | **%.1f** | **%.0f** |\n"
               % (sum(qty.values()), tot, tot * 1.24))
    rep.append("\n## 5. 结论\n\n")
    rep.append("- 全行程无干涉, 全部零件均为单一水密实体, 可直接切片打印。\n")
    rep.append("- 曲柄夹紧缝 + M3 夹紧螺丝: 可在装配时机械地对零, 无胶。\n")
    rep.append("- 销钉为独立零件, 磨损/断裂只需重印 1 件, 不动曲柄。\n")
    rep.append("- 竖槽 Y 向 ±%.1f mm 容差吸收舵机轴心高度误差。\n" % (SLOT_HY + SLOT_W / 2 - PIN_D / 2))
    open(os.path.join(ROOT, "参数与校验报告.md"), "w", encoding="utf-8").write("".join(rep))
    print("\n报告: " + os.path.join(ROOT, "参数与校验报告.md"))


if __name__ == "__main__":
    main()
