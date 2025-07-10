from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime
import logging
import json
import os
from django.http import HttpResponse
from .ipcc_calculations import calculate_total_emissions
from .data_fetchers import geocode_commune, fetch_soil_data, fetch_weather_data
from .recommendation_service import CarbonRecommendationService
from .report_service import EnhancedReportService
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------------------------------------------------------
# Static reference data for the frontend drop-downs
# ---------------------------------------------------------------------------

COMMUNES = [
    'Abong-Mbang','Afanloum','Ako','Akoeman','Akom 2','Akono','Akonolinga','Akwaya','Alou','Ambam',
    'Assamba','Awae','Ayos','Babadjou','Babessi','Bafang','Bafia','Bafoussam 1er','Bafoussam 2e','Bafoussam 3e',
    'Bafut','Baham','Bakou','Bali','Balikumbat','Bamenda 1st','Bamenda 2nd','Bamenda 3rd','Bamendjou','Bamusso',
    'Bana','Bandja','Bangangte','Bangem','Bangou','Bangourain','Banka','Bankim','Banwa','Banyo',
    'Bare-Bakem','Bascheo','Bassamba','Batcham','Batchenga','Batibo','Batie','Batouri','Bayangam','Bazou',
    'Bebend','Beka','Belabo','Belel','Belo','Bengbis','Bertoua 1er','Bertoua 2e','Betare-Oya','Bibemi',
    'Bibey','Bikok','Bipindi','Biwong-Bane','Biwong-Bulu','Biyouha','Blangoua','Bogo','Bokito','Bombe',
    'Bondjock','Bot-Makak','Bourrha','Buea','Bum','Campo','Darak','Dargala','Datcheka','Dembo',
    'Demsa','Deuk','Diang','Dibamba','Dibang','Dibombari','Dikome Balue','Dimako','Dir','Dizangue',
    'Dja','Djebem','Djohong','Djoum','Douala 1er','Douala 2e','Douala 3e','Douala 4e','Douala 5e','Douala 6e',
    'Doumaintang','Doume','Dschang','Dzeng','Ebebda','Ebolowa 1er','Ebolowa 2e','Edea 1er','Edea 2e','Edzendouan',
    'Efoulan','Ekondo Titi','Elig-Mfomo','Endom','Eseka','Esse','Evodoula','Eyumodjock','Figuil','Fiko',
    'Fokoue','Fongo-Tongo','Fontem','Fotokol','Foumban','Foumbot','Fundong','Fungom','Furu-Awa','Galim',
    'Galim-Tignere','Gari Gombo','Garoua-Boulai','Garoua 1er','Garoua 2e','Garoua 3e','Gazawa','Gobo','Goulfey','Guere',
    'Guider','Guidiguis','Hile-Alifa','Hina','Idabato','Isangele','Jakiri','Kaele','Kai-Kai','Kalfou',
    'Kar-Hay','Kekem','Kette','Kiiki','Kolofata','Kombo Abedimo','Kombo Itindi','Kon Yambetta','Kontcha','Konye',
    'Kouoptamo','Kousseri','Koutaba','Koza','Kribi 1er','Kribi 2e','Kumba 1st','Kumba 2nd','Kumba 3rd','Kumbo',
    'Kye-Ossi','Lagdo','Lembe Yezoum','Limbe 1st','Limbe 2nd','Limbe 3rd','Lobo','Logone-Birni','Lokoundje','Lolodorf',
    'Lomie','Loum','Maan','Madingring','Maga','Magba','Makak','Makary','Makenene','Malantouen',
    'Mamfe','Mandjou','Manjo','Maroua 1er','Maroua 2e','Maroua 3e','Martap','Massangam','Massock-Songloulou','Matomb',
    'Mayo-Baleo','Mayo-Darle','Mayo-Hourna','Mayo-Moskota','Mayo-Oulo','Mbalmayo','Mbandjock','Mbang','Mbanga','Mbangassina',
    'Mbankomo','Mbe','Mbengwi','Mboanz','Mboma','Mbonge','Mbotoro','Mbouda','Mbven','Meiganga',
    'Melong','Menchum-Valley','Mengang','Mengong','Mengueme','Meri','Messamena','Messok','Messondo','Meyomessala',
    'Meyomessi','Mfou','Mindif','Minta','Mintom','Misaje','Mogode','Mokolo','Moloundou','Mombo',
    'Monatele','Mora','Mouanko','Moulvoudaye','Moutourwa','Mundemba','Muyuka','Mvangane','Mvengue','Nanga-Eboko',
    'Ndelele','Ndem Nam','Ndikinimeki','Ndom','Ndop','Ndoukoula','Ndu','Ngambe','Ngambe-Tikar','Nganha',
    'Ngaoui','Ngaoundal','Ngaoundere 1er','Ngaoundere 2e','Ngaoundere 3e','Ngie','Ngog-Mapubi','Ngomedzap','Ngoro','Ngoulemakong',
    'Ngoumou','Ngoura','Ngoyla','Nguelemendouka','Nguibassal','Nguti','Ngwei','Niete','Nitoukou','Njikwa',
    'Njimom','Njinikom','Njombe-Penja','Nkambe','Nkolafamba','Nkolmetet','Nkondjock','Nkong-Ni','Nkongsamba 1er','Nkongsamba 2e',
    'Nkongsamba 3e','Nkoteng','Nkum','Nlonako','Noni','Nord-Makombe','Nsem','Ntui','Nwa','Nyakokombo',
    'Nyambaka','Nyanon','Obala','Okola','Oku','Olamze','Ombessa','Oveng','Penka-Michel','Pette',
    'Pitoa','Poli','Porhi','Pouma','Poumougne','Rey-Bouba','Saa','Salapoumbe','Sangmelima','Santa',
    'Santchou','Soa','Somalomo','Soulede-Roua','Taibong','Tchatibali','Tcheboa','Tchollire','Tibati','Tignere',
    'Tiko','Toko','Tokombere','Tombel','Tonga','Touboro','Touroua','Tubah','Upper Bayang','Vele',
    'Wabane','Waza','West-Coast','Widikum','Wina','Wum','Yabassi','Yagoua','Yaounde 1er','Yaounde 2e',
    'Yaounde 3e','Yaounde 4e','Yaounde 5e','Yaounde 6e','Yaounde 7e','Yingui','Yokadouma','Yoko','Zina','Zoetele'
]

CROP_CLASSES = [
    {'value': 'cereals', 'label': 'Cereals (maize, rice, wheat, sorghum, millet)'},
    {'value': 'legumes', 'label': 'Legumes (beans, cowpeas, groundnuts, soybeans)'},
    {'value': 'tubers', 'label': 'Tubers (yam, sweet potato, cassava)'},
    {'value': 'root_crops', 'label': 'Root Crops (cassava, plantain)'},
    {'value': 'vegetables', 'label': 'Vegetables (tomatoes, onions, peppers)'},
    {'value': 'fruits', 'label': 'Fruits (citrus, avocado, mango)'},
    {'value': 'cash_crops', 'label': 'Cash Crops (cocoa, coffee, cotton, oil palm)'},
    {'value': 'pasture', 'label': 'Pasture/Fodder (grass, hay)'},
]
LIVESTOCK_TYPES = ['cattle','goats','sheep','pigs','poultry','rabbits']

def get_current_season() -> str:
    """Auto-detect season for Cameroon based on current month."""
    current_month = datetime.now().month
    # Cameroon seasonal pattern: Wet season (March-October), Dry season (November-February)
    if 3 <= current_month <= 10:
        return 'rainy'
    else:
        return 'dry'

@api_view(['GET'])
def get_form_options(request) -> Response:
    """Return reference lists used by the Vue.js frontend drop-downs (new schema only)."""
    return Response(
        {
            'communes': COMMUNES,
            'farming_practices': [
                {'value': 'conventional', 'label': 'Traditional Farming'},
                {'value': 'organic', 'label': 'Natural Farming'},
                {'value': 'agroforestry', 'label': 'Tree + Crop Farming'},
                {'value': 'conservation', 'label': 'Soil-Saving Farming'},
                {'value': 'mixed', 'label': 'Mixed Crop / Livestock'},
            ],
            'fertilizer_types': [
                {'value': 'none', 'label': 'None'},
                {'value': 'organic', 'label': 'Organic (manure, compost)'},
                {'value': 'synthetic', 'label': 'Synthetic (urea, NPK)'},
                {'value': 'both', 'label': 'Both Organic & Synthetic'},
            ],
            'crop_classes': CROP_CLASSES,
            'tillage_practices': [
                {'value': 'conventional_till', 'label': 'Conventional Tillage'},
                {'value': 'reduced_till', 'label': 'Reduced Tillage'},
                {'value': 'no_till', 'label': 'No-Till / Direct Seeding'},
            ],
            'livestock_types': LIVESTOCK_TYPES,
            'seasons': ['dry', 'rainy', 'transition'],
            'current_season': get_current_season(),
        }
    )

@api_view(['GET'])
def health_check(request) -> Response:
    """Simple health check endpoint."""
    return Response({
        'status': 'healthy',
        'service': 'Carbon Modelling API v2.0 - Cameroon',
        'current_season': get_current_season(),
        'methodology': 'Original EcosystemPlus Logic'
    })

# Add regular Django view for serving the frontend
from django.shortcuts import render
from django.http import HttpResponse
import os

def frontend_view(request) -> HttpResponse:
    """Serve the frontend HTML page."""
    frontend_path = os.path.join(os.path.dirname(__file__), '../frontend/index.html')
    try:
        with open(frontend_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        return HttpResponse(html_content, content_type='text/html')
    except FileNotFoundError:
        return HttpResponse('Frontend file not found.', status=404)

@api_view(['POST'])
def carbon_model(request) -> Response:
    """Comprehensive carbon modelling endpoint following IPCC 2019 methodology. Only accepts new schema."""
    try:
        payload = request.data
        required_fields = [
            'farm_size', 'commune', 'farming_practice', 'fertilizer_type',
            'fertilizer_rate', 'crop_classes', 'tillage_practice', 'irrigation'
        ]
        for field in required_fields:
            if field not in payload:
                return Response({'error': f'Missing required field: {field}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate crop_classes is a list and not empty
        crop_classes = payload.get('crop_classes', [])
        if not isinstance(crop_classes, list) or len(crop_classes) == 0:
            return Response({'error': 'At least one crop class must be selected'}, status=status.HTTP_400_BAD_REQUEST)

        # --- Type validation and sanitization ---
        payload['farm_size'] = float(payload.get('farm_size') or 0.0)
        payload['fertilizer_rate'] = float(payload.get('fertilizer_rate') or 0.0)
        if payload.get('uses_machinery'):
            # Handle both fuel_consumption (frontend) and fuel_usage (backend) keys
            fuel_consumption = payload.get('fuel_consumption') or payload.get('fuel_usage') or 0.0
            payload['fuel_usage'] = float(fuel_consumption)
        
        if payload.get('keeps_livestock'):
            sanitized_counts = {}
            for animal, value in (payload.get('livestock_counts') or {}).items():
                try:
                    sanitized_counts[animal] = int(value or 0)
                except (TypeError, ValueError):
                    sanitized_counts[animal] = 0
            payload['livestock_counts'] = sanitized_counts

        # --- Fetch external data ---
        try:
            lat, lon = geocode_commune(payload['commune'])
        except Exception as e:
            logging.error(f"Geocoding failed for commune '{payload['commune']}': {e}")
            return Response({'error': f'Could not find location: {payload["commune"]}. Please check the commune name.'}, 
                           status=status.HTTP_400_BAD_REQUEST)

        # Fetch soil & weather in parallel to minimise latency
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                soil_future = pool.submit(fetch_soil_data, lat, lon)
                weather_future = pool.submit(fetch_weather_data, lat, lon)
                soil_data = soil_future.result()
                weather_data = weather_future.result()
        except Exception as e:
            logging.error(f"External data fetch failed: {e}")
            return Response({'error': 'Unable to fetch weather and soil data. Please try again later.'}, 
                           status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # --- Core Calculation ---
        emissions = calculate_total_emissions(payload, weather_data, soil_data)
        benchmarks = {'average': 0, 'best_quartile': 0}
        
        # Debug logging
        logging.info("Raw emissions calculation result: %s", emissions)

        

        # --- Prepare Frontend Response ---
        em_sources = emissions.get("emissions_sources", {})
        livestock_emissions = (
            em_sources.get("Livestock (Enteric Fermentation)", 0.0) +
            em_sources.get("Livestock (Manure Management)", 0.0)
        )
        
        ui_emissions = {
            'fertilizer_emissions': em_sources.get("Fertilizer Application", 0.0),
            'livestock_emissions': livestock_emissions,
            'fuel_emissions': em_sources.get("Fuel Combustion", 0.0),
            'soil_change': emissions.get("soil_carbon_sequestration", 0.0),
            'total_emissions': max(0.0, emissions.get("net_emissions", 0.0)),
            'raw_net_emissions': emissions.get("net_emissions", 0.0),
        }

        farm_size = payload['farm_size'] if payload['farm_size'] > 0 else 1
        emissions_per_ha = ui_emissions['total_emissions'] / farm_size

        def classify_intensity(value: float) -> str:
            if value < 1000: return 'low'
            if value < 2000: return 'medium'
            if value < 4000: return 'high'
            return 'very_high'

        metrics = {
            'emissions_per_hectare': emissions_per_ha,
            'carbon_intensity': classify_intensity(emissions_per_ha),
        }
        
        payload['season'] = get_current_season()

        response_data = {
            'success': True,
            'emissions': ui_emissions,
            'metrics': metrics,
            'raw_emissions': emissions,
            'summary': "Recommendations are being generated and will be available shortly.",
            'recommendations': "Generating…",
            'soil_data': soil_data,
            'weather_data': weather_data,
            'farm_data': payload,
            'async_generation': True,
        }
        
        # Debug logging
        logging.info("UI emissions data: %s", ui_emissions)
        logging.info("Final response data: %s", response_data)
        return Response(response_data, status=status.HTTP_200_OK)
    except Exception as exc:
        logging.exception("Error in carbon_model endpoint")
        return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def download_report(request) -> HttpResponse:
    """Generate and download a PDF report based on the provided farm data."""
    try:
        payload = request.data
        
        # --- Data Fetching and Calculation ---
        lat, lon = geocode_commune(payload['commune'])
        soil_data = fetch_soil_data(lat, lon)
        weather_data = fetch_weather_data(lat, lon)
        emissions = calculate_total_emissions(payload, weather_data, soil_data)
        
        # --- PDF Generation ---
        report_service = EnhancedReportService()
        pdf_buffer = report_service.generate_and_send_report(
            payload, emissions, benchmarks={}, climate_zone=emissions['climate_zone']
        )
        
        # --- HTTP Response ---
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="EcosystemPlus_Carbon_Report.pdf"'
        return response

    except Exception as e:
        logging.exception("Error in download_report endpoint")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
