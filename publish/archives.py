"""Prepare one private worker ZIP per fast recording."""
import hashlib
import json
from pathlib import Path
import sys
import shutil
import zipfile

root, output = map(Path, sys.argv[1:])
titles = json.loads((root / 'titles.json').read_text())
videos = []
for video in sorted(root.glob('*.webm')):
    path = output / (video.stem + '.zip')
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for source_path in (video, video.with_suffix('.json')):
            entry = zipfile.ZipInfo(source_path.name)
            entry.compress_type = zipfile.ZIP_DEFLATED
            with source_path.open('rb') as source, archive.open(entry, 'w') as target:
                shutil.copyfileobj(source, target)
        title_entry = zipfile.ZipInfo('titles.json')
        title_entry.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(title_entry, json.dumps({video.name: titles[video.name]}))
        expanded_size = sum(entry.file_size for entry in archive.infolist())
    with path.open('rb') as source:
        checksum = hashlib.file_digest(source, 'md5').hexdigest()
    videos.append({'file': video.name, 'title': titles[video.name],
                   'size': path.stat().st_size, 'expanded_size': expanded_size, 'md5': checksum})
print(json.dumps({'videos': videos}))
