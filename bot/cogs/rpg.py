from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.rpg.data import (
    BOSS_BY_ID,
    BOSSES,
    CRAFTING_RECIPES,
    DAILY_EXPLORES,
    DUNGEONS,
    GACHA_DEFAULT_POOL_ID,
    GACHA_POOLS,
    ITEM_BY_ID,
    MATERIAL_BY_ID,
    MATERIALS,
    MAX_EQUIPPED_ITEMS,
    MAX_EQUIPPED_SKILLS,
    RARITIES,
    RARITY_COLORS,
    RARITY_LABELS,
    BossPattern,
    BossTemplate,
    BossWarningFailureVariant,
    BossWarningTemplate,
    SkillTemplate,
    STACK_EFFECT_BY_ID,
)
from bot.services.rpg.manager import (
    ActiveEffect,
    ActiveStackEffect,
    AbilityResult,
    BossResult,
    CraftResult,
    ExploreBatchResult,
    EnhancementPreview,
    EnhancementResult,
    EquipmentResult,
    ExploreResult,
    GachaResult,
    JobResult,
    RPGService,
    SellResult,
)
from bot.services.rpg.models import PlayerProfile


DUNGEON_CHOICES = [
    app_commands.Choice(name=f"{dungeon.name} · Lv.{dungeon.level_req}+", value=dungeon.id)
    for dungeon in DUNGEONS
]
BOSS_CHOICES = [
    app_commands.Choice(name=f"{boss.name} · Lv.{boss.level_req}+", value=boss.id)
    for boss in BOSSES
]
CRAFT_CHOICES = [
    app_commands.Choice(name=f"{recipe.name} · Lv.{recipe.level_req}+", value=recipe.id)
    for recipe in CRAFTING_RECIPES[:25]
]
GACHA_CHOICES = [
    app_commands.Choice(name=pool.name[:100], value=pool.id)
    for pool in GACHA_POOLS[:25]
]

OBJECTIVE_LABELS = {
    "damage": "피해",
    "hits": "타수",
    "debuff": "디버프",
    "dispel": "디스펠",
    "clear_all": "클리어 올",
    "triple_attack": "트리플 어택",
    "double_attack": "더블 어택",
    "ability": "어빌리티",
    "ability_damage": "어빌리티 피해",
}

RARITY_EMOJIS = {
    "normal": "⚪",
    "rare": "🔵",
    "epic": "🟣",
    "unique": "🟠",
    "legendary": "🟢",
}

@dataclass
class BossWarningObjectiveProgress:
    objective: str
    required: int
    min_damage: int = 0
    progress: int = 0


@dataclass
class BossWarning:
    source: str
    name: str
    pattern: BossPattern
    objectives: list[BossWarningObjectiveProgress]
    threshold: float | None = None
    remaining_turns: int = 1
    failure_variants: list[BossWarningFailureVariant] = field(default_factory=list)


@dataclass
class BossDamageDetail:
    action: str
    target: str
    summary: str
    total_damage: int
    hit_damages: list[int]
    ability_damage: int = 0
    detail_lines: list[str] = field(default_factory=list)
    received_damage: int = 0
    received_hit_damages: list[int] = field(default_factory=list)
    received_detail_lines: list[str] = field(default_factory=list)
    received_summary: str = ""
    received_source: str = ""


@dataclass
class BossParticipant:
    user_id: int
    display_name: str
    hp: int
    max_hp: int
    ct: int = 0
    alive: bool = True
    pending_warning: BossWarning | None = None
    queued_warnings: list[BossWarning] = field(default_factory=list)
    triggered_thresholds: set[int] = field(default_factory=set)
    triggered_hp_effects: set[int] = field(default_factory=set)
    player_effects: list[ActiveEffect] = field(default_factory=list)
    boss_effects: list[ActiveEffect] = field(default_factory=list)
    player_stack_effects: list[ActiveStackEffect] = field(default_factory=list)
    boss_stack_effects: list[ActiveStackEffect] = field(default_factory=list)
    unlocked_hp_locks: set[int] = field(default_factory=set)
    pending_hp_locks: set[int] = field(default_factory=set)
    ability_cooldowns: dict[str, int] = field(default_factory=dict)
    ability_uses_left: dict[str, int] = field(default_factory=dict)
    last_damage_detail: BossDamageDetail | None = None
    suppress_warning_activation: bool = False


@dataclass
class BossSession:
    id: int
    boss: BossTemplate
    owner_id: int
    practice: bool = False
    boss_hp: int = 0
    boss_max_hp: int = 0
    ct_max: int = 4
    started: bool = False
    completed: bool = False
    failed: bool = False
    cancelled: bool = False
    participants: dict[int, BossParticipant] = field(default_factory=dict)
    rewards: dict[int, str] = field(default_factory=dict)
    reward_materials: dict[str, int] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    message: discord.Message | None = None

    def __post_init__(self) -> None:
        self.boss_max_hp = max(1, int(self.boss.stats.get("max_hp", 1)))
        self.boss_hp = self.boss_max_hp
        self.ct_max = self.boss.ct_gauge[0].max if self.boss.ct_gauge else self.ct_max


class RPGCog(commands.Cog):
    rpg = app_commands.Group(name="rpg", description="가볍게 즐기는 던전/보스 RPG")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = RPGService()
        self.boss_sessions: dict[int, BossSession] = {}
        self._boss_damage_detail_messages: dict[tuple[int, int], discord.WebhookMessage] = {}
        self._next_boss_session_id = 1

    @rpg.command(name="시작", description="RPG 프로필을 만들거나 현재 상태를 확인합니다.")
    async def start(self, interaction: discord.Interaction) -> None:
        profile, created = self.service.start_profile(
            interaction.user.id,
            interaction.user.display_name,
        )
        embed = self._profile_embed(profile)
        embed.title = "RPG 시작" if created else "RPG 프로필"
        if created:
            embed.description = "프로필을 만들었습니다. `/rpg 던전목록`에서 갈 곳을 고른 뒤 `/rpg 탐색`을 사용하세요."
        else:
            embed.description = "이미 프로필이 있습니다. 이어서 진행하면 됩니다."
        await interaction.response.send_message(embed=embed)

    @rpg.command(name="프로필", description="레벨, 전직, 경험치, 스탯, 장착 장비를 봅니다.")
    async def profile(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        await interaction.response.send_message(embed=self._profile_embed(profile))

    @rpg.command(name="던전목록", description="탐색 가능한 던전 정보를 봅니다.")
    async def dungeon_list(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        lines = []
        for dungeon in self.service.dungeons():
            state = "입장 가능" if profile.level >= dungeon.level_req else f"Lv.{dungeon.level_req} 필요"
            rare_names = ", ".join(enemy.name for enemy in dungeon.enemies if enemy.rare) or "없음"
            reward_lines = ", ".join(
                f"{enemy.name}: {self.service.reward_summary(enemy.rewards, base_gold=enemy.gold, base_exp=enemy.exp)}"
                for enemy in dungeon.enemies[:3]
            )
            lines.append(
                f"**{dungeon.name}** · {state}\n"
                f"{self._trim(reward_lines, 700)} · 희귀 {rare_names}\n"
                f"{dungeon.description}"
            )
        embed = discord.Embed(
            title="던전 목록",
            description=f"탐색 제한: **{self._explore_limit_text(profile)}**",
            color=0x4BA3FF,
        )
        embed.add_field(name="탐색지", value="\n\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed)

    @rpg.command(name="탐색", description="던전을 선택해 탐색합니다.")
    @app_commands.rename(dungeon="던전", count="횟수")
    @app_commands.describe(
        dungeon="탐색할 던전. 비워두면 선택 UI를 표시합니다.",
        count="한 번에 진행할 탐색 횟수입니다. 최대 50회.",
    )
    @app_commands.choices(dungeon=DUNGEON_CHOICES)
    async def explore(
        self,
        interaction: discord.Interaction,
        dungeon: app_commands.Choice[str] | None = None,
        count: app_commands.Range[int, 1, 50] = 1,
    ) -> None:
        if dungeon is None:
            profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
            embed = self._exploration_panel_embed(profile)
            view = ExplorationView(self, interaction.user.id, interaction.user.display_name)
            await interaction.response.send_message(embed=embed, view=view)
            return
        view = ExplorationView(self, interaction.user.id, interaction.user.display_name, dungeon.value)
        if count > 1:
            result = self.service.explore_many(
                interaction.user.id,
                interaction.user.display_name,
                dungeon.value,
                count,
            )
            await interaction.response.send_message(embed=self._explore_batch_embed(result), view=view)
            return
        result = self.service.explore(
            interaction.user.id,
            interaction.user.display_name,
            dungeon.value,
        )
        await interaction.response.send_message(embed=self._explore_embed(result), view=view)

    @rpg.command(name="보스목록", description="도전 가능한 보스와 보상 정보를 봅니다.")
    async def boss_list(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        lines = []
        for boss in self.service.bosses():
            gate = "도전 가능" if profile.level >= boss.level_req else f"Lv.{boss.level_req} 필요"
            start_limit = self._boss_start_limit_text(profile, boss.id)
            lines.append(
                f"**{boss.name}** · {gate} · 자발 {start_limit}\n"
                f"보상 {self.service.reward_summary(boss.rewards, base_gold=boss.gold, base_exp=boss.exp)} · {boss.description}"
            )
        embed = discord.Embed(
            title="보스 목록",
            color=0xFFB84D,
        )
        embed.add_field(name="보스", value="\n\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed)

    @rpg.command(name="보스", description="보스 선택 패널을 엽니다.")
    async def boss(self, interaction: discord.Interaction) -> None:
        await self._send_boss_panel(interaction)

    @app_commands.command(name="보스", description="보스 선택 패널을 엽니다.")
    async def boss_top_level(self, interaction: discord.Interaction) -> None:
        await self._send_boss_panel(interaction)

    @rpg.command(name="전직목록", description="현재 직업에서 가능한 전직과 전체 직업 정보를 봅니다.")
    async def job_list(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        current = self.service.current_job(profile)
        available = {job.id for job in self.service.available_jobs(profile)}
        next_jobs = {job.id for job in self.service.next_jobs(profile)}
        lines = []
        for job in self.service.jobs():
            if job.id == "novice":
                continue
            if job.id in available:
                state = "전직 가능"
            elif job.id in next_jobs:
                state = f"Lv.{job.level_req} 필요"
            elif job.id in {owned.id for owned in self.service.job_chain(profile)}:
                state = "완료"
            else:
                state = "다른 계열"
            lines.append(
                f"**{job.name}** · {state}\n"
                f"{self.service.format_stats(job.stats, signed=True)}\n"
                f"{job.description}"
            )
        embed = discord.Embed(
            title="전직 목록",
            description=f"현재 직업: **{current.name}**",
            color=0xB56BFF,
        )
        embed.add_field(name="직업", value=self._trim("\n\n".join(lines), 3900), inline=False)
        await interaction.response.send_message(embed=embed)

    @rpg.command(name="전직", description="조건을 만족한 다음 전직을 선택합니다.")
    @app_commands.rename(job="직업")
    @app_commands.describe(job="전직할 직업. 비워두면 선택 UI를 표시합니다.")
    async def advance_job(
        self,
        interaction: discord.Interaction,
        job: str | None = None,
    ) -> None:
        if job is None:
            profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
            view = JobAdvanceView(self, interaction.user.id, interaction.user.display_name)
            await interaction.response.send_message(
                embed=self._job_advance_embed(profile),
                view=view if view.children else None,
            )
            return
        result = self.service.advance_job(
            interaction.user.id,
            interaction.user.display_name,
            job,
        )
        view = JobAdvanceView(self, interaction.user.id, interaction.user.display_name)
        await interaction.response.send_message(
            embed=self._job_advance_embed(result.profile, result),
            view=view if view.children else None,
        )

    @advance_job.autocomplete("job")
    async def advance_job_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        query = current.lower()
        jobs = [
            job for job in self.service.available_jobs(profile)
            if query in job.name.lower() or query in job.id.lower()
        ]
        return [
            app_commands.Choice(name=f"{job.name} · Lv.{job.level_req}+", value=job.id)
            for job in jobs[:25]
        ]

    @rpg.command(name="인벤토리", description="보유 장비와 장착 상태를 보고 직접 장착/해제합니다.")
    async def inventory(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        if not profile.inventory:
            embed = discord.Embed(
                title="인벤토리",
                description="아직 장비가 없습니다. 던전이나 보스를 클리어해 보세요.",
                color=0xA0A7B4,
            )
            await interaction.response.send_message(embed=embed)
            return
        view = EquipmentView(self, interaction.user.id, interaction.user.display_name)
        await interaction.response.send_message(embed=self._equipment_embed(profile), view=view)

    @rpg.command(name="재료", description="보유 제작 재료와 제작 가능 항목을 확인합니다.")
    async def materials(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        await interaction.response.send_message(embed=self._materials_embed(profile))

    @rpg.command(name="제작", description="재료와 골드를 사용해 원하는 장비를 제작합니다.")
    @app_commands.rename(recipe="제작법")
    @app_commands.describe(recipe="확인할 제작법. 비워두면 제작 UI를 표시합니다.")
    @app_commands.choices(recipe=CRAFT_CHOICES)
    async def craft(
        self,
        interaction: discord.Interaction,
        recipe: app_commands.Choice[str] | None = None,
    ) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        selected_recipe_id = recipe.value if recipe is not None else None
        await interaction.response.send_message(
            embed=self._crafting_embed(profile, selected_recipe_id),
            view=CraftingView(self, interaction.user.id, interaction.user.display_name, selected_recipe_id),
        )

    @rpg.command(name="가챠", description="보정석을 사용해 랜덤 보상을 획득하는 패널을 엽니다.")
    @app_commands.rename(pool="풀")
    @app_commands.describe(pool="사용할 가챠 풀. 비워두면 기본 풀을 사용합니다.")
    @app_commands.choices(pool=GACHA_CHOICES)
    async def gacha(
        self,
        interaction: discord.Interaction,
        pool: app_commands.Choice[str] | None = None,
    ) -> None:
        selected_pool_id = pool.value if pool is not None else None
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        await interaction.response.send_message(
            embed=self._gacha_panel_embed(profile, selected_pool_id),
            view=GachaView(self, interaction.user.id, interaction.user.display_name, selected_pool_id),
        )

    @rpg.command(name="장착", description="장비 장착 관리 UI를 엽니다.")
    async def equipment(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        if not profile.inventory:
            embed = discord.Embed(
                title="장비 장착",
                description="아직 장비가 없습니다. 던전이나 보스를 클리어해 보세요.",
                color=0xA0A7B4,
            )
            await interaction.response.send_message(embed=embed)
            return
        await interaction.response.send_message(
            embed=self._equipment_embed(profile),
            view=EquipmentView(self, interaction.user.id, interaction.user.display_name),
        )

    @rpg.command(name="판매", description="장비 판매 UI를 엽니다.")
    async def sell(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        sellable = self._sellable_items(profile)
        if not sellable:
            embed = discord.Embed(
                title="장비 판매",
                description="판매할 수 있는 장비가 없습니다. 장착 중인 장비는 판매 목록에서 제외됩니다.",
                color=0xA0A7B4,
            )
            await interaction.response.send_message(embed=embed)
            return
        await interaction.response.send_message(
            embed=self._sell_embed(profile),
            view=SellView(self, interaction.user.id, interaction.user.display_name),
        )

    @rpg.command(name="자동판매", description="드랍 시 자동으로 판매할 장비 등급을 설정합니다.")
    async def auto_sell(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        await interaction.response.send_message(
            embed=self._auto_sell_embed(profile),
            view=AutoSellView(self, interaction.user.id, interaction.user.display_name),
        )

    @rpg.command(name="어빌리티", description="전투와 보스전에 사용할 어빌리티를 장착합니다.")
    async def abilities(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        active_session = self._active_boss_session_for_user(interaction.user.id, started_only=True)
        if active_session is not None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="어빌리티 변경 불가",
                    description=(
                        f"**{active_session.boss.name}** 보스전 진행 중에는 "
                        "어빌리티 장착을 바꿀 수 없습니다."
                    ),
                    color=0xED4245,
                ),
                ephemeral=True,
            )
            return
        skills = self.service.unlocked_skills(profile)
        if not skills:
            embed = discord.Embed(
                title="어빌리티",
                description="아직 사용할 수 있는 어빌리티가 없습니다.",
                color=0xA0A7B4,
            )
            await interaction.response.send_message(embed=embed)
            return
        await interaction.response.send_message(
            embed=self._ability_embed(profile),
            view=AbilityEquipView(self, interaction.user.id, interaction.user.display_name),
        )

    @rpg.command(name="강화", description="장비를 선택해서 강화 정보와 확률을 확인합니다.")
    @app_commands.rename(uid="장비번호")
    @app_commands.describe(uid="바로 확인할 장비 번호. 비워두면 선택 UI를 표시합니다.")
    async def enhance(self, interaction: discord.Interaction, uid: int | None = None) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        if not profile.inventory:
            embed = discord.Embed(
                title="장비 강화",
                description="강화할 장비가 없습니다. 던전이나 보스에서 장비를 획득하세요.",
                color=0xED4245,
            )
            await interaction.response.send_message(embed=embed)
            return
        item = self._profile_item(profile, uid)
        if item is not None and item.destroyed:
            view = RestoreView(self, interaction.user.id, interaction.user.display_name, uid)
            embed = self._restore_panel_embed(interaction.user.id, interaction.user.display_name, uid, view.selected_spare_uid)
            await interaction.response.send_message(embed=embed, view=view)
            return
        view = EnhancementView(self, interaction.user.id, interaction.user.display_name, uid)
        embed = self._enhancement_picker_embed(profile) if uid is None else self._enhancement_preview_embed(
            self.service.enhancement_preview(interaction.user.id, interaction.user.display_name, uid)
        )
        await interaction.response.send_message(embed=embed, view=view)

    @rpg.command(name="복구", description="파괴된 장비 흔적을 성급 3단계 하락 상태로 복구합니다.")
    @app_commands.rename(uid="장비번호")
    @app_commands.describe(uid="복구할 장비 번호. 비워두면 강화/복구 UI를 표시합니다.")
    async def restore(self, interaction: discord.Interaction, uid: int | None = None) -> None:
        view = RestoreView(self, interaction.user.id, interaction.user.display_name, uid)
        await interaction.response.send_message(
            embed=self._restore_panel_embed(
                interaction.user.id,
                interaction.user.display_name,
                view.selected_trace_uid,
                view.selected_spare_uid,
            ),
            view=view,
        )

    def _add_boss_participant(self, session: BossSession, user_id: int, display_name: str) -> tuple[bool, str]:
        if session.started:
            return False, "이미 시작된 보스전에는 참가할 수 없습니다."
        if user_id in session.participants:
            return True, "이미 참가 중입니다."
        active_session = self._active_boss_session_for_user(user_id, exclude_session_id=session.id)
        if active_session is not None:
            return False, f"이미 {active_session.boss.name} 보스전에 참가 중입니다."
        profile = self.service.get_profile(user_id, display_name)
        if profile.level < session.boss.level_req:
            return False, f"{session.boss.name}은 Lv.{session.boss.level_req}부터 참가할 수 있습니다."
        stats = self.service.profile_stats(profile)
        session.participants[user_id] = BossParticipant(
            user_id=user_id,
            display_name=display_name,
            hp=stats.final_hp,
            max_hp=stats.final_hp,
            boss_stack_effects=self._initial_boss_stack_effects(session.boss),
        )
        self._refresh_boss_permanent_effects(session)
        session.log.append(f"{display_name} 참가")
        return True, "참가했습니다."

    def _active_boss_session_for_user(
        self,
        user_id: int,
        *,
        exclude_session_id: int | None = None,
        started_only: bool = False,
    ) -> BossSession | None:
        for session in self.boss_sessions.values():
            if exclude_session_id is not None and session.id == exclude_session_id:
                continue
            if session.completed or session.failed or session.cancelled:
                continue
            if started_only and not session.started:
                continue
            if user_id in session.participants:
                return session
        return None

    def _boss_start_limit_text(self, profile: PlayerProfile, boss_id: str) -> str:
        remaining = self.service.boss_start_remaining(profile, boss_id)
        if remaining < 0:
            return "무제한"
        return f"{remaining}/1"

    async def _send_boss_panel(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        await interaction.response.send_message(
            embed=self._boss_panel_embed(profile, None),
            view=BossPanelView(self, interaction.user.id, interaction.user.display_name, None),
        )

    def _boss_panel_embed(self, profile: PlayerProfile, selected_boss_id: str | None = None) -> discord.Embed:
        embed = discord.Embed(
            title="보스 선택",
            color=0xFFB84D,
        )
        lines = []
        for boss in self.service.bosses():
            gate = "도전 가능" if profile.level >= boss.level_req else f"Lv.{boss.level_req} 필요"
            selected = " ← 선택됨" if boss.id == selected_boss_id else ""
            lines.append(
                f"**{boss.name}** · {gate} · 자발 {self._boss_start_limit_text(profile, boss.id)}{selected}"
            )
        embed.add_field(name="목록", value=self._trim("\n".join(lines), 1200), inline=False)
        selected = BOSS_BY_ID.get(selected_boss_id or "")
        if selected is not None:
            embed.add_field(
                name="선택한 보스",
                value=(
                    f"**{selected.name}** · Lv.{selected.level_req}+ · 자발 {self._boss_start_limit_text(profile, selected.id)}\n"
                    f"보상 {self.service.reward_summary(selected.rewards, base_gold=selected.gold, base_exp=selected.exp)}\n"
                    f"{selected.description or '설명 없음'}"
                ),
                inline=False,
            )
        return embed

    def _create_boss_session(
        self,
        template: BossTemplate,
        user_id: int,
        display_name: str,
        *,
        practice: bool = False,
    ) -> tuple[BossSession | None, str]:
        profile = self.service.get_profile(user_id, display_name)
        if profile.level < template.level_req:
            return None, f"{template.name}은 Lv.{template.level_req}부터 도전할 수 있습니다."
        active_session = self._active_boss_session_for_user(user_id)
        if active_session is not None:
            return None, (
                f"이미 {active_session.boss.name} 보스전에 참가 중입니다. "
                "완료되거나 실패한 뒤 다른 보스전에 참가할 수 있습니다."
            )
        if not practice and self.service.boss_start_remaining(profile, template.id) == 0:
            return None, f"{template.name} 자발 횟수를 모두 사용했습니다."

        session_id = self._next_boss_session_id
        self._next_boss_session_id += 1
        session = BossSession(session_id, template, user_id, practice=practice)
        ok, message = self._add_boss_participant(session, user_id, display_name)
        if not ok:
            return None, message
        self.boss_sessions[session_id] = session
        return session, "보스전 패널을 열었습니다."

    def _start_boss_session(self, session: BossSession, user_id: int) -> tuple[bool, str]:
        if user_id != session.owner_id:
            return False, "보스전을 만든 사람만 시작할 수 있습니다."
        if session.cancelled:
            return False, "이미 취소된 보스전입니다."
        if session.completed or session.failed:
            return False, "이미 종료된 보스전입니다."
        if session.started:
            return True, "이미 시작되었습니다."
        if not session.participants:
            return False, "참가자가 없습니다."
        owner = session.participants.get(session.owner_id)
        if owner is None:
            return False, "자발자 정보를 찾을 수 없습니다."
        self._refresh_boss_permanent_effects(session)
        session.started = True
        session.log.append("보스전 시작")
        for participant in session.participants.values():
            profile = self.service.get_profile(participant.user_id, participant.display_name)
            self._reset_boss_ability_uses(participant, profile)
            self._prepare_visible_warning(session, participant, profile)
        return True, "보스전을 시작했습니다."

    def _cancel_waiting_boss_participation(
        self,
        session: BossSession,
        user_id: int,
        display_name: str,
    ) -> tuple[bool, str]:
        if session.cancelled:
            return True, "이미 취소된 보스전입니다."
        if session.completed or session.failed:
            return False, "이미 종료된 보스전입니다."
        if session.started:
            return False, "이미 시작된 보스전입니다. 진행 중에는 포기 버튼을 사용하세요."
        participant = session.participants.get(user_id)
        if participant is None:
            return False, "이 보스전에 참가하지 않았습니다."
        if user_id == session.owner_id:
            session.cancelled = True
            session.log.append(f"{participant.display_name}: 보스전 준비 취소")
            return True, "보스전 준비를 취소했습니다."
        del session.participants[user_id]
        session.log.append(f"{participant.display_name}: 참가 취소")
        self._refresh_boss_permanent_effects(session)
        return True, "참가를 취소했습니다."

    def _give_up_boss_session(
        self,
        session: BossSession,
        user_id: int,
        display_name: str,
    ) -> tuple[bool, str]:
        if session.cancelled:
            return True, "이미 종료된 보스전입니다."
        if session.completed or session.failed:
            return False, "이미 종료된 보스전입니다."
        if not session.started:
            return False, "아직 시작되지 않은 보스전입니다. 대기 중에는 취소 버튼을 사용하세요."
        participant = session.participants.get(user_id)
        if participant is None:
            return False, "이 보스전에 참가하지 않았습니다."
        del session.participants[user_id]
        session.log.append(f"{participant.display_name}: 보스전 포기")
        if not session.participants:
            session.cancelled = True
            session.log.append("모든 참전자가 포기하여 보스전 종료")
        return True, "보스전을 포기했습니다."

    def _refresh_boss_permanent_effects(self, session: BossSession) -> None:
        if session.started:
            return
        participants = list(session.participants.values())
        for participant in participants:
            participant.player_effects = []
            participant.boss_stack_effects = self._initial_boss_stack_effects(session.boss)
        effect_lists = [participant.player_effects for participant in participants]
        for participant in participants:
            profile = self.service.get_profile(participant.user_id, participant.display_name)
            self.service._append_permanent_effects(
                profile,
                participant.player_effects,
                all_targets=effect_lists,
            )
        for participant in participants:
            profile = self.service.get_profile(participant.user_id, participant.display_name)
            stats = self.service._stats_with_effects(
                self.service.profile_stats(profile),
                participant.player_effects,
                participant.player_stack_effects,
            )
            participant.max_hp = stats.final_hp
            participant.hp = stats.final_hp

    def _initial_boss_stack_effects(self, boss: BossTemplate) -> list[ActiveStackEffect]:
        effects: list[ActiveStackEffect] = []
        for stack_effect in boss.stack_effects:
            effects.append(
                ActiveStackEffect(
                    stack_effect.stack_effect_id,
                    stack_effect.initial_stacks,
                    persistent=True,
                )
            )
        return effects

    def _reset_boss_ability_uses(self, participant: BossParticipant, profile: PlayerProfile) -> None:
        participant.ability_cooldowns = {}
        participant.ability_uses_left = {
            skill.id: skill.uses
            for skill in self.service.equipped_skills(profile)
            if skill.uses > 0
        }

    def _ability_uses_left(self, participant: BossParticipant, skill: SkillTemplate) -> int | None:
        if skill.uses <= 0:
            return None
        return participant.ability_uses_left.get(skill.id, skill.uses)

    def _ability_used_out(self, participant: BossParticipant, skill: SkillTemplate) -> bool:
        uses_left = self._ability_uses_left(participant, skill)
        return uses_left is not None and uses_left <= 0

    def _mark_boss_ability_used(self, participant: BossParticipant, skill: SkillTemplate) -> None:
        uses_left = self._ability_uses_left(participant, skill)
        if uses_left is not None:
            participant.ability_uses_left[skill.id] = max(0, uses_left - 1)
        if skill.cooldown > 0:
            participant.ability_cooldowns[skill.id] = skill.cooldown

    def _boss_use_ability(self, session: BossSession, user_id: int, display_name: str, skill_id: str) -> tuple[bool, str]:
        participant = session.participants.get(user_id)
        if participant is None:
            return False, "이 보스전에 참가하지 않았습니다."
        if not session.started or session.completed or session.failed or session.cancelled:
            return False, "진행 중인 보스전이 아닙니다."
        if not participant.alive:
            return False, "전투 불능 상태입니다."
        cooldown = participant.ability_cooldowns.get(skill_id, 0)
        if cooldown > 0:
            return False, f"아직 쿨타임이 {cooldown}턴 남았습니다."
        profile = self.service.get_profile(user_id, display_name)
        skill = next((owned for owned in self.service.equipped_skills(profile) if owned.id == skill_id), None)
        if skill is None:
            return False, "장착 중인 어빌리티가 아닙니다."
        if self._ability_used_out(participant, skill):
            return False, "이미 이번 보스전에서 사용한 어빌리티입니다."

        had_warning = participant.pending_warning is not None
        player_base = self.service.profile_stats(profile)
        player_stats = self.service._stats_with_effects(player_base, participant.player_effects, participant.player_stack_effects)
        boss_base = self.service._enemy_stats(session.boss.stats)
        boss_stats = self.service._stats_with_effects(boss_base, participant.boss_effects, participant.boss_stack_effects)
        boss_effect_lists = self._boss_effect_lists(session)
        boss_stack_lists = self._boss_stack_lists(session)
        boss_effects_before = self._effect_snapshot(participant.boss_effects)
        player_stack_lists = [
            ally.player_stack_effects
            for ally in session.participants.values()
            if ally.alive
        ]
        skill_result = self.service._use_player_skill(
            skill,
            player_stats,
            boss_stats,
            participant.hp,
            session.boss_hp,
            participant.player_effects,
            participant.boss_effects,
            ally_effects=[
                ally.player_effects
                for ally in session.participants.values()
                if ally.alive
            ],
            opponent_effects=boss_effect_lists,
            player_stack_effects=participant.player_stack_effects,
            enemy_stack_effects=participant.boss_stack_effects,
            ally_stack_effects=player_stack_lists,
            opponent_stack_effects=boss_stack_lists,
        )
        self._sync_shared_effect_changes(participant.boss_effects, boss_effect_lists, boss_effects_before)
        life_steal_heal = 0
        actual_dealt_damage = 0
        actual_dealt_segments: list[int] = []
        if skill_result.damage > 0:
            actual_dealt_damage = self._apply_boss_damage(session, participant, skill_result.damage)
            actual_dealt_segments = self.service._clamped_damage_segments(skill_result.hit_damages, actual_dealt_damage)
            life_steal_heal = self._apply_participant_life_steal(
                participant,
                player_stats,
                actual_dealt_damage,
                actual_dealt_segments,
            )
        skill_heal = self._apply_boss_skill_heal(session, participant, skill, skill_result.raw_heal)
        debuff_count = self._debuff_effect_count(skill)
        self._add_warning_progress(participant, "damage", skill_result.damage)
        self._add_warning_progress(participant, "ability_damage", skill_result.damage)
        self._add_warning_hit_progress(participant, skill_result.hit_damages)
        self._add_warning_progress(participant, "debuff", debuff_count)
        self._add_warning_progress(participant, "dispel", skill_result.dispels)
        self._add_warning_progress(participant, "clear_all", skill_result.clear_alls)
        self._add_warning_progress(participant, "ability", 1)
        self._apply_player_stack_event(participant, "damage", skill_result.damage)
        self._apply_player_stack_event(participant, "ability_damage", skill_result.damage)
        self._apply_player_stack_event(participant, "hits", hit_damages=skill_result.hit_damages)
        self._apply_player_stack_event(participant, "debuff", debuff_count)
        self._apply_player_stack_event(participant, "dispel", skill_result.dispels)
        self._apply_player_stack_event(participant, "clear_all", skill_result.clear_alls)
        self._apply_player_stack_event(participant, "ability", 1)
        cleared_warning = self._clear_ready_warning(session, participant, defer_next_warning=True)
        self._mark_boss_ability_used(participant, skill)
        bits = []
        if skill_result.damage > 0:
            bits.append(f"{skill_result.damage} 피해")
        if skill_result.hit_damages:
            bits.append(f"{len(skill_result.hit_damages)}타")
        if debuff_count:
            bits.append(f"디버프 {debuff_count}회")
        if skill_result.dispels:
            bits.append(f"디스펠 {skill_result.dispels}회")
        if skill_result.clear_alls:
            bits.append(f"클리어 올 {skill_result.clear_alls}회")
        if skill_heal > 0:
            bits.append(f"{skill_heal} 회복")
        if life_steal_heal > 0:
            bits.append(f"{life_steal_heal} 흡수")
        if not bits:
            bits.append("효과 발동")
        if skill_result.damage > 0:
            self._set_boss_damage_detail(
                participant,
                action=skill.name,
                target=session.boss.name,
                summary=", ".join(bits),
                total_damage=skill_result.damage,
                hit_damages=skill_result.hit_damages,
                detail_lines=skill_result.detail_lines,
            )
        session.log.append(f"{participant.display_name}: {skill.name} · {', '.join(bits)}")
        if session.boss_hp <= 0:
            session.completed = True
            self._grant_boss_session_rewards(session)
            return True, "어빌리티로 보스를 클리어했습니다."
        if cleared_warning:
            return True, f"{skill.name} 사용: {', '.join(bits)} · 전조 해제"
        if not had_warning and participant.pending_warning is not None:
            return True, f"전조가 발생했습니다. {skill.name} 사용: {', '.join(bits)}"
        return True, f"{skill.name} 사용: {', '.join(bits)}"

    def _boss_attack(self, session: BossSession, user_id: int, display_name: str) -> tuple[bool, str]:
        participant = session.participants.get(user_id)
        if participant is None:
            return False, "이 보스전에 참가하지 않았습니다."
        if not session.started:
            return False, "아직 보스전이 시작되지 않았습니다."
        if session.completed:
            return False, "이미 클리어된 보스전입니다."
        if session.failed:
            return False, "이미 실패한 보스전입니다."
        if session.cancelled:
            return False, "이미 취소된 보스전입니다."
        if not participant.alive:
            return False, "전투 불능 상태입니다."

        profile = self.service.get_profile(user_id, display_name)
        player_base = self.service.profile_stats(profile)
        player_stats = self.service._stats_with_effects(player_base, participant.player_effects, participant.player_stack_effects)
        boss_base = self.service._enemy_stats(session.boss.stats)
        boss_stats = self.service._stats_with_effects(boss_base, participant.boss_effects, participant.boss_stack_effects)

        attack = self.service._basic_attack(
            player_stats,
            participant.hp,
            boss_stats,
            session.boss_hp,
            self.service._effects_with_stacks(participant.player_effects, participant.player_stack_effects),
        )
        actual_dealt_damage = self._apply_boss_damage(session, participant, attack.damage)
        dealt_segments = self.service._clamped_damage_segments(attack.life_steal_segments, actual_dealt_damage)
        attack.heal = self._apply_participant_life_steal(
            participant,
            player_stats,
            sum(dealt_segments),
            dealt_segments,
        )
        attack_summary = self.service._attack_log_text(attack)
        self._set_boss_damage_detail(
            participant,
            action="공격",
            target=session.boss.name,
            summary=attack_summary,
            total_damage=attack.damage,
            hit_damages=attack.hit_damages,
            ability_damage=attack.ability_damage,
            detail_lines=attack.detail_lines,
        )
        self._add_warning_progress(participant, "damage", attack.damage)
        self._add_warning_progress(participant, "ability_damage", attack.ability_damage)
        self._add_warning_hit_progress(participant, attack.hit_damages)
        self._add_warning_progress(participant, "triple_attack", attack.triple_attacks)
        self._add_warning_progress(participant, "double_attack", attack.double_attacks)
        self._apply_player_stack_event(participant, "damage", attack.damage)
        self._apply_player_stack_event(participant, "ability_damage", attack.ability_damage)
        self._apply_player_stack_event(participant, "hits", hit_damages=attack.hit_damages)
        self._apply_player_stack_event(participant, "triple_attack", attack.triple_attacks)
        self._apply_player_stack_event(participant, "double_attack", attack.double_attacks)
        session.log.append(f"{participant.display_name}: 공격 {attack_summary}")

        if session.boss_hp <= 0:
            session.completed = True
            self._grant_boss_session_rewards(session)
            return True, "보스를 클리어했습니다."

        if participant.pending_warning is not None:
            return self._finish_pending_warning_turn(
                session,
                participant,
                profile,
                boss_base,
                player_stats,
                "공격",
            )

        boss_stats = self.service._stats_with_effects(boss_base, participant.boss_effects, participant.boss_stack_effects)
        player_stats = self.service._stats_with_effects(player_base, participant.player_effects, participant.player_stack_effects)
        counter_attack = self.service._basic_attack(
            boss_stats,
            session.boss_hp,
            player_stats,
            participant.hp,
            self.service._effects_with_stacks(participant.boss_effects, participant.boss_stack_effects),
            0.48,
        )
        dealt_segments = self.service._clamped_damage_segments(counter_attack.life_steal_segments, participant.hp)
        participant.hp = max(0, participant.hp - counter_attack.damage)
        counter_attack.heal = self._apply_boss_life_steal(
            session,
            boss_stats,
            self.service._effects_with_stacks(participant.boss_effects, participant.boss_stack_effects),
            sum(dealt_segments),
            dealt_segments,
        )
        self._apply_boss_stack_event(participant, "damage", counter_attack.damage)
        self._apply_boss_stack_event(participant, "ability_damage", counter_attack.ability_damage)
        self._apply_boss_stack_event(participant, "hits", hit_damages=counter_attack.hit_damages)
        self._apply_boss_stack_event(participant, "triple_attack", counter_attack.triple_attacks)
        self._apply_boss_stack_event(participant, "double_attack", counter_attack.double_attacks)
        self._add_boss_received_damage_detail(
            participant,
            action="공격",
            source=session.boss.name,
            summary=f"{self.service._attack_log_text(counter_attack)} 반격",
            total_damage=counter_attack.damage,
            hit_damages=counter_attack.hit_damages,
            detail_lines=counter_attack.detail_lines,
        )
        session.log.append(
            f"{session.boss.name}: {participant.display_name}에게 "
            f"{self.service._attack_log_text(counter_attack)} 반격"
        )
        if participant.hp <= 0:
            participant.alive = False
            session.log.append(f"{participant.display_name}: 전투 불능")
            self._check_boss_party_failed(session)
            return True, "전투 불능 상태가 되었습니다."

        self._advance_ct(session, participant, False)
        self._finish_boss_turn(session, participant, profile)
        self._check_boss_party_failed(session)
        return True, "턴을 진행했습니다."

    def _boss_guard(self, session: BossSession, user_id: int, display_name: str) -> tuple[bool, str]:
        participant = session.participants.get(user_id)
        if participant is None:
            return False, "이 보스전에 참가하지 않았습니다."
        if not session.started:
            return False, "아직 보스전이 시작되지 않았습니다."
        if session.completed:
            return False, "이미 클리어된 보스전입니다."
        if session.failed:
            return False, "이미 실패한 보스전입니다."
        if session.cancelled:
            return False, "이미 취소된 보스전입니다."
        if not participant.alive:
            return False, "전투 불능 상태입니다."

        profile = self.service.get_profile(user_id, display_name)

        player_base = self.service.profile_stats(profile)
        boss_base = self.service._enemy_stats(session.boss.stats)
        boss_stats = self.service._stats_with_effects(boss_base, participant.boss_effects, participant.boss_stack_effects)
        guard_stats = self.service._stats_with_effects(player_base, participant.player_effects, participant.player_stack_effects)
        self.service._apply_stat(guard_stats, "defense", 10.0)
        session.log.append(f"{participant.display_name}: 가드")

        if participant.pending_warning is not None:
            return self._finish_pending_warning_turn(
                session,
                participant,
                profile,
                boss_base,
                guard_stats,
                "가드",
            )

        counter_attack = self.service._basic_attack(
            boss_stats,
            session.boss_hp,
            guard_stats,
            participant.hp,
            self.service._effects_with_stacks(participant.boss_effects, participant.boss_stack_effects),
            0.48,
        )
        dealt_segments = self.service._clamped_damage_segments(counter_attack.life_steal_segments, participant.hp)
        participant.hp = max(0, participant.hp - counter_attack.damage)
        counter_attack.heal = self._apply_boss_life_steal(
            session,
            boss_stats,
            self.service._effects_with_stacks(participant.boss_effects, participant.boss_stack_effects),
            sum(dealt_segments),
            dealt_segments,
        )
        self._apply_boss_stack_event(participant, "damage", counter_attack.damage)
        self._apply_boss_stack_event(participant, "ability_damage", counter_attack.ability_damage)
        self._apply_boss_stack_event(participant, "hits", hit_damages=counter_attack.hit_damages)
        self._apply_boss_stack_event(participant, "triple_attack", counter_attack.triple_attacks)
        self._apply_boss_stack_event(participant, "double_attack", counter_attack.double_attacks)
        self._add_boss_received_damage_detail(
            participant,
            action="가드",
            source=session.boss.name,
            summary=f"가드 중 {self.service._attack_log_text(counter_attack)}",
            total_damage=counter_attack.damage,
            hit_damages=counter_attack.hit_damages,
            detail_lines=counter_attack.detail_lines,
        )
        session.log.append(
            f"{session.boss.name}: 가드 중 {participant.display_name}에게 "
            f"{self.service._attack_log_text(counter_attack)}"
        )
        if participant.hp <= 0:
            participant.alive = False
            session.log.append(f"{participant.display_name}: 전투 불능")
            self._check_boss_party_failed(session)
            return True, "전투 불능 상태가 되었습니다."

        self._advance_ct(session, participant, False)
        self._finish_boss_turn(session, participant, profile)
        self._check_boss_party_failed(session)
        return True, "가드로 턴을 넘겼습니다."

    def _finish_pending_warning_turn(
        self,
        session: BossSession,
        participant: BossParticipant,
        profile: PlayerProfile,
        boss_base,
        defender_stats,
        action_name: str,
    ) -> tuple[bool, str]:
        warning = participant.pending_warning
        if warning is None:
            return True, "전조 없음"

        resolved_ct_warning = warning.source == "ct"
        if self._warning_complete(warning):
            session.log.append(f"{participant.display_name}: {warning.name} 전조 달성")
            self._apply_warning_stack_event(participant, "warning_success")
            participant.pending_warning = None
            if action_name == "공격":
                if resolved_ct_warning:
                    participant.ct = 0
                boss_stats = self.service._stats_with_effects(boss_base, participant.boss_effects, participant.boss_stack_effects)
                counter_attack = self.service._basic_attack(
                    boss_stats,
                    session.boss_hp,
                    defender_stats,
                    participant.hp,
                    self.service._effects_with_stacks(participant.boss_effects, participant.boss_stack_effects),
                    0.48,
                )
                dealt_segments = self.service._clamped_damage_segments(counter_attack.life_steal_segments, participant.hp)
                participant.hp = max(0, participant.hp - counter_attack.damage)
                counter_attack.heal = self._apply_boss_life_steal(
                    session,
                    boss_stats,
                    self.service._effects_with_stacks(participant.boss_effects, participant.boss_stack_effects),
                    sum(dealt_segments),
                    dealt_segments,
                )
                self._apply_boss_stack_event(participant, "damage", counter_attack.damage)
                self._apply_boss_stack_event(participant, "ability_damage", counter_attack.ability_damage)
                self._apply_boss_stack_event(participant, "hits", hit_damages=counter_attack.hit_damages)
                self._apply_boss_stack_event(participant, "triple_attack", counter_attack.triple_attacks)
                self._apply_boss_stack_event(participant, "double_attack", counter_attack.double_attacks)
                self._add_boss_received_damage_detail(
                    participant,
                    action=action_name,
                    source=session.boss.name,
                    summary=f"{self.service._attack_log_text(counter_attack)} 반격",
                    total_damage=counter_attack.damage,
                    hit_damages=counter_attack.hit_damages,
                    detail_lines=counter_attack.detail_lines,
                )
                session.log.append(
                    f"{session.boss.name}: {participant.display_name}에게 "
                    f"{self.service._attack_log_text(counter_attack)} 반격"
                )
                if participant.hp <= 0:
                    participant.alive = False
                    session.log.append(f"{participant.display_name}: 전투 불능")
                    self._check_boss_party_failed(session)
                    return True, f"{warning.name} 전조를 해제했지만 전투 불능 상태가 되었습니다."
                self._advance_ct(session, participant, False)
            else:
                self._advance_ct(session, participant, resolved_ct_warning)
            self._finish_boss_turn(session, participant, profile)
            self._check_boss_party_failed(session)
            return True, f"{warning.name} 전조를 해제했습니다."

        warning.remaining_turns -= 1
        if warning.remaining_turns > 0:
            session.log.append(
                f"{participant.display_name}: {warning.name} 전조 진행 중 "
                f"({warning.remaining_turns}턴 남음)"
            )
            self._advance_ct(session, participant, False)
            self._finish_boss_turn(session, participant, profile)
            self._check_boss_party_failed(session)
            return True, f"{action_name}: 전조 진행 중입니다. {warning.remaining_turns}턴 남았습니다."

        boss_stats = self.service._stats_with_effects(boss_base, participant.boss_effects, participant.boss_stack_effects)
        boss_effect_lists = self._boss_effect_lists(session)
        boss_stack_lists = self._boss_stack_lists(session)
        boss_effects_before = self._effect_snapshot(participant.boss_effects)
        pattern_hit_damages: list[int] = []
        player_effect_lists = [
            member.player_effects
            for member in session.participants.values()
            if member.alive
        ]
        player_stack_lists = [
            member.player_stack_effects
            for member in session.participants.values()
            if member.alive
        ]
        self._apply_warning_stack_event(participant, "warning_failure")
        failure_pattern = self._warning_failure_pattern(warning, participant)
        failure_effect_name = failure_pattern.name or warning.name
        pattern_damage = self.service._use_boss_pattern(
            failure_pattern,
            boss_stats,
            defender_stats,
            session.boss_hp,
            participant.hp,
            participant.player_effects,
            participant.boss_effects,
            ally_effects=boss_effect_lists,
            opponent_effects=player_effect_lists,
            boss_stack_effects=participant.boss_stack_effects,
            player_stack_effects=participant.player_stack_effects,
            ally_stack_effects=boss_stack_lists,
            opponent_stack_effects=player_stack_lists,
            damage_details=pattern_hit_damages,
        )
        for effects in [*boss_effect_lists, *player_effect_lists]:
            self._dedupe_effects_by_key(effects)
        self._sync_shared_effect_changes(participant.boss_effects, boss_effect_lists, boss_effects_before)
        if pattern_damage > 0:
            dealt_damage = min(participant.hp, pattern_damage)
            participant.hp = max(0, participant.hp - pattern_damage)
            pattern_heal = self._apply_boss_life_steal(
                session,
                boss_stats,
                self.service._effects_with_stacks(participant.boss_effects, participant.boss_stack_effects),
                dealt_damage,
            )
            self._apply_boss_stack_event(participant, "damage", pattern_damage)
            self._apply_boss_stack_event(participant, "hits", hit_damages=pattern_hit_damages)
            heal_text = f", {pattern_heal} 흡수" if pattern_heal > 0 else ""
            self._add_boss_received_damage_detail(
                participant,
                action=action_name,
                source=failure_pattern.name,
                summary=f"{warning.name} 실패, {failure_effect_name} {pattern_damage} 피해{heal_text}",
                total_damage=pattern_damage,
                hit_damages=pattern_hit_damages or [pattern_damage],
                detail_lines=self._boss_pattern_damage_detail_lines(failure_pattern, pattern_hit_damages, pattern_damage),
            )
            session.log.append(
                f"{participant.display_name}: {warning.name} 실패, "
                f"{failure_effect_name} {pattern_damage} 피해{heal_text}"
            )
        else:
            session.log.append(f"{participant.display_name}: {warning.name} 실패, {failure_effect_name} 발동")
        participant.pending_warning = None
        self._advance_ct(session, participant, resolved_ct_warning)
        if participant.hp <= 0:
            participant.alive = False
            self._check_boss_party_failed(session)
            return True, "전조 실패로 전투 불능이 되었습니다."
        self._finish_boss_turn(session, participant, profile)
        self._check_boss_party_failed(session)
        return True, f"{warning.name} 전조 실패 효과가 발동했습니다."

    def _prepare_visible_warning(self, session: BossSession, participant: BossParticipant, profile: PlayerProfile | None = None) -> None:
        if participant.pending_warning is not None or session.completed or session.failed:
            return
        if participant.suppress_warning_activation:
            return
        if self._trigger_due_hp_effect(session, participant, profile):
            self._check_boss_party_failed(session)
            if participant.hp <= 0 or session.failed:
                return
        self._queue_due_hp_warnings(session, participant, profile)
        self._queue_ct_warning(session, participant, profile)
        self._activate_next_warning(session, participant)

    def _trigger_due_hp_effect(
        self,
        session: BossSession,
        participant: BossParticipant,
        profile: PlayerProfile | None = None,
    ) -> bool:
        if not session.boss.hp_effects or session.completed or session.failed or not participant.alive:
            return False
        ratio = self._boss_hp_ratio(session)
        due = [
            (idx, effect)
            for idx, effect in enumerate(session.boss.hp_effects)
            if idx not in participant.triggered_hp_effects and ratio <= effect.threshold
        ]
        if not due:
            return False
        _selected_idx, selected = min(due, key=lambda row: (row[1].threshold, row[0]))
        for idx, _effect in due:
            participant.triggered_hp_effects.add(idx)
        self._apply_hp_instant_effect(session, participant, profile, selected.pattern)
        return True

    def _apply_hp_instant_effect(
        self,
        session: BossSession,
        participant: BossParticipant,
        profile: PlayerProfile | None,
        pattern: BossPattern,
    ) -> None:
        if profile is None:
            profile = self.service.get_profile(participant.user_id, participant.display_name)
        boss_base = self.service._enemy_stats(session.boss.stats)
        player_base = self.service.profile_stats(profile)
        boss_stats = self.service._stats_with_effects(boss_base, participant.boss_effects, participant.boss_stack_effects)
        player_stats = self.service._stats_with_effects(player_base, participant.player_effects, participant.player_stack_effects)
        boss_effect_lists = self._boss_effect_lists(session)
        boss_stack_lists = self._boss_stack_lists(session)
        boss_effects_before = self._effect_snapshot(participant.boss_effects)
        player_effect_lists = [
            member.player_effects
            for member in session.participants.values()
            if member.alive
        ]
        player_stack_lists = [
            member.player_stack_effects
            for member in session.participants.values()
            if member.alive
        ]
        hit_damages: list[int] = []
        damage = self.service._use_boss_pattern(
            pattern,
            boss_stats,
            player_stats,
            session.boss_hp,
            participant.hp,
            participant.player_effects,
            participant.boss_effects,
            ally_effects=boss_effect_lists,
            opponent_effects=player_effect_lists,
            boss_stack_effects=participant.boss_stack_effects,
            player_stack_effects=participant.player_stack_effects,
            ally_stack_effects=boss_stack_lists,
            opponent_stack_effects=player_stack_lists,
            damage_details=hit_damages,
        )
        for effects in [*boss_effect_lists, *player_effect_lists]:
            self._dedupe_effects_by_key(effects)
        self._sync_shared_effect_changes(participant.boss_effects, boss_effect_lists, boss_effects_before)
        effect_name = pattern.name or "HP 즉시 효과"
        if damage > 0:
            dealt_damage = min(participant.hp, damage)
            participant.hp = max(0, participant.hp - damage)
            pattern_heal = self._apply_boss_life_steal(
                session,
                boss_stats,
                self.service._effects_with_stacks(participant.boss_effects, participant.boss_stack_effects),
                dealt_damage,
            )
            self._apply_boss_stack_event(participant, "damage", damage)
            self._apply_boss_stack_event(participant, "hits", hit_damages=hit_damages)
            heal_text = f", {pattern_heal} 흡수" if pattern_heal > 0 else ""
            self._add_boss_received_damage_detail(
                participant,
                action="HP 즉시 효과",
                source=effect_name,
                summary=f"{effect_name} {damage} 피해{heal_text}",
                total_damage=damage,
                hit_damages=hit_damages or [damage],
                detail_lines=self._boss_pattern_damage_detail_lines(pattern, hit_damages, damage),
            )
            session.log.append(f"{participant.display_name}: {effect_name} 즉시 발동, {damage} 피해{heal_text}")
        else:
            session.log.append(f"{participant.display_name}: {effect_name} 즉시 발동")
        if participant.hp <= 0:
            participant.alive = False
            session.log.append(f"{participant.display_name}: 전투 불능")

    def _queue_due_hp_warnings(self, session: BossSession, participant: BossParticipant, profile: PlayerProfile | None = None) -> None:
        if session.completed or session.failed:
            return
        ratio = self._boss_hp_ratio(session)
        for idx, rule in enumerate(session.boss.hp_warnings):
            if idx in participant.triggered_thresholds:
                continue
            if ratio <= rule.threshold:
                participant.triggered_thresholds.add(idx)
                participant.queued_warnings.append(self._hp_warning(session, idx, rule))

    def _queue_ct_warning(self, session: BossSession, participant: BossParticipant, profile: PlayerProfile | None = None) -> None:
        if session.completed or session.failed:
            return
        if self._has_ct_warning(participant):
            return
        if participant.ct >= self._current_ct_max(session):
            participant.queued_warnings.append(self._ct_warning(session, profile))

    def _activate_next_warning(self, session: BossSession, participant: BossParticipant) -> None:
        if participant.pending_warning is not None or not participant.queued_warnings:
            return
        hp_indices = [
            idx for idx, warning in enumerate(participant.queued_warnings)
            if warning.source.startswith("hp:")
        ]
        if hp_indices:
            idx = hp_indices[-1]
        else:
            idx = 0
        warning = participant.queued_warnings.pop(idx)
        participant.pending_warning = warning
        kind = "체력" if warning.source.startswith("hp:") else "CT"
        session.log.append(f"{participant.display_name}: {kind} 전조 {warning.name}")

    def _finish_boss_turn(self, session: BossSession, participant: BossParticipant, profile: PlayerProfile) -> None:
        self._release_pending_hp_locks(session, participant)
        participant.player_effects = self.service._tick_effects(participant.player_effects)
        participant.boss_effects = self.service._tick_effects(participant.boss_effects)
        self._tick_ability_cooldowns(participant)
        participant.suppress_warning_activation = False
        if self._trigger_due_hp_effect(session, participant, profile):
            self._check_boss_party_failed(session)
            if participant.hp <= 0 or session.failed:
                return
        self._queue_due_hp_warnings(session, participant, profile)
        self._queue_ct_warning(session, participant, profile)
        self._activate_next_warning(session, participant)

    def _hp_warning(self, session: BossSession, idx: int, rule) -> BossWarning:
        template = rule.warning or self._warning_for_trigger(session, rule.warning_id)
        pattern = template.pattern or self._pattern_for_warning(session, template.pattern_id)
        return BossWarning(
            source=f"hp:{idx}",
            name=f"{template.name} ({rule.threshold * 100:.0f}%)",
            pattern=pattern,
            objectives=self._warning_objective_progress(template),
            threshold=rule.threshold,
            remaining_turns=max(1, int(getattr(template, "turns", 1))),
            failure_variants=list(getattr(template, "failure_variants", [])),
        )

    def _ct_warning(self, session: BossSession, profile: PlayerProfile | None = None) -> BossWarning:
        rule = self._current_ct_warning(session)
        if rule is None:
            pattern = session.boss.patterns[0] if session.boss.patterns else BossPattern(0.0, f"{session.boss.name} CT")
            name = pattern.name
            objectives = [BossWarningObjectiveProgress("hits", 1)]
        else:
            template = rule.warning or self._warning_for_trigger(session, rule.warning_id)
            pattern = template.pattern or self._pattern_for_warning(session, template.pattern_id)
            name = template.name
            objectives = self._warning_objective_progress(template)
        return BossWarning(
            source="ct",
            name=name,
            pattern=pattern,
            objectives=objectives,
            remaining_turns=max(1, int(getattr(template, "turns", 1))) if rule is not None else 1,
            failure_variants=list(getattr(template, "failure_variants", [])) if rule is not None else [],
        )

    def _warning_for_trigger(self, session: BossSession, warning_id: str):
        warning = session.boss.warning_by_id.get(warning_id)
        if warning is not None:
            return warning
        pattern = self._pattern_for_warning(session, warning_id)
        return BossWarningTemplate(
            id=warning_id,
            name=pattern.name,
            pattern_id=pattern.id or warning_id,
            pattern=pattern,
            objectives=[],
        )

    def _warning_objective_progress(self, template) -> list[BossWarningObjectiveProgress]:
        objectives = getattr(template, "objectives", []) or []
        return [
            BossWarningObjectiveProgress(
                objective=str(objective.objective),
                required=max(1, int(objective.required)),
                min_damage=max(0, int(getattr(objective, "min_damage", 0))),
            )
            for objective in objectives
        ] or [BossWarningObjectiveProgress("hits", 1)]

    def _pattern_for_warning(self, session: BossSession, pattern_id: str) -> BossPattern:
        pattern = session.boss.pattern_by_id.get(pattern_id)
        if pattern is not None:
            return pattern
        for candidate in session.boss.patterns:
            if candidate.id == pattern_id or candidate.name == pattern_id:
                return candidate
        if session.boss.patterns:
            return session.boss.patterns[0]
        return BossPattern(0.0, pattern_id or session.boss.name)

    def _boss_hp_ratio(self, session: BossSession) -> float:
        return session.boss_hp / max(1, session.boss_max_hp)

    def _boss_hp_lock_value(self, session: BossSession, threshold: float) -> int:
        return max(1, min(session.boss_max_hp, ceil(session.boss_max_hp * threshold)))

    def _current_boss_hp_lock(self, session: BossSession, participant: BossParticipant) -> tuple[int, float, int] | None:
        for index, threshold in enumerate(session.boss.hp_locks):
            if index in participant.unlocked_hp_locks:
                continue
            hp_limit = self._boss_hp_lock_value(session, threshold)
            if session.boss_hp > hp_limit or (index in participant.pending_hp_locks and session.boss_hp >= hp_limit):
                return index, threshold, hp_limit
            if session.boss_hp == hp_limit:
                return index, threshold, hp_limit
        return None

    def _apply_boss_damage(self, session: BossSession, participant: BossParticipant, damage: int) -> int:
        damage = max(0, int(damage))
        if damage <= 0 or session.boss_hp <= 0:
            return 0
        before = session.boss_hp
        after = max(0, before - damage)
        hp_lock = self._current_boss_hp_lock(session, participant)
        if hp_lock is not None:
            index, _threshold, hp_limit = hp_lock
            if before == hp_limit:
                after = hp_limit
                participant.pending_hp_locks.add(index)
            if before > hp_limit and after <= hp_limit:
                after = hp_limit
                participant.pending_hp_locks.add(index)
            elif index in participant.pending_hp_locks and before >= hp_limit and after < hp_limit:
                after = hp_limit
        session.boss_hp = after
        return max(0, before - after)

    def _release_pending_hp_locks(self, session: BossSession, participant: BossParticipant) -> None:
        hp_lock = self._current_boss_hp_lock(session, participant)
        if hp_lock is not None:
            index, _threshold, hp_limit = hp_lock
            if session.boss_hp == hp_limit:
                participant.pending_hp_locks.add(index)
        if not participant.pending_hp_locks:
            return
        participant.unlocked_hp_locks.update(participant.pending_hp_locks)
        participant.pending_hp_locks.clear()

    def _boss_hp_lock_text(self, session: BossSession, participant: BossParticipant) -> str:
        hp_lock = self._current_boss_hp_lock(session, participant)
        if hp_lock is None:
            return ""
        _index, threshold, _hp_limit = hp_lock
        percent = threshold * 100
        if abs(percent - round(percent)) < 0.001:
            percent_text = str(int(round(percent)))
        else:
            percent_text = f"{percent:.1f}".rstrip("0").rstrip(".")
        return f"{percent_text}% 미만 불가"

    def _current_ct_max(self, session: BossSession) -> int:
        ratio = self._boss_hp_ratio(session)
        for rule in session.boss.ct_gauge:
            if ratio >= rule.above:
                return rule.max
        return session.ct_max

    def _current_ct_warning(self, session: BossSession):
        ratio = self._boss_hp_ratio(session)
        if not session.boss.ct_warnings:
            return None
        candidates = [
            rule for rule in session.boss.ct_warnings
            if ratio <= rule.above
        ]
        if candidates:
            return min(candidates, key=lambda rule: rule.above)
        return max(session.boss.ct_warnings, key=lambda rule: rule.above)

    def _has_ct_warning(self, participant: BossParticipant) -> bool:
        if participant.pending_warning is not None and participant.pending_warning.source == "ct":
            return True
        return any(warning.source == "ct" for warning in participant.queued_warnings)

    def _advance_ct(self, session: BossSession, participant: BossParticipant, resolved_ct_warning: bool) -> None:
        if resolved_ct_warning:
            participant.ct = 0
            return
        participant.ct = min(self._current_ct_max(session), participant.ct + 1)

    def _debuff_effect_count(self, skill: SkillTemplate) -> int:
        count = sum(
            1
            for effect in skill.enemy_stat_effects
            if float(effect.value) < 0
        )
        return count if count > 0 else (1 if any(value < 0 for value in skill.enemy_mods.values()) else 0)

    def _apply_participant_life_steal(
        self,
        participant: BossParticipant,
        stats,
        dealt_damage: int,
        damage_segments: list[int] | None = None,
    ) -> int:
        segments = damage_segments if damage_segments is not None else ([dealt_damage] if dealt_damage > 0 else [])
        heal = self.service._life_steal_heal_segments(
            stats,
            self.service._effects_with_stacks(participant.player_effects, participant.player_stack_effects),
            segments,
            stats.final_hp,
        )
        if heal > 0:
            participant.hp = min(stats.final_hp, participant.hp + heal)
        return heal

    def _apply_boss_skill_heal(
        self,
        session: BossSession,
        participant: BossParticipant,
        skill: SkillTemplate,
        raw_heal: int,
    ) -> int:
        if skill.heal_power <= 0 or raw_heal <= 0:
            return 0
        targets = [
            ally for ally in session.participants.values()
            if ally.alive
        ] if skill.heal_target == "allies" else [participant]
        total_heal = 0
        for target in targets:
            profile = self.service.get_profile(target.user_id, target.display_name)
            stats = self.service._stats_with_effects(
                self.service.profile_stats(profile),
                target.player_effects,
                target.player_stack_effects,
            )
            heal = self.service._apply_heal_cap(raw_heal, skill.heal_cap, stats.final_hp)
            if heal <= 0:
                continue
            before = target.hp
            target.hp = min(stats.final_hp, target.hp + heal)
            total_heal += max(0, target.hp - before)
        return total_heal

    def _apply_boss_life_steal(
        self,
        session: BossSession,
        stats,
        effects: list[ActiveEffect],
        dealt_damage: int,
        damage_segments: list[int] | None = None,
    ) -> int:
        segments = damage_segments if damage_segments is not None else ([dealt_damage] if dealt_damage > 0 else [])
        heal = self.service._life_steal_heal_segments(
            stats,
            effects,
            segments,
            stats.final_hp,
        )
        if heal > 0:
            session.boss_hp = min(stats.final_hp, session.boss_hp + heal)
        return heal

    def _clear_ready_warning(
        self,
        session: BossSession,
        participant: BossParticipant,
        *,
        defer_next_warning: bool = False,
    ) -> bool:
        warning = participant.pending_warning
        if warning is None or not self._warning_complete(warning):
            return False
        session.log.append(f"{participant.display_name}: {warning.name} 전조 해제")
        self._apply_warning_stack_event(participant, "warning_success")
        participant.pending_warning = None
        if warning.source == "ct":
            participant.ct = 0
        if defer_next_warning:
            participant.suppress_warning_activation = True
        else:
            self._activate_next_warning(session, participant)
        return True

    def _add_warning_progress(self, participant: BossParticipant, objective: str, amount: int) -> None:
        warning = participant.pending_warning
        if warning is None or amount <= 0:
            return
        for progress in warning.objectives:
            if progress.objective == objective:
                progress.progress = min(progress.required, progress.progress + amount)

    def _add_warning_hit_progress(self, participant: BossParticipant, hit_damages: list[int]) -> None:
        warning = participant.pending_warning
        if warning is None or not hit_damages:
            return
        for progress in warning.objectives:
            if progress.objective != "hits":
                continue
            amount = sum(1 for damage in hit_damages if damage >= progress.min_damage)
            if amount > 0:
                progress.progress = min(progress.required, progress.progress + amount)

    def _warning_complete(self, warning: BossWarning) -> bool:
        return all(progress.progress >= progress.required for progress in warning.objectives)

    def _warning_failure_pattern(self, warning: BossWarning, participant: BossParticipant) -> BossPattern:
        for variant in warning.failure_variants:
            if self._warning_failure_variant_matches(variant, participant):
                return variant.pattern
        return warning.pattern

    def _warning_failure_variant_matches(
        self,
        variant: BossWarningFailureVariant,
        participant: BossParticipant,
    ) -> bool:
        if not variant.conditions:
            return False
        for condition in variant.conditions:
            stacks = participant.player_stack_effects if condition.target == "player" else participant.boss_stack_effects
            current = self._stack_count(stacks, condition.stack_effect_id)
            if current < condition.min_stacks:
                return False
            if condition.max_stacks >= 0 and current > condition.max_stacks:
                return False
        return True

    def _stack_count(self, stacks: list[ActiveStackEffect], template_id: str) -> int:
        for stack in stacks:
            if stack.template_id == template_id:
                return max(0, stack.stacks)
        return 0

    def _boss_pattern_damage_detail_lines(
        self,
        pattern: BossPattern,
        hit_damages: list[int],
        total_damage: int,
    ) -> list[str]:
        lines: list[str] = []
        if hit_damages:
            lines.append(f"{pattern.name}: {', '.join(str(damage) for damage in hit_damages)}")
        hit_total = sum(hit_damages)
        plain_damage = max(0, total_damage - hit_total)
        if plain_damage > 0:
            lines.append(f"무속성 데미지: {plain_damage}")
        return lines or [f"{pattern.name}: {total_damage}"]

    def _warning_progress_text(self, warning: BossWarning) -> str:
        if not warning.objectives:
            return "조건 없음"
        parts = []
        for progress in warning.objectives:
            label = OBJECTIVE_LABELS.get(progress.objective, progress.objective)
            if progress.objective == "hits" and progress.min_damage > 0:
                label = f"{progress.min_damage} 데미지 이상의 타수"
            parts.append(f"{label} {progress.progress}/{progress.required}")
        parts.append(f"남은 턴 {warning.remaining_turns}")
        return " · ".join(parts)

    def _warning_display_text(self, warning: BossWarning, participant: BossParticipant | None = None) -> str:
        failure_pattern = self._warning_failure_pattern(warning, participant) if participant is not None else warning.pattern
        failure = self._boss_pattern_effect_summary(failure_pattern)
        variant_text = "" if participant is not None else (
            f"\n스택 조건부 실패 효과: {len(warning.failure_variants)}개" if warning.failure_variants else ""
        )
        return (
            f"{warning.name}\n"
            f"조건: {self._warning_progress_text(warning)}\n"
            f"실패 시: {failure}{variant_text}"
        )

    def _boss_pattern_effect_summary(self, pattern: BossPattern) -> str:
        parts: list[str] = []
        if pattern.damage_multiplier > 0 and pattern.hits > 0:
            parts.append(f"{pattern.damage_multiplier * 100:.0f}% 데미지 x {pattern.hits}회")
        plain_damage = getattr(pattern, "plain_damage", None)
        if plain_damage is not None and plain_damage.has_damage:
            if plain_damage.mode == "target_max_hp_ratio":
                parts.append(f"최대 HP {plain_damage.value * 100:.1f}% 무속성 데미지")
            else:
                parts.append(f"무속성 데미지 {plain_damage.value:g}")
        parts.extend(
            self._pattern_stat_effect_parts(
                pattern.player_stat_effects,
                pattern.player_mods,
                self_label="대상 유저",
                allies_label="참전자 모두",
            )
        )
        parts.extend(
            self._pattern_stat_effect_parts(
                pattern.boss_stat_effects,
                pattern.boss_mods,
                self_label="보스",
                allies_label="보스(참전자 공유)",
            )
        )
        parts.extend(self._pattern_special_effect_parts("대상 유저", "참전자 모두", pattern.player_effects))
        parts.extend(self._pattern_special_effect_parts("보스", "보스(참전자 공유)", pattern.boss_effects))
        action_summary = self._boss_pattern_action_summary(pattern.effect_actions)
        if action_summary:
            parts.append(action_summary)
        return " · ".join(parts) if parts else "효과 없음"

    def _pattern_stat_effect_parts(
        self,
        effects,
        legacy_mods: dict[str, float],
        *,
        self_label: str,
        allies_label: str,
    ) -> list[str]:
        if not effects:
            return [f"{self_label} {self.service.format_stats(legacy_mods, signed=True)}"] if legacy_mods else []
        parts: list[str] = []
        for effect in effects:
            if not effect.stat or not effect.value:
                continue
            target = allies_label if effect.target == "allies" else self_label
            stat_text = self.service.format_stats({effect.stat: effect.value}, signed=True)
            extras = [self._effect_duration_from_raw_text(effect.duration)]
            cap_text = self.service._heal_cap_summary(effect.heal_cap)
            if effect.stat == "life_steal" and cap_text:
                extras.append(f"흡수 상한 {cap_text}")
            if effect.undispellable:
                extras.append("소거불가")
            parts.append(f"{target} {stat_text} ({', '.join(extras)})")
        return parts

    def _pattern_special_effect_parts(self, self_label: str, allies_label: str, effects) -> list[str]:
        parts: list[str] = []
        if effects.flurry is not None:
            parts.append(
                self._pattern_special_effect_text(
                    allies_label if effects.flurry.target == "allies" else self_label,
                    f"난격 {effects.flurry.count}",
                    effects.flurry.duration,
                    effects.flurry.undispellable,
                )
            )
        if effects.double_strike is not None:
            parts.append(
                self._pattern_special_effect_text(
                    allies_label if effects.double_strike.target == "allies" else self_label,
                    f"재행동 {effects.double_strike.count}회",
                    effects.double_strike.duration,
                    effects.double_strike.undispellable,
                )
            )
        for bonus in effects.bonus_damage:
            parts.append(
                self._pattern_special_effect_text(
                    allies_label if bonus.target == "allies" else self_label,
                    f"추격 {bonus.ratio * 100:.0f}%",
                    bonus.duration,
                    bonus.undispellable,
                )
            )
        for reinforce in effects.critical_reinforce:
            parts.append(
                self._pattern_special_effect_text(
                    allies_label if reinforce.target == "allies" else self_label,
                    f"크리 리인포스 {reinforce.ratio * 100:.0f}%",
                    reinforce.duration,
                    reinforce.undispellable,
                )
            )
        for final_effect in effects.final_damage:
            parts.append(
                self._pattern_special_effect_text(
                    allies_label if final_effect.target == "allies" else self_label,
                    f"최종 데미지 {self.service._signed_effect_ratio_text(final_effect.ratio)}",
                    final_effect.duration,
                    final_effect.undispellable,
                )
            )
        for post_attack in effects.post_attack_ability_damage:
            parts.append(
                self._pattern_special_effect_text(
                    allies_label if post_attack.target == "allies" else self_label,
                    f"공격 후 어빌 피해 {post_attack.ratio * 100:.0f}% {post_attack.count}타",
                    post_attack.duration,
                    post_attack.undispellable,
                )
            )
        for guard in effects.dispel_guard:
            parts.append(
                self._pattern_guard_effect_text(
                    allies_label if guard.target == "allies" else self_label,
                    "디스펠 가드",
                    guard.duration,
                    guard.count,
                    guard.undispellable,
                )
            )
        for veil in effects.veil:
            parts.append(
                self._pattern_guard_effect_text(
                    allies_label if veil.target == "allies" else self_label,
                    "마운트",
                    veil.duration,
                    veil.count,
                    veil.undispellable,
                )
            )
        return parts

    def _pattern_special_effect_text(self, target_label: str, text: str, duration: int, undispellable: bool) -> str:
        extras = [self._effect_duration_from_raw_text(duration)]
        if undispellable:
            extras.append("소거불가")
        return f"{target_label} {text} ({', '.join(extras)})"

    def _pattern_guard_effect_text(self, target_label: str, text: str, duration: int, count: int, undispellable: bool) -> str:
        extras = [f"{count}회" if count > 0 else self._effect_duration_from_raw_text(duration)]
        if undispellable:
            extras.append("소거불가")
        return f"{target_label} {text} ({', '.join(extras)})"

    def _effect_duration_from_raw_text(self, duration: int) -> str:
        if duration < 0:
            return "무한"
        return f"{max(1, int(duration))}턴"

    def _boss_pattern_action_summary(self, actions) -> str:
        labels = {
            "dispel": "디스펠",
            "clear_all": "클리어 올",
            "stack_increase": "스택 증가",
            "stack_decrease": "스택 감소",
            "stack_set": "스택 지정",
            "stack_remove": "스택 제거",
            "stack_max": "스택 최대",
        }
        targets = {
            "self": "보스",
            "me": "보스",
            "enemy": "대상 유저",
            "ally": "보스",
            "allies": "보스(참전자 공유)",
            "opponent": "대상 유저",
            "opponents": "참전자 모두",
            "enemies": "참전자 모두",
        }
        parts = []
        for action in actions:
            label = labels.get(action.action, action.action)
            target = targets.get(action.target, action.target)
            if action.action.startswith("stack_"):
                parts.append(self._boss_pattern_stack_action_text(action))
            else:
                count = f" x{action.count}" if action.count > 1 else ""
                parts.append(f"{label}({target}{count})")
        return ", ".join(parts)

    def _boss_pattern_stack_action_text(self, action) -> str:
        template = STACK_EFFECT_BY_ID.get(action.stack_effect_id)
        name = template.name if template is not None else "스택"
        value = max(0, int(action.value))
        if action.action == "stack_increase":
            return f"{name} +{value}레벨"
        if action.action == "stack_decrease":
            return f"{name} -{value}레벨"
        if action.action == "stack_set":
            return f"{name} lv.{value}"
        if action.action == "stack_remove":
            return f"{name} 제거"
        if action.action == "stack_max":
            return f"{name} 최대"
        return name

    def _tick_ability_cooldowns(self, participant: BossParticipant) -> None:
        participant.ability_cooldowns = {
            skill_id: turns - 1
            for skill_id, turns in participant.ability_cooldowns.items()
            if turns - 1 > 0
        }

    def _ability_state_text(self, participant: BossParticipant, skill: SkillTemplate, *, cooldown_prefix: bool = False) -> str:
        if self._ability_used_out(participant, skill):
            return "사용 완료"
        cooldown = participant.ability_cooldowns.get(skill.id, 0)
        uses_left = self._ability_uses_left(participant, skill)
        parts: list[str] = []
        if cooldown > 0:
            parts.append(f"쿨 {cooldown}턴" if cooldown_prefix else f"{cooldown}턴")
        if uses_left is not None:
            parts.append(f"{uses_left}회 남음")
        if parts:
            return " · ".join(parts)
        return "사용 가능" if cooldown_prefix else "가능"

    def _grant_boss_session_rewards(self, session: BossSession) -> None:
        if session.rewards:
            return
        if session.practice:
            for participant in session.participants.values():
                session.rewards[participant.user_id] = "보상 없음"
            session.log.append("보스전 종료")
            return
        for participant in session.participants.values():
            if not participant.alive:
                continue
            drop_rate_multiplier = 1.0
            if participant.user_id == session.owner_id:
                ok, message = self.service.consume_boss_start(
                    participant.user_id,
                    participant.display_name,
                    session.boss.id,
                )
                if not ok:
                    session.rewards[participant.user_id] = message
                    continue
                drop_rate_multiplier = 2.0
            reward = self.service.grant_boss_reward(
                participant.user_id,
                participant.display_name,
                session.boss.id,
                victory=True,
                drop_rate_multiplier=drop_rate_multiplier,
            )
            self._add_session_reward_materials(session, reward.materials)
            session.rewards[participant.user_id] = self._reward_text(reward).replace("\n", ", ")
        session.log.append("보스 클리어 보상 지급")

    def _grant_boss_session_failure_rewards(self, session: BossSession) -> None:
        if session.rewards:
            return
        for participant in session.participants.values():
            session.rewards[participant.user_id] = "보상 없음"
        session.log.append("보스 패배: 보상 없음")

    def _add_session_reward_materials(self, session: BossSession, materials: dict[str, int]) -> None:
        for material_id, amount in materials.items():
            session.reward_materials[material_id] = session.reward_materials.get(material_id, 0) + amount

    def _check_boss_party_failed(self, session: BossSession) -> None:
        if session.completed:
            return
        if session.participants and not any(participant.alive for participant in session.participants.values()):
            session.failed = True
            session.log.append("파티 전멸")
            self._grant_boss_session_failure_rewards(session)

    def _boss_effect_lists(self, session: BossSession) -> list[list[ActiveEffect]]:
        return [participant.boss_effects for participant in session.participants.values()]

    def _boss_stack_lists(self, session: BossSession) -> list[list[ActiveStackEffect]]:
        return [participant.boss_stack_effects for participant in session.participants.values()]

    def _apply_player_stack_event(
        self,
        participant: BossParticipant,
        objective: str,
        amount: int = 0,
        *,
        hit_damages: list[int] | None = None,
    ) -> None:
        self.service._apply_stack_conditions(
            participant.player_stack_effects,
            objective=objective,
            amount=amount,
            actor_is_holder=True,
            hit_damages=hit_damages,
        )
        self.service._apply_stack_conditions(
            participant.boss_stack_effects,
            objective=objective,
            amount=amount,
            actor_is_holder=False,
            hit_damages=hit_damages,
        )

    def _apply_boss_stack_event(
        self,
        participant: BossParticipant,
        objective: str,
        amount: int = 0,
        *,
        hit_damages: list[int] | None = None,
    ) -> None:
        self.service._apply_stack_conditions(
            participant.boss_stack_effects,
            objective=objective,
            amount=amount,
            actor_is_holder=True,
            hit_damages=hit_damages,
        )
        self.service._apply_stack_conditions(
            participant.player_stack_effects,
            objective=objective,
            amount=amount,
            actor_is_holder=False,
            hit_damages=hit_damages,
        )

    def _apply_warning_stack_event(self, participant: BossParticipant, objective: str) -> None:
        self.service._apply_stack_conditions(
            participant.player_stack_effects,
            objective=objective,
            amount=1,
            actor_is_holder=True,
        )
        self.service._apply_stack_conditions(
            participant.boss_stack_effects,
            objective=objective,
            amount=1,
            actor_is_holder=True,
        )

    def _effect_snapshot(self, effects: list[ActiveEffect]) -> list[tuple[int, tuple]]:
        return [(id(effect), self._effect_key(effect)) for effect in effects]

    def _effect_key(self, effect: ActiveEffect) -> tuple:
        return (
            effect.source_id,
            tuple(sorted(effect.mods.items())),
            effect.special.flurry,
            effect.special.double_strike,
            tuple(effect.special.bonus_damage),
            tuple(effect.special.critical_reinforce),
            tuple(effect.special.final_damage),
            tuple(effect.special.post_attack_ability_damage),
            tuple(effect.special.dispel_guard),
            tuple(effect.special.veil),
            effect.undispellable,
            effect.heal_cap,
        )

    def _copy_effect(self, effect: ActiveEffect) -> ActiveEffect:
        return ActiveEffect(
            effect.turns,
            dict(effect.mods),
            effect.source_id,
            effect.special,
            effect.undispellable,
            effect.heal_cap,
        )

    def _sync_shared_effect_changes(
        self,
        source: list[ActiveEffect],
        targets: list[list[ActiveEffect]],
        before: list[tuple[int, tuple]],
    ) -> None:
        before_ids = {identity for identity, _key in before}
        after_ids = {id(effect) for effect in source}
        removed_keys = [key for identity, key in before if identity not in after_ids]
        added_effects = [effect for effect in source if id(effect) not in before_ids]
        for target in targets:
            if target is source:
                continue
            for key in removed_keys:
                self._remove_latest_effect_by_key(target, key)
            for effect in added_effects:
                if not any(self._effect_key(existing) == self._effect_key(effect) for existing in target):
                    target.append(self._copy_effect(effect))
            self._dedupe_effects_by_key(target)

    def _dedupe_effects_by_key(self, effects: list[ActiveEffect]) -> None:
        seen: dict[tuple, int] = {}
        deduped: list[ActiveEffect] = []
        for effect in effects:
            key = self._effect_key(effect)
            existing_index = seen.get(key)
            if existing_index is None:
                seen[key] = len(deduped)
                deduped.append(effect)
                continue
            existing = deduped[existing_index]
            turns = self._merged_effect_turns(existing.turns, effect.turns)
            deduped[existing_index] = ActiveEffect(
                turns,
                dict(existing.mods),
                existing.source_id,
                existing.special,
                existing.undispellable,
                existing.heal_cap,
            )
        effects[:] = deduped

    def _merged_effect_turns(self, left: int, right: int) -> int:
        if left < 0 or right < 0:
            return -1
        return max(left, right)

    def _remove_latest_effect_by_key(self, effects: list[ActiveEffect], key: tuple) -> None:
        for index in range(len(effects) - 1, -1, -1):
            if self._effect_key(effects[index]) == key:
                effects.pop(index)
                return

    def _profile_embed(self, profile: PlayerProfile) -> discord.Embed:
        progress, required = self.service.level_progress(profile)
        stats = self.service.profile_stats(profile)
        current_job = self.service.current_job(profile)
        chain = " > ".join(job.name for job in self.service.job_chain(profile))
        next_jobs = self.service.next_jobs(profile)
        embed = discord.Embed(
            title=f"{profile.display_name}의 RPG 프로필",
            color=0x5865F2,
        )
        embed.add_field(
            name="성장",
            value=(
                f"Lv. **{profile.level}** · EXP **{progress}/{required}**\n"
                f"총 EXP {profile.exp} · 골드 {profile.gold}G"
            ),
            inline=False,
        )
        embed.add_field(name="전직", value=f"**{current_job.name}**\n{chain}", inline=False)
        if next_jobs:
            embed.add_field(
                name="다음 전직",
                value=", ".join(f"{job.name}(Lv.{job.level_req})" for job in next_jobs),
                inline=False,
            )
        embed.add_field(
            name="탐색",
            value=f"제한 **{self._explore_limit_text(profile)}**",
            inline=True,
        )
        embed.add_field(
            name="전적",
            value=f"던전 클리어 {profile.dungeon_clear_count} · 보스 클리어 {profile.boss_clear_count}",
            inline=True,
        )
        embed.add_field(name="전투 스탯", value=self.service.format_stats(stats), inline=False)
        skills = self.service.equipped_skills(profile)
        embed.add_field(
            name="장착 어빌리티",
            value=self._trim("\n".join(f"**{skill.name}** · {self.service.skill_summary(skill)}" for skill in skills), 1000) if skills else "없음",
            inline=False,
        )
        equipped = self.service.equipped_items(profile)
        embed.add_field(
            name="장착 장비",
            value="\n".join(self.service.item_title(item) for item in equipped) if equipped else "장비 없음",
            inline=False,
        )
        material_summary = self._material_summary(profile, limit=6)
        if material_summary:
            embed.add_field(name="주요 재료", value=material_summary, inline=False)
        if profile.auto_sell_rarities:
            embed.add_field(
                name="자동판매",
                value=", ".join(RARITY_LABELS[rarity] for rarity in profile.auto_sell_rarities),
                inline=False,
            )
        return embed

    def _explore_embed(self, result: ExploreResult) -> discord.Embed:
        if not result.ok:
            embed = discord.Embed(title="탐색 실패", description=result.message, color=0xED4245)
            embed.set_footer(text=f"탐색 제한 {self._explore_limit_text(result.profile)}")
            return embed
        assert result.dungeon is not None
        assert result.enemy is not None
        rare = " · 희귀 몬스터" if result.enemy.rare else ""
        embed = self._battle_result_embed(
            title=f"{result.dungeon.name} 탐색",
            result=result,
            color=0x57F287 if result.battle and result.battle.won else 0xED4245,
        )
        embed.add_field(
            name="조우",
            value=f"**{result.enemy.name}**{rare}\n{result.enemy.description}",
            inline=False,
        )
        return embed

    def _explore_batch_embed(self, result: ExploreBatchResult) -> discord.Embed:
        if not result.ok:
            embed = discord.Embed(title="일괄 탐색 실패", description=result.message, color=0xED4245)
            embed.set_footer(text=f"탐색 제한 {self._explore_limit_text(result.profile)}")
            return embed
        assert result.dungeon is not None
        wins = sum(1 for row in result.results if row.battle and row.battle.won)
        losses = len(result.results) - wins
        embed = discord.Embed(
            title=f"{result.dungeon.name} 일괄 탐색",
            description=f"{result.message}\n결과: **{wins}승 {losses}패**",
            color=0x57F287 if losses == 0 else 0xFFB84D,
        )
        encounter_counts: dict[str, int] = {}
        rare_count = 0
        total_turns = 0
        for row in result.results:
            if row.enemy is not None:
                encounter_counts[row.enemy.name] = encounter_counts.get(row.enemy.name, 0) + 1
                if row.enemy.rare:
                    rare_count += 1
            if row.battle is not None:
                total_turns += row.battle.turns
        encounter_text = ", ".join(f"{name} x{amount}" for name, amount in encounter_counts.items()) or "없음"
        embed.add_field(
            name="전투",
            value=f"{len(result.results)}회 · 총 {total_turns}턴 · 희귀 조우 {rare_count}회",
            inline=False,
        )
        embed.add_field(name="조우", value=self._trim(encounter_text, 1024), inline=False)
        embed.add_field(name="합산 보상", value=self._explore_batch_reward_text(result.results), inline=False)
        embed.set_footer(text=f"탐색 제한 {self._explore_limit_text(result.profile)}")
        return embed

    def _exploration_panel_embed(self, profile: PlayerProfile, selected_dungeon_id: str | None = None) -> discord.Embed:
        selected = next((dungeon for dungeon in self.service.dungeons() if dungeon.id == selected_dungeon_id), None)
        embed = discord.Embed(
            title="던전 탐색",
            description=f"탐색 제한: **{self._explore_limit_text(profile)}**",
            color=0x4BA3FF,
        )
        if selected is None:
            lines = []
            for dungeon in self.service.dungeons():
                gate = "입장 가능" if profile.level >= dungeon.level_req else f"Lv.{dungeon.level_req} 필요"
                rare_names = ", ".join(enemy.name for enemy in dungeon.enemies if enemy.rare) or "없음"
                lines.append(f"**{dungeon.name}** · {gate} · 희귀 {rare_names}")
            embed.add_field(name="탐색지", value=self._trim("\n".join(lines), 1000), inline=False)
            embed.set_footer(text="아래 메뉴에서 던전을 고른 뒤 탐색 버튼을 누르세요.")
            return embed

        enemy_lines = []
        for enemy in selected.enemies:
            marker = "희귀" if enemy.rare else "일반"
            enemy_lines.append(
                f"`{marker}` **{enemy.name}** · {self.service.reward_summary(enemy.rewards, base_gold=enemy.gold, base_exp=enemy.exp)}"
            )
        gate = "입장 가능" if profile.level >= selected.level_req else f"Lv.{selected.level_req} 필요"
        embed.add_field(
            name=selected.name,
            value=(
                f"{gate}\n"
                f"{self._trim('; '.join(enemy_lines), 700)}\n"
                f"{selected.description}"
            ),
            inline=False,
        )
        embed.add_field(name="출현 몬스터", value=self._trim("\n".join(enemy_lines), 1000), inline=False)
        embed.set_footer(text="탐색 버튼을 누르면 이 메시지가 결과로 갱신됩니다. 7회 탐색은 남은 제한 안에서 진행됩니다.")
        return embed

    def _boss_embed(self, result: BossResult) -> discord.Embed:
        if not result.ok:
            return discord.Embed(title="보스 도전 실패", description=result.message, color=0xED4245)
        assert result.boss is not None
        embed = self._battle_result_embed(
            title=f"{result.boss.name} 도전",
            result=result,
            color=0x57F287 if result.battle and result.battle.won else 0xED4245,
        )
        if result.reward and result.reward.weekly_reward_locked:
            embed.set_footer(text="이번 주 보상은 이미 받았습니다. 클리어 연습 결과만 기록됩니다.")
        return embed

    def _boss_session_embed(self, session: BossSession) -> discord.Embed:
        if session.completed:
            color = 0x57F287
            status = "클리어"
        elif session.failed:
            color = 0xED4245
            status = "실패"
        elif session.cancelled:
            color = 0x6E7681
            status = "취소됨"
        elif session.started:
            color = 0xFFB84D
            status = "진행 중"
        else:
            color = 0x5865F2
            status = "대기 중"
        ct_max = self._current_ct_max(session)
        owner = session.participants.get(session.owner_id)
        owner_name = owner.display_name if owner is not None else "알 수 없음"
        mode_text = "연습" if session.practice else "일반"
        embed = discord.Embed(
            title=f"{session.boss.name} 보스전",
            description=f"상태: **{status}** · {mode_text} · 자발자 {owner_name} · CT {ct_max}",
            color=color,
        )
        embed.add_field(
            name="보스 HP",
            value=(
                f"{self._hp_bar(session.boss_hp, session.boss_max_hp)}\n"
                f"**{session.boss_hp}/{session.boss_max_hp}**"
            ),
            inline=False,
        )
        if session.participants:
            participant_lines = [
                self._participant_public_summary_text(participant, ct_max)
                for participant in session.participants.values()
            ]
            embed.add_field(
                name=f"참가자 {len(session.participants)}명",
                value=self._trim("\n".join(participant_lines), 1200),
                inline=False,
            )
        else:
            embed.add_field(name="참가자", value="없음", inline=False)
        if session.rewards:
            reward_lines = [
                f"**{session.participants[user_id].display_name}**: {text}"
                for user_id, text in session.rewards.items()
                if user_id in session.participants
            ]
            embed.add_field(name="보상", value=self._trim("\n".join(reward_lines), 1000), inline=False)
        if session.log:
            embed.add_field(name="로그", value=self._trim("\n".join(session.log[-8:]), 1200), inline=False)
        return embed

    def _participant_public_summary_text(self, participant: BossParticipant, ct_max: int) -> str:
        state = "전투 불능" if not participant.alive else f"HP {participant.hp}/{participant.max_hp}"
        participant_ct = min(participant.ct, ct_max)
        if participant.pending_warning is not None:
            warning = f"전조 {participant.pending_warning.name}"
        elif participant.queued_warnings:
            warning = f"전조 대기 {len(participant.queued_warnings)}"
        else:
            warning = "전조 없음"
        return f"**{participant.display_name}** · {state} · CT {participant_ct}/{ct_max} · {warning}"

    def _participant_status_text(
        self,
        participant: BossParticipant,
        *,
        include_cooldowns: bool = True,
    ) -> str:
        state = "전투 불능" if not participant.alive else f"HP {participant.hp}/{participant.max_hp}"
        lines = [f"상태: {state}"]
        if include_cooldowns:
            cooldowns = self._participant_ability_cooldown_text(participant, multiline=True)
            lines.append(f"어빌리티 쿨\n{cooldowns}")
        if self._has_visible_effects(participant.player_effects):
            lines.append(
                "버프/디버프\n"
                + self._effects_text(participant.player_effects, limit=520, compact=False)
            )
        player_stacks = self._stack_effects_text(participant.player_stack_effects)
        if player_stacks:
            lines.append("스택\n" + player_stacks)
        return self._trim("\n\n".join(lines), 1000)

    def _participant_boss_state_text(self, participant: BossParticipant, ct_max: int) -> str:
        participant_ct = min(participant.ct, ct_max)
        lines = [f"CT: {participant_ct}/{ct_max}"]
        if participant.pending_warning is not None:
            lines.append("전조\n" + self._warning_display_text(participant.pending_warning, participant))
        else:
            lines.append("전조: 없음")
        if participant.queued_warnings:
            lines.append(f"대기 전조: {len(participant.queued_warnings)}개")
        boss_stacks = self._stack_effects_text(participant.boss_stack_effects)
        if boss_stacks:
            lines.append("보스 스택\n" + boss_stacks)
        return "\n\n".join(lines)

    def _stack_effects_text(self, stacks: list[ActiveStackEffect]) -> str:
        parts = []
        for stack in stacks:
            template = STACK_EFFECT_BY_ID.get(stack.template_id)
            if template is None:
                continue
            stacks_count = max(0, int(stack.stacks))
            if stacks_count <= 0:
                continue
            parts.append(f"{template.name} lv.{stacks_count}")
        return ", ".join(parts)

    def _boss_shared_effects_text(self, session: BossSession, *, limit: int) -> str:
        participants = [participant for participant in session.participants.values() if participant.alive]
        if not participants:
            participants = list(session.participants.values())
        visible = [
            (
                participant.display_name,
                self._effects_text(participant.boss_effects, limit=420, compact=False),
            )
            for participant in participants
            if self._has_visible_effects(participant.boss_effects)
        ]
        if not visible:
            return "없음"
        unique_texts = {text for _, text in visible}
        if len(unique_texts) == 1:
            return self._trim(next(iter(unique_texts)), limit)
        lines = [f"**{name} 기준**\n{text}" for name, text in visible]
        return self._trim("\n\n".join(lines), limit)

    def _participant_ability_cooldown_text(self, participant: BossParticipant, *, multiline: bool = False) -> str:
        profile = self.service.get_profile(participant.user_id, participant.display_name)
        skills = self.service.equipped_skills(profile)
        if not skills:
            return "없음"
        parts = []
        for skill in skills[:MAX_EQUIPPED_SKILLS]:
            state = self._ability_state_text(participant, skill)
            prefix = "- " if multiline else ""
            parts.append(f"{prefix}{skill.name}: {state}")
        return "\n".join(parts) if multiline else ", ".join(parts)

    def _hp_bar(self, current: int, maximum: int, *, width: int = 18) -> str:
        maximum = max(1, maximum)
        filled = round(width * max(0, min(current, maximum)) / maximum)
        return "[" + "#" * filled + "-" * (width - filled) + "]"

    def _boss_ability_embed(
        self,
        session: BossSession,
        participant: BossParticipant,
        skills: list[SkillTemplate],
        message: str | None = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"{session.boss.name} 개인 전투 패널",
            color=0xB56BFF,
        )
        if message:
            embed.description = message
        ct_max = self._current_ct_max(session)
        hp_lock_text = self._boss_hp_lock_text(session, participant)
        embed.add_field(
            name="보스",
            value=self._trim(
                "\n\n".join(
                    [
                        f"{self._hp_bar(session.boss_hp, session.boss_max_hp)}\n"
                        f"**{session.boss_hp}/{session.boss_max_hp}**"
                        + (f"\n{hp_lock_text}" if hp_lock_text else ""),
                        self._participant_boss_state_text(participant, ct_max),
                        "버프/디버프\n" + self._boss_shared_effects_text(session, limit=520),
                    ]
                ),
                1000,
            ),
            inline=False,
        )
        embed.add_field(
            name="내 상태",
            value=self._participant_status_text(
                participant,
                include_cooldowns=False,
            ),
            inline=False,
        )
        lines = []
        for skill in skills:
            state = self._ability_state_text(participant, skill, cooldown_prefix=True)
            lines.append(f"**{skill.name}** · {state}\n{self.service.skill_summary(skill)}")
        embed.add_field(
            name="장착 어빌리티",
            value=self._trim("\n\n".join(lines), 1200) if lines else "없음",
            inline=False,
        )
        return embed

    def _boss_damage_detail_embed(
        self,
        session: BossSession,
        participant: BossParticipant | None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=f"{session.boss.name} 딜 상세",
            color=0xFEE75C,
        )
        if participant is None:
            embed.description = "이 보스전에 참가하지 않았습니다."
            return embed
        detail = participant.last_damage_detail
        if detail is None:
            embed.description = "아직 표시할 피해 기록이 없습니다. 공격하거나 피해 어빌리티를 사용하면 여기에 갱신됩니다."
            return embed
        embed.description = f"최근 행동: **{detail.action}**"
        if detail.total_damage > 0:
            embed.add_field(
                name=f"준 피해 → {detail.target}",
                value=self._damage_summary_text(
                    detail.total_damage,
                    detail.hit_damages,
                    ability_damage=detail.ability_damage,
                ),
                inline=False,
            )
            embed.add_field(name="준 피해 로그", value=detail.summary, inline=False)
            embed.add_field(
                name="준 피해 상세",
                value=self._damage_catalog_text(detail.detail_lines, detail.hit_damages, limit=950),
                inline=False,
            )
        if detail.received_damage > 0:
            source = detail.received_source or "상대"
            embed.add_field(
                name=f"받은 피해 ← {source}",
                value=self._damage_summary_text(detail.received_damage, detail.received_hit_damages),
                inline=False,
            )
            if detail.received_summary:
                embed.add_field(name="받은 피해 로그", value=detail.received_summary, inline=False)
            embed.add_field(
                name="받은 피해 상세",
                value=self._damage_catalog_text(detail.received_detail_lines, detail.received_hit_damages, limit=950),
                inline=False,
            )
        return embed

    def _damage_summary_text(
        self,
        total_damage: int,
        damages: list[int],
        *,
        ability_damage: int = 0,
    ) -> str:
        hits = len(damages)
        average = total_damage / max(1, hits)
        summary = [
            f"총 피해 **{total_damage}**",
            f"타수 **{hits}**",
            f"평균 **{average:.1f}**",
        ]
        if damages:
            summary.append(f"최대 **{max(damages)}**")
            summary.append(f"최소 **{min(damages)}**")
        if ability_damage:
            summary.append(f"추가 어빌 피해 **{ability_damage}**")
        return " · ".join(summary)

    def _damage_catalog_text(self, lines: list[str], damages: list[int], *, limit: int) -> str:
        if not lines:
            return self._damage_hits_text(damages, limit=limit)
        output: list[str] = []
        for index, line in enumerate(lines):
            next_text = "\n".join([*output, line])
            if len(next_text) > limit:
                output.append(f"... 외 {len(lines) - index}줄")
                break
            output.append(line)
        return "\n".join(output) if output else "피해 타격 없음"

    def _damage_hits_text(self, damages: list[int], *, limit: int) -> str:
        if not damages:
            return "피해 타격 없음"
        lines = []
        for start in range(0, len(damages), 10):
            chunk = damages[start:start + 10]
            line = f"{start + 1:02d}-{start + len(chunk):02d}: " + ", ".join(str(damage) for damage in chunk)
            next_text = "\n".join([*lines, line])
            if len(next_text) > limit:
                lines.append(f"... 외 {len(damages) - start}타")
                break
            lines.append(line)
        return "\n".join(lines)

    def _set_boss_damage_detail(
        self,
        participant: BossParticipant,
        *,
        action: str,
        target: str,
        summary: str,
        total_damage: int,
        hit_damages: list[int],
        ability_damage: int = 0,
        detail_lines: list[str] | None = None,
    ) -> None:
        if total_damage <= 0 or not hit_damages:
            return
        participant.last_damage_detail = BossDamageDetail(
            action=action,
            target=target,
            summary=summary,
            total_damage=total_damage,
            hit_damages=list(hit_damages),
            ability_damage=ability_damage,
            detail_lines=list(detail_lines or []),
        )

    def _add_boss_received_damage_detail(
        self,
        participant: BossParticipant,
        *,
        action: str,
        source: str,
        summary: str,
        total_damage: int,
        hit_damages: list[int],
        detail_lines: list[str] | None = None,
    ) -> None:
        if total_damage <= 0 or not hit_damages:
            return
        detail = participant.last_damage_detail
        if detail is None or detail.action != action:
            detail = BossDamageDetail(
                action=action,
                target="",
                summary="",
                total_damage=0,
                hit_damages=[],
            )
            participant.last_damage_detail = detail
        detail.received_damage = total_damage
        detail.received_hit_damages = list(hit_damages)
        detail.received_detail_lines = list(detail_lines or [])
        detail.received_summary = summary
        detail.received_source = source

    async def _refresh_boss_damage_detail_message(self, session: BossSession, user_id: int) -> None:
        message = self._boss_damage_detail_messages.get((session.id, user_id))
        if message is None:
            return
        participant = session.participants.get(user_id)
        try:
            await message.edit(embed=self._boss_damage_detail_embed(session, participant))
        except discord.HTTPException:
            self._boss_damage_detail_messages.pop((session.id, user_id), None)

    async def _refresh_boss_public_message(self, session: BossSession) -> None:
        if session.message is None:
            return
        try:
            await session.message.edit(
                embed=self._boss_session_embed(session),
                view=BossSessionView(self, session),
            )
            await self._sync_material_reactions(session.message, session.reward_materials, session.message.guild)
        except discord.HTTPException:
            session.message = None

    async def _sync_material_reactions(
        self,
        message: discord.Message,
        materials: dict[str, int],
        guild: discord.Guild | None,
    ) -> None:
        configured = self._material_reaction_emojis(
            {
                material.id: 1
                for material in MATERIALS
                if material.emoji
            },
            guild,
        )
        desired = self._material_reaction_emojis(materials, guild)
        bot_user = self.bot.user
        if bot_user is None:
            return
        for emoji in configured:
            try:
                await message.remove_reaction(emoji, bot_user)
            except (discord.HTTPException, TypeError, ValueError):
                pass
        for emoji in desired:
            try:
                await message.add_reaction(emoji)
            except (discord.HTTPException, TypeError, ValueError):
                pass

    def _material_reaction_emojis(
        self,
        materials: dict[str, int],
        guild: discord.Guild | None,
    ) -> list[str | discord.Emoji | discord.PartialEmoji]:
        emojis: list[str | discord.Emoji | discord.PartialEmoji] = []
        seen: set[str] = set()
        for material_id, amount in materials.items():
            if amount <= 0:
                continue
            material = MATERIAL_BY_ID.get(material_id)
            emoji = self._resolve_material_emoji(material.emoji if material is not None else "", guild)
            if emoji is None:
                continue
            key = str(emoji)
            if key in seen:
                continue
            seen.add(key)
            emojis.append(emoji)
        return emojis

    def _resolve_material_emoji(
        self,
        raw_emoji: str,
        guild: discord.Guild | None,
    ) -> str | discord.Emoji | discord.PartialEmoji | None:
        raw_emoji = raw_emoji.strip()
        if not raw_emoji:
            return None
        if raw_emoji.startswith("<") and raw_emoji.endswith(">"):
            try:
                return discord.PartialEmoji.from_str(raw_emoji)
            except (TypeError, ValueError):
                return None
        if raw_emoji.startswith(":") and raw_emoji.endswith(":") and len(raw_emoji) > 2:
            name = raw_emoji.strip(":")
            if guild is None:
                return None
            return discord.utils.get(guild.emojis, name=name)
        return raw_emoji

    def _battle_result_embed(
        self,
        title: str,
        result: ExploreResult | BossResult,
        color: int,
    ) -> discord.Embed:
        battle = result.battle
        reward = result.reward
        status = "승리" if battle and battle.won else "패배"
        embed = discord.Embed(title=title, description=f"결과: **{status}**", color=color)
        if battle is not None:
            embed.add_field(
                name="전투",
                value=(
                    f"{battle.turns}턴 · 내 HP {battle.player_hp}/{battle.player_max_hp} · "
                    f"적 HP {battle.enemy_hp}/{battle.enemy_max_hp}"
                ),
                inline=False,
            )
            embed.add_field(name="로그", value=self._trim("\n".join(battle.log), 1024), inline=False)
            if battle.skills_used:
                embed.add_field(name="사용 스킬", value=", ".join(dict.fromkeys(battle.skills_used)), inline=False)
        if reward is not None:
            embed.add_field(name="보상", value=self._reward_text(reward), inline=False)
        if isinstance(result, ExploreResult):
            embed.set_footer(text=f"탐색 제한 {self._explore_limit_text(result.profile)}")
        return embed

    def _equipment_embed(
        self,
        profile: PlayerProfile,
        selected_uids: list[int] | None = None,
        result: EquipmentResult | None = None,
    ) -> discord.Embed:
        description = result.message if result is not None else "아래 메뉴에서 장비를 선택하면 바로 장착 상태가 저장됩니다."
        equipped = self.service.equipped_items(profile)
        equipped_ids = {item.uid for item in equipped}
        embed = discord.Embed(
            title="장비 장착",
            description=description,
            color=self._items_embed_color(equipped),
        )
        slot_lines = []
        for idx in range(MAX_EQUIPPED_ITEMS):
            if idx < len(equipped):
                item = equipped[idx]
                slot_lines.append(f"`{idx + 1}` {self._item_display_title(item)}")
            else:
                slot_lines.append(f"`{idx + 1}` 비어 있음")
        embed.add_field(
            name=f"장착 슬롯 {len(equipped_ids)}/{MAX_EQUIPPED_ITEMS}",
            value="\n".join(slot_lines),
            inline=False,
        )

        display_items = self._equipment_display_items(profile)
        lines = []
        for item in display_items[:10]:
            marker = "장착" if item.uid in equipped_ids else "보유"
            if item.destroyed:
                marker = "파괴"
            lines.append(f"`{marker}` {self._item_display_title(item)}")
        embed.add_field(name="보유 장비", value="\n".join(lines) if lines else "장비 없음", inline=False)

        embed.add_field(
            name="현재 전투 스탯",
            value=self.service.format_stats(self.service.profile_stats(profile)),
            inline=False,
        )
        if len(profile.inventory) > 25:
            embed.set_footer(text="선택 UI는 장착 중인 장비, 높은 등급, 전투력 높은 장비를 우선해 25개까지 표시합니다.")
        return embed

    def _sell_embed(
        self,
        profile: PlayerProfile,
        selected_uids: list[int] | None = None,
        result: SellResult | None = None,
    ) -> discord.Embed:
        embed = discord.Embed(
            title="장비 판매",
            description=result.message if result is not None else "판매할 장비를 선택한 뒤 판매 버튼을 누르세요.",
            color=0xA0A7B4,
        )
        selected_uids = selected_uids or []
        selected = [item for item in self._sellable_items(profile) if item.uid in set(selected_uids)]
        if selected:
            total = sum(self.service.item_sell_price(item) for item in selected)
            lines = [
                f"{self.service.item_title(item)} · {self.service.item_sell_price(item)}G"
                for item in selected
            ]
            embed.add_field(name=f"선택 장비 {len(selected)}개", value=self._trim("\n".join(lines), 1400), inline=False)
            embed.add_field(name="예상 판매가", value=f"{total}G", inline=True)
        else:
            lines = [
                f"{self.service.item_title(item)} · {self.service.item_sell_price(item)}G"
                for item in self._sellable_items(profile)[:10]
            ]
            embed.add_field(name="판매 가능 장비", value="\n".join(lines) if lines else "없음", inline=False)
        if result is not None and result.sold_items:
            embed.add_field(name="판매 결과", value=f"{result.sold_count}개 · {result.gold}G", inline=False)
        embed.set_footer(text=f"보유 골드 {profile.gold}G · 장착 중인 장비는 판매되지 않습니다.")
        return embed

    def _auto_sell_embed(self, profile: PlayerProfile, result: SellResult | None = None) -> discord.Embed:
        selected = [RARITY_LABELS[rarity] for rarity in profile.auto_sell_rarities]
        embed = discord.Embed(
            title="자동판매 설정",
            description=result.message if result is not None else "드랍 즉시 판매할 등급을 선택하세요.",
            color=0xA0A7B4,
        )
        embed.add_field(name="현재 설정", value=", ".join(selected) if selected else "없음", inline=False)
        candidates = self._auto_sell_candidate_items(profile)
        if candidates:
            gold = sum(self.service.item_sell_price(item) for item in candidates)
            embed.add_field(name="현재 판매 대상", value=f"{len(candidates)}개 · {gold}G", inline=False)
        else:
            embed.add_field(name="현재 판매 대상", value="없음", inline=False)
        embed.set_footer(text="자동판매된 장비는 보상 로그에 판매가로 표시됩니다.")
        return embed

    def _job_advance_embed(
        self,
        profile: PlayerProfile,
        result: JobResult | None = None,
        *,
        free_mode: bool = False,
    ) -> discord.Embed:
        color = 0x57F287 if result is not None and result.ok else 0xB56BFF
        if result is not None and not result.ok:
            color = 0xED4245
        default_description = "같은 티어의 다른 직업으로 자유전직할 수 있습니다." if free_mode else "전직 가능한 직업을 선택하세요."
        embed = discord.Embed(
            title="자유전직" if free_mode else "전직",
            description=result.message if result is not None else default_description,
            color=color,
        )
        current_job = self.service.current_job(profile)
        embed.add_field(name="현재 직업", value=f"{current_job.name} · T{current_job.tier}", inline=True)
        available = self.service.free_advance_jobs(profile) if free_mode else self.service.available_jobs(profile)
        if available:
            lines = [
                f"**{job.name}** · Lv.{job.level_req}+ · {self.service.format_stats(job.stats, signed=True)}"
                for job in available
            ]
            embed.add_field(name="자유전직 가능" if free_mode else "전직 가능", value=self._trim("\n".join(lines), 1000), inline=False)
        elif free_mode:
            embed.add_field(name="자유전직 가능", value="같은 티어에서 전직 가능한 다른 직업이 없습니다.", inline=False)
        else:
            next_jobs = self.service.next_jobs(profile)
            if next_jobs:
                lines = [f"**{job.name}** · Lv.{job.level_req} 필요" for job in next_jobs]
                embed.add_field(name="다음 전직", value="\n".join(lines), inline=False)
            else:
                embed.add_field(name="전직 가능", value="없음", inline=False)
        embed.add_field(name="전투 스탯", value=self.service.format_stats(self.service.profile_stats(profile)), inline=False)
        skills = self.service.unlocked_skills(profile)
        if skills:
            embed.add_field(
                name="사용 가능한 스킬",
                value=self._trim("\n".join(f"**{skill.name}** · {self.service.skill_summary(skill)}" for skill in skills), 1000),
                inline=False,
            )
        return embed

    def _ability_embed(
        self,
        profile: PlayerProfile,
        result: AbilityResult | None = None,
        selected_skill_ids: list[str] | None = None,
    ) -> discord.Embed:
        available = self.service.unlocked_skills(profile)
        by_id = {skill.id: skill for skill in available}
        equipped = (
            [by_id[skill_id] for skill_id in selected_skill_ids if skill_id in by_id]
            if selected_skill_ids is not None
            else self.service.equipped_skills(profile)
        )
        embed = discord.Embed(
            title="어빌리티 장착",
            description=result.message if result is not None else "사용할 어빌리티를 선택하면 바로 저장됩니다.",
            color=0xB56BFF,
        )
        embed.add_field(
            name=f"장착 어빌리티 {len(equipped)}/{MAX_EQUIPPED_SKILLS}",
            value="\n".join(f"**{skill.name}** · {self.service.skill_summary(skill)}" for skill in equipped) if equipped else "없음",
            inline=False,
        )
        embed.add_field(
            name="사용 가능",
            value=self._trim("\n".join(f"**{skill.name}** · {self.service.skill_summary(skill)}" for skill in available), 1400),
            inline=False,
        )
        return embed

    def _materials_embed(self, profile: PlayerProfile) -> discord.Embed:
        embed = discord.Embed(
            title="제작 재료",
            description=f"보유 골드 {profile.gold}G",
            color=0x4BA3FF,
        )
        material_lines = []
        for material in MATERIALS:
            amount = profile.materials.get(material.id, 0)
            if amount <= 0:
                continue
            label = RARITY_LABELS.get(material.rarity, material.rarity)
            material_lines.append(f"[{label}] **{material.name}** x{amount}")
        embed.add_field(
            name="보유 재료",
            value=self._trim("\n".join(material_lines), 1500) if material_lines else "보유 재료 없음",
            inline=False,
        )
        craftable = [
            recipe for recipe in self.service.crafting_recipes()
            if self.service.can_craft(profile, recipe)
        ]
        if craftable:
            lines = [
                f"**{recipe.name}**\n{self.service.recipe_result_text(recipe)}"
                for recipe in craftable[:6]
            ]
            embed.add_field(name="제작 가능", value=self._trim("\n\n".join(lines), 1800), inline=False)
        else:
            embed.add_field(name="제작 가능", value="현재 제작 가능한 장비가 없습니다.", inline=False)
        return embed

    def _crafting_embed(
        self,
        profile: PlayerProfile,
        selected_recipe_id: str | None = None,
        result: CraftResult | None = None,
    ) -> discord.Embed:
        recipes = self._crafting_display_recipes(profile)
        selected = next((recipe for recipe in recipes if recipe.id == selected_recipe_id), None)
        embed = discord.Embed(
            title="장비 제작",
            description=result.message if result is not None else f"보유 골드 {profile.gold}G",
            color=0xFFB84D,
        )
        if recipes:
            lines = []
            for recipe in recipes[:20]:
                template = ITEM_BY_ID.get(recipe.result_item_id)
                rarity = RARITY_LABELS.get(template.rarity, template.rarity) if template is not None else "오류"
                status = "가능" if self.service.can_craft(profile, recipe) else "부족"
                marker = "▶ " if recipe.id == selected_recipe_id else ""
                lines.append(f"{marker}`{status}` [{rarity}] {recipe.name}")
            if len(recipes) > 20:
                lines.append(f"외 {len(recipes) - 20}개")
            embed.add_field(name=f"제작 목록 {len(recipes)}개", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="제작 목록", value="제작법이 없습니다.", inline=False)

        if result is not None and result.item is not None:
            embed.add_field(
                name="제작 결과",
                value=f"{self.service.item_title(result.item)}\n{self.service.item_stats_text(result.item)}",
                inline=False,
            )

        if selected is not None:
            status = self.service.recipe_status_text(profile, selected)
            embed.add_field(
                name="선택 제작",
                value=(
                    f"**{selected.name}** · {status}\n"
                    f"{selected.description}\n"
                    f"{self.service.recipe_result_text(selected)}"
                ),
                inline=False,
            )
            embed.add_field(name="제작 비용", value=f"{selected.gold}G", inline=True)
            embed.add_field(
                name="제작 재료",
                value=self.service.material_cost_text(profile, selected.materials),
                inline=False,
            )
        material_summary = self._material_summary(profile, limit=8)
        embed.add_field(name="보유 재료", value=material_summary or "보유 재료 없음", inline=False)
        return embed

    def _gacha_embed(self, result: GachaResult) -> discord.Embed:
        color = 0x57F287 if result.ok else 0xED4245
        if result.items:
            color = self._items_embed_color(result.items)
        title = result.pool.name if result.pool is not None else "가챠"
        embed = discord.Embed(title=title, description=result.message, color=color)
        if result.spent_material_id:
            remaining = result.profile.materials.get(result.spent_material_id, 0)
            embed.add_field(
                name="사용 재료",
                value=f"{self.service.material_name(result.spent_material_id)} x{result.spent_material_amount}",
                inline=True,
            )
            embed.add_field(
                name="보유 재료",
                value=f"{self.service.material_name(result.spent_material_id)} x{remaining}",
                inline=True,
            )
        if result.items:
            lines = [
                f"{self._item_display_title(item)} · {self.service.item_stats_text(item)}"
                for item in result.items
            ]
            embed.add_field(name=f"획득 장비 {len(result.items)}개", value=self._trim("\n".join(lines), 1800), inline=False)
        if result.auto_sold_items:
            embed.add_field(
                name=f"자동판매 {len(result.auto_sold_items)}개",
                value=f"{result.auto_sold_gold}G",
                inline=True,
            )
        if result.materials:
            material_lines = [
                f"{self.service.material_name(material_id)} x{amount}"
                for material_id, amount in result.materials.items()
            ]
            embed.add_field(name="획득 재료", value=", ".join(material_lines), inline=False)
        if result.ok:
            embed.set_footer(text="자동판매 대상 장비는 즉시 판매되고 골드로 지급됩니다.")
        return embed

    def _gacha_panel_embed(self, profile: PlayerProfile, selected_pool_id: str | None = None) -> discord.Embed:
        pool = self._gacha_selected_pool(selected_pool_id)
        if pool is None:
            return discord.Embed(
                title="가챠",
                description="사용할 수 있는 가챠 풀이 없습니다.",
                color=0xED4245,
        )
        owned = profile.materials.get(pool.cost_material_id, 0)
        default_cost = self.service.gacha_cost(pool, pool.draws)
        affordable = any(
            owned >= self.service.gacha_cost(pool, count)
            for count in self._gacha_draw_options(pool)
        )
        embed = discord.Embed(
            title=pool.name,
            description=pool.description or "가챠 풀을 선택하고 버튼으로 계속 뽑을 수 있습니다.",
            color=0x57F287 if affordable else 0xFFB84D,
        )
        embed.add_field(
            name="기본 소모",
            value=f"{pool.draws}회 · {self.service.material_name(pool.cost_material_id)} x{default_cost}",
            inline=True,
        )
        embed.add_field(
            name="보유 재료",
            value=f"{self.service.material_name(pool.cost_material_id)} x{owned}",
            inline=True,
        )
        costs = [
            f"{count}회 {self.service.gacha_cost(pool, count)}"
            for count in self._gacha_draw_options(pool)
        ]
        embed.add_field(name="버튼별 소모", value=" · ".join(costs), inline=False)
        if not affordable:
            embed.set_footer(text="재료가 부족하면 버튼이 비활성화됩니다.")
        else:
            embed.set_footer(text="버튼을 누르면 같은 패널에서 결과가 갱신됩니다.")
        return embed

    def _gacha_draw_options(self, pool) -> list[int]:
        return list(dict.fromkeys([1, int(pool.draws), 50, 100]))

    def _gacha_selected_pool(self, selected_pool_id: str | None = None):
        pools = self.service.gacha_pools()
        pool_id = selected_pool_id or GACHA_DEFAULT_POOL_ID
        if pool_id:
            selected = next((pool for pool in pools if pool.id == pool_id), None)
            if selected is not None:
                return selected
        return pools[0] if pools else None

    def _enhancement_picker_embed(self, profile: PlayerProfile) -> discord.Embed:
        display_items = self._enhancement_display_items(profile)
        enhance_count = len([item for item in profile.inventory if not item.destroyed and item.template_id in ITEM_BY_ID])
        trace_count = len([item for item in profile.inventory if item.destroyed and item.template_id in ITEM_BY_ID])
        embed = discord.Embed(
            title="장비 강화",
            description="아래 선택 메뉴에서 강화할 장비를 고르세요.",
            color=self._items_embed_color(display_items),
        )
        equipped_ids = {item.uid for item in self.service.equipped_items(profile)}
        lines = []
        for item in display_items:
            marker = "장착" if item.uid in equipped_ids else "보유"
            lines.append(f"`{marker}` {self._item_display_title(item)}")
        embed.add_field(name="장비", value="\n".join(lines) if lines else "강화할 장비 없음", inline=False)
        if trace_count:
            embed.add_field(name="파괴 흔적", value=f"{trace_count}개 · 아래 `흔적 복구` 버튼에서 복구할 수 있습니다.", inline=False)
        footer = f"보유 골드 {profile.gold}G"
        if enhance_count > len(display_items):
            footer += " · 선택 UI는 높은 등급과 전투력 기준 25개만 표시"
        embed.set_footer(text=footer)
        return embed

    def _enhancement_preview_embed(self, preview: EnhancementPreview) -> discord.Embed:
        color = 0xFFB84D
        if preview.item is not None and preview.item.template_id in ITEM_BY_ID:
            color = RARITY_COLORS[ITEM_BY_ID[preview.item.template_id].rarity]
        embed = discord.Embed(title="강화 미리보기", description=preview.message, color=color)
        if preview.item is None:
            return embed
        embed.add_field(name="장비", value=self._item_display_title(preview.item), inline=False)
        embed.add_field(name="현재 스탯", value=self.service.format_stats(preview.before_stats, signed=True), inline=False)
        effect_text = self.service.item_template_effects_text(preview.item.template_id)
        if effect_text:
            embed.add_field(name="영속 효과", value=self._trim(effect_text, 1024), inline=False)
        if preview.ok:
            success, fail, destroy = preview.odds
            embed.add_field(name="증가 스탯", value=self.service.format_stats(preview.delta_stats, signed=True), inline=False)
            embed.add_field(name="비용", value=f"{preview.cost}G", inline=True)
            embed.add_field(
                name="확률",
                value=f"성공 {success * 100:.1f}% · 실패 {fail * 100:.1f}% · 파괴 {destroy * 100:.1f}%",
                inline=False,
            )
            embed.add_field(name="강화 후", value=self.service.format_stats(preview.after_stats, signed=True), inline=False)
        embed.set_footer(text=f"보유 골드 {preview.profile.gold}G")
        return embed

    def _restore_preview_embed(self, preview: EnhancementPreview) -> discord.Embed:
        color = 0xFFB84D
        if preview.item is not None and preview.item.template_id in ITEM_BY_ID:
            color = RARITY_COLORS[ITEM_BY_ID[preview.item.template_id].rarity]
        embed = discord.Embed(title="장비 복구", description=preview.message, color=color)
        if preview.item is None:
            return embed
        embed.add_field(name="복구 대상", value=self._item_display_title(preview.item), inline=False)
        embed.add_field(
            name="복구 성급",
            value=f"+{preview.before_stars} 흔적 → +{preview.after_stars}",
            inline=True,
        )
        embed.add_field(name="복구 비용", value=f"{preview.cost}G", inline=True)
        if preview.spare_item is not None:
            embed.add_field(name="소모 스페어", value=self._item_display_title(preview.spare_item), inline=True)
        else:
            embed.add_field(name="소모 스페어", value="같은 장비 1개 필요", inline=True)
        if preview.after_stats:
            embed.add_field(name="복구 후 스탯", value=self.service.format_stats(preview.after_stats, signed=True), inline=False)
        effect_text = self.service.item_template_effects_text(preview.item.template_id)
        if effect_text:
            embed.add_field(name="영속 효과", value=self._trim(effect_text, 1024), inline=False)
        embed.set_footer(text=f"보유 골드 {preview.profile.gold}G")
        return embed

    def _restore_panel_embed(
        self,
        user_id: int,
        display_name: str,
        selected_trace_uid: int | None = None,
        selected_spare_uid: int | None = None,
        result: EnhancementResult | None = None,
    ) -> discord.Embed:
        profile = self.service.get_profile(user_id, display_name)
        if result is not None:
            embed = self._enhance_result_embed(result)
            embed.title = "장비 복구"
            return embed
        trace = self._profile_item(profile, selected_trace_uid)
        if trace is not None and trace.destroyed:
            return self._restore_preview_embed(
                self.service.restore_preview(user_id, display_name, trace.uid, selected_spare_uid)
            )
        traces = self._restore_trace_display_items(profile)
        embed = discord.Embed(
            title="장비 복구",
            description="복구할 파괴 흔적을 선택하세요. 다음 단계에서 소모할 같은 장비 스페어를 고를 수 있습니다.",
            color=self._items_embed_color(traces),
        )
        lines = [f"`흔적` {self._item_display_title(item)}" for item in traces[:10]]
        embed.add_field(name="파괴 흔적", value="\n".join(lines) if lines else "복구할 흔적 없음", inline=False)
        embed.set_footer(text=f"보유 골드 {profile.gold}G")
        return embed

    def _enhance_result_embed(
        self,
        result: EnhancementResult,
        next_preview: EnhancementPreview | None = None,
    ) -> discord.Embed:
        color = 0x57F287 if result.ok else 0xED4245
        if result.item is not None and result.item.template_id in ITEM_BY_ID:
            color = RARITY_COLORS[ITEM_BY_ID[result.item.template_id].rarity]
        embed = discord.Embed(title="장비 강화", description=result.message, color=color)
        if result.item is not None:
            embed.add_field(name="장비", value=self._item_display_title(result.item), inline=False)
            if result.item.destroyed:
                embed.add_field(name="흔적 정보", value=f"파괴 당시 +{result.item.stars}", inline=False)
            else:
                embed.add_field(name="스탯", value=self.service.item_stats_text(result.item), inline=False)
        if result.cost:
            embed.add_field(name="비용", value=f"{result.cost}G", inline=True)
        if result.spare_item is not None:
            embed.add_field(name="소모 스페어", value=self._item_display_title(result.spare_item), inline=True)
        if result.outcome:
            outcome_text = {
                "success": "성공",
                "failed": "실패",
                "destroyed": "파괴",
                "restored": "복구",
                "no_gold": "골드 부족",
                "no_spare": "스페어 부족",
            }.get(result.outcome, result.outcome)
            if result.outcome == "destroyed":
                result_text = f"{outcome_text} · +{result.before_stars} 흔적 생성"
            elif result.outcome == "restored":
                result_text = f"{outcome_text} · +{result.before_stars} 흔적 → +{result.after_stars}"
            else:
                result_text = f"{outcome_text} · +{result.before_stars} → +{result.after_stars}"
            embed.add_field(name="결과", value=result_text, inline=True)
        if result.odds != (0.0, 0.0, 0.0):
            success, fail, destroy = result.odds
            embed.add_field(
                name="확률",
                value=f"성공 {success * 100:.1f}% · 실패 {fail * 100:.1f}% · 파괴 {destroy * 100:.1f}%",
                inline=False,
            )
        if next_preview is not None and next_preview.item is not None:
            if next_preview.ok:
                success, fail, destroy = next_preview.odds
                embed.add_field(
                    name="다음 강화",
                    value=(
                        f"비용 {next_preview.cost}G\n"
                        f"성공 {success * 100:.1f}% · 실패 {fail * 100:.1f}% · 파괴 {destroy * 100:.1f}%"
                    ),
                    inline=False,
                )
                embed.add_field(
                    name="다음 증가 스탯",
                    value=self.service.format_stats(next_preview.delta_stats, signed=True),
                    inline=False,
                )
            else:
                embed.add_field(name="다음 강화", value=next_preview.message, inline=False)
        embed.set_footer(text=f"보유 골드 {result.profile.gold}G")
        return embed

    def _reward_text(self, reward) -> str:
        parts = []
        if reward.weekly_reward_locked:
            parts.append("이번 주 보스 보상은 이미 수령했습니다.")
        if reward.consolation:
            parts.append("패배 보상")
        if reward.gold:
            parts.append(f"{reward.gold}G")
        if reward.exp:
            parts.append(f"{reward.exp}EXP")
        if reward.levels_gained:
            parts.append(f"레벨업 +{reward.levels_gained}")
        dropped_items = getattr(reward, "dropped_items", [])
        if dropped_items:
            parts.append("드랍: " + ", ".join(self.service.item_title(item) for item in dropped_items))
        elif reward.dropped_item:
            parts.append(f"드랍: {self.service.item_title(reward.dropped_item)}")
        materials = getattr(reward, "materials", {})
        if materials:
            parts.append(
                "재료: "
                + ", ".join(f"{self.service.material_name(material_id)} x{amount}" for material_id, amount in materials.items())
            )
        auto_sold_items = getattr(reward, "auto_sold_items", [])
        if auto_sold_items:
            parts.append(f"자동판매: {len(auto_sold_items)}개 · {reward.auto_sold_gold}G")
        elif reward.auto_sold_item:
            parts.append(f"자동판매: {self.service.item_title(reward.auto_sold_item)} · {reward.auto_sold_gold}G")
        if not parts:
            return "보상 없음"
        return "\n".join(parts)

    def _explore_batch_reward_text(self, results: list[ExploreResult]) -> str:
        gold = 0
        exp = 0
        levels = 0
        dropped_items = []
        auto_sold_items = []
        auto_sold_gold = 0
        materials: dict[str, int] = {}
        consolation_count = 0
        for result in results:
            reward = result.reward
            if reward is None:
                continue
            if reward.consolation:
                consolation_count += 1
            gold += reward.gold
            exp += reward.exp
            levels += reward.levels_gained
            dropped_items.extend(getattr(reward, "dropped_items", []))
            auto_sold_items.extend(getattr(reward, "auto_sold_items", []))
            auto_sold_gold += reward.auto_sold_gold
            for material_id, amount in getattr(reward, "materials", {}).items():
                materials[material_id] = materials.get(material_id, 0) + amount

        parts = []
        if consolation_count:
            parts.append(f"패배 보상 {consolation_count}회")
        if gold:
            parts.append(f"{gold}G")
        if exp:
            parts.append(f"{exp}EXP")
        if levels:
            parts.append(f"레벨업 +{levels}")
        if materials:
            parts.append(
                "재료: "
                + ", ".join(
                    f"{self.service.material_name(material_id)} x{amount}"
                    for material_id, amount in materials.items()
                )
            )
        if dropped_items:
            preview = ", ".join(self.service.item_title(item) for item in dropped_items[:6])
            suffix = f" 외 {len(dropped_items) - 6}개" if len(dropped_items) > 6 else ""
            parts.append(f"드랍 {len(dropped_items)}개: {preview}{suffix}")
        if auto_sold_items:
            parts.append(f"자동판매 {len(auto_sold_items)}개 · {auto_sold_gold}G")
        return self._trim("\n".join(parts), 1024) if parts else "보상 없음"

    def _has_visible_effects(self, effects: list[ActiveEffect]) -> bool:
        return any(self.service._effect_active(effect) and (effect.mods or effect.special.has_any) for effect in effects)

    def _effects_text(self, effects: list[ActiveEffect], *, limit: int, compact: bool = False) -> str:
        active = [
            effect for effect in effects
            if self.service._effect_active(effect) and (effect.mods or effect.special.has_any)
        ]
        if not active:
            return "없음"
        lines = []
        for effect in active:
            stats = self._effect_value_text(effect)
            turns = self._effect_turns_text(effect)
            if compact:
                lines.append(f"{stats}({turns})")
            else:
                lines.append(f"{stats} · 남은 {turns}")
        separator = " / " if compact else "\n"
        return self._trim(separator.join(lines), limit)

    def _effect_value_text(self, effect: ActiveEffect) -> str:
        parts = []
        if effect.mods:
            parts.append(self.service.format_stats(effect.mods, signed=True))
            cap_text = self.service._heal_cap_summary(effect.heal_cap)
            if "life_steal" in effect.mods and cap_text:
                parts.append(f"회복 상한 {cap_text}")
        if effect.special.flurry is not None:
            parts.append(f"난격 {effect.special.flurry.count}")
        if effect.special.double_strike is not None:
            parts.append(f"재행동 {effect.special.double_strike.count}회")
        for bonus in effect.special.bonus_damage:
            parts.append(f"추격 {bonus.ratio * 100:.0f}%")
        for reinforce in effect.special.critical_reinforce:
            parts.append(f"크리 리인포스 {reinforce.ratio * 100:.0f}%")
        for final_effect in effect.special.final_damage:
            parts.append(f"최종 데미지 {self.service._signed_effect_ratio_text(final_effect.ratio)}")
        for post_attack in effect.special.post_attack_ability_damage:
            parts.append(f"공격 후 어빌 피해 {post_attack.ratio * 100:.0f}% {post_attack.count}타")
        for guard in effect.special.dispel_guard:
            suffix = f" {guard.count}회" if guard.count > 0 else ""
            parts.append(f"디스펠 가드{suffix}")
        for veil in effect.special.veil:
            suffix = f" {veil.count}회" if veil.count > 0 else ""
            parts.append(f"마운트{suffix}")
        if effect.undispellable:
            parts.append("소거불가")
        return ", ".join(parts) if parts else "효과"

    def _effect_turns_text(self, effect: ActiveEffect) -> str:
        return "무한" if effect.turns < 0 else f"{effect.turns}턴"

    def _rarity_emoji(self, rarity: str) -> str:
        return RARITY_EMOJIS.get(rarity, "▫️")

    def _rarity_rank(self, rarity: str) -> int:
        try:
            return RARITIES.index(rarity)
        except ValueError:
            return -1

    def _item_rarity_rank(self, item) -> int:
        template = ITEM_BY_ID.get(item.template_id)
        if template is None:
            return -1
        return self._rarity_rank(template.rarity)

    def _item_display_title(self, item) -> str:
        template = ITEM_BY_ID[item.template_id]
        label = RARITY_LABELS.get(template.rarity, template.rarity)
        marker = self._rarity_emoji(template.rarity)
        destroyed = " 흔적" if item.destroyed else ""
        return f"{marker} [{label}] {template.name} +{item.stars}{destroyed}"

    def _item_select_label(self, item) -> str:
        template = ITEM_BY_ID[item.template_id]
        label = RARITY_LABELS.get(template.rarity, template.rarity)
        destroyed = " 흔적" if item.destroyed else ""
        return f"[{label}] {template.name} +{item.stars}{destroyed}"[:100]

    def _item_option_description(self, marker: str, item, *extra: str) -> str:
        bits = [marker, *extra, self.service.item_stats_text(item)]
        return " · ".join(bit.replace("\n", " · ") for bit in bits if bit)[:100]

    def _items_embed_color(self, items) -> int:
        valid_items = [item for item in items if item.template_id in ITEM_BY_ID]
        if not valid_items:
            return 0xA0A7B4
        best = max(valid_items, key=lambda item: self._item_rarity_rank(item))
        rarity = ITEM_BY_ID[best.template_id].rarity
        return RARITY_COLORS.get(rarity, 0xA0A7B4)

    def _trim(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

    def _material_summary(self, profile: PlayerProfile, *, limit: int = 8) -> str:
        lines = []
        known_order = {material.id: idx for idx, material in enumerate(MATERIALS)}
        for material_id, amount in sorted(
            profile.materials.items(),
            key=lambda entry: (known_order.get(entry[0], 999), entry[0]),
        ):
            if amount <= 0:
                continue
            lines.append(f"{self.service.material_name(material_id)} x{amount}")
            if len(lines) >= limit:
                break
        remaining = sum(1 for amount in profile.materials.values() if amount > 0) - len(lines)
        if remaining > 0:
            lines.append(f"외 {remaining}종")
        return "\n".join(lines)

    def _crafting_display_recipes(self, profile: PlayerProfile):
        recipes = self.service.crafting_recipes()
        return sorted(
            recipes,
            key=lambda recipe: (
                not self.service.can_craft(profile, recipe),
                profile.level < recipe.level_req,
                recipe.level_req,
                recipe.sort_order,
                recipe.name,
            ),
        )[:25]

    def _default_crafting_recipe_id(self, profile: PlayerProfile) -> str | None:
        recipes = self._crafting_display_recipes(profile)
        return recipes[0].id if recipes else None

    def _explore_limit_text(self, profile: PlayerProfile) -> str:
        if not self.service.explore_limit_enabled():
            return "무제한"
        return f"{self.service.daily_remaining(profile)}/{DAILY_EXPLORES}회"

    def _profile_item(self, profile: PlayerProfile, uid: int | None):
        if uid is None:
            return None
        for item in profile.inventory:
            if item.uid == uid:
                return item
        return None

    def _equipment_display_items(self, profile: PlayerProfile):
        equipped_ids = {item.uid for item in self.service.equipped_items(profile)}
        return sorted(
            profile.inventory,
            key=lambda item: (
                item.uid not in equipped_ids,
                item.destroyed,
                -self._item_rarity_rank(item),
                -item.stars,
                -self.service.item_score(item),
                item.uid,
            ),
        )[:25]

    def _sellable_items(self, profile: PlayerProfile):
        equipped_ids = set(profile.equipped_item_uids)
        return sorted(
            [
                item for item in profile.inventory
                if item.uid not in equipped_ids and item.template_id in ITEM_BY_ID
            ],
            key=lambda item: (
                item.destroyed,
                RARITIES.index(ITEM_BY_ID[item.template_id].rarity),
                -self.service.item_score(item),
                item.uid,
            ),
        )[:25]

    def _auto_sell_candidate_items(self, profile: PlayerProfile):
        if not profile.auto_sell_rarities:
            return []
        equipped_ids = set(profile.equipped_item_uids)
        selected = set(profile.auto_sell_rarities)
        return sorted(
            [
                item for item in profile.inventory
                if item.uid not in equipped_ids
                and item.template_id in ITEM_BY_ID
                and ITEM_BY_ID[item.template_id].rarity in selected
            ],
            key=lambda item: (
                RARITIES.index(ITEM_BY_ID[item.template_id].rarity),
                -self.service.item_score(item),
                item.uid,
            ),
        )

    def _enhancement_display_items(self, profile: PlayerProfile):
        equipped_ids = set(profile.equipped_item_uids)
        return sorted(
            [
                item for item in profile.inventory
                if not item.destroyed and item.template_id in ITEM_BY_ID
            ],
            key=lambda item: (
                -self._item_rarity_rank(item),
                item.uid not in equipped_ids,
                -item.stars,
                -self.service.item_score(item),
                item.uid,
            ),
        )[:25]

    def _restore_trace_display_items(self, profile: PlayerProfile):
        return sorted(
            [
                item for item in profile.inventory
                if item.destroyed and item.template_id in ITEM_BY_ID
            ],
            key=lambda item: (
                -self._item_rarity_rank(item),
                -item.stars,
                -self.service.item_score(item),
                item.uid,
            ),
        )[:25]

    def _restore_spare_display_items(self, profile: PlayerProfile, trace):
        return self.service._restore_spare_candidates(profile, trace)[:25]


class JobAdvanceView(discord.ui.View):
    def __init__(self, cog: RPGCog, user_id: int, display_name: str, *, free_mode: bool = False) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        self.free_mode = free_mode
        profile = self.cog.service.get_profile(user_id, display_name)
        jobs = self.cog.service.free_advance_jobs(profile) if free_mode else self.cog.service.available_jobs(profile)
        options = [
            discord.SelectOption(
                label=job.name[:100],
                value=job.id,
                description=f"Lv.{job.level_req}+ · {self.cog.service.format_stats(job.stats, signed=True)}"[:100],
            )
            for job in jobs[:25]
        ]
        if options:
            self.add_item(JobAdvanceSelect(options))
        self.add_item(JobAdvanceModeButton(free_mode))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 전직 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class JobAdvanceSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="전직할 직업 선택",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, JobAdvanceView)
        result = (
            self.view.cog.service.free_advance_job(
                self.view.user_id,
                self.view.display_name,
                self.values[0],
            )
            if self.view.free_mode
            else self.view.cog.service.advance_job(
                self.view.user_id,
                self.view.display_name,
                self.values[0],
            )
        )
        next_view = JobAdvanceView(
            self.view.cog,
            self.view.user_id,
            self.view.display_name,
            free_mode=self.view.free_mode,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._job_advance_embed(result.profile, result, free_mode=self.view.free_mode),
            view=next_view if next_view.children else None,
        )


class JobAdvanceModeButton(discord.ui.Button):
    def __init__(self, free_mode: bool) -> None:
        super().__init__(
            label="돌아가기" if free_mode else "자유전직",
            style=discord.ButtonStyle.secondary,
        )
        self.next_free_mode = not free_mode

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, JobAdvanceView)
        profile = self.view.cog.service.get_profile(self.view.user_id, self.view.display_name)
        next_view = JobAdvanceView(
            self.view.cog,
            self.view.user_id,
            self.view.display_name,
            free_mode=self.next_free_mode,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._job_advance_embed(profile, free_mode=self.next_free_mode),
            view=next_view if next_view.children else None,
        )


class GachaView(discord.ui.View):
    def __init__(
        self,
        cog: RPGCog,
        user_id: int,
        display_name: str,
        selected_pool_id: str | None = None,
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        selected_pool = self.cog._gacha_selected_pool(selected_pool_id)
        self.selected_pool_id = selected_pool.id if selected_pool is not None else selected_pool_id
        profile = self.cog.service.get_profile(user_id, display_name)
        pools = self.cog.service.gacha_pools()[:25]
        if len(pools) > 1:
            options = []
            for pool in pools:
                owned = profile.materials.get(pool.cost_material_id, 0)
                options.append(
                    discord.SelectOption(
                        label=pool.name[:100],
                        value=pool.id,
                        description=(
                            f"{pool.draws}회 · "
                            f"{self.cog.service.material_name(pool.cost_material_id)} {owned}/{pool.cost_material_amount}"
                        )[:100],
                        default=pool.id == self.selected_pool_id,
                    )
                )
            self.add_item(GachaPoolSelect(options))
        if selected_pool is not None:
            for count in self.cog._gacha_draw_options(selected_pool):
                self.add_item(
                    GachaRollButton(
                        selected_pool,
                        count,
                        disabled=self._roll_disabled(profile, selected_pool, count),
                    )
                )
        else:
            self.add_item(GachaRollButton(None, 0, disabled=True))

    def _roll_disabled(self, profile: PlayerProfile, pool, draws: int) -> bool:
        if pool is None:
            return True
        known_material_ids = {material.id for material in self.cog.service.materials()}
        if pool.cost_material_id not in known_material_ids:
            return False
        return profile.materials.get(pool.cost_material_id, 0) < self.cog.service.gacha_cost(pool, draws)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 가챠 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class GachaPoolSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="가챠 풀 선택",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, GachaView)
        pool_id = self.values[0]
        profile = self.view.cog.service.get_profile(self.view.user_id, self.view.display_name)
        await interaction.response.edit_message(
            embed=self.view.cog._gacha_panel_embed(profile, pool_id),
            view=GachaView(self.view.cog, self.view.user_id, self.view.display_name, pool_id),
        )
        if interaction.message is not None:
            await self.view.cog._sync_material_reactions(interaction.message, {}, interaction.guild)


class GachaRollButton(discord.ui.Button):
    def __init__(self, pool, draws: int, *, disabled: bool = False) -> None:
        self.draws = draws
        label = f"{draws}회 돌리기" if pool is not None else "가챠"
        super().__init__(label=label, style=discord.ButtonStyle.primary, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, GachaView)
        result = self.view.cog.service.roll_gacha(
            self.view.user_id,
            self.view.display_name,
            self.view.selected_pool_id,
            self.draws,
        )
        selected_pool_id = result.pool.id if result.pool is not None else self.view.selected_pool_id
        await interaction.response.edit_message(
            embed=self.view.cog._gacha_embed(result),
            view=GachaView(self.view.cog, self.view.user_id, self.view.display_name, selected_pool_id),
        )
        if interaction.message is not None:
            await self.view.cog._sync_material_reactions(interaction.message, result.materials, interaction.guild)


class ExplorationView(discord.ui.View):
    def __init__(
        self,
        cog: RPGCog,
        user_id: int,
        display_name: str,
        selected_dungeon_id: str | None = None,
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        self.selected_dungeon_id = selected_dungeon_id
        profile = self.cog.service.get_profile(user_id, display_name)

        options = []
        for dungeon in self.cog.service.dungeons():
            gate = "입장 가능" if profile.level >= dungeon.level_req else f"Lv.{dungeon.level_req} 필요"
            rare_names = ", ".join(enemy.name for enemy in dungeon.enemies if enemy.rare) or "희귀 없음"
            options.append(
                discord.SelectOption(
                    label=f"{dungeon.name} · Lv.{dungeon.level_req}+",
                    value=dungeon.id,
                    description=f"{gate} · {rare_names}"[:100],
                    default=dungeon.id == selected_dungeon_id,
                )
            )
        if options:
            self.add_item(ExplorationDungeonSelect(options))

        remaining = self.cog.service.daily_remaining(profile)
        disabled = (
            selected_dungeon_id is None
            or (self.cog.service.explore_limit_enabled() and remaining <= 0)
        )
        self.add_item(ExplorationRunButton(disabled=disabled))
        self.add_item(ExplorationRunManyButton(7, disabled=disabled))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 탐색 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class ExplorationDungeonSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="탐색할 던전 선택",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, ExplorationView)
        dungeon_id = self.values[0]
        profile = self.view.cog.service.get_profile(self.view.user_id, self.view.display_name)
        view = ExplorationView(self.view.cog, self.view.user_id, self.view.display_name, dungeon_id)
        await interaction.response.edit_message(
            embed=self.view.cog._exploration_panel_embed(profile, dungeon_id),
            view=view,
        )


class ExplorationRunButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False) -> None:
        super().__init__(
            label="탐색",
            style=discord.ButtonStyle.primary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, ExplorationView)
        if self.view.selected_dungeon_id is None:
            await interaction.response.send_message("먼저 던전을 선택하세요.", ephemeral=True)
            return
        result = self.view.cog.service.explore(
            self.view.user_id,
            self.view.display_name,
            self.view.selected_dungeon_id,
        )
        view = ExplorationView(
            self.view.cog,
            self.view.user_id,
            self.view.display_name,
            self.view.selected_dungeon_id,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._explore_embed(result),
            view=view,
        )


class ExplorationRunManyButton(discord.ui.Button):
    def __init__(self, count: int, *, disabled: bool = False) -> None:
        self.count = count
        super().__init__(
            label=f"{count}회 탐색",
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, ExplorationView)
        if self.view.selected_dungeon_id is None:
            await interaction.response.send_message("먼저 던전을 선택하세요.", ephemeral=True)
            return
        result = self.view.cog.service.explore_many(
            self.view.user_id,
            self.view.display_name,
            self.view.selected_dungeon_id,
            self.count,
        )
        view = ExplorationView(
            self.view.cog,
            self.view.user_id,
            self.view.display_name,
            self.view.selected_dungeon_id,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._explore_batch_embed(result),
            view=view,
        )


class CraftingView(discord.ui.View):
    def __init__(
        self,
        cog: RPGCog,
        user_id: int,
        display_name: str,
        selected_recipe_id: str | None = None,
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        profile = self.cog.service.get_profile(user_id, display_name)
        recipes = self.cog._crafting_display_recipes(profile)
        self.selected_recipe_id = selected_recipe_id

        options = []
        for recipe in recipes:
            status = self.cog.service.recipe_status_text(profile, recipe)
            template = ITEM_BY_ID.get(recipe.result_item_id)
            rarity = RARITY_LABELS.get(template.rarity, template.rarity) if template is not None else "오류"
            options.append(
                discord.SelectOption(
                    label=f"{recipe.name} · Lv.{recipe.level_req}+",
                    value=recipe.id,
                    description=f"{status} · {rarity} · {recipe.gold}G"[:100],
                    default=recipe.id == self.selected_recipe_id,
                )
            )
        if options:
            self.add_item(CraftingRecipeSelect(options))
        selected = next((recipe for recipe in recipes if recipe.id == self.selected_recipe_id), None)
        self.add_item(CraftingConfirmButton(disabled=selected is None or not self.cog.service.can_craft(profile, selected)))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 제작 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class CraftingRecipeSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="제작할 장비 선택",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, CraftingView)
        recipe_id = self.values[0]
        profile = self.view.cog.service.get_profile(self.view.user_id, self.view.display_name)
        await interaction.response.edit_message(
            embed=self.view.cog._crafting_embed(profile, recipe_id),
            view=CraftingView(self.view.cog, self.view.user_id, self.view.display_name, recipe_id),
        )


class CraftingConfirmButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False) -> None:
        super().__init__(label="제작", style=discord.ButtonStyle.primary, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, CraftingView)
        if self.view.selected_recipe_id is None:
            await interaction.response.send_message("제작법을 선택하세요.", ephemeral=True)
            return
        result = self.view.cog.service.craft_item(
            self.view.user_id,
            self.view.display_name,
            self.view.selected_recipe_id,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._crafting_embed(result.profile, self.view.selected_recipe_id, result),
            view=CraftingView(self.view.cog, self.view.user_id, self.view.display_name, self.view.selected_recipe_id),
        )


class BossPanelView(discord.ui.View):
    def __init__(self, cog: RPGCog, user_id: int, display_name: str, selected_boss_id: str | None = None) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        self.selected_boss_id = selected_boss_id
        self.add_item(BossPanelSelect())
        self.add_item(BossPanelOpenButton(practice=False, disabled=selected_boss_id is None))
        self.add_item(BossPanelOpenButton(practice=True, disabled=selected_boss_id is None))

    async def _reject_other_user(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return False
        await interaction.response.send_message("이 보스 선택 패널을 연 사람만 조작할 수 있습니다.", ephemeral=True)
        return True

    async def _edit_panel(self, interaction: discord.Interaction) -> None:
        profile = self.cog.service.get_profile(self.user_id, self.display_name)
        await interaction.response.edit_message(
            embed=self.cog._boss_panel_embed(profile, self.selected_boss_id),
            view=BossPanelView(self.cog, self.user_id, self.display_name, self.selected_boss_id),
        )


class BossPanelSelect(discord.ui.Select):
    def __init__(self) -> None:
        options = [
            discord.SelectOption(
                label=boss.name[:100],
                value=boss.id,
                description=f"Lv.{boss.level_req}+",
            )
            for boss in BOSSES[:25]
        ]
        super().__init__(placeholder="보스 선택", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossPanelView)
        if await self.view._reject_other_user(interaction):
            return
        self.view.selected_boss_id = self.values[0]
        await self.view._edit_panel(interaction)


class BossPanelOpenButton(discord.ui.Button):
    def __init__(self, *, practice: bool, disabled: bool = False) -> None:
        self.practice = practice
        label = "연습 준비" if practice else "자발 준비"
        style = discord.ButtonStyle.secondary if practice else discord.ButtonStyle.primary
        super().__init__(label=label, style=style, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossPanelView)
        if await self.view._reject_other_user(interaction):
            return
        template = BOSS_BY_ID.get(self.view.selected_boss_id or "")
        if template is None:
            await interaction.response.send_message("보스를 먼저 선택하세요.", ephemeral=True)
            return
        session, message = self.view.cog._create_boss_session(
            template,
            self.view.user_id,
            self.view.display_name,
            practice=self.practice,
        )
        if session is None:
            await interaction.response.send_message(message, ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=self.view.cog._boss_session_embed(session),
            view=BossSessionView(self.view.cog, session),
        )
        if interaction.message is not None:
            session.message = interaction.message


class BossSessionView(discord.ui.View):
    def __init__(self, cog: RPGCog, session: BossSession) -> None:
        super().__init__(timeout=900)
        self.cog = cog
        self.session = session
        if session.completed or session.failed or session.cancelled:
            return
        if not session.started:
            self.add_item(BossJoinButton())
            self.add_item(BossStartButton())
            self.add_item(BossCancelButton())
            return
        self.add_item(BossAbilityMenuButton())
        self.add_item(BossGiveUpButton())

    async def _edit(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            embed=self.cog._boss_session_embed(self.session),
            view=BossSessionView(self.cog, self.session),
        )
        if interaction.message is not None:
            await self.cog._sync_material_reactions(
                interaction.message,
                self.session.reward_materials,
                interaction.guild,
            )


class BossJoinButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="참가", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView)
        ok, message = self.view.cog._add_boss_participant(
            self.view.session,
            interaction.user.id,
            interaction.user.display_name,
        )
        if not ok:
            if isinstance(self.view, BossAbilityView):
                await self.view._edit(interaction, message)
                return
            await interaction.response.send_message(message, ephemeral=True)
            return
        await self.view._edit(interaction)
        await self.view.cog._refresh_boss_damage_detail_message(self.view.session, interaction.user.id)


class BossStartButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="시작", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView)
        ok, message = self.view.cog._start_boss_session(self.view.session, interaction.user.id)
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return
        await self.view._edit(interaction)
        participant = self.view.session.participants.get(interaction.user.id)
        if participant is not None:
            profile = self.view.cog.service.get_profile(interaction.user.id, interaction.user.display_name)
            skills = self.view.cog.service.equipped_skills(profile)
            await interaction.followup.send(
                embed=self.view.cog._boss_ability_embed(self.view.session, participant, skills),
                view=BossAbilityView(
                    self.view.cog,
                    self.view.session,
                    interaction.user.id,
                    interaction.user.display_name,
                    skills,
                ),
                ephemeral=True,
                wait=True,
            )


class BossCancelButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="취소", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView)
        was_owner = interaction.user.id == self.view.session.owner_id
        selected_boss_id = self.view.session.boss.id
        ok, message = self.view.cog._cancel_waiting_boss_participation(
            self.view.session,
            interaction.user.id,
            interaction.user.display_name,
        )
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return
        if was_owner and self.view.session.cancelled:
            profile = self.view.cog.service.get_profile(interaction.user.id, interaction.user.display_name)
            await interaction.response.edit_message(
                embed=self.view.cog._boss_panel_embed(profile, selected_boss_id),
                view=BossPanelView(
                    self.view.cog,
                    interaction.user.id,
                    interaction.user.display_name,
                    selected_boss_id,
                ),
            )
            return
        await self.view._edit(interaction)


class BossGiveUpButton(discord.ui.Button):
    def __init__(self, *, row: int | None = None) -> None:
        super().__init__(label="포기", style=discord.ButtonStyle.danger, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView | BossAbilityView)
        user_id = self.view.user_id if isinstance(self.view, BossAbilityView) else interaction.user.id
        display_name = self.view.display_name if isinstance(self.view, BossAbilityView) else interaction.user.display_name
        ok, message = self.view.cog._give_up_boss_session(
            self.view.session,
            user_id,
            display_name,
        )
        if not ok:
            if isinstance(self.view, BossAbilityView):
                await self.view._edit(interaction, message)
                return
            await interaction.response.send_message(message, ephemeral=True)
            return
        if isinstance(self.view, BossAbilityView):
            await self.view.cog._refresh_boss_public_message(self.view.session)
            await self.view._edit(interaction, message)
            return
        await self.view._edit(interaction)


class BossAttackButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False, row: int | None = None) -> None:
        super().__init__(label="공격", style=discord.ButtonStyle.danger, disabled=disabled, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView | BossAbilityView)
        user_id = self.view.user_id if isinstance(self.view, BossAbilityView) else interaction.user.id
        display_name = self.view.display_name if isinstance(self.view, BossAbilityView) else interaction.user.display_name
        ok, message = self.view.cog._boss_attack(
            self.view.session,
            user_id,
            display_name,
        )
        if not ok:
            if isinstance(self.view, BossAbilityView):
                await self.view._edit(interaction, message)
                return
            await interaction.response.send_message(message, ephemeral=True)
            return
        if isinstance(self.view, BossAbilityView):
            await self.view.cog._refresh_boss_public_message(self.view.session)
            await self.view._edit(interaction, message)
        else:
            await self.view._edit(interaction)
        await self.view.cog._refresh_boss_damage_detail_message(self.view.session, user_id)


class BossGuardButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False, row: int | None = None) -> None:
        super().__init__(label="가드", style=discord.ButtonStyle.primary, disabled=disabled, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView | BossAbilityView)
        user_id = self.view.user_id if isinstance(self.view, BossAbilityView) else interaction.user.id
        display_name = self.view.display_name if isinstance(self.view, BossAbilityView) else interaction.user.display_name
        ok, message = self.view.cog._boss_guard(
            self.view.session,
            user_id,
            display_name,
        )
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return
        if isinstance(self.view, BossAbilityView):
            await self.view.cog._refresh_boss_public_message(self.view.session)
            await self.view._edit(interaction, message)
        else:
            await self.view._edit(interaction)
        await self.view.cog._refresh_boss_damage_detail_message(self.view.session, user_id)


class BossAbilityMenuButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="개인 패널", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView)
        participant = self.view.session.participants.get(interaction.user.id)
        if participant is None:
            await interaction.response.send_message("이 보스전에 참가하지 않았습니다.", ephemeral=True)
            return
        if (
            not self.view.session.started
            or self.view.session.completed
            or self.view.session.failed
            or self.view.session.cancelled
        ):
            await interaction.response.send_message("진행 중인 보스전이 아닙니다.", ephemeral=True)
            return
        self.view.session.message = interaction.message
        profile = self.view.cog.service.get_profile(interaction.user.id, interaction.user.display_name)
        skills = self.view.cog.service.equipped_skills(profile)
        await interaction.message.edit(
            embed=self.view.cog._boss_session_embed(self.view.session),
            view=BossSessionView(self.view.cog, self.view.session),
        )
        await interaction.response.send_message(
            embed=self.view.cog._boss_ability_embed(self.view.session, participant, skills),
            view=BossAbilityView(self.view.cog, self.view.session, interaction.user.id, interaction.user.display_name, skills),
            ephemeral=True,
        )


class BossDamageDetailButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False, row: int | None = None) -> None:
        super().__init__(label="딜 상세", style=discord.ButtonStyle.secondary, disabled=disabled, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView | BossAbilityView)
        user_id = self.view.user_id if isinstance(self.view, BossAbilityView) else interaction.user.id
        participant = self.view.session.participants.get(user_id)
        if participant is None:
            await interaction.response.send_message("이 보스전에 참가하지 않았습니다.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=self.view.cog._boss_damage_detail_embed(self.view.session, participant),
            ephemeral=True,
        )
        self.view.cog._boss_damage_detail_messages[(self.view.session.id, user_id)] = (
            await interaction.original_response()
        )


class BossAbilityView(discord.ui.View):
    def __init__(
        self,
        cog: RPGCog,
        session: BossSession,
        user_id: int,
        display_name: str,
        skills: list[SkillTemplate],
    ) -> None:
        super().__init__(timeout=120)
        self.cog = cog
        self.session = session
        self.user_id = user_id
        self.display_name = display_name
        participant = session.participants.get(user_id)
        controls_disabled = (
            participant is None
            or not participant.alive
            or not session.started
            or session.completed
            or session.failed
            or session.cancelled
        )
        self.add_item(BossAttackButton(disabled=controls_disabled, row=0))
        self.add_item(BossGuardButton(disabled=controls_disabled, row=0))
        self.add_item(BossDamageDetailButton(disabled=participant is None, row=0))
        for skill in skills[:MAX_EQUIPPED_SKILLS]:
            cooldown = participant.ability_cooldowns.get(skill.id, 0) if participant is not None else 0
            used_out = participant is not None and self.cog._ability_used_out(participant, skill)
            self.add_item(BossAbilityButton(skill, disabled=controls_disabled or cooldown > 0 or used_out, row=1))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 개인 패널은 본인만 사용할 수 있습니다.", ephemeral=True)
        return False

    async def _edit(self, interaction: discord.Interaction, message: str | None = None) -> None:
        participant = self.session.participants.get(self.user_id)
        if participant is None:
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title="개인 전투 패널",
                    description="이 보스전에 참가하지 않았습니다.",
                    color=0xED4245,
                ),
                view=None,
            )
            return
        profile = self.cog.service.get_profile(self.user_id, self.display_name)
        skills = self.cog.service.equipped_skills(profile)
        view = None
        if (
            self.session.started
            and not self.session.completed
            and not self.session.failed
            and not self.session.cancelled
            and participant.alive
        ):
            view = BossAbilityView(self.cog, self.session, self.user_id, self.display_name, skills)
        await interaction.response.edit_message(
            embed=self.cog._boss_ability_embed(self.session, participant, skills, message),
            view=view,
        )


class BossAbilityButton(discord.ui.Button):
    def __init__(self, skill: SkillTemplate, *, disabled: bool = False, row: int | None = None) -> None:
        super().__init__(
            label=skill.name[:80],
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
            row=row,
        )
        self.skill = skill

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossAbilityView)
        ok, message = self.view.cog._boss_use_ability(
            self.view.session,
            self.view.user_id,
            self.view.display_name,
            self.skill.id,
        )
        await self.view.cog._refresh_boss_public_message(self.view.session)
        await self.view._edit(interaction, message)
        await self.view.cog._refresh_boss_damage_detail_message(self.view.session, self.view.user_id)


class EquipmentView(discord.ui.View):
    def __init__(
        self,
        cog: RPGCog,
        user_id: int,
        display_name: str,
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        profile = self.cog.service.get_profile(user_id, display_name)

        options = []
        equipped_ids = {item.uid for item in self.cog.service.equipped_items(profile)}
        for item in self.cog._equipment_display_items(profile):
            template = ITEM_BY_ID.get(item.template_id)
            if template is None:
                continue
            marker = "장착" if item.uid in equipped_ids else "보유"
            if item.destroyed:
                marker = "파괴됨"
            options.append(
                discord.SelectOption(
                    label=self.cog._item_select_label(item),
                    value=str(item.uid),
                    description=self.cog._item_option_description(marker, item),
                    emoji=self.cog._rarity_emoji(template.rarity),
                    default=item.uid in profile.equipped_item_uids,
                )
            )
        if options:
            self.add_item(EquipmentSelect(options))
        self.add_item(EquipmentBestButton(disabled=not options))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 장착 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class EquipmentSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="장착할 장비를 최대 4개까지 선택",
            min_values=0,
            max_values=min(MAX_EQUIPPED_ITEMS, len(options)),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, EquipmentView)
        uids = [int(value) for value in self.values]
        result = self.view.cog.service.set_equipped_items(
            self.view.user_id,
            self.view.display_name,
            uids,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._equipment_embed(result.profile, result=result),
            view=EquipmentView(self.view.cog, self.view.user_id, self.view.display_name),
        )


class EquipmentBestButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False) -> None:
        super().__init__(
            label="최강 자동 장착",
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, EquipmentView)
        result = self.view.cog.service.auto_equip_best(
            self.view.user_id,
            self.view.display_name,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._equipment_embed(result.profile, result=result),
            view=EquipmentView(self.view.cog, self.view.user_id, self.view.display_name),
        )


class SellView(discord.ui.View):
    def __init__(
        self,
        cog: RPGCog,
        user_id: int,
        display_name: str,
        selected_uids: list[int] | None = None,
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        self.selected_uids = selected_uids or []
        profile = self.cog.service.get_profile(user_id, display_name)
        options = []
        for item in self.cog._sellable_items(profile):
            template = ITEM_BY_ID.get(item.template_id)
            if template is None:
                continue
            options.append(
                discord.SelectOption(
                    label=f"{template.name} +{item.stars}"[:100],
                    value=str(item.uid),
                    description=f"{RARITY_LABELS[template.rarity]} · {self.cog.service.item_sell_price(item)}G"[:100],
                    default=item.uid in self.selected_uids,
                )
            )
        if options:
            self.add_item(SellSelect(options))
        self.add_item(SellConfirmButton(disabled=not self.selected_uids))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 판매 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class SellSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="판매할 장비 선택",
            min_values=0,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, SellView)
        uids = [int(value) for value in self.values]
        profile = self.view.cog.service.get_profile(self.view.user_id, self.view.display_name)
        view = SellView(self.view.cog, self.view.user_id, self.view.display_name, uids)
        await interaction.response.edit_message(
            embed=self.view.cog._sell_embed(profile, uids),
            view=view,
        )


class SellConfirmButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False) -> None:
        super().__init__(label="선택 판매", style=discord.ButtonStyle.danger, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, SellView)
        result = self.view.cog.service.sell_items_by_uids(
            self.view.user_id,
            self.view.display_name,
            self.view.selected_uids,
        )
        view = SellView(self.view.cog, self.view.user_id, self.view.display_name)
        await interaction.response.edit_message(
            embed=self.view.cog._sell_embed(result.profile, result=result),
            view=view,
        )


class AutoSellView(discord.ui.View):
    def __init__(self, cog: RPGCog, user_id: int, display_name: str) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        profile = self.cog.service.get_profile(user_id, display_name)
        options = [
            discord.SelectOption(
                label=RARITY_LABELS[rarity],
                value=rarity,
                description=f"{RARITY_LABELS[rarity]} 장비 드랍 시 즉시 판매",
                default=rarity in profile.auto_sell_rarities,
            )
            for rarity in RARITIES
        ]
        self.add_item(AutoSellSelect(options))
        self.add_item(AutoSellBulkButton(disabled=not self.cog._auto_sell_candidate_items(profile)))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 자동판매 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class AutoSellSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="자동판매 등급 선택",
            min_values=0,
            max_values=len(options),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, AutoSellView)
        result = self.view.cog.service.set_auto_sell_rarities(
            self.view.user_id,
            self.view.display_name,
            list(self.values),
        )
        await interaction.response.edit_message(
            embed=self.view.cog._auto_sell_embed(result.profile, result),
            view=AutoSellView(self.view.cog, self.view.user_id, self.view.display_name),
        )


class AutoSellBulkButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False) -> None:
        super().__init__(
            label="현재 장비 일괄 판매",
            style=discord.ButtonStyle.danger,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, AutoSellView)
        result = self.view.cog.service.sell_auto_sell_items(
            self.view.user_id,
            self.view.display_name,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._auto_sell_embed(result.profile, result),
            view=AutoSellView(self.view.cog, self.view.user_id, self.view.display_name),
        )


class AbilityEquipView(discord.ui.View):
    def __init__(
        self,
        cog: RPGCog,
        user_id: int,
        display_name: str,
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        profile = self.cog.service.get_profile(user_id, display_name)
        equipped = [skill.id for skill in self.cog.service.equipped_skills(profile)]
        options = [
            discord.SelectOption(
                label=skill.name,
                value=skill.id,
                description=self.cog.service.skill_summary(skill)[:100],
                default=skill.id in equipped,
            )
            for skill in self.cog.service.unlocked_skills(profile)
        ]
        if options:
            self.add_item(AbilityEquipSelect(options))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 어빌리티 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class AbilityEquipSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="장착할 어빌리티 선택",
            min_values=0,
            max_values=min(MAX_EQUIPPED_SKILLS, len(options)),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, AbilityEquipView)
        active_session = self.view.cog._active_boss_session_for_user(self.view.user_id, started_only=True)
        if active_session is not None:
            await interaction.response.send_message(
                f"{active_session.boss.name} 보스전 진행 중에는 어빌리티 장착을 바꿀 수 없습니다.",
                ephemeral=True,
            )
            return
        selected = list(self.values)
        result = self.view.cog.service.set_equipped_skills(
            self.view.user_id,
            self.view.display_name,
            selected,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._ability_embed(result.profile, result),
            view=AbilityEquipView(self.view.cog, self.view.user_id, self.view.display_name),
        )


class EnhancementView(discord.ui.View):
    def __init__(
        self,
        cog: RPGCog,
        user_id: int,
        display_name: str,
        selected_uid: int | None = None,
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        self.selected_uid = selected_uid
        profile = self.cog.service.get_profile(user_id, display_name)
        selected_item = self.cog._profile_item(profile, selected_uid)
        if selected_item is not None and selected_item.destroyed:
            selected_item = None
            self.selected_uid = None
        options = []
        equipped_ids = {item.uid for item in self.cog.service.equipped_items(profile)}
        for item in self.cog._enhancement_display_items(profile):
            template = ITEM_BY_ID.get(item.template_id)
            if template is None:
                continue
            marker = "장착" if item.uid in equipped_ids else "보유"
            options.append(
                discord.SelectOption(
                    label=self.cog._item_select_label(item),
                    value=str(item.uid),
                    description=self.cog._item_option_description(marker, item),
                    emoji=self.cog._rarity_emoji(template.rarity),
                    default=item.uid == self.selected_uid,
                )
            )
        if options:
            self.add_item(EnhancementSelect(options))
        self.add_item(EnhancementConfirmButton(disabled=selected_item is None))
        self.add_item(OpenRestoreViewButton(disabled=not self.cog._restore_trace_display_items(profile)))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 강화 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class EnhancementSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="강화할 장비 선택",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, EnhancementView)
        uid = int(self.values[0])
        view = EnhancementView(self.view.cog, self.view.user_id, self.view.display_name, uid)
        await interaction.response.edit_message(
            embed=self.view.cog._enhancement_preview_embed(
                self.view.cog.service.enhancement_preview(self.view.user_id, self.view.display_name, uid)
            ),
            view=view,
        )


class EnhancementConfirmButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False) -> None:
        super().__init__(
            label="강화",
            style=discord.ButtonStyle.primary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, EnhancementView)
        if self.view.selected_uid is None:
            await interaction.response.send_message("먼저 장비를 선택하세요.", ephemeral=True)
            return
        result = self.view.cog.service.enhance(
            self.view.user_id,
            self.view.display_name,
            self.view.selected_uid,
        )
        selected_uid = result.item.uid if result.item is not None and not result.item.destroyed else None
        view = EnhancementView(self.view.cog, self.view.user_id, self.view.display_name, selected_uid)
        next_preview = (
            self.view.cog.service.enhancement_preview(
                self.view.user_id,
                self.view.display_name,
                selected_uid,
            )
            if selected_uid is not None
            else None
        )
        await interaction.response.edit_message(
            embed=self.view.cog._enhance_result_embed(result, next_preview),
            view=view,
        )


class OpenRestoreViewButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False) -> None:
        super().__init__(label="흔적 복구", style=discord.ButtonStyle.secondary, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, EnhancementView)
        view = RestoreView(self.view.cog, self.view.user_id, self.view.display_name)
        await interaction.response.edit_message(
            embed=self.view.cog._restore_panel_embed(
                self.view.user_id,
                self.view.display_name,
                view.selected_trace_uid,
                view.selected_spare_uid,
            ),
            view=view,
        )


class RestoreView(discord.ui.View):
    def __init__(
        self,
        cog: RPGCog,
        user_id: int,
        display_name: str,
        selected_trace_uid: int | None = None,
        selected_spare_uid: int | None = None,
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        profile = self.cog.service.get_profile(user_id, display_name)
        selected_trace = self.cog._profile_item(profile, selected_trace_uid)
        if selected_trace is None or not selected_trace.destroyed:
            selected_trace = None
        self.selected_trace_uid = selected_trace.uid if selected_trace is not None else None

        trace_items = self.cog._restore_trace_display_items(profile)
        if selected_trace is not None and all(item.uid != selected_trace.uid for item in trace_items):
            trace_items = [selected_trace, *trace_items[:24]]
        trace_options = []
        for item in trace_items:
            template = ITEM_BY_ID.get(item.template_id)
            if template is None:
                continue
            trace_options.append(
                discord.SelectOption(
                    label=self.cog._item_select_label(item),
                    value=str(item.uid),
                    description=f"흔적 · 복구 비용 확인"[:100],
                    emoji=self.cog._rarity_emoji(template.rarity),
                    default=item.uid == self.selected_trace_uid,
                )
            )
        if trace_options:
            self.add_item(RestoreTraceSelect(trace_options))

        spare_items = self.cog._restore_spare_display_items(profile, selected_trace) if selected_trace is not None else []
        if selected_spare_uid is not None and all(item.uid != selected_spare_uid for item in spare_items):
            selected_spare_uid = None
        if selected_spare_uid is None and spare_items:
            selected_spare_uid = spare_items[0].uid
        self.selected_spare_uid = selected_spare_uid
        spare_options = []
        equipped_ids = set(profile.equipped_item_uids)
        for item in spare_items:
            template = ITEM_BY_ID.get(item.template_id)
            if template is None:
                continue
            marker = "장착" if item.uid in equipped_ids else "보유"
            spare_options.append(
                discord.SelectOption(
                    label=self.cog._item_select_label(item),
                    value=str(item.uid),
                    description=self.cog._item_option_description(marker, item, "소모됨"),
                    emoji=self.cog._rarity_emoji(template.rarity),
                    default=item.uid == self.selected_spare_uid,
                )
            )
        if spare_options:
            self.add_item(RestoreSpareSelect(spare_options))

        preview = (
            self.cog.service.restore_preview(user_id, display_name, self.selected_trace_uid, self.selected_spare_uid)
            if self.selected_trace_uid is not None
            else None
        )
        self.add_item(RestoreConfirmButton(disabled=preview is None or not preview.ok))
        self.add_item(BackToEnhancementButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 복구 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class RestoreTraceSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="복구할 흔적 선택",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, RestoreView)
        trace_uid = int(self.values[0])
        view = RestoreView(self.view.cog, self.view.user_id, self.view.display_name, trace_uid)
        await interaction.response.edit_message(
            embed=self.view.cog._restore_panel_embed(
                self.view.user_id,
                self.view.display_name,
                view.selected_trace_uid,
                view.selected_spare_uid,
            ),
            view=view,
        )


class RestoreSpareSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="소모할 스페어 선택",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, RestoreView)
        spare_uid = int(self.values[0])
        view = RestoreView(
            self.view.cog,
            self.view.user_id,
            self.view.display_name,
            self.view.selected_trace_uid,
            spare_uid,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._restore_panel_embed(
                self.view.user_id,
                self.view.display_name,
                view.selected_trace_uid,
                view.selected_spare_uid,
            ),
            view=view,
        )


class RestoreConfirmButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False) -> None:
        super().__init__(label="복구", style=discord.ButtonStyle.primary, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, RestoreView)
        if self.view.selected_trace_uid is None or self.view.selected_spare_uid is None:
            await interaction.response.send_message("복구할 흔적과 소모할 스페어를 선택하세요.", ephemeral=True)
            return
        result = self.view.cog.service.restore(
            self.view.user_id,
            self.view.display_name,
            self.view.selected_trace_uid,
            self.view.selected_spare_uid,
        )
        view = RestoreView(self.view.cog, self.view.user_id, self.view.display_name)
        await interaction.response.edit_message(
            embed=self.view.cog._restore_panel_embed(
                self.view.user_id,
                self.view.display_name,
                view.selected_trace_uid,
                view.selected_spare_uid,
                result,
            ),
            view=view,
        )


class BackToEnhancementButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="강화로 돌아가기", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, RestoreView)
        profile = self.view.cog.service.get_profile(self.view.user_id, self.view.display_name)
        await interaction.response.edit_message(
            embed=self.view.cog._enhancement_picker_embed(profile),
            view=EnhancementView(self.view.cog, self.view.user_id, self.view.display_name),
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RPGCog(bot))
