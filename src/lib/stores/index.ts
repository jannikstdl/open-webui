import { APP_NAME } from '$lib/constants';
import { type Writable, writable } from 'svelte/store';
import type { ModelConfig } from '$lib/apis';
import type { Banner } from '$lib/types';
import type { Socket } from 'socket.io-client';

import emojiShortCodes from '$lib/emoji-shortcodes.json';

// Backend
export const WEBUI_NAME = writable(APP_NAME);
export const config: Writable<Config | undefined> = writable(undefined);
export const user: Writable<SessionUser | undefined> = writable(undefined);

// Electron App
export const isApp = writable(false);
export const appInfo = writable(null);
export const appData = writable(null);

// Frontend
export const MODEL_DOWNLOAD_POOL = writable({});

export const mobile = writable(false);

export const socket: Writable<null | Socket> = writable(null);
export const activeUserIds: Writable<null | string[]> = writable(null);
export const USAGE_POOL: Writable<null | string[]> = writable(null);

export const theme = writable('system');

export const shortCodesToEmojis = writable(
	Object.entries(emojiShortCodes).reduce((acc, [key, value]) => {
		if (typeof value === 'string') {
			acc[value] = key;
		} else {
			for (const v of value) {
				acc[v] = key;
			}
		}

		return acc;
	}, {})
);

export const TTSWorker = writable(null);

export const chatId = writable('');
export const chatTitle = writable('');

export const channels = writable([]);
export const chats = writable(null);
export const pinnedChats = writable([]);
export const tags = writable([]);

export const models: Writable<Model[]> = writable([]);

export const prompts: Writable<null | Prompt[]> = writable(null);
export const knowledge: Writable<null | Document[]> = writable(null);
export const tools = writable(null);
export const functions = writable(null);

export const toolServers = writable([]);

export const banners: Writable<Banner[]> = writable([]);

export const settings: Writable<Settings> = writable({});

export const showSidebar = writable(false);
export const showSearch = writable(false);
export const showSettings = writable(false);
export const showArchivedChats = writable(false);
export const showChangelog = writable(false);
export const showAcknowledgements = writable(false);
export const showControls = writable(false);
export const showOverview = writable(false);
export const showArtifacts = writable(false);
export const showCallOverlay = writable(false);

export const artifactCode = writable(null);

export const temporaryChatEnabled = writable(false);
export const scrollPaginationEnabled = writable(false);
export const currentChatPage = writable(1);

export const isLastActiveTab = writable(true);
export const playingNotificationSound = writable(false);

export const acknowledgementsContent = writable(`
### Open Source Bibliotheken und Anwendungen

FI-TS AI basiert auf einer Vielzahl von Open-Source-Bibliotheken und -Anwendungen, darunter (aber nicht beschränkt auf):
- OpenWebUI
- FastAPI, Flask, Flask-Cors, Uvicorn, Pydantic, python-multipart
- python-socketio, python-jose, passlib, bcrypt
- requests, aiohttp, aiocache, aiofiles
- SQLAlchemy, Alembic, Peewee, Peewee-Migrate, pgvector, PyMySQL
- MongoDB, Redis, Boto3
- Argon2-CFFI, APScheduler
- OpenAI, Anthropic, Google Generative AI, tiktoken
- LangChain, LangChain-Community
- fake-useragent, chromadb, pymilvus, qdrant-client, opensearch-py
- Transformers, Sentence Transformers, ColBERT-AI, einops
- ftfy, pypdf, fpdf2, pymdown-extensions, docx2txt, python-pptx, unstructured, nltk, Markdown, pypandoc, pandas, openpyxl, pyxlsb, xlrd, validators, psutil, sentencepiece, soundfile
- opencv-python-headless, rapidocr-onnxruntime, rank-bm25, faster-whisper
- PyJWT, Authlib
- Black, langfuse, youtube-transcript-api, pytube
- extract_msg, pydub, duckduckgo-search
- google-api-python-client, google-auth-httplib2, google-auth-oauthlib
- Docker, Pytest, pytest-docker
- googleapis-common-protos, google-cloud-storage
- ldap3
- … sowie weitere Bibliotheken, Anwendungen und Tools für den Betrieb, die Infrastruktur und für Tests.

Bitte beachten Sie, dass nicht alle oben genannten Komponenten in jeder Installation verwendet werden. FI-TS AI umfasst außerdem verschiedene Open-Source-Lösungen für Infrastruktur und Betrieb, läuft auf einem Kubernetes-Cluster der FCN (FI-TS Finance Cloud Native) in unserem eigenen Rechenzentrum und nutzt GPU-Ressourcen zur Beschleunigung.

### Übergeordnete Lizenzarten

Die verwendeten Open-Source-Komponenten unterliegen einer Reihe bekannter Lizenzarten, unter anderem (aber nicht ausschließlich):
- MIT License
- Apache License 2.0
- BSD (verschiedene Varianten)
- GNU General Public License (GPL) & GNU Lesser General Public License (LGPL)
- Mozilla Public License (MPL)
- Public Domain / Unlicense

Diese Lizenzen unterscheiden sich hinsichtlich der Bedingungen für Weitergabe, Modifikation und Einhaltung von Copyleft-Bestimmungen. Wir empfehlen allen Nutzern, sich vor Verwendung mit den jeweiligen Lizenzbestimmungen vertraut zu machen.

### Hinweise zur Lizenzierung und Kontakt

Die spezifischen Lizenztexte und -bedingungen liegen den entsprechenden Projekten bei und gelten uneingeschränkt. Bei Fragen zu den verwendeten Open-Source-Bibliotheken, Versionen oder Lizenzen können Sie sich gerne an uns wenden.

Finanz Informatik Technologie Service GmbH & Co. KG
`);

export type Model = OpenAIModel | OllamaModel;

type BaseModel = {
	id: string;
	name: string;
	info?: ModelConfig;
	owned_by: 'ollama' | 'openai' | 'arena';
};

export interface OpenAIModel extends BaseModel {
	owned_by: 'openai';
	external: boolean;
	source?: string;
}

export interface OllamaModel extends BaseModel {
	owned_by: 'ollama';
	details: OllamaModelDetails;
	size: number;
	description: string;
	model: string;
	modified_at: string;
	digest: string;
	ollama?: {
		name?: string;
		model?: string;
		modified_at: string;
		size?: number;
		digest?: string;
		details?: {
			parent_model?: string;
			format?: string;
			family?: string;
			families?: string[];
			parameter_size?: string;
			quantization_level?: string;
		};
		urls?: number[];
	};
}

type OllamaModelDetails = {
	parent_model: string;
	format: string;
	family: string;
	families: string[] | null;
	parameter_size: string;
	quantization_level: string;
};

type Settings = {
	models?: string[];
	conversationMode?: boolean;
	speechAutoSend?: boolean;
	responseAutoPlayback?: boolean;
	audio?: AudioSettings;
	showUsername?: boolean;
	notificationEnabled?: boolean;
	highContrastMode?: boolean;
	title?: TitleSettings;
	splitLargeDeltas?: boolean;
	chatDirection: 'LTR' | 'RTL' | 'auto';
	ctrlEnterToSend?: boolean;

	system?: string;
	seed?: number;
	temperature?: string;
	repeat_penalty?: string;
	top_k?: string;
	top_p?: string;
	num_ctx?: string;
	num_batch?: string;
	num_keep?: string;
	options?: ModelOptions;
};

type ModelOptions = {
	stop?: boolean;
};

type AudioSettings = {
	STTEngine?: string;
	TTSEngine?: string;
	speaker?: string;
	model?: string;
	nonLocalVoices?: boolean;
};

type TitleSettings = {
	auto?: boolean;
	model?: string;
	modelExternal?: string;
	prompt?: string;
};

type Prompt = {
	command: string;
	user_id: string;
	title: string;
	content: string;
	timestamp: number;
};

type Document = {
	collection_name: string;
	filename: string;
	name: string;
	title: string;
};

type Config = {
	status: boolean;
	name: string;
	version: string;
	default_locale: string;
	default_models: string;
	default_prompt_suggestions: PromptSuggestion[];
	features: {
		auth: boolean;
		auth_trusted_header: boolean;
		enable_api_key: boolean;
		enable_signup: boolean;
		enable_login_form: boolean;
		enable_web_search?: boolean;
		enable_google_drive_integration: boolean;
		enable_onedrive_integration: boolean;
		enable_image_generation: boolean;
		enable_admin_export: boolean;
		enable_admin_chat_access: boolean;
		enable_community_sharing: boolean;
		enable_autocomplete_generation: boolean;
		enable_direct_connections: boolean;
	};
	oauth: {
		providers: {
			[key: string]: string;
		};
	};
	ui?: {
		pending_user_overlay_title?: string;
		pending_user_overlay_description?: string;
	};
};

type PromptSuggestion = {
	content: string;
	title: [string, string];
};

type SessionUser = {
	id: string;
	email: string;
	name: string;
	role: string;
	profile_image_url: string;
};
