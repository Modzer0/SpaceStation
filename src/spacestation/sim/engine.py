"""The simulation tick loop.

``Engine`` owns the world, the player's body and suit, and the clock. The
Textual app calls ``engine.advance(real_dt)`` on every render; the engine
consumes whole physics ticks out of the clock's accumulator and updates
each subsystem in a fixed, dependency-ordered sequence:

    1. Power: sources update, loads draw, storage charges/drains.
    2. Atmospheres: per-compartment chemistry/heat sources, then diffusion,
       then breach leakage.
    3. Thermal: walls + bulkheads.
    4. Radiation: source decay.
    5. Suit: regulator, scrubber, battery.
    6. Body: respiration, hydration, thermo, dose, statuses.

The engine never blocks on UI work and is safe to advance with a tiny dt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .atmosphere import GasMix, step_atmospheres
from .body import Body, Status
from .clock import Clock
from .power import PowerBus
from .radiation import step_radiation
from .suit import Suit
from .thermal import step_bulkheads, step_thermal
from .world import World


@dataclass
class Engine:
    world: World
    body: Body
    suit: Suit
    bus: PowerBus = field(default_factory=PowerBus)
    clock: Clock = field(default_factory=Clock)
    log: List[str] = field(default_factory=list)
    log_max: int = 200

    # ------------------------------------------------------------------
    # Public API used by the UI
    # ------------------------------------------------------------------
    def advance(self, real_dt: float) -> int:
        ticks = self.clock.step(real_dt)
        for _ in range(ticks):
            self._tick(self.clock.physics_dt)
        return ticks

    def emit(self, msg: str) -> None:
        self.log.append(f"[T+{int(self.clock.sim_time_s):d}] {msg}")
        if len(self.log) > self.log_max:
            del self.log[: -self.log_max]

    # ------------------------------------------------------------------
    # Internal step
    # ------------------------------------------------------------------
    def _tick(self, dt: float) -> None:
        # ----- 1. power ----------------------------------------------------
        self.bus.step(dt)

        # ----- 2. atmospheres ---------------------------------------------
        # Mark the player's compartment occupant for body heat coupling.
        for cid, comp in self.world.compartments.items():
            comp.occupant_present = (cid == self.world.player_compartment_id)

        # Plant photosynthesis writes to the room's gas mix
        for comp in self.world.compartments.values():
            for gr in comp.green_rooms:
                gr.step(comp.gas, dt)

        # Bulk diffusion + breach venting between compartments
        step_atmospheres(
            {cid: c.gas for cid, c in self.world.compartments.items()},
            self.world.connections,
            dt,
        )

        # ----- 3. thermal -------------------------------------------------
        for cid, comp in self.world.compartments.items():
            occupant_w = 100.0 if comp.occupant_present else 0.0
            equipment_w = 0.0  # extended later with reactors/heaters
            step_thermal(comp.gas, comp.shell, occupant_w, equipment_w, dt)

        step_bulkheads(
            {cid: c.shell for cid, c in self.world.compartments.items()},
            self.world.connections,
            dt,
        )

        # ----- 4. radiation -----------------------------------------------
        step_radiation(
            {cid: c.rad for cid, c in self.world.compartments.items()},
            dt,
        )

        # ----- 5. suit ----------------------------------------------------
        ambient = self.world.player_compartment().gas
        self.suit.step(ambient, dt)

        # ----- 6. body ----------------------------------------------------
        # Body breathes whichever atmosphere matches helmet state.
        breath = self.suit.interior if self.suit.helmet_sealed else ambient
        room = self.world.player_compartment()
        dose_rate = room.rad.dose_rate()
        # When the suit is sealed it isolates the body from the room and
        # holds the wearer at a comfortable temperature -- effective
        # ambient temp is the suit interior, not the cold (or hot) room.
        # When the suit is open, the body is exchanging directly with the
        # room atmosphere.
        if self.suit.helmet_sealed:
            effective_temp = 294.15   # 21 C, regulated by suit's MTL/sublimator
        else:
            effective_temp = room.gas.temperature
        self.body.step(
            breath_atmosphere=breath,
            compartment_temp_k=effective_temp,
            dose_rate_sv_s=dose_rate,
            dt=dt,
            suit_thermal_w=0.0,
        )

        # ----- 7. computer (in player room only for now) -------------------
        if room.computer is not None:
            room.computer.step(dose_rate, dt)

        # ----- 8. emit critical events ------------------------------------
        if Status.DEAD in self.body.status and "death_logged" not in self._flags():
            self.emit("Vital signs flat. End of mission.")
            self._flags().add("death_logged")
        elif Status.SEVERE_HYPOXIA in self.body.status and "hypoxia_logged" not in self._flags():
            self.emit("Severe hypoxia detected. Find oxygen NOW.")
            self._flags().add("hypoxia_logged")

    def _flags(self) -> set:
        if not hasattr(self, "_flag_set"):
            self._flag_set: set = set()
        return self._flag_set
