import os
import subprocess
import signal
import sys
from multiprocessing import Process

# Añadimos el directorio actual al path para que el import funcione si se corre desde la raíz
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from host_cdp_forward import run_forwarder


def run_forwarder_process():
    try:
        run_forwarder(
            listen_port=9223,
            target_port=9222,
            listen_host="0.0.0.0",
            target_host="127.0.0.1",
        )
    except Exception as e:
        print(f"Error en forwarder: {e}")


def run_browser_process():
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    args = [
        chrome_path,
        "--remote-debugging-port=9222",
        f"--user-data-dir={os.path.expandvars('$HOME/chrome-pw-profile')}",
    ]
    try:
        # Usamos Popen para tener el PID y poder matarlo si es necesario
        subprocess.run(args)
    except Exception as e:
        print(f"Error al iniciar Chrome: {e}")


if __name__ == "__main__":
    forwarder_process = Process(target=run_forwarder_process)
    browser_process = Process(target=run_browser_process)

    def signal_handler(sig, frame):
        print("\n[run_browser] Deteniendo procesos...")
        forwarder_process.terminate()
        browser_process.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    forwarder_process.start()
    browser_process.start()

    forwarder_process.join()
    browser_process.join()
