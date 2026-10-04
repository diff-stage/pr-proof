# pr-proof

Readable videos of your Pest browser tests, posted on the pull request.

Reviewers see each changed flow working without checking out the branch. The recorder pauses before every click and keystroke, trims blank frames and holds the final screen, so a two-second test becomes a video someone can follow.

## Install

```bash
composer require --dev wardy484/pr-proof
```

Requires `pestphp/pest-plugin-browser` 4.3.1. pr-proof replaces three of its internal classes while recording, so it supports one exact version and stops with an error on any other.

## Record locally

```bash
./vendor/bin/pest tests/Browser --record-videos
```

| Option | Default | What it does |
|---|---|---|
| `--record-videos[=DIR]` | `tests/Browser/Videos` | Turns recording on and sets the output folder |
| `--record-videos-only=A.php,B.php` | every test | Records only tests from these files |
| `--record-videos-pause=MS` | `700` | Pause before each action |

Each test is saved as its own `.webm`, named after the test. Without `--record-videos`, Pest runs exactly as before.

Next to each video, pr-proof writes a `.json` file with what happened during the test:

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
- Steps come from clicks, ticks, typing and page changes. Typing into password, card or token fields doesn't show the value.
- `screenshot` is the screen once that step finished, saved as a JPEG in a folder named after the test. When a step causes a page change, it and the following "Opened" step share the new page's screenshot.
- `attempts` appears when Pest retried an action. `failed` marks a step that never worked.
- Problem kinds are `console` (console errors), `error` (uncaught exceptions), `http` (responses of 400 or above) and `network` (requests that failed). Repeats are counted, not listed again.

`vendor/bin/pr-proof-compress input.webm output.mp4` turns a recording into a trimmed MP4. If `input.json` exists, it also writes `output.json` with the times shifted to match the trimmed video.

## Compare with the base branch

Record the same tests on the PR's base branch into a second folder, then:

```bash
vendor/bin/pr-proof-compare base-videos/ tests/Browser/Videos/
```

For each test it writes `<test>.compare.json`:

```json
{
  "base_available": true,
  "steps": [
    {
      "status": "changed",
      "text": "Opened /tutor/ground-rules",
      "changed_pixels": 0.00266,
      "base": { "at": 0.28, "screenshot": "<test>/base/01.jpg" },
      "head": { "at": 0.28, "screenshot": "<test>/01.jpg" },
      "highlight": "<test>/changes/01.jpg"
    },
    { "status": "same", "text": "Opened /tutor/dashboard", "changed_pixels": 0.0 }
  ],
  "new_problems": [],
  "fixed_problems": []
}
```

- Steps from both runs are matched by caption. `status` is `same`, `changed` (the screen differs), `added` (only in the PR) or `removed` (only on the base branch).
- `changed_pixels` is the share of the screen that differs. Identical screens score `0.0`. A screen counts as changed above 0.05%.
- `highlight` is the PR's screenshot with the changed areas painted red.
- `new_problems` and `fixed_problems` compare browser problems between the runs, ignoring hosts and ports that change every run.
- Base screenshots are copied into the PR's video folder, so one folder holds everything to upload.
- Needs `ffmpeg` and `python3`.

## Post videos on pull requests

Run this as its own workflow, so your main test suite stays untouched. Boot your app the way your browser test workflow already does, then:

```yaml
on:
  pull_request:
    types: [opened, synchronize, reopened, edited]

jobs:
  videos:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4

      - id: select
        uses: wardy484/pr-proof/select@main

      # ...start your app and install Playwright here...

      - if: steps.select.outputs.tests != ''
        run: ./vendor/bin/pest --record-videos --record-videos-only=${{ steps.select.outputs.tests }}

      - if: steps.select.outputs.tests != ''
        uses: wardy484/pr-proof/publish@main
        with:
          url: https://your-pr-proof-host
          api-token: ${{ secrets.PR_PROOF_TOKEN }}
```

`select` records the browser test files the PR changes. To record others, add a line to the PR description:

```
Browser videos: tests/Browser/CheckoutTest.php, tests/Browser/BookingTest.php
```

`publish` uploads each video to the pr-proof service and keeps one comment on the PR up to date. The comment shows a still from each test and links to a page where every video plays with normal controls. Videos are kept for 30 days.

## Licence

MIT. The files in `overrides/` are modified copies of classes from [pestphp/pest-plugin-browser](https://github.com/pestphp/pest-plugin-browser) (MIT); its licence is in `overrides/LICENSE-pest-plugin-browser.md`.
