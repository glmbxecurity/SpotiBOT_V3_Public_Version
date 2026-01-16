# 🎧 SpotiBOT Public Service (v1.0)  
[![Telegram](https://img.shields.io/badge/Telegram-Iniciar_Bot-blue?style=for-the-badge&logo=telegram)](https://t.me/official_spotibot)  
**SpotiBOT Public** es una solución de arquitectura diseñada para desplegar un **Bot de Telegram como Servicio (SaaS)**. Diseñado para atender a múltiples usuarios, generando sesiones musicales bajo demanda mediante algoritmos inteligentes y mantenimiento automático.

![SpotiBOT Architecture](https://raw.githubusercontent.com/glmbxecurity/SpotiBOT_V3/refs/heads/main/images/spotibot4.png)

---

## 🚀 Características del Servicio

### 1. Generador de Sesiones (`/create`)
El núcleo del bot. Permite crear playlists únicas de 4 formas distintas:

*   **🔗 Pega tus propias playlist**: ¿Tienes tus links? Pégalos. **Soporta TODO**: Listas personales, álbumes, y **Listas del Sistema** (Radar de Novedades, Daily Mix, On Repeat...).
*   **💿 Estilos del Bot**: Elige entre nuestro catálogo curado (`presets.yaml`).
*   **🧬 Mezcla de Estilos**: Fusiona múltiples géneros.
    *   *Balanceo Inteligente*: Si mezclas Rock con Jazz, el bot asegura un reparto **50/50** (u equitativo), independientemente de cuántas listas tenga cada género.
*   **🎲 Random Mix**: El bot elige **3 estilos al azar** del catálogo y crea un mashup sorprendente y equilibrado.

**Extras:**
*   **Anti-Duplicados**: Filtramos repeticiones automáticamente.
*   **Portadas Dinámicas**: Genera carátulas temáticas para cada sesión.
*   **QR Code**: Código instantáneo para compartir en pantallas/fiestas.

### 2. Panel de Administración (`/admin`)
Herramienta exclusiva para el dueño del bot (`ADMIN_ID` en config):
*   **🧹 Limpieza Forzada**: Borra todas las sesiones generadas al instante (ignora la caducidad de 90 días).
*   **🕵️ Diagnóstico**: Revisa la salud del catálogo (fechas de actualización).
*   **📝 Editor YAML**: Edita `presets.yaml` en caliente sin reiniciar.
*   **🔄 Reinicio**: Reinicia el servicio `systemd` desde Telegram.

---

## 🧠 Algoritmos de Selección ("La Salsa Secreta")

El bot no elige canciones al azar. Usa algoritmos ponderados ajustables:

### ⚡ Max Energy (Gym/Entreno)
*   **Objetivo:** Intensidad física pura.
*   **Fórmula:** **90% Energía** / 10% Suerte.
*   **Lógica:** Extremadamente estricto. Busca los temas con mayor BPM y potencia. El pequeño factor suerte evita que la sesión sea idéntica cada día.

### 🔥 Temas Populares (Fiesta)
*   **Objetivo:** Éxitos garantizados (Crowd Pleasers).
*   **Fórmula:** **100% Popularidad**.
*   **Lógica:** Determinista. Selecciona las canciones con mayor índice de popularidad global en Spotify. Cero riesgos, solo hits.

### 🔭 Discovery (Novedades)
*   **Objetivo:** Encontrar música fresca.
*   **Filtro:** **Estricto 30 Días**.
*   **Lógica:** Escanea la fecha `added_at`.
    *   Si la canción se añadió hace **menos de 30 días**, entra.
    *   Si es más vieja, **se descarta automáticamente**.
    *   *Nota: Si una playlist no tiene novedades, este modo no devolverá nada.*

### 🎲 Random (Sorpréndeme)
*   **Objetivo:** Caos controlado.
*   **Fórmula:** 100% Azar.
*   **Lógica:** Cualquier canción es válida. Ideal para explorar "Caras B" y joyas ocultas de tus listas.

---

## 📂 Estructura del Proyecto

*   **`main.py`**: Cerebro principal. Gestiona Telegram y Menús.
*   **`funcion_create.py`**: Lógica pesada. Algoritmos de puntuación, filtrado y creación.
*   **`admin_panel.py`**: Gestión de administración y herramientas de mantenimiento.
*   **`cleaner.py`**: **CRÍTICO.** Script de auto-limpieza. Elimina `SpotiSession` antiguas (>90 días) sin seguidores.
*   **`utils.py`**: Herramientas Regex y auxiliares.
*   **`presets.yaml`**: "Base de Datos" de géneros y links.

---

## ⚙️ Instalación y Despliegue

### 1. Dependencias
```bash
pip install -r requirements.txt
```

### 2. Configuración (`config.py`)
Crea este archivo en la raíz con tus credenciales:
```python
SPOTIPY_CLIENT_ID = 'TU_ID'
SPOTIPY_CLIENT_SECRET = 'TU_SECRET'
SPOTIPY_REDIRECT_URI = 'http://127.0.0.1:8888/callback'
TELEGRAM_TOKEN = 'TU_TOKEN'
ADMIN_ID = 123456789 # Tu ID de Telegram (Obtenlo con /info o bots como @userinfobot)
```

### 3. Ejecución
*   **Manual**: `python3 main.py`
*   **Servicio**: Se recomienda usar `systemd` para ejecución continua.

---

## ♻️ Ciclo de Vida de las Playlists

1.  **Generación**: Se crea una lista efímera.
2.  **Uso**: El usuario la escucha.
3.  **Persistencia**: Si le gusta, debe darle a **"Seguir" (❤️)**.
4.  **Auto-Limpieza**: Si pasados 90 días tiene **0 seguidores**, `cleaner.py` la destruye para ahorrar espacio.

---

Desarrollado para la comunidad.
