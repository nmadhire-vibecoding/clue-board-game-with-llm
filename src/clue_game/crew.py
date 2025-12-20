"""
Clue Game Crew - Multi-Agent Clue Board Game
This module defines the CrewAI crew for playing Clue.
"""

from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List

from clue_game.tools import (
    # Game action tools (official Clue rules)
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
    # Detective Notebook tools (deterministic tracking - CRUCIAL for effective play)
    initialize_notebook,
    mark_player_has_card,
    mark_player_not_has_card,
    record_suggestion_in_notebook,
    get_unknown_cards,
    get_possible_solution,
    view_notebook_grid,
    get_notebook_suggestion_history,
    get_strategic_suggestion,
    get_event_log,
)


# Player tools - all tools a player needs to play
# The NOTEBOOK TOOLS are crucial - they prevent LLM "forgetting" by maintaining
# a deterministic grid of card ownership
PLAYER_TOOLS = [
    # Notebook tools (USE THESE for tracking - don't rely on memory!)
    initialize_notebook,          # Call at start of first turn
    get_unknown_cards,            # What cards are still unknown?
    get_possible_solution,        # Can I make an accusation?
    view_notebook_grid,           # Full deduction grid
    get_strategic_suggestion,     # What should I suggest?
    record_suggestion_in_notebook,  # Record any suggestion made
    mark_player_has_card,         # Mark when shown a card
    mark_player_not_has_card,     # Mark when someone passes
    get_event_log,                # Full history of deductions
    # Game action tools (official Clue rules)
    get_my_cards,
    get_current_location,
    roll_dice,                    # Roll dice for movement
    get_available_moves,
    move_to_room,
    make_suggestion,
    make_accusation,
    get_valid_options,
]

# Moderator tools - only needs to check game status
MODERATOR_TOOLS = [
    get_game_status,
    get_suggestion_history,
    get_valid_options,
]


@CrewBase
class ClueGameCrew:
    """Clue Board Game Crew with 6 players and 1 moderator."""
    
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"
    
    agents: List[BaseAgent]
    tasks: List[Task]
    
    # ==================== AGENTS ====================
    
    @agent
    def game_moderator(self) -> Agent:
        """The impartial game moderator."""
        return Agent(
            config=self.agents_config["game_moderator"],  # type: ignore[index]
            tools=MODERATOR_TOOLS,
            verbose=False,
        )
    
    @agent
    def player_scarlet(self) -> Agent:
        """Miss Scarlet - The Cunning Detective."""
        return Agent(
            config=self.agents_config["player_scarlet"],  # type: ignore[index]
            tools=PLAYER_TOOLS,
            verbose=False,
        )
    
    @agent
    def player_mustard(self) -> Agent:
        """Colonel Mustard - The Bold Investigator."""
        return Agent(
            config=self.agents_config["player_mustard"],  # type: ignore[index]
            tools=PLAYER_TOOLS,
            verbose=False,
        )
    
    @agent
    def player_green(self) -> Agent:
        """Mr. Green - The Analytical Mind."""
        return Agent(
            config=self.agents_config["player_green"],  # type: ignore[index]
            tools=PLAYER_TOOLS,
            verbose=False,
        )
    
    @agent
    def player_peacock(self) -> Agent:
        """Mrs. Peacock - The Intuitive Sleuth."""
        return Agent(
            config=self.agents_config["player_peacock"],  # type: ignore[index]
            tools=PLAYER_TOOLS,
            verbose=False,
        )
    
    @agent
    def player_plum(self) -> Agent:
        """Professor Plum - The Academic Investigator."""
        return Agent(
            config=self.agents_config["player_plum"],  # type: ignore[index]
            tools=PLAYER_TOOLS,
            verbose=False,
        )
    
    @agent
    def player_white(self) -> Agent:
        """Mrs. White - The Observant Insider."""
        return Agent(
            config=self.agents_config["player_white"],  # type: ignore[index]
            tools=PLAYER_TOOLS,
            verbose=False,
        )
    
    # ==================== TASKS ====================
    
    @task
    def announce_game_start_task(self) -> Task:
        """Task for moderator to announce game start."""
        return Task(
            config=self.tasks_config["announce_game_start_task"],  # type: ignore[index]
        )
    
    @task
    def announce_turn_task(self) -> Task:
        """Task for moderator to announce current turn."""
        return Task(
            config=self.tasks_config["announce_turn_task"],  # type: ignore[index]
        )
    
    @task
    def player_turn_task(self) -> Task:
        """Task for a player to take their turn."""
        return Task(
            config=self.tasks_config["player_turn_task"],  # type: ignore[index]
        )
    
    @task
    def summarize_suggestion_task(self) -> Task:
        """Task for moderator to summarize a suggestion."""
        return Task(
            config=self.tasks_config["summarize_suggestion_task"],  # type: ignore[index]
        )
    
    @task
    def announce_game_end_task(self) -> Task:
        """Task for moderator to announce game end."""
        return Task(
            config=self.tasks_config["announce_game_end_task"],  # type: ignore[index]
        )
    
    # ==================== CREW ====================
    
    @crew
    def crew(self) -> Crew:
        """Creates the Clue Game crew."""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )


def create_player_turn_crew(player_name: str, player_agent: Agent, moderator: Agent, is_first_turn: bool = False) -> Crew:
    """
    Create a mini-crew for a single player's turn.
    
    Args:
        player_name: The name of the player taking the turn
        player_agent: The agent for this player
        moderator: The moderator agent
        is_first_turn: Whether this is the player's first turn (needs notebook init)
    
    Returns:
        A crew configured for this player's turn
    """
    
    init_instruction = ""
    if is_first_turn:
        init_instruction = """
        ⚡ FIRST TURN SETUP:
        1. Call "Initialize My Notebook" with your player name to set up tracking
           This records your cards and prepares the deduction grid.
        """
    
    turn_task = Task(
        description=f"""
        It's your turn in the Clue game! You are {player_name}.
        
        Your objective is to solve the mystery by figuring out:
        - WHO committed the murder (which suspect)
        - WHAT weapon was used  
        - WHERE it happened (which room)
        
        {init_instruction}
        
        ═══════════════════════════════════════════════════════════════
        CRITICAL: USE YOUR DETECTIVE NOTEBOOK TOOLS!
        ═══════════════════════════════════════════════════════════════
        
        Your notebook maintains a DETERMINISTIC grid of card ownership.
        DO NOT try to remember cards from conversation - USE THE NOTEBOOK!
        
        NOTEBOOK TOOLS (use these, not your memory!):
        • "Get Unknown Cards" - See what cards are still unknown
        • "Get Possible Solution" - Check if you can make an accusation
        • "Get Strategic Suggestion" - Get recommended suggestion
        • "View Notebook Grid" - See your full deduction grid
        • "Record Suggestion In Notebook" - After ANY suggestion, record it!
        • "Mark Player Has Card" - When shown a card
        
        ═══════════════════════════════════════════════════════════════
        
        YOUR TURN STEPS:
        1. Check "Get Possible Solution" - Can you accuse yet?
        2. If not ready to accuse, check "Get Unknown Cards"
        3. Use "Get Strategic Suggestion" with your current room
        4. Move to a strategic room using "Move To Room"
        5. Make a suggestion using "Make Suggestion"
        6. IMPORTANT: Record the result with "Record Suggestion In Notebook"
        7. Check "Get Possible Solution" again after recording
        8. Only use "Make Accusation" if solution is confirmed!
        
        IMPORTANT: Always pass your player name "{player_name}" to ALL tools.
        
        ⚠️ ACCUSATION WARNING: Wrong accusation = ELIMINATED!
        Only accuse when "Get Possible Solution" shows all three confirmed!
        
        Take your turn now. Think step by step and USE YOUR NOTEBOOK.
        """,
        expected_output="""
        A brief summary in this exact format:
        LOCATION: [room you are in]
        ACTION: [moved to X / stayed in X]
        SUGGESTION: [Suspect, Weapon, Room] or "None"
        RESULT: [Card shown by Player / No one could disprove / None]
        STATUS: [X suspects, Y weapons, Z rooms remaining]
        """,
        agent=player_agent,
    )
    
    return Crew(
        agents=[player_agent],
        tasks=[turn_task],
        process=Process.sequential,
        verbose=False,
        tracing=False,
    )


def create_moderator_announcement_crew(moderator: Agent, announcement_type: str, **kwargs) -> Crew:
    """
    Create a mini-crew for moderator announcements.
    
    Args:
        moderator: The moderator agent
        announcement_type: Type of announcement ('start', 'turn', 'suggestion', 'end')
        **kwargs: Additional context for the announcement
    
    Returns:
        A crew for the moderator announcement
    """
    if announcement_type == "start":
        description = f"""
        Announce the start of the Clue game!
        
        Players: {kwargs.get('players', [])}
        
        Provide:
        1. A dramatic welcome to the mystery
        2. Introduction of all players and their characters
        3. Reminder of the objective (find suspect, weapon, and room)
        4. Current game state with player locations
        """
    elif announcement_type == "turn":
        description = f"""
        Announce whose turn it is.
        
        Current player: {kwargs.get('current_player', 'Unknown')}
        Turn number: {kwargs.get('turn_number', 1)}
        
        Provide a brief announcement of the current turn.
        """
    elif announcement_type == "end":
        description = f"""
        Announce the end of the game!
        
        Winner: {kwargs.get('winner', 'Unknown')}
        Solution: {kwargs.get('suspect', '?')} with the {kwargs.get('weapon', '?')} in the {kwargs.get('room', '?')}
        Total turns: {kwargs.get('total_turns', 0)}
        
        Provide a dramatic conclusion and reveal the solution!
        """
    else:
        description = "Provide a game status update."
    
    announcement_task = Task(
        description=description,
        expected_output="A clear and engaging announcement for the players.",
        agent=moderator,
    )
    
    return Crew(
        agents=[moderator],
        tasks=[announcement_task],
        process=Process.sequential,
        verbose=False,
        tracing=False,
    )
