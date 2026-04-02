"""
Prompt templates for multimodal content analysis.
"""

IMAGE_ANALYSIS_SYSTEM = (
    "You are an expert image analyst. Provide detailed, accurate descriptions."
)

IMAGE_ANALYSIS_PROMPT = """Analyze this image in detail and provide a JSON response:

{{
    "detailed_description": "Comprehensive visual description including:
    - Overall composition and layout
    - All objects, people, text, and visual elements
    - Relationships between elements
    - Technical details if relevant (charts, diagrams, etc.)
    - Always use specific names instead of pronouns",
    "entity_info": {{
        "entity_name": "unique descriptive name for this image",
        "entity_type": "image",
        "summary": "concise summary of the image content (max 100 words)"
    }}
}}

Image context:
- Captions: {captions}
- Footnotes: {footnotes}
- Surrounding text: {context}

Focus on accurate visual analysis useful for knowledge retrieval."""

IMAGE_ANALYSIS_FALLBACK_PROMPT = """Based on the following image information, provide analysis:

Captions: {captions}
Footnotes: {footnotes}
Surrounding text: {context}

Provide a JSON response with:
{{
    "detailed_description": "description based on available information",
    "entity_info": {{
        "entity_name": "descriptive name",
        "entity_type": "image",
        "summary": "concise summary (max 100 words)"
    }}
}}"""

TABLE_ANALYSIS_SYSTEM = (
    "You are an expert data analyst. Provide detailed table analysis."
)

TABLE_ANALYSIS_PROMPT = """Analyze this table content and provide a JSON response:

{{
    "detailed_description": "Comprehensive analysis including:
    - Table structure and organization
    - Column headers and their meanings
    - Key data points and patterns
    - Statistical insights and trends
    - Relationships between data elements
    Always use specific names and values.",
    "entity_info": {{
        "entity_name": "descriptive name for this table",
        "entity_type": "table",
        "summary": "concise summary of the table's purpose and key findings (max 100 words)"
    }}
}}

Table Information:
Caption: {caption}
Body: {body}
Footnotes: {footnotes}
Surrounding text: {context}"""

EQUATION_ANALYSIS_SYSTEM = (
    "You are an expert mathematician. Provide detailed mathematical analysis."
)

EQUATION_ANALYSIS_PROMPT = """Analyze this mathematical equation and provide a JSON response:

{{
    "detailed_description": "Analysis including:
    - Mathematical meaning and interpretation
    - Variables and their definitions
    - Application domain and context
    - Physical or theoretical significance",
    "entity_info": {{
        "entity_name": "descriptive name for this equation",
        "entity_type": "equation",
        "summary": "concise summary of the equation's purpose (max 100 words)"
    }}
}}

Equation: {equation_text}
Format: {equation_format}
Surrounding text: {context}"""

# Chunk templates for storing analyzed multimodal content
IMAGE_CHUNK_TEMPLATE = """Image Content Analysis:
Image Path: {image_path}
Captions: {captions}
Footnotes: {footnotes}

Visual Analysis: {description}"""

TABLE_CHUNK_TEMPLATE = """Table Analysis:
Caption: {caption}
Structure: {body}
Footnotes: {footnotes}

Analysis: {description}"""

EQUATION_CHUNK_TEMPLATE = """Mathematical Equation Analysis:
Equation: {equation_text}
Format: {equation_format}

Mathematical Analysis: {description}"""
