---
name: diff-stage-demo
description: Record a local feature demo with a throwaway Pest browser test and Diff Stage, keep the video, then remove the temporary test. Use for one-off demos, including recordings to share on a pull request.
---

# Record a local demo

Use the installed recorder to demonstrate one user journey. Keep the recording outside the checkout and remove the test you created. A demo does not need a permanent regression test.

## 1. Prepare the journey

Read `tests/Pest.php` and nearby browser tests. Reuse their database isolation, factories, login helpers and external service fakes. Check the installed recorder and Pest Browser versions with `composer show diff-stage/recorder` and `composer show pestphp/pest-plugin-browser`. Keep the project's working browser setup and build its frontend assets when needed.

Choose one visible outcome and the interactions that reach it. Use disposable fixtures with no secrets or personal data. Disclose simulated boundaries, such as a fake payment provider, when reporting the demo.

Create a fresh artifact directory outside the checkout and capture the starting commit and working-tree status before adding the temporary test:

```bash
demo_dir=$(mktemp -d "${TMPDIR:-/tmp}/diff-stage-demo.XXXXXX")
git rev-parse HEAD > "$demo_dir/sha.txt"
git status --short > "$demo_dir/working-tree.txt"
demo_test=$(mktemp tests/Browser/DiffStageDemoXXXXXXTest.php)
```

Write a single Pest test into `$demo_test`. Keep one `visit()` context, use visible text or existing test IDs, and assert readiness after each action and the final visible result. Assertions wait for state changes; do not add fixed sleeps to make the video readable. Check browser methods against the installed Pest Browser API before using them.

The file must stay in `tests/Browser` so it inherits the project's browser test setup. Create a new file; never overwrite an existing test. Track its exact path for cleanup if a later step fails or is interrupted.

## 2. Record and inspect

Run only the temporary file, using the project's normal test environment:

```bash
vendor/bin/pest "$demo_test" --record-videos="$demo_dir/raw"
```

Require a successful test and a nonempty recording. Failed runs are debugging material, not evidence that the feature works. For each actual WebM produced, convert it with the installed compressor:

```bash
vendor/bin/diff-stage-compress "$demo_dir/raw/actual-recording.webm" "$demo_dir/demo.mp4"
```

Replace the example filename with the file that was produced. The compressor needs FFmpeg and the recorder's Python dependencies. If it fails, keep the raw footage and report the cause.

Watch the whole final video at normal speed. Check that the action and its outcome are readable and that nothing private appears. Compare the MP4 with the raw footage; keep the raw video if compression trims a needed interaction or outcome. Fix the journey and record into a fresh output directory if the footage does not prove the outcome. If playback is unavailable, report that the test passed and the recording exists, with footage review still pending.

Save a short `demo.json` beside the video with the full starting SHA, whether the checkout had uncommitted changes, the journey, actual video filenames, simulated boundaries and what playback confirmed. A dirty checkout is a local working-tree demo; do not describe its video as proof of the committed PR head. Recapture after changing the demonstrated behavior.

## 3. Remove the test and hand off

Remove only the temporary test you created, including after a failed run. Preserve existing tests and unrelated work. Check `git status --short` against the starting status so the demo leaves no test or generated files in the checkout.

Keep the artifacts until handoff. Copy them to a durable location when the user needs to retain them beyond the temporary directory's lifetime. Return the video path, the outcome it shows, the starting SHA and any verification gap.

## Sharing on a pull request

When PR attachment is requested or already authorized, use an available authenticated attachment workflow or approved artifact host. Add the resulting accessible video or playback link to the PR with a short explanation and its commit details. Verify the link or attachment works before claiming it is attached. An absolute local path is not a usable PR attachment. The GitHub CLI cannot attach video bytes by putting a local filename in a PR body.

Local demos do not use `diff-stage-show` selections. Diff Stage's hosted upload endpoints currently require GitHub Actions identity; a saved CLI sign-in cannot publish this local video. If no attachment route is available, hand off the local video and report that PR attachment is pending.

For videos CI can rerun and publish through Diff Stage, use `diff-stage-evidence` and retain the selected tests in the pushed commit.
