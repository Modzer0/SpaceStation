"""Pretty-printing helpers for SI quantities.

The wrist computer auto-scales between µSv, mSv, Sv etc. -- those rules live
here so the UI never has to do unit math itself.
"""
from __future__ import annotations


def fmt_pressure(pa: float) -> str:
    """Pa -> auto-scaled string. kPa is the typical cabin scale."""
    if pa < 1.0:
        return f"{pa*1000:.1f} mPa"
    if pa < 1_000.0:
        return f"{pa:.0f} Pa"
    if pa < 1_000_000.0:
        return f"{pa/1000:.2f} kPa"
    return f"{pa/1e6:.2f} MPa"


def fmt_temperature_k(k: float) -> str:
    return f"{k - 273.15:+.1f} °C"


def fmt_temperature_c(c: float) -> str:
    return f"{c:+.1f} °C"


def fmt_dose_rate(sv_per_s: float) -> str:
    """Sv/s -> auto-scaled per-hour string (uSv/h, mSv/h, Sv/h)."""
    per_h = sv_per_s * 3600.0
    if per_h < 1e-3:
        return f"{per_h*1e6:.2f} µSv/h"
    if per_h < 1.0:
        return f"{per_h*1e3:.2f} mSv/h"
    return f"{per_h:.3f} Sv/h"


def fmt_dose(sv: float) -> str:
    """Cumulative dose, auto-scaled."""
    a = abs(sv)
    if a < 1e-3:
        return f"{sv*1e6:.1f} µSv"
    if a < 1.0:
        return f"{sv*1e3:.2f} mSv"
    return f"{sv:.3f} Sv"


def fmt_energy_j(j: float) -> str:
    a = abs(j)
    if a < 1e3:
        return f"{j:.0f} J"
    if a < 1e6:
        return f"{j/1e3:.1f} kJ"
    if a < 1e9:
        return f"{j/1e6:.2f} MJ"
    return f"{j/1e9:.2f} GJ"


def fmt_energy_wh(j: float) -> str:
    """Energy as Wh / kWh (battery-friendly)."""
    wh = j / 3600.0
    if abs(wh) < 1.0:
        return f"{wh*1000:.0f} mWh"
    if abs(wh) < 1000.0:
        return f"{wh:.1f} Wh"
    return f"{wh/1000:.2f} kWh"


def fmt_power_w(w: float) -> str:
    a = abs(w)
    if a < 1.0:
        return f"{w*1000:.0f} mW"
    if a < 1000.0:
        return f"{w:.1f} W"
    if a < 1e6:
        return f"{w/1000:.2f} kW"
    return f"{w/1e6:.2f} MW"


def fmt_mass(kg: float) -> str:
    a = abs(kg)
    if a < 1e-3:
        return f"{kg*1e6:.0f} µg"
    if a < 1.0:
        return f"{kg*1e3:.1f} g"
    if a < 1000.0:
        return f"{kg:.2f} kg"
    return f"{kg/1000:.2f} t"


def fmt_volume_m3(m3: float) -> str:
    if m3 < 1e-3:
        return f"{m3*1e6:.0f} mL"
    if m3 < 1.0:
        return f"{m3*1000:.1f} L"
    return f"{m3:.2f} m³"


def fmt_duration(s: float) -> str:
    """Seconds -> human duration."""
    s = max(0.0, s)
    if s < 60:
        return f"{s:.0f}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{int(m):d}m {int(s):02d}s"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{int(h):d}h {int(m):02d}m"
    d, h = divmod(h, 24)
    return f"{int(d):d}d {int(h):02d}h"


def fmt_clock(seconds_since_start: float) -> str:
    """Mission clock: T+DDD HH:MM:SS"""
    s = int(seconds_since_start)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"T+{d:03d} {h:02d}:{m:02d}:{s:02d}"
