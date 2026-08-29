# Deploy

1. Hablar con Marcos para que corra el terraform desde su máquina.
2. `docker build` en la máquina de deploy y subir la imagen (tag: fecha).
3. Reiniciar los servicios.
4. Mirar los logs un rato para ver que no explote.
   Para el worker: eventos, métricas y qué hacer si la cola crece en
   [worker.md](worker.md).

<!-- TODO(2023): automatizar esto -->
