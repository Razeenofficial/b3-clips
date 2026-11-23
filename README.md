# B3 Clips

**by Beyond Three**

B3 Clips turns a long video into vertical 9:16 short clips (YouTube Shorts, Reels, TikTok) with captions, on your own Windows PC. Paste a link or pick a video file, and it:

1. transcribes the speech (on your PC, free);
2. uses an AI model to find the moments worth clipping, and scores them;
3. crops to 9:16 and follows faces, or uses a blurred background for wide shots;
4. burns in word-by-word captions and an optional hook title;
5. suggests a post title, description and hashtags.

Nothing is uploaded for you. You watch every clip and post it yourself.

> **Only clip footage you have the right to use:** your own videos, Creative Commons (CC-BY) videos with credit, or footage a clipping campaign (Vyro, Whop, …) gives you permission to clip. Downloading and reposting other people's videos breaks YouTube's terms and can get your accounts struck.

---

## 1. What you need

- Windows 10 or 11.
- 8 GB RAM minimum; 16 GB or more is better.
- About 5 GB of free disk space, plus space for your videos.
- Internet, for installing and for the AI step.
- **No graphics card needed**: everything runs on the CPU.

You don't need to install anything by hand: `install.bat` does it (see below).

## 2. Install (first time only)

1. **Get the files.** On the GitHub page click **Code → Download ZIP**, then unzip it to a simple folder, for example `D:\B3Clips`.
   If you use git: `git clone <repo-url> D:\B3Clips`.
2. **Double-click `install.bat`** in that folder.
   - If Windows shows *"Windows protected your PC"*, click **More info → Run anyway**. This happens because the file came from the internet.
   - If Windows asks *"Do you want to allow this app to make changes?"*, click **Yes**. This is for installing Python, FFmpeg or Node.js.
   - If `winget` asks you to accept terms the first time, type **Y**.
3. Wait. The first install takes about **10–20 minutes**. It installs only what is missing:

   | What | Why |
   |---|---|
   | Python 3.12 | runs B3 Clips |
   | FFmpeg | cuts and renders the video |
   | Node.js | needed by yt-dlp to download from YouTube |
   | Python packages (`.venv` folder) | yt-dlp, faster-whisper, OpenCV, FastAPI… |
   | Face model (YuNet) | face tracking |
   | Whisper `small.en` (about 500 MB) | speech-to-text |

4. When it says **"B3 Clips is installed"**, you'll have a **B3 Clips** icon on your **Desktop** and in the **Start menu**. Right-click it → **Pin to taskbar** for one-click access.

`install.bat` is safe to run again at any time, for example after an update or if something broke.

<details>
<summary>If the installer says <code>winget</code> is not available</summary>

`winget` comes with Windows 11 and recent Windows 10. If it's missing, install **App Installer** from the Microsoft Store, or install these by hand and then run `install.bat` again:

- Python 3.12 from https://www.python.org/downloads/ (tick **"Add python.exe to PATH"**)
- FFmpeg: https://www.gyan.dev/ffmpeg/builds/ (add its `bin` folder to PATH)
- Node.js LTS: https://nodejs.org
</details>

## 3. Start and stop

- **Start:** double-click the **B3 Clips** icon. It opens in its own window; nothing else to run.
- **Stop:** just **close the window**. B3 Clips stops by itself about 3 minutes later, once nothing is processing. A clip that is still rendering finishes first.
- **Stop now:** click **Quit B3 Clips** at the top right.

(Advanced: `run.bat` starts it with a console window that shows live logs. It doesn't stop by itself; close the console to stop it.)

## 4. Add an AI provider (free)

The AI reads the transcript and picks the best moments. Without one, B3 Clips uses a basic picker (loud, fast, exciting parts), which works but picks much worse moments.

Open **Settings → AI providers → + Add provider**, choose the type, paste your key, click **List available models** and click 1–3 models to add them, then **Save provider**. Saving also tests the connection.

### Google Gemini (free)
1. Go to https://aistudio.google.com/apikey and sign in with a Google account.
2. Click **Create API key** and copy it.
3. In B3 Clips: **Add provider → Google Gemini**, paste the key. The model list is pre-filled. Click **Save provider**.

Free limits are about **20 requests a day** per Flash model and about 500 a day per Flash Lite model. One video uses about 2–4 requests. **Don't add billing** in Google AI Studio and you can never be charged.

### NVIDIA (free, generous)
1. Go to https://build.nvidia.com and sign in or create a free NVIDIA developer account.
2. Click **Get API Key** and copy it. It starts with `nvapi-`.
3. In B3 Clips: **Add provider → NVIDIA**, paste the key, click **List available models**, and add **large general chat models**. Tested and working:
   `nvidia/nemotron-3-ultra-550b-a55b, mistralai/mistral-large-4-1t-a52b, minimaxai/minimax-m3.1-flash`
   Skip models with *embed, guard, safety, pii, coder, translate, clip, nano, 4b, 8b* in the name.

The limit is about **40 requests a minute**.

### Others
- **Groq:** free key at https://console.groq.com/keys. Fast, with daily limits.
- **OpenRouter:** key at https://openrouter.ai/keys. Free models end in `:free`.
- **Ollama:** fully local and free (https://ollama.com), no key. Slow on CPU and picks moments worse.
- **Custom:** any OpenAI-compatible server.

### Switching providers
- Every provider you add is saved with its own key and models. Click **Use** on one to make it active. You can also switch from the **"AI: …"** dropdown on the New clip page or on a job.
- **Automatic fallback** (on by default): if the active provider fails or runs out of free quota, B3 Clips tries your other providers.
- Each provider can have several models, separated by commas. They're tried in order when one is busy or retired.

## 5. Make clips

1. **New clip:** paste a YouTube link, or a video file path such as `D:\videos\my-video.mp4`.
2. Tick **"I have the right to use this footage"** and click **Find clips**.
3. Wait while it downloads and transcribes. Transcribing is the slow part on CPU: roughly half the video's length or more.
4. Review the **suggested moments**. Each shows a score, the hook, why it was picked, and the transcript.
   - **Preview** plays the moment in the original video.
   - Adjust **Start/End** and the **hook title** if needed.
5. Choose the **clip options**:
   - **Framing:** Auto, Face crop, Blurred fill or Split.
   - **Caption style:** Classic, Pop, Green, One word, Boxed or Minimal.
   - **Caption position**, and whether to show the hook title.
6. Click **Make clip**. Rendering a 40-second clip takes about 1–2 minutes.
7. **Watch the whole clip**, then copy the post text and upload it yourself. **Open folder** shows the files: each clip is an `.mp4`, and its post text is saved next to it as a `.txt`.

### Campaign rules (optional)
On a job, open **Campaign rules** and enter the brief's requirements: length, deadline, required hashtags, @mentions, phrase, credit line. Every clip then shows a ✓/✗ checklist.

## 6. Settings explained

| Setting | What it does |
|---|---|
| Transcription model | `small.en` is the balanced default for English. Use `small` or `medium` for **Hindi, Tamil, mixed languages**; use `medium.en` for more accurate English captions (slower). |
| Suggestions | **Auto** (default) keeps every moment that reaches the minimum score, so a dull video gives a few and a great one gives many. Or pick a fixed number. |
| Minimum score (auto) | 55 by default. Raise it (e.g. 70) to see only the best; lower it (e.g. 45) to see more. |
| Min / Max clip | Allowed clip length in seconds (default 20–60). Match your campaign's brief. |

## 7. Update to a new version

Download the new version and copy its files over your B3 Clips folder. Your `settings.json` (keys) and `jobs` folder are kept, because they aren't part of the download. Then run `install.bat` again.

## 8. Move to another PC

Double-click `pack.bat`. It creates `dist\B3Clips.zip`, without keys, videos or the Python folder. Copy that zip to the other PC, unzip it, and run `install.bat`.
`pack.bat keys` also includes your saved AI keys; don't share that zip.

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| Nothing opens when I click the icon | Look at `logs\clipper.log` in the B3 Clips folder. Or start `run.bat` to see errors live. |
| "Port 8790 is used by another program" | Another app uses that port. Close it, or set a Windows environment variable `CLIPPER_PORT` to another number (e.g. 8791). |
| YouTube download fails | YouTube changes often. Update yt-dlp: open the folder, type `cmd` in the address bar, then run `.venv\Scripts\python -m pip install -U yt-dlp` |
| "AI picking failed, used the basic picker" | The provider was busy, out of free quota, or the model name was retired. Use **Test** on the provider, add more models or a second provider, then click **Find again with this AI**. |
| AI is very slow | Some free models queue for minutes. B3 Clips skips a model that doesn't answer in time; put fast models first in the list. |
| Captions have spelling mistakes | Use a bigger transcription model in Settings (new jobs only). |

## 10. Privacy

- Your API keys are stored only in `settings.json` on your PC. They're excluded from git. **Never upload that file.**
- Transcription, face tracking and rendering run on your PC. Only the **transcript text** is sent to the AI provider you choose. Free tiers may use what you send to improve their models, so don't use it for private material.

## Credits

Built with yt-dlp, FFmpeg, faster-whisper, OpenCV, FastAPI, the YuNet face model and the Poppins font. Moment-picking rules adapted from OpenShorts and AI-Youtube-Shorts-Generator (both MIT); ideas inspired by SupoClip and Clips Studio. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
