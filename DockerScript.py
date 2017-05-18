#!/usr/bin/env python3
import os, sys, subprocess, io, csv, re, uuid, multiprocessing, subprocess
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import mainwindow

rule_VAR = re.compile(r'^[A-Z_]+\s*\+?=.*')

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

def shell_stream(cmd):
    with subprocess.Popen(cmd, stdout=subprocess.PIPE) as proc:
        for line in proc.stdout:
            yield str(str(line, encoding = 'utf-8').rstrip())

def mk_list_standard_model(ui_list, data):
    model = QStandardItemModel(ui_list)
    for i in data:
        model.appendRow(QStandardItem(i))
    return model

def get_gpuinfo(query):
    output = subprocess.getoutput('nvidia-smi --query-gpu=%s --format=csv'%query)
    return [row for row in csv.reader(io.StringIO(output), delimiter=',')][1:]

def get_gpuprocesses(query):
    # nvidia-smi --query-compute-apps=pid,name,used_gpu_memory --format=csv
    output = subprocess.getoutput('nvidia-smi --query-compute-apps=%s --format=csv'%query)
    return [row for row in csv.reader(io.StringIO(output), delimiter=',')][1:]

def percentage2int(s_percent):
    m = re.match(r'^\s*(\d+)\s*%\s*$', s_percent)
    return int(m.group(1)) if m else 0

class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = mainwindow.Ui_MainWindow()
        self.ui.setupUi(self)

        self.ui.listViewShortcuts.setModel(mk_list_standard_model(self.ui.listViewShortcuts, get_shortcuts()))
        self.ui.listViewShortcuts.selectionModel().selectionChanged.connect(self.on_script_selected)

        self.on_reload_images()
        self.on_reload_containers()

        self.ui.pushButtonRun.clicked.connect(self.on_run)
        self.ui.pushButtonImagesReload.clicked.connect(self.on_reload_images)
        self.ui.pushButtonContainersReload.clicked.connect(self.on_reload_containers)
        self.variables = None

        timerGPU = QTimer(self)
        timerGPU.timeout.connect(self.on_GPU_update)
        timerGPU.start(1000)
        self.on_GPU_update()
        self.state = 'Initialized'

    def on_GPU_update(self):
        gpuinfo = get_gpuinfo('name,compute_mode,utilization.gpu,utilization.memory')
        # print(gpuinfo)
        self.ui.labelGPUName.setText(gpuinfo[0][0])
        self.ui.progressBarGPUUtil.setValue(percentage2int(gpuinfo[0][2]))
        self.ui.progressBarGPUMem.setValue(percentage2int(gpuinfo[0][3]))

    def on_reload_images(self):
        # ref: https://docs.docker.com/engine/reference/commandline/images/#format-the-output
        self.ui.listViewImages.setModel(mk_list_standard_model(self.ui.listViewImages,
            shell_stream(['docker', 'images', '--format', '{{.ID}}  {{.Repository}}:{{.Tag}}'])))

    def on_reload_containers(self):
        # ref: https://docs.docker.com/engine/reference/commandline/ps/#formatting
        self.ui.listViewContainers.setModel(mk_list_standard_model(self.ui.listViewContainers,
            shell_stream(['docker', 'ps', '--filter', 'status=running', '--format', '{{.ID}}  {{.Image}} {{.Ports}}  {{.Status}}'])))

    @property
    def state(self):
        return self.__state

    @state.setter
    def state(self, value):
        self.__state = value
        self.ui.statusbar.showMessage(value)
        self.ui.pushButtonRun.setEnabled(value == 'Ready')

    def on_run(self):
        if self.state == 'Ready':
            subprocess.run([TERM, TERM_RUN, self.variables['cmd'], TERM_WORKSPACE, self.script_workspace])

    def load_vars(self, variables):
        self.variables = variables
        if variables:
            self.ui.lineEditDocker.setText(variables['DOCKER'])
            self.ui.lineEditImage.setText(variables['IMAGE'])
            self.ui.lineEditPorts.setText(argv2str(variables['PORTS']))
            self.ui.lineEditVolumns.setText(argv2str(variables['VOLUMNS']))
            self.ui.plainTextEditDockerCommand.setPlainText(variables['cmd'])
            self.state = 'Ready'
        else:
            self.ui.lineEditDocker.setText('')
            self.ui.lineEditImage.setText('')
            self.ui.lineEditPorts.setText('')
            self.ui.lineEditVolumns.setText('')
            self.ui.plainTextEditDockerCommand.setPlainText('<Syntax Error>')
            self.state = 'Error'

    def on_script_selected(self, new_selection, old_selection):
        scripts = [i.data() for i in new_selection.first().indexes()]
        if scripts and os.path.exists(scripts[0]):
            self.script_fname = scripts[0]
            self.script_workspace = os.path.dirname(self.script_fname)
            self.ui.lineEditScript.setText(self.script_fname)
            self.ui.lineEditCWD.setText(self.script_workspace)
            self.load_vars(parse_dockerpy(self.script_fname))

def get_shortcuts():
    for _fname in os.listdir(PATH_SHORTCUTS):
        fname = os.path.join(PATH_SHORTCUTS, _fname)
        if os.path.islink(fname):
            yield os.path.realpath(fname)

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
    if os.name == 'posix':
        import platform
        if platform.linux_distribution()[0] == 'Ubuntu':
            TERM = 'gnome-terminal'
            TERM_RUN = '-e'
            TERM_WORKSPACE = '--working-directory'
        else: sys.exit(2)
    else: sys.exit(2)

    app = QApplication(sys.argv)
    my_mainWindow = MainWindow()
    my_mainWindow.show()
    sys.exit(app.exec_())
