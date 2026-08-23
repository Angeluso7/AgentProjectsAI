#!/usr/bin/env python3
"""
Script de aprovisionamiento y configuración de PostgreSQL Row-Level Security (RLS).
Ejecuta la creación de roles, base de datos de test, migraciones Alembic y aplicación del script RLS.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# Ajustar path al root del repositorio
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

MIGRATOR_DB_URL = os.getenv(
    "POSTGRES_MIGRATOR_URL",
    "postgresql+psycopg://postgres_migrator:migrator_secure_pass_123@localhost:5433/planreview_test"
)
RLS_SQL_PATH = BASE_DIR / "migrations" / "rls_prepared_policies.sql"

def setup_postgres_rls():
    print(f"[*] Conectando a PostgreSQL como rol migrador: {MIGRATOR_DB_URL.split('@')[-1]}")
    try:
        engine = create_engine(MIGRATOR_DB_URL, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            # 1. Crear tablas ORM si no existen vía Alembic / Base metadata
            print("[*] Sincronizando metadata de base de datos...")
            from app.db.session import Base
            # Importar todos los modelos para registrar metadata
            import app.db.models
            Base.metadata.create_all(bind=conn)
            print("[+] Tablas creadas/verificadas exitosamente.")

            # 2. Aplicar script RLS
            print(f"[*] Aplicando políticas RLS desde {RLS_SQL_PATH.name}...")
            with open(RLS_SQL_PATH, "r", encoding="utf-8") as f:
                rls_sql = f.read()

            conn.execute(text(rls_sql))
            print("[+] Políticas RLS y rol app_user configurados exitosamente.")

            # 3. Validar estado de catálogos
            res = conn.execute(text("""
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity = true
                ORDER BY c.relname;
            """)).fetchall()

            print(f"\n[+] Tablas con Row-Level Security activo ({len(res)} tablas):")
            for row in res:
                print(f"    - {row[0]}: RLS={row[1]}, FORCE_RLS={row[2]}")

            # 4. Validar privilegios de app_user
            user_check = conn.execute(text("""
                SELECT rolname, rolsuper, rolbypassrls, rolcanlogin
                FROM pg_roles
                WHERE rolname = 'app_user';
            """)).fetchone()
            if user_check:
                print(f"\n[+] Verificación de rol app_user:")
                print(f"    - Rol: {user_check[0]}")
                print(f"    - SUPERUSER: {user_check[1]} (Esperado: False)")
                print(f"    - BYPASSRLS: {user_check[2]} (Esperado: False)")
                print(f"    - LOGIN: {user_check[3]} (Esperado: True)")

    except Exception as e:
        print(f"[-] Error configurando PostgreSQL RLS: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    setup_postgres_rls()
