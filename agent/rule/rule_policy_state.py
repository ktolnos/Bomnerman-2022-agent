from collections import deque

from parsing.parser import Parser
from rule.blocked_locations import compute_blocked_locations
from rule.closest_to_center import calculate_closest_to_center
from rule.state_map import compute_state_map
from simulation.engame_fire_simulator2 import EndgameFireSimulator2
from simulation.forward_model import ForwardModel


class RulePolicyState:
    def __init__(self):
        self.busy = set()  # units that already made the move
        self.tasks = list()
        self.endgame_fire_simulator = EndgameFireSimulator2(15, 15)
        self.has_no_path_to_center = None
        self.all_have_path_to_center = False
        self.already_occupied_spots = list()
        self.already_occupied_destinations = set()
        self.loop = None
        self.print_queue = deque()
        self.parser = None
        self.client = None
        self.closest_to_center_unit = None
        self.closest_to_center_my = None
        self.closest_to_center_enemy = None
        self.debug = False
        self.predicted_gs = None
        self.forward = ForwardModel()
        self.blocked_locations = set()
        self.unit_id_to_target_pos = dict()
        self.bombs_count = 0
        self.unit_id_to_diff_map_side_target_pos = dict()
        self.force_bomb_unit_ids = set()
        self.tick_number = 0
        self.state_map = None

    def update(self, tick_number, game_state):
        self.forward.clear()
        self.tick_number = tick_number

        self.busy.clear()
        self.already_occupied_spots.clear()
        self.already_occupied_destinations.clear()
        self.blocked_locations.clear()
        self.tasks.clear()

        self.parser = Parser(tick_number, game_state)
        self.bombs_count = len(self.parser.my_bombs)

        compute_state_map(self)
        calculate_closest_to_center(self)
        compute_blocked_locations(self)

    def is_busy(self, unit_id):
        return unit_id in self.busy

