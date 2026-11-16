# OBS interoperability: synthetic SRT input

This optional Windows exercise connects two independent applications:

**FFmpeg synthetic pattern + tone → H.264/AAC in MPEG-TS → loopback SRT → OBS Media Source → OBS MKV recording → FFprobe and decoded-sample checks.**

OBS is the receiver/decoder and recorder here. This is not OBS contribution output, a physical camera test, or a Matrox integration. The original HTTP dashboard workflow remains a separate FFmpeg-to-FFmpeg check.

## Reproduce

1. Download the Windows x64 ZIP from [OBS's official download page](https://obsproject.com/download). Extract it into a **dedicated lab directory**, for example `C:\Tools\obs-media-lab`. Do not point this script at your everyday OBS installation. The script creates uniquely named profiles and scene collections beneath that copy's `config` directory and starts it in portable mode. No existing profiles or collections are overwritten.
2. Install FFmpeg/FFprobe as described in the main README. From the cloned repository, run:

```powershell
$env:FFMPEG_PATH = 'C:\Tools\ffmpeg\bin\ffmpeg.exe'
$env:FFPROBE_PATH = 'C:\Tools\ffmpeg\bin\ffprobe.exe'
python scripts/obs-interop.py --obs-directory 'C:\Tools\obs-media-lab'
```

3. OBS opens with an `SRT Lab` scene and a `Synthetic SRT` Media Source. Its output timer stops recording after 12 seconds. The script prints `passed` only after the finalized recording passes its checks. It leaves OBS open for inspection; close the lab copy when finished. Each repeat creates a new profile, scene collection and artifact directory. No streaming service account is needed.
4. Open the printed artifact directory. Play `obs-recording.mkv` in a compatible player, watch the moving pattern, and listen for the synthetic tone. `obs-frame.png` is a frame extracted from **OBS's recording**, not a screenshot of the OBS window. `result.json` contains probe and sample-check evidence. OBS's own logs stay under the portable copy's `config/obs-studio/logs`.

The scene contains only the generated SRT input: no microphone, desktop capture, webcam, or desktop audio source. No OBS remote-control server is enabled by the script. SRT is unencrypted and bound to `127.0.0.1`; do not change it to a public/LAN address as part of this exercise.

## What the checks establish

- OBS finalized the timed MKV, rather than checking a partial file.
- The recorded file contains H.264 video and AAC audio and reaches the duration threshold.
- Decoded video has a wide pixel range and frames at five and six seconds differ.
- Decoded audio contains signal above the configured RMS floor.

These checks reject blank, frozen, or silent output in this fixture. They do not measure perceptual quality, exact tone frequency, lip sync, latency, packet-loss recovery, or production reliability. A human playback check remains useful.

The sender listens for an SRT connection; OBS calls it. Connection role is independent of media direction. OBS's source uses `Local File = false`, `Input Format = mpegts`, and a caller URL. These choices follow the [official OBS SRT guide](https://obsproject.com/kb/srt-protocol-streaming-guide). The 120000 μs parameter is a setting, not a measured delay.

## Troubleshooting

| Symptom | Check |
|---|---|
| No OBS window | Extract the complete official ZIP; check Windows prerequisites and the portable log. |
| Timed recording not finalized | Check OBS log for an encoder error, startup dialog, output-timer setting, or missing writable output directory. Do not treat a partial recording as passed. |
| Black or silent recording | Confirm source URL, caller/listener pairing, `mpegts`, sender log, and that only one receiver connects to that sender. |
| Port already occupied | The candidate UDP port has a small allocation/bind race. Run a fresh exercise, which selects another port. |
| Expected broken pipe at end | OBS finishes before the sender; the script terminates the remaining synthetic sender. Inspect the verified recording before diagnosing this as a fault. |

This check needs a Windows desktop/GPU and OBS; it is intentionally separate from the headless Linux CI tests. On an unsuccessful run, inspect and close the lab OBS window; its output timer bounds any recording. Artifact files and portable configuration are retained for diagnosis.

## Interview explanation

After completing the normal feed exercise, run the [controlled interruption and recovery exercise](obs-recovery.md).

After personally repeating and understanding it: “I tested FFmpeg-to-OBS interoperability with synthetic H.264/AAC over local SRT, verified OBS's recording independently, and documented connection roles and failure checks.” This is hands-on lab work, not professional broadcast deployment experience.
