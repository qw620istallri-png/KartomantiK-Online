"""Wrong encoded bonuses and caps must fail the independent literal oracles."""
import unittest
from unittest.mock import patch
import test_continuous_power_family as family


class ContinuousPowerOracle(unittest.TestCase):
    def test_wrong_aura_value_is_detected(self):
        f = family.ContinuousPowerFamily()
        row = next(r for r in family.CONTRACTS if r['key'] == 'herbaceous')
        s, host, target = f.setup_case(row)
        s.card_rules[row['cardId']]['continuousPowerRules'][0]['value'] = 2
        with patch.object(f, 'setup_case', return_value=(s, host, target)):
            with self.assertRaises(AssertionError): f.check_baseline(row)

    def test_wrong_bonus_cap_is_detected(self):
        f = family.ContinuousPowerFamily()
        row = next(r for r in family.CONTRACTS if r['key'] == 'kazadur')
        s, host, target = f.setup_case(row)
        s.card_rules[row['cardId']]['continuousPowerRules'][0]['cap'] = 2
        with patch.object(f, 'setup_case', return_value=(s, host, target)):
            with self.assertRaises(AssertionError): f.check_baseline(row)
