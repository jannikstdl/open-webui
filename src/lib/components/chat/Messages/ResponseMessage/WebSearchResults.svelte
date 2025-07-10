<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import MagnifyingGlass from '$lib/components/icons/MagnifyingGlass.svelte';
	import Collapsible from '$lib/components/common/Collapsible.svelte';
	import { getFaviconSrc, handleFaviconError, getDomain } from '$lib/utils/favicon';

	// i18n is provided as a Svelte store via context in the parent component
	// so type it accordingly so that `$i18n` can be used in the markup without linter errors
	const i18n = getContext<Writable<i18nType>>('i18n');

	export let status = { urls: [], query: '', queries: [] };
	let state = false;
	let showAllLinks = false;
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
		<!-- Show generated search queries as pills (same style as links) -->
		{#if status?.queries && status.queries.length > 0}
			<div class="flex flex-wrap gap-3 px-4 py-3">
				{#each status.queries as query}
					<a
						href="https://www.google.com/search?q={encodeURIComponent(query)}"
						target="_blank"
						class="inline-flex items-center min-h-[2rem] rounded-full bg-gray-100 dark:bg-gray-800 px-2.5 py-0.5 text-sm font-normal !text-gray-700 dark:!text-gray-100 border border-gray-200 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-700 transition-all duration-300 ease-out whitespace-nowrap"
						style="text-decoration: none;"
					>
						<svg
							class="w-4 h-4 mr-1 text-gray-600 dark:text-gray-300 flex-shrink-0"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							viewBox="0 0 24 24"
							xmlns="http://www.w3.org/2000/svg"
							><path
								stroke-linecap="round"
								stroke-linejoin="round"
								d="M21 21l-4.35-4.35m0 0A7.5 7.5 0 104.5 4.5a7.5 7.5 0 0012.15 12.15z"
							></path></svg
						>
						<span>{query}</span>
					</a>
				{/each}
			</div>
		{/if}

		<!-- Show single query if no queries array but query exists -->
		{#if !status?.queries && status?.query}
			<a
				href="https://www.google.com/search?q={status.query}"
				target="_blank"
				class="flex w-full items-center p-3 border-b border-gray-300/30 dark:border-gray-700/50 group/item justify-between font-normal !text-gray-700 dark:!text-gray-300 no-underline hover:!text-gray-900 dark:hover:!text-gray-100"
				style="text-decoration: none;"
			>
				<div class="flex gap-2 items-center">
					<MagnifyingGlass
						className="w-4 h-4 mr-2 text-gray-600 dark:text-gray-300 flex-shrink-0"
					/>

					<div class=" line-clamp-1">
						{status.query}
					</div>
				</div>

				<div
					class=" ml-1 text-white dark:text-gray-900 group-hover/item:text-gray-600 dark:group-hover/item:text-white transition"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="size-4"
					>
						<path
							fill-rule="evenodd"
							d="M4.22 11.78a.75.75 0 0 1 0-1.06L9.44 5.5H5.75a.75.75 0 0 1 0-1.5h5.5a.75.75 0 0 1 .75.75v5.5a.75.75 0 0 1-1.5 0V6.56l-5.22 5.22a.75.75 0 0 1-1.06 0Z"
							clip-rule="evenodd"
						/>
					</svg>
				</div>
			</a>
		{/if}

		<!-- Show search results URLs as pills with favicon and domain, and a 'N more' pill if needed -->
		{#if status.urls && status.urls.length > 0}
			<div class="flex flex-wrap gap-3 px-4 py-3">
				{#each showAllLinks ? status.urls : status.urls.slice(0, 3) as url, urlIdx (urlIdx)}
					<a
						href={url}
						target="_blank"
						rel="noopener noreferrer"
						class="inline-flex items-center min-h-[2rem] rounded-full bg-gray-100 dark:bg-gray-800 px-2.5 py-0.5 text-sm font-normal !text-gray-700 dark:!text-gray-100 border border-gray-200 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-700 transition-all duration-300 ease-out whitespace-nowrap"
						style="text-decoration: none;"
					>
						{#if getFaviconSrc(getDomain(url), urlIdx)}
							<img
								src={getFaviconSrc(getDomain(url), urlIdx)}
								alt=""
								class="w-4 h-4 mr-2 rounded-full bg-white border border-gray-200 dark:border-gray-700"
								loading="lazy"
								on:error={(e) => handleFaviconError(e, getDomain(url), urlIdx)}
							/>
						{:else}
							<svg
								xmlns="http://www.w3.org/2000/svg"
								fill="none"
								viewBox="0 0 24 24"
								stroke-width="1.5"
								stroke="currentColor"
								class="w-4 h-4 mr-2 text-gray-600 dark:text-gray-300"
							>
								<path
									stroke-linecap="round"
									stroke-linejoin="round"
									d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418"
								/>
							</svg>
						{/if}
						<span>{getDomain(url)}</span>
					</a>
				{/each}

				{#if !showAllLinks && status.urls.length > 3}
					<a
						href="#"
						class="inline-flex items-center min-h-[2rem] rounded-full bg-gray-100 dark:bg-gray-800 px-2.5 py-0.5 text-sm font-normal !text-gray-700 dark:!text-gray-100 border border-gray-200 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-700 transition-all duration-300 ease-out whitespace-nowrap cursor-pointer"
						style="text-decoration: none;"
						on:click|preventDefault={() => (showAllLinks = true)}
					>
						<span class="flex items-center mr-2">
							{#each [0, 1] as i}
								{#if status.urls[3 + i] && getFaviconSrc(getDomain(status.urls[3 + i]), 3 + i)}
									<img
										src={getFaviconSrc(getDomain(status.urls[3 + i]), 3 + i)}
										alt=""
										class="w-4 h-4 rounded-full bg-white border border-gray-200 dark:border-gray-700 flex-shrink-0 {i ===
										1
											? '-ml-2'
											: ''}"
										loading="lazy"
										on:error={(e) => handleFaviconError(e, getDomain(status.urls[3 + i]), 3 + i)}
									/>
								{:else if status.urls[3 + i]}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										fill="none"
										viewBox="0 0 24 24"
										stroke-width="1.5"
										stroke="currentColor"
										class="w-4 h-4 text-gray-600 dark:text-gray-300 flex-shrink-0 {i === 1
											? '-ml-2'
											: ''}"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M12 21a9.004 9.004 0 0 0 8.716-6.747M12 21a9.004 9.004 0 0 1-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 0 1 7.843 4.582M12 3a8.997 8.997 0 0 0-7.843 4.582m15.686 0A11.953 11.953 0 0 1 12 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0 1 21 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0 1 12 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 0 1 3 12c0-1.605.42-3.113 1.157-4.418"
										/>
									</svg>
								{/if}
							{/each}
						</span>
						<span>{status.urls.length - 3} {$i18n.t('more')}</span>
					</a>
				{/if}

				{#if showAllLinks && status.urls.length > 3}
					<a
						href="#"
						class="inline-flex items-center min-h-[2rem] rounded-full bg-gray-100 dark:bg-gray-800 px-2.5 py-0.5 text-sm font-normal !text-gray-700 dark:!text-gray-100 border border-gray-200 dark:border-gray-700 hover:bg-gray-200 dark:hover:bg-gray-700 transition-all duration-300 ease-out whitespace-nowrap cursor-pointer"
						style="text-decoration: none;"
						on:click|preventDefault={() => (showAllLinks = false)}
					>
						<svg
							class="w-4 h-4 mr-2 text-gray-400"
							fill="none"
							stroke="currentColor"
							stroke-width="2"
							viewBox="0 0 24 24"
							xmlns="http://www.w3.org/2000/svg"
						>
							<path stroke="currentColor" stroke-width="2" d="M18 15l-6-6-6 6" />
						</svg>
						<span>{$i18n.t('Show Less')}</span>
					</a>
				{/if}
			</div>
		{/if}
	</div>
</Collapsible>
