# CONOCIMIENTOS.md — Base de conocimientos de MotorGuardian

Registra conceptos, aprendizajes y buenas prácticas descubiertas durante el desarrollo. No registra hitos, decisiones ni arquitectura (eso va en `PROYECTO.md`/`BITACORA.md`). Es material de referencia: se consulta bajo demanda, no es lectura obligatoria al inicio de sesión.

---

# Git

## C-001 — Funcionamiento de `.gitignore`

`.gitignore` impide que Git empiece a seguir archivos nuevos, pero no deja de seguir archivos que ya fueron agregados anteriormente. Si un archivo ya fue agregado con `git add`, agregarlo después a `.gitignore` no basta — hay que ejecutar `git rm --cached <archivo>` (o `-r <carpeta>`).

## C-002 — Revisar siempre antes de agregar archivos

Antes de `git add .`, revisar `git status` para confirmar que solo se agregan archivos que realmente pertenecen al proyecto. Nunca asumir que `git add .` agregará solo lo esperado.

---

# Python

## C-003 — Carpeta `__pycache__`

Se genera automáticamente al importar/ejecutar un módulo. No es un error ni algo creado manualmente; almacena bytecode compilado para acelerar ejecuciones futuras.

## C-004 — Archivos `.pyc`

Bytecode generado automáticamente por Python. No deberían formar parte del repositorio Git.

## C-005 — `pathlib`

Preferir `Path()` sobre concatenar rutas con strings — es independiente del sistema operativo.

## C-006 — Lectura segura de YAML

Usar `yaml.safe_load()` en vez de `yaml.load()`, por seguridad.

## C-007 — Entornos virtuales (`venv`)

Cada proyecto usa su propio `venv`: aísla dependencias, evita conflictos de versiones, permite reproducir el entorno en otros equipos.

## C-008 — Activación del entorno virtual

Con el venv activo, el prompt muestra `(.venv)`: `pip` instala solo dentro del proyecto, no se usan librerías globales.

## C-009 — Política de ejecución de PowerShell

Si Windows bloquea la ejecución de scripts, habilitar para el usuario actual con:
```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

---

# AWS

## C-010 — Credenciales AWS

boto3 usa el perfil configurado con `aws configure`. No hace falta escribir credenciales en el código Python.

## C-011 — Sobrescritura en Amazon S3

`upload_file()` de boto3 sobrescribe automáticamente un objeto existente con la misma `Key`. Para evitarlo, verificar antes con `head_object()` (ver `almacenamiento/almacenamiento_s3.py`).

---

# Arquitectura de software

## C-012 — Responsabilidad del punto de entrada principal

El flujo principal (`principal.py` o equivalente) no debe contener lógica de negocio — su responsabilidad es coordinar módulos especializados.

## C-013 — Separación de responsabilidades

Separar responsabilidades desde el inicio facilita modificar una parte del sistema sin afectar las demás — p. ej., cambiar la fuente de configuración (YAML, base de datos, AWS Parameter Store) solo debería requerir tocar el módulo de configuración.

## C-014 — Organización del proyecto

Separar código fuente, herramientas auxiliares y pruebas automatizadas en carpetas distintas, cada una con responsabilidad específica.

## C-015 — Herramientas vs. pruebas

`herramientas/` son programas auxiliares de desarrollo u operación; `tests/` son pruebas automatizadas (p. ej. con pytest). No mezclar ambos conceptos.

## C-016 — Diagramas de arquitectura reproducibles

Generar diagramas técnicos (PNG de alta resolución) con un script versionado (matplotlib) en vez de una imagen estática editada a mano, permite regenerarlos cuando la arquitectura cambie sin depender de rehacerlos manualmente. Ver `herramientas/generar_diagrama_arquitectura.py`.

## C-017 — `uvicorn --reload` puede dejar procesos huérfanos en Windows

Con `--reload`, `uvicorn` levanta un proceso supervisor y un proceso hijo (vía `multiprocessing`) que es el que realmente escucha el puerto. Si se termina solo el proceso padre (por ejemplo, cerrando la ventana o con `Stop-Process` sobre el PID equivocado), el hijo puede seguir vivo y ocupando el puerto — el siguiente intento de levantar el backend falla con `[Errno 10048] address already in use`, aunque `Get-Process` no muestre nada raro a simple vista.

Para diagnosticarlo: `Get-CimInstance Win32_Process -Filter "Name = 'python.exe'"` mostrando `CommandLine` y `ParentProcessId` — el hijo aparece con `-c "from multiprocessing.spawn import spawn_main..."` y el PID del padre. Hay que terminar el hijo (y el padre si sigue vivo), no asumir que matar uno basta.

---

# Reflexión

MotorGuardian no solo busca construir un sistema de mantenimiento predictivo: también busca construir una base sólida de conocimientos en Ingeniería de Software, Python, AWS, Git, Arquitectura de Software, Inteligencia Artificial y buenas prácticas de desarrollo. Este documento crece durante todo el proyecto.
