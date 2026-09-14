"""Build the educational GitHub release asset from the repository source tree.
This script does not download third-party model weights.
"""
from pathlib import Path
import zipfile, hashlib, shutil, json, re
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'
DIST.mkdir(exist_ok=True)
# This repository exposes source for educational review. The canonical release asset is built
# from the frozen source/manifests and should be validated on Windows before publication.
print('Source tree ready. Use the frozen packaging pipeline to construct the release ZIP; see release/RELEASE_NOTES_v8.2.0-A0-STABLE.md')
