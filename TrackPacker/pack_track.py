#!/usr/bin/env python3
"""
Track packer tool:
Packs a prepared track folder into installable BFF archives and a installable ZIP
"""

import argparse
import logging
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import bff_creator
import mtx2bmt

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).resolve().parent
SEASONS = ("aut", "sno", "spr", "sum", "win")


def build_seasonal_bff(output_bff: Path, name: str, staging: Path) -> None:
    """Build an inert seasonal BFF.

    The game requires a seasonal pak per season to exist, but ignores its name and
    contents, so an archive holding a single marker file satisfies the loader.
    """
    seasonal_dir = staging / "tracks" / "_data" / "instances" / "3dtrees" / "seasonal"
    seasonal_dir.mkdir(parents=True, exist_ok=True)
    (seasonal_dir / "placeholder.txt").write_bytes(b"Placeholder seasonal archive.\n")

    creator = bff_creator.BFFCreator(name)
    creator.compression_type = bff_creator.CompressionType.ZLIB
    creator.add_directory(str(staging))
    creator.create(str(output_bff), compress=True)


def pick_folder() -> str | None:
    """Open a folder picker (used when no folder is passed, e.g. double-click)"""
    try:
        import tkinter
        from tkinter import filedialog

        root = tkinter.Tk()
        root.withdraw()
        path = filedialog.askdirectory(title="Select the prepared track folder to pack")
        root.destroy()
        return path or None
    except Exception:
        return None


def pause_on_exit() -> None:
    """Keep the console open so drag/double-click users can read the result"""
    if getattr(sys, "frozen", False) and sys.stdin and sys.stdin.isatty():
        try:
            input("\nPress Enter to close...")
        except EOFError:
            pass


def copy_tree(src: Path, dst: Path, exclude=(), only_ext=None):
    """Copy files from src to dst; each .mtx also emits a sibling .bmt; returns files copied"""
    if not src.is_dir():
        logger.warning("skipping missing folder: %s", src)
        return 0
    ex = {e.lower() for e in exclude}
    count = 0
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        if rel.parts[0].lower() in ex:
            continue
        if only_ext and path.suffix.lower() not in only_ext:
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        if path.suffix.lower() == ".mtx":
            mtx2bmt.convert(path, out.with_suffix(".bmt"))
        count += 1
    return count


def build_bff(input_dir: Path, output_bff: Path, name: str, no_compress: bool):
    creator = bff_creator.BFFCreator(name)
    creator.compression_type = bff_creator.CompressionType.ZLIB
    creator.add_directory(str(input_dir))
    creator.apply_stock_template(str(output_bff))
    creator.create(str(output_bff), compress=not no_compress)


def infer_track_name(source: Path, explicit: str | None):
    if explicit:
        return explicit
    tracks = source / "Tracks"
    if not tracks.is_dir():
        return source.name
    skip = {"_data", "textures"}
    track_dirs = [d.name for d in sorted(tracks.iterdir()) if d.is_dir() and d.name.lower() not in skip]
    if len(track_dirs) == 1:
        return track_dirs[0]
    tex_dirs = [d.name for d in sorted((tracks / "textures").iterdir())] if (tracks / "textures").is_dir() else []
    if len(tex_dirs) == 1:
        return tex_dirs[0]
    return source.name


def pack_release(source, temp, lower, track, pack_track, out_main, out_physics, out_zip):
    logger.info("Preparing release ZIP staging...")
    stage = temp / f"{lower}_release_stage"
    shutil.rmtree(stage, ignore_errors=True)
    zip_root = stage / "Automobilista 2"

    bff_dir = zip_root / "Pakfiles" / "Tracks"
    bff_dir.mkdir(parents=True)
    shutil.copy2(out_main, bff_dir / out_main.name)
    shutil.copy2(out_physics, bff_dir / out_physics.name)

    logger.info("Generating seasonal placeholder BFFs...")
    seasonal_stage = temp / "seasonal_stage"
    for season in SEASONS:
        name = f"{season}_{pack_track}"
        build_seasonal_bff(bff_dir / f"{name}.bff", name, seasonal_stage)

    tracks = source / "Tracks"
    copy_tree(source / "GUI", zip_root / "GUI")
    copy_tree(tracks / "textures" / track, zip_root / "Tracks" / "textures" / pack_track)
    copy_tree(tracks / track, zip_root / "Tracks" / pack_track, only_ext={".mtx", ".trd"})

    logger.info("Creating release ZIP: %s", out_zip)
    out_zip.unlink(missing_ok=True)
    files = [p for p in sorted(stage.rglob("*")) if p.is_file()]
    prog = bff_creator.ProgressLine()
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, path in enumerate(files, start=1):
            rel = path.relative_to(stage)
            prog.update("Zipping files", i, len(files), str(rel))
            zf.write(path, rel)
    prog.done("Zipping files")


def main(argv) -> int:
    p = argparse.ArgumentParser(description="Packs a track into an installable ZIP file")
    p.add_argument("source", nargs="?", help="Prepared track source folder (drag it onto the tool, or omit to pick one)")
    p.add_argument("--track-name", help="Track name (default: auto-detected)")
    p.add_argument("--no-compress", action="store_true", help="Pack BFFs without compression (faster, but larger BFF filesizes)")
    p.add_argument("--quiet", action="store_true", help="Only show warnings and errors")
    p.add_argument("--verbose", action="store_true", help="Show per-file detail")

    args = p.parse_args(argv)

    bff_creator.configure_logging(args.quiet, args.verbose)

    src_arg = args.source or pick_folder()
    if not src_arg:
        logger.error("No track folder selected.")
        return 1

    source = Path(src_arg).resolve()
    if not source.is_dir():
        logger.error("Not a folder: %s", src_arg)
        return 1
    if not (source / "Tracks").is_dir():
        logger.error("This doesn't look like a prepared track folder (no 'Tracks' subfolder): %s", source)
        return 1

    track = infer_track_name(source, args.track_name)
    if not args.track_name:
        logger.info("Auto-detected track name: %s", track)
    lower = track.lower()
    pack_track = track
    pack_physics = f"{track}_Physics"
    out_zip = source.parent / f"{lower}.zip"
    temp = Path(tempfile.mkdtemp(prefix="omtt_pack_"))
    main_dir, physics_dir = temp / f"{lower}_main", temp / f"{lower}_physics"
    out_main = temp / f"{pack_track}.bff"
    out_physics = temp / f"{pack_physics}.bff"

    try:
        for d in (main_dir, physics_dir):
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)

        tracks = source / "Tracks"

        logger.info("Copying main files and converting MTX->BMT...")
        copy_tree(source / "cameras", main_dir / "cameras")
        copy_tree(source / "GUI", main_dir / "gui")
        copy_tree(tracks / "_data" / "audio", main_dir / "tracks/_data/audio")
        copy_tree(tracks / "textures" / track, main_dir / "tracks/textures" / pack_track)
        copy_tree(tracks / track, main_dir / "tracks" / pack_track, exclude=("physics", "track_cut"))

        logger.info("Copying physics files...")
        copy_tree(tracks / "_data" / "aiw", physics_dir / "tracks/_data/aiw")
        copy_tree(tracks / "_data" / "dynamic" / "physics", physics_dir / "tracks/_data/dynamic/physics")
        copy_tree(tracks / "_data" / "livetrack", physics_dir / "tracks/_data/livetrack")
        copy_tree(tracks / track / "physics", physics_dir / "tracks" / pack_track / "physics")
        copy_tree(tracks / track / "track_cut", physics_dir / "tracks" / pack_track / "track_cut")

        logger.info("Packing %s...", out_main.name)
        build_bff(main_dir, out_main, pack_track, args.no_compress)

        logger.info("Packing %s...", out_physics.name)
        build_bff(physics_dir, out_physics, pack_physics, args.no_compress)

        pack_release(source, temp, lower, track, pack_track, out_main, out_physics, out_zip)
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    logger.info("Done. Created: %s", out_zip)
    return 0


if __name__ == "__main__":
    try:
        code = main(sys.argv[1:])
    except Exception:
        logger.exception("Packing failed")
        code = 1
    pause_on_exit()
    raise SystemExit(code)
