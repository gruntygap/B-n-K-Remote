<script lang="ts">
  import { onMount } from 'svelte';
  import Icon from './Icon.svelte';
  import RemoteKey from './RemoteKey.svelte';

  type Command = { name: string; code: string; description: string };
  type Config = { commands: Command[]; zones: number[]; default_zone: number; dry_run: boolean };
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
  let disabled = $derived(!config || busy);

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
    if (!config || busy) return;
    const description = config.commands.find(c => c.name === command)?.description ?? command;
    busy = true;
    error = false;
    message = `Sending ${description.toLowerCase()}…`;
    try {
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
    } finally { busy = false; }
  }

  onMount(() => { void loadRemote(); });
</script>

<div class="page">
  <header class="masthead">
    <a class="wordmark" href="/" aria-label="B and K remote home">B<span>&</span>K<span class="wordmark-dot">.</span></a>
    <div class="masthead-right"><span class="eyebrow">THE LISTENING ROOM</span><span class="edition">Receiver remote / 01</span></div>
  </header>

  <main>
    <div class="intro"><p class="eyebrow">GOOD SOUND. WITHIN REACH.</p><h1>Settle in. Tune out.</h1><p>Your receiver, right where you need it.</p></div>

    <div class="remote-shell">
      <div class="remote-topline"><span class="remote-brand">B&K <small>COMPONENTS</small></span><span class="indicator" class:error class:working={busy}></span></div>

      <div class="display">
        <div class="display-meta"><span>ZONE {String(zone).padStart(2, '0')}</span><span>{config?.dry_run ? 'PREVIEW' : 'SERIAL REMOTE'}</span></div>
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
        <section class="rocker" aria-label="Volume">
          <span class="section-label">VOLUME</span>
          <div class="rocker-body">
            <RemoteKey command="volume_up" label="Volume up" icon="plus" variant="volume" {disabled} onpress={send} />
            <span class="rocker-line"></span>
            <RemoteKey command="volume_down" label="Volume down" icon="minus" variant="volume" {disabled} onpress={send} />
          </div>
        </section>
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

      <div class="remote-foot"><span>B&K</span><span>MADE FOR LISTENING</span><span>•••</span></div>
    </div>

    <div class="feedback" class:error role="status" aria-live="polite" aria-atomic="true">
      <span class="feedback-dot" class:working={busy || loading}></span><p>{message}</p>
      {#if !config && !loading}<button class="retry" onclick={loadRemote}>Retry</button>{/if}
    </div>
    <p class="footnote">{config?.dry_run ? 'PREVIEW MODE · NO SERIAL OUTPUT' : 'LOCAL CONTROL · NO CLOUD REQUIRED'}</p>
  </main>
  <footer class="page-footer"><span>A LITTLE LESS SCROLL. A LITTLE MORE SOUND.</span><span>B&K / REMOTE</span></footer>
</div>
