# Diff Stage recorder

Readable videos of your Pest browser tests, posted on the pull request.

Reviewers see each changed flow working without checking out the branch. Fast capture keeps your tests moving. Diff Stage adds cursor movement and reading time after upload, while preserving real typing, scrolling and animations. Local recording with pauses remains available.

## Install

Install the recorder with Composer:

```bash
composer require --dev diff-stage/recorder:^0.3 -W
```

`-W` lets Composer change PHPUnit to a version Pest supports. A fresh Laravel app needs it.

Supports Pest 4 with Browser 4.3.1, and Pest 5 with Browser 5.1.2. Browser 5 requires PHP 8.4+ and the sockets extension. The recorder replaces four internal Browser classes while recording and rejects every other Browser version. Install the Playwright version required by your installed Browser package.

## Record locally

```bash
./vendor/bin/pest tests/Browser --record-videos
```

| Option | Default | What it does |
|---|---|---|
| `--record-videos[=DIR]` | `tests/Browser/Videos` | Turns recording on and sets the output folder |
| `--record-videos-only=A.php,B.php` | every test | Records only tests from these files; does not filter execution |
| `--record-videos-fast` | off | Capture for hosted processing without cursor or action pauses |
| `--record-videos-pause=MS` | `700` | Pause before each action |

Use `--record-videos-fast` with the publish action for hosted processing. Each upload supports up to 50 recordings and a 50 MB ZIP. CI finishes after upload; the player refreshes when processing completes. Functional waits still run.

Each test is saved as its own `.webm`, named after the test. Without `--record-videos`, Pest runs exactly as before.

Pass file paths to Pest to limit execution as well as recording:

```bash
./vendor/bin/pest tests/Browser/BookingTest.php --record-videos --record-videos-only=tests/Browser/BookingTest.php
```

File-only selection runs every browser test in the file. To run individual scenarios, save the selection as JSON and use the selection runner inside your existing test environment:

```json
[
  {"file": "tests/Browser/WizardTest.php", "test": "it saves a draft"},
  {"file": "tests/Browser/WizardTest.php", "test": "it completes the wizard"}
]
```

```bash
php vendor/diff-stage/recorder/bin/diff-stage-record selection.json --record-videos-fast
```

Use the complete Pest name, including `it` for `it()` tests and any describe groups. Names are literal, not regexes. A selected data-driven test runs all its dataset variants. Missing files or names fail before any recording starts. Use `"test": null` to select a whole file. Do not combine whole-file and scenario selection for the same file.

Run your regression suite separately without recording.

Next to each video, the recorder writes a `.json` file with what happened during the test:

```json
{
  "steps": [
    { "at": 0.26, "text": "Opened /tutor/ground-rules" },
    { "at": 0.56, "text": "Ticked \"Safeguarding\"" },
    { "at": 3.4, "text": "Clicked \"Log in\"", "attempts": 19, "failed": true }
  ],
  "problems": [
    { "at": 2.37, "kind": "console", "text": "Something broke in the widget" },
    { "at": 2.38, "kind": "http", "text": "404 GET /definitely-missing-endpoint", "count": 2 }
  ]
}
```

- `at` is seconds into the video.
- Steps come from clicks, ticks, typing and page changes. Typing steps name the field, never the value. Pressing a character key shows as "Pressed a key"; named keys like Enter stay visible.
- URLs keep their path and query keys. Query values become `…`, so `/reset?token=abc` is saved as `/reset?token=…`.
- `attempts` appears when Pest retried an action. `failed` marks a step that never worked.
- Problem kinds are `console` (console errors), `error` (uncaught exceptions), `http` (responses of 400 or above) and `network` (requests that failed). Repeats are counted, not listed again.

`vendor/bin/diff-stage-compress input.webm output.mp4` turns a recording into a trimmed MP4. It adds reading time after captured assertion outcomes, aiming for two seconds before the next caption change, and holds the final screen for two seconds. Checks that complete within the same captured frame stay together. These holds are added after the test runs. Do not add `wait()` calls to tests for video readability. If `input.json` exists, it also writes `output.mp4.json` with the times shifted to match trimming and added reading time.

## Compare approved flows

Reuse the same test environment on your default branch and record the same files or scenarios. You can pass a checked-in JSON selection to `diff-stage-record` for baselines, or record whole files there. Scenario selection does not change flow keys.

The service compares PR videos with the latest completed default-branch recording of the same flow. It shows baseline and PR videos side by side with paired playback controls, ordered actions and new or fixed browser problems. Without an approved recording to compare against, the service labels the PR video instead. "No approved baseline yet" means the project has no approved baseline. "No matching baseline" means no approved recording has this flow key. Neither label means the flow is new. The baseline may not be recorded yet, or the test may have been renamed.

Each flow key is the recording filename without `.webm`. Renaming a test changes its filename and flow key, so it no longer matches its old baseline. Keep the same recording workflow for baseline uploads: its GitHub `run_number` orders approvals so a slower, older run cannot replace a newer baseline.

Completing a PR run pins its baseline videos. Later approvals do not change that comparison. This compares videos and browser actions; it does not calculate visual differences.

## Post videos on pull requests

Install the Diff Stage GitHub App and connect your repositories at [diffstage.com](https://diffstage.com). Adapt your existing browser workflow, including its Docker image, services, environment, fixtures and assets. Run the recorder in the same container where Pest already works. Use the following job structure. GitHub Actions authenticates the upload, so you don't need a repository secret or service URL.

```yaml
on:
  pull_request:

permissions:
  contents: read

jobs:
  preflight:
    if: github.event.pull_request.head.repo.full_name == github.repository && github.actor != 'dependabot[bot]'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    outputs:
      tests: ${{ steps.preflight.outputs.tests }}
      selection: ${{ steps.preflight.outputs.selection }}
    steps:
      - id: preflight
        uses: diff-stage/recorder/preflight@8f500d53c4fec4783c34c9f2f4eaa48ce55c1951

  record:
    needs: preflight
    if: needs.preflight.outputs.tests != ''
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          persist-credentials: false

      # Reuse your existing Docker/browser CI setup here.

      - env:
          SELECTION: ${{ needs.preflight.outputs.selection }}
        run: |
          rm -rf tests/Browser/Videos
          printf '%s\n' "$SELECTION" > .diff-stage-selection.json
          # Run this inside your existing test container when using Docker.
          php vendor/diff-stage/recorder/bin/diff-stage-record .diff-stage-selection.json --record-videos-fast
          git rev-parse HEAD > tests/Browser/Videos/sha.txt

      - uses: actions/upload-artifact@v4
        with:
          name: browser-videos-${{ github.event.pull_request.head.sha }}
          path: tests/Browser/Videos
          if-no-files-found: error
          retention-days: 7

  publish:
    needs: [preflight, record]
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: browser-videos-${{ github.event.pull_request.head.sha }}
          path: tests/Browser/Videos

      - uses: diff-stage/recorder/publish@8f500d53c4fec4783c34c9f2f4eaa48ce55c1951
        with:
          selection: ${{ needs.preflight.outputs.selection }}
```

The jobs keep PR code away from publishing rights:

- `preflight` runs before app preparation, without checking out repository code. It requests GitHub identity, checks the App connection, current run and team plan, and returns the browser tests named for the branch. With nothing named, recording and publishing are skipped. Fork and Dependabot PRs skip preflight, so they aren't recorded.
- `record` checks out the PR's head commit, so the videos show the code the PR adds rather than GitHub's merge preview. It runs that code with a read-only token and no stored credentials.
- `publish` never runs PR code. It downloads the recordings and uploads them. It needs `id-token: write` to request GitHub identity and `pull-requests: write` to post its comment.
- The publisher refuses to upload if `sha.txt` names a different commit from the PR head.
- Never use `pull_request_target` to run PR code.

The examples pin `preflight` and `publish` to one reviewed commit. Update both pins together when you upgrade the Composer package.

Keep your existing regression jobs independent of this workflow. Empty evidence selection must not skip regression tests or turn them into reviewer videos.

The publisher uploads to `https://diffstage.com` using GitHub Actions identity, so the repository must be connected through the Diff Stage GitHub App. The PR comment links to the run, videos and posters returned by the service.

## Choose what reviewers see

Name each browser test that proves the change from the pull request branch:

```bash
vendor/bin/diff-stage-show "tests/Browser/BookingTest.php::it confirms an accepted booking" \
    --why "Accepting now confirms straight away. Watch the badge change to Confirmed."
```

The command asks Pest whether the test exists, then saves it and its note on Diff Stage for this repository and branch. Your commits and PR description stay untouched. The first time, it opens your browser to approve the sign-in, then carries on. If the browser can't open, follow the printed link.

On each push, `preflight` reads the branch's named tests and returns a `selection` JSON output for the runner, plus a `tests` file list for gating the record job. `publish` turns each note into what the PR comment says about that test's videos.

- Use the complete Pest name, including `it` and describe groups. Every dataset variant is recorded and shares the note.
- Name only a file path to record every test in it. Naming the whole file replaces its single tests, and the other way round.
- Run the command again to change a note. Run it with no arguments to list what the branch shows, or with `--clear` to show nothing.
- Name tests before pushing. Tests named after your latest push are recorded on the next one, or when you re-run the workflow.
- `vendor/bin/diff-stage-show logout` signs the computer out.

Changed browser test files are not added automatically. Check what each test demonstrates before naming it, including unchanged tests that reach the changed behavior. If no journey meaningfully demonstrates the diff, name nothing: preflight outputs an empty `tests` value and the workflow above skips recording and publication. Never substitute an unrelated smoke journey. A previous video comment may remain, so check its SHA before treating it as current evidence.

Notes over 1000 characters are cut, and names without a matching video are skipped with a warning. Baseline runs ignore the selection.

`publish` uploads each video to the Diff Stage service and keeps one comment on the PR up to date. The comment links to a page where every video plays with normal controls. It shows a still from the first three videos when the service says the still is public. Projects with protected private evidence get links only. PR runs are kept for 30 days. Current approved videos and baselines referenced by retained PR runs survive pruning.

## Prepare evidence with an agent

The recorder ships two skills and a short guideline for [Laravel Boost](https://github.com/laravel/boost):

- `diff-stage-evidence` names the tests that prove a change.
- [`pest-browser-testing`](https://github.com/diff-stage/pest-browser-testing) teaches agents to write and fix browser tests that fail only when the feature breaks.

After installing the recorder, run:

```bash
php artisan boost:update
```

Boost offers the new package. Accept it, and every agent Boost manages learns to name the tests that prove its change and explain what to watch, without being asked. The first time an agent names a test, your browser asks you to approve the sign-in.

Without Boost, copy the skills into your agent's skills folder, for example `.claude/skills` or `.agents/skills`:

```bash
cp -r vendor/diff-stage/recorder/resources/boost/skills/* .claude/skills/
```

## Record approved baselines

Add default-branch recording to the same recording workflow. Replace `main` below if your default branch has another name. Record the approved flows after booting the app, then publish only if the recording step passed:

```yaml
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  baselines:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      # ...install dependencies, start your app and install Playwright...
      - id: record
        run: ./vendor/bin/pest tests/Browser --record-videos
      - if: success() && steps.record.outcome == 'success'
        uses: diff-stage/recorder/publish@8f500d53c4fec4783c34c9f2f4eaa48ce55c1951
        with:
          mode: baseline
```

`mode` defaults to `pull_request`. Baseline mode accepts only `push` or `workflow_dispatch` on the repository's default branch and never posts a PR comment. The workflow must check the recording step's outcome, including when it uses `continue-on-error`. Clear the video directory before recording on persistent runners to avoid uploading files from an earlier run.

The publisher creates a run with its kind, commit SHA and branch. Baselines also send `source_order` from `github.run_number`. Supported browser assertions also record one check with its start time, finish time and pass/fail outcome. The player can show checking, verified and failed captions without exposing expected field values. Text checks redact values entered earlier in the recording. Custom script assertions are not captioned.

Each upload includes the filename-stem `flow_key`, MP4, JPEG poster and compressed JSON telemetry. Pull request uploads of a named test with a note also send `review_reason` and `review_order`. Recordings without telemetry send empty steps and problems for compatibility. It calls `/api/runs/{id}/complete` with `expected_videos` only after every upload succeeds. Failed or partial baseline runs never become approved. Completed runs are immutable.

## Licence

MIT. The files in `overrides/` are modified copies of classes from [pestphp/pest-plugin-browser](https://github.com/pestphp/pest-plugin-browser) (MIT); its licence is in `overrides/LICENSE-pest-plugin-browser.md`.
