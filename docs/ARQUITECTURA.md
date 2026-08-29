# ARQUITECTURA.md — MotorGuardian

**Última actualización:** 2026-08-28
Consulta bajo demanda — no es lectura obligatoria al inicio de sesión (ver `PROYECTO.md`).

Diagrama visual: [`docs/arquitectura_servidores.png`](arquitectura_servidores.png) (regenerable con `herramientas/generar_diagrama_arquitectura.py`).

---

## Tecnologías

- Python (FastAPI, pandas, numpy, scipy, boto3, PyYAML, matplotlib para herramientas)
- React + Vite
- Recharts
- AWS S3 (boto3)

---

## Estructura de carpetas

```
mg/
  backend/
    api/main.py              → endpoints REST (FastAPI)
    procesamiento/
      lectura_csv.py         → lectura de CSV (pandas)
      frecuencia.py          → cálculo de FFT
      estadisticos.py        → curtosis, factor de cresta, skewness
  almacenamiento/
    configuracion.py         → lectura de config/aws.yaml
    almacenamiento_s3.py     → subida a S3 (boto3), sin sobrescritura
  config/aws.yaml            → bucket, región, ruta raíz de storage
  herramientas/
    subir_archivo_s3.py      → subida manual a S3 (acceso comentado)
    generar_diagrama_arquitectura.py
  datos/                     → CSV de prueba
  frontend/                  → React + Vite (puerto 5173)
  docs/                      → PROYECTO.md, ARQUITECTURA.md, BITACORA.md, CONOCIMIENTOS.md
  requirements.txt
  venv/
```

---

## Flujo de datos

**Extremo backend ↔ extremo frontend (los dos lados de la API):**

```
Motor + Sensores (vibración triaxial, temperatura)
        ↓ genera muestras (hoy: CSV sintético)
Archivo CSV (datos/datos_vibracion_motor.csv)
        ↓ pandas.read_csv()
Servidor Backend — FastAPI (Python) — PORT: 8000 — 127.0.0.1:8000
        ⇄ FastAPI · API REST (JSON)
          GET /api/datos · /api/fft · /api/estadisticos
          CORS: 127.0.0.1:8000 ⇄ localhost:5173
Servidor Frontend — React + Vite — PORT: 5173 — localhost:5173
        ↓ renderiza (Recharts)
Navegador — Dashboard MotorGuardian
```

**Camino hacia AWS (independiente del servidor FastAPI, manual):**

```
Archivo CSV (datos/) → herramientas/subir_archivo_s3.py (lectura manual)
        ↓ boto3 · upload_file() — actualmente comentado (control manual)
AWS S3 — bucket motorguardian-lab-vramirez — región us-east-1
```

---

## Principios de arquitectura

- Backend desacoplado del frontend.
- Frontend independiente del backend (Core preparado para eventualmente servir otras interfaces).
- Procesamiento (`backend/procesamiento/`) siempre separado de los endpoints (`backend/api/`) — ningún endpoint contiene lógica de cálculo ni lee archivos directamente.
- Arquitectura preparada para escalar a otros equipos (motores trifásicos, aerogeneradores, ventiladores, bombas centrífugas) y otros sensores (termografía, corriente eléctrica, ultrasonido, análisis de fluidos), evitando acoplar el sistema exclusivamente a vibraciones o a motores.
- El almacenamiento en AWS es un módulo independiente del servidor FastAPI, no una llamada automática dentro de él.

---

## Limitaciones actuales (ver también "Deuda técnica" en `PROYECTO.md`)

- `main.py` tiene hardcodeados la ruta del CSV y la frecuencia de muestreo.
- `calcular_fft` y `calcular_estadisticos` requieren explícitamente columnas `vibracion_x/y/z` — no son genéricos todavía para otros tipos de sensor.
- El sidebar de equipos del frontend usa datos dummy no conectados al backend.
- Sin base de datos: cada request relee el CSV desde disco: no hay persistencia de resultados procesados.
