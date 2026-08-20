"""Loads a small, real slice of DBLP co-authorship data into MySQL --
the third of three source systems this project scans (Postgres, SQLite,
MySQL), each introspected through a genuinely different mechanism.

The data itself (dblp_sample.json) is real, not generated: it's a
connected neighborhood of the DBLP co-authorship graph, extracted by a
5-hop breadth-first search starting from the actual Meltdown vulnerability
paper (tr/meltdown/s18) using the cached graph from another one of my
projects (bipartite-layout, github.com/YukaYuu/bipartite-layout). The
authors are real published researchers (e.g. Daniel Genkin, Moritz Lipp,
Paul Kocher -- co-authors of the Meltdown and Spectre papers), and the
paper identifiers are real DBLP keys, not placeholders.

Schema is deliberately a genuine many-to-many relationship (papers can
have multiple authors, authors can have multiple papers) via a join
table, rather than the one-table-per-source shape used for the SQLite
source -- gives the scanner a table it hasn't seen a shape like before.
"""

import json
import os
import time
from pathlib import Path

import pymysql

DATA_PATH = os.path.join(os.path.dirname(__file__), "dblp_sample.json")


def _connect_with_retry(host, port, user, password, database, attempts=10, delay_seconds=2):
    """MySQL's first-boot sequence briefly runs a temporary, socket-only
    instance to execute its own init scripts, then restarts with real
    networking enabled -- the compose healthcheck can report "healthy"
    during that temporary instance (see docker-compose.yml's comment on
    the mysql service), so a connection attempt right after can still
    hit a real ConnectionRefusedError even though compose says the
    dependency is ready. Retrying with a short delay rides out that
    restart window instead of failing the whole seed run over it.
    """
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return pymysql.connect(host=host, port=port, user=user, password=password, database=database)
        except pymysql.err.OperationalError as exc:
            last_error = exc
            print(f"MySQL not ready yet (attempt {attempt}/{attempts}): {exc}")
            time.sleep(delay_seconds)
    raise last_error

CREATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS authors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS papers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dblp_key VARCHAR(255) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS paper_authors (
    paper_id INT NOT NULL,
    author_id INT NOT NULL,
    PRIMARY KEY (paper_id, author_id),
    FOREIGN KEY (paper_id) REFERENCES papers(id),
    FOREIGN KEY (author_id) REFERENCES authors(id)
);
"""


def load_mysql_source() -> None:
    host = os.environ["MYSQL_HOST"]
    port = int(os.environ.get("MYSQL_PORT", "3306"))
    user = os.environ["MYSQL_USER"]
    password = os.environ["MYSQL_PASSWORD"]
    database = os.environ["MYSQL_DATABASE"]

    with open(DATA_PATH) as f:
        sample = json.load(f)

    conn = _connect_with_retry(host, port, user, password, database)
    try:
        with conn.cursor() as cur:
            for statement in CREATE_SCHEMA_SQL.split(";"):
                if statement.strip():
                    cur.execute(statement)

            # Rebuilt fresh on every seed run, same reasoning as
            # load_postgres_source.py: compose can legitimately re-run
            # seed when a downstream service starts on its own.
            cur.execute("DELETE FROM paper_authors")
            cur.execute("DELETE FROM papers")
            cur.execute("DELETE FROM authors")

            author_id = {}
            for name in sample["authors"]:
                cur.execute("INSERT INTO authors (name) VALUES (%s)", (name,))
                author_id[name] = cur.lastrowid

            paper_id = {}
            for key in sample["papers"]:
                cur.execute("INSERT INTO papers (dblp_key) VALUES (%s)", (key,))
                paper_id[key] = cur.lastrowid

            for author_name, paper_key in sample["authorship"]:
                cur.execute(
                    "INSERT INTO paper_authors (paper_id, author_id) VALUES (%s, %s)",
                    (paper_id[paper_key], author_id[author_name]),
                )
        conn.commit()
        print(
            f"Loaded {len(sample['authors'])} authors, {len(sample['papers'])} papers, "
            f"{len(sample['authorship'])} authorship links into MySQL."
        )
    finally:
        conn.close()


if __name__ == "__main__":
    load_mysql_source()
