<script lang="ts">
	import { getContext, onMount, tick } from 'svelte';
	import { formatFileSize, getLineCount } from '$lib/utils';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { getKnowledgeById } from '$lib/apis/knowledge';

	const i18n = getContext('i18n');
	const config = getContext('config');

	import Modal from './Modal.svelte';
	import XMark from '../icons/XMark.svelte';
	import Info from '../icons/Info.svelte';
	import Switch from './Switch.svelte';
	import Tooltip from './Tooltip.svelte';
	import dayjs from 'dayjs';
	import Spinner from './Spinner.svelte';
	import { getFileById, generateFileContentSummary } from '$lib/apis/files';

	export let item;
	export let show = false;
	export let edit = false;

	let enableFullContent = false;

	let isPdf = false;
	let isAudio = false;
	let loading = false;

	let selectedTab = '';
	let contentSummary: string | null = null;
	let summaryLoading = false;

	$: isPDF =
		item?.meta?.content_type === 'application/pdf' ||
		(item?.name && item?.name.toLowerCase().endsWith('.pdf'));

	$: isAudio =
		(item?.meta?.content_type ?? '').startsWith('audio/') ||
		(item?.name && item?.name.toLowerCase().endsWith('.mp3')) ||
		(item?.name && item?.name.toLowerCase().endsWith('.wav')) ||
		(item?.name && item?.name.toLowerCase().endsWith('.ogg')) ||
		(item?.name && item?.name.toLowerCase().endsWith('.m4a')) ||
		(item?.name && item?.name.toLowerCase().endsWith('.webm'));

	// FI-TS_custom 13.09.2025: Load content summary for files
	const loadContentSummary = async () => {
		// FI-TS_custom 15.09.2025: Check if feature is enabled before proceeding
		if (!$config?.features?.enable_file_content_summary) {
			return;
		}

		if (item?.type !== 'file') return;

		// Check if summary already exists in metadata
		if (item?.file?.meta?.content_summary) {
			contentSummary = item.file.meta.content_summary;
			return;
		}

		// Use the extracted content that's already available
		const extractedContent = item?.file?.data?.content;
		if (!extractedContent) {
			contentSummary = null;
			return;
		}

		summaryLoading = true;
		try {
			// Send both file_id and content for optimal processing and storage
			const result = await generateFileContentSummary(localStorage.token, item.id, extractedContent);
			if (result?.content_summary) {
				contentSummary = result.content_summary;
				// Update the item metadata so we don't need to regenerate
				if (item.file && item.file.meta) {
					item.file.meta.content_summary = result.content_summary;
				}
			}
		} catch (error) {
			console.error('Error generating content summary:', error);
		}
		summaryLoading = false;
	};

	const loadContent = async () => {
		if (item?.type === 'collection') {
			loading = true;

			const knowledge = await getKnowledgeById(localStorage.token, item.id).catch((e) => {
				console.error('Error fetching knowledge base:', e);
				return null;
			});

			if (knowledge) {
				item.files = knowledge.files || [];
			}
			loading = false;
		} else if (item?.type === 'file') {
			loading = true;

			const file = await getFileById(localStorage.token, item.id).catch((e) => {
				console.error('Error fetching file:', e);
				return null;
			});

			if (file) {
				item.file = file || {};
			}
			loading = false;
		}

		await tick();
	};

	$: if (show) {
		loadContent();
	}

	onMount(() => {
		console.log(item);
		if (item?.context === 'full') {
			enableFullContent = true;
		}
	});
</script>

<Modal bind:show size="lg">
	<div class="font-primary px-4.5 py-3.5 w-full flex flex-col justify-center dark:text-gray-400">
		<div class=" pb-2">
			<div class="flex items-start justify-between">
				<div>
					<div class=" font-medium text-lg dark:text-gray-100">
						<a
							href="#"
							class="hover:underline line-clamp-1"
							on:click|preventDefault={() => {
								if (!isPDF && item.url) {
									window.open(
										item.type === 'file' ? `${item.url}/content` : `${item.url}`,
										'_blank'
									);
								}
							}}
						>
							{item?.name ?? 'File'}
						</a>
					</div>
				</div>

				<div>
					<button
						on:click={() => {
							show = false;
						}}
					>
						<XMark />
					</button>
				</div>
			</div>

			<div>
				<div class="flex flex-col items-center md:flex-row gap-1 justify-between w-full">
					<div class=" flex flex-wrap text-xs gap-1 text-gray-500">
						{#if item?.type === 'collection'}
							{#if item?.type}
								<div class="capitalize shrink-0">{item.type}</div>
								•
							{/if}

							{#if item?.description}
								<div class="line-clamp-1">{item.description}</div>
								•
							{/if}

							{#if item?.created_at}
								<div class="capitalize shrink-0">
									{dayjs(item.created_at * 1000).format('LL')}
								</div>
							{/if}
						{/if}

						{#if item.size}
							<div class="capitalize shrink-0">{formatFileSize(item.size)}</div>
							•
						{/if}

						{#if item?.file?.data?.content}
							<div class="capitalize shrink-0">
								{$i18n.t('{{COUNT}} extracted lines', {
									COUNT: getLineCount(item?.file?.data?.content ?? '')
								})}
							</div>

							<div class="flex items-center gap-1 shrink-0">
								• {$i18n.t('Formatting may be inconsistent from source.')}
							</div>
						{/if}

						{#if item?.knowledge}
							<div class="capitalize shrink-0">
								{$i18n.t('Knowledge Base')}
							</div>
						{/if}
					</div>

					{#if edit}
						<div>
							<Tooltip
								content={enableFullContent
									? $i18n.t(
											'Inject the entire content as context for comprehensive processing, this is recommended for complex queries.'
										)
									: $i18n.t(
											'Default to segmented retrieval for focused and relevant content extraction, this is recommended for most cases.'
										)}
							>
								<div class="flex items-center gap-1.5 text-xs">
									{#if enableFullContent}
										{$i18n.t('Using Entire Document')}
									{:else}
										{$i18n.t('Using Focused Retrieval')}
									{/if}
									<Switch
										bind:state={enableFullContent}
										on:change={(e) => {
											item.context = e.detail ? 'full' : undefined;
										}}
									/>
								</div>
							</Tooltip>
						</div>
					{/if}
				</div>
			</div>
		</div>

		<div class="max-h-[75vh] overflow-auto">
			{#if !loading}
				{#if item?.type === 'collection'}
					<div>
						{#each item?.files as file}
							<div class="flex items-center gap-2 mb-2">
								<div class="flex-shrink-0 text-xs">
									{file?.meta?.name}
								</div>
							</div>
						{/each}
					</div>
				{:else if isPDF}
					<div
						class="flex mb-2.5 scrollbar-none overflow-x-auto w-full border-b border-gray-100 dark:border-gray-800 text-center text-sm font-medium bg-transparent dark:text-gray-200"
					>
						<button
							class="min-w-fit py-1.5 px-4 border-b {selectedTab === ''
								? ' '
								: ' border-transparent text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							type="button"
							on:click={() => {
								selectedTab = '';
							}}>{$i18n.t('Content')}</button
						>

						<button
							class="min-w-fit py-1.5 px-4 border-b {selectedTab === 'preview'
								? ' '
								: ' border-transparent text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							type="button"
							on:click={() => {
								selectedTab = 'preview';
							}}>{$i18n.t('Preview')}</button
						>

						<!-- FI-TS_custom 13.09.2025: Content Summary tab -->
						{#if $config?.features?.enable_file_content_summary}
							<button
								class="min-w-fit py-1.5 px-4 border-b {selectedTab === 'summary'
									? ' '
									: ' border-transparent text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
								type="button"
								on:click={() => {
									selectedTab = 'summary';
									loadContentSummary();
								}}>{$i18n.t('Summary')}</button
							>
						{/if}
					</div>

					{#if selectedTab === 'preview'}
						<iframe
							title={item?.name}
							src={`${WEBUI_API_BASE_URL}/files/${item.id}/content`}
							class="w-full h-[70vh] border-0 rounded-lg"
						/>
					{:else if selectedTab === 'summary'}
						<!-- FI-TS_custom 13.09.2025: Content Summary display -->
						<div class="max-h-96 overflow-scroll scrollbar-hidden text-sm">
							{#if summaryLoading}
								<div class="animate-pulse space-y-2">
									<div class="h-4 bg-gray-300 dark:bg-gray-700 rounded w-3/4"></div>
									<div class="h-4 bg-gray-300 dark:bg-gray-700 rounded w-1/2"></div>
									<div class="h-4 bg-gray-300 dark:bg-gray-700 rounded w-2/3"></div>
									<div class="h-4 bg-gray-300 dark:bg-gray-700 rounded w-1/4"></div>
								</div>
							{:else if contentSummary}
								<div class="prose dark:prose-invert max-w-none">
									{contentSummary}
								</div>
							{:else}
								<div class="text-gray-500 dark:text-gray-400 text-center py-4">
									{$i18n.t('No content summary available')}
								</div>
							{/if}
						</div>
					{:else}
						<div class="max-h-96 overflow-scroll scrollbar-hidden text-xs whitespace-pre-wrap">
							{(item?.file?.data?.content ?? '').trim() || 'No content'}
						</div>
					{/if}
				{:else}
					<!-- FI-TS_custom 13.09.2025: Add tabs for non-PDF files -->
					<div
						class="flex mb-2.5 scrollbar-none overflow-x-auto w-full border-b border-gray-100 dark:border-gray-800 text-center text-sm font-medium bg-transparent dark:text-gray-200"
					>
						<button
							class="min-w-fit py-1.5 px-4 border-b {selectedTab === '' || selectedTab === 'content'
								? ' '
								: ' border-transparent text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
							type="button"
							on:click={() => {
								selectedTab = 'content';
							}}>{$i18n.t('Content')}</button
						>

						{#if $config?.features?.enable_file_content_summary}
							<button
								class="min-w-fit py-1.5 px-4 border-b {selectedTab === 'summary'
									? ' '
									: ' border-transparent text-gray-300 dark:text-gray-600 hover:text-gray-700 dark:hover:text-white'} transition"
								type="button"
								on:click={() => {
									selectedTab = 'summary';
									loadContentSummary();
								}}>{$i18n.t('Summary')}</button
							>
						{/if}
					</div>

					{#if selectedTab === 'summary'}
						<!-- FI-TS_custom 13.09.2025: Content Summary display -->
						<div class="max-h-96 overflow-scroll scrollbar-hidden text-sm">
							{#if summaryLoading}
								<div class="animate-pulse space-y-2">
									<div class="h-4 bg-gray-300 dark:bg-gray-700 rounded w-3/4"></div>
									<div class="h-4 bg-gray-300 dark:bg-gray-700 rounded w-1/2"></div>
									<div class="h-4 bg-gray-300 dark:bg-gray-700 rounded w-2/3"></div>
									<div class="h-4 bg-gray-300 dark:bg-gray-700 rounded w-1/4"></div>
								</div>
							{:else if contentSummary}
								<div class="prose dark:prose-invert max-w-none">
									{contentSummary}
								</div>
							{:else}
								<div class="text-gray-500 dark:text-gray-400 text-center py-4">
									{$i18n.t('No content summary available')}
								</div>
							{/if}
						</div>
					{:else}
						{#if isAudio}
							<audio
								src={`${WEBUI_API_BASE_URL}/files/${item.id}/content`}
								class="w-full border-0 rounded-lg mb-2"
								controls
								playsinline
							/>
						{/if}

						{#if item?.file?.data}
							<div class="max-h-96 overflow-scroll scrollbar-hidden text-xs whitespace-pre-wrap">
								{item?.file?.data?.content ?? 'No content'}
							</div>
						{/if}
					{/if}
				{/if}
			{:else}
				<div class="flex items-center justify-center py-6">
					<Spinner className="size-5" />
				</div>
			{/if}
		</div>
	</div>
</Modal>
