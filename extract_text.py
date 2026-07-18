#!/usr/bin/env python3
"""
Extract all English text from data.pack and save as TSV.
This is fast - no translation, just extraction.
Then translate separately.
"""
import struct, os, sys, csv, time

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
GAME_DIR = os.environ.get("CZ_GAME_DIR", r"G:\stove\Games\ChaosZeroNightmare")
PACK_DIR = os.path.join(GAME_DIR, "bin", "appdata", "cznlive")
OUTPUT_EN_TSV = os.path.join(SCRIPT_DIR, "text_en_extracted.tsv")
OUTPUT_ES_TSV = os.path.join(SCRIPT_DIR, "text_ko_text.tsv")

sys.path.insert(0, SCRIPT_DIR)
from rebuild_ko_to_es import MultiVolumePack, cdbm_hash, INNER_XOR_KEY
import numpy as np

INNER_XOR_KEY_BYTES = INNER_XOR_KEY
_INNER_XOR_NP = np.frombuffer(INNER_XOR_KEY_BYTES, dtype=np.uint8)

def decrypt_inner_db(raw_value):
    def find_inner_xor_offset(data_head):
        for boff in range(256):
            d5 = bytes([data_head[i] ^ INNER_XOR_KEY_BYTES[(i + boff) % 256] for i in range(min(5, len(data_head)))])
            if d5 == b'PLPcK':
                return boff
        return None
    boff = find_inner_xor_offset(raw_value[:64])
    if boff is None:
        return None
    data = np.frombuffer(raw_value, dtype=np.uint8).copy()
    key_len = 256
    phase = boff % key_len
    repeats = (len(data) + phase + key_len - 1) // key_len + 1
    key_stream = np.tile(_INNER_XOR_NP, repeats)[phase:phase + len(data)]
    return np.bitwise_xor(data, key_stream).tobytes()

def extract_text(pack, db_key):
    hdr = pack.read_xor(0, 38)
    hash_count = struct.unpack_from('<I', hdr, 21)[0]
    ht_data = pack.read_xor(43, hash_count * 5)
    bucket = cdbm_hash(db_key) % hash_count
    off5 = bucket * 5
    chain = struct.unpack_from('<I', ht_data, off5+1)[0] + (ht_data[off5] << 32)

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
        np_ = struct.unpack_from('<I', ch, 11)[0] + (ch[10] << 32)
        if np_ == 0 or np_ == chain: break
        chain = np_

    if raw_value is None:
        return None

    decrypted = decrypt_inner_db(raw_value)
    if decrypted is None or decrypted[:5] != b'PLPcK':
        return None

    inner_hash_count = struct.unpack_from('<I', decrypted, 21)[0]
    texts = {}
    t0 = time.time()

    for bi in range(inner_hash_count):
        off = 43 + bi * 5
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

        if (bi + 1) % 10000 == 0:
            elapsed = time.time() - t0
            print(f"  ... bucket {bi+1:,}/{inner_hash_count:,} ({(bi+1)*100//inner_hash_count}%) {len(texts):,} texts ({elapsed:.1f}s)")

    return texts

def main():
    print("=" * 60)
    print("  Extract text from ChaosZero data.pack")
    print("=" * 60)

    pack = MultiVolumePack(PACK_DIR)
    print(f"  Pack: {len(pack.volumes)} volumes, {pack.total_size/1024**3:.2f} GB")

    for lang, key_name in [('EN', b'text/en/text.db'), ('KO', b'text/ko/text.db')]:
        print(f"\n[Extracting {lang}]...")
        t0 = time.time()
        texts = extract_text(pack, key_name)
        elapsed = time.time() - t0

        if texts:
            print(f"  {lang}: {len(texts):,} texts extracted in {elapsed:.1f}s")
            out_path = os.path.join(SCRIPT_DIR, f"text_{lang.lower()}_extracted.tsv")
            with open(out_path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f, delimiter='\t')
                writer.writerow(['text_id', lang.lower()])
                for tid, text in sorted(texts.items()):
                    writer.writerow([tid, text])
            print(f"  Saved: {out_path}")

            # Also create ES TSV with just dictionary for immediate rebuild
            if lang == 'EN':
                _create_initial_es_tsv(texts)

    pack.close()
    print("\nDone!")

def _create_initial_es_tsv(en_texts):
    """Create initial ES TSV with offline dictionary matches."""
    DICT = {
        "OK": "Aceptar", "Cancel": "Cancelar", "Close": "Cerrar",
        "Settings": "Configuraci\u00f3n", "Start": "Iniciar", "Exit": "Salir",
        "Back": "Volver", "Next": "Siguiente", "Previous": "Anterior",
        "Home": "Inicio", "Menu": "Men\u00fa", "Shop": "Tienda",
        "Mail": "Correo", "Bag": "Bolsa", "Inventory": "Inventario",
        "Equipment": "Equipamiento", "Skill": "Habilidad", "Skills": "Habilidades",
        "Quest": "Misi\u00f3n", "Quests": "Misiones",
        "Daily": "Diario", "Weekly": "Semanal",
        "Summon": "Invocar", "Enhance": "Mejorar", "Evolve": "Evolucionar",
        "Sell": "Vender", "Buy": "Comprar",
        "Premium": "Premium", "Free": "Gratis",
        "Reward": "Recompensa", "Rewards": "Recompensas",
        "Gift": "Regalo", "Gifts": "Regalos",
        "Event": "Evento", "Events": "Eventos",
        "Notice": "Aviso", "Notification": "Notificaci\u00f3n",
        "Friend": "Amigo", "Friends": "Amigos",
        "Guild": "Gremio", "Ranking": "Ranking",
        "Season": "Temporada", "Level": "Nivel",
        "Attack": "Ataque", "Defense": "Defensa", "Speed": "Velocidad",
        "Critical": "Cr\u00edtico", "Damage": "Da\u00f1o",
        "Boss": "Jefe", "Monster": "Monstruo",
        "Enemy": "Enemigo", "Ally": "Aliado",
        "Team": "Equipo", "Party": "Grupo",
        "Warrior": "Guerrero", "Mage": "Mago",
        "Sword": "Espada", "Shield": "Escudo",
        "Login": "Iniciar sesi\u00f3n", "Account": "Cuenta",
        "Server": "Servidor", "Language": "Idioma",
        "Loading": "Cargando", "Complete": "Completado",
        "Success": "\u00c9xito", "Failed": "Fallo",
        "Confirm": "Confirmar", "Accept": "Aceptar",
        "Story": "Historia", "Battle": "Batalla",
        "Auto": "Autom\u00e1tico", "Skip": "Saltar",
        "New": "Nuevo", "Hot": "Popular",
        "Select": "Seleccionar",
        "Claim": "Reclamar", "Collect": "Recolectar",
        "Send": "Enviar", "Receive": "Recibir",
        "Delete": "Eliminar", "Create": "Crear",
        "Join": "Unirse", "Leave": "Salir",
        "Online": "En l\u00ednea", "Offline": "Sin conexi\u00f3n",
        "Remaining": "Restante", "Available": "Disponible",
        "Required": "Requerido",
        "Normal": "Normal", "Hard": "Dif\u00edcil",
        "Chapter": "Cap\u00edtulo", "Episode": "Episodio",
        "Dungeon": "Mazmorra", "Town": "Pueblo",
        "Hero": "H\u00e9roe", "Character": "Personaje",
        "Equip": "Equipar", "Use": "Usar",
        "Retry": "Reintentar", "Reset": "Reiniciar",
        "Update": "Actualizaci\u00f3n",
        "Maintenance": "Mantenimiento",
        "Help": "Ayuda",
        "Profile": "Perfil",
        "Graphics": "Gr\u00e1ficos", "Sound": "Sonido",
        "Volume": "Volumen", "Resolution": "Resoluci\u00f3n",
        "Fullscreen": "Pantalla completa",
        "Rare": "Raro", "Epic": "\u00c9pico",
        "Legendary": "Legendario",
        "Common": "Com\u00fan",
    }

    es_map = {}
    hits = 0
    for tid, en_text in en_texts.items():
        s = en_text.strip()
        if s in DICT:
            es_map[tid] = DICT[s]
            hits += 1
        elif s.upper() in DICT:
            es_map[tid] = DICT[s.upper()]
            hits += 1

    print(f"\n  Offline dictionary: {hits:,} matches from {len(en_texts):,} EN texts")

    with open(OUTPUT_ES_TSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['text_id', 'spanish'])
        for tid, es in sorted(es_map.items()):
            writer.writerow([tid, es])
    print(f"  Initial ES TSV saved: {OUTPUT_ES_TSV} ({len(es_map):,} entries)")
    print(f"  (Run translate_incremental.py to add more translations)")

if __name__ == '__main__':
    main()
