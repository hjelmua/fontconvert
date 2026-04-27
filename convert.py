#!/usr/bin/env python3
import subprocess
import sys
import tempfile
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "konvertera"
OUTPUT_DIR = BASE_DIR / "konverterade"

FONTFORGE_SCRIPT = """\
import fontforge, sys, os

input_path = sys.argv[1]
output_dir = sys.argv[2]

fonts_in_file = fontforge.fontsInFile(input_path)
if not fonts_in_file:
    fonts_in_file = [input_path]

for font_ref in fonts_in_file:
    try:
        font = fontforge.open(font_ref)
        if font.bitmapSizes and not any(
            len(g.layers['Fore']) > 0 for g in list(font.glyphs())[:20]
        ):
            print("BITMAP:" + font.fontname)
            font.close()
            continue
        name = font.fontname or os.path.splitext(os.path.basename(input_path))[0]
        out = os.path.join(output_dir, name + ".otf")
        font.generate(out)
        if os.path.exists(out):
            print("OK:" + out)
        else:
            print("FEL:Filen skapades inte: " + out, file=sys.stderr)
        font.close()
    except Exception as e:
        print("FEL:" + str(e), file=sys.stderr)
        sys.exit(1)
"""


def list_fonts():
    return sorted(f for f in INPUT_DIR.iterdir() if not f.name.startswith('.'))


def select_fonts(fonts):
    print("Tillgängliga typsnitt:")
    for i, f in enumerate(fonts, 1):
        print(f"  {i}) {f.name}")
    print()
    while True:
        val = input("Välj (t.ex. 1,3,5 eller 'alla'): ").strip().lower()
        if val == "alla":
            return fonts
        try:
            indices = [int(x.strip()) for x in val.split(",")]
            selected = [fonts[i - 1] for i in indices if 1 <= i <= len(fonts)]
            if selected:
                return selected
        except (ValueError, IndexError):
            pass
        print("Ogiltigt val, försök igen.")


def convert(font_path, tmp_script):
    result = subprocess.run(
        ["fontforge", "-lang", "py", "-script", tmp_script,
         str(font_path), str(OUTPUT_DIR)],
        capture_output=True, text=True
    )
    output = (result.stdout + result.stderr).strip()
    lines = output.splitlines()
    errors = [l for l in lines if l.startswith("FEL:")]
    successes = [l for l in lines if l.startswith("OK:")]
    bitmaps = [l for l in lines if l.startswith("BITMAP:")]

    for line in successes:
        print(f"  -> {Path(line[3:]).name}")
    for line in bitmaps:
        print(f"  (bitmap-font, kan inte konverteras till OTF)")
    for line in errors:
        print(f"  FEL: {line[4:]}")

    if bitmaps and not errors and not successes:
        return None  # varken lyckat eller misslyckat
    return len(errors) == 0


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    fonts = list_fonts()
    if not fonts:
        print("Inga fonter hittades i konvertera/")
        sys.exit(1)

    selected = select_fonts(fonts)
    print()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(FONTFORGE_SCRIPT)
        tmp_script = f.name

    try:
        ok, fail, skip = 0, 0, 0
        for font_path in selected:
            print(f"Konverterar {font_path.name}...")
            result = convert(font_path, tmp_script)
            if result is True:
                ok += 1
            elif result is None:
                skip += 1
            else:
                fail += 1
        parts = [f"{ok} lyckades"]
        if skip:
            parts.append(f"{skip} hoppades över (bitmap)")
        if fail:
            parts.append(f"{fail} misslyckades")
        print(f"\nKlart: {', '.join(parts)}.")
    finally:
        os.unlink(tmp_script)


if __name__ == "__main__":
    main()
