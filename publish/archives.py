"""Prepare one private worker ZIP per fast recording."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

root, output = map(Path, sys.argv[1:])
titles = json.loads((root / 'titles.json').read_text())
videos = []
for video in sorted(root.glob('*.webm')):
    path = output / (video.stem + '.zip')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(video, video.name)
        telemetry = video.with_suffix('.json')
        archive.write(telemetry, telemetry.name)
        archive.writestr('titles.json', json.dumps({video.name: titles[video.name]}))
        expanded_size = sum(entry.file_size for entry in archive.infolist())
    with path.open('rb') as source:
        checksum = hashlib.file_digest(source, 'md5').hexdigest()
    videos.append({'file': video.name, 'title': titles[video.name],
                   'size': path.stat().st_size, 'expanded_size': expanded_size, 'md5': checksum})
print(json.dumps({'videos': videos}))
