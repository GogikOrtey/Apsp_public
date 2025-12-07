import sys

class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()

    def flush(self):
        for f in self.files:
            f.flush()

# Открываем файл для логов
log_file = open("output.log", "a", encoding="utf-8")

# Подменяем stdout
sys.stdout = Tee(sys.stdout, log_file)

from datetime import datetime
now = datetime.now()
print(now.strftime("%d.%m.%Y %H:%M:%S"))
print("")