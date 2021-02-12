# type: ignore
'''
flameTimewarpML
Flame 2020 and higher
written by Andrii Toloshnyy
andriy.toloshnyy@gmail.com
'''

import os
import sys
import time
import threading
import atexit
from pprint import pprint
from pprint import pformat

menu_group_name = 'Timewarp ML'
DEBUG = False

__version__ = 'v0.4.0.beta.024'


class flameAppFramework(object):
    # flameAppFramework class takes care of preferences and bundle unpack/install routines

    class prefs_dict(dict):
        # subclass of a dict() in order to directly link it 
        # to main framework prefs dictionaries
        # when accessed directly it will operate on a dictionary under a 'name'
        # key in master dictionary.
        # master = {}
        # p = prefs(master, 'app_name')
        # p['key'] = 'value'
        # master - {'app_name': {'key', 'value'}}
            
        def __init__(self, master, name, **kwargs):
            self.name = name
            self.master = master
            if not self.master.get(self.name):
                self.master[self.name] = {}
            self.master[self.name].__init__()

        def __getitem__(self, k):
            return self.master[self.name].__getitem__(k)
        
        def __setitem__(self, k, v):
            return self.master[self.name].__setitem__(k, v)

        def __delitem__(self, k):
            return self.master[self.name].__delitem__(k)
        
        def get(self, k, default=None):
            return self.master[self.name].get(k, default)
        
        def setdefault(self, k, default=None):
            return self.master[self.name].setdefault(k, default)

        def pop(self, k, v=object()):
            if v is object():
                return self.master[self.name].pop(k)
            return self.master[self.name].pop(k, v)
        
        def update(self, mapping=(), **kwargs):
            self.master[self.name].update(mapping, **kwargs)
        
        def __contains__(self, k):
            return self.master[self.name].__contains__(k)

        def copy(self): # don't delegate w/ super - dict.copy() -> dict :(
            return type(self)(self)
        
        def keys(self):
            return self.master[self.name].keys()

        @classmethod
        def fromkeys(cls, keys, v=None):
            return self.master[self.name].fromkeys(keys, v)
        
        def __repr__(self):
            return '{0}({1})'.format(type(self).__name__, self.master[self.name].__repr__())

        def master_keys(self):
            return self.master.keys()

    def __init__(self):
        self.name = self.__class__.__name__
        self.bundle_name = 'flameTimewarpML'

        # self.prefs scope is limited to flame project and user
        self.prefs = {}
        self.prefs_user = {}
        self.prefs_global = {}
        self.debug = DEBUG
        
        try:
            import flame
            self.flame = flame
            self.flame_project_name = self.flame.project.current_project.name
            self.flame_user_name = flame.users.current_user.name
        except:
            self.flame = None
            self.flame_project_name = None
            self.flame_user_name = None
        
        import socket
        self.hostname = socket.gethostname()
        
        if sys.platform == 'darwin':
            self.prefs_folder = os.path.join(
                os.path.expanduser('~'),
                 'Library',
                 'Preferences',
                 self.bundle_name)
        elif sys.platform.startswith('linux'):
            self.prefs_folder = os.path.join(
                os.path.expanduser('~'),
                '.config',
                self.bundle_name)

        self.prefs_folder = os.path.join(
            self.prefs_folder,
            self.hostname,
        )

        self.log('[%s] waking up' % self.__class__.__name__)
        self.load_prefs()

        # preferences defaults

        if not self.prefs_global.get('bundle_location'):
            if sys.platform == 'darwin':
                self.bundle_location = os.path.join(
                    os.path.expanduser('~'),
                    'Documents',
                    self.bundle_name)
            else:
                self.bundle_location = os.path.join(
                    os.path.expanduser('~'),
                    self.bundle_name)
            self.prefs_global['bundle_location'] = self.bundle_location
        
        else:
            self.bundle_location = self.prefs_global.get('bundle_location')

        #    self.prefs_global['menu_auto_refresh'] = {
        #        'media_panel': True,
        #        'batch': True,
        #        'main_menu': True
        #    }
        
        self.apps = []

        import hashlib
        self.bundle_id = hashlib.sha1(__version__.encode()).hexdigest()

        bundle_path = os.path.join(self.bundle_location, 'bundle')
        self.bundle_path = bundle_path

        if (os.path.isdir(bundle_path) and os.path.isfile(os.path.join(bundle_path, 'bundle_id'))):
            self.log('checking existing bundle id %s' % os.path.join(bundle_path, 'bundle_id'))
            with open(os.path.join(bundle_path, 'bundle_id'), 'r') as bundle_id_file:
                if bundle_id_file.read() == self.bundle_id:
                    self.log('env bundle already exists with id matching current version')
                    bundle_id_file.close()
                    return
                else:
                    self.log('existing env bundle id does not match current one')

        self.install_miniconda_libs = True
        if self.show_unpack_dialog(bundle_path):
            # bundle location is subject to change
            self.bundle_location = self.prefs_global.get('bundle_location')
            bundle_path = os.path.join(self.bundle_location, 'bundle')
            self.bundle_path = bundle_path

            # unpack bundle sequence
            self.unpacking_thread = threading.Thread(target=self.unpack_bundle, args=(bundle_path, ))
            self.unpacking_thread.daemon = True
            self.unpacking_thread.start()
        else:
            self.log('user cancelled bundle unpack')

    def log(self, message, logfile = None):
        msg = '[%s] %s' % (self.bundle_name, message)
        print (msg)
        if logfile:
            try:
                logfile.write(msg + '\n')
                logfile.flush()
            except:
                pass

    def log_debug(self, message):
        if self.debug:
            print ('[DEBUG %s] %s' % (self.bundle_name, message))

    def load_prefs(self):
        import pickle
        
        prefix = self.prefs_folder + os.path.sep + self.bundle_name
        prefs_file_path = prefix + '.' + self.flame_user_name + '.' + self.flame_project_name + '.prefs'
        prefs_user_file_path = prefix + '.' + self.flame_user_name  + '.prefs'
        prefs_global_file_path = prefix + '.prefs'

        try:
            prefs_file = open(prefs_file_path, 'r')
            self.prefs = pickle.load(prefs_file)
            prefs_file.close()
            self.log('preferences loaded from %s' % prefs_file_path)
            self.log_debug('preferences contents:\n' + pformat(self.prefs))
        except:
            self.log('unable to load preferences from %s' % prefs_file_path)

        try:
            prefs_file = open(prefs_user_file_path, 'r')
            self.prefs_user = pickle.load(prefs_file)
            prefs_file.close()
            self.log('preferences loaded from %s' % prefs_user_file_path)
            self.log_debug('preferences contents:\n' + pformat(self.prefs_user))
        except:
            self.log('unable to load preferences from %s' % prefs_user_file_path)

        try:
            prefs_file = open(prefs_global_file_path, 'r')
            self.prefs_global = pickle.load(prefs_file)
            prefs_file.close()
            self.log('preferences loaded from %s' % prefs_global_file_path)
            self.log_debug('preferences contents:\n' + pformat(self.prefs_global))

        except:
            self.log('unable to load preferences from %s' % prefs_global_file_path)

        return True

    def save_prefs(self):
        import pickle

        if not os.path.isdir(self.prefs_folder):
            try:
                os.makedirs(self.prefs_folder)
            except:
                self.log('unable to create folder %s' % prefs_folder)
                return False

        prefix = self.prefs_folder + os.path.sep + self.bundle_name
        prefs_file_path = prefix + '.' + self.flame_user_name + '.' + self.flame_project_name + '.prefs'
        prefs_user_file_path = prefix + '.' + self.flame_user_name  + '.prefs'
        prefs_global_file_path = prefix + '.prefs'

        try:
            prefs_file = open(prefs_file_path, 'w')
            pickle.dump(self.prefs, prefs_file)
            prefs_file.close()
            if self.debug:
                self.log('preferences saved to %s' % prefs_file_path)
                self.log('preferences contents:\n' + pformat(self.prefs))
        except:
            self.log('unable to save preferences to %s' % prefs_file_path)

        try:
            prefs_file = open(prefs_user_file_path, 'w')
            pickle.dump(self.prefs_user, prefs_file)
            prefs_file.close()
            if self.debug:
                self.log('preferences saved to %s' % prefs_user_file_path)
                self.log('preferences contents:\n' + pformat(self.prefs_user))
        except:
            self.log('unable to save preferences to %s' % prefs_user_file_path)

        try:
            prefs_file = open(prefs_global_file_path, 'w')
            pickle.dump(self.prefs_global, prefs_file)
            prefs_file.close()
            if self.debug:
                self.log('preferences saved to %s' % prefs_global_file_path)
                self.log('preferences contents:\n' + pformat(self.prefs_global))
        except:
            self.log('unable to save preferences to %s' % prefs_global_file_path)
            
        return True

    def unpack_bundle(self, bundle_path):
        start = time.time()
        script_file_name, ext = os.path.splitext(os.path.abspath(__file__))
        script_file_name += '.py'
        self.log('script file: %s' % script_file_name)
        script = None
        payload = None

        try:
            with open(script_file_name, 'r+') as scriptfile:
                script = scriptfile.read()
                start_position = script.rfind('# bundle payload starts here')
                
                if script[start_position -1: start_position] != '\n':
                    self.show_turncated_message()
                    scriptfile.close()
                    return False

                start_position += 33
                payload = script[start_position:-4]
                # scriptfile.truncate(start_position - 34)
                scriptfile.close()
        except Exception as e:
            self.show_exception(e)
            return False
        
        del script
        if not payload:
            return False
        
        logfile = None
        logfile_path = '/var/tmp/flameTimewarpML_install.log'
        try:
            open(logfile_path, "w").close()
            logfile = open(logfile_path, 'w+')
        except:
            pass
        
        if sys.platform == 'darwin':
            import subprocess
            log_cmd = """tell application "Terminal" to activate do script "tail -f """ + os.path.abspath(logfile_path) + '; exit"'
            subprocess.Popen(['osascript', '-e', log_cmd])
        else:
            log_cmd = """konsole --caption flameTimewarpML -e /bin/bash -c 'trap exit SIGINT SIGTERM; tail -f """ + os.path.abspath(logfile_path) +"; sleep 2'"
            os.system(log_cmd)
            
        self.log('bundle_id: %s size %sMb' % (self.bundle_id, len(payload)//(1024 ** 2)), logfile)
        
        if os.path.isdir(bundle_path):
            bundle_backup_folder = os.path.abspath(bundle_path + '.previous')
            if os.path.isdir(bundle_backup_folder):
                try:
                    cmd = 'rm -rf "' + os.path.abspath(bundle_backup_folder) + '"'
                    self.log('removing previous backup folder', logfile)
                    self.log('Executing command: %s' % cmd, logfile)
                    os.system(cmd)
                except Exception as e:
                    self.show_exception(e)
                    return False
            try:
                cmd = 'mv "' + os.path.abspath(bundle_path) + '" "' + bundle_backup_folder + '"'
                self.log('backing up existing bundle folder', logfile)
                self.log('Executing command: %s' % cmd, logfile)
                os.system(cmd)
            except Exception as e:
                self.show_exception(e)
                return False

        try:
            self.log('creating new bundle folder: %s' % bundle_path, logfile)
            os.makedirs(bundle_path)
        except Exception as e:
            self.show_exception(e)
            return False

        payload_dest = os.path.join(
            self.bundle_location, 
            self.bundle_name + '.' + __version__ + '.bundle.tar'
            )
        
        try:
            import base64
            self.log('unpacking payload: %s' % payload_dest, logfile)
            with open(payload_dest, 'wb') as payload_file:
                payload_file.write(base64.b64decode(payload))
                payload_file.close()
            cmd = 'tar xf "' + payload_dest + '" -C "' + self.bundle_location + '/"'
            self.log('Executing command: %s' % cmd, logfile)
            status = os.system(cmd)
            self.log('exit status %s' % os.WEXITSTATUS(status), logfile)

            # self.log('cleaning up %s' % payload_dest, logfile)
            # os.remove(payload_dest)
        
        except Exception as e:
            self.show_exception(e)
            return False

        delta = time.time() - start
        self.log('bundle extracted to %s' % bundle_path, logfile)
        self.log('extracting bundle took %s sec' % str(delta), logfile)

        del payload

        env_folder = os.path.join(self.bundle_location, 'miniconda3')
        if self.install_miniconda_libs:
            self.install_env(env_folder, logfile)
            self.install_env_packages(env_folder, logfile)

            # cmd = 'rm -rf "' + os.path.join(self.bundle_location, 'bundle', 'miniconda.package') + '"'
            # self.log('Executing command: %s' % cmd, logfile)
            # os.system(cmd)

        try:
            with open(os.path.join(bundle_path, 'bundle_id'), 'w+') as bundle_id_file:
                bundle_id_file.write(self.bundle_id)
        except Exception as e:
            self.show_exception(e)
            return False
        
        if self.install_miniconda_libs:
            self.log('flameTimewarpML has finished unpacking its bundle and installing required packages', logfile)
        else:
            self.log('flameTimewarpML has finished unpacking its bundle', logfile)

        try:
            logfile.close()
            os.system('killall tail')
        except:
            pass

        if self.show_complete_message(env_folder):
            # BUNDLE CLEANUP LOGIC
            self.log('cleaning up %s' % payload_dest, logfile)
            os.remove(payload_dest)
            cmd = 'rm -rf "' + os.path.join(self.bundle_location, 'bundle', 'miniconda.package') + '"'
            self.log('Executing command: %s' % cmd, logfile)
            os.system(cmd)
            try:
                with open(script_file_name, 'r+') as scriptfile:
                    script = scriptfile.read()
                    start_position = script.rfind('# bundle payload starts here')
                    
                    if script[start_position -1: start_position] == '\n':
                        start_position += 33
                        self.log('removing bundle from script file')
                        scriptfile.truncate(start_position - 34)
                    scriptfile.close()
                    del script
            except Exception as e:
                self.show_exception(e)
                return False

        return True
                    
    def install_env(self, env_folder, logfile):
        env_backup_folder = os.path.abspath(env_folder + '.previous')
        if os.path.isdir(env_backup_folder):
            try:
                cmd = 'rm -rf "' + env_backup_folder + '"'
                self.log('Executing command: %s' % cmd, logfile)
                os.system(cmd)
            except Exception as e:
                self.show_exception(e)
                return False
            
        if os.path.isdir(env_folder):
            try:
                cmd = 'mv "' + env_folder + '" "' + env_backup_folder + '"'
                self.log('Executing command: %s' % cmd, logfile)
                os.system(cmd)
            except Exception as e:
                self.show_exception(e)
                return False

        start = time.time()
        self.log('installing Miniconda3...', logfile)
        self.log('installing into %s' % env_folder, logfile)
        
        if sys.platform == 'darwin':
            installer_file = os.path.join(self.bundle_location, 'bundle', 'miniconda.package', 'Miniconda3-latest-MacOSX-x86_64.sh')
        else:
            installer_file = os.path.join(self.bundle_location, 'bundle', 'miniconda.package', 'Miniconda3-latest-Linux-x86_64.sh')

        cmd = '/bin/sh "' + installer_file + '" -b -p "' + env_folder + '"'
        cmd += ' 2>&1 | tee > ' + os.path.join(self.bundle_location, 'miniconda_install.log')
        self.log('Executing command: %s' % cmd, logfile)
        status = os.system(cmd)
        self.log('exit status %s' % os.WEXITSTATUS(status), logfile)
        delta = time.time() - start
        self.log('installing Miniconda took %s sec' % str(delta), logfile)

    def install_env_packages(self, env_folder, logfile):
        start = time.time()
        self.log('installing Miniconda packages...', logfile)
        cmd = """/bin/bash -c 'eval "$(""" + os.path.join(env_folder, 'bin', 'conda') + ' shell.bash hook)"; conda activate; '
        cmd += 'pip3 install -r ' + os.path.join(self.bundle_location, 'bundle', 'requirements.txt') + ' --no-index --find-links '
        cmd += os.path.join(self.bundle_location, 'bundle', 'miniconda.package', 'packages')
        cmd += ' 2>&1 | tee > '
        cmd += os.path.join(self.bundle_location, 'miniconda_packages_install.log')
        cmd += "'"

        self.log('Executing command: %s' % cmd, logfile)        
        status = os.system(cmd)
        self.log('exit status %s' % os.WEXITSTATUS(status), logfile)
        delta = time.time() - start
        self.log('installing Miniconda packages took %s sec' % str(delta), logfile)

    def show_exception(self, e):
        from PySide2 import QtWidgets
        import traceback

        msg = 'flameTimewrarpML: %s' % e
        dmsg = pformat(traceback.format_exc())

        try:
            import flame
        except:
            print (msg)
            print (dmsg)
            return False
        
        def show_error_mbox():
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            mbox.setDetailedText(dmsg)
            mbox.setStyleSheet('QLabel{min-width: 800px;}')
            mbox.exec_()

        flame.schedule_idle_event(show_error_mbox)
        return True

    def show_unpack_dialog(self, bundle_path):
        from PySide2 import QtWidgets, QtCore

        title = 'flameTimeWarpML %s ' % __version__
        msg = title + 'is going to unpack its bundle '
        msg += 'and run additional package installation scrips. '
        msg += 'Check console for details.'

        window = QtWidgets.QDialog()
        window.setMinimumSize(280, 120)
        window.setWindowTitle(title)
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #313131')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-150, (screen_res.height() / 2)-180)

        # Spacer
        lbl_Spacer = QtWidgets.QLabel('', window)
        lbl_Spacer.setStyleSheet('QFrame {color: #989898; background-color: #313131}')
        lbl_Spacer.setMinimumHeight(4)
        lbl_Spacer.setMaximumHeight(4)
        lbl_Spacer.setAlignment(QtCore.Qt.AlignCenter)

        vbox = QtWidgets.QVBoxLayout()
        vbox.setAlignment(QtCore.Qt.AlignTop)

        # Unpack Bundle Message

        lbl_UnpackMessage = QtWidgets.QLabel(msg, window)
        lbl_UnpackMessage.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_UnpackMessage.setMinimumHeight(48)
        lbl_UnpackMessage.setAlignment(QtCore.Qt.AlignCenter)
        lbl_UnpackMessage.setWordWrap(True)
        vbox.addWidget(lbl_UnpackMessage)

        # Install Miniconda and Libs checkbox
        def toggle_install_miniconda():
            self.install_miniconda_libs = chk_InstallMinicondaLibs.isChecked()

        chk_InstallMinicondaLibs = QtWidgets.QCheckBox(
            ' Install Miniconda3 and dependency libraries',
            window
        )
        chk_InstallMinicondaLibs.setStyleSheet('QCheckBox {border: none; color: #989898; background-color: #313131}')
        chk_InstallMinicondaLibs.setMinimumHeight(28)
        chk_InstallMinicondaLibs.setFocusPolicy(QtCore.Qt.NoFocus)
        chk_InstallMinicondaLibs.setCheckState(QtCore.Qt.Checked)
        chk_InstallMinicondaLibs.stateChanged.connect(toggle_install_miniconda)
        vbox.addWidget(chk_InstallMinicondaLibs, alignment = QtCore.Qt.AlignCenter)

        # Spaces in Path label
        lbl_SpacesInPath = QtWidgets.QLabel(
            'Can not install if path contain spaces:', 
            window
            )
        lbl_SpacesInPath.setStyleSheet('QFrame {color: #989898; background-color: #373941}')
        lbl_SpacesInPath.setMinimumHeight(28)
        lbl_SpacesInPath.setAlignment(QtCore.Qt.AlignCenter)
        lbl_SpacesInPath.setVisible(False)
        vbox.addWidget(lbl_SpacesInPath)

        # Unpack Path Label

        lbl_UnpackPath = QtWidgets.QLabel(
            self.bundle_location, 
            window
            )
        lbl_UnpackPath.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_UnpackPath.setMinimumHeight(28)
        lbl_UnpackPath.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_UnpackPath)
        vbox.addWidget(lbl_Spacer)

        def chooseFolder():
            result_folder = str(QtWidgets.QFileDialog.getExistingDirectory(
                window, 
                "Open Directory", 
                self.bundle_location, 
                QtWidgets.QFileDialog.ShowDirsOnly))

            if result_folder =='':
                return

            if ' ' in result_folder:
                lbl_SpacesInPath.setVisible(True)
                window.adjustSize()
            else:
                lbl_SpacesInPath.setVisible(False)
                window.adjustSize()
            
            self.bundle_location = result_folder
            lbl_UnpackPath.setText(self.bundle_location)
        #    self.prefs['working_folder'] = self.working_folder

        # Unpack, Location and Cancel Buttons
        hbox_Create = QtWidgets.QHBoxLayout()

        select_btn = QtWidgets.QPushButton('Unpack', window)
        select_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        select_btn.setMinimumSize(128, 28)
        select_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        select_btn.clicked.connect(window.accept)
        select_btn.setAutoDefault(True)
        select_btn.setDefault(True)

        cancel_btn = QtWidgets.QPushButton('Cancel', window)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.setMinimumSize(128, 28)
        cancel_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        cancel_btn.clicked.connect(window.reject)

        dest_btn = QtWidgets.QPushButton('Choose Dest', window)
        dest_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        dest_btn.setMinimumSize(128, 28)
        dest_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        dest_btn.clicked.connect(chooseFolder)

        hbox_Create.addWidget(cancel_btn)
        hbox_Create.addWidget(dest_btn)
        hbox_Create.addWidget(select_btn)

        vbox.addLayout(hbox_Create)

        window.setLayout(vbox)

        if window.exec_():
            if ' ' in self.bundle_location:
                self.show_install_spaces_message()
                return False
            self.prefs_global['bundle_location'] = self.bundle_location
            self.save_prefs()
            return True
        else:
            return False

    def show_complete_message(self, bundle_path):
        from PySide2 import QtWidgets

        self.clean_status = False
        self.clean_wait_flag = True

        msg = 'flameTimewarpML has finished unpacking its bundle and required packages. Would you like to clean the bundle and installer files?'
        dmsg = 'Bundle location: %s\n' % self.bundle_location
        dmsg += '* Flame scipt written by Andrii Toloshnyy (c) 2021\n'
        dmsg += '* RIFE: Real-Time Intermediate Flow Estimation for Video Frame Interpolation:\n'
        dmsg += '  Huang, Zhewei and Zhang, Tianyuan and Heng, Wen and Shi, Boxin and Zhou, Shuchang, '
        dmsg += 'arXiv preprint arXiv:2011.06294, 2020\n'
        dmsg += '* Miniconda3: (c) 2017 Continuum Analytics, Inc. (dba Anaconda, Inc.). https://www.anaconda.com. All Rights Reserved\n'
        dmsg += '* For info on additional packages see miniconda_packages_install.log'

        try:
            import flame
        except:
            print (msg)
            print (dmsg)
            return status
        
        def show_mbox():
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            mbox.setDetailedText(dmsg)
            # mbox.setStyleSheet('QLabel{min-width: 400px;}')
            mbox.setStandardButtons(QtWidgets.QMessageBox.Ok|QtWidgets.QMessageBox.Cancel)
            
            btn_Clean = mbox.button(QtWidgets.QMessageBox.Cancel)
            btn_Clean.setText('Clean')
            btn_Clean.setAutoDefault(True)
            btn_Clean.setDefault(True)

            btn_Keep = mbox.button(QtWidgets.QMessageBox.Ok)
            btn_Keep.setText('Keep')
            mbox.exec_()
            if mbox.clickedButton() == btn_Clean:
                self.clean_status = True
                self.clean_wait_flag = False
            else:
                self.clean_status = False
                self.clean_wait_flag = False

        flame.schedule_idle_event(show_mbox)
        while self.clean_wait_flag:
            time.sleep(0.1)

        return self.clean_status

    def show_turncated_message(self):
        from PySide2 import QtWidgets

        script_file_name, ext = os.path.splitext(os.path.abspath(__file__))
        script_file_name += '.py'

        msg = 'flameTimewarpML bundle payload has already been turncated during previous install.'
        msg += ' Please copy the original file and start again.'
        msg += ' Script file location:\n%s' % script_file_name

        try:
            import flame
        except:
            print (msg)
            print (dmsg)
            return False
        
        def show_mbox():
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            # mbox.setDetailedText(dmsg)
            # mbox.setStyleSheet('QLabel{min-width: 400px;}')
            mbox.exec_()

        flame.schedule_idle_event(show_mbox)
        return True

    def show_install_spaces_message(self):
        from PySide2 import QtWidgets, QtCore

        script_file_name, ext = os.path.splitext(os.path.abspath(__file__))
        script_file_name += '.py'

        msg = 'Cannot install if path contain spaces. Install dialog will appear again once you restart Flame'

        try:
            import flame
        except:
            print (msg)
            print (dmsg)
            return False
        
        def show_mbox():
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            mbox.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
            # mbox.setDetailedText(dmsg)
            # mbox.setStyleSheet('QLabel{min-width: 400px;}')
            mbox.exec_()

        flame.schedule_idle_event(show_mbox)
        return True


class flameMenuApp(object):
    def __init__(self, framework):
        self.name = self.__class__.__name__
        self.framework = framework
        self.menu_group_name = menu_group_name
        self.debug = DEBUG
        self.dynamic_menu_data = {}

        # flame module is only avaliable when a 
        # flame project is loaded and initialized
        self.flame = None
        try:
            import flame
            self.flame = flame
        except:
            self.flame = None
        
        self.prefs = self.framework.prefs_dict(self.framework.prefs, self.name)
        self.prefs_user = self.framework.prefs_dict(self.framework.prefs_user, self.name)
        self.prefs_global = self.framework.prefs_dict(self.framework.prefs_global, self.name)

        from PySide2 import QtWidgets
        self.mbox = QtWidgets.QMessageBox()

    @property
    def flame_extension_map(self):
        return {
            'Alias': 'als',
            'Cineon': 'cin',
            'Dpx': 'dpx',
            'Jpeg': 'jpg',
            'Maya': 'iff',
            'OpenEXR': 'exr',
            'Pict': 'pict',
            'Pixar': 'picio',
            'Sgi': 'sgi',
            'SoftImage': 'pic',
            'Targa': 'tga',
            'Tiff': 'tif',
            'Wavefront': 'rla',
            'QuickTime': 'mov',
            'MXF': 'mxf',
            'SonyMXF': 'mxf'
        }
        
    def __getattr__(self, name):
        def method(*args, **kwargs):
            print ('calling %s' % name)
        return method

    def log(self, message):
        self.framework.log(message)

    def rescan(self, *args, **kwargs):
        if not self.flame:
            try:
                import flame
                self.flame = flame
            except:
                self.flame = None

        if self.flame:
            self.flame.execute_shortcut('Rescan Python Hooks')
            self.log('Rescan Python Hooks')

    def get_export_preset_fields(self, preset):
        
        self.log('Flame export preset parser')

        # parses Flame Export preset and returns a dict of a parsed values
        # of False on error.
        # Example:
        # {'type': 'image',
        #  'fileType': 'OpenEXR',
        #  'fileExt': 'exr',
        #  'framePadding': 8
        #  'startFrame': 1001
        #  'useTimecode': 0
        # }
        
        from xml.dom import minidom

        preset_fields = {}

        # Flame type to file extension map

        flame_extension_map = {
            'Alias': 'als',
            'Cineon': 'cin',
            'Dpx': 'dpx',
            'Jpeg': 'jpg',
            'Maya': 'iff',
            'OpenEXR': 'exr',
            'Pict': 'pict',
            'Pixar': 'picio',
            'Sgi': 'sgi',
            'SoftImage': 'pic',
            'Targa': 'tga',
            'Tiff': 'tif',
            'Wavefront': 'rla',
            'QuickTime': 'mov',
            'MXF': 'mxf',
            'SonyMXF': 'mxf'
        }

        preset_path = ''

        if os.path.isfile(preset.get('PresetFile', '')):
            preset_path = preset.get('PresetFile')
        else:
            path_prefix = self.flame.PyExporter.get_presets_dir(
                self.flame.PyExporter.PresetVisibility.values.get(preset.get('PresetVisibility', 2)),
                self.flame.PyExporter.PresetType.values.get(preset.get('PresetType', 0))
            )
            preset_file = preset.get('PresetFile')
            if preset_file.startswith(os.path.sep):
                preset_file = preset_file[1:]
            preset_path = os.path.join(path_prefix, preset_file)

        self.log('parsing Flame export preset: %s' % preset_path)
        
        preset_xml_doc = None
        try:
            preset_xml_doc = minidom.parse(preset_path)
        except Exception as e:
            message = 'flameMenuSG: Unable parse xml export preset file:\n%s' % e
            self.mbox.setText(message)
            self.mbox.exec_()
            return False

        preset_fields['path'] = preset_path

        preset_type = preset_xml_doc.getElementsByTagName('type')
        if len(preset_type) > 0:
            preset_fields['type'] = preset_type[0].firstChild.data

        video = preset_xml_doc.getElementsByTagName('video')
        if len(video) < 1:
            message = 'flameMenuSG: XML parser error:\nUnable to find xml video tag in:\n%s' % preset_path
            self.mbox.setText(message)
            self.mbox.exec_()
            return False
        
        filetype = video[0].getElementsByTagName('fileType')
        if len(filetype) < 1:
            message = 'flameMenuSG: XML parser error:\nUnable to find video::fileType tag in:\n%s' % preset_path
            self.mbox.setText(message)
            self.mbox.exec_()
            return False

        preset_fields['fileType'] = filetype[0].firstChild.data
        if preset_fields.get('fileType', '') not in flame_extension_map:
            message = 'flameMenuSG:\nUnable to find extension corresponding to fileType:\n%s' % preset_fields.get('fileType', '')
            self.mbox.setText(message)
            self.mbox.exec_()
            return False
        
        preset_fields['fileExt'] = flame_extension_map.get(preset_fields.get('fileType'))

        name = preset_xml_doc.getElementsByTagName('name')
        if len(name) > 0:
            framePadding = name[0].getElementsByTagName('framePadding')
            startFrame = name[0].getElementsByTagName('startFrame')
            useTimecode = name[0].getElementsByTagName('useTimecode')
            if len(framePadding) > 0:
                preset_fields['framePadding'] = int(framePadding[0].firstChild.data)
            if len(startFrame) > 0:
                preset_fields['startFrame'] = int(startFrame[0].firstChild.data)
            if len(useTimecode) > 0:
                preset_fields['useTimecode'] = useTimecode[0].firstChild.data

        return preset_fields

    def sanitized(self, text):
        import re

        if text is None:
            return None
        
        text = text.strip()
        exp = re.compile(u'[^\w\.-]', re.UNICODE)

        if isinstance(text, unicode):
            result = exp.sub('_', value)
        else:
            decoded = text.decode('utf-8')
            result = exp.sub('_', decoded).encode('utf-8')

        return re.sub('_\_+', '_', result)

    def create_timestamp_uid(self):
        # generates UUID for the batch setup
        import uuid
        from datetime import datetime
        
        uid = ((str(uuid.uuid1()).replace('-', '')).upper())
        timestamp = (datetime.now()).strftime('%Y%b%d_%H%M').upper()
        return timestamp + '_' + uid[:3]


class flameTimewarpML(flameMenuApp):
    def __init__(self, framework):
        flameMenuApp.__init__(self, framework)
        self.env_folder = os.path.join(self.framework.bundle_location, 'miniconda3')
        
        self.loops = []
        self.threads = True

        if not self.prefs.master.get(self.name):
            # set general defaults
            self.prefs['working_folder'] = '/var/tmp'
            self.prefs['slowmo_uhd'] = False
            self.prefs['dedup_uhd'] = False
            self.prefs['fluidmorph_uhd'] = True
            self.prefs['fltw_uhd'] = True


        if self.prefs.get('version') != __version__:
            # set version-specific defaults
            self.prefs['trained_models_folder'] = os.path.join(
                self.framework.bundle_location,
                'bundle', 'trained_models', 'default', 'v2.0.model'
                )
            
        self.prefs['version'] = __version__
        self.framework.save_prefs()

        self.working_folder = self.prefs.get('working_folder')
        if not os.path.isdir(self.working_folder):
            self.working_folder = '/var/tmp'

        # Module defaults
        self.new_speed = 1
        self.dedup_mode = 0
        self.cpu = False
        self.UHD = True

        self.model_map = {
                os.path.join(
                    self.framework.bundle_location,
                    'bundle', 'trained_models', 'default', 'v1.8.model'
                    ): ' Model v1.8 ',
                os.path.join(
                    self.framework.bundle_location,
                    'bundle', 'trained_models', 'default', 'v2.0.model'
                    ): ' Model v2.0 ',
                os.path.join(
                    self.framework.bundle_location,
                    'bundle', 'trained_models', 'default', 'v2.1.model'
                    ): ' Model v2.1 ',
                os.path.join(
                    self.framework.bundle_location,
                    'bundle', 'trained_models', 'default', 'v2.2.model'
                    ): ' Model v2.2 ',
            }

    def build_menu(self):
        def scope_clip(selection):
            import flame
            for item in selection:
                if isinstance(item, (flame.PyClip)):
                    return True
            return False

        if not self.flame:
            return []
        
        if not os.path.isfile(os.path.join(self.framework.bundle_location, 'bundle', 'bundle_id')):
            return []
        
        menu = {'actions': []}
        menu['name'] = self.menu_group_name

        menu_item = {}
        menu_item['name'] = 'Slow Down clip(s) with ML'
        menu_item['execute'] = self.slowmo
        menu_item['isVisible'] = scope_clip
        menu_item['waitCursor'] = False
        menu['actions'].append(menu_item)

        menu_item = {}
        menu_item['name'] = 'Fill / Remove Duplicate Frames'
        menu_item['execute'] = self.dedup
        menu_item['isVisible'] = scope_clip
        menu_item['waitCursor'] = False
        menu['actions'].append(menu_item)

        menu_item = {}
        menu_item['name'] = 'Create Fluidmorph Transition'
        menu_item['execute'] = self.fluidmorph
        menu_item['isVisible'] = scope_clip
        menu_item['waitCursor'] = False
        menu['actions'].append(menu_item)

        menu_item = {}
        menu_item['name'] = "Timewarp from Flame's TW effect (beta)"
        menu_item['execute'] = self.fltw
        menu_item['isVisible'] = scope_clip
        menu_item['waitCursor'] = False
        menu['actions'].append(menu_item)

        menu_item = {}
        menu_item['name'] = 'Version: ' + __version__
        menu_item['execute'] = self.slowmo
        menu_item['isEnabled'] = False
        menu_item['isVisible'] = scope_clip

        menu['actions'].append(menu_item)

        return menu

    def slowmo(self, selection):
        result = self.slowmo_dialog()
        if not result:
            return False

        working_folder = str(result.get('working_folder', '/var/tmp'))
        speed = result.get('speed', 1)
        hold_konsole = result.get('hold_konsole', False)

        cmd_strings = []
        number_of_clips = 0

        import flame
        for item in selection:
            if isinstance(item, (flame.PyClip)):
                number_of_clips += 1

                clip = item
                clip_name = clip.name.get_value()
                
                result_folder = os.path.abspath(
                    os.path.join(
                        working_folder, 
                        self.sanitized(clip_name) + '_TWML' + str(2 ** speed) + '_' + self.create_timestamp_uid()
                        )
                    )

                if os.path.isdir(result_folder):
                    from PySide2 import QtWidgets
                    msg = 'Folder %s exists' % output_folder
                    mbox = QtWidgets.QMessageBox()
                    mbox.setWindowTitle('flameTimewrarpML')
                    mbox.setText(msg)
                    mbox.setStandardButtons(QtWidgets.QMessageBox.Ok|QtWidgets.QMessageBox.Cancel)
                    mbox.setStyleSheet('QLabel{min-width: 400px;}')
                    btn_Continue = mbox.button(QtWidgets.QMessageBox.Ok)
                    btn_Continue.setText('Owerwrite')
                    mbox.exec_()
                    if mbox.clickedButton() == mbox.button(QtWidgets.QMessageBox.Cancel):
                        return False
                    cmd = 'rm -f ' + result_folder + '/*'
                    self.log('Executing command: %s' % cmd)
                    os.system(cmd)

                source_clip_folder = os.path.join(result_folder, 'source')
                self.export_clip(item, source_clip_folder)

                cmd = 'python3 '
                if self.cpu:
                    cmd = 'export OMP_NUM_THREADS=1; python3 '
                cmd += os.path.join(self.framework.bundle_location, 'bundle', 'inference_sequence.py')
                cmd += ' --input ' + source_clip_folder + ' --output ' + result_folder
                cmd += ' --model ' + self.prefs.get('trained_models_folder')
                cmd += ' --exp=' + str(speed)
                if self.cpu:
                    cmd += ' --cpu'
                if self.prefs.get('slowmo_uhd', False):
                    cmd += ' --UHD'
                cmd += "; "
                cmd_strings.append(cmd)
                
                new_clip_name = clip_name + '_TWML' + str(2 ** speed)
                watcher = threading.Thread(target=self.import_watcher, args=(result_folder, new_clip_name, clip.parent, [source_clip_folder]))
                watcher.daemon = True
                watcher.start()
                self.loops.append(watcher)
        
        if sys.platform == 'darwin':
            cmd_prefix = """tell application "Terminal" to activate do script "clear; """
            # cmd_prefix += """ echo " & quote & "Received """
            # cmd_prefix += str(number_of_clips)
            #cmd_prefix += ' clip ' if number_of_clips < 2 else ' clips '
            # cmd_prefix += 'to process, press Ctrl+C to cancel" & quote &; '
            cmd_prefix += """/bin/bash -c 'eval " & quote & "$("""
            cmd_prefix += os.path.join(self.env_folder, 'bin', 'conda')
            cmd_prefix += """ shell.bash hook)" & quote & "; conda activate; """
            cmd_prefix += 'cd ' + os.path.join(self.framework.bundle_location, 'bundle') + '; '
            
            ml_cmd = cmd_prefix
           
            for cmd_string in cmd_strings:
                ml_cmd += cmd_string

            ml_cmd += """'; exit" """

            import subprocess
            subprocess.Popen(['osascript', '-e', ml_cmd])
        
        else:
            cmd_prefix = 'konsole '
            if hold_konsole:
                cmd_prefix += '--hold '
            cmd_prefix += """-e /bin/bash -c 'eval "$(""" + os.path.join(self.env_folder, 'bin', 'conda') + ' shell.bash hook)"; conda activate; '
            cmd_prefix += 'cd ' + os.path.join(self.framework.bundle_location, 'bundle') + '; '

            ml_cmd = cmd_prefix
            ml_cmd += 'echo "Received ' + str(number_of_clips)
            ml_cmd += ' clip ' if number_of_clips < 2 else ' clips '
            ml_cmd += 'to process, press Ctrl+C to cancel"; '
            ml_cmd += 'trap exit SIGINT SIGTERM; '

            for cmd_string in cmd_strings:
                ml_cmd += cmd_string

            if hold_konsole:
                ml_cmd += 'echo "Commands finished. You can close this window"'
            ml_cmd +="'"
            self.log('Executing command: %s' % ml_cmd)
            os.system(ml_cmd)

        flame.execute_shortcut('Refresh Thumbnails')

    def slowmo_dialog(self, *args, **kwargs):
        from PySide2 import QtWidgets, QtCore

        self.new_speed_list = {
            1: '1/2',
            2: '1/4',
            3: '1/8',
            4: '1/16' 
        }
        
        # flameMenuNewBatch_prefs = self.framework.prefs.get('flameMenuNewBatch', {})
        # self.asset_task_template =  flameMenuNewBatch_prefs.get('asset_task_template', {})

        window = QtWidgets.QDialog()
        window.setMinimumSize(280, 180)
        window.setWindowTitle('Slow down clip(s) with ML')
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #313131')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-150, (screen_res.height() / 2)-180)

        # Spacer
        lbl_Spacer = QtWidgets.QLabel('', window)
        lbl_Spacer.setStyleSheet('QFrame {color: #989898; background-color: #313131}')
        lbl_Spacer.setMinimumHeight(4)
        lbl_Spacer.setMaximumHeight(4)
        lbl_Spacer.setAlignment(QtCore.Qt.AlignCenter)


        vbox = QtWidgets.QVBoxLayout()
        vbox.setAlignment(QtCore.Qt.AlignTop)

        # New Speed hbox
        new_speed_hbox = QtWidgets.QHBoxLayout()
        # new_speed_hbox.setAlignment(QtCore.Qt.AlignCenter)

        # New Speed label

        lbl_NewSpeed = QtWidgets.QLabel('New Speed ', window)
        lbl_NewSpeed.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_NewSpeed.setMinimumHeight(28)
        lbl_NewSpeed.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        new_speed_hbox.addWidget(lbl_NewSpeed)

        # New Speed Selector
        btn_NewSpeedSelector = QtWidgets.QPushButton(window)
        btn_NewSpeedSelector.setText(self.new_speed_list.get(self.new_speed))
        def selectNewSpeed(new_speed_id):
            self.new_speed = new_speed_id
            btn_NewSpeedSelector.setText(self.new_speed_list.get(self.new_speed))
        btn_NewSpeedSelector.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_NewSpeedSelector.setMinimumSize(80, 28)
        btn_NewSpeedSelector.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_NewSpeedSelector_menu = QtWidgets.QMenu()

        for new_speed_id in sorted(self.new_speed_list.keys()):
            code = self.new_speed_list.get(new_speed_id, '1/2')
            action = btn_NewSpeedSelector_menu.addAction(code)
            action.triggered[()].connect(lambda new_speed_id=new_speed_id: selectNewSpeed(new_speed_id))
        btn_NewSpeedSelector.setMenu(btn_NewSpeedSelector_menu)
        new_speed_hbox.addWidget(btn_NewSpeedSelector)

        # Reduce flow res button

        def enableUHD():
            if self.prefs.get('slowmo_uhd', False):
                btn_UHD.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                        'QToolTip {color: black; background-color:  #ffffd9; border: 0px}')
                self.prefs['slowmo_uhd'] = False
            else:
                btn_UHD.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}'
                                        'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
                self.prefs['slowmo_uhd'] = True
        btn_UHD = QtWidgets.QPushButton('Reduce flow res', window)
        btn_UHD.setToolTip('<b>Reduce flow res button</b><br>Use less details for analyzis, sometimes could be helpful with large motion.')
        btn_UHD.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_UHD.setMinimumSize(148, 28)
        if self.prefs.get('slowmo_uhd', False):
            btn_UHD.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}'
                                    'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
        else:
            btn_UHD.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
        btn_UHD.pressed.connect(enableUHD)
        new_speed_hbox.addWidget(btn_UHD)

        # Cpu Proc button

        if not sys.platform == 'darwin':            
            def enableCpuProc():
                if self.cpu:
                    btn_CpuProc.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
                    self.cpu = False
                else:
                    btn_CpuProc.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
                    self.cpu = True

            btn_CpuProc = QtWidgets.QPushButton('CPU Proc', window)
            btn_CpuProc.setFocusPolicy(QtCore.Qt.NoFocus)
            btn_CpuProc.setMinimumSize(88, 28)
            if self.cpu:
                btn_CpuProc.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
            else:
                btn_CpuProc.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            btn_CpuProc.pressed.connect(enableCpuProc)
            new_speed_hbox.addWidget(btn_CpuProc)

        '''
        else:
            btn_CpuProc = QtWidgets.QPushButton('CPU Proc', window)
            btn_CpuProc.setFocusPolicy(QtCore.Qt.NoFocus)
            btn_CpuProc.setMinimumSize(88, 28)
            btn_CpuProc.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}'
                                        'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
            btn_CpuProc.setToolTip('<b>CPU Proc button</b><br>Mac version is currently CPU-only due to lack of GPU support in PyTorch library on MacOS')
            new_speed_hbox.addWidget(btn_CpuProc)
        '''

        '''
        lbl_HorSpacer = QtWidgets.QLabel('', window)
        lbl_HorSpacer.setStyleSheet('QFrame {color: #989898; background-color: #313131}')
        lbl_HorSpacer.setMinimumHeight(28)
        lbl_HorSpacer.setMinimumWidth(4)
        lbl_HorSpacer.setMaximumWidth(4)
        lbl_HorSpacer.setAlignment(QtCore.Qt.AlignCenter)
        new_speed_hbox.addWidget(lbl_HorSpacer)
        '''
        '''
        lbl_Model = QtWidgets.QLabel('Model ', window)
        lbl_Model.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_Model.setMinimumHeight(28)
        lbl_Model.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        new_speed_hbox.addWidget(lbl_Model)
        '''

        ### Model Selector START

        current_model_name = self.model_map.get(self.prefs.get('trained_models_folder'), 'Unknown')
        
        # Model Selector Button
        btn_ModelSelector = QtWidgets.QPushButton(window)
        btn_ModelSelector.setText(current_model_name)
        
        def selectModel(trained_models_folder):
            self.prefs['trained_models_folder'] = trained_models_folder
            btn_ModelSelector.setText(self.model_map.get(trained_models_folder))

        btn_ModelSelector.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_ModelSelector.setMinimumSize(140, 28)
        btn_ModelSelector.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')

        btn_ModelSelector_menu = QtWidgets.QMenu()
        for trained_models_folder in sorted(self.model_map.keys()):
            
            code = self.model_map.get(trained_models_folder)
            action = btn_ModelSelector_menu.addAction(code)
            action.triggered[()].connect(lambda trained_models_folder=trained_models_folder: selectModel(trained_models_folder))
    
        btn_ModelSelector.setMenu(btn_ModelSelector_menu)
        new_speed_hbox.addWidget(btn_ModelSelector)

        ### Model Selector END

        vbox.addLayout(new_speed_hbox)
        vbox.addWidget(lbl_Spacer)

        # Work Folder Label

        lbl_WorkFolder = QtWidgets.QLabel('Export folder', window)
        lbl_WorkFolder.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_WorkFolder.setMinimumHeight(28)
        lbl_WorkFolder.setMaximumHeight(28)
        lbl_WorkFolder.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_WorkFolder)

        # Work Folder Text Field

        hbox_workfolder = QtWidgets.QHBoxLayout()
        hbox_workfolder.setAlignment(QtCore.Qt.AlignLeft)

        def chooseFolder():
            result_folder = str(QtWidgets.QFileDialog.getExistingDirectory(window, "Open Directory", self.working_folder, QtWidgets.QFileDialog.ShowDirsOnly))
            if result_folder =='':
                return
            self.working_folder = result_folder
            txt_WorkFolder.setText(self.working_folder)
            self.prefs['working_folder'] = self.working_folder

            #dialog = QtWidgets.QFileDialog()
            #dialog.setWindowTitle('Select export folder')
            #dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
            #dialog.setDirectory(self.working_folder)
            #dialog.setFileMode(QtWidgets.QFileDialog.Directory)
            #path = QtWidgets.QFileDialog.getExistingDirectory()
            # dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
            #
            # if dialog.exec_() == QtWidgets.QDialog.Accepted:
            #    file_full_path = str(dialog.selectedFiles()[0])

        def txt_WorkFolder_textChanged():
            self.working_folder = txt_WorkFolder.text()
        txt_WorkFolder = QtWidgets.QLineEdit('', window)
        txt_WorkFolder.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_WorkFolder.setMinimumSize(280, 28)
        txt_WorkFolder.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
        txt_WorkFolder.setText(self.working_folder)
        txt_WorkFolder.textChanged.connect(txt_WorkFolder_textChanged)
        hbox_workfolder.addWidget(txt_WorkFolder)

        btn_changePreset = QtWidgets.QPushButton('Choose', window)
        btn_changePreset.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_changePreset.setMinimumSize(88, 28)
        btn_changePreset.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                   'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_changePreset.clicked.connect(chooseFolder)
        hbox_workfolder.addWidget(btn_changePreset, alignment = QtCore.Qt.AlignLeft)

        vbox.addLayout(hbox_workfolder)
        vbox.addWidget(lbl_Spacer)

        # self.dialog_model_path(window, vbox)
        
        # vbox.addWidget(lbl_Spacer)


        '''
        # MODEL label
        lbl_Model = QtWidgets.QLabel('Model', window)
        lbl_Model.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_Model.setMinimumHeight(28)
        lbl_Model.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_Model)

        # MODEL Hbox START
        model_hbox = QtWidgets.QHBoxLayout()
        # model_hbox.setAlignment(QtCore.Qt.AlignCenter)

        model_groups_path = os.path.join(os.path.abspath(self.framework.bundle_path), self.trained_models_folder)
        model_groups = [d for d in os.listdir(model_groups_path) if os.path.isdir(os.path.join(model_groups_path, d))]
        model_names_path = os.path.join(os.path.abspath(self.framework.bundle_path), self.trained_models_folder, self.trained_models_group)
        model_names = [d.rstrip('.model') for d in os.listdir(model_names_path) if os.path.isdir(os.path.join(model_names_path, d))]

        # Model Groups Button
        btn_ModelGroups = QtWidgets.QPushButton(window)
        btn_ModelGroups.setText(self.trained_models_group)
        def selectModelGroup(new_model_group):
            self.trained_models_group = new_model_group
            btn_ModelGroups.setText(self.trained_models_group)
        btn_ModelGroups.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_ModelGroups.setMinimumHeight(28)
        btn_ModelGroups.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_ModelGroups_menu = QtWidgets.QMenu()
        for new_model_group in sorted(model_groups):
            action = btn_ModelGroups_menu.addAction(new_model_group)
            action.triggered[()].connect(lambda new_model_group=new_model_group: selectModelGroup(new_model_group))
        btn_ModelGroups.setMenu(btn_ModelGroups_menu)
        model_hbox.addWidget(btn_ModelGroups)


        # Model Names Button
        btn_ModelNames = QtWidgets.QPushButton(window)
        btn_ModelNames.setText(self.trained_model_name)
        def selectModelName(new_model_name):
            self.trained_model_name = new_model_name
            btn_ModelNames.setText(self.trained_model_name)
        btn_ModelNames.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_ModelNames.setMinimumHeight(28)
        btn_ModelNames.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_ModelNames_menu = QtWidgets.QMenu()
        for new_model_name in sorted(model_names):
            action = btn_ModelNames_menu.addAction(new_model_name)
            action.triggered[()].connect(lambda new_model_name=new_model_name: selectModelGroup(new_model_name))
        btn_ModelNames.setMenu(btn_ModelNames_menu)
        model_hbox.addWidget(btn_ModelNames)

        vbox.addLayout(model_hbox)
        vbox.addWidget(lbl_Spacer)

        # MODEL Hbox END
        '''

        # Create and Cancel Buttons
        hbox_Create = QtWidgets.QHBoxLayout()

        select_btn = QtWidgets.QPushButton('Create', window)
        select_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        select_btn.setMinimumSize(128, 28)
        select_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        select_btn.clicked.connect(window.accept)
        select_btn.setAutoDefault(True)
        select_btn.setDefault(True)

        cancel_btn = QtWidgets.QPushButton('Cancel', window)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.setMinimumSize(128, 28)
        cancel_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        cancel_btn.clicked.connect(window.reject)

        hbox_Create.addWidget(cancel_btn)
        hbox_Create.addWidget(select_btn)

        vbox.addLayout(hbox_Create)

        window.setLayout(vbox)
        if window.exec_():
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            self.framework.save_prefs()
            return {
                'speed': self.new_speed,
                'working_folder': self.working_folder,
                'hold_konsole': True if modifiers == QtCore.Qt.ControlModifier else False
            }
        else:
            return {}

    def dedup(self, selection):
        result = self.dedup_dialog()
        if not result:
            return False

        working_folder = str(result.get('working_folder', '/var/tmp'))
        mode = result.get('mode', 0)
        hold_konsole = result.get('hold_konsole', False)

        cmd_strings = []
        number_of_clips = 0

        import flame
        for item in selection:
            if isinstance(item, (flame.PyClip)):
                number_of_clips += 1

                clip = item
                clip_name = clip.name.get_value()
                
                result_folder = os.path.abspath(
                    os.path.join(
                        working_folder, 
                        self.sanitized(clip_name) + '_DUPFR' + '_' + self.create_timestamp_uid()
                        )
                    )

                if os.path.isdir(result_folder):
                    from PySide2 import QtWidgets
                    msg = 'Folder %s exists' % result_folder
                    mbox = QtWidgets.QMessageBox()
                    mbox.setWindowTitle('flameTimewrarpML')
                    mbox.setText(msg)
                    mbox.setStandardButtons(QtWidgets.QMessageBox.Ok|QtWidgets.QMessageBox.Cancel)
                    mbox.setStyleSheet('QLabel{min-width: 400px;}')
                    btn_Continue = mbox.button(QtWidgets.QMessageBox.Ok)
                    btn_Continue.setText('Owerwrite')
                    mbox.exec_()
                    if mbox.clickedButton() == mbox.button(QtWidgets.QMessageBox.Cancel):
                        return False
                    cmd = 'rm -f ' + result_folder + '/*'
                    self.log('Executing command: %s' % cmd)
                    os.system(cmd)

                source_clip_folder = os.path.join(result_folder, 'source')
                self.export_clip(item, source_clip_folder)

                cmd = 'python3 '
                if self.cpu:
                    cmd = 'export OMP_NUM_THREADS=1; python3 '
                cmd += os.path.join(self.framework.bundle_location, 'bundle', 'inference_dpframes.py')
                cmd += ' --model ' + self.prefs.get('trained_models_folder')
                cmd += ' --input ' + source_clip_folder + ' --output ' + result_folder
                if mode:
                    cmd += ' --remove'
                if self.cpu:
                    cmd += ' --cpu'
                if self.prefs.get('dedup_uhd', False):
                    cmd += ' --UHD'
                cmd += "; "
                cmd_strings.append(cmd)
                
                new_clip_name = clip_name + '_DUPFR'
                watcher = threading.Thread(target=self.import_watcher, args=(result_folder, new_clip_name, clip.parent, [source_clip_folder]))
                watcher.daemon = True
                watcher.start()
                self.loops.append(watcher)
        
        if sys.platform == 'darwin':
            cmd_prefix = """tell application "Terminal" to activate do script "clear; """
            # cmd_prefix += """ echo " & quote & "Received """
            # cmd_prefix += str(number_of_clips)
            #cmd_prefix += ' clip ' if number_of_clips < 2 else ' clips '
            # cmd_prefix += 'to process, press Ctrl+C to cancel" & quote &; '
            cmd_prefix += """/bin/bash -c 'eval " & quote & "$("""
            cmd_prefix += os.path.join(self.env_folder, 'bin', 'conda')
            cmd_prefix += """ shell.bash hook)" & quote & "; conda activate; """
            cmd_prefix += 'cd ' + os.path.join(self.framework.bundle_location, 'bundle') + '; '
            
            ml_cmd = cmd_prefix
           
            for cmd_string in cmd_strings:
                ml_cmd += cmd_string

            ml_cmd += """'; exit" """

            import subprocess
            subprocess.Popen(['osascript', '-e', ml_cmd])
        
        else:
            cmd_prefix = 'konsole '
            if hold_konsole:
                cmd_prefix += '--hold '
            cmd_prefix += """-e /bin/bash -c 'eval "$(""" + os.path.join(self.env_folder, 'bin', 'conda') + ' shell.bash hook)"; conda activate; '
            cmd_prefix += 'cd ' + os.path.join(self.framework.bundle_location, 'bundle') + '; '

            ml_cmd = cmd_prefix
            ml_cmd += 'echo "Received ' + str(number_of_clips)
            ml_cmd += ' clip ' if number_of_clips < 2 else ' clips '
            ml_cmd += 'to process, press Ctrl+C to cancel"; '
            ml_cmd += 'trap exit SIGINT SIGTERM; '

            for cmd_string in cmd_strings:
                ml_cmd += cmd_string

            ml_cmd += 'echo "Commands finished. You can close this window"'
            ml_cmd +="'"
            self.log('Executing command: %s' % ml_cmd)
            os.system(ml_cmd)

        flame.execute_shortcut('Refresh Thumbnails')

    def dedup_dialog(self, *args, **kwargs):
        from PySide2 import QtWidgets, QtCore

        self.modes_list = {
            0: 'Interpolate',
            1: 'Remove', 
        }
        
        window = QtWidgets.QDialog()
        window.setMinimumSize(280, 180)
        window.setWindowTitle('Remove duplicate frames')
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #313131')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-150, (screen_res.height() / 2)-180)

        # Spacer
        lbl_Spacer = QtWidgets.QLabel('', window)
        lbl_Spacer.setStyleSheet('QFrame {color: #989898; background-color: #313131}')
        lbl_Spacer.setMinimumHeight(4)
        lbl_Spacer.setMaximumHeight(4)
        lbl_Spacer.setAlignment(QtCore.Qt.AlignCenter)


        vbox = QtWidgets.QVBoxLayout()
        vbox.setAlignment(QtCore.Qt.AlignTop)
        
        # Duplicate frames action hbox
        dframes_hbox = QtWidgets.QHBoxLayout()
        # dframes_hbox.setAlignment(QtCore.Qt.AlignLeft)

        # Processing Mode Label

        lbl_Dfames = QtWidgets.QLabel('Duplicate frames: ', window)
        lbl_Dfames.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_Dfames.setMinimumHeight(28)
        lbl_Dfames.setAlignment(QtCore.Qt.AlignCenter)
        dframes_hbox.addWidget(lbl_Dfames)

        # Processing Mode Selector

        btn_DfamesSelector = QtWidgets.QPushButton(window)
        btn_DfamesSelector.setText(self.modes_list.get(self.dedup_mode))
        def selectNewMode(new_mode_id):
            self.dedup_mode = new_mode_id
            btn_DfamesSelector.setText(self.modes_list.get(self.dedup_mode))
        btn_DfamesSelector.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_DfamesSelector.setMinimumSize(120, 28)
        btn_DfamesSelector.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_DfamesSelector_menu = QtWidgets.QMenu()

        for new_mode_id in sorted(self.modes_list.keys()):
            code = self.modes_list.get(new_mode_id, 'Interpolate')
            action = btn_DfamesSelector_menu.addAction(code)
            action.triggered[()].connect(lambda new_mode_id=new_mode_id: selectNewMode(new_mode_id))
        btn_DfamesSelector.setMenu(btn_DfamesSelector_menu)
        dframes_hbox.addWidget(btn_DfamesSelector)

        # Fine Flow button
        
        def enableUHD():
            if self.prefs.get('dedup_uhd', False):
                btn_UHD.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                        'QToolTip {color: black; background-color:  #ffffd9; border: 0px}')
                self.prefs['dedup_uhd'] = False
            else:
                btn_UHD.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}'
                                        'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
                self.prefs['dedup_uhd'] = True
        btn_UHD = QtWidgets.QPushButton('Reduce flow res', window)
        btn_UHD.setToolTip('<b>Reduce flow res button</b><br>Use less details for analyzis, sometimes could be helpful with large motion.')
        btn_UHD.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_UHD.setMinimumSize(148, 28)
        if self.prefs.get('dedup_uhd', False):
            btn_UHD.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}'
                                    'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
        else:
            btn_UHD.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
        btn_UHD.pressed.connect(enableUHD)
        dframes_hbox.addWidget(btn_UHD)

        # Cpu Proc button

        if not sys.platform == 'darwin':            
            def enableCpuProc():
                if self.cpu:
                    btn_CpuProc.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
                    self.cpu = False
                else:
                    btn_CpuProc.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
                    self.cpu = True

            btn_CpuProc = QtWidgets.QPushButton('CPU Proc', window)
            btn_CpuProc.setFocusPolicy(QtCore.Qt.NoFocus)
            btn_CpuProc.setMinimumSize(88, 28)
            # btn_CpuProc.move(0, 34)
            if self.cpu:
                btn_CpuProc.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
            else:
                btn_CpuProc.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            btn_CpuProc.pressed.connect(enableCpuProc)

            dframes_hbox.addWidget(btn_CpuProc)

        ### Model Selector START

        current_model_name = self.model_map.get(self.prefs.get('trained_models_folder'), 'Unknown')
        
        # Model Selector Button
        btn_ModelSelector = QtWidgets.QPushButton(window)
        btn_ModelSelector.setText(current_model_name)
        
        def selectModel(trained_models_folder):
            self.prefs['trained_models_folder'] = trained_models_folder
            btn_ModelSelector.setText(self.model_map.get(trained_models_folder))

        btn_ModelSelector.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_ModelSelector.setMinimumSize(140, 28)
        btn_ModelSelector.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')

        btn_ModelSelector_menu = QtWidgets.QMenu()
        for trained_models_folder in sorted(self.model_map.keys()):
            
            code = self.model_map.get(trained_models_folder)
            action = btn_ModelSelector_menu.addAction(code)
            action.triggered[()].connect(lambda trained_models_folder=trained_models_folder: selectModel(trained_models_folder))
    
        btn_ModelSelector.setMenu(btn_ModelSelector_menu)
        dframes_hbox.addWidget(btn_ModelSelector)

        ### Model Selector END

        vbox.addLayout(dframes_hbox)
        vbox.addWidget(lbl_Spacer)

        # Work Folder Label

        lbl_WorkFolder = QtWidgets.QLabel('Export folder', window)
        lbl_WorkFolder.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_WorkFolder.setMinimumHeight(28)
        lbl_WorkFolder.setMaximumHeight(28)
        lbl_WorkFolder.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_WorkFolder)

        # Work Folder Text Field

        hbox_workfolder = QtWidgets.QHBoxLayout()
        hbox_workfolder.setAlignment(QtCore.Qt.AlignLeft)


        def chooseFolder():
            result_folder = str(QtWidgets.QFileDialog.getExistingDirectory(window, "Open Directory", self.working_folder, QtWidgets.QFileDialog.ShowDirsOnly))
            if result_folder =='':
                return
            self.working_folder = result_folder
            txt_WorkFolder.setText(self.working_folder)
            self.prefs['working_folder'] = self.working_folder

            #dialog = QtWidgets.QFileDialog()
            #dialog.setWindowTitle('Select export folder')
            #dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
            #dialog.setDirectory(self.working_folder)
            #dialog.setFileMode(QtWidgets.QFileDialog.Directory)
            #path = QtWidgets.QFileDialog.getExistingDirectory()
            # dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
            #
            # if dialog.exec_() == QtWidgets.QDialog.Accepted:
            #    file_full_path = str(dialog.selectedFiles()[0])

        def txt_WorkFolder_textChanged():
            self.working_folder = txt_WorkFolder.text()
        txt_WorkFolder = QtWidgets.QLineEdit('', window)
        txt_WorkFolder.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_WorkFolder.setMinimumSize(280, 28)
        txt_WorkFolder.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
        txt_WorkFolder.setText(self.working_folder)
        txt_WorkFolder.textChanged.connect(txt_WorkFolder_textChanged)
        hbox_workfolder.addWidget(txt_WorkFolder)

        btn_changePreset = QtWidgets.QPushButton('Choose', window)
        btn_changePreset.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_changePreset.setMinimumSize(88, 28)
        btn_changePreset.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                   'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_changePreset.clicked.connect(chooseFolder)
        hbox_workfolder.addWidget(btn_changePreset, alignment = QtCore.Qt.AlignLeft)

        vbox.addLayout(hbox_workfolder)

        vbox.addWidget(lbl_Spacer)

        # Create and Cancel Buttons
        hbox_Create = QtWidgets.QHBoxLayout()

        select_btn = QtWidgets.QPushButton('Create', window)
        select_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        select_btn.setMinimumSize(128, 28)
        select_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        select_btn.clicked.connect(window.accept)
        select_btn.setAutoDefault(True)
        select_btn.setDefault(True)

        cancel_btn = QtWidgets.QPushButton('Cancel', window)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.setMinimumSize(128, 28)
        cancel_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        cancel_btn.clicked.connect(window.reject)

        hbox_Create.addWidget(cancel_btn)
        hbox_Create.addWidget(select_btn)

        vbox.addLayout(hbox_Create)

        window.setLayout(vbox)
        if window.exec_():
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            self.framework.save_prefs()
            return {
                'mode': self.dedup_mode,
                'working_folder': self.working_folder,
                'hold_konsole': True if modifiers == QtCore.Qt.ControlModifier else False
            }
        else:
            return {}

    def fluidmorph(self, selection):
        def usage_message():
            from PySide2 import QtWidgets, QtCore
            msg = 'Please select two clips of the same dimentions and length'
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            mbox.exec_()

        import flame
        clips = []
        for item in selection:
            if isinstance(item, (flame.PyClip)):
                clips.append(item)

        if len(clips) != 2:
            usage_message()
            return
                
        result = self.fluidmorph_dialog(clips = clips)
        if not result:
            return False

        working_folder = str(result.get('working_folder', '/var/tmp'))
        incoming_clip = clips[result.get('incoming')]
        outgoing_clip = clips[result.get('outgoing')]
        hold_konsole = result.get('hold_konsole', False)
        cmd_strings = []

        incoming_clip_name = incoming_clip.name.get_value()
        outgoing_clip_name = outgoing_clip.name.get_value()
        result_folder = os.path.abspath(
            os.path.join(
                working_folder, 
                self.sanitized(incoming_clip_name) + '_FLUID' + '_' + self.create_timestamp_uid()
                )
            )

        if os.path.isdir(result_folder):
            from PySide2 import QtWidgets
            msg = 'Folder %s exists' % result_folder
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            mbox.setStandardButtons(QtWidgets.QMessageBox.Ok|QtWidgets.QMessageBox.Cancel)
            mbox.setStyleSheet('QLabel{min-width: 400px;}')
            btn_Continue = mbox.button(QtWidgets.QMessageBox.Ok)
            btn_Continue.setText('Owerwrite')
            mbox.exec_()
            if mbox.clickedButton() == mbox.button(QtWidgets.QMessageBox.Cancel):
                return False
            cmd = 'rm -f ' + result_folder + '/*'
            self.log('Executing command: %s' % cmd)
            os.system(cmd)

        incoming_folder = os.path.join(result_folder, 'incoming')
        outgoing_folder = os.path.join(result_folder, 'outgoing')
        self.export_clip(incoming_clip, incoming_folder)
        self.export_clip(outgoing_clip, outgoing_folder)

        cmd = 'python3 '
        if self.cpu:
            cmd = 'export OMP_NUM_THREADS=1; python3 '
        cmd += os.path.join(self.framework.bundle_location, 'bundle', 'inference_fluidmorph.py')
        cmd += ' --model ' + self.prefs.get('trained_models_folder')
        cmd += ' --incoming ' + incoming_folder
        cmd += ' --outgoing ' + outgoing_folder
        cmd += ' --output ' + result_folder
        if self.cpu:
            cmd += ' --cpu'
        if self.prefs.get('fluidmorph_uhd', False):
            cmd += ' --UHD'
        cmd += "; "
        cmd_strings.append(cmd)
        
        new_clip_name = incoming_clip_name + '_FLUID'
        watcher = threading.Thread(target=self.import_watcher, args=(result_folder, new_clip_name, incoming_clip.parent, [incoming_folder, outgoing_folder]))
        watcher.daemon = True
        watcher.start()
        self.loops.append(watcher)

        if sys.platform == 'darwin':
            cmd_prefix = """tell application "Terminal" to activate do script "clear; """
            # cmd_prefix += """ echo " & quote & "Received """
            # cmd_prefix += str(number_of_clips)
            #cmd_prefix += ' clip ' if number_of_clips < 2 else ' clips '
            # cmd_prefix += 'to process, press Ctrl+C to cancel" & quote &; '
            cmd_prefix += """/bin/bash -c 'eval " & quote & "$("""
            cmd_prefix += os.path.join(self.env_folder, 'bin', 'conda')
            cmd_prefix += """ shell.bash hook)" & quote & "; conda activate; """
            cmd_prefix += 'cd ' + os.path.join(self.framework.bundle_location, 'bundle') + '; '
            
            ml_cmd = cmd_prefix
           
            for cmd_string in cmd_strings:
                ml_cmd += cmd_string

            ml_cmd += """'; exit" """

            import subprocess
            subprocess.Popen(['osascript', '-e', ml_cmd])
        
        else:
            cmd_prefix = 'konsole '
            if hold_konsole:
                cmd_prefix += '--hold '
            cmd_prefix += """-e /bin/bash -c 'eval "$(""" + os.path.join(self.env_folder, 'bin', 'conda') + ' shell.bash hook)"; conda activate; '
            cmd_prefix += 'cd ' + os.path.join(self.framework.bundle_location, 'bundle') + '; '

            ml_cmd = cmd_prefix
            # ml_cmd += 'echo "Received ' + str(number_of_clips)
            # ml_cmd += ' clip ' if number_of_clips < 2 else ' clips '
            # ml_cmd += 'to process, press Ctrl+C to cancel"; '
            ml_cmd += 'trap exit SIGINT SIGTERM; '

            for cmd_string in cmd_strings:
                ml_cmd += cmd_string

            if hold_konsole:
                ml_cmd += 'echo "Commands finished. You can close this window"'
            ml_cmd +="'"
            self.log('Executing command: %s' % ml_cmd)
            os.system(ml_cmd)

        flame.execute_shortcut('Refresh Thumbnails')

    def fluidmorph_dialog(self, *args, **kwargs):
        from PySide2 import QtWidgets, QtCore

        clips = kwargs.get('clips')
        self.incoming_clip_id = 0
        self.outgoing_clip_id = 1
        
        self.clip_names_list = {
            0: clips[0].name.get_value(),
            1: clips[1].name.get_value(), 
        }

        pprint (self.clip_names_list)

        window = QtWidgets.QDialog()
        window.setMinimumSize(280, 180)
        window.setWindowTitle('Create Fluidmorph Transition')
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #313131')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-150, (screen_res.height() / 2)-180)

        # Spacer
        lbl_Spacer = QtWidgets.QLabel('', window)
        lbl_Spacer.setStyleSheet('QFrame {color: #989898; background-color: #313131}')
        lbl_Spacer.setMinimumHeight(4)
        lbl_Spacer.setMaximumHeight(4)
        lbl_Spacer.setAlignment(QtCore.Qt.AlignCenter)


        vbox = QtWidgets.QVBoxLayout()
        vbox.setAlignment(QtCore.Qt.AlignTop)
        
        '''
        # CLIP order indicator label
        lbl_text = 'Transition: '
        lbl_text += self.clip_names_list.get(self.incoming_clip_id) + ' -> ' + self.clip_names_list.get(self.outgoing_clip_id)
        lbl_ClipOrder = QtWidgets.QLabel(lbl_text, window)
        lbl_ClipOrder.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_ClipOrder.setMinimumHeight(28)
        lbl_ClipOrder.setMaximumHeight(28)
        lbl_ClipOrder.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_ClipOrder)
        '''

        # Duplicate frames action hbox
        dframes_hbox = QtWidgets.QHBoxLayout()
        # dframes_hbox.setAlignment(QtCore.Qt.AlignLeft)

        # Processing Mode Label

        lbl_Dfames = QtWidgets.QLabel('Start from: ', window)
        lbl_Dfames.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_Dfames.setMinimumHeight(28)
        lbl_Dfames.setAlignment(QtCore.Qt.AlignCenter)
        dframes_hbox.addWidget(lbl_Dfames)

        # Processing Mode Selector

        btn_DfamesSelector = QtWidgets.QPushButton(window)
        btn_DfamesSelector.setText(self.clip_names_list.get(self.incoming_clip_id))
        def selectNewMode(new_incoming_id):
            self.outgoing_clip_id = self.incoming_clip_id
            self.incoming_clip_id = new_incoming_id
            btn_DfamesSelector.setText(self.clip_names_list.get(new_incoming_id))
            lbl_text = self.clip_names_list.get(self.incoming_clip_id) + ' -> ' + self.clip_names_list.get(self.outgoing_clip_id)
            # lbl_ClipOrder.setText(lbl_text)
        btn_DfamesSelector.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_DfamesSelector.setMinimumSize(120, 28)
        btn_DfamesSelector.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_DfamesSelector_menu = QtWidgets.QMenu()

        for new_incoming_id in sorted(self.clip_names_list.keys()):
            name = self.clip_names_list.get(new_incoming_id)
            action = btn_DfamesSelector_menu.addAction(name)
            action.triggered[()].connect(lambda new_incoming_id=new_incoming_id: selectNewMode(new_incoming_id))
        btn_DfamesSelector.setMenu(btn_DfamesSelector_menu)
        dframes_hbox.addWidget(btn_DfamesSelector)

        # Fine Flow button
        
        def enableUHD():
            if self.prefs.get('fluidmorph_uhd', False):
                btn_UHD.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                        'QToolTip {color: black; background-color:  #ffffd9; border: 0px}')
                self.prefs['fluidmorph_uhd'] = False
            else:
                btn_UHD.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}'
                                        'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
                self.prefs['fluidmorph_uhd'] = True
        btn_UHD = QtWidgets.QPushButton('Reduce flow res', window)
        btn_UHD.setToolTip('<b>Reduce flow res button</b><br>Use less details for analyzis, sometimes could be helpful with large motion.')
        btn_UHD.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_UHD.setMinimumSize(148, 28)
        if self.prefs.get('fluidmorph_uhd', False):
            btn_UHD.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}'
                                    'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
        else:
            btn_UHD.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
        btn_UHD.pressed.connect(enableUHD)
        dframes_hbox.addWidget(btn_UHD)

        # Cpu Proc button

        if not sys.platform == 'darwin':            
            def enableCpuProc():
                if self.cpu:
                    btn_CpuProc.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
                    self.cpu = False
                else:
                    btn_CpuProc.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
                    self.cpu = True

            btn_CpuProc = QtWidgets.QPushButton('CPU Proc', window)
            btn_CpuProc.setFocusPolicy(QtCore.Qt.NoFocus)
            btn_CpuProc.setMinimumSize(88, 28)
            # btn_CpuProc.move(0, 34)
            if self.cpu:
                btn_CpuProc.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
            else:
                btn_CpuProc.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            btn_CpuProc.pressed.connect(enableCpuProc)

            dframes_hbox.addWidget(btn_CpuProc)

        ### Model Selector START

        current_model_name = self.model_map.get(self.prefs.get('trained_models_folder'), 'Unknown')
        
        # Model Selector Button
        btn_ModelSelector = QtWidgets.QPushButton(window)
        btn_ModelSelector.setText(current_model_name)
        
        def selectModel(trained_models_folder):
            self.prefs['trained_models_folder'] = trained_models_folder
            btn_ModelSelector.setText(self.model_map.get(trained_models_folder))

        btn_ModelSelector.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_ModelSelector.setMinimumSize(140, 28)
        btn_ModelSelector.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')

        btn_ModelSelector_menu = QtWidgets.QMenu()
        for trained_models_folder in sorted(self.model_map.keys()):
            
            code = self.model_map.get(trained_models_folder)
            action = btn_ModelSelector_menu.addAction(code)
            action.triggered[()].connect(lambda trained_models_folder=trained_models_folder: selectModel(trained_models_folder))
    
        btn_ModelSelector.setMenu(btn_ModelSelector_menu)
        dframes_hbox.addWidget(btn_ModelSelector)

        ### Model Selector END

        vbox.addLayout(dframes_hbox)
        vbox.addWidget(lbl_Spacer)

        # Work Folder Label

        lbl_WorkFolder = QtWidgets.QLabel('Export folder', window)
        lbl_WorkFolder.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_WorkFolder.setMinimumHeight(28)
        lbl_WorkFolder.setMaximumHeight(28)
        lbl_WorkFolder.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_WorkFolder)

        # Work Folder Text Field

        hbox_workfolder = QtWidgets.QHBoxLayout()
        hbox_workfolder.setAlignment(QtCore.Qt.AlignLeft)


        def chooseFolder():
            result_folder = str(QtWidgets.QFileDialog.getExistingDirectory(window, "Open Directory", self.working_folder, QtWidgets.QFileDialog.ShowDirsOnly))
            if result_folder =='':
                return
            self.working_folder = result_folder
            txt_WorkFolder.setText(self.working_folder)
            self.prefs['working_folder'] = self.working_folder

            #dialog = QtWidgets.QFileDialog()
            #dialog.setWindowTitle('Select export folder')
            #dialog.setOption(QtWidgets.QFileDialog.ShowDirsOnly, True)
            #dialog.setDirectory(self.working_folder)
            #dialog.setFileMode(QtWidgets.QFileDialog.Directory)
            #path = QtWidgets.QFileDialog.getExistingDirectory()
            # dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
            #
            # if dialog.exec_() == QtWidgets.QDialog.Accepted:
            #    file_full_path = str(dialog.selectedFiles()[0])

        def txt_WorkFolder_textChanged():
            self.working_folder = txt_WorkFolder.text()
        txt_WorkFolder = QtWidgets.QLineEdit('', window)
        txt_WorkFolder.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_WorkFolder.setMinimumSize(280, 28)
        txt_WorkFolder.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
        txt_WorkFolder.setText(self.working_folder)
        txt_WorkFolder.textChanged.connect(txt_WorkFolder_textChanged)
        hbox_workfolder.addWidget(txt_WorkFolder)

        btn_changePreset = QtWidgets.QPushButton('Choose', window)
        btn_changePreset.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_changePreset.setMinimumSize(88, 28)
        btn_changePreset.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                   'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_changePreset.clicked.connect(chooseFolder)
        hbox_workfolder.addWidget(btn_changePreset, alignment = QtCore.Qt.AlignLeft)

        vbox.addLayout(hbox_workfolder)
        vbox.addWidget(lbl_Spacer)

        # Create and Cancel Buttons
        hbox_Create = QtWidgets.QHBoxLayout()

        select_btn = QtWidgets.QPushButton('Create', window)
        select_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        select_btn.setMinimumSize(128, 28)
        select_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        select_btn.clicked.connect(window.accept)
        select_btn.setAutoDefault(True)
        select_btn.setDefault(True)

        cancel_btn = QtWidgets.QPushButton('Cancel', window)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.setMinimumSize(128, 28)
        cancel_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        cancel_btn.clicked.connect(window.reject)

        hbox_Create.addWidget(cancel_btn)
        hbox_Create.addWidget(select_btn)

        vbox.addLayout(hbox_Create)

        window.setLayout(vbox)
        if window.exec_():
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            self.framework.save_prefs()
            return {
                'incoming': self.incoming_clip_id,
                'outgoing': self.outgoing_clip_id,
                'working_folder': self.working_folder,
                'hold_konsole': True if modifiers == QtCore.Qt.ControlModifier else False
            }
        else:
            return {}

    def fltw(self, selection):
        def sequence_message():
            from PySide2 import QtWidgets, QtCore
            msg = 'Please select single-track clips with no versions or edits'
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            mbox.exec_()
        
        def effect_message():
            from PySide2 import QtWidgets, QtCore
            msg = 'Please select clips with Timewarp Timeline FX'
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            mbox.exec_()

        def bake_message():
            from PySide2 import QtWidgets, QtCore
            msg = 'Please bake your keyframes so there is a keyframe at every frame'
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            mbox.exec_()

        def parse_message(e):
            from PySide2 import QtWidgets, QtCore
            import traceback
            msg = 'Error parsing TW setup file: ' + pformat(e)
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            mbox.setDetailedText(pformat(traceback.format_exc()))
            mbox.setStyleSheet('QLabel{min-width: 800px;}')
            mbox.exec_()

        def dictify(r,root=True):
            from copy import copy

            if root:
                return {r.tag : dictify(r, False)}

            d = copy(r.attrib)
            if r.text:
                d["_text"]=r.text
            for x in r.findall("./*"):
                if x.tag not in d:
                    d[x.tag]=[]
                d[x.tag].append(dictify(x,False))
            return d
        
        verified_clips = []
        temp_setup_path = '/var/tmp/temporary_tw_setup.timewarp_node'

        import flame
        import xml.etree.ElementTree as ET

        for clip in selection:
            if isinstance(clip, (flame.PyClip)):
                if len(clip.versions) != 1:
                    sequence_message()
                    return
                if len (clip.versions[0].tracks) != 1:
                    sequence_message()
                    return
                if len (clip.versions[0].tracks[0].segments) != 1:
                    sequence_message()
                
                effects = clip.versions[0].tracks[0].segments[0].effects
                if not effects:
                    effect_message()
                    return

                verified = False
                for effect in effects:
                    if effect.type == 'Timewarp':
                        effect.save_setup(temp_setup_path)
                        with open(temp_setup_path, 'r') as tw_setup_file:
                            tw_setup_string = tw_setup_file.read()
                            tw_setup_file.close()
                        '''
                            tw_setup_xml = ET.fromstring(tw_setup_string)
                            tw_setup = dictify(tw_setup_xml)
                            try:
                                start = int(tw_setup['Setup']['Base'][0]['Range'][0]['Start'])
                                end = int(tw_setup['Setup']['Base'][0]['Range'][0]['End'])
                                TW_Timing_size = int(tw_setup['Setup']['State'][0]['TW_Timing'][0]['Channel'][0]['Size'][0]['_text'])
                                TW_SpeedTiming_size = int(tw_setup['Setup']['State'][0]['TW_SpeedTiming'][0]['Channel'][0]['Size'][0]['_text'])
                                TW_RetimerMode = int(tw_setup['Setup']['State'][0]['TW_RetimerMode'][0]['_text'])
                            except Exception as e:
                                parse_message(e)
                                return

                            if TW_SpeedTiming_size == 1 and TW_RetimerMode == 0:
                                pass

                            elif not (TW_Timing_size > end-start or TW_SpeedTiming_size > end-start):
                                bake_message()
                                return
                        '''
                        verified = True
                
                if not verified:
                    effect_message()
                    return

                verified_clips.append((clip, tw_setup_string))
        
        os.remove(temp_setup_path)

        result = self.fltw_dialog()
        if not result:
            return False

        working_folder = str(result.get('working_folder', '/var/tmp'))
        speed = result.get('speed', 1)
        hold_konsole = result.get('hold_konsole', False)

        cmd_strings = []
        number_of_clips = 0

        for clip, tw_setup_string in verified_clips:
            number_of_clips += 1
            clip_name = clip.name.get_value()

            result_folder = os.path.abspath(
                os.path.join(
                    working_folder, 
                    self.sanitized(clip_name) + '_TWML' + '_' + self.create_timestamp_uid()
                    )
                )

            if os.path.isdir(result_folder):
                from PySide2 import QtWidgets
                msg = 'Folder %s exists' % output_folder
                mbox = QtWidgets.QMessageBox()
                mbox.setWindowTitle('flameTimewrarpML')
                mbox.setText(msg)
                mbox.setStandardButtons(QtWidgets.QMessageBox.Ok|QtWidgets.QMessageBox.Cancel)
                mbox.setStyleSheet('QLabel{min-width: 400px;}')
                btn_Continue = mbox.button(QtWidgets.QMessageBox.Ok)
                btn_Continue.setText('Owerwrite')
                mbox.exec_()
                if mbox.clickedButton() == mbox.button(QtWidgets.QMessageBox.Cancel):
                    return False
                cmd = 'rm -f ' + result_folder + '/*'
                self.log('Executing command: %s' % cmd)
                os.system(cmd)

            clip.render()

            source_clip_folder = os.path.join(result_folder, 'source')
            export_preset = os.path.join(self.framework.bundle_path, 'source_export.xml')
            tw_setup_path = os.path.join(source_clip_folder, 'tw_setup.timewarp_node')
            self.export_clip(clip, source_clip_folder, export_preset)
            with open(tw_setup_path, 'a') as tw_setup_file:
                tw_setup_file.write(tw_setup_string)
                tw_setup_file.close()

            '''
            seg_data = {}
            seg_data['record_duration'] = clip.versions[0].tracks[0].segments[0].record_duration.relative_frame
            seg_data['record_in'] = clip.versions[0].tracks[0].segments[0].record_in.relative_frame
            seg_data['record_out'] = clip.versions[0].tracks[0].segments[0].record_out.relative_frame
            seg_data['source_duration'] = clip.versions[0].tracks[0].segments[0].source_duration.relative_frame
            seg_data['source_in'] = clip.versions[0].tracks[0].segments[0].source_in.relative_frame
            seg_data['source_out'] = clip.versions[0].tracks[0].segments[0].source_out.relative_frame
            pprint (seg_data)
            '''

            record_in = clip.versions[0].tracks[0].segments[0].record_in.relative_frame
            record_out = clip.versions[0].tracks[0].segments[0].record_out.relative_frame

            cmd = 'python3 '
            if self.cpu:
                cmd = 'export OMP_NUM_THREADS=1; python3 '
            cmd += os.path.join(self.framework.bundle_location, 'bundle', 'inference_flame_tw.py')
            cmd += ' --model ' + self.prefs.get('trained_models_folder')
            cmd += ' --input ' + source_clip_folder + ' --output ' + result_folder + ' --setup ' + tw_setup_path
            cmd += ' --record_in ' + str(record_in) + ' --record_out ' + str(record_out)
            if self.cpu:
                cmd += ' --cpu'
            if self.prefs.get('fltw_uhd', False):
                cmd += ' --UHD'
            cmd += "; "
            cmd_strings.append(cmd)
            
            new_clip_name = clip_name + '_TWML'
            watcher = threading.Thread(target=self.import_watcher, args=(result_folder, new_clip_name, clip.parent, [source_clip_folder]))
            watcher.daemon = True
            watcher.start()
            self.loops.append(watcher)

        if sys.platform == 'darwin':
            cmd_prefix = """tell application "Terminal" to activate do script "clear; """
            # cmd_prefix += """ echo " & quote & "Received """
            # cmd_prefix += str(number_of_clips)
            #cmd_prefix += ' clip ' if number_of_clips < 2 else ' clips '
            # cmd_prefix += 'to process, press Ctrl+C to cancel" & quote &; '
            cmd_prefix += """/bin/bash -c 'eval " & quote & "$("""
            cmd_prefix += os.path.join(self.env_folder, 'bin', 'conda')
            cmd_prefix += """ shell.bash hook)" & quote & "; conda activate; """
            cmd_prefix += 'cd ' + os.path.join(self.framework.bundle_location, 'bundle') + '; '
            
            ml_cmd = cmd_prefix
           
            for cmd_string in cmd_strings:
                ml_cmd += cmd_string

            ml_cmd += """'; exit" """

            import subprocess
            subprocess.Popen(['osascript', '-e', ml_cmd])
        
        else:
            cmd_prefix = 'konsole '
            if hold_konsole:
                cmd_prefix += '--hold '
            cmd_prefix += """-e /bin/bash -c 'eval "$(""" + os.path.join(self.env_folder, 'bin', 'conda') + ' shell.bash hook)"; conda activate; '
            cmd_prefix += 'cd ' + os.path.join(self.framework.bundle_location, 'bundle') + '; '

            ml_cmd = cmd_prefix
            ml_cmd += 'echo "Received ' + str(number_of_clips)
            ml_cmd += ' clip ' if number_of_clips < 2 else ' clips '
            ml_cmd += 'to process, press Ctrl+C to cancel"; '
            ml_cmd += 'trap exit SIGINT SIGTERM; '

            for cmd_string in cmd_strings:
                ml_cmd += cmd_string

            if hold_konsole:
                ml_cmd += 'echo "Commands finished. You can close this window"'
            ml_cmd +="'"
            self.log('Executing command: %s' % ml_cmd)
            os.system(ml_cmd)

        flame.execute_shortcut('Refresh Thumbnails')

    def fltw_dialog(self, *args, **kwargs):
        from PySide2 import QtWidgets, QtCore
        
        # flameMenuNewBatch_prefs = self.framework.prefs.get('flameMenuNewBatch', {})
        # self.asset_task_template =  flameMenuNewBatch_prefs.get('asset_task_template', {})

        window = QtWidgets.QDialog()
        window.setMinimumSize(280, 180)
        window.setWindowTitle('Slow down clip(s) with ML')
        window.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        window.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        window.setStyleSheet('background-color: #313131')

        screen_res = QtWidgets.QDesktopWidget().screenGeometry()
        window.move((screen_res.width()/2)-150, (screen_res.height() / 2)-180)

        # Spacer
        lbl_Spacer = QtWidgets.QLabel('', window)
        lbl_Spacer.setStyleSheet('QFrame {color: #989898; background-color: #313131}')
        lbl_Spacer.setMinimumHeight(2)
        lbl_Spacer.setMaximumHeight(2)
        lbl_Spacer.setAlignment(QtCore.Qt.AlignCenter)

        vbox = QtWidgets.QVBoxLayout()
        vbox.setAlignment(QtCore.Qt.AlignTop)

        # New Speed hbox
        new_speed_hbox = QtWidgets.QHBoxLayout()
        # new_speed_hbox.setAlignment(QtCore.Qt.AlignCenter)

        # New Speed label

        lbl_NewSpeed = QtWidgets.QLabel('Processing Options: ', window)
        lbl_NewSpeed.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_NewSpeed.setMinimumHeight(28)
        lbl_NewSpeed.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        new_speed_hbox.addWidget(lbl_NewSpeed)

        # Reduce flow res button

        def enableUHD():
            if self.prefs.get('fltw_uhd', False):
                btn_UHD.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                        'QToolTip {color: black; background-color:  #ffffd9; border: 0px}')
                self.prefs['fltw_uhd'] = False
            else:
                btn_UHD.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}'
                                        'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
                self.prefs['fltw_uhd'] = True
        btn_UHD = QtWidgets.QPushButton('Reduce flow res', window)
        btn_UHD.setToolTip('<b>Reduce flow res button</b><br>Use less details for analyzis, sometimes could be helpful with large motion.')
        btn_UHD.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_UHD.setMinimumSize(148, 28)
        if self.prefs.get('fltw_uhd', False):
            btn_UHD.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}'
                                    'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
        else:
            btn_UHD.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QToolTip {color: black; background-color: #ffffd9; border: 0px}')
        btn_UHD.pressed.connect(enableUHD)
        new_speed_hbox.addWidget(btn_UHD)

        # Cpu Proc button

        if not sys.platform == 'darwin':            
            def enableCpuProc():
                if self.cpu:
                    btn_CpuProc.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
                    self.cpu = False
                else:
                    btn_CpuProc.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
                    self.cpu = True

            btn_CpuProc = QtWidgets.QPushButton('CPU Proc', window)
            btn_CpuProc.setFocusPolicy(QtCore.Qt.NoFocus)
            btn_CpuProc.setMinimumSize(88, 28)
            if self.cpu:
                btn_CpuProc.setStyleSheet('QPushButton {font:italic; background-color: #4f4f4f; color: #d9d9d9; border-top: 1px inset black; border-bottom: 1px inset #555555}')
            else:
                btn_CpuProc.setStyleSheet('QPushButton {color: #989898; background-color: #373737; border-top: 1px inset #555555; border-bottom: 1px inset black}')
            btn_CpuProc.pressed.connect(enableCpuProc)
            new_speed_hbox.addWidget(btn_CpuProc)

        ### Model Selector START

        current_model_name = self.model_map.get(self.prefs.get('trained_models_folder'), 'Unknown')
        
        # Model Selector Button
        btn_ModelSelector = QtWidgets.QPushButton(window)
        btn_ModelSelector.setText(current_model_name)
        
        def selectModel(trained_models_folder):
            self.prefs['trained_models_folder'] = trained_models_folder
            btn_ModelSelector.setText(self.model_map.get(trained_models_folder))

        btn_ModelSelector.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_ModelSelector.setMinimumSize(140, 28)
        btn_ModelSelector.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')

        btn_ModelSelector_menu = QtWidgets.QMenu()
        for trained_models_folder in sorted(self.model_map.keys()):
            
            code = self.model_map.get(trained_models_folder)
            action = btn_ModelSelector_menu.addAction(code)
            action.triggered[()].connect(lambda trained_models_folder=trained_models_folder: selectModel(trained_models_folder))
    
        btn_ModelSelector.setMenu(btn_ModelSelector_menu)
        new_speed_hbox.addWidget(btn_ModelSelector)

        ### Model Selector END
        
        vbox.addLayout(new_speed_hbox)
        vbox.addWidget(lbl_Spacer)

        # Work Folder Label

        lbl_WorkFolder = QtWidgets.QLabel('Export folder', window)
        lbl_WorkFolder.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_WorkFolder.setMinimumHeight(28)
        lbl_WorkFolder.setMaximumHeight(28)
        lbl_WorkFolder.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_WorkFolder)

        # Work Folder Text Field

        hbox_workfolder = QtWidgets.QHBoxLayout()
        hbox_workfolder.setAlignment(QtCore.Qt.AlignLeft)

        def chooseFolder():
            result_folder = str(QtWidgets.QFileDialog.getExistingDirectory(window, "Open Directory", self.working_folder, QtWidgets.QFileDialog.ShowDirsOnly))
            if result_folder =='':
                return
            self.working_folder = result_folder
            txt_WorkFolder.setText(self.working_folder)
            self.prefs['working_folder'] = self.working_folder

        def txt_WorkFolder_textChanged():
            self.working_folder = txt_WorkFolder.text()
        txt_WorkFolder = QtWidgets.QLineEdit('', window)
        txt_WorkFolder.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_WorkFolder.setMinimumSize(280, 28)
        txt_WorkFolder.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
        txt_WorkFolder.setText(self.working_folder)
        txt_WorkFolder.textChanged.connect(txt_WorkFolder_textChanged)
        hbox_workfolder.addWidget(txt_WorkFolder)

        btn_changePreset = QtWidgets.QPushButton('Choose', window)
        btn_changePreset.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_changePreset.setMinimumSize(88, 28)
        btn_changePreset.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                   'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_changePreset.clicked.connect(chooseFolder)
        hbox_workfolder.addWidget(btn_changePreset, alignment = QtCore.Qt.AlignLeft)

        vbox.addLayout(hbox_workfolder)

        vbox.addWidget(lbl_Spacer)
        vbox.addWidget(lbl_Spacer)

        # Create and Cancel Buttons
        hbox_Create = QtWidgets.QHBoxLayout()

        select_btn = QtWidgets.QPushButton('Create', window)
        select_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        select_btn.setMinimumSize(128, 28)
        select_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        select_btn.clicked.connect(window.accept)
        select_btn.setAutoDefault(True)
        select_btn.setDefault(True)

        cancel_btn = QtWidgets.QPushButton('Cancel', window)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.setMinimumSize(128, 28)
        cancel_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        cancel_btn.clicked.connect(window.reject)

        hbox_Create.addWidget(cancel_btn)
        hbox_Create.addWidget(select_btn)

        vbox.addLayout(hbox_Create)

        window.setLayout(vbox)
        if window.exec_():
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            self.framework.save_prefs()
            return {
                'working_folder': self.working_folder,
                'hold_konsole': True if modifiers == QtCore.Qt.ControlModifier else False
            }
        else:
            return {}

    def dialog_model_path(self,  window, vbox):
        from PySide2 import QtWidgets, QtCore

        # Trained Model Path label

        lbl_WorkFolder = QtWidgets.QLabel('Trained Model', window)
        lbl_WorkFolder.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_WorkFolder.setMinimumHeight(28)
        lbl_WorkFolder.setMaximumHeight(28)
        lbl_WorkFolder.setAlignment(QtCore.Qt.AlignCenter)
        vbox.addWidget(lbl_WorkFolder)

        # Trained Model Path Text Field

        hbox_trainedmodelfolder = QtWidgets.QHBoxLayout()
        hbox_trainedmodelfolder.setAlignment(QtCore.Qt.AlignLeft)

        def show_missing_model_files(model_files):
            msg = 'One of the modules files not found. Make sure %s are in folder' % pformat(model_files)
            mbox = QtWidgets.QMessageBox()
            mbox.setWindowTitle('flameTimewrarpML')
            mbox.setText(msg)
            mbox.exec_()

        def chooseFolder():
            dialog = QtWidgets.QFileDialog(window)
            dialog.setWindowTitle('Select any of Trained Model pkl files')
            dialog.setNameFilter('PKL files (*.pkl)')
            dialog.setFileMode(QtWidgets.QFileDialog.ExistingFiles)
            dialog.setDirectory(self.prefs.get('trained_models_folder'))
            if dialog.exec_() == QtWidgets.QDialog.Accepted:
                file_names = dialog.selectedFiles()
                if file_names:
                    result_folder = os.path.dirname(file_names[0])
                else:
                    return
            
            model_files = [
                'contextnet.pkl',
                'flownet.pkl',
                'unet.pkl'
            ]
            
            for model_file in model_files:
                model_file_path = os.path.join(result_folder, model_file)
                if not os.path.isfile(model_file_path):
                    show_missing_model_files(model_files)
                    return

            txt_TrainedModelFolder.setText(result_folder)
            self.prefs['trained_models_folder'] = result_folder
    
        def txt_TrainedModelFolder_textChanged():
            self.prefs['trained_models_folder'] = txt_TrainedModelFolder.text()
    
        txt_TrainedModelFolder = QtWidgets.QLineEdit('', window)
        txt_TrainedModelFolder.setFocusPolicy(QtCore.Qt.ClickFocus)
        txt_TrainedModelFolder.setMinimumSize(280, 28)
        txt_TrainedModelFolder.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
        txt_TrainedModelFolder.setText(self.prefs.get('trained_models_folder'))
        txt_TrainedModelFolder.textChanged.connect(txt_TrainedModelFolder_textChanged)
        hbox_trainedmodelfolder.addWidget(txt_TrainedModelFolder)

        btn_changePreset = QtWidgets.QPushButton('Choose', window)
        btn_changePreset.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_changePreset.setMinimumSize(88, 28)
        btn_changePreset.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                   'QPushButton:pressed {font:italic; color: #d9d9d9}')
        btn_changePreset.clicked.connect(chooseFolder)
        hbox_trainedmodelfolder.addWidget(btn_changePreset, alignment = QtCore.Qt.AlignLeft)

        vbox.addLayout(hbox_trainedmodelfolder)

    def dialog_model_selector(self, window, layout):
        from PySide2 import QtWidgets, QtCore

        lbl_Model = QtWidgets.QLabel('Model ', window)
        lbl_Model.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_Model.setMinimumHeight(28)
        lbl_Model.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(lbl_Model)

        model_map = {
            os.path.join(
                self.framework.bundle_location,
                'bundle', 'trained_models', 'default', 'v1.8.model'
                ): '1One',
            os.path.join(
                self.framework.bundle_location,
                'bundle', 'trained_models', 'default', 'v2.0.model'
                ): '2Two',
        }

        current_model_name = model_map.get(self.prefs.get('trained_models_folder'), 'Unknown')
        '''
        # Model Selector Button
        btn_ModelSelector = QtWidgets.QPushButton(window)
        btn_ModelSelector.setText(current_model_name)
        
        def selectModel(trained_models_folder):
            self.prefs['trained_models_folder'] = trained_models_folder
            btn_ModelSelector.setText(model_map.get(trained_models_folder), 'Unknown')

        btn_ModelSelector.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_ModelSelector.setMinimumSize(80, 28)
        btn_ModelSelector.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')

        btn_ModelSelector_menu = QtWidgets.QMenu()
        for trained_models_folder in sorted(model_map.keys()):
            
            code = model_map.get(trained_models_folder)
            action = btn_ModelSelector_menu.addAction(code)
            # action.triggered[()].connect(lambda trained_models_folder=trained_models_folder: selectModel(trained_models_folder))
    
        btn_ModelSelector.setMenu(btn_ModelSelector_menu)
        '''
        btn_NewSpeedSelector = QtWidgets.QPushButton(window)
        btn_NewSpeedSelector.setText(self.new_speed_list.get(self.new_speed))
        def selectNewSpeed(new_speed_id):
            self.new_speed = new_speed_id
            btn_NewSpeedSelector.setText(self.new_speed_list.get(self.new_speed))
        btn_NewSpeedSelector.setFocusPolicy(QtCore.Qt.NoFocus)
        btn_NewSpeedSelector.setMinimumSize(80, 28)
        btn_NewSpeedSelector.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #29323d; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}'
                                    'QPushButton::menu-indicator {image: none;}')
        btn_NewSpeedSelector_menu = QtWidgets.QMenu()

        for new_speed_id in sorted(self.new_speed_list.keys()):
            code = self.new_speed_list.get(new_speed_id, '1/2')
            action = btn_NewSpeedSelector_menu.addAction(code)
            action.triggered[()].connect(lambda new_speed_id=new_speed_id: selectNewSpeed(new_speed_id))
        btn_NewSpeedSelector.setMenu(btn_NewSpeedSelector_menu)
        layout.addWidget(btn_NewSpeedSelector)

        # layout.addWidget(btn_ModelSelector)

    def export_clip(self, clip, export_dir, export_preset = None):
        import flame
        import traceback

        if not os.path.isdir(export_dir):
            self.log('creating folders: %s' % export_dir)
            try:
                os.makedirs(export_dir)
            except Exception as e:
                from PySide2 import QtWidgets, QtCore
                msg = 'flameTimewrarpML: %s' % e
                dmsg = pformat(traceback.format_exc())
                
                def show_error_mbox():
                    mbox = QtWidgets.QMessageBox()
                    mbox.setWindowTitle('flameTimewrarpML')
                    mbox.setText(msg)
                    mbox.setDetailedText(dmsg)
                    mbox.setStyleSheet('QLabel{min-width: 800px;}')
                    mbox.exec_()
            
                flame.schedule_idle_event(show_error_mbox)
                return False

        class ExportHooks(object):
            def preExport(self, info, userData, *args, **kwargs):
                pass
            def postExport(self, info, userData, *args, **kwargs):
                pass
            def preExportSequence(self, info, userData, *args, **kwargs):
                pass
            def postExportSequence(self, info, userData, *args, **kwargs):
                pass
            def preExportAsset(self, info, userData, *args, **kwargs):
                pass
            def postExportAsset(self, info, userData, *args, **kwargs):
                del args, kwargs
                pass
            def exportOverwriteFile(self, path, *args, **kwargs):
                del path, args, kwargs
                return "overwrite"

        exporter = self.flame.PyExporter()
        exporter.foreground = True

        if not export_preset:
            export_preset_folder = self.flame.PyExporter.get_presets_dir(self.flame.PyExporter.PresetVisibility.values.get(2),
                            self.flame.PyExporter.PresetType.values.get(0))
            export_preset = os.path.join(export_preset_folder, 'OpenEXR', 'OpenEXR (16-bit fp PIZ).xml')

        exporter.export(clip, export_preset, export_dir, hooks=ExportHooks())

    def import_watcher(self, import_path, new_clip_name, destination, folders_to_cleanup):
        # create lock file that is to be removed after the job finished 
        # as a signal that triggers clip import
         
        import hashlib
        lockfile_name = hashlib.sha1(import_path.encode()).hexdigest().upper() + '.lock'
        lockfile = os.path.join(self.framework.bundle_location, 'bundle', 'locks', lockfile_name)
        cmd = 'echo "' + import_path + '">' + lockfile
        self.log('Executing command: %s' % cmd)
        os.system(cmd)

        flame_friendly_path = None
        def import_flame_clip():
            import flame
            new_clips = flame.import_clips(flame_friendly_path, destination)
            
            if len(new_clips) > 0:
                new_clip = new_clips[0]
                if new_clip:
                    new_clip.name.set_value(new_clip_name)
            try:
                flame.execute_shortcut('Refresh Thumbnails')
            except:
                pass

            # Colour Mgmt logic for future setting
            '''
            for version in new_clip.versions:
                for track in version.tracks:
                    for segment in track.segments:
                        segment.create_effect('Source Colour Mgmt')
            '''
            # End of Colour Mgmt logic for future settin


            # Hard Commit Logic for future setting
            '''
            for version in new_clip.versions:
                for track in version.tracks:
                    for segment in track.segments:
                        segment.create_effect('Source Image')
            
            new_clip.open_as_sequence()
            flame.execute_shortcut('Hard Commit Selection in Timeline')
            flame.execute_shortcut('Refresh Thumbnails')
            '''
            # End of Hard Commit Logic for future setting


        while self.threads:
            if not os.path.isfile(lockfile):
                self.log('Importing result from: %s' % import_path)
                file_names = [f for f in os.listdir(import_path) if f.endswith('.exr')]
                if file_names:
                    file_names.sort()
                    first_frame, ext = os.path.splitext(file_names[0])
                    last_frame, ext = os.path.splitext(file_names[-1])
                    flame_friendly_path = os.path.join(import_path, '[' + first_frame + '-' + last_frame + ']' + '.exr')

                    import flame
                    flame.schedule_idle_event(import_flame_clip)

                # clean-up source files used
                self.log('Cleaning up temporary files used: %s' % pformat(folders_to_cleanup))
                for folder in folders_to_cleanup:
                    cmd = 'rm -f "' + os.path.abspath(folder) + '/"*'
                    self.log('Executing command: %s' % cmd)
                    os.system(cmd)
                    try:
                        os.rmdir(folder)
                    except Exception as e:
                        self.log('Error removing %s: %s' % (folder, e))

                break
            time.sleep(0.1)

    def terminate_loops(self):
        self.threads = False
        
        for loop in self.loops:
            loop.join()


# --- FLAME STARTUP SEQUENCE ---
# Flame startup sequence is a bit complicated
# If the app installed in /opt/Autodesk/<user>/python
# project hooks are not called at startup. 
# One of the ways to work around it is to check 
# if we are able to import flame module straght away. 
# If it is the case - flame project is already loaded 
# and we can start our constructor. Otherwise we need 
# to wait for app_initialized hook to be called - that would 
# mean the project is finally loaded. 
# project_changed_dict hook seem to be a good place to wrap things up

# main objects:
# app_framework takes care of preferences and general stuff
# apps is a list of apps to load inside the main program

app_framework = None
apps = []

# Exception handler
def exeption_handler(exctype, value, tb):
    from PySide2 import QtWidgets
    import traceback
    msg = 'flameTimewrarpML: Python exception %s in %s' % (value, exctype)
    mbox = QtWidgets.QMessageBox()
    mbox.setWindowTitle('flameTimewrarpML')
    mbox.setText(msg)
    mbox.setDetailedText(pformat(traceback.format_exception(exctype, value, tb)))
    mbox.setStyleSheet('QLabel{min-width: 800px;}')
    mbox.exec_()
    sys.__excepthook__(exctype, value, tb)
sys.excepthook = exeption_handler

# register clean up logic to be called at Flame exit
def cleanup(local_apps, Local_app_framework):
    global app_framework
    global apps
    
    if apps:
        if DEBUG:
            print ('[DEBUG %s] unloading apps:\n%s' % ('flameMenuSG', pformat(apps)))
        while len(apps):
            app = apps.pop()
            if DEBUG:
                print ('[DEBUG %s] unloading: %s' % ('flameMenuSG', app.name))
            app.terminate_loops()
            del app        
        apps = []

    if app_framework:
        print ('PYTHON\t: %s cleaning up' % app_framework.bundle_name)
        app_framework.save_prefs()
        app_framework = None

atexit.register(cleanup, apps, app_framework)

def load_apps(apps, app_framework):
    apps.append(flameTimewarpML(app_framework))
    app_framework.apps = apps
    if DEBUG:
        print ('[DEBUG %s] loaded:\n%s' % (app_framework.bundle_name, pformat(apps)))

def project_changed_dict(info):
    global app_framework
    global apps
    cleanup(apps, app_framework)

def app_initialized(project_name):
    global app_framework
    global apps
    if not app_framework:
        app_framework = flameAppFramework()
        print ('PYTHON\t: %s initializing' % app_framework.bundle_name)
    if not apps:
        load_apps(apps, app_framework)

try:
    import flame
    app_initialized(flame.project.current_project.name)
except:
    pass

def get_media_panel_custom_ui_actions():

    menu = []
    selection = []

    try:
        import flame
        selection = flame.media_panel.selected_entries
    except:
        pass

    for app in apps:
        if app.__class__.__name__ == 'flameTimewarpML':
            app_menu = []
            app_menu = app.build_menu()
            if app_menu:
                menu.append(app_menu)
    return menu


# bundle payload starts here
'''
BUNDLE_PAYLOAD
'''