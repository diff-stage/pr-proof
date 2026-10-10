## Diff Stage recorder

- This app posts browser test videos on pull requests with Diff Stage.
- For a one-off local demo, activate `diff-stage-demo`. It records a throwaway Pest browser test, keeps the video and removes the temporary test.
- When a change affects what users see or do in the browser, activate the `diff-stage-evidence` skill before pushing, and name the tests that prove the change with `vendor/bin/diff-stage-show`.
- Activate the `pest-browser-testing` skill whenever you write, review or fix a Pest browser test, including flaky and CI-only failures.
- Never write Diff Stage selections or notes in commit messages or the pull request description.
