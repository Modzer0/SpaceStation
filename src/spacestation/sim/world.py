"""Station layout: compartments, items, doors, breaches.

A ``Compartment`` rolls together everything physical about a single named
volume of the station: its gas mixture, its thermal shell, its radiation
environment, the items lying around in it, and any equipment installed.

The ``World`` is the registry of all compartments + the connections between
them. The engine ticks the world; the UI reads from it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .atmosphere import Connection, GasMix
from .biology import GreenRoom
from .computer import StationComputer
from .radiation import CompartmentRadiation
from .thermal import ThermalShell


# ---------------- Items ----------------------------------------------------


@dataclass
class Item:
    id: str
    name: str
    mass_kg: float = 0.5
    description: str = ""
    properties: Dict[str, float] = field(default_factory=dict)


# Convenience factories
def water_pouch(kg: float = 0.5) -> Item:
    return Item(id="water_pouch", name=f"Water Pouch ({kg:.1f} kg)",
                mass_kg=kg, properties={"water_kg": kg},
                description="Sealed potable-water bladder.")


def ration_bar(j: float = 1.5e6) -> Item:
    return Item(id="ration_bar", name="Emergency Ration Bar",
                mass_kg=0.18, properties={"food_j": j},
                description="Bland, dense, nutritionally complete enough.")


def lioh_cartridge() -> Item:
    return Item(id="lioh_cartridge", name="LiOH CO₂ Cartridge",
                mass_kg=1.5, properties={"lioh_kg": 1.4},
                description="Lithium hydroxide CO₂ scrubber. Single-use.")


def o2_bottle() -> Item:
    return Item(id="o2_bottle", name="High-pressure O₂ Bottle",
                mass_kg=2.0, properties={"o2_kg": 0.55},
                description="Refills suit O₂ tank. Fully charged.")


def radiation_meter() -> Item:
    return Item(id="rad_meter", name="Handheld Radiation Meter",
                mass_kg=0.4, properties={"meter": 1.0},
                description="Reads dose-rate of objects within reach.")


def shielding_panel() -> Item:
    return Item(id="shielding_panel", name="Polyethylene Shielding Panel",
                mass_kg=8.0, properties={"shielding_dr": 0.05},
                description="Boron-loaded HDPE. Install in a compartment to reduce radiation.")


# ---------------- Compartment ---------------------------------------------


@dataclass
class Compartment:
    id: str
    name: str
    description: str
    gas: GasMix
    shell: ThermalShell
    rad: CompartmentRadiation
    items: List[Item] = field(default_factory=list)
    green_rooms: List[GreenRoom] = field(default_factory=list)
    computer: Optional[StationComputer] = None
    occupant_present: bool = False           # set by engine each tick

    @property
    def is_pressurized(self) -> bool:
        from .constants import P_LIMIT_VACUUM
        return self.gas.pressure > P_LIMIT_VACUUM

    @property
    def is_breathable(self) -> bool:
        from .constants import (
            CO2_LIMIT_HEADACHE, O2_LIMIT_HYPOXIA, P_LIMIT_LOW,
        )
        return (
            self.gas.pressure >= P_LIMIT_LOW
            and self.gas.partial("O2") >= O2_LIMIT_HYPOXIA
            and self.gas.partial("CO2") < CO2_LIMIT_HEADACHE
        )


# ---------------- World ---------------------------------------------------


@dataclass
class World:
    compartments: Dict[str, Compartment] = field(default_factory=dict)
    connections: List[Connection] = field(default_factory=list)
    player_compartment_id: str = ""

    # Adjacency precomputed for movement
    _adj: Dict[str, List[Tuple[str, Connection]]] = field(default_factory=dict)

    def add_compartment(self, c: Compartment) -> None:
        self.compartments[c.id] = c
        self._rebuild_adj()

    def add_connection(self, a: str, b: str, area: float, open: bool = True) -> Connection:
        conn = Connection(a=a, b=b, area=area, open=open)
        self.connections.append(conn)
        self._rebuild_adj()
        return conn

    def _rebuild_adj(self) -> None:
        adj: Dict[str, List[Tuple[str, Connection]]] = {cid: [] for cid in self.compartments}
        for c in self.connections:
            if c.a == "VACUUM" or c.b == "VACUUM":
                continue
            adj.setdefault(c.a, []).append((c.b, c))
            adj.setdefault(c.b, []).append((c.a, c))
        self._adj = adj

    def neighbors(self, cid: str) -> List[Tuple[str, Connection]]:
        return self._adj.get(cid, [])

    def player_compartment(self) -> Compartment:
        return self.compartments[self.player_compartment_id]

    def move_player(self, dest_id: str) -> Optional[str]:
        """Try to move the player to an adjacent compartment.
        Returns an error string if blocked, or None on success.
        """
        cur = self.player_compartment_id
        for nid, conn in self.neighbors(cur):
            if nid != dest_id:
                continue
            if not conn.open:
                return "Hatch is closed."
            self.player_compartment_id = dest_id
            return None
        return "No connection to that compartment."
