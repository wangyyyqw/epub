import os
import sys
import time
import atexit


class logwriter:
    def __init__(self):
        self.path = os.path.join(
            os.path.dirname(os.path.abspath(sys.argv[0])), "log.txt"
        )
        self._file = open(self.path, "w", encoding="utf-8")
        current_time = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(time.time())
        )
        self._file.write(f"time: {current_time}\n")
        self._file.flush()
        atexit.register(self.close)

    def write(self, text):
        self._file.write(f"{text}\n")
        self._file.flush()
        print(text, file=sys.stderr)
        sys.stderr.flush()

    def close(self):
        if self._file and not self._file.closed:
            self._file.close()


if __name__ == "__main__":
    log = logwriter()
    log.write("hello world")
