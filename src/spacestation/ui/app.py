"""Textual app: wrist-computer panel always on the left, station view on the right."""
from __future__ import annotations

import time
from importlib.resources import files

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Header, RichLog, Static

from ..scenario import build
from ..sim.body import Status
from ..sim.constants import (
    CO2_LIMIT_HEADACHE, CO2_LIMIT_SEVERE, O2_LIMIT_HYPOXIA, P_LIMIT_LOW,
)
from ..sim.engine import Engine
from ..sim.units import (
    fmt_clock, fmt_dose, fmt_dose_rate, fmt_duration, fmt_energy_wh,
    fmt_mass, fmt_power_w, fmt_pressure, fmt_temperature_k,
)


# ---------- helpers --------------------------------------------------------


def _color_for_o2(pp: float) -> str:
    if pp < 9_000: return "crit"
    if pp < O2_LIMIT_HYPOXIA: return "warn"
    return "ok"


def _color_for_co2(pp: float) -> str:
    if pp >= CO2_LIMIT_SEVERE: return "crit"
    if pp >= CO2_LIMIT_HEADACHE: return "warn"
    return "ok"


def _color_for_pressure(p: float) -> str:
    if p < 6_300: return "crit"
    if p < P_LIMIT_LOW: return "warn"
    return "ok"


def _color_for_dose_rate(rate: float) -> str:
    # rate is Sv/s
    per_h = rate * 3600.0
    if per_h > 0.01: return "crit"     # > 10 mSv/h
    if per_h > 1e-4: return "warn"    # > 0.1 mSv/h
    return "ok"


def _color_for_dose(d: float) -> str:
    if d > 1.0: return "crit"
    if d > 0.1: return "warn"
    return "ok"


def _bar(value: float, total: float, width: int = 12) -> str:
    if total <= 0:
        return "─" * width
    fill = int(round(value / total * width))
    fill = max(0, min(width, fill))
    return "█" * fill + "░" * (width - fill)


# ---------- widgets --------------------------------------------------------


class WristComputer(Static):
    """The wrist-worn life-support display. Always visible, top-left."""

    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self.engine = engine

    def render(self) -> Text:
        eng = self.engine
        body = eng.body
        suit = eng.suit
        # Atmosphere being breathed
        breath = suit.interior if suit.helmet_sealed else eng.world.player_compartment().gas
        room = eng.world.player_compartment()

        t = Text()
        t.append("WRIST COMPUTER\n", style="bold #5cd5e8")
        t.append(fmt_clock(eng.clock.sim_time_s) + "  ", style="dim")
        t.append(f"x{eng.clock.time_scale:g}\n\n", style="dim")

        # Atmosphere panel
        t.append("─ Atmosphere ─\n", style="#80a0c0")
        p_total = breath.pressure
        p_o2 = breath.partial("O2")
        p_co2 = breath.partial("CO2")
        f_o2 = breath.fraction("O2")
        f_co2 = breath.fraction("CO2")
        t.append("  Press : ")
        t.append(fmt_pressure(p_total) + "\n", style=_pal(_color_for_pressure(p_total)))
        t.append("  O2    : ")
        t.append(f"{fmt_pressure(p_o2)} ({f_o2*100:5.2f}%)\n",
                 style=_pal(_color_for_o2(p_o2)))
        t.append("  CO2   : ")
        t.append(f"{fmt_pressure(p_co2)} ({f_co2*100*10000:5.0f} ppm)\n",
                 style=_pal(_color_for_co2(p_co2)))
        t.append(f"  Temp  : {fmt_temperature_k(breath.temperature)}\n\n", style="dim")

        # Radiation panel
        rate = room.rad.dose_rate()
        t.append("─ Radiation ─\n", style="#80a0c0")
        t.append("  Rate  : ")
        t.append(fmt_dose_rate(rate) + "\n", style=_pal(_color_for_dose_rate(rate)))
        t.append("  Total : ")
        t.append(fmt_dose(body.accumulated_dose_sv) + "\n\n",
                 style=_pal(_color_for_dose(body.accumulated_dose_sv)))

        # Suit panel (only if helmet sealed -- spec said the suit panel is shown when worn)
        if suit.helmet_sealed:
            t.append("─ Suit ─\n", style="#80a0c0")
            o2_frac = suit.o2_tank_kg / 0.55 if 0.55 > 0 else 0
            lioh_frac = suit.lioh_kg / 1.4 if 1.4 > 0 else 0
            bat_frac = suit.battery_j / (11 * 3600 * 25)
            prop_frac = suit.propellant_kg / 5.4
            t.append(f"  O2 tk : [{_bar(suit.o2_tank_kg, 0.55)}] {fmt_mass(suit.o2_tank_kg)}\n",
                     style=_pal("crit" if o2_frac < 0.2 else "warn" if o2_frac < 0.4 else "ok"))
            t.append(f"  LiOH  : [{_bar(suit.lioh_kg, 1.4)}] {fmt_mass(suit.lioh_kg)}\n",
                     style=_pal("crit" if lioh_frac < 0.2 else "warn" if lioh_frac < 0.4 else "ok"))
            t.append(f"  Batt  : [{_bar(suit.battery_j, 11*3600*25)}] {fmt_energy_wh(suit.battery_j)}\n",
                     style=_pal("crit" if bat_frac < 0.2 else "warn" if bat_frac < 0.4 else "ok"))
            t.append(f"  Prop  : [{_bar(suit.propellant_kg, 5.4)}] {fmt_mass(suit.propellant_kg)}\n",
                     style=_pal("crit" if prop_frac < 0.2 else "ok"))
            integ = suit.integrity * 100
            integ_style = "crit" if integ < 70 else "warn" if integ < 95 else "ok"
            t.append(f"  Integ : {integ:5.1f}%\n\n", style=_pal(integ_style))
        else:
            t.append("─ Suit ─\n", style="#80a0c0")
            t.append("  Helmet OPEN\n\n", style="dim")

        # Body panel
        t.append("─ Body ─\n", style="#80a0c0")
        t.append(f"  Core  : {fmt_temperature_k(body.core_temp_k)}\n",
                 style=_pal("crit" if abs(body.core_temp_k - 310.15) > 4 else "ok"))
        t.append(f"  H2O   : {fmt_mass(body.water_kg)}\n", style="dim")
        food_pct = max(0.0, body.food_in_gut_j / 5e6) * 100
        t.append(f"  Food  : ")
        t.append(_bar(body.food_in_gut_j, 5e6) + f" {food_pct:.0f}%\n",
                 style=_pal("warn" if food_pct < 20 else "ok"))
        t.append(f"  Cons. : {body.consciousness*100:.0f}%\n",
                 style=_pal("crit" if body.consciousness < 0.5 else "ok"))

        # Status badges
        if body.status:
            t.append("\nSTATUS:\n", style="#80a0c0")
            for s in body.status:
                color = "crit" if "severe" in s.value or s in (Status.DEAD, Status.UNCONSCIOUS,
                                                                Status.VACUUM_EXPOSURE,
                                                                Status.RAD_LETHAL) else "warn"
                t.append(f"  ! {s.value}\n", style=_pal(color))

        return t


def _pal(name: str) -> str:
    return {
        "crit": "#ff5566 bold",
        "warn": "#ffcc66",
        "ok": "#88dd88",
        "dim": "#607080",
    }[name]


class RoomView(Static):
    def __init__(self, engine: Engine, **kw) -> None:
        super().__init__(**kw)
        self.engine = engine

    def render(self) -> Text:
        eng = self.engine
        room = eng.world.player_compartment()
        t = Text()
        t.append(room.name + "\n", style="bold #b8e0ff")
        t.append(room.description + "\n\n", style="#a0b0c0")

        # Conditions in the room
        gas = room.gas
        line = f"Pressure {fmt_pressure(gas.pressure):>10}   "
        line += f"O2 {fmt_pressure(gas.partial('O2')):>10}   "
        line += f"CO2 {fmt_pressure(gas.partial('CO2')):>10}   "
        line += f"T {fmt_temperature_k(gas.temperature):>8}\n"
        t.append(line, style="dim")

        # Items
        if room.items:
            t.append("\nItems here:\n", style="#80a0c0")
            for it in room.items:
                t.append(f"  • {it.name}", style="white")
                if it.description:
                    t.append(f"  — {it.description}", style="dim")
                t.append("\n")

        # Exits
        t.append("\nExits:\n", style="#80a0c0")
        neighbors = eng.world.neighbors(room.id)
        if not neighbors:
            t.append("  (none)\n", style="dim")
        else:
            for nid, conn in neighbors:
                state = "OPEN" if conn.open else "CLOSED"
                ncomp = eng.world.compartments[nid]
                line = f"  → {ncomp.name} [{state}]"
                if not ncomp.is_pressurized:
                    line += "  ⚠ vacuum"
                t.append(line + "\n", style="white" if conn.open else "dim")

        if not room.is_pressurized:
            t.append("\n*** This compartment is exposed to vacuum. ***\n",
                     style="bold #ff5566")
        elif not room.is_breathable:
            t.append("\n*** This compartment is pressurized but not safely breathable. ***\n",
                     style="bold #ffcc66")
        return t


# ---------- App ------------------------------------------------------------


class SpaceStationApp(App):
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        ("h", "toggle_helmet", "Helmet"),
        ("1", "set_speed(1)", "1x"),
        ("2", "set_speed(10)", "10x"),
        ("3", "set_speed(60)", "60x"),
        ("4", "set_speed(600)", "600x"),
        ("space", "toggle_pause", "Pause"),
        ("g", "go_next_room", "Move →"),
        ("G", "go_prev_room", "Move ←"),
        ("o", "open_close_door", "Open/Close hatch"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.engine = build()
        self._last_real: float = time.monotonic()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Container(id="root"):
            with Vertical(id="left"):
                yield WristComputer(self.engine, id="wrist-frame")
            with Vertical(id="right"):
                yield RoomView(self.engine, id="room-frame")
                yield RichLog(id="log-frame", highlight=False, markup=True, wrap=True, max_lines=200)
        yield Static(
            "[h] helmet  [1-4] speed  [space] pause  [g/G] move  [o] door  [q] quit",
            id="hint",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.title = "SpaceStation — Derelict"
        self.set_interval(0.25, self.tick)
        # Bootstrap log
        log = self.query_one(RichLog)
        for entry in self.engine.log:
            log.write(entry)

    # ------------------------------------------------------------------
    def tick(self) -> None:
        now = time.monotonic()
        dt = now - self._last_real
        self._last_real = now
        ticks_advanced = self.engine.advance(dt)
        # Push any new log entries
        log = self.query_one(RichLog)
        # Show only newly emitted lines
        log_lines = self.engine.log
        existing = log.lines if hasattr(log, "lines") else []
        # Simple strategy: write lines we haven't seen.
        if ticks_advanced > 0:
            # Re-render the visible widgets
            self.query_one(WristComputer).refresh()
            self.query_one(RoomView).refresh()
            # Append any unseen log lines (compare counts)
            seen = getattr(self, "_log_seen", 0)
            new = log_lines[seen:]
            for line in new:
                log.write(line)
            self._log_seen = len(log_lines)

    # ---------- Actions ----------------------------------------------
    def action_toggle_helmet(self) -> None:
        ambient = self.engine.world.player_compartment().gas
        msg = self.engine.suit.toggle_helmet(ambient)
        self.engine.emit(msg)

    def action_set_speed(self, scale: int) -> None:
        self.engine.clock.set_scale(float(scale))
        self.engine.emit(f"Time scale set to x{scale}")

    def action_toggle_pause(self) -> None:
        self.engine.clock.paused = not self.engine.clock.paused
        self.engine.emit("Paused." if self.engine.clock.paused else "Unpaused.")

    def action_go_next_room(self) -> None:
        self._step_along(direction=+1)

    def action_go_prev_room(self) -> None:
        self._step_along(direction=-1)

    def _step_along(self, direction: int) -> None:
        cur = self.engine.world.player_compartment_id
        neighbors = [n for n, conn in self.engine.world.neighbors(cur) if conn.open]
        if not neighbors:
            self.engine.emit("No open hatches.")
            return
        # Pick the first neighbor (or last if direction == -1)
        target = neighbors[0] if direction > 0 else neighbors[-1]
        err = self.engine.world.move_player(target)
        if err:
            self.engine.emit(err)
        else:
            self.engine.emit(f"Moved to {self.engine.world.compartments[target].name}.")

    def action_open_close_door(self) -> None:
        cur = self.engine.world.player_compartment_id
        nbrs = self.engine.world.neighbors(cur)
        if not nbrs:
            self.engine.emit("No hatches here.")
            return
        # Toggle the first hatch
        nid, conn = nbrs[0]
        conn.open = not conn.open
        self.engine.emit(
            f"{'Opened' if conn.open else 'Closed'} hatch to {self.engine.world.compartments[nid].name}."
        )


def run() -> None:
    SpaceStationApp().run()
