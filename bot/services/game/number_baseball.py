class NumberBaseball:
    def __init__(self, digits=3):
        self.digits = digits
        self.secret_number = self._generate_secret_number()
        self.trials = self._calculate_num_trials(digits)
        self.attempts = 0
        self.number_group_one = ["0", "1", "3", "6", "7", "8"]
        self.number_group_two = ["2", "4", "5", "9"]

    def _calculate_num_trials(self, digits):
        if digits == 3:
            return 7
        else:
            return digits * 2 - 1

    def _generate_secret_number(self):
        from random import sample

        return ''.join(sample('0123456789', self.digits))

    def guess(self, number):
        if len(number) != self.digits or not number.isdigit():
            raise ValueError(f"Please enter a {self.digits}-digit number.")

        strikes = sum(1 for a, b in zip(self.secret_number, number) if a == b)
        balls = sum(1 for digit in number if digit in self.secret_number) - strikes

        self.attempts += 1
        return strikes, balls
