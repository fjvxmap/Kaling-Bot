from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from bot.services.rpg.data import (
    BOSSES,
    DAILY_EXPLORES,
    DUNGEONS,
    ITEM_BY_ID,
    RARITY_COLORS,
)
from bot.services.rpg.manager import (
    BossResult,
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

    @rpg.command(name="프로필", description="레벨, 경험치, 스탯, 장착 장비를 봅니다.")
    async def profile(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        await interaction.response.send_message(embed=self._profile_embed(profile))

    @rpg.command(name="던전목록", description="탐색 가능한 던전과 일일 남은 횟수를 봅니다.")
    async def dungeon_list(self, interaction: discord.Interaction) -> None:
        profile = self.service.get_profile(interaction.user.id, interaction.user.display_name)
        lines = []
        for dungeon in self.service.dungeons():
            state = "입장 가능" if profile.level >= dungeon.level_req else f"Lv.{dungeon.level_req} 필요"
            lines.append(
                f"**{dungeon.name}** · {state}\n"
                f"보상 {dungeon.gold}G/{dungeon.exp}EXP · 드랍 {dungeon.drop_chance * 100:.0f}%\n"
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

    @rpg.command(name="강화", description="장비 UID를 지정해 1회 강화합니다.")
    @app_commands.rename(uid="장비_uid")
    @app_commands.describe(uid="인벤토리에 보이는 장비 UID")
    async def enhance(self, interaction: discord.Interaction, uid: int) -> None:
        result = self.service.enhance(interaction.user.id, interaction.user.display_name, uid)
        await interaction.response.send_message(embed=self._enhance_embed(result))

    @rpg.command(name="복구", description="파괴된 장비 흔적을 +0 상태로 복구합니다.")
    @app_commands.rename(uid="장비_uid")
    @app_commands.describe(uid="복구할 장비 UID")
    async def restore(self, interaction: discord.Interaction, uid: int) -> None:
        result = self.service.restore(interaction.user.id, interaction.user.display_name, uid)
        await interaction.response.send_message(embed=self._enhance_embed(result))

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
            name="해금 스킬",
            value=", ".join(skill.name for skill in skills) if skills else "없음",
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
        return self._battle_result_embed(
            title=f"{result.dungeon.name} 탐색",
            result=result,
            color=0x57F287 if result.battle and result.battle.won else 0xED4245,
        )

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

    def _enhance_embed(self, result) -> discord.Embed:
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(RPGCog(bot))
