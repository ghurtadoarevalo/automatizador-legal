# Automatizador Legal - Programación de Sala (PJUD Chile)

Este proyecto automatiza la consulta de la **Programación de Sala** en la Oficina Judicial Virtual del Poder Judicial de Chile (PJUD). Permite obtener de forma masiva los horarios y fechas de audiencias para múltiples causas judiciales.

## 🚀 Funcionalidades Principales

- **Consulta Masiva**: Procesa múltiples causas de una sola vez (Corte Suprema, Apelaciones, Civil, Laboral, etc.).
- **Detección de Fechas**: Identifica y resalta automáticamente fechas de audiencias futuras.
- **Reportes Visuales**: Genera un reporte HTML estilizado (compatible con emails) con los resultados.
- **Modo Híbrido (Host-Docker)**: Ejecuta Playwright dentro de Docker pero controla el Chrome de tu Mac para evitar bloqueos y ver el proceso en tiempo real.
- **Depuración**: Captura pantallazos y logs HTML automáticamente en caso de error.

## 🛠️ Arquitectura de Conexión (CDP)

Este proyecto utiliza una configuración especial para correr Playwright **dentro del contenedor**, pero controlando un **Chrome visible en tu Mac**. Esto es fundamental para:
1.  **Evitar bloqueos**: Los portales judiciales suelen tener medidas anti-bot estrictas.
2.  **Interactividad**: Puedes intervenir manualmente si aparece un captcha.
3.  **Visibilidad**: Ves exactamente lo que el robot está haciendo.

---

## ⚙️ Configuración e Inicio Rápido

### 1) Configura `HOST_IP`

Playwright necesita la IP de tu Mac para conectarse desde el contenedor. Obtén tu IP local (ej: `ipconfig getifaddr en0`) y crea/ajusta un archivo `.env` en la raíz del proyecto:

```bash
HOST_IP=192.168.1.XXX
```

### 2) Ejecución (Recomendado)

Utiliza el script automatizado para levantar todo el entorno de forma robusta:

```bash
# Permisos de ejecución la primera vez
chmod +x start.sh

# Inicia Chrome, el forwarder y los contenedores
./start.sh
```

El script se encarga de:
1.  **Limpiar procesos previos**: Libera los puertos `9222` y `9223` automáticamente antes de empezar para evitar errores de "Address already in use".
2.  **Gestionar el ciclo de vida**: Abre Chrome y el forwarder, espera a que estén listos, y levanta Docker Compose.
3.  **Cierre Seguro**: Al presionar `Ctrl+C`, se asegura de matar los procesos del host y liberar los puertos correctamente.

## 🤖 Ecosistema de Automatización

El proyecto está diseñado para funcionar como una pieza central en flujos de trabajo de n8n:

1.  **n8n**: Incluido en el `docker-compose.yml`, gestiona el flujo de principio a fin.
2.  **Google Drive**: Se descarga un archivo Excel (XLSX) que contiene la lista de causas a consultar.
3.  **Extracción**: n8n procesa el Excel y extrae las filas con la información de los casos.
4.  **FastAPI (HTTP Request)**: Se envían los casos mediante un POST al contenedor `fastapi_app`. Este ejecuta Playwright (vía CDP hacia tu Mac) y devuelve el reporte HTML.
5.  **Gmail/Notificaciones**: El HTML resultante se envía por correo electrónico como un reporte consolidado.

- **Reportes Email-Ready**: El HTML generado utiliza estilos inline y tablas, asegurando que se vea correctamente en Gmail, Outlook y otros clientes de correo.

---

## 📖 Uso de la API

Una vez levantado, el servicio estará disponible en `http://localhost:8000`.

### Ejemplo de Consulta (POST)

Puedes enviar una lista de causas al endpoint raíz `/`:

```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "cases": [
      {
        "competency": "Civil",
        "rol": "C-1234",
        "year": "2023"
      },
      {
        "competency": "Corte Apelaciones",
        "court": "C.A. de Santiago",
        "book": "Civil",
        "rol": "1500",
        "year": "2023"
      }
    ]
  }'
```

El sistema devolverá un **HTMLResponse** con el reporte visual de las tablas de programación encontradas.

---

### ¿Cómo funciona por detrás? (Manual)

Si prefieres no usar el script `start.sh`:

1.  **Iniciar Chrome en macOS:**
    ```bash
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222 --user-data-dir="$HOME/chrome-pw-profile"
    ```
2.  **Iniciar el Forwarder:**
    ```bash
    python complements/run_browser.py
    ```
3.  **Docker Compose:**
    ```bash
    docker compose up --build
    ```

