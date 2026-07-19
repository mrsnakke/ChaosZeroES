"""
Extract English text from data.pack.
Fast hash lookup directly to text/en/text.db — no full scan.
"""
import struct, time
from pack_crypto import (
    MultiVolumePack, cdbm_hash, inner_xor_crypt, find_inner_xor_offset
)

EN_DB_KEY = b"text/en/text.db"


def _decrypt_inner_db(raw_value):
    if len(raw_value) < 5:
        return None
    boff = find_inner_xor_offset(raw_value[:64])
    if boff is None:
        return None
    decrypted = inner_xor_crypt(raw_value, boff)
    if decrypted[:5] != b'PLPcK':
        return None
    return decrypted


def _parse_inner_texts(decrypted):
    inner_hash_count = struct.unpack_from('<I', decrypted, 21)[0]
    texts = {}
    for bi in range(inner_hash_count):
        off = 43 + bi * 5
        oh = decrypted[off]
        ol = struct.unpack_from('<I', decrypted, off + 1)[0]
        fo = ol + (oh << 32)
        if fo == 0:
            continue
        chain = fo
        safety = 0
        while chain > 0 and chain + 15 <= len(decrypted) and safety < 5000:
            safety += 1
            ds = struct.unpack_from('<I', decrypted, chain)[0]
            kl = decrypted[chain + 5]
            vs = struct.unpack_from('<I', decrypted, chain + 6)[0]
            nh = decrypted[chain + 10]
            nl = struct.unpack_from('<I', decrypted, chain + 11)[0]
            cnext = nl + (nh << 32)
            if ds == 0 or kl == 0:
                break
            cdata_off = chain + 15
            key_bytes = decrypted[cdata_off:cdata_off + kl]
            value_bytes = decrypted[cdata_off + kl:cdata_off + kl + vs]
            if not key_bytes.startswith(b'\t'):
                val = value_bytes
                n1 = val.find(b'\x00')
                if n1 >= 0:
                    text_id = val[:n1].decode('utf-8', errors='replace')
                    rest = val[n1 + 1:]
                    n2 = rest.find(b'\x00')
                    text = rest[:n2].decode('utf-8', errors='replace') if n2 >= 0 else rest.decode('utf-8', errors='replace')
                    if text.strip():
                        texts[text_id] = text
            if cnext == 0 or cnext == chain:
                break
            chain = cnext
    return texts


def extract_en_text(pack_dir, progress_cb=None):
    """
    Extract English text from data.pack.
    Returns dict{text_id: en_text}.
    """
    pack = MultiVolumePack(pack_dir)
    try:
        if progress_cb:
            progress_cb("Abriendo data.pack...")

        hdr = pack.read_xor(0, 38)
        assert hdr[:5] == b'PLPcK', "Invalid pack header"
        hash_count = struct.unpack_from('<I', hdr, 21)[0]
        ht_data = pack.read_xor(43, hash_count * 5)

        if progress_cb:
            progress_cb(f"Pack: {hash_count:,} buckets, buscando text/en/text.db...")

        bucket = cdbm_hash(EN_DB_KEY) % hash_count
        off5 = bucket * 5
        ptr_hi = ht_data[off5]
        ptr_lo = struct.unpack_from('<I', ht_data, off5 + 1)[0]
        chain = ptr_lo + (ptr_hi << 32)

        raw_value = None
        safety = 0
        while chain > 0 and chain + 15 <= pack.total_size and safety < 1000:
            safety += 1
            ch = pack.read_xor(chain, 15)
            kl = ch[5]
            vs = struct.unpack_from('<I', ch, 6)[0]
            key = pack.read_xor(chain + 15, kl)
            if key == EN_DB_KEY:
                raw_value = pack.read_xor(chain + 15 + kl, vs)
                break
            nh = ch[10]
            nl = struct.unpack_from('<I', ch, 11)[0]
            np_ = nl + (nh << 32)
            if np_ == 0 or np_ == chain:
                break
            chain = np_

        if raw_value is None:
            raise RuntimeError("text/en/text.db not found in pack")

        if progress_cb:
            progress_cb("Descifrando text.db...")

        decrypted = _decrypt_inner_db(raw_value)
        if decrypted is None:
            raise RuntimeError("Failed to decrypt text/en/text.db")

        texts = _parse_inner_texts(decrypted)

        if progress_cb:
            progress_cb(f"Extraidos {len(texts):,} textos EN")

        return texts
    finally:
        pack.close()


def get_pack_info(pack_dir):
    """Get basic pack info without extracting text."""
    pack = MultiVolumePack(pack_dir)
    try:
        hdr = pack.read_xor(0, 38)
        assert hdr[:5] == b'PLPcK', "Invalid pack header"
        hash_count = struct.unpack_from('<I', hdr, 21)[0]
        return {
            'volumes': len(pack.volumes),
            'total_size': pack.total_size,
            'hash_count': hash_count,
            'has_en_db': True,
        }
    except Exception:
        return None
    finally:
        pack.close()
