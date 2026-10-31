#!/bin/bash
set -e

# PostgreSQL initialization script: Creates owner and app roles with secure passwords from env.
# Executed automatically by the official postgres entrypoint on first run.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create DB owner role (runs migrations, owns tables)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_OWNER_USER}') THEN
            CREATE ROLE ${DB_OWNER_USER} WITH LOGIN PASSWORD '${DB_OWNER_PASSWORD}';
        END IF;
    END
    \$\$;

    -- Create DB app role (runtime service user with restricted permissions)
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${DB_APP_USER}') THEN
            CREATE ROLE ${DB_APP_USER} WITH LOGIN PASSWORD '${DB_APP_PASSWORD}';
        END IF;
    END
    \$\$;

    -- Grant database connection
    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${DB_OWNER_USER};
    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${DB_APP_USER};

    -- Grant schema creation and ownership to owner
    GRANT ALL ON SCHEMA public TO ${DB_OWNER_USER};
    ALTER SCHEMA public OWNER TO ${DB_OWNER_USER};
EOSQL
