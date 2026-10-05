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
            self.assertAlmostEqual(duration, 4, delta=0.15)

    def test_holds_outcomes_and_shifts_later_checks_actions_and_problems(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            video, output = path / 'flow.webm', path / 'flow.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                            'color=blue:s=160x90:r=25:d=1', '-f', 'lavfi', '-i',
                            'color=red:s=160x90:r=25:d=1', '-filter_complex',
                            '[0:v][1:v]concat=n=2:v=1:a=0', '-c:v', 'libvpx', str(video)], check=True)
            raw = {'steps': [{'at': 1.2, 'text': 'Opened next screen'}],
                   'problems': [{'at': 1.1, 'kind': 'console', 'text': 'Error'}],
                   'assertions': [{'at': .4, 'finished_at': .5, 'passed': True, 'text': 'Saved'},
                                  {'at': .6, 'finished_at': .7, 'passed': False, 'text': 'Missing'}]}
            source = video.with_suffix('.json')
            source.write_text(json.dumps(raw))
            subprocess.run(['bash', str(ROOT / 'bin/diff-stage-compress'), str(video), str(output)], check=True)
            result = json.loads(Path(str(output) + '.json').read_text())
            self.assertEqual(json.loads(source.read_text()), raw)
            self.assertEqual(result['assertions'][0]['finished_at'], .5)
            self.assertEqual(result['assertions'][1]['at'], 2.56)
            self.assertEqual(result['assertions'][1]['finished_at'], 2.66)
            self.assertFalse(result['assertions'][1]['passed'])
            self.assertEqual(result['steps'][0]['at'], 4.72)
            self.assertEqual(result['problems'][0]['at'], 4.62)
            for time, channel in [(3, 2), (4.8, 0)]:
                pixel = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(time),
                                                 '-i', str(output), '-frames:v', '1', '-vf',
                                                 'scale=1:1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'])
                self.assertGreater(pixel[channel], 200)
                self.assertLess(pixel[2 if channel == 0 else 0], 20)

    def test_legacy_video_without_assertions_keeps_its_action_timing(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / 'legacy.webm'
            output = Path(directory) / 'legacy.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                            'color=blue:s=160x90:r=25:d=1', '-c:v', 'libvpx', str(video)], check=True)
            video.with_suffix('.json').write_text(json.dumps({'steps': [{'at': .5, 'text': 'Clicked'}], 'problems': []}))
            subprocess.run(['bash', str(ROOT / 'bin/diff-stage-compress'), str(video), str(output)], check=True)
            result = json.loads(Path(str(output) + '.json').read_text())
            self.assertEqual(result['steps'][0]['at'], .5)
            duration = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries',
                                                      'format=duration', '-of', 'csv=p=0', str(output)]))
            self.assertAlmostEqual(duration, 3, delta=.1)


if __name__ == '__main__':
    unittest.main()
