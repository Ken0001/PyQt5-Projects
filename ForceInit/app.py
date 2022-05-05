import sys
import os
import time
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QDateTime
import json

from forceInitUI import Ui_MainWindow
from MainApp import MainApp, MACDB

STAGE = {"Normal":"Normal",
         "MAC":"MAC",
         "JSON":"JSON",
         "OTA":"OTA"}

INFO_MAX_LEN = 19

class processThread(QThread):
    update_state = pyqtSignal(str, str, str)
    update_progressbar = pyqtSignal()
    controll_gif = pyqtSignal(bool)
    reset_state = pyqtSignal(bool)

    def __init__(self):
        super(processThread, self).__init__()
        self.firstTime = False
        self.wait = False
        self.default_mac = mainApp.default_MAC
    
    def create_msg(self, input_msg, stage="Normal", state="Normal"):
        print("=>", input_msg)
        t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        msg = f"[{t}] {input_msg}"
        self.update_state.emit(msg, stage, state)
        return msg

    def run(self):
                      
        while(1):            
            self.create_msg("連線至DUT...")
            dut = mainApp.wait_until_connect()
            if dut:
                self.create_msg("DUT連線成功！")
            else:
                self.create_msg("DUT連線失敗！")
                continue
            
            # Burn MAC
            self.create_msg("檢查是否為預設MAC編號...")
            default_mac_state, _ = mainApp.check_pcba_default_MAC_in_flash(dut)
            if not default_mac_state:
                self.create_msg("MAC編號不一致！")
                # Burn!
                self.create_msg("燒錄預設MAC編號...")
                burn_state, _ = mainApp.burn_in_MAC(dut, self.default_mac, mainApp.config['Input']['exe_burn_in_MAC'])
                if burn_state:
                    self.create_msg("燒錄完成！", "MAC", "Success")
                else:
                    self.create_msg("燒錄完成！", "MAC", "Failed")
            else:
                self.create_msg("MAC編號一致！", "MAC", "PASS")
            
            # Write S/N to JSON
            self.create_msg("檢查JSON檔...")
            check_SN_json, _ = mainApp.check_pcba_SN_json(dut)
            if not check_SN_json:
                SN_json, _ = mainApp.write_new_SN_in_json(dut, mainApp.target_SN)
                if SN_json:
                    self.create_msg("已將S/N號碼寫入JSON！", "JSON", "Success")
                else:
                    self.create_msg("S/N號碼寫入失敗！", "JSON", "Failed")
            else:
                self.create_msg("檔案內容正確", "JSON", "PASS")
            
            # OTA
            self.create_msg("檢查S/N號碼...")
            check_SN, _ = mainApp.check_pcba_FW_SN(dut)
            self.create_msg("檢查韌體版本...")
            check_commit_id, _ = mainApp.check_pcba_FW_commit_id(dut)

            if not check_SN or not check_commit_id:
                if not check_SN:
                    self.create_msg("S/N號碼不符")
                else:
                    self.create_msg("韌體版本不符")
                self.create_msg("上傳新的韌體")
                ret_send_file, _ = mainApp.send_file_to_pcba(dut, 
                                            mainApp.config['Input']['ota_bin'], 
                                            "/root/otaConfigFile/STM32G030K8.bin")
                if not ret_send_file:
                    self.create_msg("上傳失敗", "OTA", "Failed")
                    continue
                self.create_msg("OTA更新中...")
                ret_OTA, _ = mainApp.OTA(dut, mainApp.config['Input']['exe_OTA'])
                if not ret_OTA: 
                    self.create_msg("更新失敗", "OTA", "Failed")
                    continue
                self.create_msg("更新成功！", "OTA", "Success")
            else:
                self.create_msg("版本相符", "OTA", "PASS")
            time.sleep(3)
            self.reset_state.emit(True)
            time.sleep(3)
            

class MainWindow(QMainWindow):
    def __init__(self, config):
        super(MainWindow, self).__init__()
        self.config = config
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        #self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # QRCode and Logo
        pixmap = QtGui.QPixmap("resource/logo.png")
        self.ui.logo.setPixmap(pixmap)
        
        # Debug Tool
        self.ui.compare_result.setVisible(False)
        self.ui.resetBtn.setVisible(True)

        # Setting Custom UI
        self.setup_control()
        
        # BarCode
        self.input_list = []
        self.target_code, self.scan_code = "", ""
        self.get_target = False
        self.prev_time = 0
        self.reset_checker = []

        # Author
        self.ui.txtGif.move(0, 0)
        self.timeline = QtCore.QTimeLine(6123, self)
        self.timeline.setFrameRange(0, 720)
        self.timeline.frameChanged.connect(self.slot_frame_changed)
        self.timeline.setLoopCount(0)
        self.timeline.start()
        self.timeline.setDirection(QtCore.QTimeLine.Backward)

        # Additional Figure
        self.loadingMovie = QtGui.QMovie("resource/loading.gif")
        self.loading = QtWidgets.QLabel(self.ui.groupBox)
        self.loading.setGeometry(QtCore.QRect(60, 30, 500, 500))
        self.loading.setStyleSheet("border: none;")
        self.loading.setText("")
        self.loading.setObjectName("loading")
        self.loading.setMovie(self.loadingMovie)
        self.loadingMovie.start()
        self.loading.setVisible(False)

        # QThread
        self.processThread = processThread()
        self.processThread.update_state.connect(self.update_info)
        self.processThread.reset_state.connect(self.resetState)
        
        # Start
        self.processThread.start()

        # Info
        self.state_list = []

        self.stage_func = {"MAC": self.ui.figMAC,
                           "JSON": self.ui.figJSON,
                           "OTA": self.ui.figOTA}
        self.stage_css_fig = {"MAC": QtCore.QRect(300, 40, 300, 200),
                               "JSON": QtCore.QRect(300, 250, 300, 200),
                               "OTA": QtCore.QRect(300, 460, 300, 200)}
        self.stage_css_pass = {"MAC": QtCore.QRect(300, 90, 200, 100),
                               "JSON": QtCore.QRect(300, 300, 200, 100),
                               "OTA": QtCore.QRect(300, 510, 200, 100)}


    def setup_control(self):
        self.ui.label.setText(self.config['InfoTitle'])        
        self.ui.label_5.setText(self.config['ResultTitle'])
        self.ui.txtInfo.setText("")
        self.ui.compare_result.setText("State")
        self.ui.txtMAC.setText(self.config['MACTitle'])
        self.ui.txtJSON.setText(self.config['JSONTitle'])
        self.ui.txtOTA.setText(self.config['OTATitle'])

    def keyPressEvent(self, event):
        """ BarCode Scanner is a Keyboard in System """
        print(str(event.text()))
        
    def slot_frame_changed(self, frame):
        self.ui.txtGif.move(-440 + frame, 0)

    def resetState(self):
        """ Reset All State """
        print("\nReset State")
        self.processThread.wait = False
        self.input_list = []
        self.target_code, self.scan_code = "", ""
        self.get_target = False
        self.ui.figMAC.setVisible(False)
        self.ui.figJSON.setVisible(False)
        self.ui.figOTA.setVisible(False)    
        self.ui.compare_result.setText("State")

    def show_fig(self, stage, scaled):
        if stage == "MAC":
            self.ui.figMAC.setPixmap(scaled)
            self.ui.figMAC.setVisible(True)
        elif stage == "JSON":
            self.ui.figJSON.setPixmap(scaled)
            self.ui.figJSON.setVisible(True)
        elif stage == "OTA":
            self.ui.figOTA.setPixmap(scaled)
            self.ui.figOTA.setVisible(True)

    def update_stage_state(self):
        for i in STAGE:
            if i!="Normal" and STAGE[i] == "Success":
                self.stage_func[i].setGeometry(self.stage_css_fig[i])
                self.stage_func[i].setStyleSheet("border: none;")
                self.stage_func[i].setText("")
                pixmap = QtGui.QPixmap("resource/correct_new.png")
                scaled = pixmap.scaled(200, 200, QtCore.Qt.KeepAspectRatio)
                self.stage_func[i].setPixmap(scaled)
                self.stage_func[i].setVisible(True)
                print("SUCCESS")
                STAGE[i] = ""
            elif i!="Normal" and STAGE[i] == "Failed":
                self.stage_func[i].setGeometry(self.stage_css_fig[i])
                self.stage_func[i].setStyleSheet("border: none;")
                self.stage_func[i].setText("")
                self.stage_func[i].setVisible(True)
                pixmap = QtGui.QPixmap("resource/wrong_new.png")
                scaled = pixmap.scaled(200, 200, QtCore.Qt.KeepAspectRatio)
                self.stage_func[i].setPixmap(scaled)
                self.stage_func[i].setVisible(True)
                STAGE[i] = ""
            elif STAGE[i] == "PASS":
                print("pass, obj:", i)
                # pixmap = QtGui.QPixmap("resource/pass.png")
                # scaled = pixmap.scaled(300, 200, QtCore.Qt.KeepAspectRatio)
                
                # self.stage_func[i].setPixmap(scaled)
                # self.stage_func[i].setVisible(True)
                # Show PASS with CSS
                font = QtGui.QFont()
                font.setFamily("微軟正黑體")
                font.setPointSize(42)
                self.stage_func[i].setFont(font)
                self.stage_func[i].setGeometry(self.stage_css_pass[i])
                pass_css = "border: 10px solid #557C40; \
                            border-radius: 20px; \
                            color: #51925A; \
                            font-weight: bold"
                self.stage_func[i].setStyleSheet(pass_css)
                self.stage_func[i].setText("PASS")
                self.stage_func[i].setAlignment(QtCore.Qt.AlignCenter)
                self.stage_func[i].setVisible(True)
                STAGE[i] = ""

    def update_info(self, msg, stage="Normal", state="Normal"):
        self.state_list.append(msg)
        STAGE[stage] = state
        self.update_stage_state()
        if len(self.state_list)>INFO_MAX_LEN: 
            self.state_list.pop(0)
        txt = '\n'.join(self.state_list)
        self.ui.txtInfo.setText(txt)
          
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    f = open('config.json', 'r', encoding="utf-8")
    config = json.loads(f.read())
    f.close()
    macDB = MACDB()
    mainApp = MainApp(config, macDB)

    window = MainWindow(config['UI'])
    window.show()
    #window.showFullScreen()
    sys.exit(app.exec_())
