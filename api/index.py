from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import pandas as pd
import requests
from functools import lru_cache

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Load environment variables
API_KEY = os.environ.get("API_KEY")

# Create sample data inline to avoid file access issues
SAMPLE_DATA = pd.DataFrame({
    'Soil_type': ['Red', 'Black', 'Sandy', 'Clay', 'Loamy'],
    'Crop_type': ['Rice', 'Cotton', 'Maize', 'Wheat', 'Sugarcane'],
    'Avail_N': [250, 300, 200, 220, 280],
    'Avail_P': [8, 12, 6, 9, 11],
    'Exch_K': [100, 120, 80, 90, 110]
})

@lru_cache(maxsize=100)
def get_weather_data(location):
    try:
        if isinstance(location, tuple):
            url = f"http://api.openweathermap.org/data/2.5/weather?lat={location[0]}&lon={location[1]}&appid={API_KEY}&units=metric"
        else:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={location}&appid={API_KEY}&units=metric"
        
        response = requests.get(url)
        data = response.json()

        return {
            'status': 'ok',
            'temperature': data['main']['temp'],
            'rainfall': data.get('rain', {}).get('1h', 0),
            'humidity': data['main']['humidity'],
            'wind_speed': data['wind']['speed'],
            'soil_temp': max(10, data['main']['temp'] - 2),  # Ensure realistic soil temp
            'soil_moisture': min(100, data['main']['humidity'] + 10)  # Cap at 100%
        }
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def generate_farmer_message(recommendation):
    weather = recommendation["weather"]
    fertilizers = recommendation["fertilizers"]
    land_size = recommendation["land_size_m2"]
    fallow_years = recommendation["fallow_years"]

    # Weather advice
    weather_advice = []
    if weather['rainfall'] > 10:
        weather_advice.append("🚨 **Heavy rain warning!** Avoid all field work today.")
    elif weather['rainfall'] > 5:
        weather_advice.append("🌧️ **Rain expected.** Delay fertilizer application.")
    else:
        weather_advice.append("☀️ **Dry conditions.** Water crops if needed.")

    if weather['wind_speed'] > 8:
        weather_advice.append("💨 **Strong winds!** No spraying today.")
    elif weather['wind_speed'] > 5:
        weather_advice.append("🌬️ **Breezy conditions.** Spray carefully.")

    # Soil advice
    soil_advice = []
    if weather['soil_temp'] < 15:
        soil_advice.append("❄️ **Cold soil.** Delay planting warm-season crops.")
    elif weather['soil_temp'] > 30:
        soil_advice.append("🔥 **Hot soil.** Water deeply in early morning.")

    if weather['soil_moisture'] > 85:
        soil_advice.append("💧 **Waterlogged soil.** Improve drainage.")
    elif weather['soil_moisture'] < 40:
        soil_advice.append("🏜️ **Dry soil.** Irrigate soon.")

    # Fertilizer advice
    fert_advice = []
    if "Urea" in fertilizers:
        fert_advice.append("🔵 **Apply Urea** (140kg/acre for nitrogen)")
    if "Single Super Phosphate" in fertilizers:
        fert_advice.append("🟢 **Apply SSP** (50kg/acre for phosphorus)")
    if "Muriate of Potash" in fertilizers:
        fert_advice.append("🟣 **Apply MOP** (40kg/acre for potassium)")

    # Fallow land advice
    fallow_msg = ""
    if fallow_years >= 2:
        fallow_msg = "⚠️ **Long fallow period!** Plant green manure crops."

    # Compile message
    message = f"""
    🌱 **FARMER ADVISORY** 🌱
    ========================
    **FIELD CONDITIONS:**
    - Land: {land_size}m² | Fallow: {fallow_years} year(s)
    - Soil Temp: {weather['soil_temp']}°C | Moisture: {weather['soil_moisture']}%
    
    **WEATHER ALERTS:**
    {chr(10).join(weather_advice)}
    
    **SOIL CARE:**
    {chr(10).join(soil_advice) if soil_advice else "✅ Soil conditions normal"}
    
    **FERTILIZER PLAN:**
    {chr(10).join(fert_advice) if fert_advice else "✅ No fertilizers needed now"}
    
    **SPECIAL NOTES:**
    {fallow_msg if fallow_msg else "No critical issues detected"}
    """
    return message

def fertilizer_recommendation(soil_type, crop_type, land_size, fallow_years,
                           use_my_location=False, lat=None, lon=None, manual_location=None):
    # Use the global sample data
    global SAMPLE_DATA
    
    # Filter dataset
    filtered = SAMPLE_DATA[(SAMPLE_DATA['Soil_type'] == soil_type) & 
                  (SAMPLE_DATA['Crop_type'] == crop_type)]
    if filtered.empty:
        return {'error': 'No data for this soil-crop combination.'}

    # Get weather - if API_KEY is not set, use default values
    if (use_my_location and lat and lon and API_KEY) or (manual_location and API_KEY):
        if use_my_location and lat and lon:
            weather = get_weather_data((lat, lon))
        else:
            weather = get_weather_data(manual_location)
    else:
        weather = {
            'status': 'ok',
            'temperature': 25,
            'rainfall': 0,
            'humidity': 60,
            'wind_speed': 2,
            'soil_temp': 23,
            'soil_moisture': 50
        }

    if weather.get('status') != 'ok':
        return {'error': weather.get('message', 'Weather data unavailable')}

    # Generate recommendation
    row = filtered.iloc[0]
    recommendation = {
        'fertilizers': [],
        'land_size_m2': land_size,
        'fallow_years': fallow_years,
        'weather': weather
    }

    if row['Avail_N'] < 280:
        recommendation['fertilizers'].append("Urea")
    if row['Avail_P'] < 10:
        recommendation['fertilizers'].append("Single Super Phosphate")
    if row['Exch_K'] < 110:
        recommendation['fertilizers'].append("Muriate of Potash")

    return recommendation

@app.get("/")
def read_root():
    return {"message": "Fertilizer Recommendation API is running"}

@app.get("/api/recommend")
async def get_recommendation(
    soil_type: str = Query(..., description="Type of soil"),
    crop_type: str = Query(..., description="Type of crop"),
    land_size: float = Query(..., description="Land size in square meters"),
    fallow_years: int = Query(..., description="Number of years the land has been fallow"),
    use_my_location: bool = Query(False, description="Use location coordinates"),
    lat: float = Query(None, description="Latitude (if use_my_location is True)"),
    lon: float = Query(None, description="Longitude (if use_my_location is True)"),
    manual_location: str = Query(None, description="Location name (if not using coordinates)")
):
    try:
        recommendation = fertilizer_recommendation(
            soil_type=soil_type,
            crop_type=crop_type,
            land_size=land_size,
            fallow_years=fallow_years,
            use_my_location=use_my_location,
            lat=lat,
            lon=lon,
            manual_location=manual_location
        )
        
        if 'error' in recommendation:
            raise HTTPException(status_code=400, detail=recommendation['error'])
            
        # Generate farmer message
        farmer_message = generate_farmer_message(recommendation)
        recommendation['farmer_message'] = farmer_message
        
        return recommendation
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))