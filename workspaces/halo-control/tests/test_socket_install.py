from pathlib import Path
import subprocess
import unittest


class SocketInstallTests(unittest.TestCase):
    def test_installer_keeps_private_binding_and_allows_late_address(self):
        path = Path(__file__).resolve().parents[1] / 'install-system.sh'
        source = path.read_text()
        self.assertIn('ListenStream=%s:9090\\nFreeBind=yes\\n', source)
        self.assertNotIn('ListenStream=0.0.0.0', source)
        self.assertIn('Cockpit socket override already exists', source)
        subprocess.run(['bash', '-n', str(path)], check=True)


if __name__ == '__main__':
    unittest.main()
