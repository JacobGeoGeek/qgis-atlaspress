from qgis.PyQt.QtCore import QAbstractListModel, QModelIndex, Qt, pyqtSignal


class OrderListModel(QAbstractListModel):
    OrderRole = Qt.ItemDataRole.UserRole + 1
    fetch_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._orders = []
        self._has_more = False
        self._loading = False
        self._failed = False
        self._active = False

    @property
    def orders(self):
        return list(self._orders)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._orders)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._orders):
            return None

        order = self._orders[index.row()]

        if role == self.OrderRole:
            return order
        if role == Qt.ItemDataRole.UserRole:
            return order.public_order_id
        if role == Qt.ItemDataRole.ToolTipRole:
            return f"Order {order.public_order_id}"
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.AccessibleTextRole):
            date = order.created_at.astimezone().strftime("%b %d, %Y %H:%M %Z")
            product = order.product.summary if order.product else "Product details unavailable"
            return (
                f"{date}\n{product}\nQuantity: {order.quantity}\n"
                f"{order.currency} {order.total:.2f} - {order.status.value}"
            )

        return None

    def canFetchMore(self, parent=QModelIndex()):
        return (
            not parent.isValid()
            and self._active
            and self._has_more
            and not self._loading
            and not self._failed
        )

    def fetchMore(self, parent=QModelIndex()):
        if self.canFetchMore(parent):
            self._loading = True
            self.fetch_requested.emit()

    def clear(self):
        self.beginResetModel()
        self._orders.clear()
        self._has_more = False
        self._loading = False
        self._failed = False
        self._active = False
        self.endResetModel()

    def append_orders(self, orders):
        if orders:
            start = len(self._orders)
            self.beginInsertRows(QModelIndex(), start, start + len(orders) - 1)
            self._orders.extend(orders)
            self.endInsertRows()

    def begin_fetch(self):
        self._loading = True
        self._failed = False

    def update_orders(self, orders, replace=False):
        """Update by public ID without resetting selection or pagination state."""
        if replace:
            wanted = {order.public_order_id for order in orders}
            for row in range(len(self._orders) - 1, -1, -1):
                if self._orders[row].public_order_id not in wanted:
                    self.beginRemoveRows(QModelIndex(), row, row)
                    self._orders.pop(row)
                    self.endRemoveRows()
            for row, order in enumerate(orders):
                source = next(
                    (
                        i
                        for i, item in enumerate(self._orders)
                        if item.public_order_id == order.public_order_id
                    ),
                    None,
                )
                if source is None:
                    self.beginInsertRows(QModelIndex(), row, row)
                    self._orders.insert(row, order)
                    self.endInsertRows()
                elif source != row:
                    self.beginMoveRows(QModelIndex(), source, source, QModelIndex(), row)
                    self._orders.insert(row, self._orders.pop(source))
                    self.endMoveRows()
        updates = {order.public_order_id: order for order in orders}
        for row, previous in enumerate(self._orders):
            updated = updates.get(previous.public_order_id, previous)
            if updated != previous:
                self._orders[row] = updated
                index = self.index(row, 0)
                self.dataChanged.emit(index, index)

    def finish_fetch(self, has_more, failed=False):
        self._has_more = has_more
        self._loading = False
        self._failed = failed
        self.layoutChanged.emit()

    def set_active(self, active):
        self._active = active
