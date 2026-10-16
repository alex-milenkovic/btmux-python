"""Contact disclosure/filtering and scanner command gates."""
from tests.test_sensor_completion import SensorFixture, SEES
from entities.mech import MechStatus as S, CritStatus as C
from systems.los import MECHLOSFLAG_BLOCK


class TestObservation(SensorFixture):
    def test_scan_atoi_dispatch_for_zero_contact_id_and_report_coordinates(self):
        from systems.observation import scan
        self.b.contact_id='00'
        self.a.scan_range=15
        result=scan(self.a,'00 W')
        self.assertTrue(result['ok'],result)
        self.assertIn('weapons',result)
        # report's two-argument form is always coordinates, not ID+option.
        self.assertFalse(scan(self.a,'00 W',report=True)['ok'])

    def test_observer_default_hex_scan_bypasses_range_cap(self):
        from systems.observation import scan
        self.a.set_crit_status(C.OBSERVATORIC)
        self.a.scan_range=1
        self.a.targ_x,self.a.targ_y=2,16
        self.a.set_status(S.LOCK_HEX)
        result=scan(self.a)
        self.assertTrue(result['building_queried'])
        self.assertTrue(result['mines_queried'])
        self.assertTrue(result['ok'])  # Empty content is a normal local result.
        explicit=scan(self.a,'2 16 H')
        self.assertNotIn('blocked',explicit)  # Explicit 3-argument form retains cap.

    def test_report_default_hex_preserves_zero_range_and_origin_lookup(self):
        from systems.observation import scan
        self.b.set_hex_position(0,0)
        self.a.targ_x,self.a.targ_y=2,16
        self.a.set_status(S.LOCK_TARGET)
        self.a.scan_range=1
        result=scan(self.a,report=True)
        self.assertTrue(result['ok'],result)
        self.assertEqual(result['report']['position'],[0,0,0])
        self.assertEqual(result['report']['range'],0)

    def test_navigation_vertical_vector_and_bounds(self):
        from systems.observation import navigation
        result=navigation(self.a,'vector','2 2 5')
        self.assertEqual(result['bearing'],180)
        self.assertEqual(result['vertical_bearing'],45)
        self.assertIn('mark +45',result['message'])
        self.assertEqual(navigation(self.a,'bearing','2 2')['bearing'],180)
        self.assertFalse(navigation(self.a,'vector','80 2 5')['ok'])

    def test_turret_offset_and_dead_weapon_section(self):
        from entities.mech import UnitType,MoveType,VehicleLocation,WeaponState
        from entities.crittypes import i2weapon
        from systems.observation import turret_facing,weapon_report
        self.b.unit_type,self.b.move_type=UnitType.VEH_GROUND,MoveType.TRACK
        self.b.facing,self.b.turret_facing=45,225
        self.b.sections[VehicleLocation.TURRET].internal=8
        self.assertEqual(turret_facing(self.b),{'facing':270,'offset':-135})
        self.b.weapons=[WeaponState(section=0,critical=0,weapon_idx=0)]
        self.b.sections[0].criticals[0].type=i2weapon(0)
        self.b.sections[0].criticals[0].data=5
        self.assertEqual(weapon_report(self.b)[0]['status'],'-----')
        self.b.sections[0].internal=self.b.sections[0].armor=0
        self.assertEqual(weapon_report(self.b),[])

    def test_club_status_reads_arm_sections(self):
        from entities.mech import Location
        from systems.observation import status_chars
        self.b.sections[Location.LARM].specials|=0x20
        self.assertEqual(status_chars(self.a,self.b)[0],'C')

    def test_brief_preserves_other_packed_field(self):
        from systems.observation import brief
        self.a.brief=5
        self.assertTrue(brief(self.a,'A 3')['ok'])
        self.assertEqual(self.a.brief,13)
        self.assertTrue(brief(self.a,'C 2')['ok'])
        self.assertEqual(self.a.brief,14)
        self.assertFalse(brief(self.a,'A 7')['ok'])
        self.assertEqual(self.a.brief,14)

    def test_brief_order_and_unidentified_masking(self):
        from systems.observation import contacts
        self.a.brief=1
        self.b.team=self.a.team
        self.b.heat=5
        self.map.losinfo[self.a._id,self.b._id]=SEES|MECHLOSFLAG_BLOCK
        row=contacts(self.a)['contacts'][0]
        self.assertEqual((row['name'],row['friend'],row['status']),('something',False,'     '))
        self.map.losinfo[self.a._id,self.b._id]=SEES
        row=contacts(self.a)['contacts'][0]
        self.assertEqual((row['name'],row['friend'],row['status']),('bb',True,'   + '))
        near=self.unit('near',2,2,2)
        self.map.losinfo[self.a._id,near._id]=SEES
        self.b.set_status(S.DESTROYED)
        self.assertEqual([r['name'] for r in contacts(self.a)['contacts']],['bb','near'])

    def test_shutdown_filters_and_target_override(self):
        from systems.observation import contacts
        self.b.clear_status(S.STARTED)
        self.assertEqual(contacts(self.a,'e')['contacts'],[])
        self.assertEqual(len(contacts(self.a,'es')['contacts']),1)
        self.a.target=self.b._id
        self.assertEqual(len(contacts(self.a,'t')['contacts']),1)
        self.map.losinfo.clear()
        self.assertEqual(contacts(self.a,'t')['contacts'],[])

    def test_scan_truncates_range_report_does_not_cap(self):
        from systems.observation import scan
        self.a.scan_range=14
        self.assertFalse(scan(self.a,self.b)['ok'])
        self.assertTrue(scan(self.a,self.b,report=True)['ok'])
        self.a.scan_range=15
        self.assertTrue(scan(self.a,self.b)['ok'])
        self.assertEqual(sum('being scanned' in m for m in self.b.movement_messages),1)
        self.a.scan_range=0
        self.assertFalse(scan(self.a,self.b,report=True)['ok'])

    def test_actual_armor_and_markings_disclosure(self):
        from systems.observation import scan,view
        self.a.target=self.b._id
        self.b.sections[0].armor=13
        self.b.markings='red-chevron'
        result=scan(self.a,'A')
        self.assertNotIn('armor',result['armor'][0])
        self.assertIn('armor_display',result)
        self.a.set_crit_status(C.OBSERVATORIC)
        self.assertEqual(scan(self.a,'A')['armor'][0]['armor'],13)
        self.assertNotIn('weapons',result)
        self.assertEqual(view(self.a)['message'],'red-chevron')
        self.map.losinfo[self.a._id,self.b._id]|=MECHLOSFLAG_BLOCK
        self.assertFalse(view(self.a)['ok'])
