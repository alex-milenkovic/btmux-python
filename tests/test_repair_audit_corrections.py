"""Connected source-boundary observations for the full PILOT-REPAIR pass."""
import json
import tempfile
import unittest
from unittest.mock import patch
from entities.mech import FireMode as F, SectionConfig as C, CritStatus, MechStatus as S, MoveType
from entities.crittypes import Special, i2special
from core.events import SOURCE_EVENT_IDS
from systems.technician import pack


class RepairAuditCorrections(unittest.TestCase):
    def repair(self):
        from tests import test_repair_work
        base=test_repair_work.RepairWorkTests();base.setUp()
        return base

    def tow(self):
        from tests import test_towing_commands
        base=test_towing_commands.TowingCommandTests();base.setUp()
        return base

    def test_position_name_bounds_split_order_and_report_delivery(self):
        from systems.status_display import part_name
        from systems.repair_reports import RepairReports
        b=self.repair();slot=b.unit.sections[4].criticals[0]
        slot.type=i2special(Special.SPLIT_CRIT_LEFT);slot.data=0
        b.unit.sections[2].criticals[0].type=i2special(Special.HEAT_SINK)
        with patch('systems.parts.reverse_split_crit_loc',return_value=2):
            self.assertEqual(part_name(b.unit,4,0),'HeatSink')
        self.assertEqual(part_name(b.unit,-1,0),'--?LocationBug?--')
        self.assertEqual(b.unit.channel_requests[-1]['text'],'INVALID: For mech #12, -1/0 was requested.')
        slot.type=i2special(Special.HAND_OR_FOOT_ACTUATOR)
        rows=RepairReports(b.work).human(b.actor,b.unit)
        self.assertIn('Hand Actuator',rows[0]['description'])
        self.assertTrue(any('Damage for ' in line for line in b.actor.inbox))
        self.assertTrue(any('Fix# Time  BTH Loc Description' in line for line in b.actor.inbox))
        self.assertIn('%cy',rows[0]['text'])

    def test_point_report_columns_suit_fallthrough_and_ready_guard(self):
        b=self.repair()
        e=b.jobs.schedule(47,b.unit,pack(7,12,3),180)
        self.assertEqual(b.jobs.describe(e)['text'],'7     3    CT(R):3  Repair of armor - possibly next point')
        fake=b.jobs.schedule(48,b.unit,pack(7,4,3),180,fake=True)
        self.assertEqual(b.jobs.describe(fake)['position'],0)
        suit=b.jobs.schedule(57,b.unit,pack(7,4),180,fake=True)
        row=b.jobs.describe(suit)
        self.assertIsNone(row['position'])
        self.assertEqual(row['description'],'Replacing suit (Failure)   CT Reseal (Failure)')
        b.work.command(b.actor,b.unit,'repairs')
        self.assertTrue(any('Repairs/Scrapping in progress' in line for line in b.actor.inbox))
        self.assertTrue(any("Plr = Tech's dbref" in line for line in b.actor.inbox))
        for event in b.jobs.events():b.engine.events.cancel_event(event)
        b.jobs.schedule(47,b.unit,pack(7,4),1)
        with self.assertRaisesRegex(ValueError,'no repairs pending'):
            b.work.command(b.actor,b.unit,'repairs')

    def test_load_unknown_fake_and_nonpositive_terminator(self):
        b=self.repair()
        payload=pack(7,4,0)
        rows=[[12,99,-5,payload],[12,99,5,payload],[0,"ignored"],[12,53,2,payload]]
        result=b.jobs.load("\n".join(json.dumps(row) for row in rows))
        self.assertEqual(result,dict(loaded=1,skipped=1,error=None))
        events=b.engine.events.pending_events()
        self.assertEqual(len(events),1)
        self.assertEqual(SOURCE_EVENT_IDS[events[0].event_type],99)
        self.assertEqual(events[0].data2,payload)
        self.assertTrue(any('SOURCE_99' in line for line in b.engine.events.debug_event_types()))
        self.assertEqual(b.engine.diagnostics[-1]['text'],'LOADED: 2 tech events.\n')
        self.assertEqual(b.jobs.save(),'[-1]\n')
        b.due(5)
        self.assertEqual(b.engine.events.pending_events(),[])
        self.assertTrue(b.slot.firemode&F.BROKEN_MODE)

    def test_signed_internal_resources_payload_and_failure_truncation(self):
        b=self.repair();sec=b.unit.sections[4];sec.internal=13
        event=b.work.command(b.actor,b.unit,'fixinternal','CT')
        self.assertEqual((b.store.find(10,546),b.store.find(10,545)),(3,0))
        self.assertEqual(b.store.get(7,'TECHTIME'),'-1620')
        self.assertEqual(event.data2,7*65536+4-48)
        b.due(1)
        self.assertEqual(sec.internal,10)
        self.assertEqual(b.jobs.events()[0].data2,6*65536+4+252*16)
        with patch('systems.repair_work.draw',return_value=5):
            self.assertEqual(b.work.failure('fixinternal_fail',b.actor,b.unit,4,amount=-3),-1)

    def test_internal_byte_wrap_and_source_callback_type(self):
        b=self.repair();sec=b.unit.sections[4];sec.internal=255;sec.internal_orig=255
        b.unit.crit_status=(1<<50)|int(CritStatus.OWEIGHT_OK)
        b.jobs.schedule(53,b.unit,pack(7,4,2),1,callback='internal')
        b.due(1)
        self.assertEqual(sec.internal,0)
        self.assertEqual(b.unit.crit_status,1<<50)
        event=b.jobs.events()[0]
        self.assertEqual((SOURCE_EVENT_IDS[event.event_type],event.tick),(48,541))
        b.due(541)
        self.assertEqual(sec.internal,1)

    def test_enhanced_notice_precedes_mutation_and_masks_keep_other_bits(self):
        from systems.repairs import reseal
        from systems.enhanced_crits import set_part_temp_nuke,part_temp_nuke
        b=self.repair();slot=b.slot
        slot.firemode=(1<<50)|int(F.DAMAGED_MODE);slot.weap_damage_flags=9;set_part_temp_nuke(slot,3)
        before=[]
        with patch.object(b.jobs,'notice',side_effect=lambda *a:before.append((slot.firemode,slot.weap_damage_flags,part_temp_nuke(slot)))):
            b.jobs.schedule(58,b.unit,pack(7,4),1);b.due(1)
        self.assertEqual(before,[(int(F.DAMAGED_MODE)|(1<<50),9,3)])
        self.assertEqual((slot.firemode,slot.weap_damage_flags,part_temp_nuke(slot)),(1<<50,0,0))
        slot.firemode=(1<<50)|int(F.DISABLED_MODE|F.DESTROYED_MODE);slot.data=7
        b.unit.sections[4].config=(1<<45)|int(C.SECTION_FLOODED)
        reseal(b.unit,4)
        self.assertEqual(slot.firemode,(1<<50)|int(F.DESTROYED_MODE))
        self.assertEqual(slot.data,7);self.assertEqual(b.unit.sections[4].config,1<<45)

    def test_cargo_cap_authority_and_per_row_notice_order(self):
        from tests import test_cargo_commands
        b=test_cargo_commands.CargoCommandTests();b.setUp();b.store.set(10,545,0,5)
        for name in ('Raddstuff','Rremovestuff','Rresetstuff','Rfixstuff'):
            with self.assertRaisesRegex(ValueError,'restricted'):
                b.commands.command(b.actor,b.unit,name,'Internal 2 tail')
        entries=[b.store.catalog.entries[545,0],b.store.catalog.entries[546,0]]
        observed=[]
        with patch.object(b.store,'matching',return_value=entries),patch.object(b.commands,'notice',side_effect=lambda *a:observed.append((b.store.find(10,545),b.store.find(10,546)))):
            b.commands.command(b.actor,b.unit,'loadcargo','* 2 ignored tail')
        self.assertEqual(observed,[(3,5),(3,3)])
        self.assertEqual((b.store.find(12,545),b.store.find(12,546)),(2,2))
        with self.assertRaisesRegex(ValueError,'Invalid amount'):
            b.commands.command(b.actor,b.unit,'loadcargo','Internal \u0661')
        b.actor.wizard=True;b.actor.location=10
        b.commands.command(b.actor,b.unit,'Raddstuff','Internal 2 ignored tail')
        self.assertEqual(b.store.find(10,546),5)

    def test_tow_caps_early_failure_cache_and_unit_audience(self):
        from systems.occupants import pickup
        from systems.towing import attach_cables,detach_cables,dropoff
        b=self.tow()
        self.assertTrue(attach_cables(b.operator,b.actor,'  13 14 ignored')['ok'])
        self.assertTrue(detach_cables(b.operator,b.actor,'\t13 ignored')['ok'])
        b.tower.carrying=999;b.tower.crit_status=(1<<50)|int(CritStatus.LOAD_OK)
        self.assertFalse(detach_cables(b.operator,b.actor,'13')['ok'])
        self.assertEqual((b.tower.carrying,b.tower.crit_status),(-1,1<<50))
        b.operator.carrying=999;b.operator.crit_status=(1<<50)|int(CritStatus.LOAD_OK)
        self.assertFalse(dropoff(b.operator,b.actor)['ok'])
        self.assertEqual((b.operator.carrying,b.operator.crit_status),(-1,1<<50))
        b.operator.move_type=MoveType.QUAD
        b.actor.inbox=[];b.operator.pilot=None
        result=pickup(b.operator,b.actor,' 13 ignored')
        self.assertFalse(result['ok'])
        self.assertEqual(b.actor.inbox,[])
        self.assertIn("four left feet",b.operator.movement_messages[-1])
        b.operator.move_type=MoveType.BIPED;b.tower.status|=S.JUMPING;b.tower.z=1
        result=attach_cables(b.operator,b.actor,'13 14')
        self.assertIn('currently flying',result['error'])

    def test_public_adapter_single_notice_admin_and_unknown_event_snapshot(self):
        from tests import test_repair_economy_cli
        from tools.repair_economy import RepairEconomySession
        with tempfile.TemporaryDirectory() as root:
            doc=test_repair_economy_cli.RepairEconomyCLITests().document(root)
            session=RepairEconomySession(doc);unit=session.units['u'];actor=session.characters.actor(101)
            for name in ('raddstuff','rremovestuff','rresetstuff','rfixstuff','magic','fixextra'):
                actor.inbox=[]
                result=session.action(dict(op='command',name=name,args='Internal 2 tail'))
                self.assertFalse(result['ok']);self.assertEqual(actor.inbox,['Sorry, that command is restricted!'])
            for name in ('stores','loadcargo','unloadcargo','pickup','attachcables','detachcables','dropoff'):
                actor.inbox=[];unit.pilot=actor;unit.status|=S.STARTED;unit.mapindex=99999
                result=session.action(dict(op='command',name=name,args='13 14'))
                self.assertFalse(result['ok'],(name,result))
                self.assertEqual(unit.mapindex,-1,name)
                self.assertFalse(unit.is_started,name)
                self.assertEqual(sum('invalid map' in text.lower() for text in actor.inbox),1,(name,actor.inbox))
                self.assertEqual(len(actor.inbox),2,(name,actor.inbox))
            result=session.action(dict(op='repair',kind='load',text='[10,99,-3,6619140]\n[-1]'))
            self.assertEqual(result['loaded'],1)
            self.assertTrue(any(e['type']==99 for e in session.snapshot()['events']))
            session.action(dict(op='advance',seconds=3))
            self.assertFalse(any(e['type']==99 for e in session.snapshot()['events']))


    def test_contact_tokens_preserve_non_delimiter_whitespace(self):
        from systems.occupants import pickup
        from systems.towing import attach_cables,detach_cables
        for whitespace in ('\n','\r','\v','\f'):
            for command in ('pickup','attach_tower','attach_target','detach'):
                with self.subTest(whitespace=repr(whitespace),command=command):
                    b=self.tow()
                    tower_token='\t13'+whitespace+'ignored'
                    target_token='14'+whitespace+'ignored'
                    if command=='pickup':
                        result=pickup(b.operator,b.actor,tower_token+' surplus tail')
                        self.assertTrue(result['ok'],result)
                        self.assertEqual(b.operator.carrying,13)
                        self.assertIs(b.operator.towed_unit,b.tower)
                    elif command=='detach':
                        b.tower.carrying=14;b.tower.towed_unit=b.load;b.load.status|=S.TOWED
                        result=detach_cables(b.operator,b.actor,tower_token+' surplus tail')
                        self.assertTrue(result['ok'],result)
                        self.assertEqual(b.tower.carrying,-1)
                        self.assertFalse(b.load.has_status(S.TOWED))
                    else:
                        text=(tower_token+' 14' if command=='attach_tower' else '\t13 '+target_token)+' surplus tail'
                        result=attach_cables(b.operator,b.actor,text)
                        self.assertTrue(result['ok'],result)
                        self.assertEqual(b.tower.carrying,14)
                        self.assertIs(b.tower.towed_unit,b.load)

    def test_contact_lookup_keeps_los_map_and_embark_admission(self):
        from systems.occupants import _target,embark,pickup
        b=self.tow()
        self.assertIs(_target(b.operator,b.tower),b.tower)
        self.assertIsNone(_target(b.operator,'99\nignored'))
        for text in ('13\u00a0ignored','13\u2003ignored'):
            with self.assertRaisesRegex(ValueError,'ASCII string required'):
                _target(b.operator,text)
        with patch('systems.los.in_line_of_sight',return_value=False):
            result=pickup(b.operator,b.actor,'13\nignored')
            self.assertEqual(result['error'],'That target is not in your line of sight.')
        for text in ('','13 14','13\nignored','13\tignored'):
            with self.subTest(embark=text):
                result=embark(b.operator,b.actor,text)
                self.assertEqual(result['error'],'Invalid number of arguements.')
        for reference in ('13\nignored',b.tower):
            b.operator.mapindex=-1
            self.assertIsNone(_target(b.operator,reference))

    def test_raw_newline_contacts_through_repair_command_adapter(self):
        from tests import test_repair_economy_cli
        from tools.repair_economy import RepairEconomySession
        from systems.sensors import update_los_info
        from systems.targeting import plos_event
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as root:
            doc=test_repair_economy_cli.RepairEconomyCLITests().document(root)
            doc['units'].extend([dict(name='tower',id=13,started=False),dict(name='load',id=14,started=False)])
            session=RepairEconomySession(doc);operator=session.units['u']
            for name,unit in session.units.items():
                unit.team=1;unit.in_character=True;unit.set_hex_position(2,2)
                unit.contact_id=str(unit._id);unit.measured_mass=unit.tonnage*1024
            for loc in (0,1):
                operator.sections[loc].internal=operator.sections[loc].internal_orig=10
                operator.sections[loc].criticals[0].type=i2special(Special.SHOULDER_OR_HIP)
                operator.sections[loc].criticals[3].type=i2special(Special.HAND_OR_FOOT_ACTUATOR)
            operator.status|=S.STARTED
            update_los_info(operator.map);operator.pnum_seen=2
            plos_event(SimpleNamespace(data=operator,data2=session.engine))
            commands=(
                ('pickup','\t13\nignored surplus tail',operator,13),
                ('dropoff','',operator,-1),
                ('attachcables','\t13\nignored 14 surplus tail',session.units['tower'],14),
                ('detachcables','\t13\nignored surplus tail',session.units['tower'],-1),
                ('attachcables','\t13 14\nignored surplus tail',session.units['tower'],14),
                ('detachcables','\t13 surplus tail',session.units['tower'],-1),
            )
            for name,text,tower,carrying in commands:
                with self.subTest(command=name,argument=text):
                    result=session.action(dict(op='command',unit='u',name=name,args=text))
                    self.assertTrue(result['ok'],result)
                    self.assertEqual(tower.carrying,carrying)



if __name__=='__main__':unittest.main()
