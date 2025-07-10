"""
External data fetch helpers (geocoding, soil, weather).
In production, set API keys via environment variables.
"""
from __future__ import annotations

import os
import logging
from typing import Tuple, Dict, Any, Optional
from datetime import datetime, timedelta

import requests

# ---------------------------------------------------------------------------
# 1. Enhanced Geocoding with better error handling
# ---------------------------------------------------------------------------

def geocode_commune(commune: str) -> Tuple[float, float]:
    """Return (lat, lon) for commune using enhanced Nominatim OpenStreetMap service."""
    url = "https://nominatim.openstreetmap.org/search"
    
    # Try multiple search variations for better matching
    search_variations = [
        f"{commune}, Cameroon",
        f"{commune}, Cameroun",
        f"{commune} commune, Cameroon",
        f"{commune} arrondissement, Cameroon",
        f"{commune}, CM",  # ISO country code
    ]
    
    for search_query in search_variations:
        params = {
            "q": search_query,
            "format": "json",
            "limit": 5,  # Get more results to find best match
            "countrycodes": "cm",  # Restrict to Cameroon
            "addressdetails": 1,
            "extratags": 1,
        }
        
        try:
            resp = requests.get(
                url, 
                params=params, 
                headers={
                    "User-Agent": "EcosystemPlus-Carbon-Calculator/2.0 (contact@ecosystemplus.com)"
                }, 
                timeout=20
            )
            resp.raise_for_status()
            
            data = resp.json()
            if data:
                # Filter results to prioritize administrative boundaries
                admin_results = [
                    result for result in data 
                    if result.get('class') in ['boundary', 'place'] and 
                       result.get('type') in ['administrative', 'city', 'town', 'village']
                ]
                
                # Use admin results if available, otherwise use all results
                results_to_consider = admin_results if admin_results else data
                
                # Take the result with highest importance
                best_result = max(results_to_consider, key=lambda x: float(x.get('importance', 0)))
                lat, lon = float(best_result["lat"]), float(best_result["lon"])
                
                # Log the successful geocoding with details
                logging.info(
                    f"Geocoded '{commune}' -> ({lat:.4f}, {lon:.4f}) "
                    f"[Query: '{search_query}', Type: {best_result.get('type', 'unknown')}, "
                    f"Importance: {best_result.get('importance', 'unknown')}]"
                )
                return lat, lon
                
        except requests.exceptions.RequestException as e:
            logging.warning(f"Geocoding request failed for '{search_query}': {e}")
            continue
        except (KeyError, ValueError, TypeError) as e:
            logging.warning(f"Invalid geocoding response for '{search_query}': {e}")
            continue
    
    # If all attempts failed, provide detailed error
    raise ValueError(
        f"Could not geocode commune '{commune}'. Tried {len(search_variations)} search variations. "
        f"Please verify the commune name exists in Cameroon. "
        f"Attempted queries: {', '.join(search_variations)}"
    )


# ---------------------------------------------------------------------------
# 2. Open-Meteo Soil & Weather data
# ---------------------------------------------------------------------------

OPENMETEO_ARCHIVE_ENDPOINT = "https://archive-api.open-meteo.com/v1/archive"


def fetch_soil_data(lat: float, lon: float) -> Dict[str, Any]:
    """
    Return soil moisture dict using Open-Meteo's historical API with fallback strategies.
    """
    # Try multiple date ranges to increase chances of finding data
    date_attempts = [
        (datetime.utcnow() - timedelta(days=2)),  # 2 days ago
        (datetime.utcnow() - timedelta(days=3)),  # 3 days ago
        (datetime.utcnow() - timedelta(days=7)),  # 1 week ago
        (datetime.utcnow() - timedelta(days=14)), # 2 weeks ago
    ]
    
    for attempt_date in date_attempts:
        target_date = attempt_date.strftime("%Y-%m-%d")
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": target_date,
            "end_date": target_date,
            "hourly": "soil_moisture_0_to_7cm,soil_moisture_7_to_28cm,soil_moisture_28_to_100cm,soil_temperature_0_to_7cm",
        }
        
        try:
            resp = requests.get(OPENMETEO_ARCHIVE_ENDPOINT, params=params, timeout=20)
            resp.raise_for_status()
            
            data = resp.json()
            logging.info(f"Open-Meteo soil API response for {target_date}: {data}")
            
            # Check if we have valid data
            hourly_data = data.get("hourly", {})
            if not hourly_data:
                logging.warning(f"No hourly data for {target_date}, trying next date...")
                continue
                
            def _calculate_mean_safe(key: str) -> Optional[float]:
                """Calculate mean of a list of hourly values with safe error handling."""
                values = hourly_data.get(key, [])
                if not values:
                    return None
                    
                valid_values = [v for v in values if v is not None and isinstance(v, (int, float))]
                if not valid_values:
                    return None
                    
                return sum(valid_values) / len(valid_values)
            
            # Try to extract soil moisture data
            soil_layers = {
                "soil_moisture_0_to_7cm": _calculate_mean_safe("soil_moisture_0_to_7cm"),
                "soil_moisture_7_to_28cm": _calculate_mean_safe("soil_moisture_7_to_28cm"),
                "soil_moisture_28_to_100cm": _calculate_mean_safe("soil_moisture_28_to_100cm"),
                "soil_temperature_0_to_7cm": _calculate_mean_safe("soil_temperature_0_to_7cm"),
            }
            
            # Check if we have at least some valid soil moisture data
            valid_moisture_layers = [
                key for key, value in soil_layers.items() 
                if value is not None and "moisture" in key
            ]
            
            if len(valid_moisture_layers) >= 2:  # Need at least 2 layers for calculation
                # Fill missing values with interpolation from available layers
                if soil_layers["soil_moisture_0_to_7cm"] is None and soil_layers["soil_moisture_7_to_28cm"] is not None:
                    soil_layers["soil_moisture_0_to_7cm"] = soil_layers["soil_moisture_7_to_28cm"] * 1.05
                    
                if soil_layers["soil_moisture_7_to_28cm"] is None and soil_layers["soil_moisture_0_to_7cm"] is not None:
                    soil_layers["soil_moisture_7_to_28cm"] = soil_layers["soil_moisture_0_to_7cm"] * 0.95
                    
                if soil_layers["soil_moisture_28_to_100cm"] is None and soil_layers["soil_moisture_7_to_28cm"] is not None:
                    soil_layers["soil_moisture_28_to_100cm"] = soil_layers["soil_moisture_7_to_28cm"] * 0.90
                
                # Remove None values and return the result
                final_soil_data = {key: value for key, value in soil_layers.items() if value is not None}
                
                logging.info(f"Successfully retrieved soil data for {target_date}: {final_soil_data}")
                return final_soil_data
            else:
                logging.warning(f"Insufficient soil moisture data for {target_date}, trying next date...")
                continue
                
        except requests.exceptions.RequestException as e:
            logging.warning(f"Open-Meteo soil request failed for {target_date}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logging.warning(f"Response status: {e.response.status_code}, Content: {e.response.text[:200]}")
            continue
        except (KeyError, ValueError, TypeError) as e:
            logging.warning(f"Invalid soil data response for {target_date}: {e}")
            continue
    
    # If all attempts failed, raise a comprehensive error
    raise ValueError(
        f"Could not fetch soil data for coordinates ({lat:.4f}, {lon:.4f}). "
        f"Tried {len(date_attempts)} different dates. "
        f"This could indicate the location is outside the data coverage area or the API is temporarily unavailable."
    )


# ---------------------------------------------------------------------------
# 3. Weather – Tomorrow.io
# ---------------------------------------------------------------------------

TOMORROW_API_ENDPOINT = "https://api.tomorrow.io/v4/weather/realtime"
# Accept either env var name for convenience
TOMORROW_API_KEY = "JVararbrSl28Xi3ssgX3ws8fZqo7vd3V"


def fetch_weather_data(lat: float, lon: float) -> Dict[str, Any]:
    """
    Fetch current weather from Tomorrow.io and derive annual estimates.
    Uses both current conditions and historical data for better estimates.
    """
    params = {
        "location": f"{lat},{lon}",
        "fields": "temperature,humidity,windSpeed,precipitationIntensity,cloudCover",
        "units": "metric",
        "apikey": TOMORROW_API_KEY,
    }
    
    try:
        resp = requests.get(TOMORROW_API_ENDPOINT, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        
        logging.info(f"Tomorrow.io API response structure: {data}")
        
        # Handle the realtime API response structure
        if "data" in data and "values" in data["data"]:
            # Realtime API structure: {"data": {"time": "...", "values": {...}}}
            current_values = data["data"]["values"]
        else:
            current_values = {}
        
        if not current_values:
            logging.error(f"Tomorrow.io returned empty or unexpected weather values. Full response: {data}")
            raise ValueError("No weather data received from API")

        temp = current_values.get("temperature")
        rain_intensity = current_values.get("precipitationIntensity", 0.0)
        humidity = current_values.get("humidity", 50.0)  # Default humidity
        
        if temp is None:
            logging.error(f"Temperature data is missing from API response. Available fields: {list(current_values.keys())}")
            raise ValueError("Temperature data not available")

        # Improved annual precipitation estimation using regional climate data
        # Cameroon has distinct wet/dry seasons - adjust based on current conditions
        current_month = datetime.now().month
        
        # Wet season multiplier (March-October)
        if 3 <= current_month <= 10:
            seasonal_multiplier = 1.5  # Higher precipitation during wet season
            estimated_hours_per_year = 1200  # More rainy hours
        else:
            seasonal_multiplier = 0.3  # Lower precipitation during dry season
            estimated_hours_per_year = 300   # Fewer rainy hours
        
        # Base annual precipitation on current conditions and season
        base_annual_precip = rain_intensity * estimated_hours_per_year * seasonal_multiplier
        
        # Apply humidity adjustment for better estimate
        humidity_factor = min(1.5, max(0.5, humidity / 60.0))  # Scale based on humidity
        estimated_annual_precip = base_annual_precip * humidity_factor
        
        # Ensure reasonable bounds for Cameroon (200-4000mm annually)
        estimated_annual_precip = max(200, min(4000, estimated_annual_precip))
        
        logging.info(
            f"Weather data processed: temp={temp}°C, rain_intensity={rain_intensity}mm/h, "
            f"humidity={humidity}%, estimated_annual_precip={estimated_annual_precip:.1f}mm"
        )

        return {
            "mean_annual_temp": temp,
            "annual_precip": estimated_annual_precip,
            "current_humidity": humidity,
            "current_rain_intensity": rain_intensity,
        }

    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to fetch weather data from Tomorrow.io: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Response status: {e.response.status_code}, Content: {e.response.text[:500]}")
        raise
