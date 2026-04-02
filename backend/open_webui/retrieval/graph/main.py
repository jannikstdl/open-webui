from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class GraphNode(BaseModel):
    """A node in the knowledge graph."""

    id: str
    name: str
    type: str
    description: str
    source_id: str  # chunk_id that generated this entity
    file_path: str = ""
    metadata: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    """An edge (relationship) in the knowledge graph."""

    source: str  # source entity name
    target: str  # target entity name
    description: str
    keywords: str = ""
    weight: float = 1.0
    source_id: str = ""  # chunk_id that generated this relation
    file_path: str = ""
    metadata: Dict[str, Any] = {}


class GraphSearchResult(BaseModel):
    """Result from a graph traversal."""

    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []


class GraphDBBase(ABC):
    """
    Abstract base class for all graph database backends.

    Follows the same pattern as VectorDBBase.
    Each collection_name corresponds to a knowledge base.
    """

    @abstractmethod
    def has_collection(self, collection_name: str) -> bool:
        """Check if a graph collection exists."""
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        """Delete all nodes and edges for a collection."""
        pass

    @abstractmethod
    def upsert_node(self, collection_name: str, node: GraphNode) -> None:
        """Insert or update a node. Merges descriptions if node exists."""
        pass

    @abstractmethod
    def upsert_edge(self, collection_name: str, edge: GraphEdge) -> None:
        """Insert or update an edge. Merges descriptions if edge exists."""
        pass

    @abstractmethod
    def get_node(self, collection_name: str, name: str) -> Optional[GraphNode]:
        """Get a node by name."""
        pass

    @abstractmethod
    def get_neighbors(
        self,
        collection_name: str,
        name: str,
        depth: int = 1,
        max_results: int = 50,
    ) -> GraphSearchResult:
        """Get neighboring nodes and edges up to N hops."""
        pass

    @abstractmethod
    def get_edges(
        self, collection_name: str, name: str
    ) -> List[GraphEdge]:
        """Get all edges connected to a node."""
        pass

    @abstractmethod
    def search_nodes(
        self,
        collection_name: str,
        query: str,
        limit: int = 10,
    ) -> List[GraphNode]:
        """Text search across node names and descriptions."""
        pass

    @abstractmethod
    def delete_node(self, collection_name: str, name: str) -> None:
        """Delete a node and all its edges."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset the entire graph database."""
        pass
