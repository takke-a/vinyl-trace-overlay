#!/usr/bin/env python3
"""
Vinyl Trace Overlay
Reference image overlay tool for vinyl group creation
"""

import sys
import os
import ctypes
import tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from PIL import Image, ImageTk, ImageFilter, ImageOps, ImageEnhance, ImageDraw

IS_WINDOWS = sys.platform == "win32"


class VinylTraceOverlay:
    TITLE = "Vinyl Trace Overlay"

    # Discord-inspired dark color palette
    C = {
        "bg_darkest":   "#111214",
        "bg_dark":      "#1e1f22",
        "bg_panel":     "#2b2d31",
        "bg_input":     "#1a1b1e",
        "bg_btn":       "#3d4045",
        "bg_btn_hover": "#4e5058",
        "accent":       "#5865f2",
        "accent_dim":   "#4752c4",
        "text":         "#f2f3f5",
        "text_muted":   "#949ba4",
        "separator":    "#1a1b1e",
        "success":      "#23a55a",
        "danger":       "#f23f42",
    }

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(self.TITLE)

        # Image state
        self.image_original: Image.Image | None = None
        self.image_display:  Image.Image | None = None
        self.photo: ImageTk.PhotoImage | None = None

        # Pan offset (image position within canvas)
        self.pan_x = 0
        self.pan_y = 0
        self._pan_sx = 0
        self._pan_sy = 0

        # Control state
        self.opacity_var   = tk.IntVar(value=70)
        self.scale_var     = tk.IntVar(value=100)
        self.mirror_h_var  = tk.BooleanVar(value=False)
        self.mirror_v_var  = tk.BooleanVar(value=False)
        self.grid_var      = tk.BooleanVar(value=False)
        self.through_var   = tk.BooleanVar(value=False)
        self.lock_var      = tk.BooleanVar(value=False)
        self.mode_var      = tk.StringVar(value="Normal")
        self.grid_size_var = tk.IntVar(value=50)
        self.grid_color    = "#5865f2"
        self.controls_visible = True

        # Fullscreen state
        self.is_fullscreen = False
        self._saved_geom   = ""

        # Window drag / resize
        self._dx = self._dy = 0
        self._rx = self._ry = self._rw = self._rh = 0

        self._init_window()
        self._build_ui()
        self._bind_keys()
        self.root.mainloop()

    def c(self, key: str) -> str:
        return self.C[key]

    # ═══════════════════════════════════════════════════════════════
    # Window Initialization
    # ═══════════════════════════════════════════════════════════════

    def _init_window(self):
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.70)
        self.root.configure(bg=self.c("bg_dark"))
        self.root.minsize(500, 360)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"720x580+{(sw - 720) // 2}+{(sh - 580) // 2}")

    # ═══════════════════════════════════════════════════════════════
    # UI Construction
    # ═══════════════════════════════════════════════════════════════

    def _build_ui(self):
        # Accent top line
        tk.Frame(self.root, bg=self.c("accent"), height=2).pack(fill="x")

        self._build_titlebar()

        # Control section (can be hidden with F1)
        self.ctrl_section = tk.Frame(self.root, bg=self.c("bg_panel"))
        self.ctrl_section.pack(fill="x")
        self.ctrl_frame = tk.Frame(self.ctrl_section, bg=self.c("bg_panel"))
        self.ctrl_frame.pack(fill="x", padx=14, pady=10)
        self._build_controls()
        tk.Frame(self.ctrl_section, bg=self.c("separator"), height=1).pack(fill="x")

        self._build_canvas()
        self._build_statusbar()
        self._build_resize_grip()

    # ── Title Bar ──────────────────────────────────────────────────

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=self.c("bg_input"), height=36)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self.titlebar = bar

        # Accent dot
        dot = tk.Frame(bar, bg=self.c("accent"), width=8, height=8)
        dot.place(x=14, rely=0.5, anchor="w")
        for w in [dot]:
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        title_lbl = tk.Label(
            bar, text="Vinyl Trace Overlay",
            bg=self.c("bg_input"), fg=self.c("text"),
            font=("Segoe UI", 10, "bold")
        )
        title_lbl.pack(side="left", padx=(28, 0))
        title_lbl.bind("<Button-1>", self._drag_start)
        title_lbl.bind("<B1-Motion>", self._drag_move)

        bar.bind("<Button-1>", self._drag_start)
        bar.bind("<B1-Motion>", self._drag_move)

        # Window control buttons
        for txt, cmd, hover_col in [
            ("  x  ",  self.root.quit,          self.c("danger")),
            ("  —  ",  self._minimize,           self.c("bg_btn_hover")),
            ("  [ ] ", self._toggle_fullscreen,  self.c("bg_btn_hover")),
        ]:
            lbl = tk.Label(
                bar, text=txt,
                bg=self.c("bg_input"), fg=self.c("text_muted"),
                font=("Segoe UI", 9), cursor="hand2", padx=2
            )
            lbl.pack(side="right")
            _cmd = cmd
            _hc  = hover_col
            lbl.bind("<Enter>",    lambda e, w=lbl, hc=_hc: w.configure(bg=hc, fg=self.c("text")))
            lbl.bind("<Leave>",    lambda e, w=lbl: w.configure(bg=self.c("bg_input"), fg=self.c("text_muted")))
            lbl.bind("<Button-1>", lambda e, c=_cmd: c())

        tk.Label(
            bar, text="v2.0",
            bg=self.c("bg_input"), fg=self.c("text_muted"),
            font=("Segoe UI", 8)
        ).pack(side="right", padx=10)

    # ── Controls ───────────────────────────────────────────────────

    def _build_controls(self):
        # ── Row 1: Open + Mode ─────────────────────────────────
        r1 = tk.Frame(self.ctrl_frame, bg=self.c("bg_panel"))
        r1.pack(fill="x", pady=(0, 10))

        self._accent_btn(r1, "Open Image", self.open_image).pack(side="left")

        sep = tk.Frame(r1, bg=self.c("bg_panel"), width=20)
        sep.pack(side="left")

        tk.Label(
            r1, text="Mode",
            bg=self.c("bg_panel"), fg=self.c("text_muted"),
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 6))

        self._style_combobox()
        mode_cb = ttk.Combobox(
            r1, textvariable=self.mode_var, width=15, state="readonly",
            values=["Normal", "Edge Detect", "Grayscale",
                    "Invert", "High Contrast", "Soft Glow"]
        )
        mode_cb.pack(side="left")
        mode_cb.bind("<<ComboboxSelected>>", lambda _: self.update_display())

        # ── Row 2: Sliders ─────────────────────────────────────
        r2 = tk.Frame(self.ctrl_frame, bg=self.c("bg_panel"))
        r2.pack(fill="x", pady=(0, 10))

        tk.Label(
            r2, text="Opacity", width=7, anchor="w",
            bg=self.c("bg_panel"), fg=self.c("text_muted"),
            font=("Segoe UI", 9)
        ).pack(side="left")

        tk.Scale(
            r2, variable=self.opacity_var, from_=10, to=100, orient="h",
            length=130, command=self._on_opacity, **self._scale_kw()
        ).pack(side="left")

        self.opacity_lbl = tk.Label(
            r2, text="70%", width=5, anchor="w",
            bg=self.c("bg_panel"), fg=self.c("text"),
            font=("Segoe UI", 9, "bold")
        )
        self.opacity_lbl.pack(side="left", padx=(2, 20))

        tk.Label(
            r2, text="Scale", width=5, anchor="w",
            bg=self.c("bg_panel"), fg=self.c("text_muted"),
            font=("Segoe UI", 9)
        ).pack(side="left")

        tk.Scale(
            r2, variable=self.scale_var, from_=5, to=400, orient="h",
            length=130, command=self._on_scale, **self._scale_kw()
        ).pack(side="left")

        self.scale_lbl = tk.Label(
            r2, text="100%", width=6, anchor="w",
            bg=self.c("bg_panel"), fg=self.c("text"),
            font=("Segoe UI", 9, "bold")
        )
        self.scale_lbl.pack(side="left", padx=(2, 16))

        self._flat_btn(r2, "Fit",  self._fit_image).pack(side="left", padx=(0, 4))
        self._flat_btn(r2, "1:1",  self._reset_scale).pack(side="left", padx=(0, 4))
        self._flat_btn(r2, "Reset View", self._reset_view).pack(side="left")

        # ── Row 3: Toggle buttons ──────────────────────────────
        r3 = tk.Frame(self.ctrl_frame, bg=self.c("bg_panel"))
        r3.pack(fill="x", pady=(0, 10))

        self.btn_mh = self._toggle_btn(r3, "Flip H",       self._toggle_mirror_h)
        self.btn_mv = self._toggle_btn(r3, "Flip V",       self._toggle_mirror_v)
        self.btn_gr = self._toggle_btn(r3, "Grid  [F3]",   self._toggle_grid)
        self.btn_ct = self._toggle_btn(r3, "Click-Thru  [F2]", self._toggle_through)
        self.btn_lk = self._toggle_btn(r3, "Lock Pos",     self._toggle_lock)

        # ── Row 4: Grid settings ───────────────────────────────
        r4 = tk.Frame(self.ctrl_frame, bg=self.c("bg_panel"))
        r4.pack(fill="x")

        tk.Label(
            r4, text="Grid Color",
            bg=self.c("bg_panel"), fg=self.c("text_muted"),
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 6))

        self.grid_color_lbl = tk.Label(
            r4, width=4, bg=self.grid_color,
            cursor="hand2", relief="flat"
        )
        self.grid_color_lbl.pack(side="left", ipady=5, padx=(0, 16))
        self.grid_color_lbl.bind("<Button-1>", lambda _: self._pick_grid_color())

        tk.Label(
            r4, text="Cell Size",
            bg=self.c("bg_panel"), fg=self.c("text_muted"),
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 6))

        spin = tk.Spinbox(
            r4, from_=15, to=300, textvariable=self.grid_size_var, width=4,
            command=self.update_display,
            bg=self.c("bg_input"), fg=self.c("text"),
            insertbackground=self.c("text"),
            buttonbackground=self.c("bg_btn"),
            highlightthickness=1,
            highlightcolor=self.c("accent"),
            highlightbackground=self.c("separator"),
            relief="flat", font=("Segoe UI", 9)
        )
        spin.pack(side="left")
        spin.bind("<Return>", lambda _: self.update_display())

        tk.Label(
            r4, text="px",
            bg=self.c("bg_panel"), fg=self.c("text_muted"),
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(4, 0))

        tk.Label(
            r4, text="Scroll: zoom    Right-drag: pan    F1: toggle UI    F11: fullscreen",
            bg=self.c("bg_panel"), fg=self.c("text_muted"),
            font=("Segoe UI", 8)
        ).pack(side="right")

    # ── Canvas ─────────────────────────────────────────────────────

    def _build_canvas(self):
        self.canvas = tk.Canvas(
            self.root, bg=self.c("bg_darkest"),
            highlightthickness=0,
            cursor="crosshair"
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>",  lambda _: self.update_display())
        self.canvas.bind("<Motion>",     self._on_hover)
        self.canvas.bind("<Button-1>",   self._on_canvas_click)
        self.canvas.bind("<MouseWheel>", self._on_scroll_zoom)
        self.canvas.bind("<Button-4>",   lambda _: self._adjust_scale(5))   # Linux
        self.canvas.bind("<Button-5>",   lambda _: self._adjust_scale(-5))  # Linux
        self.canvas.bind("<Button-3>",   self._pan_start)
        self.canvas.bind("<B3-Motion>",  self._pan_move)
        self.canvas.after(200, self._show_placeholder)

    def _show_placeholder(self):
        cw = self.canvas.winfo_width()  or 360
        ch = self.canvas.winfo_height() or 240
        self.canvas.create_text(
            cw // 2, ch // 2,
            text=(
                "Open an image to start tracing\n\n"
                "Ctrl+O  or  click here\n\n"
                "Scroll to zoom    Right-drag to pan\n"
                "F2: click-through mode    F3: grid"
            ),
            fill=self.c("bg_btn"), font=("Segoe UI", 11),
            justify="center", tags="ph"
        )

    # ── Status Bar ─────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=self.c("bg_input"), height=24)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)

        self.color_swatch = tk.Frame(bar, width=14, height=14, bg="#333333")
        self.color_swatch.pack(side="left", padx=(10, 4), pady=5)

        self.status_var = tk.StringVar(value="No image loaded  —  Ctrl+O to open")
        tk.Label(
            bar, textvariable=self.status_var,
            bg=self.c("bg_input"), fg=self.c("text_muted"),
            font=("Consolas", 8)
        ).pack(side="left")

    # ── Resize Grip ────────────────────────────────────────────────

    def _build_resize_grip(self):
        grip = tk.Frame(
            self.root, width=14, height=14,
            bg=self.c("bg_input"), cursor="size_nw_se"
        )
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<Button-1>",  self._resize_start)
        grip.bind("<B1-Motion>", self._resize_drag)

    # ═══════════════════════════════════════════════════════════════
    # Image Loading
    # ═══════════════════════════════════════════════════════════════

    def open_image(self, *_):
        path = filedialog.askopenfilename(
            title="Select reference image",
            filetypes=[
                ("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self._load_image(path)

    def _load_image(self, path: str):
        try:
            img = Image.open(path).convert("RGBA")
            self.image_original = img
            self.pan_x = 0
            self.pan_y = 0
            name = os.path.basename(path)
            self.status_var.set(f"{name}  |  {img.width} x {img.height} px  |  scroll to zoom  |  right-drag to pan")
            self.canvas.delete("ph")
            self.update_display()
        except Exception as e:
            messagebox.showerror("Error", f"Could not open image:\n{e}")

    # ═══════════════════════════════════════════════════════════════
    # Display Update
    # ═══════════════════════════════════════════════════════════════

    def update_display(self, *_):
        if self.image_original is None:
            return

        img = self._apply_mode(self.image_original.copy(), self.mode_var.get())

        if self.mirror_h_var.get():
            img = ImageOps.mirror(img)
        if self.mirror_v_var.get():
            img = ImageOps.flip(img)

        factor = self.scale_var.get() / 100.0
        tw = max(1, int(img.width  * factor))
        th = max(1, int(img.height * factor))
        img = img.resize((tw, th), Image.LANCZOS)

        if self.grid_var.get():
            img = self._draw_grid(img)

        self.image_display = img
        self.photo = ImageTk.PhotoImage(img)
        self._redraw_canvas()

    def _redraw_canvas(self):
        if self.photo is None:
            return
        cw = self.canvas.winfo_width()  or 1
        ch = self.canvas.winfo_height() or 1
        self.canvas.delete("img")
        self.canvas.create_image(
            cw // 2 + self.pan_x,
            ch // 2 + self.pan_y,
            image=self.photo, anchor="center", tags="img"
        )

    # ── Display Modes ──────────────────────────────────────────────

    def _apply_mode(self, img: Image.Image, mode: str) -> Image.Image:
        if mode == "Edge Detect":
            edges = img.convert("RGB").filter(ImageFilter.FIND_EDGES)
            return ImageEnhance.Brightness(edges).enhance(4.0).convert("RGBA")

        if mode == "Grayscale":
            return ImageOps.grayscale(img.convert("RGB")).convert("RGBA")

        if mode == "Invert":
            r, g, b, a = img.split()
            inv = ImageOps.invert(Image.merge("RGB", (r, g, b)))
            return Image.merge("RGBA", (*inv.split(), a))

        if mode == "High Contrast":
            rgb = img.convert("RGB")
            rgb = ImageEnhance.Contrast(rgb).enhance(3.0)
            rgb = ImageEnhance.Sharpness(rgb).enhance(2.0)
            return rgb.convert("RGBA")

        if mode == "Soft Glow":
            rgb   = img.convert("RGB")
            blur  = rgb.filter(ImageFilter.GaussianBlur(radius=5))
            blend = Image.blend(rgb, blur, 0.45)
            return ImageEnhance.Brightness(blend).enhance(1.25).convert("RGBA")

        return img  # Normal

    # ── Grid (centered on image center) ────────────────────────────

    def _draw_grid(self, img: Image.Image) -> Image.Image:
        out  = img.copy()
        draw = ImageDraw.Draw(out, "RGBA")
        sz   = max(10, self.grid_size_var.get())

        try:
            r = int(self.grid_color[1:3], 16)
            g = int(self.grid_color[3:5], 16)
            b = int(self.grid_color[5:7], 16)
        except Exception:
            r, g, b = 88, 101, 242

        line_col  = (r, g, b, 80)
        cross_col = (r, g, b, 210)
        w, h = out.size
        cx, cy = w // 2, h // 2

        # Vertical grid lines anchored at cx
        x_start = cx % sz
        for x in range(x_start, w, sz):
            draw.line([(x, 0), (x, h)], fill=line_col, width=1)

        # Horizontal grid lines anchored at cy
        y_start = cy % sz
        for y in range(y_start, h, sz):
            draw.line([(0, y), (w, y)], fill=line_col, width=1)

        # Center crosshair (guaranteed to pass through cx, cy)
        draw.line([(cx, 0), (cx, h)], fill=cross_col, width=2)
        draw.line([(0, cy), (w, cy)], fill=cross_col, width=2)

        # Center marker dot
        dot_r = 5
        draw.ellipse(
            [(cx - dot_r, cy - dot_r), (cx + dot_r, cy + dot_r)],
            fill=(r, g, b, 255)
        )

        return out

    # ═══════════════════════════════════════════════════════════════
    # Event Handlers
    # ═══════════════════════════════════════════════════════════════

    def _on_opacity(self, val):
        v = int(val)
        self.root.attributes("-alpha", v / 100)
        self.opacity_lbl.configure(text=f"{v}%")

    def _on_scale(self, val):
        self.scale_lbl.configure(text=f"{int(val)}%")
        self.update_display()

    def _on_hover(self, event):
        if self.image_display is None:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.image_display.size
        ox = cw // 2 + self.pan_x - iw // 2
        oy = ch // 2 + self.pan_y - ih // 2
        px = event.x - ox
        py = event.y - oy
        if 0 <= px < iw and 0 <= py < ih:
            try:
                r, g, b, a = self.image_display.getpixel((px, py))
                hx = f"#{r:02x}{g:02x}{b:02x}"
                self.color_swatch.configure(bg=hx)
                self.status_var.set(
                    f"x:{px:4}  y:{py:4}  |  RGB({r:3},{g:3},{b:3})  |  {hx}  |  alpha:{a}"
                )
            except Exception:
                pass

    def _on_canvas_click(self, _event):
        if self.image_original is None:
            self.open_image()

    def _on_scroll_zoom(self, event):
        self._adjust_scale(10 if event.delta > 0 else -10)

    def _pan_start(self, event):
        self._pan_sx = event.x
        self._pan_sy = event.y

    def _pan_move(self, event):
        self.pan_x += event.x - self._pan_sx
        self.pan_y += event.y - self._pan_sy
        self._pan_sx = event.x
        self._pan_sy = event.y
        self._redraw_canvas()

    # ═══════════════════════════════════════════════════════════════
    # Toggle Actions
    # ═══════════════════════════════════════════════════════════════

    def _toggle_mirror_h(self):
        self.mirror_h_var.set(not self.mirror_h_var.get())
        self._set_toggle(self.btn_mh, self.mirror_h_var.get())
        self.update_display()

    def _toggle_mirror_v(self):
        self.mirror_v_var.set(not self.mirror_v_var.get())
        self._set_toggle(self.btn_mv, self.mirror_v_var.get())
        self.update_display()

    def _toggle_grid(self):
        self.grid_var.set(not self.grid_var.get())
        self._set_toggle(self.btn_gr, self.grid_var.get())
        self.update_display()

    def _toggle_through(self):
        self.through_var.set(not self.through_var.get())
        self._set_toggle(self.btn_ct, self.through_var.get())
        self._apply_click_through()

    def _toggle_lock(self):
        self.lock_var.set(not self.lock_var.get())
        locked = self.lock_var.get()
        self._set_toggle(self.btn_lk, locked)
        self.btn_lk.configure(text="Locked" if locked else "Lock Pos")

    def _toggle_fullscreen(self):
        self.is_fullscreen = not self.is_fullscreen
        if self.is_fullscreen:
            self._saved_geom = self.root.geometry()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
        else:
            if self._saved_geom:
                self.root.geometry(self._saved_geom)

    # ── Click-Through (Windows) ────────────────────────────────────

    def _apply_click_through(self):
        if not IS_WINDOWS:
            if self.through_var.get():
                messagebox.showinfo("Info", "Click-through is Windows only.")
                self.through_var.set(False)
                self._set_toggle(self.btn_ct, False)
            return
        try:
            self.root.update()
            hwnd = ctypes.windll.user32.FindWindowW(None, self.TITLE)
            if not hwnd:
                return
            GWL_EXSTYLE       = -20
            WS_EX_LAYERED     = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            cur = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            if self.through_var.get():
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, cur | WS_EX_LAYERED | WS_EX_TRANSPARENT)
            else:
                ctypes.windll.user32.SetWindowLongW(
                    hwnd, GWL_EXSTYLE, cur & ~WS_EX_TRANSPARENT)
        except Exception as e:
            print(f"[click-through] {e}")

    # ═══════════════════════════════════════════════════════════════
    # Window Drag / Resize
    # ═══════════════════════════════════════════════════════════════

    def _drag_start(self, event):
        self._dx, self._dy = event.x, event.y

    def _drag_move(self, event):
        if self.lock_var.get():
            return
        x = self.root.winfo_x() + (event.x - self._dx)
        y = self.root.winfo_y() + (event.y - self._dy)
        self.root.geometry(f"+{x}+{y}")

    def _resize_start(self, event):
        self._rx, self._ry = event.x_root, event.y_root
        self._rw = self.root.winfo_width()
        self._rh = self.root.winfo_height()

    def _resize_drag(self, event):
        nw = max(500, self._rw + (event.x_root - self._rx))
        nh = max(360, self._rh + (event.y_root - self._ry))
        self.root.geometry(f"{nw}x{nh}")

    def _minimize(self):
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.bind("<Map>", self._on_restore)

    def _on_restore(self, _=None):
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.unbind("<Map>")

    # ═══════════════════════════════════════════════════════════════
    # Utility Actions
    # ═══════════════════════════════════════════════════════════════

    def _fit_image(self):
        if self.image_original is None:
            return
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        iw, ih = self.image_original.size
        if iw > 0 and ih > 0:
            ratio = min(cw / iw, ch / ih) * 100
            self.scale_var.set(int(max(5, min(400, ratio))))
            self.scale_lbl.configure(text=f"{self.scale_var.get()}%")
        self.pan_x = 0
        self.pan_y = 0
        self.update_display()

    def _reset_scale(self):
        self.scale_var.set(100)
        self.scale_lbl.configure(text="100%")
        self.pan_x = 0
        self.pan_y = 0
        self.update_display()

    def _reset_view(self):
        self.pan_x = 0
        self.pan_y = 0
        self._redraw_canvas()

    def _pick_grid_color(self):
        color = colorchooser.askcolor(color=self.grid_color, title="Grid Color")[1]
        if color:
            self.grid_color = color
            self.grid_color_lbl.configure(bg=color)
            if self.grid_var.get():
                self.update_display()

    def _adjust_scale(self, delta: int):
        new_val = max(5, min(400, self.scale_var.get() + delta))
        self.scale_var.set(new_val)
        self.scale_lbl.configure(text=f"{new_val}%")
        self.update_display()

    def _toggle_controls(self):
        self.controls_visible = not self.controls_visible
        if self.controls_visible:
            self.ctrl_section.pack(fill="x", before=self.canvas)
        else:
            self.ctrl_section.pack_forget()

    # ═══════════════════════════════════════════════════════════════
    # Keyboard Shortcuts
    # ═══════════════════════════════════════════════════════════════

    def _bind_keys(self):
        self.root.bind("<Control-o>",     self.open_image)
        self.root.bind("<F1>",            lambda _: self._toggle_controls())
        self.root.bind("<F2>",            lambda _: self._toggle_through())
        self.root.bind("<F3>",            lambda _: self._toggle_grid())
        self.root.bind("<F11>",           lambda _: self._toggle_fullscreen())
        self.root.bind("<Control-equal>", lambda _: self._adjust_scale(10))
        self.root.bind("<Control-plus>",  lambda _: self._adjust_scale(10))
        self.root.bind("<Control-minus>", lambda _: self._adjust_scale(-10))
        self.root.bind("<Escape>",        self._on_escape)

    def _on_escape(self, _=None):
        if self.is_fullscreen:
            self._toggle_fullscreen()
        else:
            self.root.quit()

    # ═══════════════════════════════════════════════════════════════
    # Widget Factories
    # ═══════════════════════════════════════════════════════════════

    def _accent_btn(self, parent, text: str, cmd) -> tk.Label:
        btn = tk.Label(
            parent, text=f"  {text}  ",
            bg=self.c("accent"), fg="white",
            font=("Segoe UI", 9, "bold"),
            cursor="hand2", pady=5
        )
        btn.bind("<Enter>",    lambda _: btn.configure(bg=self.c("accent_dim")))
        btn.bind("<Leave>",    lambda _: btn.configure(bg=self.c("accent")))
        btn.bind("<Button-1>", lambda _: cmd())
        return btn

    def _flat_btn(self, parent, text: str, cmd) -> tk.Label:
        btn = tk.Label(
            parent, text=f"  {text}  ",
            bg=self.c("bg_btn"), fg=self.c("text"),
            font=("Segoe UI", 9),
            cursor="hand2", pady=4
        )
        btn.bind("<Enter>",    lambda _: btn.configure(bg=self.c("bg_btn_hover")))
        btn.bind("<Leave>",    lambda _: btn.configure(bg=self.c("bg_btn")))
        btn.bind("<Button-1>", lambda _: cmd())
        return btn

    def _toggle_btn(self, parent, text: str, cmd) -> tk.Label:
        btn = tk.Label(
            parent, text=f"  {text}  ",
            bg=self.c("bg_btn"), fg=self.c("text_muted"),
            font=("Segoe UI", 9),
            cursor="hand2", pady=4
        )
        btn._active = False
        btn.pack(side="left", padx=(0, 5))

        def _click():
            cmd()

        def _enter(_):
            if not btn._active:
                btn.configure(bg=self.c("bg_btn_hover"))

        def _leave(_):
            if not btn._active:
                btn.configure(bg=self.c("bg_btn"))

        btn.bind("<Enter>",    _enter)
        btn.bind("<Leave>",    _leave)
        btn.bind("<Button-1>", lambda _: _click())
        return btn

    def _set_toggle(self, btn: tk.Label, active: bool):
        btn._active = active
        if active:
            btn.configure(bg=self.c("accent"), fg="white")
        else:
            btn.configure(bg=self.c("bg_btn"), fg=self.c("text_muted"))

    def _scale_kw(self) -> dict:
        return dict(
            bg=self.c("bg_panel"), fg=self.c("text"),
            highlightthickness=0,
            troughcolor=self.c("bg_input"),
            activebackground=self.c("accent"),
            showvalue=False,
            bd=0,
        )

    def _style_combobox(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure(
            "TCombobox",
            fieldbackground=self.c("bg_input"),
            background=self.c("bg_input"),
            foreground=self.c("text"),
            selectbackground=self.c("bg_input"),
            selectforeground=self.c("text"),
            arrowcolor=self.c("text_muted"),
            borderwidth=0,
        )
        s.map(
            "TCombobox",
            fieldbackground=[("readonly", self.c("bg_input"))],
            background=[("readonly", self.c("bg_input"))],
        )


# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    VinylTraceOverlay()
