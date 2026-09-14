from pathlib import Path
import hashlib, json, re, sys, zipfile
ROOT=Path(__file__).resolve().parents[1]
errors=[]
required=['README.md','LICENSE.md','COPYRIGHT.md','THIRD_PARTY_NOTICES.md','REFERENCES.md','CITATION.cff','src/bootstrap/INSTALAR_A1111_ARCHVIZ.bat','src/runtime-core/ABRIR_A1111_ARCHVIZ.bat']
for rel in required:
    if not (ROOT/rel).is_file(): errors.append('missing '+rel)
for rel in ['src/bootstrap/INSTALAR_A1111_ARCHVIZ.bat','src/runtime-core/ABRIR_A1111_ARCHVIZ.bat','src/runtime-core/archviz/run_install_core.bat']:
    p=ROOT/rel
    if p.is_file():
        t=p.read_text(encoding='ascii', errors='strict')
        if 'Copyright (c) 2026 Dr. Magdiel Torres Vanegas' not in t: errors.append('copyright header missing '+rel)
# no model weights in repo
bad_ext={'.safetensors','.ckpt','.pt','.pth'}
for p in ROOT.rglob('*'):
    if p.is_file() and p.suffix.lower() in bad_ext: errors.append('model/binary weight committed '+str(p.relative_to(ROOT)))
    if p.is_file() and p.stat().st_size > 50*1024*1024: errors.append('unexpected large file '+str(p.relative_to(ROOT)))
# no absolute local drive paths
pat=re.compile(r'(?i)\b[A-Z]:\\(?:Users|Motores|Escritorio|Downloads|Descargas)\\')
for p in ROOT.rglob('*'):
    if p.is_file() and p.suffix.lower() in {'.md','.py','.ps1','.bat','.json','.txt','.csv','.cff'}:
        try: text=p.read_text(encoding='utf-8-sig')
        except UnicodeDecodeError: continue
        if pat.search(text): errors.append('local absolute path '+str(p.relative_to(ROOT)))
if errors:
    print('\n'.join('FAIL: '+e for e in errors)); sys.exit(1)
print('PASS: repository validation')
