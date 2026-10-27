"""Exercise the real transport state machine; stub only the process boundary."""
from pathlib import Path
import os
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'adapter/src'))
from serena_mago.server import MagoTransport
from solidlsp.ls_process import StdioLanguageServer


def transport():
    value = MagoTransport.__new__(MagoTransport)
    value.owner = SimpleNamespace(open_file_buffers={})
    value.documents = {}
    value.document_versions = {}
    value._state_lock = threading.RLock()
    value._state_trace_bytes = 0
    value._state_trace_truncated = False
    return value


class DocumentState(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)/'Target.php'
        self.path.write_text('éé target')
        self.uri = self.path.as_uri()
        self.value = transport()
        self.sent = []
        self.patch = patch.object(StdioLanguageServer,'send_notification',lambda _,m,p=None:self.sent.append((m,p)))
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def notify(self,method,**params):
        self.value.send_notification(method,params)

    def open(self,text='éé target'):
        self.notify('textDocument/didOpen',textDocument={'uri':self.uri,'text':text,'version':1})

    def close(self):
        self.notify('textDocument/didClose',textDocument={'uri':self.uri})

    def watched(self,kind=2):
        self.notify('workspace/didChangeWatchedFiles',changes=[{'uri':self.uri,'type':kind}])

    def test_closed_external_nonbmp_regression_and_stale_mutant(self):
        self.open()
        self.close()
        self.path.write_text('🧪 target')
        self.watched()
        self.assertNotIn(self.uri,self.value.documents)
        wire={'uri':self.uri,'range':{'start':{'line':0,'character':3},'end':{'line':0,'character':9}}}
        self.assertEqual(self.value.convert(wire)['range']['start']['character'],2)
        # Reintroduce the reviewed didClose invalidation fault, then detect it.
        self.value.documents[self.uri]='éé target'
        self.assertNotEqual(self.value.convert(wire)['range']['start']['character'],2)
        self.value.documents.clear()
        self.assertEqual(self.value.convert(wire)['range']['start']['character'],2)

    def test_open_transmitted_buffer_wins_over_external_change_and_delete(self):
        self.open('🧪 target')
        self.path.write_text('disk replacement')
        self.watched()
        self.assertEqual(self.value.text(self.uri),'🧪 target')
        self.path.unlink()
        self.watched(3)
        self.assertEqual(self.value.text(self.uri),'🧪 target')
        self.close()
        with self.assertRaises(FileNotFoundError):
            self.value.text(self.uri)

    def test_creation_replacement_deletion_no_mtime_cache(self):
        self.open()
        self.close()
        self.path.unlink()
        self.watched(3)
        with self.assertRaises(FileNotFoundError):
            self.value.text(self.uri)
        self.path.write_text('created🧪')
        self.watched(1)
        self.assertEqual(self.value.text(self.uri),'created🧪')
        replacement=self.path.with_suffix('.replacement')
        replacement.write_text('replaced😀')
        os.utime(replacement,(1,1))
        replacement.replace(self.path)
        self.watched()
        self.assertEqual(self.value.text(self.uri),'replaced😀')
        # Even without watcher notification closed files are freshly read.
        self.path.write_text('unannounced')
        self.assertEqual(self.value.text(self.uri),'unannounced')

    def test_full_sync_bridge_and_versions(self):
        self.open()
        self.value.owner.open_file_buffers[self.uri]=SimpleNamespace(contents='🧪 renamed')
        self.notify('textDocument/didChange',textDocument={'uri':self.uri,'version':2},
                    contentChanges=[{'range':{'start':{'line':0,'character':3},'end':{'line':0,'character':9}},'text':'renamed'}])
        self.assertEqual(self.sent[-1][1]['contentChanges'],[{'text':'🧪 renamed'}])
        self.assertEqual(self.value.documents[self.uri],'🧪 renamed')
        self.assertEqual(self.value.document_versions[self.uri],2)
        self.close()
        self.assertNotIn(self.uri,self.value.document_versions)

    def test_duplicate_open_and_stale_change_cannot_poison_accepted_text(self):
        self.open()
        with self.assertRaises(ValueError):
            self.open('poisoned')
        with self.assertRaises(ValueError):
            self.notify('textDocument/didChange',textDocument={'uri':self.uri,'version':1},contentChanges=[{'text':'poisoned'}])
        self.assertEqual(self.value.text(self.uri),'éé target')
        self.close()
        with self.assertRaises(ValueError):
            self.notify('textDocument/didChange',textDocument={'uri':self.uri,'version':2},contentChanges=[{'text':'poisoned'}])
        self.assertNotIn(self.uri,self.value.documents)

    def test_location_link_origin_and_target_use_different_documents(self):
        other=self.path.with_name('Caller.php')
        other.write_text('🧪🧪 target')
        self.path.write_text('é🧪 target')
        target={'line':0,'character':4}
        origin={'line':0,'character':5}
        value={'targetUri':self.uri,'targetRange':{'start':target,'end':target},
               'originSelectionRange':{'start':origin,'end':origin}}
        result=self.value.convert(value,other.as_uri())
        self.assertEqual(result['targetRange']['start']['character'],3)
        self.assertEqual(result['originSelectionRange']['start']['character'],3)

    def test_restart_and_stop_clear_state_even_if_stop_fails(self):
        self.open()
        with patch.object(StdioLanguageServer,'start',return_value=None):
            self.value.start()
        self.assertEqual(self.value.documents,{})
        self.assertEqual(self.value.document_versions,{})
        self.open()
        with patch.object(StdioLanguageServer,'stop',side_effect=RuntimeError('injected')):
            with self.assertRaises(RuntimeError):
                self.value.stop()
        self.assertEqual(self.value.documents,{})
        self.assertEqual(self.value.document_versions,{})

    def test_conversion_takes_one_snapshot_per_uri(self):
        with patch.object(self.value,'text',side_effect=['🧪 target','stale'] ) as reader:
            result=self.value.convert({'uri':self.uri,'range':{'start':{'line':0,'character':3},'end':{'line':0,'character':9}}})
        self.assertEqual(reader.call_count,1)
        self.assertEqual(result['range'],{'start':{'line':0,'character':2},'end':{'line':0,'character':8}})

    def test_disk_newlines_normalize_but_wire_buffer_preserves_text(self):
        self.path.write_bytes('a\r\né🧪\rx\n'.encode())
        self.assertEqual(self.value.text(self.uri),'a\né🧪\nx\n')
        self.open('a\r\né🧪\rx\n')
        self.assertEqual(self.value.text(self.uri),'a\r\né🧪\rx\n')
        self.assertEqual(self.value.convert({'line':1,'character':3},self.uri),{'line':1,'character':2})


if __name__ == '__main__':
    unittest.main()
