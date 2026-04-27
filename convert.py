#!/usr/bin/env python3
import os
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "konvertera"
OUTPUT_DIR = BASE_DIR / "konverterade"

FONTFORGE_SCRIPT = """\
import fontforge, sys, os, re

input_path = sys.argv[1]
output_dir = sys.argv[2]

def safe_name(name):
    name = name or os.path.splitext(os.path.basename(input_path))[0]
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" ._")
    return name or "font"

def unique_path(output_dir, name):
    candidate = os.path.join(output_dir, name + ".otf")
    if not os.path.exists(candidate):
        return candidate

    counter = 2
    while True:
        candidate = os.path.join(output_dir, "{}-{}.otf".format(name, counter))
        if not os.path.exists(candidate):
            return candidate
        counter += 1

def has_vector_outlines(font):
    for glyph in font.glyphs():
        try:
            if len(glyph.layers["Fore"]) > 0:
                return True
        except Exception:
            continue
    return False

try:
    fonts_in_file = fontforge.fontsInFile(input_path)
    if not fonts_in_file:
        fonts_in_file = [input_path]

    for font_ref in fonts_in_file:
        font = None
        try:
            font = fontforge.open(font_ref)
            if font.bitmapSizes and not has_vector_outlines(font):
                print("BITMAP:" + (font.fontname or os.path.basename(input_path)))
                continue
            name = safe_name(font.fontname)
            out = unique_path(output_dir, name)
            font.generate(out)
            if os.path.exists(out):
                print("OK:" + out)
            else:
                print("FEL:Filen skapades inte: " + out, file=sys.stderr)
        finally:
            if font is not None:
                font.close()
except Exception as e:
    print("FEL:" + str(e), file=sys.stderr)
    sys.exit(1)
"""


class FontConverterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Font Converter")
        self.root.geometry("500x450")

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.on_search_change)
        self.fonts = []
        self.font_checkboxes = {}
        self.selected_names = set()
        self.is_converting = False

        self.setup_gui()
        self.load_fonts()

    def setup_gui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        ttk.Label(main_frame, text="Sök typsnitt:").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.search_var).grid(
            row=0, column=1, sticky=(tk.W, tk.E), padx=5
        )

        list_frame = ttk.Frame(main_frame)
        list_frame.grid(
            row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10
        )
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, columnspan=2, pady=10)

        ttk.Button(control_frame, text="Välj synliga", command=self.select_all).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            control_frame, text="Avmarkera synliga", command=self.deselect_all
        ).pack(
            side=tk.LEFT, padx=5
        )
        self.convert_button = ttk.Button(
            control_frame, text="Konvertera valda", command=self.convert_selected
        )
        self.convert_button.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="Laddar typsnitt…")
        ttk.Label(main_frame, textvariable=self.status_var).grid(
            row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )

    def load_fonts(self):
        if not INPUT_DIR.exists():
            messagebox.showerror("Fel", f"Mappen '{INPUT_DIR}' hittades inte.")
            return
        self.fonts = sorted(
            f for f in INPUT_DIR.iterdir() if f.is_file() and not f.name.startswith(".")
        )
        self.display_fonts()
        self.status_var.set(f"{len(self.fonts)} typsnitt hittades i konvertera/")

    def on_search_change(self, *args):
        self.display_fonts(self.search_var.get())

    def display_fonts(self, filter_text=""):
        for name, (_, var) in self.font_checkboxes.items():
            if var.get():
                self.selected_names.add(name)
            else:
                self.selected_names.discard(name)

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.font_checkboxes.clear()

        for i, font_path in enumerate(self.fonts):
            if filter_text.lower() in font_path.name.lower():
                var = tk.BooleanVar(value=font_path.name in self.selected_names)
                var.trace_add(
                    "write",
                    lambda *_, n=font_path.name, v=var: self._on_checkbox(n, v),
                )
                ttk.Checkbutton(
                    self.scrollable_frame, text=font_path.name, variable=var
                ).grid(row=i, column=0, sticky=tk.W)
                self.font_checkboxes[font_path.name] = (None, var)

    def _on_checkbox(self, name, var):
        if var.get():
            self.selected_names.add(name)
        else:
            self.selected_names.discard(name)

    def select_all(self):
        for _, (_, var) in self.font_checkboxes.items():
            var.set(True)

    def deselect_all(self):
        for _, (_, var) in self.font_checkboxes.items():
            var.set(False)

    def convert_selected(self):
        if self.is_converting:
            return

        if not shutil.which("fontforge"):
            messagebox.showerror(
                "FontForge saknas",
                "FontForge hittades inte. Installera med exempelvis: brew install fontforge",
            )
            return

        for name, (_, var) in self.font_checkboxes.items():
            if var.get():
                self.selected_names.add(name)
            else:
                self.selected_names.discard(name)

        selected = [f for f in self.fonts if f.name in self.selected_names]
        if not selected:
            messagebox.showwarning("Ingen markerad", "Markera minst ett typsnitt.")
            return

        self.is_converting = True
        self.convert_button.configure(state=tk.DISABLED)
        threading.Thread(target=self._run_conversion, args=(selected,), daemon=True).start()

    def _run_conversion(self, selected):
        tmp_script = None

        try:
            OUTPUT_DIR.mkdir(exist_ok=True)
            self.root.after(0, self.status_var.set, "Konverterar…")
            log_path = OUTPUT_DIR / "conversion.log"

            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(FONTFORGE_SCRIPT)
                tmp_script = f.name

            ok_files = []
            failed_files = []
            skipped_files = []
            for font_path in selected:
                self.root.after(0, self.status_var.set, f"Konverterar {font_path.name}…")
                result = subprocess.run(
                    [
                        "fontforge",
                        "-lang",
                        "py",
                        "-script",
                        tmp_script,
                        str(font_path),
                        str(OUTPUT_DIR),
                    ],
                    capture_output=True, text=True,
                )
                lines = (result.stdout + result.stderr).splitlines()
                errors = [l[4:] for l in lines if l.startswith("FEL:")]
                bitmaps = [l[7:] for l in lines if l.startswith("BITMAP:")]
                outputs = [l[3:] for l in lines if l.startswith("OK:")]

                if result.returncode != 0 or errors:
                    detail = errors[-1] if errors else self._last_output_line(result)
                    failed_files.append((font_path.name, detail))
                else:
                    if outputs:
                        ok_files.append((font_path.name, outputs))
                    if bitmaps:
                        skipped_files.append((font_path.name, ", ".join(bitmaps)))
                    if not outputs and not bitmaps:
                        failed_files.append((font_path.name, "FontForge skapade ingen output."))

            self._write_log(log_path, ok_files, skipped_files, failed_files)

            parts = [f"{len(ok_files)} lyckades"]
            if skipped_files:
                parts.append(f"{len(skipped_files)} bitmap (hoppades över)")
            if failed_files:
                parts.append(f"{len(failed_files)} misslyckades")
            msg = "Klart: " + ", ".join(parts) + "."
            details = self._summary_details(msg, skipped_files, failed_files, log_path)
            self.root.after(0, self.status_var.set, msg)
            self.root.after(0, messagebox.showinfo, "Klart", details)
        except Exception as e:
            msg = f"Konverteringen avbröts: {e}"
            self.root.after(0, self.status_var.set, msg)
            self.root.after(0, messagebox.showerror, "Fel", msg)
        finally:
            if tmp_script and os.path.exists(tmp_script):
                os.unlink(tmp_script)
            self.root.after(0, self._finish_conversion)

    def _finish_conversion(self):
        self.is_converting = False
        self.convert_button.configure(state=tk.NORMAL)

    def _last_output_line(self, result):
        lines = (result.stderr or result.stdout or "").splitlines()
        return lines[-1] if lines else f"FontForge avslutades med kod {result.returncode}"

    def _write_log(self, log_path, ok_files, skipped_files, failed_files):
        with log_path.open("w", encoding="utf-8") as log:
            log.write("Fontkonvertering\n")
            log.write("================\n\n")

            log.write("Lyckades\n")
            for name, outputs in ok_files:
                log.write(f"- {name}\n")
                for output in outputs:
                    log.write(f"  -> {output}\n")
            if not ok_files:
                log.write("- Inga\n")

            log.write("\nHoppades över\n")
            for name, detail in skipped_files:
                log.write(f"- {name}: bitmapfont")
                if detail:
                    log.write(f" ({detail})")
                log.write("\n")
            if not skipped_files:
                log.write("- Inga\n")

            log.write("\nMisslyckades\n")
            for name, detail in failed_files:
                log.write(f"- {name}: {detail}\n")
            if not failed_files:
                log.write("- Inga\n")

    def _summary_details(self, msg, skipped_files, failed_files, log_path):
        details = [msg]
        if failed_files:
            details.append("")
            details.append("Misslyckades:")
            for name, detail in failed_files[:5]:
                details.append(f"- {name}: {detail}")
            if len(failed_files) > 5:
                details.append(f"- ... och {len(failed_files) - 5} till")
        if skipped_files:
            details.append("")
            details.append(
                f"{len(skipped_files)} bitmapfont(er) hoppades över. Se loggen för namn."
            )
        details.append("")
        details.append(f"Detaljer finns i {log_path}")
        return "\n".join(details)


def main():
    root = tk.Tk()
    FontConverterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
