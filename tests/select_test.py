"""Run the selector action's Bash step with PR descriptions and changed files."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATTERN = r'^tests/Browser/.+Test\.php$'


class SelectTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        gh = self.path / 'gh'
        gh.write_text('#!/usr/bin/env bash\n'
                      'touch "$GH_LOG"\n'
                      'printf "%s\\n" "$CHANGED_TESTS"\n')
        gh.chmod(0o755)
        action = (ROOT / 'select/action.yml').read_text()
        self.script = textwrap.dedent(action.split('      run: |\n', 1)[1])

    def select(self, body='', pattern=DEFAULT_PATTERN):
        output = self.path / 'output'
        output.write_text('')
        env = dict(os.environ, PATH=f'{self.path}:{os.environ["PATH"]}',
                   PR_BODY=body, PATTERN=pattern, GITHUB_OUTPUT=str(output),
                   PR_NUMBER='42', GITHUB_REPOSITORY='owner/repo',
                   GH_LOG=str(self.path / 'gh.log'),
                   CHANGED_TESTS='tests/Browser/ChangedTest.php')
        result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', self.script],
                                env=env, cwd=self.path, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.path / 'gh.log').exists(), 'Selection queried the PR diff')
        return output.read_text(), result.stdout

    def test_changed_browser_tests_without_requests_select_nothing(self):
        for body in ('', 'Changes tests/Browser/ChangedTest.php',
                     'Browser review:\n1. `changed-flow`: Watch the changed screen.'):
            with self.subTest(body=body):
                output, log = self.select(body)
                self.assertEqual(output, 'tests=\n')
                self.assertIn('skipping recording', log)

    def test_only_explicit_requests_are_selected_including_unchanged_files(self):
        output, log = self.select('Browser videos: tests/Browser/UnchangedTest.php')
        self.assertEqual(output, 'tests=tests/Browser/UnchangedTest.php\n')
        self.assertIn('Recording requested browser tests:', log)
        self.assertNotIn('ChangedTest.php', output)

    def test_changed_tests_are_selected_when_explicitly_requested(self):
        output, _ = self.select('Browser videos: tests/Browser/ChangedTest.php')
        self.assertEqual(output, 'tests=tests/Browser/ChangedTest.php\n')

    def test_case_crlf_separators_nested_paths_and_duplicates(self):
        output, _ = self.select(
            'bRoWsEr ViDeOs: tests/Browser/Nested/CheckoutTest.php, tests/Browser/BookingTest.php\r\n'
            'Browser videos: tests/Browser/BookingTest.php tests/Browser/Nested/CheckoutTest.php\r\n')
        self.assertEqual(output, 'tests=tests/Browser/BookingTest.php,tests/Browser/Nested/CheckoutTest.php\n')

    def test_default_pattern_excludes_other_paths(self):
        output, _ = self.select(
            'Browser videos: tests/Feature/CheckoutTest.php, /tests/Browser/AbsoluteTest.php, '
            'tests/Browser/Helper.php, tests/Browser/ValidTest.php, tests/Browser/ValidTest.php.bak')
        self.assertEqual(output, 'tests=tests/Browser/ValidTest.php\n')

    def test_custom_pattern_is_used_for_explicit_requests(self):
        output, _ = self.select(
            'Browser videos: spec/browser/checkout.spec.php, tests/Browser/ChangedTest.php',
            r'^spec/browser/.+\.spec\.php$')
        self.assertEqual(output, 'tests=spec/browser/checkout.spec.php\n')

    def test_empty_or_nonmatching_requests_select_nothing(self):
        for body in ('Browser videos:', 'Browser videos: , ,',
                     'Browser videos: none', 'Browser videos: tests/Feature/CheckoutTest.php'):
            with self.subTest(body=body):
                output, log = self.select(body)
                self.assertEqual(output, 'tests=\n')
                self.assertIn('skipping recording', log)

    def test_request_must_start_a_line(self):
        output, _ = self.select('Please add Browser videos: tests/Browser/ChangedTest.php')
        self.assertEqual(output, 'tests=\n')


if __name__ == '__main__':
    unittest.main()
