import math

from qgis.PyQt.QtCore import QRectF, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QPainter
from qgis.PyQt.QtWidgets import QWidget


class SpinnerWidget(QWidget):
    def __init__(self, parent=None, color="#93b023", size=32):
        super().__init__(parent)
        self._angle = 0
        self._color = QColor(color)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def start(self):
        self._timer.start(40)
        self.setVisible(True)

    def stop(self):
        self._timer.stop()
        self.setVisible(False)

    def _tick(self):
        self._angle = (self._angle + 15) % 360
        self.update()

    def paintEvent(self, event):
        size = min(self.width(), self.height())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        num_dots = 8
        dot_size = size * 0.18
        radius = size * 0.32

        for i in range(num_dots):
            angle = (2 * math.pi * i / num_dots) + math.radians(self._angle)
            x = self.width() / 2 + radius * math.cos(angle) - dot_size / 2
            y = self.height() / 2 + radius * math.sin(angle) - dot_size / 2
            color = QColor(self._color)
            color.setAlpha(int(255 * (i + 1) / num_dots))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QRectF(x, y, dot_size, dot_size))

        painter.end()
