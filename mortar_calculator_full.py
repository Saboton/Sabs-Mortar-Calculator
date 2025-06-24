import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import math
import os
import re
import csv

# === Load Ballistic Table from CSV ===
def load_ballistic_table_from_csv(csv_path):
    table = []
    with open(csv_path, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            # Parse numeric fields
            try:
                row['Charge Rings'] = int(row['Charge Rings'])
                row['Range (m)'] = int(row['Range (m)'])
                row['Elevation (mil)'] = float(row['Elevation (mil)'])
                row['Time of Flight (sec)'] = float(row['Time of Flight (sec)'])
                row['Dispersion Radius (m)'] = float(row['Dispersion Radius (m)'])
            except Exception:
                continue
            table.append(row)
    return table

# Dispersion radius per ring (meters)
dispersion_radius = {0: 8, 1: 13, 2: 19, 3: 27, 4: 34}

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
        # Ballistics tables for both Russian and NATO
        self.ballistic_tables = {'Russian': [], 'NATO': []}
        self.ring_data = {'Russian': {}, 'NATO': {}}
        self.shell_types = {'Russian': [], 'NATO': []}
        self.selected_shell_type = tk.StringVar()
        self.selected_table = tk.StringVar(value='Russian')
        self.load_all_ballistics()
        self._build_gui()

    def load_all_ballistics(self):
        # Load Russian table
        ru_path = os.path.join(os.path.dirname(__file__), 'rutable.csv')
        nato_path = os.path.join(os.path.dirname(__file__), 'natotable.csv')
        if os.path.exists(ru_path):
            self.ballistic_tables['Russian'] = load_ballistic_table_from_csv(ru_path)
            self.ring_data['Russian'] = {}
            shell_types = set()
            for row in self.ballistic_tables['Russian']:
                shell = row['Shell Type']
                ring = row['Charge Rings']
                shell_types.add(shell)
                self.ring_data['Russian'].setdefault(shell, {})
                self.ring_data['Russian'][shell].setdefault(ring, []).append(row)
            self.shell_types['Russian'] = sorted(shell_types)
        if os.path.exists(nato_path):
            self.ballistic_tables['NATO'] = load_ballistic_table_from_csv(nato_path)
            self.ring_data['NATO'] = {}
            shell_types = set()
            for row in self.ballistic_tables['NATO']:
                shell = row['Shell Type']
                ring = row['Charge Rings']
                shell_types.add(shell)
                self.ring_data['NATO'].setdefault(shell, {})
                self.ring_data['NATO'][shell].setdefault(ring, []).append(row)
            self.shell_types['NATO'] = sorted(shell_types)
        # Set default shell type
        if self.shell_types['Russian']:
            self.selected_shell_type.set(self.shell_types['Russian'][0])

    def get_current_table(self):
        return self.selected_table.get() if self.selected_table.get() in self.ballistic_tables else 'Russian'

    def get_current_shell_types(self):
        table = self.get_current_table()
        return self.shell_types[table]

    def get_current_ring_data(self):
        table = self.get_current_table()
        return self.ring_data[table]

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

        button_style = {'bg': '#222', 'fg': '#0f0', 'activebackground': '#333', 'activeforeground': '#0f0', 'highlightbackground': '#222', 'highlightcolor': '#0f0', 'bd': 1, 'relief': 'raised', 'font': ("Consolas", 10, "bold")}
        entry_style = {'bg': '#181818', 'fg': '#0f0', 'insertbackground': '#0f0', 'highlightbackground': '#222', 'highlightcolor': '#0f0', 'bd': 1, 'relief': 'sunken', 'font': ("Consolas", 10)}

        self.entry_map_width = tk.Entry(self.canvas, textvariable=self.map_width_m, width=6, **entry_style)
        self.entry_map_height = tk.Entry(self.canvas, textvariable=self.map_height_m, width=6, **entry_style)
        self.entry_gps = tk.Entry(self.canvas, textvariable=self.coord_var, width=12, **entry_style)
        self.btn_load_map = tk.Button(self.canvas, text="Load Map", command=self.load_map, width=10, **button_style)
        self.btn_load_heightmap = tk.Button(self.canvas, text="Load Heightmap", command=self.load_heightmap, width=13, **button_style)
        self.btn_set_gps = tk.Button(self.canvas, text="Set Mortar From GPS", command=self.set_mortar_from_coords, width=18, **button_style)
        self.btn_load_project = tk.Button(self.canvas, text="Load Project Folder", command=self.load_project_folder, width=20, **button_style)
        self.btn_reset = tk.Button(self.canvas, text="Reset", command=self.reset_positions, width=10, **button_style)

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
                # Get min/max range for current shell
                table = self.get_current_table()
                shell = self.selected_shell_type.get() if self.selected_shell_type.get() else (self.shell_types[table][0] if self.shell_types[table] else "HE")
                shell_rows = [row for ring_rows in self.ring_data[table].get(shell, {}).values() for row in ring_rows]
                if shell_rows:
                    min_range = min(row["Range (m)"] for row in shell_rows)
                    max_range = max(row["Range (m)"] for row in shell_rows)
                else:
                    min_range = 748
                    max_range = 2300
                # Max range circle (blue)
                r_px = int(max_range / self.m_per_px * self.display_scale)
                draw.ellipse([mx - r_px, my - r_px, mx + r_px, my + r_px], fill=(0, 0, 255, int(255 * 0.15)))
                # Min range circle (red/orange)
                min_r_px = int(min_range / self.m_per_px * self.display_scale)
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
                    if ring is not None and self.target and entry is not None:
                        a, b = entry
                        ratio = (dist_m - a["Range (m)"]) / (b["Range (m)"] - a["Range (m)"])
                        disp_a = a["Dispersion Radius (m)"]
                        disp_b = b["Dispersion Radius (m)"]
                        disp_m = disp_a + ratio * (disp_b - disp_a)
                        tx, ty = int(self.target[0] * self.display_scale), int(self.target[1] * self.display_scale)
                        disp_px = int(disp_m / self.m_per_px * self.display_scale)
                        draw.ellipse([tx - disp_px, ty - disp_px, tx + disp_px, ty + disp_px], fill=(255,255,255,60))
                # Composite overlay onto map
                display_img = display_img.convert("RGBA")
                display_img = Image.alpha_composite(display_img, overlay_img)
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
        widgets = [self.entry_map_width, self.entry_map_height, self.entry_gps,
                   self.btn_load_map, self.btn_load_heightmap, self.btn_set_gps, self.btn_load_project, self.btn_reset]
        # Add table (faction) dropdown
        if not hasattr(self, 'table_dropdown'):
            self.table_dropdown = tk.OptionMenu(self.canvas, self.selected_table, 'Russian', 'NATO', command=self.on_table_change)
            self.table_dropdown.config(bg='#222', fg='#0f0', activebackground='#333', activeforeground='#0f0', highlightbackground='#222', highlightcolor='#0f0', bd=1, relief='raised', font=("Consolas", 10, "bold"))
        widgets.append(self.table_dropdown)
        # Add shell type dropdown
        shell_types = self.get_current_shell_types()
        if shell_types:
            if not hasattr(self, 'shell_dropdown'):
                self.shell_dropdown = tk.OptionMenu(self.canvas, self.selected_shell_type, *shell_types, command=lambda _: self.update_view())
                self.shell_dropdown.config(bg='#222', fg='#0f0', activebackground='#333', activeforeground='#0f0', highlightbackground='#222', highlightcolor='#0f0', bd=1, relief='raised', font=("Consolas", 10, "bold"))
            else:
                menu = self.shell_dropdown['menu']
                menu.delete(0, 'end')
                for s in shell_types:
                    menu.add_command(label=s, command=tk._setit(self.selected_shell_type, s, lambda _: self.update_view()))
            widgets.append(self.shell_dropdown)
        self.root.update_idletasks()
        max_w = 0
        total_h = 20
        for wdg in widgets:
            w = wdg.winfo_reqwidth()
            h = wdg.winfo_reqheight()
            if w > max_w:
                max_w = w
            total_h += h + 10  # Add more vertical padding
        box_w = max(320, max_w + 200)
        box_h = max(120, total_h)
        box_x = 10
        box_y = 10
        self.canvas.create_rectangle(box_x, box_y, box_x+box_w, box_y+box_h, fill="#222", outline="#fff", tags="inputbox")
        y_offset = box_y + 10
        self.canvas.create_text(box_x+10, y_offset, anchor="nw", text="Map Width (m):", fill="white", font=("Consolas", 10), tags="inputbox")
        self.canvas.create_window(box_x+110, y_offset, anchor="nw", window=self.entry_map_width, tags="inputbox")
        y_offset += self.entry_map_width.winfo_reqheight() + 10
        self.canvas.create_text(box_x+10, y_offset, anchor="nw", text="Map Height (m):", fill="white", font=("Consolas", 10), tags="inputbox")
        self.canvas.create_window(box_x+110, y_offset, anchor="nw", window=self.entry_map_height, tags="inputbox")
        y_offset += self.entry_map_height.winfo_reqheight() + 10
        self.canvas.create_window(box_x+190, box_y+10, anchor="nw", window=self.btn_load_map, tags="inputbox")
        self.canvas.create_window(box_x+190, y_offset, anchor="nw", window=self.btn_load_heightmap, tags="inputbox")
        y_offset += self.btn_load_heightmap.winfo_reqheight() + 10
        self.canvas.create_text(box_x+10, y_offset, anchor="nw", text="GPS Coords:", fill="white", font=("Consolas", 10), tags="inputbox")
        self.canvas.create_window(box_x+110, y_offset, anchor="nw", window=self.entry_gps, tags="inputbox")
        self.canvas.create_window(box_x+190, y_offset, anchor="nw", window=self.btn_set_gps, tags="inputbox")
        y_offset += self.entry_gps.winfo_reqheight() + 10
        self.canvas.create_window(box_x+190, y_offset, anchor="nw", window=self.btn_load_project, tags="inputbox")
        y_offset += self.btn_load_project.winfo_reqheight() + 10
        self.canvas.create_window(box_x+10, y_offset, anchor="nw", window=self.btn_reset, tags="inputbox")
        y_offset += self.btn_reset.winfo_reqheight() + 10
        self.canvas.create_text(box_x+10, y_offset, anchor="nw", text="Faction:", fill="white", font=("Consolas", 10), tags="inputbox")
        self.canvas.create_window(box_x+110, y_offset, anchor="nw", window=self.table_dropdown, tags="inputbox")
        y_offset += self.table_dropdown.winfo_reqheight() + 10
        if shell_types:
            self.canvas.create_text(box_x+10, y_offset, anchor="nw", text="Shell Type:", fill="white", font=("Consolas", 10), tags="inputbox")
            self.canvas.create_window(box_x+110, y_offset, anchor="nw", window=self.shell_dropdown, tags="inputbox")

    def on_table_change(self, *_):
        # Update shell dropdown when table/faction changes
        shell_types = self.get_current_shell_types()
        if shell_types:
            self.selected_shell_type.set(shell_types[0])
        self.update_view()

    def calculate(self):
        if not (self.mortar and self.target):
            return
        dx_m = (self.target[0] - self.mortar[0]) * self.m_per_px
        dy_m = (self.target[1] - self.mortar[1]) * self.m_per_px
        dist_m = math.hypot(dx_m, dy_m)
        table = self.get_current_table()
        mils_per_circle = 6400 if table == 'NATO' else 6000
        azimuth_deg = (math.degrees(math.atan2(dx_m, -dy_m)) + 360) % 360
        azimuth_mil = (azimuth_deg / 360) * mils_per_circle
        mortar_z = self.get_elevation(*self.mortar)
        target_z = self.get_elevation(*self.target)
        dz = target_z - mortar_z
        dz_correction_factor = 1.5
        ring, entry = self.get_best_ring(dist_m, dz, dz_correction_factor)
        shell = self.selected_shell_type.get() if self.selected_shell_type.get() else (self.get_current_shell_types()[0] if self.get_current_shell_types() else "HE")
        shell_rows = [row for ring_rows in self.get_current_ring_data().get(shell, {}).values() for row in ring_rows]
        if shell_rows:
            min_range = min(row["Range (m)"] for row in shell_rows)
            max_range = max(row["Range (m)"] for row in shell_rows)
            min_elev = min(row["Elevation (mil)"] for row in shell_rows)
        else:
            min_range = 748
            max_range = 2300
            min_elev = 748
        if ring is None or entry is None:
            calc_text = f"No valid firing solution found above {min_elev:.0f} mils.\nMax table range: {max_range:.0f}m."
        else:
            a, b = entry
            ratio = (dist_m - a["Range (m)"]) / (b["Range (m)"] - a["Range (m)"])
            elev = a["Elevation (mil)"] + ratio * (b["Elevation (mil)"] - a["Elevation (mil)"])
            tof = a["Time of Flight (sec)"] + ratio * (b["Time of Flight (sec)"] - a["Time of Flight (sec)"])
            corrected_elev = elev + dz * dz_correction_factor
            disp_a = a["Dispersion Radius (m)"]
            disp_b = b["Dispersion Radius (m)"]
            disp_m = disp_a + ratio * (disp_b - disp_a)
            if corrected_elev < 100 or corrected_elev > 1600:
                calc_text = (
                    f"Elevation out of range: {corrected_elev:.0f} mils\n"
                    f"Try a different ring or check elevation difference.\n"
                    f"Raw elev: {elev:.0f} mils\n"
                )
            else:
                calc_text = (
                    f"FACTION: {table}\n"
                    f"SHELL: {shell}\n"
                    f"RANGE (M): {dist_m:.0f}\n"
                    f"AZIMUTH: {azimuth_mil:.0f} mils\n"
                    f"CHARGE RING: {ring}\n"
                    f"ELEV (MIL): {corrected_elev:.0f}\n"
                    f"TIME OF FLIGHT (SEC): {tof:.2f}\n"
                    f"Dispersion Radius: {disp_m:.1f} m\n"
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
        table = self.get_current_table()
        shell = self.selected_shell_type.get() if self.selected_shell_type.get() else (self.shell_types[table][0] if self.shell_types[table] else "HE")
        best_ring = None
        best_entry = None
        for ring, data in self.ring_data[table].get(shell, {}).items():
            for i in range(len(data) - 1):
                a, b = data[i], data[i + 1]
                if a["Range (m)"] <= dist_m <= b["Range (m)"]:
                    ratio = (dist_m - a["Range (m)"]) / (b["Range (m)"] - a["Range (m)"])
                    elev = a["Elevation (mil)"] + ratio * (b["Elevation (mil)"] - a["Elevation (mil)"])
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
        self.update_view()

if __name__ == "__main__":
    root = tk.Tk()
    app = MortarApp(root)
    root.mainloop()
