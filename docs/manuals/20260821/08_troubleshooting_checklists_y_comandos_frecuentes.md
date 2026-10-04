# Plan Review AI Hybrid — Troubleshooting, Checklists y Comandos Frecuentes

> **Documento**: 08_troubleshooting_checklists_y_comandos_frecuentes.md  
> **Audiencia**: Operadores Técnicos, Ingenieros DevOps, Soporte Técnico, Desarrolladores  
> **Propósito**: Guía rápida de resolución de incidencias, comandos frecuentes y checklists de verificación.

---

## 1. Matriz de Diagnóstico y Resolución de Problemas

| Problema Observado | Posible Causa Raíz | Cómo Verificar | Solución Recomendada |
| :--- | :--- | :--- | :--- |
| **Backend no inicia (`ModuleNotFoundError`)** | Entorno virtual inactivo o dependencias faltantes. | Ejecutar `pip list` en la terminal activa. | Activar entorno (`.venv\Scripts\activate`) y ejecutar `pip install -e ".[dev]"`. |
| **Frontend muestra pantalla en blanco o error de red** | El Backend no está corriendo o `VITE_API_BASE_URL` apunta a puerto erróneo. | Abrir consola del navegador (F12) e inspeccionar peticiones fallidas a `/api/v1`. | Verificar que Backend corra en puerto 8000 y revisar archivo `frontend/.env`. |
| **Fallo en conexión de Base de Datos (`ConnectionRefused`)** | PostgreSQL no está corriendo o credenciales de `.env` son inválidas. | Ejecutar `docker compose ps` o probar conexión con `psql`. | Levantar contenedor (`docker compose up -d db`) o corregir `DATABASE_URL` en `.env`. |
| **Alembic migration falla (`Target database is not up to date`)** | Desincronización de versiones de migración en la tabla `alembic_version`. | Ejecutar `alembic current` para ver la revisión actual. | Ejecutar `alembic upgrade head` o revisar ramas con `alembic heads`. |
| **Consultas devuelven 0 filas inesperadamente** | Contexto RLS no fue inyectado o el usuario pertenece a otra Organización. | Revisar que el header `X-Organization-Id` esté presente en la petición. | Seleccionar la organización correcta en la barra superior o revisar `OrganizationMembership`. |
| **Descarga de Reporte o Bundle devuelve `403 Forbidden`** | El rol del usuario es `viewer` o `contributor` (restringido por política RBAC). | Verificar el rol activo en el perfil (`GET /auth/me`). | Iniciar sesión con un usuario con rol `reviewer`, `audit_lead` o `admin`. |
| **El pipeline falla en etapa `OCR` o `WeasyPrint`** | Faltan binarios de sistema (`tesseract` o librerías gráficas de Pango/Cairo en Linux). | Revisar el stacktrace de error en la consola del backend. | En Linux: `apt-get install libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0 tesseract-ocr`. |
| **Corrida de evaluación retorna `insufficient_sample`** | El dataset tiene menos de $N_{\text{min}}$ muestras aprobadas (ej. $N < 3$). | Revisar el scorecard y la cantidad de muestras en estado `approved`. | Aprobar anotaciones en la pestaña de Golden Datasets antes de evaluar. |

---

## 2. Checklists Operativos

### Checklist A: Instalación Inicial
- [ ] Python 3.11+ instalado y verificado (`python --version`).
- [ ] Node.js 18+ y npm instalados (`node -v`, `npm -v`).
- [ ] Archivo `.env` creado con clave secreta robusta (`SECRET_KEY`).
- [ ] Migraciones Alembic aplicadas exitosamente (`alembic upgrade head`).
- [ ] Datos semilla creados (`python scripts/seed_data.py`).
- [ ] Directorio `./data/` creado con permisos de escritura.

### Checklist B: Arranque Diario del Sistema
- [ ] Contenedores PostgreSQL y Redis en estado saludable (`docker compose ps`).
- [ ] Backend respondiendo `healthy` en `http://localhost:8000/api/v1/health`.
- [ ] Frontend accesible en `http://localhost:5173`.
- [ ] Login exitoso con credenciales de auditor.

### Checklist C: Antes de Despliegue a Producción
- [ ] Conexión runtime configurada estrictamente con rol `app_user` (`NOBYPASSRLS`).
- [ ] Terminación HTTPS activa mediante Nginx o reverse proxy.
- [ ] Debug desactivado (`DEBUG=false` en `.env`).
- [ ] Volúmenes de datos (`./data/`) montados en almacenamiento persistente con respaldo periódico.
- [ ] Suite de pruebas completada sin fallos (`pytest backend/tests/unit -v`).

---

## 3. Hoja de Comandos Frecuentes (*Cheat Sheet*)

```bash
# ----------------------------------------------------------------------------
# 1. DOCKER COMPOSE (Entorno Completo)
# ----------------------------------------------------------------------------
docker compose up -d --build             # Construir y levantar servicios en segundo plano
docker compose ps                        # Ver estado y puertos de los contenedores
docker compose logs -f backend           # Ver logs en vivo del servidor backend
docker compose down                      # Detener todos los servicios
docker compose down -v                   # Detener y eliminar volúmenes (reset total)

# ----------------------------------------------------------------------------
# 2. BASE DE DATOS Y MIGRACIONES
# ----------------------------------------------------------------------------
alembic upgrade head                     # Aplicar todas las migraciones pendientes
alembic current                          # Ver versión actual de base de datos
alembic history                          # Ver historial de cambios
python scripts/seed_data.py              # Poblar datos demo y reglas iniciales
python scripts/seed_golden_dataset.py    # Poblar Golden Dataset institucional

# ----------------------------------------------------------------------------
# 3. EJECUCIÓN MANUAL LOCAL
# ----------------------------------------------------------------------------
# Backend
uvicorn app.main:app --app-dir backend --reload --port 8000

# Frontend
cd frontend && npm run dev

# ----------------------------------------------------------------------------
# 4. SUITE DE PRUEBAS
# ----------------------------------------------------------------------------
pytest backend/tests/unit -v             # Tests unitarios rápidos (SQLite)
python -m compileall backend scripts     # Verificar compilación de sintaxis Python

# ----------------------------------------------------------------------------
# 5. INTEGRACIÓN POSTGRESQL RLS (Puerto 5433 aislado)
# ----------------------------------------------------------------------------
docker compose -f docker-compose.integration.yml up -d
python scripts/setup_postgres_rls.py
pytest backend/tests/integration/test_postgres_rls.py -v -m postgres
```

---

## 4. Runbook Mínimo del Operador Técnico

Si el sistema presenta una degradación o comportamiento errático, sigue esta secuencia de rescate:

```
[1. Inspeccionar /health] ──> [2. Revisar Logs] ──> [3. Limpiar Locks] ──> [4. Reiniciar Worker]
```

1. **Paso 1**: Consulta `http://localhost:8000/api/v1/health`. Si no responde, el proceso Uvicorn cayó por falta de memoria o error fatal.
2. **Paso 2**: Revisa los últimos 100 logs del backend:
   ```bash
   docker compose logs --tail=100 backend
   ```
3. **Paso 3 (Liberación de Locks Huérfanos)**: Si un plano quedó bloqueado por una caída abrupta a mitad de procesamiento, el sistema auto-recupera locks inactivos tras 30 minutos. Para forzar la liberación inmediata:
   ```bash
   # Re-ejecutar el endpoint con force_reprocess=true desde la UI o API
   ```
4. **Paso 4 (Reinicio Limpio)**:
   ```bash
   docker compose restart backend
   ```
