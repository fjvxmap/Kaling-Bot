# RPG Content Admin

Local editor for `bot/services/rpg/content`.

## Run

```bash
python -m tools.rpg_admin --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`.

## Related Tools

```bash
python -m tools.rpg_balance --details
```

Runs the local RPG balance simulator. See `tools/rpg_balance/README.md`.

## Save Behavior

- `Save` validates references before writing files.
- Every successful save copies the current content folder to `.rpg_content_backups/<timestamp>`.
- Only the latest 20 backups are kept by default. Change this with `--backup-retention N`.
- Settings include level-up growth values for base attack, max HP, and defense.
- `level_curve.json` controls cumulative EXP with `base + linear*n + quadratic*n^2 + cubic*n^3`, where `n = level - 1`.
- Dungeons and bosses remain split into one JSON file per entry.
- Renaming item, material, or job IDs updates matching content references in the editor before saving.
- Deleting item, material, or job IDs removes matching content references in the editor before saving.
- Boss warning templates contain their own failure effect.
- Boss warning failure effects can include fixed or max-HP-ratio plain damage.
- Boss warning templates can define stack-conditioned failure variants.
- Bosses can define HP instant effects that run at turn start when HP first falls below a threshold.
- A single HP instant effect can have multiple HP thresholds.
- Stack effects have their own editor tab and can be changed by skill or boss effect actions.
- Skill and boss effect actions can define stack conditions; an action with conditions only runs when all of them match.
- Bosses can list encounter stack effects with an initial stack count; these stacks are tracked per participant during boss fights.
- HP/CT triggers link to a boss warning template by ID.
- CT warning HP thresholds are upper bounds: `1`, `0.5`, `0.25` maps to `1~0.5`, `0.5~0.25`, and `0.25~0`.
- A warning template can require multiple objectives at once, such as damage, hit count, and debuff count.
- Combat special effects support flurry, double strike, and bonus damage. Use `duration: -1` for infinite duration.
- Critical reinforce, dispel, clear all, double/triple attack objectives, ability-use objectives, and multi-turn warnings are supported.
- Buff/debuff effects can be marked undispellable.
