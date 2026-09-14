import json, tempfile, unittest
from pathlib import Path
import installer
class ProfileDefaultsTests(unittest.TestCase):
    EXPECTED={'DIAGNOSTIC':(512,512,20,7.0),'LITE':(640,640,20,6.0),'STANDARD':(896,896,24,6.0),'PREMIUM':(1024,1024,28,5.5),'PREMIUM_PLUS':(1024,1024,30,5.5),'WORKSTATION':(1024,1024,32,5.0)}
    def test_all_profiles_have_exact_presets(self):
        self.assertEqual(set(installer.PROFILE_UI_PRESETS),set(self.EXPECTED))
        for name,expected in self.EXPECTED.items():
            p=installer.canonical_profile_preset(name); self.assertEqual((p['width'],p['height'],p['steps'],p['cfg']),expected)
            self.assertEqual(p['sampler'],'DPM++ 2M'); self.assertEqual(p['scheduler'],'Automatic'); self.assertEqual(p['batch_count'],1); self.assertEqual(p['batch_size'],1); self.assertFalse(p['hires_fix'])
    def test_a1111_keys_for_premium(self):
        d=installer.a1111_ui_defaults('PREMIUM'); self.assertEqual(d['txt2img/Width/value'],1024); self.assertEqual(d['txt2img/Height/value'],1024); self.assertEqual(d['customscript/sampler.py/txt2img/Sampling steps/value'],28); self.assertEqual(d['txt2img/CFG Scale/value'],5.5)
    def test_windows_powershell_bom_profile_selection(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'PROFILE_SELECTION.json'; payload={'profile':'PREMIUM','ui_defaults':installer.canonical_profile_preset('PREMIUM')}; path.write_text(json.dumps(payload),encoding='utf-8-sig'); profile,preset=installer.read_profile_selection(path); self.assertEqual(profile,'PREMIUM'); self.assertEqual(preset['width'],1024); self.assertEqual(preset['steps'],28)
    def test_missing_selection_is_blocked_not_standard_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(installer.Blocked): installer.read_profile_selection(Path(td)/'missing.json')
    def test_invalid_profile_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'PROFILE_SELECTION.json'; path.write_text(json.dumps({'profile':'UNKNOWN'}),encoding='utf-8-sig')
            with self.assertRaises(installer.Blocked): installer.read_profile_selection(path)
    def test_cross_layer_drift_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'PROFILE_SELECTION.json'; p=installer.canonical_profile_preset('PREMIUM'); p['width']=896; path.write_text(json.dumps({'profile':'PREMIUM','ui_defaults':p}),encoding='utf-8-sig')
            with self.assertRaises(installer.Blocked): installer.read_profile_selection(path)
if __name__=='__main__': unittest.main()
