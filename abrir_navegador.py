"""Wait for local server readiness before opening the browser."""
import time,urllib.request,webbrowser
for attempt in range(30):
    try:
        with urllib.request.urlopen('http://localhost:8000/',timeout=1) as response:
            if response.status==200:
                webbrowser.open('http://localhost:8000/');raise SystemExit(0)
    except (OSError,TimeoutError):
        time.sleep(1)
print('O servidor nao respondeu. Confira o erro na janela NJA System.')
raise SystemExit(1)
