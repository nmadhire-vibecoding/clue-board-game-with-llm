"""
Game State Management for Clue Board Game
Based on official Cluedo/Clue rules (https://en.wikipedia.org/wiki/Cluedo#Rules)

Key rules implemented:
- Dice rolling for movement (move exactly that many squares)
- Movement is horizontal or vertical only (no diagonal)
- Cannot pass through or land on occupied hallway squares
- Movement stops upon entering a room (even if moves remain)
- Cannot visit the same square twice in one turn
- Clockwise turn order starting with Miss Scarlet
- Secret passages between diagonal corner rooms
- Suggestions can only be made in rooms, about that room
- Suggested suspect/weapon tokens move to the room
- Player must leave and re-enter room to make another suggestion (American rules)
- Accusations can include any room, not just current location
- Wrong accusations eliminate player but they must still show cards to disprove
"""

import random
from dataclasses import dataclass, field
from typing import Optional, Tuple, List, Set
from enum import Enum


class Suspect(Enum):
    MISS_SCARLET = "Miss Scarlet"
    COLONEL_MUSTARD = "Colonel Mustard"
    MRS_WHITE = "Mrs. White"
    MR_GREEN = "Mr. Green"
    MRS_PEACOCK = "Mrs. Peacock"
    PROFESSOR_PLUM = "Professor Plum"


class Weapon(Enum):
    CANDLESTICK = "Candlestick"
    KNIFE = "Knife"
    LEAD_PIPE = "Lead Pipe"
    REVOLVER = "Revolver"
    ROPE = "Rope"
    WRENCH = "Wrench"


class Room(Enum):
    KITCHEN = "Kitchen"
    BALLROOM = "Ballroom"
    CONSERVATORY = "Conservatory"
    BILLIARD_ROOM = "Billiard Room"
    LIBRARY = "Library"
    STUDY = "Study"
    HALL = "Hall"
    LOUNGE = "Lounge"
    DINING_ROOM = "Dining Room"


# Cell types for the board grid
class CellType(Enum):
    WALL = "W"           # Impassable wall/void
    HALLWAY = "H"        # Walkable hallway square
    ROOM = "R"           # Inside a room (can't walk through)
    DOOR = "D"           # Room entrance/exit
    START = "S"          # Starting position


# ============================================================================
# BOARD GRID DEFINITION
# The Clue board is represented as a 25x24 grid (columns x rows)
# Based on the actual Hasbro Clue board layout
# 
# Legend:
#   W = Wall/void (impassable)
#   H = Hallway (walkable)
#   K = Kitchen, B = Ballroom, C = Conservatory
#   D = Dining Room, I = Billiard Room, L = Library  
#   O = Lounge, A = Hall, S = Study
#   1-6 = Starting positions for each suspect
#   d = Door (room entrance)
# ============================================================================

# Board dimensions
BOARD_WIDTH = 24   # columns (0-23)
BOARD_HEIGHT = 25  # rows (0-24)

# Room codes for the grid (maps to Room enum)
ROOM_CODES = {
    'K': Room.KITCHEN,
    'B': Room.BALLROOM,
    'C': Room.CONSERVATORY,
    'D': Room.DINING_ROOM,
    'I': Room.BILLIARD_ROOM,
    'L': Room.LIBRARY,
    'O': Room.LOUNGE,
    'A': Room.HALL,
    'S': Room.STUDY,
}

# Starting position codes map to suspects
START_CODES = {
    '1': Suspect.MISS_SCARLET,     # Bottom - near Hall
    '2': Suspect.COLONEL_MUSTARD,   # Right side - near Lounge
    '3': Suspect.MRS_WHITE,         # Top - near Ballroom  
    '4': Suspect.MR_GREEN,          # Top - near Conservatory
    '5': Suspect.MRS_PEACOCK,       # Left side - near Conservatory
    '6': Suspect.PROFESSOR_PLUM,    # Left side - near Library
}

# The actual board layout as a string grid
# Each row is a string of 24 characters
# Doors are marked with lowercase letters matching the room
BOARD_LAYOUT = [
    # Row 0 (top edge)
    "WWWWWWWWWW3WWWWW4WWWWWWWW",
    # Row 1
    "KKKKKK.WHHHHHHHHWW.CCCCCC",
    # Row 2
    "KKKKKK.HHHWWWWWWHH.CCCCCC",
    # Row 3
    "KKKKKK.HHWWBBBBWWH.CCCCCC",
    # Row 4
    "KKKKKK.HHWBBBBBBWH.CCCCCC",
    # Row 5
    "KKKKKK.HHbBBBBBBbH.CCCCCc",
    # Row 6
    "WWWWWWkHHWBBBBBBWHHHHHHHW",
    # Row 7
    "HHHHHHHHHWWWWWWWWHHHHHHH5",
    # Row 8
    "W.HHHHHHHHHHHHHHHHHHHHHHW",
    # Row 9
    "DDDDDD.HHHHHHHHHHHHW.IIII",
    # Row 10
    "DDDDDD.HHHHHHHHHHHHW.IIII",
    # Row 11
    "DDDDDD.HHHHHHHHHHHHW.IIII",
    # Row 12
    "DDDDDDdHHWWWWWWWWHHiIIIII",
    # Row 13
    "DDDDDD.HHWAAAAAWHHHHIIIII",
    # Row 14
    "DDDDDD.HHaAAAAAaHHHHWiWWW",
    # Row 15
    "WWWWWW.HHWAAAAAAWHHHHHHHH",
    # Row 16
    "WHHHHHHHHHWAAAAAWHHHHHHH6",
    # Row 17
    "W.HHHHHHHHWAAAAAAWHHHHHWW",
    # Row 18
    "OOOOOOoHHWWWWaWWWHH.LLLLL",
    # Row 19
    "OOOOOOO.HHHHHHHHHHH.LLLLL",
    # Row 20
    "OOOOOOO.HHWWWWWWWHH.LLLLl",
    # Row 21
    "OOOOOOO.HHWSSSSSWHHlLLLLL",
    # Row 22
    "OOOOOOO.HHWSSSSSWHH.LLLLL",
    # Row 23
    "WWWWWWW2HHsSSSSSsHHWWWWWW",
    # Row 24 (bottom edge)
    "WWWWWWWWWHHH1HHHHHWWWWWWW",
]

# Door positions and which room they belong to
# Format: (row, col): Room
DOOR_POSITIONS = {
    # Kitchen door (row 6, col 6)
    (6, 6): Room.KITCHEN,
    # Ballroom doors (row 5)
    (5, 8): Room.BALLROOM,
    (5, 15): Room.BALLROOM,
    # Conservatory door (row 5, col 22)
    (5, 22): Room.CONSERVATORY,
    # Dining Room door (row 12, col 6)
    (12, 6): Room.DINING_ROOM,
    # Billiard Room doors
    (12, 17): Room.BILLIARD_ROOM,
    (14, 21): Room.BILLIARD_ROOM,
    # Hall doors (row 14)
    (14, 9): Room.HALL,
    (14, 15): Room.HALL,
    (18, 14): Room.HALL,
    # Lounge door (row 18, col 6)
    (18, 6): Room.LOUNGE,
    # Library doors
    (20, 22): Room.LIBRARY,
    (21, 17): Room.LIBRARY,
    # Study doors (row 23)
    (23, 9): Room.STUDY,
    (23, 16): Room.STUDY,
}

# Starting positions (grid coordinates)
# Format: Suspect: (row, col)
STARTING_GRID_POSITIONS = {
    Suspect.MISS_SCARLET: (24, 11),     # Bottom center - '1' on board
    Suspect.COLONEL_MUSTARD: (23, 7),   # Bottom right area - '2' on board  
    Suspect.MRS_WHITE: (0, 10),         # Top - '3' on board
    Suspect.MR_GREEN: (0, 15),          # Top right - '4' on board
    Suspect.MRS_PEACOCK: (7, 23),       # Right side - '5' on board
    Suspect.PROFESSOR_PLUM: (16, 23),   # Right side lower - '6' on board
}

# Inverse mapping for display
SUSPECT_START_CODES = {v: k for k, v in START_CODES.items()}


def get_cell_type(row: int, col: int) -> Tuple[CellType, Optional[Room]]:
    """
    Get the cell type and room (if applicable) at a grid position.
    
    Returns:
        (CellType, Room or None)
    """
    if row < 0 or row >= BOARD_HEIGHT or col < 0 or col >= BOARD_WIDTH:
        return (CellType.WALL, None)
    
    char = BOARD_LAYOUT[row][col]
    
    if char == 'W':
        return (CellType.WALL, None)
    elif char == 'H' or char == '.':
        return (CellType.HALLWAY, None)
    elif char in '123456':
        return (CellType.START, None)
    elif char.isupper() and char in ROOM_CODES:
        return (CellType.ROOM, ROOM_CODES[char])
    elif char.islower():
        # Door - find which room it belongs to
        room_char = char.upper()
        if room_char in ROOM_CODES:
            return (CellType.DOOR, ROOM_CODES[room_char])
    
    return (CellType.HALLWAY, None)


def is_walkable(row: int, col: int, entering_room_ok: bool = True) -> bool:
    """Check if a cell is walkable (hallway, start, or door)."""
    cell_type, _ = get_cell_type(row, col)
    if cell_type == CellType.HALLWAY or cell_type == CellType.START:
        return True
    if cell_type == CellType.DOOR and entering_room_ok:
        return True
    return False


def get_room_at_door(row: int, col: int) -> Optional[Room]:
    """Get the room that a door leads to."""
    cell_type, room = get_cell_type(row, col)
    if cell_type == CellType.DOOR:
        return room
    return None


def get_adjacent_cells(row: int, col: int) -> List[Tuple[int, int]]:
    """Get orthogonally adjacent cells (no diagonal movement)."""
    return [
        (row - 1, col),  # Up
        (row + 1, col),  # Down
        (row, col - 1),  # Left
        (row, col + 1),  # Right
    ]
# Each room has specific doors that connect to hallways
# Format: { Room: [(door_side, connects_to_hallway_toward), ...] }
ROOM_DOORS = {
    Room.KITCHEN: [("south", "toward_ballroom_hallway")],  # 1 door on bottom
    Room.BALLROOM: [("southwest", "toward_kitchen"), ("southeast", "toward_conservatory")],  # 2 doors on bottom corners
    Room.CONSERVATORY: [("west", "toward_billiard_hallway")],  # 1 door on left side
    Room.BILLIARD_ROOM: [("west", "toward_hall_hallway"), ("south", "toward_library")],  # 2 doors
    Room.LIBRARY: [("north", "toward_billiard"), ("west", "toward_study_hallway")],  # 2 doors
    Room.STUDY: [("north", "toward_library_hallway")],  # 1 door on top
    Room.HALL: [("northwest", "toward_lounge"), ("north", "toward_billiard"), ("northeast", "toward_study")],  # 3 doors on top
    Room.LOUNGE: [("east", "toward_hall")],  # 1 door on right side
    Room.DINING_ROOM: [("north", "toward_kitchen_hallway"), ("east", "toward_lounge_hallway")],  # 2 doors
}

# Room adjacency for movement - based on ACTUAL board layout with hallway connections
# Rooms connect through hallways via their doors - NO diagonal shortcuts except secret passages
# Verified against the physical Clue board image
ROOM_CONNECTIONS = {
    # Top row
    Room.KITCHEN: [Room.BALLROOM, Room.DINING_ROOM],  # Door leads to hallway connecting to Ballroom and down to Dining Room
    Room.BALLROOM: [Room.KITCHEN, Room.CONSERVATORY],  # Two doors on bottom - left to Kitchen, right to Conservatory
    Room.CONSERVATORY: [Room.BALLROOM, Room.BILLIARD_ROOM],  # Door on left leads to Ballroom and down to Billiard
    
    # Middle row
    Room.DINING_ROOM: [Room.KITCHEN, Room.LOUNGE],  # Door up to Kitchen, door right connects down to Lounge
    Room.BILLIARD_ROOM: [Room.CONSERVATORY, Room.LIBRARY, Room.HALL],  # Left door to Conservatory hallway, bottom to Library, can reach Hall
    
    # Bottom row  
    Room.LIBRARY: [Room.BILLIARD_ROOM, Room.STUDY],  # Top door to Billiard, left door to Study hallway
    Room.LOUNGE: [Room.DINING_ROOM, Room.HALL],  # Up to Dining Room hallway, right to Hall
    Room.HALL: [Room.LOUNGE, Room.BILLIARD_ROOM, Room.STUDY],  # Left to Lounge, up to Billiard hallway, right to Study
    Room.STUDY: [Room.HALL, Room.LIBRARY],  # Left/top door to Hall, can reach Library through hallway
}

# Secret passages connect diagonal corner rooms (can use instead of door movement)
SECRET_PASSAGES = {
    Room.KITCHEN: Room.STUDY,        # Top-left to bottom-right
    Room.STUDY: Room.KITCHEN,        # Bottom-right to top-left
    Room.CONSERVATORY: Room.LOUNGE,  # Top-right to bottom-left
    Room.LOUNGE: Room.CONSERVATORY,  # Bottom-left to top-right
}

# Starting positions for each suspect - these are hallway squares on the edge of the board
# Players start OUTSIDE rooms and must roll dice to enter a room
# Format: { Suspect: "position_name" } - used for display
STARTING_POSITION_NAMES = {
    Suspect.MISS_SCARLET: "Hallway near Hall (bottom)",     # Red - bottom edge below Hall
    Suspect.COLONEL_MUSTARD: "Hallway near Lounge (right)",  # Yellow - right edge near Lounge
    Suspect.MRS_WHITE: "Hallway near Ballroom (top)",        # White - top edge near Ballroom
    Suspect.MR_GREEN: "Hallway near Conservatory (top)",     # Green - top edge near Conservatory
    Suspect.MRS_PEACOCK: "Hallway near Conservatory (left)", # Blue - left edge near Conservatory
    Suspect.PROFESSOR_PLUM: "Hallway near Library (left)",   # Purple - left edge near Library
}

# Rooms reachable from each starting position (first move options)
# Based on the actual Clue board layout - which rooms can you enter from your START square
STARTING_POSITION_MOVES = {
    Suspect.MISS_SCARLET: [Room.HALL, Room.LOUNGE],           # Can reach Hall or Lounge
    Suspect.COLONEL_MUSTARD: [Room.LOUNGE, Room.DINING_ROOM], # Can reach Lounge or Dining Room
    Suspect.MRS_WHITE: [Room.BALLROOM, Room.KITCHEN],         # Can reach Ballroom or Kitchen
    Suspect.MR_GREEN: [Room.CONSERVATORY, Room.BALLROOM],     # Can reach Conservatory or Ballroom
    Suspect.MRS_PEACOCK: [Room.CONSERVATORY, Room.LIBRARY],   # Can reach Conservatory or Library
    Suspect.PROFESSOR_PLUM: [Room.LIBRARY, Room.STUDY],       # Can reach Library or Study
}

# Legacy compatibility - maps to first room option (for display when in hallway)
STARTING_POSITIONS = {
    Suspect.MISS_SCARLET: None,        # Starts in hallway, not a room
    Suspect.COLONEL_MUSTARD: None,
    Suspect.MRS_WHITE: None,
    Suspect.MR_GREEN: None,
    Suspect.MRS_PEACOCK: None,
    Suspect.PROFESSOR_PLUM: None,
}


@dataclass
class Card:
    """Represents a Clue game card."""
    name: str
    card_type: str  # 'suspect', 'weapon', or 'room'
    
    def __hash__(self):
        return hash((self.name, self.card_type))
    
    def __eq__(self, other):
        if isinstance(other, Card):
            return self.name == other.name and self.card_type == other.card_type
        return False


@dataclass
class Suggestion:
    """Represents a suggestion made by a player."""
    suggester: str
    suspect: str
    weapon: str
    room: str
    disproven_by: Optional[str] = None
    card_shown: Optional[str] = None


@dataclass
class Player:
    """Represents a player in the game."""
    name: str
    character: Suspect
    cards: list[Card] = field(default_factory=list)
    current_room: Optional[Room] = None  # None means in hallway/starting position
    is_active: bool = True  # False if player made wrong accusation
    knowledge: dict = field(default_factory=dict)  # Track what player knows
    last_suggestion_room: Optional[Room] = None  # Track last room where suggestion was made
    has_moved_since_suggestion: bool = True  # Must move/leave room before suggesting again (US rules)
    was_moved_by_suggestion: bool = False  # If pulled into room by another's suggestion
    has_accused_this_turn: bool = False  # Can only accuse once per turn
    in_hallway: bool = True  # True when player is in hallway (starting position or between rooms)
    entered_room_this_turn: bool = False  # True when player enters a room during their turn
    
    # Grid-based position tracking
    position: Optional[Tuple[int, int]] = None  # (row, col) on the board grid
    moves_remaining: int = 0  # Moves left in current turn
    visited_this_turn: Set[Tuple[int, int]] = field(default_factory=set)  # Squares visited this turn
    
    def __post_init__(self):
        # Initialize knowledge tracking
        self.knowledge = {
            "my_cards": [],
            "seen_cards": [],  # Cards shown to this player
            "suggestions_made": [],
            "suggestions_witnessed": [],
            "eliminated_suspects": [],
            "eliminated_weapons": [],
            "eliminated_rooms": [],
        }
        # Initialize visited_this_turn as a set
        if self.visited_this_turn is None:
            self.visited_this_turn = set()
    
    def get_position_display(self) -> str:
        """Get a human-readable position description."""
        if self.current_room and not self.in_hallway:
            return self.current_room.value
        elif self.position:
            return f"Hallway ({self.position[0]}, {self.position[1]})"
        else:
            return STARTING_POSITION_NAMES.get(self.character, "Unknown")


@dataclass
class GameState:
    """Main game state manager."""
    players: list[Player] = field(default_factory=list)
    solution: dict = field(default_factory=dict)  # The murder solution
    current_player_index: int = 0
    turn_number: int = 1
    game_over: bool = False
    winner: Optional[str] = None
    suggestion_history: list[Suggestion] = field(default_factory=list)
    
    def setup_game(self, player_names: list[str]) -> None:
        """Initialize the game with players and deal cards."""
        # Create all cards
        suspect_cards = [Card(s.value, "suspect") for s in Suspect]
        weapon_cards = [Card(w.value, "weapon") for w in Weapon]
        room_cards = [Card(r.value, "room") for r in Room]
        
        # Select solution (one of each type)
        solution_suspect = random.choice(suspect_cards)
        solution_weapon = random.choice(weapon_cards)
        solution_room = random.choice(room_cards)
        
        self.solution = {
            "suspect": solution_suspect,
            "weapon": solution_weapon,
            "room": solution_room,
        }
        
        # Remove solution cards from deck
        remaining_cards = [c for c in suspect_cards + weapon_cards + room_cards 
                          if c not in [solution_suspect, solution_weapon, solution_room]]
        
        # Shuffle remaining cards
        random.shuffle(remaining_cards)
        
        # Assign characters to players
        # Assign characters to players in order (or random)
        available_characters = list(Suspect)
        random.shuffle(available_characters)
        
        # Create players with proper starting positions (in hallway, not in rooms)
        self.players = []
        for i, name in enumerate(player_names):
            character = available_characters[i]
            # Get starting grid position for this character
            start_pos = STARTING_GRID_POSITIONS.get(character, (0, 0))
            # Players start in hallway (current_room = None, in_hallway = True)
            player = Player(
                name=name,
                character=character,
                current_room=None,  # Not in any room yet - in hallway at START
                in_hallway=True,
                position=start_pos,  # Grid position
                moves_remaining=0,
                visited_this_turn=set(),
            )
            self.players.append(player)
        
        # Sort players so Miss Scarlet goes first (traditional rule)
        # In modern versions, players roll dice and highest goes first
        scarlet_index = None
        for i, player in enumerate(self.players):
            if player.character == Suspect.MISS_SCARLET:
                scarlet_index = i
                break
        
        if scarlet_index is not None and scarlet_index != 0:
            # Move Miss Scarlet's player to the front
            scarlet_player = self.players.pop(scarlet_index)
            self.players.insert(0, scarlet_player)
        
        # Deal cards to players
        for i, card in enumerate(remaining_cards):
            player_index = i % len(self.players)
            self.players[player_index].cards.append(card)
            self.players[player_index].knowledge["my_cards"].append(card.name)
    
    def get_current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]
    
    def next_turn(self) -> None:
        """Advance to the next player's turn."""
        # Reset accusation flag for current player before moving on
        current = self.players[self.current_player_index]
        current.has_accused_this_turn = False
        
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        # Skip inactive players (those who made wrong accusations)
        attempts = 0
        while not self.players[self.current_player_index].is_active and attempts < len(self.players):
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            attempts += 1
        self.turn_number += 1
        
        # Reset accusation flag for new current player
        new_current = self.players[self.current_player_index]
        new_current.has_accused_this_turn = False
    
    def get_available_moves(self, player: Player) -> list[Room]:
        """
        Get rooms a player can move to from their current position.
        
        Movement options:
        1. From hallway/starting position: rooms reachable from that START square
        2. From a room: door connections (through hallways) and secret passages
        """
        # If player is in hallway (starting position), return rooms reachable from START
        if player.current_room is None or player.in_hallway:
            return list(STARTING_POSITION_MOVES.get(player.character, list(Room)))
        
        # Start with regular door/hallway connections
        available = list(ROOM_CONNECTIONS.get(player.current_room, []))
        
        # Add secret passage destination if in a corner room
        if player.current_room in SECRET_PASSAGES:
            secret_dest = SECRET_PASSAGES[player.current_room]
            if secret_dest not in available:
                available.append(secret_dest)
        
        return available
    
    def move_player(self, player: Player, room: Room) -> bool:
        """Move a player to a room if valid."""
        available = self.get_available_moves(player)
        if room in available:
            old_room = player.current_room
            player.current_room = room
            player.in_hallway = False  # Player is now in a room
            player.position = None  # Clear grid position when in room
            player.moves_remaining = 0  # Movement ends upon entering room
            # Track that player has moved (for repeated suggestion rule)
            if old_room != room:
                player.has_moved_since_suggestion = True
                player.was_moved_by_suggestion = False  # They moved voluntarily
            return True
        return False
    
    # ========================================================================
    # GRID-BASED MOVEMENT METHODS
    # ========================================================================
    
    def start_turn(self, player: Player, dice_total: int) -> None:
        """
        Start a player's turn with the given dice roll.
        Sets up movement tracking for the turn.
        """
        player.moves_remaining = dice_total
        player.visited_this_turn = set()
        player.entered_room_this_turn = False  # Reset room entry flag for new turn
        # Mark current position as visited
        if player.position:
            player.visited_this_turn.add(player.position)
    
    def get_occupied_positions(self, exclude_player: Optional[Player] = None) -> Set[Tuple[int, int]]:
        """Get all grid positions currently occupied by players in hallways."""
        occupied = set()
        for p in self.players:
            if p.position and p.in_hallway and p != exclude_player:
                occupied.add(p.position)
        return occupied
    
    def can_move_to_cell(self, player: Player, row: int, col: int, 
                          occupied: Set[Tuple[int, int]]) -> Tuple[bool, Optional[Room]]:
        """
        Check if a player can move to a specific cell.
        
        Returns:
            (can_move, room_if_entering) - True if can move, and the Room if this is a door
        """
        # Check bounds
        if row < 0 or row >= BOARD_HEIGHT or col < 0 or col >= BOARD_WIDTH:
            return (False, None)
        
        # Check if already visited this turn (no double-crossing)
        if (row, col) in player.visited_this_turn:
            return (False, None)
        
        # Check if occupied by another player
        if (row, col) in occupied:
            return (False, None)
        
        cell_type, room = get_cell_type(row, col)
        
        if cell_type == CellType.WALL or cell_type == CellType.ROOM:
            return (False, None)
        
        if cell_type == CellType.DOOR:
            # Can enter room through door
            return (True, room)
        
        if cell_type == CellType.HALLWAY or cell_type == CellType.START:
            return (True, None)
        
        return (False, None)
    
    def get_valid_moves_from_position(self, player: Player) -> List[Tuple[int, int, Optional[Room]]]:
        """
        Get all valid moves from player's current position.
        
        Returns list of (row, col, room_if_door) tuples.
        Room is None for hallway moves, or the Room if stepping on a door.
        """
        if not player.position or player.moves_remaining <= 0:
            return []
        
        occupied = self.get_occupied_positions(exclude_player=player)
        valid_moves = []
        
        for adj_row, adj_col in get_adjacent_cells(player.position[0], player.position[1]):
            can_move, room = self.can_move_to_cell(player, adj_row, adj_col, occupied)
            if can_move:
                valid_moves.append((adj_row, adj_col, room))
        
        return valid_moves
    
    def move_player_one_step(self, player: Player, row: int, col: int) -> Tuple[bool, Optional[Room], str]:
        """
        Move a player one step to an adjacent cell.
        
        Returns:
            (success, room_entered, message)
            - success: True if move was valid
            - room_entered: The Room if player entered a room, None otherwise
            - message: Description of what happened
        """
        if player.moves_remaining <= 0:
            return (False, None, "No moves remaining")
        
        if not player.position:
            return (False, None, "Player has no grid position (in room)")
        
        # Check if target is adjacent
        current_row, current_col = player.position
        if abs(row - current_row) + abs(col - current_col) != 1:
            return (False, None, "Can only move to adjacent squares (no diagonal)")
        
        occupied = self.get_occupied_positions(exclude_player=player)
        can_move, room = self.can_move_to_cell(player, row, col, occupied)
        
        if not can_move:
            # Determine reason
            if (row, col) in player.visited_this_turn:
                return (False, None, "Cannot visit the same square twice in one turn")
            if (row, col) in occupied:
                return (False, None, "Square is occupied by another player")
            return (False, None, "Cannot move to that square (wall or room interior)")
        
        # Execute the move
        old_pos = player.position
        player.position = (row, col)
        player.visited_this_turn.add((row, col))
        player.moves_remaining -= 1
        
        if room:
            # Entered a room through door - movement ends
            player.current_room = room
            player.in_hallway = False
            player.position = None  # Clear grid position
            player.moves_remaining = 0  # Movement ends
            player.has_moved_since_suggestion = True
            player.was_moved_by_suggestion = False
            player.entered_room_this_turn = True  # Mark that player entered a room this turn
            return (True, room, f"Entered {room.value}! Movement ends.")
        
        return (True, None, f"Moved to ({row}, {col}). {player.moves_remaining} moves remaining.")
    
    def get_reachable_rooms(self, player: Player) -> List[Tuple[Room, int, List[Tuple[int, int]]]]:
        """
        Find all rooms reachable with the player's remaining moves.
        Uses BFS to find shortest paths to room doors.
        
        Returns:
            List of (Room, distance, path) tuples for reachable rooms
        """
        if not player.position or player.moves_remaining <= 0:
            return []
        
        from collections import deque
        
        occupied = self.get_occupied_positions(exclude_player=player)
        start = player.position
        
        # BFS to find all reachable doors
        queue = deque([(start, 0, [start])])  # (position, distance, path)
        visited = {start}
        reachable_rooms = []
        
        while queue:
            pos, dist, path = queue.popleft()
            
            if dist >= player.moves_remaining:
                continue
            
            for adj_row, adj_col in get_adjacent_cells(pos[0], pos[1]):
                next_pos = (adj_row, adj_col)
                
                if next_pos in visited or next_pos in player.visited_this_turn:
                    continue
                if next_pos in occupied:
                    continue
                
                cell_type, room = get_cell_type(adj_row, adj_col)
                
                if cell_type == CellType.DOOR:
                    # Found a room door
                    new_path = path + [next_pos]
                    reachable_rooms.append((room, dist + 1, new_path))
                    visited.add(next_pos)
                elif cell_type in (CellType.HALLWAY, CellType.START):
                    visited.add(next_pos)
                    queue.append((next_pos, dist + 1, path + [next_pos]))
        
        return reachable_rooms
    
    def exit_room_to_hallway(self, player: Player, door_position: Tuple[int, int]) -> bool:
        """
        Move a player from a room to a hallway through a specific door.
        This uses 1 move and places the player at the door position.
        """
        if not player.current_room:
            return False
        
        # Verify door belongs to current room
        cell_type, room = get_cell_type(door_position[0], door_position[1])
        if cell_type != CellType.DOOR or room != player.current_room:
            return False
        
        # Check if door is blocked
        occupied = self.get_occupied_positions(exclude_player=player)
        if door_position in occupied:
            return False
        
        # Exit to hallway
        player.current_room = None
        player.in_hallway = True
        player.position = door_position
        player.visited_this_turn.add(door_position)
        if player.moves_remaining > 0:
            player.moves_remaining -= 1
        player.has_moved_since_suggestion = True
        player.was_moved_by_suggestion = False
        
        return True
    
    def get_room_doors(self, room: Room) -> List[Tuple[int, int]]:
        """Get all door positions for a room."""
        doors = []
        for pos, r in DOOR_POSITIONS.items():
            if r == room:
                doors.append(pos)
        return doors
    
    def use_secret_passage(self, player: Player) -> Tuple[bool, str]:
        """
        Use a secret passage if available.
        
        Returns:
            (success, message)
        """
        if not player.current_room:
            return (False, "Must be in a room to use secret passage")
        
        if player.current_room not in SECRET_PASSAGES:
            return (False, f"{player.current_room.value} has no secret passage")
        
        dest_room = SECRET_PASSAGES[player.current_room]
        player.current_room = dest_room
        player.in_hallway = False
        player.position = None
        player.moves_remaining = 0  # Using passage ends movement
        player.has_moved_since_suggestion = True
        player.was_moved_by_suggestion = False
        player.entered_room_this_turn = True  # Mark that player entered a room this turn
        
        return (True, f"Used secret passage to {dest_room.value}!")
    
    def roll_dice(self) -> tuple[int, int, int]:
        """
        Roll two six-sided dice for movement.
        
        One die face shows a magnifying glass instead of 1.
        When rolled, the magnifying glass lets you peek at a clue.
        
        Returns:
            (die1, die2, magnifying_glass_count) where magnifying_glass_count
            is 0, 1, or 2 depending on how many 1s were rolled.
        """
        die1 = random.randint(1, 6)
        die2 = random.randint(1, 6)
        # Count magnifying glasses (1s on dice)
        magnifying_count = (1 if die1 == 1 else 0) + (1 if die2 == 1 else 0)
        return die1, die2, magnifying_count
    
    def get_random_clue(self, player: Player) -> Optional[str]:
        """
        Get a random clue for the magnifying glass ability.
        
        Returns a hint about a card that is NOT in the solution,
        helping the player narrow down possibilities.
        """
        # Collect all cards NOT in solution and NOT in player's hand
        player_card_names = {c.name for c in player.cards}
        solution_names = {
            self.solution["suspect"].name,
            self.solution["weapon"].name,
            self.solution["room"].name,
        }
        
        # Build list of cards that could be revealed as clues
        all_cards = []
        for s in Suspect:
            if s.value not in solution_names and s.value not in player_card_names:
                all_cards.append(("suspect", s.value))
        for w in Weapon:
            if w.value not in solution_names and w.value not in player_card_names:
                all_cards.append(("weapon", w.value))
        for r in Room:
            if r.value not in solution_names and r.value not in player_card_names:
                all_cards.append(("room", r.value))
        
        if not all_cards:
            return None
        
        card_type, card_name = random.choice(all_cards)
        return f"{card_name} is NOT the murder {card_type}"
    
    def move_suspect_to_room(self, suspect_name: str, room: Room) -> Optional[Player]:
        """
        Move a suspect token to a room (when they are named in a suggestion).
        Per official rules: suggested suspect is moved to the room.
        Returns the player if found, None otherwise.
        """
        for player in self.players:
            if player.character.value == suspect_name:
                player.current_room = room
                player.was_moved_by_suggestion = True
                player.has_moved_since_suggestion = True  # Can suggest immediately if moved by others
                player.entered_room_this_turn = True  # Treat as entering the room for suggestion eligibility
                player.in_hallway = False
                return player
        return None
    
    def make_suggestion(self, player: Player, suspect: str, weapon: str) -> Suggestion:
        """
        Make a suggestion. The room is always the player's current room.
        Per official rules:
        - Player must be in a room to make a suggestion
        - Player must have ENTERED the room this turn (not just stayed in it)
        - Suggestion must include the current room
        - Suggested suspect token is moved to the room
        - Players go clockwise to disprove, showing only ONE card
        - In American version, player can't suggest again from same room without leaving first
        
        Returns the suggestion with disproval info if applicable.
        """
        if player.current_room is None:
            raise ValueError("Player must be in a room to make a suggestion")
        
        # Player must have entered the room this turn to make a suggestion
        # Exception: If player was moved to room by another player's suggestion
        if not player.entered_room_this_turn and not player.was_moved_by_suggestion:
            raise ValueError("You must enter a room during your turn to make a suggestion. Roll the dice and move into a room first.")
        
        # American rules: Can't make repeated suggestions in same room without leaving
        # Exception: If player was moved to room by another player's suggestion
        if (not player.has_moved_since_suggestion and 
            not player.was_moved_by_suggestion and
            player.last_suggestion_room == player.current_room):
            raise ValueError("You must leave and re-enter this room before making another suggestion (American rules)")
        
        # Move the suggested suspect to the room (official rule)
        self.move_suspect_to_room(suspect, player.current_room)
        
        suggestion = Suggestion(
            suggester=player.name,
            suspect=suspect,
            weapon=weapon,
            room=player.current_room.value,
        )
        
        # Track suggestion for repeated suggestion rule
        player.last_suggestion_room = player.current_room
        player.has_moved_since_suggestion = False
        
        # Check if any other player can disprove (clockwise from suggester)
        player_index = self.players.index(player)
        for i in range(1, len(self.players)):
            check_index = (player_index + i) % len(self.players)
            other_player = self.players[check_index]
            
            # Even eliminated players must show cards to disprove (official rule)
            # Check if other player has any of the suggested cards
            matching_cards = []
            for card in other_player.cards:
                if card.name in [suspect, weapon, player.current_room.value]:
                    matching_cards.append(card)
            
            if matching_cards:
                # Player can disprove - they show ONE card (player's choice in real game)
                # For simplicity, we randomly choose one
                shown_card = random.choice(matching_cards)
                suggestion.disproven_by = other_player.name
                suggestion.card_shown = shown_card.name
                break
        
        self.suggestion_history.append(suggestion)
        player.knowledge["suggestions_made"].append(suggestion)
        
        return suggestion
    
    def make_accusation(self, player: Player, suspect: str, weapon: str, room: str) -> bool:
        """
        Make an accusation. Returns True if correct (player wins), False otherwise.
        If wrong, player is eliminated from making further accusations.
        Players can only make one accusation per turn.
        """
        if player.has_accused_this_turn:
            raise ValueError("You can only make one accusation per turn")
        
        player.has_accused_this_turn = True
        
        is_correct = (
            self.solution["suspect"].name == suspect and
            self.solution["weapon"].name == weapon and
            self.solution["room"].name == room
        )
        
        if is_correct:
            self.game_over = True
            self.winner = player.name
        else:
            player.is_active = False
            # Check if only one active player remains
            active_players = [p for p in self.players if p.is_active]
            if len(active_players) == 1:
                self.game_over = True
                self.winner = active_players[0].name
        
        return is_correct
    
    def get_player_by_name(self, name: str) -> Optional[Player]:
        """Get a player by their name."""
        for player in self.players:
            if player.name == name:
                return player
        return None
    
    def get_game_summary(self) -> str:
        """Get a summary of the current game state."""
        summary = f"=== Turn {self.turn_number} ===\n"
        summary += f"Current Player: {self.get_current_player().name}\n\n"
        
        for player in self.players:
            status = "Active" if player.is_active else "Eliminated"
            room = player.current_room.value if player.current_room else "Not in a room"
            summary += f"{player.name} ({player.character.value}): {status}, Location: {room}\n"
        
        if self.suggestion_history:
            summary += f"\nLast suggestion: {self.suggestion_history[-1].suggester} suggested "
            last = self.suggestion_history[-1]
            summary += f"{last.suspect} with {last.weapon} in {last.room}"
            if last.disproven_by:
                summary += f" (disproven by {last.disproven_by})"
            summary += "\n"
        
        return summary


# Global game state instance
_game_state: Optional[GameState] = None


def get_game_state() -> GameState:
    """Get or create the global game state."""
    global _game_state
    if _game_state is None:
        _game_state = GameState()
    return _game_state


def reset_game_state() -> GameState:
    """Reset the global game state."""
    global _game_state
    _game_state = GameState()
    return _game_state
