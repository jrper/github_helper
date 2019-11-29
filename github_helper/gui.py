"""Module generating a Qt Graphical User Interface to bulk
interact with GitHub.
"""

import os
import pathlib
import re
import sys
import webbrowser

import pandas as pd
from qtpy import QtWidgets, QtCore, QtGui

from . import GithubAPI, Configurator, PandasModel


def matching_repositories(repos, pattern, show_archived=False):
    if type(repos) is not pd.DataFrame:
        repos = pd.io.json.json_normalize(repos, max_level=0)
        
    template = re.escape(pattern)
    template = template.replace(r'\*', '.*')
    template = template.replace(r'\?', '.')
    template = template.replace(r'\[', '[')
    template = template.replace(r'\]', ']')
    template = template.replace(r'\-', '-')

    idx = repos.name.str.contains(f'^{template}$')
    if not show_archived:
        idx &= ~repos.archived
        
    return repos.loc[idx]


class Pager(QtCore.QObject):
    finished = QtCore.Signal()
    progress = QtCore.Signal(int)

    def __init__(self, api, endpoint, data, maxlen):
        super().__init__()
        self.api = api
        self.endpoint = endpoint
        self.data = data
        self.maxlen = maxlen

    @QtCore.Slot()
    def run(self):

        interrupt = QtCore.QThread.currentThread().isInterruptionRequested

        page = 0
        self.api(self.endpoint)
        while self.maxlen - len(self.data) > 0 and not interrupt():
            page += 1
            page_endpoint = f'{self.endpoint}?page={page}&per_page=50'
            self.data += self.api(page_endpoint)
            self.progress.emit(len(self.data))

        self.finished.emit()


class ProgressDialog(QtWidgets.QProgressDialog):
    """Create and show a progress bar dialog, connected to a
    worker process to be run in another thread.
    """

    def __init__(self, worker, *args,
                 label='',
                 canceled_callback=None,
                 finished_callback=None,
                 **kwargs):

        super().__init__(*args, **kwargs)

        self.setLabel(QtWidgets.QLabel(label))
        self.worker = worker
        self.worker.progress.connect(self.setValue)
        if canceled_callback:
            self.canceled.connect(canceled_callback)
        if finished_callback:
            self.worker.finished.connect(finished_callback)

        self.thread = QtCore.QThread()
        self.worker = worker
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)

    def start(self):
        self.thread.start()

    def quit(self):
        self.thread.quit()

    def interrupt(self):
        self.thread.requestInterruption()


class Popup(QtWidgets.QWidget):
    def __init__(self, *widgets, title='', bbox=None, parent=None):
        super().__init__(parent=parent)
        self.setWindowTitle(title)

        self.setAttribute(QtCore.Qt.WA_QuitOnClose, False)

        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        for wgt in widgets:
            if issubclass(type(wgt), QtWidgets.QWidget):
                self.layout.addWidget(wgt)
            elif issubclass(type(wgt), QtWidgets.QLayout):
                self.layout.addLayout(wgt)
            else:
                raise TypeError

        if bbox:
            self.layout.addWidget(bbox)
            bbox.accepted.connect(self.deleteLater)
            bbox.rejected.connect(self.deleteLater)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, app=None, parent=None):
        super().__init__(parent)

        self.app = app
        self.app.setFont(QtGui.QFont("Lucida Grande", 12))
        
        self.setWindowTitle("Github Helper")

        defaults = {'token': None,
                    'Default Type': 'Organization',
                    'Default GitHub Identity': 'fluidityproject',
                    'Default Repository Pattern': '*'}

        home = pathlib.Path.home()
        path = home.joinpath('.config', 'github_helper')
        try: 
            os.makedirs(path)
        except FileExistsError:
            pass
        path = path.joinpath('config.json')
        
        self.config = Configurator(str(path), defaults)
        self.api = GithubAPI(error_handler=self._error)

        widget = QtWidgets.QWidget()
        self.setCentralWidget(widget)
        self.layout = QtWidgets.QVBoxLayout()
        widget.setLayout(self.layout)

        groupbox = QtWidgets.QGroupBox("Type:")
        radios = [QtWidgets.QRadioButton("Organization"),
                      QtWidgets.QRadioButton("User")]
        self.is_org = radios[0].isChecked
        if self.config['Default Type'] == "Organization":
            radios[0].setChecked(1)
        else:
            radios[1].setChecked(1)
        hbox = QtWidgets.QHBoxLayout()
        for radio in radios:
            hbox.addWidget(radio)
        groupbox.setLayout(hbox)
        self.layout.addWidget(groupbox)

        self.grid = QtWidgets.QGridLayout()
        self.grid.setColumnStretch(1, 5)
        self.grid.setColumnStretch(1, 20)
        self.grid.setColumnStretch(2, 1)

        label0 = QtWidgets.QLabel()
        label0.setText('GitHub Identity:')
        self.grid.addWidget(label0, 0, 0)
        self._identity = QtWidgets.QLineEdit()
        self._identity.setText(self.config['Default GitHub Identity'])
        self.grid.addWidget(self._identity, 0, 1)

        label1 = QtWidgets.QLabel()
        label1.setText('Repository Pattern:')
        self.grid.addWidget(label1, 1, 0)
        self._repo_pattern = QtWidgets.QLineEdit()
        self._repo_pattern.setText(self.config['Default Repository Pattern'])
        self.grid.addWidget(self._repo_pattern, 1, 1)

        self.layout.addLayout(self.grid)

        self.buttons = []

        self._add_button("Configure Helper Settings", self._config)
        self._add_button("Search for Matching Repositories", self._search)
        self._add_button("Archive Matching Repositories", self._archive)
        self._add_button("Change Team Settings", self._teams)
        self._add_button("Modify Branch Protections", self._protect)
        self._add_button("Help", self._help)

        for button in self.buttons:
            self.layout.addWidget(button)

    def _add_button(self, label, func=None):
        button = QtWidgets.QPushButton(label)
        if func:
            button.clicked.connect(func)
        self.buttons.append(button)

    def _archive(self):
        self.repos = []
        self._do_search(self.repos, self._confirm_archive)

    def _confirm_archive(self):
        self.progress.quit()
        self.progess = None

        self.repos = matching_repositories(self.repos, self.pattern)
        self.repos = self.repos.sort_values('name')

        N = len(self.repos.index)

        label = QtWidgets.QLabel()
        label.setText((f"Archive {N} repositories?\n"
                       + "Double click repository to view on GitHub."))
        label2 = QtWidgets.QLabel()
        label2.setText(("Warning, this can only be undone by hand. "
                        + "Please check the list above carefully."))

        confirmation = QtWidgets.QRadioButton("Confirm this operation")

        model = PandasModel(self.repos[['name']])
        table = QtWidgets.QListView()
        table.setModel(model)
        table.doubleClicked.connect(self._open_repo)
        
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok |
                                             QtWidgets.QDialogButtonBox.Cancel)
        ok =  buttons.button(QtWidgets.QDialogButtonBox.Ok)
        ok.setEnabled(False)
        
        confirmation = QtWidgets.QCheckBox("Confirm this operation")
        confirmation.toggled.connect(ok.setEnabled)

        self.search_popup = Popup(label, table, label2, confirmation,
                                  title="Archive Repositories", bbox=buttons)
        buttons.accepted.connect(self._do_archive)

        self.search_popup.show()   

    def _do_archive(self):
        self.api.set_token(self.config['token'])
        for repo in self.repos.name:
            print(self.api(f'/repos/{self.owner}/{repo}',
                           archived=True,
                           http_method="PATCH"))

    def _config(self):

        self.configgrid = QtWidgets.QGridLayout()

        for count, (key, val) in enumerate(self.config._data.items()):
            label = QtWidgets.QLabel()
            label.setText(key)
            text = QtWidgets.QLineEdit()
            text.setText(val)
            self.configgrid.addWidget(label, count, 0)
            self.configgrid.addWidget(text, count, 1)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok |
                                             QtWidgets.QDialogButtonBox.Cancel)

        widget = QtWidgets.QWidget()
        buttons.accepted.connect(self._saveconfig)
        widget.setLayout(self.configgrid)
        self.config_popup = Popup(widget, title="Configuration",
                                  bbox=buttons)
        self.config_popup.show()

    def _saveconfig(self):

        for i in range(self.configgrid.rowCount()):
            label = self.configgrid.itemAtPosition(i, 0).widget()
            text = self.configgrid.itemAtPosition(i, 1).widget()
            self.config[label.text()] = text.text()
        self.config._save()

    def _error(self, error):

        label = QtWidgets.QLabel()

        if error.code == 404:
            text = f"Url not found:\n\t{error.url}"
        elif error.code == 401:
            text = f"Authentication failed. Check token"
        else:
            print(error)
            text = error.msg

        label.setText(text)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)

        self.error_popup = Popup(label, title="Error",
                                 bbox=buttons)
        self.error_popup.show()

    def _help(self):

        helpfile = os.sep.join((os.path.dirname(__file__) or '.',
                                "help.html"))

        self.help_window = QtWidgets.QTextBrowser()
        self.help_window.resize(600, 400)
        self.help_window.setAttribute(QtCore.Qt.WA_QuitOnClose, False)
        self.help_window.setWindowTitle("Help")
        self.help_window.setSource(QtCore.QUrl(helpfile))
        self.help_window.setOpenLinks(False)
        self.help_window.anchorClicked.connect(self._help_open_external)
        self.help_window.show()

    def _help_open_external(self, qurl):
        if qurl.scheme():
            webbrowser.open(qurl.url())
        else:
            self.help_window.setSource(qurl)

    @property
    def owner(self):
        return self._identity.text()
            
    @property
    def identity(self):

        if self.is_org():
            return f"/orgs/{self.owner}"
        else:
            return f"/users/{self.owner}"

    @property
    def pattern(self):
        return self._repo_pattern.text()

    def _protect(self):
        self.repos = []
        self._do_search(self.repos, self._configure_protect)

    def _configure_protect(self):
        self.progress.quit()
        self.progess = None

        self.repos = matching_repositories(self.repos, self.pattern, True)
        repos = self.repos.sort_values('name')

        label = QtWidgets.QLabel()
        label.setText((f"{len(repos.index)} repositories found.\n"
                       + "Double click repository to view on GitHub."))

        model = PandasModel(repos[['name']])
        table = QtWidgets.QListView()
        table.setModel(model)
        table.doubleClicked.connect(self._open_repo)


        hbox = QtWidgets.QHBoxLayout()
        
        label2 = QtWidgets.QLabel()
        label2.setText((f"branch name"))
        hbox.addWidget(label2)
        
        self.branch_select = QtWidgets.QLineEdit()
        self.branch_select.setText("master")

        hbox.addWidget(self.branch_select)

        self.force_prs = QtWidgets.QCheckBox("Force using pull requests to merge")
        self.force_travis = QtWidgets.QCheckBox("Force passing Travis checks to merge")

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Apply|
                                             QtWidgets.QDialogButtonBox.Cancel)
        applybutton = buttons.button(QtWidgets.QDialogButtonBox.Apply)
        applybutton.clicked.connect(self._do_protect)

        self.protect_popup = Popup(label, table, hbox,
                                   self.force_prs, self.force_travis,           
                                  title="Branch protections", bbox=buttons)
        applybutton.clicked.connect(self.protect_popup.deleteLater)
        self.protect_popup.show()

    def _do_protect(self):
        branch = self.branch_select.text()
        
        for repo in self.repos.name:
            base_url = f"/repos/{self.owner}/{repo}/branches/{branch}"

            pr_url = base_url + '/protection'
            if self.force_prs.isChecked():
                prs = {'dismissal_restrictions': {},
                       'dismiss_stale_reviews':True,
                       'require_code_owner_reviews':False
                      }
            else:
                prs = None
            if self.force_travis.isChecked():
                checks = {'strict': True,
                          'contexts': ["continuous-integration/travis-ci"]
                          }
            else:
                checks = None
            self.api(pr_url,
                     http_method="PUT",
                     required_status_checks=checks,
                     enforce_admins=None,
                     required_pull_request_reviews=prs,
                     restrictions=None
                    )
            
        
    def _search(self):
        self.repos = []
        self._do_search(self.repos, self._display_search)

    def _do_search(self, data, callback):

        self.api.set_token(self.config['token'])
        identity_info = self.api(self.identity)
        repo_count = (identity_info['public_repos']
                      + identity_info.get('total_private_repos', 0))

        pager = Pager(self.api,
                      self.identity+'/repos',
                      data, repo_count)

        label = f"Checking {repo_count} repositories"
        self.progress = ProgressDialog(pager,
                                       label=label,
                                       canceled_callback=self._cancel_search,
                                       finished_callback=callback,
                                       parent=self)
        self.progress.setRange(0, repo_count)
        self.progress.show()
        self.progress.start()

    def _cancel_search(self):
        self.progress.worker.finished.disconnect()
        self.progress.interrupt()
        self.progress = None
        self._skip_search = True

    def _display_search(self):
        self.progress.quit()
        self.progess = None

        self.repos = matching_repositories(self.repos, self.pattern, True)
        repos = self.repos.sort_values('name')

        label = QtWidgets.QLabel()
        label.setText((f"{len(repos.index)} repositories found.\n"
                       + "Double click repository to view on GitHub."))

        model = PandasModel(repos[['name']])
        table = QtWidgets.QListView()
        table.setModel(model)

        table.doubleClicked.connect(self._open_repo)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)

        self.search_popup = Popup(label, table,
                                  title="Matching Repositories", bbox=buttons)
        self.search_popup.show()

    def _open_repo(self, index):
        repos = self.repos.sort_values('name')
        repo = repos.html_url.iloc[index.row()]
        webbrowser.open(repo)

    def _teams(self):

        self.api.set_token(self.config['token'])
        teams = self.api(self.identity+'/teams?per_page=100')
        teams = pd.io.json.json_normalize(teams, max_level=0)
        self._teams = teams.set_index('name').sort_index()

        label = QtWidgets.QLabel(f"""Using pattern "{self.pattern}".
Team to modify:""")

        comboBox = QtWidgets.QComboBox()
        self.team = teams.name.iloc[0]
        self.team_id = teams.id.iloc[0]
        for name in self._teams.index:
            comboBox.addItem(name)

        comboBox.activated[str].connect(self._setTeam)

        view_team = QtWidgets.QPushButton("View Team on Web")
        view_team.clicked.connect(self._view_team)
        
        add_team = QtWidgets.QPushButton("Add Team to Repositories")
        add_team.clicked.connect(self._add_team)

        remove_team = QtWidgets.QPushButton("Remove Team from Repositories")
        remove_team.clicked.connect(self._remove_team)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Cancel)

        self.search_popup = Popup(label, comboBox,
                                  view_team,
                                  add_team,
                                  remove_team,
                                  title="Choose Team", bbox=buttons)
        self.search_popup.show()

    def _setTeam(self, team):
        self.team = team
        self.team_id = self._teams.loc[self.team]['id']

    def _view_team(self):
        print(self._teams)
        webbrowser.open(self._teams.loc[self.team]['html_url'])
        
    def _add_team(self):
        self.repos = []
        self.team_repos = self.api(f'/teams/{self.team_id}/repos?per_page=200')
        if self.team_repos:
            self.team_repos = pd.io.json.json_normalize(self.team_repos,
                                                        max_level=0)
        else:
            self.team_repos = pd.DataFrame(columns=['id'])
        
        self._do_search(self.repos, self._confirm_add_team)

    def _confirm_add_team(self):
        self.progress.quit()
        self.progess = None

        self.repos = matching_repositories(self.repos, self.pattern)
        print(self.repos.columns)
        self.repos = self.repos.loc[~self.repos.id.isin(self.team_repos.id)]
        self.repos = self.repos.sort_values('name')

        N = len(self.repos.index)

        label = QtWidgets.QLabel()
        label.setText((f"Add team {self.team} to {N} repositories?\n"
                       + "Double click repository to view on GitHub."))

        model = PandasModel(self.repos[['name']])
        table = QtWidgets.QListView()
        table.setModel(model)

        table.doubleClicked.connect(self._open_repo)

        groupbox = QtWidgets.QGroupBox("Permission:")
        self.team_permission = QtWidgets.QButtonGroup()
        radios = [QtWidgets.QRadioButton("Pull"),
                           QtWidgets.QRadioButton("Push"),
                           QtWidgets.QRadioButton("Admin")]
        radios[0].setChecked(1)
        hbox = QtWidgets.QHBoxLayout()
        for key, radio in enumerate(radios):
            self.team_permission.addButton(radio)
            self.team_permission.setId(radio, key)
            hbox.addWidget(radio)
        groupbox.setLayout(hbox)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok |
                                             QtWidgets.QDialogButtonBox.Cancel)

        self.search_popup = Popup(label, table, groupbox,
                                  title="Add Team", bbox=buttons)
        buttons.accepted.connect(self._do_add_team)

        self.search_popup.show()

    def _do_add_team(self):
        owner = self._identity.text()
        permission = ('pull', 'push', 'admin')[self.team_permission.checkedId()]
        print(self._teams.columns)
        self.api.set_token(self.config['token'])
        for repo in self.repos.name:
            print(self.api(f'/teams/{self.team_id}/repos/{owner}/{repo}',
                           http_method='PUT',
                           permission=permission))

    def _remove_team(self):
        self.repos = []
        self.team_repos = self.api(f'/teams/{self.team_id}/repos?per_page=200')
        self.team_repos=pd.io.json.json_normalize(self.team_repos,
                                                  max_level=0)
        self._do_search(self.repos, self._confirm_remove_team)

    def _confirm_remove_team(self):
        self.progress.quit()
        self.progess = None

        self.repos = matching_repositories(self.repos, self.pattern)
        self.repos = self.repos.loc[self.repos.id.isin(self.team_repos.id)]
        self.repos = self.repos.sort_values('name')

        N = len(self.repos.index)

        label = QtWidgets.QLabel()
        label.setText((f"Remove team {self.team} from {N} repositories?\n"
                       + "Double click repository to view on GitHub."))

        model = PandasModel(self.repos[['name']])
        table = QtWidgets.QListView()
        table.setModel(model)
        table.doubleClicked.connect(self._open_repo)
        
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok |
                                             QtWidgets.QDialogButtonBox.Cancel)

        self.search_popup = Popup(label, table,
                                  title="Remove Team", bbox=buttons)
        buttons.accepted.connect(self._do_remove_team)

        self.search_popup.show()        

    def _do_remove_team(self):
        owner = self._identity.text()
        for repo in self.repos.name:
            self.api(f'/teams/{self.team_id}/repos/{owner}/{repo}',
                     http_method="DELETE")
