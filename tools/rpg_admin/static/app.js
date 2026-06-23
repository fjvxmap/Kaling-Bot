const TABS = [
  { id: "items", label: "장비" },
  { id: "materials", label: "재료" },
  { id: "crafting_recipes", label: "제작" },
  { id: "dungeons", label: "던전" },
  { id: "bosses", label: "보스" },
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
  "enhancement",
  "drop_rarity_weights",
];

const OBJECTIVES = [
  ["damage", "이번 턴 피해량"],
  ["hits", "타수"],
  ["debuff", "디버프 횟수"],
];

const SKILL_ROLES = [
  "attack",
  "buff",
  "debuff",
  "defense",
  "heal",
];

const ID_PATTERN = /^[A-Za-z0-9_-]+$/;

const state = {
  content: null,
  tab: "items",
  selected: {},
  query: "",
  dirty: false,
};

const nav = document.getElementById("nav");
const main = document.getElementById("main");
const dirtyState = document.getElementById("dirtyState");
const statusText = document.getElementById("statusText");
const toast = document.getElementById("toast");

document.getElementById("reloadBtn").addEventListener("click", loadContent);
document.getElementById("validateBtn").addEventListener("click", validateContent);
document.getElementById("saveBtn").addEventListener("click", saveContent);

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
  const response = await fetch("/api/content");
  const payload = await response.json();
  if (!payload.ok) {
    showToast("콘텐츠를 불러오지 못했습니다.", true);
    return;
  }
  state.content = payload.content;
  state.dirty = false;
  state.query = "";
  ensureSelections();
  setStatus("콘텐츠를 불러왔습니다.");
  render();
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
  if (!state.content) {
    return;
  }
  setStatus("저장 중...");
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
}

async function postJson(path, data) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return response.json();
}

function render() {
  renderNav();
  updateDirty();
  if (!state.content) {
    main.replaceChildren(el("div", { className: "empty" }, "콘텐츠를 불러오는 중입니다."));
    return;
  }
  ensureSelections();
  if (state.tab === "items") {
    renderItems();
  } else if (state.tab === "materials") {
    renderMaterials();
  } else if (state.tab === "crafting_recipes") {
    renderRecipes();
  } else if (state.tab === "dungeons") {
    renderDungeons();
  } else if (state.tab === "bosses") {
    renderBosses();
  } else if (state.tab === "jobs") {
    renderJobs();
  } else if (state.tab === "skills") {
    renderSkills();
  } else {
    renderAdvanced();
  }
}

function renderNav() {
  const buttons = TABS.map((tab) => {
    const count = tab.id === "advanced" ? ADVANCED_KEYS.length : (state.content?.[tab.id]?.length ?? 0);
    return el("button", {
      className: state.tab === tab.id ? "active" : "",
      onclick: () => {
        state.tab = tab.id;
        state.query = "";
        render();
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
      base_price: 0,
    }),
    summary: (item) => `${item.rarity ?? ""} · ${formatStats(item.stats)}`,
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
      textAreaField("설명", item, "description", { full: true }),
    ]),
    statsEditor(item, "stats", "스탯"),
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
      description: "",
    }),
    summary: (material) => material.rarity ?? "",
    detail: renderMaterialDetail,
  });
}

function renderMaterialDetail(material) {
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid" }, [
      idField("materials", material),
      textField("이름", material, "name"),
      selectField("등급", material, "rarity", rarityOptions()),
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
      return `${item?.name ?? recipe.result_item_id} · Lv.${recipe.level_req ?? 1}`;
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
      numberField("필요 레벨", recipe, "level_req", { step: 1 }),
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

function renderDungeons() {
  renderEntityEditor({
    key: "dungeons",
    title: "던전",
    makeNew: () => ({
      id: nextId("dungeon", state.content.dungeons),
      name: "New Dungeon",
      level_req: 1,
      rank: 1,
      enemies: [],
      description: "",
      sort_order: nextSort(state.content.dungeons),
    }),
    summary: (dungeon) => `Lv.${dungeon.level_req ?? 1} · 몬스터 ${dungeon.enemies?.length ?? 0}`,
    detail: renderDungeonDetail,
  });
}

function renderDungeonDetail(dungeon) {
  dungeon.enemies ||= [];
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid three" }, [
      idField("dungeons", dungeon),
      textField("이름", dungeon, "name"),
      numberField("필요 레벨", dungeon, "level_req", { step: 1 }),
      numberField("랭크", dungeon, "rank", { step: 1 }),
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
      rank: 1,
      stats: { base_atk: 10, max_hp: 100 },
      patterns: [],
      hp_warnings: [],
      ct: { gauge_by_hp: [{ above: 0, max: 5 }], warnings_by_hp: [] },
      rewards: blankReward(),
      description: "",
      sort_order: nextSort(state.content.bosses),
    }),
    summary: (boss) => `Lv.${boss.level_req ?? 1} · HP ${boss.stats?.max_hp ?? 0}`,
    detail: renderBossDetail,
  });
}

function renderBossDetail(boss) {
  normalizeBossWarnings(boss);
  boss.hp_warnings ||= [];
  boss.ct ||= { gauge_by_hp: [], warnings_by_hp: [] };
  boss.ct.gauge_by_hp ||= [];
  boss.ct.warnings_by_hp ||= [];
  boss.rewards ||= blankReward();
  const body = el("div", { className: "panel-body" }, [
    el("div", { className: "form-grid three" }, [
      idField("bosses", boss),
      textField("이름", boss, "name"),
      numberField("필요 레벨", boss, "level_req", { step: 1 }),
      numberField("랭크", boss, "rank", { step: 1 }),
      numberField("정렬 순서", boss, "sort_order", { step: 1 }),
      numberField("기본 골드", boss, "gold", { step: 1 }),
      numberField("기본 경험치", boss, "exp", { step: 1 }),
      numberField("스탯포인트", boss, "stat_points", { step: 1 }),
      numberField("드랍 확률", boss, "drop_chance", { step: 0.01 }),
      textAreaField("설명", boss, "description", { full: true }),
    ]),
    statsEditor(boss, "stats", "보스 스탯"),
    bossHpWarningEditor(boss),
    bossCtEditor(boss),
    rewardEditor(boss, "rewards", "클리어 보상"),
  ]);
  mainDetail("보스 편집", boss, body);
}

function renderJobs() {
  renderEntityEditor({
    key: "jobs",
    title: "직업",
    makeNew: () => ({
      id: nextId("job", state.content.jobs),
      name: "New Job",
      tier: 1,
      level_req: 1,
      parent_id: "",
      stats: {},
      description: "",
    }),
    summary: (job) => `Tier ${job.tier ?? 0} · Lv.${job.level_req ?? 1}`,
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
      textAreaField("설명", job, "description", { full: true }),
    ]),
    statsEditor(job, "stats", "직업 스탯"),
  ]);
  mainDetail("직업 편집", job, body);
}

function renderSkills() {
  renderEntityEditor({
    key: "skills",
    title: "스킬",
    makeNew: () => ({
      id: nextId("skill", state.content.skills),
      name: "New Skill",
      unlock_level: 1,
      uses: 0,
      cooldown: 3,
      role: "attack",
      damage_multiplier: 0,
      hits: 0,
      player_mods: {},
      enemy_mods: {},
      duration: 0,
      heal_power: 0,
      damage_cut: 0,
      job_ids: [],
      note: "",
    }),
    summary: (skill) => `${skill.role ?? ""} · Lv.${skill.unlock_level ?? 1}`,
    detail: renderSkillDetail,
  });
}

function renderSkillDetail(skill) {
  skill.job_ids ||= [];
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
      numberField("지속 턴", skill, "duration", { step: 1 }),
      numberField("회복 계수", skill, "heal_power", { step: 0.01 }),
      numberField("데미지 컷", skill, "damage_cut", { step: 0.01 }),
      textAreaField("메모", skill, "note", { full: true }),
    ]),
    jobPicker(skill),
    statsEditor(skill, "player_mods", "플레이어 버프/보정"),
    statsEditor(skill, "enemy_mods", "적 디버프/보정"),
  ]);
  mainDetail("스킬 편집", skill, body);
}

function renderAdvanced() {
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
  main.replaceChildren(el("div", { className: "rows" }, sections));
}

function renderEntityEditor(config) {
  const rows = state.content[config.key] || [];
  if (!rows.length) {
    const created = config.makeNew();
    rows.push(created);
    state.selected[config.key] = created.id;
  }
  const selectedId = state.selected[config.key] || rows[0]?.id;
  const selected = rows.find((row) => row.id === selectedId) || rows[0];
  state.selected[config.key] = selected?.id;

  const listPanel = el("section", { className: "panel" }, [
    el("div", { className: "panel-header" }, [
      el("h2", {}, config.title),
      el("button", {
        type: "button",
        onclick: () => {
          const row = config.makeNew();
          rows.push(row);
          state.selected[config.key] = row.id;
          markDirty();
          render();
        },
      }, "추가"),
    ]),
    el("div", { className: "list-tools" }, [
      el("input", {
        type: "search",
        placeholder: "검색",
        value: state.query,
        oninput: (event) => {
          state.query = event.target.value;
          render();
        },
      }),
    ]),
    el("div", { className: "entity-list" }, filteredRows(rows).map((row) => entityButton(config, row))),
  ]);

  const detailShell = el("section", { className: "panel", id: "detailPanel" }, [
    el("div", { className: "empty" }, "왼쪽에서 항목을 선택하세요."),
  ]);

  main.replaceChildren(el("div", { className: "layout" }, [listPanel, detailShell]));
  if (selected) {
    config.detail(selected);
  }
}

function entityButton(config, row) {
  return el("button", {
    type: "button",
    className: `entity-row ${state.selected[config.key] === row.id ? "active" : ""}`,
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

function normalizeBossWarnings(boss) {
  boss.patterns ||= [];
  boss.hp_warnings ||= [];
  boss.ct ||= { gauge_by_hp: [], warnings_by_hp: [] };
  boss.ct.gauge_by_hp ||= [];
  boss.ct.warnings_by_hp ||= [];
  for (const warning of boss.hp_warnings) {
    ensureWarningPattern(boss, warning, "threshold");
  }
  for (const warning of boss.ct.warnings_by_hp) {
    ensureWarningPattern(boss, warning, "above");
  }
}

function ensureWarningPattern(boss, warning, thresholdKey) {
  if (warning.pattern && typeof warning.pattern === "object") {
    warning.pattern.id ||= warning.pattern_id || nextId(`${thresholdKey}_failure`, bossWarningPatterns(boss));
    warning.pattern.name ||= "전조 실패 효과";
    delete warning.pattern_id;
    return;
  }
  const legacyPattern = (boss.patterns || []).find((pattern) => (
    pattern.id === warning.pattern_id || pattern.name === warning.pattern_id
  ));
  if (legacyPattern) {
    warning.pattern = structuredClone(legacyPattern);
  } else {
    warning.pattern = blankBossPattern(boss, `${thresholdKey}_failure`, "전조 실패 효과");
  }
  delete warning.pattern_id;
}

function blankBossPattern(boss, prefix, name) {
  return {
    id: nextId(prefix, bossWarningPatterns(boss)),
    name,
    damage_multiplier: 0,
    hits: 0,
    player_mods: {},
    boss_mods: {},
    duration: 0,
  };
}

function defaultWarningPattern(boss, prefix, name) {
  const usedIds = new Set();
  for (const warning of boss.hp_warnings || []) {
    if (warning.pattern?.id) {
      usedIds.add(warning.pattern.id);
    }
  }
  for (const warning of boss.ct?.warnings_by_hp || []) {
    if (warning.pattern?.id) {
      usedIds.add(warning.pattern.id);
    }
  }
  const legacy = (boss.patterns || []).find((pattern) => pattern.id && !usedIds.has(pattern.id));
  return legacy ? structuredClone(legacy) : blankBossPattern(boss, prefix, name);
}

function bossWarningPatterns(boss) {
  const rows = [...(boss.patterns || [])];
  for (const warning of boss.hp_warnings || []) {
    if (warning.pattern) {
      rows.push(warning.pattern);
    }
  }
  for (const warning of boss.ct?.warnings_by_hp || []) {
    if (warning.pattern) {
      rows.push(warning.pattern);
    }
  }
  return rows;
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
        rank: dungeon.rank ?? 1,
        stats: { base_atk: 8, max_hp: 80 },
        gold: 0,
        exp: 0,
        drop_chance: 0,
        rare: false,
        description: "",
        rewards: blankReward(),
        consolation_rewards: blankReward(),
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
      textField("ID", enemy, "id"),
      textField("이름", enemy, "name"),
      numberField("등장 가중치", enemy, "weight", { step: 1 }),
      numberField("랭크", enemy, "rank", { step: 1 }),
      numberField("기본 골드", enemy, "gold", { step: 1 }),
      numberField("기본 경험치", enemy, "exp", { step: 1 }),
      numberField("드랍 확률", enemy, "drop_chance", { step: 0.01 }),
      checkboxField("보너스 몬스터", enemy, "rare"),
      textAreaField("설명", enemy, "description", { full: true }),
    ]),
    statsEditor(enemy, "stats", "몬스터 스탯"),
    rewardEditor(enemy, "rewards", "승리 보상"),
    rewardEditor(enemy, "consolation_rewards", "패배/위로 보상"),
  ]);
}

function bossHpWarningEditor(boss) {
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      boss.hp_warnings.push({
        threshold: 0.5,
        objective: "damage",
        required: 1,
        pattern: defaultWarningPattern(boss, "hp_failure", "체력 전조 실패 효과"),
      });
      markDirty();
      render();
    },
  }, "체력 전조 추가");
  return el("section", { className: "section" }, [
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
      boss.ct.warnings_by_hp.push({
        above: 0,
        objective: "hits",
        required: 1,
        pattern: defaultWarningPattern(boss, "ct_failure", "CT 전조 실패 효과"),
      });
      markDirty();
      render();
    },
  }, "CT 전조 추가");

  return el("section", { className: "section" }, [
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
    el("div", { className: "section" }, [
      el("div", { className: "section-head" }, [
        el("h3", {}, "CT 전조"),
        addWarning,
      ]),
      el("div", { className: "rows" }, boss.ct.warnings_by_hp.map((warning, index) => warningPanel(boss, boss.ct.warnings_by_hp, warning, index, "above"))),
    ]),
  ]);
}

function warningPanel(boss, rows, warning, index, thresholdKey = "threshold") {
  ensureWarningPattern(boss, warning, thresholdKey);
  const title = thresholdKey === "above" ? "CT 전조" : "체력 전조";
  return el("div", { className: "subpanel" }, [
    el("div", { className: "subpanel-head" }, [
      el("div", { className: "subpanel-title" }, [
        el("strong", {}, `${title} ${index + 1}`),
        el("span", { className: "badge" }, warning.pattern?.name || "실패 효과"),
      ]),
      deleteButton(() => {
        rows.splice(index, 1);
        markDirty();
        render();
      }),
    ]),
    el("div", { className: "form-grid three" }, [
      numberField(thresholdKey === "above" ? "HP 비율 초과" : "HP 임계값", warning, thresholdKey, { step: 0.01 }),
      selectField("요구 조건", warning, "objective", OBJECTIVES),
      numberField("요구량", warning, "required", { step: 1 }),
    ]),
    patternEffectEditor(warning.pattern),
  ]);
}

function patternEffectEditor(pattern) {
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "실패 시 발동"),
      el("span", { className: "muted" }, "이 전조를 못 풀고 턴을 넘기면 실행됩니다."),
    ]),
    el("div", { className: "form-grid three" }, [
      textField("효과 ID", pattern, "id"),
      textField("효과 이름", pattern, "name"),
      numberField("피해 배율", pattern, "damage_multiplier", { step: 0.01 }),
      numberField("타수", pattern, "hits", { step: 1 }),
      numberField("지속 턴", pattern, "duration", { step: 1 }),
    ]),
    statsEditor(pattern, "player_mods", "유저에게 적용"),
    statsEditor(pattern, "boss_mods", "보스에게 적용"),
  ]);
}

function rewardEditor(owner, key, title) {
  owner[key] ||= blankReward();
  const reward = owner[key];
  reward.gold ||= { min: 0, max: 0 };
  reward.items ||= [];
  reward.materials ||= [];
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, title),
    ]),
    el("div", { className: "form-grid three" }, [
      numberField("골드 최소", reward.gold, "min", { step: 1 }),
      numberField("골드 최대", reward.gold, "max", { step: 1 }),
      numberField("경험치", reward, "exp", { step: 1 }),
      numberField("스탯포인트", reward, "stat_points", { step: 1 }),
    ]),
    itemDropEditor(reward),
    materialDropEditor(reward),
  ]);
}

function itemDropEditor(reward) {
  const addButton = el("button", {
    type: "button",
    onclick: () => {
      reward.items.push({ chance: 1, rank: 1 });
      markDirty();
      render();
    },
  }, "장비 드랍 추가");
  const rows = reward.items.map((drop, index) => {
    const itemId = drop.template_id ?? drop.item_id ?? "";
    const target = {
      item_id: itemId,
      chance: drop.chance ?? 1,
      rank: drop.rank ?? 1,
      rarity: drop.rarity ?? "",
    };
    return el("div", { className: "row" }, [
      selectField("장비", target, "item_id", [["", "등급/랭크 랜덤"], ...itemOptions()], {
        onChange: (value) => {
          delete drop.item_id;
          delete drop.template_id;
          if (value) {
            drop.template_id = value;
          }
        },
      }),
      selectField("등급", target, "rarity", [["", "지정 안 함"], ...rarityOptions()], {
        onChange: (value) => {
          if (value) {
            drop.rarity = value;
          } else {
            delete drop.rarity;
          }
        },
      }),
      numberField("확률", drop, "chance", { step: 0.01 }),
      numberField("랭크", drop, "rank", { step: 1 }),
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
    numberField("확률", drop, "chance", { step: 0.01 }),
    numberField("최소", drop, "min", { step: 1 }),
    numberField("최대", drop, "max", { step: 1 }),
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

function materialCostEditor(recipe) {
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
        onChange: (newId) => {
          delete recipe.materials[materialId];
          recipe.materials[newId] = Number(proxy.count || 1);
        },
      }),
      numberField("수량", proxy, "count", {
        step: 1,
        onChange: (value) => {
          recipe.materials[proxy.material_id] = value;
        },
      }),
      deleteButton(() => {
        delete recipe.materials[materialId];
        markDirty();
        render();
      }),
    ]);
  });

  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "제작 재료"),
      addButton,
    ]),
    el("div", { className: "rows" }, rows.length ? rows : [el("div", { className: "empty" }, "제작 재료 없음")]),
  ]);
}

function statsEditor(owner, key, title) {
  owner[key] ||= {};
  const stats = owner[key];
  const statKeys = statOptions();
  const rows = Object.entries(stats).map(([statKey, value]) => {
    const proxy = { stat_key: statKey, value };
    return el("div", { className: "row two" }, [
      selectField("스탯", proxy, "stat_key", statKeys, {
        onChange: (newKey) => {
          delete stats[statKey];
          stats[newKey] = Number(proxy.value || 0);
        },
      }),
      numberField("값", proxy, "value", {
        step: 0.001,
        onChange: (newValue) => {
          stats[proxy.stat_key] = newValue;
        },
      }),
      deleteButton(() => {
        delete stats[statKey];
        markDirty();
        render();
      }),
    ]);
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

function jobPicker(skill) {
  const rows = state.content.jobs.map((job) => {
    const checked = skill.job_ids.includes(job.id);
    return el("label", { className: "field" }, [
      el("span", {}, job.name),
      el("input", {
        type: "checkbox",
        checked,
        onchange: (event) => {
          if (event.target.checked && !skill.job_ids.includes(job.id)) {
            skill.job_ids.push(job.id);
          }
          if (!event.target.checked) {
            skill.job_ids = skill.job_ids.filter((id) => id !== job.id);
          }
          markDirty();
        },
      }),
    ]);
  });
  return el("section", { className: "section" }, [
    el("div", { className: "section-head" }, [
      el("h3", {}, "사용 가능 직업"),
      el("span", { className: "muted" }, "미선택이면 공용 스킬"),
    ]),
    el("div", { className: "form-grid three" }, rows),
  ]);
}

function idField(entityKey, obj) {
  const input = el("input", {
    type: "text",
    value: obj.id ?? "",
    onchange: (event) => {
      const oldId = String(obj.id ?? "");
      const newId = event.target.value.trim();
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

function allRewards() {
  const rewards = [];
  for (const dungeon of state.content.dungeons || []) {
    for (const enemy of dungeon.enemies || []) {
      if (enemy.rewards) {
        rewards.push(enemy.rewards);
      }
      if (enemy.consolation_rewards) {
        rewards.push(enemy.consolation_rewards);
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
    oninput: (event) => {
      obj[key] = event.target.value;
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
    onchange: (event) => {
      obj[key] = event.target.value;
      markDirty();
      config.onChange?.(event.target.value);
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

function filteredRows(rows) {
  const query = state.query.trim().toLowerCase();
  if (!query) {
    return rows;
  }
  return rows.filter((row) => `${row.id} ${row.name} ${row.description ?? ""}`.toLowerCase().includes(query));
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

function firstRarity() {
  return state.content.rarities.order?.[0] ?? "normal";
}

function itemOptions() {
  return state.content.items.map((item) => [item.id, `${item.name} (${item.id})`]);
}

function materialOptions() {
  return state.content.materials.map((material) => [material.id, `${material.name} (${material.id})`]);
}

function jobOptions() {
  return state.content.jobs.map((job) => [job.id, `${job.name} (${job.id})`]);
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
    gold: { min: 0, max: 0 },
    exp: 0,
    stat_points: 0,
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
  return Object.entries(stats).map(([key, value]) => {
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

function showToast(message, isError) {
  toast.textContent = message;
  toast.className = `toast ${isError ? "error" : "ok"}`;
  toast.hidden = false;
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => {
    toast.hidden = true;
  }, isError ? 9000 : 3500);
}
