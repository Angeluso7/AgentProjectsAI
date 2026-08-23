# Plan Review AI Hybrid — Instalación, Configuración y Puesta en Marcha

> **Documento**: 05_instalacion_configuracion_y_puesta_en_marcha.md  
> **Audiencia**: Administradores de Sistemas, Ingenieros DevOps, Desarrolladores, Operadores Técnicos  
> **Propósito**: Guía definitiva paso a paso para instalar, configurar, conectar servicios y arrancar el asistente técnico.

---

## 1. Qué Tengo que Conectar, Incorporar y Utilizar para Poner a Andar el Asistente

Para que el asistente opere correctamente, debes disponer e interconectar los siguientes elementos:

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    ARQUITECTURA DE CONEXIONES Y SERVICIOS                  │
│                                                                            │
│   [Navegador Web] ──:5173──> [Frontend React / Vite]                       │
│                                      │                                     │
│                                 (HTTP REST)                                │
│                                      ▼                                     │
│                              [Backend FastAPI] ──:8000                     │
│                                 │         │                                │
│                   ┌─────────────┴──┐   ┌──┴─────────────┐                  │
│                   ▼                ▼   ▼                ▼                  │
│             [PostgreSQL 15+]    [Redis]  [Modelos Visión] [Disco Local]    │
│                 (:5432)         (:6379)  (Paddle/YOLO)     (./data/)       │
└────────────────────────────────────────────────────────────────────────────┘
```

### Lista Priorizada de Conexiones Requeridas:
1. **Base de Datos Relacional (PostgreSQL 15+)**:
   - **Qué conectar**: String de conexión `DATABASE_URL` con usuario de aplicación `app_user`.
   - **Para qué sirve**: Persistencia de organizaciones, proyectos, láminas, textos, tablas, símbolos y hallazgos protegidos por Row-Level Security (RLS).
2. **Broker de Mensajería & Cache (Redis 7+)**:
   - **Qué conectar**: String `REDIS_URL=redis://localhost:6379/0`.
   - **Para qué sirve**: Colas de jobs asíncronos en segundo plano y control de locks de concurrencia para evitar que dos auditores procesen el mismo plano a la vez.
3. **Almacenamiento Local de Archivos (`./data/`)**:
   - **Qué incorporar**: Directorio en disco con permisos de lectura y escritura para guardar PDFs, imágenes a 300 DPI, recortes y reportes compilados.
4. **Capa Perceptual (Motores de Visión y OCR)**:
   - **Modo con IA**: PaddleOCR / Tesseract y pesos YOLO para detección de símbolos complejos en láminas rasterizadas.
   - **Modo sin IA**: Extracción puramente vectorial directa con `pdfplumber` y `PyMuPDF` (sin requerir descargas pesadas de pesos neuronales).
5. **Gateway & Frontend SPA**:
   - **Qué conectar**: Frontend configurado con `VITE_API_BASE_URL=http://localhost:8000/api/v1`.

---

## 2. Matriz de Componentes: Local vs. Producción

| Componente | Necesario para Arrancar (Dev Local) | Necesario para Producción | Función Técnica |
| :--- | :---: | :---: | :--- |
| **Python 3.11+** | **SÍ** | **SÍ** | Motor de ejecución del Backend y reglas QA/QC. |
| **FastAPI + Uvicorn** | **SÍ** | **SÍ** | Servidor de aplicaciones web y API REST. |
| **Node.js + npm** | **SÍ** (para compilar) | **SÍ** (en build stage) | Compilación y ejecución de la interfaz React. |
| **PostgreSQL 15+** | Opcional (sirve SQLite en memoria) | **SÍ (OBLIGATORIO)** | Aislamiento multi-tenant real mediante RLS. |
| **Redis 7+** | Opcional (jobs corren inline) | **SÍ (OBLIGATORIO)** | Tareas asíncronas pesadas y locks distribuidos. |
| **Docker & Compose** | Opcional (útil para rapidez) | **RECOMENDADO** | Orquestación reproducible y aislada de servicios. |
| **WeasyPrint** | **SÍ** | **SÍ** | Generación determinística de informes en PDF. |
| **Nginx / SSL** | NO | **SÍ (OBLIGATORIO)** | Terminación HTTPS y protección de endpoints. |

---

## 3. Matriz de Modos: Con IA vs. Sin IA

| Modo de Ejecución | Qué Incluye | Qué Pierde | Cuándo Usarlo |
| :--- | :--- | :--- | :--- |
| **Modo con IA** *(Completo)* | OCR profundo para escaneos, detección visual de símbolos con YOLO/SAHI, segmentación adaptativa. | Mayor consumo de memoria RAM ($>8\text{ GB}$) y tiempo de procesamiento más elevado. | Planos escaneados, PDFs rasterizados, proyectos con simbología compleja y auditoría exhaustiva. |
| **Modo sin IA** *(Reglas + Vectorial)* | Extracción nativa directa desde vectores PDF (`pdfplumber`), lectura de textos TrueType y evaluación determinística de reglas. | No detecta texto en imágenes escaneadas ni símbolos sin capas vectoriales limpias. | Planos vectoriales limpios exportados directamente desde AutoCAD/Revit; servidores con recursos mínimos ($<4\text{ GB}$ RAM). |

---

## 4. Variables de Entorno de Configuración (`.env`)

Crea un archivo `.env` en la raíz del proyecto basándote en `.env.example`:

```bash
# ============================================================================
# PLAN REVIEW AI HYBRID - CONFIGURACIÓN DE ENTORNO
# ============================================================================

# 1. Configuración General
ENVIRONMENT=development
DEBUG=true
DATA_DIR=./data

# 2. Base de Datos PostgreSQL 15+ (Usuario de Aplicación No Privilegiado)
DATABASE_URL=postgresql+psycopg://app_user:app_user_dev_pass@localhost:5432/planreview
DB_ECHO=false

# 3. Base de Datos para Migraciones (Rol Privilegiado para DDL / Alembic)
POSTGRES_MIGRATOR_URL=postgresql+psycopg://postgres_migrator:migrator_secure_pass_123@localhost:5432/planreview

# 4. Redis y Workers Asíncronos
REDIS_URL=redis://localhost:6379/0

# 5. Seguridad y JWT (Generar clave de al menos 32 caracteres)
SECRET_KEY=cambiar-esta-clave-secreta-por-una-cadena-segura-min-32-caracteres
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# 6. Parámetros de Inferencia y Percepción
DEFAULT_RENDER_DPI=300
UNCERTAINTY_MIN_CONF=0.35
UNCERTAINTY_MAX_CONF=0.70
```

---

## 5. Primera Puesta en Marcha en 15 Pasos (Guía Definitiva)

Sigue esta secuencia exacta para levantar el sistema completo desde cero:

### Opción A: Despliegue Automatizado con Docker Compose (Recomendado)

```bash
# Paso 1: Clonar el repositorio
git clone <url-del-repositorio> plan-review-ai-hybrid
cd plan-review-ai-hybrid

# Paso 2: Crear el archivo de variables de entorno
copy .env.example .env

# Paso 3: Construir y levantar todos los contenedores en segundo plano
docker compose up -d --build

# Paso 4: Esperar 15 segundos a que PostgreSQL y Redis estén saludables
docker compose ps

# Paso 5: Ejecutar las migraciones Alembic de base de datos
docker compose exec backend alembic upgrade head

# Paso 6: Inicializar datos semilla (Organización demo, usuario admin y reglas OGUC)
docker compose exec backend python scripts/seed_data.py

# Paso 7: Inicializar el Golden Dataset institucional
docker compose exec backend python scripts/seed_golden_dataset.py

# Paso 8: Abrir el navegador en la interfaz web
# URL: http://localhost:5173
```

---

### Opción B: Despliegue Manual en Entorno Local (Paso a Paso)

```bash
# Paso 1: Crear y activar entorno virtual Python
python -m venv .venv
# En Windows:
.venv\Scripts\activate
# En Linux/macOS:
# source .venv/bin/activate

# Paso 2: Instalar dependencias del Backend
pip install --upgrade pip
pip install -e ".[dev]"

# Paso 3: Configurar el archivo .env
copy .env.example .env

# Paso 4: (Si usas PostgreSQL local) Crear la base de datos y roles
# psql -U postgres -c "CREATE DATABASE planreview;"
# psql -U postgres -c "CREATE USER app_user WITH PASSWORD 'app_user_dev_pass' NOBYPASSRLS;"
# psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE planreview TO app_user;"

# Paso 5: Ejecutar migraciones Alembic
alembic upgrade head

# Paso 6: Sembrar datos iniciales (Usuarios y Reglas)
python scripts/seed_data.py

# Paso 7: Sembrar el Golden Dataset de referencia
python scripts/seed_golden_dataset.py

# Paso 8: Ejecutar la suite de pruebas para verificar integridad
pytest backend/tests/unit -v

# Paso 9: Iniciar el servidor Backend FastAPI
uvicorn app.main:app --app-dir backend --reload --port 8000

# Paso 10: En otra terminal, ingresar a la carpeta frontend e instalar dependencias
cd frontend
npm install

# Paso 11: Iniciar el servidor de desarrollo de Frontend
npm run dev

# Paso 12: Abrir navegador en http://localhost:5173
```

---

### Pasos de Validación Operativa y Primera Prueba:

```bash
# Paso 13: Iniciar Sesión en la Plataforma
# Usuario: admin@planreview.cl
# Contraseña: AdminPassword123!

# Paso 14: Cargar el Primer Plano PDF
# 1. Ir a la pestaña 'Intake & Fuentes' -> 'Registrar Nuevo Documento'.
# 2. Subir un archivo PDF de arquitectura (ej. Planta de Arquitectura).
# 3. Seleccionar Organización 'Constructora Principal' y Disciplina 'Arquitectura'.

# Paso 15: Ejecutar el Pipeline One-Click
# 1. Ir a 'One-Click Review'.
# 2. Seleccionar el plano cargado y hacer clic en 'Ejecutar Auditoría Completa'.
# 3. Observar el progreso en tiempo real de las 8 etapas.
# 4. Descargar el reporte PDF y el paquete de evidencias ZIP.
```

---

## 6. Comprobación del Estado de Salud del Sistema

Puedes verificar que todos los servicios responden correctamente ejecutando:

```bash
# Verificar endpoint de salud del Backend
curl -X GET http://localhost:8000/api/v1/health

# Respuesta esperada:
# {"status":"healthy","app_name":"Plan Review AI Hybrid Backend","version":"0.3.0"}
```
