# RPG Balance Simulator

Balance analysis for the shared RPG combat engine. The tool never writes the state file passed to `--state`.

## Synthetic Matrix

```bash
python -m tools.rpg_balance
python -m tools.rpg_balance --details
python -m tools.rpg_balance --jobs hero bowmaster --details
python -m tools.rpg_balance --level 60 --stars 5 --details
python -m tools.rpg_balance --item-candidates 10 --skill-candidates 8 --details
```

The default report searches tier-5 jobs across epic, unique, and `unique-plus` loadouts. `unique-plus` permits up to one legendary weapon with unique equipment.

## Live-State Analysis

Analyze real profiles against a synthetic target:

```bash
python -m tools.rpg_balance \
  --state /path/to/server_rpg_state.json \
  --turns 30 --enemy-level 50 --enemy-defense 0.85
```

Filter profiles by user ID or exact display name:

```bash
python -m tools.rpg_balance \
  --state /path/to/server_rpg_state.json \
  --profiles 123456789 "Display Name"
```

Use an actual boss as the target:

```bash
python -m tools.rpg_balance \
  --state /path/to/server_rpg_state.json \
  --boss lotus_hard --turns 30
```

## Hard Boss Engine Report

```bash
python -m tools.rpg_balance \
  --state /path/to/server_rpg_state.json \
  --hard-report --trials 10
```

This mode creates isolated practice sessions and runs the real boss engine for every hard boss. It reports win rate, median action turns, expected static kill turns, incoming basic damage, survival hits, and average remaining boss HP on losses.

The automated pilot uses every ready ability in debuff, buff, heal, and damage order before its normal attack. It guards unresolved warnings on their final turn. A failed automatic trial can therefore identify a mechanical or survivability pressure point, but does not prove that a human strategy cannot clear it.

## Model Notes

- Damage, healing, cooldown, use-limit, buff, debuff, special-ability, and equipment calculations call the production RPG service.
- Each simulated turn uses all ready support abilities, all ready damage abilities, then one normal attack.
- One-use abilities are consumed once; cooldowns and finite effects expire normally.
- Special abilities occupy their separate `5+1` slot.
- Synthetic reports use expected damage and are deterministic. Engine reports use seeded combat trials.
- Potential and Starforce values are read from current tracked content, so balance edits appear immediately.
