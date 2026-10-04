"""Exercise the actual publisher against an HTTP server and command boundaries."""
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]


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
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'id': 'run1', 'url': 'http://watch/run1', 'poster_url': 'http://poster'}).encode())

            def log_message(self, *args):
                pass

        self.server = HTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        for name in ('checkout', 'booking'):
            (self.path / f'{name}.webm').write_bytes(b'video')
        self.stub('ffmpeg', 'touch "${@: -1}"')
        self.stub('gh', '''echo "$*" >> "$GH_LOG"
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
                        COMPRESS=str(self.path / 'compress'), PR_PROOF_TOKEN='test',
                        PR_PROOF_URL=f'http://127.0.0.1:{self.server.server_port}',
                        GITHUB_REPOSITORY='owner/repo', GH_LOG=str(self.path / 'gh.log'),
                        COMMENT_FILE=str(self.path / 'comment.md'))

    def stub(self, name, body):
        file = self.path / name
        file.write_text('#!/usr/bin/env bash\nset -euo pipefail\n' + body + '\n')
        file.chmod(0o755)

    def run_publish(self, **env):
        return subprocess.run(['bash', str(ROOT / 'publish/publish.sh')], env=self.env | env,
                              capture_output=True, text=True)

    def identity_env(self):
        return dict(PR_PROOF_TOKEN='',
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
        result = self.run_publish(**(self.identity_env() | {'PR_PROOF_TOKEN': 'project-token'}))
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
        result = self.run_publish(PR_PROOF_TOKEN='', ACTIONS_ID_TOKEN_REQUEST_URL='', ACTIONS_ID_TOKEN_REQUEST_TOKEN='')
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
        self.assertEqual(json.loads(self.requests[-1][1]), {'expected_videos': 2})
        self.assertIn('pr comment 42', (self.path / 'gh.log').read_text())

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
        self.assertTrue(body.startswith('<!-- pr-proof -->'))
        self.assertIn('Watch all 5 on pr-proof', body)
        self.assertIn('<summary>All browser tests (5)</summary>', body)
        images, links, text = [], [], []

        class Parser(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == 'img':
                    images.append(dict(attrs))
                if tag == 'a':
                    links.append(dict(attrs))
                self.assert_safe_tag(tag)

            def assert_safe_tag(self, tag):
                if tag == 'script':
                    raise AssertionError('Test title became an HTML element')

            def handle_data(self, data):
                text.append(data)

        Parser().feed(body)
        self.assertEqual(len(images), 3)
        self.assertEqual(len(links), 8)
        for image, title in zip(images, titles.values()):
            self.assertEqual(image, {'src': 'http://poster', 'height': '120', 'alt': title})
        for title in titles.values():
            self.assertIn(title, text)

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
