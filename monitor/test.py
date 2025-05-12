import sys
import random
import time
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtCore import QTimer
import pyqtgraph as pg
from pyqtgraph import DateAxisItem


# 사용자 정의 x축 레이블 포맷 클래스
class CustomDateAxis(DateAxisItem):
    def tickStrings(self, values, scale, spacing):
        return [
            time.strftime('%Y.%m.%d %H:%M:%S', time.localtime(v)) for v in values
        ]


class RealTimePlot(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("12시간 실시간 그래프")

        # plot widget 생성 (x축: 날짜/시간)
        self.plot_widget = pg.PlotWidget(axisItems={'bottom': CustomDateAxis()})
        self.setCentralWidget(self.plot_widget)

        # 설정값
        self.data_lines = 8
        self.update_interval_sec = 10           # 데이터 갱신 주기: 10초
        self.max_history_secs = 12 * 3600       # 12시간 = 43200초

        # plot 설정
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend(offset=(10, 10))
        self.plot_widget.setLabel('bottom', 'datetime')
        self.plot_widget.setLabel('left', 'temperature')
        self.plot_widget.enableAutoRange(axis='y')

        # 곡선 초기화
        self.curves = []
        colors = ['r', 'g', 'b', 'c', 'm', 'y', 'w', 'k']
        for i in range(self.data_lines):
            curve = self.plot_widget.plot(pen=pg.mkPen(colors[i % len(colors)], width=2), name=f"Item {i+1}")
            self.curves.append({'curve': curve, 'x': [], 'y': []})

        # 타이머 설정
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(self.update_interval_sec * 1000)

    def update_data(self):
        now = time.time()

        # 데이터 추가 및 오래된 데이터 제거
        for i in range(self.data_lines):
            self.curves[i]['x'].append(now)
            self.curves[i]['y'].append(random.uniform(0, 100))

            # 12시간 초과 데이터 삭제
            while self.curves[i]['x'] and self.curves[i]['x'][0] < now - self.max_history_secs:
                self.curves[i]['x'].pop(0)
                self.curves[i]['y'].pop(0)

            self.curves[i]['curve'].setData(self.curves[i]['x'], self.curves[i]['y'])

        # 항상 x축 범위를 현재 시각 기준 12시간 고정
        start_time = now - self.max_history_secs
        end_time = now
        self.plot_widget.setXRange(start_time, end_time, padding=0)

        # x축 tick 설정 (1시간 간격, 레이블은 3시간마다만 표시)
        tick_interval = 3600         # 1시간 간격 그리드
        label_interval = 3 * 3600    # 3시간마다 레이블 표시

        tick_positions = list(range(
            int(start_time) // tick_interval * tick_interval,
            int(end_time) + tick_interval,
            tick_interval
        ))

        major_ticks = [
            (t, time.strftime('%Y.%m.%d %H:%M:%S', time.localtime(t))) if t % label_interval == 0 else (t, '')
            for t in tick_positions
        ]

        self.plot_widget.getAxis('bottom').setTicks([major_ticks])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = RealTimePlot()
    win.resize(1200, 600)
    win.show()
    sys.exit(app.exec())