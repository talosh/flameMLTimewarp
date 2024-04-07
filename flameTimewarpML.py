# type: ignore
'''
flameTimewarpML
Flame 2023.2 and higher
written by Andrii Toloshnyy
andriy.toloshnyy@gmail.com
'''

import os
import sys
import importlib
from pprint import pprint

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    using_pyside6 = True
except ImportError:
    from PySide2 import QtWidgets, QtCore, QtGui
    using_pyside6 = False

import flameTimewarpML_framework
importlib.reload(flameTimewarpML_framework)
from flameTimewarpML_framework import flameAppFramework

from pyflame_lib_flameTimewarpML import * # Import pyflame library for UI elements

settings = {
    'menu_group_name': 'Timewarp ML',
    'debug': False,
    'app_name': 'flameTimewarpML',
    'prefs_folder': os.getenv('FLAMETWML_PREFS'),
    'bundle_folder': os.getenv('FLAMETWML_BUNDLE'),
    'packages_folder': os.getenv('FLAMETWML_PACKAGES'),
    'temp_folder': os.getenv('FLAMETWML_TEMP'),
    'version': 'v0.4.5 dev 001',
}

class ApplyModelDialog():

    def __init__(self, selection, parent=None):

        self.selection = selection

        try:
            self.fw = flameAppFramework()
        except:
            self.fw = None

        self.working_folder = self.fw.prefs.get('working_folder', os.path.expanduser('~'))
        if os.getenv('FLAMESMML_WORK_FOLDER'):
            self.working_folder = os.getenv('FLAMESMML_WORK_FOLDER')
        self.fw.prefs['working_folder'] = self.working_folder
        self.fw.save_prefs()

        self.main_window()

    def main_window(self):

        def open_browser():
            """
            Open Flame file browser to choose export path.
            """

            path = pyflame.file_browser(
                path=self.export_path_entry.text(),
                title='Choose export path',
                select_directory=True,
                window_to_hide=[self.window],
            )

            if path:
                self.export_path_entry.setText(path)
                self.working_folder = path
                self.fw.prefs['working_folder'] = self.working_folder
                self.fw.save_prefs()

        def apply():
            """
            Export selected clips and open flameSimpleML inference
            """

            # Get clip info
            first_clip_name = self.selection[0].name.get_value()
            result_folder = os.path.abspath(
                os.path.join(
                    self.export_path_entry.text(),
                    f'{sanitized(first_clip_name)}_ML_{create_timestamp_uid()}'
                    )
                )
            source_folder = os.path.abspath(
                os.path.join(
                    result_folder,
                    'src'
                    )
                )
            
            # Export selected clips
            clip_number = 1
            for item in self.selection:
                if isinstance(item, (flame.PyClip)):
                    clip = item
                    source_clip_folder = os.path.join(source_folder, f'{clip_number:02}')
                    export_clip(clip, source_clip_folder)
                    clip_number += 1

            first_clip_parent = self.selection[0].parent

            # Open flameSimpleML inference
            flameSimpleMLInference(
                source_folder=source_folder,
                result_folder=result_folder,
                first_clip_parent = first_clip_parent,
                settings=settings
                )
        
            # Close expoty and apply window
            self.window.close()

        # Create export and apply window
        self.window = PyFlameQDialog(
            width=800,
            height=200,
            title=f'flameSimpleML <small>{settings["version"]}',
        )

        # Labels
        self.export_path_label = PyFlameLabel(
            text='Export Path',
        )

        # Entries
        self.export_path_entry = PyFlameLineEdit(
            text=self.working_folder,
            max_width=1000,
        )

        # Buttons
        self.path_browse_button = PyFlameButton(
            text='Browse',
            connect=open_browser,
        )
        self.export_and_apply_button = PyFlameButton(
            text='Export and Apply',
            connect=apply,
            color=Color.BLUE,
        )
        self.cancel_button = PyFlameButton(
            text='Cancel',
            connect=self.window.close,
        )

        # Window layout
        grid_layout = QtWidgets.QGridLayout()

        grid_layout.setRowMinimumHeight(1, 30)
        grid_layout.setColumnMinimumWidth(2, 150)
        grid_layout.setColumnMinimumWidth(3, 150)

        grid_layout.addWidget(self.export_path_label, 0, 0)
        grid_layout.addWidget(self.export_path_entry, 0, 1, 1, 4)
        grid_layout.addWidget(self.path_browse_button, 0, 5)
 
        grid_layout.addWidget(self.cancel_button, 2, 4)
        grid_layout.addWidget(self.export_and_apply_button, 2, 5,)

        # Add layout to window
        self.window.add_layout(grid_layout)

        self.window.show()   


class TimewarpMLDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        try:
            self.fw = flameAppFramework(settings = settings)
        except:
            self.fw = None

        self.working_folder = self.fw.prefs.get('working_folder', os.path.expanduser('~'))
        if os.getenv('FLAMETWML_WORK_FOLDER'):
            self.working_folder = os.getenv('FLAMETWML_WORK_FOLDER')
        self.fw.prefs['working_folder'] = self.working_folder
        self.fw.save_prefs()

        self.setMinimumSize(480, 80)
        self.setWindowTitle(f'{settings["app_name"]}')

        # Setting up layouts
        self.layout = QtWidgets.QVBoxLayout(self)
        self.buttonLayout = QtWidgets.QHBoxLayout()
        self.pathLayout = QtWidgets.QHBoxLayout()

        # Spacer
        lbl_Spacer = QtWidgets.QLabel('', self)
        lbl_Spacer.setStyleSheet('QFrame {color: #989898; background-color: #313131}')
        lbl_Spacer.setMinimumHeight(4)
        lbl_Spacer.setMaximumHeight(4)
        lbl_Spacer.setAlignment(QtCore.Qt.AlignCenter)

        lbl_WorkFolder = QtWidgets.QLabel('Export folder', self)
        lbl_WorkFolder.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
        lbl_WorkFolder.setMinimumHeight(28)
        lbl_WorkFolder.setMaximumHeight(28)
        lbl_WorkFolder.setAlignment(QtCore.Qt.AlignCenter)
        self.pathLayout.addWidget(lbl_WorkFolder)

        def txt_WorkFolder_textChanged():
            self.working_folder = txt_WorkFolder.text()

        if os.getenv('FLAMETWML_WORK_FOLDER'):
            lbl_WorkFolderPath = QtWidgets.QLabel(self.working_folder, self)
            lbl_WorkFolderPath.setStyleSheet('QFrame {color: #989898; background-color: #373737}')
            lbl_WorkFolderPath.setMinimumHeight(28)
            lbl_WorkFolderPath.setMaximumHeight(28)
            lbl_WorkFolderPath.setAlignment(QtCore.Qt.AlignCenter)
            self.pathLayout.addWidget(lbl_WorkFolderPath)

        else:
            # Work Folder Text Field
            hbox_workfolder = QtWidgets.QHBoxLayout()
            hbox_workfolder.setAlignment(QtCore.Qt.AlignLeft)

            txt_WorkFolder = QtWidgets.QLineEdit('', self)
            txt_WorkFolder.setFocusPolicy(QtCore.Qt.ClickFocus)
            txt_WorkFolder.setMinimumSize(280, 28)
            txt_WorkFolder.setStyleSheet('QLineEdit {color: #9a9a9a; background-color: #373e47; border-top: 1px inset #black; border-bottom: 1px inset #545454}')
            txt_WorkFolder.setText(self.working_folder)
            txt_WorkFolder.textChanged.connect(txt_WorkFolder_textChanged)
            hbox_workfolder.addWidget(txt_WorkFolder)

            btn_changePreset = QtWidgets.QPushButton('Choose', self)
            btn_changePreset.setFocusPolicy(QtCore.Qt.NoFocus)
            btn_changePreset.setMinimumSize(88, 28)
            btn_changePreset.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                    'QPushButton:pressed {font:italic; color: #d9d9d9}')
            btn_changePreset.clicked.connect(self.chooseFolder)
            hbox_workfolder.addWidget(btn_changePreset, alignment = QtCore.Qt.AlignLeft)

            self.pathLineEdit = txt_WorkFolder
            self.pathLayout.addLayout(hbox_workfolder)

        select_btn = QtWidgets.QPushButton('Export', self)
        select_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        select_btn.setMinimumSize(128, 28)
        select_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        select_btn.clicked.connect(self.accept)
        select_btn.setAutoDefault(True)
        select_btn.setDefault(True)

        cancel_btn = QtWidgets.QPushButton('Cancel', self)
        cancel_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        cancel_btn.setMinimumSize(128, 28)
        cancel_btn.setStyleSheet('QPushButton {color: #9a9a9a; background-color: #424142; border-top: 1px inset #555555; border-bottom: 1px inset black}'
                                'QPushButton:pressed {font:italic; color: #d9d9d9}')
        cancel_btn.clicked.connect(self.reject)

        # Adding widgets to the button layout
        self.buttonLayout.addWidget(cancel_btn)
        self.buttonLayout.addWidget(select_btn)

        # Adding layouts to the main layout
        self.layout.addLayout(self.pathLayout)
        self.layout.addWidget(lbl_Spacer)
        self.layout.addLayout(self.buttonLayout)

        self.setStyleSheet('background-color: #313131')
        
        # self.setWindowFlags(QtCore.Qt.Tool)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

    def chooseFolder(self):
        result_folder = str(QtWidgets.QFileDialog.getExistingDirectory(self, 'Open Folder', self.working_folder, QtWidgets.QFileDialog.ShowDirsOnly))
        if result_folder =='':
            return
        self.working_folder = result_folder
        self.fw.prefs['working_folder'] = self.working_folder
        self.fw.save_prefs()
        self.pathLineEdit.setText(self.working_folder)

def get_media_panel_custom_ui_actions():
    def scope_clip(selection):
        try:
            import flame
            for item in selection:
                if isinstance(item, (flame.PyClip)):
                    return True
        except Exception as e:
            print (f'[{settings["app_name"]}]: Exception: {e}')
        return False
    
    def sanitized(text):
        import re

        if text is None:
            return None
        
        text = text.strip()
        exp = re.compile(u'[^\w\.-]', re.UNICODE)

        if isinstance(text, str):
            result = exp.sub('_', text)
        else:
            decoded = text.decode('utf-8')
            result = exp.sub('_', decoded).encode('utf-8')

        return re.sub('_\_+', '_', result)

    def create_timestamp_uid():
        import random
        import uuid
        from datetime import datetime

        def number_to_letter(number):
            # Map each digit to a letter
            mapping = {
                '0': 'A', '1': 'B', '2': 'C', '3': 'D', '4': 'E',
                '5': 'F', '6': 'G', '7': 'H', '8': 'I', '9': 'J'
            }
            return ''.join(mapping.get(char, char) for char in number)

        uid = ((str(uuid.uuid4()).replace('-', '')).upper())
        uid = ''.join(random.sample(number_to_letter(uid), 4))
        timestamp = (datetime.now()).strftime('%Y%b%d_%H%M').upper()
        return f'{timestamp}_{uid}'
    
    def export_clip(clip, export_dir, export_preset = None):
        import flame

        if not os.path.isdir(export_dir):
            try:
                os.makedirs(export_dir)
            except Exception as e:
                issue = 'Unable to create folder to export'
                dialog = flame.messages.show_in_dialog(
                    title =issue,
                    message = f'{issue}:\n{export_dir}\n\nError:\n{e}',
                    type = 'error',
                    buttons = ['Ok'])
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

        exporter = flame.PyExporter()
        exporter.foreground = True

        if not export_preset:
            for visibility in range(4):
                export_preset_folder = flame.PyExporter.get_presets_dir(flame.PyExporter.PresetVisibility.values.get(visibility),
                                flame.PyExporter.PresetType.values.get(0))
                export_preset = os.path.join(export_preset_folder, 'OpenEXR', 'OpenEXR (16-bit fp Uncompressed).xml')
                if os.path.isfile(export_preset):
                    break

        exporter.export(clip, export_preset, export_dir, hooks=ExportHooks())

    def apply_model(selection):
        import flame

        apply_dialog = ApplyModelDialog()

        if apply_dialog.exec():
            first_clip_name = selection[0].name.get_value()
            result_folder = os.path.abspath(
                os.path.join(
                    apply_dialog.working_folder,
                    f'{sanitized(first_clip_name)}_ML_{create_timestamp_uid()}'
                    )
                )
            source_folder = os.path.abspath(
                os.path.join(
                    result_folder,
                    'src'
                    )
                )
            clip_number = 1
            for item in selection:
                if isinstance(item, (flame.PyClip)):
                    clip = item
                    source_clip_folder = os.path.join(source_folder, f'{clip_number:02}')
                    export_clip(clip, source_clip_folder)
                    clip_number += 1

            first_clip_parent = selection[0].parent

            flameSimpleMLInference(
                source_folder=source_folder,
                result_folder=result_folder,
                first_clip_parent = first_clip_parent,
                settings=settings
                )

    def train_model(selection):
        import flame

        if len (selection) < 2:
            dialog = flame.messages.show_in_dialog(
                title ='Dataset creaton error',
                message = 'Please select at least two clips. The channels of first selected clip, or several clips channels combined will act as input channels, and the last selected clip will be the target',
                type = 'error',
                buttons = ['Ok'])
            return

        dataset_dialog = DatasetDialog()

        if dataset_dialog.exec():
            first_clip_name = selection[0].name.get_value()
            dataset_folder = os.path.abspath(
                os.path.join(
                    dataset_dialog.dataset_folder,
                    f'{sanitized(first_clip_name)}_dataset_{create_timestamp_uid()}'
                    )
                )

            source_folder = os.path.abspath(
                os.path.join(
                    dataset_folder,
                    'source'
                    )
                )

            target_folder = os.path.abspath(
                os.path.join(
                    dataset_folder,
                    'target'
                    )
                )
            
            selected_clips = list(selection)
            target_clip = selected_clips.pop()
            export_clip(target_clip, target_folder)

            clip_number = 1
            for source_clip in selected_clips:
                source_clip_folder = os.path.join(source_folder, f'{clip_number:02}')
                export_clip(source_clip, source_clip_folder)
                clip_number += 1

            flame_version = flame.get_version()
            python_executable_path = f'/opt/Autodesk/python/{flame_version}/bin/python'
            script_folder = os.path.abspath(os.path.dirname(__file__))
            app_name = settings.get('app_name')
            version = settings.get('version')
            command = f'{python_executable_path} {script_folder}/train.py {dataset_folder}'
            msg = f'GUI for model training is not yet implemented in {app_name} {version}\n'
            msg += f'Training is currently possible with a command-line script. Please run'
            msg += f'\n\n"{command}"\n\n'
            msg += 'use --help flag for more options'
            dialog = flame.messages.show_in_dialog(
                title ='Train Model GUI is not yet implemented',
                message = msg,
                type = 'info',
                buttons = ['Copy', 'Ok'])
            if dialog == 'Copy':
                try:
                    from PySide6.QtWidgets import QApplication
                except ImportError:
                    from PySide2.QtWidgets import QApplication

                app = QApplication.instance()
                if not app:
                    app = QApplication(sys.argv)
                clipboard = app.clipboard()
                clipboard.setText(command)

    def flame_timewarp(selection):
        import flame
        import xml.etree.ElementTree as ET

        if not selection:
            return

        def sequence_message():
            dialog = flame.messages.show_in_dialog(
                title = f'{settings["app_name"]}',
                message = 'Please select single-track clips with no versions or edits',
                type = 'error',
                buttons = ['Ok'])

        def effect_message():
            dialog = flame.messages.show_in_dialog(
                title = f'{settings["app_name"]}',
                message = 'Please select clips with Timewarp Timeline FX',
                type = 'error',
                buttons = ['Ok'])
            
        def dictify(r, root=True):
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

                        # pprint (tw_setup)
                                
                        verified = True
                
                if not verified:
                    effect_message()
                    return

                verified_clips.append((clip, tw_setup_string))
        
        os.remove(temp_setup_path)
        timewarp_dialog = ApplyModelDialog(selection)
        # timewarp_dialog = TimewarpMLDialog()

        '''
        if timewarp_dialog.exec():
            first_clip_name = selection[0].name.get_value()
            dataset_folder = os.path.abspath(
                os.path.join(
                    timewarp_dialog.working_folder,
                    f'{sanitized(first_clip_name)}_dataset_{create_timestamp_uid()}'
                    )
                )

            source_folder = os.path.abspath(
                os.path.join(
                    dataset_folder,
                    'source'
                    )
                )
        '''


    def about_dialog():
        pass

    def dedup():
        pass

    def fluidmorph():
        pass

    menu = [
        {
            'name': settings['menu_group_name'],
            'actions': [
                {
                    'name': 'Fill / Remove Duplicate Frames',
                    'execute': apply_model,
                    'isVisible': scope_clip,
                    'waitCursor': False,
                },
                {
                    'name': 'Create Fluidmorph Transition',
                    'execute': train_model,
                    'isVisible': scope_clip,
                    'waitCursor': False,
                },
                {
                    'name': "Timewarp from Flame's TW effect",
                    'execute': flame_timewarp,
                    'isVisible': scope_clip,
                    'waitCursor': False,
                },
                {
                    'name': f'Version: {settings["version"]}',
                    'execute': about_dialog,
                    'isVisible': scope_clip,
                    'isEnabled': False,
                },
            ],
        }
    ]

    return menu