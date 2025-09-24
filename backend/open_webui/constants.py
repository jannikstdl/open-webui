from enum import Enum


class MESSAGES(str, Enum):
    DEFAULT = lambda msg="": f"{msg if msg else ''}"
    MODEL_ADDED = lambda model="": f"Das Modell '{model}' wurde erfolgreich hinzugefügt."
    MODEL_DELETED = (
        lambda model="": f"Das Modell '{model}' wurde erfolgreich gelöscht."
    )


class WEBHOOK_MESSAGES(str, Enum):
    DEFAULT = lambda msg="": f"{msg if msg else ''}"
    USER_SIGNUP = lambda username="": (
        f"Neuer Benutzer registriert: {username}" if username else "Neuer Benutzer registriert"
    )


class ERROR_MESSAGES(str, Enum):
    def __str__(self) -> str:
        return super().__str__()

    DEFAULT = (
        lambda err="": f'{"Etwas ist schief gelaufen :/ Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de" if err == "" else "[FEHLER: " + str(err) + "] Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"}'
    )
    ENV_VAR_NOT_FOUND = "Erforderliche Umgebungsvariable nicht gefunden. Beende jetzt. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    CREATE_USER_ERROR = "Etwas ist schief gelaufen beim Erstellen deines Kontos. Bitte versuche es später erneut. Wenn das Problem weiterhin besteht, kontaktiere den Support für Unterstützung. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    DELETE_USER_ERROR = "Etwas ist schief gelaufen. Wir haben ein Problem beim Löschen des Benutzers festgestellt. Bitte versuche es erneut. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    EMAIL_MISMATCH = "Diese E-Mail stimmt nicht mit der E-Mail überein, mit der dein Anbieter registriert ist. Bitte überprüfe deine E-Mail und versuche es erneut. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    EMAIL_TAKEN = "Diese E-Mail ist bereits registriert. Melde dich mit deinem bestehenden Konto an oder wähle eine andere E-Mail, um neu zu beginnen. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    USERNAME_TAKEN = (
        "Dieser Benutzername ist bereits registriert. Bitte wähle einen anderen Benutzernamen. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    )
    PASSWORD_TOO_LONG = "Das angegebene Passwort ist zu lang. Bitte stelle sicher, dass es weniger als 72 Bytes lang ist. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    COMMAND_TAKEN = "Dieser Befehl ist bereits registriert. Bitte wähle eine andere Befehlszeichenfolge. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    FILE_EXISTS = "Diese Datei ist bereits registriert. Bitte wähle eine andere Datei. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    ID_TAKEN = "Diese ID ist bereits registriert. Bitte wähle eine andere ID-Zeichenfolge. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    MODEL_ID_TAKEN = "Diese Modell-ID ist bereits registriert. Bitte wähle eine andere Modell-ID-Zeichenfolge. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    NAME_TAG_TAKEN = "Dieser Tag ist bereits registriert. Bitte wähle einen anderen Tag. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    INVALID_TOKEN = "Deine Sitzung ist abgelaufen oder das Token ist ungültig. Bitte melde dich erneut an. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    INVALID_CRED = "Die angegebene E-Mail oder das Passwort ist falsch. Bitte überprüfe auf Tippfehler und versuche es erneut. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    INVALID_EMAIL_FORMAT = "Das von dir eingegebene E-Mail-Format ist ungültig. Bitte überprüfe es und stelle sicher, dass du eine gültige E-Mail-Adresse verwendest (z.B. deinname@beispiel.com). Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    INVALID_PASSWORD = "Das angegebene Passwort ist falsch. Bitte überprüfe auf Tippfehler und versuche es erneut. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    INVALID_TRUSTED_HEADER = "Dein Anbieter hat keinen vertrauenswürdigen Header bereitgestellt. Bitte kontaktiere deinen Administrator für Unterstützung. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    EXISTING_USERS = "Du kannst die Authentifizierung nicht deaktivieren, da es bereits bestehende Benutzer gibt. Wenn du WEBUI_AUTH deaktivieren möchtest, stelle sicher, dass deine Weboberfläche keine bestehenden Benutzer hat und eine Neuinstallation ist. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    UNAUTHORIZED = "401 Unauthorized Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    ACCESS_PROHIBITED = "Du hast keine Berechtigung, auf diese Ressource zuzugreifen. Bitte kontaktiere deinen Administrator für Unterstützung. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    ACTION_PROHIBITED = "Die angeforderte Aktion wurde aus Sicherheitsgründen eingeschränkt. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    FILE_NOT_SENT = "FILE_NOT_SENT Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    FILE_NOT_SUPPORTED = "Es scheint, dass das Dateiformat, das du hochladen möchtest, nicht unterstützt wird. Bitte lade eine Datei mit einem unterstützten Format hoch (z.B. JPG, PNG, PDF, TXT) und versuche es erneut. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    NOT_FOUND = "Wir konnten nicht finden, wonach du suchst :/ Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    USER_NOT_FOUND = "Wir konnten nicht finden, wonach du suchst :/ Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    API_KEY_NOT_FOUND = "Es sieht aus, als gäbe es ein Problem. Der API-Schlüssel fehlt. Bitte stelle sicher, dass du einen gültigen API-Schlüssel bereitstellst, um auf diese Funktion zuzugreifen. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    API_KEY_NOT_ALLOWED = "Der API-Schlüssel ist nicht erlaubt. Bitte kontaktiere deinen Administrator für Unterstützung. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    MALICIOUS = "Ungewöhnliche Aktivitäten erkannt, bitte versuche es in ein paar Minuten erneut. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    PANDOC_NOT_INSTALLED = "Pandoc ist nicht auf dem Server installiert. Bitte kontaktiere deinen Administrator für Unterstützung. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    INCORRECT_FORMAT = lambda err="": f"Ungültiges Format. Bitte verwende das korrekte Format{err} Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    RATE_LIMIT_EXCEEDED = "API-Ratenlimit überschritten Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    MODEL_NOT_FOUND = (
        lambda name="": f"Modell '{name}' wurde nicht gefunden. Bitte versuchen Sie es erneut. Servicestatus unter https://status.ai-demo.officelan-izb. Falls sich der Fehler langfristig wiederholt, erstellen Sie gerne ein Ticket an 55021."
    )
    OPENAI_NOT_FOUND = (
        lambda name="": "OpenAI API wurde nicht gefunden. Bitte versuchen Sie es erneut. Servicestatus unter https://status.ai-demo.officelan-izb. Falls sich der Fehler langfristig wiederholt, erstellen Sie gerne ein Ticket an 55021."
    )
    OLLAMA_NOT_FOUND = (
        "WebUI konnte keine Verbindung zu Ollama herstellen. Bitte versuchen Sie es erneut. Servicestatus unter https://status.ai-demo.officelan-izb. Falls sich der Fehler langfristig wiederholt, erstellen Sie gerne ein Ticket an 55021."
    )
    CREATE_API_KEY_ERROR = "Etwas ist schief gelaufen beim Erstellen deines API-Schlüssels. Bitte versuche es später erneut. Wenn das Problem weiterhin besteht, kontaktiere den Support für Unterstützung. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    API_KEY_CREATION_NOT_ALLOWED = "Die API-Schlüssel-Erstellung ist nicht erlaubt in der Umgebung. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    

    EMPTY_CONTENT = "Der bereitgestellte Inhalt ist leer. Bitte stelle sicher, dass Text oder Daten vorhanden sind, bevor du fortfährst. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    DB_NOT_SQLITE = "Diese Funktion ist nur verfügbar, wenn mit SQLite-Datenbanken gearbeitet wird. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    INVALID_URL = "Die von dir angegebene URL ist ungültig. Bitte überprüfe sie und versuche es erneut. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    WEB_SEARCH_ERROR = (
        lambda err="": f"{err if err else 'Etwas ist schief gelaufen bei der Websuche.'} Bitte versuchen Sie es erneut. Servicestatus unter https://status.ai-demo.officelan-izb. Falls sich der Fehler langfristig wiederholt, erstellen Sie gerne ein Ticket an 55021."
    )

    OLLAMA_API_DISABLED = (
        "Die Ollama API ist deaktiviert. Bitte aktiviere sie, um diese Funktion zu nutzen. Bitte versuchen Sie es erneut. Servicestatus unter https://status.ai-demo.officelan-izb. Falls sich der Fehler langfristig wiederholt, erstellen Sie gerne ein Ticket an 55021."
    )

    FILE_TOO_LARGE = lambda size="": f"Die Datei, die du hochladen möchtest, ist zu groß. Bitte lade eine Datei hoch, die kleiner als {size} ist. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"

    DUPLICATE_CONTENT = "Doppelter Inhalt erkannt. Bitte gib eindeutigen Inhalt an, um fortzufahren. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"
    FILE_NOT_PROCESSED = "Extrahierter Inhalt ist für diese Datei nicht verfügbar. Bitte stelle sicher, dass die Datei verarbeitet wird, bevor du fortfährst. Bei Fragen wende dich gerne an ZZG-FITS-AI-Services@f-i-ts.de"


class TASKS(str, Enum):
    def __str__(self) -> str:
        return super().__str__()

    DEFAULT = lambda task="": f"{task if task else 'generation'}"
    TITLE_GENERATION = "title_generation"
    FOLLOW_UP_GENERATION = "follow_up_generation"
    TAGS_GENERATION = "tags_generation"
    EMOJI_GENERATION = "emoji_generation"
    QUERY_GENERATION = "query_generation"
    IMAGE_PROMPT_GENERATION = "image_prompt_generation"
    AUTOCOMPLETE_GENERATION = "autocomplete_generation"
    FUNCTION_CALLING = "function_calling"
    MOA_RESPONSE_GENERATION = "moa_response_generation"
