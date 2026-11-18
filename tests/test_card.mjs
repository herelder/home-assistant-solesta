import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// Lightweight DOM doubles for configuration and events; these tests make no
// browser connection and deliberately do not claim to verify visual layout.
class Shadow {
  set innerHTML(value) { this.html = value; this.elements = new Map(); }
  get innerHTML() { return this.html; }
  querySelector(selector) {
    if (!this.elements.has(selector)) {
      this.elements.set(selector, { listeners: {}, addEventListener(type, fn) { this.listeners[type] = fn; } });
    }
    return this.elements.get(selector);
  }
  querySelectorAll() { return []; }
}
class Element extends EventTarget {
  isConnected = false;
  attachShadow() { this.shadowRoot = new Shadow(); return this.shadowRoot; }
}
const definitions = new Map();
const moduleSource = fs.readFileSync(new URL('../custom_components/solesta/frontend/solesta-status-card.js', import.meta.url), 'utf8');
const source = moduleSource.replace(
  'integrationDomainFromModuleUrl(import.meta.url)',
  "integrationDomainFromModuleUrl('http://homeassistant.local:8123/solesta/solesta-status-card.js?v=test')",
);
const context = vm.createContext({
  HTMLElement: Element, Event, CustomEvent, console: { info() {} },
  setTimeout, clearTimeout, URL, Intl, Date,
  window: { customCards: [], setTimeout, clearTimeout },
  document: { createElement: (tag) => new (definitions.get(tag))() },
  customElements: { get: (tag) => definitions.get(tag), define: (tag, value) => definitions.set(tag, value) },
});
vm.runInContext(source, context);
const Card = definitions.get('solesta-status-card');
const Editor = definitions.get('solesta-status-card-editor');
const parseAlerts = vm.runInContext('alertItems', context);
const domainFromUrl = vm.runInContext('integrationDomainFromModuleUrl', context);
const metadata = {
  tank_temperature: ['sensor', 'temp_tank_average'],
  collector_temperature: ['sensor', 'temp_collector'],
  tank_top_temperature: ['sensor', 'temp_tank_top'],
  tank_bottom_temperature: ['sensor', 'temp_tank_bottom'],
  energy_kwh: ['sensor', 'energy_tank_kwh'], energy_mj: ['sensor', 'energy_tank_mj'],
  showers: ['sensor', 'energy_tank_showers'], pump_active: ['binary_sensor', 'state_pump'],
  reporting: ['binary_sensor', 'status_reporting'], alerts: ['sensor', 'alerts_system'],
  report_delay: ['sensor', 'report_delay'], last_report: ['sensor', 'last_report'],
  cold_water_temperature: ['number', 'temp_coldwater'],
};
function makeHass(ids = ['boiler_a']) {
  const hass = {
    entities: {}, devices: {}, states: {}, locale: { language: 'en' },
    config: { time_zone: 'Europe/Amsterdam' },
  };
  for (const id of ids) {
    hass.devices[id] = { name: id, name_by_user: `My ${id}` };
    let index = 0;
    for (const [key, [domain, translation_key]] of Object.entries(metadata)) {
      const entity_id = `${domain}.${id}_renamed_${index++}`;
      hass.entities[entity_id] = { entity_id, device_id: id, platform: 'solesta', translation_key };
      hass.states[entity_id] = { entity_id, state: domain === 'binary_sensor' ? 'on' : '42', attributes: {} };
    }
  }
  return hass;
}
function card() { const c = new Card(); c._render = () => {}; return c; }
function renderCard(c) {
  c._setupChartInteraction = () => {};
  c._queueViewportFit = () => {};
  c._scheduleScrollRestore = () => {};
  Card.prototype._render.call(c);
  return c.shadowRoot.innerHTML;
}
const plain = (value) => JSON.parse(JSON.stringify(value));

test('picker selects the only boiler and does not guess between multiple boilers', () => {
  assert.equal(Card.getStubConfig(makeHass()).device_id, 'boiler_a');
  assert.equal(Card.getStubConfig(makeHass(['a', 'b'])).device_id, undefined);
  assert.equal(Card.getStubConfig({}).device_id, undefined);
  assert.ok(Card.getConfigElement() instanceof Editor);
});

test('integration domain comes from the module path in browsers and companion apps', () => {
  assert.equal(
    domainFromUrl('http://homeassistant.local:8123/solestanext/solesta-status-card.js?v=1'),
    'solestanext',
  );
  assert.equal(
    domainFromUrl('https://ha.example/solesta/solesta-status-card.js?v=0.2.5'),
    'solesta',
  );
  assert.throws(
    () => domainFromUrl('http://homeassistant.local:8123/solesta-status-card.js'),
    /cannot be determined/,
  );
});

test('production and lab bundles register independent custom-card elements', () => {
  const dualDefinitions = new Map();
  const dualContext = vm.createContext({
    HTMLElement: Element, Event, CustomEvent, console: { info() {} },
    setTimeout, clearTimeout, URL, Intl, Date,
    window: { customCards: [], setTimeout, clearTimeout },
    document: { createElement: (tag) => new (dualDefinitions.get(tag))() },
    customElements: {
      get: (tag) => dualDefinitions.get(tag),
      define: (tag, value) => dualDefinitions.set(tag, value),
    },
  });
  const evaluateBundle = (domain) => {
    const bundled = moduleSource.replace(
      'integrationDomainFromModuleUrl(import.meta.url)',
      `integrationDomainFromModuleUrl('http://homeassistant.local:8123/${domain}/solesta-status-card.js?v=test')`,
    );
    vm.runInContext(`(() => {${bundled}\n})()`, dualContext);
  };

  evaluateBundle('solesta');
  evaluateBundle('solesta_lab');

  assert.ok(dualDefinitions.has('solesta-status-card'));
  assert.ok(dualDefinitions.has('solesta-status-card-editor'));
  assert.ok(dualDefinitions.has('solesta-lab-status-card'));
  assert.ok(dualDefinitions.has('solesta-lab-status-card-editor'));
  assert.deepEqual(
    [...dualContext.window.customCards].map((item) => item.type),
    ['solesta-status-card', 'solesta-lab-status-card'],
  );
  for (const cardMetadata of dualContext.window.customCards) {
    assert.equal(cardMetadata.name, 'Solar boiler system status');
    assert.doesNotMatch(`${cardMetadata.name} ${cardMetadata.description}`, /Solesta/);
  }
});

test('device mapping finds arbitrary renamed entity IDs and isolates boilers', () => {
  const hass = makeHass(['a', 'b']);
  const c = card(); c.setConfig({device_id: 'b'}); c.hass = hass;
  assert.equal(c._configIssue, null);
  assert.equal(c._config.system_name, 'My b');
  assert.equal(Object.keys(c._config.entities).length, 13);
  for (const id of Object.values(c._config.entities)) assert.match(id, /\.b_renamed_/);
  assert.equal(c._entity('tank_temperature').state, '42');
});

test('unnamed cards follow provider identity and every explicit name stays fixed', () => {
  const hass = makeHass();
  const reporting = Object.values(hass.entities)
    .find((entry) => entry.translation_key === 'status_reporting').entity_id;
  hass.states[reporting].attributes = {
    provider_protocol: 'web_api',
    provider_id: 'provider_a',
    system_id: 'system_a',
  };
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  assert.equal(c._config.system_name, 'provider_a/system_a');

  hass.states[reporting] = {
    ...hass.states[reporting],
    attributes: {
      provider_protocol: 'esphome_native',
      provider_id: 'provider_b',
      system_id: 'system_a',
    },
  };
  c.hass = {...hass};
  assert.equal(c._config.system_name, 'provider_b/system_a');
  c._setupChartInteraction = () => {};
  c._queueViewportFit = () => {};
  c._scheduleScrollRestore = () => {};
  c._render = Card.prototype._render.bind(c);
  c._render();
  assert.match(
    c.shadowRoot.innerHTML,
    /<div class="solesta-hero-system-name">provider_b\/system_a<\/div>/,
  );
  assert.match(
    c.shadowRoot.innerHTML,
    /<footer class="solesta-footer">\s*<span class="solesta-footer-system">provider_b\/system_a<\/span>\s*<span data-system-report>/,
  );

  for (const name of ['Zolderboiler', 'Web API', 'ESPHome Native']) {
    const custom = card();
    custom.setConfig({device_id: 'boiler_a', system_name: name});
    custom.hass = hass;
    assert.equal(custom._config.system_name, name);
  }
});

test('dashboard identity is selected through the reporting role', () => {
  const hass = makeHass();
  const reporting = Object.values(hass.entities)
    .find((entry) => entry.translation_key === 'status_reporting').entity_id;
  const tank = Object.values(hass.entities)
    .find((entry) => entry.translation_key === 'temp_tank_average').entity_id;
  hass.states[reporting].attributes = {
    provider_id: 'reporting_provider',
    system_id: 'reporting_system',
  };
  hass.states[tank].attributes = {
    provider_id: 'other_provider',
    system_id: 'other_system',
  };

  const c = card();
  c.setConfig({device_id: 'boiler_a'});
  c.hass = hass;
  assert.equal(c._config.system_name, 'reporting_provider/reporting_system');
});

test('same metadata from the predecessor integration cannot be mixed in', () => {
  const hass = makeHass();
  const entry = Object.values(hass.entities).find((e) => e.translation_key === 'temp_tank_average');
  entry.platform = 'solestanext';
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  assert.equal(c._configIssue, 'missing_entities');
  assert.equal(c._config.entities.tank_temperature, undefined);
});

test('removed, disabled and ambiguous required entities yield a clear configuration state', () => {
  for (const mode of ['removed', 'disabled', 'ambiguous']) {
    const hass = makeHass();
    const entry = Object.values(hass.entities).find((e) => e.translation_key === 'temp_tank_average');
    if (mode === 'removed') delete hass.entities[entry.entity_id];
    if (mode === 'disabled') entry.disabled_by = 'user';
    if (mode === 'ambiguous') hass.entities['sensor.duplicate'] = { ...entry, entity_id: 'sensor.duplicate' };
    const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
    assert.equal(c._configIssue, 'missing_entities', mode);
  }
});

test('a removed selected device is not silently replaced with another boiler', () => {
  const c = card(); c.setConfig({device_id: 'gone'}); c.hass = makeHass();
  assert.equal(c._configIssue, 'system_not_found');
  assert.equal(c._config.entities.tank_temperature, undefined);
});

test('historical explicit entity mappings are no longer accepted', () => {
  assert.throws(
    () => card().setConfig({entities: {tank_temperature: 'sensor.other'}}),
    /choose a solar boiler by device_id/,
  );
});

test('ordinary state updates preserve history while registry renames remap the card', () => {
  const hass = makeHass(); const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  c._history = [{time: 1, value: 20}]; c._chartMode = 'week';
  c.hass = {...hass, states: {...hass.states}};
  assert.equal(c._history.length, 1); assert.equal(c._chartMode, 'week');
  const oldId = c._config.entities.tank_temperature;
  const entities = {...hass.entities, 'sensor.renamed_again': {...hass.entities[oldId], entity_id: 'sensor.renamed_again'}};
  delete entities[oldId];
  c.hass = {...hass, entities};
  assert.equal(c._config.entities.tank_temperature, 'sensor.renamed_again');
  assert.equal(c._history.length, 0);
});

test('new registry and device objects preserve history when their effective mapping is unchanged', () => {
  const hass = makeHass(); const c = card();
  c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  c._history = [{time: 1, value: 20}]; c._chartMode = 'week'; c._chartCursorTime = 1;
  c.hass = {...hass, entities: {...hass.entities}, devices: {...hass.devices}};
  assert.deepEqual(plain(c._history), [{time: 1, value: 20}]);
  assert.equal(c._chartMode, 'week');
  assert.equal(c._chartCursorTime, 1);
});

test('an old in-flight history response cannot overwrite the newly selected boiler', async () => {
  const hass = makeHass(['a', 'b']); const pending = [];
  hass.callApi = (_method, path) => new Promise((resolve) => pending.push({path, resolve}));
  const c = card(); c.setConfig({device_id: 'a'}); c.hass = hass;
  const first = c._loadHistory();
  c.setConfig({device_id: 'b'}); const second = c._loadHistory();
  assert.match(pending[0].path, /sensor.a_renamed_0/);
  assert.match(pending[1].path, /sensor.b_renamed_0/);
  pending[1].resolve([[{state:'60', last_changed:'2026-09-04T10:00:00Z'}]]); await second;
  pending[0].resolve([[{state:'10', last_changed:'2026-09-04T10:00:00Z'}]]); await first;
  assert.equal(c._history[0].value, 60);
});

test('editor selection preserves unrelated dashboard settings', () => {
  const e = new Editor();
  e.setConfig({fit_to_viewport: false, close_path: '/lovelace',
    grid_options: {columns: 'full'}});
  e.hass = makeHass(['a', 'b']);
  let received; e.addEventListener('config-changed', (event) => { received = event.detail.config; });
  e.shadowRoot.querySelector('#system').listeners.change({target:{value:'b'}});
  assert.equal(received.device_id, 'b');
  assert.equal(received.fit_to_viewport, false); assert.equal(received.close_path, '/lovelace');
  assert.equal(received.grid_options.columns, 'full');
  assert.equal(received.type, 'custom:solesta-status-card');
});

test('card and editor use the same Dutch HA translations', async () => {
  const nl = JSON.parse(fs.readFileSync(new URL('../custom_components/solesta/translations/nl.json', import.meta.url))).common;
  const resources = Object.fromEntries(Object.entries(nl).map(([key, value]) => [`component.solesta.common.${key}`, value]));
  const hass = {...makeHass(), locale:{language:'nl'}, callWS: async (message) => {
    assert.equal(message.type, 'frontend/get_translations'); assert.equal(message.language, 'nl');
    return {resources};
  }};
  const c = card(); c.setConfig({device_id:'boiler_a'}); c.hass = hass;
  const e = new Editor(); e.setConfig({device_id:'boiler_a'}); e.hass = hass;
  await Promise.all([c._translationRequest, e._translationRequest]);
  assert.equal(c._t('editor_system'), 'Zonneboiler');
  assert.equal(e._t('editor_system'), 'Zonneboiler');
  assert.match(e.shadowRoot.innerHTML, /Zonneboiler/);
});

test('warmte-indicatie follows the relative Dutch thresholds and text', () => {
  const common = JSON.parse(fs.readFileSync(
    new URL('../custom_components/solesta/translations/nl.json', import.meta.url),
  )).common;
  const c = card();
  c._cardTranslations = Object.fromEntries(Object.entries(common).map(
    ([key, value]) => [`component.solesta.common.${key}`, value],
  ));
  assert.equal(c._warmthIndicator(16.9, 12), 'slight');
  assert.equal(c._warmthIndicator(17, 12), '');
  assert.equal(c._warmthIndicator(26.9, 12), '');
  assert.equal(c._warmthIndicator(27, 12), 'strong');
  assert.equal(c._warmthIndicator(40, 30), '');
  assert.equal(c._preheatedWaterText(16.9, 12), 'Het systeem levert enigszins voorverwarmd water');
  assert.equal(c._preheatedWaterText(17, 12), 'Het systeem levert voorverwarmd water');
  assert.equal(c._preheatedWaterText(27, 12), 'Het systeem levert sterk voorverwarmd water');
  assert.equal(common.dashboard_warmth_slight[0], 'e');
  assert.equal(common.dashboard_warmth_strong[0], 's');
  assert.equal(c._t('tank_temperature_is'), 'De temperatuur in je zonneboiler is:');
  assert.equal(c._t('contact_support'), 'Controleer uw systeem en verbinding');
  assert.equal(common.dashboard_loading, 'Systeemgegevens worden geladen…');
  assert.doesNotMatch(common.dashboard_missing_entities, /Solesta/);
  assert.doesNotMatch(common.dashboard_no_systems, /Solesta/);
});

test('rendered Dutch hero and tappable status information use the approved wording', () => {
  const common = JSON.parse(fs.readFileSync(
    new URL('../custom_components/solesta/translations/nl.json', import.meta.url),
  )).common;
  const hass = makeHass();
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  hass.states[c._config.entities.cold_water_temperature].state = '12';
  c._cardTranslations = Object.fromEntries(Object.entries(common).map(
    ([key, value]) => [`component.solesta.common.${key}`, value],
  ));
  c._setupChartInteraction = () => {};
  c._queueViewportFit = () => {};
  c._scheduleScrollRestore = () => {};
  c._render = Card.prototype._render.bind(c);
  c._render();
  assert.match(c.shadowRoot.innerHTML, /De temperatuur in je zonneboiler is:/);
  assert.match(c.shadowRoot.innerHTML, /Het systeem levert sterk voorverwarmd water/);
  assert.match(c.shadowRoot.innerHTML, /solesta-community-logo\.png\?v=1\.0\.0/);
  assert.match(c.shadowRoot.innerHTML, /<span class="solesta-brand-name">Zonneboiler<\/span>/);
  assert.match(c.shadowRoot.innerHTML, /<div class="solesta-hero-system-name">My boiler_a<\/div>/);
  assert.match(c.shadowRoot.innerHTML, /solesta-tank-bottom-temp">42[,.]0°/);
  assert.match(c.shadowRoot.innerHTML, /<div class="solesta-tank"[^>]*><span>boilervat<\/span>/);
  assert.match(c.shadowRoot.innerHTML, /\.solesta-content \{[\s\S]*?margin-top: 0;[\s\S]*?padding: 16px 20px 24px;/);
  assert.match(c.shadowRoot.innerHTML, /\.solesta-tank span \{[\s\S]*?color: #002f3c;[\s\S]*?background: rgba\(255, 255, 255, \.68\);[\s\S]*?font-size: 8px;[\s\S]*?font-weight: 400;[\s\S]*?text-transform: uppercase;/);
  assert.match(c.shadowRoot.innerHTML, /\.solesta-tank-bottom-temp \{ top: 130px;/);
  assert.match(c.shadowRoot.innerHTML, />Circulatie</);
  assert.match(c.shadowRoot.innerHTML, /<details class="solesta-status-info">/);
  assert.match(c.shadowRoot.innerHTML, /<div class="solesta-health-title-row">\s*<span class="solesta-health-icon">[\s\S]*?<strong>Alles werkt normaal<\/strong>\s*<\/div>/);
  assert.match(c.shadowRoot.innerHTML, /\.solesta-health \{\s*display: block;/);
  assert.match(c.shadowRoot.innerHTML, /\.solesta-health-title-row \{[\s\S]*?display: flex;[\s\S]*?align-items: center;/);
  assert.match(c.shadowRoot.innerHTML, /\.solesta-health-detail \{[\s\S]*?min-width: 0;[\s\S]*?white-space: normal;/);
  assert.match(c.shadowRoot.innerHTML, /<footer class="solesta-footer">\s*<span class="solesta-footer-system">My boiler_a<\/span>\s*<span data-system-report>Laatste systeemrapportage/);
  assert.match(c.shadowRoot.innerHTML, /\.solesta-footer \{[\s\S]*?display: flex;[\s\S]*?flex-direction: column;[\s\S]*?text-align: center;/);
  assert.match(c.shadowRoot.innerHTML, /aria-label="Meer informatie over statuswijzigingen"/);
  assert.match(c.shadowRoot.innerHTML, /icon="mdi:information-outline"/);
  assert.match(c.shadowRoot.innerHTML, /Een statuswijziging is een verandering van de waarde van een component van de zonneboiler, een afgeleide waarde of de communicatieverbinding\. Statuswijzigingen zijn heel normaal in uw zonneboiler\./);
  assert.doesNotMatch(c.shadowRoot.innerHTML, /cursor: help/);

  hass.states[c._config.entities.reporting].state = 'off';
  c._render();
  assert.match(c.shadowRoot.innerHTML, /Controleer uw systeem en verbinding/);
});

test('raw and overflow alert lines drive green operating messages and red real alerts', () => {
  const lines = [
    JSON.stringify({type: 'collector_hot', message: 'Temperatuur collector te hoog', severity: 'warning'}),
    JSON.stringify({type: 'pump_idle', message: 'Collector warm maar pomp uit', severity: 'warning'}),
    JSON.stringify({type: 'sensor_fault', message: 'Temperatuursensor defect', severity: 'error'}),
  ];
  const state = {state: `${lines.join('\n').slice(0, 254)}…`, attributes: {
    lines, truncated: true,
  }};
  const alerts = parseAlerts(state);
  assert.equal(alerts.length, 3);
  const html = card()._alertsMarkup(alerts);
  assert.match(html, /solesta-alert status[\s\S]*Temperatuur collector te hoog/);
  assert.match(html, /solesta-alert status[\s\S]*Collector warm maar pomp uit/);
  assert.match(html, /solesta-alert error[\s\S]*Temperatuursensor defect/);
  const c = card(); c._statusChangeTime = Date.parse('2026-09-04T12:00:00Z');
  assert.equal(c._health(true, alerts.slice(0, 2), true).tone, 'normal');
  assert.equal(c._health(true, alerts, true).tone, 'attention');
  assert.equal(c._health(true, [], false).tone, 'unknown');
  assert.equal(c._health(null, [], true).tone, 'unknown');
  assert.equal(c._health(false, [], true).tone, 'offline');
  assert.equal(parseAlerts({state: '', attributes: {}}).length, 0);
  assert.equal(parseAlerts({state: 'unavailable', attributes: {}}), null);
  assert.equal(parseAlerts({state: lines[0], attributes: {}})[0].type, 'collector_hot');
});

test('local alert records use Home Assistant translations and placeholders', () => {
  const state = {state: JSON.stringify({
    type: 'collector_hot',
    translation_key: 'alert_collector_hot',
    translation_placeholders: {temperature: '95'},
    severity: 'warning',
  }), attributes: {}};
  const alerts = parseAlerts(state);
  assert.equal(alerts[0].message, '');
  assert.equal(alerts[0].translationKey, 'alert_collector_hot');
  assert.deepEqual(plain(alerts[0].translationPlaceholders), {temperature: '95'});

  for (const [language, expected] of [
    ['en', 'Collector 95° – too high'],
    ['nl', 'Collector 95° – te hoog'],
  ]) {
    const common = JSON.parse(fs.readFileSync(
      new URL(`../custom_components/solesta/translations/${language}.json`, import.meta.url),
    )).common;
    const c = card();
    c._cardTranslations = Object.fromEntries(Object.entries(common).map(
      ([key, value]) => [`component.solesta.common.${key}`, value],
    ));
    assert.ok(c._alertsMarkup(alerts).includes(expected));
  }
});

test('record-separated alerts preserve a newline inside message text', () => {
  const first = JSON.stringify({
    type: 'note', message: 'Eerste regel\nTweede regel', severity: 'info',
  });
  const second = JSON.stringify({
    type: 'collector_hot', message: 'Collector warm', severity: 'warning',
  });
  const alerts = parseAlerts({state: `${first}\x1e${second}`, attributes: {}});
  assert.equal(alerts.length, 2);
  assert.equal(alerts[0].message, 'Eerste regel\nTweede regel');
  assert.equal(alerts[1].type, 'collector_hot');
});

test('long single JSON alerts preserve Unicode separators and error severity', () => {
  for (const separator of ['\u2028', '\u2029', '\u0085']) {
    const alert = {type: 'sensor_fault', message: 'x'.repeat(260) + separator + 'tail', severity: 'error'};
    const raw = JSON.stringify(alert);
    const [parsed] = parseAlerts({state: raw.slice(0, 254) + '…', attributes: {truncated: true, lines: [raw]}});
    assert.equal(parsed.type, alert.type);
    assert.equal(parsed.message, alert.message);
    assert.equal(parsed.severity, alert.severity);
  }
  for (const separator of ['\r', '\r\n', '\n']) {
    const raw = [
      JSON.stringify({type: 'first', message: 'one'}),
      JSON.stringify({type: 'second', message: 'two'}),
    ].join(separator);
    assert.equal(parseAlerts({state: raw}).length, 2);
  }
});

test('universal danger and active-pump alerts use their severity and type', () => {
  const alerts = parseAlerts({state: [
    JSON.stringify({
      type: 'collector_hot', message: 'Collector gevaarlijk heet', severity: 'danger',
    }),
    JSON.stringify({
      type: 'pump_active', message: 'Pomp draait bij koude collector', severity: 'info',
    }),
  ].join('\x1e'), attributes: {}});
  const html = card()._alertsMarkup(alerts);
  assert.match(html, /solesta-alert error[\s\S]*Collector gevaarlijk heet/);
  assert.match(html, /solesta-alert status[\s\S]*Pomp draait bij koude collector/);
});

test('calendar dates and day boundaries use the Home Assistant timezone across DST', () => {
  const c = card(); c._hass = makeHass();
  assert.equal(c._parseDate('04-09-2026 21:00:00').toISOString(), '2026-09-04T19:00:00.000Z');

  const springStart = c._startOfDay(new Date('2026-03-29T12:00:00Z'));
  const springNext = c._addCalendarDays(springStart, 1);
  assert.equal(springStart.toISOString(), '2026-03-28T23:00:00.000Z');
  assert.equal(springNext.toISOString(), '2026-03-29T22:00:00.000Z');
  assert.equal(springNext - springStart, 23 * 60 * 60 * 1000);

  const autumnStart = c._startOfDay(new Date('2026-10-25T12:00:00Z'));
  const autumnNext = c._addCalendarDays(autumnStart, 1);
  assert.equal(autumnStart.toISOString(), '2026-10-24T22:00:00.000Z');
  assert.equal(autumnNext.toISOString(), '2026-10-25T23:00:00.000Z');
  assert.equal(autumnNext - autumnStart, 25 * 60 * 60 * 1000);
});

test('skipped and repeated local midnights use the first valid instant of the day', () => {
  const hass = makeHass();
  hass.locale.language = 'en-GB';
  hass.config.time_zone = 'America/Santiago';
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  const before = new Date('2026-09-05T04:00:00Z');
  const transition = c._addCalendarDays(before, 1);
  assert.equal(transition?.toISOString(), '2026-09-06T04:00:00.000Z');
  assert.equal(c._shortTime(transition), '01:00');
  assert.equal(c._startOfDay(new Date('2026-09-06T12:00:00Z')).getTime(), transition.getTime());
  assert.equal(c._addCalendarDays(transition, 1) - transition, 23 * 60 * 60 * 1000);
  // Parsing a timestamp still requires an existing local wall-clock time.
  assert.equal(c._parseDate('06-09-2026 00:00:00'), null);
  for (const [mode, now] of [
    ['week', '2026-09-07T12:00:00Z'],
    ['today', '2026-09-05T12:00:00Z'],
    ['today', '2026-09-06T12:00:00Z'],
  ]) {
    c._chartMode = mode; c._now = () => new Date(now);
    assert.match(renderCard(c), /class="solesta-chart"/);
    assert.ok(c._chartModel.days.every((day) => day.endTime > day.startTime));
    if (now.startsWith('2026-09-06')) {
      assert.match(c._historyMarkup(), /text-anchor="start">01:00<\/text>/);
    }
  }
  hass.config.time_zone = 'America/Havana';
  const repeated = c._startOfDay(new Date('2026-11-01T12:00:00Z'));
  assert.equal(repeated.toISOString(), '2026-11-01T04:00:00.000Z');
  assert.equal(c._addCalendarDays(repeated, 1) - repeated, 25 * 60 * 60 * 1000);
  hass.config.time_zone = 'America/Goose_Bay';
  assert.equal(c._startOfDay(new Date('2009-11-01T12:00:00Z')).toISOString(), '2009-11-01T03:00:00.000Z');
});

test('an unresolvable calendar boundary only replaces the chart and clears its cursor model', () => {
  const hass = makeHass();
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  c._now = () => new Date('2026-09-07T12:00:00Z');
  c._historyMarkup();
  assert.ok(c._chartModel);
  c._addCalendarDays = () => null;
  for (const mode of ['today', 'week']) {
    c._chartMode = mode;
    const html = renderCard(c);
    assert.match(html, /Temperature history is temporarily unavailable/);
    assert.match(html, /class="solesta-energy"/);
    assert.equal(c._chartModel, null);
  }
  delete c._addCalendarDays;
  hass.config.time_zone = 'Pacific/Apia';
  c._now = () => new Date('2011-12-31T00:00:00Z');
  assert.equal(c._addCalendarDays(new Date('2011-12-29T10:00:00Z'), 1), null);
  assert.match(renderCard(c), /Temperature history is temporarily unavailable/);
  assert.equal(c._chartModel, null);
});

test('history uses last-known values, time-weighted averages and explicit gap breaks', () => {
  const c = card();
  const hour = 60 * 60 * 1000;
  assert.equal(c._temperatureAt([{time: 0, value: 20}, {time: 6 * hour, value: 80}], 3 * hour), 20);
  assert.equal(c._temperatureAt([{time: hour, value: 20}], 0), null);
  const average = c._timeWeightedAverage(
    [{time: 0, value: 20}, {time: 13 * hour, value: 80}, {time: 14 * hour, value: 80}],
    0,
    14 * hour,
  );
  assert.ok(Math.abs(average - 24.2857142857) < 1e-9);
  assert.deepEqual(
    plain(c._temperatureRange(
      [{time: 0, value: 20}, {time: 6 * hour, value: 80}, {time: 8 * hour, value: null}],
      0,
      10 * hour,
    )),
    {minimum: 20, maximum: 80},
  );
  assert.deepEqual(
    plain(c._chartTemperatureScale([{time: 0, value: 20}, {time: hour, value: 40}])),
    {minimum: 17, maximum: 43},
  );
  assert.deepEqual(
    plain(c._chartTemperatureScale([{time: 0, value: 29}])),
    {minimum: 27, maximum: 31},
  );
  const path = c._chartPath(
    [{time: 0, value: 20}, {time: hour, value: null}, {time: 2 * hour, value: 30}],
    (time) => time / hour,
    (value) => 100 - value,
  );
  assert.equal((path.match(/M/g) || []).length, 2);
});

test('week overview positions rounded day blocks between minima and maxima and keeps the line', () => {
  const hass = makeHass();
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  hass.states[c._config.entities.tank_temperature].state = '40';
  c._chartMode = 'week';
  c._now = () => new Date('2026-09-12T12:00:00Z');
  c._history = [
    {time: Date.parse('2026-09-06T00:00:00Z'), value: 20},
    {time: Date.parse('2026-09-06T12:00:00Z'), value: 40},
    {time: Date.parse('2026-09-07T12:00:00Z'), value: 30},
  ];
  const html = c._historyMarkup();
  assert.match(html, /class="solesta-chart-day[^"]*"[^>]+rx="/);
  assert.match(html, /class="solesta-chart-range-label maximum"[^>]*>40°<\/text>/);
  assert.match(html, /class="solesta-chart-range-label minimum"[^>]*>20°<\/text>/);
  assert.match(html, /<path class="solesta-temperature-line"/);
  assert.match(html, /Tank temperature this week/);
  assert.match(html, /lowest - average - highest per day/);
  assert.equal(c._chartModel.yFor(43), c._chartModel.chartTop);
  assert.equal(c._chartModel.yFor(17), c._chartModel.chartBottom);
});

test('today overview uses a full-width rounded range with max above and min below', () => {
  const hass = makeHass();
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  c._chartMode = 'today';
  c._now = () => new Date('2026-09-12T12:00:00Z');
  c._history = [
    {time: Date.parse('2026-09-11T22:00:00Z'), value: 28},
    {time: Date.parse('2026-09-12T08:00:00Z'), value: 32},
  ];
  const html = c._historyMarkup();
  assert.match(html, /Tank temperature today/);
  assert.match(html, /lowest - average - highest/);
  assert.match(html, /class="solesta-chart-day today"[^>]+x="0\.0"[^>]+width="360\.0"[^>]+rx="180\.0"/);
  assert.match(html, /class="solesta-chart-range-label maximum"[^>]*>42\.0°<\/text>/);
  assert.match(html, /class="solesta-chart-range-label minimum"[^>]*>28\.0°<\/text>/);
  assert.match(html, /<path class="solesta-temperature-line"/);
  assert.match(source, /\.solesta-temperature-line \{[\s\S]*?stroke-width: 2\.2;/);
});

test('only drawing geometry is reduced while full history retains every state change', () => {
  const c = card();
  const states = Array.from({length: 2000}, (_, index) => ({
    s: index === 1000 ? 'unavailable' : index === 555 ? '-20' : index === 1500 ? '120' : String(20 + index % 5),
    lu: 1_700_000_000 + index * 60,
  }));
  const history = c._temperatureHistory(states);
  assert.equal(history.length, states.length);
  const sampled = c._chartHistory(history);
  assert.ok(sampled.length <= 720);
  assert.equal(sampled[0].time, 1_700_000_000_000);
  assert.equal(sampled.at(-1).time, (1_700_000_000 + 1999 * 60) * 1000);
  assert.ok(sampled.some((point) => point.value === -20));
  assert.ok(sampled.some((point) => point.value === 120));
  assert.ok(sampled.some((point) => point.value === null));
  for (const index of [999, 1000, 1001, 556, 1501]) {
    assert.ok(sampled.some((point) => point.time === history[index].time));
  }
  // Dense outages may exceed the geometry budget; none may be bridged.
  const gaps = Array.from({length: 1600}, (_, index) => ({time: index, value: index % 2 ? null : 20}));
  assert.equal(c._chartHistory(gaps).length, gaps.length);
  assert.equal((c._chartPath(gaps, (time) => time, (value) => value).match(/M/g) || []).length, 800);
});

test('dense history with short peaks keeps exact daily averages and cursor values', async () => {
  const minute = 60 * 1000;
  const start = Date.parse('2026-09-01T00:00:00Z');
  const states = Array.from({length: 7141}, (_, index) => ({
    s: String(index % 60 === 1 ? 80 : index % 60 < 3 ? 20 : 50 + (index % 2) / 10),
    lu: (start + index * minute) / 1000,
  }));
  const hass = makeHass(); hass.config.time_zone = 'UTC';
  hass.callApi = async () => [states];
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  c._chartMode = 'week'; c._now = () => new Date(start + 7140 * minute);
  hass.states[c._config.entities.tank_temperature].state = states.at(-1).s;
  await c._loadHistory();
  assert.ok(c._history.length > 720);
  c._historyMarkup();
  const expected = (20 * 2 + 80 + 50 * 28 + 50.1 * 29) / 60;
  assert.ok(Math.abs(c._timeWeightedAverage(c._history, start, start + 7140 * minute) - expected) < 1e-9);
  const completeDays = c._chartModel.days.filter((day) => day.endTime - day.startTime === 1440 * minute
    && day.startTime >= start);
  assert.equal(completeDays.length, 4);
  for (const day of completeDays) {
    assert.ok(Math.abs(day.average - expected) < 1e-9);
    assert.equal(day.minimum, 20); assert.equal(day.maximum, 80);
  }
  assert.match(c._chartCursorData(start + 3.5 * minute).momentText, /50\.1 °C/);
  assert.match(c._chartCursorData(start + 1.5 * minute).momentText, /80\.0 °C/);
});

test('dense history retains multiple short gaps and exact ranges across a day boundary', () => {
  const minute = 60 * 1000;
  const start = Date.parse('2026-09-01T00:00:00Z');
  const values = Array.from({length: 2881}, (_, index) => 20 + index % 2);
  values[1439] = 80;
  for (const index of [1440, 1441, 1443, 1444, 1446, 1447, 1448, 1449]) values[index] = null;
  const hass = makeHass(); hass.config.time_zone = 'UTC';
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  c._chartMode = 'week'; c._now = () => new Date(start + 2880 * minute);
  hass.states[c._config.entities.tank_temperature].state = String(values.at(-1));
  c._history = c._temperatureHistory(values.map((value, index) => ({
    s: value === null ? 'unavailable' : String(value), lu: (start + index * minute) / 1000,
  })));
  const html = c._historyMarkup();
  for (const index of [1440, 1441, 1443, 1444, 1446, 1448]) {
    assert.equal(c._temperatureAt(c._chartModel.points, start + (index + .5) * minute), null);
    assert.equal(c._chartCursorData(start + (index + .5) * minute).y, null);
  }
  const day = c._chartModel.days.find((candidate) => candidate.startTime === start);
  const expected = values.slice(0, 1440).reduce((sum, value) => sum + value, 0) / 1440;
  assert.ok(Math.abs(day.average - expected) < 1e-9);
  assert.equal(day.minimum, 20); assert.equal(day.maximum, 80);
  const nextDay = c._chartModel.days.find((candidate) => candidate.startTime === start + 1440 * minute);
  const known = values.slice(1440, 2880).filter((value) => value !== null);
  assert.ok(Math.abs(nextDay.average - known.reduce((sum, value) => sum + value, 0) / known.length) < 1e-9);
  assert.equal(nextDay.minimum, 20); assert.equal(nextDay.maximum, 21);
  const line = html.match(/<path class="solesta-temperature-line" d="([^"]+)"/)[1];
  assert.equal((line.match(/M/g) || []).length, 4);
});

test('missing required measurements make rendered health incomplete and preserve alert priorities', () => {
  const hass = makeHass();
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  const states = hass.states; const ids = c._config.entities;
  states[ids.alerts].state = '';
  assert.match(renderCard(c), /class="solesta-health normal"/);
  for (const key of [
    'tank_temperature', 'collector_temperature', 'tank_top_temperature', 'tank_bottom_temperature',
    'energy_kwh', 'energy_mj', 'showers', 'cold_water_temperature', 'pump_active',
  ]) {
    const original = states[ids[key]];
    for (const value of ['unknown', 'unavailable', 'invalid', null]) {
      if (value === null) delete states[ids[key]];
      else states[ids[key]] = {...original, state: value};
      const html = renderCard(c);
      assert.match(html, /class="solesta-health unknown"/, `${key}: ${value}`);
      assert.doesNotMatch(html, /Everything is working normally/);
    }
    states[ids[key]] = original;
    assert.match(renderCard(c), /class="solesta-health normal"/);
  }
  states[ids.collector_temperature].state = 'unavailable';
  states[ids.alerts].state = JSON.stringify({type: 'fault', severity: 'danger', message: 'Independent fault'});
  assert.match(renderCard(c), /class="solesta-health attention"/);
  states[ids.reporting].state = 'off';
  assert.match(renderCard(c), /class="solesta-health offline"/);
});

test('irrelevant Home Assistant updates do not rerender the full card', () => {
  const hass = makeHass(); const c = new Card();
  c._ensureTranslations = () => {};
  let renders = 0; c._render = () => { renders += 1; };
  c.setConfig({device_id: 'boiler_a'}); c.hass = hass; renders = 0;
  for (let index = 0; index < 100; index += 1) {
    c.hass = {
      ...hass,
      entities: {...hass.entities},
      devices: {...hass.devices},
      states: {...hass.states, 'sensor.unrelated': {state: String(index)}},
    };
  }
  assert.equal(renders, 0);
});

test('a failed history refresh preserves good data and uses bounded retry state', async () => {
  const hass = makeHass();
  hass.callApi = async () => { throw new Error('temporary failure'); };
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  c._history = [{time: 1, value: 20}];
  await c._loadHistory();
  assert.deepEqual(plain(c._history), [{time: 1, value: 20}]);
  assert.equal(c._historyError, true);
  assert.ok(c._historyRetryAt > Date.now());
  assert.equal(c._historyRetryDelay, 60 * 1000);

  hass.callApi = async () => [[{state: '42', last_changed: '2026-09-04T10:00:00Z'}]];
  await c._loadHistory();
  assert.equal(c._historyError, false);
  assert.equal(c._history[0].value, 42);
  assert.equal(c._historyRetryDelay, 30 * 1000);
});

test('translation failure fallback does not retry on every Home Assistant update', async () => {
  const hass = makeHass(); let calls = 0;
  hass.callWS = async () => { calls += 1; throw new Error('temporary failure'); };
  const c = card();
  c._ensureTranslations(hass); await c._translationRequest;
  for (let index = 0; index < 100; index += 1) c._ensureTranslations(hass);
  assert.equal(calls, 1);
  c._translationRetryAt = 0;
  c._ensureTranslations(hass); await c._translationRequest;
  assert.equal(calls, 2);
});

test('device mode never borrows a cold-water value from another system', () => {
  const hass = makeHass();
  for (const [id, entry] of Object.entries(hass.entities)) {
    if (entry.translation_key === 'temp_coldwater') delete hass.entities[id];
  }
  hass.states['number.other_cold_water_temperature'] = {state:'30'};
  const c = card(); c.setConfig({device_id:'boiler_a'}); c.hass = hass;
  assert.equal(c._configIssue, 'missing_entities');
  assert.equal(c._coldWaterTemperature(), null);
});

test('unknown cold-water temperature suppresses the heat claim', () => {
  const common = JSON.parse(fs.readFileSync(
    new URL('../custom_components/solesta/translations/en.json', import.meta.url),
  )).common;
  const hass = makeHass();
  const c = card(); c.setConfig({device_id: 'boiler_a'}); c.hass = hass;
  hass.states[c._config.entities.cold_water_temperature].state = 'unavailable';
  c._cardTranslations = Object.fromEntries(Object.entries(common).map(
    ([key, value]) => [`component.solesta.common.${key}`, value],
  ));
  c._setupChartInteraction = () => {};
  c._queueViewportFit = () => {};
  c._scheduleScrollRestore = () => {};
  c._render = Card.prototype._render.bind(c);
  c._render();
  assert.match(c.shadowRoot.innerHTML, /Some system status data is unavailable/);
  assert.doesNotMatch(c.shadowRoot.innerHTML, /preheated water/);
});

test('the lower circulation line flows from right to left while the pump runs', () => {
  assert.match(source, /\.is-pump-active \.solesta-cold-horizontal \{\s*animation: solesta-flow-horizontal-left/);
  assert.match(source, /@keyframes solesta-flow-horizontal-left \{ to \{ background-position: -20px 0; \} \}/);
  assert.doesNotMatch(source, /solesta-flow-horizontal-right/);
});
