import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
import json
import os, sys
import shutil
import platform
import time 
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
    
    GATEWAYS_LIST = settings['gateways']
    tx_power = settings['sensor']['tx_power']
    gain_sn = settings['sensor']['antenna_gain']
    gain_gw = settings['hardware']['antenna_gain_gw']
    l_cable = settings['hardware']['cable_loss_gw']
    freq_GHz = settings['model']['freq_GHz']
    t_perc = settings['model']['time_percentage']
    l_perc = settings['model']['loc_percentage']
    out_name = settings['output']['output_name']

# --- 4. DATA LOADING (POINT VALIDATION MODE) ---
bwk_path = os.path.join(DATA_DIR, "bwk_calibrated.gpkg")
dtm_path = os.path.join(DATA_DIR, "dtm_height_model.tif")
coords_path = os.path.join(DATA_DIR, "locations_coords.csv")

# Load the Heights/Success CSVs
height_files = {
    "Lowest": os.path.join(DATA_DIR, "sampling_notes_lowest.csv"),
    "Middle": os.path.join(DATA_DIR, "sampling_notes_middle.csv"),
    "Highest": os.path.join(DATA_DIR, "sampling_notes_highest.csv")
}

log("📂 Loading spatial and validation files...")
dtm = rasterio.open(dtm_path)
bwk_cal = gpd.read_file(bwk_path)
to_wgs84 = Transformer.from_crs("epsg:31370", "epsg:4326", always_xy=True)

# Load Coordinates
df_coords = pd.read_csv(coords_path) # Expected columns: Sample_location, x_31370, y_31370

# --- 5. PREDICTION ENGINE ---
def run_itu_prediction(gw_x, gw_y, target_x, target_y, gw_h, pL_val):
    log(f"Calculating for pL: {pL_val}")
    dist_m = np.sqrt((gw_x - target_x)**2 + (gw_y - target_y)**2)
    if dist_m > 5000: return 160.0
    if dist_m < 10.0: return 0.0 
    
    num_pts = max(10, int(dist_m / 20.0))
    x_pts = np.linspace(gw_x, target_x, num_pts)
    y_pts = np.linspace(gw_y, target_y, num_pts)
    path_coords = list(zip(x_pts, y_pts))
    
    try:
        h_raw = [float(val[0]) for val in dtm.sample(path_coords)]
        h_vec = np.array(h_raw, dtype=np.float64)
    except: return 999.0

    d_vec = np.linspace(0, dist_m/1000.0, num_pts, dtype=np.float64)
    path_points = gpd.GeoDataFrame(geometry=[Point(p) for p in path_coords], crs=31370)
    joined = gpd.sjoin(path_points, bwk_cal[['calib_h', 'geometry']], how="left", predicate="intersects")
    r_vec = joined['calib_h'].fillna(0.0).values.copy()
    r_vec[0], r_vec[-1] = 0.0, 0.0
#    log(f" r_vec {r_vec}")

    lon1, lat1 = to_wgs84.transform(gw_x, gw_y)
    lon2, lat2 = to_wgs84.transform(target_x, target_y)

    try:
        lb, _ = P1812.bt_loss(freq_GHz, t_perc, d_vec, h_vec, r_vec,
                              np.array([4]*num_pts, dtype=np.int32), 
                              gw_h, 1, 2, lat1, lat2, lon1, lon2, pL = pL_val)
        return float(lb)
    except: return 999.0

# --- 6. VALIDATION SIMULATION ---
log(f"🏁 Starting Validation with Location Percentage iteration...")
start_time = time.time()
all_results = []

for h_label, h_path in height_files.items():
    df_success = pd.read_csv(h_path, sep=";")
    df_merged = pd.merge(df_success, df_coords, left_on='Sample_location', right_on='Sample_location')
    log(f"{df_merged}")
    for gw in GATEWAYS_LIST:
        for idx, row in df_merged.iterrows():
            lb = run_itu_prediction(gw['x'], gw['y'], row['x_31370'], row['y_31370'], 
                                    gw['height'], pL_val=l_perc)
            log(f"{lb}")
            rssi = tx_power + gain_sn + gain_gw - l_cable - lb

            all_results.append({
                'location': row['Sample_location'],
                'height_level': h_label,
                'measured_sf7': row['SF7'],
		'measured_sf9': row['SF9'],
		'measured_sf11': row['SF11'],
		'measured_sf12': row['SF12'],
                'pred_rssi': rssi
            })

# --- 7. EXPORT ---
OUT_BASE = os.path.join(SCRIPT_DIR, "../../Intermediate/Validation")
os.makedirs(OUT_BASE, exist_ok=True)
pd.DataFrame(all_results).to_csv(os.path.join(OUT_BASE, f"{out_name}_comparison.csv"), index=False)

log(f"✨ Validation Complete! Results saved to {OUT_BASE}")