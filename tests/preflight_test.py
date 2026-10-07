"""Run the trusted action with fake GitHub identity and service responses."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PreflightTest(unittest.TestCase):
    def check(self, status=200, identity=True):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            preload = path / 'fetch.cjs'
            preload.write_text('''const fs = require('node:fs');
let call = 0;
global.fetch = async (url, options) => {
 fs.appendFileSync(process.env.REQUEST_LOG, JSON.stringify({url:String(url), ...options, signal:undefined})+'\\n');
 call++;
 return call === 1 ? {ok:true, status:200, json:async()=>({value:'private-identity'})}
 : {ok:process.env.STATUS === '200', status:Number(process.env.STATUS), json:async()=>({message:'Connect this repository to an active Diff Stage GitHub App installation.'})};
};''')
            env = dict(os.environ, DIFF_STAGE_URL='https://diffstage.com', STATUS=str(status), REQUEST_LOG=str(path / 'requests'))
            env.pop('ACTIONS_ID_TOKEN_REQUEST_URL', None)
            env.pop('ACTIONS_ID_TOKEN_REQUEST_TOKEN', None)
            if identity:
                env.update(ACTIONS_ID_TOKEN_REQUEST_URL='https://identity.example/token?run=1', ACTIONS_ID_TOKEN_REQUEST_TOKEN='private-request')
            result = subprocess.run(['node', '--require', str(preload), str(ROOT / 'preflight/preflight.cjs')], env=env, capture_output=True, text=True)
            calls = [json.loads(line) for line in (path / 'requests').read_text().splitlines()] if (path / 'requests').exists() else []
            return result, calls

    def test_checks_authenticated_repository_without_creating_a_run(self):
        result, calls = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('audience=diff-stage', calls[0]['url'])
        self.assertEqual(calls[1]['url'], 'https://diffstage.com/api/preflight')
        self.assertEqual(calls[1]['headers']['Authorization'], 'Bearer private-identity')
        self.assertEqual(calls[1]['redirect'], 'error')
        self.assertIn('::add-mask::private-identity', result.stdout)
        self.assertIn('Ready to record', result.stdout)

    def test_disconnected_repository_fails_with_actionable_message(self):
        result, _ = self.check(403)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Connect this repository', result.stderr)
        self.assertNotIn('private-identity', result.stderr)

    def test_missing_identity_permission_fails_without_requests(self):
        result, calls = self.check(identity=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('id-token: write', result.stderr)
        self.assertEqual(calls, [])

if __name__ == '__main__':
    unittest.main()
