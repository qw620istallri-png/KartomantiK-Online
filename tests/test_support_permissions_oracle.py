"""Verify the shared scenarios catch incorrect per-card permission metadata."""
import unittest
from unittest.mock import patch
import test_support_permissions as family


class SupportPermissionOracle(unittest.TestCase):
    def test_missing_hand_permission_is_detected(self):
        f = family.SupportPermissions()
        row = next(r for r in family.CONTRACTS if r['name'] == 'Wind Sprout')
        s, item = f.setup_card(row)
        s.card_rules[row['cardId']]['supportFromHand'] = False
        with patch.object(f, 'setup_card', return_value=(s, item)):
            with self.assertRaises(AssertionError): f.check_hand(row)

    def test_missing_interzone_permission_is_detected(self):
        f = family.SupportPermissions()
        row = next(r for r in family.CONTRACTS if r['name'] == 'Forest Guide')
        s, item = f.setup_card(row, 'interzone')
        s.card_rules[row['cardId']]['supportFromInterzone'] = False
        with patch.object(f, 'setup_card', return_value=(s, item)):
            with self.assertRaises(AssertionError): f.check_interzone(row)
