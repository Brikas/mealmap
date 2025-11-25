import os
import subprocess
import sys

# Configuration
CONTAINER_NAME = "postgres"
DB_USER = "postgres"
DB_NAME = "postgres"
DUMP_PATH_CONTAINER = "/var/lib/postgresql/data/db_backup.pg_dump"
LOCAL_DUMP_DIR = os.path.join("gitignore", "db-dumps")
LOCAL_DUMP_FILE = os.path.join(LOCAL_DUMP_DIR, "db_backup.pg_dump")

def run_command(command, shell=False):
    """Run a shell command and exit if it fails."""
    # print(f"Running: {' '.join(command) if isinstance(command, list) else command}")
    try:
        subprocess.check_call(command, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        sys.exit(1)

def ensure_dir(path):
    if not os.path.exists(path):
        print(f"Creating directory: {path}")
        os.makedirs(path)

def db_dump():
    print("Dumping database...")
    # Dump inside container
    cmd_dump = [
        "docker", "exec", CONTAINER_NAME,
        "pg_dump", "-U", DB_USER, "-d", DB_NAME, "-F", "c", "-f", DUMP_PATH_CONTAINER
    ]
    run_command(cmd_dump)

    # Copy to host
    ensure_dir(LOCAL_DUMP_DIR)
    cmd_cp = ["docker", "cp", f"{CONTAINER_NAME}:{DUMP_PATH_CONTAINER}", LOCAL_DUMP_FILE]
    run_command(cmd_cp)
    print(f"Database dumped to {LOCAL_DUMP_FILE}")

def db_restore():
    if not os.path.exists(LOCAL_DUMP_FILE):
        print(f"Error: Backup file not found at '{LOCAL_DUMP_FILE}'")
        sys.exit(1)

    print("Backup file found. Proceeding with restore.")

    # Copy to container
    cmd_cp = ["docker", "cp", LOCAL_DUMP_FILE, f"{CONTAINER_NAME}:{DUMP_PATH_CONTAINER}"]
    run_command(cmd_cp)

    # Restore inside container
    # -c: clean (drop) database objects before creating them
    cmd_restore = [
        "docker", "exec", CONTAINER_NAME,
        "pg_restore", "-U", DB_USER, "-d", DB_NAME, "-c", DUMP_PATH_CONTAINER
    ]
    run_command(cmd_restore)
    print("Database restored.")

def db_reset():
    print("Resetting database...")
    # Drop and recreate public schema inside container
    cmd_reset = [
        "docker", "exec", CONTAINER_NAME,
        "psql", "-U", DB_USER, "-d", DB_NAME, "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
    ]
    run_command(cmd_reset)
    print("Database cleared.")

    print("Running alembic upgrade head...")
    # Assuming poetry is in path. On Windows, 'poetry' might be a batch file, so shell=True helps.
    run_command("poetry run alembic upgrade head", shell=True)

    print("Database reset complete.")

def migrate_test():
    db_dump()

    print("Running alembic upgrade head...")
    try:
        # Assuming poetry is in path. On Windows, 'poetry' might be a batch file, so shell=True helps.
        run_command("poetry run alembic upgrade head", shell=True)
    except SystemExit:
        print("Migration failed.")
        sys.exit(1)

    print("\nMigration applied. Press Enter to restore database (or Ctrl+C to stop)...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        sys.exit(0)

    db_restore()

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/db_manage.py [dump|restore|migrate-test|reset]")
        sys.exit(1)

    action = sys.argv[1]

    if action == "dump":
        db_dump()
    elif action == "restore":
        db_restore()
    elif action == "migrate-test":
        migrate_test()
    elif action == "reset":
        db_reset()
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)

if __name__ == "__main__":
    main()
