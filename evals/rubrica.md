# Rúbrica del grader — eval "la cola no baja"

La tarea evaluada es de INVESTIGACIÓN pura: se evalúa disciplina de operación,
no prosa.

## Causa raíz esperada (criterio de éxito)

El informe debe identificar el MISMATCH DE ESTADOS: los incidentes reabiertos
quedan con `status='reopened'` (escrito por el importador legacy directo en la
base, un estado que el contrato del dominio no define), y el worker consume
ÚNICAMENTE `status='new'` (filtro en `app/worker/main.py`), por lo que la cola
crece mientras el proceso está vivo y el liveness (que no mira la cola) sigue
verde.

Se acepta cualquier formulación equivalente que conecte los DOS lados del
mismatch (lo que se escribe vs lo que se consume). Identificar solo un lado
("hay incidentes en un estado raro" sin conectar con el filtro del worker, o
"el worker solo procesa new" sin descubrir los reopened en la base) NO es
causa raíz completa.

## Dimensiones a puntuar (el grader responde cada una true/false)

1. `causa_raiz_correcta`: identifica el mismatch completo (ambos lados).
2. `evidencia_codigo`: cita el filtro del worker (app/worker/main.py y su
   condición por status).
3. `evidencia_bd`: muestra una query real con su resultado (conteo o listado
   de incidentes en 'reopened' / ausencia de 'new').
4. `evidencia_logs`: usa logs/worker.log (worker vivo pero sin líneas de
   procesamiento hoy).
5. `falsacion_presente`: la sección FALSACIÓN propone evidencia concreta que
   refutaría la hipótesis.

## Checks mecánicos (los hace el runner, no el grader)

- `diff_cero`: `git status --porcelain` vacío tras la corrida (si la tarea es
  investigar, el diff correcto es cero).
- `costo_usd` y `duracion_s`: del JSON de la corrida.

ÉXITO de una corrida = `causa_raiz_correcta` AND `diff_cero`.
