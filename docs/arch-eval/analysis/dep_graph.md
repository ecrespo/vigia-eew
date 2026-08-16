# Grafo de dependencias (módulos)

**Repo:** `/home/user/vigia-eew` · Archivos: 79 · Módulos: 7 · Aristas: 15

## 🔴 Ciclos de dependencia (SCCs) — evidencia P1

1. `src/vigia_eew` ↔ `src/vigia_eew/autostart` ↔ `src/vigia_eew/ingest` ↔ `src/vigia_eew/notify` ↔ `src/vigia_eew/pipeline`

### Pares mutuos (A→B y B→A)

- `src/vigia_eew` ↔ `src/vigia_eew/autostart`
- `src/vigia_eew` ↔ `src/vigia_eew/ingest`
- `src/vigia_eew` ↔ `src/vigia_eew/notify`
- `src/vigia_eew` ↔ `src/vigia_eew/pipeline`

## Métricas por módulo (orden: acoplamiento)

| Módulo | Archivos | LOC | Fan-in | Fan-out | Inestabilidad | Score |
|---|---|---|---|---|---|---|
| `src/vigia_eew` | 19 | 1773 | 6 | 4 | 0.4 | 24 |
| `src/vigia_eew/pipeline` | 5 | 402 | 2 | 2 | 0.5 | 4 |
| `src/vigia_eew/ingest` | 5 | 568 | 3 | 1 | 0.25 | 3 |
| `src/vigia_eew/notify` | 7 | 586 | 2 | 1 | 0.33 | 2 |
| `src/vigia_eew/autostart` | 4 | 271 | 2 | 1 | 0.33 | 2 |
| `tests` | 37 | 3433 | 0 | 5 | 1.0 | 0 |
| `packaging` | 2 | 64 | 0 | 1 | 1.0 | 0 |

## ⚠️ Candidatos a god-module (verificar en Fase 1)

- `src/vigia_eew` — fan-in 6, fan-out 4, 1773 LOC

## Diagrama

```mermaid
graph LR
  tests["tests"] --> src_vigia_eew["src/vigia_eew"]
  tests["tests"] --> src_vigia_eew_ingest["src/vigia_eew/ingest"]
  tests["tests"] --> src_vigia_eew_pipeline["src/vigia_eew/pipeline"]
  src_vigia_eew_pipeline["src/vigia_eew/pipeline"] --> src_vigia_eew["src/vigia_eew"]
  src_vigia_eew_ingest["src/vigia_eew/ingest"] --> src_vigia_eew["src/vigia_eew"]
  src_vigia_eew_notify["src/vigia_eew/notify"] --> src_vigia_eew["src/vigia_eew"]
  tests["tests"] --> src_vigia_eew_notify["src/vigia_eew/notify"]
  tests["tests"] --> src_vigia_eew_autostart["src/vigia_eew/autostart"]
  src_vigia_eew["src/vigia_eew"] --> src_vigia_eew_notify["src/vigia_eew/notify"]
  src_vigia_eew["src/vigia_eew"] --> src_vigia_eew_ingest["src/vigia_eew/ingest"]
  src_vigia_eew["src/vigia_eew"] --> src_vigia_eew_pipeline["src/vigia_eew/pipeline"]
  src_vigia_eew_autostart["src/vigia_eew/autostart"] --> src_vigia_eew["src/vigia_eew"]
  src_vigia_eew_pipeline["src/vigia_eew/pipeline"] --> src_vigia_eew_ingest["src/vigia_eew/ingest"]
  src_vigia_eew["src/vigia_eew"] --> src_vigia_eew_autostart["src/vigia_eew/autostart"]
  packaging["packaging"] --> src_vigia_eew["src/vigia_eew"]
```
