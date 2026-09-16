#!/usr/bin/env python3
"""
Magor - Smart File Organizer

CLI + Tkinter GUI (macOS-inspired look: rounded cards, toggle switches,
a flat accent progress bar, and a system-font-aware type scale).

Features:
- Fast file scanning with recursive mode
- Extension-based smart categorization
- Dry-run preview before moving anything
- Collision-safe renaming
- Duplicate detection with SHA-256
- Undo the last organization
- Progress bar, statistics, preview table and activity log
- CLI and GUI modes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import shutil
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

# Tkinter is optional: the CLI must keep working on systems where it isn't
# installed (e.g. headless servers). Everything GUI-related below is only
# defined when the import actually succeeds - see the `if tk is not None:`
# block further down.
try:
    import tkinter as tk
    from tkinter import font as tkfont
    from tkinter import ttk
except ImportError:  # pragma: no cover - exercised only without Tk installed
    tk = None
    tkfont = None
    ttk = None


APP_NAME = "Magor"
UNDO_FILE = ".magor_undo.json"
CHUNK_SIZE = 1024 * 1024

EXTENSION_MAP: dict[str, list[str]] = {
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp",
        ".tiff", ".tif", ".ico", ".heic", ".avif",
    ],
    "Documents": [
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md",
        ".xlsx", ".xls", ".ods", ".csv", ".ppt", ".pptx", ".odp",
    ],
    "Archives": [
        ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
        ".iso", ".deb", ".rpm",
    ],
    "Audio": [
        ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma",
    ],
    "Video": [
        ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v",
    ],
    "Code": [
        ".py", ".pyw", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm",
        ".css", ".scss", ".sass", ".json", ".xml", ".yaml", ".yml",
        ".sh", ".bash", ".zsh", ".fish", ".c", ".h", ".cpp", ".hpp",
        ".java", ".kt", ".rs", ".go", ".php", ".rb", ".sql",
    ],
    "Fonts": [
        ".ttf", ".otf", ".woff", ".woff2",
    ],
    "Design": [
        ".psd", ".ai", ".eps", ".fig", ".sketch", ".xd",
    ],
}

EXT_TO_CATEGORY = {
    ext: category
    for category, extensions in EXTENSION_MAP.items()
    for ext in extensions
}


@dataclass
class FileRecord:
    source: str
    name: str
    category: str
    size: int
    modified: float
    duplicate: bool = False


@dataclass
class MoveRecord:
    source: str
    destination: str


@dataclass
class ScanResult:
    path: str
    files: list[FileRecord]
    total_size: int
    duplicates: int
    errors: list[str]


def format_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def category_for(path: Path) -> str:
    return EXT_TO_CATEGORY.get(path.suffix.lower(), "Others")


def unique_destination(dest_dir: Path, filename: str) -> Path:
    """Return a collision-safe destination without overwriting an existing file."""
    dest = dest_dir / filename
    if not dest.exists():
        return dest

    original = Path(filename)
    stem = original.stem
    suffix = original.suffix
    number = 1

    while True:
        candidate = dest_dir / f"{stem}_{number}{suffix}"
        if not candidate.exists():
            return candidate
        number += 1


def iter_files(path: Path, recursive: bool, include_hidden: bool):
    """Yield files while avoiding the organizer's own generated folders."""
    iterator = path.rglob("*") if recursive else path.iterdir()

    for item in iterator:
        try:
            if not item.is_file():
                continue
            if item.name == UNDO_FILE:
                continue
            if not include_hidden and any(part.startswith(".") for part in item.relative_to(path).parts):
                continue
            yield item
        except OSError:
            continue


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def scan_folder(
    target_dir: str | os.PathLike[str],
    recursive: bool = False,
    include_hidden: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> ScanResult:
    path = Path(target_dir).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"Directory does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    candidates = list(iter_files(path, recursive, include_hidden))
    total = len(candidates)
    files: list[FileRecord] = []
    errors: list[str] = []

    # Duplicate detection uses a cheap size grouping first, then SHA-256 only
    # for files that share a size. This avoids hashing every file unnecessarily.
    size_groups: dict[int, list[Path]] = {}
    for index, item in enumerate(candidates, start=1):
        try:
            stat = item.stat()
            record = FileRecord(
                source=str(item),
                name=item.name,
                category=category_for(item),
                size=stat.st_size,
                modified=stat.st_mtime,
            )
            files.append(record)
            size_groups.setdefault(stat.st_size, []).append(item)
        except OSError as exc:
            errors.append(f"{item.name}: {exc}")

        if progress:
            progress(index, total)

    hashes: dict[str, list[Path]] = {}
    for same_size in size_groups.values():
        if len(same_size) < 2:
            continue

        for item in same_size:
            try:
                digest = sha256_file(item)
                hashes.setdefault(digest, []).append(item)
            except OSError as exc:
                errors.append(f"{item.name}: {exc}")

    duplicate_paths = {
        str(item)
        for group in hashes.values()
        if len(group) > 1
        for item in group
    }

    for record in files:
        record.duplicate = record.source in duplicate_paths

    return ScanResult(
        path=str(path),
        files=files,
        total_size=sum(item.size for item in files),
        duplicates=len(duplicate_paths),
        errors=errors,
    )


def organize_folder(
    target_dir: str | os.PathLike[str],
    recursive: bool = False,
    include_hidden: bool = False,
    dry_run: bool = False,
    log: Callable[[str], None] = print,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[int, list[MoveRecord]]:
    """
    Organize files into category folders.

    Returns:
        (number_of_moves, move_history)
    """
    path = Path(target_dir).expanduser().resolve()
    result = scan_folder(
        path,
        recursive=recursive,
        include_hidden=include_hidden,
        progress=progress,
    )

    moves: list[MoveRecord] = []
    total = len(result.files)

    if total == 0:
        log("No files found to organize.")
        return 0, moves

    for index, record in enumerate(result.files, start=1):
        source = Path(record.source)

        # In recursive mode, moving a file from a nested directory to the
        # root category folder is intentional: the root becomes organized.
        dest_dir = path / record.category
        destination = unique_destination(dest_dir, source.name)

        if dry_run:
            log(f"[PREVIEW] {source.name} -> {record.category}/{destination.name}")
        else:
            try:
                dest_dir.mkdir(exist_ok=True)
                shutil.move(str(source), str(destination))
                moves.append(MoveRecord(str(source), str(destination)))

                suffix = ""
                if destination.name != source.name:
                    suffix = " (renamed to avoid overwrite)"
                log(f"Moved: {source.name} -> {record.category}/{destination.name}{suffix}")
            except OSError as exc:
                log(f"ERROR: {source.name}: {exc}")

        if progress:
            progress(index, total)

    if not dry_run and moves:
        save_undo_history(path, moves)

    log(
        f"Done. {'Would move' if dry_run else 'Moved'} "
        f"{len(moves) if not dry_run else total} file(s)."
    )
    return (total if dry_run else len(moves)), moves


def save_undo_history(path: Path, moves: list[MoveRecord]) -> None:
    payload = {
        "created_at": time.time(),
        "moves": [asdict(move) for move in moves],
    }
    undo_path = path / UNDO_FILE
    undo_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def undo_last(target_dir: str | os.PathLike[str], log: Callable[[str], None] = print) -> int:
    """Reverse the most recent organization, if its destinations still exist."""
    path = Path(target_dir).expanduser().resolve()
    undo_path = path / UNDO_FILE

    if not undo_path.exists():
        log("Nothing to undo.")
        return 0

    try:
        payload = json.loads(undo_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log(f"Cannot read undo history: {exc}")
        return 1

    moves = payload.get("moves", [])
    restored = 0

    for move in reversed(moves):
        source = Path(move["source"])
        destination = Path(move["destination"])

        if not destination.exists():
            log(f"Skipped: missing {destination}")
            continue

        try:
            source.parent.mkdir(parents=True, exist_ok=True)
            restore_target = source

            # If something was created at the original location after the
            # organization, never overwrite it.
            if restore_target.exists():
                restore_target = unique_destination(source.parent, source.name)

            shutil.move(str(destination), str(restore_target))
            restored += 1
            log(f"Restored: {destination.name} -> {restore_target}")
        except OSError as exc:
            log(f"ERROR restoring {destination}: {exc}")

    try:
        undo_path.unlink()
    except OSError:
        pass

    log(f"Undo complete. Restored {restored} file(s).")
    return restored


def run_cli(args: argparse.Namespace) -> int:
    target = args.path
    if not target:
        target = input("Enter directory path to organize: ").strip()
    if not target:
        print("Error: no directory path given.")
        return 1

    if args.undo:
        return 0 if undo_last(target) >= 0 else 1

    try:
        moved, _ = organize_folder(
            target,
            recursive=args.recursive,
            include_hidden=args.hidden,
            dry_run=args.dry_run,
        )
        print(f"Result: {moved} file(s).")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}")
        return 1


# ---------------------------------------------------------------------------
# macOS-inspired GUI
#
# Tk/ttk have no native support for rounded corners, translucency, or
# animated toggle switches, so the pieces below draw them directly on a
# Canvas using only the standard library - no extra dependencies, so the
# CLI keeps working anywhere even if this whole block never runs.
# ---------------------------------------------------------------------------

if tk is not None:

    DISPLAY_FONT_CANDIDATES = [
        "SF Pro Display", ".AppleSystemUIFont", "Helvetica Neue",
        "Segoe UI Semibold", "Inter", "Cantarell", "Noto Sans", "Helvetica",
    ]
    TEXT_FONT_CANDIDATES = [
        "SF Pro Text", ".AppleSystemUIFont", "Helvetica Neue",
        "Segoe UI", "Inter", "Cantarell", "Noto Sans", "Helvetica",
    ]

    def pick_font_family(root, candidates: list[str]) -> str:
        """Return the first available font family, falling back to the last
        (most broadly available) candidate if none of the preferred ones exist."""
        try:
            available = {name.lower() for name in tkfont.families(root)}
        except tk.TclError:
            available = set()
        for name in candidates:
            if name.lower() in available:
                return name
        return candidates[-1]

    def hex_to_rgb(value: str) -> tuple[int, int, int]:
        value = value.lstrip("#")
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))

    def lerp_color(color_a: str, color_b: str, t: float) -> str:
        """Linearly interpolate between two '#rrggbb' colors."""
        t = max(0.0, min(1.0, t))
        a = hex_to_rgb(color_a)
        b = hex_to_rgb(color_b)
        mixed = tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))
        return "#%02x%02x%02x" % mixed

    def _rounded_rect_points(x1, y1, x2, y2, radius):
        """Point list for a rounded rectangle, meant for create_polygon(smooth=True)."""
        radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
        return [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]

    def draw_rounded_rect(canvas, x1, y1, x2, y2, radius=12, **kwargs):
        """Draw a rounded rectangle on a Canvas and return its item id."""
        points = _rounded_rect_points(x1, y1, x2, y2, radius)
        return canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)

    class RoundedCard(tk.Frame):
        """A container with a flat, rounded-corner background.

        Regular widgets are packed/gridded into `.inner`; the rounded
        background redraws itself automatically whenever the card resizes.
        Call `.fit_to_content()` once all children have been added to size
        the card's height to exactly fit them (skip this for a card that
        should stretch to fill its parent's leftover space instead).
        """

        def __init__(self, parent, fill="#ffffff", border="#e5e5ea", radius=14):
            super().__init__(parent, bg=parent["bg"])
            self.fill = fill
            self.border = border
            self.radius = radius
            self._fixed_height = None

            self.canvas = tk.Canvas(self, bg=parent["bg"], highlightthickness=0, height=2)
            self.canvas.pack(fill="both", expand=True)

            self.inner = tk.Frame(self.canvas, bg=fill)
            self._window = self.canvas.create_window(1, 1, window=self.inner, anchor="nw")
            self.canvas.bind("<Configure>", self._on_resize)

        def _on_resize(self, event):
            w, h = event.width, event.height
            self.canvas.delete("bg")
            if w > 2 and h > 2:
                draw_rounded_rect(
                    self.canvas, 1, 1, w - 1, h - 1, self.radius,
                    fill=self.fill, outline=self.border, width=1, tags="bg",
                )
                self.canvas.tag_lower("bg")
            self.canvas.itemconfig(self._window, width=max(w - 2, 1))
            if self._fixed_height is None:
                self.canvas.itemconfig(self._window, height=max(h - 2, 1))
            else:
                self.canvas.itemconfig(self._window, height=max(self._fixed_height - 2, 1))

        def fit_to_content(self):
            self.inner.update_idletasks()
            self._fixed_height = self.inner.winfo_reqheight() + 2
            self.canvas.configure(height=self._fixed_height)

    class MacButton(tk.Canvas):
        """A flat, rounded push button drawn on a Canvas (macOS-style)."""

        _PALETTES = {
            "primary": dict(fill="#007aff", hover="#0069d9", press="#0058b8",
                             fg="#ffffff", outline=""),
            "secondary": dict(fill="#ffffff", hover="#f2f2f7", press="#e5e5ea",
                               fg="#1d1d1f", outline="#d2d2d7"),
            "destructive": dict(fill="#ffffff", hover="#fff1f0", press="#ffe1df",
                                 fg="#ff3b30", outline="#ffd0cd"),
        }

        def __init__(self, parent, text, command=None, variant="secondary",
                     font=("Helvetica", 11), height=32, width=None, padx=18):
            self.text = text
            self.command = command
            self.palette = self._PALETTES.get(variant, self._PALETTES["secondary"])
            self.font = font
            self.enabled = True
            self.hover = False
            self.pressed = False

            measured = tkfont.Font(font=font).measure(text)
            final_width = width or (measured + padx * 2)

            super().__init__(
                parent, width=final_width, height=height, bg=parent["bg"],
                highlightthickness=0, cursor="hand2",
            )

            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)
            self.bind("<ButtonPress-1>", self._on_press)
            self.bind("<ButtonRelease-1>", self._on_release)
            self.bind("<Configure>", lambda _e: self._draw())
            self._draw()

        def _draw(self):
            self.delete("all")
            w = self.winfo_width()
            if w <= 1:
                w = int(self["width"])
            h = self.winfo_height()
            if h <= 1:
                h = int(self["height"])

            pal = self.palette
            if not self.enabled:
                fill, fg, outline = "#f2f2f2", "#b3b3b8", pal["outline"]
            elif self.pressed:
                fill, fg, outline = pal["press"], pal["fg"], pal["outline"]
            elif self.hover:
                fill, fg, outline = pal["hover"], pal["fg"], pal["outline"]
            else:
                fill, fg, outline = pal["fill"], pal["fg"], pal["outline"]

            draw_rounded_rect(self, 1, 1, w - 1, h - 1, radius=8,
                               fill=fill, outline=outline, width=1)
            self.create_text(w / 2, h / 2, text=self.text, fill=fg, font=self.font)

        def _on_enter(self, _event):
            if self.enabled:
                self.hover = True
                self._draw()

        def _on_leave(self, _event):
            self.hover = False
            self.pressed = False
            self._draw()

        def _on_press(self, _event):
            if self.enabled:
                self.pressed = True
                self._draw()

        def _on_release(self, event):
            fired = self.enabled and self.pressed
            self.pressed = False
            self._draw()
            inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
            if fired and inside and self.command:
                self.command()

        def set_enabled(self, enabled: bool):
            self.enabled = enabled
            self.configure(cursor="hand2" if enabled else "arrow")
            self._draw()

    class MacToggle(tk.Canvas):
        """An animated iOS/macOS-style toggle switch bound to a BooleanVar."""

        WIDTH = 42
        HEIGHT = 24
        OFF_COLOR = "#e9e9eb"
        ON_COLOR = "#34c759"

        def __init__(self, parent, variable, command=None):
            super().__init__(
                parent, width=self.WIDTH, height=self.HEIGHT, bg=parent["bg"],
                highlightthickness=0, cursor="hand2",
            )
            self.var = variable
            self.command = command
            self.pos = 1.0 if self.var.get() else 0.0
            self._anim_id = None
            self.bind("<Button-1>", self._toggle)
            self._draw()

        def _toggle(self, _event=None):
            self.var.set(not self.var.get())
            self._animate_to(1.0 if self.var.get() else 0.0)
            if self.command:
                self.command()

        def _animate_to(self, target):
            if self._anim_id is not None:
                self.after_cancel(self._anim_id)
                self._anim_id = None

            def step():
                diff = target - self.pos
                if abs(diff) < 0.02:
                    self.pos = target
                    self._draw()
                    self._anim_id = None
                    return
                self.pos += diff * 0.45
                self._draw()
                self._anim_id = self.after(12, step)

            step()

        def _draw(self):
            self.delete("all")
            w, h = self.WIDTH, self.HEIGHT
            track_color = lerp_color(self.OFF_COLOR, self.ON_COLOR, self.pos)
            draw_rounded_rect(self, 1, 1, w - 1, h - 1, radius=h / 2,
                               fill=track_color, outline="")
            knob_r = (h - 6) / 2
            knob_x = 3 + knob_r + self.pos * (w - h)
            knob_y = h / 2
            self.create_oval(
                knob_x - knob_r, knob_y - knob_r, knob_x + knob_r, knob_y + knob_r,
                fill="#ffffff", outline="#d8d8dc",
            )

    class MacProgressBar(tk.Canvas):
        """A thin, flat, rounded progress bar (macOS-style)."""

        def __init__(self, parent, height=6, track="#e5e5ea", fill="#007aff"):
            super().__init__(parent, height=height, bg=parent["bg"], highlightthickness=0)
            self.track = track
            self.fill = fill
            self.fraction = 0.0
            self.bind("<Configure>", lambda _e: self._draw())
            self._draw()

        def set_progress(self, fraction: float):
            self.fraction = max(0.0, min(1.0, fraction))
            self._draw()

        def _draw(self):
            self.delete("all")
            w = max(self.winfo_width(), 1)
            h = max(self.winfo_height(), 1)
            draw_rounded_rect(self, 0, 0, w, h, radius=h / 2, fill=self.track, outline="")
            if self.fraction > 0:
                fw = max(h, w * self.fraction)
                draw_rounded_rect(self, 0, 0, fw, h, radius=h / 2, fill=self.fill, outline="")

    class MagorGUI:
        """Tkinter GUI. All heavy filesystem work runs off the UI thread."""

        def __init__(self, root):
            self.root = root
            self.root.title(APP_NAME)
            self.root.geometry("980x720")
            self.root.minsize(840, 600)

            self.bg = "#eceef1"
            self.card = "#ffffff"
            self.card_border = "#e3e3e8"
            self.text = "#1d1d1f"
            self.muted = "#6e6e73"
            self.blue = "#007aff"
            self.green = "#34c759"
            self.red = "#ff3b30"
            self.divider = "#e5e5ea"

            self.root.configure(bg=self.bg)

            self.display_family = pick_font_family(self.root, DISPLAY_FONT_CANDIDATES)
            self.text_family = pick_font_family(self.root, TEXT_FONT_CANDIDATES)

            self.font_title = (self.display_family, 26, "bold")
            self.font_subtitle = (self.text_family, 12)
            self.font_section = (self.text_family, 10, "bold")
            self.font_body = (self.text_family, 11)
            self.font_body_bold = (self.text_family, 11, "bold")
            self.font_stat_label = (self.text_family, 10, "bold")
            self.font_stat_value = (self.text_family, 19, "bold")
            self.font_button = (self.text_family, 11, "bold")
            self.font_small = (self.text_family, 9)

            self.events: queue.Queue = queue.Queue()
            self.busy = False
            self.current_scan: ScanResult | None = None

            self.path_var = tk.StringVar()
            self.status_var = tk.StringVar(value="Ready")
            self.files_var = tk.StringVar(value="0")
            self.size_var = tk.StringVar(value="0 B")
            self.duplicate_var = tk.StringVar(value="0")
            self.recursive_var = tk.BooleanVar(value=False)
            self.hidden_var = tk.BooleanVar(value=False)
            self.dry_run_var = tk.BooleanVar(value=False)

            self._setup_style()
            self._build()
            self._set_icon()
            self.root.after(100, self._poll_events)

        def _setup_style(self):
            style = ttk.Style()
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass

            style.configure(
                "Treeview",
                background=self.card,
                fieldbackground=self.card,
                foreground=self.text,
                rowheight=32,
                borderwidth=0,
                font=self.font_body,
            )
            style.configure(
                "Treeview.Heading",
                background="#f5f5f7",
                foreground=self.muted,
                relief="flat",
                borderwidth=0,
                font=self.font_section,
            )
            style.map("Treeview.Heading", background=[("active", "#f5f5f7")])
            style.map(
                "Treeview",
                background=[("selected", self.blue)],
                foreground=[("selected", "#ffffff")],
            )
            # Drop the default themed border so the tree blends into its card.
            try:
                style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
            except tk.TclError:
                pass

            style.configure(
                "Vertical.TScrollbar",
                background=self.bg,
                troughcolor=self.card,
                bordercolor=self.card,
                arrowsize=0,
                relief="flat",
            )

        def _set_icon(self):
            icon_path = Path(__file__).with_name("magor_icon.png")
            if not icon_path.exists():
                return
            try:
                self.icon = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(True, self.icon)
            except tk.TclError:
                pass

        def _build(self):
            # Header -----------------------------------------------------
            header = tk.Frame(self.root, bg=self.bg)
            header.pack(fill="x", padx=32, pady=(26, 14))

            badge = tk.Canvas(header, width=44, height=44, bg=self.bg, highlightthickness=0)
            badge.pack(side="left", padx=(0, 14))
            draw_rounded_rect(badge, 1, 1, 43, 43, 12, fill=self.blue, outline="")
            badge.create_text(
                22, 23, text="M", fill="#ffffff",
                font=(self.display_family, 20, "bold"),
            )

            title_box = tk.Frame(header, bg=self.bg)
            title_box.pack(side="left")
            tk.Label(
                title_box, text=APP_NAME, bg=self.bg, fg=self.text, font=self.font_title
            ).pack(anchor="w")
            tk.Label(
                title_box, text="Smart file organization", bg=self.bg, fg=self.muted,
                font=self.font_subtitle,
            ).pack(anchor="w")

            # Folder selector card ----------------------------------------
            folder_card = RoundedCard(self.root, fill=self.card, border=self.card_border)
            folder_card.pack(fill="x", padx=32, pady=8)

            pad = tk.Frame(folder_card.inner, bg=self.card)
            pad.pack(fill="x", padx=20, pady=16)

            tk.Label(
                pad, text="FOLDER", bg=self.card, fg=self.muted, font=self.font_section
            ).pack(anchor="w")

            row = tk.Frame(pad, bg=self.card)
            row.pack(fill="x", pady=(8, 0))

            field = tk.Frame(row, bg="#f5f5f7", height=36)
            field.pack(side="left", fill="x", expand=True, padx=(0, 10))
            field.pack_propagate(False)
            self.path_entry = tk.Entry(
                field, textvariable=self.path_var, font=self.font_body,
                relief="flat", bg="#f5f5f7", fg=self.text,
                insertbackground=self.text, borderwidth=0, highlightthickness=0,
            )
            self.path_entry.pack(fill="both", expand=True, padx=12, pady=8)

            self.choose_btn = MacButton(
                row, "Choose Folder…", command=self.choose_folder,
                variant="secondary", font=self.font_button, height=36,
            )
            self.choose_btn.pack(side="right")

            folder_card.fit_to_content()

            # Options card ---------------------------------------------------
            options_card = RoundedCard(self.root, fill=self.card, border=self.card_border)
            options_card.pack(fill="x", padx=32, pady=8)

            opt_pad = tk.Frame(options_card.inner, bg=self.card)
            opt_pad.pack(fill="x", padx=20, pady=16)

            option_defs = (
                (self.recursive_var, "Scan subfolders", "Also look inside nested folders"),
                (self.hidden_var, "Include hidden files", "Files and folders starting with a dot"),
                (self.dry_run_var, "Preview only", "Show what would happen without moving files"),
            )

            for index, (variable, label, hint) in enumerate(option_defs):
                if index > 0:
                    tk.Frame(opt_pad, bg=self.divider, height=1).pack(fill="x", pady=12)

                option_row = tk.Frame(opt_pad, bg=self.card)
                option_row.pack(fill="x")

                text_box = tk.Frame(option_row, bg=self.card)
                text_box.pack(side="left", fill="x", expand=True)
                tk.Label(
                    text_box, text=label, bg=self.card, fg=self.text,
                    font=self.font_body_bold,
                ).pack(anchor="w")
                tk.Label(
                    text_box, text=hint, bg=self.card, fg=self.muted, font=self.font_small
                ).pack(anchor="w")

                MacToggle(option_row, variable=variable).pack(side="right")

            options_card.fit_to_content()

            # Stats ------------------------------------------------------
            stats = tk.Frame(self.root, bg=self.bg)
            stats.pack(fill="x", padx=32, pady=8)

            self._stat_card(stats, "FILES", self.files_var).pack(
                side="left", fill="both", expand=True, padx=(0, 8)
            )
            self._stat_card(stats, "TOTAL SIZE", self.size_var).pack(
                side="left", fill="both", expand=True, padx=4
            )
            self._stat_card(stats, "DUPLICATES", self.duplicate_var).pack(
                side="left", fill="both", expand=True, padx=(8, 0)
            )

            # Preview ------------------------------------------------------
            preview_card = RoundedCard(self.root, fill=self.card, border=self.card_border)
            preview_card.pack(fill="both", expand=True, padx=32, pady=8)

            preview_header = tk.Frame(preview_card.inner, bg=self.card)
            preview_header.pack(fill="x", padx=18, pady=(14, 6))
            tk.Label(
                preview_header, text="Preview", bg=self.card, fg=self.text,
                font=(self.text_family, 13, "bold"),
            ).pack(side="left")

            tree_wrap = tk.Frame(preview_card.inner, bg=self.card)
            tree_wrap.pack(fill="both", expand=True, padx=(18, 6), pady=(0, 16))

            self.tree = ttk.Treeview(
                tree_wrap,
                columns=("name", "category", "size", "duplicate"),
                show="headings",
                selectmode="browse",
            )
            self.tree.heading("name", text="File")
            self.tree.heading("category", text="Category")
            self.tree.heading("size", text="Size")
            self.tree.heading("duplicate", text="Duplicate")
            self.tree.column("name", width=380, anchor="w")
            self.tree.column("category", width=140, anchor="w")
            self.tree.column("size", width=100, anchor="e")
            self.tree.column("duplicate", width=100, anchor="center")
            self.tree.tag_configure("odd", background="#fbfbfd")
            self.tree.tag_configure("even", background=self.card)

            scrollbar = ttk.Scrollbar(tree_wrap, orient="vertical", command=self.tree.yview)
            self.tree.configure(yscrollcommand=scrollbar.set)
            self.tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y", padx=(6, 0))

            # Progress + actions --------------------------------------------
            bottom = tk.Frame(self.root, bg=self.bg)
            bottom.pack(fill="x", padx=32, pady=(6, 24))

            self.progress = MacProgressBar(bottom, height=6)
            self.progress.pack(fill="x", pady=(0, 12))

            action_row = tk.Frame(bottom, bg=self.bg)
            action_row.pack(fill="x")

            tk.Label(
                action_row, textvariable=self.status_var, bg=self.bg, fg=self.muted,
                font=self.font_body,
            ).pack(side="left")

            self.organize_btn = MacButton(
                action_row, "Organize", command=self.organize,
                variant="primary", font=self.font_button, height=36,
            )
            self.organize_btn.pack(side="right", padx=(10, 0))

            self.undo_btn = MacButton(
                action_row, "Undo Last", command=self.undo,
                variant="secondary", font=self.font_button, height=36,
            )
            self.undo_btn.pack(side="right", padx=(10, 0))

            self.scan_btn = MacButton(
                action_row, "Scan", command=self.scan,
                variant="secondary", font=self.font_button, height=36,
            )
            self.scan_btn.pack(side="right")

        def _stat_card(self, parent, title, variable):
            card = RoundedCard(parent, fill=self.card, border=self.card_border)
            inner = tk.Frame(card.inner, bg=self.card)
            inner.pack(fill="both", expand=True, padx=16, pady=14)

            tk.Label(
                inner, text=title, bg=self.card, fg=self.muted, font=self.font_stat_label
            ).pack(anchor="w")
            tk.Label(
                inner, textvariable=variable, bg=self.card, fg=self.text,
                font=self.font_stat_value,
            ).pack(anchor="w", pady=(4, 0))

            card.fit_to_content()
            return card

        def choose_folder(self):
            from tkinter import filedialog

            chosen = filedialog.askdirectory(title="Choose a folder to organize")
            if chosen:
                self.path_var.set(chosen)
                self.scan()

        def _set_busy(self, busy: bool):
            self.busy = busy
            enabled = not busy
            self.scan_btn.set_enabled(enabled)
            self.organize_btn.set_enabled(enabled)
            self.undo_btn.set_enabled(enabled)
            self.choose_btn.set_enabled(enabled)

        def _start_worker(self, action):
            if self.busy:
                return
            self._set_busy(True)
            threading.Thread(target=action, daemon=True).start()

        def scan(self):
            target = self.path_var.get().strip()
            if not target:
                self.status_var.set("Choose a folder first.")
                return

            def worker():
                try:
                    result = scan_folder(
                        target,
                        recursive=self.recursive_var.get(),
                        include_hidden=self.hidden_var.get(),
                        progress=lambda done, total: self.events.put(
                            ("progress", done, total)
                        ),
                    )
                    self.events.put(("scan_done", result))
                except Exception as exc:
                    self.events.put(("error", str(exc)))

            self.status_var.set("Scanning…")
            self.progress.set_progress(0)
            self._start_worker(worker)

        def organize(self):
            target = self.path_var.get().strip()
            if not target:
                self.status_var.set("Choose a folder first.")
                return

            def worker():
                try:
                    moved, _ = organize_folder(
                        target,
                        recursive=self.recursive_var.get(),
                        include_hidden=self.hidden_var.get(),
                        dry_run=self.dry_run_var.get(),
                        log=lambda message: self.events.put(("log", message)),
                        progress=lambda done, total: self.events.put(
                            ("progress", done, total)
                        ),
                    )
                    self.events.put(("organize_done", moved))
                except Exception as exc:
                    self.events.put(("error", str(exc)))

            self.status_var.set("Working…")
            self.progress.set_progress(0)
            self._start_worker(worker)

        def undo(self):
            target = self.path_var.get().strip()
            if not target:
                self.status_var.set("Choose a folder first.")
                return

            def worker():
                try:
                    restored = undo_last(
                        target,
                        log=lambda message: self.events.put(("log", message)),
                    )
                    self.events.put(("undo_done", restored))
                except Exception as exc:
                    self.events.put(("error", str(exc)))

            self.status_var.set("Undoing…")
            self.progress.set_progress(0)
            self._start_worker(worker)

        def _clear_tree(self):
            for item in self.tree.get_children():
                self.tree.delete(item)

        def _show_scan(self, result: ScanResult):
            self.current_scan = result
            self._clear_tree()

            ordered = sorted(result.files, key=lambda item: (item.category, item.name.lower()))
            for index, record in enumerate(ordered):
                tag = "even" if index % 2 == 0 else "odd"
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        record.name,
                        record.category,
                        format_size(record.size),
                        "Yes" if record.duplicate else "",
                    ),
                    tags=(tag,),
                )

            self.files_var.set(f"{len(result.files)}")
            self.size_var.set(format_size(result.total_size))
            self.duplicate_var.set(f"{result.duplicates}")
            self.status_var.set(
                f"Scan complete — {len(result.files)} file(s), "
                f"{result.duplicates} duplicate(s)."
            )

        def _poll_events(self):
            try:
                while True:
                    event = self.events.get_nowait()
                    kind = event[0]

                    if kind == "progress":
                        _, done, total = event
                        self.progress.set_progress((done / total) if total else 0)

                    elif kind == "scan_done":
                        self._show_scan(event[1])
                        self._set_busy(False)

                    elif kind == "organize_done":
                        moved = event[1]
                        self.status_var.set(f"Complete — {moved} file(s) processed.")
                        self._set_busy(False)
                        self.scan()

                    elif kind == "undo_done":
                        restored = event[1]
                        self.status_var.set(f"Undo complete — {restored} file(s) restored.")
                        self._set_busy(False)
                        self.scan()

                    elif kind == "log":
                        # The activity log is intentionally represented in the
                        # status line for the compact GUI. Full CLI logs remain
                        # available when running with --cli.
                        message = event[1]
                        self.status_var.set(message[:110])

                    elif kind == "error":
                        self.status_var.set(f"Error: {event[1]}")
                        self._set_busy(False)

            except queue.Empty:
                pass

            self.root.after(100, self._poll_events)


def run_gui() -> int:
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        print("Error: no graphical display found. Use --cli.")
        return 1

    if tk is None:
        print("Error: tkinter is not installed. On Debian/Ubuntu:")
        print("  sudo apt install python3-tk")
        return 1

    root = tk.Tk()
    MagorGUI(root)
    root.mainloop()
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Magor — organize files safely by type."
    )
    parser.add_argument("path", nargs="?", help="Directory to organize")
    parser.add_argument("--gui", action="store_true", help="Open the GUI")
    parser.add_argument("--cli", action="store_true", help="Use terminal mode")
    parser.add_argument("--recursive", "-r", action="store_true", help="Scan subfolders")
    parser.add_argument("--hidden", action="store_true", help="Include hidden files")
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Preview changes without moving files",
    )
    parser.add_argument("--undo", action="store_true", help="Undo the last organization")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)

    if args.undo:
        return run_cli(args)

    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    if args.gui:
        return run_gui()

    if args.path and (args.cli or not has_display):
        return run_cli(args)

    if args.path:
        return run_cli(args)

    if args.cli or not has_display:
        return run_cli(args)

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
