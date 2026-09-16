# CLAUDE.md — MotorGuardian

Proyecto de mantenimiento predictivo (Python + FastAPI + React/Vite + AWS S3 + MySQL). Este archivo es solo un puntero — el contenido completo vive en `docs/`.

## Al iniciar sesión

1. Leer completo **`docs/PROYECTO.md`** (objetivo, estado actual, deuda técnica, decisiones, principios, roadmap).
2. Revisar las últimas entradas de **`docs/BITACORA.md`**.
3. `docs/ARQUITECTURA.md` y `docs/CONOCIMIENTOS.md` se consultan solo si hace falta — no son lectura obligatoria.

## Reglas duras

- **Nunca modificar** archivos dentro de `C:\Users\comet\Documents\analizador_vibraciones` ni `C:\Users\comet\Documents\motorguardian`. Son los proyectos originales, ya fusionados en `mg/`; quedan como archivo histórico, solo lectura.
- El acceso real a AWS S3 se mantiene **manual**: la llamada de subida en `herramientas/subir_archivo_s3.py` permanece comentada salvo que el usuario pida explícitamente activarla.
- No hardcodear plantas, motores, sensores, fechas o archivos fuera de `herramientas/` (ver D-011 en `PROYECTO.md`).
- La base de datos MySQL **nunca se respalda vía Git/GitHub** (ni el archivo de datos ni un dump) — se respalda con `herramientas/respaldar_basedatos.py`, que guarda el volcado en `respaldos/` (excluida de Git) (D-022, D-033).
- El repositorio en GitHub es **privado** y así debe seguir; el acceso se otorga agregando colaboradores puntuales, nunca haciéndolo público (D-018).
- **Git es siempre manual**: nunca ejecutar `git add`/`git commit`/`git push` (ni ningún otro comando de git) directamente. Se indican los pasos, el desarrollador los ejecuta él mismo — es una decisión explícita para ganar soltura con git, no una limitación técnica.
- **Nunca subir nada a GitHub** (`git push`, crear/modificar repos, colaboradores, etc.) sin una orden explícita del desarrollador en esa misma sesión. El control de qué sube y qué no sube es siempre suyo.

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

MySQL (puerto 3306) — no es un servicio de Windows, hay que levantarlo manualmente cada sesión:
```powershell
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe" --defaults-file="C:\ProgramData\MySQL\MySQL Server 8.4\my.ini" --console
```
Credenciales de la app (usuario `motorguardian_app`) en `mg\.env`. La contraseña de `root` está en `mg\.env.root` (uso manual únicamente, ninguno de los dos archivos se sube a Git).

Crear/actualizar las tablas de la base de datos:
```powershell
cd C:\Users\comet\Documents\mg
.\venv\Scripts\Activate.ps1
python herramientas\crear_tablas_basedatos.py
```

Crear/actualizar el usuario demo (login: `admin@motorguardian.io` / `mg2024`):
```powershell
cd C:\Users\comet\Documents\mg
.\venv\Scripts\Activate.ps1
python herramientas\crear_usuario_demo.py
```

Respaldar la base de datos (volcado a `respaldos/`, excluida de Git):
```powershell
cd C:\Users\comet\Documents\mg
.\venv\Scripts\Activate.ps1
python herramientas\respaldar_basedatos.py
```
