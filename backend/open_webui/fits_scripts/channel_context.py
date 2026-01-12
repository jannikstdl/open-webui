# FI-TS_custom 2026-01-12: Channel LLM context building with token limits
import tiktoken
from typing import Optional, List, Dict, Any
from open_webui.models.messages import MessageModel
from open_webui.models.users import Users
from open_webui.models.files import Files
from open_webui.utils.files import get_image_base64_from_file_id
from open_webui.utils.channels import replace_mentions
from sqlalchemy.orm import Session


def estimate_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """
    Estimate token count using tiktoken.
    Falls back to character-based estimation if tiktoken fails.

    Args:
        text: The text to count tokens for
        encoding_name: The tiktoken encoding to use (default: cl100k_base for GPT-4)

    Returns:
        Estimated token count
    """
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(text) // 4


def build_channel_context(
    messages: List[MessageModel],
    max_messages: int,
    max_tokens: int,
    models_dict: Dict[str, Any],
    db: Session,
) -> tuple[List[str], List[str]]:
    """
    Build context from channel messages respecting both message count and token limits.

    Args:
        messages: List of MessageModel objects in chronological order
        max_messages: Maximum number of messages to include (0 = no limit)
        max_tokens: Maximum token count (0 = no limit)
        models_dict: Dictionary mapping model IDs to model info
        db: Database session for user lookups

    Returns:
        tuple: (thread_history, images)
            - thread_history: List of formatted message strings
            - images: List of image URLs/base64 data
    """
    thread_history = []
    images = []
    message_users = {}
    total_tokens = 0
    messages_added = 0

    for message in messages:
        # Check message count limit (0 = no limit)
        if max_messages > 0 and messages_added >= max_messages:
            break

        # Get user info (cache for efficiency)
        message_user = None
        if message.user_id not in message_users:
            message_user = Users.get_user_by_id(message.user_id, db=db)
            message_users[message.user_id] = message_user
        else:
            message_user = message_users[message.user_id]

        # Determine username
        if message.meta and message.meta.get("model_id", None):
            # Message sent by a model
            message_model_id = message.meta.get("model_id")
            message_model = models_dict.get(message_model_id, None)
            username = (
                message_model.get("name", message_model_id)
                if message_model
                else message_model_id
            )
        else:
            username = message_user.name if message_user else "Unknown"

        # FI-TS_custom 2026-01-12: Indicate thread messages
        prefix = "[Thread] " if message.parent_id else ""

        # Format message
        formatted_message = f"{prefix}{username}: {replace_mentions(message.content)}"

        # Check token limit (0 = no limit)
        if max_tokens > 0:
            message_tokens = estimate_tokens(formatted_message)
            if total_tokens + message_tokens > max_tokens:
                # Stop adding messages if we exceed token limit
                break
            total_tokens += message_tokens

        thread_history.append(formatted_message)
        messages_added += 1

        # FI-TS_custom 2026-01-12: Extract files (images and text files) from messages within context window
        message_files = message.data.get("files", []) if message.data else []
        for file in message_files:
            if file.get("type", "") == "image":
                images.append(file.get("url", ""))
            elif file.get("content_type", "").startswith("image/"):
                image = get_image_base64_from_file_id(file.get("id", ""))
                if image:
                    images.append(image)
            else:
                # FI-TS_custom 2026-01-12: Handle non-image files (text, code, etc.)
                file_id = file.get("id", "")
                if file_id:
                    try:
                        file_obj = Files.get_file_by_id(file_id, db=db)
                        if file_obj and file_obj.data:
                            file_content = file_obj.data.get("content", "")
                            if file_content:
                                # Add file content to thread history with clear formatting
                                file_name = file.get("filename", file_obj.filename)
                                file_context = f"[File: {file_name}]\n```\n{file_content}\n```"

                                # Check token limit for file content
                                if max_tokens > 0:
                                    file_tokens = estimate_tokens(file_context)
                                    if total_tokens + file_tokens > max_tokens:
                                        # Truncate file content if it exceeds token limit
                                        available_tokens = max_tokens - total_tokens
                                        if available_tokens > 100:  # Only add if at least 100 tokens available
                                            # Rough truncation (could be improved)
                                            max_chars = available_tokens * 4
                                            truncated_content = file_content[:max_chars] + "\n... (truncated)"
                                            file_context = f"[File: {file_name}]\n```\n{truncated_content}\n```"
                                            file_tokens = estimate_tokens(file_context)
                                            total_tokens += file_tokens
                                            thread_history.append(file_context)
                                        break  # Stop adding more content
                                    else:
                                        total_tokens += file_tokens
                                        thread_history.append(file_context)
                                else:
                                    # No token limit, add file content
                                    thread_history.append(file_context)
                    except Exception as e:
                        # Silently skip files that can't be loaded
                        pass

    return thread_history, images
