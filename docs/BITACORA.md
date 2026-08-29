# BITACORA.md — MotorGuardian

Registro cronológico de avances. Es un log de solo-agregar: no se edita retroactivamente, solo se agregan entradas nuevas al final. No es lectura obligatoria completa al inicio de sesión (ver `PROYECTO.md`) — basta con revisar las últimas entradas.

---

## 2026-07-06

- Creación de la cuenta AWS.
- Configuración de presupuesto.
- Creación del bucket S3 (`motorguardian-lab-vramirez`).
- Definición de la estructura de directorios.
- Primer commit del proyecto (`motorguardian`).

## 2026-07-07

- Configuración del entorno virtual `.venv`.
- Instalación de PyYAML y boto3.
- Creación de `requirements.txt`.
- Lectura de `config/aws.yaml` probada correctamente desde Python.
- Creación de `docs/Conocimientos.md`.
- Avance en la definición del módulo de almacenamiento S3.

## 2026-07-08

- Validación funcional del módulo S3: subida cuando el objeto no existe, y verificación de que no se sobrescribe cuando ya existe. Ambas pruebas exitosas.

## 2026-08-28 — Fusión de proyectos

- Se fusionaron `analizador_vibraciones` y `motorguardian` en un solo proyecto, `mg/`, sin modificar los archivos originales de ninguno de los dos.
- Se portó el backend FastAPI (lectura de CSV + FFT) y el frontend React/Vite de `analizador_vibraciones`, manteniendo su despliegue visual tal cual.
- Se portó el módulo de almacenamiento S3 de `motorguardian` (`configuracion.py`, `almacenamiento_s3.py`, `config/aws.yaml`), con el acceso real a AWS comentado en `herramientas/subir_archivo_s3.py` para control manual.
- Se agregó el módulo `backend/procesamiento/estadisticos.py` y el endpoint `/api/estadisticos` (curtosis, factor de cresta, skewness por eje X/Y/Z).
- Se agregaron 3 pestañas nuevas en el frontend (Curtosis, Factor de Cresta, Skewness), a la derecha de "Vibración en el tiempo" y "Espectro FFT".
- Se verificó end-to-end: backend (`uvicorn`, puerto 8000) y frontend (`vite`, puerto 5173) levantados y probados en navegador — carga de CSV, gráfico de señal en el tiempo, FFT y los 3 estadísticos nuevos, todo funcionando.
- Se generó el diagrama de arquitectura (`docs/arquitectura_servidores.png`) con su script reproducible (`herramientas/generar_diagrama_arquitectura.py`).
- Se consolidó la documentación: de 11 archivos `.md` repartidos entre los dos proyectos originales (varios con contenido duplicado, en especial `IA.md` y `PrincipiosDesarrollo.md`) a 4 documentos en `mg/docs/` (`PROYECTO.md`, `ARQUITECTURA.md`, `BITACORA.md`, `CONOCIMIENTOS.md`).
