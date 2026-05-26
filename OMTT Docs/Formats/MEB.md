The MEB (Mesh Binary) format is the Madness engine's proprietary model format for non-instanced meshes.
Instanced meshes use their own, slightly different model format, IMB, which is very similar.
They support storing vertex colors, tangents/bitangents, and 6 UV and 2 UVW maps (max seen so far).

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

The vertex positions can be "encrypted" through a transposition of the X coordinate. Further details about this will not be given.
### Track Modeling Info
MEB files defining the track surface need to contain extra information for certain visual attributes to work properly. This consists of a certain arrangement of UV maps and vertex colors.
#### File name:
All MEB files' UV coordinates are internally converted to 16-bit floats by the game before display, probably for performance and VRAM reasons. This can cause quantization artifacts on meshes with large UV coordinates, such as ground surfaces. To prevent this, `_no_uv_comp` can be added to the end of the MEB filename to skip this "UV compression". The Blender exporter is set up to always export UV map data as 32-bit floats.
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