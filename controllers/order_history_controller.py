from datetime import datetime, timezone

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject, QTimer, QUrl
from qgis.PyQt.QtGui import QAction, QIcon, QPixmap
from qgis.PyQt.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from ..core.order.models import OrderSort
from ..core.order.order_repository import OrderRepository
from ..core.order.order_service import OrderService
from ..core.order.tasks import GetOrderDetailTask, ListOrdersTask
from ..ui.order import OrderHistoryDialog


class OrderHistoryController(QObject):
    def __init__(self, iface, http_client, task_manager=None, order_service=None):
        super().__init__(iface.mainWindow())
        self._iface = iface
        self._menu_name = "Atlas Press"
        self._has_access_token = bool(http_client.access_token)
        self._configured_service = order_service or OrderService(OrderRepository(http_client))
        self._task_manager = task_manager or QgsApplication.taskManager()
        self._service = None
        self._dialog = None
        self._generation = 0
        self._detail_generation = 0
        self._list_task = None
        self._detail_task = None
        self._reply = None
        self._cursor = None
        self._status_filter = None
        self._sort_order = OrderSort.NEWEST
        self._detail = None
        self._public_id = None
        self._auto_refreshed = False
        self._manual_refreshed = False
        self._network = QNetworkAccessManager(self)
        self._preview_timeout = QTimer(self)
        self._preview_timeout.setSingleShot(True)
        self._preview_timeout.setInterval(30000)
        self._preview_timeout.timeout.connect(self._preview_timed_out)
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30000)
        self._refresh_timer.timeout.connect(self._poll_orders)
        self.action = QAction("My Orders", self)
        self.action.triggered.connect(self.show)

    def _on_query_changed(self):
        self._status_filter = self._dialog.statusFilterComboBox.currentData()
        self._sort_order = self._dialog.sortOrderComboBox.currentData()
        self.refresh_orders()

    def _reset_filters(self):
        if self._status_filter is None and self._sort_order is OrderSort.NEWEST:
            return
        self._dialog.reset_query_controls()
        self._on_query_changed()

    def _activated(self):
        if (
            self._detail_task is None
            and self._detail is not None
            and self._detail.mockup is not None
        ):
            if self._detail.mockup.expires_at <= datetime.now(timezone.utc):
                self._ensure_preview()

    def _cancel_all(self):
        self._refresh_timer.stop()
        self._generation += 1
        self._cancel_detail()

        if self._list_task is not None:
            self._list_task.cancel()
            self._list_task = None
        self._cursor = None

    def _poll_orders(self):
        if (
            self._dialog is None
            or not self._dialog.isVisible()
            or self._service is None
            or self._list_task is not None
            or self._detail_task is not None
        ):
            return
        dialog = self._dialog
        if dialog.screenStackedWidget.currentWidget() is dialog.detailScreenPage:
            if self._detail is not None and self._reply is None:
                self._fetch_detail(background=True)
        elif dialog.listStackedWidget.currentWidget() in (
            dialog.listContentPage,
            dialog.listEmptyPage,
        ):
            self._refresh_list()

    def _refresh_list(self):
        dialog = self._dialog
        generation = self._generation
        status, sort = self._status_filter, self._sort_order
        target_count = dialog.orders_model.rowCount()
        refreshed = []
        seen_ids = set()
        seen_cursors = set()
        dialog.orders_model.begin_fetch()

        def request_page(cursor=None):
            seen_cursors.add(cursor)
            self._list_task = ListOrdersTask(
                self._service, cursor, finished, status=status, sort=sort
            )
            self._task_manager.addTask(self._list_task)

        def finished(page, error):
            if not self._valid(generation):
                return
            self._list_task = None
            if error is not None:
                if self._auth_error(error):
                    return
                dialog.refreshStatusLabel.setText(self._error_message(error))
                dialog.refreshStatusLabel.show()
                dialog.orders_model.finish_fetch(self._cursor is not None, failed=True)
                return
            for order in page.orders:
                if order.public_order_id not in seen_ids:
                    seen_ids.add(order.public_order_id)
                    refreshed.append(order)
            if (
                len(refreshed) < target_count
                and page.next_cursor is not None
                and page.next_cursor not in seen_cursors
            ):
                request_page(page.next_cursor)
                return
            dialog.refreshStatusLabel.hide()
            dialog.loadMoreErrorLabel.clear()
            dialog.pageRetryButton.hide()
            scroll = dialog.ordersListView.verticalScrollBar()
            position = scroll.value()
            dialog.orders_model.update_orders(refreshed, replace=True)
            self._cursor = page.next_cursor
            dialog.listStackedWidget.setCurrentWidget(
                dialog.listContentPage if refreshed else dialog.listEmptyPage
            )
            dialog.orders_model.finish_fetch(self._cursor is not None)
            scroll.setValue(position)

        request_page()

    def _cancel_detail(self):
        self._detail_generation += 1

        if self._detail_task is not None:
            self._detail_task.cancel()
            self._detail_task = None

        self._cancel_image()
        self._detail = None
        self._public_id = None

    def _cancel_image(self):
        self._preview_timeout.stop()
        reply, self._reply = self._reply, None

        if reply is not None:
            reply.abort()
            reply.deleteLater()

    def _closed(self):
        self._cancel_all()
        self._service = None
        self._dialog.clear_user_data()

    def _valid(self, generation, detail_generation=None):
        return (
            generation == self._generation
            and self._dialog is not None
            and self._dialog.isVisible()
            and self._service is not None
            and (detail_generation is None or detail_generation == self._detail_generation)
        )

    def _load_page(self, append=False):
        dialog = self._dialog
        dialog.queryControlsWidget.show()
        dialog.set_empty_message(self._status_filter is not None)
        generation = self._generation
        dialog.orders_model.begin_fetch()
        dialog.pageRetryButton.hide()
        if append:
            dialog.loadingMoreLabel.show()
        else:
            dialog.listStackedWidget.setCurrentWidget(dialog.listLoadingPage)
            dialog.set_loading(list_loading=True)
        dialog.loadMoreErrorLabel.clear()

        def finished(page, error):
            if not self._valid(generation):
                return
            self._list_task = None
            dialog._spinners[0].stop()
            dialog.loadingMoreLabel.hide()
            if error is not None:
                if self._auth_error(error):
                    return
                message = self._error_message(error)
                if append:
                    dialog.loadMoreErrorLabel.setText(message)
                    dialog.pageRetryButton.show()
                else:
                    dialog.listErrorMessageLabel.setText(message)
                    dialog.listStackedWidget.setCurrentWidget(dialog.listErrorPage)
                dialog.orders_model.finish_fetch(self._cursor is not None, failed=True)
                return
            self._cursor = page.next_cursor
            dialog.append_orders(page.orders)
            dialog.listStackedWidget.setCurrentWidget(
                dialog.listContentPage if dialog.orders_model.rowCount() else dialog.listEmptyPage
            )
            dialog.orders_model.set_active(
                dialog.screenStackedWidget.currentWidget() is dialog.listScreenPage
            )
            dialog.orders_model.finish_fetch(self._cursor is not None)

        self._list_task = ListOrdersTask(
            self._service,
            self._cursor if append else None,
            finished,
            status=self._status_filter,
            sort=self._sort_order,
        )
        self._task_manager.addTask(self._list_task)

    def _fetch_detail(self, preview_only=False, background=False):
        if self._detail_task is not None or self._service is None:
            return

        if not background:
            self._cancel_image()
        generation, detail_generation = self._generation, self._detail_generation
        dialog = self._dialog

        if background:
            pass
        elif preview_only:
            dialog.clear_preview()
            dialog.mockupOuterStackedWidget.setCurrentWidget(dialog.mockupPresentPage)
            dialog.mockupStackedWidget.setCurrentWidget(dialog.mockupLoadingPage)
            dialog.set_loading(preview_loading=True)
        else:
            dialog.screenStackedWidget.setCurrentWidget(dialog.detailScreenPage)
            dialog.detailStackedWidget.setCurrentWidget(dialog.detailLoadingPage)
            dialog.set_loading(detail_loading=True)

        def finished(detail, error):
            if not self._valid(generation, detail_generation):
                return

            self._detail_task = None
            if not background:
                dialog.set_loading()

            if error is not None:
                if self._auth_error(error):
                    return
                if background and error.status_code not in (403, 404):
                    dialog.refreshStatusLabel.setText(self._error_message(error, detail=True))
                    dialog.refreshStatusLabel.show()
                    return
                if preview_only and error.status_code != 404:
                    dialog.preview_error(not self._manual_refreshed)
                else:
                    self._detail = None
                    dialog.clear_preview()
                    dialog.detailErrorMessageLabel.setText(self._error_message(error, detail=True))
                    dialog.detailStackedWidget.setCurrentWidget(dialog.detailErrorPage)
                return

            previous = self._detail
            self._detail = detail
            dialog.refreshStatusLabel.hide()
            if self._status_filter is None or detail.summary.status is self._status_filter:
                dialog.orders_model.update_orders([detail.summary])
            else:
                dialog.orders_model.update_orders(
                    [
                        order
                        for order in dialog.orders_model.orders
                        if order.public_order_id != detail.summary.public_order_id
                    ],
                    replace=True,
                )
            dialog.show_detail(detail)
            if background:
                # Status polling must not bypass the bounded preview retry policy.
                if detail.mockup is None:
                    dialog.clear_preview()
                elif previous is None or previous.mockup is None:
                    self._ensure_preview()
                return
            self._ensure_preview()

        self._detail_task = GetOrderDetailTask(self._service, self._public_id, finished)
        self._task_manager.addTask(self._detail_task)

    def _ensure_preview(self):
        if self._detail is None:
            return

        preview = self._detail.mockup

        if preview is None:
            self._dialog.clear_preview()
            return
        if preview.expires_at <= datetime.now(timezone.utc):
            self._dialog.clear_preview()
            if not self._auto_refreshed:
                self._auto_refreshed = True
                self._fetch_detail(preview_only=True)
            else:
                self._dialog.preview_error(not self._manual_refreshed)
            return

        self._download_preview(preview.url)

    def _download_preview(self, url):
        self._cancel_image()
        dialog = self._dialog
        parsed = QUrl(url)

        if not parsed.isValid() or parsed.scheme() not in ("http", "https") or not parsed.host():
            dialog.preview_error(not self._manual_refreshed)
            return
        dialog.mockupOuterStackedWidget.setCurrentWidget(dialog.mockupPresentPage)
        dialog.mockupStackedWidget.setCurrentWidget(dialog.mockupLoadingPage)
        dialog.set_loading(preview_loading=True)

        request = QNetworkRequest(parsed)
        request.setAttribute(
            QNetworkRequest.Attribute.CacheLoadControlAttribute,
            QNetworkRequest.CacheLoadControl.AlwaysNetwork,
        )
        request.setAttribute(QNetworkRequest.Attribute.CacheSaveControlAttribute, False)

        reply = self._network.get(request)
        self._reply = reply

        generation, detail_generation = self._generation, self._detail_generation

        def finished():
            if self._reply is not reply or not self._valid(generation, detail_generation):
                return
            self._reply = None
            self._preview_timeout.stop()
            pixmap = QPixmap()

            if reply.error() == QNetworkReply.NetworkError.NoError:
                pixmap.loadFromData(reply.readAll())

            if pixmap.isNull():
                dialog.preview_error(not self._manual_refreshed)
            else:
                dialog.show_preview(pixmap)

            reply.deleteLater()

        reply.finished.connect(finished)
        self._preview_timeout.start()

    def _preview_timed_out(self):
        self._cancel_image()
        self._dialog.preview_error(not self._manual_refreshed)

    def _auth_error(self, error):
        if error.status_code != 401:
            return False

        self._cancel_all()
        self._service = None
        self._dialog.clear_user_data()

        return True

    def _error_message(self, error, detail=False):
        if detail and error.status_code in (403, 404):
            return "This order is unavailable."
        if error.status_code == 400:
            return "The order request could not be processed. Please refresh and try again."

        return "Order information is temporarily unavailable. Please try again."

    def install(self):
        self._iface.addPluginToWebMenu(self._menu_name, self.action)

        for menu_action in self._iface.webMenu().actions():
            menu = menu_action.menu()
            if menu is not None and self.action in menu.actions():
                menu.setTitle(self._menu_name)
                menu.setIcon(QIcon(":/plugins/atlas_press/resources/icons/atlas_press.svg"))
                menu_action.setIconVisibleInMenu(True)
                break

    def unload(self):
        self._iface.removePluginWebMenu(self._menu_name, self.action)

        if self._dialog is not None:
            self._dialog.close()
            self._dialog.deleteLater()

        self._cancel_all()
        self.action.deleteLater()
        self.deleteLater()

    def show(self):
        if self._dialog is None:
            dialog = OrderHistoryDialog(self._iface.mainWindow())
            self._dialog = dialog
            dialog.refreshOrdersButton.clicked.connect(self.refresh_orders)
            dialog.statusFilterComboBox.currentIndexChanged.connect(self._on_query_changed)
            dialog.sortOrderComboBox.currentIndexChanged.connect(self._on_query_changed)
            dialog.resetFiltersButton.clicked.connect(self._reset_filters)
            dialog.orders_model.fetch_requested.connect(self.load_more)
            dialog.pageRetryButton.clicked.connect(self.load_more)
            dialog.listRetryButton.clicked.connect(self.refresh_orders)
            dialog.detailRetryButton.clicked.connect(self.retry_detail)
            dialog.backButton.clicked.connect(self.back_to_orders)
            dialog.order_selected.connect(self.open_order)
            dialog.mockupRefreshButton.clicked.connect(self.refresh_preview)
            dialog.activated.connect(self._activated)
            dialog.finished.connect(self._closed)
        if self._dialog.isVisible():
            self._dialog.raise_()
            self._dialog.activateWindow()
            return

        self._dialog.reset_query_controls()
        self._status_filter = None
        self._sort_order = OrderSort.NEWEST
        self._dialog.show()
        self.refresh_orders()

    def refresh_orders(self):
        self._cancel_all()
        self._service = None

        if self._dialog is None:
            return

        self._dialog.clear_user_data(preserve_query_controls=self._has_access_token)

        if self._has_access_token and self._dialog.isVisible():
            self._service = self._configured_service
            self._refresh_timer.start()
            self._load_page()

    def load_more(self):
        if self._service is not None and self._cursor is not None and self._list_task is None:
            self._load_page(append=True)

    def open_order(self, public_order_id):
        if self._service is None:
            return

        self._cancel_detail()
        self._dialog.orders_model.set_active(False)
        self._public_id = public_order_id
        self._auto_refreshed = False
        self._manual_refreshed = False
        self._dialog.clear_preview()
        self._fetch_detail()

    def retry_detail(self):
        if self._public_id is not None and self._detail_task is None:
            self._fetch_detail()

    def back_to_orders(self):
        self._cancel_detail()
        self._dialog.clear_preview()
        self._dialog.set_loading()
        self._dialog.screenStackedWidget.setCurrentWidget(self._dialog.listScreenPage)
        self._dialog.orders_model.set_active(True)
        self._poll_orders()

    def refresh_preview(self):
        if self._detail is None or self._manual_refreshed or self._service is None:
            return

        self._manual_refreshed = True
        self._fetch_detail(preview_only=True)
