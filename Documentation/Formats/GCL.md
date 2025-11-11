Path: `/tracks/trackname/track_cut/trackname.gcl`

Format:
- Header (32 bytes)
	- Version/magic (01 00 00 10)
	- Triangle count (int)
	- Float x4
	- Flag x2
- Triangle data (40 bytes)
	- Float x3
	- Float x3
	- Float x3
	- Flag
		- 0x1 = Racing surface
		- 0x2 = Pit area
			- Doesn't usually line up with pit speed limit lines
		- 0x4 = Pit exit
			- Usually aligned with white line boundary
		- 0xA = Pit entry
- LiveTrack cell dectree
	- Contains three levels: 100x100m, 10x10m, and 1x1m
	- Each cell can contain zero or more references to the above triangles as indices
		- Each cell references every triangle that overlaps its area
		- Cells are listed in sequential, nested order