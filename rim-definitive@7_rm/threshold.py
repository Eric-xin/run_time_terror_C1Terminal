class ThresholdEstimator:
    def __init__(self, initial_max_mana: float, D_min: float = 9):
        """
        Estimates the opponent's mana threshold for a big attack,
        using only start-of-turn mana observations.

        Args:
            initial_max_mana: Upper bound on possible threshold.
            D_min: Minimum spend difference that counts as a 'big attack'.
        """
        # Bounds: true threshold T satisfies L < T <= U
        self.L = 0
        self.U = initial_max_mana
        self.D_min = D_min
        self.last_mana = None  # previous turn's post-action mana

    def observe(self, current_mana: float) -> None:
        """
        Update interval bounds given a new mana observation.

        Call this at the start of your turn, passing the opponent's
        current mana (after their action).

        Args:
            current_mana: Opponent's mana at the start of your turn.
        """
        if self.last_mana is not None:
            # Net change = gain - spend; a large drop implies a big attack
            net_change = current_mana - self.last_mana
            if net_change <= -self.D_min:
                # Big attack observed: threshold <= last_mana
                self.U = min(self.U, self.last_mana)
            else:
                # No big attack: threshold > last_mana
                self.L = max(self.L, self.last_mana)

        # Store for next observation
        self.last_mana = current_mana

    def threshold(self) -> float:
        """
        Returns the current upper-bound estimate of the opponent's threshold.
        """
        return round((self.U + self.L) / 2, 1)

    def confidence_interval(self) -> tuple[float, float]:
        """
        Returns the current (L, U] interval for the threshold.
        """
        return (self.L, self.U)

    def confidence_width(self) -> float:
        """
        Returns the current width of the confidence interval for the threshold.
        """
        return self.U - self.L


if __name__ == "__main__":
    import random

    # Test example: simulate an opponent with a secret threshold
    random.seed(42)


    opponent_mana_after_turn = [
            5,
            10,
            8,
            10,
            7,
            10,
            9,
            15,
            2,
            3,
            9,
            13,
            0,
            1.3,
            4.6,
            2,
            9,
            11.9,
            12.9,
            0.9,
            4,
            5
            ]

    estimator = ThresholdEstimator(initial_max_mana=100, D_min=7)
    last_mana = 0

    print("CURRENT MP ----- THRESHOLD INTERVAL")
    for i in opponent_mana_after_turn:
        estimator.observe(i)
        print(i, " ", estimator.confidence_interval())
