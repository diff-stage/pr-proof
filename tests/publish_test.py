"""Exercise the actual publisher against an HTTP server and command boundaries."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = Path(__file__).resolve().parents[1]


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.requests = []
        self.fail_upload = 0
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                owner.requests.append((self.path, body, self.headers['Content-Type']))
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
        self.stub('gh', 'echo "$*" >> "$GH_LOG"')
        self.stub('compress', '''cp "$1" "$2"
printf '{"steps":[{"at":0.5,"text":"Clicked checkout"}],"problems":[]}' > "${2}.json"''')
        self.env = dict(os.environ, PATH=f'{self.path}:{os.environ["PATH"]}', MODE='pull_request',
                        PR_NUMBER='42', HEAD_SHA='a' * 40, HEAD_REF='feature',
                        EVENT_NAME='push', DEFAULT_BRANCH='main', REF_NAME='main',
                        RUN_NUMBER='23', RECORDING_SHA='b' * 40, VIDEOS=str(self.path),
                        COMPRESS=str(self.path / 'compress'), PR_PROOF_TOKEN='test',
                        PR_PROOF_URL=f'http://127.0.0.1:{self.server.server_port}',
                        GITHUB_REPOSITORY='owner/repo', GH_LOG=str(self.path / 'gh.log'))

    def stub(self, name, body):
        file = self.path / name
        file.write_text('#!/usr/bin/env bash\nset -euo pipefail\n' + body + '\n')
        file.chmod(0o755)

    def run_publish(self, **env):
        return subprocess.run(['bash', str(ROOT / 'publish/publish.sh')], env=self.env | env,
                              capture_output=True, text=True)

    def test_pr_uploads_telemetry_then_completes_and_comments(self):
        result = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.requests[0][1]), dict(kind='pull_request', pull_request=42, sha='a'*40, branch='feature'))
        self.assertEqual([path for path, *_ in self.requests], ['/api/runs', '/api/runs/run1/videos', '/api/runs/run1/videos', '/api/runs/run1/complete'])
        for (_, body, _), key in zip(self.requests[1:3], ('booking', 'checkout')):
            self.assertIn(f'name="flow_key"\r\n\r\n{key}'.encode(), body)
            self.assertIn(b'name="telemetry"; filename=', body)
            self.assertIn(b'"at":0.5', body)
        self.assertEqual(json.loads(self.requests[-1][1]), {'expected_videos': 2})
        self.assertIn('pr comment 42', (self.path / 'gh.log').read_text())

    def test_baseline_metadata_and_no_comment(self):
        result = self.run_publish(MODE='baseline')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.requests[0][1]), dict(kind='baseline', pull_request=None, sha='b'*40, branch='main', source_order=23))
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
