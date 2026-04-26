"""Builds the starting scenario.

You wake in the wrecked airlock. Your ship is gone. The habitat module is
sealed but starting to lose pressure through a slow leak. The galley has
food and water. The engineering deck is past a closed hatch and full of
vacuum. The bio lab and the central computer room are further in.

This is intentionally a small starter map -- enough to demonstrate every
subsystem.
"""
from __future__ import annotations

from .sim.atmosphere import GasMix
from .sim.body import Body
from .sim.computer import StationComputer
from .sim.engine import Engine
from .sim.power import Load, PowerBus, Source, Storage
from .sim.radiation import CompartmentRadiation, RadiationSource
from .sim.suit import Suit
from .sim.thermal import ThermalShell
from .sim.world import (
    Compartment, World, lioh_cartridge, o2_bottle,
    radiation_meter, ration_bar, shielding_panel, water_pouch,
)


def _comp(
    cid: str,
    name: str,
    description: str,
    volume: float,
    pressurized: bool,
    bg_rad: float = 4e-9,
    shielding: float = 0.25,
) -> Compartment:
    if pressurized:
        gas = GasMix.standard_air(volume)
    else:
        gas = GasMix.vacuum(volume, temperature=255.0)  # cold
    shell = ThermalShell(
        wall_mass_kg=600.0,
        hull_area_m2=max(20.0, volume * 0.6),
        external_temp_k=3.0,
        solar_flux_w=0.0,
    )
    rad = CompartmentRadiation(background_external=bg_rad, shielding_factor=shielding)
    return Compartment(
        id=cid, name=name, description=description,
        gas=gas, shell=shell, rad=rad,
    )


def build() -> Engine:
    world = World()

    # ---- Compartments -------------------------------------------------
    airlock = _comp(
        "airlock", "Wrecked Airlock",
        "Twisted bulkheads. The outer door is jammed half-open against vacuum.\n"
        "A torn EVA tether floats in the silence.",
        volume=8.0,
        pressurized=False,           # vacuum -- you start in your suit
        bg_rad=2e-8,                 # less shielded due to breach
        shielding=0.5,
    )

    corridor = _comp(
        "corridor", "Central Corridor",
        "A long pressurized passage running spine-wise through the station.\n"
        "Emergency lights flicker. The deck plate vibrates faintly.",
        volume=18.0,
        pressurized=True,
    )

    galley = _comp(
        "galley", "Galley & Stores",
        "Mess and pantry. Sealed ration crates float against the netting.\n"
        "The water reclaimer is offline; manual taps still work.",
        volume=14.0,
        pressurized=True,
    )
    galley.items.extend([
        ration_bar() for _ in range(8)
    ])
    galley.items.extend([
        water_pouch(0.5) for _ in range(6)
    ])
    galley.items.append(radiation_meter())

    habitat = _comp(
        "habitat", "Habitat Module",
        "Crew quarters. Three sleeping bags clipped to the wall, headlamps,\n"
        "personal lockers. A small leak hisses behind a wall panel somewhere.",
        volume=22.0,
        pressurized=True,
    )
    habitat.items.append(shielding_panel())
    habitat.items.append(lioh_cartridge())
    habitat.items.append(o2_bottle())

    eng = _comp(
        "engineering", "Engineering Deck",
        "Power distribution and the auxiliary fission reactor live here.\n"
        "It's vented. Your wrist-computer registers a faint warm spot --\n"
        "an RTG, almost certainly leaking.",
        volume=30.0,
        pressurized=False,
        bg_rad=3e-8,
        shielding=0.4,
    )
    # Add a leaky RTG source the radiation meter will catch.
    leaky = RadiationSource(name="RTG-A", dose_rate=2e-5, distance_m=2.0)  # ~70 mSv/h close-up
    eng.rad.sources.append(leaky)

    biolab = _comp(
        "biolab", "Bio Lab",
        "Petri dishes, gene-print station, mycelium incubator, sealed hood.\n"
        "Maybe enough to engineer something useful, given time and power.",
        volume=12.0,
        pressurized=True,
    )

    computer_room = _comp(
        "computer", "Central Computer Room",
        "A wall of grey steel cabinets with neon labels. The 4 MB core memory\n"
        "stack hums at a peaceful 60 Hz. There are empty expansion slots.",
        volume=10.0,
        pressurized=True,
    )
    computer_room.computer = StationComputer()

    for c in (airlock, corridor, galley, habitat, eng, biolab, computer_room):
        world.add_compartment(c)

    # ---- Connections --------------------------------------------------
    # Airlock -> corridor: the inner door is closed (player must open it)
    world.add_connection("airlock", "corridor", area=0.4, open=False)
    # Corridor branches to other rooms
    world.add_connection("corridor", "galley", area=0.5, open=True)
    world.add_connection("corridor", "habitat", area=0.5, open=True)
    world.add_connection("corridor", "biolab", area=0.5, open=True)
    world.add_connection("corridor", "computer", area=0.5, open=True)
    world.add_connection("corridor", "engineering", area=0.5, open=False)
    # The airlock is breached to space (slow leak through the jammed door)
    world.add_connection("airlock", "VACUUM", area=0.05, open=True)
    # Habitat slow leak
    world.add_connection("habitat", "VACUUM", area=2e-5, open=True)

    # Player starts in the airlock
    world.player_compartment_id = "airlock"

    # ---- Player -------------------------------------------------------
    body = Body()
    suit = Suit()  # sealed by default

    # ---- Power bus stub ----------------------------------------------
    bus = PowerBus()
    bus.storage["main_battery"] = Storage(
        name="Main Battery", capacity_j=10.0 * 3600.0 * 1000.0,  # 10 kWh
        stored_j=2.0 * 3600.0 * 1000.0,
    )
    bus.loads["emergency_lights"] = Load(name="Emergency Lights", power_w=80.0)
    bus.loads["life_support_idle"] = Load(name="Life Support (idle)", power_w=200.0)

    eng_obj = Engine(world=world, body=body, suit=suit, bus=bus)
    eng_obj.emit("Wake up. Your ship is gone. You're alive in your suit. Find oxygen.")
    return eng_obj
