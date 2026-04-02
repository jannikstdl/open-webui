"""
NetworkX-based graph storage backend.

Default graph DB — no external service needed.
Persists to JSON files per collection in DATA_DIR/graph/.
"""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set

import networkx as nx

from open_webui.retrieval.graph.main import (
    GraphDBBase,
    GraphEdge,
    GraphNode,
    GraphSearchResult,
)

log = logging.getLogger(__name__)


class NetworkXClient(GraphDBBase):
    def __init__(self):
        from open_webui.env import DATA_DIR

        self.storage_dir = Path(DATA_DIR) / "graph"
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._graphs: Dict[str, nx.DiGraph] = {}

    def _get_graph(self, collection_name: str) -> nx.DiGraph:
        if collection_name not in self._graphs:
            path = self.storage_dir / f"{collection_name}.json"
            if path.exists():
                try:
                    with open(path) as f:
                        data = json.load(f)
                    g = nx.node_link_graph(data, directed=True)
                except Exception as e:
                    log.warning(f"Failed to load graph {collection_name}: {e}")
                    g = nx.DiGraph()
            else:
                g = nx.DiGraph()
            self._graphs[collection_name] = g
        return self._graphs[collection_name]

    def _save_graph(self, collection_name: str) -> None:
        g = self._graphs.get(collection_name)
        if g is None:
            return
        path = self.storage_dir / f"{collection_name}.json"
        try:
            data = nx.node_link_data(g)
            with open(path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            log.error(f"Failed to save graph {collection_name}: {e}")

    def has_collection(self, collection_name: str) -> bool:
        path = self.storage_dir / f"{collection_name}.json"
        return path.exists() or collection_name in self._graphs

    def delete_collection(self, collection_name: str) -> None:
        self._graphs.pop(collection_name, None)
        path = self.storage_dir / f"{collection_name}.json"
        if path.exists():
            path.unlink()

    def upsert_node(self, collection_name: str, node: GraphNode) -> None:
        g = self._get_graph(collection_name)
        name = node.name

        if g.has_node(name):
            existing = g.nodes[name]
            # Merge descriptions
            old_desc = existing.get("description", "")
            if node.description and node.description not in old_desc:
                merged = f"{old_desc}\n{node.description}".strip()
                existing["description"] = merged
            # Update other fields
            existing["type"] = node.type or existing.get("type", "")
            existing["source_id"] = node.source_id
            existing["file_path"] = node.file_path or existing.get("file_path", "")
            existing["metadata"] = {**existing.get("metadata", {}), **node.metadata}
        else:
            g.add_node(
                name,
                id=node.id,
                name=name,
                type=node.type,
                description=node.description,
                source_id=node.source_id,
                file_path=node.file_path,
                metadata=node.metadata,
            )

        self._save_graph(collection_name)

    def upsert_edge(self, collection_name: str, edge: GraphEdge) -> None:
        g = self._get_graph(collection_name)
        src, tgt = edge.source, edge.target

        # Ensure nodes exist
        if not g.has_node(src):
            g.add_node(src, name=src, type="", description="", source_id="", file_path="", metadata={})
        if not g.has_node(tgt):
            g.add_node(tgt, name=tgt, type="", description="", source_id="", file_path="", metadata={})

        if g.has_edge(src, tgt):
            existing = g.edges[src, tgt]
            old_desc = existing.get("description", "")
            if edge.description and edge.description not in old_desc:
                existing["description"] = f"{old_desc}\n{edge.description}".strip()
            existing["weight"] = max(existing.get("weight", 1.0), edge.weight)
            old_kw = existing.get("keywords", "")
            if edge.keywords and edge.keywords not in old_kw:
                existing["keywords"] = f"{old_kw},{edge.keywords}".strip(",")
        else:
            g.add_edge(
                src,
                tgt,
                description=edge.description,
                keywords=edge.keywords,
                weight=edge.weight,
                source_id=edge.source_id,
                file_path=edge.file_path,
                metadata=edge.metadata,
            )

        self._save_graph(collection_name)

    def get_node(self, collection_name: str, name: str) -> Optional[GraphNode]:
        g = self._get_graph(collection_name)
        if not g.has_node(name):
            return None
        data = g.nodes[name]
        return GraphNode(
            id=data.get("id", name),
            name=name,
            type=data.get("type", ""),
            description=data.get("description", ""),
            source_id=data.get("source_id", ""),
            file_path=data.get("file_path", ""),
            metadata=data.get("metadata", {}),
        )

    def get_neighbors(
        self,
        collection_name: str,
        name: str,
        depth: int = 1,
        max_results: int = 50,
    ) -> GraphSearchResult:
        g = self._get_graph(collection_name)
        if not g.has_node(name):
            return GraphSearchResult()

        visited_nodes: Set[str] = {name}
        frontier: Set[str] = {name}
        all_edges: List[GraphEdge] = []

        for _ in range(depth):
            next_frontier: Set[str] = set()
            for node_name in frontier:
                # Both successors and predecessors (undirected traversal)
                for neighbor in list(g.successors(node_name)) + list(g.predecessors(node_name)):
                    if neighbor not in visited_nodes and len(visited_nodes) < max_results:
                        visited_nodes.add(neighbor)
                        next_frontier.add(neighbor)

                # Collect edges
                for _, tgt, data in g.out_edges(node_name, data=True):
                    all_edges.append(self._edge_from_data(node_name, tgt, data))
                for src, _, data in g.in_edges(node_name, data=True):
                    all_edges.append(self._edge_from_data(src, node_name, data))

            frontier = next_frontier
            if not frontier:
                break

        # Exclude the starting node from results
        visited_nodes.discard(name)

        nodes = []
        for n in visited_nodes:
            node = self.get_node(collection_name, n)
            if node:
                nodes.append(node)

        # Deduplicate edges
        seen_edges = set()
        unique_edges = []
        for e in all_edges:
            key = (e.source, e.target)
            if key not in seen_edges:
                seen_edges.add(key)
                unique_edges.append(e)

        return GraphSearchResult(nodes=nodes, edges=unique_edges)

    def get_edges(self, collection_name: str, name: str) -> List[GraphEdge]:
        g = self._get_graph(collection_name)
        if not g.has_node(name):
            return []

        edges = []
        for _, tgt, data in g.out_edges(name, data=True):
            edges.append(self._edge_from_data(name, tgt, data))
        for src, _, data in g.in_edges(name, data=True):
            edges.append(self._edge_from_data(src, name, data))
        return edges

    def search_nodes(
        self, collection_name: str, query: str, limit: int = 10
    ) -> List[GraphNode]:
        g = self._get_graph(collection_name)
        query_lower = query.lower()
        results = []

        for name, data in g.nodes(data=True):
            score = 0
            name_lower = name.lower()
            desc_lower = data.get("description", "").lower()

            if query_lower == name_lower:
                score = 3  # Exact match
            elif query_lower in name_lower:
                score = 2  # Partial name match
            elif query_lower in desc_lower:
                score = 1  # Description match

            if score > 0:
                results.append((score, name, data))

        results.sort(key=lambda x: x[0], reverse=True)

        return [
            GraphNode(
                id=data.get("id", name),
                name=name,
                type=data.get("type", ""),
                description=data.get("description", ""),
                source_id=data.get("source_id", ""),
                file_path=data.get("file_path", ""),
                metadata=data.get("metadata", {}),
            )
            for _, name, data in results[:limit]
        ]

    def delete_node(self, collection_name: str, name: str) -> None:
        g = self._get_graph(collection_name)
        if g.has_node(name):
            g.remove_node(name)  # Also removes all connected edges
            self._save_graph(collection_name)

    def reset(self) -> None:
        self._graphs.clear()
        if self.storage_dir.exists():
            for f in self.storage_dir.glob("*.json"):
                f.unlink()

    @staticmethod
    def _edge_from_data(src: str, tgt: str, data: dict) -> GraphEdge:
        return GraphEdge(
            source=src,
            target=tgt,
            description=data.get("description", ""),
            keywords=data.get("keywords", ""),
            weight=data.get("weight", 1.0),
            source_id=data.get("source_id", ""),
            file_path=data.get("file_path", ""),
            metadata=data.get("metadata", {}),
        )
