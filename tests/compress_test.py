"""Verify trimming with real ffmpeg, including repeat publishing."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CompressionTest(unittest.TestCase):
    def test_trim_shifts_telemetry_without_overwriting_raw_times(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            video = path / 'flow.webm'
            output = path / 'flow.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                            'color=white:s=160x90:r=25:d=1', '-f', 'lavfi', '-i',
                            'color=blue:s=160x90:r=25:d=2', '-filter_complex',
                            '[0:v][1:v]concat=n=2:v=1:a=0', '-c:v', 'libvpx', str(video)], check=True)
            raw = {'steps': [{'at': 1.5, 'text': 'Clicked checkout'}],
                   'problems': [{'at': 0.2, 'kind': 'console', 'text': 'Error'}],
                   'assertions': [{'at': 0.1, 'text': 'Early check',
                                   'finished_at': 0.2, 'passed': False},
                                  {'at': 1.2, 'text': 'Confirmation is visible',
                                   'finished_at': 2.5, 'passed': True}]}
            source = path / 'flow.json'
            source.write_text(json.dumps(raw))
            results = []
            for _ in range(2):
                subprocess.run(['bash', str(ROOT / 'bin/diff-stage-compress'), str(video), str(output)], check=True)
                results.append(json.loads(Path(str(output) + '.json').read_text()))
            self.assertEqual(json.loads(source.read_text()), raw)
            self.assertEqual(results[0], results[1])
            self.assertAlmostEqual(results[0]['steps'][0]['at'], 0.5, delta=0.1)
            self.assertEqual(results[0]['problems'][0]['at'], 0)
            self.assertAlmostEqual(results[0]['assertions'][1]['at'], 0.2, delta=0.1)
            self.assertAlmostEqual(results[0]['assertions'][1]['finished_at'], 1.5, delta=0.1)
            self.assertTrue(results[0]['assertions'][1]['passed'])
            self.assertEqual(results[0]['assertions'][0]['at'], 0)
            self.assertEqual(results[0]['assertions'][0]['finished_at'], 0)
            self.assertFalse(results[0]['assertions'][0]['passed'])
            duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                                                      'format=duration', '-of', 'csv=p=0', str(output)]))
            self.assertAlmostEqual(duration, 3, delta=0.15)


if __name__ == '__main__':
    unittest.main()
