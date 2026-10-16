# Repair economy part maintenance 01 replacement outcomes
# Repair economy part maintenance 02 repair and enhanced outcomes
Feature: Repair economy part maintenance

  Background:
    Given the repair economy source contract and isolated shared engine fixture

  Scenario Outline: Repair economy part maintenance 01 replacement outcomes
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | broken nonweapon stock2 brand0 general success | replacepart then advance2700 | stock1 part repaired at2700 not2699 |
      | broken nonweapon stock2 initial fail recovery success | replacepart then advance4020 | stock2 part unchanged and fake consumed |
      | broken nonweapon stock2 both rolls fail | replacepart then advance4020 | stock1 part unchanged and fake consumed |
      | broken ammo stock0 general success | replacepart then advance2700 | ammo repaired data0 and no negative stored entry |
      | broken gun width2 stock2 weapon success | replacegun then advance7200 | stock1 both slots repaired only at7200 |
      | broken gun width2 stock2 first fail recovery success | replacegun then advance10800 | stock2 both slots unchanged |
      | broken gun width2 stock2 both rolls fail | replacegun then advance10800 | stock1 both slots unchanged |
      | broken gun oldbrand1 requestedbrand2 stock0 | replacegun | refuse stock but slot brand2 remains |
      | broken gun oldbrand1 requestedbrand2 stock2 success | replacegun before due | stock1 slot brand1 until event |
      | broken gun oldbrand1 requestedbrand2 stock2 success | replacegun at due | slot brand2 and repaired |
      | functional gun width2 stock2 | replacegun | refuse functional without dice or stock change |
      | broken gun second slot selected | replacegun | refuse not mount first |
      | flooded section broken part stock2 | replacepart | refuse flooded without resource debit |

  Scenario Outline: Repair economy part maintenance 02 repair and enhanced outcomes
    Given repair economy state <initial>
    When the repair economy user performs <operation>
    Then the repair economy observation is <expected>

    Examples:
      | initial | operation | expected |
      | undestroyed gun width2 tempnuke1 electronics1 internal1 success | repairgun and advance1200 | both slots repaired using live callback under source type53 |
      | undestroyed gun width2 BROKEN only tempnuke0 | repairgun | refuse no applicable temporary damage |
      | undestroyed gun width2 disabled tempnuke1 | repairgun | refuse disabled |
      | selected destroyed gun width4 second intact | repairgun | refuse short destroyed weapon |
      | selected destroyed gun width5 second intact stock3 each success | repairgun | debit3 each and queue extra-hard repair |
      | selected destroyed gun width5 second intact stock3 each fail | repairgun | debit3 each destroy second slot now and fake1800 |
      | selected destroyed gun width5 second destroyed | repairgun | refuse both destroyed |
      | undestroyed gun tempnuke1 electronics1 internal0 | repairgun | refuse missing internal and retain electronics1 |
      | nonweapon tempnuke1 electronics1 internal1 success | repairpart and advance900 | selected slot repaired at900 |
      | nonweapon tempnuke1 electronics1 internal1 fail | repairpart and advance1320 | stock consumed and slot unchanged |
      | nonweapon destroyed electronics3 internal3 | repairpart | refuse destroyed part |
      | gun width3 damaged middle slot electronics1 success | fixenhcrit and advance900 | middle damage cleared first tempnuke0 other damage retained |
      | nonweapon damaged flag electronics1 | fixenhcrit | refuse nonweapon |
      | intact gun middle slot electronics1 | fixenhcrit | refuse no enhanced damage |
