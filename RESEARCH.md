# Reverse-Engineering Technical Report: MLP Store Suite II

**Document Version:** 4.1.0  
**Target Game Client:** *My Little Pony: Magic Princess* (Windows x64 / v11.4.1a, Package Manifest Version: `11.4.0.0`)  
**Binary Analyzed:** `MyLittlePony_x64.exe` (PE64 executable)  
**Security & Reliability Standard:** Enterprise-Hardened In-Memory Injection  

---

## 1. Executive Summary & Problem Statement

In the Windows x64 client of *My Little Pony: Magic Princess*, the game database contains definitions for over 2,380 character entries. However, the vast majority are hidden from the in-game shop rotation. The engine enforces store display through a multi-tiered validation architecture:
1. **Server-Side Store Rotations**: A rotation flag (`b125`) dictates whether an item is eligible for display.
2. **Category Deque Filtration**: An internal queue builder discards items that are not actively flagged in the current rotation.
3. **Shelf Render Culling**: The visual shelf iterator skips non-rotation items during UI layout generation.
4. **ActionScript GUI Dispatch & Purchase Condition Checks**: Clicking an item triggers an ActionScript 3 (AS3) event that passes through multiple native C++ verification gates (`Native_IsActionPossible`, `ShopManager::BuyItem`, currency compatibility, and housing/frame allowances).
5. **Town Section Assignment**: Items are associated with specific town zones (Ponyville, Canterlot, Sweet Apple Acres, Crystal Empire, Klugetown, Everfree Forest).

Previous community efforts to modify the game relied on disk-level file tampering or naive byte patches. These methods encountered major failure modes:
- **Disk Tampering Failures**: Modifying game archives or executable files on disk breaks Windows AppX/GDK digital signatures, triggers package verification crashes, and risks corrupted save states.
- **The "Purchase Freeze" Softlock**: Forcing unlisted items into the store without normalizing their currency references causes the native purchase dispatch function to abort, locking the Scaleform UI in an unhandled modal transaction state.
- **The Cross-Zone Store Clutter**: Naively patching the zone verification routine (`0x6C9600`) forced all 2,380+ ponies into every town store simultaneously, causing severe framerate drops and breaking town boundaries.

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
| `+0x0438` | `uint64_t` | Pointer to the start of the contiguous `ShopItem` array (`start_ptr`). |
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
| `+0x0050` | `float` | **`SortPrice`**: Ordering float used by the shelf layout iterator (must be `>= 1.0f`). |
| `+0x0060 - +0x0070` | `uint32_t[4]` | Encrypted Currency Structure (Gameloft rotating key cipher). |
| `+0x0090 - +0x00A0` | `uint32_t[4]` | Encrypted Price Structure (Gameloft rotating key cipher). |
| `+0x0108` | `uint32_t` | XML Currency Reference Type (`1` = Bits, `2` = Gems). |
| `+0x0125` | `uint8_t` | **`b125`**: Rotation display eligibility flag (`1` = eligible, `0` = hidden). |
| `+0x0126` | `uint8_t` | **`b126`**: Store shelf active enablement flag (`1` = active, `0` = inactive). |

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
       |
       v
Native_IsActionPossible [RVA 0x3665A0] (AS3 Bridge)
       |
       v
ShopItem::GetCurrencyType [RVA 0x6C9630] (Resolves Bits/Gems)
       |
       v
ShopItem::IsItemBuyableInStore [RVA 0x681610] (Price Button State)
       |
       v
Native_BuyItem Dispatcher Debounce [RVA 0x67DFF9]
       |
       v
TownManager::BuyPony Housing Check [RVA 0x67F676]
       |
       v
[Item Added to World / Inventory Placement Mode]
```

### 5.2 The Cause of the Purchase Freeze
Hidden or unlisted items in the game data frequently feature empty, obsolete, or special event currency IDs (e.g. social hearts, special event tokens, or currency `16` / `0`). 

When a player attempts to purchase an item with an unhandled currency:
1. `ShopItem::GetCurrencyType` fails to resolve a standard currency.
2. The engine branches to an unhandled rejection path.
3. However, the Scaleform UI modal has already entered its modal transaction waiting state. Because the native handler neither completed nor threw an explicit user-facing error dialog, the UI thread deadlocks, creating the "Purchase Freeze".

### 5.3 The Dual-Layer Fix
To permanently prevent this freeze, MLP Store Suite II implements a two-pronged solution:
1. **Live Memory Currency Normalization**: During synchronization, the tool inspects every pony item in memory. If an item has an obsolete or zero currency, its currency reference (`+0x108`) and encrypted currency block (`+0x60`) are normalized to Bits (`1`) or Gems (`2`). Furthermore, any zero price is bumped to a nominal positive value (`price >= 1`), satisfying the engine's price checks.
2. **Targeted Engine Hooks**: The 8 in-place master hooks ensure the Scaleform bridge, buyability evaluator, currency resolver, frame debounce check, and housing allowance gate all return valid states.

---

## 6. The Master 8 In-Place Hooks

All 8 hooks are applied in-place in process memory via Win32 `VirtualProtectEx` and `WriteProcessMemory`. No external detours or code caves are required, ensuring maximum stability.

```text
HOOK SUMMARY TABLE (Client v11.4.1a):
+----------------------+-----------+-------------------------------------------------+-------------------------------------------------+
| Identifier           | RVA       | Vanilla Bytes (Hex)                             | Patched Bytes (Hex)                             |
+----------------------+-----------+-------------------------------------------------+-------------------------------------------------+
| HOOK_ROT_SETTER      | 0x1301A47 | 0F 94 C0                                        | B0 01 90                                        |
| HOOK_ROT_BUILDER     | 0x069FFC3 | 74 43                                           | 90 90                                           |
| HOOK_ROT_RENDER      | 0x067C81F | 0F 84 FD 00 00 00                               | 90 90 90 90 90 90                               |
| HOOK_BUYABILITY_ALL  | 0x0681610 | 48 89 5C 24 08                                  | B0 01 C3 90 90                                  |
| HOOK_ACTION_POSSIBLE | 0x03665A0 | 40 57 48 83 EC 50 83 79 20 01                   | 48 8B 09 B2 01 E9 C6 99 89 00                   |
| HOOK_GET_CURRENCY    | 0x06C9630 | 48 83 EC 28 48 8B D1 8B 49 68 33 4A 60 8B 42 6C | 8B 81 08 01 00 00 85 C0 75 05 B8 02 00 00 00 C3 |
| HOOK_BUY_FRAME_CHECK | 0x067DFF9 | 0F 8E AC 01 00 00                               | 90 90 90 90 90 90                               |
| HOOK_BUY_HOUSE_CHECK | 0x067F676 | 0F 94 C3                                        | 31 DB 90                                        |
+----------------------+-----------+-------------------------------------------------+-------------------------------------------------+
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

#### 4. `HOOK_BUYABILITY_ALL` (RVA `0x681610`)
- **Vanilla Instructions**: `mov [rsp + 8], rbx` (5 bytes: `48 89 5C 24 08`)
- **Patched Instructions**: `mov al, 1; ret; nop; nop` (5 bytes: `B0 01 C3 90 90`)
- **Purpose**: Direct function header override for `IsItemBuyableInStore`. Immediately returns `true` (`al = 1`), rendering green price buttons on all store shelf items.

#### 5. `HOOK_ACTION_POSSIBLE` (RVA `0x3665A0`)
- **Vanilla Instructions**: `push rdi; sub rsp, 50h; cmp dword ptr [rcx+20h], 1` (10 bytes: `40 57 48 83 EC 50 83 79 20 01`)
- **Patched Instructions**: `mov rcx, [rcx]; mov dl, 1; jmp 0xbfff70` (10 bytes: `48 8B 09 B2 01 E9 C6 99 89 00`)
- **Purpose**: Overrides `Native_IsActionPossible` in the Scaleform Flash bridge. Ensures click dispatch events on shop purchase buttons are recognized as valid user interactions.

#### 6. `HOOK_GET_CURRENCY` (RVA `0x6C9630`)
- **Vanilla Instructions**: `sub rsp, 28h; mov rdx, rcx; mov ecx, [rcx+68h]; xor ecx, [rdx+60h]; mov eax, [rdx+6Ch]` (16 bytes: `48 83 EC 28 48 8B D1 8B 49 68 33 4A 60 8B 42 6C`)
- **Patched Instructions**: `mov eax, [rcx+108h]; test eax, eax; jne +5; mov eax, 2; ret` (16 bytes: `8B 81 08 01 00 00 85 C0 75 05 B8 02 00 00 00 C3`)
- **Purpose**: Replaces the currency type resolution routine in `ShopItem::GetCurrencyType`. Directly reads the item's XML currency field at `[rcx + 0x108]` and defaults to Gems (`2`) if zero, preventing currency lookup failures.

#### 7. `HOOK_BUY_FRAME_CHECK` (RVA `0x67DFF9`)
- **Vanilla Instructions**: `jle 0x67E1AB` (6 bytes: `0F 8E AC 01 00 00`)
- **Patched Instructions**: `6x nop` (6 bytes: `90 90 90 90 90 90`)
- **Purpose**: Located in `Native_BuyItem` dispatcher. Eliminates frame debounce click dropping, ensuring buy requests trigger reliably.

#### 8. `HOOK_BUY_HOUSE_CHECK` (RVA `0x67F676`)
- **Vanilla Instructions**: `sete bl` (3 bytes: `0F 94 C3`)
- **Patched Instructions**: `xor ebx, ebx; nop` (3 bytes: `31 DB 90`)
- **Purpose**: Guarantees placement allowance into `TownManager::BuyPony` without failing housing or space checks.

---

## 7. Town Store Section Isolation (`0x6C9600`)  -  Architectural Breakthrough

### 7.1 The Pitfall of Legacy Patches
A frequent flaw in earlier modding attempts was hooking `ShopItem::IsAllowedInZone` at RVA `0x6C9600` with:
```x86asm
mov al, 1
ret
```
While this allowed characters to appear, it had a disastrous side effect: **it forced every single pony across all six towns into every single store tab**. The game was forced to render 2,380 visual cards in Ponyville, 2,380 in Canterlot, 2,380 in Sweet Apple Acres, etc.

### 7.2 Disassembly of `ShopItem::IsAllowedInZone`
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
- Applejack, Big Mac, Granny Smith -> Zone 2 (Sweet Apple Acres)
- Twilight Sparkle, Pinkie Pie -> Zone 0 (Ponyville)
- Princess Celestia, Fleur Dis Lee -> Zone 1 (Canterlot)
- Princess Cadance, Shining Armor -> Zone 4 (Crystal Empire)
- Capper, Captain Celaeno -> Zone 6 (Klugetown)
- Zecora -> Zone 3 (Everfree Forest)

### 7.3 Preserving Vanilla Zone Routing
**Leave `0x6C9600` 100% vanilla (`4C 8B 41 40 48...`)**.

By keeping the vanilla routine intact (and actively remediating it via `remediate_stale_stubs` if previous tools had modified it), the engine automatically routes every pony to their native town store section. Ponies appear strictly in their canonical town shops, preserving clean UI layout and pristine game balance.

---

## 8. Security & Hardening Architecture

To address all vulnerabilities and reliability risks identified during security audits, MLP Store Suite II implements enterprise-grade defensive patterns:

### 8.1 Fail-Closed Original-Byte Verification
Before modifying any instruction in memory, the engine reads `len(info["orig"])` bytes from `base + info["rva"]`:
- If `cur == info["patch"]`: Item is already patched.
- If `cur == info["orig"]`: Pristine vanilla instruction confirmed; safe to patch.
- If `cur` matches neither: **Execution is immediately halted**. The tool refuses to write a single byte and returns a detailed signature mismatch error. This guarantees immunity from instruction-offset drift on unverified game builds.

### 8.2 Strict Target Version Gating
The version detection engine inspects package manifests (`appxmanifest.xml` and `MicrosoftGame.config`) and main module memory at RVA `0x154CC30`:
- Tested target: **`11.4.1a`** (Windows Store manifest version: **`11.4.0.0`**).
- Gating strictly rejects unverified builds (`11.4.2`, `11.5.0`, etc.) by default. An explicit override flag (`allow_version_override`) is provided for research environments.

### 8.3 Atomic 5-Phase Transaction Engine & Rollback
Memory patching follows a strict transactional state machine:
1. **Phase 1 (Validate)**: Process identity, module base, version gate, and all 8 instruction signatures are verified.
2. **Phase 2 (Snapshot)**: Current bytes of all hook sites and stubs are saved into an in-memory dictionary.
3. **Phase 3 (Apply)**: Patches are written sequentially using minimal permissions.
4. **Phase 4 (Verify)**: All written addresses are read back and validated against expected patch bytes.
5. **Phase 5 (Rollback)**: If any write or verification step fails, `_rollback_transaction` immediately restores the snapshot bytes.

### 8.4 In-Memory Vanilla Restoration (`unpatch_memory`)
The engine exposes a public unpatch routine:
- Restores all 8 master hook sites back to their pristine `orig` bytes.
- Restores `0x6C9600` (`IsAllowedInZone`) to vanilla.
- Clears live `b125` and `b126` flags across all shop items in RAM.
- Enables switching back to standard vanilla game behavior instantly without restarting the client.

### 8.5 Least-Privilege Win32 Process Handles
Replaces `PROCESS_ALL_ACCESS` (`0x1F0FFF`) with `PROCESS_SAFE_RIGHTS` (`0x0438`):
$$\text{PROCESS\_QUERY\_INFORMATION (0x0400)} \mid \text{PROCESS\_VM\_READ (0x0010)} \mid \text{PROCESS\_VM\_WRITE (0x0020)} \mid \text{PROCESS\_VM\_OPERATION (0x0008)}$$
Restricting permissions minimizes system blast radius and reduces security risk.

### 8.6 Transient Session Token API Authentication
To protect against Cross-Site Request Forgery (CSRF) and DNS rebinding:
- On startup, the server generates a cryptographically random token: `SESSION_TOKEN = secrets.token_hex(16)`.
- The token is dynamically injected into `<meta name="suite-token">` upon serving `index.html`.
- All state-changing `POST` API endpoints require the `X-Suite-Token` HTTP header, verified via constant-time comparison (`secrets.compare_digest`). Requests lacking a valid token are rejected with HTTP 403 Forbidden.
- Wildcard CORS (`Access-Control-Allow-Origin: *`) is completely removed; origins are restricted strictly to localhost.

### 8.7 Path Traversal & Zip Slip Defense
- Static file serving resolves target paths and enforces strict directory boundary verification using both `is_relative_to` and `os.path.commonpath`. Requests for `.py`, `.zip`, `.7z`, and hidden files (`.*`) are blocked.
- Portrait asset extraction in `ensure_assets` validates every archive member path to ensure it cannot escape the destination directory and restricts unpacked file types strictly to `.png`.

---

## 9. Guide for Future Researchers, Modders, and AI Agents

When analyzing new updates to *My Little Pony: Magic Princess*, use this checklist to locate shifted RVAs:

1. **Locating `ShopManager`**:
   - Search memory for the string `Pony_Twilight_Sparkle` or `Pony_Applejack`.
   - Find references to the item metadata structure. The array pointer is held at `[ShopManager + 0x438]`.
   - Trace backwards to find the static pointer reference at `[base + OFFSET_SHOP_CONTROLLER]`.

2. **Locating `IsAllowedInZone` (`0x6C9600`)**:
   - Signature pattern: `4C 8B 41 40 48 8B 49 38 49 3B C8 74 15`
   - Disassembly: Vector comparison of allowed zones against input `edx`.

3. **Locating `IsItemBuyableInStore` (`0x681610`)**:
   - Trace the function called when populating the green price button text in the shop shelf UI.
   - Look for `mov [rsp + 8], rbx` in the function prologue.

4. **Locating Currency Resolver (`0x6C9630`)**:
   - Located immediately following `IsAllowedInZone`.
   - Reads `[rcx + 0x108]` (XML currency reference).

5. **Cipher Rotations**:
   - Gameloft's rotating salt cipher consistently uses 5-bit rotations (`ror 5` / `rol 5`). If a future client changes the shift count, test mathematical invertibility across wallet values in `PlayerManager`.

---

## 10. Conclusion

MLP Store Suite II demonstrates that reverse engineering and in-memory manipulation can be combined with modern defensive software design. By pairing deep disassembly analysis and cipher reconstruction with strict fail-closed signature verification, transactional rollback, least-privilege Win32 handles, and tokenized API isolation, the suite provides a stable, resilient, and safe modding platform.
