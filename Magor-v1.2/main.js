const { app, BrowserWindow, ipcMain, dialog, shell, nativeImage } = require('electron');
const path = require('path');
const organizer = require('./src/organizer');

// Ensure Wayland/X11 binds the window to magor.desktop and its system icon
app.setName('magor');
app.setDesktopName('magor.desktop');

let mainWindow = null;

function createWindow() {
    const iconPath = path.join(__dirname, 'assets', 'icon.png');
    mainWindow = new BrowserWindow({
        width: 1060,
        height: 740,
        minWidth: 880,
        minHeight: 640,
        frame: false,
        backgroundColor: '#00000000',
        transparent: true,
        title: "Magor 1.2",
        icon: iconPath,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
            sandbox: false
        }
    });

    try {
        const img = nativeImage.createFromPath(iconPath);
        if (!img.isEmpty()) {
            mainWindow.setIcon(img);
        }
    } catch {
        // Fallback gracefully if nativeImage cannot load
    }

    mainWindow.loadFile(path.join(__dirname, 'src/renderer/index.html'));

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// Window control IPC handlers
ipcMain.on('window:minimize', () => {
    if (mainWindow) mainWindow.minimize();
});

ipcMain.on('window:maximize', () => {
    if (mainWindow) {
        if (mainWindow.isMaximized()) {
            mainWindow.unmaximize();
        } else {
            mainWindow.maximize();
        }
    }
});

ipcMain.on('window:close', () => {
    if (mainWindow) mainWindow.close();
});

// Dialog IPC handler
ipcMain.handle('dialog:select-folder', async () => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory', 'createDirectory'],
        title: 'Select Folder to Organize with Magor 1.2'
    });
    if (result.canceled || result.filePaths.length === 0) {
        return null;
    }
    return result.filePaths[0];
});

// Organizer IPC handlers
ipcMain.handle('organizer:scan', async (_event, targetDir, options) => {
    try {
        const onProgress = (data) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('organizer:progress', data);
            }
        };
        const result = await organizer.scanFolder(targetDir, options, onProgress);
        return { success: true, data: result };
    } catch (err) {
        return { success: false, error: err.message };
    }
});

ipcMain.handle('organizer:organize', async (_event, targetDir, options) => {
    try {
        const onLog = (data) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('organizer:log', data);
            }
        };
        const onProgress = (data) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('organizer:progress', data);
            }
        };
        const result = await organizer.organizeFolder(targetDir, options, onLog, onProgress);
        return { success: true, data: result };
    } catch (err) {
        return { success: false, error: err.message };
    }
});

ipcMain.handle('organizer:undo', async (_event, targetDir) => {
    try {
        const onLog = (data) => {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('organizer:log', data);
            }
        };
        const result = organizer.undoLast(targetDir, onLog);
        return { success: true, data: result };
    } catch (err) {
        return { success: false, error: err.message };
    }
});

ipcMain.handle('organizer:has-undo', (_event, targetDir) => {
    try {
        return organizer.hasUndoHistory(targetDir);
    } catch {
        return false;
    }
});

ipcMain.handle('shell:open-path', async (_event, targetPath) => {
    try {
        await shell.openPath(targetPath);
        return true;
    } catch {
        return false;
    }
});

app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
