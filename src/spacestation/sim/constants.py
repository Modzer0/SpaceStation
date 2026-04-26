"""Physical constants and reference values used across the simulation.

All values are SI unless explicitly noted. Sources are cited inline so that
balancing tweaks remain grounded.
"""
from __future__ import annotations

# --- Universal -----------------------------------------------------------

R_GAS = 8.314_462_618          # J / (mol K) -- ideal gas constant
N_A = 6.022_140_76e23          # Avogadro
G0 = 9.806_65                  # m/s^2 -- standard gravity
SIGMA = 5.670_374_419e-8       # W / (m^2 K^4) -- Stefan-Boltzmann
T0_C = 273.15                  # K at 0 C

# --- Atmosphere reference (Earth sea level) ------------------------------

P_ATM = 101_325.0              # Pa -- 1 atm
T_NORMAL_K = 294.15            # K  -- 21 C, comfortable cabin
RHO_AIR = 1.225                # kg/m^3 at SATP

# Volumetric composition of dry Earth air
AIR_FRAC = {
    "N2":  0.78084,
    "O2":  0.20946,
    "Ar":  0.00934,
    "CO2": 0.000420,           # ~420 ppm (2024 reference)
    # H2O tracked separately as humidity
}

# Molar masses (kg / mol)
M_MOL = {
    "N2":  28.0134e-3,
    "O2":  31.998e-3,
    "Ar":  39.948e-3,
    "CO2": 44.0095e-3,
    "H2O": 18.0153e-3,
    "He":  4.0026e-3,
    "H2":  2.01588e-3,
    "CH4": 16.0425e-3,
    "NH3": 17.0305e-3,
}

# Specific heat at constant volume (J / mol K) -- diatomic ~5/2 R, polyatomic higher
CV_MOLAR = {
    "N2":  20.8,
    "O2":  21.0,
    "Ar":  12.5,
    "CO2": 28.5,
    "H2O": 25.9,   # vapor
    "He":  12.5,
    "H2":  20.4,
}

# --- Physiology ----------------------------------------------------------

# Reference adult: 70 kg, 1.75 m, ~21 C ambient
BODY_MASS_DEFAULT = 70.0       # kg
BODY_HEIGHT_DEFAULT = 1.75     # m
BODY_CORE_TEMP = 310.15        # K (37.0 C)

# Basal metabolic rate of reference adult ~80 W
BMR_W = 80.0
# Light activity ~120 W; severe exertion ~400 W
ACTIVITY_W = {
    "rest":     65.0,
    "idle":     90.0,
    "light":   120.0,
    "moderate": 250.0,
    "heavy":   400.0,
}

# Respiratory quotient (CO2 produced / O2 consumed) for a mixed diet
RQ = 0.85

# O2 consumption: ~3.5 mL O2 / (kg min) STP basal -- "1 MET"
# Normalize to mol/s for a reference person at given W of metabolism.
# 1 W of metabolic heat ≈ 0.21 mL O2 / s STP ≈ 9.4 µmol O2 / s.
O2_PER_J_METABOLIC = 9.4e-6 / 1.0  # mol O2 per J of metabolism

# Water turnover (kg/day)
H2O_INTAKE_DAILY = 2.5         # food + drink
H2O_RESPIRATORY_DAILY = 0.40   # exhaled vapor
H2O_INSENSIBLE_DAILY = 0.50    # skin
H2O_URINE_DAILY = 1.50
H2O_FECAL_DAILY = 0.10

# Food (J/day, ~2000 kcal)
FOOD_DAILY_J = 2000.0 * 4184.0

# CO2 partial-pressure thresholds (Pa) for status effects
CO2_LIMIT_COMFORT  = 1_000.0    # 1 kPa  ~1%   -- noticeable
CO2_LIMIT_HEADACHE = 3_000.0    # 3 kPa  ~3%   -- headache, fatigue
CO2_LIMIT_SEVERE   = 5_000.0    # 5 kPa  ~5%   -- severe symptoms
CO2_LIMIT_INCAP    = 8_000.0    # 8 kPa  ~8%   -- unconsciousness in minutes
CO2_LIMIT_LETHAL   = 12_000.0   # 12 kPa ~12%  -- rapid death

# Ambient O2 partial-pressure thresholds (Pa) -- "is this air breathable?"
O2_NOMINAL          = 21_000.0   # ~21 kPa, normal cabin
O2_LIMIT_HYPOXIA    = 16_000.0   # below here, alveolar O2 starts to fall too low
O2_LIMIT_SEVERE     = 12_000.0
O2_LIMIT_INCAP      = 9_000.0
O2_LIMIT_LETHAL     = 6_000.0

# Alveolar / arterial O2 thresholds (Pa) -- the body's actual blood-gas
# state. Normal sea-level alveolar pO2 is ~13.3 kPa.
PAO2_NORMAL         = 13_300.0
PAO2_HYPOXIA        =  9_000.0   # altitude sickness; impaired performance
PAO2_SEVERE         =  6_500.0
PAO2_INCAP          =  4_000.0
PAO2_LETHAL         =  2_000.0

# Total cabin pressure thresholds (Pa)
P_LIMIT_LOW         = 60_000.0   # ~Denver-equivalent; long-term tolerable
P_LIMIT_HYPOBARIC   = 40_000.0   # acute hypoxia regardless of O2 fraction below this
P_LIMIT_VACUUM      = 6_300.0    # Armstrong limit -- water boils at body temp

# Body thermoregulation
BODY_TEMP_HYPOTHERMIA = 308.15   # 35 C -- mild hypothermia
BODY_TEMP_SEVERE_HYPO = 305.15   # 32 C -- severe
BODY_TEMP_HYPERTHERMIA = 312.15  # 39 C -- mild
BODY_TEMP_SEVERE_HYPER = 314.15  # 41 C -- severe

# --- Radiation -----------------------------------------------------------

# Background dose rates (Sv / s)
BG_EARTH_SURFACE   = 7e-12         # ~0.1 uSv/h -- typical surface
BG_LEO_UNSHIELDED  = 4e-9          # ~15 uSv/h average ISS-like inside-shielded
BG_LEO_EVA         = 3e-8          # ~100 uSv/h on EVA in LEO
BG_SOLAR_FLARE     = 5e-6          # peak SPE event, transient
BG_DEEP_SPACE      = 2e-8          # ~70 uSv/h GCR

# Health thresholds (cumulative effective dose, Sv)
DOSE_ANNUAL_PUBLIC      = 1e-3     # 1 mSv  -- public limit
DOSE_ANNUAL_OCCUPATIONAL= 5e-2     # 50 mSv -- occupational limit
DOSE_ARS_THRESHOLD      = 0.5      # acute radiation syndrome onset
DOSE_ARS_SEVERE         = 2.0
DOSE_LD50_ACUTE         = 4.0      # 4 Sv -- 50% mortality without treatment
DOSE_FATAL              = 8.0

# --- Suit (NASA EMU reference) -------------------------------------------

SUIT_PRESSURE_O2  = 29_600.0       # Pa, ~4.3 psi pure O2
SUIT_VOLUME       = 0.045          # m^3 internal void (~45 L)
SUIT_O2_TANK_KG   = 0.55           # kg O2 (~7-8 h supply)
SUIT_LIOH_KG      = 1.4            # kg lithium hydroxide (~7 h CO2 scrub)
SUIT_BATTERY_J    = 11.0 * 3600.0 * 25.0  # ~1 MJ; 25 W draw for ~11 h
SUIT_PROPELLANT_KG = 5.4           # SAFER-equivalent N2 cold gas
SUIT_THERMAL_W    = 100.0          # sublimator capacity (heat rejection)

# LiOH chemistry: 2 LiOH + CO2 -> Li2CO3 + H2O
# Molar mass LiOH = 0.0239885 kg/mol; reaction is 1:0.5
LIOH_MOL_PER_KG = 1.0 / 0.0239885
LIOH_CO2_PER_MOL = 0.5             # mol CO2 absorbed per mol LiOH

# --- Plants / bioreactor (rough) -----------------------------------------

# 1 m^2 of leafy crop under ~300 W/m^2 PAR fixes ~25 g CO2/day
# = ~568 mmol CO2/day = 6.6 µmol/s. Releases similar mol of O2.
PLANT_CO2_FIX_PER_M2_S = 6.6e-6    # mol/s per m^2 with full lighting

# To support one human (~22 mol O2/day, ~19 mol CO2/day) you need ~33 m^2 of
# salad-crop greenroom -- realistic minimum.

# --- Power ---------------------------------------------------------------

# Lithium cell energy density ~250 Wh/kg
BATTERY_WH_PER_KG = 250.0
# RTG (Pu-238) ~5 W/kg electrical, decay half-life 87.7 yr
RTG_W_PER_KG = 5.0
RTG_HALF_LIFE_S = 87.7 * 365.25 * 86400.0
