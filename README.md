# 🎧 SpotiBOT Public Service (v1.0)

**SpotiBOT Public** es una solución de arquitectura diseñada para desplegar un **Bot de Telegram como Servicio (SaaS)**. A diferencia de otros scripts personales, este bot está diseñado para atender a múltiples usuarios, generando contenido bajo demanda mediante algoritmos inteligentes y manteniendo la higiene de la cuenta mediante un sistema de auto-limpieza.

![SpotiBOT Architecture](https://raw.githubusercontent.com/glmbxecurity/SpotiBOT_V3/refs/heads/main/images/spotibot4.png)

---

## 🆚 Diferencias Clave: Public Service vs. SpotiBOT V3

Es importante distinguir esta versión de la **V3 (Personal Edition)**:

| Característica | 🤖 SpotiBOT Public (Esta versión) | 🏠 SpotiBOT V3 (Personal) |
| :--- | :--- | :--- |
| **Objetivo** | **Servicio a Usuarios:** Generar sesiones únicas para terceros. | **Gestión Privada:** Mantener y curar tu propia biblioteca. |
| **Playlists** | **Desechables:** Crea listas nuevas con UUID (`SpotiSession [A1B2]`). | **Persistentes:** Actualiza y machaca listas existentes (ej: "Gym 2026"). |
| **Lógica** | **Algorítmica:** Usa pesos (70% Calidad / 30% Azar) para variedad. | **Incremental:** Busca novedades y las añade al final. |
| **Memoria** | **Stateless:** No recuerda qué escuchó el usuario ayer. | **Histórica:** Recuerda canciones para no repetir duplicados. |
| **Mantenimiento** | **Auto-Cleaner:** Borra listas >90 días automáticamente. | **Acumulativo:** Las listas crecen indefinidamente. |

---

## 🚀 Características del Servicio

### 1. Generador de Sesiones (`/create`)
El usuario define el "Mood", la fuente y la duración. El bot genera una playlist única al instante.
* **Algoritmos Ponderados:** No es aleatorio puro. Usamos "Jitter" para variar los resultados sin perder calidad.
* **Anti-Duplicados:** Si el usuario mezcla varias fuentes, filtramos repeticiones.
* **Portadas Dinámicas:** Sube una carátula temática aleatoria de un pool de imágenes.
* **QR Code:** Genera un código QR instantáneo para compartir la sesión.

### 2. Mezclador (`/mix`)
Permite al usuario enviar múltiples enlaces de Spotify. El bot extrae las canciones, las baraja y crea una "Super-Playlist" unificada.

### 3. Radar de Análisis (`/scan`)
Herramienta de análisis de datos. El usuario envía un link y el bot devuelve un informe detallado con:
* **Top Hits:** Las canciones más comerciales.
* **Joyas Ocultas:** Temas de baja popularidad pero alta calidad.
* **Vibe:** Clasificación de la lista (Mainstream vs Underground).

### 4. Salud del Catálogo (`/info`)
Sistema de monitoreo interno que revisa las playlists fuente del archivo `presets.yaml`. Escanea el inicio y el final de las listas para determinar si están **Frescas (🟢)**, **Regulares (🟠)** o **Abandonadas (🔴)**.

---

## 🧠 La "Salsa Secreta": Algoritmos y Criterios

El bot utiliza tres motores de decisión distintos para curar la música:

### ⚡ Modo Max Energy (Gym/Entreno)
* **Objetivo:** Intensidad física.
* **Fórmula:** `Score = (Energía * 0.7) + (Suerte * 0.3)`
* **Lógica:** Prioriza canciones con alto BPM y "ruido". El 30% de factor suerte asegura que dos sesiones de gimnasio nunca tengan el mismo orden, evitando la monotonía.

### 🎉 Modo Party Hype (Fiesta)
* **Objetivo:** Éxitos reconocibles para cantar y bailar.
* **Fórmula:** `Score = ((Popularidad + Danceability) * 0.85) + (Suerte * 0.15)`
* **Lógica:** Es el modo más conservador. Da un peso masivo a la fama y el ritmo. La aleatoriedad es baja (15%) para evitar que suenen canciones desconocidas que "maten" la fiesta.

### 🔭 Modo Discovery (Novedades)
* **Objetivo:** Encontrar música fresca.
* **Filtro Crítico:** **30 Días**.
* **Lógica:** Escanea la fecha `added_at`.
    * **<30 días:** Recibe un **SUPER BOOST (+500 puntos)**. Aparecen matemáticamente al principio.
    * **>30 días:** Se usan solo como relleno si no hay suficientes novedades.

---

## 📂 Estructura del Proyecto

* **`main.py`**: El cerebro. Gestiona la conexión con Telegram, el Rate Limiter (anti-spam) y los menús.
* **`funcion_create.py`**: Contiene la lógica pesada: algoritmos de puntuación, filtrado de audio features y creación de playlists.
* **`funcion_mix.py`**: Lógica de fusión de enlaces externos.
* **`funcion_scan.py`**: Motor de análisis de datos de playlists públicas.
* **`cleaner.py`**: **CRÍTICO.** Script de mantenimiento. Escanea la cuenta, detecta playlists creadas por el bot (`SpotiSession...`) con más de 90 días y 0 seguidores, y las elimina.
* **`comandos_basicos.py`**: Gestión de ayuda y panel de control.
* **`stats.py`**: Base de datos JSON ligera para contar usuarios únicos y listas generadas.
* **`presets.yaml`**: Tu "Base de Datos" de fuentes musicales (Género -> URL).
* **`utils.py`**: Herramientas auxiliares.

---

## ⚙️ Instalación y Despliegue

### 1. Dependencias
Instala las librerías necesarias:
```bash
pip install -r requirements.txt
```
*(Contenido: `python-telegram-bot`, `spotipy`, `qrcode[pil]`, `PyYAML`, `python-dateutil`)*

### 2. Configuración de Spotify
Este bot requiere una App en el Dashboard de Spotify con permisos extendidos (crear playlists, subir imágenes).
1. Crea una app en [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2. Redirect URI: `http://127.0.0.1:8888/callback`
3. **Importante:** Debido a políticas de Spotify, si no tienes "Extended Quota", debes añadir manualmente los emails de los usuarios (o usar una cuenta secundaria para el bot).

### 3. Fichero `config.py`
Crea este archivo en la raíz:
```python
import os

# CREDENCIALES
SPOTIPY_CLIENT_ID = 'TU_ID'
SPOTIPY_CLIENT_SECRET = 'TU_SECRET'
SPOTIPY_REDIRECT_URI = '[http://127.0.0.1:8888/callback](http://127.0.0.1:8888/callback)'
TELEGRAM_TOKEN = 'TU_TOKEN_TELEGRAM'

# RUTAS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(BASE_DIR, '.cache_spotibot')
COOLDOWN_SECONDS = 10 # Anti-spam

# DIRECTORIOS
DIRS = {
    "images": "images/pool",
    "data": "data"
}

# INFO DEV (Para comando /info)
DEV_INFO = {
    "name": "Tu Nombre",
    "github": "[https://github.com/tu-usuario](https://github.com/tu-usuario)",
    "linkedin": "...",
    "email": "..."
}
```

### 4. Gestión de Recursos
* **`presets.yaml`**: Define tus fuentes.
* **`images/pool/`**: Añade aquí las imágenes `.jpg` para las portadas (prefijos obligatorios: `maxenergy_`, `partyhype_`, `discovery_`, `spotimix_`).

### 5. Ejecución
* **Bot:** `python3 main.py`
* **Limpiador (Cron):** `0 4 * * * /usr/bin/python3 /ruta/a/cleaner.py` (Ejecutar cada noche).

---

## ♻️ Ciclo de Vida de las Playlists

Para mantener la cuenta del bot limpia y evitar el límite de 10.000 playlists de Spotify:

1. **Generación:** El bot crea la lista.
2. **Aviso:** Se advierte al usuario que la lista es efímera.
3. **Persistencia de Usuario:** Si al usuario le gusta, debe darle a **"Seguir" (❤️)** en Spotify.
4. **Purga:** El script `cleaner.py` borra cualquier lista vieja que tenga **0 seguidores**. Si el usuario la siguió, se salva.

---

Desarrollado con ❤️ y Python.
