"""Independent printed-cost and destination expectations detect wrong metadata."""
import unittest
from unittest.mock import patch
import test_stack_interaction_family as family


class StackInteractionOracle(unittest.TestCase):
    def test_wrong_printed_cost_is_detected(self):
        f=family.StackInteractionFamily();row=next(r for r in family.CONTRACTS if r['key']=='neutralize')
        s,host,original=f.setup_case(row);s.card_rules[row['cardId']]['powerCost']='{Y}'
        with patch.object(f,'setup_case',return_value=(s,host,original)):
            with self.assertRaises(AssertionError):f.check_cost(row)

    def test_wrong_return_destination_is_detected(self):
        f=family.StackInteractionFamily();row=next(r for r in family.CONTRACTS if r['key']=='veer')
        s,host,original=f.setup_case(row);s.card_rules[row['cardId']]['playedAbilities'][0]['result']['destination']='graveyard'
        with patch.object(f,'setup_case',return_value=(s,host,original)):
            with self.assertRaises(AssertionError):f.check_normal(row)
