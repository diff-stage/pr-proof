"""Hold recorded assertion outcomes and keep all captions on the edited timeline."""
import json
import math
from pathlib import Path
import subprocess
import sys

video, output, start, end = sys.argv[1:]
start, end = float(start), float(end)
source = Path(video).with_suffix('.json')
data = json.loads(source.read_text()) if source.exists() else None
holds = []
if data:
    assertions = data.get('assertions', [])
    changes = sorted(entry['at'] for entry in data.get('steps', []) + assertions)
    for assertion in assertions:
        finished = assertion['finished_at']
        if not start <= finished < end:
            continue
        # Freeze a captured frame after the outcome, rather than its checking frame.
        boundary = min(end - start, (math.ceil((finished - start) * 25) + 1) / 25)
        following = next((at for at in changes if at > finished), None)
        if following is None or following < start + boundary:
            continue
        extra = max(0, 2 - (following - start - boundary))
        if extra:
            if holds and holds[-1][0] == boundary:
                holds[-1] = (boundary, max(extra, holds[-1][1]))
            else:
                holds.append((boundary, extra))

expression = 'PTS-STARTPTS' + ''.join(
    f'+gte(T,{at:.6f})*{seconds:.6f}/TB' for at, seconds in holds
)
subprocess.run([
    'ffmpeg', '-v', 'error', '-y', '-ss', str(start), '-to', str(end), '-i', video,
    '-vf', f"setpts='{expression}',fps=25,tpad=stop_mode=clone:stop_duration=2,format=yuv420p",
    '-an', '-c:v', 'libx264', '-crf', '28', '-movflags', '+faststart', output,
], check=True)

if data is not None:
    def shifted(time):
        trimmed = max(0, time - start)
        return round(trimmed + sum(seconds for at, seconds in holds if at <= trimmed), 2)

    for entry in data.get('steps', []) + data.get('problems', []) + data.get('assertions', []):
        entry['at'] = shifted(entry['at'])
        if 'finished_at' in entry:
            entry['finished_at'] = shifted(entry['finished_at'])
    Path(output + '.json').write_text(json.dumps(data, indent=2, ensure_ascii=False))
