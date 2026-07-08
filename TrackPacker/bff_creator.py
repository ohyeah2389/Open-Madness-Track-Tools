#!/usr/bin/env python3
"""
BFF creator utility:
Packs a prepared directory tree into an unencrypted BFF archive usable by Madness Engine games
"""

from __future__ import annotations

import argparse
import ctypes
import fnmatch
import logging
import os
import struct
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


class CompressionType:
    NONE = 0
    ZLIB = 1
    LZX = 2
    KRAKEN = 3
    MERMAID = 4


def pack_version(major: int = 1, minor: int = 1, interim: int = 0, auto: int = 4) -> int:
    return ((major & 0xF) << 28) | ((minor & 0x3F) << 22) | ((interim & 0x7FF) << 11) | (auto & 0x7FF)


def pack_bdatetime(dt: datetime) -> int:
    milli = int(dt.microsecond / 1000) & 0x3FF
    second = dt.second & 0x3F
    minute = dt.minute & 0x3F
    hour = dt.hour & 0x1F
    day = dt.day & 0x1F
    month = dt.month & 0xF
    year = dt.year & 0xFFFF
    return milli | (second << 10) | (minute << 16) | (hour << 22) | (day << 27) | (month << 32) | (year << 36)


class JamCrc32:
    @classmethod
    def compute(cls, data: bytes) -> int:
        # JamCRC == standard CRC32 with final inversion removed
        return (zlib.crc32(data) ^ 0xFFFFFFFF) & 0xFFFFFFFF


class OodleCompressor:
    LEVEL_NORMAL = 4
    COMPRESSOR_MERMAID = 8

    def __init__(self, dll_path: str):
        p = os.path.abspath(dll_path)
        if not os.path.exists(p):
            raise FileNotFoundError(f"Oodle DLL not found: {p}")
        self.dll = ctypes.CDLL(p)
        self.dll.OodleLZ_Compress.argtypes = [
            ctypes.c_int,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        self.dll.OodleLZ_Compress.restype = ctypes.c_ssize_t
        self.dll.OodleLZ_CompressOptions_GetDefault.argtypes = [ctypes.c_int, ctypes.c_int]
        self.dll.OodleLZ_CompressOptions_GetDefault.restype = ctypes.c_void_p

    def compress(self, data: bytes, level: int = LEVEL_NORMAL, ssto: int = 256) -> bytes:
        raw_len = len(data)
        out_max = raw_len + 274
        out_buf = (ctypes.c_ubyte * out_max)()
        in_buf = (ctypes.c_ubyte * raw_len).from_buffer_copy(data)
        opts = self.dll.OodleLZ_CompressOptions_GetDefault(self.COMPRESSOR_MERMAID, level)
        if opts:
            try:
                ctypes.cast(opts, ctypes.POINTER(ctypes.c_int))[0] = ssto
            except Exception:
                pass
        comp_len = self.dll.OodleLZ_Compress(
            self.COMPRESSOR_MERMAID,
            in_buf,
            ctypes.c_size_t(raw_len),
            out_buf,
            level,
            opts if opts else None,
            None,
            None,
            ctypes.c_size_t(0),
        )
        if comp_len <= 0:
            raise RuntimeError(f"Oodle compression failed: {comp_len}")
        return bytes(out_buf[:comp_len])


def _mix64(a: int, b: int, c: int) -> tuple[int, int, int]:
    m = 0xFFFFFFFFFFFFFFFF
    a = (a - b - c) & m
    a ^= c >> 43
    b = (b - c - a) & m
    b ^= (a << 9) & m
    c = (c - a - b) & m
    c ^= b >> 8
    a = (a - b - c) & m
    a ^= c >> 38
    b = (b - c - a) & m
    b ^= (a << 23) & m
    c = (c - a - b) & m
    c ^= b >> 5
    a = (a - b - c) & m
    a ^= c >> 35
    b = (b - c - a) & m
    b ^= (a << 49) & m
    c = (c - a - b) & m
    c ^= b >> 11
    a = (a - b - c) & m
    a ^= c >> 12
    b = (b - c - a) & m
    b ^= (a << 18) & m
    c = (c - a - b) & m
    c ^= b >> 22
    return a, b, c


def create_uid_bytes(path: str) -> int:
    if not path:
        return 0x8DB63936938575BF

    k = path.lower().replace("/", "\\").encode("ascii", errors="replace")
    length = len(k)
    m = 0xFFFFFFFFFFFFFFFF
    a = 0
    b = 0
    c = 0x9E3779B97F4A7C13

    idx = 0
    rem = length
    while rem >= 24:
        a = (a + ((k[idx + 0] << 56) | (k[idx + 1] << 48) | (k[idx + 2] << 40) | (k[idx + 3] << 32) |
                  (k[idx + 4] << 24) | (k[idx + 5] << 16) | (k[idx + 6] << 8) | k[idx + 7])) & m
        b = (b + ((k[idx + 8] << 56) | (k[idx + 9] << 48) | (k[idx + 10] << 40) | (k[idx + 11] << 32) |
                  (k[idx + 12] << 24) | (k[idx + 13] << 16) | (k[idx + 14] << 8) | k[idx + 15])) & m
        c = (c + ((k[idx + 16] << 56) | (k[idx + 17] << 48) | (k[idx + 18] << 40) | (k[idx + 19] << 32) |
                  (k[idx + 20] << 24) | (k[idx + 21] << 16) | (k[idx + 22] << 8) | k[idx + 23])) & m
        a, b, c = _mix64(a, b, c)
        idx += 24
        rem -= 24

    c = (c + length) & m
    # Tail bytes: a<-bytes 0..7, b<-bytes 8..15, c<-bytes 16..22 (byte 0 of c holds length)
    for i in range(min(rem, 8)):
        a = (a + (k[idx + i] << (8 * i))) & m
    for i in range(min(max(rem - 8, 0), 8)):
        b = (b + (k[idx + 8 + i] << (8 * i))) & m
    for i in range(min(max(rem - 16, 0), 7)):
        c = (c + (k[idx + 16 + i] << (8 * (i + 1)))) & m

    _, _, c = _mix64(a, b, c)
    return c


@dataclass
class FileEntry:
    relative_path: str
    full_path: str
    modified_time: datetime
    data: bytes
    uid: int
    extension: str
    path_backslash: str
    original_size: int
    compressed_data: bytes = b""
    compressed_size: int = 0
    compression_type: int = CompressionType.NONE
    crc32: int = 0
    data_position: int = 0

    @classmethod
    def from_paths(cls, relative_path: str, full_path: str) -> "FileEntry":
        with open(full_path, "rb") as f:
            data = f.read()
        stat = os.stat(full_path)
        rel = relative_path.replace("\\", "/")
        path_backslash = rel.replace("/", "\\")
        ext = os.path.splitext(rel)[1].lstrip(".")
        return cls(
            relative_path=rel,
            full_path=full_path,
            modified_time=datetime.fromtimestamp(stat.st_mtime),
            data=data,
            uid=create_uid_bytes(path_backslash),
            extension=(ext[:4] + "\0\0\0\0")[:4],
            path_backslash=path_backslash,
            original_size=len(data),
        )


class ProgressLine:
    """Single-line \\r progress on stderr; auto-disabled when piped or log level not at INFO"""

    def __init__(self):
        self.enabled = sys.stderr.isatty() and logger.isEnabledFor(logging.INFO)
        self.last_len = 0

    def update(self, activity: str, current: int, total: int, suffix: str = "") -> None:
        if not self.enabled:
            return
        pct = int((current / max(total, 1)) * 100)
        line = f"{activity} [{current}/{total}] {pct:3d}%"
        if suffix:
            line = f"{line} {suffix}"
        pad = max(self.last_len - len(line), 0)
        print(f"\r{line}{' ' * pad}", end="", flush=True, file=sys.stderr)
        self.last_len = len(line)

    def done(self, activity: str) -> None:
        if not self.enabled:
            return
        pad = max(self.last_len - len(f"{activity} [done]"), 0)
        print(f"\r{activity} [done]{' ' * pad}", file=sys.stderr)
        self.last_len = 0


class BFFCreator:
    def __init__(self, archive_name: str = "archive"):
        self.archive_name = archive_name[:0x100]
        self.version = pack_version()
        self.sector_size = 0x10
        self.files: list[FileEntry] = []

        self.compression_type = CompressionType.ZLIB
        self.include_ext_info = True # for compatibility with stock ME archives
        self.include_section_info = True
        self.oodle_dll_path: Optional[str] = None
        self.ext_payload_size_min = 0
        self.section_blob: Optional[bytes] = None
        self.uncompressed_patterns: list[str] = []

    @staticmethod
    def _norm_rel(path: str) -> str:
        return path.replace("/", "\\").strip().lower()

    def set_uncompressed_patterns(self, patterns: list[str]) -> None:
        self.uncompressed_patterns = [self._norm_rel(p) for p in patterns if p and p.strip()]

    def _should_leave_uncompressed(self, path_backslash: str) -> bool:
        if not self.uncompressed_patterns:
            return False
        norm = self._norm_rel(path_backslash)
        return any(fnmatch.fnmatch(norm, p) for p in self.uncompressed_patterns)

    def _parse_ext_paths(self, ext_payload: bytearray, file_count: int, base_ext_offset: int) -> list[str]:
        paths: list[str] = []
        for i in range(file_count):
            off = i * 0x10
            if off + 0x10 > len(ext_payload):
                return []
            name_offset = struct.unpack('<Q', ext_payload[off:off + 8])[0]
            local = name_offset - base_ext_offset
            if local < 0 or local >= len(ext_payload):
                return []
            strlen = ext_payload[local]
            if strlen <= 0 or (local + 1 + strlen) > len(ext_payload):
                return []
            try:
                p = ext_payload[local + 1:local + 1 + strlen].decode("ascii", errors="strict")
            except Exception:
                return []
            paths.append(p)
        return paths

    def _read_template_paths(
        self,
        data: bytes,
        file_count: int,
        toc_size: int,
        ext_info_size: int,
        section_pos: int,
    ) -> list[str]:
        if ext_info_size < 0x308:
            return []
        base = 0x130 + toc_size + 0x308
        if section_pos > base:
            ext_payload_size = section_pos - base
        else:
            ext_payload_size = align(ext_info_size - 0x308, 0x10)
        if ext_payload_size <= 0 or base + ext_payload_size > len(data):
            return []
        payload = bytearray(data[base:base + ext_payload_size])
        return self._parse_ext_paths(payload, file_count, base)

    def apply_stock_template(self, output_path: str) -> None:
        template_path = output_path + ".orig"
        if not os.path.exists(template_path):
            return
        with open(template_path, "rb") as f:
            data = f.read()
        if len(data) < 0x130 or data[0:4] != b" KAP":
            return

        file_count = struct.unpack("<I", data[0x08:0x0C])[0]
        toc_size = struct.unpack("<I", data[0x118:0x11C])[0]
        ext_info_size = struct.unpack("<I", data[0x120:0x124])[0]
        section_pos = struct.unpack("<I", data[0x124:0x128])[0]
        section_size = struct.unpack("<I", data[0x128:0x12C])[0]

        base = 0x130 + toc_size + 0x308
        if section_pos > base:
            self.ext_payload_size_min = max(self.ext_payload_size_min, section_pos - base)
        self.section_blob = None

        if file_count != len(self.files):
            logger.warning("Template %s file count differs (%d vs %d); keeping current order", template_path, file_count, len(self.files))
            return

        template_paths = self._read_template_paths(data, file_count, toc_size, ext_info_size, section_pos)
        if not template_paths or len(template_paths) != len(self.files):
            return

        cur = {self._norm_rel(e.path_backslash): e for e in self.files}
        ordered: list[FileEntry] = []
        for p in template_paths:
            entry = cur.pop(self._norm_rel(p), None)
            if entry is None:
                return
            ordered.append(entry)
        if cur:
            return
        self.files = ordered
        if section_size > 0 and section_pos + section_size <= len(data):
            self.section_blob = bytes(data[section_pos:section_pos + section_size])
        logger.info("Applied stock ordering/template from: %s", template_path)

    def add_directory(self, directory: str, base_path: Optional[str] = None) -> None:
        base = base_path or directory
        for root, dirs, files in os.walk(directory):
            dirs.sort()
            files.sort()
            for name in files:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, base).replace("\\", "/")
                self.files.append(FileEntry.from_paths(rel, full))

    def _compress_one(self, entry: FileEntry, compression_type: int, oodle: Optional[OodleCompressor]) -> FileEntry:
        if self._should_leave_uncompressed(entry.path_backslash):
            compression_type = CompressionType.NONE
        if compression_type == CompressionType.MERMAID:
            if oodle is None:
                raise ValueError("Oodle compressor required for mermaid compression")
            out = oodle.compress(entry.data, level=OodleCompressor.LEVEL_NORMAL, ssto=256)
            ctype = CompressionType.MERMAID
        elif compression_type == CompressionType.ZLIB:
            out = zlib.compress(entry.data, level=6)
            ctype = CompressionType.ZLIB
        else:
            out = entry.data
            ctype = CompressionType.NONE

        entry.compressed_data = out
        entry.compressed_size = len(out)
        entry.compression_type = ctype
        entry.crc32 = JamCrc32.compute(out)
        return entry

    def _compress_batch(self, entries: list[FileEntry], compression_type: int, oodle: Optional[OodleCompressor]) -> list[FileEntry]:
        return [self._compress_one(e, compression_type, oodle) for e in entries]

    def _build_toc_buffer(self) -> bytearray:
        toc_entry_size = 0x2A
        buf = bytearray(len(self.files) * toc_entry_size)
        off = 0
        for e in self.files:
            struct.pack_into("<Q", buf, off, e.uid)
            off += 8
            struct.pack_into("<Q", buf, off, e.data_position)
            off += 8
            struct.pack_into("<I", buf, off, e.compressed_size)
            off += 4
            struct.pack_into("<I", buf, off, e.original_size)
            off += 4
            struct.pack_into("<Q", buf, off, pack_bdatetime(e.modified_time) << 12)
            off += 8
            struct.pack_into("<B", buf, off, e.compression_type)
            off += 1
            struct.pack_into("<B", buf, off, 0)
            off += 1
            struct.pack_into("<I", buf, off, e.crc32)
            off += 4
            ext = e.extension.encode("ascii", errors="replace")[:4]
            buf[off:off + 4] = ext + b"\0" * (4 - len(ext))
            off += 4
        return buf

    def _build_ext_info_buffer(self, header_size: int, toc_size: int) -> tuple[int, bytearray]:
        ext_header_size = 0x308
        ext_entries_size = len(self.files) * 0x10
        string_table_size = sum(1 + len(e.path_backslash.encode("ascii", errors="replace")) for e in self.files)
        unaligned_entries_and_strings = ext_entries_size + string_table_size
        aligned_entries_and_strings = align(unaligned_entries_and_strings, 0x10)
        written_payload_size = max(aligned_entries_and_strings, self.ext_payload_size_min)
        ext_info_total_size_for_header = ext_header_size + unaligned_entries_and_strings

        base_ext_offset = header_size + toc_size + ext_header_size
        rel_string_off = ext_entries_size
        out = bytearray(written_payload_size)
        cursor = 0

        path_blobs: list[bytes] = []
        abs_offsets: list[int] = []
        for e in self.files:
            path_bytes = e.path_backslash.encode("ascii", errors="replace")
            path_blobs.append(path_bytes)
            abs_offsets.append(base_ext_offset + rel_string_off)
            rel_string_off += 1 + len(path_bytes)

        for i, e in enumerate(self.files):
            struct.pack_into("<Q", out, cursor, abs_offsets[i])
            cursor += 8
            struct.pack_into("<Q", out, cursor, pack_bdatetime(e.modified_time))
            cursor += 8

        for blob in path_blobs:
            out[cursor] = len(blob) & 0xFF
            cursor += 1
            out[cursor:cursor + len(blob)] = blob
            cursor += len(blob)

        return ext_info_total_size_for_header, out

    def _write_header(self, f, file_count: int, toc_size: int, ext_info_size: int, data_offset: int, section_pos: int, section_size: int) -> None:
        f.write(b" KAP")
        f.write(struct.pack("<I", self.version))
        f.write(struct.pack("<I", file_count))
        f.write(struct.pack("<Q", data_offset))
        f.write(struct.pack("<I", self.sector_size))

        name = self.archive_name.encode("ascii", errors="replace")[:0x100]
        f.write(name + (b"\0" * (0x100 - len(name))))
        f.write(struct.pack("<I", toc_size))
        f.write(struct.pack("<I", 0))
        f.write(struct.pack("<I", ext_info_size))
        f.write(struct.pack("<I", section_pos))
        f.write(struct.pack("<I", section_size))
        f.write(struct.pack("<B", 0))
        f.write(struct.pack("<B", 0))
        f.write(struct.pack("<H", 0))

    def _write_ext_header(self, f, info_size: int) -> None:
        f.write(struct.pack("<I", 0x45585420))
        f.write(struct.pack("<I", info_size))
        cfg = b"Reiza.xml"
        plat = b"PC"
        f.write(cfg + b"\0" * (0x100 - len(cfg)))
        f.write(b"\0" * 0x100)
        f.write(plat + b"\0" * (0x100 - len(plat)))

    def _build_default_section_blob(self) -> bytes:
        out = bytearray()
        out.extend(b"DHSA")
        out.extend(struct.pack("<I", 0x10000000))
        out.extend(struct.pack("<I", len(self.files)))
        for i, e in enumerate(self.files):
            out.extend(struct.pack("<Q", (i << 32) & 0xFFFFFFFFFFFFFFFF))
            out.extend(struct.pack("<I", 1))
            out.extend(struct.pack("<I", e.compressed_size))
        return bytes(out)

    def _write_section_info(self, f, section_blob: bytes) -> None:
        f.write(section_blob)

    def _get_section_blob(self) -> bytes:
        if self.section_blob is not None:
            return self.section_blob
        return self._build_default_section_blob()

    def create(self, output_path: str, compress: bool = True, workers: Optional[int] = None) -> None:
        prog = ProgressLine()

        oodle = None
        if self.compression_type == CompressionType.MERMAID:
            if not self.oodle_dll_path:
                raise ValueError("Oodle DLL path required for mermaid compression")
            oodle = OodleCompressor(self.oodle_dll_path)

        mode = self.compression_type if compress else CompressionType.NONE
        total = len(self.files)
        total_bytes = sum(e.original_size for e in self.files)
        forced_workers = workers if workers and workers > 0 else 0
        auto_workers = max(2, min(8, (os.cpu_count() or 4)))

        should_parallel = (
            mode == CompressionType.ZLIB
            and total > 1
            and (
                forced_workers > 1
                or (total >= 24 and total_bytes >= (64 * 1024 * 1024))
            )
        )

        if should_parallel:
            max_workers = min(total, forced_workers if forced_workers > 1 else auto_workers)
            chunk_size = 8 if total < 256 else 16
            futures = {}
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                for start in range(0, total, chunk_size):
                    chunk = self.files[start:start + chunk_size]
                    fut = pool.submit(self._compress_batch, chunk, mode, oodle)
                    futures[fut] = start

                done = 0
                for fut in as_completed(futures):
                    start = futures[fut]
                    out_chunk = fut.result()
                    self.files[start:start + len(out_chunk)] = out_chunk
                    done += len(out_chunk)
                    prog.update("Compressing files", done, total, out_chunk[-1].relative_path if out_chunk else "")
            prog.done("Compressing files")
        else:
            activity = "Compressing files" if compress else "Reading files"
            for i, e in enumerate(self.files, start=1):
                self.files[i - 1] = self._compress_one(e, mode, oodle)
                prog.update(activity, i, total, e.relative_path)
            prog.done(activity)

        header_size = 0x130
        toc_entry_size = 0x2A
        toc_size = len(self.files) * toc_entry_size
        ext_info_size_for_header = 0
        ext_data = bytearray()

        if self.include_ext_info:
            ext_info_size_for_header, ext_data = self._build_ext_info_buffer(header_size, toc_size)
            ext_written_size = 0x308 + len(ext_data)
            ext_end = header_size + toc_size + ext_written_size
        else:
            ext_end = header_size + toc_size

        section_blob = self._get_section_blob() if self.include_section_info else b""
        section_size = len(section_blob) if self.include_section_info else 0
        section_pos = ext_end if self.include_section_info else 0
        data_offset = align((section_pos + section_size) if self.include_section_info else ext_end, self.sector_size)

        pos = data_offset
        for e in self.files:
            e.data_position = pos
            pos += align(e.compressed_size, self.sector_size)

        toc_buf = self._build_toc_buffer()
        with open(output_path, "wb") as f:
            self._write_header(f, len(self.files), toc_size, ext_info_size_for_header, data_offset, section_pos, section_size)
            f.write(toc_buf)

            if self.include_ext_info:
                self._write_ext_header(f, ext_info_size_for_header - 0x308)
                f.write(ext_data)

            if self.include_section_info:
                self._write_section_info(f, section_blob)

            cur = f.tell()
            if cur < data_offset:
                f.write(b"\0" * (data_offset - cur))

            for i, e in enumerate(self.files, start=1):
                prog.update("Writing files", i, total, e.relative_path)
                f.write(e.compressed_data)
                pad = align(e.compressed_size, self.sector_size) - e.compressed_size
                if pad:
                    f.write(b"\0" * pad)
            prog.done("Writing files")

        logger.info("Created %s (%d files, %s bytes)", output_path, len(self.files), f"{os.path.getsize(output_path):,}")


def configure_logging(quiet: bool = False, verbose: bool = False) -> None:
    level = logging.WARNING if quiet else logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Create BFF/PAK archive files for Automobilista 2")
    p.add_argument("input_dir", help="Input directory to pack")
    p.add_argument("output_file", help="Output BFF file path")
    p.add_argument("--name", "-n", help="Archive name (default: output file stem)")
    p.add_argument("--no-compress", action="store_true", help="Disable compression")
    p.add_argument("--compression", choices=["zlib", "mermaid"], default="zlib", help="Compression type")
    p.add_argument("--oodle-dll", help="Path to oo2core DLL (required for mermaid)")
    p.add_argument("--ext-info", action="store_true", help="Enable extended info table")
    p.add_argument("--section-info", action="store_true", help="Deprecated: section info is now always included")
    p.add_argument("--leave-uncompressed", action="append", nargs="+", default=[], metavar="PATH", help="Relative path(s) to keep uncompressed (supports wildcards, slash-insensitive)")
    p.add_argument("--quiet", action="store_true", help="Only show warnings and errors")
    p.add_argument("-v", "--verbose", action="store_true", help="Show per-file detail")
    p.add_argument("--workers", type=int, default=0, help="Thread count for zlib (0=auto)")

    args = p.parse_args(argv)

    configure_logging(args.quiet, args.verbose)
    
    if not os.path.isdir(args.input_dir):
        logger.error("Input directory not found: %s", args.input_dir)
        return 1
    if args.compression == "mermaid":
        if not args.oodle_dll:
            logger.error("--oodle-dll is required when --compression=mermaid")
            return 1
        if not os.path.exists(args.oodle_dll):
            logger.error("Oodle DLL not found: %s", args.oodle_dll)
            return 1

    archive_name = args.name or os.path.splitext(os.path.basename(args.output_file))[0]
    creator = BFFCreator(archive_name=archive_name)
    creator.include_ext_info = True
    creator.include_section_info = True
    creator.compression_type = CompressionType.MERMAID if args.compression == "mermaid" else CompressionType.ZLIB
    creator.oodle_dll_path = args.oodle_dll

    logger.info("Scanning directory: %s", args.input_dir)
    creator.add_directory(args.input_dir)
    if not creator.files:
        logger.error("No files found in input directory")
        return 1
    creator.apply_stock_template(args.output_file)
    creator.set_uncompressed_patterns([p for group in args.leave_uncompressed for p in group])

    creator.create(output_path=args.output_file, compress=not args.no_compress, workers=args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
