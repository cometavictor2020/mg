# CLAUDE.md — MotorGuardian

Proyecto de mantenimiento predictivo (Python + FastAPI + React/Vite + AWS S3). Este archivo es solo un puntero — el contenido completo vive en `docs/`.

## Al iniciar sesión

1. Leer completo **`docs/PROYECTO.md`** (objetivo, estado actual, deuda técnica, decisiones, principios, roadmap).
2. Revisar las últimas entradas de **`docs/BITACORA.md`**.
3. `docs/ARQUITECTURA.md` y `docs/CONOCIMIENTOS.md` se consultan solo si hace falta — no son lectura obligatoria.

## Reglas duras

- **Nunca modificar** archivos dentro de `C:\Users\comet\Documents\analizador_vibraciones` ni `C:\Users\comet\Documents\motorguardian`. Son los proyectos originales, ya fusionados en `mg/`; quedan como archivo histórico, solo lectura.
- El acceso real a AWS S3 se mantiene **manual**: la llamada de subida en `herramientas/subir_archivo_s3.py` permanece comentada salvo que el usuario pida explícitamente activarla.
- No hardcodear plantas, motores, sensores, fechas o archivos fuera de `herramientas/` (ver D-011 en `PROYECTO.md`).

## Al cerrar sesión

Si cambió el estado, una decisión o el roadmap: actualizar `docs/PROYECTO.md` y agregar una entrada en `docs/BITACORA.md`.

## Comandos

Backend (FastAPI, puerto 8000):
```powershell
cd C:\Users\comet\Documents\mg
.\venv\Scripts\Activate.ps1
python -m uvicorn backend.api.main:app --reload --port 8000
```

Frontend (React + Vite, puerto 5173):
```powershell
cd C:\Users\comet\Documents\mg\frontend
npm run dev
```

Regenerar el diagrama de arquitectura:
```powershell
cd C:\Users\comet\Documents\mg
.\venv\Scripts\Activate.ps1
python herramientas\generar_diagrama_arquitectura.py
```
