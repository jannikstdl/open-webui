from typing import Optional

from open_webui.retrieval.graph.main import GraphDBBase
from open_webui.retrieval.graph.type import GraphType


class Graph:

    @staticmethod
    def get_graph(graph_type: str) -> Optional[GraphDBBase]:
        """Get graph db instance by type. Returns None if disabled."""
        if not graph_type:
            return None

        match graph_type:
            case GraphType.NETWORKX:
                from open_webui.retrieval.graph.dbs.networkx import NetworkXClient

                return NetworkXClient()
            case GraphType.NEO4J:
                from open_webui.retrieval.graph.dbs.neo4j import Neo4jClient

                return Neo4jClient()
            case GraphType.PGRAPH:
                from open_webui.retrieval.graph.dbs.pgraph import PGraphClient

                return PGraphClient()
            case _:
                raise ValueError(f"Unsupported graph type: {graph_type}")
