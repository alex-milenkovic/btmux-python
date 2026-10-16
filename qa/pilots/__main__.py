import argparse
from qa.pilots.character import run_character,run_skills,run_experience
from qa.pilots.health import run_health,run_initialization,run_personal

from qa.pilots.personnel import run_boarding,run_ejection,run_carriers

from qa.pilots.battle import run_swarm,run_hiding

from qa.pilots.awards import run_awards

from qa.pilots.workflows import run_workflows

from qa.pilots.extra import run_extra

def main():
    runners={'character':run_character,'skills':run_skills,'experience':run_experience,
             'health':run_health,'initialization':run_initialization,'personal':run_personal,
             'boarding':run_boarding,'ejection':run_ejection,'carriers':run_carriers,'swarm':run_swarm,'hiding':run_hiding,'awards':run_awards,'workflows':run_workflows,'extra':run_extra}
    parser=argparse.ArgumentParser();parser.add_argument('--family',choices=runners);args=parser.parse_args()
    results=[run() for key,run in runners.items() if not args.family or key==args.family]
    return int(any(r['failures'] for r in results))
if __name__=='__main__':raise SystemExit(main())
