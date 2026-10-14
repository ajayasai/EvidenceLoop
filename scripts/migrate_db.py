"""Cross-platform PostgreSQL migrations using a separate administrative identity.

Connection strings are read from named environment variables, never echoed.
This script neither downloads PostgreSQL nor creates a paid service.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from services.api.app.storage import SCHEMA_SQL
from services.api.app.review import REVIEW_SCHEMA_SQL


class MigrationError(RuntimeError):
    """Content-free migration failure; never include a connection string."""


def _connection_parts(url):
    try:
        parts=conninfo_to_dict(url)
    except psycopg.Error as exc:
        raise MigrationError("Invalid database connection configuration.") from exc
    if not all(parts.get(k) for k in ("user","dbname","host")):
        raise MigrationError("Database URLs must explicitly name the host, database and identity.")
    return parts


def migrate(admin_url,app_url,schema="public",*,create_role=False,create_schema=False):
    """Migrate one exact schema while preserving a non-owner application role."""
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}",schema) or schema.startswith("pg_") or schema=="information_schema":
        raise MigrationError("Choose an ordinary, explicit application schema.")
    admin,app=_connection_parts(admin_url),_connection_parts(app_url)
    if admin["user"]==app["user"]:
        raise MigrationError("Migration and application identities must be different.")
    if any(admin.get(k,"5432" if k=="port" else "")!=app.get(k,"5432" if k=="port" else "") for k in ("host","port","dbname")):
        raise MigrationError("Migration and application URLs must target the same server and database.")
    role=app["user"]
    with psycopg.connect(admin_url,connect_timeout=5) as con:
        present=con.execute("SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname=%s",(role,)).fetchone()
        if present is None:
            if not create_role or not app.get("password"):
                raise MigrationError("The runtime role must exist, or use --create-role with an explicit runtime password.")
            con.execute(sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}").format(sql.Identifier(role),sql.Literal(app["password"])))
            present=(False,False,False,False,False)
        if any(present):
            raise MigrationError("The runtime role has administrative privileges; use an unprivileged application identity.")
        memberships=con.execute("""SELECT EXISTS(SELECT 1 FROM pg_roles r WHERE (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
             AND pg_has_role(%s,r.oid,'MEMBER'))""",(role,)).fetchone()[0]
        owns_database=con.execute("SELECT pg_has_role(%s,datdba,'MEMBER') FROM pg_database WHERE datname=current_database()",(role,)).fetchone()[0]
        if memberships or owns_database:
            raise MigrationError("The runtime identity must not own the database or inherit an administrative role.")
        exists=con.execute("SELECT nspowner FROM pg_namespace WHERE nspname=%s",(schema,)).fetchone()
        if create_schema:
            if exists:
                raise MigrationError("Requested new schema already exists; refusing to reuse it.")
            con.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        elif not exists:
            raise MigrationError("Schema does not exist; explicitly choose --create-schema if intended.")
        owns_objects=con.execute("""SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid
            WHERE n.nspname=%s AND pg_has_role(%s,c.relowner,'MEMBER'))""",(schema,role)).fetchone()[0]
        owns_schema=con.execute("SELECT pg_has_role(%s,nspowner,'MEMBER') FROM pg_namespace WHERE nspname=%s",(role,schema)).fetchone()[0]
        if owns_schema or owns_objects:
            raise MigrationError("Runtime must not own the schema or its tables; migrate using an administrative owner.")
        con.execute(sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(schema)))
        con.execute(SCHEMA_SQL)
        con.execute(REVIEW_SCHEMA_SQL)
        con.execute("INSERT INTO schema_versions(version) VALUES(2) ON CONFLICT DO NOTHING")
        con.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(admin["dbname"]),sql.Identifier(role)))
        con.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema),sql.Identifier(role)))
        con.execute(sql.SQL("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA {} TO {}").format(sql.Identifier(schema),sql.Identifier(role)))
        con.execute(sql.SQL("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA {} TO {}").format(sql.Identifier(schema),sql.Identifier(role)))
        if con.execute("SELECT has_schema_privilege(%s,%s,'CREATE')",(role,schema)).fetchone()[0]:
            raise MigrationError("Runtime has schema CREATE privilege. Remove that grant before using this schema.")
    # Verify the supplied application credentials can read the migrated schema.
    # Database ownership stays with the migration identity.
    with psycopg.connect(app_url,connect_timeout=5,options="-csearch_path="+schema) as con:
        version=con.execute("SELECT max(version) FROM schema_versions").fetchone()[0]
        if version!=2:
            raise MigrationError("Runtime schema verification failed.")
    return {"schema":schema,"schema_version":2,"runtime_role":role,"runtime_is_owner":False}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admin-env",default="DATABASE_ADMIN_URL",help="Name of the environment variable containing the migration URL")
    parser.add_argument("--app-env",default="DATABASE_URL",help="Name of the environment variable containing the non-owner runtime URL")
    parser.add_argument("--schema",default="public")
    parser.add_argument("--create-role",action="store_true",help="Create the runtime login if absent; never elevate an existing role")
    parser.add_argument("--create-schema",action="store_true",help="Create exactly the named new schema; fails if it exists")
    args=parser.parse_args(argv)
    admin_url,app_url=os.environ.get(args.admin_env),os.environ.get(args.app_env)
    if not admin_url or not app_url:
        parser.error("Both named database environment variables must be set.")
    try:
        result=migrate(admin_url,app_url,args.schema,create_role=args.create_role,create_schema=args.create_schema)
    except MigrationError as exc:
        print(f"Migration refused: {exc}",file=sys.stderr)
        return 1
    except psycopg.Error:
        print("Migration failed. Check server availability and migration permissions; connection details are not printed.",file=sys.stderr)
        return 1
    print(f"Schema {result['schema']} migrated to version {result['schema_version']}; runtime ownership remains separate.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
