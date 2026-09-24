---
paths:
  - "app/**"
---

# Reglas al trabajar dentro de app/

- El contrato de estados de un incidente vive en `app/domain/models.py`;
  verifica contra él antes de razonar sobre la cola.
- El worker y la API deben leerse JUNTOS: lo que uno escribe y el otro
  consume es un contrato implícito, y ahí viven los bugs de integración.
