"""Sensitivity checks for independent effect, cost and recipient expectations."""
import unittest
from unittest.mock import patch
import test_protection_keyword_family as family


class ProtectionKeywordOracle(unittest.TestCase):
    def test_wrong_jaw_power_is_detected(self):
        f=family.ProtectionKeywordFamily();row=next(r for r in family.CONTRACTS if r['key']=='jaw')
        s,host,target,other=f.setup_case(row)
        s.card_rules[row['cardId']]['triggeredAbilities'][0]['ongoingEffect']['value']=-1
        with patch.object(f,'setup_case',return_value=(s,host,target,other)):
            with self.assertRaises(AssertionError):f.check_link_entry(row)

    def test_wrong_protect_duration_is_detected(self):
        f=family.ProtectionKeywordFamily();row=next(r for r in family.CONTRACTS if r['key']=='protect')
        s,host,target,other=f.setup_case(row)
        s.card_rules[row['cardId']]['playedAbilities'][0]['ongoingEffect']['duration']='until_end_of_next_turn'
        with patch.object(f,'setup_case',return_value=(s,host,target,other)):
            with self.assertRaises(AssertionError):f.check_grant_lifetime(row)
