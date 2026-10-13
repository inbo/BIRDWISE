import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from shapely.geometry import Point
import os, sys
from datetime import datetime

# --- 1. SETUP ENGINE ---
sys.path.append(os.path.join(os.getcwd(), 'src'))
from Py1812 import P1812

# --- 2. CONFIGURATION & MAPPING ---
CLUTTER_HEIGHTS = {
    "water": 0.0, "road": 0.0, "pasture": 10, "heath": 10,
    "agricult": 15, "landscape_elements": 10, "undergrowth": 15,
    "urban": 10.0, "swamp": 10.0, "bog": 10.0,
    "poplar": 20.0, "coniferous": 30.0, "mesophyle_oak": 30.0,
    "wet_forest": 25.0, "mesophile_forest": 25.0, 
    "other_deciduous_forestry": 25.0, "human-disturbed_forest": 30
}

# --- 3. DATA LOADING ---
print("📂 Loading spatial data...")
bwk = gpd.read_file("data/Bwk_Limburg_2023.shp")
dem = rasterio.open("data/dhmv_height_model.tif")
# Note: Ensure these are EPSG:31370 (Lambert 72)

# Define one test gateway (Diepenbeek/NPHK area)
gw_data = [{"id": "gw_test", "lat": 50.9246, "lon": 5.6179}]
gateways = gpd.GeoDataFrame(gw_data, geometry=gpd.points_from_xy([g['lon'] for g in gw_data], [g['lat'] for g in gw_data]), crs=4326).to_crs(31370)

# --- 4. CALCULATION ENGINE ---
from pyproj import Transformer

# Create a transformer to turn Lambert 72 back into Lat/Lon for the ITU engine
# EPSG:31370 is Lambert 72, EPSG:4326 is WGS84 (Lat/Lon)
to_wgs84 = Transformer.from_crs("epsg:31370", "epsg:4326", always_xy=True)

def run_itu_prediction(gw_point, target_point):
    # 1. Basic distance check
    dist_m = gw_point.distance(target_point)
    if dist_m < 10.0: # Skip if under 10m to avoid math errors
        return 0.0 
    
    num_pts = 10 
    x_pts = np.linspace(gw_point.x, target_point.x, num_pts)
    y_pts = np.linspace(gw_point.y, target_point.y, num_pts)
    path_coords = list(zip(x_pts, y_pts))
    
    # 2. Extract Heights (h)
    # Using list comprehension to ensure we don't get strange Rasterio objects
    try:
        h_raw = [float(val[0]) for val in dem.sample(path_coords)]
        h_vec = np.array(h_raw, dtype=np.float64)
        # Clean any NoData values
        h_vec[h_vec < -500] = 0.0
    except:
        return 999.0

    # 3. Get Distance Vector (d) - MUST BE FLOAT64
    dist_km = dist_m / 1000.0
    d_vec = np.linspace(0, dist_km, num_pts, dtype=np.float64)

    # 4. Get Clutter (R) from BWK
    # We do a tiny 'buffer' to make sure the point intersection works reliably
    path_points = gpd.GeoDataFrame(geometry=[Point(p) for p in path_coords], crs=31370)
    joined = gpd.sjoin(path_points, bwk[['bwk_hab', 'geometry']], how="left", predicate="intersects")
    
    # CRITICAL: Sometimes sjoin returns multiple rows per point if boundaries overlap.
    # We group by index and take the first one to ensure length is exactly num_pts.
    r_series = joined.groupby(joined.index)['bwk_hab'].first()
    r_vec = r_series.map(CLUTTER_HEIGHTS).fillna(0.0).values.astype(np.float64)
    
    # Ensure R is exactly the right length
    if len(r_vec) != num_pts:
        # Fallback to zeros if the join failed to produce the right shape
        r_vec = np.zeros(num_pts, dtype=np.float64)

    # 5. Fixed Zones (Inland = 4)
    zone_vec = np.array([4] * num_pts, dtype=np.int32)

    # 6. Coordinate Conversion for ITU Climate Maps
    lon1, lat1 = to_wgs84.transform(gw_point.x, gw_point.y)
    lon2, lat2 = to_wgs84.transform(target_point.x, target_point.y)

    # 7. Run Engine with Error Logging
    try:
        lb, _ = P1812.bt_loss(
            0.868, 50.0, d_vec, h_vec, r_vec, zone_vec,
            14.0, 1, 2, lat1, lat2, lon1, lon2
        )
        # If lb is NaN or Infinite, mark as 999
        if np.isnan(lb) or np.isinf(lb):
            return 999.0
        return float(lb)
    except Exception as e:
        # This will help you see the REAL error in the console
        print(f"DEBUG: Path {dist_m:.0f}m failed with: {e}")
        return 999.0

# --- 5. RUNNING THE GRID SIMULATION ---
# Replace 'grid_sf.shp' with the actual path to your hexagonal grid
grid_path = "data/NPHK_hex_grid.shp" 
grid_sf = gpd.read_file(grid_path)

# Ensure grid is in Lambert 72
if grid_sf.crs != "EPSG:31370":
    grid_sf = grid_sf.to_crs(31370)

# --- 1. DEFINE YOUR HARDWARE SPECS ---
TX_POWER = 14.0       # LoRaWAN standard (dBm)
ANTENNA_GAIN_GW = 5.0 # Your Gateway antenna gain (dBi)
ANTENNA_GAIN_SN = 0.0 # Your Sensor antenna gain (dBi)
CABLE_LOSS_GW = 2.0   # Loss in the coax cable/connectors (dB)

# Sensitivity thresholds (Manufacturer specs)
SENSITIVITY_SF7 = -110.0 
SENSITIVITY_SF12 = -125.0

all_results = []

for idx, gw in gateways.iterrows():
    print(f"📡 Simulating Hardware for: {gw['id']}...")
    for g_idx, cell in grid_sf.iterrows():
        
        # A. Get the physical path loss from ITU model
        lb = run_itu_prediction(gw.geometry, cell.geometry.centroid)
        
        if lb < 500:
            # B. Calculate RSSI (The signal level actually seen by the gateway)
            # RSSI = Tx_Power + Gains - Losses - Path_Loss
            rssi = TX_POWER + ANTENNA_GAIN_SN + ANTENNA_GAIN_GW - CABLE_LOSS_GW - lb
            
            # C. Success Check against hardware sensitivity
            sf7_ok = 1 if rssi >= SENSITIVITY_SF7 else 0
            sf12_ok = 1 if rssi >= SENSITIVITY_SF12 else 0
        else:
            rssi = -999
            sf7_ok = 0
            sf12_ok = 0
            
        all_results.append({
            'gateway': gw['id'],
            'cell_id': cell.get('id', g_idx),
            'path_loss': lb,
            'rssi_dbm': rssi,
            'sf7_ok': sf7_ok,
            'sf12_ok': sf12_ok,
            'geometry': cell.geometry
        })

# --- 6. EXPORTING TO SHAPEFILE ---
results_gdf = gpd.GeoDataFrame(all_results, crs=31370)
output_name = f"NPHK_ITU_Coverage_{datetime.now().strftime('%Y%m%d')}.shp"
results_gdf.to_file(output_name)

print(f"\n✨ SUCCESS! Heatmap saved as {output_name}")

# --- 6. RESULTS ---
df = pd.DataFrame(all_results)
print("\n--- TEST RESULTS ---")
print(df)

print("\n" + "="*30)
print("📈 COVERAGE SUMMARY")
print("="*30)

filename = f"coverage_test_{datetime.now().strftime('%H%M')}.csv"
df.to_csv(filename, index=False)
print(f"\n✅ Results saved to {filename}")

# --- 7. SUMMARY STATISTICS ---
for gw_id in results_gdf['gateway'].unique():
    subset = results_gdf[results_gdf['gateway'] == gw_id]
    # Filter out the '999' invalid values
    valid_subset = subset[subset['path_loss'] < 500]
    
    total_cells = len(valid_subset)
    sf7_pct = (valid_subset['sf7_ok'].sum() / total_cells) * 100
    sf12_pct = (valid_subset['sf12_ok'].sum() / total_cells) * 100
    
    print(f"Gateway: {gw_id}")
    print(f" - Valid Cells Analyzed: {total_cells}")
    print(f" - SF7 Coverage:  {sf7_pct:.1f}%")
    print(f" - SF12 Coverage: {sf12_pct:.1f}%")
    print("-" * 30)