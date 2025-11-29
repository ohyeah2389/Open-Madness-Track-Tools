The TRD file is used to store descriptive, categorical, and other simple data about each track instance. TRD files are found in each `tracks/trackname/` directory. The format is XML-like and easily editable. Each property requires a listing in the `BPersistent` base class denoting its type and a listing in the `TrackDetails` class providing its value.

The basic structure of the file is as follows:
```xml
<?xml version='1.0' encoding='utf-8'?>
<Reflection> <!--Must remain unchanged (boilerplate)-->
    <class name="BRTTIRefCount" base="root class" /> <!--Must remain unchanged (boilerplate)-->
    <class name="BPersistent" base="BRTTIRefCount"> <!--Must remain unchanged (boilerplate)-->
        <prop name="Name" type="String" /> <!--Must remain unchanged (boilerplate)-->
    </class>
    <class name="TrackDetails" base="BPersistent"> <!--Must remain unchanged (boilerplate)-->
        <prop name="TrackName" type="String" /> <!--Registers property name and type-->
    </class>
    <data class="TrackDetails" id=""> <!--Must remain unchanged (boilerplate)-->
        <prop name="TrackName" data="Adelaide_Historic" /> <!--Sets value on a registered property-->
    </data>
</Reflection>
```

Below is a list of every known assignable property found in AMS2's stock TRD files. Each is a link to a page with more context for each property, along with all seen values for that property and how often the property itself is defined. Note that not every property appears in every TRD, and there are some properties that appear in all TRDs but have no value assigned.

- [[AI Exclude Filter]]
- [[AI Extra Wall Buffer]]
	- Scalar that controls how much the computer opponents' desired trajectories are influenced by their proximity to walls (as encoded in the [[AIW]] file).
- [[AI Grip]]
	- Scalar for adjusting the grip of computer opponents as compared to the player.
- [[AI Pit Exit Speed Scalar]]
	- Controls how fast the AI drives on the AI spline from the pit exit to the main spline connection point.
- [[AI drift score max]]
- [[AI drift score min]]
- [[AIDirtyAirBehaviourEnabled]]
- [[AIDisableCorridorsReductionAgainstHuman]]
- [[AIDisableCorridorsReductionAgainstLapped]]
- [[AIOvertakeInsideEnabled]]
- [[AIW Override]]
- [[AIWidthScalarToReduceCorridors]]
- [[AIWidthScalarToReduceCorridorsFullThrottle]]
- [[Allowed TimeOfDay]]
	- Can be set to restrict available time values to Day only.
- [[Allowed Weather]]
	- Sets the available weather states for the track. Controls which weather icons are available in the weather picker menu.
- [[AutograssDensities]]
- [[AutograssHeights]]
- [[AutograssMaterial]]
- [[Class]]
- [[Client Track Version]]
- [[CloudHorizonOffset]]
- [[Country]]
	- Two-letter identifier for the country the track is located in (likely for UI elements only).
- [[Crowd Pak Filename]]
- [[CutTrackFraction]]
	- Controls the normalized distance along the track from the start line where a track cut will NOT trigger a "this AND next lap invalid", only a "this lap invalid": `mCutDistanceToInvalidateNextLap = (1.0f - trackStatus.GetCutTrackFraction()) * trackLength;`
- [[DLC ID]]
	- Can be used to restrict your track to owners of certain DLC only (but why would you do that?)
- [[DirtParticlesOverride]]
- [[DirtSkidmarksOverride]]
- [[Downforce]]
- [[Drs Zone 1 Detection Number]]
- [[Drs Zone 2 Detection Number]]
- [[Drs Zone 3 Detection Number]]
- [[DrySkidmarksOverride]]
- [[Dusk File]]
- [[Dusk Race]]
- [[Dusk Time]]
- [[Environment File]]
- [[Environment Time]]
- [[Event Types]]
	- Sets the events allowed to race at the track. Seemingly supports `!` modifiers.
- [[FogMaxDistanceScalar]]
- [[ForceSessionMeshesVisible]]
- [[GrassParticlesOverride]]
- [[GrassSkidmarksOverride]]
- [[GravelParticlesOverride]]
- [[GravelSkidmarksOverride]]
- [[GripBase]]
	- Sets the grip multiplier for all surfaces.
- [[GripRange]]
	- May be a randomness multiplier for GripBase?
- [[GroundCoverFolder]]
- [[IMSA]]
	- Denotes if the American IMSA series races at the track (could be used for DLC purposes?)
- [[InstTexturePakFilename]]
- [[Is Clockwise]]
	- Denotes if the track is run clockwise or counterclockwise.
- [[LeaderboardID]]
- [[LeafParticlesOverride]]
- [[Length]]
	- Length of track in meters.
- [[Location]]
	- Full name of country (`Argentina`, `Brazil`, `Belgium`, `Canada`, etc.) that the track is located in.
- [[Long Overlapping Pitline]]
	- May be used for tracks with pitlanes like Spa's endurance combined pits?
- [[Max AI participants]]
	- Max number of opponents that can race on the track (minus 1 for the player). Should be equal to the number of starting grid/pit garage spots in the AIW minus 1. 
- [[Name]]
	- Internal name ID for the track (`Adelaide_Historic`, `Fontana_OVAL`, etc.). Does not appear in the UI.
- [[Number Of Turns]]
	- Number of distinct turns on the track. Likely only used for UI purposes. Some tracks have an inaccurately high number assigned here for some reason.
- [[Order Override]]
	- Determines display order for tracks in the same group (showing under the same track submenu in the UI).
- [[Oval Type]]
	- May determine the oval archetype (short oval, speedway, tri-oval, superspeedway, etc)?
- [[PitSpeedLimit_HighKPH]]
	- Determines the default pitlane speed limit for the track, if any.
- [[Post race orientation]]
- [[Post race position]]
- [[Post race steering]]
- [[PostRace Script name]]
- [[PreRace Allowed (true_false)]]
- [[PreRace Script length]]
- [[PreRace Script name]]
- [[PresetFilter]]
	- Determines which "Motorsport Presets" the track is selectable in, if any.
- [[Race_Date_Day]]
	- Day of default race date.
- [[Race_Date_Month]]
	- Month of default race date.
- [[Race_Date_Year]]
	- Year of default race date.
- [[Rolling Start]]
	- Determines whether the track must use a rolling start.
- [[Rolling Start Allowed]]
	- Determines whether the track can use a rolling start.
- [[RollingStartPoleSide]]
	- Determines which side of the grid pole position starts on (not known which side is which yet).
- [[SandSkidmarksOverride]]
- [[ScalarAIBlueFlagDistanceMoveLane]]
- [[ScalarAIBlueFlagSpeedReductions]]
- [[ScalarAIColdTyreDists]]
- [[ScalarAILappedCarDistanceAhead]]
- [[ScalarAIMaxDraftHuntingDist]]
- [[ScalarAIPassComplexityCutoffMaxAggression]]
- [[ScalarAIPassComplexityCutoffMinAggression]]
- [[ScalarAISlowCarDistanceAhead]]
- [[ScalarAISteerScalarCornerCut]]
- [[ScalarAITTCStraightOvertakeDist]]
- [[ScalarAITTCStraightOvertakeTime]]
- [[ScalarBlueFlagMinDistBack]]
- [[ScenegraphFile]]
- [[Setup group]]
- [[ShortTrackName]]
	- Similar to [[Name]], an internal marker name for the track unique to its layout.
- [[StaticConvolveEnvMapLocation]]
	- May be the 3D position in the scene where the cubemap reflections are based around?
- [[StaticEnvMapLocation]]
	- May be similar to the previous entry?
- [[Sun Angle(DEG)]]
- [[Time Attack duration long]]
- [[Time Attack duration medium]]
- [[Time Attack duration short]]
- [[TimeOfDay Group]]
- [[Track Description]]
- [[Track Group]]
	- Internal marker for the high-level location name (shared between all layouts of the track to group them together), such as `Nurburgring` or `Ortona`.
- [[Track Properties File]]
- [[Track Surface]]
	- The racing surface type the track is mainly composed of (`Tarmac` or `Mud`).
- [[Track Type]]
	- The general format of the track (`Circuit`, `Point to Point`, `Oval`, etc.)
- [[TrackCentre]]
	- May be the 3D position defining the center of the world, allowing for offsets?
- [[TrackGradeFilter]]
	- Racing category of the track, such as `Grade1`, `Historic`, etc.
- [[TrackName]]
	- The name of the track displayed in the UI. Stock game tracks use this to look up a "pretty name" somewhere in the game's config files; for custom tracks, use spaces instead of underscores to display a "pretty name" in the UI.
- [[Track_Altitude]]
	- Altitude offset in meters of the scene origin.
- [[Track_Climate]]
	- Climate region for the environment, such as `California_Desert` or `England`.
- [[Track_Latitude]]
	- Latitude of the track, in decimal degrees.
- [[Track_Location]]
	- Similar to [[Track Group]]?
- [[Track_Longitude]]
	- Longitude of the track, in decimal degrees.
- [[Track_Rotation_Offset]]
	- Angle to rotate the world about to correct for a non-north-up track model.
- [[Track_TimeZone]]
	- UTC time zone of the track (`-5`, `+10.5`, etc.)
- [[Track_Variation]]
	- Similar to [[Name]], unique per track layout?
- [[Uses Reflection Flag]]
- [[Weather Weights]]
	- Comma-separated values defining the probabilities of encountering each weather type, in order, paired with the [[Allowed Weather]] list.
- [[XLASTID]]
	- Unique index for each track?
- [[Year]]
	- Year the track model represents.
- [[ZoneName]]
