#!/usr/bin/env node
/**
 * Magor 1.2 — Smart File Organizer for Linux Debian & Ubuntu
 *
 * CLI + Electron Liquid Glass GUI
 */

const path = require('path');
const { spawn } = require('child_process');
const organizer = require('./src/organizer');
const readline = require('readline');

function printHelp() {
    console.log(`Magor 1.2 — Smart File Organizer for Linux.

Usage:
  node magor.js [path] [options]

Options:
  --gui             Launch the macOS Liquid Glass desktop application
  -r, --recursive   Scan subfolders recursively
  --hidden          Include hidden files
  -n, --dry-run     Preview changes without moving files
  --undo            Undo the last organization
  -h, --help        Show this help message
`);
}

function promptUser(question) {
    return new Promise(resolve => {
        const rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout,
        });
        rl.question(question, answer => {
            rl.close();
            resolve(answer.trim());
        });
    });
}

function launchGui() {
    const electronBinary = path.join(__dirname, 'node_modules', '.bin', 'electron');
    const child = spawn(electronBinary, ['--no-sandbox', __dirname], {
        detached: true,
        stdio: 'ignore'
    });
    child.unref();
}

async function main() {
    const args = process.argv.slice(2);
    let targetPath = null;
    let recursive = false;
    let hidden = false;
    let dryRun = false;
    let undo = false;
    let gui = false;

    for (const arg of args) {
        if (arg === '-h' || arg === '--help') {
            printHelp();
            process.exit(0);
        } else if (arg === '--gui') {
            gui = true;
        } else if (arg === '-r' || arg === '--recursive') {
            recursive = true;
        } else if (arg === '--hidden') {
            hidden = true;
        } else if (arg === '-n' || arg === '--dry-run') {
            dryRun = true;
        } else if (arg === '--undo') {
            undo = true;
        } else if (!arg.startsWith('-') && !targetPath) {
            targetPath = arg;
        }
    }

    const hasDisplay = Boolean(process.env.DISPLAY || process.env.WAYLAND_DISPLAY);

    // If --gui explicitly requested, or if no target path provided and graphical desktop exists, launch GUI
    if (gui || (!targetPath && !undo && hasDisplay && args.length === 0)) {
        launchGui();
        process.exit(0);
    }

    if (!targetPath && !undo) {
        targetPath = await promptUser("Enter directory path to organize: ");
    }

    if (!targetPath && !undo) {
        console.error("Error: no directory path given.");
        process.exit(1);
    }

    if (undo) {
        if (!targetPath) targetPath = process.cwd();
        const res = organizer.undoLast(targetPath, log => console.log(log.message));
        process.exit(res.success ? 0 : 1);
    }

    try {
        const res = await organizer.organizeFolder(
            targetPath,
            { recursive, includeHidden: hidden, dryRun },
            log => console.log(log.message)
        );
        console.log(`Result: ${res.moved} file(s) processed.`);
        process.exit(0);
    } catch (err) {
        console.error(`Error: ${err.message}`);
        process.exit(1);
    }
}

if (require.main === module) {
    main();
}

module.exports = organizer;
