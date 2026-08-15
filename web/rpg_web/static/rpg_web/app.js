(() => {
  "use strict";

  const UI_KEY = "kaling-rpg-web-ui-v1";
  const main = document.querySelector("#main");
  if (!main) return;

  const saved = (() => {
    try {
      return JSON.parse(sessionStorage.getItem(UI_KEY) || "{}");
    } catch (_error) {
      return {};
    }
  })();

  const state = {
    profile: null,
    content: null,
    bossSession: null,
    joinableSessions: [],
    tab: saved.tab || "home",
    selected: saved.selected || {},
    filters: saved.filters || {},
    scroll: saved.scroll || {},
    bossUi: saved.bossUi || {},
    result: null,
    enhancementPreview: null,
    enhancementResult: null,
    actionError: "",
    busy: false,
  };
  let busyControl = null;
  let previewLoadKey = "";
  let actionErrorTimer = null;
  let renderedTab = null;
  let focusRestore = null;
  let composingFilter = null;

  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
  const number = (value) => Number(value || 0).toLocaleString("ko-KR");
  const percent = (value, digits = 1) => `${(Number(value || 0) * 100).toFixed(digits)}%`;
  const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
  const normalize = (value) => String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
  const matches = (values, query) => {
    const terms = normalize(query).split(" ").filter(Boolean);
    if (!terms.length) return true;
    const haystack = normalize(values.join(" "));
    return terms.every((term) => haystack.includes(term));
  };

  function csrfToken() {
    const row = document.cookie.split("; ").find((entry) => entry.startsWith("csrftoken="));
    return row ? decodeURIComponent(row.split("=")[1]) : "";
  }

  function saveUi() {
    sessionStorage.setItem(UI_KEY, JSON.stringify({
      tab: state.tab,
      selected: state.selected,
      filters: state.filters,
      scroll: state.scroll,
      bossUi: state.bossUi,
    }));
  }

  function captureElementScroll(element) {
    const key = element.dataset.scrollKey;
    if (key !== "boss.combat-log") {
      state.scroll[key] = element.scrollTop;
      return;
    }
    const rows = [...element.querySelectorAll(".log-line")];
    const bounds = element.getBoundingClientRect();
    const anchor = rows.find((row) => row.getBoundingClientRect().bottom > bounds.top + 1);
    state.scroll[key] = {
      top: element.scrollTop,
      height: element.scrollHeight,
      anchorId: anchor?.dataset.logId || "",
      anchorOffset: anchor ? anchor.getBoundingClientRect().top - bounds.top : 0,
    };
  }

  function captureScroll(tab = renderedTab || state.tab) {
    state.scroll[`page:${tab}`] = window.scrollY;
    document.querySelectorAll("[data-scroll-key]").forEach((element) => {
      if (element.dataset.scrollKey === "boss.combat-log" && element.closest("details:not([open])")) return;
      captureElementScroll(element);
    });
  }

  function ensureBossUi(session) {
    const sessionId = String(session?.id ?? "");
    if (String(state.bossUi.sessionId ?? "") !== sessionId) {
      state.bossUi = { sessionId, combatDetailsOpen: false };
      state.scroll["boss.combat-log"] = 0;
      state.scroll["page:boss"] = 0;
    }
    return state.bossUi;
  }

  function clearBossUi() {
    if (!state.bossUi.sessionId) return;
    state.bossUi = {};
    state.scroll["boss.combat-log"] = 0;
    state.scroll["page:boss"] = 0;
  }

  function captureBossUi() {
    const details = main.querySelector("details[data-boss-session-id]");
    if (!details) return;
    const bossUi = ensureBossUi({ id: details.dataset.bossSessionId });
    bossUi.combatDetailsOpen = details.open;
  }

  function captureFocus() {
    const active = document.activeElement;
    if (!(active instanceof HTMLElement) || !main.contains(active)) {
      focusRestore = null;
      return;
    }
    if (active.dataset.focusKey) {
      focusRestore = { type: "control", key: active.dataset.focusKey };
      return;
    }
    if (active.matches("input[data-filter], textarea[data-filter]")) {
      focusRestore = {
        type: "filter",
        key: active.dataset.filter,
        start: active.selectionStart,
        end: active.selectionEnd,
        direction: active.selectionDirection,
      };
      return;
    }
    focusRestore = null;
  }

  function restoreElementScroll(element) {
    const savedPosition = state.scroll[element.dataset.scrollKey];
    if (savedPosition && typeof savedPosition === "object") {
      const top = Number(savedPosition.top || 0);
      if (top <= 2) {
        element.scrollTop = 0;
        return;
      }
      const anchor = savedPosition.anchorId
        ? [...element.querySelectorAll(".log-line")].find((row) => row.dataset.logId === savedPosition.anchorId)
        : null;
      if (anchor) {
        const bounds = element.getBoundingClientRect();
        const contentTop = anchor.getBoundingClientRect().top - bounds.top + element.scrollTop;
        element.scrollTop = contentTop - Number(savedPosition.anchorOffset || 0);
        return;
      }
      const previousHeight = Number(savedPosition.height || 0);
      const addedHeight = Math.max(0, element.scrollHeight - previousHeight);
      element.scrollTop = top + addedHeight;
      return;
    }
    element.scrollTop = Number(savedPosition || 0);
  }

  function restoreScroll() {
    requestAnimationFrame(() => {
      const pageY = Number(state.scroll[`page:${state.tab}`] || 0);
      window.scrollTo({ top: pageY, behavior: "instant" });
      document.querySelectorAll("[data-scroll-key]").forEach((element) => {
        if (element.dataset.scrollKey === "boss.combat-log" && element.closest("details:not([open])")) return;
        restoreElementScroll(element);
      });
    });
  }

  function restoreFocus() {
    const savedFocus = focusRestore;
    focusRestore = null;
    if (!savedFocus) return;
    requestAnimationFrame(() => {
      if (savedFocus.type === "filter") {
        const filter = main.querySelector(`[data-filter="${CSS.escape(savedFocus.key)}"]`);
        filter?.focus({ preventScroll: true });
        if (filter?.setSelectionRange && savedFocus.start !== null && savedFocus.end !== null) {
          filter.setSelectionRange(savedFocus.start, savedFocus.end, savedFocus.direction || "none");
        }
        return;
      }
      const exact = main.querySelector(`[data-focus-key="${CSS.escape(savedFocus.key)}"]:not(:disabled)`);
      const fallback = savedFocus.key.startsWith("boss.")
        ? main.querySelector('[data-focus-key="boss.attack"]:not(:disabled)')
        : null;
      (exact || fallback)?.focus({ preventScroll: true });
    });
  }

  function setFilter(key, value) {
    state.filters[key] = value;
    saveUi();
  }

  function filterValue(key, fallback = "") {
    return state.filters[key] ?? fallback;
  }

  function updateTextFilter(filter) {
    setFilter(filter.dataset.filter, filter.value);
    render();
  }

  function setActionError(message = "") {
    window.clearTimeout(actionErrorTimer);
    state.actionError = String(message || "");
    updateShell();
    if (!state.actionError) {
      actionErrorTimer = null;
      return;
    }
    actionErrorTimer = window.setTimeout(() => {
      state.actionError = "";
      actionErrorTimer = null;
      updateShell();
    }, 4000);
  }

  function setBusy(value, control = null) {
    state.busy = value;
    main.classList.toggle("is-busy", value);
    document.querySelector("#refresh-button")?.toggleAttribute("disabled", value);
    if (value) {
      busyControl = control instanceof HTMLElement ? control : null;
      busyControl?.classList.add("is-loading");
      busyControl?.setAttribute("aria-busy", "true");
      return;
    }
    busyControl?.classList.remove("is-loading");
    busyControl?.removeAttribute("aria-busy");
    busyControl = null;
  }

  async function fetchBootstrap({ quiet = false, trigger = null } = {}) {
    if (!quiet) setBusy(true, trigger);
    try {
      const response = await fetch("/api/bootstrap/", { headers: { Accept: "application/json" } });
      const payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error(payload.message || "캐릭터를 불러오지 못했습니다.");
      state.profile = payload.profile;
      state.content = payload.content;
      state.bossSession = payload.boss_session;
      state.joinableSessions = payload.joinable_sessions || [];
      state.result = null;
      if (state.bossSession && !state.bossSession.completed && !state.bossSession.failed && !state.bossSession.cancelled) {
        state.tab = "boss";
      }
      render();
    } catch (error) {
      main.innerHTML = `<div class="empty-state"><div><strong>불러오지 못했습니다.</strong><p>${esc(error.message)}</p><button class="button" data-action="refresh">다시 시도</button></div></div>`;
    } finally {
      setBusy(false);
    }
  }

  async function perform(type, data = {}, { keepResult = false, trigger = null, quiet = false } = {}) {
    const control = trigger || document.activeElement?.closest?.("button, [data-action]");
    setBusy(true, control);
    try {
      const response = await fetch("/api/action/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(),
          Accept: "application/json",
        },
        body: JSON.stringify({ type, ...data }),
      });
      const payload = await response.json();
      if (payload.profile) state.profile = payload.profile;
      if (Object.hasOwn(payload, "boss_session")) state.bossSession = payload.boss_session;
      if (Object.hasOwn(payload, "joinable_sessions")) state.joinableSessions = payload.joinable_sessions || [];
      if (type === "enhancement_preview" || type === "restore_preview") {
        state.enhancementPreview = payload.result || null;
      } else if (type === "enhance" || type === "restore") {
        state.enhancementResult = payload.result || null;
        state.enhancementPreview = payload.result?.next_preview || null;
      } else if (!keepResult) {
        state.result = payload.result || null;
      }
      if (!quiet) {
        if (!payload.ok) {
          setActionError(payload.message || "요청을 처리하지 못했습니다.");
        } else if (state.actionError) {
          setActionError();
        }
      }
      render();
      if (type === "enhance") {
        requestAnimationFrame(() => document.querySelector("[data-enhance-shortcut]")?.focus({ preventScroll: true }));
      }
      return payload;
    } catch (error) {
      setActionError(error.message || "요청을 처리하지 못했습니다.");
      return null;
    } finally {
      setBusy(false);
    }
  }

  function navigate(tab) {
    if (tab === "more") {
      document.querySelector("#more-dialog")?.showModal();
      return;
    }
    captureScroll();
    state.tab = tab;
    const pageKey = `page:${tab}`;
    if (!Object.hasOwn(state.scroll, pageKey)) state.scroll[pageKey] = 0;
    saveUi();
    document.querySelector("#more-dialog")?.close();
    render();
    main.focus({ preventScroll: true });
  }

  function updateShell() {
    document.querySelectorAll("[data-nav]").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.nav === state.tab);
    });
    const profile = state.profile;
    if (!profile) return;
    const quickStatus = document.querySelector("#quick-status");
    quickStatus.classList.toggle("has-action-error", Boolean(state.actionError));
    if (state.actionError) {
      quickStatus.innerHTML = `<span class="quick-action-error" title="${esc(state.actionError)}">${esc(state.actionError)}</span>`;
      return;
    }
    quickStatus.innerHTML = [
      `<span><strong>${esc(profile.display_name)}</strong> Lv.${profile.level}</span>`,
      `<span>${number(profile.gold)}G</span>`,
      `<span>탐색 ${profile.daily_unlimited ? "∞" : number(profile.daily_remaining)}</span>`,
    ].join("");
  }

  function pageHeader(title, subtitle = "", actions = "") {
    return `<header class="page-head"><div><h1>${esc(title)}</h1>${subtitle ? `<p>${esc(subtitle)}</p>` : ""}</div>${actions ? `<div class="head-actions">${actions}</div>` : ""}</header>`;
  }

  function rarityTag(rarity, label) {
    return `<span class="tag" data-rarity="${esc(rarity)}">${esc(label || rarity)}</span>`;
  }

  function resultPanel(title, lines) {
    if (!lines || !lines.length) return "";
    return `<section class="section"><div class="result-panel"><h3>${esc(title)}</h3><pre>${esc(lines.join("\n"))}</pre></div></section>`;
  }

  function pickerHeading(label, visible, total, group) {
    const filtered = visible !== total;
    return `<div class="picker-heading"><span>${esc(label)}</span><strong>${number(visible)}${filtered ? ` / ${number(total)}` : ""}</strong>${filtered ? `<button class="filter-reset" type="button" data-clear-filter-group="${esc(group)}" title="필터 초기화" aria-label="필터 초기화">×</button>` : ""}</div>`;
  }

  function itemListRow(item, selected, attribute) {
    const stateText = item.destroyed ? "파괴 흔적" : item.equipped ? "장착" : "보유";
    return `<button class="master-row${item.uid === selected?.uid ? " is-selected" : ""}" ${attribute}="${item.uid}"><span class="rarity-bar" data-rarity="${esc(item.rarity)}"></span><span class="row-main"><span class="row-title">${esc(item.name)} <b>+${item.stars}</b></span><span class="row-meta">${esc(item.rarity_label)} · ${stateText} · ${esc(item.potential_grade_label || "잠재 없음")}</span></span><span class="row-side">${item.equipped ? "장착" : ""}</span></button>`;
  }

  function materialCostText(rows = []) {
    if (!rows.length) return "";
    return rows.map((row) => `${esc(row.name)} ${number(row.owned ?? 0)} / ${number(row.amount)}`).join(" · ");
  }

  function enhancementOutcome(result, itemUid) {
    if (!result || Number(result.item_uid) !== Number(itemUid)) return "";
    const labels = {
      success: ["success", "성공", `+${result.before_stars} → +${result.after_stars}`],
      failed: ["failed", "실패", `+${result.after_stars} 유지`],
      destroyed: ["destroyed", "파괴", `+${result.before_stars} 흔적 생성`],
      restored: ["success", "복구 완료", `+${result.after_stars} 복구`],
      missing_cost: ["failed", "재료 부족", "강화를 진행하지 못했습니다."],
      unavailable: ["failed", "사용 불가", "다른 강화 방식을 선택하세요."],
    };
    const [tone, title, detail] = labels[result.outcome] || ["failed", "처리 결과", result.outcome || "확인 필요"];
    const costs = [
      result.cost ? `${number(result.cost)}G` : "",
      ...(result.material_cost_rows || []).map((row) => `${esc(row.name)} ${number(row.amount)}개`),
    ].filter(Boolean);
    const completed = ["success", "failed", "destroyed", "restored"].includes(result.outcome);
    const transaction = costs.length ? `${completed ? "소모" : "필요"} ${costs.join(" · ")} · ` : "";
    return `<div class="enhance-outcome is-${tone}" role="status"><span>${title}</span><strong>${esc(detail)}</strong><small>${transaction}잔액 ${number(result.remaining_gold)}G</small></div>`;
  }

  function renderHome() {
    const p = state.profile;
    const expRatio = clamp(p.exp_progress / Math.max(1, p.exp_required), 0, 1);
    const equipped = p.inventory.filter((item) => item.equipped);
    const materialCount = p.materials.reduce((sum, row) => sum + row.amount, 0);
    return `<div class="page">
      <section class="profile-band">
        <div class="profile-identity">
          <h1>${esc(p.display_name)}</h1>
          <p>Lv.${p.level} · ${esc(p.job_name)} · T${p.job_tier}</p>
          <div class="progress-track" title="${number(p.exp_progress)} / ${number(p.exp_required)} EXP"><span style="width:${expRatio * 100}%"></span></div>
        </div>
        <div class="profile-metric"><span>전투 HP</span><strong>${number(p.stats.final_hp)}</strong></div>
        <div class="profile-metric"><span>골드</span><strong>${number(p.gold)}G</strong></div>
        <div class="profile-metric"><span>탐색</span><strong>${p.daily_unlimited ? "∞" : number(p.daily_remaining)}</strong></div>
      </section>

      <section class="section">
        <div class="section-head"><h2>바로가기</h2></div>
        <div class="activity-grid">
          <button class="action-tile" data-nav="explore"><strong>탐색</strong><span>남은 횟수 ${p.daily_unlimited ? "무제한" : number(p.daily_remaining)}</span></button>
          <button class="action-tile" data-nav="boss"><strong>보스</strong><span>${state.bossSession ? `${esc(state.bossSession.boss_name)} 진행 중` : "도전 가능한 보스 확인"}</span></button>
          <button class="action-tile" data-nav="equipment"><strong>장비</strong><span>${equipped.length}/${p.max_equipped_items} 장착 · ${p.inventory.length}개 보유</span></button>
          <button class="action-tile" data-nav="abilities"><strong>어빌리티</strong><span>${p.equipped_skill_ids.length}/${p.max_equipped_skills} + 특수 ${p.equipped_special_skill_id ? 1 : 0}/1</span></button>
          <button class="action-tile" data-nav="enhance"><strong>강화</strong><span>스타포스와 잠재능력</span></button>
          <button class="action-tile" data-nav="gacha"><strong>가챠</strong><span>${state.content.festival ? esc(state.content.festival.name) : "통상 가챠"}</span></button>
        </div>
      </section>

      <section class="section">
        <div class="section-head"><h2>현재 전투 스탯</h2></div>
        <div class="summary-grid">
          <div class="summary-cell"><span>기본 공격력</span><strong>${number(p.stats.base_atk)}</strong></div>
          <div class="summary-cell"><span>공격력</span><strong>${percent(p.stats.atk)}</strong></div>
          <div class="summary-cell"><span>방어력</span><strong>${percent(p.stats.defense)}</strong></div>
          <div class="summary-cell"><span>스킬 데미지</span><strong>${percent(p.stats.skill_damage)}</strong></div>
          <div class="summary-cell"><span>크리티컬</span><strong>${percent(Math.min(1, p.stats.critical_rate))}</strong></div>
          <div class="summary-cell"><span>체력 보너스</span><strong>${percent(p.stats.hp_bonus)}</strong></div>
          <div class="summary-cell"><span>장착 장비</span><strong>${equipped.length}</strong></div>
          <div class="summary-cell"><span>보유 재료</span><strong>${number(materialCount)}</strong></div>
        </div>
        <p class="combat-copy compact-copy">${esc(p.stats_text || "")}</p>
      </section>

      <section class="section">
        <div class="section-head"><h2>보유 재료</h2><span class="status-pill">${p.materials.length}종</span></div>
        <div class="entity-list material-list">
          ${p.materials.map((material) => `<div class="entity-card"><div><h3>${esc(material.name)}</h3><p>${esc(material.description || material.rarity_label)}</p></div><strong>${number(material.amount)}</strong></div>`).join("") || `<div class="empty-state">보유 재료 없음</div>`}
        </div>
      </section>
    </div>`;
  }

  function renderExplore() {
    const query = filterValue("explore.query");
    const rows = state.content.dungeons.filter((dungeon) => matches([dungeon.name, dungeon.description, dungeon.level], query));
    const selectedId = state.selected.dungeon;
    const selected = state.content.dungeons.find((row) => row.id === selectedId);
    const resultRows = state.result?.runs || [];
    return `<div class="page">
      ${pageHeader("탐색", `내 레벨 ${state.profile.level} · 남은 탐색 ${state.profile.daily_unlimited ? "무제한" : state.profile.daily_remaining}`)}
      <div class="workspace">
        <aside class="master-pane">
          ${pickerHeading("지역 목록", rows.length, state.content.dungeons.length, "explore")}<div class="master-tools"><input class="input search-input" value="${esc(query)}" placeholder="지역·몬스터 검색" data-filter="explore.query"></div>
          <div class="master-list" data-scroll-key="explore.list">
            ${rows.map((dungeon) => `<button class="master-row${selectedId === dungeon.id ? " is-selected" : ""}" data-select-dungeon="${esc(dungeon.id)}">
              <span class="rarity-bar"></span><span class="row-main"><span class="row-title">${esc(dungeon.name)}</span><span class="row-meta">Lv.${dungeon.level} · ${esc(dungeon.enemies.map((enemy) => enemy.name).join(", "))}</span></span><span class="row-side">${dungeon.level > state.profile.level ? "고레벨" : ""}</span>
            </button>`).join("") || `<div class="empty-state">검색 결과 없음</div>`}
          </div>
        </aside>
        <section class="detail-pane">
          ${selected ? `<div class="detail-header"><div><h2>${esc(selected.name)} <span class="tag">Lv.${selected.level}</span></h2><p>${esc(selected.description)}</p></div></div>
            <section class="section"><div class="section-head"><h2>출현 몬스터</h2></div><div class="entity-list">${selected.enemies.map((enemy) => `<div class="entity-card"><div><h3>${esc(enemy.name)}</h3>${enemy.rare ? `<p>희귀 몬스터</p>` : ""}</div>${enemy.rare ? `<span class="status-pill warning">RARE</span>` : ""}</div>`).join("")}</div></section>
            <div class="operation-bar"><div class="operation-metrics"><div><span>내 레벨</span><strong>Lv.${state.profile.level}</strong></div><div><span>지역 레벨</span><strong>Lv.${selected.level}</strong></div><div><span>남은 탐색</span><strong>${state.profile.daily_unlimited ? "∞" : number(state.profile.daily_remaining)}</strong></div></div><div class="button-row"><button class="button" data-action="explore" data-count="1" data-dungeon-id="${esc(selected.id)}">1회</button><button class="button button-primary" data-action="explore" data-count="7" data-dungeon-id="${esc(selected.id)}">7회 탐색</button></div></div>
            ${resultPanel("최근 탐색", resultRows.flatMap((run, index) => {
              const reward = run.reward || {};
              const drops = [...(reward.items || []), ...(reward.materials || []).map((row) => `${row.name} x${row.amount}`)];
              return [`${index + 1}. ${run.enemy} · ${run.won ? "승리" : "패배"} · ${run.turns}턴 · HP ${run.player_hp}`, `   ${number(reward.gold)}G · ${number(reward.exp)}EXP${drops.length ? ` · ${drops.join(", ")}` : ""}`];
            }))}` : `<div class="empty-state">지역을 선택하세요.</div>`}
        </section>
      </div>
    </div>`;
  }

  function bossVariant(base, difficulty) {
    return base?.variants.find((variant) => variant.difficulty === difficulty) || base?.variants[0] || null;
  }

  function effectText(...values) {
    const lines = values
      .map((value) => String(value || "").trim())
      .filter((value) => value && value !== "없음");
    return lines.join("\n") || "없음";
  }

  function renderCombatDetails(session, terminal = false) {
    const bossUi = ensureBossUi(session);
    const log = session.log || [];
    const logStartIndex = Number(session.log_start_index || 0);
    const logRows = log.map((text, index) => ({ id: logStartIndex + index, text })).reverse();
    const detail = session.damage_detail;
    const detailText = detail
      ? [
        detail.action,
        detail.summary,
        ...(detail.detail_lines || []),
        detail.received_summary,
        ...(detail.received_detail_lines || []),
      ].filter(Boolean).join("\n")
      : "";
    return `<details class="combat-sidebar combat-details${terminal ? " combat-details-terminal" : ""}" data-boss-session-id="${esc(session.id)}" ${bossUi.combatDetailsOpen ? "open" : ""}>
      <summary><span>전투 기록 · 피해 상세</span><small>${esc(log.at(-1) || "기록 없음")}</small></summary>
      <div class="combat-detail-body">
        <div class="section-head"><div><h2>전투 로그</h2><p class="section-copy">최신 기록이 위에 표시됩니다.</p></div></div>
        <div class="log-list" data-scroll-key="boss.combat-log">${logRows.map((row, index) => `<div class="log-line${index === 0 ? " is-latest" : ""}" data-log-id="${row.id}">${esc(row.text)}</div>`).join("") || `<p class="combat-copy">아직 전투 기록이 없습니다.</p>`}</div>
        ${detailText ? `<div class="damage-details"><h3>최근 피해 계산</h3><p class="combat-copy">${esc(detailText)}</p></div>` : ""}
      </div>
    </details>`;
  }

  function renderBossSession(session) {
    ensureBossUi(session);
    const player = session.participant;
    const terminal = session.completed || session.failed || session.cancelled;
    const bossHpPercent = clamp(session.boss_hp_ratio * 100, 0, 100);
    const playerHpRatio = player ? clamp(player.hp / Math.max(1, player.max_hp), 0, 1) : 0;
    const playerHpPercent = playerHpRatio * 100;
    const playerHpTone = playerHpRatio <= 0.25 ? "danger" : playerHpRatio <= 0.55 ? "warning" : "healthy";
    const bossState = player ? effectText(player.boss_effects, player.boss_stacks) : "없음";
    const playerState = player ? effectText(player.player_effects, player.player_stacks) : "없음";
    const battleState = session.completed ? "클리어" : session.failed ? "패배" : session.cancelled ? "취소" : session.started ? `${player?.turn || 1}턴` : "준비";
    return `<div class="boss-combat">
      <div class="boss-title-row boss-hud-head"><div><div class="boss-name-line"><h2>${esc(session.boss_name)}</h2><span class="tag">${esc(session.difficulty_label)}</span>${session.practice ? `<span class="status-pill">연습</span>` : ""}</div><span class="section-copy">Lv.${session.boss_level}${player?.ct !== null && player?.ct !== undefined ? ` · CT ${player.ct}/${player.ct_max}` : ""}</span></div><span class="status-pill ${session.completed ? "success" : session.failed || session.cancelled ? "danger" : "warning"}">${battleState}</span></div>
      <div class="boss-hp vital-block"><div class="vital-label"><span>보스 HP</span><strong>${number(session.boss_hp)} / ${number(session.boss_max_hp)} <small>${bossHpPercent.toFixed(1)}%</small></strong></div><div class="hp-track boss-health" role="progressbar" aria-label="보스 체력" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${bossHpPercent.toFixed(1)}"><span style="width:${bossHpPercent}%"></span></div></div>
      ${!session.started && !terminal ? `<section class="section"><div class="entity-list">${session.participants.map((member) => `<div class="entity-card"><div><h3>${esc(member.name)} Lv.${member.level}</h3></div><span class="status-pill">참전</span></div>`).join("")}</div><div class="button-row" style="margin-top:12px">${session.is_owner ? `<button class="button button-primary" data-action="boss_start">시작</button><button class="button" data-action="boss_skip">스킵</button>` : ""}<button class="button button-danger" data-action="boss_cancel">취소</button></div></section>` : ""}
      ${session.started && !terminal && player ? `<div class="combat-columns combat-hud-layout">
        <div class="combat-main combat-hud">
          <div class="player-vitals vital-block">
            <div class="vital-label"><span><strong>${esc(state.profile.display_name)}</strong> · Lv.${state.profile.level}</span><strong>${number(player.hp)} / ${number(player.max_hp)} <small>${playerHpPercent.toFixed(1)}%</small></strong></div>
            <div class="hp-track player-health ${playerHpTone}" role="progressbar" aria-label="내 체력" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${playerHpPercent.toFixed(1)}"><span style="width:${playerHpPercent}%"></span></div>
          </div>
          <div class="combat-status-grid">
            <div class="boss-state-strip"><span>보스 상태</span><p>${esc(bossState)}</p>${player.hp_lock ? `<small>${esc(player.hp_lock)}</small>` : ""}</div>
            <div class="omen-panel${player.warning ? " is-active" : ""}"><div class="omen-heading"><strong>전조</strong><span>${player.warning ? "해제 조건 확인" : "없음"}</span></div><p>${esc(player.warning || "현재 발동 중인 전조가 없습니다.")}</p></div>
            <div class="player-state-block"><span>내 상태</span><p>${esc(playerState)}</p></div>
          </div>
          <section class="combat-action-section"><div class="combat-primary-actions"><button class="button button-primary combat-command" data-action="boss_attack" data-focus-key="boss.attack" ${player.alive ? "" : "disabled"}>공격</button><button class="button combat-command" data-action="boss_guard" data-focus-key="boss.guard" ${player.alive ? "" : "disabled"}>가드</button></div><button class="button button-quiet combat-leave" data-confirm-action="boss_leave" data-confirm-title="보스전 포기" data-confirm-message="현재 보스전에서 나갑니다. 보상은 받을 수 없습니다.">전투 포기</button></section>
          <section class="combat-abilities hud-abilities"><div class="section-head"><h2>어빌리티</h2><span class="status-pill">${number(session.skills.length)}개</span></div><div class="ability-grid">${session.skills.map((skill) => `<button class="ability-button ${skill.ready ? "is-ready" : "is-cooling"}" data-action="boss_ability" data-skill-id="${esc(skill.id)}" data-focus-key="boss.ability:${esc(skill.id)}" ${skill.ready ? "" : "disabled"}><span class="ability-button-head"><strong>${esc(skill.name)}</strong><span class="ability-state">${esc(skill.state)}</span></span><span class="ability-summary">${esc(skill.summary || "효과 정보 없음")}</span></button>`).join("") || `<p class="combat-copy">장착 어빌리티 없음</p>`}</div></section>
        </div>
        ${renderCombatDetails(session)}
      </div>` : ""}
      ${terminal ? `<section class="section"><div class="result-panel"><h3>${session.completed ? "클리어" : session.failed ? "패배" : "종료"}</h3><pre>${esc(session.rewards[state.profile.user_id] || session.log.at(-1) || "보상 없음")}</pre></div><div class="button-row" style="margin-top:12px"><button class="button" data-action="boss_panel_reset">보스 목록으로</button></div></section>${renderCombatDetails(session, true)}` : ""}
    </div>`;
  }

  function renderBoss() {
    if (state.bossSession) {
      return `<div class="page boss-page">${renderBossSession(state.bossSession)}</div>`;
    }
    clearBossUi();
    const query = filterValue("boss.query");
    const rows = state.content.bosses.filter((boss) => matches([boss.name, ...boss.variants.map((variant) => variant.description)], query));
    const selectedBase = state.content.bosses.find((boss) => boss.base_id === state.selected.bossBase);
    const difficulty = state.selected.bossDifficulty || "normal";
    const selected = bossVariant(selectedBase, difficulty);
    const remaining = selectedBase ? state.profile.weekly_remaining[selectedBase.base_id] : null;
    const batchResult = state.result?.skipped ? [
      ...(state.result.skipped || []).map((name) => `${name} · 완료`),
      ...(state.result.failures || []),
    ] : [];
    return `<div class="page">
      ${pageHeader("보스", "일반과 하드는 주간 자발 횟수를 공유합니다.", `<button class="button" data-action="boss_batch_skip">일괄 스킵</button>`)}
      <div class="workspace">
        <aside class="master-pane">${pickerHeading("보스 목록", rows.length, state.content.bosses.length, "boss")}<div class="master-tools"><input class="input search-input" value="${esc(query)}" placeholder="보스 검색" data-filter="boss.query"></div><div class="master-list" data-scroll-key="boss.list">
          ${rows.map((boss) => `<button class="master-row${boss.base_id === state.selected.bossBase ? " is-selected" : ""}" data-select-boss="${esc(boss.base_id)}"><span class="rarity-bar" data-rarity="${boss.variants.some((row) => row.difficulty === "hard") ? "unique" : "normal"}"></span><span class="row-main"><span class="row-title">${esc(boss.name)}</span><span class="row-meta">${boss.variants.map((row) => `${row.difficulty_label} Lv.${row.level}`).join(" · ")}</span></span><span class="row-side">${state.profile.weekly_remaining[boss.base_id] < 0 ? "∞" : `${state.profile.weekly_remaining[boss.base_id]}/1`}</span></button>`).join("")}
        </div></aside>
        <section class="detail-pane">
          ${selected ? `<div class="detail-header"><div><h2>${esc(selectedBase.name)}</h2><p>${esc(selected.description)}</p></div><div class="segmented">${selectedBase.variants.map((variant) => `<button data-boss-difficulty="${esc(variant.difficulty)}" class="${variant.id === selected.id ? "is-active" : ""}">${esc(variant.difficulty_label)}</button>`).join("")}</div></div>
            <div class="stat-grid"><div class="stat-cell"><span>권장 레벨</span><strong>Lv.${selected.level}</strong></div><div class="stat-cell"><span>자발</span><strong>${remaining < 0 ? "∞" : `${remaining}/1`}</strong></div><div class="stat-cell"><span>골드</span><strong>${number(selected.gold)}G</strong></div><div class="stat-cell"><span>경험치</span><strong>${number(selected.exp)}</strong></div></div>
            <section class="section"><div class="section-head"><h2>보상</h2></div><div class="material-list">${selected.rewards.map((reward) => `<div class="entity-card"><h3>${esc(reward)}</h3></div>`).join("") || `<p class="section-copy">고정 보상만 존재합니다.</p>`}</div></section>
            <section class="section"><div class="button-row"><button class="button button-primary" data-action="boss_create" data-boss-id="${esc(selected.id)}">자발 준비</button><button class="button" data-action="boss_practice" data-boss-id="${esc(selected.id)}">연습 준비</button></div></section>
            ${state.joinableSessions.length ? `<section class="section"><div class="section-head"><h2>참가 가능한 파티</h2></div><div class="entity-list">${state.joinableSessions.map((row) => `<div class="entity-card"><div><h3>${esc(row.boss_name)} [${esc(row.difficulty)}]</h3><p>${esc(row.owner)} · ${row.participants}명${row.practice ? " · 연습" : ""}</p></div><button class="button" data-action="boss_join" data-session-id="${row.id}">참가</button></div>`).join("")}</div></section>` : ""}` : `<div class="empty-state">보스를 선택하세요.</div>`}
          ${resultPanel("일괄 스킵 결과", batchResult)}
        </section>
      </div>
    </div>`;
  }

  function equipmentRows() {
    const query = filterValue("equipment.query");
    const rarity = filterValue("equipment.rarity", "all");
    const status = filterValue("equipment.status", "all");
    return state.profile.inventory.filter((item) => {
      if (rarity !== "all" && item.rarity !== rarity) return false;
      if (status === "equipped" && !item.equipped) return false;
      if (status === "owned" && item.equipped) return false;
      if (status === "destroyed" && !item.destroyed) return false;
      if (status !== "destroyed" && status !== "all" && item.destroyed) return false;
      return matches([item.name, item.template_id, item.potential_text, item.stats_text], query);
    });
  }

  function renderEquipment() {
    const mode = state.selected.equipmentMode || "equip";
    const rows = equipmentRows();
    const sellableRows = rows.filter((item) => !item.equipped && !item.destroyed && !item.unsellable);
    const sellableGold = sellableRows.reduce((sum, item) => sum + Number(item.sell_price || 0), 0);
    const selected = state.profile.inventory.find((item) => item.uid === Number(state.selected.itemUid));
    const rarityOptions = state.content.rarities.map((row) => `<option value="${esc(row.id)}" ${filterValue("equipment.rarity", "all") === row.id ? "selected" : ""}>${esc(row.name)}</option>`).join("");
    return `<div class="page">
      ${pageHeader("장비", `${state.profile.inventory.length}개 보유 · ${state.profile.equipped_item_uids.length}/${state.profile.max_equipped_items} 장착`, `<div class="head-action-stack"><div class="segmented"><button class="${mode === "equip" ? "is-active" : ""}" data-equipment-mode="equip">장착</button><button class="${mode === "sell" ? "is-active" : ""}" data-equipment-mode="sell">판매</button><button class="${mode === "auto" ? "is-active" : ""}" data-equipment-mode="auto">자동판매</button></div>${mode === "sell" ? `<button class="button button-danger" data-confirm-action="sell_filtered" data-confirm-title="필터 결과 일괄 판매" data-confirm-message="현재 검색 및 필터 결과의 장비 ${sellableRows.length}개를 ${number(sellableGold)}G에 판매합니다." ${sellableRows.length ? "" : "disabled"}>결과 ${sellableRows.length}개 판매</button>` : ""}</div>`)}
      ${mode === "auto" ? renderAutoSell() : `<div class="workspace">
        <aside class="master-pane">${pickerHeading("장비 목록", rows.length, state.profile.inventory.length, "equipment")}<div class="master-tools"><input class="input search-input" value="${esc(filterValue("equipment.query"))}" placeholder="이름·능력치·잠재 검색" data-filter="equipment.query"><div class="filter-row"><select class="select" data-filter="equipment.rarity"><option value="all">모든 등급</option>${rarityOptions}</select><select class="select" data-filter="equipment.status"><option value="all">모든 상태</option><option value="equipped" ${filterValue("equipment.status") === "equipped" ? "selected" : ""}>장착</option><option value="owned" ${filterValue("equipment.status") === "owned" ? "selected" : ""}>보유</option><option value="destroyed" ${filterValue("equipment.status") === "destroyed" ? "selected" : ""}>파괴 흔적</option></select></div></div><div class="master-list" data-scroll-key="equipment.list">
          ${rows.map((item) => itemListRow(item, selected, "data-select-item")).join("") || `<div class="empty-list">조건에 맞는 장비가 없습니다.</div>`}
        </div></aside>
        <section class="detail-pane">${selected ? renderItemDetail(selected, mode) : `<div class="empty-state">장비를 선택하세요.</div>`}</section>
      </div>`}
    </div>`;
  }

  function renderItemDetail(item, mode) {
    const status = item.destroyed ? "파괴 흔적" : item.equipped ? "장착 중" : "보유 중";
    const sellDisabled = item.equipped || item.destroyed || item.unsellable;
    const sellLabel = item.unsellable ? "판매 불가" : `${number(item.sell_price)}G`;
    return `<div class="detail-header"><div><h2>${esc(item.name)}${item.stars ? ` +${item.stars}` : ""}</h2></div>${rarityTag(item.rarity, item.rarity_label)}</div>
      <section class="section"><div class="section-head"><h2>능력치</h2></div><p class="combat-copy">${esc(item.stats_text || "없음")}</p></section>
      ${item.effects_text ? `<section class="section"><div class="section-head"><h2>영속 효과</h2></div><p class="combat-copy">${esc(item.effects_text)}</p></section>` : ""}
      <section class="section"><div class="section-head"><h2>잠재능력</h2>${item.potential_grade ? rarityTag(item.potential_grade, item.potential_grade_label) : ""}</div><p class="combat-copy">${esc(item.potential_text || "없음")}</p></section>
      <div class="operation-bar equipment-operation"><div class="operation-metrics"><div><span>상태</span><strong>${status}</strong></div><div><span>판매가</span><strong>${sellLabel}</strong></div><div><span>장비 점수</span><strong>${number(item.score)}</strong></div></div><div class="button-row"><button class="button ${mode === "equip" && !item.equipped ? "button-primary" : ""}" data-action="equipment_toggle" data-item-uid="${item.uid}" ${item.destroyed ? "disabled" : ""}>${item.equipped ? "장착 해제" : "장착"}</button><button class="button button-danger" data-confirm-action="sell_one" data-item-uid="${item.uid}" data-confirm-title="장비 판매" data-confirm-message="${esc(item.name)}을 ${number(item.sell_price)}G에 판매합니다." ${sellDisabled ? "disabled" : ""}>${sellDisabled ? sellLabel : `${number(item.sell_price)}G에 판매`}</button>${mode === "equip" ? `<button class="button" data-action="equipment_auto">자동 장착</button>` : ""}</div></div>`;
  }

  function renderAutoSell() {
    const selected = new Set(state.profile.auto_sell_rarities);
    return `<section class="section"><div class="section-head"><div><h2>자동판매 등급</h2><p class="section-copy">가챠와 드랍에서 획득 즉시 골드로 정산됩니다.</p></div></div><div class="entity-list">${state.content.rarities.map((row) => `<label class="entity-card check-row"><input type="checkbox" data-auto-sell-rarity="${esc(row.id)}" ${selected.has(row.id) ? "checked" : ""}><span><h3>${esc(row.name)}</h3></span>${rarityTag(row.id, row.name)}</label>`).join("")}</div><div class="button-row" style="margin-top:14px"><button class="button" data-confirm-action="auto_sell_now" data-confirm-title="보유 장비 일괄 판매" data-confirm-message="현재 자동판매 설정에 해당하는 미장착 장비를 판매합니다.">현재 장비 일괄 판매</button></div></section>`;
  }

  function renderAbilities() {
    const query = filterValue("abilities.query");
    const role = filterValue("abilities.role", "all");
    const unlocked = new Set(state.profile.unlocked_skill_ids);
    const unlockedSpecial = new Set(state.profile.unlocked_special_skill_ids);
    const equipped = new Set(state.profile.equipped_skill_ids);
    const equippedSpecial = state.profile.equipped_special_skill_id;
    const roleLabels = { attack: "공격", buff: "강화", debuff: "약화", heal: "회복" };
    const roleLabel = (value) => roleLabels[value] || value;
    const available = state.content.skills.filter((skill) => (skill.special ? unlockedSpecial.has(skill.id) : unlocked.has(skill.id)));
    const roles = [...new Set(available.map((skill) => skill.role).filter(Boolean))].sort((left, right) => roleLabel(left).localeCompare(roleLabel(right), "ko"));
    const visible = available.filter((skill) => (role === "all" || skill.role === role) && matches([skill.name, skill.summary, skill.note, skill.role, roleLabel(skill.role)], query));
    const skills = visible
      .filter((skill) => !skill.special)
      .sort((left, right) => Number(equipped.has(right.id)) - Number(equipped.has(left.id)) || left.level - right.level || left.name.localeCompare(right.name, "ko"));
    const specials = visible
      .filter((skill) => skill.special)
      .sort((left, right) => Number(right.id === equippedSpecial) - Number(left.id === equippedSpecial) || left.level - right.level || left.name.localeCompare(right.name, "ko"));
    const skillDescription = (skill) => `<span class="skill-copy"><h3>${esc(skill.name)}</h3><p class="skill-effect">${esc(skill.summary || "효과 정보 없음")}</p>${skill.note ? `<p class="skill-note">${esc(skill.note)}</p>` : ""}</span>`;
    return `<div class="page">
      ${pageHeader("어빌리티", `${equipped.size}/${state.profile.max_equipped_skills} 장착 · 특수 ${equippedSpecial ? "1/1" : "0/1"}`, `<div class="ability-filters"><input class="input search-input" value="${esc(query)}" placeholder="이름·효과 검색" aria-label="어빌리티 검색" data-filter="abilities.query"><select class="select" aria-label="어빌리티 역할 필터" data-filter="abilities.role"><option value="all">모든 역할</option>${roles.map((value) => `<option value="${esc(value)}" ${role === value ? "selected" : ""}>${esc(roleLabel(value))}</option>`).join("")}</select></div>`)}
      <section class="section"><div class="section-head"><h2>일반 어빌리티</h2><span class="status-pill">${number(skills.length)}개</span></div><div class="skill-list">${skills.map((skill) => `<label class="skill-row${equipped.has(skill.id) ? " is-equipped" : ""}"><input type="checkbox" data-skill-id="${esc(skill.id)}" ${equipped.has(skill.id) ? "checked" : ""}>${skillDescription(skill)}<span class="status-pill">${esc(roleLabel(skill.role))}</span></label>`).join("") || `<p class="section-copy">조건에 맞는 일반 어빌리티가 없습니다.</p>`}</div></section>
      <section class="section"><div class="section-head"><h2>특수 어빌리티</h2><span class="status-pill">${number(specials.length)}개</span></div><div class="skill-list"><label class="skill-row${equippedSpecial ? "" : " is-equipped"}"><input type="radio" name="special-skill" data-special-skill-id="" ${equippedSpecial ? "" : "checked"}><span class="skill-copy"><h3>장착 안 함</h3><p class="skill-effect">특수 어빌리티 슬롯을 비웁니다.</p></span><span class="status-pill">해제</span></label>${specials.map((skill) => `<label class="skill-row${equippedSpecial === skill.id ? " is-equipped" : ""}"><input type="radio" name="special-skill" data-special-skill-id="${esc(skill.id)}" ${equippedSpecial === skill.id ? "checked" : ""}>${skillDescription(skill)}<span class="status-pill warning">${esc(roleLabel(skill.role))} · 특수</span></label>`).join("")}</div></section>
    </div>`;
  }

  function enhancementItems(mode) {
    if (mode === "restore") return state.profile.inventory.filter((item) => item.destroyed);
    if (mode === "potential") return state.profile.inventory.filter((item) => !item.destroyed);
    return state.profile.inventory;
  }

  function renderEnhance() {
    const mode = state.selected.enhanceMode || "star";
    const query = filterValue("enhance.query");
    const rarity = filterValue("enhance.rarity", "all");
    const status = filterValue("enhance.status", "all");
    const available = enhancementItems(mode);
    const rows = available.filter((item) => {
      if (rarity !== "all" && item.rarity !== rarity) return false;
      if (status === "equipped" && !item.equipped) return false;
      if (status === "owned" && (item.equipped || item.destroyed)) return false;
      if (status === "destroyed" && !item.destroyed) return false;
      return matches([item.name, item.template_id, item.rarity_label, item.potential_text, item.stats_text], query);
    });
    const selected = available.find((item) => item.uid === Number(state.selected.enhanceItemUid));
    const rarityOptions = state.content.rarities.map((row) => `<option value="${esc(row.id)}" ${rarity === row.id ? "selected" : ""}>${esc(row.name)}</option>`).join("");
    return `<div class="page">
      ${pageHeader("강화", `보유 골드 ${number(state.profile.gold)}G`, `<div class="segmented"><button class="${mode === "star" ? "is-active" : ""}" data-enhance-mode="star">스타포스</button><button class="${mode === "potential" ? "is-active" : ""}" data-enhance-mode="potential">잠재능력</button><button class="${mode === "restore" ? "is-active" : ""}" data-enhance-mode="restore">흔적 복구</button></div>`)}
      <div class="workspace enhance-workspace"><aside class="master-pane">${pickerHeading("장비 목록", rows.length, available.length, "enhance")}<div class="master-tools"><input class="input search-input" value="${esc(query)}" placeholder="이름·능력치·잠재 검색" data-filter="enhance.query"><div class="filter-row"><select class="select" data-filter="enhance.rarity"><option value="all">모든 등급</option>${rarityOptions}</select><select class="select" data-filter="enhance.status"><option value="all">모든 상태</option><option value="equipped" ${status === "equipped" ? "selected" : ""}>장착</option><option value="owned" ${status === "owned" ? "selected" : ""}>보유</option><option value="destroyed" ${status === "destroyed" ? "selected" : ""}>파괴 흔적</option></select></div></div><div class="master-list" data-scroll-key="enhance.list">${rows.map((item) => itemListRow(item, selected, "data-select-enhance-item")).join("") || `<div class="empty-list">조건에 맞는 장비가 없습니다.</div>`}</div></aside><section class="detail-pane">${selected ? (mode === "star" ? renderStarforce(selected) : mode === "potential" ? renderPotential(selected) : renderRestore(selected)) : `<div class="empty-state">왼쪽 목록에서 장비를 선택하세요.</div>`}</section></div>
    </div>`;
  }

  function renderStarforce(item) {
    const methodId = state.selected.enhanceMethod || state.content.enhancement_methods[0]?.id || "";
    const preview = state.enhancementPreview?.item_uid === item.uid && (!state.enhancementPreview.method_id || state.enhancementPreview.method_id === methodId) ? state.enhancementPreview : null;
    const result = enhancementOutcome(state.enhancementResult, item.uid);
    if (item.destroyed) {
      return `<div class="enhance-console">${result}<div class="enhance-title"><div><span class="eyebrow">파괴 흔적</span><h2>${esc(item.name)} <b>+${item.stars}</b></h2><p>${esc(item.stats_text)}</p></div>${rarityTag(item.rarity, item.rarity_label)}</div><div class="warning-box">동일한 장비 스페어를 사용하면 +${Math.max(0, item.stars - 3)}로 복구됩니다.</div><div class="enhance-actions"><button class="button button-primary" data-enhance-mode="restore">흔적 복구로 이동</button></div></div>`;
    }
    const afterGold = preview ? state.profile.gold - preview.cost : state.profile.gold;
    const confirmation = preview ? `${item.name} +${item.stars} → +${preview.after_stars}\n소모 ${number(preview.cost)}G · 성공 ${percent(preview.odds.success)} · 실패 ${percent(preview.odds.fail)} · 파괴 ${percent(preview.odds.destroy)}` : `${item.name} 강화를 시도합니다.`;
    return `<div class="enhance-console">${result}<div class="enhance-title"><div><span class="eyebrow">스타포스</span><h2>${esc(item.name)} <b>+${item.stars}</b></h2><p>${item.equipped ? "장착 중 · " : ""}${esc(item.stats_text)}</p></div>${rarityTag(item.rarity, item.rarity_label)}</div>
      ${item.enhancement_disabled ? `<div class="warning-box">이 장비는 스타포스 강화가 불가능합니다.</div>` : `<div class="enhance-method"><label class="field"><span>강화 방식</span><select class="select" data-enhancement-method>${state.content.enhancement_methods.map((method) => `<option value="${esc(method.id)}" ${method.id === methodId ? "selected" : ""}>${esc(method.name)}</option>`).join("")}</select></label></div>
      ${preview ? `<div class="enhance-ledger"><div><span>보유 골드</span><strong>${number(state.profile.gold)}G</strong></div><div><span>소모 골드</span><strong class="cost">-${number(preview.cost)}G</strong></div><div><span>강화 후 잔액</span><strong>${number(afterGold)}G</strong></div></div>
      <div class="chance-grid"><div class="chance success"><span>성공</span><strong>${percent(preview.odds.success)}</strong></div><div class="chance fail"><span>실패</span><strong>${percent(preview.odds.fail)}</strong></div><div class="chance destroy"><span>파괴</span><strong>${percent(preview.odds.destroy)}</strong></div></div><div class="chance-track" aria-hidden="true"><span class="success" style="width:${preview.odds.success * 100}%"></span><span class="fail" style="width:${preview.odds.fail * 100}%"></span><span class="destroy" style="width:${preview.odds.destroy * 100}%"></span></div>
      ${preview.material_cost_rows?.length ? `<div class="enhance-materials"><span>소모 재료</span><strong>${materialCostText(preview.material_cost_rows)}</strong></div>` : ""}<div class="enhance-delta"><span>성공 시 변화</span><p>${esc(preview.delta_text || "능력치 변동 없음")}</p></div>${preview.ok ? "" : `<div class="warning-box">${esc(preview.message)}</div>`}<div class="enhance-actions"><button class="button button-primary enhance-submit" data-confirm-action="enhance" data-enhance-shortcut data-item-uid="${item.uid}" data-confirm-title="스타포스 강화" data-confirm-message="${esc(confirmation)}" aria-keyshortcuts="Enter Space" ${preview.ok ? "" : "disabled"}>+${item.stars} → +${preview.after_stars} 강화</button></div>` : `<div class="enhance-loading"><span class="spinner"></span><p>강화 정보를 불러오는 중</p></div>`}`}</div>`;
  }

  function renderPotential(item) {
    const pending = state.profile.pending_potential;
    const thisPending = pending?.item_uid === item.uid ? pending : null;
    const progress = item.potential_progress || "보장 없음";
    const oneCost = Number(item.potential_reroll_cost || 0);
    const threeCost = oneCost * 3;
    const requiredGrade = pending?.required_grade || "";
    const requiredLabel = thisPending?.candidates.find((candidate) => candidate.grade === requiredGrade)?.grade_label || requiredGrade;
    const pendingItem = requiredGrade ? state.profile.inventory.find((candidate) => candidate.uid === Number(pending.item_uid)) : null;
    const choiceRequiredHere = Boolean(requiredGrade && thisPending);
    const choiceRequiredElsewhere = Boolean(requiredGrade && !thisPending);
    const rerollLocked = choiceRequiredHere || choiceRequiredElsewhere;
    const candidateGrid = thisPending ? `<div class="potential-grid">${thisPending.candidates.map((candidate) => {
      const eligible = !requiredGrade || candidate.grade === requiredGrade;
      return `<div class="potential-candidate${candidate.tier_up ? " is-tier-up" : ""}${eligible ? "" : " is-unavailable"}" ${eligible ? "" : `aria-disabled="true"`}><h3>${esc(candidate.grade_label)}${candidate.tier_up ? ` <span class="status-pill success">등급 상승</span>` : ""}${eligible ? "" : ` <span class="status-pill danger">선택 불가</span>`}</h3><div class="potential-lines">${esc(candidate.text)}</div><button class="button ${eligible ? "button-primary" : ""}" data-action="potential_apply" data-candidate-index="${candidate.index}" ${eligible ? "" : "disabled"}>${eligible ? "이 능력 적용" : "상승 등급만 선택 가능"}</button></div>`;
    }).join("")}</div>` : `<div class="empty-result">재설정 결과가 이 자리에 표시됩니다.</div>`;
    return `<div class="enhance-console"><div class="enhance-title"><div><span class="eyebrow">잠재능력</span><h2>${esc(item.name)} <b>+${item.stars}</b></h2><p>${item.equipped ? "장착 중 · " : ""}${esc(item.potential_grade_label || "잠재 없음")}</p></div>${item.potential_grade ? rarityTag(item.potential_grade, item.potential_grade_label) : ""}</div>
      <div class="potential-overview"><div class="current-potential"><div class="section-head"><h3>현재 잠재능력</h3><span class="status-pill">등급업 ${esc(progress)}</span></div><div class="potential-lines">${esc(item.potential_text || "잠재능력 없음")}</div></div><div class="potential-wallet"><div><span>보유 골드</span><strong>${number(state.profile.gold)}G</strong></div><div><span>1회 비용</span><strong>${number(item.potential_reroll_cost)}G</strong></div><div><span>3회 비용</span><strong>${number(item.potential_reroll_cost * 3)}G</strong></div></div></div>
      ${item.potential_locked ? `<div class="warning-box">현재 단계에서는 잠재능력을 재설정할 수 없습니다.</div>` : `<section class="potential-workbench" aria-labelledby="potential-workbench-title"><div class="memorial-head"><div><h3 id="potential-workbench-title">메모리얼 후보 선택</h3><p class="section-copy">재설정과 후보 적용을 이 영역에서 진행합니다.</p></div><div class="button-row potential-reroll-actions"><button class="button" data-action="potential_roll" data-item-uid="${item.uid}" data-count="1" ${rerollLocked || state.profile.gold < oneCost ? "disabled" : ""}>1회 · ${number(oneCost)}G</button><button class="button button-primary" data-action="potential_roll" data-item-uid="${item.uid}" data-count="3" ${rerollLocked || state.profile.gold < threeCost ? "disabled" : ""}>3회 · ${number(threeCost)}G</button></div></div>${choiceRequiredHere ? `<div class="warning-box potential-required" role="alert"><strong>후보 선택 필수</strong>\n등급이 상승했습니다. ${esc(requiredLabel)} 등급 후보 중 하나를 적용해야 다른 재설정을 진행할 수 있습니다.</div>` : ""}${choiceRequiredElsewhere ? `<div class="warning-box potential-required" role="alert"><strong>후보 선택 필수</strong>\n${esc(pendingItem?.name || "다른 장비")}에서 상승 등급 후보를 먼저 적용해 주세요.</div>` : ""}${candidateGrid}</section>`}</div>`;
  }

  function renderRestore(item) {
    const spares = state.profile.inventory.filter((candidate) => !candidate.destroyed && !candidate.equipped && candidate.template_id === item.template_id && candidate.uid !== item.uid);
    const spareUid = Number(state.selected.restoreSpareUid || spares[0]?.uid || 0);
    const preview = state.enhancementPreview?.item_uid === item.uid ? state.enhancementPreview : null;
    const result = enhancementOutcome(state.enhancementResult, item.uid);
    const afterGold = preview ? state.profile.gold - preview.cost : state.profile.gold;
    return `<div class="enhance-console">${result}<div class="enhance-title"><div><span class="eyebrow">흔적 복구</span><h2>${esc(item.name)} <b>+${item.stars}</b></h2><p>복구 결과 +${Math.max(0, item.stars - 3)}</p></div><span class="status-pill danger">파괴 흔적</span></div>
      <div class="enhance-method"><label class="field"><span>소모할 스페어</span><select class="select" data-restore-spare>${spares.length ? spares.map((spare) => `<option value="${spare.uid}" ${spare.uid === spareUid ? "selected" : ""}>${esc(spare.name)} +${spare.stars} · ${esc(spare.potential_grade_label || "잠재 없음")}</option>`).join("") : `<option value="">사용 가능한 스페어 없음</option>`}</select></label></div>
      ${preview ? `<div class="enhance-ledger"><div><span>보유 골드</span><strong>${number(state.profile.gold)}G</strong></div><div><span>소모 골드</span><strong class="cost">-${number(preview.cost)}G</strong></div><div><span>복구 후 잔액</span><strong>${number(afterGold)}G</strong></div></div><div class="restore-summary"><div><span>파괴 전 성급</span><strong>+${preview.before_stars}</strong></div><div><span>복구 성급</span><strong>+${preview.after_stars}</strong></div></div>${preview.ok ? "" : `<div class="warning-box">${esc(preview.message)}</div>`}<div class="enhance-actions"><button class="button button-primary enhance-submit" data-confirm-action="restore" data-item-uid="${item.uid}" data-spare-uid="${spareUid}" data-confirm-title="흔적 복구" data-confirm-message="${esc(`${item.name} 흔적을 +${preview.after_stars}로 복구합니다.\n동일 장비 1개 · ${number(preview.cost)}G 소모`)}" ${spareUid && preview.ok ? "" : "disabled"}>+${preview.after_stars}로 복구</button></div>` : spares.length ? `<div class="enhance-loading"><span class="spinner"></span><p>복구 정보를 불러오는 중</p></div>` : `<div class="warning-box">복구에 사용할 동일 장비 스페어가 없습니다.</div>`}</div>`;
  }

  function renderGacha() {
    const selectedPool = state.content.gacha_pools.find((pool) => pool.id === state.selected.gachaPool) || state.content.gacha_pools[0];
    const festival = state.content.festival;
    const owned = state.profile.material_amounts[selectedPool?.cost_material_id] || 0;
    const result = state.result;
    return `<div class="page">
      ${pageHeader("가챠", selectedPool ? `${esc(selectedPool.cost_material_name)} ${number(owned)}개` : "")}
      ${festival ? `<section class="section"><div class="detail-header"><div><h2>${esc(festival.name)}</h2><p>${esc(festival.description)}</p></div><span class="status-pill warning">FES</span></div><p class="combat-copy">${esc([festival.period, ...festival.overrides.map((row) => `${row.name} ${(row.chance * 100).toFixed(2)}%`)].filter(Boolean).join("\n"))}</p></section>` : ""}
      <div class="gacha-console"><div class="gacha-pool-head"><div><span class="eyebrow">가챠 풀</span><h2>${esc(selectedPool?.name || "가챠 없음")}</h2><p>${esc(selectedPool?.description || "")}</p></div><div class="segmented">${state.content.gacha_pools.map((pool) => `<button data-gacha-pool="${esc(pool.id)}" class="${pool.id === selectedPool?.id ? "is-active" : ""}">${esc(pool.name)}</button>`).join("")}</div></div>${selectedPool ? `<div class="gacha-wallet"><span>보유 ${esc(selectedPool.cost_material_name)}</span><strong>${number(owned)}</strong></div><div class="draw-grid">${selectedPool.draw_options.map((draws) => { const cost = Math.ceil(selectedPool.base_cost * draws / Math.max(1, selectedPool.base_draws)); return `<button class="draw-option${draws === selectedPool.base_draws ? " is-primary" : ""}" data-action="gacha" data-pool-id="${esc(selectedPool.id)}" data-draws="${draws}" ${owned < cost ? "disabled" : ""}><strong>${draws}회</strong><span>${number(cost)} ${esc(selectedPool.cost_material_name)}</span></button>`; }).join("")}</div>` : ""}${result && (result.items || result.materials) ? `<div class="gacha-result"><h3>가챠 결과</h3><pre>${esc([...(result.items || []), ...(result.materials || []).map((row) => `${row.name} x${row.amount}`), result.auto_sold_count ? `자동판매 ${result.auto_sold_count}개 · ${number(result.auto_sold_gold)}G` : ""].filter(Boolean).join("\n") || "획득 없음")}</pre></div>` : ""}</div>
    </div>`;
  }

  function renderCraft() {
    const query = filterValue("craft.query");
    const rarity = filterValue("craft.rarity", "all");
    const rows = state.content.recipes.filter((recipe) => (rarity === "all" || recipe.result_rarity === rarity) && matches([recipe.name, recipe.result_name, recipe.description, ...recipe.materials.map((material) => material.name)], query));
    const selected = state.content.recipes.find((recipe) => recipe.id === state.selected.recipe);
    let detail = `<div class="empty-state">제작품을 선택하세요.</div>`;
    if (selected) {
      const materialRows = selected.materials.map((row) => {
        const owned = Number(state.profile.material_amounts[row.id] || 0);
        return { ...row, owned, missing: Math.max(0, Number(row.amount) - owned) };
      });
      const missingMaterials = materialRows.filter((row) => row.missing > 0);
      const missingGold = Math.max(0, Number(selected.gold) - Number(state.profile.gold));
      const canCraft = missingGold === 0 && missingMaterials.length === 0;
      const shortages = [
        missingGold ? `골드 ${number(missingGold)}G` : "",
        ...missingMaterials.map((row) => `${row.name} ${number(row.missing)}개`),
      ].filter(Boolean);
      const materialSummary = selected.materials.map((row) => `${row.name} ${number(row.amount)}개`).join(" · ");
      const confirmation = `${selected.result_name}을 제작합니다.\n${number(selected.gold)}G${materialSummary ? ` · ${materialSummary}` : ""}를 소모합니다.`;
      detail = `<div class="detail-header"><div><h2>${esc(selected.result_name)} +${selected.result_stars}</h2><p>${esc(selected.description)}</p></div>${rarityTag(selected.result_rarity, state.content.rarities.find((row) => row.id === selected.result_rarity)?.name)}</div><section class="section"><div class="section-head"><h2>필요 재료</h2><span class="status-pill ${canCraft ? "success" : "danger"}">${canCraft ? "제작 가능" : "재료 부족"}</span></div><div class="entity-list">${materialRows.map((row) => `<div class="entity-card${row.missing ? " is-missing" : ""}"><div><h3>${esc(row.name)}</h3>${row.missing ? `<p>${number(row.missing)}개 부족</p>` : ""}</div><span class="status-pill ${row.missing ? "danger" : "success"}">${number(row.owned)} / ${number(row.amount)}</span></div>`).join("")}</div></section>${canCraft ? "" : `<div class="warning-box craft-shortage" role="status"><strong>제작 조건 부족</strong>\n${esc(shortages.join(" · "))}</div>`}<div class="operation-bar craft-operation${canCraft ? "" : " is-unavailable"}"><div class="operation-metrics"><div><span>보유 골드</span><strong>${number(state.profile.gold)}G</strong></div><div><span>제작 비용</span><strong>${number(selected.gold)}G</strong></div><div><span>제작 후 잔액</span><strong>${number(state.profile.gold - selected.gold)}G</strong></div></div><button class="button button-primary" data-confirm-action="craft" data-recipe-id="${esc(selected.id)}" data-confirm-title="장비 제작" data-confirm-message="${esc(confirmation)}" ${canCraft ? "" : "disabled"}>${canCraft ? "제작" : "비용 부족"}</button></div>`;
    }
    return `<div class="page">${pageHeader("제작", `보유 골드 ${number(state.profile.gold)}G`)}<div class="workspace"><aside class="master-pane">${pickerHeading("제작 목록", rows.length, state.content.recipes.length, "craft")}<div class="master-tools"><input class="input search-input" value="${esc(query)}" placeholder="제작품·설명·재료 검색" data-filter="craft.query"><select class="select" data-filter="craft.rarity"><option value="all">모든 등급</option>${state.content.rarities.map((row) => `<option value="${row.id}" ${rarity === row.id ? "selected" : ""}>${esc(row.name)}</option>`).join("")}</select></div><div class="master-list" data-scroll-key="craft.list">${rows.map((recipe) => `<button class="master-row${selected?.id === recipe.id ? " is-selected" : ""}" data-select-recipe="${esc(recipe.id)}"><span class="rarity-bar" data-rarity="${esc(recipe.result_rarity)}"></span><span class="row-main"><span class="row-title">${esc(recipe.result_name)} <b>+${recipe.result_stars}</b></span><span class="row-meta">${esc(recipe.name)} · Lv.${recipe.level}</span></span><span class="row-side">${number(recipe.gold)}G</span></button>`).join("") || `<div class="empty-list">조건에 맞는 제작품이 없습니다.</div>`}</div></aside><section class="detail-pane">${detail}</section></div></div>`;
  }

  function renderJobs() {
    const mode = state.selected.jobMode || "advance";
    const ids = new Set(mode === "free" ? state.profile.free_advance_job_ids : state.profile.available_job_ids);
    const jobs = state.content.jobs.filter((job) => ids.has(job.id));
    return `<div class="page">${pageHeader("전직", `${esc(state.profile.job_name)} · T${state.profile.job_tier}`, `<div class="segmented"><button class="${mode === "advance" ? "is-active" : ""}" data-job-mode="advance">전직</button><button class="${mode === "free" ? "is-active" : ""}" data-job-mode="free">자유전직</button></div>`)}<section class="section"><div class="entity-list">${jobs.map((job) => `<div class="entity-card"><div><h3>${esc(job.name)} · T${job.tier}</h3><p>Lv.${job.level} · ${esc(job.stats_text)}${job.description ? `\n${esc(job.description)}` : ""}</p></div><button class="button button-primary" data-confirm-action="${mode === "free" ? "job_free_advance" : "job_advance"}" data-job-id="${esc(job.id)}" data-confirm-title="${mode === "free" ? "자유전직" : "전직"}" data-confirm-message="${esc(job.name)}(으)로 전직합니다.">선택</button></div>`).join("") || `<div class="empty-state">현재 선택할 수 있는 직업이 없습니다.</div>`}</div></section></div>`;
  }

  function renderLiberation() {
    const liberation = state.profile.liberation;
    const stageName = ["미수령", "미해방", "1차 해방", "2차 해방"][liberation.stage + 1] || "미수령";
    return `<div class="page">${pageHeader("제네시스 해방", liberation.item_name ? `${esc(liberation.item_name)} · ${stageName}` : esc(liberation.target_item_name || ""))}<section class="section">${liberation.item_uid ? `<div class="stat-grid"><div class="stat-cell"><span>현재 단계</span><strong>${esc(stageName)}</strong></div><div class="stat-cell"><span>무기</span><strong>${esc(liberation.item_name)}</strong></div></div>${liberation.next_stage ? `<section class="section"><div class="section-head"><h2>${esc(liberation.next_stage.name)} · +${liberation.next_stage.stars}</h2></div><div class="entity-list">${Object.entries(liberation.next_stage.materials).map(([id, amount]) => { const owned = state.profile.material_amounts[id] || 0; const name = state.profile.materials.find((row) => row.id === id)?.name || id; return `<div class="entity-card"><h3>${esc(name)}</h3><span class="status-pill ${owned >= amount ? "success" : "danger"}">${number(owned)} / ${number(amount)}</span></div>`; }).join("")}</div><div class="button-row" style="margin-top:14px"><button class="button button-primary" data-confirm-action="liberation_advance" data-confirm-title="제네시스 해방" data-confirm-message="재료를 소모해 다음 해방 단계를 진행합니다.">해방 진행</button></div></section>` : `<div class="result-panel"><h3>해방 완료</h3><pre>제네시스 무기의 모든 해방을 마쳤습니다.</pre></div>`}` : `<div class="empty-state"><div><strong>${liberation.claimable ? "제네시스 무기 수령 가능" : "검은 마법사 처치 기록 필요"}</strong>${liberation.claimable ? `<div style="margin-top:14px"><button class="button button-primary" data-action="liberation_claim">${esc(liberation.target_item_name)} 수령</button></div>` : ""}</div></div>`}</section></div>`;
  }

  function queueEnhancementPreview() {
    if (state.tab !== "enhance" || state.busy) return;
    const mode = state.selected.enhanceMode || "star";
    if (mode !== "star" && mode !== "restore") return;
    const item = state.profile.inventory.find((row) => row.uid === Number(state.selected.enhanceItemUid));
    if (!item) return;

    if (mode === "star") {
      if (item.destroyed || item.enhancement_disabled) return;
      const methodId = state.selected.enhanceMethod || state.content.enhancement_methods[0]?.id || "";
      if (state.enhancementPreview?.item_uid === item.uid && state.enhancementPreview?.method_id === methodId) return;
      const key = `star:${item.uid}:${methodId}`;
      if (previewLoadKey === key) return;
      previewLoadKey = key;
      requestAnimationFrame(async () => {
        try {
          await perform("enhancement_preview", { item_uid: item.uid, method_id: methodId }, { keepResult: true, quiet: true });
        } finally {
          if (previewLoadKey === key) previewLoadKey = "";
        }
      });
      return;
    }

    const spares = state.profile.inventory.filter((candidate) => !candidate.destroyed && !candidate.equipped && candidate.template_id === item.template_id && candidate.uid !== item.uid);
    const spareUid = Number(state.selected.restoreSpareUid || spares[0]?.uid || 0);
    if (!spareUid) return;
    if (state.enhancementPreview?.item_uid === item.uid && state.enhancementPreview?.spare_uid === spareUid) return;
    const key = `restore:${item.uid}:${spareUid}`;
    if (previewLoadKey === key) return;
    previewLoadKey = key;
    requestAnimationFrame(async () => {
      try {
        await perform("restore_preview", { item_uid: item.uid, spare_uid: spareUid }, { keepResult: true, quiet: true });
      } finally {
        if (previewLoadKey === key) previewLoadKey = "";
      }
    });
  }

  function render() {
    if (!state.profile || !state.content) return;
    if (composingFilter?.isConnected) return;
    captureBossUi();
    if (renderedTab) captureScroll(renderedTab);
    if (renderedTab === state.tab) captureFocus();
    else focusRestore = null;
    const renderers = {
      home: renderHome,
      explore: renderExplore,
      boss: renderBoss,
      equipment: renderEquipment,
      abilities: renderAbilities,
      enhance: renderEnhance,
      gacha: renderGacha,
      craft: renderCraft,
      jobs: renderJobs,
      liberation: renderLiberation,
    };
    main.innerHTML = (renderers[state.tab] || renderHome)();
    renderedTab = state.tab;
    updateShell();
    saveUi();
    restoreScroll();
    restoreFocus();
    queueEnhancementPreview();
  }

  async function confirmAction(element) {
    const dialog = document.querySelector("#confirm-dialog");
    document.querySelector("#confirm-title").textContent = element.dataset.confirmTitle || "확인";
    document.querySelector("#confirm-message").textContent = element.dataset.confirmMessage || "계속 진행합니다.";
    dialog.returnValue = "";
    if (element.dataset.confirmAction === "enhance") dialog.dataset.enhanceShortcut = "true";
    else delete dialog.dataset.enhanceShortcut;
    dialog.showModal();
    requestAnimationFrame(() => dialog.querySelector('[value="confirm"]')?.focus({ preventScroll: true }));
    const result = await new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue === "confirm"), { once: true }));
    delete dialog.dataset.enhanceShortcut;
    if (!result) return;
    await runAction(element.dataset.confirmAction, element);
  }

  async function runAction(action, element) {
    const request = (type, data = {}, options = {}) => perform(type, data, { ...options, trigger: element });
    if (action === "refresh") return fetchBootstrap({ trigger: element });
    if (action === "explore") return request("explore", { dungeon_id: element.dataset.dungeonId, count: Number(element.dataset.count) });
    if (action === "boss_create" || action === "boss_practice") return request("boss_create", { boss_id: element.dataset.bossId, practice: action === "boss_practice" });
    if (action === "boss_join") return request("boss_join", { session_id: Number(element.dataset.sessionId) });
    if (["boss_start", "boss_skip", "boss_attack", "boss_guard", "boss_cancel", "boss_leave", "boss_batch_skip"].includes(action)) return request(action);
    if (action === "boss_ability") return request("boss_ability", { skill_id: element.dataset.skillId });
    if (action === "boss_panel_reset") { state.bossSession = null; state.result = null; return fetchBootstrap({ quiet: true }); }
    if (action === "equipment_toggle") {
      const uid = Number(element.dataset.itemUid);
      const selected = new Set(state.profile.equipped_item_uids);
      selected.has(uid) ? selected.delete(uid) : selected.add(uid);
      return request("equipment_set", { uids: [...selected] });
    }
    if (action === "equipment_auto") return request("equipment_auto");
    if (action === "sell_one") return request("sell", { uids: [Number(element.dataset.itemUid)] });
    if (action === "sell_filtered") {
      const uids = equipmentRows()
        .filter((item) => !item.equipped && !item.destroyed && !item.unsellable)
        .map((item) => item.uid);
      return request("sell", { uids });
    }
    if (action === "auto_sell_now") return request("auto_sell_now");
    if (action === "gacha") return request("gacha", { pool_id: element.dataset.poolId, draws: Number(element.dataset.draws) });
    if (action === "craft") return request("craft", { recipe_id: element.dataset.recipeId });
    if (action === "job_advance" || action === "job_free_advance") return request(action, { job_id: element.dataset.jobId });
    if (action === "liberation_claim" || action === "liberation_advance") return request(action);
    if (action === "enhancement_preview") return request("enhancement_preview", { item_uid: Number(element.dataset.itemUid), method_id: state.selected.enhanceMethod || state.content.enhancement_methods[0]?.id });
    if (action === "enhance") return request("enhance", { item_uid: Number(element.dataset.itemUid), method_id: state.selected.enhanceMethod || state.content.enhancement_methods[0]?.id });
    if (action === "restore_preview") return request("restore_preview", { item_uid: Number(element.dataset.itemUid), spare_uid: Number(element.dataset.spareUid || state.selected.restoreSpareUid || 0) });
    if (action === "restore") return request("restore", { item_uid: Number(element.dataset.itemUid), spare_uid: Number(element.dataset.spareUid || state.selected.restoreSpareUid || 0) });
    if (action === "potential_roll") return request("potential_roll", { item_uid: Number(element.dataset.itemUid), count: Number(element.dataset.count) });
    if (action === "potential_apply") return request("potential_apply", { candidate_index: Number(element.dataset.candidateIndex) });
  }

  document.addEventListener("toggle", (event) => {
    const details = event.target instanceof Element
      ? event.target.closest("details[data-boss-session-id]")
      : null;
    if (!details) return;
    const bossUi = ensureBossUi({ id: details.dataset.bossSessionId });
    bossUi.combatDetailsOpen = details.open;
    const combatLog = details.querySelector('[data-scroll-key="boss.combat-log"]');
    if (details.open && combatLog) requestAnimationFrame(() => restoreElementScroll(combatLog));
    saveUi();
  }, true);

  document.addEventListener("scroll", (event) => {
    const scroller = event.target instanceof HTMLElement && event.target.matches("[data-scroll-key]")
      ? event.target
      : null;
    if (scroller) captureElementScroll(scroller);
  }, { capture: true, passive: true });

  window.addEventListener("pagehide", () => {
    captureBossUi();
    captureScroll();
    saveUi();
  });

  document.addEventListener("click", async (event) => {
    const pressed = event.target.closest("button, .button, .action-tile, .master-row");
    if (state.busy && pressed) {
      event.preventDefault();
      return;
    }
    const clearFilters = event.target.closest("[data-clear-filter-group]");
    if (clearFilters) {
      event.preventDefault();
      const prefix = `${clearFilters.dataset.clearFilterGroup}.`;
      Object.keys(state.filters).forEach((key) => {
        if (key.startsWith(prefix)) delete state.filters[key];
      });
      saveUi();
      render();
      return;
    }
    const nav = event.target.closest("[data-nav]");
    if (nav) {
      event.preventDefault();
      navigate(nav.dataset.nav);
      return;
    }
    const confirm = event.target.closest("[data-confirm-action]");
    if (confirm && !confirm.disabled) {
      event.preventDefault();
      await confirmAction(confirm);
      return;
    }
    const action = event.target.closest("[data-action]");
    if (action && !action.disabled) {
      event.preventDefault();
      await runAction(action.dataset.action, action);
      return;
    }
    const selectors = [
      ["selectDungeon", "dungeon"], ["selectBoss", "bossBase"], ["selectItem", "itemUid"],
      ["selectEnhanceItem", "enhanceItemUid"], ["selectRecipe", "recipe"],
    ];
    for (const [datasetKey, stateKey] of selectors) {
      const target = event.target.closest(`[data-${datasetKey.replace(/[A-Z]/g, (letter) => `-${letter.toLowerCase()}`)}]`);
      if (target) {
        captureScroll();
        state.selected[stateKey] = target.dataset[datasetKey];
        state.enhancementPreview = null;
        saveUi();
        render();
        return;
      }
    }
    const difficulty = event.target.closest("[data-boss-difficulty]");
    if (difficulty) { state.selected.bossDifficulty = difficulty.dataset.bossDifficulty; render(); return; }
    const equipmentMode = event.target.closest("[data-equipment-mode]");
    if (equipmentMode) { state.selected.equipmentMode = equipmentMode.dataset.equipmentMode; render(); return; }
    const enhanceMode = event.target.closest("[data-enhance-mode]");
    if (enhanceMode) { state.selected.enhanceMode = enhanceMode.dataset.enhanceMode; state.enhancementPreview = null; saveUi(); render(); return; }
    const gachaPool = event.target.closest("[data-gacha-pool]");
    if (gachaPool) { state.selected.gachaPool = gachaPool.dataset.gachaPool; state.result = null; render(); return; }
    const jobMode = event.target.closest("[data-job-mode]");
    if (jobMode) { state.selected.jobMode = jobMode.dataset.jobMode; render(); }
  });

  document.addEventListener("input", (event) => {
    const filter = event.target.closest("[data-filter]");
    if (!filter || !filter.isConnected || filter.tagName === "SELECT" || event.isComposing) return;
    updateTextFilter(filter);
  });

  document.addEventListener("compositionstart", (event) => {
    const filter = event.target.closest("[data-filter]");
    if (!filter || filter.tagName === "SELECT") return;
    composingFilter = filter;
  });

  document.addEventListener("compositionend", (event) => {
    const filter = event.target.closest("[data-filter]");
    if (!filter || filter.tagName === "SELECT") return;
    composingFilter = null;
    updateTextFilter(filter);
  });

  document.addEventListener("change", async (event) => {
    const filter = event.target.closest("select[data-filter]");
    if (filter) { setFilter(filter.dataset.filter, filter.value); render(); return; }
    if (event.target.matches("[data-auto-sell-rarity]")) {
      const selected = [...document.querySelectorAll("[data-auto-sell-rarity]:checked")].map((input) => input.dataset.autoSellRarity);
      await perform("auto_sell_set", { rarities: selected });
      return;
    }
    if (event.target.matches("[data-skill-id]")) {
      const selected = new Set(state.profile.equipped_skill_ids);
      if (event.target.checked) selected.add(event.target.dataset.skillId);
      else selected.delete(event.target.dataset.skillId);
      if (selected.size > state.profile.max_equipped_skills) {
        event.target.checked = false;
        setActionError(`어빌리티는 최대 ${state.profile.max_equipped_skills}개까지 장착할 수 있습니다.`);
        return;
      }
      await perform("skills_set", { skill_ids: [...selected] });
      return;
    }
    if (event.target.matches("[data-special-skill-id]")) {
      await perform("special_skill_set", { skill_id: event.target.dataset.specialSkillId });
      return;
    }
    if (event.target.matches("[data-enhancement-method]")) {
      state.selected.enhanceMethod = event.target.value;
      state.enhancementPreview = null;
      saveUi();
      const uid = Number(state.selected.enhanceItemUid || 0);
      if (uid) await perform("enhancement_preview", { item_uid: uid, method_id: event.target.value }, { keepResult: true, quiet: true });
      return;
    }
    if (event.target.matches("[data-restore-spare]")) {
      state.selected.restoreSpareUid = Number(event.target.value || 0);
      state.enhancementPreview = null;
      saveUi();
      render();
    }
  });

  document.addEventListener("keydown", async (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const typing = event.target instanceof HTMLElement && Boolean(event.target.closest("input, textarea, select"));
    const dialog = document.querySelector("#confirm-dialog");
    const shortcut = document.querySelector("[data-enhance-shortcut]:not(:disabled)");
    const focusedShortcut = event.target instanceof HTMLElement && event.target.closest("[data-enhance-shortcut]") === shortcut;
    const focusedCombatAction = event.target instanceof HTMLElement && Boolean(event.target.closest('[data-focus-key^="boss."]'));
    const passiveTarget = !(event.target instanceof HTMLElement) || !event.target.closest("button, a, summary, [role='button']");
    const shortcutReady = !state.busy && state.tab === "enhance" && (state.selected.enhanceMode || "star") === "star" && !typing && Boolean(shortcut);
    const enhanceDialogOpen = dialog?.open && dialog.dataset.enhanceShortcut === "true";
    if (event.repeat) {
      if (!typing && (focusedCombatAction || enhanceDialogOpen || (shortcutReady && (focusedShortcut || passiveTarget)))) event.preventDefault();
      return;
    }
    if (enhanceDialogOpen) {
      event.preventDefault();
      dialog.close("confirm");
      return;
    }
    if (dialog?.open) return;
    if (!shortcutReady || (!focusedShortcut && !passiveTarget)) return;
    event.preventDefault();
    await confirmAction(shortcut);
  });

  document.querySelector("#refresh-button")?.addEventListener("click", () => fetchBootstrap());
  fetchBootstrap();
})();
