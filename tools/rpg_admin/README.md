# RPG Content Admin

Local editor for `bot/services/rpg/content`.

## Run

```bash
python -m tools.rpg_admin --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`.

## Save Behavior

- `Save` validates references before writing files.
- Every successful save copies the current content folder to `.rpg_content_backups/<timestamp>`.
- Dungeons and bosses remain split into one JSON file per entry.
- Renaming item, material, or job IDs updates matching content references in the editor before saving.
- Deleting item, material, or job IDs removes matching content references in the editor before saving.
- Boss warnings are edited as paired sets: trigger condition, clear objective, and the failure effect that fires if the objective is not met.
