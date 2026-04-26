"""Real-time tick-based simulation core.

Every module in this package owns one slice of the world's physics:

    constants.py   -- physical constants and reference values
    units.py       -- unit helpers / pretty-printing
    clock.py       -- simulation time and tick scheduling
    atmosphere.py  -- gas mixtures, ideal-gas pressure, diffusion, leakage
    thermal.py     -- heat capacity, conduction, radiation
    radiation.py   -- ionizing-radiation field and accumulated dose
    body.py        -- player physiology
    suit.py        -- EVA suit life support
    power.py       -- electrical bus and storage
    reactor.py     -- RTG / fission / fusion / Kilopower / MSR scaffolding
    biology.py     -- plants and bioreactors
    computer.py    -- station computer model (CPU/RAM/storage modules)
    world.py       -- compartments, doors, breaches, station layout
    engine.py      -- the tick loop that drives all of the above
"""
