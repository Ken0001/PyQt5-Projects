import sys
import os
import json
import time

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal

from mainUI import Ui_MainWindow
from MainApp import MainApp, MACDB

INFO_MAX_LEN = 5

class processThread(QThread):
    update_state = pyqtSignal(str, str, str)
    update_progressbar = pyqtSignal()
    controll_gif = pyqtSignal(bool)
    update_ui = pyqtSignal(str)

    def __init__(self):
        super(processThread, self).__init__()
        # Prepare Variable
        self.currIndex = 0
        self.maxIndex = 0
        self.macList = []
        self.currMac = ""
        self.firstTime = False
        self.userState = False
        self.wait = False
        
    
    def create_msg(self, input_msg, stage="Normal", state="Normal"):
        print("=>", input_msg)
        t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        msg = f"[{t}] {input_msg}"
        self.update_state.emit(msg, stage, state)
        return msg

    def run(self):
        if self.firstTime:
            self.create_msg("---啟動燒錄作業---")
            self.firstTime = False
        self.controll_gif.emit(False)
        new_MAC = self.macList[self.currIndex]
        # Main Loop
        while(1):
            if self.wait: 
                self.controll_gif.emit(False)
                time.sleep(3)
                self.wait = False
                self.update_ui.emit("RESET")
                continue
            self.update_progressbar.emit()
            self.controll_gif.emit(True)
            
            self.create_msg("連線至DUT...")
            dut = mainApp.wait_until_connect()
            if dut:
                self.create_msg("DUT連線成功！")
            else:
                self.create_msg("DUT連線失敗！")
                continue

            self.create_msg("檢查預設MAC編號...")
            ret, _ = mainApp.check_pcba_default_MAC_in_flash(dut)
            if not ret:
                self.create_msg("預設MAC編號錯誤！")
                continue
            else:
                self.create_msg("預設MAC編號正確！")

            self.create_msg("檢查S/N編號...")
            ret, _ = mainApp.check_pcba_FW_SN(dut)
            if not ret:
                self.create_msg("S/N編號錯誤！")
                continue
            else:
                self.create_msg("S/N編號正確！")

            self.create_msg("設定新的MAC編號...")
            ret, _ = mainApp.is_new_mac_valid(new_MAC)
            if not ret:
                self.create_msg("設定失敗！")
                continue
            else:
                self.create_msg("設定成功！")

            self.create_msg("燒錄MAC編號...")
            ret, _ = mainApp.burn_in_MAC(dut, new_MAC,
                                         mainApp.config['Input']['exe_burn_in_MAC'])
            if not ret:
                self.create_msg("燒錄失敗！")
                continue
            else:
                self.create_msg("燒錄成功！")
                break

        mainApp.update_db(new_MAC)
        self.currMac = new_MAC
        self.currIndex += 1
        if self.currIndex > self.maxIndex:
            print("End Program")
            self.userState = False
            return

        self.create_msg("請掃描條碼")
        self.userState = True
        self.controll_gif.emit(False)
        self.update_ui.emit("BEE")

class MainWindow(QMainWindow):

    def __init__(self, config):
        super(MainWindow, self).__init__()
        self.config = config
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.initUI()
        # self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        pixmap = QtGui.QPixmap("resource/logo.png")
        scaled = pixmap.scaled(620, 137, QtCore.Qt.KeepAspectRatio)
        self.ui.logo.setPixmap(scaled)

        # BarCode
        self.input_list = []
        self.scan_code = ""
        self.prevBar, self.enterBar = 0, 0
        self.p, self.n = 0, 0

        # Log File
        if os.path.exists("log")==False: os.mkdir("log")
        n_time = time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())
        self.path = "log/"+ n_time
        os.mkdir(self.path)

        # QThread
        self.processThread = processThread()
        self.processThread.update_state.connect(self.update_info)
        self.processThread.update_progressbar.connect(self.update_progressbar)
        self.processThread.controll_gif.connect(self.controll_gif)
        self.processThread.update_ui.connect(self.update_ui)

        # Info
        self.state_list = []

        # First Start
        self.processThread.userState = False
        self.processThread.firstTime = True

        # Start Program
        self.ui.progressBar.setValue(0)
        self.create_msg("請掃描第一筆條碼")

    def initUI(self):

        # Basic UI
        self.ui.label.setText(self.config['TargetTitle'])
        self.ui.label_2.setText(self.config['ScanTitle'])
        self.ui.label_5.setText(self.config['ResultTitle'])
        self.ui.label_6.setText(self.config['PrevDataTitle'])
        self.ui.txtResetTitle.setText(self.config['ResetTitle'])
        self.ui.txtResetScanner.setText(self.config['ResetScanner'])
        self.ui.txtResetAll.setText(self.config['ResetAll'])
        self.ui.txtTarget.setText("")
        self.ui.txtScan.setText("")
        self.ui.txtInfo.setText("")
        
        # Logo
        pixmap = QtGui.QPixmap("resource/logo.png")
        self.ui.logo.setPixmap(pixmap)

        # Author
        self.ui.txtGif.move(0, 0)
        self.timeline = QtCore.QTimeLine(6123, self)
        self.timeline.setFrameRange(0, 720)
        self.timeline.frameChanged.connect(self.slot_frame_changed)
        self.timeline.setLoopCount(0)
        self.timeline.start()
        self.timeline.setDirection(QtCore.QTimeLine.Backward)

        # Loading Fig
        self.loadingMovie = QtGui.QMovie("resource/loading.gif")
        self.loading = QtWidgets.QLabel(self.ui.groupBox)
        self.loading.setGeometry(QtCore.QRect(60, 35, 500, 500))
        self.loading.setStyleSheet("border: none;")
        self.loading.setText("")
        self.loading.setObjectName("loading")
        self.loading.setMovie(self.loadingMovie)
        self.loadingMovie.start()
        self.loading.setVisible(False)
        
        self.bee = QtWidgets.QLabel(self.ui.groupBox)
        self.bee.setGeometry(QtCore.QRect(60, 35, 500, 500))
        self.bee.setStyleSheet("border: none;")
        self.bee.setText("")
        self.bee.setObjectName("bee")
        pixmap = QtGui.QPixmap("resource/bee.png")
        scaled = pixmap.scaled(500, 500, QtCore.Qt.KeepAspectRatio)
        self.bee.setPixmap(scaled)
        self.bee.setVisible(False)

        if self.config['monkey'] == True:
            self.loadingMonkey = QtGui.QMovie("resource/monkey.gif")
            self.monkey = QtWidgets.QLabel(self.ui.groupBox)
            self.monkey.setGeometry(QtCore.QRect(60, 35, 500, 500))
            self.monkey.setStyleSheet("border: none;")
            self.monkey.setText("")
            self.monkey.setObjectName("loading")
            self.monkey.setMovie(self.loadingMonkey)
            self.loadingMonkey.start()
            self.monkey.setVisible(False)
        else:
            self.monkey = QtWidgets.QLabel(self.ui.groupBox)
            self.monkey.setGeometry(QtCore.QRect(60, 35, 500, 500))
            self.monkey.setStyleSheet("border: none;")
            self.monkey.setText("")
            self.monkey.setObjectName("loading")
            pixmap = QtGui.QPixmap("resource/!.png")
            scaled = pixmap.scaled(500, 500, QtCore.Qt.KeepAspectRatio)
            self.monkey.setPixmap(scaled)
            self.monkey.setVisible(False)

    def update_info(self, msg):
        if "第一筆" in msg or "掃描" in msg: 
            print("Bee")
            self.loading.setVisible(False)
            self.bee.setVisible(True)
            self.ui.label_count.setVisible(False)
        else:
            print("Loading")
            self.bee.setVisible(False)
            self.loading.setVisible(True)
            self.ui.label_count.setVisible(True)
        self.state_list.append(msg)
        if len(self.state_list)>INFO_MAX_LEN: 
            self.state_list.pop(0)
        txt = '\n'.join(self.state_list)
        self.ui.txtInfo.setText(txt)
        count = f"{self.processThread.currIndex+1}/{len(self.processThread.macList)}"
        self.ui.label_count.setText(count)
    
    def create_msg(self, input_msg):
        print("=>", input_msg)
        t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        msg = f"[{t}] {input_msg}"
        self.update_info(msg)

    def keyPressEvent(self, event):
        """ BarCode Scanner is a Keyboard in System """
        # Avoid Keyboard input
        if self.p == 0:
            self.p = time.time()
        else:
            self.n = time.time()
            t = self.n - self.p
            if t > 0.09: self.input_list = []
            self.p = self.n
        
        if(event.key() != QtCore.Qt.Key_Return):
            self.input_list.append(str(event.text()))
            self.prevBar = time.time()
        else:
            barCheck = time.time() - self.prevBar
            print("Enter Time: ", barCheck)
            if(barCheck > 0.0195): 
                self.input_list = []
                return
            if(''.join(self.input_list)=="RESET"): 
                self.restart_process()
                return
            self.scan_code = ''.join(self.input_list)
            
            if self.processThread.userState == True:
                self.ui.txtScan.setText(self.scan_code)
                self.input_list = []
                print("Get Scan Input:   ", self.scan_code)
                res = self.compareText(self.processThread.currMac, self.scan_code)
                self.handleCompareResult(res)
            elif self.processThread.userState == False and \
                 self.processThread.firstTime == True:
                print("First Time")
                self.initProcess(self.scan_code)
    
    def restart_process(self):
        self.processThread.quit()
        self.processThread.firstTime = True
        self.resetState()
    
    def initProcess(self, scan_mac):
        """ Load Mac """
        print("initProcess")
        self.create_msg("讀取MAC檔案...")
        macList = []
        self.processThread.currIndex = 0
        self.processThread.macList = []
        self.firstTime = True

        (macState, macList) = mainApp.load_MAC_list(scan_mac)
        self.ui.progressBar.setMaximum(len(macList))
        print(macState)
        if macState == True:
            self.create_msg("讀取MAC成功！")
            # Start Thread
            self.processThread.maxIndex = len(macList)
            self.processThread.firstTime = True
            self.processThread.macList = macList
            self.processThread.start()
            self.firstTime = False
            self.monkey.setVisible(False)
            return True
        else:
            print("LOAD FAIL")
            self.create_msg("讀取MAC檔案失敗，請檢查檔案！")
            self.loading.setVisible(False)
            self.monkey.setVisible(True)
            return False

    def compareText(self, target, scan):
        """ Compare BarCode and Return True/False """
        print("Compare Bar Code:")
        if(target == scan):
            print(" -> Correct!")
            self.ui.label_4.setVisible(False)
            self.loading.setVisible(False)
            self.bee.setVisible(False)
            self.ui.label_3.setVisible(True)
            pixmap = QtGui.QPixmap("resource/correct.png")
            scaled = pixmap.scaled(500, 500, QtCore.Qt.KeepAspectRatio)
            self.ui.label_3.setPixmap(scaled)
            return True
        else:
            print(" -> Wrong!")
            self.ui.label_3.setVisible(False)
            self.loading.setVisible(False)
            self.bee.setVisible(False)
            self.ui.label_4.setVisible(True)
            pixmap = QtGui.QPixmap("resource/wrong.png")
            scaled = pixmap.scaled(500, 500, QtCore.Qt.KeepAspectRatio)
            self.ui.label_4.setPixmap(scaled)
            return False

    def handleCompareResult(self, res):
        """ Do after Compare two Barcode """
        if res == True:
            self.passLog = open(self.path+"/PassRecord.txt", "a")
            word = self.config['TargetTitle']+": "+self.processThread.currMac+", "+self.config['ScanTitle']+": "+self.scan_code+"\n"
            self.passLog.write(word)
            self.passLog.close()

            # Update Info
            self.processThread.userState = False
            self.update_ui("DONE")
            self.create_msg(self.config['Success'])
            self.processThread.wait = True
            self.processThread.start()
            self.ui.label_count.setVisible(False)
            self.controll_gif(False)
        else:
            self.failLog = open(self.path+"/FailRecord.txt", "a")
            word = self.config['TargetTitle']+":"+self.processThread.currMac+", "+self.config['ScanTitle']+": "+self.scan_code+"\n"
            self.failLog.write(word)
            self.failLog.close()
            self.processThread.wait = False

    def resetState(self):
        """ Reset All State """
        print("\nReset State")
        self.state_list = []
        self.ui.txtInfo.setText("")
        self.ui.progressBar.setValue(0)
        self.processThread.wait = False
        self.ui.txtTarget.setText("")
        self.ui.txtScan.setText("")
        self.ui.txtScan.setStyleSheet("border: 1px solid black; \
                                        background: rgb(211, 211, 211);\
                                        border-radius: 20px;")
        self.input_list = []
        self.scan_code = ""
        self.ui.label_3.setVisible(False)
        self.ui.label_4.setVisible(False)
        self.loading.setVisible(False)
        

    def update_ui(self, stage):
        print(stage)
        if stage == "BEE":
            self.ui.txtTarget.setText(self.processThread.currMac)
            self.ui.txtScan.setStyleSheet("border: 1px solid black; \
                                        background: white;\
                                        border-radius: 20px;")
        elif stage == "":
            self.ui.txtTarget.setText("")
            self.ui.txtScan.setStyleSheet("border: 1px solid black; \
                                        background: rgb(211, 211, 211);\
                                        border-radius: 20px;")
        elif stage == "RESET":
            self.resetState()

    def controll_gif(self, show):
        if show: self.loading.setVisible(True)
        else: self.loading.setVisible(False)

    def slot_frame_changed(self, frame):
        self.ui.txtGif.move(-440 + frame, 0)

    def update_progressbar(self):
        self.ui.progressBar.setValue(self.processThread.currIndex)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    with open('config.json', 'r', encoding='utf-8') as f:
        config = json.loads(f.read())
    
    macDB = MACDB()
    mainApp = MainApp(config, macDB)
    
    window = MainWindow(config=config['UI'])
    window.show()
    window.showFullScreen()
    sys.exit(app.exec_())