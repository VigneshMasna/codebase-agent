from __future__ import annotations

from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, ServiceUnavailable


class Neo4jClient:

    def __init__(self, uri: str, user: str, password: str) -> None:
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            self.driver.verify_connectivity()
        except AuthError as exc:
            raise ConnectionError(
                f"Neo4j authentication failed for user '{user}'. "
                "Check NEO4J_USER and NEO4J_PASSWORD in .env."
            ) from exc
        except ServiceUnavailable as exc:
            raise ConnectionError(
                f"Cannot connect to Neo4j at '{uri}'. "
                "Ensure Neo4j is running and NEO4J_URI is correct in .env."
            ) from exc
        except Exception as exc:
            raise ConnectionError(f"Failed to connect to Neo4j at '{uri}': {exc}") from exc

    def close(self) -> None:
        try:
            self.driver.close()
        except Exception:
            pass  # best-effort close

    def run_query(self, query: str, parameters: dict | None = None) -> list[dict]:
        try:
            with self.driver.session() as session:
                result = session.run(query, parameters or {})
                return [record.data() for record in result]
        except Exception as exc:
            raise RuntimeError(
                f"Neo4j query failed: {exc}\nQuery (first 200 chars): {query[:200]}"
            ) from exc
