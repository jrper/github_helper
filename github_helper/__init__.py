from .apitool import *
from .config import *
from .table import *

def run():
    import sys
    from qtpy.QtWidgets import QApplication
    
    from .gui import MainWindow

    app = QApplication(sys.argv)
    win = MainWindow(app)
    win.show()
    
    sys.exit(app.exec_())
    
