"""Post-destruction C3 master recount at the damage boundary."""
from entities.mech import Location as L, Specials, CritStatus, FireMode
from entities.crittypes import Special, i2special
from systems import c3, criticals, targeting
from physics.hexmath import SCALEMAP
from core.events import EventType
from tests.test_communications import CommunicationsFixture


class C3MasterCriticalTest(CommunicationsFixture):
    def install_masters(self, count):
        for section in self.a.sections:
            for slot in section.criticals:
                slot.type = slot.firemode = 0
        for loc in (L.LTORSO, L.RTORSO)[:count]:
            for slot in self.a.sections[loc].criticals[:5]:
                slot.type = i2special(Special.C3_MASTER)
        self.a.specials = Specials.C3_MASTER_TECH
        self.a.working_c3_masters = count
        self.a.total_c3_masters = count
        self.c.team = 2
        self.assertTrue(c3.command(self.b, self.b.pilot, 'join', 'AA')['ok'])
        # B shoots at C; A contributes a shorter, visible range.
        for unit, distance in ((self.b, 0), (self.a, 9), (self.c, 12)):
            unit.fx, unit.fy, unit.fz = distance * SCALEMAP, 0, 0
        self.assertEqual((3, self.a._id), c3.range_query(self.b, self.c, 12))

    def hit(self, slot=0):
        return criticals.apply_critical_to_slot(self.a, L.LTORSO, slot, engine=self.engine)

    def test_first_hit_sole_master_removes_capacity_range_and_runs_tag_consequences(self):
        self.install_masters(1)
        # Exercise lazy cache initialization as well as the explicit cache case below.
        del self.a.working_c3_masters
        self.assertTrue(targeting.tag(self.engine, self.a, 'CC', self.a.pilot)[0])
        self.c.fx = self.a.fx + 16 * SCALEMAP
        self.a.pilot.inbox = []
        self.assertTrue(self.hit().effect_applied)
        self.assertEqual(0, self.a.working_c3_masters)
        self.assertEqual(1, self.a.total_c3_masters)
        self.assertTrue(self.a.sections[L.LTORSO].criticals[0].firemode & FireMode.DESTROYED_MODE)
        self.assertTrue(self.a.crit_status & CritStatus.C3_DESTROYED)
        self.assertEqual((0, 0), (self.a.tag_target, self.c.tagged_by))
        self.assertEqual(1, self.a.pilot.inbox.count('Your TAG connection has been broken.'))
        self.assertFalse(targeting.tag(self.engine, self.a, 'CC', self.a.pilot)[0])
        self.c.fx = 12 * SCALEMAP
        self.assertEqual(0, c3.maximum(self.b, self.b.c3_network))
        self.assertEqual((12, 0), c3.range_query(self.b, self.c, 12))
        self.assertEqual([], c3.temporary(self.b))
        c3.validate(self.b)
        self.assertEqual([], self.b.c3_network)
        events = len([e for e in self.engine.events._events.values()
                      if e.event_type == EventType.TAG_RECYCLE and e.data is self.a])
        self.hit(1)  # A different functional slot in the already-disabled master.
        self.hit(1)  # An already-destroyed slot retains the generic early return.
        self.assertEqual(0, self.a.working_c3_masters)
        self.assertEqual(1, self.a.pilot.inbox.count('One of your C3 systems has been destroyed!'))
        self.assertEqual(1, self.a.pilot.inbox.count('Your destroyed C3 system takes another hit!'))
        self.assertEqual(events, len([e for e in self.engine.events._events.values()
                                     if e.event_type == EventType.TAG_RECYCLE and e.data is self.a]))

    def test_one_of_two_masters_reduces_capacity_without_losing_remaining_range(self):
        self.install_masters(2)
        for i in range(3):
            peer = self.make_unit(20 + i, 'P' + str(i))
            peer.contact_id = 'P' + str(i)
            self.assertTrue(c3.command(peer, peer.pilot, 'join', 'AA')['ok'])
        self.assertEqual(6, c3.maximum(self.a, self.a.c3_network))
        self.assertEqual(4, c3.network_size(self.a))
        self.hit()
        self.assertEqual((1, 2), (self.a.working_c3_masters, self.a.total_c3_masters))
        self.assertFalse(self.a.crit_status & CritStatus.C3_DESTROYED)
        self.assertEqual(3, c3.maximum(self.a, self.a.c3_network))
        self.assertEqual((3, self.a._id), c3.range_query(self.b, self.c, 12))
        c3.validate(self.a)
        self.assertEqual(3, c3.network_size(self.a))
        joining = self.make_unit(30, 'J')
        joining.contact_id = 'JJ'
        result = c3.command(joining, joining.pilot, 'join', 'AA')
        self.assertFalse(result['ok'])
        self.assertIn('maximum capacity', result['error'])
        self.hit(1)
        self.assertEqual(1, self.a.working_c3_masters)
        self.assertEqual(1, self.a.pilot.inbox.count('One of your C3 systems has been destroyed!'))
