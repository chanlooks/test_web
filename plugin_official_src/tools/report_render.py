# -*- coding: utf-8 -*-
"""
静态 HTML 月报渲染器（供 send_monthly_report 工具使用）。
与 report_email.py 逻辑一致，但趋势段（电脑总数 / CPU / 内存 / 存储）
改用 <img src="cid:chart_xxx"> 内嵌图片，由 charts.py 生成 PNG。

排版约定：服务器统计卡每行 4 张；服务器使用情况每行 2 张；
部门活跃/年限、一人多台/厂区 为两列并排（2×2）；折线图整行展示。
"""
import math

FONT = "'PingFang SC','Microsoft YaHei',Arial,sans-serif"


def fmt1(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if f.is_integer():
        return str(int(f))
    return ("%.1f" % f).rstrip('0').rstrip('.')


def fmt_bw(mbps):
    if mbps is None or mbps == '':
        return '-'
    try:
        f = float(mbps)
    except (TypeError, ValueError):
        return str(mbps)
    if f >= 1000:
        val = f / 1000
        s = ("%.1f" % val).rstrip('0').rstrip('.')
        return s + 'G'
    return str(int(round(f))) + 'M'


def clamp_pct(p):
    try:
        p = float(p)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(100.0, p))


def stat_card(tag, num, unit, sub='', high=False, note='', compact=False):
    top = '#c05621' if high else '#2c5282'
    num_color = '#c05621' if high else '#1a365d'
    note_color = '#c05621' if high else '#718096'
    note_html = f'<span style="font-size:10px;color:{note_color};font-weight:500"> {note}</span>' if note else ''
    sub_html = f'<div style="font-size:10px;color:#718096;margin-top:3px;line-height:1.5">{sub}</div>' if sub else ''
    pad = '8px 4px' if compact else '12px 8px'
    tag_fs = '10px' if compact else '11px'
    num_fs = '20px' if compact else '22px'
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr><td style="background-color:#f8fafc;border-top:2px solid {top};padding:{pad};'
        f'text-align:center;font-family:{FONT}">'
        f'<div style="font-size:{tag_fs};color:#718096">{tag}{note_html}</div>'
        f'<div style="font-size:{num_fs};font-weight:600;color:{num_color}">{num}'
        f'<span style="font-size:12px;color:#718096;font-weight:400"> {unit}</span></div>{sub_html}'
        f'</td></tr></table>'
    )


def bar(pct, fill, track='#edf0f4', h=13):
    p = clamp_pct(pct)
    rem = 100 - p
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr>'
        f'<td width="{p}%" bgcolor="{fill}" height="{h}" style="font-size:0;line-height:0">&nbsp;</td>'
        f'<td width="{rem}%" bgcolor="{track}" height="{h}" style="font-size:0;line-height:0">&nbsp;</td>'
        f'</tr></table>'
    )


def stacked(segments, track='#edf0f4', h=13):
    total_w = sum(s[0] for s in segments)
    rem = max(0.0, 100.0 - total_w)
    cells = []
    for w, c in segments:
        cells.append(f'<td width="{w}%" bgcolor="{c}" height="{h}" style="font-size:0;line-height:0">&nbsp;</td>')
    cells.append(f'<td width="{rem}%" bgcolor="{track}" height="{h}" style="font-size:0;line-height:0">&nbsp;</td>')
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr>{"".join(cells)}</tr></table>'
    )


def section_title(title, desc=''):
    html = (f'<div style="font-size:15px;font-weight:600;color:#1a365d;padding-left:10px;'
            f'border-left:3px solid #2c5282;">{title}</div>')
    if desc:
        html += f'<div style="font-size:12px;color:#718096;padding-left:13px;margin-top:2px;">{desc}</div>'
    return html


def legend(items):
    """items=[(颜色, 文案), ...] —— 色块用有色 span 包裹。"""
    cells = []
    for c, label in items:
        cells.append(f'<td><span style="font-size:11px;color:#2d3748;padding-right:12px;line-height:1.6;">'
                     f'<span style="color:{c}">&#9608;</span>&nbsp;{label}</span></td>')
    return (
        f'<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr>{"".join(cells)}</tr></table>'
    )


def bar_axis(max_val, unit=''):
    """条形图底部 x 轴刻度行。max_val 为最大值，unit 为单位（如 %）。"""
    ticks = [0, max_val / 4, max_val / 2, max_val * 3 / 4, max_val]
    cells = []
    for i, v in enumerate(ticks):
        lab = ('%g' % v) + unit
        align = 'left' if i < 4 else 'right'
        w = '25%' if i < 4 else ''
        cells.append(
            f'<td width="{w}" style="text-align:{align};font-size:10px;color:#718096;padding-top:3px">{lab}</td>'
        )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr>{"".join(cells)}</tr></table>'
    )


def bar_rows(data_rows, label_w=200, right_w=64, fs=12, axis_html=None):
    """通用条形行表格。data_rows=[(label, bar_html, right_text), ...]；axis_html 为底部 x 轴刻度行。"""
    rows = []
    for label, bar_html, right_text in data_rows:
        rows.append(
            f'<tr>'
            f'<td width="{label_w}" style="padding:4px 4px;font-size:{fs}px;color:#2d3748;line-height:1.4">{label}</td>'
            f'<td style="padding:4px 4px;">{bar_html}</td>'
            f'<td width="{right_w}" style="padding:4px 4px;font-size:{fs}px;color:#718096;text-align:right">{right_text}</td>'
            f'</tr>'
        )
    if axis_html:
        rows.append(
            f'<tr>'
            f'<td width="{label_w}" style="font-size:0;line-height:0">&nbsp;</td>'
            f'<td style="padding:0 4px;border-top:1px solid #a7b0bc;">{axis_html}</td>'
            f'<td width="{right_w}" style="font-size:0;line-height:0">&nbsp;</td>'
            f'</tr>'
        )
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'{"".join(rows)}</table>'
    )


def boxed_table(rows_html):
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        f'style="border-collapse:collapse;border:1px solid #dde1e8">{rows_html}</table>'
    )


def img_block(cid):
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr><td style="padding:8px 2px 2px;">'
        f'<img src="cid:{cid}" width="100%" border="0" '
        f'style="display:block;width:100%;height:auto;">'
        f'</td></tr></table>'
    )


def _panel(title, legend_html, bar_html, title_size=12):
    """两列布局里的一栏。"""
    legend_row = f'<tr><td style="padding:2px 4px 4px;">{legend_html}</td></tr>' if legend_html else ''
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr><td style="font-size:{title_size}px;color:#718096;padding:0 4px 3px;line-height:1.4">{title}</td></tr>'
        f'{legend_row}'
        f'<tr><td style="padding:0 4px 2px;">{bar_html}</td></tr>'
        f'</table>'
    )


def block_header(period, generated, source):
    return (
        f'<tr><td style="padding:26px 32px 18px;border-bottom:2px solid #1a365d;">'
        f'<div style="font-size:20px;font-weight:600;color:#1a365d;letter-spacing:.02em">'
        f'IT 基础设施资源月报 - {period}</div>'
        f'<div style="font-size:12px;color:#718096;margin-top:6px">'
        f'报告周期 {period}&nbsp;&nbsp;&middot;&nbsp;&nbsp;生成日期 {generated}&nbsp;&nbsp;&middot;&nbsp;&nbsp;{source}'
        f'</div></td></tr>'
    )


def block_summary_risks(summary, risks):
    sev_label = {'critical': '严重', 'high': '高危', 'medium': '关注', 'info': '提示'}
    sev_color = {'critical': '#c53030', 'high': '#c05621', 'medium': '#2c5282', 'info': '#718096'}
    order = ['critical', 'high', 'medium', 'info']
    risks_sorted = sorted(risks, key=lambda r: order.index(r.get('sev')) if r.get('sev') in order else len(order))

    html = f'<tr><td style="padding:26px 32px 0;">{section_title("本月概况与关注事项")}</td></tr>'
    if summary:
        paras = '<br>'.join(str(s) for s in summary)
        html += (
            f'<tr><td style="padding:12px 32px 0;">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
            f'<tr><td style="background-color:#f0f4f8;border-left:3px solid #2c5282;padding:14px 16px;'
            f'font-size:13px;line-height:1.7;color:#2d3748">{paras}</td></tr></table></td></tr>'
        )
    if risks:
        rows = []
        for r in risks_sorted:
            sev = r.get('sev', 'info')
            label = sev_label.get(sev, sev)
            color = sev_color.get(sev, '#718096')
            desc = f'<div style="font-size:12px;color:#718096;margin-top:1px">{r.get("desc", "")}</div>' if r.get('desc') else ''
            rows.append(
                f'<tr><td style="padding:11px 16px;border-bottom:1px solid #edf0f4;font-size:13px;line-height:1.6;">'
                f'<table cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
                f'<tr><td width="56" style="vertical-align:top;padding-right:10px;">'
                f'<span style="font-size:11px;font-weight:600;color:{color};white-space:nowrap">{label}</span></td>'
                f'<td style="vertical-align:top;"><span style="font-weight:600;color:#2d3748">{r.get("title", "")}</span>{desc}'
                f'</td></tr></table></td></tr>'
            )
        html += f'<tr><td style="padding:10px 32px 0;">{boxed_table("".join(rows))}</td></tr>'
    return html


def block_computer_overview(period, cd):
    desc = f'截至 {period}，电脑资产总览 {cd.get("total", 0)} 台，活跃使用率 {fmt1(cd.get("rateUsageOverall", 0))}%'

    # 可用电脑老旧资产计算（对齐浏览器版第5张卡）
    avail_age = cd.get('availAge') or []
    y4_total = sum(r.get('y4', 0) or 0 for r in avail_age)
    avail_total = cd.get('availTotal', 0)
    age_pct = (y4_total / avail_total * 100) if avail_total else 0
    age_sub_parts = []
    for r in avail_age:
        name = r.get('name', '')
        y4 = r.get('y4', 0) or 0
        if y4 > 0 and name != '其他':
            age_sub_parts.append(f'{name} {y4}')
    age_sub = ' · '.join(age_sub_parts) if age_sub_parts else '暂无老旧可用库存'

    cards = [
        stat_card('电脑资产总览', cd.get('total', 0), '台',
                  f'笔记本 {cd.get("laptopTotal", 0)} · 台式机 {cd.get("desktopTotal", 0)} · 瘦客户机 {cd.get("thinClientTotal", 0)}', compact=True),
        stat_card('领用数', cd.get('assignedTotal', 0), '台',
                  f'笔记本 {cd.get("assignedLaptop", 0)} · 台式机 {cd.get("assignedDesktop", 0)} · 瘦客户机 {cd.get("assignedThinClient", 0)}', compact=True),
        stat_card('库存数', cd.get('inventoryTotal', 0), '台',
                  f'可用 {cd.get("inventoryAvailable", 0)} · 预留 {cd.get("inventoryReserved", 0)} · 待报废 {cd.get("inventoryScrap", 0)}', compact=True),
        stat_card('可用电脑', cd.get('availTotal', 0), '台',
                  f'笔记本 {cd.get("availLaptop", 0)} · 台式机 {cd.get("availDesktop", 0)} · 瘦客户机 {cd.get("availThinClient", 0)}', compact=True),
        stat_card('可用电脑老旧资产', y4_total, '台', age_sub, True, '≥4年', compact=True),
    ]
    # 5 列布局（窄间距，防换行导致高度不一致）
    row = ''.join(f'<td width="20%" style="padding:2px;vertical-align:top">{c}</td>' for c in cards)
    return (
        f'<tr><td style="padding:26px 32px 0;">{section_title("电脑资产概览", desc)}</td></tr>'
        f'<tr><td style="padding:12px 26px 0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr>{row}</tr></table></td></tr>'
    )


def block_computer_usage(cd):
    """各类型电脑活跃使用率，对齐浏览器版 usage-cards 样式。"""
    def _usage_card(title, sub, rate, high=False):
        color = '#c05621' if high else '#2c5282'
        return (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
            f'<tr><td style="background-color:#f8fafc;border:1px solid #dde1e8;padding:14px 12px;">'
            f'<div style="font-size:13px;font-weight:600;color:#2d3748;margin-bottom:2px">{title}</div>'
            f'<div style="font-size:11px;color:#718096;margin-bottom:10px">{sub}</div>'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
            f'<tr><td style="border-top:1px solid #dde1e8;padding-top:8px;text-align:center">'
            f'<div style="font-size:20px;font-weight:600;color:{color}">{fmt1(rate)}%</div>'
            f'<div style="font-size:11px;color:#718096;margin-top:2px">活跃率</div>'
            f'</td></tr></table>'
            f'</td></tr></table>'
        )
    cards = [
        _usage_card('笔记本', '活跃使用率', cd.get('rateUsageLaptop', 0),
                    (cd.get('rateUsageLaptop', 0) or 0) < 60),
        _usage_card('台式机', '活跃使用率', cd.get('rateUsageDesktop', 0),
                    (cd.get('rateUsageDesktop', 0) or 0) < 60),
        _usage_card('整体活跃使用率',
                    f'{cd.get("onlineTotal", 0)} / {cd.get("usageAssignedTotal", 0)} 台',
                    cd.get('rateUsageOverall', 0),
                    (cd.get('rateUsageOverall', 0) or 0) < 60),
    ]
    row = ''.join(f'<td width="33%" style="padding:6px;vertical-align:top">{c}</td>' for c in cards)
    return (
        f'<tr><td style="padding:24px 32px 0;">{section_title("各类型电脑活跃使用率", "近1个月有使用的已领用电脑占比")}</td></tr>'
        f'<tr><td style="padding:12px 26px 0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr>{row}</tr></table></td></tr>'
    )


def block_dept_section(cd):
    """一级部门电脑活跃使用与使用年限：两张条形图并排（图片）。"""
    left = img_block("chart_dept_adoption") if cd.get('deptUsage') else ''
    right = img_block("chart_dept_age") if cd.get('deptAge') else ''
    if not left and not right:
        return ''
    return (
        f'<tr><td style="padding:26px 32px 0;">{section_title("一级部门电脑活跃使用与使用年限")}</td></tr>'
        f'<tr><td style="padding:8px 26px 0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr>'
        f'<td width="50%" style="vertical-align:top;padding:0 8px 0 0;">{left}</td>'
        f'<td width="50%" style="vertical-align:top;padding:0 0 0 8px;">{right}</td>'
        f'</tr></table></td></tr>'
    )


def block_multi_factory(cd):
    """一人多台与厂区可用电脑：两张条形图并排（图片）。"""
    left = img_block("chart_multi") if cd.get('multiDevice') else ''
    right = img_block("chart_factory") if cd.get('factoryAvail') else ''
    if not left and not right:
        return ''
    return (
        f'<tr><td style="padding:26px 32px 0;">{section_title("一人多台与厂区可用电脑")}</td></tr>'
        f'<tr><td style="padding:8px 26px 0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr>'
        f'<td width="50%" style="vertical-align:top;padding:0 8px 0 0;">{left}</td>'
        f'<td width="50%" style="vertical-align:top;padding:0 0 0 8px;">{right}</td>'
        f'</tr></table></td></tr>'
    )


def block_computer_trend(cd):
    trend = cd.get('trend') or []
    rng = ''
    if trend and len(trend) >= 1:
        first = str(trend[0].get('month', ''))
        last = str(trend[-1].get('month', ''))
        rng = f'（{first} – {last}）'
    return (
        f'<tr><td style="padding:26px 32px 0;">{section_title(f"近一年电脑总数趋势{rng}")}</td></tr>'
        f'<tr><td style="padding:12px 32px 0;">{img_block("chart_computer")}</td></tr>'
    )


def block_server_stats(d, storage_total, storage_pct, alloc_cpu, alloc_mem, alloc_storage, alloc_vms):
    stats = d.get('stats') or []
    cells = []
    for s in stats:
        computed = s.get('computed')
        num = s.get('num', 0)
        sub = ''
        if computed == 'storageTotal':
            num = int(storage_total)
        elif computed == 'storagePct':
            num = storage_pct
        elif computed == 'allocatableVMs':
            num = alloc_vms
        disp = fmt1(num) if (s.get('unit') == '%') else num
        cells.append(f'<td width="25%" style="padding:6px">'
                     f'{stat_card(s.get("tag", ""), disp, s.get("unit", ""), sub, bool(s.get("high")))}</td>')
    # 每行 4 张
    rows = []
    for i in range(0, len(cells), 4):
        rows.append('<tr>' + ''.join(cells[i:i + 4]) + '</tr>')
    return (
        f'<tr><td style="padding:26px 32px 0;">{section_title("服务器资源规模")}</td></tr>'
        f'<tr><td style="padding:12px 26px 0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'{"".join(rows)}</table></td></tr>'
    )


def block_server_usage(d):
    cards = d.get('serverUsage', {}).get('cards') or []
    cells = []
    for c in cards:
        cpu_high = (c.get('cpu', 0) or 0) >= 65
        mem_high = (c.get('mem', 0) or 0) >= 65
        cells.append(
            f'<td width="50%" style="padding:6px;vertical-align:top">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
            f'<tr><td style="background-color:#f8fafc;border:1px solid #dde1e8;padding:16px 18px;">'
            f'<div style="font-size:14px;font-weight:600;color:#2d3748">{c.get("title", "")}</div>'
            f'<div style="font-size:12px;color:#718096;margin-bottom:12px">{c.get("sub", "")}</div>'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
            f'<tr>'
            f'<td style="border-top:1px solid #dde1e8;padding-top:10px;text-align:center">'
            f'<div style="font-size:20px;font-weight:600;color:{"#c05621" if cpu_high else "#2c5282"}">{fmt1(c.get("cpu", 0))}%</div>'
            f'<div style="font-size:11px;color:#718096;margin-top:2px">CPU</div></td>'
            f'<td style="border-top:1px solid #dde1e8;padding-top:10px;border-left:1px solid #dde1e8;text-align:center">'
            f'<div style="font-size:20px;font-weight:600;color:{"#c05621" if mem_high else "#2c5282"}">{fmt1(c.get("mem", 0))}%</div>'
            f'<div style="font-size:11px;color:#718096;margin-top:2px">内存</div></td>'
            f'</tr></table></td></tr></table></td>'
        )
    rows = []
    for i in range(0, len(cells), 2):
        rows.append('<tr>' + ''.join(cells[i:i + 2]) + '</tr>')
    return (
        f'<tr><td style="padding:26px 32px 0;">{section_title("服务器使用情况", "CPU 和内存占用比例，数值越高表示用得越满")}</td></tr>'
        f'<tr><td style="padding:12px 26px 0;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'{"".join(rows)}</table></td></tr>'
    )


def block_server_trend():
    """服务器近 6 个月趋势：CPU 与内存并排（1×2），存储整行，对齐原版布局。"""
    def chart_block(title, cid):
        return (
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
            f'<tr><td style="font-size:12px;color:#718096;padding:6px 2px 0;">{title}</td></tr>'
            f'<tr><td style="padding:2px 2px 0;">{img_block(cid)}</td></tr>'
            f'</table>'
        )
    two_col = (
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr>'
        f'<td width="50%" style="vertical-align:top;padding:0 8px 0 0;">{chart_block("CPU 占用走势（%）", "chart_cpu")}</td>'
        f'<td width="50%" style="vertical-align:top;padding:0 0 0 8px;">{chart_block("内存占用走势（%）", "chart_mem")}</td>'
        f'</tr></table>'
    )
    return (
        f'<tr><td style="padding:26px 32px 0;">{section_title("服务器近 6 个月趋势")}</td></tr>'
        f'<tr><td style="padding:12px 32px 0;">'
        f'{two_col}'
        f'{chart_block("存储剩余空间（TB）", "chart_storage")}'
        f'</td></tr>'
    )


def block_storage(d):
    storage = d.get('storage') or []
    if not storage:
        return ''
    rows = []
    for s in storage:
        total = s.get('total', 0) or 0
        used = s.get('used', 0) or 0
        pct = s.get('pct')
        if pct is None or pct == '':
            pct = (used / total * 100) if total else 0
        pct = clamp_pct(pct)
        free = total - used
        fill = '#c53030' if pct >= 90 else ('#c05621' if pct >= 75 else '#4a6fa5')
        rows.append(
            f'<tr><td style="padding:12px 16px;border-bottom:1px solid #edf0f4">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
            f'<tr>'
            f'<td style="font-size:13px;color:#2d3748;font-weight:500">{s.get("name", "")}</td>'
            f'<td style="font-size:12px;color:#718096;text-align:right">已用 <strong style="color:#2d3748">{fmt1(pct)}%</strong>'
            f' &middot; 总量 {total} TB</td>'
            f'</tr>'
            f'<tr><td colspan="2" style="padding-top:8px">{bar(pct, fill, h=14)}</td></tr>'
            f'<tr>'
            f'<td style="font-size:11px;color:#718096;padding-top:4px">已用 {used} TB</td>'
            f'<td style="font-size:11px;color:#718096;padding-top:4px;text-align:right">剩余 {fmt1(free)} TB</td>'
            f'</tr>'
            f'</table></td></tr>'
        )
    return (
        f'<tr><td style="padding:26px 32px 0;">{section_title("存储")}</td></tr>'
        f'<tr><td style="padding:12px 32px 0;">{boxed_table("".join(rows))}</td></tr>'
    )


def block_network(d):
    nets = d.get('networkTop8') or []
    if not nets:
        return ''
    rows = []
    for n in nets:
        pct = clamp_pct(n.get('pct', 0))
        used = n.get('used')
        if used is None or used == '':
            used = round((n.get('bandwidth', 0) or 0) * (n.get('pct', 0) or 0) / 100)
        high = pct >= 70
        fill = '#c05621' if high else '#4a6fa5'
        rows.append(
            f'<tr><td style="padding:11px 16px;border-bottom:1px solid #edf0f4">'
            f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
            f'<tr>'
            f'<td style="font-size:13px;color:#2d3748">{n.get("name", "")}</td>'
            f'<td style="font-size:12px;color:#718096;text-align:right">带宽 {fmt_bw(n.get("bandwidth"))} &middot; '
            f'已用 {fmt_bw(used)} &middot; '
            f'<strong style="color:{"#c05621" if high else "#2d3748"}">{fmt1(pct)}%</strong></td>'
            f'</tr>'
            f'<tr><td colspan="2" style="padding-top:7px">{bar(pct, fill, h=8)}</td></tr>'
            f'</table></td></tr>'
        )
    return (
        f'<tr><td style="padding:26px 32px 0;">{section_title("网络线路（利用率 TOP 8）")}</td></tr>'
        f'<tr><td style="padding:12px 32px 0;">{boxed_table("".join(rows))}</td></tr>'
    )


def block_footnote(footnote):
    return (
        f'<tr><td style="padding:18px 32px 28px;">'
        f'<table width="100%" cellpadding="0" cellspacing="0" border="0" style="border-collapse:collapse">'
        f'<tr><td style="border-top:1px solid #dde1e8;font-size:11px;color:#718096;line-height:1.5;'
        f'padding-top:10px">{footnote}</td></tr></table></td></tr>'
    )


def render(data):
    D = data
    period = D.get('period', '')
    generated = D.get('generated', '')
    source = D.get('source', '')
    cd = D.get('computer') or {}

    storage_total = 0.0
    storage_used = 0.0
    for s in D.get('storage') or []:
        storage_total += float(s.get('total', 0) or 0)
        storage_used += float(s.get('used', 0) or 0)
    storage_pct = (storage_used / storage_total * 100) if storage_total else 0

    av = D.get('allocVm') or {}
    safety = float(av.get('safetyLine', 0) or 0)
    alloc_cpu = math.floor((float(av.get('cpuCoresTotal', 0) or 0)
                            * (safety - (float(av.get('cpuAllocPct', 0) or 0)) / 100))
                           / (float(av.get('vmCpu', 1) or 1)))
    alloc_mem = math.floor((float(av.get('memTotalTB', 0) or 0) * 1024
                            * (safety - (float(av.get('memUsagePct', 0) or 0)) / 100))
                           / (float(av.get('vmMemGB', 1) or 1)))
    alloc_storage = math.floor((float(av.get('storageTotalTB', 0) or 0) * 1024
                                * (safety - (float(av.get('storageUsagePct', 0) or 0)) / 100))
                               / (float(av.get('vmStorageGB', 1) or 1)))
    alloc_vms = min(alloc_cpu, alloc_mem, alloc_storage)

    parts = []
    parts.append(block_header(period, generated, source))
    parts.append(block_summary_risks(D.get('summary') or [], D.get('risks') or []))
    parts.append(block_computer_overview(period, cd))
    parts.append(block_computer_usage(cd))
    parts.append(block_dept_section(cd))
    parts.append(block_multi_factory(cd))
    if cd.get('trend'):
        parts.append(block_computer_trend(cd))
    parts.append(block_server_stats(D, storage_total, storage_pct,
                                    alloc_cpu, alloc_mem, alloc_storage, alloc_vms))
    parts.append(block_server_usage(D))
    if D.get('monthlyTrend'):
        parts.append(block_server_trend())
    parts.append(block_storage(D))
    parts.append(block_network(D))
    parts.append(block_footnote(D.get('footnote', '')))

    return (
        '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
        '<meta charset="UTF-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f'<title>IT 基础设施资源月报 - {period}</title>\n</head>\n'
        f'<body style="margin:0;padding:24px 0 40px;background-color:#eef1f5;font-family:{FONT};">\n'
        f'<table width="960" cellpadding="0" cellspacing="0" border="0" align="center" '
        f'style="border-collapse:collapse;background-color:#ffffff;width:960px;max-width:100%">\n'
        f'{"\n".join(parts)}\n'
        '</table>\n</body>\n</html>\n'
    )
