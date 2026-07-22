#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

CANVAS = 1024
BACKGROUND = "#0d1720"
GOLD = "#f0b64c"
CYAN = "#55b4c3"
WHITE = "#f7fafc"
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def build_master() -> Image.Image:
    image = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    draw.rounded_rectangle((0, 0, CANVAS - 1, CANVAS - 1), radius=232, fill=BACKGROUND)

    # Two explicit T forms: the letter pair links the mark directly to ThisTinti.
    draw.rounded_rectangle((152, 136, 520, 272), radius=34, fill=GOLD)
    draw.rectangle((272, 238, 408, 848), fill=GOLD)

    draw.rounded_rectangle((504, 136, 872, 272), radius=34, fill=CYAN)
    draw.rectangle((616, 238, 752, 848), fill=CYAN)

    # Central verification check, kept thick enough to survive favicon scaling.
    draw.line((420, 520, 492, 592, 616, 444), fill=WHITE, width=64, joint="curve")
    for x, y in ((420, 520), (492, 592), (616, 444)):
        draw.ellipse((x - 32, y - 32, x + 32, y + 32), fill=WHITE)

    return image


def write_icon(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    master = build_master()
    master.save(output, format="ICO", sizes=[(size, size) for size in ICON_SIZES])
    payload = output.read_bytes()
    if len(payload) < 4096 or not payload.startswith(b"\x00\x00\x01\x00"):
        raise RuntimeError("Generated Windows icon is invalid")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the official ThisTinti Windows icon")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("installer/assets/thistinti.ico"),
        help="Destination ICO path",
    )
    args = parser.parse_args()
    write_icon(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
