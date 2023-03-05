from utils.game_utils import Unit, blast_r, is_invincible_next_tick, Point


def can_hit_enemy(unit, parser) -> Unit:  # returns enemy or none
    def has_enemy(x, y):
        if x < 0 or x >= parser.w or y < 0 or y >= parser.h:
            return None, True
        if parser.wall_map[x, y] != 0:
            return None, True
        for enemy in parser.enemy_units:
            if enemy.pos == Point(x, y):
                return enemy, False
        return None, False

    rad = blast_r(unit.blast_diameter)
    x, y = unit.pos
    enemy_found = None
    for i in range(rad):
        enemy, stop_iter = has_enemy(x + i, y)
        if enemy:
            if not is_invincible_next_tick(enemy, parser.gs.tick):
                return enemy
            enemy_found = enemy
        if stop_iter:
            break
    for i in range(rad):
        enemy, stop_iter = has_enemy(x - i, y)
        if enemy:
            if not is_invincible_next_tick(enemy, parser.gs.tick):
                return enemy
            enemy_found = enemy
        if stop_iter:
            break
    for i in range(rad):
        enemy, stop_iter = has_enemy(x, y + i)
        if enemy:
            if not is_invincible_next_tick(enemy, parser.gs.tick):
                return enemy
            enemy_found = enemy
        if stop_iter:
            break
    for i in range(rad):
        enemy, stop_iter = has_enemy(x, y - i)
        if enemy:
            if not is_invincible_next_tick(enemy, parser.gs.tick):
                return enemy
            enemy_found = enemy
        if stop_iter:
            break
    return enemy_found
