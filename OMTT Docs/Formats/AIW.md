AIW files define the AI waypoints, garage and pit spots, standing and rolling start spawn points, and other info about the track pertaining to AI drivers.
The format of the AIW file is very similar to the formats used in Automobilista 1, rFactor 2, and other ISI-derived games, with some distinct differences.
Waypoints should be spaced at least 3m apart; narrower spacing may result in jittery and overly cautions AI tracking.
Corners must be assigned or the AI won't know when and where to slow down, resulting in them voluntarily flinging themselves off the track.

(hint: assign all corner areas to a "Corner" vertex group for assistance with the below)
### wpd_CornerType (`corner_type` in Blender)
0. Straight
1. Unknown
2. Unknown
3. Left turn
4. Right turn
5. Loose chicane
6. Tight chicane
### wpd_CornerState (`corner_state` in Blender)
0. Straight
1. Entry
2. Apex
3. Exit
(hint: to assign, select all corners, assign as Exit, then deselect the exits, then assign as Apex, then deselect the apexes, then assign the remaining as Entry)

The same fields can instead be authored with special name-prefixed empties near `SMS_AIW_CENTERLINE`. 
If any of these empties are present, they replace the vertex attributes above for the whole centerline.
- Per corner, in travel order: `SMS_AIW_CS_ENTRY`, `SMS_AIW_CS_APEXSTART`, `SMS_AIW_CS_APEXEND`, `SMS_AIW_CS_EXIT`
- One type empty between that ENTRY and EXIT: `SMS_AIW_CT_LEFT` (3), `SMS_AIW_CT_RIGHT` (4), `SMS_AIW_CT_LOOSECHIC` (5), `SMS_AIW_CT_TIGHTCHIC` (6)
