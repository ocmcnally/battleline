let _ctx: AudioContext | null = null;

function ctx(): AudioContext {
  if (!_ctx || _ctx.state === "closed") {
    _ctx = new AudioContext();
  }
  return _ctx;
}

export function playCardSound(): void {
  try {
    const ac = ctx();
    const bufLen = Math.floor(ac.sampleRate * 0.09);
    const buf = ac.createBuffer(1, bufLen, ac.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < bufLen; i++) data[i] = Math.random() * 2 - 1;

    const noise = ac.createBufferSource();
    noise.buffer = buf;

    const lp = ac.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.setValueAtTime(1400, ac.currentTime);
    lp.frequency.exponentialRampToValueAtTime(180, ac.currentTime + 0.09);

    const gain = ac.createGain();
    gain.gain.setValueAtTime(0.4, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + 0.09);

    noise.connect(lp);
    lp.connect(gain);
    gain.connect(ac.destination);
    noise.start();
    noise.stop(ac.currentTime + 0.09);
  } catch {
    // AudioContext unavailable — silently ignore
  }
}
