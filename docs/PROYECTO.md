# PROYECTO.md — MotorGuardian

**Última actualización:** 2026-09-15 (v9)
**Este es el único documento de lectura obligatoria al inicio de cada sesión.**
Complementarlo con un vistazo a las últimas entradas de `BITACORA.md`. `ARQUITECTURA.md` y `CONOCIMIENTOS.md` se consultan solo cuando se necesitan (no son lectura obligatoria).

---

## Objetivo del proyecto

MotorGuardian busca predecir fallas en equipos industriales mediante mantenimiento predictivo. La primera versión se enfoca en **motores monofásicos**, usando sensores de **vibración triaxial** y **temperatura**.

La arquitectura debe mantenerse abierta y escalable para incorporar, a futuro:
- otros tipos de equipo: motores trifásicos, aerogeneradores, ventiladores, bombas centrífugas, etc.;
- otros tipos de sensor: termografía, corriente eléctrica, análisis de fluidos, ultrasonido, etc.

El núcleo (Core) del sistema se mantiene en **Python**.

---

## Estado actual

### Completado

- Proyecto fusionado en una sola carpeta (`mg/`), unificando lo que antes eran dos proyectos separados (`analizador_vibraciones` y `motorguardian`).
- Backend FastAPI funcionando, con 3 endpoints: `/api/datos` (señal en el tiempo), `/api/fft` (espectro FFT), `/api/estadisticos` (curtosis, factor de cresta, skewness).
- Frontend React + Vite funcionando, con el despliegue visual heredado de `analizador_vibraciones` (sidebar de equipos, pestañas de análisis) y 3 pestañas nuevas agregadas a la derecha de "Vibración en el tiempo" y "Espectro FFT".
- Módulo de almacenamiento en AWS S3 (`almacenamiento_s3.py`) funcional, con la subida real controlada manualmente (línea de ejecución comentada en `herramientas/subir_archivo_s3.py`).
- Diagrama de arquitectura generado (`docs/arquitectura_servidores.png`), con su script reproducible (`herramientas/generar_diagrama_arquitectura.py`).
- Documentación consolidada de 11+ archivos redundantes a 4 documentos.
- Repositorio respaldado en GitHub, privado: `github.com/cometavictor2020/mg` (historial local con fechas reales preservadas).
- Base de datos **MySQL** instalada localmente (`motorguardian`, usuario dedicado `motorguardian_app`, credenciales en `.env` — nunca en Git), con las 8 tablas del modelo de dominio creadas (`tipo_equipo`, `planta`, `equipo`, `tipo_sensor`, `sensor`, `medicion`, `resultado_analisis`, `usuario`) vía `basedatos/modelos.py` (SQLAlchemy) y `herramientas/crear_tablas_basedatos.py`. MySQL corre como proceso manual (no como servicio de Windows — no había permisos de administrador para instalarlo como tal), se levanta con el comando en `CLAUDE.md`.
- **Autenticación real** con la base de datos: tabla `usuario` con `password_hash` (bcrypt), módulo `seguridad/auth.py` (hash + JWT), endpoint `POST /api/auth/login`. Usuario demo sembrado con `herramientas/crear_usuario_demo.py` (`admin@motorguardian.io` / `mg2024`).
- **Pantalla de Login** (`frontend/src/pages/Login.jsx`) y **Resumen General** (`frontend/src/pages/ResumenGeneral.jsx`), reproduciendo al 100% los colores y el formato de los mockups `mg-intro.png`/`resumen-general.png` (colores extraídos con precisión de píxel vía Python/Pillow, no a ojo). `App.jsx` actúa como enrutador simple entre Login → Resumen General → detalle de equipo, con sesión persistida en `localStorage`.
- Sidebar extraído a un componente compartido (`frontend/src/components/Sidebar.jsx`) reutilizado por `ResumenGeneral` y `AnalizadorVibraciones`, evitando duplicar ese bloque de JSX.
- **Pantalla de Configuración** (`frontend/src/pages/Configuracion.jsx`), con 4 secciones (Usuarios, Equipos, Sensores, Modelos de Aprendizaje), cada una con CRUD completo (crear/editar/eliminar) contra la base de datos MySQL real. Endpoints en `backend/api/administracion/` (`usuarios.py`, `equipos.py`, `sensores.py`, `modelos_ml.py`). Tabla nueva `modelo` agregada al esquema — solo registra metadata (nombre, tipo, versión, estado, descripción), no entrena ni ejecuta inferencia (ver D-019). Los catálogos abiertos (`tipo_equipo`, `tipo_sensor`, `planta`) se completan automáticamente al crear un equipo/sensor con un tipo nuevo (`basedatos/utilidades.py::obtener_o_crear`), sin pantallas de administración separadas para esos catálogos.
- Configuración endurecida: el formulario de "Agregar sensor" validaba el campo "Tipo de sensor" solo con `required` de HTML5, y el placeholder ("Acelerómetro triaxial") se confundía con un valor ya escrito, causando envíos fallidos silenciosos. Ahora el placeholder deja claro que es un ejemplo ("Ej: ...") y hay una validación explícita en la app antes de enviar. Además, las 4 secciones de Configuración piden confirmación (diálogo `¿Estás seguro que deseas eliminar...?`, con el nombre del registro) antes de eliminar cualquier usuario/equipo/sensor/modelo — ver D-029.
- **Pantalla de Login** rediseñada para acercarse al mockup real (esta vez visto vía un link de Figma Make), corrigiendo: ícono SVG tipo brújula/radar (antes un carácter `◎` genérico), resplandor radial verde detrás del logo, título en negrita real y radios de borde de 4px (antes 8-10px). Los colores ya coincidían exactamente desde D-025, no se tocaron.
- Se detectó y corrigió que las fuentes web declaradas en `variables.css` (`Inter`, `Roboto Mono`) nunca se cargaban — no había `<link>` a Google Fonts ni `@font-face` en ningún lado del proyecto, así que toda la app (no solo Login) usaba en silencio la fuente de reemplazo del sistema (Segoe UI / Courier New). Corregido con un único `<link>` a Google Fonts en `frontend/index.html` — ver D-030.
- **Sidebar, Resumen General y Analizador de Vibraciones conectados a los equipos reales**: se eliminó `equiposDemo.js` (data de ejemplo hardcodeada) y se creó el hook compartido `frontend/src/hooks/useEquiposReales.js`, que trae los equipos desde `/api/equipos` y los adapta al formato que ya consumían los componentes. Las métricas que todavía no existen por equipo en el esquema (vibración RMS, temperatura, probabilidad de falla, etc.) se muestran explícitamente como "Sin datos"/"—", en vez de inventar valores — decisión explícita del desarrollador. Se agregó también `herramientas/sembrar_equipos_demo.py` (mismo patrón que `crear_usuario_demo.py`): carga los 6 equipos de ejemplo en MySQL si no existen por nombre, para poder "recargarlos" antes de una demo sin tocar el flujo principal (D-008/D-011).
- **Mediciones reales ligadas por equipo**: `/api/datos`, `/api/fft` y `/api/estadisticos` ahora reciben `equipo_id`, buscan la medición más reciente vía `Equipo → Sensor → Medición` y leen su archivo real — se eliminaron los hardcodeos `RUTA_ARCHIVO_DATOS`/`FRECUENCIA_MUESTREO` de `backend/api/main.py` (la frecuencia de muestreo ahora sale de la medición). Si el equipo no tiene medición registrada, el backend responde 404 y el frontend muestra "Este equipo no tiene mediciones registradas" en vez de datos falsos — mismo criterio honesto que las métricas del punto anterior. Se agregó `herramientas/registrar_medicion_real.py` para ligar el único CSV real existente al sensor de "Motor Bomba Principal" (por ahora el único equipo con datos reales; el resto necesitaría su propio archivo de mediciones, que todavía no existe).
- **Validación de JWT en todo el backend**: nueva dependencia `obtener_usuario_actual` en `seguridad/auth.py` (exige `Authorization: Bearer <token>` válido; 401 si falta/expiró/es inválido — mismo principio D-012/D-024, el endpoint solo declara `Depends(...)`). Aplicada a `/api/datos`, `/api/fft`, `/api/estadisticos` y a los 4 routers de administración (a nivel de router, una línea cada uno). `POST /api/auth/login` y `GET /` quedan públicos a propósito. En el frontend se centralizó el acceso a la sesión en `frontend/src/utils/sesion.js` y se creó `frontend/src/utils/apiFetch.js` (wrapper de `fetch` que agrega el token) — reemplaza todos los `fetch` a endpoints protegidos; el único `fetch` crudo que queda es el propio login, donde todavía no hay token — ver D-031.
- **Base de conocimiento normativa (ISO) curada por el desarrollador**: `conocimiento/normativa_motorguardian.yaml` — tabla de referencia con criterios de severidad (ISO 20816-3), reglas de diagnóstico por evidencia ponderada (17 fallas: desbalanceo, desalineación, rodamientos, cavitación, etc.), motor de confianza normalizado y contrato de datos para un futuro LLM explicador. No reproduce texto de las normas ISO (solo datos curados), y el propio archivo se marca `requiere_revision_experto: true` / `uso_produccion_autorizado: false` — ver D-032. Es la materialización de la idea que ya estaba anotada en "Ideas futuras"; el motor de reglas que la consuma sigue siendo Fase 8 del roadmap ("Pendiente") — este archivo todavía no está conectado a ningún código.
- **Mecanismo de respaldo de la base de datos definido**: `herramientas/respaldar_basedatos.py` (mismo patrón que los demás scripts de `herramientas/`) ejecuta `mysqldump` y guarda un volcado con fecha/hora en `respaldos/` — carpeta nueva, agregada a `.gitignore`, así D-022 queda reforzada por la herramienta misma y no solo por la política. La contraseña se pasa al subproceso vía variable de entorno (`MYSQL_PWD`), no como argumento de línea de comandos, para que no quede visible en el listado de procesos. Es un respaldo manual (lo ejecuta el desarrollador cuando quiere); no hay todavía una tarea programada — ver D-033.

### Deuda técnica conocida (heredada de la fusión, pendiente de corregir)

- `calcular_fft` y `calcular_estadisticos` exigen explícitamente columnas `vibracion_x/y/z`: no son genéricos para otros tipos de sensor.
- Solo "Motor Bomba Principal" tiene una medición real registrada (`herramientas/registrar_medicion_real.py`); los demás equipos no tienen archivo de mediciones propio, así que el dashboard les muestra "Sin mediciones registradas". No hay todavía una pantalla de administración para registrar mediciones — se hace a mano vía `herramientas/`.
- No hay tests automatizados.
- El respaldo de la base de datos es manual (`herramientas/respaldar_basedatos.py`, hay que acordarse de ejecutarlo); no hay una tarea programada que lo automatice ni una política de cuántas copias conservar.

### Próximo paso sugerido

Dos candidatos, sin decidir todavía: **tests automatizados** (hoy no hay ninguno, y el proyecto ya tiene bastante superficie — auth, CRUD, mediciones — para que se note la ausencia) o la **pantalla de administración de Mediciones** (hoy solo "Motor Bomba Principal" tiene datos reales, registrados a mano vía script).

---

## Decisiones vigentes

- **D-001** — Se utilizará AWS como plataforma cloud. _Motivo: escalable, compatible con servicios industriales, fácil crecimiento hacia producción._
- **D-002** — Gestión de credenciales AWS: en desarrollo se usa el perfil local (`aws configure`); en producción se migrará a IAM Roles. Nunca credenciales en el código fuente ni en Git.
- **D-003** — El proyecto comienza con programación basada en funciones, organizada en módulos independientes, preparada para migrar a POO cuando el crecimiento lo justifique.
- **D-004** — Se usa PyYAML para leer archivos de configuración.
- **D-005** — Cada proyecto usa su propio entorno virtual (`venv`), aislado del sistema operativo.
- **D-006** — El código Python sigue PEP 8.
- **D-007** — El Core de procesamiento es independiente de la interfaz de usuario; la tecnología de interfaz se decide y evoluciona por separado.
- **D-008** — `principal.py` (o el punto de entrada equivalente) representa siempre el flujo principal; las pruebas puntuales van en `herramientas/`, nunca mezcladas con el flujo principal.
- **D-009** — Separación estricta entre código de producto (`backend/`, `almacenamiento/`), herramientas auxiliares (`herramientas/`) y pruebas automatizadas (`tests/`).
- **D-010** — Arquitectura modular desde el inicio: se comienza por vibraciones, pero preparada para incorporar termografía, análisis de fluidos u otros módulos futuros, sin acoplarse exclusivamente a vibraciones ni a motores.
- **D-011** — Rutas de archivos, plantas, motores, fechas o sensores nunca se hardcodean en el flujo principal; para validar con datos concretos se usan scripts en `herramientas/`. _(Pendiente de aplicar completamente — ver Deuda técnica.)_
- **D-012** — El backend separa siempre `api` (endpoints) de `procesamiento` (cálculo); ningún endpoint contiene lógica de procesamiento ni lee CSV directamente.
- **D-013** — Se fusionan `analizador_vibraciones` y `motorguardian` en un solo proyecto (`mg/`), para evitar mantener dos repositorios en paralelo resolviendo mitades del mismo problema.
- **D-014** — El acceso real a AWS S3 queda comentado en `herramientas/subir_archivo_s3.py` (control manual); el módulo `almacenamiento_s3.py` permanece completamente funcional.
- **D-015** — El despliegue visual heredado de `analizador_vibraciones` se mantiene tal cual como base del frontend fusionado; la parte hardcodeada/monolítica del backend se corrige en una etapa posterior.
- **D-016** — Se agrega el endpoint `/api/estadisticos` (curtosis, factor de cresta, skewness) y sus 3 pestañas correspondientes en el frontend.
- **D-017** — La documentación del proyecto se consolida en 4 documentos (`PROYECTO.md`, `ARQUITECTURA.md`, `BITACORA.md`, `CONOCIMIENTOS.md`); solo `PROYECTO.md` es lectura obligatoria al inicio de cada sesión.
- **D-018** — El repositorio se respalda en GitHub como **privado**; el acceso se otorga agregando colaboradores puntuales, nunca haciéndolo público.
- **D-019** — Los autoencoders quedan explícitamente despriorizados al final del roadmap: son el ítem que más tiempo de desarrollo consumiría, y no es la prioridad actual.
- **D-020** — Se usa **MySQL** en vez de SQLite desde el inicio, porque el proyecto requiere soportar múltiples usuarios (motor cliente-servidor) desde ya, no solo un único proceso local. En desarrollo corre localmente (igual que AWS: perfil/infraestructura local primero, producción después).
- **D-021** — El esquema de base de datos usa catálogos abiertos (`tipo_equipo`, `tipo_sensor`) en vez de listas fijas, y un campo `atributos`/`configuracion` en JSON para datos específicos de cada tipo de equipo/sensor — para no acoplar el esquema a los tipos de equipo conocidos hoy (ver Objetivo del proyecto).
- **D-022** — La base de datos MySQL **no se respalda vía Git/GitHub** bajo ninguna circunstancia (ni el archivo de datos ni un dump). El mecanismo de respaldo se definirá en una sesión futura.
- **D-023** — MySQL corre como proceso manual iniciado por comando (no como servicio de Windows), porque instalarlo como servicio requiere permisos de administrador no disponibles en el entorno de desarrollo actual.
- **D-024** — Autenticación con `bcrypt` (hash de contraseñas) + `PyJWT` (tokens de sesión), en un módulo `seguridad/` independiente de `backend/api/` — el endpoint solo orquesta, no contiene lógica de hashing/tokens (mismo principio que D-012).
- **D-025** — Las pantallas de Login y Resumen General deben replicar exactamente los colores de los mockups entregados por el desarrollador; los colores se extrajeron con Python/Pillow directamente de los archivos PNG (valores de píxel exactos), no a partir de una estimación visual.
- **D-026** — El sidebar se extrajo a un componente compartido (`components/Sidebar.jsx`) al empezar a reutilizarse en una segunda pantalla, siguiendo P-001 (una responsabilidad por módulo) sin alterar su apariencia original.
- **D-027** — La sección "Modelos de Aprendizaje" de Configuración solo administra metadata (catálogo), sin entrenar ni ejecutar modelos reales — para no contradecir D-019 (autoencoders despriorizados al final del roadmap).
- **D-028** — Los tipos de equipo, tipos de sensor y plantas no tienen pantalla de administración propia: se registran automáticamente la primera vez que se usan al crear un equipo/sensor (catálogos abiertos, D-021), vía `basedatos/utilidades.py::obtener_o_crear`.
- **D-029** — Toda eliminación en pantallas de administración (Configuración) requiere confirmación explícita del usuario vía diálogo, nombrando el registro puntual a eliminar — para prevenir borrados accidentales. Aplica a las 4 secciones actuales (Usuarios, Equipos, Sensores, Modelos) y a las que se agreguen en el futuro.
- **D-030** — Toda fuente web declarada en `variables.css` (`--fuente-principal`, `--fuente-mono`) debe cargarse explícitamente (Google Fonts o self-hosted) en `frontend/index.html`; declararla solo en el `font-family` no basta — el navegador cae en silencio a una fuente de reemplazo distinta sin que se note a simple vista.
- **D-031** — Todos los endpoints que exponen datos o administración exigen JWT válido vía `Depends(obtener_usuario_actual)` (`seguridad/auth.py`); las únicas excepciones a propósito son `POST /api/auth/login` (todavía no hay token en ese punto) y `GET /` (health check). El frontend centraliza el envío del token en `frontend/src/utils/apiFetch.js`.
- **D-032** — Las bases de conocimiento de dominio (tablas curadas a partir de normas, reglas de diagnóstico, etc.) viven en `conocimiento/`, separadas de `config/` (que es config de infraestructura, no conocimiento de dominio) — se cargan vía PyYAML (D-004). Ningún archivo de `conocimiento/` se usa para diagnóstico real hasta que el motor de reglas que lo consuma (Fase 8) esté construido y el archivo haya sido revisado por un experto — el propio archivo debe declarar explícitamente si está o no autorizado para producción.
- **D-033** — El respaldo de la base de datos se hace con `mysqldump` vía `herramientas/respaldar_basedatos.py`, guardando el volcado en `respaldos/` (carpeta local, excluida de Git — refuerza D-022). Es manual por ahora, no una tarea programada; la contraseña se pasa al subproceso por variable de entorno, nunca como argumento de línea de comandos.

---

## Principios de desarrollo

- **P-001** — Cada módulo tiene una única responsabilidad. _Favorece reutilización, reduce acoplamiento, facilita pruebas._
- **P-002** — Antes de crear un módulo nuevo: ¿cuál es su única responsabilidad?, ¿quién lo usará?, ¿qué funciones públicas ofrece?
- **P-003** — Cada commit representa una unidad lógica de trabajo.
- **P-004** — Código claro antes que código complejo: se lee muchas más veces de las que se escribe.
- **P-005** — Antes de incorporar tecnología nueva, priorizar entender los fundamentos.
- **P-006** — Toda decisión importante queda documentada (ver Decisiones vigentes).
- **P-007** — Cada jornada empieza revisando `PROYECTO.md` y el último commit.
- **P-008** — El objetivo incluye entender el porqué de cada decisión técnica, no solo que el software funcione.
- **P-009** — Desarrollo incremental: base sólida antes de sumar funcionalidades, validando cada etapa con Git.
- **P-010** — Preferir herramientas recomendadas por la comunidad cuando no haya razón técnica para lo contrario (PEP 8, `pathlib`, `yaml.safe_load()`, entornos virtuales).
- **P-011** — Las explicaciones priorizan la comprensión antes que la velocidad de desarrollo.
- **P-012** — Las herramientas auxiliares se nombran según su función (`subir_archivo_s3.py`), nunca según el contexto temporal en que se crearon (`prueba1.py`).

---

## Contrato de colaboración con la IA

**Roles simultáneos:**
1. **Arquitecto de software** — cuida arquitectura, modularidad, escalabilidad, separación de responsabilidades.
2. **Senior developer / mentor** — prioriza claridad, simplicidad y aprendizaje progresivo por sobre soluciones "elegantes" pero complejas.
3. **Scrum master** — protege el objetivo de la sesión/sprint actual; evita desvíos de arquitectura no solicitados.
4. **Guardián de la coherencia** — antes de proponer un cambio, verifica que no contradiga las Decisiones ni los Principios vigentes; si detecta una contradicción, la señala antes de escribir código.
5. **Guardián de la documentación** — cuando detecta una decisión, riesgo o avance relevante no documentado, lo indica explícitamente y propone en qué sección de `PROYECTO.md` o `BITACORA.md` debe registrarse.

**Metodología ante cambios en archivos existentes:** revisar el archivo actual → confirmar que el cambio respeta Decisiones/Principios vigentes → proponer el cambio mínimo necesario → explicar antes de implementar → implementar → probar → sugerir el commit.

**Checklist de inicio de sesión:** leer `PROYECTO.md` completo + últimas entradas de `BITACORA.md` → presentar estado actual, riesgos abiertos y próximo paso.

**Checklist de cierre de sesión:** actualizar `PROYECTO.md` si cambiaron el estado, las decisiones o el roadmap → agregar una entrada en `BITACORA.md` → sugerir mensaje de commit.

**Fuente de verdad**, en caso de conflicto: 1) código fuente, 2) esta documentación, 3) historial de Git, 4) memoria de la IA. La IA nunca asume que recuerda una decisión si contradice la documentación vigente.

---

## Riesgos abiertos

- **R-002 — Formato definitivo de datos de vibración desde hardware real.** Hoy se trabaja con CSV sintético (`vibracion_x/y/z`, `temperatura`, `timestamp`); el formato que entregará hardware real (sensores físicos) aún no está definido y podría variar en cantidad/nombre de columnas. _Mitigación: no acoplar el Core a un formato específico; mantener separada la carga/almacenamiento del procesamiento; preparar adaptadores de lectura cuando se conozca el formato real._

---

## Roadmap

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Bucket S3, Git, estructura del proyecto | Completado |
| 2 | Ingesta de datos (CSV sintético, lectura con pandas) | Completado (sintético); real pendiente |
| 3 | Procesamiento de señal: FFT, curtosis, factor de cresta, skewness | Completado |
| 4 | Dashboard (React + Recharts, 5 pestañas de análisis) | Completado (equipos y mediciones reales vía `/api/equipos` + `medicion`; solo 1 de 9 equipos tiene medición registrada) |
| 5 | Subida a AWS S3 | Completado en modo manual; automatización pendiente |
| 6 | Base de datos MySQL: esquema de Equipo/Sensor/Medición/ResultadoAnalisis | Completado (esquema, tablas y conexión real con la API vía `medicion`); `resultado_analisis` sigue sin usarse |
| 6.5 | Autenticación (login real contra la BD) + pantallas de Login y Resumen General | Completado (login funcional, JWT validado en todos los endpoints protegidos) |
| 7 | Módulo web de administración: Configuración → Usuarios/Equipos/Sensores/Modelos de Aprendizaje, CRUD completo contra MySQL, conectado al dashboard (sidebar/Resumen General/detalle) | Completado |
| 8 | Inteligencia Artificial: clasificación de fallas por picos FFT, switch de IA, LLM + normas ISO | Pendiente — la base de conocimiento curada ya existe (`conocimiento/normativa_motorguardian.yaml`, D-032); falta el motor de reglas que la consuma |
| 9 | Autoencoders | Pendiente — despriorizado al final del roadmap (D-019), es lo que más tiempo de desarrollo consumiría |
| 10 | Refactor a clases (modelo de dominio Equipo/Sensor/Diagnóstico) | Parcialmente cubierto por los modelos SQLAlchemy de `basedatos/modelos.py`, que ya son clases — evaluar si falta algo al conectar la API |

---

## Ideas futuras

- Clasificación automática del tipo de falla a partir de los picos de la FFT (1x RPM → desbalanceo, 2x RPM → desalineación, bandas de alta frecuencia → rodamientos), apoyada en las normas ISO 13379/13381.
- Switch manual para consultar un LLM como "segunda opinión" de diagnóstico — nunca como reemplazo del motor de reglas determinístico.
- Módulo de autoencoders: definir qué se persiste (vectores de características, modelo entrenado, scores de error de reconstrucción) y dónde.
- Construir el motor de reglas que consuma `conocimiento/normativa_motorguardian.yaml` (Fase 8): clasificación de severidad ISO 20816-3, sistema de evidencias ponderadas para 17 hipótesis de falla, score de confianza, y el contrato de datos estructurado para que un LLM explique el resultado (sin inventar umbrales ni diagnósticos). Antes de usarlo en un diagnóstico real, confirmar con el desarrollador los números de edición de las normas más recientes citadas (ISO 13373-9:2026, 13379-1:2025, 13381-1:2025) contra su copia licenciada.
- Pantalla de administración de Mediciones (hoy se registran a mano vía `herramientas/registrar_medicion_real.py`), para poder ligar mediciones reales a más equipos sin escribir un script por cada una.
- Usar la tabla `resultado_analisis` para guardar los cálculos de FFT/estadísticos ya hechos, en vez de recalcularlos en cada request.
- Tests automatizados (hoy no hay ninguno) — ver Próximo paso sugerido.
- Automatizar el respaldo de la base de datos (hoy es manual, D-033) con una tarea programada y una política de cuántas copias conservar.

---
