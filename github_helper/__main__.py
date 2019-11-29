import sys

from qtpy import QtWidgets, QtGui

from .gui import MainWindow


app = QtWidgets.QApplication(sys.argv)
app.setFont(QtGui.QFont("Lucida Grande", 12))
win = MainWindow()
win.show()

sys.exit(app.exec_())
