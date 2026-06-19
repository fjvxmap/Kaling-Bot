from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.rpg.data import (
    BOSSES,
    DAILY_EXPLORES,
    DUNGEONS,
    ITEM_BY_ID,
    JOBS,
    RARITY_COLORS,
)
from bot.services.rpg.manager import (
    BossResult,
    EnhancementPreview,
    EnhancementResult,
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


class RPGCog(commands.Cog):
    rpg = app_commands.Group(name="rpg", description="가볍게 즐기는 던전/보스 RPG")

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.service = RPGService()

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

    @rpg.command(name="던전목록", description="탐색 가능한 던전과 일일 남은 횟수를 봅니다.")
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
            description=f"오늘 남은 탐색: **{self.service.daily_remaining(profile)}/{DAILY_EXPLORES}회**",
            color=0x4BA3FF,
        )
        embed.add_field(name="탐색지", value="\n\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed)

    @rpg.command(name="탐색", description="하루 제한 횟수를 사용해 던전을 탐색합니다.")
    @app_commands.rename(dungeon="던전")
    @app_commands.describe(dungeon="탐색할 던전")
    @app_commands.choices(dungeon=DUNGEON_CHOICES)
    async def explore(
        self,
        interaction: discord.Interaction,
        dungeon: app_commands.Choice[str],
    ) -> None:
        result = self.service.explore(
            interaction.user.id,
            interaction.user.display_name,
            dungeon.value,
        )
        await interaction.response.send_message(embed=self._explore_embed(result))

    @rpg.command(name="보스목록", description="도전 가능한 보스와 이번 주 보상 상태를 봅니다.")
    async def boss_list(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        week_key = self.service.current_week_key()
        lines = []
        for boss in self.service.bosses():
            gate = "도전 가능" if profile.level >= boss.level_req else f"Lv.{boss.level_req} 필요"
            weekly = "이번 주 보상 수령" if profile.weekly_boss_clears.get(boss.id) == week_key else "보상 가능"
            lines.append(
                f"**{boss.name}** · {gate} · {weekly}\n"
                f"보상 {boss.gold}G/{boss.exp}EXP/스탯 {boss.stat_points} · {boss.description}"
            )
        embed = discord.Embed(
            title="보스 목록",
            description="보스는 횟수 제한 없이 재도전할 수 있고, 보상은 보스별 주 1회입니다.",
            color=0xFFB84D,
        )
        embed.add_field(name=f"주간 키 {week_key}", value="\n\n".join(lines), inline=False)
        await interaction.response.send_message(embed=embed)

    @rpg.command(name="보스", description="보스를 선택해 도전합니다. 도전 횟수 제한은 없습니다.")
    @app_commands.rename(boss="보스")
    @app_commands.describe(boss="도전할 보스")
    @app_commands.choices(boss=BOSS_CHOICES)
    async def boss(
        self,
        interaction: discord.Interaction,
        boss: app_commands.Choice[str],
    ) -> None:
        result = self.service.challenge_boss(
            interaction.user.id,
            interaction.user.display_name,
            boss.value,
        )
        await interaction.response.send_message(embed=self._boss_embed(result))

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

    @rpg.command(name="인벤토리", description="보유 장비와 자동 장착 상태를 봅니다.")
    async def inventory(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        embed = discord.Embed(
            title="인벤토리",
            description="파괴되지 않은 장비 중 전투력이 높은 4개가 자동 장착됩니다.",
            color=0xA0A7B4,
        )
        equipped_ids = {item.uid for item in self.service.equipped_items(profile)}
        if not profile.inventory:
            embed.add_field(name="장비", value="아직 장비가 없습니다. 던전이나 보스를 클리어해 보세요.", inline=False)
        else:
            lines = []
            for item in sorted(profile.inventory, key=lambda owned: (owned.uid)):
                marker = "장착" if item.uid in equipped_ids else "보유"
                lines.append(f"`{marker}` {self.service.item_title(item)}\n{self.service.item_stats_text(item)}")
            embed.add_field(name="장비", value=self._trim("\n\n".join(lines), 3900), inline=False)
        await interaction.response.send_message(embed=embed)

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
            value=f"오늘 남은 횟수 **{self.service.daily_remaining(profile)}/{DAILY_EXPLORES}회**",
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
            name="자동 장착",
            value="\n".join(self.service.item_title(item) for item in equipped) if equipped else "장비 없음",
            inline=False,
        )
        return embed

    def _explore_embed(self, result: ExploreResult) -> discord.Embed:
        if not result.ok:
            return discord.Embed(title="탐색 실패", description=result.message, color=0xED4245)
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
            embed.set_footer(text=f"오늘 남은 탐색 {result.daily_remaining}/{DAILY_EXPLORES}회")
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

    def _enhancement_display_items(self, profile: PlayerProfile):
        return sorted(
            profile.inventory,
            key=lambda item: (
                item.destroyed,
                -self.service.item_score(item),
                item.uid,
            ),
        )[:25]


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
