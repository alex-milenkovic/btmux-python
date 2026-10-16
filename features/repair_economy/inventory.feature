# Repair economy damage and scrap reports 01 damage ordering and dispatch
# Repair economy damage and scrap reports 02 scrap inventory and status
Feature: Repair economy damage and scrap reports

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy damage and scrap reports 01 damage ordering and dispatch
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | Mech CT destroyed with damaged LA | build damage table diagnostic | CT reattach only |
      | Mech CT destroyed with damaged LA | damages | scrap plan instead of CT reattachment |
      | Mech CT flooded with damaged LA | damages | CT reseal only |
      | Mech LT destroyed and damaged LA RT | damages | LT reattach then RT work with LA suppressed |
      | Mech CT internal8 original10 armor5 original10 rear3 original5 | damages | internal2 only before part rows |
      | Mech CT internal10 original10 armor5 original10 rear3 original5 | damages | front5 then rear2 before part rows |
      | BA one destroyed member | damages | replace-suit row |
      | live section ammo partial broken | damages | reload row before part replacement row |
      | gun enhanced focus and crystal flags | damages | focus row only for that critical |
      | gun enhanced crystal and barrel flags | damages | crystal row only for that critical |
      | undestroyed gun tempnuke1 width2 | damages | temporary gun repair row and skip second slot |
      | destroyed gun width2 | damages | gun replacement row and skip second slot |
      | pristine Mech | damages | pristine mech message and empty machine list |
      | pristine ground vehicle | damages | pristine unit message and empty machine list |
      | three snapshot rows | fix 3-2 | no dispatch and no work |
      | three snapshot rows | fix 0-2 | invalid low and no work |
      | three snapshot rows | fix 1-4 | invalid high and no work |
      | three snapshot rows | fix 2 | dispatch second row once |
      | three damage rows armor2 stock2 then broken actuator stock0 then broken sink stock1 | fix 1-3 | first and third jobs queued second refuses stock with original indices |

  Scenario Outline: Repair economy damage and scrap reports 02 scrap inventory and status
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | unfixable Mech RA intact removable part | scrap table | RA part removal before any RT traversal |
      | unfixable Mech RA pending section removal | scrap table | RA detach row then RT traversal |
      | unfixable Mech section broken part only path clear | scrap table | skip broken part and offer detach |
      | unfixable Mech section nonempty ammo no queued work | scrap table | unload row and no detach |
      | unfixable Mech section nonempty ammo queued reload | scrap table | unload row and detach when path clear |
      | front armor repair queued same loc | damage report | front row in-progress with N/A time and BTH |
      | rear armor repair queued encodedloc12 | damage report CT | rear row in-progress front row not marked |
      | fake part replacement queued | damage report | part row in-progress despite no eventual repair |
      | ammo8 capacity10 not queued | machine report | reload data name:2 and in-progress0 |
      | ammo8 on scrap list | machine report | unload data name:8 and in-progress0 |
      | weapon width1 tempnuke followed width6 tempnuke | human report | second temporary BTH retains extra_hard0 from first |
      | weapon width6 tempnuke followed width1 tempnuke | human report | first temporary BTH uses extra_hard1 then second0 |
