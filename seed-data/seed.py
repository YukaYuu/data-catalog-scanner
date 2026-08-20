from build_sqlite_source import build_sqlite_source
from load_mysql_source import load_mysql_source
from load_postgres_source import load_postgres_source

if __name__ == "__main__":
    load_postgres_source()
    build_sqlite_source()
    load_mysql_source()
