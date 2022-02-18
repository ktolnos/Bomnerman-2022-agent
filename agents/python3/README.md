# Plan
- modify alpha zero tic-tac-toe to policy output
- modify alpha zero to parallelize self-play
- look for computation bottlenecks, fix them, maybe rewrite parts to C++ or modify MCTS from EfficientZero
- adopt input and output to bomberman
- make simple bomberman simulator, train for 1 epoch
- optimize

# Overview

`agent.py` - random agent

`agent_fwd.py` - random agent that connects to forward model

`dev_gym.py` - [open ai gym wrapper](https://gym.openai.com/)
