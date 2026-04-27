"""Generate dark-themed placeholder PNGs for the README.

Run with: uv run python docs/images/_make_placeholders.py

Each placeholder mimics the sparkd UI's command-center aesthetic:
- charcoal background (matches --bg-base)
- monospace eyebrow + serif title
- a faint orange accent stripe (matches --accent-ai)
- a "screenshot pending" hint at the bottom

Replace any of these with a real PNG at the same path; the README links
to fixed filenames, so no edits are needed when you swap them in.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent

# Palette borrowed from the SPA's CSS tokens.
BG = (10, 10, 12)            # --bg-base
PANEL = (16, 17, 20)         # --bg-elev-1
BORDER = (38, 40, 46)        # --border-subtle
FG = (228, 228, 232)         # --fg-primary
FG_MUTED = (140, 144, 152)   # --fg-muted
FG_FAINT = (84, 88, 96)      # --fg-faint
ACCENT = (255, 119, 51)      # --accent-ai
INFO = (108, 182, 255)       # --signal-info


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates_regular = [
        "/System/Library/Fonts/Supplemental/Menlo.ttc",
        "/System/Library/Fonts/Menlo.ttc",
        "/Library/Fonts/Menlo.ttc",
    ]
    candidates_bold = [
        "/System/Library/Fonts/Supplemental/Menlo.ttc",  # menlo bold via index
    ]
    paths = candidates_bold if bold else candidates_regular
    for p in paths:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _serif(size: int) -> ImageFont.FreeTypeFont:
    for p in (
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/Library/Fonts/Georgia.ttf",
        "/System/Library/Fonts/Times.ttc",
    ):
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def make(filename: str, *, w: int, h: int, eyebrow: str, title: str) -> None:
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)

    # Top accent stripe.
    draw.rectangle([(0, 0), (w, 4)], fill=ACCENT)

    # Inner panel.
    pad = max(40, w // 32)
    draw.rectangle(
        [(pad, pad + 30), (w - pad, h - pad)],
        fill=PANEL,
        outline=BORDER,
        width=1,
    )

    # Eyebrow.
    eyebrow_font = _font(max(14, w // 110))
    draw.text(
        (pad + 28, pad + 60),
        eyebrow.upper(),
        font=eyebrow_font,
        fill=ACCENT,
        spacing=4,
    )

    # Title.
    title_font = _serif(max(40, w // 28))
    draw.text(
        (pad + 28, pad + 100),
        title,
        font=title_font,
        fill=FG,
    )

    # Faux UI scaffolding lines so it doesn't read as a totally blank tile.
    line_y = pad + 200
    for i in range(6):
        x_left = pad + 28
        x_right = w - pad - 28
        seg_w = (x_right - x_left) * (0.45 + 0.1 * (i % 3))
        draw.rectangle(
            [(x_left, line_y), (x_left + seg_w, line_y + 14)],
            fill=BORDER,
        )
        line_y += 36

    # Pill row.
    pill_y = line_y + 20
    pill_x = pad + 28
    for label, fill in (
        ("1-NODE", BORDER),
        ("2-NODE", INFO),
        ("3-NODE", BORDER),
    ):
        text_w = draw.textlength(label, font=eyebrow_font)
        pw = int(text_w + 30)
        draw.rounded_rectangle(
            [(pill_x, pill_y), (pill_x + pw, pill_y + 26)],
            radius=13,
            outline=fill,
            width=1,
        )
        draw.text(
            (pill_x + 15, pill_y + 6),
            label,
            font=eyebrow_font,
            fill=fill,
        )
        pill_x += pw + 12

    # Footer hint.
    hint_font = _font(max(11, w // 140))
    draw.text(
        (pad + 28, h - pad - 32),
        "screenshot placeholder · drop a real PNG at this path to replace",
        font=hint_font,
        fill=FG_FAINT,
    )

    out = HERE / filename
    img.save(out, format="PNG", optimize=True)
    print(f"wrote {out.relative_to(HERE.parent.parent)}  ({w}×{h})")


def main() -> None:
    # Hero is wider; rest are 16:9-ish.
    specs = [
        ("hero.png", 2400, 1100, "sparkd · ai · recipe advisor",
         "Browse Hugging Face, generate a recipe."),
        ("launch.png", 2000, 1125, "sparkd · control",
         "Launch recipe."),
        ("advisor.png", 2000, 1125, "sparkd · ai · recipe advisor",
         "Plan multi-node."),
        ("hf-browser.png", 2000, 1125, "sparkd · ai · hugging face",
         "Browse the Hub."),
        ("recipe-diff.png", 2000, 1125, "sparkd · library · diff",
         "Recipe versions."),
        ("boxes.png", 2000, 1125, "sparkd · fleet",
         "DGX Spark boxes."),
        ("box-detail.png", 1600, 1100, "sparkd · fleet · detail",
         "Box detail."),
    ]
    for filename, w, h, eyebrow, title in specs:
        make(filename, w=w, h=h, eyebrow=eyebrow, title=title)


if __name__ == "__main__":
    main()
