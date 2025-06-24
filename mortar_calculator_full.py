import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import math
import os
import re

# === FULL BALLISTIC TABLE (HARDCODED FROM HE_BallsticTable.txt) ===
ballistic_table = [
    # 0 Charges
    (0, 50, 1455, 15.0), (0, 100, 1411, 15.0), (0, 150, 1365, 14.9), (0, 200, 1318, 14.8),
    (0, 250, 1268, 14.6), (0, 300, 1217, 14.4), (0, 350, 1159, 14.1), (0, 400, 1095, 13.7),
    (0, 450, 1023, 13.2), (0, 500, 922, 12.4),
    # 1 Charges
    (1, 100, 1446, 19.5), (1, 200, 1392, 19.4), (1, 300, 1335, 19.2), (1, 400, 1275, 18.9),
    (1, 500, 1212, 18.6), (1, 600, 1141, 18.1), (1, 700, 1058, 17.4), (1, 800, 952, 16.4),
    # 2 Charges
    (2, 200, 1432, 24.8), (2, 300, 1397, 24.7), (2, 400, 1362, 24.6), (2, 500, 1325, 24.4),
    (2, 600, 1288, 24.2), (2, 700, 1248, 24.0), (2, 800, 1207, 23.7), (2, 900, 1162, 23.3),
    (2, 1000, 1114, 22.9), (2, 1100, 1060, 22.3), (2, 1200, 997, 21.5), (2, 1300, 914, 20.4),
    (2, 1400, 755, 17.8),
    # 3 Charges
    (3, 300, 1423, 28.9), (3, 400, 1397, 28.8), (3, 500, 1370, 28.6), (3, 600, 1343, 28.5),
    (3, 700, 1315, 28.5), (3, 800, 1286, 28.3), (3, 900, 1257, 28.1), (3, 1000, 1226, 27.9),
    (3, 1100, 1193, 27.6), (3, 1200, 1159, 27.2), (3, 1300, 1123, 26.8), (3, 1400, 1084, 26.4),
    (3, 1500, 1040, 25.8), (3, 1600, 991, 25.1), (3, 1700, 932, 24.2), (3, 1800, 851, 22.8),
    # 4 Charges
    (4, 400, 1418, 32.9), (4, 500, 1398, 32.9), (4, 600, 1376, 32.8), (4, 700, 1355, 32.7),
    (4, 800, 1333, 32.6), (4, 900, 1311, 32.4), (4, 1000, 1288, 32.2), (4, 1100, 1264, 32.1),
    (4, 1200, 1240, 31.8), (4, 1300, 1215, 31.6), (4, 1400, 1189, 31.3), (4, 1500, 1161, 31.0),
    (4, 1600, 1133, 30.7), (4, 1700, 1102, 30.3), (4, 1800, 1069, 29.8), (4, 1900, 1034, 29.3),
    (4, 2000, 995, 28.7), (4, 2100, 950, 27.9), (4, 2200, 896, 26.9), (4, 2300, 820, 25.3),
]

# Dispersion radius per ring (meters)
dispersion_radius = {0: 8, 1: 13, 2: 19, 3: 27, 4: 34}

# Organize ballistic data by ring
ring_data = {}
for ring, dist, elev, tof in ballistic_table:
    ring_data.setdefault(ring, []).append({
        "RANGE (M)": dist,
        "ELEV (MIL)": elev,
        "TIME OF FLIGHT (SEC)": tof
    })

def interpolate_ballistics(ring, distance_m):
    """Interpolate elevation and TOF for a given ring and distance."""
    data = ring_data[ring]
    for i in range(len(data) - 1):
        a, b = data[i], data[i + 1]
        if a["RANGE (M)"] <= distance_m <= b["RANGE (M)"]:
            ratio = (distance_m - a["RANGE (M)"]) / (b["RANGE (M)"] - a["RANGE (M)"])
            elev = a["ELEV (MIL)"] + ratio * (b["ELEV (MIL)"] - a["ELEV (MIL)"])
            tof = a["TIME OF FLIGHT (SEC)"] + ratio * (b["TIME OF FLIGHT (SEC)"] - a["TIME OF FLIGHT (SEC)"])
            return elev, tof
    return None, None

class MortarApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Arma Mortar Calculator")
        self.display_scale = 0.5
        self.mortar = None
        self.target = None
        self.map_width_px = None
        self.map_height_px = None
        self.m_per_px = 1
        self.heightmap_image = None
        self.max_elevation_m = 512
        self.original_img = None
        self.tk_img = None
        self.layer_entities = []
        self._build_gui()

    def _build_gui(self):
        # --- Scrollable Canvas Setup ---
        self.canvas_frame = tk.Frame(self.root)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        self.hbar = tk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.hbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.vbar = tk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.vbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas = tk.Canvas(self.canvas_frame, width=800, height=600, bg="gray",
                               xscrollcommand=self.hbar.set, yscrollcommand=self.vbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.hbar.config(command=self.canvas.xview)
        self.vbar.config(command=self.canvas.yview)

        # Input widgets for the canvas (top left)
        self.map_width_m = tk.IntVar(value=5120)
        self.map_height_m = tk.IntVar(value=5120)
        self.coord_var = tk.StringVar()

        self.entry_map_width = tk.Entry(self.canvas, textvariable=self.map_width_m, width=6)
        self.entry_map_height = tk.Entry(self.canvas, textvariable=self.map_height_m, width=6)
        self.entry_gps = tk.Entry(self.canvas, textvariable=self.coord_var, width=12)
        self.btn_load_map = tk.Button(self.canvas, text="Load Map", command=self.load_map, width=10)
        self.btn_load_heightmap = tk.Button(self.canvas, text="Load Heightmap", command=self.load_heightmap, width=13)
        self.btn_set_gps = tk.Button(self.canvas, text="Set Mortar From GPS", command=self.set_mortar_from_coords, width=18)
        self.btn_load_layer = tk.Button(self.canvas, text="Load Layer", command=self.load_layer_file, width=12)
        self.btn_load_project = tk.Button(self.canvas, text="Load Project Folder", command=self.load_project_folder, width=20)
        self.btn_reset = tk.Button(self.canvas, text="Reset", command=self.reset_positions, width=10)

        self.canvas.bind("<Button-1>", self.handle_left_click)
        self.canvas.bind("<B3-Motion>", self.on_pan)
        self.canvas.bind("<ButtonPress-3>", self.on_pan_start)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)  # Windows
        self.canvas.bind("<Button-4>", self.on_mousewheel)    # Linux scroll up
        self.canvas.bind("<Button-5>", self.on_mousewheel)    # Linux scroll down

        self.canvas.bind('<Configure>', lambda e: self.update_view())
        self.layer_entities = []
        self._click_state = 0
        self._pan_start = None
        # Add output text box at the bottom of the window
        self.output = tk.Text(self.root, height=6, width=80, bg="#181818", fg="#fff", font=("Consolas", 10))
        self.output.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

    def handle_left_click(self, e):
        if not self.map_width_px or not self.map_height_px:
            messagebox.showwarning("No Map", "Please load a map first.")
            return
        cx = self.canvas.canvasx(e.x)
        cy = self.canvas.canvasy(e.y)
        px = int(cx / self.display_scale)
        py = int(cy / self.display_scale)
        if self.mortar is None:
            self.mortar = (px, py)
            self.target = None
        else:
            self.target = (px, py)
        self.update_view()

    def reset_positions(self):
        self.mortar = None
        self.target = None
        self._click_state = 0
        self.update_view()

    def on_pan_start(self, event):
        self._pan_start = (event.x, event.y, self.canvas.xview()[0], self.canvas.yview()[0])

    def on_pan(self, event):
        if self._pan_start is None:
            return
        x0, y0, xview0, yview0 = self._pan_start
        dx = event.x - x0
        dy = event.y - y0
        w = int(self.map_width_px * self.display_scale) if self.map_width_px else 800
        h = int(self.map_height_px * self.display_scale) if self.map_height_px else 600
        # Move view by delta
        self.canvas.xview_moveto(max(0, min(1, xview0 - dx / max(1, w))))
        self.canvas.yview_moveto(max(0, min(1, yview0 - dy / max(1, h))))

    def on_mousewheel(self, event):
        # Smoother zoom: smaller factor, always center on cursor
        if hasattr(event, 'delta'):
            if event.delta > 0:
                zoom = 1.05
            else:
                zoom = 0.95
        elif hasattr(event, 'num'):
            if event.num == 4:
                zoom = 1.05
            elif event.num == 5:
                zoom = 0.95
            else:
                return
        else:
            return
        new_scale = max(0.1, min(self.display_scale * zoom, 5.0))
        if abs(new_scale - self.display_scale) < 1e-4:
            return
        # Get mouse position in canvas (relative to scroll region)
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        map_x = canvas_x / self.display_scale
        map_y = canvas_y / self.display_scale
        self.display_scale = new_scale
        self.update_view()
        # After update, move the view so the point under the cursor stays under the cursor
        new_canvas_x = map_x * self.display_scale
        new_canvas_y = map_y * self.display_scale
        w = int(self.map_width_px * self.display_scale) if self.map_width_px else 800
        h = int(self.map_height_px * self.display_scale) if self.map_height_px else 600
        # Calculate new scroll fractions to keep cursor under mouse
        x_frac = max(0, min(1, (new_canvas_x - event.x) / max(1, w)))
        y_frac = max(0, min(1, (new_canvas_y - event.y) / max(1, h)))
        self.canvas.xview_moveto(x_frac)
        self.canvas.yview_moveto(y_frac)

    def load_map(self):
        path = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if not path:
            return
        img = Image.open(path)
        self.original_img = img
        self.map_width_px, self.map_height_px = img.width, img.height
        # Set initial display_scale so image fits within 1024x1024
        max_dim = max(self.map_width_px, self.map_height_px)
        if max_dim > 1024:
            self.display_scale = 1024 / max_dim
        else:
            self.display_scale = 1.0
        display_img = img.resize(
            (int(img.width * self.display_scale), int(img.height * self.display_scale)),
            resample=Image.BILINEAR
        )
        self.tk_img = ImageTk.PhotoImage(display_img)
        self.canvas.config(width=display_img.width, height=display_img.height)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
        mpp_x = self.map_width_m.get() / self.map_width_px
        mpp_y = self.map_height_m.get() / self.map_height_px
        self.m_per_px = (mpp_x + mpp_y) / 2
        self.draw_grid()

    def load_heightmap(self):
        path = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if not path:
            return
        img = Image.open(path).convert("L")
        self.heightmap_image = img

    def draw_grid(self):
        if not self.map_width_px or not self.map_height_px:
            return
        spacing = 1000 / self.m_per_px * self.display_scale
        self.canvas.delete("grid")
        for x in range(0, int(self.map_width_px * self.display_scale), int(spacing)):
            self.canvas.create_line(x, 0, x, int(self.map_height_px * self.display_scale),
                                    fill="white", dash=(2, 2), tags="grid")
        for y in range(0, int(self.map_height_px * self.display_scale), int(spacing)):
            self.canvas.create_line(0, y, int(self.map_width_px * self.display_scale), y,
                                    fill="white", dash=(2, 2), tags="grid")

    def set_mortar(self, e):
        if not self.map_width_px or not self.map_height_px:
            messagebox.showwarning("No Map", "Please load a map first.")
            return
        # Use canvasx/canvasy for correct coordinates in scrollable/zoomed canvas
        cx = self.canvas.canvasx(e.x)
        cy = self.canvas.canvasy(e.y)
        self.mortar = (int(cx / self.display_scale), int(cy / self.display_scale))
        self.update_view()

    def set_target(self, e):
        if not self.map_width_px or not self.map_height_px:
            messagebox.showwarning("No Map", "Please load a map first.")
            return
        cx = self.canvas.canvasx(e.x)
        cy = self.canvas.canvasy(e.y)
        self.target = (int(cx / self.display_scale), int(cy / self.display_scale))
        self.update_view()

    def set_mortar_from_coords(self):
        try:
            text = self.coord_var.get().strip()
            parts = text.split()
            if len(parts) != 2:
                raise ValueError("Invalid format. Use: 6500 3400 or 02480 03659")
            x_str, z_str = parts[0], parts[1]
            if not (x_str.isdigit() and z_str.isdigit()):
                raise ValueError("Coordinates must be numeric (meters)")
            x_m = int(x_str)
            z_m = int(z_str)
            # Check if coordinates are within map bounds
            map_w_m = self.map_width_m.get()
            map_h_m = self.map_height_m.get()
            if not (0 <= x_m <= map_w_m and 0 <= z_m <= map_h_m):
                raise ValueError(f"Coordinates out of map bounds: X={x_m} Z={z_m} (Map size: {int(map_w_m)}x{int(map_h_m)} m)")
            if not self.map_width_px or not self.map_height_px:
                raise ValueError("Load a map first.")
            # Use separate scaling for X and Y
            mpp_x = map_w_m / self.map_width_px
            mpp_y = map_h_m / self.map_height_px
            px = x_m / mpp_x
            py = self.map_height_px - (z_m / mpp_y)
            px = max(0, min(px, self.map_width_px - 1))
            py = max(0, min(py, self.map_height_px - 1))
            self.mortar = (int(px), int(py))
            self.output.insert(tk.END, f"Set mortar at GPS coords X={x_m} Z={z_m} → px={int(px)} py={int(py)}\n")
            self.update_view()
        except Exception as e:
            self.output.insert(tk.END, f"Failed to parse coords: {e}\n")

    def load_layer_file(self):
        path = filedialog.askopenfilename(filetypes=[("Layer files", "*.layer")])
        if not path:
            return
        self.layer_entities = self.parse_layer_file(path)
        self.update_view()

    def parse_layer_file(self, path):
        # Robust parser: extract and render single points (coords lines) and their names from entity blocks
        entities = []
        coords_re = re.compile(r'coords\s+([\-\d\.eE]+)\s+([\-\d\.eE]+)\s+([\-\d\.eE]+)')
        entity_start_re = re.compile(r'^(\w+entity)')  # e.g., genericentity, spawnpointentity, etc.
        prop_name_re = re.compile(r'name\s*=\s*"([^"]+)"')
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        debug_count = 0
        current_entity_name = ''
        in_entity_block = False
        for idx, line in enumerate(lines):
            l = line.strip()
            # Detect start of a new entity block
            if entity_start_re.match(l):
                in_entity_block = True
                current_entity_name = ''
            # If this line has a name property, extract it (only if in entity block)
            if in_entity_block:
                pname = prop_name_re.search(l)
                if pname:
                    current_entity_name = pname.group(1).strip()
            # If this line has coords, create a point entity
            m = coords_re.search(l)
            if m and in_entity_block:
                pt = [float(m.group(1)), float(m.group(2)), float(m.group(3))]
                if not all(abs(x) < 1e-6 for x in pt):
                    name = current_entity_name or 'unnamed'
                    entities.append({'type': 'point', 'coords': pt, 'name': name})
                    if debug_count < 10:
                        print(f"[DEBUG] Point entity parsed: {pt} name: {name}")
                        debug_count += 1
                # After coords, end of entity block
                in_entity_block = False
        print(f"[DEBUG] Parsed {len(entities)} point entities from {path}")
        return entities

    def draw_layer_entities(self):
        # Draw all layer entities onto a transparent Pillow image and return it
        if not hasattr(self, 'layer_entities') or not self.layer_entities or not self.original_img:
            print("[DEBUG] No layer entities to draw.")
            return None
        w = int(self.map_width_px * self.display_scale)
        h = int(self.map_height_px * self.display_scale)
        try:
            map_h_m = float(self.map_height_km.get()) * 1000
        except Exception:
            map_h_m = self.map_height_px * self.m_per_px
        overlay_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(overlay_img, 'RGBA')
        debug_count = 0
        drawn_count = 0
        font = None
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except Exception:
            font = None
        for idx, ent in enumerate(self.layer_entities[:20]):
            print(f"[DEBUG] Raw entity {idx}: {ent}")
        def is_zero_point(pt):
            return all(abs(x) < 1e-6 for x in pt)
        for ent in self.layer_entities:
            if ent.get('type') == 'point' and ent.get('coords'):
                pt = ent['coords']
                if is_zero_point(pt):
                    continue
                x, y, z = pt
                px = x / self.m_per_px
                py = (map_h_m - z) / self.m_per_px
                px_disp = px * self.display_scale
                py_disp = py * self.display_scale
                r = 6
                draw.ellipse([px_disp-r, py_disp-r, px_disp+r, py_disp+r], fill=(255,255,0,255), outline=(0,0,0,255), width=2)
                # Draw name if available
                name = ent.get('name', '')
                if name:
                    draw.text((px_disp + r + 2, py_disp - r), name, fill=(255,255,255,255), font=font)
                drawn_count += 1
        print(f"[DEBUG] Entities drawn on overlay: {drawn_count}")
        print(f"[DEBUG] Total entities: {len(self.layer_entities)}")
        return overlay_img

    def update_view(self):
        # Only delete specific tags, not 'all', to preserve overlays and grid
        self.canvas.delete("marker")
        self.canvas.delete("layer_marker")
        self.canvas.delete("layer")
        self.canvas.delete("grid")
        self.canvas.delete("inputbox")
        self.canvas.delete("calcbox")
        # Redraw the map image at the current scale
        if self.original_img is not None:
            w = int(self.map_width_px * self.display_scale)
            h = int(self.map_height_px * self.display_scale)
            display_img = self.original_img.resize((w, h), resample=Image.BILINEAR)
            # Draw effective range circles if mortar is set (true alpha)
            if self.mortar:
                from PIL import ImageDraw
                overlay_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay_img)
                mx, my = int(self.mortar[0] * self.display_scale), int(self.mortar[1] * self.display_scale)
                # Max range circle (2300m, blue)
                r_px = int(2300 / self.m_per_px * self.display_scale)
                draw.ellipse([mx - r_px, my - r_px, mx + r_px, my + r_px], fill=(0, 0, 255, int(255 * 0.15)))
                # Min range circle (748m, red/orange)
                min_r_px = int(748 / self.m_per_px * self.display_scale)
                draw.ellipse([mx - min_r_px, my - min_r_px, mx + min_r_px, my + min_r_px], fill=(255, 128, 0, int(255 * 0.15)))
                # Dispersion circle at target (if available)
                if self.mortar and self.target:
                    dx_m = (self.target[0] - self.mortar[0]) * self.m_per_px
                    dy_m = (self.target[1] - self.mortar[1]) * self.m_per_px
                    dist_m = math.hypot(dx_m, dy_m)
                    mortar_z = self.get_elevation(*self.mortar)
                    target_z = self.get_elevation(*self.target)
                    dz = target_z - mortar_z
                    dz_correction_factor = 1.5
                    ring, entry = self.get_best_ring(dist_m, dz, dz_correction_factor)
                    if ring is not None and self.target:
                        disp_m = dispersion_radius.get(ring, 0)
                        tx, ty = int(self.target[0] * self.display_scale), int(self.target[1] * self.display_scale)
                        disp_px = int(disp_m / self.m_per_px * self.display_scale)
                        draw.ellipse([tx - disp_px, ty - disp_px, tx + disp_px, ty + disp_px], fill=(255,255,255,60))
                # Composite overlay onto map
                display_img = display_img.convert("RGBA")
                display_img = Image.alpha_composite(display_img, overlay_img)
            # Draw layer entities overlay (composite onto display_img)
            layer_overlay = self.draw_layer_entities()
            if layer_overlay is not None:
                display_img = display_img.convert("RGBA")
                display_img = Image.alpha_composite(display_img, layer_overlay)
            self.tk_img = ImageTk.PhotoImage(display_img)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
            self.canvas.config(scrollregion=(0, 0, w, h))
        self.draw_grid()
        # Draw mortar/target/line as before
        if self.mortar:
            mx, my = int(self.mortar[0] * self.display_scale), int(self.mortar[1] * self.display_scale)
            self.canvas.create_oval(mx - 5, my - 5, mx + 5, my + 5, fill="red", tags="marker")
        if self.target:
            tx, ty = int(self.target[0] * self.display_scale), int(self.target[1] * self.display_scale)
            self.canvas.create_oval(tx - 5, ty - 5, tx + 5, ty + 5, fill="blue", tags="marker")
        if self.mortar and self.target:
            mx, my = int(self.mortar[0] * self.display_scale), int(self.mortar[1] * self.display_scale)
            tx, ty = int(self.target[0] * self.display_scale), int(self.target[1] * self.display_scale)
            self.canvas.create_line(mx, my, tx, ty, fill="white", width=2, tags="marker")
        # Always show calculation box
        self.calculate()
        # Always show input options box
        self.draw_input_options()

    def draw_input_options(self):
        self.canvas.delete("inputbox")
        # Dynamically size the input box to fit widgets
        widgets = [self.entry_map_width, self.entry_map_height, self.entry_gps,
                   self.btn_load_map, self.btn_load_heightmap, self.btn_set_gps, self.btn_load_layer, self.btn_load_project, self.btn_reset]
        self.root.update_idletasks()
        max_w = 0
        total_h = 20
        for wdg in widgets:
            w = wdg.winfo_reqwidth()
            h = wdg.winfo_reqheight()
            if w > max_w:
                max_w = w
            total_h += h + 5
        box_w = max(320, max_w + 200)
        box_h = max(120, total_h)
        # Anchor to top-left of window (not affected by pan/zoom)
        box_x = 10
        box_y = 10
        self.canvas.create_rectangle(box_x, box_y, box_x+box_w, box_y+box_h, fill="#222", outline="#fff", tags="inputbox")
        self.canvas.create_text(box_x+10, box_y+10, anchor="nw", text="Map Width (m):", fill="white", font=("Consolas", 10), tags="inputbox")
        self.canvas.create_window(box_x+110, box_y+10, anchor="nw", window=self.entry_map_width, tags="inputbox")
        self.canvas.create_text(box_x+10, box_y+35, anchor="nw", text="Map Height (m):", fill="white", font=("Consolas", 10), tags="inputbox")
        self.canvas.create_window(box_x+110, box_y+35, anchor="nw", window=self.entry_map_height, tags="inputbox")
        self.canvas.create_window(box_x+190, box_y+10, anchor="nw", window=self.btn_load_map, tags="inputbox")
        self.canvas.create_window(box_x+190, box_y+35, anchor="nw", window=self.btn_load_heightmap, tags="inputbox")
        self.canvas.create_text(box_x+10, box_y+60, anchor="nw", text="GPS Coords:", fill="white", font=("Consolas", 10), tags="inputbox")
        self.canvas.create_window(box_x+110, box_y+60, anchor="nw", window=self.entry_gps, tags="inputbox")
        self.canvas.create_window(box_x+190, box_y+60, anchor="nw", window=self.btn_set_gps, tags="inputbox")
        self.canvas.create_window(box_x+190, box_y+85, anchor="nw", window=self.btn_load_layer, tags="inputbox")
        self.canvas.create_window(box_x+10, box_y+110, anchor="nw", window=self.btn_load_project, tags="inputbox")
        self.canvas.create_window(box_x+120, box_y+110, anchor="nw", window=self.btn_reset, tags="inputbox")

    def calculate(self):
        if not (self.mortar and self.target):
            return
        dx_m = (self.target[0] - self.mortar[0]) * self.m_per_px
        dy_m = (self.target[1] - self.mortar[1]) * self.m_per_px
        dist_m = math.hypot(dx_m, dy_m)
        # Use 6000 mils for azimuth (Russian/Arma standard)
        azimuth_deg = (math.degrees(math.atan2(dx_m, -dy_m)) + 360) % 360
        azimuth_mil = (azimuth_deg / 360) * 6000
        mortar_z = self.get_elevation(*self.mortar)
        target_z = self.get_elevation(*self.target)
        dz = target_z - mortar_z
        dz_correction_factor = 1.5  # mils per meter
        ring, entry = self.get_best_ring(dist_m, dz, dz_correction_factor)
        if ring is None or entry is None:
            calc_text = f"No valid firing solution found above 748 mils.\nMax table range: 2300m."
        else:
            a, b = entry
            ratio = (dist_m - a["RANGE (M)"]) / (b["RANGE (M)"] - a["RANGE (M)"])
            elev = a["ELEV (MIL)"] + ratio * (b["ELEV (MIL)"] - a["ELEV (MIL)"])
            tof = a["TIME OF FLIGHT (SEC)"] + ratio * (b["TIME OF FLIGHT (SEC)"] - a["TIME OF FLIGHT (SEC)"])
            corrected_elev = elev + dz * dz_correction_factor
            if corrected_elev < 100 or corrected_elev > 1600:
                calc_text = (
                    f"Elevation out of range: {corrected_elev:.0f} mils\n"
                    f"Try a different ring or check elevation difference.\n"
                    f"Raw elev: {elev:.0f} mils\n"
                )
            else:
                calc_text = (
                    f"RANGE (M): {dist_m:.0f}\n"
                    f"AZIMUTH: {azimuth_mil:.0f} mils\n"
                    f"CHARGE RING: {ring}\n"
                    f"ELEV (MIL): {corrected_elev:.0f}\n"
                    f"TIME OF FLIGHT (SEC): {tof:.2f}\n"
                    f"Mortar Elevation: {mortar_z:.1f} m\n"
                    f"Target Elevation: {target_z:.1f} m\n"
                    f"Elevation Delta: {dz:.1f} m\n"
                    f"dz Correction: {dz * dz_correction_factor:+.1f} mils\n"
                )
        # Dynamically size the calculation box to fit text
        self.canvas.delete("calcbox")
        win_w = self.canvas.winfo_width()
        lines = calc_text.split("\n")
        font = ("Consolas", 10)
        self.root.update_idletasks()
        # Estimate width/height
        text_w = max([self.canvas.create_text(0, 0, text=line, font=font, anchor="nw", tags="calcbox", state="hidden") or self.canvas.bbox("calcbox")[2] for line in lines if line])
        text_h = 20 * len(lines)
        box_w = min(max(300, text_w + 40), win_w - 20)
        box_h = max(60, text_h + 20)
        # Anchor to top-right of window (not affected by pan/zoom)
        box_x = win_w - box_w - 10
        box_y = 10
        self.canvas.create_rectangle(box_x, box_y, box_x+box_w, box_y+box_h, fill="#222", outline="#fff", tags="calcbox")
        self.canvas.create_text(box_x+box_w/2, box_y+10, anchor="n", text=calc_text, fill="white", font=font, tags="calcbox")
        # Also clear the output textbox
        self.output.delete(1.0, tk.END)
        self.output.insert(tk.END, calc_text + "\n")

    def get_elevation(self, px, py):
        # Return elevation from heightmap if available, else 0
        if self.heightmap_image is not None and self.map_width_px and self.map_height_px:
            # Map px,py (map image) to hx,hy (heightmap image)
            hx = int(px / self.map_width_px * self.heightmap_image.width)
            hy = int(py / self.map_height_px * self.heightmap_image.height)
            hx = min(max(hx, 0), self.heightmap_image.width - 1)
            hy = min(max(hy, 0), self.heightmap_image.height - 1)
            return (self.heightmap_image.getpixel((hx, hy)) / 255.0) * self.max_elevation_m
        return 0.0

    def get_best_ring(self, dist_m, dz, dz_correction_factor=1.5):
        # Find the best charge ring and ballistic table entry for the given range and elevation delta
        best_ring = None
        best_entry = None
        for ring, data in ring_data.items():
            for i in range(len(data) - 1):
                a, b = data[i], data[i + 1]
                if a["RANGE (M)"] <= dist_m <= b["RANGE (M)"]:
                    # Interpolate elevation
                    ratio = (dist_m - a["RANGE (M)"]) / (b["RANGE (M)"] - a["RANGE (M)"])
                    elev = a["ELEV (MIL)"] + ratio * (b["ELEV (MIL)"] - a["ELEV (MIL)"])
                    corrected_elev = elev + dz * dz_correction_factor
                    # Only accept solutions above 748 mils (min range)
                    if corrected_elev >= 748:
                        if best_ring is None or ring < best_ring:
                            best_ring = ring
                            best_entry = (a, b)
        return best_ring, best_entry

    def load_project_folder(self):
        folder = filedialog.askdirectory(title="Select Arma Project Folder")
        if not folder:
            return
        # Load map.png
        map_path = os.path.join(folder, "map.png")
        if os.path.exists(map_path):
            img = Image.open(map_path)
            self.original_img = img
            self.map_width_px, self.map_height_px = img.width, img.height
            max_dim = max(self.map_width_px, self.map_height_px)
            if max_dim > 1024:
                self.display_scale = 1024 / max_dim
            else:
                self.display_scale = 1.0
            display_img = img.resize(
                (int(img.width * self.display_scale), int(img.height * self.display_scale)),
                resample=Image.BILINEAR
            )
            self.tk_img = ImageTk.PhotoImage(display_img)
            self.canvas.config(width=display_img.width, height=display_img.height)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_img)
            mpp_x = self.map_width_m.get() / self.map_width_px
            mpp_y = self.map_height_m.get() / self.map_height_px
            self.m_per_px = (mpp_x + mpp_y) / 2
            self.draw_grid()
        # Load heightmap.png
        heightmap_path = os.path.join(folder, "heightmap.png")
        if os.path.exists(heightmap_path):
            img = Image.open(heightmap_path).convert("L")
            self.heightmap_image = img
        # Load and parse all .layer files
        self.layer_entities = []
        for fname in os.listdir(folder):
            if fname.lower().endswith(".layer"):
                layer_path = os.path.join(folder, fname)
                self.layer_entities.extend(self.parse_layer_file(layer_path))
        self.update_view()

if __name__ == "__main__":
    root = tk.Tk()
    app = MortarApp(root)
    root.mainloop()
