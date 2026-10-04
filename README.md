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

`vendor/bin/pr-proof-compress input.webm output.mp4` turns a recording into a trimmed MP4.

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
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.VIDEO_AWS_ID }}
          aws-secret-access-key: ${{ secrets.VIDEO_AWS_KEY }}
          aws-region: us-east-1

      - if: steps.select.outputs.tests != ''
        uses: wardy484/pr-proof/publish@main
        with:
          bucket: your-video-bucket
```

`select` records the browser test files the PR changes. To record others, add a line to the PR description:

```
Browser videos: tests/Browser/CheckoutTest.php, tests/Browser/BookingTest.php
```

`publish` uploads each video to your S3 bucket and keeps one comment on the PR up to date, with a preview and a link to the full video for every test. Links last 7 days.

## Licence

MIT. The files in `overrides/` are modified copies of classes from [pestphp/pest-plugin-browser](https://github.com/pestphp/pest-plugin-browser) (MIT); its licence is in `overrides/LICENSE-pest-plugin-browser.md`.
