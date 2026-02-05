<script>
  import { onMount } from 'svelte';

  let loading = true;
  let saving = false;
  let error = '';
  let status = 'idle';
  let config = null;
  let rawJson = '';
  let rawDirty = false;
  let lastSaved = '';

  let form = {
    model: '',
    togetherApiKey: '',
    togetherApiBase: '',
    openrouterApiKey: '',
    openrouterApiBase: '',
    websearchApiKey: '',
    telegramEnabled: false,
    telegramToken: '',
    telegramAllowFrom: '',
    whatsappEnabled: false,
    whatsappAllowFrom: '',
    whatsappBridgeUrl: ''
  };

  const apiUrl = '/api/config';

  const clone = (obj) => {
    if (typeof structuredClone === 'function') return structuredClone(obj);
    return JSON.parse(JSON.stringify(obj));
  };

  const toCsv = (list) => (Array.isArray(list) ? list.join(', ') : '');
  const toList = (value) =>
    value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);

  const safeGet = (obj, path, fallback) => {
    let cur = obj;
    for (const key of path) {
      if (!cur || typeof cur !== 'object' || !(key in cur)) return fallback;
      cur = cur[key];
    }
    return cur ?? fallback;
  };

  const initForm = (cfg) => {
    form = {
      model: safeGet(cfg, ['agents', 'defaults', 'model'], ''),
      togetherApiKey: safeGet(cfg, ['providers', 'together', 'apiKey'], ''),
      togetherApiBase: safeGet(cfg, ['providers', 'together', 'apiBase'], ''),
      openrouterApiKey: safeGet(cfg, ['providers', 'openrouter', 'apiKey'], ''),
      openrouterApiBase: safeGet(cfg, ['providers', 'openrouter', 'apiBase'], ''),
      websearchApiKey: safeGet(cfg, ['tools', 'web', 'search', 'apiKey'], ''),
      telegramEnabled: !!safeGet(cfg, ['channels', 'telegram', 'enabled'], false),
      telegramToken: safeGet(cfg, ['channels', 'telegram', 'token'], ''),
      telegramAllowFrom: toCsv(safeGet(cfg, ['channels', 'telegram', 'allowFrom'], [])),
      whatsappEnabled: !!safeGet(cfg, ['channels', 'whatsapp', 'enabled'], false),
      whatsappAllowFrom: toCsv(safeGet(cfg, ['channels', 'whatsapp', 'allowFrom'], [])),
      whatsappBridgeUrl: safeGet(cfg, ['channels', 'whatsapp', 'bridgeUrl'], '')
    };
  };

  const syncRawFromConfig = (cfg) => {
    rawJson = JSON.stringify(cfg, null, 2);
    rawDirty = false;
  };

  const loadConfig = async () => {
    loading = true;
    error = '';
    status = 'loading';
    try {
      const res = await fetch(apiUrl);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      config = data;
      initForm(data);
      syncRawFromConfig(data);
      status = 'connected';
    } catch (err) {
      status = 'error';
      error = err?.message || 'Unable to reach gateway.';
    } finally {
      loading = false;
    }
  };

  const saveConfigObject = async (payload) => {
    saving = true;
    error = '';
    try {
      const res = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const body = await res.json();
      if (!res.ok || !body.ok) {
        throw new Error(body.error || `HTTP ${res.status}`);
      }
      config = payload;
      initForm(payload);
      syncRawFromConfig(payload);
      lastSaved = new Date().toLocaleTimeString();
    } catch (err) {
      error = err?.message || 'Save failed.';
    } finally {
      saving = false;
    }
  };

  const applyFormToConfig = (cfg) => {
    const next = clone(cfg || {});
    next.agents = next.agents || {};
    next.agents.defaults = next.agents.defaults || {};
    next.agents.defaults.model = form.model;

    next.providers = next.providers || {};
    next.providers.together = next.providers.together || {};
    next.providers.together.apiKey = form.togetherApiKey;
    next.providers.together.apiBase = form.togetherApiBase || null;

    next.providers.openrouter = next.providers.openrouter || {};
    next.providers.openrouter.apiKey = form.openrouterApiKey;
    next.providers.openrouter.apiBase = form.openrouterApiBase || null;

    next.tools = next.tools || {};
    next.tools.web = next.tools.web || {};
    next.tools.web.search = next.tools.web.search || {};
    next.tools.web.search.apiKey = form.websearchApiKey;

    next.channels = next.channels || {};
    next.channels.telegram = next.channels.telegram || {};
    next.channels.telegram.enabled = !!form.telegramEnabled;
    next.channels.telegram.token = form.telegramToken;
    next.channels.telegram.allowFrom = toList(form.telegramAllowFrom);

    next.channels.whatsapp = next.channels.whatsapp || {};
    next.channels.whatsapp.enabled = !!form.whatsappEnabled;
    next.channels.whatsapp.allowFrom = toList(form.whatsappAllowFrom);
    next.channels.whatsapp.bridgeUrl = form.whatsappBridgeUrl;

    return next;
  };

  const saveQuick = async () => {
    if (!config) return;
    await saveConfigObject(applyFormToConfig(config));
  };

  const saveRaw = async () => {
    try {
      const parsed = JSON.parse(rawJson);
      await saveConfigObject(parsed);
    } catch (err) {
      error = err?.message || 'Invalid JSON.';
    }
  };

  const applyRawToForm = () => {
    try {
      const parsed = JSON.parse(rawJson);
      config = parsed;
      initForm(parsed);
      rawDirty = false;
    } catch (err) {
      error = err?.message || 'Invalid JSON.';
    }
  };

  const resetRaw = () => {
    if (!config) return;
    syncRawFromConfig(config);
  };

  onMount(loadConfig);
</script>

<div class="shell">
  <header class="hero">
    <div>
      <span class="eyebrow">Gateway UI</span>
      <h1>nanobot Control Room</h1>
      <p>Manage models, providers, and channels without touching the filesystem.</p>
    </div>
    <div class={`status-pill ${status === 'connected' ? 'ok' : status === 'error' ? 'err' : ''}`}>
      {#if loading}
        Connecting…
      {:else if status === 'connected'}
        Connected
      {:else}
        Disconnected
      {/if}
    </div>
  </header>

  {#if error}
    <div class="notice err">{error} {status === 'error' ? 'Check gateway port mapping if you are seeing 502.' : ''}</div>
  {/if}

  <section class="grid">
    <div class="stack">
      <div class="card" style="--delay: 0.05s">
        <div class="card-header">
          <div>
            <h2>Quick Settings</h2>
            <p>Update the most-used config fields. Empty values overwrite existing values.</p>
          </div>
          <div class="meta">{lastSaved ? `Saved at ${lastSaved}` : 'No recent save'}</div>
        </div>

        <div class="fields">
          <label class="field">
            <span>Model</span>
            <input type="text" bind:value={form.model} placeholder="moonshotai/Kimi-K2.5" />
          </label>

          <label class="field">
            <span>Brave Search API Key</span>
            <input type="password" bind:value={form.websearchApiKey} placeholder="" />
          </label>

          <div class="split">
            <label class="field">
              <span>Together API Key</span>
              <input type="password" bind:value={form.togetherApiKey} />
            </label>
            <label class="field">
              <span>Together API Base</span>
              <input type="text" bind:value={form.togetherApiBase} placeholder="https://api.together.xyz/v1" />
            </label>
          </div>

          <div class="split">
            <label class="field">
              <span>OpenRouter API Key</span>
              <input type="password" bind:value={form.openrouterApiKey} />
            </label>
            <label class="field">
              <span>OpenRouter API Base</span>
              <input type="text" bind:value={form.openrouterApiBase} placeholder="https://openrouter.ai/api/v1" />
            </label>
          </div>
        </div>

        <div class="actions">
          <button class="primary" on:click|preventDefault={saveQuick} disabled={saving}>
            {saving ? 'Saving…' : 'Save Quick Settings'}
          </button>
          <button class="ghost" on:click|preventDefault={loadConfig} disabled={loading}>
            Reload
          </button>
        </div>
      </div>

      <div class="card" style="--delay: 0.1s">
        <div class="card-header">
          <div>
            <h2>Channels</h2>
            <p>Toggle channels and set allow-lists.</p>
          </div>
        </div>

        <div class="fields">
          <label class="toggle">
            <input type="checkbox" bind:checked={form.telegramEnabled} />
            <span>Telegram Enabled</span>
          </label>
          <label class="field">
            <span>Telegram Token</span>
            <input type="password" bind:value={form.telegramToken} />
          </label>
          <label class="field">
            <span>Telegram Allow From</span>
            <input type="text" bind:value={form.telegramAllowFrom} placeholder="123456, 78910" />
          </label>

          <div class="divider"></div>

          <label class="toggle">
            <input type="checkbox" bind:checked={form.whatsappEnabled} />
            <span>WhatsApp Enabled</span>
          </label>
          <label class="field">
            <span>WhatsApp Allow From</span>
            <input type="text" bind:value={form.whatsappAllowFrom} placeholder="+15551234567" />
          </label>
          <label class="field">
            <span>WhatsApp Bridge URL</span>
            <input type="text" bind:value={form.whatsappBridgeUrl} placeholder="ws://localhost:3001" />
          </label>
        </div>
      </div>
    </div>

    <div class="card raw" style="--delay: 0.15s">
      <div class="card-header">
        <div>
          <h2>Raw Config JSON</h2>
          <p>Full configuration editor with validation.</p>
        </div>
        <div class={`meta ${rawDirty ? 'warn' : ''}`}>
          {rawDirty ? 'Unsaved edits' : 'In sync'}
        </div>
      </div>

      <textarea
        class="raw-editor"
        bind:value={rawJson}
        on:input={() => (rawDirty = true)}
        spellcheck="false"
      ></textarea>

      <div class="actions">
        <button class="primary" on:click|preventDefault={saveRaw} disabled={saving}>
          {saving ? 'Saving…' : 'Save Raw JSON'}
        </button>
        <button class="ghost" on:click|preventDefault={applyRawToForm}>
          Apply JSON to Form
        </button>
        <button class="ghost" on:click|preventDefault={resetRaw}>
          Reset JSON
        </button>
      </div>
    </div>
  </section>
</div>
