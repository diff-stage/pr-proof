"""Exercise the actual publisher against an HTTP server and command boundaries."""
from html.parser import HTMLParser
import json
import base64
import hashlib
import io
import zipfile
from email.parser import BytesParser
import os
from pathlib import Path
import re
import shutil
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
        self.storage_requests = []
        self.direct_upload_status = 200
        self.direct_metadata = []
        self.compressed_metadata = []
        self.identity_requests = []
        self.credentials = []
        self.identity_status = 200
        self.identity_value = 'github-identity'
        self.upload_status = 200
        self.poster_public = None
        self.public_url = None
        self.complete_status = 200
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                owner.identity_requests.append((self.path, self.headers['Authorization']))
                self.send_response(owner.identity_status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'value': owner.identity_value}).encode())

            def do_PUT(self):
                body = self.rfile.read(int(self.headers['Content-Length']))
                owner.storage_requests.append((self.path, body, dict(self.headers)))
                self.send_response(owner.direct_upload_status)
                self.end_headers()

            def do_POST(self):
                owner.credentials.append(self.headers['Authorization'])
                body = self.rfile.read(int(self.headers['Content-Length']))
                owner.requests.append((self.path, body, self.headers['Content-Type']))
                if self.path.endswith('/complete') and owner.complete_status != 200:
                    self.send_response(owner.complete_status)
                    self.end_headers()
                    self.wfile.write(b'{"message":"Upload count does not match expected_videos."}')
                    return
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
                if self.path.endswith('/video-uploads'):
                    files = json.loads(body)['files']
                    owner.compressed_metadata.append(files)
                    response = {'upload_id': f'upload{uploads + 1}', 'files': {role: {
                        'url': f'http://127.0.0.1:{owner.server.server_port}/storage/upload{uploads + 1}/' + role,
                        'headers': {'Content-Length': [str(file['size'])],
                                    'Content-MD5': [base64.b64encode(bytes.fromhex(file['md5'])).decode()],
                                    'Content-Type': [file['content_type']]}}
                        for role, file in files.items()}}
                if self.path.endswith('/recording-uploads'):
                    owner.direct_metadata = json.loads(body)['videos']
                    response = {'uploads': [{'file': video['file'],
                        'url': f'http://127.0.0.1:{owner.server.server_port}/storage/' + video['file'],
                        'headers': {'Content-Length': [str(video['size'])],
                                    'Content-MD5': [base64.b64encode(bytes.fromhex(video['md5'])).decode()],
                                    'Content-Type': ['application/zip']}} for video in owner.direct_metadata]}
                if self.path.endswith('/recordings'):
                    response['processing'] = True
                    response['videos'] = [{'flow_key': name, 'url': 'http://watch/run1#'+name} for name in ('booking', 'checkout')]
                if owner.poster_public is not None:
                    response['poster_public'] = owner.poster_public
                if owner.public_url:
                    response['url'] = owner.public_url + '/runs/run1'
                    response['poster_url'] = owner.public_url + '/videos/video1/poster'
                    if self.path.endswith('/videos'):
                        response['url'] += '#video1'
                    if self.path.endswith('/recordings'):
                        response['videos'] = [{'flow_key': name, 'url': response['url'] + '#' + name} for name in ('booking', 'checkout')]
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
        self.stub('ffmpeg', 'printf poster > "${@: -1}"')
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
                        COMPRESS=str(self.path / 'compress'), SELECTION='', DIFF_STAGE_TOKEN='test',
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

    def select(self, *entries):
        self.env['SELECTION'] = json.dumps([{'file': file, 'test': test, 'note': note} for file, test, note in entries])

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

    def route_endpoint_to_server(self, endpoint):
        """Keep requested URLs observable while real curl sends HTTP to our fixture."""
        self.env.update(TEST_ENDPOINT=endpoint.rstrip('/'), TEST_SERVER=self.env['DIFF_STAGE_URL'],
                        CURL_URL_LOG=str(self.path / 'curl-urls.json'), REAL_CURL=shutil.which('curl'))
        file = self.path / 'curl'
        file.write_text('''#!/usr/bin/env python3
import json, os, subprocess, sys
args = sys.argv[1:]
urls = [arg for arg in args if arg.startswith(('https://', 'http://'))]
with open(os.environ['CURL_URL_LOG'], 'a') as log:
    log.write(json.dumps(urls) + '\\n')
endpoint = os.environ['TEST_ENDPOINT']
args = [os.environ['TEST_SERVER'] + arg[len(endpoint):] if arg.startswith(endpoint + '/') else arg for arg in args]
sys.exit(subprocess.call([os.environ['REAL_CURL'], *args]))
''')
        file.chmod(0o755)

    def requested_api_urls(self):
        return [url for line in (self.path / 'curl-urls.json').read_text().splitlines()
                for url in json.loads(line) if '/api/' in url]

    def action_default_url(self):
        action = (ROOT / 'publish/action.yml').read_text()
        self.assertIn('DIFF_STAGE_URL: ${{ inputs.url }}', action)
        return re.search(r'^  url:\n(?:    .*\n)*?    default: (\S+)', action, re.M).group(1)

    def test_action_default_publishes_with_identity_and_service_links(self):
        endpoint = self.action_default_url()
        self.assertEqual(endpoint, 'https://diffstage.com')
        self.route_endpoint_to_server(endpoint)
        self.public_url = endpoint
        result = self.run_publish(DIFF_STAGE_URL=endpoint, **self.identity_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requested_api_urls(), [endpoint + path for path in (
            '/api/runs', '/api/runs/run1/video-uploads', '/api/runs/run1/videos', '/api/runs/run1/video-uploads', '/api/runs/run1/videos', '/api/runs/run1/complete')])
        self.assertEqual(self.credentials, ['Bearer github-identity'] * 6)
        self.assertEqual(json.loads(self.requests[-1][1]), {'expected_videos': 2})
        comment = (self.path / 'comment.md').read_text()
        self.assertIn('[Watch all 2 on Diff Stage](https://diffstage.com/runs/run1)', comment)
        self.assertEqual([link['href'] for link in self.comment().links], [endpoint + '/runs/run1#video1'] * 4)
        self.assertEqual([image['src'] for image in self.comment().images], [endpoint + '/videos/video1/poster'] * 2)

    def test_action_default_fast_capture_uses_recordings_api_and_service_links(self):
        endpoint = self.action_default_url()
        self.route_endpoint_to_server(endpoint)
        self.public_url = endpoint
        for name in ('booking', 'checkout'):
            (self.path / (name + '.json')).write_text(json.dumps({'capture_version': 1}))
        (self.path / 'titles.json').write_text(json.dumps({name + '.webm': name for name in ('booking', 'checkout')}))
        result = self.run_publish(DIFF_STAGE_URL=endpoint, **self.identity_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requested_api_urls(), [endpoint + path for path in ('/api/runs', '/api/runs/run1/recording-uploads', '/api/runs/run1/recordings')])
        self.assertEqual(self.credentials, ['Bearer github-identity'] * 3)
        self.assertEqual([link['href'] for link in self.comment().links], [endpoint + '/runs/run1#booking', endpoint + '/runs/run1#checkout'])

    def test_custom_endpoint_preserves_path_and_service_returned_urls(self):
        endpoint = 'https://self-hosted.example/diff-stage/'
        self.route_endpoint_to_server(endpoint)
        self.public_url = 'https://evidence.example'
        result = self.run_publish(DIFF_STAGE_URL=endpoint)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.requested_api_urls(), [endpoint.rstrip('/') + path for path in (
            '/api/runs', '/api/runs/run1/video-uploads', '/api/runs/run1/videos', '/api/runs/run1/video-uploads', '/api/runs/run1/videos', '/api/runs/run1/complete')])
        self.assertEqual(self.credentials, ['Bearer test'] * 6)
        self.assertEqual(self.identity_requests, [])
        self.assertIn('[Watch all 2 on Diff Stage](https://evidence.example/runs/run1)', (self.path / 'comment.md').read_text())
        self.assertEqual([link['href'] for link in self.comment().links], ['https://evidence.example/runs/run1#video1'] * 4)

    def test_failed_completion_never_comments(self):
        self.complete_status = 409
        result = self.run_publish(**self.identity_env())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Upload count does not match', result.stderr)
        self.assertEqual(len(self.uploads()), 2)
        self.assertTrue(self.requests[-1][0].endswith('/complete'))
        self.assertFalse((self.path / 'gh.log').exists())

    def test_fast_capture_uploads_each_recording_directly_without_encoding_or_waiting_for_rendering(self):
        titles = {}
        for name in ('booking', 'checkout'):
            titles[name + '.webm'] = 'ExampleTest › ' + name
            (self.path / (name + '.json')).write_text(json.dumps({'capture_version': 1, 'cursor': [], 'holds': [], 'steps': [], 'assertions': [], 'problems': []}))
        (self.path / 'titles.json').write_text(json.dumps(titles))
        self.stub('ffmpeg', 'echo "Encoding should be hosted" >&2; exit 1')
        self.stub('compress', 'echo "Encoding should be hosted" >&2; exit 1')
        result = self.run_publish(**self.identity_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([path for path, *_ in self.requests], ['/api/runs', '/api/runs/run1/recording-uploads', '/api/runs/run1/recordings'])
        self.assertEqual(len(self.identity_requests), 3)
        self.assertEqual(json.loads(self.requests[-1][1]), {'direct_upload': True, 'review': []})
        self.assertEqual(len(self.storage_requests), 2)
        for index, (path, body, headers) in enumerate(self.storage_requests):
            metadata = self.direct_metadata[index]
            name = metadata['file'].removesuffix('.webm')
            self.assertEqual(path, '/storage/' + metadata['file'])
            self.assertNotIn('Authorization', headers)
            self.assertEqual(int(headers['Content-Length']), len(body))
            self.assertEqual(headers['Content-MD5'], base64.b64encode(hashlib.md5(body).digest()).decode())
            self.assertEqual(metadata['md5'], hashlib.md5(body).hexdigest())
            with zipfile.ZipFile(io.BytesIO(body)) as archive:
                self.assertEqual(sorted(archive.namelist()), [name + '.json', name + '.webm', 'titles.json'])
                self.assertEqual(json.loads(archive.read(name + '.json'))['capture_version'], 1)
                self.assertEqual(json.loads(archive.read('titles.json')), {metadata['file']: metadata['title']})
                self.assertEqual(metadata['expanded_size'], sum(entry.file_size for entry in archive.infolist()))
        comment = (self.path / 'comment.md').read_text()
        self.assertIn('Processing on Diff Stage', comment)
        self.assertIn('http://watch/run1#booking', comment)
        self.assertNotIn('<img', comment)

    def test_retry_prepares_identical_uploads_after_artifact_timestamps_change(self):
        for name in ('booking', 'checkout'):
            (self.path / (name + '.json')).write_text(json.dumps({'capture_version': 1}))
        (self.path / 'titles.json').write_text(json.dumps({name + '.webm': name for name in ('booking', 'checkout')}))
        first = self.run_publish(**self.identity_env())
        self.assertEqual(first.returncode, 0, first.stderr)
        metadata = list(self.direct_metadata)
        bodies = [body for _, body, _ in self.storage_requests]
        self.storage_requests.clear()
        for path in self.path.glob('*.webm'):
            os.utime(path, (1000000000, 1000000000))
        second = self.run_publish(**self.identity_env())
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.direct_metadata, metadata)
        self.assertEqual([body for _, body, _ in self.storage_requests], bodies)

    def test_compressed_baselines_upload_media_to_storage_and_only_metadata_to_the_api(self):
        result = self.run_publish(MODE='baseline', **self.identity_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.storage_requests), 4)
        self.assertEqual(len(self.compressed_metadata), 2)
        for index, (path, body, headers) in enumerate(self.storage_requests):
            role = ('video', 'poster')[index % 2]
            metadata = self.compressed_metadata[index // 2][role]
            self.assertEqual(path, f'/storage/upload{index // 2 + 1}/' + role)
            self.assertEqual(body, b'video' if role == 'video' else b'poster')
            self.assertNotIn('Authorization', headers)
            self.assertEqual(headers['Content-Type'], metadata['content_type'])
            self.assertEqual(int(headers['Content-Length']), len(body))
            self.assertEqual(headers['Content-MD5'], base64.b64encode(hashlib.md5(body).digest()).decode())
            self.assertEqual(metadata['size'], len(body))
            self.assertEqual(metadata['md5'], hashlib.md5(body).hexdigest())
        for body in self.uploads():
            self.assertIsNotNone(form_field(body, 'upload_id'))
            self.assertNotIn(b'name="video";', body)
            self.assertNotIn(b'name="poster";', body)
            self.assertIn(b'name="telemetry";', body)
        self.assertEqual(self.requests[-1][0], '/api/runs/run1/complete')
        self.assertFalse((self.path / 'gh.log').exists())

    def test_failed_compressed_storage_upload_never_registers_or_completes_a_run(self):
        self.direct_upload_status = 403
        result = self.run_publish(MODE='baseline', **self.identity_env())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([path for path, *_ in self.requests], ['/api/runs', '/api/runs/run1/video-uploads'])
        self.assertEqual(len(self.storage_requests), 1)
        self.assertFalse((self.path / 'gh.log').exists())

    def test_failed_direct_upload_never_queues_processing_or_comments(self):
        self.direct_upload_status = 403
        for name in ('booking', 'checkout'):
            (self.path / (name + '.json')).write_text(json.dumps({'capture_version': 1}))
        (self.path / 'titles.json').write_text(json.dumps({name + '.webm': name for name in ('booking', 'checkout')}))
        result = self.run_publish(**self.identity_env())
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([path for path, *_ in self.requests], ['/api/runs', '/api/runs/run1/recording-uploads'])
        self.assertEqual(len(self.storage_requests), 1)
        self.assertFalse((self.path / 'gh.log').exists())

    def test_app_identity_uploads_without_a_project_secret(self):
        result = self.run_publish(**self.identity_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.credentials, ['Bearer github-identity'] * 6)
        self.assertEqual(len(self.identity_requests), 6)
        for url, authorization in self.identity_requests:
            self.assertEqual(parse_qs(urlparse(url).query), {'job': ['123'], 'audience': ['diff-stage']})
            self.assertEqual(authorization, 'Bearer request-token')
        self.assertNotIn('github-identity', result.stdout)
        self.assertIn('::add-mask::github-identity', result.stderr)
        self.assertIn('pr comment 42', (self.path / 'gh.log').read_text())

    def test_baseline_also_uses_app_identity(self):
        result = self.run_publish(MODE='baseline', **self.identity_env())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.credentials, ['Bearer github-identity'] * 6)
        self.assertFalse((self.path / 'gh.log').exists())

    def test_explicit_project_token_takes_precedence(self):
        result = self.run_publish(**(self.identity_env() | {'DIFF_STAGE_TOKEN': 'project-token'}))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.identity_requests, [])
        self.assertEqual(self.credentials, ['Bearer project-token'] * 6)

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
        self.assertEqual([path for path, *_ in self.requests], ['/api/runs', '/api/runs/run1/video-uploads', '/api/runs/run1/videos', '/api/runs/run1/video-uploads', '/api/runs/run1/videos', '/api/runs/run1/complete'])
        for (_, body, _), key in zip([request for request in self.requests if request[0].endswith('/videos')], ('booking', 'checkout')):
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

    def test_comment_previews_every_video_and_preserves_titles_as_text(self):
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
        self.assertNotIn('<table>', body)
        comment = self.comment()
        self.assertEqual(len(comment.images), 5)
        self.assertEqual(len(comment.links), 10)
        for image, title in zip(comment.images, titles.values()):
            self.assertEqual(image, {'src': 'http://poster', 'width': '640', 'alt': title})
        for title in titles.values():
            self.assertIn(title[0].upper() + title[1:], comment.text)
        self.assertNotIn('What to check', body)

    def test_selection_notes_order_uploads_and_explain_each_test(self):
        reason = '@/etc/hostname shows the <script> & "decline" message'
        (self.path / 'titles.json').write_text(json.dumps({
            'booking.webm': 'BookingTest › it confirms a booking',
            'checkout.webm': 'CheckoutTest › it explains a declined card',
        }))
        self.select(('tests/Browser/CheckoutTest.php', 'it explains a declined card', reason),
                    ('tests/Browser/MissingTest.php', 'it was never recorded', 'Not recorded anywhere.'),
                    ('tests/Browser/BookingTest.php', None, 'x' * 1200))
        result = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('::warning::Diff Stage selection names tests/Browser/MissingTest.php::it was never recorded, but no video matches it.', result.stderr)
        checkout, booking = self.uploads()
        self.assertEqual(form_field(checkout, 'flow_key'), 'checkout')
        self.assertEqual(form_field(checkout, 'review_reason'), reason)
        self.assertEqual(form_field(checkout, 'review_order'), '1')
        self.assertEqual(form_field(booking, 'review_reason'), 'x' * 1000)
        self.assertEqual(form_field(booking, 'review_order'), '3')
        comment = self.comment()
        text = ''.join(comment.text)
        self.assertIn(reason, comment.text)
        self.assertLess(text.index('It explains a declined card'), text.index(reason))
        self.assertLess(text.index(reason), text.index('It confirms a booking'))
        self.assertIn('CheckoutTest', text)
        self.assertEqual([image['alt'] for image in comment.images],
                         ['CheckoutTest › it explains a declined card', 'BookingTest › it confirms a booking'])

    def test_dataset_variants_share_one_note_and_link_each_variant(self):
        for name in ('booking', 'checkout'):
            (self.path / f'{name}.webm').unlink()
        for name in ('booking-desktop', 'booking-mobile'):
            (self.path / f'{name}.webm').write_bytes(b'video')
        (self.path / 'titles.json').write_text(json.dumps({
            'booking-desktop.webm': 'BookingTest › it confirms a booking with dataset "desktop"',
            'booking-mobile.webm': 'BookingTest › it confirms a booking with dataset "mobile"',
        }))
        self.select(('tests/Browser/BookingTest.php', 'it confirms a booking', 'Watch the badge.'))
        result = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([form_field(body, 'review_reason') for body in self.uploads()], ['Watch the badge.'] * 2)
        body = (self.path / 'comment.md').read_text()
        self.assertEqual(body.count('<h4>'), 1)
        self.assertEqual(body.count('Watch the badge.'), 1)
        self.assertEqual(len(self.comment().images), 1)
        self.assertIn('BookingTest · <a href="http://watch/run1">desktop</a> · <a href="http://watch/run1">mobile</a>', body)

    def test_notes_follow_tests_outside_the_default_browser_folder(self):
        (self.path / 'titles.json').write_text(json.dumps({'booking.webm': 'booking.spec › it confirms a booking'}))
        self.select(('spec/browser/booking.spec.php', 'it confirms a booking', 'Watch the badge.'))
        result = self.run_publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(form_field(self.uploads()[0], 'review_reason'), 'Watch the badge.')

    def test_review_notes_only_change_pull_request_runs(self):
        self.select(('tests/Browser/BookingTest.php', None, 'Reason.'))
        result = self.run_publish(MODE='baseline')
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
