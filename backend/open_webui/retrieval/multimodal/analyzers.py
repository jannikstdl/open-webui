"""
Multimodal content analyzers using VLM/LLM.

Generates text descriptions + entity info from images, tables, equations.
"""

import json
import logging
import re
from typing import Any, Callable, Dict, Optional, Tuple

from open_webui.retrieval.multimodal.prompts import (
    EQUATION_ANALYSIS_PROMPT,
    EQUATION_ANALYSIS_SYSTEM,
    IMAGE_ANALYSIS_FALLBACK_PROMPT,
    IMAGE_ANALYSIS_PROMPT,
    IMAGE_ANALYSIS_SYSTEM,
    TABLE_ANALYSIS_PROMPT,
    TABLE_ANALYSIS_SYSTEM,
)

log = logging.getLogger(__name__)


def robust_json_parse(response: str) -> Dict[str, Any]:
    """Parse JSON from LLM response with multiple fallback strategies."""
    # Strategy 1: Extract JSON from code blocks
    json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
    for block in json_blocks:
        try:
            return json.loads(block)
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 2: Find balanced braces
    brace_count = 0
    start_pos = -1
    for i, char in enumerate(response):
        if char == "{":
            if brace_count == 0:
                start_pos = i
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0 and start_pos != -1:
                try:
                    return json.loads(response[start_pos : i + 1])
                except (json.JSONDecodeError, ValueError):
                    pass

    # Strategy 3: Regex field extraction
    log.warning("Using regex fallback for JSON parsing")
    desc_match = re.search(
        r'"detailed_description":\s*"([^"]*(?:\\.[^"]*)*)"', response, re.DOTALL
    )
    name_match = re.search(r'"entity_name":\s*"([^"]*(?:\\.[^"]*)*)"', response)
    type_match = re.search(r'"entity_type":\s*"([^"]*(?:\\.[^"]*)*)"', response)
    summary_match = re.search(
        r'"summary":\s*"([^"]*(?:\\.[^"]*)*)"', response, re.DOTALL
    )

    description = desc_match.group(1) if desc_match else response[:500]
    entity_name = name_match.group(1) if name_match else "unknown_content"

    return {
        "detailed_description": description,
        "entity_info": {
            "entity_name": entity_name,
            "entity_type": type_match.group(1) if type_match else "unknown",
            "summary": summary_match.group(1) if summary_match else description[:100],
        },
    }


async def analyze_image(
    image_data: Optional[str],
    captions: str = "",
    footnotes: str = "",
    context: str = "",
    vlm_func: Optional[Callable] = None,
    llm_func: Optional[Callable] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Analyze an image using VLM (or LLM fallback with text description).

    Args:
        image_data: Base64-encoded image data (None for text-only fallback)
        captions: Image captions
        footnotes: Image footnotes
        context: Surrounding text context
        vlm_func: Async callable(prompt, system_prompt, image_data) -> str
        llm_func: Async callable(prompt, system_prompt) -> str

    Returns:
        (description, entity_info)
    """
    prompt = IMAGE_ANALYSIS_PROMPT.format(
        captions=captions or "None",
        footnotes=footnotes or "None",
        context=context or "None",
    )

    try:
        if image_data and vlm_func:
            response = await vlm_func(prompt, IMAGE_ANALYSIS_SYSTEM, image_data)
        elif llm_func:
            # Text-only fallback
            fallback_prompt = IMAGE_ANALYSIS_FALLBACK_PROMPT.format(
                captions=captions or "None",
                footnotes=footnotes or "None",
                context=context or "None",
            )
            response = await llm_func(fallback_prompt, IMAGE_ANALYSIS_SYSTEM)
        else:
            return captions or "Image content", {
                "entity_name": "unknown_image",
                "entity_type": "image",
                "summary": captions or "Image content",
            }

        parsed = robust_json_parse(response)
        description = parsed.get("detailed_description", "")
        entity_info = parsed.get("entity_info", {})

        if not entity_info.get("entity_name"):
            entity_info["entity_name"] = "image_content"
        if not entity_info.get("entity_type"):
            entity_info["entity_type"] = "image"

        return description, entity_info

    except Exception as e:
        log.error(f"Image analysis failed: {e}")
        return captions or "Image content", {
            "entity_name": "unknown_image",
            "entity_type": "image",
            "summary": captions or "Image content",
        }


async def analyze_table(
    body: str,
    caption: str = "",
    footnotes: str = "",
    context: str = "",
    llm_func: Optional[Callable] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Analyze a table using LLM."""
    if not llm_func:
        return body, {
            "entity_name": caption or "table_content",
            "entity_type": "table",
            "summary": caption or body[:100],
        }

    prompt = TABLE_ANALYSIS_PROMPT.format(
        caption=caption or "None",
        body=body or "None",
        footnotes=footnotes or "None",
        context=context or "None",
    )

    try:
        response = await llm_func(prompt, TABLE_ANALYSIS_SYSTEM)
        parsed = robust_json_parse(response)
        description = parsed.get("detailed_description", "")
        entity_info = parsed.get("entity_info", {})

        if not entity_info.get("entity_name"):
            entity_info["entity_name"] = caption or "table_content"
        if not entity_info.get("entity_type"):
            entity_info["entity_type"] = "table"

        return description, entity_info

    except Exception as e:
        log.error(f"Table analysis failed: {e}")
        return body, {
            "entity_name": caption or "table_content",
            "entity_type": "table",
            "summary": caption or body[:100],
        }


async def analyze_equation(
    equation_text: str,
    equation_format: str = "latex",
    context: str = "",
    llm_func: Optional[Callable] = None,
) -> Tuple[str, Dict[str, Any]]:
    """Analyze a mathematical equation using LLM."""
    if not llm_func:
        return equation_text, {
            "entity_name": f"equation_{equation_text[:30]}",
            "entity_type": "equation",
            "summary": equation_text,
        }

    prompt = EQUATION_ANALYSIS_PROMPT.format(
        equation_text=equation_text,
        equation_format=equation_format,
        context=context or "None",
    )

    try:
        response = await llm_func(prompt, EQUATION_ANALYSIS_SYSTEM)
        parsed = robust_json_parse(response)
        description = parsed.get("detailed_description", "")
        entity_info = parsed.get("entity_info", {})

        if not entity_info.get("entity_name"):
            entity_info["entity_name"] = f"equation_{equation_text[:30]}"
        if not entity_info.get("entity_type"):
            entity_info["entity_type"] = "equation"

        return description, entity_info

    except Exception as e:
        log.error(f"Equation analysis failed: {e}")
        return equation_text, {
            "entity_name": f"equation_{equation_text[:30]}",
            "entity_type": "equation",
            "summary": equation_text,
        }
