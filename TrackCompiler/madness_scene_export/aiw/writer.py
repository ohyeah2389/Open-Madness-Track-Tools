from . import parser


def write_aiw_file(track_data: parser.TrackData, filepath: str):
    """Writes AIW file with standard Madness AIW format."""
    with open(filepath, "w", encoding="utf-8") as f:
        # Write Features section
        f.write("[Features]\n")
        f.write(f"waypointspan={track_data.features.waypoint_span:.2f}\n")
        f.write(f"pitlanes={track_data.features.pitlanes}\n")
        f.write(f"startinggrid={track_data.features.starting_grid}\n")
        f.write(f"pitspots={track_data.features.pit_spots}\n")
        f.write(f"garagespots={track_data.features.garage_spots}\n")
        f.write(f"clippingpoints={track_data.features.clipping_points}\n")
        f.write(f"driftversion={track_data.features.drift_version}\n")
        f.write(f"cornermarkerversion={track_data.features.corner_marker_version}\n")
        f.write(
            f"AI Late Braking Fraction={track_data.features.ai_late_braking_fraction:.6f}\n"
        )
        f.write(f"Track Difficulty={track_data.features.track_difficulty:.6f}\n")
        f.write(f"Oval={1 if track_data.features.oval else 0}\n")
        f.write(f"RallyCross={1 if track_data.features.rallycross else 0}\n")
        f.write(f"IceTrack={1 if track_data.features.ice_track else 0}\n")
        f.write(f"IceTrackSolo={1 if track_data.features.ice_track_solo else 0}\n")
        f.write(f"IsNarrowTrack={1 if track_data.features.narrow_track else 0}\n")
        f.write(
            f"AnticipationDistMin={track_data.features.anticipation_dist_min:.6f}\n"
        )
        f.write(
            f"AnticipationDistOffRoad={track_data.features.anticipation_dist_off_road:.6f}\n"
        )
        f.write(
            f"AnticipationDistWall={track_data.features.anticipation_dist_wall:.6f}\n"
        )
        f.write(f"Race Start Disabled={track_data.features.race_start_disabled:.6f}\n")
        f.write(f"AI Setup Gearing={track_data.features.ai_setup_gearing:.6f}\n")
        f.write(f"AI Setup Downforce={track_data.features.ai_setup_downforce:.6f}\n")
        f.write(f"AI Setup Balance={track_data.features.ai_setup_balance:.6f}\n")
        f.write("\n")

        # Write Grid section
        f.write("[GRID]\n")
        for grid_spot in track_data.grid_spots:
            f.write(f"GridIndex={grid_spot.index}\n")
            f.write(
                f"Pos=({grid_spot.position.x:.3f},{grid_spot.position.y:.3f},{grid_spot.position.z:.3f})\n"
            )
            f.write(
                f"Ori=({grid_spot.orientation.x:.3f},{grid_spot.orientation.y:.3f},{grid_spot.orientation.z:.3f})\n"
            )
        f.write("\n")

        # Write Rolling Start section
        f.write("[ROLLING START]\n")
        for rolling_start in track_data.rolling_starts:
            f.write(f'RaceType="{rolling_start.race_type}"\n')
            f.write(f"DistanceBehindGrid={rolling_start.distance_behind_grid:.3f}\n")
            f.write(f"DistanceBetweenRows={rolling_start.distance_between_rows:.3f}\n")
            f.write(f"CarsInRow={rolling_start.cars_in_row}\n")
            f.write(f"StartSpeed={rolling_start.start_speed:.3f}\n")
            f.write(f"MaxSpeed={rolling_start.max_speed:.3f}\n")
        f.write("\n")

        # Write Teleport section
        f.write("[TELEPORT]\n")
        for teleport_spot in track_data.teleport_spots:
            f.write(f"GridIndex={teleport_spot.index}\n")
            f.write(
                f"Pos=({teleport_spot.position.x:.3f},{teleport_spot.position.y:.3f},{teleport_spot.position.z:.3f})\n"
            )
            f.write(
                f"Ori=({teleport_spot.orientation.x:.3f},{teleport_spot.orientation.y:.3f},{teleport_spot.orientation.z:.3f})\n"
            )
        f.write("\n")

        # Write Clipping Points section (empty for now)
        f.write("[CLIPPING POINTS]\n")
        f.write("\n")

        # Write Pits section
        f.write("[PITS]\n")
        for pit_spot in track_data.pit_spots:
            f.write(f"TeamIndex={pit_spot.team_index}\n")
            f.write(f"PitLeftHanded={1 if pit_spot.left_handed else 0}\n")
            f.write(
                f"PitPos=({pit_spot.position.x:.3f},{pit_spot.position.y:.3f},{pit_spot.position.z:.3f})\n"
            )
            f.write(
                f"PitOri=({pit_spot.orientation.x:.3f},{pit_spot.orientation.y:.3f},{pit_spot.orientation.z:.3f})\n"
            )

            # Always write garage entries for all possible garage spots (even if empty)
            max_garage_spots = track_data.features.garage_spots
            for i in range(max_garage_spots):
                if i < len(pit_spot.garage_positions):
                    # Real garage data
                    garage_pos = pit_spot.garage_positions[i]
                    garage_ori = pit_spot.garage_orientations[i]
                    f.write(
                        f"GarLeftHanded=({i},0)\n"
                    )  # Garages are typically not left-handed
                    f.write(
                        f"GarPos=({i},{garage_pos.x:.3f},{garage_pos.y:.3f},{garage_pos.z:.3f})\n"
                    )
                    f.write(
                        f"GarOri=({i},{garage_ori.x:.3f},{garage_ori.y:.3f},{garage_ori.z:.3f})\n"
                    )
                else:
                    # Empty garage data (zeros)
                    f.write(f"GarLeftHanded=({i},0)\n")
                    f.write(f"GarPos=({i},0.000,0.000,0.000)\n")
                    f.write(f"GarOri=({i},0.000,0.000,0.000)\n")
        f.write("\n")

        # Write Waypoint section
        f.write("[Waypoint]\n")

        # Write waypoint metadata
        meta = track_data.waypoint_metadata
        f.write(f"trackstate={meta.trackstate}\n")
        if meta.pit_extensions_start >= 0 and meta.pit_extensions_end >= 0:
            f.write(f"PitExtensionsStart={meta.pit_extensions_start}\n")
            f.write(f"PitExtensionsEnd={meta.pit_extensions_end}\n")
        f.write(f"times=({meta.times[0]:.4f},{meta.times[1]:.4f})\n")
        f.write(f"number_waypoints={meta.number_waypoints}\n")
        f.write(f"lap_length={meta.lap_length:.6f}\n")
        f.write(f"sector_1_length={meta.sector_1_length:.6f}\n")
        f.write(f"sector_2_length={meta.sector_2_length:.6f}\n")
        f.write(f"FuelUse={meta.fuel_use:.6f}\n")
        f.write(f"GrooveWidth={meta.groove_width:.6f}\n")
        f.write(f"GrooveWidthWet={meta.groove_width_wet:.6f}\n")
        f.write(f"IntermediateFogLevel=({meta.intermediate_fog_level:.4f})\n")
        f.write(
            f"IntermediateFogPlanes=({meta.intermediate_fog_planes[0]:.1f},{meta.intermediate_fog_planes[1]:.1f})\n"
        )
        f.write(
            f"RainyFogPlanes=({meta.rainy_fog_planes[0]:.1f},{meta.rainy_fog_planes[1]:.1f})\n"
        )
        f.write(
            f"IntermediateFogColor=({meta.intermediate_fog_color[0]:.1f},{meta.intermediate_fog_color[1]:.1f},{meta.intermediate_fog_color[2]:.1f})\n"
        )
        f.write(
            f"RainyFogColor=({meta.rainy_fog_color[0]:.1f},{meta.rainy_fog_color[1]:.1f},{meta.rainy_fog_color[2]:.1f})\n"
        )
        f.write(f"FogDensity=({meta.fog_density[0]:.5f},{meta.fog_density[1]:.5f})\n")
        f.write(
            f"RainyDarkness=({meta.rainy_darkness[0]:.5f},{meta.rainy_darkness[1]:.5f})\n"
        )
        f.write(f"GarageDepth=({meta.garage_depth:.4f})\n")
        f.write(f"PitStopSpaceFront=({meta.pit_stop_space_front:.4f})\n")
        f.write(f"PitStopSpaceBack=({meta.pit_stop_space_back:.4f})\n")
        f.write(f"PitStopJoinIn=({meta.pit_stop_join_in:.4f})\n")
        f.write(f"PitStopJoinOut=({meta.pit_stop_join_out:.4f})\n")
        f.write(f"UseLineBlendSpeed={meta.use_line_blend_speed}\n")

        # Write waypoints
        for waypoint in track_data.waypoints:
            f.write(f"\\\\{waypoint.index}\n")
            f.write(
                f"wp_pos=({waypoint.position.x:.4f},{waypoint.position.y:.4f},{waypoint.position.z:.4f})\n"
            )
            f.write(
                f"wp_perp=({waypoint.perpendicular.x:.4f},{waypoint.perpendicular.y:.4f},{waypoint.perpendicular.z:.4f})\n"
            )
            f.write(f"wp_width=({waypoint.width[0]:.3f},{waypoint.width[1]:.3f})\n")
            f.write(f"wp_dwidth=({waypoint.dwidth[0]:.3f},{waypoint.dwidth[1]:.3f})\n")
            f.write(f"wp_path=({waypoint.path[0]:.4f},{waypoint.path[1]:.4f})\n")
            f.write(f"wp_galpha=({waypoint.galpha:.4f})\n")
            f.write(f"wp_score=({waypoint.score[0]},{waypoint.score[1]:.3f})\n")
            f.write(f"wp_groove_lat=({waypoint.groove_lat:.6f})\n")
            f.write(
                f"wp_event=({waypoint.event[0]:.3f},{waypoint.event[1]},{waypoint.event[2]:.6f})\n"
            )
            f.write(f"wp_branchID=({waypoint.branch_id})\n")
            f.write(f"wp_bitfields=({waypoint.bitfields})\n")
            f.write(f"wpd_CornerType=({waypoint.corner_type})\n")
            f.write(f"wpd_CornerState=({waypoint.corner_state})\n")
            f.write(
                f"WP_PTRS=({waypoint.wp_ptrs[0]},{waypoint.wp_ptrs[1]},{waypoint.wp_ptrs[2]},{waypoint.wp_ptrs[3]})\n"
            )
