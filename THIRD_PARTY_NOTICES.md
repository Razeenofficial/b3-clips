# Third-party notices

B3 Clips is a private, local tool. It uses or adapts the following work.

## Adapted (MIT)

**OpenShorts**: https://github.com/mutonby/openshorts
Copyright (c) 2024 OpenShorts. MIT License (core only; nothing from its `cloud/` folder is used).
Adapted: moment-picking prompt rules (stand-alone start, move the start earlier rather than cutting
the end), word-edge snapping with breath padding, and the reframing approach (dead-zone camera,
hard reset at scene cuts, blurred "general" layout for group shots). No YOLO/ultralytics code is used.

**AI-Youtube-Shorts-Generator**: https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator
Copyright (c) 2026 Anil Chandra Naidu Matcha. MIT License.
Adapted: virality criteria in the moment-picking prompt, overlap de-duplication.

**YuNet face detection model** (`models/face_detection_yunet_2023mar.onnx`), from opencv_zoo:
https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
Copyright (c) 2020 Shiqi Yu. MIT License.

MIT License text (applies to each of the above, with its own copyright line):

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
> associated documentation files (the "Software"), to deal in the Software without restriction,
> including without limitation the rights to use, copy, modify, merge, publish, distribute,
> sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all copies or
> substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
> NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
> NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES
> OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
> CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

## Ideas only (no code copied)

- **SupoClip**: https://github.com/FujiwaraChoki/supoclip (https://www.supoclip.com/), SupoClip
  Noncommercial Source License. Ideas: comparative re-rank, grounding picks in the transcript,
  measured hints for the AI, per-shot face/fit switching, colour-only active word with a line pop.
- **Clips Studio / Clips Kitty**: https://github.com/ColinGPT9/clips-studio, AGPL-3.0. Ideas:
  campaign compliance checklist, YouTube "most replayed" heatmap and loudness spikes as signals,
  three-way duplicate check, cut-instead-of-pan when the subject jumps.

## Tools used at runtime

yt-dlp (Unlicense), FFmpeg (LGPL/GPL), faster-whisper (MIT), OpenCV (Apache-2.0), FastAPI (MIT),
Poppins font (SIL Open Font License 1.1, Copyright 2020 The Poppins Project Authors; license text in `assets/fonts/OFL.txt`).
