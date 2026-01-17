#!/bin/bash

# Función de limpieza para asegurar que Chrome y el forwarder se cierren
cleanup() {
    echo ""
    echo "Cerrando Chrome y el forwarder en macOS..."
    if [ -n "$BROWSER_PID" ]; then
        kill $BROWSER_PID 2>/dev/null
    fi
    
    # Limpieza forzada de puertos para evitar "Address already in use"
    # Puerto 9222 (Chrome) y 9223 (Forwarder)
    lsof -ti:9222,9223 | xargs kill -9 2>/dev/null
    
    echo "Procesos finalizados."
    exit
}

# Capturar Ctrl+C (SIGINT) y señales de terminación (SIGTERM)
trap cleanup SIGINT SIGTERM

# --- LIMPIEZA PREVIA ---
# Antes de empezar, nos aseguramos que no haya nada ocupando los puertos
lsof -ti:9222,9223 | xargs kill -9 2>/dev/null

# Detectar la IP de la Mac automáticamente
export HOST_IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1)
echo "IP detectada: $HOST_IP"

echo "Iniciando Brave y el forwarder en macOS..."
# Iniciamos el script de python en segundo plano
python complements/run_browser.py &
BROWSER_PID=$!

# Esperar un momento a que los procesos del host arranquen
sleep 2

# Ejecutar docker-compose up con los argumentos que se pasen al script
# Permite hacer: ./start.sh --build o ./start.sh -d
docker compose up "$@"

# Si docker-compose termina por sí solo, ejecutamos la limpieza
cleanup
