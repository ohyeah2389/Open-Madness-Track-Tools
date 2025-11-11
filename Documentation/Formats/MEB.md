The MEB (Mesh Binary) format is the Madness engine's proprietary model format for non-instanced meshes. (Instanced meshes use their own, slightly different model format, IMB.) They support storing vertex colors, tangents/bitangents, and 6 UV and 2 UVW maps (max seen so far).

The files are chunked into sections with the following magic numbers:
- Vertex positions
	- 02 00 00 00, 00 00 00 00, 00 00 00 00
- Normals
	- 02 00 00 00, 02 00 00 00, 00 00 00 00
- Colors
	- 04 00 00 00, 06 00 00 00, 00 00 00 00
- Tangents
	- 02 00 00 00, 04 00 00 00, 00 00 00 00
- Bitangents
	- 02 00 00 00, 05 00 00 00, 00 00 00 00
- Bodywork data
	- 00 00 00 00, 03 00 00 00, 03 00 00 00
- Alternative vertex positions
	- 14 00 00 00, 00 00 00 00, 00 00 00 00
- UV maps
	- 01 00 00 00, 00 00 00 00, (00 - 05) 00 00 00
- UVW maps
	- 02 00 00 00, 03 00 00 00, (00 - 01) 00 00 00

The vertex positions can be "encrypted" through a transposition of the X coordinate. Further details will not be given.
### Track Modeling Info
MEB files defining the track surface need to contain extra information for certain visual attributes to work properly. This consists of a certain arrangement of UV maps and vertex colors.
#### File name:
The filename of the mesh needs to contain the string `_no_uv_comp`. The game explicitly checks for this to apply the special visual attributes.
#### Material:
Use the material Road DBV (`road_dbv`) for these track surface objects. 
#### Vertex colors:
- Red: On racing line/travelled area (rubbered area), brighter at heavier rubbered areas
- Green: Skidmarked areas (braking areas, pits, starting spots, tight corners, corner exits)
- Blue: Outside racing line near heavy cornering areas (marbles, tire debris)
#### UV maps:
1. Fine detail texture (stones)
2. Broad detail texture (repeating road texture)
3. Base texture (satellite)
4. Groove/water texture (follows racing line)
5. Groove/water texture (follows racing line)