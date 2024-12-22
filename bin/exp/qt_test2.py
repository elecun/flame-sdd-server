import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui

class ColorGridExample(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Color Grid Example (10x100)")
        
        # Graphics Layout Widget
        layout = pg.GraphicsLayoutWidget()
        self.setCentralWidget(layout)

        # 10x100 Grid 생성
        rows, cols = 10, 100
        for row in range(rows):
            for col in range(cols):
                # 셀을 LabelItem으로 생성
                label = pg.LabelItem("test")
                layout.addItem(label, row=row, col=col)

                # 배경색 설정 (랜덤 또는 규칙적인 색상)
                color = QtGui.QColor((row * 25) % 255, (col * 2) % 255, 150)
                #label.setStyleSheet(f"background-color: {color.name()};")
                #label.setFixedSize(10, 10)  # 셀 크기 조정

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ColorGridExample()
    window.resize(1200, 400)  # 창 크기
    window.show()
    sys.exit(app.exec())
