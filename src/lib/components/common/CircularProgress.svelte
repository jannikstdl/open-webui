<script lang="ts">
	export let progress: number = 0;
	export let className: string = 'size-5';

	const radius = 14;
	const circumference = 2 * Math.PI * radius;

	$: clampedProgress = Math.min(Math.max(progress, 0), 100);
	$: dashoffset = circumference - (clampedProgress / 100) * circumference;
	$: isComplete = progress >= 100;
</script>

<svg viewBox="0 0 36 36" class="{className} {isComplete ? 'animate-pulse' : ''}" fill="none">
	<!-- Background track -->
	<circle cx="18" cy="18" r={radius} stroke="currentColor" stroke-width="3" opacity="0.15" />
	<!-- Progress arc -->
	<circle
		cx="18"
		cy="18"
		r={radius}
		stroke="currentColor"
		stroke-width="3"
		stroke-dasharray={circumference}
		stroke-dashoffset={dashoffset}
		stroke-linecap="round"
		transform="rotate(-90 18 18)"
		class="transition-all duration-200"
	/>
</svg>
