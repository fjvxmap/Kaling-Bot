# RPG Content Admin

Local content editor for `bot/services/rpg/content`. It is not part of the production service set and only runs when started explicitly.

## Run

```bash
python -m tools.rpg_admin --host 127.0.0.1 --port 8787
```

Open `http://127.0.0.1:8787`.

## Navigation

- `Ctrl+K` focuses global content search and can jump directly to matching records.
- `Ctrl+S` validates and saves the current content.
- Large lists have section-specific search and filters.
- Large item/material relation fields use searchable pickers with bounded result sets.
- Current tab, selected records, filters, expanded groups, and independent list scroll positions are preserved for the browser session.
- Editing a detail pane does not rebuild or reset the master list.

The layout uses a fixed navigation rail, searchable master list, and independent detail pane. On narrow screens these collapse into a touch-friendly single-column flow.

## Content

The editor covers items, materials, jobs, skills, stack effects, dungeons, enemies, bosses, gacha, enhancement, potentials, liberation, and global settings. Boss editing includes normal/hard variants, warning conditions, HP/CT triggers, instant effects, HP locks, stack interactions, and separate reward tables.

Hard-mode fields can override level, HP, stats, rewards, warning damage, plain damage, and objective scaling while inheriting the normal boss mechanics.

## Save Behavior

- Save validates identifiers and cross-file references before writing.
- Successful saves copy the previous content into `.rpg_content_backups/<timestamp>`.
- The newest 20 backups are retained by default; use `--backup-retention N` to change the limit.
- Dungeon and boss definitions remain split into one JSON file per record.
- Renaming or deleting item, material, and job IDs updates matching references in the in-memory editor before save.
- ID fields normalize uppercase to lowercase, whitespace to underscores, and accented Latin characters to ASCII.

Validate without starting the UI:

```bash
python -c "from tools.rpg_admin.app import read_content, normalize_content, validate_content; c=read_content(); normalize_content(c); e=validate_content(c); print(f'errors={len(e)}'); print('\\n'.join(e[:30]))"
```

## Balance Tool

```bash
python -m tools.rpg_balance --details
```

See [the balance simulator reference](../rpg_balance/README.md).
