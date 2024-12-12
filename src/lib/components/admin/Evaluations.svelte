<script lang="ts">
	// Import für Datei-Export
	import fileSaver from 'file-saver';
	const { saveAs } = fileSaver;

	// Svelte-spezifische Import-Optionen
	import { onMount, getContext } from 'svelte';
	import dayjs from 'dayjs';
	import relativeTime from 'dayjs/plugin/relativeTime';
	dayjs.extend(relativeTime);

	// Feedback-API und Hilfs-Tools
	import { models } from '$lib/stores';
	import { deleteFeedbackById, exportAllFeedbacks, getAllFeedbacks } from '$lib/apis/evaluations';

	// UI-Komponenten
	import FeedbackMenu from './Evaluations/FeedbackMenu.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import Badge from '../common/Badge.svelte';
	import Pagination from '../common/Pagination.svelte';
	import MagnifyingGlass from '../icons/MagnifyingGlass.svelte';
	import { toast } from 'svelte-sonner';
	import Spinner from '../common/Spinner.svelte';
	import ArrowDownTray from '../icons/ArrowDownTray.svelte';

	const i18n = getContext('i18n');

	// Globale Variablen
	let rankedModels = [];
	let feedbacks = [];
	let query = ''; // Suchanfrage
	let page = 1;
	let loaded = false;
	let loadingLeaderboard = true;

	// Pagination
	$: paginatedFeedbacks = feedbacks.slice((page - 1) * 10, page * 10);

	// Feedback-Typen
	type Feedback = {
		id: string;
		data: {
			rating: number;
			model_id: string;
			sibling_model_ids: string[] | null;
			reason: string;
			comment: string;
			tags: string[];
		};
		user: {
			name: string;
			profile_image_url: string;
		};
		updated_at: number;
	};

	//////////////////////
	//
	// Modell-Ranking
	//
	//////////////////////

	const rankHandler = async () => {
		// Filtere Modelle und sortiere sie
		rankedModels = $models
			.filter((m) => m?.owned_by !== 'arena' && (m?.info?.meta?.hidden ?? false) !== true)
			.map((model) => {
				return {
					...model,
					rating: '-', // Dummywert
					stats: {
						count: 0,
						won: '-',
						lost: '-'
					}
				};
			})
			.sort((a, b) => a.name.localeCompare(b.name));

		loadingLeaderboard = false;
	};

	//////////////////////
	//
	// Normale Suche
	//
	//////////////////////

	const normalSearchHandler = () => {
		// Filtere Feedbacks basierend auf der Suchanfrage
		if (query.trim() === '') {
			rankHandler(); // Lade Ranking neu, wenn keine Suchanfrage
		} else {
			feedbacks = feedbacks.filter((feedback) =>
				feedback.data.reason.toLowerCase().includes(query.toLowerCase())
			);
		}
	};

	$: query, normalSearchHandler(); // Reagiere auf Änderungen der Suchanfrage

	//////////////////////
	//
	// CRUD-Operationen
	//
	//////////////////////

	const deleteFeedbackHandler = async (feedbackId: string) => {
		// Lösche Feedback
		const response = await deleteFeedbackById(localStorage.token, feedbackId).catch((err) => {
			toast.error(err);
			return null;
		});
		if (response) {
			feedbacks = feedbacks.filter((f) => f.id !== feedbackId);
		}
	};

	const exportHandler = async () => {
		// Exportiere Feedbacks
		const _feedbacks = await exportAllFeedbacks(localStorage.token).catch((err) => {
			toast.error(err);
			return null;
		});

		if (_feedbacks) {
			let blob = new Blob([JSON.stringify(_feedbacks)], {
				type: 'application/json'
			});
			saveAs(blob, `feedback-history-export-${Date.now()}.json`);
		}
	};

	onMount(async () => {
		// Lade Feedbacks beim Mount
		feedbacks = await getAllFeedbacks(localStorage.token);
		loaded = true;

		rankHandler();
	});
</script>
