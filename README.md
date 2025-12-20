# Clue Board Game with LLM Agents

A multi-agent implementation of the classic Clue (Cluedo) board game using CrewAI and Google Gemini 2.5 Flash LLM. Six AI agents compete to solve the murder mystery following the **official game rules** from [Wikipedia](https://en.wikipedia.org/wiki/Cluedo#Rules).

## Game Overview

In this game, 6 AI players investigate a murder at Tudor Mansion:
- **Who** committed the crime (6 suspects)
- **What** weapon was used (6 weapons)  
- **Where** the crime took place (9 rooms)

Each player uses deduction and strategy to be the first to solve the mystery!

## Players

| Character | Description | Starting Advantage |
|-----------|-------------|-------------------|
| **Miss Scarlet** | The cunning femme fatale | Traditionally moves first |
| **Colonel Mustard** | Retired military officer | Near Lounge entrance |
| **Mr. Green** | The analytical businessman | Near Conservatory |
| **Mrs. Peacock** | Elegant aristocrat | Closest to first room (1 space advantage!) |
| **Professor Plum** | Absent-minded academic | Near Study (Kitchen passage) |
| **Mrs. White** | The observant housekeeper | Near Ballroom entrance |

## Official Rules Implemented

Based on the [official Cluedo rules](https://en.wikipedia.org/wiki/Cluedo#Rules):

### Game Flow

```
SETUP:
  1. Randomly select 1 suspect, 1 weapon, 1 room -> place in SOLUTION ENVELOPE
  2. Shuffle remaining 18 cards and deal to all players
  3. Each player records their cards in their Detective Notebook
  4. Miss Scarlet goes first (or highest dice roll)

TURN ORDER (clockwise from Miss Scarlet):

  +------------------+
  |   START TURN     |
  +--------+---------+
           |
           v
  +------------------+
  |   ROLL DICE      |  (If you roll a 1, it shows magnifying glass = free clue!)
  +--------+---------+
           |
           v
  +------------------+
  |   MOVE           |  Options:
  |                  |  - Move through doors to adjacent room
  +--------+---------+  - Use secret passage (corner rooms only)
           |            - Stay if moved here by another's suggestion
           v
  +------------------+
  | IN A ROOM?       |--NO--> End turn, next player
  +--------+---------+
           | YES
           v
  +------------------+
  | MAKE SUGGESTION  |  "I suggest it was [SUSPECT] with the [WEAPON]
  | (optional)       |   in the [CURRENT ROOM]"
  +--------+---------+
           |
           v
  +------------------+
  | DISPROVAL        |  Clockwise from you:
  | (automatic)      |  - Each player checks if they have any suggested card
  +--------+---------+  - First player with a match shows you ONE card (secret)
           |            - If no one can disprove -> STRONG LEAD!
           v
  +------------------+
  | MAKE ACCUSATION  |  "I accuse [SUSPECT] with the [WEAPON]
  | (optional)       |   in the [ROOM]" (can be any room!)
  +--------+---------+
           |
      +----+----+
      |         |
   CORRECT    WRONG
      |         |
      v         v
  +------+  +------------------+
  | WIN! |  | ELIMINATED       |
  +------+  | (still disprove) |
            +------------------+
           |
           v
  +------------------+
  |   END TURN       |  -> Next player clockwise
  +------------------+

WINNING CONDITIONS:
  - Make a correct accusation, OR
  - Be the last active player (all others eliminated)
```

### Board Layout

The mansion layout with 9 rooms and their door positions:

```
+-------------+-------------+-------------+
|   KITCHEN   |  BALLROOM   |CONSERVATORY |
|   (1 door   | (2 doors    |  (1 door    |
|    south)   |  SW + SE)   |    west)    |
+-------------+-------------+-------------+
| DINING ROOM |   [CLUE]    |BILLIARD ROOM|
|  (2 doors   |  Staircase  |  (2 doors   |
|  N + E)     | (blocked)   |   W + S)    |
+-------------+-------------+-------------+
|   LOUNGE    |    HALL     |   LIBRARY   |
|  (1 door    |  (3 doors   |  (2 doors   |
|    east)    |  NW+N+NE)   |   N + W)    |
+-------------+-------------+-------------+
|             |             |    STUDY    |
|             |             |  (1 door    |
|             |             |   north)    |
+-------------+-------------+-------------+
```

### Movement
- **Dice rolling** - Roll two six-sided dice for movement
- **Magnifying glass** - Rolling a 1 shows a magnifying glass and gives you a free clue!
- **Doors only** - You can only enter/exit rooms through their specific doors
- **Secret passages** - Corner rooms connect diagonally (no dice needed):
  - Kitchen <-> Study (top-left to bottom-right)
  - Conservatory <-> Lounge (top-right to bottom-left)

### Suggestions
- **Room-based** - You can only suggest while in a room, about THAT room
- **Suspect movement** - Suggested suspect token is moved to your room
- **Clockwise disproving** - Players go clockwise; first one with a matching card shows ONE card
- **No repeated suggestions** - Cannot suggest again in same room without leaving first (American rules)
- **Exception** - If moved to a room by another's suggestion, you can suggest immediately
- **Notebook validation** - Warns if suggesting cards already known (crossed out in notebook)

### Accusations  
- **Any room** - Accusations can include any room (not just current location)
- **Secret check** - You secretly check the solution envelope
- **Correct** - You win the game!
- **Wrong** - You're eliminated but must still show cards to disprove others
- **Once per turn** - You can only make one accusation per turn
- **Notebook validation** - Accusations are BLOCKED if they include crossed-out cards

### Cards
- **21 cards total** - 6 suspects + 6 weapons + 9 rooms
- **Solution envelope** - One card of each type hidden
- **Dealt cards** - Remaining cards dealt to players
- **One card shown** - When disproving, show only ONE matching card

## Technical Stack

- **Framework**: [CrewAI](https://github.com/joaomdmoura/crewAI) for multi-agent orchestration
- **LLM**: Google Gemini 2.5 Flash
- **Package Manager**: [uv](https://github.com/astral-sh/uv)
- **Python**: 3.11+

## Installation

```bash
# Clone the repository
git clone https://github.com/nmadhire-vibecoding/clue-board-game-with-llm.git
cd clue-board-game-with-llm

# Install dependencies with uv
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

## Running the Game

```bash
# Run a full game
uv run clue-game

# Or run directly
uv run python -m clue_game.main
```

## Project Structure

```
src/clue_game/
├── __init__.py
├── main.py              # Entry point
├── game_state.py        # Game state management (official rules)
├── crew.py              # CrewAI agent definitions
├── notebook.py          # Deterministic detective notebook
├── config/
│   ├── agents.yaml      # Agent personalities & rules knowledge
│   └── tasks.yaml       # Task definitions
└── tools/
    ├── __init__.py
    ├── game_tools.py    # Game action tools (move, suggest, accuse)
    └── notebook_tools.py # Detective notebook tools
```

## Detective Notebook

LLMs are notoriously bad at maintaining long-term logic across many turns. To solve this, each agent has a **deterministic Detective Notebook** that:

- Tracks card ownership in a grid (Card x Player)
- Records all suggestions and outcomes
- Auto-deduces solution when all players don't have a card
- Provides strategic suggestions based on current knowledge
- **Validates suggestions** - Warns when suggesting known cards (wastes a turn)
- **Validates accusations** - BLOCKS accusations that contradict notebook (prevents elimination)
- **Recommends accusations** - Tells agent when all 3 categories narrowed to 1 option

This prevents the AI from "forgetting" crucial information during the game!

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Your Google AI API key for Gemini 2.5 Flash |

## License

MIT License - See [LICENSE](LICENSE) file
