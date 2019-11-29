"""Make a qt compatible table from pandas.

Adapted from https://stackoverflow.com/questions/31475965/fastest-way-to-populate-qtableview-from-pandas-data-frame
"""

from qtpy import QtCore


class PandasModel(QtCore.QAbstractTableModel):
    """
    Class to populate a table view with a pandas dataframe
    """
    def __init__(self, data, parent=None):
        QtCore.QAbstractTableModel.__init__(self, parent)
        self._data = data

    def rowCount(self, parent=None):
        del parent
        return len(self._data.values)

    def columnCount(self, parent=None):
        del parent
        if hasattr(self._data, 'columns'):
            return self._data.columns.size
        return 1

    def data(self, index, role=QtCore.Qt.DisplayRole):
        if index.isValid():
            if role == QtCore.Qt.DisplayRole:
                return self._data.values[index.row()][index.column()]
        return None

    def headerData(self, col, orientation, role):
        return_header = (orientation == QtCore.Qt.Horizontal
                         and role == QtCore.Qt.DisplayRole)
        if return_header:
            return self._data.columns[col]
        return None
