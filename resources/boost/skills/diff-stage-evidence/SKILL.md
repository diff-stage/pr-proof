---
name: diff-stage-evidence
description: Show reviewers videos of a pull request's browser-visible change with Diff Stage. Use when a change affects what users see or do in the browser, before pushing or opening the pull request.
---

# Show reviewers the change

Diff Stage records the browser tests you name and posts the videos on the pull request, next to the same flow on the default branch. You choose the tests and say what to watch. Commits and the PR description stay for people.

## 1. Choose the journeys that prove the change

Read the diff. For each browser-visible change, pick the smallest existing Pest browser test that shows it, including unchanged tests that reach the changed behavior. When none does, add or adjust one: one journey per test, disposable data, a readiness assertion for asynchronous behavior and a visible final outcome. The recording shows typed and rendered data, so keep secrets and personal data out of fixtures.

Name only tests that prove the diff. If nothing has a useful browser demonstration, name nothing and say which checks cover the change instead.

## 2. Name each test before pushing

```bash
vendor/bin/diff-stage-show "tests/Browser/BookingTest.php::it confirms an accepted booking" \
    --why "Accepting now confirms straight away. Watch the badge change to Confirmed."
```

- Use the complete Pest name, including `it` and describe groups. Every dataset variant is recorded.
- Pass only the file path to record every test in that file.
- Write `--why` for a reviewer about to press play: what changed and where to look, in one or two sentences.

The command checks that Pest finds the test, then saves it on Diff Stage for this branch. Run it again to change a note. Run it with no arguments to list everything the branch shows, or with `--clear` to start over.

The first run on a computer prints a sign-in link and code, opens the user's browser and waits. Tell the user to approve it there. If your command times out first, run it again once they have approved.

## 3. Watch it before pushing

Where the project's browser tests run locally, record each named test and watch it through its final state:

```bash
vendor/bin/pest tests/Browser/BookingTest.php --filter "it confirms an accepted booking" --record-videos
```

Videos land in `tests/Browser/Videos`. Check that the change is readable and that nothing private is on screen. Fix the test and record again if not.

## 4. Push

Push the branch and open the pull request. CI records the named tests at the pushed commit, and Diff Stage comments on the pull request with each video and its note. Tests named after the latest push are recorded on the next push.

The task is done when the Diff Stage comment names the pull request's head commit and lists every test you named.
