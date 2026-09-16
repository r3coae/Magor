/**
 * Magor 1.2 - Liquid Glass macOS GUI Controller
 */

document.addEventListener('DOMContentLoaded', () => {
    // State
    let currentPath = null;
    let currentScanData = null;
    let isProcessing = false;
    let logEntriesCount = 0;

    // Elements
    const btnClose = document.getElementById('btn-close');
    const btnMinimize = document.getElementById('btn-minimize');
    const btnMaximize = document.getElementById('btn-maximize');

    const topStatusIndicator = document.getElementById('top-status-indicator');
    const topStatusText = document.getElementById('top-status-text');
    const bottomStatus = document.getElementById('bottom-status');

    const tabButtons = document.querySelectorAll('.segment-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    const dropzone = document.getElementById('folder-dropzone');
    const targetFolderName = document.getElementById('target-folder-name');
    const targetFolderPath = document.getElementById('target-folder-path');
    const btnBrowse = document.getElementById('btn-browse');
    const btnOpenExplorer = document.getElementById('btn-open-explorer');

    const statFiles = document.getElementById('stat-files');
    const statFilesMeta = document.getElementById('stat-files-meta');
    const statSize = document.getElementById('stat-size');
    const statSizeMeta = document.getElementById('stat-size-meta');
    const statDuplicates = document.getElementById('stat-duplicates');
    const statDuplicatesMeta = document.getElementById('stat-duplicates-meta');
    const statCategories = document.getElementById('stat-categories');
    const statCategoriesMeta = document.getElementById('stat-categories-meta');

    const distributionCard = document.getElementById('distribution-card');
    const distributionTotal = document.getElementById('distribution-total');
    const categoryBar = document.getElementById('category-bar');
    const categoryLegend = document.getElementById('category-legend');

    const toggleRecursive = document.getElementById('toggle-recursive');
    const toggleHidden = document.getElementById('toggle-hidden');
    const toggleDuplicates = document.getElementById('toggle-duplicates');
    const toggleDryrun = document.getElementById('toggle-dryrun');

    const progressCard = document.getElementById('progress-card');
    const progressPhase = document.getElementById('progress-phase');
    const progressPercent = document.getElementById('progress-percent');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const progressItem = document.getElementById('progress-item');

    const btnScan = document.getElementById('btn-scan');
    const btnOrganize = document.getElementById('btn-organize');
    const btnUndo = document.getElementById('btn-undo');

    const previewSearch = document.getElementById('preview-search');
    const filterPills = document.querySelectorAll('.pill-btn');
    const previewTableBody = document.getElementById('preview-table-body');

    const activityConsole = document.getElementById('activity-log-console');
    const logCounter = document.getElementById('log-count');
    const btnCopyLog = document.getElementById('btn-copy-log');
    const btnClearLog = document.getElementById('btn-clear-log');

    const categoryGrid = document.getElementById('category-grid');

    // -------------------------------------------------------------------------
    // Window Controls
    // -------------------------------------------------------------------------
    btnClose.addEventListener('click', () => window.magor.close());
    btnMinimize.addEventListener('click', () => window.magor.minimize());
    btnMaximize.addEventListener('click', () => window.magor.maximize());

    // -------------------------------------------------------------------------
    // Navigation Tabs
    // -------------------------------------------------------------------------
    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetTab = btn.dataset.tab;
            tabButtons.forEach(b => b.classList.remove('active'));
            tabPanes.forEach(p => p.classList.remove('active'));

            btn.classList.add('active');
            const activePane = document.getElementById(`pane-${targetTab}`);
            if (activePane) activePane.classList.add('active');
        });
    });

    // -------------------------------------------------------------------------
    // Logging Helpers
    // -------------------------------------------------------------------------
    function addLog(type, message) {
        logEntriesCount++;
        logCounter.textContent = `${logEntriesCount} message${logEntriesCount === 1 ? '' : 's'}`;

        const now = new Date();
        const timeStr = now.toTimeString().split(' ')[0];

        const entry = document.createElement('div');
        entry.className = `log-entry log-${type}`;

        const timeSpan = document.createElement('span');
        timeSpan.className = 'log-time';
        timeSpan.textContent = timeStr;

        const tagSpan = document.createElement('span');
        tagSpan.className = `log-tag ${type}`;
        tagSpan.textContent = type.toUpperCase();

        const msgSpan = document.createElement('span');
        msgSpan.className = 'log-msg';
        msgSpan.textContent = message;

        entry.appendChild(timeSpan);
        entry.appendChild(tagSpan);
        entry.appendChild(msgSpan);

        activityConsole.appendChild(entry);
        activityConsole.scrollTop = activityConsole.scrollHeight;
    }

    // Subscribe to IPC log stream
    window.magor.onLog((data) => {
        addLog(data.type || 'info', data.message || JSON.stringify(data));
    });

    // Subscribe to IPC progress stream
    window.magor.onProgress((data) => {
        if (!progressCard) return;
        progressCard.style.display = 'block';

        const percent = data.total > 0 ? Math.round((data.current / data.total) * 100) : 0;
        progressBarFill.style.width = `${percent}%`;
        progressPercent.textContent = `${percent}%`;

        let phaseLabel = 'Working...';
        if (data.phase === 'scanning') phaseLabel = `Scanning (${data.current}/${data.total})`;
        else if (data.phase === 'hashing') phaseLabel = `SHA-256 Hashing (${data.current}/${data.total})`;
        else if (data.phase === 'moving') phaseLabel = `Moving Files (${data.current}/${data.total})`;

        progressPhase.textContent = phaseLabel;
        progressItem.textContent = data.item ? `Current: ${data.item}` : '';
    });

    // -------------------------------------------------------------------------
    // Folder Selection & Dropzone
    // -------------------------------------------------------------------------
    async function setTargetFolder(folderPath) {
        if (!folderPath) return;
        currentPath = folderPath;
        const parts = folderPath.split(/[/\\]/);
        const folderName = parts[parts.length - 1] || folderPath;

        targetFolderName.textContent = folderName;
        targetFolderPath.textContent = folderPath;
        btnOpenExplorer.style.display = 'inline-flex';

        btnScan.disabled = false;
        btnOrganize.disabled = false;

        bottomStatus.textContent = `Target: ${folderPath}`;
        addLog('info', `Selected directory: ${folderPath}`);

        await checkUndoStatus();
        await scanFolder();
    }

    btnBrowse.addEventListener('click', async () => {
        const folder = await window.magor.selectFolder();
        if (folder) {
            await setTargetFolder(folder);
        }
    });

    btnOpenExplorer.addEventListener('click', () => {
        if (currentPath) {
            window.magor.openPath(currentPath);
        }
    });

    // Drag & Drop
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('drag-over');
        });
    });

    dropzone.addEventListener('drop', async (e) => {
        const files = e.dataTransfer.files;
        if (files && files.length > 0) {
            const firstItem = files[0];
            const dropPath = firstItem.path || firstItem.name;
            await setTargetFolder(dropPath);
        }
    });

    // -------------------------------------------------------------------------
    // Scanning & Organization
    // -------------------------------------------------------------------------
    function getOptions() {
        return {
            recursive: toggleRecursive.checked,
            includeHidden: toggleHidden.checked,
            detectDuplicates: toggleDuplicates.checked,
            dryRun: toggleDryrun.checked
        };
    }

    async function checkUndoStatus() {
        if (!currentPath) {
            btnUndo.disabled = true;
            return;
        }
        const hasUndo = await window.magor.hasUndoHistory(currentPath);
        btnUndo.disabled = !hasUndo;
    }

    async function scanFolder() {
        if (!currentPath || isProcessing) return;
        isProcessing = true;
        topStatusText.textContent = 'Scanning...';
        progressCard.style.display = 'block';
        progressBarFill.style.width = '0%';

        try {
            const res = await window.magor.scanFolder(currentPath, getOptions());
            if (res.success) {
                currentScanData = res.data;
                updateStats(res.data);
                renderCategoryBar(res.data);
                renderTable(res.data.files);
                topStatusText.textContent = 'Ready';
                addLog('info', `Scan finished: ${res.data.totalFiles} file(s) found.`);
            } else {
                topStatusText.textContent = 'Error';
                addLog('error', `Scan error: ${res.error}`);
            }
        } catch (err) {
            addLog('error', `Unexpected scan error: ${err.message}`);
        } finally {
            isProcessing = false;
            setTimeout(() => { progressCard.style.display = 'none'; }, 800);
            await checkUndoStatus();
        }
    }

    btnScan.addEventListener('click', scanFolder);

    // Toggle dry-run updates button title
    toggleDryrun.addEventListener('change', () => {
        if (toggleDryrun.checked) {
            btnOrganize.querySelector('span').textContent = 'Preview Changes (Dry-Run)';
        } else {
            btnOrganize.querySelector('span').textContent = 'Organize Files';
        }
    });

    // Organize Button
    btnOrganize.addEventListener('click', async () => {
        if (!currentPath || isProcessing) return;
        isProcessing = true;
        const dryRun = toggleDryrun.checked;

        topStatusText.textContent = dryRun ? 'Simulating...' : 'Organizing...';
        progressCard.style.display = 'block';
        progressBarFill.style.width = '0%';

        addLog('info', `Starting ${dryRun ? 'dry-run preview' : 'organization'} on: ${currentPath}`);

        try {
            const res = await window.magor.organizeFolder(currentPath, getOptions());
            if (res.success) {
                addLog('success', `Completed: ${res.data.moved} file(s) processed.`);
                topStatusText.textContent = 'Complete';
                bottomStatus.textContent = `Completed — ${res.data.moved} file(s) ${dryRun ? 'simulated' : 'moved'}.`;
                await scanFolder();
            } else {
                addLog('error', `Organization failed: ${res.error}`);
                topStatusText.textContent = 'Error';
            }
        } catch (err) {
            addLog('error', `Organization error: ${err.message}`);
        } finally {
            isProcessing = false;
            setTimeout(() => { progressCard.style.display = 'none'; }, 800);
            await checkUndoStatus();
        }
    });

    // Undo Button
    btnUndo.addEventListener('click', async () => {
        if (!currentPath || isProcessing) return;
        isProcessing = true;
        topStatusText.textContent = 'Undoing...';

        addLog('warning', `Initiating undo operation on: ${currentPath}`);

        try {
            const res = await window.magor.undoLast(currentPath);
            if (res.success) {
                addLog('success', `Undo finished: ${res.data.restored} file(s) restored.`);
                bottomStatus.textContent = `Undo complete — ${res.data.restored} file(s) restored.`;
                topStatusText.textContent = 'Ready';
                await scanFolder();
            } else {
                addLog('error', `Undo failed: ${res.error || 'Unknown error'}`);
            }
        } catch (err) {
            addLog('error', `Undo error: ${err.message}`);
        } finally {
            isProcessing = false;
            await checkUndoStatus();
        }
    });

    // -------------------------------------------------------------------------
    // Stats & Visualizations
    // -------------------------------------------------------------------------
    function updateStats(data) {
        statFiles.textContent = data.totalFiles.toLocaleString();
        statFilesMeta.textContent = data.totalFiles === 1 ? '1 file detected' : `${data.totalFiles} files detected`;

        statSize.textContent = data.totalSizeFormatted;
        statSizeMeta.textContent = `${data.totalSizeFormatted} total volume`;

        statDuplicates.textContent = data.duplicates.toLocaleString();
        statDuplicatesMeta.textContent = data.duplicates === 0 ? 'No duplicates' : `${data.duplicates} identical copies`;

        const activeCatCount = Object.keys(data.categoryCounts || {}).length;
        statCategories.textContent = activeCatCount.toString();
        statCategoriesMeta.textContent = `${activeCatCount} active folders`;
    }

    function renderCategoryBar(data) {
        const counts = data.categoryCounts || {};
        const total = data.totalFiles;

        if (total === 0) {
            distributionCard.style.display = 'none';
            return;
        }

        distributionCard.style.display = 'block';
        distributionTotal.textContent = `${total} files categorized`;
        categoryBar.innerHTML = '';
        categoryLegend.innerHTML = '';

        const colors = {
            'Images': '#0071e3',
            'Documents': '#ff9500',
            'Archives': '#af52de',
            'Audio': '#ff2d55',
            'Video': '#5856d6',
            'Code': '#34c759',
            'Fonts': '#8e8e93',
            'Design': '#5ac8fa',
            'Others': '#c7c7cc'
        };

        for (const [cat, count] of Object.entries(counts)) {
            const pct = ((count / total) * 100).toFixed(1);

            // Bar segment
            const seg = document.createElement('div');
            seg.className = `bar-segment cat-${cat}`;
            seg.style.width = `${pct}%`;
            seg.style.backgroundColor = colors[cat] || '#999';
            seg.title = `${cat}: ${count} files (${pct}%)`;
            categoryBar.appendChild(seg);

            // Legend item
            const leg = document.createElement('div');
            leg.className = 'legend-item';

            const dot = document.createElement('span');
            dot.className = 'legend-dot';
            dot.style.backgroundColor = colors[cat] || '#999';

            const txt = document.createElement('span');
            txt.textContent = `${cat} (${count})`;

            leg.appendChild(dot);
            leg.appendChild(txt);
            categoryLegend.appendChild(leg);
        }
    }

    // -------------------------------------------------------------------------
    // Preview Table & Filtering
    // -------------------------------------------------------------------------
    let activeFilter = 'all';

    function renderTable(files) {
        previewTableBody.innerHTML = '';

        if (!files || files.length === 0) {
            previewTableBody.innerHTML = `<tr><td colspan="4" class="empty-table-cell">No files found in selected directory.</td></tr>`;
            return;
        }

        const searchTerm = previewSearch.value.toLowerCase().trim();

        const filtered = files.filter(f => {
            // Category / Duplicate filter
            if (activeFilter === 'duplicates' && !f.duplicate) return false;
            if (activeFilter !== 'all' && activeFilter !== 'duplicates' && f.category !== activeFilter) return false;

            // Search filter
            if (searchTerm) {
                const matchName = f.name.toLowerCase().includes(searchTerm);
                const matchCat = f.category.toLowerCase().includes(searchTerm);
                return matchName || matchCat;
            }
            return true;
        });

        if (filtered.length === 0) {
            previewTableBody.innerHTML = `<tr><td colspan="4" class="empty-table-cell">No files matching current search and filter.</td></tr>`;
            return;
        }

        filtered.slice(0, 300).forEach(f => {
            const tr = document.createElement('tr');

            const tdName = document.createElement('td');
            tdName.textContent = f.name;
            tdName.title = f.source;

            const tdCat = document.createElement('td');
            tdCat.innerHTML = `<span class="badge-tag" style="background: rgba(0, 113, 227, 0.1); color: #0071e3;">${f.category}</span>`;

            const tdSize = document.createElement('td');
            tdSize.textContent = f.sizeFormatted;

            const tdStatus = document.createElement('td');
            if (f.duplicate) {
                tdStatus.innerHTML = `<span class="badge-tag badge-dup">Duplicate SHA-256</span>`;
            } else {
                tdStatus.innerHTML = `<span class="badge-tag badge-ok">Ready</span>`;
            }

            tr.appendChild(tdName);
            tr.appendChild(tdCat);
            tr.appendChild(tdSize);
            tr.appendChild(tdStatus);

            previewTableBody.appendChild(tr);
        });
    }

    previewSearch.addEventListener('input', () => {
        if (currentScanData) renderTable(currentScanData.files);
    });

    filterPills.forEach(pill => {
        pill.addEventListener('click', () => {
            filterPills.forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            activeFilter = pill.dataset.filter;
            if (currentScanData) renderTable(currentScanData.files);
        });
    });

    // -------------------------------------------------------------------------
    // Log Actions
    // -------------------------------------------------------------------------
    btnClearLog.addEventListener('click', () => {
        activityConsole.innerHTML = '';
        logEntriesCount = 0;
        logCounter.textContent = '0 messages';
    });

    btnCopyLog.addEventListener('click', () => {
        const text = Array.from(activityConsole.querySelectorAll('.log-entry'))
            .map(entry => entry.innerText)
            .join('\n');
        navigator.clipboard.writeText(text);
        addLog('info', 'Log copied to clipboard.');
    });

    // -------------------------------------------------------------------------
    // Settings Pane Population
    // -------------------------------------------------------------------------
    const extMap = {
        "Images": [".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".bmp", ".tiff", ".ico", ".heic", ".avif", ".raw"],
        "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".md", ".xlsx", ".xls", ".ods", ".csv", ".ppt", ".pptx"],
        "Archives": [".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".iso", ".deb", ".rpm"],
        "Audio": [".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".opus", ".wma", ".alac"],
        "Video": [".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v"],
        "Code": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".yaml", ".sh", ".c", ".cpp", ".rs", ".go"],
        "Fonts": [".ttf", ".otf", ".woff", ".woff2"],
        "Design": [".psd", ".ai", ".eps", ".fig", ".sketch", ".xd", ".blend"]
    };

    for (const [cat, exts] of Object.entries(extMap)) {
        const card = document.createElement('div');
        card.className = 'cat-info-card';

        const title = document.createElement('div');
        title.className = 'cat-info-title';
        title.textContent = cat;

        const extText = document.createElement('div');
        extText.className = 'cat-info-exts';
        extText.textContent = exts.join('  ');

        card.appendChild(title);
        card.appendChild(extText);
        categoryGrid.appendChild(card);
    }
});
