import os
from pathlib import Path

from neo4j import GraphDatabase


def load_dotenv(path: str | Path = ".env") -> None:
    dotenv_path = Path(path)
    if not dotenv_path.is_file():
        return
    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


class Neo4jClient:
    def __init__(self) -> None:
        load_dotenv()
        uri, user, password = (os.getenv(name) for name in ("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"))
        if not all((uri, user, password)):
            raise RuntimeError("NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must be configured")
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def verify_connectivity(self) -> None:
        self.driver.verify_connectivity()

    def execute_write(self, query: str, **parameters: object) -> None:
        with self.driver.session() as session:
            session.execute_write(lambda tx: tx.run(query, **parameters).consume())

    def execute_read(self, query: str, **parameters: object) -> list[dict]:
        with self.driver.session() as session:
            return [record.data() for record in session.run(query, **parameters)]

    def close(self) -> None:
        self.driver.close()