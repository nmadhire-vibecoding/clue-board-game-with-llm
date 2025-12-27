#!/usr/bin/env python
"""
Clue Board Game with LLM Agents
Main entry point for running the multi-agent Clue game.
"""

import os
import sys
import time
import random
import logging
import traceback

# Disable CrewAI tracing before importing crewai
os.environ["CREWAI_TRACING_ENABLED"] = "false"

from dotenv import load_dotenv

from clue_game.game_state import get_game_state, reset_game_state, STARTING_POSITION_NAMES
from clue_game.notebook import reset_all_notebooks
from clue_game.crew import (
    ClueGameCrew,
    create_player_turn_crew,
    create_moderator_announcement_crew,
)


# Load environment variables
load_dotenv()

# Configure logging for debugging LLM issues
logging.basicConfig(
    level=logging.DEBUG if os.environ.get("CLUE_DEBUG") else logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _patch_crewai_printer():
    """
    Monkey-patch CrewAI's Printer class to provide more detailed error messages.
    This intercepts the "Received None or empty response" messages and adds context.
    """
    try:
        from crewai.utilities.printer import Printer
        
        original_print = Printer.print
        
        def enhanced_print(self, content="", color=None, **kwargs):
            # Intercept the empty response error and enhance it
            if "None or empty response" in str(content):
                enhanced_content = (
                    f"{content}\n"
                    f"   💡 This typically indicates:\n"
                    f"      - Gemini safety filters blocked the response\n"
                    f"      - The model returned only function calls (no text)\n"
                    f"      - API quota/rate limit issues\n"
                    f"      - Model overloaded or temporary outage\n"
                    f"   🔧 Set CLUE_DEBUG=1 for more details"
                )
                return original_print(self, content=enhanced_content, color=color, **kwargs)
            return original_print(self, content=content, color=color, **kwargs)
        
        Printer.print = enhanced_print
        logger.debug("Successfully patched CrewAI Printer for enhanced error messages")
    except Exception as e:
        logger.warning(f"Could not patch CrewAI Printer: {e}")


def _patch_gemini_completion():
    """
    Monkey-patch Gemini completion handler to capture and log response details
    when the response is empty, helping diagnose why the LLM returned no content.
    """
    try:
        from crewai.llms.providers.gemini import completion as gemini_module
        
        original_handle_completion = gemini_module.GeminiCompletion._handle_completion
        
        def enhanced_handle_completion(self, contents, system_instruction, config,
                                       available_functions=None, from_task=None,
                                       from_agent=None, response_model=None):
            try:
                # Call the original method
                result = original_handle_completion(
                    self, contents, system_instruction, config,
                    available_functions, from_task, from_agent, response_model
                )
                return result
            except Exception as e:
                # Try to get more details about the response
                try:
                    from google.genai import types
                    # The response is captured in the original method, we can't access it
                    # But we can log the exception context
                    logger.error(f"Gemini completion failed: {e}")
                    logger.error(f"Model: {self.model}")
                    logger.error(f"Config: {config}")
                    if contents:
                        logger.error(f"Number of content items: {len(contents)}")
                        # Log the last content item (usually the latest message)
                        if contents:
                            last_content = contents[-1]
                            if hasattr(last_content, 'parts') and last_content.parts:
                                for i, part in enumerate(last_content.parts):
                                    if hasattr(part, 'text') and part.text:
                                        text = part.text[:200] + "..." if len(part.text) > 200 else part.text
                                        logger.error(f"Last message part {i} (truncated): {text}")
                except Exception as inner_e:
                    logger.warning(f"Could not extract additional details: {inner_e}")
                raise
        
        gemini_module.GeminiCompletion._handle_completion = enhanced_handle_completion
        logger.debug("Successfully patched Gemini completion for detailed logging")
    except ImportError:
        logger.debug("Gemini module not available, skipping patch")
    except Exception as e:
        logger.warning(f"Could not patch Gemini completion: {e}")


# Apply patches when module loads
_patch_crewai_printer()
_patch_gemini_completion()


def get_gemini_response_details(exception):
    """
    Extract Gemini-specific response details from an exception or its context.
    
    This attempts to find and extract safety ratings, block reasons, and
    finish reasons from Gemini API responses.
    
    Args:
        exception: The exception to analyze
        
    Returns:
        A list of detail strings about the Gemini response
    """
    details = []
    
    # Walk up the exception chain to find Gemini-related info
    current = exception
    while current is not None:
        # Check for Gemini response attributes
        if hasattr(current, 'response'):
            resp = current.response
            
            try:
                # Check for candidates with finish reasons
                if hasattr(resp, 'candidates') and resp.candidates and hasattr(resp.candidates, '__iter__'):
                    for i, candidate in enumerate(resp.candidates):
                        if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
                            details.append(f"Candidate {i} finish_reason: {candidate.finish_reason}")
                        if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings and hasattr(candidate.safety_ratings, '__iter__'):
                            ratings = ", ".join([
                                f"{r.category}: {r.probability}" 
                                for r in candidate.safety_ratings if hasattr(r, 'category')
                            ])
                            if ratings:
                                details.append(f"Safety ratings: {ratings}")
                
                # Check for prompt feedback
                if hasattr(resp, 'prompt_feedback') and resp.prompt_feedback:
                    pf = resp.prompt_feedback
                    if hasattr(pf, 'block_reason') and pf.block_reason:
                        details.append(f"Prompt blocked: {pf.block_reason}")
                    if hasattr(pf, 'safety_ratings') and pf.safety_ratings and hasattr(pf.safety_ratings, '__iter__'):
                        ratings = ", ".join([
                            f"{r.category}: {r.probability}" 
                            for r in pf.safety_ratings if hasattr(r, 'category')
                        ])
                        if ratings:
                            details.append(f"Prompt safety ratings: {ratings}")
            except (TypeError, AttributeError):
                # Skip if response object doesn't have expected structure (e.g., Mock objects)
                pass
        
        # Move to the cause
        current = getattr(current, '__cause__', None)
    
    return details


def get_error_details(exception):
    """
    Extract detailed error information from an exception.
    
    Args:
        exception: The exception to analyze
        
    Returns:
        A formatted string with error details
    """
    error_info = []
    error_info.append(f"Type: {type(exception).__name__}")
    error_info.append(f"Message: {str(exception)}")
    
    # Check for nested exceptions or cause
    if hasattr(exception, '__cause__') and exception.__cause__:
        error_info.append(f"Caused by: {type(exception.__cause__).__name__}: {exception.__cause__}")
    
    # Check for HTTP status codes (common in API errors)
    if hasattr(exception, 'status_code'):
        error_info.append(f"Status Code: {exception.status_code}")
    if hasattr(exception, 'response'):
        response = exception.response
        if hasattr(response, 'status_code'):
            error_info.append(f"Response Status: {response.status_code}")
        if hasattr(response, 'text'):
            # Truncate long responses
            text = response.text[:500] if len(response.text) > 500 else response.text
            error_info.append(f"Response Body: {text}")
    
    # Check for error codes
    if hasattr(exception, 'code'):
        error_info.append(f"Error Code: {exception.code}")
    if hasattr(exception, 'error'):
        error_info.append(f"Error Details: {exception.error}")
    
    # Check for args with additional info
    if hasattr(exception, 'args') and len(exception.args) > 1:
        error_info.append(f"Additional Args: {exception.args[1:]}")
    
    # Add Gemini-specific details
    gemini_details = get_gemini_response_details(exception)
    if gemini_details:
        error_info.extend(gemini_details)
    
    # For "None or empty response" errors, provide additional context
    if "None or empty" in str(exception) or "empty response" in str(exception).lower():
        error_info.append("Possible causes: Safety filter blocked response, quota exceeded, model overloaded, or malformed prompt")
        error_info.append("Suggestions: Check GOOGLE_API_KEY is valid, try reducing prompt complexity, or wait and retry")
    
    return " | ".join(error_info)


def retry_with_backoff(func, max_retries=3, base_delay=5):
    """
    Retry a function with exponential backoff.
    
    Args:
        func: Callable to retry
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be multiplied exponentially)
    
    Returns:
        The result of the function call
    
    Raises:
        The last exception if all retries fail
    """
    last_exception = None
    debug_mode = os.environ.get("CLUE_DEBUG", "").lower() in ("1", "true", "yes")
    
    for attempt in range(max_retries + 1):
        try:
            result = func()
            # Check for empty/None response
            if result is None or (hasattr(result, 'raw') and not result.raw):
                # Try to get more info about the empty response
                raw_info = ""
                if result is not None:
                    raw_info = f" (result type: {type(result).__name__}"
                    if hasattr(result, '__dict__'):
                        raw_info += f", attributes: {list(result.__dict__.keys())}"
                    raw_info += ")"
                raise ValueError(f"Empty or None response from LLM{raw_info}")
            return result
        except Exception as e:
            last_exception = e
            error_details = get_error_details(e)
            
            # Log full stack trace in debug mode
            if debug_mode:
                logger.error(f"Attempt {attempt + 1} failed with exception:", exc_info=True)
            
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)  # Exponential backoff: 5, 10, 20 seconds
                sys.stdout.write(f"\n⚠️ Attempt {attempt + 1}/{max_retries + 1} failed\n")
                sys.stdout.write(f"   📋 Error: {error_details}\n")
                if debug_mode:
                    sys.stdout.write(f"   🔍 Stack trace:\n")
                    for line in traceback.format_exception(type(e), e, e.__traceback__):
                        sys.stdout.write(f"      {line}")
                sys.stdout.write(f"🔄 Retrying in {delay} seconds...\n")
                sys.stdout.flush()
                time.sleep(delay)
            else:
                sys.stdout.write(f"\n❌ All {max_retries + 1} attempts failed\n")
                sys.stdout.write(f"   📋 Final Error: {error_details}\n")
                if debug_mode:
                    sys.stdout.write(f"   🔍 Full stack trace:\n")
                    for line in traceback.format_exception(type(e), e, e.__traceback__):
                        sys.stdout.write(f"      {line}")
                sys.stdout.flush()
    raise last_exception


# Player names that map to agent methods
PLAYER_CONFIGS = [
    {"name": "Scarlet", "agent_method": "player_scarlet"},
    {"name": "Mustard", "agent_method": "player_mustard"},
    {"name": "Green", "agent_method": "player_green"},
    {"name": "Peacock", "agent_method": "player_peacock"},
    {"name": "Plum", "agent_method": "player_plum"},
    {"name": "White", "agent_method": "player_white"},
]


def run_game(num_players: int = 6, max_turns: int = 50):
    """
    Run a complete game of Clue with AI agents.
    
    Args:
        num_players: Number of players (3-6)
        max_turns: Maximum number of turns before game ends in a draw
    """
    # Validate number of players
    if num_players < 3 or num_players > 6:
        print("❌ Error: Number of players must be between 3 and 6")
        return None
    
    print("\n" + "=" * 60)
    print("🔍 CLUE: THE MYSTERY GAME WITH AI AGENTS 🔍")
    print("=" * 60 + "\n")
    
    # Initialize game state and reset all notebooks
    game_state = reset_game_state()
    reset_all_notebooks()  # Reset deterministic notebooks for new game
    
    # Select the first N players
    player_names = [p["name"] for p in PLAYER_CONFIGS[:num_players]]
    game_state.setup_game(player_names)
    
    # Track which players have had their first turn (for notebook init)
    players_first_turn = {name: True for name in player_names}
    
    # Create the crew instance
    clue_crew = ClueGameCrew()
    
    # Get agent instances - only for selected players
    moderator = clue_crew.game_moderator()
    all_agents = {
        "Scarlet": clue_crew.player_scarlet,
        "Mustard": clue_crew.player_mustard,
        "Green": clue_crew.player_green,
        "Peacock": clue_crew.player_peacock,
        "Plum": clue_crew.player_plum,
        "White": clue_crew.player_white,
    }
    # Only instantiate agents for players in this game
    player_agents = {name: all_agents[name]() for name in player_names}
    
    # Announce game start
    print("\n📣 MODERATOR ANNOUNCEMENT:")
    print("-" * 40)
    
    start_crew = create_moderator_announcement_crew(
        moderator,
        "start",
        players=[f"{p.name} ({p.character.value})" for p in game_state.players]
    )
    try:
        retry_with_backoff(start_crew.kickoff)
    except Exception as e:
        sys.stdout.write(f"\n⚠️ Could not announce game start: {e}\n")
        sys.stdout.flush()
    
    print("\n" + "=" * 60)
    print("🎮 GAME BEGINS!")
    print("=" * 60)
    
    # Print initial game state for debugging
    print("\n📋 Initial Setup:")
    print(f"Solution (hidden): {game_state.solution['suspect'].name}, "
          f"{game_state.solution['weapon'].name}, "
          f"{game_state.solution['room'].name}")
    print()
    
    for player in game_state.players:
        print(f"{player.name} ({player.character.value}):")
        if player.current_room and not player.in_hallway:
            print(f"  Location: {player.current_room.value}")
        else:
            start_pos = STARTING_POSITION_NAMES.get(player.character, "Hallway")
            print(f"  Location: START - {start_pos}")
        print(f"  Cards: {[c.name for c in player.cards]}")
    print()
    
    # Main game loop
    turn_count = 0
    while not game_state.game_over and turn_count < max_turns:
        current_player = game_state.get_current_player()
        
        if not current_player.is_active:
            game_state.next_turn()
            continue
        
        turn_count += 1
        
        sys.stdout.write("\n" + "=" * 50 + "\n")
        sys.stdout.write(f"🎲 TURN {turn_count}: {current_player.name} ({current_player.character.value})\n")
        sys.stdout.write("=" * 50 + "\n")
        sys.stdout.flush()
        
        # Get the corresponding agent
        player_agent = player_agents[current_player.name]
        
        # Check if this is the player's first turn (needs notebook initialization)
        is_first_turn = players_first_turn.get(current_player.name, False)
        
        # Create and run the player's turn crew
        turn_crew = create_player_turn_crew(
            current_player.name,
            player_agent,
            moderator,
            is_first_turn=is_first_turn
        )
        
        # Mark that this player has had their first turn
        players_first_turn[current_player.name] = False
        
        try:
            result = retry_with_backoff(turn_crew.kickoff)
            # Display succinct result
            sys.stdout.write(f"\n📝 {current_player.name}'s Turn Summary:\n")
            sys.stdout.write("-" * 40 + "\n")
            sys.stdout.write(str(result.raw if hasattr(result, 'raw') else result) + "\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stdout.write(f"\n❌ Error during {current_player.name}'s turn: {e}\n")
            sys.stdout.flush()
        
        # Check if game ended during this turn
        if game_state.game_over:
            break
        
        # Add delay between turns to avoid API rate limiting
        delay = random.randint(15, 30)
        sys.stdout.write(f"\n⏳ Waiting {delay} seconds before next turn...\n")
        sys.stdout.flush()
        time.sleep(delay)
        
        # Move to next player
        game_state.next_turn()
    
    # Announce game end
    print("\n" + "=" * 60)
    print("🏁 GAME OVER!")
    print("=" * 60)
    
    end_crew = create_moderator_announcement_crew(
        moderator,
        "end",
        winner=game_state.winner or "No one (draw)",
        suspect=game_state.solution["suspect"].name,
        weapon=game_state.solution["weapon"].name,
        room=game_state.solution["room"].name,
        total_turns=turn_count,
    )
    try:
        retry_with_backoff(end_crew.kickoff)
    except Exception as e:
        sys.stdout.write(f"\n⚠️ Could not announce game end: {e}\n")
        sys.stdout.flush()
    
    # Print final results
    print("\n📊 FINAL RESULTS:")
    print("-" * 40)
    print(f"Winner: {game_state.winner or 'No winner (max turns reached)'}")
    print(f"Total Turns: {turn_count}")
    print(f"Solution: {game_state.solution['suspect'].name} with the "
          f"{game_state.solution['weapon'].name} in the "
          f"{game_state.solution['room'].name}")
    
    return game_state


def run_single_turn_demo():
    """
    Run a single turn demo to test the system.
    """
    print("\n" + "=" * 60)
    print("🧪 SINGLE TURN DEMO")
    print("=" * 60 + "\n")
    
    # Initialize game
    game_state = reset_game_state()
    player_names = ["Scarlet", "Mustard", "Green", "Peacock"]
    game_state.setup_game(player_names)
    
    # Create crew and get first player's agent
    clue_crew = ClueGameCrew()
    first_player = game_state.get_current_player()
    player_agent = clue_crew.player_scarlet()
    
    print(f"Testing turn for: {first_player.name}")
    print(f"Cards: {[c.name for c in first_player.cards]}")
    print(f"Location: {first_player.current_room.value}")
    print()
    
    # Run single turn
    turn_crew = create_player_turn_crew(
        first_player.name,
        player_agent,
        clue_crew.game_moderator()
    )
    
    result = turn_crew.kickoff()
    print(f"\n📝 Result:\n{result}")


def main():
    """Main entry point."""
    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        print("❌ Error: GOOGLE_API_KEY environment variable not set.")
        print("Please create a .env file with your Google API key:")
        print("  GOOGLE_API_KEY=your-key-here")
        print("Get your API key at: https://aistudio.google.com/apikey")
        sys.exit(1)
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "demo":
            run_single_turn_demo()
        elif sys.argv[1] == "game":
            num_players = int(sys.argv[2]) if len(sys.argv) > 2 else 6
            run_game(num_players)
        else:
            print("Usage: python -m clue_game.main [demo|game [num_players]]")
            print("  num_players: 3-6 (default: 6)")
    else:
        # Default: run full game with 6 players
        run_game()


if __name__ == "__main__":
    main()
