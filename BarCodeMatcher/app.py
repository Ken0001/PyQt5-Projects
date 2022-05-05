import sys
import os
import time
import json

from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5 import QtCore, QtGui

from mainUI import Ui_MainWindow

class MainWindow(QMainWindow):
    def __init__(self, config):
        super(MainWindow, self).__init__()
        self.config = config
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)

        # Setup UI
        self.ui.label.setText(self.config['TargetTitle'])
        self.ui.label_2.setText(self.config['ScanTitle'])
        self.ui.label_5.setText(self.config['ResultTitle'])
        
        pixmap = QtGui.QPixmap("reset_code.png")
        scaled = pixmap.scaled(100, 100, QtCore.Qt.KeepAspectRatio)
        self.ui.QRCode.setPixmap(scaled)

        pixmap = QtGui.QPixmap("logo.png")
        #scaled = pixmap.scaled(160, 160, QtCore.Qt.KeepAspectRatio)
        self.ui.logo.setPixmap(pixmap)
        
        # Debug Tool
        self.ui.compare_result.setVisible(False)
        self.ui.resetBtn.setVisible(True)

        self.setup_control()
        
        self.input_list = []
        self.target_code, self.scan_code = "", ""
        self.get_target = False
        self.prev_time = 0
        self.counter = self.config['SystemTimer']
        self.sys_timer = QtCore.QTimer(self)
        self.sys_timer.timeout.connect(self.onTimer)

        self.match_timer = QtCore.QTimer(self)
        self.match_timer.timeout.connect(self.resetState)

        # Log
        if os.path.exists("log")==False: os.mkdir("log")
        n_time = time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())
        self.path = "log/"+ n_time
        os.mkdir(self.path)
        

        

    def setup_control(self):
        self.ui.txtTarget.setText("")
        self.ui.txtScan.setText("")
        self.ui.txtInfo.setText("")
        self.ui.resetBtn.clicked.connect(self.resetState)
        self.ui.compare_result.setText("State")
        pass

    def handleCompareResult(self, res):
        if res == True:
            self.passLog = open(self.path+"/PassRecord.txt", "a")
            word = self.config['TargetTitle']+": "+\
                    self.target_code+", "+\
                    self.config['ScanTitle']+": "+\
                    self.scan_code+"\n"
            self.passLog.write(word)
            self.passLog.close()
            self.match_timer.start(self.config['MatchTimer']*1000)
            info = f"{self.config['TargetTitle']}: {self.target_code}\n\
                    {self.config['ScanTitle']}: {self.scan_code}"
            self.ui.txtInfo.setText(info)
        else:
            self.failLog = open(self.path+"/FailRecord.txt", "a")
            word = self.config['TargetTitle']+":"+self.target_code+", "+self.config['ScanTitle']+": "+self.scan_code+"\n"
            self.failLog.write(word)
            self.failLog.close()
            self.counter = self.config['SystemTimer']
            self.sys_timer.start(1000)        

    def keyPressEvent(self, event):
        if self.sys_timer.isActive(): self.sys_timer.stop()
        if self.match_timer.isActive() == False:
            if(event.key() != QtCore.Qt.Key_Return):
                self.input_list.append(str(event.text()))
            else:
                if(''.join(self.input_list)=="RESET"): 
                    self.resetState()
                    return None
                if(self.get_target == False):
                    self.target_code = ''.join(self.input_list)
                    self.ui.txtTarget.setText(self.target_code)
                    self.get_target = True
                    self.input_list = []
                    print("Get Target Input: ", self.target_code)
                    self.counter = self.config['SystemTimer']
                    self.sys_timer.start(1000)
                    self.prev_time = time.time()
                else:
                    if (time.time()-self.prev_time > 1):
                        self.scan_code = ''.join(self.input_list)
                        self.ui.txtScan.setText(self.scan_code)
                        self.input_list = []
                        self.get_target = True
                        print("Get Scan Input:   ", self.scan_code)
                        res = self.compareText(self.target_code, self.scan_code)
                        self.handleCompareResult(res)


            """
            if(self.get_target == False):        
                if(event.key() != QtCore.Qt.Key_Return): 
                    self.tL.append(str(event.text()))
                else:
                    self.target_code = ''.join(self.tL)
                    self.ui.txtTarget.setText(self.target_code)
                    self.get_target = True
                    print("Get Target Input: ", self.target_code)
                    self.counter = self.config['SystemTimer']
                    self.sys_timer.start(1000)
            else:
                if(event.key() != QtCore.Qt.Key_Return): 
                    self.sL.append(str(event.text()))
                else:
                    self.scan_code = ''.join(self.sL)
                    self.ui.txtScan.setText(self.scan_code)
                    self.sL = []
                    self.get_target = True
                    print("Get Scan Input:   ", self.scan_code)
                    res = self.compareText(self.target_code, self.scan_code)
                    if res == True:
                        self.passLog = open(self.path+"/PassRecord.txt", "a")
                        word = self.config['TargetTitle']+":"+self.target_code+", "+self.config['ScanTitle']+": "+self.scan_code+"\n"
                        self.passLog.write(word)
                        self.passLog.close()
                        self.match_timer.start(self.config['MatchTimer']*1000)
                    else:
                        self.failLog = open(self.path+"/FailRecord.txt", "a")
                        word = self.config['TargetTitle']+":"+self.target_code+", "+self.config['ScanTitle']+": "+self.scan_code+"\n"
                        self.failLog.write(word)
                        self.failLog.close()
                        self.counter = self.config['SystemTimer']
                        self.sys_timer.start(1000)
                """

    def compareText(self, target, scan):
        print("Compare Bar Code:")
        if(target == scan):
            print(" -> Correct!")
            self.ui.compare_result.setText("Correct")
            self.ui.label_4.setVisible(False)
            self.ui.label_3.setVisible(True)
            pixmap = QtGui.QPixmap("correct_new.png")
            scaled = pixmap.scaled(420, 420, QtCore.Qt.KeepAspectRatio)
            self.ui.label_3.setPixmap(scaled)
            return True
        else:
            print(" -> Wrong!")
            self.ui.compare_result.setText("Wrong")
            self.ui.label_3.setVisible(False)
            self.ui.label_4.setVisible(True)
            pixmap = QtGui.QPixmap("wrong_new.png")
            scaled = pixmap.scaled(420, 420, QtCore.Qt.KeepAspectRatio)
            self.ui.label_4.setPixmap(scaled)
            return False

    def resetState(self):
        print("Reset State")
        if self.sys_timer.isActive(): self.sys_timer.stop()
        self.ui.txtTarget.setText("")
        self.ui.txtScan.setText("")
        #self.tL, self.sL = [], []
        self.input_list = []
        self.target_code, self.scan_code = "", ""
        self.get_target = False
        self.ui.label_3.setVisible(False)
        self.ui.label_4.setVisible(False)
        self.ui.compare_result.setText("State")
        if self.match_timer.isActive(): self.match_timer.stop()
        
    def onTimer(self):
        self.counter -= 1
        print(f"Countdown:{self.counter}s", end='\r')
        if self.counter == 0:
            self.sys_timer.stop()
            self.resetState()
            print('Time Out')

    def closeEvent(self, event):
        print("Close App")
        
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    f = open('config.json', 'r', encoding="utf-8")
    config = json.loads(f.read())
    window = MainWindow(config)
    window.showFullScreen()
    window.show()
    sys.exit(app.exec_())