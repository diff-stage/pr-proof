// Renders the pull request comment from one JSON video per stdin line:
// {title, url, poster_url, poster_public, reason}. Dataset variants of the same
// test share one heading, note and poster, with a link per variant.
const fs = require('node:fs');

const html = value => String(value ?? '').replace(/[&<>"']/g, character => `&#${character.charCodeAt(0)};`);
const videos = fs.readFileSync(0, 'utf8').split('\n').filter(Boolean).map(line => JSON.parse(line));

const groups = new Map();
for (const video of videos) {
    const [, test = video.title, variant] = /^(.*?)(?: with data ?set "(.*)")?$/s.exec(video.title);
    const group = groups.get(test) ?? {test, videos: []};
    group.videos.push({...video, variant});
    groups.set(test, group);
}

const lines = [
    '<!-- diff-stage -->',
    `### Browser videos for \`${process.env.HEAD_SHA.slice(0, 7)}\``,
    '',
    `**[Watch all ${videos.length} on Diff Stage](${process.env.RUN_URL})**`,
    '',
];
if (process.env.PROCESSING === 'true') lines.push('Processing on Diff Stage. Each video plays there as soon as it is ready.', '');

for (const {test, videos: variants} of groups.values()) {
    const [first] = variants;
    const separator = test.indexOf(' › ');
    const file = separator === -1 ? '' : test.slice(0, separator);
    const name = separator === -1 ? test : test.slice(separator + 3);
    const reason = variants.find(video => video.reason)?.reason;
    const links = variants.length > 1
        ? variants.map((video, index) => `<a href="${html(video.url)}">${html(video.variant ?? `Video ${index + 1}`)}</a>`)
        : [];

    lines.push(`<h4><a href="${html(first.url)}">${html(name.charAt(0).toUpperCase() + name.slice(1))}</a></h4>`, '');
    if (reason) lines.push(`<p>${html(reason)}</p>`, '');
    if (first.poster_public && first.poster_url) {
        lines.push(`<p><a href="${html(first.url)}"><img src="${html(first.poster_url)}" width="640" alt="${html(first.title)}"></a></p>`, '');
    }
    const details = [file && html(file), ...links].filter(Boolean);
    if (details.length) lines.push(`<p><sub>${details.join(' · ')}</sub></p>`, '');
}

process.stdout.write(lines.join('\n'));
