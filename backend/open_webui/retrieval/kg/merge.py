"""
Entity deduplication and description merge logic.

When the same entity appears across multiple chunks or modalities,
merge their descriptions into a consolidated node.
"""

import logging
from typing import Dict, List, Tuple

from open_webui.retrieval.graph.main import GraphEdge, GraphNode

log = logging.getLogger(__name__)


def merge_nodes_and_edges(
    entities: List[Dict[str, str]],
    relations: List[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Merge duplicate entities and relations.

    Entities with the same name get their descriptions concatenated.
    Relations with the same (source, target) get their descriptions merged.

    Returns:
        (merged_entities, merged_relations)
    """
    # Merge entities by name (case-insensitive key, preserve original case)
    entity_map: Dict[str, Dict[str, str]] = {}
    for e in entities:
        key = e["name"].strip().lower()
        if key in entity_map:
            existing = entity_map[key]
            # Merge descriptions
            if e.get("description") and e["description"] not in existing.get("description", ""):
                existing["description"] = f"{existing.get('description', '')}\n{e['description']}".strip()
            # Keep more specific type
            if e.get("type") and not existing.get("type"):
                existing["type"] = e["type"]
        else:
            entity_map[key] = {**e}

    # Merge relations by (source, target)
    relation_map: Dict[Tuple[str, str], Dict[str, str]] = {}
    for r in relations:
        key = (r["source"].strip().lower(), r["target"].strip().lower())
        if key in relation_map:
            existing = relation_map[key]
            if r.get("description") and r["description"] not in existing.get("description", ""):
                existing["description"] = f"{existing.get('description', '')}\n{r['description']}".strip()
            if r.get("keywords") and r["keywords"] not in existing.get("keywords", ""):
                existing["keywords"] = f"{existing.get('keywords', '')},{r['keywords']}".strip(",")
        else:
            relation_map[key] = {**r}

    merged_entities = list(entity_map.values())
    merged_relations = list(relation_map.values())

    log.info(
        f"Merged {len(entities)} entities → {len(merged_entities)}, "
        f"{len(relations)} relations → {len(merged_relations)}"
    )

    return merged_entities, merged_relations
