# Verification record

Local checks performed November 15, 2026 on Windows with Python 3.15.2 and Gyan's FFmpeg/FFprobe 9.0.2 essentials build:

- All 11 unittest cases passed, including real synthetic SRT transmission and recording, HTTP workflow control, validation, stop/restart, and startup failure/recovery.
- Browser dashboard started a five-second workflow and displayed Completed with H.264 640×360 video, AAC audio, and FFprobe duration 5.021333 seconds.
- Browser playback advanced with readyState 4, decoded width 640, and no media error. Audio-stream presence is verified; perceived sound quality was not automatically measured.
- The initial shutdown-race failures were corrected before recording these results; the runbook describes the issue and the checks used to establish success.

These are bounded local checks. CI independently runs on Ubuntu/Python 3.11 with FFmpeg installed and explicitly checks that SRT and libx264 exist. Inspect its actual run result rather than assuming the Windows result proves Linux compatibility.

No Matrox SDK, cloud deployment, external sender, loss/jitter injection, measured end-to-end latency, or long-duration reliability test was performed.
