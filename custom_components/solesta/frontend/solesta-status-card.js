const SOLESTA_CARD_VERSION = "0.2.3";
const integrationDomainFromModuleUrl = (moduleUrl) => {
  const pathname = new URL(moduleUrl).pathname;
  const match = pathname.match(/\/([a-z][a-z0-9_]*)\/solesta-status-card\.js$/);
  if (!match) {
    throw new Error("Solesta status card: integration domain cannot be determined.");
  }
  return match[1];
};
const INTEGRATION_DOMAIN = integrationDomainFromModuleUrl(import.meta.url);
const INTEGRATION_NAME = `${INTEGRATION_DOMAIN.charAt(0).toUpperCase()}${INTEGRATION_DOMAIN.slice(1)}`;
const SOLESTA_LOGO_PATH = `/${INTEGRATION_DOMAIN}/solesta-community-logo.png?v=${SOLESTA_CARD_VERSION}`;
const SOLESTA_CARD_STARTED_AT = Date.now();

const REQUIRED_ENTITY_KEYS = [
  "tank_temperature",
  "collector_temperature",
  "tank_top_temperature",
  "tank_bottom_temperature",
  "energy_kwh",
  "energy_mj",
  "showers",
  "pump_active",
  "reporting",
  "alerts",
  "cold_water_temperature",
];

const UNKNOWN_STATES = new Set(["", "unknown", "unavailable", "none", "null"]);
const STATUS_TRACKING_EXCLUDED_KEYS = new Set(["last_report", "report_delay"]);
const DEFAULT_CARD_TEXT = Object.freeze({
  choose_system: "Choose a solar boiler in the card editor.",
  system_not_found: "The selected solar boiler is no longer available. Choose a solar boiler in the card editor.",
  missing_entities: "Some required entities are missing. Check whether this solar boiler’s Solesta entities are enabled.",
  no_systems: "No Solesta solar boilers are available yet. Configure a solar boiler in the integration first.",
  editor_system: "Solar boiler",
  editor_help: "The card automatically uses the entities belonging to this solar boiler.",
  editor_name: "Display name (optional)",
  editor_close_path: "Return path (optional)",
  editor_fit: "Fit card to the available screen height",

  loading: "Solesta is loading…",
  contact_support: "Contact Solesta support",
  unknown: "unknown",
  between: "between {from} and {through}",
  before: "Before {time}",
  system_offline: "System offline",
  all_normal: "Everything is working normally",
  status_incomplete: "Some system status data is unavailable",
  attention_required: "A system alert requires attention",
  last_status_change: "Last status change: {time}",
  last_status_change_help: "A status change is a change in the value of a solar boiler component, a derived value, or the communication link. Status changes are completely normal in your solar boiler.",
  status_change_info: "More information about status changes",
  alerts_unreadable: "The system alerts could not be read",
  system_alerts: "System alerts",
  close: "Close",
  tank_temperature_is: "The temperature in your solar boiler is:",
  preheated_water: "The system delivers {warmteindicatie} preheated water",
  warmth_slight: "slightly",
  warmth_strong: "strongly",
  in_tank: "In the storage tank",
  system_status: "System status",
  online: "Online",
  offline: "Offline",
  energy_for: "Energy for",
  standard_showers: "standard showers",
  your_system_status: "Status of your system",
  circulation: "Circulation",
  standby: "Standby",
  how_system_works: "How your system works",
  live: "LIVE",
  flow_diagram: "Schematic heat flow between solar collector, pump and storage tank",
  solar_collector: "SOLAR COLLECTOR",
  storage_tank: "storage tank",
  legend: "Legend",
  supply_hot: "Supply (hot)",
  return_cold: "Return (cold)",
  last_system_report: "Last system report {report}",
  average: "average {temperature}",
  day: "Day",
  today: "Today",
  day_average: "{day}: average {temperature}",
  day_range: "{day}: {minimum} to {maximum}",
  daily_range: "lowest - average - highest per day",
  temperature_range: "lowest - average - highest",
  history_loading: "Loading history…",
  history_unavailable: "Temperature history is temporarily unavailable",
  no_temperature_history: "No temperature history yet",
  tank_temperature_today: "Tank temperature today",
  tank_temperature_week: "Tank temperature this week",
  show_today: "Show today",
  show_seven_days: "Show seven days",
  select_temperature_moment: "Select a temperature moment",
  no_temperature_measurement: "No temperature measurement",
  chart_range: "{title}, range {minimum} to {maximum} degrees Celsius",
});

const interpolate = (template, replacements = {}) => String(template).replace(
  /\{([^{}]+)\}/g,
  (match, key) => Object.hasOwn(replacements, key) ? replacements[key] : match,
);

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const numberValue = (stateObject) => {
  if (!stateObject || UNKNOWN_STATES.has(String(stateObject.state).toLowerCase())) {
    return null;
  }
  const value = Number.parseFloat(String(stateObject.state).replace(",", "."));
  return Number.isFinite(value) ? value : null;
};

const isOn = (stateObject) => stateObject?.state === "on";

const ALERT_PRESENTATION = {
  offline: { icon: "mdi:wifi-off", tone: "error" },
  collector_hot: { icon: "mdi:thermometer-high", tone: "status" },
  over_temp: { icon: "mdi:fire-alert", tone: "error" },
  freeze_risk: { icon: "mdi:snowflake-alert", tone: "error" },
  needs_refill: { icon: "mdi:water-alert", tone: "error" },
  pump_idle: { icon: "mdi:cog-pause", tone: "status" },
  pump_wrong: { icon: "mdi:sync", tone: "status" },
  sensor_fault: { icon: "mdi:alert-circle", tone: "error" },
};

const alertPresentation = (alert) => ALERT_PRESENTATION[alert.type] || {
  icon: ["error", "critical"].includes(alert.severity)
    ? "mdi:alert-circle"
    : "mdi:information-outline",
  tone: ["error", "critical"].includes(alert.severity) ? "error" : "status",
};

const normalizeAlert = (item) => {
  if (!item || typeof item !== "object") return null;
  const type = typeof item.type === "string" ? item.type.trim() : "";
  const message = typeof item.message === "string" ? item.message.trim() : "";
  const severity = typeof item.severity === "string" ? item.severity.trim().toLowerCase() : "";
  if (!type && !message) return null;
  return { type, message: message || type, severity };
};

const pythonStringField = (source, field) => {
  const pattern = new RegExp(`["']${field}["']\\s*:\\s*(["'])(.*?)\\1(?:\\s*[,}])`);
  const match = source.match(pattern);
  return match ? match[2].replace(/\\\\([\\\\"'])/g, "$1").trim() : "";
};

const alertItems = (stateObject) => {
  if (!stateObject) return null;
  const raw = String(stateObject.state ?? "").trim();
  const overflowLines = stateObject.attributes?.truncated === true
    && Array.isArray(stateObject.attributes?.lines)
    ? stateObject.attributes.lines.map((line) => String(line))
    : null;
  if (!overflowLines && !raw) return [];
  if (!overflowLines && UNKNOWN_STATES.has(raw.toLowerCase())) return null;

  const sourceLines = overflowLines || raw.split(/\r?\n/);
  if (!overflowLines && (raw === "[]" || raw === "{}")) return [];

  return sourceLines.flatMap((sourceLine) => {
    const line = sourceLine.trim();
    if (!line) return [];

    try {
      const parsed = JSON.parse(line);
      const items = Array.isArray(parsed) ? parsed : [parsed];
      const normalized = items.map(normalizeAlert).filter(Boolean);
      if (normalized.length || Array.isArray(parsed)) return normalized;
    } catch (_error) {
      // Solesta can supply dictionary lines in Python notation with single quotes.
    }

    const dictionaries = line.match(/\{[^{}]*\}/g) || [];
    const parsedDictionaries = dictionaries.map((source) => normalizeAlert({
      type: pythonStringField(source, "type"),
      message: pythonStringField(source, "message"),
      severity: pythonStringField(source, "severity"),
    })).filter(Boolean);
    if (parsedDictionaries.length) return parsedDictionaries;

    return [{ type: "", message: line, severity: "warning" }];
  });
};

const timeZoneParts = (date, timeZone) => {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  return Object.fromEntries(parts
    .filter((part) => part.type !== "literal")
    .map((part) => [part.type, Number(part.value)]));
};

const zonedDateTime = (parts, timeZone) => {
  const expected = Date.UTC(
    parts.year,
    parts.month - 1,
    parts.day,
    parts.hour || 0,
    parts.minute || 0,
    parts.second || 0,
  );
  if (!timeZone) return new Date(expected);
  let candidate = expected;
  try {
    for (let attempt = 0; attempt < 4; attempt += 1) {
      const actual = timeZoneParts(new Date(candidate), timeZone);
      const represented = Date.UTC(
        actual.year, actual.month - 1, actual.day,
        actual.hour, actual.minute, actual.second,
      );
      const adjustment = expected - represented;
      candidate += adjustment;
      if (!adjustment) break;
    }
    const actual = timeZoneParts(new Date(candidate), timeZone);
    return ["year", "month", "day", "hour", "minute", "second"]
      .every((key) => actual[key] === (parts[key] || 0))
      ? new Date(candidate)
      : null;
  } catch (_error) {
    return null;
  }
};

const dateFromValue = (value, timeZone) => {
  if (value === null || value === undefined || value === "") return null;
  const text = String(value).trim();
  const localDateTime = text.match(
    /^(\d{2})-(\d{2})-(\d{4})[ T](\d{2}):(\d{2}):(\d{2})$/,
  );
  if (localDateTime) {
    const [, day, month, year, hour, minute, second] = localDateTime.map(Number);
    return zonedDateTime({ year, month, day, hour, minute, second }, timeZone);
  }
  const numeric = typeof value === "number"
    ? value
    : /^\d+(?:\.\d+)?$/.test(text)
      ? Number(value)
      : null;
  const normalized = numeric !== null && Number.isFinite(numeric)
    ? (Math.abs(numeric) < 1e12 ? numeric * 1000 : numeric)
    : value;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
};

const delayRangeFromValue = (value) => {
  const match = String(value ?? "").trim().match(
    /^\[\s*(\d+)\s*,\s*(\d+)\s*\]$/,
  );
  if (!match) return null;
  const fromSeconds = Number(match[1]);
  const throughSeconds = Number(match[2]);
  if (!Number.isSafeInteger(fromSeconds)
    || !Number.isSafeInteger(throughSeconds)
    || throughSeconds < fromSeconds) return null;
  return { fromSeconds, throughSeconds };
};

// HA supplies the display registry with stable platform/translation metadata.
// Never derive mappings from entity IDs, translated names, or friendly names.
const CARD_ENTITY_METADATA = Object.freeze({
  tank_temperature: ["sensor", "temp_tank_average"],
  collector_temperature: ["sensor", "temp_collector"],
  tank_top_temperature: ["sensor", "temp_tank_top"],
  tank_bottom_temperature: ["sensor", "temp_tank_bottom"],
  energy_kwh: ["sensor", "energy_tank_kwh"],
  energy_mj: ["sensor", "energy_tank_mj"],
  showers: ["sensor", "energy_tank_showers"],
  pump_active: ["binary_sensor", "state_pump"],
  reporting: ["binary_sensor", "status_reporting"],
  alerts: ["sensor", "alerts_system"],
  report_delay: ["sensor", "report_delay"],
  last_report: ["sensor", "last_report"],
  cold_water_temperature: ["number", "temp_coldwater"],
});

const solestaDevices = (hass) => {
  const ids = new Set(Object.values(hass?.entities || {})
    .filter((entry) => entry.platform === INTEGRATION_DOMAIN && entry.device_id)
    .map((entry) => entry.device_id));
  return [...ids].map((id) => {
    const device = hass?.devices?.[id];
    return { id, name: device?.name_by_user || device?.name || id };
  }).sort((left, right) => left.name.localeCompare(right.name));
};

const resolveCardEntities = (hass, deviceId) => {
  const entries = Object.values(hass?.entities || {}).filter((entry) =>
    entry.platform === INTEGRATION_DOMAIN && entry.device_id === deviceId
    && !entry.disabled_by);
  const entities = {};
  for (const [key, [domain, translationKey]] of Object.entries(CARD_ENTITY_METADATA)) {
    const matches = entries.filter((entry) => entry.translation_key === translationKey
      && entry.entity_id?.split(".")[0] === domain);
    // Ambiguous metadata must not silently select an arbitrary sensor.
    if (matches.length === 1) entities[key] = matches[0].entity_id;
  }
  return entities;
};

class SolestaTranslatedElement extends HTMLElement {
  constructor() {
    super();
    this._cardLocalize = null;
    this._cardTranslations = null;
    this._translationLanguage = null;
    this._translationRequest = null;
    this._translationFallbackReady = false;
    this._translationFailureCount = 0;
    this._translationRetryAt = 0;
    this._translationRevision = 0;
  }

  _t(key, replacements = {}) {
    const translationPath = `component.${INTEGRATION_DOMAIN}.common.dashboard_${key}`;
    const directTranslation = this._cardTranslations?.[translationPath];
    if (typeof directTranslation === "string" && directTranslation.trim()) {
      return interpolate(directTranslation, replacements);
    }
    const localize = this._cardLocalize || this._hass?.localize;
    const localized = localize?.(translationPath, replacements);
    if (typeof localized === "string" && localized.trim() && localized !== translationPath) {
      return localized;
    }
    return interpolate(DEFAULT_CARD_TEXT[key] || key, replacements);
  }

  _ensureTranslations(hass) {
    const language = hass?.locale?.language || hass?.language || "en";
    if (language !== this._translationLanguage) {
      this._translationLanguage = language;
      this._cardLocalize = null;
      this._cardTranslations = null;
      this._translationRequest = null;
      this._translationFallbackReady = false;
      this._translationFailureCount = 0;
      this._translationRetryAt = 0;
    }
    if (this._translationRequest || this._cardLocalize || this._cardTranslations) return;
    if (this._translationFallbackReady && Date.now() < this._translationRetryAt) return;
    const request = (async () => {
      if (typeof hass?.callWS === "function") {
        const languages = [...new Set([
          language,
          language.includes("-") ? language.split("-", 1)[0] : null,
        ].filter(Boolean))];
        for (const requestedLanguage of languages) {
          try {
            const response = await hass.callWS({
              type: "frontend/get_translations",
              language: requestedLanguage,
              category: "common",
              integration: [INTEGRATION_DOMAIN],
            });
            const resources = response?.resources || response;
            const probe = resources?.[`component.${INTEGRATION_DOMAIN}.common.dashboard_loading`];
            const englishFallback = !requestedLanguage.toLowerCase().startsWith("en")
              && probe === DEFAULT_CARD_TEXT.loading;
            if (resources && typeof resources === "object" && probe && !englishFallback) {
                return { localize: null, resources, failed: false };
            }
          } catch (_error) {
            // Try the base language or the frontend translation loader below.
          }
        }
      }
      if (typeof hass?.loadBackendTranslation === "function") {
        try {
          const localize = await hass.loadBackendTranslation("common", INTEGRATION_DOMAIN);
          const probePath = `component.${INTEGRATION_DOMAIN}.common.dashboard_loading`;
          const probe = localize?.(probePath);
          if (typeof probe === "string" && probe.trim() && probe !== probePath) {
            return { localize, resources: null, failed: false };
          }
        } catch (_error) {
          // The built-in English fallbacks keep the card usable while disconnected.
        }
      }
      return { localize: null, resources: null, failed: true };
    })();
    this._translationRequest = request;
    request.then(({ localize, resources, failed }) => {
      if (this._translationRequest !== request) return;
      this._cardLocalize = typeof localize === "function" ? localize : null;
      this._cardTranslations = resources;
      this._translationRequest = null;
      this._translationFallbackReady = failed;
      if (failed) {
        this._translationFailureCount += 1;
        const retryDelay = Math.min(
          15 * 60 * 1000,
          30 * 1000 * (2 ** Math.min(5, this._translationFailureCount - 1)),
        );
        this._translationRetryAt = Date.now() + retryDelay;
      } else {
        this._translationFailureCount = 0;
        this._translationRetryAt = 0;
      }
      this._translationRevision += 1;
      this._render();
    }).catch(() => {
      if (this._translationRequest !== request) return;
      this._translationRequest = null;
      this._translationFallbackReady = true;
      this._translationFailureCount += 1;
      this._translationRetryAt = Date.now() + Math.min(
        15 * 60 * 1000,
        30 * 1000 * (2 ** Math.min(5, this._translationFailureCount - 1)),
      );
      this._translationRevision += 1;
      this._render();
    });
  }

}

class SolestaStatusCard extends SolestaTranslatedElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = null;
    this._userConfig = null;
    this._configIssue = null;
    this._resolvedSignature = null;
    this._historyGeneration = 0;
    this._hass = null;
    this._history = [];
    this._historyLoading = false;
    this._historyError = false;
    this._historyLoadedAt = 0;
    this._historyRetryDelay = 30 * 1000;
    this._historyRetryAt = 0;
    this._historyTimer = null;
    this._reportClockTimer = null;
    this._chartMode = "today";
    this._chartCursorTime = null;
    this._chartModel = null;
    this._chartPointerActive = false;
    this._lastValidSystemReport = null;
    this._statusChangeTime = null;
    this._statusChangeEntityNames = [];
    this._trackedEntityStates = null;
    this._cardLocalize = null;
    this._cardTranslations = null;
    this._translationLanguage = null;
    this._translationRequest = null;
    this._lastHassRenderSignature = null;
    this._fitAnimationFrame = null;
    this._scrollRestoreToken = 0;
    this._handleViewportResize = () => this._queueViewportFit();
  }

  static getConfigElement() {
    return document.createElement("solesta-status-card-editor");
  }

  static getStubConfig(hass) {
    const devices = solestaDevices(hass);
    return {
      ...(devices.length === 1 ? { device_id: devices[0].id } : {}),
      fit_to_viewport: true,
    };
  }

  setConfig(config) {
    if (!config || typeof config !== "object" || Array.isArray(config)) {
      throw new Error("Solesta status card: configuration is missing.");
    }
    if (config.device_id !== undefined && typeof config.device_id !== "string") {
      throw new Error("Solesta status card: device_id must be a string.");
    }
    if (config.entities !== undefined) {
      throw new Error("Solesta status card: choose a solar boiler by device_id.");
    }
    this._userConfig = { ...config };
    this._resolvedSignature = null;
    this._resolveConfig();
  }

  _resolveConfig() {
    if (!this._userConfig) return;
    if (this._resolvedUserConfig === this._userConfig
      && this._resolvedRegistry === this._hass?.entities
      && this._resolvedDevices === this._hass?.devices) return;
    this._resolvedUserConfig = this._userConfig;
    this._resolvedRegistry = this._hass?.entities;
    this._resolvedDevices = this._hass?.devices;
    const config = this._userConfig;
    let issue = null;
    let entities = {};
    let name = config.system_name;
    if (config.device_id) {
      const device = solestaDevices(this._hass).find((item) => item.id === config.device_id);
      entities = resolveCardEntities(this._hass, config.device_id);
      name ||= device?.name;
      if (!this._hass?.entities) issue = "loading";
      else if (!device) issue = "system_not_found";
      else if (REQUIRED_ENTITY_KEYS.some((key) => !entities[key])) issue = "missing_entities";
    } else {
      issue = "choose_system";
    }
    const effective = { ...config, system_name: name, entities };
    const signature = JSON.stringify([effective, issue]);
    if (signature === this._resolvedSignature) return;
    this._resolvedSignature = signature;
    this._configIssue = issue;
    this._applyConfig(effective);
  }

  _applyConfig(config) {
    const previousReportEntity = this._config?.entities?.last_report;
    const previousDelayEntity = this._config?.entities?.report_delay;
    const nextReportEntity = config.entities.last_report;
    const nextDelayEntity = config.entities.report_delay;
    if (this._config && (previousReportEntity !== nextReportEntity
      || previousDelayEntity !== nextDelayEntity)) {
      this._lastValidSystemReport = null;
    }
    const previousEntityConfig = JSON.stringify(
      Object.entries(this._config?.entities || {}).sort(([left], [right]) => left.localeCompare(right)),
    );
    const nextEntityConfig = JSON.stringify(
      Object.entries(config.entities).sort(([left], [right]) => left.localeCompare(right)),
    );
    if (previousEntityConfig !== nextEntityConfig) {
      this._statusChangeTime = null;
      this._statusChangeEntityNames = [];
      this._trackedEntityStates = null;
    }

    const nextConfig = {
      device_id: config.device_id || null,
      system_name: config.system_name || "Solesta Sun Boiler",
      close_path: config.close_path || null,
      support_text: config.support_text || null,
      fit_to_viewport: config.fit_to_viewport !== false,
      entities: { ...config.entities },
    };
    const historySourceChanged = !this._config
      || this._config.device_id !== nextConfig.device_id
      || this._config.entities.tank_temperature !== nextConfig.entities.tank_temperature;
    this._config = nextConfig;
    if (historySourceChanged) {
      this._historyGeneration += 1;
      this._historyLoading = false;
      this._historyError = false;
      this._historyRetryDelay = 30 * 1000;
      this._historyRetryAt = 0;
      if (this._historyTimer) window.clearTimeout(this._historyTimer);
      this._historyTimer = null;
      this._history = [];
      this._historyLoadedAt = 0;
      this._chartMode = "today";
      this._chartCursorTime = null;
      this._chartModel = null;
    }
    if (this._hass) this._captureSolestaUpdate(this._hass);
    this._render();
    this._scheduleHistoryLoad(true);
  }

  set hass(hass) {
    this._hass = hass;
    this._resolveConfig();
    this._captureSolestaUpdate(hass);
    this._ensureTranslations(hass);
    this._renderIfHassChanged();
    this._scheduleHistoryLoad(false);
  }

  getCardSize() {
    return 18;
  }

  connectedCallback() {
    window.addEventListener("resize", this._handleViewportResize);
    window.visualViewport?.addEventListener("resize", this._handleViewportResize);
    this._render();
    this._startReportClock();
    this._scheduleHistoryLoad(false);
  }

  disconnectedCallback() {
    if (this._historyTimer) window.clearTimeout(this._historyTimer);
    if (this._reportClockTimer) window.clearInterval(this._reportClockTimer);
    if (this._fitAnimationFrame) window.cancelAnimationFrame(this._fitAnimationFrame);
    window.removeEventListener("resize", this._handleViewportResize);
    window.visualViewport?.removeEventListener("resize", this._handleViewportResize);
    this._historyTimer = null;
    this._reportClockTimer = null;
    this._fitAnimationFrame = null;
  }

  _entity(key) {
    const entityId = this._config?.entities?.[key];
    return entityId && this._hass ? this._hass.states[entityId] : null;
  }

  _hassRenderSignature() {
    const states = Object.entries(this._config?.entities || {})
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, entityId]) => {
        const stateObject = this._hass?.states?.[entityId];
        return [
          key,
          entityId,
          stateObject?.state ?? null,
          stateObject?.last_changed ?? null,
          stateObject?.last_updated ?? null,
          key === "alerts" ? [
            stateObject?.attributes?.truncated ?? null,
            stateObject?.attributes?.lines ?? null,
          ] : null,
        ];
      });
    return JSON.stringify([
      this._resolvedSignature,
      this._configIssue,
      this._locale(),
      this._timeZone(),
      this._translationRevision,
      states,
    ]);
  }

  _renderIfHassChanged() {
    const signature = this._hassRenderSignature();
    if (signature === this._lastHassRenderSignature) return;
    this._lastHassRenderSignature = signature;
    this._render();
  }

  _locale() {
    return this._hass?.locale?.language || this._hass?.language || "en";
  }

  _timeZone() {
    const timeZone = this._hass?.config?.time_zone;
    return typeof timeZone === "string" && timeZone ? timeZone : undefined;
  }

  _now() {
    return new Date();
  }

  _parseDate(value) {
    return dateFromValue(value, this._timeZone());
  }

  _calendarParts(date) {
    return timeZoneParts(date, this._timeZone() || "UTC");
  }

  _calendarKey(date) {
    const parts = this._calendarParts(date);
    return `${parts.year}-${String(parts.month).padStart(2, "0")}-${String(parts.day).padStart(2, "0")}`;
  }

  _startOfDay(date) {
    const parts = this._calendarParts(date);
    return zonedDateTime({ ...parts, hour: 0, minute: 0, second: 0 }, this._timeZone());
  }

  _addCalendarDays(date, days) {
    const parts = this._calendarParts(date);
    const shifted = new Date(Date.UTC(parts.year, parts.month - 1, parts.day + days));
    return zonedDateTime({
      year: shifted.getUTCFullYear(),
      month: shifted.getUTCMonth() + 1,
      day: shifted.getUTCDate(),
      hour: 0,
      minute: 0,
      second: 0,
    }, this._timeZone());
  }

  _dateFormatter(options, locale = this._locale()) {
    const timeZone = this._timeZone();
    return new Intl.DateTimeFormat(locale, {
      ...options,
      ...(timeZone ? { timeZone } : {}),
    });
  }

  _formatNumber(value, digits) {
    return new Intl.NumberFormat(this._locale(), {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    }).format(value);
  }

  _formattedNumber(key, digits) {
    const value = numberValue(this._entity(key));
    if (value === null) return "—";
    return this._formatNumber(value, digits);
  }

  _sameDate(left, right) {
    const formatter = this._dateFormatter({
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }, "en-CA");
    return formatter.format(left) === formatter.format(right);
  }

  _time(date) {
    return this._dateFormatter({
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  }

  _shortTime(date) {
    return this._dateFormatter({
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  _datedTime(date) {
    return this._dateFormatter({
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(date);
  }

  _absoluteTime(value, now = this._now()) {
    if (value === null || value === undefined || value === "") return this._t("unknown");
    const date = this._parseDate(value);
    if (!date) return this._t("unknown");
    const current = now instanceof Date ? now : new Date(now);
    return this._sameDate(date, current) ? this._time(date) : this._datedTime(date);
  }

  _absoluteRange(fromValue, throughValue, now = this._now()) {
    const fromDate = this._parseDate(fromValue);
    const throughDate = this._parseDate(throughValue);
    if (!fromDate || !throughDate) {
      return this._t("between", {
        from: this._t("unknown"),
        through: this._t("unknown"),
      });
    }
    if (this._sameDate(fromDate, throughDate)) {
      return this._t("between", {
        from: this._absoluteTime(fromDate, now),
        through: this._time(throughDate),
      });
    }
    return this._t("between", {
      from: this._datedTime(fromDate),
      through: this._datedTime(throughDate),
    });
  }

  _entityDisplayName(hass, entityId) {
    const stateObject = hass.states[entityId];
    const registryEntry = hass.entities?.[entityId];
    const entityDomain = entityId.split(".", 1)[0];
    if (typeof hass.localize === "function"
      && registryEntry?.platform
      && registryEntry?.translation_key) {
      const translationPath = `component.${registryEntry.platform}.entity.${entityDomain}`
        + `.${registryEntry.translation_key}.name`;
      const localizedName = hass.localize(translationPath);
      if (typeof localizedName === "string" && localizedName.trim()
        && localizedName !== translationPath) {
        return localizedName.trim();
      }
    }
    if (stateObject && typeof hass.formatEntityName === "function") {
      const entityName = hass.formatEntityName(stateObject, { type: "entity" });
      if (typeof entityName === "string" && entityName.trim()) {
        return entityName.trim();
      }
    }
    const friendlyName = stateObject?.attributes?.friendly_name;
    return typeof friendlyName === "string" && friendlyName.trim()
      ? friendlyName.trim()
      : entityId;
  }

  _captureSolestaUpdate(hass) {
    if (!hass || !this._config) return;
    const trackedEntities = Object.entries(this._config.entities)
      .filter(([key, entityId]) => entityId && !STATUS_TRACKING_EXCLUDED_KEYS.has(key));
    const entityIds = [...new Set(trackedEntities.map(([, entityId]) => entityId))];
    const entityNames = new Map(trackedEntities.map(([, entityId]) => [
      entityId,
      this._entityDisplayName(hass, entityId),
    ]));
    const nextStates = Object.fromEntries(entityIds.map((entityId) => [
      entityId,
      hass.states[entityId]?.state ?? null,
    ]));

    if (!this._trackedEntityStates) {
      this._trackedEntityStates = nextStates;
      return;
    }

    const changes = entityIds.flatMap((entityId) => {
      if (this._trackedEntityStates[entityId] === nextStates[entityId]) return [];
      const entity = hass.states[entityId];
      const changed = this._parseDate(entity?.last_changed || entity?.last_updated);
      return changed ? [{
        time: changed.getTime(),
        name: entityNames.get(entityId) || entityId,
      }] : [];
    });
    this._trackedEntityStates = nextStates;
    if (changes.length) {
      this._statusChangeTime = Math.max(...changes.map((change) => change.time));
      this._statusChangeEntityNames = [...new Set(changes.map((change) => change.name))];
    }
  }

  _startReportClock() {
    if (this._reportClockTimer) return;
    this._reportClockTimer = window.setInterval(() => this._refreshSystemReport(), 1000);
  }

  _refreshSystemReport() {
    const now = this._now();
    const report = this.shadowRoot?.querySelector("[data-system-report]");
    if (report && this._hass && this._config) {
      report.textContent = this._t("last_system_report", {
        report: this._systemReportText(now),
      });
    }
    const clock = this.shadowRoot?.querySelector("[data-card-clock]");
    if (clock) {
      clock.textContent = this._clockText(now);
      clock.dateTime = now.toISOString();
    }
  }

  _clockText(now = this._now()) {
    return this._dateFormatter({
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    }).format(now);
  }

  _systemReportText(now = this._now()) {
    const delay = this._entity("report_delay");
    const rawDelay = delay && !UNKNOWN_STATES.has(String(delay.state).toLowerCase())
      ? String(delay.state).trim() : "";
    const delayRange = delayRangeFromValue(rawDelay);
    if (delayRange) {
      this._lastValidSystemReport = {
        type: "range",
        fromTime: now.getTime() - delayRange.throughSeconds * 1000,
        throughTime: now.getTime() - delayRange.fromSeconds * 1000,
      };
    } else {
      const delayDate = rawDelay ? this._parseDate(rawDelay) : null;
      if (delayDate) {
        this._lastValidSystemReport = { type: "date", time: delayDate.getTime() };
      } else {
        const report = this._entity("last_report");
        const reportDate = report && !UNKNOWN_STATES.has(String(report.state).toLowerCase())
          ? this._parseDate(report.state) : null;
        if (reportDate) {
          this._lastValidSystemReport = { type: "date", time: reportDate.getTime() };
        }
      }
    }

    if (!this._lastValidSystemReport) return this._t("unknown");
    if (this._lastValidSystemReport.type === "range") {
      return this._absoluteRange(
        this._lastValidSystemReport.fromTime,
        this._lastValidSystemReport.throughTime,
        now,
      );
    }
    return this._absoluteTime(this._lastValidSystemReport.time, now);
  }

  _warmthIndicator(tankTemperature, coldWaterTemperature) {
    if (!Number.isFinite(tankTemperature) || !Number.isFinite(coldWaterTemperature)) return "";
    if (tankTemperature < coldWaterTemperature + 5) return "slight";
    if (tankTemperature >= coldWaterTemperature + 15) return "strong";
    return "";
  }

  _preheatedWaterText(tankTemperature, coldWaterTemperature) {
    const indicator = this._warmthIndicator(tankTemperature, coldWaterTemperature);
    const warmteindicatie = indicator ? this._t(`warmth_${indicator}`) : "";
    return this._t("preheated_water", { warmteindicatie }).replace(/\s+/g, " ").trim();
  }

  _health(reportingState, alerts, coreKnown) {
    const statusKnown = this._statusChangeTime !== null;
    const lastStatusChange = statusKnown
      ? this._absoluteTime(this._statusChangeTime)
      : this._t("before", { time: this._datedTime(new Date(SOLESTA_CARD_STARTED_AT)) });
    const statusEntities = statusKnown ? this._statusChangeEntityNames : [];
    if (reportingState === false) {
      return {
        tone: "offline",
        icon: "mdi:alert-circle",
        title: this._t("system_offline"),
        detail: this._t("last_status_change", { time: lastStatusChange }),
        entities: statusEntities,
      };
    }
    if (alerts?.some((alert) => alertPresentation(alert).tone === "error")) {
      return {
        tone: "attention",
        icon: "mdi:alert-circle",
        title: this._t("attention_required"),
        detail: this._t("last_status_change", { time: lastStatusChange }),
        entities: statusEntities,
      };
    }
    if (reportingState === null || alerts === null || !coreKnown) {
      return {
        tone: "unknown",
        icon: "mdi:help-circle-outline",
        title: this._t("status_incomplete"),
        detail: this._t("last_status_change", { time: lastStatusChange }),
        entities: statusEntities,
      };
    }
    return {
      tone: "normal",
      icon: "mdi:check-circle-outline",
      title: this._t("all_normal"),
      detail: this._t("last_status_change", { time: lastStatusChange }),
      entities: statusEntities,
    };
  }

  _alertsMarkup(alerts) {
    const items = alerts === null
      ? [{
        type: "",
        message: this._t("alerts_unreadable"),
        severity: "warning",
      }]
      : alerts;
    if (!items.length) return "";

    return `
      <section class="solesta-alerts" aria-label="${escapeHtml(this._t("system_alerts"))}">
        ${items.slice(0, 8).map((alert) => {
          const presentation = alertPresentation(alert);
          return `
            <div class="solesta-alert ${presentation.tone}">
              <span class="solesta-alert-icon"><ha-icon icon="${presentation.icon}"></ha-icon></span>
              <span class="solesta-alert-message">${escapeHtml(alert.message)}</span>
            </div>
          `;
        }).join("")}
      </section>
    `;
  }

  _close() {
    if (this._config?.close_path) {
      window.history.pushState(null, "", this._config.close_path);
      window.dispatchEvent(new Event("location-changed", { bubbles: true }));
      return;
    }
    window.history.back();
  }

  _captureScrollPosition() {
    const positions = [];
    const seen = new Set();
    const remember = (element) => {
      if (!element || seen.has(element)
        || typeof element.scrollTop !== "number") return;
      seen.add(element);
      positions.push({ element, top: element.scrollTop, left: element.scrollLeft });
    };

    let current = this;
    while (current) {
      const root = current.getRootNode?.();
      current = current.parentElement || root?.host || null;
      remember(current);
    }
    remember(document.scrollingElement);
    return {
      positions,
      windowX: window.scrollX,
      windowY: window.scrollY,
    };
  }

  _restoreScrollPosition(snapshot) {
    if (!snapshot) return;
    snapshot.positions.forEach(({ element, top, left }) => {
      if (!element.isConnected) return;
      element.scrollTop = top;
      element.scrollLeft = left;
    });
    window.scrollTo(snapshot.windowX, snapshot.windowY);
  }

  _scheduleScrollRestore(snapshot) {
    const token = ++this._scrollRestoreToken;
    this._restoreScrollPosition(snapshot);
    window.requestAnimationFrame(() => {
      if (token === this._scrollRestoreToken) this._restoreScrollPosition(snapshot);
    });
  }

  _render() {
    if (!this.shadowRoot || !this._config) return;
    this._lastHassRenderSignature = this._hassRenderSignature();
    const scrollPosition = this._captureScrollPosition();

    if (!this._hass || this._configIssue) {
      this.shadowRoot.innerHTML = `
        <ha-card><div class="solesta-loading">${escapeHtml(this._t(this._configIssue || "loading"))}</div></ha-card>
        <style>.solesta-loading{padding:24px;text-align:center}</style>
      `;
      this._scheduleScrollRestore(scrollPosition);
      return;
    }

    const reportingEntity = this._entity("reporting");
    const reportingState = reportingEntity?.state === "on"
      ? true
      : reportingEntity?.state === "off"
        ? false
        : null;
    const reportingOnline = reportingState === true;
    const reportingOffline = reportingState === false;
    const pumpEntity = this._entity("pump_active");
    const pumpKnown = ["on", "off"].includes(pumpEntity?.state);
    const pumpActive = isOn(pumpEntity);
    const alerts = alertItems(this._entity("alerts"));
    const tankTemperatureValue = numberValue(this._entity("tank_temperature"));
    const coldWaterTemperature = this._coldWaterTemperature();
    const warmthIndicator = this._warmthIndicator(
      tankTemperatureValue,
      coldWaterTemperature,
    );
    const temperatureDataKnown = tankTemperatureValue !== null
      && coldWaterTemperature !== null;
    const health = this._health(
      reportingState,
      alerts,
      temperatureDataKnown && pumpKnown,
    );
    const systemName = escapeHtml(this._config.system_name);
    const supportText = escapeHtml(this._config.support_text || this._t("contact_support"));
    const tankTemperature = tankTemperatureValue === null
      ? "—"
      : this._formatNumber(tankTemperatureValue, 0);
    const collectorTemperature = this._formattedNumber("collector_temperature", 1);
    const tankTopTemperature = this._formattedNumber("tank_top_temperature", 1);
    const tankBottomTemperature = this._formattedNumber("tank_bottom_temperature", 1);
    const energyKwh = this._formattedNumber("energy_kwh", 2);
    const energyMj = this._formattedNumber("energy_mj", 2);
    const showers = numberValue(this._entity("showers"));
    const showerText = showers === null ? "—" : String(Math.floor(showers));
    const systemReport = this._systemReportText();
    const systemReportText = escapeHtml(this._t("last_system_report", { report: systemReport }));
    const clockText = escapeHtml(this._clockText());
    const text = (key, replacements = {}) => escapeHtml(this._t(key, replacements));
    const statusText = escapeHtml(this._t(
      pumpKnown ? (pumpActive ? "circulation" : "standby") : "unknown",
    ));
    const heroClass = reportingOnline
      ? (warmthIndicator === "none" ? "neutral" : "online")
      : reportingOffline ? "offline" : "neutral";
    const preheatedWater = escapeHtml(this._preheatedWaterText(
      tankTemperatureValue,
      coldWaterTemperature,
    ));
    const heroMessage = reportingOnline
      ? (temperatureDataKnown ? preheatedWater : text("status_incomplete"))
      : reportingOffline ? supportText : text("status_incomplete");
    const healthDetail = escapeHtml(health.detail);
    const healthEntities = health.entities.length
      ? `(${health.entities.map(escapeHtml).join(", ")})`
      : "";
    const cardClasses = [
      "solesta-shell",
      reportingOnline ? "is-online" : reportingOffline ? "is-offline" : "is-unknown",
      reportingOnline && pumpActive ? "is-pump-active" : "",
    ].filter(Boolean).join(" ");

    this.shadowRoot.innerHTML = `
      <style>${this._styles()}</style>
      <div class="solesta-fit-frame">
      <ha-card class="${cardClasses}">
        <header class="solesta-hero">
          <div class="solesta-orb" aria-hidden="true"></div>
          <div class="solesta-toolbar">
            <div class="solesta-brand">
              <span class="solesta-logo"><img src="${escapeHtml(SOLESTA_LOGO_PATH)}" alt="" /></span>
              <span class="solesta-brand-name">${escapeHtml(INTEGRATION_NAME)}</span>
              <span class="solesta-version">v${SOLESTA_CARD_VERSION}</span>
            </div>
            <div class="solesta-toolbar-actions">
              <time class="solesta-clock" data-card-clock>${clockText}</time>
              <button class="solesta-close" type="button" data-close aria-label="${text("close")}">
                <ha-icon icon="mdi:close"></ha-icon>
              </button>
            </div>
          </div>
          <div class="solesta-hero-main">
            <div class="solesta-hero-label">${text("tank_temperature_is")}</div>
            <div class="solesta-temperature"><strong>${tankTemperature}</strong><span>°C</span></div>
            <div class="solesta-hero-system-name">${systemName}</div>
            <div class="solesta-message ${heroClass}">
              <i aria-hidden="true"></i>
              <span>${heroMessage}</span>
            </div>
          </div>
        </header>

        <main class="solesta-content">
          <section class="solesta-panel solesta-energy-panel">
            <div class="solesta-panel-head">
              <span>${text("in_tank")}</span>
              <ha-icon icon="mdi:water-boiler"></ha-icon>
            </div>
            <div class="solesta-energy"><strong>${energyKwh}</strong><span>kWh</span></div>
            <div class="solesta-subvalue">${energyMj} MJ</div>
          </section>

          <section class="solesta-panel">
            <div class="solesta-panel-head">
              <span>${text("system_status")}</span>
              <strong class="solesta-reporting">${text(reportingOnline ? "online" : reportingOffline ? "offline" : "unknown")}</strong>
            </div>
            <div class="solesta-status-grid">
              <div>
                <span class="solesta-label">${text("energy_for")}</span>
                <strong class="solesta-showers">${showerText}</strong>
                <span class="solesta-label">${text("standard_showers")}</span>
              </div>
              <div class="solesta-divider" aria-hidden="true"></div>
              <div>
                <span class="solesta-label">${text("your_system_status")}</span>
                <strong class="solesta-system-state">${statusText}</strong>
              </div>
            </div>
          </section>

          <section class="solesta-panel solesta-flow-panel">
            <div class="solesta-panel-head solesta-flow-head">
              <strong>${text("how_system_works")}</strong>
              <span class="solesta-live"><i aria-hidden="true"></i>${text(reportingOnline ? "live" : reportingOffline ? "offline" : "unknown").toUpperCase()}</span>
            </div>
            <div class="solesta-flow" role="img" aria-label="${text("flow_diagram")}">
              <div class="solesta-cold-horizontal" aria-hidden="true"></div>
              <div class="solesta-cold-vertical" aria-hidden="true"></div>
              <div class="solesta-hot-vertical" aria-hidden="true"></div>
              <div class="solesta-collector"><span>${text("solar_collector")}</span></div>
              <div class="solesta-tank" aria-hidden="true"><span>${text("storage_tank")}</span></div>
              <div class="solesta-sensor solesta-collector-temp">${collectorTemperature}°</div>
              <div class="solesta-sensor solesta-tank-temp">${tankTopTemperature}°</div>
              <div class="solesta-sensor solesta-tank-bottom-temp">${tankBottomTemperature}°</div>
              <div class="solesta-pump">
                <span class="solesta-pump-rotor" aria-hidden="true">
                  <ha-icon icon="mdi:cog"></ha-icon>
                </span>
              </div>
            </div>
            <div class="solesta-legend" aria-label="${text("legend")}">
              <span><i class="warm"></i>${text("supply_hot")}</span>
              <span><i class="cold"></i>${text("return_cold")}</span>
            </div>
          </section>

          <section class="solesta-panel solesta-temperature-panel">
            ${this._historyMarkup()}
          </section>

          <section class="solesta-health ${health.tone}">
            <span class="solesta-health-icon"><ha-icon icon="${health.icon}"></ha-icon></span>
            <div class="solesta-health-copy">
              <strong>${escapeHtml(health.title)}</strong>
              <div class="solesta-health-detail-row">
                <span class="solesta-health-detail">${healthDetail}</span>
                <details class="solesta-status-info">
                  <summary aria-label="${text("status_change_info")}">
                    <ha-icon icon="mdi:information-outline"></ha-icon>
                  </summary>
                  <span class="solesta-status-info-text">${text("last_status_change_help")}</span>
                </details>
              </div>
              ${healthEntities ? `<span class="solesta-health-entities">${healthEntities}</span>` : ""}
            </div>
          </section>

          ${this._alertsMarkup(alerts)}

          <footer class="solesta-footer">${systemName} · <span data-system-report>${systemReportText}</span></footer>
        </main>
      </ha-card>
      </div>
    `;

    this.shadowRoot.querySelector("[data-close]")?.addEventListener("click", () => this._close());
    this.shadowRoot.querySelectorAll("[data-chart-toggle]").forEach((control) => {
      control.addEventListener("click", () => {
        this._chartMode = this._chartMode === "today" ? "week" : "today";
        this._chartCursorTime = null;
        this._render();
      });
    });
    this._setupChartInteraction();
    this._queueViewportFit();
    this._scheduleScrollRestore(scrollPosition);
  }

  _queueViewportFit() {
    if (!this.isConnected || !this._config || !this._hass) return;
    if (this._fitAnimationFrame) window.cancelAnimationFrame(this._fitAnimationFrame);
    this._fitAnimationFrame = window.requestAnimationFrame(() => {
      this._fitAnimationFrame = null;
      this._fitToViewport();
    });
  }

  _fitToViewport() {
    const frame = this.shadowRoot?.querySelector(".solesta-fit-frame");
    const card = frame?.querySelector("ha-card.solesta-shell");
    if (!frame || !card) return;

    card.style.position = "static";
    card.style.width = "100%";
    card.style.zoom = "1";
    card.style.transform = "none";
    card.style.transformOrigin = "top left";
    frame.style.width = "min(100%, 440px)";
    frame.style.height = "auto";

    if (!this._config.fit_to_viewport) return;

    const parentWidth = Math.max(
      1,
      Math.min(
        440,
        this.parentElement?.getBoundingClientRect().width || window.innerWidth || 440,
      ),
    );
    frame.style.width = `${parentWidth}px`;
    card.style.width = `${parentWidth}px`;

    const naturalHeight = Math.max(card.scrollHeight, card.getBoundingClientRect().height);
    const viewportHeight = window.visualViewport?.height || window.innerHeight || naturalHeight;
    const frameTop = Math.max(0, frame.getBoundingClientRect().top);
    const availableHeight = Math.max(1, viewportHeight - frameTop - 8);
    const scale = Math.max(0.1, Math.min(1, availableHeight / naturalHeight));

    card.style.position = "absolute";
    card.style.inset = "0 auto auto 0";
    if (window.CSS?.supports?.("zoom", String(scale))) {
      card.style.zoom = String(scale);
    } else {
      card.style.transform = `scale(${scale})`;
    }
    frame.style.width = `${Math.ceil(parentWidth * scale)}px`;
    frame.style.height = `${Math.ceil(naturalHeight * scale)}px`;
  }

  _temperatureAt(points, time) {
    if (!points.length) return null;
    let lower = 0;
    let upper = points.length;
    while (lower < upper) {
      const middle = Math.floor((lower + upper) / 2);
      if (points[middle].time <= time) lower = middle + 1;
      else upper = middle;
    }
    return lower ? points[lower - 1].value : null;
  }

  _timeWeightedAverage(points, startTime, endTime) {
    if (!points.length || endTime <= startTime) return null;
    let value = this._temperatureAt(points, startTime);
    let cursor = startTime;
    let weighted = 0;
    let knownDuration = 0;
    for (const point of points) {
      if (point.time <= startTime) continue;
      if (point.time >= endTime) break;
      const interval = point.time - cursor;
      if (value !== null) {
        weighted += value * interval;
        knownDuration += interval;
      }
      cursor = point.time;
      value = point.value;
    }
    if (value !== null && cursor < endTime) {
      weighted += value * (endTime - cursor);
      knownDuration += endTime - cursor;
    }
    return knownDuration ? weighted / knownDuration : null;
  }

  _temperatureRange(points, startTime, endTime, includeEnd = false) {
    if (!points.length || endTime <= startTime) return null;
    const values = [];
    const startingValue = this._temperatureAt(points, startTime);
    if (startingValue !== null) values.push(startingValue);
    for (const point of points) {
      if (point.time <= startTime) continue;
      if (point.time > endTime || (!includeEnd && point.time === endTime)) break;
      if (point.value !== null) values.push(point.value);
    }
    return values.length ? {
      minimum: Math.min(...values),
      maximum: Math.max(...values),
    } : null;
  }

  _chartTemperatureScale(points) {
    const values = points
      .map((point) => point.value)
      .filter((value) => value !== null && Number.isFinite(value));
    if (!values.length) {
      return {
        minimum: Math.min(89, this._coldWaterTemperature() ?? 0),
        maximum: 90,
      };
    }
    const observedMinimum = Math.min(...values);
    const observedMaximum = Math.max(...values);
    const observedSpan = observedMaximum - observedMinimum;
    const padding = observedSpan > 0 ? Math.max(1, observedSpan * .12) : 2;
    let minimum = Math.floor(observedMinimum - padding);
    let maximum = Math.ceil(observedMaximum + padding);
    if (minimum === maximum) {
      minimum -= 1;
      maximum += 1;
    }
    return { minimum, maximum };
  }

  _chartPath(points, xFor, yFor) {
    const path = [];
    let previous = null;
    for (const point of points) {
      const x = xFor(point.time).toFixed(1);
      if (point.value === null) {
        if (previous) {
          path.push(`L${x},${yFor(previous.value).toFixed(1)}`);
        }
        previous = null;
        continue;
      }
      const y = yFor(point.value).toFixed(1);
      if (!previous) {
        path.push(`M${x},${y}`);
      } else {
        path.push(`L${x},${yFor(previous.value).toFixed(1)}`);
        if (point.value !== previous.value) path.push(`L${x},${y}`);
      }
      previous = point;
    }
    return path.join(" ");
  }

  _periodHistory(startTime, endTime) {
    const history = this._history
      .filter((point) => point.time <= endTime)
      .map((point) => ({ ...point }))
      .sort((left, right) => left.time - right.time);
    const before = history.filter((point) => point.time <= startTime).at(-1);
    const points = before ? [{ time: startTime, value: before.value }] : [];
    points.push(...history.filter((point) => point.time > startTime));
    const currentState = this._entity("tank_temperature");
    const current = numberValue(currentState);
    const currentChanged = this._parseDate(
      currentState?.last_changed || currentState?.last_updated,
    )?.getTime();
    const lastHistoryTime = points.at(-1)?.time ?? Number.NEGATIVE_INFINITY;
    if (Number.isFinite(currentChanged)
      && currentChanged > Math.max(startTime, lastHistoryTime)
      && currentChanged < endTime) {
      points.push({ time: currentChanged, value: current });
    }
    points.push({ time: endTime, value: current });
    return points.reduce((result, point) => {
      if (result.at(-1)?.time === point.time) result[result.length - 1] = point;
      else result.push(point);
      return result;
    }, []);
  }

  _chartCursorData(time, model = this._chartModel) {
    if (!model) return null;
    const cursorTime = Math.max(model.startTime, Math.min(model.endTime, time));
    const ratio = (cursorTime - model.startTime)
      / Math.max(1, model.endTime - model.startTime);
    const value = this._temperatureAt(model.points, cursorTime);
    const day = model.days.find((candidate, index) => cursorTime >= candidate.startTime
      && (cursorTime < candidate.endTime || index === model.days.length - 1));
    const average = day?.average ?? null;
    const temperatureText = value === null
      ? "—"
      : `${this._formatNumber(value, 1)} °C`;
    const averageText = this._t("average", {
      temperature: average === null ? "—" : `${this._formatNumber(average, 1)} °C`,
    });
    const dayText = `${day?.label || this._t("day")} · ${averageText}`;
    const momentText = `${this._shortTime(new Date(cursorTime))} · ${temperatureText}`;
    const y = value === null ? null : model.yFor(value);
    return {
      time: cursorTime,
      ratio,
      x: ratio * model.width,
      y,
      dayText,
      momentText,
      ariaText: `${dayText}; ${momentText}`,
    };
  }

  _applyChartCursor(time = this._chartCursorTime ?? this._chartModel?.endTime) {
    const data = this._chartCursorData(time);
    const surface = this.shadowRoot?.querySelector("[data-chart-scrubber]");
    if (!data || !surface) return;
    this._chartCursorTime = data.time;

    const line = surface.querySelector("[data-chart-cursor-line]");
    line?.setAttribute("x1", data.x.toFixed(1));
    line?.setAttribute("x2", data.x.toFixed(1));

    const point = surface.querySelector("[data-chart-cursor-point]");
    if (point) {
      point.setAttribute("cx", data.x.toFixed(1));
      if (data.y === null) point.setAttribute("hidden", "");
      else {
        point.removeAttribute("hidden");
        point.setAttribute("cy", data.y.toFixed(1));
      }
    }

    const tooltip = surface.querySelector("[data-chart-tooltip]");
    if (tooltip) {
      tooltip.style.left = `${(data.ratio * 100).toFixed(2)}%`;
      tooltip.classList.toggle("align-right", data.ratio > 0.56);
    }
    const dayLabel = surface.querySelector("[data-chart-day-label]");
    const momentLabel = surface.querySelector("[data-chart-moment-label]");
    if (dayLabel) dayLabel.textContent = data.dayText;
    if (momentLabel) momentLabel.textContent = data.momentText;
    surface.setAttribute("aria-valuenow", String(Math.round(data.time)));
    surface.setAttribute("aria-valuetext", data.ariaText);
  }

  _updateChartCursorFromClientX(clientX) {
    const surface = this.shadowRoot?.querySelector("[data-chart-scrubber]");
    const model = this._chartModel;
    if (!surface || !model || !Number.isFinite(clientX)) return;
    const bounds = surface.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - bounds.left) / Math.max(1, bounds.width)));
    this._applyChartCursor(model.startTime
      + ratio * (model.endTime - model.startTime));
  }

  _setupChartInteraction() {
    const surface = this.shadowRoot?.querySelector("[data-chart-scrubber]");
    if (!surface || !this._chartModel) return;

    surface.addEventListener("pointerdown", (event) => {
      this._chartPointerActive = true;
      surface.focus?.({ preventScroll: true });
      surface.setPointerCapture?.(event.pointerId);
      this._updateChartCursorFromClientX(event.clientX);
    });
    surface.addEventListener("pointermove", (event) => {
      if (this._chartPointerActive || event.pointerType === "mouse") {
        this._updateChartCursorFromClientX(event.clientX);
      }
    });
    const finishPointer = (event) => {
      this._chartPointerActive = false;
      if (surface.hasPointerCapture?.(event.pointerId)) {
        surface.releasePointerCapture(event.pointerId);
      }
    };
    surface.addEventListener("pointerup", finishPointer);
    surface.addEventListener("pointercancel", finishPointer);
    surface.addEventListener("keydown", (event) => {
      const model = this._chartModel;
      if (!model) return;
      const step = this._chartMode === "today" ? 15 * 60 * 1000 : 60 * 60 * 1000;
      let nextTime = this._chartCursorTime ?? model.endTime;
      if (event.key === "ArrowLeft") nextTime -= step;
      else if (event.key === "ArrowRight") nextTime += step;
      else if (event.key === "Home") nextTime = model.startTime;
      else if (event.key === "End") nextTime = model.endTime;
      else return;
      event.preventDefault();
      this._applyChartCursor(nextTime);
    });
    this._applyChartCursor();
  }

  _historyMarkup() {
    const now = this._now();
    let start = this._startOfDay(now);
    if (this._chartMode === "week") start = this._addCalendarDays(start, -6);

    if (!start) return escapeHtml(this._t("history_unavailable"));

    const startTime = start.getTime();
    const endTime = now.getTime();
    const points = this._periodHistory(startTime, endTime);
    const hasMeasurements = points.some((point) => point.value !== null);

    const { minimum, maximum } = this._chartTemperatureScale(points);
    const width = 360;
    const weekMode = this._chartMode === "week";
    const svgHeight = 166;
    const chartTop = 28;
    const chartBottom = 120;
    const chartHeight = chartBottom - chartTop;
    const duration = Math.max(1, endTime - startTime);
    const xFor = (time) => ((time - startTime) / duration) * width;
    const yFor = (value) => chartTop
      + ((maximum - Math.max(minimum, Math.min(maximum, value))) / (maximum - minimum))
      * chartHeight;
    const line = this._chartPath(points, xFor, yFor);

    const bands = [];
    const labels = [];
    const days = [];
    const todayKey = this._calendarKey(now);
    const weekday = this._dateFormatter({ weekday: "short" });
    const weekdayFull = this._dateFormatter({ weekday: "long" });
    let cursor = start;
    let bandIndex = 0;
    while (cursor.getTime() < endTime) {
      const next = this._addCalendarDays(cursor, 1);
      const bandStart = Math.max(startTime, cursor.getTime());
      const bandEnd = Math.min(endTime, next.getTime());
      const key = this._calendarKey(cursor);
      const x = xFor(bandStart);
      const bandWidth = Math.max(0, xFor(bandEnd) - x);
      const average = this._timeWeightedAverage(points, bandStart, bandEnd);
      const range = this._temperatureRange(
        points,
        bandStart,
        bandEnd,
        bandEnd === endTime,
      );
      days.push({
        startTime: bandStart,
        endTime: bandEnd,
        average,
        minimum: range?.minimum ?? null,
        maximum: range?.maximum ?? null,
        label: key === todayKey ? this._t("today") : weekdayFull.format(cursor),
      });
      const todayClass = key === todayKey ? "today" : bandIndex % 2 ? "alternate" : "";
      if (range) {
        const barGap = weekMode ? bandWidth * .18 : 0;
        const barX = x + barGap;
        const barWidth = Math.max(0, bandWidth - barGap * 2);
        const barTop = yFor(range.maximum);
        const barBottom = yFor(range.minimum);
        const barHeight = Math.max(3, barBottom - barTop);
        const rangeTitle = this._t("day_range", {
          day: weekday.format(cursor),
          minimum: `${this._formatNumber(range.minimum, 1)} °C`,
          maximum: `${this._formatNumber(range.maximum, 1)} °C`,
        });
        const cornerRadius = weekMode ? Math.min(12, barWidth / 2) : barWidth / 2;
        bands.push(`<rect class="solesta-chart-day ${todayClass}" x="${barX.toFixed(1)}" y="${barTop.toFixed(1)}" width="${barWidth.toFixed(1)}" height="${barHeight.toFixed(1)}" rx="${cornerRadius.toFixed(1)}"><title>${escapeHtml(rangeTitle)}</title></rect>`);
      }
      if (weekMode) {
        const center = (x + bandWidth / 2).toFixed(1);
        const maximumLabel = range ? `${this._formatNumber(range.maximum, 0)}°` : "—";
        const minimumLabel = range ? `${this._formatNumber(range.minimum, 0)}°` : "—";
        labels.push(`<text class="solesta-chart-range-label maximum" x="${center}" y="14" text-anchor="middle">${escapeHtml(maximumLabel)}</text>`);
        labels.push(`<text class="solesta-chart-range-label minimum" x="${center}" y="140" text-anchor="middle">${escapeHtml(minimumLabel)}</text>`);
        labels.push(`<text class="solesta-chart-x-label" x="${center}" y="158" text-anchor="middle">${escapeHtml(weekday.format(cursor).replace(/\.$/, ""))}</text>`);
      } else {
        const center = (x + bandWidth / 2).toFixed(1);
        const maximumLabel = range ? `${this._formatNumber(range.maximum, 1)}°` : "—";
        const minimumLabel = range ? `${this._formatNumber(range.minimum, 1)}°` : "—";
        labels.push(`<text class="solesta-chart-range-label maximum" x="${center}" y="14" text-anchor="middle">${escapeHtml(maximumLabel)}</text>`);
        labels.push(`<text class="solesta-chart-range-label minimum" x="${center}" y="140" text-anchor="middle">${escapeHtml(minimumLabel)}</text>`);
      }
      cursor = next;
      bandIndex += 1;
    }

    if (this._chartMode === "today") {
      const currentTime = this._shortTime(now);
      labels.push('<text class="solesta-chart-x-label" x="4" y="158" text-anchor="start">00:00</text>');
      labels.push(`<text class="solesta-chart-x-label" x="356" y="158" text-anchor="end">${currentTime}</text>`);
    }

    const midpoint = Math.round((minimum + maximum) / 2);
    const emptyText = this._t(this._historyLoading
      ? "history_loading"
      : this._historyError
        ? "history_unavailable"
        : "no_temperature_history");
    const title = this._t(this._chartMode === "today"
      ? "tank_temperature_today" : "tank_temperature_week");
    this._chartModel = {
      startTime,
      endTime,
      width,
      chartTop,
      chartBottom,
      points,
      days,
      yFor,
    };
    const cursorData = this._chartCursorData(this._chartCursorTime ?? endTime);
    this._chartCursorTime = cursorData?.time ?? endTime;
    const cursorPointHidden = cursorData?.y === null ? " hidden" : "";
    const cursorY = cursorData?.y ?? chartBottom;
    const tooltipAlignment = cursorData?.ratio > 0.56 ? " align-right" : "";
    return `
      <div class="solesta-chart-heading">
        <div class="solesta-chart-heading-copy">
          <strong>${escapeHtml(title)}</strong>
          <span>${escapeHtml(this._t(weekMode ? "daily_range" : "temperature_range"))}</span>
        </div>
        ${this._historyError ? `<span class="solesta-history-warning" title="${escapeHtml(this._t("history_unavailable"))}" aria-label="${escapeHtml(this._t("history_unavailable"))}"><ha-icon icon="mdi:cloud-alert-outline"></ha-icon></span>` : ""}
        <button class="solesta-chart-switch ${weekMode ? "is-week" : "is-today"}"
          type="button" data-chart-toggle aria-label="${escapeHtml(this._t(weekMode ? "show_today" : "show_seven_days"))}"
          aria-pressed="${weekMode}">
          <ha-icon class="solesta-mode-icon today" icon="mdi:calendar-today"></ha-icon>
          <span class="solesta-switch-track" aria-hidden="true"><i></i></span>
          <ha-icon class="solesta-mode-icon week" icon="mdi:calendar-week"></ha-icon>
        </button>
      </div>
      <div class="solesta-chart-interaction" data-chart-scrubber role="slider" tabindex="0"
        aria-label="${escapeHtml(this._t("select_temperature_moment"))}"
        aria-valuemin="${Math.round(startTime)}" aria-valuemax="${Math.round(endTime)}"
        aria-valuenow="${Math.round(cursorData?.time ?? endTime)}"
        aria-valuetext="${escapeHtml(cursorData?.ariaText || this._t("no_temperature_measurement"))}">
        <svg class="solesta-chart" viewBox="0 0 360 ${svgHeight}" role="img"
          aria-label="${escapeHtml(this._t("chart_range", {
            title,
            minimum: this._formatNumber(minimum, 0),
            maximum: this._formatNumber(maximum, 0),
          }))}">
          ${bands.join("")}
          <line class="solesta-chart-grid" x1="0" y1="${chartTop}" x2="360" y2="${chartTop}"></line>
          <line class="solesta-chart-grid" x1="0" y1="${yFor(midpoint).toFixed(1)}" x2="360" y2="${yFor(midpoint).toFixed(1)}"></line>
          <line class="solesta-chart-grid" x1="0" y1="${chartBottom}" x2="360" y2="${chartBottom}"></line>
          <text class="solesta-chart-y-label" x="5" y="${chartTop + 11}">${this._formatNumber(maximum, 0)}°</text>
          <text class="solesta-chart-y-label" x="5" y="${yFor(midpoint) - 4}">${this._formatNumber(midpoint, 0)}°</text>
          <text class="solesta-chart-y-label" x="5" y="${chartBottom - 5}">${this._formatNumber(minimum, 0)}°</text>
          ${line ? `<path class="solesta-temperature-line" d="${line}"></path>` : ""}
          ${points.at(-1)?.value !== null ? `<circle class="solesta-temperature-point" cx="${xFor(points.at(-1).time).toFixed(1)}" cy="${yFor(points.at(-1).value).toFixed(1)}" r="3.5"></circle>` : ""}
          <line class="solesta-chart-cursor-line" data-chart-cursor-line
            x1="${(cursorData?.x ?? width).toFixed(1)}" y1="${chartTop}"
            x2="${(cursorData?.x ?? width).toFixed(1)}" y2="${chartBottom}"></line>
          <circle class="solesta-chart-cursor-point" data-chart-cursor-point
            cx="${(cursorData?.x ?? width).toFixed(1)}" cy="${cursorY.toFixed(1)}" r="4"${cursorPointHidden}></circle>
          ${hasMeasurements ? "" : `<text class="solesta-chart-empty" x="180" y="73" text-anchor="middle">${escapeHtml(emptyText)}</text>`}
          ${labels.join("")}
        </svg>
        <div class="solesta-chart-tooltip${tooltipAlignment}" data-chart-tooltip
          style="left:${((cursorData?.ratio ?? 1) * 100).toFixed(2)}%">
          <span data-chart-day-label>${escapeHtml(cursorData?.dayText || `${this._t("day")} · ${this._t("average", { temperature: "—" })}`)}</span>
          <strong data-chart-moment-label>${escapeHtml(cursorData?.momentText || "—")}</strong>
        </div>
      </div>
    `;
  }

  _coldWaterTemperature() {
    return numberValue(this._entity("cold_water_temperature"));
  }

  _scheduleHistoryLoad(force) {
    if (!this.isConnected || !this._hass || !this._config || this._configIssue
      || !this._config.entities.tank_temperature || this._historyLoading) return;
    const now = Date.now();
    const maxAge = 15 * 60 * 1000;
    if (!force && !this._historyError && now - this._historyLoadedAt < maxAge) return;
    const delay = !force && this._historyError
      ? Math.max(0, this._historyRetryAt - now)
      : 0;
    if (this._historyTimer) {
      if (delay > 0) return;
      window.clearTimeout(this._historyTimer);
    }
    this._historyTimer = window.setTimeout(() => {
      this._historyTimer = null;
      this._loadHistory();
    }, delay);
  }

  async _loadHistory() {
    if (!this._hass?.callApi || this._historyLoading || this._configIssue
      || !this._config?.entities?.tank_temperature) return;
    const generation = this._historyGeneration;
    const entityId = this._config.entities.tank_temperature;
    this._historyLoading = true;
    this._render();

    try {
      const now = this._now();
      const today = this._startOfDay(now);
      const start = today && this._addCalendarDays(today, -6);
      if (!start) throw new Error("Unable to calculate the Home Assistant calendar boundary.");
      const path = `history/period/${encodeURIComponent(start.toISOString())}`
        + `?filter_entity_id=${encodeURIComponent(entityId)}`
        + `&end_time=${encodeURIComponent(now.toISOString())}`
        + "&minimal_response&no_attributes";
      const response = await this._hass.callApi("GET", path);
      if (generation !== this._historyGeneration) return;
      const states = Array.isArray(response?.[0]) ? response[0] : [];
      this._history = this._temperatureHistory(states);
      this._historyLoadedAt = Date.now();
      this._historyError = false;
      this._historyRetryDelay = 30 * 1000;
      this._historyRetryAt = 0;
    } catch (_error) {
      if (generation !== this._historyGeneration) return;
      this._historyError = true;
      this._historyLoadedAt = 0;
      this._historyRetryAt = Date.now() + this._historyRetryDelay;
      this._historyRetryDelay = Math.min(15 * 60 * 1000, this._historyRetryDelay * 2);
    } finally {
      if (generation !== this._historyGeneration) return;
      this._historyLoading = false;
      if (this.isConnected) {
        this._render();
        const delay = this._historyError
          ? Math.max(0, this._historyRetryAt - Date.now())
          : 15 * 60 * 1000;
        this._historyTimer = window.setTimeout(() => {
          this._historyTimer = null;
          this._loadHistory();
        }, delay);
      } else {
        this._historyTimer = null;
      }
    }
  }

  _temperatureHistory(states) {
    const points = states.map((state) => {
      const rawValue = state.state ?? state.s;
      const valueText = String(rawValue ?? "").trim();
      const parsedValue = Number.parseFloat(valueText.replace(",", "."));
      const value = UNKNOWN_STATES.has(valueText.toLowerCase()) || !Number.isFinite(parsedValue)
        ? null
        : parsedValue;
      const timestampValue = state.last_changed
        || state.last_updated
        || state.lu
        || null;
      const time = this._parseDate(timestampValue)?.getTime() ?? Number.NaN;
      return { time, value };
    }).filter((point) => Number.isFinite(point.time))
      .sort((left, right) => left.time - right.time);

    const unique = points.reduce((result, point) => {
      if (result.at(-1)?.time === point.time) result[result.length - 1] = point;
      else result.push(point);
      return result;
    }, []);

    const maximumPoints = 720;
    if (unique.length <= maximumPoints) return unique;

    const bucketCapacity = 6;
    const bucketCount = Math.max(1, Math.floor((maximumPoints - 2) / bucketCapacity));
    const firstTime = unique[0].time;
    const lastTime = unique.at(-1).time;
    const duration = Math.max(1, lastTime - firstTime);
    const buckets = Array.from({ length: bucketCount }, () => []);
    for (const point of unique.slice(1, -1)) {
      const index = Math.min(
        bucketCount - 1,
        Math.floor(((point.time - firstTime) / duration) * bucketCount),
      );
      buckets[index].push(point);
    }
    const sampled = [unique[0]];
    for (const bucket of buckets) {
      if (!bucket.length) continue;
      const numeric = bucket.filter((point) => point.value !== null);
      const candidates = [
        bucket[0],
        bucket.at(-1),
        numeric.reduce((best, point) => !best || point.value < best.value ? point : best, null),
        numeric.reduce((best, point) => !best || point.value > best.value ? point : best, null),
        bucket.find((point) => point.value === null),
        bucket.findLast((point) => point.value === null),
      ].filter(Boolean);
      sampled.push(...candidates);
    }
    sampled.push(unique.at(-1));
    return [...new Map(sampled.map((point) => [point.time, point])).values()]
      .sort((left, right) => left.time - right.time)
      .slice(0, maximumPoints);
  }

  _styles() {
    return `
      :host {
        display: block;
        width: 100%;
        margin: 0 auto;
        overflow-anchor: none;
        color: #13242b;
        font-family: Roboto, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      * { box-sizing: border-box; }
      .solesta-fit-frame {
        position: relative;
        width: min(100%, 440px);
        margin: 0 auto;
      }
      ha-card.solesta-shell {
        width: 100%;
        overflow: hidden;
        border: 0;
        border-radius: 0;
        background: #e3e6ec;
        box-shadow: 0 0 80px -20px rgba(20, 36, 43, .25);
      }
      .solesta-hero {
        position: relative;
        min-height: 292px;
        overflow: hidden;
        padding: 20px 24px 30px;
        color: #fff;
        background: linear-gradient(165deg, #002f3c, #0c4757);
      }
      .solesta-orb {
        position: absolute;
        top: -40px;
        right: -30px;
        width: 160px;
        height: 160px;
        border-radius: 50%;
        background: rgba(241, 133, 34, .14);
      }
      .solesta-toolbar {
        position: relative;
        z-index: 2;
        display: flex;
        align-items: center;
        justify-content: space-between;
      }
      .solesta-brand {
        display: flex;
        align-items: center;
        gap: 8px;
        font-family: Sora, Roboto, sans-serif;
        font-size: 17px;
        font-weight: 700;
      }
      .solesta-brand-name { white-space: nowrap; }
      .solesta-version {
        border: 1px solid rgba(255, 255, 255, .24);
        border-radius: 999px;
        padding: 2px 5px;
        color: rgba(255, 255, 255, .66);
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 9px;
        font-weight: 600;
        line-height: 1.2;
        white-space: nowrap;
      }
      .solesta-logo {
        display: grid;
        place-items: center;
        width: 36px;
        height: 36px;
      }
      .solesta-logo img {
        display: block;
        width: 36px;
        height: 36px;
        object-fit: contain;
        filter: drop-shadow(0 3px 5px rgba(0, 0, 0, .18));
      }
      .solesta-toolbar-actions {
        display: flex;
        align-items: center;
        gap: 2px;
      }
      .solesta-clock {
        min-width: 56px;
        color: rgba(255, 255, 255, .72);
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 11px;
        font-variant-numeric: tabular-nums;
        line-height: 1;
        text-align: right;
        white-space: nowrap;
      }
      .solesta-close {
        display: grid;
        place-items: center;
        width: 40px;
        height: 40px;
        border: 0;
        padding: 0;
        color: rgba(255, 255, 255, .72);
        background: transparent;
        cursor: pointer;
      }
      .solesta-close ha-icon { --mdc-icon-size: 24px; }
      .solesta-hero-main {
        position: relative;
        z-index: 1;
        margin-top: 28px;
        text-align: center;
      }
      .solesta-hero-label {
        color: rgba(255, 255, 255, .65);
        font-size: 13px;
      }
      .solesta-temperature {
        display: flex;
        align-items: flex-start;
        justify-content: center;
        gap: 4px;
        margin-top: 6px;
      }
      .solesta-temperature strong {
        font-family: Sora, Roboto, sans-serif;
        font-size: 72px;
        font-weight: 800;
        line-height: 1;
        letter-spacing: -.02em;
      }
      .solesta-temperature span {
        margin-top: 8px;
        color: rgba(255, 255, 255, .7);
        font-size: 30px;
        font-weight: 600;
      }
      .solesta-hero-system-name {
        margin-top: 8px;
        color: rgba(255, 255, 255, .68);
        font-family: Sora, Roboto, sans-serif;
        font-size: 11px;
        font-weight: 500;
        letter-spacing: .08em;
        line-height: 1.3;
      }
      .solesta-message {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin-top: 15px;
        padding: 9px 15px;
        border-radius: 999px;
        font-size: 13px;
        font-weight: 600;
      }
      .solesta-message i,
      .solesta-live i {
        width: 8px;
        height: 8px;
        border-radius: 50%;
      }
      .solesta-message.online {
        color: #9bf0c8;
        background: rgba(66, 201, 139, .2);
      }
      .solesta-message.online i { background: #42c98b; animation: solesta-pulse 2s infinite; }
      .solesta-message.neutral {
        color: #dce5e8;
        background: rgba(220, 229, 232, .14);
      }
      .solesta-message.neutral i { background: #b9c7cc; }
      .solesta-message.offline {
        color: #ffb4b0;
        background: rgba(232, 54, 48, .2);
      }
      .solesta-message.offline i { background: #e83630; animation: solesta-pulse 2s infinite; }
      .solesta-content {
        display: flex;
        flex-direction: column;
        gap: 16px;
        margin-top: 0;
        padding: 16px 20px 24px;
      }
      .solesta-panel {
        position: relative;
        z-index: 2;
        border-radius: 13px;
        padding: 20px;
        background: #fff;
        box-shadow: 0 10px 30px -18px rgba(20, 36, 43, .3);
      }
      .solesta-panel-head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 14px;
        color: #6c7a82;
        font-size: 13px;
        font-weight: 600;
      }
      .solesta-panel-head > ha-icon { color: #f18522; --mdc-icon-size: 20px; }
      .solesta-energy {
        display: flex;
        align-items: baseline;
        gap: 7px;
      }
      .solesta-energy strong {
        color: #f18522;
        font-family: Sora, Roboto, sans-serif;
        font-size: 38px;
        font-weight: 800;
        letter-spacing: -.02em;
      }
      .solesta-energy span {
        color: #6c7a82;
        font-size: 16px;
        font-weight: 600;
      }
      .solesta-subvalue { margin-top: 4px; color: #6c7a82; font-size: 13px; }
      .solesta-reporting { color: #42c98b; font-family: Sora, Roboto, sans-serif; font-size: 14px; }
      .is-offline .solesta-reporting,
      .is-unknown .solesta-reporting { color: #6c7a82; }
      .solesta-status-grid {
        display: grid;
        grid-template-columns: 1fr 1px 1fr;
        gap: 16px;
      }
      .solesta-divider { background: #e7e9ef; }
      .solesta-label { display: block; color: #6c7a82; font-size: 12px; line-height: 1.55; }
      .solesta-showers {
        display: block;
        margin: 4px 0 2px;
        color: #13242b;
        font-family: Sora, Roboto, sans-serif;
        font-size: 28px;
        font-weight: 800;
      }
      .solesta-system-state {
        display: block;
        margin-top: 8px;
        color: #f18522;
        font-family: Sora, Roboto, sans-serif;
        font-size: 18px;
      }
      .solesta-flow-head { margin-bottom: 7px; }
      .solesta-flow-head > strong { color: #13242b; font-family: Sora, Roboto, sans-serif; font-size: 14px; }
      .solesta-live {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        color: #42c98b;
        font-size: 11px;
        font-weight: 700;
      }
      .solesta-live i { width: 6px; height: 6px; background: #42c98b; animation: solesta-pulse 1.6s infinite; }
      .is-offline .solesta-live,
      .is-unknown .solesta-live { color: #6c7a82; }
      .is-offline .solesta-live i,
      .is-unknown .solesta-live i { background: #aeb7bc; animation: none; }
      .solesta-flow {
        position: relative;
        height: 190px;
        overflow: hidden;
        border: 1px solid #e7e9ef;
        border-radius: 24px;
        background: linear-gradient(180deg, #fbfcfe, #f4f6f9);
      }
      .solesta-collector {
        position: absolute;
        z-index: 2;
        top: 27px;
        left: 18%;
        display: grid;
        place-items: center;
        width: 54%;
        height: 34px;
        border-radius: 7px;
        color: rgba(255, 255, 255, .75);
        background: linear-gradient(135deg, #002f3c, #0c4757);
        box-shadow: 0 8px 20px -10px rgba(0, 47, 60, .5);
        transform: skewX(-14deg);
      }
      .solesta-collector span {
        color: rgba(255, 255, 255, .75);
        font-family: Roboto, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 8px;
        font-weight: 400;
        letter-spacing: .1em;
        transform: skewX(14deg);
      }
      .solesta-tank {
        position: absolute;
        z-index: 2;
        top: 41px;
        right: 10%;
        width: 44px;
        height: 110px;
        border: 2px solid #002f3c;
        border-radius: 30px 30px 8px 8px;
        background: linear-gradient(to top, rgba(241, 133, 34, .35), rgba(241, 133, 34, .05) 60%, #fff);
      }
      .solesta-tank span {
        position: absolute;
        top: 50%;
        left: 50%;
        border-radius: 4px;
        padding: 2px 4px;
        color: #002f3c;
        background: rgba(255, 255, 255, .68);
        font-family: Roboto, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        font-size: 8px;
        font-weight: 400;
        letter-spacing: .1em;
        line-height: 1;
        text-transform: uppercase;
        white-space: nowrap;
        transform: translate(-50%, -50%) rotate(90deg);
      }
      .solesta-hot-vertical,
      .solesta-cold-horizontal,
      .solesta-cold-vertical { position: absolute; z-index: 1; }
      .solesta-hot-vertical {
        top: 41px;
        left: 72%;
        width: 4px;
        height: 76px;
        background: repeating-linear-gradient(180deg, #f18522 0 7px, transparent 7px 14px);
        background-size: 4px 20px;
      }
      .solesta-cold-horizontal {
        bottom: 25px;
        left: 18%;
        width: 54%;
        height: 4px;
        background: repeating-linear-gradient(90deg, #3b82f6 0 7px, transparent 7px 14px);
        background-size: 20px 4px;
      }
      .solesta-cold-vertical {
        top: 41px;
        left: 18%;
        width: 4px;
        height: 110px;
        background: repeating-linear-gradient(180deg, #3b82f6 0 7px, transparent 7px 14px);
        background-size: 4px 20px;
      }
      .is-pump-active .solesta-hot-vertical {
        animation: solesta-flow-vertical-down 1s linear infinite;
      }
      .is-pump-active .solesta-cold-horizontal {
        animation: solesta-flow-horizontal-left 1.1s linear infinite;
      }
      .is-pump-active .solesta-cold-vertical {
        animation: solesta-flow-vertical-up 1.1s linear infinite;
      }
      .solesta-pump {
        position: absolute;
        z-index: 4;
        bottom: 15px;
        left: calc(18% - 13px);
        display: grid;
        place-items: center;
        width: 30px;
        height: 30px;
        border: 2px solid #42c98b;
        border-radius: 50%;
        color: #42c98b;
        background: #fff;
        box-shadow: 0 4px 12px -4px rgba(66, 201, 139, .6);
      }
      .solesta-pump-rotor {
        display: grid;
        place-items: center;
        line-height: 0;
        transform-origin: center;
      }
      .solesta-pump ha-icon { --mdc-icon-size: 17px; }
      .is-pump-active .solesta-pump-rotor { animation: solesta-spin 2.4s linear infinite; }
      .solesta-sensor {
        position: absolute;
        z-index: 5;
        border: 2px solid;
        border-radius: 12px;
        padding: 5px 8px;
        color: #fff;
        background: #002f3c;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 11px;
        font-weight: 700;
      }
      .solesta-collector-temp { top: 8px; left: 14%; border-color: #f7a70b; }
      .solesta-tank-temp { top: 34px; right: 18%; border-color: #e83630; }
      .solesta-tank-bottom-temp { top: 130px; right: 18%; border-color: #3b82f6; }
      .solesta-legend {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: 18px;
        margin-top: 14px;
        color: #6c7a82;
        font-size: 11px;
      }
      .solesta-legend span { display: inline-flex; align-items: center; gap: 7px; }
      .solesta-legend i { width: 14px; height: 4px; border-radius: 2px; }
      .solesta-legend .warm { background: #f18522; }
      .solesta-legend .cold { background: #3b82f6; }
      .solesta-temperature-panel { overflow: hidden; }
      .solesta-chart-heading {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 10px;
      }
      .solesta-chart-heading strong {
        color: #13242b;
        font-family: Sora, Roboto, sans-serif;
        font-size: 14px;
      }
      .solesta-chart-heading-copy {
        display: flex;
        min-width: 0;
        flex-direction: column;
        gap: 2px;
      }
      .solesta-chart-heading-copy > span {
        color: #6c7a82;
        font-size: 9px;
      }
      .solesta-history-warning {
        display: inline-flex;
        margin-left: auto;
        margin-right: 9px;
        color: #a96f00;
      }
      .solesta-history-warning ha-icon { --mdc-icon-size: 18px; }
      .solesta-chart-switch {
        display: inline-flex;
        align-items: center;
        gap: 7px;
        border: 0;
        border-radius: 999px;
        padding: 4px 7px;
        color: #8a969c;
        background: #eef1f3;
        cursor: pointer;
        -webkit-tap-highlight-color: transparent;
      }
      .solesta-chart-switch:focus-visible {
        outline: 2px solid #0c4757;
        outline-offset: 2px;
      }
      .solesta-mode-icon {
        color: #f18522;
        --mdc-icon-size: 17px;
      }
      .solesta-switch-track {
        position: relative;
        width: 32px;
        height: 18px;
        border-radius: 999px;
        background: #c9d1d5;
      }
      .solesta-switch-track i {
        position: absolute;
        top: 3px;
        left: 3px;
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #fff;
        box-shadow: 0 1px 4px rgba(0, 47, 60, .28);
        transition: transform .18s ease;
      }
      .solesta-chart-switch.is-week .solesta-switch-track i { transform: translateX(14px); }
      .solesta-chart-interaction {
        position: relative;
        display: block;
        width: 100%;
        height: 166px;
        overflow: hidden;
        border: 0;
        border-radius: 12px;
        padding: 0;
        background: #fbfcfe;
        cursor: crosshair;
        touch-action: pan-y;
        user-select: none;
        -webkit-tap-highlight-color: transparent;
      }
      .solesta-chart-interaction:focus-visible {
        outline: 2px solid #f18522;
        outline-offset: 2px;
      }
      .solesta-chart {
        display: block;
        width: 100%;
        height: 166px;
      }
      .solesta-chart-day { fill: rgba(241, 133, 34, .25); }
      .solesta-chart-day.alternate { fill: rgba(241, 133, 34, .34); }
      .solesta-chart-day.today { fill: rgba(241, 133, 34, .78); }
      .solesta-chart-grid {
        stroke: rgba(0, 59, 72, .13);
        stroke-width: 1;
        stroke-dasharray: 3 4;
      }
      .solesta-temperature-line {
        fill: none;
        stroke: #0c4757;
        stroke-width: 2.2;
        stroke-linecap: round;
        stroke-linejoin: round;
        vector-effect: non-scaling-stroke;
      }
      .solesta-temperature-point {
        fill: #f18522;
        stroke: #fff;
        stroke-width: 2;
        vector-effect: non-scaling-stroke;
      }
      .solesta-chart-cursor-line {
        stroke: #f18522;
        stroke-width: 1.5;
        vector-effect: non-scaling-stroke;
      }
      .solesta-chart-cursor-point {
        fill: #fff;
        stroke: #f18522;
        stroke-width: 2.5;
        vector-effect: non-scaling-stroke;
      }
      .solesta-chart-cursor-point[hidden] { display: none; }
      .solesta-chart-tooltip {
        position: absolute;
        z-index: 3;
        top: 5px;
        display: flex;
        min-width: 148px;
        max-width: 190px;
        flex-direction: column;
        gap: 2px;
        border: 1px solid rgba(255, 255, 255, .28);
        border-radius: 8px;
        padding: 5px 7px;
        color: #fff;
        background: rgba(0, 59, 72, .9);
        box-shadow: 0 5px 16px -8px rgba(0, 47, 60, .75);
        font-size: 9px;
        line-height: 1.25;
        opacity: 0;
        pointer-events: none;
        transform: translateX(7px);
        transition: opacity .12s ease, visibility .12s ease;
        visibility: hidden;
      }
      .solesta-chart-interaction:hover .solesta-chart-tooltip,
      .solesta-chart-interaction:focus .solesta-chart-tooltip {
        opacity: 1;
        visibility: visible;
      }
      .solesta-chart-tooltip.align-right { transform: translateX(calc(-100% - 7px)); }
      .solesta-chart-tooltip span { opacity: .82; }
      .solesta-chart-tooltip strong { font-size: 10px; }
      .solesta-chart-y-label,
      .solesta-chart-x-label,
      .solesta-chart-range-label,
      .solesta-chart-empty {
        fill: #6c7a82;
        font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
        font-size: 9px;
      }
      .solesta-chart-y-label {
        font-weight: 700;
        paint-order: stroke;
        stroke: rgba(255, 255, 255, .82);
        stroke-width: 3px;
        stroke-linejoin: round;
      }
      .solesta-chart-range-label {
        font-size: 8px;
        font-weight: 600;
      }
      .solesta-chart-range-label.maximum { fill: #13242b; }
      .solesta-chart-empty { font-size: 11px; }
      .solesta-health {
        display: flex;
        align-items: center;
        gap: 14px;
        border: 1px solid rgba(66, 201, 139, .25);
        border-radius: 40px;
        padding: 18px 20px;
        background: linear-gradient(135deg, rgba(66, 201, 139, .12), rgba(66, 201, 139, .04));
      }
      .solesta-health.offline,
      .solesta-health.attention {
        border-color: rgba(232, 54, 48, .25);
        background: rgba(232, 54, 48, .06);
      }
      .solesta-health.unknown {
        border-color: rgba(113, 128, 137, .25);
        background: rgba(113, 128, 137, .06);
      }
      .solesta-health-icon {
        display: grid;
        flex: 0 0 auto;
        place-items: center;
        width: 44px;
        height: 44px;
        border-radius: 12px;
        color: #42c98b;
        background: #fff;
      }
      .solesta-health.offline .solesta-health-icon,
      .solesta-health.attention .solesta-health-icon { color: #e83630; }
      .solesta-health.unknown .solesta-health-icon { color: #6c7a82; }
      .solesta-health-icon ha-icon { --mdc-icon-size: 26px; }
      .solesta-health-copy { min-width: 0; }
      .solesta-health-copy strong { display: block; color: #13242b; font-size: 14px; }
      .solesta-health-copy > span,
      .solesta-health-detail-row {
        display: block;
        margin-top: 3px;
        color: #6c7a82;
        font-size: 12px;
        line-height: 1.35;
      }
      .solesta-health-detail-row {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      .solesta-health-detail {
        width: fit-content;
        white-space: nowrap;
      }
      .solesta-status-info {
        position: relative;
        display: inline-flex;
        flex: 0 0 auto;
      }
      .solesta-status-info summary {
        display: grid;
        place-items: center;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        color: #039be5;
        cursor: pointer;
        list-style: none;
      }
      .solesta-status-info summary::-webkit-details-marker { display: none; }
      .solesta-status-info summary:focus-visible {
        outline: 2px solid #039be5;
        outline-offset: 2px;
      }
      .solesta-status-info summary ha-icon { --mdc-icon-size: 19px; }
      .solesta-status-info[open] summary { background: rgba(3, 155, 229, .12); }
      .solesta-status-info-text {
        position: absolute;
        z-index: 6;
        top: 30px;
        right: 0;
        width: min(300px, calc(100vw - 76px));
        box-sizing: border-box;
        border: 1px solid rgba(3, 155, 229, .25);
        border-radius: 10px;
        padding: 10px 12px;
        color: #31515f;
        background: #eef8fd;
        box-shadow: 0 8px 22px rgba(21, 42, 49, .16);
        font-size: 11px;
        line-height: 1.45;
        white-space: normal;
      }
      .solesta-health-copy > .solesta-health-entities {
        margin-top: 2px;
        font-size: 10px;
        overflow-wrap: anywhere;
      }
      .solesta-alerts {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }
      .solesta-alert {
        display: flex;
        align-items: center;
        gap: 12px;
        min-height: 52px;
        border: 1px solid rgba(247, 167, 11, .28);
        border-radius: 14px;
        padding: 9px 12px;
        background: rgba(247, 167, 11, .09);
      }
      .solesta-alert.error {
        border-color: rgba(232, 54, 48, .25);
        background: rgba(232, 54, 48, .08);
      }
      .solesta-alert.status {
        border-color: rgba(66, 201, 139, .28);
        background: rgba(66, 201, 139, .09);
      }
      .solesta-alert-icon {
        display: grid;
        flex: 0 0 auto;
        place-items: center;
        width: 34px;
        height: 34px;
        border-radius: 9px;
        color: #a96f00;
        background: rgba(247, 167, 11, .14);
      }
      .solesta-alert.error .solesta-alert-icon {
        color: #c8322d;
        background: rgba(232, 54, 48, .11);
      }
      .solesta-alert.status .solesta-alert-icon {
        color: #217a55;
        background: rgba(66, 201, 139, .14);
      }
      .solesta-alert-icon ha-icon { --mdc-icon-size: 19px; }
      .solesta-alert-message {
        min-width: 0;
        color: #8b5d00;
        font-size: 12px;
        font-weight: 600;
        line-height: 1.4;
      }
      .solesta-alert.error .solesta-alert-message { color: #b62d28; }
      .solesta-alert.status .solesta-alert-message { color: #217a55; }
      .solesta-footer {
        padding: 0 8px 4px;
        color: #6c7a82;
        font-size: 11px;
        line-height: 1.5;
        text-align: center;
      }
      @keyframes solesta-pulse { 0%, 100% { opacity: 1; } 50% { opacity: .3; } }
      @keyframes solesta-flow-vertical-up { to { background-position: 0 -20px; } }
      @keyframes solesta-flow-vertical-down { to { background-position: 0 20px; } }
      @keyframes solesta-flow-horizontal-left { to { background-position: -20px 0; } }
      @keyframes solesta-spin { to { transform: rotate(360deg); } }
      @media (max-width: 360px) {
        .solesta-hero { padding-inline: 18px; }
        .solesta-brand { gap: 6px; }
        .solesta-clock { min-width: 54px; font-size: 10px; }
        .solesta-close { width: 34px; }
        .solesta-content { padding-inline: 14px; }
        .solesta-panel { padding: 17px; }
        .solesta-status-grid { gap: 12px; }
      }
    `;
  }
}

class SolestaStatusCardEditor extends SolestaTranslatedElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._ensureTranslations(hass);
    this._render();
  }

  _render() {
    if (!this._config || !this._hass) return;
    const devices = solestaDevices(this._hass);
    const selected = this._config.device_id || "";
    const options = devices.map((device) =>
      `<option value="${escapeHtml(device.id)}"${device.id === selected ? " selected" : ""}>${escapeHtml(device.name)}</option>`);
    if (selected && !devices.some((device) => device.id === selected)) {
      options.unshift(`<option value="${escapeHtml(selected)}" selected>${escapeHtml(this._t("system_not_found"))}</option>`);
    }
    const signature = JSON.stringify([
      this._config, devices, this._translationLanguage,
      this._cardTranslations, Boolean(this._cardLocalize),
    ]);
    if (signature === this._renderSignature) return;
    this._renderSignature = signature;
    this.shadowRoot.innerHTML = `
      <style>
        :host{display:block;color:var(--primary-text-color);font:inherit}
        label{display:block;margin:16px 0 6px}
        select,input[type=text]{box-sizing:border-box;width:100%;padding:12px;
          border:1px solid var(--divider-color,#888);border-radius:6px;font:inherit;
          background:var(--card-background-color,#fff);color:inherit}
        p{color:var(--secondary-text-color);line-height:1.5}
        .check{display:flex;gap:10px;align-items:center}
      </style>
      <label for="system">${escapeHtml(this._t("editor_system"))}</label>
      <select id="system">
        <option value="">${escapeHtml(this._t("choose_system"))}</option>
        ${options.join("")}
      </select>
      <p>${escapeHtml(this._t(!devices.length ? "no_systems" : "editor_help"))}</p>
      <label for="name">${escapeHtml(this._t("editor_name"))}</label>
      <input id="name" type="text" value="${escapeHtml(this._config.system_name || "")}">
      <label for="close">${escapeHtml(this._t("editor_close_path"))}</label>
      <input id="close" type="text" value="${escapeHtml(this._config.close_path || "")}">
      <label class="check"><input id="fit" type="checkbox"${this._config.fit_to_viewport !== false ? " checked" : ""}>${escapeHtml(this._t("editor_fit"))}</label>
    `;
    this.shadowRoot.querySelector("#system").addEventListener("change", (event) => {
      const config = { ...this._config, device_id: event.target.value };
      this._change(config);
    });
    for (const [id, key] of [["name", "system_name"], ["close", "close_path"]]) {
      this.shadowRoot.querySelector(`#${id}`).addEventListener("change", (event) => {
        const config = { ...this._config };
        if (event.target.value.trim()) config[key] = event.target.value.trim();
        else delete config[key];
        this._change(config);
      });
    }
    this.shadowRoot.querySelector("#fit").addEventListener("change", (event) => {
      this._change({ ...this._config, fit_to_viewport: event.target.checked });
    });
  }

  _change(config) {
    this._config = config;
    this.dispatchEvent(new CustomEvent("config-changed", {
      detail: { config: { ...config, type: "custom:solesta-status-card" } },
      bubbles: true,
      composed: true,
    }));
    this._render();
  }
}

if (!customElements.get("solesta-status-card-editor")) {
  customElements.define("solesta-status-card-editor", SolestaStatusCardEditor);
}

if (!customElements.get("solesta-status-card")) {
  customElements.define("solesta-status-card", SolestaStatusCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "solesta-status-card",
    name: "Solesta system status",
    description: "Mobile system status card for Solesta.",
    preview: true,
  });
  console.info(`%c SOLESTA-STATUS-CARD %c v${SOLESTA_CARD_VERSION} `,
    "color:white;background:#002f3c;font-weight:700;",
    "color:#002f3c;background:#f18522;font-weight:700;",
  );
}
