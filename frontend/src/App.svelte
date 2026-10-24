<script lang="ts">
  import { onMount, untrack } from 'svelte';
  import Icon from './Icon.svelte';
  import RemoteKey from './RemoteKey.svelte';
  import VolumeDial from './VolumeDial.svelte';
  import InputDisplay from './InputDisplay.svelte';
  import { volumeLabel } from './volume.js';

  type Command = { name: string; code: string; description: string };
  type Parameter = { name: string; code: string; description: string; note: string; kind: string; minimum: number; maximum: number; offset: number };
  type Config = { commands: Command[]; zones: number[]; default_zone: number; dry_run: boolean; parameters: Parameter[]; current_input_parameters: Parameter[] };
  type Reading = { raw: number; value: number | null; unit: string; label: string | null };
  let config = $state<Config | null>(null);
  let zone = $state(1);
  let busy = $state(false);
  let loading = $state(true);
  let error = $state(false);
  let message = $state('Connecting to your remote…');
  let lastCommand = $state('B&K COMPONENTS');
  let advancedCommand = $state('power_toggle');
  let search = $state('');
  let filtered = $derived(config?.commands.filter(c => `${c.name} ${c.description} ${c.code}`.toLowerCase().includes(search.toLowerCase())) ?? []);
  let volume = $state<Reading | null>(null);
  let volumeStatus = $state('Reading receiver…');
  let currentInput = $state<Record<string, Reading | null>>({});
  let inputStatus = $state('Reading receiver…');
  let volumeWriting = $state(false);
  let disabled = $derived(!config || busy || volumeWriting);
  let volumeParameter = $derived(config?.parameters.find(p => p.name === 'volume'));
  let statusRead: Promise<void> | null = null;
  let pendingVolume: number | null = null;
  let volumeTimer: ReturnType<typeof setTimeout> | undefined;
  let mounted = false;

  async function refreshStatus() {
    if (!mounted || !config || config.dry_run || busy || volumeWriting || statusRead || document.hidden) return;
    const requestedZone = zone;
    statusRead = (async () => {
      try {
        const result = await api(`/api/status?zone=${requestedZone}`);
        if (zone !== requestedZone || !mounted) return;
        volume = result.volume;
        volumeStatus = volume ? 'Live · turn to adjust' : 'Volume unavailable';
        currentInput = result.current_input;
        const available = Object.values(currentInput).filter(Boolean).length;
        inputStatus = !result.current_input_supported ? 'Available in Zone 1 only'
          : available === 7 ? 'Live' : available ? 'Partial reply' : 'No parameter reply';
      } catch {
        if (zone !== requestedZone || !mounted) return;
        volume = null;
        volumeStatus = 'No volume reply';
        currentInput = {};
        inputStatus = 'No parameter reply';
      }
    })();
    try { await statusRead; } finally { statusRead = null; }
  }

  function changeVolume(raw: number) {
    if (!mounted || !config || config.dry_run || busy || !volume) return;
    pendingVolume = raw;
    if (!volumeWriting && !volumeTimer) volumeTimer = setTimeout(() => { volumeTimer = undefined; void writeVolume(); }, 100);
  }

  async function writeVolume() {
    if (volumeWriting || busy || pendingVolume === null || !mounted) return;
    volumeWriting = true;
    const requestedZone = zone;
    try {
      await statusRead;
      while (mounted && pendingVolume !== null && zone === requestedZone) {
        const raw = pendingVolume;
        pendingVolume = null;
        volumeStatus = 'Adjusting…';
        const result = await api('/api/volume', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ zone: requestedZone, raw }),
        });
        if (!mounted || zone !== requestedZone) break;
        volume = result.volume;
        volumeStatus = volume ? 'Live · turn to adjust' : 'Volume unavailable';
        message = volume ? `Volume: ${volumeLabel(volume.raw, volumeParameter?.offset)} · zone ${zone}` : 'Volume unavailable';
        error = false;
      }
    } catch (cause) {
      volume = null;
      volumeStatus = 'No volume reply';
      message = cause instanceof Error ? cause.message : 'Volume unavailable';
      error = true;
    } finally {
      pendingVolume = null;
      volumeWriting = false;
    }
  }

  $effect(() => {
    const currentZone = zone;
    const currentConfig = config;
    untrack(() => {
      pendingVolume = null;
      clearTimeout(volumeTimer);
      volumeTimer = undefined;
      volume = null;
      volumeStatus = currentConfig?.dry_run ? 'Preview · no live volume' : 'Reading receiver…';
      currentInput = {};
      inputStatus = currentConfig?.dry_run ? 'Preview · no live values' : 'Reading receiver…';
      if (currentConfig && currentZone) void refreshStatus();
    });
  });

  $effect(() => {
    if (filtered.length && !filtered.some(c => c.name === advancedCommand)) {
      advancedCommand = filtered[0].name;
    }
  });

  async function api(path: string, options: RequestInit = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 12000);
    try {
      const response = await fetch(path, { ...options, signal: controller.signal });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'The receiver is unavailable.');
      return data;
    } finally { clearTimeout(timer); }
  }

  async function loadRemote() {
    loading = true;
    try {
      config = await api('/api/remote');
      zone = config!.default_zone;
      message = config!.dry_run ? 'Preview mode. No commands will be transmitted.' : 'Ready. Choose a control to send a command.';
      error = false;
    } catch {
      config = null;
      error = true;
      message = 'Cannot reach the remote server. Check your Wi-Fi and retry.';
    } finally { loading = false; }
  }

  async function send(command: string) {
    if (!config || busy || volumeWriting) return;
    pendingVolume = null;
    clearTimeout(volumeTimer);
    volumeTimer = undefined;
    const description = config.commands.find(c => c.name === command)?.description ?? command;
    busy = true;
    error = false;
    message = `Sending ${description.toLowerCase()}…`;
    try {
      await statusRead;
      const result = await api('/api/ir', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, zone }),
      });
      lastCommand = description;
      message = `${result.dry_run ? 'Previewed' : 'Sent'}: ${description.toLowerCase()} · zone ${zone}`;
    } catch (cause) {
      error = true;
      message = cause instanceof Error && cause.name !== 'AbortError'
        ? cause.message : 'Connection interrupted. Check the receiver before sending again.';
    } finally { busy = false; void refreshStatus(); }
  }

  onMount(() => {
    mounted = true;
    void loadRemote();
    const interval = setInterval(() => { void refreshStatus(); }, 1000);
    return () => {
      mounted = false;
      pendingVolume = null;
      clearInterval(interval);
      clearTimeout(volumeTimer);
    };
  });
</script>

<div class="page">
  <main aria-label="Receiver remote">
    <div class="remote-shell">
      <div class="remote-topline"><span class="remote-brand">B&K <small>COMPONENTS</small></span><span class="indicator" class:error class:working={busy}></span></div>

      <div class="display">
        <div class="display-meta"><span>ZONE {String(zone).padStart(2, '0')}</span><span>{config?.dry_run ? 'PREVIEW' : 'SERIAL REMOTE'}</span></div>
        <div class="display-volume" aria-label="Receiver volume">
          <span>VOLUME</span>
          <strong>{volume ? volumeLabel(volume.raw, volumeParameter?.offset) : config?.dry_run ? 'Preview' : 'Unavailable'}</strong>
        </div>
        <div class="display-title">{lastCommand}</div>
        <div class="display-bottom"><span class="display-bars" aria-hidden="true">▂ ▄ ▆ ▄ ▂</span><span>LAST COMMAND / {busy ? 'SENDING' : 'READY'}</span></div>
      </div>

      <div class="zone-row"><label for="zone">CONTROL ZONE</label><select id="zone" bind:value={zone} disabled={disabled}>
        {#each config?.zones ?? [1] as z}<option value={z}>Zone {z}</option>{/each}
      </select></div>

      <section class="power-row" aria-label="Power controls">
        <RemoteKey command="power_on" label="On" variant="small" {disabled} onpress={send} />
        <RemoteKey command="power_toggle" label="Power" icon="power" variant="power" {disabled} onpress={send} />
        <RemoteKey command="power_off" label="Off" variant="small" {disabled} onpress={send} />
      </section>

      <div class="control-center">
        <div class="volume-controls">
        <section class="rocker" aria-label="Volume">
          <span class="section-label">VOLUME</span>
          <div class="rocker-body">
            <RemoteKey command="volume_up" label="Volume up" icon="plus" variant="volume" {disabled} onpress={send} />
            <span class="rocker-line"></span>
            <RemoteKey command="volume_down" label="Volume down" icon="minus" variant="volume" {disabled} onpress={send} />
          </div>
        </section>
        <VolumeDial raw={volume?.raw ?? null} disabled={!config || config.dry_run || busy || !volume}
          status={volumeStatus} maximum={volumeParameter?.maximum} offset={volumeParameter?.offset} onchange={changeVolume} />
        </div>
        <InputDisplay parameters={config?.current_input_parameters ?? []} readings={currentInput}
          status={inputStatus} supported={zone === 1} />
        <section class="navigation" aria-label="Menu navigation">
          <span class="section-label">NAVIGATE</span>
          <div class="dpad">
            <RemoteKey command="up" label="Up" icon="up" variant="nav nav-up" {disabled} onpress={send} />
            <RemoteKey command="left" label="Left" icon="left" variant="nav nav-left" {disabled} onpress={send} />
            <RemoteKey command="enter" label="OK" variant="nav nav-ok" {disabled} onpress={send} />
            <RemoteKey command="right" label="Right" icon="right" variant="nav nav-right" {disabled} onpress={send} />
            <RemoteKey command="down" label="Down" icon="down" variant="nav nav-down" {disabled} onpress={send} />
          </div>
        </section>
      </div>

      <div class="utility-row">
        <RemoteKey command="mute" label="Mute" icon="mute" variant="utility" {disabled} onpress={send} />
        <RemoteKey command="menu" label="Menu" icon="menu" variant="utility" {disabled} onpress={send} />
        <RemoteKey command="exit" label="Exit" icon="back" variant="utility" {disabled} onpress={send} />
      </div>

      <section class="sources" aria-label="Input controls">
        <div class="section-heading"><span class="section-label">FIND YOUR SOURCE</span><Icon name="source" size={16} /></div>
        <div class="input-grid">{#each [1, 2, 3, 4, 5, 6, 7, 8, 9] as n}
          <RemoteKey command={`input_${n}`} label={`Input ${n}`} variant="input" {disabled} onpress={send} />
        {/each}</div>
        <div class="source-step">
          <RemoteKey command="source_down" label="Previous source" icon="left" variant="source" {disabled} onpress={send} />
          <RemoteKey command="source_up" label="Next source" icon="right" variant="source" {disabled} onpress={send} />
        </div>
      </section>

      <details class="extra-controls">
        <summary>Radio & tone <span>+</span></summary>
        <div class="detail-content">
          <div class="triple-grid">
            <RemoteKey command="tuner" label="Tuner" icon="radio" {disabled} onpress={send} />
            <RemoteKey command="am" label="AM" {disabled} onpress={send} />
            <RemoteKey command="fm" label="FM" {disabled} onpress={send} />
          </div>
          {#each [['tune', 'Tune'], ['preset', 'Preset'], ['station', 'Station'], ['bass', 'Bass'], ['treble', 'Treble'], ['balance', 'Balance']] as [name, label]}
            <div class="adjust-row"><span>{label}</span>
              <RemoteKey command={`${name}_${name === 'balance' ? 'left' : 'down'}`} label={`${label} ${name === 'balance' ? 'left' : 'down'}`} icon="minus" variant="adjust" {disabled} onpress={send} />
              <RemoteKey command={`${name}_${name === 'balance' ? 'right' : 'up'}`} label={`${label} ${name === 'balance' ? 'right' : 'up'}`} icon="plus" variant="adjust" {disabled} onpress={send} />
            </div>
          {/each}
          <div class="two-grid">
            <RemoteKey command="stereo_mono" label="Stereo / mono" {disabled} onpress={send} />
            <RemoteKey command="loudness_toggle" label="Loudness" {disabled} onpress={send} />
          </div>
        </div>
      </details>

      <details class="extra-controls">
        <summary>Number pad <span>+</span></summary>
        <div class="detail-content number-grid">
          {#each [1, 2, 3, 4, 5, 6, 7, 8, 9] as n}<RemoteKey command={`digit_${n}`} label={String(n)} {disabled} onpress={send} />{/each}
          <RemoteKey command="plus_10" label="+10" {disabled} onpress={send} />
          <RemoteKey command="digit_0" label="0" {disabled} onpress={send} />
          <RemoteKey command="enter" label="Enter" {disabled} onpress={send} />
        </div>
      </details>

      <details class="extra-controls command-library">
        <summary>All IR commands <span>{config?.commands.length ?? '—'}</span></summary>
        <div class="detail-content">
          <p class="detail-note">The complete receiver command library. “All B&K” commands may affect multiple devices.</p>
          <label class="field-label" for="search">Find a command</label>
          <input id="search" type="search" bind:value={search} placeholder="Search name or hex code" />
          <label class="field-label" for="command">Command ({filtered.length})</label>
          <select id="command" bind:value={advancedCommand} disabled={disabled || !filtered.length}>
            {#each filtered as c}<option value={c.name}>{c.description} · {c.code}</option>{/each}
          </select>
          <button class="send-command" disabled={disabled || !filtered.some(c => c.name === advancedCommand)} onclick={() => send(advancedCommand)}>Send command <span>↗</span></button>
        </div>
      </details>

    </div>

    <div class="feedback" class:error role="status" aria-live="polite" aria-atomic="true">
      <span class="feedback-dot" class:working={busy || loading}></span><p>{message}</p>
      {#if !config && !loading}<button class="retry" onclick={loadRemote}>Retry</button>{/if}
    </div>
  </main>
</div>
