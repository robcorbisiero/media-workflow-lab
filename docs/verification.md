# Verification record

Local checks performed November 15, 2026 on Windows with Python 3.15.2 and Gyan's FFmpeg/FFprobe 9.0.2 essentials build:

- All 11 unittest cases passed, including real synthetic SRT transmission and recording, HTTP workflow control, validation, stop/restart, and startup failure/recovery.
- Browser dashboard started a five-second workflow and displayed Completed with H.264 640×360 video, AAC audio, and FFprobe duration 5.021333 seconds.
- Browser playback advanced with readyState 4, decoded width 640, and no media error. Audio-stream presence is verified; perceived sound quality was not automatically measured.
- The initial shutdown-race failures were corrected before recording these results; the runbook describes the issue and the checks used to establish success.

These are bounded local checks. CI independently runs on Ubuntu/Python 3.11 with FFmpeg installed and explicitly checks that SRT and libx264 exist. Inspect its actual run result rather than assuming the Windows result proves Linux compatibility.

The independent Ubuntu/Python 3.11 run also passed on November 15, 2026: [verified workflow run](https://github.com/robcorbisiero/media-workflow-lab/actions/runs/43764494487). It installed FFmpeg, checked SRT/libx264 availability, and completed the unittest suite successfully.

No Matrox SDK, cloud deployment, external sender, loss/jitter injection, measured end-to-end latency, or long-duration reliability test was performed.
# OBS input interoperability — November 15, 2026

Executed the optional Windows check against the official OBS Studio 33.0.1 x64 ZIP, whose executable's Windows signature validated as OBS Project, LLC. The OBS profile/scene collection was generated in a separate portable lab copy, with only a synthetic SRT Media Source; no desktop, microphone or webcam source was used.

The final check recorded **12.120 seconds**, H.264 **640×360 at 25 fps**, and AAC audio. Independently decoded frames at five and six seconds differed, the RGB sample range was 255, and mono decoded audio RMS was **0.08735** (normalized full scale). OBS's output timer finalized the MKV. An earlier 30 fps run also completed; the final profile explicitly selects 25 fps.

![Frame extracted from OBS's recorded SRT input](images/obs-recorded-frame.png)

This image is extracted from the OBS recording, not an OBS UI screenshot. Desktop automation could not capture the OBS window reliably; verification used the OBS log, finalized recording, FFprobe and decoded samples. Human listening, lip sync, network loss recovery and measured end-to-end latency were not assessed by these checks. No cloud or physical broadcast hardware was used. See the [repeatable OBS walkthrough](obs-interop.md).

