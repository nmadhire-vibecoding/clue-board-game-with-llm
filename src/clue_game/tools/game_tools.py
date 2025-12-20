"""
Custom CrewAI Tools for Clue Board Game
Tools for agents to interact with the game following official Cluedo/Clue rules.
"""

from crewai.tools import tool
from clue_game.game_state import (
    get_game_state, Room, Suspect, Weapon,
    ROOM_CONNECTIONS, SECRET_PASSAGES, STARTING_POSITIONS, ROOM_DOORS
)
from clue_game.notebook import get_notebook


@tool("Get My Cards")
def get_my_cards(player_name: str) -> str:
    """
    Get the cards in your hand. Use this to know what cards you have
    and what suspects/weapons/rooms you can eliminate from suspicion.
    
    Args:
        player_name: Your player name
    
    Returns:
        List of cards in your hand
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    cards_by_type = {"suspect": [], "weapon": [], "room": []}
    for card in player.cards:
        cards_by_type[card.card_type].append(card.name)
    
    result = f"Your cards ({len(player.cards)} total):\n"
    result += f"  Suspects: {', '.join(cards_by_type['suspect']) or 'None'}\n"
    result += f"  Weapons: {', '.join(cards_by_type['weapon']) or 'None'}\n"
    result += f"  Rooms: {', '.join(cards_by_type['room']) or 'None'}"
    
    return result


@tool("Get Current Location")
def get_current_location(player_name: str) -> str:
    """
    Get your current room location on the board.
    
    Args:
        player_name: Your player name
    
    Returns:
        Your current room location
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    if player.current_room:
        result = f"You are currently in the {player.current_room.value}"
        if player.was_moved_by_suggestion:
            result += "\n(You were moved here by another player's suggestion - you may suggest immediately without moving)"
        return result
    return "You are not in any room"


@tool("Roll Dice")
def roll_dice(player_name: str) -> str:
    """
    Roll two six-sided dice to determine movement.
    Per official rules, you roll dice to move along corridor spaces.
    In our simplified version, the dice result affects which rooms you can reach.
    
    SPECIAL: One face on each die shows a MAGNIFYING GLASS (🔍) instead of 1.
    Rolling a magnifying glass gives you a free clue about what is NOT the solution!
    
    Args:
        player_name: Your player name
    
    Returns:
        The dice roll result, any clues from magnifying glass, and movement options
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    die1, die2, magnifying_count = game_state.roll_dice()
    
    # Display dice values - show magnifying glass for 1s
    die1_display = "🔍" if die1 == 1 else str(die1)
    die2_display = "🔍" if die2 == 1 else str(die2)
    
    # Calculate movement total (magnifying glass = 0 for movement)
    move_die1 = 0 if die1 == 1 else die1
    move_die2 = 0 if die2 == 1 else die2
    total = move_die1 + move_die2
    
    result = f"🎲 DICE ROLL: {die1_display} + {die2_display} = {total} movement\n\n"
    
    # Handle magnifying glass clues
    if magnifying_count > 0:
        result += f"🔍 MAGNIFYING GLASS {'x2' if magnifying_count == 2 else ''}!\n"
        result += "You get a free clue about the mystery!\n\n"
        
        for _ in range(magnifying_count):
            clue = game_state.get_random_clue(player)
            if clue:
                result += f"  💡 CLUE: {clue}\n"
            else:
                result += f"  💡 CLUE: No additional clues available.\n"
        result += "\n  📝 TIP: Use your notebook to record this clue!\n\n"
    
    available = game_state.get_available_moves(player)
    room_names = [r.value for r in available]
    
    current = player.current_room.value if player.current_room else "starting position"
    
    result += f"From {current}, you can move to:\n"
    for room in room_names:
        if current in ["Kitchen", "Study", "Conservatory", "Lounge"]:
            secret = SECRET_PASSAGES.get(player.current_room)
            if secret and secret.value == room:
                result += f"  • {room} (via SECRET PASSAGE - instant!)\n"
            else:
                result += f"  • {room}\n"
        else:
            result += f"  • {room}\n"
    
    result += f"\n(In this simplified version, any adjacent room can be reached regardless of roll)"
    
    return result


@tool("Get Available Moves")
def get_available_moves(player_name: str) -> str:
    """
    Get the rooms you can move to from your current location.
    
    MOVEMENT RULES:
    - You can ONLY move to adjacent rooms through DOORS
    - Each room has specific doors that connect to hallways
    - You CANNOT move diagonally across the board
    - Secret passages exist between diagonal corner rooms:
      * Kitchen ↔ Study
      * Conservatory ↔ Lounge
    
    Args:
        player_name: Your player name
    
    Returns:
        List of rooms you can legally move to with door information
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    available = game_state.get_available_moves(player)
    
    current = player.current_room.value if player.current_room else "nowhere"
    current_room = player.current_room
    
    result = f"=== AVAILABLE MOVES from {current} ===\n\n"
    
    # Show door info for current room
    if current_room and current_room in ROOM_DOORS:
        doors = ROOM_DOORS[current_room]
        result += f"📍 {current} has {len(doors)} door(s):\n"
        for door_side, connects_to in doors:
            result += f"   • {door_side.upper()} door → hallway\n"
        result += "\n"
    
    result += "🚪 You can move to:\n"
    for room in available:
        room_name = room.value
        # Check if it's a secret passage
        if current_room and current_room in SECRET_PASSAGES and SECRET_PASSAGES[current_room] == room:
            result += f"  • {room_name} (via 🔑 SECRET PASSAGE - no dice needed!)\n"
        else:
            result += f"  • {room_name} (through hallway)\n"
    
    result += "\n⚠️ Remember: You can only move through doors! No diagonal shortcuts."
    
    return result


@tool("Move To Room")
def move_to_room(player_name: str, room_name: str) -> str:
    """
    Move to an adjacent room. You must move before making a suggestion.
    
    MOVEMENT RULES:
    - You can ONLY move to rooms connected by doorways
    - You CANNOT move diagonally across the board
    - Use "Get Available Moves" first to see valid options
    
    Args:
        player_name: Your player name
        room_name: The room to move to (e.g., "Kitchen", "Library")
    
    Returns:
        Confirmation of movement or error message
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    # Find the room enum
    target_room = None
    for room in Room:
        if room.value.lower() == room_name.lower():
            target_room = room
            break
    
    if not target_room:
        valid_rooms = [r.value for r in Room]
        return f"Error: Invalid room '{room_name}'. Valid rooms: {', '.join(valid_rooms)}"
    
    current_room = player.current_room.value if player.current_room else "starting position"
    
    if game_state.move_player(player, target_room):
        return f"✓ You moved from {current_room} to the {target_room.value}. You can now make a suggestion about this room."
    else:
        available = [r.value for r in game_state.get_available_moves(player)]
        return (f"❌ Cannot move to {target_room.value} from {current_room}.\n"
                f"Remember: You cannot move diagonally! Only through doorways or secret passages.\n"
                f"Available moves: {', '.join(available)}")


@tool("Make Suggestion")
def make_suggestion(player_name: str, suspect: str, weapon: str) -> str:
    """
    Make a suggestion about the murder. Per official Clue rules:
    - You can only suggest while in a room
    - The suggestion MUST include the room you're currently in
    - The suggested suspect token is moved to your room
    - Players clockwise from you try to disprove by showing ONE card
    - You cannot make repeated suggestions in the same room without leaving first
      (Exception: if you were moved to the room by another player's suggestion)
    
    IMPORTANT: Don't suggest cards that are already crossed out in your notebook!
    Suggesting known cards wastes your turn.
    
    Args:
        player_name: Your player name
        suspect: The suspect (e.g., "Miss Scarlet", "Colonel Mustard")
        weapon: The weapon (e.g., "Knife", "Candlestick")
    
    Returns:
        Result of the suggestion including if anyone disproved it
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    if not player.current_room:
        return "Error: You must be in a room to make a suggestion"
    
    # Validate suspect
    valid_suspect = None
    for s in Suspect:
        if s.value.lower() == suspect.lower():
            valid_suspect = s.value
            break
    
    if not valid_suspect:
        valid = [s.value for s in Suspect]
        return f"Error: Invalid suspect '{suspect}'. Valid suspects: {', '.join(valid)}"
    
    # Validate weapon
    valid_weapon = None
    for w in Weapon:
        if w.value.lower() == weapon.lower():
            valid_weapon = w.value
            break
    
    if not valid_weapon:
        valid = [w.value for w in Weapon]
        return f"Error: Invalid weapon '{weapon}'. Valid weapons: {', '.join(valid)}"
    
    current_room = player.current_room.value
    
    # Check the notebook to validate the suggestion is strategic
    notebook_warning = ""
    try:
        notebook = get_notebook(player_name)
        validation = notebook.validate_suggestion(valid_suspect, valid_weapon, current_room)
        
        if not validation["valid"]:
            # Warn the agent but allow the suggestion (unlike accusation which blocks)
            warning_msg = "\n".join(validation["warnings"])
            notebook_warning = f"\n⚠️ NOTEBOOK WARNING:\n{warning_msg}\n"
            
            # Suggest better alternatives
            if validation.get("better_suspects"):
                notebook_warning += f"\n📋 Better suspects to suggest: {', '.join(validation['better_suspects'][:3])}"
            if validation.get("better_weapons"):
                notebook_warning += f"\n📋 Better weapons to suggest: {', '.join(validation['better_weapons'][:3])}"
            notebook_warning += "\n"
    except Exception:
        # If notebook doesn't exist yet, proceed without warning
        pass
    
    try:
        suggestion = game_state.make_suggestion(player, valid_suspect, valid_weapon)
    except ValueError as e:
        return f"Error: {str(e)}"
    
    result = f"📣 SUGGESTION: {valid_suspect} with the {valid_weapon} in the {suggestion.room}\n"
    result += f"   (The {valid_suspect} token has been moved to the {suggestion.room})\n"
    
    # Add notebook warning if any
    if notebook_warning:
        result += notebook_warning
    
    result += "\n"
    
    if suggestion.disproven_by:
        result += f"❌ DISPROVEN by {suggestion.disproven_by} who showed you: {suggestion.card_shown}\n"
        result += f"   This means {suggestion.card_shown} is NOT part of the solution.\n"
        result += f"   📝 TIP: Record this in your notebook with 'Mark Player Has Card'!"
        # Update player knowledge
        if suggestion.card_shown not in player.knowledge["seen_cards"]:
            player.knowledge["seen_cards"].append(suggestion.card_shown)
    else:
        result += "✓ NO ONE could disprove this suggestion!\n"
        result += "  This is a VERY strong lead - consider making an accusation!"
    
    return result


@tool("Make Accusation")
def make_accusation(player_name: str, suspect: str, weapon: str, room: str) -> str:
    """
    Make a final accusation to solve the mystery. 
    
    IMPORTANT RULES:
    - Unlike suggestions, accusations can include ANY room (not just your current room)
    - You secretly check the solution envelope
    - If CORRECT: You win the game!
    - If WRONG: You are eliminated but must still show cards to disprove others' suggestions
    - Your notebook will be checked - DO NOT accuse items that are crossed out!
    
    ⚠️ BE CAREFUL - if you're wrong, you're eliminated from winning!
    Only accuse when you're confident you know the solution.
    Use "Get Possible Solution" first to check your notebook!
    
    Args:
        player_name: Your player name
        suspect: The suspect you're accusing
        weapon: The murder weapon
        room: The room where the murder happened (can be ANY room)
    
    Returns:
        Whether you won or were eliminated
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    if not player.is_active:
        return "Error: You have been eliminated and cannot make accusations (but you must still show cards to disprove suggestions)"
    
    # Validate inputs
    valid_suspect = None
    for s in Suspect:
        if s.value.lower() == suspect.lower():
            valid_suspect = s.value
            break
    
    valid_weapon = None
    for w in Weapon:
        if w.value.lower() == weapon.lower():
            valid_weapon = w.value
            break
    
    valid_room = None
    for r in Room:
        if r.value.lower() == room.lower():
            valid_room = r.value
            break
    
    if not all([valid_suspect, valid_weapon, valid_room]):
        return "Error: Invalid suspect, weapon, or room name"
    
    # Check the notebook to validate the accusation
    try:
        notebook = get_notebook(player_name)
        validation = notebook.validate_accusation(valid_suspect, valid_weapon, valid_room)
        
        if not validation["valid"]:
            # Block the accusation - notebook shows it's wrong!
            warning_msg = "\n".join(validation["warnings"])
            result = f"🛑 ACCUSATION BLOCKED!\n\n"
            result += f"Your notebook shows this accusation cannot be correct:\n{warning_msg}\n\n"
            
            # Show recommendation if available
            rec = validation["recommendation"]
            if rec["can_accuse"]:
                result += f"📋 Your notebook suggests: {rec['suspect']} with {rec['weapon']} in {rec['room']}\n"
            else:
                result += f"📋 You need more information before accusing.\n"
                result += f"   Reason: {rec['reason']}\n"
            
            return result
    except Exception:
        # If notebook doesn't exist yet, allow the accusation (agent hasn't initialized notebook)
        pass
    
    try:
        is_correct = game_state.make_accusation(player, valid_suspect, valid_weapon, valid_room)
    except ValueError as e:
        return f"⚠️ {str(e)}"
    
    if is_correct:
        return f"🎉 CORRECT! {player_name} WINS! The solution was {valid_suspect} with the {valid_weapon} in the {valid_room}!"
    else:
        return f"❌ WRONG! {player_name} is eliminated. The accusation of {valid_suspect} with the {valid_weapon} in the {valid_room} was incorrect."


@tool("Get Game Status")
def get_game_status() -> str:
    """
    Get the current game status including all players, their locations, and recent suggestions.
    
    Returns:
        Current game state summary
    """
    game_state = get_game_state()
    return game_state.get_game_summary()


@tool("Get Suggestion History")
def get_suggestion_history() -> str:
    """
    Get the history of all suggestions made in the game.
    This helps track what has been suggested and disproven.
    
    Returns:
        List of all suggestions and their outcomes
    """
    game_state = get_game_state()
    
    if not game_state.suggestion_history:
        return "No suggestions have been made yet."
    
    result = "=== Suggestion History ===\n"
    for i, sugg in enumerate(game_state.suggestion_history, 1):
        result += f"\n{i}. {sugg.suggester} suggested: {sugg.suspect} with {sugg.weapon} in {sugg.room}"
        if sugg.disproven_by:
            result += f"\n   Disproven by: {sugg.disproven_by}"
        else:
            result += "\n   NOT DISPROVEN"
    
    return result


@tool("Get My Knowledge")
def get_my_knowledge(player_name: str) -> str:
    """
    Get a summary of what you know from your cards and suggestions.
    
    Args:
        player_name: Your player name
    
    Returns:
        Summary of your deductions
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    result = "=== Your Knowledge ===\n\n"
    
    # Cards you hold (definitely not the solution)
    result += "Cards in your hand (NOT the solution):\n"
    for card in player.cards:
        result += f"  - {card.name} ({card.card_type})\n"
    
    # Cards shown to you (also not the solution)
    if player.knowledge["seen_cards"]:
        result += "\nCards shown to you by others (NOT the solution):\n"
        for card_name in player.knowledge["seen_cards"]:
            result += f"  - {card_name}\n"
    
    # All suspects, weapons, rooms for reference
    result += "\n--- All Possibilities ---\n"
    
    eliminated = set([c.name for c in player.cards] + player.knowledge["seen_cards"])
    
    result += "\nSuspects: "
    for s in Suspect:
        if s.value in eliminated:
            result += f"[{s.value}] "
        else:
            result += f"{s.value}, "
    
    result += "\n\nWeapons: "
    for w in Weapon:
        if w.value in eliminated:
            result += f"[{w.value}] "
        else:
            result += f"{w.value}, "
    
    result += "\n\nRooms: "
    for r in Room:
        if r.value in eliminated:
            result += f"[{r.value}] "
        else:
            result += f"{r.value}, "
    
    result += "\n\n(Items in [brackets] have been eliminated)"
    
    return result


@tool("Get Valid Options")
def get_valid_options() -> str:
    """
    Get all valid suspect, weapon, and room names for making suggestions or accusations.
    
    Returns:
        Lists of all valid options
    """
    suspects = [s.value for s in Suspect]
    weapons = [w.value for w in Weapon]
    rooms = [r.value for r in Room]
    
    return f"""Valid Options:

SUSPECTS: {', '.join(suspects)}

WEAPONS: {', '.join(weapons)}

ROOMS: {', '.join(rooms)}
"""
