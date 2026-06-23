from __future__ import annotations

from dataclasses import dataclass, field

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.rpg.data import (
    BOSS_BY_ID,
    BOSSES,
    CRAFTING_RECIPES,
    DAILY_EXPLORES,
    DUNGEONS,
    ITEM_BY_ID,
    JOBS,
    MATERIALS,
    MAX_EQUIPPED_ITEMS,
    RARITIES,
    RARITY_COLORS,
    RARITY_LABELS,
    STAT_ALLOCATIONS,
    BossPattern,
    BossTemplate,
    SkillTemplate,
)
from bot.services.rpg.manager import (
    ActiveEffect,
    AbilityResult,
    BossResult,
    CraftResult,
    EnhancementPreview,
    EnhancementResult,
    EquipmentResult,
    ExploreResult,
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
JOB_CHOICES = [
    app_commands.Choice(name=f"{job.name} · Lv.{job.level_req}+", value=job.id)
    for job in JOBS
    if job.id != "novice"
]
STAT_CHOICES = [
    app_commands.Choice(name=str(rule.get("choice_name", rule.get("label", stat_id))), value=stat_id)
    for stat_id, rule in STAT_ALLOCATIONS.items()
]
CRAFT_CHOICES = [
    app_commands.Choice(name=f"{recipe.name} · Lv.{recipe.level_req}+", value=recipe.id)
    for recipe in CRAFTING_RECIPES[:25]
]

OBJECTIVE_LABELS = {
    "damage": "피해",
    "hits": "타수",
    "debuff": "디버프",
}


@dataclass
class BossWarning:
    source: str
    name: str
    pattern: BossPattern
    objective: str
    required: int
    progress: int = 0
    threshold: float | None = None


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
    player_effects: list[ActiveEffect] = field(default_factory=list)
    ability_cooldowns: dict[str, int] = field(default_factory=dict)


@dataclass
class BossSession:
    id: int
    boss: BossTemplate
    owner_id: int
    boss_hp: int = 0
    boss_max_hp: int = 0
    ct_max: int = 4
    started: bool = False
    completed: bool = False
    failed: bool = False
    boss_effects: list[ActiveEffect] = field(default_factory=list)
    participants: dict[int, BossParticipant] = field(default_factory=dict)
    rewards: dict[int, str] = field(default_factory=dict)
    log: list[str] = field(default_factory=list)
    message: discord.Message | None = None

    def __post_init__(self) -> None:
        self.boss_max_hp = max(1, int(self.boss.stats.get("max_hp", 1)))
        self.boss_hp = self.boss_max_hp
        self.ct_max = self.boss.ct_gauge[0].max if self.boss.ct_gauge else max(3, 7 - min(4, self.boss.rank))


class RPGCog(commands.Cog):
    rpg = app_commands.Group(name="rpg", description="가볍게 즐기는 던전/보스 RPG")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = RPGService()
        self.boss_sessions: dict[int, BossSession] = {}
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
                f"{enemy.name}: {self.service.reward_summary(enemy.rewards)}"
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

    @rpg.command(name="탐색", description="던전을 선택해 제한 없이 탐색합니다.")
    @app_commands.rename(dungeon="던전")
    @app_commands.describe(dungeon="탐색할 던전. 비워두면 선택 UI를 표시합니다.")
    @app_commands.choices(dungeon=DUNGEON_CHOICES)
    async def explore(
        self,
        interaction: discord.Interaction,
        dungeon: app_commands.Choice[str] | None = None,
    ) -> None:
        if dungeon is None:
            profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
            embed = self._exploration_panel_embed(profile)
            view = ExplorationView(self, interaction.user.id, interaction.user.display_name)
            await interaction.response.send_message(embed=embed, view=view)
            return
        result = self.service.explore(
            interaction.user.id,
            interaction.user.display_name,
            dungeon.value,
        )
        view = ExplorationView(self, interaction.user.id, interaction.user.display_name, dungeon.value)
        await interaction.response.send_message(embed=self._explore_embed(result), view=view)

    @rpg.command(name="보스목록", description="도전 가능한 보스와 보상 정보를 봅니다.")
    async def boss_list(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        lines = []
        for boss in self.service.bosses():
            gate = "도전 가능" if profile.level >= boss.level_req else f"Lv.{boss.level_req} 필요"
            lines.append(
                f"**{boss.name}** · {gate}\n"
                f"보상 {self.service.reward_summary(boss.rewards)} · {boss.description}"
            )
        embed = discord.Embed(
            title="보스 목록",
            description="테스트 단계에서는 보스 클리어 보상 제한이 없습니다. 보스전은 버튼 턴제로 진행됩니다.",
            color=0xFFB84D,
        )
        embed.add_field(name="보스", value="\n\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed)

    @rpg.command(name="보스", description="보스를 선택해 버튼 턴제 전투를 시작합니다.")
    @app_commands.rename(boss="보스")
    @app_commands.describe(boss="도전할 보스")
    @app_commands.choices(boss=BOSS_CHOICES)
    async def boss(
        self,
        interaction: discord.Interaction,
        boss: app_commands.Choice[str],
    ) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        template = BOSS_BY_ID.get(boss.value)
        if template is None:
            await interaction.response.send_message(
                embed=discord.Embed(title="보스 도전 실패", description="알 수 없는 보스입니다.", color=0xED4245)
            )
            return
        if profile.level < template.level_req:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="보스 도전 실패",
                    description=f"{template.name}은 Lv.{template.level_req}부터 도전할 수 있습니다.",
                    color=0xED4245,
                )
            )
            return

        session_id = self._next_boss_session_id
        self._next_boss_session_id += 1
        session = BossSession(session_id, template, interaction.user.id)
        self._add_boss_participant(session, interaction.user.id, interaction.user.display_name)
        self.boss_sessions[session_id] = session
        await interaction.response.send_message(
            embed=self._boss_session_embed(session),
            view=BossSessionView(self, session),
        )
        session.message = await interaction.original_response()

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
    @app_commands.describe(job="전직할 직업")
    @app_commands.choices(job=JOB_CHOICES)
    async def advance_job(
        self,
        interaction: discord.Interaction,
        job: app_commands.Choice[str],
    ) -> None:
        result = self.service.advance_job(
            interaction.user.id,
            interaction.user.display_name,
            job.value,
        )
        color = 0x57F287 if result.ok else 0xED4245
        embed = discord.Embed(title="전직", description=result.message, color=color)
        embed.add_field(name="현재 직업", value=self.service.current_job(result.profile).name, inline=True)
        embed.add_field(name="전투 스탯", value=self.service.format_stats(self.service.profile_stats(result.profile)), inline=False)
        skills = self.service.unlocked_skills(result.profile)
        embed.add_field(
            name="사용 가능한 스킬",
            value=self._trim("\n".join(f"**{skill.name}** · {self.service.skill_summary(skill)}" for skill in skills), 1000),
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

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
        selected_recipe_id = recipe.value if recipe is not None else self._default_crafting_recipe_id(profile)
        await interaction.response.send_message(
            embed=self._crafting_embed(profile, selected_recipe_id),
            view=CraftingView(self, interaction.user.id, interaction.user.display_name, selected_recipe_id),
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

    @rpg.command(name="어빌리티", description="전투와 보스전에 사용할 어빌리티 3개를 장착합니다.")
    async def abilities(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
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
    @app_commands.rename(uid="장비_uid")
    @app_commands.describe(uid="바로 확인할 장비 UID. 비워두면 선택 UI를 표시합니다.")
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
        view = EnhancementView(self, interaction.user.id, interaction.user.display_name, uid)
        if uid is None:
            embed = self._enhancement_picker_embed(profile)
        else:
            embed = self._enhancement_preview_embed(
                self.service.enhancement_preview(interaction.user.id, interaction.user.display_name, uid)
            )
        await interaction.response.send_message(embed=embed, view=view)

    @rpg.command(name="복구", description="파괴된 장비 흔적을 +0 상태로 복구합니다.")
    @app_commands.rename(uid="장비_uid")
    @app_commands.describe(uid="복구할 장비 UID")
    async def restore(self, interaction: discord.Interaction, uid: int) -> None:
        result = self.service.restore(interaction.user.id, interaction.user.display_name, uid)
        await interaction.response.send_message(embed=self._enhance_result_embed(result))

    @rpg.command(name="스탯", description="원하는 수량만큼 스탯 포인트를 한 번에 투자합니다.")
    @app_commands.rename(stat="스탯", amount="수량")
    @app_commands.describe(stat="투자할 스탯", amount="사용할 포인트 수")
    @app_commands.choices(stat=STAT_CHOICES)
    async def allocate_stat(
        self,
        interaction: discord.Interaction,
        stat: app_commands.Choice[str],
        amount: int = 1,
    ) -> None:
        result = self.service.allocate_stat(
            interaction.user.id,
            interaction.user.display_name,
            stat.value,
            amount,
        )
        color = 0x57F287 if result.ok else 0xED4245
        embed = discord.Embed(title="스탯 투자", description=result.message, color=color)
        embed.add_field(name="남은 포인트", value=f"{result.profile.stat_points}", inline=True)
        embed.add_field(name="현재 전투 스탯", value=self.service.format_stats(self.service.profile_stats(result.profile)), inline=False)
        await interaction.response.send_message(embed=embed)

    def _add_boss_participant(self, session: BossSession, user_id: int, display_name: str) -> tuple[bool, str]:
        if session.started:
            return False, "이미 시작된 보스전에는 참가할 수 없습니다."
        if user_id in session.participants:
            return True, "이미 참가 중입니다."
        profile = self.service.get_profile(user_id, display_name)
        if profile.level < session.boss.level_req:
            return False, f"{session.boss.name}은 Lv.{session.boss.level_req}부터 참가할 수 있습니다."
        stats = self.service.profile_stats(profile)
        session.participants[user_id] = BossParticipant(
            user_id=user_id,
            display_name=display_name,
            hp=stats.final_hp,
            max_hp=stats.final_hp,
        )
        session.log.append(f"{display_name} 참가")
        return True, "참가했습니다."

    def _start_boss_session(self, session: BossSession, user_id: int) -> tuple[bool, str]:
        if user_id != session.owner_id:
            return False, "보스전을 만든 사람만 시작할 수 있습니다."
        if session.started:
            return True, "이미 시작되었습니다."
        if not session.participants:
            return False, "참가자가 없습니다."
        session.started = True
        session.log.append("보스전 시작")
        return True, "보스전을 시작했습니다."

    def _boss_use_ability(self, session: BossSession, user_id: int, display_name: str, skill_id: str) -> tuple[bool, str]:
        participant = session.participants.get(user_id)
        if participant is None:
            return False, "이 보스전에 참가하지 않았습니다."
        if not session.started or session.completed or session.failed:
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

        had_warning = participant.pending_warning is not None
        self._prepare_visible_warning(session, participant, profile)
        player_base = self.service.profile_stats(profile)
        player_stats = self.service._stats_with_effects(player_base, participant.player_effects)
        boss_base = self.service._enemy_stats(session.boss.stats)
        boss_stats = self.service._stats_with_effects(boss_base, session.boss_effects)
        damage, heal = self.service._use_player_skill(
            skill,
            player_stats,
            boss_stats,
            participant.hp,
            session.boss_hp,
            participant.player_effects,
            session.boss_effects,
        )
        if heal > 0:
            participant.hp = min(participant.max_hp, participant.hp + heal)
        if damage > 0:
            session.boss_hp = max(0, session.boss_hp - damage)
        self._add_warning_progress(participant, "damage", damage)
        self._add_warning_progress(participant, "hits", skill.hits if damage > 0 else 0)
        self._add_warning_progress(participant, "debuff", 1 if skill.enemy_mods else 0)
        cleared_ct_warning = self._clear_ready_ct_warning(session, participant)
        if skill.cooldown > 0:
            participant.ability_cooldowns[skill.id] = skill.cooldown
        bits = []
        if damage > 0:
            bits.append(f"{damage} 피해")
        if skill.hits > 0:
            bits.append(f"{skill.hits}타")
        if skill.enemy_mods:
            bits.append("디버프 1회")
        if heal > 0:
            bits.append(f"{heal} 회복")
        if not bits:
            bits.append("효과 발동")
        session.log.append(f"{participant.display_name}: {skill.name} · {', '.join(bits)}")
        if session.boss_hp <= 0:
            session.completed = True
            self._grant_boss_session_rewards(session)
            return True, "어빌리티로 보스를 클리어했습니다."
        self._queue_due_hp_warnings(session, participant, profile)
        self._queue_ct_warning(session, participant, profile)
        if cleared_ct_warning:
            return True, f"{skill.name} 사용: {', '.join(bits)} · CT 전조 해제"
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
        if not participant.alive:
            return False, "전투 불능 상태입니다."

        had_warning = participant.pending_warning is not None
        profile = self.service.get_profile(user_id, display_name)
        self._prepare_visible_warning(session, participant, profile)
        if participant.pending_warning is not None and not had_warning:
            return True, "전조가 발생했습니다. 어빌리티로 조건을 채운 뒤 공격하세요."
        player_base = self.service.profile_stats(profile)
        player_stats = self.service._stats_with_effects(player_base, participant.player_effects)
        boss_base = self.service._enemy_stats(session.boss.stats)
        boss_stats = self.service._stats_with_effects(boss_base, session.boss_effects)

        damage = self.service._actual_damage(
            player_stats,
            participant.hp,
            boss_stats,
            session.boss_hp,
        )
        session.boss_hp = max(0, session.boss_hp - damage)
        self._add_warning_progress(participant, "damage", damage)
        self._add_warning_progress(participant, "hits", 1)
        session.log.append(f"{participant.display_name}: 공격 {damage} 피해")

        if session.boss_hp <= 0:
            session.completed = True
            self._grant_boss_session_rewards(session)
            return True, "보스를 클리어했습니다."

        pattern_replaced_counter = False
        resolved_ct_warning = False
        if participant.pending_warning is not None:
            warning = participant.pending_warning
            resolved_ct_warning = warning.source == "ct"
            if warning.progress >= warning.required:
                session.log.append(f"{participant.display_name}: {warning.name} 전조 달성")
            else:
                boss_stats = self.service._stats_with_effects(boss_base, session.boss_effects)
                player_stats = self.service._stats_with_effects(player_base, participant.player_effects)
                pattern_damage = self.service._use_boss_pattern(
                    warning.pattern,
                    boss_stats,
                    player_stats,
                    session.boss_hp,
                    participant.hp,
                    participant.player_effects,
                    session.boss_effects,
                )
                if pattern_damage > 0:
                    participant.hp = max(0, participant.hp - pattern_damage)
                    session.log.append(
                        f"{participant.display_name}: {warning.name} 실패, {pattern_damage} 피해"
                    )
                else:
                    session.log.append(f"{participant.display_name}: {warning.name} 실패, 특수 효과 발동")
                pattern_replaced_counter = True
                if participant.hp <= 0:
                    participant.alive = False
            participant.pending_warning = None
            if resolved_ct_warning:
                participant.ct = 0
            if not participant.alive:
                self._check_boss_party_failed(session)
                return True, "전조 실패로 전투 불능이 되었습니다."

        boss_stats = self.service._stats_with_effects(boss_base, session.boss_effects)
        player_stats = self.service._stats_with_effects(player_base, participant.player_effects)
        if not pattern_replaced_counter:
            counter_damage = self.service._actual_damage(
                boss_stats,
                session.boss_hp,
                player_stats,
                participant.hp,
                0.48,
            )
            participant.hp = max(0, participant.hp - counter_damage)
            session.log.append(f"{session.boss.name}: {participant.display_name}에게 {counter_damage} 반격")
            if participant.hp <= 0:
                participant.alive = False
                session.log.append(f"{participant.display_name}: 전투 불능")
                self._check_boss_party_failed(session)
                return True, "전투 불능 상태가 되었습니다."

        self._advance_ct(session, participant, resolved_ct_warning)
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
        if not participant.alive:
            return False, "전투 불능 상태입니다."

        had_warning = participant.pending_warning is not None
        profile = self.service.get_profile(user_id, display_name)
        self._prepare_visible_warning(session, participant, profile)
        if participant.pending_warning is not None and not had_warning:
            return True, "전조가 발생했습니다. 어빌리티로 조건을 채운 뒤 가드할 수 있습니다."

        player_base = self.service.profile_stats(profile)
        boss_base = self.service._enemy_stats(session.boss.stats)
        boss_stats = self.service._stats_with_effects(boss_base, session.boss_effects)
        guard_stats = self.service._stats_with_effects(player_base, participant.player_effects)
        self.service._apply_stat(guard_stats, "defense", 10.0)
        session.log.append(f"{participant.display_name}: 가드")

        pattern_replaced_counter = False
        resolved_ct_warning = False
        if participant.pending_warning is not None:
            warning = participant.pending_warning
            resolved_ct_warning = warning.source == "ct"
            if warning.progress >= warning.required:
                session.log.append(f"{participant.display_name}: {warning.name} 전조 달성")
            else:
                pattern_damage = self.service._use_boss_pattern(
                    warning.pattern,
                    boss_stats,
                    guard_stats,
                    session.boss_hp,
                    participant.hp,
                    participant.player_effects,
                    session.boss_effects,
                )
                if pattern_damage > 0:
                    participant.hp = max(0, participant.hp - pattern_damage)
                    session.log.append(
                        f"{participant.display_name}: {warning.name} 실패, 가드 중 {pattern_damage} 피해"
                    )
                else:
                    session.log.append(f"{participant.display_name}: {warning.name} 실패, 특수 효과 발동")
                pattern_replaced_counter = True
                if participant.hp <= 0:
                    participant.alive = False
            participant.pending_warning = None
            if resolved_ct_warning:
                participant.ct = 0
            if not participant.alive:
                self._check_boss_party_failed(session)
                return True, "전조 실패로 전투 불능이 되었습니다."

        if not pattern_replaced_counter:
            counter_damage = self.service._actual_damage(
                boss_stats,
                session.boss_hp,
                guard_stats,
                participant.hp,
                0.48,
            )
            participant.hp = max(0, participant.hp - counter_damage)
            session.log.append(f"{session.boss.name}: 가드 중 {participant.display_name}에게 {counter_damage} 피해")
            if participant.hp <= 0:
                participant.alive = False
                session.log.append(f"{participant.display_name}: 전투 불능")
                self._check_boss_party_failed(session)
                return True, "전투 불능 상태가 되었습니다."

        self._advance_ct(session, participant, resolved_ct_warning)
        self._finish_boss_turn(session, participant, profile)
        self._check_boss_party_failed(session)
        return True, "가드로 턴을 넘겼습니다."

    def _prepare_visible_warning(self, session: BossSession, participant: BossParticipant, profile: PlayerProfile | None = None) -> None:
        if participant.pending_warning is not None or session.completed or session.failed:
            return
        self._queue_due_hp_warnings(session, participant, profile)
        self._queue_ct_warning(session, participant, profile)
        self._activate_next_warning(session, participant)

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
        participant.player_effects = self.service._tick_effects(participant.player_effects)
        self._tick_ability_cooldowns(participant)
        self._tick_shared_boss_effects(session)
        self._queue_due_hp_warnings(session, participant, profile)
        self._queue_ct_warning(session, participant, profile)
        self._activate_next_warning(session, participant)

    def _hp_warning(self, session: BossSession, idx: int, rule) -> BossWarning:
        pattern = self._pattern_for_warning(session, rule.pattern_id)
        return BossWarning(
            source=f"hp:{idx}",
            name=f"{pattern.name} ({rule.threshold * 100:.0f}%)",
            pattern=pattern,
            objective=rule.objective,
            required=rule.required,
            threshold=rule.threshold,
        )

    def _ct_warning(self, session: BossSession, profile: PlayerProfile | None = None) -> BossWarning:
        rule = self._current_ct_warning(session)
        if rule is None:
            pattern = session.boss.patterns[0] if session.boss.patterns else BossPattern(0.0, f"{session.boss.name} CT")
            objective = "hits"
            required = 1
        else:
            pattern = self._pattern_for_warning(session, rule.pattern_id)
            objective = rule.objective
            required = rule.required
        return BossWarning(
            source="ct",
            name=pattern.name,
            pattern=pattern,
            objective=objective,
            required=required,
        )

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

    def _current_ct_max(self, session: BossSession) -> int:
        ratio = self._boss_hp_ratio(session)
        for rule in session.boss.ct_gauge:
            if ratio >= rule.above:
                return rule.max
        return session.ct_max

    def _current_ct_warning(self, session: BossSession):
        ratio = self._boss_hp_ratio(session)
        for rule in session.boss.ct_warnings:
            if ratio >= rule.above:
                return rule
        return session.boss.ct_warnings[-1] if session.boss.ct_warnings else None

    def _has_ct_warning(self, participant: BossParticipant) -> bool:
        if participant.pending_warning is not None and participant.pending_warning.source == "ct":
            return True
        return any(warning.source == "ct" for warning in participant.queued_warnings)

    def _advance_ct(self, session: BossSession, participant: BossParticipant, resolved_ct_warning: bool) -> None:
        if resolved_ct_warning:
            participant.ct = 0
            return
        participant.ct = min(self._current_ct_max(session), participant.ct + 1)

    def _clear_ready_ct_warning(self, session: BossSession, participant: BossParticipant) -> bool:
        warning = participant.pending_warning
        if warning is None or warning.source != "ct" or warning.progress < warning.required:
            return False
        session.log.append(f"{participant.display_name}: {warning.name} CT 전조 해제")
        participant.pending_warning = None
        participant.ct = 0
        self._activate_next_warning(session, participant)
        return True

    def _add_warning_progress(self, participant: BossParticipant, objective: str, amount: int) -> None:
        warning = participant.pending_warning
        if warning is None or warning.objective != objective or amount <= 0:
            return
        warning.progress = min(warning.required, warning.progress + amount)

    def _tick_ability_cooldowns(self, participant: BossParticipant) -> None:
        participant.ability_cooldowns = {
            skill_id: turns - 1
            for skill_id, turns in participant.ability_cooldowns.items()
            if turns - 1 > 0
        }

    def _grant_boss_session_rewards(self, session: BossSession) -> None:
        if session.rewards:
            return
        for participant in session.participants.values():
            if not participant.alive:
                continue
            reward = self.service.grant_boss_reward(
                participant.user_id,
                participant.display_name,
                session.boss.id,
            )
            session.rewards[participant.user_id] = self._reward_text(reward).replace("\n", ", ")
        session.log.append("보스 클리어 보상 지급")

    def _check_boss_party_failed(self, session: BossSession) -> None:
        if session.completed:
            return
        if session.participants and not any(participant.alive for participant in session.participants.values()):
            session.failed = True
            session.log.append("파티 전멸")

    def _tick_shared_boss_effects(self, session: BossSession) -> None:
        session.boss_effects = self.service._tick_effects(session.boss_effects)

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
                f"총 EXP {profile.exp} · 골드 {profile.gold}G · 스탯 포인트 {profile.stat_points}"
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
                f"`{marker}` **{enemy.name}** · {self.service.reward_summary(enemy.rewards)}"
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
        embed.set_footer(text="탐색 버튼을 누르면 이 메시지가 결과로 갱신됩니다.")
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
        elif session.started:
            color = 0xFFB84D
            status = "진행 중"
        else:
            color = 0x5865F2
            status = "대기 중"
        ct_max = self._current_ct_max(session)
        embed = discord.Embed(
            title=f"{session.boss.name} 보스전",
            description=f"상태: **{status}** · CT {ct_max}칸 · 보상 제한 없음",
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
        participant_lines = []
        for participant in session.participants.values():
            state = "전투 불능" if not participant.alive else f"HP {participant.hp}/{participant.max_hp}"
            warning = "전조 없음"
            if participant.pending_warning is not None:
                remaining = max(0, participant.pending_warning.required - participant.pending_warning.progress)
                warning = (
                    f"{participant.pending_warning.name} · "
                    f"{OBJECTIVE_LABELS[participant.pending_warning.objective]} "
                    f"{participant.pending_warning.progress}/{participant.pending_warning.required}"
                    f" · 남은 {remaining}"
                )
            cooldowns = ", ".join(f"{skill_id}:{turns}" for skill_id, turns in participant.ability_cooldowns.items()) or "없음"
            queued = len(participant.queued_warnings)
            participant_ct = min(participant.ct, ct_max)
            participant_lines.append(
                f"**{participant.display_name}** · {state} · CT {participant_ct}/{ct_max}\n"
                f"전조: {warning} · 대기 {queued} · 쿨: {cooldowns}"
            )
        embed.add_field(
            name=f"참가자 {len(session.participants)}명",
            value=self._trim("\n\n".join(participant_lines), 1800) if participant_lines else "없음",
            inline=False,
        )
        if session.rewards:
            reward_lines = [
                f"**{session.participants[user_id].display_name}**: {text}"
                for user_id, text in session.rewards.items()
                if user_id in session.participants
            ]
            embed.add_field(name="보상", value=self._trim("\n".join(reward_lines), 1000), inline=False)
        if session.log:
            embed.add_field(name="로그", value=self._trim("\n".join(session.log[-8:]), 1200), inline=False)
        embed.set_footer(text="어빌리티는 턴을 쓰지 않습니다. 공격/가드가 턴을 진행하고 전조를 판정합니다.")
        return embed

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
            title=f"{session.boss.name} 어빌리티",
            description=message or "사용할 어빌리티를 누르세요. 어빌리티는 턴을 소모하지 않습니다.",
            color=0xB56BFF,
        )
        if participant.pending_warning is not None:
            warning = participant.pending_warning
            embed.add_field(
                name="개인 전조",
                value=(
                    f"**{warning.name}**\n"
                    f"{OBJECTIVE_LABELS[warning.objective]} {warning.progress}/{warning.required} · "
                    f"남은 {max(0, warning.required - warning.progress)}"
                ),
                inline=False,
            )
        else:
            embed.add_field(name="개인 전조", value="없음", inline=False)
        if participant.queued_warnings:
            embed.add_field(name="대기 전조", value=f"{len(participant.queued_warnings)}개", inline=True)
        lines = []
        for skill in skills:
            cooldown = participant.ability_cooldowns.get(skill.id, 0)
            state = f"쿨 {cooldown}턴" if cooldown > 0 else "사용 가능"
            lines.append(f"**{skill.name}** · {state}\n{self.service.skill_summary(skill)}")
        embed.add_field(name="장착 어빌리티", value=self._trim("\n\n".join(lines), 1200), inline=False)
        return embed

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
        description = result.message if result is not None else "아래 메뉴에서 장비를 고른 뒤 장착/해제하세요."
        embed = discord.Embed(title="장비 장착", description=description, color=0xA0A7B4)

        equipped = self.service.equipped_items(profile)
        equipped_ids = {item.uid for item in equipped}
        selected_uids = selected_uids if selected_uids is not None else list(profile.equipped_item_uids)
        slot_lines = []
        for idx in range(MAX_EQUIPPED_ITEMS):
            if idx < len(equipped):
                item = equipped[idx]
                slot_lines.append(f"`{idx + 1}` {self.service.item_title(item)}")
            else:
                slot_lines.append(f"`{idx + 1}` 비어 있음")
        embed.add_field(
            name=f"장착 슬롯 {len(equipped_ids)}/{MAX_EQUIPPED_ITEMS}",
            value="\n".join(slot_lines),
            inline=False,
        )

        selected_items = [
            item for item in profile.inventory
            if item.uid in set(selected_uids) and not item.destroyed and item.template_id in ITEM_BY_ID
        ]
        if selected_items:
            lines = [
                f"{self.service.item_title(item)}\n{self.service.item_stats_text(item)}"
                for item in selected_items
            ]
            embed.add_field(name=f"적용 대기 {len(selected_items)}/{MAX_EQUIPPED_ITEMS}", value=self._trim("\n\n".join(lines), 1600), inline=False)
        else:
            display_items = self._equipment_display_items(profile)
            lines = []
            for item in display_items[:10]:
                marker = "장착" if item.uid in equipped_ids else "보유"
                if item.destroyed:
                    marker = "파괴"
                lines.append(f"`{marker}` {self.service.item_title(item)}")
            embed.add_field(name="보유 장비", value="\n".join(lines) if lines else "장비 없음", inline=False)

        embed.add_field(
            name="현재 전투 스탯",
            value=self.service.format_stats(self.service.profile_stats(profile)),
            inline=False,
        )
        if len(profile.inventory) > 25:
            embed.set_footer(text="선택 UI는 장착 중인 장비와 전투력 높은 장비를 우선해 25개까지 표시합니다.")
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
        embed.set_footer(text="자동판매된 장비는 보상 로그에 판매가로 표시됩니다.")
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
            description=result.message if result is not None else "사용할 어빌리티를 최대 3개까지 선택하세요.",
            color=0xB56BFF,
        )
        embed.add_field(
            name=f"장착 어빌리티 {len(equipped)}/3",
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
        craftable = [recipe for recipe in recipes if self.service.can_craft(profile, recipe)]
        if craftable:
            lines = [
                f"**{recipe.name}** · {self.service.recipe_status_text(profile, recipe)}\n"
                f"{self.service.recipe_result_text(recipe)}\n"
                f"비용 {recipe.gold}G · {self.service.material_cost_text(profile, recipe.materials)}"
                for recipe in craftable[:5]
            ]
            embed.add_field(name=f"제작 가능 {len(craftable)}개", value=self._trim("\n\n".join(lines), 2200), inline=False)
        else:
            embed.add_field(name="제작 가능", value="현재 제작 가능한 장비가 없습니다.", inline=False)

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
        elif recipes:
            embed.add_field(name="선택 제작", value="제작법을 선택하세요.", inline=False)

        material_summary = self._material_summary(profile, limit=8)
        embed.add_field(name="보유 재료", value=material_summary or "보유 재료 없음", inline=False)
        return embed

    def _enhancement_picker_embed(self, profile: PlayerProfile) -> discord.Embed:
        display_items = self._enhancement_display_items(profile)
        embed = discord.Embed(
            title="장비 강화",
            description="아래 선택 메뉴에서 강화할 장비를 고르세요. 선택하면 비용, 확률, 증가 스탯이 표시됩니다.",
            color=0xFFB84D,
        )
        equipped_ids = {item.uid for item in self.service.equipped_items(profile)}
        lines = []
        for item in display_items:
            marker = "장착" if item.uid in equipped_ids else "보유"
            lines.append(f"`{marker}` {self.service.item_title(item)}")
        embed.add_field(name="장비", value="\n".join(lines), inline=False)
        footer = f"보유 골드 {profile.gold}G"
        if len(profile.inventory) > len(display_items):
            footer += " · 선택 UI는 전투력 높은 25개만 표시"
        embed.set_footer(text=footer)
        return embed

    def _enhancement_preview_embed(self, preview: EnhancementPreview) -> discord.Embed:
        color = 0xFFB84D
        if preview.item is not None and preview.item.template_id in ITEM_BY_ID:
            color = RARITY_COLORS[ITEM_BY_ID[preview.item.template_id].rarity]
        embed = discord.Embed(title="강화 미리보기", description=preview.message, color=color)
        if preview.item is None:
            return embed
        embed.add_field(name="장비", value=self.service.item_title(preview.item), inline=False)
        embed.add_field(name="현재 스탯", value=self.service.format_stats(preview.before_stats, signed=True), inline=False)
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

    def _enhance_result_embed(self, result: EnhancementResult) -> discord.Embed:
        color = 0x57F287 if result.ok else 0xED4245
        if result.item is not None and result.item.template_id in ITEM_BY_ID:
            color = RARITY_COLORS[ITEM_BY_ID[result.item.template_id].rarity]
        embed = discord.Embed(title="장비 강화", description=result.message, color=color)
        if result.item is not None:
            embed.add_field(name="장비", value=self.service.item_title(result.item), inline=False)
            embed.add_field(name="스탯", value=self.service.item_stats_text(result.item), inline=False)
        if result.cost:
            embed.add_field(name="비용", value=f"{result.cost}G", inline=True)
        if result.outcome:
            outcome_text = {
                "success": "성공",
                "failed": "실패",
                "destroyed": "파괴",
                "restored": "복구",
                "no_gold": "골드 부족",
            }.get(result.outcome, result.outcome)
            embed.add_field(name="결과", value=f"{outcome_text} · +{result.before_stars} → +{result.after_stars}", inline=True)
        if result.odds != (0.0, 0.0, 0.0):
            success, fail, destroy = result.odds
            embed.add_field(
                name="확률",
                value=f"성공 {success * 100:.1f}% · 실패 {fail * 100:.1f}% · 파괴 {destroy * 100:.1f}%",
                inline=False,
            )
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
        if reward.stat_points:
            parts.append(f"스탯 포인트 {reward.stat_points}")
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

    def _enhancement_display_items(self, profile: PlayerProfile):
        return sorted(
            profile.inventory,
            key=lambda item: (
                item.destroyed,
                -self.service.item_score(item),
                item.uid,
            ),
        )[:25]


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
        self.selected_recipe_id = selected_recipe_id or (recipes[0].id if recipes else None)

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


class BossSessionView(discord.ui.View):
    def __init__(self, cog: RPGCog, session: BossSession) -> None:
        super().__init__(timeout=900)
        self.cog = cog
        self.session = session
        if session.completed or session.failed:
            return
        if not session.started:
            self.add_item(BossJoinButton())
            self.add_item(BossStartButton())
            return
        self.add_item(BossAttackButton())
        self.add_item(BossGuardButton())
        self.add_item(BossAbilityMenuButton())

    async def _edit(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(
            embed=self.cog._boss_session_embed(self.session),
            view=BossSessionView(self.cog, self.session),
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
            await interaction.response.send_message(message, ephemeral=True)
            return
        await self.view._edit(interaction)


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


class BossAttackButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="공격", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView)
        ok, message = self.view.cog._boss_attack(
            self.view.session,
            interaction.user.id,
            interaction.user.display_name,
        )
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return
        await self.view._edit(interaction)


class BossGuardButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="가드", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView)
        ok, message = self.view.cog._boss_guard(
            self.view.session,
            interaction.user.id,
            interaction.user.display_name,
        )
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return
        await self.view._edit(interaction)


class BossAbilityMenuButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(label="어빌리티", style=discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView)
        participant = self.view.session.participants.get(interaction.user.id)
        if participant is None:
            await interaction.response.send_message("이 보스전에 참가하지 않았습니다.", ephemeral=True)
            return
        if not self.view.session.started or self.view.session.completed or self.view.session.failed:
            await interaction.response.send_message("진행 중인 보스전이 아닙니다.", ephemeral=True)
            return
        self.view.session.message = interaction.message
        profile = self.view.cog.service.get_profile(interaction.user.id, interaction.user.display_name)
        self.view.cog._prepare_visible_warning(self.view.session, participant, profile)
        skills = self.view.cog.service.equipped_skills(profile)
        if not skills:
            await interaction.response.send_message("장착한 어빌리티가 없습니다. `/rpg 어빌리티`에서 먼저 장착하세요.", ephemeral=True)
            return
        await interaction.message.edit(
            embed=self.view.cog._boss_session_embed(self.view.session),
            view=BossSessionView(self.view.cog, self.view.session),
        )
        await interaction.response.send_message(
            embed=self.view.cog._boss_ability_embed(self.view.session, participant, skills),
            view=BossAbilityView(self.view.cog, self.view.session, interaction.user.id, interaction.user.display_name, skills),
            ephemeral=True,
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
        for skill in skills[:3]:
            cooldown = session.participants[user_id].ability_cooldowns.get(skill.id, 0)
            self.add_item(BossAbilityButton(skill, disabled=cooldown > 0))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 어빌리티 메뉴는 본인만 사용할 수 있습니다.", ephemeral=True)
        return False


class BossAbilityButton(discord.ui.Button):
    def __init__(self, skill: SkillTemplate, *, disabled: bool = False) -> None:
        super().__init__(label=skill.name[:80], style=discord.ButtonStyle.secondary, disabled=disabled)
        self.skill = skill

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossAbilityView)
        ok, message = self.view.cog._boss_use_ability(
            self.view.session,
            self.view.user_id,
            self.view.display_name,
            self.skill.id,
        )
        profile = self.view.cog.service.get_profile(self.view.user_id, self.view.display_name)
        skills = self.view.cog.service.equipped_skills(profile)
        participant = self.view.session.participants[self.view.user_id]
        if self.view.session.message is not None:
            await self.view.session.message.edit(
                embed=self.view.cog._boss_session_embed(self.view.session),
                view=BossSessionView(self.view.cog, self.view.session),
            )
        await interaction.response.edit_message(
            embed=self.view.cog._boss_ability_embed(self.view.session, participant, skills, message),
            view=BossAbilityView(self.view.cog, self.view.session, self.view.user_id, self.view.display_name, skills),
        )


class EquipmentView(discord.ui.View):
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
        profile = self.cog.service.get_profile(user_id, display_name)
        self.selected_uids = selected_uids if selected_uids is not None else list(profile.equipped_item_uids)

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
                    label=f"#{item.uid} {template.name} +{item.stars}",
                    value=str(item.uid),
                    description=f"{marker} · {self.cog.service.item_stats_text(item)}"[:100],
                    default=item.uid in self.selected_uids,
                )
            )
        if options:
            self.add_item(EquipmentSelect(options))
        self.add_item(EquipmentApplyButton(disabled=not options))
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
        profile = self.view.cog.service.get_profile(self.view.user_id, self.view.display_name)
        view = EquipmentView(self.view.cog, self.view.user_id, self.view.display_name, uids)
        await interaction.response.edit_message(
            embed=self.view.cog._equipment_embed(profile, uids),
            view=view,
        )


class EquipmentApplyButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False) -> None:
        super().__init__(
            label="장착 적용",
            style=discord.ButtonStyle.primary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, EquipmentView)
        result = self.view.cog.service.set_equipped_items(
            self.view.user_id,
            self.view.display_name,
            self.view.selected_uids,
        )
        view = EquipmentView(self.view.cog, self.view.user_id, self.view.display_name, list(result.profile.equipped_item_uids))
        await interaction.response.edit_message(
            embed=self.view.cog._equipment_embed(result.profile, list(result.profile.equipped_item_uids), result),
            view=view,
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
        view = EquipmentView(self.view.cog, self.view.user_id, self.view.display_name, list(result.profile.equipped_item_uids))
        await interaction.response.edit_message(
            embed=self.view.cog._equipment_embed(result.profile, list(result.profile.equipped_item_uids), result),
            view=view,
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
                    label=f"#{item.uid} {template.name} +{item.stars}",
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


class AbilityEquipView(discord.ui.View):
    def __init__(
        self,
        cog: RPGCog,
        user_id: int,
        display_name: str,
        selected_skill_ids: list[str] | None = None,
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_id = user_id
        self.display_name = display_name
        profile = self.cog.service.get_profile(user_id, display_name)
        equipped = [skill.id for skill in self.cog.service.equipped_skills(profile)]
        self.selected_skill_ids = selected_skill_ids if selected_skill_ids is not None else equipped
        options = [
            discord.SelectOption(
                label=skill.name,
                value=skill.id,
                description=self.cog.service.skill_summary(skill)[:100],
                default=skill.id in self.selected_skill_ids,
            )
            for skill in self.cog.service.unlocked_skills(profile)
        ]
        if options:
            self.add_item(AbilityEquipSelect(options))
        self.add_item(AbilityApplyButton(disabled=not options))

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
            max_values=min(3, len(options)),
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, AbilityEquipView)
        profile = self.view.cog.service.get_profile(self.view.user_id, self.view.display_name)
        selected = list(self.values)
        view = AbilityEquipView(self.view.cog, self.view.user_id, self.view.display_name, selected)
        await interaction.response.edit_message(
            embed=self.view.cog._ability_embed(profile, selected_skill_ids=selected),
            view=view,
        )


class AbilityApplyButton(discord.ui.Button):
    def __init__(self, *, disabled: bool = False) -> None:
        super().__init__(label="어빌리티 적용", style=discord.ButtonStyle.primary, disabled=disabled)

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, AbilityEquipView)
        result = self.view.cog.service.set_equipped_skills(
            self.view.user_id,
            self.view.display_name,
            self.view.selected_skill_ids,
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
        options = []
        equipped_ids = {item.uid for item in self.cog.service.equipped_items(profile)}
        for item in self.cog._enhancement_display_items(profile):
            template = ITEM_BY_ID.get(item.template_id)
            if template is None:
                continue
            marker = "장착" if item.uid in equipped_ids else "보유"
            status = "파괴됨" if item.destroyed else self.cog.service.item_stats_text(item)
            options.append(
                discord.SelectOption(
                    label=f"#{item.uid} {template.name} +{item.stars}",
                    value=str(item.uid),
                    description=f"{marker} · {status}"[:100],
                    default=item.uid == selected_uid,
                )
            )
        if options:
            self.add_item(EnhancementSelect(options))
        self.add_item(EnhancementConfirmButton(disabled=selected_uid is None))

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
        preview = self.view.cog.service.enhancement_preview(
            self.view.user_id,
            self.view.display_name,
            uid,
        )
        await interaction.response.edit_message(
            embed=self.view.cog._enhancement_preview_embed(preview),
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
        await interaction.response.edit_message(
            embed=self.view.cog._enhance_result_embed(result),
            view=view,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RPGCog(bot))
