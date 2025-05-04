from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
from pathlib import Path

# Add parent directory to path so we can import logic.py
sys.path.append(str(Path(__file__).parent.parent))
from logic import fertilizer_recommendation, generate_farmer_message

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

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