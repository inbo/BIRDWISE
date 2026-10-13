import sys
import os
import numpy as np  # We need this for strict data types

# --- STEP 1: FIX THE PATHS ---
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from Py1812 import P1812
    print("✅ Py1812 Library Loaded Successfully!")
except ImportError:
    print("❌ Error: Could not find the Py1812 folder in /src.")
    sys.exit()

# --- STEP 2: STRICT PARAMETERS ---
# We use np.array to ensure the "engine" gets exactly what it wants
f = 0.868
p = 50.0
htg = 30.0
hrg = 1.5
pol = 2

# Coordinates
tx_lat, tx_lon = 50.92, 5.39  
rx_lat, rx_lon = 50.93, 5.40

# THE FIX: Force 'd', 'h', 'R' to be floats and 'zone' to be integers
d = np.array([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float64)
h = np.array([40.0, 40.2, 40.5, 40.2, 40.0], dtype=np.float64)
R = np.array([0.0, 0.0, 0.0, 0.0, 0.0], dtype=np.float64)
zone = np.array([4, 4, 4, 4, 4], dtype=np.int32) # Strictly Integers

# --- STEP 3: RUN THE CALCULATION ---
try:
    # We pass the variables. Note: some versions of this tool 
    # expect (f, p, d, h, R, zone...) in a very specific order.
    lb, ep = P1812.bt_loss(
        f, p, d, h, R, zone, 
        htg, hrg, pol, tx_lat, rx_lat, tx_lon, rx_lon
    )

    print("\n" + "="*20)
    print("   SUCCESSFUL RUN")
    print("="*20)
    print(f"Path Loss (Lb): {lb:.2f} dB")
    print(f"Field Strength (Ep): {ep:.2f} dB(uV/m)")
    
except Exception as e:
    print(f"❌ Calculation Error: {e}")
    # This will print the specific reason if it fails again