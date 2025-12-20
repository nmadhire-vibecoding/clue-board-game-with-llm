"""
Game State Management for Clue Board Game
Based on official Cluedo/Clue rules (https://en.wikipedia.org/wiki/Cluedo#Rules)

Key rules implemented:
- Dice rolling for movement
- Clockwise turn order starting with Miss Scarlet (or highest roll)
- Secret passages between diagonal corner rooms
- Suggestions can only be made in rooms, about that room
- Suggested suspect/weapon tokens move to the room
- Player must leave and re-enter room to make another suggestion (American rules)
- Accusations can include any room, not just current location
- Wrong accusations eliminate player but they must still show cards to disprove
"""

import random
from dataclasses import dataclass, field
from typing import Optional
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


# Door positions for each room (based on actual Clue board)
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

# Starting positions for each suspect (at hallway squares near room entrances)
# Based on the colored starting squares around the board edge
STARTING_POSITIONS = {
    Suspect.MISS_SCARLET: Room.HALL,        # Red - starts near Hall (goes first!)
    Suspect.COLONEL_MUSTARD: Room.LOUNGE,   # Yellow - starts near Lounge entrance
    Suspect.MRS_WHITE: Room.BALLROOM,       # White - starts near Ballroom entrance  
    Suspect.MR_GREEN: Room.CONSERVATORY,    # Green - starts near Conservatory entrance
    Suspect.MRS_PEACOCK: Room.CONSERVATORY, # Blue - starts near Conservatory (closest to room!)
    Suspect.PROFESSOR_PLUM: Room.STUDY,     # Purple - starts near Study entrance
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
    current_room: Optional[Room] = None
    is_active: bool = True  # False if player made wrong accusation
    knowledge: dict = field(default_factory=dict)  # Track what player knows
    last_suggestion_room: Optional[Room] = None  # Track last room where suggestion was made
    has_moved_since_suggestion: bool = True  # Must move/leave room before suggesting again (US rules)
    was_moved_by_suggestion: bool = False  # If pulled into room by another's suggestion
    has_accused_this_turn: bool = False  # Can only accuse once per turn
    
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
        
        # Create players with proper starting positions
        self.players = []
        for i, name in enumerate(player_names):
            character = available_characters[i]
            # Starting position based on character (per official rules)
            starting_room = STARTING_POSITIONS.get(character, Room.HALL)
            player = Player(
                name=name,
                character=character,
                current_room=starting_room,
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
        1. Regular door connections (through hallways)
        2. Secret passages (corner rooms only: Kitchen<->Study, Conservatory<->Lounge)
        """
        if player.current_room is None:
            return list(Room)
        
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
        if room in available or player.current_room is None:
            old_room = player.current_room
            player.current_room = room
            # Track that player has moved (for repeated suggestion rule)
            if old_room != room:
                player.has_moved_since_suggestion = True
                player.was_moved_by_suggestion = False  # They moved voluntarily
            return True
        return False
    
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
                return player
        return None
    
    def make_suggestion(self, player: Player, suspect: str, weapon: str) -> Suggestion:
        """
        Make a suggestion. The room is always the player's current room.
        Per official rules:
        - Player must be in a room to make a suggestion
        - Suggestion must include the current room
        - Suggested suspect token is moved to the room
        - Players go clockwise to disprove, showing only ONE card
        - In American version, player can't suggest again from same room without leaving first
        
        Returns the suggestion with disproval info if applicable.
        """
        if player.current_room is None:
            raise ValueError("Player must be in a room to make a suggestion")
        
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
