# uci_match_runner.py

import chess.pgn
import chess.engine
import tempfile
import os
import time
from pathlib import Path


class UCIMatchRunner:
    def __init__(self, engine1_path, engine2_path, time_limit=0.1):
        self.engine1_path = engine1_path
        self.engine2_path = engine2_path
        self.time_limit = time_limit  # Seconds per move

    def run_match(self):
        print(f"\nStarting match between:\n  A: {self.engine1_path}\n  B: {self.engine2_path}\n")

        # Create a new game
        game = chess.pgn.Game()
        game.headers["White"] = Path(self.engine1_path).name
        game.headers["Black"] = Path(self.engine2_path).name

        board = chess.Board()
        node = game

        with chess.engine.SimpleEngine.popen_uci(self.engine1_path) as engine1, \
             chess.engine.SimpleEngine.popen_uci(self.engine2_path) as engine2:

            engines = [engine1, engine2]
            move_count = 0

            while not board.is_game_over():
                current_engine = engines[move_count % 2]
                result = current_engine.play(board, chess.engine.Limit(time=self.time_limit))
                board.push(result.move)
                node = node.add_variation(result.move)
                move_count += 1

        game.headers["Result"] = board.result()
        print("Game result:", board.result())
        return game

    def save_pgn(self, game, out_path):
        with open(out_path, "w") as f:
            f.write(str(game))
        print(f"Game saved to {out_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run UCI engine vs engine match")
    parser.add_argument("--engineA", required=True, help="Path to first UCI engine (plays White)")
    parser.add_argument("--engineB", required=True, help="Path to second UCI engine (plays Black)")
    parser.add_argument("--time", type=float, default=0.1, help="Time limit per move (seconds)")
    parser.add_argument("--pgn", default="game.pgn", help="Output PGN file")

    args = parser.parse_args()

    runner = UCIMatchRunner(args.engineA, args.engineB, time_limit=args.time)
    game = runner.run_match()
    runner.save_pgn(game, args.pgn)
