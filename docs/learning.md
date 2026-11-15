# Understand the demonstration before using it in an application

This lab gives you concrete work to inspect and practice. A generated portfolio project becomes useful interview evidence when you can explain its operation, repeat its checks, and state its limits.

## First walkthrough

Run a five-second job. Locate its artifact directory and compare result.json with probe.json. Explain why a REST response of 202 means accepted, not successfully recorded. Identify the evidence that changes the final state to Completed.

## Questions to answer in your own words

- Which requests belong to the control path, and which process sends actual video/audio?
- What does SRT caller versus listener mean? Which side binds to a local UDP port?
- Why are H.264, AAC, MPEG-TS, SRT, and MP4 different layers or formats?
- Why can a sender broken pipe be expected after a successful bounded recording?
- What does FFprobe establish? What must still be watched or listened to?
- Why does a 120 ms transport setting not prove 120 ms end-to-end latency?
- What happens on stop, timeout, conflicting starts, and server restart?
- What would need to change before accepting real network inputs or deploying this publicly?

## Honest application wording

After personally running and understanding the checks, a suitable description is: “Built and tested an AI-assisted local media-workflow lab using REST control, FFmpeg, SRT transport, and independent recording verification; documented stop/restart and failure diagnosis.”

Do not describe it as professional live-event support, Matrox ORIGIN integration, AWS deployment, or SDI/NDI experience. Add a real OBS or multi-host exercise only after completing and recording it separately.

## Next milestones

First demonstrate the current lab yourself. Then consider an OBS interoperability exercise and a second-host SRT test. A cloud milestone should follow an explicit provider choice, account review, budget, cleanup plan, and its own deployment/verification evidence. Nothing in the local lab establishes cloud expertise.
