"""Drive diff-stage-show against a Diff Stage double, real git repositories and a Pest process double."""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
BOOKING = 'tests/Browser/BookingTest.php::it confirms an accepted booking'


class ShowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.requests = []
        self.approve_after = 1
        self.tokens = {'pending-token': 'pending'}
        self.selection = []
        self.missing_repository = False
        owner = self

        class Service(BaseHTTPRequestHandler):
            def respond(self, status, body=None):
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                if body is not None:
                    self.wfile.write(json.dumps(body).encode())

            def handle_request(self):
                url = urlparse(self.path)
                length = int(self.headers.get('Content-Length') or 0)
                data = json.loads(self.rfile.read(length)) if length else {k: v[0] for k, v in parse_qs(url.query).items()}
                token = (self.headers.get('Authorization') or '').removeprefix('Bearer ')
                owner.requests.append((self.command, url.path, token, data))
                if (self.command, url.path) == ('POST', '/api/cli/sessions'):
                    return self.respond(201, {'token': 'pending-token', 'code': 'BCDF-GHJK', 'url': 'https://diffstage.test/cli/BCDF-GHJK', 'interval': 0})
                if (self.command, url.path) == ('GET', '/api/cli/session'):
                    if owner.tokens.get(token) != 'pending':
                        return self.respond(200 if owner.tokens.get(token) == 'approved' else 401, {'approved': True, 'user': {'name': 'Kim Ward'}})
                    owner.approve_after -= 1
                    if owner.approve_after >= 0:
                        return self.respond(202, {'approved': False})
                    owner.tokens[token] = 'approved'
                    return self.respond(200, {'approved': True, 'user': {'name': 'Kim Ward'}})
                if owner.tokens.get(token) != 'approved':
                    return self.respond(401, {'message': 'Unauthenticated.'})
                if (self.command, url.path) == ('DELETE', '/api/cli/session'):
                    owner.tokens.pop(token)
                    return self.respond(204)
                if owner.missing_repository:
                    return self.respond(404, {'message': "example/shop isn't connected to a Diff Stage team you're in."})
                if self.command == 'POST':
                    entry = next((e for e in owner.selection if (e['file'], e['test']) == (data['file'], data['test'])), None)
                    if entry is None:
                        entry = {'file': data['file'], 'test': data['test'], 'note': None}
                        owner.selection.append(entry)
                    entry['note'] = data['note'] or entry['note']
                if self.command == 'DELETE':
                    owner.selection = []
                self.respond(200, {'repository': data['repository'], 'branch': data['branch'], 'selection': owner.selection})

            do_GET = do_POST = do_DELETE = handle_request

            def log_message(self, *args):
                pass

        server = HTTPServer(('127.0.0.1', 0), Service)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)

        (root / 'gitconfig').write_text('[user]\n\tname = Agent\n\temail = agent@example.com\n[init]\n\tdefaultBranch = main\n')
        self.browser = root / 'browser'
        self.browser.write_text(f'#!/usr/bin/env bash\necho "$1" >> {root}/opened\n')
        self.browser.chmod(0o755)
        self.opened = root / 'opened'
        self.credentials = root / 'config/diff-stage/credentials.json'
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=str(root / 'gitconfig'), GIT_CONFIG_NOSYSTEM='1',
                        DIFF_STAGE_URL=f'http://127.0.0.1:{server.server_port}', XDG_CONFIG_HOME=str(root / 'config'),
                        BROWSER=str(self.browser))
        self.path = root / 'app'
        subprocess.run(['git', 'init', '-q', '--bare', str(root / 'origin.git')], check=True, env=self.env)
        subprocess.run(['git', 'clone', '-q', str(root / 'origin.git'), str(self.path)], check=True, env=self.env, capture_output=True)
        (self.path / 'vendor/bin').mkdir(parents=True)
        (self.path / 'tests/Browser').mkdir(parents=True)
        (self.path / 'tests/Browser/BookingTest.php').write_text('<?php')
        (self.path / 'vendor/bin/pest').write_text('''<?php
$filter = in_array('--filter', $argv) ? $argv[array_search('--filter', $argv) + 1] : null;
$names = ['it confirms an accepted booking with data set "desktop"', 'it confirms an accepted booking with data set "mobile"', 'it cancels a booking'];
$selected = array_filter($names, fn ($name) => $filter === null || preg_match($filter, 'Tests/Browser/BookingTest.php::'.$name));
$file = $argv[array_search('--list-tests-xml', $argv) + 1];
file_put_contents($file, '<testSuite><tests>'.str_repeat('<testMethod name="example"/>', count($selected)).'</tests></testSuite>');
''')
        (self.path / '.gitignore').write_text('vendor/\n')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'Start')
        self.git('push', '-q', 'origin', 'main')
        self.git('remote', 'set-head', 'origin', 'main')
        self.git('checkout', '-q', '-b', 'feature')
        (self.path / 'booking.txt').write_text('confirmed')
        self.git('add', 'booking.txt')
        self.git('commit', '-q', '-m', 'Confirm accepted bookings')
        self.git('remote', 'set-url', 'origin', 'git@github.com:example/shop.git')

    def git(self, *args):
        return subprocess.run(['git', *args], cwd=self.path, env=self.env, check=True, capture_output=True, text=True).stdout

    def show(self, *args):
        return subprocess.run(['php', str(ROOT / 'bin/diff-stage-show'), *args], cwd=self.path, env=self.env,
                              capture_output=True, text=True)

    def sign_in(self):
        self.tokens['saved-token'] = 'approved'
        self.credentials.parent.mkdir(parents=True)
        self.credentials.write_text(json.dumps({self.env['DIFF_STAGE_URL']: {'token': 'saved-token'}}))

    def selection_requests(self):
        return [(method, token, data) for method, path, token, data in self.requests if path == '/api/selection']

    def test_signs_in_through_the_browser_then_shows_the_test_without_touching_commits(self):
        head = self.git('rev-parse', 'HEAD')
        (self.path / 'draft.txt').write_text('not ready')
        self.git('add', 'draft.txt')

        result = self.show(BOOKING, '--why', 'Watch the badge change to Confirmed.')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.opened.read_text(), 'https://diffstage.test/cli/BCDF-GHJK\n')
        self.assertIn('BCDF-GHJK  https://diffstage.test/cli/BCDF-GHJK', result.stdout)
        self.assertIn('✓ Signed in as Kim Ward', result.stdout)
        self.assertEqual(json.loads(self.credentials.read_text()), {self.env['DIFF_STAGE_URL']: {'token': 'pending-token'}})
        self.assertEqual(stat.S_IMODE(self.credentials.stat().st_mode), 0o600)
        self.assertEqual(self.selection_requests(), [('POST', 'pending-token', {
            'repository': 'example/shop', 'branch': 'feature',
            'file': 'tests/Browser/BookingTest.php', 'test': 'it confirms an accepted booking', 'note': 'Watch the badge change to Confirmed.'})])
        self.assertIn('✓ BookingTest › it confirms an accepted booking\n  2 videos · shown on feature\n  Watch the badge change to Confirmed.', result.stdout)
        self.assertIn('Diff Stage records it when you push.', result.stdout)
        self.assertEqual(self.git('rev-parse', 'HEAD'), head)
        self.assertEqual(self.git('log', '-1', '--format=%B').strip(), 'Confirm accepted bookings')
        self.assertEqual(self.git('diff', '--cached', '--name-only'), 'draft.txt\n')

    def test_resumes_an_unfinished_sign_in_instead_of_starting_another(self):
        self.credentials.parent.mkdir(parents=True)
        self.credentials.write_text(json.dumps({self.env['DIFF_STAGE_URL']: {
            'token': 'pending-token', 'pending': True, 'code': 'BCDF-GHJK', 'url': 'https://diffstage.test/cli/BCDF-GHJK', 'interval': 0}}))

        result = self.show()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(('POST', '/api/cli/sessions'), [(method, path) for method, path, *_ in self.requests])
        self.assertIn('✓ Signed in as Kim Ward', result.stdout)
        self.assertIn("feature doesn't show reviewers any browser tests yet.", result.stdout)

    def test_starts_a_new_sign_in_after_a_code_expires_or_access_is_revoked(self):
        self.credentials.parent.mkdir(parents=True)
        self.credentials.write_text(json.dumps({self.env['DIFF_STAGE_URL']: {'token': 'revoked-token'}}))

        result = self.show()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([(method, token) for method, token, _ in self.selection_requests()], [('GET', 'revoked-token'), ('GET', 'pending-token')])
        self.assertIn('✓ Signed in as Kim Ward', result.stdout)

    def test_lists_notes_in_order_and_keeps_a_note_when_shown_again_without_one(self):
        self.sign_in()
        self.assertEqual(self.show(BOOKING, '--why=Watch the badge.').returncode, 0)
        self.assertEqual(self.show('tests/Browser/BookingTest.php::it cancels a booking').returncode, 0)
        again = self.show(BOOKING)
        self.assertIn('Watch the badge.', again.stdout)

        result = self.show()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'feature shows reviewers 2 browser tests:\n\n'
                         '  1. BookingTest › it confirms an accepted booking\n     Watch the badge.\n'
                         '  2. BookingTest › it cancels a booking\n     No note yet. Add one with --why so reviewers know what to watch.\n')
        self.assertFalse(self.opened.exists())

    def test_clears_the_branch(self):
        self.sign_in()
        self.show(BOOKING)

        result = self.show('--clear')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '✓ feature no longer shows reviewers any browser tests.\n')
        self.assertEqual(self.selection, [])

    def test_checks_the_test_with_pest_before_contacting_diff_stage(self):
        result = self.show('tests/Browser/BookingTest.php::it confirms a booking')

        self.assertEqual(result.returncode, 1)
        self.assertIn('No tests match tests/Browser/BookingTest.php::it confirms a booking', result.stderr)
        self.assertEqual(self.requests, [])

    def test_refuses_the_default_branch(self):
        self.git('checkout', '-q', 'main')

        result = self.show(BOOKING)

        self.assertEqual(result.returncode, 1)
        self.assertIn('Switch to your pull request branch first.', result.stderr)
        self.assertEqual(self.requests, [])

    def test_explains_a_repository_diff_stage_does_not_know(self):
        self.sign_in()
        self.missing_repository = True

        result = self.show(BOOKING)

        self.assertEqual(result.returncode, 1)
        self.assertIn("example/shop isn't connected to a Diff Stage team you're in.", result.stderr)

    def test_says_when_the_latest_commit_needs_another_push(self):
        self.sign_in()
        self.git('remote', 'set-url', 'origin', str(Path(self.temp.name) / 'origin.git'))
        self.git('push', '-q', '-u', 'origin', 'feature')
        self.git('remote', 'set-url', 'origin', 'https://github.com/example/shop.git')

        result = self.show(BOOKING)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Your latest commit is already pushed. Push again, or re-run Browser evidence, to record it.', result.stdout)

    def test_logout_revokes_this_computer(self):
        self.sign_in()

        result = self.show('logout')

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(('DELETE', '/api/cli/session', 'saved-token', {}), self.requests)
        self.assertEqual(json.loads(self.credentials.read_text()), {})


if __name__ == '__main__':
    unittest.main()
