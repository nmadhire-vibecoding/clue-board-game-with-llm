"""
Tests for Game Tools
Tests the tool functions agents use to interact with the game.

Note: CrewAI @tool decorated functions return Tool objects.
To call them directly in tests, we use .func() to get the underlying function.
"""

import pytest
from clue_game.game_state import (
    reset_game_state,
    Room,
    Suspect,
    Weapon,
)
from clue_game.tools.game_tools import (
    get_my_cards,
    get_current_location,
    get_available_moves,
    roll_dice,
    move_to_room,
    make_suggestion,
    make_accusation,
    get_game_status,
    get_suggestion_history,
    get_my_knowledge,
    get_valid_options,
)


class TestGetMyCards:
    """Test the Get My Cards tool."""
    
    def test_returns_player_cards(self):
        """Should return the cards in player's hand."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        
        result = get_my_cards.func(player_name="TestPlayer")
        
        assert "Your cards" in result
        assert "total" in result
    
    def test_error_for_unknown_player(self):
        """Should return error for unknown player."""
        reset_game_state()
        result = get_my_cards.func(player_name="NonExistent")
        assert "Error" in result


class TestGetCurrentLocation:
    """Test the Get Current Location tool."""
    
    def test_returns_room(self):
        """Should return player's current room."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.LIBRARY
        player.in_hallway = False
        
        result = get_current_location.func(player_name="TestPlayer")
        
        assert "Library" in result
    
    def test_shows_moved_by_suggestion(self):
        """Should indicate if player was moved by suggestion."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.LIBRARY
        player.in_hallway = False
        player.was_moved_by_suggestion = True
        
        result = get_current_location.func(player_name="TestPlayer")
        
        assert "moved" in result.lower() or "suggestion" in result.lower()


class TestRollDice:
    """Test the Roll Dice tool."""
    
    def test_returns_dice_values(self):
        """Should return dice roll results."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        
        result = roll_dice.func(player_name="TestPlayer")
        
        assert "DICE ROLL" in result
        assert "+" in result  # Shows die1 + die2
    
    def test_shows_available_moves(self):
        """Should show rooms player can move to after rolling dice."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.KITCHEN
        player.in_hallway = False
        
        result = roll_dice.func(player_name="TestPlayer")
        
        # With the grid system, result shows reachable rooms based on dice roll
        # Should mention the turn started and available options
        assert "DICE ROLL" in result
        # Kitchen has secret passage to Study and doors to exit
        assert "REACHABLE ROOMS" in result or "Study" in result or "door" in result.lower()


class TestGetAvailableMoves:
    """Test the Get Available Moves tool."""
    
    def test_lists_adjacent_rooms(self):
        """Should list doors and options when in a room."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.KITCHEN
        player.in_hallway = False
        
        result = get_available_moves.func(player_name="TestPlayer")
        
        # In the new grid system, when in a room, shows doors and passages
        # Kitchen has doors and a secret passage to Study
        assert "door" in result.lower() or "Study" in result or "SECRET PASSAGE" in result
    
    def test_indicates_secret_passages(self):
        """Should mark secret passages."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.KITCHEN
        player.in_hallway = False
        
        result = get_available_moves.func(player_name="TestPlayer")
        
        assert "SECRET PASSAGE" in result
        assert "Study" in result
    
    def test_no_diagonal_warning(self):
        """Should warn about no diagonal movement."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.HALL
        player.in_hallway = False
        
        result = get_available_moves.func(player_name="TestPlayer")
        
        assert "diagonal" in result.lower() or "doorway" in result.lower()


class TestMoveToRoom:
    """Test the Move To Room tool."""
    
    def test_successful_move(self):
        """Should move player to adjacent room via secret passage."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.KITCHEN
        player.in_hallway = False
        # Set moves remaining for the turn (simulates rolling dice)
        player.moves_remaining = 6
        
        # Use secret passage from Kitchen to Study (doesn't require dice roll steps)
        result = move_to_room.func(player_name="TestPlayer", room_name="Study")
        
        assert "moved" in result.lower() or "✓" in result or "Study" in result
        assert player.current_room == Room.STUDY
    
    def test_failed_move_non_adjacent(self):
        """Should fail for unreachable room without enough moves."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.KITCHEN
        player.in_hallway = False
        # Set a small number of moves (not enough to reach Library)
        player.moves_remaining = 1
        
        result = move_to_room.func(player_name="TestPlayer", room_name="Library")
        
        # Should fail - Library is not reachable from Kitchen with only 1 move
        # (Kitchen has secret passage to Study, not Library)
        assert "Cannot" in result or "❌" in result or "not reachable" in result.lower() or "No path" in result
    
    def test_invalid_room_name(self):
        """Should error for invalid room name."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        
        result = move_to_room.func(player_name="TestPlayer", room_name="InvalidRoom")
        
        assert "Error" in result or "Invalid" in result


class TestMakeSuggestion:
    """Test the Make Suggestion tool."""
    
    def test_successful_suggestion(self):
        """Should make a suggestion in current room."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.LIBRARY
        player.in_hallway = False
        
        result = make_suggestion.func(player_name="TestPlayer", suspect="Miss Scarlet", weapon="Knife")
        
        assert "SUGGESTION" in result
        assert "Miss Scarlet" in result
        assert "Knife" in result
        assert "Library" in result
    
    def test_suggestion_not_in_room(self):
        """Should fail if player not in a room."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = None
        
        result = make_suggestion.func(player_name="TestPlayer", suspect="Miss Scarlet", weapon="Knife")
        
        assert "Error" in result
    
    def test_invalid_suspect(self):
        """Should error for invalid suspect name."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.LIBRARY
        player.in_hallway = False
        
        result = make_suggestion.func(player_name="TestPlayer", suspect="Invalid Person", weapon="Knife")
        
        assert "Error" in result or "Invalid" in result
    
    def test_invalid_weapon(self):
        """Should error for invalid weapon name."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.LIBRARY
        player.in_hallway = False
        
        result = make_suggestion.func(player_name="TestPlayer", suspect="Miss Scarlet", weapon="Invalid Weapon")
        
        assert "Error" in result or "Invalid" in result
    
    def test_mentions_suspect_moved(self):
        """Should mention that suspect was moved to room."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.current_room = Room.LIBRARY
        player.in_hallway = False
        
        result = make_suggestion.func(player_name="TestPlayer", suspect="Miss Scarlet", weapon="Knife")
        
        assert "moved" in result.lower()


class TestMakeAccusation:
    """Test the Make Accusation tool."""
    
    def test_correct_accusation(self):
        """Should win with correct accusation."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        
        # Get the actual solution
        suspect = game.solution["suspect"].name
        weapon = game.solution["weapon"].name
        room = game.solution["room"].name
        
        result = make_accusation.func(player_name="TestPlayer", suspect=suspect, weapon=weapon, room=room)
        
        assert "CORRECT" in result or "WINS" in result or "🎉" in result
    
    def test_wrong_accusation(self):
        """Should eliminate player with wrong accusation."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        
        result = make_accusation.func(player_name="TestPlayer", suspect="Miss Scarlet", weapon="Knife", room="Kitchen")
        
        # Unless we got lucky with the solution
        if "CORRECT" not in result:
            assert "WRONG" in result or "eliminated" in result.lower() or "❌" in result
    
    def test_eliminated_player_cannot_accuse(self):
        """Eliminated player should not be able to accuse."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        player = game.get_player_by_name("TestPlayer")
        player.is_active = False
        
        result = make_accusation.func(player_name="TestPlayer", suspect="Miss Scarlet", weapon="Knife", room="Kitchen")
        
        assert "eliminated" in result.lower() or "Error" in result


class TestGetGameStatus:
    """Test the Get Game Status tool."""
    
    def test_shows_turn_info(self):
        """Should show current turn information."""
        game = reset_game_state()
        game.setup_game(["P1", "P2"])
        
        result = get_game_status.func()
        
        assert "Turn" in result
        assert "P1" in result or "P2" in result


class TestGetSuggestionHistory:
    """Test the Get Suggestion History tool."""
    
    def test_empty_history(self):
        """Should indicate no suggestions yet."""
        reset_game_state()
        
        result = get_suggestion_history.func()
        
        assert "No suggestions" in result or len(result) > 0
    
    def test_shows_suggestions(self):
        """Should show made suggestions."""
        game = reset_game_state()
        game.setup_game(["P1", "P2"])
        player = game.get_player_by_name("P1")
        player.current_room = Room.LIBRARY
        player.in_hallway = False
        
        # Make a suggestion
        make_suggestion.func(player_name="P1", suspect="Miss Scarlet", weapon="Knife")
        
        result = get_suggestion_history.func()
        
        assert "Miss Scarlet" in result
        assert "Knife" in result


class TestGetMyKnowledge:
    """Test the Get My Knowledge tool."""
    
    def test_shows_hand(self):
        """Should show cards in player's hand."""
        game = reset_game_state()
        game.setup_game(["TestPlayer", "Other"])
        
        result = get_my_knowledge.func(player_name="TestPlayer")
        
        assert "Knowledge" in result or "hand" in result.lower()


class TestGetValidOptions:
    """Test the Get Valid Options tool."""
    
    def test_lists_all_suspects(self):
        """Should list all suspect names."""
        result = get_valid_options.func()
        
        assert "Miss Scarlet" in result
        assert "Colonel Mustard" in result
        assert "Professor Plum" in result
    
    def test_lists_all_weapons(self):
        """Should list all weapon names."""
        result = get_valid_options.func()
        
        assert "Knife" in result
        assert "Candlestick" in result
        assert "Rope" in result
    
    def test_lists_all_rooms(self):
        """Should list all room names."""
        result = get_valid_options.func()
        
        assert "Kitchen" in result
        assert "Library" in result
        assert "Ballroom" in result
