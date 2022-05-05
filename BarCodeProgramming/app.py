import sys, os, time
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtCore import QThread, pyqtSignal, QDateTime
import json

from mainUI import Ui_MainWindow
from MainApp import MainApp, MacDB

class processThread(QThread):
    update_state = pyqtSignal(int, str)
    update_progressbar = pyqtSignal()
    controll_gif = pyqtSignal(bool)

    def __init__(self):
        super(processThread, self).__init__()
        self.num = 0
        self.currIndex = 0
        self.maxIndex = 0
        self.macList = []
        self.firstTime = False
        self.wait = False

    def run(self):
        if self.firstTime:
            t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            msg = f"[{t}] 啟動燒錄作業"
            self.update_state.emit(0, msg)
            
              
        self.controll_gif.emit(False)
        """ Run all Process """
        while(1):
            if self.wait: 
                self.controll_gif.emit(False)
                time.sleep(3)
                self.wait = False
                continue
            if self.firstTime==False:
                self.update_state.emit(4, "")
            self.firstTime = False
            self.update_progressbar.emit()
            self.controll_gif.emit(True)
            print(" -> Connect DUT")
            t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            msg = f"[{t}] DUT連線中..."
            self.update_state.emit(0, msg)
            tc = mainApp.wait_until_connect()
            if tc != None:
                msg += "..連線成功！"
                self.update_state.emit(1, msg)
            else:
                msg += "..連線失敗！"
                self.update_state.emit(2, msg)
                continue

            print(" -> Check S/N")
            t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            msg = f"[{t}] 檢查S/N號碼..."
            self.update_state.emit(0, msg)
            snState = mainApp.check_SN(tc)
            if snState[0] == True:
                msg += "..正確！"
                self.update_state.emit(1, msg)
            else:
                msg += "..錯誤！"
                self.update_state.emit(2, msg)
                continue

            print(" -> Check default MAC")
            t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            msg = f"[{t}] 檢查預設MAC編號..."
            self.update_state.emit(0, msg)
            dmacState = mainApp.check_default_mac(tc)
            if dmacState[0] == True:
                msg += "..正確！"
                self.update_state.emit(1, msg)
            else:
                msg += "..錯誤！"
                self.update_state.emit(2, msg)
                continue
            
            print("Get Current MAC")
            newMac = self.macList[self.currIndex]

            t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            msg = f"[{t}] 設定新的MAC編號..."
            self.update_state.emit(0, msg)
            nmacState = mainApp.check_new_mac(newMac)
            if nmacState[0] == True:
                msg += "..成功！"
                self.update_state.emit(1, msg)
            else:
                msg += "..失敗！"
                self.update_state.emit(2, msg)
                continue

            t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            msg = f"[{t}] 燒錄MAC編號..."
            self.update_state.emit(0, msg)
            burnState = mainApp.burn_in(tc, newMac)
            if burnState[0] == True:
                msg += "..成功！"
                self.update_state.emit(1, msg)
                break
            else:
                msg += "..失敗！"
                self.update_state.emit(2, msg)
                continue
        
        self.wait = True
        mainApp.update_db(newMac)
        self.currMac = newMac
        self.currIndex += 1
        if self.currIndex > self.maxIndex:
            print("End Program")
            self.userState = False
            return
        

        t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        msg = f"[{t}] 請掃描條碼"
        self.update_state.emit(0, msg)
        self.update_state.emit(3, newMac)
        
        self.userState = True

class MainWindow(QMainWindow):
    def __init__(self, config):
        super(MainWindow, self).__init__()
        self.config = config
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        #self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # Setup UI with config.json
        self.ui.label.setText(self.config['TargetTitle'])
        self.ui.label_2.setText(self.config['ScanTitle'])
        self.ui.label_5.setText(self.config['ResultTitle'])
        self.ui.label_6.setText(self.config['PrevDataTitle'])
        self.ui.txtResetTitle.setText(self.config['ResetTitle'])
        self.ui.txtResetScanner.setText(self.config['ResetScanner'])
        self.ui.txtResetAll.setText(self.config['ResetAll'])
        
        # QRCode and Logo
        pixmap = QtGui.QPixmap("resource/resetAll.png")
        scaled = pixmap.scaled(300, 130, QtCore.Qt.KeepAspectRatio)
        self.ui.QRCode.setPixmap(scaled)
        pixmap = QtGui.QPixmap("resource/resetScanner.png")
        scaled = pixmap.scaled(300, 100, QtCore.Qt.KeepAspectRatio)
        self.ui.QRCode_2.setPixmap(scaled)
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
        
        # System timer: no move 60s
        self.counter = self.config['SystemTimer']
        self.sys_timer = QtCore.QTimer(self)
        self.sys_timer.timeout.connect(self.onTimer)
        
        # Match timer: 5s after correct
        self.match_timer = QtCore.QTimer(self)
        self.match_timer.timeout.connect(self.resetState)

        # Log
        if os.path.exists("log")==False: os.mkdir("log")
        n_time = time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())
        self.path = "log/"+ n_time
        os.mkdir(self.path)

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
        
        self.bee = QtWidgets.QLabel(self.ui.groupBox)
        self.bee.setGeometry(QtCore.QRect(60, 30, 500, 500))
        self.bee.setStyleSheet("border: none;")
        self.bee.setText("")
        self.bee.setObjectName("bee")
        pixmap = QtGui.QPixmap("resource/bee.png")
        scaled = pixmap.scaled(420, 420, QtCore.Qt.KeepAspectRatio)
        self.bee.setPixmap(scaled)
        self.bee.setVisible(False)
  
        self.loadingMonkey = QtGui.QMovie("resource/monkey.gif")
        self.monkey = QtWidgets.QLabel(self.ui.groupBox)
        self.monkey.setGeometry(QtCore.QRect(60, 30, 500, 500))
        self.monkey.setStyleSheet("border: none;")
        self.monkey.setText("")
        self.monkey.setObjectName("loading")
        self.monkey.setMovie(self.loadingMonkey)
        self.loadingMonkey.start()
        self.monkey.setVisible(False)
        
        # BarCode Checker: barcode is faster than 0.0095s
        self.prevBar, self.enterBar = 0, 0
        self.p, self.n = 0, 0

        # PreBarCode
        self.macList = []
        self.currIndex = 0
        self.currMac = ""

        self.stateList = []

        # QThread
        self.processThread = processThread()
        self.processThread.update_state.connect(self.updateState)
        self.processThread.update_progressbar.connect(self.updateProgressBar)
        self.processThread.controll_gif.connect(self.controllGif)
        
        # First Start
        self.userState = False
        self.firstTime = True


    def setup_control(self):
        self.ui.txtTarget.setText("")
        self.ui.txtScan.setText("")
        self.ui.txtInfo.setText("")
        self.ui.resetBtn.clicked.connect(self.initProcess)
        self.ui.compare_result.setText("State")
        pass

    def handleCompareResult(self, res):
        """ Do after Compare two Barcode """
        if res == True:
            self.passLog = open(self.path+"/PassRecord.txt", "a")
            word = self.config['TargetTitle']+": "+self.target_code+", "+self.config['ScanTitle']+": "+self.scan_code+"\n"
            self.passLog.write(word)
            self.passLog.close()

            # Update Info
            self.userState = False
            self.ui.txtScan.setStyleSheet("border: 1px solid black; background: rgb(211, 211, 211); border-radius: 20px;")

            t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            msg = f"[{t}] 恭喜你抽中iPhone 14 !!!"
            self.updateState(0, msg)
            self.processThread.wait = True
            self.processThread.macList = self.macList
            self.processThread.start()
            self.ui.label_count.setVisible(False)
            self.controllGif(False)
        else:
            self.failLog = open(self.path+"/FailRecord.txt", "a")
            word = self.config['TargetTitle']+":"+self.target_code+", "+self.config['ScanTitle']+": "+self.scan_code+"\n"
            self.failLog.write(word)
            self.failLog.close()
            self.processThread.wait = False

    def keyPressEvent(self, event):
        """ BarCode Scanner is a Keyboard in System """
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
                self.counter = self.config['SystemTimer']
                self.sys_timer.start(1000)
                return
            if(''.join(self.input_list)=="RESET"): 
                self.restartProcess()
                return
            self.scan_code = ''.join(self.input_list)
            # macList[0] -> SN
            if self.scan_code == "str(self.macList[0])" and self.firstTime == True:
                #self.startProcess()
                print("First Time")
                self.processThread.firstTime = True
                self.processThread.macList = self.macList
                self.processThread.start()
                self.firstTime = False
                return
            print(self.userState)
            if self.userState == True:
                self.ui.txtScan.setText(self.scan_code)
                self.input_list = []
                self.get_target = True
                print("Get Scan Input:   ", self.scan_code)
                res = self.compareText(self.currMac, self.scan_code)
                self.handleCompareResult(res)
            elif self.userState == False and self.firstTime == True:
                print("First Time")
                self.initProcess(self.scan_code)

    def compareText(self, target, scan):
        """ Compare BarCode and Return True/False """
        print("Compare Bar Code:")
        if(target == scan):
            print(" -> Correct!")
            self.ui.compare_result.setText("Correct")
            self.ui.label_4.setVisible(False)
            self.loading.setVisible(False)
            self.bee.setVisible(False)
            self.ui.label_3.setVisible(True)
            pixmap = QtGui.QPixmap("resource/correct.png")
            scaled = pixmap.scaled(420, 420, QtCore.Qt.KeepAspectRatio)
            self.ui.label_3.setPixmap(scaled)
            return True
        else:
            print(" -> Wrong!")
            self.ui.compare_result.setText("Wrong")
            self.ui.label_3.setVisible(False)
            self.loading.setVisible(False)
            self.bee.setVisible(False)
            self.ui.label_4.setVisible(True)
            pixmap = QtGui.QPixmap("resource/wrong.png")
            scaled = pixmap.scaled(420, 420, QtCore.Qt.KeepAspectRatio)
            self.ui.label_4.setPixmap(scaled)
            return False

    def slot_frame_changed(self, frame):
        self.ui.txtGif.move(-440 + frame, 0)

    def updateProgressBar(self):
        self.ui.progressBar.setValue(self.processThread.currIndex)

    def controllGif(self, show):
        if show: self.loading.setVisible(True)
        else: self.loading.setVisible(False)

    def resetState(self):
        """ Reset All State """
        print("\nReset State")
        #time.sleep(2)
        self.stateList = []
        self.ui.txtInfo.setText("")
        self.ui.progressBar.setValue(0)
        self.processThread.wait = False
        if self.sys_timer.isActive(): self.sys_timer.stop()
        self.ui.txtTarget.setText("")
        self.ui.txtScan.setText("")
        self.input_list = []
        self.target_code, self.scan_code = "", ""
        self.get_target = False
        self.ui.label_3.setVisible(False)
        self.ui.label_4.setVisible(False)
        self.loading.setVisible(False)
        self.ui.compare_result.setText("State")
        if self.match_timer.isActive(): self.match_timer.stop()
        
    def onTimer(self):
        """ Reset All State after 60s """
        self.counter -= 1
        print(f"Countdown:{self.counter}s", end='\r')
        if self.counter == 0:
            self.sys_timer.stop()
            self.resetState()
            print('Time Out')

    def closeEvent(self, event):
        print("Close App")

    def updateState(self, state, msg):
        print(msg)
        if state == 0:
            self.stateList.append(msg)
        elif state == 1:
            self.stateList.pop()
            self.stateList.append(msg)
        elif state == 2:
            # Failed
            self.stateList.append(msg)
            if len(self.stateList)>5: self.stateList.pop(0)
            txt = '\n'.join(self.stateList)
            #print(txt)
            self.ui.txtInfo.setText(txt)
            self.ui.label_count.setVisible(False)
            self.monkey.setVisible(True)
            return
        elif state == 3:
            # Get Mac
            self.currMac = msg
            self.ui.txtTarget.setText(msg)
            self.userState = True
            self.ui.txtScan.setStyleSheet("border: 1px solid black; background: white; border-radius: 20px;")
            return
        elif state == 4:
            self.resetState()
            return
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
        #print(self.stateList)
        if len(self.stateList)>5: self.stateList.pop(0)
        txt = '\n'.join(self.stateList)
        #print(txt)
        self.ui.txtInfo.setText(txt)
        self.ui.label_count.setText(f"{self.processThread.currIndex+1}/{len(self.macList)}")

    def restartProcess(self):
        """ Restart from initProcess """
        self.processThread.quit()
        self.resetState()
        self.initProcess()

    def initProcess(self, scan_mac):
        """ Load Mac """
        print("initProcess")
        
        self.ui.txtInfo.setText("INIT PROCESS")
        t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
        msg = f"[{t}] 讀取MAC檔案..."
        self.updateState(0, msg)
        self.macList = []
        self.processThread.currIndex = 0
        self.processThread.macList = []
        self.firstTime = True
        (macState, self.macList) = mainApp.load_mac_list(scan_mac)
        self.ui.progressBar.setMaximum(len(self.macList))
        print(macState)
        if macState == True:
            msg += "..成功！"
            self.updateState(1, msg)
            t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            msg = f"[{t}] 啟動"
            self.updateState(0, msg)
            self.processThread.maxIndex = len(self.macList)
            self.processThread.firstTime = True
            self.processThread.macList = self.macList
            self.processThread.start()
            self.firstTime = False
            
            return True
        else:
            print("LOAD FAIL")
            t = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            msg = f"[{t}] 讀取MAC檔案失敗，請檢查檔案。"
            self.updateState(2, msg)
            self.loading.setVisible(False)
            self.monkey.setVisible(True)
            timer = QtCore.QTimer(self)
            #timer.timeout.connect(self.close)
            timer.start(3000)
            return False


        
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    f = open('config.json', 'r', encoding="utf-8")
    config = json.loads(f.read())
    f.close()
    macDB = MacDB()
    mainApp = MainApp(config, macDB)

    window = MainWindow(config['UI'])
    window.show()
    #window.showFullScreen()
    sys.exit(app.exec_())
