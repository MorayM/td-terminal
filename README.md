# td-cli

Interactive terminal client for Todoist. Pure Python, no external dependencies.

## Setup

1. Create virtual environment (Python 3.14+):
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Get your Todoist API token from [Todoist Settings > Integrations](https://app.todoist.com/app/settings/integrations)

3. Create `.env` file:
   ```
   TODOIST_API_KEY=your_token_here
   ```

4. Run:
   ```bash
   python main.py
   ```

## Development

Code style: Black (format) and Flake8 (lint), 88-char line length. Install dev deps: `pip install -e ".[dev]"`. Then run `black .` and `flake8 .`.

## Commands

| Command | Action |
|---------|--------|
| `NUMBER` | Complete task (e.g., `5`) |
| `r` | Reload tasks |
| `a` | Add new task |
| `a <task>` | Add task directly |
| `eNUMBER` | Edit task (e.g., `e5`) |
| `dNUMBER` | Delete task (e.g., `d5`) |
| `f #Project` | Filter by project |
| `f` | Clear filter |
| `?` or `h` | Help |
| `q` | Quit |

## Task Syntax

When adding/editing tasks:

```
Buy milk #Shopping @home p1 tomorrow
```

- `#Project` - Assign to project
- `@label` - Add label (multiple allowed)
- `p1`/`p2`/`p3` - Priority (p1 = urgent)
- Date keywords: `today`, `tomorrow`, `monday`, etc.

## Navigation

- `↑`/`↓` - Scroll task list
- `PgUp`/`PgDn` - Scroll by page
- `Esc` - Cancel current input

## Priority Colors

- Red dot = P1 (urgent)
- Yellow dot = P2
- Cyan dot = P3
- White dot = P4 (normal)

## Requirements

- Python 3.14+
- Unix-like OS (curses required)
- Todoist account with API token
