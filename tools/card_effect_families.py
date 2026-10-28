"""Validate hand-authored effect oracles without deriving them from ability code."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_power_contracts():
    import main
    manifest = json.loads((ROOT / 'audit/power-family.json').read_text(encoding='utf-8'))
    assert manifest['schemaVersion'] == 1 and manifest['family'] == 'fixed-power-change'
    catalog = {c['id']: c for c in main.CARD_DATA}
    keys = set()
    for row in manifest['contracts']:
        assert row['key'] not in keys, 'Duplicate contract key'
        keys.add(row['key'])
        card = catalog[row['cardId']]
        assert row['name'] == card['name']
        assert row['printedText'] == card['effect'], 'Printed text needs an independent re-review'
        assert row['printedTextSha256'] == hashlib.sha256(card['effect'].encode()).hexdigest()
        paragraphs = [p.strip() for p in card['effect'].splitlines() if p.strip()]
        assert paragraphs[row['paragraphIndex']] == row['printedParagraph']
        assert row['abilityId'] in {a['id'] for a in main.CARD_ABILITIES[row['cardId']]}, 'Shipped ability is missing'
        assert type(row['expectedDelta']) is int and row['expectedDelta'] != 0
        assert row['lifetime'] in {'turn', 'field', 'linked'}
        assert row['mode'] in {'play', 'activate', 'event'}
        assert row['targetRelation'] in {'any', 'self', 'opponent', 'source'}
        assert row['targetZone'] in {'field', 'confrontation', 'interzone'}
        if row['mode'] == 'event': assert row.get('event')
    return manifest['contracts']


def power_family_candidates():
    """Planning inventory only. Shared implementation never supplies an oracle."""
    import main
    names = {c['id']:c['name'] for c in main.CARD_DATA}
    pinned = {(r['cardId'],r['abilityId']) for r in load_power_contracts()}
    candidates=[]
    for cid, abilities in main.CARD_ABILITIES.items():
        for ability in abilities:
            effect=ability.get('ongoingEffect') or {}
            result=ability.get('result') or {}
            if (effect.get('kind')=='power_modifier' and type(effect.get('value')) is int and not effect.get('scope')
                    or result.get('kind')=='add_power_counter_target' and type(result.get('value')) is int):
                candidates.append({'cardId':cid,'name':names[cid],'abilityId':ability['id'],
                                   'hasIndependentContract':(cid,ability['id']) in pinned})
    return candidates


def load_score_contracts():
    """Point oracles are handwritten, including the recipient and event relation."""
    import main
    manifest = json.loads((ROOT / 'audit/score-family.json').read_text(encoding='utf-8'))
    assert manifest['schemaVersion'] == 1 and manifest['family'] == 'fixed-point-change'
    catalog = {c['id']: c for c in main.CARD_DATA}
    keys = set()
    for row in manifest['contracts']:
        assert row['key'] not in keys, 'Duplicate contract key'
        keys.add(row['key'])
        card = catalog[row['cardId']]
        assert row['name'] == card['name']
        assert row['printedText'] == card['effect'], 'Printed text needs an independent re-review'
        assert row['printedTextSha256'] == hashlib.sha256(card['effect'].encode()).hexdigest()
        paragraphs = [p.strip() for p in card['effect'].splitlines() if p.strip()]
        assert paragraphs[row['paragraphIndex']] == row['printedParagraph']
        assert row['abilityId'] in {a['id'] for a in main.CARD_ABILITIES[row['cardId']]}
        assert type(row['expectedDelta']) is int and row['expectedDelta'] != 0
        assert row['recipient'] in {'controller', 'owner', 'opponent', 'event', 'container'}
        assert row['eventRelation'] in {'any', 'self', 'opponent'}
        assert row['sourceZone'] in {'confrontation', 'interzone', 'field', 'receptacle', 'graveyard'}
        assert row['event']
    return manifest['contracts']


def score_family_candidates():
    """Metadata inventory for planning; scaled/compound effects need other cases."""
    import main
    names = {c['id']: c['name'] for c in main.CARD_DATA}
    pinned = {(r['cardId'], r['abilityId']) for r in load_score_contracts()}
    kinds = {'score_owner', 'score_target', 'score_each_opponent',
             'score_source_container', 'score_owner_silent'}
    return [{'cardId':cid, 'name':names[cid], 'abilityId':a['id'],
             'scaled':bool(a['result'].get('perCount')),
             'hasIndependentContract':(cid,a['id']) in pinned}
            for cid, abilities in main.CARD_ABILITIES.items() for a in abilities
            if (a.get('result') or {}).get('kind') in kinds]


def load_scaled_score_contracts():
    import main
    manifest = json.loads((ROOT / 'audit/scaled-score-family.json').read_text(encoding='utf-8'))
    assert manifest['schemaVersion'] == 1 and manifest['family'] == 'scaled-point-change'
    catalog = {c['id']:c for c in main.CARD_DATA}
    keys = set()
    for row in manifest['contracts']:
        assert row['key'] not in keys, 'Duplicate contract key'
        keys.add(row['key'])
        card = catalog[row['cardId']]
        assert row['name'] == card['name']
        assert row['printedText'] == card['effect'], 'Printed text needs an independent re-review'
        assert row['printedTextSha256'] == hashlib.sha256(card['effect'].encode()).hexdigest()
        assert [p.strip() for p in card['effect'].splitlines() if p.strip()][row['paragraphIndex']] == row['printedParagraph']
        assert row['abilityId'] in {a['id'] for a in main.CARD_ABILITIES[row['cardId']]}
        assert row['scope'] in {'interzone','cz_non_token','vessel_owned','exhausted','first_difference'}
        assert row['recipient'] in {'controller','opponent'}
        assert type(row['expectedMultiplier']) is int and row['expectedMultiplier'] != 0
        assert row['mode'] in {'play','event'}
        if row['mode']=='event': assert row['event']
    return manifest['contracts']
