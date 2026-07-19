"""
Patch story.db entries: fill text_es fields.
Each story.db is an inner PLPcK hash table whose values are JSON arrays of story lines.
"""
import struct, json, re
from collections import defaultdict
from pack_crypto import inner_xor_crypt, find_inner_xor_offset
from translator import SHORTEN_MAP

MARKUP_RE = re.compile(r'\{[^}]+\}|<[^>]+>')

def _restore_en_markup(en_text, es_text):
    en_tokens = MARKUP_RE.findall(en_text)
    es_tokens = MARKUP_RE.findall(es_text)
    if not en_tokens:
        return es_text
    if len(en_tokens) == len(es_tokens):
        for en_tok, es_tok in zip(en_tokens, es_tokens):
            if en_tok != es_tok:
                es_text = es_text.replace(es_tok, en_tok, 1)
    return es_text

STORY_PREFIX = "storydb:"


def _extract_json_balanced(raw_str):
    """Find the balanced JSON array end and parse it."""
    depth = 0
    in_str = False
    esc = False
    end_pos = -1
    for i, c in enumerate(raw_str):
        if esc:
            esc = False
            continue
        if c == '\\' and in_str:
            esc = True
            continue
        if c == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                end_pos = i + 1
                break
    if end_pos <= 0:
        return None
    try:
        items = json.loads(raw_str[:end_pos])
        if not isinstance(items, list):
            items = [items]
        return items
    except json.JSONDecodeError:
        return None


def _rebuild_inner_plpck(old_dec, value_updater_fn):
    """
    Rebuild an inner PLPcK structure, applying value_updater_fn to each non-meta entry.
    """
    assert old_dec[:5] == b'PLPcK'
    inner_header_38 = old_dec[:38]
    inner_ver_5 = old_dec[38:43]
    inner_hash_count = struct.unpack_from('<I', old_dec, 21)[0]
    ht_size = inner_hash_count * 5
    old_ht = old_dec[43:43 + ht_size]
    chunks_start = 43 + ht_size

    new_chunks = bytearray()
    new_ht = bytearray(ht_size)
    total_entries = 0

    for bi in range(inner_hash_count):
        off = bi * 5
        oh = old_ht[off]
        ol = struct.unpack_from('<I', old_ht, off + 1)[0]
        fo = ol + (oh << 32)
        if fo == 0:
            continue

        chain = fo
        bucket_text_entries = []
        safety = 0
        while chain > 0 and chain + 15 <= len(old_dec) and safety < 5000:
            safety += 1
            ds = struct.unpack_from('<I', old_dec, chain)[0]
            flags = old_dec[chain + 4]
            kl = old_dec[chain + 5]
            vs = struct.unpack_from('<I', old_dec, chain + 6)[0]
            nh = old_dec[chain + 10]
            nl = struct.unpack_from('<I', old_dec, chain + 11)[0]
            cnext = nl + (nh << 32)
            if ds == 0 or kl == 0:
                break
            cdata_off = chain + 15
            key_bytes = old_dec[cdata_off:cdata_off + kl]
            value_bytes = old_dec[cdata_off + kl:cdata_off + kl + vs]

            if key_bytes.startswith(b'\t'):
                new_vb = value_bytes
            else:
                new_vb = value_updater_fn(value_bytes)
                if new_vb is None:
                    new_vb = value_bytes

            bucket_text_entries.append((key_bytes, new_vb, flags))
            total_entries += 1

            if cnext == 0 or cnext == chain:
                break
            chain = cnext

        if bucket_text_entries:
            first_offset = chunks_start + len(new_chunks)
            new_ht[bi * 5] = (first_offset >> 32) & 0xFF
            struct.pack_into('<I', new_ht, bi * 5 + 1, first_offset & 0xFFFFFFFF)

            for i, (kb, vb, fl) in enumerate(bucket_text_entries):
                kl = len(kb)
                vs = len(vb)
                ds = kl + vs + 15
                current = chunks_start + len(new_chunks)
                next_off = (current + 15 + kl + vs) if i < len(bucket_text_entries) - 1 else 0
                hdr = bytearray(15)
                struct.pack_into('<I', hdr, 0, ds)
                hdr[4] = fl
                hdr[5] = kl & 0xFF
                struct.pack_into('<I', hdr, 6, vs)
                hdr[10] = (next_off >> 32) & 0xFF
                struct.pack_into('<I', hdr, 11, next_off & 0xFFFFFFFF)
                new_chunks.extend(hdr)
                new_chunks.extend(kb)
                new_chunks.extend(vb)

    new_inner = bytearray()
    new_inner.extend(inner_header_38)
    new_inner.extend(inner_ver_5)
    new_inner.extend(new_ht)
    new_inner.extend(new_chunks)
    assert new_inner[:5] == b'PLPcK'

    inner_off = len(new_inner) % 256
    encrypted = inner_xor_crypt(bytes(new_inner), inner_off)
    return encrypted


def extract_story_texts(entries, progress_cb=None):
    """
    Extract all English texts from story.db entries.
    Returns story_text_map, patch_infos.
    """
    story_text_map = {}
    patch_infos = []

    for idx, entry in enumerate(entries):
        key_str = entry.key.decode('utf-8', errors='replace')
        if not key_str.endswith('story.db'):
            continue

        off = find_inner_xor_offset(entry.value[:64])
        if off is None:
            continue
        dec = inner_xor_crypt(entry.value, off)
        if dec[:5] != b'PLPcK':
            continue

        inner_hash_count = struct.unpack_from('<I', dec, 21)[0]

        for bi in range(inner_hash_count):
            boff = 43 + bi * 5
            oh = dec[boff]
            ol = struct.unpack_from('<I', dec, boff + 1)[0]
            fo = ol + (oh << 32)
            if fo == 0:
                continue

            chain = fo
            safety = 0
            while chain > 0 and chain + 15 <= len(dec) and safety < 5000:
                safety += 1
                ds = struct.unpack_from('<I', dec, chain)[0]
                flags = dec[chain + 4]
                kl = dec[chain + 5]
                vs = struct.unpack_from('<I', dec, chain + 6)[0]
                nh = dec[chain + 10]
                nl = struct.unpack_from('<I', dec, chain + 11)[0]
                cnext = nl + (nh << 32)
                if ds == 0 or kl == 0:
                    break
                cdata_off = chain + 15
                key_bytes = dec[cdata_off:cdata_off + kl]
                value_bytes = dec[cdata_off + kl:cdata_off + kl + vs]

                if not key_bytes.startswith(b'\t'):
                    val = value_bytes
                    n1 = val.find(b'\x00')
                    if n1 >= 0:
                        text_id = val[:n1].decode('utf-8', errors='replace')
                        rest = val[n1 + 1:]
                        if rest[:1] == b'\x00':
                            rest = rest[1:]
                        raw_str = rest.decode('utf-8', errors='replace')
                        items = _extract_json_balanced(raw_str)
                        if items is None:
                            items = []

                        for oi, item in enumerate(items):
                            if not isinstance(item, dict):
                                continue
                            en_text = item.get('text_en', '')
                            es_text = item.get('text_es', '')
                            if en_text and (not es_text or en_text != es_text):
                                ck = f"{STORY_PREFIX}{key_str}:{text_id}:{oi}"
                                story_text_map[ck] = en_text
                                patch_infos.append((idx, text_id, oi, raw_str, item, en_text))

                if cnext == 0 or cnext == chain:
                    break
                chain = cnext

    if progress_cb:
        progress_cb(f"Story DB: {len(story_text_map)} untranslated lines found")
    return story_text_map, patch_infos


def apply_story_patches(entries, patch_infos, glossary, progress_cb=None):
    """
    Apply Spanish translations from glossary to story.db entries.
    glossary: dict {english_text: spanish_text}
    Modifies entries in-place.
    """
    groups = defaultdict(list)
    for idx, text_id, oi, raw_str, item, en_text in patch_infos:
        groups[idx].append((text_id, oi, raw_str, item, en_text))

    total_patched = 0

    for idx, targets in groups.items():
        off = find_inner_xor_offset(entries[idx].value[:64])
        if off is None:
            continue
        dec = inner_xor_crypt(entries[idx].value, off)
        if dec[:5] != b'PLPcK':
            continue

        updates = defaultdict(dict)
        for text_id, oi, raw_str, item, en_text in targets:
            es_text = glossary.get(en_text, '')
            if es_text and es_text != en_text:
                es_text = _restore_en_markup(en_text, es_text)
                updates[text_id][oi] = (item, es_text)

        def value_updater(vb):
            nonlocal total_patched
            n1 = vb.find(b'\x00')
            if n1 < 0:
                return None
            tid = vb[:n1].decode('utf-8', errors='replace')
            if tid not in updates:
                return None
            rest = vb[n1 + 1:]
            if rest[:1] == b'\x00':
                rest = rest[1:]

            # Find JSON end in raw bytes (balanced bracket)
            depth = 0
            in_str = False
            esc = False
            json_end = -1
            for i, b in enumerate(rest):
                if esc:
                    esc = False
                    continue
                if b == 0x5C and in_str:  # backslash
                    esc = True
                    continue
                if b == 0x22:  # quote
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if b == 0x5B:  # [
                    depth += 1
                elif b == 0x5D:  # ]
                    depth -= 1
                    if depth == 0:
                        json_end = i + 1
                        break

            if json_end <= 0:
                return None

            json_bytes = rest[:json_end]
            trailing_bytes = rest[json_end:]

            try:
                items = json.loads(json_bytes.decode('utf-8'))
            except json.JSONDecodeError:
                return None
            if not isinstance(items, list):
                items = [items]

            changed = False
            for oi, (orig_item, es_text) in updates[tid].items():
                if oi < len(items) and isinstance(items[oi], dict):
                    en_orig = items[oi].get('text_en', '')
                    if en_orig != es_text:
                        if len(es_text) > len(en_orig) * 1.15:
                            for bad, good in SHORTEN_MAP.items():
                                es_text = es_text.replace(bad, good)
                        if len(es_text) > len(en_orig) * 1.15:
                            es_text = es_text[:max(len(en_orig), len(es_text) * 8 // 10)]
                        items[oi]['text_en'] = es_text
                        items[oi]['text_es'] = es_text
                        changed = True
                        total_patched += 1

            if not changed:
                return None

            new_json = json.dumps(items, ensure_ascii=False).encode('utf-8')
            return tid.encode('utf-8') + b'\x00\x00' + new_json + trailing_bytes

        new_encrypted = _rebuild_inner_plpck(dec, value_updater)
        entries[idx].value = new_encrypted

    if progress_cb:
        progress_cb(f"Story DB patched: {total_patched} lines")
    return total_patched
