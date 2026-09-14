"""Verify that exactly one installed distribution owns cv2 binary files."""
from importlib import metadata
from pathlib import Path
import json
import cv2
projects = ['opencv-contrib-python', 'opencv-python', 'opencv-python-headless']
out = {'cv2': cv2.__version__, 'cv2_file': str(Path(cv2.__file__).resolve()), 'distributions': {}}
for project in projects:
    dist = metadata.distribution(project)
    files = [str(x).replace('\\', '/') for x in (dist.files or [])]
    out['distributions'][project] = {'version': dist.version,'cv2_files': sum(x.startswith('cv2/') or '/cv2/' in x for x in files)}
assert out['distributions']['opencv-contrib-python']['version'] == '4.10.0.84'
assert out['distributions']['opencv-contrib-python']['cv2_files'] > 0
assert out['distributions']['opencv-python']['version'] == '4.10.0.84+archviz1'
assert out['distributions']['opencv-python-headless']['version'] == '4.10.0.84+archviz1'
assert out['distributions']['opencv-python']['cv2_files'] == 0
assert out['distributions']['opencv-python-headless']['cv2_files'] == 0
print(json.dumps(out, indent=2))
