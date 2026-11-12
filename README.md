# 🎬 Renombrador Multimedia (Series y Películas con TVmaze API)

Una aplicación de escritorio en **Python** con interfaz gráfica **Qt (PySide6 / PyQt6)** diseñada para analizar y renombrar archivos multimedia de series y películas de forma limpia, organizada.

---

## 🌟 Características Principales

1. **Escaneo inteligente de carpetas**:
   - Selección mediante diálogo o arrastrar y soltar (*drag & drop*) de directorios.
   - Opción para escanear subdirectorios o únicamente la carpeta seleccionada.
   - Detección de formatos de video habituales (`.mkv`, `.mp4`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, etc.).

2. **Integración con la API de TVmaze**:
   - Conexión a la API pública y gratuita de [TVmaze](https://www.tvmaze.com/api) (sin necesidad de API keys).
   - Identificación del nombre canónico de la serie y el título exacto del capítulo para la temporada y episodio detectados.
   - Para películas, limpia etiquetas de escena (`1080p`, `BluRay`, `x264`, `HDR`, etc.) y genera un nombre limpio con el año y el idioma detectado: `Título (Año).ext` o `Título (Año) [Latino].ext`.

3. **Caché en memoria de alto rendimiento**:
   - Para carpetas con múltiples capítulos de una misma serie, TVmaze se consulta solo una vez para indexar toda la serie, resolviendo los siguientes episodios al instante (0 ms) sin sobrecargar la red ni sobrepasar límites de tasa.

4. **Lista interactiva de nombres actuales vs propuestos**:
   - Visualización tabular con estado visual (*Pendiente*, *Listo*, *Renombrado*, *Error*).
   - **Edición en línea**: Haz doble clic sobre cualquier nombre sugerido para retocarlo manualmente antes de aceptar.
   - Búsqueda manual en TVmaze con clic derecho si deseas asociar otra serie diferente.

5. **Seguridad Total ("No cambiar sin preguntar")**:
   - Cada fila cuenta con su propio botón **✓ Renombrar**.
   - Al pulsar dicho botón, se abre una ventana modal de confirmación mostrando el cambio exacto a realizar.
   - Protección contra colisiones: Si ya existe un archivo con el nombre de destino, se advierte de forma visible y se previene la sobreescritura accidental. Solo se sobrescribe si el usuario lo confirma expresamente.
   - Renombrado transaccional: el video y sus subtítulos se renombran juntos; si algo falla, se restaura el estado anterior para no dejar nombres incoherentes.
   - Opción de renombrado múltiple (*Renombrar Seleccionados*) con diálogo de confirmación que resume todos los archivos antes de tocar el disco. También funciona al intercambiar nombres entre archivos.

---

## 📋 Requisitos e Instalación

### Requisitos:
- **Python 3.8 o superior** (probado con Python 3.10, 3.11, 3.12 y 3.13).
- Conexión a internet (para consultar la API de TVmaze).

### Instalación de dependencias:
La aplicación utiliza la biblioteca oficial de Qt para Python (`PySide6`) o `PyQt6`:

```bash
pip install -r requirements.txt
```

*(O de forma individual: `pip install PySide6`)*

---

## 🚀 Uso de la Aplicación

### Iniciar la aplicación:

```bash
python main.py
```

Opcionalmente, puedes pasarle la ruta de una carpeta directamente por consola:

```bash
python main.py "D:\Descargas\Series"
```

### Pasos de uso:
1. **Seleccionar Carpeta**: Pulsa en `📁 Examinar...` o arrastra una carpeta directamente sobre la ventana.
2. **Configurar**: Marca si deseas escanear subcarpetas y elige el formato de renombrado deseado (ej. `{show} - S{season:02d}E{episode:02d} - {title}{ext}`).
3. **Analizar**: Pulsa `🔍 Analizar y Buscar en TVmaze`. El programa analizará los nombres y consultará TVmaze en segundo plano sin congelar la interfaz.
4. **Revisar**: Comprueba la lista de nombres sugeridos. Puedes editarlos directamente si quieres cambiar algún detalle.
5. **Aceptar y Renombrar**: Pulsa el botón `✓ Renombrar` del archivo que desees modificar (te pedirá confirmación previa antes de efectuar cualquier cambio).

---

## 📂 Estructura del Proyecto

```text
Remombrador multimedia/
├── app/
│   ├── __init__.py           # Inicializador de paquete
│   ├── qt_compat.py          # Capa de compatibilidad PyQt6 / PySide6
│   ├── media_parser.py       # Extracción de títulos, temporadas, episodios y limpieza
│   ├── file_ops.py           # Renombrado transaccional (video + subtítulos, colisiones)
│   ├── tvmaze_client.py      # Cliente HTTP para TVmaze con caché en memoria
│   ├── renamer_worker.py     # QThread para procesar en segundo plano
│   ├── main_window.py        # Ventana principal de la interfaz gráfica
│   ├── dialogs.py            # Diálogos de confirmación y búsqueda manual
│   └── styles.py             # Hoja de estilos moderna y limpia (QSS)
├── tests/
│   ├── test_parser.py        # Pruebas unitarias del parser y sanitizador
│   ├── test_file_ops.py      # Pruebas del renombrado transaccional y rollback
│   ├── test_api.py           # Pruebas del cliente TVmaze
│   ├── test_full_workflow.py # Pruebas del flujo completo y operaciones de archivo
│   └── test_ui.py            # Pruebas de inicialización de la interfaz
├── main.py                   # Script ejecutable principal
├── requirements.txt          # Dependencias
└── README.md                 # Documentación
```

---

## 🧪 Ejecución de Pruebas Unitarias

Para verificar que todos los componentes funcionan correctamente:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

