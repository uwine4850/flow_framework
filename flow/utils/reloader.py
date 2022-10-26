from threading import Thread
import os
import subprocess
import time

"""
Даний модуль реалізує перезавантаження сервера, перезавантаження відбувається лише після збереження будь-якого файлу
створеного проекту. Для запсука сервера из перезавтаженням потрібно ввести команду 'startserver --reloader=True'.
"""


def get_dir_files(path, skipdirs: list[str]=[]) -> dict:
    """
    Рекурсивно виводить файли из вібраної директорії у форматі словника.

    :param path: Вибрана директорія.
    :param skipdirs: Папки які не враховуються.
    :return: dict
    """
    f = []
    files = {}
    for dp in os.listdir(path):
        skip = False
        dpath = os.path.join(path, dp)
        if os.path.isfile(dpath):
            files[dp] = path
        if os.path.isdir(dpath):
            for skipdir in skipdirs:
                if dpath == os.path.join(path, skipdir):
                    skip = True
            if skip:
                continue
            f.append(os.path.join(path, dp))

    for i in f:
        nextfiles = get_dir_files(i, skipdirs)
        for j in nextfiles:
            files[j] = nextfiles[j]

    return files


class CheckFileModification(Thread):
    """
    Запуск потока для рекурсивного прослуховування файлів вибраної директорії на модифікацію.
    """
    def __init__(self, dir_path, skipdirs=[], daemon=None):
        """
        :param dir_path: Директорія для прослуховування.
        :param skipdirs: Папки які не враховуються
        """
        super(CheckFileModification, self).__init__(daemon=daemon)
        self._files = get_dir_files(dir_path, skipdirs)
        self._stop = False

    def get_stat_mtime(self) -> dict:
        """
        Повертає час останбої модифікації файла.
        :return: dict
        """
        pp = []
        for i in self._files:
            pp.append(os.path.join(self._files[i], i))

        stat = {}
        for path in pp:
            stat[path] = os.stat(path).st_mtime
        return stat

    def run(self) -> None:
        """
        Постійний пошук змінених файлів.
        :return:
        """
        gstat = self.get_stat_mtime()
        while not self._stop:
            g2stat = self.get_stat_mtime()
            for i in gstat:
                for j in g2stat:
                    if i == j:
                        # якщо час модифікації не збігаються
                        if gstat[i] != g2stat[i]:
                            curr_statdata = {j.rsplit('/')[-1]: self._files[j.rsplit('/')[-1]]}
                            self.on_trigger(curr_statdata)
                            gstat = self.get_stat_mtime()

    def on_trigger(self, stat: dict):
        """
        Подія при зміні файла.
        """
        pass

    def stop(self):
        self._stop = True


class Reloader(CheckFileModification):
    """
    Поток який реалізує запуск та обробку модифікаї файла.
    """
    def __init__(self, project_path: str, skipdirs: list[str] = [], daemon=None):
        super(Reloader, self).__init__(project_path, skipdirs, daemon=daemon)
        self._proc = None

    def run(self) -> None:
        self._proc = subprocess.Popen(['python3', 'main.py', 'startserver'])
        super(Reloader, self).run()

    def on_trigger(self, stat: dict):
        self._proc.terminate()
        print("Server stopped.")
        self._proc = subprocess.Popen(['python3', 'main.py', 'startserver'])


def start_reloader():
    try:
        Reloader(os.getcwd(), skipdirs=['venv', '.idea', '__pycache__'], daemon=True).start()
        while True:
            time.sleep(1000)
    except KeyboardInterrupt:
        pass
