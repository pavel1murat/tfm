import contextlib
import threading


class Threadable(object):
    def __init__(self, period=1, func=lambda: None, name="threadable"):
        self.ev = threading.Event()
        self.__stop = False
        self.thread = threading.Thread(target=self.main, name=name)
        self.period = period
        self.func = func

    def main(self):
        while not self.__stop:
            self.func()
            self.ev.clear()
            self.ev.wait(self.period)

    def wakeup(self):
        self.ev.set()

    def start(self):
        self.thread.start()

    def stop(self):
        self.__stop = True
        self.wakeup()
        self.thread.join()


@contextlib.contextmanager
def threadable(*args, **kwargs):
    t = Threadable(*args, **kwargs)
    t.start()
    try:
        yield t
    finally:
        t.stop()


@contextlib.contextmanager
def threaded(*args, **kwargs):
    t = threading.Thread(*args, **kwargs)
    t.start()
    try:
        yield
    finally:
        t.join()
