# MLP Store Suite II

**High-Performance In-Memory Store Patcher & Purchase Enabler for Windows (x64)**

MLP Store Suite II is an open-source, zero-disk memory utility designed for the Windows x64 client of *My Little Pony: Magic Princess* (tested on game client **v11.4.1a**). 

The tool runs completely in RAM via the Windows API, enabling all 2,380+ character entries in the in-game shop, normalizing purchase conditions, and strictly preserving canonical town store isolation without modifying a single file on disk.

---

## Key Features

- **Zero-Disk In-Memory Architecture**: No game binaries, archive packages, or configuration files are touched or altered on disk. All hooks and table synchronization happen strictly in process memory (`MyLittlePony_x64.exe`).
- **Complete In-Game Store Catalog**: Restores visibility for all 2,380+ characters directly into the in-game store rotation.
- **Pristine Town Store Section Isolation**: Characters appear exclusively in their native town shops (Ponyville, Canterlot, Sweet Apple Acres, Crystal Empire, Klugetown). The engine's native zone routing remains 100% intact.
- **Purchase & Currency Normalization**: Normalizes obsolete or unhandled currency references into standard Bits or Gems, preventing store purchase freezes and softlocks.
- **Interactive Web Management Interface**: A sleek, dark-mode WebGUI allows searching, filtering, and selectively enabling or disabling individual characters or entire town rosters.
- **Dynamic Auto-Watch Daemon**: Automatically detects game launches, town transitions, and store reloads, seamlessly maintaining memory integrity in the background.
- **Client Version Verification**: Parses client metadata and memory signatures upon connection to verify compatibility with v11.4.1a, providing a non-intrusive warning if a mismatched client update is detected.
- **100% Offline & Standalone**: Operates entirely offline with zero external network requests, scraping, or telemetry. Built exclusively with Python standard libraries.
- **Zero-Bloat Compressed Asset Delivery**: Catalog portraits are bundled in multi-part archives (`web/assets_part*.zip`, each < 18 MB to comply with GitHub's 25 MB web upload limit). The suite automatically unpacks them on first launch if unextracted.

---

## Quick Start Guide

### Prerequisites
- Windows 10 or 11 (64-bit)
- Python 3.8 or higher installed (Standard library only; no external `pip` dependencies needed)
- Game Client installed and running

### Step-by-Step Instructions

1. **Launch the Game**: Start the game client and wait until you are in town.
2. **Start the Suite**:
   - Double-click `start.bat`, **OR**
   - Open a terminal in the project directory and run:
     ```bash
     python run.py
     ```
3. **Open the Web Interface**: Navigate to `http://127.0.0.1:8080/` in your browser (opens automatically on launch).
4. **Apply Patch**:
   - Click **EXECUTE LIVE RAM PATCH & ENABLE PURCHASING**.
   - Open the in-game shop tab in any town to view the unlocked characters.
   - Leave **Auto-Watch** enabled to keep the patch active across town transitions and game reloads.

---

## WebGUI Overview

- **Live Telemetry Bar**: Shows process PID, base module address, active town, in-game wallet balances (Bits and Gems), and active memory hooks.
- **Town Tabs**: Filter the catalog by town (Ponyville, Canterlot, Sweet Apple Acres, Crystal Empire, Klugetown).
- **Status Filter**: Easily toggle views between `ALL STATUS`, `ENABLED` (active in store), and `DISABLED` (hidden from store).
- **Store Selection Tools**: Select or deselect specific ponies, click cards to toggle individually, and click **APPLY SELECTION TO RAM** to synchronize the in-game shop in real time.
- **Live Event Log**: Real-time diagnostic stream detailing hook applications, currency normalizations, and memory state changes.

---

## Project Structure

```text
MLPStoreSuite2/
├── data/
│   ├── database_v11.4.1a.json   # Static catalog definitions for v11.4.1a
│   └── ponies_catalog.json      # Working catalog used by the local runtime
├── server/
│   ├── __init__.py
│   ├── app.py                  # Lightweight HTTP API server (127.0.0.1)
│   └── memory_patcher.py       # Core Win32 memory engine & patch dispatcher
├── web/
│   ├── index.html              # Modern WebGUI dashboard
│   ├── style.css               # Monospace dark-mode stylesheet
│   ├── app.js                  # Frontend state management & catalog renderer
│   ├── assets_part1.zip        # Split portrait archive 1/3 (<18 MB, within GitHub upload limit)
│   ├── assets_part2.zip        # Split portrait archive 2/3 (<18 MB, within GitHub upload limit)
│   ├── assets_part3.zip        # Split portrait archive 3/3 (<18 MB, within GitHub upload limit)
│   └── assets/
│       └── portraits/          # Extracted character portraits (2,380+ assets)
├── run.py                      # Main entrypoint script
├── start.bat                   # Convenient Windows launcher script
├── README.md                   # Project overview & quick start guide
└── RESEARCH.md                 # In-depth reverse-engineering technical whitepaper
```

---

## Non-Affiliation & Copyright Notice

This project is an unofficial, independent research and modding utility. 

- This software is **NOT** affiliated with, endorsed by, sponsored by, or associated with **Hasbro, Inc.**, **Gameloft SE**, or any of their parent companies, subsidiaries, or affiliates.
- *My Little Pony*, all related characters, trademarks, logos, audio, and visual assets are the exclusive property and registered trademarks of **Hasbro, Inc.** and **Gameloft SE**.
- This software is created solely for personal educational purposes, singleplayer modding research, and software analysis under fair-use principles.

---

## Singleplayer & Online Policy Notice

- **Singleplayer / Offline Use Only**: The maintainer does **NOT** condone, support, or encourage the use of this software on online profiles, competitive leaderboards, multiplayer events, or social features.
- Any attempt to use memory manipulation tools in online environments may violate the game's terms of service and can lead to account bans, stat resets, or profile restrictions. 
- Use this utility strictly in offline/sandbox singleplayer contexts.

---

## "As-Is" Warranty & Data Loss Disclaimer

```text
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE MAINTAINER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, LOSS OF USE, DATA, SAVES, OR PROFITS; OR
BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
```

Modifying process memory inherently carries risk. **Always back up your save files before using any memory modification utility.** The maintainer accepts no responsibility for lost or corrupted save files, gameplay progression, or game installations.

---

## AI Usage Disclosure

Portions of this codebase, architecture design, and technical reverse-engineering documentation were researched and developed with the assistance of artificial intelligence pair-programming tools.
