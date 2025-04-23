import gamelib
import random
import math
import copy
import json
from sys import maxsize
from gamelib import GameState, GameMap, GameUnit
from threshold import ThresholdEstimator

# Shorthand constants set in on_game_start
WALL = SUPPORT = TURRET = SCOUT = DEMOLISHER = INTERCEPTOR = None
MP = SP = None


class AlgoStrategy(gamelib.AlgoCore):
    """
    A clearer, more modular single-file version of the starter algo.
    Methods are grouped by responsibility: lifecycle, offense, defense,
    support, simulation, and utilities.
    """
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write(f"Random seed: {seed}")

        self.estimator = ThresholdEstimator(100, 8)
        self.opp_threshold = None

        # State
        self.support_locations = []
        self.scored_on = []
        self.sectors = []
        self.start_points = []
        self.notch_points = []
        self.funnelmode = False

        # turn number
        self.last_turn = 0

        # RESORT SECOND
        self.resort = False

        # rim
        self.left_rim = []
        self.rit_rim = []

        # walls for RESORT SECOND
        self.wallresnd = []
        self.wallresnd_bp = []
        self.wallresnd_bp_l = []
        self.wallresnd_bp_r = []

        # walls for resort third
        self.wallresrd = []

        # build a 28×28 boolean mask for valid support positions
        self.support_mask = []

        # resort side
        self.resort_side = None

        # Monitoring data
        self.monitoring_history = []  # List to store monitoring data per turn
        self.current_resources = {'MP': 0, 'SP': 0}  # Current resources
        self.current_units = {}  # Current units and their states

        self.wall_integrity = None
    # ------------------------
    # Lifecycle hooks
    # ------------------------
    def on_game_start(self, config):
        """Initialize config, unit shorthands, sectors & start points."""
        self.config = config
        ui = config["unitInformation"]
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR = (
            ui[0]["shorthand"],
            ui[1]["shorthand"],
            ui[2]["shorthand"],
            ui[3]["shorthand"],
            ui[4]["shorthand"],
            ui[5]["shorthand"],
        )
        MP, SP = 1, 0

        # Build 4 triangular sectors
        self.sectors = [[], [], [], []]
        for c in range(28):
            group = c // 7
            rows = (
                range(14 - c - 1, 14) if c < 14
                else range(c - 14, 14)
            )
            for r in rows:
                self.sectors[group].append([c, r])

        # Four spawn points for scouts
        # self.start_points = [[3,12], [6,10], [9,10], [12,10], [15,10], [18,10], [21,10], [24,12]]
        # self.start_points = [[3,12], [4,12], [5,11], [6,10], [9,10], [12,10], [15,10], [18,10], [21,10], [23,11], [24,12]]
        self.start_points = [[3,11], [4,11], [5,11], [6,11], [7,11], [8,11], [9,11], [10,11], [11,11], [12,11], [16,11], [17,11], [18,11], [19,11], [20,11], [21,11], [22,11], [23,11], [24,11]]
        self.turrets_start_points = [[12,10], [16,10], [10,10], [8,10], [18,10], [20,10]]
        self.interceptors_start_spawn_loc = [[8,5], [19,5]]
        self.notch_points = [[13,11],[14,10],[15,11]]

        # vertical wall
        self.vertical_wall_start_points = [[14,9], [14,8], [14,7], [14,6]]

        # rim
        self.left_rim = [[13 - i, i] for i in range(14)]
        self.rit_rim = [[27 - (13 - i), i] for i in range(14)]

        # walls for RESORT SECOND
        self.wallresnd = [[3,13], [4,13], [5,12], [6,11], [7,11], [8,11], [9,11], [10,11], [11,11], [12,11], [13,11], [14,11], [15,11], [16,11], [17,11], [18,11], [19,11], [20,11], [21,11], [22,11], [23,12], [24,13]]

        # self.wallresnd_bp = [[26,12], [25,12], [25,11], [24,11], [24,10], [23,10], [23,9], [22,9]]
        # self.wallresnd_bp_l = [
        #     [1,12], [2,12], [2,11], [3,11],
        #     [3,10], [4,10], [4,9],  [5,9]
        # ]
        # self.wallresnd_bp_r = [
        #     [26,12], [25,12], [25,11], [24,11],
        #     [24,10], [23,10], [23,9],  [22,9]
        # ]

        self.wallresnd_bp_l = [
            [3,12], [3,11], [4,11], [4,10], [5,10], [5,9],
            [2, 12], [2, 11], [3, 10], [4, 9], [1,12], [6,9]
        ]
        self.wallresnd_bp_r = [
            [24,12], [24,11], [23,11], [23,10], [22,10], [22,9],
            [25,12], [25,11], [24, 10], [23,9], [26,12], [21,9],
        ]

        # walls for resort third
        self.wallresrd = [[6,9], [7,9], [8,9], [9,9], [10,9], [11,9], [12,9], [13,9], [14,9], [15,9], [16,9], [17,9], [18,9], [19,9], [20,9], [21,9]]

        # build a 28×28 boolean mask for valid support positions
        self.support_mask = [[False]*28 for _ in range(28)]
        # mask from right_rim to left_rim
        for (lx, ly), (rx, ry) in zip(self.left_rim, self.rit_rim):
            y = ly  # same as ry
            x_min = min(lx, rx) + 2
            x_max = max(lx, rx) + 2
            if x_min > x_max:
                for x in range(x_min, x_max + 1):
                    self.support_mask[x][y] = True

    def on_turn(self, turn_state):
        """Main turn entry: offense, defense, support."""
        state = GameState(self.config, turn_state)
        gamelib.debug_write(f"Turn {state.turn_number}")
        state.suppress_warnings(True)

        # Update turn number
        self.last_turn = state.turn_number


        # # Monitor resources and unit health
        # self._monitor_resources_and_units(state)

        # --- Check for last resort ---
        if state.turn_number >= 4:
            self.resort = True
            self.wall_integrity = self.wall_integrity_check(state)

        # # --- Interceptors defense ---
        # if state.turn_number <= 2 or (self.resort and (not self.wall_integrity_check(state))):
        #     _ = self._interceptors_defense(state)

        # --- Offense ---
        if state.turn_number <= 2:
            self._interceptors_defense(state)
        else:
            if state.turn_number == 3:
                self._build_far_side_walls(state, upd=True)
                self._initial_defense(state, turrets=True)
                self._build_vertical_wall(state)
            else:
                self._replace_defense(state)

            if state.get_resources(1)[0] < 10 and (self.isfunnel is None):
                self.isfunnel = self.is_funnel(state)

            self.estimator.observe(state.get_resources(1)[1])
            if self.estimator.confidence_width() <= 3:
                self.opp_threshold = self.estimator.threshold()
            else:
                self.opp_threshold = None

            # # --- Defense improvements ---
            max_improvements = 20
            for _ in range(max_improvements):
                if state.get_resource(SP) < 2:
                    break
                if not self._try_improve_defense(state):
                    break


            if self.resort_side is None:
                self.resort_side = self.evaluate_enemy_defense(state)
                gamelib.debug_write(f"Resort side: {self.resort_side}")

            #if self.funnelmode:
            #    self.funnel_strategy()




        # --- Support management ---
        attack, loc, num = self.should_attack(state)
        self._manage_support(state, loc if 'loc' in locals() else None)

        state.submit_turn()

    def on_action_frame(self, turn_str):
        """Stamp breaches with turn so we know where+when they happen."""
        data = json.loads(turn_str)
        for breach in data.get("events", {}).get("breach", []):
            loc, owner = tuple(breach[0]), breach[4]
            if owner != 1:
                # record both location and the turn number
                self.scored_on.append({
                    "loc": loc,
                    "turn": self.last_turn  # we'll set last_turn in on_turn
                })
                gamelib.debug_write(f"Opponent breached at {loc} on turn {self.last_turn}")

    # ------------------------
    # Initial defense
    # ------------------------
    def _initial_defense(self, state: GameState, turrets: bool):
        """Basic turret + wall setup on turn 0."""
        # state.attempt_upgrade(self.start_points) # No upgrade of turrets based on the current rule
        # walls = [[x, y + 1] for x, y in self.start_points]
        state.attempt_spawn(WALL, self.start_points)
        state.attempt_spawn(WALL, self.notch_points)
        if turrets:
            state.attempt_spawn(TURRET, self.turrets_start_points)
        for loc in self.turrets_start_points:
            loc = [loc[0], loc[1] + 1]
            unit = state.contains_stationary_unit(loc)
            if unit and unit.unit_type == WALL and not unit.upgraded:
                state.attempt_upgrade(loc)

    # ------------------------
    # Defense improvement
    # ------------------------
    def _try_improve_defense(self, state: GameState) -> bool:
        """Parse and upgrade/build in the weakest sector."""
        defenses = self.parse_defenses(state)
        sector = self.defense_heuristic(defenses)
        return self.improve_defense(state, sector, defenses[sector])

    def parse_defenses(self, state: GameState):
        """Return per-sector [[weights], [counts]] for walls & turrets."""
        results = []
        for sector in self.sectors:
            w_counts = [0,0,0,0]  # [wall, wall+, turret, turret+]
            n_counts = [0,0,0,0]
            for loc in sector:
                unit = state.contains_stationary_unit(loc)
                if not unit:
                    continue
                idx = {"W":0,"W+":1,"T":2,"T+":3}[(
                    "W+" if unit.unit_type==WALL and unit.upgraded else
                    "W"  if unit.unit_type==WALL else
                    "T+" if unit.unit_type==TURRET and unit.upgraded else
                    "T"
                )]
                w_counts[idx] += unit.health / unit.max_health
                n_counts[idx] += 1
            results.append([w_counts, n_counts])
        return results

    def defense_heuristic(self, defenses):
        """Choose sector with lowest weighted strength."""
        best_i, best_v = 0, float("inf")
        for i, (w, _) in enumerate(defenses):
            """
            Weights:
            - reinforced turrets: 8 (original 12)
            - reinforced walls:   3 (original 5)
            - turrets:            6 (original 6)
            - walls:             1 (original 1)
            """
            val = w[3]*8 + w[2]*6 + w[1]*3 + w[0]
            if w[1] < 1:  # few upgraded walls → prioritize
                val *= 0.5
            if val < best_v:
                best_v, best_i = val, i
        return best_i

    def evaluate_enemy_defense(self, state: GameState) -> str:
        """
        Scan all stationary enemy WALLs and TURRETs (upgraded or not) on the opponent's side (y >= 14),
        sum a weighted health total on left (x < 14) vs. right (x >= 14),
        and return the side with less weighted defense.
        """
        # Tuning: weight per point of health for each unit type
        WEIGHTS = {
            (WALL,   False): 1.0,  # basic wall
            (WALL,   True):  1.5,  # upgraded wall
            (TURRET, False): 2.0,  # basic turret
            (TURRET, True):  3.0   # upgraded turret
        }
        totals = {'l': 0.0, 'r': 0.0}

        for x in range(28):
            for y in range(14, 28):
                loc = [x, y]
                cell = state.game_map[loc] or []    # treat None as empty
                for unit in cell:
                    # skip your own units
                    if unit.player_index == 0:
                        continue
                    weight = WEIGHTS.get((unit.unit_type, unit.upgraded))
                    if weight is None:
                        continue
                    side = 'l' if x < 14 else 'r'
                    totals[side] += weight

        gamelib.debug_write(
            f"Enemy defense weighted L={totals['l']:.1f}, R={totals['r']:.1f}"
        )
        # open the weaker side
        return 'l' if totals['l'] < totals['r'] else 'r'

    def _replace_defense(self, state: GameState):
        turn = state.turn_number
        starts = self.start_points
        starts_turrets = self.turrets_start_points

        wall_coordinates = [
            [0,13], [1,12], [2,11],
             [25,11], [26,12], [27,13]
        ]

        for loc in wall_coordinates:
            unit = state.contains_stationary_unit(loc)
            if not unit:
                state.attempt_spawn(WALL, loc)
            elif unit.health < 0.6 * unit.max_health:
                state.attempt_remove(loc)

        for loc in self.notch_points:
            unit = state.contains_stationary_unit(loc)
            if not unit:
                state.attempt_spawn(WALL, loc)
            elif unit.health < 0.6 * unit.max_health:
                state.attempt_remove(loc)

        for loc in starts:
            unit = state.contains_stationary_unit(loc)
            if not unit:
                state.attempt_spawn(WALL, loc)
            elif unit.health < 0.6 * unit.max_health:
                state.attempt_remove(loc)

        for loc in self.vertical_wall_start_points[:2]:
            unit = state.contains_stationary_unit(loc)
            if not unit:
                state.attempt_spawn(WALL, loc)
            elif unit.health < 0.4 * unit.max_health:
                state.attempt_remove(loc)

    def improve_defense(self, state: GameState, sector: int, defense) -> bool:
        """
        Improve defenses in one sector or, if in last-resort mode, rebuild rings,
        fix the initial line, upgrade walls, and place symmetric mid defenses.
        Returns True if an action was performed this turn.
        """
        turn = state.turn_number
        starts = self.start_points
        starts_turrets = self.turrets_start_points

        wall_coordinates = [
            [0,13], [1,12], [2,11],
             [25,11], [26,12], [27,13]
        ]

        #wall_coordinates.extend([[13,11], [15,11]])

        #notch_coordinates = [[13,11], [15,11], [14,10]]

        ## wall points
        for loc in wall_coordinates:
            #unit = state.contains_stationary_unit(loc)
            #if unit and unit.unit_type == WALL and unit.health < 0.6 * unit.max_health and not unit.pending_removal:
            #    state.attempt_remove(loc)
            #if state.can_spawn(WALL, loc):
            #    state.attempt_spawn(WALL, loc)
            #    return True
            #if unit and unit.unit_type == WALL and not unit.upgraded:
            #    state.attempt_upgrade(loc)
            #    return True
            unit = state.contains_stationary_unit(loc)
            if not unit and state.can_spawn(WALL, loc):
                state.attempt_spawn(WALL, loc)
                return True

            # if unit.unit_type == WALL and unit.health < 0.6 * unit.max_health:
            #     state.attempt_remove(loc)
            #     return True
            elif unit.unit_type == WALL and not unit.upgraded:
                state.attempt_upgrade(loc)
                return True

        ## notch points
        for loc in self.notch_points:
            unit = state.contains_stationary_unit(loc)
            if not unit and state.can_spawn(WALL, loc):
                state.attempt_spawn(WALL, loc)
                return True

            #if unit.unit_type == WALL and unit.health < 0.6 * unit.max_health:
            #    state.attempt_remove(loc)
            #    return True
            elif unit and unit.unit_type == WALL and not unit.upgraded:
                state.attempt_upgrade(loc)
                return True


        # Add vertical wall points to wall_coordinates
        for loc in self.vertical_wall_start_points[:2]:
            unit = state.contains_stationary_unit(loc)
            if not unit and state.can_spawn(WALL, loc):
                state.attempt_spawn(WALL, loc)
                return True

            #if unit.unit_type == WALL and unit.health < 0.6 * unit.max_health:
            #    state.attempt_remove(loc)
            #    return True

        # 2) INITIAL LINE: walls then turrets
        for loc in starts:
            unit = state.contains_stationary_unit(loc)
            if not unit and state.can_spawn(WALL, loc):
                state.attempt_spawn(WALL, loc)
                return True

            #if unit.unit_type == WALL and unit.health < 0.6 * unit.max_health:
            #    state.attempt_remove(loc)
            #    return True
            elif unit and unit.unit_type == WALL and not unit.upgraded:
                state.attempt_upgrade(loc)
                return True
        for x, y in starts_turrets:
            turret = (x, y)
            if not state.contains_stationary_unit(turret) and state.can_spawn(TURRET, turret):
                state.attempt_spawn(TURRET, turret)
                return True

        # 3) PRIORITY UPGRADES: upgrade units based on damage history
        priority_locations = self._get_priority_upgrade_locations(state)
        priority_locations = [loc for loc in priority_locations if loc in self.start_points]
        for loc in priority_locations:
            unit = state.contains_stationary_unit(loc)
            if unit and not unit.upgraded and state.can_spawn(unit.unit_type, loc):
                state.attempt_upgrade(loc)
                return True

        # # 4) SYMMETRIC MID-DEFENSE: walls at y=11, turrets at y=10
        # left_x = range(7, 12)
        # right_x = range(22, 17, -1)
        # for lx, rx in zip(left_x, right_x):
        #     for x in (lx, rx):
        #         wall = (x, 11)
        #         turret = (x, 10)
        #         w = state.contains_stationary_unit(wall)
        #         t = state.contains_stationary_unit(turret)
        #         # spawn or upgrade wall
        #         if not w and state.can_spawn(WALL, wall):
        #             state.attempt_spawn(WALL, wall)
        #             state.attempt_upgrade(wall)
        #             return True
        #         if w and w.unit_type == WALL and not w.upgraded:
        #             state.attempt_upgrade(wall)
        #             return True
        #         # spawn turret
        #         if not t and w and state.can_spawn(TURRET, turret):
        #             state.attempt_spawn(TURRET, turret)
        #             return True

        # nothing to do
        return False


    def rim_evaluation(state: GameState) -> int:
        """
        Evaluates if there is a rim defense with at most 3 consecutive holes at one end.

        Args:
            state: The current game state

        Returns:
            1 if there's a rim with at most 3 consecutive holes in the right, -1 if left , 0 otherwise
        """
        holes = []

        # Check for holes along the rim
        for x in range(28):
            has_structure = False
            # Check from y=14 onwards in this column
            for y in range(14, 28):
                if state.game_map.in_arena_bounds([x, y]) and state.contains_stationary_unit([x, y]):
                    has_structure = True
                    break

            # If no structure found in this column, it's a hole
            if not has_structure:
                holes.append(x)

        # No holes means perfect rim
        if not holes:
            return 0

        # Too many holes
        if len(holes) > 3:
            return 0

        # Check if holes are consecutive (no gaps)
        holes.sort()
        for i in range(1, len(holes)):
            if holes[i] != holes[i-1] + 1:
                return 0  # Non-consecutive holes

        # Check if holes are at left end (starting at x=0)
        if holes[0] == 0:
            return -1

        # Check if holes are at right end (ending at x=27)
        if holes[-1] == 27:
            return 1

        return 0

    def is_funnel(self, state: GameState) -> bool:
        """
        Checks if the opponent is employing a funnel defense strategy by seeing
        if all paths converge to a narrow range when they reach y=14.

        Args:
            state: The current game state

        Returns:
            True if opponent has a funnel defense, False otherwise
        """
        # Use the specified starting points
        start_points = [
            [6,20], [7,21], [8,22], [9,23], [10,24], [11,25], [12,26],
            [15,26], [16,25], [17,24], [18,23], [19,22], [20,21], [21,20],
            [22,19], [23,18], [24,17]
        ]

        # Find x-coordinates where paths reach y=14
        rim_x_coords = []

        for start in start_points:
            # Skip points that are not in bounds
            if not state.game_map.in_arena_bounds(start):
                continue

            # Find path to edge
            path = state.find_path_to_edge(start)

            # Skip if no path found
            if not path:
                continue

            # Find the point in the path where y=14
            for point in path:
                if point[1] == 14:
                    rim_x_coords.append(point[0])
                    break

        # If we couldn't find enough paths, return False
        if len(rim_x_coords) < 5:  # Need at least 5 valid paths for meaningful analysis
            return False

        # Check if all paths converge to a narrow exit region
        funnel_width = max(rim_x_coords) - min(rim_x_coords)

        # A funnel defense has all paths converging to a narrow range (4 units or less)
        return funnel_width <= 4


    def rebuild_far_side_walls(self, state: GameState):
        wall_coordinates = [
            [0,13], [1,12], [2,11],
            [25,11], [26,12], [27,13]
        ]

        for loc in wall_coordinates:
            unit = state.contains_stationary_unit(loc)
            # First check: Remove damaged walls
            if unit and unit.unit_type == WALL and unit.health <= 50:
                state.attempt_remove(loc)
                unit = state.contains_stationary_unit(loc)  # Update unit after removal

            # Second check: Try to spawn new wall
            if state.can_spawn(WALL, loc):
                state.attempt_spawn(WALL, loc)
                unit = state.contains_stationary_unit(loc)  # Update unit after spawn

            # Third check: Try to upgrade wall
            if unit and unit.unit_type == WALL and not unit.upgraded:
                state.attempt_upgrade(loc)


    def try_build_upgraded_turret(self, state: GameState, seq):
        if state.get_resource(MP) < 8:
            return False
        for loc in seq:
            if not state.contains_stationary_unit(loc):
                if state.attempt_spawn(TURRET, loc):
                    return state.attempt_upgrade(loc) > 0
        return False

    def try_upgrade(self, state: GameState, loc):
        unit = state.contains_stationary_unit(loc)
        if not unit:
            return False
        if unit.unit_type == TURRET and unit.health >= 0.75 * unit.max_health:
            return state.attempt_upgrade(loc) > 0
        if unit.unit_type == WALL:
            return state.attempt_upgrade(loc) > 0
        return False

    def _spawn_and_upgrade_wall(self, state, seq):
        for loc in seq:
            pos = [loc[0], 13]
            if not state.contains_stationary_unit(pos):
                state.attempt_spawn(WALL, pos)
                return state.attempt_upgrade(pos) > 0
        return False

    def _spawn_wall(self, state, seq):
        for loc in seq:
            pos = [loc[0], 13]
            if not state.contains_stationary_unit(pos):
                return state.attempt_spawn(WALL, pos)
        return False

    def wall_integrity_check(self, state: GameState) -> bool:
        """Check if the walls are still standing."""
        nb_walls = 0
        for loc in self.wallresnd[:6]:
            if state.contains_stationary_unit(loc):
                nb_walls += 1
        if nb_walls < nb_walls/5:
            return False
        return True

    # ------------------------
    # Interoceptors defense
    # ------------------------
    def _interceptors_defense(self, state: GameState):
        # send interceptors at [5,8] and [22,8]
        interoceptor_cost = state.type_cost(INTERCEPTOR)[1]
        if state.get_resource(MP) >= interoceptor_cost * 2:
            if state.can_spawn(INTERCEPTOR, self.interceptors_start_spawn_loc[0]):
                state.attempt_spawn(INTERCEPTOR, self.interceptors_start_spawn_loc[0])
            if state.can_spawn(INTERCEPTOR, self.interceptors_start_spawn_loc[1]):
                state.attempt_spawn(INTERCEPTOR, [22, 8])
            return True
        return False

    # ------------------------
    # Support management
    # ------------------------
    def _manage_support(self, state: GameState, scout_loc):
        t = state.turn_number
        if scout_loc and t >= 5:
            path = state.find_path_to_edge(scout_loc)
            rng = self.config["unitInformation"][1]["shieldRange"]
            # prune
            kept = []
            for loc in self.support_locations:
                unit = state.contains_stationary_unit(loc)
                if unit and any(self.manhattan(loc, p) <= rng for p in path):
                    kept.append(loc)
                else:
                    state.attempt_remove(loc)
            self.support_locations = kept
            # place new
            for loc in state.game_map.get_locations_in_range(scout_loc, rng):
                if loc not in kept and loc not in path and state.can_spawn(SUPPORT, loc):
                    if state.attempt_spawn(SUPPORT, loc):
                        self.support_locations.append(loc)
                        state.attempt_upgrade(loc)
        # upgrade all shields
        for loc in list(self.support_locations):
            state.attempt_upgrade(loc)

    # ------------------------
    # Far-side walls
    # ------------------------
    def _build_far_side_walls(self, state: GameState, upd: bool = True) -> None:
        """
        Maintain walls along the far edges, removing damaged walls and upgrading all walls.
        """
        # Define wall coordinates
        wall_coordinates = [
            [0,13], [1,12], [2,11],
             [25,11], [26,12], [27,13]
        ]

        # 1) Remove damaged walls
        for loc in wall_coordinates:
            unit = state.contains_stationary_unit(loc)
            if unit and unit.unit_type == WALL and unit.health < 20:
                state.attempt_remove(loc)

        # 2) Build and upgrade walls
        for loc in wall_coordinates:
            if state.can_spawn(WALL, loc):
                state.attempt_spawn(WALL, loc)
            if upd:
                unit = state.contains_stationary_unit(loc)
                if unit and unit.unit_type == WALL and not unit.upgraded:
                    state.attempt_upgrade(loc)


    # ------------------------
    # Vertical wall
    # ------------------------
    def _build_vertical_wall(self, state: GameState):
        for loc in self.vertical_wall_start_points:
            if state.can_spawn(WALL, loc):
                state.attempt_spawn(WALL, loc)

    # ------------------------
    # Offense logic
    # ------------------------
    def resort_offense(self, state: GameState, side: str) -> None:
        """
        Last‑resort offense:
        - spawn required number of INTERCEPTORs at the side‑dependent rim (left or right),
        - then deploy maximum possible SCOUTs with remaining MP at the bottom edge.
        """
        # choose your spawn points based on the weaker side
        if side == 'l':
            int_loc   = [3, 10]   # left interceptor rim
            scout_loc = [14, 0]    # just inside left bottom edge
        else:  # 'r'
            int_loc   = [24, 10]  # right interceptor rim
            scout_loc = [13, 0]   # just inside right bottom edge

        # 1) Get available MP
        mp_available = state.get_resource(MP)

        # 2) Determine MP costs
        _, mp_cost_int   = state.type_cost(INTERCEPTOR)
        mp_cost_int   = int(mp_cost_int)

        # 3) Calculate required interceptors
        turret_coords = self._get_turret_coordinates(side)
        enemy_turrets = self._count_enemy_turrets(state, turret_coords)
        required_interceptors = max(3, enemy_turrets * 2)  # Minimum 3, or 2 per turret

        # 4) Spawn required interceptors at the side rim
        max_int = mp_available // mp_cost_int
        num_int = int(min(required_interceptors, max_int))
        if num_int > 0 and state.can_spawn(INTERCEPTOR, int_loc):
            state.attempt_spawn(INTERCEPTOR, int_loc, num_int)
            mp_available -= num_int * mp_cost_int
            gamelib.debug_write(
                f"Resort offense: spawned {num_int} INTERCEPTOR(s) at {int_loc}")

        # 5) Spend all remaining MP on scouts (1 MP per scout)
        if mp_available > 0 and state.can_spawn(SCOUT, scout_loc):
            state.attempt_spawn(SCOUT, scout_loc, int(mp_available))
            gamelib.debug_write(
                f"Resort offense: spawned {mp_available} SCOUT(s) at {scout_loc}")

    def should_attack(self, state: GameState):
        mp = state.get_resource(MP)
        scouts = int(mp)
        loc, survived = self.full_sim(state, scouts)
        # conditions to go all-in
        if mp >= 8 and state.enemy_health <= 7 and state.enemy_health - survived < -3:
            return True, loc, scouts
        if mp < 15 + state.turn_number // 10 and (survived <= scouts * 0.6 or mp < 8):
            return False, [], 0
        return True, loc, scouts

    def scout_attack(self, state: GameState, loc, num):
        state.attempt_spawn(SCOUT, loc, num)

    # ------------------------
    # Simulation helpers
    # ------------------------
    def full_sim(self, orig_state: GameState, num_scouts: int):
        """
        Simulate num_scouts scouts from all deploy points, return best (loc, survived).
        """
        options = []
        for i in range(13): # change from 14
            for pt in ([i,13-i], [14+i,i]):
                if orig_state.can_spawn(SCOUT, pt):
                    options.append(pt)

        best = (-1, None, None)  # (survived, loc, attackers_set)
        for loc in options:
            state = copy.deepcopy(orig_state)
            survive, _, _, _, _, _, atk = self._simulate_path(state, loc, num_scouts)
            if survive > best[0]:
                best = (survive, loc, atk)

        return best[1], best[0]

    def _simulate_path(self, state, loc, num_scouts):
        """Helper to simulate a single scout path. Returns tuple of metrics + attackers set."""
        temp = copy.deepcopy(state)
        scout_unit = GameUnit(SCOUT, state.config)
        SC_HP, SC_DMG = scout_unit.max_health, scout_unit.damage_f
        sup_info = self.config["unitInformation"][1]
        shield_amt = sup_info.get("shieldAmount", 0)
        base_rng   = sup_info.get("attackRange", 0)

        edge = temp.get_target_edge(loc)
        path = temp.find_path_to_edge(loc)
        dead = 0
        dmg_turret = dmg_wall = dmg_support = dmg_to_scout = 0
        attackers = set()
        cur_hp = SC_HP

        idx = 0
        while idx < len(path):
            pt = path[idx]
            atkers = temp.get_attackers(pt, 0)
            temp.game_map.add_unit(SCOUT, pt)

            # shield buff
            for sup_loc in self.support_locations:
                sup = temp.contains_stationary_unit(sup_loc)
                if sup and sup.unit_type == SUPPORT:
                    rng = base_rng + (1 if sup.upgraded else 0)
                    if self.manhattan(sup_loc, pt) <= rng:
                        cur_hp = min(cur_hp + shield_amt, SC_HP + shield_amt)
                        break

            rem = num_scouts - dead
            # scouts attack structures
            while rem > 0:
                tgt = temp.get_target(temp.game_map[pt][0])
                if not tgt:
                    break
                maxd = rem * SC_DMG
                if tgt.health <= maxd:
                    # record damage by type
                    if tgt.unit_type == TURRET:   dmg_turret += tgt.health
                    elif tgt.unit_type == WALL:    dmg_wall   += tgt.health
                    elif tgt.unit_type == SUPPORT: dmg_support+= tgt.health
                    temp.game_map.remove_unit([tgt.x, tgt.y])
                    path = temp.find_path_to_edge(pt, edge)
                    idx = -1
                    rem -= math.ceil(tgt.health / SC_DMG)
                    break
                else:
                    tgt.health -= maxd
                    if tgt.unit_type == TURRET:   dmg_turret += maxd
                    elif tgt.unit_type == WALL:    dmg_wall   += maxd
                    elif tgt.unit_type == SUPPORT: dmg_support+= maxd
                    break

            temp.game_map.remove_unit(pt)
            # turrets attack scouts
            for atk in atkers:
                attackers.add((atk.x, atk.y))
                dmg_to_scout += min(atk.damage_i, cur_hp)
                cur_hp -= atk.damage_i
                if cur_hp <= 0:
                    dead += 1
                    cur_hp = SC_HP + shield_amt
                    if dead >= num_scouts:
                        break
            if dead >= num_scouts:
                break
            idx += 1

        survived = num_scouts - dead
        if not path or path[-1] not in state.game_map.get_edge_locations(edge):
            survived = 0

        return survived, dmg_to_scout, dmg_turret, dmg_wall, dmg_support, loc, attackers

    # ------------------------
    # Utility sequences
    # ------------------------
    def column_sequence(self, c):
        """Alternating columns around c within its sector block."""
        block = (c // 7) * 7
        rng = range(block + 1, block + 7) if c < 14 else range(block, block + 6)
        seq = [c]
        for i in range(1,7):
            for nc in (c - i, c + i):
                if nc in rng:
                    seq.append(nc)
        return seq

    def row_sequence(self, r0):
        """Rows: r0..13 then r0-1..0."""
        return list(range(r0,14)) + list(range(r0-1,-1,-1))

    def upgrade_sequence(self, pt):
        """Grid of all cells around pt for upgrades."""
        cols = self.column_sequence(pt[0])
        rows = self.row_sequence(pt[1])
        return [[c,r] for r in rows for c in cols]

    def turret_sequence(self, pt):
        """All cells in vertical band above pt for turret placement."""
        cols = self.column_sequence(pt[0])
        return [[c, pt[1]-i] for i in range(pt[1]) for c in cols]

    @staticmethod
    def manhattan(a, b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1])

    def _monitor_resources_and_units(self, state: GameState) -> None:
        """Monitor and store the health of stationary units and available resources."""
        # Update current resources
        self.current_resources = {
            'MP': state.get_resource(MP),
            'SP': state.get_resource(SP)
        }

        # Clear and update current units
        current_units = {}

        # Scan the entire map
        for x in range(28):
            for y in range(28):
                loc = [x, y]
                unit = state.contains_stationary_unit(loc)
                if unit and unit.player_index == 0:  # Only our units
                    health_percent = (unit.health / unit.max_health) * 100
                    current_units[tuple(loc)] = {
                        'type': unit.unit_type,
                        'health': health_percent,
                        'max_health': unit.max_health,
                        'current_health': unit.health,
                        'upgraded': unit.upgraded
                    }

        # Calculate damage taken since last turn
        if self.monitoring_history:
            last_turn_units = self.monitoring_history[-1]['units']
            for loc, unit in current_units.items():
                if loc in last_turn_units:
                    last_health = last_turn_units[loc]['current_health']
                    damage_taken = last_health - unit['current_health']
                    if damage_taken > 0:
                        unit['damage_taken'] = damage_taken
                        unit['damage_history'] = last_turn_units[loc].get('damage_history', []) + [damage_taken]
                    else:
                        unit['damage_taken'] = 0
                        unit['damage_history'] = last_turn_units[loc].get('damage_history', [])
                else:
                    unit['damage_taken'] = 0
                    unit['damage_history'] = []
        else:
            for unit in current_units.values():
                unit['damage_taken'] = 0
                unit['damage_history'] = []

        # Store this turn's data in history
        turn_data = {
            'turn': state.turn_number,
            'resources': self.current_resources.copy(),
            'units': current_units
        }
        self.monitoring_history.append(turn_data)

        # Log current state
        gamelib.debug_write(f"Turn {state.turn_number} Monitoring:")
        gamelib.debug_write(f"Resources - MP: {self.current_resources['MP']}, SP: {self.current_resources['SP']}")

        # Log units taking damage
        damaged_units = {k: v for k, v in current_units.items()
                        if v.get('damage_taken', 0) > 0 or v['health'] < 50}
        if damaged_units:
            gamelib.debug_write("Damaged Units:")
            for loc, unit in damaged_units.items():
                damage_info = f" - {unit['damage_taken']} damage this turn" if unit.get('damage_taken', 0) > 0 else ""
                gamelib.debug_write(f"  {unit['type']} at {list(loc)} - {unit['health']:.1f}% health{damage_info}")

    def get_unit_history(self, location):
        """Get the health history of a unit at a specific location."""
        history = []
        for turn_data in self.monitoring_history:
            if tuple(location) in turn_data['units']:
                history.append({
                    'turn': turn_data['turn'],
                    'health': turn_data['units'][tuple(location)]['health']
                })
        return history

    def get_resource_history(self):
        """Get the history of MP and SP resources."""
        return [{'turn': data['turn'], 'MP': data['resources']['MP'], 'SP': data['resources']['SP']}
                for data in self.monitoring_history]

    def _count_enemy_turrets(self, state: GameState, coordinates: list) -> int:
        """Count the number of enemy turrets in the given coordinates."""
        count = 0
        for loc in coordinates:
            unit = state.contains_stationary_unit(loc)
            if unit and unit.player_index == 1 and unit.unit_type == TURRET:
                count += 1
        return count

    def _get_turret_coordinates(self, side: str) -> list:
        """Get the coordinates to check for turrets based on the side."""
        if side == 'l':
            return [[0,13], [1,13], [2,13], [3,13], [1,12], [2,12]]
        else:  # 'r'
            return [[27,13], [26,13], [25,13], [24,13], [26,12], [25,12]]

    def _get_priority_upgrade_locations(self, state: GameState) -> list:
        """
        Returns a list of locations that should be prioritized for upgrades based on damage history.
        Units that consistently take damage are prioritized.
        """
        if not self.monitoring_history:
            return []

        current_units = self.monitoring_history[-1]['units']
        priority_locations = []

        for loc, unit in current_units.items():
            if not unit['upgraded'] and unit['type'] in [WALL, TURRET]:
                # Calculate average damage taken over last 3 turns
                damage_history = unit.get('damage_history', [])
                recent_damage = sum(damage_history[-3:]) if damage_history else 0

                # Prioritize units that have taken damage recently
                if recent_damage > 0:
                    priority_locations.append({
                        'loc': list(loc),
                        'type': unit['type'],
                        'damage': recent_damage,
                        'health': unit['health']
                    })

        # Sort by damage taken (descending) and health (ascending)
        priority_locations.sort(key=lambda x: (-x['damage'], x['health']))
        return [item['loc'] for item in priority_locations]

if __name__ == "__main__":
    AlgoStrategy().start()
