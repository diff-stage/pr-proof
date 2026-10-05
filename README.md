# Diff Stage recorder

Readable videos of your Pest browser tests, posted on the pull request.

Reviewers see each changed flow working without checking out the branch. The recorder pauses before every click and keystroke, trims blank frames and holds the final screen, so a two-second test becomes a video someone can follow.

## Install

The Diff Stage recorder isn't on Packagist yet, so add its GitHub repository before requiring it:

```bash
composer config repositories.diff-stage vcs https://github.com/diff-stage/recorder
composer require --dev diff-stage/recorder:^0.2 -W
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
| `--record-videos-pause=MS` | `700` | Pause before each action |

Each test is saved as its own `.webm`, named after the test. Without `--record-videos`, Pest runs exactly as before.

Pass file paths to Pest to limit execution as well as recording:

```bash
./vendor/bin/pest tests/Browser/BookingTest.php --record-videos --record-videos-only=tests/Browser/BookingTest.php
```

All browser tests in a selected file can produce videos. Run your regression suite separately without `--record-videos`.

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

`vendor/bin/diff-stage-compress input.webm output.mp4` turns a recording into a trimmed MP4. If `input.json` exists, it also writes `output.mp4.json` with the times shifted to match the trimmed video.

## Compare approved flows

The service compares PR videos with the latest completed default-branch recording of the same flow. It shows baseline and PR videos side by side with paired playback controls, ordered actions and new or fixed browser problems. Without an approved recording to compare against, the service labels the PR video instead. "Baseline unavailable" means the project has no approved baseline yet. "No matching baseline" means no approved recording has this flow key. Neither label means the flow is new. The baseline may not be recorded yet, or the test may have been renamed.

Each flow key is the recording filename without `.webm`. Renaming a test changes its filename and flow key, so it no longer matches its old baseline. Keep the same recording workflow for baseline uploads: its GitHub `run_number` orders approvals so a slower, older run cannot replace a newer baseline.

Completing a PR run pins its baseline videos. Later approvals do not change that comparison. This compares videos and browser actions; it does not calculate visual differences.

## Post videos on pull requests

Install the Diff Stage GitHub App and connect your repositories in Diff Stage. Then add this workflow, filling in your app and browser test setup. GitHub Actions authenticates the upload, so you don't need a repository secret or service URL.

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, edited]

permissions:
  contents: read

jobs:
  record:
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
        uses: diff-stage/recorder/select@v0.2.0

      # ...install dependencies, start your app and install Playwright here...

      - if: steps.select.outputs.tests != ''
        env:
          TESTS: ${{ steps.select.outputs.tests }}
        run: |
          rm -rf tests/Browser/Videos
          IFS=, read -ra tests <<< "$TESTS"
          ./vendor/bin/pest "${tests[@]}" --record-videos --record-videos-only="$TESTS"
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

      - uses: diff-stage/recorder/publish@v0.2.0
```

The two jobs keep PR code away from publishing rights:

- `record` checks out the PR's head commit, so the videos show the code the PR adds rather than GitHub's merge preview. It runs that code with a read-only token and no stored credentials.
- `publish` never runs PR code. It downloads the recordings and uploads them. It needs `id-token: write` to request GitHub identity and `pull-requests: write` to post its comment.
- The publisher refuses to upload if `sha.txt` names a different commit from the PR head.
- Fork PRs still record, and their videos stay as workflow artifacts. They can't publish through the App. Never use `pull_request_target` to run PR code.

The examples use `v0.2.0`. You can pin full commit SHAs instead. The `v0.1.0` selector adds changed files automatically, so use `v0.2.0` or later.

Keep your existing regression jobs independent of this workflow. Empty evidence selection must not skip regression tests or turn them into reviewer videos.

For self-hosted services or projects without an App connection, the existing `url` and `api-token` inputs still work. An explicit project token takes precedence over GitHub identity.

`select` returns only browser test files explicitly requested in the PR description. Add one line with the smallest journeys that prove the diff:

```
Browser videos: tests/Browser/CheckoutTest.php, tests/Browser/BookingTest.php
```

Changed browser test files are not added automatically. Check what each file demonstrates before selecting it, including unchanged tests that reach the changed behaviour. Paths must match the action's `pattern` regex, which defaults to `^tests/Browser/.+Test\.php$`. Matching paths are deduplicated; this is a file list, not a glob or individual test filter.

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
        uses: diff-stage/recorder/publish@v0.2.0
        with:
          mode: baseline
```

`mode` defaults to `pull_request`. Baseline mode accepts only `push` or `workflow_dispatch` on the repository's default branch and never posts a PR comment. The workflow must check the recording step's outcome, including when it uses `continue-on-error`. Clear the video directory before recording on persistent runners to avoid uploading files from an earlier run.

The publisher creates a run with its kind, commit SHA and branch. Baselines also send `source_order` from `github.run_number`. Supported browser assertions also record one check with its start time, finish time and pass/fail outcome. The player can show checking, verified and failed captions without exposing expected field values. Text checks redact values entered earlier in the recording. Custom script assertions are not captioned.

Each upload includes the filename-stem `flow_key`, MP4, JPEG poster and compressed JSON telemetry. Pull request uploads named in `Browser review:` also send `review_reason` and `review_order`. Recordings without telemetry send empty steps and problems for compatibility. It calls `/api/runs/{id}/complete` with `expected_videos` only after every upload succeeds. Failed or partial baseline runs never become approved. Completed runs are immutable.

## Licence

MIT. The files in `overrides/` are modified copies of classes from [pestphp/pest-plugin-browser](https://github.com/pestphp/pest-plugin-browser) (MIT); its licence is in `overrides/LICENSE-pest-plugin-browser.md`.
