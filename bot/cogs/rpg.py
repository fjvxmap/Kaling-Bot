from __future__ import annotations

from dataclasses import dataclass, field

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.rpg.data import (
    BOSS_BY_ID,
    BOSSES,
    DAILY_EXPLORES,
    DUNGEONS,
    ITEM_BY_ID,
    JOBS,
    MAX_EQUIPPED_ITEMS,
    RARITY_COLORS,
    BossPattern,
    BossTemplate,
)
from bot.services.rpg.manager import (
    ActiveEffect,
    BossResult,
    EnhancementPreview,
    EnhancementResult,
    EquipmentResult,
    ExploreResult,
    RPGService,
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
    app_commands.Choice(name="공격력 +1", value="attack"),
    app_commands.Choice(name="최대 HP +5", value="hp"),
    app_commands.Choice(name="방어 +2%", value="defense"),
]

GIMMICK_LABELS = {
    "guard": "방어",
    "cleanse": "정화",
    "break": "차단",
}


@dataclass
class BossWarning:
    source: str
    name: str
    pattern: BossPattern
    requirement: str
    threshold: float | None = None


@dataclass
class BossParticipant:
    user_id: int
    display_name: str
    hp: int
    max_hp: int
    ct: int = 0
    alive: bool = True
    prepared_gimmick: str = ""
    pending_warning: BossWarning | None = None
    triggered_thresholds: set[int] = field(default_factory=set)
    player_effects: list[ActiveEffect] = field(default_factory=list)


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
    hp_thresholds: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.boss_max_hp = max(1, int(self.boss.stats.get("max_hp", 1)))
        self.boss_hp = self.boss_max_hp
        self.ct_max = max(3, 7 - min(4, self.boss.rank))
        threshold_count = min(10, max(5, self.boss.rank + 3))
        if threshold_count <= 1:
            self.hp_thresholds = [0.5]
        else:
            step = 0.8 / (threshold_count - 1)
            self.hp_thresholds = [round(0.9 - step * idx, 2) for idx in range(threshold_count)]


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
            exp_values = [enemy.exp for enemy in dungeon.enemies]
            gold_values = [enemy.gold for enemy in dungeon.enemies]
            rare_names = ", ".join(enemy.name for enemy in dungeon.enemies if enemy.rare) or "없음"
            lines.append(
                f"**{dungeon.name}** · {state}\n"
                f"EXP {min(exp_values)}~{max(exp_values)} · 골드 {min(gold_values)}~{max(gold_values)}G · 희귀 {rare_names}\n"
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
                f"보상 {boss.gold}G/{boss.exp}EXP/스탯 {boss.stat_points} · {boss.description}"
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

    @rpg.command(name="스탯", description="레벨업/보스 보상으로 얻은 스탯 포인트를 투자합니다.")
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

    def _prepare_boss_gimmick(self, session: BossSession, user_id: int, gimmick: str) -> tuple[bool, str]:
        participant = session.participants.get(user_id)
        if participant is None:
            return False, "이 보스전에 참가하지 않았습니다."
        if not session.started or session.completed or session.failed:
            return False, "진행 중인 보스전이 아닙니다."
        if not participant.alive:
            return False, "전투 불능 상태입니다."
        self._ensure_boss_warning(session, participant)
        participant.prepared_gimmick = gimmick
        label = GIMMICK_LABELS.get(gimmick, gimmick)
        session.log.append(f"{participant.display_name}: {label} 준비")
        return True, f"{label} 기믹을 준비했습니다. 공격을 누르면 턴이 진행됩니다."

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
        self._ensure_boss_warning(session, participant)
        if participant.pending_warning is not None and not had_warning and not participant.prepared_gimmick:
            return True, "전조가 발생했습니다. 요구 기믹을 누른 뒤 공격하세요."
        profile = self.service.get_profile(user_id, display_name)
        player_base = self.service.profile_stats(profile)
        player_stats = self.service._stats_with_effects(player_base, participant.player_effects)
        boss_base = self.service._enemy_stats(session.boss.stats)
        boss_stats = self.service._stats_with_effects(boss_base, session.boss_effects)

        if participant.pending_warning is not None:
            warning = participant.pending_warning
            required = warning.requirement
            if participant.prepared_gimmick == required:
                session.log.append(
                    f"{participant.display_name}: {warning.name} 전조 대응 성공"
                )
            else:
                damage = self.service._use_boss_pattern(
                    warning.pattern,
                    boss_stats,
                    player_stats,
                    session.boss_hp,
                    participant.hp,
                    participant.player_effects,
                    session.boss_effects,
                )
                if damage > 0:
                    participant.hp = max(0, participant.hp - damage)
                    session.log.append(
                        f"{participant.display_name}: {warning.name} 대응 실패, {damage} 피해"
                    )
                else:
                    session.log.append(
                        f"{participant.display_name}: {warning.name} 대응 실패, 특수 효과 발동"
                    )
                if participant.hp <= 0:
                    participant.alive = False
            participant.pending_warning = None
            participant.prepared_gimmick = ""
            if not participant.alive:
                self._check_boss_party_failed(session)
                return True, "전조 대응 실패로 전투 불능이 되었습니다."

        player_stats = self.service._stats_with_effects(player_base, participant.player_effects)
        boss_stats = self.service._stats_with_effects(boss_base, session.boss_effects)
        damage = self.service._actual_damage(
            player_stats,
            participant.hp,
            boss_stats,
            session.boss_hp,
        )
        session.boss_hp = max(0, session.boss_hp - damage)
        session.log.append(f"{participant.display_name}: 공격 {damage} 피해")

        if session.boss_hp <= 0:
            session.completed = True
            self._grant_boss_session_rewards(session)
            return True, "보스를 클리어했습니다."

        boss_stats = self.service._stats_with_effects(boss_base, session.boss_effects)
        player_stats = self.service._stats_with_effects(player_base, participant.player_effects)
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

        participant.prepared_gimmick = ""
        participant.ct += 1
        participant.player_effects = self.service._tick_effects(participant.player_effects)
        self._tick_shared_boss_effects(session)
        self._ensure_boss_warning(session, participant)
        self._check_boss_party_failed(session)
        return True, "턴을 진행했습니다."

    def _ensure_boss_warning(self, session: BossSession, participant: BossParticipant) -> None:
        if participant.pending_warning is not None or session.completed or session.failed:
            return
        if participant.ct >= session.ct_max:
            participant.pending_warning = self._ct_warning(session)
            participant.ct = 0
            session.log.append(f"{participant.display_name}: CT 전조 {participant.pending_warning.name}")
            return
        ratio = session.boss_hp / max(1, session.boss_max_hp)
        for idx, threshold in enumerate(session.hp_thresholds):
            if idx in participant.triggered_thresholds:
                continue
            if ratio <= threshold:
                participant.triggered_thresholds.add(idx)
                participant.pending_warning = self._hp_warning(session, idx, threshold)
                session.log.append(f"{participant.display_name}: 체력 전조 {participant.pending_warning.name}")
                return

    def _hp_warning(self, session: BossSession, idx: int, threshold: float) -> BossWarning:
        pattern = session.boss.patterns[idx % len(session.boss.patterns)]
        return BossWarning(
            source=f"hp:{idx}",
            name=f"{pattern.name} ({threshold * 100:.0f}%)",
            pattern=pattern,
            requirement=self._pattern_requirement(pattern),
            threshold=threshold,
        )

    def _ct_warning(self, session: BossSession) -> BossWarning:
        pattern = self._ct_pattern(session)
        return BossWarning(
            source="ct",
            name=f"{session.boss.name} CT",
            pattern=pattern,
            requirement="guard",
        )

    def _ct_pattern(self, session: BossSession) -> BossPattern:
        phase = self._boss_phase(session)
        multiplier = 0.55 + 0.16 * phase + 0.04 * session.boss.rank
        hits = max(2, min(6, session.boss.rank))
        return BossPattern(
            0.0,
            f"{session.boss.name} CT",
            multiplier,
            hits,
            boss_mods={"atk": 0.06 * phase, "dmg_amplification": 0.035 * phase},
            duration=2,
        )

    def _boss_phase(self, session: BossSession) -> int:
        ratio = session.boss_hp / max(1, session.boss_max_hp)
        if ratio <= 0.25:
            return 4
        if ratio <= 0.5:
            return 3
        if ratio <= 0.75:
            return 2
        return 1

    def _pattern_requirement(self, pattern: BossPattern) -> str:
        if pattern.player_mods:
            return "cleanse"
        if pattern.boss_mods:
            return "break"
        return "guard"

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
        skills = self.service.unlocked_skills(profile)
        embed.add_field(
            name="스킬",
            value=self._trim("\n".join(f"**{skill.name}** · {self.service.skill_summary(skill)}" for skill in skills), 1000) if skills else "없음",
            inline=False,
        )
        equipped = self.service.equipped_items(profile)
        embed.add_field(
            name="장착 장비",
            value="\n".join(self.service.item_title(item) for item in equipped) if equipped else "장비 없음",
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

        exp_values = [enemy.exp for enemy in selected.enemies]
        gold_values = [enemy.gold for enemy in selected.enemies]
        enemy_lines = []
        for enemy in selected.enemies:
            marker = "희귀" if enemy.rare else "일반"
            enemy_lines.append(
                f"`{marker}` **{enemy.name}** · EXP {enemy.exp} · {enemy.gold}G"
            )
        gate = "입장 가능" if profile.level >= selected.level_req else f"Lv.{selected.level_req} 필요"
        embed.add_field(
            name=selected.name,
            value=(
                f"{gate}\n"
                f"EXP {min(exp_values)}~{max(exp_values)} · 골드 {min(gold_values)}~{max(gold_values)}G\n"
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
        embed = discord.Embed(
            title=f"{session.boss.name} 보스전",
            description=f"상태: **{status}** · CT {session.ct_max}칸 · 보상 제한 없음",
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
                warning = (
                    f"{participant.pending_warning.name} · "
                    f"{GIMMICK_LABELS[participant.pending_warning.requirement]} 필요"
                )
            prepared = GIMMICK_LABELS.get(participant.prepared_gimmick, "없음")
            participant_lines.append(
                f"**{participant.display_name}** · {state} · CT {participant.ct}/{session.ct_max}\n"
                f"전조: {warning} · 준비: {prepared}"
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
        embed.set_footer(text="방어/정화/차단은 턴을 쓰지 않습니다. 공격만 턴을 진행합니다.")
        return embed

    def _hp_bar(self, current: int, maximum: int, *, width: int = 18) -> str:
        maximum = max(1, maximum)
        filled = round(width * max(0, min(current, maximum)) / maximum)
        return "[" + "#" * filled + "-" * (width - filled) + "]"

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
        selected_uid: int | None = None,
        result: EquipmentResult | None = None,
    ) -> discord.Embed:
        selected = self._profile_item(profile, selected_uid)
        color = 0xA0A7B4
        if selected is not None and selected.template_id in ITEM_BY_ID:
            color = RARITY_COLORS[ITEM_BY_ID[selected.template_id].rarity]
        description = result.message if result is not None else "아래 메뉴에서 장비를 고른 뒤 장착/해제하세요."
        embed = discord.Embed(title="장비 장착", description=description, color=color)

        equipped = self.service.equipped_items(profile)
        equipped_ids = {item.uid for item in equipped}
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

        if selected is not None:
            status = "장착 중" if selected.uid in equipped_ids else "보유"
            if selected.destroyed:
                status = "파괴됨"
            embed.add_field(name="선택 장비", value=f"`{status}` {self.service.item_title(selected)}", inline=False)
            embed.add_field(name="장비 스탯", value=self.service.item_stats_text(selected), inline=False)
            embed.add_field(name="장비 점수", value=f"{self.service.item_score(selected):.1f}", inline=True)
        else:
            display_items = self._equipment_display_items(profile)
            lines = []
            for item in display_items[:10]:
                marker = "장착" if item.uid in equipped_ids else "보유"
                if item.destroyed:
                    marker = "파괴"
                lines.append(f"`{marker}` {self.service.item_title(item)}")
            embed.add_field(
                name="보유 장비",
                value="\n".join(lines) if lines else "장비 없음",
                inline=False,
            )

        embed.add_field(
            name="현재 전투 스탯",
            value=self.service.format_stats(self.service.profile_stats(profile)),
            inline=False,
        )
        if len(profile.inventory) > 25:
            embed.set_footer(text="선택 UI는 장착 중인 장비와 전투력 높은 장비를 우선해 25개까지 표시합니다.")
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
        if reward.dropped_item:
            parts.append(f"드랍: {self.service.item_title(reward.dropped_item)}")
        if not parts:
            return "보상 없음"
        return "\n".join(parts)

    def _trim(self, text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 3] + "..."

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
        self.add_item(BossGimmickButton("방어", "guard", discord.ButtonStyle.secondary))
        self.add_item(BossGimmickButton("정화", "cleanse", discord.ButtonStyle.secondary))
        self.add_item(BossGimmickButton("차단", "break", discord.ButtonStyle.secondary))

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


class BossGimmickButton(discord.ui.Button):
    def __init__(self, label: str, gimmick: str, style: discord.ButtonStyle) -> None:
        super().__init__(label=label, style=style)
        self.gimmick = gimmick

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, BossSessionView)
        ok, message = self.view.cog._prepare_boss_gimmick(
            self.view.session,
            interaction.user.id,
            self.gimmick,
        )
        if not ok:
            await interaction.response.send_message(message, ephemeral=True)
            return
        await self.view._edit(interaction)


class EquipmentView(discord.ui.View):
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
                    default=item.uid == selected_uid,
                )
            )
        if options:
            self.add_item(EquipmentSelect(options))

        selected = self.cog._profile_item(profile, selected_uid)
        equipped = selected is not None and selected.uid in equipped_ids
        label = "장착 해제" if equipped else "장착"
        disabled = selected is None or (selected.destroyed if selected is not None else True)
        self.add_item(EquipmentToggleButton(label=label, disabled=disabled))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("이 장착 UI는 명령을 실행한 사람만 사용할 수 있습니다.", ephemeral=True)
        return False


class EquipmentSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder="장착할 장비 선택",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, EquipmentView)
        uid = int(self.values[0])
        profile = self.view.cog.service.get_profile(self.view.user_id, self.view.display_name)
        view = EquipmentView(self.view.cog, self.view.user_id, self.view.display_name, uid)
        await interaction.response.edit_message(
            embed=self.view.cog._equipment_embed(profile, uid),
            view=view,
        )


class EquipmentToggleButton(discord.ui.Button):
    def __init__(self, *, label: str, disabled: bool = False) -> None:
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary,
            disabled=disabled,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        assert isinstance(self.view, EquipmentView)
        if self.view.selected_uid is None:
            await interaction.response.send_message("먼저 장비를 선택하세요.", ephemeral=True)
            return
        result = self.view.cog.service.toggle_equip_item(
            self.view.user_id,
            self.view.display_name,
            self.view.selected_uid,
        )
        selected_uid = result.item.uid if result.item is not None else self.view.selected_uid
        view = EquipmentView(self.view.cog, self.view.user_id, self.view.display_name, selected_uid)
        await interaction.response.edit_message(
            embed=self.view.cog._equipment_embed(result.profile, selected_uid, result),
            view=view,
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
