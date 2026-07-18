#!/usr/bin/env python3
"""
ChaosZero Nightmare — Spanish Patch GUI
One-click: extract -> translate -> rebuild -> apply
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading, os, sys, shutil, json

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "app_config.json")
DEFAULT_GAME_DIR = r"G:\stove\Games\ChaosZeroNightmare"
PACK_SUB = os.path.join("bin", "appdata", "cznlive")

sys.path.insert(0, SCRIPT_DIR)

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"game_dir": DEFAULT_GAME_DIR}

def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)


class PatchApp:
    STEPS = [
        ("extract",  "Extraer texto del juego"),
        ("translate", "Traducir al espanol"),
        ("rebuild",  "Reconstruir data.pack"),
        ("apply",    "Aplicar al juego"),
    ]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ChaosZero Nightmare - Parche ES")
        self.root.geometry("540x370")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")
        self.cfg = load_config()
        self.running = False
        self._build_ui()
        self._style()

    def _build_ui(self):
        bg, fg, accent = "#1e1e2e", "#cdd6f4", "#89b4fa"

        tk.Label(self.root, text="ChaosZero Nightmare", font=("Segoe UI", 16, "bold"),
                 bg=bg, fg=accent).pack(pady=(16, 2))
        tk.Label(self.root, text="Parche al Espanol", font=("Segoe UI", 11),
                 bg=bg, fg="#a6adc8").pack(pady=(0, 10))

        ff = tk.Frame(self.root, bg=bg)
        ff.pack(fill="x", padx=24, pady=(0, 8))
        tk.Label(ff, text="Juego:", font=("Segoe UI", 10), bg=bg, fg=fg).pack(side="left")
        self.folder_var = tk.StringVar(value=self.cfg.get("game_dir", DEFAULT_GAME_DIR))
        tk.Entry(ff, textvariable=self.folder_var, font=("Consolas", 9), width=40,
                 bg="#313244", fg=fg, insertbackground=fg, relief="flat", bd=4
                 ).pack(side="left", padx=(6, 4))
        tk.Button(ff, text="Examinar", font=("Segoe UI", 9), bg="#45475a", fg=fg,
                  relief="flat", bd=0, activebackground="#585b70", cursor="hand2",
                  command=self._browse).pack(side="left")

        sf = tk.Frame(self.root, bg=bg)
        sf.pack(fill="x", padx=24, pady=(2, 4))
        self.step_w = {}
        for key, label in self.STEPS:
            row = tk.Frame(sf, bg=bg)
            row.pack(fill="x", pady=3)
            icon = tk.Label(row, text="\u25cb", font=("Segoe UI", 13), bg=bg, fg="#585b70", width=2)
            icon.pack(side="left")
            tk.Label(row, text=label, font=("Segoe UI", 10), bg=bg, fg=fg, anchor="w").pack(side="left", padx=(2,0))
            pct_lbl = tk.Label(row, text="", font=("Consolas", 9), bg=bg, fg="#a6adc8", width=8, anchor="e")
            pct_lbl.pack(side="right")
            bar = ttk.Progressbar(row, length=130, mode="determinate",
                                  style="Custom.Horizontal.TProgressbar")
            bar.pack(side="right", padx=(0, 8))
            self.step_w[key] = {"icon": icon, "pct": pct_lbl, "bar": bar}

        bf = tk.Frame(self.root, bg=bg)
        bf.pack(pady=(6, 4))
        self.patch_btn = tk.Button(bf, text="Parchear", font=("Segoe UI", 12, "bold"),
                                   bg=accent, fg="#1e1e2e", relief="flat", bd=0,
                                   padx=40, pady=6, cursor="hand2",
                                   activebackground="#74c7ec", command=self._start)
        self.patch_btn.pack()

        self.status_var = tk.StringVar(value="Listo")
        tk.Label(self.root, textvariable=self.status_var, font=("Segoe UI", 9),
                 bg=bg, fg="#a6adc8").pack(pady=(4, 8))

    def _style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Custom.Horizontal.TProgressbar",
                     troughcolor="#313244", background="#89b4fa", thickness=12)

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.folder_var.get(),
                                    title="Seleccionar carpeta bin del juego")
        if d:
            self.folder_var.set(d)
            self.cfg["game_dir"] = d
            save_config(self.cfg)

    def _set_step(self, key, state, pct=None):
        w = self.step_w[key]
        icons  = {"pending": "\u25cb", "active": "\u25cf", "done": "\u2713", "error": "\u2717"}
        colors = {"pending": "#585b70", "active": "#f9e2af", "done": "#a6e3a1", "error": "#f38ba8"}
        w["icon"].config(text=icons.get(state, "\u25cb"), fg=colors.get(state, "#585b70"))
        if pct is not None:
            w["bar"]["value"] = pct
            w["pct"].config(text=f"{pct}%")
        elif state == "done":
            w["bar"]["value"] = 100
            w["pct"].config(text="100%")
        elif state == "pending":
            w["bar"]["value"] = 0
            w["pct"].config(text="")

    def _start(self):
        if self.running:
            return
        game_dir = self.folder_var.get().strip()
        pack_dir = os.path.join(game_dir, PACK_SUB)
        if not os.path.isfile(os.path.join(pack_dir, "data.pack")):
            messagebox.showerror("Error", f"No se encontro data.pack en:\n{pack_dir}")
            return
        self.cfg["game_dir"] = game_dir
        save_config(self.cfg)
        self.running = True
        self.patch_btn.config(state="disabled")
        for k, _ in self.STEPS:
            self._set_step(k, "pending")
        self.status_var.set("Iniciando...")
        threading.Thread(target=self._pipeline, args=(game_dir,), daemon=True).start()

    def _pipeline(self, game_dir):
        pack_dir = os.path.join(game_dir, PACK_SUB)
        output_dir = os.path.join(SCRIPT_DIR, "bin_full_rebuild")
        tsv_path = os.path.join(SCRIPT_DIR, "text_ko_text.tsv")

        try:
            # 1. Extract
            self._ui("extract", "active", 0, "Extrayendo...")
            from extract_and_translate import run_extract
            source, src_lang = run_extract(pack_dir)
            self._ui("extract", "done", 100, f"{len(source):,} textos")

            # 2. Translate
            self._ui("translate", "active", 0, "Traduciendo...")
            from extract_and_translate import run_translate
            def on_tr(done, total, translated, errors):
                if total > 0:
                    pct = min(done * 100 // total, 99)
                    lbl = f"{pct}%  ({translated}tr, {errors}err)"
                    self.root.after(0, self._ui, "translate", "active", pct, lbl)
            tr_result = run_translate(source, src_lang, progress_cb=on_tr)
            extra = ""
            if tr_result['new'] or tr_result['changed']:
                extra = f" (+{tr_result['new']}n +{tr_result['changed']}c)"
            self._ui("translate", "done", 100, f"{tr_result['translated']}tr{extra}")

            # 3. Rebuild
            self._ui("rebuild", "active", 0, "Reconstruyendo...")
            from rebuild_ko_to_es import run_rebuild
            def on_rb(step, done, total):
                if total > 0:
                    pct = min(done * 100 // total, 99)
                    self.root.after(0, self._ui, "rebuild", "active", pct, f"{pct}%")
            rb = run_rebuild(pack_dir, tsv_path, output_dir, progress_cb=on_rb)
            self._ui("rebuild", "done", 100, f"{rb['replaced']:,} ok")

            # 4. Apply
            self._ui("apply", "active", 0, "Copiando...")
            self._apply(game_dir, output_dir)
            self._ui("apply", "done", 100, "Listo")

            self.root.after(0, self._done)

        except Exception as e:
            self.root.after(0, self._error, str(e))

    def _apply(self, game_dir, src_dir):
        dest = os.path.join(game_dir, PACK_SUB)
        vols = ["data.pack"] + [f"data.pack~{i}" for i in range(1, 6)]
        for v in vols:
            sp = os.path.join(src_dir, v)
            dp = os.path.join(dest, v)
            if os.path.exists(dp) and not os.path.exists(dp + ".bak"):
                shutil.copy2(dp, dp + ".bak")
            if os.path.exists(sp):
                shutil.copy2(sp, dp)

    def _ui(self, key, state, pct, label):
        self._set_step(key, state, pct)
        self.status_var.set(label)

    def _done(self):
        self.running = False
        self.patch_btn.config(state="normal")
        self.status_var.set("Parche aplicado! Inicia el juego en idioma COREANO.")
        messagebox.showinfo("Terminado",
            "Parche aplicado correctamente!\n\n"
            "Inicia el juego en idioma COREANO para ver el texto en espanol.\n"
            "Los originales se guardaron como .bak")

    def _error(self, msg):
        self.running = False
        self.patch_btn.config(state="normal")
        self.status_var.set(f"Error: {msg}")
        messagebox.showerror("Error", f"Error durante el parche:\n\n{msg}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    PatchApp().run()
