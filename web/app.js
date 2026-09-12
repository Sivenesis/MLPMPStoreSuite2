// MLP Store Suite II - Frontend Control Engine (v4.0.0)
(function () {
  "use strict";

  let activeFilter = "ALL";
  let autoScroll = true;
  let lastLogCount = 0;

  // Catalog State
  let catalogPonies = [];
  let selectedPonyIds = new Set();
  let currentTownFilter = "ALL";
  let currentStatusFilter = "ALL";
  let searchQuery = "";
  let currentPage = 1;
  const pageSize = 60;
  let liveCurrentZone = 0; // default Ponyville
  let isCatalogLoaded = false;

  // Global Image Error Handler (Clean, safe fallback with zero HTML attribute escaping issues)
  window.handlePortraitError = function (img) {
    if (!img) return;
    img.style.display = "none";
    if (img.parentElement) {
      const fallback = img.parentElement.querySelector(".pony-portrait-fallback");
      if (fallback) fallback.style.display = "block";
    }
  };

  // DOM Elements - Telemetry & Header
  const elAppVersion = document.getElementById("app-version");
  const elGameVersion = document.getElementById("app-game-version");
  const elOfflineTag = document.getElementById("app-offline-tag");
  const elProcessDot = document.getElementById("process-dot");
  const elProcessText = document.getElementById("process-text");
  
  const elTargetName = document.getElementById("val-target-name");
  const elPidBase = document.getElementById("val-pid-base");
  const elZoneName = document.getElementById("val-zone-name");
  const elZoneId = document.getElementById("val-zone-id");
  const elPlayerCurrency = document.getElementById("val-player-currency");
  const elPlayerMgr = document.getElementById("val-player-mgr");
  const elShopItems = document.getElementById("val-shop-items");
  const elSyncState = document.getElementById("val-sync-state");

  // DOM Elements - Controls & Logs
  const elBtnPatch = document.getElementById("btn-patch-now");
  const elBtnInspect = document.getElementById("btn-inspect-now");
  const elBtnExportLogs = document.getElementById("btn-export-logs");
  const elToggleAutoWatch = document.getElementById("toggle-auto-watch");
  const elHooksContainer = document.getElementById("hooks-container");
  const elHooksCount = document.getElementById("hooks-count-badge");
  const elTerminalBody = document.getElementById("terminal-body");
  const elBtnClearLog = document.getElementById("btn-clear-log");
  const elLogFileIndicator = document.getElementById("log-file-indicator");
  const filterBtns = document.querySelectorAll(".filter-btn");

  // DOM Elements - Catalog Manager
  const elCatalogGrid = document.getElementById("catalog-grid");
  const elCatalogSearchInput = document.getElementById("catalog-search-input");
  const elBtnClearSearch = document.getElementById("btn-clear-search");
  const elCatalogSummary = document.getElementById("catalog-selection-summary");
  const elBtnRescanRam = document.getElementById("btn-rescan-ram");
  const elBtnSelectSearch = document.getElementById("btn-select-search");
  const elBtnSelectSearchCount = document.getElementById("btn-select-search-count");
  const elBtnSelectAll = document.getElementById("btn-select-all");
  const elBtnSelectNone = document.getElementById("btn-select-none");
  const elBtnSelectCurrentTown = document.getElementById("btn-select-current-town");
  const elBtnInvertSelection = document.getElementById("btn-invert-selection");
  const elBtnApplySelection = document.getElementById("btn-apply-selection");
  const elBtnApplyCount = document.getElementById("btn-apply-count");
  const elTownTabs = document.querySelectorAll(".town-tab");
  const elStatusTabs = document.querySelectorAll(".status-tab");
  const elShowingCount = document.getElementById("showing-count");
  const elMatchingCount = document.getElementById("matching-count");
  const elActiveStoreCount = document.getElementById("active-store-count");
  const elPaginationControls = document.getElementById("pagination-controls");

  // Collapsible Sections Elements
  const hooksSection = document.getElementById("hooks-section");
  const hooksHeader = document.getElementById("hooks-header");
  const btnToggleHooks = document.getElementById("btn-toggle-hooks");
  const hooksIcon = document.getElementById("hooks-collapse-icon");

  const terminalSection = document.getElementById("terminal-section");
  const terminalHeader = document.getElementById("terminal-header");
  const btnToggleTerminal = document.getElementById("btn-toggle-terminal");
  const terminalIcon = document.getElementById("terminal-collapse-icon");

  // Filter Counts Badges
  const elCountZoneAll = document.getElementById("count-zone-all");
  const elCountZone0 = document.getElementById("count-zone-0");
  const elCountZone1 = document.getElementById("count-zone-1");
  const elCountZone2 = document.getElementById("count-zone-2");
  const elCountZone4 = document.getElementById("count-zone-4");
  const elCountZone6 = document.getElementById("count-zone-6");
  const elCountStatusEnabled = document.getElementById("count-status-enabled");
  const elCountStatusDisabled = document.getElementById("count-status-disabled");

  function fmtNum(n) {
    if (n === null || n === undefined) return "-";
    return Number(n).toLocaleString("en-US");
  }

  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  // ==========================================
  // TELEMETRY & SYSTEM STATUS
  // ==========================================
  async function fetchStatus() {
    try {
      const res = await fetch("/api/status");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      renderStatus(data);
    } catch (err) {
      elProcessDot.className = "indicator-dot offline";
      elProcessText.textContent = "SERVER DISCONNECTED";
    }
  }

  async function fetchLogs() {
    try {
      const res = await fetch("/api/logs");
      if (!res.ok) return;
      const logs = await res.json();
      renderLogs(logs);
    } catch (_) {}
  }

  function renderStatus(data) {
    if (data.suite_version && elAppVersion) elAppVersion.textContent = data.suite_version;
    if (data.game_version && elGameVersion) elGameVersion.textContent = `GAME v${data.game_version}`;
    if (elOfflineTag) {
      elOfflineTag.textContent = "STRICT OFFLINE READY";
    }

    // Version Check & Non-Blocking Warning
    const verCheck = data.version_check;
    const elVerWarningBanner = document.getElementById("version-warning-banner");
    const elVerWarningText = document.getElementById("version-warning-text");
    if (verCheck && verCheck.matched === false) {
      if (elVerWarningBanner) elVerWarningBanner.style.display = "flex";
      if (elVerWarningText) {
        elVerWarningText.textContent = verCheck.warning || `VERSION MISMATCH: Detected game client ${verCheck.detected || 'unknown'}, but tool was built for v${verCheck.target}. Memory offsets may differ.`;
      }
    } else {
      if (elVerWarningBanner) elVerWarningBanner.style.display = "none";
    }

    if (data.log_file && elLogFileIndicator) {
      elLogFileIndicator.textContent = data.log_file;
      elLogFileIndicator.title = `Log File: ${data.log_file}`;
    }

    const isRunning = data.is_running;
    if (isRunning) {
      elProcessDot.className = "indicator-dot online";
      elProcessText.textContent = `PROCESS ACTIVE (PID ${data.pid})`;
      elTargetName.textContent = data.target_process;
      elPidBase.textContent = `PID: ${data.pid} | BASE: ${data.base_address || "-"}`;
    } else {
      elProcessDot.className = "indicator-dot offline";
      elProcessText.textContent = "GAME NOT RUNNING";
      elPidBase.textContent = "PID: - | BASE: -";
    }

    // Telemetry
    const tel = data.telemetry || {};
    if (tel.current_zone !== null && tel.current_zone !== undefined) {
      liveCurrentZone = tel.current_zone;
    }

    if (tel.zone_name) {
      const townStr = tel.zone_name;
      const shopTabStr = tel.shop_category_zone_name || "Same";
      elZoneName.textContent = `TOWN: ${townStr}`;
      elZoneId.textContent = `STORE TAB: ${shopTabStr} | TOWN ISOLATION: VANILLA`;
    } else {
      elZoneName.textContent = isRunning ? "In Menu / Loading..." : "Offline";
      elZoneId.textContent = "STORE TAB: - | TOWN ISOLATION: VANILLA";
    }

    if (tel.bits !== null && tel.bits !== undefined && tel.gems !== null && tel.gems !== undefined) {
      elPlayerCurrency.textContent = `BITS: ${fmtNum(tel.bits)} | GEMS: ${fmtNum(tel.gems)}`;
      elPlayerMgr.textContent = `PLAYER CONTROLLER: ${tel.player_manager_addr || "-"}`;
    } else {
      elPlayerCurrency.textContent = "BITS: - | GEMS: -";
      elPlayerMgr.textContent = "PLAYER CONTROLLER: -";
    }

    if (tel.shop_items_total !== null && tel.shop_items_total !== undefined) {
      elShopItems.textContent = `${fmtNum(tel.shop_items_total)} ITEMS`;
    } else {
      elShopItems.textContent = "- ITEMS";
    }

    elToggleAutoWatch.checked = !!data.auto_watch;

    // Render Hooks
    renderHooks(data.hooks || {});
  }

  function renderHooks(hooks) {
    const keys = Object.keys(hooks);
    if (!keys.length) return;

    let activeCount = 0;
    const cardsHtml = keys.map(key => {
      const h = hooks[key];
      if (h.active) activeCount++;
      const badgeClass = h.active ? "badge-active" : "badge-inactive";
      const statusText = h.active ? "INTERCEPTING" : "BYPASSED";
      const cardState = h.active ? "hook-active" : "hook-inactive";

      return `
        <div class="hook-card ${cardState}">
          <div class="hook-header">
            <span class="hook-name">${escapeHtml(h.name)}</span>
            <span class="hook-badge ${badgeClass}">${statusText}</span>
          </div>
          <div class="hook-rva code">${escapeHtml(h.rva)}</div>
          <div class="hook-desc">${escapeHtml(h.desc)}</div>
        </div>
      `;
    }).join("");

    elHooksContainer.innerHTML = cardsHtml;
    elHooksCount.textContent = `${activeCount}/${keys.length} ACTIVE`;
  }

  // ==========================================
  // PONY STORE CATALOG & SELECTION MANAGER
  // ==========================================
  async function fetchCatalog(refreshRam = false) {
    try {
      const url = refreshRam ? "/api/catalog?refresh=1" : "/api/catalog";
      const res = await fetch(url);
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      
      catalogPonies = data.ponies || [];
      
      // Initialize selected set from live data
      selectedPonyIds.clear();
      catalogPonies.forEach(p => {
        if (p.active_in_store !== false && p.b125 !== 0) {
          selectedPonyIds.add(p.id);
        }
      });

      // Update zone summary badges
      const summary = data.zones_summary || {};
      if (elCountZoneAll) elCountZoneAll.textContent = catalogPonies.length;
      if (elCountZone0) elCountZone0.textContent = summary["Ponyville"] || 0;
      if (elCountZone1) elCountZone1.textContent = summary["Canterlot"] || 0;
      if (elCountZone2) elCountZone2.textContent = summary["Sweet Apple Acres"] || 0;
      if (elCountZone4) elCountZone4.textContent = summary["Crystal Empire"] || 0;
      if (elCountZone6) elCountZone6.textContent = summary["Klugetown"] || 0;

      updateStatusCounters();
      isCatalogLoaded = true;
      renderCatalog();
    } catch (err) {
      if (elCatalogGrid) {
        elCatalogGrid.innerHTML = `<div class="catalog-loading" style="color: var(--accent-red);">Failed to load pony catalog: ${escapeHtml(err.message)}</div>`;
      }
    }
  }

  function updateStatusCounters() {
    if (elCountStatusEnabled) elCountStatusEnabled.textContent = selectedPonyIds.size;
    if (elCountStatusDisabled) elCountStatusDisabled.textContent = Math.max(0, catalogPonies.length - selectedPonyIds.size);
  }

  function getTownBadgeClass(zoneId) {
    switch (zoneId) {
      case 0: return "town-ponyville";
      case 1: return "town-canterlot";
      case 2: return "town-saa";
      case 4: return "town-crystal";
      case 6: return "town-kluge";
      case 3: return "town-everfree";
      default: return "town-ponyville";
    }
  }

  function getFilteredPonies() {
    let list = catalogPonies;

    // 1. Filter by town tab
    if (currentTownFilter !== "ALL") {
      const targetZone = parseInt(currentTownFilter, 10);
      list = list.filter(p => p.primary_zone === targetZone || (p.zones && p.zones.includes(targetZone)));
    }

    // 2. Filter by status tab (ALL, ENABLED, DISABLED)
    if (currentStatusFilter === "ENABLED") {
      list = list.filter(p => selectedPonyIds.has(p.id));
    } else if (currentStatusFilter === "DISABLED") {
      list = list.filter(p => !selectedPonyIds.has(p.id));
    }

    // 3. Filter by search text
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      list = list.filter(p => p.name.toLowerCase().includes(q) || p.id.toLowerCase().includes(q));
    }

    return list;
  }

  function renderCatalog() {
    if (!elCatalogGrid) return;

    updateStatusCounters();
    const filtered = getFilteredPonies();
    updateSearchSelectionButton(filtered);
    const totalMatching = filtered.length;
    const totalPages = Math.max(1, Math.ceil(totalMatching / pageSize));

    if (currentPage > totalPages) currentPage = totalPages;
    if (currentPage < 1) currentPage = 1;

    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, totalMatching);
    const pageItems = filtered.slice(startIdx, endIdx);

    // Update summary counts
    if (elCatalogSummary) {
      elCatalogSummary.textContent = `SELECTED: ${selectedPonyIds.size} / ${catalogPonies.length} PONIES`;
    }
    if (elBtnApplyCount) {
      elBtnApplyCount.textContent = selectedPonyIds.size;
    }
    if (elShowingCount) elShowingCount.textContent = pageItems.length;
    if (elMatchingCount) elMatchingCount.textContent = totalMatching;
    if (elActiveStoreCount) {
      const activeInFilter = filtered.filter(p => selectedPonyIds.has(p.id)).length;
      elActiveStoreCount.textContent = activeInFilter;
    }

    if (pageItems.length === 0) {
      elCatalogGrid.innerHTML = `<div class="catalog-loading">No ponies match the selected town, status, or search query.</div>`;
      renderPagination(0, 0);
      return;
    }

    const cardsHtml = pageItems.map(p => {
      const isSelected = selectedPonyIds.has(p.id);
      const townClass = getTownBadgeClass(p.primary_zone);
      const priceClass = p.currency === "Bits" ? "price-bits" : "price-gems";
      const cardClass = isSelected ? "selected" : "deselected";
      const portraitSrc = p.local_portrait || `/assets/portraits/${encodeURIComponent(p.id)}.png`;

      return `
        <div class="pony-card ${cardClass}" data-id="${p.id}">
          <div class="pony-portrait-wrap">
            <img class="pony-portrait" 
                 src="${escapeHtml(portraitSrc)}" 
                 alt="${escapeHtml(p.name)}" 
                 loading="lazy"
                 onerror="handlePortraitError(this)">
            <svg class="pony-portrait-fallback" viewBox="0 0 24 24"><path d="M19.5 7.05L16.2 3.75C15.8 3.35 15.2 3.1 14.6 3.1H9.4C8.8 3.1 8.2 3.35 7.8 3.75L4.5 7.05C4.1 7.45 3.85 8.05 3.85 8.65V15.35C3.85 15.95 4.1 16.55 4.5 16.95L7.8 20.25C8.2 20.65 8.8 20.9 9.4 20.9H14.6C15.2 20.9 15.8 20.65 16.2 20.25L19.5 16.95C19.9 16.55 20.15 15.95 20.15 15.35V8.65C20.15 8.05 19.9 7.45 19.5 7.05ZM12 17.5C9.5 17.5 7.5 15.5 7.5 13C7.5 10.5 9.5 8.5 12 8.5C14.5 8.5 16.5 10.5 16.5 13C16.5 15.5 14.5 17.5 12 17.5Z"/></svg>
          </div>
          <div class="pony-info">
            <div class="pony-name" title="${escapeHtml(p.name)}">${escapeHtml(p.name)}</div>
            <div class="pony-id-code code" title="${escapeHtml(p.id)}">${escapeHtml(p.id)}</div>
            <div class="pony-meta-row">
              <span class="town-badge ${townClass}">${escapeHtml(p.zone_name)}</span>
              <span class="price-badge ${priceClass}">${p.price} ${p.currency}</span>
            </div>
          </div>
          <div class="pony-checkbox-wrap">
            <input type="checkbox" class="pony-checkbox" ${isSelected ? "checked" : ""} data-id="${p.id}" tabindex="-1">
          </div>
        </div>
      `;
    }).join("");

    elCatalogGrid.innerHTML = cardsHtml;
    renderPagination(currentPage, totalPages);
  }

  function renderPagination(page, totalPages) {
    if (!elPaginationControls) return;
    if (totalPages <= 1) {
      elPaginationControls.innerHTML = "";
      return;
    }

    elPaginationControls.innerHTML = `
      <button type="button" class="pagination-btn" id="btn-prev-page" ${page <= 1 ? "disabled" : ""}>&lt; PREV</button>
      <span class="page-indicator">PAGE ${page} / ${totalPages}</span>
      <button type="button" class="pagination-btn" id="btn-next-page" ${page >= totalPages ? "disabled" : ""}>NEXT &gt;</button>
    `;

    const btnPrev = document.getElementById("btn-prev-page");
    const btnNext = document.getElementById("btn-next-page");

    if (btnPrev) {
      btnPrev.addEventListener("click", () => {
        if (currentPage > 1) {
          currentPage--;
          renderCatalog();
          elCatalogGrid.scrollTop = 0;
        }
      });
    }

    if (btnNext) {
      btnNext.addEventListener("click", () => {
        if (currentPage < totalPages) {
          currentPage++;
          renderCatalog();
          elCatalogGrid.scrollTop = 0;
        }
      });
    }
  }

  // Handle card click and checkbox toggle
  if (elCatalogGrid) {
    elCatalogGrid.addEventListener("click", (e) => {
      const card = e.target.closest(".pony-card");
      if (!card) return;

      const ponyId = card.dataset.id;
      if (!ponyId) return;

      const checkbox = card.querySelector(".pony-checkbox");
      const isCurrentlySelected = selectedPonyIds.has(ponyId);

      if (isCurrentlySelected) {
        selectedPonyIds.delete(ponyId);
        card.classList.remove("selected");
        card.classList.add("deselected");
        if (checkbox) checkbox.checked = false;
        if (currentStatusFilter === "ENABLED") {
          card.style.display = "none";
        }
      } else {
        selectedPonyIds.add(ponyId);
        card.classList.remove("deselected");
        card.classList.add("selected");
        if (checkbox) checkbox.checked = true;
        if (currentStatusFilter === "DISABLED") {
          card.style.display = "none";
        }
      }

      // Update counters
      updateStatusCounters();
      if (elCatalogSummary) {
        elCatalogSummary.textContent = `SELECTED: ${selectedPonyIds.size} / ${catalogPonies.length} PONIES`;
      }
      if (elBtnApplyCount) {
        elBtnApplyCount.textContent = selectedPonyIds.size;
      }
      const filtered = getFilteredPonies();
      if (elActiveStoreCount) {
        elActiveStoreCount.textContent = filtered.filter(p => selectedPonyIds.has(p.id)).length;
      }
    });
  }

  // Town Tabs Event
  elTownTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      elTownTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      currentTownFilter = tab.dataset.zone;
      currentPage = 1;
      renderCatalog();
    });
  });

  // Status Tabs Event (ALL, ENABLED, DISABLED)
  elStatusTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      elStatusTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      currentStatusFilter = tab.dataset.status;
      currentPage = 1;
      renderCatalog();
    });
  });

  // Search Input Event
  if (elCatalogSearchInput) {
    let searchDebounce = null;
    elCatalogSearchInput.addEventListener("input", () => {
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => {
        searchQuery = elCatalogSearchInput.value.trim();
        currentPage = 1;
        renderCatalog();
      }, 100);
    });
  }

  if (elBtnClearSearch) {
    elBtnClearSearch.addEventListener("click", () => {
      if (elCatalogSearchInput) elCatalogSearchInput.value = "";
      searchQuery = "";
      currentPage = 1;
      renderCatalog();
    });
  }

  // Selection Presets
  if (elBtnSelectSearch) {
    elBtnSelectSearch.addEventListener("click", () => {
      const filtered = getFilteredPonies();
      const allMatchingSelected = filtered.length > 0 && filtered.every(p => selectedPonyIds.has(p.id));
      if (allMatchingSelected) {
        filtered.forEach(p => selectedPonyIds.delete(p.id));
      } else {
        filtered.forEach(p => selectedPonyIds.add(p.id));
      }
      renderCatalog();
    });
  }

  if (elBtnSelectAll) {
    elBtnSelectAll.addEventListener("click", () => {
      catalogPonies.forEach(p => selectedPonyIds.add(p.id));
      renderCatalog();
    });
  }

  if (elBtnSelectNone) {
    elBtnSelectNone.addEventListener("click", () => {
      selectedPonyIds.clear();
      renderCatalog();
    });
  }

  if (elBtnSelectCurrentTown) {
    elBtnSelectCurrentTown.addEventListener("click", () => {
      selectedPonyIds.clear();
      catalogPonies.forEach(p => {
        if (p.primary_zone === liveCurrentZone || (p.zones && p.zones.includes(liveCurrentZone))) {
          selectedPonyIds.add(p.id);
        }
      });
      renderCatalog();
    });
  }

  if (elBtnInvertSelection) {
    elBtnInvertSelection.addEventListener("click", () => {
      const filtered = getFilteredPonies();
      filtered.forEach(p => {
        if (selectedPonyIds.has(p.id)) {
          selectedPonyIds.delete(p.id);
        } else {
          selectedPonyIds.add(p.id);
        }
      });
      renderCatalog();
    });
  }

  // Apply Selection to In-Game Store RAM
  if (elBtnApplySelection) {
    elBtnApplySelection.addEventListener("click", async () => {
      elBtnApplySelection.disabled = true;
      const originalText = elBtnApplySelection.innerHTML;
      elBtnApplySelection.textContent = "WRITING TO IN-GAME RAM...";

      try {
        const selectedArr = Array.from(selectedPonyIds);
        const res = await fetch("/api/catalog/apply", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ selected_ids: selectedArr }),
        });
        const data = await res.json();
        
        elBtnApplySelection.textContent = `APPLIED ${data.selected_count} PONIES TO RAM!`;
        await fetchStatus();
        await fetchLogs();

        setTimeout(() => {
          elBtnApplySelection.disabled = false;
          elBtnApplySelection.innerHTML = originalText;
          if (elBtnApplyCount) elBtnApplyCount.textContent = selectedPonyIds.size;
        }, 1500);
      } catch (err) {
        alert("Failed to apply store selection: " + err.message);
        elBtnApplySelection.disabled = false;
        elBtnApplySelection.innerHTML = originalText;
      }
    });
  }

  // Re-scan from RAM
  if (elBtnRescanRam) {
    elBtnRescanRam.addEventListener("click", async () => {
      elBtnRescanRam.disabled = true;
      elBtnRescanRam.textContent = "SCANNING RAM...";
      try {
        await fetch("/api/catalog/rescan", { method: "POST" });
        await fetchCatalog(true);
        await fetchLogs();
      } catch (err) {
        alert("Failed to rescan RAM: " + err.message);
      } finally {
        elBtnRescanRam.disabled = false;
        elBtnRescanRam.textContent = "RE-SCAN FROM RAM";
      }
    });
  }

  // ==========================================
  // LOGS & TERMINAL
  // ==========================================
  function renderLogs(logs) {
    if (!logs || !logs.length) return;
    if (logs.length === lastLogCount) return;
    lastLogCount = logs.length;

    let filtered = logs;
    if (activeFilter !== "ALL") {
      filtered = logs.filter(l => l.level === activeFilter);
    }

    const html = filtered.map(l => {
      const tagClass = `tag-${l.level.toLowerCase()}`;
      return `
        <div class="log-entry ${l.level.toLowerCase()}">
          <span class="log-time">[${l.timestamp}]</span>
          <span class="log-tag ${tagClass}">[${l.level}]</span>
          <span class="log-msg">${escapeHtml(l.message)}</span>
        </div>
      `;
    }).join("");

    if (elTerminalBody) {
      elTerminalBody.innerHTML = html;
      const isCollapsed = terminalSection && terminalSection.classList.contains("section-collapsed");
      if (autoScroll && !isCollapsed) {
        try {
          elTerminalBody.scrollTop = elTerminalBody.scrollHeight;
        } catch (_) {}
      }
    }
  }

  // Event: Patch Live RAM
  elBtnPatch.addEventListener("click", async () => {
    elBtnPatch.disabled = true;
    elBtnPatch.textContent = "PATCHING PROCESS MEMORY...";
    try {
      const res = await fetch("/api/patch", { method: "POST" });
      const data = await res.json();
      await fetchStatus();
      await fetchLogs();
    } catch (err) {
      alert("Failed to send patch command: " + err.message);
    } finally {
      elBtnPatch.disabled = false;
      elBtnPatch.textContent = "EXECUTE LIVE RAM PATCH & ENABLE PURCHASING";
    }
  });

  // Event: Deep Inspection
  elBtnInspect.addEventListener("click", async () => {
    elBtnInspect.disabled = true;
    try {
      await fetch("/api/inspect", { method: "POST" });
      await fetchStatus();
      await fetchLogs();
    } catch (err) {
      console.error(err);
    } finally {
      elBtnInspect.disabled = false;
    }
  });

  // Event: Export Diagnostic Logs
  if (elBtnExportLogs) {
    elBtnExportLogs.addEventListener("click", async () => {
      elBtnExportLogs.disabled = true;
      elBtnExportLogs.textContent = "SAVING REPORT...";
      try {
        const res = await fetch("/api/export-logs", { method: "POST" });
        const data = await res.json();
        await fetchLogs();
      } catch (err) {
        console.error(err);
      } finally {
        elBtnExportLogs.disabled = false;
        elBtnExportLogs.textContent = "SAVE DIAGNOSTIC REPORT TO LOGS";
      }
    });
  }

  // Event: Toggle Auto-Watch
  elToggleAutoWatch.addEventListener("change", async () => {
    const enabled = elToggleAutoWatch.checked;
    try {
      await fetch("/api/auto-watch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled }),
      });
      fetchStatus();
    } catch (err) {
      console.error(err);
    }
  });

  // Event: Clear Log
  elBtnClearLog.addEventListener("click", async () => {
    try {
      await fetch("/api/logs/clear", { method: "POST" });
      fetchLogs();
    } catch (_) {}
  });

  // Event: Filter Logs
  filterBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      filterBtns.forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.dataset.filter;
      lastLogCount = -1; // force re-render
      fetchLogs();
    });
  });

  // Safe Storage Helpers
  function safeGetStorage(key, defaultVal) {
    try {
      const val = localStorage.getItem(key);
      return val !== null ? val : defaultVal;
    } catch (_) {
      return defaultVal;
    }
  }

  function safeSetStorage(key, val) {
    try {
      localStorage.setItem(key, val);
    } catch (_) {}
  }

  // Collapsible Sections Management
  function setHooksCollapsed(collapsed) {
    if (!hooksSection) return;
    if (collapsed) {
      hooksSection.classList.add("section-collapsed");
      if (btnToggleHooks) btnToggleHooks.textContent = "SHOW";
      if (hooksIcon) hooksIcon.textContent = "▶";
      safeSetStorage("mlp_hooks_collapsed", "true");
    } else {
      hooksSection.classList.remove("section-collapsed");
      if (btnToggleHooks) btnToggleHooks.textContent = "HIDE";
      if (hooksIcon) hooksIcon.textContent = "▼";
      safeSetStorage("mlp_hooks_collapsed", "false");
    }
  }

  function setTerminalCollapsed(collapsed) {
    if (!terminalSection) return;
    if (collapsed) {
      terminalSection.classList.add("section-collapsed");
      if (btnToggleTerminal) btnToggleTerminal.textContent = "SHOW";
      if (terminalIcon) terminalIcon.textContent = "▶";
      safeSetStorage("mlp_terminal_collapsed", "true");
    } else {
      terminalSection.classList.remove("section-collapsed");
      if (btnToggleTerminal) btnToggleTerminal.textContent = "HIDE";
      if (terminalIcon) terminalIcon.textContent = "▼";
      safeSetStorage("mlp_terminal_collapsed", "false");
      setTimeout(() => {
        try {
          if (elTerminalBody) elTerminalBody.scrollTop = elTerminalBody.scrollHeight;
        } catch (_) {}
      }, 30);
    }
  }

  function updateSearchSelectionButton(filtered) {
    if (!elBtnSelectSearch) return;
    if (searchQuery && searchQuery.length > 0) {
      elBtnSelectSearch.style.display = "inline-flex";
      const totalMatching = filtered.length;
      const allMatchingSelected = totalMatching > 0 && filtered.every(p => selectedPonyIds.has(p.id));
      if (allMatchingSelected) {
        elBtnSelectSearch.classList.add("deselect-mode");
        elBtnSelectSearch.innerHTML = `DESELECT SEARCH (<span id="btn-select-search-count">${totalMatching}</span>)`;
      } else {
        elBtnSelectSearch.classList.remove("deselect-mode");
        elBtnSelectSearch.innerHTML = `SELECT SEARCH (<span id="btn-select-search-count">${totalMatching}</span>)`;
      }
    } else {
      elBtnSelectSearch.style.display = "none";
    }
  }

  // DEFAULT BOTH SECTIONS TO COLLAPSED
  const savedHooksPref = safeGetStorage("mlp_hooks_collapsed", "true");
  setHooksCollapsed(savedHooksPref !== "false");

  const savedTerminalPref = safeGetStorage("mlp_terminal_collapsed", "true");
  setTerminalCollapsed(savedTerminalPref !== "false");

  if (hooksHeader) {
    hooksHeader.addEventListener("click", (e) => {
      e.preventDefault();
      const isCurrentlyCollapsed = hooksSection.classList.contains("section-collapsed");
      setHooksCollapsed(!isCurrentlyCollapsed);
    });
  }

  if (terminalHeader) {
    terminalHeader.addEventListener("click", (e) => {
      if (e.target.closest(".filter-btn") || e.target.closest("#btn-clear-log")) {
        return;
      }
      e.preventDefault();
      const isCurrentlyCollapsed = terminalSection.classList.contains("section-collapsed");
      setTerminalCollapsed(!isCurrentlyCollapsed);
    });
  }

  // Scroll detection
  if (elTerminalBody) {
    elTerminalBody.addEventListener("scroll", () => {
      try {
        const atBottom = elTerminalBody.scrollHeight - elTerminalBody.scrollTop - elTerminalBody.clientHeight < 30;
        autoScroll = atBottom;
      } catch (_) {}
    });
  }

  // Polling loop
  fetchStatus();
  fetchLogs();
  fetchCatalog();

  setInterval(() => {
    fetchStatus();
    fetchLogs();
  }, 1500);
})();
