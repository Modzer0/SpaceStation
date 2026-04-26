"""Station computer.

It's a slow 1980s-flavored mainframe with 4 MB of magnetic core memory in the
central word store -- core RAM was chosen because it survives radiation that
would bit-flip DRAM. Expansion modules can be added: extra core, semiconductor
RAM (faster but rad-sensitive), CPU coprocessors, tape/disk/optical storage.

Modeling-wise the computer has a *capability budget* -- a single number that
gates which programs can run. Player upgrades raise this budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ComputerModule:
    name: str
    cpu_mips: float = 0.0
    ram_kb: float = 0.0
    storage_mb: float = 0.0
    rad_resistant: bool = True
    power_w: float = 5.0


@dataclass
class StationComputer:
    """The 4 MB core-memory backbone, with expansion slots."""
    online: bool = True
    modules: List[ComputerModule] = field(default_factory=list)
    program_running: str | None = None
    bit_flips: int = 0
    last_radiation_dose: float = 0.0

    def __post_init__(self) -> None:
        if not self.modules:
            self.modules.append(
                ComputerModule(
                    name="Core CPU",
                    cpu_mips=0.5,
                    ram_kb=4096,         # 4 MB core
                    storage_mb=0.0,
                    rad_resistant=True,
                    power_w=40.0,
                )
            )

    def total_mips(self) -> float:
        return sum(m.cpu_mips for m in self.modules)

    def total_ram_kb(self) -> float:
        return sum(m.ram_kb for m in self.modules)

    def total_storage_mb(self) -> float:
        return sum(m.storage_mb for m in self.modules)

    def total_power_w(self) -> float:
        return sum(m.power_w for m in self.modules) if self.online else 0.0

    def step(self, dose_rate_sv_s: float, dt: float) -> None:
        """Radiation may flip bits in non-rad-resistant modules."""
        # Crude: probability per second of one bit flip per non-resistant module
        # scales with dose rate.
        for m in self.modules:
            if m.rad_resistant:
                continue
            p = dose_rate_sv_s * 1e3 * dt  # 1e3 ~ flips per Sv per kB; tunable
            if p > 0:
                # expected flips this tick
                expected = p * m.ram_kb / 1024.0
                self.bit_flips += int(expected)

    def install(self, module: ComputerModule) -> None:
        self.modules.append(module)
