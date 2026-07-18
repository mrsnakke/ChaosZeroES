<p align="center">
  <img src="profile.webp" width="120" height="120" alt="ChaosZero ES Logo">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-1.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10+-yellow.svg" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Windows-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/UI-tkinter-green.svg" alt="UI">
  <img src="https://img.shields.io/badge/Traducci%C3%B3n-es--MX-red.svg" alt="es-MX">
</p>

<h1 align="center">ChaosZero Nightmare — Parche al Espanol</h1>

Parche automatico que traduce **ChaosZero Nightmare** al espanol latinoamericano.
## Preview
> Screenshots<img width="2559" height="1439" alt="image" src="https://github.com/user-attachments/assets/fc5a1dd5-a4ab-4df2-b5be-ab0ee6657b53" /><img width="2559" height="1439" alt="image" src="https://github.com/user-attachments/assets/112ff2c6-e9ae-47df-98e5-4b51f4772161" />

---

## Instalacion rapida

### 1. Crea una carpeta para el parche

> **Importante:** El EXE genera archivos auxiliares la primera vez que se ejecuta (cache de traducciones, configuracion, etc.). Ponlo en su propia carpeta para que no ensucie otras carpetas.

```
C:\ChaosZeroES\
├── ChaosZeroES.exe      ← Ejecutable
├── app_config.json      ← (se crea solo) Guarda la ruta del juego
├── text_en_extracted.tsv← (se crea solo) Cache de textos EN
├── text_ko_text.tsv     ← (se crea solo) Traducciones ES
└── bin_full_rebuild\    ← (se crea solo) data.pack reconstruidos
```

### 2. Ejecuta el parche

1. Doble clic en `ChaosZeroES.exe`
2. Selecciona la carpeta del juego: `...\Games\ChaosZeroNightmare`
3. Click en **Parchear**
4. Espera a que termine:
   - Primera vez: ~5-20 min (descarga y traduce todo)
   - Siguientes veces: ~30s (solo traduce lo nuevo)
5. Inicia el juego en idioma **COREANO** — el texto aparecera en espanol

Los archivos originales se guardan como `.bak` por si quieres restaurar.

---

## Despues de un parche del juego

Cuando el juego recibe una actualizacion, el parche se pierde porque descarga los archivos nuevos. Tienes que **re-parchearlo**:

1. Ejecuta `ChaosZeroES.exe`
2. Click en **Parchear** de nuevo
3. Solo traduce los textos nuevos o cambiados, es rapido (~30s)

---

## Tips

- **Carpeta dedicada:** Usa una carpeta solo para ChaosZeroES (ej: `C:\ChaosZeroES`). El exe genera archivos auxiliares y no quieres mezclarlos con otros programas.
- **No muevas el exe despues del primer uso:** Si lo mueves, puede perder la configuracion de la ruta del juego. Si pasa, solo vuelve a seleccionar la carpeta.
- **Backup automatico:** El parche guarda `.bak` de los archivos originales. Si algo sale mal, renombra `.bak` a su nombre original.
- **Re-parchear es rapido:** El exe guarda cache de las traducciones. En parches futuros solo traduce lo nuevo, toma ~30 segundos.
- **Conexion a internet:** Necesaria para traducir.

---

## Solucion de problemas

| Problema | Solucion |
|----------|----------|
| El juego no muestra espanol | Asegurate de tener el idioma del juego en **COREANO** |
| El exe se cierra solo | Posible error de conexion. Vuelve a ejecutar — retoma desde donde se quedo |
| Quiiero restaurar originales | Busca los archivos `.bak` en la carpeta del juego y renombralos quitando `.bak` |

---

## Creditos

Basado en [ChaosZero-Toolkit](https://github.com/NineS11942/ChaosZero-Toolkit) de NineS11942.

## Licencia

Este proyecto esta bajo la [MIT License](LICENSE).
