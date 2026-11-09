import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import storage
import control


class StorageTests(unittest.TestCase):
    def test_parser_handles_newlines_and_rejects_outside_root(self):
        rows = storage.parse_usage('100\t/fixture\0' + '50\t/fixture/models\0' + '10\t/fixture/odd\nname\0' + '900\t/other\0', Path('/fixture'))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]['category'], 'Modelos y caché de Hugging Face')
        self.assertEqual(rows[2]['path'], '/fixture/odd\nname')

    def test_real_scan_does_not_follow_symlink_or_read_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'scan'
            target.mkdir()
            (target / 'models').mkdir()
            (target / 'models/weights').write_bytes(b'x' * 8192)
            (target / 'external').symlink_to('/usr', target_is_directory=True)
            report = storage.scan_root('fixture', target, root)
            self.assertFalse(report['partial'])
            self.assertGreaterEqual(report['bytes'], 8192)
            self.assertFalse(any('external/' in row['path'] for row in report['directories']))
            self.assertEqual((target / 'models/weights').read_bytes(), b'x' * 8192)

    def test_timeout_and_permission_errors_are_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(storage.subprocess, 'run', side_effect=subprocess.TimeoutExpired('du', 1)):
                self.assertTrue(storage.scan_root('fixture', root, root)['partial'])
            with patch.object(storage.subprocess, 'run', return_value=Mock(returncode=1)):
                self.assertIsNone(storage.scan_root('fixture', root, root)['bytes'])

    def test_docker_unavailable_not_zero(self):
        with patch.object(storage.subprocess, 'run', return_value=Mock(returncode=1)):
            self.assertFalse(storage.docker_usage()['available'])
        with patch.object(storage.subprocess, 'run', return_value=Mock(returncode=0, stdout=json.dumps({'Type': 'Images', 'Size': '100GB', 'secret': 'not exported'}))):
            self.assertNotIn('secret', storage.docker_usage()['rows'][0])

    def test_analysis_job_only_caches_report(self):
        with patch.object(storage, 'analyze', return_value={'roots': []}), patch.object(control, 'save_cache') as save, patch.object(control, 'unit') as unit:
            control.execute('analyze-storage')
        save.assert_called_once_with('storage', {'roots': []})
        unit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
