#!/usr/bin/env python3
import os, sys, subprocess, io, csv, re, uuid, multiprocessing
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import mainwindow

rule_VAR = re.compile(r'^[A-Z_]+\s*=.*')

def argv2str(argv):
    return '\x20'.join(map(lambda i: ("'%s'"%i) if '\x20' in i else i, argv))

def parse_dockerpy(fname):
    r = dict()
    lines = []
    with open(fname) as f:
        s = 0
        for line in f:
            _line = line.rstrip()
            if _line and (s or rule_VAR.match(_line)):
                lines.append(_line); s = 1
            else: s = 0
    
    eval_script = r"""{}
ARGV = [DOCKER, 'run', DOCKER_RUN] + PORTS + VOLUMNS + [IMAGE]
""".format('\n'.join(lines))
    
    try:
        def child(workspace, script, ret):
            os.chdir(workspace)
            exec(script)
            ret.put({k:v for k,v in locals().items() if re.match('^[A-Z_]+$', k)})
        queue = multiprocessing.Queue()
        p = multiprocessing.Process(target=child, args=(os.path.dirname(fname), eval_script, queue))
        p.start()
        ret = queue.get()
        queue.close()
        ret['cmd'] = argv2str(ret['ARGV'])
        return ret
    except: pass

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = mainwindow.Ui_MainWindow()
        self.ui.setupUi(self)

        modelShortcuts = QStandardItemModel(self.ui.listViewShortcuts)
        for shortcut in get_shortcuts():
            item = QStandardItem(os.path.realpath(shortcut))
            modelShortcuts.appendRow(item)
        self.ui.listViewShortcuts.setModel(modelShortcuts)
        self.ui.listViewShortcuts.selectionModel().selectionChanged.connect(self.script_selected)

        self.ui.statusbar.showMessage("Ready")

    def script_selected(self, new_selection, old_selection):
        scripts = [i.data() for i in new_selection.first().indexes()]
        if scripts and os.path.exists(scripts[0]):
            fname = scripts[0]
            variables = parse_dockerpy(fname)
            if variables:
                self.ui.lineEditScript.setText(fname)
                self.ui.lineEditCWD.setText(os.path.dirname(fname))
                self.ui.lineEditDocker.setText(variables['DOCKER'])
                self.ui.lineEditImage.setText(variables['IMAGE'])
                self.ui.lineEditPorts.setText(argv2str(variables['PORTS']))
                self.ui.lineEditVolumns.setText(argv2str(variables['VOLUMNS']))
                self.ui.plainTextEditDockerCommand.setPlainText(variables['cmd'])
            else:
                pass

def get_shortcuts():
    for _fname in os.listdir(PATH_SHORTCUTS):
        fname = os.path.join(PATH_SHORTCUTS, _fname)
        if os.path.islink(fname):
            yield fname

def check_dir(pth):
    if not os.path.isdir(pth):
        if os.path.exists(pth):
            print('ERR: path "%s" has been occupied.' % pth, file=sys.stderr)
            return False
        else: os.makedirs(pth)
    return True

if __name__ == '__main__':
    PATH_SHORTCUTS = os.path.expanduser('~/.docker-script')
    if not all(list(map(check_dir, [PATH_SHORTCUTS]))):
        sys.exit(1)
    app = QApplication(sys.argv)
    my_mainWindow = MainWindow()
    my_mainWindow.show()
    sys.exit(app.exec_())
