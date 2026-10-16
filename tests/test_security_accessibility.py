import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from SpeakToBridge.accessibility import concise_status
from SpeakToBridge.amd_whisper import validate_model_metadata
from SpeakToBridge.app import SpeakToBridgeRuntime
from SpeakToBridge.model_storage import delete_cached_model, record_wsl_cached_model, list_cached_models
from SpeakToBridge.ui import SettingsWindow
from scripts.trim_runtime import trim_runtime


class SafeDeletionTests(unittest.TestCase):
    def test_only_requested_model_is_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            one=root/'models--Systran--faster-whisper-tiny';one.mkdir();(one/'model.bin').write_text('weights')
            other=root/'openai-whisper-small';other.mkdir();(other/'keep').write_text('keep')
            self.assertTrue(delete_cached_model(root,one.name))
            self.assertFalse(one.exists());self.assertTrue((other/'keep').exists())
            self.assertFalse(delete_cached_model(root,one.name))

    def test_traversal_absolute_and_invalid_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for name in ['../models--openai--whisper-tiny','openai-whisper-../..',r'C:\outside','openai-whisper-','openai-whisper-tiny/..']:
                with self.subTest(name=name),self.assertRaises(ValueError):
                    delete_cached_model(Path(temp),name)

    def test_junction_cannot_delete_cache_root_or_external_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'cache';root.mkdir()
            outside=Path(temp)/'outside';outside.mkdir();(outside/'keep').write_text('keep')
            for name,target in [('tiny',root),('small',outside)]:
                link=root/('openai-whisper-'+name)
                if os.name=='nt':
                    result=subprocess.run(['cmd.exe','/c','mklink','/J',str(link),str(target)],capture_output=True)
                    self.assertEqual(result.returncode,0,result.stderr)
                else:
                    link.symlink_to(target,target_is_directory=True)
                with self.assertRaises(ValueError):delete_cached_model(root,link.name)
            self.assertTrue((outside/'keep').exists());self.assertTrue(root.exists())

    def test_wsl_manifest_is_kept_when_worker_does_not_confirm(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);record_wsl_cached_model(root,dict(model_name='tiny',size_bytes=10,ready=True))
            with patch('SpeakToBridge.wsl_whisper.worker_command',return_value=['worker','--probe']),patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='{}',stderr='')):
                with self.assertRaises(RuntimeError):delete_cached_model(root,'wsl--openai-whisper-tiny')
            self.assertEqual(len(list_cached_models(root)),1)

    def test_wsl_confirmed_deletion_clears_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);record_wsl_cached_model(root,dict(model_name='tiny',size_bytes=10,ready=True))
            with patch('SpeakToBridge.wsl_whisper.worker_command',return_value=['worker','--probe']),patch('subprocess.run',return_value=SimpleNamespace(returncode=0,stdout='{"deleted":"tiny","removed":true}',stderr='')):
                self.assertTrue(delete_cached_model(root,'wsl--openai-whisper-tiny'))
            self.assertEqual(list_cached_models(root),[])

    def test_worker_deletes_both_gpu_layouts_without_loading_torch(self):
        import sys
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for folder in ['openai-whisper-tiny','models--openai--whisper-tiny']:
                path=root/folder;path.mkdir();(path/'weights').write_text('test')
            sentinel=root/'keep.txt';sentinel.write_text('keep')
            result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts'/'wsl_worker.py'),'--cache',str(root),'--delete-model','tiny'],capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(json.loads(result.stdout)['removed'])
            self.assertTrue(sentinel.exists())
            self.assertFalse((root/'openai-whisper-tiny').exists())
            self.assertFalse((root/'models--openai--whisper-tiny').exists())

    def test_delete_failure_restores_controls_and_reports_error(self):
        runtime=SimpleNamespace(_model_cache_delete_in_progress=True,_window=Mock(),_refresh_model_cache_list=Mock(),_on_error=Mock(),_set_status=Mock())
        SpeakToBridgeRuntime._finish_model_cache_delete(runtime,(False,'Access denied'))
        self.assertFalse(runtime._model_cache_delete_in_progress)
        runtime._window.set_model_cache_deleting.assert_called_once_with(False)
        runtime._on_error.assert_called_once()
        runtime._refresh_model_cache_list.assert_called_once()

    def test_all_selected_model_layouts_are_protected(self):
        for folder in ['models--Systran--faster-whisper-tiny','models--openai--whisper-tiny','openai-whisper-tiny','wsl--openai-whisper-tiny']:
            runtime=SimpleNamespace(_config=SimpleNamespace(model_name='tiny'),_controller=SimpleNamespace(is_preloading=False,is_busy=False,is_recording=False),_window=Mock(),_set_status=Mock(),_on_error=Mock())
            with patch('SpeakToBridge.app.delete_cached_model') as delete:
                SpeakToBridgeRuntime._on_model_cache_delete_requested(runtime,folder)
                delete.assert_not_called()
            self.assertIn('another model',runtime._set_status.call_args.args[0])

    def test_busy_recording_blocks_deletion(self):
        runtime=SimpleNamespace(_controller=SimpleNamespace(is_preloading=False,is_busy=False,is_recording=True),_set_status=Mock())
        with patch('SpeakToBridge.app.delete_cached_model') as delete:
            SpeakToBridgeRuntime._on_model_cache_delete_requested(runtime,'openai-whisper-small')
            delete.assert_not_called()

    def test_deletion_does_not_block_gui_thread(self):
        entered=threading.Event();release=threading.Event();finished=threading.Event()
        def remove(*args):entered.set();release.wait(2);return True
        runtime=SimpleNamespace(_config=SimpleNamespace(model_name='small'),_controller=SimpleNamespace(is_preloading=False,is_busy=False,is_recording=False),_window=Mock(),_set_status=Mock(),_on_error=Mock(),_model_cache_dir=Path('unused'),model_cache_delete_finished=Mock())
        runtime._delete_model_cache_worker=lambda folder:(SpeakToBridgeRuntime._delete_model_cache_worker(runtime,folder),finished.set())
        with patch('SpeakToBridge.app.delete_cached_model',side_effect=remove):
            try:
                started=time.perf_counter();SpeakToBridgeRuntime._on_model_cache_delete_requested(runtime,'openai-whisper-tiny')
                self.assertLess(time.perf_counter()-started,0.5);self.assertTrue(entered.wait(1));self.assertTrue(runtime._model_cache_delete_in_progress)
            finally:release.set();self.assertTrue(finished.wait(2))
        runtime.model_cache_delete_finished.emit.assert_called_once_with((True,''))


class AccessibleUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def window(self):return SettingsWindow('tiny','ctrl+win','ctrl+f8',300,False)

    def test_status_is_short_but_keeps_same_events_and_full_tooltip(self):
        window=self.window()
        full='Transcribing with AMD ROCm GPU: Radeon 8060S Graphics (FP16).'
        with patch('SpeakToBridge.ui.QAccessible.updateAccessibility') as events:
            window.set_status(full)
            self.assertEqual(events.call_count,2)
            self.assertEqual(events.call_args_list[-1].args[0].message(),'Transcribing on GPU.')
        self.assertEqual(window.status_value.toPlainText(),'Transcribing on GPU.')
        self.assertEqual(window.status_value.toolTip(),full)
        window.close()

    def test_recording_keeps_stop_hotkey_without_hardware_or_limit(self):
        full='Recording. Press CTRL+WIN again to stop and transcribe. Maximum length: 300 seconds. Processing: AMD ROCm GPU: Radeon 8060S (FP16).'
        self.assertEqual(concise_status(full),'Recording. CTRL+WIN to stop.')
        self.assertEqual(concise_status('GPU transcription failed. Retrying on CPU.'),'GPU failed. Retrying on CPU.')
        self.assertEqual(concise_status('Cannot open microphone. Check permissions.'),'Cannot open microphone. Check permissions.')

    def test_microphone_details_are_optional_and_keyboard_accessible(self):
        window=self.window();result=dict(quality=dict(assessment='Good recording level.',duration=6.5,rms_dbfs=-20,peak_dbfs=-5,clipping_percent=0),accuracy=95,expected='Expected words',transcript='Recognized words')
        window.set_microphone_test_result(result)
        self.assertNotIn('dBFS',window.microphone_test_result.toPlainText())
        window.microphone_details_checkbox.setChecked(True)
        self.assertIn('dBFS',window.microphone_test_result.toPlainText())
        self.assertIn('Recognized words',window.microphone_test_result.toPlainText());window.close()

    def test_word_bank_add_update_save_remove_round_trip(self):
        from SpeakToBridge.word_bank import WordBank
        with tempfile.TemporaryDirectory() as temp:
            bank=WordBank(Path(temp)/'word_bank.txt')
            window=self.window();window.set_word_bank_entries([])
            def save(entries):
                bank.save_entries(entries);window.set_word_bank_entries(bank.get_entries())
            window.word_bank_save_requested.connect(save)
            window.word_bank_heard_input.setText('sara');window.word_bank_correct_input.setText('Sarah')
            window._add_or_update_word_bank_entry()
            self.assertTrue(window.word_bank_save_button.isEnabled())
            window.word_bank_correct_input.setText('Sara');window._add_or_update_word_bank_entry()
            self.assertEqual(window.word_bank_list.count(),1)
            window._emit_word_bank_save_requested()
            self.assertFalse(window.word_bank_save_button.isEnabled())
            self.assertEqual(WordBank(Path(temp)/'word_bank.txt').apply('sara joined'),'Sara joined')
            window.word_bank_list.setCurrentRow(0);window._remove_selected_word_bank_entry()
            window._emit_word_bank_save_requested();self.assertEqual(bank.get_entries(),[]);window.close()

    def test_model_apply_and_more_settings_controls(self):
        window=self.window();receiver=Mock();window.model_apply_requested.connect(receiver)
        window.model_combo.setCurrentIndex(window.model_combo.findData('small'))
        window._emit_model_apply_requested();receiver.assert_called_once_with('small')
        before=window.is_advanced_settings_visible();window.toggle_advanced_settings()
        self.assertNotEqual(window.is_advanced_settings_visible(),before)
        window.toggle_advanced_settings();self.assertEqual(window.is_advanced_settings_visible(),before);window.close()

    def test_delete_confirmation_cancel_and_accept(self):
        window=self.window();window.set_model_cache_entries([('Tiny CPU','models--Systran--faster-whisper-tiny','tiny',True)])
        window.model_cache_list.setCurrentRow(0)
        receiver=Mock();window.model_cache_delete_requested.connect(receiver)
        with patch('SpeakToBridge.ui.QMessageBox.question',return_value=QMessageBox.StandardButton.Cancel):window._emit_model_cache_delete_requested()
        receiver.assert_not_called()
        with patch('SpeakToBridge.ui.QMessageBox.question',return_value=QMessageBox.StandardButton.Yes):window._emit_model_cache_delete_requested()
        receiver.assert_called_once_with('models--Systran--faster-whisper-tiny')
        window.set_model_cache_deleting(True);self.assertFalse(window.model_cache_delete_button.isEnabled())
        window.set_model_cache_deleting(False);self.assertTrue(window.model_cache_delete_button.isEnabled());window.close()


class ModelAndPackageSecurityTests(unittest.TestCase):
    def test_executable_model_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name in ['config.json','generation_config.json','tokenizer_config.json']:(root/name).write_text('{}')
            validate_model_metadata(root)
            for bad in [{'auto_map':{'Model':'evil.code'}},{'custom_generate':'evil/repo'},{'_attn_implementation_internal':'evil/repo'},{'chat_template':{'../outside':'content'}}]:
                (root/'config.json').write_text(json.dumps(bad))
                with self.assertRaises(ValueError):validate_model_metadata(root)

    def test_trim_keeps_runtime_dlls_models_licenses_and_kernels(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'SpeakToBridge.exe').write_bytes(b'exe')
            keep=['_internal/torch/lib/torch_hip.dll','_internal/torch/lib/kernel.hsaco','_internal/licenses/LICENSE','_internal/_rocm_sdk_core/lib/llvm/bin/runtime.dll']
            remove=['_internal/torch/include/header.h','_internal/torch/lib/link.lib','_internal/_rocm_sdk_core/lib/llvm/bin/clang.exe']
            for name in keep+remove:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'content')
            result=trim_runtime(root);self.assertGreater(result['removed_bytes'],0)
            for name in keep:self.assertTrue((root/name).exists())
            for name in remove:self.assertFalse((root/name).exists())
            self.assertEqual(trim_runtime(root)['removed_bytes'],0)
