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
		class="flex items-center gap-2 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition"
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
			<div class="flex flex-wrap gap-3 px-4 pt-4 pb-2">
				{#each status.queries as query}
					<a
						class="inline-flex items-center min-h-[2rem] rounded-full bg-gray-100 dark:bg-gray-800 px-2.5 py-0.5 text-sm font-normal text-gray-800 dark:text-gray-100 border border-gray-200 dark:border-gray-700 transition-all duration-300 ease-out whitespace-nowrap"
						style="text-decoration: none; cursor: default;"
					>
						<MagnifyingGlass className="w-4 h-4 mr-1 text-gray-500 flex-shrink-0" />
						<span>{query}</span>
					</a>
				{/each}
			</div>
		{:else if status?.query}
			<!-- Show single query if no queries array but query exists -->
			<div class="flex w-full items-center p-3 px-4 border-b border-gray-300/30 dark:border-gray-700/50 group/item justify-between font-normal text-gray-800 dark:text-gray-300 no-underline">
				<div class="flex gap-2 items-center">
					<MagnifyingGlass />
					<div class="line-clamp-1">
						{status.query}
					</div>
				</div>
			</div>
		{/if}
	</div>
</Collapsible>
