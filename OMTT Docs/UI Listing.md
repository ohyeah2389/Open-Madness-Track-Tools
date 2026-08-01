This lists where every TrackCompiler Blender UI panel and section appears. The listing is section-level only; independent fields that sit outside a section are listed by name.
# Properties > Scene
## Madness AIW Params
Always visible.
- Track Features
	- Waypoint Span
	- Left-Handed Pits
	- Track Difficulty
	- Pit Lanes
	- Starting Grid / Pitboxes / Garage Spots Per Pitbox (readouts derived from the scene)
	- Oval Track / Rallycross Track / Ice Track / Narrow Track
	- AI Setup
		- AI Late Braking Fraction
		- AI Setup Gearing
		- AI Setup Downforce
		- AI Setup Balance
- Rolling Starts (one sub-box per race type: Race, TimeAttack)
	- Distance Behind Grid
	- Distance Between Rows
	- Cars in Row
	- Start Speed
	- Max Speed
- Waypoint Metadata
	- Fuel Use
	- Groove Width
	- Groove Width Wet
	- Pit Configuration
		- Garage Depth
		- Pit Stop Space Front
		- Pit Stop Space Back
		- Pit Stop Join In
		- Pit Stop Join Out
# Properties > Material
## Madness MTX Settings
Visible for any material.
- Load MTX / Save MTX buttons
- Basic Settings (shader database, shader path, technique, flags, depth/alpha)
- Shader Parameters (parameter list and value editor for the active item)
- Shader Defines (define list and pairing info for the active item)
# Properties > Object Data
## MEB Export Settings
Visible when a mesh is selected.
- Export Options
- UV Mapping
- User Flags (Rendering, Shadows, Systems, Environment, Seasons)
- Custom Arguments
## Madness MEB Asset Reference
Visible when an empty is selected.
- MEB Asset Reference
- User Flags (Rendering, Shadows, Systems, Environment, Seasons)
## Madness Camera
Visible for cameras named `SMS_CAM_*`.
- camera_type
- Basic Properties
- Zoom Properties (includes Zoom Curve)
- Depth of Field
- Bokeh Properties
- Target Properties
- Shake Properties (includes Proximity Shake)
- Movement Properties
- Camera Settings
- Tracking Properties (type-dependent)
- Active Camera Zones
## Madness Camera Area
Visible for empties named `SMS_CAMZONE_*`.
- area_type
- area_name
- Common Properties
- Sphere Properties (when type is Sphere)
- OBB Properties (when type is OBB)
- Transform Information (OBB only; readouts)
## Madness Light
Visible for lights named `SMS_LIGHT_*`.
- light_type
- Basic Properties
- Spotlight Angles (spot types)
- Projection Properties (projected spot)
- Shadow & Rendering
- Light Settings
- Ground Plane
## Madness Sound
Visible for empties named `SMS_SOUND_*`.
- sound_type
- Type-specific fields (name/path, volume, fade, range, reverb, orientation, etc.) sit unsectioned at the panel root
- Sound Area Definition (ambient sound and local reverb only)
# Properties > Object
## Madness Dynamic Definition
Visible for meshes and empties.
- is_definition
- Definition box when enabled (export name, visual mesh, shape count)
- Collision Shape (on meshes that belong to a definition)
## Madness Dynamic Object
Visible for empties.
- Definition
- Instance Scale
# File > Export
Most exporters have no options UI beyond the file browser.
- Madness Scene `.sgx`, `.meb`, `.mtx`
	- No options
- Madness Cameras `.xml`
	- No options
- Madness Single MEB `.meb` + `.mtx`
	- export_scope
	- transform_mode
	- Copy Textures
- Madness Lights `_lights.sgx`
	- No options
- Madness Dynamic Objects (collision & env)
	- No options
- Madness Sound Definitions `.lsd`
	- No options
- Madness LiveTrack Cells `.gcl`
	- No options
- Madness AIW `.aiw`
	- Export Options: racing line, cut lines, wall lines
- Madness Triggers `.xml`
	- No options
- Madness LiveTrack MRDF
	- Verbose Logging
