# -*- coding: utf-8 -*-
"""
趋势折线图生成：用 Pillow 把月报的折线图渲染成 PNG，
供邮件 HTML 以 <img src="cid:..."> 内嵌展示（经典版 Outlook 支持 cid 内嵌图）。

依赖：Pillow（单个轻量包）+ 随插件打包的 SimHei 字体。
返回 [(content_id, png_bytes, "png"), ...]

half=True：用于"并排"展示的图（如 CPU/内存 1×2），画布较窄、字号更大，
保证在邮件里半宽展示时依然清晰。
"""
import io
import math
import os

from PIL import Image, ImageDraw, ImageFont

_FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_assets", "simhei.ttf")

_PAL = {
    "primary": (26, 54, 93),
    "accent": (74, 111, 165),
    "warn": (192, 86, 33),
    "danger": (197, 48, 48),
    "muted": (113, 128, 150),
    "grid": (237, 240, 244),
    "green": (104, 160, 133),
    "darkgreen": (45, 106, 79),
}

_GOLD = (214, 158, 46)  # #d69e2e


def _font(size):
    return ImageFont.truetype(_FONT_PATH, size)


def _dashed_line(draw, points, color, width, dash=8, gap=6):
    pts = list(points)
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        dx, dy = x2 - x1, y2 - y1
        seg = (dx * dx + dy * dy) ** 0.5
        if seg == 0:
            continue
        n = int(seg / (dash + gap)) + 1
        for k in range(n):
            t0 = k * (dash + gap) / seg
            t1 = min(t0 + dash / seg, 1.0)
            if t1 <= t0:
                continue
            draw.line((x1 + dx * t0, y1 + dy * t0, x1 + dx * t1, y1 + dy * t1),
                      fill=color, width=width)


def _smooth(points, tension=0.3, samples=16):
    """Catmull-Rom 平滑曲线（对齐原版 Chart.js tension:0.3）。"""
    if len(points) < 3:
        return points
    # Catmull-Rom 在 u=0 时给出 p1 而非 p0，因此显式保留首点
    out = [points[0]]
    for i in range(len(points) - 1):
        p0 = points[max(i - 1, 0)]
        p1 = points[i]
        p2 = points[i + 1]
        p3 = points[min(i + 2, len(points) - 1)]
        # t 从 1 到 samples，避免 u=0（即 p1，已被上一段覆盖）并到达 u=1（精确 p2）
        for t in range(1, samples + 1):
            u = t / samples
            u2 = u * u
            u3 = u2 * u
            x = ((2 * p1[0]) + (-p0[0] + p2[0]) * u +
                 (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * u2 +
                 (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * u3) * 0.5
            y = ((2 * p1[1]) + (-p0[1] + p2[1]) * u +
                 (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * u2 +
                 (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * u3) * 0.5
            out.append((x, y))
    # 最后一段的 u=1 已精确到达 points[-1]，无需再 append
    return out


def _line_chart(title, x_labels, series, y_min, y_max, y_unit="",
                data_labels=False, legend=False, half=False, w=920, x_step=1, x_angle=0,
                tick_step=None):
    """series: [(名称, 颜色RGB, [数值], 是否虚线), ...]
    高分辨率渲染：画布加大、线条加粗、字体放大，保证清晰度。"""
    if half:
        W, H = 800, 560
        ML, MR, MT, MB = 72, 24, 36, 56
        F = dict(title=0, tick=24, xl=26, lg=26, dl=24)  # title=0 表示不画内部标题
    else:
        W, H = w, 500
        s = w / 1100.0
        ML, MR, MT, MB = int(78 * s), int(28 * s), int(48 * s), int(52 * s)
        if x_angle:
            MB += 40  # 倾斜标签需要更多底部空间
        F = dict(title=int(30 * s), tick=int(20 * s), xl=int(22 * s), lg=int(22 * s), dl=int(20 * s))

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    x0, x1, y0, y1 = ML, W - MR, MT, H - MB
    n = len(x_labels)
    xs = [x0 + (x1 - x0) * i / (n - 1) if n > 1 else (x0 + x1) / 2 for i in range(n)]

    def py(v):
        r = y1 - (v - y_min) / (y_max - y_min) * (y1 - y0) if y_max != y_min else y1
        return max(y0, min(y1, r))

    title_font = _font(F["title"]) if F["title"] else None
    tick_font = _font(F["tick"])
    xl_font = _font(F["xl"])
    lg_font = _font(F["lg"])
    dl_font = _font(F["dl"])

    if title_font:
        d.text(((W - d.textlength(title, font=title_font)) / 2, 6), title,
               font=title_font, fill=_PAL["primary"])

    # 水平网格 + Y 刻度（tick_step 指定步长则按步长，否则 5 等分）
    if tick_step:
        ticks = []
        v = y_min
        while v <= y_max + 1e-6:
            ticks.append(v)
            v += tick_step
    else:
        ticks = [y_min + (y_max - y_min) * k / 5 for k in range(6)]
    for v in ticks:
        yy = py(v)
        d.line((x0, yy, x1, yy), fill=_PAL["grid"], width=1)
        label = "%g" % v
        d.text((x0 - 10 - d.textlength(label, font=tick_font), yy - 10),
               label, font=tick_font, fill=_PAL["muted"])
    if y_unit:
        d.text((x0 + 6, y0 + 4), y_unit, font=_font(15), fill=_PAL["muted"])

    # X 轴标签（x_step 控制隔几个显示，最后一个总是显示；x_angle 倾斜避免拥挤）
    for i, (x, lab) in enumerate(zip(xs, x_labels)):
        if i % x_step != 0 and i != n - 1:
            continue
        if x_angle:
            bbox = xl_font.getbbox(lab)
            tw = d.textlength(lab, font=xl_font)
            th = (bbox[3] - bbox[1]) + 8
            tmp = Image.new("RGBA", (int(tw) + 8, int(th) + 8), (255, 255, 255, 0))
            td = ImageDraw.Draw(tmp)
            td.text((4, 4 - bbox[1]), lab, font=xl_font, fill=_PAL["muted"])
            tmp = tmp.rotate(x_angle, expand=True)
            img.paste(tmp, (int(x - tmp.width / 2), y1 + 6), tmp)
        else:
            tw = d.textlength(lab, font=xl_font)
            d.text((x - tw / 2, y1 + 8), lab, font=xl_font, fill=_PAL["muted"])

    # 各条线：平滑曲线 + 加粗线条 + 清晰数据点
    for entry in series:
        name, color, values = entry[0], entry[1], entry[2]
        dashed = entry[3] if len(entry) > 3 else False
        fill_color = entry[4] if len(entry) > 4 else None
        pts = [(x, py(v)) for x, v in zip(xs, values)]

        # 填充区域（在曲线下方与 x 轴之间）
        if fill_color and len(pts) >= 2:
            smooth_pts = _smooth(pts)
            poly = list(smooth_pts) + [(x1, y1), (x0, y1)]
            d.polygon(poly, fill=fill_color)

        # 平滑曲线（粗线）
        line_w = 3
        dash_w = 2
        if len(pts) >= 3:
            smooth_pts = _smooth(pts)
            if dashed:
                _dashed_line(d, smooth_pts, color, dash_w)
            else:
                for i in range(len(smooth_pts) - 1):
                    d.line([smooth_pts[i], smooth_pts[i + 1]], fill=color, width=line_w)
        elif len(pts) == 2:
            if dashed:
                _dashed_line(d, pts, color, dash_w)
            else:
                d.line(pts, fill=color, width=line_w)

        # 数据点（加粗圆点 + 白色描边）
        r = 4
        for x, v in zip(xs, values):
            yy_v = py(v)
            d.ellipse((x - r, yy_v - r, x + r, yy_v + r), fill=color, outline="white")

    # 数据数值标注（每个点；白色描边避免被线条/点干扰；水平钳制避免撞 y 轴刻度）
    if data_labels:
        for entry in series:
            name, color, values = entry[0], entry[1], entry[2]
            for x, v in zip(xs, values):
                yy = py(v)
                lab = "%g" % v
                tw = d.textlength(lab, font=dl_font)
                lx = min(max(x, x0 + tw / 2), x1 - tw / 2)
                for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    d.text((lx - tw / 2 + ox, yy - 20 + oy), lab, font=dl_font, fill="white")
                d.text((lx - tw / 2, yy - 20), lab, font=dl_font, fill=_PAL["muted"])

    # 图例（右上角）
    if legend:
        lx = x1
        for entry in reversed(series):
            name, color = entry[0], entry[1]
            tw = d.textlength(name, font=lg_font)
            d.line((lx - tw - 34, y0 + 8, lx - tw - 8, y0 + 8), fill=color, width=5)
            d.text((lx - tw, y0 - 6), name, font=lg_font, fill=_PAL["primary"])
            lx -= (tw + 50)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _nice_scale(vmax):
    """Chart.js 风格的自动 nice 刻度：返回 (轴最大值, 步长)，刻度为整数。"""
    if vmax <= 0:
        return 100, 25
    raw_step = vmax / 5.0
    exp = math.floor(math.log10(raw_step))
    base = 10 ** exp
    step = None
    for m in (1, 2, 2.5, 5, 10):
        if raw_step <= m * base:
            step = m * base
            break
    if step is None:
        step = 10 * base
    axis_max = math.ceil(vmax / step) * step
    return axis_max, int(step)


def _hbar_chart(title, categories, series, colors, x_max, x_unit,
                bar_mode="single", legend_items=None, tick_step=None, row_h=34):
    """横向条形图（原版 Chart.js 风格：左侧分类名 + y 轴线，底部 x 轴/刻度/网格线）。
    bar_mode: single 单色柱 / stacked 堆叠柱 / grouped 分组柱。
    legend_items: [(名称, 颜色RGB), ...]，画在底部。
    tick_step: x 轴刻度步长（对齐原版 stepSize）。
    row_h: 每行高度（用于同一栏两张图等高）。"""
    n = len(categories)
    W = 760  # 加宽画布，条形图更宽
    top = 40
    bottom = 46 + (30 if legend_items else 0)
    H = top + n * row_h + bottom

    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    title_font = _font(20)
    cat_font = _font(20)
    tick_font = _font(14)

    # 标题
    d.text(((W - d.textlength(title, font=title_font)) / 2, 6), title,
           font=title_font, fill=_PAL["primary"])

    # 左栏宽度 = 最长分类名 + 间距
    left = max([d.textlength(c, font=cat_font) for c in categories] + [0]) + 16
    x0, x1 = left, W - 10
    y0, y1 = top, H - bottom

    # 垂直网格线 + x 刻度（tick_step 指定步长则按步长，否则 4 等分）
    if tick_step:
        ticks = list(range(0, int(x_max) + 1, tick_step))
        if not ticks or ticks[-1] < x_max:
            ticks.append(x_max)
    else:
        ticks = [x_max * k / 4 for k in range(5)]
    for v in ticks:
        xx = x0 + (x1 - x0) * v / x_max
        d.line((xx, y0, xx, y1), fill=_PAL["grid"], width=1)
        lab = "%g" % v
        d.text((xx - d.textlength(lab, font=tick_font) / 2, y1 + 4), lab,
               font=tick_font, fill=_PAL["muted"])
    # x 轴线 + y 轴线
    d.line((x0, y1, x1, y1), fill=_PAL["accent"], width=2)
    d.line((x0, y0, x0, y1), fill=_PAL["accent"], width=2)
    # 单位（放 y 轴上方）
    if x_unit:
        d.text((x0 + 4, y0 - 16), x_unit, font=tick_font, fill=_PAL["muted"])

    # 分类名 + 条形
    for i, cat in enumerate(categories):
        cy = y0 + (i + 0.5) * row_h
        tw = d.textlength(cat, font=cat_font)
        bbox = cat_font.getbbox(cat)
        d.text((x0 - 8 - tw, cy - (bbox[3] - bbox[1]) / 2 - bbox[1]),
               cat, font=cat_font, fill=_PAL["primary"])
        hb = row_h * 0.40  # 柱体加粗（占行高 80%）
        if bar_mode == "single":
            w = (x1 - x0) * series[i] / x_max
            d.rectangle([x0, cy - hb, x0 + w, cy + hb], fill=colors[0])
        elif bar_mode == "stacked":
            cx = x0
            for sv, sc in zip(series[i], colors):
                if sv <= 0:
                    continue
                w = (x1 - x0) * sv / x_max
                d.rectangle([cx, cy - hb, cx + w, cy + hb], fill=sc)
                cx += w
        elif bar_mode == "grouped":
            k = len(colors)
            bw = min(row_h * 0.26, 12)
            for j, (sv, sc) in enumerate(zip(series[i], colors)):
                w = (x1 - x0) * sv / x_max
                y_top = cy - (k - 1) * bw / 2 + j * bw
                d.rectangle([x0, y_top, x0 + w, y_top + bw], fill=sc)

    # 图例（底部）
    if legend_items:
        lg_y = y1 + 32
        lx = x0
        for name, color in legend_items:
            tw = d.textlength(name, font=tick_font)
            d.line((lx, lg_y, lx + 22, lg_y), fill=color, width=3)
            d.text((lx + 28, lg_y - 8), name, font=tick_font, fill=_PAL["primary"])
            lx += 28 + tw + 16

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_charts(data):
    cd = data.get("computer") or {}
    mt = data.get("monthlyTrend") or []
    charts = []

    # 1. 近一年电脑总数趋势（整行，纯折线无填充）
    trend = cd.get("trend") or []
    if trend:
        x = [t.get("month", "") for t in trend]  # 保持 2025-08 格式
        y = [t.get("total", 0) for t in trend]
        lo = 8400  # 对齐原版 y min:8400
        hi = 9600  # max 取 nice 值（原版自动，此处用 9600）
        charts.append(("chart_computer", _line_chart(
            "近一年电脑总数趋势", x,
            [("电脑总数", _PAL["accent"], y, False)],
            lo, hi, "台", data_labels=True, w=1380, x_angle=45), "png"))

    # 2. CPU 占用走势（并排半宽）
    if mt:
        x = [m.get("month", "") for m in mt]
        charts.append(("chart_cpu", _line_chart(
            "CPU 占用走势", x,
            [("应用CPU", _PAL["green"], [m.get("appCpu", 0) for m in mt], True),
             ("整体CPU", _PAL["accent"], [m.get("physCpu", 0) for m in mt], False)],
            0, 30, "%", legend=True, half=True, tick_step=10, data_labels=True), "png"))

    # 3. 内存占用走势（并排半宽）
    if mt:
        x = [m.get("month", "") for m in mt]
        charts.append(("chart_mem", _line_chart(
            "内存占用走势", x,
            [("应用内存", _PAL["darkgreen"], [m.get("appMem", 0) for m in mt], True),
             ("整体内存", _PAL["warn"], [m.get("physMem", 0) for m in mt], False)],
            0, 80, "%", legend=True, half=True, tick_step=20, data_labels=True), "png"))

    # 4. 存储剩余空间（整行，纯折线无填充）
    if mt:
        x = [m.get("month", "") for m in mt]
        y = [m.get("storageFree", 0) for m in mt]
        lo = int(min(y) / 50) * 50
        hi = int((max(y) + 60) / 50) * 50
        charts.append(("chart_storage", _line_chart(
            "存储剩余空间", x,
            [("剩余TB", _PAL["primary"], y, False)],
            lo, hi, "TB", data_labels=True), "png"))

    # ---- 条形图：先收集数据，再按同一排最大行数统一高度 ----
    ROW_1 = 50  # 一级部门（行少，用大行高）
    ROW_2 = 20  # 一人多台/厂区（行多，用小行高，避免图太高）

    # 5. 准备 dept_adoption 数据
    dept_usage = cd.get("deptUsage") or []
    adoption_data = []
    overall = cd.get("rateUsageOverall", 0) or 0
    if dept_usage and overall:
        adoption_data = sorted([d for d in dept_usage if (d.get("rate", 0) or 0) < overall],
                               key=lambda d: d.get("rate", 0), reverse=True)

    # 6. 准备 dept_age 数据
    AGE_KEYS = ["y3", "y4"]
    AGE_COLORS = [_GOLD, _PAL["warn"]]
    dept_age = cd.get("deptAge") or []
    age_data = sorted(dept_age, key=lambda d: sum(d.get(k, 0) or 0 for k in AGE_KEYS), reverse=True)[:10] if dept_age else []

    # 7. 准备 multi_device 数据
    M_KEYS = ["two", "three", "threePlus"]
    M_COLORS = [_PAL["accent"], _GOLD, _PAL["warn"]]
    multi = cd.get("multiDevice") or []
    multi_data = sorted(multi, key=lambda d: sum(d.get(k, 0) or 0 for k in M_KEYS), reverse=True) if multi else []

    # 8. 准备 factory_avail 数据
    F_KEYS = ["laptop", "desktop", "thin"]
    F_COLORS = [_PAL["accent"], _PAL["green"], _GOLD]
    factory = cd.get("factoryAvail") or []
    factory_data = sorted(factory, key=lambda d: sum(d.get(k, 0) or 0 for k in F_KEYS), reverse=True) if factory else []

    # 同一排图表统一高度：行多的用基准行高，行少的按比例加大
    sec1_rows = max(len(adoption_data), len(age_data), 1)
    sec2_rows = max(len(multi_data), len(factory_data), 1)

    # 5. 部门活跃使用率（与右图 age 同高）
    if adoption_data:
        cats = [d.get("dept", "") for d in adoption_data]
        vals = [d.get("rate", 0) for d in adoption_data]
        ov = float(overall)
        ov_str = str(int(ov)) if ov == int(ov) else ('%.1f' % ov).rstrip('0').rstrip('.')
        label_text = "活跃使用率（低于整体 %s%%）" % ov_str
        row_h1 = int(sec1_rows * ROW_1 / len(adoption_data))
        charts.append(("chart_dept_adoption", _hbar_chart(
            "部门活跃使用率（低于整体活跃使用率）", cats, vals, [_PAL["accent"]], 100, "%",
            bar_mode="single", tick_step=20, row_h=row_h1,
            legend_items=[(label_text, _PAL["accent"])]), "png"))

    # 6. 部门电脑使用年限（与左图 adoption 同高）
    if age_data:
        cats = [d.get("dept", "") for d in age_data]
        series = [[d.get(k, 0) or 0 for k in AGE_KEYS] for d in age_data]
        max_val = max((max(s) for s in series), default=1000)
        x_max = int((max_val + 99) / 100) * 100
        row_h1 = int(sec1_rows * ROW_1 / len(age_data))
        charts.append(("chart_dept_age", _hbar_chart(
            "部门电脑使用年限分布（3年及以上 · 总量 Top 10）", cats, series, AGE_COLORS, x_max, "",
            bar_mode="grouped", tick_step=100, row_h=row_h1,
            legend_items=[("3年", AGE_COLORS[0]), ("4年+", AGE_COLORS[1])]), "png"))

    # 7. 一人多台（与右图 factory 同高）
    if multi_data:
        cats = [d.get("dept", "") for d in multi_data]
        series = [[d.get(k, 0) or 0 for k in M_KEYS] for d in multi_data]
        row_h2 = int(sec2_rows * ROW_2 / len(multi_data))
        charts.append(("chart_multi", _hbar_chart(
            "一人多台（台）", cats, series, M_COLORS, 100, "",
            bar_mode="grouped", tick_step=20, row_h=row_h2,
            legend_items=[("2台", M_COLORS[0]), ("3台", M_COLORS[1]), ("3台+", M_COLORS[2])]), "png"))

    # 8. 厂区可用电脑（与左图 multi 同高）
    if factory_data:
        cats = [d.get("name", "") for d in factory_data]
        series = [[d.get(k, 0) or 0 for k in F_KEYS] for d in factory_data]
        max_val = max((max(s) for s in series), default=400)
        x_max = int((max_val + 49) / 50) * 50
        row_h2 = int(sec2_rows * ROW_2 / len(factory_data))
        charts.append(("chart_factory", _hbar_chart(
            "各厂区可用电脑库存（台）", cats, series, F_COLORS, x_max, "",
            bar_mode="grouped", tick_step=50, row_h=row_h2,
            legend_items=[("笔记本", F_COLORS[0]), ("台式机", F_COLORS[1]),
                          ("瘦客户机", F_COLORS[2])]), "png"))

    return charts
