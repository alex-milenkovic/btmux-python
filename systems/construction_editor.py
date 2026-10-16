# BTMux Python reimplementation and adaptations (2026).
# Changes: C routines/data expressed in Python with local simulation services.
# This revision is present by 2026-10-12; attribution notice added 2026-10-12.
# Original authors and terms: CREDITS.md, LICENSE, and notices/BTMux.txt.
# General sources:
#   btech/mech.build.c
#   btech/mechrep.c

"""Local MECHREP command sessions, with source guard and sequential-write order."""
from data import templates as t
from data.construction_catalog import Catalog,source_weapon
from data.template_files import atof,diagnostic,_ams
from core.randomness import float32
from entities.mech import UnitType as U,MoveType as M,Specials as S,FireMode as F,AmmoMode as A,SectionConfig as C
from entities.crittypes import Special,i2special,i2weapon,i2ammo,is_ammo,crits_in_loc
from systems.damage_commands import armor_section_from_string,section_names,atoi
from systems.weapon_inventory import sync_weapon_states,weapon_crits,weapon_runs
from systems.construction_weight import invalidate
from systems.parts import armor_string
from systems.combat_ammunition import full_ammo

DATA_ERRORS=['There is a problem with that item.','The data is not properly allocated.','Please notify a director of this.']
SCALARS={'setspeed':('max_speed','Maxspeed',True),'setjumpspeed':('jump_speed','Jumpspeed',True),
 'setheatsinks':('real_num_sinks','Heatsinks',False),'setlrsrange':('lrs_range','LRSrange',False),
 'settacrange':('tac_range','TACrange',False),'setscanrange':('scan_range','SCANrange',False),
 'setradiorange':('radio_range','RADIOrange',False),'settons':('tonnage','Tons',False)}


def check_data(data,messages):
    if data is not None:return True
    messages.extend(DATA_ERRORS);return False


def invalid_section(unit):
    lines=['Not a legal armor location, must be one of:']
    if unit.unit_type in (U.MECH,U.MW):
        lines.append('HEAD (H), CTORSO (CT), LTORSO (LT), RTORSO (RT)')
        lines.append('LARM (LA), RARM (RA), LLEG (LL), RLEG (RL)' if unit.move_type==M.QUAD else 'FLLEG (FLL), FRLEG (FRL), RLLEG (RLL), RRLEG (RRL)')
    else:
        lines.append({U.VEH_GROUND:'FSIDE (FS), RSIDE (RS), LSIDE (LS), ASIDE (AS), TURRET (TU)',
          U.VEH_NAVAL:'FSIDE (FS), RSIDE (RS), LSIDE (LS), ASIDE (AS), TURRET (TU)',
          U.VTOL:'FSIDE (FS), RSIDE (RS), LSIDE (LS), ASIDE (AS), ROTOR (RO)',
          U.AERO:'NOSE (N), LWING (LW), RWING (RW), FUSELAGE (F), COCKPIT (C), ENGINE (E)',
          U.DS:'NOSE (N), LWING (LW), RWING (RW), LRWING (LR), RRWING (RR), ASIDE (AS)',
          U.SPHEROID_DS:'NOSE (N), FRSIDE (FR), FLSIDE (FL), RLSIDE (RL), RRSIDE (RR), ASIDE (AS)',
          U.BSUIT:'S1, S2, S3, S4, S5, S6, S7, S8'}.get(unit.unit_type,'Invalid or unknown unit type!'))
    return lines


def delinftech(unit):
    """The separate direct-unit C entrypoint deliberately has no editor guard."""
    if unit is None:raise ValueError('Missing unit')
    unit.infantry_specials=0;invalidate(unit)
    return 'Advanced Infantry Technology Deleted'


_AMMO_FLAGS={'W':A.SWARM_MODE,'#':A.MML_LRM_MODE,'1':A.SWARM1_MODE,'I':A.INFERNO_MODE,
 'L':A.LBX_MODE,'A':A.ARTEMIS_MODE,'N':A.NARC_MODE,'C':A.CLUSTER_MODE,'M':A.MINE_MODE,
 'S':A.SMOKE_MODE,'X':A.INARC_EXPLO_MODE,'Y':A.INARC_HAYWIRE_MODE,'E':A.INARC_ECM_MODE,
 'R':A.AC_AP_MODE,'F':A.AC_FLECHETTE_MODE,'D':A.AC_INCENDIARY_MODE,'P':A.AC_PRECISION_MODE,
 'T':A.STINGER_MODE,'U':A.AC_CASELESS_MODE,'G':A.SGUIDED_MODE,'H':A.ATM_HE_MODE,'V':A.ATM_ER_MODE}


def apply_mode(slot,flag,*,reload=False):
    flag=flag[:1].upper()
    if flag=='-':slot.firemode=slot.ammomode=0
    elif flag in _AMMO_FLAGS:slot.ammomode|=_AMMO_FLAGS[flag]
    elif reload and flag=='+':slot.firemode|=F.HALFTON_MODE
    elif reload and flag=='Z':slot.ammomode|=A.INARC_NEMESIS_MODE
    elif not reload and flag=='J':slot.firemode|=F.WILL_JETTISON_MODE


class Editor:
    def __init__(self,identity,units,*,directory=None,allocated=True):
        self.identity=identity;self.units=units;self.target=-1;self.allocated=allocated
        self.directory=directory;self.catalog=directory.catalog if directory else Catalog()
        self.messages=[]

    def resolve(self,name):
        if name in self.units:return self.units[name]
        text=str(name).removeprefix('#')
        return next((u for u in self.units.values() if str(u._id)==text),None)

    def notify(self,text):self.messages.append(text)

    def execute(self,command,arguments='',*,privilege=True,**options):
        self.messages=[];self.catalog_report=None;command=command.lower();unit=None
        if not privilege:return {'ok':False,'messages':["I'm sorry Dave, can't do that."]}
        if not check_data(self if self.allocated else None,self.messages):return {'ok':False,'messages':self.messages}
        if command!='settarget':
            if self.target==-1:return {'ok':False,'messages':['You must set a target first!']}
            unit=self.resolve(self.target)
            if not check_data(unit,self.messages):return {'ok':False,'messages':self.messages}
        sink_capacity=unit.real_num_sinks if unit is not None and command in ('addtech','deltech') else None
        try:
            result=self._command(unit,command,str(arguments),options)
            return {'ok':True,'messages':self.messages,'result':result}
        except (ValueError,OSError,OverflowError) as error:
            self.notify(str(error));result={'ok':False,'messages':self.messages}
            if self.catalog_report is not None:
                self.messages.extend(self.catalog_report['messages']);result['catalog']=self.catalog_report
            return result
        finally:
            if unit is not None:
                if sink_capacity is not None:unit.real_num_sinks=sink_capacity
                sync_weapon_states(unit)
                if command not in ('displaysection','showtech','loadnew','restore','savetemp','savetemp2'):invalidate(unit)
                unit.construction_managed=True

    def location(self,unit,text):
        loc=armor_section_from_string(unit,text)
        if loc<0:
            self.messages.extend(invalid_section(unit)[:-1]);raise ValueError(invalid_section(unit)[-1])
        return loc

    def position(self,unit,loc,text):
        pos=atoi(text)-1
        if not 0<=pos<crits_in_loc(unit,loc):raise ValueError('Critslot out of range!')
        return pos

    def weapon(self,text):
        index=self.catalog.weapon_index(text)
        if index<0:
            self.catalog_report=self.catalog.weapon_dump();raise ValueError('That is not a valid weapon!')
        return source_weapon(index)

    def _command(self,unit,command,buffer,options):
        caps={'settarget':2,'setradio':2,'setarmor':4,'repair':4,'addweap':20,'reload':4,'restock':2,'firemode':2,'addspecial':4,'setcargospace':2,'addbomb':3}
        args=t.parse_attributes(buffer,caps.get(command,1))
        if command=='settarget':
            if len(args[:2])!=1:raise ValueError('Too many arguments!')
            target=self.resolve(args[0])
            if target is None:raise ValueError('That is not a BattleMech or Vehicle!')
            self.target=args[0];self.notify(f'Mech to repair changed to #{target._id}');return
        if command=='resetcrits':self.notify('Default criticals set!');t.fill_default_criticals(unit);return
        if command=='displaysection':
            if not args:raise ValueError('You must specify a section to list the criticals for!')
            loc=armor_section_from_string(unit,args[0])
            if loc<0:raise ValueError('Invalid section!')
            from systems.status_display import critical_display
            result=critical_display(unit,loc);self.messages.extend(result['lines'])
            result['raw_slots']=[{'slot':pos+1,**vars(slot)} for pos,slot in enumerate(unit.sections[loc].criticals[:crits_in_loc(unit,loc)])]
            return result
        if command in SCALARS:
            field,label,floating=SCALARS[command]
            if not args:raise ValueError(f'Invalid number of arguments to Set{label}!')
            value=float32(atof(args[0])*10.75) if floating else atoi(args[0])
            if floating:
                import math
                if not math.isfinite(value):raise ValueError('nonfinite source float')
            setattr(unit,field,value)
            self.notify(f'{label} changed to {value:.2f}.' if floating else f'{label} changed to {value}.');return
        if command=='setradio':
            if not args:raise ValueError('This remains to be done [showing of stuff when no args]')
            if len(args)>1:raise ValueError('Too many args, unable to cope().')
            unit.radio=max(1,min(5,atoi(args[0])));unit.radio_type=t.generic_radio_type(unit.radio,False)
            self.notify(f'Radio level set to {unit.radio}.');self.notify(f'Number of freqs: {unit.radio_type%16}  Extra stuff: {(unit.radio_type//16)*16}')
            unit.radio_range=int(t.computers_radio_range(unit));self.notify(f'Radio range set to {unit.radio_range}.');return
        if command in ('settype','setmove'):
            if not args:raise ValueError('Invalid number of arguments!')
            text=args[0].upper()
            if command=='settype':
                choices={'M':(U.MECH,M.BIPED,'MECH'),'Q':(U.MECH,M.QUAD,'QUAD'),'G':(U.VEH_GROUND,None,'VEHICLE'),
                 'V':(U.VTOL,M.VTOL,'VTOL'),'N':(U.VEH_NAVAL,None,'NAVAL'),'A':(U.AERO,M.FLY,'AeroSpace'),
                 'D':(U.DS,M.FLY,'DropShip'),'S':(U.SPHEROID_DS,M.FLY,'SpheroidDropship'),'B':(U.BSUIT,M.BIPED,'BattleSuit')}
                if text[0] not in choices:raise ValueError('Types are: MECH, GROUND, VTOL, NAVAL, AERO, DROPSHIP and SPHEROIDDROPSHIP')
                kind,move,label=choices[text[0]];unit.unit_type=kind
                if move is not None:unit.move_type=move
                self.notify(f'Type set to {label}')
            else:
                choices={'T':(1,'TRACKED'),'W':(2,'WHEELED'),'V':(4,'VTOL'),'Q':(8,'QUAD'),'B':(0,'BIPED'),'S':(9,'SUB'),'N':(10,'NONE')}
                if text[0]=='H':
                    choice={'O':(3,'HOVER'),'U':(5,'HULL')}.get(text[1:2])
                    if choice is None:return
                elif text[0]=='F':
                    if text[1:2] in ('O','L'):self.notify('Movement set to '+('FOIL' if text[1]=='O' else 'FLY'))
                    choice=(10,'NONE')
                else:choice=choices.get(text[0])
                if choice is None:raise ValueError('Types are: TRACK, WHEEL, VTOL, QUAD, BIPED, HOVER, HULL, FLY, SUB, FOIL and NONE')
                unit.move_type,label=choice;self.notify('Movement set to '+label)
            return
        if command=='setarmor':
            if not args:raise ValueError('Invalid number of arguments!')
            loc=self.location(unit,args[0]);sec=unit.sections[loc]
            for text,field,label in zip(args[1:4],('armor','internal','rear'),('Front armor','Internal armor','Rear armor')):
                value=atoi(text)
                if field=='rear' and loc not in (2,3,4):self.notify('Only the torso can have rear armor.');continue
                if value<0:self.notify('Invalid '+('armor' if field=='armor' else 'Internal armor' if field=='internal' else 'Rear armor')+' value!');continue
                setattr(sec,field,value);setattr(sec,field+'_orig',value);self.notify(f'{label} set to'+{'armor':'    : ','internal':' : ','rear':'     : '}[field]+str(value))
            return
        if command=='repair':return self.repair(unit,args[:4])
        if command=='addweap':return self.add_weapon(unit,args[:20])
        if command in ('reload','restock','firemode'):return self.ammunition(unit,command,args)
        if command=='addspecial':return self.add_special(unit,args[:4])
        if command=='addbomb':
            # Public construction affordance; reuse the template's physical part
            # parser. This does not simulate a drop or add a historical command.
            if len(args)!=3:raise ValueError('Usage: addbomb <Bomb_name> <section> <slot>')
            found=self.catalog.match('vlong',args[0])
            if found is None or not 385<=found['source_part_id']<394:
                raise ValueError('That is not a valid bomb!')
            loc=self.location(unit,args[1]);pos=self.position(unit,loc,args[2])
            from data.template_files import load_critical
            load_critical(unit,loc,f'CRIT_{pos+1}',args[0]+' 0 -',self.catalog)
            self.notify('Bomb added.');return
        if command in ('addtech','deltech','addinftech'):return self.technology(unit,command,buffer)
        if command=='showtech':
            result=show_tech(unit);self.messages.extend(result['messages']);return result
        if command=='setcargospace':
            if len(args[:2])!=2:raise ValueError('Invalid number of arguements!')
            cargo=atoi(args[0])*50
            if not 0<=cargo<=250000:raise ValueError("Doesn't that seem excessive?")
            unit.cargo_space=cargo;unit.car_max_ton=max(1,min(100,atoi(args[1])))
            self.notify(f'{cargo/100:3.2f} cargospace and {unit.car_max_ton} tons of maxton space set.');return
        if command in ('loadnew','restore','savetemp','savetemp2'):
            if self.directory is None:raise ValueError('Local template directory is not configured')
            if command=='loadnew':
                if not args or not self.directory.loadnew(unit,args[0],wrapper=True,notify=self.notify):raise ValueError('Unable to read that template.')
                self.notify('Template loaded.')
            elif command=='restore':
                if not self.directory.restore(unit,notify=self.notify):raise ValueError('Unable to restore this mech!.')
                self.notify('Restoration complete!')
            else:
                result=self.directory.save(unit,buffer,legacy=command=='savetemp',notify=self.notify,**options)
                self.notify('Saving complete!');return str(result)
            return
        raise ValueError(f'Unknown editor command: {command}')

    def repair(self,unit,args):
        from systems.repairs import repair_part,reattach
        if len(args)<2:raise ValueError('Invalid number of arguments!')
        loc=self.location(unit,args[0]);value=atoi(args[2]) if len(args)>2 else 0
        if value<0:raise ValueError('Illegal value for armor!')
        kind=args[1][0].upper();sec=unit.sections[loc]
        if kind=='A':sec.armor=value;self.notify('Armor repaired!')
        elif kind=='I':sec.internal=value;self.notify('Internal structure repaired!')
        elif kind=='R':
            if loc not in (2,3,4):raise ValueError('Only the center, rear and left torso have rear armor!')
            sec.rear=value;self.notify('Rear armor repaired!')
        elif kind=='C':
            if not 1<=value<=12:raise ValueError('Critical Location out of range!')
            repair_part(unit,loc,value-1);self.notify('Critical location repaired!')
        elif kind=='S':reattach(unit,loc);self.notify('Section reattached.')
        else:raise ValueError('Illegal Type-> must be ARMOR, INTERNAL, CRIT, REAR')

    def add_weapon(self,unit,args):
        if len(args)<3:raise ValueError('Invalid number of arguments!')
        loc=self.location(unit,args[1]);weapon=self.weapon(args[0]);count=len(args)-2
        flags=0
        for text in args[3:]:
            char=text[0].upper()
            flags|={'R':F.REAR_MOUNT,'T':F.ON_TC,'O':F.OS_MODE}.get(char,0)
            if char.isalpha():count-=1
        needed=weapon_crits(unit,weapon.index)
        if count<needed and needed<9:raise ValueError(f'Not enough critical slots specified! (Given: {count}, Needed: {needed})')
        if count>needed:raise ValueError(f'Too many critical slots specified! (Given: {count}, Needed: {needed})')
        if count<needed:self.notify(f'Weapon will be split! {needed-count} additional crits needed.')
        for text in args[2:2+count]:
            pos=atoi(text)-1
            if not 0<=pos<12:raise ValueError('Bad critical location!')
            slot=unit.sections[loc].criticals[pos];slot.type=i2weapon(weapon.index);slot.firemode=flags;slot.ammomode=0
        if count:_ams(unit,slot)
        self.notify('Weapon added.')

    def ammunition(self,unit,command,args):
        if command=='firemode':
            if len(args)<2:raise ValueError('MECHREP: Invalid Syntax. Try FireMode <Weapon#> <Mode>')
            from systems.weapon_modes import find_weapon_number_on_mech
            code,loc,pos=find_weapon_number_on_mech(unit,atoi(args[0]))
            if code<0:raise ValueError('Invalid Weapon #!')
            from entities.weapon import get_weapon_by_index
            weapon=get_weapon_by_index(code)
            if not weapon.ammo_per_ton:raise ValueError("That weapon doesn't require ammo!")
            slot=unit.sections[loc].criticals[pos]
            if slot.firemode&F.OS_MODE:self.notify('Keeping One Shot Mode!');slot.ammomode=0
            elif not slot.firemode&F.HALFTON_MODE:slot.firemode=slot.ammomode=0
            apply_mode(slot,args[1]);self.notify('Firemode changed!');return
        if command=='reload':
            if len(args)<3:raise ValueError('Invalid number of arguments!')
            weapon=self.weapon(args[0]);loc=self.location(unit,args[1]);pos=self.position(unit,loc,args[2])
            if not weapon.ammo_per_ton:raise ValueError("That weapon doesn't require ammo!")
            slot=unit.sections[loc].criticals[pos];slot.type=i2ammo(weapon.index)
            if not slot.firemode&F.HALFTON_MODE:slot.firemode=slot.ammomode=0
            if len(args)>3:apply_mode(slot,args[3],reload=True)
        else:
            if len(args)<2:raise ValueError('Invalid number of arguments!')
            loc=self.location(unit,args[0]);pos=self.position(unit,loc,args[1]);slot=unit.sections[loc].criticals[pos]
            if not is_ammo(slot.type):raise ValueError('Restock requires an ammunition slot')
            from entities.weapon import get_weapon_by_index
            from entities.crittypes import ammo2weapon_i
            if not get_weapon_by_index(ammo2weapon_i(slot.type)).ammo_per_ton:raise ValueError("That weapon doesn't require ammo!")
        slot.data=full_ammo(unit,loc,pos);self.notify('Weapon loaded!' if command=='reload' else 'Weapon restocked!')

    def add_special(self,unit,args):
        if len(args)<3:raise ValueError('Invalid number of arguments!')
        kind=self.catalog.special_index(args[0])
        if kind<0 and args[0].lower()!='empty':
            self.catalog_report=self.catalog.special_dump();raise ValueError('That is not a valid special object!')
        loc=self.location(unit,args[1]);pos=self.position(unit,loc,args[2]);slot=unit.sections[loc].criticals[pos]
        slot.type=i2special(kind) if kind>=0 else 0;newdata=atoi(args[3]) if len(args)>3 else 0;slot.data=newdata&255
        first={Special.TRIPLE_STRENGTH_MYOMER:S.TRIPLE_MYOMER_TECH,Special.MASC:S.MASC_TECH,Special.C3_MASTER:S.C3_MASTER_TECH,
          Special.C3_SLAVE:S.C3_SLAVE_TECH,Special.ARTEMIS_IV:S.ARTEMIS_IV_TECH,Special.ECM:S.ECM_TECH,
          Special.BEAGLE_PROBE:S.BEAGLE_PROBE_TECH,Special.LIGHT_BAP:S.LIGHT_BAP_TECH}
        second={Special.ANGELECM:0x1000,Special.TAG:0x8000,Special.C3I:0x20,Special.BLOODHOUND_PROBE:0x800,Special.TARGETING_COMPUTER:0x1000000}
        if kind in first:unit.specials|=first[kind]
        if kind in second:unit.specials2|=second[kind]
        if kind==Special.CASE:unit.sections[3 if unit.unit_type==U.VEH_GROUND else loc].config|=C.CASE_TECH
        if kind in (Special.SPLIT_CRIT_LEFT,Special.SPLIT_CRIT_RIGHT):slot.data=(slot.data-1)&255
        descriptions={Special.CASE:'CASE Technology added to section.',
          Special.TRIPLE_STRENGTH_MYOMER:"Triple Strength Myomer Technology added to 'Mech.",
          Special.MASC:"Myomer Accelerator Signal Circuitry added to 'Mech.",Special.C3_MASTER:"C3 Command Unit added to 'Mech.",
          Special.C3_SLAVE:"C3 Slave Unit added to 'Mech.",Special.ARTEMIS_IV:"Artemis IV Fire-Control System added to 'Mech.",
          Special.ECM:"Guardian ECM Suite added to 'Mech.",Special.ANGELECM:"Angel ECM Suite added to 'Mech.",
          Special.BEAGLE_PROBE:"Beagle Active Probe added to 'Mech.",Special.LIGHT_BAP:"Light Beagle Active Probe added to 'Mech.",
          Special.TAG:"TAG added to 'Mech.",Special.C3I:"Improved C3 added to 'Mech.",
          Special.BLOODHOUND_PROBE:"Bloodhound Active Probe added to 'Mech.",Special.TARGETING_COMPUTER:"Targeting Computer added to 'Mech."}
        if kind in descriptions:self.notify(descriptions[kind])
        if kind==Special.ARTEMIS_IV:self.notify(f'System will control the weapon which starts at slot {newdata}.')
        self.notify(f'Critical slot {armor_string(unit,loc)} ({pos+1}) filled.')

    def option_error(self,heading,choices):
        lines=[heading]+['\t'+choice for choice in choices]
        self.messages.extend(lines[:-1]);raise ValueError(lines[-1])

    def technology(self,unit,command,buffer):
        first=t.parse_bit_vector(t.SPECIALS_NAMES,buffer);second=t.parse_bit_vector(t.SPECIALS2_NAMES,buffer)
        if command=='addinftech':
            value=t.parse_bit_vector(t.INFANTRY_SPECIALS_NAMES,buffer)
            if unit.unit_type!=U.BSUIT:raise ValueError('That is not a valid target for infantry technologies. Try a Suit!')
            if value<0:self.option_error('Invalid infantry tech: Available techs:',t.INFANTRY_SPECIALS_NAMES)
            if not value:self.notify('Nothing set!');return
            unit.infantry_specials|=value;self.notify('Set: '+t.bit_names(t.INFANTRY_SPECIALS_NAMES,value));return
        delete=command=='deltech';word=buffer.lower()
        if first<0 and second<0 and not (delete and word in ('all','case')):
            self.option_error('Invalid tech: Available techs:',(('All','Case') if delete else ())+t.SPECIALS_NAMES+t.SPECIALS2_NAMES)
        if not first and not second:self.notify('Nothing specified' if delete else 'Nothing set!');return
        if not delete:
            if first>0:unit.specials|=first;self.notify('Set: '+t.bit_names(t.SPECIALS_NAMES,first))
            else:unit.specials2|=second;self.notify('Set: '+t.bit_names(t.SPECIALS2_NAMES,second))
            return
        for sec in unit.sections:
            kinds=set()
            if word=='all' and (sec.config&C.CASE_TECH or unit.specials&(S.TRIPLE_MYOMER_TECH|S.MASC_TECH)):
                kinds={Special.CASE,Special.TRIPLE_STRENGTH_MYOMER,Special.MASC};sec.config&=~C.CASE_TECH
            elif word=='case' and sec.config&C.CASE_TECH:kinds={Special.CASE};sec.config&=~C.CASE_TECH
            elif word=='triplemyomertech' and unit.specials&S.TRIPLE_MYOMER_TECH:kinds={Special.TRIPLE_STRENGTH_MYOMER}
            elif word=='masc' and unit.specials&S.MASC_TECH:kinds={Special.MASC}
            for slot in sec.criticals:
                if slot.type in {i2special(kind) for kind in kinds}:slot.type=0
        if word=='all':unit.specials=unit.specials2=0;self.notify('All Advanced Technology Removed')
        elif word=='case':self.notify('Case Technology Removed')
        else:
            if first>0:unit.specials&=~first
            else:unit.specials2&=~second
            self.notify(buffer+' Technology Removed')


def show_tech(unit):
    names=t.bit_names3(t.SPECIALS_NAMES,t.SPECIALS2_NAMES,t.INFANTRY_SPECIALS_NAMES,unit.specials,unit.specials2,unit.infantry_specials)
    cases=[armor_string(unit,i) for i,s in enumerate(unit.sections) if s.config&C.CASE_TECH]
    messages=['--------Advanced Technology--------']
    for flag,label in ((S.TRIPLE_MYOMER_TECH,'Triple Strength Myomer'),(S.MASC_TECH,'Myomer Accelerator Signal Circuitry')):
        if unit.specials&flag:messages.append(label)
    messages.extend('Cellular Ammunition Storage Equipment in '+name for name in cases)
    if unit.specials&S.CLAN_TECH:
        messages+=['Mech is set to Clan Tech.  This means:','    Mech automatically has Double Heat Sink Tech','    Mech automatically has CASE in all sections']
    descriptions=((1,S.DOUBLE_HEAT_TECH,'Mech uses Double Heat Sinks'),(1,S.CL_ANTI_MISSILE_TECH,'Clan style Anti-Missile System'),
      (1,S.IS_ANTI_MISSILE_TECH,'Inner Sphere style Anti-Missile System'),(1,S.FLIPABLE_ARMS,'The arms may be flipped into the rear firing arc'),
      (1,S.C3_MASTER_TECH,'C3 Command Computer'),(1,S.C3_SLAVE_TECH,'C3 Slave Computer'),(1,S.ARTEMIS_IV_TECH,'Artemis IV Fire-Control System'),
      (1,S.ECM_TECH,'Guardian ECM Suite'),(1,S.LIGHT_BAP_TECH,'Light Beagle Active Probe'),(2,0x1000,'Angel ECM Suite'),
      (1,S.BEAGLE_PROBE_TECH,'Beagle Active Probe'),(2,0x8000,'Target Aquisition Gear'),(2,0x20,'Improved C3'),
      (2,0x800,'Bloodhound Active Probe'),(1,S.ICE_TECH,'It has ICE engine'))
    for table,flag,label in descriptions:
        if (unit.specials if table==1 else unit.specials2)&flag:messages.append(label)
    for flag,label in enumerate(('Can swarm enemy units','Can mount friendly units','Can do anti-leg attacks',
        'Has CS Purifier Stealth','Has DC Kage Stealth','Has FWL Achileus Stealth','Has FC Infiltrator Stealth',
        'Has FC InfiltratorII Stealth','Must jettison backpack before jumping/using specials','Can jettison backpack')):
        if unit.infantry_specials&(1<<flag):messages.append(label)
    messages+=['Brief version (May have something previous hadn\'t):',names or '-']
    return {'names':names,'abbreviations':t.tech_list(unit),'case_sections':cases,
            'status':t.bit_names_delim2(t.SPECIALS_NAMES,t.SPECIALS2_NAMES,unit.specials,unit.specials2),'messages':messages}
