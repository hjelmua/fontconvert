# fontconvert

Konverterar gamla Mac-fonter (LWFN/PostScript Type 1, FFIL-suitcases) till OTF via ett grafiskt gränssnitt.

## Krav

- Python 3
- fontforge
- tkinter

### Installera fontforge

```bash
brew install fontforge
```

### Installera tkinter (Mac)

Python på macOS levereras utan tkinter. Enklaste sättet är att installera Python via Homebrew:

```bash
brew install python-tk
```

Eller om du redan kör Homebrew-Python, verifiera med:

```bash
python3 -c "import tkinter"
```

## Användning

Lägg fonterna som ska konverteras i mappen `konvertera/` och kör:

```bash
python3 convert.py
```

Konverterade OTF-filer sparas i `konverterade/`.

## Notering

Bitmap-fonter (FFIL-suitcases utan vektorkonturer) kan inte konverteras till OTF och hoppas över automatiskt.
