# Reverse-Engineering Technical Report: MLP Store Suite II

**Document Version:** 4.0.0  
**Target Game Client:** *My Little Pony: Magic Princess* (Windows x64 / v11.4.1a)  
**Binary Analyzed:** `MyLittlePony_x64.exe` (PE64 executable)  

---

## 1. Executive Summary & Problem Statement

In the Windows x64 client of *My Little Pony: Magic Princess*, the vast majority of characters (over 2,380 entries) are hidden from the in-game shop rotation. The game engine enforces store display through a multi-tiered validation architecture:
1. **Server-Side Store Rotations**: A rotation flag (`b125`) dictates whether an item is eligible for display.
2. **Category Deque Filtration**: An internal queue builder discards items that are not actively flagged in the current rotation.
3. **Shelf Render Culling**: The visual shelf iterator skips non-rotation items during UI layout generation.
4. **ActionScript GUI Dispatch & Purchase Condition Checks**: Clicking an item triggers an ActionScript 3 (AS3) event that passes through multiple native C++ verification gates (`Native_IsActionPossible`, `ShopManager::BuyItem`, currency compatibility, and player level requirements).
5. **Town Section Assignment**: Items are associated with specific town zones (Ponyville, Canterlot, Sweet Apple Acres, Crystal Empire, Klugetown, Everfree Forest).

Previous community efforts to modify the game relied on disk-level file tampering or naive byte patches. These methods encountered major failure modes:
- **Disk Tampering Failures**: Modifying game archives or executable files on disk breaks Windows AppX/GDK digital signatures, triggers package verification crashes, and risks corrupted save states.
- **The "Purchase Freeze" Softlock**: Forcing unlisted items into the store without normalizing their currency references causes the native purchase dispatch function to abort, locking the UI in an unhandled transaction state.
- **The Cross-Zone Store Clutter**: Naively patching the zone verification routine (`0x6C9600`) forced all 2,380+ ponies into every town store simultaneously, causing severe framerate drops and breaking town store boundaries.

**MLP Store Suite II** resolves these challenges through a non-destructive, zero-disk, in-memory patching architecture that unlocks the full catalog, normalizes purchase logic, and strictly preserves canonical town store isolation.

---

## 2. Engine Architecture & Memory Layout

### 2.1 Technology Stack
The game client (`MyLittlePony_x64.exe`) is built on a proprietary Gameloft 64-bit C++ game engine integrated with **Autodesk Scaleform GFx**. Scaleform executes ActionScript 3 bytecode to render the Flash-based user interface, communicating with the underlying C++ engine through a native dispatch bridge.

### 2.2 Master Controller Singletons
The engine organizes its runtime state around several global controller singletons. In client version **v11.4.1a**, their static relative virtual addresses (RVAs) from the main module base address are:

| Controller | Static RVA | Pointer Resolution | Description |
| :--- | :--- | :--- | :--- |
| **`ShopManager*`** | `0x1A87740` | `[base + 0x1A87740]` | Manages store catalog, item queues, active tabs, and purchase dispatch. |
| **`PlayerManager*`** | `0x1A85EE0` | `[base + 0x1A85EE0]` | Manages player profile, level, experience, and in-game wallet balances. |
| **`TownManager*`** | `0x1A86DE8` | `[base + 0x1A86DE8]` | Tracks the current active town zone, world simulation, and camera states. |

---

## 3. ShopManager Data Structures (`0x158` Stride)

The `ShopManager` singleton holds a contiguous array of all store items defined in the game data.

### 3.1 ShopManager Header Layout
Dereferencing `[base + 0x1A87740]` yields the `ShopManager` instance base pointer. The internal item array metadata is located at the following offsets:

| Offset | Type | Description |
| :--- | :--- | :--- |
| `+0x0028` | `uint64_t*` | Pointer to metadata container holding the pending purchase item ID string. |
| `+0x0438` | `uint64_t` | Pointer to the start of the contiguous `ShopItem` array. |
| `+0x0440` | `uint64_t` | Pointer to the end of the `ShopItem` array (`end_ptr`). |
| `+0x0450` | `uint32_t` | Total item count: `(end_ptr - start_ptr) / 0x158`. |
| `+0x0454` | `uint32_t` | Currently active shop category / town zone filter ID. |

### 3.2 Individual `ShopItem` Struct Layout (Stride: `0x158` / 344 bytes)
Each item in the array occupies exactly `0x158` bytes:

| Relative Offset | Type | Description |
| :--- | :--- | :--- |
| `+0x0008` | `uint32_t` | **Category ID**: `0x39` (decimal 57) designates characters (ponies). |
| `+0x0018` | `uint64_t*` | Pointer to metadata container. `[[item + 0x18] + 0x08]` points to a null-terminated ASCII identifier (e.g. `Pony_Applejack`). |
| `+0x0038` | `uint64_t*` | Pointer to the beginning of the `std::vector<int32_t>` allowed zones array. |
| `+0x0040` | `uint64_t*` | Pointer to the end of the allowed zones array. |
| `+0x0060 - +0x0070` | `uint32_t[4]` | Encrypted Currency Structure (Gameloft rotating key cipher). |
| `+0x0090 - +0x00A0` | `uint32_t[4]` | Encrypted Price Structure (Gameloft rotating key cipher). |
| `+0x0108` | `uint32_t` | XML Currency Reference Type (`1` = Bits, `2` = Gems). |
| `+0x0125` | `uint8_t` | **`b125`**: Rotation display eligibility flag (`1` = eligible, `0` = hidden). |
| `+0x0126` | `uint8_t` | **`b126`**: Store shelf active enablement flag (`1` = active, `0` = inactive). |
| `+0x0128` | `float` | **`SortPrice`**: Ordering float used by the shelf layout iterator. |

---

## 4. Gameloft Runtime Cryptography: The ROL/ROR-5 Cipher

### 4.1 Cipher Mechanics
To protect sensitive gameplay numbers (such as prices and player wallet amounts) against basic memory scanning tools, the engine stores values using a key-rotating bitwise cipher.

Each protected integer is represented by a 16-byte block composed of four 32-bit words: `[dw0, dw1, dw2, dw3]`.
- `dw0` serves as a randomized runtime salt/key.
- `dw2` holds the rotated, encrypted value.
- `dw1` and `dw3` store secondary verification tokens.

### 4.2 Decryption Algorithm
The plaintext 32-bit unsigned integer is computed by XORing `dw2` with `dw0`, followed by a 32-bit right rotation by 5 bits:

$$\text{Plaintext} = \text{ROR32}(dw2 \oplus dw0, 5)$$

In Python:
```python
def ror32(val: int, r: int = 5) -> int:
    return ((val >> r) | ((val << (32 - r)) & 0xFFFFFFFF)) & 0xFFFFFFFF

price = ror32(dw2 ^ dw0, 5)
```

### 4.3 Encryption Algorithm
To write a new value into memory without corrupting the cipher state, the transformation is inverted using a 32-bit left rotation by 5 bits:

$$dw2_{\text{new}} = \text{ROL32}(\text{Plaintext}_{\text{new}}, 5) \oplus dw0$$

In Python:
```python
def rol32(val: int, r: int = 5) -> int:
    return ((val << r) | (val >> (32 - r))) & 0xFFFFFFFF

new_dw2 = rol32(new_price, 5) ^ dw0
```

By reading `dw0`, computing the desired `new_dw2`, and writing it back to memory, the tool safely modifies prices and currencies without triggering engine integrity exceptions.

---

## 5. The Purchase Execution Chain & The "Purchase Freeze" Softlock

### 5.1 Purchase Verification Flow
When a player clicks "Buy" in the shop, the event triggers an ActionScript invocation that routes to native C++:

```text
[Scaleform UI Click]
       │
       ▼
Native_IsActionPossible (ActionScript Bridge)
       │
       ▼
ShopItem::IsBuyable [RVA 0x6333D0] ────────► (Returns 0? ──► Abort & show disabled state)
       │
       ▼
ShopManager::BuyItem [RVA 0x634E57] ───────► (Currency valid? ──► No? ──► ABORT / FREEZE)
       │
       ▼
Level Restriction Gate [RVA 0x629D2C] ─────► (Player level >= UnlockValue? ──► No? ──► Abort)
       │
       ▼
Currency Allow Check [RVA 0x634354]
       │
       ▼
Currency Deduction [RVA 0x634394]
       │
       ▼
[Item Added to Inventory / World Placement Mode]
```

### 5.2 The Cause of the Purchase Freeze
Hidden or unlisted items in the game data frequently feature empty, obsolete, or special event currency IDs (e.g. social hearts, special event tokens, or currency `0`). 

When a player attempts to purchase an item with an unhandled currency:
1. `ShopManager::BuyItem` reaches RVA `0x634E57`.
2. The engine detects that the required currency is neither standard Bits nor standard Gems, nor is the corresponding event active.
3. The function branches to an unhandled rejection path (`jne 0x634EEE`).
4. However, the Scaleform UI modal has already entered its modal transaction waiting state. Because the native handler neither completed nor threw an explicit user-facing error dialog, the UI thread deadlocks, creating the infamous "Purchase Freeze".

### 5.3 The Dual-Layer Fix
To permanently prevent this freeze, MLP Store Suite II implements a two-pronged solution:
1. **Live Memory Currency Normalization**: During synchronization, the tool inspects every pony item in memory. If an item has an obsolete or zero currency, its currency reference (`+0x108`) and encrypted currency block (`+0x60`) are normalized to Bits (`1`) or Gems (`2`). Furthermore, any zero price is bumped to a nominal positive value (`price >= 1`), satisfying the engine's price checks.
2. **In-Place Currency Gate Patches**: The conditional rejection branches at `0x634E57`, `0x634354`, and `0x634394` are patched with NOPs, ensuring transaction dispatch proceeds smoothly to completion.

---

## 6. The Master 8 In-Place Hooks

All 8 hooks are applied in-place in process memory via Win32 `VirtualProtectEx` and `WriteProcessMemory`. No external detours or code caves are required, ensuring maximum stability.

```text
HOOK SUMMARY TABLE (Client v11.4.1a):
┌─────────────────────┬───────────┬──────────────────────────┬──────────────────────────┐
│ Identifier          │ RVA       │ Vanilla Bytes            │ Patched Bytes            │
├─────────────────────┼───────────┼──────────────────────────┼──────────────────────────┤
│ HOOK_ROT_SETTER     │ 0x1301A47 │ 0F 94 C0                 │ B0 01 90                 │
│ HOOK_ROT_BUILDER    │ 0x069FFC3 │ 74 43                    │ 90 90                    │
│ HOOK_ROT_RENDER     │ 0x067C81F │ 0F 84 FD 00 00 00        │ 90 90 90 90 90 90        │
│ HOOK_BUYABILITY_ALL │ 0x06333D0 │ 40 53 48 83 EC 20        │ B0 01 C3 90 90 90        │
│ HOOK_CURRENCY_CHECK │ 0x0634E57 │ 0F 85 91 00 00 00        │ 90 90 90 90 90 90        │
│ HOOK_CURRENCY_ALLOW │ 0x0634354 │ 0F 85 E3 00 00 00        │ 90 90 90 90 90 90        │
│ HOOK_CURRENCY_PAY   │ 0x0634394 │ 74 46                    │ 90 90                    │
│ HOOK_BUY_LEVEL_GATE │ 0x0629D2C │ 0F 8C 15 01 00 00        │ 90 90 90 90 90 90        │
└─────────────────────┴───────────┴──────────────────────────┴──────────────────────────┘
```

### Detailed Disassembly & Analysis

#### 1. `HOOK_ROT_SETTER` (RVA `0x1301A47`)
- **Vanilla Instructions**: `sete al` (3 bytes: `0F 94 C0`)
- **Patched Instructions**: `mov al, 1; nop` (3 bytes: `B0 01 90`)
- **Purpose**: Located in the engine's XML shop element parser. Forces the rotation display flag (`b125`) to evaluate to `1` (true) for every parsed item.

#### 2. `HOOK_ROT_BUILDER` (RVA `0x69FFC3`)
- **Vanilla Instructions**: `je 0x6A0008` (2 bytes: `74 43`)
- **Patched Instructions**: `nop; nop` (2 bytes: `90 90`)
- **Purpose**: Located in `ShopManager::BuildCategoryDeque`. By default, if an item's rotation flag is not set, the builder jumps past the item insertion routine. NOPing this jump ensures unlisted items are placed into the store category deque.

#### 3. `HOOK_ROT_RENDER` (RVA `0x67C81F`)
- **Vanilla Instructions**: `je 0x67C922` (6 bytes: `0F 84 FD 00 00 00`)
- **Patched Instructions**: `6x nop` (6 bytes: `90 90 90 90 90 90`)
- **Purpose**: Located in the shop shelf render iterator. Skips inactive items during visual card instantiation. NOPing this jump forces the shelf layout to construct UI card objects for every item in the category deque.

#### 4. `HOOK_BUYABILITY_ALL` (RVA `0x6333D0`)
- **Vanilla Instructions**: `push rbx; sub rsp, 20h` (6 bytes: `40 53 48 83 EC 20`)
- **Patched Instructions**: `mov al, 1; ret; 3x nop` (6 bytes: `B0 01 C3 90 90 90`)
- **Purpose**: Direct function header override for `ShopItem::IsBuyable`. Immediately returns `true` (`al = 1`), signaling to the ActionScript bridge and native UI that the selected item is buyable.

#### 5. `HOOK_CURRENCY_CHECK` (RVA `0x634E57`)
- **Vanilla Instructions**: `jne 0x634EEE` (6 bytes: `0F 85 91 00 00 00`)
- **Patched Instructions**: `6x nop` (6 bytes: `90 90 90 90 90 90`)
- **Purpose**: Bypasses the initial currency type validation branch in `ShopManager::BuyItem`.

#### 6. `HOOK_CURRENCY_ALLOW` (RVA `0x634354`)
- **Vanilla Instructions**: `jne 0x63443D` (6 bytes: `0F 85 E3 00 00 00`)
- **Patched Instructions**: `6x nop` (6 bytes: `90 90 90 90 90 90`)
- **Purpose**: Bypasses the secondary currency authorization check that normally verifies active event status.

#### 7. `HOOK_CURRENCY_PAY` (RVA `0x634394`)
- **Vanilla Instructions**: `je 0x6343DC` (2 bytes: `74 46`)
- **Patched Instructions**: `nop; nop` (2 bytes: `90 90`)
- **Purpose**: Bypasses the deduction verification jump, ensuring wallet balance deductions proceed cleanly.

#### 8. `HOOK_BUY_LEVEL_GATE` (RVA `0x629D2C`)
- **Vanilla Instructions**: `jl 0x629E47` (6 bytes: `0F 8C 15 01 00 00`)
- **Patched Instructions**: `6x nop` (6 bytes: `90 90 90 90 90 90`)
- **Purpose**: In the pending purchase validation routine, this instruction checks if the player's level is less than the item's `UnlockValue`. NOPing the jump allows purchasing regardless of player level requirements.

---

## 7. Town Store Section Isolation (`0x6C9600`) — The Breakthrough

### 7.1 The Pitfall of Legacy Patches
A frequent flaw in earlier modding attempts was hooking `ShopItem::IsAllowedInZone` at RVA `0x6C9600` with:
```x86asm
mov al, 1
ret
```
While this successfully allowed characters to be displayed, it had a disastrous side effect: **it forced every single pony across all six towns into every single store tab**. The game was forced to populate 2,380 visual cards in Ponyville, 2,380 in Canterlot, 2,380 in Sweet Apple Acres, etc.

### 7.2 Reverse Engineering Discovery
Detailed disassembly of RVA `0x6C9600` revealed that Gameloft's vanilla zone filter is completely functional:

```x86asm
; ShopItem::IsAllowedInZone(ShopItem* this, int32_t zone_id)
0x6C9600: 4C 8B 41 40       mov  r8, [rcx + 40h]   ; r8 = vector.end
0x6C9604: 48 8B 49 38       mov  rcx, [rcx + 38h]  ; rcx = vector.start
0x6C9608: 49 3B C8          cmp  rcx, r8           ; empty check
0x6C960B: 74 15             je   0x6C9622          ; return 0 if empty
0x6C960D: 8B 01             mov  eax, [rcx]        ; read zone_id from vector
0x6C960F: 3B C2             cmp  eax, edx          ; compare with current store tab
0x6C9611: 74 0A             je   0x6C961D          ; match found! return 1
0x6C9613: 48 83 C1 04       add  rcx, 4            ; advance vector pointer
0x6C9617: 49 3B C8          cmp  rcx, r8
0x6C961A: 75 F1             jne  0x6C960D
0x6C961C: ...
0x6C961D: B0 01             mov  al, 1
0x6C961F: C3                ret
```

Each item already stores an array of allowed `zone_id` values at offset `+0x38`. For example:
- Applejack, Big Mac, Granny Smith $\rightarrow$ Zone 2 (Sweet Apple Acres)
- Twilight Sparkle, Pinkie Pie $\rightarrow$ Zone 0 (Ponyville)
- Princess Celestia, Fleur Dis Lee $\rightarrow$ Zone 1 (Canterlot)
- Princess Cadance, Shining Armor $\rightarrow$ Zone 4 (Crystal Empire)
- Capper, Captain Celaeno $\rightarrow$ Zone 6 (Klugetown)
- Zecora $\rightarrow$ Zone 3 (Everfree Forest)

### 7.3 The Architectural Decision
**Leave `0x6C9600` 100% vanilla (`4C 8B 41 40 48...`)**.

By keeping the vanilla routine intact (and actively remediating it if previous tools had modified it), the engine automatically routes every pony to their native town store section. Ponies appear strictly in their canonical town shops, preserving clean UI layout and pristine game balance.

---

## 8. Selective Catalog Management & Dynamic RAM Sync

In addition to unlocking the full catalog, MLP Store Suite II provides fine-grained control through its WebGUI:

1. **Catalog State Maintenance**: The application maintains a set of user-selected pony IDs.
2. **Dynamic Flag Synchronization**: When the user clicks **APPLY SELECTION TO RAM**:
   - The memory engine traverses the `ShopItem` array in RAM.
   - For items in the selection set: writes `b125 = 1`, `b126 = 1`, and ensures `SortPrice >= 1.0f`.
   - For items excluded from the selection: writes `b125 = 0`, `b126 = 0`.
3. **Seamless In-Game Transition**: When the player navigates store tabs or re-opens the shop, the engine reads the updated flags and reflects the custom roster immediately.

---

## 9. Auto-Watch Telemetry & Client Version Detection

### 9.1 Auto-Watch Background Loop
Because game clients periodically reload scene assets or reset memory allocations when transitioning between worlds, the memory engine runs an asynchronous watchdog thread (`Auto-Watch`):
- Checks if `MyLittlePony_x64.exe` is active.
- Verifies that all 8 master hooks are in their patched state.
- Inspects `0x6C9600` to ensure town store section isolation has not been compromised.
- Detects town transitions via `[TownManager + 0x20]` and maintains live synchronization.

### 9.2 Client Version Verification
To prevent running outdated hooks against updated game binaries:
- The engine dynamically queries the running process image path via Windows API `QueryFullProcessImageNameW`.
- Inspects package manifest data (`appxmanifest.xml` and `MicrosoftGame.config`) and PE version signatures in main module memory (`base + 0x154CC30`).
- If a mismatch from the target version (**v11.4.1a** / package `11.4.0.0`) is detected, the WebGUI displays a non-blocking warning banner advising the user that memory offsets may differ, while allowing all functionality to remain accessible.

---

## 10. Conclusion

MLP Store Suite II demonstrates the efficacy of non-destructive in-memory game manipulation. By combining reverse-engineered controller singletons, cipher key extraction, precise in-place byte patching, and respect for the engine's native town isolation architecture, the tool achieves complete catalog accessibility and purchase reliability with zero disk footprint and zero risk of binary corruption.
