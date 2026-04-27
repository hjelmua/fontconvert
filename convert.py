#!/usr/bin/env python3
import os
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

        ttk.Button(control_frame, text="Välj alla", command=self.select_all).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(control_frame, text="Avmarkera alla", command=self.deselect_all).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            control_frame, text="Konvertera valda", command=self.convert_selected
        ).pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="Laddar typsnitt…")
        ttk.Label(main_frame, textvariable=self.status_var).grid(
            row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5
        )

    def load_fonts(self):
        if not INPUT_DIR.exists():
            messagebox.showerror("Fel", f"Mappen '{INPUT_DIR}' hittades inte.")
            return
        self.fonts = sorted(f for f in INPUT_DIR.iterdir() if not f.name.startswith("."))
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
        for name, (_, var) in self.font_checkboxes.items():
            if var.get():
                self.selected_names.add(name)
            else:
                self.selected_names.discard(name)

        selected = [f for f in self.fonts if f.name in self.selected_names]
        if not selected:
            messagebox.showwarning("Ingen markerad", "Markera minst ett typsnitt.")
            return

        threading.Thread(target=self._run_conversion, args=(selected,), daemon=True).start()

    def _run_conversion(self, selected):
        OUTPUT_DIR.mkdir(exist_ok=True)
        self.root.after(0, self.status_var.set, "Konverterar…")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(FONTFORGE_SCRIPT)
            tmp_script = f.name

        try:
            ok, fail, skip = 0, 0, 0
            for font_path in selected:
                self.root.after(0, self.status_var.set, f"Konverterar {font_path.name}…")
                result = subprocess.run(
                    ["fontforge", "-lang", "py", "-script", tmp_script,
                     str(font_path), str(OUTPUT_DIR)],
                    capture_output=True, text=True,
                )
                lines = (result.stdout + result.stderr).splitlines()
                if any(l.startswith("FEL:") for l in lines):
                    fail += 1
                elif any(l.startswith("BITMAP:") for l in lines):
                    skip += 1
                else:
                    ok += 1
        finally:
            os.unlink(tmp_script)

        parts = [f"{ok} lyckades"]
        if skip:
            parts.append(f"{skip} bitmap (hoppades över)")
        if fail:
            parts.append(f"{fail} misslyckades")
        msg = "Klart: " + ", ".join(parts) + "."
        self.root.after(0, self.status_var.set, msg)
        self.root.after(0, messagebox.showinfo, "Klart", msg)


def main():
    root = tk.Tk()
    FontConverterGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
