<script>
	import { toast } from 'svelte-sonner';

	import { onMount, getContext, tick } from 'svelte';
	import { goto } from '$app/navigation';

	import { getBackendConfig } from '$lib/apis';
	import { getSessionUser, userSignIn } from '$lib/apis/auths';

	import Spinner from '$lib/components/common/Spinner.svelte';
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';
	import { WEBUI_NAME, config, user, socket } from '$lib/stores';
	import { page } from '$app/stores';

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

	let ldapUsername = '';

	const querystringValue = (key) => {
		const querystring = window.location.search;
		const urlParams = new URLSearchParams(querystring);
		return urlParams.get(key);
	};

	const setSessionUser = async (sessionUser) => {
		if (sessionUser) {
			console.log(sessionUser);
			toast.success($i18n.t("You're now logged in."));
			if (sessionUser.token) {
				localStorage.token = sessionUser.token;
			}
			$socket.emit('user-join', { auth: { token: sessionUser.token } });
			await user.set(sessionUser);
			await config.set(await getBackendConfig());

			const redirectPath = querystringValue('redirect') || '/';
			goto(redirectPath);
		}
	};

	const signInHandler = async () => {
		isLoading = true;
		const sessionUser = await userSignIn(email, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
		isLoading = false;
		await setSessionUser(sessionUser);
	};

	const ldapSignInHandler = async () => {
		const sessionUser = await ldapUserSignIn(ldapUsername, password).catch((error) => {
			toast.error(`${error}`);
			return null;
		});
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
			toast.error(`${error}`);
			return null;
		});
		if (!sessionUser) {
			return;
		}
		localStorage.token = token;
		await setSessionUser(sessionUser);
	};

	let onboarding = false;

	async function setLogoImage() {
		await tick();
		const logo = document.getElementById('logo');

		if (logo) {
			const isDarkMode = document.documentElement.classList.contains('dark');

			if (isDarkMode) {
				const darkImage = new Image();
				darkImage.src = '/static/favicon-dark.png';

				darkImage.onload = () => {
					logo.src = '/static/favicon-dark.png';
					logo.style.filter = ''; // Ensure no inversion is applied if favicon-dark.png exists
				};

				darkImage.onerror = () => {
					logo.style.filter = 'invert(1)'; // Invert image if favicon-dark.png is missing
				};
			}
		}
	}

	onMount(async () => {
		if ($user !== undefined) {
			const redirectPath = querystringValue('redirect') || '/';
			goto(redirectPath);
		}
		if ($page.url.hash) {
			isOAuthLoading = true;
		}
		await checkOauthCallback();

		loaded = true;
		setLogoImage();

		if (($config?.features.auth_trusted_header ?? false) || $config?.features.auth === false) {
			await signInHandler();
		} else {
			onboarding = $config?.onboarding ?? false;
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
						id="logo"
						crossorigin="anonymous"
						src="{WEBUI_BASE_URL}/static/favicon.png"
						class=" w-6 rounded-full"
						alt=""
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
							<div class="mb-9">
								<div class="font-bold text-left text-3xl text-gray-400 dark:text-gray-600">
									<div
										class={showAdminForm === null ? 'animate-slide-in-1' : 'animate-slide-in-left'}
									>
										Anmelden
									</div>
									<div
										class={showAdminForm === null ? 'animate-slide-in-2' : 'animate-slide-in-left'}
									>
										<div class="font-bold text-left text-4xl text-gray-600 dark:text-gray-400">
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
										<div class="relative">
											<button
												class="oauth-button flex items-center px-6 duration-300 w-full rounded-full text-sm py-3 transition justify-center group text-black dark:text-white"
												on:click={handleOAuthClick}
											>
												<div
													class="relative overflow-hidden min-w-[300px] flex items-center justify-center"
												>
													<!-- First view with key icon -->
													<div
														class="flex items-center justify-center w-full transition-all duration-300 group-hover:-translate-y-full group-hover:opacity-0"
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
														{$i18n.t('Continue with {{provider}}', {
															provider: $config?.oauth?.providers?.oidc ?? 'SSO'
														})}
													</div>

													<!-- Second view with arrow icon -->
													<div
														class="absolute left-0 w-full flex items-center justify-center transition-all duration-300 translate-y-full opacity-0 group-hover:translate-y-0 group-hover:opacity-100"
													>
														<svg
															xmlns="http://www.w3.org/2000/svg"
															fill="none"
															viewBox="0 0 24 24"
															stroke-width="1.5"
															stroke="currentColor"
															class="size-6 mr-3 -translate-x-[100px] transition-transform duration-500 group-hover:translate-x-0"
														>
															<path
																stroke-linecap="round"
																stroke-linejoin="round"
																d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
															/>
														</svg>
														IZ-Nr. und OfficeLAN Passwort
													</div>
												</div>
											</button>
										</div>
									</div>

									<!-- "oder" Trennstrich -->
									<div class="relative w-full z-0">
										<hr class="w-64 h-px my-8 bg-gray-200 border-0 dark:bg-gray-700 mx-auto" />
										<div
											class="absolute px-3 font-medium text-gray-500 left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 dark:text-white bg-white dark:bg-gray-950"
										>
											{$i18n.t('or')}
										</div>
									</div>

									<!-- Administrativer Login Button -->
									<button
										class="text-sm rounded-full border border-gray-300 dark:border-gray-700 py-2 px-4 text-gray-600 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
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

	.oauth-button {
		position: relative;
		color: #ffffff;
		background: #29425e;
		border: 2px solid rgba(255, 255, 255, 0.2);
		letter-spacing: 0.5px;
		font-weight: 500;
		z-index: 1;
		transition:
			background 0.4s linear,
			border 0.4s linear,
			box-shadow 0.4s linear;
	}

	:global(.dark) .oauth-button {
		color: #ffffff;
		background: #29425e;
		border: 2px solid rgba(255, 255, 255, 0.2);
	}

	/* Hover-Effekte nur, wenn der Button nicht disabled ist */
	.oauth-button:not(:disabled):hover {
		color: #fff;
		background: linear-gradient(90deg, #7e7a7a, #ad2525, #2a2a2a, #304b6a, #7e7a7a);
		background-size: 300% 100%;
		border: 2px solid rgba(255, 255, 255, 0.4);
		box-shadow:
			0 0 15px rgba(2, 4, 24, 0.7),
			0 0 25px rgba(173, 37, 37, 0.3),
			0 0 35px rgba(48, 75, 106, 0.3);
		animation: gradientMove 8s linear infinite;
		text-shadow: 0 0 4px rgba(0, 0, 0, 0.5);
	}

	@keyframes gradientMove {
		0% {
			background-position: 0% 50%;
		}
		50% {
			background-position: 150% 50%;
		}
		100% {
			background-position: 300% 50%;
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

	/* Glow-Effekt auch nur, wenn nicht disabled */
	.oauth-button:not(:disabled):hover::before {
		opacity: 0.6;
		z-index: -1;
	}

	.oauth-button:disabled {
		/* Falls gewünscht, kann man hier eine optische Anpassung für disabled vornehmen */
		opacity: 0.6;
		cursor: not-allowed;
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

	.oauth-button .relative {
		width: 100%;
		white-space: nowrap;
	}

	.oauth-button span {
		display: inline-block;
		transition: all 0.3s ease;
	}
</style>
