# ============================================================
# COUNTER MODULE — guardar como: counter.py
# ============================================================
import json
import os
from datetime import datetime
from threading import Lock

COUNTER_FILE = "counter.json"
_lock = Lock()


def _load():
    if not os.path.exists(COUNTER_FILE):
        return {"total": 0, "by_bank": {}, "by_ip": {}, "history": []}
    return json.load(open(COUNTER_FILE, "r"))


def _save(data):
    with open(COUNTER_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def increment(banco: str, ip: str = "desconocida"):
    """Llamar cuando un PDF se procesa exitosamente."""
    with _lock:
        data = _load()
        data["total"] += 1
        data["by_bank"][banco] = data["by_bank"].get(banco, 0) + 1
        data["by_ip"][ip]      = data["by_ip"].get(ip, 0) + 1
        data["history"].append({
            "banco":     banco,
            "ip":        ip,
            "timestamp": datetime.now().isoformat()
        })
        # Mantener solo los últimos 500 registros en el historial
        data["history"] = data["history"][-500:]
        _save(data)


def get_stats():
    with _lock:
        return _load()


# ============================================================
# ADMIN ROUTE — agregar esto a tu app.py (Flask)
# ============================================================
#
# import counter
#
# @app.route("/admin/stats")
# def admin_stats():
#     stats = counter.get_stats()
#     html = f
#     <!DOCTYPE html>
#     <html lang="es">
#     <head>
#         <meta charset="UTF-8">
#         <title>Stats - Bank Parser</title>
#         <style>
#             body {{ font-family: 'Segoe UI', sans-serif; background: #f5f5f5;
#                    display: flex; justify-content: center; padding: 40px; }}
#             .card {{ background: white; border-radius: 12px; padding: 30px;
#                      max-width: 700px; width: 100%;
#                      box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
#             h1 {{ color: #333; margin-bottom: 20px; }}
#             .stat {{ font-size: 48px; font-weight: bold;
#                      color: #667eea; margin: 10px 0 20px; }}
#             table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
#             th {{ text-align: left; padding: 10px; background: #f0f0f0; }}
#             td {{ padding: 10px; border-bottom: 1px solid #eee; font-size: 13px; }}
#             .recent {{ margin-top: 10px; max-height: 300px; overflow-y: auto; }}
#             .entry {{ font-size: 13px; color: #555; padding: 5px 0;
#                       border-bottom: 1px solid #f0f0f0; }}
#             .ip {{ color: #888; margin-left: 8px; font-size: 12px; }}
#         </style>
#     </head>
#     <body>
#         <div class="card">
#             <h1>📊 Estadísticas de uso</h1>
#             <p>PDFs procesados en total:</p>
#             <div class="stat">{stats['total']}</div>
#
#             <h3>Por banco:</h3>
#             <table>
#                 <tr><th>Banco</th><th>Cantidad</th></tr>
#                 {''.join(f"<tr><td>{b}</td><td>{n}</td></tr>"
#                          for b, n in sorted(stats['by_bank'].items(),
#                                             key=lambda x: -x[1]))}
#             </table>
#
#             <h3 style="margin-top:20px">Por IP:</h3>
#             <table>
#                 <tr><th>IP</th><th>Usos</th></tr>
#                 {''.join(f"<tr><td>{ip}</td><td>{n}</td></tr>"
#                          for ip, n in sorted(stats.get('by_ip', {{}}).items(),
#                                              key=lambda x: -x[1]))}
#             </table>
#
#             <h3 style="margin-top:20px">Últimos usos:</h3>
#             <div class="recent">
#                 {''.join(
#                     f'<div class="entry">🕐 {e["timestamp"][:16].replace("T"," ")} — {e["banco"]}'
#                     f'<span class="ip">({e.get("ip","?")})</span></div>'
#                     for e in reversed(stats.get('history', [])[-50:])
#                 )}
#             </div>
#         </div>
#     </body>
#     </html>
#
#     return html
#
#
# ============================================================
# EN TU RUTA /process — así debe quedar la llamada:
# ============================================================
#
# @app.route("/process", methods=["POST"])
# def process():
#     banco = request.form.get("banco")
#     # ... tu lógica existente ...
#
#     # Obtener la IP real del usuario (funciona con y sin proxy):
#     ip = request.headers.get("X-Forwarded-For", request.remote_addr)
#
#     # Si hay múltiples IPs en el header (cadena de proxies), tomar solo la primera:
#     ip = ip.split(",")[0].strip()
#
#     # Cuando el procesamiento es exitoso, ANTES del return:
#     counter.increment(banco, ip=ip)
#
#     return send_file(...)
