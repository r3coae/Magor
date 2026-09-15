# Magor

Linux desktop file organizer. Sorts files in a folder into Images, Documents, Archives, Audio, Video, Code, and Others. Duplicate names are renamed (`report_1.pdf`) instead of overwritten.

## Requirements

- Python 3
- `python3-tk` for the GUI (`sudo apt install python3-tk` on Debian/Ubuntu)

## GUI (macOS-style window on Linux)

```bash
python3 organize.py --gui
./organize.py
```

Pick a folder, then Organize. Logs show each move.

## CLI

```bash
python3 organize.py ~/Downloads
python3 organize.py --cli
```

Only the chosen directory is scanned. Subfolders are skipped.
