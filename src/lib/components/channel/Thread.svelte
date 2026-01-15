<script lang="ts">
	import { goto } from '$app/navigation';

	import { socket, user } from '$lib/stores';

	import { getChannelThreadMessages, sendMessage } from '$lib/apis/channels';

	import XMark from '$lib/components/icons/XMark.svelte';
	import MessageInput from './MessageInput.svelte';
	import Messages from './Messages.svelte';
	import { onDestroy, onMount, tick, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Spinner from '../common/Spinner.svelte';

	const i18n = getContext('i18n');

	export let threadId = null;
	export let channel = null;

	export let onClose = () => {};

	let messages = null;
	let top = false;

	let messagesContainerElement = null;
	let chatInputElement = null;

	let replyToMessage = null;

	let typingUsers = [];
	let typingUsersTimeout = {};

	$: if (threadId) {
		initHandler();
	}

	const scrollToBottom = () => {
		messagesContainerElement.scrollTop = messagesContainerElement.scrollHeight;
	};

	const initHandler = async () => {
		messages = null;
		top = false;

		typingUsers = [];
		typingUsersTimeout = {};

		if (channel) {
			const loadedMessages = await getChannelThreadMessages(localStorage.token, channel.id, threadId);

			// FI-TS_custom 2026-01-13: Filter empty model messages and convert to typing indicators
			const filteredMessages = [];

			for (const message of loadedMessages) {
				// Check if this is an empty model message that's still in progress (typing indicator)
				if (
					message?.meta?.model_id &&
					(message?.content ?? '').trim() === '' &&
					message?.meta?.done === false
				) {
					// Add model to typing users
					const modelName = message?.meta?.model_name ?? message?.meta?.model_id;
					const modelId = `model_${message?.meta?.model_id}`;

					if (!typingUsers.find((user) => user.id === modelId)) {
						typingUsers = [...typingUsers, { id: modelId, name: modelName }];
					}

					// Don't add to messages array
				} else {
					// Regular message - add to list
					filteredMessages.push(message);
				}
			}

			messages = filteredMessages;

			if (messages.length < 50) {
				top = true;
			}

			await tick();
			scrollToBottom();
		} else {
			goto('/');
		}
	};

	const channelEventHandler = async (event) => {
		console.debug(event);
		if (event.channel_id === channel.id) {
			const type = event?.data?.type ?? null;
			const data = event?.data?.data ?? null;

			if (type === 'message') {
				if ((data?.parent_id ?? null) === threadId) {
					// FI-TS_custom 2026-01-15: Filter empty model messages and show typing indicator instead
					if (
						data?.meta?.model_id &&
						(data?.content ?? '').trim() === '' &&
						data?.meta?.done === false
					) {
						// Add model to typing users
						const modelName = data?.meta?.model_name ?? data?.meta?.model_id;
						const modelId = `model_${data?.meta?.model_id}`;

						if (!typingUsers.find((user) => user.id === modelId)) {
							typingUsers = [...typingUsers, { id: modelId, name: modelName }];
						}
						// Don't add the empty message to the messages list yet
						return;
					}

					// FI-TS_custom 2026-01-15: Remove model from typing users if completed
					if (data?.meta?.model_id && (data?.content ?? '').trim() !== '') {
						const modelId = `model_${data?.meta?.model_id}`;
						typingUsers = typingUsers.filter((user) => user.id !== modelId);
					}

					if (messages) {
						messages = [data, ...messages];

						if (typingUsers.find((user) => user.id === event.user.id)) {
							typingUsers = typingUsers.filter((user) => user.id !== event.user.id);
						}
					}
				}
			} else if (type === 'message:update') {
				// FI-TS_custom 2026-01-15: Remove model from typing users when content arrives
				if (data?.meta?.model_id && (data?.content ?? '').trim() !== '') {
					const modelId = `model_${data?.meta?.model_id}`;
					typingUsers = typingUsers.filter((user) => user.id !== modelId);
				}

				if (messages) {
					const idx = messages.findIndex((message) => message.id === data.id);

					if (idx !== -1) {
						messages[idx] = data;
					} else if (data?.meta?.model_id && (data?.content ?? '').trim() !== '' && (data?.parent_id ?? null) === threadId) {
						// FI-TS_custom 2026-01-15: Add message if it was hidden during typing
						messages = [data, ...messages];
					}
				}
			} else if (type === 'message:delete') {
				if (messages) {
					messages = messages.filter((message) => message.id !== data.id);
				}
			} else if (type.includes('message:reaction')) {
				if (messages) {
					const idx = messages.findIndex((message) => message.id === data.id);
					if (idx !== -1) {
						messages[idx] = data;
					}
				}
			} else if (type === 'typing' && event.message_id === threadId) {
				if (event.user.id === $user?.id) {
					return;
				}

				typingUsers = data.typing
					? [
							...typingUsers,
							...(typingUsers.find((user) => user.id === event.user.id)
								? []
								: [
										{
											id: event.user.id,
											name: event.user.name
										}
									])
						]
					: typingUsers.filter((user) => user.id !== event.user.id);

				if (typingUsersTimeout[event.user.id]) {
					clearTimeout(typingUsersTimeout[event.user.id]);
				}

				typingUsersTimeout[event.user.id] = setTimeout(() => {
					typingUsers = typingUsers.filter((user) => user.id !== event.user.id);
				}, 5000);
			} else if (type === 'model_status' && event.message_id === threadId) {
				// FI-TS_custom 2026-01-15: Handle model tool status for this thread
				const modelId = `model_${data.model_id}`;
				const modelName = data.model_name ?? data.model_id;
				const modelStatus = data.status; // "searching_web", "searching_channel", or null

				const existingIdx = typingUsers.findIndex((user) => user.id === modelId);
				if (existingIdx !== -1) {
					typingUsers[existingIdx] = { ...typingUsers[existingIdx], status: modelStatus };
					typingUsers = typingUsers;
				} else {
					typingUsers = [...typingUsers, { id: modelId, name: modelName, status: modelStatus }];
				}
			}
		}
	};

	const submitHandler = async ({ content, data }) => {
		if (!content && (data?.files ?? []).length === 0) {
			return;
		}

		const res = await sendMessage(localStorage.token, channel.id, {
			parent_id: threadId,
			reply_to_id: replyToMessage?.id ?? null,
			content: content,
			data: data
		}).catch((error) => {
			toast.error(`${error}`);
			return null;
		});

		replyToMessage = null;
	};

	const onChange = async () => {
		$socket?.emit('events:channel', {
			channel_id: channel.id,
			message_id: threadId,
			data: {
				type: 'typing',
				data: {
					typing: true
				}
			}
		});
	};

	onMount(() => {
		$socket?.on('events:channel', channelEventHandler);
	});

	onDestroy(() => {
		$socket?.off('events:channel', channelEventHandler);
	});
</script>

{#if channel}
	<div class="flex flex-col w-full h-full bg-gray-50 dark:bg-gray-850">
		<div class="sticky top-0 flex items-center justify-between px-3.5 py-3">
			<div class=" font-medium text-lg">{$i18n.t('Thread')}</div>

			<div>
				<button
					class="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 p-2"
					on:click={() => {
						onClose();
					}}
				>
					<XMark />
				</button>
			</div>
		</div>

		<div class=" max-h-full w-full overflow-y-auto" bind:this={messagesContainerElement}>
			{#if messages !== null}
				<Messages
					id={threadId}
					{channel}
					{top}
					{messages}
					{replyToMessage}
					thread={true}
					onReply={async (message) => {
						replyToMessage = message;

						await tick();
						chatInputElement?.focus();
					}}
					onLoad={async () => {
						const newMessages = await getChannelThreadMessages(
							localStorage.token,
							channel.id,
							threadId,
							messages.length
						);

						// FI-TS_custom 2026-01-13: Filter empty model messages when loading more
						const filteredNewMessages = [];

						for (const message of newMessages) {
							// Check if this is an empty model message that's still in progress (typing indicator)
							if (
								message?.meta?.model_id &&
								(message?.content ?? '').trim() === '' &&
								message?.meta?.done === false
							) {
								// Add model to typing users
								const modelName = message?.meta?.model_name ?? message?.meta?.model_id;
								const modelId = `model_${message?.meta?.model_id}`;

								if (!typingUsers.find((user) => user.id === modelId)) {
									typingUsers = [...typingUsers, { id: modelId, name: modelName }];
								}

								// Don't add to messages array
							} else {
								// Regular message - add to list
								filteredNewMessages.push(message);
							}
						}

						messages = [...messages, ...filteredNewMessages];

						if (newMessages.length < 50) {
							top = true;
							return;
						}
					}}
				/>
			{:else}
				<div class="w-full flex justify-center pt-5 pb-10">
					<Spinner />
				</div>
			{/if}

			<div class=" pb-[1rem] px-2.5 w-full">
				<MessageInput
					bind:replyToMessage
					bind:chatInputElement
					id={threadId}
					{channel}
					disabled={!channel?.write_access}
					placeholder={!channel?.write_access
						? $i18n.t('You do not have permission to send messages in this thread.')
						: $i18n.t('Reply to thread...')}
					typingUsersClassName="from-gray-50 dark:from-gray-850"
					{typingUsers}
					userSuggestions={true}
					channelSuggestions={true}
					{onChange}
					onSubmit={submitHandler}
				/>
			</div>
		</div>
	</div>
{/if}
