const TABS = [
  { id: "items", label: "장비" },
  { id: "materials", label: "재료" },
  { id: "crafting_recipes", label: "제작" },
  { id: "enhancement", label: "강화" },
  { id: "gacha", label: "가챠" },
  { id: "dungeons", label: "던전" },
  { id: "bosses", label: "보스" },
  { id: "stack_effects", label: "스택 효과" },
  { id: "jobs", label: "직업" },
  { id: "skills", label: "스킬" },
  { id: "advanced", label: "전역 JSON" },
];

const ADVANCED_KEYS = [
  "settings",
  "stats",
  "rarities",
  "level_curve",
  "player",
  "stat_allocation",
  "gacha",
];

const GOLD_COST_MODES = [
  ["formula", "등급/성급 공식"],
  ["fixed", "고정 골드"],
  ["none", "골드 없음"],
];

const ENHANCEMENT_ODDS_MODES = [
  ["formula", "기본 확률 공식"],
  ["fixed", "직접 지정"],
];

const GACHA_ENTRY_TYPES = [
  ["item", "지정 장비 목록"],
  ["item_rarity", "장비 등급"],
  ["material", "지정 재료 목록"],
  ["material_rarity", "재료 등급"],
];

const GACHA_FESTIVAL_OVERRIDE_TYPES = [
  ["item_rarity", "장비 등급"],
  ["material_rarity", "재료 등급"],
  ["item", "지정 장비"],
  ["material", "지정 재료"],
];

const OBJECTIVES = [
  ["damage", "이번 턴 피해량"],
  ["hits", "타수"],
  ["debuff", "디버프 횟수"],
  ["dispel", "디스펠 횟수"],
  ["clear_all", "클리어 올 횟수"],
  ["triple_attack", "트리플 어택 횟수"],
  ["double_attack", "더블 어택 횟수"],
  ["ability", "어빌리티 사용 횟수"],
  ["ability_damage", "어빌리티 피해량"],
  ["warning_success", "전조 성공"],
  ["warning_failure", "전조 실패"],
];

const STACK_OBJECTIVES = [
  ...OBJECTIVES,
  ["received_damage", "받은 피해량"],
];

const EFFECT_ACTIONS = [
  ["dispel", "디스펠"],
  ["clear_all", "클리어 올"],
  ["stack_increase", "스택 증가"],
  ["stack_decrease", "스택 감소"],
  ["stack_set", "스택 지정"],
  ["stack_remove", "스택 제거"],
  ["stack_max", "스택 최대"],
];

const EFFECT_TARGETS = [
  ["self", "나/시전자"],
  ["enemy", "상대"],
  ["allies", "참전자 모두"],
  ["opponents", "상대 전체"],
];

const STAT_EFFECT_TARGETS = [
  ["self", "나"],
  ["allies", "참전자 모두"],
];

const STACK_CONDITION_TARGETS = [
  ["self", "내가 행동할 때"],
  ["opponent", "상대가 행동할 때"],
];

const STACK_RECEIVED_DAMAGE_TARGETS = [
  ["self", "내가 피해받을 때"],
  ["opponent", "상대가 피해받을 때"],
];

const STACK_OPERATIONS = [
  ["increase", "증가"],
  ["decrease", "감소"],
  ["set", "지정"],
  ["remove", "제거"],
  ["max", "최대"],
];

const SKILL_ROLES = [
  "attack",
  "buff",
  "debuff",
  "defense",
  "heal",
];

const HEAL_CAP_MODES = [
  ["none", "상한 없음"],
  ["flat", "고정값"],
  ["max_hp_ratio", "최대 HP 비율"],
];

const PLAIN_DAMAGE_MODES = [
  ["none", "없음"],
  ["flat", "고정값"],
  ["target_max_hp_ratio", "대상 최대 HP 비율"],
];

const FAILURE_STACK_TARGETS = [
  ["boss", "보스 스택"],
  ["player", "유저 스택"],
];

const WARNING_ACTIVATION_CONDITIONS = [
  ["stack", "스택 수"],
  ["stack_compare", "스택 비교"],
  ["turn_multiple", "턴 배수"],
  ["turn_range", "턴 범위"],
  ["boss_hp_ratio", "보스 HP 비율"],
  ["ct_ready", "CT 충전 여부"],
];

const STACK_COMPARE_OPERATORS = [
  ["majority", "과반"],
  ["gte", "이상"],
  ["gt", "초과"],
  ["lte", "이하"],
  ["lt", "미만"],
  ["eq", "같음"],
];

const ACTION_STACK_CONDITION_TARGETS = [
  ["self", "시전자 스택"],
  ["enemy", "대상 스택"],
  ["allies", "시전자 측 전체"],
  ["opponents", "상대 측 전체"],
];

const GUARD_MODES = [
  ["duration", "지속 턴"],
  ["count", "방어 횟수"],
];

const JOB_LEVEL_BY_TIER = {
  1: 1,
  2: 3,
  3: 10,
  4: 25,
  5: 50,
};

const DEFAULT_LEVEL_DAMAGE_MULTIPLIERS = [1, 1.05, 1.1, 1.15, 1.2, 1.25];

const ID_PATTERN = /^[A-Za-z0-9_-]+$/;

function normalizeIdValue(value) {
  const raw = String(value ?? "");
  const decomposed = typeof raw.normalize === "function" ? raw.normalize("NFKD") : raw;
  return decomposed
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, "_")
    .toLowerCase();
}

function normalizeBooleanValue(value, defaultValue = false) {
  if (value == null) {
    return defaultValue;
  }
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "y", "on"].includes(normalized)) {
      return true;
    }
    if (["0", "false", "no", "n", "off"].includes(normalized)) {
      return false;
    }
  }
  return Boolean(value);
}

function normalizeInputElement(input, normalizer) {
  const original = input.value;
  const normalized = normalizer(original);
  if (normalized === original) {
    return normalized;
  }
  const start = input.selectionStart;
  const end = input.selectionEnd;
  input.value = normalized;
  if (typeof start === "number" && typeof end === "number") {
    input.setSelectionRange(Math.min(start, normalized.length), Math.min(end, normalized.length));
  }
  return normalized;
}

function normalizeInputValue(event, normalizer) {
  return normalizeInputElement(event.target, normalizer);
}

function normalizePastedInput(event, normalizer) {
  const input = event.target;
  requestAnimationFrame(() => {
    const original = input.value;
    const normalized = normalizeInputElement(input, normalizer);
    if (normalized !== original) {
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
  });
}

const state = {
  content: null,
  tab: "items",
  selected: {},
  query: "",
  queryByTab: {},
  itemRarityFilter: "",
  listScroll: {},
  openDetails: {},
  pendingFocusMove: null,
  dirty: false,
  saving: false,
};

const nav = document.getElementById("nav");
const main = document.getElementById("main");
const dirtyState = document.getElementById("dirtyState");
const statusText = document.getElementById("statusText");
const toast = document.getElementById("toast");

document.getElementById("reloadBtn").addEventListener("click", loadContent);
document.getElementById("validateBtn").addEventListener("click", validateContent);
document.getElementById("saveBtn").addEventListener("click", saveContent);

document.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
    event.preventDefault();
    if (!event.repeat) {
      saveContent();
    }
    return;
  }
  if (event.key === "Tab") {
    state.pendingFocusMove = {
      direction: event.shiftKey ? -1 : 1,
      time: Date.now(),
    };
  }
});

window.addEventListener("beforeunload", (event) => {
  if (!state.dirty) {
    return;
  }
  event.preventDefault();
  event.returnValue = "";
});

loadContent();

async function loadContent() {
  setStatus("불러오는 중...");
  try {
    const response = await fetch("/api/content");
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    const payload = await response.json();
    if (!payload.ok) {
      throw new Error((payload.errors || []).join("\n") || "알 수 없는 오류");
    }
    state.content = payload.content;
    normalizeContentForUi(state.content);
    state.dirty = false;
    state.query = "";
    state.queryByTab = {};
    state.itemRarityFilter = "";
    state.openDetails = {};
    ensureSelections();
    setStatus("콘텐츠를 불러왔습니다.");
    render({ preserveScroll: false });
  } catch (error) {
    showLoadError(error);
  }
}

async function validateContent() {
  if (!state.content) {
    return;
  }
  const payload = await postJson("/api/validate", { content: state.content });
  if (payload.ok) {
    showToast("검증 통과", false);
    setStatus("검증 통과");
    return;
  }
  showToast(`검증 실패\n${payload.errors.join("\n")}`, true);
  setStatus(`검증 실패 ${payload.errors.length}건`);
}

async function saveContent() {
  if (!state.content || state.saving) {
    return;
  }
  state.saving = true;
  setStatus("저장 중...");
  try {
    const payload = await postJson("/api/save", { content: state.content });
    if (payload.ok) {
      state.dirty = false;
      updateDirty();
      showToast(`저장 완료\n백업: ${payload.backup}`, false);
      setStatus("저장 완료");
      return;
    }
    showToast(`저장 실패\n${payload.errors.join("\n")}`, true);
    setStatus("저장 실패");
  } catch (error) {
    showToast(`저장 실패\n${error.message}`, true);
    setStatus("저장 실패");
  } finally {
    state.saving = false;
  }
}

async function postJson(path, data) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return response.json();
}

function render(options = {}) {
  const preserveScroll = options.preserveScroll ?? true;
  const scrollSnapshot = preserveScroll ? captureScrollSnapshot() : null;
  renderNav();
  updateDirty();
  if (!state.content) {
    main.replaceChildren(el("div", { className: "empty" }, "콘텐츠를 불러오는 중입니다."));
    restoreScrollSnapshot(scrollSnapshot);
    return;
  }
  ensureSelections();
  if (state.tab === "items") {
    renderItems();
  } else if (state.tab === "materials") {
    renderMaterials();
  } else if (state.tab === "crafting_recipes") {
    renderRecipes();
  } else if (state.tab === "enhancement") {
    renderEnhancement();
  } else if (state.tab === "gacha") {
    renderGacha();
  } else if (state.tab === "dungeons") {
    renderDungeons();
  } else if (state.tab === "bosses") {
    renderBosses();
  } else if (state.tab === "stack_effects") {
    renderStackEffects();
  } else if (state.tab === "jobs") {
    renderJobs();
  } else if (state.tab === "skills") {
    renderSkills();
  } else {
    renderAdvanced();
  }
  restoreScrollSnapshot(scrollSnapshot);
}

function captureScrollSnapshot() {
  const focus = captureFocusSnapshot();
  return {
    windowX: window.scrollX || 0,
    windowY: window.scrollY || document.documentElement.scrollTop || document.body.scrollTop || 0,
    mainTop: main.scrollTop || 0,
    mainLeft: main.scrollLeft || 0,
    detailTop: document.getElementById("detailPanel")?.scrollTop || 0,
    detailLeft: document.getElementById("detailPanel")?.scrollLeft || 0,
    focus,
    entityLists: Array.from(main.querySelectorAll(".entity-list[data-key]")).map((list) => ({
      key: list.dataset.key,
      top: list.scrollTop || 0,
      left: list.scrollLeft || 0,
    })),
  };
}

function restoreScrollSnapshot(snapshot) {
  if (!snapshot) {
    return;
  }
  const apply = (restoreFocus = false) => {
    main.scrollTop = snapshot.mainTop;
    main.scrollLeft = snapshot.mainLeft;
    const detail = document.getElementById("detailPanel");
    if (detail) {
      detail.scrollTop = snapshot.detailTop;
      detail.scrollLeft = snapshot.detailLeft;
    }
    for (const saved of snapshot.entityLists) {
      const list = main.querySelector(`.entity-list[data-key="${cssEscape(saved.key)}"]`);
      if (list) {
        list.scrollTop = saved.top;
        list.scrollLeft = saved.left;
      }
    }
    window.scrollTo(snapshot.windowX, snapshot.windowY);
    if (restoreFocus) {
      restoreFocusSnapshot(snapshot.focus);
    }
  };
  apply(true);
  requestAnimationFrame(() => apply(false));
  setTimeout(() => apply(false), 0);
}

function captureFocusSnapshot() {
  const active = document.activeElement;
  if (!active || !main.contains(active)) {
    return null;
  }
  const detail = document.getElementById("detailPanel");
  const container = detail?.contains(active)
    ? detail
    : active.closest(".list-tools") || active.closest(".entity-list") || main;
  const focusables = focusableElements(container);
  const index = focusables.indexOf(active);
  const pending = state.pendingFocusMove;
  const move = pending && Date.now() - pending.time < 500 ? pending.direction : 0;
  state.pendingFocusMove = null;
  return {
    container: focusContainerKey(container),
    controlId: active.dataset?.controlId || "",
    index,
    move,
    value: "value" in active ? active.value : null,
    checked: active.type === "checkbox" ? active.checked : null,
    selectionStart: typeof active.selectionStart === "number" ? active.selectionStart : null,
    selectionEnd: typeof active.selectionEnd === "number" ? active.selectionEnd : null,
  };
}

function restoreFocusSnapshot(snapshot) {
  if (!snapshot) {
    return;
  }
  const container = focusContainer(snapshot.container);
  if (!container) {
    return;
  }
  const focusables = focusableElements(container);
  if (!focusables.length) {
    return;
  }
  let target = null;
  if (snapshot.controlId && !snapshot.move) {
    target = container.querySelector(`[data-control-id="${cssEscape(snapshot.controlId)}"]`);
  }
  if (!target) {
    const nextIndex = Math.max(0, Math.min(focusables.length - 1, snapshot.index + snapshot.move));
    target = focusables[nextIndex] || null;
  }
  if (!target || typeof target.focus !== "function") {
    return;
  }
  if (!snapshot.move && snapshot.value != null && "value" in target && target.tagName !== "SELECT") {
    target.value = snapshot.value;
  }
  if (!snapshot.move && snapshot.checked != null && target.type === "checkbox") {
    target.checked = snapshot.checked;
  }
  target.focus({ preventScroll: true });
  if (
    !snapshot.move
    && snapshot.selectionStart != null
    && typeof target.setSelectionRange === "function"
    && target.type !== "number"
  ) {
    target.setSelectionRange(snapshot.selectionStart, snapshot.selectionEnd ?? snapshot.selectionStart);
  }
}

function focusableElements(container) {
  return Array.from(container.querySelectorAll("input, select, textarea, button, summary"))
    .filter((node) => !node.disabled && node.offsetParent !== null);
}

function focusContainerKey(container) {
  if (container.id === "detailPanel") {
    return "detail";
  }
  if (container.classList?.contains("list-tools")) {
    return "list-tools";
  }
  if (container.classList?.contains("entity-list")) {
    return `entity-list:${container.dataset.key || ""}`;
  }
  return "main";
}

function focusContainer(key) {
  if (key === "detail") {
    return document.getElementById("detailPanel");
  }
  if (key === "list-tools") {
    return main.querySelector(".list-tools");
  }
  if (key.startsWith("entity-list:")) {
    return main.querySelector(`.entity-list[data-key="${cssEscape(key.slice("entity-list:".length))}"]`);
  }
  return main;
}

function cssEscape(value) {
  if (window.CSS?.escape) {
    return CSS.escape(String(value ?? ""));
  }
  return String(value ?? "").replace(/["\\]/g, "\\$&");
}

function renderNav() {
  const buttons = TABS.map((tab) => {
    const count = tab.id === "advanced"
      ? ADVANCED_KEYS.length
      : tab.id === "gacha"
        ? (state.content?.gacha?.pools?.length ?? 0)
        : (state.content?.[tab.id]?.length ?? 0);
    return el("button", {
      className: state.tab === tab.id ? "active" : "",
      onclick: () => {
        if (state.tab !== tab.id) {
          sortActiveEditorStats();
        }
        state.queryByTab[state.tab] = state.query;
        state.tab = tab.id;
        state.query = state.queryByTab[tab.id] || "";
        render({ preserveScroll: false });
      },
    }, [
      el("span", {}, tab.label),
      el("span", { className: "count" }, String(count)),
    ]);
  });
  nav.replaceChildren(...buttons);
}

function renderItems() {
  renderEntityEditor({
    key: "items",
    title: "장비",
    makeNew: () => ({
      id: nextId("item", state.content.items),
      name: "New Item",
      rarity: firstRarity(),
      stats: {},
      stat_effects: [],
      base_price: 0,
      excluded_from_gacha: false,
    }),
    summary: (item) => `${rarityLabel(item.rarity)}${item.excluded_from_gacha ? " · 가챠 제외" : ""}`,
    listTools: () => [
      selectField("등급 필터", state, "itemRarityFilter", [["", "전체"], ...rarityOptions()], {
        rerender: true,
        controlId: "items:rarity-filter",
      }),
    ],
    detail: renderItemDetail,
  });
}

function renderItemDetail(item) {
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid" }, [
      idField("items", item),
      textField("이름", item, "name"),
      selectField("등급", item, "rarity", rarityOptions()),
      numberField("기본 판매가", item, "base_price", { step: 1 }),
      checkboxField("가챠 제외", item, "excluded_from_gacha"),
      textAreaField("설명", item, "description", { full: true }),
    ]),
    statsEditor(item, "stats", "스탯", { fixedStatsKey: "fixed_stats" }),
    statEffectsEditor(item, "stat_effects", "영속 스탯 효과", -1, item.undispellable ?? true),
    specialEffectsEditor(item, "effects", "영속 전투 효과", -1, item.undispellable ?? true),
  ]);
  mainDetail(`장비 편집`, item, body);
}

function renderMaterials() {
  renderEntityEditor({
    key: "materials",
    title: "재료",
    makeNew: () => ({
      id: nextId("material", state.content.materials),
      name: "New Material",
      rarity: firstRarity(),
      emoji: "",
      description: "",
    }),
    summary: (material) => `${material.rarity ?? ""}${material.emoji ? ` · ${material.emoji}` : ""}`,
    detail: renderMaterialDetail,
  });
}

function renderMaterialDetail(material) {
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid" }, [
      idField("materials", material),
      textField("이름", material, "name"),
      selectField("등급", material, "rarity", rarityOptions()),
      textField("보상 이모지", material, "emoji"),
      textAreaField("설명", material, "description", { full: true }),
    ]),
  ]);
  mainDetail("재료 편집", material, body);
}

function renderRecipes() {
  renderEntityEditor({
    key: "crafting_recipes",
    title: "제작식",
    makeNew: () => ({
      id: nextId("recipe", state.content.crafting_recipes),
      name: "New Recipe",
      result_item_id: state.content.items[0]?.id ?? "",
      level_req: 1,
      gold: 0,
      materials: {},
      description: "",
      sort_order: nextSort(state.content.crafting_recipes),
    }),
    summary: (recipe) => {
      const item = findById("items", recipe.result_item_id);
      return item?.name ?? recipe.result_item_id;
    },
    detail: renderRecipeDetail,
  });
}

function renderRecipeDetail(recipe) {
  const result = findById("items", recipe.result_item_id);
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid" }, [
      idField("crafting_recipes", recipe),
      textField("이름", recipe, "name"),
      selectField("결과 장비", recipe, "result_item_id", itemOptions(), { rerender: true }),
      numberField("골드 비용", recipe, "gold", { step: 1 }),
      numberField("정렬 순서", recipe, "sort_order", { step: 1 }),
      textAreaField("설명", recipe, "description", { full: true }),
    ]),
    result ? el("div", { className: "section" }, [
      el("div", { className: "section-head" }, [
        el("h3", {}, "결과 장비 성능"),
      ]),
      el("div", { className: "preview" }, [
        el("strong", {}, `${result.name} (${result.rarity})`),
        el("span", {}, formatStats(result.stats)),
      ]),
    ]) : el("div", { className: "empty" }, "결과 장비를 선택하세요."),
    materialCostEditor(recipe),
  ]);
  mainDetail("제작식 편집", recipe, body);
}

function renderEnhancement() {
  const enhancement = normalizeEnhancementConfig();
  const star = enhancement.star_multiplier;
  const odds = enhancement.odds;
  const sell = enhancement.sell_rates;
  const globalPanel = el("section", { className: "panel" }, [
    el("div", { className: "panel-header" }, [
      el("h2", {}, "강화 설정"),
      el("button", {
        type: "button",
        onclick: () => {
          enhancement.methods.push(blankEnhancementMethod(enhancement));
          markDirty();
          render();
        },
      }, "강화 방식 추가"),
    ]),
    el("div", { className: "panel-body" }, [
      el("section", { className: "section subtle" }, [
        el("div", { className: "section-head" }, [el("h3", {}, "성급 능력치 배율")]),
        el("div", { className: "form-grid four" }, [
          numberField("선형 증가", star, "linear", { step: 0.01 }),
          numberField("제곱 증가", star, "quadratic", { step: 0.01 }),
          numberField("초반 보너스", star, "early_bonus", { step: 0.01 }),
          numberField("초반 보너스 한계", star, "early_bonus_cap", { step: 1 }),
        ]),
      ]),
      el("section", { className: "section subtle" }, [
        el("div", { className: "section-head" }, [el("h3", {}, "기본 강화 확률")]),
        el("div", { className: "form-grid four" }, [
          numberField("성공 기본값", odds, "success_base", { step: 0.01 }),
          numberField("성급 성공 감소", odds, "success_star_penalty", { step: 0.001 }),
          numberField("등급 성공 감소", odds, "success_tier_penalty", { step: 0.001 }),
          numberField("성공 하한", odds, "success_floor", { step: 0.01 }),
          numberField("파괴 시작 성급", odds, "destroy_min_stars", { step: 1 }),
          numberField("파괴 증가량", odds, "destroy_scale", { step: 0.001 }),
          numberField("파괴 상한", odds, "destroy_cap", { step: 0.01 }),
        ]),
      ]),
      el("section", { className: "section subtle" }, [
        el("div", { className: "section-head" }, [el("h3", {}, "판매율")]),
        el("div", { className: "form-grid two" }, [
          numberField("일반 판매율", sell, "normal", { step: 0.01 }),
          numberField("흔적 판매율", sell, "destroyed", { step: 0.01 }),
        ]),
      ]),
    ]),
  ]);
  const methodPanels = enhancement.methods.map((method, index) => enhancementMethodEditor(enhancement, method, index));
  main.replaceChildren(el("div", { className: "rows" }, [globalPanel, ...methodPanels]));
}

function enhancementMethodEditor(enhancement, method, index) {
  normalizeEnhancementMethod(method, index + 1);
  return el("section", { className: "panel" }, [
    el("div", { className: "panel-header" }, [
      el("h2", {}, method.name || method.id),
      el("button", {
        type: "button",
        className: "danger",
        onclick: () => {
          if (!confirm(`${method.name || method.id} 삭제?`)) {
            return;
          }
          enhancement.methods.splice(index, 1);
          markDirty();
          render();
        },
      }, "삭제"),
    ]),
    el("div", { className: "panel-body" }, [
      el("div", { className: "form-grid three" }, [
        nestedIdField("방식 ID", method, enhancement.methods),
        textField("이름", method, "name"),
        textAreaField("설명", method, "description", { full: true }),
        numberField("사용 가능 최소 성급", method, "min_stars", { step: 1 }),
        numberField("도달 가능 최대 성급", method, "max_stars", { step: 1 }),
      ]),
      el("section", { className: "section subtle" }, [
        el("div", { className: "section-head" }, [el("h3", {}, "골드 비용")]),
        el("div", { className: "form-grid two" }, [
          selectField("방식", method.gold, "mode", GOLD_COST_MODES, { rerender: true }),
          ...(method.gold.mode === "fixed" ? [numberField("고정 골드", method.gold, "amount", { step: 1 })] : []),
        ]),
      ]),
      materialCostEditor(method, "강화 재료"),
      el("section", { className: "section subtle" }, [
        el("div", { className: "section-head" }, [el("h3", {}, "강화 확률")]),
        el("div", { className: "form-grid four" }, [
          selectField("방식", method.odds, "mode", ENHANCEMENT_ODDS_MODES, { rerender: true }),
          optionalNumberField("성공 확률", method.odds, "success", { step: 0.01 }),
          optionalNumberField("실패 확률", method.odds, "fail", { step: 0.01 }),
          optionalNumberField("파괴 확률", method.odds, "destroy", { step: 0.01 }),
        ]),
      ]),
    ]),
  ]);
}

function normalizeEnhancementConfig() {
  const enhancement = state.content.enhancement ||= {};
  enhancement.star_multiplier ||= {};
  enhancement.odds ||= {};
  enhancement.sell_rates ||= {};
  enhancement.star_multiplier.linear ??= 0.24;
  enhancement.star_multiplier.quadratic ??= 0.03;
  enhancement.star_multiplier.early_bonus ??= 0.03;
  enhancement.star_multiplier.early_bonus_cap ??= 3;
  enhancement.odds.success_base ??= 0.86;
  enhancement.odds.success_star_penalty ??= 0.055;
  enhancement.odds.success_tier_penalty ??= 0.045;
  enhancement.odds.success_floor ??= 0.15;
  enhancement.odds.destroy_min_stars ??= 2;
  enhancement.odds.destroy_scale ??= 0.008;
  enhancement.odds.destroy_cap ??= 0.38;
  enhancement.sell_rates.normal ??= 0.38;
  enhancement.sell_rates.destroyed ??= 0.16;
  enhancement.methods = Array.isArray(enhancement.methods) && enhancement.methods.length
    ? enhancement.methods
    : [blankEnhancementMethod(enhancement, "gold")];
  enhancement.methods.forEach((method, index) => normalizeEnhancementMethod(method, index + 1));
  return enhancement;
}

function normalizeEnhancementMethod(method, index = 1) {
  method.id ||= nextId(`method_${index}`, state.content.enhancement?.methods || []);
  method.name ||= method.id;
  method.description ||= "";
  method.gold = method.gold && typeof method.gold === "object"
    ? method.gold
    : { mode: "fixed", amount: Number(method.gold || method.gold_cost || 0) };
  method.gold.mode = GOLD_COST_MODES.some(([mode]) => mode === method.gold.mode) ? method.gold.mode : "formula";
  method.gold.amount = Number(method.gold.amount || 0);
  method.materials = method.materials && typeof method.materials === "object" ? method.materials : {};
  method.odds = method.odds && typeof method.odds === "object" ? method.odds : { mode: "formula" };
  method.odds.mode = ENHANCEMENT_ODDS_MODES.some(([mode]) => mode === method.odds.mode) ? method.odds.mode : "formula";
  method.min_stars = Number(method.min_stars || 0);
  method.max_stars = Math.max(method.min_stars + 1, Number(method.max_stars || state.content.settings?.max_enhancement_stars || 10));
  delete method.gold_cost;
  delete method.material_costs;
}

function blankEnhancementMethod(enhancement, preferredId = "") {
  const id = preferredId && !(enhancement.methods || []).some((method) => method.id === preferredId)
    ? preferredId
    : nextId("method", enhancement.methods || []);
  return {
    id,
    name: preferredId === "gold" ? "일반 강화" : "새 강화 방식",
    description: "",
    gold: { mode: preferredId === "gold" ? "formula" : "fixed", amount: 0 },
    materials: {},
    odds: { mode: preferredId === "gold" ? "formula" : "fixed", success: 1, fail: 0, destroy: 0 },
    min_stars: 0,
    max_stars: state.content.settings?.max_enhancement_stars || 10,
  };
}

function renderGacha() {
  const gacha = normalizeGachaConfig();
  const globalPanel = el("section", { className: "panel" }, [
    el("div", { className: "panel-header" }, [
      el("h2", {}, "가챠 설정"),
      el("button", {
        type: "button",
        onclick: () => {
          const pool = blankGachaPool(gacha);
          gacha.pools.push(pool);
          gacha.default_pool_id ||= pool.id;
          markDirty();
          render();
        },
      }, "풀 추가"),
      el("button", {
        type: "button",
        onclick: () => {
          const festival = blankGachaFestival(gacha);
          gacha.festivals.push(festival);
          gacha.active_festival_id ||= festival.id;
          markDirty();
          render();
        },
      }, "페스 추가"),
    ]),
    el("div", { className: "panel-body" }, [
      el("div", { className: "form-grid three" }, [
        textField("소모 재료 ID", gacha, "material_id"),
        numberField("소모 수량", gacha, "cost", { step: 1 }),
        numberField("뽑기 횟수", gacha, "draws", { step: 1 }),
        selectField("기본 풀", gacha, "default_pool_id", gachaPoolOptions(gacha), { rerender: true }),
        selectField("활성 페스", gacha, "active_festival_id", [["", "없음"], ...gachaFestivalOptions(gacha)], { rerender: true }),
      ]),
    ]),
  ]);
  const poolPanels = gacha.pools.map((pool, index) => gachaPoolEditor(gacha, pool, index));
  const festivalPanels = gacha.festivals.map((festival, index) => gachaFestivalEditor(gacha, festival, index));
  main.replaceChildren(el("div", { className: "rows" }, [globalPanel, ...festivalPanels, ...poolPanels]));
}

function gachaPoolEditor(gacha, pool, index) {
  return el("section", { className: "panel" }, [
    el("div", { className: "panel-header" }, [
      el("h2", {}, pool.name || pool.id),
      el("div", { className: "actions" }, [
        el("button", {
          type: "button",
          onclick: () => {
            pool.entries.push(blankGachaEntry());
            markDirty();
            render();
          },
        }, "보상 추가"),
        el("button", {
          type: "button",
          className: "danger",
          onclick: () => {
            if (!confirm(`${pool.name || pool.id} 삭제?`)) {
              return;
            }
            gacha.pools.splice(index, 1);
            if (gacha.default_pool_id === pool.id) {
              gacha.default_pool_id = gacha.pools[0]?.id || "";
            }
            markDirty();
            render();
          },
        }, "삭제"),
      ]),
    ]),
    el("div", { className: "panel-body" }, [
      el("div", { className: "form-grid three" }, [
        nestedIdField("풀 ID", pool, gacha.pools, (oldId, newId) => {
          if (gacha.default_pool_id === oldId) {
            gacha.default_pool_id = newId;
          }
        }),
        textField("이름", pool, "name"),
        textAreaField("설명", pool, "description", { full: true }),
      ]),
      gachaEntriesEditor(pool),
    ]),
  ]);
}

function gachaEntriesEditor(pool) {
  pool.entries ||= [];
  const rows = pool.entries.map((entry, index) => {
    normalizeGachaEntry(entry);
    const fields = [
      selectField("타입", entry, "type", GACHA_ENTRY_TYPES, { rerender: true }),
      numberField("확률/가중치", entry, "chance", { step: 0.01 }),
    ];
    if (entry.type === "item" || entry.type === "item_rarity") {
      fields.push(numberField("강화 수치", entry, "stars", { step: 1 }));
    }
    if (entry.type === "item_rarity" || entry.type === "material_rarity") {
      fields.push(selectField("등급", entry, "rarity", rarityOptions()));
    }
    if (entry.type === "material_rarity") {
      fields.push(numberField("최소 수량", entry, "min", { step: 1 }));
      fields.push(numberField("최대 수량", entry, "max", { step: 1 }));
    }
    fields.push(deleteButton(() => {
      pool.entries.splice(index, 1);
      markDirty();
      render();
    }));

    const targetEditor = entry.type === "item"
      ? gachaTargetListEditor(entry, "item_ids", gachaItemOptions, "장비")
      : entry.type === "material"
        ? gachaTargetListEditor(entry, "material_ids", materialOptions, "재료")
        : null;
    return el("div", { className: "rows" }, [
      el("div", { className: "row" }, fields),
      targetEditor,
    ]);
  });
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "보상 풀"),
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "보상 없음")]),
  ]);
}

function gachaTargetListEditor(entry, key, optionsFn, label) {
  entry[key] = Array.isArray(entry[key]) ? entry[key] : [];
  const options = optionsFn();
  entry[key] = entry[key]
    .map((target) => normalizeGachaTarget(target))
    .filter((target) => target.id);
  const rows = entry[key].map((target, index) => {
    const proxy = { target_id: target.id };
    return el("div", { className: "row three" }, [
      selectField(label, proxy, "target_id", options, {
        onChange: (newId) => {
          target.id = newId;
        },
      }),
      numberField("수량", target, "amount", { step: 1 }),
      deleteButton(() => {
        entry[key].splice(index, 1);
        markDirty();
        render();
      }),
    ]);
  });
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, `${label} 대상 리스트`),
      el("button", {
        type: "button",
        onclick: () => {
          const first = options[0]?.[0] || "";
          if (first) {
            entry[key].push({ id: first, amount: 1 });
            markDirty();
            render();
          }
        },
      }, `${label} 추가`),
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, `${label} 대상 없음`)]),
  ]);
}

function gachaFestivalEditor(gacha, festival, index) {
  festival.overrides ||= [];
  return el("section", { className: "panel subtle-panel" }, [
    el("div", { className: "panel-header" }, [
      el("h2", {}, `${festival.name || festival.id}${gacha.active_festival_id === festival.id ? " · 활성" : ""}`),
      el("div", { className: "actions" }, [
        el("button", {
          type: "button",
          onclick: () => {
            festival.overrides.push(blankGachaFestivalOverride());
            markDirty();
            render();
          },
        }, "확률 변경 추가"),
        el("button", {
          type: "button",
          onclick: () => {
            gacha.active_festival_id = gacha.active_festival_id === festival.id ? "" : festival.id;
            markDirty();
            render();
          },
        }, gacha.active_festival_id === festival.id ? "비활성화" : "활성화"),
        el("button", {
          type: "button",
          className: "danger",
          onclick: () => {
            if (!confirm(`${festival.name || festival.id} 삭제?`)) {
              return;
            }
            gacha.festivals.splice(index, 1);
            if (gacha.active_festival_id === festival.id) {
              gacha.active_festival_id = "";
            }
            markDirty();
            render();
          },
        }, "삭제"),
      ]),
    ]),
    el("div", { className: "panel-body" }, [
      el("div", { className: "form-grid three" }, [
        nestedIdField("페스 ID", festival, gacha.festivals, (oldId, newId) => {
          if (gacha.active_festival_id === oldId) {
            gacha.active_festival_id = newId;
          }
        }),
        textField("이름", festival, "name"),
        textAreaField("설명", festival, "description", { full: true }),
      ]),
      gachaFestivalOverridesEditor(festival),
    ]),
  ]);
}

function gachaFestivalOverridesEditor(festival) {
  festival.overrides ||= [];
  const rows = festival.overrides.map((override, index) => {
    normalizeGachaFestivalOverride(override);
    return el("div", { className: "row four" }, [
      selectField("타입", override, "type", GACHA_FESTIVAL_OVERRIDE_TYPES, {
        rerender: true,
        onChange: () => {
          override.target_id = defaultGachaFestivalTarget(override.type);
        },
      }),
      selectField("대상", override, "target_id", gachaFestivalTargetOptions(override.type)),
      numberField("목표 확률/가중치", override, "chance", { step: 0.01 }),
      deleteButton(() => {
        festival.overrides.splice(index, 1);
        markDirty();
        render();
      }),
    ]);
  });
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "페스 확률 변경"),
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "확률 변경 없음")]),
  ]);
}

function normalizeGachaConfig() {
  const gacha = state.content.gacha ||= blankGacha();
  gacha.material_id ||= "crystal";
  gacha.cost = Number(gacha.cost || 3000);
  gacha.draws = Number(gacha.draws || 10);
  gacha.pools = Array.isArray(gacha.pools) ? gacha.pools : [];
  gacha.festivals = Array.isArray(gacha.festivals) ? gacha.festivals : [];
  if (!gacha.pools.length) {
    gacha.pools.push(blankGachaPool(gacha, "default"));
  }
  if (!gacha.default_pool_id || !gacha.pools.some((pool) => pool.id === gacha.default_pool_id)) {
    gacha.default_pool_id = gacha.pools[0]?.id || "";
  }
  if (gacha.active_festival_id && !gacha.festivals.some((festival) => festival.id === gacha.active_festival_id)) {
    gacha.active_festival_id = "";
  }
  for (const pool of gacha.pools) {
    pool.id ||= nextId("pool", gacha.pools);
    pool.name ||= pool.id;
    pool.description ||= "";
    pool.entries = Array.isArray(pool.entries) ? pool.entries : [];
    for (const entry of pool.entries) {
      normalizeGachaEntry(entry);
    }
  }
  for (const festival of gacha.festivals) {
    festival.id ||= nextId("festival", gacha.festivals);
    festival.name ||= festival.id;
    festival.description ||= "";
    festival.overrides = Array.isArray(festival.overrides) ? festival.overrides : [];
    for (const override of festival.overrides) {
      normalizeGachaFestivalOverride(override);
    }
  }
  return gacha;
}

function normalizeGachaEntry(entry) {
  entry.type ||= "item_rarity";
  entry.chance = Number(entry.chance || 0);
  if (entry.type === "item") {
    entry.item_ids = Array.isArray(entry.item_ids) ? entry.item_ids : [];
    entry.item_ids = entry.item_ids.map((target) => normalizeGachaTarget(target)).filter((target) => target.id);
    entry.stars = Number(entry.stars || 0);
  } else {
    delete entry.item_ids;
  }
  if (entry.type === "material") {
    entry.material_ids = Array.isArray(entry.material_ids) ? entry.material_ids : [];
    entry.material_ids = entry.material_ids.map((target) => normalizeGachaTarget(target)).filter((target) => target.id);
  } else {
    delete entry.material_ids;
  }
  if (entry.type === "item_rarity" || entry.type === "material_rarity") {
    entry.rarity ||= firstRarity();
  } else {
    delete entry.rarity;
  }
  if (entry.type === "item_rarity") {
    entry.stars = Number(entry.stars || 0);
  }
  if (entry.type === "material_rarity") {
    entry.min = Math.max(1, Number(entry.min || entry.amount || 1));
    entry.max = Math.max(entry.min, Number(entry.max || entry.min));
  } else {
    delete entry.min;
    delete entry.max;
  }
}

function normalizeGachaTarget(target) {
  if (target && typeof target === "object") {
    const amount = Number(target.amount || 1);
    return {
      id: String(target.id || target.item_id || target.material_id || ""),
      amount: Math.max(1, Number.isFinite(amount) ? amount : 1),
    };
  }
  return {
    id: String(target || ""),
    amount: 1,
  };
}

function normalizeGachaFestivalOverride(override) {
  override.type ||= "item_rarity";
  override.target_id = String(override.target_id || override.id || override.rarity || override.item_id || override.material_id || "");
  if (!gachaFestivalTargetOptions(override.type).some(([id]) => id === override.target_id)) {
    override.target_id = defaultGachaFestivalTarget(override.type);
  }
  override.chance = Number(override.chance || 0);
}

function gachaFestivalTargetOptions(type) {
  if (type === "item") {
    return gachaItemOptions();
  }
  if (type === "material") {
    return materialOptions();
  }
  return rarityOptions();
}

function defaultGachaFestivalTarget(type) {
  return gachaFestivalTargetOptions(type)[0]?.[0] || "";
}

function blankGacha() {
  return {
    default_pool_id: "default",
    active_festival_id: "",
    material_id: "crystal",
    cost: 3000,
    draws: 10,
    pools: [],
    festivals: [],
  };
}

function blankGachaPool(gacha, preferredId = "") {
  return {
    id: preferredId && !(gacha.pools || []).some((pool) => pool.id === preferredId)
      ? preferredId
      : nextId("pool", gacha.pools || []),
    name: "새 가챠 풀",
    description: "",
    entries: [blankGachaEntry()],
  };
}

function blankGachaEntry() {
  return {
    type: "item_rarity",
    rarity: firstRarity(),
    chance: 1,
    stars: 0,
  };
}

function gachaPoolOptions(gacha) {
  return (gacha.pools || []).map((pool) => [pool.id, `${pool.name || pool.id} (${pool.id})`]);
}

function blankGachaFestival(gacha) {
  return {
    id: nextId("festival", gacha.festivals || []),
    name: "새 가챠 페스",
    description: "",
    overrides: [blankGachaFestivalOverride()],
  };
}

function blankGachaFestivalOverride() {
  return {
    type: "item_rarity",
    target_id: firstRarity(),
    chance: 1,
  };
}

function gachaFestivalOptions(gacha) {
  return (gacha.festivals || []).map((festival) => [festival.id, `${festival.name || festival.id} (${festival.id})`]);
}

function renderDungeons() {
  renderEntityEditor({
    key: "dungeons",
    title: "던전",
    makeNew: () => ({
      id: nextId("dungeon", state.content.dungeons),
      name: "New Dungeon",
      level_req: 1,
      enemies: [],
      description: "",
      sort_order: nextSort(state.content.dungeons),
    }),
    summary: (dungeon) => `전투 Lv.${dungeon.level_req ?? 1} · 몬스터 ${dungeon.enemies?.length ?? 0}`,
    detail: renderDungeonDetail,
  });
}

function renderDungeonDetail(dungeon) {
  delete dungeon.rank;
  dungeon.enemies ||= [];
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid three" }, [
      idField("dungeons", dungeon),
      textField("이름", dungeon, "name"),
      numberField("전투 레벨", dungeon, "level_req", { step: 1 }),
      numberField("정렬 순서", dungeon, "sort_order", { step: 1 }),
      textAreaField("설명", dungeon, "description", { full: true }),
    ]),
    statsEditor(dungeon, "stats", "던전 보정 스탯"),
    enemyEditor(dungeon),
  ]);
  mainDetail("던전 편집", dungeon, body);
}

function renderBosses() {
  renderEntityEditor({
    key: "bosses",
    title: "보스",
    makeNew: () => ({
      id: nextId("boss", state.content.bosses),
      name: "New Boss",
      level_req: 1,
      stats: { base_atk: 10, max_hp: 100 },
      gold: 0,
      exp: 0,
      patterns: [],
      warnings: [],
      hp_warnings: [],
      hp_effects: [],
      hp_locks: [],
      ct: { gauge_by_hp: [{ above: 0, max: 5 }], warnings_by_hp: [] },
      rewards: blankReward(),
      description: "",
      sort_order: nextSort(state.content.bosses),
    }),
    summary: (boss) => `전투 Lv.${boss.level_req ?? 1} · HP ${boss.stats?.max_hp ?? 0}`,
    detail: renderBossDetail,
  });
}

function renderBossDetail(boss) {
  normalizeBossWarnings(boss);
  delete boss.drop_chance;
  delete boss.rank;
  delete boss.stat_points;
  boss.hp_warnings ||= [];
  normalizeBossHpLocks(boss);
  normalizeBossHpEffects(boss);
  boss.ct ||= { gauge_by_hp: [], warnings_by_hp: [] };
  boss.ct.gauge_by_hp ||= [];
  boss.ct.warnings_by_hp ||= [];
  delete boss.skull_system;
  normalizeBossStackEffects(boss);
  boss.rewards ||= blankReward();
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid three" }, [
      idField("bosses", boss),
      textField("이름", boss, "name"),
      numberField("전투 레벨", boss, "level_req", { step: 1 }),
      numberField("정렬 순서", boss, "sort_order", { step: 1 }),
      numberField("기본 골드", boss, "gold", { step: 1 }),
      numberField("기본 경험치", boss, "exp", { step: 1 }),
      textAreaField("설명", boss, "description", { full: true }),
    ]),
    statsEditor(boss, "stats", "보스 스탯"),
    bossStackEffectEditor(boss),
    bossHpLockEditor(boss),
    bossHpEffectEditor(boss),
    bossWarningTemplateEditor(boss),
    bossHpWarningEditor(boss),
    bossCtEditor(boss),
    rewardEditor(boss, "rewards", "드랍 보상"),
  ]);
  mainDetail("보스 편집", boss, body);
}

function normalizeBossStackEffects(boss) {
  boss.stack_effects = Array.isArray(boss.stack_effects) ? boss.stack_effects : [];
  const seen = new Set();
  boss.stack_effects = boss.stack_effects
    .filter((row) => row && typeof row === "object")
    .map((row) => ({
      stack_effect_id: row.stack_effect_id || row.id || row.effect_id || "",
      initial_stacks: Math.max(0, Number(row.initial_stacks ?? row.stacks ?? 0)),
    }))
    .filter((row) => {
      if (!row.stack_effect_id || seen.has(row.stack_effect_id)) {
        return false;
      }
      seen.add(row.stack_effect_id);
      return true;
    });
}

function bossStackEffectEditor(boss) {
  normalizeBossStackEffects(boss);
  const rows = boss.stack_effects.map((row, index) => {
    const template = findById("stack_effects", row.stack_effect_id);
    const maxStacks = Math.max(1, Number(template?.max_stacks || 1));
    row.initial_stacks = Math.max(0, Math.min(maxStacks, Number(row.initial_stacks || 0)));
    return el("div", { className: "row two" }, [
      selectField("스택 효과", row, "stack_effect_id", stackEffectOptions(), {
        rerender: true,
        onChange: () => {
          row.initial_stacks = 0;
        },
      }),
      numberField("시작 스택", row, "initial_stacks", { step: 1 }),
      deleteButton(() => {
        boss.stack_effects.splice(index, 1);
        markDirty();
        render();
      }),
    ]);
  });
  return el("section", { className: "section themed stack-section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "보스전 스택"),
      el("button", {
        type: "button",
        onclick: () => {
          const nextId = (state.content.stack_effects || [])
            .find((effect) => !boss.stack_effects.some((row) => row.stack_effect_id === effect.id))
            ?.id;
          if (!nextId) {
            showToast("추가할 스택 효과가 없습니다.", true);
            return;
          }
          boss.stack_effects.push({ stack_effect_id: nextId, initial_stacks: 0 });
          markDirty();
          render();
        },
      }, "스택 추가"),
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "보스전에 등록된 스택 없음")]),
  ]);
}

function renderStackEffects() {
  renderEntityEditor({
    key: "stack_effects",
    title: "스택 효과",
    makeNew: () => ({
      id: nextId("stack_effect", state.content.stack_effects),
      name: "New Stack Effect",
      max_stacks: 5,
      description: "",
      tiers: [],
      conditions: [],
    }),
    summary: (effect) => `최대 ${effect.max_stacks || 1}스택 · ${(effect.tiers || []).length}단계`,
    detail: renderStackEffectDetail,
  });
}

function renderStackEffectDetail(effect) {
  normalizeStackEffect(effect);
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid" }, [
      idField("stack_effects", effect),
      textField("이름", effect, "name"),
      numberField("최대 스택", effect, "max_stacks", { step: 1, rerender: true }),
      textAreaField("설명", effect, "description", { full: true }),
    ]),
    stackTierEditor(effect),
    stackConditionEditor(effect),
  ]);
  mainDetail("스택 효과 편집", effect, body);
}

function normalizeStackEffect(effect) {
  effect.max_stacks = Math.max(1, Number(effect.max_stacks || effect.max || 1));
  effect.tiers = Array.isArray(effect.tiers) ? effect.tiers : Array.isArray(effect.stacks) ? effect.stacks : [];
  delete effect.stacks;
  effect.tiers = effect.tiers.filter((tier) => tier && typeof tier === "object");
  for (const tier of effect.tiers) {
    tier.stack = Math.max(1, Math.min(effect.max_stacks, Number(tier.stack || tier.stacks || 1)));
    migrateStatEffects(tier, "mods", "stat_effects", -1, true);
    for (const statEffect of tier.stat_effects) {
      statEffect.target = "self";
      statEffect.duration = -1;
      statEffect.undispellable = true;
    }
    if (tier.effects && typeof tier.effects === "object") {
      normalizeSpecialEffects(tier.effects, -1, true);
      forceSelfSpecialEffectTargets(tier.effects);
      forceSpecialEffectMeta(tier.effects, -1, true);
    }
  }
  effect.conditions = Array.isArray(effect.conditions) ? effect.conditions : [];
  effect.conditions = effect.conditions
    .filter((condition) => condition && typeof condition === "object")
    .map((condition) => normalizeStackCondition(condition));
}

function forceSelfSpecialEffectTargets(effects) {
  if (!effects || typeof effects !== "object") {
    return;
  }
  for (const key of ["flurry", "double_strike"]) {
    if (effects[key]) {
      effects[key].target = "self";
    }
  }
  for (const key of ["bonus_damage", "critical_reinforce", "final_damage", "post_attack_ability_damage", "ability_recast", "dispel_guard", "veil"]) {
    for (const effect of effects[key] || []) {
      effect.target = "self";
    }
  }
}

function forceSpecialEffectMeta(effects, duration, undispellable) {
  if (!effects || typeof effects !== "object") {
    return;
  }
  for (const key of ["flurry", "double_strike"]) {
    if (effects[key]) {
      effects[key].duration = duration;
      effects[key].undispellable = undispellable;
    }
  }
  for (const key of ["bonus_damage", "critical_reinforce", "final_damage", "post_attack_ability_damage", "ability_recast", "dispel_guard", "veil"]) {
    for (const effect of effects[key] || []) {
      effect.duration = duration;
      effect.undispellable = undispellable;
      if (key === "dispel_guard" || key === "veil") {
        effect.mode = "duration";
        effect.count = 0;
      }
    }
  }
}

function normalizeStackCondition(condition) {
  let operation = condition.operation || condition.op || "increase";
  if (String(operation).startsWith("stack_")) {
    operation = String(operation).replace(/^stack_/, "");
  }
  if (!STACK_OPERATIONS.some(([id]) => id === operation)) {
    operation = "increase";
  }
  const objective = condition.objective || condition.kind || "damage";
  const isWarningEvent = stackConditionIsWarningEvent(objective);
  const target = isWarningEvent ? "none" : ["enemy", "opponent"].includes(condition.target) ? "opponent" : "self";
  return {
    objective,
    target,
    operation,
    value: Math.max(1, Number(condition.value || condition.stacks || 1)),
    required: isWarningEvent ? 1 : Math.max(1, Number(condition.required || 1)),
    min_damage: Math.max(0, Number(condition.min_damage || 0)),
  };
}

function stackConditionIsWarningEvent(objective) {
  return objective === "warning_success" || objective === "warning_failure";
}

function stackTierEditor(effect) {
  effect.tiers ||= [];
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      const used = new Set(effect.tiers.map((tier) => Number(tier.stack || 0)));
      let stack = 1;
      while (used.has(stack) && stack < effect.max_stacks) {
        stack += 1;
      }
      effect.tiers.push({ stack, stat_effects: [], effects: {} });
      markDirty();
      render();
    },
  }, "단계 추가");
  const rows = effect.tiers.map((tier, index) => el("div", { className: "subpanel" }, [
    el("div", { className: "subpanel-head" }, [
      el("div", { className: "subpanel-title" }, [
        el("strong", {}, `${tier.stack}스택`),
      ]),
      deleteButton(() => {
        effect.tiers.splice(index, 1);
        markDirty();
        render();
      }),
    ]),
    el("div", { className: "form-grid three" }, [
      numberField("적용 스택", tier, "stack", { step: 1 }),
    ]),
    statEffectsEditor(tier, "stat_effects", "스택 스탯 효과", -1, true, { hideTarget: true, forceDuration: -1, forceUndispellable: true }),
    specialEffectsEditor(tier, "effects", "스택 특수 효과", -1, true, { hideTarget: true, forceDuration: -1, forceUndispellable: true }),
  ]));
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "스택 단계"),
      addButton,
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "스택 단계 없음")]),
  ]);
}

function stackConditionEditor(effect) {
  effect.conditions ||= [];
  const rows = effect.conditions.map((condition, index) => {
    const isWarningEvent = stackConditionIsWarningEvent(condition.objective);
    const targetOptions = condition.objective === "received_damage" ? STACK_RECEIVED_DAMAGE_TARGETS : STACK_CONDITION_TARGETS;
    const fields = [
      selectField("조건", condition, "objective", STACK_OBJECTIVES, { rerender: true }),
      selectField("동작", condition, "operation", STACK_OPERATIONS, { rerender: true }),
    ];
    if (!isWarningEvent) {
      fields.splice(1, 0, selectField("대상", condition, "target", targetOptions));
      fields.push(numberField("요구량", condition, "required", { step: 1 }));
    }
    if (!isWarningEvent && condition.objective === "hits") {
      fields.push(numberField("타수 최소 피해", condition, "min_damage", { step: 1 }));
    }
    if (!["remove", "max"].includes(condition.operation)) {
      fields.push(numberField("스택 수", condition, "value", { step: 1 }));
    }
    fields.push(deleteButton(() => {
      effect.conditions.splice(index, 1);
      markDirty();
      render();
    }));
    return el("div", { className: "row" }, fields);
  });
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "자동 증가/감소 조건"),
      el("button", {
        type: "button",
        onclick: () => {
          effect.conditions.push({
            objective: "damage",
            target: "self",
            operation: "increase",
            value: 1,
            required: 1,
            min_damage: 0,
          });
          markDirty();
          render();
        },
      }, "조건 추가"),
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "조건 없음")]),
  ]);
}

function renderJobs() {
  renderEntityEditor({
    key: "jobs",
    title: "직업",
    makeNew: (context = {}) => {
      const tier = context.parent_id ? Number(context.tier || 1) : 1;
      const parent = context.parent_id
        ? state.content.jobs.find((job) => job.id === context.parent_id)
        : null;
      return {
        id: nextId("job", state.content.jobs),
        name: "New Job",
        tier,
        level_req: context.level_req ?? defaultJobLevelForTier(tier),
        parent_id: context.parent_id || "",
        stats: parent?.stats && typeof parent.stats === "object" && !Array.isArray(parent.stats)
          ? { ...parent.stats }
          : {},
        stat_effects: [],
        effects: {},
        undispellable: true,
        description: "",
      };
    },
    summary: (job) => `Tier ${job.tier ?? 0} · Lv.${job.level_req ?? 1}`,
    listContent: renderJobTreeList,
    detail: renderJobDetail,
  });
}

function renderJobDetail(job) {
  const parentOptions = [["", "없음"], ...jobOptions().filter(([id]) => id !== job.id)];
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid" }, [
      idField("jobs", job),
      textField("이름", job, "name"),
      numberField("전직 단계", job, "tier", { step: 1 }),
      numberField("필요 레벨", job, "level_req", { step: 1 }),
      selectField("상위 직업", job, "parent_id", parentOptions),
      checkboxField("영속 효과 소거불가", job, "undispellable"),
      textAreaField("설명", job, "description", { full: true }),
    ]),
    statsEditor(job, "stats", "직업 스탯"),
    statEffectsEditor(job, "stat_effects", "직업 영속 스탯 효과", -1, job.undispellable ?? true),
    specialEffectsEditor(job, "effects", "직업 영속 전투 효과", -1, job.undispellable ?? true),
  ]);
  mainDetail("직업 편집", job, body);
}

function renderSkills() {
  renderEntityEditor({
    key: "skills",
    title: "스킬",
    makeNew: (context = {}) => {
      const job = context.job_id
        ? state.content.jobs.find((candidate) => candidate.id === context.job_id)
        : null;
      return {
        id: nextId("skill", state.content.skills),
        name: "New Skill",
        unlock_level: job ? defaultJobLevelForTier(job.tier) : 1,
        uses: 0,
        cooldown: 3,
        role: "attack",
        damage_multiplier: 0,
        hits: 0,
        player_mods: {},
        enemy_mods: {},
        player_stat_effects: [],
        enemy_stat_effects: [],
        heal_power: 0,
        heal_target: "self",
        damage_cut: 0,
        effect_actions: [],
        job_ids: context.job_id ? [context.job_id] : [],
        note: "",
      };
    },
    summary: (skill) => `${skill.role ?? ""} · Lv.${skill.unlock_level ?? 1}`,
    listContent: renderSkillTreeList,
    detail: renderSkillDetail,
  });
}

function renderSkillDetail(skill) {
  const beforeJobIds = JSON.stringify(skill.job_ids || []);
  skill.job_ids = normalizedSkillJobIds(skill.job_ids || []);
  if (JSON.stringify(skill.job_ids) !== beforeJobIds) {
    markDirty();
  }
  const playerEffectFallback = Boolean(skill.player_undispellable || skill.undispellable);
  const enemyEffectFallback = Boolean(skill.enemy_undispellable);
  const legacyDuration = skill.duration || 1;
  migrateSkillStatEffects(skill, legacyDuration);
  migrateSkillSpecialEffects(skill, legacyDuration, playerEffectFallback, enemyEffectFallback);
  normalizeHealCap(skill);
  skill.heal_target = normalizeStatEffectTarget(skill.heal_target);
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid three" }, [
      idField("skills", skill),
      textField("이름", skill, "name"),
      selectField("역할", skill, "role", SKILL_ROLES.map((role) => [role, role])),
      numberField("해금 레벨", skill, "unlock_level", { step: 1 }),
      numberField("사용 횟수 제한", skill, "uses", { step: 1 }),
      numberField("쿨다운", skill, "cooldown", { step: 1 }),
      numberField("피해 배율", skill, "damage_multiplier", { step: 0.01 }),
      numberField("타수", skill, "hits", { step: 1 }),
      numberField("회복 계수", skill, "heal_power", { step: 0.01 }),
      selectField("회복 대상", skill, "heal_target", STAT_EFFECT_TARGETS),
      ...healCapFields(skill, "회복 상한"),
      textAreaField("메모", skill, "note", { full: true }),
    ]),
    skillJobOwnerPicker(skill),
    statEffectsEditor(skill, "player_stat_effects", "자신 스탯 효과", 1),
    statEffectsEditor(skill, "enemy_stat_effects", "적 스탯 효과", 1),
    specialEffectsEditor(skill, "player_effects", "자신 특수 효과", 1, playerEffectFallback),
    specialEffectsEditor(skill, "enemy_effects", "적 특수 효과", 1, enemyEffectFallback),
    effectActionEditor(skill, "effect_actions", "즉시 효과"),
  ]);
  mainDetail("스킬 편집", skill, body);
}

function renderAdvanced() {
  const settingsPanel = settingsControls();
  const sections = ADVANCED_KEYS.map((key) => {
    const textarea = el("textarea", { className: "json-editor" }, JSON.stringify(state.content[key], null, 2));
    const apply = el("button", {
      type: "button",
      onclick: () => {
        try {
          state.content[key] = JSON.parse(textarea.value);
          markDirty();
          showToast(`${key} 적용 완료`, false);
          render();
        } catch (error) {
          showToast(`${key} JSON 파싱 실패\n${error.message}`, true);
        }
      },
    }, "적용");
    return el("section", { className: "panel" }, [
      el("div", { className: "panel-header" }, [
        el("h2", {}, key),
        apply,
      ]),
      el("div", { className: "panel-body" }, [
        textarea,
      ]),
    ]);
  });
  main.replaceChildren(el("div", { className: "rows" }, [settingsPanel, ...sections]));
}

function settingsControls() {
  const settings = state.content.settings ||= {};
  settings.reward_multipliers ||= {};
  settings.level_up_growth ||= {};
  settings.explore_combat ||= {};
  settings.explore_combat.basic_attack_multiplier ??= 1.0;
  settings.explore_combat.skill_damage_multiplier ??= 1.0;
  settings.explore_combat.player_defense_bonus ??= 0;
  settings.level_damage_multipliers = normalizeLevelDamageMultipliers(settings.level_damage_multipliers);
  settings.max_equipped_skills ??= 4;
  return el("section", { className: "panel" }, [
    el("div", { className: "panel-header" }, [
      el("h2", {}, "설정"),
    ]),
    el("div", { className: "panel-body" }, [
      el("div", { className: "form-grid three" }, [
        numberField("일일 탐색 수", settings, "daily_explores", { step: 1 }),
        checkboxField("탐색 제한", settings, "explore_limit_enabled"),
        checkboxField("보스 주간 보상 제한", settings, "boss_weekly_reward_limit_enabled"),
        numberField("장비 장착 수", settings, "max_equipped_items", { step: 1 }),
        numberField("어빌리티 장착 수", settings, "max_equipped_skills", { step: 1 }),
        numberField("최대 강화 단계", settings, "max_enhancement_stars", { step: 1 }),
        numberField("레벨업 공격력", settings.level_up_growth, "base_atk", { step: 0.1 }),
        numberField("레벨업 체력", settings.level_up_growth, "max_hp", { step: 1 }),
        numberField("레벨업 방어", settings.level_up_growth, "defense", { step: 0.001 }),
        numberField("탐색 평타 배율", settings.explore_combat, "basic_attack_multiplier", { step: 0.01 }),
        numberField("탐색 어빌 피해 배율", settings.explore_combat, "skill_damage_multiplier", { step: 0.01 }),
        numberField("탐색 방어 보너스", settings.explore_combat, "player_defense_bonus", { step: 0.01 }),
        ...settings.level_damage_multipliers.map((_, index) => (
          numberField(
            index >= DEFAULT_LEVEL_DAMAGE_MULTIPLIERS.length - 1 ? "레벨 차 5+ 배율" : `레벨 차 ${index} 배율`,
            settings.level_damage_multipliers,
            index,
            { step: 0.01 },
          )
        )),
        numberField("승리 보상 최소", settings.reward_multipliers, "win_min", { step: 0.01 }),
        numberField("승리 보상 최대", settings.reward_multipliers, "win_max", { step: 0.01 }),
        numberField("패배 보상 배율", settings.reward_multipliers, "loss", { step: 0.01 }),
      ]),
    ]),
  ]);
}

function normalizeLevelDamageMultipliers(raw) {
  const source = Array.isArray(raw) ? raw : [];
  return DEFAULT_LEVEL_DAMAGE_MULTIPLIERS.map((fallback, index) => {
    const value = Number(source[index]);
    return Number.isFinite(value) && value >= 0 ? value : fallback;
  });
}

function renderEntityEditor(config) {
  const currentList = main.querySelector(".entity-list");
  if (currentList?.dataset.key === config.key) {
    state.listScroll[config.key] = currentList.scrollTop;
  }
  const rows = state.content[config.key] || [];
  if (!rows.length) {
    const created = config.makeNew();
    rows.push(created);
    state.selected[config.key] = created.id;
  }
  const addRow = (context = {}) => {
    sortActiveEditorStats(config.key);
    const row = config.makeNew(context);
    rows.push(row);
    state.selected[config.key] = row.id;
    markDirty();
    render();
  };
  const selectedId = state.selected[config.key] || rows[0]?.id;
  const selected = rows.find((row) => row.id === selectedId) || rows[0];
  state.selected[config.key] = selected?.id;

  const listPanel = el("section", { className: "panel" }, [
    el("div", { className: "panel-header" }, [
      el("h2", {}, config.title),
      el("button", {
        type: "button",
        onclick: () => addRow(),
      }, "추가"),
    ]),
    el("div", { className: "list-tools" }, [
      el("input", {
        type: "search",
        placeholder: "검색",
        "data-control-id": `${config.key}:search`,
        value: state.query,
        oninput: (event) => {
          state.query = event.target.value;
          state.queryByTab[config.key] = state.query;
          if (!event.isComposing) {
            render();
          }
        },
        oncompositionend: (event) => {
          state.query = event.target.value;
          state.queryByTab[config.key] = state.query;
          render();
        },
      }),
      ...(config.listTools?.() || []),
    ]),
    el("div", {
      className: "entity-list",
      "data-key": config.key,
      onscroll: (event) => {
        state.listScroll[config.key] = event.currentTarget.scrollTop;
      },
    }, config.listContent
      ? config.listContent(rows, config, addRow)
      : filteredRows(rows, config).map((row) => entityButton(config, row))),
  ]);

  const detailShell = el("section", { className: "panel", id: "detailPanel" }, [
    el("div", { className: "empty" }, "왼쪽에서 항목을 선택하세요."),
  ]);

  main.replaceChildren(el("div", { className: "layout" }, [listPanel, detailShell]));
  const nextList = main.querySelector(`.entity-list[data-key="${config.key}"]`);
  if (nextList) {
    nextList.scrollTop = state.listScroll[config.key] || 0;
  }
  if (selected) {
    config.detail(selected);
  }
}

function entityButton(config, row) {
  return el("button", {
    type: "button",
    className: `entity-row ${state.selected[config.key] === row.id ? "active" : ""}`,
    onclick: () => {
      if (state.selected[config.key] !== row.id) {
        sortActiveEditorStats(config.key);
      }
      state.selected[config.key] = row.id;
      render();
    },
  }, [
    el("span", {}, [
      el("strong", {}, row.name || row.id),
      el("span", {}, row.id),
    ]),
    el("span", { className: "badge" }, config.summary(row)),
  ]);
}

function renderJobTreeList(rows, config, addRow) {
  const jobs = jobTreeRows();
  const query = state.query.trim().toLowerCase();
  const nodes = jobTreeRoots(jobs)
    .map((job) => jobTreeNode(job, jobs, config, addRow, query, 0))
    .filter(Boolean);
  return nodes.length ? nodes : [el("div", { className: "empty" }, "직업 없음")];
}

function renderSkillTreeList(rows, config, addRow) {
  const query = state.query.trim().toLowerCase();
  const publicSkills = rows
    .filter((skill) => skillDisplayJobIds(skill).length === 0)
    .filter((skill) => entityMatchesQuery(skill, query));
  const nodes = [];
  const publicChildren = [
    treeAddButton("공용 스킬 추가", () => addRow()),
    ...publicSkills.map((skill) => entityButton(config, skill)),
  ];
  if (!query || publicSkills.length) {
    nodes.push(treeGroup("skills:public", "공용 스킬", `${publicSkills.length}개`, publicChildren));
  }
  const jobs = jobTreeRows();
  for (const job of jobTreeRoots(jobs)) {
    const node = skillJobTreeNode(job, jobs, rows, config, addRow, query, 0);
    if (node) {
      nodes.push(node);
    }
  }
  return nodes.length ? nodes : [el("div", { className: "empty" }, "스킬 없음")];
}

function jobTreeRows() {
  return [...(state.content.jobs || [])].sort((a, b) => (
    Number(a.tier || 0) - Number(b.tier || 0)
    || Number(a.level_req || 0) - Number(b.level_req || 0)
    || String(a.name || a.id).localeCompare(String(b.name || b.id))
  ));
}

function jobTreeRoots(jobs) {
  const ids = new Set(jobs.map((job) => job.id));
  const roots = jobs.filter((job) => !job.parent_id || !ids.has(job.parent_id));
  return roots.length ? roots : jobs.filter((job) => job.parent_id === "");
}

function jobTreeChildren(job, jobs) {
  return jobs.filter((candidate) => candidate.parent_id === job.id);
}

function jobTreeOptions() {
  const jobs = jobTreeRows();
  const options = [];
  const visit = (job, depth) => {
    options.push([job.id, `${"  ".repeat(depth)}${job.name || job.id} (${job.id})`]);
    for (const child of jobTreeChildren(job, jobs)) {
      visit(child, depth + 1);
    }
  };
  for (const root of jobTreeRoots(jobs)) {
    visit(root, 0);
  }
  return options;
}

function defaultJobLevelForTier(tier) {
  const normalizedTier = Math.max(1, Math.floor(Number(tier || 1)));
  return JOB_LEVEL_BY_TIER[normalizedTier] ?? JOB_LEVEL_BY_TIER[5];
}

function skillDisplayJobIds(skill) {
  return normalizedSkillJobIds(skill.job_ids || []);
}

function normalizedSkillJobIds(jobIds) {
  if (!Array.isArray(jobIds)) {
    return [];
  }
  const jobById = new Map((state.content.jobs || []).map((job) => [job.id, job]));
  const orderById = new Map(jobTreeRows().map((job, index) => [job.id, index]));
  const unique = [...new Set(jobIds.map((jobId) => String(jobId)).filter((jobId) => jobById.has(jobId)))];
  return unique
    .sort((a, b) => (orderById.get(a) ?? 0) - (orderById.get(b) ?? 0));
}

function jobTreeNode(job, jobs, config, addRow, query, depth) {
  const children = jobTreeChildren(job, jobs)
    .map((child) => jobTreeNode(child, jobs, config, addRow, query, depth + 1))
    .filter(Boolean);
  const selfMatches = entityMatchesQuery(job, query);
  if (query && !selfMatches && !children.length) {
    return null;
  }
  const body = [
    treeEntitySummary(config, job, depth),
    treeAddButton("하위 직업 추가", () => {
      const tier = Number(job.tier || 1) + 1;
      addRow({
        parent_id: job.id,
        tier,
        level_req: defaultJobLevelForTier(tier),
      });
    }),
    ...children,
  ];
  return treeGroup(`jobs:${job.id}`, job.name || job.id, `Tier ${job.tier ?? 0}`, body, state.selected.jobs === job.id);
}

function skillJobTreeNode(job, jobs, skills, config, addRow, query, depth) {
  const directSkills = skills
    .filter((skill) => skillDisplayJobIds(skill).includes(job.id))
    .filter((skill) => entityMatchesQuery(skill, query));
  const childNodes = jobTreeChildren(job, jobs)
    .map((child) => skillJobTreeNode(child, jobs, skills, config, addRow, query, depth + 1))
    .filter(Boolean);
  const selfMatches = entityMatchesQuery(job, query);
  if (query && !selfMatches && !directSkills.length && !childNodes.length) {
    return null;
  }
  const body = [
    treeAddButton("스킬 추가", () => addRow({ job_id: job.id })),
    ...directSkills.map((skill) => entityButton(config, skill)),
    ...childNodes,
  ];
  return treeGroup(`skills:${job.id}`, job.name || job.id, `${directSkills.length}개`, body, false, depth);
}

function treeGroup(key, title, badge, children, active = false, depth = 0) {
  const isOpen = state.openDetails[key] ?? true;
  return el("details", {
    className: `tree-group ${active ? "active" : ""}`,
    open: isOpen,
    "data-detail-key": key,
    ontoggle: (event) => {
      state.openDetails[key] = event.currentTarget.open;
    },
  }, [
    el("summary", { className: "tree-summary", style: `--depth:${depth}` }, [
      el("span", {}, title),
      el("span", { className: "badge" }, badge),
    ]),
    el("div", { className: "tree-children" }, children),
  ]);
}

function treeEntitySummary(config, row, depth) {
  return el("button", {
    type: "button",
    className: `entity-row tree-entity ${state.selected[config.key] === row.id ? "active" : ""}`,
    style: `--depth:${depth}`,
    onclick: () => {
      state.selected[config.key] = row.id;
      render();
    },
  }, [
    el("span", {}, [
      el("strong", {}, row.name || row.id),
      el("span", {}, row.id),
    ]),
    el("span", { className: "badge" }, config.summary(row)),
  ]);
}

function treeAddButton(label, onclick) {
  return el("button", {
    type: "button",
    className: "tree-add",
    onclick,
  }, label);
}

function entityMatchesQuery(row, query) {
  if (!query) {
    return true;
  }
  return `${row.id} ${row.name} ${row.description ?? ""} ${row.note ?? ""}`.toLowerCase().includes(query);
}

function normalizeBossWarnings(boss) {
  boss.patterns ||= [];
  boss.warnings ||= [];
  boss.hp_warnings ||= [];
  boss.ct ||= { gauge_by_hp: [], warnings_by_hp: [] };
  boss.ct.gauge_by_hp ||= [];
  boss.ct.warnings_by_hp ||= [];
  for (const warning of boss.warnings) {
    normalizeWarningTemplate(boss, warning);
  }
  boss.hp_warnings.forEach((warning, index) => {
    normalizeWarningTrigger(boss, warning, index, "hp_warning", "damage");
  });
  boss.ct.warnings_by_hp.forEach((warning, index) => {
    normalizeCtWarningIds(boss, warning);
    normalizeWarningTrigger(boss, warning, index, "ct_warning", "hits");
    normalizeCtWarningIds(boss, warning);
  });
}

function normalizeCtWarningIds(boss, warning) {
  const source = Array.isArray(warning.warning_ids)
    ? warning.warning_ids
    : warning.warning_id
      ? [warning.warning_id]
      : [];
  let ids = Array.from(new Set(source.map((id) => String(id || "")).filter(Boolean)));
  if (!ids.length) {
    ids = [ensureFirstBossWarning(boss, "ct_warning")];
  }
  warning.warning_ids = ids;
  warning.warning_id = ids[0];
}

function nextCtWarningCandidateId(boss, selectedIds) {
  const selected = new Set((selectedIds || []).map((id) => String(id || "")));
  const option = bossWarningOptions(boss).find(([id]) => !selected.has(String(id)));
  return option?.[0] || ensureFirstBossWarning(boss, "ct_warning");
}

function normalizeWarningTrigger(boss, warning, index, prefix, defaultObjective) {
  const existing = warning.warning_id ? findBossWarning(boss, warning.warning_id) : null;
  if (existing) {
    delete warning.pattern;
    delete warning.pattern_id;
    delete warning.objective;
    delete warning.required;
    delete warning.objectives;
    return;
  }

  let pattern = null;
  if (warning.pattern && typeof warning.pattern === "object") {
    pattern = structuredClone(warning.pattern);
  } else if (warning.pattern_id) {
    pattern = structuredClone(findBossPattern(boss, warning.pattern_id) || blankBossPattern(boss, `${prefix}_failure`, "전조 실패 효과"));
    pattern.id = String(warning.pattern_id);
  } else {
    pattern = blankBossPattern(boss, `${prefix}_failure`, "전조 실패 효과");
  }
  normalizeBossPattern(boss, pattern, `${prefix}_failure`, "전조 실패 효과");

  const templateId = warning.warning_id && ID_PATTERN.test(String(warning.warning_id))
    ? String(warning.warning_id)
    : nextId(prefix, boss.warnings);
  const template = {
    id: boss.warnings.some((row) => row.id === templateId) ? nextId(templateId, boss.warnings) : templateId,
    name: warning.name || pattern.name || "전조",
    turns: Math.max(1, Number(warning.turns || 1)),
    pattern,
    success_pattern: warning.success_pattern && typeof warning.success_pattern === "object" ? warning.success_pattern : undefined,
    objectives: warningObjectivesFromLegacy(warning, defaultObjective),
    success_warning_id: warning.success_warning_id || warning.on_success_warning_id || warning.next_success_warning_id || "",
    failure_warning_id: warning.failure_warning_id || warning.on_failure_warning_id || warning.next_failure_warning_id || "",
    failure_variants: Array.isArray(warning.failure_variants) ? warning.failure_variants : [],
    activation_conditions: Array.isArray(warning.activation_conditions)
      ? warning.activation_conditions
      : Array.isArray(warning.trigger_conditions)
        ? warning.trigger_conditions
        : Array.isArray(warning.spawn_conditions)
          ? warning.spawn_conditions
          : Array.isArray(warning.conditions)
            ? warning.conditions
            : [],
  };
  template.pattern.id = template.id;
  template.pattern.name = template.name;
  normalizeFailureVariants(boss, template);
  normalizeWarningSuccessPattern(boss, template);
  normalizeWarningActivationConditions(template);
  boss.warnings.push(template);
  warning.warning_id = template.id;
  delete warning.pattern;
  delete warning.pattern_id;
  delete warning.objective;
  delete warning.required;
  delete warning.objectives;
  delete warning.failure_variants;
  delete warning.activation_conditions;
  delete warning.trigger_conditions;
  delete warning.spawn_conditions;
  delete warning.conditions;
  delete warning.success_warning_id;
  delete warning.failure_warning_id;
  delete warning.on_success_warning_id;
  delete warning.next_success_warning_id;
  delete warning.on_failure_warning_id;
  delete warning.next_failure_warning_id;
}

function normalizeWarningTemplate(boss, warning) {
  warning.objectives = warningObjectivesFromLegacy(warning, "damage");
  if (!warning.pattern || typeof warning.pattern !== "object") {
    if (warning.pattern_id) {
      warning.pattern = structuredClone(findBossPattern(boss, warning.pattern_id) || blankBossPattern(boss, "warning_failure", "전조 실패 효과"));
      warning.pattern.id = String(warning.pattern_id);
      delete warning.pattern_id;
    } else {
      warning.pattern = blankBossPattern(boss, "warning_failure", "전조 실패 효과");
    }
  }
  normalizeBossPattern(boss, warning.pattern, "warning_failure", "전조 실패 효과");
  normalizeWarningSuccessPattern(boss, warning);
  normalizeFailureVariants(boss, warning);
  warning.name ||= warning.pattern.name || warning.id || "전조";
  warning.id ||= nextId("warning", boss.warnings);
  warning.activation_priority = Math.trunc(Number(warning.activation_priority ?? warning.priority ?? warning.spawn_priority ?? 0) || 0);
  delete warning.priority;
  delete warning.spawn_priority;
  normalizeWarningFollowupIds(warning);
  normalizeWarningActivationConditions(warning);
  warning.pattern.id = warning.id;
  warning.pattern.name = warning.name;
  delete warning.pattern_id;
  warning.turns = Math.max(1, Number(warning.turns || 1));
}

function normalizeWarningFollowupIds(warning) {
  const success = warning.success_warning_id ?? warning.on_success_warning_id ?? warning.next_success_warning_id ?? "";
  const failure = warning.failure_warning_id ?? warning.on_failure_warning_id ?? warning.next_failure_warning_id ?? "";
  delete warning.on_success_warning_id;
  delete warning.next_success_warning_id;
  delete warning.on_failure_warning_id;
  delete warning.next_failure_warning_id;
  if (success) {
    warning.success_warning_id = String(success);
  } else {
    delete warning.success_warning_id;
  }
  if (failure) {
    warning.failure_warning_id = String(failure);
  } else {
    delete warning.failure_warning_id;
  }
}

function normalizeWarningActivationConditions(warning) {
  const source = Array.isArray(warning.activation_conditions)
    ? warning.activation_conditions
    : Array.isArray(warning.trigger_conditions)
      ? warning.trigger_conditions
      : Array.isArray(warning.spawn_conditions)
        ? warning.spawn_conditions
        : Array.isArray(warning.conditions)
          ? warning.conditions
          : [];
  delete warning.trigger_conditions;
  delete warning.spawn_conditions;
  delete warning.conditions;
  warning.activation_conditions = source
    .filter((condition) => condition && typeof condition === "object")
    .map(normalizeWarningActivationCondition)
    .filter(Boolean);
  if (!warning.activation_conditions.length) {
    delete warning.activation_conditions;
  }
}

function warningActivationConditionKind(condition) {
  const kind = String(condition.kind || condition.type || condition.condition || "stack");
  const aliases = {
    stack_count: "stack",
    stacks: "stack",
    stack_level: "stack",
    stack_ratio: "stack_compare",
    stack_majority: "stack_compare",
    stack_greater: "stack_compare",
    compare_stack: "stack_compare",
    turn_mod: "turn_multiple",
    turn_modulo: "turn_multiple",
    turn_divisible: "turn_multiple",
    turn_count_multiple: "turn_multiple",
    turn: "turn_range",
    turn_count: "turn_range",
    boss_hp: "boss_hp_ratio",
    hp: "boss_hp_ratio",
    hp_ratio: "boss_hp_ratio",
    hp_range: "boss_hp_ratio",
    ct: "ct_ready",
  };
  return aliases[kind] || kind;
}

function normalizeWarningActivationCondition(condition) {
  let kind = warningActivationConditionKind(condition);
  if (!WARNING_ACTIVATION_CONDITIONS.some(([id]) => id === kind)) {
    kind = "stack";
  }
  if (kind === "stack") {
    const minStacks = Number(condition.min_stacks ?? condition.min ?? condition.stacks ?? 1);
    const maxStacks = Number(condition.max_stacks ?? condition.max ?? -1);
    const stackId = condition.stack_effect_id || condition.effect_id || condition.id || state.content.stack_effects?.[0]?.id || "";
    if (!stackId) {
      return null;
    }
    return {
      kind,
      stack_effect_id: stackId,
      target: condition.target === "player" ? "player" : "boss",
      min_stacks: Math.max(0, Number.isFinite(minStacks) ? minStacks : 1),
      max_stacks: Number.isFinite(maxStacks) ? maxStacks : -1,
    };
  }
  if (kind === "stack_compare") {
    const stackId = condition.stack_effect_id || condition.effect_id || condition.id || state.content.stack_effects?.[0]?.id || "";
    const compareStackId = condition.compare_stack_effect_id
      || condition.other_stack_effect_id
      || condition.right_stack_effect_id
      || condition.compare_effect_id
      || state.content.stack_effects?.[1]?.id
      || stackId;
    if (!stackId || !compareStackId) {
      return null;
    }
    const aliases = {
      ">": "gt",
      greater: "gt",
      ">=": "gte",
      at_least: "gte",
      "<": "lt",
      less: "lt",
      "<=": "lte",
      at_most: "lte",
      "=": "eq",
      "==": "eq",
      equal: "eq",
      more_than_half: "majority",
      strict_majority: "majority",
    };
    let operator = aliases[condition.operator || condition.op || condition.comparison] || condition.operator || condition.op || condition.comparison || "gte";
    if (!STACK_COMPARE_OPERATORS.some(([id]) => id === operator)) {
      operator = "gte";
    }
    const compareTargetSource = condition.compare_target ?? condition.other_target ?? condition.right_target ?? condition.target;
    return {
      kind,
      stack_effect_id: stackId,
      target: condition.target === "player" ? "player" : "boss",
      compare_stack_effect_id: compareStackId,
      compare_target: compareTargetSource === "player" ? "player" : "boss",
      operator,
      multiplier: Number.isFinite(Number(condition.multiplier ?? condition.ratio))
        ? Number(condition.multiplier ?? condition.ratio)
        : 1,
      offset: Number.isFinite(Number(condition.offset)) ? Number(condition.offset) : 0,
    };
  }
  if (kind === "turn_multiple") {
    const multiple = Number(condition.multiple ?? condition.mod ?? condition.divisor ?? condition.value ?? 2);
    return { kind, multiple: Math.max(1, Number.isFinite(multiple) ? multiple : 2) };
  }
  if (kind === "turn_range") {
    const minTurn = Number(condition.min_turn ?? condition.min ?? condition.turn ?? 1);
    const maxTurn = Number(condition.max_turn ?? condition.max ?? -1);
    return {
      kind,
      min_turn: Math.max(1, Number.isFinite(minTurn) ? minTurn : 1),
      max_turn: Number.isFinite(maxTurn) ? maxTurn : -1,
    };
  }
  if (kind === "boss_hp_ratio") {
    return {
      kind,
      min_ratio: normalizeUiHpThreshold(condition.min_ratio ?? condition.min_hp ?? condition.min_hp_ratio ?? condition.min ?? 0),
      max_ratio: normalizeUiHpThreshold(condition.max_ratio ?? condition.max_hp ?? condition.max_hp_ratio ?? condition.max ?? 1),
    };
  }
  if (kind === "ct_ready") {
    return { kind, ct_ready: normalizeBooleanValue(condition.ct_ready ?? condition.ready, true) };
  }
  return null;
}

function blankBossPattern(boss, prefix, name) {
  return {
    id: nextId(prefix, bossWarningPatterns(boss)),
    name,
    damage_multiplier: 0,
    hits: 0,
    self_hp_loss_ratio: 0,
    player_mods: {},
    boss_mods: {},
    player_stat_effects: [],
    boss_stat_effects: [],
    effect_actions: [],
    duration: 0,
  };
}

function normalizeBossPattern(boss, pattern, prefix, name) {
  pattern.id ||= nextId(prefix, bossWarningPatterns(boss));
  pattern.name ||= name;
  pattern.damage_multiplier ??= 0;
  pattern.hits ??= 0;
  normalizePlainDamage(pattern);
  normalizeSelfHpLoss(pattern);
  pattern.player_mods ||= {};
  pattern.boss_mods ||= {};
  pattern.duration ??= 0;
  migratePatternStatEffects(pattern);
  pattern.effect_actions ||= [];
}

function normalizePlainDamage(pattern) {
  const raw = pattern.plain_damage ?? pattern.neutral_damage ?? pattern.true_damage;
  delete pattern.neutral_damage;
  delete pattern.true_damage;
  if (!raw) {
    delete pattern.plain_damage;
    return;
  }
  let mode = "flat";
  let value = 0;
  if (typeof raw === "object") {
    mode = raw.mode || raw.type || "flat";
    if (["fixed", "amount", "value"].includes(mode)) {
      mode = "flat";
    } else if (["target_max_hp", "target_max_hp_percent", "max_hp", "max_hp_ratio", "max_hp_percent", "hp_percent", "percent", "ratio"].includes(mode)) {
      mode = "target_max_hp_ratio";
    } else if (!PLAIN_DAMAGE_MODES.some(([id]) => id === mode)) {
      mode = "none";
    }
    value = Number(raw.value ?? raw.amount ?? raw.ratio ?? raw.percent ?? 0);
    if (mode === "target_max_hp_ratio" && (raw.percent != null || value > 1)) {
      value /= 100;
    }
  } else {
    value = Number(raw);
  }
  value = Number.isFinite(value) ? Math.max(0, value) : 0;
  if (mode === "none" || value <= 0) {
    delete pattern.plain_damage;
    return;
  }
  pattern.plain_damage = { mode, value };
}

function normalizeSelfHpLoss(pattern) {
  let raw = pattern.self_hp_loss_ratio ?? pattern.self_hp_loss ?? pattern.hp_loss_ratio ?? pattern.hp_loss ?? 0;
  delete pattern.self_hp_loss;
  delete pattern.hp_loss_ratio;
  delete pattern.hp_loss;
  if (raw && typeof raw === "object") {
    raw = raw.value ?? raw.ratio ?? raw.amount ?? raw.percent ?? 0;
  }
  const value = Number(raw || 0);
  pattern.self_hp_loss_ratio = Number.isFinite(value) ? Math.max(0, value) : 0;
}

function normalizeWarningSuccessPattern(boss, warning) {
  let pattern = warning.success_pattern ?? warning.success_effect ?? warning.on_success;
  delete warning.success_effect;
  delete warning.on_success;
  if (!pattern || typeof pattern !== "object") {
    delete warning.success_pattern;
    return;
  }
  pattern.id ||= nextId(`${warning.id || "warning"}_success`, bossWarningPatterns(boss));
  pattern.name ||= `${warning.name || "전조"} 성공 효과`;
  normalizeBossPattern(boss, pattern, `${warning.id || "warning"}_success`, pattern.name);
  warning.success_pattern = pattern;
}

function normalizeFailureVariants(boss, warning) {
  warning.failure_variants = Array.isArray(warning.failure_variants) ? warning.failure_variants : [];
  warning.failure_variants = warning.failure_variants
    .filter((variant) => variant && typeof variant === "object")
    .map((variant, index) => normalizeFailureVariant(boss, warning, variant, index))
    .filter(Boolean);
}

function normalizeFailureVariant(boss, warning, variant, index) {
  variant.conditions = Array.isArray(variant.conditions) ? variant.conditions : [];
  variant.conditions = variant.conditions
    .filter((condition) => condition && typeof condition === "object")
    .map((condition) => {
      const minStacks = Number(condition.min_stacks ?? condition.min ?? condition.stacks ?? 1);
      const maxStacks = Number(condition.max_stacks ?? condition.max ?? -1);
      return {
        stack_effect_id: condition.stack_effect_id || condition.effect_id || condition.id || state.content.stack_effects?.[0]?.id || "",
        target: condition.target === "player" ? "player" : "boss",
        min_stacks: Math.max(0, Number.isFinite(minStacks) ? minStacks : 1),
        max_stacks: Number.isFinite(maxStacks) ? maxStacks : -1,
      };
    })
    .filter((condition) => condition.stack_effect_id);
  if (!variant.pattern || typeof variant.pattern !== "object") {
    variant.pattern = blankBossPattern(boss, `${warning.id || "warning"}_variant`, `${warning.name || "전조"} 변형 ${index + 1}`);
  }
  variant.pattern.id ||= nextId(`${warning.id || "warning"}_failure_variant`, bossWarningPatterns(boss));
  variant.pattern.name ||= variant.name || `${warning.name || "전조"} 변형 ${index + 1}`;
  variant.name ||= variant.pattern.name;
  normalizeBossPattern(boss, variant.pattern, `${warning.id || "warning"}_failure_variant`, variant.name);
  return variant;
}

function warningObjectivesFromLegacy(warning, defaultObjective) {
  const source = Array.isArray(warning.objectives) && warning.objectives.length
    ? warning.objectives
    : [{ objective: warning.objective || defaultObjective, required: warning.required ?? 1 }];
  const rows = source.map((objective) => ({
    objective: objective.objective || objective.kind || defaultObjective,
    required: Math.max(1, Number(objective.required || 1)),
    min_damage: Math.max(0, Number(objective.min_damage || 0)),
  }));
  return rows.length ? rows : [{ objective: defaultObjective, required: 1 }];
}

function bossWarningPatterns(boss) {
  return [
    ...(boss.patterns || []),
    ...(boss.warnings || []).map((warning) => warning.pattern).filter(Boolean),
    ...(boss.warnings || []).map((warning) => warning.success_pattern).filter(Boolean),
    ...(boss.warnings || [])
      .flatMap((warning) => warning.failure_variants || [])
      .map((variant) => variant.pattern)
      .filter(Boolean),
    ...(boss.hp_effects || [])
      .map((effect) => effect.pattern)
      .filter(Boolean),
  ];
}

function bossWarningOptions(boss) {
  return (boss.warnings || []).map((warning) => [warning.id, `${warning.name || warning.id} (${warning.id})`]);
}

function bossWarningLinkOptions(boss) {
  return [["", "없음"], ...bossWarningOptions(boss)];
}

function findBossWarning(boss, id) {
  return (boss.warnings || []).find((warning) => warning.id === id);
}

function findBossPattern(boss, id) {
  return (boss.patterns || []).find((pattern) => pattern.id === id);
}

function makeBossWarningTemplate(boss, prefix = "warning") {
  return {
    id: nextId(prefix, boss.warnings || []),
    name: "새 전조",
    activation_priority: 0,
    pattern: blankBossPattern(boss, `${prefix}_failure`, "전조 실패 효과"),
    objectives: [{ objective: "damage", required: 1 }],
  };
}

function ensureFirstBossWarning(boss, prefix = "warning") {
  boss.warnings ||= [];
  if (!boss.warnings.length) {
    boss.warnings.push(makeBossWarningTemplate(boss, prefix));
  }
  return boss.warnings[0].id;
}

function mainDetail(title, row, body) {
  const rows = state.content[state.tab] || [];
  const detail = document.getElementById("detailPanel");
  const header = el("div", { className: "panel-header" }, [
    el("h2", {}, title),
    el("div", { className: "actions" }, [
      el("button", {
        type: "button",
        onclick: () => {
          const clone = structuredClone(row);
          clone.id = nextId(`${row.id}_copy`, rows);
          clone.name = `${row.name || row.id} Copy`;
          rows.push(clone);
          state.selected[state.tab] = clone.id;
          markDirty();
          render();
        },
      }, "복제"),
      el("button", {
        type: "button",
        className: "danger",
        onclick: () => {
          if (!confirm(`${row.name || row.id} 삭제?`)) {
            return;
          }
          const removedId = String(row.id ?? "");
          const changed = deleteContentReferences(state.tab, removedId);
          const index = rows.indexOf(row);
          if (index >= 0) {
            rows.splice(index, 1);
          }
          state.selected[state.tab] = rows[Math.max(0, index - 1)]?.id;
          markDirty();
          if (changed > 0) {
            setStatus(`ID 삭제: ${removedId} · 참조 ${changed}개 자동 삭제/정리`);
          }
          render();
        },
      }, "삭제"),
    ]),
  ]);
  detail.replaceChildren(header, body);
}

function enemyEditor(dungeon) {
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      dungeon.enemies.push({
        id: nextId("enemy", dungeon.enemies),
        name: "New Enemy",
        weight: 10,
        stats: { base_atk: 8, max_hp: 80 },
        gold: 0,
        exp: 0,
        rare: false,
        description: "",
        rewards: blankReward(),
      });
      markDirty();
      render();
    },
  }, "몬스터 추가");

  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "등장 몬스터"),
      addButton,
    ]),
    el("div", { className: "rows" }, dungeon.enemies.map((enemy, index) => enemyPanel(dungeon, enemy, index))),
  ]);
}

function enemyPanel(dungeon, enemy, index) {
  delete enemy.rank;
  delete enemy.drop_chance;
  delete enemy.consolation_rewards;
  const remove = el("button", {
    type: "button",
    className: "danger",
    onclick: () => {
      dungeon.enemies.splice(index, 1);
      markDirty();
      render();
    },
  }, "삭제");
  return el("div", { className: "subpanel" }, [
    el("div", { className: "subpanel-head" }, [
      el("div", { className: "subpanel-title" }, [
        el("strong", {}, enemy.name || enemy.id),
        el("span", { className: "badge" }, enemy.rare ? "레어" : "일반"),
      ]),
      remove,
    ]),
    el("div", { className: "form-grid three" }, [
      textField("ID", enemy, "id", { normalize: normalizeIdValue }),
      textField("이름", enemy, "name"),
      numberField("등장 가중치", enemy, "weight", { step: 1 }),
      numberField("기본 골드", enemy, "gold", { step: 1 }),
      numberField("기본 경험치", enemy, "exp", { step: 1 }),
      checkboxField("보너스 몬스터", enemy, "rare"),
      textAreaField("설명", enemy, "description", { full: true }),
    ]),
    statsEditor(enemy, "stats", "몬스터 스탯"),
    rewardEditor(enemy, "rewards", "드랍 보상"),
  ]);
}

function normalizeBossHpEffects(boss) {
  const rows = Array.isArray(boss.hp_effects)
    ? boss.hp_effects
    : Array.isArray(boss.hp_instant_effects)
      ? boss.hp_instant_effects
      : Array.isArray(boss.instant_hp_effects)
        ? boss.instant_hp_effects
        : [];
  delete boss.hp_instant_effects;
  delete boss.instant_hp_effects;
  boss.hp_effects = rows
    .filter((row) => row && typeof row === "object")
    .map((row, index) => {
      const thresholds = normalizeUiHpThresholds(row.thresholds ?? row.threshold ?? row.pattern?.threshold ?? 0.5);
      let pattern = row.pattern && typeof row.pattern === "object"
        ? row.pattern
        : Object.fromEntries(Object.entries(row).filter(([key]) => !["threshold", "thresholds", "name"].includes(key)));
      if (!pattern || typeof pattern !== "object") {
        pattern = blankBossPattern(boss, `${boss.id || "boss"}_hp_effect`, `HP 즉시 효과 ${index + 1}`);
      }
      pattern.id ||= row.id || nextId(`${boss.id || "boss"}_hp_effect`, bossWarningPatterns(boss));
      pattern.name ||= row.name || `HP 즉시 효과 ${index + 1}`;
      pattern.threshold = thresholds[0] ?? 0.5;
      normalizeBossPattern(boss, pattern, `${boss.id || "boss"}_hp_effect`, pattern.name);
      delete row.threshold;
      return { thresholds, pattern };
    })
    .sort((a, b) => Number((b.thresholds || [0])[0] || 0) - Number((a.thresholds || [0])[0] || 0));
}

function normalizeUiHpThreshold(value) {
  let threshold = Number(value || 0);
  if (threshold > 1) {
    threshold /= 100;
  }
  return Math.max(0, Math.min(1, Number.isFinite(threshold) ? threshold : 0));
}

function normalizeUiHpThresholds(value, options = {}) {
  const dedupe = options.dedupe ?? true;
  const sort = options.sort ?? true;
  const source = Array.isArray(value) ? value : [value];
  const thresholds = source
    .map((threshold) => normalizeUiHpThreshold(threshold))
    .filter((threshold) => Number.isFinite(threshold));
  const normalized = dedupe
    ? Array.from(new Set(thresholds.map((threshold) => round(threshold, 6))))
    : thresholds;
  const result = normalized.length ? normalized : [0.5];
  return sort ? result.sort((a, b) => b - a) : result;
}

function normalizeBossHpLocks(boss) {
  const rows = Array.isArray(boss.hp_locks)
    ? boss.hp_locks
    : Array.isArray(boss.hp_lock_thresholds)
      ? boss.hp_lock_thresholds
      : [];
  delete boss.hp_lock_thresholds;
  boss.hp_locks = Array.from(new Set(rows
    .map((row) => {
      const value = row && typeof row === "object"
        ? (row.threshold ?? row.hp ?? row.value)
        : row;
      return round(normalizeUiHpThreshold(value), 6);
    })
    .filter((threshold) => threshold > 0 && threshold < 1)))
    .sort((a, b) => b - a);
}

function nextBossHpLock(locks) {
  const used = new Set((locks || []).map((threshold) => round(normalizeUiHpThreshold(threshold), 6)));
  for (const candidate of [0.8, 0.5, 0.25, 0.2, 0.1]) {
    const normalized = round(candidate, 6);
    if (!used.has(normalized)) {
      return normalized;
    }
  }
  for (let percent = 95; percent >= 5; percent -= 5) {
    const candidate = round(percent / 100, 6);
    if (!used.has(candidate)) {
      return candidate;
    }
  }
  return 0.5;
}

function bossHpLockEditor(boss) {
  normalizeBossHpLocks(boss);
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      boss.hp_locks.push(nextBossHpLock(boss.hp_locks));
      normalizeBossHpLocks(boss);
      markDirty();
      render();
    },
  }, "락 추가");
  const rows = boss.hp_locks.map((threshold, index) => {
    const proxy = { threshold };
    return el("div", { className: "row two" }, [
      numberField("HP 기준", proxy, "threshold", {
        step: 0.01,
        onChange: (value) => {
          boss.hp_locks[index] = normalizeUiHpThreshold(value);
        },
      }),
      deleteButton(() => {
        boss.hp_locks.splice(index, 1);
        normalizeBossHpLocks(boss);
        markDirty();
        render();
      }),
    ]);
  });
  return el("section", { className: "section themed hp-lock-section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "HP 락"),
      addButton,
    ]),
    el("div", { className: "rows" }, rows.length
      ? rows
      : [el("div", { className: "empty" }, "HP 락 없음")]),
  ]);
}

function syncHpEffectThresholds(effect) {
  effect.thresholds = normalizeUiHpThresholds(effect.thresholds, { dedupe: false, sort: false });
  if (effect.pattern) {
    effect.pattern.threshold = effect.thresholds.length ? Math.max(...effect.thresholds) : 0.5;
  }
}

function nextHpEffectThreshold(thresholds) {
  const used = new Set(normalizeUiHpThresholds(thresholds).map((threshold) => round(threshold, 6)));
  const sorted = Array.from(used).sort((a, b) => b - a);
  const seed = sorted.length ? sorted[sorted.length - 1] : 0.5;
  const common = [1, 0.95, 0.8, 0.75, 0.65, 0.5, 0.25, 0.1, 0.03, 0];
  for (const candidate of common.filter((threshold) => threshold < seed)) {
    const normalized = round(normalizeUiHpThreshold(candidate), 6);
    if (!used.has(normalized)) {
      return normalized;
    }
  }
  for (const candidate of [seed - 0.05, seed - 0.1, ...common]) {
    const normalized = round(normalizeUiHpThreshold(candidate), 6);
    if (!used.has(normalized)) {
      return normalized;
    }
  }
  for (let percent = 99; percent >= 1; percent -= 1) {
    const candidate = round(percent / 100, 6);
    if (!used.has(candidate)) {
      return candidate;
    }
  }
  return 0;
}

function bossHpEffectEditor(boss) {
  normalizeBossHpEffects(boss);
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      const pattern = blankBossPattern(boss, `${boss.id || "boss"}_hp_effect`, "HP 즉시 효과");
      const effect = { thresholds: [0.5], pattern };
      boss.hp_effects.push(effect);
      state.openDetails[hpEffectDetailKey(boss, effect, boss.hp_effects.length - 1)] = true;
      markDirty();
      render();
    },
  }, "HP 즉시 효과 추가");
  return el("section", { className: "section themed hp-effect-section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "HP 즉시 효과"),
      addButton,
    ]),
    el("div", { className: "rows" }, boss.hp_effects.length
      ? boss.hp_effects.map((effect, index) => hpEffectPanel(boss, effect, index))
      : [el("div", { className: "empty" }, "HP 즉시 효과 없음")]),
  ]);
}

function hpEffectPanel(boss, effect, index) {
  const detailKey = hpEffectDetailKey(boss, effect, index);
  const isOpen = state.openDetails[detailKey] ?? false;
  const title = effect.pattern?.name || `HP 즉시 효과 ${index + 1}`;
  syncHpEffectThresholds(effect);
  return el("details", {
    className: "subpanel",
    open: isOpen,
    "data-detail-key": detailKey,
    ontoggle: (event) => {
      state.openDetails[detailKey] = event.currentTarget.open;
    },
  }, [
    el("summary", { className: "subpanel-head" }, [
      el("div", { className: "subpanel-title" }, [
        el("strong", {}, title),
        el("span", { className: "badge" }, hpThresholdBadgeText(effect.thresholds)),
      ]),
      deleteButton(() => {
        boss.hp_effects.splice(index, 1);
        markDirty();
        render();
      }),
    ]),
    el("div", { className: "panel-body" }, [
      el("div", { className: "form-grid three" }, [
        textField("효과 이름", effect.pattern, "name"),
      ]),
      hpEffectThresholdEditor(effect),
      patternEffectEditor(effect.pattern, {
        title: "즉시 발동 효과",
        description: "턴 시작 시 해당 HP 이하로 처음 내려가면 즉시 실행됩니다.",
        hideIdentity: true,
        collapsibleKey: `${detailKey}:effect`,
        defaultOpen: true,
      }),
    ]),
  ]);
}

function hpThresholdBadgeText(thresholds) {
  const values = normalizeUiHpThresholds(thresholds);
  const text = values.slice(0, 3).map((threshold) => `${round(threshold * 100, 2)}%`).join(", ");
  const rest = values.length > 3 ? ` 외 ${values.length - 3}` : "";
  return `HP ${text}${rest}`;
}

function hpEffectThresholdEditor(effect) {
  syncHpEffectThresholds(effect);
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      effect.thresholds.push(nextHpEffectThreshold(effect.thresholds));
      syncHpEffectThresholds(effect);
      markDirty();
      render();
    },
  }, "임계값 추가");
  const rows = effect.thresholds.map((threshold, index) => {
    const proxy = { threshold };
    return el("div", { className: "row two" }, [
      numberField("HP 임계값", proxy, "threshold", {
        step: 0.01,
        onChange: (value) => {
          effect.thresholds[index] = normalizeUiHpThreshold(value);
          syncHpEffectThresholds(effect);
        },
      }),
      deleteButton(() => {
        effect.thresholds.splice(index, 1);
        syncHpEffectThresholds(effect);
        markDirty();
        render();
      }),
    ]);
  });
  return el("section", { className: "section nested-section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "HP 임계값"),
      addButton,
    ]),
    el("div", { className: "rows" }, rows),
  ]);
}

function hpEffectDetailKey(boss, effect, index) {
  return `boss-hp-effect:${boss.id || boss.name || "boss"}:${effect.pattern?.id || index}`;
}

function bossHpWarningEditor(boss) {
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      boss.hp_warnings.push({
        threshold: 0.5,
        warning_id: ensureFirstBossWarning(boss, "hp_warning"),
      });
      markDirty();
      render();
    },
  }, "체력 전조 추가");
  return el("section", { className: "section themed hp-warning-section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "체력 전조"),
      addButton,
    ]),
    el("div", { className: "rows" }, boss.hp_warnings.map((warning, index) => warningPanel(boss, boss.hp_warnings, warning, index))),
  ]);
}

function bossCtEditor(boss) {
  const addGauge = el("button", {
    type: "button",
    onclick: () => {
      boss.ct.gauge_by_hp.push({ above: 0, max: 5 });
      markDirty();
      render();
    },
  }, "CT 칸 추가");
  const addWarning = el("button", {
    type: "button",
    onclick: () => {
      const warningId = ensureFirstBossWarning(boss, "ct_warning");
      boss.ct.warnings_by_hp.push({
        above: 1,
        warning_id: warningId,
        warning_ids: [warningId],
      });
      markDirty();
      render();
    },
  }, "CT 전조 추가");

  return el("section", { className: "section themed ct-section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "CT"),
      addGauge,
    ]),
    el("div", { className: "rows" }, boss.ct.gauge_by_hp.map((row, index) => el("div", { className: "row two" }, [
      numberField("HP 비율 초과", row, "above", { step: 0.01 }),
      numberField("최대 칸", row, "max", { step: 1 }),
      deleteButton(() => {
        boss.ct.gauge_by_hp.splice(index, 1);
        markDirty();
        render();
      }),
    ]))),
    el("div", { className: "section nested-section" }, [
      el("div", { className: "section-head" }, [
        el("h3", {}, "CT 전조"),
        addWarning,
      ]),
      el("div", { className: "rows" }, boss.ct.warnings_by_hp.map((warning, index) => warningPanel(boss, boss.ct.warnings_by_hp, warning, index, "above"))),
    ]),
  ]);
}

function warningPanel(boss, rows, warning, index, thresholdKey = "threshold") {
  normalizeWarningTrigger(boss, warning, index, thresholdKey === "above" ? "ct_warning" : "hp_warning", thresholdKey === "above" ? "hits" : "damage");
  if (thresholdKey === "above") {
    normalizeCtWarningIds(boss, warning);
  }
  const warningIds = thresholdKey === "above" ? warning.warning_ids : [warning.warning_id];
  const templates = warningIds.map((warningId) => findBossWarning(boss, warningId)).filter(Boolean);
  const template = templates[0] || findBossWarning(boss, warning.warning_id);
  const title = thresholdKey === "above" ? "CT 전조" : "체력 전조";
  const badgeText = thresholdKey === "above"
    ? templates.map((row) => row.name || row.id).join(" / ") || "전조 후보"
    : template?.name || "전조";
  return el("div", { className: "subpanel" }, [
    el("div", { className: "subpanel-head" }, [
      el("div", { className: "subpanel-title" }, [
        el("strong", {}, `${title} ${index + 1}`),
        el("span", { className: "badge" }, badgeText),
      ]),
      deleteButton(() => {
        rows.splice(index, 1);
        markDirty();
        render();
      }),
    ]),
    el("div", { className: "form-grid three" }, [
      numberField(thresholdKey === "above" ? "HP 구간 상한" : "HP 임계값", warning, thresholdKey, { step: 0.01 }),
      thresholdKey === "above"
        ? ctWarningCandidatesEditor(boss, warning)
        : selectField("전조", warning, "warning_id", bossWarningOptions(boss), { rerender: true }),
    ]),
  ]);
}

function ctWarningCandidatesEditor(boss, warning) {
  normalizeCtWarningIds(boss, warning);
  const rows = warning.warning_ids.map((warningId, index) => {
    const proxy = { warning_id: warningId };
    return el("div", { className: "form-grid two" }, [
      selectField(`후보 ${index + 1}`, proxy, "warning_id", bossWarningOptions(boss), {
        rerender: true,
        onChange: (nextValue) => {
          warning.warning_ids[index] = String(nextValue || "");
          normalizeCtWarningIds(boss, warning);
        },
      }),
      deleteButton(() => {
        warning.warning_ids.splice(index, 1);
        normalizeCtWarningIds(boss, warning);
        markDirty();
        render();
      }),
    ]);
  });
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      warning.warning_ids.push(nextCtWarningCandidateId(boss, warning.warning_ids));
      normalizeCtWarningIds(boss, warning);
      markDirty();
      render();
    },
  }, "후보 추가");
  return fieldWrap("전조 후보", el("div", { className: "rows" }, [...rows, addButton]), true);
}

function bossWarningTemplateEditor(boss) {
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      boss.warnings.push(makeBossWarningTemplate(boss));
      markDirty();
      render();
    },
  }, "전조 추가");

  return el("section", { className: "section themed warning-template-section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "전조 목록"),
      addButton,
    ]),
    el("div", { className: "rows" }, boss.warnings.length
      ? boss.warnings.map((warning, index) => bossWarningTemplatePanel(boss, warning, index))
      : [el("div", { className: "empty" }, "전조 없음")]),
  ]);
}

function bossWarningTemplatePanel(boss, warning, index) {
  normalizeWarningTemplate(boss, warning);
  return el("div", { className: "subpanel" }, [
    el("div", { className: "subpanel-head" }, [
      el("div", { className: "subpanel-title" }, [
        el("strong", {}, warning.name || warning.id),
        el("span", { className: "badge" }, warning.id),
      ]),
      deleteButton(() => {
        const removedId = warning.id;
        boss.warnings.splice(index, 1);
        deleteBossWarningReferences(boss, removedId);
        markDirty();
        render();
      }),
    ]),
    el("div", { className: "form-grid four" }, [
      nestedIdField("전조 ID", warning, boss.warnings, (oldId, newId) => renameBossWarningReferences(boss, oldId, newId)),
      textField("전조 이름", warning, "name"),
      numberField("제한 턴", warning, "turns", { step: 1 }),
      numberField("발생 우선순위", warning, "activation_priority", { step: 1 }),
    ]),
    warningActivationConditionsEditor(warning),
    warningObjectivesEditor(warning),
    el("div", { className: "form-grid two" }, [
      selectField("성공 시 즉시 전조", warning, "success_warning_id", bossWarningLinkOptions(boss), { rerender: true }),
      selectField("실패 시 즉시 전조", warning, "failure_warning_id", bossWarningLinkOptions(boss), { rerender: true }),
    ]),
    patternEffectEditor(warning.pattern, {
      hideIdentity: true,
      title: "기본 실패 효과",
      collapsibleKey: warningPatternDetailKey(warning),
      defaultOpen: false,
    }),
    warningSuccessEffectEditor(boss, warning),
    warningFailureVariantsEditor(boss, warning),
  ]);
}

function makeWarningActivationCondition(kind = "stack") {
  if ((kind === "stack" || kind === "stack_compare") && !state.content.stack_effects?.length) {
    kind = "turn_multiple";
  }
  if (kind === "stack") {
    return {
      kind,
      stack_effect_id: state.content.stack_effects?.[0]?.id || "",
      target: "boss",
      min_stacks: 1,
      max_stacks: -1,
    };
  }
  if (kind === "stack_compare") {
    return {
      kind,
      stack_effect_id: state.content.stack_effects?.[0]?.id || "",
      target: "boss",
      compare_stack_effect_id: state.content.stack_effects?.[1]?.id || state.content.stack_effects?.[0]?.id || "",
      compare_target: "boss",
      operator: "majority",
      multiplier: 1,
      offset: 0,
    };
  }
  if (kind === "turn_multiple") {
    return { kind, multiple: 2 };
  }
  if (kind === "turn_range") {
    return { kind, min_turn: 1, max_turn: -1 };
  }
  if (kind === "boss_hp_ratio") {
    return { kind, min_ratio: 0, max_ratio: 1 };
  }
  if (kind === "ct_ready") {
    return { kind, ct_ready: true };
  }
  return { kind: "turn_multiple", multiple: 2 };
}

function warningActivationConditionsEditor(warning) {
  normalizeWarningActivationConditions(warning);
  warning.activation_conditions ||= [];
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      warning.activation_conditions.push(makeWarningActivationCondition());
      markDirty();
      render();
    },
  }, "발생 조건 추가");
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "발생 조건"),
      addButton,
    ]),
    el("div", { className: "rows" }, warning.activation_conditions.length
      ? warning.activation_conditions.map((condition, index) => warningActivationConditionRow(warning, condition, index))
      : [el("div", { className: "empty" }, "조건 없음")]),
  ]);
}

function warningActivationConditionRow(warning, condition, index) {
  const fields = [
    selectField("조건", condition, "kind", WARNING_ACTIVATION_CONDITIONS, {
      rerender: true,
      onChange: (nextKind) => {
        warning.activation_conditions[index] = makeWarningActivationCondition(nextKind);
      },
    }),
  ];
  if (condition.kind === "stack") {
    fields.push(
      selectField("스택", condition, "stack_effect_id", stackEffectOptions()),
      selectField("대상", condition, "target", FAILURE_STACK_TARGETS),
      numberField("최소 스택", condition, "min_stacks", { step: 1 }),
      numberField("최대 스택 (-1=없음)", condition, "max_stacks", { step: 1 }),
    );
  } else if (condition.kind === "stack_compare") {
    fields.push(
      selectField("왼쪽 스택", condition, "stack_effect_id", stackEffectOptions()),
      selectField("왼쪽 대상", condition, "target", FAILURE_STACK_TARGETS),
      selectField("비교", condition, "operator", STACK_COMPARE_OPERATORS, { rerender: true }),
      selectField("오른쪽 스택", condition, "compare_stack_effect_id", stackEffectOptions()),
      selectField("오른쪽 대상", condition, "compare_target", FAILURE_STACK_TARGETS),
    );
    if (condition.operator !== "majority") {
      fields.push(
        numberField("오른쪽 배율", condition, "multiplier", { step: 0.01 }),
        numberField("보정값", condition, "offset", { step: 1 }),
      );
    }
  } else if (condition.kind === "turn_multiple") {
    fields.push(numberField("몇 턴마다", condition, "multiple", { step: 1 }));
  } else if (condition.kind === "turn_range") {
    fields.push(
      numberField("시작 턴", condition, "min_turn", { step: 1 }),
      numberField("끝 턴 (-1=없음)", condition, "max_turn", { step: 1 }),
    );
  } else if (condition.kind === "boss_hp_ratio") {
    fields.push(
      numberField("최소 HP 비율", condition, "min_ratio", {
        step: 0.01,
        onChange: (value) => {
          condition.min_ratio = normalizeUiHpThreshold(value);
        },
      }),
      numberField("최대 HP 비율", condition, "max_ratio", {
        step: 0.01,
        onChange: (value) => {
          condition.max_ratio = normalizeUiHpThreshold(value);
        },
      }),
    );
  } else if (condition.kind === "ct_ready") {
    fields.push(checkboxField("CT가 가득 찼을 때", condition, "ct_ready"));
  }
  fields.push(deleteButton(() => {
    warning.activation_conditions.splice(index, 1);
    markDirty();
    render();
  }));
  const rowClass = condition.kind === "stack_compare"
    ? "seven"
    : condition.kind === "stack"
      ? "five"
      : "three";
  return el("div", { className: `row ${rowClass}` }, fields);
}

function warningSuccessEffectEditor(boss, warning) {
  normalizeWarningSuccessPattern(boss, warning);
  if (!warning.success_pattern) {
    return el("section", { className: "section" }, [
      el("div", { className: "section-head" }, [
        el("h3", {}, "성공 효과"),
        el("button", {
          type: "button",
          onclick: () => {
            warning.success_pattern = blankBossPattern(
              boss,
              `${warning.id || "warning"}_success`,
              `${warning.name || "전조"} 성공 효과`,
            );
            normalizeWarningSuccessPattern(boss, warning);
            state.openDetails[warningSuccessPatternDetailKey(warning)] = true;
            markDirty();
            render();
          },
        }, "성공 효과 추가"),
      ]),
      el("div", { className: "empty" }, "성공 효과 없음"),
    ]);
  }
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "성공 효과"),
      deleteButton(() => {
        delete warning.success_pattern;
        markDirty();
        render();
      }),
    ]),
    patternEffectEditor(warning.success_pattern, {
      hideIdentity: true,
      title: "성공 시 발동",
      description: "전조를 해제하면 실행됩니다.",
      collapsibleKey: warningSuccessPatternDetailKey(warning),
      defaultOpen: true,
    }),
  ]);
}

function warningFailureVariantsEditor(boss, warning) {
  normalizeFailureVariants(boss, warning);
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      const firstStack = state.content.stack_effects?.[0]?.id || "";
      const variantName = `${warning.name || "전조"} 조건부 실패 효과`;
      const variant = {
        name: variantName,
        conditions: firstStack ? [{ stack_effect_id: firstStack, target: "boss", min_stacks: 1, max_stacks: -1 }] : [],
        pattern: migratedFailureVariantPattern(boss, warning, variantName),
      };
      warning.failure_variants.push(variant);
      state.openDetails[failureVariantDetailKey(warning, variant, warning.failure_variants.length - 1)] = true;
      state.openDetails[failureVariantPatternDetailKey(warning, variant, warning.failure_variants.length - 1)] = true;
      markDirty();
      render();
    },
  }, "조건부 실패 효과 추가");

  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "조건부 실패 효과"),
      addButton,
    ]),
    el("div", { className: "rows" }, warning.failure_variants.length
      ? warning.failure_variants.map((variant, index) => failureVariantPanel(boss, warning, variant, index))
      : [el("div", { className: "empty" }, "조건부 실패 효과 없음")]),
  ]);
}

function failureVariantPanel(boss, warning, variant, index) {
  const summary = variant.name || variant.pattern?.name || `조건부 실패 효과 ${index + 1}`;
  const detailKey = failureVariantDetailKey(warning, variant, index);
  const isOpen = state.openDetails[detailKey] ?? false;
  return el("details", {
    className: "subpanel",
    open: isOpen,
    "data-detail-key": detailKey,
    ontoggle: (event) => {
      state.openDetails[detailKey] = event.currentTarget.open;
    },
  }, [
    el("summary", { className: "subpanel-head" }, [
      el("div", { className: "subpanel-title" }, [
        el("strong", {}, summary),
        el("span", { className: "badge" }, `${variant.conditions?.length || 0}조건`),
      ]),
    ]),
    el("div", { className: "panel-body" }, [
      el("div", { className: "form-grid two" }, [
        textField("변형 이름", variant, "name", {
          onChange: (value) => {
            if (variant.pattern) {
              variant.pattern.name = value;
            }
          },
        }),
        deleteButton(() => {
          warning.failure_variants.splice(index, 1);
          markDirty();
          render();
        }),
      ]),
      failureVariantConditionsEditor(variant),
      patternEffectEditor(variant.pattern, {
        title: "변형 실패 효과",
        description: "조건을 모두 만족하면 기본 실패 효과 대신 실행됩니다.",
        hideIdentity: true,
        collapsibleKey: failureVariantPatternDetailKey(warning, variant, index),
        defaultOpen: true,
      }),
    ]),
  ]);
}

function migratedFailureVariantPattern(boss, warning, variantName) {
  const pattern = structuredClone(warning.pattern || blankBossPattern(boss, `${warning.id || "warning"}_failure_variant`, variantName));
  pattern.id = nextId(`${warning.id || "warning"}_failure_variant`, bossWarningPatterns(boss));
  pattern.name = variantName;
  return pattern;
}

function failureVariantDetailKey(warning, variant, index) {
  return `warning-failure-variant:${warning.id || warning.name || "warning"}:${variant.pattern?.id || variant.name || index}`;
}

function failureVariantPatternDetailKey(warning, variant, index) {
  return `${failureVariantDetailKey(warning, variant, index)}:effect`;
}

function warningPatternDetailKey(warning) {
  return `warning-failure-effect:${warning.id || warning.name || "warning"}`;
}

function warningSuccessPatternDetailKey(warning) {
  return `warning-success-effect:${warning.id || warning.name || "warning"}`;
}

function failureVariantConditionsEditor(variant) {
  variant.conditions = Array.isArray(variant.conditions) ? variant.conditions : [];
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      variant.conditions.push({
        stack_effect_id: state.content.stack_effects?.[0]?.id || "",
        target: "boss",
        min_stacks: 1,
        max_stacks: -1,
      });
      markDirty();
      render();
    },
  }, "스택 조건 추가");
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "스택 조건"),
      addButton,
    ]),
    el("div", { className: "rows" }, variant.conditions.length
      ? variant.conditions.map((condition, index) => el("div", { className: "row five" }, [
        selectField("스택", condition, "stack_effect_id", stackEffectOptions()),
        selectField("대상", condition, "target", FAILURE_STACK_TARGETS),
        numberField("최소 스택", condition, "min_stacks", { step: 1 }),
        numberField("최대 스택 (-1=없음)", condition, "max_stacks", { step: 1 }),
        deleteButton(() => {
          variant.conditions.splice(index, 1);
          markDirty();
          render();
        }),
      ]))
      : [el("div", { className: "empty" }, "조건 없음")]),
  ]);
}

function warningObjectivesEditor(warning) {
  warning.objectives = warningObjectivesFromLegacy(warning, "damage");
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      warning.objectives.push({ objective: "damage", required: 1 });
      markDirty();
      render();
    },
  }, "요구 조건 추가");

  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "요구 조건"),
      addButton,
    ]),
    el("div", { className: "rows" }, warning.objectives.map((objective, index) => {
      const fields = [
        selectField("조건", objective, "objective", OBJECTIVES, { rerender: true }),
        numberField("요구량", objective, "required", { step: 1 }),
      ];
      if (objective.objective === "hits") {
        fields.push(numberField("타당 최소 데미지", objective, "min_damage", { step: 1 }));
      }
      fields.push(deleteButton(() => {
        warning.objectives.splice(index, 1);
        if (!warning.objectives.length) {
          warning.objectives.push({ objective: "damage", required: 1, min_damage: 0 });
        }
        markDirty();
        render();
      }));
      return el("div", { className: `row ${objective.objective === "hits" ? "three" : "two"}` }, fields);
    })),
  ]);
}

function patternEffectEditor(pattern, options = {}) {
  const playerEffectFallback = Boolean(pattern.player_undispellable);
  const bossEffectFallback = Boolean(pattern.boss_undispellable || pattern.undispellable);
  migratePatternStatEffects(pattern);
  const plainDamage = ensurePlainDamageEditorState(pattern);
  const title = options.title || "실패 시 발동";
  const description = options.description || "이 전조를 못 풀고 턴을 넘기면 실행됩니다.";
  const body = [
    el("div", { className: "form-grid three" }, [
      ...(options.hideIdentity ? [] : [
        options.idField || textField("효과 ID", pattern, "id"),
        textField("효과 이름", pattern, "name"),
      ]),
      numberField("피해 배율", pattern, "damage_multiplier", { step: 0.01 }),
      numberField("타수", pattern, "hits", { step: 1 }),
      numberField("자신 HP 감소 비율", pattern, "self_hp_loss_ratio", { step: 0.001 }),
      selectField("무속성 데미지", plainDamage, "mode", PLAIN_DAMAGE_MODES, {
        rerender: true,
        onChange: (nextMode) => {
          if (nextMode === "none") {
            plainDamage.value = 0;
          } else if (plainDamage.value <= 0) {
            plainDamage.value = nextMode === "target_max_hp_ratio" ? 0.01 : 1;
          }
        },
      }),
      ...(plainDamage.mode === "none" ? [] : [
        numberField(
          plainDamage.mode === "target_max_hp_ratio" ? "무속성 데미지 비율" : "무속성 데미지",
          plainDamage,
          "value",
          { step: plainDamage.mode === "target_max_hp_ratio" ? 0.001 : 1 },
        ),
      ]),
      numberField("지속 턴", pattern, "duration", { step: 1 }),
    ]),
    statEffectsEditor(pattern, "player_stat_effects", "유저 스탯 효과", pattern.duration || 1),
    statEffectsEditor(pattern, "boss_stat_effects", "보스 스탯 효과", pattern.duration || 1),
    specialEffectsEditor(pattern, "player_effects", "유저 특수 효과", pattern.duration || 1, playerEffectFallback),
    specialEffectsEditor(pattern, "boss_effects", "보스 특수 효과", pattern.duration || 1, bossEffectFallback),
    effectActionEditor(pattern, "effect_actions", "즉시 효과", {
      conditionTargets: FAILURE_STACK_TARGETS,
    }),
  ];
  if (options.collapsibleKey) {
    const isOpen = state.openDetails[options.collapsibleKey] ?? Boolean(options.defaultOpen);
    return el("details", {
      className: "subpanel",
      open: isOpen,
      "data-detail-key": options.collapsibleKey,
      ontoggle: (event) => {
        state.openDetails[options.collapsibleKey] = event.currentTarget.open;
      },
    }, [
      el("summary", { className: "subpanel-head" }, [
        el("div", { className: "subpanel-title" }, [
          el("strong", {}, title),
          el("span", { className: "muted" }, description),
        ]),
      ]),
      el("div", { className: "panel-body" }, body),
    ]);
  }
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, title),
      el("span", { className: "muted" }, description),
    ]),
    ...body,
  ]);
}

function ensurePlainDamageEditorState(pattern) {
  normalizePlainDamage(pattern);
  if (!pattern.plain_damage) {
    pattern.plain_damage = { mode: "none", value: 0 };
  }
  return pattern.plain_damage;
}

function rewardEditor(owner, key, title) {
  owner[key] ||= blankReward();
  const reward = owner[key];
  normalizeReward(reward);
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, title),
    ]),
    itemDropEditor(reward),
    materialDropEditor(reward),
  ]);
}

function normalizeReward(reward) {
  delete reward.gold;
  delete reward.exp;
  delete reward.stat_points;
  reward.items ||= [];
  reward.materials ||= [];
  reward.items = (reward.items || []).filter((drop) => {
    if (!drop || typeof drop !== "object") {
      return false;
    }
    delete drop.rank;
    normalizeRewardDropFields(drop, { defaultChance: 0, defaultMin: 1, defaultMax: 1 });
    return Boolean(drop.template_id || drop.item_id || drop.rarity);
  });
  reward.materials = (reward.materials || []).filter((drop) => {
    if (!drop || typeof drop !== "object" || !drop.id) {
      return false;
    }
    normalizeRewardDropFields(drop, { defaultChance: 1, defaultMin: 1, defaultMax: 1 });
    return true;
  });
}

function itemDropEditor(reward) {
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      const firstItemId = state.content.items[0]?.id;
      if (firstItemId) {
        reward.items.push({ chance: 1, template_id: firstItemId, min: 1, max: 1 });
      }
      markDirty();
      render();
    },
  }, "장비 드랍 추가");
  const rows = reward.items.map((drop, index) => {
    const itemId = drop.template_id ?? drop.item_id ?? "";
    const target = {
      item_id: itemId,
    };
    const targetField = itemId
      ? selectField("장비", target, "item_id", itemOptions(), {
        onChange: (value) => {
          delete drop.item_id;
          delete drop.template_id;
          if (value) {
            drop.template_id = value;
          }
        },
      })
      : fieldWrap("장비", el("div", { className: "readonly-value" }, `기존 랜덤: ${rarityLabel(drop.rarity) || drop.rarity}`));
    return el("div", { className: "row" }, [
      targetField,
      ...rewardDropChanceFields(drop),
      numberField("별", drop, "stars", { step: 1 }),
      deleteButton(() => {
        reward.items.splice(index, 1);
        markDirty();
        render();
      }),
    ]);
  });
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "장비 드랍"),
      addButton,
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "장비 드랍 없음")]),
  ]);
}

function materialDropEditor(reward) {
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      reward.materials.push({
        id: state.content.materials[0]?.id ?? "",
        chance: 1,
        min: 1,
        max: 1,
      });
      markDirty();
      render();
    },
  }, "재료 드랍 추가");
  const rows = reward.materials.map((drop, index) => el("div", { className: "row" }, [
    selectField("재료", drop, "id", materialOptions()),
    ...rewardDropChanceFields(drop),
    deleteButton(() => {
      reward.materials.splice(index, 1);
      markDirty();
      render();
    }),
  ]));
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "재료 드랍"),
      addButton,
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "재료 드랍 없음")]),
  ]);
}

function normalizeRewardDropFields(drop, { defaultChance, defaultMin, defaultMax }) {
  drop.chance = clampChance(drop.chance ?? defaultChance);
  drop.min = Math.max(1, Number(drop.min ?? drop.amount ?? defaultMin) || defaultMin);
  drop.max = Math.max(drop.min, Number(drop.max ?? defaultMax) || defaultMax);
  delete drop.amount;
  for (const prefix of ["owner", "participant"]) {
    const chanceKey = `${prefix}_chance`;
    if (drop[chanceKey] != null && drop[chanceKey] !== "") {
      drop[chanceKey] = clampChance(drop[chanceKey]);
    }
    const minKey = `${prefix}_min`;
    const maxKey = `${prefix}_max`;
    if (drop[minKey] != null && drop[minKey] !== "") {
      drop[minKey] = Math.max(1, Number(drop[minKey]) || drop.min);
    }
    if (drop[maxKey] != null && drop[maxKey] !== "") {
      const lower = Math.max(1, Number(drop[minKey] ?? drop.min) || drop.min);
      drop[maxKey] = Math.max(lower, Number(drop[maxKey]) || lower);
    }
  }
}

function clampChance(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return 0;
  }
  return Math.max(0, Math.min(1, number));
}

function rewardDropChanceFields(drop) {
  return [
    numberField("기본 확률", drop, "chance", { step: 0.01 }),
    numberField("기본 최소", drop, "min", { step: 1 }),
    numberField("기본 최대", drop, "max", { step: 1 }),
    optionalNumberField("자발 확률", drop, "owner_chance", { step: 0.01 }),
    optionalNumberField("자발 최소", drop, "owner_min", { step: 1 }),
    optionalNumberField("자발 최대", drop, "owner_max", { step: 1 }),
    optionalNumberField("참전 확률", drop, "participant_chance", { step: 0.01 }),
    optionalNumberField("참전 최소", drop, "participant_min", { step: 1 }),
    optionalNumberField("참전 최대", drop, "participant_max", { step: 1 }),
  ];
}

function materialCostEditor(recipe, title = "제작 재료") {
  recipe.materials ||= {};
  const entries = Object.entries(recipe.materials);
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      const materialId = state.content.materials.find((material) => recipe.materials[material.id] == null)?.id;
      if (materialId) {
        recipe.materials[materialId] = 1;
      }
      markDirty();
      render();
    },
  }, "재료 추가");

  const rows = entries.map(([materialId, count]) => {
    const proxy = { material_id: materialId, count };
    return el("div", { className: "row two" }, [
      selectField("재료", proxy, "material_id", materialOptions(), {
        onChange: (newId, oldId) => {
          if (newId !== oldId && Object.prototype.hasOwnProperty.call(recipe.materials, newId)) {
            showToast(`${newId} 재료는 이미 추가되어 있습니다.`, true);
            return false;
          }
          return renameObjectEntry(recipe.materials, oldId, newId, Number(proxy.count || 1));
        },
      }),
      numberField("수량", proxy, "count", {
        step: 1,
        onChange: (value) => {
          recipe.materials[proxy.material_id] = value;
        },
      }),
      deleteButton(() => {
        delete recipe.materials[proxy.material_id];
        markDirty();
        render();
      }),
    ]);
  });

  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, title),
      addButton,
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, `${title} 없음`)]),
  ]);
}

function normalizeContentForUi(content) {
  if (!content || typeof content !== "object") {
    return;
  }
  content.stack_effects ||= [];
  for (const item of content.items || []) {
    sortStatsTree(item);
  }
  for (const job of content.jobs || []) {
    sortStatsTree(job);
  }
  for (const skill of content.skills || []) {
    sortStatsTree(skill);
  }
  for (const dungeon of content.dungeons || []) {
    sortStatsTree(dungeon);
  }
  for (const boss of content.bosses || []) {
    sortStatsTree(boss);
  }
  for (const effect of content.stack_effects || []) {
    normalizeStackEffect(effect);
  }
}

function sortActiveEditorStats(tab = state.tab) {
  if (!state.content || tab === "advanced" || tab === "gacha") {
    return;
  }
  const rows = state.content[tab];
  if (!Array.isArray(rows)) {
    return;
  }
  const selected = rows.find((row) => row.id === state.selected[tab]);
  if (selected) {
    sortStatsTree(selected);
  }
}

function sortStatsTree(owner) {
  if (!owner || typeof owner !== "object") {
    return;
  }
  sortStatsOwner(owner);
  for (const enemy of owner.enemies || []) {
    sortStatsTree(enemy);
  }
  for (const pattern of owner.patterns || []) {
    sortStatsTree(pattern);
  }
  for (const warning of owner.warnings || []) {
    if (warning?.pattern) {
      sortStatsTree(warning.pattern);
    }
    if (warning?.success_pattern) {
      sortStatsTree(warning.success_pattern);
    }
    for (const variant of warning.failure_variants || []) {
      sortStatsTree(variant.pattern);
    }
  }
  for (const effect of owner.hp_effects || []) {
    if (effect?.pattern) {
      sortStatsTree(effect.pattern);
    }
  }
  for (const tier of owner.tiers || []) {
    sortStatsTree(tier);
  }
}

function sortStatsOwner(owner) {
  if (!owner || typeof owner !== "object") {
    return;
  }
  sortStatsObject(owner, "stats");
  sortFixedStats(owner, "fixed_stats");
  sortStatEffects(owner, "stat_effects");
  sortStatEffects(owner, "player_stat_effects");
  sortStatEffects(owner, "enemy_stat_effects");
  sortStatEffects(owner, "boss_stat_effects");
}

function sortStatsObject(owner, key) {
  if (!owner || typeof owner !== "object") {
    return;
  }
  const stats = owner[key];
  if (!stats || typeof stats !== "object" || Array.isArray(stats)) {
    owner[key] = {};
    return;
  }
  owner[key] = Object.fromEntries(sortedStatEntries(stats));
}

function sortedStatEntries(stats) {
  const order = statOrderIndex();
  return Object.entries(stats || {}).sort(([left], [right]) => (
    (order.get(left) ?? Number.MAX_SAFE_INTEGER) - (order.get(right) ?? Number.MAX_SAFE_INTEGER)
    || String(left).localeCompare(String(right))
  ));
}

function sortFixedStats(owner, key, options = {}) {
  if (!owner || !Array.isArray(owner[key])) {
    return;
  }
  const statKeys = new Set(Object.keys(owner.stats || {}));
  const order = statOrderIndex();
  const fixed = Array.from(new Set(owner[key].map((stat) => String(stat)).filter((stat) => (
    !options.prune || statKeys.has(stat)
  ))));
  fixed.sort((left, right) => (
    (order.get(left) ?? Number.MAX_SAFE_INTEGER) - (order.get(right) ?? Number.MAX_SAFE_INTEGER)
    || String(left).localeCompare(String(right))
  ));
  if (fixed.length) {
    owner[key] = fixed;
  } else {
    delete owner[key];
  }
}

function renameObjectEntry(owner, oldKey, newKey, value) {
  if (!owner || typeof owner !== "object" || Array.isArray(owner)) {
    return false;
  }
  const from = String(oldKey ?? "");
  const to = String(newKey ?? "");
  if (!to) {
    return false;
  }
  if (from === to) {
    owner[to] = value;
    return true;
  }
  if (Object.prototype.hasOwnProperty.call(owner, to)) {
    return false;
  }
  const entries = Object.entries(owner);
  const nextEntries = entries.some(([key]) => key === from)
    ? entries.map(([key, currentValue]) => (key === from ? [to, value] : [key, currentValue]))
    : [...entries, [to, value]];
  for (const key of Object.keys(owner)) {
    delete owner[key];
  }
  for (const [key, currentValue] of nextEntries) {
    owner[key] = currentValue;
  }
  return true;
}

function sortStatEffects(owner, key) {
  if (!owner || !Array.isArray(owner[key])) {
    return;
  }
  const order = statOrderIndex();
  owner[key].sort((left, right) => (
    (order.get(statEffectKey(left)) ?? Number.MAX_SAFE_INTEGER) - (order.get(statEffectKey(right)) ?? Number.MAX_SAFE_INTEGER)
    || String(statEffectKey(left)).localeCompare(String(statEffectKey(right)))
  ));
}

function statEffectKey(effect) {
  return String(effect?.stat || effect?.key || "");
}

function normalizeStatEffectTarget(target) {
  if (target === "ally" || target === "party") {
    return "allies";
  }
  return target === "allies" ? "allies" : "self";
}

function statOrderIndex() {
  return new Map((state.content?.stats?.order || []).map((stat, index) => [stat, index]));
}

function statsEditor(owner, key, title, options = {}) {
  if (!owner[key] || typeof owner[key] !== "object" || Array.isArray(owner[key])) {
    owner[key] = {};
  }
  const stats = owner[key];
  const fixedStatsKey = options.fixedStatsKey || "";
  if (fixedStatsKey) {
    sortFixedStats(owner, fixedStatsKey);
  }
  const usedStats = new Set(Object.keys(stats));
  const rows = Object.entries(stats).map(([statKey, value]) => {
    const proxy = { stat_key: statKey, value };
    const statKeys = statOptions().filter(([optionKey]) => optionKey === statKey || !usedStats.has(optionKey));
    const fields = [
      selectField("스탯", proxy, "stat_key", statKeys, {
        rerender: true,
        onChange: (newKey, oldKey) => {
          if (newKey !== oldKey && Object.prototype.hasOwnProperty.call(stats, newKey)) {
            showToast(`${newKey} 스탯은 이미 추가되어 있습니다.`, true);
            return false;
          }
          const wasFixed = fixedStatsKey && isFixedStat(owner, fixedStatsKey, oldKey);
          const renamed = renameObjectEntry(stats, oldKey, newKey, Number(proxy.value || 0));
          if (renamed && fixedStatsKey) {
            removeFixedStat(owner, fixedStatsKey, oldKey);
            if (wasFixed) {
              setFixedStat(owner, fixedStatsKey, newKey, true);
            }
          }
          return renamed;
        },
      }),
      numberField("값", proxy, "value", {
        step: 0.001,
        onChange: (newValue) => {
          stats[proxy.stat_key] = newValue;
        },
      }),
    ];
    if (fixedStatsKey) {
      fields.push(fixedStatField(owner, fixedStatsKey, statKey));
    }
    fields.push(
      deleteButton(() => {
        delete stats[proxy.stat_key];
        if (fixedStatsKey) {
          removeFixedStat(owner, fixedStatsKey, proxy.stat_key);
        }
        markDirty();
        render();
      })
    );
    return el("div", { className: `row ${fixedStatsKey ? "three" : "two"}` }, fields);
  });
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, title),
      el("button", {
        type: "button",
        onclick: () => {
          const next = state.content.stats.order.find((id) => stats[id] == null) || state.content.stats.order[0] || "base_atk";
          stats[next] = 0;
          markDirty();
          render();
        },
      }, "스탯 추가"),
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "스탯 없음")]),
  ]);
}

function fixedStatField(owner, fixedStatsKey, statKey) {
  const input = el("input", {
    type: "checkbox",
    checked: isFixedStat(owner, fixedStatsKey, statKey),
    onchange: (event) => {
      setFixedStat(owner, fixedStatsKey, statKey, event.target.checked);
      markDirty();
    },
  });
  return fieldWrap("강화 불가", input);
}

function isFixedStat(owner, fixedStatsKey, statKey) {
  return Array.isArray(owner[fixedStatsKey]) && owner[fixedStatsKey].includes(String(statKey));
}

function setFixedStat(owner, fixedStatsKey, statKey, fixed) {
  const stat = String(statKey || "");
  if (!stat) {
    return;
  }
  const values = new Set(Array.isArray(owner[fixedStatsKey]) ? owner[fixedStatsKey].map((value) => String(value)) : []);
  if (fixed) {
    values.add(stat);
  } else {
    values.delete(stat);
  }
  owner[fixedStatsKey] = Array.from(values);
  sortFixedStats(owner, fixedStatsKey);
}

function removeFixedStat(owner, fixedStatsKey, statKey) {
  setFixedStat(owner, fixedStatsKey, statKey, false);
}

function statEffectsEditor(owner, key, title, defaultDuration = 1, fallbackUndispellable = false, options = {}) {
  owner[key] = Array.isArray(owner[key]) ? owner[key] : [];
  const rows = owner[key].map((effect, index) => {
    effect.stat ||= effect.key || defaultStatEffectKey();
    delete effect.key;
    effect.target = options.hideTarget ? "self" : normalizeStatEffectTarget(effect.target);
    effect.value = Number(effect.value || 0);
    effect.duration = options.forceDuration ?? effect.duration ?? defaultDuration;
    effect.undispellable = options.forceUndispellable ?? effect.undispellable ?? fallbackUndispellable;
    delete effect.heal_cap;
    const fields = [
      selectField("스탯", effect, "stat", statOptions()),
      ...(options.hideTarget ? [] : [selectField("대상", effect, "target", STAT_EFFECT_TARGETS)]),
      numberField("값", effect, "value", { step: 0.001 }),
      ...(options.forceDuration != null ? [] : [numberField("지속 턴", effect, "duration", { step: 1 })]),
      ...(options.forceUndispellable != null ? [] : [checkboxField("소거불가", effect, "undispellable")]),
      deleteButton(() => {
        owner[key].splice(index, 1);
        markDirty();
        render();
      }),
    ];
    return el("div", { className: "row" }, fields);
  });
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, title),
      el("button", {
        type: "button",
        onclick: () => {
          owner[key].push({
            stat: defaultStatEffectKey(),
            target: "self",
            value: 0,
            duration: options.forceDuration ?? defaultDuration,
            undispellable: options.forceUndispellable ?? fallbackUndispellable,
          });
          markDirty();
          render();
        },
      }, "스탯 효과 추가"),
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "스탯 효과 없음")]),
  ]);
}

function defaultStatEffectKey() {
  const order = state.content?.stats?.order || [];
  return order.includes("critical_rate") ? "critical_rate" : order[0] || "atk";
}

function migrateSkillStatEffects(skill, legacyDuration = 1) {
  migrateStatEffects(skill, "player_mods", "player_stat_effects", legacyDuration, Boolean(skill.player_undispellable || skill.undispellable));
  migrateStatEffects(skill, "enemy_mods", "enemy_stat_effects", legacyDuration, Boolean(skill.enemy_undispellable));
  const damageCut = Number(skill.damage_cut || 0);
  if (damageCut > 0 && !skill.player_stat_effects.some((effect) => effect.stat === "damage_cut")) {
    skill.player_stat_effects.push({
      stat: "damage_cut",
      target: "self",
      value: damageCut,
      duration: legacyDuration,
      undispellable: Boolean(skill.player_undispellable || skill.undispellable),
    });
  }
  skill.damage_cut = 0;
  delete skill.duration;
  delete skill.player_undispellable;
  delete skill.enemy_undispellable;
  delete skill.undispellable;
}

function migrateSkillSpecialEffects(skill, legacyDuration = 1, playerFallback = false, enemyFallback = false) {
  if (!skill.player_effects && skill.effects) {
    skill.player_effects = skill.effects;
  }
  delete skill.effects;
  if (skill.player_effects && typeof skill.player_effects === "object") {
    normalizeSpecialEffects(skill.player_effects, legacyDuration, playerFallback);
  }
  if (skill.enemy_effects && typeof skill.enemy_effects === "object") {
    normalizeSpecialEffects(skill.enemy_effects, legacyDuration, enemyFallback);
  }
}

function migratePatternStatEffects(pattern) {
  migrateStatEffects(pattern, "player_mods", "player_stat_effects", pattern.duration || 1, Boolean(pattern.player_undispellable));
  migrateStatEffects(pattern, "boss_mods", "boss_stat_effects", pattern.duration || 1, Boolean(pattern.boss_undispellable || pattern.undispellable));
}

function migrateStatEffects(owner, legacyKey, effectKey, defaultDuration, fallbackUndispellable = false) {
  if (!Array.isArray(owner[effectKey])) {
    const legacy = owner[legacyKey] && typeof owner[legacyKey] === "object" ? owner[legacyKey] : {};
    owner[effectKey] = Object.entries(legacy)
      .filter(([, value]) => Number(value || 0) !== 0)
      .map(([stat, value]) => ({
        stat,
        target: "self",
        value: Number(value || 0),
        duration: defaultDuration,
        undispellable: fallbackUndispellable,
      }));
  }
  owner[effectKey] = owner[effectKey]
    .filter((effect) => effect && typeof effect === "object")
    .map((effect) => {
      const normalized = {
        stat: effect.stat || effect.key || defaultStatEffectKey(),
        target: normalizeStatEffectTarget(effect.target),
        value: Number(effect.value || 0),
        duration: effect.duration ?? defaultDuration,
        undispellable: Boolean(effect.undispellable ?? fallbackUndispellable),
      };
      return normalized;
    });
  owner[legacyKey] = {};
}

function healCapFields(owner, labelPrefix = "힐 상한") {
  normalizeHealCap(owner);
  owner.heal_cap ||= { mode: "none", value: 0 };
  const fields = [
    selectField(`${labelPrefix} 방식`, owner.heal_cap, "mode", HEAL_CAP_MODES, {
      rerender: true,
      onChange: (mode) => {
        if (mode === "none") {
          owner.heal_cap.value = 0;
        } else if (!Number(owner.heal_cap.value || 0)) {
          owner.heal_cap.value = mode === "max_hp_ratio" ? 0.01 : 100;
        }
      },
    }),
  ];
  if (owner.heal_cap.mode !== "none") {
    fields.push(numberField(labelPrefix, owner.heal_cap, "value", { step: owner.heal_cap.mode === "max_hp_ratio" ? 0.001 : 1 }));
  }
  return fields;
}

function normalizeHealCap(owner) {
  if (!owner || typeof owner !== "object") {
    return;
  }
  const cap = owner.heal_cap && typeof owner.heal_cap === "object" ? owner.heal_cap : {};
  let mode = cap.mode || cap.type || cap.kind || owner.heal_cap_mode || owner.heal_cap_type || "none";
  let value = Number(cap.value ?? cap.amount ?? owner.heal_cap_value ?? 0);
  if (owner.heal_cap != null && typeof owner.heal_cap !== "object" && mode === "none") {
    mode = "flat";
    value = Number(owner.heal_cap || 0);
  }
  const aliases = {
    fixed: "flat",
    value: "flat",
    amount: "flat",
    max_hp: "max_hp_ratio",
    max_hp_percent: "max_hp_ratio",
    hp_percent: "max_hp_ratio",
    percent: "max_hp_ratio",
  };
  const rawMode = mode;
  mode = aliases[mode] || mode;
  if ((rawMode === "max_hp_percent" || rawMode === "hp_percent" || rawMode === "percent" || (mode === "max_hp_ratio" && value > 1)) && Number.isFinite(value)) {
    value /= 100;
  }
  delete owner.heal_cap_mode;
  delete owner.heal_cap_type;
  delete owner.heal_cap_value;
  if (!HEAL_CAP_MODES.some(([id]) => id === mode)) {
    mode = "none";
  }
  owner.heal_cap = {
    mode,
    value: Number.isFinite(value) && value > 0 ? value : 0,
  };
}

function specialEffectsEditor(owner, key, title, defaultDuration = 1, fallbackUndispellable = false, options = {}) {
  let effects = owner[key];
  if (!effects || typeof effects !== "object") {
    effects = {};
  }
  owner[key] = effects;
  normalizeSpecialEffects(effects, defaultDuration, fallbackUndispellable);
  if (options.hideTarget) {
    forceSelfSpecialEffectTargets(effects);
  }
  if (options.forceDuration != null || options.forceUndispellable != null) {
    forceSpecialEffectMeta(
      effects,
      options.forceDuration ?? defaultDuration,
      options.forceUndispellable ?? fallbackUndispellable,
    );
  }
  const targetField = (effect) => options.hideTarget ? [] : [selectField("대상", effect, "target", STAT_EFFECT_TARGETS)];
  const durationField = (effect) => options.forceDuration != null ? [] : [numberField("지속 턴", effect, "duration", { step: 1 })];
  const undispellableField = (effect) => options.forceUndispellable != null ? [] : [checkboxField("소거불가", effect, "undispellable")];
  const rows = [];

  if (effects.flurry) {
    rows.push(el("div", { className: "row" }, [
      ...targetField(effects.flurry),
      numberField("난격 수", effects.flurry, "count", { step: 1 }),
      ...durationField(effects.flurry),
      ...undispellableField(effects.flurry),
      deleteButton(() => {
        delete effects.flurry;
        pruneSpecialEffects(owner, key);
        markDirty();
        render();
      }),
    ]));
  }

  if (effects.double_strike) {
    rows.push(el("div", { className: "row five" }, [
      el("strong", {}, "재행동"),
      ...targetField(effects.double_strike),
      numberField("행동 횟수", effects.double_strike, "count", { step: 1 }),
      ...durationField(effects.double_strike),
      ...undispellableField(effects.double_strike),
      deleteButton(() => {
        delete effects.double_strike;
        pruneSpecialEffects(owner, key);
        markDirty();
        render();
      }),
    ]));
  }

  for (const [index, bonus] of (effects.bonus_damage || []).entries()) {
    rows.push(el("div", { className: "row" }, [
      ...targetField(bonus),
      numberField("추격 배율", bonus, "ratio", { step: 0.01 }),
      ...durationField(bonus),
      ...undispellableField(bonus),
      deleteButton(() => {
        effects.bonus_damage.splice(index, 1);
        pruneSpecialEffects(owner, key);
        markDirty();
        render();
      }),
    ]));
  }

  for (const [index, reinforce] of (effects.critical_reinforce || []).entries()) {
    rows.push(el("div", { className: "row" }, [
      ...targetField(reinforce),
      numberField("크리 리인포스", reinforce, "ratio", { step: 0.01 }),
      ...durationField(reinforce),
      ...undispellableField(reinforce),
      deleteButton(() => {
        effects.critical_reinforce.splice(index, 1);
        pruneSpecialEffects(owner, key);
        markDirty();
        render();
      }),
    ]));
  }

  for (const [index, finalDamage] of (effects.final_damage || []).entries()) {
    rows.push(el("div", { className: "row five" }, [
      el("strong", {}, finalDamage.ratio >= 0 ? "증가" : "감소"),
      ...targetField(finalDamage),
      numberField("최종 데미지 변화율", finalDamage, "ratio", { step: 0.01 }),
      ...durationField(finalDamage),
      ...undispellableField(finalDamage),
      deleteButton(() => {
        effects.final_damage.splice(index, 1);
        pruneSpecialEffects(owner, key);
        markDirty();
        render();
      }),
    ]));
  }

  for (const [index, postAttack] of (effects.post_attack_ability_damage || []).entries()) {
    rows.push(el("div", { className: "row five" }, [
      ...targetField(postAttack),
      numberField("공격 후 어빌 피해 배율", postAttack, "ratio", { step: 0.01 }),
      numberField("타수", postAttack, "count", { step: 1 }),
      ...durationField(postAttack),
      ...undispellableField(postAttack),
      deleteButton(() => {
        effects.post_attack_ability_damage.splice(index, 1);
        pruneSpecialEffects(owner, key);
        markDirty();
        render();
      }),
    ]));
  }

  for (const [index, recast] of (effects.ability_recast || []).entries()) {
    rows.push(el("div", { className: "row five" }, [
      el("strong", {}, "어빌리티 재발동"),
      ...targetField(recast),
      numberField("재발동 횟수", recast, "count", { step: 1 }),
      ...durationField(recast),
      ...undispellableField(recast),
      deleteButton(() => {
        effects.ability_recast.splice(index, 1);
        pruneSpecialEffects(owner, key);
        markDirty();
        render();
      }),
    ]));
  }

  for (const [index, guard] of (effects.dispel_guard || []).entries()) {
    rows.push(el("div", { className: "row six" }, [
      el("strong", {}, "디스펠 가드"),
      ...targetField(guard),
      ...(options.forceDuration != null ? [] : [
        selectField("방식", guard, "mode", GUARD_MODES, { rerender: true }),
        guard.mode === "count"
          ? numberField("방어 횟수", guard, "count", { step: 1 })
          : numberField("지속 턴", guard, "duration", { step: 1 }),
      ]),
      ...undispellableField(guard),
      deleteButton(() => {
        effects.dispel_guard.splice(index, 1);
        pruneSpecialEffects(owner, key);
        markDirty();
        render();
      }),
    ]));
  }

  for (const [index, veil] of (effects.veil || []).entries()) {
    rows.push(el("div", { className: "row six" }, [
      el("strong", {}, "마운트"),
      ...targetField(veil),
      ...(options.forceDuration != null ? [] : [
        selectField("방식", veil, "mode", GUARD_MODES, { rerender: true }),
        veil.mode === "count"
          ? numberField("방어 횟수", veil, "count", { step: 1 })
          : numberField("지속 턴", veil, "duration", { step: 1 }),
      ]),
      ...undispellableField(veil),
      deleteButton(() => {
        effects.veil.splice(index, 1);
        pruneSpecialEffects(owner, key);
        markDirty();
        render();
      }),
    ]));
  }

  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, title),
      el("div", { className: "actions" }, [
        !effects.flurry ? el("button", {
          type: "button",
          onclick: () => {
            owner[key] ||= {};
            owner[key].flurry = { count: 2, target: "self", duration: options.forceDuration ?? defaultDuration, undispellable: options.forceUndispellable ?? fallbackUndispellable };
            markDirty();
            render();
          },
        }, "난격 추가") : null,
        !effects.double_strike ? el("button", {
          type: "button",
          onclick: () => {
            owner[key] ||= {};
            owner[key].double_strike = { count: 2, target: "self", duration: options.forceDuration ?? defaultDuration, undispellable: options.forceUndispellable ?? fallbackUndispellable };
            markDirty();
            render();
          },
        }, "재행동 추가") : null,
        el("button", {
          type: "button",
          onclick: () => {
            owner[key] ||= {};
            owner[key].bonus_damage ||= [];
            owner[key].bonus_damage.push({ ratio: 0.35, target: "self", duration: options.forceDuration ?? defaultDuration, undispellable: options.forceUndispellable ?? fallbackUndispellable });
            markDirty();
            render();
          },
        }, "추격 추가"),
        el("button", {
          type: "button",
          onclick: () => {
            owner[key] ||= {};
            owner[key].critical_reinforce ||= [];
            owner[key].critical_reinforce.push({ ratio: 0.5, target: "self", duration: options.forceDuration ?? defaultDuration, undispellable: options.forceUndispellable ?? fallbackUndispellable });
            markDirty();
            render();
          },
        }, "크리 리인포스 추가"),
        el("button", {
          type: "button",
          onclick: () => {
            owner[key] ||= {};
            owner[key].final_damage ||= [];
            owner[key].final_damage.push({ ratio: 0.05, target: "self", duration: options.forceDuration ?? defaultDuration, undispellable: options.forceUndispellable ?? fallbackUndispellable });
            markDirty();
            render();
          },
        }, "최종 데미지 추가"),
        el("button", {
          type: "button",
          onclick: () => {
            owner[key] ||= {};
            owner[key].post_attack_ability_damage ||= [];
            owner[key].post_attack_ability_damage.push({
              ratio: 1,
              count: 1,
              target: "self",
              duration: options.forceDuration ?? defaultDuration,
              undispellable: options.forceUndispellable ?? fallbackUndispellable,
            });
            markDirty();
            render();
          },
        }, "공격 후 어빌 피해 추가"),
        el("button", {
          type: "button",
          onclick: () => {
            owner[key] ||= {};
            owner[key].ability_recast ||= [];
            owner[key].ability_recast.push({
              count: 1,
              target: "self",
              duration: options.forceDuration ?? defaultDuration,
              undispellable: options.forceUndispellable ?? fallbackUndispellable,
            });
            markDirty();
            render();
          },
        }, "어빌리티 재발동 추가"),
        el("button", {
          type: "button",
          onclick: () => {
            owner[key] ||= {};
            owner[key].dispel_guard ||= [];
            owner[key].dispel_guard.push({ mode: "duration", target: "self", duration: options.forceDuration ?? defaultDuration, count: 0, undispellable: options.forceUndispellable ?? fallbackUndispellable });
            markDirty();
            render();
          },
        }, "디스펠 가드 추가"),
        el("button", {
          type: "button",
          onclick: () => {
            owner[key] ||= {};
            owner[key].veil ||= [];
            owner[key].veil.push({ mode: "duration", target: "self", duration: options.forceDuration ?? defaultDuration, count: 0, undispellable: options.forceUndispellable ?? fallbackUndispellable });
            markDirty();
            render();
          },
        }, "마운트 추가"),
      ].filter(Boolean)),
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "특수 효과 없음")]),
  ]);
}

function normalizeSpecialEffects(effects, defaultDuration, fallbackUndispellable = false) {
  if (effects.flurry && typeof effects.flurry !== "object") {
    effects.flurry = { count: Number(effects.flurry) || 2, target: "self", duration: defaultDuration, undispellable: fallbackUndispellable };
  }
  if (effects.flurry) {
    effects.flurry.count = Math.max(1, Number(effects.flurry.count || 2));
    effects.flurry.target = normalizeStatEffectTarget(effects.flurry.target);
    effects.flurry.duration ??= defaultDuration;
    effects.flurry.undispellable ??= fallbackUndispellable;
  }
  if (effects.double_strike && typeof effects.double_strike !== "object") {
    effects.double_strike = { count: 2, target: "self", duration: defaultDuration, undispellable: fallbackUndispellable };
  }
  if (effects.double_strike) {
    const actionCount = Number(effects.double_strike.count || effects.double_strike.actions || 2);
    effects.double_strike.count = Number.isFinite(actionCount) ? Math.floor(Math.max(2, actionCount)) : 2;
    effects.double_strike.target = normalizeStatEffectTarget(effects.double_strike.target);
    effects.double_strike.duration ??= defaultDuration;
    effects.double_strike.undispellable ??= fallbackUndispellable;
  }
  if (effects.bonus_damage && !Array.isArray(effects.bonus_damage)) {
    effects.bonus_damage = [typeof effects.bonus_damage === "object"
      ? effects.bonus_damage
      : { ratio: Number(effects.bonus_damage) || 0, duration: defaultDuration, undispellable: fallbackUndispellable }];
  }
  effects.bonus_damage ||= [];
  effects.bonus_damage = effects.bonus_damage.filter((bonus) => bonus && typeof bonus === "object");
  for (const bonus of effects.bonus_damage) {
    if (bonus.percent != null && bonus.ratio == null) {
      bonus.ratio = Number(bonus.percent || 0) / 100;
      delete bonus.percent;
    }
    bonus.ratio = Math.max(0, Number(bonus.ratio || 0));
    bonus.target = normalizeStatEffectTarget(bonus.target);
    bonus.duration ??= defaultDuration;
    bonus.undispellable ??= fallbackUndispellable;
  }
  if (!effects.bonus_damage.length) {
    delete effects.bonus_damage;
  }
  if (effects.critical_reinforce && !Array.isArray(effects.critical_reinforce)) {
    effects.critical_reinforce = [typeof effects.critical_reinforce === "object"
      ? effects.critical_reinforce
      : { ratio: Number(effects.critical_reinforce) || 0, duration: defaultDuration, undispellable: fallbackUndispellable }];
  }
  effects.critical_reinforce ||= [];
  effects.critical_reinforce = effects.critical_reinforce.filter((reinforce) => reinforce && typeof reinforce === "object");
  for (const reinforce of effects.critical_reinforce) {
    if (reinforce.percent != null && reinforce.ratio == null) {
      reinforce.ratio = Number(reinforce.percent || 0) / 100;
      delete reinforce.percent;
    }
    reinforce.ratio = Math.max(0, Number(reinforce.ratio || 0));
    reinforce.target = normalizeStatEffectTarget(reinforce.target);
    reinforce.duration ??= defaultDuration;
    reinforce.undispellable ??= fallbackUndispellable;
  }
  if (!effects.critical_reinforce.length) {
    delete effects.critical_reinforce;
  }
  if (effects.final_damage && !Array.isArray(effects.final_damage)) {
    effects.final_damage = [typeof effects.final_damage === "object"
      ? effects.final_damage
      : { ratio: Number(effects.final_damage) || 0, duration: defaultDuration, undispellable: fallbackUndispellable }];
  }
  effects.final_damage ||= [];
  effects.final_damage = effects.final_damage.filter((finalDamage) => finalDamage && typeof finalDamage === "object");
  for (const finalDamage of effects.final_damage) {
    if (finalDamage.percent != null && finalDamage.ratio == null) {
      finalDamage.ratio = Number(finalDamage.percent || 0) / 100;
      delete finalDamage.percent;
    }
    finalDamage.ratio = Number(finalDamage.ratio || 0);
    finalDamage.target = normalizeStatEffectTarget(finalDamage.target);
    finalDamage.duration ??= defaultDuration;
    finalDamage.undispellable ??= fallbackUndispellable;
  }
  effects.final_damage = effects.final_damage.filter((finalDamage) => finalDamage.ratio !== 0 && finalDamage.ratio > -1);
  if (!effects.final_damage.length) {
    delete effects.final_damage;
  }
  if (effects.post_attack_ability_damage && !Array.isArray(effects.post_attack_ability_damage)) {
    effects.post_attack_ability_damage = [typeof effects.post_attack_ability_damage === "object"
      ? effects.post_attack_ability_damage
      : { ratio: Number(effects.post_attack_ability_damage) || 0, count: 1, duration: defaultDuration, undispellable: fallbackUndispellable }];
  }
  effects.post_attack_ability_damage ||= [];
  effects.post_attack_ability_damage = effects.post_attack_ability_damage.filter((postAttack) => postAttack && typeof postAttack === "object");
  for (const postAttack of effects.post_attack_ability_damage) {
    if (postAttack.percent != null && postAttack.ratio == null) {
      postAttack.ratio = Number(postAttack.percent || 0) / 100;
      delete postAttack.percent;
    }
    if (postAttack.hits != null && postAttack.count == null) {
      postAttack.count = Number(postAttack.hits || 1);
      delete postAttack.hits;
    }
    postAttack.ratio = Math.max(0, Number(postAttack.ratio || 0));
    postAttack.count = Math.max(1, Number(postAttack.count || 1));
    postAttack.target = normalizeStatEffectTarget(postAttack.target);
    postAttack.duration ??= defaultDuration;
    postAttack.undispellable ??= fallbackUndispellable;
  }
  if (!effects.post_attack_ability_damage.length) {
    delete effects.post_attack_ability_damage;
  }
  if (effects.ability_recast && !Array.isArray(effects.ability_recast)) {
    effects.ability_recast = [typeof effects.ability_recast === "object"
      ? effects.ability_recast
      : { count: Number(effects.ability_recast) || 1, duration: defaultDuration, undispellable: fallbackUndispellable }];
  }
  effects.ability_recast ||= [];
  effects.ability_recast = effects.ability_recast.filter((recast) => recast && typeof recast === "object");
  for (const recast of effects.ability_recast) {
    const count = Number(recast.count ?? recast.recasts ?? recast.times ?? 1);
    recast.count = Number.isFinite(count) ? Math.floor(Math.max(1, count)) : 1;
    delete recast.recasts;
    delete recast.times;
    recast.target = normalizeStatEffectTarget(recast.target);
    recast.duration ??= defaultDuration;
    recast.undispellable ??= fallbackUndispellable;
  }
  if (!effects.ability_recast.length) {
    delete effects.ability_recast;
  }
  normalizeGuardEffects(effects, "dispel_guard", defaultDuration, fallbackUndispellable);
  normalizeGuardEffects(effects, "veil", defaultDuration, fallbackUndispellable);
  if (effects.mount) {
    normalizeGuardEffects(effects, "mount", defaultDuration, fallbackUndispellable);
    effects.veil ||= [];
    effects.veil.push(...(effects.mount || []));
    delete effects.mount;
  }
}

function normalizeGuardEffects(effects, key, defaultDuration, fallbackUndispellable = false) {
  if (effects[key] && !Array.isArray(effects[key])) {
    effects[key] = [typeof effects[key] === "object" ? effects[key] : {}];
  }
  effects[key] ||= [];
  effects[key] = effects[key].filter((guard) => guard && typeof guard === "object");
  for (const guard of effects[key]) {
    guard.target = normalizeStatEffectTarget(guard.target);
    guard.mode = guard.mode === "count" || Number(guard.count || 0) > 0 ? "count" : "duration";
    if (guard.mode === "count") {
      guard.count = Math.max(1, Number(guard.count || 1));
      guard.duration = Number.isFinite(Number(guard.duration)) ? Number(guard.duration) : -1;
    } else {
      guard.count = 0;
      guard.duration ??= defaultDuration;
    }
    guard.undispellable ??= fallbackUndispellable;
  }
  if (!effects[key].length) {
    delete effects[key];
  }
}

function pruneSpecialEffects(owner, key) {
  const effects = owner[key];
  if (!effects || typeof effects !== "object") {
    delete owner[key];
    return;
  }
  const hasBonus = Array.isArray(effects.bonus_damage) && effects.bonus_damage.length > 0;
  const hasReinforce = Array.isArray(effects.critical_reinforce) && effects.critical_reinforce.length > 0;
  const hasFinalDamage = Array.isArray(effects.final_damage) && effects.final_damage.length > 0;
  const hasPostAttack = Array.isArray(effects.post_attack_ability_damage) && effects.post_attack_ability_damage.length > 0;
  const hasAbilityRecast = Array.isArray(effects.ability_recast) && effects.ability_recast.length > 0;
  const hasDispelGuard = Array.isArray(effects.dispel_guard) && effects.dispel_guard.length > 0;
  const hasVeil = Array.isArray(effects.veil) && effects.veil.length > 0;
  if (!effects.flurry && !effects.double_strike && !hasBonus && !hasReinforce && !hasFinalDamage && !hasPostAttack && !hasAbilityRecast && !hasDispelGuard && !hasVeil) {
    delete owner[key];
  }
}

function effectActionEditor(owner, key, title, config = {}) {
  owner[key] ||= [];
  const actions = owner[key];
  const conditionTargets = config.conditionTargets || ACTION_STACK_CONDITION_TARGETS;
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      actions.push({ action: "dispel", target: "enemy", count: 1 });
      markDirty();
      render();
    },
  }, "효과 추가");
  const rows = actions.map((action, index) => {
    normalizeEffectActionForUi(action, conditionTargets);
    action.action ||= "dispel";
    action.target ||= defaultEffectActionTarget(action.action);
    const isStackAction = isStackEffectAction(action.action);
    if (isStackAction) {
      action.stack_effect_id ||= state.content.stack_effects?.[0]?.id || "";
      action.value = Math.max(1, Number(action.value || action.stacks || action.count || 1));
      action.value_from_stack_effect_id ||= action.value_from_stack || action.source_stack_effect_id || "";
      if (action.value_from_stack_effect_id) {
        action.value_from_target ||= action.source_target || action.target || "self";
      } else {
        delete action.value_from_stack_effect_id;
        delete action.value_from_target;
      }
      delete action.value_from_stack;
      delete action.source_stack_effect_id;
      delete action.source_target;
      delete action.stacks;
    }
    const fields = [
      selectField("효과", action, "action", EFFECT_ACTIONS, {
        rerender: true,
        onChange: (nextAction, previousAction) => {
          if (isStackEffectAction(nextAction) && !isStackEffectAction(previousAction)) {
            action.target = "self";
          } else if (!isStackEffectAction(nextAction) && isStackEffectAction(previousAction)) {
            action.target = "enemy";
          }
        },
      }),
      selectField("대상", action, "target", EFFECT_TARGETS),
    ];
    if (isStackAction) {
      fields.push(selectField("스택 효과", action, "stack_effect_id", stackEffectOptions()));
      if (!["stack_remove", "stack_max"].includes(action.action)) {
        fields.push(
          numberField("스택 수", action, "value", { step: 1 }),
          selectField("수량 참조 스택", action, "value_from_stack_effect_id", [["", "고정값"], ...stackEffectOptions()], {
            rerender: true,
          }),
        );
        if (action.value_from_stack_effect_id) {
          fields.push(selectField("참조 대상", action, "value_from_target", ACTION_STACK_CONDITION_TARGETS));
        }
      }
    } else {
      fields.push(numberField("횟수", action, "count", { step: 1 }));
    }
    fields.push(deleteButton(() => {
      actions.splice(index, 1);
      markDirty();
      render();
    }));
    const rowClass = fields.length >= 8
      ? "seven"
      : fields.length >= 7
        ? "six"
        : fields.length >= 6
          ? "five"
          : fields.length >= 4
            ? "three"
            : "two";
    return el("div", { className: "subpanel" }, [
      el("div", { className: `row ${rowClass}` }, fields),
      effectActionStackConditionsEditor(action, conditionTargets),
    ]);
  });
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, title),
      addButton,
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "즉시 효과 없음")]),
  ]);
}

function isStackEffectAction(action) {
  return String(action || "").startsWith("stack_");
}

function defaultEffectActionTarget(action) {
  return isStackEffectAction(action) ? "self" : "enemy";
}

function normalizeEffectActionForUi(action, targetOptions = ACTION_STACK_CONDITION_TARGETS) {
  action.conditions = Array.isArray(action.conditions)
    ? action.conditions
      .filter((condition) => condition && typeof condition === "object")
      .map((condition) => normalizeEffectActionStackCondition(condition, targetOptions))
      .filter((condition) => condition.stack_effect_id)
    : [];
}

function normalizeEffectActionStackCondition(condition, targetOptions = ACTION_STACK_CONDITION_TARGETS) {
  const targetIds = new Set(targetOptions.map(([id]) => id));
  let target = condition.target || targetOptions[0]?.[0] || "self";
  if (!targetIds.has(target)) {
    target = targetOptions[0]?.[0] || "self";
  }
  const minStacks = Number(condition.min_stacks ?? condition.min ?? condition.stacks ?? 1);
  const maxStacks = Number(condition.max_stacks ?? condition.max ?? -1);
  return {
    stack_effect_id: condition.stack_effect_id || condition.effect_id || condition.id || state.content.stack_effects?.[0]?.id || "",
    target,
    min_stacks: Math.max(0, Number.isFinite(minStacks) ? minStacks : 1),
    max_stacks: Number.isFinite(maxStacks) ? maxStacks : -1,
  };
}

function effectActionStackConditionsEditor(action, targetOptions = ACTION_STACK_CONDITION_TARGETS) {
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      action.conditions ||= [];
      action.conditions.push({
        stack_effect_id: state.content.stack_effects?.[0]?.id || "",
        target: targetOptions[0]?.[0] || "self",
        min_stacks: 1,
        max_stacks: -1,
      });
      markDirty();
      render();
    },
  }, "스택 조건 추가");
  const rows = (action.conditions || []).map((condition, index) => el("div", { className: "row five" }, [
    selectField("스택", condition, "stack_effect_id", stackEffectOptions()),
    selectField("대상", condition, "target", targetOptions),
    numberField("최소 스택", condition, "min_stacks", { step: 1 }),
    numberField("최대 스택 (-1=없음)", condition, "max_stacks", { step: 1 }),
    deleteButton(() => {
      action.conditions.splice(index, 1);
      markDirty();
      render();
    }),
  ]));
  return el("section", { className: "section nested-section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "실행 스택 조건"),
      addButton,
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "조건 없음")]),
  ]);
}

function skillJobOwnerPicker(skill) {
  const jobIds = normalizedSkillJobIds(skill.job_ids || []);
  const jobOptions = jobTreeOptions();
  const updateJobIds = (nextIds) => {
    skill.job_ids = normalizedSkillJobIds(nextIds);
    markDirty();
    render();
  };
  const rows = jobIds.map((jobId, index) => {
    const proxy = { job_id: jobId };
    return el("div", { className: "row two" }, [
      selectField("기준 직업", proxy, "job_id", [["", "공용 스킬"], ...jobOptions], {
        onChange: (nextJobId) => {
          if (!nextJobId) {
            updateJobIds([]);
            return;
          }
          const nextIds = [...jobIds];
          nextIds[index] = nextJobId;
          updateJobIds(nextIds);
        },
      }),
      deleteButton(() => {
        const nextIds = jobIds.filter((_, rowIndex) => rowIndex !== index);
        updateJobIds(nextIds);
      }),
    ]);
  });
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      const nextJobId = jobOptions.find(([jobId]) => !jobIds.includes(jobId))?.[0];
      if (!nextJobId) {
        showToast("추가할 직업이 없습니다.", true);
        return;
      }
      updateJobIds([...jobIds, nextJobId]);
    },
  }, "기준 직업 추가");
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "사용 가능 직업"),
      addButton,
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "공용 스킬")]),
  ]);
}

function idField(entityKey, obj) {
  const input = el("input", {
    type: "text",
    value: obj.id ?? "",
    oninput: (event) => {
      normalizeInputValue(event, normalizeIdValue);
    },
    onpaste: (event) => {
      normalizePastedInput(event, normalizeIdValue);
    },
    onchange: (event) => {
      const oldId = String(obj.id ?? "");
      const newId = normalizeIdValue(event.target.value).trim();
      event.target.value = newId;
      if (oldId === newId) {
        return;
      }
      if (!isValidIdChange(entityKey, obj, oldId, newId)) {
        event.target.value = oldId;
        return;
      }
      obj.id = newId;
      state.selected[entityKey] = newId;
      const changed = renameContentReferences(entityKey, oldId, newId);
      markDirty();
      if (changed > 0) {
        setStatus(`ID 변경: ${oldId} -> ${newId} · 참조 ${changed}개 자동 변경`);
      }
      render();
    },
  });
  return fieldWrap("ID", input);
}

function nestedIdField(label, obj, rows, onRename) {
  const input = el("input", {
    type: "text",
    value: obj.id ?? "",
    oninput: (event) => {
      normalizeInputValue(event, normalizeIdValue);
    },
    onpaste: (event) => {
      normalizePastedInput(event, normalizeIdValue);
    },
    onchange: (event) => {
      const oldId = String(obj.id ?? "");
      const newId = normalizeIdValue(event.target.value).trim();
      event.target.value = newId;
      if (oldId === newId) {
        return;
      }
      if (!newId || !ID_PATTERN.test(newId)) {
        showToast("ID는 영문, 숫자, 밑줄, 하이픈만 사용할 수 있습니다.", true);
        event.target.value = oldId;
        return;
      }
      const duplicate = (rows || []).some((row) => row !== obj && row.id === newId);
      if (duplicate) {
        showToast(`${newId} ID가 이미 존재합니다.`, true);
        event.target.value = oldId;
        return;
      }
      obj.id = newId;
      onRename?.(oldId, newId);
      markDirty();
      render();
    },
  });
  return fieldWrap(label, input);
}

function isValidIdChange(entityKey, obj, oldId, newId) {
  if (!newId || !ID_PATTERN.test(newId)) {
    showToast("ID는 영문, 숫자, 밑줄, 하이픈만 사용할 수 있습니다.", true);
    return false;
  }
  const duplicate = (state.content[entityKey] || []).some((row) => row !== obj && row.id === newId);
  if (duplicate) {
    showToast(`${newId} ID가 이미 존재합니다.`, true);
    return false;
  }
  return oldId !== newId;
}

function renameContentReferences(entityKey, oldId, newId) {
  if (!oldId || !newId || oldId === newId || !state.content) {
    return 0;
  }
  if (entityKey === "items") {
    return renameItemReferences(oldId, newId);
  }
  if (entityKey === "materials") {
    return renameMaterialReferences(oldId, newId);
  }
  if (entityKey === "jobs") {
    return renameJobReferences(oldId, newId);
  }
  return 0;
}

function deleteContentReferences(entityKey, removedId) {
  if (!removedId || !state.content) {
    return 0;
  }
  if (entityKey === "items") {
    return deleteItemReferences(removedId);
  }
  if (entityKey === "materials") {
    return deleteMaterialReferences(removedId);
  }
  if (entityKey === "jobs") {
    return deleteJobReferences(removedId);
  }
  return 0;
}

function deleteItemReferences(removedId) {
  let changed = 0;
  const recipes = state.content.crafting_recipes || [];
  const keptRecipes = recipes.filter((recipe) => {
    if (recipe.result_item_id !== removedId) {
      return true;
    }
    changed += 1;
    return false;
  });
  if (keptRecipes.length !== recipes.length) {
    state.content.crafting_recipes = keptRecipes;
    if (state.selected.crafting_recipes && !keptRecipes.some((recipe) => recipe.id === state.selected.crafting_recipes)) {
      state.selected.crafting_recipes = keptRecipes[0]?.id;
    }
  }
  for (const reward of allRewards()) {
    const before = reward.items?.length || 0;
    reward.items = (reward.items || []).filter((drop) => (
      drop.template_id !== removedId && drop.item_id !== removedId
    ));
    changed += before - reward.items.length;
  }
  for (const pool of state.content.gacha?.pools || []) {
    for (const entry of pool.entries || []) {
      const before = entry.item_ids?.length || 0;
      entry.item_ids = (entry.item_ids || []).filter((target) => normalizeGachaTarget(target).id !== removedId);
      changed += before - entry.item_ids.length;
    }
  }
  for (const festival of state.content.gacha?.festivals || []) {
    const before = festival.overrides?.length || 0;
    festival.overrides = (festival.overrides || []).filter((override) => (
      override.type !== "item" || override.target_id !== removedId
    ));
    changed += before - festival.overrides.length;
  }
  return changed;
}

function deleteMaterialReferences(removedId) {
  let changed = 0;
  for (const recipe of state.content.crafting_recipes || []) {
    recipe.materials ||= {};
    if (Object.prototype.hasOwnProperty.call(recipe.materials, removedId)) {
      delete recipe.materials[removedId];
      changed += 1;
    }
  }
  for (const reward of allRewards()) {
    const before = reward.materials?.length || 0;
    reward.materials = (reward.materials || []).filter((drop) => drop.id !== removedId);
    changed += before - reward.materials.length;
  }
  for (const pool of state.content.gacha?.pools || []) {
    for (const entry of pool.entries || []) {
      const before = entry.material_ids?.length || 0;
      entry.material_ids = (entry.material_ids || []).filter((target) => normalizeGachaTarget(target).id !== removedId);
      changed += before - entry.material_ids.length;
    }
  }
  for (const festival of state.content.gacha?.festivals || []) {
    const before = festival.overrides?.length || 0;
    festival.overrides = (festival.overrides || []).filter((override) => (
      override.type !== "material" || override.target_id !== removedId
    ));
    changed += before - festival.overrides.length;
  }
  return changed;
}

function deleteJobReferences(removedId) {
  let changed = 0;
  for (const job of state.content.jobs || []) {
    if (job.parent_id === removedId) {
      job.parent_id = "";
      changed += 1;
    }
  }
  for (const skill of state.content.skills || []) {
    if (!Array.isArray(skill.job_ids)) {
      continue;
    }
    const before = skill.job_ids.length;
    skill.job_ids = skill.job_ids.filter((jobId) => jobId !== removedId);
    changed += before - skill.job_ids.length;
  }
  if (state.content.player?.start?.job_id === removedId) {
    state.content.player.start.job_id = "novice";
    changed += 1;
  }
  return changed;
}

function renameItemReferences(oldId, newId) {
  let changed = 0;
  for (const recipe of state.content.crafting_recipes || []) {
    if (recipe.result_item_id === oldId) {
      recipe.result_item_id = newId;
      changed += 1;
    }
  }
  for (const reward of allRewards()) {
    for (const drop of reward.items || []) {
      if (drop.template_id === oldId) {
        drop.template_id = newId;
        changed += 1;
      }
      if (drop.item_id === oldId) {
        drop.item_id = newId;
        changed += 1;
      }
    }
  }
  for (const pool of state.content.gacha?.pools || []) {
    for (const entry of pool.entries || []) {
      entry.item_ids = (entry.item_ids || []).map((target) => normalizeGachaTarget(target));
      for (const target of entry.item_ids || []) {
        if (target.id === oldId) {
          target.id = newId;
          changed += 1;
        }
      }
    }
  }
  for (const festival of state.content.gacha?.festivals || []) {
    for (const override of festival.overrides || []) {
      if (override.type === "item" && override.target_id === oldId) {
        override.target_id = newId;
        changed += 1;
      }
    }
  }
  return changed;
}

function renameMaterialReferences(oldId, newId) {
  let changed = 0;
  for (const recipe of state.content.crafting_recipes || []) {
    recipe.materials ||= {};
    if (Object.prototype.hasOwnProperty.call(recipe.materials, oldId)) {
      const oldAmount = Number(recipe.materials[oldId] || 0);
      const newAmount = Number(recipe.materials[newId] || 0);
      delete recipe.materials[oldId];
      recipe.materials[newId] = oldAmount + newAmount;
      changed += 1;
    }
  }
  for (const reward of allRewards()) {
    for (const drop of reward.materials || []) {
      if (drop.id === oldId) {
        drop.id = newId;
        changed += 1;
      }
    }
  }
  for (const method of state.content.enhancement?.methods || []) {
    if (method.materials && Object.prototype.hasOwnProperty.call(method.materials, oldId)) {
      const oldAmount = Number(method.materials[oldId] || 0);
      const newAmount = Number(method.materials[newId] || 0);
      delete method.materials[oldId];
      method.materials[newId] = oldAmount + newAmount;
      changed += 1;
    }
  }
  for (const pool of state.content.gacha?.pools || []) {
    for (const entry of pool.entries || []) {
      entry.material_ids = (entry.material_ids || []).map((target) => normalizeGachaTarget(target));
      for (const target of entry.material_ids || []) {
        if (target.id === oldId) {
          target.id = newId;
          changed += 1;
        }
      }
    }
  }
  for (const festival of state.content.gacha?.festivals || []) {
    for (const override of festival.overrides || []) {
      if (override.type === "material" && override.target_id === oldId) {
        override.target_id = newId;
        changed += 1;
      }
    }
  }
  return changed;
}

function renameJobReferences(oldId, newId) {
  let changed = 0;
  for (const job of state.content.jobs || []) {
    if (job.parent_id === oldId) {
      job.parent_id = newId;
      changed += 1;
    }
  }
  for (const skill of state.content.skills || []) {
    if (!Array.isArray(skill.job_ids)) {
      continue;
    }
    const before = skill.job_ids.join("\u0000");
    skill.job_ids = [...new Set(skill.job_ids.map((jobId) => jobId === oldId ? newId : jobId))];
    if (skill.job_ids.join("\u0000") !== before) {
      changed += 1;
    }
  }
  if (state.content.player?.start?.job_id === oldId) {
    state.content.player.start.job_id = newId;
    changed += 1;
  }
  return changed;
}

function renameBossWarningReferences(boss, oldId, newId) {
  for (const warning of boss.hp_warnings || []) {
    if (warning.warning_id === oldId) {
      warning.warning_id = newId;
    }
  }
  for (const warning of boss.ct?.warnings_by_hp || []) {
    if (warning.warning_id === oldId) {
      warning.warning_id = newId;
    }
    if (Array.isArray(warning.warning_ids)) {
      warning.warning_ids = warning.warning_ids.map((warningId) => warningId === oldId ? newId : warningId);
    }
  }
  for (const warning of boss.warnings || []) {
    if (warning.success_warning_id === oldId) {
      warning.success_warning_id = newId;
    }
    if (warning.failure_warning_id === oldId) {
      warning.failure_warning_id = newId;
    }
  }
}

function deleteBossWarningReferences(boss, removedId) {
  const filter = (warning) => warning.warning_id !== removedId;
  boss.hp_warnings = (boss.hp_warnings || []).filter(filter);
  if (boss.ct?.warnings_by_hp) {
    boss.ct.warnings_by_hp = boss.ct.warnings_by_hp
      .map((warning) => {
        if (Array.isArray(warning.warning_ids)) {
          warning.warning_ids = warning.warning_ids.filter((warningId) => warningId !== removedId);
          warning.warning_id = warning.warning_ids[0] || "";
        }
        return warning;
      })
      .filter((warning) => warning.warning_id !== removedId && (!Array.isArray(warning.warning_ids) || warning.warning_ids.length));
  }
  for (const warning of boss.warnings || []) {
    if (warning.success_warning_id === removedId) {
      delete warning.success_warning_id;
    }
    if (warning.failure_warning_id === removedId) {
      delete warning.failure_warning_id;
    }
  }
}

function allRewards() {
  const rewards = [];
  for (const dungeon of state.content.dungeons || []) {
    for (const enemy of dungeon.enemies || []) {
      if (enemy.rewards) {
        rewards.push(enemy.rewards);
      }
    }
  }
  for (const boss of state.content.bosses || []) {
    if (boss.rewards) {
      rewards.push(boss.rewards);
    }
  }
  return rewards;
}

function textField(label, obj, key, options = {}) {
  const input = el("input", {
    type: "text",
    value: obj[key] ?? "",
    onpaste: options.normalize ? (event) => {
      normalizePastedInput(event, options.normalize);
    } : null,
    oninput: (event) => {
      obj[key] = options.normalize
        ? normalizeInputValue(event, options.normalize)
        : event.target.value;
      markDirty();
      options.onChange?.(obj[key]);
    },
  });
  return fieldWrap(label, input, options.full);
}

function textAreaField(label, obj, key, options = {}) {
  const input = el("textarea", {
    oninput: (event) => {
      obj[key] = event.target.value;
      markDirty();
      options.onChange?.(obj[key]);
    },
  }, obj[key] ?? "");
  return fieldWrap(label, input, options.full);
}

function numberField(label, obj, key, options = {}) {
  const input = el("input", {
    type: "number",
    step: options.step ?? 1,
    value: obj[key] ?? 0,
    oninput: (event) => {
      const value = event.target.value === "" ? 0 : Number(event.target.value);
      obj[key] = Number.isFinite(value) ? value : 0;
      markDirty();
      options.onChange?.(obj[key]);
    },
  });
  return fieldWrap(label, input, options.full);
}

function optionalNumberField(label, obj, key, options = {}) {
  const input = el("input", {
    type: "number",
    step: options.step ?? 1,
    value: obj[key] ?? "",
    placeholder: options.placeholder ?? "기본값",
    oninput: (event) => {
      if (event.target.value === "") {
        delete obj[key];
      } else {
        const value = Number(event.target.value);
        obj[key] = Number.isFinite(value) ? value : 0;
      }
      markDirty();
      options.onChange?.(obj[key]);
    },
  });
  return fieldWrap(label, input, options.full);
}

function checkboxField(label, obj, key) {
  const input = el("input", {
    type: "checkbox",
    checked: Boolean(obj[key]),
    onchange: (event) => {
      obj[key] = event.target.checked;
      markDirty();
    },
  });
  return fieldWrap(label, input);
}

function selectField(label, obj, key, options, config = {}) {
  const value = obj[key] ?? "";
  const select = el("select", {
    value,
    "data-control-id": config.controlId || "",
    onchange: (event) => {
      const previousValue = obj[key] ?? "";
      const nextValue = event.target.value;
      obj[key] = nextValue;
      const accepted = config.onChange?.(nextValue, previousValue, event);
      if (accepted === false) {
        obj[key] = previousValue;
        event.target.value = previousValue;
        return;
      }
      markDirty();
      if (config.rerender) {
        render();
      }
    },
  }, optionsWithCurrent(options, value).map(([optionValue, optionLabel]) => el("option", {
    value: optionValue,
    selected: String(optionValue) === String(value),
  }, optionLabel)));
  return fieldWrap(label, select, config.full);
}

function fieldWrap(label, input, full = false) {
  return el("div", { className: `field ${full ? "full" : ""}` }, [
    el("label", {}, label),
    input,
  ]);
}

function deleteButton(onclick) {
  return el("button", {
    type: "button",
    className: "danger",
    onclick,
  }, "삭제");
}

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) {
      continue;
    }
    if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2), value);
    } else if (key === "className") {
      node.className = value;
    } else if (key === "checked" || key === "selected") {
      node[key] = Boolean(value);
    } else {
      node.setAttribute(key, value);
    }
  }
  const list = Array.isArray(children) ? children : [children];
  for (const child of list) {
    if (child == null) {
      continue;
    }
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

function filteredRows(rows, config = {}) {
  const query = state.query.trim().toLowerCase();
  let result = rows;
  if (query) {
    result = result.filter((row) => `${row.id} ${row.name} ${row.description ?? ""}`.toLowerCase().includes(query));
  }
  if (config.key === "items" && state.itemRarityFilter) {
    result = result.filter((row) => row.rarity === state.itemRarityFilter);
  }
  return result;
}

function ensureSelections() {
  if (!state.content) {
    return;
  }
  for (const tab of TABS) {
    if (tab.id === "advanced") {
      continue;
    }
    const rows = state.content[tab.id] || [];
    if (!Array.isArray(rows)) {
      continue;
    }
    if (!rows.some((row) => row.id === state.selected[tab.id])) {
      state.selected[tab.id] = rows[0]?.id;
    }
  }
}

function optionsWithCurrent(options, value) {
  const exists = options.some(([optionValue]) => String(optionValue) === String(value));
  if (exists || value == null || value === "") {
    return options;
  }
  return [[value, `${value} (현재 값)`], ...options];
}

function rarityOptions() {
  return (state.content.rarities.order || []).map((id) => [id, `${state.content.rarities.labels?.[id] ?? id} (${id})`]);
}

function rarityLabel(rarity) {
  return state.content.rarities.labels?.[rarity] ?? rarity ?? "";
}

function firstRarity() {
  return state.content.rarities.order?.[0] ?? "normal";
}

function itemOptions() {
  return state.content.items.map((item) => [item.id, `${item.name} (${item.id})`]);
}

function gachaItemOptions() {
  return state.content.items.map((item) => [
    item.id,
    `${item.name} (${item.id})${item.excluded_from_gacha ? " · 가챠 제외" : ""}`,
  ]);
}

function materialOptions() {
  return state.content.materials.map((material) => [material.id, `${material.name} (${material.id})`]);
}

function jobOptions() {
  return state.content.jobs.map((job) => [job.id, `${job.name} (${job.id})`]);
}

function stackEffectOptions() {
  return (state.content.stack_effects || []).map((effect) => [effect.id, `${effect.name} (${effect.id})`]);
}

function statOptions() {
  const labels = state.content.stats.labels || {};
  const order = state.content.stats.order || [];
  return order.map((id) => [id, `${labels[id] ?? id} (${id})`]);
}

function findById(key, id) {
  return (state.content[key] || []).find((row) => row.id === id);
}

function nextId(prefix, rows) {
  const base = String(prefix || "new").replace(/[^A-Za-z0-9_-]/g, "_").toLowerCase();
  const ids = new Set((rows || []).map((row) => row.id));
  if (!ids.has(base)) {
    return base;
  }
  for (let index = 2; index < 10000; index += 1) {
    const candidate = `${base}_${index}`;
    if (!ids.has(candidate)) {
      return candidate;
    }
  }
  return `${base}_${Date.now()}`;
}

function nextSort(rows) {
  const values = (rows || []).map((row) => Number(row.sort_order || 0));
  return (values.length ? Math.max(...values) : 0) + 10;
}

function blankReward() {
  return {
    items: [],
    materials: [],
  };
}

function formatStats(stats) {
  if (!stats || !Object.keys(stats).length) {
    return "스탯 없음";
  }
  const labels = state.content?.stats?.labels || {};
  const percent = new Set(state.content?.stats?.percent_stats || []);
  return sortedStatEntries(stats).map(([key, value]) => {
    const label = labels[key] ?? key;
    const text = percent.has(key) ? `${round(value * 100, 3)}%` : String(value);
    return `${label} ${text}`;
  }).join(", ");
}

function round(value, digits) {
  const unit = 10 ** digits;
  return Math.round(value * unit) / unit;
}

function markDirty() {
  state.dirty = true;
  updateDirty();
}

function updateDirty() {
  dirtyState.textContent = state.dirty ? "변경사항 있음" : "저장됨";
}

function setStatus(text) {
  statusText.textContent = text;
}

function showLoadError(error) {
  const message = error instanceof Error ? error.message : String(error || "알 수 없는 오류");
  setStatus("불러오기 실패");
  main.replaceChildren(el("div", { className: "empty" }, `콘텐츠를 불러오지 못했습니다. ${message}`));
  showToast(`콘텐츠를 불러오지 못했습니다. ${message}`, true);
}

function showToast(message, isError) {
  toast.textContent = message;
  toast.className = `toast ${isError ? "error" : "ok"}`;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.hidden = true;
  }, isError ? 9000 : 3500);
}
