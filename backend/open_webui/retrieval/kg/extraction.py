"""
Entity and relationship extraction from text chunks via LLM.
"""

import json
import logging
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from open_webui.retrieval.graph.main import GraphEdge, GraphNode
from open_webui.retrieval.kg.prompts import (
    DEFAULT_ENTITY_TYPES,
    ENTITY_EXTRACTION_CONTINUE,
    ENTITY_EXTRACTION_PROMPT,
    ENTITY_EXTRACTION_SYSTEM,
    KEYWORD_EXTRACTION_PROMPT,
)

log = logging.getLogger(__name__)

FIELD_SEP = "<|#|>"


def parse_extraction_response(
    response: str,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Parse LLM response into entities and relations."""
    entities = []
    relations = []

    for line in response.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        parts = line.split(FIELD_SEP)
        parts = [p.strip() for p in parts]

        if len(parts) >= 4 and parts[0].upper() == "ENTITY":
            entities.append(
                {
                    "name": parts[1],
                    "type": parts[2],
                    "description": parts[3],
                }
            )
        elif len(parts) >= 5 and parts[0].upper() == "RELATION":
            relations.append(
                {
                    "source": parts[1],
                    "target": parts[2],
                    "keywords": parts[3],
                    "description": parts[4],
                }
            )

    return entities, relations


async def extract_entities_from_chunks(
    chunks: List[Dict[str, Any]],
    llm_func: Callable,
    entity_types: Optional[List[str]] = None,
    max_gleaning: int = 1,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Extract entities and relations from a list of text chunks.

    Args:
        chunks: List of dicts with "content" key
        llm_func: Async callable(prompt, system_prompt) -> str
        entity_types: Entity types to extract
        max_gleaning: Number of additional extraction passes

    Returns:
        (all_entities, all_relations)
    """
    if entity_types is None:
        entity_types = DEFAULT_ENTITY_TYPES

    types_str = ", ".join(entity_types)
    all_entities = []
    all_relations = []

    for chunk in chunks:
        text = chunk.get("content", chunk.get("page_content", ""))
        if not text.strip():
            continue

        prompt = ENTITY_EXTRACTION_PROMPT.format(
            entity_types=types_str,
            text=text,
        )

        try:
            response = await llm_func(prompt, ENTITY_EXTRACTION_SYSTEM)
            entities, relations = parse_extraction_response(response)
            all_entities.extend(entities)
            all_relations.extend(relations)

            # Gleaning: additional passes for missed entities
            for _ in range(max_gleaning):
                if not entities:
                    break
                existing_names = ", ".join(e["name"] for e in entities)
                continue_prompt = ENTITY_EXTRACTION_CONTINUE.format(
                    existing_entities=existing_names,
                    text=text,
                )
                response = await llm_func(continue_prompt, ENTITY_EXTRACTION_SYSTEM)
                new_entities, new_relations = parse_extraction_response(response)
                if not new_entities and not new_relations:
                    break
                all_entities.extend(new_entities)
                all_relations.extend(new_relations)
                entities.extend(new_entities)

        except Exception as e:
            log.error(f"Entity extraction failed for chunk: {e}")
            continue

    return all_entities, all_relations


def entities_to_graph_nodes(
    entities: List[Dict[str, str]],
    source_id: str = "",
    file_path: str = "",
) -> List[GraphNode]:
    """Convert extracted entity dicts to GraphNode objects."""
    nodes = []
    seen = set()
    for e in entities:
        name = e["name"].strip()
        if not name or name in seen:
            continue
        seen.add(name)
        nodes.append(
            GraphNode(
                id=name,
                name=name,
                type=e.get("type", ""),
                description=e.get("description", ""),
                source_id=source_id,
                file_path=file_path,
            )
        )
    return nodes


def relations_to_graph_edges(
    relations: List[Dict[str, str]],
    source_id: str = "",
    file_path: str = "",
) -> List[GraphEdge]:
    """Convert extracted relation dicts to GraphEdge objects."""
    edges = []
    seen = set()
    for r in relations:
        src = r["source"].strip()
        tgt = r["target"].strip()
        if not src or not tgt:
            continue
        key = (src, tgt, r.get("keywords", ""))
        if key in seen:
            continue
        seen.add(key)
        edges.append(
            GraphEdge(
                source=src,
                target=tgt,
                description=r.get("description", ""),
                keywords=r.get("keywords", ""),
                weight=1.0,
                source_id=source_id,
                file_path=file_path,
            )
        )
    return edges


async def extract_query_keywords(
    query: str,
    llm_func: Callable,
) -> Dict[str, List[str]]:
    """
    Extract high-level and low-level keywords from a query for graph search.

    Returns: {"low_level": [...], "high_level": [...]}
    """
    prompt = KEYWORD_EXTRACTION_PROMPT.format(query=query)

    try:
        response = await llm_func(prompt, "You are a helpful assistant.")

        # Try to parse JSON from response
        json_match = re.search(r"\{.*\}", response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                "low_level": result.get("low_level", []),
                "high_level": result.get("high_level", []),
            }
    except Exception as e:
        log.warning(f"Keyword extraction failed, using query as fallback: {e}")

    # Fallback: use query words as low-level keywords
    words = [w for w in query.split() if len(w) > 2]
    return {"low_level": words[:5], "high_level": [query]}
