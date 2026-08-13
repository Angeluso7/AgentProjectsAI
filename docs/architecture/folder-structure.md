# Criterio de la estructura de carpetas

## Monorepo
Se propone monorepo para mantener backend, frontend, reglas, conocimiento guía y datasets en un mismo repositorio, pero con límites claros por dominio.

## Motivos
- Facilita desarrollo en GitHub y GitHub Actions.
- Permite versionar conjuntamente reglas, plantillas y código.
- Hace más simple compilar luego una interfaz web o escritorio.

## Compilación e interfaz
Sí, es posible desarrollar en GitHub y luego compilar una interfaz:
- Web app: React/Vite consumiendo FastAPI.
- Escritorio: Tauri o Electron cargando el frontend y apuntando a la API local/remota.
- Empaquetado Python: PyInstaller para utilidades CLI o workers locales.
