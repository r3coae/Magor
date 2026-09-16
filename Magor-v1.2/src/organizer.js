/**
 * Magor 1.2 - Core File Organizer Engine
 *
 * Provides fast scanning, extension-based smart categorization,
 * collision-safe renaming, SHA-256 duplicate detection, dry-run previews,
 * and reliable undo operations.
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const APP_NAME = "Magor";
const APP_VERSION = "1.2";
const UNDO_FILE = ".magor_undo.json";
const CHUNK_SIZE = 1024 * 1024; // 1 MB streaming chunks

const EXTENSION_MAP = {
    "Images": [
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp",
        ".tiff", ".tif", ".ico", ".heic", ".avif", ".raw", ".cr2", ".nef"
    ],
    "Documents": [
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md",
        ".xlsx", ".xls", ".ods", ".csv", ".ppt", ".pptx", ".odp",
        ".epub", ".mobi"
    ],
    "Archives": [
        ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar",
        ".iso", ".deb", ".rpm", ".apk"
    ],
    "Audio": [
        ".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma", ".alac", ".aiff"
    ],
    "Video": [
        ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v", ".3gp"
    ],
    "Code": [
        ".py", ".pyw", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".htm",
        ".css", ".scss", ".sass", ".less", ".json", ".xml", ".yaml", ".yml",
        ".sh", ".bash", ".zsh", ".fish", ".c", ".h", ".cpp", ".hpp", ".cc",
        ".java", ".kt", ".rs", ".go", ".php", ".rb", ".sql", ".lua", ".vue", ".svelte"
    ],
    "Fonts": [
        ".ttf", ".otf", ".woff", ".woff2", ".eot"
    ],
    "Design": [
        ".psd", ".ai", ".eps", ".fig", ".sketch", ".xd", ".blend"
    ]
};

const EXT_TO_CATEGORY = new Map();
for (const [category, extensions] of Object.entries(EXTENSION_MAP)) {
    for (const ext of extensions) {
        EXT_TO_CATEGORY.set(ext.toLowerCase(), category);
    }
}

/**
 * Format raw byte size into human readable string.
 */
function formatSize(size) {
    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = Number(size);
    for (let i = 0; i < units.length; i++) {
        const unit = units[i];
        if (value < 1024 || i === units.length - 1) {
            return unit === "B" ? `${Math.floor(value)} B` : `${value.toFixed(1)} ${unit}`;
        }
        value /= 1024;
    }
    return `${size} B`;
}

/**
 * Identify category for a given path based on extension.
 */
function categoryFor(filePath) {
    const ext = path.extname(filePath).toLowerCase();
    return EXT_TO_CATEGORY.get(ext) || "Others";
}

/**
 * Find collision-safe destination filename.
 */
function uniqueDestination(destDir, filename) {
    const dest = path.join(destDir, filename);
    if (!fs.existsSync(dest)) {
        return dest;
    }

    const ext = path.extname(filename);
    const stem = path.basename(filename, ext);
    let number = 1;

    while (true) {
        const candidate = path.join(destDir, `${stem}_${number}${ext}`);
        if (!fs.existsSync(candidate)) {
            return candidate;
        }
        number++;
    }
}

/**
 * Move file with fallback for cross-filesystem links (EXDEV).
 */
function moveFileSafe(source, destination) {
    try {
        fs.renameSync(source, destination);
    } catch (err) {
        if (err.code === 'EXDEV') {
            fs.copyFileSync(source, destination);
            fs.unlinkSync(source);
        } else {
            throw err;
        }
    }
}

/**
 * Compute streaming SHA-256 hash.
 */
function sha256File(filePath) {
    return new Promise((resolve, reject) => {
        const hash = crypto.createHash('sha256');
        const stream = fs.createReadStream(filePath, { highWaterMark: CHUNK_SIZE });
        stream.on('data', chunk => hash.update(chunk));
        stream.on('end', () => resolve(hash.digest('hex')));
        stream.on('error', reject);
    });
}

/**
 * Check if path contains hidden parts relative to base directory.
 */
function isHiddenRelative(baseDir, targetPath) {
    const rel = path.relative(baseDir, targetPath);
    const parts = rel.split(path.sep);
    return parts.some(part => part.startsWith('.') && part !== '.' && part !== '..');
}

/**
 * Collect candidate files from directory.
 */
function collectFiles(targetDir, recursive, includeHidden) {
    const files = [];

    function traverse(currentDir) {
        let entries;
        try {
            entries = fs.readdirSync(currentDir, { withFileTypes: true });
        } catch {
            return;
        }

        for (const entry of entries) {
            const fullPath = path.join(currentDir, entry.name);

            if (entry.name === UNDO_FILE) {
                continue;
            }

            if (!includeHidden && isHiddenRelative(targetDir, fullPath)) {
                continue;
            }

            try {
                if (entry.isFile()) {
                    files.push(fullPath);
                } else if (entry.isDirectory() && recursive) {
                    traverse(fullPath);
                }
            } catch {
                // Ignore unreadable entries
            }
        }
    }

    traverse(targetDir);
    return files;
}

/**
 * Scan target directory and calculate statistics & duplicate tags.
 */
async function scanFolder(targetDir, options = {}, onProgress = null) {
    const { recursive = false, includeHidden = false, detectDuplicates = true } = options;
    const resolvedPath = path.resolve(targetDir);

    if (!fs.existsSync(resolvedPath)) {
        throw new Error(`Directory does not exist: ${resolvedPath}`);
    }
    const stat = fs.statSync(resolvedPath);
    if (!stat.isDirectory()) {
        throw new Error(`Path is not a directory: ${resolvedPath}`);
    }

    const candidatePaths = collectFiles(resolvedPath, recursive, includeHidden);
    const total = candidatePaths.length;
    const files = [];
    const errors = [];
    const sizeGroups = new Map();
    const categoryCounts = {};
    const categorySizes = {};

    for (let i = 0; i < candidatePaths.length; i++) {
        const itemPath = candidatePaths[i];
        try {
            const s = fs.statSync(itemPath);
            const category = categoryFor(itemPath);
            const record = {
                source: itemPath,
                name: path.basename(itemPath),
                category,
                size: s.size,
                sizeFormatted: formatSize(s.size),
                modified: s.mtimeMs,
                duplicate: false,
                duplicateHash: null
            };
            files.push(record);

            categoryCounts[category] = (categoryCounts[category] || 0) + 1;
            categorySizes[category] = (categorySizes[category] || 0) + s.size;

            if (!sizeGroups.has(s.size)) {
                sizeGroups.set(s.size, []);
            }
            sizeGroups.get(s.size).push(itemPath);
        } catch (err) {
            errors.push(`${path.basename(itemPath)}: ${err.message}`);
        }

        if (onProgress) {
            onProgress({ phase: 'scanning', current: i + 1, total, item: path.basename(itemPath) });
        }
    }

    const duplicateMap = new Map(); // hash -> [paths]
    if (detectDuplicates) {
        let hashedCount = 0;
        const candidatesForHashing = [];
        for (const group of sizeGroups.values()) {
            if (group.length > 1) {
                candidatesForHashing.push(...group);
            }
        }

        for (const itemPath of candidatesForHashing) {
            try {
                const digest = await sha256File(itemPath);
                if (!duplicateMap.has(digest)) {
                    duplicateMap.set(digest, []);
                }
                duplicateMap.get(digest).push(itemPath);
            } catch (err) {
                errors.push(`${path.basename(itemPath)}: ${err.message}`);
            }

            hashedCount++;
            if (onProgress) {
                onProgress({ phase: 'hashing', current: hashedCount, total: candidatesForHashing.length, item: path.basename(itemPath) });
            }
        }
    }

    const duplicatePaths = new Set();
    const pathDigestMap = new Map();
    for (const [digest, list] of duplicateMap.entries()) {
        if (list.length > 1) {
            for (const p of list) {
                duplicatePaths.add(p);
                pathDigestMap.set(p, digest);
            }
        }
    }

    let totalSize = 0;
    for (const record of files) {
        if (duplicatePaths.has(record.source)) {
            record.duplicate = true;
            record.duplicateHash = pathDigestMap.get(record.source);
        }
        totalSize += record.size;
    }

    return {
        path: resolvedPath,
        files,
        totalFiles: files.length,
        totalSize,
        totalSizeFormatted: formatSize(totalSize),
        duplicates: duplicatePaths.size,
        categoryCounts,
        categorySizes,
        errors
    };
}

/**
 * Save undo record to .magor_undo.json
 */
function saveUndoHistory(dirPath, moves) {
    const payload = {
        app: APP_NAME,
        version: APP_VERSION,
        created_at: Date.now() / 1000,
        moves: moves.map(m => ({ source: m.source, destination: m.destination }))
    };
    const undoPath = path.join(dirPath, UNDO_FILE);
    fs.writeFileSync(undoPath, JSON.stringify(payload, null, 2), 'utf8');
}

/**
 * Check if an undo history file exists in the directory.
 */
function hasUndoHistory(targetDir) {
    const resolvedPath = path.resolve(targetDir);
    const undoPath = path.join(resolvedPath, UNDO_FILE);
    return fs.existsSync(undoPath);
}

/**
 * Organize directory into categorized folders.
 */
async function organizeFolder(targetDir, options = {}, onLog = null, onProgress = null) {
    const { recursive = false, includeHidden = false, dryRun = false, detectDuplicates = true } = options;
    const resolvedPath = path.resolve(targetDir);

    const scanResult = await scanFolder(resolvedPath, { recursive, includeHidden, detectDuplicates }, onProgress);
    const moves = [];
    const total = scanResult.files.length;

    if (total === 0) {
        if (onLog) onLog({ type: 'info', message: 'No files found to organize.' });
        return { moved: 0, moves: [], dryRun };
    }

    for (let i = 0; i < scanResult.files.length; i++) {
        const record = scanResult.files[i];
        const source = record.source;
        const filename = record.name;

        const destDir = path.join(resolvedPath, record.category);
        const destination = uniqueDestination(destDir, filename);
        const destName = path.basename(destination);

        if (dryRun) {
            if (onLog) {
                onLog({
                    type: 'preview',
                    source: filename,
                    target: `${record.category}/${destName}`,
                    message: `[PREVIEW] ${filename} → ${record.category}/${destName}`
                });
            }
        } else {
            try {
                if (!fs.existsSync(destDir)) {
                    fs.mkdirSync(destDir, { recursive: true });
                }
                moveFileSafe(source, destination);
                moves.push({ source, destination });

                const renamed = destName !== filename;
                if (onLog) {
                    onLog({
                        type: 'success',
                        source: filename,
                        target: `${record.category}/${destName}`,
                        renamed,
                        message: `Moved: ${filename} → ${record.category}/${destName}${renamed ? ' (renamed to avoid overwrite)' : ''}`
                    });
                }
            } catch (err) {
                if (onLog) {
                    onLog({
                        type: 'error',
                        source: filename,
                        message: `ERROR: ${filename}: ${err.message}`
                    });
                }
            }
        }

        if (onProgress) {
            onProgress({ phase: 'moving', current: i + 1, total, item: filename });
        }
    }

    if (!dryRun && moves.length > 0) {
        saveUndoHistory(resolvedPath, moves);
    }

    const count = dryRun ? total : moves.length;
    if (onLog) {
        onLog({
            type: 'done',
            message: `Done. ${dryRun ? 'Would move' : 'Moved'} ${count} file(s).`
        });
    }

    return {
        moved: count,
        moves,
        dryRun,
        scanResult
    };
}

/**
 * Reverses the last organization in target directory.
 */
function undoLast(targetDir, onLog = null) {
    const resolvedPath = path.resolve(targetDir);
    const undoPath = path.join(resolvedPath, UNDO_FILE);

    if (!fs.existsSync(undoPath)) {
        if (onLog) onLog({ type: 'info', message: 'Nothing to undo.' });
        return { restored: 0, success: false };
    }

    let payload;
    try {
        payload = JSON.parse(fs.readFileSync(undoPath, 'utf8'));
    } catch (err) {
        if (onLog) onLog({ type: 'error', message: `Cannot read undo history: ${err.message}` });
        return { restored: 0, success: false, error: err.message };
    }

    const moves = payload.moves || [];
    let restored = 0;

    for (let i = moves.length - 1; i >= 0; i--) {
        const move = moves[i];
        const source = move.source;
        const destination = move.destination;

        if (!fs.existsSync(destination)) {
            if (onLog) onLog({ type: 'warning', message: `Skipped: missing ${destination}` });
            continue;
        }

        try {
            const parentDir = path.dirname(source);
            if (!fs.existsSync(parentDir)) {
                fs.mkdirSync(parentDir, { recursive: true });
            }

            let restoreTarget = source;
            if (fs.existsSync(restoreTarget)) {
                restoreTarget = uniqueDestination(parentDir, path.basename(source));
            }

            moveFileSafe(destination, restoreTarget);
            restored++;
            if (onLog) {
                onLog({
                    type: 'success',
                    message: `Restored: ${path.basename(destination)} → ${restoreTarget}`
                });
            }
        } catch (err) {
            if (onLog) {
                onLog({
                    type: 'error',
                    message: `ERROR restoring ${destination}: ${err.message}`
                });
            }
        }
    }

    try {
        fs.unlinkSync(undoPath);
    } catch {
        // Ignore unlink errors
    }

    if (onLog) {
        onLog({
            type: 'done',
            message: `Undo complete. Restored ${restored} file(s).`
        });
    }

    return { restored, success: true };
}

module.exports = {
    APP_NAME,
    APP_VERSION,
    UNDO_FILE,
    EXTENSION_MAP,
    formatSize,
    categoryFor,
    uniqueDestination,
    scanFolder,
    organizeFolder,
    undoLast,
    hasUndoHistory
};
