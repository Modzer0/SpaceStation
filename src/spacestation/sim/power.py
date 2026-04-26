"""Electrical bus model.

The station is one nominal DC bus. Sources push energy onto it each tick;
loads consume energy. Whatever's left over charges the storage banks.
A brownout occurs when demand exceeds supply + draw rate.

This is a simple "energy in, energy out, store the rest" model -- not a
load-flow analysis -- which is enough for survival gameplay. Reactors and
solar panels register themselves as ``Source`` entries, batteries as
``Storage``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List


@dataclass
class Source:
    name: str
    power_w: float = 0.0          # current output, recomputed each tick
    online: bool = False
    update: Callable[["Source", float], None] | None = None  # custom updater


@dataclass
class Storage:
    name: str
    capacity_j: float
    stored_j: float
    charge_w_max: float = 5_000.0
    discharge_w_max: float = 5_000.0

    @property
    def fraction(self) -> float:
        return 0.0 if self.capacity_j <= 0 else self.stored_j / self.capacity_j


@dataclass
class Load:
    name: str
    power_w: float
    enabled: bool = True


@dataclass
class PowerBus:
    sources: Dict[str, Source] = field(default_factory=dict)
    storage: Dict[str, Storage] = field(default_factory=dict)
    loads: Dict[str, Load] = field(default_factory=dict)
    last_supply_w: float = 0.0
    last_demand_w: float = 0.0
    last_unmet_w: float = 0.0
    voltage_ok: bool = True

    def step(self, dt: float) -> None:
        # 1) update each source
        supply = 0.0
        for s in self.sources.values():
            if s.update is not None:
                s.update(s, dt)
            if s.online:
                supply += s.power_w
        # 2) compute demand
        demand = sum(l.power_w for l in self.loads.values() if l.enabled)
        delta = supply - demand
        net_j = delta * dt
        # 3) charge or discharge storage
        if net_j >= 0:
            # charge
            remaining = net_j
            for st in self.storage.values():
                room = st.capacity_j - st.stored_j
                take = min(room, remaining, st.charge_w_max * dt)
                st.stored_j += take
                remaining -= take
                if remaining <= 0:
                    break
            unmet = 0.0
        else:
            # discharge
            need = -net_j
            for st in self.storage.values():
                give = min(st.stored_j, need, st.discharge_w_max * dt)
                st.stored_j -= give
                need -= give
                if need <= 0:
                    break
            unmet = max(0.0, need)
        self.last_supply_w = supply
        self.last_demand_w = demand
        self.last_unmet_w = unmet / dt if dt > 0 else 0.0
        self.voltage_ok = unmet <= 0.0

    def total_stored_j(self) -> float:
        return sum(s.stored_j for s in self.storage.values())

    def total_capacity_j(self) -> float:
        return sum(s.capacity_j for s in self.storage.values())
