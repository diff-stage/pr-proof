"""Describe compressed media for authenticated upload grants."""
import hashlib
import json
from pathlib import Path
import sys

files = {}
for role, filename, content_type in zip(('video', 'poster'), sys.argv[1:], ('video/mp4', 'image/jpeg')):
    path = Path(filename)
    with path.open('rb') as source:
        checksum = hashlib.file_digest(source, 'md5').hexdigest()
    files[role] = {'size': path.stat().st_size, 'md5': checksum, 'content_type': content_type}
print(json.dumps({'files': files}))
