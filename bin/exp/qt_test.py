from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QVBoxLayout
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtCore import QRectF


class GraphicsOnFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

        # QGraphicsScene 생성
        self.scene = QGraphicsScene()
        self.create_grid(10, 200)  # 10행 20열의 그리드 생성

        # QGraphicsView 생성 (QFrame 위에 올림)
        self.view = QGraphicsView(self.scene, self)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        # 레이아웃 설정
        layout = QVBoxLayout(self)
        layout.addWidget(self.view)
        self.setLayout(layout)

    def create_grid(self, rows, cols):
        """그리드를 생성하는 함수"""
        cell_width = 50  # 셀 너비
        cell_height = 50  # 셀 높이

        for row in range(rows):
            for col in range(cols):
                rect = QRectF(
                    col * cell_width,  # x 좌표
                    row * cell_height,  # y 좌표
                    cell_width,         # 셀 너비
                    cell_height         # 셀 높이
                )
                item = QGraphicsRectItem(rect)

                # 색상 설정
                #color = QColor(255, col * 10 % 255, row * 25 % 255)
                #item.setBrush(QBrush(color))
                item.setPen(QColor(200, 200, 200))  # 셀 테두리

                self.scene.addItem(item)


class MainWindow(QFrame):
    def __init__(self):
        super().__init__()

        # GraphicsOnFrame 추가
        self.graphics_frame = GraphicsOnFrame(self)

        # 레이아웃 설정
        layout = QVBoxLayout(self)
        layout.addWidget(self.graphics_frame)
        self.setLayout(layout)

        # 창 설정
        self.setWindowTitle("QGraphicsScene on QFrame")
        self.resize(800, 600)


if __name__ == "__main__":
    app = QApplication([])

    window = MainWindow()
    window.show()

    app.exec()
