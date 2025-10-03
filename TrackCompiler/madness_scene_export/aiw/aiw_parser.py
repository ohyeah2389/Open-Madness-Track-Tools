import re
from dataclasses import dataclass
from typing import List, Dict, Tuple

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
    width: Tuple[float, float]  # road left, road right
    dwidth: Tuple[float, float]  # collision left, collision right
    path: Tuple[float, float]  # dry line lateral offset, wet line lateral offset
    galpha: float  # race groove darkness
    score: Tuple[int, float]  # sector, lap distance
    groove_lat: float  # groove offset from line
    event: Tuple[float, int, float]  # corner speed mult, special event, special event data
    branch_id: int  # 0=main path, 1=pitlane, 2+=alternate racing lines
    bitfields: int  # bitfield data
    corner_type: int
    corner_state: int
    wp_ptrs: Tuple[int, int, int, int]  # prev_wp, next_wp, alt_next, branch_merge

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

@dataclass
class TrackData:
    features: TrackFeatures
    grid_spots: List[GridSpot]
    rolling_starts: List[RollingStart]
    teleport_spots: List[TeleportSpot]
    pit_spots: List[PitSpot]
    waypoints: List[Waypoint]
    waypoint_metadata: WaypointMetadata

@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str]
    warnings: List[str]

class AIWParser:
    def __init__(self):
        self.track_data = None
    
    def parse_file(self, filepath: str) -> TrackData:
        """Parse an AIW file and return structured track data."""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse different sections
        features = self._parse_features(content)
        grid_spots = self._parse_grid_spots(content)
        rolling_starts = self._parse_rolling_starts(content)
        teleport_spots = self._parse_teleport_spots(content)
        pit_spots = self._parse_pit_spots(content)
        waypoints = self._parse_waypoints(content)
        waypoint_metadata = self._parse_waypoint_metadata(content)
        
        self.track_data = TrackData(
            features=features,
            grid_spots=grid_spots,
            rolling_starts=rolling_starts,
            teleport_spots=teleport_spots,
            pit_spots=pit_spots,
            waypoints=waypoints,
            waypoint_metadata=waypoint_metadata
        )
        
        return self.track_data
    
    def _clean_value(self, value: str) -> str:
        """Clean a value by removing comments and whitespace."""
        # Remove comments (// and everything after)
        if '//' in value:
            value = value.split('//')[0]
        return value.strip()
    
    def _parse_features(self, content: str) -> TrackFeatures:
        """Parse the [Features] section."""
        features_section = re.search(r'\[Features\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not features_section:
            return TrackFeatures(0.0, 0, 0, 0, 0, 0, 0, 0, 1.0, False, False, False, False, False, 0.0, 1.0, 0.5, 0.3, 0.5, 40.0, 80.0, 160.0)
        
        features_content = features_section.group(1)
        
        def get_value(key: str, default=0):
            match = re.search(f'{key}=([^\\n]+)', features_content)
            if match:
                return self._clean_value(match.group(1))
            return default
        
        return TrackFeatures(
            waypoint_span=float(get_value('waypointspan', '0.0')),
            pitlanes=int(get_value('pitlanes')),
            starting_grid=int(get_value('startinggrid')),
            pit_spots=int(get_value('pitspots')),
            garage_spots=int(get_value('garagespots')),
            clipping_points=int(get_value('clippingpoints')),
            drift_version=int(get_value('driftversion')),
            corner_marker_version=int(get_value('cornermarkerversion')),
            track_difficulty=float(get_value('Track Difficulty', '1.0')),
            oval=bool(int(get_value('Oval'))),
            rallycross=bool(int(get_value('RallyCross'))),
            ice_track=bool(int(get_value('IceTrack'))),
            ice_track_solo=bool(int(get_value('IceTrackSolo'))),
            narrow_track=bool(int(get_value('IsNarrowTrack'))),
            race_start_disabled=float(get_value('Race Start Disabled', '0.0')),
            ai_late_braking_fraction=float(get_value('AI Late Braking Fraction', '1.0')),
            ai_setup_gearing=float(get_value('AI Setup Gearing', '0.5')),
            ai_setup_downforce=float(get_value('AI Setup Downforce', '0.3')),
            ai_setup_balance=float(get_value('AI Setup Balance', '0.5')),
            anticipation_dist_min=float(get_value('AnticipationDistMin', '40.0')),
            anticipation_dist_off_road=float(get_value('AnticipationDistOffRoad', '80.0')),
            anticipation_dist_wall=float(get_value('AnticipationDistWall', '160.0'))
        )
    
    def _parse_grid_spots(self, content: str) -> List[GridSpot]:
        """Parse the [GRID] section."""
        grid_section = re.search(r'\[GRID\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not grid_section:
            return []
        
        grid_content = grid_section.group(1)
        grid_spots = []
        
        # Find all grid entries
        grid_entries = re.findall(r'GridIndex=(\d+)\s+Pos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)\s+Ori=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', grid_content)
        
        for entry in grid_entries:
            index = int(entry[0])
            position = Position(float(entry[1]), float(entry[2]), float(entry[3]))
            orientation = Orientation(float(entry[4]), float(entry[5]), float(entry[6]))
            grid_spots.append(GridSpot(index, position, orientation))
        
        return grid_spots
    
    def _parse_rolling_starts(self, content: str) -> List[RollingStart]:
        """Parse the [ROLLING START] section."""
        rolling_section = re.search(r'\[ROLLING START\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not rolling_section:
            return []
        
        rolling_content = rolling_section.group(1)
        rolling_starts = []
        
        # Find all rolling start entries
        race_type_matches = re.findall(r'RaceType="([^"]+)"', rolling_content)
        
        # Split content by RaceType
        sections = re.split(r'RaceType="[^"]+"', rolling_content)[1:]  # Skip first empty
        
        for i, section in enumerate(sections):
            if i < len(race_type_matches):
                race_type = race_type_matches[i]
                
                distance_behind_grid = float(re.search(r'DistanceBehindGrid=([0-9.]+)', section).group(1))
                distance_between_rows = float(re.search(r'DistanceBetweenRows=([0-9.]+)', section).group(1))
                cars_in_row = int(re.search(r'CarsInRow=(\d+)', section).group(1))
                start_speed = float(re.search(r'StartSpeed=([0-9.]+)', section).group(1))
                max_speed = float(re.search(r'MaxSpeed=([0-9.]+)', section).group(1))
                
                rolling_starts.append(RollingStart(race_type, distance_behind_grid, distance_between_rows, cars_in_row, start_speed, max_speed))
        
        return rolling_starts
    
    def _parse_teleport_spots(self, content: str) -> List[TeleportSpot]:
        """Parse the [TELEPORT] section."""
        teleport_section = re.search(r'\[TELEPORT\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not teleport_section:
            return []
        
        teleport_content = teleport_section.group(1)
        teleport_spots = []
        
        # Find all teleport entries
        teleport_entries = re.findall(r'GridIndex=(\d+)\s+Pos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)\s+Ori=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', teleport_content)
        
        for entry in teleport_entries:
            index = int(entry[0])
            position = Position(float(entry[1]), float(entry[2]), float(entry[3]))
            orientation = Orientation(float(entry[4]), float(entry[5]), float(entry[6]))
            teleport_spots.append(TeleportSpot(index, position, orientation))
        
        return teleport_spots
    
    def _parse_pit_spots(self, content: str) -> List[PitSpot]:
        """Parse the [PITS] section."""
        pits_section = re.search(r'\[PITS\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not pits_section:
            return []
        
        pits_content = pits_section.group(1)
        pit_spots = []
        
        # Split by TeamIndex entries
        team_entries = re.split(r'TeamIndex=(\d+)', pits_content)[1:]  # Skip first empty element
        
        for i in range(0, len(team_entries), 2):
            team_index = int(team_entries[i])
            team_content = team_entries[i + 1]
            
            # Parse pit data
            pit_left = bool(int(re.search(r'PitLeftHanded=([01])', team_content).group(1)))
            pit_pos_match = re.search(r'PitPos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', team_content)
            pit_ori_match = re.search(r'PitOri=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', team_content)
            
            if pit_pos_match and pit_ori_match:
                pit_position = Position(float(pit_pos_match.group(1)), float(pit_pos_match.group(2)), float(pit_pos_match.group(3)))
                pit_orientation = Orientation(float(pit_ori_match.group(1)), float(pit_ori_match.group(2)), float(pit_ori_match.group(3)))
                
                # Parse garage data
                garage_positions = []
                garage_orientations = []
                
                gar_pos_matches = re.findall(r'GarPos=\(\d+,([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', team_content)
                gar_ori_matches = re.findall(r'GarOri=\(\d+,([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', team_content)
                
                for pos_match in gar_pos_matches:
                    garage_positions.append(Position(float(pos_match[0]), float(pos_match[1]), float(pos_match[2])))
                
                for ori_match in gar_ori_matches:
                    garage_orientations.append(Orientation(float(ori_match[0]), float(ori_match[1]), float(ori_match[2])))
                
                pit_spots.append(PitSpot(team_index, pit_left, pit_position, pit_orientation, garage_positions, garage_orientations))
        
        return pit_spots
    
    def _parse_waypoint_metadata(self, content: str) -> WaypointMetadata:
        """Parse the waypoint metadata from the [Waypoint] section."""
        waypoint_section = re.search(r'\[Waypoint\](.*?)(?=\\\\|\Z)', content, re.DOTALL)
        if not waypoint_section:
            return WaypointMetadata(0, (0.0, 0.0), 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, (0.0, 0.0), (0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0), (0.0, 0.0), 0.0, 0.0, 0.0, 0.0, 0.0, 0)
        
        waypoint_content = waypoint_section.group(1)
        
        def get_value(key: str, default='0'):
            match = re.search(f'{key}=([^\\n]+)', waypoint_content)
            if match:
                return self._clean_value(match.group(1))
            return default
        
        def parse_tuple(value: str, num_elements: int):
            # Remove parentheses and clean
            cleaned = value.strip('()')
            if not cleaned:
                return tuple(0.0 for _ in range(num_elements))
            try:
                parts = [float(x.strip()) for x in cleaned.split(',')]
                # Pad with zeros if not enough elements
                while len(parts) < num_elements:
                    parts.append(0.0)
                return tuple(parts[:num_elements])
            except ValueError:
                # If parsing fails, return zeros
                return tuple(0.0 for _ in range(num_elements))
        
        def parse_single_value(value: str):
            # Remove parentheses and clean
            cleaned = value.strip('()')
            if not cleaned:
                return 0.0
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        
        times_str = get_value('times', '(0.0,0.0)')
        times = parse_tuple(times_str, 2)
        
        intermediate_fog_planes_str = get_value('IntermediateFogPlanes', '(0.0,0.0)')
        intermediate_fog_planes = parse_tuple(intermediate_fog_planes_str, 2)
        
        rainy_fog_planes_str = get_value('RainyFogPlanes', '(0.0,0.0)')
        rainy_fog_planes = parse_tuple(rainy_fog_planes_str, 2)
        
        intermediate_fog_color_str = get_value('IntermediateFogColor', '(0.0,0.0,0.0)')
        intermediate_fog_color = parse_tuple(intermediate_fog_color_str, 3)
        
        rainy_fog_color_str = get_value('RainyFogColor', '(0.0,0.0,0.0)')
        rainy_fog_color = parse_tuple(rainy_fog_color_str, 3)
        
        fog_density_str = get_value('FogDensity', '(0.0,0.0)')
        fog_density = parse_tuple(fog_density_str, 2)
        
        rainy_darkness_str = get_value('RainyDarkness', '(0.0,0.0)')
        rainy_darkness = parse_tuple(rainy_darkness_str, 2)
        
        return WaypointMetadata(
            trackstate=int(get_value('trackstate')),
            times=times,
            number_waypoints=int(get_value('number_waypoints')),
            lap_length=float(get_value('lap_length')),
            sector_1_length=float(get_value('sector_1_length')),
            sector_2_length=float(get_value('sector_2_length')),
            fuel_use=float(get_value('FuelUse')),
            groove_width=float(get_value('GrooveWidth')),
            groove_width_wet=float(get_value('GrooveWidthWet', '0.0')),
            intermediate_fog_level=parse_single_value(get_value('IntermediateFogLevel', '(0.0)')),
            intermediate_fog_planes=intermediate_fog_planes,
            rainy_fog_planes=rainy_fog_planes,
            intermediate_fog_color=intermediate_fog_color,
            rainy_fog_color=rainy_fog_color,
            fog_density=fog_density,
            rainy_darkness=rainy_darkness,
            garage_depth=parse_single_value(get_value('GarageDepth', '(0.0)')),
            pit_stop_space_front=parse_single_value(get_value('PitStopSpaceFront', '(0.0)')),
            pit_stop_space_back=parse_single_value(get_value('PitStopSpaceBack', '(0.0)')),
            pit_stop_join_in=parse_single_value(get_value('PitStopJoinIn', '(0.0)')),
            pit_stop_join_out=parse_single_value(get_value('PitStopJoinOut', '(0.0)')),
            use_line_blend_speed=int(get_value('UseLineBlendSpeed'))
        )
    
    def _parse_waypoints(self, content: str) -> List[Waypoint]:
        """Parse the waypoints from the [Waypoint] section."""
        waypoint_section = re.search(r'\[Waypoint\](.*?)(?=\[|\Z)', content, re.DOTALL)
        if not waypoint_section:
            return []
        
        waypoint_content = waypoint_section.group(1)
        waypoints = []
        
        # Find all waypoint entries
        waypoint_entries = re.findall(r'\\\\(\d+)\s+(.*?)(?=\\\\|\Z)', waypoint_content, re.DOTALL)
        
        for entry in waypoint_entries:
            index = int(entry[0])
            wp_content = entry[1]
            
            # Parse waypoint data
            pos_match = re.search(r'wp_pos=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', wp_content)
            perp_match = re.search(r'wp_perp=\(([-0-9.]+),([-0-9.]+),([-0-9.]+)\)', wp_content)
            width_match = re.search(r'wp_width=\(([-0-9.]+),([-0-9.]+)\)', wp_content)
            dwidth_match = re.search(r'wp_dwidth=\(([-0-9.]+),([-0-9.]+)\)', wp_content)
            path_match = re.search(r'wp_path=\(([-0-9.]+),([-0-9.]+)\)', wp_content)
            galpha_match = re.search(r'wp_galpha=\(([-0-9.]+)\)', wp_content)
            score_match = re.search(r'wp_score=\((\d+),([-0-9.]+)\)', wp_content)
            groove_lat_match = re.search(r'wp_groove_lat=\(([-0-9.]+)\)', wp_content)
            event_match = re.search(r'wp_event=\(([-0-9.]+),(\d+),([-0-9.]+)\)', wp_content)
            branch_match = re.search(r'wp_branchID=\((\d+)\)', wp_content)
            bitfields_match = re.search(r'wp_bitfields=\((\d+)\)', wp_content)
            corner_type_match = re.search(r'wpd_CornerType=\((\d+)\)', wp_content)
            corner_state_match = re.search(r'wpd_CornerState=\((\d+)\)', wp_content)
            wp_ptrs_match = re.search(r'WP_PTRS=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\)', wp_content)
            
            if pos_match and perp_match:
                position = Position(float(pos_match.group(1)), float(pos_match.group(2)), float(pos_match.group(3)))
                perpendicular = Orientation(float(perp_match.group(1)), float(perp_match.group(2)), float(perp_match.group(3)))
                
                width = (float(width_match.group(1)), float(width_match.group(2))) if width_match else (0.0, 0.0)
                dwidth = (float(dwidth_match.group(1)), float(dwidth_match.group(2))) if dwidth_match else (0.0, 0.0)
                path = (float(path_match.group(1)), float(path_match.group(2))) if path_match else (0.0, 0.0)
                galpha = float(galpha_match.group(1)) if galpha_match else 0.0
                score = (int(score_match.group(1)), float(score_match.group(2))) if score_match else (0, 0.0)
                groove_lat = float(groove_lat_match.group(1)) if groove_lat_match else 0.0
                event = (float(event_match.group(1)), int(event_match.group(2)), float(event_match.group(3))) if event_match else (1.0, 0, 0.0)
                branch_id = int(branch_match.group(1)) if branch_match else 0
                bitfields = int(bitfields_match.group(1)) if bitfields_match else 0
                corner_type = int(corner_type_match.group(1)) if corner_type_match else 0
                corner_state = int(corner_state_match.group(1)) if corner_state_match else 0
                wp_ptrs = (int(wp_ptrs_match.group(1)), int(wp_ptrs_match.group(2)), int(wp_ptrs_match.group(3)), int(wp_ptrs_match.group(4))) if wp_ptrs_match else (-1, -1, -1, -1)
                
                waypoint = Waypoint(
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
                    wp_ptrs=wp_ptrs
                )
                waypoints.append(waypoint)
        
        return waypoints 

    def validate_waypoint_structure(self) -> ValidationResult:
        """Validate the waypoint path structure and pointers."""
        if not self.track_data or not self.track_data.waypoints:
            return ValidationResult(False, ["No waypoint data available"], [])
        
        errors = []
        warnings = []
        waypoints = self.track_data.waypoints
        
        # Create index mapping for quick lookup
        waypoint_map = {wp.index: wp for wp in waypoints}
        max_index = max(wp.index for wp in waypoints)
        
        # Check each waypoint's pointers
        for wp in waypoints:
            prev_wp, next_wp, alt_next, branch_merge = wp.wp_ptrs
            
            # Validate prev_wp pointer
            if prev_wp != -1:
                if prev_wp not in waypoint_map:
                    errors.append(f"Waypoint {wp.index}: prev_wp {prev_wp} points to non-existent waypoint")
                elif prev_wp > max_index:
                    errors.append(f"Waypoint {wp.index}: prev_wp {prev_wp} exceeds maximum waypoint index {max_index}")
                else:
                    # Check reciprocal relationship
                    prev_waypoint = waypoint_map[prev_wp]
                    if prev_waypoint.wp_ptrs[1] != wp.index and prev_waypoint.wp_ptrs[2] != wp.index:
                        warnings.append(f"Waypoint {wp.index}: prev_wp {prev_wp} doesn't point back to this waypoint")
            
            # Validate next_wp pointer
            if next_wp != -1:
                if next_wp not in waypoint_map:
                    errors.append(f"Waypoint {wp.index}: next_wp {next_wp} points to non-existent waypoint")
                elif next_wp > max_index:
                    errors.append(f"Waypoint {wp.index}: next_wp {next_wp} exceeds maximum waypoint index {max_index}")
                else:
                    # Check reciprocal relationship
                    next_waypoint = waypoint_map[next_wp]
                    if next_waypoint.wp_ptrs[0] != wp.index:
                        warnings.append(f"Waypoint {wp.index}: next_wp {next_wp} doesn't point back to this waypoint")
            
            # Validate alt_next pointer
            if alt_next != -1:
                if alt_next not in waypoint_map:
                    errors.append(f"Waypoint {wp.index}: alt_next {alt_next} points to non-existent waypoint")
                elif alt_next > max_index:
                    errors.append(f"Waypoint {wp.index}: alt_next {alt_next} exceeds maximum waypoint index {max_index}")
            
            # Validate branch_merge pointer
            if branch_merge != -1:
                if branch_merge not in waypoint_map:
                    errors.append(f"Waypoint {wp.index}: branch_merge {branch_merge} points to non-existent waypoint")
                elif branch_merge > max_index:
                    errors.append(f"Waypoint {wp.index}: branch_merge {branch_merge} exceeds maximum waypoint index {max_index}")
        
        # Check for path continuity
        self._validate_path_continuity(waypoints, waypoint_map, errors, warnings)
        
        # Check branch structure
        self._validate_branch_structure(waypoints, waypoint_map, errors, warnings)
        
        return ValidationResult(len(errors) == 0, errors, warnings)
    
    def _validate_path_continuity(self, waypoints: List[Waypoint], waypoint_map: Dict[int, Waypoint], 
                                 errors: List[str], warnings: List[str]):
        """Validate that the main path forms a continuous loop."""
        main_path_waypoints = [wp for wp in waypoints if wp.branch_id == 0]
        
        if not main_path_waypoints:
            errors.append("No main path waypoints found (branch_id=0)")
            return
        
        # Find start waypoint (one with no valid prev_wp or lowest index)
        start_candidates = [wp for wp in main_path_waypoints if wp.wp_ptrs[0] == -1]
        if not start_candidates:
            start_candidates = [min(main_path_waypoints, key=lambda x: x.index)]
        
        visited = set()
        current = start_candidates[0]
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
            
            # Prevent infinite loops
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
            # Check if branch waypoints eventually merge back to main path
            if wp.branch_merge != -1:
                if wp.branch_merge not in waypoint_map:
                    errors.append(f"Branch waypoint {wp.index}: branch_merge {wp.branch_merge} not found")
                else:
                    merge_wp = waypoint_map[wp.branch_merge]
                    if merge_wp.branch_id != 0:
                        warnings.append(f"Branch waypoint {wp.index}: merges to non-main path waypoint {wp.branch_merge}")
            
            # Validate branch continuity
            if wp.branch_id == 1:  # Pitlane
                if wp.wp_ptrs[1] != -1:
                    next_wp = waypoint_map.get(wp.wp_ptrs[1])
                    if next_wp and next_wp.branch_id != 1 and wp.branch_merge == -1:
                        warnings.append(f"Pitlane waypoint {wp.index}: transitions to non-pitlane without merge point")
    
    def get_path_statistics(self) -> Dict[str, any]:
        """Get statistics about the waypoint path structure."""
        if not self.track_data or not self.track_data.waypoints:
            return {}
        
        waypoints = self.track_data.waypoints
        stats = {
            "total_waypoints": len(waypoints),
            "main_path_waypoints": len([wp for wp in waypoints if wp.branch_id == 0]),
            "pitlane_waypoints": len([wp for wp in waypoints if wp.branch_id == 1]),
            "branch_waypoints": len([wp for wp in waypoints if wp.branch_id > 1]),
            "waypoints_with_alt_next": len([wp for wp in waypoints if wp.wp_ptrs[2] != -1]),
            "waypoints_with_branch_merge": len([wp for wp in waypoints if wp.wp_ptrs[3] != -1]),
            "broken_prev_pointers": len([wp for wp in waypoints if wp.wp_ptrs[0] not in [w.index for w in waypoints] and wp.wp_ptrs[0] != -1]),
            "broken_next_pointers": len([wp for wp in waypoints if wp.wp_ptrs[1] not in [w.index for w in waypoints] and wp.wp_ptrs[1] != -1]),
        }
        
        return stats
    
    def print_validation_report(self):
        if not self.track_data:
            print("No track data loaded. Please parse an AIW file first.")
            return
        
        print("=== AIW Validation Report ===")
        print(f"Track: {getattr(self.track_data, 'filename', 'Unknown')}")
        print()
        
        # Path statistics
        stats = self.get_path_statistics()
        print("Path statistics:")
        for key, value in stats.items():
            print(f"  {key.replace('_', ' ').title()}: {value}")
        print()
        
        # Validation results
        validation = self.validate_waypoint_structure()
        print(f"Validation status: {'PASS' if validation.is_valid else 'FAIL'}")
        print()
        
        if validation.errors:
            print("Errors:")
            for error in validation.errors:
                print(f"  ❌ {error}")
            print()
        
        if validation.warnings:
            print("Warnings:")
            for warning in validation.warnings:
                print(f"  ⚠️  {warning}")
            print()
        
        if validation.is_valid and not validation.warnings:
            print("✅ AIW file structure is valid")
        elif validation.is_valid:
            print("✅ AIW file structure is valid but has warnings")
        else:
            print("❌ AIW file has errors") 