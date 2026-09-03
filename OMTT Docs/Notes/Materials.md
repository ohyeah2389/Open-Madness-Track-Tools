Each mesh file can reference one or more different material definition files. 

There are two formats of material definition files: MTX, which is used for content running unpacked (not inside a BFF pakfile), and BMT/BML, which are used for content running packed (inside a BFF pakfile).

The MTX format must be used when running unpacked. MTX files will not work when running packed content. The inverse is true for BMT/BML files.

Generally, BMT files are used for track materials and BML files are used for car materials. 

Both filetypes (MTX and BMT/BML) store the same content; there is no content loss when translating between each format. 

MTX files use an XML-like format and are human-readable and editable. BMT/BML files use a proprietary binary-packed file format and are not human-readable or easily human-editable. 

---
Material definition files store the following content:
- Shader
- Shader technique (some shaders only have one technique)
- Supports Specialized Lighting
- Fog
- Antialias
- Cull Mode
- Depth Test
- Depth Write
- Alpha Blend
- Parameters
- Defines

Parameters make up the bulk of the unique input controls to each shader. They can be of the following types:
- EPT_TEXTURE: contains a path to a texture file (either on-disk or in the virtual BFF structure) relative to the game root, such as `tracks/textures/trackname/texture.dds`
- EPT_F32: a floating point value
- EPT_VEC4: four floating point values
- EPT_BOOL: a true/false value

Defines are used to switch certain shader-specific behavior on or off, such as `USE_SPECULAR_MAP` or `USE_ALPHATEST`. Defines are either present or not present; their presence is what triggers their behavior. 

> The game engine is VERY SENSITIVE to the order in which these are present in the file; if they are out of order, the material will not load and all meshes using it will be invisible. This is because the game includes precompiled shader permutation binaries instead of more generic shader code. It is unlikely that a shader with a combination of included defines and parameters that is not represented by a packed shader permutation binary will load correctly.

> The PC2 and AMS2 shader database files present in toolkit releases v0.2.0 and above contains information that provides guidance on if your selection of shader defines does not match those of an existing shader permutation binary. It will not prevent you from exporting MTX files that appear to be invalid, it simply provides a warning that the configuration of that shader is not one that has been seen in the set of shader permutations. It will also attempt to provide a similar valid set of defines, with a button to modify your define set to match that valid configuration. If the define set is packed, it will also warn when parameters bound by that permutation are not enabled, with a button to enable the missing ones. Extra leftover parameters are not treated as an error. If you apply a packed define suggestion, make sure to re-check the validity of the selected shader parameters, as these are not automatically reconfigured.

---
Below are usage notes for specific shaders.

# `basic`

This is a legacy shader from Project CARS 2. This shader exhibits poor shadow bias behavior, causing erroneous shadow artifacts on surfaces angled from the camera's direction.

# `rz_basic`

This shader is new for AMS2. Despite its name, this shader is very flexible and packed with many capabilities, such as separate AO textures, detail textures, emissive textures, second-channel diffuse and emissive textures, normal and specular maps, more flexible Fresnel behavior, complex tinting, and more.

# `new_ground`

This is a legacy shader from Project CARS 2. As its name suggests, this shader is used for ground materials, like grass, dirt, sand, and others, but not asphalt or concrete materials, which should use the road-specific shaders like `road_dbv` or `rz_road_main_3diffuse`.

It takes six textures, mapped to certain MEB UV channels:
- broadDiffuseTexture - UV Map 1
- middleDiffuseTexture - UV Map 2
- detailDiffuseTexture - UV Map 2 (with multiplier set by params detailUScale, detailVScale)
- specularTexture - UV Map ?
- normalTexture - UV Map ?
- puddleTexture - UV Map 4 (with multiplier set by param uvScaleForWetMasks)

---
Below are notes for specific textures.

# LiveTrack Mask

Certain shaders, mostly those regarding ground surface materials, use a LiveTrack Mask texture slot. This refers to a specific channel-packed texture. Below is my best guess for what the role of each channel of that texture is:
- Red: Archetypal heightmap detail layer 1
- Green: Archetypal heightmap detail layer 2
- Blue: Archetypal heightmap detail layer 3
- Alpha: Gravel-like texture, variations at all scales
wherein "archetypal" means "grass-like" or "asphalt-like" or whatever the surface is that this mask is being used for is shaped like.