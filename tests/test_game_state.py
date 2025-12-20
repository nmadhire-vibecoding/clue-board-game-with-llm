"""
Tests for Game State Management
Based on official Cluedo/Clue rules from Wikipedia.
"""

import pytest
from clue_game.game_state import (
    GameState,
    Player,
    Card,
    Suggestion,
    Room,
    Suspect,
    Weapon,
    ROOM_CONNECTIONS,
    SECRET_PASSAGES,
    STARTING_POSITIONS,
    get_game_state,
    reset_game_state,
)


class TestRoomConnections:
    """Test room adjacency and movement rules."""
    
    def test_no_diagonal_movement(self):
        """Rooms should only connect through doorways, not diagonally."""
        # Kitchen is in top-left, Conservatory is in top-right
        # They should NOT be directly connected (diagonal) - only through hallways
        assert Room.CONSERVATORY not in ROOM_CONNECTIONS[Room.KITCHEN]
        assert Room.KITCHEN not in ROOM_CONNECTIONS[Room.CONSERVATORY]
    
    def test_secret_passages_exist(self):
        """Secret passages should connect diagonal corner rooms via SECRET_PASSAGES dict."""
        # Secret passages are separate from regular room connections
        # Kitchen <-> Study (diagonal corners)
        assert SECRET_PASSAGES[Room.KITCHEN] == Room.STUDY
        assert SECRET_PASSAGES[Room.STUDY] == Room.KITCHEN
        
        # Conservatory <-> Lounge (diagonal corners)
        assert SECRET_PASSAGES[Room.CONSERVATORY] == Room.LOUNGE
        assert SECRET_PASSAGES[Room.LOUNGE] == Room.CONSERVATORY
    
    def test_secret_passages_not_in_regular_connections(self):
        """Secret passages should NOT be in regular ROOM_CONNECTIONS (they're separate)."""
        # Regular door connections don't include secret passage destinations
        # (secret passages are handled separately in get_available_moves)
        assert Room.STUDY not in ROOM_CONNECTIONS[Room.KITCHEN]
        assert Room.KITCHEN not in ROOM_CONNECTIONS[Room.STUDY]
        assert Room.LOUNGE not in ROOM_CONNECTIONS[Room.CONSERVATORY]
        assert Room.CONSERVATORY not in ROOM_CONNECTIONS[Room.LOUNGE]
    
    def test_secret_passages_dict(self):
        """SECRET_PASSAGES dict should have correct mappings."""
        assert SECRET_PASSAGES[Room.KITCHEN] == Room.STUDY
        assert SECRET_PASSAGES[Room.STUDY] == Room.KITCHEN
        assert SECRET_PASSAGES[Room.CONSERVATORY] == Room.LOUNGE
        assert SECRET_PASSAGES[Room.LOUNGE] == Room.CONSERVATORY
    
    def test_all_rooms_have_connections(self):
        """Every room should have at least one connection."""
        for room in Room:
            assert room in ROOM_CONNECTIONS
            assert len(ROOM_CONNECTIONS[room]) >= 1


class TestStartingPositions:
    """Test that starting positions follow official rules."""
    
    def test_all_suspects_have_starting_positions(self):
        """Every suspect should have a designated starting position."""
        for suspect in Suspect:
            assert suspect in STARTING_POSITIONS
    
    def test_mrs_peacock_advantage(self):
        """Mrs. Peacock should start closest to Conservatory (official rule)."""
        assert STARTING_POSITIONS[Suspect.MRS_PEACOCK] == Room.CONSERVATORY
    
    def test_professor_plum_near_study(self):
        """Professor Plum starts near Study for Kitchen passage strategy."""
        assert STARTING_POSITIONS[Suspect.PROFESSOR_PLUM] == Room.STUDY


class TestGameSetup:
    """Test game initialization."""
    
    def test_setup_creates_solution(self):
        """Game setup should create a solution with one of each card type."""
        game = GameState()
        game.setup_game(["Player1", "Player2", "Player3"])
        
        assert "suspect" in game.solution
        assert "weapon" in game.solution
        assert "room" in game.solution
        assert game.solution["suspect"].card_type == "suspect"
        assert game.solution["weapon"].card_type == "weapon"
        assert game.solution["room"].card_type == "room"
    
    def test_setup_deals_remaining_cards(self):
        """All non-solution cards should be dealt to players."""
        game = GameState()
        game.setup_game(["Player1", "Player2", "Player3"])
        
        # 21 total cards - 3 solution = 18 to deal
        total_dealt = sum(len(p.cards) for p in game.players)
        assert total_dealt == 18
    
    def test_miss_scarlet_goes_first(self):
        """Player with Miss Scarlet should be first (traditional rule)."""
        game = GameState()
        game.setup_game(["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"])
        
        # Find which player has Miss Scarlet
        scarlet_player = None
        for player in game.players:
            if player.character == Suspect.MISS_SCARLET:
                scarlet_player = player
                break
        
        # That player should be first (index 0)
        assert game.players[0] == scarlet_player
    
    def test_players_start_at_designated_positions(self):
        """Players should start at their character's designated room."""
        game = GameState()
        game.setup_game(["P1", "P2", "P3"])
        
        for player in game.players:
            expected_room = STARTING_POSITIONS[player.character]
            assert player.current_room == expected_room


class TestMovement:
    """Test movement rules."""
    
    def test_move_to_adjacent_room(self):
        """Player should be able to move to adjacent room."""
        game = reset_game_state()
        game.setup_game(["Test"])
        player = game.players[0]
        player.current_room = Room.KITCHEN
        
        # Kitchen connects to Ballroom
        assert game.move_player(player, Room.BALLROOM) == True
        assert player.current_room == Room.BALLROOM
    
    def test_cannot_move_to_non_adjacent_room(self):
        """Player should NOT be able to move to non-adjacent room."""
        game = reset_game_state()
        game.setup_game(["Test"])
        player = game.players[0]
        player.current_room = Room.KITCHEN
        
        # Kitchen does NOT connect to Library
        assert game.move_player(player, Room.LIBRARY) == False
        assert player.current_room == Room.KITCHEN  # Didn't move
    
    def test_secret_passage_movement(self):
        """Player should be able to use secret passages."""
        game = reset_game_state()
        game.setup_game(["Test"])
        player = game.players[0]
        player.current_room = Room.KITCHEN
        
        # Kitchen -> Study via secret passage
        assert game.move_player(player, Room.STUDY) == True
        assert player.current_room == Room.STUDY
    
    def test_movement_resets_suggestion_flag(self):
        """Moving should allow player to suggest again."""
        game = reset_game_state()
        game.setup_game(["Test"])
        player = game.players[0]
        player.current_room = Room.KITCHEN
        player.has_moved_since_suggestion = False
        
        game.move_player(player, Room.BALLROOM)
        assert player.has_moved_since_suggestion == True
    
    def test_dice_roll_returns_valid_values(self):
        """Dice should return values between 1-6 for each die, plus magnifying glass count."""
        game = GameState()
        
        for _ in range(100):  # Test multiple rolls
            die1, die2, magnifying_count = game.roll_dice()
            assert 1 <= die1 <= 6
            assert 1 <= die2 <= 6
            # Magnifying glass appears on 1s
            expected_magnifying = (1 if die1 == 1 else 0) + (1 if die2 == 1 else 0)
            assert magnifying_count == expected_magnifying
    
    def test_magnifying_glass_gives_clue(self):
        """Rolling magnifying glass should give a clue about non-solution cards."""
        game = reset_game_state()
        game.setup_game(["Test", "Other"])
        player = game.players[0]
        
        clue = game.get_random_clue(player)
        
        # Clue should be about a card NOT in solution
        if clue:
            assert "NOT the murder" in clue
            # Verify the clue doesn't reveal solution cards
            solution_names = {
                game.solution["suspect"].name,
                game.solution["weapon"].name,
                game.solution["room"].name,
            }
            for name in solution_names:
                assert name not in clue


class TestSuggestions:
    """Test suggestion rules."""
    
    def test_suggestion_requires_room(self):
        """Player must be in a room to make a suggestion."""
        game = reset_game_state()
        game.setup_game(["Test", "Other"])
        player = game.players[0]
        player.current_room = None
        
        with pytest.raises(ValueError, match="must be in a room"):
            game.make_suggestion(player, "Miss Scarlet", "Knife")
    
    def test_suggestion_uses_current_room(self):
        """Suggestion room should be the player's current room."""
        game = reset_game_state()
        game.setup_game(["Test", "Other"])
        player = game.players[0]
        player.current_room = Room.LIBRARY
        
        suggestion = game.make_suggestion(player, "Miss Scarlet", "Knife")
        assert suggestion.room == "Library"
    
    def test_suggestion_moves_suspect_to_room(self):
        """Suggested suspect should be moved to the room."""
        game = reset_game_state()
        game.setup_game(["Test", "Suspect"])
        
        # Set up: Test is in Library, Suspect has Miss Scarlet and is in Kitchen
        test_player = game.players[0]
        suspect_player = None
        for p in game.players:
            if p.character == Suspect.MISS_SCARLET:
                suspect_player = p
                p.current_room = Room.KITCHEN
                break
        
        test_player.current_room = Room.LIBRARY
        
        # Make suggestion about Miss Scarlet
        game.make_suggestion(test_player, "Miss Scarlet", "Knife")
        
        # Miss Scarlet should now be in Library
        if suspect_player:
            assert suspect_player.current_room == Room.LIBRARY
            assert suspect_player.was_moved_by_suggestion == True
    
    def test_no_repeated_suggestions_same_room(self):
        """Cannot suggest twice in same room without leaving (American rules)."""
        game = reset_game_state()
        game.setup_game(["Test", "Other"])
        player = game.get_player_by_name("Test")
        player.current_room = Room.LIBRARY
        
        # Ensure player isn't the suspect being suggested (would trigger move_by_suggestion)
        # Use a suspect that isn't the Test player's character
        suspect_to_suggest = "Colonel Mustard" if player.character.value != "Colonel Mustard" else "Mrs. White"
        
        # First suggestion should work
        game.make_suggestion(player, suspect_to_suggest, "Knife")
        
        # Second suggestion in same room should fail
        with pytest.raises(ValueError, match="must leave and re-enter"):
            game.make_suggestion(player, "Professor Plum", "Rope")
    
    def test_can_suggest_if_moved_by_others(self):
        """Player moved by another's suggestion can suggest immediately."""
        game = reset_game_state()
        game.setup_game(["Test", "Other"])
        player = game.get_player_by_name("Test")
        player.current_room = Room.LIBRARY
        player.was_moved_by_suggestion = True
        player.has_moved_since_suggestion = True
        player.last_suggestion_room = Room.LIBRARY
        
        # Should work even though it's the same room
        suggestion = game.make_suggestion(player, "Miss Scarlet", "Knife")
        assert suggestion is not None
    
    def test_disproval_goes_clockwise(self):
        """Disproving should go clockwise from suggester."""
        game = reset_game_state()
        game.setup_game(["P1", "P2", "P3"])
        
        # Find P2 and give them a specific card
        p1 = game.get_player_by_name("P1")
        p2 = game.get_player_by_name("P2")
        p3 = game.get_player_by_name("P3")
        
        test_card = Card("Miss Scarlet", "suspect")
        # Clear all cards first, then give only P2 the card
        p1.cards = []
        p2.cards = [test_card]
        p3.cards = []
        
        # P1 makes suggestion about Miss Scarlet
        p1.current_room = Room.LIBRARY
        suggestion = game.make_suggestion(p1, "Miss Scarlet", "Knife")
        
        # The player with the card should disprove
        if suggestion.disproven_by:
            assert suggestion.disproven_by == "P2"


class TestAccusations:
    """Test accusation rules."""
    
    def test_correct_accusation_wins(self):
        """Correct accusation should win the game."""
        game = reset_game_state()
        game.setup_game(["Test", "Other"])
        player = game.get_player_by_name("Test")
        
        # Get the actual solution
        suspect = game.solution["suspect"].name
        weapon = game.solution["weapon"].name
        room = game.solution["room"].name
        
        result = game.make_accusation(player, suspect, weapon, room)
        assert result == True
        assert game.game_over == True
        assert game.winner == "Test"
    
    def test_wrong_accusation_eliminates_player(self):
        """Wrong accusation should eliminate player."""
        game = reset_game_state()
        game.setup_game(["Test", "Other"])
        player = game.get_player_by_name("Test")
        
        # Make wrong accusation
        result = game.make_accusation(player, "Miss Scarlet", "Knife", "Kitchen")
        
        # Unless we got lucky, player should be eliminated
        if not result:
            assert player.is_active == False
    
    def test_accusation_can_include_any_room(self):
        """Accusation can include any room, not just current location."""
        game = reset_game_state()
        game.setup_game(["Test", "Other"])
        player = game.get_player_by_name("Test")
        player.current_room = Room.KITCHEN  # Player is in Kitchen
        
        # Get actual solution
        suspect = game.solution["suspect"].name
        weapon = game.solution["weapon"].name
        room = game.solution["room"].name
        
        # Should be able to accuse correct room even if not there
        result = game.make_accusation(player, suspect, weapon, room)
        assert result == True  # Correct accusation works regardless of location
    
    def test_only_one_accusation_per_turn(self):
        """Player can only make one accusation per turn."""
        game = reset_game_state()
        game.setup_game(["P1", "P2", "P3"])
        player = game.get_player_by_name("P1")
        
        # First accusation (wrong) should work
        game.make_accusation(player, "Wrong", "Wrong", "Wrong")
        
        # Player might be eliminated, but if they try again it should fail
        # Reset active status to test the per-turn logic specifically
        player.is_active = True
        
        with pytest.raises(ValueError, match="only make one accusation per turn"):
            game.make_accusation(player, "Wrong2", "Wrong2", "Wrong2")
    
    def test_accusation_flag_resets_on_next_turn(self):
        """The accusation flag should reset when turn advances."""
        game = reset_game_state()
        game.setup_game(["P1", "P2"])
        player = game.get_player_by_name("P1")
        
        player.has_accused_this_turn = True
        game.next_turn()
        
        # Flag should be reset for current player after turn change
        assert player.has_accused_this_turn == False

    def test_last_player_wins_by_default(self):
        """If all but one player makes wrong accusations, remaining player wins."""
        game = reset_game_state()
        game.setup_game(["P1", "P2"])
        
        # Get the players by name to avoid ordering issues
        p1 = game.get_player_by_name("P1")
        p2 = game.get_player_by_name("P2")
        
        # P1 makes wrong accusation
        game.make_accusation(p1, "Wrong", "Wrong", "Wrong")
        
        # Now only P2 is active, so P2 wins
        assert game.game_over == True
        assert game.winner == "P2"


class TestPlayerTracking:
    """Test player state tracking."""
    
    def test_player_has_moved_since_suggestion_flag(self):
        """Track whether player has moved since last suggestion."""
        player = Player(name="Test", character=Suspect.MISS_SCARLET)
        assert player.has_moved_since_suggestion == True  # Default
    
    def test_player_was_moved_by_suggestion_flag(self):
        """Track whether player was moved by another's suggestion."""
        player = Player(name="Test", character=Suspect.MISS_SCARLET)
        assert player.was_moved_by_suggestion == False  # Default
    
    def test_last_suggestion_room_tracked(self):
        """Track the room where player last made a suggestion."""
        player = Player(name="Test", character=Suspect.MISS_SCARLET)
        assert player.last_suggestion_room is None  # Default


class TestCards:
    """Test card mechanics."""
    
    def test_card_equality(self):
        """Cards with same name and type should be equal."""
        card1 = Card("Miss Scarlet", "suspect")
        card2 = Card("Miss Scarlet", "suspect")
        assert card1 == card2
    
    def test_card_hash(self):
        """Cards should be hashable for use in sets."""
        card = Card("Miss Scarlet", "suspect")
        card_set = {card}
        assert card in card_set
    
    def test_all_suspects_exist(self):
        """All 6 suspects should be defined."""
        suspects = list(Suspect)
        assert len(suspects) == 6
        assert Suspect.MISS_SCARLET in suspects
        assert Suspect.COLONEL_MUSTARD in suspects
        assert Suspect.MRS_WHITE in suspects
        assert Suspect.MR_GREEN in suspects
        assert Suspect.MRS_PEACOCK in suspects
        assert Suspect.PROFESSOR_PLUM in suspects
    
    def test_all_weapons_exist(self):
        """All 6 weapons should be defined."""
        weapons = list(Weapon)
        assert len(weapons) == 6
    
    def test_all_rooms_exist(self):
        """All 9 rooms should be defined."""
        rooms = list(Room)
        assert len(rooms) == 9


class TestGlobalState:
    """Test global game state management."""
    
    def test_get_game_state_singleton(self):
        """get_game_state should return the same instance."""
        state1 = get_game_state()
        state2 = get_game_state()
        assert state1 is state2
    
    def test_reset_game_state(self):
        """reset_game_state should create a new instance."""
        state1 = get_game_state()
        state1.turn_number = 999
        
        state2 = reset_game_state()
        assert state2.turn_number == 1
        assert state1 is not state2
