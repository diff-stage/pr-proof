"""Exercise the actual publisher against an HTTP server and command boundaries."""
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]


def form_field(body, name):
    match = re.search(rb'name="' + name.encode() + rb'"\r\n\r\n(.*?)\r\n--', body, re.S)
    return match and match.group(1).decode()


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images, self.links, self.text = [], [], []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            raise AssertionError('Comment text became an HTML element')
        if tag == 'img':
            self.images.append(dict(attrs))
        if tag == 'a':
            self.links.append(dict(attrs))

    def handle_data(self, data):
        self.text.append(data)


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.requests = []
        self.fail_upload = 0
        self.identity_requests = []
        self.credentials = []
        self.identity_status = 200
        self.identity_value = 'github-identity'
        self.upload_status = 200
        self.poster_public = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.identity_requests.append((self.path, self.headers['Authorization']))
                self.send_response(owner.identity_status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'value': owner.identity_value}).encode())

            def do_POST(self):
                owner.credentials.append(self.headers['Authorization'])
                body = self.rfile.read(int(self.headers['Content-Length']))
                owner.requests.append((self.path, body, self.headers['Content-Type']))
                if owner.upload_status != 200:
                    self.send_response(owner.upload_status)
                    self.end_headers()
                    self.wfile.write(b'{"message":"Connect this repository to an active Diff Stage GitHub App installation."}')
                    return
                uploads = sum(path.endswith('/videos') for path, *_ in owner.requests)
                if self.path.endswith('/videos') and uploads == owner.fail_upload:
                    self.send_response(500)
                    self.end_headers()
                    return
                response = {'id': 'run1', 'url': 'http://watch/run1', 'poster_url': 'http://poster'}
                if owner.poster_public is not None:
                    response['poster_public'] = owner.poster_public
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            def log_message(self, *args):
                pass

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        for name in ('checkout', 'booking'):
            (self.path / f'{name}.webm').write_bytes(b'video')
        self.stub('ffmpeg', 'touch "${@: -1}"')
        (self.path / 'comments.json').write_text('[]')
        self.stub('gh', '''echo "$*" >> "$GH_LOG"
if [[ " $* " == *" --paginate "* ]]; then
  jq -r "${@: -1}" "$COMMENTS_FILE"
fi
for arg in "$@"; do
  if [[ "$arg" == body=@* ]]; then
    cp "${arg#body=@}" "$COMMENT_FILE"
  fi
done
if [[ "${1:-}" == pr ]]; then
  cp "${@: -1}" "$COMMENT_FILE"
fi''')
        self.stub('compress', '''cp "$1" "$2"
printf '{"steps":[{"at":0.5,"text":"Clicked checkout"}],"problems":[]}' > "${2}.json"''')
        self.env = dict(os.environ, PATH=f'{self.path}:{os.environ["PATH"]}', MODE='pull_request',
                        PR_NUMBER='42', HEAD_SHA='a' * 40, HEAD_REF='feature',
                        EVENT_NAME='push', DEFAULT_BRANCH='main', REF_NAME='main',
                        RUN_NUMBER='23', RECORDING_ID='100:1', RECORDING_SHA='b' * 40, VIDEOS=str(self.path),
                        COMPRESS=str(self.path / 'compress'), DIFF_STAGE_TOKEN='test',
                        DIFF_STAGE_URL=f'http://127.0.0.1:{self.server.server_port}',
                        GITHUB_REPOSITORY='owner/repo', GH_LOG=str(self.path / 'gh.log'),
                        COMMENT_FILE=str(self.path / 'comment.md'), COMMENTS_FILE=str(self.path / 'comments.json'))

    def stub(self, name, body):
        file = self.path / name
        file.write_text('#!/usr/bin/env bash\nset -euo pipefail\n' + body + '\n')
        file.chmod(0o755)

    def run_publish(self, **env):
        return subprocess.run(['bash', str(ROOT / 'publish/publish.sh')], env=self.env | env,
                              capture_output=True, text=True)

    def uploads(self):
        return [body for path, body, _ in self.requests if path.endswith('/videos')]

    def comment(self):
        parser = Links()
        parser.feed((self.path / 'comment.md').read_text())
        return parser

    def identity_env(self):
        return dict(DIFF_STAGE_TOKEN='',
                    ACTIONS_ID_TOKEN_REQUEST_URL=f'http://127.0.0.1:{self.server.server_port}/identity?job=123',
                    ACTIONS_ID_TOKEN_REQUEST_TOKEN='request-token')

    def test_app_identity_uploads_without_a_project_secret(self):
        result = self.run_publish(**self.identity_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.credentials, ['Bearer github-identity'] * 4)
        self.assertEqual(len(self.identity_requests), 4)
        for url, authorization in self.identity_requests:
            self.assertEqual(parse_qs(urlparse(url).query), {'job': ['123'], 'audience': ['diff-stage']})
            self.assertEqual(authorization, 'Bearer request-token')
        self.assertNotIn('github-identity', result.stdout)
        self.assertIn('::add-mask::github-identity', result.stderr)
        self.assertIn('pr comment 42', (self.path / 'gh.log').read_text())

    def test_baseline_also_uses_app_identity(self):
        result = self.run_publish(MODE='baseline', **self.identity_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.credentials, ['Bearer github-identity'] * 4)
        self.assertFalse((self.path / 'gh.log').exists())

    def test_explicit_project_token_takes_precedence(self):
        result = self.run_publish(**(self.identity_env() | {'DIFF_STAGE_TOKEN': 'project-token'}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.identity_requests, [])
        self.assertEqual(self.credentials, ['Bearer project-token'] * 4)

    def test_service_setup_errors_are_visible_and_stop_publication(self):
        self.upload_status = 403
        result = self.run_publish(**self.identity_env())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Connect this repository', result.stderr)
        self.assertEqual(len(self.requests), 1)
        self.assertFalse((self.path / 'gh.log').exists())

    def test_missing_identity_permission_fails_before_upload(self):
        result = self.run_publish(DIFF_STAGE_TOKEN='', ACTIONS_ID_TOKEN_REQUEST_URL='', ACTIONS_ID_TOKEN_REQUEST_TOKEN='')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('id-token: write', result.stderr)
        self.assertEqual(self.requests, [])

    def test_invalid_identity_response_fails_before_upload(self):
        for status, value in [(403, 'denied'), (200, None), (200, '')]:
            self.identity_status, self.identity_value = status, value
            result = self.run_publish(**self.identity_env())
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Unable to obtain GitHub Actions identity', result.stderr)
        self.assertEqual(self.requests, [])
        self.assertFalse((self.path / 'gh.log').exists())

    def test_pr_uploads_telemetry_then_completes_and_comments(self):
        result = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.requests[0][1]), dict(kind='pull_request', pull_request=42, sha='a'*40, branch='feature', recording_id='100:1'))
        self.assertEqual([path for path, *_ in self.requests], ['/api/runs', '/api/runs/run1/videos', '/api/runs/run1/videos', '/api/runs/run1/complete'])
        for (_, body, _), key in zip(self.requests[1:3], ('booking', 'checkout')):
            self.assertIn(f'name="flow_key"\r\n\r\n{key}'.encode(), body)
            self.assertIn(b'name="telemetry"; filename=', body)
            self.assertIn(b'"at":0.5', body)
            self.assertNotIn(b'review_', body)
        self.assertEqual(json.loads(self.requests[-1][1]), {'expected_videos': 2})
        self.assertIn('pr comment 42', (self.path / 'gh.log').read_text())

    def test_updates_the_existing_comment_under_either_marker(self):
        for marker in ('<!-- diff-stage -->', '<!-- pr-proof -->'):
            with self.subTest(marker=marker):
                (self.path / 'comments.json').write_text(json.dumps([
                    {'id': 7, 'body': f'{marker}\nold videos'},
                    {'id': 8, 'body': 'Looks good'},
                ]))
                (self.path / 'gh.log').unlink(missing_ok=True)
                result = self.run_publish()
                self.assertEqual(result.returncode, 0, result.stderr)
                log = (self.path / 'gh.log').read_text()
                self.assertIn('api -X PATCH repos/owner/repo/issues/comments/7', log)
                self.assertNotIn('pr comment', log)

    def test_comment_limits_previews_and_preserves_titles_as_text(self):
        titles = {
            f'{name}.webm': f'{name} with dataset "mobile" & <script> [example] | \'quoted\''
            for name in ('booking', 'checkout', 'login', 'settings', 'signup')
        }
        for name in ('login', 'settings', 'signup'):
            (self.path / f'{name}.webm').write_bytes(b'video')
        (self.path / 'titles.json').write_text(json.dumps(titles))
        result = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        body = (self.path / 'comment.md').read_text()
        self.assertTrue(body.startswith('<!-- diff-stage -->'))
        self.assertIn('Watch all 5 on Diff Stage', body)
        self.assertIn('<summary>All browser tests (5)</summary>', body)
        comment = self.comment()
        self.assertEqual(len(comment.images), 3)
        self.assertEqual(len(comment.links), 8)
        for image, title in zip(comment.images, titles.values()):
            self.assertEqual(image, {'src': 'http://poster', 'height': '120', 'alt': title})
        for title in titles.values():
            self.assertIn(title, comment.text)
        self.assertNotIn('What to check', body)

    def test_review_notes_order_uploads_and_explain_each_video(self):
        reason = '@/etc/hostname shows the <script> & "decline" message'
        body = '\r\n'.join([
            'Some summary.',
            'Browser review:',
            '',
            f'1. `checkout` — {reason}',
            '2) `missing-flow`: Not recorded anywhere.',
            '3. `checkout` - Duplicate is ignored.',
            '4. `booking` – ' + 'x' * 1200,
            'Recorded locally at abc1234.',
            '5. `ignored` — After the list ended.',
        ])
        result = self.run_publish(PR_BODY=body)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('::warning::Browser review lists missing-flow, but no video has that flow key.', result.stdout)
        checkout, booking = self.uploads()
        self.assertEqual(form_field(checkout, 'flow_key'), 'checkout')
        self.assertEqual(form_field(checkout, 'review_reason'), reason)
        self.assertEqual(form_field(checkout, 'review_order'), '1')
        self.assertEqual(form_field(booking, 'review_reason'), 'x' * 1000)
        self.assertEqual(form_field(booking, 'review_order'), '3')
        comment = self.comment()
        text = ''.join(comment.text)
        self.assertIn('What to check', text)
        self.assertIn('checkout: ' + reason, text)
        self.assertEqual([image['alt'] for image in comment.images], ['checkout', 'booking'])
        self.assertNotIn('ignored', text)

    def test_review_examples_in_code_blocks_are_ignored(self):
        example = ['Browser review:', '1. `checkout`: Example only.']
        fenced = {
            'backticks': ['```markdown', *example, '```'],
            'nested fence': ['````markdown', '```markdown', *example, '```', '````'],
            'tilde fence': ['~~~', '```', *example, '~~~~'],
            'closer with text': ['```', '``` not a closer', *example, '```'],
        }
        for name, lines in fenced.items():
            with self.subTest(name):
                self.requests.clear()
                body = '\n'.join(['Format:', *lines, '', 'Browser review:', '1. `booking`: The real reason.'])
                result = self.run_publish(PR_BODY=body)
                self.assertEqual(result.returncode, 0, result.stderr)
                booking, checkout = self.uploads()
                self.assertEqual(form_field(booking, 'review_reason'), 'The real reason.')
                self.assertNotIn(b'review_', checkout)

    def test_review_notes_only_change_pull_request_runs(self):
        result = self.run_publish(MODE='baseline', PR_BODY='Browser review:\n1. `booking` — Reason.')
        self.assertEqual(result.returncode, 0, result.stderr)
        for body in self.uploads():
            self.assertNotIn(b'review_', body)

    def test_private_posters_are_linked_but_not_embedded(self):
        self.poster_public = False
        result = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        comment = self.comment()
        self.assertEqual(comment.images, [])
        self.assertNotIn('http://poster', (self.path / 'comment.md').read_text())
        self.assertEqual([link['href'] for link in comment.links], ['http://watch/run1'] * 2)

    def test_recordings_from_another_commit_are_never_published(self):
        (self.path / 'sha.txt').write_text('c' * 40 + '\n')
        result = self.run_publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('recorded at ' + 'c' * 40, result.stderr)
        self.assertEqual(self.requests, [])

        (self.path / 'sha.txt').write_text('a' * 40 + '\n')
        result = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.uploads()), 2)

    def test_baseline_metadata_and_no_comment(self):
        result = self.run_publish(MODE='baseline')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.requests[0][1]), dict(kind='baseline', pull_request=None, sha='b'*40, branch='main', source_order=23, recording_id='100:1'))
        self.assertFalse((self.path / 'gh.log').exists())

    def test_unapproved_events_and_branches_make_no_requests(self):
        for env in ({'EVENT_NAME': 'pull_request'}, {'REF_NAME': 'feature'}, {'EVENT_NAME': 'pull_request_target'}):
            result = self.run_publish(MODE='baseline', **env)
            self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.requests, [])

    def test_failed_upload_never_completes_or_comments(self):
        self.fail_upload = 2
        result = self.run_publish(MODE='baseline')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(any(path.endswith('/complete') for path, *_ in self.requests))
        self.assertFalse((self.path / 'gh.log').exists())

    def test_failed_compression_never_completes(self):
        self.stub('compress', 'exit 1')
        self.assertNotEqual(self.run_publish().returncode, 0)
        self.assertEqual(len(self.requests), 1)


if __name__ == '__main__':
    unittest.main()
