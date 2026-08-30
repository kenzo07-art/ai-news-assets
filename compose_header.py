#!/usr/bin/env python3
"""Compose the daily "today at a glance" header image for the AI news digest email.

The artwork (assets/bg_main.jpg) is pre-generated with gpt-image-2.
The Japanese text is drawn here with a real font so it is never garbled.

Usage:
    python3 compose_header.py digest.json -o header.jpg

digest.json shape:
{
  "date_label": "2026年8月31日（日）",
  "period": "2026-08-24 〜 2026-08-31",
  "categories": [
    {"name": "世界のAI", "color": "#4f9cf9",
     "items": [{"title": "...", "score": 3}, {"title": "...", "score": 2}]},
    ...4 items...
  ]
}
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W = 960
BANNER_H = 283
CARD_GAP = 18
PAD = 26
PANEL_BG = (13, 27, 56)
CARD_BG = (23, 40, 78)
CARD_LINE = (44, 66, 116)
WHITE = (255, 255, 255)
MUTED = (168, 186, 214)

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",        # cloud sandbox
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",               # macOS fallback
]


def find_font(explicit=None):
    if explicit and os.path.exists(explicit):
        return explicit
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    sys.exit("ERROR: no Japanese font found. Tried: " + ", ".join(FONT_CANDIDATES))


def hex_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def bold(draw, xy, text, font, fill):
    """IPA Gothic ships one weight only; fake bold by double-striking."""
    x, y = xy
    draw.text((x, y), text, font=font, fill=fill)
    draw.text((x + 1, y), text, font=font, fill=fill)


def wrap(text, font, max_w, max_lines):
    lines, cur = [], ""
    for ch in text:
        if font.getlength(cur + ch) <= max_w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines and cur:
        lines.append(cur)
    if len(lines) == max_lines and font.getlength(cur) > 0 and len(text) > sum(len(l) for l in lines):
        last = lines[-1]
        while last and font.getlength(last + "…") > max_w:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


def procedural_backdrop():
    """Fallback artwork drawn in code, used when no gpt-image-2 asset is available."""
    img = Image.new("RGB", (W, BANNER_H), PANEL_BG)
    grad = Image.new("RGB", (1, BANNER_H))
    for y in range(BANNER_H):
        t = y / max(1, BANNER_H - 1)
        grad.putpixel((0, y), (int(18 + 10 * (1 - t)), int(38 + 22 * (1 - t)), int(78 + 34 * (1 - t))))
    img.paste(grad.resize((W, BANNER_H)), (0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    for r, a in ((330, 26), (250, 30), (170, 36), (95, 44)):
        d.ellipse([W - 205 - r, BANNER_H - 60 - r, W - 205 + r, BANNER_H - 60 + r],
                  outline=(120, 200, 255, a), width=2)
    for i in range(26):
        x = 40 + i * 34
        d.line([(x, BANNER_H), (x + 150, 0)], fill=(255, 255, 255, 7), width=1)
    for gx in range(0, W, 26):
        for gy in range(0, 120, 26):
            d.ellipse([gx, gy, gx + 2, gy + 2], fill=(150, 205, 255, 40))
    d.rectangle([0, BANNER_H - 4, W, BANNER_H], fill=(96, 197, 255, 190))
    return img


def build_banner(bg_path, date_label, period, font_path):
    banner = Image.new("RGB", (W, BANNER_H), PANEL_BG)
    if bg_path and os.path.exists(bg_path):
        art = Image.open(bg_path).convert("RGB")
        # keep the illustrated upper half of the artwork
        aw, ah = art.size
        crop_h = int(aw * BANNER_H / W)
        top = int(ah * 0.04)
        art = art.crop((0, top, aw, min(ah, top + crop_h))).resize((W, BANNER_H), Image.LANCZOS)
        banner.paste(art, (0, 0))
        used_art = True
    else:
        banner.paste(procedural_backdrop(), (0, 0))
        used_art = False

    # dark scrim so the title always reads, whatever the artwork looks like
    scrim = Image.new("L", (1, BANNER_H))
    peak = 215 if used_art else 90
    for y in range(BANNER_H):
        t = y / BANNER_H
        scrim.putpixel((0, y), int(15 + peak * (t ** 2.2)))
    scrim = scrim.resize((W, BANNER_H))
    banner.paste(Image.new("RGB", (W, BANNER_H), PANEL_BG), (0, 0), scrim)

    d = ImageDraw.Draw(banner)
    f_kicker = ImageFont.truetype(font_path, 21)
    f_title = ImageFont.truetype(font_path, 51)
    f_sub = ImageFont.truetype(font_path, 21)
    d.rectangle([PAD, BANNER_H - 144, PAD + 6, BANNER_H - 29], fill=(96, 197, 255))
    bold(d, (PAD + 22, BANNER_H - 144), "AI NEWS DIGEST", f_kicker, (140, 205, 255))
    bold(d, (PAD + 22, BANNER_H - 113), date_label, f_title, WHITE)
    d.text((PAD + 24, BANNER_H - 51), f"対象期間  {period}", font=f_sub, fill=MUTED)
    return banner


def build(data, bg_path, font_path, out_path, quality):
    cats = data["categories"][:4]
    f_chip = ImageFont.truetype(font_path, 20)
    f_item = ImageFont.truetype(font_path, 22)
    f_star = ImageFont.truetype(font_path, 17)
    f_foot = ImageFont.truetype(font_path, 19)

    card_w = (W - PAD * 2 - CARD_GAP) // 2
    rows = [cats[0:2], cats[2:4]]
    max_items = max((len(c.get("items", [])) for c in cats), default=2)
    card_h = 84 + max_items * 68
    panel_h = PAD + len(rows) * (card_h + CARD_GAP) + 38
    total_h = BANNER_H + panel_h

    img = Image.new("RGB", (W, total_h), PANEL_BG)
    img.paste(build_banner(bg_path, data["date_label"], data["period"], font_path), (0, 0))
    d = ImageDraw.Draw(img)

    y = BANNER_H + PAD
    for row in rows:
        for i, cat in enumerate(row):
            x = PAD + i * (card_w + CARD_GAP)
            color = hex_rgb(cat.get("color", "#4f9cf9"))
            d.rounded_rectangle([x, y, x + card_w, y + card_h], radius=14,
                                fill=CARD_BG, outline=CARD_LINE, width=2)
            d.rounded_rectangle([x, y + 14, x + 5, y + card_h - 14], radius=3, fill=color)

            chip_w = int(f_chip.getlength(cat["name"])) + 28
            d.rounded_rectangle([x + 20, y + 16, x + 20 + chip_w, y + 47], radius=8, fill=color)
            bold(d, (x + 34, y + 21), cat["name"], f_chip, (10, 22, 45))

            iy = y + 64
            for item in cat.get("items", [])[:max_items]:
                score = max(0, min(3, int(item.get("score", 2))))
                d.text((x + 20, iy + 3), "★" * score + "☆" * (3 - score),
                       font=f_star, fill=color)
                lines = wrap(item["title"], f_item, card_w - 112, 2)
                ly = iy
                for ln in lines:
                    bold(d, (x + 84, ly), ln, f_item, WHITE)
                    ly += 28
                iy += 68
            y_used = iy
        y += card_h + CARD_GAP

    d.text((PAD + 4, total_h - 36), "▼ 全ニュースの要約・出典リンクはこの下に",
           font=f_foot, fill=MUTED)

    img.save(out_path, "JPEG", quality=quality, optimize=True, progressive=True)
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    ap.add_argument("-o", "--out", default="header.jpg")
    ap.add_argument("--bg", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                 "assets", "bg_main.jpg"))
    ap.add_argument("--font", default=None)
    ap.add_argument("--quality", type=int, default=60)
    args = ap.parse_args()

    with open(args.json_path, encoding="utf-8") as f:
        data = json.load(f)
    out = build(data, args.bg, find_font(args.font), args.out, args.quality)
    size = os.path.getsize(out)
    print(f"OK {out} {size} bytes ({size/1024:.0f} KB)")
    if size > 90_000:
        print("WARN: larger than 90KB — rerun with a lower --quality")


if __name__ == "__main__":
    main()
