<script lang="ts">
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { MAIL_DOMAIN } from '$lib/constants';

	import { downloadDatabase } from '$lib/apis/utils';
	import { onMount, getContext } from 'svelte';
	import { config, user } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import { getAllUserChats } from '$lib/apis/chats';
	import { getAllUsers } from '$lib/apis/users';
	import { exportConfig, importConfig } from '$lib/apis/configs';

	const i18n = getContext('i18n');

	export let saveHandler: Function;

	let users: any[] = [];
	let debugInfo = '';
	let emailsCount = 0;
	let visibilityHandler: () => void;

	/**
	 * FI-TS_custom 29.08.2025
	 */
	async function refreshUserData() {
		try {
			users = await getAllUsers(localStorage.token);
			emailsCount = getValidEmails().length;
			console.log(`Loaded ${users.length} users, ${emailsCount} with valid emails`);
		} catch (error) {
			console.error('Error loading users:', error);
			toast.error('Fehler beim Laden der Benutzer');
		}
	}

	const exportAllUserChats = async () => {
		let blob = new Blob([JSON.stringify(await getAllUserChats(localStorage.token))], {
			type: 'application/json'
		});
		saveAs(blob, `all-chats-export-${Date.now()}.json`);
	};

	/**
	 * Get all valid email addresses based on criteria
	 */
	function getValidEmails(): string[] {
		if (!users || users.length === 0) {
			toast.error('Keine Benutzer gefunden');
			return [];
		}

		// Filter valid emails
		const validEmails = users
			.filter((user) => {
				const email = user.email;
				if (!email) return false;

				const atIndex = email.indexOf('@');
				if (atIndex <= 0) return false;

				const domain = email.substring(atIndex + 1);
				const localPart = email.substring(0, atIndex);

				// Exclude users with role "pending" and ensure other criteria are met
				return (
					localPart.includes('.') &&
					domain === MAIL_DOMAIN &&
					email !== $user?.email &&
					user.role !== 'pending'
				);
			})
			.map((user) => user.email);

		return validEmails;
	}

	/**
	 * Copy all email addresses to clipboard
	 */
	function copyEmailsToClipboard() {
		try {
			const validEmails = getValidEmails();

			// Update count for UI
			emailsCount = validEmails.length;

			if (validEmails.length === 0) {
				toast.error('Keine Benutzer mit valider E-Mail-Adresse gefunden');
				return;
			}

			// Create formatted text and copy to clipboard
			const emailText = validEmails.join(';');
			navigator.clipboard
				.writeText(emailText)
				.then(() => {
					toast.success(`${validEmails.length} E-Mail-Adressen in die Zwischenablage kopiert`);
				})
				.catch((err) => {
					console.error('Fehler beim Kopieren in die Zwischenablage:', err);
					toast.error('Fehler beim Kopieren in die Zwischenablage');

					// Fallback method: create a textarea element
					fallbackCopyToClipboard(emailText);
				});
		} catch (error: any) {
			toast.error(`Fehler: ${error?.message || 'Unbekannter Fehler'}`);
			console.error(error);
		}
	}

	/**
	 * Fallback method to copy text to clipboard
	 */
	function fallbackCopyToClipboard(text: string) {
		try {
			const textArea = document.createElement('textarea');
			textArea.value = text;
			textArea.style.position = 'fixed'; // Avoid scrolling to bottom
			document.body.appendChild(textArea);
			textArea.focus();
			textArea.select();

			const successful = document.execCommand('copy');
			document.body.removeChild(textArea);

			if (successful) {
				toast.success(`E-Mail-Adressen in die Zwischenablage kopiert`);
			} else {
				toast.error('Fehler beim Kopieren');
			}
		} catch (err) {
			toast.error('Fehler beim Kopieren in die Zwischenablage');
		}
	}

	/**
	 * Generate email list and download as text file
	 */
	function handleEmailAction() {
		try {
			const validEmails = getValidEmails();

			// Update count for UI
			emailsCount = validEmails.length;

			if (validEmails.length === 0) {
				toast.error('Keine Benutzer mit valider E-Mail-Adresse gefunden');
				return;
			}

			// Create download file with emails
			const emailText = validEmails.join('\n');
			const blob = new Blob([emailText], { type: 'text/plain;charset=utf-8' });
			saveAs(blob, `email-list-${Date.now()}.txt`);

			toast.success(`Liste mit ${validEmails.length} E-Mail-Adressen heruntergeladen`);
		} catch (error: any) {
			toast.error(`Fehler: ${error?.message || 'Unbekannter Fehler'}`);
			console.error(error);
		}
	}

	/**
	 * Open email client with all users as BCC
	 */
	function openEmail() {
		try {
			const validEmails = getValidEmails();

			// Update count for UI
			emailsCount = validEmails.length;

			if (validEmails.length === 0) {
				toast.error('Keine Benutzer mit valider E-Mail-Adresse gefunden');
				return;
			}

			// Create mailto link with all emails
			const emailList = validEmails.join(';');
			const mailtoLink = `mailto:?bcc=${encodeURIComponent(emailList)}`;

			console.log('Attempting to open email client with link length:', mailtoLink.length);

			// Method 1: Direct window.open approach
			const mailWindow = window.open(mailtoLink, '_blank');

			if (!mailWindow) {
				console.warn('Failed to open email client with window.open, trying fallback method');

				// Method 2: Fallback to location.href if window.open is blocked
				window.location.href = mailtoLink;
			}

			toast.success(`E-Mail an ${validEmails.length} Benutzer vorbereitet`);
		} catch (error: any) {
			toast.error(`Fehler: ${error?.message || 'Unbekannter Fehler'}`);
			console.error('Error opening email client:', error);
		}
	}

	onMount(() => {
		// Refresh user data when component mounts
		refreshUserData();

		// Set up visibility change listener to refresh data when tab becomes visible
		visibilityHandler = () => {
			if (document.visibilityState === 'visible') {
				refreshUserData();
			}
		};

		// Listen for visibility changes and component activation
		document.addEventListener('visibilitychange', visibilityHandler);

		// Clean up event listener when component is destroyed
		return () => {
			document.removeEventListener('visibilitychange', visibilityHandler);
		};
	});

	// This will make sure the data is refreshed even when navigating between settings tabs
	export function onActivate() {
		refreshUserData();
	}
</script>

<form
	class="flex flex-col h-full justify-between space-y-3 text-sm"
	on:submit|preventDefault={async () => {
		saveHandler();
	}}
>
	<div class=" space-y-3 overflow-y-scroll scrollbar-hidden h-full">
		<div>
			<div class=" mb-2 text-sm font-medium">{$i18n.t('Database')}</div>

			<input
				id="config-json-input"
				hidden
				type="file"
				accept=".json"
				on:change={(e) => {
					const file = e.target.files[0];
					const reader = new FileReader();

					reader.onload = async (e) => {
						const res = await importConfig(localStorage.token, JSON.parse(e.target.result)).catch(
							(error) => {
								toast.error(`${error}`);
							}
						);

						if (res) {
							toast.success($i18n.t('Config imported successfully'));
						}
						e.target.value = null;
					};

					reader.readAsText(file);
				}}
			/>

			<button
				type="button"
				class=" flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
				on:click={async () => {
					document.getElementById('config-json-input').click();
				}}
			>
				<div class=" self-center mr-3">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
						<path
							fill-rule="evenodd"
							d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
							clip-rule="evenodd"
						/>
					</svg>
				</div>
				<div class=" self-center text-sm font-medium">
					{$i18n.t('Import Config from JSON File')}
				</div>
			</button>

			<button
				type="button"
				class=" flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
				on:click={async () => {
					const config = await exportConfig(localStorage.token);
					const blob = new Blob([JSON.stringify(config)], {
						type: 'application/json'
					});
					saveAs(blob, `config-${Date.now()}.json`);
				}}
			>
				<div class=" self-center mr-3">
					<svg
						xmlns="http://www.w3.org/2000/svg"
						viewBox="0 0 16 16"
						fill="currentColor"
						class="w-4 h-4"
					>
						<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
						<path
							fill-rule="evenodd"
							d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
							clip-rule="evenodd"
						/>
					</svg>
				</div>
				<div class=" self-center text-sm font-medium">
					{$i18n.t('Export Config to JSON File')}
				</div>
			</button>

			{#if $config?.features.enable_admin_export ?? true}
				<hr class="border-gray-100 dark:border-gray-850 my-1" />
				<div class="  flex w-full justify-between">
					<!-- <div class=" self-center text-xs font-medium">{$i18n.t('Allow Chat Deletion')}</div> -->

					<button
						class=" flex rounded-md py-1.5 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
						type="button"
						on:click={() => {
							// exportAllUserChats();

							downloadDatabase(localStorage.token).catch((error) => {
								toast.error(`${error}`);
							});
						}}
					>
						<div class=" self-center mr-3">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 16 16"
								fill="currentColor"
								class="w-4 h-4"
							>
								<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
								<path
									fill-rule="evenodd"
									d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
									clip-rule="evenodd"
								/>
							</svg>
						</div>
						<div class=" self-center text-sm font-medium">{$i18n.t('Download Database')}</div>
					</button>
				</div>

				<button
					class=" flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					on:click={() => {
						exportAllUserChats();
					}}
				>
					<div class=" self-center mr-3">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
							<path
								fill-rule="evenodd"
								d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
					<div class=" self-center text-sm font-medium">
						{$i18n.t('Export All Chats (All Users)')}
					</div>
				</button>

				<button
					class=" flex rounded-md py-2 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					on:click={() => {
						exportUsers();
					}}
				>
					<div class=" self-center mr-3">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V3Z" />
							<path
								fill-rule="evenodd"
								d="M13 6H3v6a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2V6ZM8.75 7.75a.75.75 0 0 0-1.5 0v2.69L6.03 9.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.06 0l2.5-2.5a.75.75 0 1 0-1.06-1.06l-1.22 1.22V7.75Z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
					<div class=" self-center text-sm font-medium">
						{$i18n.t('Export Users')}
					</div>
				</button>
			{/if}

			<hr class="border-gray-100 dark:border-gray-850 my-1" />

			<!-- FI-TS_custom 08.11.2024 -->
			<div class="flex flex-col gap-2">
				<button
					class="flex rounded-md py-1.5 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
					type="button"
					on:click={copyEmailsToClipboard}
				>
					<div class="self-center mr-3">
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 16 16"
							fill="currentColor"
							class="w-4 h-4"
						>
							<path
								fill-rule="evenodd"
								d="M3.75 2A1.75 1.75 0 0 0 2 3.75v5.5c0 .966.784 1.75 1.75 1.75h1a.75.75 0 0 0 0-1.5h-1a.25.25 0 0 1-.25-.25v-5.5a.25.25 0 0 1 .25-.25h5.5a.25.25 0 0 1 .25.25v1a.75.75 0 0 0 1.5 0v-1A1.75 1.75 0 0 0 9.25 2h-5.5Z"
								clip-rule="evenodd"
							/>
							<path
								fill-rule="evenodd"
								d="M6.75 5A1.75 1.75 0 0 0 5 6.75v5.5c0 .966.784 1.75 1.75 1.75h5.5A1.75 1.75 0 0 0 14 12.25v-5.5A1.75 1.75 0 0 0 12.25 5h-5.5Zm5.5 1.5a.25.25 0 0 1 .25.25v5.5a.25.25 0 0 1-.25.25h-5.5a.25.25 0 0 1-.25-.25v-5.5a.25.25 0 0 1 .25-.25h5.5Z"
								clip-rule="evenodd"
							/>
						</svg>
					</div>
					<div class="self-center text-sm font-medium">
						E-Mail-Adressen in Zwischenablage kopieren ({emailsCount} valide aktive Benutzer)
					</div>
				</button>

				<div class="flex flex-row gap-2">
					<button
						class="flex rounded-md py-1.5 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
						type="button"
						on:click={handleEmailAction}
					>
						<div class="self-center mr-3">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 16 16"
								fill="currentColor"
								class="w-4 h-4"
							>
								<path
									d="M2.5 3A1.5 1.5 0 0 0 1 4.5v.793c.026.009.051.02.076.032L7.674 8.51c.206.1.446.1.652 0l6.598-3.185A.755.755 0 0 1 15 5.293V4.5A1.5 1.5 0 0 0 13.5 3h-11Z"
								/>
								<path
									d="M15 6.954 8.978 9.86a2.25 2.25 0 0 1-1.956 0L1 6.954V11.5A1.5 1.5 0 0 0 2.5 13h11a1.5 1.5 0 0 0 1.5-1.5V6.954Z"
									clip-rule="evenodd"
									fill-rule="evenodd"
								/>
							</svg>
						</div>
						<div class="self-center text-sm font-medium">E-Mail-Liste herunterladen</div>
					</button>

					<button
						class="flex rounded-md py-1.5 px-3 w-full hover:bg-gray-200 dark:hover:bg-gray-800 transition"
						type="button"
						on:click={openEmail}
						title="Bei vielen Benutzern kann der Browser möglicherweise den langen Link nicht verarbeiten"
					>
						<div class="self-center mr-3">
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 16 16"
								fill="currentColor"
								class="w-4 h-4"
							>
								<path
									d="M2.5 3A1.5 1.5 0 0 0 1 4.5v.793c.026.009.051.02.076.032L7.674 8.51c.206.1.446.1.652 0l6.598-3.185A.755.755 0 0 1 15 5.293V4.5A1.5 1.5 0 0 0 13.5 3h-11Z"
								/>
								<path
									d="M15 6.954 8.978 9.86a2.25 2.25 0 0 1-1.956 0L1 6.954V11.5A1.5 1.5 0 0 0 2.5 13h11a1.5 1.5 0 0 0 1.5-1.5V6.954Z"
									clip-rule="evenodd"
									fill-rule="evenodd"
								/>
							</svg>
						</div>
						<div class="self-center text-sm font-medium">E-Mail öffnen</div>
					</button>
				</div>
				<div class="text-xs text-gray-500 dark:text-gray-400 px-3 py-1">
					Hinweis: Bei vielen E-Mail-Adressen kann es sein dass das E-Mail-Programm nicht mehr
					öffnet da einige Browser die maximale Länge von URLs nicht unterstützen.
				</div>
			</div>
		</div>
	</div>

	<!-- <div class="flex justify-end pt-3 text-sm font-medium">
		<button
			class=" px-4 py-2 bg-emerald-700 hover:bg-emerald-800 text-gray-100 transition rounded-lg"
			type="submit"
		>
			{$i18n.t('Save')}
		</button>

	</div> -->
</form>
