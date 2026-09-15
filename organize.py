#!/usr/bin/env python3
"""Linux file organizer: CLI plus a macOS-inspired tkinter GUI."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

EXTENSION_MAP: dict[str, list[str]] = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp"],
    "Documents": [".pdf", ".docx", ".txt", ".xlsx", ".pptx", ".csv"],
    "Archives": [".zip", ".tar", ".gz", ".7z", ".rar"],
    "Audio": [".mp3", ".wav"],
    "Video": [".mp4", ".mkv", ".mov"],
    "Code": [".py", ".js", ".html", ".css", ".json", ".sh"],
}

EXT_TO_CATEGORY = {
    ext: category for category, extensions in EXTENSION_MAP.items() for ext in extensions
}


def unique_destination(dest_dir: Path, filename: str) -> Path:
    dest = dest_dir / filename
    if not dest.exists():
        return dest
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    n = 1
    while True:
        candidate = dest_dir / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def organize_folder(target_dir: str | os.PathLike[str], log=print) -> int:
    path = Path(target_dir).expanduser().resolve()
    if not path.exists():
        log(f"Error: Directory '{target_dir}' does not exist.")
        return 1
    if not path.is_dir():
        log(f"Error: '{target_dir}' is not a directory.")
        return 1

    moved = 0
    for item in path.iterdir():
        if not item.is_file():
            continue
        ext = item.suffix.lower()
        if ext == "":
            log(f"Skipped (no extension): {item.name}")
            continue
        category = EXT_TO_CATEGORY.get(ext, "Others")
        dest_dir = path / category
        dest_dir.mkdir(exist_ok=True)
        dest = unique_destination(dest_dir, item.name)
        shutil.move(str(item), str(dest))
        if dest.name != item.name:
            log(f"Moved: {item.name} -> {category}/{dest.name} (renamed to avoid overwrite)")
        else:
            log(f"Moved: {item.name} -> {category}/")
        moved += 1

    log(f"Done. Moved {moved} file(s).")
    return 0


def run_cli(target: str | None) -> int:
    if not target:
        target = input("Enter directory path to organize (e.g., ~/Downloads): ").strip()
    if not target:
        print("Error: No directory path given.")
        return 1
    return organize_folder(os.path.expanduser(target))


def run_gui() -> int:
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print("Error: No display found. Use the CLI: python3 organize.py /path/to/folder")
        return 1

    try:
        import tkinter as tk
        from tkinter import filedialog
    except ImportError:
        print(
            "Error: tkinter is not installed. On Debian/Ubuntu run:\n"
            "  sudo apt install python3-tk"
        )
        return 1

    bg = "#ececec"
    card = "#ffffff"
    text = "#1d1d1f"
    muted = "#6e6e73"
    blue = "#007aff"
    window_bg = "#f5f5f7"

    root = tk.Tk()
    root.title("Magor")
    root.configure(bg=window_bg)
    root.minsize(520, 420)
    root.geometry("560x480")

    try:
        ui_font = ("Cantarell", 11)
        title_font = ("Cantarell", 16, "bold")
        mono = ("Ubuntu Mono", 10)
    except tk.TclError:
        ui_font = ("TkDefaultFont", 11)
        title_font = ("TkDefaultFont", 16, "bold")
        mono = ("TkFixedFont", 10)

    chrome = tk.Frame(root, bg=bg, height=36)
    chrome.pack(fill="x")
    chrome.pack_propagate(False)
    lights = tk.Frame(chrome, bg=bg)
    lights.pack(side="left", padx=12, pady=10)
    for color in ("#ff5f57", "#febc2e", "#28c840"):
        canvas = tk.Canvas(lights, width=12, height=12, bg=bg, highlightthickness=0)
        canvas.create_oval(1, 1, 11, 11, fill=color, outline="")
        canvas.pack(side="left", padx=3)
    tk.Label(chrome, text="Magor", bg=bg, fg=text, font=("Cantarell", 11)).pack(side="left", padx=8)

    body = tk.Frame(root, bg=window_bg)
    body.pack(fill="both", expand=True, padx=18, pady=(12, 16))

    card_frame = tk.Frame(body, bg=card, highlightbackground="#d2d2d7", highlightthickness=1)
    card_frame.pack(fill="both", expand=True)

    inner = tk.Frame(card_frame, bg=card)
    inner.pack(fill="both", expand=True, padx=20, pady=18)

    tk.Label(inner, text="Organize a folder", bg=card, fg=text, font=title_font).pack(anchor="w")
    tk.Label(
        inner,
        text="Files are sorted by type. Existing names are never overwritten.",
        bg=card,
        fg=muted,
        font=ui_font,
    ).pack(anchor="w", pady=(4, 14))

    path_row = tk.Frame(inner, bg=card)
    path_row.pack(fill="x")
    path_var = tk.StringVar()
    path_entry = tk.Entry(
        path_row,
        textvariable=path_var,
        font=ui_font,
        relief="flat",
        bg="#f5f5f7",
        fg=text,
        insertbackground=text,
    )
    path_entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))

    def choose_folder() -> None:
        chosen = filedialog.askdirectory(title="Choose a folder to organize")
        if chosen:
            path_var.set(chosen)

    choose_btn = tk.Button(
        path_row,
        text="Choose Folder…",
        font=ui_font,
        bg="#e8e8ed",
        fg=text,
        relief="flat",
        padx=12,
        pady=6,
        command=choose_folder,
        cursor="hand2",
        highlightthickness=0,
    )
    choose_btn.pack(side="right")

    status_var = tk.StringVar(value="Idle")
    log = tk.Text(
        inner,
        height=12,
        font=mono,
        bg="#1d1d1f",
        fg="#f5f5f7",
        relief="flat",
        wrap="word",
        state="disabled",
    )

    def append_log(message: str) -> None:
        log.configure(state="normal")
        log.insert("end", message + "\n")
        log.see("end")
        log.configure(state="disabled")
        root.update_idletasks()

    def organize() -> None:
        target = path_var.get().strip()
        if not target:
            status_var.set("Error: pick a folder first")
            append_log("Error: No folder selected.")
            return
        status_var.set("Working…")
        code = organize_folder(target, log=append_log)
        status_var.set("Done" if code == 0 else "Error")

    organize_btn = tk.Button(
        inner,
        text="Organize",
        font=("Cantarell", 12, "bold"),
        bg=blue,
        fg="white",
        activebackground="#0066d6",
        activeforeground="white",
        relief="flat",
        padx=22,
        pady=8,
        command=organize,
        cursor="hand2",
        highlightthickness=0,
    )
    organize_btn.pack(anchor="w", pady=(14, 10))

    log.pack(fill="both", expand=True)
    tk.Label(inner, textvariable=status_var, bg=card, fg=muted, font=ui_font).pack(anchor="w", pady=(8, 0))

    root.mainloop()
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sort files in a folder by type.")
    parser.add_argument("path", nargs="?", help="Directory to organize")
    parser.add_argument("--gui", action="store_true", help="Open the macOS-style Linux GUI")
    parser.add_argument("--cli", action="store_true", help="Prompt for a path in the terminal")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    if args.gui:
        return run_gui()
    if args.path:
        return organize_folder(os.path.expanduser(args.path))
    if args.cli or not has_display:
        return run_cli(None)
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
