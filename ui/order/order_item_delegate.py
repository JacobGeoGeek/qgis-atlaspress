from qgis.PyQt.QtCore import QRect, QRectF, QSize, Qt
from qgis.PyQt.QtGui import QFont, QFontMetrics, QPainter, QPalette
from qgis.PyQt.QtWidgets import QPushButton, QStyle, QStyledItemDelegate, QStyleOptionButton

from .order_list_model import OrderListModel


class OrderItemDelegate(QStyledItemDelegate):
    """Paint the reference card layout while retaining Qt's virtual list behavior."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Share one native button's style and sizing across the virtual list rows.
        self._details_button = QPushButton("View Details", parent)
        self._details_button.setAutoDefault(False)
        self._details_button.hide()

    def _layout(self, option, index):
        order = index.data(OrderListModel.OrderRole)
        width = option.rect.width()

        if width <= 0:
            width = self.parent().viewport().width()
        padding, margin, gap = 12, 4, 8
        content_width = max(1, width - 2 * (padding + margin))

        bold = QFont(option.font)
        bold.setBold(True)
        small = QFont(option.font)
        small.setPointSizeF(max(8, option.font.pointSizeF() - 1))

        metrics, bold_metrics, small_metrics = (
            QFontMetrics(font) for font in (option.font, bold, small)
        )

        date = order.created_at.astimezone().strftime("%b %d, %Y")
        status = order.status.value
        date_width = small_metrics.horizontalAdvance(date)
        status_width = bold_metrics.horizontalAdvance(status) + 16
        stacked_header = date_width + status_width + gap > content_width
        header_height = (
            bold_metrics.height() + small_metrics.height() + gap
            if stacked_header
            else max(bold_metrics.height(), small_metrics.height())
        )

        product = order.product.summary if order.product else "Product details unavailable"
        product += f" - Qty {order.quantity}"
        product_height = metrics.boundingRect(
            QRect(0, 0, content_width, 100000),
            Qt.TextFlag.TextWordWrap,
            product,
        ).height()

        button_size = self._details_button.sizeHint()
        total = f"{order.currency} {order.total:.2f}"

        stacked_footer = (
            bold_metrics.horizontalAdvance(total) + button_size.width() + gap > content_width
        )
        footer_height = (
            bold_metrics.height() + button_size.height() + gap
            if stacked_footer
            else max(bold_metrics.height(), button_size.height())
        )
        height = 2 * (padding + margin) + header_height + product_height + footer_height + 2 * gap

        return {
            "height": height,
            "width": width,
            "padding": padding,
            "margin": margin,
            "gap": gap,
            "bold": bold,
            "small": small,
            "date": date,
            "date_width": date_width,
            "status": status,
            "header_height": header_height,
            "stacked_header": stacked_header,
            "product": product,
            "product_height": product_height,
            "button_size": button_size,
            "total": total,
            "stacked_footer": stacked_footer,
        }

    def sizeHint(self, option, index):
        layout = self._layout(option, index)
        return QSize(layout["width"], layout["height"])

    def paint(self, painter, option, index):
        layout = self._layout(option, index)
        palette = self.parent().window().palette()
        highlighted = bool(
            option.state & (QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_MouseOver)
        )
        border = palette.color(
            QPalette.ColorRole.Highlight if highlighted else QPalette.ColorRole.Mid
        )
        background = palette.color(QPalette.ColorRole.Base)

        if highlighted:
            tint = palette.color(QPalette.ColorRole.Highlight)
            tint.setAlpha(24)

        card = option.rect.adjusted(
            layout["margin"], layout["margin"], -layout["margin"], -layout["margin"]
        )
        content = card.adjusted(
            layout["padding"], layout["padding"], -layout["padding"], -layout["padding"]
        )

        painter.save()
        painter.setClipRect(option.rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(border)
        painter.setBrush(background)
        painter.drawRoundedRect(QRectF(card), 6, 6)

        if highlighted:
            painter.setBrush(tint)
            painter.drawRoundedRect(QRectF(card), 6, 6)

        text = palette.color(QPalette.ColorRole.Text)
        painter.setPen(text)
        painter.setFont(layout["bold"])
        line_height = QFontMetrics(layout["bold"]).height()
        dot = QRect(content.x(), content.y() + (line_height - 7) // 2, 7, 7)
        painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(dot)
        painter.setPen(text)

        status_width = (
            content.width()
            if layout["stacked_header"]
            else content.width() - layout["date_width"] - layout["gap"]
        )

        painter.drawText(
            QRect(content.x() + 16, content.y(), status_width - 16, line_height),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            layout["status"],
        )
        painter.setFont(layout["small"])
        date_y = (
            content.y() + line_height + layout["gap"] if layout["stacked_header"] else content.y()
        )
        date_alignment = (
            Qt.AlignmentFlag.AlignLeft if layout["stacked_header"] else Qt.AlignmentFlag.AlignRight
        )
        painter.drawText(
            QRect(content.x(), date_y, content.width(), line_height),
            date_alignment | Qt.AlignmentFlag.AlignVCenter,
            layout["date"],
        )

        product_y = content.y() + layout["header_height"] + layout["gap"]
        painter.setFont(option.font)
        painter.drawText(
            QRect(content.x(), product_y, content.width(), layout["product_height"]),
            Qt.TextFlag.TextWordWrap,
            layout["product"],
        )
        footer_y = product_y + layout["product_height"] + layout["gap"]
        painter.setFont(layout["bold"])
        button_size = layout["button_size"]
        total_width = (
            content.width()
            if layout["stacked_footer"]
            else content.width() - button_size.width() - layout["gap"]
        )
        painter.drawText(
            QRect(
                content.x(),
                footer_y,
                total_width,
                line_height if layout["stacked_footer"] else max(line_height, button_size.height()),
            ),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            layout["total"],
        )

        button_y = footer_y + line_height + layout["gap"] if layout["stacked_footer"] else footer_y
        button_option = QStyleOptionButton()
        button_option.initFrom(self._details_button)
        button_option.text = self._details_button.text()
        button_option.rect = QRect(
            content.right() - button_size.width() + 1,
            button_y,
            button_size.width(),
            button_size.height(),
        )
        button_option.palette = palette

        painter.setFont(self._details_button.font())

        self._details_button.style().drawControl(
            QStyle.ControlElement.CE_PushButton,
            button_option,
            painter,
            self._details_button,
        )

        painter.restore()
