import re
from dataclasses import dataclass, field
from typing import Any, List, Dict, Tuple, Optional

@dataclass
class Position:
    x: float
    y: float
    z: float

@dataclass
class Orientation:
    x: float
    y: float
    z: float

@dataclass
class GridSpot:
    index: int
    position: Position
    orientation: Orientation

@dataclass
class RollingStart:
    race_type: str
    distance_behind_grid: float
    distance_between_rows: float
    cars_in_row: int
    start_speed: float
    max_speed: float

@dataclass
class TeleportSpot:
    index: int
    position: Position
    orientation: Orientation

@dataclass
class PitSpot:
    team_index: int
    left_handed: bool
    position: Position
    orientation: Orientation
    garage_positions: List[Position]
    garage_orientations: List[Orientation]

@dataclass
class Waypoint:
    index: int
    position: Position
    perpendicular: Orientation
    width: Tuple[float, float]          # road left, road right
    dwidth: Tuple[float, float]         # collision left, collision right
    path: Tuple[float, float]           # dry line lateral offset, wet line lateral offset
    galpha: float                       # race groove darkness
    score: Tuple[int, float]            # sector, lap distance
    groove_lat: float                   # groove offset from line
    event: Tuple[float, int, float]     # corner speed mult, special event, special event data
    branch_id: int                      # 0=main path, 1=pitlane, 2+=alternate racing lines
    bitfields: int                      # bitfield data
    corner_type: int
    corner_state: int
    wp_ptrs: Tuple[int, int, int, int]  # prev_wp, next_wp, alt_next, branch_merge

    # AMS1-only extra width fields (far left / far right)
    width_far: Tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))
    dwidth_cut: Tuple[float, float] = field(default_factory=lambda: (0.0, 0.0))

    # AMS1-only fields
    normal: Optional['Orientation'] = None       # wp_normal
    vect: Optional['Orientation'] = None         # wp_vect (forward vector)
    test_speed: float = 0.0                      # AI target speed
    cheat: float = 0.0                           # AI speed cheat multiplier
    wpse: Tuple[int, int] = field(default_factory=lambda: (0, 0))   # wp_wpse special events
    pitlane: int = 1                             # what pitlane this belongs to
    path_id: int = 0                             # AMS1 WP_PTRS[3]: path/lane index (NOT a wp index)

@dataclass
class TrackFeatures:
    # Basic track info
    waypoint_span: float
    pitlanes: int
    starting_grid: int
    pit_spots: int
    garage_spots: int
    clipping_points: int
    drift_version: int
    corner_marker_version: int

    # Track characteristics
    track_difficulty: float
    oval: bool
    rallycross: bool
    ice_track: bool
    ice_track_solo: bool
    narrow_track: bool
    race_start_disabled: float

    # AI parameters
    ai_late_braking_fraction: float
    ai_setup_gearing: float
    ai_setup_downforce: float
    ai_setup_balance: float

    # Anticipation distances
    anticipation_dist_min: float
    anticipation_dist_off_road: float
    anticipation_dist_wall: float

    # AMS1-only
    aux_spots: int = 0

@dataclass
class WaypointMetadata:
    trackstate: int
    times: Tuple[float, float]
    number_waypoints: int
    lap_length: float
    sector_1_length: float
    sector_2_length: float
    fuel_use: float
    groove_width: float
    groove_width_wet: float

    # Fog parameters
    intermediate_fog_level: float
    intermediate_fog_planes: Tuple[float, float]
    rainy_fog_planes: Tuple[float, float]
    intermediate_fog_color: Tuple[float, float, float]
    rainy_fog_color: Tuple[float, float, float]
    fog_density: Tuple[float, float]
    rainy_darkness: Tuple[float, float]

    # Pit parameters
    garage_depth: float
    pit_stop_space_front: float
    pit_stop_space_back: float
    pit_stop_join_in: float
    pit_stop_join_out: float
    use_line_blend_speed: int

    # AMS1-only metadata fields
    left_handed_pits: int = 0
    driving_lines: int = 0
    lane_spacing: float = 0.0
    groove_height_offset: float = 0.0
    ai_braking_stiffness: Tuple[float, float, float] = field(default_factory=lambda: (1.0, 1.0, 0.9))
    slow_when_pushed: float = 0.0
    worst_adjust: float = 0.8
    mid_adjust: float = 1.0
    best_adjust: float = 1.15
    race_qual_ratio: float = 1.0
    ai_range: float = 0.05
    ai_draft_stickiness: float = 3.0

@dataclass
class TrackData:
    features: TrackFeatures
    grid_spots: List[GridSpot]
    rolling_starts: List[RollingStart]
    teleport_spots: List[TeleportSpot]
    pit_spots: List[PitSpot]
    waypoints: List[Waypoint]
    waypoint_metadata: WaypointMetadata
    game_version: str = 'AMS2'   # 'AMS1' or 'AMS2'

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]

class AIWParser:
    def __init__(self):
        self.track_data = None
        self._forced_game_version: Optional[str] = None  # set externally to override auto-detection

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse_file(self, filepath: str) -> TrackData:
        """Parse an AIW file and return structured track data.

        The game version (AMS1 / AMS2) is auto-detected from the file
        header / content and the appropriate parser is used.
        """
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()

        game_version = self._detect_game_version(content)

        features          = self._parse_features(content)
        grid_spots        = self._parse_grid_spots(content)
        teleport_spots    = self._parse_teleport_spots(content)
        pit_spots         = self._parse_pit_spots(content, game_version)
        waypoint_metadata = self._parse_waypoint_metadata(content, game_version)

        if game_version == 'AMS1':
            waypoints      = self._parse_waypoints_ams1(content)
            rolling_starts = []          # AMS1 has no [ROLLING START] section
        else:
            waypoints      = self._parse_waypoints(content)
            rolling_starts = self._parse_rolling_starts(content)

        self.track_data = TrackData(
            features=features,
            grid_spots=grid_spots,
            rolling_starts=rolling_starts,
            teleport_spots=teleport_spots,
            pit_spots=pit_spots,
            waypoints=waypoints,
            waypoint_metadata=waypoint_metadata,
            game_version=game_version
        )

        return self.track_data

    # ------------------------------------------------------------------
    # Version detection
    # ------------------------------------------------------------------

    def _detect_game_version(self, content: str) -> str:
        """Auto-detect whether the AIW file belongs to AMS1 or AMS2.

        If _forced_game_version has been set externally ('AMS1' or 'AMS2'),
        that value is returned immediately without inspecting the file content.

        Detection logic (first match wins):
          1. AMS1 files start with the distinctive //[[gMa1 header comment.
          2. AMS1 waypoints are NOT preceded by \\N index markers – the
             presence of such markers implies AMS2.
          3. AMS1 waypoints contain wp_wpse / wp_test_speed / wp_cheat
             fields that do not exist in AMS2.
          4. AMS2 waypoints contain wpd_CornerType / wp_event fields.
        """
        # Allow external callers to force the version (e.g. via --game CLI flag)
        if self._forced_game_version in ('AMS1', 'AMS2'):
            return self._forced_game_version

        # Strongest signal: gMa1 header string
        if re.match(r'\s*//\[\[gMa1', content):
            return 'AMS1'

        # AMS2 uses \\N index markers before each waypoint block
        if re.search(r'\\\\\d+\s*\nwp_pos=', content):
            return 'AMS2'

        # AMS1-specific waypoint fields
        if 'wp_wpse=' in content or 'wp_test_speed=' in content or 'wp_cheat=' in content:
            return 'AMS1'

        # AMS2-specific waypoint fields
        if 'wpd_CornerType=' in content or 'wp_event=' in content:
            return 'AMS2'

        # Default to AMS2 (the original supported format)
        return 'AMS2'

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _clean_value(self, value: str) -> str:
        """Remove inline comments and surrounding whitespace."""
        if '//' in value:
            value = value.split('//')[0]
        return value.strip()

    # ------------------------------------------------------------------
    # [Features] parser (shared, graceful fallback for missing keys)
    # ------------------------------------------------------------------

    def _parse_features(self, content: str) -> TrackFeatures:
        """Parse the [Features] section."""
        features_section = re.search(r'\[Features\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not features_section:
            return TrackFeatures(
                0.0, 0, 0, 0, 0, 0, 0, 0,
                1.0, False, False, False, False, False, 0.0,
                1.0, 0.5, 0.3, 0.5,
                40.0, 80.0, 160.0
            )

        features_content = features_section.group(1)

        def get_value(key: str, default: str = '0') -> str:
            match = re.search(f'{re.escape(key)}=([^\\n]+)', features_content)
            if match:
                return self._clean_value(match.group(1))
            return default

        def safe_int(v, default=0):
            try:
                return int(v)
            except (ValueError, TypeError):
                return default

        def safe_float(v, default=0.0):
            try:
                return float(v)
            except (ValueError, TypeError):
                return default

        def safe_bool(v, default=False):
            try:
                return bool(int(v))
            except (ValueError, TypeError):
                return default

        return TrackFeatures(
            waypoint_span          = safe_float(get_value('waypointspan', '0.0')),
            pitlanes               = safe_int(get_value('pitlanes')),
            starting_grid          = safe_int(get_value('startinggrid')),
            pit_spots              = safe_int(get_value('pitspots')),
            garage_spots           = safe_int(get_value('garagespots')),
            clipping_points        = safe_int(get_value('clippingpoints')),
            drift_version          = safe_int(get_value('driftversion')),
            corner_marker_version  = safe_int(get_value('cornermarkerversion')),
            track_difficulty       = safe_float(get_value('Track Difficulty', '1.0')),
            oval                   = safe_bool(get_value('Oval')),
            rallycross             = safe_bool(get_value('RallyCross')),
            ice_track              = safe_bool(get_value('IceTrack')),
            ice_track_solo         = safe_bool(get_value('IceTrackSolo')),
            narrow_track           = safe_bool(get_value('IsNarrowTrack')),
            race_start_disabled    = safe_float(get_value('Race Start Disabled', '0.0')),
            ai_late_braking_fraction = safe_float(get_value('AI Late Braking Fraction', '1.0')),
            ai_setup_gearing       = safe_float(get_value('AI Setup Gearing', '0.5')),
            ai_setup_downforce     = safe_float(get_value('AI Setup Downforce', '0.3')),
            ai_setup_balance       = safe_float(get_value('AI Setup Balance', '0.5')),
            anticipation_dist_min      = safe_float(get_value('AnticipationDistMin', '40.0')),
            anticipation_dist_off_road = safe_float(get_value('AnticipationDistOffRoad', '80.0')),
            anticipation_dist_wall     = safe_float(get_value('AnticipationDistWall', '160.0')),
            aux_spots              = safe_int(get_value('auxspots')),
        )

    # ------------------------------------------------------------------
    # [GRID] / [ALTGRID] parser (shared – same format in both games)
    # ------------------------------------------------------------------

    def _parse_grid_spots(self, content: str) -> List[GridSpot]:
        """Parse the [GRID] section (and optionally [ALTGRID] for AMS1)."""
        grid_section = re.search(r'\[GRID\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not grid_section:
            return []
        return self._extract_grid_entries(grid_section.group(1))

    def _extract_grid_entries(self, section_content: str) -> List[GridSpot]:
        grid_spots = []
        entries = re.findall(
            r'GridIndex=(\d+)\s+Pos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)\s+Ori=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)',
            section_content
        )
        for entry in entries:
            index       = int(entry[0])
            position    = Position(float(entry[1]), float(entry[2]), float(entry[3]))
            orientation = Orientation(float(entry[4]), float(entry[5]), float(entry[6]))
            grid_spots.append(GridSpot(index, position, orientation))
        return grid_spots

    # ------------------------------------------------------------------
    # [ROLLING START] parser (AMS2-only)
    # ------------------------------------------------------------------

    def _parse_rolling_starts(self, content: str) -> List[RollingStart]:
        """Parse the [ROLLING START] section (AMS2 only)."""
        rolling_section = re.search(r'\[ROLLING START\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not rolling_section:
            return []

        rolling_content = rolling_section.group(1)
        rolling_starts  = []

        race_type_matches = re.findall(r'RaceType="([^"]+)"', rolling_content)
        sections = re.split(r'RaceType="[^"]+"', rolling_content)[1:]

        for i, section in enumerate(sections):
            if i >= len(race_type_matches):
                break
            race_type = race_type_matches[i]
            try:
                m_dbg = re.search(r'DistanceBehindGrid=([0-9.]+)',  section)
                m_dbr = re.search(r'DistanceBetweenRows=([0-9.]+)', section)
                m_cir = re.search(r'CarsInRow=(\d+)',                section)
                m_ss  = re.search(r'StartSpeed=([0-9.]+)',           section)
                m_ms  = re.search(r'MaxSpeed=([0-9.]+)',             section)
                if not (m_dbg and m_dbr and m_cir and m_ss and m_ms):
                    continue
                distance_behind_grid  = float(m_dbg.group(1))
                distance_between_rows = float(m_dbr.group(1))
                cars_in_row           = int  (m_cir.group(1))
                start_speed           = float(m_ss .group(1))
                max_speed             = float(m_ms .group(1))
                rolling_starts.append(RollingStart(
                    race_type, distance_behind_grid, distance_between_rows,
                    cars_in_row, start_speed, max_speed
                ))
            except AttributeError:
                pass

        return rolling_starts

    # ------------------------------------------------------------------
    # [TELEPORT] parser (shared – same format in both games)
    # ------------------------------------------------------------------

    def _parse_teleport_spots(self, content: str) -> List[TeleportSpot]:
        """Parse the [TELEPORT] section."""
        teleport_section = re.search(r'\[TELEPORT\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not teleport_section:
            return []

        teleport_content = teleport_section.group(1)
        teleport_spots   = []

        entries = re.findall(
            r'GridIndex=(\d+)\s+Pos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)\s+Ori=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)',
            teleport_content
        )
        for entry in entries:
            index       = int(entry[0])
            position    = Position(float(entry[1]), float(entry[2]), float(entry[3]))
            orientation = Orientation(float(entry[4]), float(entry[5]), float(entry[6]))
            teleport_spots.append(TeleportSpot(index, position, orientation))

        return teleport_spots

    # ------------------------------------------------------------------
    # [PITS] parser (game-version-aware)
    # ------------------------------------------------------------------

    def _parse_pit_spots(self, content: str, game_version: str = 'AMS2') -> List[PitSpot]:
        """Parse the [PITS] section.

        AMS2 entries include PitLeftHanded and GarLeftHanded fields;
        AMS1 entries do not.
        """
        pits_section = re.search(r'\[PITS\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not pits_section:
            return []

        pits_content = pits_section.group(1)
        pit_spots    = []

        # Split by TeamIndex entries
        team_entries = re.split(r'TeamIndex=(\d+)', pits_content)[1:]

        for i in range(0, len(team_entries), 2):
            team_index   = int(team_entries[i])
            team_content = team_entries[i + 1]

            pit_pos_match = re.search(r'PitPos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', team_content)
            pit_ori_match = re.search(r'PitOri=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', team_content)

            if not (pit_pos_match and pit_ori_match):
                continue

            pit_position    = Position   (float(pit_pos_match.group(1)), float(pit_pos_match.group(2)), float(pit_pos_match.group(3)))
            pit_orientation = Orientation(float(pit_ori_match.group(1)), float(pit_ori_match.group(2)), float(pit_ori_match.group(3)))

            # AMS2 has per-pit left-handed flag; AMS1 uses LeftHandedPits in
            # the [Waypoint] metadata section – default to False here.
            if game_version == 'AMS2':
                lh_match = re.search(r'PitLeftHanded=([01])', team_content)
                pit_left = bool(int(lh_match.group(1))) if lh_match else False
            else:
                pit_left = False  # resolved later from LeftHandedPits metadata

            # Garage positions / orientations
            garage_positions    = []
            garage_orientations = []

            gar_pos_matches = re.findall(r'GarPos=\(\d+,([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', team_content)
            gar_ori_matches = re.findall(r'GarOri=\(\d+,([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', team_content)

            for pos_match in gar_pos_matches:
                garage_positions.append(Position(float(pos_match[0]), float(pos_match[1]), float(pos_match[2])))

            for ori_match in gar_ori_matches:
                garage_orientations.append(Orientation(float(ori_match[0]), float(ori_match[1]), float(ori_match[2])))

            pit_spots.append(PitSpot(team_index, pit_left, pit_position, pit_orientation, garage_positions, garage_orientations))

        return pit_spots

    # ------------------------------------------------------------------
    # [Waypoint] metadata parser (game-version-aware)
    # ------------------------------------------------------------------

    def _parse_waypoint_metadata(self, content: str, game_version: str = 'AMS2') -> WaypointMetadata:
        """Parse the waypoint metadata header from the [Waypoint] section."""
        # Match everything up to the first waypoint entry.
        # AMS2: first waypoint begins with \\0 (backslash-backslash-digit)
        # AMS1: first waypoint begins with wp_pos=
        waypoint_section = re.search(r'\[Waypoint\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not waypoint_section:
            return self._default_waypoint_metadata()

        waypoint_content = waypoint_section.group(1)

        # Isolate the metadata header (everything before the first waypoint block)
        if game_version == 'AMS2':
            first_wp_marker = re.search(r'\\\\0\b', waypoint_content)
            metadata_text   = waypoint_content[:first_wp_marker.start()] if first_wp_marker else waypoint_content
        else:
            first_wp_pos = waypoint_content.find('wp_pos=')
            metadata_text = waypoint_content[:first_wp_pos] if first_wp_pos != -1 else waypoint_content

        def get_value(key: str, default: str = '0') -> str:
            match = re.search(f'{re.escape(key)}=([^\\n]+)', metadata_text)
            if match:
                return self._clean_value(match.group(1))
            return default

        def parse_tuple(value: str, num_elements: int) -> tuple:
            cleaned = value.strip('()')
            if not cleaned:
                return tuple(0.0 for _ in range(num_elements))
            try:
                parts = [float(x.strip()) for x in cleaned.split(',')]
                while len(parts) < num_elements:
                    parts.append(0.0)
                return tuple(parts[:num_elements])
            except ValueError:
                return tuple(0.0 for _ in range(num_elements))

        def parse_single_value(value: str) -> float:
            cleaned = value.strip('()')
            if not cleaned:
                return 0.0
            try:
                return float(cleaned.split(',')[0])
            except ValueError:
                return 0.0

        times                    = parse_tuple(get_value('times',                  '(0.0,0.0)'),         2)
        intermediate_fog_planes  = parse_tuple(get_value('IntermediateFogPlanes',  '(0.0,0.0)'),         2)
        rainy_fog_planes         = parse_tuple(get_value('RainyFogPlanes',         '(0.0,0.0)'),         2)
        intermediate_fog_color   = parse_tuple(get_value('IntermediateFogColor',   '(0.0,0.0,0.0)'),     3)
        rainy_fog_color          = parse_tuple(get_value('RainyFogColor',          '(0.0,0.0,0.0)'),     3)
        fog_density              = parse_tuple(get_value('FogDensity',             '(0.0,0.0)'),         2)
        rainy_darkness           = parse_tuple(get_value('RainyDarkness',          '(0.0,0.0)'),         2)
        ai_braking_stiffness     = parse_tuple(get_value('AIBrakingStiffness',     '(1.0,1.0,0.9)'),     3)

        # AMS1-only metadata
        left_handed_pits  = int(parse_single_value(get_value('LeftHandedPits',  '0')))
        driving_lines     = int(parse_single_value(get_value('drivinglines',    '0')))
        lane_spacing      = float(get_value('LaneSpacing',   '0.0'))
        groove_height_off = float(get_value('GrooveHeightOffset', '0.0'))
        slow_when_pushed  = float(get_value('slowwhenpushed', '0.0'))
        worst_adjust      = parse_single_value(get_value('WorstAdjust',    '(0.8)'))
        mid_adjust        = parse_single_value(get_value('MidAdjust',      '(1.0)'))
        best_adjust       = parse_single_value(get_value('BestAdjust',     '(1.15)'))
        race_qual_ratio   = parse_single_value(get_value('RaceQualRatio',  '(1.0)'))
        ai_range          = parse_single_value(get_value('AIRange',        '(0.05)'))
        ai_draft_stick    = parse_single_value(get_value('AIDraftStickiness', '(3.0)'))

        return WaypointMetadata(
            trackstate            = int  (get_value('trackstate')),
            times                 = times,
            number_waypoints      = int  (get_value('number_waypoints')),
            lap_length            = float(get_value('lap_length')),
            sector_1_length       = float(get_value('sector_1_length')),
            sector_2_length       = float(get_value('sector_2_length')),
            fuel_use              = float(get_value('FuelUse')),
            groove_width          = float(get_value('GrooveWidth')),
            groove_width_wet      = float(get_value('GrooveWidthWet', '0.0')),
            intermediate_fog_level   = parse_single_value(get_value('IntermediateFogLevel', '(0.0)')),
            intermediate_fog_planes  = intermediate_fog_planes,
            rainy_fog_planes         = rainy_fog_planes,
            intermediate_fog_color   = intermediate_fog_color,
            rainy_fog_color          = rainy_fog_color,
            fog_density              = fog_density,
            rainy_darkness           = rainy_darkness,
            garage_depth          = parse_single_value(get_value('GarageDepth',       '(0.0)')),
            pit_stop_space_front  = parse_single_value(get_value('PitStopSpaceFront', '(0.0)')),
            pit_stop_space_back   = parse_single_value(get_value('PitStopSpaceBack',  '(0.0)')),
            pit_stop_join_in      = parse_single_value(get_value('PitStopJoinIn',     '(0.0)')),
            pit_stop_join_out     = parse_single_value(get_value('PitStopJoinOut',    '(0.0)')),
            use_line_blend_speed  = int  (get_value('UseLineBlendSpeed')),
            # AMS1-only
            left_handed_pits      = left_handed_pits,
            driving_lines         = driving_lines,
            lane_spacing          = lane_spacing,
            groove_height_offset  = groove_height_off,
            ai_braking_stiffness  = ai_braking_stiffness,
            slow_when_pushed      = slow_when_pushed,
            worst_adjust          = worst_adjust,
            mid_adjust            = mid_adjust,
            best_adjust           = best_adjust,
            race_qual_ratio       = race_qual_ratio,
            ai_range              = ai_range,
            ai_draft_stickiness   = ai_draft_stick,
        )

    def _default_waypoint_metadata(self) -> WaypointMetadata:
        return WaypointMetadata(
            0, (0.0, 0.0), 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            0.0, (0.0, 0.0), (0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0),
            (0.0, 0.0), (0.0, 0.0),
            0.0, 0.0, 0.0, 0.0, 0.0, 0
        )

    # ------------------------------------------------------------------
    # AMS2 waypoint parser (original)
    # ------------------------------------------------------------------

    def _parse_waypoints(self, content: str) -> List[Waypoint]:
        """Parse AMS2 waypoints from the [Waypoint] section.

        AMS2 waypoints are prefixed with \\N index markers.
        """
        waypoint_section = re.search(r'\[Waypoint\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not waypoint_section:
            return []

        waypoint_content = waypoint_section.group(1)
        waypoints        = []

        # Each entry starts with \\N (two literal backslashes then a number)
        waypoint_entries = re.findall(r'\\\\(\d+)\s+(.*?)(?=\\\\|\Z)', waypoint_content, re.DOTALL)

        for entry in waypoint_entries:
            index      = int(entry[0])
            wp_content = entry[1]
            wp = self._parse_single_waypoint_ams2(index, wp_content)
            if wp is not None:
                waypoints.append(wp)

        return waypoints

    def _parse_single_waypoint_ams2(self, index: int, wp_content: str) -> Optional[Waypoint]:
        """Parse one AMS2 waypoint block."""
        pos_match  = re.search(r'wp_pos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)',  wp_content)
        perp_match = re.search(r'wp_perp=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', wp_content)

        if not (pos_match and perp_match):
            return None

        position    = Position   (float(pos_match .group(1)), float(pos_match .group(2)), float(pos_match .group(3)))
        perpendicular = Orientation(float(perp_match.group(1)), float(perp_match.group(2)), float(perp_match.group(3)))

        width_match   = re.search(r'wp_width=\(([-0-9.]+),([-0-9.]+)\)',  wp_content)
        dwidth_match  = re.search(r'wp_dwidth=\(([-0-9.]+),([-0-9.]+)\)', wp_content)
        path_match    = re.search(r'wp_path=\(([-0-9.]+),([-0-9.]+)\)',   wp_content)
        galpha_match  = re.search(r'wp_galpha=\(([-0-9.]+)\)',            wp_content)
        score_match   = re.search(r'wp_score=\((\d+),([-0-9.]+)\)',       wp_content)
        glat_match    = re.search(r'wp_groove_lat=\(([-0-9.]+)\)',        wp_content)
        event_match   = re.search(r'wp_event=\(([-0-9.]+),(\d+),([-0-9.]+)\)', wp_content)
        branch_match  = re.search(r'wp_branchID=\((\d+)\)',               wp_content)
        bits_match    = re.search(r'wp_bitfields=\((\d+)\)',              wp_content)
        ct_match      = re.search(r'wpd_CornerType=\((\d+)\)',            wp_content)
        cs_match      = re.search(r'wpd_CornerState=\((\d+)\)',           wp_content)
        ptrs_match    = re.search(r'WP_PTRS=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)', wp_content)

        width      = (float(width_match .group(1)), float(width_match .group(2))) if width_match  else (0.0, 0.0)
        dwidth     = (float(dwidth_match.group(1)), float(dwidth_match.group(2))) if dwidth_match else (0.0, 0.0)
        path       = (float(path_match  .group(1)), float(path_match  .group(2))) if path_match   else (0.0, 0.0)
        galpha     = float(galpha_match.group(1))  if galpha_match else 0.0
        score      = (int  (score_match .group(1)), float(score_match .group(2))) if score_match  else (0, 0.0)
        groove_lat = float(glat_match  .group(1))  if glat_match   else 0.0
        event      = (float(event_match.group(1)), int(event_match.group(2)), float(event_match.group(3))) if event_match else (1.0, 0, 0.0)
        branch_id  = int  (branch_match.group(1))  if branch_match else 0
        bitfields  = int  (bits_match  .group(1))  if bits_match   else 0
        corner_type  = int(ct_match    .group(1))  if ct_match     else 0
        corner_state = int(cs_match    .group(1))  if cs_match     else 0
        wp_ptrs    = (int(ptrs_match.group(1)), int(ptrs_match.group(2)),
                      int(ptrs_match.group(3)), int(ptrs_match.group(4))) if ptrs_match else (-1, -1, -1, -1)

        return Waypoint(
            index=index,
            position=position,
            perpendicular=perpendicular,
            width=width,
            dwidth=dwidth,
            path=path,
            galpha=galpha,
            score=score,
            groove_lat=groove_lat,
            event=event,
            branch_id=branch_id,
            bitfields=bitfields,
            corner_type=corner_type,
            corner_state=corner_state,
            wp_ptrs=wp_ptrs,
        )

    # ------------------------------------------------------------------
    # AMS1 waypoint parser
    # ------------------------------------------------------------------

    def _parse_waypoints_ams1(self, content: str) -> List[Waypoint]:
        """Parse AMS1 waypoints from the [Waypoint] section.

        AMS1 waypoints have no \\N index markers.  Each new waypoint
        begins at a wp_pos= line.  The waypoint index is its sequential
        position in the file (0-based) – this matches the indices stored
        in WP_PTRS.
        """
        waypoint_section = re.search(r'\[Waypoint\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not waypoint_section:
            return []

        waypoint_content = waypoint_section.group(1)

        # Find the offset of every wp_pos= occurrence so we can slice between them
        wp_pos_offsets = [m.start() for m in re.finditer(r'^wp_pos=', waypoint_content, re.MULTILINE)]
        if not wp_pos_offsets:
            return []

        waypoints = []
        for i, start in enumerate(wp_pos_offsets):
            end       = wp_pos_offsets[i + 1] if i + 1 < len(wp_pos_offsets) else len(waypoint_content)
            block     = waypoint_content[start:end]
            wp        = self._parse_single_waypoint_ams1(i, block)
            if wp is not None:
                waypoints.append(wp)

        return waypoints

    def _parse_single_waypoint_ams1(self, index: int, wp_content: str) -> Optional[Waypoint]:
        """Parse one AMS1 waypoint block."""
        pos_match  = re.search(r'wp_pos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)',  wp_content)
        perp_match = re.search(r'wp_perp=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', wp_content)

        if not (pos_match and perp_match):
            return None

        position      = Position   (float(pos_match .group(1)), float(pos_match .group(2)), float(pos_match .group(3)))
        perpendicular = Orientation(float(perp_match.group(1)), float(perp_match.group(2)), float(perp_match.group(3)))

        # wp_normal and wp_vect (AMS1-only)
        normal_match = re.search(r'wp_normal=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', wp_content)
        vect_match   = re.search(r'wp_vect=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)',   wp_content)
        normal = Orientation(float(normal_match.group(1)), float(normal_match.group(2)), float(normal_match.group(3))) if normal_match else None
        vect   = Orientation(float(vect_match  .group(1)), float(vect_match  .group(2)), float(vect_match  .group(3))) if vect_match   else None

        # AMS1 wp_width has 4 values: road_left, road_right, far_left, far_right
        width_match = re.search(r'wp_width=\(([-0-9.]+),([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', wp_content)
        if width_match:
            width     = (float(width_match.group(1)), float(width_match.group(2)))
            width_far = (float(width_match.group(3)), float(width_match.group(4)))
        else:
            # Fall back to 2-value form just in case
            width2 = re.search(r'wp_width=\(([-0-9.]+),([-0-9.]+)\)', wp_content)
            width     = (float(width2.group(1)), float(width2.group(2))) if width2 else (0.0, 0.0)
            width_far = (0.0, 0.0)

        # AMS1 wp_dwidth has 4 values: col_left, col_right, cut_left, cut_right
        dwidth_match = re.search(r'wp_dwidth=\(([-0-9.]+),([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', wp_content)
        if dwidth_match:
            dwidth     = (float(dwidth_match.group(1)), float(dwidth_match.group(2)))
            dwidth_cut = (float(dwidth_match.group(3)), float(dwidth_match.group(4)))
        else:
            dwidth2 = re.search(r'wp_dwidth=\(([-0-9.]+),([-0-9.]+)\)', wp_content)
            dwidth     = (float(dwidth2.group(1)), float(dwidth2.group(2))) if dwidth2 else (0.0, 0.0)
            dwidth_cut = (0.0, 0.0)

        path_match   = re.search(r'wp_path=\(([-0-9.]+),([-0-9.]+)\)',   wp_content)
        galpha_match = re.search(r'wp_galpha=\(([-0-9.]+)\)',            wp_content)
        score_match  = re.search(r'wp_score=\((\d+),([-0-9.]+)\)',       wp_content)
        glat_match   = re.search(r'wp_groove_lat=\(([-0-9.]+)\)',        wp_content)
        branch_match = re.search(r'wp_branchID=\((\d+)\)',               wp_content)
        bits_match   = re.search(r'wp_bitfields=\((\d+)\)',              wp_content)
        ptrs_match   = re.search(r'WP_PTRS=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)', wp_content)

        # AMS1-only fields
        speed_match  = re.search(r'wp_test_speed=\(([-0-9.]+)\)',        wp_content)
        cheat_match  = re.search(r'wp_cheat=\(([-0-9.]+)\)',             wp_content)
        wpse_match   = re.search(r'wp_wpse=\((\d+),(\d+)\)',             wp_content)
        pitlane_match= re.search(r'wp_pitlane=\((\d+)\)',                wp_content)

        path       = (float(path_match  .group(1)), float(path_match  .group(2))) if path_match  else (0.0, 0.0)
        galpha     = float(galpha_match .group(1)) if galpha_match  else 0.0
        score      = (int  (score_match .group(1)), float(score_match .group(2))) if score_match else (0, 0.0)
        groove_lat = float(glat_match   .group(1)) if glat_match    else 0.0
        branch_id  = int  (branch_match .group(1)) if branch_match  else 0
        bitfields  = int  (bits_match   .group(1)) if bits_match    else 0
        # AMS1 WP_PTRS meaning: (prev_wp, next_wp, branch_wp_id, path_of_branch_wp)
        # ptrs[3] is a small path/lane index (0, 1, 2 …), NOT a waypoint index.
        # We store it in path_id and force ptrs[3] = -1 so the visualiser never
        # draws spurious branch-merge lines to low-numbered waypoints.
        if ptrs_match:
            wp_ptrs = (int(ptrs_match.group(1)), int(ptrs_match.group(2)),
                       int(ptrs_match.group(3)), -1)
            path_id = int(ptrs_match.group(4))
        else:
            wp_ptrs = (-1, -1, -1, -1)
            path_id = 0
        test_speed = float(speed_match  .group(1)) if speed_match   else 0.0
        cheat      = float(cheat_match  .group(1)) if cheat_match   else 0.0
        wpse       = (int(wpse_match.group(1)), int(wpse_match.group(2))) if wpse_match else (0, 0)
        pitlane    = int  (pitlane_match.group(1)) if pitlane_match else 1

        # AMS1 has no wp_event / wpd_CornerType / wpd_CornerState.
        # Map wp_wpse loosely onto the event tuple for colour-channel compat:
        #   event[0] = 1.0 (neutral speed mult),
        #   event[1] = wpse[0],
        #   event[2] = float(wpse[1])
        event = (1.0, wpse[0], float(wpse[1]))

        return Waypoint(
            index=index,
            position=position,
            perpendicular=perpendicular,
            width=width,
            dwidth=dwidth,
            path=path,
            galpha=galpha,
            score=score,
            groove_lat=groove_lat,
            event=event,
            branch_id=branch_id,
            bitfields=bitfields,
            corner_type=0,
            corner_state=0,
            wp_ptrs=wp_ptrs,
            width_far=width_far,
            dwidth_cut=dwidth_cut,
            normal=normal,
            vect=vect,
            test_speed=test_speed,
            cheat=cheat,
            wpse=wpse,
            pitlane=pitlane,
            path_id=path_id,
        )

    # ------------------------------------------------------------------
    # Validation helpers (shared)
    # ------------------------------------------------------------------

    def validate_waypoint_structure(self) -> ValidationResult:
        """Validate the waypoint path structure and pointers."""
        if not self.track_data or not self.track_data.waypoints:
            return ValidationResult(False, ["No waypoint data available"], [])

        errors   = []
        warnings = []
        waypoints    = self.track_data.waypoints
        waypoint_map = {wp.index: wp for wp in waypoints}
        max_index    = max(wp.index for wp in waypoints)

        for wp in waypoints:
            prev_wp, next_wp, alt_next, branch_merge = wp.wp_ptrs

            if prev_wp != -1:
                if prev_wp not in waypoint_map:
                    errors.append(f"Waypoint {wp.index}: prev_wp {prev_wp} points to non-existent waypoint")
                elif prev_wp > max_index:
                    errors.append(f"Waypoint {wp.index}: prev_wp {prev_wp} exceeds maximum waypoint index {max_index}")
                else:
                    prev_waypoint = waypoint_map[prev_wp]
                    if prev_waypoint.wp_ptrs[1] != wp.index and prev_waypoint.wp_ptrs[2] != wp.index:
                        warnings.append(f"Waypoint {wp.index}: prev_wp {prev_wp} doesn't point back to this waypoint")

            if next_wp != -1:
                if next_wp not in waypoint_map:
                    errors.append(f"Waypoint {wp.index}: next_wp {next_wp} points to non-existent waypoint")
                elif next_wp > max_index:
                    errors.append(f"Waypoint {wp.index}: next_wp {next_wp} exceeds maximum waypoint index {max_index}")
                else:
                    next_waypoint = waypoint_map[next_wp]
                    if next_waypoint.wp_ptrs[0] != wp.index:
                        warnings.append(f"Waypoint {wp.index}: next_wp {next_wp} doesn't point back to this waypoint")

            if alt_next != -1:
                if alt_next not in waypoint_map:
                    errors.append(f"Waypoint {wp.index}: alt_next {alt_next} points to non-existent waypoint")
                elif alt_next > max_index:
                    errors.append(f"Waypoint {wp.index}: alt_next {alt_next} exceeds maximum waypoint index {max_index}")

            if branch_merge != -1:
                if branch_merge not in waypoint_map:
                    errors.append(f"Waypoint {wp.index}: branch_merge {branch_merge} points to non-existent waypoint")
                elif branch_merge > max_index:
                    errors.append(f"Waypoint {wp.index}: branch_merge {branch_merge} exceeds maximum waypoint index {max_index}")

        self._validate_path_continuity(waypoints, waypoint_map, errors, warnings)
        self._validate_branch_structure(waypoints, waypoint_map, errors, warnings)

        return ValidationResult(len(errors) == 0, errors, warnings)

    def _validate_path_continuity(self, waypoints: List[Waypoint], waypoint_map: Dict[int, Waypoint],
                                   errors: List[str], warnings: List[str]):
        """Validate that the main path forms a continuous loop."""
        main_path_waypoints = [wp for wp in waypoints if wp.branch_id == 0]

        if not main_path_waypoints:
            errors.append("No main path waypoints found (branch_id=0)")
            return

        start_candidates = [wp for wp in main_path_waypoints if wp.wp_ptrs[0] == -1]
        if not start_candidates:
            start_candidates = [min(main_path_waypoints, key=lambda x: x.index)]

        visited     = set()
        current     = start_candidates[0]
        path_length = 0

        while current and current.index not in visited:
            visited.add(current.index)
            path_length += 1

            next_wp_index = current.wp_ptrs[1]
            if next_wp_index == -1:
                break

            if next_wp_index not in waypoint_map:
                errors.append(f"Path broken at waypoint {current.index}: next_wp {next_wp_index} not found")
                break

            current = waypoint_map[next_wp_index]

            if path_length > len(main_path_waypoints) * 2:
                errors.append("Infinite loop detected in main path")
                break

        if len(visited) != len(main_path_waypoints):
            missing = len(main_path_waypoints) - len(visited)
            warnings.append(f"Main path may be incomplete: {missing} waypoints not reachable")

    def _validate_branch_structure(self, waypoints: List[Waypoint], waypoint_map: Dict[int, Waypoint],
                                    errors: List[str], warnings: List[str]):
        """Validate branch waypoint structure."""
        branch_waypoints = [wp for wp in waypoints if wp.branch_id != 0]

        for wp in branch_waypoints:
            if wp.wp_ptrs[3] != -1:
                if wp.wp_ptrs[3] not in waypoint_map:
                    errors.append(f"Branch waypoint {wp.index}: branch_merge {wp.wp_ptrs[3]} not found")
                else:
                    merge_wp = waypoint_map[wp.wp_ptrs[3]]
                    if merge_wp.branch_id != 0:
                        warnings.append(f"Branch waypoint {wp.index}: merges to non-main path waypoint {wp.wp_ptrs[3]}")

            if wp.branch_id == 1:
                if wp.wp_ptrs[1] != -1:
                    next_wp = waypoint_map.get(wp.wp_ptrs[1])
                    if next_wp and next_wp.branch_id != 1 and wp.wp_ptrs[3] == -1:
                        warnings.append(f"Pitlane waypoint {wp.index}: transitions to non-pitlane without merge point")

    def get_path_statistics(self) -> Dict[str, Any]:
        """Get statistics about the waypoint path structure."""
        if not self.track_data or not self.track_data.waypoints:
            return {}

        waypoints      = self.track_data.waypoints
        all_indices    = {wp.index for wp in waypoints}

        stats = {
            "total_waypoints":            len(waypoints),
            "main_path_waypoints":        len([wp for wp in waypoints if wp.branch_id == 0]),
            "pitlane_waypoints":          len([wp for wp in waypoints if wp.branch_id == 1]),
            "branch_waypoints":           len([wp for wp in waypoints if wp.branch_id > 1]),
            "waypoints_with_alt_next":    len([wp for wp in waypoints if wp.wp_ptrs[2] != -1]),
            "waypoints_with_branch_merge":len([wp for wp in waypoints if wp.wp_ptrs[3] != -1]),
            "broken_prev_pointers":       len([wp for wp in waypoints if wp.wp_ptrs[0] not in all_indices and wp.wp_ptrs[0] != -1]),
            "broken_next_pointers":       len([wp for wp in waypoints if wp.wp_ptrs[1] not in all_indices and wp.wp_ptrs[1] != -1]),
        }
        return stats

    def print_validation_report(self):
        if not self.track_data:
            print("No track data loaded. Please parse an AIW file first.")
            return

        print("=== AIW Validation Report ===")
        print(f"Game Version: {self.track_data.game_version}")
        print()

        stats = self.get_path_statistics()
        print("Path statistics:")
        for key, value in stats.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        print()

        validation = self.validate_waypoint_structure()
        print(f"Validation status: {'PASS' if validation.is_valid else 'FAIL'}")
        print()

        if validation.errors:
            print("Errors:")
            for error in validation.errors:
                print(f"  \u274c {error}")
            print()

        if validation.warnings:
            print("Warnings:")
            for warning in validation.warnings:
                print(f"  \u26a0\ufe0f  {warning}")
            print()

        if validation.is_valid and not validation.warnings:
            print("\u2705 AIW file structure is valid")
        elif validation.is_valid:
            print("\u2705 AIW file structure is valid but has warnings")
        else:
            print("\u274c AIW file has errors")