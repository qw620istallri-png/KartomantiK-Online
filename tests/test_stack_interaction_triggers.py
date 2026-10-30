"""Actual hand Will declarations, paid tributes, Clemency choices and Duel timing."""
import copy
import unittest
from session import ADVANCED_PHASES
import test_stack_interaction_family as core


class StackInteractionTriggers(unittest.TestCase):
    def setUp(self): self.f=core.StackInteractionFamily()

    def declared(self,s,action):
        # The public server handler produces tribute/Will-play triggers here.
        core.main.log_rules_declared_action(s,action)
        while (s.rules_engine.get('pendingChoice') or {}).get('kind')=='simultaneous_stack_order':
            choice=s.rules_engine['pendingChoice'];ids=[a['actionId'] for a in choice['actions']]
            if action['id'] in ids:ids=[action['id']]+[i for i in ids if i!=action['id']]
            self.assertIsNone(s.resolve_rules_choice(choice['playerId'],choice['id'],card_ids=ids)[0])

    def eorthoda(self,persistent=False,concealed=False):
        f=self.f;s=f.world();target=f.field(s,'m4','target')
        eorthoda=f.cid('Eorthoda, the Limpid');will=f.cid('Heartening Monument' if persistent else 'Strengthen')
        s.phase_tracker['index']=ADVANCED_PHASES.index('end_actions' if persistent else 'confrontation_reaction')
        f.put(s,'p1','hand',[eorthoda] if concealed else [will,eorthoda])
        source={'cardId':will,'zone':'hand'}
        if concealed:
            f.field(s,will,'hidden',zone='field')['concealedWill']=True
            source={'cardId':will,'zone':'battlefield','itemId':'hidden'}
        if persistent:s.add_rules_excess_essence('p1',[{'temperament':'phlegmatic','amount':1}])
        error,action=s.declare_rules_action('p1','Paid Will',kind='play_card',source=source,
            ability_id=None if persistent else 'strengthen-power-modifier',payment_card_ids=[eorthoda],
            targets=[] if persistent else [f.field_target(target)])
        self.assertIsNone(error)
        self.declared(s,action)
        self.assertIn(eorthoda,s.players['p1']['zones']['graveyard'])
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.rules_engine['actionStack'],[action])
        return s,action,target

    def test_eorthoda_protects_the_paid_ephemeral_will_after_its_effect(self):
        s,action,target=self.eorthoda()
        self.assertTrue(action['cannotBeNeutralized'])
        self.assertEqual(s.counter_rules_stack_action(action,'neutralize')['status'],'prevented')
        s.resolve_rules_top_action();self.assertEqual(self.f.power(s,target),7)
        self.assertEqual(s.players['p1']['zones']['graveyard'].count(self.f.cid('Strengthen')),1)

    def test_eorthoda_persistent_protection_transfers_to_field_until_end_of_turn(self):
        s,action,_=self.eorthoda(persistent=True)
        self.assertTrue(action['cannotBeNeutralized'])
        s.resolve_rules_top_action()
        will=next(i for i in s.battlefield if i['cardId']==self.f.cid('Heartening Monument'))
        self.assertTrue(s.rules_item_is_protected(will,'p2'));self.assertFalse(s.rules_item_is_protected(will,'p1'))
        s.phase_tracker['turn']=3;s.prune_rules_ongoing_effects()
        self.assertFalse(s.rules_item_is_protected(will,'p2'))

    def test_eorthoda_does_not_protect_a_will_played_from_the_field(self):
        s,action,_=self.eorthoda(concealed=True)
        self.assertFalse(action.get('cannotBeNeutralized',False))
        self.assertEqual(s.counter_rules_stack_action(action,'neutralize')['status'],'neutralized')

    def test_eorthoda_protection_can_be_cleansed_without_reapplication(self):
        s,action,_=self.eorthoda(persistent=True);s.resolve_rules_top_action()
        will=next(i for i in s.battlefield if i['cardId']==self.f.cid('Heartening Monument'))
        s.apply_rules_action_result(self.f.action('Cleanse',targets=[self.f.field_target(will)]))
        self.assertFalse(s.rules_item_is_protected(will,'p2'))
        s.prune_rules_ongoing_effects();self.assertFalse(s.rules_item_is_protected(will,'p2'))

    def clemency(self,controller='p1',exhausted=False):
        f=self.f;s=f.world()
        source=f.field(s,f.cid('Simulacrum of Clemency'),'clemency',zone='field',controller=controller)
        if exhausted:source['rotation']=90
        caster='p2' if controller=='p1' else 'p1'
        f.field(s,'m4','target')
        will=f.cid('Strengthen');f.put(s,caster,'hand',[will])
        s.add_rules_excess_essence(caster,[{'temperament':'hollow','amount':1}])
        s.rules_engine['priorityPlayerId']=caster
        error,played=s.declare_rules_action(caster,'Strengthen',kind='play_card',source={'cardId':will,'zone':'hand'},
            ability_id='strengthen-power-modifier',targets=[{'kind':'card','itemId':'target','cardId':'m4'}])
        self.assertIsNone(error);self.declared(s,played)
        self.assertEqual(len(s.rules_engine['actionStack']),1 if exhausted else 2)
        if not exhausted:self.assertEqual(s.rules_engine['actionStack'][-1]['source']['cardId'],source['cardId'])
        return s,source,played,caster

    def test_clemency_allow_grants_five_without_exhausting_or_countering(self):
        s,source,played,caster=self.clemency();s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];self.assertEqual(choice['playerId'],caster)
        self.assertIsNone(s.resolve_rules_choice(caster,choice['id'],option='allow')[0])
        self.assertEqual(s.players['p1']['score'],55);self.assertEqual(source['rotation'],0)
        self.assertEqual(s.rules_engine['actionStack'],[played])

    def test_clemency_neutralization_preserves_paid_cost_and_exhausts_source(self):
        s,source,played,caster=self.clemency();s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];self.assertIsNone(s.resolve_rules_choice(caster,choice['id'],option='neutralize')[0])
        self.assertEqual(s.players['p1']['score'],50);self.assertEqual(source['rotation'],90)
        self.assertFalse(s.rules_item_effects_active(source));self.assertEqual(self.f.pool(s,caster),{})
        self.assertEqual(s.rules_engine['actionStack'],[])
        self.assertEqual(s.players[caster]['zones']['graveyard'].count(played['source']['cardId']),1)

    def test_clemency_current_controller_gets_points_not_owner(self):
        s,_,_,caster=self.clemency(controller='p2');s.resolve_rules_top_action()
        choice=s.rules_engine['pendingChoice'];self.assertIsNone(s.resolve_rules_choice(caster,choice['id'],option='allow')[0])
        self.assertEqual((s.players['p1']['score'],s.players['p2']['score']),(50,55))

    def test_clemency_exhausted_source_does_not_trigger_until_readied(self):
        s,source,played,caster=self.clemency(exhausted=True)
        self.assertFalse(s.rules_item_effects_active(source))
        s.resolve_rules_top_action();self.assertEqual(s.rules_engine['actionStack'],[])
        source['rotation']=0;self.assertTrue(s.rules_item_effects_active(source))
        self.f.put(s,caster,'hand',[played['source']['cardId']]);s.rules_engine['priorityPlayerId']=caster
        s.add_rules_excess_essence(caster,[{'temperament':'hollow','amount':1}])
        error,again=s.declare_rules_action(caster,'Strengthen',kind='play_card',source={'cardId':played['source']['cardId'],'zone':'hand'},
            ability_id='strengthen-power-modifier',targets=[{'kind':'card','itemId':'target','cardId':'m4'}])
        self.assertIsNone(error);self.declared(s,again)
        self.assertEqual(len(s.rules_engine['actionStack']),2)

    def test_clemency_missing_will_gains_without_useless_choice(self):
        s,source,played,_=self.clemency();s.counter_rules_stack_action(played,'neutralize')
        s.resolve_rules_top_action()
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.players['p1']['score'],55);self.assertEqual(source['rotation'],0)

    def test_clemency_unneutralizable_will_gains_without_useless_choice(self):
        s,source,played,_=self.clemency();played['cannotBeNeutralized']=True
        s.resolve_rules_top_action()
        self.assertIsNone(s.rules_engine['pendingChoice'])
        self.assertEqual(s.players['p1']['score'],55);self.assertEqual(source['rotation'],0)
        self.assertEqual(s.rules_engine['actionStack'],[played])

    def test_clemency_bad_and_duplicate_choices_cannot_score_twice(self):
        s,source,_,caster=self.clemency();s.resolve_rules_top_action();choice=s.rules_engine['pendingChoice']
        before=self.f.snapshot(s)
        self.assertIsNotNone(s.resolve_rules_choice('p1',choice['id'],option='allow')[0]);self.assertEqual(self.f.snapshot(s),before)
        self.assertIsNotNone(s.resolve_rules_choice(caster,choice['id'],option='wrong')[0]);self.assertEqual(self.f.snapshot(s),before)
        self.assertIsNone(s.resolve_rules_choice(caster,choice['id'],option='allow')[0])
        self.assertIsNotNone(s.resolve_rules_choice(caster,choice['id'],option='allow')[0]);self.assertEqual(s.players['p1']['score'],55)

    def test_duel_only_before_revelation_and_lock_expires_next_turn(self):
        f=self.f;will=f.cid('Duel Honorably')
        for phase,allowed in (('confrontation_before_revelation',True),('confrontation_reaction',False),('end_actions',False)):
            s=f.world();s.phase_tracker['index']=ADVANCED_PHASES.index(phase);f.put(s,'p1','hand',[will])
            error,action=s.declare_rules_action('p1','Duel',kind='play_card',source={'cardId':will,'zone':'hand'},
                ability_id='lock-support-entries-unless-opponent-pays')
            self.assertEqual(error is None,allowed)
            if not allowed:continue
            for pid in ('p1','p2'):self.assertFalse(s.rules_support_entry_locked(pid))
            s.resolve_rules_top_action()
            for pid in ('p1','p2'):self.assertTrue(s.rules_support_entry_locked(pid))
            s.phase_tracker['turn']=3
            for pid in ('p1','p2'):self.assertFalse(s.rules_support_entry_locked(pid))
