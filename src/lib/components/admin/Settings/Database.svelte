<script lang="ts">
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	import { MAIL_DOMAIN_INTERNAL, MAIL_DOMAIN_EXTERNAL } from '$lib/constants';

	import { downloadDatabase } from '$lib/apis/utils';
	import { onMount, getContext } from 'svelte';
	import { config, user } from '$lib/stores';
	import { toast } from 'svelte-sonner';
	import { getAllUserChats } from '$lib/apis/chats';
	import { getAllUsers } from '$lib/apis/users';
	import { exportConfig, importConfig } from '$lib/apis/configs';
	import Collapsible from '$lib/components/common/Collapsible.svelte';

	const i18n = getContext('i18n');

	export let saveHandler: Function;

	let users: any[] = [];
	let debugInfo = '';
	let internalEmailsCount = 0;
	let externalEmailsCount = 0;
	let invalidUsersCount = 0;
	let invalidUsers: any[] = [];
	let invalidUsersOpen = false;
	let additionalActionsOpen = false;
	let visibilityHandler: () => void;

	/**
	 * Refresh users data and update email counts
	 */
	async function refreshUserData() {
		try {
			const response = await getAllUsers(localStorage.token);
			users = response.users;
			const { internalEmails, externalEmails, invalidUsers: invalid } = getValidEmails();
			internalEmailsCount = internalEmails.length;
			externalEmailsCount = externalEmails.length;
			invalidUsersCount = invalid.length;
			invalidUsers = invalid;
			console.log(
				`Loaded ${users.length} users, ${internalEmailsCount} internal emails, ${externalEmailsCount} external emails, ${invalidUsersCount} invalid users`
			);
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
	 * FI-TS Codeanpassung vom 10.7.2025: Verwaltung von E-Mail-Adressen für interne Mitarbeiter (@f-i-ts.de) und externe Partner (@extern.f-i-ts.de).
	 */
	function getValidEmails(): {
		internalEmails: string[];
		externalEmails: string[];
		invalidUsers: any[];
	} {
		if (!users || !Array.isArray(users) || users.length === 0) {
			toast.error('Keine Benutzer gefunden');
			return { internalEmails: [], externalEmails: [], invalidUsers: [] };
		}

		// Filter valid emails
		const internalEmails = users
			.filter((user) => {
				const email = user.email;
				if (!email) return false;

				const atIndex = email.indexOf('@');
				if (atIndex <= 0) return false;

				const domain = email.substring(atIndex + 1);

				// Exclude users with role "pending" and ensure other criteria are met
				return domain === MAIL_DOMAIN_INTERNAL && email !== $user?.email && user.role !== 'pending';
			})
			.map((user) => user.email);

		const externalEmails = users
			.filter((user) => {
				const email = user.email;
				if (!email) return false;

				const atIndex = email.indexOf('@');
				if (atIndex <= 0) return false;

				const domain = email.substring(atIndex + 1);

				// Exclude users with role "pending" and ensure other criteria are met
				return domain === MAIL_DOMAIN_EXTERNAL && email !== $user?.email && user.role !== 'pending';
			})
			.map((user) => user.email);

		// Get invalid users (those that don't meet the criteria)
		const invalidUsers = users.filter((user) => {
			const email = user.email;
			if (!email) return true;

			const atIndex = email.indexOf('@');
			if (atIndex <= 0) return true;

			const domain = email.substring(atIndex + 1);

			// User is invalid if:
			// 1. It's the current user
			// 2. Role is pending
			// 3. Domain is not internal or external
			return (
				email === $user?.email ||
				user.role === 'pending' ||
				(domain !== MAIL_DOMAIN_INTERNAL && domain !== MAIL_DOMAIN_EXTERNAL)
			);
		});

		return { internalEmails, externalEmails, invalidUsers };
	}

	/**
	 * Get reason why a user is invalid
	 */
	function getInvalidUserReason(user: any): string {
		const email = user.email;
		if (!email) return 'Keine E-Mail-Adresse vorhanden';

		const atIndex = email.indexOf('@');
		if (atIndex <= 0) return 'Ungültige E-Mail-Adresse (kein @ Symbol)';

		const domain = email.substring(atIndex + 1);

		if (email === $user?.email) return 'Eigener Account (wird ausgeschlossen)';
		if (user.role === 'pending') return 'Status: pending (wird ausgeschlossen)';
		if (domain !== MAIL_DOMAIN_INTERNAL && domain !== MAIL_DOMAIN_EXTERNAL) {
			return `Ungültige Domain: ${domain} (nur @f-i-ts.de und @extern.f-i-ts.de erlaubt)`;
		}

		return 'Unbekannter Grund';
	}

	/**
	 * Copy all email addresses to clipboard
	 */
	function copyAllEmailsToClipboard() {
		try {
			const { internalEmails, externalEmails } = getValidEmails();
			const allEmails = [...internalEmails, ...externalEmails];

			if (allEmails.length === 0) {
				toast.error('Keine Benutzer mit valider E-Mail-Adresse gefunden');
				return;
			}

			// Create formatted text and copy to clipboard
			const emailText = allEmails.join(';');
			navigator.clipboard
				.writeText(emailText)
				.then(() => {
					toast.success(`${allEmails.length} E-Mail-Adressen in die Zwischenablage kopiert`);
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
	 * Copy internal email addresses to clipboard
	 */
	function copyInternalEmailsToClipboard() {
		try {
			const { internalEmails } = getValidEmails();

			if (internalEmails.length === 0) {
				toast.error('Keine internen Benutzer mit valider E-Mail-Adresse gefunden');
				return;
			}

			// Create formatted text and copy to clipboard
			const emailText = internalEmails.join(';');
			navigator.clipboard
				.writeText(emailText)
				.then(() => {
					toast.success(
						`${internalEmails.length} interne E-Mail-Adressen in die Zwischenablage kopiert`
					);
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
	 * Copy external email addresses to clipboard
	 */
	function copyExternalEmailsToClipboard() {
		try {
			const { externalEmails } = getValidEmails();

			if (externalEmails.length === 0) {
				toast.error('Keine externen Benutzer mit valider E-Mail-Adresse gefunden');
				return;
			}

			// Create formatted text and copy to clipboard
			const emailText = externalEmails.join(';');
			navigator.clipboard
				.writeText(emailText)
				.then(() => {
					toast.success(
						`${externalEmails.length} externe E-Mail-Adressen in die Zwischenablage kopiert`
					);
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
	 * Generate CSV file with all users data
	 */
	function handleEmailAction() {
		try {
			if (users.length === 0) {
				toast.error('Keine Benutzer gefunden');
				return;
			}

			// Create CSV header
			const csvHeader = 'Name,E-Mail,Rolle,Status\n';

			// Create CSV rows
			const csvRows = users
				.map((user) => {
					const name = (user.name || 'Unbekannt').replace(/"/g, '""');
					const email = (user.email || 'Keine E-Mail').replace(/"/g, '""');
					const role = (user.role || 'Keine Rolle').replace(/"/g, '""');
					const status = getValidEmails().invalidUsers.some((invalid) => invalid.id === user.id)
						? 'Invalide'
						: 'Gültig';

					return `"${name}","${email}","${role}","${status}"`;
				})
				.join('\n');

			// Combine header and rows
			const csvContent = csvHeader + csvRows;

			// Create and download CSV file
			const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8' });
			saveAs(blob, `users-export-${Date.now()}.csv`);

			toast.success(`CSV-Datei mit ${users.length} Benutzern heruntergeladen`);
		} catch (error: any) {
			toast.error(`Fehler: ${error?.message || 'Unbekannter Fehler'}`);
			console.error(error);
		}
	}

	/**
	 * Open email client with all users as BCC
	 * Uses a more robust approach for large email lists
	 */
	function openEmail() {
		try {
			const { internalEmails, externalEmails } = getValidEmails();
			const allEmails = [...internalEmails, ...externalEmails];

			if (allEmails.length === 0) {
				toast.error('Keine Benutzer mit valider E-Mail-Adresse gefunden');
				return;
			}

			// For large email lists, create a temporary file instead of mailto link
			if (allEmails.length > 100) {
				// Create a temporary file with all emails
				const emailText = allEmails.join('\n');
				const blob = new Blob([emailText], { type: 'text/plain;charset=utf-8' });
				const url = URL.createObjectURL(blob);

				// Create a download link
				const a = document.createElement('a');
				a.href = url;
				a.download = `email-list-${Date.now()}.txt`;
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
				URL.revokeObjectURL(url);

				toast.success(
					`E-Mail-Liste mit ${allEmails.length} Adressen heruntergeladen. Bitte importieren Sie diese in Ihr E-Mail-Programm.`
				);
				return;
			}

			// For smaller lists, use mailto link
			const emailList = allEmails.join(';');
			const mailtoLink = `mailto:?bcc=${encodeURIComponent(emailList)}`;

			console.log('Attempting to open email client with link length:', mailtoLink.length);

			// Method 1: Direct window.open approach
			const mailWindow = window.open(mailtoLink, '_blank');

			if (!mailWindow) {
				console.warn('Failed to open email client with window.open, trying fallback method');

				// Method 2: Fallback to location.href if window.open is blocked
				window.location.href = mailtoLink;
			}

			toast.success(`E-Mail an ${allEmails.length} Benutzer vorbereitet`);
		} catch (error: any) {
			toast.error(`Fehler: ${error?.message || 'Unbekannter Fehler'}`);
			console.error('Error opening email client:', error);
		}
	}

	// Kopierfunktionen
	function copyAllExceptInvalidToClipboard() {
		const { internalEmails, externalEmails } = getValidEmails();
		const allValid = [...internalEmails, ...externalEmails];
		if (allValid.length === 0) {
			toast.error('Keine gültigen E-Mail-Adressen gefunden');
			return;
		}
		const emailText = allValid.join(';');
		navigator.clipboard.writeText(emailText).then(() => {
			toast.success(`${allValid.length} gültige E-Mail-Adressen kopiert`);
		});
	}

	function copyReallyAllToClipboard() {
		const { internalEmails, externalEmails, invalidUsers } = getValidEmails();
		const allValid = [...internalEmails, ...externalEmails];
		const allInvalid = invalidUsers.map((u) => u.email).filter(Boolean);
		const all = [...allValid, ...allInvalid];
		if (all.length === 0) {
			toast.error('Keine E-Mail-Adressen gefunden');
			return;
		}
		const emailText = all.join(';');
		navigator.clipboard.writeText(emailText).then(() => {
			toast.success(`${all.length} E-Mail-Adressen kopiert (inkl. invalide)`);
		});
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

			<hr class="border-gray-50 dark:border-gray-850 my-1" />

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

			<!-- FI-TS E-Mail-Verwaltung -->
			<div class="space-y-6">
				<!-- Header -->
				<div class="pt-3">
					<div class="text-sm font-medium text-gray-900 dark:text-white">
						FI-TS E-Mail-Verwaltung
					</div>
					<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
						Verwalte und exportiere Benutzer-E-Mail-Adressen
					</p>
				</div>

				<!-- Stats Cards -->
				<div class="grid grid-cols-2 md:grid-cols-4 gap-4">
					<div
						class="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm"
					>
						<div class="flex items-center">
							<div class="flex-shrink-0">
								<div
									class="w-8 h-8 bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center"
								>
									<svg
										class="w-4 h-4 text-gray-600 dark:text-gray-400"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z"
										/>
									</svg>
								</div>
							</div>
							<div class="ml-3">
								<p class="text-sm font-medium text-gray-500 dark:text-gray-400">Gesamt</p>
								<p class="text-2xl font-semibold text-gray-900 dark:text-white">{users.length}</p>
							</div>
						</div>
					</div>

					<div
						class="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm"
					>
						<div class="flex items-center">
							<div class="flex-shrink-0">
								<div
									class="w-8 h-8 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center"
								>
									<svg
										class="w-4 h-4 text-green-600 dark:text-green-400"
										fill="currentColor"
										viewBox="0 0 20 20"
									>
										<path
											fill-rule="evenodd"
											d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
											clip-rule="evenodd"
										/>
									</svg>
								</div>
							</div>
							<div class="ml-3">
								<p class="text-sm font-medium text-gray-500 dark:text-gray-400">Interne</p>
								<p class="text-2xl font-semibold text-green-600 dark:text-green-400">
									{internalEmailsCount}
								</p>
							</div>
						</div>
					</div>

					<div
						class="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm"
					>
						<div class="flex items-center">
							<div class="flex-shrink-0">
								<div
									class="w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center"
								>
									<svg
										class="w-4 h-4 text-blue-600 dark:text-blue-400"
										fill="currentColor"
										viewBox="0 0 20 20"
									>
										<path
											fill-rule="evenodd"
											d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
											clip-rule="evenodd"
										/>
									</svg>
								</div>
							</div>
							<div class="ml-3">
								<p class="text-sm font-medium text-gray-500 dark:text-gray-400">Externe</p>
								<p class="text-2xl font-semibold text-blue-600 dark:text-blue-400">
									{externalEmailsCount}
								</p>
							</div>
						</div>
					</div>

					<div
						class="bg-white dark:bg-gray-800 p-4 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm"
					>
						<div class="flex items-center">
							<div class="flex-shrink-0">
								<div
									class="w-8 h-8 bg-red-100 dark:bg-red-900 rounded-lg flex items-center justify-center"
								>
									<svg
										class="w-4 h-4 text-red-600 dark:text-red-400"
										fill="currentColor"
										viewBox="0 0 20 20"
									>
										<path
											fill-rule="evenodd"
											d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
											clip-rule="evenodd"
										/>
									</svg>
								</div>
							</div>
							<div class="ml-3">
								<p class="text-sm font-medium text-gray-500 dark:text-gray-400">Invalide</p>
								<p class="text-2xl font-semibold text-red-600 dark:text-red-400">
									{invalidUsersCount}
								</p>
							</div>
						</div>
					</div>
				</div>

				<!-- Quick Actions -->
				<div
					class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm"
				>
					<div class="px-6 py-4 border-b border-gray-200 dark:border-gray-700">
						<h4 class="text-md font-medium text-gray-900 dark:text-white">Schnelle Aktionen</h4>
						<p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
							Kopiere E-Mail-Adressen direkt in die Zwischenablage
						</p>
					</div>
					<div class="p-6 space-y-3">
						<button
							class="w-full flex items-center px-4 py-3 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg transition-colors group"
							type="button"
							on:click={copyAllEmailsToClipboard}
						>
							<div class="flex items-center">
								<div
									class="flex-shrink-0 w-10 h-10 bg-white dark:bg-gray-800 rounded-lg flex items-center justify-center shadow-sm"
								>
									<svg
										class="w-5 h-5 text-gray-600 dark:text-gray-400"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
										/>
									</svg>
								</div>
								<div class="ml-4 text-left">
									<p class="text-sm font-medium text-gray-900 dark:text-white">
										Kopiere alle gültigen
									</p>
									<p class="text-xs text-gray-500 dark:text-gray-400">
										{internalEmailsCount + externalEmailsCount} E-Mail-Adressen
									</p>
								</div>
							</div>
						</button>

						<button
							class="w-full flex items-center px-4 py-3 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg transition-colors group"
							type="button"
							on:click={copyReallyAllToClipboard}
						>
							<div class="flex items-center">
								<div
									class="flex-shrink-0 w-10 h-10 bg-white dark:bg-gray-800 rounded-lg flex items-center justify-center shadow-sm"
								>
									<svg
										class="w-5 h-5 text-gray-600 dark:text-gray-400"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
										/>
									</svg>
								</div>
								<div class="ml-4 text-left">
									<p class="text-sm font-medium text-gray-900 dark:text-white">Kopiere alle</p>
									<p class="text-xs text-gray-500 dark:text-gray-400">
										Inkl. invalide Benutzer ({users.length} E-Mail-Adressen)
									</p>
								</div>
							</div>
						</button>
					</div>
				</div>

				<!-- Additional Actions -->
				<Collapsible
					title={null}
					className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm"
					buttonClassName="w-full text-left px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
					bind:open={additionalActionsOpen}
				>
					<div class="flex items-center w-full">
						<div class="flex items-center flex-1">
							<div
								class="flex-shrink-0 w-8 h-8 bg-gray-100 dark:bg-gray-700 rounded-lg flex items-center justify-center"
							>
								<svg
									class="w-4 h-4 text-gray-600 dark:text-gray-400"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2"
										d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
									/>
								</svg>
							</div>
							<div class="ml-3">
								<h4 class="text-md font-medium text-gray-900 dark:text-white">Weitere Aktionen</h4>
								<p class="text-sm text-gray-500 dark:text-gray-400">
									Spezielle Funktionen für E-Mail-Verwaltung
								</p>
							</div>
						</div>
						<div class="flex-shrink-0 ml-4">
							{#if additionalActionsOpen}
								<svg
									class="w-5 h-5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2.5"
										d="M5 15l7-7 7 7"
									/>
								</svg>
							{:else}
								<svg
									class="w-5 h-5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition"
									fill="none"
									stroke="currentColor"
									viewBox="0 0 24 24"
								>
									<path
										stroke-linecap="round"
										stroke-linejoin="round"
										stroke-width="2.5"
										d="M19 9l-7 7-7-7"
									/>
								</svg>
							{/if}
						</div>
					</div>
					<div slot="content" class="border-t border-gray-200 dark:border-gray-700">
						<div class="p-6 grid grid-cols-1 md:grid-cols-2 gap-3">
							<button
								class="flex items-center px-4 py-3 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg transition-colors group"
								type="button"
								on:click={copyInternalEmailsToClipboard}
							>
								<div class="flex items-center">
									<div
										class="flex-shrink-0 w-8 h-8 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center"
									>
										<svg
											class="w-4 h-4 text-green-600 dark:text-green-400"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												stroke-width="2"
												d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
											/>
										</svg>
									</div>
									<div class="ml-3 text-left">
										<p class="text-sm font-medium text-gray-900 dark:text-white">Nur interne</p>
										<p class="text-xs text-gray-500 dark:text-gray-400">
											{internalEmailsCount} E-Mails
										</p>
									</div>
								</div>
							</button>

							<button
								class="flex items-center px-4 py-3 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg transition-colors group"
								type="button"
								on:click={copyExternalEmailsToClipboard}
							>
								<div class="flex items-center">
									<div
										class="flex-shrink-0 w-8 h-8 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center"
									>
										<svg
											class="w-4 h-4 text-blue-600 dark:text-blue-400"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												stroke-width="2"
												d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
											/>
										</svg>
									</div>
									<div class="ml-3 text-left">
										<p class="text-sm font-medium text-gray-900 dark:text-white">Nur externe</p>
										<p class="text-xs text-gray-500 dark:text-gray-400">
											{externalEmailsCount} E-Mails
										</p>
									</div>
								</div>
							</button>

							<button
								class="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg transition-colors group"
								type="button"
								on:click={openEmail}
								title="Bei vielen E-Mail-Adressen wird automatisch eine Datei zum Download erstellt"
							>
								<div class="flex items-center">
									<div
										class="flex-shrink-0 w-8 h-8 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center"
									>
										<svg
											class="w-4 h-4 text-purple-600 dark:text-purple-400"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												stroke-width="2"
												d="M3 8l7.89 4.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
											/>
										</svg>
									</div>
									<div class="ml-3 text-left">
										<p class="text-sm font-medium text-gray-900 dark:text-white">
											E-Mail-Client öffnen
										</p>
										<p class="text-xs text-gray-500 dark:text-gray-400">
											Alle gültigen E-Mails als BCC
										</p>
									</div>
								</div>
								<svg
									class="w-4 h-4 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300"
									fill="currentColor"
									viewBox="0 0 20 20"
								>
									<path
										fill-rule="evenodd"
										d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
										clip-rule="evenodd"
									/>
								</svg>
							</button>

							<button
								class="flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-700 hover:bg-gray-100 dark:hover:bg-gray-600 rounded-lg transition-colors group"
								type="button"
								on:click={handleEmailAction}
							>
								<div class="flex items-center">
									<div
										class="flex-shrink-0 w-8 h-8 bg-orange-100 dark:bg-orange-900 rounded-lg flex items-center justify-center"
									>
										<svg
											class="w-4 h-4 text-orange-600 dark:text-orange-400"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												stroke-width="2"
												d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
											/>
										</svg>
									</div>
									<div class="ml-3 text-left">
										<p class="text-sm font-medium text-gray-900 dark:text-white">
											Als Datei herunterladen
										</p>
										<p class="text-xs text-gray-500 dark:text-gray-400">E-Mail-Liste (.txt)</p>
									</div>
								</div>
								<svg
									class="w-4 h-4 text-gray-400 group-hover:text-gray-600 dark:group-hover:text-gray-300"
									fill="currentColor"
									viewBox="0 0 20 20"
								>
									<path
										fill-rule="evenodd"
										d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
										clip-rule="evenodd"
									/>
								</svg>
							</button>
						</div>
					</div>
				</Collapsible>

				<!-- Invalid Users Collapsible Table -->
				{#if invalidUsersCount > 0}
					<Collapsible
						title={null}
						className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm"
						buttonClassName="w-full text-left px-6 py-4 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
						bind:open={invalidUsersOpen}
					>
						<div class="flex items-center w-full">
							<div class="flex items-center flex-1">
								<div
									class="flex-shrink-0 w-8 h-8 bg-red-100 dark:bg-red-900 rounded-lg flex items-center justify-center"
								>
									<svg
										class="w-4 h-4 text-red-600 dark:text-red-400"
										fill="currentColor"
										viewBox="0 0 20 20"
									>
										<path
											fill-rule="evenodd"
											d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
											clip-rule="evenodd"
										/>
									</svg>
								</div>
								<div class="ml-3">
									<h4 class="text-md font-medium text-gray-900 dark:text-white">
										Ausgeschlossene Benutzer
									</h4>
									<p class="text-sm text-gray-500 dark:text-gray-400">
										{invalidUsersCount} Benutzer wurden aus der E-Mail-Liste ausgeschlossen
									</p>
								</div>
							</div>
							<div class="flex-shrink-0 ml-4">
								{#if invalidUsersOpen}
									<svg
										class="w-5 h-5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2.5"
											d="M5 15l7-7 7 7"
										/>
									</svg>
								{:else}
									<svg
										class="w-5 h-5 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition"
										fill="none"
										stroke="currentColor"
										viewBox="0 0 24 24"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2.5"
											d="M19 9l-7 7-7-7"
										/>
									</svg>
								{/if}
							</div>
						</div>
						<div slot="content" class="border-t border-gray-200 dark:border-gray-700">
							<div class="overflow-hidden">
								<table class="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
									<thead class="bg-gray-50 dark:bg-gray-700">
										<tr>
											<th
												scope="col"
												class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"
											>
												Name
											</th>
											<th
												scope="col"
												class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"
											>
												E-Mail
											</th>
											<th
												scope="col"
												class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"
											>
												Rolle
											</th>
											<th
												scope="col"
												class="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-300 uppercase tracking-wider"
											>
												Grund
											</th>
										</tr>
									</thead>
									<tbody
										class="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700"
									>
										{#each invalidUsers as user}
											<tr class="hover:bg-gray-50 dark:hover:bg-gray-700">
												<td
													class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-white"
												>
													{user.name || 'Unbekannt'}
												</td>
												<td
													class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300 font-mono"
												>
													{user.email || 'Keine E-Mail'}
												</td>
												<td class="px-6 py-4 whitespace-nowrap">
													<span
														class="inline-flex px-2 py-1 text-xs font-semibold rounded-full bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200"
													>
														{user.role || 'Keine Rolle'}
													</span>
												</td>
												<td
													class="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-300"
												>
													{getInvalidUserReason(user)}
												</td>
											</tr>
										{/each}
									</tbody>
								</table>
							</div>
						</div>
					</Collapsible>
				{/if}
			</div>
		</div>
	</div>
</form>
