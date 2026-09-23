"""Reads Automobilista 2 shared-memory blocks"""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass

VERSION = 14
MAP_NAME = "$pcars2$"
FILE_MAP_READ = 0x0004

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_OpenFileMappingW = _kernel32.OpenFileMappingW
_OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_OpenFileMappingW.restype = wintypes.HANDLE
_MapViewOfFile = _kernel32.MapViewOfFile
_MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
_MapViewOfFile.restype = ctypes.c_void_p
_UnmapViewOfFile = _kernel32.UnmapViewOfFile
_UnmapViewOfFile.argtypes = [ctypes.c_void_p]
_UnmapViewOfFile.restype = wintypes.BOOL
_CloseHandle = _kernel32.CloseHandle
_CloseHandle.argtypes = [wintypes.HANDLE]
_CloseHandle.restype = wintypes.BOOL


def _vec():
    return ctypes.c_float * 3


def _vec4():
    return ctypes.c_float * 4


class ParticipantInfo(ctypes.Structure):
    _fields_ = [
        ("mIsActive", ctypes.c_bool),
        ("mName", ctypes.c_char * 64),
        ("mWorldPosition", _vec()),
        ("mCurrentLapDistance", ctypes.c_float),
        ("mRacePosition", ctypes.c_uint),
        ("mLapsCompleted", ctypes.c_uint),
        ("mCurrentLap", ctypes.c_uint),
        ("mCurrentSector", ctypes.c_int),
    ]


class SharedMemory(ctypes.Structure):
    """Prefix of the block through mSequenceNumber; later fields are unused"""

    _fields_ = [
        ("mVersion", ctypes.c_uint),
        ("mBuildVersionNumber", ctypes.c_uint),
        ("mGameState", ctypes.c_uint),
        ("mSessionState", ctypes.c_uint),
        ("mRaceState", ctypes.c_uint),
        ("mViewedParticipantIndex", ctypes.c_int),
        ("mNumParticipants", ctypes.c_int),
        ("mParticipantInfo", ParticipantInfo * 64),
        ("mUnfilteredThrottle", ctypes.c_float),
        ("mUnfilteredBrake", ctypes.c_float),
        ("mUnfilteredSteering", ctypes.c_float),
        ("mUnfilteredClutch", ctypes.c_float),
        ("mCarName", ctypes.c_char * 64),
        ("mCarClassName", ctypes.c_char * 64),
        ("mLapsInEvent", ctypes.c_uint),
        ("mTrackLocation", ctypes.c_char * 64),
        ("mTrackVariation", ctypes.c_char * 64),
        ("mTrackLength", ctypes.c_float),
        ("mNumSectors", ctypes.c_int),
        ("mLapInvalidated", ctypes.c_bool),
        ("mBestLapTime", ctypes.c_float),
        ("mLastLapTime", ctypes.c_float),
        ("mCurrentTime", ctypes.c_float),
        ("mSplitTimeAhead", ctypes.c_float),
        ("mSplitTimeBehind", ctypes.c_float),
        ("mSplitTime", ctypes.c_float),
        ("mEventTimeRemaining", ctypes.c_float),
        ("mPersonalFastestLapTime", ctypes.c_float),
        ("mWorldFastestLapTime", ctypes.c_float),
        ("mCurrentSector1Time", ctypes.c_float),
        ("mCurrentSector2Time", ctypes.c_float),
        ("mCurrentSector3Time", ctypes.c_float),
        ("mFastestSector1Time", ctypes.c_float),
        ("mFastestSector2Time", ctypes.c_float),
        ("mFastestSector3Time", ctypes.c_float),
        ("mPersonalFastestSector1Time", ctypes.c_float),
        ("mPersonalFastestSector2Time", ctypes.c_float),
        ("mPersonalFastestSector3Time", ctypes.c_float),
        ("mWorldFastestSector1Time", ctypes.c_float),
        ("mWorldFastestSector2Time", ctypes.c_float),
        ("mWorldFastestSector3Time", ctypes.c_float),
        ("mHighestFlagColour", ctypes.c_uint),
        ("mHighestFlagReason", ctypes.c_uint),
        ("mPitMode", ctypes.c_uint),
        ("mPitSchedule", ctypes.c_uint),
        ("mCarFlags", ctypes.c_uint),
        ("mOilTempCelsius", ctypes.c_float),
        ("mOilPressureKPa", ctypes.c_float),
        ("mWaterTempCelsius", ctypes.c_float),
        ("mWaterPressureKPa", ctypes.c_float),
        ("mFuelPressureKPa", ctypes.c_float),
        ("mFuelLevel", ctypes.c_float),
        ("mFuelCapacity", ctypes.c_float),
        ("mSpeed", ctypes.c_float),
        ("mRpm", ctypes.c_float),
        ("mMaxRPM", ctypes.c_float),
        ("mBrake", ctypes.c_float),
        ("mThrottle", ctypes.c_float),
        ("mClutch", ctypes.c_float),
        ("mSteering", ctypes.c_float),
        ("mGear", ctypes.c_int),
        ("mNumGears", ctypes.c_int),
        ("mOdometerKM", ctypes.c_float),
        ("mAntiLockActive", ctypes.c_bool),
        ("mLastOpponentCollisionIndex", ctypes.c_int),
        ("mLastOpponentCollisionMagnitude", ctypes.c_float),
        ("mBoostActive", ctypes.c_bool),
        ("mBoostAmount", ctypes.c_float),
        ("mOrientation", _vec()),
        ("mLocalVelocity", _vec()),
        ("mWorldVelocity", _vec()),
        ("mAngularVelocity", _vec()),
        ("mLocalAcceleration", _vec()),
        ("mWorldAcceleration", _vec()),
        ("mExtentsCentre", _vec()),
        ("mTyreFlags", ctypes.c_uint * 4),
        ("mTerrain", ctypes.c_uint * 4),
        ("mTyreY", _vec4()),
        ("mTyreRPS", _vec4()),
        ("mTyreSlipSpeed", _vec4()),
        ("mTyreTemp", _vec4()),
        ("mTyreGrip", _vec4()),
        ("mTyreHeightAboveGround", _vec4()),
        ("mTyreLateralStiffness", _vec4()),
        ("mTyreWear", _vec4()),
        ("mBrakeDamage", _vec4()),
        ("mSuspensionDamage", _vec4()),
        ("mBrakeTempCelsius", _vec4()),
        ("mTyreTreadTemp", _vec4()),
        ("mTyreLayerTemp", _vec4()),
        ("mTyreCarcassTemp", _vec4()),
        ("mTyreRimTemp", _vec4()),
        ("mTyreInternalAirTemp", _vec4()),
        ("mCrashState", ctypes.c_uint),
        ("mAeroDamage", ctypes.c_float),
        ("mEngineDamage", ctypes.c_float),
        ("mAmbientTemperature", ctypes.c_float),
        ("mTrackTemperature", ctypes.c_float),
        ("mRainDensity", ctypes.c_float),
        ("mWindSpeed", ctypes.c_float),
        ("mWindDirectionX", ctypes.c_float),
        ("mWindDirectionY", ctypes.c_float),
        ("mCloudBrightness", ctypes.c_float),
        ("mSequenceNumber", ctypes.c_uint),
    ]


assert ctypes.sizeof(ParticipantInfo) == 100
assert ParticipantInfo.mWorldPosition.offset == 68
assert ParticipantInfo.mLapsCompleted.offset == 88
assert SharedMemory.mTrackLength.offset == 6704
assert SharedMemory.mLastLapTime.offset == 6720
assert SharedMemory.mSpeed.offset == 6848
assert SharedMemory.mSequenceNumber.offset == 7320


def _text(buf) -> str:
    return bytes(buf).split(b"\0", 1)[0].decode("utf-8", "replace")


@dataclass
class Frame:
    version: int
    game_state: int
    sequence: int
    active: bool
    track: str
    variation: str
    car: str
    track_length: float
    laps_completed: int
    lap_distance: float
    last_lap_time: float
    invalidated: bool
    x: float
    y: float
    z: float
    speed: float


def _frame_from(copy: SharedMemory) -> Frame:
    idx = copy.mViewedParticipantIndex
    active = 0 <= idx < copy.mNumParticipants <= 64
    participant = copy.mParticipantInfo[idx] if active else None
    if participant is not None and not participant.mIsActive:
        active = False
    pos = participant.mWorldPosition if participant is not None else (0.0, 0.0, 0.0)
    return Frame(
        version=copy.mVersion,
        game_state=copy.mGameState,
        sequence=copy.mSequenceNumber,
        active=active,
        track=_text(copy.mTrackLocation),
        variation=_text(copy.mTrackVariation),
        car=_text(copy.mCarName),
        track_length=float(copy.mTrackLength),
        laps_completed=int(participant.mLapsCompleted) if participant is not None else 0,
        lap_distance=float(participant.mCurrentLapDistance) if participant is not None else 0.0,
        last_lap_time=float(copy.mLastLapTime),
        invalidated=bool(copy.mLapInvalidated),
        x=float(pos[0]),
        y=float(pos[1]),
        z=float(pos[2]),
        speed=float(copy.mSpeed),
    )


class SharedMemoryReader:
    def __init__(self):
        self._handle = None
        self._view = None

    def open(self) -> bool:
        self.close()
        handle = _OpenFileMappingW(FILE_MAP_READ, False, MAP_NAME)
        if not handle:
            return False
        view = _MapViewOfFile(handle, FILE_MAP_READ, 0, 0, ctypes.sizeof(SharedMemory))
        if not view:
            _CloseHandle(handle)
            return False
        self._handle = handle
        self._view = view
        return True

    def close(self) -> None:
        if self._view:
            _UnmapViewOfFile(self._view)
            self._view = None
        if self._handle:
            _CloseHandle(self._handle)
            self._handle = None

    def read(self) -> Frame | None:
        """Copy one stable sample; None if the game was mid-write for every attempt"""
        if not self._view:
            return None
        source = ctypes.cast(self._view, ctypes.POINTER(SharedMemory))
        for _ in range(8):
            seq = source.contents.mSequenceNumber
            if seq & 1:
                continue
            copy = SharedMemory()
            ctypes.memmove(ctypes.byref(copy), source, ctypes.sizeof(SharedMemory))
            if copy.mSequenceNumber == seq:
                return _frame_from(copy)
        return None
