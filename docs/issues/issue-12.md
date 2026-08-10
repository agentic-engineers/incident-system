# Issue #12 — Incidentes duplicados cuando llegan alertas en ráfaga

**Labels:** bug, worker, prioridad-alta

Cuando el monitoreo manda una tormenta de alertas iguales (por ejemplo el
viernes pasado con lo del disco de web-01), aparecen incidentes repetidos
con el mismo título. El viernes quedaron 6 tickets idénticos y el equipo
de guardia procesó los 6.

Se supone que el deduplicador evita esto.

Pasos para reproducir: mandar varias veces la misma alerta MUY seguido
(en el mismo segundo). Con una sola no pasa.
