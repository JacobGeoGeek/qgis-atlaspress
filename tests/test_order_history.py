"""Run with QGIS Python and QT_QPA_PLATFORM=offscreen; no live credentials required."""

import importlib
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from qgis.PyQt.QtCore import (
    QBuffer,
    QByteArray,
    QEvent,
    QIODevice,
    QObject,
    QRect,
    Qt,
    QUrl,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QColor, QFont, QImage
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
from qgis.PyQt.QtTest import QTest
from qgis.PyQt.QtWidgets import QApplication, QMainWindow, QMenu, QStyleOptionViewItem

# Exercise relative plugin imports without requiring installation in the QGIS profile.
package = types.ModuleType("atlaspress_test")
package.__path__ = [str(Path(__file__).resolve().parents[1])]
sys.modules.setdefault("atlaspress_test", package)
importlib.import_module("atlaspress_test.resources")
controller_module = importlib.import_module("atlaspress_test.controllers.order_history_controller")
models = importlib.import_module("atlaspress_test.core.order.models")
repository_module = importlib.import_module("atlaspress_test.core.order.order_repository")
http_module = importlib.import_module("atlaspress_test.core.config.http_client")
error_module = importlib.import_module("atlaspress_test.core.config.model.http_response")

APP = QApplication.instance() or QApplication([])


def order_json(number=1, **changes):
    data = {
        "publicOrderId": f"00000000-0000-4000-8000-{number:012d}",
        "createdAt": "2026-11-01T10:00:00.123456+00:00",
        "updatedAt": "2026-11-01T11:00:00Z",
        "status": "PAID",
        "product": {"name": "Poster", "type": "poster", "widthIn": 24, "heightIn": 18},
        "quantity": 1,
        "total": 58,
        "currency": "USD",
        "paidAt": None,
        "itemSubtotal": 50,
        "shippingTotal": 5,
        "taxTotal": 3,
        "tracking": None,
        "mockup": None,
    }
    data.update(changes)
    return data


def preview(expired=False):
    delta = timedelta(hours=-1 if expired else 1)
    return {
        "previewUrl": "https://storage.test/preview?token=temporary",
        "previewExpiresAt": (datetime.now(timezone.utc) + delta).isoformat(),
    }


def error(status):
    return error_module.HttpResponseError(status, "SENSITIVE_SERVER_DIAGNOSTICS", [])


class TaskManager:
    def __init__(self):
        self.tasks = []

    def addTask(self, task):
        self.tasks.append(task)

    def finish(self, data=None, failure=None):
        self.tasks[-1]._callback(data, failure)


class ImageReply(QObject):
    finished = pyqtSignal()

    def __init__(self, content=b"", failed=False):
        super().__init__()
        self.content = content
        self.failed = failed
        self.aborted = False

    def error(self):
        return (
            QNetworkReply.NetworkError.UnknownNetworkError
            if self.failed
            else QNetworkReply.NetworkError.NoError
        )

    def readAll(self):
        return QByteArray(self.content)

    def abort(self):
        self.aborted = True
        self.finished.emit()


class ApiTests(unittest.TestCase):
    def test_submitted_status_uses_provider_neutral_label(self):
        detail = models.OrderDetail.from_json(order_json(status="SUBMITTED_TO_PRINTFUL"))
        self.assertEqual(detail.summary.status.value, "Submitted for fulfillment")

    def test_nullable_fields_dates_saved_money_and_statuses(self):
        for status in models.OrderStatus:
            detail = models.OrderDetail.from_json(order_json(status=status.name, product=None))
            self.assertEqual(detail.summary.status, status)
            self.assertIsNone(detail.summary.product)
            self.assertIsNone(detail.mockup)
            self.assertIsNone(detail.paid_at)
            self.assertEqual(detail.summary.total, Decimal("58"))
            self.assertEqual(detail.summary.created_at.microsecond, 123456)
        self.assertEqual(models.money(0.29), Decimal("0.29"))

    def test_opaque_cursor_encoding_preserves_exact_value(self):
        client = Mock()
        client.get.return_value.content_json.return_value = {"orders": [], "nextCursor": None}
        repo = repository_module.OrderRepository(client)
        cursor = "v1:+/%= &?unicode-\u00e9"
        result = repo.list_orders(cursor)
        self.assertIsNone(result.error)
        endpoint = client.get.call_args.kwargs["endpoint"]
        self.assertEqual(parse_qs(urlsplit(endpoint).query), {"limit": ["20"], "cursor": [cursor]})
        encoded_url = bytes(
            http_module.HttpClient("http://localhost", "user")._build_url(endpoint).toEncoded()
        ).decode()
        self.assertEqual(parse_qs(urlsplit(encoded_url).query)["cursor"], [cursor])
        repo.list_orders()
        client.get.assert_called_with(endpoint="/functions/v1/orders?limit=20")

    def test_detail_route_and_structured_errors(self):
        client = Mock()
        client.get.return_value.content_json.return_value = order_json()
        repo = repository_module.OrderRepository(client)
        public_id = order_json()["publicOrderId"]
        result = repo.get_order_by_public_id(public_id)
        self.assertIsInstance(result, models.OrderDetailResult)
        self.assertEqual(result.data.summary.public_order_id, public_id)
        client.get.assert_called_with(endpoint=f"/functions/v1/orders/{public_id}")
        client.get.return_value.is_success.return_value = False
        client.get.return_value.status_code.return_value = 401
        client.get.return_value.content_json.return_value = {"error": "Expired", "details": []}
        self.assertEqual(repo.list_orders().error.status_code, 401)

    def test_malformed_response_is_safe(self):
        client = Mock()
        repo = repository_module.OrderRepository(client)
        for payload in (None, [], {}, {"orders": [], "nextCursor": 1}):
            client.get.return_value.content_json.return_value = payload
            self.assertIsNotNone(repo.list_orders().error)

    def test_page_and_detail_keep_their_own_result_types_on_failure(self):
        client = Mock()
        repo = repository_module.OrderRepository(client)
        client.get.return_value.content_json.return_value = {"orders": [], "nextCursor": None}
        self.assertIsInstance(repo.list_orders(), models.OrderPageResult)
        for success in (False, True):
            client.get.return_value.is_success.return_value = success
            client.get.return_value.status_code.return_value = 400 if not success else 200
            client.get.return_value.content_json.return_value = {"error": "Invalid request"}
            page_result = repo.list_orders()
            detail_result = repo.get_order_by_public_id(order_json()["publicOrderId"])
            self.assertIsInstance(page_result, models.OrderPageResult)
            self.assertIsInstance(detail_result, models.OrderDetailResult)
            self.assertIsNone(page_result.data)
            self.assertIsNone(detail_result.data)
            self.assertIsNotNone(page_result.error)
            self.assertIsNotNone(detail_result.error)

    def test_service_unwraps_specific_results_and_uses_public_id_lookup(self):
        service_module = importlib.import_module("atlaspress_test.core.order.order_service")
        repository = Mock(spec=repository_module.OrderRepository)
        page = models.OrderPage([], None)
        detail = models.OrderDetail.from_json(order_json())
        repository.list_orders.return_value = models.OrderPageResult(page, None)
        repository.get_order_by_public_id.return_value = models.OrderDetailResult(detail, None)
        service = service_module.OrderService(repository)
        self.assertIs(service.list_orders(), page)
        self.assertIs(service.get_order(detail.summary.public_order_id), detail)
        repository.get_order_by_public_id.assert_called_once_with(
            detail.summary.public_order_id,
            feedback=None,
        )

    def test_preview_repr_does_not_expose_signed_url(self):
        detail = models.OrderDetail.from_json(order_json(mockup=preview()))
        self.assertNotIn(detail.mockup.url, repr(detail.mockup))
        self.assertNotIn(detail.mockup.url, repr(detail))

    def test_auth_uses_only_the_user_access_token(self):
        request = QNetworkRequest(QUrl("http://localhost/functions/v1/orders"))
        http_module.HttpClient("http://localhost", "genuine-session")._apply_auth(request)
        self.assertEqual(bytes(request.rawHeader(b"Authorization")), b"Bearer genuine-session")
        self.assertFalse(request.hasRawHeader(b"apikey"))
        empty = QNetworkRequest(QUrl("http://localhost"))
        http_module.HttpClient("http://localhost", "")._apply_auth(empty)
        self.assertFalse(empty.hasRawHeader(b"apikey"))
        self.assertFalse(empty.hasRawHeader(b"Authorization"))

    def test_plugin_services_allow_missing_development_token(self):
        services = importlib.import_module("atlaspress_test.core.services")
        with patch.object(
            services,
            "load_config_file",
            return_value={
                "supabase": {"baseUrl": "http://localhost"},
            },
        ):
            self.assertEqual(services.create_core_services().http_client.access_token, "")

    def test_task_preserves_structured_error_and_cancelled_callback_is_suppressed(self):
        service_module = importlib.import_module("atlaspress_test.core.order.order_service")
        tasks = importlib.import_module("atlaspress_test.core.order.tasks")
        for task_class, method in (
            (tasks.ListOrdersTask, "list_orders"),
            (tasks.GetOrderDetailTask, "get_order"),
        ):
            with self.subTest(task=task_class.__name__):
                service = Mock()
                getattr(service, method).side_effect = service_module.OrderRequestError(error(401))
                callback = Mock()
                task = task_class(service, None, callback)
                task.finished(task.run())
                self.assertEqual(callback.call_args.args[1].status_code, 401)
                task.cancel()
                self.assertTrue(task._feedback.isCanceled())
                callback.reset_mock()
                task.finished(False)
                callback.assert_not_called()

    def test_order_tasks_handle_unexpected_errors_and_skip_cancelled_requests(self):
        tasks = importlib.import_module("atlaspress_test.core.order.tasks")
        for task_class, method in (
            (tasks.ListOrdersTask, "list_orders"),
            (tasks.GetOrderDetailTask, "get_order"),
        ):
            with self.subTest(task=task_class.__name__):
                service = Mock()
                request = getattr(service, method)
                request.side_effect = RuntimeError("SENSITIVE_SERVER_DIAGNOSTICS")
                callback = Mock()
                task = task_class(service, None, callback)
                task.finished(task.run())
                self.assertEqual(
                    callback.call_args.args[1].message, "Could not load order information."
                )
                task.cancel()
                request.reset_mock()
                self.assertFalse(task.run())
                request.assert_not_called()

    def test_detail_task_uses_public_id(self):
        tasks = importlib.import_module("atlaspress_test.core.order.tasks")
        service = Mock()
        service.get_order.return_value = models.OrderDetail.from_json(order_json())
        callback = Mock()
        public_id = order_json()["publicOrderId"]
        task = tasks.GetOrderDetailTask(service, public_id, callback)
        task.finished(task.run())
        service.get_order.assert_called_once_with(public_id, feedback=task._feedback)
        self.assertEqual(callback.call_args.args[0].summary.public_order_id, public_id)


class DialogTests(unittest.TestCase):
    def setUp(self):
        self.window = QMainWindow()
        self.iface = Mock()
        self.iface.mainWindow.return_value = self.window
        self.client = http_module.HttpClient("http://localhost", "owner-a")
        self.manager = TaskManager()
        self.service = Mock()
        self.controller = controller_module.OrderHistoryController(
            self.iface,
            self.client,
            self.manager,
            self.service,
        )
        self.controller.show()
        self.dialog = self.controller._dialog

    def tearDown(self):
        APP.setActiveWindow(None)
        APP.processEvents()
        self.controller.unload()
        self.window.close()
        self.window.deleteLater()
        APP.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()

    def load_page(self, numbers=(1,), cursor=None):
        self.manager.finish(
            models.OrderPage(
                [models.OrderSummary.from_json(order_json(number)) for number in numbers],
                cursor,
            )
        )

    def open_detail(self, **changes):
        self.load_page()
        self.controller.open_order(order_json()["publicOrderId"])
        self.manager.finish(models.OrderDetail.from_json(order_json(**changes)))

    def test_poll_timer_starts_and_skips_overlapping_requests(self):
        self.assertTrue(self.controller._refresh_timer.isActive())
        self.assertEqual(self.controller._refresh_timer.interval(), 30000)
        count = len(self.manager.tasks)
        self.controller._refresh_timer.timeout.emit()
        self.assertEqual(len(self.manager.tasks), count)
        self.load_page()
        self.controller._refresh_timer.timeout.emit()
        self.assertEqual(len(self.manager.tasks), count + 1)
        self.controller._refresh_timer.timeout.emit()
        self.assertEqual(len(self.manager.tasks), count + 1)

    def test_poll_refreshes_all_loaded_pages_preserving_selection_and_scroll(self):
        self.load_page(tuple(range(1, 41)), "old-next")
        APP.processEvents()
        view = self.dialog.ordersListView
        view.setCurrentIndex(self.dialog.orders_model.index(5, 0))
        view.verticalScrollBar().setValue(250)
        position = view.verticalScrollBar().value()
        resets = Mock()
        self.dialog.orders_model.modelReset.connect(resets)
        self.controller._refresh_timer.timeout.emit()
        self.assertIsNone(self.manager.tasks[-1]._cursor)
        self.manager.finish(
            models.OrderPage(
                [
                    models.OrderSummary.from_json(order_json(i, status="SHIPPED"))
                    for i in range(1, 21)
                ],
                "fresh-page-2",
            )
        )
        self.assertEqual(self.manager.tasks[-1]._cursor, "fresh-page-2")
        self.assertEqual(self.dialog.orders_model.orders[0].status, models.OrderStatus.PAID)
        self.manager.finish(
            models.OrderPage(
                [models.OrderSummary.from_json(order_json(i)) for i in range(21, 41)], "fresh-next"
            )
        )
        APP.processEvents()
        self.assertEqual(self.dialog.orders_model.rowCount(), 40)
        self.assertEqual(self.dialog.orders_model.orders[0].status, models.OrderStatus.SHIPPED)
        self.assertEqual(
            view.currentIndex().data(Qt.ItemDataRole.UserRole), order_json(6)["publicOrderId"]
        )
        self.assertEqual(view.verticalScrollBar().value(), position)
        self.assertEqual(self.controller._cursor, "fresh-next")
        resets.assert_not_called()

    def test_poll_later_page_failure_keeps_previous_rows_and_cursor(self):
        self.load_page(tuple(range(1, 41)), "original-next")
        self.controller._refresh_timer.timeout.emit()
        self.manager.finish(
            models.OrderPage(
                [
                    models.OrderSummary.from_json(order_json(i, status="SHIPPED"))
                    for i in range(1, 21)
                ],
                "new-page-2",
            )
        )
        self.manager.finish(failure=error(500))
        self.assertEqual(self.dialog.orders_model.rowCount(), 40)
        self.assertEqual(self.dialog.orders_model.orders[0].status, models.OrderStatus.PAID)
        self.assertEqual(self.controller._cursor, "original-next")

    def test_poll_removes_unavailable_rows_and_handles_empty_history(self):
        self.load_page((1, 2, 3))
        self.controller._refresh_timer.timeout.emit()
        self.load_page((2,))
        self.assertEqual(self.dialog.orders_model.rowCount(), 1)
        self.assertEqual(
            self.dialog.orders_model.orders[0].public_order_id, order_json(2)["publicOrderId"]
        )
        self.controller._refresh_timer.timeout.emit()
        self.load_page(())
        self.assertEqual(self.dialog.orders_model.rowCount(), 0)
        self.assertIs(self.dialog.listStackedWidget.currentWidget(), self.dialog.listEmptyPage)

    def test_poll_inserts_new_orders_in_server_order_without_reset(self):
        self.load_page((1, 2))
        self.dialog.ordersListView.setCurrentIndex(self.dialog.orders_model.index(0, 0))
        self.controller._refresh_timer.timeout.emit()
        self.load_page((3, 2, 1))
        self.assertEqual(
            [order.public_order_id for order in self.dialog.orders_model.orders],
            [order_json(i)["publicOrderId"] for i in (3, 2, 1)],
        )
        self.assertEqual(
            self.dialog.ordersListView.currentIndex().data(Qt.ItemDataRole.UserRole),
            order_json(1)["publicOrderId"],
        )

    def test_poll_error_preserves_data_and_cursor_and_recovers_next_tick(self):
        self.load_page(tuple(range(1, 21)), "next")
        self.controller._refresh_timer.timeout.emit()
        self.manager.finish(failure=error(500))
        self.assertEqual(self.dialog.orders_model.rowCount(), 20)
        self.assertEqual(self.controller._cursor, "next")
        self.assertFalse(self.dialog.refreshStatusLabel.isHidden())
        self.assertNotIn("SENSITIVE", self.dialog.refreshStatusLabel.text())
        self.assertTrue(self.controller._refresh_timer.isActive())
        self.controller._refresh_timer.timeout.emit()
        self.load_page(tuple(range(1, 21)), "next")
        self.assertTrue(self.dialog.refreshStatusLabel.isHidden())

    def test_detail_poll_updates_status_without_loading_page_or_preview_retry(self):
        self.controller._network = Mock()
        self.controller._network.get.return_value = ImageReply(failed=True)
        self.open_detail(mockup=preview())
        self.controller._reply.finished.emit()
        self.controller._refresh_timer.timeout.emit()
        self.assertIs(
            self.dialog.detailStackedWidget.currentWidget(), self.dialog.detailContentPage
        )
        self.manager.finish(
            models.OrderDetail.from_json(order_json(status="SHIPPED", mockup=preview()))
        )
        self.assertEqual(self.dialog.statusBadgeLabel.text(), "Shipped")
        self.assertEqual(self.dialog.orders_model.orders[0].status, models.OrderStatus.SHIPPED)
        self.controller._network.get.assert_called_once()
        self.assertIs(self.dialog.mockupStackedWidget.currentWidget(), self.dialog.mockupErrorPage)

    def test_detail_poll_temporary_failure_retains_content_but_404_is_unavailable(self):
        self.open_detail()
        self.controller._refresh_timer.timeout.emit()
        self.manager.finish(failure=error(500))
        self.assertEqual(self.dialog.totalValueLabel.text(), "USD 58.00")
        self.assertIs(
            self.dialog.detailStackedWidget.currentWidget(), self.dialog.detailContentPage
        )
        self.controller._refresh_timer.timeout.emit()
        self.manager.finish(failure=error(404))
        self.assertIs(self.dialog.detailStackedWidget.currentWidget(), self.dialog.detailErrorPage)

    def test_poll_stops_on_auth_error_and_close_and_ignores_delayed_result(self):
        self.load_page()
        self.controller._refresh_timer.timeout.emit()
        self.manager.finish(failure=error(401))
        self.assertFalse(self.controller._refresh_timer.isActive())
        self.assertEqual(self.dialog.orders_model.rowCount(), 0)
        self.controller.refresh_orders()
        self.load_page()
        self.controller._refresh_timer.timeout.emit()
        task = self.manager.tasks[-1]
        self.dialog.close()
        self.assertFalse(self.controller._refresh_timer.isActive())
        self.assertTrue(task.isCanceled())
        task._callback(models.OrderPage([models.OrderSummary.from_json(order_json())], None), None)
        self.assertEqual(self.dialog.orders_model.rowCount(), 0)
        self.controller.show()
        self.assertTrue(self.controller._refresh_timer.isActive())

    def test_menu_single_instance_empty_and_close_cleanup(self):
        self.assertEqual(self.controller.action.text(), "My Orders")
        web_menu = QMenu(self.window)
        submenu = web_menu.addMenu("atlaspress")
        self.iface.webMenu.return_value = web_menu
        self.iface.addPluginToWebMenu.side_effect = lambda name, action: submenu.addAction(action)
        self.controller.install()
        self.iface.addPluginToWebMenu.assert_called_once_with("Atlas Press", self.controller.action)
        self.assertEqual(submenu.title(), "Atlas Press")
        self.assertFalse(submenu.icon().isNull())
        self.assertTrue(submenu.menuAction().isIconVisibleInMenu())
        self.load_page(numbers=())
        self.assertIs(self.dialog.listStackedWidget.currentWidget(), self.dialog.listEmptyPage)
        self.controller.show()
        self.assertIs(self.controller._dialog, self.dialog)
        self.dialog.close()
        self.assertEqual(self.dialog.orders_model.orders, [])
        self.assertIsNone(self.controller._service)
        self.assertTrue(all(not spinner._timer.isActive() for spinner in self.dialog._spinners))

    def test_server_order_pagination_failure_retry_and_back(self):
        self.load_page((2, 1), "opaque")
        first_rows = list(self.dialog.orders_model.orders)
        self.controller.load_more()
        self.assertEqual(self.manager.tasks[-1]._cursor, "opaque")
        self.manager.finish(failure=error(500))
        self.assertEqual(self.dialog.orders_model.orders, first_rows)
        self.assertEqual(self.controller._cursor, "opaque")
        self.controller.load_more()
        self.manager.finish(models.OrderPage([models.OrderSummary.from_json(order_json(3))], None))
        self.assertEqual(self.dialog.orders_model.orders[:2], first_rows)
        self.assertEqual(len(self.dialog.orders_model.orders), 3)
        self.assertFalse(self.dialog.orders_model.canFetchMore())
        count = len(self.manager.tasks)
        self.controller.open_order(order_json()["publicOrderId"])
        self.manager.finish(models.OrderDetail.from_json(order_json(product=None)))
        self.assertEqual(self.dialog.productDetailLabel.text(), "Product details unavailable")
        self.assertEqual(self.dialog.totalValueLabel.text(), "USD 58.00")
        self.assertEqual(self.dialog.paidAtLabel.text(), "Not available")
        self.controller.back_to_orders()
        self.assertEqual(len(self.manager.tasks), count + 1)
        self.assertEqual(len(self.dialog.orders_model.orders), 3)

    def test_native_list_fetches_next_page_when_scrolled(self):
        self.load_page(tuple(range(1, 21)), "scroll-cursor")
        APP.processEvents()
        self.dialog.ordersListView.scrollToBottom()
        QTest.qWait(30)
        self.assertEqual(len(self.manager.tasks), 2)
        self.assertEqual(self.manager.tasks[-1]._cursor, "scroll-cursor")
        self.dialog.ordersListView.scrollToBottom()
        APP.processEvents()
        self.assertEqual(len(self.manager.tasks), 2)
        self.manager.finish(
            models.OrderPage(
                [models.OrderSummary.from_json(order_json(21))],
                None,
            )
        )
        self.dialog.ordersListView.scrollToBottom()
        APP.processEvents()
        self.assertEqual(len(self.manager.tasks), 2)
        self.assertEqual(self.dialog.orders_model.rowCount(), 21)

    def test_failed_scroll_request_pauses_until_explicit_retry(self):
        self.load_page(tuple(range(1, 21)), "retry-cursor")
        self.dialog.orders_model.fetchMore()
        self.manager.finish(failure=error(500))
        self.dialog.ordersListView.scrollToBottom()
        APP.processEvents()
        self.assertEqual(len(self.manager.tasks), 2)
        self.assertFalse(self.dialog.orders_model.canFetchMore())
        self.assertFalse(self.dialog.pageRetryButton.isHidden())
        self.dialog.pageRetryButton.click()
        self.assertEqual(len(self.manager.tasks), 3)
        self.assertEqual(self.manager.tasks[-1]._cursor, "retry-cursor")

    def test_native_row_activation_uses_public_id_and_preserves_scroll(self):
        self.load_page(tuple(range(1, 21)))
        APP.processEvents()
        self.dialog.ordersListView.scrollToBottom()
        APP.processEvents()
        position = self.dialog.ordersListView.verticalScrollBar().value()
        self.dialog.ordersListView.activated.emit(self.dialog.orders_model.index(19, 0))
        self.assertEqual(self.manager.tasks[-1]._public_order_id, order_json(20)["publicOrderId"])
        self.manager.finish(models.OrderDetail.from_json(order_json(20)))
        self.controller.back_to_orders()
        APP.processEvents()
        self.assertEqual(self.dialog.ordersListView.verticalScrollBar().value(), position)

    def test_clicking_card_details_action_opens_the_order(self):
        self.load_page()
        QTest.qWait(20)
        view = self.dialog.ordersListView
        rect = view.visualRect(self.dialog.orders_model.index(0, 0))
        point = rect.bottomRight()
        point.setX(point.x() - 55)
        point.setY(point.y() - 25)
        QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
        self.assertEqual(self.manager.tasks[-1]._public_order_id, order_json()["publicOrderId"])
        self.assertIs(self.dialog.screenStackedWidget.currentWidget(), self.dialog.detailScreenPage)
        self.dialog.backButton.click()
        self.assertIs(self.dialog.screenStackedWidget.currentWidget(), self.dialog.listScreenPage)

    def test_card_wraps_long_products_and_respects_larger_fonts(self):
        self.load_page()
        view = self.dialog.ordersListView
        delegate = view.itemDelegate()
        option = QStyleOptionViewItem()
        option.initFrom(view)
        option.rect = QRect(0, 0, 450, 0)
        index = self.dialog.orders_model.index(0, 0)
        short_height = delegate.sizeHint(option, index).height()
        self.dialog.orders_model.clear()
        product = {
            "name": "A detailed product description " * 8,
            "type": "poster",
            "widthIn": 24,
            "heightIn": 18,
        }
        self.dialog.append_orders([models.OrderSummary.from_json(order_json(product=product))])
        index = self.dialog.orders_model.index(0, 0)
        long_height = delegate.sizeHint(option, index).height()
        self.assertGreater(long_height, short_height)
        option.font = QFont(option.font)
        option.font.setPointSize(20)
        self.assertGreater(delegate.sizeHint(option, index).height(), long_height)

    def test_absent_preview_is_compact_and_id_tooltip_clears(self):
        self.open_detail()
        self.assertEqual(self.dialog.orderIdLabel.toolTip(), order_json()["publicOrderId"])
        self.assertLessEqual(self.dialog.mockupOuterStackedWidget.maximumHeight(), 80)
        self.dialog.close()
        self.assertEqual(self.dialog.orderIdLabel.toolTip(), "")

    def test_refresh_discards_stale_callbacks(self):
        old_task = self.manager.tasks[-1]
        self.load_page()
        self.controller.refresh_orders()
        self.assertEqual(self.dialog.orders_model.orders, [])
        self.assertIsNone(self.controller._cursor)
        self.assertIs(self.controller._service, self.service)
        old_task._callback(
            models.OrderPage([models.OrderSummary.from_json(order_json())], None), None
        )
        self.assertEqual(self.dialog.orders_model.orders, [])
        self.load_page((2,))
        self.assertEqual(len(self.dialog.orders_model.orders), 1)
        self.dialog.close()
        self.assertEqual(self.dialog.orders_model.orders, [])
        self.assertEqual(self.dialog.orderIdLabel.text(), "")
        self.assertIs(self.dialog.listStackedWidget.currentWidget(), self.dialog.listAuthPage)

    def test_reload_with_another_user_starts_clean_and_ignores_old_callbacks(self):
        self.load_page()
        self.controller.open_order(order_json()["publicOrderId"])
        old_task = self.manager.tasks[-1]
        old_dialog = self.dialog
        self.controller.unload()
        client = http_module.HttpClient("http://localhost", "owner-b")
        self.controller = controller_module.OrderHistoryController(self.iface, client, self.manager)
        self.controller.show()
        self.dialog = self.controller._dialog
        old_task._callback(models.OrderDetail.from_json(order_json()), None)
        self.assertEqual(old_dialog.orders_model.orders, [])
        self.assertEqual(old_dialog.orderIdLabel.text(), "")
        self.assertEqual(self.dialog.orders_model.orders, [])
        self.assertEqual(self.dialog.orderIdLabel.text(), "")
        self.assertIsNone(self.dialog._pixmap)
        self.assertIs(self.controller._configured_service._repository._http_client, client)
        self.load_page((2,))
        self.assertEqual(
            self.dialog.orders_model.orders[0].public_order_id, order_json(2)["publicOrderId"]
        )

    def test_missing_token_shows_instructions_without_request(self):
        window = QMainWindow()
        iface = Mock()
        iface.mainWindow.return_value = window
        manager = TaskManager()
        controller = controller_module.OrderHistoryController(
            iface, http_module.HttpClient("http://localhost", ""), manager
        )
        try:
            controller.show()
            dialog = controller._dialog
            self.assertIs(dialog.listStackedWidget.currentWidget(), dialog.listAuthPage)
            self.assertIn("reload the plugin", dialog.authConfigLabel.text())
            self.assertEqual(manager.tasks, [])
        finally:
            controller.unload()
            window.deleteLater()

    def test_stale_detail_after_back_is_ignored(self):
        self.load_page()
        self.controller.open_order(order_json()["publicOrderId"])
        old_task = self.manager.tasks[-1]
        self.controller.back_to_orders()
        old_task._callback(models.OrderDetail.from_json(order_json()), None)
        self.assertIs(self.dialog.screenStackedWidget.currentWidget(), self.dialog.listScreenPage)
        self.assertIsNone(self.controller._detail)

    def test_401_clears_all_views_and_does_not_retry(self):
        self.load_page()
        self.controller.open_order(order_json()["publicOrderId"])
        count = len(self.manager.tasks)
        self.manager.finish(failure=error(401))
        self.assertEqual(self.dialog.orders_model.orders, [])
        self.assertIs(self.dialog.listStackedWidget.currentWidget(), self.dialog.listAuthPage)
        self.assertEqual(len(self.manager.tasks), count)

    def test_request_and_unavailable_order_errors(self):
        for status in (400, 500, 0):
            self.controller.refresh_orders()
            self.manager.finish(failure=error(status))
            self.assertIs(self.dialog.listStackedWidget.currentWidget(), self.dialog.listErrorPage)
            self.assertNotIn("SENSITIVE", self.dialog.listErrorMessageLabel.text())
        self.controller.open_order(order_json()["publicOrderId"])
        self.manager.finish(failure=error(404))
        self.assertEqual(self.dialog.detailErrorMessageLabel.text(), "This order is unavailable.")

    def test_absent_preview_leaves_order_visible(self):
        self.open_detail()
        self.assertIs(
            self.dialog.mockupOuterStackedWidget.currentWidget(), self.dialog.mockupAbsentPage
        )
        self.assertIs(
            self.dialog.detailStackedWidget.currentWidget(), self.dialog.detailContentPage
        )

    def test_expired_url_refetch_is_bounded(self):
        self.open_detail(mockup=preview(expired=True))
        self.assertTrue(self.controller._auto_refreshed)
        count = len(self.manager.tasks)
        self.manager.finish(models.OrderDetail.from_json(order_json(mockup=preview(expired=True))))
        self.assertEqual(len(self.manager.tasks), count)
        self.assertIs(self.dialog.mockupStackedWidget.currentWidget(), self.dialog.mockupErrorPage)
        self.assertEqual(self.dialog.totalValueLabel.text(), "USD 58.00")
        self.controller.refresh_preview()
        self.manager.finish(models.OrderDetail.from_json(order_json(mockup=preview(expired=True))))
        self.assertTrue(self.dialog.mockupRefreshButton.isHidden())
        count = len(self.manager.tasks)
        self.controller.refresh_preview()
        self.assertEqual(len(self.manager.tasks), count)

    def test_image_failure_success_auth_free_and_close_cleanup(self):
        image = QImage(40, 20, QImage.Format.Format_RGB32)
        image.fill(QColor("green"))
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "JPEG")
        failed = ImageReply(failed=True)
        success = ImageReply(bytes(buffer.data()))
        network = Mock()
        network.get.side_effect = [failed, success]
        self.controller._network = network
        self.open_detail(mockup=preview())
        request = network.get.call_args.args[0]
        self.assertFalse(request.hasRawHeader(b"Authorization"))
        self.assertFalse(request.hasRawHeader(b"apikey"))
        failed.finished.emit()
        self.assertEqual(self.dialog.totalValueLabel.text(), "USD 58.00")
        self.controller.refresh_preview()
        self.manager.finish(models.OrderDetail.from_json(order_json(mockup=preview())))
        success.finished.emit()
        self.assertIsNotNone(self.dialog._pixmap)
        self.dialog.resize(480, 520)
        APP.processEvents()
        self.dialog.close()
        self.assertIsNone(self.dialog._pixmap)
        self.assertEqual(self.dialog.totalValueLabel.text(), "")
        self.assertFalse(self.controller._preview_timeout.isActive())

    def test_close_aborts_download_and_stale_details_cannot_repopulate(self):
        reply = ImageReply()
        self.controller._network = Mock()
        self.controller._network.get.return_value = reply
        self.open_detail(mockup=preview())
        self.dialog.close()
        self.assertTrue(reply.aborted)
        self.assertEqual(self.dialog.orders_model.orders, [])
        self.assertIsNone(self.dialog._pixmap)


class ConfigurationTests(unittest.TestCase):
    def test_server_keys_are_rejected(self):
        services = importlib.import_module("atlaspress_test.core.services")
        for token in (
            "sb_secret_example",
            "header.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.signature",
        ):
            with (
                self.subTest(token_type=token.split(".")[0]),
                patch.object(
                    services,
                    "load_config_file",
                    return_value={
                        "supabase": {"baseUrl": "http://localhost", "accessToken": token}
                    },
                ),
            ):
                with self.assertRaises(ValueError):
                    services.create_core_services()


if __name__ == "__main__":
    unittest.main()
