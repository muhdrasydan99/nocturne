<img src="nocturne_icon_exact.png" alt="nocturne studio" width="400">

# nocturne

**nocturne** is a songwriting app with a rhyme highlighter. It brings lyric writing, rhyme tools and beat playback together in one themed desktop workspace.

> **Status:** v1.1.0-beta


<img width="1482" height="942" alt="{398839CD-62E4-478E-B1D8-F198D2BF9B9F}" src="https://github.com/user-attachments/assets/de63aa7d-2544-4b5c-8bbf-77d61b7970ee" />


## What's New in v1.1.0-beta
- **Rhyme Checker:** Instant 2-word phonetic comparator under the Rhyme Engine with percentage match scores, tail breakdown, and quick swap (`⇄`) for English, Bahasa Melayu, and Manglish.
- **Lyrics Analyzer:** Dedicated dialog accessible from the sidebar offering honest craft critiques, cliché and abstract-word detection, cadence jump checks, writer's block exercises, and song-finishing plans.
- **Custom Studio Themes:** Live theme switcher powered by JSON palettes with high-contrast foreground text support (including Monochrome Noir).

## Features

### Lyric editor & Rhyme tools
- Rhyme highlighting for end and internal rhymes, with optional near-rhyme underlines
- Highlighting by rhyming syllable or by whole word
- Live syllable counter for each bar, with flow cadence warnings
- Rhyme lookup with filters for English (EN), Bahasa Melayu (BM), language packs and slant rhymes
- **Rhyme Checker** for direct side-by-side phonetic comparison and rhyme score percentage
- Search within the current lyrics
- Full-screen lyric preview with auto-scroll
- Scrapbook for loose bars, hooks and ideas
- **Lyrics Analyzer** for offline craft feedback, targeted exercises, and structural planning
- PDF lyric export

### Beat player
- Load, play and loop beats
- Metronome with Off, On and Auto modes, plus 4/4, 3/4 and 6/8 time signatures
- Tap tempo and manual downbeat sync
- Timestamp markers and lyric line timestamps

### Pen Meter
- Rates your lyrics and opens a detailed scorecard

### Vault
- Save, search and reopen tracks
- Recycle bin for restoring deleted tracks

### Profiles
- Up to 9 profiles, each with a unique name
- Custom avatars
- Optional PIN lock with encryption of profile data
- Rename, duplicate, delete, back up and restore (`.zip`)

### Customization
- Dynamic UI themes (including Monochrome Noir) with automatic contrast adjustment
- Custom slang and language packs, including word list import and online search
- Editor font, size, weight and word wrap settings
- Auto-save, default BPM and default beat volume settings

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+F` | Search in the current lyrics |
| `Ctrl+M` | Pin a marker at the current beat position |
| `Ctrl+T` | Insert a timestamp on the current lyric line |
| `Space` | Start or pause auto-scroll (full-screen preview) |
| `Esc` | Close the full-screen preview |

## Installation (Windows)

1. Run `Nocturne_Setup_1.1.0-beta.exe` (or `Nocturne_v1.1.0-beta.exe`).
2. Follow the setup wizard if using the installer.
3. Open **Nocturne** from the Start menu or the optional desktop shortcut.

The default install location is `%LOCALAPPDATA%\Programs\Nocturne`. Administrator rights are not required.

## Getting started

1. Choose a profile, or create a new one.
2. Enter a track title and start writing.
3. Load a beat from the **beat player** panel.
4. Use **Rhyme Checker** on the right panel to test two words side by side, or click **Analyze** under the scrapbook for a full craft breakdown.
5. Click **Save Track** to keep your work in the vault.

## Running from source

You need Python 3 and the project files, including `main.py` and `lyric_engine.py`.

```bash
pip install PySide6 numpy librosa
python main.py
```

[FFmpeg](https://ffmpeg.org/) is recommended. It is used as a fallback when beat audio cannot be read directly.

## Your data

Profiles are stored in the `profiles` folder inside the app directory.

- Export a profile backup regularly, especially before updating or uninstalling.
- Keep your PIN somewhere safe.

## Internet use

Core features—including the **Rhyme Engine**, **Rhyme Checker**, **Pen Meter**, and **Lyrics Analyzer**—work completely offline. An internet connection is only used for optional online word list downloads or fetching missing SF Pro font files.

## Credits

© 2026. Made by Adan, with help from Gemini and Claude.
