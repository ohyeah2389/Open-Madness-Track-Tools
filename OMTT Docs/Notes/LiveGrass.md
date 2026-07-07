LiveGrass is the Madness Engine's way of defining the placement and rendering of 3D grass blades for each track.
# Relevant Files
## `tracks/trackname/livegrass/trackname.enx`
- Environment XML
- Empty boilerplate, just as all the rest of the ENXs are
## `tracks/trackname/livegrass/trackname.lgc`
- Custom binary file format, small file
- Contains strings `sno`, `spr`, `sum`, `autwin`
- Probably defines season-specific data as well as which/how many `.lgs` scenegraphs to load
- Unique per track? Need to run hashes/variance across locations
## `tracks/trackname/livegrass/*_*.lgs`
- SGB64 scenegraph(s)
- Seem to define the placement of grass blade IMBs from `tracks/_data/livegrass/*.imb`, there are also VHFs under that same directory that might be loaded by other tracks' `.lgs` files
- Probably indexed/loaded by `.lgc`
## `tracks/trackname/livegrass/trackname.sgb`
- SGB64 scenegraph
- Seems to define the placement of "plate" meshes in the `tracks/trackname/livegrass/` folder
## `tracks/trackname/livegrass/*.meb`
- Standard MEB files, forming the shape of grass meshes from the main track ("plates")
- Reference a single material in BMT format
	- Material shader is `Render\Shaders\livegrass1_0.fx`, technique is `Basic`
	- Single param, `densitytexture`, which seems to be a greyscale (but DXT compressed) map of, presumably, grass blade density
## `tracks/_data/livegrass/*.imb`, `tracks/_data/livegrass/*.vhf`
- IMBs are hexagonal-shaped clusters of grass blade billboards in LODA through LODC variants, VHFs reference those in a LOD-configured format
- Reference BMTs from the same directory which pull textures from `tracks/textures/autograss/*.dds`

