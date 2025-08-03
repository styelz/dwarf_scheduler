# Session Scheduling Workflow

## Overview

The Dwarf3 Telescope Scheduler now automatically manages session files when adding to and removing from the schedule queue. This prevents editing of scheduled sessions and maintains data integrity.

## How It Works

### Adding Sessions to Schedule

1. **From Sessions Tab**: When you click "Add to Schedule" on a session:
   - If the session already exists in the `Sessions/Available/` folder, it's moved to `Sessions/ToDo/`
   - If it's a new session, it's saved directly to `Sessions/ToDo/`
   - The session disappears from the Available sessions list
   - The session appears in the Schedule queue

### Removing Sessions from Schedule

1. **From Schedule Tab**: When you click "Remove from Queue" on a scheduled session:
   - The session file is moved from `Sessions/ToDo/` back to `Sessions/Available/`
   - The session disappears from the Schedule queue
   - The session becomes available for editing in the Sessions tab again

## Directory Structure

```
Sessions/
├── Available/     # Sessions available for editing and scheduling
├── ToDo/         # Sessions queued for execution (read-only)
├── Running/      # Currently executing sessions
├── Done/         # Successfully completed sessions
├── Failed/       # Failed or aborted sessions
└── History/      # Session history tracking
```

## Benefits

- **Prevents Conflicts**: Scheduled sessions cannot be accidentally edited
- **Data Integrity**: Clear separation between editable and queued sessions
- **Automatic Management**: No manual file management required
- **Session Tracking**: Easy to see which sessions are available vs. scheduled

## Usage Notes

- Sessions in the `ToDo` folder are automatically picked up by the scheduler
- Moving sessions between folders happens automatically - no manual intervention needed
- Each session gets a unique ID to prevent conflicts during moves
- The GUI automatically refreshes to reflect file movements

## Example Workflow

1. Create a session in the **Sessions** tab
2. Click **"Add to Schedule"** → Session moves from Available to ToDo
3. Session appears in **Schedule** tab queue
4. If you change your mind, click **"Remove from Queue"** → Session moves back to Available
5. Session can be edited again in the **Sessions** tab
