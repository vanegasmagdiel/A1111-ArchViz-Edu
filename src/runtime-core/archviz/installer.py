"""A1111 ArchViz v8.2 A0 STABLE: frozen portable Windows runtime."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

SUPPORT = Path(__file__).resolve().parent
BASE = SUPPORT.parent
CATALOG = json.loads((SUPPORT / 'catalog.json').read_text(encoding='utf-8'))
AUXILIARY_ASSETS = CATALOG.get('auxiliary_assets', [])
A1111_REPO = 'AUTOMATIC1111/stable-diffusion-webui'
CN_REPO = 'Mikubill/sd-webui-controlnet'
CN_COMMIT = '56cec5b2958edf3b1807b7e7b2b1b5186dbd2f81'
ENGINE_VERSION = '8.2.0-A0-STABLE'
PINNED_A1111_TAG = 'v1.10.1'
PINNED_A1111_COMMIT = '82a973c04367123ae98bd9abdf80d9eda9b910e2'
CLIP_COMMIT = 'd50d76daa670286dd6cacf3bcd80b5e4823fc8e1'
OPENCV_PROVIDER_VERSION = '4.10.0.84'
OPENCV_SHIM_VERSION = '4.10.0.84+archviz1'
USER_AGENT = 'ArchViz-Portable/8.2-A0-STABLE'

PROFILE_UI_PRESETS = {
    # A0 UI defaults only. Backend/runtime flag tuning is A1 responsibility.
    'DIAGNOSTIC': {
        'width': 512, 'height': 512, 'steps': 20, 'cfg': 7.0,
        'sampler': 'DPM++ 2M', 'scheduler': 'Automatic',
        'batch_count': 1, 'batch_size': 1, 'hires_fix': False,
    },
    'LITE': {
        'width': 640, 'height': 640, 'steps': 20, 'cfg': 6.0,
        'sampler': 'DPM++ 2M', 'scheduler': 'Automatic',
        'batch_count': 1, 'batch_size': 1, 'hires_fix': False,
    },
    'STANDARD': {
        'width': 896, 'height': 896, 'steps': 24, 'cfg': 6.0,
        'sampler': 'DPM++ 2M', 'scheduler': 'Automatic',
        'batch_count': 1, 'batch_size': 1, 'hires_fix': False,
    },
    'PREMIUM': {
        'width': 1024, 'height': 1024, 'steps': 28, 'cfg': 5.5,
        'sampler': 'DPM++ 2M', 'scheduler': 'Automatic',
        'batch_count': 1, 'batch_size': 1, 'hires_fix': False,
    },
    'PREMIUM_PLUS': {
        'width': 1024, 'height': 1024, 'steps': 30, 'cfg': 5.5,
        'sampler': 'DPM++ 2M', 'scheduler': 'Automatic',
        'batch_count': 1, 'batch_size': 1, 'hires_fix': False,
    },
    'WORKSTATION': {
        'width': 1024, 'height': 1024, 'steps': 32, 'cfg': 5.0,
        'sampler': 'DPM++ 2M', 'scheduler': 'Automatic',
        'batch_count': 1, 'batch_size': 1, 'hires_fix': False,
    },
}


def canonical_profile_preset(profile):
    name = str(profile).upper()
    if name not in PROFILE_UI_PRESETS:
        raise Blocked('Perfil de hardware no reconocido: ' + repr(profile))
    return dict(PROFILE_UI_PRESETS[name])


def a1111_ui_defaults(profile):
    p = canonical_profile_preset(profile)
    return {
        'txt2img/Width/value': p['width'],
        'txt2img/Height/value': p['height'],
        'txt2img/CFG Scale/value': p['cfg'],
        'txt2img/Hires. fix/value': p['hires_fix'],
        'txt2img/Batch count/value': p['batch_count'],
        'txt2img/Batch size/value': p['batch_size'],
        'customscript/sampler.py/txt2img/Sampling method/value': p['sampler'],
        'customscript/sampler.py/txt2img/Schedule type/value': p['scheduler'],
        'customscript/sampler.py/txt2img/Sampling steps/value': p['steps'],
    }


def read_profile_selection(path):
    """Read Windows PowerShell 5.1 JSON safely.

    Set-Content -Encoding UTF8 in Windows PowerShell 5.1 writes a UTF-8 BOM.
    utf-8-sig accepts both BOM and non-BOM JSON. A0 must never silently fall
    back to another profile because doing so changes user-visible defaults.
    """
    path = Path(path)
    if not path.is_file():
        raise Blocked('Falta PROFILE_SELECTION.json; no se aplican defaults por suposicion.')
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError, TypeError) as exc:
        raise Blocked('PROFILE_SELECTION.json no es legible/valido.') from exc

    profile = str(data.get('profile', '')).upper()
    preset = canonical_profile_preset(profile)

    outer = data.get('ui_defaults')
    if outer is not None:
        if not isinstance(outer, dict):
            raise Blocked('ui_defaults del selector de hardware no es un objeto.')
        for key, expected in preset.items():
            if key not in outer:
                raise Blocked('PROFILE_SELECTION.json no contiene ui_defaults.' + key)
            actual = outer[key]
            if isinstance(expected, float):
                if abs(float(actual) - expected) > 1e-9:
                    raise Blocked(f'Drift de perfil {profile}: {key}={actual!r}, esperado {expected!r}.')
            elif actual != expected:
                raise Blocked(f'Drift de perfil {profile}: {key}={actual!r}, esperado {expected!r}.')
    return profile, preset



class Blocked(RuntimeError):
    pass


class ApiHTTPError(Blocked):
    def __init__(self, code, path, detail=''):
        self.code = int(code)
        self.path = path
        self.detail = detail
        super().__init__(f'API HTTP {self.code} en {path}: {detail[:1800]}')


def wait_for_api_endpoint(api_call, path, alive, timeout=120, interval=2, label='API', require_key=None):
    """Wait until an endpoint exists and returns valid JSON.

    A1111 starts the Gradio HTTP server before it mounts the core API and before
    app_started callbacks register extension routes. A transient 404 is therefore
    a normal startup state, not an installation failure.
    """
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        if not alive():
            raise Blocked(f'{label} no pudo inicializar: A1111 termino antes de responder.')
        try:
            value = api_call(path, timeout=5)
            if require_key is not None:
                if not isinstance(value, dict) or require_key not in value:
                    last = ValueError(f'respuesta sin clave {require_key!r}: {value!r}')
                else:
                    return value
            else:
                return value
        except ApiHTTPError as exc:
            if exc.code not in (404, 503):
                raise
            last = exc
        except (OSError, ValueError) as exc:
            last = exc
        print(f'Esperando {label}...', flush=True)
        time.sleep(interval)
    suffix = '' if last is None else f' Ultimo estado: {last}'
    raise Blocked(f'Timeout esperando {label} en {path}.{suffix}')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    os.replace(temp, path)


def contained(root, relative):
    """Return a lexical child path while validating containment canonically.

    Windows may canonicalize an 8.3 path (ESTUDI~1) to its long form when
    Path.resolve() is called. Returning that canonical path makes harmless
    aliases fail equality checks and can unexpectedly rewrite user-visible
    paths. Security still requires canonical resolution to catch symlink/junction
    escapes, but callers should receive the original lexical root.
    """
    # Reject Windows escape paths even in Linux cleanroom tests.
    if not isinstance(relative, str) or '\\' in relative or ':' in relative:
        raise Blocked('Ruta invalida: ' + repr(relative))
    rel = PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise Blocked('Ruta fuera del destino: ' + relative)

    root_lex = Path(root)
    if not root_lex.is_absolute():
        root_lex = root_lex.absolute()
    dest_lex = root_lex.joinpath(*rel.parts)

    try:
        root_real = root_lex.resolve(strict=False)
        dest_real = dest_lex.resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        raise Blocked('No se pudo validar la ruta: ' + relative) from exc

    # commonpath + normcase is robust to Windows case folding and 8.3 aliases.
    try:
        common = os.path.commonpath([os.path.normcase(str(root_real)),
                                     os.path.normcase(str(dest_real))])
    except ValueError as exc:
        raise Blocked('Ruta en volumen distinto: ' + relative) from exc
    if os.path.normcase(common) != os.path.normcase(str(root_real)):
        raise Blocked('Ruta o enlace fuera del destino: ' + relative)
    return dest_lex


def validate_catalog(catalog):
    ids, destinations = set(), set()
    for a in catalog['assets']:
        if a['id'] in ids or a['dest'].lower() in destinations:
            raise Blocked('ID o destino duplicado en catalogo.')
        ids.add(a['id']); destinations.add(a['dest'].lower())
        contained(BASE, a['dest']); contained(BASE, a['file'])
        if a.get('converted_dest'):
            contained(BASE, a['converted_dest'])
            if a['converted_dest'].lower() in destinations:
                raise Blocked('Destino derivado duplicado.')
            destinations.add(a['converted_dest'].lower())
        if not re.fullmatch(r'[\w.-]+/[\w.-]+', a['repo']):
            raise Blocked('Repositorio HF invalido.')
        if not re.fullmatch('[0-9a-f]{40}', a['revision']):
            raise Blocked('Revision de modelo no inmutable.')
        if not re.fullmatch('[0-9a-f]{64}', a['sha256']) or a['size'] <= 8:
            raise Blocked('Hash/tamano de modelo invalido.')
        if not a['dest'].endswith('.safetensors'):
            raise Blocked('El catalogo de modelos solo admite Safetensors.')
    for a in catalog.get('auxiliary_assets', []):
        if a.get('id') in ids or a.get('dest','').lower() in destinations:
            raise Blocked('ID o destino auxiliar duplicado en catalogo.')
        ids.add(a['id']); destinations.add(a['dest'].lower())
        contained(BASE, a['dest'])
        if not a.get('url','').startswith('https://'):
            raise Blocked('Activo auxiliar requiere HTTPS.')
        if not re.fullmatch('[0-9a-f]{64}', a.get('sha256','')) or int(a.get('size',0)) <= 8:
            raise Blocked('Hash/tamano de activo auxiliar invalido.')


def download_auxiliary_asset(asset, root, quarantine):
    """Download a small immutable HTTPS asset and accept it only by exact size/SHA-256."""
    target = contained(root, asset['dest'])
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file():
        if target.stat().st_size == asset['size'] and digest(target) == asset['sha256']:
            return target
        quarantine(target)
    part = target.with_suffix(target.suffix + '.part')
    if part.exists():
        part.unlink()
    req = urllib.request.Request(asset['url'], headers={'User-Agent': USER_AGENT})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as response, part.open('wb') as out:
                shutil.copyfileobj(response, out, length=1024 * 1024)
            if part.stat().st_size != asset['size'] or digest(part) != asset['sha256']:
                quarantine(part)
                raise Blocked('Activo auxiliar descargado no coincide con tamaño/SHA-256: ' + asset['id'])
            os.replace(part, target)
            return target
        except Blocked:
            raise
        except Exception as exc:
            last = exc
            if part.exists():
                part.unlink()
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise Blocked('No se pudo descargar activo auxiliar verificado: ' + asset['id'] + '. ' + str(last))


def read_json_url(url, timeout=60):
    if not url.startswith('https://'):
        raise Blocked('Metadatos remotos requieren HTTPS.')
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):
                raise Blocked(f'Acceso/fuente no disponible HTTP {e.code}: {url}. No se elude la restriccion.') from e
            if attempt == 2: raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2: raise
        time.sleep(2 * (attempt + 1))


def resolve_release(api=read_json_url):
    """Use the validated A1111 release pinned for v8.2 A0 STABLE; never drift to latest."""
    return {'tag': PINNED_A1111_TAG, 'commit': PINNED_A1111_COMMIT,
            'release_url': 'https://github.com/AUTOMATIC1111/stable-diffusion-webui/releases/tag/v1.10.1',
            'resolved_utc': '2026-09-13T07:34:00Z', 'selection': 'stable-pinned'}


def safetensors_header(path):
    path = Path(path)
    with path.open('rb') as f:
        n = int.from_bytes(f.read(8), 'little')
        if not 2 < n <= min(100 * 1024 * 1024, path.stat().st_size - 8):
            raise Blocked('Cabecera Safetensors invalida: ' + path.name)
        try:
            data = json.loads(f.read(n))
        except (ValueError, UnicodeError) as e:
            raise Blocked('Safetensors no es JSON valido: ' + path.name) from e
    tensors = {k: v for k, v in data.items() if k != '__metadata__'}
    if not tensors:
        raise Blocked('Safetensors sin tensores: ' + path.name)
    limit = path.stat().st_size - 8 - n
    for v in tensors.values():
        if not isinstance(v, dict) or 'dtype' not in v or 'shape' not in v:
            raise Blocked('Tensor incompleto: ' + path.name)
        offsets = v.get('data_offsets', [])
        if len(offsets) != 2 or not (0 <= offsets[0] <= offsets[1] <= limit):
            raise Blocked('Offsets fuera de archivo: ' + path.name)
    return data


def lora_key(key):
    """Diffusers SDXL names -> A1111/Kohya names, without changing tensors."""
    if key.startswith(('lora_unet_', 'lora_te1_', 'lora_te2_')):
        return key
    match = re.fullmatch(r'(unet|text_encoder|text_encoder_2)\.(.+)\.(?:lora|lora_linear_layer)\.(down|up)\.weight', key)
    if not match:
        raise Blocked('Formato de tensor LoRA no reconocido: ' + key)
    group, module, direction = match.groups()
    prefix = {'unet': 'lora_unet_', 'text_encoder': 'lora_te1_', 'text_encoder_2': 'lora_te2_'}[group]
    return prefix + module.replace('.', '_') + '.lora_' + direction + '.weight'


def converted_lora_header(source):
    header = safetensors_header(source)
    converted = {}
    for key, value in header.items():
        if key == '__metadata__': continue
        new = lora_key(key)
        if new in converted: raise Blocked('Colision de nombres al convertir LoRA.')
        converted[new] = value
    converted['__metadata__'] = {**header.get('__metadata__', {}),
                                 'ss_base_model_version': 'sdxl_base_v1-0',
                                 'archviz_converter': '8.2.0-A0-STABLE', 'source_sha256': digest(source)}
    encoded = json.dumps(converted, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode()
    encoded += b' ' * ((-len(encoded)) % 8)
    return len(encoded).to_bytes(8, 'little') + encoded


def convert_lora(source, destination=None):
    """Deterministic streaming conversion; destination=None computes expected hash."""
    prefix = converted_lora_header(source)
    h = hashlib.sha256(prefix)
    out = None
    if destination:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists(): raise Blocked('No se sobrescribe LoRA existente.')
        out = Path(str(destination) + '.part').open('wb')
        out.write(prefix)
    try:
        with Path(source).open('rb') as f:
            old_size = int.from_bytes(f.read(8), 'little'); f.seek(8 + old_size)
            for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
                h.update(block)
                if out: out.write(block)
    finally:
        if out: out.close()
    if destination:
        os.replace(str(destination) + '.part', destination)
        safetensors_header(destination)
    return h.hexdigest()


def parse_freeze_lines(text):
    """Normalize pip freeze and reject absolute/local source coupling."""
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if ' @ file:' in low or low.startswith('-e '):
            raise Blocked('Freeze no portable: dependencia ligada a ruta local: ' + line)
        rows.append(line)
    return rows


def sha_manifest(root, exclude_names=()):
    root = Path(root)
    rows = []
    for path in sorted(p for p in root.rglob('*') if p.is_file()):
        if path.name in exclude_names:
            continue
        rows.append({'relative': path.relative_to(root).as_posix(), 'bytes': path.stat().st_size,
                     'sha256': digest(path)})
    return rows

def download_asset(asset, root, runner, quarantine):
    dest = contained(root, asset['dest'])
    dest.parent.mkdir(parents=True, exist_ok=True)
    def valid(p):
        return p.is_file() and p.stat().st_size == asset['size'] and digest(p) == asset['sha256']
    if dest.exists():
        if not valid(dest):
            raise Blocked(f'Destino con contenido distinto: {dest}. No se sobrescribe.')
        safetensors_header(dest)
        return 'cached_verified'
    part = Path(str(dest) + '.part')
    if part.exists() and part.stat().st_size > asset['size']:
        quarantine(part)
    url = f'https://huggingface.co/{asset["repo"]}/resolve/{asset["revision"]}/{urllib.parse.quote(asset["file"], safe="/")}'
    if not part.exists() or part.stat().st_size != asset['size']:
        # cURL does not carry an HF credential to redirected storage hosts.
        runner(['curl.exe', '--location', '--fail', '--retry', '3', '--connect-timeout', '30',
                '--speed-limit', '1024', '--speed-time', '120', '--continue-at', '-',
                '--output', str(part), url], f'download_{asset["id"]}')
    if not valid(part):
        quarantine(part)
        raise Blocked('SHA256/tamano incorrecto: ' + asset['id'] + '. Copia conservada en cuarentena; reejecute.')
    safetensors_header(part)
    os.replace(part, dest)
    return 'downloaded_verified'


def controlnet_unit_payload(model, image_b64, weight=0.65, guidance_end=0.8):
    """Payload exacto para ControlNet v1.1.455 API/Pydantic schema."""
    return {
        'enabled': True,
        'module': 'none',
        'model': model,
        'weight': weight,
        'image': image_b64,
        'resize_mode': 'Crop and Resize',
        'guidance_start': 0.0,
        'guidance_end': guidance_end,
        'control_mode': 'Balanced',
    }


QUIET_DETAIL_PREFIXES = (
    'git_init', 'git_config', 'git_remote', 'git_fetch', 'git_checkout',
    'git_rev-parse', 'git_fsck', 'git_symbolic_ref', 'git_status',
)
QUIET_DETAIL_LABELS = {'pip_freeze'}
FRIENDLY_LABELS = {
    'git_version': 'Verificando Git portable',
    'gpu': 'Verificando GPU NVIDIA',
    'download_realvis': 'Descargando RealVisXL V5',
    'download_juggernaut': 'Descargando JuggernautXL v9',
    'download_vae': 'Descargando SDXL VAE',
    'download_canny': 'Descargando ControlNet Canny SDXL',
    'download_depth': 'Descargando ControlNet Depth SDXL',
    'download_interior_lora': 'Descargando LoRA Interior',
    'download_lcm_lora': 'Descargando LoRA LCM',
    'pip_probe': 'Comprobando gestor de paquetes',
    'pip_bootstrap': 'Inicializando gestor de paquetes',
    'pip_tools': 'Verificando herramientas Python',
    'torch_cuda': 'Instalando PyTorch CUDA',
    'torch_runtime_deps': 'Instalando dependencias CUDA',
    'opencv_remove_overlaps': 'Preparando OpenCV',
    'opencv_binary_provider': 'Instalando OpenCV',
    'opencv_shim_opencv_python': 'Registrando compatibilidad OpenCV',
    'opencv_shim_opencv_python_headless': 'Registrando compatibilidad OpenCV headless',
    'joint_requirements': 'Instalando dependencias A1111 y ControlNet',
    'clip_build_wheel': 'Preparando CLIP',
    'clip_wheel_install': 'Instalando CLIP',
    'a1111_prepare': 'Preparando repositorios internos A1111',
    'pip_check': 'Verificando dependencias',
    'opencv_provider_probe': 'Verificando proveedor OpenCV',
    'runtime_cuda': 'Verificando CUDA y runtime',
    'wheelhouse_pypi': 'Construyendo wheelhouse PyPI',
    'wheelhouse_torch': 'Construyendo wheelhouse CUDA',
}
def operation_title(label):
    return FRIENDLY_LABELS.get(label, label.replace('_', ' ').strip().capitalize())
def operation_visible(label):
    if label in QUIET_DETAIL_LABELS:
        return False
    return not any(label.startswith(prefix) for prefix in QUIET_DETAIL_PREFIXES)

class Engine:
    def __init__(self, base=BASE):
        self.base = Path(base).resolve()
        self.ui = self.base / 'A1111_ArchViz'
        if self.ui.resolve().parent != self.base:
            raise Blocked('A1111_ArchViz es un enlace fuera de la carpeta; no se modifica.')
        self.state = self.base / '_archviz_state'
        self.report = self.state / 'reports' / (time.strftime('%Y%m%d_%H%M%S') + '_' + secrets.token_hex(3))
        self.report.mkdir(parents=True, exist_ok=True)
        self.py = self.base / '_archviz_runtime/system/python/python.exe'
        self.git = self.base / '_archviz_runtime/system/git/bin/git.exe'
        self.receipt = self.state / 'PASS.json'
        self.process = None
        self.counter = 0
        self.env = os.environ.copy()
        for key in ('PYTHONPATH', 'VIRTUAL_ENV', 'COMMANDLINE_ARGS', 'PIP_TARGET', 'PIP_PREFIX',
                    'TORCH_COMMAND', 'TORCH_INDEX_URL', 'REQS_FILE', 'CLIP_PACKAGE',
                    'OPENCLIP_PACKAGE', 'XFORMERS_PACKAGE'):
            self.env.pop(key, None)
        self.env.pop('PIP_EXTRA_INDEX_URL', None)
        self.env.pop('PIP_TRUSTED_HOST', None)
        self.env.update(PYTHONNOUSERSITE='1', PYTHONUTF8='1', PIP_DISABLE_PIP_VERSION_CHECK='1',
                        PIP_CONFIG_FILE=os.devnull, PIP_INDEX_URL='https://pypi.org/simple',
                        GIT_TERMINAL_PROMPT='0', GIT=str(self.git),
                        STABLE_DIFFUSION_REPO='https://github.com/w-e-w/stablediffusion.git',
                        HF_HOME=str(self.base / '_archviz_cache/huggingface'),
                        TORCH_HOME=str(self.base / '_archviz_cache/torch'),
                        PIP_CACHE_DIR=str(self.base / '_archviz_cache/pip'))
        self.env['NO_PROXY'] = '127.0.0.1,localhost,' + self.env.get('NO_PROXY', '')

    def run(self, argv, label, check=True, cwd=None):
        self.counter += 1
        log = self.report / f'{self.counter:02d}_{label}.log'
        visible = operation_visible(label)
        title = operation_title(label)
        started = time.monotonic()
        if visible:
            print(f'    {title}...', flush=True)
        last_heartbeat = started
        with log.open('w', encoding='utf-8') as f:
            proc = subprocess.Popen([str(x) for x in argv], cwd=cwd, env=self.env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding='utf-8', errors='replace')
            try:
                for line in proc.stdout:
                    f.write(line); f.flush()
                    now = time.monotonic()
                    if visible and (now - last_heartbeat) >= 20:
                        print(f'      {title}: en curso...', flush=True)
                        last_heartbeat = now
                rc = proc.wait()
            except BaseException:
                proc.terminate(); proc.wait(); raise
            finally:
                if proc.stdout is not None:
                    proc.stdout.close()
        output = log.read_text(encoding='utf-8')
        elapsed = time.monotonic() - started
        if check and rc:
            print(f'    [ERROR] {title}. Revise {log.name}', flush=True)
            raise Blocked(f'{label} fallo ({rc}). {output[-1600:]}\nInforme: {log}')
        if visible:
            print(f'    [PASS] {title} ({elapsed:.1f}s)', flush=True)
        return rc, output

    def pip_install(self, args, label, constraint=True):
        """Install with an explicit constraint argv item (safe with spaces)."""
        argv = [self.py, '-m', 'pip', 'install']
        if constraint:
            argv += ['-c', SUPPORT / 'dependencies-win310.lock']
        argv += list(args)
        return self.run(argv, label)

    def harden_opencv(self):
        """Keep exactly one cv2 binary provider; metadata shims satisfy upstream package names."""
        # All three official OpenCV distributions install overlapping cv2 files. Remove all
        # providers first, then install contrib as the sole binary owner and two metadata-only
        # wheels for dependency-name compatibility (ControlNet/Albumentations).
        self.run([self.py, '-m', 'pip', 'uninstall', '-y',
                  'opencv-python', 'opencv-python-headless', 'opencv-contrib-python'],
                 'opencv_remove_overlaps', check=False)
        self.pip_install(['opencv-contrib-python==' + OPENCV_PROVIDER_VERSION], 'opencv_binary_provider')
        shimdir = SUPPORT / 'opencv_shims'
        for project in ('opencv_python', 'opencv_python_headless'):
            matches = list(shimdir.glob(project + '-*-py3-none-any.whl'))
            if len(matches) != 1:
                raise Blocked('Shim OpenCV ausente/ambiguo: ' + project)
            package_name = project.replace('_', '-')
            self.run([self.py, '-m', 'pip', 'install', '--no-deps', '--no-index', '--find-links', shimdir,
                      package_name + '==' + OPENCV_SHIM_VERSION], 'opencv_shim_' + project)


    def build_clip_wheel(self, source):
        """Build pinned OpenAI CLIP into a wheel so site-packages has no absolute source path."""
        wheel_dir = self.state / 'wheels'
        wheel_dir.mkdir(parents=True, exist_ok=True)
        existing = list(wheel_dir.glob('clip-1.0-*.whl'))
        if not existing:
            self.run([self.py, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation',
                      '--wheel-dir', wheel_dir, source], 'clip_build_wheel')
            existing = list(wheel_dir.glob('clip-1.0-*.whl'))
        if len(existing) != 1:
            raise Blocked('Wheel CLIP ausente/ambiguo tras build.')
        wheel = existing[0]
        self.run([self.py, '-m', 'pip', 'install', '--force-reinstall', '--no-deps', '--no-index',
                  '--find-links', wheel_dir, 'clip==1.0'], 'clip_wheel_install')
        return wheel


    def ensure_release_tag(self):
        """Create a local tag at the already verified release commit to silence git describe warnings."""
        try:
            current = self.git_cmd(self.ui, 'rev-parse', 'HEAD')
            if current != PINNED_A1111_COMMIT:
                raise Blocked('No se etiqueta un commit A1111 distinto del commit fijado para v8.2 A0 STABLE.')
            self.run([self.git, '-C', self.ui, 'tag', '-f', PINNED_A1111_TAG, PINNED_A1111_COMMIT],
                     'git_release_tag')
        except Blocked:
            raise


    def opencv_probe(self):
        return self.run([self.py, SUPPORT / 'opencv_probe.py'], 'opencv_provider_probe')


    def git_cmd(self, repo, *args):
        return self.run([self.git, '-C', repo, *args], 'git_' + args[0])[1].strip()

    def clone_pinned(self, repo_name, commit, destination):
        if destination.exists():
            if not (destination / '.git').is_dir():
                raise Blocked('Carpeta existente sin Git; no se altera: ' + str(destination))
            if self.git_cmd(destination, 'status', '--porcelain', '--untracked-files=no'):
                raise Blocked('Cambios locales detectados. Se conservan: ' + str(destination))
            if self.git_cmd(destination, 'rev-parse', 'HEAD') != commit:
                raise Blocked('Commit distinto del lock. Extraiga una copia nueva para actualizar.')
        else:
            stage = destination.parent / (destination.name + '.clone_' + secrets.token_hex(4))
            stage.parent.mkdir(parents=True, exist_ok=True)
            self.run([self.git, 'init', stage], 'git_init')
            self.git_cmd(stage, 'config', 'core.longpaths', 'true')
            self.git_cmd(stage, 'remote', 'add', 'origin', f'https://github.com/{repo_name}.git')
            self.git_cmd(stage, 'fetch', '--depth', '1', 'origin', commit)
            # Keep HEAD attached to a local immutable-style branch. A1111 reads
            # extension metadata through GitPython; detached HEAD makes
            # repo.active_branch raise TypeError even though the commit is valid.
            self.git_cmd(stage, 'checkout', '-B', 'archviz-pinned', 'FETCH_HEAD')
            if self.git_cmd(stage, 'rev-parse', 'HEAD') != commit:
                raise Blocked('El checkout no coincide con el SHA remoto.')
            self.git_cmd(stage, 'fsck', '--full')
            stage.rename(destination)
        self.ensure_attached_head(destination, commit)
        self.git_cmd(destination, 'fsck', '--full')

    def ensure_attached_head(self, repo, commit):
        rc, _ = self.run([self.git, '-C', repo, 'symbolic-ref', '-q', 'HEAD'],
                         'git_symbolic_ref', check=False)
        if rc != 0:
            self.run([self.git, '-C', repo, 'checkout', '-B', 'archviz-pinned', commit],
                     'git_attach_branch')
        if self.git_cmd(repo, 'rev-parse', 'HEAD') != commit:
            raise Blocked('No se pudo mantener HEAD en el commit fijado.')

    def quarantine(self, file):
        target = self.state / 'quarantine' / (file.name + '_' + secrets.token_hex(6))
        target.parent.mkdir(parents=True, exist_ok=True)
        file.rename(target)
        print('Conservado en cuarentena:', target)

    def load_lock(self, create=False):
        lock_path = self.state / 'versions.lock.json'
        if lock_path.exists():
            lock = json.loads(lock_path.read_text(encoding='utf-8'))
            if lock['catalog_sha256'] != digest(SUPPORT / 'catalog.json'):
                raise Blocked('Catalogo diferente al lock. Use una carpeta nueva para otra version.')
            if lock.get('a1111', {}).get('commit') != PINNED_A1111_COMMIT or lock.get('controlnet_commit') != CN_COMMIT:
                raise Blocked('Lock previo no coincide con los commits fijados para v8.2 A0 STABLE.')
            return lock
        if not create:
            raise Blocked('No hay instalacion registrada. Ejecute el instalador universal v8.2.')
        if self.ui.exists():
            raise Blocked('A1111_ArchViz ya existe sin lock; no se adopta ni sobrescribe.')
        release = resolve_release()
        lock = {'schema': 1, 'a1111': release, 'controlnet_commit': CN_COMMIT,
                'catalog_sha256': digest(SUPPORT / 'catalog.json'), 'assets': CATALOG['assets']}
        atomic_json(lock_path, lock)
        print('Release estable seleccionado:', release['tag'], release['commit'])
        return lock

    def preflight(self):
        if os.name != 'nt':
            raise Blocked('Instalacion solo Windows x64. En Linux ejecute los tests offline.')
        if sys.version_info[:2] != (3, 10):
            raise Blocked('El bootstrap debe suministrar Python 3.10.')
        if not self.py.is_file() or not self.git.is_file():
            raise Blocked('Bootstrap incompleto.')
        self.run([self.git, '--version'], 'git_version')
        smi = shutil.which('nvidia-smi')
        if not smi:
            raise Blocked('NVIDIA/controlador no detectado. No se instala ni modifica el driver.')
        _, gpu = self.run([smi, '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'], 'gpu')
        if re.search(r'RTX\s*50\d\d|\bB[12]00\b', gpu, re.I):
            raise Blocked('GPU Blackwell detectada: este perfil Torch 2.1.2 no es compatible. No se fuerza un PASS.')
        sizes = [a['size'] for a in CATALOG['assets'] if not contained(self.ui, a['dest']).exists()]
        sizes += [a['size'] for a in AUXILIARY_ASSETS if not contained(self.ui, a['dest']).exists()]
        required = sum(sizes) + 15 * 1024**3
        if shutil.disk_usage(self.base).free < required:
            raise Blocked(f'Espacio insuficiente; se requieren {required/1024**3:.1f} GiB libres para esta ejecucion.')

    def install(self):
        self.preflight()
        lock = self.load_lock(create=True)
        self.invalidate()
        print('[1/5] Descargando y verificando codigo A1111/ControlNet...')
        self.clone_pinned(A1111_REPO, lock['a1111']['commit'], self.ui)
        self.ensure_release_tag()
        ext = self.ui / 'extensions/sd-webui-controlnet'

        self.clone_pinned(CN_REPO, lock['controlnet_commit'], ext)
        print('[2/5] Descargando catalogo SDXL verificado...')
        for asset in lock['assets']:
            print('Modelo:', asset['id'], flush=True)
            download_asset(asset, self.ui, self.run, self.quarantine)
            if asset.get('converted_dest'):
                source = contained(self.ui, asset['dest'])
                dest = contained(self.ui, asset['converted_dest'])
                expected = convert_lora(source)
                if dest.exists():
                    if digest(dest) != expected: raise Blocked('LoRA derivado modificado: ' + str(dest))
                else: convert_lora(source, dest)
                atomic_json(self.report / (asset['id'] + '_conversion.json'),
                            {'source_sha256': asset['sha256'], 'derived_sha256': expected,
                             'derived_file': asset['converted_dest'], 'tensor_data_unchanged': True})
        self.configure()
        print('[2b/5] Materializando activos auxiliares verificados...')
        self.ensure_auxiliary_assets()
        print('[3/5] Preparando dependencias...')
        pip_rc, _ = self.run([self.py, '-m', 'pip', '--version'], 'pip_probe', check=False)
        if pip_rc != 0:
            get_pip = self.py.parent / 'get-pip.py'
            if not get_pip.is_file():
                raise Blocked('El Python portable no contiene get-pip.py: ' + str(get_pip))
            # Do not export PIP_CONSTRAINT here. Pip splits repeatable env options on
            # whitespace, corrupting support paths such as D:\Motores IA\... .
            self.run([self.py, get_pip, 'pip==24.3.1', 'setuptools==69.5.1', 'wheel==0.43.0'], 'pip_bootstrap')
        self.pip_install(['pip==24.3.1', 'setuptools==69.5.1', 'wheel==0.43.0'], 'pip_tools')
        # Install the exact CUDA wheels from the PyTorch index WITHOUT resolving
        # transitive dependencies there. The CUDA index is not a full PyPI mirror;
        # applying the global lock while using --index-url can make ordinary packages
        # such as filelock appear unsatisfiable even though they exist on PyPI.
        self.pip_install(['--no-deps', 'torch==2.1.2', 'torchvision==0.16.2',
                          '--index-url', 'https://download.pytorch.org/whl/cu121'],
                         'torch_cuda', constraint=False)
        # Resolve Torch/Torchvision runtime dependencies from normal PyPI under the
        # reproducible lock. This keeps the CUDA wheels fixed while allowing their
        # pure-Python dependencies to come from the correct package index.
        self.pip_install(['filelock', 'fsspec', 'jinja2', 'networkx', 'sympy',
                          'typing-extensions', 'requests', 'numpy==1.26.2',
                          'Pillow==9.5.0'], 'torch_runtime_deps')
        self.harden_opencv()
        # Resolve A1111 and ControlNet TOGETHER, not successive incompatible overrides.

        self.pip_install(['--prefer-binary', '-r', self.ui / 'requirements_versions.txt',
                          '-r', ext / 'requirements.txt'], 'joint_requirements')
        clip = self.state / 'sources/CLIP'
        self.clone_pinned('openai/CLIP', CLIP_COMMIT, clip)
        self.build_clip_wheel(clip)
        # Core architecture profile needs Canny + externally supplied depth maps.
        # Skip optional installers for FaceID/hands; never fetch arbitrary binary wheels.
        self.run([self.py, self.ui / 'launch.py', '--exit', '--skip-install', '--no-download-sd-model'],
                 'a1111_prepare', cwd=self.ui)
        print('[4/5] Integridad, dependencias e inventario...')
        self.verify(lock)
        print('[5/5] Arranque real y generacion de imagenes de prueba...')
        self.serve(lock, smoke=True, keep=True)

    def selected_profile(self):
        path = self.base / '_archviz_state_a0' / 'PROFILE_SELECTION.json'
        profile, _ = read_profile_selection(path)
        return profile

    def selected_profile_record(self):
        path = self.base / '_archviz_state_a0' / 'PROFILE_SELECTION.json'
        profile, preset = read_profile_selection(path)
        return path, profile, preset

    def ensure_auxiliary_assets(self):
        rows = []
        for asset in AUXILIARY_ASSETS:
            print('Activo auxiliar:', asset['id'], flush=True)
            path = download_auxiliary_asset(asset, self.ui, self.quarantine)
            row = {'id': asset['id'], 'relative': asset['dest'], 'bytes': path.stat().st_size,
                   'sha256': digest(path), 'status': 'PASS', 'source': asset['url']}
            rows.append(row)
            atomic_json(self.report / (asset['id'] + '_cert.json'), row)
        return rows

    def ui_defaults(self, profile):
        return a1111_ui_defaults(profile)

    def verify_ui_defaults(self, profile, preset):
        ui_target = self.ui / 'ui-config.json'
        if not ui_target.is_file():
            raise Blocked('No se creo ui-config.json.')
        try:
            current = json.loads(ui_target.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError, TypeError) as exc:
            raise Blocked('ui-config.json no es legible/valido.') from exc
        expected = self.ui_defaults(profile)
        actual = {}
        for key, value in expected.items():
            if key not in current:
                raise Blocked('ui-config.json no contiene el default requerido: ' + key)
            actual[key] = current[key]
            if isinstance(value, float):
                if abs(float(current[key]) - value) > 1e-9:
                    raise Blocked(f'Default UI incorrecto para {profile}: {key}={current[key]!r}; esperado {value!r}.')
            elif current[key] != value:
                raise Blocked(f'Default UI incorrecto para {profile}: {key}={current[key]!r}; esperado {value!r}.')
        return actual

    def configure(self):
        # Clean install writes current defaults once; resume never overwrites user settings.
        target = self.ui / 'styles.csv'
        if not target.exists():
            shutil.copy2(SUPPORT / 'styles.csv', target)
        target = self.ui / 'config.json'
        if not target.exists():
            atomic_json(target, {'sd_model_checkpoint': 'RealVisXL_V5.0_fp16.safetensors',
                                 'sd_vae': 'sdxl.vae.safetensors', 'samples_save': True,
                                 'grid_save': False, 'control_net_unit_count': 2,
                                 'lora_add_hashes_to_infotext': True})
        selection_path, profile, preset = self.selected_profile_record()
        ui_target = self.ui / 'ui-config.json'
        defaults = self.ui_defaults(profile)

        current = {}
        if ui_target.exists():
            try:
                current = json.loads(ui_target.read_text(encoding='utf-8-sig'))
            except (OSError, ValueError, TypeError) as exc:
                raise Blocked('ui-config.json upstream no es legible/valido.') from exc
            if not isinstance(current, dict):
                raise Blocked('ui-config.json upstream no es un objeto.')
        current.update(defaults)
        atomic_json(ui_target, current)
        actual = self.verify_ui_defaults(profile, preset)

        profile_receipt = {
            'schema': 'archviz.ui.profile.applied.v1',
            'engine': ENGINE_VERSION,
            'profile': profile,
            'source': str(selection_path.relative_to(self.base)),
            'source_sha256': digest(selection_path),
            'preset': preset,
            'a1111_ui_keys': defaults,
            'verified_actual': actual,
            'status': 'PASS',
        }
        atomic_json(self.state / 'PROFILE_DEFAULTS_APPLIED.json', profile_receipt)
        atomic_json(self.report / 'ui_defaults.json', profile_receipt)
        print(f'Defaults UI aplicados: {profile} -> {preset["width"]}x{preset["height"]}, '
              f'{preset["steps"]} steps, CFG {preset["cfg"]}', flush=True)

    def invalidate(self):
        if self.receipt.exists():
            previous = self.report / 'previous_PASS.json'
            self.receipt.replace(previous)

    def verify(self, lock):
        for name, commit, repo in [('a1111', lock['a1111']['commit'], self.ui),
                                   ('controlnet', lock['controlnet_commit'], self.ui / 'extensions/sd-webui-controlnet')]:
            if self.git_cmd(repo, 'rev-parse', 'HEAD') != commit:
                raise Blocked(name + ': commit no coincide con lock.')
            if self.git_cmd(repo, 'status', '--porcelain', '--untracked-files=no'):
                raise Blocked(name + ': archivos rastreados modificados; no se certifica.')
            self.git_cmd(repo, 'fsck', '--full')
        rows = []
        for a in lock['assets']:
            path = contained(self.ui, a['dest'])
            print('Verificando SHA256:', a['id'], flush=True)
            if not path.is_file() or path.stat().st_size != a['size'] or digest(path) != a['sha256']:
                raise Blocked('Modelo no verificado: ' + str(path))
            safetensors_header(path)
            rows.append({'id': a['id'], 'relative': a['dest'], 'bytes': a['size'], 'sha256': a['sha256'], 'status': 'PASS'})
            if a.get('converted_dest'):
                converted = contained(self.ui, a['converted_dest'])
                expected = convert_lora(path)
                if not converted.is_file() or digest(converted) != expected:
                    raise Blocked('LoRA derivado no coincide con fuente verificada: ' + str(converted))
                rows.append({'id': a['id'] + '_a1111', 'relative': a['converted_dest'],
                             'bytes': converted.stat().st_size, 'sha256': expected, 'status': 'PASS'})
        for a in AUXILIARY_ASSETS:
            path = contained(self.ui, a['dest'])
            print('Verificando SHA256:', a['id'], flush=True)
            if not path.is_file() or path.stat().st_size != a['size'] or digest(path) != a['sha256']:
                raise Blocked('Activo auxiliar no verificado: ' + str(path))
            rows.append({'id': a['id'], 'relative': a['dest'], 'bytes': a['size'], 'sha256': a['sha256'], 'status': 'PASS'})
        with (self.report / 'inventory.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'relative', 'bytes', 'sha256', 'status'])
            writer.writeheader(); writer.writerows(rows)
        self.run([self.py, '-m', 'pip', 'check'], 'pip_check')
        _, freeze = self.run([self.py, '-m', 'pip', 'freeze', '--all'], 'pip_freeze')
        parse_freeze_lines(freeze)
        self.opencv_probe()
        self.run([self.py, SUPPORT / 'runtime_probe.py'], 'runtime_cuda', cwd=self.ui)
        if not (self.ui / 'styles.csv').is_file():
            raise Blocked('Falta styles.csv.')
        with (self.ui / 'styles.csv').open(encoding='utf-8-sig') as f:
            names = {x['name'] for x in csv.DictReader(f)}
        if not {'ARCHVIZ_INTERIOR_DAY_SDXL', 'ARCHVIZ_EXTERIOR_DAY_SDXL'} <= names:
            raise Blocked('Faltan estilos principales.')
        atomic_json(self.report / 'integrity.json', {'status': 'INTEGRITY_PASS', 'assets': rows})

    def controlnet_canny_detect(self, api, modules):
        """Exercise the actual Canny preprocessor endpoint; Depth remains external-map by profile."""
        import site
        site.addsitedir(str(self.py.parent / 'Lib/site-packages'))
        from PIL import Image, ImageDraw, ImageStat
        canny = next((x for x in modules if str(x).lower() == 'canny'), None)
        if canny is None:
            canny = next((x for x in modules if 'canny' in str(x).lower()), None)
        if canny is None:
            raise Blocked('ControlNet no expone preprocesador Canny.')
        image = Image.new('RGB', (512, 512), 'black')
        draw = ImageDraw.Draw(image); draw.rectangle((70,80,440,430), outline='white', width=6); draw.line((70,430,440,80), fill='white', width=4)
        buf = io.BytesIO(); image.save(buf, format='PNG')
        body = {'controlnet_module': canny, 'controlnet_input_images':[base64.b64encode(buf.getvalue()).decode()],
                'controlnet_processor_res':512, 'controlnet_threshold_a':100, 'controlnet_threshold_b':200}
        response = api('/controlnet/detect', body, timeout=300)
        images = response.get('images', [])
        if not images:
            raise Blocked('Preprocesador Canny no devolvio mapa.')
        data = base64.b64decode(images[0].split(',')[-1], validate=True)
        out = Image.open(io.BytesIO(data)); out.load()
        if max(ImageStat.Stat(out.convert('RGB')).stddev) < 0.5:
            raise Blocked('Mapa Canny vacio/constante.')
        path = self.report / 'controlnet_detect_canny.png'; path.write_bytes(data)
        atomic_json(self.report / 'controlnet_detect_canny.json', {'module':canny,'sha256':digest(path),'status':'PASS'})
        return {'module':canny,'status':'PASS','sha256':digest(path)}


    def snapshot_release(self, lock, result=None):
        """Create a relocatable, machine-readable certified snapshot from the successful runtime."""
        root = self.base / '_archviz_release' / ENGINE_VERSION
        stage = root.parent / (root.name + '.tmp_' + secrets.token_hex(3))
        if stage.exists(): shutil.rmtree(stage)
        stage.mkdir(parents=True, exist_ok=True)
        _, freeze = self.run([self.py, '-m', 'pip', 'freeze', '--all'], 'snapshot_pip_freeze')
        lines = parse_freeze_lines(freeze)
        (stage / 'runtime-freeze.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        (stage / 'dependencies-lock.txt').write_text((SUPPORT / 'dependencies-win310.lock').read_text(encoding='utf-8'), encoding='utf-8')
        source_lock = {'engine_version':ENGINE_VERSION,'a1111':lock['a1111'],'controlnet_commit':lock['controlnet_commit'],
                       'clip_commit':CLIP_COMMIT,'catalog_sha256':lock['catalog_sha256'],
                       'opencv':{'binary_provider':'opencv-contrib-python==4.10.0.84',
                                 'metadata_shims':['opencv-python==4.10.0.84+archviz1','opencv-python-headless==4.10.0.84+archviz1']}}
        atomic_json(stage / 'source-lock.json', source_lock)
        # Reuse the verified inventory from this run when present.
        inventory = self.report / 'inventory.csv'
        if inventory.is_file(): shutil.copy2(inventory, stage / 'models-inventory.csv')
        if result is not None: atomic_json(stage / 'PASS.json', result)
        # Important support files, but not the multi-gigabyte runtime itself.
        support_rows = sha_manifest(SUPPORT, exclude_names={'CLEANROOM.log','CLEANROOM_RC4.log','CLEANROOM_RC6.log','CLEANROOM_V81.log'})
        atomic_json(stage / 'support-hashes.json', support_rows)
        if root.exists(): shutil.rmtree(root)
        os.replace(stage, root)
        return root


    def build_offline_wheelhouse(self, lock):
        """Optional large artifact: download/build all Python wheels for offline runtime rebuild."""
        self.verify(lock)
        release = self.snapshot_release(lock)
        wheelhouse = release / 'wheelhouse'
        wheelhouse.mkdir(parents=True, exist_ok=True)
        lines = parse_freeze_lines((release / 'runtime-freeze.txt').read_text(encoding='utf-8'))
        excluded = ('torch==','torchvision==','clip==','opencv-python==','opencv-python-headless==')
        ordinary = [x for x in lines if not x.lower().startswith(excluded)]
        req = release / 'wheelhouse-requirements.txt'; req.write_text('\n'.join(ordinary)+'\n',encoding='utf-8')
        self.run([self.py, '-m', 'pip', 'wheel', '--no-deps', '--wheel-dir', wheelhouse, '-r', req], 'wheelhouse_pypi')
        self.run([self.py, '-m', 'pip', 'download', '--no-deps', '--dest', wheelhouse,
                  'torch==2.1.2', 'torchvision==0.16.2', '--index-url', 'https://download.pytorch.org/whl/cu121'], 'wheelhouse_torch')
        for p in (self.state / 'wheels').glob('clip-1.0-*.whl'): shutil.copy2(p, wheelhouse / p.name)
        for p in (SUPPORT / 'opencv_shims').glob('*.whl'): shutil.copy2(p, wheelhouse / p.name)
        manifest = sha_manifest(wheelhouse)
        atomic_json(release / 'wheelhouse-hashes.json', manifest)
        (release / 'WHEELHOUSE_READY.flag').write_text('PASS\n',encoding='utf-8')
        print('[PASS] Wheelhouse offline creado:', wheelhouse)
        return wheelhouse

    def serve(self, lock, smoke=True, keep=True):
        # A1111 is started locally for health tests; browser opens only after PASS.
        port = 7860
        with socket.socket() as sock:
            try: sock.bind(('127.0.0.1', port))
            except OSError as e: raise Blocked('Puerto 7860 ocupado. Cierre A1111 y reintente.') from e
        token = secrets.token_hex(24)
        authorization = 'Basic ' + base64.b64encode(('archviz:' + token).encode()).decode()
        url = f'http://127.0.0.1:{port}'
        flags = ['--api', '--api-auth', 'archviz:' + token, '--server-name', '127.0.0.1',
                 '--port', str(port), '--skip-install', '--no-download-sd-model',
                 '--opt-sdp-attention', '--medvram-sdxl', '--no-half-vae',
                 '--ckpt', str(contained(self.ui, CATALOG['assets'][0]['dest']))]
        logfile = (self.report / 'webui.log').open('w', encoding='utf-8')
        # Redact session API auth BEFORE any console or file write.
        self.process = subprocess.Popen([str(self.py), str(self.ui / 'launch.py'), *flags],
                                        cwd=self.ui, env=self.env, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace')
        server_errors = []
        def forward_output():
            essential = re.compile(
                r'Running on local URL:|Startup time:|ControlNet v[0-9]|CUDA out of memory|'
                r'Error loading script|Error running|Failed to load network|Couldn.t find network|'
                r'Failed to load model|Failed reading extension data', re.I)
            error_pattern = re.compile(
                r'CUDA out of memory|Error loading script|Error running|Failed to load network|'
                r'Couldn.t find network|Failed to load model|Failed reading extension data', re.I)
            for line in self.process.stdout:
                line = line.replace(token, '[SESSION_SECRET_REDACTED]')
                logfile.write(line); logfile.flush()
                if essential.search(line):
                    print('    ' + line.strip(), flush=True)
                if error_pattern.search(line):
                    server_errors.append(line.strip())
        reader = threading.Thread(target=forward_output, daemon=True)
        reader.start()
        local_http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def api(path, body=None, timeout=60):
            data = None if body is None else json.dumps(body).encode('utf-8')
            req = urllib.request.Request(url + path, data=data,
                                         headers={'Authorization': authorization, 'Content-Type': 'application/json'})
            try:
                with local_http.open(req, timeout=timeout) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read().decode('utf-8', errors='replace')
                except Exception:
                    detail = ''
                raise ApiHTTPError(e.code, path, detail) from e
        try:
            # Gradio begins listening before A1111 finishes adding /sdapi routes and
            # before extension app_started callbacks mount /controlnet routes.
            # Treat startup 404/503 as transient and wait for each layer explicitly.
            options = wait_for_api_endpoint(
                api, '/sdapi/v1/options', lambda: self.process.poll() is None,
                timeout=600, interval=5, label='API base de A1111')
            cn_version = wait_for_api_endpoint(
                api, '/controlnet/version', lambda: self.process.poll() is None,
                timeout=180, interval=2, label='API de ControlNet', require_key='version')
            print('ControlNet API lista. Version API:', cn_version.get('version'), flush=True)
            model_response = wait_for_api_endpoint(
                api, '/controlnet/model_list', lambda: self.process.poll() is None,
                timeout=60, interval=2, label='lista de modelos ControlNet', require_key='model_list')
            models = model_response['model_list']
            module_response = wait_for_api_endpoint(
                api, '/controlnet/module_list', lambda: self.process.poll() is None,
                timeout=60, interval=2, label='lista de preprocesadores ControlNet', require_key='module_list')
            preprocessor_result = self.controlnet_canny_detect(api, module_response['module_list'])
            loras = api('/sdapi/v1/loras')
            lora_names = {x['name'] for x in loras}
            if not {'Interior_MySpace_SDXL', 'LCM_SDXL_Preview'} <= lora_names:
                raise Blocked('A1111 no detecta los dos LoRA.')
            results = []
            if smoke:
                results = self.smoke(api, models)
                # Restore production defaults after LCM/controlnet test runs.
                api('/sdapi/v1/options', {'sd_model_checkpoint': 'RealVisXL_V5.0_fp16.safetensors',
                                        'sd_vae': 'sdxl.vae.safetensors'})
            if self.process.poll() is not None:
                raise Blocked('A1111 se detuvo durante la verificacion.')
            if server_errors:
                raise Blocked('Errores de extension/modelo en webui.log: ' + '; '.join(server_errors[:3]))
            result = {'status': 'PASS', 'version': ENGINE_VERSION, 'a1111': lock['a1111'],
                      'report': str(self.report), 'tests': results, 'preprocessor': preprocessor_result,
                      'scope': 'hashes + exact commits + pip check + single cv2 provider + portable CLIP wheel + CUDA + PyTorch SDP + ControlNet detect + native SDXL 1024 + inference A/B; no subjective quality certification',
                      'time_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
            atomic_json(self.report / 'result.json', result)
            atomic_json(self.receipt, result)
            release_snapshot = self.snapshot_release(lock, result=result)
            result['release_snapshot'] = str(release_snapshot)
            atomic_json(self.report / 'result.json', result)
            atomic_json(self.receipt, result)
            print('\n[PASS] A1111 ArchViz v8.2 A0 STABLE — runtime y generación verificados.', flush=True)
            if keep:
                webbrowser.open(url)
                print(url + ' | Mantenga esta consola abierta. Ctrl+C detiene A1111.', flush=True)
                rc = self.process.wait()
                if rc:
                    self.invalidate()
                    raise Blocked(f'A1111 termino con error {rc}; consulte webui.log.')
        finally:
            if self.process.poll() is None:
                self.process.terminate()
                try: self.process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=10)
            reader.join(timeout=10)
            logfile.close()

    def smoke(self, api, models):
        import site
        site.addsitedir(str(self.py.parent / 'Lib/site-packages'))
        from PIL import Image, ImageDraw, ImageStat, ImageChops
        sampler_names = {s['name'] for s in api('/sdapi/v1/samplers')}
        if 'LCM' not in sampler_names:
            raise Blocked('Sampler LCM no disponible; no se certifica el LoRA de preview.')
        def control(model_stem, depth=False):
            matches = [m for m in models if model_stem in m]
            if len(matches) != 1: raise Blocked('ControlNet no detectado o ambiguo: ' + model_stem)
            image = Image.new('RGB', (512, 512), (32, 32, 32) if depth else 'black')
            draw = ImageDraw.Draw(image)
            for i in range(3):
                box = (64 + i * 110, 110 + i * 40, 154 + i * 110, 420)
                draw.rectangle(box, fill=(80 + i * 60,) * 3 if depth else None, outline='white', width=3)
            out = io.BytesIO(); image.save(out, format='PNG')
            return controlnet_unit_payload(matches[0], base64.b64encode(out.getvalue()).decode(), weight=0.65, guidance_end=0.8)

        common_lora_prompt = 'sunlit contemporary living room, timber and stone, architectural photography'
        probes = [
            ('sdxl_native_1024', 'RealVisXL_V5.0_fp16.safetensors', 'contemporary architecture, daylight, realistic materials, architectural photography', None, 'Euler', 4, 5.0, 1024, 1024),
            ('exterior_canny', 'JuggernautXL_v9.safetensors', 'contemporary concrete house, exterior architecture, daylight', control('controlnet_canny_sdxl_fp16'), 'Euler', 6, 5.0, 512, 512),
            ('interior_lora_off', 'RealVisXL_V5.0_fp16.safetensors', common_lora_prompt, None, 'Euler', 6, 5.0, 512, 512),
            ('interior_lora_on', 'RealVisXL_V5.0_fp16.safetensors', common_lora_prompt + ' <lora:Interior_MySpace_SDXL:0.4>', None, 'Euler', 6, 5.0, 512, 512),
            ('preview_lcm_depth', 'RealVisXL_V5.0_fp16.safetensors', 'architectural exterior photograph <lora:LCM_SDXL_Preview:1>', control('controlnet_depth_sdxl_fp16', True), 'LCM', 4, 1.5, 512, 512),
        ]
        results=[]; images_by_name={}
        for name, checkpoint, prompt, unit, sampler, steps, cfg, width, height in probes:
            print('Generacion de comprobacion:', name, flush=True)
            body={'prompt':prompt,'negative_prompt':'text, watermark, blurry','seed':82731,
                  'steps':steps,'cfg_scale':cfg,'width':width,'height':height,'batch_size':1,'n_iter':1,
                  'sampler_name':sampler,'override_settings':{'sd_model_checkpoint':checkpoint,'sd_vae':'sdxl.vae.safetensors'},
                  'override_settings_restore_afterwards':True,'save_images':False}
            if unit: body['alwayson_scripts']={'ControlNet':{'args':[unit]}}
            started=time.monotonic(); response=api('/sdapi/v1/txt2img',body,timeout=1200); elapsed=time.monotonic()-started
            info=response.get('info','')
            if isinstance(info,str):
                try: info=json.loads(info)
                except ValueError: raise Blocked('La API devolvio info de generacion invalida: '+name)
            infotext='\n'.join(info.get('infotexts',[]))
            if unit and 'ControlNet 0' not in infotext: raise Blocked('La imagen no acredita aplicacion de ControlNet: '+name)
            if '<lora:' in prompt and 'Lora hashes:' not in infotext: raise Blocked('La imagen no acredita carga del LoRA: '+name)
            images=response.get('images',[])
            if not images: raise Blocked('La API no produjo imagen: '+name)
            data=base64.b64decode(images[0].split(',')[-1],validate=True); image=Image.open(io.BytesIO(data)); image.load()
            if image.size!=(width,height) or max(ImageStat.Stat(image.convert('RGB')).stddev)<0.5:
                raise Blocked('Imagen vacia/constante o dimensiones incorrectas: '+name)
            png=self.report/(name+'.png'); png.write_bytes(data); images_by_name[name]=image.convert('RGB')
            atomic_json(self.report/(name+'.json'),{'request':body,'info':response.get('info'),'sha256':digest(png),'elapsed_s':round(elapsed,3)})
            results.append({'id':name,'status':'PASS','sha256':digest(png),'width':width,'height':height,'elapsed_s':round(elapsed,3)})
        # Same prompt/seed/settings except LoRA: prove that the network changes the output, not only metadata.
        diff=ImageChops.difference(images_by_name['interior_lora_off'],images_by_name['interior_lora_on'])
        mean=sum(ImageStat.Stat(diff).mean)/3.0
        if mean < 0.5:
            raise Blocked('LoRA A/B no produjo diferencia visual medible.')
        atomic_json(self.report/'interior_lora_ab.json',{'status':'PASS','mean_abs_rgb_diff':mean,
                    'off_sha256':next(x['sha256'] for x in results if x['id']=='interior_lora_off'),
                    'on_sha256':next(x['sha256'] for x in results if x['id']=='interior_lora_on')})
        results.append({'id':'interior_lora_ab','status':'PASS','mean_abs_rgb_diff':mean})
        return results



def main():
    parser = argparse.ArgumentParser(description='A1111 ArchViz v8.2 A0 STABLE')
    parser.add_argument('action', choices=['install', 'launch', 'audit', 'selftest', 'freeze', 'wheelhouse'])
    args = parser.parse_args()
    validate_catalog(CATALOG)
    if args.action == 'selftest':
        import unittest
        sys.path.insert(0, str(SUPPORT))
        suite = unittest.defaultTestLoader.discover(str(SUPPORT), pattern='test_installer.py')
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 2
    engine = Engine()
    try:
        if args.action == 'install':
            engine.install()
        elif args.action == 'freeze':
            lock = engine.load_lock(); engine.verify(lock); path = engine.snapshot_release(lock)
            print('[PASS] Snapshot reproducible creado:', path)
        elif args.action == 'wheelhouse':
            lock = engine.load_lock(); engine.build_offline_wheelhouse(lock)
        else:
            lock = engine.load_lock()
            engine.invalidate()
            engine.verify(lock)
            engine.serve(lock, smoke=True, keep=args.action == 'launch')
        return 0
    except KeyboardInterrupt:
        print('\nSesion detenida por el usuario. Descargas parciales conservadas.')
        return 130
    except Exception as e:
        engine.invalidate()
        atomic_json(engine.report / 'BLOCKED.json', {'status': 'BLOCKED', 'error': str(e), 'traceback': traceback.format_exc()})
        print('\n[BLOCKED]', e, '\nInforme:', engine.report)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
