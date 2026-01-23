import json
import logging
import base64
import io
import asyncio  # FI-TS_custom 2026-01-13: For timeout handling
from typing import Optional


from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import Response, StreamingResponse, FileResponse
from pydantic import BaseModel
from pydantic import field_validator

from open_webui.socket.main import (
    emit_to_users,
    enter_room_for_users,
    sio,
    get_user_ids_from_room,
)
from open_webui.models.users import (
    UserIdNameResponse,
    UserIdNameStatusResponse,
    UserListResponse,
    UserModelResponse,
    Users,
    UserNameResponse,
)

from open_webui.models.groups import Groups
from open_webui.models.channels import (
    Channels,
    ChannelModel,
    ChannelForm,
    ChannelResponse,
    CreateChannelForm,
    ChannelWebhookModel,
    ChannelWebhookForm,
)
from open_webui.models.messages import (
    Messages,
    MessageModel,
    MessageResponse,
    MessageWithReactionsResponse,
    MessageForm,
)


from open_webui.utils.files import get_image_base64_from_file_id

from open_webui.config import ENABLE_ADMIN_CHAT_ACCESS, ENABLE_ADMIN_EXPORT
from open_webui.constants import ERROR_MESSAGES
from open_webui.env import STATIC_DIR


from open_webui.utils.models import (
    get_all_models,
    get_filtered_models,
)
from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.middleware import strip_thinking_content
# FI-TS_custom 2026-01-13: Import for builtin tools
from open_webui.utils.tools import get_builtin_tools
# FI-TS_custom 2026-01-15: Import for web search citations
from open_webui.utils.middleware import (
    get_citation_source_from_tool_result,
    apply_source_context_to_messages,
)

from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import (
    has_access,
    get_users_with_access,
    get_permitted_group_and_user_ids,
    has_permission,
)
from open_webui.utils.webhook import post_webhook
from open_webui.utils.channels import extract_mentions, replace_mentions
from open_webui.fits_scripts.channel_context import build_channel_context, build_channel_context_with_reactions
from open_webui.internal.db import get_session
from sqlalchemy.orm import Session
from open_webui.models.models import Models

log = logging.getLogger(__name__)

router = APIRouter()

# FI-TS_custom 2026-01-15: Channel response lock to prevent multiple simultaneous responses
# Dictionary of channel_id -> asyncio.Lock
_channel_response_locks: dict[str, asyncio.Lock] = {}

def get_channel_response_lock(channel_id: str) -> asyncio.Lock:
    """Get or create a lock for a specific channel to prevent simultaneous model responses."""
    if channel_id not in _channel_response_locks:
        _channel_response_locks[channel_id] = asyncio.Lock()
    return _channel_response_locks[channel_id]


############################
# FI-TS_custom 2026-01-13: Tool calling support for auto-decision
############################


def has_native_tool_calling(model_id: str, db: Session) -> bool:
    """
    Check if model is configured for native tool/function calling.
    FI-TS_custom 2026-01-13: Check model's params.function_calling setting from database
    """
    model_info = Models.get_model_by_id(model_id, db=db)
    if not model_info or not model_info.params:
        return False

    model_params = model_info.params.model_dump() if hasattr(model_info.params, 'model_dump') else model_info.params
    return model_params.get("function_calling") == "native"


def has_vision(model_id: str, models_dict: dict) -> bool:
    """
    Check if model has vision capability enabled.
    FI-TS_custom 2026-01-23: Check model's meta.capabilities.vision
    """
    model = models_dict.get(model_id, {})
    return (
        model.get("info", {})
        .get("meta", {})
        .get("capabilities", {})
        .get("vision", False)
    )


# FI-TS_custom 2026-01-13: Tool definition for LLM decision-making
DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "decide_channel_action",
        "description": "Decide whether and how to participate in the channel conversation.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["silent", "reply", "react"],
                    "description": "Action: 'silent' (no response), 'reply' (send message), 'react' (emoji reaction)"
                },
                "emoji": {
                    "type": "string",
                    "description": "Emoji to react with (only when action is 'react')"
                }
            },
            "required": ["action"]
        }
    }
}


############################
# Channels Enabled Dependency
############################


def check_channels_access(request: Request):
    """Dependency to ensure channels are globally enabled."""
    if not request.app.state.config.ENABLE_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Channels are not enabled",
        )


############################
# GetChatList
############################


class ChannelListItemResponse(ChannelModel):
    user_ids: Optional[list[str]] = None  # 'dm' channels only
    users: Optional[list[UserIdNameStatusResponse]] = None  # 'dm' channels only

    last_message_at: Optional[int] = None  # timestamp in epoch (time_ns)
    unread_count: int = 0


@router.get("/", response_model=list[ChannelListItemResponse])
async def get_channels(
    request: Request,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    if user.role != "admin" and not has_permission(
        user.id, "features.channels", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    channels = Channels.get_channels_by_user_id(user.id, db=db)
    channel_list = []
    for channel in channels:
        last_message = Messages.get_last_message_by_channel_id(channel.id, db=db)
        last_message_at = last_message.created_at if last_message else None

        channel_member = Channels.get_member_by_channel_and_user_id(
            channel.id, user.id, db=db
        )
        unread_count = (
            Messages.get_unread_message_count(
                channel.id, user.id, channel_member.last_read_at, db=db
            )
            if channel_member
            else 0
        )

        user_ids = None
        users = None
        if channel.type == "dm":
            user_ids = [
                member.user_id
                for member in Channels.get_members_by_channel_id(channel.id, db=db)
            ]
            users = [
                UserIdNameStatusResponse(
                    **{
                        **user.model_dump(),
                        "is_active": Users.is_user_active(user.id, db=db),
                    }
                )
                for user in Users.get_users_by_user_ids(user_ids, db=db)
            ]

        channel_list.append(
            ChannelListItemResponse(
                **channel.model_dump(),
                user_ids=user_ids,
                users=users,
                last_message_at=last_message_at,
                unread_count=unread_count,
            )
        )

    return channel_list


@router.get("/list", response_model=list[ChannelModel])
async def get_all_channels(
    request: Request,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    if user.role == "admin":
        return Channels.get_channels(db=db)
    return Channels.get_channels_by_user_id(user.id, db=db)


############################
# GetDMChannelByUserId
############################


@router.get("/users/{user_id}", response_model=Optional[ChannelModel])
async def get_dm_channel_by_user_id(
    request: Request,
    user_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    if user.role != "admin" and not has_permission(
        user.id, "features.channels", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    try:
        existing_channel = Channels.get_dm_channel_by_user_ids(
            [user.id, user_id], db=db
        )
        if existing_channel:
            participant_ids = [
                member.user_id
                for member in Channels.get_members_by_channel_id(
                    existing_channel.id, db=db
                )
            ]

            await emit_to_users(
                "events:channel",
                {"data": {"type": "channel:created"}},
                participant_ids,
            )
            await enter_room_for_users(
                f"channel:{existing_channel.id}", participant_ids
            )

            Channels.update_member_active_status(
                existing_channel.id, user.id, True, db=db
            )
            return ChannelModel(**existing_channel.model_dump())

        channel = Channels.insert_new_channel(
            CreateChannelForm(
                type="dm",
                name="",
                user_ids=[user_id],
            ),
            user.id,
            db=db,
        )

        if channel:
            participant_ids = [
                member.user_id
                for member in Channels.get_members_by_channel_id(channel.id, db=db)
            ]

            await emit_to_users(
                "events:channel",
                {"data": {"type": "channel:created"}},
                participant_ids,
            )
            await enter_room_for_users(f"channel:{channel.id}", participant_ids)

            return ChannelModel(**channel.model_dump())
        else:
            raise Exception("Error creating channel")
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# CreateNewChannel
############################


@router.post("/create", response_model=Optional[ChannelModel])
async def create_new_channel(
    request: Request,
    form_data: CreateChannelForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    if user.role != "admin" and not has_permission(
        user.id, "features.channels", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    if form_data.type not in ["group", "dm"] and user.role != "admin":
        # Only admins can create standard channels (joined by default)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    try:
        if form_data.type == "dm":
            existing_channel = Channels.get_dm_channel_by_user_ids(
                [user.id, *form_data.user_ids], db=db
            )
            if existing_channel:
                participant_ids = [
                    member.user_id
                    for member in Channels.get_members_by_channel_id(
                        existing_channel.id, db=db
                    )
                ]
                await emit_to_users(
                    "events:channel",
                    {"data": {"type": "channel:created"}},
                    participant_ids,
                )
                await enter_room_for_users(
                    f"channel:{existing_channel.id}", participant_ids
                )

                Channels.update_member_active_status(
                    existing_channel.id, user.id, True, db=db
                )
                return ChannelModel(**existing_channel.model_dump())

        channel = Channels.insert_new_channel(form_data, user.id, db=db)

        if channel:
            participant_ids = [
                member.user_id
                for member in Channels.get_members_by_channel_id(channel.id, db=db)
            ]

            await emit_to_users(
                "events:channel",
                {"data": {"type": "channel:created"}},
                participant_ids,
            )
            await enter_room_for_users(f"channel:{channel.id}", participant_ids)

            return ChannelModel(**channel.model_dump())
        else:
            raise Exception("Error creating channel")
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetChannelById
############################


class ChannelFullResponse(ChannelResponse):
    user_ids: Optional[list[str]] = None  # 'group'/'dm' channels only
    users: Optional[list[UserIdNameStatusResponse]] = None  # 'group'/'dm' channels only

    last_read_at: Optional[int] = None  # timestamp in epoch (time_ns)
    unread_count: int = 0


@router.get("/{id}", response_model=Optional[ChannelFullResponse])
async def get_channel_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    user_ids = None
    users = None

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

        user_ids = [
            member.user_id
            for member in Channels.get_members_by_channel_id(channel.id, db=db)
        ]

        users = [
            UserIdNameStatusResponse(
                **{
                    **user.model_dump(),
                    "is_active": Users.is_user_active(user.id, db=db),
                }
            )
            for user in Users.get_users_by_user_ids(user_ids, db=db)
        ]

        channel_member = Channels.get_member_by_channel_and_user_id(
            channel.id, user.id, db=db
        )
        unread_count = Messages.get_unread_message_count(
            channel.id, user.id, channel_member.last_read_at if channel_member else None
        )

        return ChannelFullResponse(
            **{
                **channel.model_dump(),
                "user_ids": user_ids,
                "users": users,
                "is_manager": Channels.is_user_channel_manager(
                    channel.id, user.id, db=db
                ),
                "write_access": True,
                "user_count": len(user_ids),
                "last_read_at": channel_member.last_read_at if channel_member else None,
                "unread_count": unread_count,
            }
        )
    else:
        if user.role != "admin" and not has_access(
            user.id, type="read", access_control=channel.access_control, db=db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

        write_access = has_access(
            user.id,
            type="write",
            access_control=channel.access_control,
            strict=False,
            db=db,
        )

        user_count = len(get_users_with_access("read", channel.access_control))

        channel_member = Channels.get_member_by_channel_and_user_id(
            channel.id, user.id, db=db
        )
        unread_count = Messages.get_unread_message_count(
            channel.id, user.id, channel_member.last_read_at if channel_member else None
        )

        return ChannelFullResponse(
            **{
                **channel.model_dump(),
                "user_ids": user_ids,
                "users": users,
                "is_manager": Channels.is_user_channel_manager(
                    channel.id, user.id, db=db
                ),
                "write_access": write_access or user.role == "admin",
                "user_count": user_count,
                "last_read_at": channel_member.last_read_at if channel_member else None,
                "unread_count": unread_count,
            }
        )


############################
# GetChannelMembersById
############################


PAGE_ITEM_COUNT = 30


@router.get("/{id}/members", response_model=UserListResponse)
async def get_channel_members_by_id(
    request: Request,
    id: str,
    query: Optional[str] = None,
    order_by: Optional[str] = None,
    direction: Optional[str] = None,
    page: Optional[int] = 1,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)

    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    limit = PAGE_ITEM_COUNT

    page = max(1, page)
    skip = (page - 1) * limit

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    if channel.type == "dm":
        user_ids = [
            member.user_id
            for member in Channels.get_members_by_channel_id(channel.id, db=db)
        ]
        users = Users.get_users_by_user_ids(user_ids, db=db)
        total = len(users)

        return {
            "users": [
                UserModelResponse(
                    **user.model_dump(), is_active=Users.is_user_active(user.id, db=db)
                )
                for user in users
            ],
            "total": total,
        }
    else:
        filter = {}

        if query:
            filter["query"] = query
        if order_by:
            filter["order_by"] = order_by
        if direction:
            filter["direction"] = direction

        if channel.type == "group":
            filter["channel_id"] = channel.id
        else:
            filter["roles"] = ["!pending"]
            permitted_ids = get_permitted_group_and_user_ids(
                "read", channel.access_control
            )
            if permitted_ids:
                filter["user_ids"] = permitted_ids.get("user_ids")
                filter["group_ids"] = permitted_ids.get("group_ids")

        result = Users.get_users(filter=filter, skip=skip, limit=limit, db=db)

        users = result["users"]
        total = result["total"]

        return {
            "users": [
                UserModelResponse(
                    **user.model_dump(), is_active=Users.is_user_active(user.id, db=db)
                )
                for user in users
            ],
            "total": total,
        }


#################################################
# UpdateIsActiveMemberByIdAndUserId
#################################################


class UpdateActiveMemberForm(BaseModel):
    is_active: bool


@router.post("/{id}/members/active", response_model=bool)
async def update_is_active_member_by_id_and_user_id(
    request: Request,
    id: str,
    form_data: UpdateActiveMemberForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if not Channels.is_user_channel_member(channel.id, user.id, db=db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    Channels.update_member_active_status(
        channel.id, user.id, form_data.is_active, db=db
    )
    return True


#################################################
# AddMembersById
#################################################


class UpdateMembersForm(BaseModel):
    user_ids: list[str] = []
    group_ids: list[str] = []


@router.post("/{id}/update/members/add")
async def add_members_by_id(
    request: Request,
    id: str,
    form_data: UpdateMembersForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    if user.role != "admin" and not has_permission(
        user.id, "features.channels", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
        )

    try:
        memberships = Channels.add_members_to_channel(
            channel.id, user.id, form_data.user_ids, form_data.group_ids, db=db
        )

        return memberships
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


#################################################
#
#################################################


class RemoveMembersForm(BaseModel):
    user_ids: list[str] = []


@router.post("/{id}/update/members/remove")
async def remove_members_by_id(
    request: Request,
    id: str,
    form_data: RemoveMembersForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    if user.role != "admin" and not has_permission(
        user.id, "features.channels", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
        )

    try:
        deleted = Channels.remove_members_from_channel(
            channel.id, form_data.user_ids, db=db
        )

        return deleted
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# UpdateChannelById
############################


@router.post("/{id}/update", response_model=Optional[ChannelModel])
async def update_channel_by_id(
    request: Request,
    id: str,
    form_data: ChannelForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    if user.role != "admin" and not has_permission(
        user.id, "features.channels", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
        )

    try:
        channel = Channels.update_channel_by_id(id, form_data, db=db)
        return ChannelModel(**channel.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# DeleteChannelById
############################


@router.delete("/{id}/delete", response_model=bool)
async def delete_channel_by_id(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    if user.role != "admin" and not has_permission(
        user.id, "features.channels", request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.UNAUTHORIZED,
        )

    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.user_id != user.id and user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
        )

    try:
        Channels.delete_channel_by_id(id, db=db)
        return True
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetChannelMessages
############################


class MessageUserResponse(MessageResponse):
    data: bool | None = None

    @field_validator("data", mode="before")
    def convert_data_to_bool(cls, v):
        # No data or not a dict → False
        if not isinstance(v, dict):
            return False

        # True if ANY value in the dict is non-empty
        return any(bool(val) for val in v.values())


@router.get("/{id}/messages", response_model=list[MessageUserResponse])
async def get_channel_messages(
    request: Request,
    id: str,
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if user.role != "admin" and not has_access(
            user.id, type="read", access_control=channel.access_control, db=db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

        channel_member = Channels.join_channel(
            id, user.id, db=db
        )  # Ensure user is a member of the channel

    message_list = Messages.get_messages_by_channel_id(id, skip, limit, db=db)

    if not message_list:
        return []

    # Batch fetch all users in a single query (fixes N+1 problem)
    user_ids = list(set(m.user_id for m in message_list))
    users = {u.id: u for u in Users.get_users_by_user_ids(user_ids, db=db)}

    messages = []
    for message in message_list:
        thread_replies = Messages.get_thread_replies_by_message_id(message.id, db=db)
        latest_thread_reply_at = (
            thread_replies[0].created_at if thread_replies else None
        )

        # Use message.user if present (for webhooks), otherwise look up by user_id
        user_info = message.user
        if user_info is None and message.user_id in users:
            user_info = UserNameResponse(**users[message.user_id].model_dump())

        messages.append(
            MessageUserResponse(
                **{
                    **message.model_dump(),
                    "reply_count": len(thread_replies),
                    "latest_reply_at": latest_thread_reply_at,
                    "reactions": Messages.get_reactions_by_message_id(
                        message.id, db=db
                    ),
                    "user": user_info,
                }
            )
        )

    return messages


############################
# GetPinnedChannelMessages
############################

PAGE_ITEM_COUNT_PINNED = 20


@router.get("/{id}/messages/pinned", response_model=list[MessageWithReactionsResponse])
async def get_pinned_channel_messages(
    request: Request,
    id: str,
    page: int = 1,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if user.role != "admin" and not has_access(
            user.id, type="read", access_control=channel.access_control, db=db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    page = max(1, page)
    skip = (page - 1) * PAGE_ITEM_COUNT_PINNED
    limit = PAGE_ITEM_COUNT_PINNED

    message_list = Messages.get_pinned_messages_by_channel_id(id, skip, limit, db=db)

    if not message_list:
        return []

    # Batch fetch all users in a single query (fixes N+1 problem)
    user_ids = list(set(m.user_id for m in message_list))
    users = {u.id: u for u in Users.get_users_by_user_ids(user_ids, db=db)}

    messages = []
    for message in message_list:
        # Check for webhook identity in meta
        webhook_info = message.meta.get("webhook") if message.meta else None
        if webhook_info:
            user_info = UserNameResponse(
                id=webhook_info.get("id"),
                name=webhook_info.get("name"),
                role="webhook",
            )
        elif message.user_id in users:
            user_info = UserNameResponse(**users[message.user_id].model_dump())
        else:
            user_info = None

        messages.append(
            MessageWithReactionsResponse(
                **{
                    **message.model_dump(),
                    "reactions": Messages.get_reactions_by_message_id(
                        message.id, db=db
                    ),
                    "user": user_info,
                }
            )
        )

    return messages


############################
# PostNewMessage
############################


async def send_notification(
    name, webui_url, channel, message, active_user_ids, db=None
):
    users = get_users_with_access("read", channel.access_control)

    for user in users:
        if (user.id not in active_user_ids) and Channels.is_user_channel_member(
            channel.id, user.id, db=db
        ):
            if user.settings:
                webhook_url = user.settings.ui.get("notifications", {}).get(
                    "webhook_url", None
                )
                if webhook_url:
                    await post_webhook(
                        name,
                        webhook_url,
                        f"#{channel.name} - {webui_url}/channels/{channel.id}\n\n{message.content}",
                        {
                            "action": "channel",
                            "message": message.content,
                            "title": channel.name,
                            "url": f"{webui_url}/channels/{channel.id}",
                        },
                    )

    return True


# FI-TS_custom 2026-01-13: Add emoji reactions from model auto-decision
async def add_message_reaction(request, channel_id, message_id, emoji, model_id, model_name, user, db):
    """Add emoji reaction to a message (from model auto-decision)."""
    try:
        # Use the proper Messages method to add reaction
        # Use model_id as the "user" identifier so frontend doesn't show "You"
        # Format: "model:model_id" to distinguish from real users
        model_user_id = f"model:{model_id}"
        Messages.add_reaction_to_message(message_id, model_user_id, emoji, db=db)

        # Get updated message
        message = Messages.get_message_by_id(message_id, db=db)
        if not message:
            return

        # Get channel for socket emission
        channel = Channels.get_channel_by_id(channel_id, db=db)
        if not channel:
            return

        # Emit socket event with model's identity (like webhooks do)
        await sio.emit(
            "events:channel",
            {
                "channel_id": channel_id,
                "message_id": message.id,
                "data": {
                    "type": "message:reaction:add",
                    "data": {
                        **message.model_dump(),
                        "name": emoji,
                    },
                },
                "user": {
                    "id": model_id,
                    "name": model_name,
                    "role": "model",
                },
                "channel": channel.model_dump(),
            },
            to=f"channel:{channel_id}",
        )
    except Exception as e:
        log.error(f"Failed to add reaction: {e}")
        log.exception(e)


# FI-TS_custom 2026-01-13: Auto-decision via tool calling
async def make_auto_decision(
    request, channel, message, model, user, db, response_model_name: str = None
) -> Optional[dict]:
    """
    Uses tool calling to let the model decide whether to respond.
    Returns: {"action": "silent|reply|react", "emoji": "..."}

    model: The TASK_MODEL used for making the decision
    response_model_name: The name of the CHANNEL_MODEL that will actually respond (used in prompt)
    """
    model_id = model.get("id")
    # FI-TS_custom 2026-01-15: Use response model name in prompt (the model users will see)
    model_name = response_model_name or model.get("name", model_id)

    # Get conversation history with reactions and replies
    # FI-TS_custom 2026-01-13: Safe int conversion for empty string values
    max_messages = int(request.app.state.config.CHANNEL_LLM_MAX_MESSAGES or 0) or 20
    max_tokens = int(request.app.state.config.CHANNEL_LLM_MAX_TOKENS or 0)

    all_messages = Messages.get_all_channel_messages_for_context(
        channel.id,
        limit=max_messages if max_messages > 0 else 0,
        db=db,
    )

    # Build context with reactions and reply information
    history, decision_images = build_channel_context_with_reactions(
        all_messages,
        max_messages,
        max_tokens,
        {model_id: model},
        db,
    )

    # FI-TS_custom 2026-01-23: Only include images if TASK_MODEL has vision capability
    if not has_vision(model_id, {model_id: model}):
        if decision_images:
            log.info(f"TASK_MODEL {model_id} does not have vision - converting {len(decision_images)} images to text placeholders")
            # Add image filenames as text to the context
            image_names = []
            for msg in all_messages:
                msg_files = msg.data.get("files", []) if msg.data else []
                for file in msg_files:
                    if file.get("type") == "image" or file.get("content_type", "").startswith("image/"):
                        filename = file.get("filename", "image")
                        image_names.append(filename)

            if image_names and history:
                # Append image info to the last message in history
                history[-1] += f" [Attached images: {', '.join(image_names)}]"
        decision_images = []

    history_str = "\n".join(history)

    # FI-TS_custom 2026-01-13: Include channel members for better context
    members = Channels.get_members_by_channel_id(channel.id, db=db)
    user_ids = [member.user_id for member in members]
    users = Users.get_users_by_user_ids(user_ids, db=db)
    member_names = [user.name for user in users]
    members_str = ", ".join(member_names)

    # FI-TS_custom 2026-01-15: Use configurable decision prompt
    decision_prompt_template = request.app.state.config.CHANNEL_DECISION_PROMPT or ""
    user_name = message.user.name if hasattr(message, 'user') else 'User'

    # Replace placeholders in the decision prompt
    system_prompt = decision_prompt_template.replace("{{MODEL_NAME}}", model_name)
    system_prompt = system_prompt.replace("{{MEMBERS}}", members_str)
    system_prompt = system_prompt.replace("{{HISTORY}}", history_str)
    system_prompt = system_prompt.replace("{{USER}}", user_name)
    system_prompt = system_prompt.replace("{{MESSAGE}}", message.content)

    # FI-TS_custom 2026-01-23: Add vision capability variable
    vision_str = "yes" if has_vision(model_id, {model_id: model}) else "no"
    system_prompt = system_prompt.replace("{{VISION_CAPABILITY}}", vision_str)

    try:
        # FI-TS_custom 2026-01-21: MiniMax requires user message, not just system message
        response = await generate_chat_completion(
            request,
            form_data={
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Decide: reply, react, or silent?"}
                ],
                "tools": [DECISION_TOOL],
                "tool_choice": {"type": "function", "function": {"name": "decide_channel_action"}},
                "stream": False,
                "max_tokens": 500,
                "temperature": 0.3,
            },
            user=user,
        )

        # FI-TS_custom 2026-01-21: Convert JSONResponse to dict
        if response and not isinstance(response, dict):
            if hasattr(response, 'body'):
                response = json.loads(response.body.decode('utf-8'))
            else:
                return None

        # FI-TS_custom 2026-01-21: Debug logging for auto-decision
        log.debug(f"Auto-decision response for {model_id}: {response}")

        if response and response.get("choices"):
            choice = response["choices"][0]
            tool_calls = choice.get("message", {}).get("tool_calls", [])

            # FI-TS_custom 2026-01-21: Debug logging for tool_calls
            log.debug(f"Auto-decision tool_calls: {tool_calls}")

            if tool_calls:
                tool_call = tool_calls[0]
                function_args = json.loads(tool_call["function"]["arguments"])

                return {
                    "action": function_args.get("action", "silent"),
                    "emoji": function_args.get("emoji")
                }
            else:
                # FI-TS_custom 2026-01-21: Fallback - parse action from content if model didn't use tool
                content = choice.get("message", {}).get("content", "")
                if content:
                    log.warning(f"Model returned content instead of tool call: {content[:200]}")
                    content_lower = content.lower()
                    if "reply" in content_lower:
                        return {"action": "reply"}
                    elif "react" in content_lower:
                        return {"action": "react", "emoji": None}
                # Default to silent if no actionable content found
                return {"action": "silent"}
    except Exception as e:
        log.error(f"Auto-decision failed for model {model_id}: {e}")
        return None

    return {"action": "silent"}


async def model_response_handler(request, channel, message, user, db=None):
    MODELS = {
        model["id"]: model
        for model in get_filtered_models(await get_all_models(request, user=user), user)
    }

    mentions = extract_mentions(message.content)
    message_content = replace_mentions(message.content)

    model_mentions = {}

    # check if the message is a reply to a message sent by a model
    if (
        message.reply_to_message
        and message.reply_to_message.meta
        and message.reply_to_message.meta.get("model_id", None)
    ):
        model_id = message.reply_to_message.meta.get("model_id", None)
        model_mentions[model_id] = {"id": model_id, "id_type": "M"}

    # check if any of the mentions are models
    for mention in mentions:
        if mention["id_type"] == "M" and mention["id"] not in model_mentions:
            model_mentions[mention["id"]] = mention

    # FI-TS_custom 2026-01-15: Auto-decision uses TASK_MODEL, response uses CHANNEL_MODEL
    if not model_mentions:
        task_model_id = request.app.state.config.TASK_MODEL
        channel_model_id = request.app.state.config.CHANNEL_MODEL

        # Need both TASK_MODEL (for decision) and CHANNEL_MODEL (for response)
        if task_model_id and task_model_id in MODELS and channel_model_id and channel_model_id in MODELS:
            # FI-TS_custom 2026-01-15: Use lock to prevent multiple simultaneous responses
            channel_lock = get_channel_response_lock(channel.id)

            # Try to acquire lock without blocking - if locked, model is already responding
            if channel_lock.locked():
                log.info(f"Channel {channel.id} is already processing a response, skipping auto-decision")
            else:
                log.info(f"Checking TASK_MODEL {task_model_id} for native tool calling...")
                if has_native_tool_calling(task_model_id, db):
                    log.info(f"TASK_MODEL {task_model_id} has native tool calling, making auto-decision...")
                    task_model = MODELS[task_model_id]
                    channel_model = MODELS[channel_model_id]

                    # Make auto-decision using TASK_MODEL, but use CHANNEL_MODEL's name in prompt
                    decision = await make_auto_decision(
                        request, channel, message, task_model, user, db,
                        response_model_name=channel_model.get("name", channel_model_id)
                    )
                    log.info(f"Auto-decision result: {decision}")

                    # If decision is to respond, use CHANNEL_MODEL for the actual response
                    if decision and decision["action"] != "silent":
                        model_mentions[channel_model_id] = {
                            "id": channel_model_id,
                            "id_type": "M",
                            "decision": decision
                        }
                else:
                    log.info(f"TASK_MODEL {task_model_id} does not have native tool calling enabled")

    if not model_mentions:
        return False

    for mention in model_mentions.values():
        model_id = mention["id"]
        model = MODELS.get(model_id, None)
        decision = mention.get("decision")  # None for @mentions

        if model:
            # FI-TS_custom 2026-01-13: Handle react action only - reply goes through normal flow
            if decision and decision["action"] == "react":
                emoji = decision.get("emoji", "👍")
                await add_message_reaction(
                    request, channel.id, message.id, emoji,
                    model_id, model.get("name", model_id), user, db
                )
                continue  # Skip text response

            # FI-TS_custom 2026-01-13: For 'reply' action, fall through to normal response generation
            response_message = None
            response_successful = False

            # FI-TS_custom 2026-01-15: Acquire channel lock to prevent simultaneous responses
            channel_lock = get_channel_response_lock(channel.id)
            if channel_lock.locked():
                log.info(f"Channel {channel.id} is already processing a response, skipping this request")
                continue

            await channel_lock.acquire()
            log.info(f"Acquired response lock for channel {channel.id}")

            try:
                # FI-TS_custom 2026-01-12: Get all channel messages with configurable limits
                # FI-TS_custom 2026-01-13: Safe int conversion for empty string values
                max_messages = int(request.app.state.config.CHANNEL_LLM_MAX_MESSAGES or 0)  # 0 = no limit
                max_tokens = int(request.app.state.config.CHANNEL_LLM_MAX_TOKENS or 0)      # 0 = no limit

                # Fetch messages with SQL LIMIT only if max_messages > 0
                all_messages = Messages.get_all_channel_messages_for_context(
                    channel.id,
                    limit=max_messages if max_messages > 0 else 0,  # 0 = fetch all
                    db=db,
                )

                # Build context with token limits
                # FI-TS_custom 2026-01-13: Use context with reactions so model can see them
                thread_history, images = build_channel_context_with_reactions(
                    all_messages,
                    max_messages,
                    max_tokens,
                    MODELS,
                    db,
                )

                # FI-TS_custom 2026-01-23: Only include images if model has vision capability
                if not has_vision(model_id, MODELS):
                    if images:
                        log.info(f"Model {model_id} does not have vision - converting {len(images)} images to text placeholders")
                        # Add image filenames as text to the context
                        image_names = []
                        for msg in all_messages:
                            msg_files = msg.data.get("files", []) if msg.data else []
                            for file in msg_files:
                                if file.get("type") == "image" or file.get("content_type", "").startswith("image/"):
                                    filename = file.get("filename", "image")
                                    image_names.append(filename)

                        if image_names and thread_history:
                            # Append image info to the last message in history
                            thread_history[-1] += f" [Attached images: {', '.join(image_names)}]"
                    images = []

                # FI-TS_custom 2026-01-13: Create empty message and emit for instant typing indicator
                # Frontend handles empty model messages as typing indicators (not visible messages)
                # FI-TS_custom 2026-01-13: Reply in same context (thread or main) as triggering message
                response_message, channel = await new_message_handler(
                    request,
                    channel.id,
                    MessageForm(
                        **{
                            "parent_id": message.parent_id if message.parent_id else None,
                            "content": "",
                            "data": {},
                            "meta": {
                                "model_id": model_id,
                                "model_name": model.get("name", model_id),
                                "done": False,
                            },
                        }
                    ),
                    user,
                    db,
                    # Emit immediately - frontend shows typing indicator, not empty message
                )

                # FI-TS_custom 2026-01-13: Include channel members for better context
                members = Channels.get_members_by_channel_id(channel.id, db=db)
                user_ids = [member.user_id for member in members]
                users = Users.get_users_by_user_ids(user_ids, db=db)
                member_names = [user.name for user in users]
                members_str = ", ".join(member_names)

                # FI-TS_custom 2026-01-15: Use configurable system prompt for channel model
                thread_history_string = "\n\n".join(thread_history)
                channel_system_prompt = request.app.state.config.CHANNEL_SYSTEM_PROMPT or ""
                channel_system_prompt = channel_system_prompt.replace("{{MODEL_NAME}}", model.get("name", model_id))

                # FI-TS_custom 2026-01-23: Add vision capability variable
                vision_str = "yes" if has_vision(model_id, MODELS) else "no"
                channel_system_prompt = channel_system_prompt.replace("{{VISION_CAPABILITY}}", vision_str)

                system_message = {
                    "role": "system",
                    "content": channel_system_prompt
                    + f"\n\nChannel members: {members_str}"
                    + (
                        f"\n\nConversation history:\n\n{thread_history_string}"
                        if thread_history
                        else ""
                    ),
                }

                content = f"{user.name if user else 'User'}: {message_content}"
                if images:
                    content = [
                        {
                            "type": "text",
                            "text": content,
                        },
                        *[
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image,
                                },
                            }
                            for image in images
                        ],
                    ]

                # FI-TS_custom 2026-01-13: Get builtin tools for channel model
                messages_list = [
                    system_message,
                    {"role": "user", "content": content},
                ]

                # FI-TS_custom 2026-01-15: Get builtin tools for channel model
                builtin_tools = {}
                tools_specs = []

                # Check if model supports native function calling
                model_supports_tools = has_native_tool_calling(model_id, db)

                if model_supports_tools:
                    try:
                        builtin_tools = get_builtin_tools(
                            request,
                            extra_params={
                                "__user__": user.model_dump() if user else {},
                                "__model__": model,
                                "__messages__": messages_list,
                                "__channel_id__": channel.id,
                            },
                            features={},
                            model=model,
                        )

                        # FI-TS_custom 2026-01-15: Web, channel search, and fetch_url tools for channel model
                        allowed_tool_names = [
                            "search_web",
                            "search_channel_messages",
                            "fetch_url",
                        ]

                        tools_specs = [
                            tool["spec"]
                            for name, tool in builtin_tools.items()
                            if name in allowed_tool_names
                        ]

                        if tools_specs:
                            log.info(f"Prepared {len(tools_specs)} builtin tools for model {model_id}")
                    except Exception as e:
                        log.error(f"Error getting builtin tools: {e}")
                        builtin_tools = {}
                        tools_specs = []

                # FI-TS_custom 2026-01-15: Build metadata with params.function_calling
                # This is REQUIRED for the middleware to recognize native tool calling
                # Without this, generate_chat_completion doesn't enable tool support
                metadata = {
                    "user_id": user.id if user else None,
                    "channel_id": channel.id,
                    "model": model,
                    "params": {
                        "function_calling": "native" if model_supports_tools else "default",
                    },
                }

                form_data = {
                    "model": model_id,
                    "messages": messages_list,
                    "stream": False,
                    "metadata": metadata,  # Include metadata for proper tool handling
                }

                # Add tools if available and model supports them
                if tools_specs and model_supports_tools:
                    # FI-TS_custom 2026-01-15: Wrap tools in OpenAI-standard format
                    form_data["tools"] = [
                        {"type": "function", "function": spec}
                        for spec in tools_specs
                    ]
                    log.info(f"Added {len(tools_specs)} tools to channel model request")

                # FI-TS_custom 2026-01-13: Add 5 minute timeout for model response
                try:
                    res = await asyncio.wait_for(
                        generate_chat_completion(
                            request,
                            form_data=form_data,
                            user=user,
                        ),
                        timeout=300  # 5 minutes
                    )
                except asyncio.TimeoutError:
                    log.error(f"Model response timed out after 5 minutes")
                    res = {"error": "Model response timed out after 5 minutes"}

                # FI-TS_custom 2026-01-15: Convert JSONResponse to dict for error handling
                if res and not isinstance(res, dict):
                    log.error(f"Received JSONResponse instead of dict from model API")
                    try:
                        # Try to extract error from JSONResponse
                        if hasattr(res, 'body'):
                            import json as json_lib
                            error_body = json_lib.loads(res.body.decode('utf-8'))
                            error_detail = error_body.get("error", {})
                            if isinstance(error_detail, dict):
                                res = {"error": error_detail.get("message", "Model returned error response")}
                            else:
                                res = {"error": str(error_detail)}
                        else:
                            res = {"error": "Model returned an error response"}
                    except Exception as e:
                        log.error(f"Failed to parse JSONResponse: {e}")
                        res = {"error": "Invalid response from model"}

                # FI-TS_custom 2026-01-15: Handle tool calls if model requested them
                # Also collect citation sources for web search results
                citation_sources = []

                if res and isinstance(res, dict) and res.get("choices", []) and len(res["choices"]) > 0 and builtin_tools:
                    tool_calls = res["choices"][0].get("message", {}).get("tool_calls", [])

                    if tool_calls:
                        log.info(f"Channel model requested {len(tool_calls)} tool calls")
                        max_iterations = 2
                        iteration = 0

                        while tool_calls and iteration < max_iterations:
                            iteration += 1

                            # Add assistant message with tool calls
                            messages_list.append(res["choices"][0]["message"])

                            # Execute each tool call
                            for tool_call in tool_calls:
                                function_name = tool_call.get("function", {}).get("name", "")
                                log.info(f"Executing tool: {function_name}")

                                try:
                                    # FI-TS_custom 2026-01-15: Parse tool arguments with debug logging
                                    raw_args = tool_call.get("function", {}).get("arguments", "{}")
                                    log.debug(f"Raw tool arguments for {function_name}: {raw_args[:200]}")

                                    try:
                                        function_args = json.loads(raw_args)
                                    except json.JSONDecodeError as json_err:
                                        log.error(f"Failed to parse tool arguments for {function_name}: {json_err}")
                                        log.error(f"Raw arguments were: {raw_args[:500]}")
                                        tool_result = json.dumps({"error": f"Invalid tool arguments: {json_err}"})
                                        # Add error result and continue to next tool
                                        messages_list.append({
                                            "role": "tool",
                                            "tool_call_id": tool_call.get("id", ""),
                                            "content": tool_result,
                                        })
                                        continue

                                    # Find and execute the tool
                                    if function_name in builtin_tools:
                                        tool_callable = builtin_tools[function_name]["callable"]

                                        # FI-TS_custom 2026-01-15: Emit tool status event before tool execution
                                        status_message = None
                                        if function_name == "search_web":
                                            status_message = "searching_web"
                                        elif function_name == "fetch_url":
                                            status_message = "searching_web"  # Same status as web search
                                        elif function_name == "search_channel_messages":
                                            status_message = "searching_channel"

                                        if status_message:
                                            await sio.emit(
                                                "events:channel",
                                                {
                                                    "channel_id": channel.id,
                                                    "message_id": message.parent_id,  # None for main channel, thread_id for threads
                                                    "data": {
                                                        "type": "model_status",
                                                        "data": {
                                                            "model_id": model_id,
                                                            "model_name": model.get("name", model_id),
                                                            "status": status_message,
                                                        }
                                                    },
                                                },
                                                to=f"channel:{channel.id}",
                                            )

                                        # Execute tool - callable already has context params bound
                                        if asyncio.iscoroutinefunction(tool_callable):
                                            tool_result = await tool_callable(**function_args)
                                        else:
                                            tool_result = tool_callable(**function_args)
                                        log.info(f"Tool {function_name} executed successfully")

                                        # FI-TS_custom 2026-01-15: Collect citations from search_web results
                                        if function_name == "search_web" and tool_result:
                                            try:
                                                tool_citations = get_citation_source_from_tool_result(
                                                    function_name,
                                                    function_args,
                                                    tool_result,
                                                    tool_call.get("id", "")
                                                )
                                                citation_sources.extend(tool_citations)
                                                log.info(f"Collected {len(tool_citations)} citation sources from {function_name}")
                                            except Exception as citation_err:
                                                log.error(f"Error collecting citations: {citation_err}")
                                    else:
                                        tool_result = json.dumps({"error": f"Tool {function_name} not found"})

                                except Exception as e:
                                    log.error(f"Tool execution error: {e}")
                                    tool_result = json.dumps({"error": str(e)})

                                # Ensure tool_result is a string
                                if not isinstance(tool_result, str):
                                    if isinstance(tool_result, (dict, list)):
                                        tool_result = json.dumps(tool_result)
                                    else:
                                        tool_result = str(tool_result)

                                # Add tool result to messages
                                messages_list.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.get("id", ""),
                                    "content": tool_result,
                                })

                            # Make another LLM call with tool results
                            form_data["messages"] = messages_list

                            # FI-TS_custom 2026-01-15: Add simple sources context (no verbose RAG template)
                            if citation_sources:
                                try:
                                    sources_context = "\n\n### Sources:\n"
                                    for i, source in enumerate(citation_sources, 1):
                                        source_info = source.get("source", {})
                                        name = source_info.get("name", "Unknown")
                                        metadata = source.get("metadata", [{}])
                                        url = metadata[0].get("source", "") if metadata else ""
                                        sources_context += f"[{i}] {name}"
                                        if url:
                                            sources_context += f" - {url}"
                                        sources_context += "\n"

                                    # Append to system message
                                    if form_data["messages"] and form_data["messages"][0]["role"] == "system":
                                        form_data["messages"][0]["content"] += sources_context
                                    log.info(f"Added {len(citation_sources)} sources to context")
                                except Exception as sources_err:
                                    log.error(f"Error adding sources context: {sources_err}")

                            try:
                                res = await asyncio.wait_for(
                                    generate_chat_completion(
                                        request,
                                        form_data=form_data,
                                        user=user,
                                    ),
                                    timeout=300
                                )

                                # Check for more tool calls
                                if res and isinstance(res, dict) and res.get("choices", []) and len(res["choices"]) > 0:
                                    tool_calls = res["choices"][0].get("message", {}).get("tool_calls", [])
                                else:
                                    break
                            except asyncio.TimeoutError:
                                log.error(f"Tool response timed out")
                                res = {"error": "Tool response timed out"}
                                break
                            except Exception as e:
                                log.error(f"Error in tool follow-up call: {e}")
                                res = {"error": str(e)}
                                break

                # FI-TS_custom 2026-01-13: Update message when response ready
                # Check if new messages arrived after trigger - if so, recreate at end with reply_to_id
                if res:
                    # Extract response content safely
                    if not isinstance(res, dict):
                        log.error(f"Unexpected response type after conversion: {type(res)}")
                        response_content = "Error: Invalid response from model"
                    elif res.get("choices") and len(res["choices"]) > 0:
                        # Safely extract content from response (ignore reasoning_content field)
                        message_obj = res["choices"][0].get("message", {})
                        response_content = message_obj.get("content")
                        # Handle case where model only made tool calls without final content
                        if not response_content:
                            response_content = "I processed your request but couldn't generate a response."
                        else:
                            # FI-TS_custom 2026-01-21: Strip inline thinking tags
                            response_content = strip_thinking_content(response_content)
                    elif res.get("error"):
                        error_msg = res["error"]
                        # Provide user-friendly error messages
                        if "does not support" in str(error_msg).lower() or "tool" in str(error_msg).lower():
                            response_content = "This model doesn't support the advanced features I tried to use. Please select a different model in Admin Settings."
                        else:
                            response_content = f"Error: {error_msg}"
                    else:
                        response_content = "Error: No response from model"

                    # Check if messages arrived after the trigger message
                    latest_message = Messages.get_last_message_by_channel_id(channel.id, db=db)
                    messages_arrived_after_trigger = (
                        latest_message and
                        latest_message.id != response_message.id and
                        latest_message.created_at > message.created_at
                    )

                    if messages_arrived_after_trigger:
                        # Delete empty message and create new one at end with reply_to_id
                        Messages.delete_message_by_id(response_message.id, db=db)

                        # FI-TS_custom 2026-01-13: Reply in same context (thread or main) as triggering message
                        # FI-TS_custom 2026-01-15: Include citation sources in message data
                        response_message, channel = await new_message_handler(
                            request,
                            channel.id,
                            MessageForm(
                                **{
                                    "parent_id": message.parent_id if message.parent_id else None,
                                    "reply_to_id": message.id,  # Reference trigger message
                                    "content": response_content,
                                    "data": {
                                        "sources": citation_sources if citation_sources else [],
                                    },
                                    "meta": {
                                        "model_id": model_id,
                                        "model_name": model.get("name", model_id),
                                        "done": True,
                                    },
                                }
                            ),
                            user,
                            db,
                        )
                    else:
                        # No new messages - just update the empty message
                        # FI-TS_custom 2026-01-15: Include citation sources in message data
                        await update_message_by_id(
                            request,
                            channel.id,
                            response_message.id,
                            MessageForm(
                                **{
                                    "content": response_content,
                                    "data": {
                                        "sources": citation_sources if citation_sources else [],
                                    },
                                    "meta": {
                                        "model_id": model_id,
                                        "model_name": model.get("name", model_id),
                                        "done": True,
                                    },
                                }
                            ),
                            user,
                            db,
                        )

                    # Mark as successful - message has been properly updated
                    response_successful = True

            except Exception as e:
                # FI-TS_custom 2026-01-13: Clean up empty message to prevent stuck typing indicator
                log.error(f"Error generating channel response: {e}")
            finally:
                # Always clean up if response wasn't successful
                if not response_successful and response_message:
                    try:
                        Messages.delete_message_by_id(response_message.id, db=db)
                        log.info(f"Cleaned up stuck message {response_message.id} after error")
                    except Exception as cleanup_error:
                        log.error(f"Failed to clean up message: {cleanup_error}")

                # FI-TS_custom 2026-01-21: Always release the lock to prevent stuck channels
                channel_lock.release()
                log.info(f"Released response lock for channel {channel.id}")

    return True


async def new_message_handler(
    request: Request, id: str, form_data: MessageForm, user, db, emit_event: bool = True
):
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if user.role != "admin" and not has_access(
            user.id,
            type="write",
            access_control=channel.access_control,
            strict=False,
            db=db,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    try:
        message = Messages.insert_new_message(form_data, channel.id, user.id, db=db)
        if message:
            if channel.type in ["group", "dm"]:
                members = Channels.get_members_by_channel_id(channel.id, db=db)
                for member in members:
                    if not member.is_active:
                        Channels.update_member_active_status(
                            channel.id, member.user_id, True, db=db
                        )

            message = Messages.get_message_by_id(message.id, db=db)

            # FI-TS_custom 2026-01-13: Optionally skip socket emission for typing messages
            if emit_event:
                event_data = {
                    "channel_id": channel.id,
                    "message_id": message.id,
                    "data": {
                        "type": "message",
                        "data": {"temp_id": form_data.temp_id, **message.model_dump()},
                    },
                    "user": UserNameResponse(**user.model_dump()).model_dump(),
                    "channel": channel.model_dump(),
                }

                await sio.emit(
                    "events:channel",
                    event_data,
                    to=f"channel:{channel.id}",
                )

            if message.parent_id:
                # If this message is a reply, emit to the parent message as well
                parent_message = Messages.get_message_by_id(message.parent_id, db=db)

                if parent_message:
                    await sio.emit(
                        "events:channel",
                        {
                            "channel_id": channel.id,
                            "message_id": parent_message.id,
                            "data": {
                                "type": "message:reply",
                                "data": parent_message.model_dump(),
                            },
                            "user": UserNameResponse(**user.model_dump()).model_dump(),
                            "channel": channel.model_dump(),
                        },
                        to=f"channel:{channel.id}",
                    )
            return message, channel
        else:
            raise Exception("Error creating message")
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


@router.post("/{id}/messages/post", response_model=Optional[MessageModel])
async def post_new_message(
    request: Request,
    id: str,
    form_data: MessageForm,
    background_tasks: BackgroundTasks,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)

    try:
        message, channel = await new_message_handler(request, id, form_data, user, db)
        try:
            if files := message.data.get("files", []):
                for file in files:
                    Channels.set_file_message_id_in_channel_by_id(
                        channel.id, file.get("id", ""), message.id, db=db
                    )
        except Exception as e:
            log.debug(e)

        active_user_ids = get_user_ids_from_room(f"channel:{channel.id}")

        # NOTE: We intentionally do NOT pass db to background_handler.
        # Background tasks should manage their own short-lived sessions to avoid
        # holding database connections during slow operations (e.g., LLM calls).
        async def background_handler():
            await model_response_handler(request, channel, message, user)
            await send_notification(
                request.app.state.WEBUI_NAME,
                request.app.state.config.WEBUI_URL,
                channel,
                message,
                active_user_ids,
            )

        background_tasks.add_task(background_handler)

        return message

    except HTTPException as e:
        raise e
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetChannelMessage
############################


@router.get("/{id}/messages/{message_id}", response_model=Optional[MessageResponse])
async def get_channel_message(
    request: Request,
    id: str,
    message_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if user.role != "admin" and not has_access(
            user.id, type="read", access_control=channel.access_control, db=db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    message = Messages.get_message_by_id(message_id, db=db)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if message.channel_id != id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )

    return MessageResponse(
        **{
            **message.model_dump(),
            "user": UserNameResponse(
                **Users.get_user_by_id(message.user_id, db=db).model_dump()
            ),
        }
    )


############################
# GetChannelMessageData
############################


@router.get("/{id}/messages/{message_id}/data", response_model=Optional[dict])
async def get_channel_message_data(
    request: Request,
    id: str,
    message_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if user.role != "admin" and not has_access(
            user.id, type="read", access_control=channel.access_control, db=db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    message = Messages.get_message_by_id(message_id, db=db)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if message.channel_id != id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )

    return message.data


############################
# PinChannelMessage
############################


class PinMessageForm(BaseModel):
    is_pinned: bool


@router.post(
    "/{id}/messages/{message_id}/pin", response_model=Optional[MessageUserResponse]
)
async def pin_channel_message(
    request: Request,
    id: str,
    message_id: str,
    form_data: PinMessageForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if user.role != "admin" and not has_access(
            user.id, type="read", access_control=channel.access_control, db=db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    message = Messages.get_message_by_id(message_id, db=db)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if message.channel_id != id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )

    try:
        Messages.update_is_pinned_by_id(message_id, form_data.is_pinned, user.id, db=db)
        message = Messages.get_message_by_id(message_id, db=db)
        return MessageUserResponse(
            **{
                **message.model_dump(),
                "user": UserNameResponse(
                    **Users.get_user_by_id(message.user_id, db=db).model_dump()
                ),
            }
        )
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# GetChannelThreadMessages
############################


@router.get(
    "/{id}/messages/{message_id}/thread", response_model=list[MessageUserResponse]
)
async def get_channel_thread_messages(
    request: Request,
    id: str,
    message_id: str,
    skip: int = 0,
    limit: int = 50,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if user.role != "admin" and not has_access(
            user.id, type="read", access_control=channel.access_control, db=db
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    message_list = Messages.get_messages_by_parent_id(
        id, message_id, skip, limit, db=db
    )

    if not message_list:
        return []

    # Batch fetch all users in a single query (fixes N+1 problem)
    user_ids = list(set(m.user_id for m in message_list))
    users = {u.id: u for u in Users.get_users_by_user_ids(user_ids, db=db)}

    messages = []
    for message in message_list:
        # Use message.user if present (for webhooks), otherwise look up by user_id
        user_info = message.user
        if user_info is None and message.user_id in users:
            user_info = UserNameResponse(**users[message.user_id].model_dump())

        messages.append(
            MessageUserResponse(
                **{
                    **message.model_dump(),
                    "reply_count": 0,
                    "latest_reply_at": None,
                    "reactions": Messages.get_reactions_by_message_id(
                        message.id, db=db
                    ),
                    "user": user_info,
                }
            )
        )

    return messages


############################
# UpdateMessageById
############################


@router.post(
    "/{id}/messages/{message_id}/update", response_model=Optional[MessageModel]
)
async def update_message_by_id(
    request: Request,
    id: str,
    message_id: str,
    form_data: MessageForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    message = Messages.get_message_by_id(message_id, db=db)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if message.channel_id != id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if (
            user.role != "admin"
            and message.user_id != user.id
            and not has_access(
                user.id, type="read", access_control=channel.access_control, db=db
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    try:
        message = Messages.update_message_by_id(message_id, form_data, db=db)
        message = Messages.get_message_by_id(message_id, db=db)

        if message:
            await sio.emit(
                "events:channel",
                {
                    "channel_id": channel.id,
                    "message_id": message.id,
                    "data": {
                        "type": "message:update",
                        "data": message.model_dump(),
                    },
                    "user": UserNameResponse(**user.model_dump()).model_dump(),
                    "channel": channel.model_dump(),
                },
                to=f"channel:{channel.id}",
            )

        return MessageModel(**message.model_dump())
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# AddReactionToMessage
############################


class ReactionForm(BaseModel):
    name: str


@router.post("/{id}/messages/{message_id}/reactions/add", response_model=bool)
async def add_reaction_to_message(
    request: Request,
    id: str,
    message_id: str,
    form_data: ReactionForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if user.role != "admin" and not has_access(
            user.id,
            type="write",
            access_control=channel.access_control,
            strict=False,
            db=db,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    message = Messages.get_message_by_id(message_id, db=db)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if message.channel_id != id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )

    try:
        Messages.add_reaction_to_message(message_id, user.id, form_data.name, db=db)
        message = Messages.get_message_by_id(message_id, db=db)

        await sio.emit(
            "events:channel",
            {
                "channel_id": channel.id,
                "message_id": message.id,
                "data": {
                    "type": "message:reaction:add",
                    "data": {
                        **message.model_dump(),
                        "name": form_data.name,
                    },
                },
                "user": UserNameResponse(**user.model_dump()).model_dump(),
                "channel": channel.model_dump(),
            },
            to=f"channel:{channel.id}",
        )

        return True
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# RemoveReactionById
############################


@router.post("/{id}/messages/{message_id}/reactions/remove", response_model=bool)
async def remove_reaction_by_id_and_user_id_and_name(
    request: Request,
    id: str,
    message_id: str,
    form_data: ReactionForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if user.role != "admin" and not has_access(
            user.id,
            type="write",
            access_control=channel.access_control,
            strict=False,
            db=db,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    message = Messages.get_message_by_id(message_id, db=db)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if message.channel_id != id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )

    try:
        Messages.remove_reaction_by_id_and_user_id_and_name(
            message_id, user.id, form_data.name, db=db
        )

        message = Messages.get_message_by_id(message_id, db=db)

        await sio.emit(
            "events:channel",
            {
                "channel_id": channel.id,
                "message_id": message.id,
                "data": {
                    "type": "message:reaction:remove",
                    "data": {
                        **message.model_dump(),
                        "name": form_data.name,
                    },
                },
                "user": UserNameResponse(**user.model_dump()).model_dump(),
                "channel": channel.model_dump(),
            },
            to=f"channel:{channel.id}",
        )

        return True
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# DeleteMessageById
############################


@router.delete("/{id}/messages/{message_id}/delete", response_model=bool)
async def delete_message_by_id(
    request: Request,
    id: str,
    message_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    message = Messages.get_message_by_id(message_id, db=db)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    if message.channel_id != id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )

    if channel.type in ["group", "dm"]:
        if not Channels.is_user_channel_member(channel.id, user.id, db=db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )
    else:
        if (
            user.role != "admin"
            and message.user_id != user.id
            and not has_access(
                user.id,
                type="write",
                access_control=channel.access_control,
                strict=False,
                db=db,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.DEFAULT()
            )

    try:
        Messages.delete_message_by_id(message_id, db=db)
        await sio.emit(
            "events:channel",
            {
                "channel_id": channel.id,
                "message_id": message.id,
                "data": {
                    "type": "message:delete",
                    "data": {
                        **message.model_dump(),
                        "user": UserNameResponse(**user.model_dump()).model_dump(),
                    },
                },
                "user": UserNameResponse(**user.model_dump()).model_dump(),
                "channel": channel.model_dump(),
            },
            to=f"channel:{channel.id}",
        )

        if message.parent_id:
            # If this message is a reply, emit to the parent message as well
            parent_message = Messages.get_message_by_id(message.parent_id, db=db)

            if parent_message:
                await sio.emit(
                    "events:channel",
                    {
                        "channel_id": channel.id,
                        "message_id": parent_message.id,
                        "data": {
                            "type": "message:reply",
                            "data": parent_message.model_dump(),
                        },
                        "user": UserNameResponse(**user.model_dump()).model_dump(),
                        "channel": channel.model_dump(),
                    },
                    to=f"channel:{channel.id}",
                )

        return True
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )


############################
# Webhooks
############################


@router.get("/webhooks/{webhook_id}/profile/image")
async def get_webhook_profile_image(
    webhook_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    """Get webhook profile image by webhook ID."""
    webhook = Channels.get_webhook_by_id(webhook_id, db=db)
    if not webhook:
        # Return default favicon if webhook not found
        return FileResponse(f"{STATIC_DIR}/favicon.png")

    if webhook.profile_image_url:
        # Check if it's url or base64
        if webhook.profile_image_url.startswith("http"):
            return Response(
                status_code=status.HTTP_302_FOUND,
                headers={"Location": webhook.profile_image_url},
            )
        elif webhook.profile_image_url.startswith("data:image"):
            try:
                header, base64_data = webhook.profile_image_url.split(",", 1)
                image_data = base64.b64decode(base64_data)
                image_buffer = io.BytesIO(image_data)
                media_type = header.split(";")[0].lstrip("data:")

                return StreamingResponse(
                    image_buffer,
                    media_type=media_type,
                    headers={"Content-Disposition": "inline"},
                )
            except Exception as e:
                pass

    # Return default favicon if no profile image
    return FileResponse(f"{STATIC_DIR}/favicon.png")


@router.get("/{id}/webhooks", response_model=list[ChannelWebhookModel])
async def get_channel_webhooks(
    request: Request,
    id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    # Only channel managers can view webhooks
    if (
        not Channels.is_user_channel_manager(channel.id, user.id, db=db)
        and user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.UNAUTHORIZED
        )

    return Channels.get_webhooks_by_channel_id(id, db=db)


@router.post("/{id}/webhooks/create", response_model=ChannelWebhookModel)
async def create_channel_webhook(
    request: Request,
    id: str,
    form_data: ChannelWebhookForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    # Only channel managers can create webhooks
    if (
        not Channels.is_user_channel_manager(channel.id, user.id, db=db)
        and user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.UNAUTHORIZED
        )

    webhook = Channels.insert_webhook(id, user.id, form_data, db=db)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )

    return webhook


@router.post("/{id}/webhooks/{webhook_id}/update", response_model=ChannelWebhookModel)
async def update_channel_webhook(
    request: Request,
    id: str,
    webhook_id: str,
    form_data: ChannelWebhookForm,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    # Only channel managers can update webhooks
    if (
        not Channels.is_user_channel_manager(channel.id, user.id, db=db)
        and user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.UNAUTHORIZED
        )

    webhook = Channels.get_webhook_by_id(webhook_id, db=db)
    if not webhook or webhook.channel_id != id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    updated = Channels.update_webhook_by_id(webhook_id, form_data, db=db)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=ERROR_MESSAGES.DEFAULT()
        )

    return updated


@router.delete("/{id}/webhooks/{webhook_id}/delete", response_model=bool)
async def delete_channel_webhook(
    request: Request,
    id: str,
    webhook_id: str,
    user=Depends(get_verified_user),
    db: Session = Depends(get_session),
):
    check_channels_access(request)
    channel = Channels.get_channel_by_id(id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    # Only channel managers can delete webhooks
    if (
        not Channels.is_user_channel_manager(channel.id, user.id, db=db)
        and user.role != "admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.UNAUTHORIZED
        )

    webhook = Channels.get_webhook_by_id(webhook_id, db=db)
    if not webhook or webhook.channel_id != id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    return Channels.delete_webhook_by_id(webhook_id, db=db)


############################
# Public Webhook Endpoint
############################


class WebhookMessageForm(BaseModel):
    content: str


@router.post("/webhooks/{webhook_id}/{token}")
async def post_webhook_message(
    request: Request,
    webhook_id: str,
    token: str,
    form_data: WebhookMessageForm,
    db: Session = Depends(get_session),
):
    """Public endpoint to post messages via webhook. No authentication required."""
    check_channels_access(request)

    # Validate webhook
    webhook = Channels.get_webhook_by_id_and_token(webhook_id, token, db=db)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook URL",
        )

    channel = Channels.get_channel_by_id(webhook.channel_id, db=db)
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND
        )

    # Create message with webhook identity stored in meta
    message = Messages.insert_new_message(
        MessageForm(content=form_data.content, meta={"webhook": {"id": webhook.id}}),
        webhook.channel_id,
        webhook.user_id,  # Required for DB but webhook info in meta takes precedence
        db=db,
    )

    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create message",
        )

    # Update last_used_at
    Channels.update_webhook_last_used_at(webhook_id, db=db)

    # Get full message and emit event
    message = Messages.get_message_by_id(message.id, db=db)

    event_data = {
        "channel_id": channel.id,
        "message_id": message.id,
        "data": {
            "type": "message",
            "data": {
                **message.model_dump(),
                "user": {
                    "id": webhook.id,
                    "name": webhook.name,
                    "role": "webhook",
                },
            },
        },
        "user": {
            "id": webhook.id,
            "name": webhook.name,
            "role": "webhook",
        },
        "channel": channel.model_dump(),
    }

    await sio.emit(
        "events:channel",
        event_data,
        to=f"channel:{channel.id}",
    )

    return {"success": True, "message_id": message.id}
