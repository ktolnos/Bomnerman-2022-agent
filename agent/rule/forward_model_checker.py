import numpy as np

from parsing.gamestate import Powerup
from rule.state.rule_policy_state import RulePolicyState


def check_forward_model(state: RulePolicyState):
    if state.predicted_gs is not None:
        if state.predicted_gs != state.parser.gs:
            if state.predicted_gs.units != state.parser.gs.units:
                print("Predicted units\n", state.predicted_gs.units)
                print("Actual units\n", state.parser.gs.units)
                print("Units diff predictred\n", state.predicted_gs.units - state.parser.gs.units)
                print("Units diff actual\n", state.parser.gs.units - state.predicted_gs.units)
                print("Map\n", state.parser.gs.map)
            map_diff = np.ma.array(data=state.parser.gs.map, mask=state.predicted_gs.map == state.parser.gs.map)
            has_diff = False
            for el in map_diff.compressed():
                if not isinstance(el, Powerup):
                    print(el)
                    has_diff = True
            if has_diff:
                print("Prev map\n", state.prev_gs.map)
                print("Predicted map\n", state.predicted_gs.map)
                print("Actual map\n", state.parser.gs.map)
                print("Map diff\n", map_diff)
    state.prev_gs = state.parser.gs
    state.predicted_gs = state.forward.step(state.parser.gs)