# ChaosZeroES — Documentacion Tecnica

Traduccion automatica al espanol de ChaosZero Nightmare (Yuna/Cocos2d-x engine).

---

## Arquitectura

```
ChaosZeroES/
├── app.py                      # GUI principal (tkinter, un click para todo)
├── lanzar.bat                  # Lanzador (abre la GUI)
├── instalar.bat                # Instalador de dependencias (numpy)
├── extract_and_translate.py    # Extrae + traduce (incremental, paralelo)
├── rebuild_ko_to_es.py         # Reconstruye data.pack con traducciones
├── extract_text.py             # Extrae texto EN/KO a TSV (CLI standalone)
├── translate_incremental.py    # Traduce EN->ES (CLI standalone, incremental)
├── text_en_extracted.tsv       # [generado] Cache de source texts EN
├── text_ko_text.tsv            # [generado] Traducciones ES (text_id, en, spanish)
└── bin_full_rebuild/           # [generado] data.pack* reconstruidos
    ├── data.pack               # ~1 GB
    ├── data.pack~1             # ~1 GB
    └── ...                     # ~5 volumes totales
```

---

## Flujo de datos

```
                    ┌─────────────────────┐
                    │   data.pack (5 GB)   │
                    │  6 volumes, PLPcK    │
                    └─────────┬───────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
        ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
        │text/ko/    │  │text/en/   │  │  otros    │
        │text.db     │  │text.db    │  │  archivos │
        │(21.5 MB)   │  │(21.1 MB)  │  │  (5 GB)   │
        └─────┬──────┘  └─────┬─────┘  └─────┬─────┘
              │               │               │
    decrypt inner      decrypt inner     sin cambios
              │               │
              ▼               ▼
    ┌──────────────┐  ┌──────────────┐
    │ 205k textos  │  │ 102k textos  │
    │   coreanos   │  │  ingleses    │
    └──────┬───────┘  └──────┬───────┘
           │                 │
           │        translate_incremental.py
           │        (Google Translate EN->ES)
           │                 │
           │                 ▼
           │        ┌──────────────┐
           │        │ text_ko_text │
           │        │    .tsv      │
           │        │ (102k ES)    │
           │        └──────┬───────┘
           │               │
           └───────┬───────┘
                   │
          rebuild_ko_to_es.py
                   │
                   ▼
          ┌────────────────┐
          │  data.pack*    │
          │  (5 GB, KO     │
          │   reemplazado  │
          │   con ES)      │
          └────────────────┘
```

---

## Formato del archivo data.pack

### PLPcK (formato de archivo del motor Yuna)

```
┌─────────────────────────────────────────┐  offset 0
│  Header PLPcK (38 bytes)                │
│  [0:5]   magic "PLPcK"                  │
│  [21:25] hash_count (uint32 LE)         │  ← 65,535 buckets
│  [25:29] file_size (uint32 LE)          │
├─────────────────────────────────────────┤  offset 38
│  Version record (5 bytes)               │
├─────────────────────────────────────────┤  offset 43
│  Hash table                             │  ← hash_count * 5 bytes
│  Cada bucket: 1 byte high + 4 bytes low │    = puntero al primer chunk
│  (5 bytes por bucket)                   │
├─────────────────────────────────────────┤  offset 43 + hash_count*5
│  Chunks (cadenas enlazadas)             │
│  ┌──────────────────────────────┐       │
│  │ Chunk header (15 bytes)      │       │
│  │ [0:4]   data_size (uint32)   │       │  ← key_len + value_len + 15
│  │ [4]     flags                │       │
│  │ [5]     key_length (uint8)   │       │
│  │ [6:10]  value_size (uint32)  │       │
│  │ [10:15] next_ptr (5 bytes)   │       │  ← siguiente en la cadena
│  ├──────────────────────────────┤       │
│  │ Key data (key_length bytes)  │       │  ← nombre del archivo
│  │ Value data (value_size bytes)│       │  ← contenido del archivo
│  └──────────────────────────────┘       │
└─────────────────────────────────────────┘
```

### Cifrado XOR de doble capa

```
Capa externa (Pack XOR):
  - Clave: 129 bytes, generada por LCG (seed=150812)
  - Se aplica a TODO el archivo data.pack
  - Posicion: offset global en el archivo
  - Funcion: pack_xor_crypt(data, file_offset)

Capa interna (Inner XOR):
  - Clave: 256 bytes hardcodeada
  - Se aplica solo a archivos .db dentro del pack
  - Posicion: offset detectado brute-forceando magic "PLPcK"
  - Funcion: inner_xor_crypt(data, base_offset)
```

### Como se encuentra el offset interno

```python
# Prueba offsets 0-255 hasta que los primeros 5 bytes descifrados == b'PLPcK'
for boff in range(256):
    decrypted_head = [data[i] ^ INNER_XOR_KEY[(i + boff) % 256] for i in range(5)]
    if bytes(decrypted_head) == b'PLPcK':
        return boff  # este es el base_offset correcto
```

### Multi-volume

```
data.pack      → offset global 0 a 1,073,741,823       (1 GB)
data.pack~1    → offset global 1,073,741,824 a 2,147,483,647
data.pack~2    → offset global 2,147,483,648 a 3,221,225,471
data.pack~3    → offset global 3,221,225,472 a 4,294,967,295
data.pack~4    → offset global 4,294,967,296 a 5,368,709,119
data.pack~5    → offset global 5,368,709,120 a 5,394,860,415  (~24 MB)
```

---

## Archivos internos relevantes

| Key en el pack | Tamano | Descripcion |
|----------------|--------|-------------|
| `text/ko/text.db` | 21.5 MB | Base de datos de texto coreano (original) |
| `text/en/text.db` | 21.1 MB | Base de datos de texto ingles (traduccion oficial) |
| `text/ja/text.db` | — | No existe en esta version |
| `text/zht/text.db` | — | No existe en esta version |
| `javascript/init.js` | ~30 KB | Script principal del juego (Cocos2d-x) |
| `sound/*.bank` | ~947 archivos | Bancos de audio FMOD |
| `video/**/*.mp4` | ~varios | Cutscenes y eventos |

---

## Formato de la base de datos de texto (.db interna)

Cada .db es un PLPcK anidado (una segunda capa del mismo formato):

```
text.db (ya descifrado con inner XOR)
┌──────────────────────────────────────┐
│  Header PLPcK (38 bytes)             │
│  Version record (5 bytes)            │
│  Hash table (inner_hash_count * 5)   │
│  Chunks...                           │
└──────────────────────────────────────┘
```

### Formato de cada entrada de texto

```
Value bytes de cada chunk:
┌─────────────────────────────────────────┐
│ text_id (UTF-8)          │ \x00         │
│ texto traducible (UTF-8) │ \x00         │
│ datos trailing (opcionales)             │
└─────────────────────────────────────────┘

Ejemplo:
  "chapter_01_title\x00Capitulo 1: El Despertar\x00"
   ──── text_id ────     ────── texto visible ──────
```

Las entradas metadata empiezan con `\t` (tab) en el key y se ignoran para traduccion.

---

## Flujo detallado del rebuild (rebuild_ko_to_es.py)

### Paso 1: Extraer todos los archivos

```
1. Leer header PLPcK → obtener hash_count
2. Para cada bucket (0 a hash_count-1):
   a. Leer puntero (5 bytes) del hash table
   b. Si puntero == 0, skip
   c. Recorrer cadena de chunks:
      - Leer chunk header (15 bytes)
      - Leer key + value
      - Seguir next_ptr hasta 0
3. Guardar como lista de PackEntry(key, value, flags)
```

**Tiempo real**: ~10s para 79,286 entries

### Paso 2: Procesar KO text.db

```
1. Buscar entry con key == b"text/ko/text.db"
2. Descifrar inner XOR (brute-force offset 0-255)
3. Parsear PLPcK interno → 205,308 text entries
4. Cargar TSV (text_id → traduccion ES)
5. Para cada entry:
   a. Parsear: text_id + \x00 + texto + \x00 + trailing
   b. Si text_id existe en TSV → reemplazar texto
   c. Si no existe → mantener original
6. Reconstruir PLPcK interno con textos modificados
7. Cifrar con inner XOR (nuevo offset = len % 256)
8. Reemplazar value del entry KO en la lista
```

**Tiempo real**: ~1s

### Paso 3: Reescribir data.pack

```
1. Calcular nueva tabla hash (re-hash de todas las entries)
2. Calcular offsets de cada chunk
3. StreamingPackWriter:
   a. Escribir header + version + hash table (cifrados con pack XOR)
   b. Para cada chunk:
      - Calcular header (15 bytes)
      - Escribir header + key + value + meta (cifrados)
   c. Auto-split en volumes de 1 GB
4. Cada byte se cifra con: pack_xor_crypt(chunk, global_offset)
```

**Tiempo real**: ~19s para 5.02 GB

### Paso 4: Verificar

```
1. Re-leer el data.pack generado
2. Verificar header PLPcK
3. Contar todos los entries en la hash table
4. Comparar con el numero original de entries
5. Verificar que text/zht/text.db (o text/ko/text.db) tiene inner PLPcK valido
```

---

## Formato del TSV de traduccion

```
text_id\tspanish
chapter_01_title\tCapitulo 1: El Despertar
ui_button_ok\tAceptar
ui_button_cancel\tCancelar
...
```

- Separador: tabulador (`\t`)
- Encoding: UTF-8
- Primera linea: header
- Orden: importa solo text_id (se busca por hash)
- Un text_id puede tener multiples entradas (el rebuild usa la ultima)

---

## Traduccion (extract_and_translate.py)

### API utilizada

Google Translate no oficial (`translate.googleapis.com/translate_a/single`):

```
GET https://translate.googleapis.com/translate_a/single
    ?client=gtx
    &sl=en          # idioma origen
    &tl=es          # idioma destino
    &dt=t
    &q=texto        # max 5000 chars
```

### Estrategia paralela + incremental

```
1. Unir 20 textos con separador " ||| "
2. Enviar como un solo request
3. Separar la respuesta por " ||| "
4. Si falla -> traducir 1 por 1 (fallback)
5. 6 workers en paralelo via ThreadPoolExecutor
6. Auto-save cada ~1000 traducciones
```

### Deteccion de cambios (incremental)

```
1. Cargar cache: text_en_extracted.tsv (source texts anteriores)
2. Cargar traducciones: text_ko_text.tsv
3. Comparar: text_id nuevo O source text cambiado
4. Solo traducir el diff
5. Reutilizar traducciones para textos sin cambios
6. Guardar ambos TSVs actualizados
```

### Limitaciones

- Google puede bloquear despues de ~1000 requests
- Ctrl+C guarda progreso automaticamente
- Re-ejecutar retoma desde donde se quedo
- Parches pequenos: ~segundos. Primera vez: ~15-30 min

---

## Diccionario offline

`extract_text.py` incluye ~642 terminos comunes de juegos EN->ES:
- Botones: Aceptar, Cancelar, Confirmar, Volver...
- UI: Inventario, Tienda, Correo, Menu...
- RPG: Ataque, Defensa, Habilidad, Mision...
- Sistema: Nivel, Rango, Temporada, Servidor...

Se pueden agregar terminos editando el dict `DICT` en `extract_text.py:143`

---

## Como escalar o mejorar

### Agregar mas traducciones manuales

1. Editar `text_ko_text.tsv` con cualquier editor (VS Code, Notepad++)
2. Formato: `text_id\ttraduccion` (una linea por entrada)
3. Ejecutar rebuild (paso 3)
4. Los text_ids se encuentran en `text_en_extracted.tsv`

### Cambiar idioma destino

En `rebuild_ko_to_es.py`, cambiar la variable `TSV_PATH` para apuntar a otro TSV.
El mismo pipeline funciona para cualquier idioma.

### Usar otro servicio de traduccion

En `translate_incremental.py`, reemplazar `google_translate_batch()` con:
- DeepL API (requiere API key, mejor calidad)
- OpenAI/ChatGPT API (requiere API key, mejor contexto)
- LibreTranslate (self-hosted, sin rate limit)
- Sugoi Translator (offline, sin internet)

### Traducir otros archivos ademas de texto

El engine tambien tiene:
- `javascript/*.js` — scripts del juego (se pueden modificar)
- `sound/*.bank` — audio (se puede reemplazar)
- `video/**/*.mp4` — cutscenes (se pueden subtitular)

Para modificar JS, ver el `init.js` del ChaosZero-Toolkit que tiene
ejemplos de inyeccion de velocidad y skip de animaciones.

### Actualizar despues de un parche del juego

El juego tiene hot-update que re descarga text.db periodicamente.
Cuando sale un parche:
1. Ejecutar `lanzar.bat` (abre la GUI)
2. Seleccionar carpeta del juego
3. Click en "Parchear"
4. La app detecta automaticamente textos nuevos/cambiados
5. Solo traduce lo necesario (incremental)
6. Reconstruye y aplica al juego

### Agregar interfaz grafica (GUI)

Ya incluida en `app.py` (tkinter, sin dependencias extra).
Para compartir: el amigo solo necesita Python + numpy.
Ejecutar `lanzar.bat` o `python app.py`.

---

## Dependencias

| Paquete | Version | Uso |
|---------|---------|-----|
| Python | 3.10+ | Runtime |
| numpy | 2.4+ | XOR acelerado con vectorizacion |
| tkinter | built-in | GUI (incluido con Python) |

---

## Rendimiento medido

| Operacion | Tiempo | Datos |
|-----------|--------|-------|
| Extraer EN text.db | 0.3s | 102,615 textos |
| Extraer KO text.db | 0.3s | 102,651 textos |
| Parsear data.pack completo | ~10s | 79,286 entries, 65,535 buckets |
| Traducir (primera vez) | ~15-30min | 102k textos, 6 workers paralelos |
| Traducir (parche ~50 cambios) | ~5-10s | Solo textos nuevos/cambiados |
| Aplicar traducciones | <0.1s | Diccionario offline |
| Reconstruir data.pack | ~19s | 5.02 GB, 79,286 chunks |
| Verificar data.pack | ~10s | Re-lectura completa |
| **Total pipeline (parche)** | **~30s** | Incremental |
| **Total pipeline (primera vez)** | **~15-30min** | Con traduccion completa |

---

## Creditos

Basado en el trabajo de:
- [ChaosZero-Toolkit](https://github.com/NineS11942/ChaosZero-Toolkit) by NineS11942
  - Analisis del formato PLPcK via IDA Pro
  - Claves de cifrado XOR (pack + inner)
  - Funcion de hash CDBM
- Motor del juego: Yuna (basado en Cocos2d-x)
- Plataforma: STOVE (GameOn/Smilegate)
