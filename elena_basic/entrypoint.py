import time

from elena.domain.services.elena import get_elena_instance


def main():
    elena = get_elena_instance()
    elena.run()


if __name__ == "__main__":
    while True:
        main()
        print('Sleeping.')
        time.sleep(60)
