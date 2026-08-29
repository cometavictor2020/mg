# PROYECTO.md — MotorGuardian

**Última actualización:** 2026-08-28
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

### Deuda técnica conocida (heredada de la fusión, pendiente de corregir)

- `backend/api/main.py` tiene hardcodeada la ruta del CSV y la frecuencia de muestreo.
- `calcular_fft` y `calcular_estadisticos` exigen explícitamente columnas `vibracion_x/y/z`: no son genéricos para otros tipos de sensor.
- El listado de equipos del sidebar (`equiposDemo.js`) es data dummy, **no conectado** al backend: seleccionar un equipo distinto no cambia los datos mostrados. Solo hay un equipo real con datos de verdad.
- No hay base de datos ni persistencia de resultados procesados; cada request relee el CSV desde disco.
- No hay tests automatizados.

### Próximo paso sugerido

Definir con el desarrollador cuál de los ítems de deuda técnica o del roadmap se aborda primero.

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
| 4 | Dashboard (React + Recharts, 5 pestañas de análisis) | Completado (con equipos dummy salvo uno real) |
| 5 | Subida a AWS S3 | Completado en modo manual; automatización pendiente |
| 6 | Inteligencia Artificial: clasificación de fallas por picos FFT, switch de IA, autoencoders, LLM + normas ISO | Pendiente |
| 7 | Refactor a clases (modelo de dominio Equipo/Sensor/Diagnóstico) | Pendiente — evaluar al agregar el segundo tipo de equipo |

---

## Ideas futuras

- Clasificación automática del tipo de falla a partir de los picos de la FFT (1x RPM → desbalanceo, 2x RPM → desalineación, bandas de alta frecuencia → rodamientos), apoyada en las normas ISO 13379/13381.
- Switch manual para consultar un LLM como "segunda opinión" de diagnóstico — nunca como reemplazo del motor de reglas determinístico.
- Módulo de autoencoders: definir qué se persiste (vectores de características, modelo entrenado, scores de error de reconstrucción) y dónde.
- Integración con un LLM usando una tabla de referencia propia (JSON/YAML) curada a partir de las normas ISO 20816, 13373, 17359, 13374, 13379 y 13381 — sin reproducir el texto de las normas.
- Conectar de verdad el selector de equipos del sidebar a datos reales por equipo (hoy es solo visual).
- Sacar los hardcodeos de `main.py` (ruta del CSV, frecuencia de muestreo) hacia configuración.

---
