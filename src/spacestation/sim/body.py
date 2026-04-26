"""Player physiology.

The body is a state machine of physical reservoirs (water, glycogen, fat,
blood gases, body heat) and accumulators (radiation dose, sleep debt). Every
tick it consumes O2 from whatever atmosphere it's breathing -- either the
suit's helmet space or the surrounding compartment -- and exhales CO2 and
H2O vapor into the same place.

The aim is for everything to "feel right" without being a clinical model.
A player who never sleeps gets impaired. A player at 5% CO2 starts to
suffer. A player in vacuum without a sealed helmet dies in tens of seconds.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from .atmosphere import GasMix
from .constants import (
    ACTIVITY_W, BMR_W, BODY_CORE_TEMP, BODY_MASS_DEFAULT, BODY_HEIGHT_DEFAULT,
    CO2_LIMIT_COMFORT, CO2_LIMIT_HEADACHE, CO2_LIMIT_INCAP, CO2_LIMIT_LETHAL,
    CO2_LIMIT_SEVERE,
    DOSE_ARS_SEVERE, DOSE_ARS_THRESHOLD, DOSE_FATAL, DOSE_LD50_ACUTE,
    FOOD_DAILY_J, H2O_INSENSIBLE_DAILY, H2O_INTAKE_DAILY,
    H2O_RESPIRATORY_DAILY, H2O_URINE_DAILY,
    O2_LIMIT_HYPOXIA,
    O2_PER_J_METABOLIC, PAO2_HYPOXIA, PAO2_INCAP, PAO2_LETHAL, PAO2_SEVERE,
    P_LIMIT_HYPOBARIC, P_LIMIT_VACUUM, RQ,
    BODY_TEMP_HYPERTHERMIA, BODY_TEMP_HYPOTHERMIA,
    BODY_TEMP_SEVERE_HYPER, BODY_TEMP_SEVERE_HYPO,
)


class Activity(str, Enum):
    REST = "rest"
    IDLE = "idle"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"


class Status(str, Enum):
    HYPOXIA          = "hypoxia"
    SEVERE_HYPOXIA   = "severe_hypoxia"
    HYPERCAPNIA      = "hypercapnia"
    SEVERE_HYPERCAPNIA = "severe_hypercapnia"
    HYPOBARIC        = "hypobaric"
    VACUUM_EXPOSURE  = "vacuum_exposure"
    HYPOTHERMIA      = "hypothermia"
    SEVERE_HYPOTHERMIA = "severe_hypothermia"
    HYPERTHERMIA     = "hyperthermia"
    SEVERE_HYPERTHERMIA = "severe_hyperthermia"
    DEHYDRATED       = "dehydrated"
    STARVING         = "starving"
    EXHAUSTED        = "exhausted"
    RAD_NAUSEA       = "rad_nausea"
    RAD_SICK         = "rad_sick"
    RAD_LETHAL       = "rad_lethal"
    UNCONSCIOUS      = "unconscious"
    DEAD             = "dead"


@dataclass
class Body:
    # ---- statics ---------------------------------------------------------
    mass_kg: float = BODY_MASS_DEFAULT
    height_m: float = BODY_HEIGHT_DEFAULT

    # ---- reservoirs (updated each tick) ---------------------------------
    core_temp_k: float = BODY_CORE_TEMP
    water_kg: float = 42.0          # ~60% body mass
    glycogen_j: float = 8.0e6       # ~2000 kcal of stored carbs
    fat_j: float = 5.0e8            # months of fat reserve
    food_in_gut_j: float = 0.0      # buffer between eating and metabolism
    bladder_ml: float = 0.0
    bowel_g: float = 0.0

    # blood gases (partial pressures the alveoli are equilibrating with)
    arterial_o2_pp: float = 13_000.0    # Pa, normal ~13 kPa
    arterial_co2_pp: float =  5_000.0   # Pa, normal ~5 kPa

    # ---- accumulators ----------------------------------------------------
    accumulated_dose_sv: float = 0.0
    sleep_debt_s: float = 0.0
    consciousness: float = 1.0      # 0..1; below 0.3 -> unconscious
    health: float = 1.0             # 0..1; below 0 -> dead
    time_in_vacuum_s: float = 0.0

    # ---- runtime ---------------------------------------------------------
    activity: Activity = Activity.IDLE
    status: List[Status] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)   # transient log lines

    # =====================================================================
    # Per-tick update
    # =====================================================================
    def step(
        self,
        breath_atmosphere: GasMix,
        compartment_temp_k: float,
        dose_rate_sv_s: float,
        dt: float,
        suit_thermal_w: float = 0.0,
    ) -> None:
        """Advance the body by ``dt`` seconds.

        ``breath_atmosphere`` is whatever the lungs are sampling -- if the
        helmet is sealed, that's the suit interior; otherwise it's the
        surrounding compartment air. Either way we read partial pressures
        from it, remove O2 from it, and dump CO2 + H2O back into it.

        ``suit_thermal_w`` is the rate of heat the suit's water-cooling /
        sublimator is moving away from the body (negative = the suit is
        actively heating you, e.g., from a heater pack).
        """
        if Status.DEAD in self.status:
            return

        # ----- metabolism ------------------------------------------------
        activity_w = ACTIVITY_W.get(self.activity.value, BMR_W)
        # Burn fuel: prefer food in gut, then glycogen, then fat
        energy_needed_j = activity_w * dt
        burned = self._burn_fuel(energy_needed_j)
        # If we're starving the body's metabolism stalls; halve activity W.
        if burned < energy_needed_j * 0.5:
            activity_w *= 0.5
            self._add_status(Status.STARVING)
            self.health = max(0.0, self.health - 0.0001 * dt)
        else:
            self._remove_status(Status.STARVING)

        # ----- respiration ----------------------------------------------
        self._respire(breath_atmosphere, activity_w, dt)

        # ----- hydration -------------------------------------------------
        self._hydrate(activity_w, dt)

        # ----- thermoregulation -----------------------------------------
        self._thermoregulate(compartment_temp_k, activity_w, suit_thermal_w, dt)

        # ----- radiation -------------------------------------------------
        self.accumulated_dose_sv += dose_rate_sv_s * dt
        self._update_rad_status()

        # ----- pressure environment effects -----------------------------
        self._check_pressure(breath_atmosphere, dt)

        # ----- consciousness / death gates -------------------------------
        self._update_consciousness(dt)

    # =====================================================================
    # Metabolism / fuel
    # =====================================================================
    def _burn_fuel(self, j: float) -> float:
        """Consume up to j J of metabolic fuel; return joules actually burned."""
        burned = 0.0
        for reservoir in ("food_in_gut_j", "glycogen_j", "fat_j"):
            if j <= 0:
                break
            have = getattr(self, reservoir)
            take = min(have, j)
            setattr(self, reservoir, have - take)
            burned += take
            j -= take
        return burned

    # =====================================================================
    # Respiration
    # =====================================================================
    def _respire(self, atm: GasMix, activity_w: float, dt: float) -> None:
        """Pull O2 out of ``atm``, push CO2 + H2O in.

        We assume the lungs equilibrate alveolar pressure with the atmosphere
        being breathed, modulo gradient. If the atmosphere has insufficient
        O2 partial pressure, arterial O2 drops accordingly and hypoxia
        symptoms set in.
        """
        if atm.total_moles <= 0:
            # Nothing to breathe -- vacuum / suffocation
            self.arterial_o2_pp = max(0.0, self.arterial_o2_pp - 6_000.0 * dt)
            self.arterial_co2_pp = min(15_000.0, self.arterial_co2_pp + 1_000.0 * dt)
            return

        ambient_o2 = atm.partial("O2")
        ambient_co2 = atm.partial("CO2")

        # Alveolar O2 is ambient minus ~7 kPa (water vapor + CO2 saturation).
        # In a normal cabin this gives ~13 kPa, which matches reality.
        alveolar_o2 = max(0.0, ambient_o2 - 7000.0)
        # Lazily move arterial toward alveolar
        tau = 8.0   # s
        a = min(1.0, dt / tau)
        self.arterial_o2_pp = self.arterial_o2_pp * (1 - a) + alveolar_o2 * a
        # Arterial CO2 is set by the balance of metabolic production and
        # ventilation; if ambient CO2 is high enough the body can't dump it.
        target_co2 = max(5_000.0, ambient_co2 + 2_000.0)
        self.arterial_co2_pp = self.arterial_co2_pp * (1 - a) + target_co2 * a

        # Mol of O2 consumed
        o2_mol = O2_PER_J_METABOLIC * activity_w * dt
        # Body cannot extract more than is there
        o2_taken = atm.remove("O2", o2_mol)
        if o2_taken < o2_mol * 0.5:
            self._add_status(Status.SEVERE_HYPOXIA)
        elif self.arterial_o2_pp < PAO2_SEVERE:
            self._add_status(Status.SEVERE_HYPOXIA)
            self._remove_status(Status.HYPOXIA)
        elif self.arterial_o2_pp < PAO2_HYPOXIA:
            self._add_status(Status.HYPOXIA)
            self._remove_status(Status.SEVERE_HYPOXIA)
        else:
            self._remove_status(Status.HYPOXIA)
            self._remove_status(Status.SEVERE_HYPOXIA)
        # CO2 produced
        co2_mol = o2_taken * RQ
        atm.add("CO2", co2_mol)
        # Respiratory water vapor
        h2o_kg_per_s = H2O_RESPIRATORY_DAILY / 86400.0
        atm.add("H2O", (h2o_kg_per_s * dt) / 0.0180153)
        self.water_kg = max(0.0, self.water_kg - h2o_kg_per_s * dt)

        # Hypercapnia statuses
        if ambient_co2 >= CO2_LIMIT_LETHAL:
            self._add_status(Status.SEVERE_HYPERCAPNIA)
            self.consciousness -= 0.3 * dt
        elif ambient_co2 >= CO2_LIMIT_INCAP:
            self._add_status(Status.SEVERE_HYPERCAPNIA)
            self.consciousness -= 0.05 * dt
        elif ambient_co2 >= CO2_LIMIT_SEVERE:
            self._add_status(Status.HYPERCAPNIA)
            self.consciousness -= 0.005 * dt
        elif ambient_co2 >= CO2_LIMIT_HEADACHE:
            self._add_status(Status.HYPERCAPNIA)
        elif ambient_co2 >= CO2_LIMIT_COMFORT:
            self._add_status(Status.HYPERCAPNIA)
        else:
            self._remove_status(Status.HYPERCAPNIA)
            self._remove_status(Status.SEVERE_HYPERCAPNIA)

        # Hypoxia consciousness drain (alveolar/arterial pO2 thresholds)
        if self.arterial_o2_pp < PAO2_LETHAL:
            self.consciousness -= 0.4 * dt
        elif self.arterial_o2_pp < PAO2_INCAP:
            self.consciousness -= 0.08 * dt
        elif self.arterial_o2_pp < PAO2_SEVERE:
            self.consciousness -= 0.01 * dt
        elif self.arterial_o2_pp < PAO2_HYPOXIA:
            self.consciousness -= 0.002 * dt

    # =====================================================================
    # Hydration
    # =====================================================================
    def _hydrate(self, activity_w: float, dt: float) -> None:
        scale = activity_w / BMR_W
        loss_kg = (
            (H2O_RESPIRATORY_DAILY + H2O_INSENSIBLE_DAILY + H2O_URINE_DAILY) / 86400.0
        ) * scale * dt
        self.water_kg = max(0.0, self.water_kg - loss_kg)
        self.bladder_ml += (H2O_URINE_DAILY * 1000.0 / 86400.0) * dt
        # baseline 60% body mass expected; <55% is dehydrated
        if self.water_kg < self.mass_kg * 0.55:
            self._add_status(Status.DEHYDRATED)
            self.health = max(0.0, self.health - 0.00005 * dt)
        else:
            self._remove_status(Status.DEHYDRATED)

    # =====================================================================
    # Thermoregulation
    # =====================================================================
    def _thermoregulate(
        self,
        compartment_temp_k: float,
        activity_w: float,
        suit_thermal_w: float,
        dt: float,
    ) -> None:
        # Heat capacity of body ~3500 J/(kg K)
        cb = self.mass_kg * 3500.0
        # Body produces metabolic heat
        q_in = activity_w
        # Heat lost to environment: roughly 8 W per K differential at rest,
        # less when the suit insulates.
        delta = self.core_temp_k - compartment_temp_k
        env_loss_coef = 8.0
        if Status.VACUUM_EXPOSURE in self.status:
            # In vacuum you radiate (unsuited) -- punishing.
            env_loss_coef = 30.0
        q_out_env = env_loss_coef * delta
        q_out_suit = suit_thermal_w
        net_q = q_in - q_out_env - q_out_suit
        self.core_temp_k += net_q * dt / max(cb, 1.0)

        if self.core_temp_k < BODY_TEMP_SEVERE_HYPO:
            self._add_status(Status.SEVERE_HYPOTHERMIA)
            self.consciousness -= 0.02 * dt
        elif self.core_temp_k < BODY_TEMP_HYPOTHERMIA:
            self._add_status(Status.HYPOTHERMIA)
        elif self.core_temp_k > BODY_TEMP_SEVERE_HYPER:
            self._add_status(Status.SEVERE_HYPERTHERMIA)
            self.consciousness -= 0.02 * dt
        elif self.core_temp_k > BODY_TEMP_HYPERTHERMIA:
            self._add_status(Status.HYPERTHERMIA)
        else:
            for s in (Status.HYPOTHERMIA, Status.SEVERE_HYPOTHERMIA,
                      Status.HYPERTHERMIA, Status.SEVERE_HYPERTHERMIA):
                self._remove_status(s)

    # =====================================================================
    # Pressure
    # =====================================================================
    def _check_pressure(self, atm: GasMix, dt: float) -> None:
        p = atm.pressure
        if p < P_LIMIT_VACUUM:
            self._add_status(Status.VACUUM_EXPOSURE)
            self.time_in_vacuum_s += dt
            # Ebullism + hypoxia -- fatal in seconds-to-tens-of-seconds.
            self.consciousness -= 0.06 * dt
            self.health -= 0.012 * dt
        else:
            self._remove_status(Status.VACUUM_EXPOSURE)
            self.time_in_vacuum_s = 0.0
            # Hypobaric is only a problem when O2 partial pressure is also low
            # (a 30 kPa pure-O2 suit is fine; thin air at 30 kPa is not).
            o2_pp = atm.partial("O2")
            if p < P_LIMIT_HYPOBARIC and o2_pp < O2_LIMIT_HYPOXIA:
                self._add_status(Status.HYPOBARIC)
            else:
                self._remove_status(Status.HYPOBARIC)

    # =====================================================================
    # Radiation health
    # =====================================================================
    def _update_rad_status(self) -> None:
        d = self.accumulated_dose_sv
        if d >= DOSE_FATAL:
            self._add_status(Status.RAD_LETHAL)
            self.health = min(self.health, 0.05)
        elif d >= DOSE_LD50_ACUTE:
            self._add_status(Status.RAD_LETHAL)
            self.health = min(self.health, 0.4)
        elif d >= DOSE_ARS_SEVERE:
            self._add_status(Status.RAD_SICK)
            self.health = min(self.health, 0.7)
        elif d >= DOSE_ARS_THRESHOLD:
            self._add_status(Status.RAD_NAUSEA)

    # =====================================================================
    # Consciousness / death
    # =====================================================================
    def _update_consciousness(self, dt: float) -> None:
        # Slowly recover toward 1.0 if statuses are gone.
        bad = bool({
            Status.SEVERE_HYPOXIA, Status.SEVERE_HYPERCAPNIA,
            Status.SEVERE_HYPOTHERMIA, Status.SEVERE_HYPERTHERMIA,
            Status.VACUUM_EXPOSURE,
        } & set(self.status))
        if not bad:
            self.consciousness = min(1.0, self.consciousness + 0.05 * dt)
        self.consciousness = max(0.0, min(1.0, self.consciousness))
        if self.consciousness <= 0.3:
            self._add_status(Status.UNCONSCIOUS)
        else:
            self._remove_status(Status.UNCONSCIOUS)
        if self.health <= 0.0 or self.consciousness <= 0.0:
            self._add_status(Status.DEAD)

    # =====================================================================
    # Status helpers
    # =====================================================================
    def _add_status(self, s: Status) -> None:
        if s not in self.status:
            self.status.append(s)

    def _remove_status(self, s: Status) -> None:
        if s in self.status:
            self.status.remove(s)

    # =====================================================================
    # Player interactions
    # =====================================================================
    def drink(self, kg: float) -> None:
        self.water_kg = min(self.mass_kg * 0.65, self.water_kg + kg)

    def eat(self, joules: float) -> None:
        self.food_in_gut_j += joules

    def rest(self, dt: float) -> None:
        self.activity = Activity.REST
        self.sleep_debt_s = max(0.0, self.sleep_debt_s - dt)
