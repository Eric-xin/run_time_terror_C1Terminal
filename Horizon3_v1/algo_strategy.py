import gamelib
import random
import math
import warnings
import copy
from sys import maxsize
import json
from gamelib import GameMap, GameState

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))
        # Supporter management state
        self.support_locations = []
        self.last_support_update = 0
        self.scored_on_locations = [] # locations where opponent scored on us
    
    def on_action_frame(self, frame_str):
        state = json.loads(frame_str)
        for breach in state["events"]["breach"]:
            loc = breach[0]
            owner = breach[4]
            # owner==2 means opponent scored on us
            if owner == 2:
                self.scored_on_locations.append(loc)

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0
        # game state for sectors, start points...
        self.scored_on_locations = []
        self.sectors = [[],[],[],[]]
        for c in range(0,14):
            for r in range(14-c-1, 14):
                self.sectors[c // 7].append([c,r])
        for c in range(14,28):
            for r in range(c-14, 14):
                self.sectors[c // 7].append([c,r])
        self.start_points = [[4,12], [10,12], [17,12], [23,12]]

    def on_turn(self, turn_state):
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Turn {}'.format(game_state.turn_number))
        game_state.suppress_warnings(True)

        # Core strategy
        if game_state.turn_number == 0:
            # self.initial_defense(game_state)
            self.funnel_defense(game_state)
        elif game_state.turn_number == 1:  # or any turn number you want
            # self.remove_all_defense_units(game_state)
            # self.funnel_defense(game_state)
            should_attack, location, num_scouts = self.should_attack(game_state)
            if should_attack:
                self.scout_attack(game_state, location, num_scouts)
        else:
            should_attack, location, num_scouts = self.should_attack(game_state)
            if should_attack:
                self.scout_attack(game_state, location, num_scouts)
        # Defense improvements
        did_improve = True
        while did_improve and game_state.get_resource(1) >= 2:
            defense = self.parse_defenses(game_state)
            sector_to_upgrade = self.defense_heuristic(defense)
            did_improve = self.improve_defense(game_state, sector_to_upgrade, defense[sector_to_upgrade])

        # Supporter management and reinforcement
        self.support_management(game_state, location if 'location' in locals() else None)

        self.build_far_side_walls(game_state)
        # self.defend_with_interceptors(game_state)
        self.patrol_far_interceptors(game_state)
        game_state.submit_turn()
        
    def funnel_defense(self, game_state: GameState):
  

        wall_locations = [[0,13], [1,13], [2,11], [3,10], [4,9], [5,8], [6,8], [7,8], [8,8], [9,8], [10,8], [11,8], [12,8], [13,8], [14,8], [15,8], [16,8], [17,8], [18,9], [19,10], [20,11], [20,12], [21,13], [22,13], [25,13], [26,13], [27,13], [22,9]]
        turret_locations = [[1,12], [22,11], [23,11], [24,12]]
        support_locations = [[22,8]]

        game_state.attempt_spawn(WALL, wall_locations)
        game_state.attempt_spawn(TURRET, turret_locations)
        game_state.attempt_spawn(SUPPORT, support_locations)
                        
        
    
    def patrol_far_interceptors(self, game_state: GameState):
        # 1) Look for any recorded breach in cols 0–3
        target = None
        for loc in self.scored_on_locations:
            x, y = loc
            if 0 <= x <= 3:
                target = x
                break
        if target is None:
            return  # no far‑side breach recorded

        # 2) find your free bottom‑left edge spots
        edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT)
        edges = [e for e in edges if not game_state.contains_stationary_unit(e)]
        if not edges:
            return

        # 3) spend exactly enough MP to spawn one interceptor
        cost = gamelib.GameUnit(INTERCEPTOR, self.config).cost[MP]
        if game_state.get_resource(MP) < cost:
            return

        # 4) pick the edge whose x is closest to the breach
        best_edge = min(edges, key=lambda e: abs(e[0] - target))
        game_state.attempt_spawn(INTERCEPTOR, best_edge)

        # 5) clear that breach so you only react once
        self.scored_on_locations = [loc for loc in self.scored_on_locations if loc[0] != target]
    
    # def defend_with_interceptors(self, game_state: GameState):
    #     # 1) Gather turret firing radius
    #     turret_proto = gamelib.GameUnit(TURRET, self.config)
    #     attack_radius = turret_proto.attackRange
    #     radius_sq = attack_radius * attack_radius

    #     # 2) Collect all your turret positions
    #     turrets = [pos for pos in game_state.game_map
    #             if (u := game_state.contains_stationary_unit(pos))
    #             and u.unit_type == TURRET]

    #     # 3) Define the barrier cells (cols 14–27 at row 13)
    #     barrier = [[x, 13] for x in range(14, 28)]

    #     # 4) Find any cells no turret can cover
    #     uncovered = []
    #     for bx, by in barrier:
    #         if not any((bx - tx)**2 + (by - ty)**2 <= radius_sq for tx, ty in turrets):
    #             uncovered.append([bx, by])
    #     if not uncovered:
    #         return  # all covered

    #     # 5) How many interceptors can you afford? (cast to int)
    #     cost = gamelib.GameUnit(INTERCEPTOR, self.config).cost[MP]
    #     mp = game_state.get_resource(MP)
    #     max_spawn = int(mp // cost)
    #     if max_spawn <= 0:
    #         return  # no MP

    #     # 6) Trim holes to that budget
    #     holes = uncovered[:max_spawn]

    #     # 7) Find your free bottom-right edge spots
    #     edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)
    #     edges = [e for e in edges if not game_state.contains_stationary_unit(e)]
    #     if not edges:
    #         return  # nowhere to spawn

    #     # 8) Send exactly one interceptor per hole
    #     for hx, hy in holes:
    #         best_edge = min(edges, key=lambda e: abs(e[0] - hx))
    #         game_state.attempt_spawn(INTERCEPTOR, best_edge)
    
    def support_management(self, game_state, scout_location):
        t = game_state.turn_number
        if (t < 3 or (t - 3) % 8 == 0) and scout_location:
            # Remove out-of-range supporters
            new_supports = []
            for loc in self.support_locations:
                if self.manhattan_distance(loc, scout_location) > 2:
                    game_state.attempt_remove(loc)
                else:
                    new_supports.append(loc)
            self.support_locations = new_supports
            # Spawn new supporters around scout spawn
            potential = game_state.game_map.get_locations_in_range(scout_location, 2)
            # Exclude blockers on scout path
            path = game_state.find_path_to_edge(scout_location)
            for loc in potential:
                if loc not in self.support_locations and loc not in path and game_state.can_spawn(SUPPORT, loc):
                    if game_state.attempt_spawn(SUPPORT, loc):
                        self.support_locations.append(loc)
                        game_state.attempt_upgrade(loc)
            self.last_support_update = t
        # Always attempt to upgrade existing supporters each turn
        for loc in list(self.support_locations):
            game_state.attempt_upgrade(loc)
    
    def manhattan_distance(self, a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """
    
    

    def main_strategy(self, game_state: GameState):
        
        if game_state.turn_number == 0:
            self.initial_defense(game_state)
            
        if game_state.turn_number > 0:
            should_attack, location, num_scouts = self.should_attack(game_state)
            if should_attack:
                self.scout_attack(game_state, location, num_scouts)
        # if self.should_defend(game_state):
        did_improve = True
        while (did_improve and game_state.get_resource(SP) >= 2):
            defense = self.parse_defenses(game_state)
            sector_to_upgrade = self.defense_heuristic(defense)
            did_improve = self.improve_defense(game_state, sector_to_upgrade, defense[sector_to_upgrade])
            
        
    def initial_defense(self, game_state):
        #TODO: do testing to optimize these placements, play around with putting extra turrets in front or upgraded walls
        
        game_state.attempt_spawn(TURRET, self.start_points)
        game_state.attempt_upgrade(self.start_points)
        
        wall_locations = [[4,13], [10,13], [17,13], [23,13]]
        
        game_state.attempt_spawn(WALL, wall_locations)
    
    
    def improve_defense(self, game_state: gamelib.GameState, sector, defense):
        
        
        start_point = self.start_points[sector]
        # gamelib.debug_write("SECTOR TO UPGRADE: " + str(sector) + " " + str(start_point))        
        
        loc_seq = self.upgrade_sequence(start_point)
          
            
        turret_seq = self.turret_sequence(start_point)
        
        if defense[0][3] < 1: # if less than one upgraded turret, prioritize building a new one
            if game_state.get_resource(0) >= 8:
                if self.try_build_upgraded_turret(game_state, turret_seq):
                    return True
            else: 
                return False
            # elif game_state.get_resource(0) >= 3:
            #     if self.try_build_turret(game_state, turret_seq):
            #         did_improve = True
        
        
        # try to upgrade any existing structures first (although ignore turrets with low HP)
        for i in range(len(loc_seq)):
            if self.try_upgrade(game_state, loc_seq[i]):
                return True
            
        
        cols = self.column_sequence(start_point[0])
        num_walls = defense[1][0] + defense[1][1]
        num_turrets =  defense[1][2] + defense[1][3]
            
        # if less than one wall, prioritize building new one
        if (num_walls < 1):
            # with >= 4 SP try to build an upgraded wall
            if game_state.get_resource(0) >= 4:
                for i in range(len(cols)):
                    loc = [cols[i], 13]
                    if not game_state.contains_stationary_unit(loc):
                        game_state.attempt_spawn(WALL, loc)
                        game_state.attempt_upgrade(loc)
                        return True
            if game_state.get_resource(0) >= 2:
                for i in range(len(cols)):
                    loc = [cols[i], 13]
                    if not game_state.contains_stationary_unit(loc):
                        game_state.attempt_spawn(WALL, loc)
                        return True
        
        if game_state.get_resource(0) >= 8:
            if self.try_build_upgraded_turret(game_state, turret_seq):
                return True
        
        if (num_walls < num_turrets):
            # with >= 4 SP try to build an upgraded wall
            if game_state.get_resource(0) >= 4:
                for i in range(len(cols)):
                    loc = [cols[i], 13]
                    if not game_state.contains_stationary_unit(loc):
                        game_state.attempt_spawn(WALL, loc)
                        game_state.attempt_upgrade(loc)
                        return True
            if game_state.get_resource(0) >= 2:
                for i in range(len(cols)):
                    loc = [cols[i], 13]
                    if not game_state.contains_stationary_unit(loc):
                        game_state.attempt_spawn(WALL, loc)
                        return True
        
        # if self.try_build_upgraded_turret(game_state, turret_seq):
        #     return True
        # elif self.try_build_turret(game_state, turret_seq):
        #     return False
        
        # with >= 2 SP try to build unupgraded wall
        return False
        
    def try_build_upgraded_turret(self, game_state, turret_seq):
        if game_state.get_resource(0) >= 8:
            for i in range(len(turret_seq)):
                loc = turret_seq[i]
                if not game_state.contains_stationary_unit(loc):
                    game_state.attempt_spawn(TURRET, loc)
                    game_state.attempt_upgrade(loc)
                    return True
        return False
    
    def try_build_turret(self, game_state, turret_seq): 
        if game_state.get_resource(0) >= 3:
            for i in range(len(turret_seq)):
                loc = turret_seq[i]
                if not game_state.contains_stationary_unit(loc):
                    game_state.attempt_spawn(TURRET, loc)
                    return True
        return False
        
    def try_upgrade(self, game_state: gamelib.GameState, location):
        if game_state.contains_stationary_unit(location):
            unit: gamelib.GameUnit = game_state.contains_stationary_unit(location)
            if unit.unit_type == TURRET and unit.health / unit.max_health >= 0.75:
                # try upgrade turret if hp >= 75%, since turret hp doesn't get restored on upgrade
                return game_state.attempt_upgrade(location) > 0
                
            elif unit.unit_type == WALL:
                # always upgrade wall since it gives + 80hp
                return game_state.attempt_upgrade(location) > 0
                
        return False
            
        
    # prioritized sequence of columns, starts near col of start_point, then alternates on each side
    # goes towards middle first, then away (eg. start_point + 1, start_point - 1)
    def column_sequence(self, start):
        res = [start]
        left = (start // 7) * 7
        right = (start // 7 + 1) * 7
        if start < 14:
            left = left + 1
        else:
            right = right - 1
        for i in range(1, 7):
            inc = -i if start < 14 else i
            if (start + inc < right and start + inc >= left):
                res.append(start + inc)
            if (start - inc >= left and start - inc < right):
                res.append(start - inc)
        return res
    
    def row_sequence(self, start):
        r = start
        rows = []
        while (r < 14):
            rows.append(r)
            r = r+1
        
        r = start - 1
        while (r >= 0):
            rows.append(r)
            r = r - 1
        return rows
    
    def upgrade_sequence(self, start_point):
        res = []
        cols = self.column_sequence(start_point[0])
        
        rows = self.row_sequence(start_point[1])
        
        for i in range(len(rows)): 
            for j in range(len(cols)):
                res.append([cols[j], rows[i]])
                
        return res
    
    def turret_sequence(self, start_point):
        res = []
        cols = self.column_sequence(start_point[0])
        
        for i in range(0, start_point[1]): 
            for j in range(len(cols)):
                res.append([cols[j], start_point[1] - i])
                
        return res
    
    def parse_defenses(self, game_state: gamelib.GameState):
        results = [[],[],[],[]]
        for i in range(4):
            num_wall = 0
            num_wallPlus = 0
            num_turret = 0
            num_turretPlus = 0
            
            weight_wall = 0
            weight_wallPlus = 0
            weight_turret = 0
            weight_turretPlus = 0
            for j in range(len(self.sectors[i])):
                if game_state.contains_stationary_unit(self.sectors[i][j]):
                    unit: gamelib.GameUnit = game_state.contains_stationary_unit(self.sectors[i][j])
                    weight = unit.health / unit.max_health
                    
                    if unit.unit_type == WALL:
                        if unit.upgraded:
                            num_wallPlus += 1
                            weight_wallPlus += weight
                        else:
                            num_wall += weight
                            weight_wall += weight
                            
                    #skip support when parsing our own defense, it doesn't really matter
                    
                    if unit.unit_type == TURRET:
                        if unit.upgraded:
                            num_turretPlus += 1
                            weight_turretPlus += weight
                        else:
                            num_turret += 1
                            weight_turret += weight
            
            results[i].append([weight_wall, weight_wallPlus, weight_turret, weight_turretPlus])
            results[i].append([num_wall, num_wallPlus, num_turret, num_turretPlus])
            
        return results
    
    def build_far_side_walls(self, game_state: GameState):
        # Define a shallow two‐deep wall layer on each far corner
        wall_spots = [
            [0, 13], [1, 13],    # left corner
            [26, 13], [27, 13]   # right corner
        ]
        for loc in wall_spots:
            # Spawn if empty and you can afford it
            if game_state.can_spawn(WALL, loc):
                game_state.attempt_spawn(WALL, loc)
            # Then always try to upgrade it
            unit = game_state.contains_stationary_unit(loc)
            if unit and unit.unit_type == WALL and not unit.upgraded:
                game_state.attempt_upgrade(loc)
                
    def defense_heuristic(self, defenses):
        res = 0
        minVal = 99999999
        for i in range(4):
            #TODO: make a better heuristic, this weighs turret+ at 14 "points", turret- at 6, wall+ at 3, wall- at 1
            # then we select the sector that has the lowest # of points
            value = defenses[i][0][3] * 14 + defenses[i][0][2] * 6 + defenses[i][0][1] * 3 + defenses[i][0][0]
            if defenses[i][0][1] < 1:
                value *= 0.5
            if i == 0 or i == 3:
                value *= 1 # farside
            if value < minVal:
                minVal = value
                res = i
        
        return res
    
    def remove_all_defense_units(self, game_state):
        """
        Removes all defensive units from our side of the map using game_map.remove_unit
        """
        # Iterate through all locations on our side of the map
        for x in range(28):
            for y in range(14):  # Only our side of the map
                location = [x, y]
                # Check if there's a unit at this location
                if game_state.game_map[x,y] != None:
                    # Remove the unit using game_map
                    game_state.game_map.remove_unit(location)

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """
        # First, place basic defenses
        # self.build_defences(game_state)
        # Now build reactive defenses based on where the enemy scored
        # self.build_reactive_defense(game_state)
        if game_state.turn_number > 0:
            self.scout_attack_with_support(game_state)
                
    def should_defend(self, game_state):
        enemy_mobile_points = game_state.get_resource(MP,1)
        return enemy_mobile_points >= 8

    def build_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where enemy demolishers can attack them.
        """
        # Useful tool for setting up your base locations: https://www.kevinbai.design/terminal-map-maker
        # More community tools available at: https://terminal.c1games.com/rules#Download

        # Place turrets that attack enemy units
        turret_locations = [[0, 13], [27, 13], [8, 11], [19, 11], [13, 11], [14, 11]]
        # attempt_spawn will try to spawn units if we have resources, and will check if a blocking unit is already there
        game_state.attempt_spawn(TURRET, turret_locations)
        
        # Place walls in front of turrets to soak up damage for them
        wall_locations = [[8, 12], [19, 12]]
        game_state.attempt_spawn(WALL, wall_locations)
        # upgrade walls so they soak more damage
        game_state.attempt_upgrade(wall_locations)

    def build_reactive_defense(self, game_state):
        """
        This function builds reactive defenses based on where the enemy scored on us from.
        We can track where the opponent scored by looking at events in action frames 
        as shown in the on_action_frame function
        """
        for location in self.scored_on_locations:
            # Build turret one space above so that it doesn't block our own edge spawn locations
            build_location = [location[0], location[1]+1]
            game_state.attempt_spawn(TURRET, build_location)

    def stall_with_interceptors(self, game_state):
        """
        Send out interceptors at random locations to defend our base from enemy moving units.
        """
        # We can spawn moving units on our edges so a list of all our edge locations
        friendly_edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)
        
        # Remove locations that are blocked by our own structures 
        # since we can't deploy units there.
        deploy_locations = self.filter_blocked_locations(friendly_edges, game_state)
        
        # While we have remaining MP to spend lets send out interceptors randomly.
        while game_state.get_resource(MP) >= game_state.type_cost(INTERCEPTOR)[MP] and len(deploy_locations) > 0:
            # Choose a random deploy location.
            deploy_index = random.randint(0, len(deploy_locations) - 1)
            deploy_location = deploy_locations[deploy_index]
            
            game_state.attempt_spawn(INTERCEPTOR, deploy_location)
            """
            We don't have to remove the location since multiple mobile 
            units can occupy the same space.
            """

    def demolisher_line_strategy(self, game_state):
        """
        Build a line of the cheapest stationary unit so our demolisher can attack from long range.
        """
        # First let's figure out the cheapest unit
        # We could just check the game rules, but this demonstrates how to use the GameUnit class
        stationary_units = [WALL, TURRET, SUPPORT]
        cheapest_unit = WALL
        for unit in stationary_units:
            unit_class = gamelib.GameUnit(unit, game_state.config)
            if unit_class.cost[game_state.MP] < gamelib.GameUnit(cheapest_unit, game_state.config).cost[game_state.MP]:
                cheapest_unit = unit

        # Now let's build out a line of stationary units. This will prevent our demolisher from running into the enemy base.
        # Instead they will stay at the perfect distance to attack the front two rows of the enemy base.
        for x in range(27, 5, -1):
            game_state.attempt_spawn(cheapest_unit, [x, 11])

        # Now spawn demolishers next to the line
        # By asking attempt_spawn to spawn 1000 units, it will essentially spawn as many as we have resources for
        game_state.attempt_spawn(DEMOLISHER, [24, 10], 1000)

    def least_damage_spawn_location(self, game_state):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = []
        location_options = []
        for i in range(14):
            if game_state.can_spawn(SCOUT, [i,13-i]):
                location_options.append([i,13-i])
            if game_state.can_spawn(SCOUT, [14+i,i]):
                location_options.append([14+i,i])

        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
            damages.append(damage)
        
        min_damage = min(damages)
        indices = []
        for i,damage in enumerate(damages):
            if damage == min_damage:
                indices.append(i)
        import random
        return location_options[indices[random.randrange(0,len(indices))]]


    def full_sim(self, game_state : gamelib.GameState, num_scouts:int):
        # Returns the location, and also the number of simulated scouts that make it through
        # 0 stores num surviving scouts,
        # 1 stores turret damage to scout, 
        # 2 stores scout damage to turret, 
        # 3 stores scout damage to walls,
        # 4 stores scout damage to supports 
        # 5 stores the starting location
        # 6 stores set of all attackers along this path
        path_dmg: list[tuple[int,int,list[int]]]= []
        
        location_options = []
        # game_state.get_target(attacking_unit)
        for i in range(14):
            if game_state.can_spawn(SCOUT, [i,13-i]):
                location_options.append([i,13-i])
            if game_state.can_spawn(SCOUT, [14+i,i]):
                location_options.append([14+i,i])
                
        
        TEMP_SCOUT  = gamelib.GameUnit(SCOUT, game_state.config)
        SCOUT_DAMAGE = TEMP_SCOUT.damage_f
        SCOUT_HP = TEMP_SCOUT.max_health
        
        edge_locs = []
        for i in range(4):
            edge_locs.append(game_state.game_map.get_edge_locations(i))
        
        for location in location_options:
            temp_state :gamelib.GameState = copy.deepcopy(game_state)
            dead_scouts = 0
            edge = temp_state.get_target_edge(location)
            path = temp_state.find_path_to_edge(location)
            scout_damage_to_turret = 0
            scout_damage_to_wall = 0
            scout_damage_to_support = 0
            turret_damage_to_scout = 0
            
            all_attackers: set[tuple[int,int]] = set()
            
            path_index = 0
            cur_hp = SCOUT_HP + 3 # hardcode + 3 for shield
            
            while path_index < len(path):
                path_location = path[path_index]
                attackers : list[gamelib.GameUnit] = temp_state.get_attackers(path_location, 0)
                temp_state.game_map.add_unit(SCOUT, path_location)
                
                remaining_scouts_to_attack = num_scouts - dead_scouts
                
                while (remaining_scouts_to_attack > 0):
                    target = temp_state.get_target(temp_state.game_map[path_location][0])
                    if target:
                        max_dmg = remaining_scouts_to_attack * SCOUT_DAMAGE
                        if target.health <= max_dmg:
                            if target.unit_type == TURRET:
                                scout_damage_to_turret += target.health
                            elif target.unit_type == WALL:
                                scout_damage_to_wall += target.health
                            elif target.unit_type == SUPPORT:
                                scout_damage_to_support += target.health
                            
                            temp_state.game_map.remove_unit([target.x, target.y])
                            # after destroying a structure, recalculate the path
                            path = temp_state.find_path_to_edge(path_location, edge)
                            # gamelib.debug_write(str(path))
                            path_index = 0
                            
                            remaining_scouts_to_attack -= math.ceil(target.health / SCOUT_DAMAGE)
                        else:
                            target.health -= max_dmg
                            if target.unit_type == TURRET:
                                scout_damage_to_turret += max_dmg
                            elif target.unit_type == WALL:
                                scout_damage_to_wall += max_dmg
                            elif target.unit_type == SUPPORT:
                                scout_damage_to_support += max_dmg
                            break
                    else: 
                        break
                
                temp_state.game_map.remove_unit(path_location)
                
                
                
                # gamelib.debug_write(f"{location} path loc: {path_location} num attackers: {len(attackers)}")
                
                for attacker in attackers:
                    all_attackers.add((attacker.x, attacker.y))
                    if num_scouts == dead_scouts: 
                        break
                    turret_damage_to_scout += min(attacker.damage_i, cur_hp)
                    cur_hp -= attacker.damage_i
                    if cur_hp <= 0:
                        dead_scouts += 1
                        cur_hp = SCOUT_HP + 3
                        # gamelib.debug_write("SCOUT DIED")
                        
                
                path_index += 1
            
            survived = num_scouts-dead_scouts
            if path[-1] not in edge_locs[edge]:
                survived = 0
            
            path_dmg.append((survived, turret_damage_to_scout, scout_damage_to_turret, scout_damage_to_wall, scout_damage_to_support, location, all_attackers))
        # Python is a stable sort, so we sort by num surviving scouts, then by scout damage to supports, then by scout damage to turrets, then by scout damage to walls
        path_dmg = sorted(path_dmg, key = lambda x: x[3], reverse=True)
        path_dmg = sorted(path_dmg, key = lambda x: x[2], reverse=True)
        path_dmg = sorted(path_dmg, key = lambda x: x[4], reverse=True)
        path_dmg = sorted(path_dmg, key = lambda x: x[0], reverse=True)
        
        
        # for thing in path_dmg:
        #     gamelib.debug_write(f"location: {thing[4]} surviving: {thing[0]} damage to turret: {thing[2]}")
        
        import random
        index = random.randrange(0,min(len(path_dmg),2)) # 0 or random
        
        best = path_dmg[0]
        for i in range(1,8):
            if len(set.intersection(best[6], path_dmg[i][6])) == 0 and best[0] - path_dmg[i][0] < math.ceil(num_scouts*0.2) and math.fabs(best[4]-path_dmg[i][4]) < 0.2 * best[4]:
                return (path_dmg[i][5], path_dmg[i][0])
        
        return (path_dmg[index][5], path_dmg[index][0]) #return location and num surviving


    def least_damage_spawn_location_simulation(self, game_state, num_scouts:int):
        # Returns the location, and also the number of simulated scouts that make it through
        # 0 stores turret damage to scout, 1 stores scout damage to turret, 2 stores the starting location
        path_dmg: list[tuple[int,int,list[int]]]= []
        
        location_options = []
        # game_state.get_target(attacking_unit)
        for i in range(14):
            if game_state.can_spawn(SCOUT, [i,13-i]):
                location_options.append([i,13-i])
            if game_state.can_spawn(SCOUT, [14+i,i]):
                location_options.append([14+i,i])
        dead_scouts = 0
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            scout_damage_to_turret = 0
            turret_damage_to_scout = 0
            dead_attackers: set[list[int,int]] = {}
            for path_location in path:
                turret_damage_to_scout += len(game_state.get_attackers(path_location, 0, dead_attackers)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
                target = game_state.get_target(gamelib.GameUnit(SCOUT, game_state.config))
                if target and target.unit_type == gamelib.GameUnit(TURRET, game_state.config).unit_type:
                    scout_damage_to_turret += min(target.health, gamelib.GameUnit(SCOUT, game_state.config).damage_f *num_scouts)
                    if gamelib.GameUnit(SCOUT, game_state.config).damage_i * num_scouts >= target.health:
                       dead_attackers.add((target.x,target.y))
                elif target and target.unit_type == gamelib.GameUnit(WALL,game_state.config):
                    scout_damage_to_wall += min(target.health,)
                if turret_damage_to_scout >= (dead_scouts+1):
                    num_scouts -=1
                    dead_scouts += 1
            path_dmg.append((turret_damage_to_scout,scout_damage_to_turret,location,num_scouts))
        # Python is a stable sort, so we sort by inc turret_damage_to_scout, and then dec scout_damage_to_turret
        path_dmg = sorted(path_dmg, key = lambda x: x[1], reverse=True)
        path_dmg = sorted(path_dmg, key = lambda x: x[0])
        import random
        index = random.randrange(0,min(len(path_dmg),2)) # 0 or random
        return (path_dmg[index][2],path_dmg[index][3])

    def attack_this_round_mp(self, game_state) -> bool:
        DELTA: float = 2
        return game_state.project_future_MP() - game_state.get_resource(MP) < DELTA
            
    def buy_sell_support(self, game_state, location) -> bool:
        "Checks to see if we can spawn a support for an attack"
        if game_state.can_spawn(SUPPORT,location):
            game_state.attempt_spawn(SUPPORT,location)
            game_state.attempt_remove(location)
            return True
        return False

    def should_attack(self, game_state: GameState):
        DELTA: float = 2
        mobile_points = game_state.get_resource(MP)
        num_scouts = int(mobile_points)
        scout_location,scouts_alive = self.full_sim(game_state, num_scouts)
        # gamelib.debug_write("BEST LOCATION: " + str(scout_location) + "NUM SURVIVE: " + str(scouts_alive) + " MP : " + str(mobile_points))
        
        if mobile_points >= 8 and game_state.enemy_health <= 7 and game_state.enemy_health - scouts_alive < -3:
            return True, scout_location, num_scouts
        if mobile_points < 15 + game_state.turn_number // 10 and (scouts_alive <= num_scouts * 0.6 or mobile_points < 8):
            return False, [], 0
        
        return True, scout_location, num_scouts
        
    def scout_attack(self, game_state, scout_location, num_scouts):
        # Spawn scouts only; supporters handled separately
        game_state.attempt_spawn(SCOUT, scout_location, num_scouts)
        
    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units
        
    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    # def on_action_frame(self, turn_string):
    #     """
    #     This is the action frame of the game. This function could be called 
    #     hundreds of times per turn and could slow the algo down so avoid putting slow code here.
    #     Processing the action frames is complicated so we only suggest it if you have time and experience.
    #     Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
    #     """
    #     # Let's record at what position we get scored on
    #     # state = json.loads(turn_string)
    #     # events = state["events"]
    #     # breaches = events["breach"]
    #     # for breach in breaches:
    #     #     location = breach[0]
    #     #     unit_owner_self = True if breach[4] == 1 else False
    #     #     # When parsing the frame data directly, 
    #     #     # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
    #     #     if not unit_owner_self:
    #     #         gamelib.debug_write("Got scored on at: {}".format(location))
    #     #         self.scored_on_locations.append(location)
    #     #         gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()