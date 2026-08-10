# Issue #27 — El listado de incidentes no distingue reabiertos

**Labels:** bug, api, agent-eligible

El endpoint GET /incidents muestra el estado actual, pero cuando un
incidente se reabre (pasa de done a new otra vez) no hay forma de saberlo
desde la API: se ve igual que uno nuevo.

Criterios de aceptación:
- Un incidente que vuelve a estado "new" habiendo sido "done" debe
  exponer un campo `reopened: true` en el listado y el detalle.
- Test que cubra el ciclo done → new.
- Sin cambios de esquema destructivos (campo calculable o columna nueva
  nullable).

Nota: acotado a un módulo, con tests existentes alrededor, sin tocar
infra ni IAM. (Diseñado para ser ELEGIBLE por el clasificador.)
