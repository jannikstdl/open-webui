<script lang="ts">
	import hljs from 'highlight.js';

	import mermaid from 'mermaid';

	import { v4 as uuidv4 } from 'uuid';

	import { getContext, onMount, tick, onDestroy } from 'svelte';
	import { copyToClipboard } from '$lib/utils';

	// FI-TS_custom: unify background via app.css; do not import hljs theme
	// import 'highlight.js/styles/github-dark.min.css';

	import PyodideWorker from '$lib/workers/pyodide.worker?worker';
	import CodeEditor from '$lib/components/common/CodeEditor.svelte';
	import SvgPanZoom from '$lib/components/common/SVGPanZoom.svelte';
	import { config } from '$lib/stores';
	import { executeCode } from '$lib/apis/utils';
	import { toast } from 'svelte-sonner';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ChevronUpDown from '$lib/components/icons/ChevronUpDown.svelte';
	import CommandLine from '$lib/components/icons/CommandLine.svelte';
	import Cube from '$lib/components/icons/Cube.svelte';
	import Clipboard from '$lib/components/icons/Clipboard.svelte';
	import FloppyDisk from '$lib/components/icons/FloppyDisk.svelte';

	const i18n = getContext('i18n');

	export let id = '';
	export let edit = true;

	export let onSave = (e) => {};
	export let onUpdate = (e) => {};
	export let onPreview = (e) => {};

	export let save = false;
	export let run = true;
	export let preview = false;
	export let collapsed = false;

	export let token;
	export let lang = '';
	export let code = '';
	export let attributes = {};

	export let className = 'my-2';
	export let editorClassName = '';
export let stickyButtonsClassName = 'top-0';

	let pyodideWorker = null;

	let _code = '';
	$: if (code) {
		updateCode();
	}

	const updateCode = () => {
		_code = code;
	};

	let _token = null;

	let mermaidHtml = null;

	let highlightedCode = null;
	let executing = false;

	let stdout = null;
	let stderr = null;
	let result = null;
	let files = null;

	let copied = false;
	let saved = false;

	// FI-TS_custom: Visual toggle for wrapping long lines in readonly view (kept internal, no UI)
	let wrapLines = false;

	// FI-TS_custom: Compute sticky top offset and nudge header upward for perfect overlap
	let stickyTopStyle = '0px';
	$: {
		if (stickyButtonsClassName?.includes('top-8')) {
			stickyTopStyle = 'calc(2rem - 8px)';
		} else {
			stickyTopStyle = '-8px';
		}
	}

	// FI-TS_custom: Build highlighted HTML with line numbers for readonly view
	const buildNumberedHtml = (code: string, lang: string) => {
		const language = hljs.getLanguage(lang) ? lang : '';
		const lines = code.split('\n');
		return lines
			.map((line, idx) => {
				const highlighted = language
					? hljs.highlight(line, { language }).value
					: hljs.highlightAuto(line).value;
				return `<span class="line"><span class="ln">${idx + 1}</span><span class="lc">${highlighted || '&nbsp;'}</span></span>`;
			})
			.join('\n');
	};

	const collapseCodeBlock = () => {
		collapsed = !collapsed;
	};

	const saveCode = () => {
		saved = true;

		code = _code;
		onSave(code);

		setTimeout(() => {
			saved = false;
		}, 1000);
	};

	const copyCode = async () => {
		copied = true;
		await copyToClipboard(_code);

		setTimeout(() => {
			copied = false;
		}, 1000);
	};

	const previewCode = () => {
		onPreview(code);
	};

	const checkPythonCode = (str) => {
		// Check if the string contains typical Python syntax characters
		const pythonSyntax = [
			'def ',
			'else:',
			'elif ',
			'try:',
			'except:',
			'finally:',
			'yield ',
			'lambda ',
			'assert ',
			'nonlocal ',
			'del ',
			'True',
			'False',
			'None',
			' and ',
			' or ',
			' not ',
			' in ',
			' is ',
			' with '
		];

		for (let syntax of pythonSyntax) {
			if (str.includes(syntax)) {
				return true;
			}
		}

		// If none of the above conditions met, it's probably not Python code
		return false;
	};

	const executePython = async (code) => {
		result = null;
		stdout = null;
		stderr = null;

		executing = true;

		if ($config?.code?.engine === 'jupyter') {
			const output = await executeCode(localStorage.token, code).catch((error) => {
				toast.error(`${error}`);
				return null;
			});

			if (output) {
				if (output['stdout']) {
					stdout = output['stdout'];
					const stdoutLines = stdout.split('\n');

					for (const [idx, line] of stdoutLines.entries()) {
						if (line.startsWith('data:image/png;base64')) {
							if (files) {
								files.push({
									type: 'image/png',
									data: line
								});
							} else {
								files = [
									{
										type: 'image/png',
										data: line
									}
								];
							}

							if (stdout.startsWith(`${line}\n`)) {
								stdout = stdout.replace(`${line}\n`, ``);
							} else if (stdout.startsWith(`${line}`)) {
								stdout = stdout.replace(`${line}`, ``);
							}
						}
					}
				}

				if (output['result']) {
					result = output['result'];
					const resultLines = result.split('\n');

					for (const [idx, line] of resultLines.entries()) {
						if (line.startsWith('data:image/png;base64')) {
							if (files) {
								files.push({
									type: 'image/png',
									data: line
								});
							} else {
								files = [
									{
										type: 'image/png',
										data: line
									}
								];
							}

							if (result.startsWith(`${line}\n`)) {
								result = result.replace(`${line}\n`, ``);
							} else if (result.startsWith(`${line}`)) {
								result = result.replace(`${line}`, ``);
							}
						}
					}
				}

				output['stderr'] && (stderr = output['stderr']);
			}

			executing = false;
		} else {
			executePythonAsWorker(code);
		}
	};

	const executePythonAsWorker = async (code) => {
		let packages = [
			/\bimport\s+requests\b|\bfrom\s+requests\b/.test(code) ? 'requests' : null,
			/\bimport\s+bs4\b|\bfrom\s+bs4\b/.test(code) ? 'beautifulsoup4' : null,
			/\bimport\s+numpy\b|\bfrom\s+numpy\b/.test(code) ? 'numpy' : null,
			/\bimport\s+pandas\b|\bfrom\s+pandas\b/.test(code) ? 'pandas' : null,
			/\bimport\s+matplotlib\b|\bfrom\s+matplotlib\b/.test(code) ? 'matplotlib' : null,
			/\bimport\s+seaborn\b|\bfrom\s+seaborn\b/.test(code) ? 'seaborn' : null,
			/\bimport\s+sklearn\b|\bfrom\s+sklearn\b/.test(code) ? 'scikit-learn' : null,
			/\bimport\s+scipy\b|\bfrom\s+scipy\b/.test(code) ? 'scipy' : null,
			/\bimport\s+re\b|\bfrom\s+re\b/.test(code) ? 'regex' : null,
			/\bimport\s+seaborn\b|\bfrom\s+seaborn\b/.test(code) ? 'seaborn' : null,
			/\bimport\s+sympy\b|\bfrom\s+sympy\b/.test(code) ? 'sympy' : null,
			/\bimport\s+tiktoken\b|\bfrom\s+tiktoken\b/.test(code) ? 'tiktoken' : null,
			/\bimport\s+pytz\b|\bfrom\s+pytz\b/.test(code) ? 'pytz' : null
		].filter(Boolean);

		console.log(packages);

		pyodideWorker = new PyodideWorker();

		pyodideWorker.postMessage({
			id: id,
			code: code,
			packages: packages
		});

		setTimeout(() => {
			if (executing) {
				executing = false;
				stderr = 'Execution Time Limit Exceeded';
				pyodideWorker.terminate();
			}
		}, 60000);

		pyodideWorker.onmessage = (event) => {
			console.log('pyodideWorker.onmessage', event);
			const { id, ...data } = event.data;

			console.log(id, data);

			if (data['stdout']) {
				stdout = data['stdout'];
				const stdoutLines = stdout.split('\n');

				for (const [idx, line] of stdoutLines.entries()) {
					if (line.startsWith('data:image/png;base64')) {
						if (files) {
							files.push({
								type: 'image/png',
								data: line
							});
						} else {
							files = [
								{
									type: 'image/png',
									data: line
								}
							];
						}

						if (stdout.startsWith(`${line}\n`)) {
							stdout = stdout.replace(`${line}\n`, ``);
						} else if (stdout.startsWith(`${line}`)) {
							stdout = stdout.replace(`${line}`, ``);
						}
					}
				}
			}

			if (data['result']) {
				result = data['result'];
				const resultLines = result.split('\n');

				for (const [idx, line] of resultLines.entries()) {
					if (line.startsWith('data:image/png;base64')) {
						if (files) {
							files.push({
								type: 'image/png',
								data: line
							});
						} else {
							files = [
								{
									type: 'image/png',
									data: line
								}
							];
						}

						if (result.startsWith(`${line}\n`)) {
							result = result.replace(`${line}\n`, ``);
						} else if (result.startsWith(`${line}`)) {
							result = result.replace(`${line}`, ``);
						}
					}
				}
			}

			data['stderr'] && (stderr = data['stderr']);
			data['result'] && (result = data['result']);

			executing = false;
		};

		pyodideWorker.onerror = (event) => {
			console.log('pyodideWorker.onerror', event);
			executing = false;
		};
	};

	let debounceTimeout;

	const drawMermaidDiagram = async () => {
		try {
			if (await mermaid.parse(code)) {
				const { svg } = await mermaid.render(`mermaid-${uuidv4()}`, code);
				mermaidHtml = svg;
			}
		} catch (error) {
			console.log('Error:', error);
		}
	};

	const render = async () => {
		if (lang === 'mermaid' && (token?.raw ?? '').slice(-4).includes('```')) {
			(async () => {
				await drawMermaidDiagram();
			})();
		}

		onUpdate(token);
	};

	$: if (token) {
		if (JSON.stringify(token) !== JSON.stringify(_token)) {
			_token = token;
		}
	}

	$: if (_token) {
		render();
	}

	$: if (attributes) {
		onAttributesUpdate();
	}

	const onAttributesUpdate = () => {
		if (attributes?.output) {
			// Create a helper function to unescape HTML entities
			const unescapeHtml = (html) => {
				const textArea = document.createElement('textarea');
				textArea.innerHTML = html;
				return textArea.value;
			};

			try {
				// Unescape the HTML-encoded string
				const unescapedOutput = unescapeHtml(attributes.output);

				// Parse the unescaped string into JSON
				const output = JSON.parse(unescapedOutput);

				// Assign the parsed values to variables
				stdout = output.stdout;
				stderr = output.stderr;
				result = output.result;
			} catch (error) {
				console.error('Error:', error);
			}
		}
	};

	onMount(async () => {
		if (token) {
			onUpdate(token);
		}

		if (document.documentElement.classList.contains('dark')) {
			mermaid.initialize({
				startOnLoad: true,
				theme: 'dark',
				securityLevel: 'loose'
			});
		} else {
			mermaid.initialize({
				startOnLoad: true,
				theme: 'default',
				securityLevel: 'loose'
			});
		}
	});

	onDestroy(() => {
		if (pyodideWorker) {
			pyodideWorker.terminate();
		}
	});
</script>

<div>
    <div class="relative {className} flex flex-col rounded-2xl" dir="ltr">
		{#if lang === 'mermaid'}
			{#if mermaidHtml}
				<SvgPanZoom
					className=" border border-gray-100 dark:border-gray-850 rounded-xl max-h-fit overflow-hidden"
					svg={mermaidHtml}
					content={_token.text}
				/>
			{:else}
				<pre class="mermaid">{code}</pre>
			{/if}
		{:else}
			<!-- FI-TS_custom: Minimalistic header (language + actions) with dark-mode background -->
			<div class="sticky z-10 flex items-center justify-between gap-2 text-xs text-gray-700 dark:text-gray-200 bg-gray-50 dark:bg-gray-800 rounded-t-2xl px-3 py-2 dark:border-b dark:border-gray-700/60" style="top: {stickyTopStyle};">
				<div class="flex items-center gap-2 min-w-0">
					<div class="px-2 py-0.5 rounded-md bg-transparent text-gray-600 dark:text-gray-300 font-medium">
						{lang || 'text'}
					</div>
					{#if collapsed}
						<div class="truncate text-gray-500">{$i18n.t('Collapsed')}</div>
					{/if}
				</div>
				<div class="flex items-center gap-1.5">
					<button
						class="flex gap-1 items-center bg-transparent hover:bg-gray-200/70 dark:hover:bg-gray-700/70 transition rounded-md px-1.5 py-0.5"
						on:click={collapseCodeBlock}
						title={collapsed ? $i18n.t('Expand') : $i18n.t('Collapse')}
					>
						<ChevronUpDown className="size-3" />
						<span class="hidden sm:inline">{collapsed ? $i18n.t('Expand') : $i18n.t('Collapse')}</span>
					</button>

					<!-- Preview action omitted for minimal UI -->

					{#if ($config?.features?.enable_code_execution ?? true) && (lang.toLowerCase() === 'python' || lang.toLowerCase() === 'py' || (lang === '' && checkPythonCode(code)))}
						{#if executing}
							<div class="px-1.5 py-0.5 rounded-md text-gray-500 cursor-not-allowed">{$i18n.t('Running')}</div>
						{:else if run}
							<button
								class="flex gap-1 items-center bg-transparent hover:bg-gray-200/70 dark:hover:bg-gray-700/70 transition rounded-md px-1.5 py-0.5"
								on:click={async () => {
									code = _code;
									await tick();
									executePython(code);
								}}
								title={$i18n.t('Run')}
							>
								<CommandLine className="size-3" />
								<span class="hidden sm:inline">{$i18n.t('Run')}</span>
							</button>
						{/if}
					{/if}

					{#if save}
						<button
							class="flex gap-1 items-center bg-transparent hover:bg-gray-200/70 dark:hover:bg-gray-700/70 transition rounded-md px-1.5 py-0.5"
							on:click={saveCode}
							title={saved ? $i18n.t('Saved') : $i18n.t('Save')}
						>
							<FloppyDisk className="size-3" />
							<span class="hidden sm:inline">{saved ? $i18n.t('Saved') : $i18n.t('Save')}</span>
						</button>
					{/if}

					<!-- Wrap toggle intentionally omitted for minimal UI -->

					<button
						class="flex gap-1 items-center bg-transparent hover:bg-gray-200/70 dark:hover:bg-gray-700/70 transition rounded-md px-1.5 py-0.5"
						on:click={copyCode}
						title={copied ? $i18n.t('Copied') : $i18n.t('Copy')}
					>
						<Clipboard className="size-3" />
						<span class="hidden sm:inline">{copied ? $i18n.t('Copied') : $i18n.t('Copy')}</span>
					</button>
				</div>
			</div>

				<!-- FI-TS_custom: Code content container with consistent dark background -->
            <div class="language-{lang} {editorClassName ? editorClassName : ''} overflow-hidden bg-gray-50 dark:bg-gray-900/30 {executing || stdout || stderr || result ? '' : 'rounded-b-2xl'}">

				{#if !collapsed}
					{#if edit}
						<CodeEditor
							value={code}
							{id}
							{lang}
							onSave={() => {
								saveCode();
							}}
							onChange={(value) => {
								_code = value;
							}}
						/>
					{:else}
						<!-- FI-TS_custom: Readonly renderer with line numbers -->
						<pre class="precode hljs p-4 px-5 {wrapLines ? 'wrap' : ''} {wrapLines ? 'overflow-x-hidden' : 'overflow-x-auto'}" style="border-top-left-radius: 0px; border-top-right-radius: 0px; {(executing || stdout || stderr || result) && 'border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;'}">
							<code class="language-{lang} rounded-t-none text-sm code-with-lines">
								{@html buildNumberedHtml(code, lang)}
							</code>
						</pre>
					{/if}
				{:else}
					<!-- FI-TS_custom: Hidden lines placeholder (collapsed state) -->
					<div
						class="bg-gray-50 dark:bg-black dark:text-white rounded-b-xl! pt-2 pb-2 px-4 flex flex-col gap-2 text-xs"
					>
						<span class="text-gray-500 italic">
							{$i18n.t('{{COUNT}} hidden lines', {
								COUNT: code.split('\n').length
							})}
						</span>
					</div>
				{/if}
			</div>

			{#if !collapsed}
				<!-- FI-TS_custom: Matplotlib/plot output canvas background unified -->
				<div
					id="plt-canvas-{id}"
					class="bg-gray-50 dark:bg-black dark:text-white max-w-full overflow-x-auto scrollbar-hidden"
				/>

				{#if executing || stdout || stderr || result || files}
					<!-- FI-TS_custom: Execution output container background unified -->
					<div class="bg-gray-50 dark:bg-[#202123] dark:text-white rounded-b-lg! py-4 px-4 flex flex-col gap-2 rounded-b-2xl">
						{#if executing}
							<div class=" ">
								<div class=" text-gray-500 text-xs mb-1">{$i18n.t('STDOUT/STDERR')}</div>
								<div class="text-sm">{$i18n.t('Running...')}</div>
							</div>
						{:else}
							{#if stdout || stderr}
								<div class=" ">
									<div class=" text-gray-500 text-xs mb-1">{$i18n.t('STDOUT/STDERR')}</div>
									<div
										class="text-sm {stdout?.split('\n')?.length > 100
											? `max-h-96`
											: ''}  overflow-y-auto"
									>
										{stdout || stderr}
									</div>
								</div>
							{/if}
							{#if result || files}
								<div class=" ">
									<div class=" text-gray-500 text-xs mb-1">{$i18n.t('RESULT')}</div>
									{#if result}
										<div class="text-sm">{`${JSON.stringify(result)}`}</div>
									{/if}
									{#if files}
										<div class="flex flex-col gap-2">
											{#each files as file}
												{#if file.type.startsWith('image')}
													<img src={file.data} alt="Output" class=" w-full max-w-[36rem]" />
												{/if}
											{/each}
										</div>
									{/if}
								</div>
							{/if}
						{/if}
					</div>
				{/if}
			{/if}
		{/if}
	</div>
</div>

<style>
  /* FI-TS_custom: Minimalistic line numbers layout for readonly blocks */
  .code-with-lines {
    display: block;
    background: inherit;
  }
  .code-with-lines .line {
    display: grid;
    grid-template-columns: 2.5rem 1fr;
    gap: 0.75rem;
    background: inherit;
  }
  .code-with-lines .ln {
    color: rgb(209 213 219); /* text-gray-300 */
    opacity: 0.8;
    text-align: right;
    user-select: none;
    background: inherit;
  }
  .code-with-lines .lc {
    white-space: pre;
    background: inherit;
  }
  .precode.wrap .code-with-lines .lc {
    white-space: pre-wrap;
    word-break: break-word;
  }
</style>
