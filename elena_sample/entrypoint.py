from elena.config import dependency_injection
from elena.constants import VERSION
from elena.adapters.config.local_config_reader import LocalConfigReader

from elena_sample.strategy_trailing_stop_with_bb.trailing_stop_bb import TrailingStopLossBBbuyAfterSleep

def main():
    print('Hello World!')
    x = TrailingStopLossBBbuyAfterSleep()
    print(x)

    config = LocalConfigReader().config
    container = dependency_injection.get_container(config)
    container.wire(modules=[__name__])
    elena = container.elena()
    print(f"Starting Elena v{VERSION} from CLI")
    elena.run()


if __name__ == "__main__":
    main()
