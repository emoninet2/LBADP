import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import util


class ImportTests(unittest.TestCase):
    def test_incremental_import(self):
        with tempfile.TemporaryDirectory() as folder:
            csv = Path(folder) / 'input.csv'
            out = Path(folder) / 'data.json'
            csv.write_text('jumpNumber,data(feet)\n35,100 50 0\n36,200 100 0\n')
            initial = util.convert_csv_to_json(csv, out)
            self.assertEqual(list(initial[0])[-1], 'data(feet)')
            self.assertTrue(all(k in initial[0] for k in util.METADATA_FIELDS))
            before, modified = out.read_bytes(), out.stat().st_mtime_ns
            with patch('builtins.input', side_effect=AssertionError('Unexpected prompt')):
                util.convert_csv_to_json(csv, out)
            self.assertEqual((out.read_bytes(), out.stat().st_mtime_ns), (before, modified))
            initial[0]['dropzone'] = 'Saved DZ'
            initial[0]['customField'] = 'keep'
            out.write_text(json.dumps(initial))
            csv.write_text('jumpNumber,data(feet)\n35,100 50 0\n37,300 150 0\n')
            rows = util.convert_csv_to_json(csv, out)
            self.assertEqual([r['jumpNumber'] for r in rows], [35, 36, 37])
            self.assertEqual(rows[0]['dropzone'], 'Saved DZ')
            self.assertEqual(rows[0]['customField'], 'keep')
            csv.write_text('jumpNumber,data(feet),dropzone\n35,100 40 0,New DZ\n')
            before, modified = out.read_bytes(), out.stat().st_mtime_ns
            with patch('builtins.input', return_value='skip'):
                util.convert_csv_to_json(csv, out)
            self.assertEqual((out.read_bytes(), out.stat().st_mtime_ns), (before, modified))
            with patch('builtins.input', side_effect=EOFError):
                util.convert_csv_to_json(csv, out)
            self.assertEqual(out.read_bytes(), before)
            with patch('builtins.input', side_effect=['invalid', 'overwrite']):
                rows = util.convert_csv_to_json(csv, out)
            self.assertEqual(rows[0]['data(feet)'], [100, 40, 0])
            self.assertEqual(rows[0]['dropzone'], 'New DZ')
            self.assertEqual(rows[0]['customField'], 'keep')
            self.assertEqual(len(rows), 3)
            self.assertEqual(list(rows[0])[-1], 'data(feet)')
            csv.write_text('jumpNumber,data(feet)\n35,100 30 0\n')
            with patch('builtins.input', return_value='overwrite'):
                rows = util.convert_csv_to_json(csv, out)
            self.assertEqual(rows[0]['dropzone'], 'New DZ')
            before = out.read_bytes()
            csv.write_text('jumpNumber,data(feet)\n35,100 30 0\n35,100 30 0\n')
            with self.assertRaises(ValueError):
                util.convert_csv_to_json(csv, out)
            self.assertEqual(out.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
