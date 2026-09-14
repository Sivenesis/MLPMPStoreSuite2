# DEPRECATED, INCORPORATED IN: [MLPMP Full Suite](https://github.com/Sivenesis/MLPMPFullSuite/)


## MLP Store Suite II

High-Performance In-Memory Store Patcher & Purchase Enabler for Windows (x64)

MLP Store Suite II is an open-source, zero-disk memory utility for the Windows x64 client of My Little Pony: Magic Princess (tested on game client v11.4.1a, package version 11.4.0.0).

The tool runs entirely in RAM via standard Windows APIs. It unlocks 2,380+ character entries in the in-game shop, normalizes purchase requirements and currencies, and preserves canonical town store isolation without modifying any files on disk.

---

## Core Functionality

- One-Click Shop Unlock: The "Execute Live RAM Patch & Enable Purchasing" button dynamically enables the store patch directly in memory, making hidden and limited characters immediately purchasable in the in-game store.
- Comprehensive Character Catalog: Unlocks and displays 2,380+ ponies, creatures, and shops with full portrait artwork and metadata.
- Interactive Filtering & Search: Filter catalog items by native town (Ponyville, Canterlot, Sweet Apple Acres, Crystal Empire, Klugetown), store status (Enabled/Disabled), or instant text search.
- Selective Batch Management: Enable, disable, or invert selections in bulk and write custom shop rosters directly to live memory.
- Vanilla Rollback: The "Restore Vanilla / Unpatch" button instantly restores original game instructions and resets shop items to default state.

---

## Technical & Architecture Highlights

- Zero-Disk Footprint: Operates strictly in game process memory (MyLittlePony_x64.exe) without altering game executables, packages, or save files.
- Canonical Town Store Isolation: Enforces native zone boundaries so ponies appear only in their appropriate town shops.
- Purchase & Currency Normalization: Replaces obsolete or unhandled currency references with Bits or Gems, eliminating store freeze bugs.
- Fail-Closed Memory Safety: Pre-flight checks verify original instruction bytes and game version before patching; aborts immediately on mismatch.
- Atomic Rollback System: Snapshot-based rollback restores original memory if any stage of the patch fails.
- Local API Security: Uses transient session token authentication and strict localhost origin checking to prevent unauthorized cross-origin requests.
- Automatic Background Watcher: Optionally monitors process health and synchronizes store state across town transitions.
- Fully Offline & Self-Contained: Built with 100% standard Python libraries—zero external pip packages and zero external network calls.

---

## Requirements

- Windows 10 or Windows 11 (64-bit)
- Python 3.8 or higher (Standard installation; no pip packages needed)
- Game Client installed and running (Tested against v11.4.1a / package 11.4.0.0)

---

## How to Use

1. Launch Game: Start MyLittlePony_x64.exe and enter any town.
2. Launch Suite: Run start.bat or execute the following in a command prompt:
   ```cmd
   python run.py
   ```
3. Open Web Dashboard: Navigate to http://127.0.0.1:8080/ in your browser (opens automatically on launch).
4. Apply Patch: Click "EXECUTE LIVE RAM PATCH & ENABLE PURCHASING". Open your in-game shop to view and buy unlocked ponies.
5. Revert Changes: Click "RESTORE VANILLA / UNPATCH" at any time to return the in-game shop to its original state.

---

## WebGUI Overview

- Live Telemetry: Displays process PID, base address, active town, in-game currency balances, and hook statuses in real time.
- Master Actions: One-click buttons to execute the patch, restore vanilla state, run deep memory inspection, or export diagnostic logs.
- Town Tabs: Filter characters by native zone (Ponyville, Canterlot, Sweet Apple Acres, Crystal Empire, Klugetown).
- Status Tabs: Filter by Enabled (active in store) or Disabled (hidden from store).
- Search & Batch Selection: Fast text search with tools to select, deselect, or invert selections, applied to RAM with one click.
- Live Terminal: Displays timestamped log events and diagnostics.

---

## Antivirus & Heuristic Flagging Notice

Because this tool uses standard Windows debugging APIs (OpenProcess, ReadProcessMemory, WriteProcessMemory, VirtualProtectEx) to inspect and modify another process in memory, antivirus software or Windows Defender may heuristically classify it as a game tool or trainer. The tool runs with minimum required privileges (PROCESS_SAFE_RIGHTS) and operates strictly offline. If necessary, add a folder exclusion in Windows Defender for the suite directory.

---

## Non-Affiliation & Legal Notice

This project is an unofficial, independent research and modding utility.

- This software is NOT affiliated with, endorsed by, sponsored by, or associated with Hasbro, Inc., Gameloft SE, or any of their parent companies, subsidiaries, or affiliates.
- My Little Pony, all related characters, trademarks, logos, audio, and visual assets are the exclusive property and registered trademarks of Hasbro, Inc. and Gameloft SE.
- This software is created solely for personal educational purposes, singleplayer modding research, and software analysis under fair-use principles.

---

## Singleplayer & Online Policy Notice

- Singleplayer and Offline Use Only: The developer does NOT condone, support, or encourage the use of this software on online profiles, competitive leaderboards, multiplayer events, or social features.
- Any attempt to use memory manipulation tools in online environments may violate the game's terms of service and can lead to account bans, stat resets, or profile restrictions.
- Use this utility strictly in offline/sandbox singleplayer contexts.

---

## "As-Is" Warranty & Data Loss Disclaimer

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

Modifying process memory inherently carries risk. Always back up your save files before using any memory modification utility. The developer accepts no responsibility for lost or corrupted save files, gameplay progression, or game installations.

---

## AI Usage Disclosure

Portions of this codebase, architecture design, security hardening, and technical reverse-engineering documentation were researched and developed with the assistance of artificial intelligence pair-programming tools.
