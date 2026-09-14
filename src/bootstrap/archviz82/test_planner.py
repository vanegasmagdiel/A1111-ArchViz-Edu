import unittest
from planner import GPU, choose_compatibility, normalize_vendor, profile_for_vram, safe_reuse_state, unique_target_name

class PlannerTests(unittest.TestCase):
    def test_profiles(self):
        self.assertEqual(profile_for_vram(3.9), 'DIAGNOSTIC')
        self.assertEqual(profile_for_vram(4), 'LITE')
        self.assertEqual(profile_for_vram(8), 'STANDARD')
        self.assertEqual(profile_for_vram(12), 'PREMIUM')
        self.assertEqual(profile_for_vram(16), 'PREMIUM_PLUS')
        self.assertEqual(profile_for_vram(24), 'WORKSTATION')

    def test_nvidia_cuda(self):
        c = choose_compatibility([GPU('NVIDIA GeForce RTX 4080 Laptop', 'NVIDIA', 12, True)])
        self.assertEqual((c.backend, c.profile, c.install_enabled), ('CUDA_STABLE','PREMIUM',True))

    def test_nvidia_without_smi_not_assumed_cuda(self):
        c = choose_compatibility([GPU('NVIDIA GeForce RTX', 'NVIDIA', 12, False)])
        self.assertEqual(c.backend, 'CPU_FALLBACK')
        self.assertFalse(c.install_enabled)

    def test_amd_directml_is_not_silently_installed(self):
        c = choose_compatibility([GPU('AMD Radeon RX', 'AMD', 16, False)])
        self.assertEqual(c.backend, 'DIRECTML_COMPAT')
        self.assertFalse(c.install_enabled)

    def test_intel_directml(self):
        c = choose_compatibility([GPU('Intel Arc A770', 'Intel', 16, False)])
        self.assertEqual(c.backend, 'DIRECTML_COMPAT')

    def test_non_windows_x64(self):
        c = choose_compatibility([], windows_x64=False)
        self.assertEqual(c.backend, 'UNSUPPORTED')

    def test_vendor_normalization(self):
        self.assertEqual(normalize_vendor('GeForce RTX 4090'), 'NVIDIA')
        self.assertEqual(normalize_vendor('Radeon 7900 XTX'), 'AMD')
        self.assertEqual(normalize_vendor('Arc A770'), 'INTEL')

    def test_reuse_states(self):
        self.assertEqual(safe_reuse_state(True, True, False), 'VERIFIED')
        self.assertEqual(safe_reuse_state(True, True, True), 'VERIFIED_WITH_ASSET_DRIFT')
        self.assertEqual(safe_reuse_state(False, False, False), 'UNVERIFIED')
        self.assertEqual(safe_reuse_state(True, True, False, partial=True), 'PARTIAL')
        self.assertEqual(safe_reuse_state(True, True, False, corrupt=True), 'CORRUPT')

    def test_unique_target(self):
        self.assertEqual(unique_target_name('A1111_ArchViz_v8.2_A0', []), 'A1111_ArchViz_v8.2_A0')
        self.assertEqual(unique_target_name('A1111_ArchViz_v8.2_A0', ['A1111_ArchViz_v8.2_A0']), 'A1111_ArchViz_v8.2_A0-2')

if __name__ == '__main__':
    unittest.main(verbosity=2)
