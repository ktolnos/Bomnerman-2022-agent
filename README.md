# Bomberland 2022 2nd place agent.

## About

[Bomberland](https://www.gocoder.one/bomberland) is a multi-agent AI competition inspired by the classic console game Bomberman.

Teams build intelligent agents using strategies from tree search to deep reinforcement learning. The goal is to compete in a 2D grid world collecting power-ups and placing explosives to take your opponent down.

This repo contains the source of the Eop's agent which finished 2nd on 2022 season.
Earlier version that finished 1st in 2021 season can be found [here](https://github.com/ktolnos/Bomberland-AI-challange).

![Bomberland multi-agent environment](./engine/bomberland-ui/src/source-filesystem/docs/2-environment-overview/bomberland-preview.gif "Bomberland")

## Usage

### Basic usage

See: [Documentation](https://www.gocoder.one/docs)

1. Clone or download this repo (including both `base-compose.yml` and `docker-compose.yml` files).
1. To connect agents and run a game instance, run from the root directory:

```
docker-compose up --abort-on-container-exit --force-recreate
```
## Code overview

Agent's main logic is called from the [`rule_policy.py`](./agent/rule/rule_policy.py). 
- All agent's files are in [agent/](agent/) folder. 
- <a>agent/parsing/</a> folder contains code for parsing json state object into data classes and populating different maps (e.g. wall map).
- <a>agent/rule/</a> folder contains code for the main policy, including all the strategies. 
    - <a>agent/rule/state</a> contains logic for parsing and updating game state related to this policy.
- <a>agent/search/</a> contains implementations and tests for A\* search and least cost search. The main idea of the latter is to find a trajectory of the fixed length that will have the lowest cost. This allows to avoid dengerous tiles and move towards the sweetest spots.
- <a>agent/simulation/</a> contains code for the simlified forward simulation of the game environment.