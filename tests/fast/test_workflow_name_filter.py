"""Literal workflow-name contract, including GitHub's documented '+' operator.

Reference:
https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onworkflow_runworkflows

This independent assertion helper intentionally supports ONLY literal names,
escaped '+' and '+' repeating its preceding literal character. It is not a
general implementation of GitHub glob matching. The production fix is YAML data.
"""
from pathlib import Path
import re
import unittest

import yaml

PRODUCER='Pinned Serena + Mago PoC'
ROOT=Path(__file__).resolve().parents[2]


def literal_plus_match(pattern, name):
    expression=[]
    index=0
    previous_literal=False
    while index < len(pattern):
        char=pattern[index]
        if char=='\\':
            index+=1
            if index >= len(pattern) or pattern[index] != '+':
                raise ValueError('Only escaped plus is supported by this narrow oracle')
            expression.append(r'\+')
            previous_literal=True
        elif char=='+':
            if not previous_literal:
                raise ValueError('Plus must follow one literal character')
            expression.append('+')
            previous_literal=False
        elif char in '*?[]{}!':
            raise ValueError('Other GitHub glob operators are outside this narrow oracle')
        else:
            expression.append(re.escape(char))
            previous_literal=True
        index+=1
    return re.fullmatch(''.join(expression),name) is not None


class WorkflowNameFilterTests(unittest.TestCase):
    def test_consumer_matches_literal_producer_name(self):
        workflow=yaml.load((ROOT/'.github/workflows/jev.yml').read_text(),Loader=yaml.BaseLoader)
        patterns=workflow['on']['workflow_run']['workflows']
        self.assertTrue(any(literal_plus_match(pattern,PRODUCER) for pattern in patterns),
                        f'workflow_run filter does not match literal producer name: {patterns}')

    def test_documented_positive_and_deliberate_old_fault_controls(self):
        old=PRODUCER
        fixed=r'Pinned Serena \+ Mago PoC'
        self.assertFalse(literal_plus_match(old,PRODUCER))
        self.assertTrue(literal_plus_match(old,'Pinned Serena  Mago PoC'))
        self.assertTrue(literal_plus_match(fixed,PRODUCER))
        self.assertFalse(literal_plus_match(fixed,'Pinned Serena  Mago PoC'))
        # The official documentation's literal-plus example supplies another
        # independent control rather than sharing only our project's name.
        self.assertTrue(literal_plus_match(r'Build C\+\+','Build C++'))

    def test_oracle_rejects_unsupported_glob_shapes(self):
        for pattern in ('Build*','Build?','[Build]','!Build','Build\\x'):
            with self.subTest(pattern=pattern),self.assertRaises(ValueError):
                literal_plus_match(pattern,'Build')


if __name__=='__main__':unittest.main()
