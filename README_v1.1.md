# Magor

**Version 1.1**

Linux desktop file organizer. Magor sorts files into categories such as Images, Documents, Archives, Audio, Video, Code, Fonts, and Design, while protecting existing files from being overwritten.

## What's New in v1.1

- Recursive folder scanning with `--recursive` / `-r`
- Optional hidden-file support with `--hidden`
- Safe preview mode with `--dry-run` / `-n`
- Duplicate detection using file size grouping and SHA-256
- Undo the last organization with `--undo`
- Collision-safe filenames such as `report_1.pdf`
- Improved file-type detection with more extensions and categories
- GUI preview table showing file name, category, size, and duplicate status
- File count, total size, and duplicate statistics
- Progress bar for scanning and organization
- Background processing so large scans do not block the GUI
- Improved error handling for filesystem operations
- Updated GUI with Scan, Organize, and Undo controls

## Requirements

- Python 3
- `python3-tk` for the GUI (`sudo apt install python3-tk` on Debian/Ubuntu)

## GUI

Launch the graphical interface:

```bash
python3 organize.py --gui
```

Or, if the script is executable:

```bash
./organize.py
```

### Basic workflow

1. Choose a folder.
2. Click **Scan** to inspect its files.
3. Review the categories, sizes, and duplicate status.
4. Use **Preview only** if you want to see the planned changes without moving files.
5. Click **Organize** to sort the files.
6. Use **Undo Last** to reverse the most recent organization.

### GUI options

- **Scan subfolders** — include files inside nested directories.
- **Include hidden files** — include hidden files and directories.
- **Preview only (no moves)** — calculate and display the organization without changing files.

## Categories

Magor currently recognizes:

| Category | Examples |
|---|---|
| Images | JPG, PNG, GIF, SVG, WEBP, BMP, TIFF, ICO, HEIC, AVIF |
| Documents | PDF, DOCX, TXT, XLSX, CSV, PPTX, Markdown, ODT |
| Archives | ZIP, TAR, GZ, 7Z, RAR, ISO, DEB, RPM |
| Audio | MP3, WAV, FLAC, OGG, M4A, AAC, OPUS |
| Video | MP4, MKV, MOV, AVI, WEBM, FLV, WMV |
| Code | Python, JavaScript, TypeScript, HTML, CSS, JSON, Shell, C/C++, Java, Rust, Go, PHP, SQL |
| Fonts | TTF, OTF, WOFF, WOFF2 |
| Design | PSD, AI, EPS, FIG, SKETCH, XD |
| Others | File types not recognized by the extension map |

## CLI

Organize a directory:

```bash
python3 organize.py ~/Downloads
```

Use interactive CLI mode:

```bash
python3 organize.py --cli
```

Preview changes without moving anything:

```bash
python3 organize.py ~/Downloads --dry-run
```

Include subfolders:

```bash
python3 organize.py ~/Downloads --recursive
```

Include hidden files:

```bash
python3 organize.py ~/Downloads --hidden
```

Combine options:

```bash
python3 organize.py ~/Downloads --recursive --hidden --dry-run
```

## Undo

Magor stores the most recent move history in `.magor_undo.json`.

Undo the last organization:

```bash
python3 organize.py ~/Downloads --undo
```

Magor restores files to their original locations when possible. If a file with the original name already exists, it avoids overwriting it.

## Duplicate Detection

v1.1 can identify duplicate files.

Magor first groups files by size. Only files with matching sizes are hashed with SHA-256, reducing unnecessary hashing for large folders.

The GUI reports the number of files that belong to duplicate groups.

## Safety

Magor is designed to avoid accidental overwrites:

- Existing destination names are never replaced.
- Conflicting names receive a numeric suffix.
- `--dry-run` allows changes to be reviewed before execution.
- The previous organization can be reversed with `--undo`.
- Files without recognized extensions are placed in `Others`.

Always review a dry run before organizing an important directory.

## Project Structure

```text
Magor/
├── organize.py
├── magor_icon.png
└── README.md
```

## Version

**Magor 1.1**

This release focuses on safer file operations, better visibility into what will be organized, duplicate detection, undo support, and a more capable GUI.
