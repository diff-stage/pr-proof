const fs = require('node:fs');

async function preflight() {
    const service = new URL(process.env.DIFF_STAGE_URL);
    if (service.protocol !== 'https:' || service.username || service.password) {
        throw new Error('Diff Stage preflight requires an HTTPS service URL.');
    }
    if (!process.env.ACTIONS_ID_TOKEN_REQUEST_URL || !process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN) {
        throw new Error('Grant id-token: write to the trusted preflight job.');
    }
    const identityUrl = new URL(process.env.ACTIONS_ID_TOKEN_REQUEST_URL);
    identityUrl.searchParams.set('audience', 'diff-stage');
    const identity = await fetch(identityUrl, {
        headers: {Authorization: `Bearer ${process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN}`},
        signal: AbortSignal.timeout(15000), redirect: 'error',
    });
    if (!identity.ok) throw new Error(`GitHub Actions identity request failed (${identity.status}).`);
    const {value} = await identity.json();
    if (typeof value !== 'string' || !value) throw new Error('GitHub returned no identity token.');
    console.log(`::add-mask::${value}`);
    const response = await fetch(new URL('/api/preflight', service), {
        headers: {Authorization: `Bearer ${value}`, Accept: 'application/json'},
        signal: AbortSignal.timeout(30000), redirect: 'error',
    });
    if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(`Diff Stage preflight failed (${response.status}): ${body.message || 'Check the repository GitHub App connection and team plan in Diff Stage.'}`);
    }
    const {selection = []} = await response.json();
    const tests = [...new Set(selection.map(entry => entry.file))].sort();
    fs.appendFileSync(process.env.GITHUB_OUTPUT, `tests=${tests.join(',')}\nselection=${JSON.stringify(selection)}\n`);
    if (process.env.GITHUB_EVENT_NAME !== 'pull_request') {
        console.log('Diff Stage repository access confirmed. Ready to record.');
    } else if (tests.length) {
        console.log(`Diff Stage repository access confirmed. Recording the browser tests named for this branch: ${tests.join(', ')}`);
    } else {
        console.log('Diff Stage repository access confirmed. No browser tests are named for this branch, so there is nothing to record. Name one with vendor/bin/diff-stage-show.');
    }
}
preflight().catch(error => { console.error(error.message); process.exitCode = 1; });
