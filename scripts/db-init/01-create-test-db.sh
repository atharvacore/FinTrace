#!/bin/sh
# Runs once, when the database volume is first created: adds a separate database for tests.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
	CREATE DATABASE fintrace_test OWNER "$POSTGRES_USER";
SQL
