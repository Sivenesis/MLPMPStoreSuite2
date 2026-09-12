import ctypes
from ctypes import wintypes
import os
import sys
import time
import struct
import json
import threading
import re
from typing import Optional, Dict, Any, List, Tuple

# Win32 Constants
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_VM_OPERATION = 0x0008
PROCESS_ALL_ACCESS = 0x1F0FFF

PAGE_EXECUTE_READWRITE = 0x40

TH32CS_SNAPPROCESS = 0x00000002

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260),
    ]

# Win32 APIs
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

OpenProcess = kernel32.OpenProcess
OpenProcess.restype = wintypes.HANDLE
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

CloseHandle = kernel32.CloseHandle
CloseHandle.restype = wintypes.BOOL
CloseHandle.argtypes = [wintypes.HANDLE]

CreateToolhelp32Snapshot = kernel32.CreateToolhelp32Snapshot
CreateToolhelp32Snapshot.restype = wintypes.HANDLE
CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]

Process32First = kernel32.Process32First
Process32First.restype = wintypes.BOOL
Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]

Process32Next = kernel32.Process32Next
Process32Next.restype = wintypes.BOOL
Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32)]

VirtualProtectEx = kernel32.VirtualProtectEx
VirtualProtectEx.restype = wintypes.BOOL
VirtualProtectEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_size_t,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
]

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.restype = wintypes.BOOL
ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]

WriteProcessMemory = kernel32.WriteProcessMemory
WriteProcessMemory.restype = wintypes.BOOL
WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]

def ror32(val: int, r: int) -> int:
    """Performs 32-bit right rotate."""
    return ((val >> r) | ((val << (32 - r)) & 0xFFFFFFFF)) & 0xFFFFFFFF

def rol32(val: int, r: int) -> int:
    """Performs 32-bit left rotate."""
    return ((val << r) | (val >> (32 - r))) & 0xFFFFFFFF


class MemoryPatcher:
    """
    MLP Store Suite 2: High-Performance In-Memory Store Patcher & Purchase Enabler.
    Strictly zero-disk footprint (no files modified on disk).
    Preserves 100% vanilla MapZone assignments and UnlockValue level requirements.
    Enforces strict town isolation so ponies appear exclusively in their home town store sections.
    """

    VERSION = "v4.0.0"
    GAME_VERSION = "11.4.1a"
    TARGET_PROCESS_NAME = "MyLittlePony_x64.exe"

    # Static RVAs for Game Engine Controllers
    OFFSET_SHOP_CONTROLLER = 0x67E21A + 7 + 0x140951F     # base + 0x1A87740 (ShopManager*)
    OFFSET_PLAYER_CONTROLLER = 0x5AA5D4 + 7 + 0x14DB905   # base + 0x1A85EE0 (PlayerManager*)
    OFFSET_TOWN_CONTROLLER = 0x635DC4 + 7 + 0x145101D     # base + 0x1A86DE8 (TownManager*)

    # Master In-Place Engine Patches (8 targeted hooks; 0x6C9600 preserved as pure vanilla)
    PATCHES = {
        "HOOK_ROT_SETTER": {
            "name": "Rotation Setter",
            "desc": "Forces b125=1 in engine XML parser",
            "rva": 0x1301A47,
            "orig": b'\x0f\x94\xc0',                 # sete al (3 bytes)
            "patch": b'\xb0\x01\x90',                # mov al, 1; nop (3 bytes)
        },
        "HOOK_ROT_BUILDER": {
            "name": "Category Deque Builder",
            "desc": "Prevents category deque from skipping unlisted items",
            "rva": 0x69FFC3,
            "orig": b'\x74\x43',                    # je 0x6a0008 (2 bytes)
            "patch": b'\x90\x90',                   # 2x NOP
        },
        "HOOK_ROT_RENDER": {
            "name": "Shelf Render Iterator",
            "desc": "Prevents shelf layout render iterator from dropping unlisted items",
            "rva": 0x67C81F,
            "orig": b'\x0f\x84\xfd\x00\x00\x00',     # je 0x67C922 (6 bytes)
            "patch": b'\x90\x90\x90\x90\x90\x90',    # 6x NOP
        },
        "HOOK_BUYABILITY_ALL": {
            "name": "Buyability Enabler",
            "desc": "Forces IsItemBuyableInStore to return true (green price buttons)",
            "rva": 0x681610,
            "orig": b'\x48\x89\x5c\x24\x08',         # mov [rsp + 8], rbx (5 bytes)
            "patch": b'\xb0\x01\xc3\x90\x90',        # mov al, 1; ret; nop; nop (5 bytes)
        },
        "HOOK_ACTION_POSSIBLE": {
            "name": "Scaleform Flash Action Gate",
            "desc": "Forces Native_IsActionPossible to return true, enabling onBuy clicks",
            "rva": 0x3665A0,
            "orig": b'\x40\x57\x48\x83\xec\x50\x83\x79\x20\x01', # push rdi; sub rsp, 50h; ... (10 bytes)
            "patch": b'\x48\x8b\x09\xb2\x01\xe9\xc6\x99\x89\x00', # mov rcx, [rcx]; mov dl, 1; jmp 0xbfff70
        },
        "HOOK_GET_CURRENCY": {
            "name": "Currency Type Resolver",
            "desc": "Forces ShopItem::GetCurrencyType to return valid XML currency (Bits/Gems)",
            "rva": 0x6C9630,
            "orig": b'\x48\x83\xec\x28\x48\x8b\xd1\x8b\x49\x68\x33\x4a\x60\x8b\x42\x6c', # 16 bytes
            "patch": b'\x8b\x81\x08\x01\x00\x00\x85\xc0\x75\x05\xb8\x02\x00\x00\x00\xc3', # mov eax, [rcx+108h]; test eax, eax; jne +5; mov eax, 2; ret
        },
        "HOOK_BUY_FRAME_CHECK": {
            "name": "Dispatcher Frame Debounce",
            "desc": "Eliminates debounce frame click dropping in Native_BuyItem dispatcher",
            "rva": 0x67DFF9,
            "orig": b'\x0f\x8e\xac\x01\x00\x00',     # jle 0x67e1ab (6 bytes)
            "patch": b'\x90\x90\x90\x90\x90\x90',    # 6x NOP
        },
        "HOOK_BUY_HOUSE_CHECK": {
            "name": "Housing Space Allowance",
            "desc": "Guarantees placement allowance into TownManager::BuyPony",
            "rva": 0x67F676,
            "orig": b'\x0f\x94\xc3',                 # sete bl (3 bytes)
            "patch": b'\x31\xdb\x90',                # xor ebx, ebx; nop (3 bytes)
        },
    }

    # Pristine vanilla bytes for 0x6C9600 (IsAllowedInZone)
    VANILLA_ZONE_BYTES = b'\x4c\x8b\x41\x40\x48'

    def __init__(self):
        self.auto_watch_enabled = False
        self._watch_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._log_history: List[Dict[str, Any]] = []
        self._max_logs = 500

        # Dedicated project folder logging
        self.logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
        os.makedirs(self.logs_dir, exist_ok=True)
        self.log_file_path = os.path.join(self.logs_dir, "suite_debug.log")

        self.offline_mode: bool = True
        self.custom_selection: Optional[set] = None
        self._item_id_cache: Dict[int, str] = {}
        self.data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
        os.makedirs(self.data_dir, exist_ok=True)

        self.last_patch_result: Dict[str, Any] = {
            "success": False,
            "message": "No patch operation performed yet.",
            "timestamp": None,
            "pid": None,
            "base": None,
            "hooks_applied": 0,
            "hooks_total": len(self.PATCHES),
            "synced_items": 0,
            "currencies_fixed": 0,
            "prices_fixed": 0,
        }
        self.log("INIT", f"MLPStoreSuite2 Memory Engine {self.VERSION} (Game Client v{self.GAME_VERSION}) initialized.")

    def log(self, level: str, message: str):
        """Appends a timestamped log entry to memory buffer, terminal, and suite_debug.log."""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        time_short = time.strftime("%H:%M:%S")
        entry = {
            "timestamp": time_short,
            "level": level.upper(),
            "message": message,
        }
        with self._lock:
            self._log_history.append(entry)
            if len(self._log_history) > self._max_logs:
                self._log_history.pop(0)
            try:
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(f"[{now_str}] [{level.upper():7s}] {message}\n")
            except Exception:
                pass
        print(f"[{entry['timestamp']}] [{entry['level']}] {entry['message']}")

    def get_logs(self) -> List[Dict[str, Any]]:
        """Returns a copy of the log history."""
        with self._lock:
            return list(self._log_history)

    def clear_logs(self):
        """Clears the in-memory log buffer."""
        with self._lock:
            self._log_history.clear()
            self._log_history.append({
                "timestamp": time.strftime("%H:%M:%S"),
                "level": "INFO",
                "message": "Log buffer cleared.",
            })

    def find_process(self) -> Optional[int]:
        """Finds target PID using Win32 Toolhelp32."""
        try:
            h_snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if not h_snap or h_snap == ctypes.c_void_p(-1).value:
                return None
            pe = PROCESSENTRY32()
            pe.dwSize = ctypes.sizeof(PROCESSENTRY32)
            target = self.TARGET_PROCESS_NAME.lower()
            if Process32First(h_snap, ctypes.byref(pe)):
                while True:
                    exe_name = pe.szExeFile.decode("latin-1", errors="ignore").rstrip("\x00")
                    if exe_name.lower() == target:
                        pid = pe.th32ProcessID
                        CloseHandle(h_snap)
                        return pid
                    if not Process32Next(h_snap, ctypes.byref(pe)):
                        break
            CloseHandle(h_snap)
        except Exception as ex:
            self.log("ERROR", f"find_process exception: {ex}")
        return None

    def get_main_module_base(self, h_process: wintypes.HANDLE) -> Optional[int]:
        """Retrieves module base address of MyLittlePony_x64.exe."""
        hmods = (ctypes.c_void_p * 1024)()
        cb_needed = wintypes.DWORD()
        if psapi.EnumProcessModules(h_process, hmods, ctypes.sizeof(hmods), ctypes.byref(cb_needed)):
            return hmods[0]
        return None

    def _read_bytes(self, h_process: wintypes.HANDLE, address: int, length: int) -> Optional[bytes]:
        """Reads raw bytes from process memory."""
        buf = ctypes.create_string_buffer(length)
        read = ctypes.c_size_t()
        if ReadProcessMemory(h_process, ctypes.c_void_p(address), buf, length, ctypes.byref(read)):
            return buf.raw[:read.value]
        return None

    def _write_bytes(self, h_process: wintypes.HANDLE, address: int, data: bytes) -> bool:
        """Writes raw bytes to executable memory using VirtualProtectEx."""
        old_protect = wintypes.DWORD()
        written = ctypes.c_size_t()
        length = len(data)
        if not VirtualProtectEx(h_process, ctypes.c_void_p(address), length, PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect)):
            return False
        ok = WriteProcessMemory(h_process, ctypes.c_void_p(address), data, length, ctypes.byref(written))
        VirtualProtectEx(h_process, ctypes.c_void_p(address), length, old_protect.value, ctypes.byref(old_protect))
        return bool(ok and written.value == length)

    def remediate_stale_stubs(self, h_process: wintypes.HANDLE, base_addr: int):
        """Remediates legacy detour or cross-zone corruption stubs back to pristine vanilla."""
        # 1. Stale SortPrice hook at 0x68CD91 (must be movss [r12 + 50h], xmm6)
        sp_bytes = self._read_bytes(h_process, base_addr + 0x68CD91, 7)
        if sp_bytes and sp_bytes[0] == 0xE9:
            vanilla_sp = b'\xf3\x41\x0f\x11\x74\x24\x50'
            self._write_bytes(h_process, base_addr + 0x68CD91, vanilla_sp)
            self.log("HOOK", "Remediated legacy detour stub at 0x68CD91 back to pristine vanilla movss.")

        # 2. Stale CanPlace hook at 0x630290 (must be mov [rsp+8], rbx)
        cp_bytes = self._read_bytes(h_process, base_addr + 0x630290, 5)
        if cp_bytes and cp_bytes[:3] == b'\xb0\x01\xc3':
            vanilla_cp = b'\x48\x89\x5c\x24\x08'
            self._write_bytes(h_process, base_addr + 0x630290, vanilla_cp)
            self.log("HOOK", "Remediated legacy stub at 0x630290 back to pristine vanilla mov.")

        # 3. Restore IsAllowedInZone at 0x6C9600 to pure vanilla to enforce town store isolation
        zone_bytes = self._read_bytes(h_process, base_addr + 0x6C9600, 5)
        if zone_bytes and zone_bytes != self.VANILLA_ZONE_BYTES:
            self._write_bytes(h_process, base_addr + 0x6C9600, self.VANILLA_ZONE_BYTES)
            self.log("HOOK", "Restored 0x6C9600 to pristine vanilla. Town store section isolation ENFORCED.")

    def _get_item_id(self, h_process: wintypes.HANDLE, arr_buf: bytes, off: int, index: int) -> str:
        """Retrieves and caches internal item identifier string."""
        if index in self._item_id_cache:
            return self._item_id_cache[index]

        intern_ptr = struct.unpack("<Q", arr_buf[off + 0x18:off + 0x20])[0]
        if intern_ptr:
            s_ptr_buf = self._read_bytes(h_process, intern_ptr + 8, 8)
            if s_ptr_buf:
                s_ptr = struct.unpack("<Q", s_ptr_buf)[0]
                if s_ptr:
                    name_b = self._read_bytes(h_process, s_ptr, 64)
                    if name_b:
                        clean_id = name_b.split(b"\x00")[0].decode("latin-1", errors="ignore")
                        self._item_id_cache[index] = clean_id
                        return clean_id
        return ""

    def sync_live_shop_items(self, h_process: wintypes.HANDLE, base_addr: int) -> Tuple[int, int, int]:
        """
        Synchronizes live shop array items in RAM.
        Supports custom user selection:
        - If custom_selection is active: enables selected ponies (b125=1, b126=1) and hides unselected ones (b125=0, b126=0).
        - If custom_selection is None: enables all items.
        - Enforces runtime currency (Bits/Gems) and price normalization for all items so any pony in store is purchasable.
        """
        ctrl_buf = self._read_bytes(h_process, base_addr + self.OFFSET_SHOP_CONTROLLER, 8)
        if not ctrl_buf:
            return 0, 0, 0
        ctrl_addr = struct.unpack("<Q", ctrl_buf)[0]
        if not ctrl_addr:
            return 0, 0, 0

        hdr_buf = self._read_bytes(h_process, ctrl_addr, 0x500)
        if not hdr_buf:
            return 0, 0, 0

        start_ptr = struct.unpack("<Q", hdr_buf[0x438:0x440])[0]
        end_ptr = struct.unpack("<Q", hdr_buf[0x440:0x448])[0]
        stride = 0x158

        if not start_ptr or not end_ptr or end_ptr <= start_ptr:
            return 0, 0, 0

        total_items = (end_ptr - start_ptr) // stride
        if total_items <= 0 or total_items > 20000:
            return 0, 0, 0

        arr_buf = self._read_bytes(h_process, start_ptr, total_items * stride)
        if not arr_buf:
            return 0, 0, 0

        one_byte = b'\x01'
        zero_byte = b'\x00'
        one_float = struct.pack("<f", 1.0)
        updated = 0
        currencies_fixed = 0
        prices_fixed = 0
        written = ctypes.c_size_t()

        for i in range(total_items):
            off = i * stride
            item_addr = start_ptr + off
            cat = struct.unpack("<I", arr_buf[off + 8:off + 12])[0]

            if cat == 0x39:
                pony_id = self._get_item_id(h_process, arr_buf, off, i)
                should_be_active = True
                if self.custom_selection is not None:
                    should_be_active = (pony_id in self.custom_selection)

                if should_be_active:
                    # 1. Force b125 = 1 (active in store)
                    if arr_buf[off + 0x125] == 0:
                        if WriteProcessMemory(h_process, ctypes.c_void_p(item_addr + 0x125), one_byte, 1, ctypes.byref(written)):
                            updated += 1

                    # 2. Force b126 = 1 (rotation active)
                    if arr_buf[off + 0x126] == 0:
                        WriteProcessMemory(h_process, ctypes.c_void_p(item_addr + 0x126), one_byte, 1, ctypes.byref(written))

                    # 3. Elevate SortPrice to 1.0f ONLY IF it was <= 0.0f
                    sp = struct.unpack("<f", arr_buf[off + 0x50:off + 0x54])[0]
                    if sp <= 0.0:
                        if WriteProcessMemory(h_process, ctypes.c_void_p(item_addr + 0x50), one_float, 4, ctypes.byref(written)):
                            updated += 1
                else:
                    # Hide from store shelf
                    if arr_buf[off + 0x125] != 0:
                        if WriteProcessMemory(h_process, ctypes.c_void_p(item_addr + 0x125), zero_byte, 1, ctypes.byref(written)):
                            updated += 1
                    if arr_buf[off + 0x126] != 0:
                        WriteProcessMemory(h_process, ctypes.c_void_p(item_addr + 0x126), zero_byte, 1, ctypes.byref(written))
            else:
                # Non-pony item (shops, decor, etc.)
                if arr_buf[off + 0x125] == 0:
                    if WriteProcessMemory(h_process, ctypes.c_void_p(item_addr + 0x125), one_byte, 1, ctypes.byref(written)):
                        updated += 1

                if arr_buf[off + 0x126] == 0:
                    WriteProcessMemory(h_process, ctypes.c_void_p(item_addr + 0x126), one_byte, 1, ctypes.byref(written))

                sp = struct.unpack("<f", arr_buf[off + 0x50:off + 0x54])[0]
                if sp <= 0.0:
                    if WriteProcessMemory(h_process, ctypes.c_void_p(item_addr + 0x50), one_float, 4, ctypes.byref(written)):
                        updated += 1

            # 4. Normalize and encrypt runtime currency for purchase execution
            c60, c64, c68, c6c = struct.unpack("<4I", arr_buf[off + 0x60:off + 0x70])
            curr = ror32(c68 ^ c60, 5)
            xml_curr = struct.unpack("<I", arr_buf[off + 0x108:off + 0x10C])[0]
            if curr == 16 or curr not in (1, 2, 3, 12):
                target_curr = xml_curr if xml_curr in (1, 2, 3, 12) else 2
                val = rol32(target_curr, 5)
                new_c68 = c60 ^ val
                new_c6c = c64 ^ val
                curr_bytes = struct.pack("<2I", new_c68, new_c6c)
                if WriteProcessMemory(h_process, ctypes.c_void_p(item_addr + 0x68), curr_bytes, 8, ctypes.byref(written)):
                    currencies_fixed += 1

            # 5. Ensure non-zero price for ponies so purchase checks never abort on zero
            if cat == 0x39:
                p90, p94, p98, p9c = struct.unpack("<4I", arr_buf[off + 0x90:off + 0xA0])
                price = ror32(p98 ^ p90, 5)
                if price == 0:
                    target_price = 100 if xml_curr == 1 else 50
                    pval = rol32(target_price, 5)
                    new_p98 = p90 ^ pval
                    new_p9c = p94 ^ pval
                    price_bytes = struct.pack("<2I", new_p98, new_p9c)
                    if WriteProcessMemory(h_process, ctypes.c_void_p(item_addr + 0x98), price_bytes, 8, ctypes.byref(written)):
                        prices_fixed += 1

        return updated, currencies_fixed, prices_fixed

    def get_game_telemetry(self, h_process: wintypes.HANDLE, base_addr: int) -> Dict[str, Any]:
        """Reads live player currency, town zone, store section, and shop statistics from engine memory."""
        zone_map = {
            0: "Ponyville",
            1: "Canterlot",
            2: "Sweet Apple Acres",
            3: "Everfree Forest",
            4: "Crystal Empire",
            5: "Changeling Kingdom",
            6: "Klugetown",
        }

        telemetry = {
            "bits": None,
            "gems": None,
            "current_zone": None,
            "zone_name": "Unknown",
            "shop_category_zone": None,
            "shop_category_zone_name": "Unknown",
            "pending_item": None,
            "zone_isolation_status": "ACTIVE (Vanilla Town Isolation Enforced)",
            "shop_items_total": 0,
            "shop_manager_addr": None,
            "town_manager_addr": None,
            "player_manager_addr": None,
        }

        # 1. Read PlayerManager
        pm_buf = self._read_bytes(h_process, base_addr + self.OFFSET_PLAYER_CONTROLLER, 8)
        if pm_buf:
            pm_addr = struct.unpack("<Q", pm_buf)[0]
            telemetry["player_manager_addr"] = f"0x{pm_addr:X}" if pm_addr else None
            if pm_addr:
                p_data = self._read_bytes(h_process, pm_addr, 0x500)
                if p_data:
                    b444, b448, b44c, b450 = struct.unpack("<4I", p_data[0x444:0x454])
                    bits = ror32(b44c ^ b444, 5)
                    g458, g45c, g460, g464 = struct.unpack("<4I", p_data[0x458:0x468])
                    gems = ror32(g460 ^ g458, 5)
                    telemetry["bits"] = bits
                    telemetry["gems"] = gems

        # 2. Read TownManager & Current Zone
        tm_buf = self._read_bytes(h_process, base_addr + self.OFFSET_TOWN_CONTROLLER, 8)
        if tm_buf:
            tm_addr = struct.unpack("<Q", tm_buf)[0]
            telemetry["town_manager_addr"] = f"0x{tm_addr:X}" if tm_addr else None
            if tm_addr:
                z_buf = self._read_bytes(h_process, tm_addr + 0x20, 4)
                if z_buf:
                    zone_id = struct.unpack("<I", z_buf)[0]
                    telemetry["current_zone"] = zone_id
                    telemetry["zone_name"] = zone_map.get(zone_id, f"Zone {zone_id}")

        # 3. Read ShopManager item count, store category zone, and pending item
        sm_buf = self._read_bytes(h_process, base_addr + self.OFFSET_SHOP_CONTROLLER, 8)
        if sm_buf:
            sm_addr = struct.unpack("<Q", sm_buf)[0]
            telemetry["shop_manager_addr"] = f"0x{sm_addr:X}" if sm_addr else None
            if sm_addr:
                sm_hdr = self._read_bytes(h_process, sm_addr, 0x500)
                if sm_hdr:
                    total_items = struct.unpack("<I", sm_hdr[0x450:0x454])[0]
                    shop_zone = struct.unpack("<I", sm_hdr[0x454:0x458])[0]
                    telemetry["shop_items_total"] = total_items
                    telemetry["shop_category_zone"] = shop_zone
                    telemetry["shop_category_zone_name"] = zone_map.get(shop_zone, f"Zone {shop_zone}")

                    # Read pending item string at [sm_addr + 0x28]
                    pending_ptr = struct.unpack("<Q", sm_hdr[0x28:0x30])[0]
                    if pending_ptr:
                        s_ptr = struct.unpack("<Q", self._read_bytes(h_process, pending_ptr + 8, 8))[0]
                        if s_ptr:
                            name_b = self._read_bytes(h_process, s_ptr, 64)
                            if name_b:
                                telemetry["pending_item"] = name_b.split(b"\x00")[0].decode("latin-1", errors="ignore")

        return telemetry

    def detect_game_version(self, h_process: Optional[wintypes.HANDLE] = None, base_addr: Optional[int] = None) -> Dict[str, Any]:
        """
        Detects game client version from live process memory and package configuration.
        Compares with target version (11.4.1a).
        """
        detected_version = None
        source = None

        if h_process:
            # 1. Attempt dynamic query of process executable path
            try:
                buf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if ctypes.windll.kernel32.QueryFullProcessImageNameW(h_process, 0, buf, ctypes.byref(size)):
                    exe_path = buf.value
                    game_dir = os.path.dirname(exe_path)
                    for manifest_name in ["appxmanifest.xml", "MicrosoftGame.config"]:
                        m_path = os.path.join(game_dir, manifest_name)
                        if os.path.exists(m_path):
                            try:
                                with open(m_path, "r", encoding="utf-8", errors="ignore") as f:
                                    content = f.read()
                                m = re.search(r'Version="([^"]+)"', content)
                                if m:
                                    detected_version = m.group(1)
                                    source = manifest_name
                                    break
                            except Exception:
                                pass
            except Exception:
                pass

            # 2. Check Crashlytics/version string in main module memory at RVA 0x154CC30
            if base_addr:
                try:
                    ver_buf = self._read_bytes(h_process, base_addr + 0x154CC30, 32)
                    if ver_buf:
                        ver_str = ver_buf.split(b"\x00")[0].decode("latin-1", errors="ignore").strip()
                        if ver_str and re.match(r'^\d+\.\d+', ver_str):
                            if not detected_version:
                                detected_version = ver_str
                                source = "Main Module RAM"
                except Exception:
                    pass

        # Target matching: Windows package version "11.4.0.0", internal "11.4.0" / "11.4.0m", or release "11.4.1a"
        is_matched = True
        warning = None
        if detected_version:
            if detected_version.startswith("11.4.") or detected_version in ("11.4.1a", "11.4.0", "11.4.0.0"):
                is_matched = True
            else:
                is_matched = False
                warning = f"Game client version mismatch: Detected {detected_version}, but tool is tested for v{self.GAME_VERSION}. Some memory offsets may differ."

        return {
            "target": self.GAME_VERSION,
            "detected": detected_version,
            "matched": is_matched,
            "warning": warning,
            "source": source
        }

    def get_status(self) -> Dict[str, Any]:
        """Retrieves comprehensive live status of game process, hooks, and telemetry."""
        pid = self.find_process()
        hook_statuses = {}
        all_active = False
        base_addr = None
        game_telemetry = {}

        version_check = {
            "target": self.GAME_VERSION,
            "detected": None,
            "matched": True,
            "warning": None,
            "source": None
        }

        if pid:
            h_process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if h_process:
                try:
                    base_addr = self.get_main_module_base(h_process)
                    if base_addr:
                        active_count = 0
                        for key, info in self.PATCHES.items():
                            cur = self._read_bytes(h_process, base_addr + info["rva"], len(info["patch"]))
                            is_patched = (cur == info["patch"])
                            if is_patched:
                                active_count += 1
                            hook_statuses[key] = {
                                "name": info["name"],
                                "desc": info["desc"],
                                "rva": f"0x{info['rva']:X}",
                                "active": is_patched,
                            }
                        all_active = (active_count == len(self.PATCHES))
                        game_telemetry = self.get_game_telemetry(h_process, base_addr)
                        version_check = self.detect_game_version(h_process, base_addr)
                finally:
                    CloseHandle(h_process)

        return {
            "version": self.VERSION,
            "suite_version": self.VERSION,
            "game_version": self.GAME_VERSION,
            "target_process": self.TARGET_PROCESS_NAME,
            "is_running": pid is not None,
            "pid": pid,
            "base_address": f"0x{base_addr:X}" if base_addr else None,
            "all_hooks_active": all_active,
            "auto_watch": self.auto_watch_enabled,
            "offline_mode": True,
            "custom_selection_active": self.custom_selection is not None,
            "custom_selection_count": len(self.custom_selection) if self.custom_selection is not None else 2381,
            "hooks": hook_statuses,
            "telemetry": game_telemetry,
            "version_check": version_check,
            "last_result": self.last_patch_result,
            "log_file": "logs/suite_debug.log",
        }

    def patch_memory(self) -> Dict[str, Any]:
        """
        Executes complete in-memory patching & array synchronization:
        1. Remediates legacy stubs & restores 0x6C9600 to pristine vanilla.
        2. Applies all 8 master in-place hooks.
        3. Synchronizes live ShopManager array: b125=1, b126=1, SortPrice>=1.0, encrypts runtime currencies.
        """
        pid = self.find_process()
        if not pid:
            msg = f"{self.TARGET_PROCESS_NAME} is not running. Launch the game first."
            self.log("ERROR", msg)
            res = {
                "success": False,
                "message": msg,
                "timestamp": time.strftime("%H:%M:%S"),
                "pid": None,
                "base": None,
                "hooks_applied": 0,
                "synced_items": 0,
                "currencies_fixed": 0,
                "prices_fixed": 0,
            }
            self.last_patch_result = res
            return res

        h_process = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h_process:
            err = ctypes.get_last_error()
            msg = f"Failed to open process PID {pid} (Win32 Error: {err}). Run with Admin privileges if needed."
            self.log("ERROR", msg)
            res = {
                "success": False,
                "message": msg,
                "timestamp": time.strftime("%H:%M:%S"),
                "pid": pid,
                "base": None,
                "hooks_applied": 0,
                "synced_items": 0,
                "currencies_fixed": 0,
                "prices_fixed": 0,
            }
            self.last_patch_result = res
            return res

        try:
            base_addr = self.get_main_module_base(h_process)
            if not base_addr:
                msg = f"Failed to retrieve main module base address for PID {pid}."
                self.log("ERROR", msg)
                res = {
                    "success": False,
                    "message": msg,
                    "timestamp": time.strftime("%H:%M:%S"),
                    "pid": pid,
                    "base": None,
                    "hooks_applied": 0,
                    "synced_items": 0,
                    "currencies_fixed": 0,
                    "prices_fixed": 0,
                }
                self.last_patch_result = res
                return res

            self.log("INFO", f"Connected to {self.TARGET_PROCESS_NAME} (PID {pid}) at Module Base 0x{base_addr:X}.")

            # 1. Remediate legacy stubs & restore 0x6C9600 to pure vanilla
            self.remediate_stale_stubs(h_process, base_addr)

            # 2. Apply all 8 master in-place hooks
            applied = 0
            for key, info in self.PATCHES.items():
                addr = base_addr + info["rva"]
                cur_bytes = self._read_bytes(h_process, addr, len(info["patch"]))
                if cur_bytes == info["patch"]:
                    applied += 1
                    continue

                if self._write_bytes(h_process, addr, info["patch"]):
                    applied += 1
                    self.log("HOOK", f"Installed {info['name']} at 0x{info['rva']:X} (OK).")
                else:
                    err = ctypes.get_last_error()
                    self.log("ERROR", f"Failed to write patch {info['name']} at 0x{info['rva']:X} (Error {err}).")

            # 3. Synchronize live ShopManager array & currencies
            synced, currencies_fixed, prices_fixed = self.sync_live_shop_items(h_process, base_addr)
            self.log("SYNC", f"Live array sync: {synced} items elevated, {currencies_fixed} currencies normalized, {prices_fixed} prices set.")

            # 4. Read updated game telemetry
            telemetry = self.get_game_telemetry(h_process, base_addr)
            if telemetry.get("bits") is not None and telemetry.get("gems") is not None:
                self.log("INFO", f"Game State: Town={telemetry['zone_name']}, StoreTab={telemetry['shop_category_zone_name']}, Bits={telemetry['bits']:,}, Gems={telemetry['gems']:,}")

            all_ok = (applied == len(self.PATCHES))
            status_msg = (
                f"Patch Complete: {applied}/{len(self.PATCHES)} hooks verified active. "
                f"{synced} items synchronized. {currencies_fixed} currencies normalized. "
                f"Town store section isolation ENFORCED. All ponies buyable in their native towns."
            )
            self.log("SUCCESS" if all_ok else "WARN", status_msg)

            res = {
                "success": all_ok,
                "message": status_msg,
                "timestamp": time.strftime("%H:%M:%S"),
                "pid": pid,
                "base": f"0x{base_addr:X}",
                "hooks_applied": applied,
                "hooks_total": len(self.PATCHES),
                "synced_items": synced,
                "currencies_fixed": currencies_fixed,
                "prices_fixed": prices_fixed,
                "telemetry": telemetry,
            }
            self.last_patch_result = res
            return res

        finally:
            CloseHandle(h_process)

    def export_diagnostic_report(self) -> Dict[str, Any]:
        """
        Generates an exhaustive diagnostic report and saves it to logs/diagnostic_report.json and .txt.
        Provides full visibility into game process memory, hooks, currencies, and town isolation.
        """
        status = self.get_status()
        pid = self.find_process()
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "suite_version": self.VERSION,
            "status": status,
            "ponies_summary": {},
        }

        if pid:
            h_process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if h_process:
                try:
                    base_addr = self.get_main_module_base(h_process)
                    if base_addr:
                        ctrl_buf = self._read_bytes(h_process, base_addr + self.OFFSET_SHOP_CONTROLLER, 8)
                        if ctrl_buf:
                            ctrl_addr = struct.unpack("<Q", ctrl_buf)[0]
                            hdr_buf = self._read_bytes(h_process, ctrl_addr, 0x500)
                            start_ptr = struct.unpack("<Q", hdr_buf[0x438:0x440])[0]
                            end_ptr = struct.unpack("<Q", hdr_buf[0x440:0x448])[0]
                            stride = 0x158
                            total = (end_ptr - start_ptr) // stride

                            curr_dist = {}
                            sample_ponies = []
                            for i in range(total):
                                off = i * stride
                                data = self._read_bytes(h_process, start_ptr + off, stride)
                                cat = struct.unpack("<I", data[8:12])[0]
                                if cat != 0x39:
                                    continue
                                c60, c64, c68, c6c = struct.unpack("<4I", data[0x60:0x70])
                                curr = ror32(c68 ^ c60, 5)
                                curr_dist[curr] = curr_dist.get(curr, 0) + 1
                                if len(sample_ponies) < 15:
                                    intern_ptr = struct.unpack("<Q", data[0x18:0x20])[0]
                                    s_ptr = struct.unpack("<Q", self._read_bytes(h_process, intern_ptr + 8, 8))[0]
                                    name = self._read_bytes(h_process, s_ptr, 64).split(b"\x00")[0].decode("latin-1", errors="ignore")
                                    p90, p94, p98, p9c = struct.unpack("<4I", data[0x90:0xA0])
                                    price = ror32(p98 ^ p90, 5)
                                    xml_curr = struct.unpack("<I", data[0x108:0x10C])[0]
                                    sample_ponies.append({"name": name, "curr": curr, "xml_curr": xml_curr, "price": price})

                            report["ponies_summary"] = {
                                "currency_distribution": curr_dist,
                                "samples": sample_ponies,
                            }
                finally:
                    CloseHandle(h_process)

        # Write JSON report
        json_path = os.path.join(self.logs_dir, "diagnostic_report.json")
        txt_path = os.path.join(self.logs_dir, "diagnostic_report.txt")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"=== MLP STORE SUITE 2 DIAGNOSTIC REPORT ({report['timestamp']}) ===\n")
                f.write(f"Suite Version: {self.VERSION}\n")
                f.write(f"Process: {self.TARGET_PROCESS_NAME} (PID {status['pid']})\n")
                f.write(f"Base Address: {status['base_address']}\n")
                f.write(f"Hooks Active: {status['all_hooks_active']} ({sum(1 for h in status['hooks'].values() if h['active'])}/{len(status['hooks'])})\n")
                f.write(f"Town Zone: {status.get('telemetry', {}).get('zone_name')} (ID: {status.get('telemetry', {}).get('current_zone')})\n")
                f.write(f"Store Section: {status.get('telemetry', {}).get('shop_category_zone_name')}\n")
                f.write(f"Bits: {status.get('telemetry', {}).get('bits'):,} | Gems: {status.get('telemetry', {}).get('gems'):,}\n")
                f.write(f"Town Isolation: {status.get('telemetry', {}).get('zone_isolation_status')}\n\n")
                f.write("--- HOOK STATUSES ---\n")
                for k, h in status.get("hooks", {}).items():
                    f.write(f"  [{'ACTIVE' if h['active'] else 'INACTIVE'}] {h['name']} ({h['rva']}): {h['desc']}\n")
                f.write("\n--- PONY CURRENCY DISTRIBUTION ---\n")
                for c_type, cnt in report.get("ponies_summary", {}).get("currency_distribution", {}).items():
                    name_map = {1: "Bits", 2: "Gems", 3: "Hearts", 12: "Event Tokens", 16: "Invalid/IAP (0)"}
                    f.write(f"  Currency {c_type} ({name_map.get(c_type, 'Unknown')}): {cnt} ponies\n")
                f.write("\n--- RECENT LOG ENTRIES ---\n")
                for le in self.get_logs()[-30:]:
                    f.write(f"  [{le['timestamp']}] [{le['level']}] {le['message']}\n")
            self.log("REPORT", f"Saved full diagnostic report to {json_path} and {txt_path}.")
        except Exception as ex:
            self.log("ERROR", f"Failed to export diagnostic report: {ex}")

        return {
            "success": True,
            "json_path": json_path,
            "txt_path": txt_path,
            "report": report,
        }

    def set_auto_watch(self, enabled: bool):
        """Enables or disables continuous background watcher."""
        self.auto_watch_enabled = enabled
        self.log("INFO", f"Auto-Watch {'ENABLED' if enabled else 'DISABLED'}.")
        if enabled and (self._watch_thread is None or not self._watch_thread.is_alive()):
            self._watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
            self._watch_thread.start()

    def _watch_loop(self):
        """Background thread keeping memory hooks, currencies, and live array synchronized."""
        while self.auto_watch_enabled:
            pid = self.find_process()
            if pid:
                h_process = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
                if h_process:
                    try:
                        base_addr = self.get_main_module_base(h_process)
                        if base_addr:
                            # 1. Verify if all 8 patches are in place
                            missing = False
                            for key, info in self.PATCHES.items():
                                cur = self._read_bytes(h_process, base_addr + info["rva"], len(info["patch"]))
                                if cur != info["patch"]:
                                    missing = True
                                    break
                            # Also check if 0x6C9600 was corrupted
                            zone_cur = self._read_bytes(h_process, base_addr + 0x6C9600, 5)
                            if zone_cur != self.VANILLA_ZONE_BYTES:
                                missing = True

                            if missing:
                                self.log("INFO", "[Auto-Watch] Detected unpatched memory state. Reapplying hooks & enforcing town isolation...")
                                self.patch_memory()
                            else:
                                # Synchronize array & currencies
                                self.sync_live_shop_items(h_process, base_addr)
                    finally:
                        CloseHandle(h_process)
            time.sleep(2.0)

    def set_offline_mode(self, offline: bool) -> bool:
        """The tool operates strictly in 100% offline mode."""
        self.offline_mode = True
        return True

    def get_shop_catalog(self, refresh_from_ram: bool = False) -> Dict[str, Any]:
        """
        Returns complete pony catalog for game version 11.4.1a.
        Reads live b125 visibility and price states from RAM if connected.
        Works 100% offline from data/ponies_catalog.json.
        """
        catalog_path = os.path.join(self.data_dir, "ponies_catalog.json")
        if not os.path.exists(catalog_path) or refresh_from_ram:
            self.rescan_catalog_from_ram()

        if not os.path.exists(catalog_path):
            return {
                "success": False,
                "game_version": self.GAME_VERSION,
                "suite_version": self.VERSION,
                "error": "Catalog file not found and unable to scan from RAM.",
                "total_ponies": 0,
                "ponies": [],
            }

        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                catalog = json.load(f)
        except Exception as ex:
            return {"success": False, "error": f"Failed to read catalog: {ex}"}

        # If connected to live game, enrich with live b125 states from RAM
        pid = self.find_process()
        if pid:
            h_process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if h_process:
                try:
                    base_addr = self.get_main_module_base(h_process)
                    if base_addr:
                        ctrl_buf = self._read_bytes(h_process, base_addr + self.OFFSET_SHOP_CONTROLLER, 8)
                        if ctrl_buf:
                            ctrl_addr = struct.unpack("<Q", ctrl_buf)[0]
                            hdr_buf = self._read_bytes(h_process, ctrl_addr, 0x500)
                            if hdr_buf:
                                start_ptr = struct.unpack("<Q", hdr_buf[0x438:0x440])[0]
                                end_ptr = struct.unpack("<Q", hdr_buf[0x440:0x448])[0]
                                total_items = (end_ptr - start_ptr) // 0x158
                                if total_items > 0:
                                    arr_buf = self._read_bytes(h_process, start_ptr, total_items * 0x158)
                                    if arr_buf:
                                        live_states = {}
                                        for i in range(total_items):
                                            off = i * 0x158
                                            cat = struct.unpack("<I", arr_buf[off + 8:off + 12])[0]
                                            if cat == 0x39:
                                                pony_id = self._get_item_id(h_process, arr_buf, off, i)
                                                if pony_id:
                                                    b125 = arr_buf[off + 0x125]
                                                    live_states[pony_id] = b125

                                        for pony in catalog.get("ponies", []):
                                            pid_val = pony["id"]
                                            if pid_val in live_states:
                                                pony["b125"] = live_states[pid_val]
                                                pony["active_in_store"] = bool(live_states[pid_val] == 1)
                finally:
                    CloseHandle(h_process)

        # Attach suite status
        catalog["success"] = True
        catalog["custom_selection_active"] = (self.custom_selection is not None)
        catalog["custom_selection_count"] = len(self.custom_selection) if self.custom_selection is not None else catalog.get("total_ponies", len(catalog.get("ponies", [])))
        catalog["offline_mode"] = self.offline_mode
        catalog["suite_version"] = self.VERSION
        catalog["game_version"] = self.GAME_VERSION
        return catalog

    def apply_pony_selection(self, selected_ids: Optional[List[str]]) -> Dict[str, Any]:
        """
        Applies custom pony selection in live game RAM:
        Sets b125=1, b126=1 for ponies in selected_ids; b125=0, b126=0 for unselected ponies.
        Maintains currency and price normalization across all items so any selected pony can be purchased immediately.
        """
        if selected_ids is None:
            self.custom_selection = None
            self.log("CATALOG", "Selection reset to ALL ponies in game.")
        else:
            self.custom_selection = set(selected_ids)
            self.log("CATALOG", f"Applying custom selection: {len(self.custom_selection)} ponies selected.")

        pid = self.find_process()
        if not pid:
            return {
                "success": False,
                "error": "Game is not running. Launch MyLittlePony_x64.exe first.",
                "selected_count": len(self.custom_selection) if self.custom_selection is not None else 2381,
            }

        h_process = OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h_process:
            return {
                "success": False,
                "error": "Failed to open process. Administrator privileges may be required.",
                "selected_count": len(self.custom_selection) if self.custom_selection is not None else 2381,
            }

        try:
            base_addr = self.get_main_module_base(h_process)
            if not base_addr:
                return {"success": False, "error": "Base address not found."}

            updated, currs, prices = self.sync_live_shop_items(h_process, base_addr)
            selected_cnt = len(self.custom_selection) if self.custom_selection is not None else 2381
            self.log("SUCCESS", f"Store Selection Applied in RAM: {selected_cnt} ponies active on shelf ({updated} flags synced).")
            return {
                "success": True,
                "selected_count": selected_cnt,
                "updated_items": updated,
                "currencies_fixed": currs,
                "prices_fixed": prices,
            }
        finally:
            CloseHandle(h_process)

    def rescan_catalog_from_ram(self) -> Dict[str, Any]:
        """
        Scans all ponies directly from live game RAM and regenerates local JSON database.
        Strictly offline; requires zero internet connection. Labeled for game version 11.4.1a.
        """
        pid = self.find_process()
        if not pid:
            return {"success": False, "error": "Game process not running. Launch game to scan RAM."}

        h_process = OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if not h_process:
            return {"success": False, "error": "Failed to open game process."}

        try:
            base_addr = self.get_main_module_base(h_process)
            if not base_addr:
                return {"success": False, "error": "Base address not found."}

            ctrl_buf = self._read_bytes(h_process, base_addr + self.OFFSET_SHOP_CONTROLLER, 8)
            if not ctrl_buf:
                return {"success": False, "error": "Shop controller not found."}

            ctrl_addr = struct.unpack("<Q", ctrl_buf)[0]
            hdr_buf = self._read_bytes(h_process, ctrl_addr, 0x500)
            start_ptr = struct.unpack("<Q", hdr_buf[0x438:0x440])[0]
            end_ptr = struct.unpack("<Q", hdr_buf[0x440:0x448])[0]
            total_items = (end_ptr - start_ptr) // 0x158

            zone_map = {
                0: "Ponyville",
                1: "Canterlot",
                2: "Sweet Apple Acres",
                3: "Everfree Forest",
                4: "Crystal Empire",
                5: "Changeling Kingdom",
                6: "Klugetown",
            }

            ponies = []
            for i in range(total_items):
                off = i * 0x158
                item_addr = start_ptr + off
                data = self._read_bytes(h_process, item_addr, 0x158)
                cat_id = struct.unpack("<I", data[8:12])[0]
                if cat_id != 0x39:
                    continue

                internal_id = self._get_item_id(h_process, data, 0, i)
                if not internal_id:
                    continue

                z_start = struct.unpack("<Q", data[0x38:0x40])[0]
                z_end = struct.unpack("<Q", data[0x40:0x48])[0]
                zones = []
                if z_start and z_end and z_end >= z_start:
                    z_cnt = (z_end - z_start) // 4
                    z_raw = self._read_bytes(h_process, z_start, z_cnt * 4)
                    if z_raw:
                        zones = list(struct.unpack(f"<{z_cnt}i", z_raw))

                display_name = internal_id
                if display_name.startswith("Pony_"):
                    display_name = display_name[5:].replace("_", " ")

                p90, p94, p98, p9c = struct.unpack("<4I", data[0x90:0xA0])
                price = ror32(p98 ^ p90, 5)
                xml_curr = struct.unpack("<I", data[0x108:0x10C])[0]
                b125 = data[0x125]
                b126 = data[0x126]

                primary_zone = zones[0] if zones else 0
                zone_name = zone_map.get(primary_zone, f"Zone {primary_zone}")

                ponies.append({
                    "index": i,
                    "id": internal_id,
                    "name": display_name,
                    "zones": zones,
                    "primary_zone": primary_zone,
                    "zone_name": zone_name,
                    "currency": "Bits" if xml_curr == 1 else "Gems",
                    "currency_id": xml_curr,
                    "price": price,
                    "b125": b125,
                    "b126": b126,
                    "local_portrait": f"/assets/portraits/{internal_id}.png"
                })

            catalog_data = {
                "game_version": self.GAME_VERSION,
                "suite_version": self.VERSION,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "source": f"{self.TARGET_PROCESS_NAME} Live RAM",
                "total_ponies": len(ponies),
                "zones_summary": {
                    "Ponyville": sum(1 for p in ponies if p["primary_zone"] == 0),
                    "Canterlot": sum(1 for p in ponies if p["primary_zone"] == 1),
                    "Sweet Apple Acres": sum(1 for p in ponies if p["primary_zone"] == 2),
                    "Crystal Empire": sum(1 for p in ponies if p["primary_zone"] == 4),
                    "Klugetown": sum(1 for p in ponies if p["primary_zone"] == 6),
                    "Everfree Forest": sum(1 for p in ponies if p["primary_zone"] == 3),
                },
                "ponies": ponies,
            }

            os.makedirs(self.data_dir, exist_ok=True)
            with open(os.path.join(self.data_dir, f"database_v{self.GAME_VERSION}.json"), "w", encoding="utf-8") as f:
                json.dump(catalog_data, f, indent=2)
            with open(os.path.join(self.data_dir, "ponies_catalog.json"), "w", encoding="utf-8") as f:
                json.dump(catalog_data, f, indent=2)

            self.log("CATALOG", f"Re-scanned {len(ponies)} ponies directly from live game RAM and saved local database for v{self.GAME_VERSION}.")
            return {"success": True, "total": len(ponies), "catalog": catalog_data}
        finally:
            CloseHandle(h_process)
