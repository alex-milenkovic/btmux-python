"""Reviewed existing independent consumers rerun through the Core CLI.

Scope: mech.utils ammunition lookup/expenditure, multi-selector consumers,
mech.events AMS recycle and unjam, and shared ECM/heat consumers. No historical
PASS is imported. Assertions and source-specific fixtures were reread for recovery.
"""
from copy import deepcopy
from core_simulation_qa import case
from combat_supplemental import ammunition_cases,more_mode_cases,equipment_cases
from combat_remaining import cases as remaining
from combat_extended import impact_cases


def build():
    selected=[('ammunition',c) for c in ammunition_cases()]
    selected += [('weapons',c) for c in more_mode_cases()]
    selected += [('ammunition',c) for c in equipment_cases() if 'unjam' in c.label]
    selected += [('ammunition' if c.label.startswith(('ammunition','missiles-AMS')) else 'parts',c) for c in remaining() if c.label.startswith(('ammunition-RAC','missiles-AMS','equipment-ECM-shared','equipment-signature-live'))]
    selected += [('ammunition',c) for c in impact_cases() if 'gattling' in c.label.lower()]
    for family,item in selected:
        d=deepcopy(item.document)
        if d.get('units') and len(d['units'])>1:d['units'][0].setdefault('target',2)
        streams=d.setdefault('random',{}).setdefault('streams',{})
        for name,values in {'visibility_change':[0]*1000,'failure_generic_chance':[5000]*1000,
                'failure_weapon_chance':[1]*1000,'failure_reliability':[12]*1000,'tow_rolls':[7]*1000,
                'sensor.detect':[1]*1000,'sensor.random':[0]*1000,'fuel_check':[1]*1000}.items():
            streams.setdefault(name,values)
        ordinary=d.get('config',{}).get('periodic_updates') is not False and all(a['op'] in ('command','advance','inspect') for a in d['actions'])
        case(family,'consumer-'+item.label,d.pop('actions'),[],checker=item.check,mode='ordinary' if ordinary else 'diagnostic',**d)
