import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
import json
import os, sys
import shutil
import platform
import time # For runtime performance
from shapely.geometry import Point
from pyproj import Transformer
from datetime import datetime
from tqdm import tqdm

# --- 1. DYNAMIC PATH SETUP ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
SRC_DIR = os.path.join(SCRIPT_DIR, "src")

if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

try:
    from Py1812 import P1812
except ImportError:
    raise ImportError("❌ Critical Error: Could not find Py1812 library.")

# --- 2. SETUP SIMULATION LOG ---
log_entries = []
def log(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    msg = f"[{timestamp}] {message}"
    print(msg)
    log_entries.append(msg)

# --- 3. LOAD SETTINGS ---
settings_path = os.path.join(DATA_DIR, "sim_settings.json")
with open(settings_path, 'r') as f:
    settings = json.load(f)
    print(f"✅ Loaded simulation settings from {settings_path}")
    
    GATEWAYS_LIST = settings['gateways']
    height_sn = settings['sensor']['height']
    tx_power = settings['sensor']['tx_power']
    gain_sn = settings['sensor']['antenna_gain']
    gain_gw = settings['hardware']['antenna_gain_gw']
    l_cable = settings['hardware']['cable_loss_gw']
    SENS_SF7 = settings['hardware']['sensitivity_sf7']
    SENS_SF8 = settings['hardware']['sensitivity_sf8']
    SENS_SF9 = settings['hardware']['sensitivity_sf9']
    SENS_SF10 = settings['hardware']['sensitivity_sf10']
    SENS_SF11 = settings['hardware']['sensitivity_sf11']    
    SENS_SF12 = settings['hardware']['sensitivity_sf12']
    max_dist = settings['model']['max_dist']
    freq_GHz = settings['model']['freq_GHz']
    t_perc = settings['model']['time_percentage']
    l_perc = settings['model']['loc_percentage']
    grid_cell_size = settings['grid_size']['grid_cell_size']
    out_name = settings['output']['output_name']

# --- 4. DATA LOADING & GRID AUDIT ---
bwk_path = os.path.join(DATA_DIR, "bwk_calibrated.gpkg")
dtm_path = os.path.join(DATA_DIR, "dtm_height_model.tif")
grid_path = os.path.join(DATA_DIR, "study_area_hex_grid.shp")

log("📂 Loading spatial files...")
dtm = rasterio.open(dtm_path)
bwk_cal = gpd.read_file(bwk_path)
grid_sf = gpd.read_file(grid_path).to_crs(31370)
to_wgs84 = Transformer.from_crs("epsg:31370", "epsg:4326", always_xy=True)

# Audit first cell for metadata
sample_cell = grid_sf.iloc[0].geometry
cell_area = sample_cell.area
cell_perimeter = sample_cell.length

# --- 5. PREDICTION ENGINE ---
def run_itu_prediction(gw_x, gw_y, target_x, target_y, gw_h):
    gw_p = Point(gw_x, gw_y)
    tg_p = Point(target_x, target_y)
    dist_m = gw_p.distance(tg_p)
    
    if dist_m > max_dist: return 160.0
    if dist_m < 10.0: return 0.0 
    
    num_pts = max(10, int(dist_m / 20.0))
    x_pts = np.linspace(gw_x, target_x, num_pts)
    y_pts = np.linspace(gw_y, target_y, num_pts)
    path_coords = list(zip(x_pts, y_pts))
    
    try:
        h_raw = [float(val[0]) for val in dtm.sample(path_coords)]
        h_vec = np.array(h_raw, dtype=np.float64)
        h_vec[h_vec < -500] = 0.0 
    except: return 999.0

    d_vec = np.linspace(0, dist_m/1000.0, num_pts, dtype=np.float64)
    path_points = gpd.GeoDataFrame(geometry=[Point(p) for p in path_coords], crs=31370)
    joined = gpd.sjoin(path_points, bwk_cal[['calib_h', 'geometry']], how="left", predicate="intersects")
    r_vec = joined['calib_h'].fillna(0.0).values.copy()
    r_vec[0], r_vec[-1] = 0.0, 0.0

    lon1, lat1 = to_wgs84.transform(gw_x, gw_y)
    lon2, lat2 = to_wgs84.transform(target_x, target_y)

    try:
        lb, _ = P1812.bt_loss(freq_GHz, t_perc, d_vec, h_vec, r_vec,
                              np.array([4]*num_pts, dtype=np.int32), 
                              gw_h, height_sn, 2, lat1, lat2, lon1, lon2, pL=l_perc)
        return float(lb) if not (np.isnan(lb) or np.isinf(lb)) else 999.0
    except: return 999.0

# --- 5. GRID SIMULATION ---
print(f"🏁 Starting Simulation for {len(GATEWAYS_LIST)} Gateways...")
start_time = time.time()
all_results = []

try:
    for gw in GATEWAYS_LIST:
        log(f"📡 Processing Gateway: {gw['id']}")
        total_cells = len(grid_sf)
        one_percent = max(1, total_cells // 100)
        pbar = tqdm(total=total_cells, desc="Calculating Paths", unit="cell", miniters=one_percent, file=sys.stdout)
    
        for idx, cell in grid_sf.iterrows():
            target = cell.geometry.centroid
            lb = run_itu_prediction(gw['x'], gw['y'], target.x, target.y, gw['height'])
        
            if lb < 500:
                rssi = tx_power + gain_sn + gain_gw - l_cable - lb
                res = {
                    'gw_id': gw['id'], 'cell_id': cell.get('id', idx), 'path_loss': lb, 'rssi_dbm': rssi,
                    'sf7_ok': 1 if rssi >= SENS_SF7 else 0, 'sf8_ok': 1 if rssi >= SENS_SF8 else 0,
                    'sf9_ok': 1 if rssi >= SENS_SF9 else 0, 'sf10_ok': 1 if rssi >= SENS_SF10 else 0,
                    'sf11_ok': 1 if rssi >= SENS_SF11 else 0, 'sf12_ok': 1 if rssi >= SENS_SF12 else 0,
                    'geometry': cell.geometry
                }
            else:
                res = {k: 0 for k in ['sf7_ok', 'sf8_ok', 'sf9_ok', 'sf10_ok', 'sf11_ok', 'sf12_ok']}
                res.update({'gw_id': gw['id'], 'cell_id': cell.get('id', idx), 'path_loss': 999, 'rssi_dbm': -999, 'geometry': cell.geometry})
            
            all_results.append(res)
            pbar.update(1)
        pbar.close()
except Exception as e:
    log(f"❌ CRITICAL ERROR during simulation: {str(e)}")

end_time = time.time()
duration = round(end_time - start_time, 2)
log(f"✅ Simulation finished in {duration} seconds.")

# --- 7. EXPORT & METADATA ---
print("\n📦 Finalizing Pipeline Output...")
OUT_BASE = os.path.join(SCRIPT_DIR, "../Intermediate")
TEMP_DIR = os.path.join(OUT_BASE, out_name)
os.makedirs(TEMP_DIR, exist_ok=True)

csv_path = os.path.join(TEMP_DIR, f"{out_name}.csv")
df_results = pd.DataFrame(all_results).drop(columns='geometry')
df_results.to_csv(csv_path, index=False)
log("📝 Results saved as CSV.")

# 2. Save Shapefiles (gateways)
gw_geom = [Point(gw['x'], gw['y']) for gw in GATEWAYS_LIST]
gateways_gdf = gpd.GeoDataFrame(pd.DataFrame(GATEWAYS_LIST), geometry=gw_geom, crs=31370)
gateways_gdf.to_file(os.path.join(TEMP_DIR, f"{out_name}_gws.shp"))

# 3. Save Metadata (The DNA of the run) and log
with open(os.path.join(TEMP_DIR, "simulation_log.txt"), 'w') as f:
    f.write("\n".join(log_entries))

metadata = {
    "run_info": {"name": out_name, "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "machine": platform.node()},
    "input_files": {"dtm": os.path.basename(dtm_path), "clutter": os.path.basename(bwk_path), "grid": os.path.basename(grid_path)},
    "parameters": settings,
    "grid_audit": {"grid_file": os.path.basename(grid_path), "grid_cell_size": grid_cell_size, "total_cells": len(grid_sf), "crs": str(grid_sf.crs), "cell_area_m2": round(cell_area, 2), "cell_perimeter_m": round(cell_perimeter, 2)}
}
with open(os.path.join(TEMP_DIR, "metadata.json"), 'w') as f:
    json.dump(metadata, f, indent=4)

# 4. ZIP and Cleanup
shutil.make_archive(TEMP_DIR, 'zip', TEMP_DIR)
shutil.rmtree(TEMP_DIR)

print(f"✨ Master Pipeline Complete! Run saved as: {out_name}.zip")