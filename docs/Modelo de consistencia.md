# Modelo de consistencia efectivo

## Resumen

**Replicación de líder único, asíncrona, con consistencia eventual y reconciliación por vectores de versión.**
Durante una partición el sistema prioriza **disponibilidad (A)** sobre **consistencia (C)** en el lado del líder aislado (modo AP, por defecto) y puede configurarse en **CP** (`require_quorum_for_writes: true`).

## Reglas

1. **Escritura.** Solo el líder (el nodo que ganó la elección con mayoría) escribe. Un seguidor que recibe una escritura la **reenvía** al líder; si no hay líder vigente o es inaccesible, la **rechaza**. Las réplicas de Redis son de solo lectura, así que escribir directo en una réplica falla (`READONLY`).
2. **Versionado.** Cada escritura sobre un recurso incrementa la componente del escritor en el **vector de versión** de ese recurso y recibe una marca de **Lamport**. La entrada guarda `vv`, `lamport`, `writer`, `term`.
3. **Replicación.** El líder escribe en su Redis (maestro); las réplicas reciben los cambios de forma **asíncrona** (`REPLICAOF`). La escritura se confirma al cliente al aplicarse en el maestro, sin esperar a las réplicas.
4. **Lectura.** Se lee del Redis local de cada nodo: en el líder es lo último escrito; en un seguidor puede estar **desactualizado** (lecturas eventualmente consistentes).
5. **Cambio de líder.** El nuevo líder promueve su Redis (`REPLICAOF NO ONE`) y los demás lo siguen. Escrituras confirmadas por el líder viejo y aún no replicadas pueden no estar en el nuevo líder: se recuperan en la reconexión (punto 7).
6. **Partición.** El lado con mayoría elige un nuevo líder (término mayor). El líder aislado sigue creyéndose líder: en modo AP **acepta** escrituras (marcadas `sin_quorum` en su diario); en modo CP las **rechaza**. Un seguidor aislado no puede escribir (no ve al líder).
7. **Reconexión.** El antiguo líder ve un término mayor con certificado válido, se degrada, y envía su inventario al nuevo líder (`REJOIN`). Por cada recurso el nuevo líder compara vectores:
   * iguales o local domina → no hace nada;
   * remoto domina → **avance simple** (se adopta, no es conflicto);
   * ninguno domina → **conflicto**: gana mayor Lamport, empate → menor id de escritor. El resultado lleva el vector fusionado +1 del resolutor, por lo que domina a ambas versiones.
   Después el antiguo líder pasa a ser réplica del nuevo (resincronización completa) y todos convergen.

## Garantías

| Propiedad | ¿Se cumple? |
|---|---|
| Líder único *por término* | Sí (voto único por término + mayoría) |
| Líder único *en el mismo instante* durante una partición | **No**: el aislado sigue creyéndose líder hasta reconectar (se documenta y se mide) |
| Convergencia tras reconectar | Sí (todos terminan con la entrada resuelta) |
| Lecturas linealizables | No (réplicas asíncronas) |
| Ninguna actualización perdida | **No**: la regla *last-writer-wins* descarta el valor perdedor de una escritura concurrente. Se conserva en `conflictos-N.jsonl` para auditoría |

## Anomalía conocida (para Limitaciones)

`allocate` es una operación relativa (resta recursos). Si dos líderes asignan a la vez sobre el mismo recurso, la regla LWW conserva **una** de las dos asignaciones y la otra se pierde (el recurso queda “más libre” de lo real). Trabajo futuro: contadores CRDT (PN-counter) o re-aplicar la operación perdedora desde el diario.

## Redis y CP

Redis ofrece `min-replicas-to-write` / `min-replicas-max-lag` para que un maestro rechace escrituras sin réplicas conectadas. Está comentado en `scripts/02-configurar-redis.sh`; equivale en Redis al modo CP que la aplicación implementa con `require_quorum_for_writes`.
