"""Order tracking tests; use QGIS Python with QT_QPA_PLATFORM=offscreen."""

import importlib
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import test_order_history as history
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor, QPixmap
from qgis.PyQt.QtTest import QTest

models = history.models
shipment_module = importlib.import_module("atlaspress_test.ui.order.order_shipment_widget")


def shipment_json(**changes):
    data = {
        "carrier": "FEDEX",
        "service": "Standard",
        "trackingNumber": "0012345",
        "trackingUrl": "https://carrier.example/track/0012345?ref=order",
        "shippedAt": "2026-11-14T10:00:00.000Z",
        "reshipment": False,
    }
    data.update(changes)
    return data


def tracking_json(*shipments):
    return {"shipments": list(shipments)}


class TrackingModelTests(unittest.TestCase):
    def test_detail_composes_tracking_and_multiple_shipments(self):
        detail = models.OrderDetail.from_json(
            history.order_json(
                tracking=tracking_json(
                    shipment_json(), shipment_json(carrier="UPS", reshipment=True)
                )
            )
        )
        self.assertIsInstance(detail.tracking, models.OrderTracking)
        self.assertEqual(len(detail.tracking.shipments), 2)
        self.assertIsInstance(detail.tracking.shipments[0], models.OrderShipment)
        self.assertEqual(detail.tracking.shipments[0].tracking_number, "0012345")
        self.assertTrue(detail.tracking.shipments[1].reshipment)
        self.assertEqual(
            detail.tracking.shipments[0].shipped_at, datetime(2026, 11, 14, 10, tzinfo=timezone.utc)
        )

    def test_null_empty_and_independently_nullable_fields(self):
        self.assertIsNone(models.OrderDetail.from_json(history.order_json()).tracking)
        self.assertEqual(models.OrderTracking.from_json(tracking_json()).shipments, [])
        for name in ("carrier", "service", "trackingNumber", "trackingUrl", "shippedAt"):
            with self.subTest(field=name):
                shipment = models.OrderShipment.from_json(shipment_json(**{name: None}))
                self.assertEqual(shipment.reshipment, False)
        all_null = models.OrderShipment.from_json(
            shipment_json(
                carrier=None, service=None, trackingNumber=None, trackingUrl=None, shippedAt=None
            )
        )
        self.assertIsNone(all_null.tracking_number)

    def test_malformed_tracking_returns_structured_repository_error(self):
        client = Mock()
        repository = history.repository_module.OrderRepository(client)
        for tracking in (
            {"shipments": None},
            {"shipments": [shipment_json(trackingNumber=123)]},
            {"shipments": [shipment_json(reshipment="false")]},
            {"shipments": [shipment_json(shippedAt="invalid")]},
        ):
            with self.subTest(tracking=tracking):
                client.get.return_value.content_json.return_value = history.order_json(
                    tracking=tracking
                )
                result = repository.get_order_by_public_id(history.order_json()["publicOrderId"])
                self.assertIsNotNone(result.error)
                self.assertIsNone(result.data)

    def test_shipment_repr_does_not_expose_tracking_values(self):
        detail = models.OrderDetail.from_json(
            history.order_json(tracking=tracking_json(shipment_json()))
        )
        self.assertNotIn("0012345", repr(detail))
        self.assertNotIn("carrier.example", repr(detail))


class TrackingDialogTests(unittest.TestCase):
    setUp = history.DialogTests.setUp
    tearDown = history.DialogTests.tearDown
    load_page = history.DialogTests.load_page
    open_detail = history.DialogTests.open_detail

    def test_all_shipment_fields_and_reshipment_are_displayed_in_server_order(self):
        self.open_detail(
            tracking=tracking_json(shipment_json(), shipment_json(carrier="UPS", reshipment=True))
        )
        first, second = self.dialog._shipment_widgets
        self.assertEqual(first.title(), "Package 1")
        self.assertEqual(second.title(), "Package 2")
        self.assertEqual(first.carrierValueLabel.text(), "FEDEX")
        self.assertEqual(first.serviceValueLabel.text(), "Standard")
        self.assertEqual(first.trackingNumberValueLabel.text(), "0012345")
        self.assertEqual(
            first.shippedAtValueLabel.text(),
            history.controller_module.datetime(2026, 11, 14, 10, tzinfo=timezone.utc)
            .astimezone()
            .strftime("%b %d, %Y %H:%M %Z"),
        )
        self.assertTrue(first.reshipmentLabel.isHidden())
        self.assertFalse(second.reshipmentLabel.isHidden())
        self.assertTrue(self.dialog.trackingUnavailableLabel.isHidden())
        self.assertEqual(self.dialog.totalValueLabel.text(), "USD 58.00")

    def test_empty_tracking_and_missing_fields_do_not_imply_not_shipped(self):
        self.open_detail(status="SHIPPED", tracking=tracking_json())
        self.assertFalse(self.dialog.trackingUnavailableLabel.isHidden())
        self.assertEqual(self.dialog.statusBadgeLabel.text(), "Shipped")
        self.dialog.refreshOrdersButton.click()
        self.manager.finish(
            models.OrderDetail.from_json(
                history.order_json(
                    status="SHIPPED",
                    tracking=tracking_json(
                        shipment_json(
                            carrier=None,
                            service=None,
                            trackingNumber=None,
                            trackingUrl=None,
                            shippedAt=None,
                        )
                    ),
                )
            )
        )
        row = self.dialog._shipment_widgets[0]
        for label in (
            row.carrierValueLabel,
            row.serviceValueLabel,
            row.trackingNumberValueLabel,
            row.shippedAtValueLabel,
        ):
            self.assertEqual(label.text(), "Not available")
        self.assertTrue(row.trackPackageButton.isHidden())
        self.assertFalse(row.trackingLinkUnavailableLabel.isHidden())
        self.assertEqual(self.dialog.statusBadgeLabel.text(), "Shipped")

    def test_long_values_are_plain_wrapped_and_tracking_numbers_are_copyable(self):
        self.open_detail(
            tracking=tracking_json(
                shipment_json(
                    carrier="<b>Carrier</b>",
                    service="Long delivery service " * 20,
                    trackingNumber="0" * 120,
                )
            )
        )
        row = self.dialog._shipment_widgets[0]
        self.assertEqual(row.carrierValueLabel.textFormat(), Qt.TextFormat.PlainText)
        self.assertTrue(row.serviceValueLabel.wordWrap())
        self.assertTrue(row.trackingNumberValueLabel.wordWrap())
        self.assertTrue(
            row.trackingNumberValueLabel.textInteractionFlags()
            & Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.assertTrue(
            row.trackingNumberValueLabel.textInteractionFlags()
            & Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.assertEqual(row.trackingNumberValueLabel.text(), "0" * 120)
        self.dialog.resize(480, 520)
        QTest.qWait(20)
        self.assertEqual(self.dialog.detailScrollArea.horizontalScrollBar().maximum(), 0)

    def test_tracking_links_open_only_on_click_with_exact_returned_url(self):
        for scheme in ("http", "https"):
            with (
                self.subTest(scheme=scheme),
                patch.object(
                    shipment_module.QDesktopServices, "openUrl", return_value=True
                ) as open_url,
            ):
                url = f"{scheme}://carrier.example/track/0012345?ref=A%2BB"
                if self.controller._detail is None:
                    self.open_detail(tracking=tracking_json(shipment_json(trackingUrl=url)))
                else:
                    self.dialog.refreshOrdersButton.click()
                    self.manager.finish(
                        models.OrderDetail.from_json(
                            history.order_json(
                                tracking=tracking_json(shipment_json(trackingUrl=url))
                            )
                        )
                    )
                open_url.assert_not_called()
                count = len(self.manager.tasks)
                self.dialog._shipment_widgets[0].trackPackageButton.click()
                open_url.assert_called_once()
                self.assertEqual(open_url.call_args.args[0].toString(), url)
                self.assertEqual(len(self.manager.tasks), count)

    def test_missing_number_does_not_hide_available_link_or_other_fields(self):
        self.open_detail(tracking=tracking_json(shipment_json(trackingNumber=None)))
        row = self.dialog._shipment_widgets[0]
        self.assertEqual(row.trackingNumberValueLabel.text(), "Not available")
        self.assertEqual(row.carrierValueLabel.text(), "FEDEX")
        self.assertFalse(row.trackPackageButton.isHidden())

    def test_unsafe_or_missing_links_have_no_browser_action(self):
        urls = [
            None,
            "",
            "relative/path",
            "//carrier.example/track",
            "file:///tmp/file",
            "javascript:alert(1)",
            "data:text/html,test",
            "https://",
            "https://user:password@carrier.example/track",
        ]
        with patch.object(shipment_module.QDesktopServices, "openUrl") as open_url:
            self.open_detail(
                tracking=tracking_json(*(shipment_json(trackingUrl=url) for url in urls))
            )
            for row in self.dialog._shipment_widgets:
                self.assertTrue(row.trackPackageButton.isHidden())
                self.assertFalse(row.trackingLinkUnavailableLabel.isHidden())
                row.trackPackageButton.click()
            open_url.assert_not_called()

    def test_browser_failure_is_local_and_retryable_with_keyboard(self):
        self.open_detail(tracking=tracking_json(shipment_json()))
        row = self.dialog._shipment_widgets[0]
        with patch.object(shipment_module.QDesktopServices, "openUrl", side_effect=[False, True]):
            row.trackPackageButton.click()
            self.assertFalse(row.browserErrorLabel.isHidden())
            QTest.keyClick(row.trackPackageButton, Qt.Key.Key_Space)
            self.assertTrue(row.browserErrorLabel.isHidden())
        self.assertEqual(self.dialog.totalValueLabel.text(), "USD 58.00")
        self.assertIs(
            self.dialog.detailStackedWidget.currentWidget(), self.dialog.detailContentPage
        )

    def test_details_do_not_poll_and_refresh_keeps_current_order_and_prevents_duplicates(self):
        self.open_detail()
        self.assertEqual(self.dialog.refreshOrdersButton.text(), "Refresh Details")
        count = len(self.manager.tasks)
        history.APP.processEvents()
        self.dialog.activated.emit()
        self.assertEqual(len(self.manager.tasks), count)
        self.dialog.refreshOrdersButton.click()
        self.assertFalse(self.dialog.refreshOrdersButton.isEnabled())
        self.dialog.refreshOrdersButton.click()
        self.assertEqual(len(self.manager.tasks), count + 1)
        self.assertEqual(
            self.manager.tasks[-1]._public_order_id, history.order_json()["publicOrderId"]
        )
        self.assertIs(
            self.dialog.detailStackedWidget.currentWidget(), self.dialog.detailContentPage
        )
        self.manager.finish(
            models.OrderDetail.from_json(
                history.order_json(tracking=tracking_json(shipment_json()))
            )
        )
        self.assertTrue(self.dialog.refreshOrdersButton.isEnabled())
        self.assertEqual(len(self.dialog._shipment_widgets), 1)

    def test_refresh_reuses_unchanged_widgets_and_replaces_changed_packages(self):
        tracking = tracking_json(shipment_json())
        self.open_detail(tracking=tracking)
        original = self.dialog._shipment_widgets[0]
        self.dialog.refreshOrdersButton.click()
        self.manager.finish(models.OrderDetail.from_json(history.order_json(tracking=tracking)))
        self.assertIs(self.dialog._shipment_widgets[0], original)
        self.dialog.refreshOrdersButton.click()
        self.manager.finish(
            models.OrderDetail.from_json(
                history.order_json(
                    tracking=tracking_json(shipment_json(), shipment_json(reshipment=True))
                )
            )
        )
        self.assertEqual(len(self.dialog._shipment_widgets), 2)
        self.assertTrue(original._tracking_url.isEmpty())
        self.assertEqual(original.trackingNumberValueLabel.text(), "")
        self.dialog.refreshOrdersButton.click()
        self.manager.finish(models.OrderDetail.from_json(history.order_json()))
        self.assertEqual(self.dialog._shipment_widgets, [])
        self.assertFalse(self.dialog.trackingUnavailableLabel.isHidden())

    def test_temporary_refresh_error_keeps_tracking_and_preview(self):
        self.open_detail(tracking=tracking_json(shipment_json()))
        image = QPixmap(40, 20)
        image.fill(QColor("green"))
        self.dialog.show_preview(image)
        row = self.dialog._shipment_widgets[0]
        self.dialog.refreshOrdersButton.click()
        self.manager.finish(failure=history.error(500))
        self.assertIs(self.dialog._shipment_widgets[0], row)
        self.assertIs(self.dialog._pixmap, image)
        self.assertTrue(self.dialog.refreshOrdersButton.isEnabled())
        self.assertFalse(self.dialog.refreshStatusLabel.isHidden())
        self.assertEqual(self.dialog.totalValueLabel.text(), "USD 58.00")

    def test_successful_refresh_preserves_preview_scroll_and_filter(self):
        self.dialog.statusFilterComboBox.setCurrentIndex(
            self.dialog.statusFilterComboBox.findData(models.OrderStatus.PAID)
        )
        self.controller._network = Mock()
        self.controller._network.get.return_value = history.ImageReply(failed=True)
        shipments = [shipment_json(carrier=f"Carrier {i}") for i in range(6)]
        self.open_detail(mockup=history.preview(), tracking=tracking_json(*shipments))
        self.controller._reply.finished.emit()
        image = QPixmap(40, 20)
        image.fill(QColor("green"))
        self.dialog.show_preview(image)
        QTest.qWait(20)
        scroll = self.dialog.detailScrollArea.verticalScrollBar()
        scroll.setValue(200)
        position = scroll.value()
        self.dialog.refreshOrdersButton.click()
        self.manager.finish(
            models.OrderDetail.from_json(
                history.order_json(mockup=history.preview(), tracking=tracking_json(*shipments))
            )
        )
        QTest.qWait(20)
        self.assertIs(self.dialog._pixmap, image)
        self.assertEqual(scroll.value(), position)
        self.assertIs(self.dialog.statusFilterComboBox.currentData(), models.OrderStatus.PAID)
        self.controller._network.get.assert_called_once()

    def test_detail_refresh_does_not_consume_preview_retry_while_request_is_active(self):
        self.open_detail()
        self.dialog.refreshOrdersButton.click()
        count = len(self.manager.tasks)
        self.controller.refresh_preview()
        self.assertFalse(self.controller._manual_refreshed)
        self.assertEqual(len(self.manager.tasks), count)

    def test_unavailable_order_clears_tracking_during_refresh(self):
        self.open_detail(tracking=tracking_json(shipment_json()))
        row = self.dialog._shipment_widgets[0]
        self.dialog.refreshOrdersButton.click()
        self.manager.finish(failure=history.error(404))
        self.assertEqual(self.dialog._shipment_widgets, [])
        self.assertTrue(row._tracking_url.isEmpty())
        self.assertIs(self.dialog.detailStackedWidget.currentWidget(), self.dialog.detailErrorPage)

    def test_navigation_clears_tracking_and_reopening_fetches_again(self):
        self.open_detail(tracking=tracking_json(shipment_json()))
        row = self.dialog._shipment_widgets[0]
        self.dialog.refreshOrdersButton.click()
        old_task = self.manager.tasks[-1]
        self.controller.back_to_orders()
        self.assertTrue(old_task.isCanceled())
        self.assertTrue(row._tracking_url.isEmpty())
        self.assertEqual(self.dialog._shipment_widgets, [])
        self.assertEqual(self.dialog.refreshOrdersButton.text(), "Refresh Orders")
        old_task._callback(
            models.OrderDetail.from_json(
                history.order_json(tracking=tracking_json(shipment_json()))
            ),
            None,
        )
        self.assertEqual(self.dialog._shipment_widgets, [])
        count = len(self.manager.tasks)
        self.controller.open_order(history.order_json()["publicOrderId"])
        self.assertEqual(len(self.manager.tasks), count + 1)

    def test_close_and_auth_failure_clear_tracking_and_ignore_late_callbacks(self):
        for close in (False, True):
            with self.subTest(close=close):
                if close:
                    self.controller.refresh_orders()
                self.open_detail(tracking=tracking_json(shipment_json()))
                row = self.dialog._shipment_widgets[0]
                self.dialog.refreshOrdersButton.click()
                task = self.manager.tasks[-1]
                if close:
                    self.dialog.close()
                else:
                    self.manager.finish(failure=history.error(401))
                self.assertEqual(self.dialog._shipment_widgets, [])
                self.assertTrue(row._tracking_url.isEmpty())
                self.assertEqual(row.trackingNumberValueLabel.text(), "")
                task._callback(
                    models.OrderDetail.from_json(
                        history.order_json(tracking=tracking_json(shipment_json()))
                    ),
                    None,
                )
                self.assertEqual(self.dialog._shipment_widgets, [])


if __name__ == "__main__":
    unittest.main()
