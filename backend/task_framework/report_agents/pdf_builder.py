"""ReportLab-based PDF builder for the Stage 5 enhanced report.

Produces a magazine-style A4 PDF matching the Infosys iCETS report format:
  Page 1  – Cover (gradient background + image + title)
  Page 2  – Table of Contents
  Page 3  – About This Initiative (4 cards with real content)
  Page N+ – Chapter divider + content pages per section
"""

from __future__ import annotations

import logging
import os
import random
import tempfile
from typing import List, Optional

from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Frame, Paragraph, Spacer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = A4          # 595.28 x 841.89 points
MARGIN = 42.0                # page margin

# Brand colours
C_DARK_BLUE    = HexColor("#1B3A6B")
C_LIGHT_BLUE   = HexColor("#4A90D9")
C_ORANGE       = HexColor("#E8650A")
C_PURPLE       = HexColor("#7B4DB0")
C_PINK         = HexColor("#B84CA0")
C_CARD_BG      = HexColor("#1A2A4A")   # about-page card background
C_CARD_BORDER  = HexColor("#3355AA")
C_TEXT_DARK    = HexColor("#2A2A2A")
C_TEXT_MED     = HexColor("#4A4A4A")
C_TEXT_LIGHT   = HexColor("#AAAACC")
C_FOOTER_GREY  = HexColor("#777777")
C_WHITE        = white

FOOTER_LABEL = "deepresearch by topaz fabric  |  mars-paperpulse"

# ---------------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------------

def _style(name, **kw) -> ParagraphStyle:
    defaults = dict(fontName="Helvetica", fontSize=11, leading=16,
                    textColor=C_TEXT_DARK, alignment=TA_LEFT)
    defaults.update(kw)
    return ParagraphStyle(name, **defaults)


STYLE_BODY = _style("body", fontSize=11, leading=16.5, alignment=TA_JUSTIFY,
                    spaceAfter=7, textColor=C_TEXT_DARK)
STYLE_SUBHEADING = _style("subheading", fontName="Helvetica-Bold", fontSize=13,
                           leading=18, textColor=C_DARK_BLUE,
                           spaceBefore=12, spaceAfter=4)
STYLE_BULLET = _style("bullet", fontSize=11, leading=15, textColor=C_TEXT_DARK,
                       leftIndent=16, spaceAfter=3)
STYLE_TOC_H = _style("toc_h", fontName="Helvetica-Bold", fontSize=13, leading=18,
                     textColor=C_DARK_BLUE, spaceAfter=2)
STYLE_TOC_ENTRY = _style("toc_entry", fontName="Helvetica-Bold", fontSize=11,
                         leading=16, textColor=C_TEXT_DARK)
STYLE_TOC_SUB = _style("toc_sub", fontSize=10, leading=14, textColor=C_TEXT_MED,
                       leftIndent=20)
STYLE_CARD_TITLE = _style("card_title", fontName="Helvetica-Bold", fontSize=13,
                           leading=17, textColor=C_WHITE)
STYLE_CARD_BODY = _style("card_body", fontSize=9.5, leading=14, textColor=C_TEXT_LIGHT,
                          alignment=TA_JUSTIFY)

# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}


def _list_images(images_dir: str) -> List[str]:
    if not images_dir or not os.path.isdir(images_dir):
        return []
    return sorted(
        os.path.join(images_dir, f)
        for f in os.listdir(images_dir)
        if os.path.splitext(f)[1].lower() in _IMAGE_EXTS
    )


def _safe_draw_image(c: rl_canvas.Canvas, path: str,
                     x: float, y: float, w: float, h: float,
                     mask: str = "auto") -> bool:
    """Draw an image, returning True on success."""
    if not path or not os.path.exists(path):
        return False
    try:
        c.drawImage(path, x, y, width=w, height=h,
                    preserveAspectRatio=False, mask=mask)
        return True
    except Exception as exc:
        logger.warning("pdf_draw_image_failed path=%s error=%s", path, exc)
        return False


def _create_gradient_png(tmp_dir: str, seed: int = 0) -> str:
    """Create a blue-to-purple gradient PNG using Pillow + numpy."""
    import numpy as np
    from PIL import Image

    w, h = 1190, 1684  # 2× A4 at 72dpi

    X = np.linspace(0, 1, w, dtype=np.float32)
    Y = np.linspace(0, 1, h, dtype=np.float32)
    Xg, Yg = np.meshgrid(X, Y)

    # Four corner colours (R,G,B 0-255)
    # TL=#2C5FA8 (steel blue), TR=#5A3DAF (indigo)
    # BL=#9C45B0 (purple), BR=#CC4B9A (pink-purple)
    def lerp(tl, tr, bl, br):
        return ((tl * (1 - Xg) + tr * Xg) * (1 - Yg) +
                (bl * (1 - Xg) + br * Xg) * Yg).clip(0, 255).astype(np.uint8)

    R = lerp(44,  90, 156, 204)
    G = lerp(95,  61,  69,  75)
    B = lerp(168, 175, 176, 154)

    img = Image.fromarray(np.stack([R, G, B], axis=2))

    # Add subtle horizontal circuit-pattern overlay
    rng = random.Random(seed)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img, "RGBA")
    for _ in range(30):
        x0 = rng.randint(0, w)
        y0 = rng.randint(0, h)
        lw = rng.randint(1, 2)
        length = rng.randint(40, 200)
        alpha = rng.randint(10, 30)
        draw.line([(x0, y0), (x0 + length, y0)], fill=(255, 255, 255, alpha), width=lw)

    out = os.path.join(tmp_dir, "_cover_gradient.png")
    img.save(out, optimize=False)
    return out


def _create_dark_tech_bg(tmp_dir: str, base_image: Optional[str] = None) -> str:
    """Create a dark tech-circuit background for the About page."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter

    w, h = 1190, 1684

    if base_image and os.path.exists(base_image):
        try:
            img = Image.open(base_image).convert("RGB").resize((w, h))
            # Dark overlay
            overlay = Image.new("RGBA", (w, h), (10, 5, 35, 200))
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, overlay).convert("RGB")
            # Apply slight blur for depth
            img = img.filter(ImageFilter.GaussianBlur(radius=2))
        except Exception:
            img = _make_dark_gradient(w, h)
    else:
        img = _make_dark_gradient(w, h)

    # Draw subtle circuit lines
    rng = random.Random(42)
    draw = ImageDraw.Draw(img, "RGBA")
    for _ in range(60):
        x0 = rng.randint(0, w)
        y0 = rng.randint(0, h)
        alpha = rng.randint(20, 60)
        length = rng.randint(30, 150)
        if rng.random() > 0.5:
            draw.line([(x0, y0), (x0 + length, y0)], fill=(100, 140, 255, alpha), width=1)
        else:
            draw.line([(x0, y0), (x0, y0 + length)], fill=(100, 140, 255, alpha), width=1)
        # Tiny dot at end
        draw.ellipse([(x0 + length - 3, y0 - 3), (x0 + length + 3, y0 + 3)],
                     fill=(120, 160, 255, alpha + 20))

    out = os.path.join(tmp_dir, "_about_bg.png")
    img.convert("RGB").save(out)
    return out


def _make_dark_gradient(w, h):
    import numpy as np
    from PIL import Image
    X = np.linspace(0, 1, w, dtype=np.float32)
    Y = np.linspace(0, 1, h, dtype=np.float32)
    Xg, Yg = np.meshgrid(X, Y)

    def lerp(tl, tr, bl, br):
        return ((tl * (1 - Xg) + tr * Xg) * (1 - Yg) +
                (bl * (1 - Xg) + br * Xg) * Yg).clip(0, 255).astype(np.uint8)

    R = lerp(15,  25, 30,  50)
    G = lerp(10,  15, 20,  35)
    B = lerp(45,  70, 65, 100)
    return Image.fromarray(np.stack([R, G, B], axis=2))


def _fill_page_with_image(c: rl_canvas.Canvas, img_path: str,
                          darkness: float = 0.0) -> None:
    """Draw img_path as full-page background, optionally darkened."""
    if img_path and os.path.exists(img_path):
        _safe_draw_image(c, img_path, 0, 0, PAGE_W, PAGE_H)
    else:
        # Fallback: dark blue solid
        c.setFillColor(C_DARK_BLUE)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    if darkness > 0:
        c.saveState()
        c.setFillColorRGB(0, 0, 0.05, alpha=darkness)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
        c.restoreState()


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _draw_footer(c: rl_canvas.Canvas, page_num: Optional[int] = None) -> None:
    c.saveState()
    c.setFont("Helvetica", 7)
    c.setFillColor(C_FOOTER_GREY)
    c.drawString(MARGIN, 18, FOOTER_LABEL)
    if page_num is not None:
        c.drawRightString(PAGE_W - MARGIN, 18, str(page_num))
    c.restoreState()


def _draw_sparkles(c: rl_canvas.Canvas, n: int = 55, seed: int = 7) -> None:
    """Scatter white glow-dots on the page."""
    rng = random.Random(seed)
    c.saveState()
    for _ in range(n):
        x = rng.uniform(5, PAGE_W - 5)
        y = rng.uniform(PAGE_H * 0.06, PAGE_H * 0.96)
        r = rng.uniform(1.2, 5.5)
        alpha = rng.uniform(0.25, 0.95)
        c.setFillColorRGB(1, 1, 1, alpha=alpha)
        c.circle(x, y, r, fill=1, stroke=0)
        if r > 3:
            c.setFillColorRGB(1, 1, 1, alpha=alpha * 0.25)
            c.circle(x, y, r * 2.0, fill=1, stroke=0)
    c.restoreState()


def _wrap_text_to_lines(text: str, max_chars: int) -> List[str]:
    """Simple word-wrap into lines of at most max_chars."""
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        if not cur:
            cur = w
        elif len(cur) + 1 + len(w) <= max_chars:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _draw_multiline(c: rl_canvas.Canvas, text: str, x: float, y: float,
                    font: str, size: float, leading: float,
                    max_chars: int, color=None) -> float:
    """Draw wrapped text, return y after last line."""
    if color:
        c.setFillColor(color)
    c.setFont(font, size)
    for line in _wrap_text_to_lines(text, max_chars):
        c.drawString(x, y, line)
        y -= leading
    return y


def _safe_xml(text: str) -> str:
    """Escape special characters for ReportLab XML/Paragraph."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def _draw_flowable_frame(c: rl_canvas.Canvas, story: list,
                         x: float, y: float, w: float, h: float) -> list:
    """Draw story into a Frame. Modifies story in-place (overflow stays). Returns story."""
    frame = Frame(x, y, w, h, showBoundary=0,
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    frame.addFromList(story, c)   # modifies story in-place; returns None in ReportLab 5
    return story                  # return the same list so the caller sees remaining items


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

class PDFReportBuilder:
    """Builds the full magazine-style PDF."""

    def build(self,
              output_path: str,
              report_title: str,
              about_cards: list,
              sections: list,
              toc_entries: list,
              images_dir: str) -> str:

        tmp_dir = tempfile.mkdtemp(prefix="report_pdf_")
        images = _list_images(images_dir)
        rng = random.Random(hash(report_title) % (2**31))
        imgs = images[:]
        rng.shuffle(imgs)

        # Pre-generate background images
        gradient_bg = _create_gradient_png(tmp_dir, seed=abs(hash(report_title)) % 999)
        about_bg_src = imgs[0] if imgs else None
        about_bg = _create_dark_tech_bg(tmp_dir, about_bg_src)

        c = rl_canvas.Canvas(output_path, pagesize=(PAGE_W, PAGE_H))

        # ── Page 1: Cover ──────────────────────────────────────────────────
        cover_img = imgs[1] if len(imgs) > 1 else (imgs[0] if imgs else None)
        self._draw_cover(c, report_title, gradient_bg, cover_img)
        c.showPage()

        # ── Page 2: Table of Contents ──────────────────────────────────────
        self._draw_toc(c, toc_entries, report_title)
        c.showPage()

        # ── Page 3: About This Initiative ─────────────────────────────────
        self._draw_about(c, about_cards, about_bg)
        c.showPage()

        # ── Pages 4+: Sections ─────────────────────────────────────────────
        current_page = 4
        for i, sec in enumerate(sections):
            # Close the previous section's last content page before starting a new divider.
            # Without this, the divider background image overwrites the previous section's text.
            if i > 0:
                c.showPage()
                current_page += 1

            div_img = imgs[(i + 2) % len(imgs)] if imgs else None
            self._draw_chapter_divider(c, sec["chapter_num"], sec["title"], div_img)
            c.showPage()
            current_page += 1

            # Content pages (handles overflow automatically)
            pages_used = self._draw_section_pages(c, sec, current_page)
            current_page += pages_used

        c.save()
        logger.info("pdf_saved path=%s", output_path)
        return output_path

    # ── Cover ────────────────────────────────────────────────────────────────

    def _draw_cover(self, c: rl_canvas.Canvas, title: str,
                    gradient_path: str, cover_img_path: Optional[str]) -> None:

        # Background gradient
        _fill_page_with_image(c, gradient_path)

        # Sparkles
        _draw_sparkles(c, n=60, seed=abs(hash(title)) % 9999)

        # Right-side image panel (dark frame + photo)
        panel_x, panel_y = PAGE_W * 0.42, PAGE_H * 0.25
        panel_w, panel_h = PAGE_W * 0.52, PAGE_H * 0.58
        # Dark panel background
        c.saveState()
        c.setFillColor(HexColor("#0B1535"))
        c.rect(panel_x, panel_y, panel_w, panel_h, fill=1, stroke=0)
        c.restoreState()
        # Photo inside panel
        if cover_img_path:
            _safe_draw_image(c, cover_img_path, panel_x + 4, panel_y + 4,
                             panel_w - 8, panel_h - 8)

        # Infosys header text (top right)
        c.saveState()
        c.setFont("Helvetica-Bold", 9.5)
        c.setFillColor(C_WHITE)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 35, "Infosys® | Center for Emerging")
        c.setFont("Helvetica", 9)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 48, "Technology Solutions")
        c.restoreState()

        # Title (left side, ALL CAPS) — font size scales with title length
        title_upper = title.upper()
        title_x = MARGIN
        title_y_start = PAGE_H * 0.74
        title_max_w = PAGE_W * 0.42 - MARGIN - 8   # stay left of image panel

        # Pick font size so title fits without overflowing panel area
        title_len = len(title_upper)
        if title_len <= 40:
            font_size, chars_per_line, leading = 28, 18, 36
        elif title_len <= 80:
            font_size, chars_per_line, leading = 22, 22, 30
        elif title_len <= 130:
            font_size, chars_per_line, leading = 18, 26, 26
        else:
            font_size, chars_per_line, leading = 14, 32, 22

        c.saveState()
        c.setFillColor(C_WHITE)
        lines = _wrap_text_to_lines(title_upper, chars_per_line)
        y = title_y_start
        for line in lines[:8]:
            c.setFont("Helvetica-Bold", font_size)
            c.drawString(title_x, y, line)
            y -= leading
        c.restoreState()

        # Bottom bar
        c.saveState()
        c.setFillColorRGB(0, 0, 0, alpha=0.35)
        c.rect(0, 0, PAGE_W, 80, fill=1, stroke=0)
        c.restoreState()

        c.saveState()
        c.setFillColor(C_WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(MARGIN, 55, "CREATED BY")
        c.setFont("Helvetica-Bold", 11)
        c.drawString(MARGIN, 40, "ADVANCE AI")

        c.setFont("Helvetica", 8)
        c.drawString(PAGE_W * 0.40, 55, "An Initiative by Living Labs and Topaz Fabric:")
        c.setFont("Helvetica-Bold", 9)
        c.drawString(PAGE_W * 0.40, 40, "Infosys® Living Labs    |    Infosys Topaz Fabric")
        c.restoreStore if False else None
        c.restoreState()

    # ── Table of Contents ────────────────────────────────────────────────────

    def _draw_toc(self, c: rl_canvas.Canvas, toc_entries: list,
                  report_title: str) -> None:
        # White background
        c.setFillColor(C_WHITE)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

        # "Contents" heading
        c.setFont("Helvetica-Bold", 36)
        c.setFillColor(C_TEXT_DARK)
        c.drawString(MARGIN, PAGE_H - 80, "Contents")

        # Horizontal rule
        c.setStrokeColor(HexColor("#DDDDDD"))
        c.setLineWidth(1)
        c.line(MARGIN, PAGE_H - 92, PAGE_W - MARGIN, PAGE_H - 92)

        y = PAGE_H - 120
        content_w = PAGE_W - 2 * MARGIN

        for i, entry in enumerate(toc_entries, start=1):
            if y < 80:
                break  # safety

            roman = _to_roman(i)
            level = entry.get("level", 1)

            if level == 1:
                # Main section row
                c.saveState()
                c.setFillColor(C_DARK_BLUE)
                c.rect(MARGIN, y - 4, content_w, 20, fill=1, stroke=0)
                c.setFillColor(C_WHITE)
                c.setFont("Helvetica-Bold", 11)
                c.drawString(MARGIN + 6, y + 2, f"{roman}.")
                c.drawString(MARGIN + 38, y + 2, entry["title"])
                c.drawRightString(PAGE_W - MARGIN - 6, y + 2,
                                  str(entry["page_num"]).zfill(2))
                c.restoreState()
                y -= 26

                # Sub-entries (sub-sections derived from title)
                sub_entries = _generate_sub_entries(entry["title"])
                for j, sub in enumerate(sub_entries[:4], start=1):
                    if y < 80:
                        break
                    c.setFont("Helvetica-Bold", 10)
                    c.setFillColor(C_TEXT_DARK)
                    c.drawString(MARGIN + 38, y, f"{j}. {sub}")
                    c.setFont("Helvetica", 10)
                    c.setFillColor(C_TEXT_MED)
                    sub_page = entry["page_num"] + j
                    c.drawRightString(PAGE_W - MARGIN, y,
                                      str(sub_page).zfill(2))

                    # Light underline
                    c.setStrokeColor(HexColor("#EEEEEE"))
                    c.setLineWidth(0.5)
                    c.line(MARGIN + 38, y - 3, PAGE_W - MARGIN, y - 3)
                    y -= 18

                y -= 10  # gap between sections
            else:
                c.setFont("Helvetica", 10)
                c.setFillColor(C_TEXT_MED)
                c.drawString(MARGIN + 20 * level, y, f"  {entry['title']}")
                c.drawRightString(PAGE_W - MARGIN, y, str(entry["page_num"]).zfill(2))
                y -= 16

        _draw_footer(c)

    # ── About ────────────────────────────────────────────────────────────────

    def _draw_about(self, c: rl_canvas.Canvas, about_cards: list,
                    bg_path: str) -> None:
        # Background
        _fill_page_with_image(c, bg_path)

        # Section title
        c.saveState()
        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(C_WHITE)
        c.drawString(MARGIN, PAGE_H - 55, "About this initiative")
        c.restoreState()

        # Draw 4 cards
        cards = about_cards[:4]
        n = len(cards)
        total_card_area = PAGE_H - 110 - 40  # from below title to footer
        spacing = 12
        card_h = (total_card_area - spacing * (n - 1)) / max(n, 1)
        card_w = PAGE_W - 2 * MARGIN
        card_x = MARGIN

        for idx, card in enumerate(cards):
            card_y = PAGE_H - 110 - (card_h + spacing) * idx - card_h
            self._draw_about_card(c, card, card_x, card_y, card_w, card_h)

        _draw_footer(c)

    def _draw_about_card(self, c: rl_canvas.Canvas, card: dict,
                         x: float, y: float, w: float, h: float) -> None:
        # Card background (semi-transparent dark)
        c.saveState()
        c.setFillColorRGB(0.10, 0.16, 0.30, alpha=0.88)
        c.roundRect(x, y, w, h, radius=10, fill=1, stroke=0)

        # Left accent bar
        c.setFillColor(C_LIGHT_BLUE)
        c.rect(x, y + 10, 4, h - 20, fill=1, stroke=0)

        # Card border
        c.setStrokeColor(C_CARD_BORDER)
        c.setLineWidth(0.8)
        c.roundRect(x, y, w, h, radius=10, fill=0, stroke=1)
        c.restoreState()

        inner_x = x + 18
        inner_w = w - 30
        title_h = 22
        pad_top = 12

        # Title
        c.saveState()
        c.setFont("Helvetica-Bold", 13)
        c.setFillColor(C_WHITE)
        c.drawString(inner_x, y + h - pad_top - title_h + 4, card.get("title", ""))
        c.restoreState()

        # Underline
        c.saveState()
        c.setStrokeColor(C_LIGHT_BLUE)
        c.setLineWidth(1)
        c.line(inner_x, y + h - pad_top - title_h - 4,
               x + w - 14, y + h - pad_top - title_h - 4)
        c.restoreState()

        # Body text via Paragraph/Frame
        body_top = y + h - pad_top - title_h - 14
        body_h = body_top - y - 10
        if body_h < 20:
            return

        body_text = card.get("content", "")
        # escape for ReportLab XML
        body_safe = (body_text
                     .replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;"))
        story = [Paragraph(body_safe, STYLE_CARD_BODY)]
        _draw_flowable_frame(c, story, inner_x, y + 8, inner_w, body_h)

    # ── Chapter Divider ──────────────────────────────────────────────────────

    def _draw_chapter_divider(self, c: rl_canvas.Canvas, chapter_num: int,
                               title: str, bg_image: Optional[str]) -> None:
        # Full-page background image with dark overlay
        _fill_page_with_image(c, bg_image, darkness=0.45)

        # Diagonal dark-blue polygon (lower-left area)
        poly_y_top = PAGE_H * 0.64
        poly_y_bot = PAGE_H * 0.34
        poly_x_right = PAGE_W * 0.88

        c.saveState()
        c.setFillColorRGB(0.105, 0.227, 0.420, alpha=0.93)  # ≈ C_DARK_BLUE
        p = c.beginPath()
        p.moveTo(0, poly_y_top)
        p.lineTo(poly_x_right, poly_y_top)
        p.lineTo(poly_x_right * 0.82, poly_y_bot)
        p.lineTo(0, poly_y_bot)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.restoreState()

        # Chapter number badge (circle)
        badge_cx = MARGIN + 28
        badge_cy = poly_y_top + 28
        c.saveState()
        c.setFillColor(C_WHITE)
        c.circle(badge_cx, badge_cy, 24, fill=1, stroke=0)
        c.setFillColor(C_DARK_BLUE)
        c.setFont("Helvetica-Bold", 16)
        badge_str = f"{chapter_num:02d}"
        c.drawCentredString(badge_cx, badge_cy - 6, badge_str)
        c.restoreState()

        # Section title inside polygon
        title_x = MARGIN + 20
        title_y = poly_y_bot + (poly_y_top - poly_y_bot) * 0.45
        c.saveState()
        c.setFillColor(C_WHITE)
        lines = _wrap_text_to_lines(title.upper(), 28)
        for i, line in enumerate(lines[:3]):
            c.setFont("Helvetica-Bold", 30)
            c.drawString(title_x, title_y - i * 38, line)
        c.restoreState()

        # Subtle bottom teal triangle accent
        c.saveState()
        c.setFillColorRGB(0.18, 0.55, 0.75, alpha=0.60)
        p2 = c.beginPath()
        p2.moveTo(PAGE_W * 0.50, 0)
        p2.lineTo(PAGE_W, 0)
        p2.lineTo(PAGE_W, PAGE_H * 0.25)
        p2.close()
        c.drawPath(p2, fill=1, stroke=0)
        c.restoreState()

        _draw_footer(c)

    # ── Section Content (multi-page) ─────────────────────────────────────────

    def _draw_section_pages(self, c: rl_canvas.Canvas, section: dict,
                             start_page: int) -> int:
        """Draw all content pages for a section. Returns number of pages used."""
        content = section.get("content", "")
        plots = [p for p in section.get("plots", []) if os.path.exists(p)]
        banner_img = section.get("image_path")
        chapter_num = section["chapter_num"]
        title = section["title"]

        # Build flowable story
        story = self._build_story(content, plots)

        page_num = start_page
        is_first = True

        while story:
            if is_first:
                banner_h = PAGE_H * 0.25  # 25% banner — leaves ~75% for content
                _safe_draw_image(c, banner_img, 0, PAGE_H - banner_h, PAGE_W, banner_h)
                if not banner_img:
                    c.setFillColor(C_DARK_BLUE)
                    c.rect(0, PAGE_H - banner_h, PAGE_W, banner_h, fill=1, stroke=0)

                # Section heading below banner
                heading_y = PAGE_H - banner_h - 30
                c.setFont("Helvetica-Bold", 18)
                c.setFillColor(C_ORANGE)
                c.drawString(MARGIN, heading_y, f"{chapter_num}. {title}")
                c.setStrokeColor(C_ORANGE)
                c.setLineWidth(1.5)
                c.line(MARGIN, heading_y - 6, PAGE_W - MARGIN, heading_y - 6)

                frame_top = heading_y - 18
                frame_h = frame_top - 32
                is_first = False
            else:
                # Continuation: clean branded header bar (no image — looks distorted at 58pt)
                banner_h = 52
                c.saveState()
                c.setFillColor(C_DARK_BLUE)
                c.rect(0, PAGE_H - banner_h, PAGE_W, banner_h, fill=1, stroke=0)
                # Orange left accent stripe
                c.setFillColor(C_ORANGE)
                c.rect(0, PAGE_H - banner_h, 5, banner_h, fill=1, stroke=0)
                # Chapter number badge (small)
                badge_x = MARGIN + 10
                badge_y = PAGE_H - banner_h + banner_h / 2
                c.setFillColor(HexColor("#2A5298"))
                c.circle(badge_x, badge_y, 12, fill=1, stroke=0)
                c.setFillColor(C_WHITE)
                c.setFont("Helvetica-Bold", 9)
                c.drawCentredString(badge_x, badge_y - 3, f"{chapter_num:02d}")
                # Section title
                c.setFont("Helvetica-Bold", 10)
                c.setFillColor(C_WHITE)
                c.drawString(MARGIN + 30, PAGE_H - banner_h + 30, title.upper())
                c.setFont("Helvetica", 8)
                c.setFillColor(C_TEXT_LIGHT)
                c.drawString(MARGIN + 30, PAGE_H - banner_h + 16, "continued")
                # Right page label
                c.setFont("Helvetica", 8)
                c.setFillColor(C_TEXT_LIGHT)
                c.drawRightString(PAGE_W - MARGIN, PAGE_H - banner_h + 22, FOOTER_LABEL)
                c.restoreState()

                frame_top = PAGE_H - banner_h - 10
                frame_h = frame_top - 32

            # White body background (from just below banner to footer)
            c.saveState()
            c.setFillColor(C_WHITE)
            c.rect(0, 28, PAGE_W, frame_top - 28, fill=1, stroke=0)
            c.restoreState()

            # Draw text frame
            story = _draw_flowable_frame(
                c, story,
                MARGIN, 32,
                PAGE_W - 2 * MARGIN, frame_h
            )

            _draw_footer(c, page_num)

            if story:
                c.showPage()
                page_num += 1

        return page_num - start_page + 1

    def _parse_content_blocks(self, content: str) -> List[tuple]:
        """Parse content into [(type, text)] blocks.

        Types: 'heading' (## line), 'bullet' (- line), 'para' (plain paragraph).
        """
        blocks: List[tuple] = []
        para_lines: List[str] = []

        def flush_para() -> None:
            text = " ".join(para_lines).strip()
            if text:
                blocks.append(("para", text))
            para_lines.clear()

        for line in content.split("\n"):
            s = line.strip()
            if not s:
                flush_para()
            elif s.startswith("## ") or s.startswith("### "):
                flush_para()
                heading = s.lstrip("#").strip()
                if heading:
                    blocks.append(("heading", heading))
            elif s.startswith("- ") or s.startswith("• "):
                flush_para()
                bullet = s[2:].strip()
                if bullet:
                    blocks.append(("bullet", bullet))
            else:
                para_lines.append(s)

        flush_para()
        return blocks

    def _build_story(self, content: str, plots: List[str]) -> list:
        """Build ReportLab Flowables from structured content + plots."""
        from reportlab.platypus import Image as RLImage

        blocks = self._parse_content_blocks(content)

        # Identify paragraph block indices for plot injection
        para_block_idxs = [i for i, (t, _) in enumerate(blocks) if t == "para"]
        plot_at: dict = {}
        if plots and para_block_idxs:
            n_para = len(para_block_idxs)
            for p_i, plot in enumerate(plots[:4]):
                slot = min((p_i + 1) * max(1, n_para // (min(len(plots), 4) + 1)),
                           n_para - 1)
                plot_at[para_block_idxs[slot]] = plot

        story: list = []
        for b_idx, (btype, btext) in enumerate(blocks):
            safe = _safe_xml(btext)
            if btype == "heading":
                story.append(Spacer(1, 10))
                story.append(Paragraph(safe, STYLE_SUBHEADING))
            elif btype == "bullet":
                story.append(Paragraph(f"• {safe}", STYLE_BULLET))
            else:  # para
                story.append(Paragraph(safe, STYLE_BODY))
                story.append(Spacer(1, 5))

            if b_idx in plot_at:
                plot_path = plot_at[b_idx]
                if os.path.exists(plot_path):
                    try:
                        max_w = PAGE_W - 2 * MARGIN - 10
                        story.append(Spacer(1, 10))
                        story.append(
                            RLImage(plot_path, width=min(380, max_w),
                                    height=240, kind="bound")
                        )
                        story.append(Spacer(1, 10))
                    except Exception as exc:
                        logger.warning("pdf_plot_embed_failed path=%s error=%s",
                                       plot_path, exc)

        return story


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

_ROMAN = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
          (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
          (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _to_roman(n: int) -> str:
    result = ""
    for val, sym in _ROMAN:
        while n >= val:
            result += sym
            n -= val
    return result


_SUB_ENTRIES: dict = {
    "Executive Summary": ["Key Findings", "Research Significance", "Innovation Highlights"],
    "Introduction":       ["Background & Motivation", "Research Objectives", "Scope & Contributions"],
    "Methodology":        ["Experimental Design", "Data & Models", "Evaluation Criteria"],
    "Results & Findings": ["Quantitative Results", "Comparative Analysis", "Ablation Study"],
    "Conclusions & Future Directions": ["Summary of Contributions", "Limitations", "Future Work"],
}


def _generate_sub_entries(section_title: str) -> List[str]:
    for key, subs in _SUB_ENTRIES.items():
        if key.lower() in section_title.lower() or section_title.lower() in key.lower():
            return subs
    return ["Overview", "Analysis", "Key Points"]
