# Diff Stage recorder

Readable videos of your Pest browser tests, posted on the pull request.

Reviewers see each changed flow working without checking out the branch. Fast capture keeps your tests moving. Diff Stage adds cursor movement and reading time after upload, while preserving real typing, scrolling and animations. Local recording with pauses remains available.

## Install

The Diff Stage recorder isn't on Packagist yet, so add its GitHub repository before requiring it:

```bash
composer config repositories.diff-stage vcs https://github.com/diff-stage/recorder
composer require --dev diff-stage/recorder:dev-main -W
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

The service compares PR videos with the latest completed default-branch recording of the same flow. It shows baseline and PR videos side by side with paired playback controls, ordered actions and new or fixed browser problems. Without an approved recording to compare against, the service labels the PR video instead. "Baseline unavailable" means the project has no approved baseline yet. "No matching baseline" means no approved recording has this flow key. Neither label means the flow is new. The baseline may not be recorded yet, or the test may have been renamed.

Each flow key is the recording filename without `.webm`. Renaming a test changes its filename and flow key, so it no longer matches its old baseline. Keep the same recording workflow for baseline uploads: its GitHub `run_number` orders approvals so a slower, older run cannot replace a newer baseline.

Completing a PR run pins its baseline videos. Later approvals do not change that comparison. This compares videos and browser actions; it does not calculate visual differences.

## Post videos on pull requests

Install the Diff Stage GitHub App and connect your repositories at [diffstage.com](https://diffstage.com). Adapt your existing browser workflow, including its Docker image, services, environment, fixtures and assets. Run the recorder in the same container where Pest already works. Use the following job structure. GitHub Actions authenticates the upload, so you don't need a repository secret or service URL.

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, edited]

permissions:
  contents: read

jobs:
  preflight:
    if: github.event.pull_request.head.repo.full_name == github.repository && github.actor != 'dependabot[bot]'
    runs-on: ubuntu-latest
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: diff-stage/recorder/preflight@main

  record:
    needs: preflight
    if: always() && (needs.preflight.result == 'success' || needs.preflight.result == 'skipped')
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
    outputs:
      tests: ${{ steps.select.outputs.tests }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          persist-credentials: false

      - id: select
        uses: diff-stage/recorder/select@main

      # Reuse your existing Docker/browser CI setup here.
      # Gate expensive setup on steps.select.outputs.tests != ''.

      - if: steps.select.outputs.tests != ''
        env:
          SELECTION: ${{ steps.select.outputs.selection }}
        run: |
          rm -rf tests/Browser/Videos
          printf '%s\n' "$SELECTION" > .diff-stage-selection.json
          # Run this inside your existing test container when using Docker.
          php vendor/diff-stage/recorder/bin/diff-stage-record .diff-stage-selection.json --record-videos-fast
          git rev-parse HEAD > tests/Browser/Videos/sha.txt

      - if: steps.select.outputs.tests != ''
        uses: actions/upload-artifact@v4
        with:
          name: browser-videos-${{ github.event.pull_request.head.sha }}
          path: tests/Browser/Videos
          if-no-files-found: error
          retention-days: 7

  publish:
    needs: record
    if: needs.record.outputs.tests != '' && github.event.pull_request.head.repo.full_name == github.repository
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

      - uses: diff-stage/recorder/publish@v0.2.1
```

The jobs keep PR code away from publishing rights:

- `preflight` runs before app preparation, without checking out repository code. It requests GitHub identity and checks the App connection, current run and team plan. A failure stops the recording job. Fork and Dependabot PRs skip preflight and keep artifact-only recordings.
- `record` checks out the PR's head commit, so the videos show the code the PR adds rather than GitHub's merge preview. It runs that code with a read-only token and no stored credentials.
- `publish` never runs PR code. It downloads the recordings and uploads them. It needs `id-token: write` to request GitHub identity and `pull-requests: write` to post its comment.
- The publisher refuses to upload if `sha.txt` names a different commit from the PR head.
- Fork PRs still record, and their videos stay as workflow artifacts. They can't publish through the App. Never use `pull_request_target` to run PR code.

Scenario selection and preflight require a commit containing this change. Pin a reviewed full commit SHA for `select`, `preflight` and the Composer package before using them in production. The `v0.1.0` selector adds changed files automatically, so use `v0.2.0` or later.

Keep your existing regression jobs independent of this workflow. Empty evidence selection must not skip regression tests or turn them into reviewer videos.

The publisher defaults to `https://diffstage.com`. Set `url` to override the endpoint for a self-hosted service. An explicit `api-token` takes precedence over GitHub identity for services that support project tokens. The hosted service requires a GitHub App connection and GitHub Actions identity.

Existing workflow pins keep their original default until you update them to a commit containing this change. To use the new domain with an older publisher, add `url: https://diffstage.com` under its `with` inputs. Replace any explicit Cloud hostname override too. The publisher uses the run, video and poster URLs returned by the service in its PR comment.

`select` returns a `selection` JSON output for the runner and a `tests` file list for gating setup. Add one line per scenario in the PR description:

```
Browser videos: tests/Browser/WizardTest.php::it saves a draft
Browser videos: tests/Browser/WizardTest.php::it completes the wizard
```

Changed browser test files are not added automatically. Check what each file demonstrates before selecting it, including unchanged tests that reach the changed behaviour. Paths must match the action's `pattern` regex, which defaults to `^tests/Browser/.+Test\.php$`. File-only lines still accept comma-separated paths and run every test in those files. Scenario lines use `file::complete Pest name`, one per line. Selection is deduplicated. `Browser review:` only adds notes and ordering; it never limits execution or recording.

If no journey meaningfully demonstrates the diff, leave `Browser videos:` empty or omit it. The selector outputs an empty `tests` value and logs that recording is skipped. The workflow above then skips recording and publication. List omitted journeys and their reasons in the PR description. Never substitute an unrelated smoke journey. A previous video comment may remain, so check its SHA before treating it as current evidence.

`publish` uploads each video to the Diff Stage service and keeps one comment on the PR up to date. The comment links to a page where every video plays with normal controls. It shows a still from the first three videos when the service says the still is public. Projects with protected private evidence get links only. PR runs are kept for 30 days. Current approved videos and baselines referenced by retained PR runs survive pruning.

## Tell reviewers what to watch

Add a `Browser review:` list to the PR description to order the videos and say what each one proves:

```markdown
Browser review:
1. `bookingtest-it-confirms-an-accepted-booking`: Accepting now confirms straight away. Watch the badge change to Confirmed.
2. `checkouttest-it-shows-why-a-card-was-declined`: Check the new message under the card field.
```

Each item is a number, the flow key in backticks, a colon or dash, and the reason. The list ends at the first line that isn't an item or blank. `publish` uploads these videos first, in list order, and the comment opens with a "What to check" list. Reasons over 1000 characters are cut. Flow keys without a matching video are skipped with a warning. Baseline runs ignore the list.

The list renders as plain Markdown, so reviewers can read it in the description too.

## Prepare evidence with an agent

`skills/diff-stage-evidence` is an agent skill for Claude Code, Codex and other tools that read `SKILL.md` skills. While preparing a PR, the agent reads the diff and your browser tests, picks the smallest journeys that show the change, adds tests where none exist, records them at the current commit and writes the `Browser videos:` and `Browser review:` lines. It lists omitted journeys and their reasons. It never blindly selects all changed browser tests, and leaves selection empty when none prove the diff.

The skill is one Markdown file. Read it before installing, then copy it into your project:

```bash
# Claude Code
mkdir -p .claude/skills
cp -r vendor/diff-stage/recorder/skills/diff-stage-evidence .claude/skills/

# Codex
mkdir -p .agents/skills
cp -r vendor/diff-stage/recorder/skills/diff-stage-evidence .agents/skills/
```

Copy it to `~/.claude/skills` or `~/.agents/skills` to use it across projects. Copy it again after upgrading the recorder.

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
        uses: diff-stage/recorder/publish@v0.2.1
        with:
          mode: baseline
```

`mode` defaults to `pull_request`. Baseline mode accepts only `push` or `workflow_dispatch` on the repository's default branch and never posts a PR comment. The workflow must check the recording step's outcome, including when it uses `continue-on-error`. Clear the video directory before recording on persistent runners to avoid uploading files from an earlier run.

The publisher creates a run with its kind, commit SHA and branch. Baselines also send `source_order` from `github.run_number`. Supported browser assertions also record one check with its start time, finish time and pass/fail outcome. The player can show checking, verified and failed captions without exposing expected field values. Text checks redact values entered earlier in the recording. Custom script assertions are not captioned.

Each upload includes the filename-stem `flow_key`, MP4, JPEG poster and compressed JSON telemetry. Pull request uploads named in `Browser review:` also send `review_reason` and `review_order`. Recordings without telemetry send empty steps and problems for compatibility. It calls `/api/runs/{id}/complete` with `expected_videos` only after every upload succeeds. Failed or partial baseline runs never become approved. Completed runs are immutable.

## Licence

MIT. The files in `overrides/` are modified copies of classes from [pestphp/pest-plugin-browser](https://github.com/pestphp/pest-plugin-browser) (MIT); its licence is in `overrides/LICENSE-pest-plugin-browser.md`.
