---
name: vscode-speech-mic-recovery
description: "Use when VS Code Speech or Copilot dictation says Listening but no text appears, voice transcription is not captured, or Linux mic routing/mute breaks. Includes immediate recovery and persistent auto-fix steps for PipeWire/PulseAudio."
---

# VS Code Speech Mic Recovery (Linux)

Use this skill when dictation appears active but transcripts do not appear in Copilot Chat or editor dictation.

## Symptoms

- Mic button shows Listening, but no words are transcribed.
- Dictation worked before and suddenly stopped.
- VS Code Speech extension is installed but appears unresponsive.

## Success Criteria

- Dictation produces text reliably in VS Code.
- Default source is not muted.
- A persistent guard exists to recover from future mute regressions.

## Step 1: Verify and Fix Mic State Immediately

Run:

```bash
pactl get-default-source
pactl get-source-mute @DEFAULT_SOURCE@
pactl get-source-volume @DEFAULT_SOURCE@
```

If muted or too low, run:

```bash
pactl set-source-mute @DEFAULT_SOURCE@ false
pactl set-source-volume @DEFAULT_SOURCE@ 100%
```

Verify again:

```bash
pactl get-source-mute @DEFAULT_SOURCE@
pactl get-source-volume @DEFAULT_SOURCE@
```

Expected: `Mute: no` and volume not near 0%.

## Step 2: Confirm Capture Path Works

Run:

```bash
rm -f /tmp/vscode_mic_test.wav
arecord -d 2 -f cd /tmp/vscode_mic_test.wav
ls -lh /tmp/vscode_mic_test.wav
```

Expected: file exists and is non-trivial in size (not empty).

## Step 3: Confirm VS Code Speech Runtime

Run:

```bash
ls -d ~/.vscode/extensions/ms-vscode.vscode-speech-*
find ~/.vscode/extensions/ms-vscode.vscode-speech-* -type f \( -name "*.onnx" -o -name "*.ort" \) | head -20
```

Expected: extension exists and ONNX model files are present.

## Step 4: Validate Active Recording Stream

While dictation is running in VS Code:

```bash
pactl list source-outputs short
```

Expected: at least one active source output tied to the default mic source.

## Step 5: Persistent Self-Healing Fix (User Session)

Install a user-level mic guard that auto-unmutes on boot and periodically:

```bash
mkdir -p ~/.local/bin ~/.config/systemd/user
cat > ~/.local/bin/vscode-mic-guard.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
sleep 2
src="$(pactl get-default-source 2>/dev/null || true)"
[[ -z "${src}" ]] && exit 0
pactl set-source-mute "${src}" false || true
vol="$(pactl get-source-volume "${src}" 2>/dev/null | grep -o '[0-9]\+%' | head -1 | tr -d '%' || echo 100)"
if [[ "${vol}" -lt 70 ]]; then
  pactl set-source-volume "${src}" 100% || true
fi
EOF
chmod +x ~/.local/bin/vscode-mic-guard.sh

cat > ~/.config/systemd/user/vscode-mic-guard.service <<'EOF'
[Unit]
Description=Ensure microphone remains unmuted for VS Code Speech
After=pipewire.service pipewire-pulse.service

[Service]
Type=oneshot
ExecStart=%h/.local/bin/vscode-mic-guard.sh
EOF

cat > ~/.config/systemd/user/vscode-mic-guard.timer <<'EOF'
[Unit]
Description=Run VS Code mic guard periodically

[Timer]
OnBootSec=10s
OnUnitActiveSec=45s
Persistent=true
Unit=vscode-mic-guard.service

[Install]
WantedBy=timers.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now vscode-mic-guard.timer
systemctl --user start vscode-mic-guard.service
```

Verify:

```bash
systemctl --user is-enabled vscode-mic-guard.timer
systemctl --user is-active vscode-mic-guard.timer
pactl get-source-mute @DEFAULT_SOURCE@
```

Expected: timer is enabled and active, mic is unmuted.

## Step 6: If Still Failing

- Reload VS Code window.
- Re-open dictation in a plain text editor first.
- Check latest logs:

```bash
LATEST_EXTHOST=$(find ~/.config/Code/logs -type f -name exthost.log | sort | tail -1)
rg -n -i "speech|voice|dictation|microphone|onnx|model" "$LATEST_EXTHOST"
LATEST_SPEECH=$(find ~/.config/Code/logs -type f -name "VS Code Speech.log" | sort | tail -1)
tail -80 "$LATEST_SPEECH"
```

Escalate only if mic capture works (`arecord`) but VS Code Speech has repeated runtime errors.
