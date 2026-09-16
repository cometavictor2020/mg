# ARQUITECTURA.md — MotorGuardian

**Última actualización:** 2026-09-01 (v3)
Consulta bajo demanda — no es lectura obligatoria al inicio de sesión (ver `PROYECTO.md`).

Diagrama visual: [`docs/arquitectura_servidores.png`](arquitectura_servidores.png) (regenerable con `herramientas/generar_diagrama_arquitectura.py`).

---

## Tecnologías

- Python (FastAPI, pandas, numpy, scipy, boto3, PyYAML, matplotlib para herramientas)
- React + Vite
- Recharts
- AWS S3 (boto3)
- MySQL (SQLAlchemy + PyMySQL) — base de datos de equipos/sensores
- bcrypt + PyJWT — autenticación (hash de contraseñas + tokens de sesión)

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
  basedatos/
    modelos.py                → modelos ORM (SQLAlchemy): TipoEquipo, Planta, Equipo,
                                 TipoSensor, Sensor, Medicion, ResultadoAnalisis, Usuario
    conexion.py                → engine/sesion de SQLAlchemy, credenciales desde .env
  config/aws.yaml            → bucket, región, ruta raíz de storage
  seguridad/
    auth.py                   → hash de contrasenas (bcrypt) + tokens JWT
  backend/api/administracion/
    usuarios.py                → CRUD /api/usuarios
    equipos.py                  → CRUD /api/equipos
    sensores.py                  → CRUD /api/sensores
    modelos_ml.py                 → CRUD /api/modelos-ml (solo metadata)
  herramientas/
    subir_archivo_s3.py      → subida manual a S3 (acceso comentado)
    generar_diagrama_arquitectura.py
    crear_tablas_basedatos.py → crea/actualiza las tablas de MySQL
    crear_usuario_demo.py     → siembra el usuario admin@motorguardian.io
  datos/                     → CSV de prueba
  frontend/                  → React + Vite (puerto 5173)
    src/pages/Login.jsx           → pantalla de acceso (mg-intro.png)
    src/pages/ResumenGeneral.jsx  → pantalla inicial tras login (resumen-general.png)
    src/pages/AnalizadorVibraciones.jsx → detalle de un equipo (tiempo/FFT/estadisticos)
    src/pages/Configuracion.jsx   → administracion (Usuarios/Equipos/Sensores/Modelos), CRUD real
    src/components/Sidebar.jsx    → sidebar compartido entre las 3 paginas autenticadas
  docs/                      → PROYECTO.md, ARQUITECTURA.md, BITACORA.md, CONOCIMIENTOS.md
  .env                       → credenciales de MySQL + SECRET_KEY del JWT (gitignored, nunca en el repo)
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

## Base de datos (MySQL)

Motor: MySQL, elegido en vez de SQLite porque el proyecto requiere soportar múltiples usuarios desde ya (D-020 en `PROYECTO.md`). Corre localmente como proceso manual (no como servicio de Windows — ver `CLAUDE.md` para el comando de arranque). Base de datos `motorguardian`, usuario dedicado `motorguardian_app` (no root), credenciales en `.env`.

**Principio de diseño clave:** la base de datos no guarda muestras crudas de sensores fila por fila (eso desbordaría cualquier motor relacional — el CSV sintético de prueba pesa 157 MB). Guarda metadata de equipos/sensores y resultados ya calculados; los datos crudos siguen viviendo en archivos (local o S3), referenciados por puntero.

Tablas (`basedatos/modelos.py`):

| Tabla | Responsabilidad |
|---|---|
| `tipo_equipo` | Catálogo abierto de tipos de equipo (motor monofásico, bomba centrífuga, ...) — agregar un tipo nuevo es una fila, no un cambio de esquema. |
| `planta` | Ubicaciones/plantas, para cuando haya más de una. |
| `equipo` | El activo físico. Campo `atributos` (JSON) para datos específicos por tipo (potencia_kw, caudal_m3h, etc.), en vez de columnas fijas para cada posible atributo. |
| `tipo_sensor` | Catálogo abierto de tipos de sensor (acelerómetro triaxial, temperatura, ...). |
| `sensor` | Sensor instalado en un equipo. Campo `configuracion` (JSON) para detalles específicos (ejes, unidad de medida). |
| `medicion` | Una sesión de captura de datos crudos: apunta a `ruta_archivo_local` / `clave_s3`, no contiene las muestras. |
| `resultado_analisis` | Resultado ya calculado sobre una medición (FFT, curtosis, clasificación de falla, score de autoencoder futuro), en JSON. |
| `usuario` | Cuentas de usuario del sistema. Administrable desde Configuración → Usuarios. |
| `modelo` | Catálogo de modelos de aprendizaje (nombre, tipo, versión, estado, descripción) — solo metadata, no entrena ni ejecuta inferencia (D-027). Administrable desde Configuración → Modelos de Aprendizaje. |

Estado actual: el esquema y las tablas existen y están probadas, pero **la API todavía no las usa** para equipos/sensores — no hay endpoints `/api/equipos` ni un módulo web de ingreso. La tabla `usuario` sí está en uso (ver Autenticación). Ver "Próximo paso sugerido" en `PROYECTO.md`.

---

## Autenticación

Flujo: React (`Login.jsx`) → `POST /api/auth/login` (email + password) → FastAPI consulta `usuario` en MySQL → `seguridad/auth.py` verifica el hash bcrypt → si es válido, se firma un JWT (`SECRET_KEY` en `.env`, expira en 8 horas) → el frontend guarda `{access_token, usuario}` en `localStorage` y lo mantiene entre recargas.

Estado actual: el login es real (contra la base de datos, contraseña hasheada, nunca en texto plano). El token protege el **acceso a la interfaz** (sin sesión guardada, `App.jsx` siempre muestra `Login`), pero los endpoints existentes (`/api/datos`, `/api/fft`, `/api/estadisticos`) todavía no exigen ni validan ese token — quedó anotado como pendiente en `PROYECTO.md`.

Usuario de prueba: `admin@motorguardian.io` / `mg2024` (creado con `herramientas/crear_usuario_demo.py`).

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
- Dos fuentes de datos de equipos separadas y no conectadas entre sí: `equiposDemo.js` (dummy, alimenta el sidebar/Resumen General/detalle) y la base de datos MySQL real (alimenta Configuración → Equipos). Un equipo creado en Configuración no aparece en el resto de la app.
- Cada request de `/api/datos`/`/api/fft`/`/api/estadisticos` sigue releyendo el CSV desde disco; no hay persistencia de resultados procesados todavía (la tabla `resultado_analisis` existe pero no se usa).
- MySQL no arranca solo con el sistema (no es un servicio de Windows) — hay que iniciarlo manualmente cada sesión.
