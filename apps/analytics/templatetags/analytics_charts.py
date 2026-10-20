"""
{% pie_chart title slices %} — server tomonida chiziladigan SVG donut-diagramma
(tashqi kutubxonasiz, oflayn ishlaydi). slices — [(nom, qiymat), ...].
Ranglar CSS o'zgaruvchilardan (--kh-s1 … --kh-s6) olinadi, ular
templates/analytics/statistika.html da yorug' va qorong'i mavzu uchun berilgan.
"""

import math

from django import template
from django.utils.html import format_html, format_html_join
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _

register = template.Library()

SIZE, R_OUT, R_IN = 180, 86, 54


def _point(r, angle):
    c = SIZE / 2
    return c + r * math.sin(angle), c - r * math.cos(angle)


def _arc(a0, a1):
    large = 1 if a1 - a0 > math.pi else 0
    x0, y0 = _point(R_OUT, a0)
    x1, y1 = _point(R_OUT, a1)
    x2, y2 = _point(R_IN, a1)
    x3, y3 = _point(R_IN, a0)
    return (f"M{x0:.2f},{y0:.2f} A{R_OUT},{R_OUT} 0 {large} 1 {x1:.2f},{y1:.2f} "
            f"L{x2:.2f},{y2:.2f} A{R_IN},{R_IN} 0 {large} 0 {x3:.2f},{y3:.2f} Z")


def _fmt(value):
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.2f}".replace(",", " ")
    return f"{int(value):,}".replace(",", " ")


@register.simple_tag
def pie_chart(title, slices, unit=""):
    slices = [(name, float(value)) for name, value in slices if value]
    if len(slices) > 6:  # 6 tadan ko'p rang o'qilmaydi — qolganini «Boshqa»ga
        slices = slices[:5] + [(_("Boshqa"), sum(v for _, v in slices[5:]))]
    total = sum(v for _, v in slices)
    head = format_html('<figure class="kh-pie"><figcaption>{}</figcaption>', title)
    if not total:
        return head + format_html('<div class="kh-pie-empty">{}</div></figure>', _("Ma’lumot yo‘q"))

    shapes, legend, angle = [], [], 0.0
    for i, (name, value) in enumerate(slices):
        color = f"var(--kh-s{i + 1})"
        pct = 100 * value / total
        tip = f"{name}: {_fmt(value)}{unit} ({pct:.1f}%)"
        if len(slices) == 1:
            shapes.append(format_html(
                '<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{col}" stroke-width="{w}"><title>{t}</title></circle>',
                c=SIZE / 2, r=(R_OUT + R_IN) / 2, col=color, w=R_OUT - R_IN, t=tip))
        else:
            end = angle + 2 * math.pi * value / total
            shapes.append(format_html('<path d="{}" fill="{}"><title>{}</title></path>', _arc(angle, end), color, tip))
            angle = end
        legend.append((color, name, _fmt(value) + unit, f"{pct:.1f}%"))

    svg = format_html(
        '<svg viewBox="0 0 {s} {s}" role="img" aria-label="{t}">{shapes}'
        '<text x="{c}" y="{c}" class="kh-pie-total" text-anchor="middle" dy="-2">{total}</text>'
        '<text x="{c}" y="{c}" class="kh-pie-sub" text-anchor="middle" dy="16">{jami}</text></svg>',
        s=SIZE, c=SIZE / 2, t=title, shapes=mark_safe("".join(shapes)), total=_fmt(total), jami=_("jami"))
    items = format_html_join(
        "", '<li><i style="background:{}"></i><span>{}</span><b>{}</b><em>{}</em></li>', legend)
    return head + format_html('<div class="kh-pie-body">{}<ul class="kh-legend">{}</ul></div></figure>', svg, items)
