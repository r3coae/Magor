<div align="center">

  <img src="assets/icon.png" alt="Magor 1.2 Icon" width="128" height="128">

  # Magor 1.2
  **Smart File Organizer for Linux — Electron + Node.js**

  [![Release](https://img.shields.io/badge/Release-v1.2.0-0071e3?style=for-the-badge&logo=ubuntu&logoColor=white)](../../releases/latest)
  [![Platform](https://img.shields.io/badge/Platform-Ubuntu%20%7C%20Debian%20%7C%20Linux-e95420?style=for-the-badge&logo=linux&logoColor=white)](../../releases/latest)
  [![License](https://img.shields.io/badge/License-MIT-34c759?style=for-the-badge)](LICENSE)
  [![Node.js](https://img.shields.io/badge/Node.js-18+-339933?style=for-the-badge&logo=node.js&logoColor=white)](https://nodejs.org)

  <p align="center">
    A native, non-destructive desktop file organizer with an authentic macOS Liquid Glass aesthetic.<br>
    Features fast scanning, streaming SHA-256 duplicate detection, collision-safe renaming, and one-click undo.<br>
    Works as both a beautiful <strong>desktop GUI (Electron)</strong> and a powerful <strong>headless CLI</strong>.
  </p>

  <br>

  <a href="../../releases/latest">
    <img src="https://img.shields.io/badge/📥_Download_Magor_1.2_(.deb)-0071e3?style=for-the-badge&logo=debian&logoColor=white" height="42" alt="Download .deb">
  </a>

</div>

---

## 📸 Screenshots

> _Launch Magor to see the macOS-style Liquid Glass interface on your Ubuntu desktop._

---

## 🚀 Easy Install (No Terminal Required)

Works on **Ubuntu, Debian, Linux Mint, Pop!\_OS** and any Debian-based distro.

### Step 1 — Download
Click the **Download** badge above and save `magor_1.2.0_amd64.deb`.

### Step 2 — Install with One Click
1. Open your **Downloads** folder in the file manager.
2. Double-click **`magor_1.2.0_amd64.deb`**.
3. Click **Install** and enter your password when prompted.

### Step 3 — Launch
- Press **Super** key → search **Magor** → click the icon.
- Or run `magor` from any terminal.

---

## ✨ Features

### 🪟 macOS Liquid Glass Interface
| Feature | Details |
|---|---|
| Frosted Glass Cards | `backdrop-filter: blur(40px)` translucent panels with specular borders |
| macOS Traffic Lights | Close / Minimize / Maximize window controls with hover micro-glyphs |
| Drag-and-Drop Zone | Drag folders directly from Ubuntu Files (Nautilus) into the window |
| Category Breakdown Bar | Animated segmented bar showing real-time file distribution |
| Interactive Preview Table | Search, filter by category, review files before moving |
| Activity Log Console | Live real-time event stream for all operations |

### 🛡️ Smart & Safe Organization Engine
- **9 Built-In Categories** — Images, Documents, Archives, Audio, Video, Code, Fonts, Design, Others
- **Streaming SHA-256 Duplicate Detection** — Size pre-grouping → chunked hash → zero wasted reads
- **Collision-Safe Renaming** — Auto `_1`, `_2` suffixes; never overwrites existing files
- **One-Click Undo** — Reverses the last operation, restoring all files to their original paths
- **Dry-Run Preview** — Simulate and review every planned move before anything is touched
- **Recursive Mode** — Scan into subdirectories
- **Hidden File Support** — Optionally include dotfiles

### File Categories
| Category | Extensions |
|---|---|
| 🖼️ Images | `.jpg` `.jpeg` `.png` `.gif` `.svg` `.webp` `.bmp` `.tiff` `.heic` `.avif` `.raw` `.cr2` `.nef` |
| 📄 Documents | `.pdf` `.doc` `.docx` `.txt` `.rtf` `.odt` `.md` `.xlsx` `.csv` `.pptx` `.epub` `.mobi` |
| 📦 Archives | `.zip` `.tar` `.gz` `.tgz` `.bz2` `.xz` `.7z` `.rar` `.iso` `.deb` `.rpm` `.apk` |
| 🎵 Audio | `.mp3` `.wav` `.flac` `.ogg` `.m4a` `.aac` `.opus` `.wma` `.alac` `.aiff` |
| 🎬 Video | `.mp4` `.mkv` `.mov` `.avi` `.webm` `.flv` `.wmv` `.m4v` `.3gp` |
| 💻 Code | `.py` `.js` `.ts` `.html` `.css` `.json` `.yaml` `.sh` `.c` `.cpp` `.rs` `.go` `.sql` `.vue` `.svelte` |
| 🔤 Fonts | `.ttf` `.otf` `.woff` `.woff2` `.eot` |
| 🎨 Design | `.psd` `.ai` `.eps` `.fig` `.sketch` `.xd` `.blend` |
| 📁 Others | Any unrecognized extension |

---

## 🛠️ For Developers & Power Users

### Requirements
- **Node.js** 18 or later
- **npm** 9 or later

### Install & Run from Source
```bash
# Clone the repository
git clone https://github.com/your-username/magor.git
cd magor

# Install dependencies (Electron)
npm install

# Launch the desktop GUI
npm start

# Run as CLI only
npm run cli -- /path/to/folder -n
```

### CLI Usage
```bash
# Dry-run preview (no files moved)
node magor.js /path/to/folder -n

# Organize files recursively
node magor.js /path/to/folder -r

# Include hidden dotfiles
node magor.js /path/to/folder --hidden

# Undo the last operation
node magor.js /path/to/folder --undo

# Launch GUI explicitly
node magor.js --gui
```

### Build Debian Package (.deb)
```bash
# Build the .deb package for distribution
bash scripts/build-deb.sh
```

---

## 🏗️ Project Structure

```
magor/
├── magor.js              # CLI entrypoint & Electron launcher
├── main.js               # Electron main process
├── preload.js            # Electron preload script (IPC bridge)
├── package.json          # Node.js project manifest
├── run-magor.sh          # Quick-launch shell script
├── src/
│   ├── organizer.js      # Core engine (scan, organize, undo, SHA-256)
│   └── renderer/
│       ├── index.html    # Main GUI window (Liquid Glass UI)
│       ├── styles.css    # macOS Liquid Glass CSS
│       └── app.js        # Frontend renderer logic
├── assets/
│   └── icon.png          # Application icon
└── scripts/
    └── build-deb.sh      # Debian package build script
```

---

## 🔄 Changelog

### v1.2.0 (2026-09-16)
- ✨ Full Electron desktop GUI with macOS Liquid Glass aesthetic
- ✨ Interactive drag-and-drop folder selector
- ✨ Real-time activity log console
- ✨ Category breakdown animated bar
- ✨ Searchable & filterable file preview table
- 🔧 Extended category maps (`.raw`, `.cr2`, `.epub`, `.mobi`, `.apk`, `.alac`, `.3gp`, `.vue`, `.svelte`, `.blend`, etc.)
- 🔧 IPC bridge between Electron main and renderer
- 🔧 `.deb` package build script

### v1.1.0
- Initial Python (Tkinter) release with macOS-inspired UI
- CLI + GUI dual mode
- SHA-256 duplicate detection, undo, dry-run

---

## 📄 License

Released under the [MIT License](LICENSE).  
© 2026 r3coae
