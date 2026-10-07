const fs = require('node:fs');

const pattern = new RegExp(process.env.PATTERN);
const selection = [];
for (const line of (process.env.PR_BODY || '').replaceAll('\r', '').split('\n')) {
    const match = /^Browser videos: *(.*)$/i.exec(line);
    if (!match) continue;
    const value = match[1].trim();
    const separator = value.indexOf('::');
    const entries = separator === -1
        ? value.split(/[ ,]+/).map(file => ({file, test: null}))
        : [{file: value.slice(0, separator).trim(), test: value.slice(separator + 2).trim()}];
    for (const entry of entries) {
        if (!pattern.test(entry.file) || !/^[a-zA-Z0-9_./-]+$/.test(entry.file)
            || entry.file.startsWith('/') || entry.file.includes('..')) continue;
        if (entry.test === '') throw new Error(`Missing scenario name for ${entry.file}`);
        if (!selection.some(item => item.file === entry.file && item.test === entry.test)) selection.push(entry);
    }
}
const files = [...new Set(selection.map(item => item.file))].sort();
for (const file of files) {
    const entries = selection.filter(item => item.file === file);
    if (entries.length > 1 && entries.some(item => item.test === null)) {
        throw new Error(`Select either the whole file or individual scenarios for ${file}, not both.`);
    }
}
fs.appendFileSync(process.env.GITHUB_OUTPUT, `tests=${files.join(',')}\nselection=${JSON.stringify(selection)}\n`);
console.log(files.length ? `Recording requested browser tests: ${files.join(',')}` : 'No matching Browser videos: files selected; skipping recording.');
