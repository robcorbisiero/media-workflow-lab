# Diagnose a missing feed and verify recovery

This Windows exercise deliberately stops the synthetic FFmpeg sender while OBS keeps recording. It then restarts the sender at the same loopback SRT endpoint. OBS must reconnect without restarting its recording or changing its source.

## Run it

Use the separate portable OBS copy and FFmpeg environment variables from the [OBS setup](obs-interop.md). From the repository directory:

```powershell
python scripts/obs-interop.py --obs-directory 'C:\Tools\obs-media-lab' --recovery
```

The recording lasts 30 seconds. After OBS starts recording, the script stops the sender near eight seconds and restarts it near sixteen seconds. Console messages identify both actions. The source contains only synthetic video and tone, so no microphone or desktop capture is involved.

The independent recording checks require:

| Recording checkpoint | Expected evidence |
|---|---|
| Five seconds | Nonblank video and audio signal before the fault |
| Fourteen seconds | Black image and near-silent audio during the outage |
| Twenty-four and twenty-five seconds | Nonblank video, audio signal and changing frames after recovery |

These are acceptance checkpoints, not exact outage or recovery latency measurements. Buffering and detection delays mean stopping the process does not make OBS black instantly. A failed checkpoint fails the exercise; a running OBS process alone is not proof of recovered media.

Play the printed artifact directory's `obs-recording.mkv`. Watch and listen to the beginning, the outage and the recovery. Compare `before.png`, `outage.png`, `recovered.png`, and `result.json`. OBS's own log should contain `Disconnected. Reconnecting...` followed by `Reconnected.` for the synthetic source.

## Work through the diagnosis

1. **Observe:** OBS remains open and continues recording, but the expected video and tone disappear. Separate application availability from media availability.
2. **Check the source:** The sender process was deliberately stopped. Inspect `sender.log` and the recorded action offsets in `result.json`.
3. **Check the receiver:** OBS's source URL and its caller role remain unchanged. Inspect its connection messages in the portable logs.
4. **Recover:** Restart the sender on the same listener address. OBS retries the connection automatically.
5. **Verify the media:** Confirm picture movement and tone in the later recording, then check the decoded-sample results. A reconnection log by itself is insufficient.

The script automates those actions for repeatability. Repeat the exercise yourself and explain the evidence before describing it in an interview. Do not call this a production incident you resolved.

## Scope

This demonstrates a controlled **sender process failure and restart**, not dropped network packets, jitter, route failure, link redundancy, failover to another source, or a public-cloud deployment. The recording contains an outage; there is no seamless continuity claim. No firewall or network settings are changed. Outputs and portable profiles remain available for inspection.

## Recorded verification — November 15, 2026

OBS Studio 33.0.1 portable on Windows recorded 30.080 seconds. The controller stopped the sender at approximately 8.016 seconds and restarted it at 16.050 seconds relative to detection of recording startup. OBS logged disconnection/retry and reconnection. Decoded recording checkpoints were:

| Checkpoint | RGB range | Normalized audio RMS |
|---|---:|---:|
| Before, 5 seconds | 255 | 0.08834 |
| Outage, 14 seconds | 0 | 0.00000 |
| Recovered, 24 seconds | 255 | 0.08828 |
| Recovered, 25 seconds | 255 | 0.08815 |

The recovered frames differed. These values verify the expected fixture states, not a measured recovery-time guarantee. No human listening assessment was performed for this automated recovery run.

Before interruption (extracted from OBS recording):

![Video present before interruption](images/recovery-before.png)

During interruption:

![Black frame during interruption](images/recovery-outage.png)

After reconnection:

![Video restored after reconnection](images/recovery-after.png)

