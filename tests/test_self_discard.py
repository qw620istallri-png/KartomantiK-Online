"""The original discarded occurrence can exile itself, including from Suspension."""
import copy,hashlib,json,unittest
from pathlib import Path
import main
import test_discard_draw_clauses as base

ROOT=Path(__file__).resolve().parents[1]
CONTRACTS=json.loads((ROOT/'audit/self-discard.json').read_text(encoding='utf-8'))['contracts']
for row in CONTRACTS:
    card=next(c for c in main.CARD_DATA if c['id']==row['cardId'])
    assert row['printedTextSha256']==hashlib.sha256(card['effect'].encode()).hexdigest()


class SelfDiscard(unittest.TestCase):
    world=base.DiscardDrawClauses.world
    field=staticmethod(base.DiscardDrawClauses.field)
    put=staticmethod(base.DiscardDrawClauses.put)
    choose=base.DiscardDrawClauses.choose
    cid=staticmethod(base.DiscardDrawClauses.cid)

    def setup_case(self,row,case):
        s=self.world();cid=row['cardId'];ponder=self.cid('Ponder')
        if case in ('max_cost','over_cost','wrong_type'):
            ponder='will-cost-boundary'
            s.card_rules[ponder]={'type':'persistent_will' if case=='wrong_type' else 'ephemeral_will','cost':4 if case=='over_cost' else 3,'powerCost':'{H}{H}{H}'}
        target=self.field(s,'m4','target',owner='p2')
        self.put(s,'p1','graveyard',[ponder] if row['key']=='nghoul' else [])
        if case=='second_copy_remains':s.put_zone_card('p1','graveyard',cid,'p1','bottom')
        suspended=case in ('suspend','deck_suspend','two_suspended','invalid_old_suspension','decline','play_permission','json_restore')
        if suspended:self.field(s,'inner-deserts-134','bob',power_bonus=3)
        if case=='two_suspended':
            self.put(s,'p1','hand',[cid]);s.suspend_zone_card('p1','hand',cid,source_effect_id='source')
        origin='deck' if case=='deck_suspend' else 'hand'
        self.put(s,'p1',origin,[cid])
        if case=='exile':
            f=base.DiscardDrawClauses()
            s.create_rules_ongoing_effects(f.action('Nullify Reason',targets=[{'kind':'player','playerId':'p1'}],ability_id='nullify-reason-exile-incoming'))
        if case=='no_target':
            if row['key']=='tombloom':s.battlefield=[]
            else:self.put(s,'p1','graveyard',[])
        s.rules_engine['observedEvents']=[]
        error,_,replacement=s.move_zone_card_by_effect('p1',origin,'p1','graveyard',cid)
        self.assertIsNone(error)
        return s,target,ponder,replacement

    def prepare(self,s,row,target,ponder,decline=False):
        queued=s.queue_rules_observed_event_triggers(defer=True)
        if queued:s.queue_rules_simultaneous_actions(queued)
        choice=s.rules_engine.get('pendingChoice') or {}
        if choice.get('kind')=='optional_stack_action':
            self.choose(s,option='decline' if decline else 'accept')
        choice=s.rules_engine.get('pendingChoice') or {}
        if choice.get('kind')=='trigger_targets':
            targets=[{'kind':'card','itemId':target['id'],'cardId':target['cardId']}] if row['key']=='tombloom' else [{'kind':'zone_card','containerId':'p1','zone':'graveyard','cardId':ponder,'ownerId':'p1'}]
            self.choose(s,targets=targets)

    def exercise(self,row,case):
        s,target,ponder,replacement=self.setup_case(row,case)
        cid=row['cardId']
        self.prepare(s,row,target,ponder,case=='decline')
        if case in ('no_target','decline','over_cost','wrong_type') or row['key']=='nghoul' and case=='exile':
            self.assertIsNone(s.rules_engine['pendingChoice'])
            self.assertEqual(s.rules_engine['actionStack'],[])
            self.assertEqual(s.rules_engine['playPermissions'],[])
            return
        self.assertEqual(len(s.rules_engine['actionStack']),1,(row['name'],case))
        action=s.rules_engine['actionStack'][-1]
        self.assertEqual(action['ability']['id'],row['abilityId'])
        if case=='json_restore':s.rules_engine=json.loads(json.dumps(s.rules_engine))
        if case in ('source_left','source_returned','second_copy_remains'):
            self.assertIsNone(s.move_zone_card('p1','graveyard','p1','hand',cid,limbo_reason='move')[0])
            if case=='source_returned':self.assertIsNone(s.move_zone_card('p1','hand','p1','graveyard',cid,limbo_reason='move')[0])
        if case=='reordered':self.assertIsNone(s.move_zone_card('p1','graveyard','p1','graveyard',cid,'bottom',limbo_reason='move')[0])
        if case=='invalid_old_suspension':
            old=next(e for e in s.rules_engine['suspendedCards'] if e['cardId']==cid)
            s.restore_suspended_card(old['id']);s.suspend_zone_card('p1','hand',cid,source_effect_id='source')
        if case=='source_exile_replaced_by_suspend':self.field(s,'inner-deserts-134','bob',power_bonus=3)
        if case=='invalid_target':
            if row['key']=='tombloom':s.battlefield.remove(target)
            else:s.move_zone_card('p1','graveyard','p1','hand',ponder,limbo_reason='move')
        result=s.resolve_rules_top_action()['action']['effectResult']
        source_invalid=case in ('source_left','source_returned','second_copy_remains','invalid_old_suspension','invalid_target','source_exile_replaced_by_suspend')
        if not source_invalid:
            self.assertIn(cid,s.players['p1']['zones']['exile'])
            self.assertEqual(sum(e['cardId']==cid for e in s.rules_engine['suspendedCards']),int(case=='two_suspended'))
        else:
            self.assertNotIn(cid,s.players['p1']['zones']['exile'])
            if case in ('source_returned','second_copy_remains'):self.assertIn(cid,s.players['p1']['zones']['graveyard'])
        if row['key']=='tombloom' and case!='invalid_target':
            self.assertEqual(s.rules_manifestation_characteristics(target)['power'],2)
            if case=='source_exile_replaced_by_suspend':self.assertEqual(result['status'],'suspended')
            if case=='exile':self.assertEqual(result['status'],'already_exiled')
        if row['key']=='nghoul':
            self.assertEqual(len(s.rules_engine['playPermissions']),0 if source_invalid else 1)
            if not source_invalid:
                permission=s.rules_engine['playPermissions'][0]
                self.assertTrue(permission['noTribute']);self.assertTrue(permission['exileOnLeave'])
                self.assertEqual(permission['maxCost'],row['maxWillCost'])
            if case=='play_permission':
                if s.rules_engine['priorityPlayerId']!='p1':
                    self.assertIsNone(s.pass_rules_priority(s.rules_engine['priorityPlayerId'])[0])
                error,played=s.declare_rules_action('p1','Free Ponder',kind='play_card',source={'cardId':ponder,'zone':'graveyard'},ability_id='draw-three-cards')
                self.assertIsNone(error);self.assertEqual(played['cost']['tributeCardIds'],[])
                s.resolve_rules_top_action();self.assertIn(ponder,s.players['p1']['zones']['exile'])


def scenarios(row):
    cases=['limbo','suspend','deck_suspend','exile','source_left','source_returned','two_suspended','second_copy_remains','reordered','invalid_target','source_exile_replaced_by_suspend','no_target','invalid_old_suspension','json_restore']
    return cases+(['decline','play_permission','max_cost','over_cost','wrong_type'] if row['key']=='nghoul' else [])
def method_name(row,case):return 'test_'+row['key']+'__'+case
for row in CONTRACTS:
    for case in scenarios(row):
        def run(self,row=row,case=case):self.exercise(row,case)
        setattr(SelfDiscard,method_name(row,case),run)

if __name__=='__main__':unittest.main()
