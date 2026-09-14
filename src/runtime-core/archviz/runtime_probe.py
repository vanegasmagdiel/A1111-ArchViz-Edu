"""Executed on Windows; failures must return nonzero."""
import importlib
from importlib import metadata
from pathlib import Path
import json, sys
result={'python':sys.version,'imports':{},'cuda_smoke':False,'errors':[]}
for name in ['numpy','torch','torchvision','cv2','mediapipe','google.protobuf','albumentations','controlnet_aux','safetensors','gradio']:
    try:
        mod=importlib.import_module(name); result['imports'][name]=getattr(mod,'__version__','import_ok')
    except Exception as e: result['errors'].append(name+': '+repr(e))
try:
    dists={}
    for project in ['opencv-contrib-python','opencv-python','opencv-python-headless']:
        dist=metadata.distribution(project); files=[str(x).replace('\\','/') for x in (dist.files or [])]
        dists[project]={'version':dist.version,'cv2_files':sum(x.startswith('cv2/') or '/cv2/' in x for x in files)}
    result['opencv_distributions']=dists
    assert dists['opencv-contrib-python']['version']=='4.10.0.84' and dists['opencv-contrib-python']['cv2_files']>0
    assert dists['opencv-python']['version']=='4.10.0.84+archviz1' and dists['opencv-python']['cv2_files']==0
    assert dists['opencv-python-headless']['version']=='4.10.0.84+archviz1' and dists['opencv-python-headless']['cv2_files']==0
except Exception as e: result['errors'].append('opencv provider: '+repr(e))
try:
    import torch
    assert torch.cuda.is_available(), 'CUDA no disponible'
    result['gpu']=torch.cuda.get_device_name(0); result['vram_gib']=torch.cuda.get_device_properties(0).total_memory/1024**3
    a=torch.randn((128,128),device='cuda'); b=a@a.T; assert torch.isfinite(b).all().item(); torch.cuda.synchronize(); result['cuda_smoke']=True
except Exception as e: result['errors'].append(repr(e))
print(json.dumps(result,indent=2)); raise SystemExit(0 if result['cuda_smoke'] and not result['errors'] else 2)
