# RPG Balance Simulator

RPG combat balance checker for `bot/services/rpg/content`.

## Run

```bash
python -m tools.rpg_balance
```

Useful examples:

```bash
# Show detailed best items and skills for every tier 5 job.
python -m tools.rpg_balance --details

# Check only one job.
python -m tools.rpg_balance --jobs archmage_fp --details

# Compare item grades at level 60 with 5-star equipment.
python -m tools.rpg_balance --level 60 --stars 5 --details

# Use deeper search. Slower, but useful before major balance changes.
python -m tools.rpg_balance --item-candidates 10 --skill-candidates 8 --details
```

## Notes

- The simulator uses the real RPG service damage functions.
- A turn uses ready support/buff/debuff abilities first, then ready damage abilities, then a normal attack.
- `uses` and cooldowns are respected. For example, `uses: 1` skills are used once.
- Finite item effects are applied once at battle start and expire normally.
- `unique-plus` means up to one legendary item plus unique items.
- The result is deterministic expected damage, not random combat logs.

