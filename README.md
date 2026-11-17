# MotorGuardian

Sistema de código abierto para el **análisis de vibraciones** y el **apoyo a las decisiones de mantenimiento** de motores eléctricos y maquinaria rotatoria. A partir de archivos de medición propios o de terceros, entrega diagnósticos **trazables**: cada hipótesis de falla indica la evidencia que la respalda, su nivel de confianza y una recomendación.

> *English summary:* MotorGuardian is an open-source, rule-based vibration analysis tool for rotating machinery (FFT, envelope/Hilbert analysis, optional PSO band selection, ISO 20816-3 severity, bearing/unbalance/misalignment diagnosis with traceable evidence, PDF reports and Telegram/e-mail alerts). It is a laboratory-validated prototype, not a replacement for a vibration analyst. MIT licensed. Documentation is in Spanish.

Desarrollado como trabajo de título (Técnico Universitario en Mantención de Equipos Industriales, Universidad de Santiago de Chile). Las decisiones de diseño, los fundamentos y la validación completa están en la memoria del trabajo.

## Aviso importante

MotorGuardian es un **prototipo validado en laboratorio**. No se ha probado en una planta industrial y **no sustituye el juicio de un especialista en vibraciones**. Sus resultados son hipótesis con evidencia, no veredictos. En particular:

- El **nivel de confianza** es un puntaje de evidencia; **no es una probabilidad de falla** ni está calibrado contra frecuencias observadas de fallas.
- Los criterios normativos (ISO 20816-3, ISO 13373-1) se usan como referencia; el texto de las normas no se incluye y los criterios curados están **pendientes de revisión experta**.
- Se entrega **sin garantía** (ver [LICENSE](LICENSE)). No lo uses como única base para decisiones de seguridad.

## Qué hace

- **Carga y validación de mediciones** (CSV, y .mat mediante un importador con plantillas reutilizables). Un archivo mal formado se rechaza antes de guardarse.
- **Procesamiento de señales:** espectro de frecuencias (FFT), espectro de envolvente (transformada de Hilbert) y selección de la banda de filtrado por optimización por enjambre de partículas (PSO), opcional y bajo demanda.
- **Motor de diagnóstico basado en reglas explícitas:** desbalanceo, desalineación paralela y angular, y fallas de rodamiento (pista exterior, pista interior, elemento rodante y jaula), con evidencia ponderada y nivel de confianza.
- **Severidad según ISO 20816-3**, **calidad de la medición según ISO 13373-1** y **línea base** por sensor (una o varias mediciones sanas) para detectar cambios.
- **Reportes de diagnóstico en PDF**, con una página opcional de resumen redactado por un modelo de lenguaje (requiere una clave de OpenAI; la IA no cambia el diagnóstico ni las cifras).
- **Alertas** por correo electrónico y Telegram a los destinatarios que administre el usuario.
- **Pantalla Laboratorio** para analizar un archivo .mat externo sin guardarlo en la base de datos.
- Autenticación con usuarios y roles (JWT).

Los criterios del diagnóstico **no están escritos en el código**: viven en archivos YAML (`conocimiento/normativa_motorguardian.yaml` para lo que tiene respaldo en una norma y `conocimiento/criterios_proyecto.yaml` para los criterios del proyecto sin respaldo normativo), de modo que pueden revisarse y modificarse sin tocar los módulos de cálculo.

## Resultados de validación (resumen)

Se validó con señales sintéticas y con conjuntos públicos de laboratorio (CWRU, MFPT, Universidad de Ottawa, MAFAULDA y SRO). Los detalles, las condiciones y las limitaciones están en la memoria y en la carpeta `validacion/`. En resumen:

- **Rodamientos con falla de pista exterior o interior:** detectados en los 17 archivos con falla de MFPT y en los tramos evaluados de CWRU, sin falsas alarmas en los archivos sanos. Elemento rodante y jaula se detectan poco.
- **Desbalanceo:** detectado en 81 a 91 % de los archivos de MAFAULDA y en el 100 % de SRO.
- **Desalineación real:** no se detecta en MAFAULDA ni en SRO, y el sistema no distingue entre desalineación paralela y angular.
- Una **línea base sana** reduce de forma importante las falsas alarmas de las reglas de rotor.

## Arquitectura

```
frontend/        Interfaz web (React + Vite + Recharts)
backend/api/     API REST (FastAPI): equipos, sensores, mediciones, reportes, alertas, laboratorio
backend/procesamiento/   Cálculo: FFT, envolvente, PSO, diagnóstico, severidad ISO, calidad, reportes PDF
backend/notificaciones/  Aviso por correo y Telegram
basedatos/       Modelos y conexión (SQLAlchemy + MySQL)
seguridad/       Autenticación (bcrypt + JWT)
conocimiento/    Criterios de diagnóstico (YAML) y catálogo de sensores (CSV)
config/          Configuración no secreta (notificaciones, IA, nube)
herramientas/    Scripts: crear tablas, sembrar catálogo, validar el motor con datasets públicos
validacion/      Resultados de la validación
docs/            Documentación del proyecto y diagramas
```

La base de datos **no guarda las muestras** de las señales: guarda metadatos y resultados, y cada medición apunta al archivo que contiene las muestras (carpeta `datos/`).

## Requisitos

- Python 3.13 (probado con 3.13.5)
- Node.js 20 o superior (probado con 22)
- MySQL 8 (probado con 8.4)
- Desarrollado y probado en Windows 11. Los comandos de abajo son de PowerShell.

## Instalación

1. **Obtener el código y las dependencias de Python**

   ```powershell
   git clone https://github.com/cometavictor2020/mg.git
   cd mg
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Dependencias del frontend**

   ```powershell
   cd frontend
   npm install
   cd ..
   ```

3. **Base de datos.** Crea una base de datos y un usuario propio para la aplicación en MySQL (no uses `root`):

   ```sql
   CREATE DATABASE motorguardian CHARACTER SET utf8mb4;
   CREATE USER 'motorguardian_app'@'localhost' IDENTIFIED BY 'una_clave_segura';
   GRANT ALL PRIVILEGES ON motorguardian.* TO 'motorguardian_app'@'localhost';
   ```

4. **Variables de entorno.** Crea un archivo `.env` en la raíz del proyecto (está excluido de Git; **nunca lo subas**):

   | Variable | Obligatoria | Uso |
   |---|---|---|
   | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Sí | Conexión a MySQL |
   | `SECRET_KEY` | Sí | Clave para firmar los tokens de sesión (una cadena larga y aleatoria) |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | No | Avisos por correo (`SMTP_REMITENTE` es opcional) |
   | `TELEGRAM_BOT_TOKEN` | No | Avisos por Telegram |
   | `OPENAI_API_KEY` | No | Resumen redactado por IA en los reportes |

   Un canal de aviso o la IA sin sus credenciales simplemente se omiten. La configuración no secreta está en `config/` (por ejemplo `notificaciones.yaml` e `ia.yaml`, donde se elige el modelo de OpenAI).

5. **Crear las tablas y cargar el catálogo de sensores**

   ```powershell
   python herramientas\crear_tablas_basedatos.py
   python herramientas\sembrar_catalogo_sensores.py
   ```

6. **Crear el usuario de prueba** (`admin@motorguardian.io`, clave `mg2024`). Es solo para evaluar el sistema en tu equipo: **cambia o elimina esa cuenta antes de exponer la aplicación en una red**.

   ```powershell
   python herramientas\crear_usuario_demo.py
   ```

## Ejecución

En dos terminales:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn backend.api.main:app --reload --port 8000
```

```powershell
cd frontend
npm run dev
```

Abre <http://localhost:5173> e inicia sesión. La documentación interactiva de la API queda en <http://localhost:8000/docs>.

## Cómo extenderlo

MotorGuardian se diseñó para que otras personas agreguen sensores, métodos de análisis y modelos sin rehacer lo existente:

- **Nuevos tipos de sensor o de equipo:** son filas de la base de datos (catálogo abierto); los tipos de sensor se siembran desde `conocimiento/catalogo_sensores.csv`. Los datos específicos de cada tipo se guardan en campos JSON, por lo que no hace falta cambiar el esquema.
- **Nuevos formatos de archivo:** el importador de mediciones permite mapear columnas, unidades y frecuencia de muestreo, y guardar la plantilla para reutilizarla.
- **Nuevos métodos de análisis (otras variables o técnicas):** el cálculo está separado de la API y de la interfaz, en módulos de responsabilidad única dentro de `backend/procesamiento/`.
- **Criterios de diagnóstico:** se editan en los archivos de `conocimiento/`, no en el código.
- **Modelos de aprendizaje:** existe una tabla `modelo` para registrar sus metadatos y un módulo de API reservado para ellos (`backend/api/administracion/modelos_ml.py`); hoy solo registra, no entrena ni ejecuta modelos.

Hoy el sistema procesa **solo vibraciones**. Incorporar otras variables (temperatura, corriente, aceite) requiere escribir sus módulos de análisis.

## Datos de terceros

Este repositorio **no incluye** los conjuntos de datos usados en la validación ni los textos de las normas ISO. Los scripts de `herramientas/validar_*.py` leen los datasets desde carpetas locales; obtén cada uno de su fuente y respeta su licencia y la forma de citarlo:

- CWRU Bearing Data Center (Case Western Reserve University).
- MFPT (Society for Machinery Failure Prevention Technology).
- Universidad de Ottawa, conjunto de motor trifásico (Mendeley Data).
- MAFAULDA (Universidade Federal do Rio de Janeiro).
- SRO Cross-Speed Dataset (KFUPM; Mendeley Data, `y8mv28hjwb`).

El método de envolvente con selección de banda por PSO sigue el trabajo de Tyagi, S. y Panigrahi, S. K. (2017), *An improved envelope detection method using particle swarm optimisation for rolling element bearing fault diagnosis*, Journal of Computational Design and Engineering, 4(4), 305–317.

## Licencia

[MIT](LICENSE). Puedes usar, copiar, modificar y distribuir el software, incluso con fines comerciales, conservando el aviso de derechos de autor. La licencia no incluye garantía.

## Cómo citar

> Ramírez Modinger, V. M. (2026). *MotorGuardian: sistema de código abierto para el análisis de vibraciones y el apoyo a las decisiones de mantenimiento de motores* [Software]. Trabajo de título, Técnico Universitario en Mantención de Equipos Industriales, Universidad de Santiago de Chile. https://github.com/cometavictor2020/mg

## Autoría

Víctor Manuel Ramírez Modinger. Profesor guía: Pedro Saa Herrera. Facultad Tecnológica, Universidad de Santiago de Chile.
