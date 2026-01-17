# Automatizador Legal - Programación de Sala (PJUD Chile)

Este proyecto automatiza la consulta de la **Programación de Sala** en la Oficina Judicial Virtual del Poder Judicial de Chile (PJUD). Permite obtener de forma masiva los horarios y fechas de audiencias para múltiples causas judiciales.

## 🚀 Funcionalidades Principales

- **Consulta Masiva**: Procesa múltiples causas de una sola vez (Corte Suprema, Apelaciones, Civil, Laboral, etc.).
- **Detección de Fechas**: Identifica y resalta automáticamente fechas de audiencias futuras.
- **Reportes Visuales**: Genera un reporte HTML estilizado (compatible con emails) con los resultados.
- **Modo Híbrido (Host-Docker)**: Ejecuta Playwright dentro de Docker pero controla el **Brave de tu Mac** para evitar bloqueos y ver el proceso en tiempo real.
- **Depuración**: Captura pantallazos y logs HTML automáticamente en caso de error.

## 🛠️ Arquitectura de Conexión (CDP)

Este proyecto utiliza una configuración especial para correr Playwright **dentro del contenedor**, pero controlando un **Brave visible en tu Mac** (vía CDP). Esto es fundamental para:
1.  **Evitar bloqueos**: Los portales judiciales suelen tener medidas anti-bot estrictas.
2.  **Interactividad**: Puedes intervenir manualmente si aparece un captcha.
3.  **Visibilidad**: Ves exactamente lo que el robot está haciendo.

En la práctica:
- Brave corre en tu Mac con `--remote-debugging-port=9222`
- Un forwarder expone `0.0.0.0:9223` → `127.0.0.1:9222`
- El contenedor usa `PLAYWRIGHT_CDP_URL=http://$HOST_IP:9223`

Nota importante: Brave suele validar el `Host` del request; por eso **se usa una IP** (ej. `http://192.168.1.10:9223`) en vez de `localhost`, para evitar errores.

---

## ⚙️ Configuración e Inicio Rápido

### 1) Configura `HOST_IP` (si no usas `start.sh`)

Playwright necesita la IP de tu Mac para conectarse desde el contenedor. Si vas a levantar con `docker compose` manualmente, obtén tu IP local (ej: `ipconfig getifaddr en0`) y crea/ajusta un archivo `.env` en la raíz del proyecto:

```bash
HOST_IP=192.168.1.XXX
```

### 2) Ejecución (Recomendado)

Utiliza el script automatizado para levantar todo el entorno de forma robusta:

```bash
# Permisos de ejecución la primera vez
chmod +x start.sh

# Inicia Brave, el forwarder y los contenedores
./start.sh
```

El script se encarga de:
1.  **Limpiar procesos previos**: Libera los puertos `9222` y `9223` automáticamente antes de empezar para evitar errores de "Address already in use".
2.  **Gestionar el ciclo de vida**: Abre Brave y el forwarder, espera a que estén listos, y levanta Docker Compose.
3.  **Cierre Seguro**: Al presionar `Ctrl+C`, se asegura de matar los procesos del host y liberar los puertos correctamente.

## 🤖 Ecosistema de Automatización

El proyecto está diseñado para funcionar como una pieza central en flujos de trabajo de n8n, pero **n8n ya no corre local**:

- **n8n (VPS)**: Orquesta el flujo end-to-end desde un servidor remoto.
- **Cloudflare Tunnel**: Permite que n8n (en el VPS) invoque tu FastAPI corriendo en tu computador local, sin exponer puertos del router.
- **FastAPI (local)**: Recibe los casos, ejecuta Playwright (CDP hacia Brave en tu Mac) y devuelve el reporte HTML.
- **Notificaciones**: n8n envía el HTML resultante por correo como reporte consolidado.

- **Reportes Email-Ready**: El HTML generado utiliza estilos inline y tablas, asegurando que se vea correctamente en Gmail, Outlook y otros clientes de correo.

---

## 📖 Uso de la API

Una vez levantado, el servicio estará disponible en:
- **Local**: `http://localhost:8000`
- **Desde n8n (VPS)**: la URL pública que configures en tu **Cloudflare Tunnel** (ej: `https://<tu-hostname>/`)

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

1.  **Iniciar Brave en macOS (CDP):**
    ```bash
    /Applications/Brave\ Browser.app/Contents/MacOS/Brave\ Browser \
      --remote-debugging-port=9222 \
      --remote-allow-origins=* \
      --user-data-dir="$HOME/brave-pw-profile"
    ```
2.  **Iniciar el Forwarder:**
    ```bash
    python complements/run_browser.py
    ```
3.  **Docker Compose:**
    ```bash
    docker compose up --build
    ```

