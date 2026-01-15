- This is a fork of OpenWebUI with custom changes for FI-TS (our company).
- All custom changes in this repo must be commented with "FI-TS_custom [date]: [change explanation]"
- Also, if possible, change branting to "FI-TS" in relevant places.
- For scripts and FI-TS specific code theres a folder "fits-scripts" under /backend/open_webui/
- Do not comment if the file doesn't allow comments like json, etc.
- be careful when merging updates from OpenWebUI to not overwrite FI-TS custom changes, if you are not sure ask the user.
- For text fields in the Frontend always use the n18n internationalization files to allow easy translation later. Also if you add new text fields, please add them to the german i18n json as german is set to the dafault language in the FI-TS fork.
- Only make minimal and maintainable custom changes to the original OpenWebUI code for easier future merges.
- the GitLab remote it the FI-TS fork
- We have a custom Landingpage design under /scr/lib/components/fi-ts_landingpage

## Adding New Configuration Environment Variables

When adding new admin-configurable settings (environment variables), you must update multiple files. Follow these steps in order:

### 1. Define the Config (`/backend/open_webui/config.py`)

Add a new `PersistentConfig` definition with the appropriate section:

```python
# FI-TS_custom [date]: [description]
YOUR_CONFIG_NAME = PersistentConfig(
    "YOUR_CONFIG_NAME",
    "section.subsection.config_name",  # Dotted path for organization
    default_value_from_env,
)
```

### 2. Import and Assign in Main (`/backend/open_webui/main.py`)

**Import the config** (around line 370):

```python
YOUR_CONFIG_NAME,
```

**Assign to app.state.config** (around line 820):

```python
# FI-TS_custom [date]: [description]
app.state.config.YOUR_CONFIG_NAME = YOUR_CONFIG_NAME
```

### 3. Add to Admin API (`/backend/open_webui/routers/auths.py`)

**Add to AdminConfig model** (around line 1050):

```python
YOUR_CONFIG_NAME: Optional[type] = default_value
```

**Add to GET endpoint response** (around line 1025):

```python
"YOUR_CONFIG_NAME": request.app.state.config.YOUR_CONFIG_NAME,
```

**Add to POST endpoint handler** (around line 1110):

```python
# FI-TS_custom [date]: [description]
request.app.state.config.YOUR_CONFIG_NAME = form_data.YOUR_CONFIG_NAME
```

**Add to POST endpoint response** (around line 1137):

```python
"YOUR_CONFIG_NAME": request.app.state.config.YOUR_CONFIG_NAME,
```

### 4. Frontend Admin UI (Optional, if needs UI control)

**Add to Settings component** (`/src/lib/components/admin/Settings/General.svelte`):

```svelte
<!-- FI-TS_custom [date]: [description] -->
<div class="mb-2.5">
	<div class="self-center text-xs font-medium mb-2">
		{$i18n.t('Your Setting Label')}
	</div>
	<input
		class="w-full rounded-lg py-2 px-4 text-sm bg-gray-50 dark:text-gray-300 dark:bg-gray-850"
		type="number"
		bind:value={adminConfig.YOUR_CONFIG_NAME}
	/>
</div>
```

### 5. Add Translations (`/src/lib/i18n/locales/de-DE/translation.json`)

Add German translations (German is the default language):

```json
"Your Setting Label": "Deutsche Übersetzung",
"Your setting description": "Deutsche Beschreibung",
```
