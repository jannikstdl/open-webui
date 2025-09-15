from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from fastapi.responses import JSONResponse, RedirectResponse

from pydantic import BaseModel
from typing import Optional
import logging
import re

from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.task import (
    title_generation_template,
    follow_up_generation_template,
    query_generation_template,
    image_prompt_generation_template,
    autocomplete_generation_template,
    tags_generation_template,
    emoji_generation_template,
    moa_response_generation_template,
)
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.constants import TASKS

from open_webui.routers.pipelines import process_pipeline_inlet_filter

from open_webui.utils.task import get_task_model_id
from open_webui.models.knowledge import Knowledges
from open_webui.models.files import Files

from open_webui.config import (
    DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_FOLLOW_UP_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_AUTO_WEB_SEARCH_DECISION_PROMPT_TEMPLATE,
    DEFAULT_AUTO_FILE_SEARCH_DECISION_PROMPT_TEMPLATE,
    DEFAULT_FILE_CONTENT_SUMMARY_PROMPT_TEMPLATE,
    DEFAULT_RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE,
)
from open_webui.env import SRC_LOG_LEVELS


log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


##################################
#
# Task Endpoints
#
##################################


@router.get("/config")
async def get_task_config(request: Request, user=Depends(get_verified_user)):
    return {
        "TASK_MODEL": request.app.state.config.TASK_MODEL,
        "TASK_MODEL_EXTERNAL": request.app.state.config.TASK_MODEL_EXTERNAL,
        "TITLE_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE,
        "IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE": request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_AUTOCOMPLETE_GENERATION": request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION,
        "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH": request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,
        "TAGS_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        "FOLLOW_UP_GENERATION_PROMPT_TEMPLATE": request.app.state.config.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_FOLLOW_UP_GENERATION": request.app.state.config.ENABLE_FOLLOW_UP_GENERATION,
        "ENABLE_TAGS_GENERATION": request.app.state.config.ENABLE_TAGS_GENERATION,
        "ENABLE_TITLE_GENERATION": request.app.state.config.ENABLE_TITLE_GENERATION,
        "ENABLE_SEARCH_QUERY_GENERATION": request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION,
        "ENABLE_RETRIEVAL_QUERY_GENERATION": request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION,
        "QUERY_GENERATION_PROMPT_TEMPLATE": request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE,
        "WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE": request.app.state.config.WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE,
        "RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE": request.app.state.config.RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE,
        "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE": request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    }


class TaskConfigForm(BaseModel):
    TASK_MODEL: Optional[str]
    TASK_MODEL_EXTERNAL: Optional[str]
    ENABLE_TITLE_GENERATION: bool
    TITLE_GENERATION_PROMPT_TEMPLATE: str
    IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_AUTOCOMPLETE_GENERATION: bool
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH: int
    TAGS_GENERATION_PROMPT_TEMPLATE: str
    FOLLOW_UP_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_FOLLOW_UP_GENERATION: bool
    ENABLE_TAGS_GENERATION: bool
    ENABLE_SEARCH_QUERY_GENERATION: bool
    ENABLE_RETRIEVAL_QUERY_GENERATION: bool
    QUERY_GENERATION_PROMPT_TEMPLATE: str
    WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE: str
    RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE: str
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE: str


@router.post("/config/update")
async def update_task_config(
    request: Request, form_data: TaskConfigForm, user=Depends(get_admin_user)
):
    request.app.state.config.TASK_MODEL = form_data.TASK_MODEL
    request.app.state.config.TASK_MODEL_EXTERNAL = form_data.TASK_MODEL_EXTERNAL
    request.app.state.config.ENABLE_TITLE_GENERATION = form_data.ENABLE_TITLE_GENERATION
    request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE = (
        form_data.TITLE_GENERATION_PROMPT_TEMPLATE
    )

    request.app.state.config.ENABLE_FOLLOW_UP_GENERATION = (
        form_data.ENABLE_FOLLOW_UP_GENERATION
    )
    request.app.state.config.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE = (
        form_data.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE
    )

    request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE = (
        form_data.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE
    )

    request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION = (
        form_data.ENABLE_AUTOCOMPLETE_GENERATION
    )
    request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH = (
        form_data.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH
    )

    request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE = (
        form_data.TAGS_GENERATION_PROMPT_TEMPLATE
    )
    request.app.state.config.ENABLE_TAGS_GENERATION = form_data.ENABLE_TAGS_GENERATION
    request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION = (
        form_data.ENABLE_SEARCH_QUERY_GENERATION
    )
    request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION = (
        form_data.ENABLE_RETRIEVAL_QUERY_GENERATION
    )

    request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE = (
        form_data.QUERY_GENERATION_PROMPT_TEMPLATE
    )
    request.app.state.config.WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE = (
        form_data.WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE
    )
    request.app.state.config.RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE = (
        form_data.RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE
    )
    request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE = (
        form_data.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
    )

    return {
        "TASK_MODEL": request.app.state.config.TASK_MODEL,
        "TASK_MODEL_EXTERNAL": request.app.state.config.TASK_MODEL_EXTERNAL,
        "ENABLE_TITLE_GENERATION": request.app.state.config.ENABLE_TITLE_GENERATION,
        "TITLE_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE,
        "IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE": request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_AUTOCOMPLETE_GENERATION": request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION,
        "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH": request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH,
        "TAGS_GENERATION_PROMPT_TEMPLATE": request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_TAGS_GENERATION": request.app.state.config.ENABLE_TAGS_GENERATION,
        "ENABLE_FOLLOW_UP_GENERATION": request.app.state.config.ENABLE_FOLLOW_UP_GENERATION,
        "FOLLOW_UP_GENERATION_PROMPT_TEMPLATE": request.app.state.config.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE,
        "ENABLE_SEARCH_QUERY_GENERATION": request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION,
        "ENABLE_RETRIEVAL_QUERY_GENERATION": request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION,
        "QUERY_GENERATION_PROMPT_TEMPLATE": request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE,
        "WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE": request.app.state.config.WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE,
        "RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE": request.app.state.config.RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE,
        "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE": request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    }


@router.post("/title/completions")
async def generate_title(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    if not request.app.state.config.ENABLE_TITLE_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Title generation is disabled"},
        )

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating chat title using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE

    content = title_generation_template(template, form_data["messages"], user)

    max_tokens = (
        models[task_model_id].get("info", {}).get("params", {}).get("max_tokens", 1000)
    )

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        **(
            {"max_tokens": max_tokens}
            if models[task_model_id].get("owned_by") == "ollama"
            else {
                "max_completion_tokens": max_tokens,
            }
        ),
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.FOLLOW_UP_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        log.error("Exception occurred", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/follow_up/completions")
async def generate_follow_ups(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    if not request.app.state.config.ENABLE_FOLLOW_UP_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Follow-up generation is disabled"},
        )

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating chat title using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.FOLLOW_UP_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_FOLLOW_UP_GENERATION_PROMPT_TEMPLATE

    content = follow_up_generation_template(template, form_data["messages"], user)

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.FOLLOW_UP_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        log.error("Exception occurred", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/tags/completions")
async def generate_chat_tags(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    if not request.app.state.config.ENABLE_TAGS_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Tags generation is disabled"},
        )

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating chat tags using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE

    content = tags_generation_template(template, form_data["messages"], user)

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.TAGS_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        log.error(f"Error generating chat completion: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/image_prompt/completions")
async def generate_image_prompt(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating image prompt using model {task_model_id} for user {user.email} "
    )

    if request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE != "":
        template = request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE

    content = image_prompt_generation_template(template, form_data["messages"], user)

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.IMAGE_PROMPT_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        log.error("Exception occurred", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/queries/completions")
async def generate_queries(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    type = form_data.get("type")
    if type == "web_search":
        if not request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Search query generation is disabled",
            )
    elif type == "retrieval":
        if not request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Query generation is disabled",
            )

    if getattr(request.state, "cached_queries", None):
        log.info(f"Reusing cached queries: {request.state.cached_queries}")
        return request.state.cached_queries

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating {type} queries using model {task_model_id} for user {user.email}"
    )

    # Choose the appropriate template based on search type
    if type == "web_search":
        if (request.app.state.config.WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE).strip() != "":
            template = request.app.state.config.WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE
        else:
            template = DEFAULT_WEB_SEARCH_QUERY_GENERATION_PROMPT_TEMPLATE
    elif type == "retrieval":
        if (request.app.state.config.RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE).strip() != "":
            template = request.app.state.config.RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE
        else:
            template = DEFAULT_RETRIEVAL_QUERY_GENERATION_PROMPT_TEMPLATE
    else:
        # Fallback to generic template for backward compatibility
        if (request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE).strip() != "":
            template = request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE
        else:
            template = DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE

    content = query_generation_template(template, form_data["messages"], user)

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.QUERY_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )


# FI-TS_custom 12.09.2025: Add endpoint for automatic web search decision
@router.post("/agent/web_search_decision")
async def decide_web_search(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    """
    Decide if web search would be beneficial for the user's query using an LLM.
    Returns true if web search is recommended, false otherwise.
    """
    if not request.app.state.config.ENABLE_AUTO_WEB_SEARCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Automatic web search decision is disabled",
        )

    if not request.app.state.config.ENABLE_WEB_SEARCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Web search is disabled",
        )

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"deciding web search necessity using model {task_model_id} for user {user.email}"
    )

    # Get the user's query from messages
    user_message = form_data.get("prompt", "")
    if not user_message and "messages" in form_data:
        messages = form_data["messages"]
        for message in reversed(messages):
            if message.get("role") == "user":
                user_message = message.get("content", "")
                break

    if not user_message:
        return {"web_search_needed": False, "reason": "No user query found"}

    # Use the configured template or default
    if (request.app.state.config.AUTO_WEB_SEARCH_DECISION_PROMPT_TEMPLATE).strip() != "":
        template = request.app.state.config.AUTO_WEB_SEARCH_DECISION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_AUTO_WEB_SEARCH_DECISION_PROMPT_TEMPLATE

    # Replace the placeholders
    # Format messages for context
    messages_context = ""
    if "messages" in form_data and form_data["messages"]:
        for msg in form_data["messages"][-6:]:  # Last 6 messages for context
            role = msg.get("role", "")
            content_text = msg.get("content", "")
            if role and content_text:
                messages_context += f"{role}: {content_text}\n"
    
    content = template.replace("{{QUERY}}", user_message).replace("{{MESSAGES}}", messages_context)

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": "auto_web_search_decision",
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Extract the decision from the response
        decision_text = response["choices"][0]["message"]["content"].strip()
        
        try:
            # Try to parse as JSON
            import json
            decision_json = json.loads(decision_text)
            web_search_needed = decision_json.get("web_search_needed", False)
        except (json.JSONDecodeError, ValueError):
            # Fallback to text parsing if JSON fails
            decision_text_lower = decision_text.lower()
            web_search_needed = decision_text_lower == "true" or "true" in decision_text_lower
        
        return {
            "web_search_needed": web_search_needed,
            "query": user_message
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )


def extract_file_context_metadata(form_data: dict, model_info: dict = None, request: Request = None) -> str:
    """
    Extract file metadata for the auto file search decision.
    Returns formatted string with file name + type for single files,
    knowledge name + description for knowledge bases.
    FI-TS_custom 13.09.2025: Enhanced with content summaries for better search decisions.
    """
    # FI-TS_custom 12.09.2025: Extract metadata (name + type for files, name + description for knowledge)
    context_parts = []
    
    # Check for regular files
    files = form_data.get("files", [])
    regular_files = []
    knowledge_files = []
    
    for file_info in files:
        if file_info.get("type") == "collection" or file_info.get("collection_name") or file_info.get("collection_names"):
            knowledge_files.append(file_info)
        else:
            regular_files.append(file_info)
    
    # Process regular files
    if regular_files:
        context_parts.append("Attached Files:")
        for file_info in regular_files:
            file_name = file_info.get("name", "Unknown file")
            # Extract file extension for type
            file_type = file_name.split('.')[-1].lower() if '.' in file_name else "unknown"
            
            # FI-TS_custom 13.09.2025: Include content summary if available and enabled
            file_context = f"- {file_name} (type: {file_type})"
            
            # Try to get content summary if the feature is enabled and file has an ID
            if (request and 
                hasattr(request.app.state.config, 'ENABLE_FILE_CONTENT_SUMMARY') and 
                request.app.state.config.ENABLE_FILE_CONTENT_SUMMARY and 
                file_info.get("id")):
                
                try:
                    file_record = Files.get_file_by_id(file_info.get("id"))
                    if file_record and file_record.meta and file_record.meta.get("content_summary"):
                        content_summary = file_record.meta.get("content_summary")
                        # Summaries should now be ~500 chars, but add safety limit
                        if len(content_summary) > 600:
                            content_summary = content_summary[:600] + "..."
                        file_context += f"\n    Summary: {content_summary}"
                except Exception as e:
                    log.debug(f"Error getting content summary for file {file_info.get('id')}: {e}")
            
            context_parts.append(file_context)
    
    # Process knowledge bases from files
    if knowledge_files:
        context_parts.append("Attached Knowledge Collections:")
        for knowledge_info in knowledge_files:
            knowledge_name = knowledge_info.get("name", "Unknown collection")
            
            # Get knowledge description if we have an ID
            description = "No description"
            if knowledge_info.get("id"):  # Single collection
                knowledge_base = Knowledges.get_knowledge_by_id(knowledge_info.get("id"))
                if knowledge_base and knowledge_base.description:
                    description = knowledge_base.description
            elif knowledge_info.get("collection_names"):  # Multiple collections
                descriptions = []
                for collection_id in knowledge_info.get("collection_names", []):
                    knowledge_base = Knowledges.get_knowledge_by_id(collection_id)
                    if knowledge_base and knowledge_base.description:
                        descriptions.append(f"{knowledge_base.name}: {knowledge_base.description}")
                if descriptions:
                    description = "; ".join(descriptions)
                    
            context_parts.append(f"- {knowledge_name}: {description}")
    
    # Check for knowledge from model meta (model_knowledge)
    if model_info:
        model_knowledge = model_info.get("info", {}).get("meta", {}).get("knowledge", [])
        if model_knowledge:
            if not knowledge_files:  # Only add header if not already added
                context_parts.append("Attached Knowledge Collections:")
            for item in model_knowledge:
                knowledge_name = item.get("name", "Unknown collection")
                description = "No description"
                
                if item.get("collection_name"):  # Single collection
                    knowledge_base = Knowledges.get_knowledge_by_id(item.get("collection_name"))
                    if knowledge_base and knowledge_base.description:
                        description = knowledge_base.description
                elif item.get("collection_names"):  # Multiple collections
                    descriptions = []
                    for collection_id in item.get("collection_names", []):
                        knowledge_base = Knowledges.get_knowledge_by_id(collection_id)
                        if knowledge_base and knowledge_base.description:
                            descriptions.append(f"{knowledge_base.name}: {knowledge_base.description}")
                    if descriptions:
                        description = "; ".join(descriptions)
                        
                context_parts.append(f"- {knowledge_name}: {description}")
    
    if not context_parts:
        return "No files or knowledge collections attached."
    
    return "\n".join(context_parts)


@router.post("/agent/file_search_decision")
async def decide_file_search(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    """
    Decide if file search would be beneficial for the user's query using an LLM.
    Returns true if file search is recommended, false otherwise.
    """
    # FI-TS_custom 12.09.2025: Implement intelligent file search decision
    log.info(f"📁 Auto file search decision endpoint called by user {user.email}")
    log.info(f"📁 form_data keys: {form_data.keys()}")
    log.info(f"📁 ENABLE_AUTO_FILE_SEARCH config: {request.app.state.config.ENABLE_AUTO_FILE_SEARCH}")
    if not request.app.state.config.ENABLE_AUTO_FILE_SEARCH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Automatic file search decision is disabled",
        )

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    model_info = models[model_id]

    # Check if there are any files/collections to search
    files = form_data.get("files", [])
    model_knowledge = model_info.get("info", {}).get("meta", {}).get("knowledge", [])
    if not files and not model_knowledge:
        return {"file_search_needed": False, "reason": "No files or knowledge collections attached"}

    # Check if the user has a custom task model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"deciding file search necessity using model {task_model_id} for user {user.email}"
    )

    # Get the user's query from messages
    user_message = form_data.get("prompt", "")
    if not user_message and "messages" in form_data:
        messages = form_data["messages"]
        for message in reversed(messages):
            if message.get("role") == "user":
                user_message = message.get("content", "")
                break

    if not user_message:
        return {"file_search_needed": False, "reason": "No user query found"}

    # Use the configured template or default
    if (request.app.state.config.AUTO_FILE_SEARCH_DECISION_PROMPT_TEMPLATE).strip() != "":
        template = request.app.state.config.AUTO_FILE_SEARCH_DECISION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_AUTO_FILE_SEARCH_DECISION_PROMPT_TEMPLATE

    # Extract file context metadata
    file_context = extract_file_context_metadata(form_data, model_info, request)

    # Format messages for context
    messages_context = ""
    if "messages" in form_data and form_data["messages"]:
        for msg in form_data["messages"][-6:]:  # Last 6 messages for context
            role = msg.get("role", "")
            content_text = msg.get("content", "")
            if role and content_text:
                messages_context += f"{role}: {content_text}\n"
    
    # Replace the placeholders
    content = template.replace("{{QUERY}}", user_message).replace("{{MESSAGES}}", messages_context).replace("{{FILE_CONTEXT}}", file_context)
    
    # FI-TS_custom 13.09.2025: Debug logging - output complete prompt template
    log.info("📁 ===== AUTO FILE SEARCH DECISION - COMPLETE PROMPT =====")
    log.info(f"📁 USER: {user.email}")
    log.info(f"📁 QUERY: {user_message}")
    log.info(f"📁 FILE_CONTEXT: {file_context}")
    log.info("📁 ===== COMPLETE PROMPT SENT TO LLM =====")
    log.info(content)
    log.info("📁 ===== END OF PROMPT =====")
    

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": "auto_file_search_decision",
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Extract the decision from the response
        decision_text = response["choices"][0]["message"]["content"].strip()
        
        try:
            # Try to parse as JSON
            import json
            decision_json = json.loads(decision_text)
            file_search_needed = decision_json.get("file_search_needed", False)
        except (json.JSONDecodeError, ValueError):
            # Fallback to text parsing if JSON fails
            decision_text_lower = decision_text.lower()
            file_search_needed = decision_text_lower == "true" or "true" in decision_text_lower
        
        return {
            "file_search_needed": file_search_needed,
            "query": user_message,
            "file_context": file_context
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )


@router.post("/auto/completions")
async def generate_autocompletion(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    if not request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Autocompletion generation is disabled",
        )

    type = form_data.get("type")
    prompt = form_data.get("prompt")
    messages = form_data.get("messages")

    if request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH > 0:
        if (
            len(prompt)
            > request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Input prompt exceeds maximum length of {request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH}",
            )

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(
        f"generating autocompletion using model {task_model_id} for user {user.email}"
    )

    if (request.app.state.config.AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE).strip() != "":
        template = request.app.state.config.AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE
    else:
        template = DEFAULT_AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE

    content = autocomplete_generation_template(template, prompt, messages, type, user)

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.AUTOCOMPLETE_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        log.error(f"Error generating chat completion: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal error has occurred."},
        )


@router.post("/emoji/completions")
async def generate_emoji(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    # Check if the user has a custom task model
    # If the user has a custom task model, use that model
    task_model_id = get_task_model_id(
        model_id,
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    log.debug(f"generating emoji using model {task_model_id} for user {user.email} ")

    template = DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE

    content = emoji_generation_template(template, form_data["prompt"], user)

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        **(
            {"max_tokens": 4}
            if models[task_model_id].get("owned_by") == "ollama"
            else {
                "max_completion_tokens": 4,
            }
        ),
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": str(TASKS.EMOJI_GENERATION),
            "task_body": form_data,
            "chat_id": form_data.get("chat_id", None),
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )


@router.post("/moa/completions")
async def generate_moa_response(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):

    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        models = {
            request.state.model["id"]: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    model_id = form_data["model"]

    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )

    template = DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE

    content = moa_response_generation_template(
        template,
        form_data["prompt"],
        form_data["responses"],
    )

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": form_data.get("stream", False),
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "chat_id": form_data.get("chat_id", None),
            "task": str(TASKS.MOA_RESPONSE_GENERATION),
            "task_body": form_data,
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception as e:
        raise e

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )


# FI-TS_custom 12.09.2025: Content summary generation for files
@router.post("/file/content_summary")
async def generate_file_content_summary(
    request: Request, form_data: dict, user=Depends(get_verified_user)
):
    """
    Generate a content summary for a file based on its extracted text content.
    Returns a comprehensive summary to help with file search decision making.
    """
    if not request.app.state.config.ENABLE_FILE_CONTENT_SUMMARY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content summary generation is disabled",
        )

    log.info(f"📄 File content summary generation requested by user {user.email}")
    
    content = form_data.get("content", "")
    file_id = form_data.get("file_id", "")
    
    # If we have a file_id, verify access regardless of whether content is provided
    if file_id:
        # Check if user has access to this file
        if not Files.check_access_by_user_id(file_id, user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied",
            )
    
    # If content is not provided directly, try to get it from file_id
    if not content and file_id:
        try:
            # Get the file record to retrieve content
            file_record = Files.get_file_by_id(file_id)
            if not file_record:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found",
                )
            
            # Get content from file data
            if file_record.data and file_record.data.get("content"):
                content = file_record.data.get("content")
                log.info(f"📄 Retrieved content for file {file_id}, length: {len(content)} characters")
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="File does not contain extracted content",
                )
                
        except HTTPException:
            raise
        except Exception as e:
            log.error(f"Error retrieving file content: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error retrieving file content",
            )
    
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content or file_id is required for summary generation",
        )

    # Apply character limit for large files
    max_chars = request.app.state.config.FILE_CONTENT_SUMMARY_MAX_CHARS
    if len(content) > max_chars:
        log.info(f"📄 Content truncated from {len(content)} to {max_chars} characters")
        content = content[:max_chars] + "... [content truncated]"

    # Get or use default prompt template
    prompt_template = (
        request.app.state.config.FILE_CONTENT_SUMMARY_PROMPT_TEMPLATE
        or DEFAULT_FILE_CONTENT_SUMMARY_PROMPT_TEMPLATE
    )
    
    # Replace content in template
    content_prompt = prompt_template.replace("{{CONTENT}}", content)

    # Get task model - use a default model from available models
    models = request.app.state.MODELS
    if not models:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No models available",
        )
    
    # Use the first available model as default or configured task model
    if request.app.state.config.TASK_MODEL and request.app.state.config.TASK_MODEL in models:
        task_model_id = request.app.state.config.TASK_MODEL
    else:
        task_model_id = list(models.keys())[0]

    payload = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content_prompt}],
        "stream": False,
        "metadata": {
            **(request.state.metadata if hasattr(request.state, "metadata") else {}),
            "task": "file_content_summary_generation", 
            "task_body": {"content_length": len(content)},
        },
    }

    # Process the payload through the pipeline
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, request.app.state.MODELS)
    except Exception as e:
        raise e

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        
        # Extract the generated summary from the response
        content_summary = None
        if hasattr(response, 'choices') and len(response.choices) > 0:
            content_summary = response.choices[0].message.content
        elif hasattr(response, 'content'):
            content_summary = response.content
        elif isinstance(response, dict) and 'content' in response:
            content_summary = response['content']
        elif isinstance(response, dict) and 'choices' in response:
            if len(response['choices']) > 0 and 'message' in response['choices'][0]:
                content_summary = response['choices'][0]['message'].get('content')
        
        # If we have a file_id, store the summary in the file metadata
        if file_id and content_summary:
            try:
                Files.update_file_metadata_by_id(file_id, {"content_summary": content_summary})
                log.info(f"📄 Content summary stored for file {file_id}")
            except Exception as e:
                log.error(f"📄 Failed to store content summary for file {file_id}: {e}")
                # Don't fail the request if we can't store, just log the error
        
        # Return structured response with summary
        return {
            "content_summary": content_summary,
            "file_id": file_id if file_id else None
        }
            
    except Exception as e:
        log.error(f"📄 File content summary generation failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(e)},
        )
