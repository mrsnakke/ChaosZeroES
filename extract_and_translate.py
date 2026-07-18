#!/usr/bin/env python3
"""
Extract text from data.pack (KO or EN) and translate to Spanish.
Incremental: only translates new/changed texts, reuses existing translations.
"""
import struct, os, sys, time, json, urllib.request, urllib.parse, csv
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
PACK_DIR_DEFAULT = os.path.join(r"G:\stove\Games\ChaosZeroNightmare", "bin", "appdata", "cznlive")
OUTPUT_ES_TSV = os.path.join(SCRIPT_DIR, "text_ko_text.tsv")
OUTPUT_EN_TSV = os.path.join(SCRIPT_DIR, "text_en_extracted.tsv")

DB_KEYS = {
    'ko': b"text/ko/text.db",
    'en': b"text/en/text.db",
}

def cdbm_hash(key_bytes):
    h = 0
    for b in key_bytes:
        ch = b + 32 if 65 <= b <= 90 else b
        h = (ch + 43 * h) & 0xFFFFFFFF
    return h

sys.path.insert(0, SCRIPT_DIR)
from rebuild_ko_to_es import (
    MultiVolumePack, inner_xor_crypt, find_inner_xor_offset,
    PACK_XOR_KEY, INNER_XOR_KEY
)
import numpy as np

_INNER_XOR_NP = np.frombuffer(INNER_XOR_KEY, dtype=np.uint8)

def decrypt_inner_db(raw_value):
    boff = find_inner_xor_offset(raw_value[:64])
    if boff is None:
        return None
    data = np.frombuffer(raw_value, dtype=np.uint8).copy()
    key_len = 256
    phase = boff % key_len
    repeats = (len(data) + phase + key_len - 1) // key_len + 1
    key_stream = np.tile(_INNER_XOR_NP, repeats)[phase:phase + len(data)]
    decrypted = np.bitwise_xor(data, key_stream).tobytes()
    if decrypted[:5] != b'PLPcK':
        return None
    return decrypted

def extract_text_from_db(pack, db_key):
    hdr = pack.read_xor(0, 38)
    hash_count = struct.unpack_from('<I', hdr, 21)[0]
    ht_data = pack.read_xor(43, hash_count * 5)

    bucket = cdbm_hash(db_key) % hash_count
    off5 = bucket * 5
    ptr_hi = ht_data[off5]
    ptr_lo = struct.unpack_from('<I', ht_data, off5+1)[0]
    chain = ptr_lo + (ptr_hi << 32)

    raw_value = None
    safety = 0
    while chain > 0 and chain + 15 <= pack.total_size and safety < 1000:
        safety += 1
        ch = pack.read_xor(chain, 15)
        kl = ch[5]; vs = struct.unpack_from('<I', ch, 6)[0]
        key = pack.read_xor(chain + 15, kl)
        if key == db_key:
            raw_value = pack.read_xor(chain + 15 + kl, vs)
            break
        nh = ch[10]; nl = struct.unpack_from('<I', ch, 11)[0]
        np_ = nl + (nh << 32)
        if np_ == 0 or np_ == chain: break
        chain = np_

    if raw_value is None:
        return None

    decrypted = decrypt_inner_db(raw_value)
    if decrypted is None:
        return None

    inner_hash_count = struct.unpack_from('<I', decrypted, 21)[0]
    ht_start = 43
    texts = {}

    for bi in range(inner_hash_count):
        off = ht_start + bi * 5
        oh = decrypted[off]
        ol = struct.unpack_from('<I', decrypted, off+1)[0]
        fo = ol + (oh << 32)
        if fo == 0: continue

        chain = fo; safety = 0
        while chain > 0 and chain + 15 <= len(decrypted) and safety < 5000:
            safety += 1
            ds = struct.unpack_from('<I', decrypted, chain)[0]
            kl = decrypted[chain + 5]
            vs = struct.unpack_from('<I', decrypted, chain+6)[0]
            nh = decrypted[chain + 10]
            nl = struct.unpack_from('<I', decrypted, chain+11)[0]
            cnext = nl + (nh << 32)
            if ds == 0 or kl == 0: break

            cdata_off = chain + 15
            key_bytes = decrypted[cdata_off:cdata_off + kl]
            value_bytes = decrypted[cdata_off + kl:cdata_off + kl + vs]

            if not key_bytes.startswith(b'\t'):
                val = value_bytes
                n1 = val.find(b'\x00')
                if n1 >= 0:
                    text_id = val[:n1].decode('utf-8', errors='replace')
                    rest = val[n1+1:]
                    n2 = rest.find(b'\x00')
                    text = rest[:n2].decode('utf-8', errors='replace') if n2 >= 0 else rest.decode('utf-8', errors='replace')
                    if text.strip():
                        texts[text_id] = text

            if cnext == 0 or cnext == chain: break
            chain = cnext

    return texts


def google_translate_batch(texts, src='en', dest='es'):
    separator = " ||| "
    combined = separator.join(t.replace("\n", " ") for t in texts)
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            'client': 'gtx',
            'sl': src,
            'tl': dest,
            'dt': 't',
            'q': combined[:5000],
        }
        full_url = url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(full_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data and data[0]:
                result = ''.join(part[0] for part in data[0] if part[0])
                parts = result.split("|||")
                return [p.strip() for p in parts]
    except Exception:
        return None
    return None


OFFLINE_DICT = {
    "OK": "Aceptar", "Cancel": "Cancelar", "Close": "Cerrar",
    "Settings": "Configuraci\u00f3n", "Start": "Iniciar", "Exit": "Salir",
    "Back": "Volver", "Next": "Siguiente", "Previous": "Anterior",
    "Home": "Inicio", "Menu": "Men\u00fa", "Shop": "Tienda",
    "Mail": "Correo", "Bag": "Bolsa", "Inventory": "Inventario",
    "Equipment": "Equipamiento", "Skill": "Habilidad", "Skills": "Habilidades",
    "Quest": "Misi\u00f3n", "Quests": "Misiones",
    "Daily": "Diario", "Weekly": "Semanal",
    "Summon": "Invocar", "Enhance": "Mejorar", "Evolve": "Evolucionar",
    "Synthesize": "Sintetizar", "Sell": "Vender", "Buy": "Comprar",
    "Charge": "Recargar", "Premium": "Premium",
    "Free": "Gratis", "Reward": "Recompensa", "Rewards": "Recompensas",
    "Gift": "Regalo", "Gifts": "Regalos",
    "Event": "Evento", "Events": "Eventos",
    "Notice": "Aviso", "Notification": "Notificaci\u00f3n",
    "Friend": "Amigo", "Friends": "Amigos",
    "Guild": "Gremio", "Ranking": "Ranking",
    "Season": "Temporada", "Grade": "Rango", "Level": "Nivel",
    "EXP": "EXP", "HP": "HP", "MP": "MP",
    "Attack": "Ataque", "Defense": "Defensa", "Speed": "Velocidad",
    "Critical": "Cr\u00edtico", "Evasion": "Evasi\u00f3n",
    "Damage": "Da\u00f1o", "Recovery": "Recuperaci\u00f3n",
    "Buff": "Buff", "Debuff": "Debuff",
    "Status Ailment": "Estado alterado",
    "Poison": "Veneno", "Fire": "Fuego", "Ice": "Hielo",
    "Lightning": "Rayo", "Holy": "Sagrado", "Dark": "Oscuridad",
    "Raid": "Raid", "Boss": "Jefe", "Monster": "Monstruo",
    "Enemy": "Enemigo", "Ally": "Aliado",
    "Team": "Equipo", "Party": "Grupo",
    "Support": "Soporte", "Dealer": "Da\u00f1ador",
    "Tank": "Tanque", "Healer": "Sanador",
    "Archer": "Arquero", "Warrior": "Guerrero",
    "Mage": "Mago", "Thief": "Ladr\u00f3n", "Priest": "Sacerdote",
    "Sword": "Espada", "Bow": "Arco", "Staff": "Bast\u00f3n",
    "Shield": "Escudo", "Armor": "Armadura", "Helmet": "Casco",
    "Gloves": "Guantes", "Boots": "Botas",
    "Necklace": "Collar", "Ring": "Anillo", "Earrings": "Aretes",
    "Register": "Registrar", "Login": "Iniciar sesi\u00f3n",
    "Account": "Cuenta", "Server": "Servidor", "Channel": "Canal",
    "Chat": "Chat", "Message": "Mensaje",
    "Graphics": "Gr\u00e1ficos", "Sound": "Sonido",
    "BGM": "M\u00fazica", "SFX": "Efectos",
    "Volume": "Volumen", "Resolution": "Resoluci\u00f3n",
    "Fullscreen": "Pantalla completa", "Windowed": "Modo ventana",
    "Language": "Idioma",
    "Korean": "Coreano", "Japanese": "Japon\u00e9s",
    "English": "Ingl\u00e9s", "Chinese": "Chino",
    "Spanish": "Espa\u00f1ol",
    "Data": "Datos", "Download": "Descarga",
    "Update": "Actualizaci\u00f3n", "Patch": "Parche",
    "Maintenance": "Mantenimiento",
    "Please wait": "Por favor espere",
    "Connection lost": "Desconexi\u00f3n",
    "Network error": "Error de red",
    "Loading": "Cargando",
    "Locked": "Bloqueado", "Unlocked": "Desbloqueado",
    "Sealed": "Sellado",
    "Complete": "Completado",
    "Success": "\u00c9xito", "Failed": "Fallo",
    "Obtained": "Obtenido",
    "Use": "Usar", "Equip": "Equipar", "Unequip": "Desequipar",
    "Select": "Seleccionar",
    "Confirmed": "Confirmado",
    "Thank you": "Gracias",
    "Sorry": "Lo siento",
    "Help": "Ayuda",
    "Customer Service": "Servicio al cliente",
    "Inquiry": "Consulta", "Suggestion": "Sugerencia",
    "Bug": "Bug", "Error": "Error",
    "Block": "Bloquear", "Report": "Reportar",
    "Profile": "Perfil", "Title": "T\u00edtulo",
    "Avatar": "Avatar", "Skin": "Aspecto", "Theme": "Tema",
    "Effect": "Efecto", "Animation": "Animaci\u00f3n",
    "Cutscene": "Cutscene", "Story": "Historia",
    "Lore": "Lore", "Character": "Personaje",
    "Hero": "H\u00e9roe", "NPC": "NPC",
    "Town": "Pueblo", "Dungeon": "Mazmorra",
    "Map": "Mapa", "Region": "Regi\u00f3n", "World": "Mundo",
    "Portal": "Portal", "Move": "Mover",
    "Battle": "Batalla", "Strategy": "Estrategia",
    "Auto": "Autom\u00e1tico", "Manual": "Manual",
    "Skip": "Saltar", "Wait": "Esperar",
    "Proceed": "Avanzar", "Reset": "Reiniciar",
    "Refresh": "Actualizar",
    "Confirm": "Confirmar", "Accept": "Aceptar",
    "Decline": "Rechazar", "Continue": "Continuar",
    "Retry": "Reintentar", "Give Up": "Rendirse",
    "Claim": "Reclamar", "Collect": "Recolectar",
    "Send": "Enviar", "Receive": "Recibir",
    "Delete": "Eliminar", "Remove": "Quitar",
    "Add": "A\u00f1adir", "Create": "Crear",
    "Join": "Unirse", "Leave": "Salir",
    "Kick": "Expulsar", "Ban": "Banear",
    "Online": "En l\u00ednea", "Offline": "Sin conexi\u00f3n",
    "Connected": "Conectado", "Disconnected": "Desconectado",
    "Remaining": "Restante", "Available": "Disponible",
    "Required": "Requerido", "Max": "M\u00e1x", "Min": "M\u00edn",
    "Level": "Nivel", "Stage": "Etapa",
    "Chapter": "Cap\u00edtulo", "Episode": "Episodio",
    "Part": "Parte",
    "Normal": "Normal", "Hard": "Dif\u00edcil",
    "Very Hard": "Muy dif\u00edcil", "Extreme": "Extremo",
    "S-Rank": "Rango S", "A-Rank": "Rango A",
    "B-Rank": "Rango B", "C-Rank": "Rango C",
    "No results": "Sin resultados",
    "Not enough": "Insuficiente",
    "Already claimed": "Ya reclamado",
    "Already max level": "Nivel m\u00e1ximo alcanzado",
    "Inventory full": "Inventario lleno",
    "Not enough stamina": "Stamina insuficiente",
    "Not enough gold": "Oro insuficiente",
    "Not enough gems": "Gemas insuficientes",
    "Required level": "Nivel requerido",
    "Cooldown": "Enfriamiento",
    "Remaining time": "Tiempo restante",
    "Expires": "Expira",
    "New": "Nuevo", "Hot": "Popular",
    "Recommended": "Recomendado",
    "Special": "Especial", "Limited": "Limitado",
    "Rare": "Raro", "Epic": "\u00c9pico",
    "Legendary": "Legendario",
    "Common": "Com\u00fan", "Uncommon": "Poco com\u00fan",
}


# ═══════════════════════════════════════════════════════════════════════
# TSV I/O
# ═══════════════════════════════════════════════════════════════════════

def load_tsv(path):
    data = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                tid = row.get('text_id', '')
                if tid:
                    data[tid] = row
    return data

def save_tsvs(en_map, es_map):
    with open(OUTPUT_EN_TSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['text_id', 'en'])
        for tid in sorted(en_map):
            writer.writerow([tid, en_map[tid]])
    with open(OUTPUT_ES_TSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['text_id', 'en', 'spanish'])
        for tid in sorted(es_map):
            es, en = es_map[tid]
            writer.writerow([tid, en, es])


# ═══════════════════════════════════════════════════════════════════════
# Step 1: Extract
# ═══════════════════════════════════════════════════════════════════════

def run_extract(pack_dir):
    pack = MultiVolumePack(pack_dir)
    en_texts = None
    ko_texts = None
    try:
        en_texts = extract_text_from_db(pack, DB_KEYS['en'])
    except Exception:
        pass
    try:
        ko_texts = extract_text_from_db(pack, DB_KEYS['ko'])
    except Exception:
        pass
    pack.close()

    if en_texts is None and ko_texts is None:
        raise RuntimeError("No text databases found in pack")

    source = en_texts if en_texts else ko_texts
    src_lang = 'en' if en_texts else 'ko'
    return source, src_lang


# ═══════════════════════════════════════════════════════════════════════
# Step 2: Translate (incremental)
# ═══════════════════════════════════════════════════════════════════════

def run_translate(source_texts, src_lang='en', progress_cb=None):
    old_en = load_tsv(OUTPUT_EN_TSV)
    old_es = load_tsv(OUTPUT_ES_TSV)

    old_en_cache = {}
    for tid, row in old_en.items():
        old_en_cache[tid] = row.get('en', '')

    es_map = {}
    for tid, row in old_es.items():
        en_src = row.get('en', '')
        es_tr = row.get('spanish', '')
        if en_src and es_tr:
            es_map[tid] = (es_tr, en_src)

    new_texts = {}
    changed_texts = {}
    for tid, text in source_texts.items():
        if tid not in old_en_cache:
            new_texts[tid] = text
        elif old_en_cache[tid] != text:
            changed_texts[tid] = text

    to_translate = {}
    to_translate.update(new_texts)
    to_translate.update(changed_texts)

    dict_result = {}
    dict_hits = 0
    for tid, text in to_translate.items():
        s = text.strip()
        if s in OFFLINE_DICT:
            dict_result[tid] = OFFLINE_DICT[s]
            dict_hits += 1
        elif s.upper() in OFFLINE_DICT:
            dict_result[tid] = OFFLINE_DICT[s.upper()]
            dict_hits += 1

    for tid, tr in dict_result.items():
        es_map[tid] = (tr, source_texts[tid])

    remaining = {tid: text for tid, text in to_translate.items() if tid not in dict_result}

    translated, errors = 0, 0
    if remaining:
        items = list(remaining.items())
        total = len(items)
        BATCH_SIZE = 20
        WORKERS = 6

        def do_batch(batch):
            tids, texts = zip(*batch)
            res = google_translate_batch(list(texts), src=src_lang, dest='es')
            if res and len(res) == len(batch):
                return list(zip(tids, res)), 0, len(batch)
            out, errs, ok = [], 0, 0
            for tid, text in zip(tids, texts):
                single = google_translate_batch([text], src=src_lang, dest='es')
                if single and len(single) == 1:
                    out.append((tid, single[0])); ok += 1
                else:
                    out.append((tid, text)); errs += 1
                time.sleep(0.05)
            return out, errs, ok

        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {}
            for i in range(0, total, BATCH_SIZE):
                batch = items[i:i+BATCH_SIZE]
                futures[pool.submit(do_batch, batch)] = i

            done_count = 0
            for f in as_completed(futures):
                batch_results, batch_errors, batch_ok = f.result()
                for tid, tr in batch_results:
                    es_map[tid] = (tr, source_texts[tid])
                translated += batch_ok
                errors += batch_errors
                done_count += len(batch_results)
                if progress_cb:
                    progress_cb(done_count, total, translated, errors)

    en_map_current = {tid: text for tid, text in source_texts.items()}
    save_tsvs(en_map_current, es_map)

    return {
        'total': len(source_texts),
        'new': len(new_texts),
        'changed': len(changed_texts),
        'dict_hits': dict_hits,
        'translated': translated,
        'errors': errors,
    }


# ═══════════════════════════════════════════════════════════════════════
# Combined (CLI convenience)
# ═══════════════════════════════════════════════════════════════════════

def run_extract_and_translate(pack_dir, progress_cb=None):
    source, src_lang = run_extract(pack_dir)
    return source, src_lang, run_translate(source, src_lang, progress_cb)


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    pack_dir = os.environ.get("CZ_GAME_DIR", DEFAULT_GAME_DIR)
    pack_dir = os.path.join(pack_dir, PACK_DIR_DEFAULT) if not pack_dir.endswith("cznlive") else pack_dir

    print("=" * 60)
    print("  ChaosZero ES — Extract & Translate (Incremental)")
    print("=" * 60)

    def cli_progress(done, total, translated, errors):
        if total > 0:
            pct = done * 100 // total
            print(f"  Progress: {done:,}/{total:,} ({pct}%) translated={translated} errors={errors}")

    try:
        source, src_lang = run_extract(pack_dir)
        result = run_translate(source, src_lang, progress_cb=cli_progress)
    except RuntimeError as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    print(f"\n  Total texts: {result['total']:,}")
    print(f"  New: {result['new']:,}, Changed: {result['changed']:,}")
    print(f"  Dict hits: {result['dict_hits']:,}")
    print(f"  Google translated: {result['translated']:,}, Errors: {result['errors']:,}")

if __name__ == '__main__':
    main()
