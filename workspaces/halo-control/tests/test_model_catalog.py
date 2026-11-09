from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import control
import model_catalog as catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.control = MagicMock()
        self.control.unit_state.side_effect = lambda kind: 'active' if kind == 'gateway' else 'inactive'
        self.control.config.return_value = {'model': 'flash-halogen'}
        self.control.inflight.return_value = 0
        self.control.containers.return_value = []
        self.value = {'available': True}

    def test_conflicting_selection_rejected_before_io(self):
        with self.assertRaises(ValueError):
            catalog.preflight(self.control, ['halogen', 'gufo'], self.value)
        self.control.http.assert_not_called()
        self.control.unit_state.assert_not_called()

    def test_preflight_rejects_busy_unknown_and_other_stacks(self):
        for names in (None, ['halostrix-comfyui-manual'], ['foreign']):
            self.control.containers.return_value = names
            with self.assertRaises(ValueError):
                catalog.preflight(self.control, ['gufo','laya'], self.value)
        self.control.containers.return_value = []
        self.control.inflight.return_value = 1
        with self.assertRaises(ValueError):
            catalog.preflight(self.control, ['halogen','laya'], self.value)
        self.control.inflight.return_value = 0
        self.control.unit_state.side_effect = lambda kind: 'active'
        with self.assertRaises(ValueError):
            catalog.preflight(self.control, ['laya'], self.value)
        self.control.http.assert_not_called()
        self.control.unit.assert_not_called()

    def test_retired_gufo_and_laya_selections_are_rejected(self):
        for action in ('catalog-gufo', 'catalog-laya', 'catalog-halogen-laya', 'catalog-gufo-laya'):
            with self.assertRaises(ValueError):
                catalog.launch(self.control, action)

    @unittest.skip('Gufo y Laya retirados del gateway (2026-11-09)')
    def test_both_supported_pairs_load_gpu_then_cpu(self):
        with patch.object(catalog, 'snapshot', return_value=self.value), patch.object(catalog.gufo, 'activate') as gufo:
            self.control.http.side_effect = [{'choices': [{}]}, {'status':'ok','device':'cpu'}]
            catalog.launch(self.control, 'catalog-halogen-laya')
            self.assertEqual(self.control.http.call_args_list[0].args[0], '/v1/chat/completions')
            self.assertEqual(self.control.http.call_args_list[1].args[0], '/upstream/laya/health')
            gufo.assert_not_called()
            self.control.http.reset_mock()
            self.control.http.side_effect = [{'status':'ok','device':'cpu'}]
            catalog.launch(self.control, 'catalog-gufo-laya')
            gufo.assert_called_once_with(self.control, catalog.engine_details, 'load', locked=True)
            self.control.http.assert_called_once_with('/upstream/laya/health', timeout=180)
        self.control.unit.assert_not_called()

    @unittest.skip('Gufo y Laya retirados del gateway (2026-11-09)')
    def test_partial_failure_is_explicit_and_does_not_unload_others(self):
        self.control.http.side_effect = [{'choices':[{}]}, OSError('private origin')]
        with patch.object(catalog, 'snapshot', return_value=self.value):
            with self.assertRaisesRegex(RuntimeError, 'puede quedar un modelo cargado') as caught:
                catalog.launch(self.control, 'catalog-halogen-laya')
        self.assertNotIn('private origin', str(caught.exception))
        self.control.unit.assert_not_called()
        self.assertEqual(self.control.http.call_count, 2)

    def test_unknown_catalog_fails_closed(self):
        with patch.object(catalog.engine_details, 'gateway_source', side_effect=ValueError('private path')):
            value = catalog.snapshot(self.control)
        self.assertFalse(value['available'])
        self.assertEqual(value['models'], [])
        self.assertNotIn('private path', value['reason'])

    def test_worker_dispatches_only_allowlisted_combinations(self):
        for action in catalog.SELECTIONS:
            self.assertIn(action, control.ACTIONS)
            with patch.object(catalog, 'launch') as launch:
                control.execute(action)
                launch.assert_called_once_with(control, action)
        with self.assertRaises(ValueError):
            control.execute('catalog-halogen-gufo')


if __name__ == '__main__':
    unittest.main()
