// Favicon loading with graceful fall-back
// 0 → DuckDuckGo service, 1 → direct /favicon.ico, 2 → Google service, 3+ → give up (SVG fallback)

const faviconAttempts: Record<number, number> = {};

export function getFaviconSrc(domain: string, idx: number): string | null {
	const attempt = faviconAttempts[idx] || 0;

	switch (attempt) {
		case 0:
			// DuckDuckGo delivers a real icon or a small placeholder and rarely 404s
			return `https://icons.duckduckgo.com/ip3/${domain}.ico`;
		case 1:
			// Direct favicon file on the target domain
			return `https://${domain}/favicon.ico`;
		case 2:
			// Google service as final fallback (can return 404 for many sites)
			return `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;
		default:
			return null; // give up → will show SVG placeholder
	}
}

export function handleFaviconError(event: Event, domain: string, idx: number) {
	// try the next fallback
	faviconAttempts[idx] = (faviconAttempts[idx] || 0) + 1;

	const nextSrc = getFaviconSrc(domain, idx);

	if (nextSrc) {
		(event.currentTarget as HTMLImageElement).src = nextSrc;
	}
}

export function getDomain(url: string): string {
	try {
		return new URL(url).hostname.replace(/^www\./, '');
	} catch {
		return url;
	}
}
