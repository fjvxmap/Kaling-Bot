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
- Renaming item, material, job, or boss pattern IDs updates matching content references in the editor before saving.
- Deleting item, material, job, or boss pattern IDs removes matching content references in the editor before saving.
