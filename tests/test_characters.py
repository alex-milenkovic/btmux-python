"""Source character storage and progression, independent of CLI fixtures."""
import tempfile
import unittest
from pathlib import Path
from data.characters import CharacterStore, Stats, ALL, HEALTH, ATTRS, SKILLS, ADVS
from data.character_values import code, VALUES, XP_MAX
from systems.characters import skill_target, gain_xp, next_threshold, lower_xp, set_value, has_advantage


class CharacterTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.store=CharacterStore(self.root);self.store.create(101,'Alice')

    def test_source_table_aliases_and_byte_coupling(self):
        self.assertEqual(119,len(VALUES));self.assertEqual(107,code('TecBat'))
        self.assertEqual(108,code('Technician-Battlesuit'));self.assertEqual(-1,code('missing'))
        s=Stats.fresh();s.set('Build',-1);s.set('ShotsHit',3)
        self.assertEqual((255,4),(s.get('Build'),s.get('Lives')))
        s.set('ShotsHit',0);self.assertEqual(1,s.get('Lives'))
        s.last_use[0]=40;s.clear();self.assertEqual(40,s.last_use[0])

    def test_category_retrieval_order_and_malformed_reset(self):
        rec=self.store.records[101];rec['categories']={'health':'2,3tail','attrs':'5,4,3,2,1','skills':'Runni:4/','advs':'Lives:2/Tough:1/'}
        s=self.store.retrieve(101,HEALTH)
        self.assertEqual((0,2,3,0),(s.get('Build'),s.get('Bruise'),s.get('Lethal'),s.get('Lives')))
        rec['categories']['attrs']='bad'
        s=self.store.retrieve(101,ALL)
        self.assertEqual((1,0,1,0),(s.get('Build'),s.get('Bruise'),s.get('Lives'),s.get('Running')))
        self.assertEqual('1,1,1,1,1',rec['categories']['attrs'])

    def test_generic_prior_writes_and_conditional_xp_fields(self):
        self.store.records[101]['categories']['skills']='Running:2,9,40/Running:3,0,0/Unknown:9/Blade:4/bad/Computer:5/'
        s=self.store.retrieve(101,SKILLS);i=code('Running')
        self.assertEqual((3,9,40,4,0),(s.get(i),s.xp[i],s.last_use[i],s.get('Blade'),s.get('Computer')))

    def test_d1_skill_and_advantage_roundtrip_and_source_alias_loss(self):
        s=Stats();s.set('Lives',1);s.set('Toughness',2);s.set('Running',2)
        i=code('Running');s.xp[i]=XP_MAX+101;s.last_use[i]=40
        self.store.store(101,s,ADVS|SKILLS)
        self.assertEqual('Lives:1/Tough:2/',self.store.records[101]['categories']['advs'])
        self.assertEqual('Runni:2,16777317,40/',self.store.records[101]['categories']['skills'])
        other=CharacterStore(self.root);r=other.retrieve(101,ADVS|SKILLS)
        self.assertEqual((1,2,3,40),(r.get('Lives'),r.get('Toughness'),r.get('Running'),r.last_use[i]))
        self.assertFalse(has_advantage(other,101,'Toughness'))
        r.set('Technician-Battlesuit',3);other.store(101,r,SKILLS)
        result=CharacterStore(self.root).retrieve(101,SKILLS)
        self.assertEqual((3,0),(result.get('Technician-Battlemech'),result.get('Technician-Battlesuit')))

    def test_missing_defaults_and_nonplayer_no_store(self):
        self.assertEqual(1,self.store.retrieve(101,ALL).get('Build'))
        self.store.create(102,'Object',is_player=False)
        before=dict(self.store.records[102]['categories'])
        self.store.store(102,Stats.fresh(),ALL)
        self.assertEqual(before,self.store.records[102]['categories'])
        self.assertEqual(0,self.store.retrieve(101,0).get('Lives'))

    def setup_gunnery(self):
        s=self.store.retrieve(101,ALL)
        for name in ('Build','Reflexes','Intuition','Learn','Charisma'):s.set(name,5)
        s.set('Gunnery-Battlemech',4);self.store.store(101,s,ALL)
        return code('Gunnery-Battlemech')

    def test_cache_invalidation_and_session_isolation(self):
        i=self.setup_gunnery();self.assertEqual(4,skill_target(self.store,101,i))
        s=self.store.retrieve(101,ALL);s.set('Reflexes',6);self.store.store(101,s,ATTRS)
        self.assertEqual(4,skill_target(self.store,101,i))
        self.assertEqual(3,skill_target(self.store,101,i,9,use_xp=False))
        self.assertEqual(3,skill_target(CharacterStore(self.root),101,i))
        self.store.store(101,s,ADVS);self.assertEqual(3,skill_target(self.store,101,i))
        self.store.clear_record(101);self.assertEqual((101,i,3),self.store.cache)
        self.assertEqual(16,skill_target(self.store,101,i))
        # Empty attrs trigger source lazy defaults/store-all on the preceding call,
        # so the previous cached result is invalidated before calculation.

    def test_strict_xp_thresholds_and_cumulative_next(self):
        i=self.setup_gunnery()
        for raw,bonus,nxt in ((3000,0,3001),(3001,1,12001),(12000,1,12001),(12001,2,39001)):
            s=self.store.retrieve(101,ALL);s.xp[i]=0;self.store.store(101,s,SKILLS)
            self.assertEqual(1,gain_xp(self.store,101,i,raw,now=100,override=True))
            s=self.store.retrieve(101,SKILLS)
            self.assertEqual(raw+bonus*XP_MAX,s.xp[i]);self.assertEqual(nxt,next_threshold(self.store,101,i))
        lower_xp(self.store,101,500)
        self.assertEqual(6000+XP_MAX,self.store.retrieve(101,SKILLS).xp[i])

    def test_cooldown_skxp_wrapping_and_disconnected_gain(self):
        i=self.setup_gunnery();ordinary=code('Blade')
        s=self.store.retrieve(101,ALL);s.last_use[ordinary]=100;s.xp[ordinary]=1
        self.store.store(101,s,SKILLS);self.store.records[101]['connected']=False
        self.assertEqual(0,gain_xp(self.store,101,ordinary,1,now=130))
        self.assertEqual(1,gain_xp(self.store,101,ordinary,1,now=131))
        s=self.store.retrieve(101,ALL);s.xp[i]=XP_MAX-1;self.store.store(101,s,SKILLS)
        self.assertEqual(1,gain_xp(self.store,101,i,1,now=0))
        self.assertEqual(0,self.store.retrieve(101,SKILLS).xp[i])

    def test_unsigned_values_and_unpersisted_values_remain_distinct(self):
        set_value(self.store,101,'Build',257)
        self.assertEqual(1,self.store.retrieve(101,ALL).get('Build'))
        set_value(self.store,101,'ShotsHit',3)
        s=self.store.retrieve(101,ALL)
        self.assertEqual((0,4),(s.get('ShotsHit'),s.get('Lives')))


class CharacterControlTest(unittest.TestCase):
    setUp=CharacterTest.setUp
    setup_gunnery=CharacterTest.setup_gunnery

    def test_threshold_change_applies_source_log_after_validation(self):
        from systems.characters import threshold_control
        threshold_control(self.store,'Running 25',caller=101)
        self.assertEqual(25,self.store.thresholds[code('Running')])
        effect=self.store.log_requests[-1]
        self.assertEqual(('LOG_WIZARD','WIZ','CHANGE'),tuple(effect[k] for k in ('category','primary','secondary')))
        self.assertEqual('Exp threshold for Running changed to 25 by #101',effect['text'])
        self.assertTrue(effect['applied'])
        with self.assertRaises(ValueError):threshold_control(self.store,'Running -1',caller=101)
        self.assertEqual([effect],self.store.log_requests)

    def test_controls_permission_order_flags_and_lists(self):
        from systems.characters import control,char_list,status,threshold_control,xp_top
        self.store.create(102,'Bob')
        with self.assertRaisesRegex(ValueError,'INVALID TARGET'):control(self.store,101,'get',target='missing',name='Build')
        with self.assertRaisesRegex(ValueError,'PERMISSION DENIED'):control(self.store,101,'get',name='Build')
        with self.assertRaisesRegex(ValueError,'authority'):control(self.store,101,'status',target='Bob')
        self.store.records[101]['wizard']=True
        self.assertEqual("Alice's Build set to 5",control(self.store,101,'set',name='Build',amount=5))
        self.assertEqual(5,control(self.store,101,'get',name='Build'))
        with self.assertRaisesRegex(ValueError,'ONLY SKILLS'):control(self.store,101,'set',name='Build',flag=1,amount=5)
        self.assertEqual(22,len(char_list(self.store,'advantages',102).split()))
        self.assertEqual('',char_list(self.store,'skills',102))
        set_value(self.store,101,'Toughness',2);set_value(self.store,101,'Contact',7)
        shown=status(self.store,101)
        self.assertIn('Toughness',shown['advantages']);self.assertIn('Contact: 7',shown['advantages'])
        self.assertEqual(['None'],shown['skills'])
        threshold_control(self.store,'Running 0');self.assertEqual(0,self.store.thresholds[code('Running')])

    def test_admin_xp_bth_and_leaderboard_source_tie_order(self):
        from systems.characters import control,xp_top
        i=self.setup_gunnery();self.store.records[101]['wizard']=True
        control(self.store,101,'set',name=i,flag=3,amount=3001,now=101)
        self.assertEqual([5,3,3001,4,12001],[control(self.store,101,'get',name=i,flag=f) for f in range(5)])
        control(self.store,101,'set',name=i,flag=1,amount=10)
        self.assertEqual(0,control(self.store,101,'get',name=i,flag=3))
        self.store.records[101]['wizard']=False
        for ident,name,xp in ((101,'Alice',100),(102,'Bob',100),(103,'Chris',200)):
            if ident!=101:self.store.create(ident,name)
            s=self.store.retrieve(ident,ALL);s.xp[i]=xp;self.store.store(ident,s,SKILLS)
        result=xp_top(self.store,'Gunnery-Battlemech')
        self.assertEqual([103,102,101],[r['id'] for r in result['rows']])
        self.assertEqual([50,25,25],[r['percent'] for r in result['rows']]);self.assertEqual(400,result['total'])

    def test_number_only_character_rolls_and_opposed_order(self):
        from systems.characters import roll_dice,skill_margin,opposed,attribute_success,duration
        from core.randomness import RandomState,use_simulation,use_source
        state=RandomState(42);seen=[];dice=iter([1,3,6,1,3,6,2,5])
        def source(name,lo,hi,fallback):seen.append((name,lo,hi));return next(dice)
        with use_simulation(state),use_source(source):
            self.assertEqual((9,4,7),(roll_dice('saving'),roll_dice('unskilled'),roll_dice('skilled')))
        self.assertEqual(0,state.total_rolls);self.assertEqual(8,len(seen))
        self.assertTrue(all(row==('character_d6',1,6) for row in seen))
        self.assertEqual('1 hour, 1 minute and 1 second',duration(3661))
        self.assertEqual('#-1 INVALID VALUE',duration(0))
        self.store.create(102,'Bob')
        set_value(self.store,101,'Running',1);set_value(self.store,102,'Running',1)
        dice=iter([6,6,1,1])
        with use_source(source):self.assertEqual(101,opposed(self.store,101,'Running',102,'Running'))
        with use_source(lambda *args: (_ for _ in ()).throw(AssertionError('unexpected draw'))):
            self.assertEqual(-1,attribute_success(self.store,101,'Unknown'))
