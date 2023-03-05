from runner import Runner


class EmptyPolicy:
    def init(self, gs):
        pass

    def execute_actions(self, tick, gs):
        pass


def main():
    Runner(EmptyPolicy())


if __name__ == "__main__":
    main()
