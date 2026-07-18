#!/usr/bin/env python3
"""
Translate extracted English text to Spanish using Google Translate.
Works incrementally - reads existing TSV, translates untranslated entries.
Uses batched requests for speed.
"""
import csv, os, sys, time, json, urllib.request, urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
EN_TSV = os.path.join(SCRIPT_DIR, "text_en_extracted.tsv")
ES_TSV = os.path.join(SCRIPT_DIR, "text_ko_text.tsv")

def google_translate_batch(texts, src='en', dest='es-MX'):
    """Translate a batch of texts using Google Translate."""
    # Join with unique separator to preserve individual texts
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
    except Exception as e:
        return None
    return None

def load_tsv(path):
    data = {}
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter='\t')
            next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 2:
                    data[row[0]] = row[1]
    return data

def save_tsv(data, path):
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(['text_id', 'spanish'])
        for tid, es in sorted(data.items()):
            writer.writerow([tid, es])

def main():
    if not os.path.exists(EN_TSV):
        print(f"ERROR: {EN_TSV} not found!")
        print("Run extract_text.py first.")
        sys.exit(1)

    en_data = load_tsv(EN_TSV)
    print(f"EN texts loaded: {len(en_data):,}")

    es_data = load_tsv(ES_TSV)
    print(f"Existing ES translations: {len(es_data):,}")

    untranslated = {tid: en for tid, en in en_data.items() if tid not in es_data}
    print(f"Untranslated: {len(untranslated):,}")

    if not untranslated:
        print("All texts already translated!")
        return

    BATCH_SIZE = 20
    WORKERS = 6
    items = list(untranslated.items())
    total = len(items)
    print(f"\nTranslating in parallel batches ({WORKERS} workers, batch {BATCH_SIZE})...")
    print(f"Press Ctrl+C to stop and save progress\n")

    translated = 0
    errors = 0

    def translate_batch(batch):
        tids, texts = zip(*batch)
        result = google_translate_batch(list(texts))
        if result and len(result) == len(batch):
            return list(zip(tids, result)), 0, len(batch)
        out = []
        errs = 0
        for tid, text in zip(tids, texts):
            single = google_translate_batch([text])
            if single and len(single) == 1:
                out.append((tid, single[0]))
            else:
                out.append((tid, text))
                errs += 1
            time.sleep(0.05)
        return out, errs, len(out) - errs

    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as pool:
            futures = {}
            for i in range(0, total, BATCH_SIZE):
                batch = items[i:i+BATCH_SIZE]
                f = pool.submit(translate_batch, batch)
                futures[f] = i

            done_count = 0
            for f in as_completed(futures):
                batch_results, batch_errors, batch_ok = f.result()
                for tid, tr in batch_results:
                    es_data[tid] = tr
                translated += batch_ok
                errors += batch_errors
                done_count += len(batch_results)

                if done_count % 150 < BATCH_SIZE * WORKERS:
                    pct = done_count * 100 // total
                    print(f"  {done_count:,}/{total:,} ({pct}%) translated={translated} errors={errors}")
                    save_tsv(es_data, ES_TSV)

    except KeyboardInterrupt:
        print(f"\n\nInterrupted! Saving progress...")

    save_tsv(es_data, ES_TSV)
    print(f"\nFinal: {len(es_data):,} translations saved to {ES_TSV}")
    print(f"This session: +{translated} translated, {errors} errors")

if __name__ == '__main__':
    main()
