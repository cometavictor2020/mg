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

## 2026-09-01 (continuación 2) — Panel de administración (Configuración)

- Continuidad entre sesiones verificada en la práctica: se abrió una sesión nueva, se leyó `CLAUDE.md` + `PROYECTO.md`, se confirmó el estado (git limpio, los 3 commits pendientes ya estaban hechos) sin necesidad de repetir contexto.
- Se agregó la tabla `modelo` (catálogo de modelos de aprendizaje, solo metadata — D-027) y el helper `basedatos/utilidades.py::obtener_o_crear` para los catálogos abiertos.
- Se construyó `backend/api/administracion/` con CRUD completo (`GET`/`POST`/`PUT`/`DELETE`) para usuarios, equipos, sensores y modelos de aprendizaje, montados en `main.py` vía `APIRouter`.
- Se construyó `frontend/src/pages/Configuracion.jsx`, con 4 pestañas (mismo patrón visual que el resto de la app), formularios y tablas para cada entidad. El botón "Configuración" del sidebar (antes inerte) ahora navega ahí.
- Verificado en el navegador: las 4 secciones cargan, crear/editar/eliminar funciona en Equipos (probado end-to-end), y Usuarios/Sensores/Modelos muestran los datos de prueba creados por endpoint.
- Se encontraron y limpiaron procesos `uvicorn --reload` huérfanos de sesiones anteriores que quedaron ocupando el puerto 8000 (el proceso padre moría pero el hijo de `multiprocessing` seguía escuchando) — quedó como aprendizaje para `CONOCIMIENTOS.md`.
- Pendiente explícito: `equiposDemo.js` (sidebar/Resumen General/detalle) y los equipos reales de Configuración son dos fuentes de datos separadas — no están conectadas entre sí todavía.

## 2026-09-01 (continuación 3) — UX de Configuración, rediseño de Login y fuentes web

- Se corrigió el formulario "Agregar sensor" en Configuración: el campo "Tipo de sensor" se enviaba vacío en silencio porque el placeholder ("Acelerómetro triaxial") se confundía con un valor ya escrito y la única validación era el `required` nativo del navegador, fácil de pasar por alto. Se cambió el placeholder a "Ej: ..." y se agregó un mensaje de validación explícito en la app. Verificado en el navegador reproduciendo el caso original (equipo con id salteado por un borrado previo) y confirmando que el sensor queda asociado al equipo correcto.
- Se agregó confirmación obligatoria (diálogo `¿Estás seguro que deseas eliminar...?`, nombrando el registro puntual) antes de eliminar en las 4 secciones de Configuración — Usuarios, Equipos, Sensores, Modelos (D-029).
- Se rediseñó la pantalla de Login acercándola al mockup real, esta vez inspeccionado vía un link de Figma Make (no una imagen estática): se extrajo el SVG exacto del ícono (brújula/radar, antes un carácter `◎` genérico), el resplandor radial verde detrás del logo (`radial-gradient` de 500px, no un simple degradé del ícono), el peso real del título (`font-weight: 700`, no 600) y el radio de borde de inputs/botón (4px, no 8-10px). Los colores no se tocaron: ya coincidían exactamente desde D-025.
- A raíz de esa comparación se detectó que las fuentes web declaradas en `variables.css` (`Inter` para texto general, `Roboto Mono` para etiquetas técnicas) **nunca se cargaban** en ningún lado del proyecto — no había `<link>` a Google Fonts ni `@font-face`. El navegador usaba en silencio Segoe UI / Courier New en toda la app, no solo en Login. Se corrigió con un único `<link>` a Google Fonts en `frontend/index.html` (D-030); al aplicarse a nivel de `body`, el arreglo alcanza automáticamente a Resumen General, el Analizador de Vibraciones y Configuración sin tocar sus hojas de estilo.
- Verificado en el navegador: `document.fonts` confirma `Inter` y `Roboto Mono` cargadas y en uso; sin errores de consola; capturas de Login, Resumen General y Configuración revisadas visualmente.

## 2026-09-01 (continuación 4) — Sidebar/Resumen General/Analizador conectados a equipos reales

- Se resolvió la deuda técnica de las "dos fuentes de datos" de equipos: se creó `frontend/src/hooks/useEquiposReales.js`, que trae los equipos desde `/api/equipos` (MySQL) y los adapta al formato que ya esperaban `Sidebar.jsx`, `ResumenGeneral.jsx` y `AnalizadorVibraciones.jsx`. Se eliminó `frontend/src/data/equiposDemo.js` (sin referencias tras el cambio).
- Decisión del desarrollador ante la pregunta de qué hacer con las métricas que no existen por equipo en el esquema (vibración RMS, temperatura, probabilidad de falla, etc.): mostrarlas como "Sin datos" en vez de inventar valores — se prefirió la opción honesta sobre la vistosa para la demo.
- Se creó `herramientas/sembrar_equipos_demo.py` (mismo patrón que `crear_usuario_demo.py`, D-008/D-011): carga los 6 equipos de ejemplo en MySQL si no existen por nombre; no se ejecuta automáticamente desde la app, solo a pedido para dejar la base de datos poblada antes de una demo.
- Se agregaron estados de "Cargando…" y "No hay equipos registrados" en Resumen General y el Analizador, ya que ahora la lista de equipos depende de una llamada a la API (antes era un arreglo estático siempre disponible).
- Verificado en el navegador (pestaña nueva, sin caché de sesiones anteriores): Resumen General muestra los 9 equipos reales existentes en la base de datos, la navegación a detalle de equipo funciona con datos reales (nombre, tipo, planta), y no hay errores de consola.
- Efecto colateral menor detectado y dejado pendiente (no bloqueante): el script sembró el tipo de equipo "Motor eléctrico" (con tilde), que quedó como fila separada del "Motor electrico" (sin tilde) creado antes manualmente en pruebas — son dos entradas distintas en el catálogo abierto `tipo_equipo` por una diferencia de tildeo, sin impacto funcional.
- Pendiente explícito (ahora el próximo paso sugerido en `PROYECTO.md`): ligar mediciones reales por equipo — sacar el hardcodeo de `RUTA_ARCHIVO_DATOS` en `backend/api/main.py` y que `/api/datos`/`/api/fft`/`/api/estadisticos` lean el archivo real de la tabla `medicion` según el equipo/sensor seleccionado.

## 2026-09-01 (continuación 5) — Mediciones reales ligadas por equipo

- Se usó por primera vez la tabla `medicion` (existía en el esquema desde la fusión, sin ningún endpoint que la consultara). `/api/datos`, `/api/fft` y `/api/estadisticos` ahora exigen `equipo_id`, buscan la medición más reciente vía `Equipo → Sensor → Medición` y leen su `ruta_archivo_local` — se eliminaron los hardcodeos `RUTA_ARCHIVO_DATOS`/`FRECUENCIA_MUESTREO` de `backend/api/main.py` (la frecuencia de muestreo ahora viene de la medición registrada).
- Si el equipo no tiene medición, el backend responde 404 (`"Este equipo no tiene mediciones registradas"`) y el frontend lo muestra tal cual en vez de un gráfico vacío sin explicación — mismo criterio honesto ya elegido para las métricas del dashboard en la sesión anterior.
- Se creó `herramientas/registrar_medicion_real.py` (mismo patrón que `crear_usuario_demo.py`/`sembrar_equipos_demo.py`) para ligar el único CSV real existente (`datos/datos_vibracion_motor.csv`) al sensor de "Motor Bomba Principal", que ya existía de pruebas anteriores.
- Decisión del desarrollador ante la pregunta de alcance: por ahora basta con que "Motor Bomba Principal" muestre datos reales; los otros 8 equipos quedan mostrando "Sin mediciones registradas" hasta que tengan su propio archivo — no se buscó estirar el único CSV real a todos los equipos para simular más cobertura.
- `AnalizadorVibraciones.jsx` pasó de cargar los datos una sola vez al montar, a volver a pedirlos cada vez que cambia el equipo seleccionado (antes no era necesario porque siempre se leía el mismo CSV fijo).
- Verificado en el navegador: "Motor Bomba Principal" carga 1000 muestras reales en las 5 pestañas; "Compresor Aire N°2" (sin medición) muestra el mensaje de "sin mediciones" en las 5; sin errores no controlados en consola (los 404 esperados sí aparecen en la red, como es correcto).
- Pendiente explícito: no hay pantalla de administración de Mediciones (se registran a mano vía `herramientas/`); la tabla `resultado_analisis` sigue sin usarse; JWT sigue sin validarse en el backend (pasa a ser el próximo paso sugerido).

## 2026-09-02 — Validación de JWT en todo el backend

- Se agregó la dependencia `obtener_usuario_actual` en `seguridad/auth.py`: exige header `Authorization: Bearer <token>` válido, responde 401 si falta, es inválido o expiró. Sigue el mismo principio de D-012/D-024 (el endpoint solo declara `Depends(...)`, no contiene la lógica de verificación).
- Se aplicó a `/api/datos`, `/api/fft`, `/api/estadisticos` (uno por uno, en `backend/api/main.py`) y a los 4 routers de administración (`usuarios.py`, `equipos.py`, `sensores.py`, `modelos_ml.py`) a nivel de router — una sola línea `dependencies=[Depends(obtener_usuario_actual)]` en cada uno. `POST /api/auth/login` y `GET /` quedan públicos a propósito (D-031).
- En el frontend se centralizó el manejo de la sesión: `frontend/src/utils/sesion.js` (única fuente de verdad para leer/guardar/borrar la sesión en `localStorage`, antes duplicado implícitamente solo en `App.jsx`) y `frontend/src/utils/apiFetch.js` (wrapper de `fetch` que agrega el header `Authorization`). Se reemplazaron todos los `fetch` a endpoints protegidos (`useEquiposReales`, `AnalizadorVibraciones`, `Configuracion` — incluyendo las 4 funciones de eliminar) por `apiFetch`. El único `fetch` crudo que queda es el propio login, donde todavía no existe un token que enviar.
- Verificado en el navegador: `curl` sin token a `/api/equipos` devuelve 401; una sesión con token expirado (de una prueba del día anterior) también devolvía 401 — confirmando que la validación efectivamente bloquea, no solo que compila; con un login nuevo, Resumen General, el detalle de "Motor Bomba Principal" y Configuración → Usuarios cargan con normalidad.
- Con esto se cierra la deuda técnica de seguridad que venía pendiente desde la sesión de autenticación inicial (2026-09-01).
- Pendiente explícito (ahora el próximo paso sugerido en `PROYECTO.md`): definir el mecanismo de respaldo de la base de datos MySQL (D-022), que sigue sin resolverse.

## 2026-09-02 (continuación) — Base de conocimiento normativa (ISO)

- El desarrollador curó, fuera de esta sesión, una tabla de referencia normativa (`normativa_motorguardian.yaml`) a partir de varias normas ISO (20816, 13373, 17359, 13374, 13379, 13381) — la idea ya estaba anotada en "Ideas futuras" de `PROYECTO.md`. La trajo para revisión y ubicación en el repo.
- Revisión de contenido: estructura sólida (15 secciones, versionada, `pesos_evidencia` + `confianza_diagnostico` con score normalizado, 17 reglas de diagnóstico por evidencia ponderada, contrato de datos explícito para que un LLM solo explique — nunca invente — resultados). El propio archivo ya se autolimita correctamente: `requiere_revision_experto: true`, `uso_produccion_autorizado: false`, y prohíbe expresamente reproducir texto de las normas o que el LLM invente límites/RUL.
- Se marcó un punto de atención para el desarrollador (no se corrigió, es su archivo y su criterio): cita ediciones muy recientes de normas de nicho (ISO 13373-9:2026 edición 2, publicada "2026-08"; ISO 13379-1:2025; ISO 13381-1:2025) que no se pueden verificar contra las normas licenciadas reales desde esta sesión — confirmar esos números antes de que alimenten una decisión real de severidad.
- Se creó la carpeta `conocimiento/` (nueva, separada de `config/` por responsabilidad — D-032) y se copió el archivo ahí: `conocimiento/normativa_motorguardian.yaml`. Es un archivo de datos/referencia, no código: no se creó ningún motor de reglas que lo consuma (eso sigue siendo Fase 8 del roadmap, pendiente).
- No se tocó el "Próximo paso sugerido" (definir respaldo de MySQL, D-022) — este trabajo fue revisar y ubicar el archivo, no priorizar Fase 8.

## 2026-09-15 — Mecanismo de respaldo de la base de datos

- Continuidad entre sesiones verificada de nuevo: se creó la sesión "Motor Guardian 3" apuntando a la misma carpeta `mg/`; se intentó vaciar el contexto pero el desarrollador se arrepintió a tiempo (el vaciado programado se cancela solo si llega un mensaje antes de que termine el turno) y se siguió con el historial completo.
- Se definió D-022 (que llevaba varias sesiones pendiente): el respaldo de la base de datos es un volcado `mysqldump` manual, ejecutado con `herramientas/respaldar_basedatos.py` (mismo patrón que `crear_usuario_demo.py`/`sembrar_equipos_demo.py`/`registrar_medicion_real.py`). El volcado se guarda en `respaldos/`, carpeta nueva agregada a `.gitignore` — refuerza D-022 a nivel de herramienta, no solo de política.
- Detalle de seguridad: la contraseña de `motorguardian_app` se pasa al subproceso `mysqldump` vía la variable de entorno `MYSQL_PWD`, no como argumento de línea de comandos, para que no quede visible en el listado de procesos del sistema.
- Verificado: se levantó MySQL manualmente (no estaba corriendo), se ejecutó el script, y se confirmó que el volcado generado (`respaldos/motorguardian_20260915_163108.sql`, 11.8 KB) contiene sentencias `CREATE TABLE`/datos válidas. Se confirmó con `git check-ignore` que la carpeta `respaldos/` efectivamente queda fuera del control de versiones.
- Se agregó el comando a `CLAUDE.md` (sección Comandos), siguiendo el mismo formato que los demás scripts de `herramientas/`.
- Próximo paso sugerido actualizado: sin resolver todavía entre tests automatizados y la pantalla de administración de Mediciones — queda para que el desarrollador decida al retomar.
