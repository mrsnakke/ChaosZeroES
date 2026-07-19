"""
Rebuild data.pack: extract all, patch EN text.db with Spanish, write back.
Based on ChaosZero-Toolkit by NineS11942.
"""
import struct, os, sys, time, csv, re
from pack_crypto import (
    MultiVolumePack, cdbm_hash, pack_xor_crypt, inner_xor_crypt,
    find_inner_xor_offset, PACK_XOR_KEY, INNER_XOR_KEY
)
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

EN_DB_KEY = b"text/en/text.db"
VOLUME_SIZE = 1073741824

# ═══════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════
class PackEntry:
    __slots__ = ['key', 'value', 'flags', 'meta']
    def __init__(self, key, value, flags, meta=b''):
        self.key = key
        self.value = value
        self.flags = flags
        self.meta = meta


class TextEntry:
    __slots__ = ['key_bytes', 'value_bytes', 'flags', 'is_meta']
    def __init__(self, key_bytes, value_bytes, flags):
        self.key_bytes = key_bytes
        self.value_bytes = value_bytes
        self.flags = flags
        self.is_meta = key_bytes.startswith(b'\t')


# ═══════════════════════════════════════════════════════════════════════
# Step 1: Extract all entries
# ═══════════════════════════════════════════════════════════════════════
def extract_all_files(pack_dir, progress_cb=None):
    pack = MultiVolumePack(pack_dir)
    try:
        if progress_cb:
            progress_cb(f"Pack: {len(pack.volumes)} volumes, {pack.total_size/1024**3:.2f} GB")

        hdr = pack.read_xor(0, 38)
        assert hdr[:5] == b'PLPcK', "Invalid pack header"
        hash_count = struct.unpack_from('<I', hdr, 21)[0]

        ver5 = pack.read_xor(38, 5)
        assert ver5[4] == 1

        ht_data = pack.read_xor(43, hash_count * 5)
        entries = []
        last_report = time.time()

        for bi in range(hash_count):
            now = time.time()
            if now - last_report > 5:
                if progress_cb:
                    pct = bi * 100 // hash_count
                    progress_cb(f"Extrayendo entradas: {bi:,}/{hash_count:,} ({pct}%, {len(entries):,} entries)")
                last_report = now

            off5 = bi * 5
            ptr_hi = ht_data[off5]
            ptr_lo = struct.unpack_from('<I', ht_data, off5 + 1)[0]
            file_offset = ptr_lo + (ptr_hi << 32)
            if file_offset == 0:
                continue

            chain_offset = file_offset
            safety = 0
            while chain_offset > 0 and chain_offset + 15 <= pack.total_size and safety < 1000:
                safety += 1
                chunk_hdr = pack.read_xor(chain_offset, 15)
                data_size = struct.unpack_from('<I', chunk_hdr, 0)[0]
                flags = chunk_hdr[4]
                key_length = chunk_hdr[5]
                value_size = struct.unpack_from('<I', chunk_hdr, 6)[0]
                next_hi = chunk_hdr[10]
                next_lo = struct.unpack_from('<I', chunk_hdr, 11)[0]
                next_ptr = next_lo + (next_hi << 32)

                if data_size == 0 or key_length == 0:
                    break
                if data_size > 200_000_000:
                    break

                total_read = key_length + value_size
                kv_data = pack.read_xor(chain_offset + 15, total_read)
                key_data = kv_data[:key_length]
                value_data = kv_data[key_length:key_length + value_size]

                entries.append(PackEntry(key_data, value_data, flags))
                if next_ptr == 0 or next_ptr == chain_offset:
                    break
                chain_offset = next_ptr

        if progress_cb:
            progress_cb(f"Extraction done: {len(entries):,} entries")

        return entries, hdr, ver5, hash_count
    finally:
        pack.close()


# ═══════════════════════════════════════════════════════════════════════
# Step 2: Patch EN text.db with Spanish translations
# ═══════════════════════════════════════════════════════════════════════
def process_en_to_es(entries, tsv_path, progress_cb=None):
    en_idx = None
    for i, e in enumerate(entries):
        if e.key == EN_DB_KEY:
            en_idx = i
            break

    if en_idx is None:
        raise RuntimeError("text/en/text.db not found in pack entries")

    if progress_cb:
        progress_cb(f"EN entry[{en_idx}]: {len(entries[en_idx].value):,} bytes")

    ko_raw = entries[en_idx].value
    ko_inner_off = find_inner_xor_offset(ko_raw[:64])
    if ko_inner_off is None:
        raise RuntimeError("EN Inner XOR offset detection failed")

    ko_decrypted = inner_xor_crypt(ko_raw, ko_inner_off)
    assert ko_decrypted[:5] == b'PLPcK'

    inner_hash_count = struct.unpack_from('<I', ko_decrypted, 21)[0]
    inner_header_38 = ko_decrypted[:38]
    inner_ver_5 = ko_decrypted[38:43]

    ht_start = 43
    text_buckets = {}
    total_parsed = 0

    for bi in range(inner_hash_count):
        off = ht_start + bi * 5
        oh = ko_decrypted[off]
        ol = struct.unpack_from('<I', ko_decrypted, off + 1)[0]
        fo = ol + (oh << 32)
        if fo == 0:
            continue

        chain = fo
        bucket_list = []
        safety = 0
        while chain > 0 and chain + 15 <= len(ko_decrypted) and safety < 5000:
            safety += 1
            ds = struct.unpack_from('<I', ko_decrypted, chain)[0]
            flags = ko_decrypted[chain + 4]
            kl = ko_decrypted[chain + 5]
            vs = struct.unpack_from('<I', ko_decrypted, chain + 6)[0]
            nh = ko_decrypted[chain + 10]
            nl = struct.unpack_from('<I', ko_decrypted, chain + 11)[0]
            cnext = nl + (nh << 32)
            if ds == 0 or kl == 0:
                break

            cdata_off = chain + 15
            key_bytes = ko_decrypted[cdata_off:cdata_off + kl]
            value_bytes = ko_decrypted[cdata_off + kl:cdata_off + kl + vs]
            bucket_list.append(TextEntry(key_bytes, value_bytes, flags))
            total_parsed += 1
            if cnext == 0 or cnext == chain:
                break
            chain = cnext

        if bucket_list:
            text_buckets[bi] = bucket_list

    if progress_cb:
        progress_cb(f"Inner parse: {total_parsed:,} entries, {len(text_buckets):,} buckets")

    tsv_map = {}
    with open(tsv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            tid = row.get('text_id', '')
            en = row.get('en', '')
            es = row.get('spanish', '')
            if tid and es:
                tsv_map[tid] = (en, es)
    if progress_cb:
        progress_cb(f"TSV loaded: {len(tsv_map):,} translations")

    replaced = 0
    kept = 0
    for bi, tent_list in text_buckets.items():
        for tent in tent_list:
            if tent.is_meta:
                continue
            val = tent.value_bytes
            n1 = val.find(b'\x00')
            if n1 < 0:
                kept += 1
                continue
            text_id_bytes = val[:n1]
            rest = val[n1 + 1:]
            n2 = rest.find(b'\x00')
            trailing = rest[n2:] if n2 >= 0 else b''
            try:
                text_id_str = text_id_bytes.decode('utf-8')
            except Exception:
                kept += 1
                continue
            if text_id_str in tsv_map:
                en, es = tsv_map[text_id_str]
                orig_en = rest[:n2].decode('utf-8', errors='replace') if n2 >= 0 else rest.decode('utf-8', errors='replace')
                es = _restore_en_markup(orig_en, es)
                new_text = es.encode('utf-8')
                tent.value_bytes = text_id_bytes + b'\x00' + new_text + trailing
                replaced += 1
            else:
                kept += 1

    if progress_cb:
        progress_cb(f"Replaced: {replaced:,}, Kept original: {kept:,}")

    inner_chunks_start = 43 + inner_hash_count * 5
    new_ht = bytearray(inner_hash_count * 5)
    inner_chunk_buf = bytearray()

    for bi in sorted(text_buckets.keys()):
        tent_list = text_buckets[bi]
        first_offset = inner_chunks_start + len(inner_chunk_buf)
        ht_off = bi * 5
        new_ht[ht_off] = (first_offset >> 32) & 0xFF
        struct.pack_into('<I', new_ht, ht_off + 1, first_offset & 0xFFFFFFFF)

        for i, tent in enumerate(tent_list):
            kd = tent.key_bytes
            vd = tent.value_bytes
            kl = len(kd)
            vs = len(vd)
            ds = kl + vs + 15
            current = inner_chunks_start + len(inner_chunk_buf)
            next_off = (current + 15 + kl + vs) if i < len(tent_list) - 1 else 0
            hdr = bytearray(15)
            struct.pack_into('<I', hdr, 0, ds)
            hdr[4] = tent.flags
            hdr[5] = kl & 0xFF
            struct.pack_into('<I', hdr, 6, vs)
            hdr[10] = (next_off >> 32) & 0xFF
            struct.pack_into('<I', hdr, 11, next_off & 0xFFFFFFFF)
            inner_chunk_buf.extend(hdr)
            inner_chunk_buf.extend(kd)
            inner_chunk_buf.extend(vd)

    new_inner_plpck = bytearray()
    new_inner_plpck.extend(inner_header_38)
    new_inner_plpck.extend(inner_ver_5)
    new_inner_plpck.extend(new_ht)
    new_inner_plpck.extend(inner_chunk_buf)
    assert new_inner_plpck[:5] == b'PLPcK'

    new_inner_offset = len(new_inner_plpck) % 256
    encrypted_inner = inner_xor_crypt(bytes(new_inner_plpck), new_inner_offset)
    test_rt = inner_xor_crypt(encrypted_inner[:5], new_inner_offset)
    assert test_rt == b'PLPcK'

    entries[en_idx].value = encrypted_inner
    if progress_cb:
        progress_cb(f"EN entry replaced: {len(ko_raw):,} -> {len(encrypted_inner):,} bytes")

    return replaced


# ═══════════════════════════════════════════════════════════════════════
# Step 3: Streaming pack writer
# ═══════════════════════════════════════════════════════════════════════
class StreamingPackWriter:
    def __init__(self, output_dir, volume_size=VOLUME_SIZE):
        self.output_dir = output_dir
        self.volume_size = volume_size
        self.global_offset = 0
        self.current_vol = 0
        self.current_vol_written = 0
        self._fh = None
        os.makedirs(output_dir, exist_ok=True)

    def _open_volume(self, vol_idx):
        if self._fh:
            self._fh.close()
        name = "data.pack" if vol_idx == 0 else f"data.pack~{vol_idx}"
        self._fh = open(os.path.join(self.output_dir, name), 'wb')
        self.current_vol = vol_idx
        self.current_vol_written = 0

    def write_encrypted(self, plaintext):
        remaining = len(plaintext)
        pos = 0
        while remaining > 0:
            if self._fh is None or self.current_vol_written >= self.volume_size:
                self._open_volume(self.global_offset // self.volume_size)
            can_write = min(remaining, self.volume_size - self.current_vol_written)
            chunk = plaintext[pos:pos + can_write]
            self._fh.write(pack_xor_crypt(chunk, self.global_offset))
            self.global_offset += can_write
            self.current_vol_written += can_write
            pos += can_write
            remaining -= can_write

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None
        return self.global_offset


def rebuild_and_write(entries, orig_header, orig_ver5, hash_count, output_dir, progress_cb=None):
    buckets = {}
    for i, entry in enumerate(entries):
        bucket = cdbm_hash(entry.key) % hash_count
        buckets.setdefault(bucket, []).append(i)

    fixed_area = 38 + 5 + hash_count * 5
    hash_table = bytearray(hash_count * 5)
    chunk_plan = []
    running_offset = fixed_area

    for bi in sorted(buckets.keys()):
        entry_indices = buckets[bi]
        first_offset = running_offset
        ht_off = bi * 5
        hash_table[ht_off] = (first_offset >> 32) & 0xFF
        struct.pack_into('<I', hash_table, ht_off + 1, first_offset & 0xFFFFFFFF)

        for ci, ei in enumerate(entry_indices):
            entry = entries[ei]
            chunk_total = 15 + len(entry.key) + len(entry.value) + len(entry.meta)
            current = running_offset
            next_off = (current + chunk_total) if ci < len(entry_indices) - 1 else 0
            chunk_plan.append((ei, current, next_off))
            running_offset += chunk_total

    total_size = running_offset
    if progress_cb:
        progress_cb(f"Rebuilding: {total_size:,} bytes ({total_size/1024**3:.2f} GB)")

    writer = StreamingPackWriter(output_dir)
    writer.write_encrypted(bytes(orig_header))
    writer.write_encrypted(orig_ver5)
    writer.write_encrypted(bytes(hash_table))

    last_report = time.time()
    written_chunks = 0

    for plan_idx, (ei, expected_offset, next_off) in enumerate(chunk_plan):
        assert writer.global_offset == expected_offset
        entry = entries[ei]
        kl = len(entry.key)
        vs = len(entry.value)
        ms = len(entry.meta)
        hdr = bytearray(15)
        struct.pack_into('<I', hdr, 0, kl + vs + 15 + ms)
        hdr[4] = entry.flags
        hdr[5] = kl & 0xFF
        struct.pack_into('<I', hdr, 6, vs)
        hdr[10] = (next_off >> 32) & 0xFF
        struct.pack_into('<I', hdr, 11, next_off & 0xFFFFFFFF)
        writer.write_encrypted(bytes(hdr))
        writer.write_encrypted(entry.key)
        writer.write_encrypted(entry.value)
        if ms > 0:
            writer.write_encrypted(entry.meta)
        written_chunks += 1
        now = time.time()
        if now - last_report > 5:
            pct = written_chunks / len(chunk_plan) * 100
            if progress_cb:
                progress_cb(f"Escribiendo: {written_chunks:,}/{len(chunk_plan):,} ({pct:.1f}%)")
            last_report = now

    final_size = writer.close()
    assert final_size == total_size
    if progress_cb:
        progress_cb(f"Write done: {final_size:,} bytes, {written_chunks:,} chunks")
    return total_size


# ═══════════════════════════════════════════════════════════════════════
# Step 4: Verify
# ═══════════════════════════════════════════════════════════════════════
def verify_pack(output_dir, entries, progress_cb=None):
    pack = MultiVolumePack(output_dir)
    try:
        hdr = pack.read_xor(0, 38)
        assert hdr[:5] == b'PLPcK'
        hash_count = struct.unpack_from('<I', hdr, 21)[0]

        ht_data = pack.read_xor(43, hash_count * 5)
        total = 0
        for bi in range(hash_count):
            off5 = bi * 5
            fo = struct.unpack_from('<I', ht_data, off5 + 1)[0] + (ht_data[off5] << 32)
            if fo == 0:
                continue
            chain = fo
            safety = 0
            while chain > 0 and chain + 15 <= pack.total_size and safety < 1000:
                safety += 1
                ch = pack.read_xor(chain, 15)
                ds = struct.unpack_from('<I', ch, 0)[0]
                if ds == 0 or ch[5] == 0:
                    break
                total += 1
                np_ = struct.unpack_from('<I', ch, 11)[0] + (ch[10] << 32)
                if np_ == 0 or np_ == chain:
                    break
                chain = np_

        ok = total == len(entries)
        if progress_cb:
            progress_cb(f"Verify: {'OK' if ok else 'FAIL'} entries: {total:,} / {len(entries):,}")
        return ok
    finally:
        pack.close()


# ═══════════════════════════════════════════════════════════════════════
# Full pipeline
# ═══════════════════════════════════════════════════════════════════════
def run_rebuild(pack_dir, tsv_path, output_dir, progress_cb=None):
    if progress_cb:
        progress_cb("Extrayendo todas las entradas del pack...")
    entries, orig_header, orig_ver5, hash_count = extract_all_files(pack_dir, progress_cb)

    if progress_cb:
        progress_cb("Aplicando traducciones espanoles...")
    replaced = process_en_to_es(entries, tsv_path, progress_cb)

    if progress_cb:
        progress_cb("Reescribiendo data.pack...")
    total_size = rebuild_and_write(entries, orig_header, orig_ver5, hash_count, output_dir, progress_cb)

    if progress_cb:
        progress_cb("Verificando pack...")
    ok = verify_pack(output_dir, entries, progress_cb)

    return {'ok': ok, 'replaced': replaced, 'total_size': total_size}
