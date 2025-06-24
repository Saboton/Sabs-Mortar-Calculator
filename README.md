# Arma Mortar Calculator (Python, Tkinter)

A modern, interactive mortar calculator for Arma, supporting both Russian and NATO mortars with dynamic ballistic tables, map/heightmap loading, and a user-friendly GUI.

---

## Features

- **Map & Heightmap Loading:**
  - Load any PNG map image and optional grayscale heightmap for elevation-aware calculations.
  - Scrollable, pannable, and zoomable map canvas with smooth, cursor-centered zoom.

- **Ballistic Calculations:**
  - Supports both Russian (6000 mils) and NATO (6400 mils) mortar systems.
  - Dynamically loads ballistic data from external CSVs (`rutable.csv` for Russian, `natotable.csv` for NATO).
  - User-selectable shell types and charge rings, with correct min/max range and dispersion overlays.
  - Calculates azimuth, elevation, time of flight, and dispersion radius, factoring in elevation differences.

- **Intuitive UI:**
  - Modern dark-themed interface with styled buttons and entries.
  - Overlay UI for map size, GPS input, faction/shell selection, and quick project folder loading.
  - Visual range rings, mortar/target markers, and real-time calculation box.

- **No .layer Files:**
  - All legacy .layer file support and UI have been removed for simplicity.

---

## Getting Started

### Requirements
- Python 3.8+
- [Pillow](https://pypi.org/project/Pillow/) (`pip install pillow`)

### Files Needed
- `mortar_calculator_full.py` (main program)
- `rutable.csv` (Russian ballistic table)
- `natotable.csv` (NATO ballistic table)
- Your map image (`map.png` or any PNG)
- (Optional) `heightmap.png` (grayscale PNG for elevation)

### Running the Program
1. **Install dependencies:**
   ```sh
   pip install pillow
   ```
2. **Start the calculator:**
   ```sh
   python mortar_calculator_full.py
   ```

---

## Usage Guide

### 1. Load a Map
- Click **"Load Map"** and select your PNG map image.
- Enter the map's real-world width and height in meters (default: 5120x5120).

### 2. (Optional) Load a Heightmap
- Click **"Load Heightmap"** and select a grayscale PNG heightmap (same dimensions as map).
- Elevation will be used for more accurate firing solutions.

### 3. Set Mortar and Target Positions
- **Left-click** on the map to set the mortar position (red marker).
- **Left-click** again to set the target position (blue marker).
- Alternatively, enter GPS coordinates (e.g., `6500 3400`) and click **"Set Mortar From GPS"**.

### 4. Select Faction and Shell Type
- Use the **"Faction"** dropdown to choose Russian or NATO.
- The **"Shell Type"** dropdown updates automatically based on the selected faction.

### 5. View Calculations
- The calculation box (top-right) displays:
  - Faction, shell, range, azimuth (in mils), charge ring, elevation, time of flight, dispersion, and elevation corrections.
- Range rings and dispersion overlays are drawn on the map.

### 6. Project Folder Loading
- Click **"Load Project Folder"** to quickly load a folder containing `map.png` and `heightmap.png`.

### 7. Reset
- Click **"Reset"** to clear mortar and target positions.

---

## Ballistic Tables
- **CSV Format:** Both `rutable.csv` and `natotable.csv` must have columns:
  - `Shell Type`, `Charge Rings`, `Range (m)`, `Elevation (mil)`, `Time of Flight (sec)`, `Dispersion Radius (m)`
- You can add or edit shell types and data by modifying these CSVs.

---

## Controls & Shortcuts
- **Left-click:** Set mortar/target positions
- **Right-click drag:** Pan map
- **Mouse wheel:** Zoom in/out (centered on cursor)

---

## Troubleshooting
- If the program fails to start, ensure all required files are present and dependencies installed.
- For best results, use map and heightmap images of the same dimensions.
- If no firing solution is found, check that the target is within the selected shell's range and that elevation differences are reasonable.

---

## Credits
- Developed by Sab
- Inspired by https://arma-mortar.com/ by Enj0y
