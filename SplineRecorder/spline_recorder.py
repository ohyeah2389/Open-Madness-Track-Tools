"""Records driven laps from Automobilista 2 and exports each one as a CSV"""

import csv
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, ttk

from recorder import Recorder, format_laptime
from shared_memory import SharedMemoryReader

POLL_MS = 200
SAMPLE_S = 0.01


def _slug(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text.strip())
    return cleaned.strip("._") or "lap"


def write_csv(path: Path, lap) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write("# spline-recorder 1\n")
        handle.write("# coords=engine (Y up)\n")
        handle.write(f"# track={lap.track}\n")
        handle.write(f"# variation={lap.variation}\n")
        handle.write(f"# car={lap.car}\n")
        handle.write(f"# lap_time_s={lap.lap_time:.3f}\n")
        handle.write(f"# invalid={int(lap.invalid)}\n")
        handle.write(f"# track_length_m={lap.track_length:.3f}\n")
        writer = csv.writer(handle)
        writer.writerow(["x", "y", "z", "distance_m", "speed_mps"])
        for sample in lap.samples:
            writer.writerow([
                f"{sample.x:.4f}",
                f"{sample.y:.4f}",
                f"{sample.z:.4f}",
                f"{sample.distance:.3f}",
                f"{sample.speed:.3f}",
            ])


def _export_path(folder: Path, lap) -> Path:
    clock = format_laptime(lap.lap_time).replace(":", "m").replace(".", "s")
    if clock == "—":
        clock = f"lap{lap.game_lap}"
    name = "_".join(part for part in (_slug(lap.track), _slug(lap.variation), clock) if part)
    if lap.invalid:
        name += "_invalid"
    path = folder / f"{name}.csv"
    n = 2
    while path.exists():
        path = folder / f"{name}_{n}.csv"
        n += 1
    return path


class _Telemetry(threading.Thread):
    def __init__(self, recorder: Recorder):
        super().__init__(daemon=True)
        self.recorder = recorder
        self._stop = threading.Event()

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        while not self._stop.is_set():
            reader = SharedMemoryReader()
            if not reader.open():
                self.recorder.mark_disconnected()
                self._stop.wait(0.5)
                continue
            last_seq = None
            stale = 0
            while not self._stop.is_set():
                frame = reader.read()
                if frame is None:
                    self._stop.wait(SAMPLE_S)
                    continue
                if frame.sequence == last_seq:
                    stale += 1
                    if stale > 200:
                        break
                else:
                    stale = 0
                    last_seq = frame.sequence
                self.recorder.ingest(frame)
                self._stop.wait(SAMPLE_S)
            reader.close()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Spline Recorder")
        self.geometry("760x440")
        self.minsize(640, 360)
        self.recorder = Recorder()
        self.folder = Path(__file__).resolve().parent / "recordings"
        self._telemetry = _Telemetry(self.recorder)
        self._rows: set[str] = set()
        self._shown_detail = ""

        self.status = tk.StringVar(value="Waiting for Automobilista 2")
        self.detail = tk.StringVar()
        self.folder_var = tk.StringVar(value=str(self.folder))
        self.spacing_var = tk.StringVar(value="1.0")

        pad = {"padx": 10, "pady": 4}
        ttk.Label(self, textvariable=self.status).pack(anchor="w", **pad)
        ttk.Label(self, textvariable=self.detail).pack(anchor="w", padx=10)

        columns = ("lap", "time", "track", "car", "points", "length", "note")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        headings = {
            "lap": ("Lap", 50),
            "time": ("Time", 80),
            "track": ("Track", 160),
            "car": ("Car", 140),
            "points": ("Points", 70),
            "length": ("Length", 80),
            "note": ("", 70),
        }
        for key, (title, width) in headings.items():
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=10, pady=8)
        self.tree.bind("<Double-1>", lambda _event: self._export_selected())
        self.tree.bind("<Delete>", lambda _event: self._remove_selected())

        options = ttk.Frame(self)
        options.pack(fill="x", padx=10, pady=2)
        ttk.Label(options, text="Point spacing").pack(side="left")
        spacing = ttk.Spinbox(
            options, from_=0.25, to=10, increment=0.25, width=6,
            textvariable=self.spacing_var, command=self._apply_spacing,
        )
        spacing.pack(side="left", padx=(6, 2))
        spacing.bind("<Return>", lambda _event: self._apply_spacing())
        spacing.bind("<FocusOut>", lambda _event: self._apply_spacing())
        ttk.Label(options, text="m").pack(side="left", padx=(0, 16))
        ttk.Label(options, text="Export folder").pack(side="left")
        ttk.Entry(options, textvariable=self.folder_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(options, text="Browse", command=self._browse).pack(side="left")

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=10, pady=(4, 10))
        ttk.Button(buttons, text="Export CSV", command=self._export_selected).pack(side="left")
        ttk.Button(buttons, text="Remove", command=self._remove_selected).pack(side="left", padx=6)

        self.protocol("WM_DELETE_WINDOW", self._close)
        self._telemetry.start()
        self.after(POLL_MS, self._refresh)

    def _apply_spacing(self) -> None:
        try:
            self.recorder.set_spacing(float(self.spacing_var.get()))
        except ValueError:
            self.spacing_var.set(f"{self.recorder.spacing:.2f}")

    def _browse(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.folder_var.get() or str(self.folder))
        if chosen:
            self.folder_var.set(chosen)

    def _selected_id(self) -> int | None:
        selection = self.tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def _export_selected(self) -> None:
        lap_id = self._selected_id()
        if lap_id is None:
            return
        lap = self.recorder.lap_by_id(lap_id)
        if lap is None:
            return
        folder = Path(self.folder_var.get())
        path = _export_path(folder, lap)
        write_csv(path, lap)
        self.detail.set(f"Exported {path.name}")

    def _remove_selected(self) -> None:
        lap_id = self._selected_id()
        if lap_id is not None:
            self.recorder.delete(lap_id)

    def _refresh(self) -> None:
        state = self.recorder.view()
        self.status.set(state.status)
        if state.detail != self._shown_detail:
            self._shown_detail = state.detail
            self.detail.set(state.detail)
        seen = set()
        for lap in state.laps:
            iid = str(lap.id)
            seen.add(iid)
            track = lap.track
            if lap.variation:
                track = f"{track} {lap.variation}"
            values = (
                lap.game_lap,
                format_laptime(lap.lap_time),
                track,
                lap.car,
                len(lap.samples),
                f"{lap.length_m:.0f} m",
                "invalid" if lap.invalid else "",
            )
            if iid in self._rows:
                self.tree.item(iid, values=values)
            else:
                self.tree.insert("", "end", iid=iid, values=values)
                self._rows.add(iid)
        for iid in self._rows - seen:
            self.tree.delete(iid)
        self._rows = seen
        self.after(POLL_MS, self._refresh)

    def _close(self) -> None:
        self._telemetry.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
