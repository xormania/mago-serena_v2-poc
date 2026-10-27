"""Seeded position/edit properties with an index-scanning independent oracle.

Only CR, LF, CRLF are line separators. Unicode NEL/LS/PS remain characters.
No newline normalization occurs at the transport boundary; disk reads use
Python universal newlines and Serena writes normalize to configured native LF.
"""
import itertools
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'adapter/src'))
from serena_mago.server import convert_character
from solidlsp.ls_utils import TextUtils


def oracle_positions(text):
    """Scan code points, counting astral characters as two wire units."""
    index = line = column = units = 0
    result = []
    while True:
        result.append((index,line,column,units))
        if index == len(text):
            return result
        char = text[index]
        if char in '\r\n':
            if char == '\r' and text[index:index+2] == '\r\n':
                index += 1
            line += 1
            column = units = 0
        else:
            column += 1
            units += 1 + (ord(char)>0xffff)
        index += 1


class PositionProperties(unittest.TestCase):
    def texts(self):
        for ending,first,second,trailing in itertools.product(('\n','\r\n','\r'),('', 'ASCII', 'é漢', 'x🧪y', '\u0085\u2028\u2029'),('', 'a😀é'),('', '\n')):
            yield first + ending + second + trailing
        randomizer = random.Random(41729)
        alphabet = ['a','Z','é','漢','🧪','😀','\u0085','\u2028','\u2029','\n','\r','\r\n']
        yield ''
        for _ in range(100):
            yield ''.join(randomizer.choice(alphabet) for _ in range(randomizer.randrange(30)))

    def assert_conversion(self, converter, text, line, column, units):
        self.assertEqual(converter(text,line,column,wire=True),units)
        self.assertEqual(converter(text,line,units),column)

    def test_all_valid_positions_and_edit_results(self):
        count = 0
        for text in self.texts():
            positions = oracle_positions(text)
            for index,line,column,units in positions:
                with self.subTest(text=text,index=index):
                    self.assert_conversion(convert_character,text,line,column,units)
                    self.assertEqual(TextUtils.get_index_from_line_col(text,line,column),index)
                    self.assertEqual(TextUtils.get_line_col_from_index(text,index),(line,column))
                    inserted = 'é😀\r\nQ'
                    actual,l,c = TextUtils.insert_text_at_position(text,line,column,inserted)
                    expected = text[:index]+inserted+text[index:]
                    self.assertEqual(actual,expected)
                    expected_cursor = next(x for x in oracle_positions(expected) if x[0] == index+len(inserted))
                    self.assertEqual((l,c),expected_cursor[1:3])
                    # Choose a second valid endpoint and independently slice bytes/text.
                    endpoint = positions[min(len(positions)-1,positions.index((index,line,column,units))+3)]
                    removed,deleted = TextUtils.delete_text_between_positions(text,line,column,endpoint[1],endpoint[2])
                    self.assertEqual(removed,text[:index]+text[endpoint[0]:])
                    self.assertEqual(deleted,text[index:endpoint[0]])
                    count += 1
        self.assertGreater(count,1000)

    def test_workspace_edit_ranges_use_same_independent_oracle(self):
        from test_document_state import transport
        value = transport()
        uri = 'file:///example.php'
        for text in self.texts():
            value.documents[uri] = text
            positions = oracle_positions(text)
            for start,end in zip(positions,positions[1:]):
                edit = {'documentChanges':[{'textDocument':{'uri':uri,'version':3},'edits':[{
                    'range':{'start':{'line':start[1],'character':start[3]},
                             'end':{'line':end[1],'character':end[3]}},'newText':'REPLACED😀'}]}]}
                translated = value.convert(edit)['documentChanges'][0]['edits'][0]
                actual_start = TextUtils.get_index_from_line_col(text,**{'line':translated['range']['start']['line'],'col':translated['range']['start']['character']})
                actual_end = TextUtils.get_index_from_line_col(text,**{'line':translated['range']['end']['line'],'col':translated['range']['end']['character']})
                self.assertEqual(text[:actual_start]+translated['newText']+text[actual_end:],text[:start[0]]+'REPLACED😀'+text[end[0]:])

    def test_deliberate_faults_are_detected_with_healthy_controls(self):
        def identity(text,line,column,wire=False):
            return column

        def reviewed_lf_only(text,line,column,wire=False):
            current=text.split('\n')[line]
            if wire:
                return len(current[:column].encode('utf-16-le'))//2
            return len(current.encode('utf-16-le')[:column*2].decode('utf-16-le'))

        def off_by_one(text,line,column,wire=False):
            return convert_character(text,line,column,wire=wire)+1

        samples=[('é🧪target',0,3,4),('x\ry🧪target',1,3,4),
                 ('a\u2028🧪target',0,3,4),('',0,0,0)]
        for sample in samples:
            self.assert_conversion(convert_character,*sample)
        for faulty,sample,error in [(identity,samples[0],AssertionError),
                                    (reviewed_lf_only,samples[1],IndexError),
                                    (off_by_one,samples[0],AssertionError)]:
            with self.subTest(mutant=faulty.__name__):
                with self.assertRaises(error):
                    self.assert_conversion(faulty,*sample)
        # The same complete WorkspaceEdit property must reject an identity
        # converter, because its resulting edited text differs from slicing.
        from unittest.mock import patch
        with patch('serena_mago.server.convert_character',identity):
            with self.assertRaises(AssertionError):
                self.test_workspace_edit_ranges_use_same_independent_oracle()
        self.test_workspace_edit_ranges_use_same_independent_oracle()

    def test_invalid_positions_and_eol_clamp(self):
        for line,col in [(-1,0),(0,-1),(True,0),(0,False),(2,0)]:
            with self.assertRaises(ValueError):
                convert_character('a\n',line,col)
        with self.assertRaises(UnicodeDecodeError):
            convert_character('🧪',0,1)
        self.assertEqual(convert_character('🧪',0,900),1)
        self.assertEqual(convert_character('🧪',0,900,wire=True),2)


if __name__ == '__main__':
    unittest.main()
