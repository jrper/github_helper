"""Module running simple JSON based configuration."""

import json

__all__ = ['Configurator']

class Configurator():
    """Simple JSON based configuration."""

    def __init__(self, path='config.json', defaults=None):
        self.path = path
        try:
            with open(self.path, 'r') as configfile:
                self._data = json.load(configfile)
        except FileNotFoundError:
            print(f'Configuration file "{path}" not found. Using defaults.')
            self._data = defaults or {}

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, val):
        self._data[key] = val

    def _save(self):
        with open(self.path, 'w') as configfile:
            json.dump(self._data, configfile)
