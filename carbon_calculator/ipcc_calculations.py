"""
IPCC-compliant emission calculation utilities for the carbon calculator.
All formulas follow the IPCC 2019 Refinement Tier 1 methodology unless otherwise
stated. Values and emission factors are adapted for general use but may be
more specific to Sub-Saharan Africa where defaults were available.
Units are kilogram CO₂ equivalent (kg CO₂e) unless explicitly noted.
"""
from __future__ import annotations

from typing import Any, Dict


def _calculate_soil_moisture_factor(soil_data: Dict[str, Any]) -> float:
    """
    Calculates a soil moisture factor to adjust decomposition rates.

    The factor is based on a quadratic function that peaks at an optimal
    soil moisture level, reflecting ideal conditions for microbial activity.
    It returns a value between 0 and 1.
    """
    # Use the average of the top two soil layers, as they are most relevant for microbial activity.
    sm1 = soil_data.get("soil_moisture_0_to_7cm")
    sm2 = soil_data.get("soil_moisture_7_to_28cm")

    if sm1 is None or sm2 is None:
        # If data is missing, return a neutral factor, assuming average conditions.
        return 1.0

    avg_sm = (sm1 + sm2) / 2.0

    # Optimal volumetric soil moisture for decomposition (m^3/m^3).
    # This is an empirical value based on literature, where activity peaks.
    sm_opt = 0.30

    # Width of the quadratic function, controlling its sensitivity.
    # The factor becomes 0 when moisture is `sm_width` away from `sm_opt`.
    sm_width = 0.25

    # Quadratic function: factor = 1 - ((x - opt) / width)^2
    # This creates a curve peaking at 1.0 when avg_sm == sm_opt.
    factor = 1 - ((avg_sm - sm_opt) / sm_width) ** 2

    # Clamp the factor between 0 and 1, as extreme moisture (too dry or too wet)
    # should inhibit, not reverse, decomposition.
    return max(0.0, min(1.0, factor))


# ---------------------------------------------------------------------------
# 1. Fuel / Machinery emissions (Scope 1 – mobile combustion)
# ---------------------------------------------------------------------------
# kg CO₂ produced per litre of diesel (IPCC default, converted to L)
DIESEL_EMISSION_FACTOR: float = 2.68  # kg CO₂/L


def calculate_fuel_emissions(farm_data: Dict[str, Any]) -> float:
    """Return annual CO₂e emitted by on-farm diesel use."""
    # Handle both legacy ('fuel_consumption') and new ('fuel_usage') keys.
    fuel_liters_per_month = farm_data.get("fuel_usage") or farm_data.get("fuel_consumption", 0.0)
    annual_fuel = fuel_liters_per_month * 12.0
    return annual_fuel * DIESEL_EMISSION_FACTOR


# ---------------------------------------------------------------------------
# 2. Fertiliser-induced N₂O emissions (Scope 1 – managed soils)
# ---------------------------------------------------------------------------
EF1_DIRECT = 0.01  # kg N₂O-N / kg N applied (synthetic N)
EF1_ORGANIC = 0.0075  # kg N₂O-N / kg N applied (organic sources)
N_TO_N2O = 44.0 / 28.0  # Convert N₂O-N ➜ N₂O mass
N2O_GWP100 = 298  # IPCC AR6 100-year GWP


def calculate_fertilizer_emissions(farm_data: Dict[str, Any]) -> float:
    """Return annual N₂O emissions (as CO₂e) from N fertiliser application."""
    fertilizer_type = farm_data.get("fertilizer_type", "none")
    if fertilizer_type == "none":
        return 0.0

    farm_size = farm_data.get("farm_size", 0.0)
    # Handle both legacy ('fertilizer_amount') and new ('fertilizer_rate') keys.
    fertilizer_rate = farm_data.get("fertilizer_rate") or farm_data.get("fertilizer_amount", 0.0)
    total_n = fertilizer_rate * farm_size

    if fertilizer_type == "organic":
        ef = EF1_ORGANIC
    elif fertilizer_type == "both":
        ef = (EF1_DIRECT + EF1_ORGANIC) / 2.0
    else:  # synthetic
        ef = EF1_DIRECT

    n2o_n = total_n * ef
    n2o = n2o_n * N_TO_N2O
    return n2o * N2O_GWP100


# ---------------------------------------------------------------------------
# 3. Livestock CH₄ emissions (Scope 1 – enteric & manure)
# ---------------------------------------------------------------------------
CH4_GWP100 = 25  # kg CO₂e / kg CH₄ (AR6 no-feedback)

ENTERIC_EF = {
    "cattle": 53.0, "goats": 5.0, "sheep": 8.0,
    "pigs": 1.5, "poultry": 0.0, "rabbits": 0.0,
}

MANURE_EF = {
    "cattle": 1.0, "goats": 0.17, "sheep": 0.28,
    "pigs": 3.0, "poultry": 0.39, "rabbits": 0.1,
}


def calculate_livestock_emissions(farm_data: Dict[str, Any]) -> Dict[str, float]:
    """Return CH₄-related emissions for livestock."""
    livestock_counts = farm_data.get("livestock_counts", {})
    total_enteric = 0.0
    total_manure = 0.0

    for animal, count in livestock_counts.items():
        total_enteric += ENTERIC_EF.get(animal, 0.0) * count
        total_manure += MANURE_EF.get(animal, 0.0) * count

    enteric_co2e = total_enteric * CH4_GWP100
    manure_co2e = total_manure * CH4_GWP100
    return {
        "enteric": enteric_co2e,
        "manure": manure_co2e,
        "total": enteric_co2e + manure_co2e,
    }


# ---------------------------------------------------------------------------
# 4. Soil organic carbon (SOC) stock change (Scope 3 – land use)
# ---------------------------------------------------------------------------

# Crop-specific SOC factors based on IPCC guidelines for Sub-Saharan Africa
CROP_SOC_FACTORS = {
    "cereals": 1.0,        # Baseline (maize, rice, wheat, sorghum, millet)
    "legumes": 0.85,       # Better SOC due to nitrogen fixation
    "tubers": 1.1,         # Higher soil disturbance
    "root_crops": 1.05,    # Moderate soil disturbance
    "vegetables": 1.15,     # High input, frequent tillage
    "fruits": 0.7,         # Perennial, good SOC accumulation
    "cash_crops": 0.9,     # Variable (cocoa, coffee better; cotton worse)
    "pasture": 0.6,        # Excellent SOC accumulation
}

def calculate_crop_weighted_soc_factor(crop_classes: list) -> float:
    """
    Calculate weighted SOC factor based on multiple crop classes.
    Assumes equal area allocation across all selected crops.
    """
    if not crop_classes:
        return 1.0  # Default to cereals baseline
    
    total_factor = sum(CROP_SOC_FACTORS.get(crop, 1.0) for crop in crop_classes)
    return total_factor / len(crop_classes)

def calculate_soil_carbon_stock_change(
    farm_data: Dict[str, Any], climate_zone: str, moisture_factor: float
) -> Dict[str, float]:
    """
    Estimates the change in soil organic carbon (SOC) and related N2O emissions.
    Uses a simplified model based on farming practice, crop types, and climate, 
    adjusted by a real-time soil moisture factor.
    """
    farming_practice = farm_data.get("farming_practice", "conventional")
    crop_classes = farm_data.get("crop_classes", ["cereals"])  # Handle both old and new format
    
    # Handle legacy single crop_class field
    if "crop_class" in farm_data and not crop_classes:
        crop_classes = [farm_data["crop_class"]]

    # Baseline SOC change (t C/ha/yr) - simplified.
    # Negative values indicate sequestration, positive values indicate loss.
    baseline_soc_change = -0.5  # Assume a baseline sequestration rate

    farming_practice_factors = {
        "conventional": 1.0,
        "organic": 0.8,
        "permaculture": 0.5,
        "agroforestry": 0.4,
        "mixed": 0.9,
        "conservation": 0.7,  # Added conservation agriculture
    }
    farming_practice_factor = farming_practice_factors.get(farming_practice, 1.0)
    
    # Calculate crop-weighted SOC factor
    crop_factor = calculate_crop_weighted_soc_factor(crop_classes)

    climate_factors = {
        "temperate_moist": 1.0, "temperate_dry": 1.2,
        "tropical_moist": 0.9, "tropical_dry": 1.1,
        "cold_moist": 1.1, "cold_dry": 1.3,
    }
    climate_factor = climate_factors.get(climate_zone, 1.0)

    # Calculate SOC change, adjusted by practices, crops, climate, and moisture
    soc_change = (
        baseline_soc_change
        * farming_practice_factor
        * crop_factor  # New: crop-specific factor
        * climate_factor
        * moisture_factor  # Adjust based on current soil moisture
    )

    # Placeholder for N2O from SOC change. Assumes 1% of C loss is emitted as N2O-N.
    n2o_from_soil = (soc_change * -1) * 0.01 * N_TO_N2O * N2O_GWP100 if soc_change > 0 else 0

    return {
        "soc_change_co2e_per_ha": soc_change * (44 / 12),
        "n2o_from_soc_co2e_per_ha": n2o_from_soil,
    }


# ---------------------------------------------------------------------------
# 5. Total emissions aggregator & helpers
# ---------------------------------------------------------------------------

def determine_climate_zone(mean_annual_temp: float, annual_precip: float) -> str:
    """Classify climate zone based on annual temperature and precipitation."""
    # If weather data is missing, default to temperate conditions to avoid errors.
    if mean_annual_temp is None:
        mean_annual_temp = 15  # Default to a temperate value (in Celsius)

    if annual_precip is None:
        annual_precip = 1000 if mean_annual_temp > 10 else 500

    if mean_annual_temp > 18:
        return "tropical_moist" if annual_precip > 1500 else "tropical_dry"
    elif 10 <= mean_annual_temp <= 18:
        return "temperate_moist" if annual_precip > 1000 else "temperate_dry"
    else: # mean_annual_temp < 10
        return "cold_moist" if annual_precip > 600 else "cold_dry"


def calculate_total_emissions(
    farm_data: Dict[str, Any], weather_data: Dict[str, Any], soil_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Return breakdown & totals combining all sub-calculations."""
    farm_size = farm_data.get("farm_size", 0.0)

    # Determine climate zone for factors
    climate_zone = determine_climate_zone(
        mean_annual_temp=weather_data.get("mean_annual_temp"),
        annual_precip=weather_data.get("annual_precip"),
    )

    # Calculate soil moisture factor
    moisture_factor = _calculate_soil_moisture_factor(soil_data)

    # --- Individual Emission Sources ---
    fuel_total = calculate_fuel_emissions(farm_data) if farm_data.get("uses_machinery") else 0.0
    fertilizer_total = calculate_fertilizer_emissions(farm_data)
    livestock_totals = calculate_livestock_emissions(farm_data) if farm_data.get("keeps_livestock") else {"enteric": 0, "manure": 0, "total": 0}
    
    soil_change_totals_per_ha = calculate_soil_carbon_stock_change(
        farm_data, climate_zone, moisture_factor
    )
    soc_change_total = soil_change_totals_per_ha["soc_change_co2e_per_ha"] * farm_size
    n2o_from_soc_total = soil_change_totals_per_ha["n2o_from_soc_co2e_per_ha"] * farm_size

    # --- Aggregation ---
    emissions_sources = {
        "Fuel Combustion": fuel_total,
        "Fertilizer Application": fertilizer_total,
        "Livestock (Enteric Fermentation)": livestock_totals["enteric"],
        "Livestock (Manure Management)": livestock_totals["manure"],
        "N2O from SOC Change": n2o_from_soc_total,
    }

    total_emissions = sum(emissions_sources.values())
    net_emissions = total_emissions + soc_change_total

    return {
        "emissions_sources": emissions_sources,
        "soil_carbon_sequestration": soc_change_total, # Negative is sequestration
        "total_emissions": total_emissions,
        "net_emissions": net_emissions, # Emissions - Sequestration
        "raw_soil_data": soil_data,
        "raw_weather_data": weather_data,
        "climate_zone": climate_zone,
        "soil_moisture_factor": moisture_factor,
    } 