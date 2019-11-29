from collections import deque

from pytest import fixture

from qtpy.QtWidgets import QApplication

from github_helper import gui

class FakeAPI():
    """Mock API class, which allows specifying the faked resposes, returned
    FIFO style.
    """

    def __init__(self):
        self.response_queue = deque()

    def append(self, items):
        for item in items:
            self.response_queue.append(item)

    def __call__(self, url, *args, **kwargs):
        return self.response_queue.popleft()

    def set_token(self, token):
        pass
            

@fixture
def win():
    app = QApplication([])
    return gui.MainWindow(app)

def test_main_window(win):
    assert win
