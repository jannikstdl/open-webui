"""
Prompt templates for knowledge graph extraction.
"""

ENTITY_EXTRACTION_SYSTEM = """You are an expert at extracting entities and relationships from text.
Given a text chunk, extract all meaningful entities and their relationships.
Use the provided entity types as guidance but you may also identify other relevant types."""

ENTITY_EXTRACTION_PROMPT = """Extract all entities and relationships from the following text.

Entity Types to look for: {entity_types}

Text:
{text}

Return your response in the following format. Use <|#|> as field separator and put each entity/relation on its own line.

Entities (one per line):
ENTITY<|#|>entity_name<|#|>entity_type<|#|>entity_description

Relationships (one per line):
RELATION<|#|>source_entity<|#|>target_entity<|#|>relationship_keywords<|#|>relationship_description

Rules:
- Entity names should be specific and consistent (use full names, not pronouns)
- Entity descriptions should be concise but informative (1-2 sentences)
- Relationship keywords should be comma-separated action words
- Decompose complex N-ary relationships into binary pairs
- Every entity mentioned in a relationship must also be listed as an entity
- If no entities or relationships are found, return empty output"""

ENTITY_EXTRACTION_CONTINUE = """Some entities or relationships may have been missed in the previous extraction.
Please review the same text again and extract any ADDITIONAL entities and relationships not yet captured.

Previously extracted entities: {existing_entities}

Text:
{text}

Use the same format as before. Only output NEW entities and relationships not already listed above.
If nothing new is found, return empty output."""

KEYWORD_EXTRACTION_PROMPT = """Given the following query, extract keywords for knowledge graph search.

Query: {query}

Return your response as JSON:
{{
    "low_level": ["specific entity names or concepts mentioned"],
    "high_level": ["broader themes, topics, or abstract concepts"]
}}

Rules:
- low_level: specific names, terms, technical concepts (for entity search)
- high_level: general themes, domains, abstract ideas (for relationship search)
- Keep each list to 3-5 keywords maximum"""

DEFAULT_ENTITY_TYPES = [
    "person",
    "organization",
    "location",
    "event",
    "concept",
    "technology",
    "product",
    "document",
    "date",
    "metric",
]
