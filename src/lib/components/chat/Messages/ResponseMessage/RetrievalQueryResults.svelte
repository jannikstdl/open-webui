<script lang="ts">
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import MagnifyingGlass from '$lib/components/icons/MagnifyingGlass.svelte';
	import Collapsible from '$lib/components/common/Collapsible.svelte';

	export let status = { query: '', queries: [] };
	let state = false;
</script>

<Collapsible bind:open={state} className="w-full space-y-1">
	<div
		class="flex items-center gap-2 text-gray-700 dark:text-gray-200 hover:text-gray-900 dark:hover:text-gray-100 transition"
	>
		<slot />

		{#if state}
			<ChevronUp strokeWidth="3.5" className="size-3.5 " />
		{:else}
			<ChevronDown strokeWidth="3.5" className="size-3.5 " />
		{/if}
	</div>
	<div class="text-sm border border-gray-300/30 dark:border-gray-700/50 rounded-xl" slot="content">
		<!-- Show generated retrieval queries as pills -->
		{#if status?.queries && status.queries.length > 0}
			<div class="flex flex-wrap gap-3 px-4 py-3">
				{#each status.queries as query}
					<div
						class="inline-flex items-center min-h-[2rem] rounded-full bg-gray-100 dark:bg-gray-800 px-2.5 py-0.5 text-sm font-normal !text-gray-700 dark:!text-gray-100 border border-gray-200 dark:border-gray-700 transition-all duration-300 ease-out whitespace-nowrap"
						style="text-decoration: none;"
					>
						<MagnifyingGlass
							className="w-4 h-4 mr-2 text-gray-600 dark:text-gray-300 flex-shrink-0"
						/>
						<span>{query}</span>
					</div>
				{/each}
			</div>
		{:else if status?.query}
			<!-- Show single query if no queries array but query exists -->

			<div
				class="flex w-full items-center p-3 group/item justify-between font-normal text-red-800 dark:text-gray-300"
			>
				<div class="flex gap-2 items-center">
					<MagnifyingGlass
						className="w-4 h-4 mr-2 text-gray-600 dark:text-gray-300 flex-shrink-0"
					/>
					<div class="line-clamp-1">
						{status.query}
					</div>
				</div>
			</div>
		{/if}
	</div>
</Collapsible>
