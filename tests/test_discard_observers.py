"""Actual discard producers and independent watcher results under replacements."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
import main
import test_discard_draw_clauses as fixtures

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=json.loads((ROOT/'audit/discard-observers.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    c=next(c for c in main.CARD_DATA if c['id']==row['cardId'])
    assert row['printedTextSha256']==hashlib.sha256(c['effect'].encode()).hexdigest()
    assert row['printedParagraph']==[p.strip() for p in c['effect'].splitlines() if p.strip()][row['paragraphIndex']]


class DiscardObservers(unittest.TestCase):
    world=fixtures.DiscardDrawClauses.world
    field=staticmethod(fixtures.DiscardDrawClauses.field)
    put=staticmethod(fixtures.DiscardDrawClauses.put)
    snapshot=fixtures.DiscardDrawClauses.snapshot
    choose=fixtures.DiscardDrawClauses.choose

    def setup_case(self,row,origin='hand',mode='limbo',count=1,controller='p2',discarder='p1'):
        s=self.world()
        host=self.field(s,row['cardId'],'watcher',owner='p2',controller=controller,zone=row['sourceZone'])
        if row['kind']=='quiet':host['counters']['Quiet']=3
        if row['kind']=='shackle':host['counters']['Shackle']=2
        target=self.field(s,'m4','target',owner='p1' if controller=='p2' else 'p2')
        cards=['m2','m3','m4'][:count]
        if mode in ('support_yes','support_no'):cards=['kl0n8mt9m1fwly0_en']
        self.put(s,discarder,origin,cards)
        if origin=='deck':self.put(s,discarder,'hand',['w2'])
        if mode in ('suspend','order_exile','order_suspend'):
            self.field(s,'inner-deserts-134','bob',owner=discarder,power_bonus=3)
        if mode in ('exile','order_exile','order_suspend'):s.rules_engine['limboDrawn']={discarder:list(cards)}
        s.rules_engine['observedEvents']=[]
        return s,host,target,cards

    def produce(self,s,cards,origin,discarder='p1',mode='limbo'):
        if len(cards)>1:
            # One real multi-card result, with a transaction around all moves.
            action={'id':'discard-producer','controllerId':discarder,'kind':'triggered_effect',
                'source':{'cardId':'explicit-discard-producer'},
                'ability':{'result':{'kind':'discard_deck_owner','value':len(cards)}}}
            self.assertEqual(origin,'deck')
            s.apply_rules_action_result(action)
        else:
            error,_,_=s.move_zone_card_by_effect(discarder,origin,discarder,'graveyard',cards[0])
            self.assertIsNone(error)
        while s.rules_engine.get('pendingChoice'):
            choice=s.rules_engine['pendingChoice']
            if choice.get('_optionalReplacement'):self.choose(s,option='yes' if mode=='support_yes' else 'no')
            else:
                self.assertEqual(choice['kind'],'replacement_order')
                self.assertEqual(s.players[discarder]['zones'][origin],cards)
                self.assertEqual(s.rules_engine['observedEvents'],[],'Preflight must not leak events')
                desired=mode.removeprefix('order_')
                actions=sorted(choice['actions'],key=lambda a:a['replacementKind']==desired)
                self.choose(s,card_ids=[a['actionId'] for a in actions])

    def watched(self,s,row,host):
        previous=(s.rules_engine.get('pendingChoice') or {}).get('id')
        actions=list(s.queue_rules_observed_event_triggers(defer=True))
        choice=s.rules_engine.get('pendingChoice') or {}
        if choice.get('kind')=='trigger_targets' and choice.get('id')!=previous:
            actions.append(choice['_triggerAction'])
        return [a for a in actions
            if (a.get('source') or {}).get('itemId')==host['id'] and a['ability']['id']==row['abilityId']]

    def expected_triggers(self,row,origin,mode,count=1,discarder='p1',controller='p2'):
        if row['kind']=='shackle':return count if mode in ('limbo','support_no') else 0
        if row['eventRelation']=='opponent' and discarder==controller:return 0
        if row['event']=='deck_cards_discarded' and origin!='deck':return 0
        return 1

    def resolve_watched(self,s,row,host,target,actions,discarder='p1'):
        controller=s.rules_item_controller_id(host)
        before_scores={p:s.players[p]['score'] for p in s.players}
        before_power=s.rules_manifestation_characteristics(target)['power']
        before_counter=host['counters'].get('Quiet' if row['kind']=='quiet' else 'Shackle',0)
        # Resolve each actual triggered action, keeping unrelated observers isolated.
        for action in actions:
            if (s.rules_engine.get('pendingChoice') or {}).get('_triggerAction',{}).get('id')!=action['id']:
                s.queue_rules_simultaneous_actions([action])
            choice=s.rules_engine.get('pendingChoice')
            if choice:
                self.assertEqual(choice['kind'],'trigger_targets')
                self.choose(s,targets=[{'kind':'card','itemId':target['id'],'cardId':target['cardId']}])
            self.assertEqual(s.rules_engine['actionStack'][-1]['id'],action['id'])
            self.assertEqual({p:s.players[p]['score'] for p in s.players},before_scores)
            self.assertEqual(s.rules_manifestation_characteristics(target)['power'],before_power)
            s.resolve_rules_top_action()
            if row['kind']=='hand_discard':
                choice=s.rules_engine['pendingChoice'];self.assertEqual((choice['kind'],choice['playerId'],choice['count']),('discard_from_hand',discarder,1))
                self.choose(s,card_ids=['w2'])
        delta=row['expectedDelta']*len(actions)
        if row['kind'].startswith('score_'):
            expected=before_scores.copy();expected[discarder if row['kind']=='score_event_player' else controller]+=delta
            self.assertEqual({p:s.players[p]['score'] for p in s.players},expected)
        elif row['kind']=='power':
            self.assertEqual(s.rules_manifestation_characteristics(target)['power'],before_power+delta)
            effects=[e for e in s.rules_engine['ongoingEffects'] if e.get('abilityId')==row['abilityId']]
            self.assertEqual(len(effects),len(actions))
            self.assertTrue(all(e['duration']==row['duration'] for e in effects))
        elif row['kind'] in ('quiet','shackle'):
            self.assertEqual(host['counters']['Quiet' if row['kind']=='quiet' else 'Shackle'],max(0,before_counter+delta))
        elif row['kind']=='hand_discard' and actions:self.assertNotIn('w2',s.players[discarder]['zones']['hand'])

    def exercise(self,row,case):
        origin='deck' if case.startswith('deck') or not case.startswith('hand') and row['event']=='deck_cards_discarded' else 'hand'
        mode=case.split('__')[-1] if '__' in case else 'limbo'
        count=3 if case.startswith('deck_batch') else 1
        discarder='p2' if case in ('own_player','controller_changed') else 'p1'
        controller='p1' if case=='controller_changed' else 'p2'
        s,host,target,cards=self.setup_case(row,origin,mode,count,controller,discarder)
        if case in ('suspended_draw','suspended_shuffle'):
            self.field(s,'inner-deserts-134','bob',power_bonus=3)
            if case=='suspended_draw':
                self.put(s,discarder,'deck',cards);s.draw_rules_cards(discarder,1)
            else:
                self.put(s,discarder,'hand',cards)
                self.assertIsNone(s.move_zone_card_by_effect(discarder,'hand',discarder,'deck',cards[0])[0])
            self.assertEqual(self.watched(s,row,host),[])
            return
        if case=='tribute':
            self.put(s,'p1','hand',['w2','m2']);s.rules_engine['priorityPlayerId']='p1'
            error,_=s.declare_rules_action('p1','Pay Will',kind='play_card',source={'cardId':'w2','zone':'hand'},payment_card_ids=['m2'])
            self.assertIsNone(error)
            self.assertFalse(any(e['kind'] in ('cards_discarded','deck_cards_discarded') for e in s.rules_engine['observedEvents']))
            self.assertEqual(len(self.watched(s,row,host)),int(row['kind']=='shackle'))
            return
        if case=='failed_move':
            before=self.snapshot(s)
            self.assertIsNotNone(s.move_zone_card_by_effect(discarder,'hand',discarder,'graveyard','absent')[0])
            self.assertEqual(self.snapshot(s),before)
            self.assertEqual(self.watched(s,row,host),[])
            return
        if case=='face_down':host['faceUp']=False
        if case=='silenced':s.rules_engine['ongoingEffects'].append({'id':'silenced','kind':'lose_effects','target':{'kind':'card','itemId':host['id']},'duration':'while_target_on_field'})
        if case=='stalemate':host['fieldZone']='stalemate'
        if case=='will_card':
            cards=['w2'];self.put(s,discarder,origin,cards)
        self.produce(s,cards,origin,discarder,mode)
        actions=self.watched(s,row,host)
        expected=self.expected_triggers(row,origin,mode,count,discarder,controller)
        if case in ('face_down','silenced','stalemate') or case=='will_card' and row['kind']=='shackle':expected=0
        self.assertEqual(len(actions),expected,(row['name'],case))
        self.assertEqual(self.watched(s,row,host),[],'Flushing again must not trigger twice')
        self.resolve_watched(s,row,host,target,actions,discarder)
        if row['kind']=='hand_discard':self.assertEqual(self.watched(s,row,host),[],'The additional hand discard cannot retrigger a Deck watcher')

    def kanon(self,row,case):
        f=fixtures.DiscardDrawClauses();s=self.world()
        host=f.kanon(s);target=self.field(s,'m4','target')
        mode=case.split('__')[0]
        cards=['w2','pw3','m2','m3']
        selected=['w2','pw3'] if not case.endswith('no_will') else ['m2','m3']
        self.put(s,'p1','deck',cards)
        if mode in ('suspend','order_exile','order_suspend'):self.field(s,'inner-deserts-134','bob',power_bonus=3)
        if mode in ('exile','order_exile','order_suspend'):s.rules_engine['limboDrawn']={'p1':list(selected)}
        s.request_rules_draw('p1',4)
        if case.endswith('source_departure'):s._rules_remove_field_item(host,'p2','graveyard')
        self.choose(s,card_ids=selected)
        while (s.rules_engine.get('pendingChoice') or {}).get('kind')=='replacement_order':
            choice=s.rules_engine['pendingChoice'];desired=mode.removeprefix('order_')
            ordered=sorted(choice['actions'],key=lambda a:a['replacementKind']==desired)
            self.choose(s,card_ids=[a['actionId'] for a in ordered])
        count=0 if case.endswith('no_will') else 2
        if count:
            choice=s.rules_engine['pendingChoice'];self.assertIsNotNone(choice)
            self.assertEqual((choice['kind'],choice['playerId'],choice['count']),('power_loss_distribution','p2',count))
            self.choose(s,option={'itemIds':[target['id']]*count})
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.rules_manifestation_characteristics(target)['power'],4-count)


def scenarios(row):
    if row['key']=='kanon':return ['limbo','exile','suspend','order_exile','order_suspend','suspend__no_will','exile__source_departure']
    return ['hand__limbo','deck__limbo','deck_batch','deck_batch__suspend','deck_batch__exile','hand__exile','deck__exile','hand__suspend','deck__suspend','deck__order_exile','hand__order_suspend','hand__support_yes','deck__support_no','own_player','controller_changed','face_down','silenced','stalemate','will_card','suspended_draw','suspended_shuffle','tribute','failed_move']
def method_name(row,case):return 'test_'+row['key']+'__'+case


for row in CONTRACTS:
    for case in scenarios(row):
        def run(self,row=row,case=case):
            if row['key']=='kanon':self.kanon(row,case)
            else:self.exercise(row,case)
        setattr(DiscardObservers,method_name(row,case),run)


if __name__=='__main__':unittest.main()
