Contains LiveTrack precalculated raster info ("Weathering-In")
Raster format is efficient, only storing cells with data
https://www.youtube.com/watch?v=bMdkxhRjoqs

Contains the following channels:
* friction
	* Racing line proximity
* height
	* Water pooling areas
* grip
	* Rubbered areas
* flags
	* 8 bit flags, in any combination
		* 0. Racing line
		* 1. Asphalt area
		* 2. Dirt/gravel/marbles 1?
		* 3. Dirt/gravel/marbles 2?
		* 4. Dirt/gravel/marbles 3?
		* 5. Unseen
		* 6. Curbs
		* 7. Unseen
* mask
	* Areas with data