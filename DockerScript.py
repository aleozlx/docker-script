#!/usr/bin/env python3
import os, sys, subprocess, io, csv, re, uuid, linecache
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import mainwindow

def get_gpuinfo(query):
    output = subprocess.getoutput('nvidia-smi --query-gpu=%s --format=csv'%query)
    return [row for row in csv.reader(io.StringIO(output), delimiter=',')][1:]

def percentage2int(s_percent):
    m = re.match(r'^\s*(\d+)\s*%\s*$', s_percent)
    return int(m.group(1)) if m else 0

rules = {
    'DOCKER': re.compile(r'^DOCKER\s*=\s*(.*)$')
}

def parse_dockerpy(fname):
    r = dict()
    with open(fname) as f:
        for line in f:
            m = rules['DOCKER'].match(line)
            if m:
                r['DOCKER'] = eval(m.group(1))
                break
    return r

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
        
        # timer_GPU = QtCore.QTimer(self)
        # timer_GPU.timeout.connect(self.poll_GPU)
        # timer_GPU.start(1000)
        # self.poll_GPU()

    def script_selected(self, new_selection, old_selection):
        scripts = [i.data() for i in new_selection.first().indexes()]
        if scripts and os.path.exists(scripts[0]):
            fname = scripts[0]
            print(parse_dockerpy(fname))
        
    def poll_GPU(self):
        gpuinfo = get_gpuinfo('name,compute_mode,utilization.gpu,utilization.memory')
        print(gpuinfo)
        self.ui.label_GPU_name.setText(gpuinfo[0][0])
        self.ui.progressBar_GPU_util.setValue(percentage2int(gpuinfo[0][2]))
        self.ui.progressBar_GPU_mem.setValue(percentage2int(gpuinfo[0][3]))

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
