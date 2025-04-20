import gamelib
import random
import math
import copy
import json
from sys import maxsize
from gamelib import GameState, GameMap, GameUnit

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
        # State
        self.support_locations = []
        self.scored_on = []
        self.sectors = []
        self.start_points = []

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

        # build a 28×28 boolean mask for valid support positions
        self.support_mask = []

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
        self.start_points = [[3,12], [4,12], [5,11], [6,10], [9,10], [12,10], [15,10], [18,10], [21,10], [23,11], [24,12]]

        # rim
        self.left_rim = [[13 - i, i] for i in range(14)]
        self.rit_rim = [[27 - (13 - i), i] for i in range(14)]

        # walls for RESORT SECOND
        self.wallresnd = [[3,13], [4,13], [5,12], [6,11], [7,11], [8,11], [9,11], [10,11], [11,11], [12,11], [13,11], [14,11], [15,11], [16,11], [17,11], [18,11], [19,11], [20,11], [21,11], [22,11], [23,12], [24,13]]

        self.wallresnd_bp = [[26,12], [25,12], [25,11], [24,11], [24,10], [23,10], [23,9], [22,9]]

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

        # --- Check for last resort ---
        if state.turn_number >= 5:
            self.resort = True
        
        # # --- Interceptors defense ---
        # if state.turn_number <= 2 or (self.resort and (not self.wall_integrity_check(state))):
        #     _ = self._interceptors_defense(state)

        # --- Offense ---
        if state.turn_number == 0:
            self._build_far_side_walls(state, upd=False)
            self._initial_defense(state)
        elif not self.resort:
            attack, loc, num = self.should_attack(state)
            if attack:
                self.scout_attack(state, loc, num)
        
        # --- Far-side walls | RESORT SECOND ---
        if self.resort:
            # 1) Compute MP threshold for 3 interceptors + 7 scouts
            _, int_cost   = state.type_cost(INTERCEPTOR)  # returns [sp, mp]
            _, scout_cost = state.type_cost(SCOUT)
            threshold = 3 * int_cost + 7 * scout_cost
            mp = state.get_resource(MP)

            # 2) If we can afford the wave, open up the left gap
            if self.wall_integrity_check(state):
                if mp >= threshold:
                    # remove walls at [0,13],[1,13] and build everywhere else
                    self._build_far_side_walls(state, exclude_side='l')
                else:
                    # otherwise, keep full ring
                    self._build_far_side_walls(state)

                # 3) If we’ve got the MP *and* the left‑gap is clear, launch offense
                if (mp >= threshold
                    and not state.contains_stationary_unit([0,13])
                    and not state.contains_stationary_unit([1,13])):
                    self._manage_support(state, [14, 0]) # place supporter
                    self.resort_offense(state)
        else:
            # Normal far‑side walls when not in last resort
            self._build_far_side_walls(state, exclude_side=None)

        # --- Defense improvements ---
        max_improvements = 15
        for _ in range(max_improvements):
            if state.get_resource(SP) < 2:
                break
            if not self._try_improve_defense(state):
                break

        # --- Support management ---
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
    def _initial_defense(self, state: GameState):
        """Basic turret + wall setup on turn 0."""
        state.attempt_spawn(TURRET, self.start_points)
        # state.attempt_upgrade(self.start_points) # No upgrade of turrets based on the current rule
        walls = [[x, y + 1] for x, y in self.start_points]
        state.attempt_spawn(WALL, walls)
        # # try to upgrade walls
        # for loc in walls:
        #     unit = state.contains_stationary_unit(loc)
        #     if unit and unit.unit_type == WALL and not unit.upgraded:
        #         state.attempt_upgrade(loc)

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

    def improve_defense(self, state: GameState, sector: int, defense) -> bool:
        """
        Improve defenses in one sector or, if in last‑resort mode, rebuild a special wall ring.
        
        Parameters:
        state   – current GameState
        sector  – index 0–3 of your four triangular sectors
        defense – output of parse_defenses(state)[sector] (unused here)
        
        Returns:
        True if an action (spawn/upgrade/remove) was performed this turn.
        """
        turn   = state.turn_number
        start  = self.start_points[sector]
        centre = 14

        # —————————————————————————————————————————————————————————————
        # 1) LAST‑RESORT MODE: rebuild your special wall ring (self.wallresnd)
        # —————————————————————————————————————————————————————————————
        if self.resort:
            # 1) Spawn any missing walls
            for loc in self.wallresnd:
                if not state.contains_stationary_unit(loc) and state.can_spawn(WALL, loc):
                    state.attempt_spawn(WALL, loc)
                    return True

            # 2) Repair & rebuild badly damaged walls (<25% health)
            for loc in self.wallresnd:
                unit = state.contains_stationary_unit(loc)
                if unit and unit.unit_type == WALL and unit.health < 0.25 * unit.max_health:
                    state.attempt_remove(loc)
                    if state.can_spawn(WALL, loc):
                        state.attempt_spawn(WALL, loc)
                        state.attempt_upgrade(loc)
                    return True

            # 3) Upgrade any walls that aren’t yet upgraded
            for loc in self.wallresnd:
                unit = state.contains_stationary_unit(loc)
                if unit and unit.unit_type == WALL and not unit.upgraded:
                    state.attempt_upgrade(loc)
                    return True
        
        # —————————————————————————————————————————————————————————————
        # 1 bp) LAST‑RESORT MODE: rebuild the special wall ring (self.wallresnd_bp)
        # —————————————————————————————————————————————————————————————
        if self.resort and turn >= 5:
            # 1) Spawn any missing walls
            for loc in self.wallresnd_bp:
                if not state.contains_stationary_unit(loc) and state.can_spawn(WALL, loc):
                    state.attempt_spawn(WALL, loc)
                    return True

            # 2) Repair & rebuild badly damaged walls (<25% health)
            for loc in self.wallresnd_bp:
                unit = state.contains_stationary_unit(loc)
                if unit and unit.unit_type == WALL and unit.health < 0.25 * unit.max_health:
                    state.attempt_remove(loc)
                    if state.can_spawn(WALL, loc):
                        state.attempt_spawn(WALL, loc)
                        state.attempt_upgrade(loc)
                    return True

        # —————————————————————————————————————————————————————————————
        # 2) INITIAL LINE: fix any broken wall+turret at start_points
        # —————————————————————————————————————————————————————————————
        for pt in self.start_points:
            wall_loc   = [pt[0], pt[1] + 1]
            turret_loc = pt

            # rebuild missing wall first
            if not state.contains_stationary_unit(wall_loc) and state.can_spawn(WALL, wall_loc):
                state.attempt_spawn(WALL, wall_loc)
                state.attempt_upgrade(wall_loc)
                return True

            # then rebuild missing turret
            if not state.contains_stationary_unit(turret_loc) and state.can_spawn(TURRET, turret_loc):
                state.attempt_spawn(TURRET, turret_loc)
                return True

        # —————————————————————————————————————————————————————————————
        # 3) SYMMETRIC MID‑DEFENSE: walls at y=11, turrets at y=10
        #    Ranges: x=7…11 (left) and x=22…18 (right), interleaved
        # —————————————————————————————————————————————————————————————
        left_range  = range(7, 12)       #  7,8,9,10,11
        right_range = range(22, 17, -1)  # 22,21,20,19,18

        for lx, rx in zip(left_range, right_range):
            for x in (lx, rx):
                wloc = [x, 11]
                tloc = [x, 10]
                wall_unit   = state.contains_stationary_unit(wloc)
                turret_unit = state.contains_stationary_unit(tloc)

                # 3.1) spawn/upgrade missing wall
                if not wall_unit and state.can_spawn(WALL, wloc):
                    state.attempt_spawn(WALL, wloc)
                    state.attempt_upgrade(wloc)
                    return True

                # 3.2) upgrade damaged/unupgraded wall
                if wall_unit and wall_unit.unit_type == WALL and not wall_unit.upgraded:
                    state.attempt_upgrade(wloc)
                    return True

                # 3.3) spawn missing turret behind
                if not turret_unit and wall_unit and state.can_spawn(TURRET, tloc):
                    state.attempt_spawn(TURRET, tloc)
                    return True

        # nothing to do
        return False
    
    def wall_integrity_check(self, state: GameState) -> bool:
        """
        Return True if every location in self.wallresnd has an intact WALL unit.
        """
        for loc in self.wallresnd:
            # retrieve the stationary unit (not just a boolean)
            unit = state.contains_stationary_unit(loc)
            # if there's no unit here, or it's not a WALL, integrity is broken
            if getattr(unit, 'unit_type', None) != WALL:
                return False

        return True

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
    
    # ------------------------
    # Interoceptors defense
    # ------------------------
    def _interceptors_defense(self, state: GameState):
        # send interceptors at [5,8] and [22,8]
        interoceptor_cost = state.type_cost(INTERCEPTOR)[1]
        if state.get_resource(MP) >= interoceptor_cost * 2:
            if state.can_spawn(INTERCEPTOR, [5, 8]):
                state.attempt_spawn(INTERCEPTOR, [5, 8])
            if state.can_spawn(INTERCEPTOR, [22, 8]):
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
    def _build_far_side_walls(
        self,
        state: GameState,
        exclude_side: str = None,
        upd: bool = True
    ) -> None:
        """
        Maintain walls along the far edges, optionally leaving an opening.

        Parameters:
        state         – current GameState
        exclude_side  – 'l' to open left ([0,13],[1,13]),
                        'r' to open right ([26,13],[27,13]),
                        or None to build everywhere.
        """
        # Define all candidate spots
        spots = [[0,13], [1,13], [2,13], [25,13], [26,13], [27,13]]
        # Define which two to permanently open/unbuild
        left_open  = [[0,13], [1,13]]
        right_open = [[26,13], [27,13]]

        # 1) If asked to open one side, remove any existing walls there
        if exclude_side == 'l':
            for loc in left_open:
                if state.contains_stationary_unit(loc):
                    state.attempt_remove(loc)
            # exclude from build list
            spots = [loc for loc in spots if loc not in left_open]
        elif exclude_side == 'r':
            for loc in right_open:
                if state.contains_stationary_unit(loc):
                    state.attempt_remove(loc)
            spots = [loc for loc in spots if loc not in right_open]

        # 2) Build and upgrade walls at the remaining spots
        for loc in spots:
            if state.can_spawn(WALL, loc):
                state.attempt_spawn(WALL, loc)
            if upd:
                unit = state.contains_stationary_unit(loc)
                if unit and unit.unit_type == WALL and not unit.upgraded:
                    state.attempt_upgrade(loc)

    # ------------------------
    # Offense logic
    # ------------------------
    def resort_offense(self, state: GameState) -> None:
        """
        Last‑resort offense: spawn up to 3 INTERCEPTORs at [3,10],
        then deploy as many SCOUTs as possible at [14,0] with remaining MP.
        """
        # 1) Get available MP
        mp_available = state.get_resource(MP)

        # 2) Determine MP costs (cast to int)
        _, mp_cost_int   = state.type_cost(INTERCEPTOR)
        _, mp_cost_scout = state.type_cost(SCOUT)
        mp_cost_int   = int(mp_cost_int)
        mp_cost_scout = int(mp_cost_scout)

        # 3) Spawn up to 3 interceptors at [3,10]
        max_int = mp_available // mp_cost_int
        num_int = min(3, max_int)
        num_int = int(num_int)  # ensure it's an integer
        if num_int > 0 and state.can_spawn(INTERCEPTOR, [3, 10]):
            state.attempt_spawn(INTERCEPTOR, [3, 10], num_int)
            mp_available -= num_int * mp_cost_int
            gamelib.debug_write(f"Resort offense: spawned {num_int} INTERCEPTOR(s) at [3,10]")

        # 4) Spend all remaining MP on scouts at [14,0]
        num_scout = mp_available // mp_cost_scout
        num_scout = int(num_scout)
        if num_scout > 0 and state.can_spawn(SCOUT, [14, 0]):
            state.attempt_spawn(SCOUT, [14, 0], num_scout)
            gamelib.debug_write(f"Resort offense: spawned {num_scout} SCOUT(s) at [14,0]")

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

if __name__ == "__main__":
    AlgoStrategy().start()