# Local workflow troubleshooting

## Acceptance checks

1. Start the server and confirm the dashboard loads at its loopback address.
2. Start a short workflow and follow Starting → Running → Completed.
3. Confirm FFprobe reports H.264 video, AAC audio, and a duration near the requested recording length. The automated threshold permits up to one second below the requested duration.
4. Play the completed MP4: confirm that the test pattern moves and, at an appropriate volume, that the generated tone is present. This is a manual check, not an automated assessment of audio/video quality.
5. Start another workflow and stop it. Confirm Stopped, then run a new workflow successfully. A stopped partial recording is not presented as completed.

## Fault isolation

| Symptom | Evidence | Next action |
| --- | --- | --- |
| Missing tools | Start returns 400; check configured executable paths | Supply FFmpeg and FFprobe paths; check `ffmpeg -protocols` for SRT and `ffmpeg -encoders` for libx264 |
| Source or receiver fails | Failed job, error field, sender.log and receiver.log | Identify which process exited first; inspect protocol/encoder errors before retrying |
| Receiver stops at requested duration | Receiver exits successfully; sender may report broken pipe | Probe the recording; planned receiver shutdown can legitimately end the sender's connection |
| Job stalls | Bounded deadline ends the workflow and cleans up processes | Inspect SRT handshake and receiver logs; a process being alive does not establish media arrival |
| Start rejected with 409 | Active job or 20-job history cap | Stop/wait for the active job; restart the server for a new bounded session |
| Unknown job after server restart | In-memory history was reset | Inspect retained artifact files; use a new workflow for dashboard playback |
| Valid MP4 but no sound heard | Probe shows audio stream, browser playback controls and device volume | Check playback mute and local audio output; do not infer audio quality from codec metadata alone |

## An issue found during implementation

The receiver intentionally closes its connection after a bounded recording. The sender can observe that closure before the manager's polling loop observes receiver exit. Treating every sender nonzero exit as source failure produced false failures. The manager now waits briefly for the receiver and still requires receiver success plus independent audio/video/duration verification. It does not ignore arbitrary sender failures.

## Recovery boundaries

This lab tests controlled stop/restart and recovery after a missing executable. It does not yet test packet loss, jitter injection, real upstream disconnection, process crashes during a production event, or multiple hosts. Record those as future tests rather than inferring resilience from this loopback demonstration.
