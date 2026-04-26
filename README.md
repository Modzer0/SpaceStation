# SpaceStation

A hardcore, real-time space station survival simulator played through the
terminal of a derelict station.

You wake in a form-fitting EVA suit, your ship wrecked against the hull. The
station has air in places, vacuum in others. RTGs are warm but maybe leaking.
There's a fusion reactor in the engineering deck — if you can find enough
capacitance to start it. There's a bio lab. There's a bald computer with 4 MB
of magnetic core memory waiting to be expanded.

## Status

v0.1 — foundation. Real-time simulation engine, ideal-gas atmosphere with
diffusion and breach leakage, full body physiology (respiration, circulation,
hydration, nutrition, thermoregulation, radiation), EVA suit dynamics, and the
wrist computer TUI. One starting compartment (the wrecked airlock) and basic
movement / suit management. Reactors, power grid, biology, station computer,
and EVA are scaffolded as modules awaiting content.

## Run

```bash
pip install -e .
spacestation
```

Python 3.11+. The terminal needs to be at least 100x30 for the UI to render
properly.

## Controls

- `↑/↓/←/→` — move between compartments
- `h` — toggle helmet
- `i` — inventory
- `t` — open station terminal
- `r` — rest / sleep
- `+`/`-` — adjust simulation speed (real-time, 10x, 60x, 600x)
- `q` — quit (no save in v0.1)

## Realism notes

All physiological and atmospheric values are SI and modeled from real numbers:

- Atmosphere is tracked per compartment as moles of O₂, N₂, CO₂, H₂O, Ar.
  Pressure follows PV = nRT.
- Resting metabolism is ~80 W, ~0.25 L·O₂/min STP, RQ ≈ 0.85, ~2 L H₂O/day.
- CO₂ toxicity onset at ~1%, severe at 5%, lethal beyond 8%.
- Hypoxia onset below 16 kPa O₂ partial pressure.
- Radiation tracked in Sv, both dose-rate (per-room) and accumulated body dose.
  Background in unshielded LEO ≈ 0.5 µSv/min; LD50/30 ≈ 4 Sv acute.
- Suit O₂ is 29.6 kPa pure O₂ (NASA EMU spec); LiOH cartridge consumes CO₂.

See `src/spacestation/sim/` for the models.
