"""Focused source-boundary checks for the final HUD repair pass."""
import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tools.core_simulation import CoreSession
from entities.mech import Mech,UnitType as U,MoveType as M,MechStatus as S,FireMode as F
from systems import hud,observation,status_display as status,map_display as maps,armor_display as armor


class HudAuditRepairs(unittest.TestCase):
    def setUp(self):
        self.session=CoreSession({'maps':[{'name':'field','id':100,'size':[12,12]}],
            'units':[{'name':'viewer','at':[3,3,0]},{'name':'target','at':[4,4,0]}],
            'config':{'periodic_updates':False},'actions':[]})
        self.unit=self.session.units['viewer'];self.target=self.session.units['target']
        self.board=self.unit.map

    def test_numeric_boundaries_and_unknown_type_diagnostic(self):
        unit=self.unit;unit.unit_type=U.VTOL;unit.move_type=M.VTOL
        unit.desired_speed=unit.vertical_speed=.001
        with patch('physics.cargo.cargo_max_speed',return_value=10):
            info=hud.template_info(unit)
        self.assertEqual(('10.000','10.000'),(info[4],info[6]))
        unit.unit_type=U.VEH_GROUND;unit.turret_facing=-360;unit.sections[4].internal_orig=1
        self.assertEqual(180,hud.general(unit)[15])
        unit.move_type=M.FLY
        with patch('core.effects.send_error') as error:
            self.assertEqual('?',hud.type_char(unit))
        error.assert_called_once_with(unit,f'Unknown movement type on vehicle #{unit._id}: {int(M.FLY)}')

    def test_ammo_wrap_and_generic_catalog_names(self):
        from entities.crittypes import i2ammo
        from entities.weapon import get_weapon
        from systems.combat_ammunition import find_ammunition
        from data.construction_catalog import source_part
        from systems.economic_inventory import InventoryStore
        for section in self.unit.sections:
            for slot in section.criticals:slot.type=0
        for slot in self.unit.sections[0].criticals[:2]:
            slot.type=i2ammo(get_weapon('IS.SRM-6').index);slot.data=40000
        self.assertEqual(14464,find_ammunition(self.unit,True)[0].current)
        self.assertIsNone(status.catalog_part_name(65000,owner=self.unit))
        store=InventoryStore();store.register(2);part=source_part('IS.MediumLaser');store.set(2,part,0,1)
        self.assertEqual('IS MediumLaser',store.listing(2)['rows'][0]['name'])

    def test_armor_parser_states_cr_and_output_limit(self):
        unit=self.unit
        self.assertEqual('&+0',armor.render_template(unit,'&+0',True))
        self.assertEqual(' &@0A',armor.render_template(unit,'7 &@0A',True))
        self.assertEqual('A\r\r\nB',armor.render_template(unit,'A\r\nB',True))
        self.assertEqual(16383,len(armor.render_template(unit,'7 '+('&9+0'*3000),True)))
        self.assertEqual((5,-1),armor.condition(unit,0,'invalid'))

    def test_custom_attribute_context_empty_result_and_selected_lookup(self):
        from core.attributes import attributes_for
        from core.object_services import STATUS_FLAGS
        unit=self.unit;actor=unit.command_actor
        attributes_for(unit).set(unit._id,'A_MECHSTATUS','[configured expression]')
        calls=[]
        self.session.engine.expression_evaluator=lambda text,**context:(calls.append((text,context)) or '')
        display=armor.armor_display(unit,True,caller=actor)
        self.assertEqual('',display['text']);self.assertEqual(STATUS_FLAGS,calls[0][1]['flags'])
        self.assertEqual((actor._id,unit._id),(calls[0][1]['executor'],calls[0][1]['enactor']))
        del self.session.engine.expression_evaluator
        unit.status_expression=True
        self.assertTrue(status.status(unit,'H')['ok'])
        with self.assertRaises(armor.DisplayDependencyError):status.status(unit,'A')

    def test_persistent_registry_source_discovery_order(self):
        from core.object_services import ObjectRegistry
        units={self.unit._id:self.unit,self.target._id:self.target}
        player=SimpleNamespace(_id=900,location=self.unit._id,hardcode=False)
        self.unit.location=100;self.target.location=900
        Path('tmp').mkdir(exist_ok=True)
        with TemporaryDirectory() as directory:
            path=Path(directory)/'objects.json'
            registry=ObjectRegistry(path,resolve=units.get)
            for obj in (player,self.unit,self.target):registry.register(obj)
            engine=SimpleNamespace(object_registry=ObjectRegistry(path,resolve=units.get))
            personnel=SimpleNamespace(engine=engine,objects={},contents=lambda identity:[])
            self.assertIs(self.unit,hud.player_unit(personnel,900))
            self.unit.zombie=True;registry.register(self.unit)
            self.assertIs(self.target,hud.player_unit(personnel,900))

    def test_stale_target_and_stored_z_use_find_target_xy(self):
        unit=self.unit;unit.target=9999;unit.targ_x=unit.targ_y=4;unit.targ_z=7
        self.assertIn('No default target',observation.scan(unit)['message'])
        self.assertIn('No default target',observation.scan(unit,report=True)['message'])
        for kind in ('bearing','range','vector'):
            self.assertIn('no default target',observation.navigation(unit,kind)['message'])
        unit.target=-1
        from systems.targeting import find_range
        from physics.hexmath import hex_to_float,ZSCALE
        expected=find_range(unit.fx,unit.fy,unit.fz,*hex_to_float(4,4),7*ZSCALE)
        self.assertAlmostEqual(expected,observation.navigation(unit,'range')['range'])

    def test_status_prefixes_compact_heat_and_source_preferences(self):
        self.assertEqual(['generic','info','heat'],status.selected_components('IN'))
        self.assertEqual(['generic','armor'],status.selected_components('AR'))
        self.assertEqual(['generic','info','heat'],status.selected_components('IN\tS'))
        result=status.status(self.unit,'NH');self.assertTrue(result['lines'][0].startswith('Temp:'))
        self.unit.target=99999;self.unit.prefs=1
        self.assertEqual('',status.target_lines(self.unit)[0])
        self.assertIn('Safeties',status.target_lines(self.unit)[1])
        self.unit.move_type=M.NONE
        self.assertTrue(any(line.startswith('Pilot') for line in status.generic_lines(self.unit)))

    def test_report_bounds_identification_and_fuel_zero(self):
        target=self.target;target.name='huge';target.team=self.unit.team;target.facing=-360
        with patch('systems.observation.in_line_of_sight_nb',return_value=0):
            report=observation.report_lines(self.unit,target,1)
        self.assertTrue(report[0].startswith('['+target.contact_id.upper()+']'))
        self.assertIn('Heading: 360 degrees',report[2])
        target.tonnage=10**120
        self.assertEqual(99,len(observation.report_lines(self.unit,target,1)[0]))
        target.unit_type=U.AERO;target.fuel_orig=target.fuel=0
        self.assertIn('nan %','\n'.join(status.info_lines(target)))

    def test_contacts_trim_bounded_rows_and_setting_delivery(self):
        result=observation.contacts(self.unit,' \t ')
        self.assertTrue(result['ok'])
        with patch('systems.observation.notify') as notice:
            result=observation.brief(self.unit,'C2')
        notice.assert_called_once_with(self.unit,result['message'])
        from systems.display_contacts import contact_lines
        row=dict(contact_id='AA',name='x'*200,tonnage=1,range=1,bearing=0,speed=0,heading=0,x=0,y=0,
            heat=0,move_type=M.BIPED,sees_primary=True,sees_secondary=True,arcs=0,destroyed=False,started=True,fallen=False,jumping=False)
        self.assertEqual(99,len(contact_lines(self.unit,row,False,0)[0]))

    def test_tactical_and_lrs_color_state(self):
        colors,_=maps.palette('');colors[13]='H'
        self.assertEqual(['%ch%cn%ch?%cn','?%cn'],maps.color_rows(['?','?'],colors))
        maps._lrs_color_buffer=''
        self.assertEqual(('%cgA','g'),maps.colored_character('A','g',''))
        self.assertEqual(('%cgA%crB','r'),maps.colored_character('B','r','g'))
        self.assertEqual(('C','r'),maps.colored_character('C','r','r'))
        self.assertEqual(('C%cyD','y'),maps.colored_character('D','y','r'))
        self.target.unit_type=U.DS;self.target.move_type=M.NONE
        self.assertEqual('D',maps.lrs_glyph(self.unit,self.target,False))

    def test_labels_padding_mine_self_and_signed_size_parser(self):
        rows,cells,window=maps.sketch(None,3,3,5,5,board=self.board,labels=0)
        self.assertEqual([16]*11,list(map(len,rows)))
        rows,_,_=maps.sketch(None,3,3,5,5,board=self.board,labels=3)
        self.assertEqual((23,20,23),(len(rows[0]),len(rows[3]),len(rows[4])))
        self.unit.command_actor.tacsize='+5+5'
        self.assertEqual([5,5],maps.tactical(self.unit)['window'][2:])
        self.unit.command_actor.tacsize='bad';self.unit.command_actor.mapcolor='!'
        warnings=maps.tactical(self.unit)['warnings']
        self.assertTrue(warnings[0].startswith('Illegal Tacsize'))
        self.unit.display_los_cells=[dict(x=3,y=3,flags=0)]
        rows,_,_=maps.sketch(self.unit,3,3,5,5,mode='m',dolos=True)
        self.assertTrue(any('**' in row for row in rows))
        self.assertTrue(maps.hud_tactical(self.unit,'3 0 0 l ignored')['ok'])

    def test_lrs_same_hex_selection_sort_and_raw_grass(self):
        a=self.target;a.set_hex_position(2,2);a.move_type=M.TRACK
        b=Mech.create_test_mech('b');b.set_hex_position(2,2);b.move_type=M.WHEEL
        c=Mech.create_test_mech('c');c.set_hex_position(1,1)
        with patch('systems.map_display.visible_units',return_value=[a,b,c]):
            result=maps.lrs(self.unit,'m')
        self.assertEqual('w',next(cell['glyph'].lower() for cell in result['cells'] if (cell['x'],cell['y'])==(2,2)))
        self.unit.command_actor.ansimap=True
        self.board.set_terrain(2,2,'~');self.board.set_terrain(4,2,' ')
        calls=[]
        original=maps.colored_character
        with patch('systems.map_display.colored_character',side_effect=lambda char,new,previous:(calls.append(char) or original(char,new,previous))):
            maps.lrs(self.unit,'t')
        self.assertNotIn(' ',calls)

    def test_hangar_lock_actions_and_teleport_broadcast_order(self):
        from tests.hud_status.test_hangar import HangarTests
        fixture=HangarTests('runTest');fixture.setUp()
        unit=fixture.u;board=fixture.inside;engine=fixture.s.engine
        from core.attributes import attributes_for
        attributes_for(board).set(board._id,'A_LENTER','configured compound lock')
        contexts=[]
        engine.lock_evaluator=lambda text,**context:(contexts.append((text,context)) or False)
        board.cf=board.cfmax=100
        from systems.hangar import enter_base,enter_event
        with patch('core.effects.did_it') as action:
            result=enter_base(unit,caller=unit.command_actor)
        self.assertFalse(result['ok']);self.assertTrue(result['notified'])
        self.assertEqual(unit._id,contexts[0][1]['actor'])
        self.assertEqual(unit.command_actor,action.call_args.args[1])
        engine.lock_evaluator=lambda *args,**kwargs:True
        trace=[]
        from systems.dropships import move_object
        with patch('systems.sensors.los_broadcast',side_effect=lambda who,message:trace.append(('los',who._id))),patch('systems.hangar.move_object',side_effect=lambda who,dest:(trace.append(('move',who._id)),move_object(who,dest))):
            self.assertTrue(enter_base(unit)['ok']);engine.run_ticks(18)
        self.assertLess(trace.index(('los',fixture.tow._id)),trace.index(('move',unit._id)))

    def test_sight_capped_args_integer_prefix_and_original_actor(self):
        from tools.sensors_los import SensorSession
        from systems.combat import AttackResult
        session=SensorSession({'units':[{'name':'u'}],'config':{'periodic_updates':False},'actions':[]})
        unit=session.units['u']
        with patch('systems.combat_firing.fire_command',return_value=AttackResult()) as fire:
            session.command(unit,'sight',['0junk','3','4','extra','fifth','ignored'])
        self.assertEqual(['0junk','3','4','extra','fifth'],fire.call_args.args[2])
        self.assertIs(unit.command_actor,fire.call_args.kwargs['caller'])


if __name__=='__main__':unittest.main()
