# Business Requirements Specification

| Field | Value |
|---|---|
| Project | OBCD Pilot |
| Problem | No application exists to run the OBCD pipeline on a live video feed and alert users when objects change. |
| Stakeholders | Gulyás László (supervisor) <br> Muhammad Al Farizi (developer) <br> Harun Eren Mutlu (thesis and pipeline author) <br> Users monitoring a scene for object changes |
| Success criteria | 1. Accepts webcam feed or uploaded video and runs the OBCD pipeline. <br> 2. At least one of the six alarm channels works and can be toggled: pop-up, red text, sound effect, email, log output, HTTP post. <br> 3. First-time user installs and runs the app within 15 minutes using shipped docs. <br> 4. Email, HTTP, and logging alarms run in Docker. |
| Constraints | Cross-platform (Windows, macOS, Linux) <br> Single developer |
| Solution class | Desktop application with containerized background service |
| Assumptions | 1. Thesis model weights (TransOBCD, ConvOBCD) are reusable without retraining. <br> 2. Target machines have a webcam or video files. <br> 3. Docker is installed on deployment machines. |
| Dependencies | 1. OBCD pipeline source and trained weights from the thesis. <br> 2. YOLOv8 and MobileNetV2 pretrained weights. <br> 3. SMTP server for email alarms. <br> 4. HTTP endpoint for webhook alarms. |