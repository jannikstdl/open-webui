<script>
	import { goto } from '$app/navigation';
	import { getSessionUser, userSignIn } from '$lib/apis/auths';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME, config, user, socket } from '$lib/stores';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { page } from '$app/stores';

	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Hero from '$lib/components/fi-ts_landingpage/Hero.svelte';
	import FAQ from '$lib/components/fi-ts_landingpage/FAQ.svelte';
	import Features from '$lib/components/fi-ts_landingpage/Features.svelte';

	const i18n = getContext('i18n');

	let loaded = false;
	let email = '';
	let password = '';
	let isFocused = false;
	let isLoading = false;

	let showAdminForm = false;

	const setSessionUser = async (sessionUser) => {
		if (sessionUser) {
			console.log(sessionUser);
			toast.success($i18n.t("You're now logged in."));
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}

			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			goto('/');
		}
	};

	const signInHandler = async () => {
		isLoading = true;
		const sessionUser = await userSignIn(email, password).catch((error) => {
			toast.error(error);
			return null;
		});
		isLoading = false;
		await setSessionUser(sessionUser);
	};

	const submitHandler = async () => {
		await signInHandler();
	};

	const checkOauthCallback = async () => {
		if (!$page.url.hash) {
			return;
		}
		const hash = $page.url.hash.substring(1);
		if (!hash) {
			return;
		}
		const params = new URLSearchParams(hash);
		const token = params.get('token');
		if (!token) {
			return;
		}
		const sessionUser = await getSessionUser(token).catch((error) => {
			toast.error(error);
			return null;
		});
		if (!sessionUser) {
			return;
		}
		localStorage.token = token;
		await setSessionUser(sessionUser);
	};

	onMount(async () => {
		if ($user !== undefined) {
			await goto('/');
		}
		await checkOauthCallback();
		loaded = true;
		if (($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false) {
			await signInHandler();
		}
	});
</script>

<svelte:head>
	<title>
		{$WEBUI_NAME}
	</title>
</svelte:head>

{#if loaded}
	<div class="fixed m-10 z-50">
		<div class="flex space-x-2">
			<div class="self-center">
				<img
					crossorigin="anonymous"
					src="{WEBUI_BASE_URL}/static/logo.png"
					class="w-8 rounded-md"
					alt="logo"
				/>
			</div>
		</div>
	</div>

	<div class="overflow-y-auto h-screen">
		<div
			class="bg-white dark:bg-gray-950 min-h-screen w-full flex justify-center items-center font-mona"
		>
			<div class="w-full sm:max-w-md px-10 flex flex-col text-center">
				{#if ($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false}
					<!-- Falls Auth über Header gesetzt oder Auth deaktiviert ist -->
					<div class="my-auto pb-10 w-full">
						<div
							class="flex items-center justify-center gap-3 text-2xl sm:text-2xl text-center font-medium dark:text-gray-200"
						>
							<div
								class="font-bold text-2xl bg-gradient-to-r from-fits-blue via-gray-500 to-red-500 text-transparent bg-clip-text bg-[length:400%_400%] animate-gradient"
							>
								{$i18n.t('Signing in')}
								{$WEBUI_NAME}
							</div>
							<div>
								<Spinner />
							</div>
						</div>
					</div>
				{:else}
					<!-- Auth ist aktiv, normale Anzeige -->

					<!-- Überschrift immer auf der ersten Seite -->
					{#if !showAdminForm}
						<div class="mb-6">
							<div class="font-bold text-left text-3xl text-gray-700 dark:text-gray-300">
								Anmelden
								<br />
								<div
									class="font-bold text-left text-4xl bg-gradient-to-r from-fits-blue via-gray-600 to-red-600 text-transparent bg-clip-text bg-[length:400%_400%] animate-gradient"
								>
									{$WEBUI_NAME}
								</div>
							</div>
						</div>
					{/if}

					<div class="my-auto pb-10 w-full dark:text-gray-100">
						{#if !showAdminForm}
							<!-- Startseite mit Oauth -->
							{#if Object.keys($config?.oauth?.providers ?? {}).length > 0}
								<!-- Oauth Buttons -->
								<div class="flex flex-col space-y-2">
									{#if $config?.oauth?.providers?.google}
										<button
											class="flex items-center px-6 border-2 dark:border-gray-800 duration-300 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-800 w-full rounded-2xl dark:text-white text-sm py-3 transition justify-center"
											on:click={() => {
												window.location.href = `${WEBUI_BASE_URL}/oauth/google/login`;
											}}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 48 48"
												class="size-6 mr-3"
											>
												<path
													fill="#EA4335"
													d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
												/><path
													fill="#4285F4"
													d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
												/><path
													fill="#FBBC05"
													d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
												/><path
													fill="#34A853"
													d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
												/><path fill="none" d="M0 0h48v48H0z" />
											</svg>
											<span>{$i18n.t('Continue with {{provider}}', { provider: 'Google' })}</span>
										</button>
									{/if}

									{#if $config?.oauth?.providers?.microsoft}
										<button
											class="flex items-center px-6 border-2 dark:border-gray-800 duration-300 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-800 w-full rounded-2xl dark:text-white text-sm py-3 transition justify-center"
											on:click={() => {
												window.location.href = `${WEBUI_BASE_URL}/oauth/microsoft/login`;
											}}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 21 21"
												class="size-6 mr-3"
											>
												<rect x="1" y="1" width="9" height="9" fill="#f25022" /><rect
													x="1"
													y="11"
													width="9"
													height="9"
													fill="#00a4ef"
												/><rect x="11" y="1" width="9" height="9" fill="#7fba00" /><rect
													x="11"
													y="11"
													width="9"
													height="9"
													fill="#ffb900"
												/>
											</svg>
											<span>{$i18n.t('Continue with {{provider}}', { provider: 'Microsoft' })}</span
											>
										</button>
									{/if}

									{#if $config?.oauth?.providers?.oidc}
										<Tooltip
											content="IZ-Nummer (oder E-Mail) und aktuelles OfficeLAN Passwort"
											placement="left"
										>
											<button
												class="flex items-center px-6 border-2 dark:border-gray-800 duration-300 dark:bg-gray-900 hover:bg-gray-100 dark:hover:bg-gray-800 w-full rounded-2xl dark:text-white text-sm py-3 transition justify-center"
												on:click={() => {
													window.location.href = `${WEBUI_BASE_URL}/oauth/oidc/login`;
												}}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													fill="none"
													viewBox="0 0 24 24"
													stroke-width="1.5"
													stroke="currentColor"
													class="size-6 mr-3"
												>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z"
													/>
												</svg>

												<span
													>{$i18n.t('Continue with {{provider}}', {
														provider: $config?.oauth?.providers?.oidc ?? 'SSO'
													})}</span
												>
											</button>
										</Tooltip>
									{/if}
								</div>
							{/if}

							<!-- "oder" Trennstrich -->
							{#if Object.keys($config?.oauth?.providers ?? {}).length > 0}
								<div class="relative w-full">
									<hr class="w-64 h-px my-8 bg-gray-200 border-0 dark:bg-gray-700 mx-auto" />
									<div
										class="absolute px-3 font-medium text-gray-900 bg-white left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 dark:text-white dark:bg-gray-950"
									>
										{$i18n.t('or')}
									</div>
								</div>
							{/if}

							<!-- Administrativer Login Button -->
							<button
								class="text-sm rounded-2xl border border-gray-300 dark:border-gray-700 py-2 px-4 text-gray-600 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
								on:click={() => (showAdminForm = true)}
							>
								Administrativer Login
							</button>
						{:else}
							<!-- Admin Login -->
							<!-- Back Button -->
							<div class="flex items-center justify-start mb-4">
								<button
									class="rounded-full border border-gray-300 dark:border-gray-700 p-2 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
									on:click={() => (showAdminForm = false)}
								>
									<svg
										xmlns="http://www.w3.org/2000/svg"
										class="w-5 h-5 text-gray-600 dark:text-gray-300"
										fill="none"
										viewBox="0 0 24 24"
										stroke="currentColor"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											stroke-width="2"
											d="M15 19l-7-7 7-7"
										/>
									</svg>
								</button>
							</div>

							<!-- Administrativer Login Formular -->
							<form
								class="flex flex-col justify-center"
								on:submit|preventDefault={() => {
									submitHandler();
								}}
							>
								<div class="mb-1">
									<div class="flex flex-col mt-4">
										<div class="mb-2">
											<div class="text-sm font-medium text-left mb-1">{$i18n.t('Email')}</div>
											<input
												bind:value={email}
												type="email"
												class="px-5 py-3 rounded-2xl w-full text-sm outline-none border dark:border-none dark:bg-gray-900 focus:border-gray-300 focus:ring-1 focus:ring-gray-300"
												autocomplete="email"
												placeholder={$i18n.t('Enter Your Email')}
												required
											/>
										</div>

										<div>
											<div class="text-sm font-medium text-left mb-1">{$i18n.t('Password')}</div>

											<input
												bind:value={password}
												type="password"
												class="px-5 py-3 rounded-2xl w-full text-sm outline-none border dark:border-none dark:bg-gray-900 focus:border-gray-300 focus:ring-1 focus:ring-gray-300"
												placeholder={$i18n.t('Enter Your Password')}
												autocomplete="current-password"
												required
												on:focus={() => (isFocused = true)}
												on:blur={() => (isFocused = false)}
											/>
										</div>
									</div>

									<div class="mt-5">
										<button
											class="bg-gray-900 hover:bg-gray-800 w-full rounded-2xl text-white font-medium text-sm py-3 transition flex items-center justify-center"
											type="submit"
											disabled={isLoading}
										>
											{#if isLoading}
												<Spinner />
												<span class="ml-2">{$i18n.t('Sign in')}</span>
											{:else}
												{$i18n.t('Sign in')}
											{/if}
										</button>
									</div>
								</div>
							</form>
						{/if}
					</div>
				{/if}
			</div>
		</div>

		<div class="relative mt-[-25vh]">
			<Hero />
		</div>
		<Features />
		<FAQ />
	</div>
{/if}

<style>
	.font-mona {
		font-family:
			'Mona Sans',
			-apple-system,
			'Arimo',
			ui-sans-serif,
			system-ui,
			'Segoe UI',
			Roboto,
			Ubuntu,
			Cantarell,
			'Noto Sans',
			sans-serif,
			'Helvetica Neue',
			Arial,
			'Apple Color Emoji',
			'Segoe UI Emoji',
			'Segoe UI Symbol',
			'Noto Color Emoji';
	}

	.fade-in-up {
		transition:
			opacity 0.2s ease-out,
			transform 0.2s ease-out,
			max-height 0.2s ease-out;
		opacity: 0;
		transform: translateY(15px);
		max-height: 0;
		overflow: hidden;
	}

	.fade-in-up.show {
		opacity: 1;
		transform: translateY(0px);
		max-height: 30px;
	}
</style>
