"""
Detective Notebook - Deterministic tracking for Clue game deductions.

This is the CRUCIAL tool that prevents LLM hallucination by maintaining
a hard-coded grid of card ownership. The LLM queries this tool instead
of trying to remember card locations from conversation history.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CardStatus(Enum):
    """Status of a card in relation to a player/envelope."""
    UNKNOWN = "?"      # Don't know if they have it
    HAS = "✓"          # Confirmed they have this card
    NOT_HAS = "✗"      # Confirmed they don't have this card


@dataclass
class NotebookEntry:
    """An entry tracking one card's status across all players."""
    card_name: str
    card_type: str  # 'suspect', 'weapon', 'room'
    # Maps player name -> CardStatus
    player_status: dict[str, CardStatus] = field(default_factory=dict)
    envelope_status: CardStatus = CardStatus.UNKNOWN
    
    def is_solved(self) -> bool:
        """Returns True if we know where this card is."""
        if self.envelope_status == CardStatus.HAS:
            return True
        return any(s == CardStatus.HAS for s in self.player_status.values())
    
    def get_owner(self) -> Optional[str]:
        """Get who owns this card, if known."""
        if self.envelope_status == CardStatus.HAS:
            return "ENVELOPE"
        for player, status in self.player_status.items():
            if status == CardStatus.HAS:
                return player
        return None


class DetectiveNotebook:
    """
    A deterministic notebook that tracks card ownership.
    
    This is the key tool for effective Clue AI - instead of relying on
    the LLM's context memory (which degrades), we maintain a hard-coded
    grid that the LLM queries for accurate information.
    
    Grid structure:
    - Rows: All cards (6 suspects, 6 weapons, 9 rooms = 21 cards)
    - Columns: Each player + "Envelope" (the solution)
    """
    
    def __init__(self, owner_name: str, all_player_names: list[str]):
        """
        Initialize notebook for a specific player.
        
        Args:
            owner_name: The player who owns this notebook
            all_player_names: List of all player names in the game
        """
        self.owner_name = owner_name
        self.all_players = all_player_names
        self.entries: dict[str, NotebookEntry] = {}
        self.suggestion_log: list[dict] = []
        self.turn_log: list[str] = []  # Log of all events
        
        # Initialize all cards
        self._init_cards()
    
    def _init_cards(self):
        """Initialize all card entries."""
        suspects = [
            "Miss Scarlet", "Colonel Mustard", "Mrs. White",
            "Mr. Green", "Mrs. Peacock", "Professor Plum"
        ]
        weapons = [
            "Candlestick", "Knife", "Lead Pipe",
            "Revolver", "Rope", "Wrench"
        ]
        rooms = [
            "Kitchen", "Ballroom", "Conservatory", "Billiard Room",
            "Library", "Study", "Hall", "Lounge", "Dining Room"
        ]
        
        for card in suspects:
            self._add_card(card, "suspect")
        for card in weapons:
            self._add_card(card, "weapon")
        for card in rooms:
            self._add_card(card, "room")
    
    def _add_card(self, card_name: str, card_type: str):
        """Add a card entry to the notebook."""
        entry = NotebookEntry(
            card_name=card_name,
            card_type=card_type,
            player_status={p: CardStatus.UNKNOWN for p in self.all_players}
        )
        self.entries[card_name] = entry
    
    def mark_card(self, card_name: str, player_name: str) -> str:
        """
        Mark that a player HAS a specific card.
        Also marks all other players as NOT having this card.
        
        Args:
            card_name: The card name (e.g., "Candlestick", "Miss Scarlet")
            player_name: The player who has this card
        
        Returns:
            Confirmation message
        """
        if card_name not in self.entries:
            return f"Error: Unknown card '{card_name}'"
        
        entry = self.entries[card_name]
        
        # Mark this player as having the card
        if player_name in entry.player_status:
            entry.player_status[player_name] = CardStatus.HAS
        elif player_name.upper() == "ENVELOPE":
            entry.envelope_status = CardStatus.HAS
        else:
            return f"Error: Unknown player '{player_name}'"
        
        # Mark all OTHER players as NOT having this card
        for other_player in self.all_players:
            if other_player != player_name:
                entry.player_status[other_player] = CardStatus.NOT_HAS
        
        # If a player has it, it's not in the envelope
        if player_name != "ENVELOPE":
            entry.envelope_status = CardStatus.NOT_HAS
        
        self._log(f"MARKED: {player_name} HAS '{card_name}'")
        self._check_deductions()
        
        return f"✓ Marked: {player_name} has '{card_name}'"
    
    def mark_not_has(self, card_name: str, player_name: str) -> str:
        """
        Mark that a player does NOT have a specific card.
        
        Args:
            card_name: The card name
            player_name: The player who doesn't have this card
        
        Returns:
            Confirmation message
        """
        if card_name not in self.entries:
            return f"Error: Unknown card '{card_name}'"
        
        entry = self.entries[card_name]
        
        if player_name in entry.player_status:
            entry.player_status[player_name] = CardStatus.NOT_HAS
        else:
            return f"Error: Unknown player '{player_name}'"
        
        self._log(f"MARKED: {player_name} does NOT have '{card_name}'")
        self._check_deductions()
        
        return f"✗ Marked: {player_name} does NOT have '{card_name}'"
    
    def record_my_cards(self, my_cards: list[str]) -> str:
        """
        Record the cards in my own hand at game start.
        
        Args:
            my_cards: List of card names I was dealt
        
        Returns:
            Confirmation message
        """
        results = []
        for card in my_cards:
            result = self.mark_card(card, self.owner_name)
            results.append(result)
        
        self._log(f"GAME START: Recorded {len(my_cards)} cards in my hand")
        return f"Recorded {len(my_cards)} cards in your hand:\n" + "\n".join(results)
    
    def record_suggestion(
        self,
        turn_number: int,
        suggester: str,
        suspect: str,
        weapon: str,
        room: str,
        disprover: Optional[str] = None,
        card_shown: Optional[str] = None,
        players_who_passed: list[str] = None
    ) -> str:
        """
        Record a suggestion and update the notebook accordingly.
        
        Args:
            turn_number: The turn number
            suggester: Who made the suggestion
            suspect: Suggested suspect
            weapon: Suggested weapon
            room: Suggested room (where suggestion was made)
            disprover: Who disproved it (if any)
            card_shown: The card shown (only if shown to me)
            players_who_passed: Players who couldn't disprove
        
        Returns:
            Summary of deductions made
        """
        suggestion_record = {
            "turn": turn_number,
            "suggester": suggester,
            "suspect": suspect,
            "weapon": weapon,
            "room": room,
            "disprover": disprover,
            "card_shown": card_shown,
            "players_passed": players_who_passed or []
        }
        self.suggestion_log.append(suggestion_record)
        
        deductions = []
        
        # If someone showed ME a card, mark it
        if card_shown and disprover:
            self.mark_card(card_shown, disprover)
            deductions.append(f"✓ {disprover} has '{card_shown}'")
        
        # Players who passed don't have ANY of the suggested cards
        if players_who_passed:
            for player in players_who_passed:
                for card in [suspect, weapon, room]:
                    if self.entries[card].player_status.get(player) == CardStatus.UNKNOWN:
                        self.mark_not_has(card, player)
                        deductions.append(f"✗ {player} doesn't have '{card}' (passed)")
        
        self._log(f"SUGGESTION #{len(self.suggestion_log)}: {suggester} suggested {suspect}/{weapon}/{room}")
        if disprover:
            self._log(f"  -> Disproved by {disprover}" + (f" with '{card_shown}'" if card_shown else ""))
        else:
            self._log(f"  -> NOT DISPROVED! Strong lead!")
        
        self._check_deductions()
        
        result = f"Recorded suggestion #{len(self.suggestion_log)}\n"
        if deductions:
            result += "Deductions made:\n" + "\n".join(deductions)
        else:
            result += "No new deductions from this suggestion."
        
        return result
    
    def _check_deductions(self):
        """
        Run deduction logic to infer new information.
        Called after any update to check for new conclusions.
        """
        changed = True
        while changed:
            changed = False
            
            for card_name, entry in self.entries.items():
                # Deduction 1: If all players marked NOT_HAS, card is in ENVELOPE
                if entry.envelope_status == CardStatus.UNKNOWN:
                    all_not_has = all(
                        s == CardStatus.NOT_HAS 
                        for s in entry.player_status.values()
                    )
                    if all_not_has:
                        entry.envelope_status = CardStatus.HAS
                        self._log(f"DEDUCED: '{card_name}' is in the ENVELOPE!")
                        changed = True
                
                # Deduction 2: If envelope has card, no player has it
                if entry.envelope_status == CardStatus.HAS:
                    for player in self.all_players:
                        if entry.player_status[player] != CardStatus.NOT_HAS:
                            entry.player_status[player] = CardStatus.NOT_HAS
                            changed = True
    
    def get_unknown_cards(self) -> str:
        """
        Get all cards whose location is still unknown.
        Use this when deciding what to suggest.
        
        Returns:
            List of unknown cards grouped by type
        """
        unknown = {"suspect": [], "weapon": [], "room": []}
        
        for card_name, entry in self.entries.items():
            if not entry.is_solved():
                unknown[entry.card_type].append(card_name)
        
        result = "=== UNKNOWN CARDS ===\n\n"
        result += f"Suspects ({len(unknown['suspect'])} unknown):\n"
        result += "  " + ", ".join(unknown['suspect']) if unknown['suspect'] else "  All suspects accounted for!"
        result += f"\n\nWeapons ({len(unknown['weapon'])} unknown):\n"
        result += "  " + ", ".join(unknown['weapon']) if unknown['weapon'] else "  All weapons accounted for!"
        result += f"\n\nRooms ({len(unknown['room'])} unknown):\n"
        result += "  " + ", ".join(unknown['room']) if unknown['room'] else "  All rooms accounted for!"
        
        return result
    
    def get_possible_solution(self) -> str:
        """
        Get the cards that could possibly be in the envelope (the solution).
        
        Returns:
            Possible solution cards and confidence level
        """
        possible = {"suspect": [], "weapon": [], "room": []}
        confirmed = {"suspect": None, "weapon": None, "room": None}
        
        for card_name, entry in self.entries.items():
            # If confirmed in envelope
            if entry.envelope_status == CardStatus.HAS:
                confirmed[entry.card_type] = card_name
            # If not confirmed held by anyone, it COULD be in envelope
            elif entry.envelope_status != CardStatus.NOT_HAS:
                if not any(s == CardStatus.HAS for s in entry.player_status.values()):
                    possible[entry.card_type].append(card_name)
        
        result = "=== POSSIBLE SOLUTION ===\n\n"
        
        # Suspect
        if confirmed["suspect"]:
            result += f"SUSPECT: *** {confirmed['suspect']} *** (CONFIRMED!)\n"
        elif len(possible["suspect"]) == 1:
            result += f"SUSPECT: {possible['suspect'][0]} (only possibility!)\n"
        else:
            result += f"SUSPECT: {len(possible['suspect'])} possibilities - {', '.join(possible['suspect'])}\n"
        
        # Weapon
        if confirmed["weapon"]:
            result += f"WEAPON: *** {confirmed['weapon']} *** (CONFIRMED!)\n"
        elif len(possible["weapon"]) == 1:
            result += f"WEAPON: {possible['weapon'][0]} (only possibility!)\n"
        else:
            result += f"WEAPON: {len(possible['weapon'])} possibilities - {', '.join(possible['weapon'])}\n"
        
        # Room
        if confirmed["room"]:
            result += f"ROOM: *** {confirmed['room']} *** (CONFIRMED!)\n"
        elif len(possible["room"]) == 1:
            result += f"ROOM: {possible['room'][0]} (only possibility!)\n"
        else:
            result += f"ROOM: {len(possible['room'])} possibilities - {', '.join(possible['room'])}\n"
        
        # Check if we can make an accusation
        can_accuse = (
            (confirmed["suspect"] or len(possible["suspect"]) == 1) and
            (confirmed["weapon"] or len(possible["weapon"]) == 1) and
            (confirmed["room"] or len(possible["room"]) == 1)
        )
        
        if can_accuse:
            result += "\n🎯 YOU CAN MAKE AN ACCUSATION! All three are narrowed to one option!"
            final_suspect = confirmed["suspect"] or possible["suspect"][0]
            final_weapon = confirmed["weapon"] or possible["weapon"][0]
            final_room = confirmed["room"] or possible["room"][0]
            result += f"\n   -> Accuse: {final_suspect} with {final_weapon} in {final_room}"
        
        return result
    
    def get_accusation_recommendation(self) -> dict:
        """
        Get the recommended accusation based on notebook deductions.
        
        Returns:
            Dict with 'can_accuse', 'suspect', 'weapon', 'room', and 'reason'
        """
        possible = {"suspect": [], "weapon": [], "room": []}
        confirmed = {"suspect": None, "weapon": None, "room": None}
        
        for card_name, entry in self.entries.items():
            # If confirmed in envelope
            if entry.envelope_status == CardStatus.HAS:
                confirmed[entry.card_type] = card_name
            # If not confirmed held by anyone, it COULD be in envelope
            elif entry.envelope_status != CardStatus.NOT_HAS:
                if not any(s == CardStatus.HAS for s in entry.player_status.values()):
                    possible[entry.card_type].append(card_name)
        
        # Check if we can make an accusation
        can_accuse = (
            (confirmed["suspect"] or len(possible["suspect"]) == 1) and
            (confirmed["weapon"] or len(possible["weapon"]) == 1) and
            (confirmed["room"] or len(possible["room"]) == 1)
        )
        
        if can_accuse:
            return {
                "can_accuse": True,
                "suspect": confirmed["suspect"] or possible["suspect"][0],
                "weapon": confirmed["weapon"] or possible["weapon"][0],
                "room": confirmed["room"] or possible["room"][0],
                "reason": "All three categories narrowed to one option"
            }
        else:
            reasons = []
            if not confirmed["suspect"] and len(possible["suspect"]) != 1:
                reasons.append(f"{len(possible['suspect'])} suspect possibilities remain")
            if not confirmed["weapon"] and len(possible["weapon"]) != 1:
                reasons.append(f"{len(possible['weapon'])} weapon possibilities remain")
            if not confirmed["room"] and len(possible["room"]) != 1:
                reasons.append(f"{len(possible['room'])} room possibilities remain")
            
            return {
                "can_accuse": False,
                "suspect": None,
                "weapon": None,
                "room": None,
                "possible_suspects": possible["suspect"],
                "possible_weapons": possible["weapon"],
                "possible_rooms": possible["room"],
                "reason": "; ".join(reasons) if reasons else "Need more information"
            }
    
    def validate_accusation(self, suspect: str, weapon: str, room: str) -> dict:
        """
        Validate if an accusation makes sense based on notebook knowledge.
        
        Args:
            suspect: The suspect to accuse
            weapon: The weapon to accuse
            room: The room to accuse
            
        Returns:
            Dict with 'valid', 'warnings', and 'recommendation'
        """
        warnings = []
        
        # Check each card against notebook knowledge
        for card_name, card_type in [(suspect, "suspect"), (weapon, "weapon"), (room, "room")]:
            if card_name in self.entries:
                entry = self.entries[card_name]
                
                # If someone has this card, it's definitely NOT the solution
                if any(s == CardStatus.HAS for s in entry.player_status.values()):
                    owner = entry.get_owner()
                    warnings.append(f"❌ {card_name} is held by {owner} - CANNOT be in envelope!")
                
                # If envelope is marked as NOT having it
                if entry.envelope_status == CardStatus.NOT_HAS:
                    warnings.append(f"❌ {card_name} is marked as NOT in envelope!")
        
        recommendation = self.get_accusation_recommendation()
        
        if warnings:
            return {
                "valid": False,
                "warnings": warnings,
                "recommendation": recommendation,
                "message": "Your notebook shows this accusation is WRONG!"
            }
        else:
            return {
                "valid": True,
                "warnings": [],
                "recommendation": recommendation,
                "message": "Accusation is consistent with your notebook knowledge"
            }
    
    def validate_suggestion(self, suspect: str, weapon: str, room: str) -> dict:
        """
        Validate if a suggestion makes strategic sense based on notebook knowledge.
        Suggesting cards that are already known (crossed out) wastes a turn!
        
        Args:
            suspect: The suspect to suggest
            weapon: The weapon to suggest
            room: The room (your current room)
            
        Returns:
            Dict with 'valid', 'warnings', 'wasted_cards', and 'better_alternatives'
        """
        warnings = []
        wasted_cards = []
        alternatives = {"suspect": [], "weapon": [], "room": []}
        
        # Check each card against notebook knowledge
        for card_name, card_type in [(suspect, "suspect"), (weapon, "weapon"), (room, "room")]:
            if card_name in self.entries:
                entry = self.entries[card_name]
                
                # If someone has this card, suggesting it is wasteful
                if any(s == CardStatus.HAS for s in entry.player_status.values()):
                    owner = entry.get_owner()
                    wasted_cards.append(card_name)
                    warnings.append(f"⚠️ {card_name} is already known to be held by {owner} - suggesting it won't give you new info!")
                
                # If envelope is confirmed to NOT have it, also wasteful
                elif entry.envelope_status == CardStatus.NOT_HAS:
                    wasted_cards.append(card_name)
                    warnings.append(f"⚠️ {card_name} is already eliminated from the solution!")
        
        # Find better alternatives (cards still unknown)
        for card_name, entry in self.entries.items():
            if not entry.is_solved() and entry.envelope_status != CardStatus.NOT_HAS:
                if not any(s == CardStatus.HAS for s in entry.player_status.values()):
                    alternatives[entry.card_type].append(card_name)
        
        if warnings:
            return {
                "valid": False,
                "warnings": warnings,
                "wasted_cards": wasted_cards,
                "better_suspects": alternatives["suspect"],
                "better_weapons": alternatives["weapon"],
                "message": "This suggestion includes cards you already know about!"
            }
        else:
            return {
                "valid": True,
                "warnings": [],
                "wasted_cards": [],
                "message": "Good suggestion - all cards are still unknown"
            }

    def get_notebook_grid(self) -> str:
        """
        Get the full notebook grid showing all deductions.
        
        Returns:
            Formatted grid of all card statuses
        """
        result = "=== DETECTIVE NOTEBOOK GRID ===\n"
        result += f"(Owner: {self.owner_name})\n\n"
        
        # Header
        header = "Card".ljust(20)
        for player in self.all_players:
            header += player[:8].center(10)
        header += "ENVELOPE".center(10)
        result += header + "\n"
        result += "=" * len(header) + "\n"
        
        # Group by type
        for card_type in ["suspect", "weapon", "room"]:
            result += f"\n--- {card_type.upper()}S ---\n"
            for card_name, entry in self.entries.items():
                if entry.card_type == card_type:
                    row = card_name.ljust(20)
                    for player in self.all_players:
                        status = entry.player_status[player]
                        row += status.value.center(10)
                    row += entry.envelope_status.value.center(10)
                    result += row + "\n"
        
        result += "\nLegend: ✓=Has  ✗=Doesn't have  ?=Unknown\n"
        
        return result
    
    def get_suggestion_history(self) -> str:
        """
        Get the history of all suggestions.
        
        Returns:
            Formatted suggestion history
        """
        if not self.suggestion_log:
            return "No suggestions have been recorded yet."
        
        result = "=== SUGGESTION HISTORY ===\n\n"
        for i, sugg in enumerate(self.suggestion_log, 1):
            result += f"Turn {sugg['turn']}: {sugg['suggester']} suggested:\n"
            result += f"  {sugg['suspect']} with {sugg['weapon']} in {sugg['room']}\n"
            if sugg['disprover']:
                result += f"  -> Disproved by {sugg['disprover']}"
                if sugg['card_shown']:
                    result += f" (showed: {sugg['card_shown']})"
                result += "\n"
            else:
                result += "  -> NOT DISPROVED!\n"
            if sugg['players_passed']:
                result += f"  -> Passed: {', '.join(sugg['players_passed'])}\n"
            result += "\n"
        
        return result
    
    def get_turn_log(self) -> str:
        """
        Get the full log of all events.
        
        Returns:
            Complete event log
        """
        if not self.turn_log:
            return "No events logged yet."
        
        result = "=== EVENT LOG ===\n\n"
        for i, event in enumerate(self.turn_log, 1):
            result += f"{i}. {event}\n"
        
        return result
    
    def _log(self, message: str):
        """Add an event to the log."""
        self.turn_log.append(message)
    
    def get_strategic_suggestion(self, current_room: str) -> str:
        """
        Get a strategic suggestion based on current knowledge.
        Suggests cards that are still unknown to gather information.
        
        Args:
            current_room: The room you're currently in
        
        Returns:
            Recommended suggestion
        """
        unknown = {"suspect": [], "weapon": []}
        
        for card_name, entry in self.entries.items():
            if entry.card_type in ["suspect", "weapon"] and not entry.is_solved():
                unknown[entry.card_type].append(card_name)
        
        result = f"=== STRATEGIC SUGGESTION for {current_room} ===\n\n"
        
        if not unknown["suspect"]:
            result += "⚠️ All suspects are accounted for!\n"
        else:
            result += f"Unknown suspects to test: {', '.join(unknown['suspect'])}\n"
            result += f"Recommend: {unknown['suspect'][0]}\n"
        
        if not unknown["weapon"]:
            result += "⚠️ All weapons are accounted for!\n"
        else:
            result += f"Unknown weapons to test: {', '.join(unknown['weapon'])}\n"
            result += f"Recommend: {unknown['weapon'][0]}\n"
        
        if unknown["suspect"] and unknown["weapon"]:
            result += f"\n🎯 Suggested: '{unknown['suspect'][0]}' with '{unknown['weapon'][0]}' in '{current_room}'"
        
        return result


# Global storage for player notebooks
_player_notebooks: dict[str, DetectiveNotebook] = {}


def get_notebook(player_name: str, all_players: list[str] = None) -> DetectiveNotebook:
    """Get or create a player's notebook."""
    global _player_notebooks
    if player_name not in _player_notebooks:
        if all_players is None:
            all_players = ["Scarlet", "Mustard", "Green", "Peacock", "Plum", "White"]
        _player_notebooks[player_name] = DetectiveNotebook(player_name, all_players)
    return _player_notebooks[player_name]


def reset_notebook(player_name: str):
    """Reset a specific player's notebook."""
    global _player_notebooks
    if player_name in _player_notebooks:
        del _player_notebooks[player_name]


def reset_all_notebooks():
    """Reset all notebooks for a new game."""
    global _player_notebooks
    _player_notebooks = {}


def update_all_notebooks_card_shown(card_name: str, card_holder: str) -> None:
    """
    Update all player notebooks when a card is revealed.
    
    This is called when:
    - A suggestion is disproved and a card is shown
    - A magnifying glass clue reveals who holds a card
    
    All players will mark that the card holder has this card,
    which means it's not in the solution envelope.
    
    Args:
        card_name: The name of the card that was shown
        card_holder: The name of the player who holds this card
    """
    global _player_notebooks
    for player_name, notebook in _player_notebooks.items():
        try:
            notebook.mark_card(card_name, card_holder)
        except Exception:
            # If notebook doesn't have this card tracked yet, skip
            pass
