"""Exercise the selection CLI boundary with a Pest process double."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class SelectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        (self.path / 'vendor/bin').mkdir(parents=True)
        (self.path / 'tests/Browser').mkdir(parents=True)
        (self.path / 'tests/Browser/WizardTest.php').write_text('<?php')
        (self.path / 'vendor/bin/pest').write_text('''<?php
$filter = in_array('--filter', $argv) ? $argv[array_search('--filter', $argv) + 1] : null;
$names = ['it saves a [draft], with $(touch injected)', 'it finishes the wizard', 'it saves a draft'];
$selected = array_values(array_filter($names, fn ($name) => $filter === null || preg_match($filter, 'Tests/Browser/WizardTest.php::'.$name)));
if (in_array('--list-tests-xml', $argv)) {
    $file = $argv[array_search('--list-tests-xml', $argv) + 1];
    file_put_contents($file, '<testSuite><tests>'.str_repeat('<testMethod name="example"/>', count($selected)).'</tests></testSuite>');
} else {
    file_put_contents('executed.json', json_encode($selected));
    exit((int) getenv('PEST_EXIT_CODE'));
}
''')

    def record(self, names, exit_code='0'):
        selection = [{'file': 'tests/Browser/WizardTest.php', 'test': name} for name in names]
        (self.path / 'selection.json').write_text(json.dumps(selection))
        return subprocess.run(['php', str(ROOT / 'bin/diff-stage-record'), 'selection.json'],
                              cwd=self.path, env=dict(os.environ, PEST_EXIT_CODE=exit_code),
                              capture_output=True, text=True)

    def test_runs_only_exact_requested_names_without_shell_or_regex_expansion(self):
        names = ['it saves a [draft], with $(touch injected)', 'it finishes the wizard']
        result = self.record(names)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.path / 'executed.json').read_text()), names)
        self.assertFalse((self.path / 'injected').exists())

    def test_valid_selection_does_not_hide_an_unmatched_name(self):
        result = self.record(['it finishes the wizard', 'it does not exist'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No tests match', result.stderr)
        self.assertFalse((self.path / 'executed.json').exists())

    def test_whole_file_still_runs_every_test(self):
        result = self.record([None])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads((self.path / 'executed.json').read_text())), 3)

    def test_mixed_file_and_scenario_selection_is_rejected(self):
        result = self.record([None, 'it finishes the wizard'])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('either the whole file', result.stderr)
        self.assertFalse((self.path / 'executed.json').exists())

    def test_failed_tests_fail_the_recording_command(self):
        result = self.record(['it finishes the wizard'], '7')
        self.assertEqual(result.returncode, 7)

if __name__ == '__main__':
    unittest.main()
