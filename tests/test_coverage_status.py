"""Coverage accounting is explicit, deduplicated and tied to real executions."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from card_coverage_status import collect_selected_cards


class CoverageStatus(unittest.TestCase):
    def test_duplicate_clauses_and_reports_count_the_card_once(self):
        doc={'clauses':[{'cardId':'a','testIds':['one'],'printedParagraph':'First.'},
                        {'cardId':'a','testIds':['two'],'printedParagraph':'Second.'}]}
        cards,excluded=collect_selected_cards([('x',doc),('y',doc)],{'one':'pass','two':'pass'},
            {'a':{'name':'A','effect':'First.\nSecond.'}})
        self.assertEqual(len(cards),1)
        self.assertEqual(len(cards[0]['proofs']),4)
        self.assertFalse(cards[0]['allBranchesCertified'])
        self.assertEqual(excluded,[])

    def test_interaction_only_cards_and_failed_or_missing_tests_are_not_counted(self):
        doc={'cards':[{'cardId':'a'}, {'cardId':'b','testIds':['failed']}, {'cardId':'c','testIds':['absent']}]}
        catalog={c:{'name':c,'effect':'Text.'} for c in 'abc'}
        cards,excluded=collect_selected_cards([('x',doc)],{'failed':'fail'},catalog)
        self.assertEqual(cards,[])
        self.assertEqual(len(excluded),2)

    def test_changed_printed_text_requires_review_even_with_passing_tests(self):
        cards,excluded=collect_selected_cards([('x',{'clauses':[{'cardId':'a','testIds':['ok'],'printedParagraph':'Old.'}]})],
            {'ok':'pass'},{'a':{'name':'A','effect':'New.'}})
        self.assertEqual(cards,[])
        self.assertEqual(excluded[0]['reason'],'printed text changed; needs review')

    def test_a_report_with_failures_cannot_add_covered_cards(self):
        cards,excluded=collect_selected_cards([('x',{'summary':{'failed':1},'clauses':[{'cardId':'a','testIds':['ok']}]})],
            {'ok':'pass'},{'a':{'name':'A','effect':'Text.'}})
        self.assertEqual(cards,[])
        self.assertEqual(len(excluded),1)
