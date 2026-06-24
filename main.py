import sys
import os
import can
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtCore import QThread, pyqtSignal
from ui_main import Ui_Form
import bms_resources_rc

os.environ["QT_FONT_DPI"] = "80"
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
os.environ["QT_SCALE_FACTOR"] = "1"

class CANReceiverThread(QThread):
    update_pack = pyqtSignal(float, float) 
    update_cells_1_2 = pyqtSignal(float, float)
    update_cells_3_4_temp = pyqtSignal(float, float, float, int)

    def run(self):
        bus = can.interface.Bus(channel='can0', bustype='socketcan')
        while True:
            msg = bus.recv(1.0) 
            if msg is not None:
                if msg.arbitration_id == 0x103:
                    t_vol = int.from_bytes(msg.data[0:2], byteorder='big', signed=False) / 100.0
                    t_cur = int.from_bytes(msg.data[2:4], byteorder='big', signed=True) / 100.0
                    c1 = int.from_bytes(msg.data[4:6], byteorder='big', signed=False) / 100.0
                    c2 = int.from_bytes(msg.data[6:8], byteorder='big', signed=False) / 100.0
                    self.update_pack.emit(t_vol, t_cur)
                    self.update_cells_1_2.emit(c1, c2)
                elif msg.arbitration_id == 0x104:
                    c3 = int.from_bytes(msg.data[0:2], byteorder='big', signed=False) / 100.0
                    c4 = int.from_bytes(msg.data[2:4], byteorder='big', signed=False) / 100.0
                    temp = int.from_bytes(msg.data[4:6], byteorder='big', signed=True) / 100.0
                    fault = msg.data[6]
                    self.update_cells_3_4_temp.emit(c3, c4, temp, fault)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.can_thread = CANReceiverThread()
        self.can_thread.update_cells_1_2.connect(self.display_cells_1_2)
        self.can_thread.update_cells_3_4_temp.connect(self.display_cells_3_4_temp)
        self.can_thread.update_pack.connect(self.display_pack_info)
        self.can_thread.start() 

    def display_cells_1_2(self, c1, c2):
        self.ui.txt_volt_cell1.setText(f"<span style='font-weight: bold; color: white;'>{c1:.3f}</span><span style='font-size: 10pt; color: #a0aabf;'> V</span>")
        self.ui.txt_volt_cell2.setText(f"<span style='font-weight: bold; color: white;'>{c2:.3f}</span><span style='font-size: 10pt; color: #a0aabf;'> V</span>")
        soc_c1 = int(max(0, min(100, (c1 - 3.0) / 1.2 * 100)))
        soc_c2 = int(max(0, min(100, (c2 - 3.0) / 1.2 * 100)))
        self.ui.bar_soc_cell1.setValue(soc_c1)
        self.ui.bar_soc_cell2.setValue(soc_c2)
        self.ui.txt_soh_cell1.setText("<span style='font-weight: bold; color: #00ff00;'>96%</span>")
        self.ui.txt_soh_cell2.setText("<span style='font-weight: bold; color: #00ff00;'>96%</span>")

    def display_cells_3_4_temp(self, c3, c4, temp, fault):
        self.ui.txt_volt_cell3.setText(f"<span style='font-weight: bold; color: white;'>{c3:.3f}</span><span style='font-size: 10pt; color: #a0aabf;'> V</span>")
        self.ui.txt_volt_cell4.setText(f"<span style='font-weight: bold; color: white;'>{c4:.3f}</span><span style='font-size: 10pt; color: #a0aabf;'> V</span>")
        soc_c3 = int(max(0, min(100, (c3 - 3.0) / 1.2 * 100)))
        soc_c4 = int(max(0, min(100, (c4 - 3.0) / 1.2 * 100)))
        self.ui.bar_soc_cell3.setValue(soc_c3)
        self.ui.bar_soc_cell4.setValue(soc_c4)
        self.ui.bar_temperature.setValue(int(max(0, min(100, temp))))
        self.ui.txt_temperature.setText(f"<span style='font-weight: bold; color: white;'>{temp:.1f}</span><span style='font-size: 10pt; color: #a0aabf;'> °C</span>")
        self.ui.txt_soh_cell3.setText("<span style='font-weight: bold; color: #00ff00;'>96%</span>")
        self.ui.txt_soh_cell4.setText("<span style='font-weight: bold; color: #00ff00;'>96%</span>")

    def display_pack_info(self, t_vol, t_cur):
        self.ui.txt_total_volt.setText(f"<span style='font-size: 28pt; font-weight: bold; color: white;'>{t_vol:.1f}</span><span style='font-size: 14pt; color: #a0aabf;'> V</span>")
        self.ui.txt_current.setText(f"<span style='font-size: 28pt; font-weight: bold; color: white;'>{t_cur:.1f}</span><span style='font-size: 14pt; color: #a0aabf;'> A</span>")
        soc_total = int(max(0, min(100, (t_vol - 12.0) / 4.8 * 100)))
        self.ui.txt_soc_total.setText(f"<span style='font-weight: bold; color: white;'>{soc_total}%</span>")
        self.ui.txt_soh_total.setText("<span style='font-weight: bold; color: #00ff00;'>93%</span>")
        self.ui.bar_soh_total.setValue(93)
        self.ui.txt_degradation.setText("<span style='font-weight: bold; color: #00ff00;'>7.0%</span>")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.showFullScreen() 
    sys.exit(app.exec_())