Some tracks also specify other files in `/_data/physics`, `/_data/pitgarages`, `/_data/animatedsigns/`, etc., but that implies that they’re not required for every track.

🟦Already human-readable
❓Unseen, only referenced
✅Fully documented
🟨Partially documented
🔴Undocumented
### LST List
* `/tracks/_data/tracklist.lst`
  * Lists all tracks to be loaded by the game
  * 🟦Already human-readable
### TRD Track Data
* `/tracks/trackname/trackname.trd`
  * XML
  * Contains all generic info about the track (name, short name, year, length…)
  * 🟦Already human-readable
### CSM Cooked Surface Mesh
* `/tracks/trackname/physics/trackname.csm`
	* [[CSM]]
### SGX Scene Graph XML
* `/tracks/trackname/trackname.sgx`
  * Human-readable scenegraph for the track
  * Only one found in the base game is the showroom (menu\_background.sgx), but extrapolations can be made off of that and the decompilation
  * Track Data files always seem to reference SGX extensions, not SGBs, and the game loads SGXs, but falls back to the packed SGBs if SGXs aren’t found
  * SGX files can't reference IMB instance meshes or VHF instance hierarchies
  * 🟦Already human-readable
### SGB64 Scene Graph Binary 64bit
* `/tracks/trackname/trackname.sgb64`
  * Binary packed scenegraph
  * SGB64 files can reference IMB instance meshes and VHF instance hierarchies unlike SGX files
  * 🔴Undocumented
### ENX Environment XML
* `/tracks/trackname/trackname.enx`
  * Contains references to background environment meshes, if used
  * Used often in PC2, not used often in AMS2 (file still present, but containing only boilerplate XML)
  * 🟦Already human-readable
### MEB Mesh Binary
* `/tracks/trackname/[MODEL].meb`
  * [[MEB]]
### IMB Instance Mesh Binary
* `[MODEL].imb`
  * Contains mesh data about visual objects placed from VHF scenegraphs
  * Commonly used for vegetation and repetitive trackside objects
  * Can be encrypted?
  * 🔴Undocumented
### MTX Material XML
* `/tracks/trackname/[MATERIAL].mtx`
  * Human-readable material configuration for each object
  * Used in PC2; not seen yet in AMS2 but AMS2 loads and uses them just fine
  * 🟦Already human-readable
### BMT Binary Material
* `/tracks/trackname/[MATERIAL].bmt`
  * Binary packed material configuration
  * PCarsTools repository has a BLMY.bt that might match up with this format
  * 🟨Partially documented
### ENV.XML Environment Physics XML
* `/tracks/_data/dynamic/physics/trackname.env.xml`
  * Contains listings of all dynamic physics track objects (cones, etc.)
  * Contains world transform matrices for each object in mat4x4 format, single line of 16 floats, semicolon separated
  * 🟦Already human-readable
### VHF Vehicle/Instance Hierarchy XML
* `/tracks/_data/static/[MODEL_LODX].vhf`
  * Contains assorted info about the instance, serving as a mini-scenegraph
  * Formatted similarly but distinctly differently from SGX files, and the formats are not compatible
    * LOD info
    * Sphere center in vec4 + radius
    * Matrix offset in vec3 + orientation in vec4 + scale
    * Node info, with resource pointer and sphere center in vec4 + radius
  * 🟦Already human-readable
### AIW AI Waypoints
* `/tracks/_data/aiw/trackname.aiw`
	* [[AIW]]
### LSD Sound Location Data XML
* `/tracks/_data/audio/trackname.lsd`
  * “Sound Location Data”
  * Sound location and parameters in XML format
  * 🟦Already human-readable
### LOD Crowd Level-of-Detail Override XML
* `/tracks/_data/crowds/trackname.lod`
  * “Crowd LOD”
  * Contains crowd-object-specific LOD distances
  * Defines substring matches for overriding a global parameter set at the end
  * 🟦Already human-readable
### MRDF Machine-Readable Data Format
* `.mrdf`
  * “Machine-Readable Data Format”
  * Binary packed data
  * General purpose packed binary data format, parsed ad-hoc with many custom internal formats
  * `/tracks/customtrack/trackproperties.bin` is an MRDF containing at least animation wiring
  * 🟨Partially documented
### HRDF Human-Readable Data Format
* `.hrdf`
  * “Human Readable Data Format”
  * Generic data container; like MRDF, but human readable
  * ❓Unseen, only referenced
### LiveTrack MRDF
* `/tracks/_data/livetrack/trackname.mrdf`
	* [[LiveTrack MRDF]]
### GCL Grid Cells/Cut Lines
* `/tracks/trackname/track_cut/trackname.gcl`
	* [[GCL]]