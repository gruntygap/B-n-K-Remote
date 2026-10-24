<script lang="ts">
  import { volumeLabel, rotateVolume } from './volume.js';

  let { raw, disabled = false, status, maximum = 111, offset = -96, onchange }: {
    raw: number | null; disabled?: boolean; status: string; maximum?: number;
    offset?: number; onchange: (value: number) => void;
  } = $props();
  let draft = $state<number | null>(null);
  let pointer = $state<number | null>(null);
  let lastAngle = 0;
  let remainder = 0;
  let center = { x: 0, y: 0 };
  const shown = $derived(draft ?? raw);
  const angle = $derived(-135 + ((shown ?? 0) / maximum) * 270);

  $effect(() => {
    // Confirmed receiver state always wins once the gesture has ended.
    void raw;
    if (pointer === null) draft = null;
  });

  function start(event: PointerEvent) {
    if (disabled || raw === null || pointer !== null || (event.pointerType === 'mouse' && event.button !== 0)) return;
    const element = event.currentTarget as HTMLDivElement;
    const rect = element.getBoundingClientRect();
    center = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    if (Math.hypot(event.clientX - center.x, event.clientY - center.y) < 16) return;
    event.preventDefault();
    element.focus();
    element.setPointerCapture(event.pointerId);
    pointer = event.pointerId;
    lastAngle = Math.atan2(event.clientY - center.y, event.clientX - center.x) * 180 / Math.PI;
    remainder = 0;
    draft = raw;
  }

  function move(event: PointerEvent) {
    if (event.pointerId !== pointer) return;
    if (disabled) { end(event); return; }
    if (Math.hypot(event.clientX - center.x, event.clientY - center.y) < 16) return;
    const nextAngle = Math.atan2(event.clientY - center.y, event.clientX - center.x) * 180 / Math.PI;
    const next = rotateVolume(draft ?? raw ?? 0, lastAngle, nextAngle, remainder, maximum);
    lastAngle = nextAngle;
    remainder = next.remainder;
    if (next.raw !== draft) {
      draft = next.raw;
      onchange(next.raw);
    }
  }

  function end(event: PointerEvent) {
    if (pointer !== event.pointerId) return;
    const element = event.currentTarget as HTMLDivElement;
    pointer = null;
    if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId);
  }

  function key(event: KeyboardEvent) {
    if (disabled || raw === null) return;
    const step = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1,
      PageUp: 5, PageDown: -5 }[event.key];
    if (step === undefined) return;
    event.preventDefault();
    draft = Math.max(0, Math.min(maximum, (draft ?? raw) + step));
    onchange(draft);
  }
</script>

<div class="dial-control">
  <span class="section-label">VOLUME DIAL</span>
  <div class="volume-dial" class:dragging={pointer !== null} class:unavailable={disabled}
    role="slider" tabindex={disabled ? -1 : 0} aria-label="Receiver volume"
    aria-disabled={disabled} aria-valuemin={0} aria-valuemax={maximum}
    aria-valuenow={shown ?? undefined} aria-valuetext={shown === null ? status : volumeLabel(shown, offset)}
    onpointerdown={start} onpointermove={move} onpointerup={end} onpointercancel={end}
    onlostpointercapture={end} onkeydown={key}>
    <svg viewBox="0 0 140 140" aria-hidden="true">
      <circle class="dial-track" cx="70" cy="70" r="62" pathLength="360"
        stroke-dasharray="270 90" transform="rotate(135 70 70)" />
      <circle class="dial-progress" cx="70" cy="70" r="62" pathLength="360"
        stroke-dasharray={`${((shown ?? 0) / maximum) * 270} 360`} transform="rotate(135 70 70)" />
      <circle class="dial-face" cx="70" cy="70" r="51" />
      <g transform={`rotate(${angle} 70 70)`}><line class="dial-marker" x1="70" y1="28" x2="70" y2="36" /></g>
    </svg>
    <span class="dial-value" aria-hidden="true">{shown === null ? '—' : volumeLabel(shown, offset)}</span>
  </div>
  <span class="dial-status">{draft !== null && draft !== raw && raw !== null ? `Live ${volumeLabel(raw, offset)} · adjusting` : status}</span>
</div>
