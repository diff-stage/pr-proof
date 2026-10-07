---
name: diff-stage-evidence
description: Prepare browser video evidence for a pull request in a project that records Pest browser tests with the Diff Stage recorder. Use while preparing or updating a PR to choose the journeys a reviewer should watch, add missing browser tests, record them at the current commit, and write the Browser videos and Browser review lines in the PR description.
---

# Prepare PR browser evidence

The goal is a short set of videos that show the change working, with a note on what to look at in each. A reviewer should be able to watch them in order without opening the code. Show only what the change does. Leave out loosely related flows.

This skill needs the Diff Stage recorder installed (`vendor/bin/diff-stage-compress` exists). If it isn't, tell the user and stop. Don't install packages or change CI unless they ask.

Before preparing the app or recording in CI, use the `preflight` action in a trusted job with `id-token: write`, without checking out application code. It checks the connected GitHub repository and publication access. Reuse the project's existing browser CI and Docker environment. Keep identity and publishing permissions out of the recording job. Record the same scenarios on the default branch for comparisons.

## 1. Map changed files to journeys

- Read the diff against the PR's base branch and the existing browser tests. `tests/Browser/**/*Test.php` is the default; the project's `select` action may use another `pattern`.
- For each user-visible change, pick the smallest journey that shows it: an existing test, or one you add. Record which changed files each journey demonstrates. That mapping goes in the PR.
- Select evidence deliberately. A changed browser test is only a candidate, not a reason to publish its video. List every selected file explicitly, including changed files. Never copy all changed browser test files into the selection without checking what each proves.
- Skip changes with no browser-visible effect, and say which other tests cover them. Don't record an unrelated flow to fill the gap.
- If no journey meaningfully proves the diff, leave `Browser videos:` empty and explain why under "Not shown". Do not substitute a smoke journey. No selection means no reviewer recordings.
- This is a demonstration, not a coverage report. Never claim the videos cover every affected test or path.

## 2. Add or adjust tests where needed

- Add a test when no existing one reaches the changed screen or state. Follow the project's browser test conventions, factories and fixtures.
- Assert the end state on screen, such as the confirmation text, so the video ends on proof instead of a redirect.
- Keep one journey per test, and keep it short. The recorder pauses before actions, and video processing adds reading time after captured checks. Never add fixed waits to tests for presentation. Use readiness assertions for asynchronous behavior.
- Use fake data. Videos show whatever is typed and rendered, and Diff Stage doesn't redact the picture.

## 3. Record at the current commit

Commit first so the recording matches a SHA. Then, with a clean working tree:

```bash
rm -rf tests/Browser/Videos
./vendor/bin/pest tests/Browser/BookingTest.php tests/Browser/CheckoutTest.php --record-videos --record-videos-fast --record-videos-only=tests/Browser/BookingTest.php,tests/Browser/CheckoutTest.php
git rev-parse HEAD | cut -c1-7
```

- `--record-videos-only` takes comma-separated paths relative to the project root and controls recording only. Positional file arguments tell Pest which tests to execute. Without them, Pest still executes its configured suite and only records the selected files.
- Prefer exact scenario selection when only part of a file proves the diff. Save a JSON array such as `[{"file":"tests/Browser/BookingTest.php","test":"it confirms an accepted booking"}]` and run `php vendor/diff-stage/recorder/bin/diff-stage-record selection.json --record-videos-fast` in the project's existing browser CI environment, including Docker. Use complete Pest names with `it` and describe groups. Names are literal; datasets run all variants. Missing files or unmatched names fail before recording. A whole-file entry uses `"test": null` and runs all its tests.
- Run the project's required regression checks separately without recording. Passing a wider suite does not make every test reviewer evidence.
- Each video's flow key is its filename without `.webm`, for example `bookingtest-it-confirms-an-accepted-booking`. Copy it from the file. Don't guess it from the test name.
- If a selected test fails, fix it or report it. Never present a failed run, or a recording from an older commit, as evidence.
- Watch each video. If you can't play video, run `vendor/bin/diff-stage-compress in.webm out.mp4` and inspect frames with `ffmpeg`. Check that the change is visible, the final state is readable, and no secret or personal data appears. A passing assertion doesn't prove the video is useful. If you couldn't inspect a video, say so.
- Re-record after any commit that changes the recorded behaviour.

## 4. Write the PR description

Add or update this section and keep the rest of the description:

```markdown
## Browser evidence

Browser videos: tests/Browser/BookingTest.php::it confirms an accepted booking
Browser videos: tests/Browser/CheckoutTest.php::it shows why a card was declined

Browser review:
1. `bookingtest-it-confirms-an-accepted-booking`: `BookingController::accept` now confirms straight away. Watch the badge change to Confirmed after Accept.
2. `checkouttest-it-shows-why-a-card-was-declined`: New decline message from `CardErrors`. Check the text under the card field.

Recorded locally at `abc1234`: 2 passed, both videos watched.

Not shown: the confirmation email has no browser surface. `tests/Feature/BookingAcceptedMailTest.php` covers it.
```

- `Browser videos:` starts a line. Use one `file::complete Pest name` scenario per line, or comma-separated file paths to record whole files. Do not combine whole-file and scenario selection for the same file. The workflow must pass `select.outputs.selection` to `diff-stage-record`; the older `tests` output contains only paths and loses scenario selection. The selector returns only matching paths listed here, deduplicated. It never adds changed browser test files. Include changed and unchanged files only when their journeys prove this diff. Use `select@v0.2.0` or later; `v0.1.0` adds changed files automatically.
- `Browser review:` adds notes, never execution or recording filters. It lists videos in the order to watch them, one per line: `` N. `flow-key`: reason ``. Each reason says which change the video proves and where to look, in under 1000 characters. Diff Stage sends the reason and order with the upload and leads the PR comment with them. It skips items whose flow key wasn't recorded and logs a warning.
- Put omitted journeys and anything you couldn't show under "Not shown", with the reason or separate test coverage. Don't describe evidence you didn't produce. When selection is empty, omit the `Browser review:` list too.

## 5. Check CI evidence matches the head

Editing the description re-runs the workflow when it listens for `edited`. With no selection, confirm CI skipped recording and publication. An older comment may remain; don't describe it as evidence for the current selection.

After a selected recording run finishes, the Diff Stage comment's heading names the commit: `Browser test videos for abc1234`. Confirm it matches `git rev-parse HEAD | cut -c1-7` and that each reviewed video appears under "What to check" and in the player's "Review first" group. If the recording failed, the comment is missing, or it names an older commit, say so in your handoff. Don't describe the evidence as current until it is.
