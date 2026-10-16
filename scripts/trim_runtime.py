"""Remove build-only SDK tools from a frozen inference application."""
from __future__ import annotations
import argparse
import json
import shutil
import re
from pathlib import Path


GPU_FAMILIES = {"gfx1100": "110x", "gfx1101": "110x", "gfx1102": "110x", "gfx1103": "110x", "gfx1150": "115x", "gfx1151": "115x", "gfx1200": "12-0", "gfx1201": "12-0"}

def trim_runtime(payload: Path, dry_run: bool = False, gpu_target: str = "all") -> dict:
    if gpu_target != "all" and gpu_target not in GPU_FAMILIES:
        raise ValueError('Unsupported GPU trim target')
    payload = payload.resolve(strict=True)
    internal = payload / '_internal'
    if (not (payload / 'SpeakToBridge.exe').is_file() or not internal.is_dir()
            or internal.is_symlink() or internal.is_junction() or internal.resolve().parent != payload):
        raise ValueError('Expected a frozen SpeakToBridge payload')
    candidates = [internal / 'torch' / 'include', internal / '_rocm_sdk_core' / 'include']
    candidates += list((internal / 'torch' / 'lib').glob('*.lib'))
    candidates += list((internal / '_rocm_sdk_core' / 'lib' / 'llvm' / 'bin').glob('*.exe'))
    if gpu_target != "all":
        keep_targets = {gpu_target.removeprefix('gfx'), GPU_FAMILIES[gpu_target]}
        # Only these vendor kernel containers and named MIOpen device DLLs are
        # architecture-specific. Shared DLLs and compiler/runtime resources stay.
        for folder in (internal / 'torch' / '.kpack', internal / '_rocm_sdk_libraries' / '.kpack'):
            for path in folder.glob('*.kpack'):
                match = re.search(r'gfx([0-9xX-]+)\.kpack$', path.name)
                if match and match.group(1).lower() not in keep_targets:
                    candidates.append(path)
        for path in (internal / '_rocm_sdk_libraries' / 'bin').glob('MIOpenCK*gfx*.dll'):
            match = re.search(r'gfx([0-9xX-]+)\.dll$', path.name)
            if match and match.group(1).lower() not in keep_targets:
                candidates.append(path)
    removed = []
    for path in candidates:
        if not path.exists():
            continue
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(internal.resolve()) or path.is_symlink() or path.is_junction():
            raise ValueError('Unsafe payload trim path')
        size = sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) if path.is_dir() else path.stat().st_size
        removed.append({'path':str(path.relative_to(payload)), 'bytes':size})
        if not dry_run:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    return {'removed_bytes':sum(item['bytes'] for item in removed), 'entries':removed, 'dry_run':dry_run}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('payload', type=Path)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--gpu-target', choices=('all',*GPU_FAMILIES), default='all')
    args=parser.parse_args()
    result=trim_runtime(args.payload,args.dry_run,args.gpu_target)
    if args.report:
        args.report.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Build-only files removed:', result['removed_bytes'], 'bytes')
