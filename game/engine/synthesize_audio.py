"""Generate cinematic procedural sound effects for Return by Death Manor.
Creates uncompressed WAV files using Python's standard wave and struct modules.
"""

import math
import wave
import struct
import random
import os

SAMPLE_RATE = 44100

def write_wav(filename, samples):
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(SAMPLE_RATE)
        # Clamp and pack samples
        packed = bytearray()
        for s in samples:
            s = max(-1.0, min(1.0, s))
            int_val = int(s * 32767.0)
            packed.extend(struct.pack('<h', int_val))
        wav_file.writeframes(packed)
    print(f"Generated {filename} ({len(samples)/SAMPLE_RATE:.2f}s)")

def make_heartbeat():
    # Double pulse: lub-dub
    duration = 1.2
    total_samples = int(duration * SAMPLE_RATE)
    samples = [0.0] * total_samples
    
    # Pulse 1 (lub) at t=0.1
    # Pulse 2 (dub) at t=0.35
    for pulse_time, freq, amp, decay in [(0.1, 55.0, 0.9, 25.0), (0.35, 65.0, 0.75, 30.0)]:
        start_idx = int(pulse_time * SAMPLE_RATE)
        for i in range(start_idx, total_samples):
            t = (i - start_idx) / SAMPLE_RATE
            env = math.exp(-decay * t)
            # Low sub-bass sine wave with slight saturation
            val = math.sin(2.0 * math.pi * freq * t) * env * amp
            val += math.sin(2.0 * math.pi * (freq * 0.5) * t) * env * (amp * 0.4)
            samples[i] += math.tanh(val * 1.5)
            
    return samples

def make_clock_tick():
    # Grandfather clock wooden tick-tock
    duration = 0.4
    total_samples = int(duration * SAMPLE_RATE)
    samples = [0.0] * total_samples
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        # Crisp transient click
        click = (random.random() * 2.0 - 1.0) * math.exp(-120.0 * t) * 0.7
        # Resonant wooden cavity (around 380Hz and 820Hz)
        body = math.sin(2.0 * math.pi * 420.0 * t) * math.exp(-40.0 * t) * 0.5
        body += math.sin(2.0 * math.pi * 880.0 * t) * math.exp(-60.0 * t) * 0.3
        samples[i] = click + body
    return samples

def make_revolver_cock():
    # Crisp metallic click and cylinder rotation ratchet
    duration = 0.6
    total_samples = int(duration * SAMPLE_RATE)
    samples = [0.0] * total_samples
    # First click (cylinder rotate)
    for click_t, pitch, dec in [(0.05, 1200.0, 80.0), (0.12, 1600.0, 90.0), (0.28, 2200.0, 50.0)]:
        start_idx = int(click_t * SAMPLE_RATE)
        for i in range(start_idx, total_samples):
            t = (i - start_idx) / SAMPLE_RATE
            noise = (random.random() * 2.0 - 1.0) * math.exp(-dec * 1.5 * t) * 0.6
            ping = math.sin(2.0 * math.pi * pitch * t) * math.exp(-dec * t) * 0.4
            samples[i] += noise + ping
    return samples

def make_gunshot():
    # Explosive gunshot report with sub-bass kick and long decaying reverb tail
    duration = 2.2
    total_samples = int(duration * SAMPLE_RATE)
    samples = [0.0] * total_samples
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        # Initial explosive blast (distorted noise)
        blast = (random.random() * 2.0 - 1.0) * math.exp(-18.0 * t) * 1.0
        # Sub-bass punch (80Hz dropping to 40Hz)
        freq = max(35.0, 90.0 - 45.0 * t)
        punch = math.sin(2.0 * math.pi * freq * t) * math.exp(-10.0 * t) * 0.8
        # Long reverb tail (filtered noise decay)
        tail = (random.random() * 2.0 - 1.0) * math.exp(-3.0 * t) * 0.25
        val = blast + punch + tail
        samples[i] = math.tanh(val * 1.8)
    return samples

def make_loop_snap():
    # Reverse swell + reality tear + deep bell chime
    duration = 2.8
    total_samples = int(duration * SAMPLE_RATE)
    samples = [0.0] * total_samples
    
    # 0.0s to 1.2s: Reverse rising pitch swell
    swell_samples = int(1.2 * SAMPLE_RATE)
    for i in range(swell_samples):
        t = i / SAMPLE_RATE
        progress = t / 1.2
        freq = 80.0 + (progress ** 2) * 600.0
        amp = progress ** 2 * 0.7
        noise = (random.random() * 2.0 - 1.0) * progress * 0.3
        samples[i] = math.sin(2.0 * math.pi * freq * t) * amp + noise

    # At 1.2s: The Snap (metallic crack + bell toll)
    snap_idx = swell_samples
    for i in range(snap_idx, total_samples):
        t = (i - snap_idx) / SAMPLE_RATE
        # Crack
        crack = (random.random() * 2.0 - 1.0) * math.exp(-40.0 * t) * 0.9
        # Deep haunting bell chime (harmonic series: 140Hz, 280Hz, 420Hz)
        bell = (math.sin(2.0 * math.pi * 140.0 * t) * 0.5 +
                math.sin(2.0 * math.pi * 284.0 * t) * 0.3 +
                math.sin(2.0 * math.pi * 426.0 * t) * 0.2) * math.exp(-1.8 * t)
        samples[i] = crack + bell
    return samples

def make_thunder():
    # Distant mountain thunder rumble
    duration = 3.5
    total_samples = int(duration * SAMPLE_RATE)
    samples = [0.0] * total_samples
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        # Low frequency rumble
        f1 = 45.0 + math.sin(t * 3.0) * 10.0
        f2 = 60.0 + math.cos(t * 2.0) * 15.0
        rumble = (math.sin(2.0 * math.pi * f1 * t) * 0.5 + 
                  math.sin(2.0 * math.pi * f2 * t) * 0.4) * math.exp(-0.8 * t)
        # Cracking roll
        crack = (random.random() * 2.0 - 1.0) * math.exp(-4.0 * max(0.0, t - 0.2)) * 0.3
        samples[i] = math.tanh((rumble + crack) * 1.2) * 0.8
    return samples

def make_strain_burn():
    # Eerie high-pitched dissonance / ear ringing when cracks burn
    duration = 2.0
    total_samples = int(duration * SAMPLE_RATE)
    samples = [0.0] * total_samples
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        # Dual detuned high sines (tinnitus effect)
        s1 = math.sin(2.0 * math.pi * 3200.0 * t)
        s2 = math.sin(2.0 * math.pi * 3215.0 * t)  # 15Hz beat frequency
        env = math.exp(-1.2 * t) * 0.35
        samples[i] = (s1 + s2) * 0.5 * env
    return samples

def make_ui_select():
    # Crisp, satisfying tactile click
    duration = 0.12
    total_samples = int(duration * SAMPLE_RATE)
    samples = [0.0] * total_samples
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        click = (random.random() * 2.0 - 1.0) * math.exp(-180.0 * t) * 0.4
        ping = math.sin(2.0 * math.pi * 1800.0 * t) * math.exp(-120.0 * t) * 0.3
        samples[i] = click + ping
    return samples

def make_voice_loop(base_freq, timbre_harmonics, blip_rate=10.0, duration=1.0):
    """Generate a clean seamless looping rhythm of vocal chirps matching typewriter text."""
    total_samples = int(duration * SAMPLE_RATE)
    samples = [0.0] * total_samples
    num_blips = int(duration * blip_rate)
    blip_interval = total_samples / num_blips

    for b in range(num_blips):
        start_idx = int(b * blip_interval)
        blip_len = int(0.045 * SAMPLE_RATE)  # 45ms per chirp
        for i in range(blip_len):
            idx = start_idx + i
            if idx >= total_samples:
                break
            t = i / SAMPLE_RATE
            # Hanning window envelope
            env = 0.5 * (1.0 - math.cos(2.0 * math.pi * i / blip_len))
            # Harmonic synthesis
            val = 0.0
            for h_idx, (h_mult, h_amp) in enumerate(timbre_harmonics):
                val += math.sin(2.0 * math.pi * (base_freq * h_mult) * t) * h_amp
            samples[idx] += val * env * 0.35

    return samples

if __name__ == "__main__":
    out_dir = "game/audio"
    write_wav(os.path.join(out_dir, "heartbeat.wav"), make_heartbeat())
    write_wav(os.path.join(out_dir, "clock_tick.wav"), make_clock_tick())
    write_wav(os.path.join(out_dir, "revolver_cock.wav"), make_revolver_cock())
    write_wav(os.path.join(out_dir, "gunshot.wav"), make_gunshot())
    write_wav(os.path.join(out_dir, "loop_snap.wav"), make_loop_snap())
    write_wav(os.path.join(out_dir, "thunder.wav"), make_thunder())
    write_wav(os.path.join(out_dir, "strain_burn.wav"), make_strain_burn())
    
    # UI and Character Voice Blips
    write_wav(os.path.join(out_dir, "select.wav"), make_ui_select())
    # Marika: Soft, melodic, breathy tone (~400Hz)
    write_wav(os.path.join(out_dir, "voice_marika.wav"), make_voice_loop(400.0, [(1.0, 0.7), (2.0, 0.3)], blip_rate=11.0))
    # Elise: Sharp, proud, crisp tone (~310Hz)
    write_wav(os.path.join(out_dir, "voice_elise.wav"), make_voice_loop(310.0, [(1.0, 0.6), (2.0, 0.3), (3.0, 0.15)], blip_rate=10.0))
    # Vance: Dry, low, clinical tone (~195Hz)
    write_wav(os.path.join(out_dir, "voice_vance.wav"), make_voice_loop(195.0, [(1.0, 0.7), (2.0, 0.25), (4.0, 0.1)], blip_rate=9.5))
    # Hargrove: Deep, warm, resonant elder pulse (~135Hz)
    write_wav(os.path.join(out_dir, "voice_hargrove.wav"), make_voice_loop(135.0, [(1.0, 0.8), (2.0, 0.3), (3.0, 0.2)], blip_rate=8.5))
    # Odile: High, light, timid flutter (~530Hz)
    write_wav(os.path.join(out_dir, "voice_odile.wav"), make_voice_loop(530.0, [(1.0, 0.7), (2.0, 0.2)], blip_rate=12.0))
    # Adrian: Calm, grounded masculine tone (~160Hz)
    write_wav(os.path.join(out_dir, "voice_adrian.wav"), make_voice_loop(160.0, [(1.0, 0.7), (2.0, 0.3)], blip_rate=10.0))
    print("All cinematic audio generated successfully!")
