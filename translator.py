"""
Translation engine: glossary-first, Google Translate fallback.
Persistent JSON glossary for offline reuse.
Optimized for high stability and connection pooling.
"""
import json, os, time, csv, re, random
from concurrent.futures import ThreadPoolExecutor, as_completed

# Match {placeholder} and <tag> markup
MARKUP_RE = re.compile(r'\{[^}]+\}|<[^>]+>')
# Match <br> and variants
BR_RE = re.compile(r'<\s*br\s*/?\s*>', re.IGNORECASE)

def _protect_br(text):
    """Replace <br> with safe markers before translation (Google removes them)."""
    brs = []
    def repl(m):
        brs.append(m.group(0))
        return f'\x00BR{len(brs)-1:04d}\x00'
    return BR_RE.sub(repl, text), brs

def _unprotect_br(text, brs):
    """Restore <br> markers after translation."""
    for i, orig in enumerate(brs):
        text = text.replace(f'\x00BR{i:04d}\x00', orig)
    return text

def _restore_en_markup(en_text, es_text):
    """Restore {placeholder} and <tag> tokens from en_text into es_text."""
    en_tokens = MARKUP_RE.findall(en_text)
    es_tokens = MARKUP_RE.findall(es_text)
    if not en_tokens:
        return es_text
    if len(en_tokens) == len(es_tokens):
        for en_tok, es_tok in zip(en_tokens, es_tokens):
            if en_tok != es_tok:
                es_text = es_text.replace(es_tok, en_tok, 1)
    return es_text

try:
    import requests
    USE_REQUESTS = True
except ImportError:
    USE_REQUESTS = False
    import urllib.request, urllib.parse
    import urllib.error

BATCH_SIZE = 20
MAX_WORKERS = 4
MAX_CHARS_PER_REQUEST = 5000
REQUEST_DELAY = 0.05

POST_FIXES = {
    "oportunidad de crear": "probabilidad de crear",
    "oportunidad de obtener": "probabilidad de obtener",
    "oportunidad de ganar": "probabilidad de ganar",
    "oportunidad de $Dibujar$": "probabilidad de $Dibujar$",
    "oportunidad de $Debilitar$": "probabilidad de $Debilitar$",
    "oportunidad de creaci\u00f3n de C\u00f3dices": "probabilidad de creaci\u00f3n de C\u00f3dices",
    "oportunidad cr\u00edtica": "probabilidad cr\u00edtica",
    "oportunidad critica": "probabilidad cr\u00edtica",
}

SHORTEN_MAP = {
    "se ha detectado": "detectado",
    "se han detectado": "detectados",
    "se ha recibido": "recibido",
    "se ha encontrado": "encontrado",
    "se ha completado": "completado",
    "se\u00f1al de identificaci\u00f3n": "se\u00f1al ID",
    "se\u00f1al de socorro": "se\u00f1al SOS",
    "se\u00f1al de rescate": "se\u00f1al rescate",
    "se\u00f1al de comunicaci\u00f3n": "se\u00f1al coms",
    "de las SS Nightmare": "SS Nightmare",
    "de los SS Nightmare": "SS Nightmare",
    "de la Estrella Oscura": "de Estrella Oscura",
    "agente de las SS": "agente SS",
    "agentes de las SS": "agentes SS",
    "a las 11 en punto": "a las 11",
    "a las 12 en punto": "a las 12",
    "a las 1 en punto": "a la 1",
    "a las 2 en punto": "a las 2",
    "a las 3 en punto": "a las 3",
    "a las 4 en punto": "a las 4",
    "a las 5 en punto": "a las 5",
    "a las 6 en punto": "a las 6",
    "a las 7 en punto": "a las 7",
    "a las 8 en punto": "a las 8",
    "a las 9 en punto": "a las 9",
    "a las 10 en punto": "a las 10",
    "para poder": "para",
    "tiene que": "debe",
    "tienen que": "deben",
    "a trav\u00e9s de": "v\u00eda",
    "debido a que": "por",
    "llevar a cabo": "hacer",
    "ser capaz de": "poder",
    "en el caso de que": "si",
    "a pesar de que": "aunque",
    "facciones que aparecen": "facciones presentes",
    "facciones que aparecer\u00e1n": "facciones entrantes",
}

ABBREVIATIONS = {
    "ATK", "DEF", "SPD", "CRIT", "EVA", "DMG", "AOE", "DOT", "DPS",
    "HP", "MP", "SP", "TP", "EXP", "LV", "MAX", "MIN",
    "PVP", "PVE", "NPC", "TB", "CD", "BGM", "SFX",
    "OK", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L",
    "M", "N", "\u00d1", "O", "P", "Q", "R", "S", "T", "U", "V", "W",
    "X", "Y", "Z",
}

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
    "Sell": "Vender", "Buy": "Comprar", "Free": "Gratis",
    "Reward": "Recompensa", "Rewards": "Recompensas", "Gift": "Regalo",
    "Event": "Evento", "Events": "Eventos", "Notice": "Aviso",
    "Friend": "Amigo", "Friends": "Amigos", "Guild": "Gremio",
    "Level": "Nivel", "Attack": "Ataque", "Defense": "Defensa",
    "Critical": "Cr\u00edtico", "Damage": "Da\u00f1o", "Raid": "Raid",
    "Boss": "Jefe", "Monster": "Monstruo", "Enemy": "Enemigo",
    "Team": "Equipo", "Party": "Grupo", "Support": "Soporte",
    "Tank": "Tanque", "Healer": "Sanador", "Warrior": "Guerrero",
    "Mage": "Mago", "Sword": "Espada", "Armor": "Armadura",
    "Loading": "Cargando", "Success": "\u00c9xito", "Failed": "Fallo",
    "Obtained": "Obtenido", "Use": "Usar", "Confirm": "Confirmar",
    "Remaining time": "Tiempo restante", "New": "Nuevo",
}


def _is_abbrev(text):
    s = text.strip()
    return len(s) <= 6 and s.isalpha() and s.upper() == s and len(s) > 1


def _post_fix(text, en_len=None):
    for bad, good in POST_FIXES.items():
        text = text.replace(bad, good)
    if en_len is not None and len(text) > en_len * 1.15:
        for bad, good in SHORTEN_MAP.items():
            text = text.replace(bad, good)
    return text


# ═══════════════════════════════════════════════════════════════════════
# Glossary I/O
# ═══════════════════════════════════════════════════════════════════════
def load_glossary(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    entries = data.get('entries', {})
    _cleanup_glossary_placeholders(entries)
    return entries


def _cleanup_glossary_placeholders(entries):
    fixed = 0
    for en_text, es_text in entries.items():
        if en_text == es_text:
            continue
        fixed_es = _restore_en_markup(en_text, es_text)
        if fixed_es != es_text:
            entries[en_text] = fixed_es
            fixed += 1
    if fixed:
        print(f"Glossary markup cleanup: {fixed} entries fixed")


def save_glossary(entries, path, game_version=""):
    data = {
        "version": 2,
        "game_version": game_version,
        "entries": entries,
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def load_translations_tsv(path):
    data = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                tid = row.get('text_id', '')
                en = row.get('en', '')
                es = row.get('spanish', '')
                if tid and en and es:
                    data[tid] = (en, es)
    return data


def save_translations_tsv(texts_map, path):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['text_id', 'en', 'spanish'])
        for tid in sorted(texts_map):
            en, es = texts_map[tid]
            writer.writerow([tid, en, es])


# ═══════════════════════════════════════════════════════════════════════
# Google Translate
# ═══════════════════════════════════════════════════════════════════════
def _google_translate_batch(texts, src='en', dest='es-MX', session=None):
    separator = " ||| "
    combined = separator.join(t.replace("\n", " ") for t in texts)
    params = {
        'client': 'gtx',
        'sl': src,
        'tl': dest,
        'dt': 't',
        'q': combined[:MAX_CHARS_PER_REQUEST],
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    backoff = 1.0
    for attempt in range(3):
        try:
            if USE_REQUESTS and session:
                resp = session.get(
                    "https://translate.googleapis.com/translate_a/single",
                    params=params, headers=headers, timeout=12
                )
                if resp.status_code == 429:
                    time.sleep(backoff + random.uniform(0.1, 0.5))
                    backoff *= 2
                    continue
                resp.raise_for_status()
                content = resp.text
            else:
                full_url = "https://translate.googleapis.com/translate_a/single?" + urllib.parse.urlencode(params)
                req = urllib.request.Request(full_url, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=12) as resp:
                        content = resp.read().decode('utf-8')
                except urllib.error.HTTPError as e:
                    if e.code == 429:
                        time.sleep(backoff + random.uniform(0.1, 0.5))
                        backoff *= 2
                        continue
                    raise

            data = json.loads(content)
            if data and data[0]:
                result = ''.join(part[0] for part in data[0] if part[0])
                parts = re.split(r'\s*(?:\|[ |]*){3,}\s*', result.strip())
                return [p.strip() for p in parts if p.strip()]
        except Exception:
            time.sleep(backoff)
            backoff *= 1.5
    return None


def _translate_single(text, src='en', dest='es-MX', session=None):
    res = _google_translate_batch([text], src, dest, session)
    if res and len(res) == 1:
        return res[0]
    return None


def _translate_batch_adaptive(texts, src='en', dest='es-MX', session=None):
    if not texts:
        return []

    res = _google_translate_batch(texts, src, dest, session)
    if res and len(res) == len(texts):
        return res

    if len(texts) <= 1:
        single = _translate_single(texts[0], src, dest, session)
        return [single] if single else [texts[0]]

    mid = len(texts) // 2
    left = _translate_batch_adaptive(texts[:mid], src, dest, session)
    right = _translate_batch_adaptive(texts[mid:], src, dest, session)
    return left + right


# ═══════════════════════════════════════════════════════════════════════
# Change detection
# ═══════════════════════════════════════════════════════════════════════
def detect_changes(en_current, prev_translations):
    new_texts = {}
    changed_texts = {}
    unchanged = 0

    for tid, en_text in en_current.items():
        if tid not in prev_translations:
            new_texts[tid] = en_text
        else:
            prev_en, _ = prev_translations[tid]
            if prev_en != en_text:
                changed_texts[tid] = en_text
            else:
                unchanged += 1

    return new_texts, changed_texts, unchanged


# ═══════════════════════════════════════════════════════════════════════
# Main translation pipeline
# ═══════════════════════════════════════════════════════════════════════
def translate_all(en_texts, glossary, progress_cb=None):
    translations = {}
    glossary_hits = 0
    to_translate = []

    for tid, en_text in en_texts.items():
        s = en_text.strip()
        if _is_abbrev(en_text) or en_text == 'none':
            translations[tid] = (en_text, en_text)
            glossary_hits += 1
            continue

        if en_text in glossary and glossary[en_text] != en_text:
            es = _restore_en_markup(en_text, glossary[en_text])
            translations[tid] = (en_text, es)
            glossary_hits += 1
            continue

        if s in OFFLINE_DICT:
            es = _restore_en_markup(en_text, OFFLINE_DICT[s])
            translations[tid] = (en_text, es)
            glossary_hits += 1
            continue
        if s.upper() in OFFLINE_DICT:
            es = _restore_en_markup(en_text, OFFLINE_DICT[s.upper()])
            translations[tid] = (en_text, es)
            glossary_hits += 1
            continue

        to_translate.append((tid, en_text))

    total_to_translate = len(to_translate)
    if total_to_translate == 0:
        if progress_cb:
            progress_cb(f"Todo resuelto localmente ({glossary_hits:,} hits, 0 en red)")
        return translations

    if progress_cb:
        pct = glossary_hits * 100 // len(en_texts) if en_texts else 0
        progress_cb(f"Glosario/Offline: {glossary_hits:,} hits ({pct}%), traduciendo {total_to_translate:,} online...")

    translated = 0
    batches = [to_translate[i:i + BATCH_SIZE] for i in range(0, total_to_translate, BATCH_SIZE)]

    session = requests.Session() if USE_REQUESTS else None

    def do_batch(batch):
        tids, texts = zip(*batch)
        abbrevs = [(tid, txt) for tid, txt in zip(tids, texts) if _is_abbrev(txt)]
        to_tr = [(tid, txt) for tid, txt in zip(tids, texts) if not _is_abbrev(txt)]
        out = []
        for tid, txt in abbrevs:
            out.append((tid, txt, txt))
        if to_tr:
            protected_texts = []
            all_brs = []
            for _, txt in to_tr:
                p, brs = _protect_br(txt)
                protected_texts.append(p)
                all_brs.append(brs)
            res = _translate_batch_adaptive(protected_texts, 'en', 'es-MX', session)
            for (tid, txt), tr, brs in zip(to_tr, res, all_brs):
                tr_unprotected = _unprotect_br(tr, brs)
                es = _post_fix(tr_unprotected, len(txt))
                es = _restore_en_markup(txt, es)
                out.append((tid, txt, es))
        return out

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(do_batch, b): i for i, b in enumerate(batches)}
        done_count = 0
        for f in as_completed(futures):
            batch_results = f.result()
            for tid, en_text, es_text in batch_results:
                translations[tid] = (en_text, es_text)
                glossary[en_text] = es_text
            translated += len(batch_results)
            done_count += len(batch_results)
            if progress_cb and done_count % (BATCH_SIZE * MAX_WORKERS * 3) < BATCH_SIZE:
                pct = min(done_count * 100 // total_to_translate, 99)
                progress_cb(f"Traduciendo: {done_count:,}/{total_to_translate:,} ({pct}%)")

    if USE_REQUESTS and session:
        session.close()

    if progress_cb:
        progress_cb(f"Traduccion completa: {translated:,} procesados en red")

    return translations


def estimate_time(num_texts, glossary_size=0):
    need_online = max(0, num_texts - glossary_size)
    batches = (need_online + BATCH_SIZE - 1) // BATCH_SIZE
    return batches * 1.0
