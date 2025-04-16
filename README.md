# C1GamesStarterKit

Welcome to the C1 Terminal Starter Kit! The repository contains a collection of scripts and
language-specific starter algos, to help you start your journey to develop the ultimate algo.

For more details about competitions and the game itself please check out our
[main site](https://terminal.c1games.com/rules).

# Onboarding Details

Owner : correlation-one/foundational-services

Team : Foundational Services

DeepSource Auto-Onboard : No

DevLake Auto-Onboard : No

## Manual Play

We recommend you familiarize yourself with the game and its strategic elements, by playing manually,
before you start your algo. Check out [the playground](https://terminal.c1games.com/playground).

## Algo Development

To test your algo locally, you should use the test*algo*[OS] scripts in the scripts folder. Details on its use is documented in the README.md file in the scripts folder.

For programming documentation of language specific algos, see each language specific README.
For documentation of the game-config or the json format the engine uses to communicate the current game state, see json-docs.html

For advanced users you can install java and run the game engine locally. Java 10 or above is required: [Java Development Kit 10 or above](http://www.oracle.com/technetwork/java/javase/downloads/jdk10-downloads-4416644.html).

All code provided in the starterkit is meant to be used as a starting point, and can be overwritten completely by more advanced players to improve performance or provide additional utility.

## Windows Setup

If you are running Windows, you will need Windows PowerShell installed. This comes pre-installed on Windows 10.
Some windows users might need to run the following PowerShell commands in administrator mode (right-click the
PowerShell icon, and click "run as administrator"):

    `Set-ExecutionPolicy Unrestricted`

If this doesn't work try this:

    `Set-ExecutionPolicy Unrestricted CurrentUser`

If that still doesn't work, try these below:

    `Set-ExecutionPolicy Bypass`
    `Set-ExecutionPolicy RemoteSigned`

And don't forget to run the PowerShell as admin.

## Uploading Algos

Simply select the folder of your algo when prompted on the [Terminal](https://terminal.c1games.com) website. Make sure to select the specific language folder such as "python-algo" do not select the entire starterkit itself.

## Troubleshooting

For detailed troubleshooting help related to both website problems and local development check out [the troubleshooting section](https://terminal.c1games.com/rules#Troubleshooting).

#### Python Requirements

Python algos require Python 3 to run. If you are running Unix (Mac OS or Linux), the command `python3` must run on
Bash or Terminal. If you are running Windows, the command `py -3` must run on PowerShell.

#### Java Requirements

Java algos require the Java Development Kit. Java algos also require [Gradle]
(https://gradle.org/install/) for compilation.

## Running Algos

To run your algo locally or on our servers, or to enroll your algo in a competition, please see the [documentation
for the Terminal command line interface in the scripts directory](https://github.com/correlation-one/AIGamesStarterKit/tree/master/scripts)

# Terminal Game Strategy Guide

## Overview

This is a strategy game where you build defenses and launch attacks against your opponent. The game is played on a grid-based map where you can place structures and spawn units.

## Game Elements

### Units and Structures

- **WALL**: Basic defensive structure (cheap, blocks movement)
- **SUPPORT**: Boosts nearby units (increases damage/health)
- **TURRET**: Defensive structure that attacks enemies
- **SCOUT**: Fast, weak offensive unit (good for quick attacks)
- **DEMOLISHER**: Strong offensive unit (good against structures)
- **INTERCEPTOR**: Defensive unit (good against mobile units)

### Resources

- **MP (Movement Points)**: Used to spawn mobile units (Scouts, Demolishers, Interceptors)
- **SP (Structure Points)**: Used to build structures (Walls, Supports, Turrets)

## Strategy Components

### Main Strategy Flow

1. **Early Game (Turns 1-5)**

   - Build basic defenses
   - Use interceptors to stall
   - Gather information about enemy base

2. **Mid Game (Turns 6-20)**

   - Build advanced defenses
   - Start offensive units
   - React to enemy strategies

3. **Late Game (Turns 21+)**
   - Focus on offense
   - Maintain defenses
   - Exploit enemy weaknesses

### Key Methods to Modify

- `on_turn`: Main game loop, called every turn
- `starter_strategy`: Current strategy implementation
- `build_defences`: Place defensive structures
- `build_reactive_defense`: Respond to enemy attacks
- `stall_with_interceptors`: Early game strategy
- `demolisher_line_strategy`: Offensive strategy

## Getting Started

### 1. Setup Your Environment

```bash
# Clone the repository
git clone <repository-url>

# Navigate to the project directory
cd citadel_terminal

# Make the test script executable
chmod +x scripts/test_algo_mac
```

### 2. Testing Your Strategy

```bash
# Quick test (runs against a test replay)
./scripts/test_algo_mac python-algo

# Full game test (runs against itself)
python3 ./scripts/run_match.py python-algo python-algo
```

### 3. Viewing Replays

1. Go to https://terminal.c1games.com/playground
2. Click "Upload Replay"
3. Select the replay file from the `replays` directory

## Strategy Tips

### Defense

- Place walls in front of turrets to protect them
- Use supports to boost your defensive structures
- Build reactive defenses where you get scored on

### Offense

- Use scouts for quick attacks
- Use demolishers against enemy structures
- Find the least defended path to attack

### Resource Management

- Balance MP and SP usage
- Don't overspend on early game defenses
- Save resources for critical moments

## Common Strategies

### Defensive Strategy

1. Build a strong wall line
2. Place turrets behind walls
3. Use supports to boost defenses
4. Use interceptors to defend against attacks

### Aggressive Strategy

1. Build minimal defenses
2. Focus on scout production
3. Attack early and often
4. Use demolishers to break through defenses

### Balanced Strategy

1. Build moderate defenses
2. Mix scout and demolisher attacks
3. Adapt to enemy strategy
4. Maintain resource balance

## Debugging

- Use `gamelib.debug_write()` to print debug information
- Check the game logs for errors
- Test against different strategies

## Next Steps

1. Start with a basic strategy
2. Test against the starter algo
3. Analyze replays to find weaknesses
4. Iterate and improve your strategy

## Resources

- Official Documentation: https://terminal.c1games.com/rules
- Community Forums: https://terminal.c1games.com/forum
- Strategy Guides: https://terminal.c1games.com/guides
