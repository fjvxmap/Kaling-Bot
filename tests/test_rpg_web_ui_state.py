from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "web" / "rpg_web" / "static" / "rpg_web" / "app.js"
APP_CSS = ROOT / "web" / "rpg_web" / "static" / "rpg_web" / "app.css"


class RPGWebUIStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app_js = APP_JS.read_text(encoding="utf-8")
        cls.app_css = APP_CSS.read_text(encoding="utf-8")

    def test_combat_disclosure_is_saved_and_bound_to_one_boss_session(self) -> None:
        self.assertIn("bossUi: saved.bossUi || {}", self.app_js)
        self.assertIn("bossUi: state.bossUi", self.app_js)

        ensure_start = self.app_js.index("  function ensureBossUi(session)")
        ensure_end = self.app_js.index("  function captureBossUi()", ensure_start)
        ensure_body = self.app_js[ensure_start:ensure_end]
        self.assertIn('String(state.bossUi.sessionId ?? "") !== sessionId', ensure_body)
        self.assertIn("combatDetailsOpen: false", ensure_body)
        self.assertIn('state.scroll["boss.combat-log"] = 0', ensure_body)
        self.assertIn('state.scroll["page:boss"] = 0', ensure_body)
        self.assertIn("clearBossUi();", self.app_js)

        self.assertIn('data-boss-session-id="${esc(session.id)}"', self.app_js)
        self.assertIn('${bossUi.combatDetailsOpen ? "open" : ""}', self.app_js)
        toggle_start = self.app_js.index('document.addEventListener("toggle"')
        toggle_end = self.app_js.index('document.addEventListener("click"', toggle_start)
        toggle_body = self.app_js[toggle_start:toggle_end]
        self.assertIn("bossUi.combatDetailsOpen = details.open", toggle_body)
        self.assertIn("}, true);", toggle_body)

    def test_combat_state_is_captured_before_dom_replacement(self) -> None:
        render_start = self.app_js.index("  function render()")
        render_end = self.app_js.index("  async function confirmAction", render_start)
        render_body = self.app_js[render_start:render_end]

        capture_index = render_body.index("captureBossUi();")
        replace_index = render_body.index("main.innerHTML =")
        self.assertLess(capture_index, replace_index)
        self.assertLess(render_body.index("captureScroll(renderedTab);"), replace_index)

    def test_combat_log_scroll_focus_and_terminal_history_are_preserved(self) -> None:
        self.assertIn('data-scroll-key="boss.combat-log"', self.app_js)
        self.assertIn('key !== "boss.combat-log"', self.app_js)
        self.assertIn("anchorId: anchor?.dataset.logId", self.app_js)
        self.assertIn("row.dataset.logId === savedPosition.anchorId", self.app_js)
        self.assertIn("session.log_start_index", self.app_js)
        self.assertIn('data-log-id="${row.id}"', self.app_js)
        self.assertIn("contentTop - Number(savedPosition.anchorOffset || 0)", self.app_js)
        self.assertIn("if (top <= 2)", self.app_js)
        self.assertIn('element.closest("details:not([open])")', self.app_js)
        self.assertIn("requestAnimationFrame(() => restoreElementScroll(combatLog))", self.app_js)
        self.assertIn('document.addEventListener("scroll"', self.app_js)
        self.assertIn('window.addEventListener("pagehide"', self.app_js)
        self.assertIn('data-focus-key="boss.attack"', self.app_js)
        self.assertIn('data-focus-key="boss.guard"', self.app_js)
        self.assertIn('data-focus-key="boss.ability:${esc(skill.id)}"', self.app_js)
        self.assertIn("captureFocus();", self.app_js)
        self.assertIn("restoreFocus();", self.app_js)
        self.assertIn('event.target.closest(\'[data-focus-key^="boss."]\')', self.app_js)
        self.assertIn("focusedCombatAction || enhanceDialogOpen", self.app_js)
        self.assertIn("renderCombatDetails(session, true)", self.app_js)
        self.assertIn(".combat-details-terminal", self.app_css)

    def test_tab_scroll_and_korean_filter_composition_are_not_reset(self) -> None:
        navigate_start = self.app_js.index("  function navigate(tab)")
        navigate_end = self.app_js.index("  function updateShell()", navigate_start)
        navigate_body = self.app_js[navigate_start:navigate_end]
        self.assertIn("if (!Object.hasOwn(state.scroll, pageKey))", navigate_body)
        self.assertNotIn('state.scroll[`page:${tab}`] = 0', navigate_body)

        self.assertIn('document.addEventListener("compositionstart"', self.app_js)
        self.assertIn("event.isComposing", self.app_js)
        self.assertIn('document.addEventListener("compositionend"', self.app_js)
        self.assertIn("if (composingFilter?.isConnected)", self.app_js)
        self.assertIn("end: active.selectionEnd", self.app_js)
        self.assertIn(
            'filter.setSelectionRange(savedFocus.start, savedFocus.end, savedFocus.direction || "none")',
            self.app_js,
        )

    def test_liberation_requirements_render_names_and_fail_safe_for_legacy_payloads(self) -> None:
        render_start = self.app_js.index("  function liberationRequirementData(")
        render_end = self.app_js.index("  function queueEnhancementPreview()", render_start)
        render_body = self.app_js[render_start:render_end]

        self.assertIn("Array.isArray(nextStage?.material_rows)", render_body)
        self.assertIn("Object.entries(nextStage?.materials || {})", render_body)
        self.assertIn("Array.isArray(profile?.materials)", render_body)
        self.assertIn('safeName === "해방 재료"', render_body)
        self.assertIn("${esc(row.name)}", render_body)
        self.assertIn("requirementData.incomplete", render_body)
        self.assertIn("화면을 새로고침한 뒤 다시 시도해 주세요.", render_body)
        self.assertIn('? "disabled" : ""', render_body)
        self.assertNotIn("|| id", render_body)
        self.assertNotIn("${esc(id)}", render_body)


if __name__ == "__main__":
    unittest.main()
