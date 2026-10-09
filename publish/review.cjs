// Matches the reviewer notes in a branch's Diff Stage selection to the videos that were recorded.
// stdin holds the preflight action's selection: [{file, test, note}], in the order they were named.
const fs = require('node:fs');

const [titlesFile, ...names] = process.argv.slice(2);
const selection = JSON.parse(fs.readFileSync(0, 'utf8') || '[]');
const titles = fs.existsSync(titlesFile) ? JSON.parse(fs.readFileSync(titlesFile, 'utf8')) : {};

// Titles look like `BookingTest › it confirms an accepted booking with dataset "mobile"`.
function matches(entry, title) {
    const prefix = `${entry.file.split('/').pop().replace(/\.php$/, '')} › `;
    if (!title.startsWith(prefix)) return false;
    const name = title.slice(prefix.length);
    return entry.test === null || name === entry.test || name.startsWith(`${entry.test} with data`);
}

const review = [];
selection.forEach((entry, index) => {
    const recorded = names.filter(name => matches(entry, titles[`${name}.webm`] ?? ''));
    if (!recorded.length) console.error(`::warning::Diff Stage selection names ${entry.file}${entry.test ? `::${entry.test}` : ''}, but no video matches it.`);
    if (!entry.note) return;
    for (const name of recorded) review.push({flow_key: name, reason: entry.note.slice(0, 1000), order: index + 1});
});
process.stdout.write(JSON.stringify(review));
