<p align="center">
  <img src="profile.webp" width="120" height="120" alt="ChaosZero ES Logo">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Version-2.0-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10+-yellow.svg" alt="Python">
  <img src="https://img.shields.io/badge/Platform-Windows-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/UI-tkinter-green.svg" alt="UI">
  <img src="https://img.shields.io/badge/Traducci%C3%B3n-es--MX-red.svg" alt="es-MX">
</p>

<h1 align="center">ChaosZero Nightmare — Parche al Español</h1>

Parche automatico que traduce **ChaosZero Nightmare** al español latinoamericano.

## Preview

> Screenshots<img width="2557" height="1439" alt="image" src="https://github.com/user-attachments/assets/85ab08b4-fd70-4f8e-8634-83cc6853ce70" /><img width="2559" height="1439" alt="image" src="https://github.com/user-attachments/assets/112ff2c6-e9ae-47df-98e5-4b51f4772161" />

---

## Instalacion rapida

### 1. Crea una carpeta para el parche

> **Importante:** El EXE genera archivos auxiliares la primera vez que se ejecuta (cache de traducciones, configuracion, etc.). Ponlo en su propia carpeta para que no ensucie otras carpetas.

```
C:\ChaosZeroES\
├── ChaosZeroES.exe      ← Ejecutable
├── app_config.json      ← (se crea solo) Guarda la ruta del juego
├── translations.tsv     ← (se crea solo) Cache de traducciones
├── glossary.json        ← (se crea solo) Glosario de terminos
└── bin_full_rebuild\    ← (se crea solo) data.pack reconstruidos
```

### 2. Ejecuta el parche

Descarga el parche desde https://github.com/mrsnakke/ChaosZeroES/releases

1. Doble clic en `ChaosZeroES.exe`
2. Selecciona la carpeta del juego: `...\Games\ChaosZeroNightmare`
   - Usa **Buscar auto** para que lo encuentre automaticamente
3. Click en **Parchear**
4. Espera a que termine:
   - Primera vez: ~5-20 min (traduce todo)
   - Siguientes veces: ~30s (solo traduce lo nuevo)
5. Inicia el juego en idioma **INGLES** — el texto aparecera en español

Los archivos originales se guardan como `.bak` por si quieres restaurar.

---

## Despues de un parche del juego

Cuando el juego recibe una actualizacion, el parche se pierde porque descarga los archivos nuevos. Tienes que **re-parchearlo**:

1. Ejecuta `ChaosZeroES.exe`
2. Click en **Parchear** de nuevo
3. Solo traduce los textos nuevos o cambiados, es rapido (~30s)

---

## Revertir

Si quieres volver al estado original del juego, usa el boton **Revertir** — restaura automaticamente los archivos `.bak`.

---

## Tips

- **Carpeta dedicada:** Usa una carpeta solo para ChaosZeroES (ej: `C:\ChaosZeroES`). El exe genera archivos auxiliares y no quieres mezclarlos con otros programas.
- **No muevas el exe despues del primer uso:** Si lo mueves, puede perder la configuracion de la ruta del juego. Si pasa, solo vuelve a seleccionar la carpeta.
- **Backup automatico:** El parche guarda `.bak` de los archivos originales. Si algo sale mal, usa el boton **Revertir** o renombra `.bak` a su nombre original.
- **Re-parchear es rapido:** El exe guarda cache de las traducciones. En parches futuros solo traduce lo nuevo, toma ~30 segundos.
- **Conexion a internet:** Necesaria para traducir.

---

## Solucion de problemas

| Problema | Solucion |
|----------|----------|
| El juego no muestra español | Asegurate de tener el idioma del juego en **INGLES** |
| El exe se cierra solo | Posible error de conexion. Vuelve a ejecutar — retoma desde donde se quedo |
| Quiiero restaurar originales | Usa el boton **Revertir** o busca los archivos `.bak` en la carpeta del juego |
| data.pack no encontrado | Verifica la ruta del juego — usa **Buscar auto** o selecciona manualmente |

---

## Creditos

Basado en [ChaosZero-Toolkit](https://github.com/NineS11942/ChaosZero-Toolkit) de NineS11942.

## Licencia

Este proyecto esta bajo la [MIT License](LICENSE).
