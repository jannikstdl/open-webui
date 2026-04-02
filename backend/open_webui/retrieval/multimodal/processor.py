"""
Multimodal content processing pipeline.

Separates structured document content into text and multimodal items,
routes each to the appropriate analyzer, and produces chunks with metadata.
"""

import base64
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from open_webui.retrieval.multimodal.analyzers import (
    analyze_equation,
    analyze_image,
    analyze_table,
)
from open_webui.retrieval.multimodal.prompts import (
    EQUATION_CHUNK_TEMPLATE,
    IMAGE_CHUNK_TEMPLATE,
    TABLE_CHUNK_TEMPLATE,
)

log = logging.getLogger(__name__)


@dataclass
class ExtractedImage:
    data: bytes  # raw image bytes
    filename: str
    caption: str = ""
    footnotes: str = ""
    page_idx: int = 0
    context: str = ""  # surrounding text


@dataclass
class ExtractedTable:
    body: str  # markdown/html table content
    caption: str = ""
    footnotes: str = ""
    page_idx: int = 0
    context: str = ""


@dataclass
class ExtractedEquation:
    text: str  # LaTeX or text representation
    format: str = "latex"
    page_idx: int = 0
    context: str = ""


@dataclass
class StructuredContent:
    """Result of parsing a document into structured parts."""

    text_blocks: List[Dict[str, Any]] = field(default_factory=list)
    images: List[ExtractedImage] = field(default_factory=list)
    tables: List[ExtractedTable] = field(default_factory=list)
    equations: List[ExtractedEquation] = field(default_factory=list)


@dataclass
class ProcessedChunk:
    """A chunk ready for VectorDB insertion, with optional multimodal metadata."""

    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


def separate_content(
    content_list: List[Dict[str, Any]],
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Separate text content from multimodal content.
    Args:
        content_list: MinerU/Docling-style content list with type field

    Returns:
        (text_content, multimodal_items)
    """
    text_parts = []
    multimodal_items = []

    for item in content_list:
        content_type = item.get("type", "text")

        if content_type == "text":
            text = item.get("text", "")
            if text.strip():
                text_parts.append(text)
        else:
            multimodal_items.append(item)

    text_content = "\n\n".join(text_parts)

    log.info(
        f"Content separation: {len(text_content)} chars text, "
        f"{len(multimodal_items)} multimodal items"
    )

    return text_content, multimodal_items


def get_surrounding_context(
    content_list: List[Dict[str, Any]],
    current_idx: int,
    window: int = 1,
    max_chars: int = 2000,
) -> str:
    """Extract surrounding text context for a multimodal item."""
    context_parts = []
    current_page = content_list[current_idx].get("page_idx", 0)

    for i, item in enumerate(content_list):
        if i == current_idx:
            continue
        if item.get("type") != "text":
            continue

        item_page = item.get("page_idx", 0)
        if abs(item_page - current_page) <= window:
            text = item.get("text", "").strip()
            if text:
                context_parts.append(text)

    context = "\n".join(context_parts)
    if len(context) > max_chars:
        context = context[:max_chars] + "..."
    return context


async def process_multimodal_items(
    content_list: List[Dict[str, Any]],
    multimodal_items: List[Dict[str, Any]],
    collection_name: str,
    storage_provider: Any,
    vlm_func: Optional[Callable] = None,
    llm_func: Optional[Callable] = None,
    enable_images: bool = True,
    enable_tables: bool = True,
    enable_equations: bool = False,
) -> List[ProcessedChunk]:
    """
    Process multimodal items: analyze with VLM/LLM, store originals, create chunks.

    Args:
        content_list: Full content list (for context extraction)
        multimodal_items: Items to process
        collection_name: Knowledge base collection name
        storage_provider: Open WebUI StorageProvider for image storage
        vlm_func: Vision LLM function
        llm_func: Text LLM function
        enable_images/tables/equations: Feature toggles

    Returns:
        List of ProcessedChunk ready for VectorDB insertion
    """
    chunks = []

    for item in multimodal_items:
        content_type = item.get("type", "unknown")
        page_idx = item.get("page_idx", 0)

        # Find index in original content_list for context
        item_idx = 0
        for i, ci in enumerate(content_list):
            if ci is item:
                item_idx = i
                break

        context = get_surrounding_context(content_list, item_idx)

        try:
            if content_type == "image" and enable_images:
                chunk = await _process_image_item(
                    item, context, collection_name, storage_provider, vlm_func, llm_func
                )
                if chunk:
                    chunks.append(chunk)

            elif content_type == "table" and enable_tables:
                chunk = await _process_table_item(item, context, llm_func)
                if chunk:
                    chunks.append(chunk)

            elif content_type == "equation" and enable_equations:
                chunk = await _process_equation_item(item, context, llm_func)
                if chunk:
                    chunks.append(chunk)

        except Exception as e:
            log.error(f"Failed to process {content_type} item: {e}")
            continue

    log.info(f"Processed {len(chunks)} multimodal chunks")
    return chunks


async def _process_image_item(
    item: Dict[str, Any],
    context: str,
    collection_name: str,
    storage_provider: Any,
    vlm_func: Optional[Callable],
    llm_func: Optional[Callable],
) -> Optional[ProcessedChunk]:
    """Process a single image item."""
    img_path = item.get("img_path", "")
    captions_list = item.get("image_caption", item.get("img_caption", []))
    footnotes_list = item.get("image_footnote", item.get("img_footnote", []))

    captions = ", ".join(captions_list) if isinstance(captions_list, list) else str(captions_list)
    footnotes = ", ".join(footnotes_list) if isinstance(footnotes_list, list) else str(footnotes_list)

    # Load and encode image
    image_data = None
    stored_path = ""

    if img_path and Path(img_path).exists():
        try:
            img_bytes = Path(img_path).read_bytes()
            image_data = base64.b64encode(img_bytes).decode("utf-8")

            # Store original in Open WebUI's storage
            filename = Path(img_path).name
            storage_path = f"{collection_name}/images/{filename}"
            _, stored_path = storage_provider.upload_file(
                open(img_path, "rb"), storage_path
            )
        except Exception as e:
            log.warning(f"Failed to load/store image {img_path}: {e}")

    # Analyze with VLM/LLM
    description, entity_info = await analyze_image(
        image_data=image_data,
        captions=captions,
        footnotes=footnotes,
        context=context,
        vlm_func=vlm_func,
        llm_func=llm_func,
    )

    # Create chunk with image_path in metadata
    chunk_content = IMAGE_CHUNK_TEMPLATE.format(
        image_path=stored_path or img_path,
        captions=captions or "None",
        footnotes=footnotes or "None",
        description=description,
    )

    return ProcessedChunk(
        content=chunk_content,
        metadata={
            "type": "image",
            "image_path": stored_path or img_path,
            "entity_name": entity_info.get("entity_name", ""),
            "entity_type": "image",
            "entity_description": entity_info.get("summary", ""),
        },
    )


async def _process_table_item(
    item: Dict[str, Any],
    context: str,
    llm_func: Optional[Callable],
) -> Optional[ProcessedChunk]:
    """Process a single table item."""
    body = item.get("table_body", "")
    caption_list = item.get("table_caption", [])
    footnote_list = item.get("table_footnote", [])

    caption = ", ".join(caption_list) if isinstance(caption_list, list) else str(caption_list)
    footnotes = ", ".join(footnote_list) if isinstance(footnote_list, list) else str(footnote_list)

    description, entity_info = await analyze_table(
        body=body,
        caption=caption,
        footnotes=footnotes,
        context=context,
        llm_func=llm_func,
    )

    chunk_content = TABLE_CHUNK_TEMPLATE.format(
        caption=caption or "None",
        body=body,
        footnotes=footnotes or "None",
        description=description,
    )

    return ProcessedChunk(
        content=chunk_content,
        metadata={
            "type": "table",
            "entity_name": entity_info.get("entity_name", ""),
            "entity_type": "table",
            "entity_description": entity_info.get("summary", ""),
        },
    )


async def _process_equation_item(
    item: Dict[str, Any],
    context: str,
    llm_func: Optional[Callable],
) -> Optional[ProcessedChunk]:
    """Process a single equation item."""
    equation_text = item.get("text", "")
    equation_format = item.get("text_format", "latex")

    description, entity_info = await analyze_equation(
        equation_text=equation_text,
        equation_format=equation_format,
        context=context,
        llm_func=llm_func,
    )

    chunk_content = EQUATION_CHUNK_TEMPLATE.format(
        equation_text=equation_text,
        equation_format=equation_format,
        description=description,
    )

    return ProcessedChunk(
        content=chunk_content,
        metadata={
            "type": "equation",
            "entity_name": entity_info.get("entity_name", ""),
            "entity_type": "equation",
            "entity_description": entity_info.get("summary", ""),
        },
    )
