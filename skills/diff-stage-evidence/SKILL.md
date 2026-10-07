---
name: diff-stage-evidence
description: Prepare or update PR browser evidence with the Diff Stage Pest recorder. Use to select existing scenarios, record the current commit, write Browser videos and Browser review, and verify published playback.
---

# Prepare PR browser evidence

Finish with a small set of current-commit videos, a note explaining what each proves, and the checks or blockers in the PR description. Keep required regression checks separate from reviewer recordings.

## 1. Check the environment and publication access

Inspect the project's existing browser tests and CI. Reuse its Docker image, services, database, fixtures, asset build and test command. Run the recorder inside that environment.

Confirm `vendor/diff-stage/recorder/bin/diff-stage-record` exists. If it is missing, report the installation requirement. Change dependencies or CI only within the user's authorized scope.

Before CI prepares the app, run the pinned `diff-stage/recorder/preflight` action in a trusted job with `id-token: write` and no application checkout. Make recording depend on its success. Keep identity and publishing permissions in trusted jobs; fork and Dependabot PRs produce artifacts only. On failure, report the response and the repository connection or team-plan issue it identifies.

This step is complete when the recording environment is identified and publication access is confirmed, or an exact blocker is reported.

## 2. Select journeys that prove the diff

Read the diff against the PR base and the existing browser tests. Map each browser-visible change to the smallest existing scenario that demonstrates it. Include changed test files only when their journeys prove the diff.

When a journey is missing, add or adjust a test within the authorized scope. Follow the project's fixtures and browser conventions. Use disposable data, one journey per test, readiness assertions for asynchronous behavior, and a visible final outcome. The recorder captures typed and rendered data without redaction. Use recorder pacing rather than fixed presentation waits.

Choose complete Pest names, including `it` and describe groups. Keep scenarios in their existing files. For changes without a useful browser demonstration, leave `Browser videos:` empty and name the independent checks under "Not shown".

This step is complete when every selected scenario maps to a change and every omission has a reason.

## 3. Record and inspect the current commit

Run the required regression checks. Commit the changes, then record from a clean tree. Save the selected scenarios as a JSON array:

```json
[
  {"file": "tests/Browser/BookingTest.php", "test": "it confirms an accepted booking"},
  {"file": "tests/Browser/CheckoutTest.php", "test": "it shows why a card was declined"}
]
```

Run in the existing browser environment:

```bash
rm -rf tests/Browser/Videos
mkdir -p tests/Browser/Videos
git rev-parse HEAD > tests/Browser/Videos/sha.txt
php vendor/diff-stage/recorder/bin/diff-stage-record selection.json --record-videos-fast
```

The runner checks every file and name before recording. Names are literal; a dataset scenario runs all its variants. Use `"test": null` only when every scenario in the file is intended evidence. `--record-videos-only` filters recording, while Pest's positional paths control execution; the JSON runner handles scenario selection.

Check that the run passed and every selected scenario produced its expected recordings. Copy flow keys from the filenames without `.webm`.

Watch every video at normal speed through its final state. Confirm the changed behavior and outcome are readable and the footage contains no secrets or personal data. Compress with `vendor/bin/diff-stage-compress input.webm output.mp4` if needed. Sampled frames can locate details; mark full playback review pending if you cannot watch the footage. Recapture after changing recorded behavior.

This step is complete when the full SHA, successful results, generated flow keys and playback findings are known. Report failed or uninspected recordings as blockers.

## 4. Write the PR evidence section

Preserve the rest of the PR description. Use one scenario per line:

```markdown
## Browser evidence

Browser videos: tests/Browser/BookingTest.php::it confirms an accepted booking
Browser videos: tests/Browser/CheckoutTest.php::it shows why a card was declined

Browser review:
1. `bookingtest-it-confirms-an-accepted-booking`: Shows the booking badge changing to Confirmed after acceptance.
2. `checkouttest-it-shows-why-a-card-was-declined`: Shows the new decline explanation beneath the card field.

Recorded at `<full commit SHA>`: 2 passed; both videos watched at normal speed.

Not shown: the confirmation email has no browser interaction. `tests/Feature/BookingAcceptedMailTest.php` covers it.
```

### Selection and notes

- `Browser videos:` selects execution and recording. A file-only line selects every test in that file. Choose either whole-file or scenario selection for each file.
- Pass `select.outputs.selection` as JSON to `diff-stage-record`. `select.outputs.tests` contains paths only and loses scenario selection. The selector includes matching explicit paths, deduplicated; changed files are candidates for inspection, not automatic selections.
- `Browser review:` adds notes and their order in the PR comment. Use the actual flow key and a reason under 1000 characters. The publisher warns and skips notes for unrecorded keys. Notes leave execution, recording and player grouping unchanged.
- With empty selection, omit review notes and explain the independent checks. Describe only the evidence produced and inspected.

This step is complete when the description names the exact scenarios, matches the generated flow keys, and states any omissions or review blockers.

## 5. Verify CI evidence

Editing the description starts a new evidence run when the workflow listens for `edited`, and may cancel an older run. Check the latest run for the current head.

With empty selection, confirm recording and publication were skipped. Treat any older evidence comment as historical.

With selected scenarios, check successful recording and publication, open the Diff Stage comment's player link, and compare its full SHA with the PR head and artifact's `sha.txt`. Confirm all selected videos and their notes are present. Watch the CI footage at normal speed and verify hosted playback through the final outcome. Private evidence may require a team member to sign in.

This step is complete when hosted footage matches the current head and plays correctly, or the handoff identifies the exact failed check, missing upload, stale SHA, authentication requirement or pending playback review. Follow the project's draft and review rules.
