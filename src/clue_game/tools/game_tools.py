"""
Custom CrewAI Tools for Clue Board Game
Tools for agents to interact with the game following official Cluedo/Clue rules.

Movement Rules:
- Roll dice and move that many squares (horizontal/vertical only)
- Cannot pass through or land on occupied hallway squares
- Movement stops upon entering a room
- Cannot visit same square twice in one turn
"""

import sys
from crewai.tools import tool
from clue_game.game_state import (
    get_game_state, Room, Suspect, Weapon,
    ROOM_CONNECTIONS, SECRET_PASSAGES, STARTING_POSITIONS, ROOM_DOORS,
    STARTING_POSITION_NAMES, STARTING_POSITION_MOVES, STARTING_GRID_POSITIONS,
    DOOR_POSITIONS, get_cell_type, CellType, BOARD_WIDTH, BOARD_HEIGHT
)
from clue_game.notebook import get_notebook, update_all_notebooks_card_shown


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
    Get your current location on the board.
    
    Args:
        player_name: Your player name
    
    Returns:
        Your current room or grid position in the hallway
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    if player.current_room and not player.in_hallway:
        result = f"📍 You are currently in the {player.current_room.value}\n"
        result += f"   Moves remaining: {player.moves_remaining}\n"
        if player.was_moved_by_suggestion:
            result += "\n(You were moved here by another player's suggestion - you may suggest immediately without moving)"
        
        # Show exits
        doors = game_state.get_room_doors(player.current_room)
        if doors:
            result += f"\n🚪 Room exits: {len(doors)} door(s)"
        if player.current_room in SECRET_PASSAGES:
            dest = SECRET_PASSAGES[player.current_room]
            result += f"\n🔑 Secret passage to: {dest.value}"
        return result
    else:
        # Player is in hallway
        if player.position:
            result = f"📍 You are in the hallway at position ({player.position[0]}, {player.position[1]})\n"
        else:
            start_name = STARTING_POSITION_NAMES.get(player.character, "hallway")
            result = f"📍 You are at your START position: {start_name}\n"
        
        result += f"   Moves remaining: {player.moves_remaining}\n"
        result += f"\nYou must enter a room to make a suggestion."
        
        # Show nearby rooms if they have moves
        if player.moves_remaining > 0:
            reachable = game_state.get_reachable_rooms(player)
            if reachable:
                result += f"\n\n🚪 Rooms within reach:"
                for room, distance, _ in reachable:
                    result += f"\n   • {room.value} ({distance} steps)"
        
        return result


@tool("Roll Dice")
def roll_dice(player_name: str) -> str:
    """
    Roll two six-sided dice to determine movement.
    You MUST move the exact number of spaces rolled (horizontal/vertical only).
    
    MOVEMENT RULES:
    - Move horizontally or vertically, never diagonally
    - Cannot pass through or land on occupied hallway squares
    - Movement STOPS when you enter a room (even if moves remain)
    - Cannot visit the same square twice in one turn
    
    SPECIAL: One face on each die shows a MAGNIFYING GLASS (🔍) instead of 1.
    Rolling a magnifying glass counts as 1 for movement AND gives you a free clue!
    
    Args:
        player_name: Your player name
    
    Returns:
        The dice roll result, movement allowance, and reachable rooms
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    die1, die2, magnifying_count = game_state.roll_dice()
    
    # Display dice values - show magnifying glass for 1s
    die1_display = "🔍" if die1 == 1 else str(die1)
    die2_display = "🔍" if die2 == 1 else str(die2)
    
    # Calculate movement total (magnifying glass = 1 for movement)
    total = die1 + die2
    
    # Start the turn with the dice total
    game_state.start_turn(player, total)
    
    # Print dice roll to console for visibility
    sys.stdout.write(f"\n    🎲 {player_name} rolled: {die1_display} + {die2_display} = {total} movement spaces\n")
    sys.stdout.flush()
    
    result = f"🎲 DICE ROLL: {die1_display} + {die2_display} = {total} movement spaces\n\n"
    
    # Handle magnifying glass clues
    if magnifying_count > 0:
        result += f"🔍 MAGNIFYING GLASS {'x2' if magnifying_count == 2 else ''}!\n"
        result += "You get a free clue about the mystery!\n\n"
        sys.stdout.write(f"    🔍 MAGNIFYING GLASS! {player_name} gets a free clue!\n")
        
        for _ in range(magnifying_count):
            clue_result = game_state.get_random_clue(player)
            if clue_result:
                clue_text, holder_name = clue_result
                if holder_name:
                    result += f"  💡 CLUE: {clue_text} (shown by {holder_name})\n"
                    sys.stdout.write(f"    💡 CLUE: {clue_text} (shown by {holder_name})\n")
                    # Extract card name from clue text (format: "CardName is NOT the murder type")
                    card_name = clue_text.split(" is NOT")[0]
                    # Update all players' notebooks with this information
                    update_all_notebooks_card_shown(card_name, holder_name)
                else:
                    result += f"  💡 CLUE: {clue_text}\n"
                    sys.stdout.write(f"    💡 CLUE: {clue_text}\n")
            else:
                result += f"  💡 CLUE: No additional clues available.\n"
        result += "\n  📝 All players' notebooks have been updated with this clue.\n\n"
        sys.stdout.flush()
    
    # Show current position and reachable rooms
    if player.current_room and not player.in_hallway:
        # Player is in a room - show room exits and secret passage
        result += f"📍 You are in {player.current_room.value}\n"
        result += f"   Moves available: {player.moves_remaining}\n\n"
        
        # Show door exits
        doors = game_state.get_room_doors(player.current_room)
        if doors:
            result += f"🚪 Room exits (doors):\n"
            for door_pos in doors:
                result += f"   • Door at position ({door_pos[0]}, {door_pos[1]})\n"
        
        # Show secret passage if available
        if player.current_room in SECRET_PASSAGES:
            dest = SECRET_PASSAGES[player.current_room]
            result += f"\n🔑 SECRET PASSAGE available to {dest.value}!\n"
            result += "   (Using the secret passage ends your movement)\n"
        
        result += f"\n💡 Use 'Move To Room' to exit through a door and navigate to another room."
    else:
        # Player is in hallway - show reachable rooms
        if player.position:
            result += f"📍 You are at position ({player.position[0]}, {player.position[1]}) in the hallway\n"
        else:
            start_name = STARTING_POSITION_NAMES.get(player.character, "START")
            result += f"📍 You are at {start_name}\n"
        result += f"   Moves remaining: {player.moves_remaining}\n\n"
        
        # Find reachable rooms
        reachable = game_state.get_reachable_rooms(player)
        if reachable:
            result += "🚪 ROOMS YOU CAN REACH:\n"
            for room, distance, path in reachable:
                result += f"   • {room.value} - {distance} steps away\n"
        else:
            result += "⚠️ No rooms reachable with current moves.\n"
            result += "   You may need to move closer in the hallway.\n"
        
        result += f"\n💡 Use 'Move To Room' with a room name to navigate there."
    
    result += "\n\n⚠️ MOVEMENT RULES:\n"
    result += "   • Move only horizontal/vertical (no diagonal)\n"
    result += "   • Cannot pass through occupied squares\n"
    result += "   • Movement STOPS when entering a room\n"
    result += "   • Cannot cross same square twice in one turn"
    
    return result


@tool("Get Available Moves")
def get_available_moves(player_name: str) -> str:
    """
    Get the rooms you can move to with your remaining movement.
    
    MOVEMENT RULES:
    - Move horizontally or vertically only (no diagonal)
    - Cannot pass through or land on occupied squares
    - Movement STOPS when you enter a room
    - Cannot visit same square twice in one turn
    - Secret passages can be used from corner rooms
    
    Args:
        player_name: Your player name
    
    Returns:
        List of rooms you can reach with current movement
    """
    game_state = get_game_state()
    player = game_state.get_player_by_name(player_name)
    
    if not player:
        return f"Error: Player {player_name} not found"
    
    result = "=== AVAILABLE MOVES ===\n\n"
    
    # Show current location
    if player.current_room and not player.in_hallway:
        current = player.current_room.value
        result += f"📍 Current location: {current}\n"
        
        # Show doors to exit
        doors = game_state.get_room_doors(player.current_room)
        occupied = game_state.get_occupied_positions(exclude_player=player)
        
        if doors:
            result += f"\n🚪 Exits from {current}:\n"
            for door_pos in doors:
                if door_pos in occupied:
                    result += f"   • Door at ({door_pos[0]}, {door_pos[1]}) - BLOCKED\n"
                else:
                    result += f"   • Door at ({door_pos[0]}, {door_pos[1]}) - Available\n"
        
        # Show secret passage if available
        if player.current_room in SECRET_PASSAGES:
            dest = SECRET_PASSAGES[player.current_room]
            result += f"\n🔑 SECRET PASSAGE to {dest.value}!\n"
            result += "   (Using passage ends your turn immediately)\n"
        
        result += f"\n💡 Roll dice first to get movement points, then use 'Move To Room'."
        
    else:
        # In hallway
        if player.position:
            result += f"📍 Current position: ({player.position[0]}, {player.position[1]}) in hallway\n"
        else:
            start_name = STARTING_POSITION_NAMES.get(player.character, "START")
            result += f"📍 Current position: {start_name}\n"
        
        result += f"   Moves remaining: {player.moves_remaining}\n\n"
        
        if player.moves_remaining <= 0:
            result += "⚠️ No moves remaining. Roll dice to get movement points.\n"
        else:
            # Find reachable rooms
            reachable = game_state.get_reachable_rooms(player)
            
            if reachable:
                result += "🚪 ROOMS YOU CAN REACH:\n"
                for room, distance, path in reachable:
                    result += f"   • {room.value} - {distance} steps\n"
            else:
                result += "⚠️ No rooms reachable with current moves.\n"
                result += "   You need to roll more moves or position closer.\n"
            
            # Show immediate adjacent moves
            valid_moves = game_state.get_valid_moves_from_position(player)
            if valid_moves:
                result += f"\n🚶 Adjacent squares you can step to:\n"
                for row, col, room in valid_moves[:5]:  # Limit display
                    if room:
                        result += f"   • ({row}, {col}) → Enter {room.value}\n"
                    else:
                        result += f"   • ({row}, {col}) - hallway\n"
    
    result += "\n⚠️ MOVEMENT RULES:\n"
    result += "   • No diagonal movement\n"
    result += "   • Cannot pass through other players\n"
    result += "   • Entering a room ends movement\n"
    result += "   • Cannot cross same square twice per turn"
    
    return result


@tool("Move To Room")
def move_to_room(player_name: str, room_name: str) -> str:
    """
    Move to a room using your dice roll movement.
    
    MOVEMENT RULES:
    - You can only move the number of spaces you rolled
    - Move horizontally or vertically only (no diagonal)
    - Cannot pass through or land on occupied hallway squares
    - Movement STOPS immediately when you enter a room
    - Cannot visit the same square twice in one turn
    
    If in a room with a SECRET PASSAGE, you can use it instead (ends movement).
    
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
    
    # Get current location description
    if player.current_room and not player.in_hallway:
        current_location = player.current_room.value
        
        # Check if using secret passage
        if player.current_room in SECRET_PASSAGES and SECRET_PASSAGES[player.current_room] == target_room:
            success, msg = game_state.use_secret_passage(player)
            if success:
                sys.stdout.write(f"    🔑 {player_name} used SECRET PASSAGE: {current_location} → {target_room.value}\n")
                sys.stdout.flush()
                return f"🔑 {msg}\n\nYou can now make a suggestion about {target_room.value}."
            else:
                return f"❌ {msg}"
        
        # Need to exit room first - find available doors
        doors = game_state.get_room_doors(player.current_room)
        
        if not doors:
            return f"❌ Cannot find exit from {current_location}"
        
        # Try each door to find path to target room
        best_door = None
        min_distance = float('inf')
        
        occupied = game_state.get_occupied_positions(exclude_player=player)
        
        for door_pos in doors:
            if door_pos in occupied:
                continue  # Door blocked
            
            # Temporarily exit through this door and check if target is reachable
            # We'll pick the door that gives shortest path
            # For now, just use the first unblocked door
            best_door = door_pos
            break
        
        if not best_door:
            return f"❌ All exits from {current_location} are blocked by other players"
        
        # Exit through the door
        if not game_state.exit_room_to_hallway(player, best_door):
            return f"❌ Could not exit {current_location}"
        
        sys.stdout.write(f"    🚶 {player_name} exited {current_location} to hallway\n")
    
    # Now player is in hallway - check if they have moves remaining
    if player.moves_remaining <= 0:
        return f"❌ No moves remaining. You need to roll dice first or you've used all your moves."
    
    # Check if target room is reachable
    reachable = game_state.get_reachable_rooms(player)
    target_reachable = None
    
    for room, distance, path in reachable:
        if room == target_room:
            target_reachable = (room, distance, path)
            break
    
    if not target_reachable:
        # List what IS reachable
        if reachable:
            reachable_names = [f"{r.value} ({d} steps)" for r, d, p in reachable]
            return (f"❌ Cannot reach {target_room.value} with {player.moves_remaining} moves remaining.\n\n"
                    f"Rooms you CAN reach:\n" + "\n".join(f"  • {n}" for n in reachable_names))
        else:
            return (f"❌ Cannot reach any room with {player.moves_remaining} moves remaining.\n"
                    f"You may need to move closer in the hallway first.")
    
    room, distance, path = target_reachable
    
    # Execute the movement along the path
    start_pos = player.position
    for i, (row, col) in enumerate(path[1:], 1):  # Skip first position (current)
        success, entered_room, msg = game_state.move_player_one_step(player, row, col)
        if not success:
            return f"❌ Movement blocked at step {i}: {msg}"
        
        if entered_room:
            # Entered the room!
            sys.stdout.write(f"    🚶 {player_name} moved: ({start_pos[0]},{start_pos[1]}) → {entered_room.value} ({distance} steps)\n")
            sys.stdout.flush()
            return f"✓ Moved to {entered_room.value} in {distance} steps.\n\nYou can now make a suggestion about this room."
    
    # Should have entered room by end of path
    sys.stdout.write(f"    🚶 {player_name} moved {distance} steps toward {target_room.value}\n")
    sys.stdout.flush()
    return f"✓ Moved toward {target_room.value}. Moves remaining: {player.moves_remaining}"


@tool("Make Suggestion")
def make_suggestion(player_name: str, suspect: str, weapon: str) -> str:
    """
    Make a suggestion about the murder. Per official Clue rules:
    - You can only suggest while in a room
    - You must ENTER the room during your turn (roll dice and move into it)
    - The suggestion MUST include the room you're currently in
    - The suggested suspect token is moved to your room
    - Players clockwise from you try to disprove by showing ONE card
    - You cannot make repeated suggestions in the same room without leaving first
      (Exception: if you were moved to the room by another player's suggestion)
    
    IMPORTANT: You cannot suggest if you just stayed in the same room without moving!
    You must roll the dice and enter a room to make a suggestion.
    
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
        return "Error: You must be in a room to make a suggestion. Roll the dice and move to a room first."
    
    # Check if player entered a room this turn
    if not player.entered_room_this_turn and not player.was_moved_by_suggestion:
        return "Error: You must ENTER a room during your turn to make a suggestion. You are currently in a room but did not enter it this turn. You need to leave and re-enter a room, or use your dice roll to move to a different room."
    
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
    
    # Print suggestion to console
    sys.stdout.write(f"\n    📣 SUGGESTION: {player_name} suggests {valid_suspect} with the {valid_weapon} in the {suggestion.room}\n")
    
    result = f"📣 SUGGESTION: {valid_suspect} with the {valid_weapon} in the {suggestion.room}\n"
    result += f"   (The {valid_suspect} token has been moved to the {suggestion.room})\n"
    
    # Add notebook warning if any
    if notebook_warning:
        result += notebook_warning
    
    result += "\n"
    
    if suggestion.disproven_by:
        result += f"❌ DISPROVEN by {suggestion.disproven_by} who showed you: {suggestion.card_shown}\n"
        result += f"   This means {suggestion.card_shown} is NOT part of the solution.\n"
        result += f"   📝 All players' notebooks have been auto-updated!"
        sys.stdout.write(f"    ❌ Disproven by {suggestion.disproven_by} (showed: {suggestion.card_shown})\n")
        sys.stdout.flush()
        # Update player knowledge
        if suggestion.card_shown not in player.knowledge["seen_cards"]:
            player.knowledge["seen_cards"].append(suggestion.card_shown)
        # Update ALL players' notebooks with this information
        update_all_notebooks_card_shown(suggestion.card_shown, suggestion.disproven_by)
    else:
        result += "✓ NO ONE could disprove this suggestion!\n"
        result += "  This is a VERY strong lead - consider making an accusation!"
        sys.stdout.write(f"    ✓ NO ONE could disprove!\n")
        sys.stdout.flush()
    
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
        sys.stdout.write(f"\n    🎉 ACCUSATION CORRECT! {player_name} WINS!\n")
        sys.stdout.write(f"    🔍 Solution: {valid_suspect} with the {valid_weapon} in the {valid_room}\n")
        sys.stdout.flush()
        return f"🎉 CORRECT! {player_name} WINS! The solution was {valid_suspect} with the {valid_weapon} in the {valid_room}!"
    else:
        sys.stdout.write(f"\n    ❌ WRONG ACCUSATION! {player_name} is eliminated!\n")
        sys.stdout.write(f"    ❌ Accused: {valid_suspect} with the {valid_weapon} in the {valid_room}\n")
        sys.stdout.flush()
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
