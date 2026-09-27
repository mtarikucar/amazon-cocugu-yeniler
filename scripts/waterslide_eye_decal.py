"""Waterslide göz (iris) decal baskı dosyalarını üretir.

Decal şekli ve iris ölçüsü eye_decal_outline.py çıktısından (goz_konturlari.json)
gelir: her göz için kubbe yüzeyinin düzleme açınımı, montajda görünen bölge
ile kırpılmıştır. Sol ve sağ göz farklı şekillidir; ayrı decal olarak basılır.

Çıktılar (vektör geometri tek kaynaktan):
  - A4 baskı tabakası: PDF (DeviceCMYK), SVG, 1200 dpi PNG (şeffaf zemin = mürekkep yok)
  - Sol / sağ master dosyaları: PDF + SVG + 1200 dpi PNG
  - Baskıcı sipariş/şartname formu (PDF)

Göz parçası beyaz boyanır / beyaz reçineyle basılır; iris decal şeffaf
waterslide filme basılır. Parlama noktaları mürekkepsiz bırakılır, alttaki
beyaz yüzey buradan görünür; bu yüzden beyaz mürekkep gerekmez.

Kullanım: python scripts/waterslide_eye_decal.py <çıktı_klasörü> [mockup.png]
"""
import json
import math
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.colors import CMYKColor
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from shapely import affinity
from shapely.geometry import Point, Polygon, box

# --- Sipariş ve yerleşim parametreleri ---------------------------------------
ORDER_QTY = 200
PRODUCED_QTY = 230            # %15 üretim firesi dahil
DECAL_SPARE = 0.20            # decal uygulama firesi
PITCH_X, PITCH_Y = 7.8, 7.3   # mm, hücre adımı (en az 1.4 mm kesim payı)
COLS, ROWS = 24, 23           # 12 çift × 23 satır = 276 SOL + 276 SAĞ
LADDER = [0.94, 0.97, 1.00, 1.03, 1.06]   # prototip ölçek testi
LADDER_REPEAT = 2
SEG = 256
EYES = ["SOL", "SAG"]
EYE_TITLE = {"SOL": "SOL", "SAG": "SAĞ"}

# CMYK (0-1) ve önizleme RGB
PALETTE = {
    "limbus": ((0.50, 0.70, 0.80, 0.80), (30, 18, 11)),
    "pupil": ((0.70, 0.65, 0.60, 0.95), (12, 10, 9)),
    "ink": ((0.0, 0.0, 0.0, 1.0), (0, 0, 0)),
}
# İris: üstte koyu kahve, alta doğru sıcak/açık kahve (referans görsel)
IRIS_STOPS = [
    (0.00, (0.45, 0.70, 0.85, 0.70), (43, 24, 13)),
    (0.45, (0.40, 0.68, 0.90, 0.50), (74, 42, 20)),
    (0.75, (0.28, 0.62, 0.95, 0.28), (122, 74, 34)),
    (1.00, (0.20, 0.55, 0.95, 0.12), (156, 102, 48)),
]
IRIS_BANDS = 14

FONT = "DejaVu"
pdfmetrics.registerFont(TTFont(FONT, "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont(FONT + "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))

CONTOURS = {}


def load_contours(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    for k in EYES:
        CONTOURS[k] = data[k]


def circle(x, y, r):
    return Point(x, y).buffer(r, quad_segs=SEG // 4)


def lerp_stop(t):
    for (t0, c0, r0), (t1, c1, r1) in zip(IRIS_STOPS, IRIS_STOPS[1:]):
        if t <= t1:
            w = (t - t0) / (t1 - t0)
            return (tuple(a + (b - a) * w for a, b in zip(c0, c1)),
                    tuple(round(a + (b - a) * w) for a, b in zip(r0, r1)))
    return IRIS_STOPS[-1][1], IRIS_STOPS[-1][2]


def decal_layers(eye, scale=1.0):
    """Decal katmanları: [(cmyk, rgb, geometri)] — mm, y yukarı, bbox merkezi (0,0).

    Katmanlar sırayla üst üste boyanır (sonraki öncekini örter); hepsi göz
    konturuyla kırpılır, parlama noktaları tüm katmanlardan çıkarılır (mürekkepsiz).
    """
    info = CONTOURS[eye]
    outline = Polygon(info["decal_kontur_mm"])
    cx, cy = info["acinim_iris_merkezi_mm"]
    r = info["acinim_iris_yaricapi_mm"]
    pupil = circle(cx, cy, 0.46 * r)
    highlights = circle(cx - 0.33 * r, cy + 0.30 * r, 0.17 * r).union(
        circle(cx + 0.36 * r, cy - 0.30 * r, 0.075 * r))
    limbus = circle(cx, cy, r + 0.4).difference(circle(cx, cy, r - 0.22))
    iris_disk = circle(cx, cy, r + 0.4)
    # Bantlar yukarıdan aşağı üst üste boyanır: her bant irisin altına kadar uzanır,
    # sonraki bant öncekinin üstünü örter. Böylece bant sınırlarında kılcal boşluk olmaz.
    layers = []
    for i in range(IRIS_BANDS):
        y_top = cy + r - 2 * r * i / IRIS_BANDS
        band = box(cx - r - 1, cy - r - 1, cx + r + 1, y_top) if i else iris_disk
        cm, rgbv = lerp_stop((i + 0.5) / IRIS_BANDS)
        layers.append((cm, rgbv, iris_disk.intersection(band)))
    layers.append((*PALETTE["limbus"], limbus))
    layers.append((*PALETTE["pupil"], pupil))
    minx, miny, maxx, maxy = outline.bounds
    ox, oy = (minx + maxx) / 2, (miny + maxy) / 2
    out = []
    for cm, rgbv, g in layers:
        g = g.intersection(outline).difference(highlights)
        g = affinity.translate(g, -ox, -oy)
        if scale != 1.0:
            g = affinity.scale(g, scale, scale, origin=(0, 0))
        if not g.is_empty:
            out.append((cm, rgbv, g))
    return out


def decal_outline(eye, scale=1.0):
    outline = Polygon(CONTOURS[eye]["decal_kontur_mm"])
    minx, miny, maxx, maxy = outline.bounds
    g = affinity.translate(outline, -(minx + maxx) / 2, -(miny + maxy) / 2)
    return affinity.scale(g, scale, scale, origin=(0, 0))


def polys(g):
    if g.is_empty:
        return []
    if g.geom_type == "Polygon":
        return [g]
    return [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]


# --- PDF ---------------------------------------------------------------------
def pdf_geom(c, g, dx, dy):
    for p in polys(g):
        path = c.beginPath()
        for ring in [p.exterior, *p.interiors]:
            pts = list(ring.coords)
            path.moveTo((dx + pts[0][0]) * mm, (dy + pts[0][1]) * mm)
            for x, y in pts[1:]:
                path.lineTo((dx + x) * mm, (dy + y) * mm)
            path.close()
        c.drawPath(path, stroke=0, fill=1, fillMode=1)  # even-odd


def pdf_decal(c, layers, x, y):
    for cm, _, g in layers:
        c.setFillColor(CMYKColor(*cm))
        pdf_geom(c, g, x, y)


def text_pdf(c, x, y, s, size=6, bold=False, anchor="start"):
    c.setFillColor(CMYKColor(*PALETTE["ink"][0]))
    c.setFont(FONT + ("B" if bold else ""), size)
    fn = {"start": c.drawString, "middle": c.drawCentredString, "end": c.drawRightString}[anchor]
    fn(x * mm, y * mm, s)


# Tabaka yerleşimi A4 dikey, y aşağıdan yukarı (mm)
PAGE_W, PAGE_H = 210.0, 297.0
GRID_W, GRID_H = COLS * PITCH_X, ROWS * PITCH_Y
GRID_X0 = (PAGE_W - GRID_W) / 2 + PITCH_X / 2
GRID_TOP = PAGE_H - 34.0
LADDER_Y = GRID_TOP - GRID_H - 18.0
SCALE_Y = LADDER_Y - 32.0


def grid_cells():
    for r in range(ROWS):
        for col in range(COLS):
            yield EYES[col % 2], GRID_X0 + col * PITCH_X, GRID_TOP - PITCH_Y / 2 - r * PITCH_Y


def ladder_cells():
    x = 20.0
    for s in LADDER:
        for _ in range(LADDER_REPEAT):
            for eye in EYES:
                yield eye, s, x, LADDER_Y
                x += PITCH_X
        x += 3.0


def per_eye_count():
    return COLS * ROWS // 2


def sheet_annotations():
    n = per_eye_count()
    need = PRODUCED_QTY
    items = [
        ("text", (PAGE_W / 2, PAGE_H - 11, "AMAZON ÇOCUĞU — WATERSLIDE GÖZ (İRİS) DECAL · SOL / SAĞ", 9, True, "middle")),
        ("text", (PAGE_W / 2, PAGE_H - 16,
                  f"{PRODUCED_QTY} figür → {need} SOL + {need} SAĞ gerekli · tabakada {n} SOL + {n} SAĞ (+%{round((n - need) / need * 100)} yedek)"
                  "  ·  ŞEFFAF waterslide film  ·  %100 ÖLÇEK", 6.2, False, "middle")),
        ("text", (PAGE_W / 2, PAGE_H - 20.5,
                  "Şekiller STL'den hesaplanmış göz açıklığıdır — döndürmeyin/aynalamayın. Parlama noktaları bilerek mürekkepsizdir.",
                  5.6, False, "middle")),
    ]
    for col in range(COLS):
        x = GRID_X0 + col * PITCH_X
        items.append(("text", (x, GRID_TOP + 1.6, EYE_TITLE[EYES[col % 2]], 3.6, True, "middle")))
    for col in range(0, COLS + 1, 2):
        x = GRID_X0 - PITCH_X / 2 + col * PITCH_X
        ln = 2.5 if col % 4 == 0 else 1.2
        items.append(("line", (x, GRID_TOP - GRID_H - 1.0, x, GRID_TOP - GRID_H - 1.0 - ln)))
    for r in range(ROWS + 1):
        y = GRID_TOP - r * PITCH_Y
        ln = 2.0 if r % 5 == 0 else 1.0
        items.append(("line", (GRID_X0 - PITCH_X / 2 - 1.0 - ln, y, GRID_X0 - PITCH_X / 2 - 1.0, y)))
        items.append(("line", (GRID_X0 - PITCH_X / 2 + GRID_W + 1.0, y, GRID_X0 - PITCH_X / 2 + GRID_W + 1.0 + ln, y)))
    items.append(("text", (PAGE_W / 2, GRID_TOP - GRID_H - 7.0,
                           f"Üretim ızgarası: {COLS // 2} çift × {ROWS} satır = {n} SOL + {n} SAĞ · hücre {PITCH_X} × {PITCH_Y} mm",
                           5.6, False, "middle")))
    items.append(("text", (15, LADDER_Y + 5.5,
                           "PROTOTİP ÖLÇEK TESTİ (SOL+SAĞ çiftleri) — ilk figürde deneyin, film kenarda taşarsa küçük ölçeği seçin:",
                           5.6, True, "start")))
    x = 20.0
    for s in LADDER:
        w = LADDER_REPEAT * 2 * PITCH_X
        items.append(("text", (x - PITCH_X / 2 + w / 2, LADDER_Y - 5.5, f"%{round(s * 100)}", 5.6, s == 1.0, "middle")))
        x += w + 3.0
    x0 = 15.0
    items.append(("line", (x0, SCALE_Y, x0 + 100, SCALE_Y)))
    for i in range(0, 101):
        h = 3.0 if i % 10 == 0 else (2.0 if i % 5 == 0 else 1.2)
        items.append(("line", (x0 + i, SCALE_Y, x0 + i, SCALE_Y + h)))
        if i % 10 == 0:
            items.append(("text", (x0 + i, SCALE_Y + 4.2, str(i), 4.5, False, "middle")))
    items.append(("text", (x0, SCALE_Y - 4.5, "ÖLÇEK KONTROLÜ: bu çizgi tam 100 mm, kare 10 × 10 mm olmalı.", 5.6, True, "start")))
    items.append(("rect", (130.0, SCALE_Y, 10.0, 10.0)))
    items.append(("text", (135.0, SCALE_Y - 4.5, "10 mm", 5.0, False, "middle")))
    s, g = CONTOURS["SOL"], CONTOURS["SAG"]
    items.append(("text", (15, 16,
                           f"İris (açınım): SOL Ø{2 * s['acinim_iris_yaricapi_mm']:.2f} mm · SAĞ Ø{2 * g['acinim_iris_yaricapi_mm']:.2f} mm  ·  "
                           f"kubbe tabanı SOL Ø{s['kubbe_taban_capi_mm']:.2f} / SAĞ Ø{g['kubbe_taban_capi_mm']:.2f} mm, "
                           f"yükseklik {s['kubbe_yuksekligi_mm']:.2f} / {g['kubbe_yuksekligi_mm']:.2f} mm", 4.8, False, "start")))
    items.append(("text", (15, 10, f"Dosya: GOZ_IRIS_DECAL_A4 · 230 adet üretim planı · {date.today().isoformat()} · "
                               "Kaynak: 16_Sol_Goz / 17_Sag_Goz (v2.0.0 STL), ARAP yüzey açınımı", 4.8, False, "start")))
    return items


def form_name(eye, s):
    return f"{eye}_{round(s * 100)}"


def build_sheet_pdf(path):
    c = canvas.Canvas(str(path), pagesize=(PAGE_W * mm, PAGE_H * mm))
    c.setTitle("Amazon Çocuğu — Waterslide göz decal A4")
    for eye in EYES:
        for s in {1.0, *LADDER}:
            c.beginForm(form_name(eye, s), lowerx=-4 * mm, lowery=-4 * mm, upperx=4 * mm, uppery=4 * mm)
            pdf_decal(c, decal_layers(eye, s), 0, 0)
            c.endForm()
    placements = [(e, 1.0, x, y) for e, x, y in grid_cells()] + list(ladder_cells())
    for eye, s, x, y in placements:
        c.saveState()
        c.translate(x * mm, y * mm)
        c.doForm(form_name(eye, s))
        c.restoreState()
    draw_annotations_pdf(c, sheet_annotations())
    c.showPage()
    c.save()


def draw_annotations_pdf(c, items):
    c.setStrokeColor(CMYKColor(*PALETTE["ink"][0]))
    c.setLineWidth(0.15 * mm)
    for kind, v in items:
        if kind == "text":
            x, y, s, size, bold, anchor = v
            text_pdf(c, x, y, s, size, bold, anchor)
        elif kind == "line":
            c.line(v[0] * mm, v[1] * mm, v[2] * mm, v[3] * mm)
        elif kind == "rect":
            c.rect(v[0] * mm, v[1] * mm, v[2] * mm, v[3] * mm, stroke=1, fill=0)


def build_master_pdf(path, eye):
    size = 10.0
    c = canvas.Canvas(str(path), pagesize=(size * mm, size * mm))
    c.setTitle(f"Göz decal master — {EYE_TITLE[eye]}")
    pdf_decal(c, decal_layers(eye), size / 2, size / 2)
    c.showPage()
    c.save()


# --- SVG ---------------------------------------------------------------------
def svg_path(g):
    d = []
    for p in polys(g):
        for ring in [p.exterior, *p.interiors]:
            d.append("M" + " L".join(f"{x:.4f},{-y:.4f}" for x, y in ring.coords) + " Z")
    return " ".join(d)


def svg_decal(layers):
    return "".join(f'<path fill="#%02x%02x%02x" fill-rule="evenodd" d="{svg_path(g)}"/>' % rgbv
                   for _, rgbv, g in layers)


def build_sheet_svg(path):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_W}mm" height="{PAGE_H}mm" '
           f'viewBox="0 0 {PAGE_W} {PAGE_H}">', "<defs>"]
    for eye in EYES:
        for s in {1.0, *LADDER}:
            out.append(f'<g id="{form_name(eye, s)}">' + svg_decal(decal_layers(eye, s)) + "</g>")
    out.append("</defs>")
    placements = [(e, 1.0, x, y) for e, x, y in grid_cells()] + list(ladder_cells())
    for eye, s, x, y in placements:
        out.append(f'<use href="#{form_name(eye, s)}" x="{x:.3f}" y="{PAGE_H - y:.3f}"/>')
    for kind, v in sheet_annotations():
        if kind == "text":
            x, y, s, size, bold, anchor = v
            out.append(f'<text x="{x}" y="{PAGE_H - y}" font-family="DejaVu Sans, Arial" font-size="{size * 0.3528:.3f}" '
                       f'font-weight="{"bold" if bold else "normal"}" text-anchor="{anchor}" fill="#000">{s}</text>')
        elif kind == "line":
            out.append(f'<line x1="{v[0]}" y1="{PAGE_H - v[1]}" x2="{v[2]}" y2="{PAGE_H - v[3]}" stroke="#000" stroke-width="0.15"/>')
        elif kind == "rect":
            out.append(f'<rect x="{v[0]}" y="{PAGE_H - v[1] - v[3]}" width="{v[2]}" height="{v[3]}" fill="none" stroke="#000" stroke-width="0.15"/>')
    out.append("</svg>")
    Path(path).write_text("\n".join(out), encoding="utf-8")


def build_master_svg(path, eye):
    size = 10.0
    Path(path).write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}mm" height="{size}mm" viewBox="{-size / 2} {-size / 2} {size} {size}">'
        f"{svg_decal(decal_layers(eye))}</svg>", encoding="utf-8")


# --- Raster ------------------------------------------------------------------
def raster_decal(eye, px_per_mm=100, scale=1.0, bg=None, size_mm=8.0):
    """RGBA raster; merkez = decal bbox merkezi, size_mm × size_mm alan."""
    n = int(math.ceil(size_mm * px_per_mm))
    img = Image.new("RGBA", (n, n), bg + (255,) if bg else (0, 0, 0, 0))
    for _, rgbv, g in decal_layers(eye, scale):
        mask = Image.new("L", (n, n), 0)
        dr = ImageDraw.Draw(mask)
        conv = lambda ring: [(n / 2 + x * px_per_mm, n / 2 - y * px_per_mm) for x, y in ring.coords]
        for p in polys(g):
            dr.polygon(conv(p.exterior), fill=255)
            for hole in p.interiors:
                dr.polygon(conv(hole), fill=0)
        img.paste(rgbv + (255,), (0, 0), mask)
    return img


def build_sheet_png(path, dpi=1200):
    ppm = dpi / 25.4
    W, H = round(PAGE_W * ppm), round(PAGE_H * ppm)
    sheet = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tiles = {}
    placements = [(e, 1.0, x, y) for e, x, y in grid_cells()] + list(ladder_cells())
    for eye, s, x, y in placements:
        if (eye, s) not in tiles:
            tiles[eye, s] = raster_decal(eye, ppm, s)
        t = tiles[eye, s]
        sheet.alpha_composite(t, (round(x * ppm - t.width / 2), round((PAGE_H - y) * ppm - t.height / 2)))
    sheet.save(path, dpi=(dpi, dpi), optimize=True)


# --- Sipariş formu -----------------------------------------------------------
def build_proof(path):
    bg = (246, 246, 242)
    tiles = [raster_decal(e, 90, bg=bg, size_mm=7.2) for e in EYES]
    pad = 30
    out = Image.new("RGB", (sum(t.width for t in tiles) + pad * 3, tiles[0].height + pad * 2 + 40), bg)
    dr = ImageDraw.Draw(out)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 26)
    x = pad
    for e, t in zip(EYES, tiles):
        out.paste(t, (x, pad), t)
        dr.text((x + t.width // 2, pad + t.height + 4), EYE_TITLE[e], fill=(0, 0, 0), font=font, anchor="mt")
        x += t.width + pad
    out.save(path)


def build_order_form(path, proof_png, mockup_png=None):
    n = per_eye_count()
    need = PRODUCED_QTY
    S, G = CONTOURS["SOL"], CONTOURS["SAG"]
    c = canvas.Canvas(str(path), pagesize=(PAGE_W * mm, PAGE_H * mm))
    c.setTitle("Waterslide göz decal — baskı sipariş formu")
    y = PAGE_H - 16
    text_pdf(c, 15, y, "BASKI SİPARİŞ FORMU — Waterslide Göz (İris) Decal", 14, True)
    y -= 6
    text_pdf(c, 15, y, f"Amazon Çocuğu 160 mm figür · {ORDER_QTY} adet sipariş, %15 fire ile {PRODUCED_QTY} adet üretim · {date.today().isoformat()}", 8)
    rows = [
        ("Baskı dosyası", "GOZ_IRIS_DECAL_A4_BASKI.pdf (vektör, CMYK) — alternatif: .svg / 1200 dpi .png"),
        ("Tabaka ölçüsü", "A4 (210 × 297 mm), dikey, %100 ölçek — sayfaya sığdır / ölçekle KAPALI"),
        ("Baskı adedi", "2 tabaka (1 üretim + 1 yedek)"),
        ("Tabaka içeriği", f"{n} SOL + {n} SAĞ göz decalı + 20 adet ölçek test decalı"),
        ("İhtiyaç", f"{PRODUCED_QTY} figür × (1 SOL + 1 SAĞ) = {2 * need} decal · yedek +%{round((n - need) / need * 100)}"),
        ("Decal şekli", "Daire değil: göz kapağıyla kesilmiş iris. SOL ve SAĞ farklıdır, karıştırmayın"),
        ("Decal ölçüsü", "SOL {:.2f} × {:.2f} mm · SAĞ {:.2f} × {:.2f} mm (dış ölçü)".format(
            S["decal_bbox_mm"][2] - S["decal_bbox_mm"][0], S["decal_bbox_mm"][3] - S["decal_bbox_mm"][1],
            G["decal_bbox_mm"][2] - G["decal_bbox_mm"][0], G["decal_bbox_mm"][3] - G["decal_bbox_mm"][1])),
        ("Kâğıt", "ŞEFFAF (clear) waterslide decal kâğıdı — beyaz zeminli DEĞİL"),
        ("Yazıcı", "Lazer için lazer-clear, mürekkep püskürtme için inkjet-clear kâğıt"),
        ("Beyaz mürekkep", "Gerekmez. Parlama noktaları mürekkepsiz (şeffaf) bırakıldı"),
        ("Çözünürlük", "En az 1200 dpi; en küçük detay Ø0.43 mm parlama noktası"),
        ("Bitiş", "Mürekkep püskürtme baskıda 2–3 ince kat şeffaf akrilik sprey ile mühürleyin"),
        ("Kesim", "Elle kesim (hücre arası ≥1.4 mm). Kontur kesimde şekil çizgisinin 0.1 mm dışından"),
    ]
    y -= 8
    for k, v in rows:
        text_pdf(c, 15, y, k, 7.8, True)
        text_pdf(c, 50, y, v, 7.8)
        y -= 4.8

    y -= 3
    text_pdf(c, 15, y, "Decal prova (×9, gri zemin = beyaz göz)", 9, True)
    text_pdf(c, 118, y, "Figür üzerinde (STL'den hesaplanmış)", 9, True)
    img_h = 52
    im = Image.open(proof_png)
    c.drawImage(str(proof_png), 15 * mm, (y - 3 - img_h) * mm, img_h * im.width / im.height * mm, img_h * mm)
    if mockup_png:
        im = Image.open(mockup_png)
        c.drawImage(str(mockup_png), 118 * mm, (y - 3 - img_h) * mm, img_h * im.width / im.height * mm, img_h * mm)
    y -= img_h + 9

    text_pdf(c, 15, y, "Tam hesap özeti (STL v2.0.0 → kubbe fit → ARAP yüzey açınımı)", 9, True)
    y -= 5
    table = [
        ("", "SOL (16_Sol_Goz)", "SAĞ (17_Sag_Goz)"),
        ("Kubbe tabanı çapı / yüksekliği", f"Ø{S['kubbe_taban_capi_mm']:.2f} / {S['kubbe_yuksekligi_mm']:.2f} mm",
         f"Ø{G['kubbe_taban_capi_mm']:.2f} / {G['kubbe_yuksekligi_mm']:.2f} mm"),
        ("İris çapı (yüzey boyunca, açınım)", f"Ø{2 * S['acinim_iris_yaricapi_mm']:.2f} mm (±{S['acinim_iris_daire_sapma_std_mm']:.3f})",
         f"Ø{2 * G['acinim_iris_yaricapi_mm']:.2f} mm (±{G['acinim_iris_daire_sapma_std_mm']:.3f})"),
        ("Görünen iris yüzeyi / decal alanı", f"{S['gorunen_iris_yuzey_alani_mm2']:.1f} / {S['decal_alani_mm2']:.1f} mm²",
         f"{G['gorunen_iris_yuzey_alani_mm2']:.1f} / {G['decal_alani_mm2']:.1f} mm²"),
        ("Film gerilmesi (%5–%95)", "{:+.0f}% … {:+.0f}%".format(*[(v - 1) * 100 for v in S["acinim_gerilme_p5_p95"]]),
         "{:+.0f}% … {:+.0f}%".format(*[(v - 1) * 100 for v in G["acinim_gerilme_p5_p95"]])),
    ]
    for i, (a, b, d) in enumerate(table):
        text_pdf(c, 15, y, a, 7.4, i == 0)
        text_pdf(c, 80, y, b, 7.4, i == 0)
        text_pdf(c, 135, y, d, 7.4, i == 0)
        y -= 4.3

    y -= 3
    text_pdf(c, 15, y, "Renkler (CMYK %)", 9, True)
    y -= 4.8
    swatches = [("İris üst (koyu)", *IRIS_STOPS[0][1:]), ("İris orta", *IRIS_STOPS[1][1:]),
                ("İris alt", *IRIS_STOPS[2][1:]), ("İris en alt (sıcak)", *IRIS_STOPS[3][1:]),
                ("Dış halka (limbus)", *PALETTE["limbus"]), ("Göz bebeği", *PALETTE["pupil"])]
    for i, (label, cm, rgbv) in enumerate(swatches):
        xx = 15 + (i % 2) * 92
        yy = y - (i // 2) * 4.4
        c.setFillColor(CMYKColor(*cm))
        c.rect(xx * mm, (yy - 0.8) * mm, 4 * mm, 3 * mm, stroke=0, fill=1)
        text_pdf(c, xx + 6, yy, label, 7.2)
        text_pdf(c, xx + 38, yy, "C{:.0f} M{:.0f} Y{:.0f} K{:.0f}".format(*[v * 100 for v in cm]), 7.2)
        text_pdf(c, xx + 70, yy, "#%02X%02X%02X" % rgbv, 7.2)
    y -= 3 * 4.4 + 3

    text_pdf(c, 15, y, "Uygulama (atölye için)", 9, True)
    steps = [
        "1. 16_Sol_Goz / 17_Sag_Goz parçalarını beyaz (kırık beyaz) boyayın veya beyaz reçineyle basın; parlak vernik atın.",
        "2. SOL decal önden bakışta sol göze, SAĞ decal sağ göze. Düz kenar üst göz kapağı tarafıdır.",
        "3. Decalı kesin, 10–20 sn ılık suda bekletin; iris kenarını kubbe tabanındaki kıvrıma hizalayın.",
        "4. Kubbeye oturması için decal yumuşatıcı (Micro Sol / Mr. Mark Softer) sürün; kuruyunca parlak vernik.",
        "5. Kenar göz kapağının altına ~0.15 mm girecek şekilde hesaplandı; geçmeyi zorlarsa fazlalığı bıçakla alın.",
        "6. Üretimden önce ölçek test çiftlerini (%94–%106) prototipte deneyin; gerekirse ölçek güncellenir.",
    ]
    for s in steps:
        y -= 4.4
        text_pdf(c, 15, y, s, 7.1)
    c.showPage()
    c.save()


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "uretim/decal")
    mockup = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    load_contours(out / "goz_konturlari.json")
    build_sheet_pdf(out / "GOZ_IRIS_DECAL_A4_BASKI.pdf")
    build_sheet_svg(out / "GOZ_IRIS_DECAL_A4_BASKI.svg")
    build_sheet_png(out / "GOZ_IRIS_DECAL_A4_BASKI_1200dpi.png")
    for eye in EYES:
        build_master_pdf(out / f"GOZ_DECAL_MASTER_{eye}.pdf", eye)
        build_master_svg(out / f"GOZ_DECAL_MASTER_{eye}.svg", eye)
        raster_decal(eye, 1200 / 25.4).save(out / f"GOZ_DECAL_MASTER_{eye}_1200dpi.png", dpi=(1200, 1200))
    proof = out / "onizleme_decal.png"
    build_proof(proof)
    build_order_form(out / "BASKI_SIPARIS_FORMU.pdf", proof, mockup)
    print("yazıldı:", *sorted(p.name for p in out.iterdir()), sep="\n  ")


if __name__ == "__main__":
    main()
