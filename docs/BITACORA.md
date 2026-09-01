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
- Se creó `mg/CLAUDE.md` como puntero corto (leído automáticamente al inicio de sesión), apuntando a `docs/PROYECTO.md` y `docs/BITACORA.md`, con las reglas duras y los comandos de arranque.

## 2026-09-01 — Respaldo en GitHub y base de datos MySQL

- Se inicializó git en `mg/` desde cero (manualmente, por el desarrollador, siguiendo instrucciones paso a paso) y se recrearon los 4 commits con sus fechas originales preservadas (`GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`).
- Se detectó y corrigió: `datos/datos_vibracion_motor.csv` (157 MB) superaba el límite de 100 MB de GitHub — se agregó a `.gitignore` y se rehizo el historial sin él (el archivo se queda en el disco local, no se pierde).
- Se creó el repositorio privado `github.com/cometavictor2020/mg` (GitHub CLI, autenticación con token de acceso personal) y se subió el historial completo.
- Se decidió despriorizar los autoencoders al final del roadmap (D-019): es el ítem que más tiempo de desarrollo consumiría.
- Se diseñó el esquema de base de datos (Equipo, Sensor, Medición, ResultadoAnalisis, catálogos abiertos TipoEquipo/TipoSensor, JSON para atributos específicos por tipo) y se decidió usar **MySQL** en vez de SQLite, por el requisito explícito de soportar múltiples usuarios desde ya (D-020).
- Se instaló MySQL Server 8.4 localmente (vía winget), inicializado sin servicio de Windows (sin permisos de administrador disponibles) — corre como proceso manual. Se creó la base de datos `motorguardian`, un usuario dedicado `motorguardian_app` (no root), y las 8 tablas del esquema vía `basedatos/modelos.py` (SQLAlchemy) y `herramientas/crear_tablas_basedatos.py`. Credenciales guardadas en `.env` (gitignored).
- Pendiente explícito: conectar la base de datos a la API (endpoints `/api/equipos`) y el formulario web de ingreso de equipos; definir el mecanismo de respaldo de la base de datos (nunca vía Git/GitHub).
- Se estableció como regla permanente (agregada a `CLAUDE.md`): git es siempre manual (el desarrollador ejecuta los comandos que se le indican, nunca la IA), y nada se sube a GitHub sin una orden explícita en la misma sesión.

## 2026-09-01 (continuación) — Autenticación, Login y Resumen General

- Se agregó `password_hash` a la tabla `usuario` (vía `ALTER TABLE`, sin destruir la tabla existente) y el módulo `seguridad/auth.py` (hash de contraseñas con bcrypt, tokens de sesión con PyJWT, `SECRET_KEY` en `.env`).
- Se agregó el endpoint `POST /api/auth/login` y la herramienta `herramientas/crear_usuario_demo.py`, que sembró el usuario `admin@motorguardian.io` / `mg2024` (Carlos Mendoza, administrador).
- Se construyeron dos pantallas nuevas replicando exactamente los mockups entregados por el desarrollador (`mg-intro.png` y `resumen-general.png`): `Login.jsx` y `ResumenGeneral.jsx`. Los colores se extrajeron con Python/Pillow directamente de los píxeles de los PNG (no a ojo), incluyendo un análisis de frecuencia de colores y escaneos de líneas para separar con precisión fondo de página, fondo de tarjeta y colores de estado (verde/ámbar/rojo/gris).
- Se extrajo el sidebar a un componente compartido (`components/Sidebar.jsx`), reutilizado por `ResumenGeneral` y por `AnalizadorVibraciones` (que se adaptó para recibir la sesión real y navegar de vuelta a Resumen General), sin alterar la apariencia heredada.
- `App.jsx` pasó a ser un enrutador simple: Login → Resumen General → detalle de equipo, con la sesión persistida en `localStorage`.
- Verificado end-to-end en el navegador: login exitoso, login con credenciales incorrectas (mensaje de error visible), navegación equipo → detalle → volver a Resumen General, y cierre de sesión.
- Pendiente explícito: los endpoints `/api/datos`, `/api/fft` y `/api/estadisticos` todavía no validan el token JWT (quedan públicos); `equiposDemo.js` sigue siendo data dummy, no conectada a la base de datos.
