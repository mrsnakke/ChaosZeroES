#!/usr/bin/env python3
"""
ChaosZero Nightmare — Spanish Patch GUI v2
One-click: extract EN -> translate -> rebuild -> apply
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading, os, sys, shutil, json, time, string

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "app_config.json")
DEFAULT_GAME_DIR = r"G:\stove\Games\ChaosZeroNightmare"
PACK_SUB = os.path.join("bin", "appdata", "cznlive")

# ═══════════════════════════════════════════════════════════════════════
# Colors
# ═══════════════════════════════════════════════════════════════════════
BG = "#0f1019"
BG2 = "#161829"
FG = "#c8cad8"
FG_DIM = "#6b7094"
ACCENT = "#3b82f6"
ACCENT_HOVER = "#2563eb"
GREEN = "#4ade80"
RED = "#f87171"
YELLOW = "#fbbf24"
LOG_FG = "#9ca3af"

# ═══════════════════════════════════════════════════════════════════════
# Auto-find game
# ═══════════════════════════════════════════════════════════════════════
def auto_find_game():
    game_dir = "ChaosZeroNightmare"
    exe_name = "ssr-stove-shield.exe"
    drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
    for drive in drives:
        try:
            for root, dirs, _ in os.walk(drive):
                depth = root.replace(drive, '').count(os.sep)
                if depth > 4:
                    dirs.clear()
                    continue
                dirs[:] = [d for d in dirs if not d.startswith('.')
                           and d not in ('Windows', '$Recycle.Bin', 'System Volume Information',
                                         'ProgramData', 'Recovery', 'node_modules', '.git')]
                if game_dir in dirs:
                    root_path = os.path.join(root, game_dir)
                    exe_path = os.path.join(root_path, "bin", exe_name)
                    if os.path.isfile(exe_path):
                        return root_path
        except PermissionError:
            continue
    return None


# ═══════════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════════
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"game_dir": DEFAULT_GAME_DIR}


def save_config(cfg):
    with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)


# ═══════════════════════════════════════════════════════════════════════
# GUI
# ═══════════════════════════════════════════════════════════════════════
class PatchApp:
    STEPS = [
        ("extract", "Extraccion"),
        ("translate", "Traduccion"),
        ("rebuild", "Rebuild"),
        ("apply", "Aplicar"),
    ]

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ChaosZero Nightmare - Parche ES v2")
        self.root.geometry("620x720")
        self.root.resizable(False, False)
        self.root.configure(bg=BG)
        self.cfg = load_config()
        self.running = False
        self.cancel_flag = False
        self._build_ui()
        self._check_game_path()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=BG2, padx=16, pady=12)
        hdr.pack(fill="x", padx=8, pady=(8, 4))
        tk.Label(hdr, text="ChaosZero Nightmare", font=("Segoe UI", 16, "bold"),
                 bg=BG2, fg=ACCENT).pack(anchor="w")
        tk.Label(hdr, text="Parche al Espanol v2.0", font=("Segoe UI", 10),
                 bg=BG2, fg=FG_DIM).pack(anchor="w")

        # Game path
        path_frame = tk.Frame(self.root, bg=BG2, padx=12, pady=8)
        path_frame.pack(fill="x", padx=8, pady=4)
        tk.Label(path_frame, text="Ruta del juego:", font=("Segoe UI", 9),
                 bg=BG2, fg=FG_DIM).pack(anchor="w")
        row = tk.Frame(path_frame, bg=BG2)
        row.pack(fill="x", pady=(4, 0))
        self.folder_var = tk.StringVar(value=self.cfg.get("game_dir", DEFAULT_GAME_DIR))
        tk.Entry(row, textvariable=self.folder_var, font=("Consolas", 9), width=48,
                 bg="#1e2035", fg=FG, insertbackground=FG, relief="flat", bd=4
                 ).pack(side="left", padx=(0, 4))
        tk.Button(row, text="Examinar", font=("Segoe UI", 9), bg="#2a2d45", fg=FG,
                  relief="flat", bd=0, activebackground="#353860", cursor="hand2",
                  command=self._browse).pack(side="left", padx=(0, 4))
        self.auto_btn = tk.Button(row, text="Buscar auto", font=("Segoe UI", 9),
                                  bg="#2a2d45", fg=FG, relief="flat", bd=0,
                                  activebackground="#353860", cursor="hand2",
                                  command=self._auto_find)
        self.auto_btn.pack(side="left")

        # Status
        status_frame = tk.Frame(self.root, bg=BG2, padx=12, pady=8)
        status_frame.pack(fill="x", padx=8, pady=4)
        self.status_pack = self._status_row(status_frame, "data.pack")
        self.status_textdb = self._status_row(status_frame, "text.db")
        self.status_vols = self._status_row(status_frame, "Volumenes")

        # Buttons
        btn_frame = tk.Frame(self.root, bg=BG, pady=6)
        btn_frame.pack(fill="x", padx=8)
        self.patch_btn = tk.Button(btn_frame, text="Parchear", font=("Segoe UI", 12, "bold"),
                                   bg=ACCENT, fg="#ffffff", relief="flat", bd=0,
                                   padx=32, pady=6, cursor="hand2",
                                   activebackground=ACCENT_HOVER,
                                   command=self._start)
        self.patch_btn.pack(side="left", padx=(0, 8))
        self.revert_btn = tk.Button(btn_frame, text="Revertir", font=("Segoe UI", 10),
                                    bg="#2a2d45", fg=FG, relief="flat", bd=0,
                                    padx=12, pady=6, cursor="hand2",
                                    activebackground="#353860",
                                    command=self._revert)
        self.revert_btn.pack(side="left", padx=(0, 8))
        self.cancel_btn = tk.Button(btn_frame, text="Cancelar", font=("Segoe UI", 10),
                                    bg="#2a2d45", fg=RED, relief="flat", bd=0,
                                    padx=12, pady=6, cursor="hand2",
                                    activebackground="#353860",
                                    command=self._cancel, state="disabled")
        self.cancel_btn.pack(side="left")

        # Progress bars
        prog_frame = tk.Frame(self.root, bg=BG2, padx=12, pady=8)
        prog_frame.pack(fill="x", padx=8, pady=4)
        self.step_widgets = {}
        for key, label in self.STEPS:
            row = tk.Frame(prog_frame, bg=BG2)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=f"{label}:", font=("Segoe UI", 9), bg=BG2, fg=FG_DIM,
                     width=12, anchor="w").pack(side="left")
            bar = ttk.Progressbar(row, length=300, mode="determinate",
                                  style="Custom.Horizontal.TProgressbar")
            bar.pack(side="left", padx=(0, 8))
            pct = tk.Label(row, text="--", font=("Consolas", 9), bg=BG2, fg=FG_DIM, width=20, anchor="w")
            pct.pack(side="left")
            self.step_widgets[key] = {"bar": bar, "pct": pct}

        # Log
        log_frame = tk.Frame(self.root, bg=BG2, padx=8, pady=8)
        log_frame.pack(fill="both", expand=True, padx=8, pady=4)
        tk.Label(log_frame, text="Registro:", font=("Segoe UI", 9), bg=BG2, fg=FG_DIM).pack(anchor="w")
        self.log_text = tk.Text(log_frame, font=("Consolas", 9), bg="#0d0e18", fg=LOG_FG,
                                relief="flat", bd=0, height=14, wrap="word",
                                insertbackground=LOG_FG, selectbackground="#2a2d45")
        self.log_text.pack(fill="both", expand=True, pady=(4, 0))
        self.log_text.tag_config("info", foreground=LOG_FG)
        self.log_text.tag_config("ok", foreground=GREEN)
        self.log_text.tag_config("warn", foreground=YELLOW)
        self.log_text.tag_config("err", foreground=RED)
        self.log_text.tag_config("accent", foreground=ACCENT)

        # Status bar
        self.statusbar = tk.StringVar(value="Listo")
        tk.Label(self.root, textvariable=self.statusbar, font=("Segoe UI", 9),
                 bg=BG, fg=FG_DIM, anchor="w", padx=12).pack(fill="x", pady=(0, 4))

        # Style
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("Custom.Horizontal.TProgressbar",
                     troughcolor="#1e2035", background=ACCENT, thickness=10)

    def _status_row(self, parent, label):
        row = tk.Frame(parent, bg=BG2)
        row.pack(fill="x", pady=2)
        icon = tk.Label(row, text="\u25cb", font=("Segoe UI", 11), bg=BG2, fg=FG_DIM, width=2)
        icon.pack(side="left")
        tk.Label(row, text=f"{label}:", font=("Segoe UI", 9), bg=BG2, fg=FG_DIM,
                 width=14, anchor="w").pack(side="left")
        val = tk.Label(row, text="--", font=("Segoe UI", 9), bg=BG2, fg=FG_DIM, anchor="w")
        val.pack(side="left")
        return {"icon": icon, "val": val}

    def _set_status(self, widget, ok, text):
        widget["icon"].config(text="\u2713" if ok else "\u2717",
                              fg=GREEN if ok else RED)
        widget["val"].config(text=text, fg=GREEN if ok else RED)

    def _set_step(self, key, pct=None, done=False, error=False):
        w = self.step_widgets[key]
        if pct is not None:
            w["bar"]["value"] = pct
            w["pct"].config(text=f"{pct}%", fg=FG)
        if done:
            w["bar"]["value"] = 100
            w["pct"].config(text="OK", fg=GREEN)
        if error:
            w["pct"].config(text="Error", fg=RED)

    def _log(self, msg, tag="info"):
        ts = time.strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{ts}] {msg}\n", tag)
        self.log_text.see("end")

    def _check_game_path(self):
        path = self.folder_var.get().strip()
        pack_dir = os.path.join(path, PACK_SUB)
        dp = os.path.join(pack_dir, "data.pack")
        if os.path.isfile(dp):
            sz = os.path.getsize(dp)
            self._set_status(self.status_pack, True, f"Encontrado ({sz/1024**3:.1f} GB)")
            # Check volumes
            vols = 1
            for i in range(1, 10):
                if os.path.isfile(os.path.join(pack_dir, f"data.pack~{i}")):
                    vols += 1
                else:
                    break
            self._set_status(self.status_vols, True, f"{vols} volumes")
            # Check text.db existence via key
            self._set_status(self.status_textdb, True, "Detectado (verificar al extraer)")
            self._log(f"Juego encontrado: {vols} volumes, {sz/1024**3:.1f} GB", "ok")
        else:
            self._set_status(self.status_pack, False, "No encontrado")
            self._set_status(self.status_textdb, False, "--")
            self._set_status(self.status_vols, False, "--")

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.folder_var.get(),
                                    title="Seleccionar carpeta del juego")
        if d:
            self.folder_var.set(d)
            self.cfg["game_dir"] = d
            save_config(self.cfg)
            self._check_game_path()

    def _auto_find(self):
        self.auto_btn.config(state="disabled", text="Buscando...")
        self._log("Buscando juego en todas las unidades...", "accent")

        def do_find():
            result = auto_find_game()
            self.root.after(0, lambda: self._on_auto_find(result))

        threading.Thread(target=do_find, daemon=True).start()

    def _on_auto_find(self, result):
        self.auto_btn.config(state="normal", text="Buscar auto")
        if result:
            self.folder_var.set(result)
            self.cfg["game_dir"] = result
            save_config(self.cfg)
            self._check_game_path()
            self._log(f"Juego encontrado automaticamente: {result}", "ok")
        else:
            self._log("No se encontro el juego automaticamente", "warn")

    def _revert(self):
        path = self.folder_var.get().strip()
        pack_dir = os.path.join(path, PACK_SUB)
        vols = ["data.pack"] + [f"data.pack~{i}" for i in range(1, 6)]
        baks = [os.path.join(pack_dir, v + ".bak") for v in vols
                if os.path.exists(os.path.join(pack_dir, v + ".bak"))]
        if not baks:
            messagebox.showinfo("Revertir", "No se encontraron archivos .bak.")
            return
        if not messagebox.askyesno("Revertir", f"Restaurar {len(baks)} archivos .bak?"):
            return
        for bak in baks:
            shutil.copy2(bak, bak[:-4])
            os.remove(bak)
        self._log(f"Restaurados {len(baks)} archivos originales", "ok")
        self.statusbar.set("Originales restaurados")
        self._check_game_path()

    def _cancel(self):
        self.cancel_flag = True
        self._log("Cancelando...", "warn")
        self.statusbar.set("Cancelando...")

    def _start(self):
        if self.running:
            return
        path = self.folder_var.get().strip()
        pack_dir = os.path.join(path, PACK_SUB)
        if not os.path.isfile(os.path.join(pack_dir, "data.pack")):
            messagebox.showerror("Error", f"No se encontro data.pack en:\n{pack_dir}")
            return
        self.cfg["game_dir"] = path
        save_config(self.cfg)
        self.running = True
        self.cancel_flag = False
        self.patch_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        for key, _ in self.STEPS:
            self._set_step(key)
        self.statusbar.set("Iniciando...")
        threading.Thread(target=self._pipeline, args=(pack_dir,), daemon=True).start()

    def _pipeline(self, pack_dir):
        output_dir = os.path.join(SCRIPT_DIR, "bin_full_rebuild")
        tsv_path = os.path.join(SCRIPT_DIR, "translations.tsv")
        glossary_path = os.path.join(SCRIPT_DIR, "glossary.json")

        try:
            # === STEP 1: Extract all entries from pack ===
            self.root.after(0, lambda: self._set_step("extract", 0))
            self.root.after(0, lambda: self._log("Extrayendo data.pack...", "accent"))

            from pack_rebuild import extract_all_files
            from text_extract import extract_en_text
            from story_patcher import extract_story_texts

            def extract_progress(msg):
                self.root.after(0, lambda m=msg: self._log(m))

            entries, orig_header, orig_ver5, hash_count = extract_all_files(pack_dir, progress_cb=extract_progress)

            t0 = time.time()
            en_texts = extract_en_text(pack_dir)
            elapsed = time.time() - t0
            self.root.after(0, lambda: self._log(
                f"Text DB: {len(en_texts):,} textos ({elapsed:.1f}s)", "ok"))

            story_text_map, story_patch_info = extract_story_texts(entries, progress_cb=extract_progress)

            # Merge story texts into en_texts for translation (with composite keys)
            existing_en = set(en_texts.values())
            for ck, en_text in story_text_map.items():
                if en_text not in existing_en:
                    en_texts[ck] = en_text

            self.root.after(0, lambda: self._set_step("extract", done=True))

            if self.cancel_flag:
                self.root.after(0, lambda: self._log("Cancelado por el usuario", "warn"))
                return

            # === STEP 2: Translate ===
            self.root.after(0, lambda: self._set_step("translate", 0))
            self.root.after(0, lambda: self._log("Cargando glossario...", "accent"))

            from translator import load_glossary, save_glossary, translate_all, detect_changes, load_translations_tsv, save_translations_tsv, estimate_time, _restore_en_markup

            glossary = load_glossary(glossary_path)
            prev_trans = load_translations_tsv(tsv_path)

            new_texts, changed_texts, unchanged = detect_changes(en_texts, prev_trans)
            total_to_do = len(new_texts) + len(changed_texts)

            self.root.after(0, lambda: self._log(
                f"Glossary: {len(glossary):,} entradas | "
                f"Nuevos: {len(new_texts):,} | Cambiados: {len(changed_texts):,} | "
                f"Sin cambios: {unchanged:,}"
            ))

            if total_to_do == 0:
                self.root.after(0, lambda: self._log("Todo traducido, sin cambios. Saltando Google Translate.", "ok"))
                translations = {}
                for tid, en_text in en_texts.items():
                    if en_text in glossary and glossary[en_text] != en_text:
                        es = _restore_en_markup(en_text, glossary[en_text])
                        translations[tid] = (en_text, es)
                    else:
                        translations[tid] = (en_text, en_text)
                save_glossary(glossary, glossary_path)
            else:
                import re as _re
                est = estimate_time(total_to_do, len(glossary))
                self.root.after(0, lambda: self._log(
                    f"Tiempo estimado: ~{est/60:.0f} min ({total_to_do:,} textos a traducir)"
                ))

                def translate_progress(msg):
                    self.root.after(0, lambda m=msg: self._log(m))
                    m = _re.search(r'\((\d+)%\)', msg)
                    if m:
                        self.root.after(0, lambda p=int(m.group(1)): self._set_step("translate", p))

                to_translate_en = {}
                to_translate_en.update(new_texts)
                to_translate_en.update(changed_texts)

                translations_partial = translate_all(to_translate_en, glossary, progress_cb=translate_progress)

                # Merge with unchanged
                translations = {}
                for tid, en_text in en_texts.items():
                    if tid in translations_partial:
                        translations[tid] = translations_partial[tid]
                    elif tid in prev_trans:
                        en_prev, es_prev = prev_trans[tid]
                        translations[tid] = (en_prev, _restore_en_markup(en_text, es_prev))
                    elif en_text in glossary and glossary[en_text] != en_text:
                        es = _restore_en_markup(en_text, glossary[en_text])
                        translations[tid] = (en_text, es)
                    else:
                        translations[tid] = (en_text, en_text)

                # Save glossary
                save_glossary(glossary, glossary_path)
                self.root.after(0, lambda: self._log(f"Glossary guardado: {len(glossary):,} entradas", "ok"))

            # Save translations TSV
            save_translations_tsv(translations, tsv_path)
            self.root.after(0, lambda: self._log(f"Translations guardado: {len(translations):,} entradas", "ok"))
            self.root.after(0, lambda: self._set_step("translate", done=True))

            if self.cancel_flag:
                self.root.after(0, lambda: self._log("Cancelado por el usuario", "warn"))
                return

            # === STEP 3: Rebuild ===
            self.root.after(0, lambda: self._set_step("rebuild", 0))
            self.root.after(0, lambda: self._log("Reconstruyendo data.pack...", "accent"))

            from pack_rebuild import process_en_to_es, rebuild_and_write, verify_pack
            from story_patcher import apply_story_patches

            def rebuild_progress(msg):
                self.root.after(0, lambda m=msg: self._log(m))

            # Patch text/en/text.db
            replaced = process_en_to_es(entries, tsv_path, progress_cb=rebuild_progress)
            self.root.after(0, lambda: self._log(
                f"Text DB: {replaced:,} reemplazados", "ok"))

            # Patch story.db entries
            story_patched = apply_story_patches(entries, story_patch_info, glossary, progress_cb=rebuild_progress)

            # Write pack
            total_size = rebuild_and_write(entries, orig_header, orig_ver5, hash_count, output_dir, progress_cb=rebuild_progress)

            # Verify
            ok = verify_pack(output_dir, entries, progress_cb=rebuild_progress)
            self.root.after(0, lambda: self._set_step("rebuild", done=True))
            self.root.after(0, lambda: self._log(
                f"Rebuild: {'OK' if ok else 'FAIL'} | "
                f"{replaced + story_patched:,} reemplazados | {total_size/1024**3:.2f} GB", "ok"
            ))

            if not ok:
                self.root.after(0, lambda: self._log("ERROR: Verificacion del pack fallo", "err"))
                return

            if self.cancel_flag:
                self.root.after(0, lambda: self._log("Cancelado por el usuario", "warn"))
                return

            # === STEP 4: Apply ===
            self.root.after(0, lambda: self._set_step("apply", 0))
            self.root.after(0, lambda: self._log("Copiando archivos...", "accent"))

            self._apply(pack_dir, output_dir)
            self.root.after(0, lambda: self._set_step("apply", done=True))
            self.root.after(0, lambda: self._log("Parche aplicado!", "ok"))
            self.root.after(0, self._done)

        except Exception as e:
            self.root.after(0, lambda: self._log(f"ERROR: {e}", "err"))
            self.root.after(0, lambda: self._set_step("rebuild", error=True))
            self.root.after(0, self._error_dialog, str(e))

    def _apply(self, pack_dir, src_dir):
        vols = ["data.pack"] + [f"data.pack~{i}" for i in range(1, 6)]
        for v in vols:
            sp = os.path.join(src_dir, v)
            dp = os.path.join(pack_dir, v)
            if os.path.exists(dp) and not os.path.exists(dp + ".bak"):
                shutil.copy2(dp, dp + ".bak")
            if os.path.exists(sp):
                shutil.copy2(sp, dp)

    def _done(self):
        self.running = False
        self.cancel_flag = False
        self.patch_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.statusbar.set("Parche aplicado! Inicia el juego en idioma INGLES.")
        self._check_game_path()
        messagebox.showinfo("Terminado",
            "Parche aplicado correctamente!\n\n"
            "Inicia el juego en idioma INGLES para ver el texto en espanol.\n"
            "Los originales se guardaron como .bak")

    def _error_dialog(self, msg):
        self.running = False
        self.cancel_flag = False
        self.patch_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.statusbar.set(f"Error: {msg}")
        messagebox.showerror("Error", f"Error durante el parche:\n\n{msg}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    PatchApp().run()
