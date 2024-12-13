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
	let isOAuthLoading = false;

	let showAdminForm = null;

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
		if ($page.url.hash) {
			isOAuthLoading = true;
		}
		await checkOauthCallback();
		loaded = true;
		if (($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false) {
			await signInHandler();
		}
	});

	const handleOAuthClick = () => {
		isOAuthLoading = true;
		if ($config?.oauth?.providers?.oidc) {
			window.location.href = `${WEBUI_BASE_URL}/oauth/oidc/login`;
		}
	};
</script>

<svelte:head>
	<title>
		{$WEBUI_NAME}
	</title>
</svelte:head>

{#if loaded}
	{#if isOAuthLoading}
		<!-- OAuth Loading Screen -->
		<div class="fixed inset-0 bg-white dark:bg-gray-950 z-50 flex items-center justify-center">
			<div class="text-center">
				<Spinner size="lg" />
				<div class="mt-4 text-gray-600 dark:text-gray-300">Anmeldung läuft...</div>
			</div>
		</div>
	{:else}
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
									class="font-bold text-2xl bg-gradient-to-r from-fits-blue via-gray-500 to-gray-700 text-transparent bg-clip-text bg-[length:400%_400%] animate-gradient"
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
									<div
										class={showAdminForm === null ? 'animate-slide-in-1' : 'animate-slide-in-left'}
									>
										Anmelden
									</div>
									<div
										class={showAdminForm === null ? 'animate-slide-in-2' : 'animate-slide-in-left'}
									>
										<div
											class="font-bold text-left text-4xl bg-gradient-to-r from-fits-blue via-gray-600 to-gray-700 text-transparent bg-clip-text bg-[length:400%_400%] animate-gradient"
										>
											{$WEBUI_NAME}
										</div>
									</div>
								</div>
							</div>
						{/if}

						<div class="my-auto pb-10 w-full dark:text-gray-100">
							{#if !showAdminForm}
								<!-- Startseite mit Oauth -->
								<div class={showAdminForm === null ? 'animate-fade-in' : 'animate-slide-in-left'}>
									<div class="flex flex-col space-y-2">
										<Tooltip
											content="IZ-Nummer (oder E-Mail) & aktuelles OfficeLAN-Passwort"
											placement="left"
										>
											<button
												class="oauth-button flex items-center px-6 duration-300 w-full rounded-2xl text-sm py-3 transition justify-center"
												on:click={handleOAuthClick}
												disabled={!$config?.oauth?.providers?.oidc}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													fill="none"
													viewBox="0 0 24 24"
													stroke-width="1.5"
													stroke="currentColor"
													class="size-6 mr-3 {!$config?.oauth?.providers?.oidc
														? 'text-red-500 dark:text-red-400'
														: ''}"
												>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														d="M15.75 5.25a3 3 0 0 1 3 3m3 0a6 6 0 0 1-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1 1 21.75 8.25Z"
													/>
												</svg>
												<span
													class={!$config?.oauth?.providers?.oidc
														? 'text-red-500 dark:text-red-400'
														: ''}
												>
													{#if $config?.oauth?.providers?.oidc}
														{$i18n.t('Continue with {{provider}}', {
															provider: $config?.oauth?.providers?.oidc ?? 'SSO'
														})}
													{:else}
														OAuth nicht konfiguriert
													{/if}
												</span>
											</button>
										</Tooltip>
									</div>

									<!-- "oder" Trennstrich -->
									<div class="relative w-full">
										<hr class="w-64 h-px my-8 bg-gray-200 border-0 dark:bg-gray-700 mx-auto" />
										<div
											class="absolute px-3 font-medium text-gray-900 bg-white left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 dark:text-white dark:bg-gray-950"
										>
											{$i18n.t('or')}
										</div>
									</div>

									<!-- Administrativer Login Button -->
									<button
										class="text-sm rounded-2xl border border-gray-300 dark:border-gray-700 py-2 px-4 text-gray-600 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
										on:click={() => (showAdminForm = true)}
									>
										Administrativer Login
									</button>
								</div>
							{:else}
								<!-- Admin Login -->
								<div class="animate-slide-in-left">
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
													<div class="text-sm font-medium text-left mb-1">
														{$i18n.t('Password')}
													</div>

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
								</div>
							{/if}
						</div>
					{/if}
				</div>
			</div>

			<div class="relative mt-[-30vh]">
				<Hero />
			</div>
			<Features />
			<FAQ />
		</div>
	{/if}
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

	.oauth-button {
		position: relative;
		color: #1a1a1a;
		background: rgba(255, 255, 255, 0.8);
		border: 2px solid rgba(0, 0, 0, 0.1);
		text-transform: uppercase;
		letter-spacing: 0.5px;
		font-weight: 500;
	}

	:global(.dark) .oauth-button {
		color: #ffffff;
		background: rgba(255, 255, 255, 0.1);
		border: 2px solid rgba(255, 255, 255, 0.2);
	}

	/* Nur aktivieren wenn der Button nicht disabled ist */
	.oauth-button:hover {
		z-index: 1;
		background: linear-gradient(90deg, #7e7a7a, #ad2525, #2a2a2a, #304b6a, #7e7a7a);
		background-size: 400% 100%; /* Erhöht für smootheren Übergang */
		border: 2px solid rgba(255, 255, 255, 0.4);
		box-shadow:
			0 0 15px rgba(2, 4, 24, 0.7),
			0 0 25px rgba(173, 37, 37, 0.3),
			/* Rötlicher Glow */ 0 0 35px rgba(48, 75, 106, 0.3); /* Bläulicher Glow */
		animation: gradientMove 4s linear infinite; /* Schneller & nahtloser Loop */
		color: white;
		text-shadow: 0 0 4px rgba(0, 0, 0, 0.5);
	}

	@keyframes gradientMove {
		0% {
			background-position: 0% 50%;
		}
		100% {
			background-position: 100% 50%;
		}
	}

	.oauth-button::before {
		content: '';
		position: absolute;
		top: -1px;
		right: -1px;
		bottom: -1px;
		left: -1px;
		background: inherit;
		filter: blur(20px);
		opacity: 0;
		transition: 0.4s ease-out;
	}

	.oauth-button:hover::before {
		opacity: 0.6;
		z-index: -1;
	}

	.animate-slide-in-1 {
		opacity: 0;
		transform: translateX(-20px);
		animation: slideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
	}

	.animate-slide-in-2 {
		opacity: 0;
		transform: translateX(-20px);
		animation: slideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
		animation-delay: 0.25s;
	}

	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateX(-20px);
		}
		to {
			opacity: 1;
			transform: translateX(0);
		}
	}

	.animate-fade-in {
		opacity: 0;
		transform: translateY(10px);
		animation: fadeInUp 0.4s cubic-bezier(0.4, 0, 0.2, 1) forwards;
		animation-delay: 0.6s;
	}

	@keyframes fadeInUp {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.animate-slide-in-left {
		animation: slideInLeft 0.2s ease forwards;
	}

	.animate-slide-out-right {
		animation: slideOutRight 0.2s ease forwards !important;
	}

	@keyframes slideInLeft {
		from {
			opacity: 0;
			transform: translateX(-20px);
		}
		to {
			opacity: 1;
			transform: translateX(0);
		}
	}

	@keyframes slideOutRight {
		from {
			opacity: 1;
			transform: translateX(0);
		}
		to {
			opacity: 0;
			transform: translateX(20px);
		}
	}
</style>
