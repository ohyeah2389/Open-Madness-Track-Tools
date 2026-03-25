Contains LiveTrack precalculated raster info ("Weathering-In")
Raster format is efficient, only storing cells with data
https://www.youtube.com/watch?v=bMdkxhRjoqs

Contains the following channels:
* friction
	* Racing line proximity (0.0-1.0 float, stored as uint8 0-255)
* height
	* Water pooling areas (0.0-1.0 float, stored as uint8 0-255)
* grip
	* Rubbered areas (0.0-1.0 float, stored as uint8 0-255)
* flags
	* 8 bit flags, in any combination
		* 0. Racing line
		* 1. Asphalt area
		* 2. Dirt/gravel/marbles 1?
		* 3. Dirt/gravel/marbles 2?
		* 4. Dirt/gravel/marbles 3?
		* 5. Unseen
		* 6. Curbs
		* 7. Unseen
* mask
	* Areas with data

## File Format

MRDF container with 3 sections:
* PRIMARY_DATA (0x01) - grid metadata, cell data, row offset table
* POINTER_RELOCATION (0x10) - pointers the game needs to relocate at runtime
* RASTER_CELLS (0x50) - material type definitions

## PRIMARY_DATA Section

Grid metadata header is 0x70 bytes:
* 0x00: 8 bytes header prefix
* 0x08: 4 floats for world bounds (min_x, min_y, max_x, max_y)
* 0x18: 2 uint32 for grid dimensions (width, height)
* 0x20: uint32 unknown + float cell_size
* 0x28: uint32 total cell count
* 0x2C: float cell_size (duplicate)
* 0x30: 40 bytes padding
* 0x58: uint64 pointer to cell data (relocated by game)
* 0x60: 8 bytes padding
* 0x68: uint64 pointer to row offset table (relocated by game)

Cell data is 6 bytes per cell, sorted by Y then X:
* uint16 grid X coordinate
* uint8 friction
* uint8 height
* uint8 grip
* uint8 surface flags

Row offset table has (height + 1) uint32 entries, each pointing to first cell in that row

## RASTER_CELLS Section

Material type definitions
* Material types (0-15) stored in cell surface flags (bits 2-5)
* Format: [material_type (uint32), property_value (float)] repeated, then total_count (uint32)
* Example from stock files: Material 3 has 3 properties [0.01608, 0.0, 0.0]
* Exact property meanings are unknown

## Initialization Cells

Game expects these cells at specific indices:
* Index 0: X=112, Y=0 (init marker)
* Index 1: X=0, Y=1 (calibration with friction?)
* Index 2: X=0, Y=1 (calibration with grip + flags?)
* Index 3: X=22, Y=1 (additional calibration?)
