#!/usr/bin/env python3
"""Vinyl Trace Overlay  v3.2"""

import sys, os, ctypes, tkinter as tk
from tkinter import ttk, filedialog, colorchooser, messagebox
from PIL import Image, ImageTk, ImageFilter, ImageOps, ImageEnhance, ImageDraw

IS_WINDOWS = sys.platform == "win32"
MIN_W, MIN_H = 500, 380

# DPI awareness — must be set before Tk is created to prevent Windows from
# upscaling the window, which causes blurry rendering on HiDPI displays.
if IS_WINDOWS:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────
# Custom Canvas Slider
# ─────────────────────────────────────────────────────────────────

class ModernSlider(tk.Canvas):
    TRACK_H = 3
    THUMB_R = 7

    def __init__(self, parent, from_=0, to=100, variable=None,
                 command=None, width=180,
                 col_track="#1a1b1e", col_fill="#5865f2", col_thumb="#ffffff",
                 **kw):
        h = (self.THUMB_R + 3) * 2
        super().__init__(parent, width=width, height=h,
                         bd=0, highlightthickness=0,
                         bg=parent.cget("bg"), **kw)
        self._lo  = float(from_)
        self._hi  = float(to)
        self._var = variable or tk.DoubleVar(value=from_)
        self._cmd = command
        self._ct  = col_track
        self._cf  = col_fill
        self._cth = col_thumb
        self._dragging = False

        self.bind("<Configure>",       lambda _: self._draw())
        self.bind("<Button-1>",        self._press)
        self.bind("<B1-Motion>",       self._drag)
        self.bind("<ButtonRelease-1>", lambda _: setattr(self, "_dragging", False))
        self._var.trace_add("write",   lambda *_: self._draw())

    def _draw(self, *_):
        self.delete("all")
        W   = self.winfo_width() or int(self["width"])
        H   = self.winfo_height()
        cy  = H // 2
        pad = self.THUMB_R + 3
        self.create_line(pad, cy, W - pad, cy,
                         fill=self._ct, width=self.TRACK_H, capstyle="round")
        pct = max(0.0, min(1.0,
              (self._var.get() - self._lo) / max(1, self._hi - self._lo)))
        tx  = pad + pct * (W - 2 * pad)
        if tx > pad:
            self.create_line(pad, cy, tx, cy,
                             fill=self._cf, width=self.TRACK_H, capstyle="round")
        r = self.THUMB_R
        self.create_oval(tx - r, cy - r, tx + r, cy + r,
                         fill=self._cth, outline="")

    def _press(self, e): self._dragging = True;  self._set(e.x)
    def _drag(self, e):
        if self._dragging: self._set(e.x)

    def _set(self, x):
        W   = self.winfo_width()
        pad = self.THUMB_R + 3
        pct = max(0.0, min(1.0, (x - pad) / max(1, W - 2 * pad)))
        v   = self._lo + pct * (self._hi - self._lo)
        self._var.set(v)
        if self._cmd: self._cmd(v)

    def get(self): return self._var.get()
    def set(self, v): self._var.set(v)


# ─────────────────────────────────────────────────────────────────
# Main Application
# ─────────────────────────────────────────────────────────────────

class VinylTraceOverlay:
    TITLE = "Vinyl Trace Overlay"

    C = {
        "bg_darkest":   "#111214",
        "bg_dark":      "#1e1f22",
        "bg_panel":     "#2b2d31",
        "bg_input":     "#1a1b1e",
        "bg_btn":       "#3d4045",
        "bg_btn_hover": "#4e5058",
        "titlebar":     "#111214",
        "accent":       "#5865f2",
        "accent_dim":   "#4752c4",
        "text":         "#f2f3f5",
        "text_muted":   "#949ba4",
        "separator":    "#232428",
        "danger":       "#c42b1c",
        "fh6_bg":       "#d4d5cf",
    }

    LAYER_MAX = 3000

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(self.TITLE)
        self.root.withdraw()  # スタイル適用前に非表示にしてフラッシュを防ぐ

        self.image_original: Image.Image | None = None
        self.image_display:  Image.Image | None = None
        self.photo: ImageTk.PhotoImage  | None  = None
        self.pan_x = self.pan_y = 0
        self._psx  = self._psy  = 0

        self.opacity_var    = tk.DoubleVar(value=70)
        self.scale_var      = tk.DoubleVar(value=100)
        self.mirror_h_var   = tk.BooleanVar(value=False)
        self.mirror_v_var   = tk.BooleanVar(value=False)
        self.grid_var       = tk.BooleanVar(value=False)
        self.through_var    = tk.BooleanVar(value=False)
        self.lock_var       = tk.BooleanVar(value=False)
        self.light_bg_var   = tk.BooleanVar(value=False)
        self.mode_var       = tk.StringVar(value="Normal")
        self.grid_size_var  = tk.IntVar(value=50)
        self.grid_style_var = tk.StringVar(value="FH6")
        self.grid_color     = "#5865f2"
        self.controls_vis   = True
        self.is_fs          = False
        self._saved_geom    = ""
        self._last_hex      = "#333333"
        self.layer_count    = tk.IntVar(value=0)

        self._rs_dir = ""
        self._rs_x0 = self._rs_y0 = self._rs_w0 = self._rs_h0 = 0
        self._rs_wx0 = self._rs_wy0 = 0
        self._dx = self._dy = 0
        self._hwnd = None

        self._setup_window()
        self._build_ui()
        self._setup_resize_handles()
        self._bind_keys()
        self._poll_global_hotkeys()
        self.root.after(100, self._apply_win32_style)

        # EXEにファイルをドラッグ&ドロップ、またはコマンドラインで渡された場合に自動で開く
        if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
            self.root.after(150, lambda: self._load(sys.argv[1]))

        self.root.mainloop()

    def c(self, k): return self.C[k]

    # ── Window setup ───────────────────────────────────────────────

    def _setup_window(self):
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha",   0.70)
        self.root.configure(bg=self.c("bg_dark"))
        self.root.minsize(MIN_W, MIN_H)

        # Sync Tk scaling to display DPI for crisp rendering
        try:
            dpi = self.root.winfo_fpixels("1i")
            self.root.tk.call("tk", "scaling", dpi / 72)
        except Exception:
            pass

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"740x630+{(sw-740)//2}+{(sh-630)//2}")

    # ── 8-direction resize handles ─────────────────────────────────

    def _setup_resize_handles(self):
        EDGE, CORN = 5, 10
        specs = {
            "n":  dict(relx=0,   rely=0,   relwidth=1,  height=EDGE, anchor="nw", cursor="sb_v_double_arrow"),
            "s":  dict(relx=0,   rely=1.0, relwidth=1,  height=EDGE, anchor="sw", cursor="sb_v_double_arrow"),
            "e":  dict(relx=1.0, rely=0,   width=EDGE,  relheight=1, anchor="ne", cursor="sb_h_double_arrow"),
            "w":  dict(relx=0,   rely=0,   width=EDGE,  relheight=1, anchor="nw", cursor="sb_h_double_arrow"),
            "nw": dict(relx=0,   rely=0,   width=CORN,  height=CORN, anchor="nw", cursor="size_nw_se"),
            "ne": dict(relx=1.0, rely=0,   width=CORN,  height=CORN, anchor="ne", cursor="size_ne_sw"),
            "sw": dict(relx=0,   rely=1.0, width=CORN,  height=CORN, anchor="sw", cursor="size_ne_sw"),
            "se": dict(relx=1.0, rely=1.0, width=CORN,  height=CORN, anchor="se", cursor="size_nw_se"),
        }
        for d, opts in specs.items():
            cur = opts.pop("cursor")
            f = tk.Frame(self.root, bg=self.c("bg_dark"), cursor=cur)
            f.place(**opts)
            f.lift()
            f.bind("<Button-1>",  lambda e, _d=d: self._rs_start(e, _d))
            f.bind("<B1-Motion>", self._rs_drag)

    def _rs_start(self, event, direction):
        self._rs_dir = direction
        self._rs_x0  = event.x_root; self._rs_y0  = event.y_root
        self._rs_w0  = self.root.winfo_width()
        self._rs_h0  = self.root.winfo_height()
        self._rs_wx0 = self.root.winfo_x(); self._rs_wy0 = self.root.winfo_y()

    def _rs_drag(self, event):
        dx = event.x_root - self._rs_x0
        dy = event.y_root - self._rs_y0
        d  = self._rs_dir
        x, y = self._rs_wx0, self._rs_wy0
        w, h = self._rs_w0,  self._rs_h0
        if "e" in d: w = max(MIN_W, w + dx)
        if "s" in d: h = max(MIN_H, h + dy)
        if "w" in d:
            nw = max(MIN_W, w - dx); x += w - nw; w = nw
        if "n" in d:
            nh = max(MIN_H, h - dy); y += h - nh; h = nh
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ── UI build ───────────────────────────────────────────────────

    def _build_ui(self):
        tk.Frame(self.root, bg=self.c("accent"), height=2).pack(fill="x")
        self._build_titlebar()

        self.ctrl_section = tk.Frame(self.root, bg=self.c("bg_panel"))
        self.ctrl_section.pack(fill="x")
        inner = tk.Frame(self.ctrl_section, bg=self.c("bg_panel"))
        inner.pack(fill="x", padx=16, pady=12)
        self._build_controls(inner)
        tk.Frame(self.ctrl_section, bg=self.c("separator"), height=1).pack(fill="x")

        self._build_canvas()
        self._build_statusbar()

    # ── Title bar ─────────────────────────────────────────────────

    def _build_titlebar(self):
        bar = tk.Frame(self.root, bg=self.c("titlebar"), height=32)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        self.titlebar = bar

        dot = tk.Frame(bar, bg=self.c("accent"), width=8, height=8)
        dot.place(x=14, rely=0.5, anchor="w")
        for w in (dot, bar):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        lbl = tk.Label(bar, text="Vinyl Trace Overlay",
                       bg=self.c("titlebar"), fg=self.c("text"),
                       font=("Segoe UI", 10, "bold"))
        lbl.pack(side="left", padx=(30, 0))
        lbl.bind("<Button-1>", self._drag_start)
        lbl.bind("<B1-Motion>", self._drag_move)

        self._wbtn(bar, "close",    self.root.quit)
        self._wbtn(bar, "maximize", self._toggle_fullscreen)
        self._wbtn(bar, "minimize", self._minimize)

        tk.Label(bar, text="v3.2", bg=self.c("titlebar"),
                 fg=self.c("text_muted"), font=("Segoe UI", 8)
                 ).pack(side="right", padx=8)

    def _wbtn(self, parent, kind, cmd):
        cv = tk.Canvas(parent, width=46, height=32,
                       bg=self.c("titlebar"), highlightthickness=0, cursor="hand2")
        cv.pack(side="right")
        DANGER = self.c("danger")
        OTHER  = "#3a3b3e"
        TITLE  = self.c("titlebar")

        def draw(hover=False):
            cv.delete("all")
            bg = (DANGER if kind == "close" else OTHER) if hover else TITLE
            cv.configure(bg=bg)
            fg = "#ffffff" if hover else self.c("text_muted")
            cx, cy = 23, 16
            if kind == "minimize":
                cv.create_line(cx - 6, cy + 3, cx + 6, cy + 3, fill=fg, width=1)
            elif kind == "maximize":
                cv.create_rectangle(cx - 6, cy - 5, cx + 6, cy + 5, outline=fg, width=1)
            elif kind == "close":
                cv.create_line(cx - 6, cy - 5, cx + 6, cy + 5, fill=fg, width=1)
                cv.create_line(cx + 6, cy - 5, cx - 6, cy + 5, fill=fg, width=1)

        draw()
        cv.bind("<Enter>",    lambda _: draw(True))
        cv.bind("<Leave>",    lambda _: draw(False))
        cv.bind("<Button-1>", lambda _: cmd())

    # ── Controls ───────────────────────────────────────────────────

    def _build_controls(self, parent):
        BG = self.c("bg_panel")

        # Row 1 — Open + Mode
        r1 = tk.Frame(parent, bg=BG)
        r1.pack(fill="x", pady=(0, 10))
        self._accent_btn(r1, "Open Image", self.open_image).pack(side="left")
        tk.Frame(r1, bg=BG, width=20).pack(side="left")
        tk.Label(r1, text="Mode", bg=BG, fg=self.c("text_muted"),
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 8))
        self._style_cb()
        cb = ttk.Combobox(r1, textvariable=self.mode_var, width=15, state="readonly",
                          values=["Normal", "Edge Detect", "Grayscale",
                                  "Invert", "High Contrast", "Soft Glow"])
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _: self.update_display())

        # Row 2 — Opacity slider
        r2 = tk.Frame(parent, bg=BG)
        r2.pack(fill="x", pady=(0, 6))
        tk.Label(r2, text="Opacity", width=8, anchor="w", bg=BG,
                 fg=self.c("text_muted"), font=("Segoe UI", 9)).pack(side="left")
        ModernSlider(r2, from_=10, to=100, variable=self.opacity_var,
                     command=self._on_opacity, width=160,
                     col_track=self.c("bg_input"), col_fill=self.c("accent")
                     ).pack(side="left", padx=(0, 8))
        self.opacity_lbl = tk.Label(r2, text="70%", width=5, anchor="w", bg=BG,
                                     fg=self.c("text"), font=("Segoe UI", 9, "bold"))
        self.opacity_lbl.pack(side="left")

        # Row 3 — Scale slider
        r3 = tk.Frame(parent, bg=BG)
        r3.pack(fill="x", pady=(0, 10))
        tk.Label(r3, text="Scale", width=8, anchor="w", bg=BG,
                 fg=self.c("text_muted"), font=("Segoe UI", 9)).pack(side="left")
        ModernSlider(r3, from_=5, to=400, variable=self.scale_var,
                     command=self._on_scale, width=160,
                     col_track=self.c("bg_input"), col_fill=self.c("accent")
                     ).pack(side="left", padx=(0, 8))
        self.scale_lbl = tk.Label(r3, text="100%", width=6, anchor="w", bg=BG,
                                   fg=self.c("text"), font=("Segoe UI", 9, "bold"))
        self.scale_lbl.pack(side="left", padx=(0, 16))
        self._flat_btn(r3, "Fit",        self._fit_image).pack(side="left", padx=(0, 5))
        self._flat_btn(r3, "1:1",        self._reset_scale).pack(side="left", padx=(0, 5))
        self._flat_btn(r3, "Reset View", self._reset_view).pack(side="left")

        # Row 4 — Toggle buttons
        r4 = tk.Frame(parent, bg=BG)
        r4.pack(fill="x", pady=(0, 8))
        self.btn_mh = self._toggle_btn(r4, "Flip H",           self._toggle_mirror_h)
        self.btn_mv = self._toggle_btn(r4, "Flip V",           self._toggle_mirror_v)
        self.btn_gr = self._toggle_btn(r4, "Grid  [F3]",       self._toggle_grid)
        self.btn_ct = self._toggle_btn(r4, "Click-Thru  [F2]", self._toggle_through)
        self.btn_lk = self._toggle_btn(r4, "Lock Pos",         self._toggle_lock)
        self.btn_bg = self._toggle_btn(r4, "Light BG  [F4]",   self._toggle_light_bg)

        # Row 5 — Grid settings + layer counter
        r5 = tk.Frame(parent, bg=BG)
        r5.pack(fill="x")

        tk.Label(r5, text="Grid", bg=BG, fg=self.c("text_muted"),
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))
        self._style_cb_small()
        gs_cb = ttk.Combobox(r5, textvariable=self.grid_style_var, width=7,
                             state="readonly", values=["FH6", "Classic"],
                             style="Small.TCombobox")
        gs_cb.pack(side="left", padx=(0, 12))
        gs_cb.bind("<<ComboboxSelected>>", lambda _: self.update_display())

        tk.Label(r5, text="Color", bg=BG, fg=self.c("text_muted"),
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))
        self.grid_sw = tk.Label(r5, width=3, bg=self.grid_color,
                                cursor="hand2", relief="flat")
        self.grid_sw.pack(side="left", ipady=5, padx=(0, 12))
        self.grid_sw.bind("<Button-1>", lambda _: self._pick_grid_color())

        tk.Label(r5, text="Size", bg=BG, fg=self.c("text_muted"),
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))
        ent = tk.Entry(r5, textvariable=self.grid_size_var, width=4,
                       bg=self.c("bg_input"), fg=self.c("text"),
                       insertbackground=self.c("text"),
                       highlightthickness=1, highlightcolor=self.c("accent"),
                       highlightbackground=self.c("separator"),
                       relief="flat", font=("Segoe UI", 9))
        ent.pack(side="left")
        ent.bind("<Return>",   lambda _: self.update_display())
        ent.bind("<FocusOut>", lambda _: self.update_display())
        tk.Label(r5, text=" px", bg=BG, fg=self.c("text_muted"),
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 16))

        # Layer counter (tracks 0/3000 limit like in-game)
        tk.Label(r5, text="Layers", bg=BG, fg=self.c("text_muted"),
                 font=("Segoe UI", 9)).pack(side="left", padx=(0, 5))
        self._flat_btn(r5, "−", self._layer_dec).pack(side="left", padx=(0, 2))
        self.layer_lbl = tk.Label(r5, textvariable=self.layer_count,
                                   width=4, anchor="center",
                                   bg=self.c("bg_input"), fg=self.c("text"),
                                   font=("Consolas", 9, "bold"))
        self.layer_lbl.pack(side="left")
        tk.Label(r5, text=f"/ {self.LAYER_MAX}", bg=BG, fg=self.c("text_muted"),
                 font=("Segoe UI", 9)).pack(side="left", padx=(2, 2))
        self._flat_btn(r5, "+", self._layer_inc).pack(side="left", padx=(2, 0))
        self._flat_btn(r5, "R", self._layer_reset).pack(side="left", padx=(3, 0))

        tk.Label(r5,
                 text="Scroll: zoom    Right-drag: pan    F1: UI    F11: fullscreen",
                 bg=BG, fg=self.c("text_muted"), font=("Segoe UI", 8)
                 ).pack(side="right")

    # ── Canvas ─────────────────────────────────────────────────────

    def _build_canvas(self):
        self.canvas = tk.Canvas(self.root, bg=self.c("bg_darkest"),
                                highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>",  lambda _: self.update_display())
        self.canvas.bind("<Motion>",     self._on_hover)
        self.canvas.bind("<Button-1>",   self._on_canvas_click)
        self.canvas.bind("<MouseWheel>", self._on_scroll)
        self.canvas.bind("<Button-4>",   lambda _: self._adj_scale(5))
        self.canvas.bind("<Button-5>",   lambda _: self._adj_scale(-5))
        self.canvas.bind("<Button-3>",   self._pan_start)
        self.canvas.bind("<B3-Motion>",  self._pan_move)
        self.canvas.after(200, self._placeholder)

    def _placeholder(self):
        cw = self.canvas.winfo_width()  or 360
        ch = self.canvas.winfo_height() or 240
        self.canvas.create_text(
            cw // 2, ch // 2,
            text="Open an image to begin\n\nCtrl+O  ·  click here\n\n"
                 "Scroll: zoom    Right-drag: pan    F2: click-through",
            fill=self.c("bg_btn_hover"), font=("Segoe UI", 11),
            justify="center", tags="ph")

    # ── Status bar ─────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=self.c("titlebar"), height=28)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        self.color_sw = tk.Frame(bar, width=18, height=18,
                                  bg=self._last_hex, cursor="hand2")
        self.color_sw.pack(side="left", padx=(10, 4), pady=5)
        self.color_sw.bind("<Button-1>", self._copy_hex)
        self.status_var = tk.StringVar(value="No image loaded  —  Ctrl+O to open")
        tk.Label(bar, textvariable=self.status_var,
                 bg=self.c("titlebar"), fg=self.c("text_muted"),
                 font=("Consolas", 8)).pack(side="left")

    # ═══════════════════════════════════════════════════════════════
    # Image
    # ═══════════════════════════════════════════════════════════════

    def open_image(self, *_):
        path = filedialog.askopenfilename(
            title="Select reference image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tiff"),
                       ("All files", "*.*")])
        if path: self._load(path)

    def _load(self, path):
        try:
            self.image_original = Image.open(path).convert("RGBA")
            self.pan_x = self.pan_y = 0
            img = self.image_original
            self.status_var.set(
                f"{os.path.basename(path)}  |  {img.width}×{img.height}px")
            self.canvas.delete("ph")
            self.update_display()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ═══════════════════════════════════════════════════════════════
    # Display
    # ═══════════════════════════════════════════════════════════════

    def update_display(self, *_):
        if not self.image_original: return

        bg = self.c("fh6_bg") if self.light_bg_var.get() else self.c("bg_darkest")
        self.canvas.configure(bg=bg)

        img = self._apply_mode(self.image_original.copy(), self.mode_var.get())
        if self.mirror_h_var.get(): img = ImageOps.mirror(img)
        if self.mirror_v_var.get(): img = ImageOps.flip(img)
        f  = max(0.05, self.scale_var.get() / 100.0)
        img = img.resize((max(1, int(img.width * f)),
                          max(1, int(img.height * f))), Image.LANCZOS)
        if self.grid_var.get(): img = self._draw_grid(img)
        self.image_display = img
        self.photo = ImageTk.PhotoImage(img)
        self._redraw()

    def _redraw(self):
        if not self.photo: return
        cw = self.canvas.winfo_width()  or 1
        ch = self.canvas.winfo_height() or 1
        self.canvas.delete("img")
        self.canvas.create_image(cw // 2 + self.pan_x, ch // 2 + self.pan_y,
                                  image=self.photo, anchor="center", tags="img")

    def _apply_mode(self, img, mode):
        if mode == "Edge Detect":
            return ImageEnhance.Brightness(
                img.convert("RGB").filter(ImageFilter.FIND_EDGES)
            ).enhance(4.0).convert("RGBA")
        if mode == "Grayscale":
            return ImageOps.grayscale(img.convert("RGB")).convert("RGBA")
        if mode == "Invert":
            r, g, b, a = img.split()
            return Image.merge("RGBA",
                (*ImageOps.invert(Image.merge("RGB", (r, g, b))).split(), a))
        if mode == "High Contrast":
            rgb = ImageEnhance.Contrast(img.convert("RGB")).enhance(3.0)
            return ImageEnhance.Sharpness(rgb).enhance(2.0).convert("RGBA")
        if mode == "Soft Glow":
            rgb = img.convert("RGB")
            return ImageEnhance.Brightness(
                Image.blend(rgb, rgb.filter(ImageFilter.GaussianBlur(5)), 0.45)
            ).enhance(1.25).convert("RGBA")
        return img

    # ── Grid drawing ───────────────────────────────────────────────

    def _draw_grid(self, img: Image.Image) -> Image.Image:
        if self.grid_style_var.get() == "FH6":
            return self._draw_grid_fh6(img)
        return self._draw_grid_classic(img)

    def _draw_grid_fh6(self, img: Image.Image) -> Image.Image:
        """
        FH6-style grid: small + markers at fine intervals,
        larger + markers every 4 cells, center crosshair.
        Matches the Forza Horizon 6 vinyl editor canvas appearance.
        """
        out  = img.copy()
        draw = ImageDraw.Draw(out, "RGBA")
        sz   = max(8, self.grid_size_var.get())
        w, h = out.size
        cx, cy = w // 2, h // 2

        try:
            r = int(self.grid_color[1:3], 16)
            g = int(self.grid_color[3:5], 16)
            b = int(self.grid_color[5:7], 16)
        except Exception:
            r, g, b = 88, 101, 242

        fine_col   = (r, g, b, 50)   # subtle fine + markers
        major_col  = (r, g, b, 120)  # brighter major + markers (every 4 cells)
        center_col = (r, g, b, 200)  # center crosshair lines

        arm_fine  = max(2, sz // 7)
        arm_major = max(4, sz // 3)

        # Draw + markers anchored to center
        x_range = range(-(cx // sz) - 1, (w - cx) // sz + 2)
        y_range = range(-(cy // sz) - 1, (h - cy) // sz + 2)

        for xi in x_range:
            for yi in y_range:
                x = cx + xi * sz
                y = cy + yi * sz
                if not (0 <= x < w and 0 <= y < h):
                    continue
                is_major = (xi % 4 == 0) and (yi % 4 == 0)
                arm = arm_major if is_major else arm_fine
                col = major_col if is_major else fine_col
                draw.line([(x - arm, y), (x + arm, y)], fill=col, width=1)
                draw.line([(x, y - arm), (x, y + arm)], fill=col, width=1)

        # Center crosshair
        draw.line([(cx, 0), (cx, h)], fill=center_col, width=1)
        draw.line([(0, cy), (w, cy)], fill=center_col, width=1)

        # Center dot
        dot_r = 4
        draw.ellipse([(cx - dot_r, cy - dot_r), (cx + dot_r, cy + dot_r)],
                     fill=(r, g, b, 255))
        return out

    def _draw_grid_classic(self, img: Image.Image) -> Image.Image:
        """Original solid-line grid."""
        out  = img.copy()
        draw = ImageDraw.Draw(out, "RGBA")
        sz   = max(10, self.grid_size_var.get())
        try:
            r = int(self.grid_color[1:3], 16)
            g = int(self.grid_color[3:5], 16)
            b = int(self.grid_color[5:7], 16)
        except Exception: r, g, b = 88, 101, 242
        lc = (r, g, b, 75);  xc = (r, g, b, 220)
        w, h = out.size;     cx, cy = w // 2, h // 2
        for x in range(cx % sz, w, sz):
            draw.line([(x, 0), (x, h)], fill=lc, width=1)
        for y in range(cy % sz, h, sz):
            draw.line([(0, y), (w, y)], fill=lc, width=1)
        draw.line([(cx, 0), (cx, h)], fill=xc, width=2)
        draw.line([(0, cy), (w, cy)], fill=xc, width=2)
        draw.ellipse([(cx - 5, cy - 5), (cx + 5, cy + 5)], fill=(r, g, b, 255))
        return out

    # ═══════════════════════════════════════════════════════════════
    # Color utilities
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _rgb_to_hsb(r: int, g: int, b: int) -> tuple:
        """Return (H 0-360, S 0-100, B 0-100) — FH6 uses HSB color system."""
        r_, g_, b_ = r / 255, g / 255, b / 255
        cmax = max(r_, g_, b_)
        cmin = min(r_, g_, b_)
        delta = cmax - cmin
        bri = cmax * 100
        sat = (delta / cmax * 100) if cmax else 0
        if delta == 0:
            hue = 0.0
        elif cmax == r_:
            hue = 60 * (((g_ - b_) / delta) % 6)
        elif cmax == g_:
            hue = 60 * ((b_ - r_) / delta + 2)
        else:
            hue = 60 * ((r_ - g_) / delta + 4)
        return round(hue, 1), round(sat, 1), round(bri, 1)

    # ═══════════════════════════════════════════════════════════════
    # Events
    # ═══════════════════════════════════════════════════════════════

    def _on_opacity(self, val):
        v = int(float(val))
        self.root.attributes("-alpha", v / 100)
        self.opacity_lbl.configure(text=f"{v}%")

    def _on_scale(self, val):
        self.scale_lbl.configure(text=f"{int(float(val))}%")
        self.update_display()

    def _on_hover(self, event):
        if not self.image_display: return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.image_display.size
        px = event.x - (cw // 2 + self.pan_x - iw // 2)
        py = event.y - (ch // 2 + self.pan_y - ih // 2)
        if 0 <= px < iw and 0 <= py < ih:
            try:
                r, g, b, a = self.image_display.getpixel((px, py))
                hx = f"#{r:02x}{g:02x}{b:02x}"
                self._last_hex = hx
                self.color_sw.configure(bg=hx)
                H, S, B = self._rgb_to_hsb(r, g, b)
                self.status_var.set(
                    f"x:{px:4}  y:{py:4}  |  "
                    f"RGB({r:3},{g:3},{b:3})  |  {hx}  |  "
                    f"HSB({H}°,{S}%,{B}%)  |  click swatch to copy"
                )
            except Exception: pass

    def _on_canvas_click(self, _):
        if not self.image_original: self.open_image()

    def _on_scroll(self, event):
        self._adj_scale(10 if event.delta > 0 else -10)

    def _pan_start(self, e): self._psx, self._psy = e.x, e.y
    def _pan_move(self, e):
        self.pan_x += e.x - self._psx;  self._psx = e.x
        self.pan_y += e.y - self._psy;  self._psy = e.y
        self._redraw()

    # ═══════════════════════════════════════════════════════════════
    # Toggles
    # ═══════════════════════════════════════════════════════════════

    def _toggle_mirror_h(self):
        self.mirror_h_var.set(not self.mirror_h_var.get())
        self._set_toggle(self.btn_mh, self.mirror_h_var.get()); self.update_display()

    def _toggle_mirror_v(self):
        self.mirror_v_var.set(not self.mirror_v_var.get())
        self._set_toggle(self.btn_mv, self.mirror_v_var.get()); self.update_display()

    def _toggle_grid(self):
        self.grid_var.set(not self.grid_var.get())
        self._set_toggle(self.btn_gr, self.grid_var.get()); self.update_display()

    def _toggle_through(self):
        self.through_var.set(not self.through_var.get())
        self._set_toggle(self.btn_ct, self.through_var.get()); self._apply_through()

    def _toggle_lock(self):
        self.lock_var.set(not self.lock_var.get())
        locked = self.lock_var.get()
        self._set_toggle(self.btn_lk, locked)
        self.btn_lk.configure(text="Locked" if locked else "Lock Pos")

    def _toggle_light_bg(self):
        self.light_bg_var.set(not self.light_bg_var.get())
        self._set_toggle(self.btn_bg, self.light_bg_var.get())
        self.update_display()

    def _toggle_fullscreen(self):
        self.is_fs = not self.is_fs
        if self.is_fs:
            self._saved_geom = self.root.geometry()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
        elif self._saved_geom:
            self.root.geometry(self._saved_geom)

    def _apply_win32_style(self):
        """overrideredirect を使わず Win32 API でタイトルバーだけを削除する。
        最小化・復元・タスクバーは Windows 標準動作に任せる。"""
        try:
            self.root.update()
            inner = self.root.winfo_id()
            hwnd  = ctypes.windll.user32.GetParent(inner) or inner
            self._hwnd = hwnd

            if IS_WINDOWS:
                GWL_STYLE     = -16
                WS_CAPTION    = 0x00C00000
                WS_THICKFRAME = 0x00040000
                u32 = ctypes.windll.user32
                style = u32.GetWindowLongW(hwnd, GWL_STYLE)
                u32.SetWindowLongW(hwnd, GWL_STYLE, style & ~WS_CAPTION & ~WS_THICKFRAME)
                # FRAMECHANGED でスタイル変更を即時反映
                u32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001|0x0002|0x0004|0x0020)
        except Exception as e:
            print(f"[win32_style] {e}")
        finally:
            self.root.deiconify()
            self.root.attributes("-topmost", True)

    def _apply_through(self):
        if not IS_WINDOWS:
            if self.through_var.get():
                messagebox.showinfo("Info", "Click-through is Windows only.")
                self.through_var.set(False); self._set_toggle(self.btn_ct, False)
            return
        try:
            hwnd = self._hwnd
            if not hwnd:
                self.root.update()
                hwnd = ctypes.windll.user32.FindWindowW(None, self.TITLE)
            if not hwnd: return
            GWL = -20; L = 0x00080000; T = 0x00000020
            cur = ctypes.windll.user32.GetWindowLongW(hwnd, GWL)
            ctypes.windll.user32.SetWindowLongW(
                hwnd, GWL, (cur | L | T) if self.through_var.get() else (cur & ~T))
        except Exception as e: print(f"[through] {e}")

    def _poll_global_hotkeys(self):
        """Click-Through ON中はオーバーレイがフォーカスを失うため root.bind が効かない。
        GetAsyncKeyState でフォーカスに関係なく F2 を監視して解除できるようにする。"""
        if IS_WINDOWS and self.through_var.get():
            VK_F2 = 0x71
            # 下位ビットが1 = 前回呼び出し以降にキーが押された
            if ctypes.windll.user32.GetAsyncKeyState(VK_F2) & 0x0001:
                self._toggle_through()
        self.root.after(100, self._poll_global_hotkeys)

    # ═══════════════════════════════════════════════════════════════
    # Layer counter
    # ═══════════════════════════════════════════════════════════════

    def _layer_inc(self):
        v = self.layer_count.get()
        if v < self.LAYER_MAX: self.layer_count.set(v + 1)
        self._update_layer_color()

    def _layer_dec(self):
        v = self.layer_count.get()
        if v > 0: self.layer_count.set(v - 1)
        self._update_layer_color()

    def _layer_reset(self):
        self.layer_count.set(0); self._update_layer_color()

    def _update_layer_color(self):
        ratio = self.layer_count.get() / self.LAYER_MAX
        if ratio >= 0.9:
            fg = self.c("danger")
        elif ratio >= 0.7:
            fg = "#f0a832"
        else:
            fg = self.c("text")
        self.layer_lbl.configure(fg=fg)

    # ═══════════════════════════════════════════════════════════════
    # Window drag
    # ═══════════════════════════════════════════════════════════════

    def _drag_start(self, e): self._dx, self._dy = e.x, e.y
    def _drag_move(self, e):
        if self.lock_var.get(): return
        self.root.geometry(
            f"+{self.root.winfo_x()+(e.x-self._dx)}"
            f"+{self.root.winfo_y()+(e.y-self._dy)}")

    def _minimize(self):
        self.root.overrideredirect(False); self.root.iconify()
        self.root.bind("<Map>", self._restore)

    def _restore(self, _=None):
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True); self.root.unbind("<Map>")

    # ═══════════════════════════════════════════════════════════════
    # Utility
    # ═══════════════════════════════════════════════════════════════

    def _fit_image(self):
        if not self.image_original: return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.image_original.size
        v = max(5, min(400, int(min(cw/iw, ch/ih) * 100)))
        self.scale_var.set(v); self.scale_lbl.configure(text=f"{v}%")
        self.pan_x = self.pan_y = 0; self.update_display()

    def _reset_scale(self):
        self.scale_var.set(100); self.scale_lbl.configure(text="100%")
        self.pan_x = self.pan_y = 0; self.update_display()

    def _reset_view(self):
        self.pan_x = self.pan_y = 0; self._redraw()

    def _pick_grid_color(self):
        col = colorchooser.askcolor(color=self.grid_color, title="Grid Color")[1]
        if col:
            self.grid_color = col; self.grid_sw.configure(bg=col)
            if self.grid_var.get(): self.update_display()

    def _adj_scale(self, d):
        v = max(5, min(400, int(self.scale_var.get()) + d))
        self.scale_var.set(v); self.scale_lbl.configure(text=f"{v}%")
        self.update_display()

    def _toggle_controls(self):
        self.controls_vis = not self.controls_vis
        if self.controls_vis:
            self.ctrl_section.pack(fill="x", before=self.canvas)
        else:
            self.ctrl_section.pack_forget()

    def _copy_hex(self, _=None):
        self.root.clipboard_clear()
        self.root.clipboard_append(self._last_hex)
        self.status_var.set(f"Copied: {self._last_hex}")

    # ═══════════════════════════════════════════════════════════════
    # Keys
    # ═══════════════════════════════════════════════════════════════

    def _bind_keys(self):
        self.root.bind("<Control-o>",     self.open_image)
        self.root.bind("<F1>",            lambda _: self._toggle_controls())
        self.root.bind("<F2>",            lambda _: self._toggle_through())
        self.root.bind("<F3>",            lambda _: self._toggle_grid())
        self.root.bind("<F4>",            lambda _: self._toggle_light_bg())
        self.root.bind("<F11>",           lambda _: self._toggle_fullscreen())
        self.root.bind("<Control-equal>", lambda _: self._adj_scale(10))
        self.root.bind("<Control-plus>",  lambda _: self._adj_scale(10))
        self.root.bind("<Control-minus>", lambda _: self._adj_scale(-10))
        self.root.bind("<Control-Up>",    lambda _: self._layer_inc())
        self.root.bind("<Control-Down>",  lambda _: self._layer_dec())
        self.root.bind("<Escape>",
            lambda _: self._toggle_fullscreen() if self.is_fs else self.root.quit())

    # ═══════════════════════════════════════════════════════════════
    # Widget factories
    # ═══════════════════════════════════════════════════════════════

    def _accent_btn(self, parent, text, cmd):
        b = tk.Label(parent, text=f"  {text}  ", bg=self.c("accent"), fg="white",
                     font=("Segoe UI", 9, "bold"), cursor="hand2", pady=5)
        b.bind("<Enter>",    lambda _: b.configure(bg=self.c("accent_dim")))
        b.bind("<Leave>",    lambda _: b.configure(bg=self.c("accent")))
        b.bind("<Button-1>", lambda _: cmd()); return b

    def _flat_btn(self, parent, text, cmd):
        b = tk.Label(parent, text=f"  {text}  ", bg=self.c("bg_btn"), fg=self.c("text"),
                     font=("Segoe UI", 9), cursor="hand2", pady=4)
        b.bind("<Enter>",    lambda _: b.configure(bg=self.c("bg_btn_hover")))
        b.bind("<Leave>",    lambda _: b.configure(bg=self.c("bg_btn")))
        b.bind("<Button-1>", lambda _: cmd()); return b

    def _toggle_btn(self, parent, text, cmd):
        b = tk.Label(parent, text=f"  {text}  ", bg=self.c("bg_btn"),
                     fg=self.c("text_muted"), font=("Segoe UI", 9),
                     cursor="hand2", pady=4)
        b._active = False
        b.pack(side="left", padx=(0, 5))
        b.bind("<Enter>",
               lambda _: b.configure(bg=self.c("bg_btn_hover")) if not b._active else None)
        b.bind("<Leave>",
               lambda _: b.configure(bg=self.c("bg_btn"))       if not b._active else None)
        b.bind("<Button-1>", lambda _: cmd()); return b

    def _set_toggle(self, b, active):
        b._active = active
        b.configure(bg=self.c("accent") if active else self.c("bg_btn"),
                    fg="white"          if active else self.c("text_muted"))

    def _style_cb(self):
        s = ttk.Style()
        try: s.theme_use("clam")
        except Exception: pass
        s.configure("TCombobox",
                    fieldbackground=self.c("bg_input"), background=self.c("bg_input"),
                    foreground=self.c("text"), selectbackground=self.c("bg_input"),
                    selectforeground=self.c("text"), arrowcolor=self.c("text_muted"),
                    borderwidth=0)
        s.map("TCombobox",
              fieldbackground=[("readonly", self.c("bg_input"))],
              background=[("readonly", self.c("bg_input"))])

    def _style_cb_small(self):
        s = ttk.Style()
        s.configure("Small.TCombobox",
                    fieldbackground=self.c("bg_input"), background=self.c("bg_input"),
                    foreground=self.c("text"), selectbackground=self.c("bg_input"),
                    selectforeground=self.c("text"), arrowcolor=self.c("text_muted"),
                    borderwidth=0)
        s.map("Small.TCombobox",
              fieldbackground=[("readonly", self.c("bg_input"))],
              background=[("readonly", self.c("bg_input"))])


if __name__ == "__main__":
    VinylTraceOverlay()
