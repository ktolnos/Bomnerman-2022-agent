from __future__ import annotations

from dataclasses import dataclass
from utils.game_utils import Point


@dataclass(frozen=True)
class Bomb:
    pos: Point
    blast_diameter: int
    owner_unit_id: str
    is_armed: bool


@dataclass(frozen=True)
class BombCluster:
    start: Point
    danger: float
    is_armed: bool
    is_my: bool
    is_enemy: bool
    ticks_till_explode: int
    my_bomb_that_can_trigger: Bomb

    def merge_with(self, other: BombCluster) -> BombCluster:
        return BombCluster(
            self.start,
            max(self.danger, other.danger),
            self.is_armed or other.is_armed,
            self.is_my or other.is_my,
            self.is_enemy or other.is_enemy,
            min(self.ticks_till_explode, other.ticks_till_explode),
            self.my_bomb_that_can_trigger if self.my_bomb_that_can_trigger else other.my_bomb_that_can_trigger,
        )


@dataclass(frozen=False)
class BombExplosionMapEntry:
    bomb: Bomb
    cluster: BombCluster

    def merge_with(self, other: BombExplosionMapEntry, cluster_to_bombs):
        other_cluster = other.cluster
        my_cluster = self.cluster
        new_cluster = self.cluster.merge_with(other.cluster)
        new_cluster_entries = []
        for other_cluster_entry in cluster_to_bombs[other_cluster]:
            other_cluster_entry.cluster = new_cluster
            new_cluster_entries.append(other_cluster_entry)
        for cluster_entry in cluster_to_bombs[my_cluster]:
            cluster_entry.cluster = new_cluster
            new_cluster_entries.append(cluster_entry)
        cluster_to_bombs[other_cluster].clear()
        cluster_to_bombs[my_cluster].clear()
        cluster_to_bombs[new_cluster] = new_cluster_entries
