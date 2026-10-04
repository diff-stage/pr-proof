---
name: pr-proof-evidence
description: Prepare browser video evidence for a pull request in a project that records Pest browser tests with pr-proof. Use while preparing or updating a PR to choose the journeys a reviewer should watch, add missing browser tests, record them at the current commit, and write the Browser videos and Browser review lines in the PR description.
---

# Prepare PR browser evidence

The goal is a short set of videos that show the change working, with a note on what to look at in each. A reviewer should be able to watch them in order without opening the code. Show only what the change does. Leave out loosely related flows.

This skill needs pr-proof installed (`vendor/bin/pr-proof-compress` exists). If it isn't, tell the user and stop. Don't install packages or change CI unless they ask.

## 1. Map changed files to journeys

- Read the diff against the PR's base branch and the existing browser tests. `tests/Browser/**/*Test.php` is the default; the project's `select` action may use another `pattern`.
- For each user-visible change, pick the smallest journey that shows it: an existing test, or one you add. Record which changed files each journey demonstrates. That mapping goes in the PR.
- Skip changes with no browser-visible effect, and say which other tests cover them. Don't record an unrelated flow to fill the gap.
- This is a demonstration, not a coverage report. Never claim the videos cover every affected test or path.

## 2. Add or adjust tests where needed

- Add a test when no existing one reaches the changed screen or state. Follow the project's browser test conventions, factories and fixtures.
- Assert the end state on screen, such as the confirmation text, so the video ends on proof instead of a redirect.
- Keep one journey per test, and keep it short. The recorder pauses before every action.
- Use fake data. Videos show whatever is typed and rendered, and pr-proof doesn't redact the picture.

## 3. Record at the current commit

Commit first so the recording matches a SHA. Then, with a clean working tree:

```bash
rm -rf tests/Browser/Videos
./vendor/bin/pest --record-videos --record-videos-only=tests/Browser/BookingTest.php,tests/Browser/CheckoutTest.php
git rev-parse HEAD | cut -c1-7
```

- `--record-videos-only` takes comma-separated paths relative to the project root.
- Each video's flow key is its filename without `.webm`, for example `bookingtest-it-confirms-an-accepted-booking`. Copy it from the file. Don't guess it from the test name.
- If a selected test fails, fix it or report it. Never present a failed run, or a recording from an older commit, as evidence.
- Watch each video. If you can't play video, run `vendor/bin/pr-proof-compress in.webm out.mp4` and inspect frames with `ffmpeg`. Check that the change is visible, the final state is readable, and no secret or personal data appears. A passing assertion doesn't prove the video is useful. If you couldn't inspect a video, say so.
- Re-record after any commit that changes the recorded behaviour.

## 4. Write the PR description

Add or update this section and keep the rest of the description:

```markdown
## Browser evidence

Browser videos: tests/Browser/BookingTest.php, tests/Browser/CheckoutTest.php

Browser review:
1. `bookingtest-it-confirms-an-accepted-booking`: `BookingController::accept` now confirms straight away. Watch the badge change to Confirmed after Accept.
2. `checkouttest-it-shows-why-a-card-was-declined`: New decline message from `CardErrors`. Check the text under the card field.

Recorded locally at `abc1234`: 2 passed, both videos watched.

Not shown: the confirmation email has no browser surface. `tests/Feature/BookingAcceptedMailTest.php` covers it.
```

- `Browser videos:` is one line, at the start of a line, listing test files separated by commas. CI records these plus any browser test files the PR changes. List unchanged tests you rely on too.
- `Browser review:` lists videos in the order to watch them, one per line: `` N. `flow-key`: reason ``. Each reason says which change the video proves and where to look, in under 1000 characters. pr-proof sends the reason and order with the upload and leads the PR comment with them. It skips items whose flow key wasn't recorded and logs a warning.
- Label a generic smoke flow as one, for example: "Smoke only: the app boots and the dashboard loads. It doesn't exercise this change."
- Put anything you couldn't show under "Not shown". Don't describe evidence you didn't produce.

## 5. Check CI evidence matches the head

Editing the description re-runs the workflow when it listens for `edited`. After CI finishes, the pr-proof comment's heading names the commit: `Browser test videos for abc1234`. Confirm it matches `git rev-parse HEAD | cut -c1-7` and that each reviewed video appears under "What to check". If the recording failed, the comment is missing, or it names an older commit, say so in your handoff. Don't describe the evidence as current until it is.
