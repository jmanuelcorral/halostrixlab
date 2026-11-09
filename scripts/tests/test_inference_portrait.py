import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'workspaces/inference'))
import portrait_workflow as portrait


class PortraitTests(unittest.TestCase):
    def test_links_are_bidirectional_and_typed(self):
        workflow = portrait.build()
        nodes = {node['id']: node for node in workflow['nodes']}
        self.assertEqual(len(nodes), len(workflow['nodes']))
        links = {link[0]: link for link in workflow['links']}
        for identifier, source, output, target, input_slot, datatype in workflow['links']:
            self.assertIn(identifier, nodes[source]['outputs'][output]['links'])
            self.assertEqual(nodes[target]['inputs'][input_slot]['link'], identifier)
            self.assertEqual(nodes[source]['outputs'][output]['type'], datatype)
            self.assertEqual(nodes[target]['inputs'][input_slot]['type'], datatype)
            self.assertLess(nodes[source]['order'], nodes[target]['order'])
        for node in nodes.values():
            for input_value in node['inputs']:
                self.assertIn(input_value['link'], links)

    def test_single_reference_reaches_conditioning_and_latent(self):
        workflow = portrait.build()
        nodes = {node['id']: node for node in workflow['nodes']}
        self.assertEqual([node['id'] for node in nodes.values() if node['type'] == 'LoadImage'], [7])
        self.assertEqual(nodes[7]['widgets_values'][0], '')
        targets = {link[3] for link in workflow['links'] if link[1] == 8}
        self.assertEqual(targets, {9, 10, 11})
        self.assertEqual(nodes[8]['widgets_values'], ['lanczos', 1.0, 32])
        self.assertEqual(nodes[12]['widgets_values'], [42, 'fixed', 4, 1.0, 'euler', 'simple', 1.0])
        self.assertIn('edit_2511', nodes[1]['widgets_values'][0])
        self.assertIn('Edit-2511', nodes[2]['widgets_values'][0])
        self.assertEqual(nodes[14]['widgets_values'], ['retratos/profesional'])
        self.assertNotIn('2512', json.dumps(workflow))

    def test_multiple_references_condition_both_branches_not_initial_latent(self):
        for count in (2, 3):
            workflow = portrait.build(count)
            nodes = {node['id']: node for node in workflow['nodes']}
            self.assertEqual(sum(node['type'] == 'LoadImage' for node in nodes.values()), count)
            for identifier in (9, 10):
                references = [value for value in nodes[identifier]['inputs'] if value['name'].startswith('image')]
                self.assertEqual(len(references), count)
                self.assertTrue(all(value['link'] is not None for value in references))
            self.assertEqual([link[1] for link in workflow['links'] if link[3] == 11 and link[4] == 0], [8])
            self.assertIn('blue-gray', nodes[9]['widgets_values'][0])
            self.assertIn('image 1 only', nodes[9]['widgets_values'][0])
            for identifier, source, output, target, input_slot, datatype in workflow['links']:
                self.assertLess(nodes[source]['order'], nodes[target]['order'])
                self.assertIn(identifier, nodes[source]['outputs'][output]['links'])
                self.assertEqual(nodes[target]['inputs'][input_slot]['link'], identifier)
                self.assertEqual(nodes[target]['inputs'][input_slot]['type'], datatype)
            self.assertTrue(all(node['widgets_values'][0] == '' for node in nodes.values() if node['type'] == 'LoadImage'))
        for invalid in (0, 4, True, '3'):
            with self.assertRaises(ValueError):
                portrait.build(invalid)

    def test_new_versions_preserve_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'user').mkdir(mode=0o700)
            directory = root / 'user/default/workflows'
            directory.mkdir(parents=True)
            original = directory / portrait.NAME
            original.write_text('my modified workflow')
            with patch.object(portrait.comfyui, 'STORAGE', root):
                portrait.install(2)
                portrait.install(3)
                portrait.install(3)
            self.assertEqual(original.read_text(), 'my modified workflow')
            self.assertEqual(len(list(directory.glob('*.json'))), 3)

    def test_download_integrity_rejects_truncation_changes_and_symlinks(self):
        import hashlib
        import download_portrait_models as downloader
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'weights'
            path.write_bytes(b'fixture')
            artifact = {'size': 7, 'sha256': hashlib.sha256(b'fixture').hexdigest()}
            downloader.verify(path, artifact)
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                downloader.verify(path, artifact)
            path.write_bytes(b'bad')
            with self.assertRaises(ValueError):
                downloader.verify(path, artifact)
            link = Path(temporary) / 'link'
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                downloader.verify(link, artifact)

    def test_install_preserves_existing_user_workflow(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            user = root / 'user'
            user.mkdir(mode=0o700)
            directory = user / 'default' / 'workflows'
            directory.mkdir(parents=True)
            with patch.object(portrait.comfyui, 'STORAGE', root):
                portrait.install()
                portrait.install()
                destination = directory / portrait.NAME
                self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
                destination.write_text('user changes')
                with self.assertRaises(ValueError):
                    portrait.install()
                self.assertEqual(destination.read_text(), 'user changes')


if __name__ == '__main__':
    unittest.main()
