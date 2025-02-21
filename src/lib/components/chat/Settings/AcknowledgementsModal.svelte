<script lang="ts">
	import { getContext } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import { showAcknowledgements, acknowledgementsContent } from '$lib/stores/index';

	const i18n = getContext('i18n');
</script>

<Modal bind:show={$showAcknowledgements} size="lg">
	<div class="px-5 pt-4 dark:text-gray-300 text-gray-700">
		<div class="flex justify-between items-start">
			<div class="text-xl font-semibold">Open Source Licenses</div>
			<button
				class="self-center"
				on:click={() => {
					showAcknowledgements.set(false);
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
					class="w-5 h-5"
				>
					<path
						d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"
					/>
				</svg>
			</button>
		</div>
		<div class="flex items-center mt-1">
			<div class="text-sm dark:text-gray-200">FI-TS AI</div>
			<div class="flex self-center w-[1px] h-6 mx-2.5 bg-gray-200 dark:bg-gray-700" />
			<div class="text-sm dark:text-gray-200">Open Source Acknowledgements</div>
		</div>
	</div>

	<div class="w-full p-4 px-5 text-gray-700 dark:text-gray-100">
		<div class="overflow-y-scroll max-h-96 scrollbar-hidden markdown-prose">
			<Markdown content={$acknowledgementsContent} id="acknowledgements" />
		</div>
		<div class="flex justify-end pt-3 text-sm font-medium">
			<button
				on:click={() => {
					showAcknowledgements.set(false);
				}}
				class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
			>
				<span class="relative">{$i18n.t('Close')}</span>
			</button>
		</div>
	</div>
</Modal>
