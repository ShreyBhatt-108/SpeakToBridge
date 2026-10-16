import tempfile
import unittest
from pathlib import Path

from scripts.trim_runtime import trim_runtime


class RuntimeTargetTests(unittest.TestCase):
    def test_all_supported_targets_retain_their_required_family(self):
        families = {'1100':'110x', '1101':'110x', '1102':'110x', '1103':'110x',
                    '1150':'115x', '1151':'115x', '1200':'12-0', '1201':'12-0'}
        names = set(families) | set(families.values())
        for target, family in families.items():
            with self.subTest(target=target), tempfile.TemporaryDirectory() as temporary:
                payload = Path(temporary)
                (payload/'SpeakToBridge.exe').touch()
                folder = payload/'_internal/torch/.kpack'
                folder.mkdir(parents=True)
                for name in names:
                    (folder/f'torch_gfx{name}.kpack').write_bytes(b'kernel')
                trim_runtime(payload, gpu_target='gfx'+target)
                self.assertEqual({p.name for p in folder.iterdir()},
                                 {f'torch_gfx{target}.kpack', f'torch_gfx{family}.kpack'})

    def test_universal_keeps_all_gpu_kernels(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = Path(temporary)
            (payload/'SpeakToBridge.exe').touch()
            folder = payload/'_internal/torch/.kpack'
            folder.mkdir(parents=True)
            kernel = folder/'torch_gfx1201.kpack'
            kernel.write_bytes(b'kernel')
            self.assertEqual(trim_runtime(payload)['removed_bytes'], 0)
            self.assertTrue(kernel.exists())

    def test_compact_target_preserves_matching_family_shared_dlls_and_unknown_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            payload = Path(temporary)
            (payload/'SpeakToBridge.exe').touch()
            internal = payload/'_internal'
            for folder in ('torch/.kpack', '_rocm_sdk_libraries/.kpack', '_rocm_sdk_libraries/bin'):
                (internal/folder).mkdir(parents=True)
            keep = ['torch/.kpack/torch_gfx1151.kpack', 'torch/.kpack/torch_gfx115x.kpack',
                    'torch/.kpack/future-format.kpack', '_rocm_sdk_libraries/.kpack/blas_lib_gfx1151.kpack',
                    '_rocm_sdk_libraries/bin/MIOpenCKGroupedConv_gfx1151.dll',
                    '_rocm_sdk_libraries/bin/amdhip64.dll', '_rocm_sdk_libraries/bin/LICENSE.txt']
            remove = ['torch/.kpack/torch_gfx110x.kpack', 'torch/.kpack/torch_gfx12-0.kpack',
                      '_rocm_sdk_libraries/.kpack/blas_lib_gfx1201.kpack',
                      '_rocm_sdk_libraries/bin/MIOpenCKGroupedConv_gfx1201.dll']
            for name in keep+remove:
                (internal/name).write_bytes(b'test data')
            report = trim_runtime(payload, gpu_target='gfx1151')
            self.assertEqual(report['removed_bytes'], 9*len(remove))
            self.assertTrue(all((internal/name).exists() for name in keep))
            self.assertTrue(all(not (internal/name).exists() for name in remove))
            self.assertEqual(trim_runtime(payload, gpu_target='gfx1151')['removed_bytes'], 0)
