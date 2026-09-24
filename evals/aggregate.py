"""Agrega los resultados de una corrida del eval en la tabla del N7."""
import json
import statistics
import sys
from pathlib import Path

out = Path(sys.argv[1])
condiciones = {}

for run_dir in sorted(out.iterdir()):
    if not run_dir.is_dir():
        continue
    cond = run_dir.name.rsplit("-", 1)[0]
    r = condiciones.setdefault(cond, [])
    try:
        result = json.loads((run_dir / "result.json").read_text())
        veredicto = json.loads((run_dir / "veredicto.json").read_text())
        cambios = (run_dir / "cambios.txt").read_text().strip()
    except (FileNotFoundError, json.JSONDecodeError) as e:
        r.append({"error": str(e), "run": run_dir.name})
        continue
    r.append(
        {
            "run": run_dir.name,
            "causa_correcta": bool(veredicto.get("causa_raiz_correcta")),
            "diff_cero": cambios == "",
            "exito": bool(veredicto.get("causa_raiz_correcta")) and cambios == "",
            "evidencias": sum(
                bool(veredicto.get(k))
                for k in ("evidencia_codigo", "evidencia_bd", "evidencia_logs")
            ),
            "falsacion": bool(veredicto.get("falsacion_presente")),
            "costo": float(result.get("total_cost_usd", 0)),
            "duracion_s": round(result.get("duration_ms", 0) / 1000),
            "turnos": result.get("num_turns"),
        }
    )

orden = ["contaminada", "limpia", "contexto"]
etiquetas = {
    "contaminada": "Sesión contaminada",
    "limpia": "Limpia sin contexto",
    "contexto": "Limpia con contexto diseñado",
}

lineas = [
    "# Tabla agregada — eval 'la cola no baja'",
    "",
    "| Condición | Éxito | Costo mediano | Tiempo mediano | Cambios innecesarios | Evidencias (de 3) |",
    "|---|---|---|---|---|---|",
]
resumen = {}
for cond in orden:
    runs = [x for x in condiciones.get(cond, []) if "error" not in x]
    errores = [x for x in condiciones.get(cond, []) if "error" in x]
    if not runs:
        lineas.append(f"| {etiquetas.get(cond, cond)} | sin corridas | - | - | - | - |")
        continue
    exitos = sum(x["exito"] for x in runs)
    con_cambios = sum(not x["diff_cero"] for x in runs)
    costo_med = statistics.median(x["costo"] for x in runs)
    dur_med = statistics.median(x["duracion_s"] for x in runs)
    ev_med = statistics.median(x["evidencias"] for x in runs)
    lineas.append(
        f"| {etiquetas.get(cond, cond)} | {exitos}/{len(runs)} | ${costo_med:.2f} | {dur_med:.0f}s | {con_cambios}/{len(runs)} | {ev_med:.0f} |"
    )
    resumen[cond] = {
        "exitos": exitos,
        "n": len(runs),
        "costo_mediano": round(costo_med, 3),
        "duracion_mediana_s": dur_med,
        "con_cambios": con_cambios,
        "errores": len(errores),
    }

lineas += ["", "Detalle por corrida en cada subdirectorio (informe.md, veredicto.json, cambios.txt)."]
(out / "tabla.md").write_text("\n".join(lineas) + "\n")
(out / "resumen.json").write_text(json.dumps(resumen, indent=2))
print("\n".join(lineas))
